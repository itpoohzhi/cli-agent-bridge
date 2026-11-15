"""Одна физическая попытка passthrough с единственным владельцем cleanup."""

# Legacy-порт адаптера и JSON-поля намеренно Any, без обратного импорта адаптера.
# pyright: reportAny=false, reportExplicitAny=false
from __future__ import annotations

import http.client
import os
import socket
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from functools import partial
from typing import Any, NotRequired, Protocol, TypedDict, final

from core.backend_adapter import PreSendTransientError
from core.liveness_signals import LivenessWindow, passthrough_window
from core.nonstream_aggregator import internal_stream_body, request_deadlines
from core.passthrough_sliding_window import (
    FLAG_PASSTHROUGH_SLIDING_WINDOW,
    open_sliding_deadline,
)
from core.route_attempts import DEFAULT_ROUTE_FAILOVER_STATUSES, RouteRefusal
from core.runtime_env import flag_enabled
from core.transport_credentials import credential_ready


class ResponseSink(Protocol):
    """Структурный порт ответа, не зависящий от реализации адаптера."""

    def client_gone(self) -> bool: ...


class HandleRequestOptions(TypedDict):
    """Прежние keyword-аргументы handle; неизвестные ключи отклоняет DTO."""
    path: str
    raw_body: bytes
    request: Mapping[str, Any]
    headers: Mapping[str, str]
    sink: ResponseSink
    window: NotRequired[LivenessWindow | None]


@dataclass(frozen=True, slots=True, kw_only=True)
class PassthroughRequest:
    """Вход одной попытки, без копирования тела или изменения caller request."""
    path: str
    raw_body: bytes
    request: Mapping[str, Any]
    headers: Mapping[str, str]
    sink: ResponseSink
    window: LivenessWindow | None = None


@dataclass(frozen=True, slots=True)
class RuntimeOptions:
    """Порты прежних настроек, включая живую функцию флага фасада."""
    queue_timeout_s: float = 900.0
    sliding_enabled: Callable[[], bool] = partial(flag_enabled, FLAG_PASSTHROUGH_SLIDING_WINDOW)
    deadlines_fn: Callable[..., tuple[float, float]] = request_deadlines


# Оба catch-контракта обязательны; поля отказа задаёт только PreSendTransientError.
class PassthroughRouteRefusal(RouteRefusal, PreSendTransientError):  # pyright: ignore[reportUnsafeMultipleInheritance]
    """Отдельный HTTP-отказ с совместимостью старого catch PreSendTransientError."""

    def __init__(self, status: int, headers: tuple[tuple[str, str], ...], body: bytes) -> None:
        PreSendTransientError.__init__(
            self, "route_refused", status_code=status,
            response_headers=headers, response_body=body,
        )


def _pooling_enabled() -> bool:
    value = os.environ.get("BRIDGE_CONNECTION_POOLING_ENABLED", "1")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _response_reusable(response: http.client.HTTPResponse) -> bool:
    """Проверяет завершённость ответа и ограничения keepalive на уровне HTTP."""
    if not response.isclosed() or response.will_close:
        return False
    content_type = (response.getheader("Content-Type") or "").lower()
    unbounded = response.getheader("Content-Length") is None
    if "text/event-stream" in content_type and unbounded:
        return False
    tokens = (response.getheader("Connection") or "").lower().split(",")
    return "close" not in {token.strip() for token in tokens}


@final
class _RequestRuntime:
    """Владеет только сокетом текущей попытки и ограниченным watcher-потоком."""
    def __init__(self, adapter: Any, exchange: PassthroughRequest, options: RuntimeOptions) -> None:
        self.adapter = adapter
        raw = adapter._with_body_defaults(exchange.raw_body)
        internal = internal_stream_body(exchange.path, exchange.request, raw)
        self.internal = internal is not None
        window = exchange.window
        if self.internal:
            window = window or passthrough_window(adapter.limits, exchange.path, exchange.request)
        raw = internal if self.internal else raw
        self.exchange = replace(exchange, raw_body=raw, window=window)
        self.deadline, self.open_deadline = options.deadlines_fn(adapter.limits, self.internal)
        self.slide = open_sliding_deadline(
            self.deadline, adapter.limits, self.internal,
            exchange.request, options.sliding_enabled,
        )
        self.connection: http.client.HTTPConnection | None = None
        self.response: http.client.HTTPResponse | None = None
        self.successful = False
        self.pooling = False
        self._socket: socket.socket | None = None
        self._stop, self._aborted = threading.Event(), threading.Event()
        self._transport_lock = threading.Lock()
        self.watcher = threading.Thread(target=self._watch, daemon=True, name="passthrough-deadline")

    def abort(self) -> None:
        """Сбрасывает только принадлежащий запросу сокет, но не закрывает его."""
        with self._transport_lock:
            if self._stop.is_set():
                return
            self._aborted.set()
            if self._socket is not None:
                try:
                    self._socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    return

    def _watch(self) -> None:
        while not self._stop.wait(
            min(
                self.adapter.limits.poll_interval_s,
                max(0.0, self.slide.deadline_s - time.monotonic()),
            )
        ):
            expired = time.monotonic() >= self.slide.deadline_s
            if expired or self.exchange.sink.client_gone():
                self.abort()
                return

    def _on_socket(self, sock: socket.socket) -> None:
        with self._transport_lock:
            self._socket = sock
            self._check()

    def _on_pooling(self, enabled: bool) -> None:
        self.pooling = enabled

    def _check(self) -> None:
        if self.exchange.sink.client_gone():
            raise self.adapter._client_gone_exc()
        if self._aborted.is_set() or time.monotonic() >= self.slide.deadline_s:
            raise TimeoutError("upstream deadline exceeded")

    def open_response(self) -> bool:
        """Только connect-ошибка может выйти как PreSendTransientError."""
        request, adapter = self.exchange, self.adapter
        try:
            self._check()
            self.connection = adapter._open(
                request.path, request.raw_body, request.headers, deadline=self.open_deadline,
                on_socket=self._on_socket,
                presend_deadline=getattr(request.sink, "presend_deadline", None),
                on_pooling=self._on_pooling,
            )
            self._check()
            self.response = self.connection.getresponse()
            self.slide.relax_socket(self.connection.sock, adapter.limits.read_timeout_s, self.internal)
            self._check()
        except PreSendTransientError as error:
            if getattr(request.sink, "accepts_presend_errors", False):
                raise
            adapter._fail_io(
                request.sink,
                error.status_code == 504 or isinstance(error.__cause__, TimeoutError),
            )
            return False
        except (OSError, http.client.HTTPException) as error:
            adapter._fail_io(request.sink, self._is_timeout_error(error))
            return False
        return True

    def _is_timeout_error(self, error: BaseException) -> bool:
        return bool(
            isinstance(error, TimeoutError)
            or self._aborted.is_set()
            or time.monotonic() >= self.slide.deadline_s
            or (self.exchange.window is not None and self.exchange.window.expired())
        )

    def _reopen_response(self) -> http.client.HTTPResponse:
        request, adapter = self.exchange, self.adapter
        response, self.response = self.response, None
        connection, self.connection = self.connection, None
        try:
            if response is not None:
                response.close()
        finally:
            if connection is not None:
                connection.close()
        self._check()
        self.connection = adapter._open(
            request.path, request.raw_body, request.headers, deadline=self.open_deadline,
            on_socket=self._on_socket,
            presend_deadline=getattr(request.sink, "presend_deadline", None),
            on_pooling=self._on_pooling,
            fresh=True,
        )
        self.response = self.connection.getresponse()
        self.slide.relax_socket(self.connection.sock, adapter.limits.read_timeout_s, self.internal)
        self._check()
        return self.response

    def respond(self) -> None:
        """Разрешает прежний nonstream retry только вне транспортного роутинга."""
        response, request, adapter = self.response, self.exchange, self.adapter
        if response is None:
            raise RuntimeError("missing_upstream_response")
        if response.status in DEFAULT_ROUTE_FAILOVER_STATUSES and getattr(
            request.sink, "accepts_presend_errors", False
        ):
            body = adapter._read_presend_body(response)
            headers = tuple(adapter._response_headers(response)) + (("Content-Length", str(len(body))),)
            self._check()
            raise PassthroughRouteRefusal(response.status, headers, body)
        self.successful = adapter._respond(
            response, request.request, request.sink, self.deadline,
            on_timeout=self.abort,
            window=request.window,
            slide=self.slide,
            headers=request.headers,
            reopen=(
                self._reopen_response
                if self.internal
                and not getattr(request.sink, "accepts_presend_errors", False)
                and not flag_enabled("BRIDGE_TRANSPORT_ROUTING_ENABLED")
                else None
            ),
        )

    def _can_reuse(self) -> bool:
        response = self.response
        if not all((_pooling_enabled(), self.pooling, self.successful)):
            return False
        if self._aborted.is_set() or response is None:
            return False
        return _response_reusable(response)

    def close(self) -> None:
        """Останавливает watcher до передачи сокета следующему владельцу."""
        with self._transport_lock:
            self._stop.set()
            self._socket = None
        try:
            if self.watcher.ident is not None:
                self.watcher.join(timeout=self.adapter.limits.reader_join_timeout_s)
        finally:
            connection, self.connection = self.connection, None
            if connection is not None:
                adapter = self.adapter
                reuse = self._can_reuse()
                adapter._pool.release_connection(
                    adapter._host, adapter._port, connection, can_reuse=reuse
                )


def handle_request(
    adapter: Any, exchange: PassthroughRequest, options: RuntimeOptions | None = None
) -> None:
    """Исполняет один POST и освобождает слот даже при исключении cleanup."""
    if not credential_ready(adapter.config):
        adapter._fail(exchange.sink, 503, "route_unavailable", "upstream credential unavailable")
        return
    settings = options or RuntimeOptions()
    runtime = _RequestRuntime(adapter, exchange, settings)
    queue_default = float(getattr(adapter.host, "QUEUE_TIMEOUT_S", settings.queue_timeout_s))
    remaining = runtime.open_deadline - time.monotonic()
    if not adapter._slots.acquire(timeout=max(0.0, min(queue_default, remaining))):
        adapter._fail(exchange.sink, 503, "overloaded", "passthrough backend is saturated")
        return
    with adapter._lock:
        adapter._active += 1
    try:
        runtime.watcher.start()
        try:
            if runtime.open_response():
                runtime.respond()
        except Exception as error:
            if not isinstance(error, type(adapter._client_gone_exc())):
                raise
            runtime.abort()
    finally:
        try:
            runtime.close()
        finally:
            with adapter._lock:
                adapter._active -= 1
            adapter._slots.release()
