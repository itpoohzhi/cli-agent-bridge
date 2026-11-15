"""L1: проверка SSE до агрегации, открытия транспорта и границ ответа."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import adapters.passthrough_adapter as passthrough
from core.backend_adapter import PreSendTransientError
from core.nonstream_aggregator import NonstreamError
from core.tool_emulation import LiveParserError
from core.tool_mode import ToolMode, ToollessTagPolicy, build_mode_spec
from tests.unit._passthrough_tool_branches import (
    EMULATE_SPEC,
    adapter as adapter,
    delta_chunk,
    http_response,
    isolated_env as isolated_env,
    limits as limits,
    sink as sink,
)


def _event(chunk):
    data = json.dumps(chunk)
    return b"data: " + data.encode() + b"\n\n", data


@pytest.mark.parametrize("mode", (ToolMode.OFF, ToolMode.FORBID))
def test_checked_events_accepts_comments_non_json_and_non_list_choices(limits, mode):
    spec = build_mode_spec(mode, ToollessTagPolicy.ERROR)
    events = [
        (b": keepalive\n\n", None), (b"data: not-json\n\n", "not-json"),
        _event({"choices": "not-a-list"}),
        _event(delta_chunk(0, {"content": "ok"})),
        _event(delta_chunk(0, {}, "stop")), (b"data: [DONE]\n\n", " [DONE] "),
    ]
    assert list(passthrough._checked_events(iter(events), spec, limits)) == events


@pytest.mark.parametrize("mode", (ToolMode.OFF, ToolMode.FORBID))
def test_checked_events_finishes_partial_tag_at_done_not_comment_or_eof(limits, mode):
    spec = build_mode_spec(mode, ToollessTagPolicy.ERROR)
    content = _event(delta_chunk(0, {"content": "safe <t"}))
    comment = (b": comment\n\n", None)
    done = (b"data: [DONE]\n\n", " [DONE] ")
    after = object()
    source = iter([content, comment, done, after])
    # Итератор должен упасть на DONE, а не при чтении комментария или после EOF.
    checked = passthrough._checked_events(source, spec, limits)
    assert next(checked) == content
    assert next(checked) == comment
    with pytest.raises(LiveParserError):
        next(checked)
    assert next(source) is after


def test_checked_events_emulate_passes_raw_calls_once_without_a_parser(limits):
    events = [_event(delta_chunk(0, {"content": '<tool_call>{"name":"noop"'}))]
    source = Mock()
    source.__iter__ = Mock(side_effect=[iter(events), AssertionError("iterated twice")])
    assert list(passthrough._checked_events(source, EMULATE_SPEC, limits)) == events
    source.__iter__.assert_called_once_with()


@pytest.mark.parametrize("internal", (False, True))
def test_open_response_relaxes_socket_according_to_internal_stream(
    adapter, sink, monkeypatch, internal,
):
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    request = {"model": "m", "stream": not internal, "messages": []}
    conn = Mock(sock=Mock())
    conn.getresponse.return_value = http_response(200, [], b"ok")
    slide = Mock(deadline_s=time.monotonic() + 100)
    monkeypatch.setattr(passthrough, "open_sliding_deadline", Mock(return_value=slide))
    monkeypatch.setattr(passthrough.threading, "Thread", Mock())
    monkeypatch.setattr(adapter, "_open", Mock(return_value=conn))
    monkeypatch.setattr(adapter, "_respond", Mock(return_value=True))
    adapter.handle(
        path="/v1/chat/completions", raw_body=json.dumps(request).encode(),
        request=request, headers={}, sink=sink,
    )
    slide.relax_socket.assert_called_once_with(
        conn.sock, adapter.limits.read_timeout_s, internal,
    )
    assert json.loads(adapter._open.call_args.args[1])["stream"] is True
    assert adapter.active_count() == 0
    conn.getresponse.return_value.close()


def test_expired_presend_budget_fails_before_pool_access(adapter, monkeypatch):
    pool = Mock()
    monkeypatch.setattr(adapter, "_pool", pool)
    now = time.monotonic()
    with pytest.raises(PreSendTransientError) as raised:
        adapter._open("/v1/chat/completions", b"{}", {}, deadline=now + 10,
                      presend_deadline=now - 1)
    assert raised.value.status_code == 504
    pool.get_connection.assert_not_called()
    pool.close_all.assert_not_called()


def _connection(adapter, monkeypatch):
    conn = Mock(sock=None)
    monkeypatch.setattr(adapter._pool, "get_connection", Mock(return_value=(conn, False)))
    return conn


def test_upstream_key_replaces_both_client_auth_headers(adapter, monkeypatch):
    conn = _connection(adapter, monkeypatch)
    monkeypatch.setattr(adapter, "_upstream_key", "secret-up")
    adapter._open("/v1/chat/completions", b"{}", {
        "Authorization": "Bearer client-tok", "X-Api-Key": "client-x", "X-Custom": "keep",
    })
    sent = conn.request.call_args.kwargs["headers"]
    assert sent["Authorization"] == "Bearer secret-up"
    assert {k.lower(): v for k, v in sent.items() if k.lower() in (
        "authorization", "x-api-key",
    )} == {"authorization": "Bearer secret-up"}
    assert sent["X-Custom"] == "keep"


def test_configured_headers_replace_client_names_case_insensitively(adapter, monkeypatch):
    conn = _connection(adapter, monkeypatch)
    monkeypatch.setattr(adapter, "_upstream_headers", Mock(return_value={
        "X-Custom": "new", "Accept": "application/json",
    }))
    adapter._open("/v1/chat/completions", b"{}", {"x-custom": "old", "X-Keep": "1"})
    sent = conn.request.call_args.kwargs["headers"]
    assert sent["X-Custom"] == "new"
    assert "x-custom" not in sent
    assert sent["X-Keep"] == "1"
    assert sent["Accept"] == "application/json"


def test_respond_passes_sliding_deadline_to_stream_relay(adapter, sink, monkeypatch):
    relay = Mock(return_value=True)
    slide = object()
    monkeypatch.setattr(adapter, "_relay_stream", relay)
    resp = http_response(200, [("Content-Type", "text/event-stream")])
    assert adapter._respond(resp, {"stream": True}, sink, 123.0, slide=slide) is True
    assert relay.call_args.kwargs["deadline"] is slide
    resp.close()


def test_aggregate_retry_guard_receives_empty_headers_instead_of_none(adapter, monkeypatch):
    error = NonstreamError(502, "upstream_incomplete_stream", "incomplete")
    monkeypatch.setattr(adapter, "_read_agg_once", Mock(side_effect=error))
    guard = Mock(return_value=False)
    monkeypatch.setattr(passthrough, "should_retry_incomplete_nonstream", guard)
    monkeypatch.setattr(adapter, "_retry_runtime", Mock())
    monkeypatch.setattr(passthrough, "retry_incomplete_once", Mock(return_value=None))
    window = SimpleNamespace(internal_stream=True, s_count=0)
    with pytest.raises(NonstreamError) as raised:
        adapter._aggregate_sse(Mock(), window, headers=None)
    assert raised.value is error
    assert guard.call_args.kwargs["headers"] == {}


def test_relay_stream_replaces_upstream_content_type_exactly_once(adapter, sink, monkeypatch):
    outcome = passthrough.StreamOutcome(reader_stopped=True)
    monkeypatch.setattr(passthrough, "relay_sse", Mock(return_value=outcome))
    resp = http_response(200, [("cOnTeNt-TyPe", "text/event-stream; charset=utf-8"),
                               ("X-Upstream", "keep")])
    assert adapter._relay_stream(resp, None, sink, True) is True
    assert [h for h in sink.headers if h[0].lower() == "content-type"] == [
        ("Content-Type", "text/event-stream"),
    ]
    assert ("X-Upstream", "keep") in sink.headers
    resp.close()
