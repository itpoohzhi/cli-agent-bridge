"""L1: регрессии rework-цикла Совета RW-001..RW-003 для фаз Muse MSP.

RW-004 (дословная форма сырого лога) — tests/unit/test_muse_msp_raw_log.py.
"""

from __future__ import annotations

from adapters.muse_msp import MAX_TRACKED_ITEMS
from adapters.muse_msp_final import PhaseState, flush_chunk, store_sub
from tests.unit.msp_testlib import (
    MAIN,
    SUB,
    completed,
    message,
    parser,
    tool_completed,
    tool_started,
    user_message,
)

# --- RW-001: реестры фаз ограничены MAX_TRACKED_ITEMS -----------------------


def test_phase_tracking_bounded_under_foreign_and_mirror_flood() -> None:
    events = parser(reasoning_cap=4096)
    user_message(events)
    message(events, "f1", MAIN, "finalAnswer", "Главный итог.")
    for index in range(MAX_TRACKED_ITEMS + 6):
        completed(events, f"s{index}", SUB, "finalAnswer", "Чужой финал.")
        completed(events, f"c{index}", MAIN, "commentary", "Статус.")
    events.feed("turn/completed", {"terminal": "completed"})
    phase = events._phase
    assert len(phase.routes) <= MAX_TRACKED_ITEMS
    assert len(phase.phases) <= MAX_TRACKED_ITEMS
    assert len(phase.mirror_indices) <= MAX_TRACKED_ITEMS
    assert len(phase.sub_texts) <= MAX_TRACKED_ITEMS
    assert len(phase.flushed) <= MAX_TRACKED_ITEMS
    assert len(events._mirror_items) <= MAX_TRACKED_ITEMS
    assert events.tracked_count <= MAX_TRACKED_ITEMS
    assert events.text == "Главный итог."


def test_store_sub_stops_growing_at_tracked_limit() -> None:
    state = PhaseState()
    for index in range(MAX_TRACKED_ITEMS + 6):
        store_sub(state, f"s{index}", "текст", False)
    assert len(state.sub_texts) == MAX_TRACKED_ITEMS
    assert f"s{MAX_TRACKED_ITEMS + 5}" not in state.sub_texts
    assert state.sub_texts["s0"] == ["текст"]


def test_flush_releases_stored_subagent_text() -> None:
    state = PhaseState()
    store_sub(state, "s1", "Финал подагента.", False)
    assert flush_chunk(state, "s1", "") == "Финал подагента.\n"
    assert "s1" not in state.sub_texts
    assert flush_chunk(state, "s1", "") == ""


def test_overlong_item_id_is_not_tracked_by_phase_state() -> None:
    events = parser()
    user_message(events)
    overlong = "x" * 257
    completed(events, overlong, SUB, "finalAnswer", "Чужой финал.")
    assert overlong not in events._phase.routes
    assert overlong not in events._phase.sub_texts
    assert "Чужой финал." not in events.reasoning
    assert events.text == ""


# --- RW-002: главный ход якорится только на userMessage ---------------------


def test_first_subagent_event_does_not_anchor_main_turn() -> None:
    events = parser()
    message(events, "s1", SUB, "finalAnswer", "Финал подагента.")
    user_message(events)
    message(events, "f1", MAIN, "finalAnswer", "Финал главного.")
    assert events.text == "Финал главного."
    assert events.reasoning.count("Финал подагента.") == 1


def test_agent_message_without_turn_id_before_anchor_stays_out_of_content() -> None:
    events = parser()
    events.feed(
        "item/completed",
        {
            "item": {
                "itemId": "x1",
                "kind": "agentMessage",
                "messagePhase": "finalAnswer",
                "text": "Финал без turnId.",
            }
        },
    )
    user_message(events)
    message(events, "f1", MAIN, "finalAnswer", "Финал главного.")
    assert events.text == "Финал главного."
    assert "Финал без turnId." in events.reasoning


def test_user_message_without_turn_id_keeps_subagent_out_of_content() -> None:
    events = parser()
    events.feed(
        "item/completed",
        {"item": {"itemId": "u1", "kind": "userMessage", "text": "Вопрос"}},
    )
    message(events, "s1", SUB, "finalAnswer", "Финал подагента.")
    assert "Финал подагента." not in events.text
    assert events.reasoning.count("Финал подагента.") == 1


# --- RW-003: строка неуспеха инструмента не теряется и не дублируется -------


def test_failed_hinted_tool_args_only_on_started() -> None:
    events = parser()
    tool_started(events, "t1", "bash", {"description": "List files"})
    tail = tool_completed(events, "t1", "bash", status="failed")
    assert tail == "[Инструмент bash — List files завершён]\n"
    assert events.reasoning.count("завершён]") == 1


def test_failed_hinted_tool_args_only_on_completed() -> None:
    events = parser()
    tool_started(events, "t1", "bash")
    tail = tool_completed(
        events, "t1", "bash", {"description": "List files"}, status="failed"
    )
    assert tail == "[Инструмент bash — List files завершён]\n"
    assert events.reasoning.count("завершён]") == 1


def test_success_hinted_tool_args_only_on_completed_has_no_line() -> None:
    events = parser()
    tool_started(events, "t1", "bash")
    tail = tool_completed(events, "t1", "bash", {"description": "List files"})
    assert tail == ""
    assert "завершён]" not in events.reasoning


def test_unknown_status_hinted_tool_gets_completed_line() -> None:
    events = parser()
    args = {"description": "List files"}
    tool_started(events, "t1", "bash", args)
    tail = tool_completed(events, "t1", "bash", args, status="melted")
    assert tail == "[Инструмент bash — List files завершён]\n"


def test_non_string_status_hinted_tool_gets_completed_line() -> None:
    events = parser()
    args = {"description": "List files"}
    tool_started(events, "t1", "bash", args)
    tail = events.feed(
        "item/completed",
        {
            "item": {
                "itemId": "t1",
                "kind": "toolCall",
                "tool": "bash",
                "args": args,
                "status": 500,
            }
        },
    )
    assert tail == "[Инструмент bash — List files завершён]\n"


def test_missing_status_hinted_tool_gets_completed_line() -> None:
    events = parser()
    args = {"description": "List files"}
    tool_started(events, "t1", "bash", args)
    tail = events.feed(
        "item/completed",
        {"item": {"itemId": "t1", "kind": "toolCall", "tool": "bash", "args": args}},
    )
    assert tail == "[Инструмент bash — List files завершён]\n"


def test_success_status_hinted_tool_has_no_completed_line() -> None:
    events = parser()
    args = {"description": "List files"}
    tool_started(events, "t1", "bash", args)
    tail = tool_completed(events, "t1", "bash", args, status="success")
    assert tail == ""


def test_repeated_tool_completed_emits_completed_line_once() -> None:
    events = parser()
    args = {"description": "List files"}
    tool_started(events, "t1", "bash", args)
    tool_completed(events, "t1", "bash", args, status="failed")
    tail = tool_completed(events, "t1", "bash", args, status="failed")
    assert tail == ""
    assert events.reasoning.count("[Инструмент bash — List files завершён]\n") == 1
