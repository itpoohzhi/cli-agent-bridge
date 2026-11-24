"""Одна физическая попытка passthrough с единственным владельцем cleanup."""

# Legacy-порт адаптера и JSON-поля намеренно Any, без обратного импорта адаптера.
# pyright: reportAny=false, reportExplicitAny=false
from __future__ import annotations

import http.client
import os
import re
import socket
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from functools import partial
from typing import Any, NotRequired, Protocol, TypedDict, cast, final

from core import defaults as D, passthrough_precommit
from core.backend_adapter import PreSendTransientError
from core.liveness_signals import LivenessWindow, passthrough_window
from core.nonstream_aggregator import internal_stream_body, request_deadlines
from core.passthrough_sliding_window import FLAG_PASSTHROUGH_SLIDING_WINDOW, open_sliding_deadline
from core.passthrough_stream_options import (
    BoundedNegativeCache, model_scope_hash, prepare_stream_usage_body,
    should_retry_stream_options, strip_stream_options,
)
from core.route_attempts import RouteRefusal, evaluate_presend_candidate, failover_from_mapping
from core.runtime_env import flag_enabled
from core.slot_acquire import acquire_slot_cancellable
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
        PreSendTransientError.__init__(self, "route_refused", status_code=status, response_headers=headers, response_body=body)


_FAIL_TOKEN_RE = re.compile(r"[A-Za-z0-9_.:@/-]{1,128}")


def _fail_token(value: Any) -> str:
    """Только короткий идентификатор без разделителей строк допускается в fail-лог."""
    return value if isinstance(value, str) and _FAIL_TOKEN_RE.fullmatch(value) else "-"


def fail_context(request: Mapping[str, Any] | None, headers: Mapping[str, str] | None, host: Any = None) -> tuple[str, str]:
    """Безопасные (model, request_id) для `passthrough fail`: заголовок, extra_body, тело."""
    header_name = getattr(host, "REQUEST_ID_HEADER", None)
    if not isinstance(header_name, str) or not header_name:
        header_name = "X-Request-Id"
    request_map = request if isinstance(request, Mapping) else {}
    lowered = {str(key).lower(): value for key, value in headers.items()} if isinstance(headers, Mapping) else {}
    request_id: Any = lowered.get(header_name.lower())
    extra = request_map.get("extra_body")
    if request_id is None and isinstance(extra, Mapping):
        request_id = extra.get("request_id")
    if request_id is None:
        request_id = request_map.get("request_id")
    return _fail_token(request_map.get("model")), _fail_token(request_id)


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
        supports_fn = getattr(adapter, "_supports_stream_options", None)
        supports = bool(supports_fn(exchange.path, exchange.request)) if callable(supports_fn) else True
        internal = internal_stream_body(exchange.path, exchange.request, raw, supports_stream_options=supports)
        self.internal = internal is not None
        cache = getattr(adapter, "_stream_opt_neg_cache", None)
        if cache is None:
            cache = BoundedNegativeCache(ttl_s=D.BRIDGE_PASSTHROUGH_STREAM_OPTIONS_NEG_TTL_S, max_entries=D.BRIDGE_PASSTHROUGH_STREAM_OPTIONS_NEG_CACHE_MAX)
            setattr(adapter, "_stream_opt_neg_cache", cache)
        self._stream_opt_cache = cache
        self._stream_opt_key = (str(getattr(adapter, "id", "")), str(getattr(adapter, "_port", "")), model_scope_hash(exchange.request.get("model")), str(exchange.path))
        window = exchange.window
        if internal is not None:
            window = window or passthrough_window(adapter.limits, exchange.path, exchange.request)
            raw, self._stream_options_injected = internal, False
        else:
            enabled = flag_enabled("BRIDGE_PASSTHROUGH_STREAM_USAGE_ENABLED") if os.getenv("BRIDGE_PASSTHROUGH_STREAM_USAGE_ENABLED") is not None else D.BRIDGE_PASSTHROUGH_STREAM_USAGE_ENABLED
            raw, self._stream_options_injected = prepare_stream_usage_body(
                exchange.path, exchange.request, raw, enabled=enabled,
                supports=supports, negative_hit=cache.is_rejected(self._stream_opt_key, time.monotonic()),
            )
        self.affinity_info: dict[str, str] = {}
        self.computed_upstream_headers = adapter._upstream_headers(raw, exchange.headers, affinity_out=self.affinity_info)
        self.deadline, self.open_deadline = options.deadlines_fn(adapter.limits, self.internal)
        self.slide = open_sliding_deadline(self.deadline, adapter.limits, self.internal, exchange.request, options.sliding_enabled)
        window, self.slide = passthrough_precommit.request_window(window, self.slide)
        self.exchange = replace(exchange, raw_body=raw, window=window)
        self.connection: http.client.HTTPConnection | None = None
        self.response: http.client.HTTPResponse | None = None
        self.successful, self.pooling = False, False
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
        while not self._stop.wait(min(self.adapter.limits.poll_interval_s, max(0.0, self.slide.deadline_s - time.monotonic()))):
            if time.monotonic() >= self.slide.deadline_s or self.exchange.sink.client_gone():
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
            self.connection, self.response = passthrough_precommit.open_response(
                adapter, cast(passthrough_precommit.PrecommitSink, request.sink), self.slide,
                (request.path, request.raw_body, request.headers, self.computed_upstream_headers),
                (self.open_deadline, self._on_socket, self._on_pooling, self.internal),
            )
            self._check()
        except PreSendTransientError as error:
            if getattr(request.sink, "accepts_presend_errors", False):
                raise
            model, request_id = fail_context(request.request, request.headers, adapter.host)
            adapter._fail_io(request.sink, error.status_code == 504 or isinstance(error.__cause__, TimeoutError), model=model, request_id=request_id)
            return False
        except (OSError, http.client.HTTPException) as error:
            model, request_id = fail_context(request.request, request.headers, adapter.host)
            adapter._fail_io(request.sink, self._is_timeout_error(error), model=model, request_id=request_id)
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
        self.connection = cast(http.client.HTTPConnection, adapter._open(
            request.path, request.raw_body, request.headers, deadline=self.open_deadline,
            on_socket=self._on_socket, presend_deadline=getattr(request.sink, "presend_deadline", None),
            on_pooling=self._on_pooling, fresh=True, upstream_headers=self.computed_upstream_headers,
        ))
        self.response = cast(passthrough_precommit.PrecommitSink, request.sink).read_response(self.connection, self.slide, adapter.limits.reader_join_timeout_s)
        self.slide.relax_socket(self.connection.sock, adapter.limits.read_timeout_s, self.internal)
        self._check()
        return self.response

    def _handle_stream_options_400(self, response: http.client.HTTPResponse) -> tuple[http.client.HTTPResponse, bool]:
        body_400 = self.adapter._read_presend_body(response)
        if should_retry_stream_options(status_code=400, body=body_400, committed_to_client=False, injected_by_hub=True, attempt_index=0):
            self._stream_opt_cache.mark_rejected(self._stream_opt_key, time.monotonic())
            self._stream_options_injected = False
            self.exchange = replace(self.exchange, raw_body=strip_stream_options(self.exchange.raw_body))
            return self._reopen_response(), False
        self.successful = self.adapter._emit_response(response, self.exchange.sink, (body_400, False))
        return response, True

    def respond(self) -> None:
        """Разрешает прежний nonstream retry только вне транспортного роутинга."""
        response, request, adapter = self.response, self.exchange, self.adapter
        if response is None:
            raise RuntimeError("missing_upstream_response")
        if response.status == 400 and self._stream_options_injected:
            response, emitted = self._handle_stream_options_400(response)
            if emitted:
                return
            request = self.exchange
        failover = failover_from_mapping(getattr(adapter, "config", None))
        if not 200 <= response.status < 300 and getattr(request.sink, "accepts_presend_errors", False):
            evaluation = evaluate_presend_candidate(response.status, lambda: adapter._read_presend_body(response), failover)
            if evaluation.body is not None:
                body = evaluation.body
                headers = tuple(adapter._response_headers(response)) + (("Content-Length", str(len(body))),)
                self._check()
                if evaluation.is_refusal:
                    raise PassthroughRouteRefusal(response.status, headers, body)
                # Кандидат по статусу, но не отказ слота (например, запрет модели):
                # тело уже прочитано, поэтому ответ отдаётся дословно здесь.
                self.successful = adapter._emit_response(response, request.sink, (body, False))
                return
        reopen = self._reopen_response if self.internal and not getattr(request.sink, "accepts_presend_errors", False) and not flag_enabled("BRIDGE_TRANSPORT_ROUTING_ENABLED") else None
        self.successful = adapter._respond(
            response, request.request, request.sink, self.deadline, on_timeout=self.abort,
            window=request.window, slide=self.slide, headers=request.headers,
            affinity_uuid=self.affinity_info.get("affinity_uuid"),
            affinity_scope=self.affinity_info.get("affinity_scope"), reopen=reopen,
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
                adapter._pool.release_connection(adapter._host, adapter._port, connection, can_reuse=self._can_reuse())


def handle_request(
    adapter: Any, exchange: PassthroughRequest, options: RuntimeOptions | None = None
) -> None:
    """Исполняет один POST и освобождает слот даже при исключении cleanup."""
    if not credential_ready(adapter.config):
        model, request_id = fail_context(exchange.request, exchange.headers, adapter.host)
        adapter._fail(exchange.sink, 503, "route_unavailable", "upstream credential unavailable", model=model, request_id=request_id)
        return
    settings = options or RuntimeOptions()
    runtime = _RequestRuntime(adapter, exchange, settings)
    queue_default = float(getattr(adapter.host, "QUEUE_TIMEOUT_S", settings.queue_timeout_s))
    timeout_s = max(0.0, min(queue_default, runtime.open_deadline - time.monotonic()))
    status = acquire_slot_cancellable(adapter._slots, timeout_s, exchange.sink.client_gone)
    if status != "ok":
        if status == "timeout":
            model, req_id = fail_context(exchange.request, exchange.headers, adapter.host)
            adapter._fail(exchange.sink, 503, "overloaded", "passthrough backend is saturated", model=model, request_id=req_id)
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
