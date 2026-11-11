"""Чистый автомат решения об однократном nonstream retry до первого токена."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "RetryEffect",
    "RetryEffectKind",
    "RetryEvent",
    "RetryEventKind",
    "RetryPhase",
    "RetryState",
    "step",
    "transition",
]


class RetryPhase(Enum):
    IDLE = "idle"
    WAITING_SLOT = "waiting_slot"
    CHECKING_TIME = "checking_time"
    RETRYING = "retrying"
    TERMINAL = "terminal"


class RetryEventKind(Enum):
    UPSTREAM_ERROR = "upstream_error"
    SLOT_RESULT = "slot_result"
    TIME_BUDGET = "time_budget"


class RetryEffectKind(Enum):
    ACQUIRE_SLOT = "acquire_slot"
    CHECK_TIME = "check_time"
    RETRY = "retry"
    RERAISE = "reraise"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class RetryState:
    phase: RetryPhase = RetryPhase.IDLE
    attempts: int = 0


@dataclass(frozen=True, slots=True)
class RetryEvent:
    kind: RetryEventKind
    error_code: str = ""
    policy_enabled: bool = False
    window_expired: bool = False
    request_eligible: bool = False
    reopen_available: bool = False
    slot_acquired: bool = False
    deadline_expired: bool = False


@dataclass(frozen=True, slots=True)
class RetryEffect:
    kind: RetryEffectKind


def _error_allows_retry(event: RetryEvent) -> bool:
    return (
        event.error_code == "upstream_incomplete_stream"
        and event.policy_enabled
        and not event.window_expired
        and event.request_eligible
        and event.reopen_available
    )


def transition(
    state: RetryState, event: RetryEvent
) -> tuple[RetryState, list[RetryEffect]]:
    """Вычисляет новое состояние и декларативный эффект без I/O и часов."""
    if state.phase is RetryPhase.IDLE:
        return _transition_idle(state, event)
    if state.phase is RetryPhase.WAITING_SLOT:
        return _transition_slot(state, event)
    if state.phase is RetryPhase.CHECKING_TIME:
        return _transition_time(state, event)
    return RetryState(RetryPhase.TERMINAL, state.attempts), [
        RetryEffect(RetryEffectKind.RERAISE)
    ]


def _transition_idle(
    state: RetryState, event: RetryEvent
) -> tuple[RetryState, list[RetryEffect]]:
    allowed = event.kind is RetryEventKind.UPSTREAM_ERROR and _error_allows_retry(event)
    phase = RetryPhase.WAITING_SLOT if allowed else RetryPhase.TERMINAL
    effect = RetryEffectKind.ACQUIRE_SLOT if allowed else RetryEffectKind.RERAISE
    return RetryState(phase, state.attempts), [RetryEffect(effect)]


def _transition_slot(
    state: RetryState, event: RetryEvent
) -> tuple[RetryState, list[RetryEffect]]:
    acquired = event.kind is RetryEventKind.SLOT_RESULT and event.slot_acquired
    phase = RetryPhase.CHECKING_TIME if acquired else RetryPhase.TERMINAL
    effect = RetryEffectKind.CHECK_TIME if acquired else RetryEffectKind.RERAISE
    return RetryState(phase, state.attempts), [RetryEffect(effect)]


def _transition_time(
    state: RetryState, event: RetryEvent
) -> tuple[RetryState, list[RetryEffect]]:
    expired = event.kind is not RetryEventKind.TIME_BUDGET or event.deadline_expired
    phase = RetryPhase.TERMINAL if expired else RetryPhase.RETRYING
    effect = RetryEffectKind.TIMEOUT if expired else RetryEffectKind.RETRY
    attempts = state.attempts if expired else state.attempts + 1
    return RetryState(phase, attempts), [RetryEffect(effect)]


def step(state: RetryState, event: RetryEvent) -> tuple[RetryState, list[RetryEffect]]:
    """Каноническое имя шага F-FSM-I1; эквивалентно ``transition``."""
    return transition(state, event)
