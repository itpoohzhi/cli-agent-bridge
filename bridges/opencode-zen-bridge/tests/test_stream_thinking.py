#!/usr/bin/env python3
"""Regression-тесты для потокового стриминга и передачи мышления в opencode-zen-bridge."""

from __future__ import annotations

import json
import unittest

import server
from tests._fixtures import install_test_models

install_test_models(server)


class TestMapEffort(unittest.TestCase):
    def test_map_effort_off(self) -> None:
        self.assertEqual(server._map_effort({"reasoning_effort": "off"}), "")
        self.assertEqual(server._map_effort({"reasoning_effort": "none"}), "")

    def test_map_effort_high(self) -> None:
        self.assertEqual(server._map_effort({"reasoning_effort": "high"}), "high")
        self.assertEqual(server._map_effort({"reasoning_effort": "HIGH"}), "high")

    def test_map_effort_max(self) -> None:
        # Без model_id берётся DEFAULT_MODEL (deepseek-v4.1-flash-free): его variant_map сводит max-уровни к "max".
        self.assertEqual(server._map_effort({"reasoning_effort": "max"}), "max")
        self.assertEqual(server._map_effort({"reasoning_effort": "xhigh"}), "max")
        self.assertEqual(server._map_effort({"reasoning_effort": "ultra"}), "max")

    def test_map_effort_nested(self) -> None:
        self.assertEqual(server._map_effort({"reasoning": {"effort": "low"}}), "low")

    def test_map_effort_default(self) -> None:
        self.assertEqual(server._map_effort({}), "high")

    def test_map_effort_deepseek_v41_free(self) -> None:
        mid = "deepseek-v4.1-flash-free"
        self.assertEqual(server._map_effort({"reasoning_effort": "low"}, model_id=mid), "low")
        self.assertEqual(server._map_effort({"reasoning_effort": "medium"}, model_id=mid), "high")
        self.assertEqual(server._map_effort({"reasoning_effort": "high"}, model_id=mid), "high")
        self.assertEqual(server._map_effort({"reasoning_effort": "max"}, model_id=mid), "max")
        self.assertEqual(server._map_effort({"reasoning_effort": "xhigh"}, model_id=mid), "max")
        self.assertEqual(server._map_effort({"reasoning_effort": "off"}, model_id=mid), "")

    def test_map_effort_off_explicit_for_models(self) -> None:
        for mid in ("deepseek-v4.1-flash-free", "muse-spark-1.3-contributor-free"):
            self.assertEqual(server._map_effort({"reasoning_effort": "off"}, model_id=mid), "")
            self.assertEqual(server._map_effort({"reasoning": {"effort": "off"}}, model_id=mid), "")
            self.assertEqual(server._map_effort({"reasoning_effort": "none"}, model_id=mid), "")


class TestParseOpencodeEvent(unittest.TestCase):
    def test_reasoning_text(self) -> None:
        event = {
            "type": "reasoning",
            "part": {
                "text": "Thinking about the bug...",
            },
        }
        etype, delta = server.parse_opencode_event(event)
        self.assertEqual(etype, "reasoning")
        self.assertEqual(delta, {"reasoning_content": "Thinking about the bug..."})

    def test_reasoning_encrypted_details(self) -> None:
        event = {
            "type": "reasoning",
            "part": {
                "metadata": {
                    "openai": {
                        "reasoningEncryptedContent": "enc_payload_xyz",
                    },
                },
            },
        }
        etype, delta = server.parse_opencode_event(event)
        self.assertEqual(etype, "reasoning")
        self.assertEqual(
            delta,
            {"reasoning_details": [{"type": "reasoning.encrypted", "data": "enc_payload_xyz"}]},
        )

    def test_reasoning_text_and_encrypted(self) -> None:
        event = {
            "type": "reasoning",
            "part": {
                "text": "Deep thought",
                "metadata": {
                    "openai": {
                        "reasoningEncryptedContent": "enc_blob_123",
                    },
                },
            },
        }
        etype, delta = server.parse_opencode_event(event)
        self.assertEqual(etype, "reasoning")
        self.assertEqual(
            delta,
            {
                "reasoning_content": "Deep thought",
                "reasoning_details": [{"type": "reasoning.encrypted", "data": "enc_blob_123"}],
            },
        )

    def test_text_event(self) -> None:
        event = {
            "type": "text",
            "part": {
                "text": "Final answer snippet",
            },
        }
        etype, delta = server.parse_opencode_event(event)
        self.assertEqual(etype, "text")
        self.assertEqual(delta, {"content": "Final answer snippet"})

    def test_step_finish_event(self) -> None:
        event = {
            "type": "step_finish",
            "part": {
                "tokens": {"input": 42, "output": 100},
            },
        }
        etype, usage = server.parse_opencode_event(event)
        self.assertEqual(etype, "step_finish")
        self.assertEqual(usage, {"input": 42, "output": 100})


class TestFormatSSEChunk(unittest.TestCase):
    def test_format_initial_chunk(self) -> None:
        chunk = server.format_sse_chunk(
            resp_id="chatcmpl-test-1",
            created=1700000000,
            model="muse-spark-1.3-contributor-free",
            delta={"role": "assistant", "content": ""},
        )
        self.assertTrue(chunk.startswith("data: "))
        self.assertTrue(chunk.endswith("\n\n"))
        parsed = json.loads(chunk[6:].strip())
        self.assertEqual(parsed["id"], "chatcmpl-test-1")
        self.assertEqual(parsed["model"], "muse-spark-1.3-contributor-free")
        self.assertEqual(parsed["choices"][0]["delta"], {"role": "assistant", "content": ""})

    def test_format_reasoning_chunk(self) -> None:
        delta = {
            "reasoning_content": "Pondering...",
            "reasoning_details": [{"type": "reasoning.encrypted", "data": "enc_data"}],
        }
        chunk = server.format_sse_chunk(
            resp_id="chatcmpl-test-2",
            created=1700000000,
            model="muse-spark-1.3-contributor-free",
            delta=delta,
        )
        parsed = json.loads(chunk[6:].strip())
        self.assertEqual(parsed["choices"][0]["delta"], delta)

    def test_format_final_chunk_with_usage(self) -> None:
        chunk = server.format_sse_chunk(
            resp_id="chatcmpl-test-3",
            created=1700000000,
            model="muse-spark-1.3-contributor-free",
            delta={},
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )
        parsed = json.loads(chunk[6:].strip())
        self.assertEqual(parsed["choices"][0]["finish_reason"], "stop")
        self.assertEqual(parsed["usage"]["total_tokens"], 30)


if __name__ == "__main__":
    unittest.main()
