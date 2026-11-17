"""Совместимые policy-порты без локального повтора отправленного POST."""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from http.client import HTTPConnection, HTTPResponse
from typing import Protocol

from core.passthrough_adapter_runtime import PassthroughRouteRefusal
from core.route_attempts import (
    DEFAULT_ROUTE_FAILOVER_STATUSES,
    evaluate_presend_candidate,
    failover_from_mapping,
    is_route_refusal_status,
)

RetryOpen = Callable[[], tuple[HTTPConnection, HTTPResponse]]
# 4-й элемент — уже прочитанное тело кандидата (`None`: тело не читалось и
# терминальный ответ отдаёт обычный response-путь). Тело никогда не вешается
# атрибутом на системный `HTTPResponse`.
PresendResult = tuple[HTTPConnection, HTTPResponse, bool, bytes | None]


class PresendAdapter(Protocol):
    """Порты адаптера, нужные для передачи отказа владельцу попытки."""

    def _client_gone_exc(self) -> Exception: ...

    def _read_presend_body(self, resp: HTTPResponse) -> bytes: ...

    def _response_headers(self, resp: HTTPResponse) -> Sequence[tuple[str, str]]: ...


class PresendSink(Protocol):
    """Неблокирующий порт отмены ответа клиентом."""

    def client_gone(self) -> bool: ...


ENV_PRESEND_MAX_RETRIES = "BRIDGE_PASSTHROUGH_PRESEND_MAX_RETRIES"
ENV_PRESEND_RETRY_DELAY_S = "BRIDGE_PASSTHROUGH_PRESEND_RETRY_DELAY_S"
ENV_PRESEND_RETRY_MAX_DELAY_S = "BRIDGE_PASSTHROUGH_PRESEND_RETRY_MAX_DELAY_S"
ENV_PRESEND_MIN_REMAINING_S = "BRIDGE_PASSTHROUGH_PRESEND_MIN_REMAINING_S"

DEFAULT_PRESEND_MAX_RETRIES = 2
DEFAULT_PRESEND_RETRY_DELAY_S = 2.2
DEFAULT_PRESEND_RETRY_MAX_DELAY_S = 8.0
DEFAULT_PRESEND_MIN_REMAINING_S = 0.5


def _positive_float(environ: Mapping[str, str], name: str, default: float) -> float:
    try:
        value = float(str(environ.get(name, "")).strip())
    except ValueError:
        return default
    return value if math.isfinite(value) and value > 0 else default


def _safe_refusal(status: int) -> bool:
    """Распознаёт разрешённый HTTP-отказ, но не выдаёт право локального replay.

    Отсутствие commit проверяет владелец попытки. Произвольный proxy payload
    не доказывает, что POST не исполнялся, и не может разрешить повтор 502.
    """
    return status in DEFAULT_ROUTE_FAILOVER_STATUSES


def is_retryable_presend_payload(
    status: int, headers: Sequence[tuple[str, str]], body: bytes,
    *, extra_statuses: Iterable[int] = (), extra_error_types: Iterable[str] = (),
    message_markers: Iterable[str] = (),
) -> bool:
    """Совместимый классификатор: payload не доказывает отсутствие исполнения.

    Per-route `extra_*`/`message_markers` расширяют множество отказов слота
    (например, 403 `permission_error` и 402 у OpenCode Go); без них семантика прежняя.
    """
    return is_route_refusal_status(
        status, body, extra_statuses=extra_statuses,
        extra_error_types=extra_error_types, message_markers=message_markers,
    )


def compute_presend_retry_delay(
    headers: Sequence[tuple[str, str]],
    attempt: int,
    environ: Mapping[str, str] | None = None,
) -> float:
    """Вычисляет ограниченную экспоненциальную задержку повтора."""
    env = os.environ if environ is None else environ
    base_delay = _positive_float(
        env, ENV_PRESEND_RETRY_DELAY_S, DEFAULT_PRESEND_RETRY_DELAY_S
    )
    max_delay = _positive_float(
        env, ENV_PRESEND_RETRY_MAX_DELAY_S, DEFAULT_PRESEND_RETRY_MAX_DELAY_S
    )
    retry_after = 0.0
    for name, value in headers:
        if name.lower() != "retry-after":
            continue
        try:
            parsed = float(value.strip())
        except ValueError:
            continue
        if math.isfinite(parsed) and parsed > 0:
            retry_after = parsed
            break
    delay = max(retry_after, base_delay)
    return min(max_delay, delay * (2 ** max(0, attempt)))


def _resolve_response(
    adapter: PresendAdapter,
    conn: HTTPConnection,
    resp: HTTPResponse,
    sink: PresendSink,
) -> PresendResult:
    """Передаёт отказ общему runner без собственного replay.

    Отсутствие commit обеспечивает caller. Терминальные ответы
    остаются непрочитанными, чтобы обычный response-путь передал их дословно.
    """
    failover = failover_from_mapping(getattr(adapter, "config", None))
    if resp.status not in failover.effective_statuses():
        return conn, resp, False, None
    if not getattr(sink, "accepts_presend_errors", False):
        return conn, resp, False, None
    if sink.client_gone():
        raise adapter._client_gone_exc()
    evaluation = evaluate_presend_candidate(
        resp.status, lambda: adapter._read_presend_body(resp), failover,
    )
    body = evaluation.body or b""
    if not evaluation.is_refusal:
        # Тело уже прочитано: вернуть явно вызывающему, ответ не отказ слота.
        return conn, resp, False, evaluation.body
    headers = tuple(adapter._response_headers(resp)) + (
        ("Content-Length", str(len(body))),
    )
    raise PassthroughRouteRefusal(resp.status, headers, body)


# Callback сохранён только для совместимости прежних positional/keyword вызовов.
def resolve_presend_response(adapter: PresendAdapter, conn: HTTPConnection, resp: HTTPResponse,
                             sink: PresendSink, retry_open_fn: RetryOpen) -> PresendResult:
    return _resolve_response(adapter, conn, resp, sink)
