"""Тесты сверки thinking-токенов в core/turn_usage_fsm.py (W5; кейс req_5fc92fd732a5)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.turn_usage_fsm import TurnUsageResolution, resolve_turn_usage  # noqa: E402


@dataclass
class _Snap:
    last_step_usage: tuple[int, int, int | None, int] | None = None
    turn_output_tokens_sum: int = 0
    observed_planner_steps: int = 0
    observed_planner_steps_saturated: bool = False
    completeness: bool = True
    invalid_records_count: int = 0


def _resolve(
    usage: dict[str, int], snap: _Snap | None = None, resume: bool = False
) -> TurnUsageResolution:
    return resolve_turn_usage({"rc": 0, "state": "done", "usage": usage}, snap, 272000, resume)


def test_live_case_req_5fc92fd732a5_no_double_counting() -> None:
    res = _resolve(
        {"input_tokens": 15334, "output_tokens": 16310, "thinking_tokens": 14976, "total_tokens": 31644}
    )
    wire = res.resolved["wire"]
    assert isinstance(wire, dict)
    assert wire["prompt_tokens"] == 15334
    assert wire["completion_tokens"] == 16310  # нет двойного сложения raw_thinking
    assert wire["total_tokens"] == 31644
    assert wire["completion_tokens_details"] == {"reasoning_tokens": 14976}
    assert res.resolved["reasoning"] == 14976
    assert res.resolved["reasoning_inconsistent"] is False
    assert res.resolved["raw_thinking"] == 14976 and res.resolved["raw_total"] == 31644


def test_in_plus_out_plus_thinking_equals_total() -> None:
    res = _resolve({"input_tokens": 100, "output_tokens": 50, "thinking_tokens": 25, "total_tokens": 175})
    wire = res.resolved["wire"]
    assert isinstance(wire, dict)
    assert wire["completion_tokens"] == 75  # raw_out + raw_thinking
    assert wire["total_tokens"] == 175
    assert wire["completion_tokens_details"] == {"reasoning_tokens": 25}
    assert res.resolved["reasoning"] == 25
    assert res.resolved["reasoning_inconsistent"] is False


def test_thinking_zero_keeps_wire_structure() -> None:
    res = _resolve({"input_tokens": 10, "output_tokens": 5, "thinking_tokens": 0, "total_tokens": 15})
    wire = res.resolved["wire"]
    assert isinstance(wire, dict)
    assert wire["completion_tokens"] == 5
    assert "completion_tokens_details" not in wire
    assert res.resolved["reasoning"] is None
    assert res.resolved["reasoning_inconsistent"] is False


def test_total_zero_ambiguous_without_double_count() -> None:
    res = _resolve({"input_tokens": 10, "output_tokens": 5, "thinking_tokens": 3, "total_tokens": 0})
    wire = res.resolved["wire"]
    assert isinstance(wire, dict)
    assert wire["completion_tokens"] == 5
    assert wire["total_tokens"] == 15
    assert wire["completion_tokens_details"] == {"reasoning_tokens": 3}


def test_thinking_exceeds_output_no_clamp() -> None:
    res = _resolve({"input_tokens": 10, "output_tokens": 5, "thinking_tokens": 20, "total_tokens": 0})
    wire = res.resolved["wire"]
    assert isinstance(wire, dict)
    assert wire["completion_tokens"] == 5
    assert "completion_tokens_details" not in wire
    assert res.resolved["reasoning"] is None
    assert res.resolved["reasoning_inconsistent"] is True  # no clamp


def test_last_step_exports_or_omits_reasoning_by_completion() -> None:
    snap = _Snap(last_step_usage=(1, 100, 0, 5), turn_output_tokens_sum=80, completeness=True)
    res_ok = _resolve({"thinking_tokens": 30}, snap, resume=True)
    wire_ok = res_ok.resolved["wire"]
    assert isinstance(wire_ok, dict)
    assert res_ok.resolved["source"] == "last_step"
    assert wire_ok["completion_tokens"] == 80
    assert wire_ok["completion_tokens_details"] == {"reasoning_tokens": 30}
    assert res_ok.resolved["reasoning_inconsistent"] is False

    res_bad = _resolve({"thinking_tokens": 90}, snap, resume=True)
    wire_bad = res_bad.resolved["wire"]
    assert isinstance(wire_bad, dict)
    assert wire_bad["completion_tokens"] == 80
    assert "completion_tokens_details" not in wire_bad
    assert res_bad.resolved["reasoning"] is None
    assert res_bad.resolved["reasoning_inconsistent"] is True  # no clamp, опущено
