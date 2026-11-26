"""Runtime-оракулы phase-idle admission, TTL и наблюдаемости на ephemeral loopback."""

from __future__ import annotations

import contextlib
import http.client
import importlib.util
import json
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.strict_leak_check

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import bridge_io_config, http_accept  # noqa: E402

# fmt: off
# Плотные runtime-сценарии: форматтер не должен раздувать файл сверх лимита M-MOD-I1.


@pytest.fixture
def srv(monkeypatch):
    import server
    logs: list[str] = []
    monkeypatch.setattr(server, "_log", logs.append)
    return server, logs


@contextlib.contextmanager
def _live(server):
    httpd = server.Server(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _budget(limit):
    return bridge_io_config.AdmissionBudget(
        bridge_io_config.BridgeIOConfig(admission_limit=limit, ui_reserve=0, header_headroom=0))


def _get(port, path, timeout=2.0):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_phase_idle_eviction_frees_ticket(srv, monkeypatch) -> None:
    server, _logs = srv
    monkeypatch.setenv("BRIDGE_HTTP_IDLE_ADMISSION_TIMEOUT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_HTTP_PHASE_IDLE_TIMEOUT_S", "0.05")

    def fake_get(self):
        self._trace = None
        self._send(200, {"ok": True})

    monkeypatch.setattr(server.Handler, "do_GET", fake_get)
    with _live(server) as httpd:
        httpd._admission_budget = _budget(2)
        port = httpd.server_address[1]
        a = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        b = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            for conn in (a, b):
                conn.request("GET", "/fast")
                resp = conn.getresponse()
                assert resp.status == 200
                resp.read()
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline and httpd.admission_snapshot()["total"] != 0:
                time.sleep(0.02)
            assert httpd.admission_snapshot()["total"] == 0
            assert a.sock.recv(1) == b""
            status, _body = _get(port, "/fast")
            assert status == 200
        finally:
            a.close()
            b.close()


def test_slow_active_sse_preserved(srv, monkeypatch) -> None:
    server, _logs = srv
    monkeypatch.setenv("BRIDGE_HTTP_IDLE_ADMISSION_TIMEOUT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_HTTP_PHASE_IDLE_TIMEOUT_S", "0.05")

    def fake_get(self):
        self._trace = None
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(3):
            time.sleep(0.08)
            self.wfile.write(("data: chunk%d\n\n" % i).encode())
            self.wfile.flush()
        self.close_connection = True

    monkeypatch.setattr(server.Handler, "do_GET", fake_get)
    with _live(server) as httpd:
        port = httpd.server_address[1]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            conn.request("GET", "/slow")
            resp = conn.getresponse()
            body = resp.read().decode()
            assert resp.status == 200
            assert "chunk0" in body and "chunk2" in body
        finally:
            conn.close()


def test_overloaded_503_telemetry_log(srv, monkeypatch) -> None:
    server, logs = srv
    monkeypatch.setenv("BRIDGE_ADMISSION_TELEMETRY_ENABLED", "1")
    with _live(server) as httpd:
        httpd._admission_budget = _budget(1)
        assert httpd._admission_budget.acquire("occupied")
        port = httpd.server_address[1]
        status, body = _get(port, "/fast")
        assert status == 503 and b"bridge overloaded: connection limit" in body
    assert any("reject reason=overloaded" in x and "max_idle_age_s=" in x for x in logs)
    assert httpd._overloaded_rejects >= 1


def test_legacy_knob_warning_emit(monkeypatch) -> None:
    logs: list[str] = []
    monkeypatch.setenv("BRIDGE_MAX_HTTP_CONNECTIONS", "1024")
    assert http_accept.emit_legacy_knob_warning(logs.append, 128) is True
    assert any("legacy_knob_ignored" in x and "effective_limit=128" in x for x in logs)
    monkeypatch.setenv("BRIDGE_MAX_HTTP_CONNECTIONS", "128")
    assert http_accept.emit_legacy_knob_warning(logs.append, 128) is False


def test_drain_started_actor_fields(monkeypatch) -> None:
    from core.lifecycle import HubLifecycleManager
    logs: list[str] = []
    monkeypatch.setenv("BRIDGE_RESTART_ACTOR", "launchd")
    lifecycle = HubLifecycleManager(drain_timeout_s=0.02, log_fn=logs.append)
    lifecycle.handle_signal(signal.SIGTERM)
    lifecycle.run_drain_once()
    line = next(x for x in logs if x.startswith("drain_started"))
    assert "actor=launchd" in line and "pid=" in line and "ppid=" in line and "pgid=" in line


def test_claude_p_done_redacted_stderr(monkeypatch, tmp_path) -> None:
    path = ROOT / "bridges" / "claude-p-bridge" / "server.py"
    spec = importlib.util.spec_from_file_location("claude_p_idle_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    logs: list[str] = []
    monkeypatch.setattr(mod, "_log", logs.append)
    monkeypatch.setenv("BRIDGE_CLAUDE_P_LOG_STDERR_ON_FAIL_ENABLED", "1")
    turn = SimpleNamespace(model="m", effort="high", tag="client=1.2.3.4:5 ua=x")
    out = {"rc": 1, "state": "error", "err": "Bearer sk-secret123\napi_key=abc"}
    mod.Handler._log_turn_done(turn, out, time.monotonic() - 1.0)
    line = logs[-1]
    assert line.startswith("done model=m effort=high rc=1")
    assert "stderr_tail=[REDACTED] [REDACTED]" in line
    assert "sk-secret123" not in line and "\n" not in line
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    (src / ".claude.json").write_text('{"userID": "u1"}', encoding="utf-8")
    mod._sync_ca_files(src, dst)
    assert (dst / ".claude.json").is_file()
    seen: list[Path] = []
    monkeypatch.setattr(http_accept, "load_config", lambda p: seen.append(p) or None)
    http_accept.load_admission_idle_config(env={})
    assert seen and str(seen[0]).endswith("dynamic_config.json")


def test_health_seven_keys(srv, monkeypatch) -> None:
    server, _logs = srv
    fake = SimpleNamespace(adapters=lambda: [], active_total=lambda: 0, max_concurrent_total=lambda: 0)
    monkeypatch.setattr(server, "BACKENDS", fake)
    with _live(server) as httpd:
        port = httpd.server_address[1]
        status, body = _get(port, "/health")
        assert status == 200
        payload = json.loads(body.decode())
        assert set(payload) == {"ok", "transport", "model", "active", "max_concurrent",
                                "tool_emulation", "uptime_s"}


def test_telemetry_serve_get_attaches_admission(monkeypatch) -> None:
    from core.telemetry_hooks import TelemetryHooksMixin
    monkeypatch.setenv("BRIDGE_ADMISSION_TELEMETRY_ENABLED", "1")
    store = SimpleNamespace(get_telemetry_payload=lambda **kw: {"events": []}, recent_limit=10)
    fake_server = SimpleNamespace(admission_snapshot=lambda: {"total": 0, "limit": 128})

    class Host(TelemetryHooksMixin):
        def __init__(self):
            self.server = fake_server
            self.headers = {}
            self.path = "/v1/telemetry"
            self.sent = []

        def _send(self, code, payload, extra_headers=None):
            self.sent.append(payload)

        def _telemetry_srv(self):
            return SimpleNamespace(REQUEST_TELEMETRY=store)

    host = Host()
    host._telemetry_serve_get()
    assert "admission" in host.sent[0] and host.sent[0]["admission"]["limit"] == 128


def test_kill_switch_off_restores_active_timeout(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_HTTP_IDLE_ADMISSION_TIMEOUT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_HTTP_PHASE_IDLE_TIMEOUT_S", "0.05")
    monkeypatch.setenv("BRIDGE_READ_TIMEOUT_S", "4.5")
    with socket.socket() as sock:
        assert http_accept.apply_connection_phase_timeout(sock, "idle") == 0.05
        assert sock.gettimeout() == 0.05
        monkeypatch.setenv("BRIDGE_HTTP_IDLE_ADMISSION_TIMEOUT_ENABLED", "0")
        assert http_accept.apply_connection_phase_timeout(sock, "active") == 4.5
        assert sock.gettimeout() == 4.5


def test_kill_switch_off_restores_default_active_timeout(monkeypatch) -> None:
    monkeypatch.delenv("BRIDGE_READ_TIMEOUT_S", raising=False)
    monkeypatch.delenv("BRIDGE_HTTP_ACTIVE_SOCKET_TIMEOUT_S", raising=False)
    monkeypatch.setenv("BRIDGE_HTTP_IDLE_ADMISSION_TIMEOUT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_HTTP_PHASE_IDLE_TIMEOUT_S", "0.05")
    with socket.socket() as sock:
        assert http_accept.apply_connection_phase_timeout(sock, "idle") == 0.05
        monkeypatch.setenv("BRIDGE_HTTP_IDLE_ADMISSION_TIMEOUT_ENABLED", "0")
        assert http_accept.apply_connection_phase_timeout(sock, "active") == 3600.0
        assert sock.gettimeout() == 3600.0
        assert http_accept.apply_connection_phase_timeout(sock, "active") is None


def test_phase_edges_closing_and_signal_zero(srv, monkeypatch) -> None:
    from core.admission_idle_policy import sanitize_stderr_tail, summarize_admission_snapshot
    from core.lifecycle import HubLifecycleManager
    assert http_accept.apply_connection_phase_timeout(None, "idle") is None
    assert sanitize_stderr_tail("ab", 1) == "...b"
    assert summarize_admission_snapshot({"c": (False, float("-inf"))}, 1.0, 1, 0)["max_idle_age_s"] == 0.0
    tracker = http_accept.ConnectionTracker()
    with socket.socket() as sock:
        tracker.close_idle()
        assert tracker.set_active(sock, True) is False
    logs: list[str] = []
    monkeypatch.setenv("BRIDGE_EXIT_TIMEOUT_S", "20.0")
    HubLifecycleManager(drain_timeout_s=30.0, log_fn=logs.append).run_drain_once()
    line = next(x for x in logs if x.startswith("drain_started"))
    assert "signal=0" in line and "clamped=true" in line
    server, _slogs = srv
    called: list[bool] = []
    monkeypatch.setattr(server.BaseHTTPRequestHandler, "parse_request", lambda self: False)
    h = server.Handler.__new__(server.Handler)
    h.connection = None
    h.server = SimpleNamespace(set_connection_active=lambda _c, a: called.append(a) or True)
    assert h.parse_request() is False and called == []
    monkeypatch.setattr(server.BaseHTTPRequestHandler, "parse_request", lambda self: True)
    assert h.parse_request() is True and called == [True]
    h.server = SimpleNamespace()
    assert h.parse_request() is True
