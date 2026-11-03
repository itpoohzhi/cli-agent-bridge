"""EYE-35048 / ADR-0020: RepetitionGuard — детект зацикливания и защита от FP."""

from __future__ import annotations

import io
import json
import os
import sys
from types import SimpleNamespace
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from adapters.passthrough_adapter import (  # noqa: E402
    PassthroughAdapter,
    PassthroughLimits,
    relay_sse,
)
from core.backend_adapter import TurnResult  # noqa: E402
from core.tool_emulation import (  # noqa: E402
    LiveParserError,
    RepetitionGuard,
    RepetitionLoopDetected,
    ToolCallParser,
    _strip_code_for_guard,
)


class Collector:
    def __init__(self):
        self.content = []
        self.calls = []

    def on_content(self, text):
        self.content.append(text)

    def on_call(self, call):
        self.calls.append(call)


def _frame(payload) -> bytes:
    return b"data: " + json.dumps(payload).encode("utf-8") + b"\n\n"


def _content_chunk(text: str) -> bytes:
    return _frame(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "m",
            "choices": [
                {"index": 0, "delta": {"content": text}, "finish_reason": None}
            ],
        }
    )


DONE = b"data: [DONE]\n\n"


class TestRepetitionGuard(unittest.TestCase):
    def test_repetition_guard_detects_placeholder_loop(self):
        guard = RepetitionGuard()
        _, detected = guard.feed("\n\n_placeholder" * 25)
        self.assertTrue(detected)
        self.assertTrue(guard.detected)

    def test_repetition_guard_detects_placeholder_across_chunks(self):
        guard = RepetitionGuard(max_repeats=20)
        detected = False
        for _ in range(25):
            _, detected = guard.feed("\n\n_placeholder")
        self.assertTrue(detected)

    def test_repetition_guard_threshold_boundary(self):
        guard = RepetitionGuard(max_repeats=5)
        _, detected = guard.feed("_placeholder " * 4)
        self.assertFalse(detected)
        _, detected = guard.feed("_placeholder ")
        self.assertTrue(detected)

    def test_repetition_guard_natural_text_not_blocked(self):
        guard = RepetitionGuard()
        text = (
            "the quick brown fox jumps over the lazy dog. "
            "the dog was not amused, and the fox ran away. "
        ) * 4
        _, detected = guard.feed(text)
        self.assertFalse(detected)
        self.assertFalse(guard.detect(text))

    def test_repetition_guard_disabled_never_detects(self):
        guard = RepetitionGuard(enabled=False)
        _, detected = guard.feed("\n\n_placeholder" * 100)
        self.assertFalse(detected)

    def test_repetition_guard_false_positive_protections(self):
        guard = RepetitionGuard()
        code_block = "```python\n" + "_placeholder\n" * 40 + "```\n"
        _, detected = guard.feed(code_block)
        self.assertFalse(detected, "повторы внутри fenced-кода не детектятся")

        guard = RepetitionGuard()
        _, detected = guard.feed("\n" * 60 + " " * 40 + "\t" * 30)
        self.assertFalse(detected, "чистый whitespace не детектится")

        guard = RepetitionGuard()
        _, detected = guard.feed(("---\n" * 30) + ("===\n" * 30) + ("***\n" * 30))
        self.assertFalse(detected, "markdown-разделители не детектятся")

        # Списки инлайн-кода через запятую (сессия 73c65940, шаг 95)
        guard = RepetitionGuard()
        tags = ", ".join(f"`@user_{i}`" for i in range(30))
        _, detected = guard.feed(tags)
        self.assertFalse(detected, "список инлайн-кода через запятую не должен триггерить FP")

        # Таблицы Markdown с вертикальными чертами
        guard = RepetitionGuard()
        table_row = "| " + " | ".join(f"col_{i}" for i in range(25)) + " |\n"
        _, detected = guard.feed(table_row * 3)
        self.assertFalse(detected, "вертикальные черты Markdown не должны триггерить FP")

    def test_repetition_guard_detects_emoji_loop(self):
        guard = RepetitionGuard(max_repeats=10)
        _, detected = guard.feed("🚀 " * 9)
        self.assertFalse(detected)
        _, detected = guard.feed("🚀 ")
        self.assertTrue(detected)

    def test_repetition_guard_detects_repeated_words_with_punctuation(self):
        guard = RepetitionGuard(max_repeats=10)
        _, detected = guard.feed("hello, " * 9)
        self.assertFalse(detected)
        _, detected = guard.feed("hello, ")
        self.assertTrue(detected)

    def test_repetition_guard_loop_outside_code_still_detected(self):
        guard = RepetitionGuard()
        text = "```\nsome code\n```\n" + "\n\n_placeholder" * 25
        _, detected = guard.feed(text)
        self.assertTrue(detected)

    def test_repetition_guard_reset(self):
        guard = RepetitionGuard()
        guard.feed("\n\n_placeholder" * 25)
        self.assertTrue(guard.detected)
        guard.reset()
        self.assertFalse(guard.detected)
        _, detected = guard.feed("normal text")
        self.assertFalse(detected)

    def test_strict_live_parser_raises_on_repetition_loop(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
        with self.assertRaises((RepetitionLoopDetected, LiveParserError)):
            p.feed("\n\n_placeholder" * 25)
            p.finish()

    def test_core_does_not_read_environ(self):
        source = (
            Path(__file__).resolve().parent.parent / "core" / "tool_emulation.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("os.environ", source)
        self.assertNotIn("environ", source)

    def test_repetition_guard_dynamic_capacity_detects_1000_repeats_of_64char_token(self):
        guard = RepetitionGuard(max_repeats=1000, max_token_len=64)
        expected_max = max(32768, (1000 + 10) * (64 + 4))
        self.assertEqual(expected_max, 68680)
        self.assertEqual(guard._max_buffer, expected_max)
        self.assertEqual(guard._keep_buffer, expected_max // 2)

        token_64 = "a" * 64
        _, detected = guard.feed((token_64 + " ") * 999)
        self.assertFalse(detected)
        _, detected = guard.feed(token_64 + " ")
        self.assertTrue(detected)
        self.assertTrue(guard.detected)

        guard_stream = RepetitionGuard(max_repeats=1000, max_token_len=64)
        detected_stream = False
        for _ in range(100):
            _, detected_stream = guard_stream.feed((token_64 + "\n") * 10)
        self.assertTrue(detected_stream)

    def test_strip_code_for_guard_tracks_unmatched_inline_backticks_across_chunks_and_lines(self):
        c1, state = _strip_code_for_guard("prefix `_placeholder _placeholder\n", None)
        self.assertIsNotNone(state)
        self.assertNotIn("_placeholder", c1)
        c2, state = _strip_code_for_guard("_placeholder _placeholder` suffix\n", state)
        self.assertIsNone(state)
        self.assertNotIn("_placeholder", c2)
        self.assertIn("suffix", c2)

        # Multi-line and cross-chunk inline backticks in RepetitionGuard must not false-trigger
        guard = RepetitionGuard(max_repeats=5)
        _, detected = guard.feed("text before `_placeholder _placeholder _placeholder\n")
        self.assertFalse(detected)
        _, detected = guard.feed("_placeholder _placeholder _placeholder\n")
        self.assertFalse(detected)
        _, detected = guard.feed("_placeholder _placeholder` after\n")
        self.assertFalse(detected)

        # Real loop after closing inline backtick still triggers
        _, detected = guard.feed(" _placeholder" * 5)
        self.assertTrue(detected)


class TestPassthroughRepetitionGuard(unittest.TestCase):
    def test_relay_sse_repetition_loop_error_frame_no_done(self):
        events = (
            _content_chunk("start")
            + _content_chunk("\n\n_placeholder" * 10)
            + _content_chunk("\n\n_placeholder" * 15)
            + _content_chunk("never reached")
            + DONE
        )
        out: list = []
        outcome = relay_sse(
            io.BytesIO(events).readline,
            out.append,
            tool_schemas=None,
            limits=PassthroughLimits(repetition_guard_enabled=True),
        )
        body = b"".join(out)
        self.assertTrue(outcome.repetition_loop)
        self.assertFalse(outcome.done)
        self.assertNotIn(b"[DONE]", body)
        self.assertIn(b"upstream_repetition_loop", body)

    def test_relay_sse_normal_content_unchanged(self):
        events = (
            _content_chunk("hello ")
            + _content_chunk("world")
            + _frame(
                {
                    "id": "chatcmpl-1",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": "m",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
            )
            + DONE
        )
        out: list = []
        outcome = relay_sse(
            io.BytesIO(events).readline,
            out.append,
            tool_schemas=None,
            limits=PassthroughLimits(),
        )
        self.assertTrue(outcome.done)
        self.assertEqual(b"".join(out), events)

    def test_passthrough_limits_from_env(self):
        limits = PassthroughLimits.from_env(
            {
                "BRIDGE_REPETITION_MAX_REPEATS": "7",
                "BRIDGE_REPETITION_MAX_TOKEN_LEN": "32",
                "BRIDGE_REPETITION_GUARD_ENABLED": "true",
                "BRIDGE_INVOKE_NORMALIZATION_ENABLED": "1",
            }
        )
        self.assertEqual(limits.repetition_max_repeats, 7)
        self.assertEqual(limits.repetition_max_token_len, 32)
        self.assertTrue(limits.repetition_guard_enabled)
        self.assertTrue(limits.invoke_normalization_enabled)

    def test_passthrough_limits_defaults(self):
        limits = PassthroughLimits.from_env({})
        self.assertEqual(limits.repetition_max_repeats, 20)
        self.assertEqual(limits.repetition_max_token_len, 64)
        self.assertFalse(limits.repetition_guard_enabled)
        self.assertFalse(limits.invoke_normalization_enabled)
        default_instance = PassthroughLimits()
        self.assertFalse(default_instance.repetition_guard_enabled)
        self.assertFalse(default_instance.invoke_normalization_enabled)

    def test_dynamic_env_flags_per_request_and_server_routes(self):
        invoke_xml = '<invoke name="bash"><parameter name="command">ls</parameter></invoke>'
        raw_turn = TurnResult(state="done", rc=0, text=invoke_xml)
        ctx = {
            "backend": "droid",
            "model": "m",
            "effort": "high",
            "prompt": "p",
            "rpc": {"system": "", "runnable": "", "items": []},
            "images": [],
            "emulate_tools": True,
            "tool_schemas": None,
            "stream": False,
            "managed_turn": None,
        }
        cli_adapter = SimpleNamespace(kind="droid", execute_turn=lambda turn, writer: raw_turn)

        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BRIDGE_REPETITION_GUARD_ENABLED", None)
            os.environ.pop("BRIDGE_INVOKE_NORMALIZATION_ENABLED", None)

            # 1. Default disabled in PassthroughAdapter and server._dispatch
            pt_adapter = PassthroughAdapter(
                "test",
                {"base_url": "http://127.0.0.1:9999/v1"},
                dict,
            )
            self.assertFalse(pt_adapter.limits.repetition_guard_enabled)
            self.assertFalse(pt_adapter.limits.invoke_normalization_enabled)

            with unittest.mock.patch.object(server.BACKENDS, "get", return_value=cli_adapter):
                out_disabled = server.Handler._dispatch(SimpleNamespace(connection=None), dict(ctx), None)
            self.assertEqual(out_disabled["tool_calls"], [])
            self.assertIn("<invoke", out_disabled["text"])

            # 2. Flip env flags to enabled within process (without restart)
            os.environ["BRIDGE_REPETITION_GUARD_ENABLED"] = "true"
            os.environ["BRIDGE_INVOKE_NORMALIZATION_ENABLED"] = "true"
            self.assertTrue(pt_adapter.limits.repetition_guard_enabled)
            self.assertTrue(pt_adapter.limits.invoke_normalization_enabled)

            with unittest.mock.patch.object(server.BACKENDS, "get", return_value=cli_adapter):
                out_enabled = server.Handler._dispatch(SimpleNamespace(connection=None), dict(ctx), None)
            self.assertEqual(len(out_enabled["tool_calls"]), 1)
            self.assertEqual(out_enabled["tool_calls"][0]["function"]["name"], "bash")
            self.assertEqual(out_enabled["text"], "")

            # 3. Flip env flags back to disabled (kill switch)
            os.environ["BRIDGE_REPETITION_GUARD_ENABLED"] = "0"
            os.environ["BRIDGE_INVOKE_NORMALIZATION_ENABLED"] = "false"
            self.assertFalse(pt_adapter.limits.repetition_guard_enabled)
            self.assertFalse(pt_adapter.limits.invoke_normalization_enabled)

            with unittest.mock.patch.object(server.BACKENDS, "get", return_value=cli_adapter):
                out_killed = server.Handler._dispatch(SimpleNamespace(connection=None), dict(ctx), None)
            self.assertEqual(out_killed["tool_calls"], [])
            self.assertIn("<invoke", out_killed["text"])


if __name__ == "__main__":
    unittest.main()
