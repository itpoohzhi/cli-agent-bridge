"""Интеграционные unit-тесты моста droid-bridge (HTTP-слой с фейковым Run).

Покрывают: склейку message-событий через "\\n\\n" (M1), сквозной таймаут (M2),
ретраи транзиентных сбоев (M3), не-stream ветку с tool_calls (m4), SSE-фреймы
[DONE]/error (m4), _sweep_workspace (m1). Кламп-тесты эталона заменены строгими
проверками каталога и effort (dev-контекст, без клампов/алиасов).
"""

import json
import sys
import unittest
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import BridgeCase, TOOLS  # noqa: E402


class TestMessageJoining(BridgeCase):
    """M1: событие message несёт полный текст; сообщения склеиваются через \\n\\n."""

    def test_two_message_events_joined_nonstream(self):
        self.hub.legacy(
            [
                [
                    ("text", "First message"),
                    ("text", "Second message"),
                    ("result", {"finalText": "", "usage": {}}),
                    ("done", (0, "")),
                ]
            ]
        )
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            body["choices"][0]["message"]["content"], "First message\n\nSecond message"
        )

    def test_two_message_events_joined_sse(self):
        self.hub.legacy(
            [
                [
                    ("text", "First message"),
                    ("text", "Second message"),
                    ("result", {"finalText": "", "usage": {}}),
                    ("done", (0, "")),
                ]
            ]
        )
        status, stream = self._post(
            {
                "model": "claude-sonnet-5-5",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertIn('"content": "First message"', stream)
        self.assertIn('"content": "\\n\\nSecond message"', stream)
        self.assertNotIn('"content": "First message\\n\\nSecond message"', stream)


class TestNonStreamToolCalls(BridgeCase):
    """m4: не-stream ветка — finish_reason tool_calls и message.tool_calls."""

    def test_tool_call_block_becomes_tool_calls(self):
        self.hub.legacy(
            [
                [
                    (
                        "text",
                        server.TOOL_CALL_OPEN
                        + '{"name": "get_weather", "arguments": {"city": "Berlin"}}'
                        + server.TOOL_CALL_CLOSE,
                    ),
                    ("result", {"finalText": "", "usage": {}}),
                    ("done", (0, "")),
                ]
            ]
        )
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "tools": TOOLS,
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        choice = body["choices"][0]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        calls = choice["message"]["tool_calls"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["type"], "function")
        self.assertEqual(calls[0]["function"]["name"], "get_weather")
        self.assertEqual(
            json.loads(calls[0]["function"]["arguments"]), {"city": "Berlin"}
        )
        self.assertNotIn(server.TOOL_CALL_OPEN, choice["message"]["content"] or "")


class TestSSEFrames(BridgeCase):
    """m4: SSE-фреймы — финальный finish_reason, [DONE], error-фрейм."""

    def test_stream_ends_with_finish_and_done(self):
        self.hub.legacy(
            [
                [
                    ("text", "hello"),
                    ("result", {"finalText": "", "usage": {}}),
                    ("done", (0, "")),
                ]
            ]
        )
        status, stream = self._post(
            {
                "model": "claude-sonnet-5-5",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertIn('"finish_reason": "stop"', stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))

    def test_stream_error_frame_then_done(self):
        # три одинаковых сценария: ретраи транзиентного rc=1 исчерпают попытки
        self.hub.legacy(
            [[("stderr", "Exec failed"), ("done", (1, ""))] for _ in range(3)]
        )
        status, stream = self._post(
            {
                "model": "claude-sonnet-5-5",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertIn('"error"', stream)
        self.assertIn("Exec failed", stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
        self.assertNotIn('"finish_reason": "stop"', stream)


class TestTransientRetry(BridgeCase):
    """M3: rc=1 без выданного текста -> до 3 попыток; успех со второй."""

    def test_retry_until_success(self):
        self.hub.legacy(
            [
                [("stderr", "Exec failed"), ("done", (1, ""))],
                [
                    ("text", "Recovered"),
                    ("result", {"finalText": "", "usage": {}}),
                    ("done", (0, "")),
                ],
            ]
        )
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "Recovered")
        self.assertEqual(len(self.hub.admissions()), 2)  # принятые циклы agent loop

    def test_retry_gives_up_after_three(self):
        self.hub.legacy(
            [[("stderr", "Exec failed"), ("done", (1, ""))] for _ in range(3)]
        )
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 502)
        self.assertEqual(len(self.hub.admissions()), 3)
        self.assertIn("error", body)

    def test_no_retry_after_content_committed(self):
        # Контент удерживается до terminal; после успешного terminal он закоммичен и
        # отдан клиенту, поздняя смерть процесса ход не отменяет: ровно один цикл, без ретрая.
        self.hub.script([{"steps": [{"op": "text", "text": "Partial"}], "late": 0.05}])
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "Partial")
        self.assertEqual(len(self.hub.admissions()), 1)

    def test_buffered_text_not_leaked_on_failed_turn(self):
        # Сбой хода после частичного текста: клиент получает прежние error-кадр и DONE,
        # частичный (незакоммиченный) текст в SSE не попадает, ретрая нет (модельная ошибка).
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "text", "text": "Partial"},
                        {"op": "error", "message": "model failed"},
                    ],
                    "reason": "model_request_rejected",
                }
            ]
        )
        status, stream = self._post(
            {
                "model": "claude-sonnet-5-5",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertNotIn("Partial", stream)
        self.assertIn('"error"', stream)
        self.assertIn("model failed", stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
        self.assertEqual(len(self.hub.admissions()), 1)


class TestOverallTimeout(BridgeCase):
    """M2: превышение сквозного таймаута -> 504, слот освобождается."""

    def test_timeout_returns_504(self):
        self.hub.legacy([[]])  # процесс «молчит»: ни текста, ни terminal
        real_timeout = server.TIMEOUT_S
        server.TIMEOUT_S = 1
        try:
            status, body = self._post_json(
                {
                    "model": "claude-sonnet-5-5",
                    "messages": [{"role": "user", "content": "hi"}],
                }
            )
        finally:
            server.TIMEOUT_S = real_timeout
        self.assertEqual(status, 504)
        self.assertIn("timed out", body["error"]["message"])

    def test_slot_released_after_timeout(self):
        self.hub.legacy([[]])
        real_timeout = server.TIMEOUT_S
        server.TIMEOUT_S = 1
        try:
            self._post(
                {
                    "model": "claude-sonnet-5-5",
                    "messages": [{"role": "user", "content": "hi"}],
                }
            )
            # после таймаута слот должен вернуться в пул
            self.assertTrue(
                server._slots.acquire(timeout=5), "slot was not released after timeout"
            )
            server._slots.release()
        finally:
            server.TIMEOUT_S = real_timeout


class TestSweepWorkspace(unittest.TestCase):
    """m1: sweep удаляет только старые prompt-*.txt и img-*."""

    def test_sweep_removes_only_stale_prompts(self):
        import tempfile

        real_ws = server.WORKSPACE
        with tempfile.TemporaryDirectory() as tmp:
            server.WORKSPACE = Path(tmp)
            old = Path(tmp) / "prompt-old.txt"
            new = Path(tmp) / "prompt-new.txt"
            keep = Path(tmp) / "other.txt"
            stale_dir = Path(tmp) / "img-old"
            fresh_dir = Path(tmp) / "img-new"
            stale_dir.mkdir()
            fresh_dir.mkdir()
            for p in (old, new, keep):
                p.write_text("x", encoding="utf-8")
            stale = time.time() - 7200
            import os

            os.utime(old, (stale, stale))
            os.utime(stale_dir, (stale, stale))
            try:
                server._sweep_workspace()
            finally:
                server.WORKSPACE = real_ws
            self.assertFalse(old.exists())
            self.assertTrue(new.exists())
            self.assertTrue(keep.exists())
            self.assertFalse(stale_dir.exists())
            self.assertTrue(fresh_dir.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
