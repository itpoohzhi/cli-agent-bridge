"""Wire-границы: connect без записи, явный отказ и запрет второго POST."""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import threading
from dataclasses import replace
from typing import Any

import pytest

from core.backend_adapter import PreSendTransientError
from core.route_health_policy import (
    FailureCategory, RetryBudgetConfig, classify_provider_failure, compute_attempt_decision,
)
from tests.test_transport_modularity import RUN
from tests.test_transport_eligibility import (
    gateway, post, request_body, stage_entry, success, transport_options as transport_options,
)
from tests.transport_test_support import (
    RecordingSink, RecordingUpstream, make_adapter, require_wave_artifacts, semantic_equal,
)

CONNECT_FAILURES = [
    ConnectionRefusedError("fixture TCP refusal"),
    socket.gaierror("fixture DNS failure"),
    TimeoutError("fixture connect timeout"),
    ssl.SSLError("fixture TLS handshake failure"),
    OSError("fixture CONNECT tunnel failed"),
]


def _handle(adapter: Any, sink: RecordingSink, request: dict) -> None:
    adapter.handle(path="/v1/chat/completions", raw_body=json.dumps(request).encode(),
                   request=request, headers={}, sink=sink, window=None)


def _refuse(upstream: RecordingUpstream, status: int) -> bytes:
    body = json.dumps({"error": {"type": "proxy_connect_failed", "retryable": True}}).encode()
    upstream.respond = lambda handler, request: upstream.json(handler, body, status)
    return body


def _legacy_decision(config: RetryBudgetConfig, index: int, elapsed: float, outcome: dict) -> Any:
    """PR17 считает бюджет по категории, но ещё не знает фазу исполнения POST."""
    status = outcome["status_code"]
    category = classify_provider_failure(status, "").category if status else (
        FailureCategory.CAPACITY_EXHAUSTED
    )
    return compute_attempt_decision(config, index, elapsed, category)


def test_unknown_load_envelope_cannot_approve_first_call_bounds() -> None:
    require_wave_artifacts(RUN)
    packet = json.loads((RUN / "architecture/architecture-packet.json").read_bytes())
    highload = packet["highload_resilience"]
    operands = highload["hl_env"]
    assert operands["N_entities_max"]["value"] is None
    assert all(item["status"] == "UNKNOWN" for item in operands.values() if item["value"] is None)
    assert highload["status"] == "UNKNOWN_NOT_APPROVABLE"
    assert highload["no_fabricated_sizing"] is True


@pytest.mark.semantic_red("revoke_before_send_has_no_body")
@pytest.mark.parametrize("stream", [False, True])
def test_credential_revoke_after_readiness_prevents_wire_send(
    monkeypatch: pytest.MonkeyPatch, stream: bool,
) -> None:
    from core import passthrough_facade as facade

    monkeypatch.setenv("TRANSPORT_FIXTURE_API_KEY", "fixture-not-a-real-key")
    original, drawn = facade.route_order, []

    def draw(*args: Any) -> Any:
        for backend in original(*args):
            drawn.append(backend)
            monkeypatch.delenv("TRANSPORT_FIXTURE_API_KEY", raising=False)
            yield backend

    monkeypatch.setattr(facade, "route_order", draw)
    with RecordingUpstream() as first, RecordingUpstream() as reserve:
        success(reserve, stream)
        config = {"first": {"api_key_ref": "env:TRANSPORT_FIXTURE_API_KEY"}}
        with gateway(monkeypatch, {"first": first, "reserve": reserve}, config) as (port, _):
            status, body = post(port, request_body(stream))
        actual = (status, b"ok" in body, drawn, first.post_count, first.body_bytes, reserve.post_count)
    semantic_equal(actual, (200, True, ["first", "reserve"], 0, 0, 1),
                   "revoke_before_send_has_no_body")


@pytest.mark.semantic_red("typed_connect_before_write")
@pytest.mark.parametrize("failure", CONNECT_FAILURES)
def test_stage_w2_c_connect_errors_have_zero_wire_body(
    monkeypatch: pytest.MonkeyPatch, failure: OSError,
) -> None:
    original = http.client.HTTPConnection.connect
    with RecordingUpstream() as upstream:
        adapter, observed = make_adapter(upstream), None

        def connect(connection: http.client.HTTPConnection) -> None:
            if connection.port == upstream.port:
                raise failure
            original(connection)

        monkeypatch.setattr(http.client.HTTPConnection, "connect", connect)
        opener = stage_entry("core.passthrough_exchange", "open_request",
                             lambda adapter, path, raw, headers: adapter._open(path, raw, headers))
        try:
            try:
                connection = opener(adapter, "/v1/chat/completions", b"{}", {})
            except (PreSendTransientError, OSError) as error:
                observed = (isinstance(error, PreSendTransientError), error.__cause__ is failure)
            else:
                connection.close()
        finally:
            adapter.shutdown()
        actual = (observed, upstream.post_count, upstream.body_bytes)
    semantic_equal(actual, ((True, True), 0, 0), "typed_connect_before_write")


@pytest.mark.semantic_red("connect_failure_advances_without_body")
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("failure", CONNECT_FAILURES)
def test_stage_w2_c_http_connect_failure_advances_without_body(
    monkeypatch: pytest.MonkeyPatch, stream: bool, failure: OSError,
) -> None:
    original, request = http.client.HTTPConnection.connect, request_body(stream)
    with RecordingUpstream() as first, RecordingUpstream() as reserve:
        success(reserve, stream)

        def connect(connection: http.client.HTTPConnection) -> None:
            if connection.port == first.port:
                raise failure
            original(connection)

        monkeypatch.setattr(http.client.HTTPConnection, "connect", connect)
        with gateway(monkeypatch, {"first": first, "reserve": reserve}) as (port, _):
            status, body = post(port, request)
        actual = (status, b"ok" in body, first.post_count, first.body_bytes,
                  reserve.post_count, reserve.body_bytes)
    semantic_equal(actual, (200, True, 0, 0, 1, len(json.dumps(request).encode())),
                   "connect_failure_advances_without_body")


@pytest.mark.semantic_red("safe_refusal_before_downstream_commit")
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [401, 429, 503])
def test_stage_w2_d_safe_refusal_is_typed_without_local_replay(stream: bool, status: int) -> None:
    with RecordingUpstream() as upstream:
        body = _refuse(upstream, status)
        adapter, sink, refusal = make_adapter(upstream), RecordingSink(), None
        sink.accepts_presend_errors = True
        request = request_body(stream)
        try:
            try:
                _handle(adapter, sink, request)
            except PreSendTransientError as error:
                refusal = (error.status_code, error.response_body)
        finally:
            adapter.shutdown()
        actual = (refusal, sink.status, sink.body, upstream.post_count, upstream.body_bytes)
    semantic_equal(actual, ((status, body), None, b"", 1, len(json.dumps(request).encode())),
                   "safe_refusal_before_downstream_commit")


@pytest.mark.semantic_red("unsafe_status_no_nested_replay")
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [403, 500, 502, 504])
def test_stage_w2_e_unsafe_status_has_one_wire_post(stream: bool, status: int) -> None:
    with RecordingUpstream() as upstream:
        body = _refuse(upstream, status)
        adapter, sink = make_adapter(upstream), RecordingSink()
        request = request_body(stream)
        try:
            _handle(adapter, sink, request)
        finally:
            adapter.shutdown()
        assert (sink.status, sink.body) == (status, body)
        assert all(record.body == json.dumps(request).encode() for record in upstream.requests)
        actual = (upstream.post_count, upstream.body_bytes)
    semantic_equal(actual, (1, len(json.dumps(request).encode())), "unsafe_status_no_nested_replay")


@pytest.mark.semantic_red("safe_refusal_advances_route_once")
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [401, 429, 503])
def test_stage_w2_m_safe_refusal_advances_route_once(
    monkeypatch: pytest.MonkeyPatch, stream: bool, status: int,
) -> None:
    request = request_body(stream)
    raw = json.dumps(request).encode()
    with RecordingUpstream() as first, RecordingUpstream() as reserve:
        _refuse(first, status)
        success(reserve, stream)
        with gateway(monkeypatch, {"first": first, "reserve": reserve}) as (port, _):
            result, body = post(port, request)
        assert all(record.body == raw for record in (*first.requests, *reserve.requests))
        actual = (result, b"ok" in body, first.post_count, first.body_bytes,
                  reserve.post_count, reserve.body_bytes)
    semantic_equal(actual, (200, True, 1, len(raw), 1, len(raw)),
                   "safe_refusal_advances_route_once")


@pytest.mark.semantic_red("terminal_status_no_route_replay")
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [403, 500, 502, 504])
def test_http_unsafe_status_never_reaches_reserve(
    monkeypatch: pytest.MonkeyPatch, stream: bool, status: int,
) -> None:
    request = request_body(stream)
    with RecordingUpstream() as first, RecordingUpstream() as reserve:
        refused = _refuse(first, status)
        success(reserve, stream)
        with gateway(monkeypatch, {"first": first, "reserve": reserve}) as (port, _):
            actual_status, body = post(port, request)
        assert (actual_status, body) == (status, refused)
        actual = (first.post_count, first.body_bytes, reserve.post_count, reserve.body_bytes)
    semantic_equal(actual, (1, len(json.dumps(request).encode()), 0, 0),
                   "terminal_status_no_route_replay")


@pytest.mark.parametrize("stream", [False, True])
def test_partial_write_never_sends_second_post(
    monkeypatch: pytest.MonkeyPatch, stream: bool,
) -> None:
    request, received = request_body(stream), threading.Event()
    raw, original = json.dumps(request).encode(), http.client.HTTPConnection.send
    with RecordingUpstream() as upstream, RecordingUpstream() as reserve:
        upstream.respond = lambda handler, body: received.set()
        success(reserve, stream)

        def send(connection: http.client.HTTPConnection, data: Any) -> None:
            if connection.port == upstream.port and data == raw:
                original(connection, memoryview(raw)[:9])
                connection.sock.shutdown(socket.SHUT_WR)
                raise BrokenPipeError("fixture partial body write")
            original(connection, data)

        monkeypatch.setattr(http.client.HTTPConnection, "send", send)
        with gateway(monkeypatch, {"first": upstream, "reserve": reserve}) as (port, _):
            status, _ = post(port, request)
            assert received.wait(upstream.settings.timeout_s)
        assert (upstream.post_count, upstream.body_bytes) == (1, 9)
        assert upstream.requests[0].declared_bytes == len(raw)
        assert upstream.requests[0].body == raw[:9]
        assert status == 502
        assert (reserve.post_count, reserve.body_bytes) == (0, 0)


@pytest.mark.parametrize("stream", [False, True])
def test_read_timeout_after_body_never_sends_second_post(
    monkeypatch: pytest.MonkeyPatch, stream: bool,
) -> None:
    with RecordingUpstream() as first, RecordingUpstream() as reserve:
        first.respond = lambda handler, body: first.stop.wait(first.settings.timeout_s)
        success(reserve, stream)
        with gateway(monkeypatch, {"first": first, "reserve": reserve}) as (port, _):
            import server

            adapter = server.BACKENDS.get("first")
            adapter.limits = replace(adapter.limits, read_timeout_s=0.05)
            status, _ = post(port, request_body(stream))
        assert status == 504
        assert (first.post_count, first.body_bytes) == (1, len(json.dumps(request_body(stream)).encode()))
        assert (reserve.post_count, reserve.body_bytes) == (0, 0)


@pytest.mark.parametrize("delta", [
    {"content": "committed-marker"},
    {"reasoning_content": "committed-marker"},
    {"tool_calls": [{"index": 0, "id": "call-1", "type": "function",
                     "function": {"name": "probe", "arguments": "{}"}}]},
])
def test_committed_sse_never_replays(
    monkeypatch: pytest.MonkeyPatch, delta: dict,
) -> None:
    data = b"data: " + json.dumps({"choices": [{"index": 0, "delta": delta}]}).encode() + b"\n\n"
    request = request_body(True)
    if "tool_calls" in delta:
        data += b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\n\n'
        request["tools"] = [{"type": "function", "function": {"name": "probe", "parameters": {"type": "object"}}}]
    with RecordingUpstream() as first, RecordingUpstream() as reserve:
        first.respond = lambda handler, body: first.sse(handler, data)
        success(reserve, True)
        with gateway(monkeypatch, {"first": first, "reserve": reserve}) as (port, _):
            status, body = post(port, request)
        assert status == 200 and b'"content":"ok"' not in body
        assert body.count(b"committed-marker") + body.count(b"call-1") == 1
        assert (first.post_count, first.body_bytes) == (1, len(json.dumps(request).encode()))
        assert (reserve.post_count, reserve.body_bytes) == (0, 0)
