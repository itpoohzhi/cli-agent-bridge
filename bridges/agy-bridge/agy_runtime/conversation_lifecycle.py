"""Чистый автомат и единые пределы жизненного цикла беседы agy."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

__all__ = (
    "ConversationEvent",
    "ConversationLifecycle",
    "ConversationState",
    "LifecycleEvent",
    "LifecyclePolicy",
    "LifecycleState",
    "is_conversation_expired",
)


class LifecycleState(StrEnum):
    """Состояние сохранённой беседы без привязки к её хранилищу."""

    NONE = "none"
    ACTIVE = "active"
    EXPIRED = "expired"
    TOMBSTONED = "tombstoned"


class LifecycleEvent(StrEnum):
    """Событие, которое может изменить состояние беседы."""

    COLD_REQUEST = "cold_request"
    DELTA_COMMITTED = "delta_committed"
    MAX_TURNS = "max_turns"
    IDLE_TTL = "idle_ttl"
    MAX_TTL = "max_ttl"
    TOMBSTONE = "tombstone"
    CONTINUITY_MISS = "continuity_miss"
    RESTART = "restart"
    TEXT_ONLY_FALLBACK = "text_only_fallback"


# Более явные алиасы для потребителей, которые называют автомат по предметной области.
ConversationState = LifecycleState
ConversationEvent = LifecycleEvent


@dataclass(frozen=True, slots=True)
class LifecyclePolicy:
    """Единые ограничения беседы, разрешаемые адаптером один раз на запрос."""

    max_turns: int = 30
    idle_ttl_s: float = 2700.0
    max_ttl_s: float = 86400.0

    def __post_init__(self) -> None:
        """Отклонить значения, которые делают expiry неопределённым или вечным."""
        if type(self.max_turns) is not int or self.max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        _validate_ttl("idle_ttl_s", self.idle_ttl_s)
        _validate_ttl("max_ttl_s", self.max_ttl_s)


_EXPIRY_EVENTS: Final = frozenset(
    {LifecycleEvent.MAX_TURNS, LifecycleEvent.IDLE_TTL, LifecycleEvent.MAX_TTL}
)
_RESET_EVENTS: Final = frozenset(
    {LifecycleEvent.RESTART, LifecycleEvent.TEXT_ONLY_FALLBACK}
)


def _validate_ttl(name: str, value: float) -> None:
    """Проверить конечный положительный TTL без чтения конфигурации или часов."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite positive number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")


class ConversationLifecycle:
    """Тотальный чистый переход между состояниями жизненного цикла беседы."""

    State = LifecycleState
    Event = LifecycleEvent

    @staticmethod
    def transition(state: LifecycleState, event: LifecycleEvent) -> LifecycleState:
        """Вернуть следующее состояние для каждой допустимой пары state × event.

        Холодный запрос создаёт новую активную беседу. Истечение и потеря
        continuity не воскрешаются commit-ом; restart и text-only fallback
        отвязывают старый conversation_id до следующего холодного запроса.
        """
        if event is LifecycleEvent.COLD_REQUEST:
            return LifecycleState.ACTIVE
        if event is LifecycleEvent.TOMBSTONE:
            return LifecycleState.TOMBSTONED
        if event in _RESET_EVENTS:
            return LifecycleState.NONE
        if state is not LifecycleState.ACTIVE:
            return state
        if event in _EXPIRY_EVENTS or event is LifecycleEvent.CONTINUITY_MISS:
            return LifecycleState.EXPIRED
        return LifecycleState.ACTIVE


def is_conversation_expired(
    created_s: float,
    last_used_s: float,
    turns: int,
    now_s: float,
    policy: LifecyclePolicy = LifecyclePolicy(),
) -> bool:
    """Проверить expiry с теми же строгими TTL-границами, что и legacy store.

    TTL истекает только при ``elapsed > ttl``; предел числа ходов достигается
    при ``turns >= max_turns``. Часы и хранилище остаются в effect-shell.
    """
    return (
        now_s - last_used_s > policy.idle_ttl_s
        or now_s - created_s > policy.max_ttl_s
        or turns >= policy.max_turns
    )
