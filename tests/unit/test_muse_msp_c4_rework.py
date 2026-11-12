"""L1: blocking-регрессии Совета c4, F-001..F-005."""

from __future__ import annotations

import pytest

from adapters.muse_msp_final import PhaseState, route_for
from tests.unit.msp_testlib import MAIN, SUB, message, parser


@pytest.mark.parametrize("item", [{}, {"itemId": ""}])
def test_f001_user_message_without_item_id_does_not_anchor(
    item: dict[str, str],
) -> None:
    state = PhaseState()

    route_for(state, "item/started", {**item, "kind": "userMessage", "turnId": MAIN})

    assert state.anchored is False
    assert state.main_turn == ""


def test_f002_unknown_kind_and_explicit_foreign_turn_are_ignored() -> None:
    state = PhaseState(main_turn=MAIN, anchored=True, routes={"unknown": "answer"})

    assert route_for(
        state, "item/started", {"itemId": "unknown", "kind": "status"}
    ) == (
        "unknown",
        "ignore",
    )
    assert route_for(state, "item/delta", {"itemId": "foreign", "turnId": SUB}) == (
        "foreign",
        "ignore",
    )


def test_ignore_untyped_empty_iid_returns_false() -> None:
    state = PhaseState(main_turn=MAIN, anchored=True)
    assert route_for(state, "item/delta", {"kind": "status"}) == ("", "")


def test_early_agent_message_without_item_id_does_not_quarantine_empty() -> None:
    state = PhaseState()
    route_for(state, "item/delta", {"kind": "agentMessage"})
    assert "" not in state.quarantined


def test_f004_colliding_item_id_stays_quarantined() -> None:
    state = PhaseState(main_turn=MAIN, anchored=True)
    main = {
        "itemId": "shared",
        "kind": "agentMessage",
        "turnId": MAIN,
        "messagePhase": "finalAnswer",
    }

    assert route_for(state, "item/started", main) == ("shared", "answer")
    assert route_for(state, "item/completed", {**main, "turnId": SUB}) == (
        "shared",
        "ignore",
    )
    assert route_for(state, "item/completed", main) == ("shared", "ignore")
    assert "shared" in state.quarantined


def test_f005_agent_message_before_anchor_never_reaches_reasoning() -> None:
    events = parser()

    message(events, "early", SUB, "finalAnswer", "FOREIGN")

    assert events.text == ""
    assert events.reasoning == ""
    assert "early" not in events._phase.sub_texts
