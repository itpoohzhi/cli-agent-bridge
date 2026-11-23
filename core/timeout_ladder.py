"""Чистый домен скользящей лестницы таймаутов стрима (AD-001, L-LIVE/v1).

Полезные чанки (`content` / `reasoning` / `tool_calls`) сдвигают idle-дедлайн
вперёд, транспортные пульсы (`keepalive` / `empty`) — нет; `safety_cap_s` —
абсолютный предохранитель от старта. Модуль не знает о времени сам: часы
передаёт вызывающий (`Callable[[], float]`), конфигурация приходит явным
`Mapping` окружения. При выключенном флаге действуют legacy-значения и
статичный дедлайн первого события (прежнее поведение).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import final

__all__ = [
    "FLAG_TIMEOUT_LADDER",
    "ActivityKind",
    "SlidingActivityPolicy",
    "TimeoutLadderConfig",
    "load_timeout_ladder_config",
    "validate_ladder_monotonicity",
]

FLAG_TIMEOUT_LADDER = "BRIDGE_TIMEOUT_LADDER_ENABLED"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on", "y", "t"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", "n", "f", ""})
_USEFUL_VALUES = frozenset(
    {"content", "reasoning", "tool_calls", "tool_call", "tool_use"}
)


class ActivityKind(str, Enum):
    """Вид активности стрима; полезны только `CONTENT`/`REASONING`/`TOOL_CALLS`."""

    CONTENT = "content"
    REASONING = "reasoning"
    TOOL_CALLS = "tool_calls"
    KEEPALIVE = "keepalive"
    EMPTY = "empty"


@dataclass(frozen=True)
class TimeoutLadderConfig:
    """Иммутабельная лестница таймаутов; все значения — секунды, строго > 0."""

    enabled: bool = False
    connect_timeout_s: float = 10.0
    first_event_timeout_s: float = 600.0
    idle_timeout_s: float = 600.0
    read_chunk_timeout_s: float = 600.0
    safety_cap_s: float = 3600.0
    legacy_first_event_s: float = 300.0
    legacy_idle_s: float = 120.0
    legacy_read_chunk_s: float = 330.0

    def __post_init__(self) -> None:
        self.validate()

    @property
    def effective_first_event_s(self) -> float:
        """Окно до первого полезного чанка: лестница или legacy по флагу."""
        return self.first_event_timeout_s if self.enabled else self.legacy_first_event_s

    @property
    def effective_idle_s(self) -> float:
        """Скользящее idle-окно после полезного чанка: лестница или legacy."""
        return self.idle_timeout_s if self.enabled else self.legacy_idle_s

    @property
    def effective_read_chunk_s(self) -> float:
        """Таймаут чтения одного чанка: лестница или legacy по флагу."""
        return self.read_chunk_timeout_s if self.enabled else self.legacy_read_chunk_s

    def validate(self) -> None:
        """Fail-closed: все окна конечны и положительны, предохранитель не ниже окон."""
        fields = (
            ("connect_timeout_s", self.connect_timeout_s),
            ("first_event_timeout_s", self.first_event_timeout_s),
            ("idle_timeout_s", self.idle_timeout_s),
            ("read_chunk_timeout_s", self.read_chunk_timeout_s),
            ("safety_cap_s", self.safety_cap_s),
            ("legacy_first_event_s", self.legacy_first_event_s),
            ("legacy_idle_s", self.legacy_idle_s),
            ("legacy_read_chunk_s", self.legacy_read_chunk_s),
        )
        for name, value in fields:
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and > 0, got {value!r}")
        horizon = max(value for name, value in fields if name != "safety_cap_s")
        if self.safety_cap_s < horizon:
            raise ValueError(
                f"safety_cap_s ({self.safety_cap_s!r}) below ladder horizon ({horizon!r})"
            )


def _parse_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    """Строгий bool из окружения: неизвестное значение — `ValueError`, не молчаливый дефолт."""
    raw = env.get(key)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"{key} must be a boolean, got {raw!r}")


def _parse_float(env: Mapping[str, str], key: str, default: float) -> float:
    """Float из окружения; нечисло — `ValueError`, диапазоны проверяет `validate`."""
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except ValueError:
        raise ValueError(f"{key} must be a number, got {raw!r}") from None


def load_timeout_ladder_config(env: Mapping[str, str]) -> TimeoutLadderConfig:
    """Собирает конфиг из явного окружения; дефолты берёт из `TimeoutLadderConfig`."""
    defaults = TimeoutLadderConfig()
    return TimeoutLadderConfig(
        enabled=_parse_bool(env, FLAG_TIMEOUT_LADDER, defaults.enabled),
        connect_timeout_s=_parse_float(
            env, "BRIDGE_TIMEOUT_CONNECT_S", defaults.connect_timeout_s
        ),
        first_event_timeout_s=_parse_float(
            env, "BRIDGE_TIMEOUT_FIRST_EVENT_S", defaults.first_event_timeout_s
        ),
        idle_timeout_s=_parse_float(
            env, "BRIDGE_TIMEOUT_IDLE_S", defaults.idle_timeout_s
        ),
        read_chunk_timeout_s=_parse_float(
            env, "BRIDGE_TIMEOUT_READ_CHUNK_S", defaults.read_chunk_timeout_s
        ),
        safety_cap_s=_parse_float(
            env, "BRIDGE_TIMEOUT_SAFETY_CAP_S", defaults.safety_cap_s
        ),
    )


def validate_ladder_monotonicity(
    upper: TimeoutLadderConfig,
    lower: TimeoutLadderConfig,
    margin_s: float = 0.0,
) -> None:
    """Fail-closed: верхняя лестница не ниже нижней (+ `margin_s`) по каждому окну и предохранителю."""
    if not math.isfinite(margin_s) or margin_s < 0.0:
        raise ValueError(f"margin_s must be finite and >= 0, got {margin_s!r}")
    upper.validate()
    lower.validate()
    if upper.connect_timeout_s < lower.connect_timeout_s:
        raise ValueError(
            f"upper connect ({upper.connect_timeout_s!r}) below lower ({lower.connect_timeout_s!r})"
        )
    pairs = (
        ("first_event", upper.effective_first_event_s, lower.effective_first_event_s),
        ("idle", upper.effective_idle_s, lower.effective_idle_s),
        ("read_chunk", upper.effective_read_chunk_s, lower.effective_read_chunk_s),
        ("safety_cap", upper.safety_cap_s, lower.safety_cap_s),
    )
    for name, upper_value, lower_value in pairs:
        if upper_value < lower_value + margin_s:
            message = f"upper {name} ({upper_value!r}) below lower ({lower_value!r})"
            raise ValueError(message + f" + margin ({margin_s!r})")


@final
class SlidingActivityPolicy:
    """Скользящий дедлайн одного стрима: полезная активность продлевает, предохранитель — никогда."""

    def __init__(self, config: TimeoutLadderConfig, clock: Callable[[], float]) -> None:
        config.validate()
        self._config: TimeoutLadderConfig = config
        self._clock: Callable[[], float] = clock
        self._started_at: float = 0.0
        self._deadline: float = 0.0
        self._cap_deadline: float = 0.0
        self._saw_useful: bool = False
        _ = self.start()

    def _now(self) -> float:
        """Текущее время вызывающего; неконечное значение часов — fail-closed."""
        now = float(self._clock())
        if not math.isfinite(now):
            raise ValueError(f"clock returned non-finite time {now!r}")
        return now

    def start(self) -> float:
        """(Пере)стартует окно: дедлайн первого события, но не дальше предохранителя."""
        now = self._now()
        self._started_at = now
        self._cap_deadline = now + self._config.safety_cap_s
        self._deadline = min(
            self._cap_deadline, now + self._config.effective_first_event_s
        )
        self._saw_useful = False
        return self._deadline

    @staticmethod
    def _is_useful(kind: ActivityKind | str) -> bool:
        """Полезны только известные содержательные виды; всё остальное дедлайн не двигает."""
        value = kind.value if isinstance(kind, ActivityKind) else str(kind)
        return value.strip().lower() in _USEFUL_VALUES

    def record(self, kind: ActivityKind | str) -> float:
        """Фиксирует активность и возвращает действующий дедлайн (монотонно, не дальше предохранителя)."""
        now = self._now()
        if self._config.enabled and self._is_useful(kind):
            self._saw_useful = True
            candidate = now + self._config.effective_idle_s
            self._deadline = min(self._cap_deadline, max(self._deadline, candidate))
        return min(self._deadline, self._cap_deadline)

    def is_expired(self) -> bool:
        """Истёк ли ближайший из дедлайнов к текущему времени часов."""
        return self._now() >= min(self._deadline, self._cap_deadline)

    def expiry_reason(self) -> str | None:
        """Причина истечения по самому раннему дедлайну; `None`, пока окно живо."""
        if self._now() < min(self._deadline, self._cap_deadline):
            return None
        if self._cap_deadline <= self._deadline:
            return "safety_cap"
        return "idle_timeout" if self._saw_useful else "first_event_timeout"

    def remaining(self) -> float:
        """Секунд до ближайшего дедлайна; после истечения — ровно `0.0`."""
        return max(0.0, min(self._deadline, self._cap_deadline) - self._now())
