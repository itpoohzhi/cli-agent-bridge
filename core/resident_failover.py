"""Прекоммит-отказ резидентных CLI-ходов: чистые предикаты и тонкие хелперы без привязки к вендору."""

from __future__ import annotations

import json
import os
import re
import zlib
from collections.abc import Callable, Mapping
from typing import Final, Protocol

from core.route_attempts import RouteRefusal
from core.runtime_env import env_bool
from core.stdio_resident.sse_error_bridge import sanitize_log_text
from core.stdio_resident.turn_error_sse import ResidentTurnError

_JSON_HEADERS: tuple[tuple[str, str], ...] = (("Content-Type", "application/json"),)
PRECOMMIT_CODE_LOG_ENV: Final[str] = "BRIDGE_RESIDENT_PRECOMMIT_CODE_LOG_ENABLED"
SINGLE_ROUTE_KEEPALIVE_ENV: Final[str] = "BRIDGE_RESIDENT_SINGLE_ROUTE_KEEPALIVE_ENABLED"
DRAIN_REFUSAL_ENV: Final[str] = "BRIDGE_RESIDENT_DRAIN_REFUSAL_ENABLED"
_DRAIN_BODY: Final[bytes] = b'{"error":{"type":"service_unavailable","code":"bridge_draining","message":"bridge is draining"}}'
_SAFE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]{1,64}$")


class _FailureLease(Protocol):
    def record_failure(self, exc: BaseException) -> None: ...


class _JsonHandler(Protocol):
    def _send(self, code: int, payload: dict[str, object], /) -> None: ...


def is_precommit(handler: object, live_sent: int = 0) -> bool:
    """True только если попытка routed, заголовки не ушли, live_sent == 0 и нет commit."""
    if type(live_sent) is not int or live_sent != 0:
        return False
    attempt: object = getattr(handler, "_transport_attempt", None)
    if attempt is None:
        return False
    if bool(getattr(handler, "_headers_already_sent", False)):
        return False
    state: object = getattr(attempt, "state", None)
    return not bool(getattr(state, "committed", False))


def cli_resident_refusal(exc: ResidentTurnError) -> RouteRefusal:
    """Преобразует ResidentTurnError в RouteRefusal для роутера попыток."""
    raw_status: object = getattr(exc, "status", 502)
    status_code = (
        int(raw_status)
        if isinstance(raw_status, int)
        and not isinstance(raw_status, bool)
        and raw_status >= 400
        else 502
    )
    raw_body: object = exc.response.body
    if isinstance(raw_body, bytes):
        response_body = raw_body
    elif isinstance(raw_body, str):
        response_body = raw_body.encode("utf-8")
    else:
        response_body = json.dumps(
            raw_body, ensure_ascii=False, default=str
        ).encode("utf-8")
    return RouteRefusal(
        status_code=status_code,
        response_headers=_JSON_HEADERS,
        response_body=response_body,
    )


def _is_single_route(ctx: Mapping[str, object]) -> bool:
    routes = ctx.get("routes")
    if isinstance(routes, (list, tuple, set, frozenset)):
        return len(routes) == 1
    return ctx.get("route_count") == 1


def should_defer_sse_headers(
    handler: object, ctx: Mapping[str, object], *, environ: Mapping[str, str] | None = None
) -> bool:
    """Откладывает SSE-заголовки только для свежей pre-commit routed CLI-попытки."""
    if bool(ctx.get("attached_existing")):
        return False
    if not is_precommit(handler, live_sent=0):
        return False
    env = os.environ if environ is None else environ
    if _is_single_route(ctx) and env_bool(env, (SINGLE_ROUTE_KEEPALIVE_ENV,), False):
        return False
    return True


def check_precommit_drain_refusal(
    *, draining: bool = False, request_id: str | None = None, environ: Mapping[str, str] | None = None
) -> None:
    """Inert D4 drain DI: emits 503 bridge_draining + deterministic Retry-After >= 1 only when draining and flag enabled."""
    if not draining:
        return
    env = os.environ if environ is None else environ
    if not env_bool(env, (DRAIN_REFUSAL_ENV,), False):
        return
    retry_after = 1 + (zlib.crc32((request_id or "").encode("utf-8")) % 5)
    raise RouteRefusal(
        status_code=503,
        response_headers=(*_JSON_HEADERS, ("Retry-After", str(retry_after))),
        response_body=_DRAIN_BODY,
    )


def _log_precommit_refusal(
    exc: ResidentTurnError,
    log_fn: Callable[[str], None] | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> None:
    if log_fn is None or not env_bool(os.environ if environ is None else environ, (PRECOMMIT_CODE_LOG_ENV,), True):
        return
    raw_code = exc.response.code or ""
    safe_code = raw_code if _SAFE_CODE_RE.fullmatch(raw_code) else "unknown"
    log_fn(f"resident_precommit_refusal status={exc.status} code={safe_code}")


def handle_json_resident_error(
    handler: _JsonHandler,
    lease: _FailureLease,
    exc: ResidentTurnError,
    log_fn: Callable[[str], None],
) -> None:
    """Pre-commit отдаёт RouteRefusal роутеру; post-commit логирует и отвечает клиенту."""
    if is_precommit(handler, live_sent=0):
        _log_precommit_refusal(exc, log_fn)
        lease.record_failure(exc)
        raise cli_resident_refusal(exc) from exc
    safe_err = sanitize_log_text(exc.response.message, extra_code=exc.response.code)
    log_fn(
        f"json_resident_error status={exc.status} code={exc.response.code} err={safe_err!r}"
    )
    lease.record_failure(exc)
    handler._send(exc.status, exc.response.body)  # pyright: ignore[reportPrivateUsage]


def maybe_raise_sse_precommit_refusal(
    handler: object,
    lease: _FailureLease,
    exc: BaseException,
    live_sent: int,
    log_fn: Callable[[str], None] | None = None,
) -> None:
    """Бросает RouteRefusal для pre-commit ResidentTurnError в SSE; иначе возвращает None."""
    if isinstance(exc, ResidentTurnError) and is_precommit(
        handler, live_sent=live_sent
    ):
        _log_precommit_refusal(exc, log_fn)
        lease.record_failure(exc)
        raise cli_resident_refusal(exc) from exc
