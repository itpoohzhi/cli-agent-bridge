"""Тесты универсальной санитизации tool_calls (ADR 0010): пустые строки и `parallel`."""

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.backend_adapter import ToolCall, ToolFunction, TurnResult  # noqa: E402
from core.tool_emulation import (  # noqa: E402
    build_tool_schemas,
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
    def test_without_schema_route_fields_are_preserved(self):
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
                args_of(result[0]), args
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
    def test_empty_justification_removed_with_sandbox_permissions(self):
        # AD-002/THREAT-003: мост не фабрикует обоснование эскалации песочницы.
        args = {"command": "ls", "sandbox_permissions": "workspace-write", "justification": ""}
        for result in self.each("bash", args, {"bash": {"parameters": {"properties": {"justification": {"type": "string"}}}}}):
            self.assertEqual(
                args_of(result[0]), {"command": "ls", "sandbox_permissions": "workspace-write"}
            )

    def test_blank_justification_removed_with_sandbox_permissions(self):
        args = {"command": "ls", "sandbox_permissions": "x", "justification": "   "}
        for result in self.each("bash", args, {"bash": {"parameters": {"properties": {"justification": {"type": "string"}}}}}):
            self.assertNotIn("justification", args_of(result[0]))

    def test_without_schema_justification_is_preserved(self):
        for result in self.each("bash", {"command": "ls", "justification": ""}):
            self.assertEqual(args_of(result[0]), {"command": "ls", "justification": ""})

    def test_required_justification_is_kept_empty_not_fabricated(self):
        schemas = build_tool_schemas(
            [
                {
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "parameters": {
                            "type": "object",
                            "properties": {"justification": {"type": "string"}},
                            "required": ["justification"],
                        },
                    },
                }
            ]
        )
        result = sanitize_tool_call(
            as_dict("bash", {"command": "ls", "sandbox_permissions": "x", "justification": ""}),
            schemas,
        )
        self.assertEqual(args_of(result[0])["justification"], "")

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
            self.assertEqual(args_of(result[0]), {"prompt": "p", "provider": "", "model": ""})
            self.assertEqual(
                args_of(result[1]),
                {"command": "ls", "sandbox_permissions": "x", "justification": ""},
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


def _fn(name: str, properties: dict, required=None) -> dict:
    """OpenAI-описание инструмента для `build_tool_schemas`."""
    params: dict = {"type": "object", "properties": properties}
    if required is not None:
        params["required"] = required
    return {"type": "function", "function": {"name": name, "parameters": params}}


STR = {"type": "string"}


class TestSchemaAwareCleanup(SanitizerCase):
    SCHEMAS = {
        "write": {
            "parameters": {
                "required": ["path", "content"],
                "properties": {"path": STR, "content": STR, "note": STR, "mode": STR},
            }
        },
        "openai": {
            "function": {
                "parameters": {"required": ["path"], "properties": {"path": STR, "note": STR}}
            }
        },
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


class TestSchemaTolerance(SanitizerCase):
    """AC-01 (RW-003): толерантная проверка схем, fail-conservative."""

    def schemas(self, properties, required=None, name="tool"):
        return build_tool_schemas([_fn(name, properties, required)])

    def test_build_tool_schemas_maps_names(self):
        schemas = build_tool_schemas([_fn("a", {}), {"type": "function"}, "junk", _fn("b", {})])
        self.assertEqual(sorted(schemas), ["a", "b"])
        self.assertEqual(build_tool_schemas(None), {})

    def test_update_goal_schema_removes_empty_optional_strings(self):
        schemas = self.schemas(
            {"status": STR, "summary": STR, "note": STR}, required=["status"], name="update_goal"
        )
        args = {"status": "complete", "summary": "", "note": "  "}
        for result in self.each("update_goal", args, schemas):
            self.assertEqual(args_of(result[0]), {"status": "complete"})

    def test_type_array_with_string_is_string(self):
        schemas = self.schemas({"note": {"type": ["string", "null"]}, "n": {"type": ["integer"]}})
        for result in self.each("tool", {"note": "", "n": ""}, schemas):
            self.assertEqual(args_of(result[0]), {"n": ""})

    def test_non_string_type_is_kept(self):
        schemas = self.schemas({"note": {"type": "integer"}})
        for result in self.each("tool", {"note": ""}, schemas):
            self.assertEqual(args_of(result[0]), {"note": ""})

    def test_required_is_never_removed(self):
        schemas = self.schemas({"note": STR}, required=["note"])
        for result in self.each("tool", {"note": ""}, schemas):
            self.assertEqual(args_of(result[0]), {"note": ""})

    def test_enum_allowing_blank_is_kept(self):
        schemas = self.schemas(
            {
                "mode": {"type": "string", "enum": ["", "a"]},
                "pad": {"type": "string", "enum": ["a", "  "]},
                "plain": {"type": "string", "enum": ["a", "b"]},
            }
        )
        args = {"mode": "", "pad": "  ", "plain": ""}
        for result in self.each("tool", args, schemas):
            self.assertEqual(args_of(result[0]), {"mode": "", "pad": "  "})

    def test_const_allowing_blank_is_kept(self):
        schemas = self.schemas(
            {"empty": {"type": "string", "const": ""}, "other": {"type": "string", "const": "x"}}
        )
        for result in self.each("tool", {"empty": "", "other": ""}, schemas):
            self.assertEqual(args_of(result[0]), {"empty": ""})

    def test_unresolvable_schema_is_conservative(self):
        schemas = self.schemas(
            {
                "a": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "b": {"oneOf": [{"type": "string"}]},
                "c": {"$ref": "#/$defs/s"},
                "d": {"enum": ["x"]},
                "e": {},
            }
        )
        args = {key: "" for key in "abcde"}
        for result in self.each("tool", args, schemas):
            self.assertEqual(args_of(result[0]), args)

    def test_undeclared_property_is_kept(self):
        schemas = self.schemas({"known": STR})
        for result in self.each("tool", {"known": "", "ghost": ""}, schemas):
            self.assertEqual(args_of(result[0]), {"ghost": ""})

    def test_schema_without_properties_is_conservative(self):
        schemas = {"tool": {"function": {"name": "tool", "parameters": {"required": []}}}}
        for result in self.each("tool", {"note": ""}, schemas):
            self.assertEqual(args_of(result[0]), {"note": ""})

    def test_payload_fields_are_protected(self):
        schemas = self.schemas({"prompt": STR, "content": STR, "command": STR, "note": STR})
        args = {"prompt": "", "content": "", "command": "", "note": ""}
        for result in self.each("tool", args, schemas):
            self.assertEqual(
                args_of(result[0]), {"prompt": "", "content": "", "command": ""}
            )

    def test_goal_nested_objects_untouched(self):
        schemas = self.schemas({"meta": {"type": "object"}, "note": STR})
        args = {"meta": {"inner": ""}, "note": ""}
        for result in self.each("tool", args, schemas):
            self.assertEqual(args_of(result[0]), {"meta": {"inner": ""}})

    def test_route_fields_respect_required_and_enum(self):
        schemas = self.schemas(
            {"provider": STR, "model": {"type": "string", "enum": ["", "m"]}},
            required=["provider"],
        )
        for result in self.each("tool", {"provider": "", "model": ""}, schemas):
            self.assertEqual(args_of(result[0]), {"provider": "", "model": ""})

    def test_schema_cleanup_is_idempotent(self):
        schemas = self.schemas({"note": STR})
        once = sanitize_tool_calls_list([as_dict("tool", {"note": "", "x": 1})], schemas)
        self.assertEqual(sanitize_tool_calls_list(once, schemas), once)


class TestParallelLimits(SanitizerCase):
    """AC-02 (RW-005): лимиты веера параметризованы, ядро окружение не читает."""

    @staticmethod
    def fan(count: int) -> dict:
        return {
            "tool_uses": [
                {"recipient_name": "functions.t%d" % i, "parameters": {"i": i}}
                for i in range(count)
            ]
        }

    def test_parallel_limit_default_is_64_boundaries(self):
        for count, expected in ((63, 63), (64, 64), (65, 64), (200, 64)):
            with self.subTest(count=count):
                result = sanitize_tool_call(as_dict("parallel", self.fan(count)))
                self.assertEqual(len(result), expected)
                self.assertEqual(name_of(result[0]), "t0")
                self.assertEqual(name_of(result[-1]), "t%d" % (expected - 1))

    def test_parallel_limit_override_both_directions(self):
        call = as_dict("parallel", self.fan(10))
        self.assertEqual(len(sanitize_tool_call(call, max_parallel_calls=3)), 3)
        self.assertEqual(len(sanitize_tool_call(call, max_parallel_calls=10)), 10)
        self.assertEqual(len(sanitize_tool_call(call, max_parallel_calls=500)), 10)
        big = as_dict("parallel", self.fan(100))
        self.assertEqual(len(sanitize_tool_call(big, max_parallel_calls=100)), 100)

    def test_parallel_limit_keeps_accumulated_calls_for_tool_call_objects(self):
        call = as_tool_call("parallel", self.fan(5))
        result = sanitize_tool_call(call, max_parallel_calls=2)
        self.assertEqual([name_of(c) for c in result], ["t0", "t1"])
        self.assertTrue(all(isinstance(c, ToolCall) for c in result))

    def test_parallel_limit_nonpositive_degrades_to_one(self):
        call = as_dict("parallel", self.fan(4))
        self.assertEqual(len(sanitize_tool_call(call, max_parallel_calls=0)), 1)

    def test_parallel_limit_counts_nested_leaves(self):
        inner = {"recipient_name": "parallel", "parameters": self.fan(5)}
        outer = {"tool_uses": [inner, {"recipient_name": "tail", "parameters": {}}]}
        result = sanitize_tool_call(as_dict("parallel", outer), max_parallel_calls=3)
        self.assertEqual([name_of(c) for c in result], ["t0", "t1", "t2"])

    def test_parallel_limit_depth_is_parameter(self):
        deep = {"tool_uses": [{"recipient_name": "leaf", "parameters": {}}]}
        for _ in range(3):
            deep = {"tool_uses": [{"recipient_name": "parallel", "parameters": deep}]}
        call = as_dict("parallel", deep)
        self.assertEqual([name_of(c) for c in sanitize_tool_call(call)], ["leaf"])
        shallow = sanitize_tool_call(call, max_parallel_depth=1)
        self.assertEqual([name_of(c) for c in shallow], ["parallel"])

    def test_parallel_limit_list_per_parallel_and_reindexes(self):
        calls = [as_dict("parallel", self.fan(5), 0), as_dict("bash", {"command": "x"}, 1)]
        result = sanitize_tool_calls_list(calls, max_parallel_calls=2)
        self.assertEqual([name_of(c) for c in result], ["t0", "t1", "bash"])
        self.assertEqual([c["index"] for c in result], [0, 1, 2])

    def test_parallel_limit_core_does_not_read_environment(self):
        source = (Path(__file__).resolve().parent.parent / "core" / "tool_emulation.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("os.environ", source)
        self.assertNotIn("getenv", source)

    def test_parallel_limit_finalize_turn_passes_limit(self):
        parallel = {"tool_uses": [{"recipient_name": "t%d" % i, "parameters": {}} for i in range(4)]}
        text = "<tool_call>%s</tool_call>" % json.dumps({"name": "parallel", "arguments": parallel})
        result = finalize_turn(
            TurnResult(state="ok", rc=0, text=text), True, sanitize=True, max_parallel_calls=2
        )
        self.assertEqual([c.function.name for c in result.tool_calls], ["t0", "t1"])


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
        self.assertEqual(json.loads(result.tool_calls[0].function.arguments), {"prompt": "p", "provider": ""})
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


def test_no_schema_never_fabricates_or_removes_escalation_justification():
    args = {"provider": "", "model": "", "reasoning_effort": "", "justification": "", "sandbox_permissions": "require_escalated"}
    assert args_of(sanitize_tool_call(as_dict("bash", args))[0]) == args


def test_composed_schemas_are_conservative_even_with_string_type():
    for keyword, value in (("$ref", "#/$defs/s"), ("anyOf", [{"const": ""}]), ("oneOf", [{"const": ""}])):
        schemas = build_tool_schemas([_fn("tool", {"provider": {"type": "string", keyword: value}})])
        assert args_of(sanitize_tool_call(as_dict("tool", {"provider": ""}), schemas)[0]) == {"provider": ""}
    schemas = {"tool": {"parameters": {"anyOf": [{"required": ["note"]}], "properties": {"note": STR}}}}
    assert args_of(sanitize_tool_call(as_dict("tool", {"note": ""}), schemas)[0]) == {"note": ""}


def test_sanitizer_loads_each_arguments_string_once():
    from unittest.mock import patch
    call = as_dict("tool", {"note": ""})
    schemas = build_tool_schemas([_fn("tool", {"note": STR})])
    original_loads = json.loads
    with patch("core.tool_emulation.json.loads", wraps=original_loads) as loads:
        result = sanitize_tool_call(call, schemas)
    assert loads.call_count == 1
    assert args_of(result[0]) == {}


def test_perf_ten_thousand_turns_with_64_calls():
    import time
    schemas = build_tool_schemas([_fn("tool", {"note": STR})])
    calls = [as_dict("tool", {"note": "", "content": ""}, i) for i in range(64)]
    durations = []
    for _ in range(10_000):
        start = time.perf_counter()
        result = sanitize_tool_calls_list(calls, schemas)
        durations.append(time.perf_counter() - start)
    assert len(result) == 64
    p99 = sorted(durations)[9899]
    assert p99 <= 0.005, f"p99={p99 * 1000:.3f}ms exceeds 5ms for 64 calls"


def test_zen_clean_import_and_single_sanitizer_call(monkeypatch) -> None:
    import ast
    path = Path(__file__).resolve().parents[1] / "bridges/opencode-zen-bridge/server.py"
    source = path.read_text()
    calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sanitize_tool_calls_list"]
    assert len(calls) == 1
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p not in {str(path.parent), str(path.parents[2])}])
    namespace = {"__file__": str(path), "__name__": "zen_regression"}
    exec(compile(source.split("\nHOST =", 1)[0], str(path), "exec"), namespace)
    assert sys.path[0] == str(path.parents[2])
    call = as_dict("tool", {"note": "", "content": ""})
    schemas = build_tool_schemas([_fn("tool", {"note": STR, "content": STR})])
    assert args_of(namespace["_normalize_tool_calls"]([call], schemas)[0]) == {"content": ""}
    namespace["BRIDGE_SANITIZE_TOOL_CALLS"] = False
    assert namespace["_normalize_tool_calls"]([call], schemas) == [call]
