"""Сквозные passthrough-сценарии nonstream retry до первого семантического токена."""

from __future__ import annotations

import http.client
import io
import json
import time
from collections.abc import Iterator, Mapping
from typing import cast

import pytest

from adapters import passthrough_adapter
from adapters.passthrough_adapter import PassthroughAdapter
from core import nonstream_resilience
from core.liveness_signals import LivenessWindow, WindowSpec
from core.nonstream_aggregator import NonstreamError
from tests.test_openai_passthrough import (
    CollectSink,
    FakeUpstream,
    content,
    finish,
    make_adapter,
    message_of,
    ns_limits,
)

DONE = b"data: [DONE]\n\n"


@pytest.fixture
def retry_upstream() -> Iterator[FakeUpstream]:
    server = FakeUpstream()
    yield server
    server.close()


class _MemoryResponse:
    def __init__(self, payload: bytes) -> None:
        self._reader = io.BytesIO(payload)

    def readline(self, limit: int = -1) -> bytes:
        return self._reader.readline(limit)


def _response(payload: bytes) -> http.client.HTTPResponse:
    return cast(http.client.HTTPResponse, cast(object, _MemoryResponse(payload)))


def _internal_window() -> LivenessWindow:
    spec = WindowSpec(10.0, 10.0, 30.0, internal_stream=True)
    return LivenessWindow(spec)


def test_passthrough_retries_zero_signal_eof_once_before_first_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_NONSTREAM_INCOMPLETE_RETRY_MAX", "1")
    monkeypatch.setattr("core.nonstream_retry_runtime.random.uniform", lambda *_: 0.0)
    adapter = make_adapter(1, ns_limits(), sanitize=True)
    reopened = 0

    def reopen() -> http.client.HTTPResponse:
        nonlocal reopened
        reopened += 1
        return _response(content("retried") + finish(0, "stop") + DONE)

    try:
        raw = adapter._aggregate_sse(
            _response(b": keepalive\n\n"),
            _internal_window(),
            headers={"Idempotency-Key": "retry-once"},
            reopen=reopen,
            deadline=time.monotonic() + 10.0,
        )
    finally:
        adapter.shutdown()

    assert reopened == 1
    assert message_of(json.loads(raw))["content"] == "retried"


def test_passthrough_never_retries_after_first_semantic_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_NONSTREAM_INCOMPLETE_RETRY_MAX", "1")
    adapter = make_adapter(1, ns_limits(), sanitize=True)
    reopened = 0

    def reopen() -> http.client.HTTPResponse:
        nonlocal reopened
        reopened += 1
        return _response(content("duplicate") + finish(0, "stop") + DONE)

    try:
        with pytest.raises(NonstreamError) as error:
            adapter._aggregate_sse(
                _response(content("must-not-repeat")),
                _internal_window(),
                headers={"Idempotency-Key": "no-repeat"},
                reopen=reopen,
                deadline=time.monotonic() + 10.0,
            )
    finally:
        adapter.shutdown()

    assert error.value.code == "upstream_incomplete_stream"
    assert reopened == 0


def test_passthrough_retry_requires_available_bulkhead_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_NONSTREAM_INCOMPLETE_RETRY_MAX", "1")
    adapter = make_adapter(1, ns_limits(), sanitize=True)
    blocker = nonstream_resilience.NonstreamRetryBulkhead(max_inflight=1)
    assert blocker.try_acquire()
    monkeypatch.setattr(adapter, "_get_retry_bulkhead", lambda: blocker)
    reopened = 0

    def reopen() -> http.client.HTTPResponse:
        nonlocal reopened
        reopened += 1
        return _response(content("unexpected") + finish(0, "stop") + DONE)

    try:
        with pytest.raises(NonstreamError) as error:
            adapter._aggregate_sse(
                _response(b": keepalive\n\n"),
                _internal_window(),
                headers={"X-Request-Id": "bulkhead-full"},
                reopen=reopen,
                deadline=time.monotonic() + 10.0,
            )
    finally:
        blocker.release()
        adapter.shutdown()

    assert error.value.code == "upstream_incomplete_stream"
    assert reopened == 0


def _handle_request(
    adapter: PassthroughAdapter,
    request: dict[str, object],
    headers: Mapping[str, str],
) -> CollectSink:
    sink = CollectSink()
    adapter.handle(
        path="/v1/chat/completions",
        raw_body=json.dumps(request).encode(),
        request=request,
        headers=headers,
        sink=sink,
    )
    return sink


def test_handle_retries_zero_signal_eof_before_first_token(
    monkeypatch: pytest.MonkeyPatch, retry_upstream: FakeUpstream
) -> None:
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_NONSTREAM_INCOMPLETE_RETRY_MAX", "1")
    monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "0")
    monkeypatch.setattr("core.nonstream_retry_runtime.random.uniform", lambda *_: 0.0)
    deadline_modes: list[bool] = []
    real_deadlines = passthrough_adapter.request_deadlines

    def record_deadline_mode(limits: object, aggregate: bool) -> tuple[float, float]:
        deadline_modes.append(aggregate)
        return real_deadlines(limits, aggregate)

    monkeypatch.setattr(passthrough_adapter, "request_deadlines", record_deadline_mode)
    attempts = 0

    def respond(handler: object, body: bytes) -> None:
        nonlocal attempts
        attempts += 1
        payload = b": keepalive\n\n"
        if attempts == 2:
            payload = content("retried") + finish(0, "stop") + DONE
        FakeUpstream.sse(handler, payload)  # type: ignore[arg-type]

    retry_upstream.respond = respond
    adapter = make_adapter(retry_upstream.port, ns_limits(), sanitize=True)
    request: dict[str, object] = {"model": "m", "stream": False, "messages": []}
    try:
        sink = _handle_request(adapter, request, {"Idempotency-Key": "retry-once"})
    finally:
        adapter.shutdown()

    assert (sink.status, attempts, len(retry_upstream.requests)) == (200, 2, 2)
    assert deadline_modes == [True]
    assert message_of(json.loads(sink.body))["content"] == "retried"


def test_handle_bulkhead_refuses_retry_without_second_upstream_request(
    monkeypatch: pytest.MonkeyPatch, retry_upstream: FakeUpstream
) -> None:
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_NONSTREAM_INCOMPLETE_RETRY_MAX", "1")
    monkeypatch.setenv("BRIDGE_NONSTREAM_RETRY_MAX_INFLIGHT", "1")
    retry_upstream.respond = lambda handler, body: FakeUpstream.sse(  # type: ignore[arg-type]
        handler, b": keepalive\n\n"
    )
    adapter = make_adapter(retry_upstream.port, ns_limits(), sanitize=True)
    blocker = adapter._get_retry_bulkhead()
    assert blocker.try_acquire()
    request: dict[str, object] = {"model": "m", "stream": False, "messages": []}
    try:
        sink = _handle_request(adapter, request, {"X-Request-Id": "bulkhead-full"})
    finally:
        blocker.release()
        adapter.shutdown()

    assert len(retry_upstream.requests) == 1
    assert sink.status == 502
    assert json.loads(sink.body)["error"]["type"] == "upstream_incomplete_stream"
