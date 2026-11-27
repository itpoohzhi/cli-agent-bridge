"""Unit tests for core/route_failure_telemetry.py (Wave W1-B1)."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from typing import Any

import pytest

import core.route_failure_telemetry as rft
from core.route_attempts import RouteFailover, RouteRefusal, build_pool_exhausted_error
from core.route_failure_telemetry import (
    ALL_ROUTES_OPEN_BODY,
    ALLOWED_REFUSAL_STATUSES,
    CLOSED_ERROR_TYPES,
    RouteFailureClassification,
    classify_route_failure,
    emit_route_failure,
    finalize_cli_serve,
    finalize_passthrough_serve,
    finalize_routes_exit,
)
from core.telemetry_hooks import known_model


class Wire:
    """Записывает wire-ответ sink'а."""

    def __init__(self) -> None:
        self.started: list[tuple[int, list[tuple[str, str]]]] = []
        self.body: list[bytes] = []

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        self.started.append((status, headers))

    def write(self, payload: bytes) -> None:
        self.body.append(payload)


def make_route(
    wire: Wire, *, full: bool = True, model_id: str | None = "muse-ember-1.0"
) -> Any:
    calls: list[tuple[str, Any]] = []
    logs: list[str] = []
    handler = SimpleNamespace(
        _trace=SimpleNamespace(), connection=object(), _response_status=0
    )
    if full:
        handler._telemetry_meta = lambda **kw: calls.append(("meta", kw))
        handler._telemetry_note = lambda n: calls.append(("note", n))
        handler._record_telemetry = lambda **kw: calls.append(("record", kw))
        handler._trace_log_fields = lambda: "trace=abc"
    host = SimpleNamespace(
        _trace_headers=lambda _t: {}, _HandlerSink=lambda _h, extra_headers=None: wire
    )
    if full:
        host._log = logs.append
    route = SimpleNamespace(
        handler=handler, host=host, reject=lambda *a: calls.append(("reject", a))
    )
    if model_id is not None:
        route.model_id = model_id
    route.calls, route.logs = calls, logs
    return route


# ---- classify ----------------------------------------------------------------


def test_constants() -> None:
    assert ALLOWED_REFUSAL_STATUSES == frozenset({402, 408, 429, 502, 503, 504})
    assert CLOSED_ERROR_TYPES == frozenset(
        {"all_routes_open", "RouteRefusal", "pool_exhausted", "route_unavailable"}
    )
    assert (
        ALL_ROUTES_OPEN_BODY
        == b'{"error":{"type":"all_routes_open","code":"all_routes_open","message":"all routes are open or busy"}}'
    )
    assert json.loads(ALL_ROUTES_OPEN_BODY)["error"]["type"] == "all_routes_open"


@pytest.mark.parametrize("status", sorted({402, 408, 429, 502, 503, 504}))
def test_classify_allowed_refusal(status: int) -> None:
    got = classify_route_failure(RouteRefusal(status), "muse-ember-1.0")
    assert got == RouteFailureClassification(status, "RouteRefusal", "muse-ember-1.0")


def test_classify_is_frozen() -> None:
    got = classify_route_failure(RouteRefusal(429))
    with pytest.raises(AttributeError):
        got.status_code = 1  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]


def test_classify_anti_duck_typing() -> None:
    exc = ValueError("x")
    exc.status_code = 429  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
    assert classify_route_failure(exc) == RouteFailureClassification(
        500, "ValueError", None
    )


@pytest.mark.parametrize("status", [200, 418, 404, 500])
def test_classify_nonstandard_refusal(status: int) -> None:
    assert classify_route_failure(RouteRefusal(status)) == RouteFailureClassification(
        502, "RouteRefusal", None
    )


def test_classify_bool_status_is_nonstandard() -> None:
    err = RouteRefusal(429)
    err.status_code = True  # type: ignore[assignment]  # pyright: ignore[reportAttributeAccessIssue]
    assert classify_route_failure(err).status_code == 502


def test_classify_other_exceptions() -> None:
    assert classify_route_failure(KeyboardInterrupt()).error_type == "KeyboardInterrupt"
    assert classify_route_failure(KeyboardInterrupt()).status_code == 500
    assert classify_route_failure(None).status_code == 500


def test_model_normalisation() -> None:
    assert known_model("unknown") is None
    assert known_model("muse-ember-1.0") == "muse-ember-1.0"
    assert classify_route_failure(None, "unknown").model is None
    assert classify_route_failure(None, "").model is None
    assert classify_route_failure(None, None).model is None
    assert classify_route_failure(None, "muse-ember-1.0").model == "muse-ember-1.0"
    assert classify_route_failure(None, 5).model is None  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


# ---- emit_route_failure -----------------------------------------------------------


def test_emit_all_routes_open() -> None:
    wire = Wire()
    route = make_route(wire)
    emit_route_failure(route, None, [], [], 90)
    assert wire.started == [
        (503, [("Content-Type", "application/json"), ("Retry-After", "90")])
    ]
    assert wire.body == [ALL_ROUTES_OPEN_BODY]
    assert route.handler._response_status == 503
    assert route.calls == [
        ("meta", {"model": "muse-ember-1.0"}),
        ("note", len(ALL_ROUTES_OPEN_BODY)),
        ("record", {"status_code": 503, "error_type": "all_routes_open"}),
    ]
    assert route.logs == [
        "route_failure status=503 reason=all_routes_open model=muse-ember-1.0 retry_after=90 trace=abc"
    ]


def test_emit_single_refusal() -> None:
    wire = Wire()
    route = make_route(wire, model_id="unknown")
    err = RouteRefusal(429, (("Retry-After", "7"),), b"slow down")
    emit_route_failure(route, err, [], [], None)
    assert wire.started == [(429, [("Retry-After", "7")])]
    assert wire.body == [b"slow down"]
    assert route.handler._response_status == 429
    assert route.calls == [
        ("note", 9),
        ("record", {"status_code": 429, "error_type": "RouteRefusal"}),
    ]
    assert route.logs == [
        "route_failure status=429 reason=RouteRefusal model=- trace=abc"
    ]


def test_emit_refusal_wire_unchanged_but_telemetry_normalised() -> None:
    wire = Wire()
    route = make_route(wire)
    emit_route_failure(route, RouteRefusal(418, (), b"tea"), [], [], None)
    assert wire.started[0][0] == 418
    assert route.handler._response_status == 502
    assert ("record", {"status_code": 502, "error_type": "RouteRefusal"}) in route.calls


def test_emit_quota_skipped_uses_first_quota_refusal() -> None:
    wire = Wire()
    route = make_route(wire)
    quota = [("b2", RouteRefusal(429, (("Retry-After", "45"),), b"q"), RouteFailover())]
    emit_route_failure(route, RuntimeError("boom"), [], quota, 90)
    assert wire.started == [(429, [("Retry-After", "45")])]
    assert wire.body == [b"q"]


def test_emit_pool_exhausted() -> None:
    wire = Wire()
    route = make_route(wire)
    fo = RouteFailover(statuses=frozenset({429}), pool="pool-a", pool_label="Pool A")
    refusals = [
        ("s1", RouteRefusal(429, (), b"a"), fo),
        ("s2", RouteRefusal(429, (), b"b"), fo),
    ]
    emit_route_failure(route, refusals[-1][1], refusals, [], None)
    status, headers, payload = build_pool_exhausted_error(
        [(s, e) for s, e, _ in refusals], pool_label="Pool A"
    )
    assert wire.started == [(status, list(headers))]
    assert wire.body == [payload]
    assert route.handler._response_status == status
    assert route.calls[-1] == (
        "record",
        {"status_code": status, "error_type": "pool_exhausted"},
    )
    assert (
        "reason=pool_exhausted" in route.logs[0] and f"status={status}" in route.logs[0]
    )


def test_emit_single_slot_pool_is_not_exhausted() -> None:
    wire = Wire()
    route = make_route(wire)
    fo = RouteFailover(statuses=frozenset({429}), pool="pool-a")
    refusals = [("s1", RouteRefusal(429, (), b"a"), fo)]
    emit_route_failure(route, refusals[0][1], refusals, [], None)
    assert wire.body == [b"a"]


def test_emit_pool_ignores_refusals_without_pool() -> None:
    wire = Wire()
    route = make_route(wire)
    refusals = [
        ("s1", RouteRefusal(429, (), b"a"), RouteFailover()),
        ("s2", RouteRefusal(429, (), b"b"), RouteFailover()),
    ]
    emit_route_failure(route, refusals[0][1], refusals, [], None)
    assert wire.body == [b"a"]


def test_emit_else_rejects() -> None:
    wire = Wire()
    route = make_route(wire)
    emit_route_failure(route, RuntimeError("x"), [], [], None)
    assert route.calls == [
        ("reject", (503, "route_unavailable", "no eligible transport is available"))
    ]
    assert wire.started == [] and route.logs == []


def test_emit_minimal_namespace_no_attribute_error() -> None:
    wire = Wire()
    route = make_route(wire, full=False, model_id=None)
    emit_route_failure(route, RouteRefusal(429, (), b"{}"), [], [], None)
    emit_route_failure(route, None, [], [], 5)
    assert [s for s, _ in wire.started] == [429, 503]
    assert route.handler._response_status == 503


def test_emit_swallows_telemetry_errors() -> None:
    wire = Wire()
    route = make_route(wire)

    def boom(**_kw: Any) -> None:
        raise RuntimeError("telemetry down")

    route.handler._record_telemetry = boom
    route.host._log = boom
    emit_route_failure(route, None, [], [], 1)
    assert wire.body == [ALL_ROUTES_OPEN_BODY]


def test_emit_no_sync_duckdb(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_a: Any, **_k: Any) -> None:
        raise AssertionError("sync DuckDB access on hot path")

    # duckdb может отсутствовать в окружении: подменяем модуль целиком.
    monkeypatch.setitem(sys.modules, "duckdb", SimpleNamespace(connect=forbidden))
    wire = Wire()
    emit_route_failure(make_route(wire), None, [], [], 3)
    emit_route_failure(make_route(wire), RouteRefusal(429, (), b"x"), [], [], None)
    assert len(wire.started) == 2


# ---- finalize_cli_serve -------------------------------------------------------


def make_handler(attempt: Any = None, status: int = 0) -> Any:
    calls: list[dict[str, Any]] = []
    handler = SimpleNamespace(
        _transport_attempt=attempt,
        _response_status=status,
        _record_telemetry=lambda **kw: calls.append(kw),
        _trace_log_fields=lambda: "t=1",
    )
    handler.calls = calls
    return handler


def run_in_except(exc: BaseException, fn: Any) -> None:
    try:
        raise exc
    except type(exc):
        fn()


def test_cli_refusal_inside_failover_defers_telemetry() -> None:
    handler, logs = make_handler(attempt=object()), []
    run_in_except(
        RouteRefusal(429),
        lambda: finalize_cli_serve(handler, rft.time.monotonic(), logs.append),
    )
    assert handler.calls == []
    assert handler._response_status == 0
    assert len(logs) == 1 and logs[0].startswith(
        "done route=cli status=429 t=1 elapsed_ms="
    )


def test_cli_refusal_outside_failover_records() -> None:
    handler, logs = make_handler(attempt=None), []
    run_in_except(
        RouteRefusal(429),
        lambda: finalize_cli_serve(handler, rft.time.monotonic(), logs.append),
    )
    assert handler.calls == [{"status_code": 429, "error_type": "RouteRefusal"}]
    assert handler._response_status == 429
    assert logs[0].startswith("done route=cli status=429 ")


def test_cli_refusal_without_attempt_attr_records() -> None:
    handler, logs = make_handler(), []
    del handler._transport_attempt
    run_in_except(
        RouteRefusal(503),
        lambda: finalize_cli_serve(handler, rft.time.monotonic(), logs.append),
    )
    assert handler.calls == [{"status_code": 503, "error_type": "RouteRefusal"}]


@pytest.mark.parametrize("gone", [False, True])
def test_cli_normal_exit(gone: bool) -> None:
    handler, logs = make_handler(status=200), []
    finalize_cli_serve(handler, rft.time.monotonic() - 1, logs.append, client_gone=gone)
    assert handler.calls == [{"client_gone": gone}]
    assert handler._response_status == 200
    assert logs[0].startswith("done route=cli status=200 t=1 elapsed_ms=")
    assert int(logs[0].rsplit("=", 1)[1]) >= 1000


def test_cli_non_refusal_exception_takes_normal_path() -> None:
    handler, logs = make_handler(attempt=object(), status=500), []
    run_in_except(
        ValueError("x"),
        lambda: finalize_cli_serve(handler, rft.time.monotonic(), logs.append),
    )
    assert handler.calls == [{"client_gone": False}]
    assert handler._response_status == 500


# ---- finalize_passthrough_serve --------------------------------------------------


def make_passthrough(attempt: Any) -> tuple[Any, Any, Any]:
    done: list[int] = []
    logs: list[str] = []
    handler = SimpleNamespace(
        _transport_attempt=attempt,
        _telemetry_passthrough_done=done.append,
        _trace_log_fields=lambda: "t=2",
    )
    host = SimpleNamespace(_log=logs.append)
    handler.done, host.logs = done, logs
    return handler, host, SimpleNamespace(status=429)


def test_passthrough_refusal_inside_failover_skips_done() -> None:
    handler, host, sink = make_passthrough(object())
    run_in_except(
        RouteRefusal(429),
        lambda: finalize_passthrough_serve(handler, host, sink, rft.time.monotonic()),
    )
    assert handler.done == []
    assert len(host.logs) == 1 and host.logs[0].startswith(
        "done route=passthrough status=429 t=2 elapsed_ms="
    )


def test_passthrough_refusal_outside_failover_records() -> None:
    handler, host, sink = make_passthrough(None)
    run_in_except(
        RouteRefusal(429),
        lambda: finalize_passthrough_serve(handler, host, sink, rft.time.monotonic()),
    )
    assert handler.done == [429]


def test_passthrough_normal_200() -> None:
    handler, host, _ = make_passthrough(object())
    sink = SimpleNamespace(status=200)
    finalize_passthrough_serve(handler, host, sink, rft.time.monotonic())
    assert handler.done == [200]
    assert host.logs[0].startswith("done route=passthrough status=200 ")


def test_passthrough_non_refusal_exception_records() -> None:
    handler, host, sink = make_passthrough(object())
    run_in_except(
        ValueError("x"),
        lambda: finalize_passthrough_serve(handler, host, sink, rft.time.monotonic()),
    )
    assert handler.done == [429]


# ---- finalize_routes_exit ------------------------------------------------------


def make_exit(
    *, gone: bool = False, recorded: bool = False, status: int = 0
) -> tuple[Any, Any]:
    recs: list[dict[str, Any]] = []
    released: list[int] = []
    handler = SimpleNamespace(
        connection=object(),
        _req_recorded=recorded,
        _response_status=status,
        _record_telemetry=lambda **kw: recs.append(kw),
    )
    route = SimpleNamespace(
        handler=handler, host=SimpleNamespace(_client_gone=lambda _c: gone)
    )
    reservation = SimpleNamespace(release_unused=lambda: released.append(1))
    route.recs, reservation.released = recs, released
    return route, reservation


def test_exit_normal_return_releases_only() -> None:
    route, res = make_exit()
    finalize_routes_exit(route, res)
    assert res.released == [1] and route.recs == []


def test_exit_active_exception_records() -> None:
    route, res = make_exit()
    run_in_except(ValueError("x"), lambda: finalize_routes_exit(route, res))
    assert res.released == [1] and route.recs == [{"client_gone": False}]


def test_exit_refusal_exception_does_not_record() -> None:
    route, res = make_exit()
    run_in_except(RouteRefusal(429), lambda: finalize_routes_exit(route, res))
    assert res.released == [1] and route.recs == []


def test_exit_client_gone_records() -> None:
    route, res = make_exit(gone=True)
    finalize_routes_exit(route, res)
    assert route.recs == [{"client_gone": True}]


def test_exit_refusal_with_client_gone_records_499() -> None:
    route, res = make_exit(gone=True)
    run_in_except(RouteRefusal(429), lambda: finalize_routes_exit(route, res))
    assert route.recs == [{"client_gone": True}]


def test_exit_already_recorded_no_duplicate() -> None:
    route, res = make_exit(gone=True, recorded=True)
    run_in_except(ValueError("x"), lambda: finalize_routes_exit(route, res))
    assert res.released == [1] and route.recs == []


def test_exit_committed_response_not_touched() -> None:
    route, res = make_exit(gone=True, status=200)
    run_in_except(ValueError("x"), lambda: finalize_routes_exit(route, res))
    assert route.recs == []


def test_exit_client_gone_probe_failure_is_false() -> None:
    route, res = make_exit()

    def boom(_c: Any) -> bool:
        raise OSError("closed")

    route.host._client_gone = boom
    finalize_routes_exit(route, res)
    assert route.recs == []
    run_in_except(ValueError("x"), lambda: finalize_routes_exit(route, res))
    assert route.recs == [{"client_gone": False}]


def test_exit_missing_recorder_is_noop() -> None:
    route, res = make_exit(gone=True)
    del route.handler._record_telemetry
    finalize_routes_exit(route, res)
    assert res.released == [1]


def test_exit_recorder_error_does_not_mask_original() -> None:
    route, res = make_exit()

    def boom(**_kw: Any) -> None:
        raise RuntimeError("record failed")

    route.handler._record_telemetry = boom
    with pytest.raises(ValueError, match="orig"):
        try:
            raise ValueError("orig")
        finally:
            finalize_routes_exit(route, res)
    assert res.released == [1]


def test_exit_release_error_still_records_once() -> None:
    route, res = make_exit(gone=True)

    def boom() -> None:
        raise RuntimeError("release failed")

    res.release_unused = boom
    with pytest.raises(RuntimeError, match="release failed"):
        finalize_routes_exit(route, res)
    assert route.recs == [{"client_gone": True}]
