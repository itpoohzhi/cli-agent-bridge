"""L1: фазы agentMessage Muse MSP — в content только финальный ответ главного хода.

Фикстуры повторяют форму реальных MSP-событий Muse 1.4.15
(.ai-team/runs/dsh-dup-c1/raw/msp-events*.jsonl): первым приходит
item kind=userMessage главного хода, agentMessage несёт messagePhase и turnId,
дельты — без turnId/kind, финалы подагентов могут не получать item/completed.
"""

from __future__ import annotations

import json

import pytest

from adapters.muse_msp import MspEvents

MAIN = "turn-main"
SUB = "turn-sub"


def parser(**limits: int) -> MspEvents:
    return MspEvents(
        reasoning_cap=limits.get("reasoning_cap", 1 << 20),
        answer_cap=limits.get("answer_cap", 1 << 20),
    )


def user_message(events: MspEvents, turn: str = MAIN) -> None:
    events.feed(
        "item/completed",
        {
            "item": {
                "itemId": "u1",
                "kind": "userMessage",
                "turnId": turn,
                "text": "Вопрос",
            }
        },
    )


def started(events: MspEvents, iid: str, turn: str, phase: str) -> None:
    events.feed(
        "item/started",
        {
            "item": {
                "itemId": iid,
                "kind": "agentMessage",
                "turnId": turn,
                "messagePhase": phase,
            }
        },
    )


def delta(events: MspEvents, iid: str, text: str) -> str:
    return events.feed("item/delta", {"itemId": iid, "field": "text", "delta": text})


def completed(events: MspEvents, iid: str, turn: str, phase: str, text: str) -> str:
    return events.feed(
        "item/completed",
        {
            "item": {
                "itemId": iid,
                "kind": "agentMessage",
                "turnId": turn,
                "messagePhase": phase,
                "text": text,
            }
        },
    )


def message(events: MspEvents, iid: str, turn: str, phase: str, text: str) -> None:
    started(events, iid, turn, phase)
    delta(events, iid, text)
    completed(events, iid, turn, phase, text)


def tool_started(events: MspEvents, iid: str, name: str, args: object = None) -> str:
    item: dict[str, object] = {"itemId": iid, "kind": "toolCall", "tool": name}
    if args is not None:
        item["args"] = args
    return events.feed("item/started", {"item": item})


def tool_completed(
    events: MspEvents,
    iid: str,
    name: str,
    args: object = None,
    status: str = "completed",
) -> str:
    item: dict[str, object] = {
        "itemId": iid,
        "kind": "toolCall",
        "tool": name,
        "status": status,
    }
    if args is not None:
        item["args"] = args
    return events.feed("item/completed", {"item": item})


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


def test_text_fallback_joins_phaseless_messages_with_blank_line() -> None:
    events = parser()
    events.feed(
        "item/completed",
        {"item": {"itemId": "a", "kind": "agentMessage", "text": "Первая часть."}},
    )
    events.feed(
        "item/completed",
        {"item": {"itemId": "b", "kind": "agentMessage", "text": "Вторая часть."}},
    )
    assert events.text == "Первая часть.\n\nВторая часть."


def test_text_fallback_when_no_final_includes_commentary() -> None:
    events = parser()
    user_message(events)
    message(events, "c1", MAIN, "commentary", "Только статус.")
    assert events.text == "Только статус."


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


def test_message_without_turn_id_after_main_known_stays_main() -> None:
    events = parser()
    user_message(events)
    events.feed(
        "item/completed",
        {"item": {"itemId": "a", "kind": "agentMessage", "text": "Без turnId."}},
    )
    assert events.text == "Без turnId."


def test_answer_cap_still_enforced() -> None:
    events = parser(answer_cap=4)
    with pytest.raises(ValueError):
        events.feed(
            "item/completed",
            {"item": {"itemId": "a", "kind": "agentMessage", "text": "слишком длинно"}},
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


# --- AC3: различимые маркеры инструментов ------------------------------------


def test_tool_without_args_keeps_exact_legacy_markers() -> None:
    events = parser()
    first = tool_started(events, "t1", "read_file")
    second = tool_completed(events, "t1", "read_file")
    assert first == "[Вызов инструмента: read_file]\n"
    assert second == "[Инструмент read_file завершён]\n"


def test_tool_hint_from_description_json_string() -> None:
    events = parser()
    args = json.dumps({"command": "ls", "description": "List working directory"})
    first = tool_started(events, "t1", "bash", args)
    second = tool_completed(events, "t1", "bash", args)
    assert first == "[Вызов инструмента: bash — List working directory]\n"
    assert second == ""


def test_tool_hint_path_basename_and_secret_hidden() -> None:
    events = parser()
    args = {"path": "/home/user/secret/report.md", "token": "TOP_SECRET"}
    first = tool_started(events, "t1", "read_file", args)
    assert first == "[Вызов инструмента: read_file — report.md]\n"
    assert "TOP_SECRET" not in events.reasoning
    assert "/home/user" not in events.reasoning


def test_tool_hint_only_secret_fields_falls_back_to_legacy() -> None:
    events = parser()
    args = json.dumps({"command": "echo TOP_SECRET"})
    first = tool_started(events, "t1", "bash", args)
    second = tool_completed(events, "t1", "bash", args)
    assert first == "[Вызов инструмента: bash]\n"
    assert second == "[Инструмент bash завершён]\n"
    assert "TOP_SECRET" not in events.reasoning


def test_tool_hint_invalid_json_args_falls_back_to_legacy() -> None:
    events = parser()
    first = tool_started(events, "t1", "bash", "{not json")
    assert first == "[Вызов инструмента: bash]\n"


def test_tool_hint_first_allowlisted_field_wins() -> None:
    events = parser()
    args = {"path": "/tmp/data.txt", "description": "Read data"}
    first = tool_started(events, "t1", "read_file", args)
    assert first == "[Вызов инструмента: read_file — Read data]\n"


def test_tool_hint_skips_non_string_values() -> None:
    events = parser()
    args = {"description": 42, "pattern": "*.py"}
    first = tool_started(events, "t1", "search", args)
    assert first == "[Вызов инструмента: search — *.py]\n"


def test_tool_hint_truncated_to_80_by_default() -> None:
    events = parser()
    args = {"description": "д" * 100}
    first = tool_started(events, "t1", "bash", args)
    assert "д" * 80 in first
    assert "д" * 81 not in first


def test_tool_hint_fields_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_MUSE_TOOL_HINT_FIELDS", "pattern")
    events = parser()
    args = {"description": "Ignored", "pattern": "needle"}
    first = tool_started(events, "t1", "search", args)
    assert first == "[Вызов инструмента: search — needle]\n"


def test_tool_hint_fields_empty_env_uses_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_MUSE_TOOL_HINT_FIELDS", "")
    events = parser()
    first = tool_started(events, "t1", "bash", {"description": "Default fields"})
    assert first == "[Вызов инструмента: bash — Default fields]\n"


def test_tool_hint_max_chars_zero_disables_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_MUSE_TOOL_HINT_MAX_CHARS", "0")
    events = parser()
    first = tool_started(events, "t1", "bash", {"description": "Hidden"})
    assert first == "[Вызов инструмента: bash]\n"


def test_tool_hint_max_chars_negative_or_garbage_uses_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for raw in ("-5", "abc"):
        monkeypatch.setenv("BRIDGE_MUSE_TOOL_HINT_MAX_CHARS", raw)
        events = parser()
        first = tool_started(events, "t1", "bash", {"description": "Visible hint"})
        assert first == "[Вызов инструмента: bash — Visible hint]\n", raw


def test_failed_hinted_tool_still_gets_completed_line() -> None:
    events = parser()
    args = {"description": "List files"}
    tool_started(events, "t1", "bash", args)
    tail = tool_completed(events, "t1", "bash", args, status="failed")
    assert tail == "[Инструмент bash — List files завершён]\n"


def test_failed_plain_tool_keeps_legacy_completed_line() -> None:
    events = parser()
    tool_started(events, "t1", "bash")
    tail = tool_completed(events, "t1", "bash", status="failed")
    assert tail == "[Инструмент bash завершён]\n"


def test_suppressed_unknown_tool_with_hint_args_emits_nothing() -> None:
    events = parser()
    first = events.feed(
        "item/started",
        {
            "item": {
                "itemId": "t1",
                "kind": "toolCall",
                "args": {"description": "No name"},
            }
        },
    )
    assert first == ""
    assert events.reasoning == ""
