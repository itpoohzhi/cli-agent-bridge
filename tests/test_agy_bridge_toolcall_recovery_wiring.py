"""Wiring AD-005/AD-006 (W2-C): recovery «ошибка functionCall → валидный tool_call» и маска фразы.

Шаги транскрипта собирает `_TranscriptTail._emit_record` (через `observe_record`), решение и
доставку принимает фасад (INV-S1..S8): fail-closed, once-per-turn, только структурные tool_calls.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from resilience_wiring_support import (
    collect_log,
    enable,
    facade,
    load_server,
    malformed_ctx,
    stub,
    tail_with_steps,
    use_config,
)


def _out(**extra: Any) -> dict[str, Any]:
    return {"state": "agy_error", "rc": 1, "err": stub.MALFORMED_TEXT, "text": "", "tool_events": 0, **extra}


def _recover(tail: object, ctx: dict[str, Any], out: dict[str, Any]) -> list[str]:
    lines, log = collect_log()
    facade().recover(ctx, SimpleNamespace(_tail=tail), out, log)
    return lines


def test_observe_flag_off_collects_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = use_config(monkeypatch, tmp_path)
    assert not hasattr(tail_with_steps(), "_resilience_step_tracker")


def test_emit_record_hook_feeds_tracker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Реальный `_TranscriptTail._emit_record` передаёт ERROR_MESSAGE и PLANNER_RESPONSE фасаду."""
    enable(monkeypatch, tmp_path, "recovery")
    server = load_server()
    tail = server._TranscriptTail.__new__(server._TranscriptTail)  # pyright: ignore[reportPrivateUsage]
    tail.base_idx = 0
    tail._in_rewrite = False  # pyright: ignore[reportPrivateUsage]
    seen: list[tuple[int | None, str]] = []
    tail.note_error_record = lambda rtype, rec, idx: None  # type: ignore[method-assign]
    tail._emit_planner_record = lambda rec, idx: seen.append((idx, str(rec.get("content", ""))[:10]))  # type: ignore[method-assign]
    import json

    for rec in stub._transcript_records("malformed_valid"):  # pyright: ignore[reportPrivateUsage]
        tail._emit_record(json.dumps(rec).encode())  # pyright: ignore[reportPrivateUsage]
    steps = tail._resilience_step_tracker.snapshot().steps  # pyright: ignore[reportAttributeAccessIssue]
    assert [(s.index, s.kind) for s in steps] == [(4, "planner"), (5, "error"), (6, "planner")]
    assert len(seen) == 2


def test_recover_valid_retry_delivers_structured_calls_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "recovery")
    tail, fed = tail_with_steps(), []
    ctx, out = malformed_ctx(fed), _out()
    lines = _recover(tail, ctx, out)
    assert (out["state"], out["rc"], out["err"], out["tool_turn_stop"]) == ("done", 0, "", True)
    assert len(fed) == 1 and fed[0].count("<tool_call>") == 5 and "Retries remaining" not in fed[0]
    assert any("turn-resolved reason=toolcall.recovered" in line for line in lines)
    again = _out()
    _ = _recover(tail, ctx, again)  # INV-S6: once-per-turn
    assert again["state"] == "agy_error" and len(fed) == 1


def test_recover_nine_of_ten_rejected_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "recovery")
    fed: list[str] = []
    out = _out()
    lines = _recover(tail_with_steps(broken=True), malformed_ctx(fed), out)
    assert fed == [] and out["state"] == "agy_error"
    assert any("toolcall.rejected:strict.parse.failed" in line for line in lines)


def test_recover_flag_off_is_noop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "recovery")
    tail = tail_with_steps()
    _ = use_config(monkeypatch, tmp_path)
    fed: list[str] = []
    out = _out()
    assert _recover(tail, malformed_ctx(fed), out) == [] and fed == [] and out["state"] == "agy_error"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda ctx, out: out.update(text="уже ушёл текст"),  # INV-S1: content
        lambda ctx, out: out.update(tool_events=1),  # INV-S1: tool_events
        lambda ctx, out: out.update(err="HTTP 401 Unauthorized"),  # не functionCall-ошибка
        lambda ctx, out: out.update(state="done"),  # не agy_error
        lambda ctx, out: ctx.update(tools=[{"type": "function", "function": {"name": "bash"}}]),  # имя вне tools
        lambda ctx, out: ctx.pop("recovery_feed"),  # нет структурного эмулятора (JSON-режим)
    ],
)
def test_recover_inv_s1_and_guards_reject(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mutate: Any) -> None:
    enable(monkeypatch, tmp_path, "recovery")
    fed: list[str] = []
    ctx, out = malformed_ctx(fed), _out()
    mutate(ctx, out)
    before = dict(out)
    _ = _recover(tail_with_steps(), ctx, out)
    assert fed == []
    assert out["state"] == before["state"] and out["rc"] == before["rc"]


def test_recover_content_delivered_to_client_rejects(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from core.content_delivery_tracker import ContentDeliveryTracker

    enable(monkeypatch, tmp_path, "recovery")
    tracker = ContentDeliveryTracker()
    tracker.mark_content("частичный ответ")
    fed: list[str] = []
    out = _out()
    _ = _recover(tail_with_steps(), {**malformed_ctx(fed), "delivery_tracker": tracker}, out)
    assert fed == [] and out["state"] == "agy_error"


def test_error_body_masks_only_when_flag_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    server = load_server()
    body_in = {"state": "agy_error", "err": stub.MALFORMED_TEXT}
    _ = use_config(monkeypatch, tmp_path)
    base = server.Handler._error_body(dict(body_in))  # pyright: ignore[reportPrivateUsage]
    assert "Retries remaining: 3" in base["message"]
    enable(monkeypatch, tmp_path, "mask")
    masked = server.Handler._error_body(dict(body_in))  # pyright: ignore[reportPrivateUsage]
    assert "Retries remaining" not in masked["message"] and "Malformed function call" in masked["message"]
    assert masked["type"] == base["type"] == "agy_error" and masked["code"] == 502


def test_error_body_masks_pump_error_detail_and_none_passthrough(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "mask")
    server = load_server()
    pump = server.Handler._error_body({"state": "pump_error", "err": "boom Retries remaining: 9"})  # pyright: ignore[reportPrivateUsage]
    assert "Retries remaining" not in pump["detail"]
    ok = server.Handler._error_body({"state": "done", "rc": 0, "text": "ok"}, True)  # pyright: ignore[reportPrivateUsage]
    assert ok is None
