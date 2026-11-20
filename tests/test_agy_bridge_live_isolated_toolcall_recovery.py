"""Live-Isolated E2E (W3-A, Гейт 3): RC-2 — `Malformed function call` и повторный `<tool_call>`.

Реальный процесс `server.py`, стаб `agy` пишет `PLANNER_RESPONSE`/`ERROR_MESSAGE` в транскрипт и
завершает ход `result ERROR`. Recovery ON → структурные `tool_calls`; 9/10 → fail-closed REJECT.
"""

from __future__ import annotations

from pathlib import Path

from live_isolated_harness import ALL_OFF, ALL_ON, ChatResult, running


def _tool_call_deltas(result: ChatResult) -> list[object]:
    return [call for batch in result.delta_values("tool_calls") for call in batch]  # type: ignore[attr-defined, union-attr]


def test_recovery_on_delivers_structured_tool_calls(tmp_path: Path) -> None:
    with running(tmp_path, "malformed_valid", ALL_ON) as bridge:
        result = bridge.chat()
        spawns, log = bridge.spawn_count(), bridge.log_text()
    calls = _tool_call_deltas(result)
    assert result.status == 200 and spawns == 1 and result.errors == [] and result.done_count == 1
    assert len(calls) == 5 and "tool_calls" in result.finish_reasons  # зеркальные пары схлопнуты (INV-S5)
    content = "".join(str(v) for v in result.delta_values("content"))
    assert "<tool_call>" not in content and "Retries remaining" not in content  # INV-S4
    assert "Retries remaining" not in result.raw
    assert "turn-resolved reason=toolcall.recovered" in log
    assert bridge.is_clean, bridge.leaks


def test_nine_of_ten_is_rejected_fail_closed_with_masked_error(tmp_path: Path) -> None:
    with running(tmp_path, "malformed_nine_ten", ALL_ON) as bridge:
        result = bridge.chat()
        spawns, log = bridge.spawn_count(), bridge.log_text()
    assert result.status == 200 and spawns == 1  # INV-S7: повторного спавна нет
    assert _tool_call_deltas(result) == [] and len(result.errors) == 1 and result.done_count == 1
    assert "Retries remaining" not in result.raw and "Malformed function call" in str(result.errors[0])
    assert "toolcall.rejected:strict.parse.failed" in log
    assert bridge.is_clean, bridge.leaks


def test_flags_off_is_base_error_chunk_with_vendor_phrase(tmp_path: Path) -> None:
    """Флаги выкл.: побайтно база — error-chunk с вендорной фразой, без tool_calls и turn-resolved."""
    with running(tmp_path, "malformed_valid", ALL_OFF) as bridge:
        result = bridge.chat()
        spawns, log = bridge.spawn_count(), bridge.log_text()
    assert result.status == 200 and spawns == 1 and _tool_call_deltas(result) == []
    assert len(result.errors) == 1 and "Retries remaining: 3" in str(result.errors[0])
    assert "turn-resolved" not in log
    assert bridge.is_clean, bridge.leaks


def test_recovery_without_tools_in_request_is_rejected(tmp_path: Path) -> None:
    """Запрос без tools: нет структурного эмулятора — recovery не выполняется, ошибка как в базе."""
    with running(tmp_path, "malformed_valid", ALL_ON) as bridge:
        result = bridge.chat(tools=False)
    assert _tool_call_deltas(result) == [] and len(result.errors) == 1
    assert bridge.is_clean, bridge.leaks
