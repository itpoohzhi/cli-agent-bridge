"""Чистый HALF_OPEN-автомат и долговечный sidecar-flock store рёбер."""
from __future__ import annotations

import fcntl
import json
import math
import os
import tempfile
import time
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from core import lease_identity
class LeaseFenced(RuntimeError):
    """Токен отозван, устарел либо принадлежит другому владельцу."""

def _bounded(value: object, default: float, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return default
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return default
    return number if math.isfinite(number) and low <= number <= high else default

@dataclass(frozen=True, slots=True)
class LeaseConfig:
    lease_ttl_s: float = 60
    clock_skew_tolerance_s: float = 5
    def __post_init__(self) -> None:
        object.__setattr__(self, "lease_ttl_s", _bounded(self.lease_ttl_s, 60, 5, 600))
        object.__setattr__(self, "clock_skew_tolerance_s", _bounded(self.clock_skew_tolerance_s, 5, 0, 60))
    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> LeaseConfig:
        """Читает одинаковые ключи из окружения или файла конфигурации."""
        return cls(config.get("BRIDGE_HALF_OPEN_LEASE_TTL_S", 60), config.get("CLOCK_SKEW_TOLERANCE_S", 5))

class Phase(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class Liveness(StrEnum):
    ALIVE = "ALIVE"
    UNKNOWN = "UNKNOWN"
    DEAD = "DEAD"

@dataclass(frozen=True, slots=True)
class State:
    phase: Phase = Phase.CLOSED
    penalized_until: float = 0
    lease_until: float = 0
    lease_epoch: int = 0
    lease_token: str = ""

@dataclass(frozen=True, slots=True)
class Event:
    action: str
    now: float
    cooldown_s: float = 0
    lease_epoch: int = 0
    lease_token: str = ""
    liveness: Liveness = Liveness.UNKNOWN

def _number(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False

def _acquire(state: State, event: Event, config: LeaseConfig) -> State:
    if state.phase == Phase.OPEN and event.now < state.penalized_until:
        return state
    if state.phase == Phase.HALF_OPEN:
        if event.liveness != Liveness.DEAD or event.now < state.lease_until + config.clock_skew_tolerance_s:
            return state
    if not event.lease_token or event.lease_token == state.lease_token:
        raise ValueError("Для нового lease нужен новый токен")
    return replace(state, phase=Phase.HALF_OPEN, lease_until=event.now + config.lease_ttl_s,
                   lease_epoch=state.lease_epoch + 1, lease_token=event.lease_token)

def _fence(state: State, event: Event) -> None:
    if state.phase == Phase.HALF_OPEN or event.lease_token or event.action == "abort":
        if state.phase != Phase.HALF_OPEN or (event.lease_epoch, event.lease_token) != (state.lease_epoch, state.lease_token):
            raise LeaseFenced("Lease больше не принадлежит вызывающему")
def step(state: State, event: Event, config: LeaseConfig = LeaseConfig()) -> State:
    """Переход без часов, окружения, генерации токенов и проверки процессов."""
    if not all(_number(v) for v in (event.now, event.cooldown_s)):
        raise ValueError("Нужны конечные неотрицательные UTC seconds")
    if not all(_number(event.now + v) for v in (event.cooldown_s, config.lease_ttl_s)):
        raise ValueError("Переполнение UTC seconds")
    if event.action == "inspect":
        return state
    if event.action == "acquire":
        return _acquire(state, event, config)
    if event.action not in ("abort", "success", "failure"):
        raise ValueError("Неизвестное событие")
    _fence(state, event)
    if event.action == "abort":
        return replace(state, phase=Phase.OPEN, lease_until=0, lease_token="")
    until = event.now + event.cooldown_s if event.action == "failure" else 0
    phase = {"failure": Phase.OPEN, "success": Phase.CLOSED}[event.action]
    return replace(state, phase=phase, penalized_until=until, lease_until=0, lease_token="")
def edge_key(model: str, backend: str | None) -> str:
    """Model-only ключи никогда не проецируются на backend-specific ребро."""
    parts = [model] if backend is None else [model, backend]
    if any(not part.strip() or "::" in part for part in parts):
        raise ValueError("Пустой или неоднозначный ключ ребра")
    return "::".join(part.strip().lower() for part in parts)
def _decode(row: dict[str, Any]) -> State:
    until = row.get("penalized_until", 0)
    phase = row.get("phase", Phase.OPEN if until else Phase.CLOSED)
    state = State(Phase(phase), until, row.get("lease_until", 0), row.get("lease_epoch", 0), row.get("lease_token", ""))
    if not all(_number(v) for v in (state.penalized_until, state.lease_until, state.lease_epoch)):
        raise ValueError("Некорректные метки lease")
    if type(state.lease_epoch) is not int or not isinstance(state.lease_token, str):
        raise ValueError("Некорректный fencing")
    if state.phase == Phase.HALF_OPEN and not state.lease_token:
        raise ValueError("HALF_OPEN без токена")
    return state
def _atomic(path: Path, document: dict[str, Any]) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(document, stream, ensure_ascii=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
class RoutePenaltyState:
    """Каждая операция читает диск под flock; memory-only ownership отсутствует."""
    def __init__(self, storage_path: Path | str | None = None, config: LeaseConfig | None = None) -> None:
        self.storage_path = Path(storage_path or os.environ.get("BRIDGE_MODEL_PENALTIES_PATH", "~/.config/cli-agent-bridge/model_penalties.json")).expanduser()
        self.lock_path = self.storage_path.with_suffix(".json.lock")
        self.config = config or LeaseConfig.from_mapping(os.environ)
        self.ignored_legacy = 0

    def _read(self) -> dict[str, Any]:
        try:
            document = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            document = {}
        if not isinstance(document, dict):
            raise ValueError("Хранилище не является объектом")
        self.ignored_legacy = sum(not k.startswith("_") and "::" not in k for k in document)
        return document

    def _transition(self, row: dict[str, Any], event: Event) -> State:
        state = _decode(row)
        if event.action == "acquire" and state.phase == Phase.HALF_OPEN:
            protected = lease_identity.is_alive_or_unknown(row, lease_identity.host_id(), lease_identity.boot_id())
            event = replace(event, liveness=Liveness.UNKNOWN if protected else Liveness.DEAD)
        return step(state, event, self.config)

    def _run(self, edge: str, event: Event, owner: Mapping[str, Any] | None = None) -> State | None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock_path.open("a+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                document = self._read()
                row = document.get(edge, {})
                before = _decode(row)
                after = self._transition(row, event)
                if event.action == "acquire" and after == before:
                    return None
                if after != before:
                    document[edge] = dict(row, **asdict(after))
                    if owner is not None:
                        document[edge].update({key: owner[key] for key in lease_identity.FIELDS[:4]})
                    _atomic(self.storage_path, document)
                return after
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
            return None

    def acquire(self, edge: str, owner: Mapping[str, Any]) -> State | None:
        """Выдаёт токен только после долговечной записи; чужую жизнь не угадывает."""
        if not isinstance(owner.get("owner_host"), str) or not owner["owner_host"].strip():
            return None
        if not all(type(owner.get(k)) is int for k in lease_identity.FIELDS[1:4]) or owner["owner_pid"] <= 0:
            return None
        return self._run(edge, Event("acquire", time.time(), lease_token=uuid.uuid4().hex), owner)

    def owns(self, edge: str, lease_epoch: int, lease_token: str) -> bool:
        state = self._run(edge, Event("inspect", time.time()))
        return state is not None and state.phase == Phase.HALF_OPEN and (state.lease_epoch, state.lease_token) == (lease_epoch, lease_token)

    def abort(self, edge: str, lease_epoch: int, lease_token: str) -> State | None:
        """Возвращает прежний OPEN с исходным дедлайном без нового штрафа."""
        return self._run(edge, Event("abort", time.time(), lease_epoch=lease_epoch, lease_token=lease_token))
    def finish(self, edge: str, lease: State, cooldown_s: float | None = None) -> State | None:
        """Фиксирует результат пробы только с актуальной парой epoch/token."""
        action = "success" if cooldown_s is None else "failure"
        return self._run(edge, Event(action, time.time(), cooldown_s or 0, lease.lease_epoch, lease.lease_token))
    def is_penalized(self, model: str, backend: str | None = None) -> tuple[bool, float]:
        now = time.time()
        state = self._run(edge_key(model, backend), Event("inspect", now))
        if state is None:
            return True, self.config.lease_ttl_s
        return state.phase == Phase.HALF_OPEN or now < state.penalized_until, max(0.0, state.penalized_until - now)

    def record_start_failure(self, model: str, error_reason: str = "", backend: str | None = None) -> State | None:
        """Открывает ребро; длительность задаётся конфигурацией, не именем агента."""
        return self._run(edge_key(model, backend), Event("failure", time.time(), self.config.lease_ttl_s))

    def record_start_success(self, model: str, backend: str | None = None) -> State | None:
        """Закрывает ребро без активного lease; HALF_OPEN требует fencing."""
        return self._run(edge_key(model, backend), Event("success", time.time()))
