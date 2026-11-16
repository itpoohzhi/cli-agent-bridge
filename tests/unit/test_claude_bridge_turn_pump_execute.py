"""L1: цикл `_Execution.execute`: watchdog-таймаут, уход клиента и учёт активности."""

from __future__ import annotations

import signal
from typing import Any

import pytest

from tests.unit._claude_bridge_tool_fakes import EMPTY
from tests.unit._claude_bridge_turn_fakes import (
    FakeClock,
    FakeController,
    FakeOs,
    Pump,
    bridge as bridge,  # noqa: F401
    build_pump,
    clock as clock,  # noqa: F401
    fake_os as fake_os,  # noqa: F401
)

USAGE = {"input_tokens": 7, "output_tokens": 5}
CONN = object()


def _with_controller(
    bridge: Any,
    monkeypatch: pytest.MonkeyPatch,
    controller: FakeController,
    script: list,
) -> Pump:
    monkeypatch.setattr(bridge, "_watchdog_for", lambda _run: controller)
    return build_pump(bridge, script)


@pytest.mark.parametrize("reason", ("idle_timeout", "absolute_cap"))
def test_execute_watchdog_timeout_kills_group_before_reading_queue(
    bridge: Any,
    clock: FakeClock,
    fake_os: FakeOs,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    controller = FakeController((True, reason, None), interval=5.0)
    pump = _with_controller(bridge, monkeypatch, controller, [])
    clock.advance(5.0)
    out = pump.execution.execute(CONN)
    assert (out["state"], out["rc"]) == ("timeout", 1)
    assert out["err"] == f"claude-p watchdog: {reason}"
    assert fake_os.killed == [(pump.proc.pid, signal.SIGTERM)]
    assert pump.run.q.timeouts == []
    assert controller.closed


def test_execute_client_gone_stops_before_any_event(
    bridge: Any, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    controller = FakeController()
    pump = _with_controller(bridge, monkeypatch, controller, [])
    monkeypatch.setattr(bridge, "_client_gone", lambda _conn: True)
    out = pump.execution.execute(CONN)
    assert (out["state"], out["rc"], out["err"]) == ("client_gone", 1, "")
    assert pump.run.q.timeouts == []
    assert controller.checked == []
    assert controller.closed


def test_execute_client_gone_after_first_event_keeps_partial_text(
    bridge: Any, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    answers = [False, True]
    monkeypatch.setattr(bridge, "_client_gone", lambda _conn: answers.pop(0))
    pump = build_pump(bridge, [("text", "part")])
    out = pump.execution.execute(CONN)
    assert (out["state"], out["rc"], out["text"]) == ("client_gone", 1, "part")
    assert pump.sinks.text == ["part"]


def test_execute_records_activity_for_text_thinking_and_result_only(
    bridge: Any, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    script = [
        ("text", "a"),
        EMPTY,
        ("thinking", "b"),
        ("result", {"usage": USAGE}),
        ("done", 0),
    ]
    controller = FakeController(interval=5.0)
    pump = _with_controller(bridge, monkeypatch, controller, script)
    out = pump.execution.execute(CONN)
    assert controller.activity == ["text", "thinking", "result"]
    assert (out["state"], out["rc"], out["text"]) == ("done", 0, "a")
    assert out["reasoning"] == "b"
    assert out["usage"] == USAGE
    assert controller.checked == []
    assert controller.closed


def test_execute_pump_error_is_not_activity(
    bridge: Any, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    controller = FakeController(interval=5.0)
    pump = _with_controller(bridge, monkeypatch, controller, [("pump_error", "boom")])
    out = pump.execution.execute(CONN)
    assert (out["state"], out["rc"], out["err"]) == ("pump_error", 1, "boom")
    assert controller.activity == []
    assert controller.closed


def test_execute_without_process_runs_without_watchdog(
    bridge: Any, clock: FakeClock
) -> None:
    pump = build_pump(bridge, [("text", "hi"), ("done", 0)])
    pump.run.proc = None
    assert bridge._watchdog_for(pump.run) is None
    out = pump.execution.execute(CONN)
    assert (out["state"], out["rc"], out["text"]) == ("done", 0, "hi")
    assert pump.run.q.timeouts == [bridge.POLL_INTERVAL_S] * 2
