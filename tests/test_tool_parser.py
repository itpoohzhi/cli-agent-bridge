"""Unit-тесты ToolCallParser и _tools_section моста droid-bridge (импорт из server.py)."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import (  # noqa: E402
    TOOL_CALL_CLOSE,
    TOOL_CALL_OPEN,
    ToolCallParser,
    _messages_to_prompt,
    _parse_tool_call_block,
    _tools_section,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
            },
        },
    }
]


class Collector:
    def __init__(self):
        self.content = []
        self.calls = []

    def on_content(self, text):
        self.content.append(text)

    def on_call(self, call):
        self.calls.append(call)


class TestToolCallParser(unittest.TestCase):
    def test_plain_text_passthrough(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed("Hello, ")
        p.feed("world")
        p.finish()
        self.assertEqual("".join(c.content), "Hello, world")
        self.assertEqual(c.calls, [])

    def test_single_call_split_across_deltas(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed("Pre text ")
        p.feed(TOOL_CALL_OPEN[:5])  # разрыв прямо внутри тега
        p.feed(TOOL_CALL_OPEN[5:])
        p.feed('{"name": "get_we')
        p.feed('ather", "arguments": {"city": "Berlin"}}')
        p.feed(TOOL_CALL_CLOSE)
        p.finish()
        self.assertEqual("".join(c.content), "Pre text ")
        self.assertEqual(
            c.calls, [{"name": "get_weather", "arguments": {"city": "Berlin"}}]
        )

    def test_multiple_calls_in_row(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(
            TOOL_CALL_OPEN
            + '{"name": "a", "arguments": {}}'
            + TOOL_CALL_CLOSE
            + TOOL_CALL_OPEN
            + '{"name": "b"}'
            + TOOL_CALL_CLOSE
        )
        p.finish()
        self.assertEqual(
            c.calls, [{"name": "a", "arguments": {}}, {"name": "b", "arguments": {}}]
        )
        self.assertEqual("".join(c.content), "")

    def test_close_tag_inside_string_is_not_boundary(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        payload = json.dumps(
            {"name": "t", "arguments": {"text": "x " + TOOL_CALL_CLOSE + " y"}}
        )
        p.feed(TOOL_CALL_OPEN + payload + TOOL_CALL_CLOSE)
        p.finish()
        self.assertEqual(
            c.calls,
            [{"name": "t", "arguments": {"text": "x " + TOOL_CALL_CLOSE + " y"}}],
        )

    def test_escaped_quote_does_not_end_string(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(
            TOOL_CALL_OPEN
            + '{"name": "t", "arguments": {"q": "a\\"b"}}'
            + TOOL_CALL_CLOSE
        )
        p.finish()
        self.assertEqual(c.calls, [{"name": "t", "arguments": {"q": 'a"b'}}])

    def test_invalid_block_falls_back_to_text(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(TOOL_CALL_OPEN + "not json" + TOOL_CALL_CLOSE)
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertIn("not json", "".join(c.content))

    def test_unclosed_block_flushed_as_text_on_finish(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed("tail " + TOOL_CALL_OPEN + '{"name": "t"')
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertIn('{"name": "t"', "".join(c.content))

    def test_pending_prefix_not_emitted_early(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed("abc<tool_")
        self.assertEqual("".join(c.content), "abc")  # хвост удержан
        p.feed("call>" + '{"name": "t"}' + TOOL_CALL_CLOSE)
        p.finish()
        self.assertEqual(c.calls, [{"name": "t", "arguments": {}}])
        self.assertEqual("".join(c.content), "abc")

    def test_non_object_arguments_rejected(self):
        self.assertIsNone(_parse_tool_call_block('{"name": "t", "arguments": "[1,2]"}'))
        self.assertEqual(
            _parse_tool_call_block('{"name": "t"}'), {"name": "t", "arguments": {}}
        )

    def test_code_fence_stripped(self):
        inner = "```json\n" + '{"name": "t", "arguments": {"a": 1}}' + "\n```"
        self.assertEqual(
            _parse_tool_call_block(inner), {"name": "t", "arguments": {"a": 1}}
        )


class TestToolsSection(unittest.TestCase):
    def test_protocol_and_schema_present(self):
        section = _tools_section(TOOLS, None)
        self.assertIn("# Tool calling protocol", section)
        self.assertIn(
            TOOL_CALL_OPEN
            + '{"name": "<tool_name>", "arguments": {<json>}}'
            + TOOL_CALL_CLOSE,
            section,
        )
        self.assertIn("- get_weather: Get current weather", section)
        self.assertIn('"city"', section)
        self.assertNotIn("You MUST", section)

    def test_tool_choice_required(self):
        self.assertIn(
            "You MUST call at least one tool now.", _tools_section(TOOLS, "required")
        )

    def test_forced_function(self):
        self.assertIn(
            'You MUST call the tool "get_weather" now.',
            _tools_section(
                TOOLS, {"type": "function", "function": {"name": "get_weather"}}
            ),
        )


class TestPromptRendering(unittest.TestCase):
    def test_tool_history_roundtrip(self):
        prompt = _messages_to_prompt(
            [
                {"role": "user", "content": "Weather?"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city": "Berlin"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call_1",
                    "name": "get_weather",
                    "content": "18C, rain",
                },
            ],
            TOOLS,
        )
        self.assertIn("[tool result call_1] (get_weather)", prompt)
        self.assertIn("18C, rain", prompt)
        self.assertIn(TOOL_CALL_OPEN, prompt)
        self.assertIn('"city": "Berlin"', prompt)

    def test_tool_choice_none_omits_section(self):
        prompt = _messages_to_prompt([{"role": "user", "content": "hi"}], TOOLS, "none")
        self.assertNotIn("# Tool calling protocol", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
