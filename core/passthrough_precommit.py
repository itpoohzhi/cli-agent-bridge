# fmt: off
"""Кооперативное ожидание заголовков без изменения окна полезной активности."""
from __future__ import annotations

# Динамический шов старого адаптера и пользовательских HTTP-приёмников.
# pyright: reportAny=false, reportExplicitAny=false
import http.client
import socket
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any, cast, final

from core.passthrough_sliding_window import SlidingDeadline
from core.route_health_policy import redact_diagnostic_text
from core.stream_resilience_policy import (
    CrossHopConfig,
    raise_error,
    validate_cross_hop_timeouts,
)
from core.stream_resilience_runtime import (
    EarlyCommitSinkCoordinator,
    StreamResilienceConfig,
)


@final
class _SinkBoundary:
    def __init__(self, sink: Any) -> None:
        self.sink: Any = sink
        self.start: Callable[..., object] = sink.start
        self.write: Callable[..., object] = sink.write
    @property
    def client_gone(self) -> bool:
        value = getattr(self.sink, "client_gone", False)
        if callable(value):
            value = value()
        return bool(value)
@final
class PrecommitSink:
    """Старый HTTP-ответ до flush, единственный SSE-писатель после flush."""
    def __init__( self, sink: Any, streaming: bool, formatter: Callable[..., str],
        gone_error: Callable[[], Exception], ) -> None:
        self.boundary: _SinkBoundary = _SinkBoundary(sink)
        self.config: StreamResilienceConfig = StreamResilienceConfig.from_env()
        self.streaming: bool = streaming
        self.gone_error: Callable[[], Exception] = gone_error
        self.started_s: float = time.monotonic()
        self.coordinator: EarlyCommitSinkCoordinator = EarlyCommitSinkCoordinator(
            self.boundary, self.config, clock=lambda: time.monotonic(),
            error_formatter=formatter, )
    def __getattr__(self, name: str) -> Any:
        return getattr(self.boundary.sink, name)
    def client_gone(self) -> bool:
        return any((self.boundary.client_gone, self.coordinator.cancelled))
    @property
    def accepts_presend_errors(self) -> bool:
        accepts = bool(getattr(self.boundary.sink, "accepts_presend_errors", False))
        return all((accepts, not self.coordinator.headers_committed))
    def start(self, status: int, headers: list[tuple[str, str]]) -> object:
        action = (self.boundary.start, self._committed_start)[
            self.coordinator.headers_committed ]
        return action(status, headers)
    def _committed_start(self, status: int, headers: list[tuple[str, str]]) -> None:
        content_type = dict((k.lower(), v) for k, v in headers).get("content-type", "")
        valid = all((status == 200, "text/event-stream" in content_type.lower()))
        if not valid:
            self.coordinator.emit_error_and_done(
                redact_diagnostic_text(f"upstream returned HTTP {status}, not SSE") )
    def write(self, data: bytes) -> object:
        action = (self.boundary.write, self.coordinator.emit_chunk)[
            self.coordinator.headers_committed ]
        return action(data)
    def read_response(
        self, conn: http.client.HTTPConnection, slide: SlidingDeadline, join_s: float
    ) -> http.client.HTTPResponse:
        cooperative = self.config.flag_enabled("passthrough_early_flush_enabled")
        readers = ( conn.getresponse,
            lambda: _HeaderWait(conn, self, slide).receive(join_s), )
        response = readers[all((self.streaming, cooperative))]()
        if self.coordinator.headers_committed:
            self._committed_start(response.status, response.getheaders())
        return response
def wrap_sink( sink: Any, request: Mapping[str, object], formatter: Callable[..., str],
    gone_error: Callable[[], Exception], ) -> PrecommitSink:
    return PrecommitSink(sink, bool(request.get("stream")), formatter, gone_error)
def request_window(window: Any, slide: SlidingDeadline) -> tuple[Any, SlidingDeadline]:
    """Принимает уже созданную ячейку без потери её исходного дедлайна."""
    if isinstance(window, SlidingDeadline):
        slide, window = window, None
    return window, slide
@final
class _HeaderWait:
    def __init__( self, conn: http.client.HTTPConnection, sink: PrecommitSink,
        slide: SlidingDeadline, ) -> None:
        self.conn: http.client.HTTPConnection = conn
        self.sock: socket.socket | None = conn.sock
        self.sink: PrecommitSink = sink
        self.slide: SlidingDeadline = slide
        self.end_s: float = sink.started_s + sink.config.safety_cap_s
        self.ready: threading.Event = threading.Event()
        self.abandoned: bool = False
        self.result: list[http.client.HTTPResponse | BaseException] = []
        self.worker: threading.Thread = threading.Thread(
            target=self._read, daemon=True, name="passthrough-headers" )
    def _read(self) -> None:
        try:
            self.result.append(self.conn.getresponse())
            if self.abandoned:
                cast(http.client.HTTPResponse, self.result[0]).close()
        except BaseException as exc:
            self.result.append(exc)
        finally:
            self.ready.set()
    def is_set(self) -> bool:
        return any( ( self.ready.is_set(), self.sink.client_gone(),
                time.monotonic() >= min(self.slide.deadline_s, self.end_s), ) )
    def wait(self, timeout: float) -> object:
        return self.ready.wait(timeout)
    def receive(self, join_s: float) -> http.client.HTTPResponse:
        self.worker.start()
        received = False
        try:
            elapsed = time.monotonic() - self.sink.started_s
            self.sink.coordinator.await_headers_or_flush( self,
                flush_after_s=max(0.0, self.sink.config.passthrough_flush_s - elapsed),
            )
            if not self.ready.is_set():
                raise_error(
                    (TimeoutError, self.sink.gone_error)[self.sink.client_gone()]() )
            result = self.result[0]
            if isinstance(result, BaseException):
                raise_error(result)
            received = True
            return result
        finally:
            if not received:
                self._abort()
            self.worker.join(timeout=join_s)
            if not received:
                for result in self.result:
                    if isinstance(result, http.client.HTTPResponse):
                        result.close()
    def _abort(self) -> None:
        self.abandoned = True
        try:
            cast(socket.socket, self.sock).shutdown(socket.SHUT_RDWR)
        except (AttributeError, OSError):
            pass
        self.conn.close()
def _validate(adapter: Any, sink: PrecommitSink) -> None:
    if sink.config.flag_enabled("midstream_retry_enabled"):
        config = replace( sink.config, midstream_retry_enabled=True,
            idle_timeout_s=adapter.limits.idle_timeout_s,
            passthrough_read_timeout_s=adapter.limits.read_timeout_s, )
        try:
            validate_cross_hop_timeouts(
                cast(CrossHopConfig, cast(object, config)), hop="passthrough" )
        except ValueError as exc:
            raise_error(OSError(redact_diagnostic_text(str(exc))))
def open_response( adapter: Any, sink: PrecommitSink, slide: SlidingDeadline,
    transport: tuple[str, bytes, Mapping[str, str]], controls: tuple[
        float, Callable[[socket.socket], None], Callable[[bool], None], bool ],
) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
    """Сохраняет контракт открытия, таймаут сокета и закрытие при любом отказе."""
    _validate(adapter, sink)
    path, body, headers = transport
    deadline, on_socket, on_pooling, internal = controls
    conn = cast( http.client.HTTPConnection, adapter._open( path, body, headers,
            deadline=deadline, on_socket=on_socket,
            presend_deadline=getattr(sink, "presend_deadline", None),
            on_pooling=on_pooling, ), )
    try:
        if sink.client_gone():
            raise_error(adapter._client_gone_exc())
        response = sink.read_response(conn, slide, adapter.limits.reader_join_timeout_s)
    except BaseException:
        conn.close()
        raise
    slide.relax_socket(conn.sock, adapter.limits.read_timeout_s, internal)
    return conn, response
