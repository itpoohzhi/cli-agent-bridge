"""Тесты универсальной санитизации tool_calls (ADR 0010): пустые строки и `parallel`."""

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.backend_adapter import ToolCall, ToolFunction, TurnResult  # noqa: E402
from core.tool_emulation import (  # noqa: E402
    JUSTIFICATION_FALLBACK,
    finalize_turn,
    sanitize_tool_call,
    sanitize_tool_calls_list,
)

CALL_ID = re.compile(r"^call_[0-9a-f]{24}$")


def as_dict(name: str, arguments, index: int = 0) -> dict:
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    return {
        "index": index,
        "id": f"call_src{index}",
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def as_tool_call(name: str, arguments, index: int = 0) -> ToolCall:
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    return ToolCall(index, f"call_src{index}", ToolFunction(name, arguments))


def name_of(call) -> str:
    return call.function.name if isinstance(call, ToolCall) else call["function"]["name"]


def args_of(call) -> dict:
    raw = call.function.arguments if isinstance(call, ToolCall) else call["function"]["arguments"]
    return json.loads(raw)


def id_of(call) -> str:
    return call.id if isinstance(call, ToolCall) else call["id"]


class SanitizerCase(unittest.TestCase):
    """Каждый сценарий прогоняется для ToolCall и для dict."""

    makers = (("ToolCall", as_tool_call), ("dict", as_dict))

    def each(self, name, arguments, schemas=None):
        for label, make in self.makers:
            with self.subTest(kind=label):
                source = make(name, arguments)
                result = sanitize_tool_call(source, schemas)
                self.assertTrue(all(type(r) is type(source) for r in result))
                yield result


class TestEmptyRouteFields(SanitizerCase):
    def test_empty_route_fields_removed_for_subagent(self):
        args = {
            "cwd": "/tmp",
            "description": "d",
            "prompt": "p",
            "provider": "",
            "model": "  ",
            "reasoning_effort": "",
        }
        for result in self.each("subagent", args):
            self.assertEqual(len(result), 1)
            self.assertEqual(
                args_of(result[0]), {"cwd": "/tmp", "description": "d", "prompt": "p"}
            )

    def test_valid_route_fields_preserved(self):
        args = {"prompt": "p", "provider": "custom", "model": "gpt-5", "reasoning_effort": "high"}
        for result in self.each("subagent", args):
            self.assertEqual(args_of(result[0]), args)

    def test_unchanged_arguments_string_is_kept_verbatim(self):
        raw = '{"command":   "ls"}'
        for result in self.each("bash", raw):
            self.assertEqual(
                result[0].function.arguments
                if isinstance(result[0], ToolCall)
                else result[0]["function"]["arguments"],
                raw,
            )

    def test_invalid_json_arguments_untouched(self):
        for result in self.each("bash", "{not json"):
            raw = (
                result[0].function.arguments
                if isinstance(result[0], ToolCall)
                else result[0]["function"]["arguments"]
            )
            self.assertEqual(raw, "{not json")

    def test_original_call_is_not_mutated(self):
        source = as_dict("subagent", {"provider": "", "prompt": "p"})
        before = json.dumps(source, sort_keys=True)
        sanitize_tool_call(source)
        self.assertEqual(json.dumps(source, sort_keys=True), before)


class TestJustification(SanitizerCase):
    def test_empty_justification_gets_fallback_with_sandbox_permissions(self):
        args = {"command": "ls", "sandbox_permissions": "workspace-write", "justification": ""}
        for result in self.each("bash", args):
            self.assertEqual(args_of(result[0])["justification"], JUSTIFICATION_FALLBACK)
            self.assertEqual(args_of(result[0])["sandbox_permissions"], "workspace-write")

    def test_empty_justification_removed_without_sandbox_permissions(self):
        for result in self.each("bash", {"command": "ls", "justification": ""}):
            self.assertEqual(args_of(result[0]), {"command": "ls"})

    def test_filled_justification_preserved(self):
        args = {"command": "ls", "sandbox_permissions": "x", "justification": "нужно"}
        for result in self.each("bash", args):
            self.assertEqual(args_of(result[0]), args)


class TestParallelUnpacking(SanitizerCase):
    def parallel_args(self):
        return {
            "tool_uses": [
                {
                    "recipient_name": "functions.subagent",
                    "parameters": {"prompt": "p", "provider": "", "model": ""},
                },
                {
                    "name": "bash",
                    "arguments": json.dumps(
                        {"command": "ls", "sandbox_permissions": "x", "justification": ""}
                    ),
                },
            ]
        }

    def test_parallel_unpacked_into_top_level_calls(self):
        for result in self.each("parallel", self.parallel_args()):
            self.assertEqual([name_of(c) for c in result], ["subagent", "bash"])
            self.assertTrue(all(CALL_ID.match(id_of(c)) for c in result))
            self.assertNotIn("call_src0", [id_of(c) for c in result])
            self.assertEqual(args_of(result[0]), {"prompt": "p"})
            self.assertEqual(
                args_of(result[1]),
                {"command": "ls", "sandbox_permissions": "x", "justification": JUSTIFICATION_FALLBACK},
            )

    def test_parallel_supports_calls_key_and_unique_ids(self):
        args = {"calls": [{"name": "a", "parameters": {}}, {"name": "b", "parameters": {}}]}
        for result in self.each("parallel", args):
            self.assertEqual([name_of(c) for c in result], ["a", "b"])
            self.assertEqual(len({id_of(c) for c in result}), 2)

    def test_parallel_without_nested_calls_left_as_is(self):
        for result in self.each("parallel", {"unexpected": 1}):
            self.assertEqual(name_of(result[0]), "parallel")

    def test_list_reindexes_flattened_calls(self):
        calls = [
            as_dict("bash", {"command": "a"}, 0),
            as_dict("parallel", self.parallel_args(), 1),
            as_dict("bash", {"command": "b"}, 2),
        ]
        result = sanitize_tool_calls_list(calls)
        self.assertEqual([c["index"] for c in result], [0, 1, 2, 3])
        self.assertEqual([name_of(c) for c in result], ["bash", "subagent", "bash", "bash"])

    def test_sanitization_is_idempotent(self):
        once = sanitize_tool_calls_list([as_dict("parallel", self.parallel_args())])
        twice = sanitize_tool_calls_list(once)
        self.assertEqual(once, twice)


class TestSchemaAwareCleanup(SanitizerCase):
    SCHEMAS = {
        "write": {"parameters": {"required": ["path", "content"]}},
        "openai": {"function": {"parameters": {"required": ["path"]}}},
    }

    def test_required_empty_kept_optional_empty_removed(self):
        args = {"path": "/a", "content": "", "note": "", "mode": "w"}
        for result in self.each("write", args, self.SCHEMAS):
            self.assertEqual(args_of(result[0]), {"path": "/a", "content": "", "mode": "w"})

    def test_openai_style_schema_is_understood(self):
        for result in self.each("openai", {"path": "", "note": ""}, self.SCHEMAS):
            self.assertEqual(args_of(result[0]), {"path": ""})

    def test_without_schema_unknown_empty_fields_are_kept(self):
        for result in self.each("write", {"path": "/a", "content": ""}):
            self.assertEqual(args_of(result[0]), {"path": "/a", "content": ""})


class TestFinalizeTurn(unittest.TestCase):
    TEXT = (
        '<tool_call>{"name": "subagent", "arguments": {"prompt": "p", "provider": ""}}</tool_call>'
        '<tool_call>{"name": "parallel", "arguments": {"tool_uses": '
        '[{"recipient_name": "bash", "parameters": {"command": "ls"}}]}}</tool_call>'
    )

    def run_turn(self, sanitize: bool):
        raw = TurnResult(state="ok", rc=0, text=self.TEXT)
        return finalize_turn(raw, True, sanitize=sanitize)

    def test_sanitize_enabled(self):
        result = self.run_turn(True)
        self.assertEqual([c.function.name for c in result.tool_calls], ["subagent", "bash"])
        self.assertEqual([c.index for c in result.tool_calls], [0, 1])
        self.assertEqual(json.loads(result.tool_calls[0].function.arguments), {"prompt": "p"})
        event_calls = [e.value for e in result.events if e.kind == "tool_call"]
        self.assertEqual(event_calls, list(result.tool_calls))

    def test_sanitize_disabled_keeps_legacy_behaviour(self):
        result = self.run_turn(False)
        self.assertEqual([c.function.name for c in result.tool_calls], ["subagent", "parallel"])
        self.assertEqual(
            json.loads(result.tool_calls[0].function.arguments), {"prompt": "p", "provider": ""}
        )


if __name__ == "__main__":
    unittest.main()
