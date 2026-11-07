"""Существующие оракулы passthrough, выделенные для сохранения границ legacy."""

from __future__ import annotations

from adapters.passthrough_adapter import PassthroughLimits
from adapters.passthrough_adapter import ProcessBudget
from tests.passthrough_stream_testlib import DONE
from tests.passthrough_stream_testlib import args_of
from tests.passthrough_stream_testlib import chunk
from tests.passthrough_stream_testlib import content
from tests.passthrough_stream_testlib import finish
from tests.passthrough_stream_testlib import frame
from tests.passthrough_stream_testlib import payloads
from tests.passthrough_stream_testlib import published_calls
from tests.passthrough_stream_testlib import run_stream
from tests.passthrough_stream_testlib import tool_delta
import json
import unittest.mock


class TestStreamRelay(unittest.TestCase):
    def test_stream_content_passes_verbatim_in_order(self) -> None:
        events = content("a") + content("b") + finish(0, "stop") + DONE
        outcome, out = run_stream(events)
        self.assertEqual(b"".join(out), events)
        self.assertTrue(outcome.done)
        self.assertFalse(outcome.incomplete)

    def test_stream_non_data_events_and_comments_are_forwarded(self) -> None:
        events = b": keepalive\n\n" + content("a") + finish(0, "stop") + DONE
        _, out = run_stream(events)
        self.assertEqual(b"".join(out), events)

    def test_stream_tool_calls_buffered_sanitized_published_before_terminal(
        self,
    ) -> None:
        events = (
            content("x")
            + tool_delta(0, 0, call_id="call_a", name="subagent", args='{"prompt":"p",')
            + tool_delta(0, 0, args='"provider":"","note":" "}')
            + finish(0, usage={"total_tokens": 3})
            + DONE
        )
        outcome, out = run_stream(events)
        frames = payloads(out)
        self.assertEqual(len(published_calls(out)), 1)
        call = published_calls(out)[0]
        self.assertEqual(
            (call["id"], call["index"], call["function"]["name"]),
            ("call_a", 0, "subagent"),
        )
        self.assertEqual(args_of(call), {"prompt": "p"})
        order = [
            "content"
            if f["choices"][0]["delta"].get("content")
            else "calls"
            if f["choices"][0]["delta"].get("tool_calls")
            else "terminal"
            if f["choices"][0].get("finish_reason")
            else "other"
            for f in frames
        ]
        self.assertEqual(order, ["content", "calls", "terminal"])
        self.assertEqual(frames[-1]["usage"], {"total_tokens": 3})
        self.assertEqual(out[-1], DONE)
        self.assertEqual(outcome.tool_calls_published, 1)

    def test_stream_terminal_chunk_carrying_tool_calls_is_handled(self) -> None:
        terminal = frame(
            chunk(
                [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "subagent",
                                        "arguments": '{"prompt":"p","provider":""}',
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            )
        )
        _, out = run_stream(terminal + DONE)
        self.assertEqual(args_of(published_calls(out)[0]), {"prompt": "p"})
        self.assertEqual(payloads(out)[-1]["choices"][0]["finish_reason"], "tool_calls")

    def test_stream_choices_composite_key_keeps_calls_apart(self) -> None:
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
        zero, one = (published_calls(out, 0), published_calls(out, 1))
        self.assertEqual(
            [(c["id"], c["function"]["name"]) for c in zero], [("c0", "subagent")]
        )
        self.assertEqual(
            [(c["id"], c["function"]["name"]) for c in one], [("c1", "other")]
        )
        self.assertEqual(args_of(zero[0]), {"prompt": "zero"})
        self.assertEqual(args_of(one[0]), {"k": "one", "z": 1})
        self.assertEqual(outcome.tool_calls_published, 2)

    def test_stream_choices_finish_independently_without_flushing_others(self) -> None:
        events = (
            tool_delta(0, 0, call_id="c0", name="subagent", args='{"prompt":"a"}')
            + tool_delta(1, 0, call_id="c1", name="subagent", args='{"prompt":"b"}')
            + finish(0)
        )
        outcome, out = run_stream(events)
        self.assertEqual(len(published_calls(out, 0)), 1)
        self.assertEqual(published_calls(out, 1), [])
        self.assertTrue(outcome.incomplete)

    def test_stream_tool_call_indexes_within_choice_keep_order_and_values(self) -> None:
        events = (
            tool_delta(0, 0, call_id="c0", name="subagent", args='{"prompt":"a"}')
            + tool_delta(0, 2, call_id="c2", name="subagent", args='{"prompt":"b"}')
            + finish(0)
            + DONE
        )
        _, out = run_stream(events)
        self.assertEqual(
            [(c["index"], c["id"]) for c in published_calls(out)],
            [(0, "c0"), (2, "c2")],
        )

    def test_stream_parallel_unpacked_reindexed_and_limited(self) -> None:
        parallel = {
            "tool_uses": [
                {"recipient_name": "t%d" % i, "parameters": {}} for i in range(5)
            ]
        }
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

    def test_stream_eof_without_finish_reason_drops_buffer(self) -> None:
        events = content("x") + tool_delta(
            0, 0, call_id="c", name="subagent", args='{"prompt":"p"'
        )
        outcome, out = run_stream(events)
        self.assertEqual(published_calls(out), [])
        self.assertTrue(outcome.incomplete)
        self.assertFalse(outcome.done)
        last = payloads(out)[-1]
        self.assertEqual(last["error"]["code"], "upstream_incomplete_stream")
        self.assertTrue(b"".join(out).endswith(DONE))

    def test_stream_eof_after_done_with_unfinished_calls_is_failure_not_success(
        self,
    ) -> None:
        events = tool_delta(0, 0, call_id="c", name="subagent", args="{}") + DONE
        outcome, out = run_stream(events)
        self.assertEqual(published_calls(out), [])
        self.assertTrue(outcome.incomplete)
        self.assertTrue(b"".join(out).endswith(DONE))

    def test_stream_eof_mid_event_line_does_not_publish_calls(self) -> None:
        events = (
            tool_delta(0, 0, call_id="c", name="subagent", args='{"prompt":"p"}')
            + b'data: {"id":"x","choices":[{"index":0,"delta":{},"finish_re'
        )
        outcome, out = run_stream(events)
        self.assertEqual(published_calls(out), [])
        self.assertTrue(outcome.incomplete)

    def test_stream_eof_after_all_choices_finished_is_clean(self) -> None:
        events = tool_delta(
            0, 0, call_id="c", name="subagent", args='{"prompt":"p"}'
        ) + finish(0)
        outcome, out = run_stream(events)
        self.assertEqual(len(published_calls(out)), 1)
        self.assertFalse(outcome.incomplete)
        self.assertNotIn("error", payloads(out)[-1])

    def test_stream_eof_content_only_without_finish_is_reported(self) -> None:
        outcome, out = run_stream(content("partial"))
        self.assertTrue(outcome.incomplete)
        self.assertEqual(
            payloads(out)[-1]["error"]["code"], "upstream_incomplete_stream"
        )

    def test_stream_buffer_is_released_after_eof_drop(self) -> None:
        process = ProcessBudget(10000)
        run_stream(
            tool_delta(0, 0, call_id="c", name="subagent", args="x" * 500),
            process=process,
        )
        self.assertEqual(process.used, 0)

    def test_stream_sanitize_disabled_is_verbatim(self) -> None:
        events = (
            tool_delta(0, 0, call_id="c", name="subagent", args='{"provider":""}')
            + finish(0)
            + DONE
        )
        _, out = run_stream(events, sanitize=False)
        self.assertEqual(b"".join(out), events)

    def test_stream_upstream_error_chunk_is_forwarded_verbatim(self) -> None:
        events = frame({"error": {"message": "boom", "type": "server_error"}})
        outcome, out = run_stream(events)
        self.assertEqual(out[0], events)
        self.assertFalse(outcome.incomplete)

    def test_stream_no_schema_keeps_unknown_fields(self) -> None:
        events = tool_delta(
            0, 0, call_id="c", name="unknown", args='{"note":"","provider":""}'
        ) + finish(0)
        _, out = run_stream(events, schemas={})
        self.assertEqual(args_of(published_calls(out)[0]), {"note": "", "provider": ""})

    def test_stream_usage_only_chunk_without_choices_is_forwarded(self) -> None:
        usage = frame(chunk([], usage={"total_tokens": 1}))
        _, out = run_stream(finish(0, "stop") + usage + DONE)
        self.assertEqual(out[1], usage)
