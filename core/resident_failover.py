"""Прекоммит-отказ резидентных CLI-ходов: чистые предикаты и тонкие хелперы без привязки к вендору."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Protocol

from core.route_attempts import RouteRefusal
from core.stdio_resident.sse_error_bridge import sanitize_log_text
from core.stdio_resident.turn_error_sse import ResidentTurnError

_JSON_HEADERS: tuple[tuple[str, str], ...] = (("Content-Type", "application/json"),)


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


def should_defer_sse_headers(handler: object, ctx: Mapping[str, object]) -> bool:
    """Откладывает SSE-заголовки только для свежей pre-commit routed CLI-попытки."""
    if bool(ctx.get("attached_existing")):
        return False
    return is_precommit(handler, live_sent=0)


def handle_json_resident_error(
    handler: _JsonHandler,
    lease: _FailureLease,
    exc: ResidentTurnError,
    log_fn: Callable[[str], None],
) -> None:
    """Pre-commit отдаёт RouteRefusal роутеру; post-commit логирует и отвечает клиенту."""
    if is_precommit(handler, live_sent=0):
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
) -> None:
    """Бросает RouteRefusal для pre-commit ResidentTurnError в SSE; иначе возвращает None."""
    if isinstance(exc, ResidentTurnError) and is_precommit(
        handler, live_sent=live_sent
    ):
        lease.record_failure(exc)
        raise cli_resident_refusal(exc) from exc
