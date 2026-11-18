"""Регрессии запрета локального replay и передачи HTTP-отказов маршрутизатору."""

from __future__ import annotations

import json
import sys
import threading
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.passthrough_adapter import (
    ClientGone,
    PassthroughAdapter,
    PassthroughLimits,
    ResponseSink,
)
from core.passthrough_adapter_runtime import PassthroughRouteRefusal
from core.presend_retry_policy import (
    ENV_PRESEND_MAX_RETRIES,
    ENV_PRESEND_RETRY_DELAY_S,
    ENV_PRESEND_RETRY_MAX_DELAY_S,
    compute_presend_retry_delay,
    is_retryable_presend_payload,
    resolve_presend_response,
)

class _Upstream:
    """Локальный HTTP-сервер со счётчиком физических запросов."""

    def __init__(self, respond: Callable[[BaseHTTPRequestHandler, int], None]) -> None:
        self.requests = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: Any) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                outer.requests += 1
                respond(self, outer.requests)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = int(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class _Sink(ResponseSink):
    def __init__(self) -> None:
        self.status: int | None = None
        self.headers: list[tuple[str, str]] = []
        self.chunks: list[bytes] = []

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        self.status = status
        self.headers = headers

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    @property
    def body(self) -> bytes:
        return b"".join(self.chunks)


def _send(
    handler: BaseHTTPRequestHandler,
    status: int,
    body: bytes,
    content_type: str = "application/json",
    headers: tuple[tuple[str, str], ...] = (),
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    for name, value in headers:
        handler.send_header(name, value)
    handler.end_headers()
    handler.wfile.write(body)


def _adapter(port: int) -> PassthroughAdapter:
    return PassthroughAdapter(
        "test",
        {
            "kind": "passthrough",
            "base_url": f"http://127.0.0.1:{port}/v1",
            "max_concurrent": 2,
        },
        lambda: {},
        limits=PassthroughLimits(),
        sanitize=False,
    )


def _call(
    adapter: PassthroughAdapter, sink: _Sink | None = None, stream: bool = False
) -> _Sink:
    sink = _Sink() if sink is None else sink
    adapter.handle(
        path="/v1/chat/completions", raw_body=json.dumps({"stream": stream}).encode(),
        request={"stream": stream}, headers={}, sink=sink,
    )
    return sink


@pytest.mark.parametrize(
    ("content_type", "failure"),
    [
        ("application/json", b'{"type":"proxy_connect_failed","retryable":true}'),
        ("text/event-stream", b'data: {"type":"proxy_connect_failed","retryable":true}\n\n'),
    ],
)
def test_retryable_502_is_forwarded_verbatim_without_replay(
    content_type: str, failure: bytes
) -> None:
    def respond(handler: BaseHTTPRequestHandler, attempt: int) -> None:
        _send(
            handler, 502 if attempt == 1 else 200,
            failure if attempt == 1 else b'{"ok":true}', content_type,
        )

    upstream = _Upstream(respond)
    adapter = _adapter(upstream.port)
    try:
        sink = _call(adapter, stream=content_type == "text/event-stream")
        assert upstream.requests == 1
        assert sink.status == 502
        assert sink.body == failure
        assert ("Content-Type", content_type) in sink.headers
    finally:
        adapter.shutdown()
        upstream.close()


@pytest.mark.parametrize("status", [401, 429, 503, 500, 502, 504])
def test_route_refusal_propagates_without_sleep_or_replay(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    failure = b'{"error":{"type":"proxy_unavailable","retryable":true}}'
    sleeps: list[float] = []
    monkeypatch.setenv(ENV_PRESEND_RETRY_MAX_DELAY_S, "2")
    monkeypatch.setattr("adapters.passthrough_adapter.time.sleep", sleeps.append)
    upstream = _Upstream(lambda h, _: _send(h, status, failure, headers=(("Retry-After", "1.25"),)))
    adapter = _adapter(upstream.port)
    sink = _Sink()
    sink.accepts_presend_errors = True
    try:
        with pytest.raises(PassthroughRouteRefusal) as raised:
            _call(adapter, sink)
        assert upstream.requests == 1
        assert raised.value.status_code == status
        assert raised.value.response_body == failure
        assert ("Retry-After", "1.25") in raised.value.response_headers
        assert sleeps == []
        assert sink.status is None
        assert sink.body == b""
    finally:
        adapter.shutdown()
        upstream.close()


@pytest.mark.parametrize(
    "failure",
    [
        b'{"error":{"type":"bad_gateway","retryable":false}}',
        b"plain text 502",
    ],
)
def test_non_retryable_502_is_forwarded_without_retry(failure: bytes) -> None:
    upstream = _Upstream(lambda handler, _attempt: _send(handler, 502, failure))
    adapter = _adapter(upstream.port)
    try:
        sink = _call(adapter)
        assert upstream.requests == 1
        assert sink.status == 502
        assert sink.body == failure
    finally:
        adapter.shutdown()
        upstream.close()


def test_retry_setting_does_not_allow_502_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_PRESEND_MAX_RETRIES, "2")

    def respond(handler: BaseHTTPRequestHandler, attempt: int) -> None:
        body = json.dumps({"type": "proxy_connect_failed", "retryable": True, "attempt": attempt}).encode()
        _send(handler, 502, body)

    upstream = _Upstream(respond)
    adapter = _adapter(upstream.port)
    try:
        sink = _call(adapter)
        assert upstream.requests == 1
        assert sink.status == 502
        assert json.loads(sink.body)["attempt"] == 1
    finally:
        adapter.shutdown()
        upstream.close()


@pytest.mark.parametrize(("status", "expected"), [(401, True), (429, True), (503, True),
                                                (502, True), (500, True), (599, True),
                                                (200, False), (204, False), (299, False)])
@pytest.mark.parametrize(
    "body",
    [
        b'{"retryable":true}',
        b'{"error":{"type":"proxy_unavailable"}}',
        b'{"retryable":false,"type":"proxy_connect_failed"}',
        b'{"retryable":true,"type":"proxy_connect_failed"}',
        b"[]", b"",
    ],
)
def test_retryable_payload_classifier(status: int, body: bytes, expected: bool) -> None:
    """F-004: классификация — любой не-2xx, без status-allowlist."""
    assert is_retryable_presend_payload(status, (), body) is expected


def test_retry_delay_uses_retry_after_floor_and_exponential_cap() -> None:
    env = {
        ENV_PRESEND_RETRY_DELAY_S: "2.2",
        ENV_PRESEND_RETRY_MAX_DELAY_S: "8",
    }
    headers = (("retry-after", "3"),)
    assert compute_presend_retry_delay(headers, 0, env) == 3
    assert compute_presend_retry_delay(headers, 1, env) == 6
    assert compute_presend_retry_delay(headers, 2, env) == 8
    assert compute_presend_retry_delay((("Retry-After", "1"),), 0, env) == 2.2


@pytest.mark.parametrize("status", [401, 429, 503, 500, 502, 504])
def test_sink_accepting_presend_errors_gets_original_response(status: int) -> None:
    body = b'{"type":"proxy_connect_failed","retryable":true}'
    response = _Response(status, body)
    sink = _Sink()
    sink.accepts_presend_errors = True
    adapter = _PolicyAdapter()
    with pytest.raises(PassthroughRouteRefusal) as raised:
        resolve_presend_response(
            adapter, HTTPConnection("127.0.0.1"), response, sink, lambda: pytest.fail("retried")
        )
    assert raised.value.status_code == status
    assert raised.value.response_body == body
    assert raised.value.response_headers == (*response.getheaders(), ("Content-Length", str(len(body))))
    assert adapter.reads == 1


@pytest.mark.parametrize(("status", "accepts"), [
    (401, False), (429, False), (503, False), (502, False), (500, False),
    (200, True), (204, True), (299, True),
])
def test_response_without_route_refusal_is_not_read_or_replayed(status: int, accepts: bool) -> None:
    conn = HTTPConnection("127.0.0.1")
    response, sink = _Response(status, b'{"retryable":true}'), _Sink()
    sink.accepts_presend_errors = accepts
    adapter = _PolicyAdapter()
    result = resolve_presend_response(
        adapter, conn, response, sink, lambda: pytest.fail("retried")
    )
    assert result == (conn, response, False, None)
    assert adapter.reads == 0


class _Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body

    def getheaders(self) -> list[tuple[str, str]]:
        return [("Content-Type", "application/json"), ("Retry-After", "1.25")]


class _PolicyAdapter:
    def __init__(self) -> None:
        self.reads = 0

    def _read_presend_body(self, response: _Response) -> bytes:
        self.reads += 1
        return response.body

    def _response_headers(self, response: _Response) -> list[tuple[str, str]]:
        return response.getheaders()

    def _client_gone_exc(self) -> Exception:
        return ClientGone()


def test_modularity_line_bounds() -> None:
    root = Path(__file__).resolve().parents[1]
    adapter_lines = (root / "adapters/passthrough_adapter.py").read_text().splitlines()
    policy_lines = (root / "core/presend_retry_policy.py").read_text().splitlines()
    assert len(adapter_lines) <= 1837
    assert len(policy_lines) <= 300
