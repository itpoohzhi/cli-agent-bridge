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


DEFAULT_MAX_START_FAILS = 3
DEFAULT_INITIAL_COOLDOWN_SECONDS = 10.0
DEFAULT_MAX_COOLDOWN_SECONDS = 300.0
DEFAULT_COOLDOWN_SECONDS = 10.0  # 10s default initial cooldown (adaptive backoff 10s -> 30s -> 120s..300s)
DEFAULT_STORAGE_PATH = Path(
    "~/.config/cli-agent-bridge/model_penalties.json"
).expanduser()

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")
_State = dict[str, dict[str, Any]]


def _is_infrastructure_network_error(error_reason: str | None) -> bool:
    """Return True if error is caused by proxy, bridge socket or gateway issues, not model startup."""
    if not error_reason:
        return False
    lower = str(error_reason).strip().lower()
    return any(
        token in lower
        for token in (
            "http_502",
            "http_504",
            "connection refused",
            "connectionrefused",
            "connect_error",
            "network_error",
            "broken pipe",
            "bad gateway",
            "gateway timeout",
            "connection reset",
            "connectionreset",
            "econnreset",
        )
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
        value if value is not None
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
        value if value is not None
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

    Every operation reloads persisted state while holding the process lock,
    preventing lost updates between cooperating processes. If persistence is
    unavailable, operations continue against the last known in-memory state.
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
        self.max_start_fails = _configured_max_start_fails(max_start_fails)
        self._has_custom_cooldown = (
            cooldown_seconds is not None
            or bool(os.environ.get("BRIDGE_COOLDOWN_SECONDS", "").strip())
        )
        self.cooldown_seconds = _configured_cooldown(cooldown_seconds)
        self._lock = threading.Lock()
        self._state: _State = {}
        self._run(lambda: (None, False))

    def _load_state(self) -> _State | None:
        """Return None on I/O errors so a live in-memory state is preserved."""
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

        state: _State = {}
        invalid_entries = False
        for model_id, entry in raw.items():
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

            trips = entry.get("penalty_trips", 0)
            if not isinstance(trips, int) or trips < 0:
                trips = 0
            state[model_id.strip().lower()] = {
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
        temporary_path: Path | None = None
        try:
            # O_EXCL prevents collisions and avoids following existing symlinks.
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
        """Reload, execute, and optionally save within one locked transaction."""
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
    def _expire(entry: dict[str, Any], now: float) -> bool:
        until = entry["penalized_until"]
        if until > 0.0 and now >= until:
            entry["fails"] = 0
            entry["penalized_until"] = 0.0
            return True
        return False

    @staticmethod
    def _status(
        model_id: str, entry: dict[str, Any], now: float
    ) -> dict[str, Any]:
        until = entry["penalized_until"]
        return {
            "model": model_id,
            "fails": entry["fails"],
            "is_penalized": now < until,
            "remaining_cooldown": max(0.0, until - now),
            "penalized_until": until,
            "last_fail_at": entry["last_fail_at"],
            "last_error": entry["last_error"],
        }

    def record_start_failure(
        self, model_id: str, error_reason: str = ""
    ) -> tuple[bool, int, float]:
        """Record a failure unless a cooldown is already active.

        Calls during cooldown leave all entry fields unchanged and do not
        rewrite persisted state. Expired penalties are cleared before counting
        a new failure.
        """
        norm_id = model_id.strip().lower()

        def operation() -> tuple[tuple[bool, int, float], bool]:
            now = time.time()
            entry = self._state.setdefault(norm_id, _empty_entry())

            # Check within the locked transaction so concurrent calls cannot
            # increase the failure count or extend an active cooldown.
            if now < entry["penalized_until"]:
                return (
                    (True, entry["fails"], entry["penalized_until"]),
                    False,
                )

            # Do not penalize models for infrastructure or network proxy errors (502, connection refused).
            if _is_infrastructure_network_error(error_reason):
                _LOGGER.info(
                    "Skipping model failure penalty for infrastructure/network error: %s (model=%s)",
                    error_reason,
                    norm_id,
                )
                return (False, entry["fails"], entry["penalized_until"]), False

            self._expire(entry, now)
            entry["fails"] += 1
            entry["last_fail_at"] = now
            entry["last_error"] = str(error_reason).strip()[:120] if error_reason else None

            threshold_reached = entry["fails"] >= self.max_start_fails
            if threshold_reached:
                trips = int(entry.get("penalty_trips", 0)) + 1
                entry["penalty_trips"] = trips
                if self._has_custom_cooldown:
                    eff_cooldown = self.cooldown_seconds
                else:
                    if trips == 1:
                        eff_cooldown = 10.0
                    elif trips == 2:
                        eff_cooldown = 30.0
                    elif trips == 3:
                        eff_cooldown = 120.0
                    else:
                        eff_cooldown = min(120.0 * (2 ** min(trips - 3, 20)), DEFAULT_MAX_COOLDOWN_SECONDS)
                until = now + eff_cooldown
                if not _is_finite_nonnegative(until):
                    until = float.fromhex("0x1.fffffffffffffp+1023")
                entry["penalized_until"] = until

            return (
                (
                    threshold_reached,
                    entry["fails"],
                    entry["penalized_until"],
                ),
                True,
            )

        return self._run(operation)

    def record_start_success(self, model_id: str) -> None:
        """Clear the failure count, error, and cooldown after a successful start.

        If the model is already in the default zero-failure state, this operation
        is a no-op that avoids modifying or fsyncing persisted state.
        """
        norm_id = model_id.strip().lower()

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
        """Return penalty state and remaining seconds, clearing expired penalties."""
        norm_id = model_id.strip().lower()

        def operation() -> tuple[tuple[bool, float], bool]:
            now = time.time()
            entry = self._state.get(norm_id)
            if entry is None:
                return (False, 0.0), False
            changed = self._expire(entry, now)
            remaining = max(0.0, entry["penalized_until"] - now)
            return (now < entry["penalized_until"], remaining), changed

        return self._run(operation)

    def get_model_status(self, model_id: str) -> dict[str, Any]:
        """Atomically retrieve status snapshot under a single locked transaction."""
        norm_id = model_id.strip().lower()

        def operation() -> tuple[dict[str, Any], bool]:
            now = time.time()
            entry = self._state.get(norm_id)
            if entry is None:
                return {
                    "model": norm_id,
                    "fails": 0,
                    "is_penalized": False,
                    "remaining_cooldown": 0.0,
                    "penalized_until": 0.0,
                    "last_fail_at": 0.0,
                    "last_error": None,
                }, False
            changed = self._expire(entry, now)
            return self._status(norm_id, entry, now), changed

        return self._run(operation)

    def get_all_penalties(self) -> dict:
        """Return detached statuses keyed by normalized model ID."""
        def operation() -> tuple[dict, bool]:
            now = time.time()
            changed = False
            result = {}
            for model_id, entry in self._state.items():
                if self._expire(entry, now):
                    changed = True
                result[model_id] = self._status(model_id, entry, now)
            return result, changed

        return self._run(operation)

    def reset_all(self) -> None:
        """Remove all model states and persist the empty state."""
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