"""Изолированные wire-фикстуры и типизированные семантические расхождения W0."""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace, TracebackType
from typing import Any

import pytest


class SemanticFailure(AssertionError):
    """Только расхождение результата, не ошибка импорта, настройки или транспорта."""

    def __init__(self, defect: str, actual: object, expected: object) -> None:
        self.defect, self.actual, self.expected = defect, actual, expected
        super().__init__(defect)


def semantic_equal(actual: object, expected: object, defect: str) -> None:
    """Сравнивает наблюдаемый результат с независимо заданным ожиданием."""
    if not defect:
        raise ValueError("Не задан идентификатор семантического дефекта")
    if actual != expected:
        raise SemanticFailure(defect, actual, expected)


@dataclass(frozen=True, slots=True)
class WireSettings:
    """Ограничения только локальной тестовой инфраструктуры."""

    timeout_s: float = 2.0
    join_s: float = 3.0
    poll_s: float = 0.01
    max_body_bytes: int = 1 << 20


@dataclass(frozen=True, slots=True)
class WireRequest:
    """Сырой POST, включая неполное тело после разрыва соединения."""

    path: str
    headers: tuple[tuple[str, str], ...]
    body: bytes
    declared_bytes: int


class RunningHTTPServer:
    """Настоящий HTTP-вход с одним принадлежащим фикстуре потоком."""

    def __init__(
        self,
        handler: type[BaseHTTPRequestHandler],
        settings: WireSettings | None = None,
    ) -> None:
        self.settings = settings or WireSettings()
        self.httpd = HTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(
            target=self.httpd.serve_forever,
            kwargs={"poll_interval": self.settings.poll_s},
            name="transport-test-http",
        )
        self._closed = False
        self._thread.start()

    @property
    def port(self) -> int:
        return self.httpd.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def close(self) -> None:
        """Закрывает listener и проверяет завершение потока, в том числе повторно."""
        if self._closed:
            return
        self.httpd.shutdown()
        self.httpd.server_close()
        self._thread.join(self.settings.join_s)
        if self._thread.is_alive():
            raise RuntimeError("Не завершился поток тестового HTTP-сервера")
        self._closed = True

    def __enter__(self) -> RunningHTTPServer:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class _WireHandler(BaseHTTPRequestHandler):
    owner: RecordingUpstream

    def setup(self) -> None:
        self.connection = self.request
        self.connection.settimeout(self.owner.settings.timeout_s)
        super().setup()

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:
        self.owner._receive(self)


class RecordingUpstream(RunningHTTPServer):
    """Считает POST до чтения тела и сохраняет реальные принятые байты."""

    def __init__(self, settings: WireSettings | None = None) -> None:
        self._lock = threading.Lock()
        self._posts = 0
        self._requests: list[WireRequest] = []
        self._errors: list[Exception] = []
        self.stop = threading.Event()
        self.respond: Callable[[BaseHTTPRequestHandler, bytes], None] = lambda handler, body: (
            self.json(handler, {"ok": True})
        )
        handler = type("RecordingHandler", (_WireHandler,), {"owner": self})
        super().__init__(handler, settings)

    @property
    def requests(self) -> tuple[WireRequest, ...]:
        with self._lock:
            return tuple(self._requests)

    @property
    def post_count(self) -> int:
        with self._lock:
            return self._posts

    @property
    def body_bytes(self) -> int:
        return sum(len(request.body) for request in self.requests)

    def _receive(self, handler: BaseHTTPRequestHandler) -> None:
        with self._lock:
            self._posts += 1
        try:
            length = int(handler.headers.get("Content-Length", "0"))
            if not 0 <= length <= self.settings.max_body_bytes:
                raise ValueError("Недопустимый размер тела тестового POST")
            record = self._read_body(handler, length)
            self.respond(handler, record.body)
        except Exception as error:
            with self._lock:
                self._errors.append(error)
            handler.close_connection = True

    def _read_body(self, handler: BaseHTTPRequestHandler, length: int) -> WireRequest:
        body = bytearray()
        try:
            while len(body) < length:
                piece = handler.rfile.read1(length - len(body))
                if not piece:
                    break
                body.extend(piece)
        finally:
            record = WireRequest(handler.path, tuple(handler.headers.items()), bytes(body), length)
            with self._lock:
                self._requests.append(record)
        return record

    def close(self) -> None:
        self.stop.set()
        super().close()
        if self._errors:
            raise RuntimeError("Ошибка recording-upstream") from self._errors[0]

    @staticmethod
    def json(
        handler: BaseHTTPRequestHandler,
        payload: object,
        status: int = 200,
        extra: tuple[tuple[str, str], ...] = (),
    ) -> None:
        """Отдаёт JSON либо точные байты, не меняя наблюдаемый HTTP status."""
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        handler.send_response(status)
        for name, value in (
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(data))),
            *extra,
        ):
            handler.send_header(name, value)
        handler.end_headers()
        handler.wfile.write(data)
        handler.wfile.flush()

    @staticmethod
    def sse(handler: BaseHTTPRequestHandler, body: bytes) -> None:
        """Отдаёт точный SSE, включая намеренно незавершённые сценарии."""
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        handler.wfile.write(body)
        handler.wfile.flush()


class RecordingSink:
    """Наблюдает commit заголовков и каждого downstream chunk."""

    accepts_presend_errors = False

    def __init__(self) -> None:
        self.status: int | None = None
        self.headers: tuple[tuple[str, str], ...] = ()
        self.chunks: list[bytes] = []
        self.gone = False

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        if self.status is not None:
            raise AssertionError("Повторный commit заголовков")
        self.status, self.headers = status, tuple(headers)

    def write(self, body: bytes) -> None:
        if self.status is None:
            raise AssertionError("Тело отправлено до заголовков")
        self.chunks.append(body)

    @property
    def body(self) -> bytes:
        return b"".join(self.chunks)

    def client_gone(self) -> bool:
        return self.gone

    def error_type(self) -> str:
        return ""


def make_adapter(upstream: RecordingUpstream, config: Mapping[str, Any] | None = None) -> Any:
    """Создаёт настоящий адаптер только на локальную recording-границу."""
    from adapters.passthrough_adapter import PassthroughAdapter

    resolved = {
        "kind": "passthrough",
        "base_url": upstream.base_url,
        "max_concurrent": 1,
    }
    resolved.update(config or {})
    return PassthroughAdapter("recording", resolved, lambda: {})


def wire_post(
    port: int,
    payload: Mapping[str, object],
    headers: Mapping[str, str] | None = None,
    settings: WireSettings | None = None,
) -> tuple[int, bytes]:
    """Входит в настоящий HTTP Handler, без подмены do_POST/dispatch."""
    options = settings or WireSettings()
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=options.timeout_s)
    try:
        connection.request(
            "POST",
            "/v1/chat/completions",
            json.dumps(dict(payload)).encode(),
            dict(headers or {}),
        )
        response = connection.getresponse()
        return response.status, response.read(options.max_body_bytes + 1)
    finally:
        connection.close()


@pytest.mark.parametrize("failure", ["semantic", "wrong_name", "assert", "import", "setup"])
def test_report_hook_requires_exact_semantic_exception(failure: str) -> None:
    from tests import transport_red_oracle as oracle, transport_test_support as support

    errors = {
        "semantic": support.SemanticFailure("known", 2, 1),
        "wrong_name": support.SemanticFailure("other", 2, 1),
        "assert": AssertionError("known"),
        "import": ImportError("known"),
        "setup": support.SemanticFailure("known", 2, 1),
    }
    plugin = oracle.RedReports()
    item = SimpleNamespace(
        nodeid="exact", get_closest_marker=lambda _: SimpleNamespace(args=("known",))
    )
    call = SimpleNamespace(
        when="setup" if failure == "setup" else "call",
        excinfo=SimpleNamespace(value=errors[failure]),
    )
    hook = plugin.pytest_runtest_makereport(item, call)
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(SimpleNamespace(get_result=lambda: SimpleNamespace(outcome="failed")))
    assert plugin.reports[0]["semantic"] is (failure == "semantic")
