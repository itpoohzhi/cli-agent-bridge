"""Passthrough-шов (ADR 0011 AD-003/AD-005/AD-007): стриминг, составной ключ, EOF, лимиты, маршрут."""

import copy
import http.client
import io
import json
import socket
import sys
import threading
from types import SimpleNamespace
import unittest
import unittest.mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from core.backend_adapter import TurnResult  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402
from adapters.passthrough_adapter import (  # noqa: E402
    AccumulatorOverflow,
    ClientGone,
    PassthroughAdapter,
    PassthroughLimits,
    ProcessBudget,
    ResponseSink,
    ToolCallAccumulator,
    relay_sse,
    sanitize_completion_body,
)
from bridge_testlib import BridgeCase, load_raw_fleet  # noqa: E402
from core.backend_adapter import AdapterRegistry, FleetViolation, build_catalog  # noqa: E402

STR = {"type": "string"}
SCHEMAS = {
    "subagent": {
        "type": "function",
        "function": {
            "name": "subagent",
            "parameters": {
                "type": "object",
                "properties": {"prompt": STR, "provider": STR, "note": STR},
                "required": ["prompt"],
            },
        },
    }
}
TOOLS = list(SCHEMAS.values())


# ---- SSE-помощники ------------------------------------------------------------------
def frame(payload) -> bytes:
    return b"data: " + json.dumps(payload).encode("utf-8") + b"\n\n"


DONE = b"data: [DONE]\n\n"


def chunk(choices, **extra) -> dict:
    return {"id": "chatcmpl-1", "object": "chat.completion.chunk", "created": 1, "model": "m",
            "choices": choices, **extra}


def content(text: str, index: int = 0) -> bytes:
    return frame(chunk([{"index": index, "delta": {"content": text}, "finish_reason": None}]))


def tool_delta(index: int, tc_index: int, *, call_id=None, name=None, args=None) -> bytes:
    delta: dict = {"index": tc_index}
    if call_id is not None:
        delta["id"] = call_id
        delta["type"] = "function"
    function: dict = {}
    if name is not None:
        function["name"] = name
    if args is not None:
        function["arguments"] = args
    if function:
        delta["function"] = function
    return frame(chunk([{"index": index, "delta": {"tool_calls": [delta]}, "finish_reason": None}]))


def finish(index: int, reason: str = "tool_calls", **extra) -> bytes:
    return frame(chunk([{"index": index, "delta": {}, "finish_reason": reason}], **extra))


def run_stream(events: bytes, limits=None, schemas=None, **kwargs):
    out: list = []
    outcome = relay_sse(
        io.BytesIO(events).readline,
        out.append,
        tool_schemas=schemas if schemas is not None else SCHEMAS,
        limits=limits or PassthroughLimits(),
        **kwargs,
    )
    return outcome, out


def payloads(frames) -> list:
    """Разобранные data-кадры (без [DONE])."""
    parsed = []
    for raw in frames:
        text = raw.decode("utf-8").strip()
        if text.startswith("data:") and text[5:].strip() != "[DONE]":
            parsed.append(json.loads(text[5:]))
    return parsed


def published_calls(frames, choice: int = 0) -> list:
    calls = []
    for item in payloads(frames):
        for ch in item.get("choices") or ():
            if ch.get("index") == choice:
                calls.extend((ch.get("delta") or {}).get("tool_calls") or ())
    return calls


def args_of(call) -> dict:
    return json.loads(call["function"]["arguments"])


class TestStreamRelay(unittest.TestCase):
    def test_stream_content_passes_verbatim_in_order(self):
        events = content("a") + content("b") + finish(0, "stop") + DONE
        outcome, out = run_stream(events)
        self.assertEqual(b"".join(out), events)
        self.assertTrue(outcome.done)
        self.assertFalse(outcome.incomplete)

    def test_stream_non_data_events_and_comments_are_forwarded(self):
        events = b": keepalive\n\n" + content("a") + finish(0, "stop") + DONE
        _, out = run_stream(events)
        self.assertEqual(b"".join(out), events)

    def test_stream_tool_calls_buffered_sanitized_published_before_terminal(self):
        events = (
            content("x")
            + tool_delta(0, 0, call_id="call_a", name="subagent", args='{"prompt":"p",')
            + tool_delta(0, 0, args='"provider":"","note":" "}')
            + finish(0, usage={"total_tokens": 3})
            + DONE
        )
        outcome, out = run_stream(events)
        frames = payloads(out)
        # tool_call-дельты сами по себе клиенту не уходят: вызов приходит одним кадром перед финалом
        self.assertEqual(len(published_calls(out)), 1)
        call = published_calls(out)[0]
        self.assertEqual((call["id"], call["index"], call["function"]["name"]), ("call_a", 0, "subagent"))
        self.assertEqual(args_of(call), {"prompt": "p"})
        order = [
            "content" if (f["choices"][0]["delta"].get("content")) else
            "calls" if (f["choices"][0]["delta"].get("tool_calls")) else
            "terminal" if f["choices"][0].get("finish_reason") else "other"
            for f in frames
        ]
        self.assertEqual(order, ["content", "calls", "terminal"])
        self.assertEqual(frames[-1]["usage"], {"total_tokens": 3})
        self.assertEqual(out[-1], DONE)
        self.assertEqual(outcome.tool_calls_published, 1)

    def test_stream_terminal_chunk_carrying_tool_calls_is_handled(self):
        terminal = frame(chunk([{
            "index": 0,
            "delta": {"tool_calls": [{"index": 0, "id": "c1", "type": "function",
                                       "function": {"name": "subagent", "arguments": '{"prompt":"p","provider":""}'}}]},
            "finish_reason": "tool_calls",
        }]))
        _, out = run_stream(terminal + DONE)
        self.assertEqual(args_of(published_calls(out)[0]), {"prompt": "p"})
        self.assertEqual(payloads(out)[-1]["choices"][0]["finish_reason"], "tool_calls")

    def test_stream_choices_composite_key_keeps_calls_apart(self):
        events = (
            tool_delta(0, 0, call_id="c0", name="subagent", args='{"prompt":"zero"')
            + tool_delta(1, 0, call_id="c1", name="other", args='{"k":"one"')
            + tool_delta(0, 0, args=',"provider":""}')
            + tool_delta(1, 0, args=',"z":1}')
            + finish(0)
            + finish(1)
            + DONE
        )
        outcome, out = run_stream(events)
        zero, one = published_calls(out, 0), published_calls(out, 1)
        self.assertEqual([(c["id"], c["function"]["name"]) for c in zero], [("c0", "subagent")])
        self.assertEqual([(c["id"], c["function"]["name"]) for c in one], [("c1", "other")])
        self.assertEqual(args_of(zero[0]), {"prompt": "zero"})
        self.assertEqual(args_of(one[0]), {"k": "one", "z": 1})
        self.assertEqual(outcome.tool_calls_published, 2)

    def test_stream_choices_finish_independently_without_flushing_others(self):
        events = (
            tool_delta(0, 0, call_id="c0", name="subagent", args='{"prompt":"a"}')
            + tool_delta(1, 0, call_id="c1", name="subagent", args='{"prompt":"b"}')
            + finish(0)
        )
        outcome, out = run_stream(events)  # EOF: choice 1 без finish_reason
        self.assertEqual(len(published_calls(out, 0)), 1)
        self.assertEqual(published_calls(out, 1), [])
        self.assertTrue(outcome.incomplete)

    def test_stream_tool_call_indexes_within_choice_keep_order_and_values(self):
        events = (
            tool_delta(0, 0, call_id="c0", name="subagent", args='{"prompt":"a"}')
            + tool_delta(0, 2, call_id="c2", name="subagent", args='{"prompt":"b"}')
            + finish(0)
            + DONE
        )
        _, out = run_stream(events)
        self.assertEqual([(c["index"], c["id"]) for c in published_calls(out)], [(0, "c0"), (2, "c2")])

    def test_stream_parallel_unpacked_reindexed_and_limited(self):
        parallel = {"tool_uses": [{"recipient_name": "t%d" % i, "parameters": {}} for i in range(5)]}
        events = (
            tool_delta(0, 0, call_id="cp", name="parallel", args=json.dumps(parallel))
            + finish(0)
            + DONE
        )
        _, out = run_stream(events, limits=PassthroughLimits(max_parallel_calls=3))
        calls = published_calls(out)
        self.assertEqual([c["function"]["name"] for c in calls], ["t0", "t1", "t2"])
        self.assertEqual([c["index"] for c in calls], [0, 1, 2])
        _, out = run_stream(events)
        self.assertEqual(len(published_calls(out)), 5)

    def test_stream_eof_without_finish_reason_drops_buffer(self):
        events = content("x") + tool_delta(0, 0, call_id="c", name="subagent", args='{"prompt":"p"')
        outcome, out = run_stream(events)
        self.assertEqual(published_calls(out), [])
        self.assertTrue(outcome.incomplete)
        self.assertFalse(outcome.done)
        last = payloads(out)[-1]
        self.assertEqual(last["error"]["code"], "upstream_incomplete_stream")
        self.assertNotIn(DONE, out)

    def test_stream_eof_after_done_with_unfinished_calls_is_failure_not_success(self):
        events = tool_delta(0, 0, call_id="c", name="subagent", args="{}") + DONE
        outcome, out = run_stream(events)
        self.assertEqual(published_calls(out), [])
        self.assertTrue(outcome.incomplete)
        self.assertNotIn(DONE, out)

    def test_stream_eof_mid_event_line_does_not_publish_calls(self):
        events = (
            tool_delta(0, 0, call_id="c", name="subagent", args='{"prompt":"p"}')
            + b'data: {"id":"x","choices":[{"index":0,"delta":{},"finish_re'
        )
        outcome, out = run_stream(events)
        self.assertEqual(published_calls(out), [])
        self.assertTrue(outcome.incomplete)

    def test_stream_eof_after_all_choices_finished_is_clean(self):
        events = (
            tool_delta(0, 0, call_id="c", name="subagent", args='{"prompt":"p"}') + finish(0)
        )  # апстрим закрылся без [DONE], но финал был
        outcome, out = run_stream(events)
        self.assertEqual(len(published_calls(out)), 1)
        self.assertFalse(outcome.incomplete)
        self.assertNotIn("error", payloads(out)[-1])

    def test_stream_eof_content_only_without_finish_is_reported(self):
        outcome, out = run_stream(content("partial"))
        self.assertTrue(outcome.incomplete)
        self.assertEqual(payloads(out)[-1]["error"]["code"], "upstream_incomplete_stream")

    def test_stream_buffer_is_released_after_eof_drop(self):
        process = ProcessBudget(10_000)
        run_stream(tool_delta(0, 0, call_id="c", name="subagent", args="x" * 500), process=process)
        self.assertEqual(process.used, 0)

    def test_stream_sanitize_disabled_is_verbatim(self):
        events = tool_delta(0, 0, call_id="c", name="subagent", args='{"provider":""}') + finish(0) + DONE
        _, out = run_stream(events, sanitize=False)
        self.assertEqual(b"".join(out), events)

    def test_stream_upstream_error_chunk_is_forwarded_verbatim(self):
        events = frame({"error": {"message": "boom", "type": "server_error"}})
        outcome, out = run_stream(events)
        self.assertEqual(out[0], events)
        self.assertFalse(outcome.incomplete)  # choices не было: терминал не требуется

    def test_stream_no_schema_keeps_unknown_fields(self):
        events = tool_delta(0, 0, call_id="c", name="unknown", args='{"note":"","provider":""}') + finish(0)
        _, out = run_stream(events, schemas={})
        self.assertEqual(args_of(published_calls(out)[0]), {"note": "", "provider": ""})

    def test_stream_usage_only_chunk_without_choices_is_forwarded(self):
        usage = frame(chunk([], usage={"total_tokens": 1}))
        _, out = run_stream(finish(0, "stop") + usage + DONE)
        self.assertEqual(out[1], usage)


class TestAccumulatorLimits(unittest.TestCase):
    def acc(self, **kw):
        return ToolCallAccumulator(PassthroughLimits(**kw))

    def test_accumulator_bytes_boundary_minus_equal_plus(self):
        # лимит считает UTF-8 байты id + name + arguments
        base = len(b"c") + len(b"n")
        for extra, ok in ((-1, True), (0, True), (1, False)):
            with self.subTest(extra=extra):
                limit = base + 10
                acc = self.acc(accumulator_max_bytes=limit)
                args = "x" * (10 + extra)
                delta = [{"index": 0, "id": "c", "function": {"name": "n", "arguments": args}}]
                if ok:
                    acc.add(0, delta)
                    self.assertLessEqual(acc.size_bytes, limit)
                else:
                    with self.assertRaises(AccumulatorOverflow):
                        acc.add(0, delta)

    def test_accumulator_keys_limit(self):
        acc = self.acc(accumulator_max_keys=2)
        acc.add(0, [{"index": 0, "id": "a"}, {"index": 1, "id": "b"}])
        acc.add(0, [{"index": 1, "function": {"arguments": "x"}}])  # существующий ключ не растёт
        with self.assertRaises(AccumulatorOverflow):
            acc.add(1, [{"index": 0, "id": "c"}])  # третий ключ (choice, index)

    def test_accumulator_process_budget_is_shared_and_released(self):
        process = ProcessBudget(10)
        first = ToolCallAccumulator(PassthroughLimits(), process)
        second = ToolCallAccumulator(PassthroughLimits(), process)
        first.add(0, [{"index": 0, "function": {"arguments": "x" * 8}}])
        with self.assertRaises(AccumulatorOverflow):
            second.add(0, [{"index": 0, "function": {"arguments": "y" * 3}}])
        first.close()
        self.assertEqual(process.used, 0)
        second.add(0, [{"index": 0, "function": {"arguments": "y" * 3}}])  # после освобождения влезает
        second.close()
        self.assertEqual(process.used, 0)

    def test_accumulator_env_override_both_directions(self):
        small = PassthroughLimits.from_env({"BRIDGE_ACCUMULATOR_MAX_BYTES": "4"})
        large = PassthroughLimits.from_env({"BRIDGE_ACCUMULATOR_MAX_BYTES": str(64 * 1024 * 1024)})
        payload = [{"index": 0, "function": {"arguments": "x" * 100}}]
        with self.assertRaises(AccumulatorOverflow):
            ToolCallAccumulator(small).add(0, payload)
        ToolCallAccumulator(large).add(0, payload)

    def test_stream_overflow_emits_error_frame_without_partial_calls_or_done(self):
        events = (
            tool_delta(0, 0, call_id="c", name="subagent", args="{" + "x" * 100)
            + finish(0)
            + DONE
        )
        process = ProcessBudget(10_000)
        outcome, out = run_stream(events, limits=PassthroughLimits(accumulator_max_bytes=50), process=process)
        self.assertTrue(outcome.overflow)
        self.assertEqual(published_calls(out), [])
        self.assertEqual(payloads(out)[-1]["error"]["code"], "upstream_response_too_large")
        self.assertNotIn(DONE, out)
        self.assertEqual(process.used, 0)

    def test_accumulator_composite_key_pop_orders_by_tool_index(self):
        acc = self.acc()
        acc.add(1, [{"index": 0, "id": "b0", "function": {"name": "n"}}])
        acc.add(0, [{"index": 1, "id": "a1", "function": {"name": "n"}}, {"index": 0, "id": "a0"}])
        self.assertEqual([c["id"] for c in acc.pop_choice(0)], ["a0", "a1"])
        self.assertEqual(acc.pending_choices(), [1])


class TestLimitsFromEnv(unittest.TestCase):
    def test_defaults(self):
        limits = PassthroughLimits.from_env({})
        self.assertEqual(limits.max_parallel_calls, 64)
        self.assertEqual(limits.max_parallel_depth, 8)
        self.assertEqual(limits.max_body_bytes, 16777216)
        self.assertEqual(limits.accumulator_max_bytes, 8388608)
        self.assertEqual(limits.accumulator_max_keys, 64)
        self.assertEqual(limits.accumulator_max_process_bytes, 33554432)

    def test_every_limit_is_overridable_from_env(self):
        limits = PassthroughLimits.from_env({
            "BRIDGE_MAX_PARALLEL_CALLS": "3",
            "BRIDGE_MAX_PARALLEL_DEPTH": "2",
            "BRIDGE_PASSTHROUGH_MAX_BODY_BYTES": "100",
            "BRIDGE_ACCUMULATOR_MAX_BYTES": "200",
            "BRIDGE_ACCUMULATOR_MAX_KEYS": "5",
            "BRIDGE_ACCUMULATOR_MAX_PROCESS_BYTES": "300",
            "BRIDGE_PASSTHROUGH_CONNECT_TIMEOUT_S": "1.5",
            "BRIDGE_PASSTHROUGH_READ_TIMEOUT_S": "7",
        })
        self.assertEqual(
            (limits.max_parallel_calls, limits.max_parallel_depth, limits.max_body_bytes,
             limits.accumulator_max_bytes, limits.accumulator_max_keys,
             limits.accumulator_max_process_bytes, limits.connect_timeout_s, limits.read_timeout_s),
            (3, 2, 100, 200, 5, 300, 1.5, 7.0),
        )

    def test_invalid_values_fall_back_to_defaults(self):
        for bad in ("", "abc", "0", "-5", "1.5"):
            with self.subTest(bad=bad):
                self.assertEqual(
                    PassthroughLimits.from_env({"BRIDGE_MAX_PARALLEL_CALLS": bad}).max_parallel_calls, 64
                )

    def test_server_passes_env_limits_to_core(self):
        self.assertEqual(server._SANITIZE_LIMITS["max_parallel_calls"], server.BRIDGE_LIMITS.max_parallel_calls)


class TestCliRouteToolSchemas(unittest.TestCase):
    """F-002: схемы `request.tools` доходят до санитизатора на CLI-маршрутах фасада."""

    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "keep_empty",
                "parameters": {
                    "type": "object",
                    "properties": {"note": {"type": "string"}},
                    "required": ["note"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "drop_empty",
                "parameters": {"type": "object", "properties": {"note": {"type": "string"}}},
            },
        },
    ]

    def raw_turn(self):
        text = (
            '<tool_call>{"name": "drop_empty", "arguments": {"note": ""}}</tool_call>'
            '<tool_call>{"name": "keep_empty", "arguments": {"note": ""}}</tool_call>'
        )
        return TurnResult(state="done", rc=0, text=text)

    def finalized_args(self, tool_schemas):
        return [json.loads(call["function"]["arguments"]) for call in self.dispatch(self.raw_turn(), tool_schemas)["tool_calls"]]

    def dispatch(self, raw, schemas, stream=False, managed_turn=None, model="m", sanitize=True):
        ctx = {"backend": "droid", "model": model, "effort": "high", "prompt": "p", "rpc": {"system": "", "runnable": "", "items": []}, "images": [], "emulate_tools": True, "tool_schemas": schemas, "stream": stream, "managed_turn": managed_turn}
        adapter = SimpleNamespace(kind="droid", execute_turn=lambda turn, writer: raw)
        with unittest.mock.patch.object(server, "BRIDGE_SANITIZE_TOOL_CALLS", sanitize), unittest.mock.patch.object(server.BACKENDS, "get", return_value=adapter):
            return server.Handler._dispatch(SimpleNamespace(connection=None), ctx, None)

    def test_dispatch_sanitizes_once_after_finalize_and_matches_events(self):
        schemas = server.build_tool_schemas(self.TOOLS)
        for stream in (False, True):
            for prebuilt in (False, True):
                raw = self.raw_turn()
                if prebuilt:
                    raw = server.finalize_turn(raw, True)
                order = []
                original_finalize = server.finalize_turn
                original_sanitize = server.sanitize_tool_call
                def finalize(*args, **kwargs):
                    order.append("finalize")
                    return original_finalize(*args, **kwargs)
                def sanitize(*args, **kwargs):
                    order.append("sanitize")
                    return original_sanitize(*args, **kwargs)
                with unittest.mock.patch.object(server, "finalize_turn", side_effect=finalize), unittest.mock.patch.object(server, "sanitize_tool_call", side_effect=sanitize) as spy:
                    out = self.dispatch(raw, schemas, stream)
                self.assertEqual(spy.call_count, 2)
                self.assertEqual(order, ["finalize", "sanitize", "sanitize"])
                self.assertEqual(out["tool_calls"], [value for kind, value in out["events"] if kind == "tool_call"])
                self.assertEqual([json.loads(call["function"]["arguments"]) for call in out["tool_calls"]], [{}, {"note": ""}])

    def test_dispatch_kill_switch_skips_sanitizer(self):
        with unittest.mock.patch.object(server, "sanitize_tool_call") as spy:
            out = self.dispatch(self.raw_turn(), server.build_tool_schemas(self.TOOLS), sanitize=False)
        spy.assert_not_called()
        self.assertEqual(json.loads(out["tool_calls"][0]["function"]["arguments"]), {"note": ""})

    def test_managed_completion_receives_sanitized_result(self):
        managed = object()
        with unittest.mock.patch.object(server.TURN_MANAGER, "complete_turn_from_result") as complete:
            out = self.dispatch(self.raw_turn(), server.build_tool_schemas(self.TOOLS), managed_turn=managed)
        self.assertIs(complete.call_args.args[0], managed)
        result = complete.call_args.args[1]
        self.assertEqual(json.loads(result.tool_calls[0].function.arguments), {})
        self.assertEqual([event.value for event in result.events if event.kind == "tool_call"], list(result.tool_calls))
        self.assertEqual(out["tool_calls"][0]["function"]["arguments"], result.tool_calls[0].function.arguments)

    def test_managed_replay_returns_finalized_calls_without_sanitizing(self):
        final = self.dispatch(self.raw_turn(), server.build_tool_schemas(self.TOOLS))
        managed = SimpleNamespace(done_event=threading.Event(), final_dict=final)
        managed.done_event.set()
        with unittest.mock.patch.object(server, "sanitize_tool_call") as spy:
            replay = server.Handler._dispatch(SimpleNamespace(), {"attached_existing": True, "managed_turn": managed}, None)
        spy.assert_not_called()
        self.assertEqual(replay, final)

    def test_finalize_uses_request_tool_schemas(self):
        schemas = server.build_tool_schemas(self.TOOLS)
        self.assertEqual(self.finalized_args(schemas), [{}, {"note": ""}])

    def test_finalize_without_schemas_is_fail_conservative(self):
        self.assertEqual(self.finalized_args(None), [{"note": ""}, {"note": ""}])

    def test_turn_context_carries_tool_schemas(self):
        schemas = server.build_tool_schemas(self.TOOLS)
        self.assertIs(server.TurnContext("m", "high", "p", tool_schemas=schemas).tool_schemas, schemas)


class TestNonStreamBody(unittest.TestCase):
    def body(self, calls, **extra):
        return json.dumps(
            {"id": "x", "object": "chat.completion", "choices": [
                {"index": 0, "message": {"role": "assistant", "content": None, "tool_calls": calls},
                 "finish_reason": "tool_calls"}], "usage": {"total_tokens": 1}, **extra}
        ).encode("utf-8")

    def call(self, args, name="subagent", call_id="c1"):
        return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}

    def test_empty_optional_strings_removed(self):
        out = sanitize_completion_body(
            self.body([self.call({"prompt": "p", "provider": "", "note": ""})]),
            SCHEMAS, PassthroughLimits())
        data = json.loads(out)
        self.assertEqual(args_of(data["choices"][0]["message"]["tool_calls"][0]), {"prompt": "p"})
        self.assertEqual(data["usage"], {"total_tokens": 1})

    def test_unchanged_body_is_byte_identical(self):
        raw = self.body([self.call({"prompt": "p"})])
        self.assertIs(sanitize_completion_body(raw, SCHEMAS, PassthroughLimits()), raw)

    def test_invalid_json_and_foreign_shapes_untouched(self):
        for raw in (b"not json", b"[]", b'{"choices": 5}', b'{"error": {"message": "x"}}'):
            with self.subTest(raw=raw):
                self.assertIs(sanitize_completion_body(raw, SCHEMAS, PassthroughLimits()), raw)

    def test_parallel_unpacked_without_index_key(self):
        parallel = {"tool_uses": [{"recipient_name": "subagent", "parameters": {"prompt": "p", "provider": ""}}]}
        out = json.loads(sanitize_completion_body(
            self.body([self.call(parallel, name="parallel")]), SCHEMAS, PassthroughLimits()))
        calls = out["choices"][0]["message"]["tool_calls"]
        self.assertEqual([c["function"]["name"] for c in calls], ["subagent"])
        self.assertNotIn("index", calls[0])
        self.assertEqual(args_of(calls[0]), {"prompt": "p"})

    def test_parallel_limit_applied(self):
        parallel = {"tool_uses": [{"recipient_name": "t%d" % i, "parameters": {}} for i in range(70)]}
        raw = self.body([self.call(parallel, name="parallel")])
        calls = json.loads(sanitize_completion_body(raw, {}, PassthroughLimits()))["choices"][0]["message"]["tool_calls"]
        self.assertEqual(len(calls), 64)
        calls = json.loads(sanitize_completion_body(raw, {}, PassthroughLimits(max_parallel_calls=70)))["choices"][0]["message"]["tool_calls"]
        self.assertEqual(len(calls), 70)


# ---- реальный upstream и шов ------------------------------------------------------
class FakeUpstream:
    """Локальный OpenAI-совместимый upstream; сценарий задаёт `respond(handler, body)`."""

    def __init__(self):
        self.requests: list = []
        self.respond = lambda handler, body: None
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: D401
                return

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                outer.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                outer.respond(self, body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    @staticmethod
    def json(handler, payload, status=200, extra=()):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(data)))
        for key, value in extra:
            handler.send_header(key, value)
        handler.end_headers()
        handler.wfile.write(data)

    @staticmethod
    def sse(handler, body: bytes):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        handler.wfile.write(body)
        handler.wfile.flush()


class CollectSink(ResponseSink):
    def __init__(self):
        self.status = None
        self.headers = []
        self.chunks: list = []
        self.fail_after = None

    def start(self, status, headers):
        self.status, self.headers = status, headers

    def write(self, data):
        if self.fail_after is not None and len(self.chunks) >= self.fail_after:
            raise ClientGone()
        self.chunks.append(data)

    @property
    def body(self) -> bytes:
        return b"".join(self.chunks)

    def header(self, name):
        return next((v for k, v in self.headers if k.lower() == name.lower()), None)


def make_adapter(port: int, limits=None, **kw) -> PassthroughAdapter:
    config = {"kind": "passthrough", "base_url": "http://127.0.0.1:%d/v1" % port, "max_concurrent": 4}
    return PassthroughAdapter("codex", config, lambda: {}, None, limits=limits or PassthroughLimits(), **kw)


class SeamCase(unittest.TestCase):
    def setUp(self):
        self.upstream = FakeUpstream()
        self.addCleanup(self.upstream.close)

    def call(self, request: dict, adapter=None, headers=None, raw=None, path="/v1/chat/completions"):
        adapter = adapter or make_adapter(self.upstream.port, sanitize=True)
        raw = raw if raw is not None else json.dumps(request).encode("utf-8")
        sink = CollectSink()
        adapter.handle(path=path, raw_body=raw, request=request,
                       headers=headers or {"Authorization": "Bearer upstream-key"}, sink=sink)
        return sink


class TestSeamNonStream(SeamCase):
    def completion(self, args):
        return {"id": "x", "object": "chat.completion", "choices": [{"index": 0, "finish_reason": "tool_calls",
                "message": {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "subagent", "arguments": json.dumps(args)}}]}}]}

    def test_request_forwarded_verbatim_and_response_sanitized(self):
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, self.completion({"prompt": "p", "provider": ""}))
        request = {"model": "gpt-6.1-terra", "reasoning_effort": "xhigh", "tools": TOOLS,
                   "messages": [{"role": "user", "content": "hi"}]}
        raw = json.dumps(request, indent=2).encode("utf-8")  # нестандартная сериализация: байты не пересобираются
        sink = self.call(request, raw=raw)
        sent = self.upstream.requests[0]
        self.assertEqual(sent["body"], raw)
        self.assertEqual(sent["path"], "/v1/chat/completions")
        self.assertEqual(sent["headers"]["Authorization"], "Bearer upstream-key")
        self.assertEqual(sink.status, 200)
        data = json.loads(sink.body)
        self.assertEqual(args_of(data["choices"][0]["message"]["tool_calls"][0]), {"prompt": "p"})
        self.assertEqual(sink.header("Content-Length"), str(len(sink.body)))

    def test_missing_authorization_stays_missing_and_hop_by_hop_dropped(self):
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, {"ok": True})
        self.call({"model": "m"}, headers={"X-Custom": "1", "Connection": "keep-alive",
                                           "Accept-Encoding": "gzip", "Proxy-Authorization": "secret"})
        headers = {k.lower(): v for k, v in self.upstream.requests[0]["headers"].items()}
        self.assertNotIn("authorization", headers)
        self.assertNotIn("proxy-authorization", headers)
        self.assertEqual(headers["x-custom"], "1")
        self.assertEqual(headers["accept-encoding"], "identity")

    def test_non_200_status_and_body_verbatim(self):
        error = b'{"error": {"message": "rate limited", "type": "rate"}}'
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, error, status=429, extra=[("Retry-After", "7")])
        sink = self.call({"model": "m", "tools": TOOLS})
        self.assertEqual((sink.status, sink.body), (429, error))
        self.assertEqual(sink.header("Retry-After"), "7")

    def test_non_json_200_body_verbatim(self):
        def respond(h, b):
            h.send_response(200)
            h.send_header("Content-Type", "text/plain")
            h.send_header("Content-Length", "5")
            h.end_headers()
            h.wfile.write(b"hello")
        self.upstream.respond = respond
        sink = self.call({"model": "m"})
        self.assertEqual((sink.status, sink.body), (200, b"hello"))

    def test_body_limit_minus_equal_plus(self):
        payload = json.dumps({"id": "x", "choices": []}).encode("utf-8")
        for delta, expected in ((-1, 200), (0, 200), (1, 502)):
            with self.subTest(delta=delta):
                limits = PassthroughLimits(max_body_bytes=len(payload) - delta)
                self.upstream.respond = lambda h, b: FakeUpstream.json(h, payload)
                sink = self.call({"model": "m"}, adapter=make_adapter(self.upstream.port, limits, sanitize=True))
                self.assertEqual(sink.status, expected)
                if expected == 502:
                    self.assertEqual(json.loads(sink.body)["error"]["type"], "upstream_response_too_large")

    def test_huge_non_tool_body_rejected_without_chunked_length(self):
        def respond(h, b):
            h.send_response(200)
            h.send_header("Content-Type", "application/json")
            h.end_headers()  # без Content-Length: читаем до закрытия
            h.wfile.write(b" " * 4096)
        self.upstream.respond = respond
        sink = self.call({"model": "m"}, adapter=make_adapter(self.upstream.port, PassthroughLimits(max_body_bytes=1024), sanitize=True))
        self.assertEqual(sink.status, 502)

    def test_upstream_unavailable_is_502_and_not_retried(self):
        free = socket.socket()
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
        free.close()
        sink = self.call({"model": "m"}, adapter=make_adapter(port, sanitize=True))
        self.assertEqual(sink.status, 502)
        self.assertEqual(json.loads(sink.body)["error"]["type"], "upstream_unavailable")

    def test_upstream_read_timeout_is_504(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        self.upstream.respond = lambda h, b: gate.wait(5)
        limits = PassthroughLimits(read_timeout_s=0.3)
        sink = self.call({"model": "m"}, adapter=make_adapter(self.upstream.port, limits, sanitize=True))
        self.assertEqual(sink.status, 504)

    def test_sanitize_kill_switch_returns_body_untouched(self):
        raw = json.dumps(self.completion({"prompt": "p", "provider": ""})).encode("utf-8")
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, raw)
        sink = self.call({"model": "m", "tools": TOOLS}, adapter=make_adapter(self.upstream.port, sanitize=False))
        self.assertEqual(sink.body, raw)

    def test_saturated_backend_returns_503(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        self.upstream.respond = lambda h, b: (gate.wait(3), FakeUpstream.json(h, {"ok": 1}))
        adapter = make_adapter(self.upstream.port, sanitize=True)
        adapter.config["max_concurrent"] = 1
        adapter._slots = threading.BoundedSemaphore(1)
        adapter.host = type("Host", (), {"QUEUE_TIMEOUT_S": 0.2})()
        first = threading.Thread(target=lambda: self.call({"model": "m"}, adapter=adapter))
        first.start()
        for _ in range(100):
            if adapter.active_count():
                break
            threading.Event().wait(0.02)
        sink = self.call({"model": "m"}, adapter=adapter)
        self.assertEqual(sink.status, 503)
        gate.set()
        first.join(5)
        self.assertEqual(adapter.active_count(), 0)


class TestSeamStream(SeamCase):
    def test_stream_end_to_end_sanitizes_and_keeps_order(self):
        events = (content("hi") + tool_delta(0, 0, call_id="c", name="subagent", args='{"prompt":"p","provider":""}')
                  + finish(0) + DONE)
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        sink = self.call({"model": "m", "stream": True, "tools": TOOLS})
        self.assertEqual(sink.status, 200)
        self.assertEqual(sink.header("Content-Type"), "text/event-stream")
        self.assertEqual(args_of(published_calls(sink.chunks)[0]), {"prompt": "p"})
        self.assertEqual(sink.chunks[-1], DONE)

    def test_stream_upstream_429_is_plain_http_response_not_sse(self):
        error = b'{"error": {"message": "slow down"}}'
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, error, status=429)
        sink = self.call({"model": "m", "stream": True})
        self.assertEqual((sink.status, sink.body), (429, error))
        self.assertNotEqual(sink.header("Content-Type"), "text/event-stream")

    def test_stream_eof_without_finish_reason_end_to_end(self):
        events = tool_delta(0, 0, call_id="c", name="subagent", args='{"prompt":"p"') + b""
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        sink = self.call({"model": "m", "stream": True, "tools": TOOLS})
        self.assertEqual(published_calls(sink.chunks), [])
        self.assertEqual(payloads(sink.chunks)[-1]["error"]["code"], "upstream_incomplete_stream")
        self.assertNotIn(DONE, sink.chunks)

    def test_stream_client_gone_closes_upstream_and_releases_budget(self):
        events = b"".join(content("x%d" % i) for i in range(50)) + finish(0, "stop") + DONE
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        adapter = make_adapter(self.upstream.port, sanitize=True)
        sink = CollectSink()
        sink.fail_after = 2
        adapter.handle(path="/v1/chat/completions", raw_body=b"{}", request={"stream": True},
                       headers={}, sink=sink)
        self.assertEqual(adapter.active_count(), 0)
        self.assertEqual(adapter.process_budget.used, 0)

    def test_stream_overflow_in_started_sse_is_error_frame(self):
        events = tool_delta(0, 0, call_id="c", name="subagent", args="{" + "x" * 500) + finish(0) + DONE
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        adapter = make_adapter(self.upstream.port, PassthroughLimits(accumulator_max_bytes=100), sanitize=True)
        sink = self.call({"model": "m", "stream": True}, adapter=adapter)
        self.assertEqual(sink.status, 200)
        self.assertEqual(published_calls(sink.chunks), [])
        self.assertEqual(payloads(sink.chunks)[-1]["error"]["code"], "upstream_response_too_large")
        self.assertEqual(adapter.process_budget.used, 0)

    def test_stream_choices_interleaved_end_to_end(self):
        events = (tool_delta(0, 0, call_id="c0", name="subagent", args='{"prompt":"a"')
                  + tool_delta(1, 0, call_id="c1", name="subagent", args='{"prompt":"b"')
                  + tool_delta(0, 0, args="}") + tool_delta(1, 0, args="}")
                  + finish(1) + finish(0) + DONE)
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        sink = self.call({"model": "m", "stream": True, "tools": TOOLS})
        self.assertEqual([args_of(c) for c in published_calls(sink.chunks, 0)], [{"prompt": "a"}])
        self.assertEqual([args_of(c) for c in published_calls(sink.chunks, 1)], [{"prompt": "b"}])


# ---- fleet kind=passthrough ---------------------------------------------------------
class TestFleetPassthroughKind(unittest.TestCase):
    def raw(self):
        data = load_raw_fleet()
        return copy.deepcopy(data)

    def entry_error(self, **override):
        data = self.raw()
        data["backends"]["codex"].update(override)
        for key, value in list(data["backends"]["codex"].items()):
            if value is None:
                del data["backends"]["codex"][key]
        try:
            build_catalog(data, ADAPTER_KINDS)
        except FleetViolation as exc:
            return exc.reason
        return ""

    def test_live_fleet_declares_enabled_codex_passthrough_with_loopback_base_url(self):
        codex = self.raw()["backends"]["codex"]
        self.assertEqual(codex["kind"], "passthrough")
        self.assertEqual(codex["base_url"], "http://127.0.0.1:2455/v1")
        self.assertTrue(codex["enabled"])

    def test_valid_entry_accepted(self):
        self.assertEqual(self.entry_error(), "")
        self.assertEqual(self.entry_error(enabled=True), "")

    def test_base_url_validation_slugs(self):
        self.assertEqual(self.entry_error(base_url=None), "backend_base_url_missing")
        for bad in ("http://example.com/v1", "https://127.0.0.1:2455/v1", "http://127.0.0.1/v1",
                    "http://127.0.0.1:2455/v2", "http://127.0.0.1:99999/v1", "http://localhost:2455/v1", 5):
            with self.subTest(bad=bad):
                self.assertEqual(self.entry_error(base_url=bad), "backend_base_url_invalid")

    def test_base_url_rejected_for_other_kinds(self):
        data = self.raw()
        data["backends"]["droid"]["base_url"] = "http://127.0.0.1:2455/v1"
        with self.assertRaises(FleetViolation) as ctx:
            build_catalog(data, ADAPTER_KINDS)
        self.assertEqual(ctx.exception.reason, "backend_base_url_unexpected")

    def test_registry_builds_passthrough_adapter_without_spawn(self):
        data = self.raw()
        data["backends"]["codex"]["enabled"] = True
        catalog = build_catalog(data, ADAPTER_KINDS)
        registry = AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog)
        adapter = registry.get("codex")
        self.assertIsInstance(adapter, PassthroughAdapter)
        self.assertEqual({m.id for m in adapter.get_models()}, {"gpt-6.1-terra", "gpt-6.1-sol"})
        self.assertTrue(adapter.is_healthy())
        self.assertIs(registry.adapter_for_model("gpt-6.1-terra"), adapter)


# ---- маршрут хаба: допуск, /v1/models, дословность ------------------------------------
class TestHubRoute(BridgeCase):
    HUB_KEY = "test-key"  # BridgeCase.AUTH_KEY

    def setUp(self):
        super().setUp()
        self.upstream = FakeUpstream()
        self.addCleanup(self.upstream.close)
        data = load_raw_fleet()
        data["backends"]["codex"]["enabled"] = True
        data["backends"]["codex"]["base_url"] = "http://127.0.0.1:%d/v1" % self.upstream.port
        server.FLEET = server._build_catalog(data)
        saved = server.BACKENDS
        self.addCleanup(setattr, server, "BACKENDS", saved)
        server.BACKENDS = AdapterRegistry.from_fleet(server.FLEET, ADAPTER_KINDS, lambda: server.FLEET, server)
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, {
            "id": "x", "object": "chat.completion", "choices": [{"index": 0, "finish_reason": "tool_calls",
            "message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "subagent", "arguments": '{"prompt":"p","provider":""}'}}]}}]})

    def post(self, body: dict, auth="Bearer upstream-key"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            headers = {"Content-Type": "application/json"}
            if auth is not None:
                headers["Authorization"] = auth
            conn.request("POST", "/v1/chat/completions", body=json.dumps(body), headers=headers)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def request_body(self, **extra):
        return {"model": "gpt-6.1-terra", "reasoning_effort": "xhigh", "tools": TOOLS,
                "messages": [{"role": "user", "content": "hi"}], **extra}

    def test_deferred_auth_reserves_body_budget_before_upstream(self):
        budget = server._ByteBudget(1)
        with unittest.mock.patch.object(server, "_budget", budget), unittest.mock.patch.object(budget, "reserve", wraps=budget.reserve) as reserve:
            status, _ = self.post(self.request_body())
            self.assertEqual(status, 503)
            reserve.assert_called_once_with(len(json.dumps(self.request_body()).encode()))
        self.assertEqual(budget._used, 0)
        self.assertEqual(self.upstream.requests, [])

    def test_default_passthrough_requires_explicit_exact_model(self):
        with unittest.mock.patch.object(server, "MODEL_ID", "gpt-6.1-terra"):
            for extra in ({}, {"model": None}, {"model": ""}, {"model": " "}, {"model": " gpt-6.1-terra "}):
                body = {"messages": [{"role": "user", "content": "hi"}], **extra}
                status, _ = self.post(body)
                self.assertIn(status, (400, 401))
        self.assertEqual(self.upstream.requests, [])

    def test_unknown_string_model_is_404(self):
        status, raw = self.post(self.request_body(model="unknown-model"), auth="Bearer " + self.HUB_KEY)
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(raw)["error"]["type"], "model_not_found")
        self.assertEqual(self.upstream.requests, [])

    def test_passthrough_model_with_upstream_key_routes_verbatim_and_sanitizes(self):
        status, raw = self.post(self.request_body())
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(args_of(data["choices"][0]["message"]["tool_calls"][0]), {"prompt": "p"})
        sent = self.upstream.requests[0]
        self.assertEqual(sent["headers"]["Authorization"], "Bearer upstream-key")
        body = json.loads(sent["body"])
        self.assertEqual((body["model"], body["reasoning_effort"]), ("gpt-6.1-terra", "xhigh"))  # без клампа

    def test_passthrough_model_without_authorization_is_forwarded_not_rejected_by_hub(self):
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, {"error": {"message": "no key"}}, status=401)
        status, raw = self.post(self.request_body(), auth=None)
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(raw)["error"]["message"], "no key")  # ответ upstream, не хаба
        self.assertEqual(len(self.upstream.requests), 1)
        self.assertNotIn("authorization", {k.lower() for k in self.upstream.requests[0]["headers"]})

    def test_hub_key_still_works_for_passthrough_model(self):
        status, _ = self.post(self.request_body(), auth="Bearer " + self.HUB_KEY)
        self.assertEqual(status, 200)

    def test_other_routes_still_require_hub_key(self):
        status, raw = self.post({"model": server.MODEL_ID, "messages": [{"role": "user", "content": "x"}]},
                                auth="Bearer upstream-key")
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(raw)["error"]["type"], "auth_error")
        self.assertEqual(self.upstream.requests, [])

    def test_unknown_path_with_upstream_key_is_401(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("POST", "/v1/other", body=b"{}", headers={"Authorization": "Bearer upstream-key"})
            self.assertEqual(conn.getresponse().status, 401)
        finally:
            conn.close()

    def test_models_listing_includes_passthrough_model_for_loopback_without_hub_key(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("GET", "/v1/models", headers={"Authorization": "Bearer upstream-key"})
            resp = conn.getresponse()
            data = json.loads(resp.read())
        finally:
            conn.close()
        self.assertEqual(resp.status, 200)
        ids = [m["id"] for m in data["data"]]
        self.assertIn("gpt-6.1-terra", ids)
        self.assertEqual(self.upstream.requests, [])  # каталог без вызова upstream

    def test_other_get_routes_keep_hub_auth(self):
        status, _ = self._get("/v1/turns/abc", auth=False)
        self.assertEqual(status, 401)

    def test_passthrough_stream_through_hub(self):
        events = (tool_delta(0, 0, call_id="c", name="subagent", args='{"prompt":"p","provider":""}') + finish(0) + DONE)
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        status, raw = self.post(self.request_body(stream=True))
        self.assertEqual(status, 200)
        frames = [line for line in raw.split(b"\n\n") if line]
        calls = published_calls([f + b"\n\n" for f in frames])
        self.assertEqual(args_of(calls[0]), {"prompt": "p"})
        self.assertTrue(raw.endswith(DONE))


class TestHubWithoutPassthrough(BridgeCase):
    def test_default_fleet_keeps_legacy_401_for_upstream_style_key(self):
        data = load_raw_fleet()
        data["backends"]["codex"]["enabled"] = False
        server.FLEET = server._build_catalog(data)
        self.addCleanup(setattr, server, "BACKENDS", server.BACKENDS)
        server.BACKENDS = AdapterRegistry.from_fleet(server.FLEET, ADAPTER_KINDS, lambda: server.FLEET, server)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("POST", "/v1/chat/completions", body=b"{}",
                         headers={"Authorization": "Bearer other", "Content-Type": "application/json"})
            self.assertEqual(conn.getresponse().status, 401)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()


class TestDirectLoopbackValidation(unittest.TestCase):
    def test_invalid_url_rejected_before_any_network_call(self):
        for url in ("http://example.com:2455/v1", "https://127.0.0.1:2455/v1", "http://127.0.0.1/v1", "http://127.0.0.1:0/v1", "http://127.0.0.1:65536/v1", "http://127.0.0.1:abc/v1", "http://user@127.0.0.1:2455/v1", "http://127.0.0.1:2455/v1?x=1", "http://127.0.0.1:2455/v1#x", "http://127.1:2455/v1", "http://localhost.evil:2455/v1", "", None):
            with self.subTest(url=url), unittest.mock.patch("http.client.HTTPConnection") as connection:
                with self.assertRaises(ValueError):
                    PassthroughAdapter("codex", {"base_url": url}, dict)
                connection.assert_not_called()

    def test_approved_loopback_urls_accepted(self):
        for host in ("127.0.0.1", "localhost"):
            adapter = PassthroughAdapter("codex", {"base_url": f"http://{host}:2455/v1"}, dict)
            self.assertEqual((adapter._host, adapter._port), (host, 2455))
