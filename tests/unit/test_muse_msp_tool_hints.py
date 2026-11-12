"""L1: различимые маркеры инструментов Muse MSP (подсказки из allowlist args)."""

from __future__ import annotations

import json

import pytest

from tests.unit.msp_testlib import parser, tool_completed, tool_started

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
