"""Политика повторов явных HTTP-ошибок до отправки ответа клиенту."""

from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from core.backend_adapter import PreSendTransientError

ENV_PRESEND_MAX_RETRIES = "BRIDGE_PASSTHROUGH_PRESEND_MAX_RETRIES"
ENV_PRESEND_RETRY_DELAY_S = "BRIDGE_PASSTHROUGH_PRESEND_RETRY_DELAY_S"
ENV_PRESEND_RETRY_MAX_DELAY_S = "BRIDGE_PASSTHROUGH_PRESEND_RETRY_MAX_DELAY_S"
ENV_PRESEND_MIN_REMAINING_S = "BRIDGE_PASSTHROUGH_PRESEND_MIN_REMAINING_S"

DEFAULT_PRESEND_MAX_RETRIES = 2
DEFAULT_PRESEND_RETRY_DELAY_S = 2.2
DEFAULT_PRESEND_RETRY_MAX_DELAY_S = 8.0
DEFAULT_PRESEND_MIN_REMAINING_S = 0.5
_RETRYABLE_TYPES = frozenset({"proxy_connect_failed", "proxy_unavailable"})


def _bounded_int(
    environ: Mapping[str, str], name: str, default: int, low: int, high: int
) -> int:
    try:
        value = int(str(environ.get(name, "")).strip())
    except ValueError:
        return default
    return value if low <= value <= high else default


def _positive_float(environ: Mapping[str, str], name: str, default: float) -> float:
    try:
        value = float(str(environ.get(name, "")).strip())
    except ValueError:
        return default
    return value if math.isfinite(value) and value > 0 else default


def is_retryable_presend_payload(
    status: int, headers: Sequence[tuple[str, str]], body: bytes
) -> bool:
    """Распознаёт только явно повторяемые proxy-ошибки 502/503."""
    _ = headers
    if status not in (502, 503) or not body:
        return False
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    nested = data.get("error")
    nested = nested if isinstance(nested, dict) else {}
    retryable = data.get("retryable")
    nested_retryable = nested.get("retryable")
    if retryable is False or nested_retryable is False:
        return False
    return (
        retryable is True
        or nested_retryable is True
        or data.get("type") in _RETRYABLE_TYPES
        or nested.get("type") in _RETRYABLE_TYPES
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


def _has_retry_budget(sink: Any, delay: float, environ: Mapping[str, str]) -> bool:
    deadline = getattr(sink, "presend_deadline", None)
    if not isinstance(deadline, (int, float)) or not math.isfinite(deadline):
        return True
    minimum = _positive_float(
        environ, ENV_PRESEND_MIN_REMAINING_S, DEFAULT_PRESEND_MIN_REMAINING_S
    )
    return deadline - time.monotonic() >= delay + minimum


def resolve_presend_response(
    adapter: Any,
    conn: Any,
    resp: Any,
    sink: Any,
    retry_open_fn: Callable[[], tuple[Any, Any]],
) -> tuple[Any, Any, bool]:
    """Повторяет явный proxy-отказ или отправляет уже прочитанный ответ."""
    if resp.status not in (502, 503):
        return conn, resp, False
    body = adapter._read_presend_body(resp)
    if getattr(sink, "accepts_presend_errors", False):
        headers = adapter._response_headers(resp)
        raise PreSendTransientError(
            "transient upstream HTTP status",
            status_code=resp.status,
            response_headers=tuple(headers + [("Content-Length", str(len(body)))]),
            response_body=body,
        )
    env = os.environ
    max_retries = _bounded_int(
        env, ENV_PRESEND_MAX_RETRIES, DEFAULT_PRESEND_MAX_RETRIES, 0, 10
    )
    for attempt in range(max_retries):
        if not is_retryable_presend_payload(resp.status, resp.getheaders(), body):
            break
        delay = compute_presend_retry_delay(resp.getheaders(), attempt, env)
        if sink.client_gone():
            raise adapter._client_gone_exc()
        if not _has_retry_budget(sink, delay, env):
            break
        try:
            conn.close()
        except Exception:
            pass
        time.sleep(delay)
        conn, resp = retry_open_fn()
        if resp.status not in (502, 503):
            return conn, resp, False
        body = adapter._read_presend_body(resp)
    out_headers = adapter._response_headers(resp) + [("Content-Length", str(len(body)))]
    sink.start(resp.status, out_headers)
    sink.write(body)
    return conn, resp, True
