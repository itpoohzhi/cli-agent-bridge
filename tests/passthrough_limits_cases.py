"""Существующие оракулы passthrough, выделенные для сохранения границ legacy."""

from __future__ import annotations

from adapters.passthrough_adapter import AccumulatorOverflow
from adapters.passthrough_adapter import PassthroughLimits
from adapters.passthrough_adapter import ProcessBudget
from adapters.passthrough_adapter import ToolCallAccumulator
from adapters.passthrough_adapter import sanitize_completion_body
from tests.passthrough_stream_testlib import DONE
from tests.passthrough_stream_testlib import SCHEMAS
from tests.passthrough_stream_testlib import args_of
from tests.passthrough_stream_testlib import finish
from tests.passthrough_stream_testlib import payloads
from tests.passthrough_stream_testlib import published_calls
from tests.passthrough_stream_testlib import run_stream
from tests.passthrough_stream_testlib import tool_delta
from typing import Any
import json
import server
import unittest.mock


class TestAccumulatorLimits(unittest.TestCase):
    def acc(self, **kw: Any) -> Any:
        return ToolCallAccumulator(PassthroughLimits(**kw))

    def test_accumulator_bytes_boundary_minus_equal_plus(self) -> None:
        base = len(b"c") + len(b"n")
        for extra, ok in ((-1, True), (0, True), (1, False)):
            with self.subTest(extra=extra):
                limit = base + 10
                acc = self.acc(accumulator_max_bytes=limit)
                args = "x" * (10 + extra)
                delta = [
                    {
                        "index": 0,
                        "id": "c",
                        "function": {"name": "n", "arguments": args},
                    }
                ]
                if ok:
                    acc.add(0, delta)
                    self.assertLessEqual(acc.size_bytes, limit)
                else:
                    with self.assertRaises(AccumulatorOverflow):
                        acc.add(0, delta)

    def test_accumulator_keys_limit(self) -> None:
        acc = self.acc(accumulator_max_keys=2)
        acc.add(0, [{"index": 0, "id": "a"}, {"index": 1, "id": "b"}])
        acc.add(0, [{"index": 1, "function": {"arguments": "x"}}])
        with self.assertRaises(AccumulatorOverflow):
            acc.add(1, [{"index": 0, "id": "c"}])

    def test_accumulator_process_budget_is_shared_and_released(self) -> None:
        process = ProcessBudget(10)
        first = ToolCallAccumulator(PassthroughLimits(), process)
        second = ToolCallAccumulator(PassthroughLimits(), process)
        first.add(0, [{"index": 0, "function": {"arguments": "x" * 8}}])
        with self.assertRaises(AccumulatorOverflow):
            second.add(0, [{"index": 0, "function": {"arguments": "y" * 3}}])
        first.close()
        self.assertEqual(process.used, 0)
        second.add(0, [{"index": 0, "function": {"arguments": "y" * 3}}])
        second.close()
        self.assertEqual(process.used, 0)

    def test_accumulator_env_override_both_directions(self) -> None:
        small = PassthroughLimits.from_env({"BRIDGE_ACCUMULATOR_MAX_BYTES": "4"})
        large = PassthroughLimits.from_env(
            {"BRIDGE_ACCUMULATOR_MAX_BYTES": str(64 * 1024 * 1024)}
        )
        payload = [{"index": 0, "function": {"arguments": "x" * 100}}]
        with self.assertRaises(AccumulatorOverflow):
            ToolCallAccumulator(small).add(0, payload)
        ToolCallAccumulator(large).add(0, payload)

    def test_stream_overflow_emits_error_frame_and_done_without_partial_calls(
        self,
    ) -> None:
        events = (
            tool_delta(0, 0, call_id="c", name="subagent", args="{" + "x" * 100)
            + finish(0)
            + DONE
        )
        process = ProcessBudget(10000)
        outcome, out = run_stream(
            events, limits=PassthroughLimits(accumulator_max_bytes=50), process=process
        )
        self.assertTrue(outcome.overflow)
        self.assertEqual(published_calls(out), [])
        self.assertEqual(
            payloads(out)[-1]["error"]["code"], "upstream_response_too_large"
        )
        self.assertTrue(b"".join(out).endswith(DONE))
        self.assertEqual(process.used, 0)

    def test_accumulator_composite_key_pop_orders_by_tool_index(self) -> None:
        acc = self.acc()
        acc.add(1, [{"index": 0, "id": "b0", "function": {"name": "n"}}])
        acc.add(
            0,
            [
                {"index": 1, "id": "a1", "function": {"name": "n"}},
                {"index": 0, "id": "a0"},
            ],
        )
        self.assertEqual([c["id"] for c in acc.pop_choice(0)], ["a0", "a1"])
        self.assertEqual(acc.pending_choices(), [1])


class TestLimitsFromEnv(unittest.TestCase):
    def test_defaults(self) -> None:
        limits = PassthroughLimits.from_env({})
        self.assertEqual(limits.max_parallel_calls, 64)
        self.assertEqual(limits.max_parallel_depth, 8)
        self.assertEqual(limits.max_body_bytes, 16777216)
        self.assertEqual(limits.accumulator_max_bytes, 8388608)
        self.assertEqual(limits.accumulator_max_keys, 64)
        self.assertEqual(limits.accumulator_max_process_bytes, 33554432)

    def test_every_limit_is_overridable_from_env(self) -> None:
        limits = PassthroughLimits.from_env(
            {
                "BRIDGE_MAX_PARALLEL_CALLS": "3",
                "BRIDGE_MAX_PARALLEL_DEPTH": "2",
                "BRIDGE_PASSTHROUGH_MAX_BODY_BYTES": "100",
                "BRIDGE_ACCUMULATOR_MAX_BYTES": "200",
                "BRIDGE_ACCUMULATOR_MAX_KEYS": "5",
                "BRIDGE_ACCUMULATOR_MAX_PROCESS_BYTES": "300",
                "BRIDGE_PASSTHROUGH_CONNECT_TIMEOUT_S": "1.5",
                "BRIDGE_PASSTHROUGH_READ_TIMEOUT_S": "7",
            }
        )
        self.assertEqual(
            (
                limits.max_parallel_calls,
                limits.max_parallel_depth,
                limits.max_body_bytes,
                limits.accumulator_max_bytes,
                limits.accumulator_max_keys,
                limits.accumulator_max_process_bytes,
                limits.connect_timeout_s,
                limits.read_timeout_s,
            ),
            (3, 2, 100, 200, 5, 300, 1.5, 7.0),
        )

    def test_invalid_values_fall_back_to_defaults(self) -> None:
        for bad in ("", "abc", "0", "-5", "1.5"):
            with self.subTest(bad=bad):
                self.assertEqual(
                    PassthroughLimits.from_env(
                        {"BRIDGE_MAX_PARALLEL_CALLS": bad}
                    ).max_parallel_calls,
                    64,
                )

    def test_server_passes_env_limits_to_core(self) -> None:
        self.assertEqual(
            server._SANITIZE_LIMITS["max_parallel_calls"],
            server.BRIDGE_LIMITS.max_parallel_calls,
        )


class TestNonStreamBody(unittest.TestCase):
    def body(self, calls: Any, **extra: Any) -> Any:
        return json.dumps(
            {
                "id": "x",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": calls,
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"total_tokens": 1},
                **extra,
            }
        ).encode("utf-8")

    def call(self, args: Any, name: Any = "subagent", call_id: Any = "c1") -> Any:
        return {
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)},
        }

    def test_empty_optional_strings_removed(self) -> None:
        out = sanitize_completion_body(
            self.body([self.call({"prompt": "p", "provider": "", "note": ""})]),
            SCHEMAS,
            PassthroughLimits(),
        )
        data = json.loads(out)
        self.assertEqual(
            args_of(data["choices"][0]["message"]["tool_calls"][0]), {"prompt": "p"}
        )
        self.assertEqual(data["usage"], {"total_tokens": 1})

    def test_unchanged_body_is_byte_identical(self) -> None:
        raw = self.body([self.call({"prompt": "p"})])
        self.assertIs(sanitize_completion_body(raw, SCHEMAS, PassthroughLimits()), raw)

    def test_invalid_json_and_foreign_shapes_untouched(self) -> None:
        for raw in (
            b"not json",
            b"[]",
            b'{"choices": 5}',
            b'{"error": {"message": "x"}}',
        ):
            with self.subTest(raw=raw):
                self.assertIs(
                    sanitize_completion_body(raw, SCHEMAS, PassthroughLimits()), raw
                )

    def test_parallel_unpacked_without_index_key(self) -> None:
        parallel = {
            "tool_uses": [
                {
                    "recipient_name": "subagent",
                    "parameters": {"prompt": "p", "provider": ""},
                }
            ]
        }
        out = json.loads(
            sanitize_completion_body(
                self.body([self.call(parallel, name="parallel")]),
                SCHEMAS,
                PassthroughLimits(),
            )
        )
        calls = out["choices"][0]["message"]["tool_calls"]
        self.assertEqual([c["function"]["name"] for c in calls], ["subagent"])
        self.assertNotIn("index", calls[0])
        self.assertEqual(args_of(calls[0]), {"prompt": "p"})

    def test_parallel_limit_applied(self) -> None:
        parallel = {
            "tool_uses": [
                {"recipient_name": "t%d" % i, "parameters": {}} for i in range(70)
            ]
        }
        raw = self.body([self.call(parallel, name="parallel")])
        calls = json.loads(sanitize_completion_body(raw, {}, PassthroughLimits()))[
            "choices"
        ][0]["message"]["tool_calls"]
        self.assertEqual(len(calls), 64)
        calls = json.loads(
            sanitize_completion_body(raw, {}, PassthroughLimits(max_parallel_calls=70))
        )["choices"][0]["message"]["tool_calls"]
        self.assertEqual(len(calls), 70)
