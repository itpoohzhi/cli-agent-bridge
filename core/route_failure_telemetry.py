"""Классификация отказов маршрута и строгая однократная финализация телеметрии.

Тёмный модуль: чистая логика без БД и сети. Телеметрия фиксируется O(1) через
методы handler (`_record_telemetry` кладёт событие в очередь), синхронного
DuckDB I/O на горячем пути нет. Врезка в монолиты выполняется отдельной волной.
"""

from __future__ import annotations

import contextlib
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.route_attempts import RouteFailover, RouteRefusal, build_pool_exhausted_error
from core.telemetry_hooks import known_model

ALLOWED_REFUSAL_STATUSES: frozenset[int] = frozenset({402, 408, 429, 502, 503, 504})
CLOSED_ERROR_TYPES: frozenset[str] = frozenset(
    {"all_routes_open", "RouteRefusal", "pool_exhausted", "route_unavailable"}
)
ALL_ROUTES_OPEN_BODY: bytes = b'{"error":{"type":"all_routes_open","code":"all_routes_open","message":"all routes are open or busy"}}'

_Refusals = list[tuple[str, RouteRefusal, RouteFailover]]


@dataclass(frozen=True)
class RouteFailureClassification:
    """Итоговая классификация: HTTP-статус, тип ошибки и нормализованная модель."""

    status_code: int
    error_type: str
    model: str | None


def _norm_model(model: object) -> str | None:
    """Непустая строка → known_model(); иначе None («unknown» тоже None)."""
    if isinstance(model, str) and model:
        return known_model(model)
    return None


def classify_route_failure(
    exc: BaseException | None, model: str | None = None
) -> RouteFailureClassification:
    """Классифицирует исключение строго через isinstance (без duck-typing по status_code)."""
    norm = _norm_model(model)
    if isinstance(exc, RouteRefusal):
        code = exc.status_code
        if type(code) is int and code in ALLOWED_REFUSAL_STATUSES:
            return RouteFailureClassification(code, "RouteRefusal", norm)
        return RouteFailureClassification(502, "RouteRefusal", norm)
    name = type(exc).__name__ if exc is not None else "UnknownError"
    return RouteFailureClassification(500, name, norm)


def _call(obj: Any, name: str, *args: Any, **kwargs: Any) -> Any:
    """Безопасный вызов опционального метода: нет метода или исключение → None."""
    fn = getattr(obj, name, None)
    if not callable(fn):
        return None
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def _exhausted_pool(
    refusals: _Refusals,
) -> tuple[str, list[tuple[str, RouteRefusal]]] | None:
    """Группа отказов одного объявленного пула (>=2 слотов) для сводного 429."""
    groups: dict[str, tuple[str, list[tuple[str, RouteRefusal]]]] = {}
    for slot, error, failover in refusals:
        if not failover.pool_key:
            continue
        groups.setdefault(failover.pool_key, (failover.label, []))[1].append(
            (slot, error)
        )
    for label, group in groups.values():
        if len({slot for slot, _ in group}) >= 2:
            return label, group
    return None


def _trace_fields(handler: Any) -> str:
    fields = _call(handler, "_trace_log_fields")
    return fields if isinstance(fields, str) else ""


def _record_failure(
    route: Any, status: int, error_type: str, nbytes: int, extra: str = ""
) -> None:
    """Фиксирует исход: статус, note, телеметрию и лог; отсутствующие методы пропускаются."""
    handler, host = route.handler, route.host
    norm = _norm_model(getattr(route, "model_id", None))
    handler._response_status = status
    if norm:
        _call(handler, "_telemetry_meta", model=norm)
    _call(handler, "_telemetry_note", nbytes)
    _call(handler, "_record_telemetry", status_code=status, error_type=error_type)
    line = f"route_failure status={status} reason={error_type} model={norm or '-'}{extra} {_trace_fields(handler)}"
    _call(host, "_log", line.rstrip())


def _make_sink(route: Any) -> Any:
    return route.host._HandlerSink(
        route.handler, extra_headers=route.host._trace_headers(route.handler._trace)
    )


def _emit_refusal(
    route: Any, last_error: Any, refusals: _Refusals, quota_skipped: _Refusals
) -> None:
    sink = _make_sink(route)
    pool = _exhausted_pool(refusals + quota_skipped)
    if pool is not None:
        status, headers, payload = build_pool_exhausted_error(
            pool[1], pool_label=pool[0]
        )
        sink.start(status, list(headers))
        sink.write(payload)
        _record_failure(route, status, "pool_exhausted", len(payload))
        return
    err = last_error if isinstance(last_error, RouteRefusal) else quota_skipped[0][1]
    status = classify_route_failure(err).status_code
    sink.start(err.status_code, list(err.response_headers))
    sink.write(err.response_body)
    _record_failure(route, status, "RouteRefusal", len(err.response_body))


def _emit_all_routes_open(route: Any, cb_retry_after: int) -> None:
    sink = _make_sink(route)
    sink.start(
        503,
        [("Content-Type", "application/json"), ("Retry-After", str(cb_retry_after))],
    )
    sink.write(ALL_ROUTES_OPEN_BODY)
    _record_failure(
        route,
        503,
        "all_routes_open",
        len(ALL_ROUTES_OPEN_BODY),
        f" retry_after={cb_retry_after}",
    )


def emit_route_failure(
    route: Any,
    last_error: Any,
    refusals: list[Any],
    quota_skipped: list[Any],
    cb_retry_after: int | None,
) -> None:
    """Отправляет терминальный отказ (wire-ответ неизменен) и фиксирует телеметрию."""
    if isinstance(last_error, RouteRefusal) or quota_skipped:
        _emit_refusal(route, last_error, refusals, quota_skipped)
    elif cb_retry_after is not None:
        _emit_all_routes_open(route, cb_retry_after)
    else:
        route.reject(503, "route_unavailable", "no eligible transport is available")


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def finalize_cli_serve(
    handler: Any,
    started: float,
    log_fn: Callable[[str], None],
    *,
    client_gone: bool = False,
) -> None:
    """Финал CLI-ветки; ранний отказ внутри failover не затеняет итоговый 200."""
    exc = sys.exc_info()[1]
    if not isinstance(exc, RouteRefusal):
        handler._record_telemetry(client_gone=client_gone)
        log_fn(
            f"done route=cli status={handler._response_status} {handler._trace_log_fields()} elapsed_ms={_elapsed_ms(started)}"
        )
        return
    status = classify_route_failure(exc).status_code
    in_failover = getattr(handler, "_transport_attempt", None) is not None
    handler._response_status = status
    if not in_failover:
        handler._record_telemetry(status_code=status, error_type="RouteRefusal")
    log_fn(
        f"done route=cli status={status} {handler._trace_log_fields()} elapsed_ms={_elapsed_ms(started)}"
    )
    if in_failover:
        handler._response_status = 0


def finalize_passthrough_serve(
    handler: Any, host: Any, sink: Any, started: float
) -> None:
    """Финал passthrough; pre-commit RouteRefusal внутри failover не пишет телеметрию."""
    exc = sys.exc_info()[1]
    skip = (
        isinstance(exc, RouteRefusal)
        and getattr(handler, "_transport_attempt", None) is not None
    )
    if not skip:
        handler._telemetry_passthrough_done(sink.status)
    host._log(
        f"done route=passthrough status={sink.status} {handler._trace_log_fields()} elapsed_ms={_elapsed_ms(started)}"
    )


def _client_gone(route: Any) -> bool:
    try:
        return bool(route.host._client_gone(route.handler.connection))
    except Exception:
        return False


def _record_unrecorded_exit(route: Any, active_exc: BaseException | None) -> None:
    """Ровно одна запись на аварийном выходе (500/499); штатный и отказный выходы не трогает."""
    handler = route.handler
    gone = _client_gone(route)
    failed = active_exc is not None and not isinstance(active_exc, RouteRefusal)
    if (
        getattr(handler, "_req_recorded", False)
        or getattr(handler, "_response_status", 0) != 0
    ):
        return
    if not (failed or gone):
        return
    rec = getattr(handler, "_record_telemetry", None)
    if callable(rec):
        with contextlib.suppress(Exception):
            rec(client_gone=gone)


def finalize_routes_exit(route: Any, reservation: Any) -> None:
    """Освобождает резервацию и гарантирует exactly-once телеметрию на не-успешном выходе."""
    active_exc = sys.exc_info()[1]
    try:
        reservation.release_unused()
    finally:
        _record_unrecorded_exit(route, active_exc)
