"""Regression tests for retrying explicit pre-send proxy failures."""

from __future__ import annotations

import json
import sys
import threading
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
from core.backend_adapter import PreSendTransientError
from core.presend_retry_policy import (
    ENV_PRESEND_MAX_RETRIES,
    ENV_PRESEND_RETRY_DELAY_S,
    ENV_PRESEND_RETRY_MAX_DELAY_S,
    compute_presend_retry_delay,
    is_retryable_presend_payload,
    resolve_presend_response,
)


class _Upstream:
    """Small local HTTP upstream driven by a per-request callback."""

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


def _call(adapter: PassthroughAdapter) -> _Sink:
    sink = _Sink()
    adapter.handle(
        path="/v1/chat/completions",
        raw_body=b"{}",
        request={},
        headers={},
        sink=sink,
    )
    return sink


@pytest.fixture(autouse=True)
def _fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_PRESEND_RETRY_DELAY_S, "0.001")
    monkeypatch.setenv(ENV_PRESEND_RETRY_MAX_DELAY_S, "0.001")


@pytest.mark.parametrize(
    ("content_type", "success_body"),
    [
        ("application/json", b'{"ok":true}'),
        (
            "text/event-stream",
            b'data: {"choices":[{"index":0,"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
        ),
    ],
)
def test_retryable_502_retries_and_only_sends_success(
    content_type: str, success_body: bytes
) -> None:
    failure = json.dumps(
        {
            "type": "proxy_connect_failed",
            "message": "cannot connect to opencode.ai:443 via http://127.0.0.1:10815: ConnectionRefusedError",
            "retryable": True,
        }
    ).encode()

    def respond(handler: BaseHTTPRequestHandler, attempt: int) -> None:
        _send(handler, 502, failure) if attempt == 1 else _send(
            handler, 200, success_body, content_type
        )

    upstream = _Upstream(respond)
    adapter = _adapter(upstream.port)
    try:
        sink = _call(adapter)
        assert upstream.requests == 2
        assert sink.status == 200
        assert sink.body == success_body
        assert failure not in sink.body
    finally:
        adapter.shutdown()
        upstream.close()


def test_retryable_503_honors_retry_after_and_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = b'{"error":{"type":"proxy_unavailable","retryable":true}}'
    sleeps: list[float] = []
    monkeypatch.setenv(ENV_PRESEND_RETRY_MAX_DELAY_S, "2")
    monkeypatch.setattr("core.presend_retry_policy.time.sleep", sleeps.append)

    def respond(handler: BaseHTTPRequestHandler, attempt: int) -> None:
        if attempt == 1:
            _send(handler, 503, failure, headers=(("Retry-After", "1.25"),))
        else:
            _send(handler, 200, b'{"ok":true}')

    upstream = _Upstream(respond)
    adapter = _adapter(upstream.port)
    try:
        sink = _call(adapter)
        assert upstream.requests == 2
        assert sink.status == 200
        assert sink.body == b'{"ok":true}'
        assert sleeps == [pytest.approx(1.25)]
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


def test_retry_exhaustion_forwards_final_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_PRESEND_MAX_RETRIES, "2")

    def respond(handler: BaseHTTPRequestHandler, attempt: int) -> None:
        body = json.dumps(
            {
                "type": "proxy_connect_failed",
                "retryable": True,
                "attempt": attempt,
            }
        ).encode()
        _send(handler, 502, body)

    upstream = _Upstream(respond)
    adapter = _adapter(upstream.port)
    try:
        sink = _call(adapter)
        assert upstream.requests == 3
        assert sink.status == 502
        assert json.loads(sink.body)["attempt"] == 3
    finally:
        adapter.shutdown()
        upstream.close()


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (502, b'{"retryable":true}', True),
        (503, b'{"error":{"type":"proxy_unavailable"}}', True),
        (502, b'{"retryable":false,"type":"proxy_connect_failed"}', False),
        (500, b'{"retryable":true}', False),
        (502, b"[]", False),
        (502, b"", False),
    ],
)
def test_retryable_payload_classifier(status: int, body: bytes, expected: bool) -> None:
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


def test_sink_accepting_presend_errors_gets_original_response() -> None:
    body = b'{"type":"proxy_connect_failed","retryable":true}'
    response = _Response(502, body)
    sink = _Sink()
    sink.accepts_presend_errors = True
    adapter = _PolicyAdapter()
    with pytest.raises(PreSendTransientError) as raised:
        resolve_presend_response(
            adapter, _Connection(), response, sink, lambda: pytest.fail("retried")
        )
    assert raised.value.status_code == 502
    assert raised.value.response_body == body


class _Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body

    def getheaders(self) -> list[tuple[str, str]]:
        return [("Content-Type", "application/json")]


class _Connection:
    def close(self) -> None:
        return


class _PolicyAdapter:
    def _read_presend_body(self, response: _Response) -> bytes:
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
