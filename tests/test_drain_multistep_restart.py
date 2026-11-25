"""E2E tests for multi-step turns across graceful drain and restart (AD-005/AD-002/VER-006)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
import gc
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import signal
import stat
import threading
from typing import Any, cast

import pytest

from core.drain_policy import is_drain_policy_enabled
from core.drain_response import DEFAULT_DRAIN_MESSAGE, build_drain_sse_error
from core.lifecycle import DrainState, HubLifecycleManager, QoSSlotManager

pytestmark = pytest.mark.drain
_HttpResp = tuple[int, dict[str, str], bytes]


def _socket_fds() -> frozenset[int]:
    """Return currently open socket file descriptors of the process."""
    for root in ("/dev/fd", "/proc/self/fd"):
        if not os.path.isdir(root):
            continue
        handle = os.open(root, os.O_RDONLY)
        try:
            fds = frozenset(int(n) for n in os.listdir(handle)) - {handle}
        finally:
            os.close(handle)
        return frozenset(fd for fd in fds if _is_sock(fd))
    return frozenset()


def _is_sock(fd: int) -> bool:
    try:
        return stat.S_ISSOCK(os.fstat(fd).st_mode)
    except OSError:
        return False


def _http_request(port: int, method: str, path: str, payload: dict[str, Any] | None = None) -> _HttpResp:
    """Perform a single loopback HTTP request with explicit connection close."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else b""
    headers = {"Connection": "close", **({"Content-Type": "application/json"} if payload is not None else {})}
    conn = HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


def _spawn_post(port: int, payload: dict[str, Any], name: str) -> tuple[threading.Thread, list[_HttpResp]]:
    box: list[_HttpResp] = []
    thread = threading.Thread(
        target=lambda: box.append(_http_request(port, "POST", "/v1/chat/completions", payload)), name=name
    )
    thread.start()
    return thread, box


@dataclass
class _BridgeHarness:
    port: int
    lifecycle: HubLifecycleManager
    active_turns: set[str] = field(default_factory=set)
    turns_lock: threading.Lock = field(default_factory=threading.Lock)
    step1_started: threading.Event = field(default_factory=threading.Event)
    step1_release: threading.Event = field(default_factory=threading.Event)
    sse_headers_sent: threading.Event = field(default_factory=threading.Event)
    qos: QoSSlotManager | None = None


class _DrainHTTPServer(ThreadingHTTPServer):
    allow_reuse_address: bool = True
    daemon_threads: bool = False
    block_on_close: bool = True
    harness: _BridgeHarness


class _DrainE2EHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _harness(self) -> _BridgeHarness:
        return cast(_DrainHTTPServer, self.server).harness

    def _send_json(self, status: int, payload: dict[str, Any], extra: dict[str, str] | None = None) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.close_connection = True
        self.send_response(status)
        hdrs = {"Content-Type": "application/json", "Content-Length": str(len(raw)), "Connection": "close"}
        for key, value in (hdrs | (extra or {})).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send_json(404, {"error": "not_found"})
            return
        life = self._harness().lifecycle
        self._send_json(200, {"ok": not life.is_draining()}, life.health_headers())

    def _handle_sse_qos(self, body: dict[str, Any]) -> None:
        harness = self._harness()
        assert harness.qos is not None
        sent = False

        def _send_ka() -> bool:
            nonlocal sent
            if not sent:
                self.close_connection = True
                self.send_response(200)
                for k, v in (("Content-Type", "text/event-stream; charset=utf-8"), ("Connection", "close")):
                    self.send_header(k, v)
                self.end_headers()
                sent = True
            self.wfile.write(b": keepalive\n\n")
            self.wfile.flush()
            harness.sse_headers_sent.set()
            return True

        ok, reason = harness.qos.acquire_slot(is_interactive=True, keepalive_cb=_send_ka)
        if not ok and reason == "draining" and sent:
            frame = build_drain_sse_error(os.environ, model=str(body.get("model") or ""), message=DEFAULT_DRAIN_MESSAGE)
            self.wfile.write(frame.encode("utf-8"))
            self.wfile.flush()
            return
        if ok:
            harness.qos.release_slot(is_interactive=True)
        self._send_json(200, {"ok": True})

    def _handle_turn_step(self, body: dict[str, Any]) -> None:
        harness = self._harness()
        turn_id = f"turn-step-{body.get('step', 0)}"
        with harness.turns_lock:
            harness.active_turns.add(turn_id)
        try:
            if body.get("hold"):
                harness.step1_started.set()
                harness.step1_release.wait(timeout=5.0)
            self._send_json(200, {"ok": True, "step": body.get("step")})
        finally:
            with harness.turns_lock:
                harness.active_turns.discard(turn_id)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads((self.rfile.read(length) if length > 0 else b"{}").decode("utf-8"))
        if body.get("sse_qos"):
            self._handle_sse_qos(body)
            return
        life = self._harness().lifecycle
        if not life.accepting() and not life.wait_for_drain_hold(is_subagent=False):
            code, hdrs, err_body = life.draining_response(is_subagent=False)
            self._send_json(code, err_body, hdrs)
            return
        self._handle_turn_step(body)


@contextmanager
def _running_bridge(*, drain_timeout_s: float = 3.0, with_qos: bool = False) -> Iterator[_BridgeHarness]:
    active_turns: set[str] = set()
    turns_lock = threading.Lock()
    lifecycle = HubLifecycleManager(
        active_turns_fn=lambda: len(active_turns), drain_timeout_s=drain_timeout_s, drain_enabled_fn=lambda: True
    )
    qos = QoSSlotManager(1, keepalive_interval_s=0.01, queue_timeout_s=3.0, drain_event=lifecycle.shutdown_requested) if with_qos else None
    srv = _DrainHTTPServer(("127.0.0.1", 0), _DrainE2EHandler)
    lifecycle.attach_server(srv)
    harness = _BridgeHarness(int(srv.server_address[1]), lifecycle, active_turns, turns_lock, qos=qos)
    srv.harness = harness
    thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.02}, name="drain-e2e-http")
    thread.start()
    try:
        yield harness
    finally:
        harness.step1_release.set()
        if thread.is_alive():
            srv.shutdown()
        thread.join(timeout=5.0)
        srv.server_close()


def _assert_drain_503(resp: _HttpResp, *, expected_retry: int | None = None) -> None:
    status, headers, raw_body = resp
    assert status == 503 and headers.get("X-Bridge-Draining") == "true"
    retry_val = int(headers["Retry-After"])
    assert retry_val >= 1 and (expected_retry is None or retry_val == expected_retry)
    assert json.loads(raw_body.decode("utf-8")) == {
        "error": {"message": "bridge is draining for restart", "type": "overloaded", "code": 503}
    }


def _assert_sse_drain_frame(resp: _HttpResp, *, expected_retry: int) -> None:
    status, headers, raw = resp
    assert status == 200 and headers.get("Content-Type", "").startswith("text/event-stream")
    data = [ln.removeprefix("data: ") for ln in raw.decode("utf-8").splitlines() if ln.startswith("data: ")]
    assert len(data) == 2 and data[-1] == "[DONE]"
    err = json.loads(data[0])["error"]
    assert err["code"] == 503 and err["type"] == "overloaded_error"
    assert err["retry_after"] == expected_retry and err["retry_after"] >= 1


def test_multistep_turn_across_graceful_drain_and_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    """In-flight step 1 completes through drain; step 2 gets 503 then 200 after restart."""
    monkeypatch.setenv("BRIDGE_RETRY_AFTER_S", "4")
    monkeypatch.setenv("BRIDGE_DRAIN_HOLD_TIMEOUT_S", "0")
    drain_summary: dict[str, Any] = {}
    with _running_bridge(drain_timeout_s=3.0) as h1:
        t_step1, step1_box = _spawn_post(h1.port, {"step": 1, "hold": True}, "drain-e2e-step1")
        t_drain = threading.Thread(
            target=lambda: drain_summary.update(h1.lifecycle.run_drain_once()), name="drain-e2e-runner"
        )
        try:
            assert h1.step1_started.wait(timeout=5.0)
            h1.lifecycle.handle_signal(signal.SIGTERM, None)
            t_drain.start()
            assert h1.lifecycle.drain_started.wait(timeout=5.0)
            h_code, h_hdrs, _ = _http_request(h1.port, "GET", "/health")
            assert h_code == 200 and h_hdrs.get("X-Bridge-Draining") == "true"
            _assert_drain_503(_http_request(h1.port, "POST", "/v1/chat/completions", {"step": 2}), expected_retry=4)
            h1.step1_release.set()
            t_step1.join(timeout=5.0)
            t_drain.join(timeout=5.0)
            assert step1_box and step1_box[0][0] == 200
            assert json.loads(step1_box[0][2].decode("utf-8")) == {"ok": True, "step": 1}
            assert drain_summary["interrupted_turn_ids"] == []
            assert drain_summary["state"] == DrainState.STOPPED and h1.lifecycle.state == DrainState.STOPPED
            assert h1.lifecycle.accepting() is False and h1.lifecycle.wait_for_drain_hold(is_subagent=False) is False
        finally:
            h1.step1_release.set()
            t_step1.join(timeout=5.0)
            if t_drain.is_alive():
                t_drain.join(timeout=5.0)

    with _running_bridge(drain_timeout_s=3.0) as h2:
        code, _, body = _http_request(h2.port, "POST", "/v1/chat/completions", {"step": 2})
        assert code == 200 and json.loads(body.decode("utf-8")) == {"ok": True, "step": 2}


def test_qos_sse_already_sent_emits_drain_error_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    """When SSE headers are already sent in QoS wait, drain emits SSE error + [DONE]."""
    monkeypatch.setenv("BRIDGE_RETRY_AFTER_S", "6")
    monkeypatch.setenv("BRIDGE_DRAIN_QOS_GRACE_S", "0")
    with _running_bridge(drain_timeout_s=3.0, with_qos=True) as harness:
        assert harness.qos is not None
        assert harness.qos.acquire_slot(is_interactive=True)[0]
        slot_held = True
        t_sse, sse_box = _spawn_post(harness.port, {"model": "sse-drain-model", "stream": True, "sse_qos": True}, "drain-e2e-sse")
        try:
            assert harness.sse_headers_sent.wait(timeout=5.0)
            harness.lifecycle.handle_signal(signal.SIGTERM, None)
            harness.qos.release_slot(is_interactive=True)
            slot_held = False
            t_sse.join(timeout=5.0)
            assert len(sse_box) == 1
            _assert_sse_drain_frame(sse_box[0], expected_retry=6)
        finally:
            if slot_held:
                harness.qos.release_slot(is_interactive=True)
            t_sse.join(timeout=5.0)


def test_drain_kill_switch_and_resource_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """BRIDGE_DRAIN_POLICY_ENABLED=0 keeps Retry-After >= 1 and leaves zero leaked resources."""
    gc.collect()
    base_threads, base_sockets = frozenset(threading.enumerate()), _socket_fds()
    monkeypatch.setenv("BRIDGE_DRAIN_POLICY_ENABLED", "0")
    monkeypatch.setenv("BRIDGE_RETRY_AFTER_S", "0")
    assert is_drain_policy_enabled(os.environ) is False

    with _running_bridge(drain_timeout_s=2.0) as harness:
        harness.lifecycle.handle_signal(signal.SIGTERM, None)
        _assert_drain_503(_http_request(harness.port, "POST", "/v1/chat/completions", {"step": 1}))
        monkeypatch.delenv("BRIDGE_RETRY_AFTER_S", raising=False)
        _assert_drain_503(_http_request(harness.port, "POST", "/v1/chat/completions", {"step": 2}))
        sse_frame = build_drain_sse_error(os.environ, model="ks-model")
        assert sse_frame.endswith("\n\ndata: [DONE]\n\n")
        err = json.loads(sse_frame.split("\n\n", 1)[0].removeprefix("data: "))["error"]
        assert err["code"] == 503 and err["retry_after"] >= 1

    gc.collect()
    assert [t.name for t in threading.enumerate() if t not in base_threads and t.is_alive()] == []
    assert (_socket_fds() - base_sockets) == frozenset()
