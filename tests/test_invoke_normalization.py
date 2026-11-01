"""EYE-35048 / ADR-0020: нормализация Anthropic `<invoke>` в ToolCallParser и relay."""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.passthrough_adapter import (  # noqa: E402
    PassthroughLimits,
    ToolCallAccumulator,
    relay_sse,
    sanitize_completion_body,
)
from core.tool_emulation import LiveParserError, ToolCallParser  # noqa: E402


class Collector:
    def __init__(self):
        self.content = []
        self.calls = []

    def on_content(self, text):
        self.content.append(text)

    def on_call(self, call):
        self.calls.append(call)

    @property
    def text(self) -> str:
        return "".join(self.content)


def _frame(payload) -> bytes:
    return b"data: " + json.dumps(payload).encode("utf-8") + b"\n\n"


def _chunk(delta, finish_reason=None) -> bytes:
    return _frame(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "m",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
    )


DONE = b"data: [DONE]\n\n"

INVOKE_BASH = '<invoke name="bash"><parameter name="command">ls</parameter></invoke>'


class TestInvokeNormalization(unittest.TestCase):
    def test_tool_call_parser_normalizes_invoke_xml(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(INVOKE_BASH)
        p.finish()
        self.assertEqual(len(c.calls), 1)
        call = c.calls[0]
        self.assertEqual(call["name"], "bash")
        self.assertEqual(call["arguments"], {"command": "ls"})
        self.assertTrue(str(call.get("id", "")).startswith("call_"))
        self.assertEqual(c.text, "")

    def test_invoke_prefix_form(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed('<invoke:bash><parameter name="command">pwd</parameter></invoke:bash>')
        p.finish()
        self.assertEqual(len(c.calls), 1)
        self.assertEqual(c.calls[0]["name"], "bash")
        self.assertEqual(c.calls[0]["arguments"], {"command": "pwd"})
        self.assertEqual(c.text, "")

    def test_invoke_string_params_not_coerced(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(
            '<invoke name="bash">'
            '<parameter name="command">true</parameter>'
            '<parameter name="count">1</parameter>'
            '<parameter name="path">/tmp/foo</parameter>'
            "</invoke>"
        )
        p.finish()
        args = c.calls[0]["arguments"]
        self.assertEqual(args, {"command": "true", "count": "1", "path": "/tmp/foo"})
        self.assertTrue(all(isinstance(v, str) for v in args.values()))

    def test_invoke_json_params_parsed_only_for_brace_or_bracket(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(
            '<invoke name="tool">'
            '<parameter name="opts">{"a": 1}</parameter>'
            '<parameter name="items">[1, 2]</parameter>'
            '<parameter name="plain">42</parameter>'
            "</invoke>"
        )
        p.finish()
        args = c.calls[0]["arguments"]
        self.assertEqual(args["opts"], {"a": 1})
        self.assertEqual(args["items"], [1, 2])
        self.assertEqual(args["plain"], "42")

    def test_streaming_invoke_zero_leakage(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        raw = "before " + INVOKE_BASH + " after"
        for ch in raw:
            p.feed(ch)
            self.assertNotIn("<inv", c.text)
            self.assertNotIn("<param", c.text)
            self.assertNotIn("<invoke", c.text)
        p.finish()
        self.assertEqual(c.text, "before  after")
        self.assertEqual(len(c.calls), 1)
        self.assertEqual(c.calls[0]["name"], "bash")

    def test_invoke_split_prefixes_held(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed("abc<inv")
        self.assertEqual(c.text, "abc")
        p.feed('oke name="bash"><param')
        self.assertEqual(c.text, "abc")
        p.feed('eter name="command">ls</parameter></invoke>')
        p.finish()
        self.assertEqual(c.text, "abc")
        self.assertEqual(c.calls[0]["arguments"], {"command": "ls"})

    def test_tool_call_syntax_unchanged(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(
            '<tool_call>{"name": "bash", "arguments": {"command": "ls"}}</tool_call>'
        )
        p.finish()
        self.assertEqual(c.calls, [{"name": "bash", "arguments": {"command": "ls"}}])
        self.assertEqual(c.text, "")

    def test_invoke_allowed_tools_non_strict_drops_unauthorized(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, allowed_tools={"read"})
        p.feed(INVOKE_BASH)
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertEqual(c.text, "")

    def test_invoke_allowed_tools_strict_raises(self):
        c = Collector()
        p = ToolCallParser(
            c.on_content,
            c.on_call,
            strict_live=True,
            allowed_tools={"read"},
        )
        with self.assertRaises(LiveParserError):
            p.feed(INVOKE_BASH)
        self.assertEqual(c.calls, [])
        self.assertEqual(c.text, "")

    def test_invoke_unclosed_strict_raises_no_leak(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
        p.feed('pre <invoke name="bash"><parameter name="command">ls')
        with self.assertRaises(LiveParserError):
            p.finish()
        self.assertNotIn("<invoke", c.text)
        self.assertEqual(c.calls, [])

    def test_invoke_unclosed_non_strict_no_leak(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=False)
        p.feed('pre <invoke name="bash"><parameter name="command">ls')
        p.finish()
        self.assertNotIn("<invoke", c.text)
        self.assertNotIn("<parameter", c.text)
        self.assertEqual(c.calls, [])

    def test_invoke_inside_code_fence_is_text(self):
        raw = "Пример:\n```\n" + INVOKE_BASH + "\n```\n"
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(raw)
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertEqual(c.text, raw)

    def test_invoke_normalization_disabled_is_text(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, invoke_normalization_enabled=False)
        p.feed(INVOKE_BASH)
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertEqual(c.text, INVOKE_BASH)


class TestPassthroughInvokeNormalization(unittest.TestCase):
    def _parse_frames(self, out: list[bytes]) -> list[dict]:
        frames = []
        for raw_frame in out:
            text = raw_frame.decode("utf-8").strip()
            if text.startswith("data:") and text[5:].strip() != "[DONE]":
                frames.append(json.loads(text[5:]))
        return frames

    def test_relay_sse_invoke_becomes_tool_calls(self):
        events = (
            _chunk({"content": '<invoke name="bash">'})
            + _chunk({"content": '<parameter name="command">ls</parameter>'})
            + _chunk({"content": "</invoke>"})
            + _chunk({}, finish_reason="tool_calls")
            + DONE
        )
        out: list = []
        outcome = relay_sse(
            io.BytesIO(events).readline,
            out.append,
            tool_schemas=None,
            limits=PassthroughLimits(invoke_normalization_enabled=True),
        )
        self.assertTrue(outcome.done)
        body = b"".join(out)
        self.assertNotIn(b"<invoke", body)
        self.assertNotIn(b"<parameter", body)
        calls = []
        for payload in self._parse_frames(out):
            for ch in payload.get("choices") or ():
                calls.extend((ch.get("delta") or {}).get("tool_calls") or ())
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "bash")
        self.assertEqual(
            json.loads(calls[0]["function"]["arguments"]), {"command": "ls"}
        )
        self.assertEqual(outcome.tool_calls_published, 1)

    def test_relay_sse_terminal_chunk_emits_prefix_before_flushed_xml_and_tool_calls_and_finish(self):
        limits = PassthroughLimits(invoke_normalization_enabled=True)
        # 1. Terminal chunk with prefix + invoke XML + finish_reason="stop", both with DONE and EOF
        for tail, expect_done in ((DONE, True), (b"", False)):
            with self.subTest(expect_done=expect_done):
                events = _chunk({"content": "prefix " + INVOKE_BASH}, finish_reason="stop") + tail
                out: list[bytes] = []
                outcome = relay_sse(
                    io.BytesIO(events).readline,
                    out.append,
                    tool_schemas=None,
                    limits=limits,
                )
                self.assertEqual(outcome.done, expect_done)
                self.assertFalse(outcome.incomplete)
                frames = self._parse_frames(out)
                kinds = []
                acc_text = []
                acc_calls = []
                finish_reasons = []
                for f in frames:
                    ch = f["choices"][0]
                    delta = ch.get("delta") or {}
                    if delta.get("content"):
                        kinds.append("content")
                        acc_text.append(delta["content"])
                    if delta.get("tool_calls"):
                        kinds.append("tool_calls")
                        acc_calls.extend(delta["tool_calls"])
                    if ch.get("finish_reason"):
                        kinds.append("finish")
                        finish_reasons.append(ch["finish_reason"])
                self.assertEqual(kinds, ["content", "tool_calls", "finish"])
                self.assertEqual("".join(acc_text), "prefix ")
                self.assertEqual(len(acc_calls), 1)
                self.assertEqual(acc_calls[0]["function"]["name"], "bash")
                self.assertEqual(finish_reasons, ["stop"])

        # 2. Terminal chunk with prefix + held tag prefix ("hello <inv") + finish_reason="stop"
        for tail in (DONE, b""):
            with self.subTest(held_prefix_tail=tail):
                events = _chunk({"content": "hello <inv"}, finish_reason="stop") + tail
                out = []
                relay_sse(
                    io.BytesIO(events).readline,
                    out.append,
                    tool_schemas=None,
                    limits=limits,
                )
                frames = self._parse_frames(out)
                acc_text = []
                kinds = []
                for f in frames:
                    ch = f["choices"][0]
                    delta = ch.get("delta") or {}
                    if delta.get("content"):
                        kinds.append("content")
                        acc_text.append(delta["content"])
                    if ch.get("finish_reason"):
                        kinds.append("finish")
                self.assertEqual("".join(acc_text), "hello <inv")
                self.assertEqual(kinds[-1], "finish")

    def test_relay_sse_invoke_indices_do_not_collide_with_native_tool_calls(self):
        limits = PassthroughLimits(invoke_normalization_enabled=True)
        acc = ToolCallAccumulator(limits)
        self.assertEqual(acc.next_tool_index(0), 0)
        acc.add(0, [{"index": 0, "id": "c0", "function": {"name": "read", "arguments": '{"p":"a"}'}}])
        self.assertEqual(acc.next_tool_index(0), 1)
        self.assertEqual(acc.next_tool_index(1), 0)

        # Streaming: native tool_call at index 0 + XML invoke in same choice (choice 0) and choice 1
        events = (
            _frame({
                "id": "chatcmpl-1",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_native_0",
                                    "type": "function",
                                    "function": {"name": "read", "arguments": '{"path":"a"}'},
                                }
                            ]
                        },
                        "finish_reason": None,
                    },
                    {
                        "index": 1,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_native_1",
                                    "type": "function",
                                    "function": {"name": "read", "arguments": '{"path":"b"}'},
                                }
                            ]
                        },
                        "finish_reason": None,
                    },
                ],
            })
            + _frame({
                "id": "chatcmpl-1",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "m",
                "choices": [
                    {"index": 0, "delta": {"content": INVOKE_BASH}, "finish_reason": "tool_calls"},
                    {"index": 1, "delta": {"content": INVOKE_BASH}, "finish_reason": "tool_calls"},
                ],
            })
            + DONE
        )
        out: list[bytes] = []
        outcome = relay_sse(
            io.BytesIO(events).readline,
            out.append,
            tool_schemas=None,
            limits=limits,
        )
        self.assertTrue(outcome.done)
        by_choice: dict[int, list[dict]] = {0: [], 1: []}
        for f in self._parse_frames(out):
            for ch in f.get("choices") or ():
                tc = (ch.get("delta") or {}).get("tool_calls")
                if tc:
                    by_choice[ch["index"]].extend(tc)
        for ch_idx, expected_path in ((0, "a"), (1, "b")):
            calls = by_choice[ch_idx]
            self.assertEqual(len(calls), 2)
            self.assertEqual([c["index"] for c in calls], [0, 1])
            self.assertEqual(calls[0]["id"], f"call_native_{ch_idx}")
            self.assertEqual(calls[0]["function"]["name"], "read")
            self.assertEqual(json.loads(calls[0]["function"]["arguments"]), {"path": expected_path})
            self.assertEqual(calls[1]["function"]["name"], "bash")
            self.assertEqual(json.loads(calls[1]["function"]["arguments"]), {"command": "ls"})

    def test_sanitize_completion_body_extracts_invoke_and_preserves_native_tools(self):
        schemas = {
            "bash": {
                "type": "function",
                "function": {
                    "name": "bash",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "note": {"type": "string"},
                        },
                        "required": ["command"],
                    },
                },
            }
        }
        invoke_with_empty_opt = (
            '<invoke name="bash">'
            '<parameter name="command">ls</parameter>'
            '<parameter name="note"></parameter>'
            "</invoke>"
        )
        payload = {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Running command: " + invoke_with_empty_opt + '<invoke name="unclosed',
                        "tool_calls": [
                            {
                                "id": "call_native",
                                "type": "function",
                                "function": {
                                    "name": "bash",
                                    "arguments": json.dumps({"command": "pwd", "note": ""}),
                                },
                            }
                        ],
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        raw = json.dumps(payload).encode("utf-8")

        # When invoke_normalization_enabled=True: extracts invoke, strips XML without leak, preserves native, sanitizes both
        out_enabled = json.loads(
            sanitize_completion_body(
                raw,
                schemas,
                PassthroughLimits(invoke_normalization_enabled=True),
            )
        )
        msg = out_enabled["choices"][0]["message"]
        self.assertEqual(msg["content"], "Running command: ")
        self.assertNotIn("<invoke", msg["content"])
        self.assertNotIn("<parameter", msg["content"])
        self.assertEqual(len(msg["tool_calls"]), 2)
        self.assertEqual(msg["tool_calls"][0]["id"], "call_native")
        self.assertEqual(json.loads(msg["tool_calls"][0]["function"]["arguments"]), {"command": "pwd"})
        self.assertEqual(msg["tool_calls"][1]["function"]["name"], "bash")
        self.assertEqual(json.loads(msg["tool_calls"][1]["function"]["arguments"]), {"command": "ls"})

        # When invoke_normalization_enabled=False: XML in content is untouched
        payload_no_native = {
            "id": "chatcmpl-2",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Text " + INVOKE_BASH,
                        "tool_calls": None,
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        raw_no_native = json.dumps(payload_no_native).encode("utf-8")
        out_disabled = sanitize_completion_body(
            raw_no_native,
            schemas,
            PassthroughLimits(invoke_normalization_enabled=False),
        )
        self.assertIs(out_disabled, raw_no_native)


if __name__ == "__main__":
    unittest.main()
