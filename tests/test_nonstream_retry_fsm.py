from __future__ import annotations

import pytest

from core.nonstream_retry_fsm import (
    RetryEffectKind,
    RetryEvent,
    RetryEventKind,
    RetryPhase,
    RetryState,
    step,
    transition,
)


def test_nonstream_retry_transition_is_pure_and_explicit() -> None:
    initial = RetryState()
    event = RetryEvent(
        kind=RetryEventKind.UPSTREAM_ERROR,
        error_code="upstream_incomplete_stream",
        policy_enabled=True,
        request_eligible=True,
        reopen_available=True,
    )
    first = transition(initial, event)
    second = step(initial, event)

    assert first == second
    assert initial == RetryState()
    assert first[0] == RetryState(RetryPhase.WAITING_SLOT, 0)
    assert [effect.kind for effect in first[1]] == [RetryEffectKind.ACQUIRE_SLOT]


@pytest.mark.parametrize(
    "event",
    [
        RetryEvent(kind=RetryEventKind.UPSTREAM_ERROR),
        RetryEvent(
            kind=RetryEventKind.UPSTREAM_ERROR,
            error_code="upstream_incomplete_stream",
            policy_enabled=True,
            request_eligible=True,
            reopen_available=True,
            window_expired=True,
        ),
    ],
)
def test_nonstream_retry_transition_rejects_ineligible_error(
    event: RetryEvent,
) -> None:
    state, effects = transition(RetryState(), event)
    assert state.phase is RetryPhase.TERMINAL
    assert [effect.kind for effect in effects] == [RetryEffectKind.RERAISE]
