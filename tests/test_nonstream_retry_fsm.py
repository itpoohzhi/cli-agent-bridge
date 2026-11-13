from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

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
    assert tuple(effect.kind for effect in first[1]) == (RetryEffectKind.ACQUIRE_SLOT,)
    with pytest.raises(FrozenInstanceError):
        initial.attempts = 1  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    "changes",
    [
        {"error_code": "other"},
        {"policy_enabled": False},
        {"window_expired": True},
        {"request_eligible": False},
        {"reopen_available": False},
    ],
)
def test_nonstream_retry_transition_rejects_each_ineligible_error(
    changes: dict[str, object],
) -> None:
    fields: dict[str, object] = {
        "kind": RetryEventKind.UPSTREAM_ERROR,
        "error_code": "upstream_incomplete_stream",
        "policy_enabled": True,
        "request_eligible": True,
        "reopen_available": True,
    }
    fields.update(changes)
    event = RetryEvent(**fields)  # type: ignore[arg-type]
    state, effects = transition(RetryState(), event)
    assert state.phase is RetryPhase.TERMINAL
    assert tuple(effect.kind for effect in effects) == (RetryEffectKind.RERAISE,)


@pytest.mark.parametrize(
    ("state", "event", "expected_state", "expected_effect"),
    [
        (
            RetryState(RetryPhase.WAITING_SLOT),
            RetryEvent(RetryEventKind.SLOT_RESULT, slot_acquired=True),
            RetryState(RetryPhase.CHECKING_TIME),
            RetryEffectKind.CHECK_TIME,
        ),
        (
            RetryState(RetryPhase.WAITING_SLOT),
            RetryEvent(RetryEventKind.SLOT_RESULT),
            RetryState(RetryPhase.TERMINAL),
            RetryEffectKind.RERAISE,
        ),
        (
            RetryState(RetryPhase.WAITING_SLOT),
            RetryEvent(RetryEventKind.TIME_BUDGET, slot_acquired=True),
            RetryState(RetryPhase.TERMINAL),
            RetryEffectKind.RERAISE,
        ),
        (
            RetryState(RetryPhase.CHECKING_TIME),
            RetryEvent(RetryEventKind.TIME_BUDGET),
            RetryState(RetryPhase.RETRYING, 1),
            RetryEffectKind.RETRY,
        ),
        (
            RetryState(RetryPhase.CHECKING_TIME),
            RetryEvent(RetryEventKind.TIME_BUDGET, deadline_expired=True),
            RetryState(RetryPhase.TERMINAL),
            RetryEffectKind.TIMEOUT,
        ),
        (
            RetryState(RetryPhase.CHECKING_TIME),
            RetryEvent(RetryEventKind.SLOT_RESULT),
            RetryState(RetryPhase.TERMINAL),
            RetryEffectKind.TIMEOUT,
        ),
        (
            RetryState(RetryPhase.RETRYING, 1),
            RetryEvent(RetryEventKind.TIME_BUDGET),
            RetryState(RetryPhase.TERMINAL, 1),
            RetryEffectKind.RERAISE,
        ),
    ],
)
def test_nonstream_retry_transition_table(
    state: RetryState,
    event: RetryEvent,
    expected_state: RetryState,
    expected_effect: RetryEffectKind,
) -> None:
    original = (state, event)
    actual_state, effects = step(state, event)
    assert actual_state == expected_state
    assert tuple(effect.kind for effect in effects) == (expected_effect,)
    assert (state, event) == original
