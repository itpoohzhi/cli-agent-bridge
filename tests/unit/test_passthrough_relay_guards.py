"""L1: инварианты нормализации сообщений и публикации SSE-дельт."""

from __future__ import annotations

import io
import json
from dataclasses import replace

import pytest

import adapters.passthrough_adapter as passthrough
from core.tool_emulation import LiveParserError
from tests.unit._passthrough_tool_branches import (
    EMULATE_SPEC,
    FORBID_SPEC,
    OFF_SPEC,
    delta_chunk,
    isolated_env as isolated_env,
    limits as limits,
    sse_events,
)

CALL = '<tool_call>{"name":"noop","arguments":{}}</tool_call>'


def _frames(wire):
    return [json.loads(line[5:]) for line in wire.splitlines()
            if line.startswith(b"data:") and line[5:].strip() != b"[DONE]"]


def _relay(limits, **options):
    written = []
    relay = passthrough._SseRelay(written.append, None, limits, options)
    return relay, written


def _run(limits, wire, **options):
    written = []
    outcome = passthrough.relay_sse(
        io.BytesIO(wire).readline, written.append,
        tool_schemas=None, limits=limits, **options,
    )
    return outcome, b"".join(written)


@pytest.mark.parametrize("extra", ({}, {"id": ""}))
def test_openai_call_defaults_null_arguments_and_missing_id(extra):
    call = passthrough._openai_call({"name": "f", "arguments": None, **extra})
    assert call["function"] == {"name": "f", "arguments": "{}"}
    assert call["id"].startswith("call_")
    assert len(call["id"]) > len("call_")


@pytest.mark.parametrize("indices,expected", ((["bad"], 1), ([2, "bad"], 3)))
def test_merge_calls_preserves_index_presence_but_ignores_non_integer_values(indices, expected):
    raw = [{"id": f"c{i}", "index": index} for i, index in enumerate(indices)]
    merged = passthrough._merge_parsed_calls(raw, [{"name": "f", "arguments": {}}])
    assert merged[:-1] == raw
    assert merged[-1]["index"] == expected
    assert merged[-1]["function"] == {"name": "f", "arguments": "{}"}


def _body(message):
    return json.dumps({"choices": [{"message": message}]}, indent=2).encode()


@pytest.mark.parametrize("sanitize,enabled", ((True, False), (False, True), (False, False)))
def test_completion_emulation_requires_both_normalization_switches(limits, sanitize, enabled):
    body = _body({"role": "assistant", "content": CALL})
    actual = passthrough.sanitize_completion_body(
        body, None, replace(limits, invoke_normalization_enabled=enabled),
        EMULATE_SPEC, sanitize=sanitize,
    )
    assert actual is body
    assert json.loads(actual)["choices"][0]["message"]["content"] == CALL


def test_forbid_still_checks_text_when_sanitization_is_disabled(limits):
    with pytest.raises(LiveParserError):
        passthrough.sanitize_completion_body(
            _body({"content": CALL}), None, limits, FORBID_SPEC, sanitize=False,
        )


def test_finish_appends_partial_prefix_without_overwriting_already_emitted_text(limits):
    body = _body({"role": "assistant", "content": "hello <t"})
    actual = passthrough.sanitize_completion_body(body, None, limits, OFF_SPEC)
    assert json.loads(actual)["choices"][0]["message"]["content"] == "hello <t"
    assert actual is body


def test_reasoning_only_message_does_not_gain_content_or_change_wire_bytes(limits):
    body = _body({"role": "assistant", "reasoning_content": "ok"})
    actual = passthrough.sanitize_completion_body(body, None, limits, OFF_SPEC)
    assert actual is body
    assert "content" not in json.loads(actual)["choices"][0]["message"]


def test_delta_frame_excludes_usage_error_and_old_choices():
    base = {"id": "1", "model": "m", "usage": {"a": 1},
            "error": {"x": 1}, "choices": [{"x": 1}]}
    (frame,) = _frames(passthrough._delta_frame(base, 0, {"content": "hi"}))
    assert "usage" not in frame
    assert "error" not in frame
    assert (frame["id"], frame["model"]) == ("1", "m")
    assert frame["choices"] == [{"index": 0, "delta": {"content": "hi"}, "finish_reason": None}]


def test_disabled_repetition_guard_does_not_allocate_or_raise(limits):
    relay, written = _relay(replace(limits, repetition_guard_enabled=False))
    relay._check_repetition(0, "repeat " * 100)
    assert relay.guards == {}
    assert written == []


def test_empty_text_does_not_allocate_an_enabled_repetition_guard(limits):
    relay, written = _relay(replace(limits, repetition_guard_enabled=True))
    relay._check_repetition(7, "")
    assert relay.guards == {}
    assert written == []


def test_repetition_guard_reuses_choice_state_and_stops_repeated_tokens(limits):
    limits = replace(limits, repetition_guard_enabled=True, repetition_max_repeats=2)
    relay, _ = _relay(limits)
    relay._check_repetition(0, "repeat ")
    guard = relay.guards[0]
    with pytest.raises(passthrough._RepetitionLoop):
        relay._check_repetition(0, "repeat " * 100)
    assert relay.guards[0] is guard


def test_relay_converts_repetition_to_terminal_error(limits):
    limits = replace(limits, repetition_guard_enabled=True, repetition_max_repeats=2)
    wire = sse_events(delta_chunk(0, {"content": "repeat " * 100}))
    outcome, body = _run(limits, wire)
    assert outcome.repetition_loop is True
    assert _frames(body)[-1]["error"]["code"] == "upstream_repetition_loop"
    assert body.count(b"data: [DONE]\n\n") == 1


@pytest.mark.parametrize("sanitize,enabled", ((True, False), (False, True)))
def test_stream_emulation_keeps_literal_tools_unless_both_switches_are_on(
    limits, sanitize, enabled,
):
    relay, _ = _relay(replace(limits, invoke_normalization_enabled=enabled), sanitize=sanitize)
    choice = {"index": 0, "delta": {"content": CALL}, "finish_reason": None}
    assert relay._consume_choice(choice) is False
    assert choice["delta"] == {"content": CALL}
    assert relay.acc.pending_choices() == []
    relay.acc.close()


@pytest.mark.parametrize("trusted", (False, True))
def test_native_tools_are_published_only_when_trusted_and_counted(limits, trusted):
    relay, _ = _relay(limits, trusted_tools=trusted, sanitize=True)
    calls = [{"index": 0, "id": "c0", "type": "function",
              "function": {"name": "noop", "arguments": "{}"}}]
    delta = {"role": "assistant", "content": "hi", "tool_calls": calls}
    actual = relay._native_delta(0, delta)
    expected = delta if trusted else {"role": "assistant", "content": "hi"}
    assert actual == expected
    assert relay.outcome.tool_calls_published == int(trusted)
    relay.acc.close()


def test_flush_text_for_unknown_choice_is_a_noop(limits):
    relay, written = _relay(limits)
    relay._flush_text(99, {"id": "c"})
    assert written == []
    assert relay.texts == {}


def test_terminal_moves_content_to_separate_frame_and_preserves_role(limits):
    wire = sse_events(delta_chunk(0, {"role": "assistant", "content": "hi"}, "stop"))
    outcome, body = _run(limits, wire)
    frames = _frames(body)
    assert [frame["choices"][0]["delta"] for frame in frames] == [
        {"content": "hi"}, {"role": "assistant"},
    ]
    assert frames[-1]["choices"][0]["finish_reason"] == "stop"
    assert outcome.done is True


def test_terminal_modification_propagates_even_if_consume_choice_did_not_change(limits):
    relay, written = _relay(replace(limits, invoke_normalization_enabled=False))
    chunk = delta_chunk(0, {"content": "hi"}, "stop")
    assert relay._consume_chunk(chunk, chunk["choices"]) is True
    assert chunk["choices"][0]["delta"] == {}
    assert _frames(b"".join(written))[0]["choices"][0]["delta"] == {"content": "hi"}


def test_unmodified_chunk_preserves_original_whitespace_and_is_not_duplicated(limits):
    raw = b'data: { "choices": [ { "index":0,"delta":{},"finish_reason":"stop" } ] }\n\n'
    outcome, body = _run(limits, raw + b"data: [DONE]\n\n")
    assert body == raw + b"data: [DONE]\n\n"
    assert outcome.done is True


def test_modified_empty_delta_is_dropped_instead_of_publishing_empty_choice(limits):
    relay, written = _relay(limits)
    chunk = delta_chunk(0, {"content": '<tool_call>{"name":"noop"'})
    modified = relay._consume_chunk(chunk, chunk["choices"])
    assert modified is True
    assert chunk["choices"][0]["delta"] == {}
    relay._write_chunk(b"original", chunk, modified)
    assert written == []
    relay.acc.close()


def test_pending_error_stops_before_any_subsequent_event(limits):
    wire = sse_events(
        delta_chunk(0, {"content": "first"}),
        {"error": {"message": "boom", "type": "err"}},
        delta_chunk(0, {"content": "MUST NOT LEAK"}, "stop"),
    )
    outcome, body = _run(limits, wire)
    assert outcome.incomplete is True
    assert b"MUST NOT LEAK" not in body
    assert _frames(body)[-1]["error"]["message"] == "boom"
    assert body.count(b"data: [DONE]\n\n") == 1
