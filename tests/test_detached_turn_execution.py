import os
import tempfile
import unittest
from pathlib import Path

from core.backend_adapter import ToolCall, ToolFunction, TurnResult, Usage
from core.turn_session_manager import TurnForbiddenError, TurnSessionManager


class DetachedTurnExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._state_dir = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_client_disconnect_detaches_and_finishes_in_background(self) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        turn, existing = manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "hello"}],
            session_id="sess-01",
            owner_token_hash="owner-a",
            requested_turn_id="turn-detach-01",
            stream=True,
        )
        self.assertFalse(existing)
        self.assertEqual(turn.status, "RUNNING_ATTACHED")

        turn.buffer.append("content", "Hello ")
        turn.mark_detached()
        self.assertEqual(turn.status, "RUNNING_DETACHED")

        turn.buffer.append("content", "world!")
        result = TurnResult(
            state="done",
            rc=0,
            text="Hello world!",
            reasoning="step-by-step",
            usage=Usage(input_tokens=12, output_tokens=6),
            tool_calls=(
                ToolCall(
                    index=0,
                    id="call-1",
                    function=ToolFunction(name="read_file", arguments='{"path":"a.py"}'),
                ),
            ),
        )
        manager.complete_turn_from_result(turn, result, backend_kind="droid")

        snap = manager.get_turn_snapshot("turn-detach-01", owner_token_hash="owner-a")
        self.assertEqual(snap["schema_version"], "1.0")
        self.assertEqual(snap["status"], "completed")
        self.assertEqual(snap["state"], "COMPLETED")
        self.assertEqual(snap["content"], "Hello world!")
        self.assertEqual(snap["reasoning_content"], "step-by-step")
        self.assertEqual(len(snap["tool_calls"]), 1)
        self.assertEqual(snap["usage"]["prompt_tokens"], 12)
        self.assertEqual(snap["usage"]["completion_tokens"], 6)

        turn_file = Path(self._state_dir) / "turns" / "turn-detach-01.json"
        self.assertTrue(turn_file.exists())
        mode = os.stat(turn_file).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_idempotent_retry_and_resume_turn_id(self) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        t1, ex1 = manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "retry-test"}],
            session_id="sess-02",
            owner_token_hash="owner-a",
            requested_turn_id="turn-idem-01",
            stream=True,
        )
        self.assertFalse(ex1)

        t2, ex2 = manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "retry-test"}],
            session_id="sess-02",
            owner_token_hash="owner-a",
            requested_turn_id="turn-idem-01",
            stream=True,
        )
        self.assertTrue(ex2)
        self.assertIs(t1, t2)

        t3, ex3 = manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "retry-test"}],
            session_id="sess-02",
            owner_token_hash="owner-a",
            resume_turn_id="turn-idem-01",
            stream=True,
        )
        self.assertTrue(ex3)
        self.assertIs(t1, t3)

    def test_owner_isolation_enforced(self) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "secret"}],
            session_id="sess-03",
            owner_token_hash="owner-a",
            requested_turn_id="turn-own-01",
            stream=False,
        )
        with self.assertRaises(TurnForbiddenError):
            manager.get_turn_snapshot("turn-own-01", owner_token_hash="owner-b")


if __name__ == "__main__":
    unittest.main()
