"""L1: blocking-регрессии Совета c3, RW-001..RW-007."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from adapters.muse_msp import MAX_TRACKED_ITEMS
from adapters.muse_msp_final import PhaseState, choose_text, route_for
from tests.unit.msp_testlib import (
    MAIN,
    SUB,
    completed,
    delta,
    message,
    parser,
    started,
    tool_completed,
    tool_started,
    user_message,
)


def test_rw001_empty_item_id_is_not_routed_or_anchored() -> None:
    events = parser()
    events.feed(
        "item/completed",
        {"item": {"itemId": "", "kind": "agentMessage", "text": "FOREIGN"}},
    )
    user_message(events)
    message(events, "main", MAIN, "finalAnswer", "MAIN")
    phase = events._phase
    assert "" not in phase.routes
    assert "" not in phase.phases
    assert "" not in phase.sub_texts
    assert "FOREIGN" not in events.text
    assert "FOREIGN" not in events.reasoning
    assert events.text == "MAIN"


def test_rw001_explicit_foreign_turn_rejects_cached_main_route() -> None:
    events = parser()
    user_message(events)
    started(events, "shared", MAIN, "finalAnswer")
    delta(events, "shared", "SAFE")
    completed(events, "shared", SUB, "finalAnswer", "FOREIGN")
    delta(events, "shared", "LEAK")
    events.feed("turn/completed", {"terminal": "completed"})
    assert events.text == "SAFE"
    assert "FOREIGN" not in events.text
    assert "FOREIGN" not in events.reasoning
    assert "LEAK" not in events.text
    assert "LEAK" not in events.reasoning


def test_rw001_explicit_main_turn_discards_cached_subagent_text() -> None:
    events = parser()
    user_message(events)
    started(events, "shared", SUB, "finalAnswer")
    delta(events, "shared", "FOREIGN")
    completed(events, "shared", MAIN, "finalAnswer", "MAIN")
    assert "shared" not in events._phase.sub_texts
    events.feed("turn/completed", {"terminal": "completed"})
    assert events.text == ""
    assert "FOREIGN" not in events.reasoning
    assert "MAIN" not in events.reasoning


def test_rw001_explicit_phase_conflict_is_fail_closed() -> None:
    events = parser()
    user_message(events)
    started(events, "shared", MAIN, "finalAnswer")
    delta(events, "shared", "SAFE")
    completed(events, "shared", MAIN, "commentary", "CONFLICT")
    assert events.text == "SAFE"
    assert "CONFLICT" not in events.text
    assert "CONFLICT" not in events.reasoning


@pytest.mark.parametrize("with_short_delta", [False, True])
def test_rw002_foreign_registry_flood_cannot_evict_main_routes(
    with_short_delta: bool,
) -> None:
    events = parser(reasoning_cap=1 << 20, answer_cap=32)
    user_message(events)
    for index in range(MAX_TRACKED_ITEMS):
        iid = f"foreign-{index}"
        started(events, iid, SUB, "commentary")
        if with_short_delta:
            delta(events, iid, "hidden")
    message(events, "comment", MAIN, "commentary", "STATUS")
    message(events, "final", MAIN, "finalAnswer", "FINAL")
    events.feed("turn/completed", {"terminal": "completed"})
    assert events.text == "FINAL"
    assert "STATUS" not in events.text
    assert "STATUS" in events.reasoning
    assert events.tracked_count <= MAX_TRACKED_ITEMS


class _ExplodingAfterDescription(Mapping[str, Any]):
    def __getitem__(self, key: str) -> Any:
        if key != "description":
            raise AssertionError("allowlist traversal continued after selected hint")
        return "safe"

    def __iter__(self):
        return iter(("description",))

    def __len__(self) -> int:
        return 1


def test_rw003_mapping_value_is_bounded_before_hint_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_MUSE_TOOL_ARGS_MAX_CHARS", "32")
    args = {"description": "x" * 10_000, "path": r"C:\safe\report.md"}
    marker = tool_started(parser(), "t1", "read_file", args)
    assert marker == "[Вызов инструмента: read_file — report.md]\n"


def test_rw003_mapping_value_one_over_limit_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_MUSE_TOOL_ARGS_MAX_CHARS", "4")
    marker = tool_started(parser(), "t1", "bash", {"description": "abcde"})
    assert marker == "[Вызов инструмента: bash]\n"


def test_rw003_stops_after_first_selected_mapping_hint() -> None:
    marker = tool_started(parser(), "t1", "bash", _ExplodingAfterDescription())
    assert marker == "[Вызов инструмента: bash — safe]\n"


def test_rw003_unc_root_does_not_disclose_server_or_share() -> None:
    marker = tool_started(parser(), "t1", "read_file", {"path": r"\\server\share"})
    assert marker == "[Вызов инструмента: read_file]\n"
    assert "server" not in marker
    assert "share" not in marker


def test_rw004_commentary_does_not_spend_answer_cap() -> None:
    events = parser(answer_cap=5)
    user_message(events)
    message(events, "comment", MAIN, "commentary", "12345")
    message(events, "final", MAIN, "finalAnswer", "FINAL")
    assert events.text == "FINAL"
    assert "12345" not in events.text
    assert "12345" in events.reasoning


def test_rw004_content_excludes_non_final_answers_when_final_exists() -> None:
    answers = {"final": ["FINAL"], "commentary": ["STATUS"]}
    phases = {"final": "finalAnswer", "commentary": "commentary"}

    assert choose_text(answers, phases) == "FINAL"


def test_rw005_late_main_commentary_phase_routes_to_reasoning() -> None:
    events = parser()
    user_message(events)
    started(events, "late", MAIN, "")
    delta(events, "late", "STATUS")
    completed(events, "late", MAIN, "commentary", "STATUS")
    assert events.text == ""
    assert events.reasoning == "STATUS"


def test_rw005_late_main_final_phase_routes_to_content() -> None:
    events = parser()
    user_message(events)
    started(events, "late", MAIN, "")
    delta(events, "late", "FINAL")
    completed(events, "late", MAIN, "finalAnswer", "FINAL")
    assert events.text == "FINAL"
    assert events.reasoning == ""


def test_rw005_late_main_final_phase_on_delta_routes_to_content() -> None:
    events = parser()
    user_message(events)
    started(events, "late", MAIN, "")
    events.feed(
        "item/delta",
        {
            "itemId": "late",
            "kind": "agentMessage",
            "turnId": MAIN,
            "messagePhase": "finalAnswer",
            "field": "text",
            "delta": "FINAL",
        },
    )
    events.feed(
        "item/completed",
        {"item": {"itemId": "late", "kind": "agentMessage", "text": "FINAL"}},
    )
    assert events.text == "FINAL"
    assert events.reasoning == ""


def test_rw005_late_subagent_final_phase_routes_once_to_reasoning() -> None:
    events = parser()
    user_message(events)
    started(events, "late", SUB, "")
    delta(events, "late", "SUB")
    completed(events, "late", SUB, "finalAnswer", "SUB")
    assert events.text == ""
    assert events.reasoning == "SUB\n"


def test_rw006_empty_completed_snapshot_keeps_subagent_delta() -> None:
    events = parser()
    user_message(events)
    started(events, "sub", SUB, "finalAnswer")
    delta(events, "sub", "SUB FINAL")
    completed(events, "sub", SUB, "finalAnswer", "")
    assert events.reasoning == "SUB FINAL\n"


def test_rw006_text_snapshot_does_not_duplicate_subagent_delta() -> None:
    events = parser()
    user_message(events)
    started(events, "sub", SUB, "finalAnswer")
    delta(events, "sub", "SUB ")
    delta(events, "sub", "FINAL")
    completed(events, "sub", SUB, "finalAnswer", "SUB FINAL")
    assert events.reasoning == "SUB FINAL\n"


def test_rw006_repeated_completed_does_not_restore_flushed_text() -> None:
    events = parser()
    user_message(events)
    completed(events, "sub", SUB, "finalAnswer", "ONCE")
    completed(events, "sub", SUB, "finalAnswer", "ONCE")
    assert events.reasoning == "ONCE\n"
    assert "sub" not in events._phase.sub_texts


def test_rw007_late_args_keep_exact_legacy_completion_marker() -> None:
    events = parser()
    assert tool_started(events, "tool", "read_file") == (
        "[Вызов инструмента: read_file]\n"
    )
    assert (
        tool_completed(events, "tool", "read_file", {"path": "/tmp/report.md"})
        == "[Инструмент read_file завершён]\n"
    )


def test_rw007_completed_without_tool_keeps_started_name_and_hint() -> None:
    events = parser()
    tool_started(events, "tool", "bash", {"description": "List files"})
    tail = events.feed(
        "item/completed",
        {"item": {"itemId": "tool", "kind": "toolCall", "status": "completed"}},
    )
    assert tail == ""
    assert events.reasoning == "[Вызов инструмента: bash — List files]\n"


def test_rw007_failure_without_kind_uses_stored_tool_display_once() -> None:
    events = parser()
    tool_started(events, "tool", "bash", {"description": "List files"})
    params = {"item": {"itemId": "tool", "status": "failed"}}
    assert events.feed("item/completed", params) == (
        "[Ошибка инструмента: bash — List files]\n"
    )
    assert events.feed("item/completed", params) == ""
    assert events.reasoning.count("Ошибка инструмента: bash — List files") == 1


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
