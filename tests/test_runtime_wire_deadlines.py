"""Zero-I/O fake-clock tests for runtime_wire _TurnDeadlines integration and NFR replay."""

from __future__ import annotations

import socket
import subprocess
from types import SimpleNamespace

import pytest

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_io import TIMEOUT
from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.runtime_types import TurnTimeoutError as WireTurnTimeoutError
from core.stdio_resident.runtime_wire import _stream_plain, build_turn_deadlines
from core.stdio_resident.turn_deadlines import TurnTimeoutError as DeadlineTurnTimeoutError


class _FakeDriver:
    def decode_line(self, line: str) -> DecodedChunk | None:
        if line == "KEEPALIVE":
            return DecodedChunk(text="")
        if line == "DONE":
            return DecodedChunk(text="ok", is_terminal=True)
        return DecodedChunk(text=line)

    def is_terminal(self, line: str, _decoded: DecodedChunk | None) -> bool:
        return line == "DONE"


class _FakeClockHandle:
    def __init__(self, events: list[tuple[float, str, object]]) -> None:
        self._events = list(events)
        self.now = 0.0

    def read_line_outcome(self, timeout_s: float):
        if not self._events:
            self.now += timeout_s
            return TIMEOUT, None
        dt, kind, line = self._events[0]
        if dt >= timeout_s:
            self._events[0] = (dt - timeout_s, kind, line)
            self.now += timeout_s
            return TIMEOUT, None
        self._events.pop(0)
        self.now += dt
        if kind == "STDERR":
            return "LINE", SimpleNamespace(is_stderr=True, line=line)
        return "LINE", SimpleNamespace(is_stderr=False, line=line)


def _forbid_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a, **_kw):
        raise AssertionError("network/subprocess I/O is forbidden in T-ISO tests")

    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)


def test_keepalive_and_empty_never_reset_deadline_or_satisfy_first_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid_io(monkeypatch)
    dl = build_turn_deadlines(StdioPoolConfig(), {}, now=0.0, environ={})
    handle = _FakeClockHandle([
        (300.0, "LINE", "KEEPALIVE"),
        (300.0, "STDERR", "heartbeat"),
        (200.0, "LINE", "DONE"),
    ])
    with pytest.raises(DeadlineTurnTimeoutError) as exc_info:
        list(_stream_plain(_FakeDriver(), handle, {}, dl, now_fn=lambda: handle.now))
    assert exc_info.value.code == "first_progress_timeout"
    assert dl.has_progress is False


def test_nfr_231_sample_replay_zero_turn_timeouts_at_max_541_8s(monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid_io(monkeypatch)
    # Representative 231-sample latency distribution matching NFR (min=8.8s, p50=99.6s, p95=363.1s, max=541.8s)
    samples = [8.8 + (541.8 - 8.8) * (i / 230.0) for i in range(231)]
    samples[230] = 541.8
    timeouts = 0
    for latency in samples:
        dl = build_turn_deadlines(StdioPoolConfig(), {}, now=0.0, environ={})
        handle = _FakeClockHandle([(latency, "LINE", "DONE")])
        chunks = list(_stream_plain(_FakeDriver(), handle, {}, dl, now_fn=lambda h=handle: h.now))
        if not any(c.is_terminal for c in chunks):
            timeouts += 1
    assert timeouts == 0


def test_first_progress_601_survives_720_721_fail_and_float_backcompat(monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid_io(monkeypatch)
    dl_ok = build_turn_deadlines(StdioPoolConfig(), {}, now=0.0, environ={})
    h_601 = _FakeClockHandle([(601.0, "LINE", "DONE")])
    chunks = list(_stream_plain(_FakeDriver(), h_601, {}, dl_ok, now_fn=lambda: h_601.now))
    assert chunks[-1].text == "ok"

    for t in (720.0, 721.0):
        dl_fail = build_turn_deadlines(StdioPoolConfig(), {}, now=0.0, environ={})
        h_fail = _FakeClockHandle([(t, "LINE", "DONE")])
        with pytest.raises(DeadlineTurnTimeoutError):
            list(_stream_plain(_FakeDriver(), h_fail, {}, dl_fail, now_fn=lambda h=h_fail: h.now))

    # Float backward compatibility raises WireTurnTimeoutError (504)
    h_float = _FakeClockHandle([(50.0, "LINE", "DONE")])
    with pytest.raises(WireTurnTimeoutError) as exc_float:
        list(_stream_plain(_FakeDriver(), h_float, {}, 10.0, now_fn=lambda: h_float.now))
    assert exc_float.value.http_status == 504
