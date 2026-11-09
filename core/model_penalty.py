"""Persistent, process-safe tracking of model startup failures (POSIX)."""

from __future__ import annotations

import fcntl
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, TypeVar

from core.model_penalty_fsm import (
    FailureKind,
    classify_failure,
    is_penalizing_failure,
)
from core.runtime_env import flag_enabled


DEFAULT_MAX_START_FAILS = int(os.environ.get("BRIDGE_MAX_START_FAILS", "3"))
DEFAULT_INITIAL_COOLDOWN_SECONDS = float(
    os.environ.get("BRIDGE_INITIAL_COOLDOWN_SECONDS", "10.0")
)
DEFAULT_STEP2_COOLDOWN_SECONDS = float(
    os.environ.get("BRIDGE_STEP2_COOLDOWN_SECONDS", "30.0")
)
DEFAULT_STEP3_COOLDOWN_SECONDS = float(
    os.environ.get("BRIDGE_STEP3_COOLDOWN_SECONDS", "120.0")
)
DEFAULT_MAX_COOLDOWN_SECONDS = float(
    os.environ.get("BRIDGE_MAX_COOLDOWN_SECONDS", "300.0")
)
DEFAULT_COOLDOWN_SECONDS = DEFAULT_INITIAL_COOLDOWN_SECONDS
DEFAULT_STORAGE_PATH = Path(
    "~/.config/cli-agent-bridge/model_penalties.json"
).expanduser()

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")
_State = dict[str, dict[str, Any]]
_DISABLED_MAX_START_FAILS = 999999999


def _is_infrastructure_network_error(error_reason: str | None) -> bool:
    """Identify infrastructure failures that must not penalize a model."""
    return (
        classify_failure(error_reason, strict_classify=False)
        == FailureKind.INFRASTRUCTURE_FAILURE
    )


def _is_finite_nonnegative(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return 0.0 <= float(value) < float("inf")
    except (OverflowError, ValueError):
        return False


def _configured_max_start_fails(value: int | None) -> int:
    candidate = (
        value
        if value is not None
        else os.environ.get("BRIDGE_MAX_START_FAILS", DEFAULT_MAX_START_FAILS)
    )
    try:
        if isinstance(candidate, bool):
            raise ValueError("boolean is not a failure count")
        if not isinstance(candidate, (int, str)):
            raise ValueError("failure count must be an integer")
        result = int(candidate)
        if result < 1:
            raise ValueError("failure count must be positive")
        return result
    except (TypeError, ValueError, OverflowError):
        _LOGGER.warning(
            "Invalid max_start_fails %r; using %d",
            candidate,
            DEFAULT_MAX_START_FAILS,
        )
        return DEFAULT_MAX_START_FAILS


def _configured_cooldown(value: float | None) -> float:
    candidate = (
        value
        if value is not None
        else os.environ.get("BRIDGE_COOLDOWN_SECONDS", DEFAULT_COOLDOWN_SECONDS)
    )
    try:
        if isinstance(candidate, bool):
            raise ValueError("boolean is not a cooldown")
        result = float(candidate)
        if not _is_finite_nonnegative(result):
            raise ValueError("cooldown must be finite and nonnegative")
        return result
    except (TypeError, ValueError, OverflowError):
        _LOGGER.warning(
            "Invalid cooldown_seconds %r; using %s",
            candidate,
            DEFAULT_COOLDOWN_SECONDS,
        )
        return DEFAULT_COOLDOWN_SECONDS


def _empty_entry() -> dict[str, Any]:
    return {
        "fails": 0,
        "penalized_until": 0.0,
        "last_fail_at": 0.0,
        "last_error": None,
        "penalty_trips": 0,
    }


class ModelPenaltyTracker:
    """Track failures using a JSON file and a separate, stable flock file.

    Every operation reloads persisted state while holding the process lock.
    If persistence is unavailable, operations use the last in-memory state.
    """

    def __init__(
        self,
        storage_path: Path | str | None = None,
        max_start_fails: int | None = None,
        cooldown_seconds: float | None = None,
    ):
        configured_path = (
            storage_path
            if storage_path is not None
            else os.environ.get(
                "BRIDGE_MODEL_PENALTIES_PATH", str(DEFAULT_STORAGE_PATH)
            )
        )
        self.storage_path = Path(configured_path).expanduser()
        self.lock_path = self.storage_path.with_suffix(".json.lock")
        self._has_custom_max_start_fails = (
            max_start_fails is not None
            or bool(os.environ.get("BRIDGE_MAX_START_FAILS", "").strip())
        )
        self.configured_max_start_fails = _configured_max_start_fails(
            max_start_fails
        )
        self.max_start_fails = self.configured_max_start_fails
        self.enabled = True
        self._has_custom_cooldown = (
            cooldown_seconds is not None
            or bool(os.environ.get("BRIDGE_COOLDOWN_SECONDS", "").strip())
        )
        self.cooldown_seconds = _configured_cooldown(cooldown_seconds)
        self._lock = threading.Lock()
        self._state: _State = {}
        self._run(lambda: (None, False))

    def _load_state(self) -> _State | None:
        """Return None on I/O errors to preserve live in-memory state."""
        try:
            with self.storage_path.open("r", encoding="utf-8") as stream:
                raw = json.load(stream)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, UnicodeError, RecursionError) as exc:
            _LOGGER.warning(
                "Cannot load model penalties from %s: %s",
                self.storage_path,
                exc,
            )
            if isinstance(exc, OSError):
                return None
            return {}

        if not isinstance(raw, dict):
            _LOGGER.warning(
                "Invalid model penalties document in %s; using empty state",
                self.storage_path,
            )
            return {}

        meta = raw.get("_meta")
        if isinstance(meta, dict):
            enabled = meta.get("quarantine_enabled", True)
            if not isinstance(enabled, bool):
                enabled = True

            configured = meta.get(
                "configured_max_start_fails",
                self.configured_max_start_fails,
            )
            if (
                isinstance(configured, bool)
                or not isinstance(configured, int)
                or configured < 1
            ):
                configured = self.configured_max_start_fails
            self.configured_max_start_fails = configured

            self.enabled = enabled
            self.max_start_fails = (
                self.configured_max_start_fails
                if self.enabled
                else _DISABLED_MAX_START_FAILS
            )

        state: _State = {}
        invalid_entries = False
        for model_id, entry in raw.items():
            if model_id == "_meta":
                continue
            if not isinstance(model_id, str) or not isinstance(entry, dict):
                invalid_entries = True
                continue

            fails = entry.get("fails", 0)
            until = entry.get("penalized_until", 0.0)
            last_fail = entry.get("last_fail_at", 0.0)
            error = entry.get("last_error")
            if (
                isinstance(fails, bool)
                or not isinstance(fails, int)
                or fails < 0
                or not _is_finite_nonnegative(until)
                or not _is_finite_nonnegative(last_fail)
                or (error is not None and not isinstance(error, str))
            ):
                invalid_entries = True
                continue

            norm_id = model_id.strip().lower()
            if norm_id == "_meta":
                invalid_entries = True
                continue

            trips = entry.get("penalty_trips", 0)
            if (
                isinstance(trips, bool)
                or not isinstance(trips, int)
                or trips < 0
            ):
                trips = 0

            state[norm_id] = {
                "fails": fails,
                "penalized_until": float(until),
                "last_fail_at": float(last_fail),
                "last_error": error,
                "penalty_trips": trips,
            }

        if invalid_entries:
            _LOGGER.warning(
                "Ignored invalid model penalty entries in %s",
                self.storage_path,
            )
        return state

    def _save_state(self) -> None:
        """Atomically replace the JSON file; caller must hold both locks."""
        self._state["_meta"] = {
            "quarantine_enabled": self.enabled,
            "configured_max_start_fails": self.configured_max_start_fails,
        }
        temporary_path: Path | None = None
        try:
            for _ in range(10):
                candidate = self.storage_path.parent / (
                    f".{self.storage_path.name}.{os.getpid()}."
                    f"{threading.get_ident()}.{time.time_ns()}.tmp"
                )
                try:
                    fd = os.open(
                        candidate,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                    )
                except FileExistsError:
                    continue
                temporary_path = candidate
                break
            else:
                raise OSError("Unable to create a unique penalties temp file")

            try:
                stream = os.fdopen(fd, "w", encoding="utf-8")
            except BaseException:
                os.close(fd)
                raise

            with stream:
                json.dump(
                    self._state,
                    stream,
                    ensure_ascii=True,
                    allow_nan=False,
                    sort_keys=True,
                    indent=2,
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())

            os.replace(temporary_path, self.storage_path)
            temporary_path = None
        except (OSError, ValueError, OverflowError, RecursionError) as exc:
            _LOGGER.warning(
                "Cannot persist model penalties to %s: %s",
                self.storage_path,
                exc,
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    _LOGGER.warning(
                        "Cannot remove model penalties temp file %s: %s",
                        temporary_path,
                        exc,
                    )

    def _run(self, operation: Callable[[], tuple[_T, bool]]) -> _T:
        """Reload, execute, and optionally save in one locked transaction."""
        with self._lock:
            lock_fd: int | None = None
            locked = False
            try:
                try:
                    self.storage_path.parent.mkdir(parents=True, exist_ok=True)
                    lock_fd = os.open(
                        self.lock_path, os.O_RDWR | os.O_CREAT, 0o600
                    )
                    fcntl.flock(lock_fd, fcntl.LOCK_EX)
                    locked = True
                except OSError as exc:
                    _LOGGER.warning(
                        "Cannot lock model penalties at %s; "
                        "using in-memory state: %s",
                        self.lock_path,
                        exc,
                    )

                if locked:
                    loaded = self._load_state()
                    if loaded is not None:
                        self._state = loaded

                result, changed = operation()
                if changed and locked:
                    self._save_state()
                return result
            finally:
                if lock_fd is not None:
                    if locked:
                        try:
                            fcntl.flock(lock_fd, fcntl.LOCK_UN)
                        except OSError as exc:
                            _LOGGER.warning(
                                "Cannot unlock model penalties: %s", exc
                            )
                    try:
                        os.close(lock_fd)
                    except OSError as exc:
                        _LOGGER.warning(
                            "Cannot close model penalties lock file: %s", exc
                        )

    @staticmethod
    def _normalize_model_id(model_id: str) -> str:
        norm_id = model_id.strip().lower()
        if norm_id == "_meta":
            raise ValueError("'_meta' is reserved for quarantine metadata")
        return norm_id

    @staticmethod
    def _expire(entry: dict[str, Any], now: float) -> bool:
        until = entry["penalized_until"]
        if until > 0.0 and now >= until:
            entry["fails"] = 0
            entry["penalized_until"] = 0.0
            return True
        return False

    def _status(
        self, model: str, item: dict[str, Any], now: float | None = None
    ) -> dict[str, Any]:
        if now is None:
            now = time.time()
        fails = item["fails"]
        until = item["penalized_until"]
        last_fail = item["last_fail_at"]
        last_error = item["last_error"]
        if not self.enabled:
            is_penalized = False
            remaining_cooldown = 0.0
        else:
            is_penalized = now < until
            remaining_cooldown = max(0.0, until - now)
        return {
            "model": model,
            "fails": fails,
            "is_penalized": is_penalized,
            "remaining_cooldown": remaining_cooldown,
            "penalized_until": until,
            "last_fail_at": last_fail,
            "last_error": last_error,
        }

    def record_start_failure(
        self, model_id: str, error_reason: str = ""
    ) -> tuple[bool, int, float]:
        """Record a failure unless a cooldown is already active."""
        norm_id = self._normalize_model_id(model_id)

        def operation() -> tuple[tuple[bool, int, float], bool]:
            now = time.time()
            entry = self._state.setdefault(norm_id, _empty_entry())

            if now < entry["penalized_until"]:
                return (
                    (True, entry["fails"], entry["penalized_until"]),
                    False,
                )

            strict = flag_enabled("BRIDGE_QUARANTINE_STRICT_CLASSIFY_ENABLED")
            failure_kind = classify_failure(error_reason, strict_classify=strict)
            if not is_penalizing_failure(failure_kind):
                _LOGGER.info(
                    "Skipping model failure penalty for %s (model=%s, kind=%s)",
                    error_reason,
                    norm_id,
                    failure_kind.name,
                )
                return (
                    False,
                    entry["fails"],
                    entry["penalized_until"],
                ), False

            self._expire(entry, now)
            entry["fails"] += 1
            entry["last_fail_at"] = now
            entry["last_error"] = (
                str(error_reason).strip()[:120] if error_reason else None
            )

            threshold_reached = entry["fails"] >= self.max_start_fails
            if threshold_reached:
                trips = int(entry.get("penalty_trips", 0)) + 1
                entry["penalty_trips"] = trips
                if self._has_custom_cooldown:
                    eff_cooldown = self.cooldown_seconds
                elif trips == 1:
                    eff_cooldown = DEFAULT_INITIAL_COOLDOWN_SECONDS
                elif trips == 2:
                    eff_cooldown = DEFAULT_STEP2_COOLDOWN_SECONDS
                elif trips == 3:
                    eff_cooldown = DEFAULT_STEP3_COOLDOWN_SECONDS
                else:
                    eff_cooldown = min(
                        DEFAULT_STEP3_COOLDOWN_SECONDS
                        * (2 ** min(trips - 3, 20)),
                        DEFAULT_MAX_COOLDOWN_SECONDS,
                    )
                until = now + eff_cooldown
                if not _is_finite_nonnegative(until):
                    until = float.fromhex("0x1.fffffffffffffp+1023")
                entry["penalized_until"] = until

            return (
                threshold_reached,
                entry["fails"],
                entry["penalized_until"],
            ), True

        return self._run(operation)

    def record_start_success(self, model_id: str) -> None:
        """Clear failures, error, cooldown, and escalation after success."""
        norm_id = self._normalize_model_id(model_id)

        def operation() -> tuple[None, bool]:
            entry = self._state.get(norm_id)
            if entry is None or (
                entry.get("fails", 0) == 0
                and entry.get("penalized_until", 0.0) == 0.0
                and entry.get("penalty_trips", 0) == 0
                and entry.get("last_error") is None
            ):
                return None, False
            entry["fails"] = 0
            entry["penalized_until"] = 0.0
            entry["penalty_trips"] = 0
            entry["last_error"] = None
            return None, True

        self._run(operation)

    def is_penalized(self, model_id: str) -> tuple[bool, float]:
        """Return effective penalty state, clearing expired penalties."""
        norm_id = self._normalize_model_id(model_id)

        def operation() -> tuple[tuple[bool, float], bool]:
            if not self.enabled:
                return (False, 0.0), False

            now = time.time()
            entry = self._state.get(norm_id)
            if entry is None:
                return (False, 0.0), False
            changed = self._expire(entry, now)
            remaining = max(0.0, entry["penalized_until"] - now)
            return (now < entry["penalized_until"], remaining), changed

        return self._run(operation)

    def get_model_status(self, model_id: str) -> dict[str, Any]:
        """Atomically retrieve the stored model status."""
        norm_id = self._normalize_model_id(model_id)

        def operation() -> tuple[dict[str, Any], bool]:
            now = time.time()
            entry = self._state.get(norm_id)
            if entry is None:
                status = self._status(norm_id, _empty_entry(), now)
                if not self.enabled:
                    status["is_penalized"] = False
                    status["remaining_cooldown"] = 0.0
                    status["remaining_s"] = 0
                    status["remaining_seconds"] = 0
                return status, False
            changed = self._expire(entry, now)
            status = self._status(norm_id, entry, now)
            if not self.enabled:
                status["is_penalized"] = False
                status["remaining_cooldown"] = 0.0
                status["remaining_s"] = 0
                status["remaining_seconds"] = 0
            return status, changed

        return self._run(operation)

    def get_all_penalties(self) -> dict:
        """Return detached statuses keyed by normalized model ID."""
        def operation() -> tuple[dict, bool]:
            now = time.time()
            changed = False
            result = {}
            for model_id, entry in self._state.items():
                if model_id == "_meta":
                    continue
                if self._expire(entry, now):
                    changed = True
                result[model_id] = self._status(model_id, entry, now)
            return result, changed

        return self._run(operation)

    def set_enabled(self, enabled: bool) -> bool:
        """Persist whether quarantine enforcement is enabled."""
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")

        def operation() -> tuple[bool, bool]:
            if not enabled:
                self.enabled = False
                self.max_start_fails = _DISABLED_MAX_START_FAILS
            else:
                self.enabled = True
                self.max_start_fails = self.configured_max_start_fails
            return self.enabled, True

        return self._run(operation)

    def manually_penalize(
        self, model_id: str, duration_s: float = 300.0
    ) -> dict[str, Any]:
        """Apply a manual cooldown without changing escalation history."""
        norm_id = self._normalize_model_id(model_id)
        if not norm_id:
            raise ValueError("model must not be empty")
        if not _is_finite_nonnegative(duration_s):
            raise ValueError("duration_s must be finite and nonnegative")
        duration_s = float(duration_s)

        if not self.enabled:
            self.set_enabled(True)

        def operation() -> tuple[dict[str, Any], bool]:
            now = time.time()
            until = now + duration_s
            if not _is_finite_nonnegative(until):
                raise ValueError("resulting penalty timestamp must be finite")

            if not self.enabled:
                self.enabled = True
                self.max_start_fails = self.configured_max_start_fails

            entry = self._state.setdefault(norm_id, _empty_entry())
            entry["penalized_until"] = until
            entry["fails"] = max(entry.get("fails", 0), 1)
            entry["last_fail_at"] = now
            entry["last_error"] = "manually penalized by user"
            return self._status(norm_id, entry, now), True

        return self._run(operation)

    def unpenalize_model(self, model_id: str) -> None:
        """Clear a model's penalty and failure history."""
        self.record_start_success(model_id)

    def get_quarantine_payload(
        self, all_catalog_models: list[str] | None = None
    ) -> dict[str, Any]:
        """Return quarantine configuration and active stored penalties."""
        def operation() -> tuple[dict[str, Any], bool]:
            now = time.time()
            penalized_models = []
            changed = False
            for model_id, entry in list(self._state.items()):
                if model_id == "_meta":
                    continue
                if self._expire(entry, now):
                    changed = True
                if entry.get("penalized_until", 0.0) > now:
                    penalized_models.append(
                        self._status(model_id, entry, now)
                    )

            return {
                "enabled": self.enabled,
                "max_start_fails": self.max_start_fails,
                "cooldown_seconds": self.cooldown_seconds,
                "penalized_count": len(penalized_models),
                "penalized_models": penalized_models,
                "available_models": all_catalog_models or [],
            }, changed

        return self._run(operation)

    def reset_all(self) -> None:
        """Remove all model states while preserving quarantine configuration."""
        def operation() -> tuple[None, bool]:
            self._state.clear()
            return None, True

        self._run(operation)


_tracker_instance: ModelPenaltyTracker | None = None
_tracker_lock = threading.Lock()


def get_penalty_tracker() -> ModelPenaltyTracker:
    """Return the lazily initialized process-local tracker singleton."""
    global _tracker_instance
    with _tracker_lock:
        if _tracker_instance is None:
            _tracker_instance = ModelPenaltyTracker()
        return _tracker_instance
