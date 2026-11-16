"""L1: watchdog и keepalive цикла хода Claude-моста (`_Execution`) на фейковых часах."""

from __future__ import annotations

import signal
from typing import Any

import pytest

from tests.unit._claude_bridge_turn_fakes import (
    FakeClock,
    FakeController,
    FakeOs,
    Sinks,
    bridge as bridge,  # noqa: F401
    build_pump,
    clock as clock,  # noqa: F401
    fake_os as fake_os,  # noqa: F401
)
from tests.unit._claude_bridge_tool_fakes import EMPTY

KEEPALIVE_S = 10.0


def test_watchdog_without_controller_returns_empty(
    bridge: Any, clock: FakeClock, fake_os: FakeOs
) -> None:
    pump = build_pump(bridge)
    clock.advance(10_000.0)
    assert pump.execution.check_watchdog(None) == ""
    assert fake_os.killed == []
    assert pump.proc.waits == []


def test_watchdog_checks_only_after_interval(
    bridge: Any, clock: FakeClock, fake_os: FakeOs
) -> None:
    controller = FakeController(interval=5.0)
    pump = build_pump(bridge)
    clock.advance(4.999)
    assert pump.execution.check_watchdog(controller) == ""
    assert controller.checked == []
    clock.advance(0.001)
    assert pump.execution.check_watchdog(controller) == ""
    assert controller.checked == [pump.proc.pid]
    clock.advance(4.999)
    assert pump.execution.check_watchdog(controller) == ""
    assert controller.checked == [pump.proc.pid]
    assert fake_os.killed == []


@pytest.mark.parametrize(
    "verdict",
    (
        (False, "", None),
        (False, "idle_timeout", None),
        (True, "child_exited", None),
        (True, "liveness_stalled", None),
    ),
)
def test_watchdog_without_stop_reason_does_not_kill(
    bridge: Any, clock: FakeClock, fake_os: FakeOs, verdict: tuple
) -> None:
    controller = FakeController(verdict, interval=5.0)
    pump = build_pump(bridge)
    clock.advance(5.0)
    assert pump.execution.check_watchdog(controller) == ""
    assert controller.checked == [pump.proc.pid]
    assert fake_os.killed == []
    assert pump.proc.waits == []


@pytest.mark.parametrize(
    "reason,expected",
    (
        ("idle_timeout", "claude-p watchdog: idle_timeout"),
        ("absolute_cap", "claude-p watchdog: absolute_cap"),
    ),
)
def test_watchdog_kills_process_group_with_reason(
    bridge: Any,
    clock: FakeClock,
    fake_os: FakeOs,
    reason: str,
    expected: str,
) -> None:
    controller = FakeController((True, reason, None), interval=5.0)
    pump = build_pump(bridge)
    clock.advance(5.0)
    assert pump.execution.check_watchdog(controller) == expected
    assert fake_os.killed == [(pump.proc.pid, signal.SIGTERM)]
    assert pump.proc.waits == [bridge.PROCESS_WAIT_S]


def test_keepalive_waits_for_boundary(
    bridge: Any, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bridge, "KEEPALIVE_S", KEEPALIVE_S)
    sinks = Sinks(keepalive=True)
    pump = build_pump(bridge, [EMPTY, EMPTY], sinks)
    clock.advance(KEEPALIVE_S - 0.001)
    assert pump.execution.next_event() == ("idle", None)
    assert sinks.keepalives == 0
    assert not pump.execution.gone
    assert pump.run.q.timeouts == [bridge.POLL_INTERVAL_S]
    clock.advance(0.001)
    assert pump.execution.next_event() == ("idle", None)
    assert sinks.keepalives == 1
    assert not pump.execution.gone


def test_keepalive_resets_interval_after_beat(
    bridge: Any, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bridge, "KEEPALIVE_S", KEEPALIVE_S)
    sinks = Sinks(keepalive=True)
    pump = build_pump(bridge, [EMPTY, EMPTY, EMPTY], sinks)
    clock.advance(KEEPALIVE_S)
    pump.execution.next_event()
    clock.advance(KEEPALIVE_S - 0.001)
    pump.execution.next_event()
    assert sinks.keepalives == 1
    clock.advance(0.001)
    pump.execution.next_event()
    assert sinks.keepalives == 2


def test_keepalive_failure_marks_client_gone(
    bridge: Any, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bridge, "KEEPALIVE_S", KEEPALIVE_S)
    sinks = Sinks(keepalive=False)
    pump = build_pump(bridge, [EMPTY], sinks)
    clock.advance(KEEPALIVE_S)
    assert pump.execution.next_event() == ("idle", None)
    assert sinks.keepalives == 1
    assert pump.execution.gone


def test_keepalive_absent_callback_is_never_called(
    bridge: Any, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bridge, "KEEPALIVE_S", KEEPALIVE_S)
    sinks = Sinks(keepalive=None)
    pump = build_pump(bridge, [EMPTY], sinks)
    clock.advance(KEEPALIVE_S * 10)
    assert pump.execution.next_event() == ("idle", None)
    assert sinks.keepalives == 0
    assert not pump.execution.gone


def test_next_event_returns_queued_event_without_keepalive(
    bridge: Any, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bridge, "KEEPALIVE_S", KEEPALIVE_S)
    sinks = Sinks(keepalive=True)
    pump = build_pump(bridge, [("text", "hi")], sinks)
    clock.advance(KEEPALIVE_S * 10)
    assert pump.execution.next_event() == ("text", "hi")
    assert sinks.keepalives == 0
