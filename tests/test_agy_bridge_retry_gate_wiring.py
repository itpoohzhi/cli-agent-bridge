"""Wiring AD-002/AD-003/AD-004 (W2-B): keepalive-only commit, гейт бюджета повтора, retain сессии.

Хуки `SseStreamSession` ведут `ContentDeliveryTracker`; `server.py` отдаёт решения фасаду.
Флаги выключены → прежнее поведение (`stream_committed` запрещает невидимый повтор).
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from resilience_wiring_support import collect_log, enable, facade, make_session, stub, use_config

NETWORK_OUT = MappingProxyType({"err": stub.USERINFO_EOF, "state": "agy_error"})
MODEL_OUT = MappingProxyType({"err": stub.MALFORMED_TEXT, "state": "agy_error"})


def test_session_keepalive_and_role_delta_are_not_delivery() -> None:
    session, _wire, ctx = make_session()
    assert session.commit() is True and ctx["stream_committed"] is True
    _ = session.keepalive()
    facts = session.delivery.snapshot()
    assert facts.keepalive_count >= 2 and facts.delivered is False


@pytest.mark.parametrize(
    ("action", "field"),
    [("on_text", "content_bytes"), ("on_reasoning", "reasoning_bytes")],
)
def test_session_real_deltas_count_as_delivery(action: str, field: str) -> None:
    session, _wire, _ctx = make_session()
    _ = session.commit()
    _ = getattr(session, action)("текст")
    facts = session.delivery.snapshot()
    assert facts.delivered is True and getattr(facts, field) == len("текст".encode())


def test_session_tool_calls_and_trace_count_as_delivery() -> None:
    session, _wire, ctx = make_session()
    _ = session.commit()
    _ = session.on_calls([{"index": 0}, {"index": 1}])
    _ = session.on_tool_trace({"type": "tool_use"})
    facts = session.delivery.snapshot()
    assert (facts.tool_calls, facts.tool_events, ctx["delivery_tracker"] is session.delivery) == (2, 1, True)


def _ctx(session_ctx: dict[str, Any], **extra: object) -> dict[str, Any]:
    return {**session_ctx, **extra}


def test_flag_off_commit_blocks_retry_like_base(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = use_config(monkeypatch, tmp_path)
    session, _wire, ctx = make_session()
    _ = session.commit()
    assert facade().delivered_after_commit(ctx, NETWORK_OUT, False) is True


def test_flag_on_keepalive_only_network_failure_allows_invisible_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "keepalive")
    session, _wire, ctx = make_session()
    _ = session.commit()
    _ = session.keepalive()
    assert facade().delivered_after_commit(ctx, NETWORK_OUT, False) is False


@pytest.mark.parametrize("action", ["on_text", "on_reasoning"])
def test_flag_on_delivered_content_still_blocks_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, action: str) -> None:
    enable(monkeypatch, tmp_path, "keepalive")
    session, _wire, ctx = make_session()
    _ = session.commit()
    _ = getattr(session, action)("x")
    assert facade().delivered_after_commit(ctx, NETWORK_OUT, False) is True


def test_flag_on_tool_activity_or_events_block_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "keepalive")
    session, _wire, ctx = make_session()
    _ = session.commit()
    assert facade().delivered_after_commit(_ctx(ctx, tool_activity=True), NETWORK_OUT, False) is True
    assert facade().delivered_after_commit(ctx, {**NETWORK_OUT, "tool_events": 2}, False) is True


def test_flag_on_non_network_error_keeps_base_commit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """INV-S7: ошибка functionCall (не сеть) после commit не даёт повторного спавна."""
    enable(monkeypatch, tmp_path, "keepalive")
    session, _wire, ctx = make_session()
    _ = session.commit()
    assert facade().delivered_after_commit(ctx, MODEL_OUT, False) is True


def test_rejected_recovery_blocks_retry_like_base(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "keepalive")
    session, _wire, ctx = make_session()
    _ = session.commit()
    assert facade().delivered_after_commit(_ctx(ctx, _resilience_recovery_done=True), NETWORK_OUT, False) is True


def test_take_flag_off_delegates_to_base_token_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = use_config(monkeypatch, tmp_path)
    calls: list[int] = []
    ctx: dict[str, Any] = {}
    assert facade().take(ctx, {}, lambda: calls.append(1) or True, collect_log()[1]) is True
    assert calls == [1] and ctx == {}


def test_take_flag_on_budget_gate_and_attempt_cap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "pause")
    fac = facade()
    lines, log = collect_log()
    ctx: dict[str, Any] = {"t_req_start": 0.0, "resilience_clock": lambda: 30.0}
    spent: list[int] = []
    assert fac.take(ctx, {"duration_s": 23.0}, lambda: spent.append(1) or True, log) is True
    assert fac.take(ctx, {"duration_s": 23.0}, lambda: spent.append(1) or True, log) is False  # max_retries=1
    late: dict[str, Any] = {"t_req_start": 0.0, "resilience_clock": lambda: 700.0}
    assert fac.take(late, {"duration_s": 23.0}, lambda: spent.append(1) or True, log) is False  # бюджет 600 с
    assert spent == [1] and any("turn-resolved" in line and "retry.gate" in line for line in lines)


@pytest.mark.parametrize(
    ("flag_on", "out", "expect_invalidated"),
    [
        (False, {"err": stub.USERINFO_EOF, "num_turns": 0, "conversation_id": ""}, True),
        (True, {"err": stub.USERINFO_EOF, "num_turns": 0, "conversation_id": ""}, False),
        (True, {"err": stub.USERINFO_EOF, "num_turns": 2, "conversation_id": "c83f5757"}, True),
        (True, {"err": stub.MALFORMED_TEXT, "num_turns": 0, "conversation_id": ""}, True),
        (True, {"err": stub.USERINFO_EOF, "num_turns": None, "conversation_id": "c1"}, True),
    ],
)
def test_hot_session_retain_table(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flag_on: bool, out: dict[str, Any], expect_invalidated: bool) -> None:
    enable(monkeypatch, tmp_path, *(["retain"] if flag_on else []))
    seen: list[tuple[object, object]] = []
    ctx = {"sess_key": ("m", "/w", "high"), "conversation_id": "cid-1"}
    facade().invalidate(ctx, out, lambda key, cid: seen.append((key, cid)), collect_log()[1])
    assert bool(seen) is expect_invalidated
    assert seen in ([], [(ctx["sess_key"], "cid-1")])
