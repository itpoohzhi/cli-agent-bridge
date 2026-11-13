from itertools import chain, repeat
from http.client import HTTPConnection
import json
import os
import sys
import threading
import time
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import pytest
import server

from core.backend_adapter import TurnResult
from core.lifecycle import (
    DEFAULT_DRAIN_SECONDS,
    DrainState,
    HubLifecycleManager,
    KeepaliveController,
)
from core.turn_session_manager import ManagedTurn, TurnSessionManager


class GracefulShutdownDrainTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._state_dir = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_signal_handler_only_sets_event_and_admission_returns_503(self) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        lifecycle = HubLifecycleManager(
            state_dir=self._state_dir,
            turn_manager=manager,
            drain_timeout_s=2.0,
            retry_after_s=5,
        )
        self.assertFalse(lifecycle.is_draining())

        lifecycle.handle_signal(signal.SIGTERM, None)
        self.assertTrue(lifecycle.shutdown_requested.is_set())
        self.assertTrue(lifecycle.is_draining())

        code, headers, body = lifecycle.draining_response()
        self.assertEqual(code, 503)
        self.assertEqual(headers.get("Retry-After"), "5")
        self.assertEqual(headers.get("X-Bridge-Draining"), "true")
        self.assertEqual(body["error"]["code"], 503)
        self.assertEqual(body["error"]["type"], "overloaded")
        self.assertEqual(lifecycle.health_headers().get("X-Bridge-Draining"), "true")

    def test_drain_waits_for_active_turn_and_persists_interrupted_on_timeout(
        self,
    ) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        turn, _ = manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "long-turn"}],
            session_id="sess-drain",
            owner_token_hash="owner-1",
            requested_turn_id="turn-drain-01",
            stream=True,
        )
        turn.buffer.append("content", "partial output")

        lifecycle = HubLifecycleManager(
            state_dir=self._state_dir,
            turn_manager=manager,
            drain_timeout_s=0.1,
            retry_after_s=5,
        )
        lifecycle.handle_signal(signal.SIGTERM, None)
        summary = lifecycle.run_drain_once()

        self.assertEqual(lifecycle.state, DrainState.STOPPED)
        self.assertIn("turn-drain-01", summary["interrupted_turn_ids"])

        snap = manager.get_turn_snapshot("turn-drain-01", owner_token_hash="owner-1")
        self.assertEqual(snap["status"], "interrupted_drain")
        self.assertEqual(snap["content"], "partial output")
        self.assertEqual(snap["error"]["code"], "drain_timeout")

    def test_drain_waits_for_active_turns_fn_even_when_turn_manager_is_idle(
        self,
    ) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        active_turns_fn = Mock(side_effect=[1, 1, 0])
        logs: list[str] = []
        lifecycle = HubLifecycleManager(
            state_dir=self._state_dir,
            turn_manager=manager,
            active_turns_fn=active_turns_fn,
            drain_timeout_s=1.0,
            drain_enabled_fn=lambda: True,
            log_fn=logs.append,
        )
        server = Mock()
        shutdown_active_checks: list[int] = []
        server.shutdown.side_effect = lambda: shutdown_active_checks.append(
            active_turns_fn.call_count
        )
        lifecycle.attach_server(server)
        self.assertEqual(manager.active_count(), 0)

        with (
            patch("core.lifecycle.time.monotonic", return_value=0.0),
            patch("core.lifecycle.time.sleep") as sleep,
        ):
            summary = lifecycle.run_drain_once()

        sleep.assert_called_once_with(0.05)
        server.shutdown.assert_called_once_with()
        self.assertEqual(shutdown_active_checks, [3])
        self.assertEqual(active_turns_fn.call_count, 3)
        self.assertEqual(summary["active_turns_before"], 1)
        self.assertEqual(summary["interrupted_turn_ids"], [])
        self.assertEqual(summary["state"], DrainState.STOPPED)
        self.assertTrue(lifecycle.drain_completed.is_set())
        self.assertIn("active_turns=1", logs[0])

    def test_drain_timeout_active_turns_fn(self) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        active_turns_fn = Mock(return_value=1)
        elapsed_s = 0.0

        def advance_time(seconds: float) -> None:
            nonlocal elapsed_s
            elapsed_s += seconds

        lifecycle = HubLifecycleManager(
            state_dir=self._state_dir,
            turn_manager=manager,
            active_turns_fn=active_turns_fn,
            drain_timeout_s=0.1,
            drain_enabled_fn=lambda: True,
        )
        server = Mock()
        shutdown_times: list[float] = []
        server.shutdown.side_effect = lambda: shutdown_times.append(elapsed_s)
        lifecycle.attach_server(server)

        with (
            patch("core.lifecycle.time.monotonic", side_effect=lambda: elapsed_s),
            patch("core.lifecycle.time.sleep", side_effect=advance_time) as sleep,
        ):
            summary = lifecycle.run_drain_once()

        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(active_turns_fn.call_count, 3)
        self.assertEqual(shutdown_times, [0.1])
        server.shutdown.assert_called_once_with()
        self.assertEqual(summary["active_turns_before"], 1)
        self.assertEqual(summary["interrupted_turn_ids"], [])
        self.assertEqual(summary["state"], DrainState.STOPPED)
        self.assertTrue(lifecycle.drain_completed.is_set())

    def test_drain_safe_active_count_handles_exception(self) -> None:
        for counts in (
            [RuntimeError("counter unavailable")],
            [3, RuntimeError("counter unavailable")],
        ):
            with self.subTest(counts=counts):
                active_turns_fn = Mock(
                    side_effect=chain(
                        counts, repeat(RuntimeError("counter unavailable"))
                    )
                )
                elapsed_s = 0.0

                def advance_time(seconds: float) -> None:
                    nonlocal elapsed_s
                    elapsed_s += seconds

                logs: list[str] = []
                on_complete = Mock()
                lifecycle = HubLifecycleManager(
                    state_dir=self._state_dir,
                    active_turns_fn=active_turns_fn,
                    drain_timeout_s=0.1,
                    drain_enabled_fn=lambda: True,
                    log_fn=logs.append,
                    on_shutdown_complete=on_complete,
                )
                server = Mock()
                shutdown_times: list[float] = []
                server.shutdown.side_effect = lambda: shutdown_times.append(elapsed_s)
                lifecycle.attach_server(server)

                with (
                    patch(
                        "core.lifecycle.time.monotonic", side_effect=lambda: elapsed_s
                    ),
                    patch(
                        "core.lifecycle.time.sleep", side_effect=advance_time
                    ) as sleep,
                ):
                    summary = lifecycle.run_drain_once()

                self.assertEqual(sleep.call_count, 2)
                self.assertEqual(shutdown_times, [0.1])
                self.assertEqual(summary["state"], DrainState.STOPPED)
                self.assertEqual(
                    summary["active_turns_before"],
                    1 if isinstance(counts[0], Exception) else 3,
                )
                self.assertEqual(
                    lifecycle._safe_active_count(), summary["active_turns_before"]
                )
                self.assertTrue(lifecycle.drain_completed.is_set())
                self.assertTrue(
                    any("drain_active_count_error" in line for line in logs)
                )
                server.shutdown.assert_called_once_with()
                on_complete.assert_called_once_with()

    def test_drain_finally_guarantees_stopped_state_on_server_shutdown_error(
        self,
    ) -> None:
        lifecycle = HubLifecycleManager(state_dir=self._state_dir)
        server = Mock()
        # Exception уже подавляется; SystemExit проверяет выполнение finally.
        server.shutdown.side_effect = SystemExit("shutdown failed")
        lifecycle.attach_server(server)

        with self.assertRaisesRegex(SystemExit, "shutdown failed"):
            lifecycle.run_drain_once()

        server.shutdown.assert_called_once_with()
        self.assertEqual(lifecycle.state, DrainState.STOPPED)
        self.assertTrue(lifecycle.drain_completed.is_set())

    def test_drain_finally_guarantees_stopped_state_on_wait_error(self) -> None:
        manager = Mock(spec=TurnSessionManager)
        manager.active_count.return_value = 1
        manager.wait_for_active_turns.side_effect = RuntimeError("wait failed")
        lifecycle = HubLifecycleManager(
            state_dir=self._state_dir,
            turn_manager=manager,
            drain_enabled_fn=lambda: True,
        )

        with self.assertRaisesRegex(RuntimeError, "wait failed"):
            lifecycle.run_drain_once()

        self.assertEqual(lifecycle.state, DrainState.STOPPED)
        self.assertTrue(lifecycle.drain_completed.is_set())

    def test_drain_mixed_activity_waits_for_both(self) -> None:
        import server

        manager = TurnSessionManager(state_root=self._state_dir)
        turn, _ = manager.create_or_attach_turn(
            model="test-model",
            backend="test-backend",
            cwd=self._state_dir,
            messages=[{"role": "user", "content": "mixed activity"}],
            session_id="sess-mixed-drain",
            owner_token_hash="owner-mixed",
            requested_turn_id="turn-mixed-drain",
            stream=True,
        )
        backends = Mock()
        backends.active_total.return_value = 2
        events: list[str] = []
        wait_for_active_turns = manager.wait_for_active_turns

        def complete_managed_turn(timeout: float) -> list[ManagedTurn]:
            self.assertEqual(manager.active_count(), 1)
            self.assertEqual(backends.active_total(), 2)
            manager.complete_turn_from_result(turn, TurnResult(text="done"))
            events.append("managed_complete")
            return wait_for_active_turns(timeout)

        def complete_stream(_seconds: float) -> None:
            self.assertEqual(manager.active_count(), 0)
            backends.active_total.return_value = 0
            events.append("stream_complete")

        lifecycle = HubLifecycleManager(
            state_dir=self._state_dir,
            turn_manager=manager,
            active_turns_fn=server._active_turn_count,
            drain_timeout_s=1.0,
            drain_enabled_fn=lambda: True,
            on_shutdown_complete=lambda: events.append("complete"),
        )
        http_server = Mock()
        http_server.shutdown.side_effect = lambda: events.append("shutdown")
        lifecycle.attach_server(http_server)

        with (
            patch.object(server, "BACKENDS", backends),
            patch.object(server, "TURN_MANAGER", manager),
            patch.object(
                manager, "wait_for_active_turns", side_effect=complete_managed_turn
            ),
            patch("core.lifecycle.time.monotonic", return_value=0.0),
            patch("core.lifecycle.time.sleep", side_effect=complete_stream) as sleep,
        ):
            summary = lifecycle.run_drain_once()

        self.assertEqual(summary["active_turns_before"], 2)
        self.assertEqual(
            events, ["managed_complete", "stream_complete", "shutdown", "complete"]
        )
        self.assertEqual(summary["interrupted_turn_ids"], [])
        self.assertEqual(summary["state"], DrainState.STOPPED)
        self.assertTrue(lifecycle.drain_completed.is_set())
        sleep.assert_called_once_with(0.05)

    def test_keepalive_clamped_to_10s(self) -> None:
        ka = KeepaliveController(max_interval_s=10.0)
        self.assertEqual(ka.effective_interval(15.0), 10.0)
        self.assertEqual(ka.effective_interval(5.0), 5.0)
        self.assertTrue(ka.sse_comment().startswith(": keepalive"))


@pytest.mark.parametrize("reaper", ["registry", "lifecycle"])
@pytest.mark.parametrize("stored_parent", [True, False])
def test_rework_preserves_children_of_live_parent(
    tmp_path, monkeypatch, reaper, stored_parent
):
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True
    )
    entry = {
        "pid": proc.pid,
        "pgid": proc.pid,
        "start": server._proc_start_sig(proc.pid),
        "command": "python",
    }
    if stored_parent:
        entry["bridge_pid"] = os.getpid()
    children = tmp_path / "children.json"
    children.write_text(json.dumps([entry]))
    monkeypatch.setattr(server, "_children_path", lambda: children)
    try:
        with patch("os.killpg") as killpg:
            if reaper == "registry":
                assert server.reconcile_children() == 0
            else:
                lifecycle = HubLifecycleManager(state_dir=tmp_path, orphan_grace_s=0.05)
                assert lifecycle.reap_startup_orphans() == []
            assert all(call.args[1] == 0 for call in killpg.call_args_list)
        assert proc.poll() is None
        payload = json.loads(children.read_text())
        assert payload == [entry] or payload.get("children") == [entry]
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_rework_releases_writer_lock_explicitly(monkeypatch):
    lock = Mock()
    monkeypatch.setattr(server, "_ACTIVE_WRITER_LOCK", lock)
    calls = []
    lock.close.side_effect = lambda: calls.append("close")
    with patch("server.fcntl.flock", side_effect=lambda f, op: calls.append(op)):
        server.release_writer_lock()
        server.release_writer_lock()
    assert calls == [server.fcntl.LOCK_UN, "close"]


def test_rework_releases_writer_lock_on_drain_start(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_state_dir", lambda: tmp_path)
    writer_lock = server.acquire_writer_lock()
    assert writer_lock is not None
    monkeypatch.setattr(server, "_ACTIVE_WRITER_LOCK", writer_lock)
    assert server.acquire_writer_lock() is None
    manager = TurnSessionManager(state_root=tmp_path)
    turn, _ = manager.create_or_attach_turn(
        model="test-model",
        backend="test-backend",
        cwd=str(tmp_path),
        messages=[{"role": "user", "content": "active during handoff"}],
        session_id="sess-lock-handoff",
        owner_token_hash="owner-handoff",
        requested_turn_id="turn-lock-handoff",
        stream=True,
    )
    waiting = threading.Event()
    acquired = threading.Event()
    next_locks = []
    summaries = []
    errors = []
    wait_for_active_turns = manager.wait_for_active_turns

    def wait_for_turns(timeout):
        waiting.set()
        return wait_for_active_turns(timeout)

    monkeypatch.setattr(manager, "wait_for_active_turns", wait_for_turns)
    lifecycle = HubLifecycleManager(
        state_dir=tmp_path,
        turn_manager=manager,
        drain_timeout_s=5.0,
        drain_enabled_fn=lambda: True,
        on_drain_start_fn=server.release_writer_lock,
    )

    def drain():
        try:
            summaries.append(lifecycle.run_drain_once())
        except BaseException as exc:
            errors.append(exc)

    def acquire_next_lock():
        try:
            next_locks.append(server.acquire_writer_lock())
        finally:
            acquired.set()

    draining = threading.Thread(target=drain, daemon=True)
    acquiring = threading.Thread(target=acquire_next_lock, daemon=True)
    try:
        draining.start()
        assert waiting.wait(2)
        assert lifecycle.state == DrainState.DRAINING
        assert lifecycle.drain_started.is_set()
        acquiring.start()
        assert acquired.wait(2)
        assert next_locks and next_locks[0] is not None
        assert writer_lock.closed
        assert manager.active_count() == 1
        assert not lifecycle.drain_completed.is_set()
        assert draining.is_alive()
        manager.complete_turn_from_result(turn, TurnResult(text="done"))
        draining.join(2)
        assert not draining.is_alive()
        assert errors == []
        assert summaries[0]["interrupted_turn_ids"] == []
        assert summaries[0]["state"] == DrainState.STOPPED
    finally:
        if manager.active_count():
            manager.complete_turn_from_result(turn, TurnResult(text="cleanup"))
        if draining.ident is not None:
            draining.join(2)
        if acquiring.ident is not None:
            acquiring.join(2)
        for handle in next_locks:
            if handle is not None:
                handle.close()
        server.release_writer_lock()


def test_rework_server_wires_drain_start_callback():
    assert server.LIFECYCLE._on_drain_start_fn is server.release_writer_lock


def test_rework_drain_start_callback_is_once_and_finalized_on_error(tmp_path):
    callback = Mock(side_effect=RuntimeError("handoff failed"))
    lifecycle = HubLifecycleManager(state_dir=tmp_path, on_drain_start_fn=callback)
    with pytest.raises(RuntimeError, match="handoff failed"):
        lifecycle.run_drain_once()
    assert lifecycle.state == DrainState.STOPPED
    assert lifecycle.drain_completed.is_set()
    lifecycle.run_drain_once()
    callback.assert_called_once_with()


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, DEFAULT_DRAIN_SECONDS),
        ("", DEFAULT_DRAIN_SECONDS),
        ("  ", DEFAULT_DRAIN_SECONDS),
        (" 12.5 ", 12.5),
        ("0.01", 0.01),
        ("1e2", 100.0),
        ("bad", DEFAULT_DRAIN_SECONDS),
        ("0", DEFAULT_DRAIN_SECONDS),
        ("-1", DEFAULT_DRAIN_SECONDS),
        ("nan", DEFAULT_DRAIN_SECONDS),
        ("inf", DEFAULT_DRAIN_SECONDS),
        ("-inf", DEFAULT_DRAIN_SECONDS),
    ],
)
def test_drain_timeout_env_config(tmp_path, monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("BRIDGE_DRAIN_TIMEOUT_S", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_DRAIN_TIMEOUT_S", value)
    assert server._configured_drain_timeout_s() == expected
    assert HubLifecycleManager(state_dir=tmp_path).drain_timeout_s == expected
    assert (
        HubLifecycleManager(state_dir=tmp_path, drain_timeout_s=None).drain_timeout_s
        == expected
    )
    assert (
        HubLifecycleManager(state_dir=tmp_path, drain_timeout_s=0.25).drain_timeout_s
        == 0.25
    )


@pytest.mark.parametrize(
    "path", ["prompt-test.txt", "muse/prompt-test.txt", "muse/turn-test", "img-test"]
)
def test_rework_drain_cleanup_preserves_fresh_workspace(tmp_path, monkeypatch, path):
    monkeypatch.setattr(server, "WORKSPACE", tmp_path)
    monkeypatch.setattr(server, "TURN_MANAGER", Mock())
    monkeypatch.setattr(server, "BACKENDS", Mock())
    monkeypatch.setattr(server, "shutdown_all", Mock())
    fresh = tmp_path / path
    old = fresh.with_name(fresh.name + "-old")
    fresh.parent.mkdir(parents=True, exist_ok=True)
    if path.endswith(".txt"):
        old = fresh.with_name(fresh.stem + "-old.txt")
        fresh.write_text("active")
        old.write_text("stale")
    else:
        fresh.mkdir()
        old.mkdir()
    now = time.time()
    os.utime(fresh, (now - 1, now - 1))
    os.utime(old, (now - 120, now - 120))
    server._force_kill_all_on_drain()
    assert fresh.exists()
    assert not old.exists()


@pytest.mark.parametrize("streaming", [False, True])
def test_rework_sigterm_http_and_idle_exit(tmp_path, streaming):
    code = r"""
import signal, threading, time
import server
from core.lifecycle import HubLifecycleManager
active = threading.Event()
lifecycle = HubLifecycleManager(active_turns_fn=lambda: int(active.is_set()), drain_timeout_s=2, drain_enabled_fn=lambda: True)
server.LIFECYCLE = lifecycle
server._auth_ok = lambda _handler: True
class Handler(server.Handler):
    def do_GET(self):
        if self.path != '/stream':
            return super().do_GET()
        active.set()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        self.wfile.write(b'data: partial\n\n')
        self.wfile.flush()
        lifecycle.shutdown_requested.wait(5)
        threading.Event().wait(0.7)
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()
        active.clear()
srv = server.Server(('127.0.0.1', 0), Handler)
lifecycle.attach_server(srv)
lifecycle.install_signal_handlers()
print(srv.server_address[1], flush=True)
try:
    srv.serve_forever(poll_interval=0.01)
finally:
    srv.server_close()
lifecycle.drain_completed.wait(3)
"""
    proc = subprocess.Popen(
        [sys.executable, "-u", "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    idle = stream = None
    try:
        port = int(proc.stdout.readline())
        idle = HTTPConnection("127.0.0.1", port, timeout=3)
        idle.request("GET", "/health")
        assert idle.getresponse().read()
        if streaming:
            stream = HTTPConnection("127.0.0.1", port, timeout=3)
            stream.request("GET", "/stream")
            response = stream.getresponse()
            assert response.read(len(b"data: partial\n\n")) == b"data: partial\n\n"
        started = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        if streaming:
            # Синхронизация по HTTP-признаку drain на новом TCP-соединении.
            deadline = time.monotonic() + 0.5
            while True:
                health = HTTPConnection("127.0.0.1", port, timeout=1)
                health.request("GET", "/health")
                reply = health.getresponse()
                assert reply.status == 200
                draining = reply.getheader("X-Bridge-Draining")
                reply.read()
                health.close()
                if draining:
                    break
                assert time.monotonic() < deadline
            client = HTTPConnection("127.0.0.1", port, timeout=1)
            client.request("POST", "/v1/chat/completions", body="{}")
            rejected = client.getresponse()
            assert rejected.status == 503
            assert rejected.getheader("Retry-After")
            rejected.read()
            client.close()
            assert response.read(len(b"data: [DONE]\n\n")) == b"data: [DONE]\n\n"
        proc.wait(timeout=3)
        assert proc.returncode == 0
        elapsed = time.monotonic() - started
        assert elapsed < 3
        print(f"streaming={streaming} shutdown_elapsed_s={elapsed:.3f} rc={proc.returncode}")
        idle.sock.settimeout(1)
        assert idle.sock.recv(1) == b""
    finally:
        if idle:
            idle.close()
        if stream:
            stream.close()
        if proc.poll() is None:
            proc.kill()
        proc.communicate(timeout=3)


@pytest.mark.parametrize("reaper", ["registry", "lifecycle"])
@pytest.mark.parametrize("identity", ["owned", "reused"])
def test_rework_reaps_only_confirmed_orphan(tmp_path, monkeypatch, reaper, identity):
    launcher = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import subprocess, sys; p=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); print(p.pid, flush=True)",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    output, _ = launcher.communicate(timeout=3)
    pid = int(output)
    entry = {
        "pid": pid,
        "pgid": pid,
        "bridge_pid": launcher.pid,
        "start": server._proc_start_sig(pid),
        "command": "python",
    }
    if identity == "reused":
        entry["start"] = "reused PID signature"
    children = tmp_path / "children.json"
    children.write_text(json.dumps([entry]))
    monkeypatch.setattr(server, "_children_path", lambda: children)
    try:
        if reaper == "registry":
            reaped = server.reconcile_children()
        else:
            reaped = len(
                HubLifecycleManager(
                    state_dir=tmp_path, orphan_grace_s=0.05
                ).reap_startup_orphans()
            )
        assert reaped == (1 if identity == "owned" else 0)
        if identity == "reused":
            os.kill(pid, 0)
        else:
            deadline = time.monotonic() + 3
            while server._proc_start_sig(pid):
                assert time.monotonic() < deadline
                threading.Event().wait(0.01)
    finally:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0.12", 0.12),
        ("0", 0.0),
        (" 0.5 ", 0.5),
        ("", 4.5),
        ("bad", 4.5),
        ("nan", 4.5),
        ("-1", 4.5),
        ("inf", 4.5),
    ],
)
def test_rework_shutdown_grace_config_used(monkeypatch, value, expected):
    monkeypatch.setenv("BRIDGE_SHUTDOWN_GRACE_S", value)
    monkeypatch.setattr(server, "_shutting_down", False)
    proc = Mock(busy=False)
    monkeypatch.setattr(server, "_rpc_procs", {1: proc})
    assert server.shutdown_all() == 1
    assert proc.close.call_args.kwargs["graceful_wait"] == pytest.approx(
        expected * 0.45
    )


def test_rework_drain_closes_listener_only_after_active_turns(tmp_path):
    events = []
    active = [1]

    class HttpServer:
        def shutdown(self):
            events.append("shutdown")

        def graceful_close_listener(self):
            events.append("close")

        def close_idle_connections(self):
            events.append("idle")

    lifecycle = HubLifecycleManager(
        state_dir=tmp_path,
        active_turns_fn=lambda: active[0],
        drain_enabled_fn=lambda: True,
    )
    lifecycle.attach_server(HttpServer())

    def finish(_):
        assert events == []
        active[0] = 0

    with patch("core.lifecycle.time.sleep", side_effect=finish):
        lifecycle.run_drain_once()
    assert events == ["shutdown", "close", "idle"]


@pytest.mark.parametrize("mode", ["enabled", "disabled", "unsupported", "error"])
def test_rework_reuseport_diagnostics(monkeypatch, mode):
    import socket
    from http.server import ThreadingHTTPServer

    monkeypatch.setenv(
        "BRIDGE_SO_REUSEPORT_ENABLED", "false" if mode == "disabled" else "true"
    )
    monkeypatch.setattr(socket, "SO_REUSEPORT", 12345, raising=False)
    if mode == "unsupported":
        monkeypatch.delattr(socket, "SO_REUSEPORT")
    srv = object.__new__(server.Server)
    srv.socket = Mock()
    if mode == "error":
        srv.socket.setsockopt.side_effect = OSError("unsupported option")
    logs = []
    monkeypatch.setattr(server, "_log", logs.append)
    monkeypatch.setattr(ThreadingHTTPServer, "server_bind", lambda _: None)
    srv.server_bind()
    assert f"configured={mode != 'disabled'}" in logs[0]
    assert f"enabled={mode == 'enabled'}" in logs[0]
    assert f"reason={mode}" in logs[0]


def test_rework_keeps_active_http_response_after_turn_counter_drops(
    tmp_path, monkeypatch
):
    body_started = threading.Event()
    complete = threading.Event()
    active = threading.Event()

    class Handler(server.Handler):
        def do_GET(self):
            active.set()
            self.send_response(200)
            self.send_header("Content-Length", "4")
            self.end_headers()
            self.wfile.write(b"ab")
            self.wfile.flush()
            active.clear()
            body_started.set()
            if complete.wait(3):
                self.wfile.write(b"cd")
                self.wfile.flush()

    lifecycle = HubLifecycleManager(
        state_dir=tmp_path,
        active_turns_fn=lambda: int(active.is_set()),
        drain_enabled_fn=lambda: True,
    )
    monkeypatch.setattr(server, "LIFECYCLE", lifecycle)
    srv = server.Server(("127.0.0.1", 0), Handler)
    lifecycle.attach_server(srv)
    serving = threading.Thread(
        target=srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    serving.start()
    client = HTTPConnection(*srv.server_address, timeout=3)
    try:
        client.request("GET", "/")
        response = client.getresponse()
        assert body_started.wait(1)
        assert response.read(2) == b"ab"
        lifecycle.trigger_shutdown()
        assert lifecycle.drain_completed.wait(1)
        complete.set()
        assert response.read() == b"cd"
    finally:
        complete.set()
        client.close()
        srv.shutdown()
        srv.server_close()
        serving.join(3)
