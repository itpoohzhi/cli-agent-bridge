"""Unit-тесты для core/turn_usage_fsm.py и agy_runtime/turn_usage_finalize.py (W3, D4)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_AGY_DIR = str(_ROOT / "bridges/agy-bridge")
if _AGY_DIR not in sys.path:
    sys.path.append(_AGY_DIR)

from agy_runtime.turn_usage_finalize import (  # noqa: E402
    ensure_drained_before_usage,
    resolve_and_log_step_usage,
)
from core.turn_usage_fsm import resolve_turn_usage, should_emit_wire_usage  # noqa: E402


@dataclass
class _Snap:
    last_step_usage: tuple[int, int, int | None, int] | None = None
    turn_output_tokens_sum: int = 0
    observed_planner_steps: int = 0
    observed_planner_steps_saturated: bool = False
    completeness: bool = True
    invalid_records_count: int = 0


def test_resolve_turn_usage_last_step_complete_and_incomplete() -> None:
    snap_ok = _Snap(last_step_usage=(3, 1000, 400, 50), turn_output_tokens_sum=80, completeness=True)
    res_ok = resolve_turn_usage({"usage": {}, "rc": 0, "state": "done"}, snap_ok, 100000, True)
    assert res_ok.resolved["source"] == "last_step"
    assert res_ok.resolved["wire"] == {
        "prompt_tokens": 1400,
        "completion_tokens": 80,
        "total_tokens": 1480,
        "prompt_tokens_details": {"cached_tokens": 400},
    }
    assert res_ok.resolved["emit_wire_usage"] is True
    assert res_ok.log_messages == ()

    snap_inc = _Snap(last_step_usage=(2, 500, 100, 10), observed_planner_steps=2, completeness=False, invalid_records_count=1)
    res_inc = resolve_turn_usage({"usage": {"output_tokens": 25}}, snap_inc, 100000, True)
    assert res_inc.resolved["reason"] == "ledger_incomplete"
    assert res_inc.resolved["wire"]["completion_tokens"] == 0  # type: ignore[index]
    assert len(res_inc.log_messages) == 1 and "usage-step-ledger-incomplete" in res_inc.log_messages[0]


def test_resolve_turn_usage_missing_cumulative_and_alias_conflict() -> None:
    # Строгий missing_usage -> emit_wire_usage=False
    empty_snap = _Snap()
    res_miss = resolve_turn_usage({"rc": 0, "state": "done", "usage": {}}, empty_snap, 100000, True)
    assert res_miss.resolved["reason"] == "missing_usage"
    assert res_miss.resolved["emit_wire_usage"] is False
    assert should_emit_wire_usage(res_miss.resolved) is False

    # cumulative_estimate при переполнении окна
    res_cum = resolve_turn_usage(
        {"rc": 0, "state": "done", "num_turns": 2, "tool_events": 1, "usage": {"input_tokens": 250000, "output_tokens": 30}},
        empty_snap,
        100000,
        False,
    )
    assert res_cum.resolved["source"] == "cumulative_estimate"
    assert res_cum.resolved["reason"] == "over_window"
    assert res_cum.resolved["wire"]["prompt_tokens"] == 83333  # type: ignore[index]
    assert res_cum.resolved["wire"]["completion_tokens"] == 30  # type: ignore[index]
    assert len(res_cum.log_messages) == 1 and "usage-cumulative-fallback" in res_cum.log_messages[0]

    # alias_conflict
    res_conf = resolve_turn_usage(
        {"rc": 0, "state": "done", "usage": {"input_tokens": 500, "cache_read_tokens": 100, "cacheReadTokens": 200}},
        empty_snap,
        100000,
        True,
    )
    assert res_conf.resolved["reason"] == "alias_conflict"
    assert res_conf.resolved["emit_wire_usage"] is True
    assert should_emit_wire_usage({}) is True


def test_usage_fsm_rejects_bool_and_error_status() -> None:
    r_bool = resolve_turn_usage({"rc": 0, "state": "done", "usage": {"input_tokens": True}}, None, 200000, False)
    assert r_bool.resolved["reason"] == "missing_usage" and r_bool.resolved["emit_wire_usage"] is False
    r_err = resolve_turn_usage(
        {"rc": 0, "state": "done", "result": {"status": "ERROR"}, "usage": {"input_tokens": 500000}},
        None, 200000, False,
    )
    assert r_err.resolved["reason"] == "not_success" and r_err.resolved["source"] == "result"


def test_ensure_drained_before_usage_short_circuit_and_retained_events() -> None:
    calls: list[str] = []

    class _Thread:
        def join(self, timeout: float | None = None) -> None:
            calls.append(f"join:{timeout}")

    class _Run:
        tail = type("T", (), {"thread": _Thread()})()

        def terminal_drain(self, rem: float) -> list[tuple[str, str]]:
            calls.append(f"drain:{rem}")
            return [("text", "tail-chunk")]

    run = _Run()
    # Штатный путь _finish_done -> 0 мс short-circuit!
    out_normal: dict[str, object] = {"state": "done", "tool_turn_stop": False}
    assert ensure_drained_before_usage(run, out_normal, drain_max_s=0.5) is False
    assert calls == []

    # Ранний выход tool_turn_clean_eof -> drain + сохранение retained_events + join
    out_early: dict[str, object] = {
        "state": "done",
        "tool_turn_clean_eof": True,
        "retained_events": [("text", "first")],
    }
    assert ensure_drained_before_usage(run, out_early, drain_max_s=0.5, clock=lambda: 10.0) is True
    assert out_early["retained_events"] == [("text", "first"), ("text", "tail-chunk")]
    assert len(calls) == 2

    # resolve_and_log_step_usage прокидывает логи
    logged: list[str] = []
    snap_inc = _Snap(last_step_usage=(1, 100, 0, 5), completeness=False)
    resolved = resolve_and_log_step_usage({"usage": {}}, snap_inc, 100000, True, logged.append)
    assert resolved["reason"] == "ledger_incomplete" and len(logged) == 1
