"""Универсальные паттерны отказоустойчивости шлюза (ADR-0020 Rev 4).

Circuit Breaker с generation tokens, Bulkhead (изоляция параллелизма по `backend_id`) и
RetryPolicy (экспоненциальный бэкофф с Full Jitter и контролем дедлайна). Модуль чистый:
stdlib-only, без знания об адаптерах и именах агентов — ключ изоляции это строка `backend_id`.

Инвариант владельца: автоматического fallback на другую модель/провайдер нет. Недоступный
бэкенд = честный отказ вызывающему (`CircuitBreakerOpen` / `BulkheadCapacityExceeded`),
который фасад превращает в HTTP 503 с `Retry-After`.

Все механизмы закрыты флагами GigaRC (дефолт `false`, снимок + env-override, см.
`ResilienceFlags`); пороги и задержки — только из настроек с безопасными fallback-значениями.
"""

from __future__ import annotations

import enum
import json
import math
import os
import random
import stat
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Protocol

# --------------------------------------------------------------------------- исключения


class ResilienceError(Exception):
    """База отказов слоя отказоустойчивости: запрос отклонён до обращения к бэкенду."""

    error_code = "RESILIENCE_ERROR"
    error_type = "resilience_error"

    def __init__(self, backend_id: str, retry_after: int, message: str = "") -> None:
        self.backend_id = backend_id
        self.retry_after = max(1, int(retry_after))
        self.reason = message
        super().__init__(
            message or f"backend '{backend_id}' is temporarily unavailable"
        )


class CircuitBreakerOpen(ResilienceError):
    """Брейкер бэкенда разомкнут (или проба HALF_OPEN уже занята): fail-fast."""

    error_code = "CIRCUIT_BREAKER_OPEN"

    def __init__(self, backend_id: str, retry_after: int) -> None:
        super().__init__(backend_id, retry_after, "circuit breaker is open")


class BulkheadCapacityExceeded(ResilienceError):
    """Ёмкость отсека бэкенда исчерпана: отказ за O(1), без ожидания слота."""

    error_code = "BULKHEAD_CAPACITY_EXCEEDED"

    def __init__(self, backend_id: str, retry_after: int) -> None:
        super().__init__(backend_id, retry_after, "bulkhead capacity exceeded")


# --------------------------------------------------------------------------- настройки и флаги

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})

FLAG_RESILIENCE = "RESILIENCE_ENABLED"
FLAG_CIRCUIT_BREAKER = "CIRCUIT_BREAKER_ENABLED"
FLAG_BULKHEAD = "BULKHEAD_ENABLED"
FLAG_RETRY = "RETRY_ENABLED"
FLAG_NAMES = (FLAG_RESILIENCE, FLAG_CIRCUIT_BREAKER, FLAG_BULKHEAD, FLAG_RETRY)

ENV_PREFIX = "BRIDGE_"

SNAPSHOT_MAX_BYTES = 64 * 1024


@dataclass(frozen=True)
class ResilienceSettings:
    """Иммутабельный снимок флагов и порогов на время одного запроса.

    `circuit_breaker`/`bulkhead`/`retry` уже учитывают мастер-флаг `enabled`.
    """

    enabled: bool = False
    circuit_breaker: bool = False
    bulkhead: bool = False
    retry: bool = False
    bulkhead_max_concurrent: int = 64
    bulkhead_retry_after_s: int = 1
    fail_threshold: int = 3
    cooldown_s: float = 30.0
    cooldown_jitter: float = 0.2
    retry_max_attempts: int = 3
    retry_base_delay_s: float = 1.0
    retry_max_delay_s: float = 10.0
    retry_backoff_factor: float = 2.0


class FlagSource(Protocol):
    """Источник булевых флагов GigaRC: `{имя: bool}`; отсутствие флага = false."""

    def read(self) -> Mapping[str, bool]: ...


def default_snapshot_path() -> str:
    return os.path.expanduser("~/.config/cli-agent-bridge/resilience.snapshot.json")


def _parse_utc(value: Any) -> float:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp without tz")
    return parsed.astimezone(timezone.utc).timestamp()


@dataclass(frozen=True)
class _Snapshot:
    generated_at: float
    expires_at: float
    flags: Mapping[str, bool]


class SnapshotFlagSource:
    """Читатель локального атомарного JSON-снимка GigaRC: lastgood, default=false, без исключений.

    Снимок: `{"schema_version": 1, "generated_at": ISO, "expires_at": ISO, "flags": {...}}`.
    Любой сбой (нет файла, мусор, чужие права, симлинк) оставляет lastgood, а при его
    отсутствии все флаги false. `true` живёт только пока снимок свеж, `false` — бессрочно.
    """

    def __init__(
        self,
        path: str | None = None,
        *,
        clock: Callable[[], float] = time.time,
        max_true_age_s: float | None = None,
    ) -> None:
        self._path = path or os.environ.get(
            ENV_PREFIX + "RESILIENCE_SNAPSHOT_PATH", default_snapshot_path()
        )
        self._clock = clock
        self._max_true_age_s = (
            max_true_age_s
            if max_true_age_s is not None
            else _env_float(
                os.environ,
                (ENV_PREFIX + "RESILIENCE_SNAPSHOT_MAX_AGE_S",),
                30.0,
                minimum=0.0,
            )
        )
        self._lock = threading.Lock()
        self._sig: tuple[int, int, int, int] | None = None
        self._last: _Snapshot | None = None

    def read(self) -> Mapping[str, bool]:
        with self._lock:
            try:
                fresh = self._load()
            except Exception:  # noqa: BLE001 - гонка/мусор не должны ронять запрос
                fresh = None
            if fresh is not None:
                self._last = fresh
            snap = self._last
            if snap is None:
                return {}
            now = self._clock()
            alive = (
                now < snap.expires_at
                and (now - snap.generated_at) <= self._max_true_age_s
            )
            return {name: value and alive for name, value in snap.flags.items()}

    def _load(self) -> _Snapshot | None:
        euid = os.geteuid()
        st = os.lstat(self._path)
        if not stat.S_ISREG(st.st_mode):
            return None
        sig = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
        if sig == self._sig and self._last is not None:
            return self._last
        parent = os.stat(os.path.dirname(self._path) or ".")
        if parent.st_uid != euid or parent.st_mode & 0o077:
            return None
        fd = os.open(
            self._path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != euid
                or before.st_mode & 0o077
                or before.st_size > SNAPSHOT_MAX_BYTES
            ):
                return None
            raw = os.read(fd, SNAPSHOT_MAX_BYTES + 1)
        finally:
            os.close(fd)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            return None
        flags = data.get("flags")
        if not isinstance(flags, dict):
            return None
        snap = _Snapshot(
            generated_at=_parse_utc(data.get("generated_at")),
            expires_at=_parse_utc(data.get("expires_at")),
            flags={k: v for k, v in flags.items() if isinstance(v, bool)},
        )
        self._sig = sig
        return snap


def _env_bool(env: Mapping[str, str], name: str) -> bool | None:
    raw = env.get(ENV_PREFIX + name)
    if raw is None:
        return None
    text = raw.strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return None


def _env_float(
    env: Mapping[str, str],
    names: Iterable[str],
    default: float,
    *,
    minimum: float = 0.0,
    allow_equal: bool = True,
) -> float:
    """Первое валидное значение из списка имён (основное имя, затем алиасы), иначе default."""
    for name in names:
        raw = env.get(name)
        if raw is None:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if math.isfinite(value) and (
            value >= minimum if allow_equal else value > minimum
        ):
            return value
    return default


def _env_int(
    env: Mapping[str, str], names: Iterable[str], default: int, *, minimum: int = 1
) -> int:
    for name in names:
        raw = env.get(name)
        if raw is None:
            continue
        try:
            value = int(raw.strip())
        except ValueError:
            continue
        if value >= minimum:
            return value
    return default


class ResilienceFlags:
    """Флаги GigaRC (дефолт false) + пороги из env; env перекрывает снимок, снимок — default.

    Булев флаг: `BRIDGE_<ИМЯ>` из env (если задан и валиден) → значение снимка GigaRC →
    `False`. Env `false` — аварийный kill-switch поверх снимка. Мастер-флаг `RESILIENCE_ENABLED`
    должен быть истинным, иначе остальные не действуют. Читается на каждый запрос: смена
    флага вступает в силу без рестарта.
    """

    def __init__(
        self,
        source: FlagSource | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._source: FlagSource = (
            source if source is not None else SnapshotFlagSource()
        )
        self._env = env

    def current(self) -> ResilienceSettings:
        env: Mapping[str, str] = self._env if self._env is not None else os.environ
        try:
            snap = self._source.read()
        except Exception:  # noqa: BLE001 - источник флагов не должен ронять запрос
            snap = {}

        def flag(name: str) -> bool:
            override = _env_bool(env, name)
            return override if override is not None else bool(snap.get(name, False))

        master = flag(FLAG_RESILIENCE)
        if not master:
            return ResilienceSettings()
        p = ENV_PREFIX
        return ResilienceSettings(
            enabled=True,
            circuit_breaker=flag(FLAG_CIRCUIT_BREAKER),
            bulkhead=flag(FLAG_BULKHEAD),
            retry=flag(FLAG_RETRY),
            bulkhead_max_concurrent=_env_int(
                env,
                (
                    p + "BULKHEAD_MAX_CONCURRENT",
                    p + "BULKHEAD_MAX_PASSTHROUGH",
                ),
                64,
            ),
            bulkhead_retry_after_s=_env_int(env, (p + "BULKHEAD_RETRY_AFTER_S",), 1),
            fail_threshold=_env_int(
                env,
                (p + "CIRCUIT_BREAKER_FAIL_THRESHOLD", p + "CB_FAIL_THRESHOLD"),
                3,
            ),
            cooldown_s=_env_float(
                env,
                (p + "CIRCUIT_BREAKER_COOLDOWN_S", p + "CB_RESET_TIMEOUT_S"),
                30.0,
                minimum=0.0,
                allow_equal=False,
            ),
            cooldown_jitter=min(
                _env_float(env, (p + "CIRCUIT_BREAKER_JITTER",), 0.2, minimum=0.0),
                0.9,
            ),
            retry_max_attempts=_env_int(env, (p + "RETRY_MAX_ATTEMPTS",), 3),
            retry_base_delay_s=_env_float(
                env,
                (p + "RETRY_BASE_DELAY_S", p + "RETRY_BASE_SLEEP_S"),
                1.0,
                minimum=0.0,
            ),
            retry_max_delay_s=_env_float(
                env,
                (p + "RETRY_MAX_DELAY_S", p + "RETRY_MAX_SLEEP_S"),
                10.0,
                minimum=0.0,
            ),
            retry_backoff_factor=_env_float(
                env, (p + "RETRY_BACKOFF_FACTOR",), 2.0, minimum=1.0
            ),
        )


# --------------------------------------------------------------------------- Circuit Breaker


class CircuitBreakerState(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Потокобезопасный автомат CLOSED → OPEN → HALF_OPEN с поколениями (generation tokens).

    Каждый переход состояния увеличивает `_generation`. Допущенный вызов получает
    `(allowed, generation, is_probe)`; результат с устаревшим поколением игнорируется,
    поэтому запоздавший ответ старого запроса не портит состояние. В HALF_OPEN допускается
    ровно одна проба; `record_discard` освобождает её слот без фиксации сбоя.
    Переход OPEN → HALF_OPEN ленивый — на первом `acquire` после cooldown.
    """

    def __init__(
        self,
        backend_id: str = "",
        *,
        fail_threshold: int = 3,
        cooldown_s: float = 30.0,
        cooldown_jitter: float = 0.2,
        clock: Callable[[], float] = time.monotonic,
        rng: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self.backend_id = backend_id
        self._lock = threading.Lock()
        self._clock = clock
        self._rng = rng
        self._fail_threshold = max(1, int(fail_threshold))
        self._cooldown_s = float(cooldown_s)
        self._cooldown_jitter = float(cooldown_jitter)
        self._state = CircuitBreakerState.CLOSED
        self._generation = 0
        self._failures = 0
        self._probe_in_flight = False
        self._open_until = 0.0

    def configure(
        self,
        *,
        fail_threshold: int | None = None,
        cooldown_s: float | None = None,
        cooldown_jitter: float | None = None,
    ) -> None:
        """Горячая смена порогов (GigaRC/env) без потери состояния."""
        with self._lock:
            if fail_threshold is not None:
                self._fail_threshold = max(1, int(fail_threshold))
            if cooldown_s is not None:
                self._cooldown_s = float(cooldown_s)
            if cooldown_jitter is not None:
                self._cooldown_jitter = float(cooldown_jitter)

    @property
    def state(self) -> CircuitBreakerState:
        with self._lock:
            return self._state

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def failures(self) -> int:
        with self._lock:
            return self._failures

    @property
    def retry_after(self) -> int:
        """Целые секунды до следующей попытки; 0 — отказ не действует."""
        with self._lock:
            return self._retry_after_locked(self._clock())

    def _retry_after_locked(self, now: float) -> int:
        if self._state is CircuitBreakerState.OPEN:
            remaining = self._open_until - now
            return max(1, math.ceil(remaining)) if remaining > 0 else 0
        if self._state is CircuitBreakerState.HALF_OPEN and self._probe_in_flight:
            return 1
        return 0

    def _transition_locked(self, state: CircuitBreakerState, now: float) -> None:
        self._state = state
        self._generation += 1
        self._failures = 0
        self._probe_in_flight = False
        if state is CircuitBreakerState.OPEN:
            # Джиттер считается один раз при входе в OPEN: Retry-After стабилен.
            spread = self._cooldown_jitter
            self._open_until = now + self._cooldown_s * self._rng(
                1.0 - spread, 1.0 + spread
            )

    def acquire(self) -> tuple[bool, int, bool]:
        """(allowed, generation, is_probe). Отказ — `allowed=False`, вызывать бэкенд нельзя."""
        with self._lock:
            now = self._clock()
            if self._state is CircuitBreakerState.OPEN:
                if now < self._open_until:
                    return False, self._generation, False
                self._transition_locked(CircuitBreakerState.HALF_OPEN, now)
            if self._state is CircuitBreakerState.HALF_OPEN:
                if self._probe_in_flight:
                    return False, self._generation, False
                self._probe_in_flight = True
                return True, self._generation, True
            return True, self._generation, False

    def record_success(self, generation: int) -> None:
        with self._lock:
            if generation != self._generation:
                return
            if self._state is CircuitBreakerState.HALF_OPEN:
                self._transition_locked(CircuitBreakerState.CLOSED, self._clock())
            elif self._state is CircuitBreakerState.CLOSED:
                self._failures = 0

    def record_failure(self, generation: int, exc: BaseException | None = None) -> None:
        with self._lock:
            if generation != self._generation:
                return
            now = self._clock()
            if self._state is CircuitBreakerState.HALF_OPEN:
                self._transition_locked(CircuitBreakerState.OPEN, now)
            elif self._state is CircuitBreakerState.CLOSED:
                self._failures += 1
                if self._failures >= self._fail_threshold:
                    self._transition_locked(CircuitBreakerState.OPEN, now)

    def record_discard(self, generation: int, reason: str = "") -> None:
        """Нейтральный исход (обрыв клиента, 4xx): слот пробы свободен, счётчики не меняются."""
        with self._lock:
            if generation != self._generation:
                return
            if self._state is CircuitBreakerState.HALF_OPEN:
                self._probe_in_flight = False

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state.value,
                "generation": self._generation,
                "failures": self._failures,
                "retry_after": self._retry_after_locked(self._clock()),
            }


# --------------------------------------------------------------------------- Bulkhead


class BulkheadLease:
    """Занятый слот отсека; `close()` идемпотентен."""

    def __init__(self, bulkhead: Bulkhead) -> None:
        self._bulkhead: Bulkhead | None = bulkhead
        self._lock = threading.Lock()

    def close(self) -> None:
        with self._lock:
            bulkhead, self._bulkhead = self._bulkhead, None
        if bulkhead is not None:
            bulkhead._release()


class Bulkhead:
    """Ограничитель параллелизма бэкенда на семафоре; захват неблокирующий (`timeout=0`)."""

    def __init__(self, backend_id: str, capacity: int) -> None:
        self.backend_id = backend_id
        self.capacity = max(1, int(capacity))
        self._sem = threading.BoundedSemaphore(self.capacity)
        self._lock = threading.Lock()
        self._active = 0

    @property
    def active(self) -> int:
        with self._lock:
            return self._active

    def acquire(self, timeout: float = 0) -> BulkheadLease | None:
        if timeout <= 0:
            got = self._sem.acquire(blocking=False)
        else:
            got = self._sem.acquire(timeout=timeout)
        if not got:
            return None
        with self._lock:
            self._active += 1
        return BulkheadLease(self)

    def _release(self) -> None:
        with self._lock:
            self._active -= 1
        self._sem.release()


# --------------------------------------------------------------------------- RetryPolicy


def is_transient_backend_error(exc: BaseException | None) -> bool:
    """Транзиентный технический сбой бэкенда, повтор допустим.

    `None` — вызывающий зафиксировал сбой без исключения (например, upstream 5xx).
    Отказы самого слоя отказоустойчивости повторять нельзя.
    """
    if exc is None:
        return True
    if isinstance(exc, ResilienceError):
        return False
    return isinstance(
        exc,
        (TimeoutError, ConnectionError, InterruptedError, subprocess.SubprocessError),
    )


class RetryPolicy:
    """Повторы с экспоненциальным бэкоффом и Full Jitter (агент-агностичная политика).

    `attempt` — 0-based индекс только что упавшей попытки; всего попыток `max_attempts`.
    Задержка: `uniform(0, min(max_delay, base * factor ** attempt))`. Повтор запрещён, если
    клиенту уже отданы байты ответа (`bytes_delivered`) или исчерпан дедлайн.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_s: float = 1.0,
        max_delay_s: float = 10.0,
        backoff_factor: float = 2.0,
        *,
        rng: Callable[[float, float], float] = random.uniform,
        is_transient: Callable[
            [BaseException | None], bool
        ] = is_transient_backend_error,
    ) -> None:
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay_s = max(0.0, float(base_delay_s))
        self.max_delay_s = max(0.0, float(max_delay_s))
        self.backoff_factor = max(1.0, float(backoff_factor))
        self._rng = rng
        self._is_transient = is_transient

    @classmethod
    def from_settings(cls, settings: ResilienceSettings, **kwargs: Any) -> RetryPolicy:
        return cls(
            settings.retry_max_attempts,
            settings.retry_base_delay_s,
            settings.retry_max_delay_s,
            settings.retry_backoff_factor,
            **kwargs,
        )

    def should_retry(
        self,
        attempt: int,
        bytes_delivered: bool,
        exc: BaseException | None = None,
    ) -> bool:
        if bytes_delivered or attempt + 1 >= self.max_attempts:
            return False
        return self._is_transient(exc)

    def compute_delay(
        self, attempt: int, deadline_s: float | None = None
    ) -> float | None:
        """Секунды сна перед повтором; None — повтор не укладывается в `deadline_s` (остаток).

        Показатель степени ограничен, чтобы `factor ** attempt` не переполнялся.
        """
        if deadline_s is not None and deadline_s <= 0:
            return None
        try:
            ceiling = self.base_delay_s * self.backoff_factor ** max(
                0, min(attempt, 1023)
            )
        except OverflowError:
            ceiling = math.inf
        delay = self._rng(0.0, min(self.max_delay_s, ceiling))
        if deadline_s is not None and delay >= deadline_s:
            return None
        return delay


# --------------------------------------------------------------------------- Lease и Manager


class ResilienceLease:
    """Контекстный менеджер одного запроса: слот Bulkhead + допуск брейкера.

    Результат фиксируется только явно (`record_*`). Выход без исключения успехом не считается;
    выход с необработанным исключением фиксирует сбой. Первый явный исход финален.
    """

    def __init__(
        self,
        backend_id: str,
        breaker: CircuitBreaker | None = None,
        bulkhead_lease: BulkheadLease | None = None,
        generation: int = 0,
        is_probe: bool = False,
    ) -> None:
        self.backend_id = backend_id
        self.generation = generation
        self.is_probe = is_probe
        self._breaker = breaker
        self._bulkhead_lease = bulkhead_lease
        self._recorded = False
        self._lock = threading.Lock()

    def _claim(self) -> bool:
        with self._lock:
            if self._recorded:
                return False
            self._recorded = True
            return True

    @property
    def recorded(self) -> bool:
        return self._recorded

    def record_success(self) -> None:
        if self._claim() and self._breaker is not None:
            self._breaker.record_success(self.generation)

    def record_failure(self, exc: BaseException | None = None) -> None:
        if self._claim() and self._breaker is not None:
            self._breaker.record_failure(self.generation, exc)

    def record_discard(self, reason: str = "") -> None:
        if self._claim() and self._breaker is not None:
            self._breaker.record_discard(self.generation, reason)

    def close(self) -> None:
        with self._lock:
            lease, self._bulkhead_lease = self._bulkhead_lease, None
        if lease is not None:
            lease.close()

    def __enter__(self) -> ResilienceLease:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if exc_val is not None:
                self.record_failure(exc_val)
            elif not self.recorded and self.is_probe:
                # Проба без явного исхода не должна навсегда занять слот HALF_OPEN.
                self.record_discard("no_outcome")
        finally:
            self.close()


class ResilienceManager:
    """Реестр CircuitBreaker и Bulkhead по `backend_id`; настройки читаются на каждый запрос."""

    def __init__(
        self,
        flags: ResilienceFlags | None = None,
        *,
        backend_limits: Mapping[str, int] | None = None,
        clock: Callable[[], float] = time.monotonic,
        rng: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self._flags = flags if flags is not None else ResilienceFlags()
        self._backend_limits = dict(backend_limits or {})
        self._clock = clock
        self._rng = rng
        self._lock = threading.Lock()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._bulkheads: dict[str, Bulkhead] = {}

    def settings(self) -> ResilienceSettings:
        return self._flags.current()

    def retry_policy(self) -> RetryPolicy | None:
        """RetryPolicy по текущим настройкам; None — повторы выключены флагом."""
        settings = self._flags.current()
        if not settings.retry:
            return None
        return RetryPolicy.from_settings(settings)

    def _breaker_for(
        self, backend_id: str, settings: ResilienceSettings
    ) -> CircuitBreaker:
        with self._lock:
            breaker = self._breakers.get(backend_id)
            if breaker is None:
                breaker = CircuitBreaker(
                    backend_id,
                    fail_threshold=settings.fail_threshold,
                    cooldown_s=settings.cooldown_s,
                    cooldown_jitter=settings.cooldown_jitter,
                    clock=self._clock,
                    rng=self._rng,
                )
                self._breakers[backend_id] = breaker
        breaker.configure(
            fail_threshold=settings.fail_threshold,
            cooldown_s=settings.cooldown_s,
            cooldown_jitter=settings.cooldown_jitter,
        )
        return breaker

    def _capacity(self, backend_id: str, settings: ResilienceSettings) -> int:
        cap = settings.bulkhead_max_concurrent
        return max(1, min(self._backend_limits.get(backend_id, cap), cap))

    def _bulkhead_for(self, backend_id: str, settings: ResilienceSettings) -> Bulkhead:
        capacity = self._capacity(backend_id, settings)
        with self._lock:
            bulkhead = self._bulkheads.get(backend_id)
            if bulkhead is None or bulkhead.capacity != capacity:
                # Смена ёмкости: новый отсек; уже выданные слоты освободят старый семафор.
                bulkhead = Bulkhead(backend_id, capacity)
                self._bulkheads[backend_id] = bulkhead
            return bulkhead

    def acquire(self, backend_id: str) -> ResilienceLease:
        """Допуск запроса к бэкенду либо `CircuitBreakerOpen`/`BulkheadCapacityExceeded`."""
        settings = self._flags.current()
        if not settings.enabled or not (settings.circuit_breaker or settings.bulkhead):
            return ResilienceLease(backend_id)
        breaker: CircuitBreaker | None = None
        generation, is_probe = 0, False
        if settings.circuit_breaker:
            breaker = self._breaker_for(backend_id, settings)
            allowed, generation, is_probe = breaker.acquire()
            if not allowed:
                raise CircuitBreakerOpen(backend_id, breaker.retry_after or 1)
        bulkhead_lease: BulkheadLease | None = None
        if settings.bulkhead:
            bulkhead_lease = self._bulkhead_for(backend_id, settings).acquire(timeout=0)
            if bulkhead_lease is None:
                if breaker is not None:
                    # Запрос не дошёл до бэкенда: слот пробы HALF_OPEN возвращаем.
                    breaker.record_discard(generation, "bulkhead_rejected")
                raise BulkheadCapacityExceeded(
                    backend_id, settings.bulkhead_retry_after_s
                )
        return ResilienceLease(
            backend_id, breaker, bulkhead_lease, generation, is_probe
        )

    def snapshot(self, extra_backend_ids: Iterable[str] = ()) -> dict[str, Any]:
        """Состояние всех известных бэкендов для `GET /v1/resilience`."""
        settings = self._flags.current()
        with self._lock:
            breakers = dict(self._breakers)
            bulkheads = dict(self._bulkheads)
        ids = sorted({*breakers, *bulkheads, *extra_backend_ids})
        backends: dict[str, Any] = {}
        for backend_id in ids:
            breaker = breakers.get(backend_id)
            bulkhead = bulkheads.get(backend_id)
            entry: dict[str, Any] = (
                breaker.snapshot()
                if breaker is not None
                else {
                    "state": CircuitBreakerState.CLOSED.value,
                    "generation": 0,
                    "failures": 0,
                    "retry_after": 0,
                }
            )
            entry["active"] = bulkhead.active if bulkhead is not None else 0
            entry["capacity"] = (
                bulkhead.capacity
                if bulkhead is not None
                else self._capacity(backend_id, settings)
            )
            backends[backend_id] = entry
        return {
            "enabled": settings.enabled,
            "flags": {
                "circuit_breaker": settings.circuit_breaker,
                "bulkhead": settings.bulkhead,
                "retry": settings.retry,
            },
            "backends": backends,
        }
