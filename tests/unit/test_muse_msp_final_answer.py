"""L1: фазы agentMessage Muse MSP — в content только финальный ответ главного хода."""

from __future__ import annotations

import pytest

from adapters.muse_msp_final import PhaseState, mirror_index_for
from tests.unit.msp_testlib import (
    MAIN,
    SUB,
    completed,
    delta,
    message,
    parser,
    started,
    tool_started,
    user_message,
)

# --- AC1: в content только finalAnswer главного хода -------------------------


def test_text_contains_only_main_final_answers() -> None:
    events = parser()
    user_message(events)
    message(events, "c1", MAIN, "commentary", "Начинаю работу.")
    message(events, "f1", MAIN, "finalAnswer", "Итог один.")
    message(events, "f2", MAIN, "finalAnswer", "Итог два.")
    assert events.text == "Итог один.\n\nИтог два."


def test_text_excludes_subagent_messages() -> None:
    events = parser()
    user_message(events)
    message(events, "s1", SUB, "commentary", "Чужой статус.")
    message(events, "s2", SUB, "finalAnswer", "Чужой финал.")
    message(events, "f1", MAIN, "finalAnswer", "Главный итог.")
    assert events.text == "Главный итог."


def test_main_turn_comes_from_user_message_not_first_agent_message() -> None:
    events = parser()
    user_message(events)
    # Первым agentMessage приходит сообщение подагента — главным ходом не становится.
    message(events, "s1", SUB, "finalAnswer", "Финал подагента.")
    message(events, "f1", MAIN, "finalAnswer", "Финал главного.")
    assert events.text == "Финал главного."


def test_preanchor_phaseless_messages_are_fail_closed() -> None:
    events = parser()
    events.feed(
        "item/completed",
        {"item": {"itemId": "a", "kind": "agentMessage", "text": "Первая часть."}},
    )
    events.feed(
        "item/completed",
        {"item": {"itemId": "b", "kind": "agentMessage", "text": "Вторая часть."}},
    )
    assert events.text == ""
    assert events.reasoning == ""


def test_text_never_falls_back_to_commentary() -> None:
    events = parser()
    user_message(events)
    message(events, "c1", MAIN, "commentary", "Только статус.")
    assert events.text == ""
    assert events.reasoning == "Только статус."


def test_empty_final_does_not_hide_fallback() -> None:
    events = parser()
    user_message(events)
    message(events, "f1", MAIN, "finalAnswer", "")
    events.feed(
        "item/completed",
        {
            "item": {
                "itemId": "a",
                "kind": "agentMessage",
                "turnId": MAIN,
                "text": "Содержимое.",
            }
        },
    )
    assert events.text == "Содержимое."


def test_unknown_message_without_turn_id_after_anchor_is_ignored() -> None:
    events = parser()
    user_message(events)
    events.feed(
        "item/completed",
        {"item": {"itemId": "a", "kind": "agentMessage", "text": "Без turnId."}},
    )
    assert events.text == ""
    assert events.reasoning == ""
    assert events._phase.sub_routes["a"] == "ignore"


def test_answer_cap_still_enforced() -> None:
    events = parser(answer_cap=4)
    user_message(events)
    with pytest.raises(ValueError):
        events.feed(
            "item/completed",
            {
                "item": {
                    "itemId": "a",
                    "kind": "agentMessage",
                    "turnId": MAIN,
                    "messagePhase": "finalAnswer",
                    "text": "слишком длинно",
                }
            },
        )


def test_real_subagent_stream_shape() -> None:
    """Миниатюра реального потока: финал подагента — started+delta без completed."""
    events = parser()
    user_message(events, turn="01a1cd20-85b9-79b3-87e0-e20b6d9e8abb")
    main_turn = "01a1cd20-85b9-79b3-87e0-e20b6d9e8abb"
    sub_turn = "01a1cd20-9aed-7f60-a9f5-80af2ba2c496"
    message(
        events, "c", main_turn, "commentary", "Запускаю подагента для подсчёта файлов."
    )
    started(events, "sub-fin", sub_turn, "finalAnswer")
    delta(events, "sub-fin", "В рабочем каталоге ")
    delta(events, "sub-fin", "0 файлов.")
    message(
        events,
        "f",
        main_turn,
        "finalAnswer",
        "Подагент проверил рабочий каталог и насчитал в нём 0 файлов.",
    )
    events.feed("turn/completed", {"terminal": "completed"})
    assert events.text == "Подагент проверил рабочий каталог и насчитал в нём 0 файлов."
    assert "В рабочем каталоге 0 файлов." in events.reasoning
    assert "Запускаю подагента" in events.reasoning


# --- AC2: commentary и финалы подагентов — в reasoning -----------------------


def test_commentary_goes_to_reasoning_live_as_paragraphs() -> None:
    events = parser()
    user_message(events)
    started(events, "c1", MAIN, "commentary")
    live = delta(events, "c1", "Смотрю файлы.")
    assert "Смотрю файлы." in live
    completed(events, "c1", MAIN, "commentary", "Смотрю файлы.")
    message(events, "c2", MAIN, "commentary", "Читаю журналы.")
    assert "Смотрю файлы.\n\nЧитаю журналы." in events.reasoning
    assert (
        "Смотрю файлы." not in events.text
        or events.text == "Смотрю файлы.\n\nЧитаю журналы."
    )


def test_commentary_snapshot_reconciles_without_duplication() -> None:
    events = parser()
    user_message(events)
    started(events, "c1", MAIN, "commentary")
    delta(events, "c1", "Hel")
    delta(events, "c1", "lo")
    tail = completed(events, "c1", MAIN, "commentary", "Hello!")
    assert tail == "!"
    assert events.reasoning.count("Hello!") == 1


def test_commentary_completed_without_string_text_is_ignored() -> None:
    events = parser()
    user_message(events)
    items: list[dict[str, object]] = [
        {
            "itemId": "c1",
            "kind": "agentMessage",
            "turnId": MAIN,
            "messagePhase": "commentary",
        },
        {
            "itemId": "c2",
            "kind": "agentMessage",
            "turnId": MAIN,
            "messagePhase": "commentary",
            "text": 123,
        },
    ]
    for item in items:
        reasoning_before = events.reasoning
        text_before = events.text
        assert events.feed("item/completed", {"item": item}) == ""
        assert events.reasoning == reasoning_before
        assert events.text == text_before


def test_subagent_commentary_is_hidden_everywhere() -> None:
    events = parser()
    user_message(events)
    message(events, "s1", SUB, "commentary", "Секретный статус подагента.")
    assert "Секретный статус подагента." not in events.reasoning
    assert "Секретный статус подагента." not in events.text


def test_subagent_final_becomes_one_reasoning_line_on_completed() -> None:
    events = parser()
    user_message(events)
    message(
        events, "s1", SUB, "finalAnswer", "Строка отчёта\nвторая   строка\n\nтретья"
    )
    lines = [line for line in events.reasoning.splitlines() if "Строка отчёта" in line]
    assert lines == ["Строка отчёта вторая строка третья"]
    assert "Строка отчёта" not in events.text


def test_subagent_final_flushed_once_at_turn_completed() -> None:
    events = parser()
    user_message(events)
    started(events, "s1", SUB, "finalAnswer")
    delta(events, "s1", "Финал без completed.")
    assert "Финал без completed." not in events.reasoning
    tail = events.feed("turn/completed", {"terminal": "completed"})
    assert "Финал без completed." in tail
    assert events.reasoning.count("Финал без completed.") == 1


def test_subagent_final_not_duplicated_when_completed_then_turn_end() -> None:
    events = parser()
    user_message(events)
    message(events, "s1", SUB, "finalAnswer", "Один раз.")
    events.feed("turn/completed", {"terminal": "completed"})
    assert events.reasoning.count("Один раз.") == 1


def test_subagent_final_truncated_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_MUSE_SUBAGENT_FINAL_MAX_CHARS", "10")
    events = parser()
    user_message(events)
    message(events, "s1", SUB, "finalAnswer", "0123456789abcdef")
    assert "0123456789\n" in events.reasoning + "\n"
    assert "0123456789a" not in events.reasoning


def test_subagent_final_default_truncation_300() -> None:
    events = parser()
    user_message(events)
    message(events, "s1", SUB, "finalAnswer", "я" * 400)
    assert "я" * 300 in events.reasoning
    assert "я" * 301 not in events.reasoning


def test_empty_subagent_final_adds_no_line() -> None:
    events = parser()
    user_message(events)
    tool_started(events, "t1", "bash")
    before = events.reasoning
    message(events, "s1", SUB, "finalAnswer", "   \n  ")
    assert events.reasoning == before


def test_subagent_line_separator_after_tool_marker() -> None:
    events = parser()
    user_message(events)
    tool_started(events, "t1", "bash")
    message(events, "s1", SUB, "finalAnswer", "Итог подагента.")
    assert events.reasoning == "[Вызов инструмента: bash]\n\nИтог подагента.\n"


def test_subagent_line_at_reasoning_start_has_no_leading_blank() -> None:
    events = parser()
    user_message(events)
    message(events, "s1", SUB, "finalAnswer", "Первый в reasoning.")
    assert events.reasoning == "Первый в reasoning.\n"


def test_mirror_indices_are_stable_and_distinct() -> None:
    state = PhaseState()
    assert mirror_index_for(state, "c1") == 0
    assert mirror_index_for(state, "c1") == 0
    assert mirror_index_for(state, "c2") == 1
