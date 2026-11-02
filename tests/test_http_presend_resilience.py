"""HTTP-регрессии retry до первой клиентской записи на настоящих сокетах."""

from __future__ import annotations

import functools
import http.client
import io
import json
import socket
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast, override

import pytest

import server
from adapters.passthrough_adapter import PassthroughAdapter, PassthroughLimits
from core.lifecycle import KeepaliveController, PreSendRetry

SUCCESS = b'{"id":"once","choices":[{"message":{"content":"ok"}}]}'
CONTENT = b'data: {"id":"once","choices":[{"index":0,"delta":{"content":"first"},"finish_reason":null}]}\n\n'
TERMINAL = (
    b'data: {"id":"once","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
)
DONE = b"data: [DONE]\n\n"
WAIT_S = 5.0
Action = Callable[[BaseHTTPRequestHandler], None]
ServePassthrough = Callable[[PassthroughAdapter, bytes, dict[str, object], str], None]


@pytest.fixture(autouse=True)
def retry_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Убирает случайность backoff, сохраняя настоящий retry и HTTP-транспорт."""
    for name, value in {
        "BRIDGE_MAX_RETRIES": "3",
        "BRIDGE_RETRY_BUDGET_S": "60",
        "BRIDGE_RETRY_BACKOFF_S": "0.001",
        "BRIDGE_RETRY_MAX_BACKOFF_S": "0.001",
        "BRIDGE_RETRY_CANCEL_POLL_S": "0.001",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        server,
        "PreSendRetry",
        functools.partial(PreSendRetry, rng=lambda _low, high: high),
    )


def json_reply(status: int, body: bytes | None = None) -> Action:
    payload = (
        body
        if body is not None
        else (
            SUCCESS
            if status == 200
            else json.dumps({"error": {"code": status}}).encode()
        )
    )

    def respond(handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(payload)))
        handler.end_headers()
        _ = handler.wfile.write(payload)
        handler.wfile.flush()

    return respond


def sse_reply(body: bytes) -> Action:
    def respond(handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        _ = handler.wfile.write(body)
        handler.wfile.flush()

    return respond


def reset_reply(handler: BaseHTTPRequestHandler) -> None:
    """Обрывает upstream после чтения POST, до первой строки HTTP-ответа."""
    connection = cast(socket.socket, handler.connection)
    connection.shutdown(socket.SHUT_RDWR)
    connection.close()


class HttpStand:
    """Два локальных HTTP-сервера: upstream и настоящий passthrough-шов Handler."""

    def __init__(self, actions: list[Action]) -> None:
        self.requests: list[bytes] = []
        self.statuses: list[int] = []
        self.emitted_at_attempt: list[int] = []
        self.errors: list[BaseException] = []
        self.finished: threading.Event = threading.Event()
        outer = self

        class Upstream(BaseHTTPRequestHandler):
            @override
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.requests.append(body)
                index = len(outer.requests) - 1
                actions[min(index, len(actions) - 1)](self)

        self.upstream: ThreadingHTTPServer = ThreadingHTTPServer(
            ("127.0.0.1", 0), Upstream
        )
        self.upstream.daemon_threads = True
        port = self.upstream.server_port
        adapter = PassthroughAdapter(
            "http-retry-test",
            {"base_url": f"http://127.0.0.1:{port}/v1", "kind": "passthrough"},
            dict,
            limits=PassthroughLimits(
                connect_timeout_s=1, read_timeout_s=1, total_timeout_s=2
            ),
        )

        class Bridge(server.Handler):
            @override
            def log_message(self, fmt: str, *args: object) -> None:
                return

            @override
            def send_response(self, code: int, message: str | None = None) -> None:
                outer.statuses.append(code)
                super().send_response(code, message)

            @override
            def end_headers(self) -> None:
                outer.emitted_at_attempt.append(len(outer.requests))
                super().end_headers()

            @override
            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                try:
                    request = cast(dict[str, object], json.loads(raw))
                    serve = cast(ServePassthrough, getattr(self, "_serve_passthrough"))
                    serve(adapter, raw, request, "http-test")
                except BaseException as exc:
                    outer.errors.append(exc)
                    raise
                finally:
                    outer.finished.set()

        self.bridge: ThreadingHTTPServer = ThreadingHTTPServer(("127.0.0.1", 0), Bridge)
        self.bridge.daemon_threads = True
        self.threads: list[threading.Thread] = [
            threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01})
            for httpd in (self.upstream, self.bridge)
        ]
        for thread in self.threads:
            thread.start()

    def connect(self, *, stream: bool = False) -> socket.socket:
        body = json.dumps(
            {"model": "http-test", "stream": stream, "messages": []}
        ).encode()
        sock = socket.create_connection(("127.0.0.1", self.bridge.server_port), WAIT_S)
        sock.sendall(
            b"POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\n"
            + b"Connection: close\r\nContent-Type: application/json\r\nContent-Length: "
            + str(len(body)).encode()
            + b"\r\n\r\n"
            + body
        )
        return sock

    def response(self, *, stream: bool = False) -> tuple[int, bytes]:
        with self.connect(stream=stream) as sock:
            received = bytearray()
            while data := sock.recv(65536):
                received.extend(data)
        assert self.finished.wait(WAIT_S), "HTTP handler не завершился"
        assert not self.errors
        raw = bytes(received)
        assert raw.count(b"HTTP/1.1 ") == 1, raw

        class ResponseSocket:
            def makefile(self, _mode: str) -> io.BytesIO:
                return io.BytesIO(raw)

        response = http.client.HTTPResponse(
            cast(socket.socket, cast(object, ResponseSocket()))
        )
        response.begin()
        return response.status, response.read()

    def close(self) -> None:
        for httpd in (self.bridge, self.upstream):
            httpd.shutdown()
            httpd.server_close()
        for thread in self.threads:
            thread.join(timeout=WAIT_S)
            assert not thread.is_alive()


@contextmanager
def stand(actions: list[Action]) -> Generator[HttpStand]:
    instance = HttpStand(actions)
    try:
        yield instance
    finally:
        instance.close()


@pytest.mark.parametrize("stream", [False, True])
def test_real_502_503_retry_before_any_client_bytes(stream: bool) -> None:
    final = CONTENT + TERMINAL + DONE if stream else SUCCESS
    success = sse_reply(final) if stream else json_reply(200, final)
    with stand([json_reply(502), json_reply(503), success]) as instance:
        status, body = instance.response(stream=stream)
        assert (status, body) == (200, final)
        assert len(instance.requests) == 3
        assert len(set(instance.requests)) == 1
        assert instance.statuses == [200]
        assert instance.emitted_at_attempt == [3]


@pytest.mark.parametrize("stream", [False, True])
def test_real_reset_before_response_retries(stream: bool) -> None:
    final = CONTENT + TERMINAL + DONE if stream else SUCCESS
    success = sse_reply(final) if stream else json_reply(200, final)
    with stand([reset_reply, success]) as instance:
        assert instance.response(stream=stream) == (200, final)
        assert len(instance.requests) == 2
        assert instance.statuses == [200]
        assert instance.emitted_at_attempt == [2]


@pytest.mark.parametrize(
    "prefix",
    [
        b"",
        b": keepalive\n\n",
        KeepaliveController.sse_data_chunk(
            "http-test", completion_id="heartbeat", created=1
        ).encode(),
        CONTENT,
    ],
)
def test_real_stream_eof_after_headers_heartbeat_or_content_never_replays(
    prefix: bytes,
) -> None:
    with stand([sse_reply(prefix), sse_reply(CONTENT + TERMINAL + DONE)]) as instance:
        status, body = instance.response(stream=True)
        assert status == 200
        assert body.startswith(prefix)
        assert TERMINAL not in body
        assert len(instance.requests) == 1
        assert instance.statuses == [200]
        assert instance.emitted_at_attempt == [1]


@pytest.mark.parametrize("retries", [0, 1, 3])
def test_real_http_retry_exhaustion_is_bounded(
    monkeypatch: pytest.MonkeyPatch, retries: int
) -> None:
    monkeypatch.setenv("BRIDGE_MAX_RETRIES", str(retries))
    with stand([json_reply(503)]) as instance:
        status, body = instance.response()
        assert status == 503
        assert json.loads(body)["error"]["code"] == 503
        assert len(instance.requests) == retries + 1
        assert instance.statuses == [503]
        assert instance.emitted_at_attempt == [retries + 1]


def test_real_http_retry_budget_does_not_start_unaffordable_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_RETRY_BUDGET_S", "0.01")
    monkeypatch.setenv("BRIDGE_RETRY_BACKOFF_S", "1")
    monkeypatch.setenv("BRIDGE_RETRY_MAX_BACKOFF_S", "1")
    with stand([json_reply(502), json_reply(200)]) as instance:
        status, body = instance.response()
        assert status == 502
        assert json.loads(body)["error"]["code"] == 502
        assert len(instance.requests) == 1
        assert instance.statuses == [502]


def test_real_client_cancel_during_retry_backoff_stops_upstream_posts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_RETRY_BACKOFF_S", "1")
    monkeypatch.setenv("BRIDGE_RETRY_MAX_BACKOFF_S", "1")
    failed = threading.Event()

    def first(handler: BaseHTTPRequestHandler) -> None:
        json_reply(503)(handler)
        failed.set()

    with stand([first, json_reply(200)]) as instance:
        sock = instance.connect()
        try:
            assert failed.wait(WAIT_S)
        finally:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        assert instance.finished.wait(WAIT_S)
        assert len(instance.requests) == 1
        assert not instance.errors
