"""L1: заголовки итогового ответа и выбор media type при нормализации тела."""

from __future__ import annotations

from typing import Any

import pytest

from adapters.passthrough_adapter import PassthroughAdapter
from tests.unit._passthrough_tool_branches import (
    EMULATE_SPEC,
    adapter as adapter,
    completion_body,
    http_response,
    isolated_env as isolated_env,
    sink as sink,
)
from tests.unit._passthrough_tool_sink import _CollectSink

VALID_CALL = '<tool_call>{"name":"noop","arguments":{}}</tool_call>'
JSON_TYPE = "application/json; charset=utf-8"
TOOLS = [
    {"type": "function", "function": {"name": "noop", "parameters": {"type": "object"}}}
]
OPTIONS: dict[str, Any] = {
    "tool_schemas": {"noop": TOOLS[0]},
    "mode_spec": EMULATE_SPEC,
    "sanitize": True,
}


def _content_types(sink: _CollectSink) -> list[str]:
    return [value for name, value in sink.headers if name.lower() == "content-type"]


def test_aggregate_replaces_any_case_content_type_with_single_json_type(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    resp = http_response(
        200, [("CONTENT-TYPE", "text/event-stream"), ("X-Trace", "t1")]
    )
    assert adapter._emit_response(resp, sink, (b"{}", True)) is True
    assert _content_types(sink) == [JSON_TYPE]
    assert ("X-Trace", "t1") in sink.headers
    assert ("Content-Length", "2") in sink.headers
    assert sink.body == b"{}"


def test_non_aggregate_keeps_upstream_content_type_spelling(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    resp = http_response(200, [("CONTENT-TYPE", "Text/Plain")])
    adapter._emit_response(resp, sink, (b"abc", False))
    assert ("CONTENT-TYPE", "Text/Plain") in sink.headers
    assert ("Content-Length", "3") in sink.headers


def test_no_upstream_headers_yield_only_computed_length_for_non_aggregate(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    adapter._emit_response(http_response(204, []), sink, (b"", False))
    assert sink.headers == [("Content-Length", "0")]
    assert sink.status == 204


def test_no_upstream_headers_yield_length_and_json_type_for_aggregate(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    adapter._emit_response(http_response(200, []), sink, (b"{}", True))
    assert sink.headers == [("Content-Length", "2"), ("Content-Type", JSON_TYPE)]


def test_emit_drops_upstream_length_and_hop_by_hop_headers(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    resp = http_response(
        200, [("Connection", "close"), ("Keep-Alive", "timeout=5")], b"zz"
    )
    adapter._emit_response(resp, sink, (b"abcd", False))
    assert [(k, v) for k, v in sink.headers if k.lower() == "content-length"] == [
        ("Content-Length", "4")
    ]
    assert not any(k.lower() in ("connection", "keep-alive") for k, _ in sink.headers)


def _normalize(
    adapter: PassthroughAdapter, resp: Any, body: bytes, aggregate: bool
) -> bytes:
    return adapter._normalize_body(resp, (body, aggregate), dict(OPTIONS))


@pytest.mark.parametrize(
    "headers", ([], [("Content-Type", "")], [("Content-Type", "text/event-stream")])
)
def test_aggregate_flag_forces_json_media_regardless_of_upstream_header(
    adapter: PassthroughAdapter, headers: list[tuple[str, str]]
) -> None:
    body = completion_body(VALID_CALL)
    result = _normalize(adapter, http_response(200, headers), body, True)
    assert result != body
    assert b'"tool_calls"' in result


@pytest.mark.parametrize(
    "headers", ([], [("Content-Type", "")], [("Content-Type", "text/event-stream")])
)
def test_without_aggregate_flag_non_json_media_keeps_body(
    adapter: PassthroughAdapter, headers: list[tuple[str, str]]
) -> None:
    body = completion_body(VALID_CALL)
    assert _normalize(adapter, http_response(200, headers), body, False) == body


def test_without_aggregate_flag_mixed_case_json_media_is_normalized(
    adapter: PassthroughAdapter,
) -> None:
    resp = http_response(200, [("Content-Type", "Application/Json")])
    body = completion_body(VALID_CALL)
    assert b'"tool_calls"' in _normalize(adapter, resp, body, False)


@pytest.mark.parametrize("encoding", ("gzip", "BR"))
def test_non_identity_encoding_blocks_normalization(
    adapter: PassthroughAdapter, encoding: str
) -> None:
    resp = http_response(
        200, [("Content-Type", "application/json"), ("Content-Encoding", encoding)]
    )
    body = completion_body(VALID_CALL)
    assert _normalize(adapter, resp, body, False) == body


def test_identity_encoding_in_any_case_still_normalizes(
    adapter: PassthroughAdapter,
) -> None:
    headers = [("Content-Type", "application/json"), ("Content-Encoding", "Identity")]
    body = completion_body(VALID_CALL)
    assert b'"tool_calls"' in _normalize(
        adapter, http_response(200, headers), body, False
    )


def test_non_200_status_is_never_normalized_even_for_aggregate(
    adapter: PassthroughAdapter,
) -> None:
    body = completion_body(VALID_CALL)
    assert _normalize(adapter, http_response(502, []), body, True) == body
