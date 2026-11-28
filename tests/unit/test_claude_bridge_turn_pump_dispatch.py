"""L1: диспетчеризация событий хода Claude-моста (`_Execution.dispatch`)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.unit._claude_bridge_turn_fakes import (
    FakeClock,
    Sinks,
    bridge as bridge,  # noqa: F401
    build_pump,
    clock as clock,  # noqa: F401
)

USAGE = {"input_tokens": 7, "output_tokens": 5}


def test_dispatch_result_records_usage_and_continues(
    bridge: Any, clock: FakeClock
) -> None:
    pump = build_pump(bridge)
    payload = {"usage": USAGE, "subtype": "success"}
    assert pump.execution.dispatch("result", payload) is None
    assert pump.execution.result == payload
    assert pump.execution.usage == USAGE


@pytest.mark.parametrize("payload", ({"subtype": "success"}, {"usage": None}))
def test_dispatch_result_without_usage_defaults_to_empty(
    bridge: Any, clock: FakeClock, payload: dict
) -> None:
    pump = build_pump(bridge)
    assert pump.execution.dispatch("result", payload) is None
    assert pump.execution.result == payload
    assert pump.execution.usage == {}


def test_dispatch_text_and_thinking_reach_sinks(bridge: Any, clock: FakeClock) -> None:
    pump = build_pump(bridge)
    assert pump.execution.dispatch("text", "ab") is None
    assert pump.execution.dispatch("thinking", "why") is None
    assert pump.sinks.text == ["ab"]
    assert pump.sinks.reasoning == ["why"]
    state = pump.execution.state("probe", 0)
    assert (state["text"], state["reasoning"]) == ("ab", "why")


def test_dispatch_pump_error_returns_failed_state(
    bridge: Any, clock: FakeClock
) -> None:
    pump = build_pump(bridge)
    out = pump.execution.dispatch("pump_error", "reader boom")
    assert (out["state"], out["rc"], out["err"]) == ("pump_error", 1, "reader boom")
    assert clock.sleeps == []


def test_dispatch_done_reports_exit_code_and_stderr(
    bridge: Any, clock: FakeClock
) -> None:
    pump = build_pump(bridge)
    pump.run.err_box.extend(["warn ", "tail"])
    pump.execution.dispatch("text", "ok")
    pump.execution.dispatch("result", {"usage": USAGE})
    out = pump.execution.dispatch("done", 3)
    assert out == {
        "rc": 3,
        "text": "ok",
        "usage": USAGE,
        "reasoning": "",
        "result": {"usage": USAGE},
        "state": "done",
        "err": "warn tail",
        "tool_calls": [],
    }
    assert clock.sleeps == []


def test_dispatch_done_after_client_gone_is_not_an_error(
    bridge: Any, clock: FakeClock
) -> None:
    pump = build_pump(bridge, sinks=Sinks(accept_text=False))
    pump.run.err_box.append("noise")
    first = pump.execution.dispatch("text", "a")
    assert (first["state"], first["rc"]) == ("client_gone", 1)
    out = pump.execution.dispatch("done", 0)
    assert (out["state"], out["rc"], out["err"]) == ("client_gone", 1, "")
    assert clock.sleeps == []


def test_dispatch_result_after_client_gone_stops_turn(
    bridge: Any, clock: FakeClock
) -> None:
    pump = build_pump(bridge)
    pump.execution.gone = True
    out = pump.execution.dispatch("result", {"usage": USAGE})
    assert (out["state"], out["rc"], out["err"]) == ("client_gone", 1, "")
    assert pump.execution.usage == USAGE


def test_dispatch_idle_continues_without_output(bridge: Any, clock: FakeClock) -> None:
    pump = build_pump(bridge)
    assert pump.execution.dispatch("idle", None) is None
    assert pump.sinks.text == [] and pump.sinks.reasoning == []
