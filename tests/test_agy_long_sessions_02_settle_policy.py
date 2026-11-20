"""Unit-тесты для core/tool_turn_settle_policy.py (W4, D1)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tool_turn_settle_policy import (  # noqa: E402
    SettleDecision,
    ToolTurnSettleConfig,
    ToolTurnSettleState,
    decide_session_commit,
    evaluate_tool_turn_settle,
    resolve_tool_turn_stop,
    suppress_post_call_content,
)


def _state(**overrides: object) -> ToolTurnSettleState:
    base = {
        "now": 100.0,
        "has_error": False,
        "has_open_tool_call": False,
        "has_calls": False,
        "last_open_chunk_ts": 95.0,
        "last_chunk_ts": 95.0,
        "calls_closed_ts": 95.0,
        "proc_exited": False,
        "result_received": False,
    }
    base.update(overrides)
    return ToolTurnSettleState(**base)  # type: ignore[arg-type]


def test_suppress_post_call_content_only_when_calls_closed() -> None:
    assert suppress_post_call_content(has_calls=True, has_open_tool_call=False) is True
    assert suppress_post_call_content(has_calls=True, has_open_tool_call=True) is False
    assert suppress_post_call_content(has_calls=False, has_open_tool_call=False) is False
    assert suppress_post_call_content(has_calls=False, has_open_tool_call=True) is False


def test_open_tool_call_stall_and_parallel_call_protection() -> None:
    cfg = ToolTurnSettleConfig(settle_timeout_s=5.0, stall_timeout_s=30.0, eof_grace_s=1.5)
    # До 30 с — continue
    d1 = evaluate_tool_turn_settle(
        _state(now=129.9, has_open_tool_call=True, last_open_chunk_ts=100.0), cfg
    )
    assert d1.action == "continue" and d1.should_stop is False
    # Ровно 30 с без закрытых calls -> stall_error
    d2 = evaluate_tool_turn_settle(
        _state(now=130.0, has_open_tool_call=True, has_calls=False, last_open_chunk_ts=100.0), cfg
    )
    assert d2.action == "stall_error" and d2.should_stop is True and "stalled" in d2.error_message
    # При уже закрытых calls -> forced_stop (не stall_error!)
    d3 = evaluate_tool_turn_settle(
        _state(now=130.0, has_open_tool_call=True, has_calls=True, last_open_chunk_ts=100.0), cfg
    )
    assert d3.action == "forced_stop" and d3.tool_turn_stop is True and d3.error_message == ""


def test_closed_calls_grace_and_wait_done() -> None:
    cfg = ToolTurnSettleConfig(settle_timeout_s=5.0, stall_timeout_s=30.0, eof_grace_s=1.5)
    d_cont = evaluate_tool_turn_settle(
        _state(now=104.9, has_calls=True, calls_closed_ts=100.0, last_chunk_ts=100.0), cfg
    )
    assert d_cont.action == "continue" and d_cont.should_stop is False
    d_grace = evaluate_tool_turn_settle(
        _state(now=105.0, has_calls=True, calls_closed_ts=100.0, last_chunk_ts=100.0), cfg
    )
    assert d_grace.action == "wait_eof_grace" and d_grace.should_stop is False
    d_proc = evaluate_tool_turn_settle(
        _state(now=106.4, has_calls=True, calls_closed_ts=100.0, last_chunk_ts=100.0, proc_exited=True),
        cfg,
    )
    assert d_proc.action == "wait_done" and d_proc.should_stop is False
    d_res = evaluate_tool_turn_settle(
        _state(now=105.2, has_calls=True, calls_closed_ts=100.0, last_chunk_ts=100.0, result_received=True),
        cfg,
    )
    assert d_res.action == "wait_done" and d_res.should_stop is False


def test_closed_calls_clean_complete_forced_stop_and_kill_switch() -> None:
    cfg = ToolTurnSettleConfig(settle_timeout_s=5.0, stall_timeout_s=30.0, eof_grace_s=1.5)
    d_clean = evaluate_tool_turn_settle(
        _state(now=106.5, has_calls=True, calls_closed_ts=100.0, last_chunk_ts=100.0, result_received=True),
        cfg,
    )
    assert d_clean.action == "clean_complete" and d_clean.should_stop is True
    assert d_clean.tool_turn_stop is False and d_clean.tool_turn_clean_eof is True
    d_force = evaluate_tool_turn_settle(
        _state(now=106.5, has_calls=True, calls_closed_ts=100.0, last_chunk_ts=100.0, result_received=False),
        cfg,
    )
    assert d_force.action == "forced_stop" and d_force.tool_turn_stop is True
    d_long = evaluate_tool_turn_settle(
        _state(now=140.0, has_calls=True, calls_closed_ts=100.0, last_chunk_ts=100.0), cfg
    )
    assert d_long.action == "forced_stop" and d_long.error_message == ""
    cfg_off = ToolTurnSettleConfig(settle_timeout_s=5.0, eof_grace_s=1.5, eof_grace_enabled=False)
    d_off = evaluate_tool_turn_settle(
        _state(now=105.0, has_calls=True, calls_closed_ts=100.0, last_chunk_ts=100.0), cfg_off
    )
    assert d_off.action == "forced_stop" and d_off.should_stop is True
    assert evaluate_tool_turn_settle(_state(has_error=True), cfg).action == "forced_stop"
    assert evaluate_tool_turn_settle(_state(), cfg).action == "continue"


def test_resolve_tool_turn_stop_and_decide_session_commit() -> None:
    assert resolve_tool_turn_stop(None, proc_exited=False, result_received=False) is None
    assert resolve_tool_turn_stop(lambda: False, proc_exited=False, result_received=False) is None
    forced = resolve_tool_turn_stop(lambda: True, proc_exited=False, result_received=False)
    assert forced is not None and forced.action == "forced_stop"

    class _Owner:
        def turn_complete(self) -> bool:
            return False

        def settle_decision(self, *, proc_exited: bool, result_received: bool) -> SettleDecision:
            return SettleDecision(
                "clean_complete" if result_received else "wait_done",
                result_received,
                False,
                result_received,
            )

    owner = _Owner()
    got = resolve_tool_turn_stop(owner.turn_complete, proc_exited=False, result_received=True)
    assert got is not None and got.action == "clean_complete"

    assert decide_session_commit(
        state="done", rc=0, tool_turn_stop=False, conversation_id="cid-1", cid_valid=True
    ) == "commit"
    assert decide_session_commit(
        state="done", rc=0, tool_turn_stop=True, conversation_id="cid-1", cid_valid=True
    ) == "invalidate"
    assert decide_session_commit(
        state="agy_error", rc=1, tool_turn_stop=False, conversation_id="cid-1", cid_valid=True
    ) == "invalidate"
    assert decide_session_commit(
        state="done", rc=0, tool_turn_stop=False, conversation_id="", cid_valid=False
    ) == "noop"
