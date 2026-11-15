"""Одна физическая попытка passthrough с единственным владельцем cleanup."""

# Legacy-порт адаптера и JSON-поля намеренно Any, без обратного импорта адаптера.
# pyright: reportAny=false, reportExplicitAny=false
from __future__ import annotations

import http.client
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Any, NotRequired, Protocol, TypedDict

from core.backend_adapter import PreSendTransientError
from core.liveness_signals import LivenessWindow
from core.nonstream_aggregator import request_deadlines
from core.passthrough_sliding_window import (
    FLAG_PASSTHROUGH_SLIDING_WINDOW,
)
from core.route_attempts import RouteRefusal
from core.runtime_env import flag_enabled


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

__all__ = ('ResponseSink', 'HandleRequestOptions', 'PassthroughRequest', 'RuntimeOptions', 'PassthroughRouteRefusal', '_pooling_enabled', '_response_reusable')
