"""L1: выбор пути ответа passthrough: SSE-relay, агрегация, JSON-нормализация, заголовки."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from adapters.passthrough_adapter import PassthroughAdapter
from tests.unit._passthrough_tool_branches import (
    EMULATE_SPEC,
    OFF_SPEC,
    adapter as adapter,
    completion_body,
    delta_chunk,
    http_response,
    isolated_env as isolated_env,
    sink as sink,
    sse_events,
)
from tests.unit._passthrough_tool_sink import _CollectSink

VALID_CALL = '<tool_call>{"name":"noop","arguments":{}}</tool_call>'
TOOLS = [
    {"type": "function", "function": {"name": "noop", "parameters": {"type": "object"}}}
]
WITH_TOOLS = {"model": "m", "messages": [], "tools": TOOLS}
NO_TOOLS = {"model": "m", "messages": []}
SSE_WIRE = sse_events(delta_chunk(0, {"content": "hi"}), delta_chunk(0, {}, "stop"))
AGG_WINDOW = SimpleNamespace(internal_stream=True, expired=lambda: False)
PLAIN_WINDOW = SimpleNamespace(internal_stream=False, expired=lambda: False)


def _respond(
    adapter: PassthroughAdapter,
    resp: Any,
    request: dict[str, Any],
    sink: _CollectSink,
    **kw: Any,
) -> bool:
    return adapter._respond(resp, request, sink, time.monotonic() + 60, **kw)


def _stub_aggregate(
    monkeypatch: pytest.MonkeyPatch, adapter: PassthroughAdapter, body: bytes = b""
) -> Mock:
    stub = Mock(return_value=body or completion_body("agg"))
    monkeypatch.setattr(adapter, "_aggregate_sse", stub)
    return stub


def _first_message(sink: _CollectSink) -> dict[str, Any]:
    return json.loads(sink.body)["choices"][0]["message"]


@pytest.mark.parametrize(
    "media",
    (
        "application/json",
        "Application/JSON; Charset=UTF-8",
        "APPLICATION/VND.API+JSON",
    ),
)
def test_json_media_type_is_normalized_case_insensitively(
    adapter: PassthroughAdapter, sink: _CollectSink, media: str
) -> None:
    resp = http_response(200, [("Content-Type", media)], completion_body(VALID_CALL))
    assert _respond(adapter, resp, WITH_TOOLS, sink) is True
    message = _first_message(sink)
    assert message["tool_calls"][0]["function"]["name"] == "noop"
    assert VALID_CALL not in (message.get("content") or "")


@pytest.mark.parametrize(
    "headers", ([], [("Content-Type", "")], [("Content-Type", "text/plain")])
)
def test_absent_empty_or_non_json_media_type_keeps_body_bytes(
    adapter: PassthroughAdapter, sink: _CollectSink, headers: list[tuple[str, str]]
) -> None:
    body = completion_body(VALID_CALL)
    assert (
        _respond(adapter, http_response(200, headers, body), WITH_TOOLS, sink) is True
    )
    assert sink.body == body
    assert sink.status == 200


def test_encoded_json_body_is_not_parsed(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    body = completion_body(VALID_CALL)
    headers = [("Content-Type", "application/json"), ("Content-Encoding", "gzip")]
    _respond(adapter, http_response(200, headers, body), WITH_TOOLS, sink)
    assert sink.body == body


@pytest.mark.parametrize("status", (400, 429, 500))
def test_non_200_json_is_forwarded_with_status_and_never_normalized(
    adapter: PassthroughAdapter, sink: _CollectSink, status: int
) -> None:
    body = completion_body(VALID_CALL)
    resp = http_response(status, [("Content-Type", "application/json")], body)
    assert _respond(adapter, resp, WITH_TOOLS, sink) is True
    assert (sink.status, sink.body) == (status, body)


@pytest.mark.parametrize(
    "media", ("text/event-stream", "Text/Event-Stream; charset=utf-8")
)
def test_sse_200_without_aggregation_is_relayed(
    adapter: PassthroughAdapter,
    sink: _CollectSink,
    monkeypatch: pytest.MonkeyPatch,
    media: str,
) -> None:
    stub = _stub_aggregate(monkeypatch, adapter)
    resp = http_response(200, [("Content-Type", media)], SSE_WIRE)
    assert _respond(adapter, resp, NO_TOOLS, sink) is True
    stub.assert_not_called()
    assert sink.status == 200
    assert ("Content-Type", "text/event-stream") in sink.headers
    assert ("Cache-Control", "no-cache") in sink.headers
    assert sink.body == SSE_WIRE


def test_sse_200_with_internal_stream_window_is_aggregated_to_json(
    adapter: PassthroughAdapter, sink: _CollectSink, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = _stub_aggregate(monkeypatch, adapter)
    resp = http_response(200, [("Content-Type", "text/event-stream")], SSE_WIRE)
    assert _respond(adapter, resp, NO_TOOLS, sink, window=AGG_WINDOW) is True
    stub.assert_called_once()
    assert stub.call_args.kwargs["mode_spec"] == OFF_SPEC
    assert _first_message(sink)["content"] == "agg"
    media = [value for name, value in sink.headers if name.lower() == "content-type"]
    assert media == ["application/json; charset=utf-8"]


def test_aggregated_body_is_normalized_even_though_upstream_said_sse(
    adapter: PassthroughAdapter, sink: _CollectSink, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_aggregate(monkeypatch, adapter, completion_body(VALID_CALL))
    resp = http_response(200, [("Content-Type", "text/event-stream")], SSE_WIRE)
    _respond(adapter, resp, WITH_TOOLS, sink, window=AGG_WINDOW)
    assert _first_message(sink)["tool_calls"][0]["function"]["name"] == "noop"


def test_aggregation_window_does_not_aggregate_a_json_response(
    adapter: PassthroughAdapter, sink: _CollectSink, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = _stub_aggregate(monkeypatch, adapter)
    body = completion_body("plain")
    resp = http_response(200, [("Content-Type", "application/json")], body)
    assert _respond(adapter, resp, NO_TOOLS, sink, window=AGG_WINDOW) is True
    stub.assert_not_called()
    assert sink.body == body
    assert ("Content-Type", "application/json") in sink.headers


def test_non_200_sse_content_type_is_not_relayed_or_aggregated(
    adapter: PassthroughAdapter, sink: _CollectSink, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = _stub_aggregate(monkeypatch, adapter)
    relay = Mock()
    monkeypatch.setattr(adapter, "_relay_stream", relay)
    resp = http_response(503, [("Content-Type", "text/event-stream")], b"busy")
    assert _respond(adapter, resp, NO_TOOLS, sink, window=AGG_WINDOW) is True
    stub.assert_not_called()
    relay.assert_not_called()
    assert (sink.status, sink.body) == (503, b"busy")


def test_response_body_passes_reopen_callback_only_when_provided(
    adapter: PassthroughAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = _stub_aggregate(monkeypatch, adapter)
    resp = http_response(200, [("Content-Type", "text/event-stream")], SSE_WIRE)
    options = {"window": AGG_WINDOW, "mode_spec": EMULATE_SPEC, "headers": {"h": "1"}}
    body, aggregate = adapter._response_body(resp, options)
    assert aggregate is True and body == completion_body("agg")
    assert stub.call_args.kwargs["reopen"] is None
    assert stub.call_args.kwargs["headers"] == {"h": "1"}
    adapter._response_body(resp, {**options, "reopen": Mock(return_value=resp)})
    assert callable(stub.call_args.kwargs["reopen"])


@pytest.mark.parametrize(
    "window,wire,expected",
    (
        (None, (200, "text/event-stream"), False),
        (PLAIN_WINDOW, (200, "text/event-stream"), False),
        (AGG_WINDOW, (200, "text/event-stream"), True),
        (AGG_WINDOW, (200, "application/json"), False),
        (AGG_WINDOW, (502, "text/event-stream"), False),
    ),
)
def test_response_body_aggregates_only_for_200_sse_with_internal_stream(
    adapter: PassthroughAdapter,
    monkeypatch: pytest.MonkeyPatch,
    window: Any,
    wire: tuple[int, str],
    expected: bool,
) -> None:
    stub = _stub_aggregate(monkeypatch, adapter)
    status, media = wire
    resp = http_response(status, [("Content-Type", media)], b"raw-body")
    body, aggregate = adapter._response_body(
        resp, {"window": window, "mode_spec": OFF_SPEC}
    )
    assert aggregate is expected
    assert stub.called is expected
    assert body == (completion_body("agg") if expected else b"raw-body")


def test_response_body_raises_timeout_when_deadline_passed_after_read(
    adapter: PassthroughAdapter,
) -> None:
    resp = http_response(200, [("Content-Type", "application/json")], b"{}")
    with pytest.raises(TimeoutError, match="total deadline"):
        adapter._response_body(resp, {"deadline": time.monotonic() - 1})
