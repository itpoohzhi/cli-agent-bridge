"""Одна физическая отправка POST: connect отделён от возможного исполнения."""

from __future__ import annotations

import http.client
import os
import socket
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from string import ascii_lowercase, digits
from typing import NotRequired, Protocol, TypedDict, Unpack
from urllib.parse import SplitResult, urlsplit

from core.backend_adapter import PreSendTransientError, _base_url_allowed
from core.passthrough_headers import outbound_headers
from core.subbridge_zero_canon import (
    REVIEW_PROFILE_HEADER, ZERO_CANON_PROFILE, normalize_review_profile,
    should_forward_review_profile,
)
from core.transport_credentials import credential_required, resolve_credential

_BASE_PATH_CHARS = frozenset(ascii_lowercase + digits + "/._-")
_INTERNAL_SUBAGENT: ContextVar[str] = ContextVar("internal_subagent", default="")
_INTERNAL_REVIEW_PROFILE: ContextVar[str] = ContextVar("internal_review_profile", default="")


@contextmanager
def internal_trace_scope(extra_headers: Iterable[tuple[str, str]]) -> Iterator[None]:
    """Изолирует внутреннюю атрибуцию (subagent-id и review-profile) на время вызова."""
    pairs = tuple(extra_headers)
    subagent_id = next((v for k, v in pairs if k.lower() == "x-subagent-id"), "")
    profile = next((v for k, v in pairs if k.lower() == "x-review-profile"), "")
    token = _INTERNAL_SUBAGENT.set(subagent_id)
    profile_token = _INTERNAL_REVIEW_PROFILE.set(profile)
    try:
        yield
    finally:
        _INTERNAL_REVIEW_PROFILE.reset(profile_token)
        _INTERNAL_SUBAGENT.reset(token)


class ExchangeLimits(Protocol):
    """Существующие настраиваемые таймауты, без нового владельца настроек."""

    connect_timeout_s: float
    read_timeout_s: float
    total_timeout_s: float


class ExchangePool(Protocol):
    """Выдаёт уже подключённый socket; ошибка выдачи закрывает свой socket."""

    def get_connection(
        self, host: str, port: int, timeout: float, *, fresh: bool = False,
    ) -> tuple[http.client.HTTPConnection, bool]: ...

    def close_all(self) -> None: ...


class ExchangeAdapter(Protocol):
    """Порт существующего адаптера; не импортирует конкретную реализацию."""

    config: Mapping[str, object]
    _host: str
    _port: int
    _base_path: str
    _pool: ExchangePool

    @property
    def limits(self) -> ExchangeLimits: ...

    def _upstream_headers(
        self, raw_body: bytes = b"", headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, str]: ...


class OpenRequestOptions(TypedDict, total=False):
    """Совместимые keyword-параметры прежнего _open."""

    deadline: float | None
    on_socket: Callable[[socket.socket], None] | None
    presend_deadline: float | None
    on_reuse: Callable[[bool], None] | None
    on_pooling: Callable[[bool], None] | None
    fresh: bool
    upstream_headers: NotRequired[Mapping[str, str] | None]


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenOptions:
    """Неизменяемые параметры одной отправки; unknown kwargs запрещены."""

    deadline: float | None = None
    on_socket: Callable[[socket.socket], None] | None = None
    presend_deadline: float | None = None
    on_reuse: Callable[[bool], None] | None = None
    on_pooling: Callable[[bool], None] | None = None
    fresh: bool = False
    upstream_headers: Mapping[str, str] | None = None


def _remaining(limits: ExchangeLimits, deadline: float | None) -> float:
    remaining = limits.total_timeout_s if deadline is None else deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("upstream total deadline exceeded")
    return remaining


def _connect_budget(limits: ExchangeLimits, options: OpenOptions) -> float:
    remaining = _remaining(limits, options.deadline)
    if options.presend_deadline is not None:
        remaining = min(remaining, options.presend_deadline - time.monotonic())
    if remaining <= 0:
        raise PreSendTransientError("upstream connect budget exhausted", status_code=504)
    return min(limits.connect_timeout_s, remaining)


def _base_url_parts(base_url: str) -> SplitResult:
    parts = urlsplit(base_url)
    if parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("outbound_base_url_invalid")
    if any((parts.username is not None, parts.password is not None, parts.query, parts.fragment)):
        raise ValueError("outbound_base_url_invalid")
    if base_url != parts.geturl() or not _BASE_PATH_CHARS.issuperset(parts.path):
        raise ValueError("outbound_base_url_invalid")
    if any(segment in {".", ".."} for segment in parts.path.split("/")):
        raise ValueError("outbound_base_url_invalid")
    if not _base_url_allowed("", base_url, None):
        raise ValueError("outbound_base_url_denied")
    return parts


def _validate_endpoint(adapter: ExchangeAdapter) -> None:
    """Manifest не может сам разрешить remote egress или подменить endpoint."""
    base_url = adapter.config.get("base_url")
    if not isinstance(base_url, str):
        raise ValueError("outbound_base_url_invalid")
    parts = _base_url_parts(base_url)
    actual = (adapter._host, adapter._port, adapter._base_path)
    if actual != (parts.hostname, parts.port, parts.path.rstrip("/")):
        raise ValueError("outbound_endpoint_changed")


def _connect(
    adapter: ExchangeAdapter, options: OpenOptions, pooling: bool,
) -> tuple[http.client.HTTPConnection, bool]:
    timeout = _connect_budget(adapter.limits, options)
    connection = None
    try:
        connection, reused = adapter._pool.get_connection(
            adapter._host, adapter._port, timeout, fresh=options.fresh or not pooling,
        )
        # Запрещаем неявный connect внутри request, где ошибка уже неоднозначна.
        if connection.sock is None:
            connection.connect()
        return connection, reused
    except (OSError, http.client.HTTPException) as error:
        if connection is not None:
            connection.close()
        raise PreSendTransientError("upstream connect failed") from error
    except BaseException:
        if connection is not None:
            connection.close()
        raise


def _notify_connection(
    connection: http.client.HTTPConnection, options: OpenOptions,
    pooling: bool, reused: bool,
) -> None:
    if options.on_pooling is not None:
        options.on_pooling(pooling)
    if options.on_reuse is not None:
        options.on_reuse(reused)
    if connection.sock is not None and options.on_socket is not None:
        options.on_socket(connection.sock)


def _route_credential(config: Mapping[str, object]) -> str:
    credential = resolve_credential(config)
    if credential_required(config) and not credential:
        raise ValueError("outbound_credential_unavailable")
    return credential


def _scoped_review_profile(client: Mapping[str, str]) -> str:
    """Профиль из внутреннего scope, иначе из клиентских заголовков (retry/failover)."""
    raw = _INTERNAL_REVIEW_PROFILE.get() or next(
        (v for k, v in client.items() if k.lower() == "x-review-profile"), "",
    )
    return normalize_review_profile(raw)


def _wire_headers(
    adapter: ExchangeAdapter,
    headers: Mapping[str, str],
    size: int,
    pooling: bool,
    upstream_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    configured = (
        adapter._upstream_headers()
        if upstream_headers is None
        else upstream_headers
    )
    credential = _route_credential(adapter.config)
    forwarded = outbound_headers(headers, configured, credential)
    if upstream_headers:
        replaced = {name.lower() for name in upstream_headers}
        forwarded = {k: v for k, v in forwarded.items() if k.lower() not in replaced}
        forwarded.update(upstream_headers)
    subagent_id = _INTERNAL_SUBAGENT.get()
    trusted = should_forward_review_profile(
        adapter._base_path, str(adapter.config.get("trust_profile") or ""),
    )
    if subagent_id and trusted:
        forwarded["X-Subagent-Id"] = subagent_id
    if trusted and _scoped_review_profile(headers) == ZERO_CANON_PROFILE:
        forwarded[REVIEW_PROFILE_HEADER] = ZERO_CANON_PROFILE
    forwarded["Host"] = f"{adapter._host}:{adapter._port}"
    forwarded["Content-Length"] = str(size)
    forwarded["Accept-Encoding"] = "identity"
    forwarded["Connection"] = "keep-alive" if pooling else "close"
    return forwarded


def _target(adapter: ExchangeAdapter, path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("outbound_path_invalid")
    route, separator, query = path.partition("?")
    suffix = route[len("/v1"):] if route.startswith("/v1/") else route
    return adapter._base_path + suffix + (separator + query if separator else "")


def open_request(
    adapter: ExchangeAdapter, path: str, raw_body: bytes, headers: Mapping[str, str],
    **kwargs: Unpack[OpenRequestOptions],
) -> http.client.HTTPConnection:
    """Открывает соединение и отправляет ровно один POST без локального replay.

    Только ошибка connect оборачивается в PreSendTransientError. Любой сбой
    request, включая CannotSendRequest/partial write, остаётся terminal.
    Успешно возвращённое соединение закрывает или возвращает в пул вызывающий.
    """
    options = OpenOptions(**kwargs)
    _validate_endpoint(adapter)
    target = _target(adapter, path)
    _route_credential(adapter.config)
    pooling = os.environ.get("BRIDGE_CONNECTION_POOLING_ENABLED", "1").strip().lower()
    enabled = pooling in {"1", "true", "yes", "on"}
    if not enabled:
        adapter._pool.close_all()
    connection, reused = _connect(adapter, options, enabled)
    try:
        _notify_connection(connection, options, enabled, reused)
        # Credential и config читаются заново после connect, непосредственно до send.
        _validate_endpoint(adapter)
        upstream_headers = options.upstream_headers
        if upstream_headers is None:
            upstream_headers = adapter._upstream_headers(raw_body, headers)
        forwarded = _wire_headers(
            adapter, headers, len(raw_body), enabled, upstream_headers=upstream_headers,
        )
        remaining = _remaining(adapter.limits, options.deadline)
        if connection.sock is not None:
            connection.sock.settimeout(min(adapter.limits.read_timeout_s, remaining))
        connection.auto_open = 0
        connection.request("POST", target, body=raw_body, headers=forwarded)
    except BaseException:
        connection.close()
        raise
    return connection
