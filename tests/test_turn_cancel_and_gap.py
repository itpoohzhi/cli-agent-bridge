import subprocess
import tempfile
import unittest

from core.turn_session_manager import (
    GapDetectedError,
    TurnBuffer,
    TurnSessionManager,
    validate_turn_id,
)


class TurnCancelAndGapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._state_dir = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_delete_turn_cancels_tree_and_releases_slot_exactly_once(self) -> None:
        release_calls: list[int] = []
        manager = TurnSessionManager(state_root=self._state_dir, cancel_grace_s=0.2)
        proc = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        try:
            turn, _ = manager.create_or_attach_turn(
                model="claude-4.6-opus",
                backend="droid",
                cwd="/tmp",
                messages=[{"role": "user", "content": "cancel me"}],
                session_id="sess-cancel",
                owner_token_hash="owner-1",
                requested_turn_id="turn-cancel-01",
                stream=True,
                slot_release_fn=lambda: release_calls.append(1),
            )
            manager.register_child_pgid(
                "turn-cancel-01",
                proc.pid,
                pid=proc.pid,
                command="python3 -c import time; time.sleep(60)",
            )

            cancelled = manager.cancel_turn("turn-cancel-01", owner_token_hash="owner-1")
            self.assertEqual(cancelled.status, "CANCELLED")
            proc.wait(timeout=3.0)
            self.assertIsNotNone(proc.returncode)

            # Second cancel and manual slot release must be idempotent no-ops
            manager.cancel_turn("turn-cancel-01", owner_token_hash="owner-1")
            turn.release_slot_once()
            self.assertEqual(len(release_calls), 1)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2.0)

    def test_ring_buffer_overflow_returns_410_gap_detected(self) -> None:
        buf = TurnBuffer(max_bytes=64)
        for idx in range(10):
            buf.append("content", f"chunk-{idx:02d}-0123456789\n")

        self.assertGreater(buf.oldest_available_seq, 1)
        self.assertEqual(buf.last_seq, 10)

        with self.assertRaises(GapDetectedError) as ctx:
            buf.events_since(0, turn_id="turn-gap-01")

        payload = ctx.exception.to_http_payload()
        self.assertEqual(payload["error"]["code"], "GAP_DETECTED")
        self.assertEqual(payload["error"]["turn_id"], "turn-gap-01")
        self.assertEqual(payload["error"]["requested_from_seq"], 0)
        self.assertEqual(payload["error"]["oldest_available_seq"], buf.oldest_available_seq)
        self.assertEqual(payload["error"]["last_seq"], 10)

    def test_validate_turn_id_rejects_traversal(self) -> None:
        self.assertTrue(validate_turn_id("turn_123-abc"))
        self.assertFalse(validate_turn_id("../etc/passwd"))
        self.assertFalse(validate_turn_id("a/b"))
        self.assertFalse(validate_turn_id(""))
        self.assertFalse(validate_turn_id("x" * 65))


if __name__ == "__main__":
    unittest.main()
