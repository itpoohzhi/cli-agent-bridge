"""Persistent, process-safe tracking of model startup failures (POSIX)."""

from __future__ import annotations

import fcntl
import logging
import os
from dataclasses import asdict
from pathlib import Path
import threading
import time
from typing import Any, Callable, TypeVar

from core import lease_identity
from core import route_penalty_state as routes
from core.route_penalty_state import LeaseFenced, Phase, State


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
_State = dict[str, Any]
_DISABLED_MAX_START_FAILS = 999999999


def _is_infrastructure_network_error(error_reason: str | None) -> bool:
    """Identify infrastructure failures that must not penalize a model."""
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
    """Единый writer штрафов и lease под стабильным sidecar flock."""

    def __init__(
        self,
        storage_path: Path | str | None = None,
        max_start_fails: int | None = None,
        cooldown_seconds: float | None = None,
    ) -> None:
        self._store = routes.RoutePenaltyState(storage_path)
        self.storage_path = self._store.storage_path
        self.lock_path = self._store.lock_path
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
        try:
            self._run(lambda: (None, False))
        except OSError as exc:
            _LOGGER.warning("Penalty storage unavailable: %s", exc)

    @property
    def ignored_legacy(self) -> int:
        return self._store.ignored_legacy

    def _load_state(self, strict: bool = False) -> _State:
        """Сохраняет неизвестные поля; повреждённый v2 документ не сбрасывает."""
        try:
            raw = self._store._read()
        except (ValueError, UnicodeError, RecursionError):
            if strict:
                raise
            raw = {}
        self._restore_config(raw)
        if strict:
            return raw
        return {key.strip().lower() if not key.startswith("_") else key: value for key, value in raw.items()}

    def _restore_config(self, raw: _State) -> None:
        meta = raw.get("_meta")
        if isinstance(meta, dict):
            enabled = meta.get("quarantine_enabled", True)
            self.enabled = enabled if isinstance(enabled, bool) else True
            configured = meta.get("configured_max_start_fails")
            if type(configured) is int and configured > 0:
                self.configured_max_start_fails = configured
        self.max_start_fails = self.configured_max_start_fails if self.enabled else _DISABLED_MAX_START_FAILS

    def _save_state(self) -> None:
        """Использует общий atomic replace и fsync файла/каталога."""
        meta = self._state.get("_meta", {})
        self._state["_meta"] = dict(
            meta, quarantine_enabled=self.enabled,
            configured_max_start_fails=self.configured_max_start_fails,
        )
        routes._atomic(self.storage_path, self._state)

    def _run(self, operation: Callable[[], tuple[_T, bool]], strict: bool = False) -> _T:
        """Никаких memory-only транзакций при отказе хранилища."""
        with self._lock:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock_path.open("a+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                self._state = self._load_state(strict)
                result, changed = operation()
                if changed:
                    self._save_state()
                return result

    @staticmethod
    def _normalize_model_id(model_id: str) -> str:
        norm_id = model_id.strip().lower()
        if norm_id == "_meta":
            raise ValueError("'_meta' is reserved for quarantine metadata")
        return norm_id

    def _edge(self, model_id: str, backend: str | None = None) -> str:
        return routes.edge_key(self._normalize_model_id(model_id), backend)

    def _entry(self, key: str) -> dict[str, Any]:
        row = self._state.get(key, {})
        return dict(_empty_entry(), **row)

    @staticmethod
    def _unleased(entry: dict[str, Any]) -> None:
        if routes._decode(entry).phase == Phase.HALF_OPEN:
            raise LeaseFenced("HALF_OPEN требует ownership token")

    def _cooldown(self, trips: int) -> float:
        if self._has_custom_cooldown:
            return self.cooldown_seconds
        steps = (DEFAULT_INITIAL_COOLDOWN_SECONDS, DEFAULT_STEP2_COOLDOWN_SECONDS, DEFAULT_STEP3_COOLDOWN_SECONDS)
        if trips <= len(steps):
            return steps[trips - 1]
        return min(DEFAULT_STEP3_COOLDOWN_SECONDS * 2 ** min(trips - 3, 20), DEFAULT_MAX_COOLDOWN_SECONDS)

    def _failure(self, entry: dict[str, Any], error: str, probe: bool = False) -> bool:
        now = time.time()
        self._expire(entry, now)
        entry["fails"] += 1
        entry["last_fail_at"] = now
        entry["last_error"] = str(error).strip()[:120] if error else None
        threshold = probe or entry["fails"] >= self.max_start_fails
        if threshold:
            trips = entry["penalty_trips"] + 1
            entry["penalty_trips"] = trips
            until = now + self._cooldown(trips)
            entry["penalized_until"] = min(until, float.fromhex("0x1.fffffffffffffp+1023"))
        return threshold

    @staticmethod
    def _expire(entry: dict[str, Any], now: float) -> bool:
        until = entry["penalized_until"]
        if entry.get("phase") == Phase.HALF_OPEN:
            return False
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
        if not self.enabled and item.get("phase") != Phase.HALF_OPEN:
            is_penalized = False
            remaining_cooldown = 0.0
        else:
            is_penalized = item.get("phase") == Phase.HALF_OPEN or now < until
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
        self, model_id: str, error_reason: str = "", backend: str | None = None
    ) -> tuple[bool, int, float]:
        """Record a failure unless a cooldown is already active."""
        norm_id = self._edge(model_id, backend)

        def operation() -> tuple[tuple[bool, int, float], bool]:
            now = time.time()
            entry = self._entry(norm_id)
            self._unleased(entry)
            if now < entry["penalized_until"]:
                return (True, entry["fails"], entry["penalized_until"]), False
            if _is_infrastructure_network_error(error_reason):
                return (False, entry["fails"], entry["penalized_until"]), False
            threshold = self._failure(entry, error_reason)
            entry["phase"] = Phase.OPEN if threshold else Phase.CLOSED
            self._state[norm_id] = entry
            return (threshold, entry["fails"], entry["penalized_until"]), True

        return self._run(operation, strict=backend is not None)

    def record_start_success(self, model_id: str, backend: str | None = None) -> None:
        """Clear failures, error, cooldown, and escalation after success."""
        norm_id = self._edge(model_id, backend)

        def operation() -> tuple[None, bool]:
            if norm_id not in self._state:
                return None, False
            entry = self._entry(norm_id)
            self._unleased(entry)
            entry.update(fails=0, penalized_until=0.0, penalty_trips=0, last_error=None, phase=Phase.CLOSED)
            self._state[norm_id] = entry
            return None, True

        self._run(operation, strict=backend is not None)

    def is_penalized(self, model_id: str, backend: str | None = None) -> tuple[bool, float]:
        """Return effective penalty state, clearing expired penalties."""
        norm_id = self._edge(model_id, backend)

        def operation() -> tuple[tuple[bool, float], bool]:
            now = time.time()
            entry = self._entry(norm_id)
            if entry.get("phase") == Phase.HALF_OPEN:
                return (True, max(0.0, entry.get("lease_until", 0) - now)), False
            if not self.enabled:
                return (False, 0.0), False
            changed = self._expire(entry, now)
            if changed:
                self._state[norm_id] = entry
            remaining = max(0.0, entry["penalized_until"] - now)
            return (now < entry["penalized_until"], remaining), changed

        return self._run(operation, strict=backend is not None)

    def get_model_status(self, model_id: str, backend: str | None = None) -> dict[str, Any]:
        """Atomically retrieve the stored model status."""
        norm_id = self._edge(model_id, backend)

        def operation() -> tuple[dict[str, Any], bool]:
            now = time.time()
            entry = self._entry(norm_id)
            changed = self._expire(entry, now)
            if changed:
                self._state[norm_id] = entry
            status = self._status(norm_id, entry, now)
            if not self.enabled and entry.get("phase") != Phase.HALF_OPEN:
                status["is_penalized"] = False
                status["remaining_cooldown"] = 0.0
                status["remaining_s"] = 0
                status["remaining_seconds"] = 0
            return status, changed

        return self._run(operation, strict=backend is not None)

    def get_all_penalties(self) -> dict:
        """Return detached statuses keyed by normalized model ID."""
        def operation() -> tuple[dict, bool]:
            now = time.time()
            changed = False
            result = {}
            for model_id in self._state:
                if model_id.startswith("_"):
                    continue
                entry = self._entry(model_id)
                if self._expire(entry, now):
                    changed = True
                    self._state[model_id] = entry
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
        self, model_id: str, duration_s: float = DEFAULT_MAX_COOLDOWN_SECONDS,
        backend: str | None = None,
    ) -> dict[str, Any]:
        """Apply a manual cooldown without changing escalation history."""
        norm_id = self._edge(model_id, backend)
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

            entry = self._entry(norm_id)
            self._unleased(entry)
            entry["phase"] = Phase.OPEN
            entry["penalized_until"] = until
            entry["fails"] = max(entry.get("fails", 0), 1)
            entry["last_fail_at"] = now
            entry["last_error"] = "manually penalized by user"
            self._state[norm_id] = entry
            return self._status(norm_id, entry, now), True

        return self._run(operation, strict=backend is not None)

    def unpenalize_model(self, model_id: str, backend: str | None = None) -> None:
        """Clear a model's penalty and failure history."""
        self.record_start_success(model_id, backend)

    def get_quarantine_payload(
        self, all_catalog_models: list[str] | None = None
    ) -> dict[str, Any]:
        """Return quarantine configuration and active stored penalties."""
        def operation() -> tuple[dict[str, Any], bool]:
            now = time.time()
            penalized_models = []
            changed = False
            for model_id in list(self._state):
                if model_id.startswith("_"):
                    continue
                entry = self._entry(model_id)
                if self._expire(entry, now):
                    changed = True
                    self._state[model_id] = entry
                if entry.get("phase") == Phase.HALF_OPEN or entry.get("penalized_until", 0.0) > now:
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

    def acquire(self, edge: str, owner: dict[str, Any] | None = None) -> State | None:
        """Host-first выдача или confirmed-DEAD reclaim без локального владения."""
        model, separator, backend = edge.partition("::")
        if edge != self._edge(model, backend if separator else None):
            raise ValueError("Нужен нормализованный ключ ребра")
        if owner is None:
            owner = dict(
                owner_host=lease_identity.host_id(), boot_id=lease_identity.boot_id(),
                owner_pid=os.getpid(), owner_started_at_utc=lease_identity.process_started_at_utc(os.getpid()),
            )
        return self._store.acquire(edge, owner)

    def acquire_lease(self, model_id: str, backend: str, owner: dict[str, Any] | None = None) -> State | None:
        return self.acquire(self._edge(model_id, backend), owner)

    def _owned(self, edge: str, lease: State) -> dict[str, Any]:
        entry = self._entry(edge)
        current = routes._decode(entry)
        if type(lease.lease_epoch) is not int or type(lease.lease_token) is not str:
            raise LeaseFenced("Некорректный тип epoch/token")
        if current.phase != Phase.HALF_OPEN or time.time() >= current.lease_until:
            raise LeaseFenced("Lease отозван или просрочен")
        if (current.lease_epoch, current.lease_token) != (lease.lease_epoch, lease.lease_token):
            raise LeaseFenced("Lease epoch/token не совпадают")
        return entry

    def _lease_run(self, operation: Callable[[], tuple[_T, bool]]) -> _T:
        try:
            return self._run(operation, strict=True)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
            raise LeaseFenced("Ownership не подтверждён хранилищем") from exc

    def owns(self, edge: str, lease_epoch: int, lease_token: str) -> bool:
        def operation() -> tuple[bool, bool]:
            self._owned(edge, State(lease_epoch=lease_epoch, lease_token=lease_token))
            return True, False
        try:
            return self._lease_run(operation)
        except LeaseFenced:
            return False

    def commit(self, edge: str, lease: State, operation: Callable[[], _T]) -> _T:
        """Проверяет token и выполняет локальный commit под тем же flock."""
        def checked() -> tuple[_T, bool]:
            self._owned(edge, lease)
            return operation(), False
        return self._lease_run(checked)

    def _finish(self, edge: str, lease: State, error: str | None) -> State:
        def operation() -> tuple[State, bool]:
            entry = self._owned(edge, lease)
            cooldown = 0.0
            if error is None:
                entry.update(fails=0, penalized_until=0.0, penalty_trips=0, last_error=None)
            else:
                self._failure(entry, error, probe=True)
                cooldown = max(0.0, entry["penalized_until"] - time.time())
            event = routes.Event(
                "success" if error is None else "failure", time.time(),
                cooldown, lease.lease_epoch, lease.lease_token,
            )
            result = routes.step(routes._decode(self._state[edge]), event, self._store.config)
            self._state[edge] = dict(entry, **asdict(result))
            return result, True
        return self._lease_run(operation)

    def record_success(self, edge: str, lease: State) -> State:
        return self._finish(edge, lease, None)

    def record_failure(self, edge: str, lease: State, error_reason: str = "") -> State:
        return self._finish(edge, lease, error_reason)

    def abort(self, edge: str, lease: State) -> State | None:
        """Отмена требует того же непросроченного владельца."""
        def operation() -> tuple[State, bool]:
            entry = self._owned(edge, lease)
            event = routes.Event("abort", time.time(), lease_epoch=lease.lease_epoch, lease_token=lease.lease_token)
            result = routes.step(routes._decode(entry), event, self._store.config)
            self._state[edge] = dict(entry, **asdict(result))
            return result, True
        return self._lease_run(operation)

    def operator_clear_foreign_lease(
        self, request: lease_identity.ClearForeignLeaseRequest,
        context: lease_identity.LeaseMaintenanceContext,
    ) -> int:
        """Переиспользует двухфазный audit и тот же sidecar lock."""
        if context.lease_path.resolve() != self.storage_path.resolve():
            return 1
        if context.lock_path is None or context.lock_path.resolve() != self.lock_path.resolve():
            return 1
        return lease_identity.operator_clear_foreign_lease(request, context)

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
