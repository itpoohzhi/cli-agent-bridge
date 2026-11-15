"""W3: режимы инструментов и reasoning на входе Handler Claude-моста (в памяти)."""

from __future__ import annotations

import json
from itertools import product
from typing import Any

import pytest

from tests.unit._claude_bridge_tool_fakes import done_script, text_script
from tests.unit._claude_bridge_tool_http import (
    TOOL_TAGS,
    TOOLS,
    Harness,
    Reply,
    bridge as bridge,  # noqa: F401
    harness as harness,  # noqa: F401
    set_toolless_policy,
    sse_calls,
    sse_delta_text,
    sse_payloads,
)


def _assert_sse_response(body: str, frames: list) -> None:
    assert not any("error" in frame for frame in frames)
    assert all(frame["id"].startswith("chatcmpl-claudep-") for frame in frames)
    assert frames[-1]["choices"][0]["finish_reason"] == "stop"
    assert body.count("data: [DONE]\n\n") == 1


def _response_message(body: str, stream: bool) -> dict:
    if not stream:
        payload = json.loads(body)
        assert payload["id"].startswith("chatcmpl-claudep-")
        assert payload["choices"][0]["finish_reason"] == "stop"
        return payload["choices"][0]["message"]
    frames = sse_payloads(body)
    _assert_sse_response(body, frames)
    return {
        "content": sse_delta_text(body, "content"),
        "reasoning_content": sse_delta_text(body, "reasoning_content"),
        "tool_calls": sse_calls(frames),
    }


def _successful_sse_content(frames: list) -> str:
    return "".join(
        choice["delta"].get("content", "")
        for frame in frames
        if "error" not in frame
        for choice in frame["choices"]
    )


def _assert_sse_protocol_error(body: str) -> None:
    frames = sse_payloads(body)
    assert frames[-1]["error"]["type"] == "stream_error"
    assert frames[-1]["choices"][0]["finish_reason"] == "stop"
    assert body.count("data: [DONE]\n\n") == 1
    assert not sse_calls(frames)
    assert _successful_sse_content(frames) == "safe "
    assert frames[-1]["error"]["message"] == "malformed tool_call stream"


def _assert_protocol_error(reply: Reply, stream: bool) -> None:
    assert reply.status == (200 if stream else 502), reply.body
    assert "<" not in reply.body
    if stream:
        _assert_sse_protocol_error(reply.body)
    else:
        assert json.loads(reply.body)["error"]["type"] == "proxy_error"


def _assert_literal_log(log: str) -> None:
    assert all(
        field in log for field in ("req_tools=0", "mode=off", "policy=text", "rc=0")
    )
    assert "parser_error" not in log
    assert 'HTTP/1.1" 200 ' in log and 'HTTP/1.1" 502 ' not in log


@pytest.mark.parametrize(
    "case",
    tuple(
        product(
            (False, True),
            (None, "text"),
            (1, 7, 1000),
            ("", "<t", "<tool_c", "<i", "</t"),
        )
    ),
)
def test_off_text_literal_http(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    case: tuple,
) -> None:
    stream, policy, chunk_size, tail = case
    set_toolless_policy(monkeypatch, policy)
    expected = (
        'P1: Привет\n<tool_call>{"name":"x"}</tool_call> <invoke> \nP2: мир' + tail
    )
    runs = harness.play(text_script(expected, chunk_size))
    reply = harness.post(
        {"stream": stream, "messages": [{"role": "user", "content": "hi"}]}
    )
    assert reply.status == 200, reply.body
    message = _response_message(reply.body, stream)
    assert message["content"].encode() == expected.encode()
    assert message.get("tool_calls", []) == []
    assert harness.module.TOOLLESS_PURE_TEXT_HINT in runs.prompt
    assert runs.closed == [True]
    _assert_literal_log(capsys.readouterr().err)


@pytest.mark.parametrize(
    "case", tuple(product((False, True), ("error", "unknown"), TOOL_TAGS))
)
def test_off_error_http_no_tag_bytes(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    case: tuple,
) -> None:
    stream, policy, tag = case
    set_toolless_policy(monkeypatch, policy)
    runs = harness.play(text_script("safe " + tag, 1))
    reply = harness.post({"stream": stream, "messages": []})
    _assert_protocol_error(reply, stream)
    assert "parser_error" in capsys.readouterr().err
    assert runs.closed == [True]


@pytest.mark.parametrize(
    "case", tuple(product((False, True), ("none", {"type": "none"}), TOOL_TAGS))
)
def test_forbid_http_no_tag_bytes(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    case: tuple,
) -> None:
    stream, tool_choice, tag = case
    set_toolless_policy(monkeypatch, "text")
    runs = harness.play(text_script("safe " + tag, 1))
    reply = harness.post(
        {
            "stream": stream,
            "tools": TOOLS,
            "tool_choice": tool_choice,
            "messages": [],
        }
    )
    _assert_protocol_error(reply, stream)
    log = capsys.readouterr().err
    assert "mode=forbid" in log and "parser_error" in log
    assert runs.closed == [True]


@pytest.mark.parametrize("stream", (False, True))
@pytest.mark.parametrize(
    "tools,tool_choice", (([], None), (TOOLS, "none"), (TOOLS, None))
)
def test_reasoning_always_on_in_each_mode(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    stream: bool,
    tools: list,
    tool_choice: Any,
) -> None:
    set_toolless_policy(monkeypatch, "text")
    harness.play(
        done_script(
            ("thinking", "native "),
            *(("text", ch) for ch in "<think>tagged</think>answer"),
        )
    )
    reply = harness.post(
        {"stream": stream, "tools": tools, "tool_choice": tool_choice, "messages": []}
    )
    assert reply.status == 200, reply.body
    message = _response_message(reply.body, stream)
    assert message["content"] == "answer"
    assert message["reasoning_content"] == "native tagged"
    assert message.get("tool_calls", []) == []


def _emulated_calls(body: str, stream: bool) -> list:
    if stream:
        frames = sse_payloads(body)
        calls = sse_calls(frames)
        assert sse_delta_text(body, "reasoning_content") == "plan"
        assert sse_delta_text(body, "content") == ""
        assert frames[-1]["choices"][0]["finish_reason"] == "tool_calls"
    else:
        payload = json.loads(body)
        message = payload["choices"][0]["message"]
        calls = message["tool_calls"]
        assert message["reasoning_content"] == "plan"
        assert message["content"] == ""
        assert payload["choices"][0]["finish_reason"] == "tool_calls"
    return calls


@pytest.mark.parametrize("stream", (False, True))
def test_emulate_tool_call_and_reasoning_http(harness: Harness, stream: bool) -> None:
    text = (
        '<think>plan</think><tool_call>{"name":"get_weather",'
        '"arguments":{"city":"Oslo","note":""}}</tool_call>'
    )
    harness.play(text_script(text, 1))
    reply = harness.post({"stream": stream, "tools": TOOLS, "messages": []})
    assert reply.status == 200, reply.body
    calls = _emulated_calls(reply.body, stream)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "get_weather"
    assert json.loads(calls[0]["function"]["arguments"]) == {"city": "Oslo"}
