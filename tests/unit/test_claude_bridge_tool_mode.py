"""W3: режимы инструментов и reasoning на настоящем HTTP-входе Claude-моста."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from inspect import unwrap
from itertools import product
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests import test_claude_bridge as legacy

bridge = legacy.bridge
_FakeRun = legacy.FakeRun
TOOL_TAGS = (
    '<tool_call>{"name":"x"}</tool_call>',
    "<invoke>",
    "<t",
    "<tool_c",
    "<i",
    "</t",
)


@pytest.fixture
def http_bridge(
    bridge: Any, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Any, int]]:
    """Повторяет существующий стенд, откатывая также состояние фейкового хода."""
    monkeypatch.setattr(_FakeRun, "script", [])
    monkeypatch.setattr(_FakeRun, "captured", {})
    yield from unwrap(legacy.http_bridge)(bridge, monkeypatch)


def _set_toolless_policy(monkeypatch: pytest.MonkeyPatch, policy: str | None) -> None:
    if policy is None:
        monkeypatch.delenv("BRIDGE_TOOLLESS_TOOL_TAG_POLICY", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_TOOLLESS_TOOL_TAG_POLICY", policy)


def _text_script(text: str, chunk_size: int) -> list:
    return legacy._done_script(
        *(("text", text[i : i + chunk_size]) for i in range(0, len(text), chunk_size))
    )


def _sse_calls(frames: list) -> list:
    return [
        call
        for frame in frames
        for choice in frame.get("choices", [])
        for call in choice["delta"].get("tool_calls", [])
    ]


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
    frames = legacy._sse_payloads(body)
    _assert_sse_response(body, frames)
    return {
        "content": legacy._sse_delta_text(body, "content"),
        "reasoning_content": legacy._sse_delta_text(body, "reasoning_content"),
        "tool_calls": _sse_calls(frames),
    }


def _successful_sse_content(frames: list) -> str:
    return "".join(
        choice["delta"].get("content", "")
        for frame in frames
        if "error" not in frame
        for choice in frame["choices"]
    )


def _assert_sse_protocol_error(body: str) -> None:
    frames = legacy._sse_payloads(body)
    assert frames[-1]["error"]["type"] == "stream_error"
    assert frames[-1]["choices"][0]["finish_reason"] == "stop"
    assert body.count("data: [DONE]\n\n") == 1
    assert not _sse_calls(frames)
    assert _successful_sse_content(frames) == "safe "
    assert frames[-1]["error"]["message"] == "malformed tool_call stream"


def _assert_protocol_error(status: int, body: str, stream: bool) -> None:
    assert status == (200 if stream else 502), body
    assert "<" not in body
    if stream:
        _assert_sse_protocol_error(body)
    else:
        assert json.loads(body)["error"]["type"] == "proxy_error"


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
    http_bridge: tuple,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    case: tuple,
) -> None:
    bridge, port = http_bridge
    stream, policy, chunk_size, tail = case
    _set_toolless_policy(monkeypatch, policy)
    expected = (
        'P1: Привет\n<tool_call>{"name":"x"}</tool_call> <invoke> \nP2: мир' + tail
    )
    _FakeRun.script = _text_script(expected, chunk_size)
    status, body = legacy._post(
        port, {"stream": stream, "messages": [{"role": "user", "content": "hi"}]}
    )
    assert status == 200, body
    message = _response_message(body, stream)
    assert message["content"].encode() == expected.encode()
    assert message.get("tool_calls", []) == []
    assert bridge.TOOLLESS_PURE_TEXT_HINT in _FakeRun.captured["prompt"]
    assert _FakeRun.captured["closed"]
    _assert_literal_log(capsys.readouterr().err)


@pytest.mark.parametrize(
    "case", tuple(product((False, True), ("error", "unknown"), TOOL_TAGS))
)
def test_off_error_http_no_tag_bytes(
    http_bridge: tuple,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    case: tuple,
) -> None:
    _bridge, port = http_bridge
    stream, policy, tag = case
    _set_toolless_policy(monkeypatch, policy)
    _FakeRun.script = _text_script("safe " + tag, 1)
    status, body = legacy._post(port, {"stream": stream, "messages": []})
    _assert_protocol_error(status, body, stream)
    assert "parser_error" in capsys.readouterr().err
    assert _FakeRun.captured["closed"]


@pytest.mark.parametrize(
    "case", tuple(product((False, True), ("none", {"type": "none"}), TOOL_TAGS))
)
def test_forbid_http_no_tag_bytes(
    http_bridge: tuple,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    case: tuple,
) -> None:
    _bridge, port = http_bridge
    stream, tool_choice, tag = case
    _set_toolless_policy(monkeypatch, "text")
    _FakeRun.script = _text_script("safe " + tag, 1)
    status, body = legacy._post(
        port,
        {
            "stream": stream,
            "tools": legacy.TOOLS,
            "tool_choice": tool_choice,
            "messages": [],
        },
    )
    _assert_protocol_error(status, body, stream)
    log = capsys.readouterr().err
    assert "mode=forbid" in log and "parser_error" in log
    assert _FakeRun.captured["closed"]


@pytest.mark.parametrize("stream", (False, True))
@pytest.mark.parametrize(
    "tools,tool_choice", (([], None), (legacy.TOOLS, "none"), (legacy.TOOLS, None))
)
def test_reasoning_always_on_in_each_mode(
    http_bridge: tuple,
    monkeypatch: pytest.MonkeyPatch,
    stream: bool,
    tools: list,
    tool_choice: Any,
) -> None:
    _bridge, port = http_bridge
    _set_toolless_policy(monkeypatch, "text")
    _FakeRun.script = legacy._done_script(
        ("thinking", "native "),
        *(("text", ch) for ch in "<think>tagged</think>answer"),
    )
    status, body = legacy._post(
        port,
        {"stream": stream, "tools": tools, "tool_choice": tool_choice, "messages": []},
    )
    assert status == 200, body
    message = _response_message(body, stream)
    assert message["content"] == "answer"
    assert message["reasoning_content"] == "native tagged"
    assert message.get("tool_calls", []) == []


def _emulated_calls(body: str, stream: bool) -> list:
    if stream:
        frames = legacy._sse_payloads(body)
        calls = _sse_calls(frames)
        assert legacy._sse_delta_text(body, "reasoning_content") == "plan"
        assert legacy._sse_delta_text(body, "content") == ""
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
def test_emulate_tool_call_and_reasoning_http(http_bridge: tuple, stream: bool) -> None:
    _bridge, port = http_bridge
    text = '<think>plan</think><tool_call>{"name":"get_weather","arguments":{"city":"Oslo","note":""}}</tool_call>'
    _FakeRun.script = _text_script(text, 1)
    status, body = legacy._post(
        port, {"stream": stream, "tools": legacy.TOOLS, "messages": []}
    )
    assert status == 200, body
    calls = _emulated_calls(body, stream)
    assert len(calls) == 1
    assert json.loads(calls[0]["function"]["arguments"]) == {"city": "Oslo"}
