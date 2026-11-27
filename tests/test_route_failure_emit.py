"""Unit tests: emit_route_failure из core/route_failure_telemetry.py (Wave W1-B1)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from core.route_attempts import RouteFailover, RouteRefusal, build_pool_exhausted_error
from core.route_failure_telemetry import ALL_ROUTES_OPEN_BODY, emit_route_failure


class Wire:
    """Записывает wire-ответ sink'а."""

    def __init__(self, fail: tuple[str, Exception] | None = None) -> None:
        self.started: list[tuple[int, list[tuple[str, str]]]] = []
        self.body: list[bytes] = []
        self.fail = fail

    def _maybe_fail(self, op: str) -> None:
        if self.fail is not None and self.fail[0] == op:
            raise self.fail[1]

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        self._maybe_fail("start")
        self.started.append((status, headers))

    def write(self, payload: bytes) -> None:
        self._maybe_fail("write")
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


ELSE_ARGS = (503, "route_unavailable", "no eligible transport is available")
ELSE_LOG = (
    "route_failure status=503 reason=route_unavailable model=muse-ember-1.0 trace=abc"
)


def test_emit_else_rejects_and_records_when_reject_does_not_record() -> None:
    wire = Wire()
    route = make_route(wire)
    emit_route_failure(route, RuntimeError("x"), [], [], None)
    assert route.calls == [
        ("reject", ELSE_ARGS),
        ("meta", {"model": "muse-ember-1.0"}),
        ("note", 0),
        ("record", {"status_code": 503, "error_type": "route_unavailable"}),
    ]
    assert route.handler._response_status == 503
    assert route.logs == [ELSE_LOG]
    assert wire.started == []


def test_emit_else_no_double_record_when_reject_recorded() -> None:
    route = make_route(Wire())

    def reject(*a: Any) -> None:
        route.calls.append(("reject", a))
        route.handler._req_recorded = True

    route.reject = reject
    emit_route_failure(route, RuntimeError("x"), [], [], None)
    assert route.calls == [("reject", ELSE_ARGS)]
    assert route.logs == []


def test_emit_else_reject_raises_still_records() -> None:
    route = make_route(Wire())

    def reject(*_a: Any) -> None:
        raise OSError("broken")

    route.reject = reject
    with pytest.raises(OSError, match="broken"):
        emit_route_failure(route, RuntimeError("x"), [], [], None)
    assert route.calls[-1] == (
        "record",
        {"status_code": 503, "error_type": "route_unavailable"},
    )
    assert route.logs == [ELSE_LOG]


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


# ---- F-001: телеметрия при I/O-сбое sink -------------------------------------------

FO = RouteFailover(statuses=frozenset({429}), pool="pool-a", pool_label="Pool A")
POOL = [
    ("s1", RouteRefusal(429, (), b"a"), FO),
    ("s2", RouteRefusal(429, (), b"b"), FO),
]
POOL_STATUS = build_pool_exhausted_error(
    [(s, e) for s, e, _ in POOL], pool_label="Pool A"
)[0]
SINK_CASES = [  # (last_error, refusals, cb_retry_after, status, error_type)
    (None, [], 90, 503, "all_routes_open"),
    (RouteRefusal(429, (), b"x"), [], None, 429, "RouteRefusal"),
    (POOL[-1][1], POOL, None, POOL_STATUS, "pool_exhausted"),
]


@pytest.mark.parametrize(
    ("op", "exc"),
    [
        ("start", BrokenPipeError("pipe")),
        ("write", OSError("io")),
        ("write", ConnectionResetError("reset")),
    ],
)
@pytest.mark.parametrize("case", SINK_CASES)
def test_sink_failure_still_records_once(
    op: str, exc: Exception, case: tuple[Any, Any, Any, int, str]
) -> None:
    err, refusals, cb, status, etype = case
    route = make_route(Wire(fail=(op, exc)))
    with pytest.raises(type(exc)):
        emit_route_failure(route, err, refusals, [], cb)
    rec = [c for c in route.calls if c[0] == "record"]
    assert rec == [("record", {"status_code": status, "error_type": etype})]
    assert route.handler._response_status == status
    assert len(route.logs) == 1 and f"reason={etype}" in route.logs[0]
