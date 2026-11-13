"""Побочные эффекты однократного nonstream retry вокруг чистого FSM."""

from __future__ import annotations

import http.client
import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from core.nonstream_aggregator import NonstreamError
from core.nonstream_retry_fsm import (
    RetryEffectKind,
    RetryEvent,
    RetryEventKind,
    RetryPhase,
    RetryState,
    transition,
)


class RetryWindow(Protocol):
    def expired(self) -> bool: ...


class RetryBulkhead(Protocol):
    def try_acquire(self) -> bool: ...

    def release(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RetryRuntime:
    error: NonstreamError
    window: RetryWindow
    reopen: Callable[[], http.client.HTTPResponse] | None
    deadline: float | None
    poll_interval_s: float
    bulkhead: RetryBulkhead
    read_once: Callable[[http.client.HTTPResponse], bytes]


def retry_incomplete_once(
    runtime: RetryRuntime, *, policy_enabled: bool, request_eligible: bool
) -> bytes | None:
    """Выполняет разрешённый FSM однократный retry или возвращает ``None``."""
    state, effect = _initial_decision(runtime, policy_enabled, request_eligible)
    if effect is not RetryEffectKind.ACQUIRE_SLOT:
        return None
    _require_time(runtime, state, _remaining(runtime.deadline) <= 0)
    acquired = runtime.bulkhead.try_acquire()
    state, effects = transition(
        state,
        RetryEvent(kind=RetryEventKind.SLOT_RESULT, slot_acquired=acquired),
    )
    if effects[0].kind is not RetryEffectKind.CHECK_TIME:
        return None
    held = True
    try:
        remaining = _remaining(runtime.deadline)
        _require_time(runtime, state, remaining <= 0)
        jitter = runtime.poll_interval_s * random.uniform(0.1, 0.5)
        delay = min(jitter, max(0.0, remaining * 0.25))
        if delay > 0:
            runtime.bulkhead.release()
            held = False
            time.sleep(delay)
            if not runtime.bulkhead.try_acquire():
                return None
            held = True
        expired = runtime.deadline is not None and time.monotonic() >= runtime.deadline
        _require_time(runtime, state, expired)
        assert runtime.reopen is not None
        return runtime.read_once(runtime.reopen())
    finally:
        if held:
            runtime.bulkhead.release()


def _initial_decision(
    runtime: RetryRuntime, policy_enabled: bool, request_eligible: bool
) -> tuple[RetryState, RetryEffectKind]:
    state, effects = transition(
        RetryState(),
        RetryEvent(
            kind=RetryEventKind.UPSTREAM_ERROR,
            error_code=runtime.error.code,
            policy_enabled=policy_enabled,
            window_expired=runtime.window.expired(),
            request_eligible=request_eligible,
            reopen_available=runtime.reopen is not None,
        ),
    )
    return state, effects[0].kind


def _remaining(deadline: float | None) -> float:
    return math.inf if deadline is None else deadline - time.monotonic()


def _require_time(
    runtime: RetryRuntime, state: RetryState, deadline_expired: bool
) -> None:
    checking = RetryState(RetryPhase.CHECKING_TIME, state.attempts)
    _, effects = transition(
        checking,
        RetryEvent(
            kind=RetryEventKind.TIME_BUDGET,
            deadline_expired=deadline_expired or runtime.window.expired(),
        ),
    )
    if effects[0].kind is RetryEffectKind.TIMEOUT:
        message = "upstream did not respond in time"
        raise NonstreamError(504, "upstream_timeout", message) from runtime.error
