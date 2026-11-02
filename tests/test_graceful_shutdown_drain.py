from itertools import chain, repeat
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.backend_adapter import TurnResult
from core.lifecycle import DrainState, HubLifecycleManager, KeepaliveController
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

    def test_drain_waits_for_active_turn_and_persists_interrupted_on_timeout(self) -> None:
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

    def test_drain_waits_for_active_turns_fn_even_when_turn_manager_is_idle(self) -> None:
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
                    side_effect=chain(counts, repeat(RuntimeError("counter unavailable")))
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
                    patch("core.lifecycle.time.monotonic", side_effect=lambda: elapsed_s),
                    patch("core.lifecycle.time.sleep", side_effect=advance_time) as sleep,
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
                self.assertTrue(any("drain_active_count_error" in line for line in logs))
                server.shutdown.assert_called_once_with()
                on_complete.assert_called_once_with()

    def test_drain_finally_guarantees_stopped_state_on_server_shutdown_error(self) -> None:
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
        backends.active_total.return_value = 1
        events: list[str] = []
        wait_for_active_turns = manager.wait_for_active_turns

        def complete_managed_turn(timeout: float) -> list[ManagedTurn]:
            self.assertEqual(manager.active_count(), 1)
            self.assertEqual(backends.active_total(), 1)
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

    def test_startup_orphan_reaper_cleans_children_json(self) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        proc = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        try:
            manager.register_child_pgid(
                "turn-orphan-01",
                proc.pid,
                pid=proc.pid,
                command="python3 -c import time; time.sleep(60)",
            )
            lifecycle = HubLifecycleManager(
                state_dir=self._state_dir,
                turn_manager=manager,
                orphan_grace_s=0.2,
            )
            reaped = lifecycle.reap_orphans_on_startup()
            self.assertIn(proc.pid, reaped)
            proc.wait(timeout=3.0)
            self.assertIsNotNone(proc.returncode)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2.0)

    def test_keepalive_clamped_to_10s(self) -> None:
        ka = KeepaliveController(max_interval_s=10.0)
        self.assertEqual(ka.effective_interval(15.0), 10.0)
        self.assertEqual(ka.effective_interval(5.0), 5.0)
        self.assertTrue(ka.sse_comment().startswith(": keepalive"))


if __name__ == "__main__":
    unittest.main()
