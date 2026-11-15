"""VER-004: SSE, однобайтовые разбиения и EOF шести passthrough-конфигураций."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import json
import pytest

from tests.unit._passthrough_tool_mode import (
    FORBIDDEN,
    LITERAL,
    POLICY_ENV,
    _CollectSink,
    _assert_fail_closed,
    _assert_success,
    _assert_text_transport,
    _messages,
    _payloads,
    _published_calls,
    _request,
    _upstream_body,
    adapter as adapter,
    call_adapter as call_adapter,
    manifests as manifests,
    parser_spies as parser_spies,
)
from tests.passthrough_stream_testlib import DONE, chunk, content, finish, frame


@pytest.fixture(params=(True,), ids=("sse",))
def stream(request: pytest.FixtureRequest) -> bool:
    return request.param


def test_off_text_preserves_literals_without_any_response_parser(
    call_adapter: Callable[..., _CollectSink],
    stream: bool,
    parser_spies: tuple[Mock, Mock],
) -> None:
    sink = call_adapter(_request(stream), _upstream_body(LITERAL, stream))
    assert sink.status == 200
    for spy in parser_spies:
        spy.assert_not_called()
    assert not _published_calls(sink, stream)
    text = "".join(message.get("content") or "" for message in _messages(sink, stream))
    assert text.encode("utf-8") == LITERAL.encode("utf-8")
    assert not any(item.get("error") for item in _payloads(sink, stream))
    _assert_text_transport(sink, stream)


def test_off_rejects_upstream_native_tool_calls(
    call_adapter: Callable[..., _CollectSink], stream: bool
) -> None:
    sink = call_adapter(_request(stream), _upstream_body("", stream, native=True))
    _assert_fail_closed(sink, stream)
    assert b"secret_fn" not in sink.body


def test_off_error_rejects_markup_without_leak(
    call_adapter: Callable[..., _CollectSink],
    stream: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(POLICY_ENV, "error")
    sink = call_adapter(_request(stream), _upstream_body(FORBIDDEN, stream))
    _assert_fail_closed(sink, stream)
    assert b"<tool_call>" not in sink.body
    assert b"secret_fn" not in sink.body
    assert not any(message.get("content") for message in _messages(sink, stream))


@pytest.mark.parametrize(
    "choice", ("none", {"type": "none"}), ids=("string-none", "object-none")
)
def test_forbid_rejects_markup_and_hides_tool_name(
    call_adapter: Callable[..., _CollectSink], stream: bool, choice: Any
) -> None:
    sink = call_adapter(
        _request(stream, tools=True, choice=choice), _upstream_body(FORBIDDEN, stream)
    )
    _assert_fail_closed(sink, stream)
    assert b"<tool_call>" not in sink.body
    assert b"secret_fn" not in sink.body
    assert not any(message.get("content") for message in _messages(sink, stream))


def test_emulate_still_extracts_valid_tool_calls(
    call_adapter: Callable[..., _CollectSink],
    stream: bool,
    parser_spies: tuple[Mock, Mock],
) -> None:
    literal = '<tool_call>{"name":"noop","arguments":{}}</tool_call>'
    sink = call_adapter(_request(stream, tools=True), _upstream_body(literal, stream))
    _assert_success(sink, stream)
    calls = _published_calls(sink, stream)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "noop"
    assert json.loads(calls[0]["function"]["arguments"]) == {}
    assert not any(message.get("content") for message in _messages(sink, stream))
    assert parser_spies[0].call_count >= 1
    assert parser_spies[1].call_count >= 1


@pytest.mark.parametrize(
    "choice", ("none", {"type": "none"}), ids=("string-none", "object-none")
)
@pytest.mark.parametrize("tail", ("<tool_c", "<t"))
@pytest.mark.parametrize("eof", (False, True), ids=("done", "transport-eof"))
def test_forbid_rejects_one_char_split_sse_eof_prefix(
    call_adapter: Callable[..., _CollectSink], choice: Any, tail: str, eof: bool
) -> None:
    sink = call_adapter(
        _request(True, tools=True, choice=choice), _upstream_body(tail, True, eof=eof)
    )
    _assert_fail_closed(sink, True)
    assert not _published_calls(sink, True)
    assert not any(message.get("content") for message in _messages(sink, True))
    assert tail.encode("utf-8") not in sink.body


@pytest.mark.parametrize("tail", ("<tool_c", "<t"))
def test_off_error_rejects_one_char_split_sse_eof_prefix(
    call_adapter: Callable[..., _CollectSink],
    tail: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(POLICY_ENV, "error")
    sink = call_adapter(_request(True), _upstream_body(tail, True))
    _assert_fail_closed(sink, True)
    assert not any(message.get("content") for message in _messages(sink, True))


def test_off_text_reasoning_channel_does_not_reparse_literals(
    call_adapter: Callable[..., _CollectSink],
) -> None:
    reasoning = '<tool_call>{"name":"secret_fn"}</tool_call>'
    events = (
        frame(
            chunk(
                [
                    {
                        "index": 0,
                        "delta": {"reasoning_content": reasoning},
                        "finish_reason": None,
                    }
                ]
            )
        )
        + content("answer")
        + finish(0, "stop")
        + DONE
    )
    sink = call_adapter(_request(True), events)
    assert sink.status == 200
    messages = _messages(sink, True)
    assert "".join(m.get("reasoning_content") or "" for m in messages) == reasoning
    assert "".join(m.get("content") or "" for m in messages) == "answer"
    assert not _published_calls(sink, True)
