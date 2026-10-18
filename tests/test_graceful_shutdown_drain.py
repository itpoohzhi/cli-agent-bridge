import signal
import subprocess
import tempfile
import unittest

from core.lifecycle import DrainState, HubLifecycleManager, KeepaliveController
from core.turn_session_manager import TurnSessionManager


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
