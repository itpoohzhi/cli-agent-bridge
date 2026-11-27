"""W2-B3: интеграционные тесты телеметрии отказов — AC-1 (503 all_routes_open), AC-2 (CLI RouteRefusal), OPEN-01."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core import passthrough_facade as facade
from core.request_telemetry import RequestTelemetryStore
from tests.failover_telemetry_helpers import (
    CLI_ID,
    PT_A,
    REFUSAL_CODES,
    Route,
    gateway,
    open_store,
    post,
    setup_isolated_runtime,
)
from tests.failover_telemetry_responders import (
    assert_all_routes_open_wire,
    assert_cli_done_before_passthrough_done,
    assert_route_failure_log,
    assert_single_record,
    cli_refuses,
    open_all_route_breakers,
    upstream_ok,
)


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_isolated_runtime(monkeypatch)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[RequestTelemetryStore]:
    yield from open_store(tmp_path)


# ---- AC-1: 503 all_routes_open -----------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True])
def test_all_routes_open_returns_503_and_records_telemetry(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore, stream: bool
) -> None:
    routes: list[Route] = [(CLI_ID, cli_refuses(502)), (PT_A, upstream_ok(stream))]
    with gateway(monkeypatch, store, routes) as gw:
        open_all_route_breakers([CLI_ID, PT_A])
        status, headers, raw = post(gw.port, stream=stream)
    assert_all_routes_open_wire(status, headers, raw)
    assert gw.cli_calls == [] and gw.upstreams[PT_A].post_count == 0
    assert_single_record(gw, status=503, error_type="all_routes_open")
    assert_route_failure_log(gw)


# ---- AC-2: терминальный CLI RouteRefusal ---------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("code", REFUSAL_CODES)
def test_cli_route_refusal_terminal_records_refusal_status(
    monkeypatch: pytest.MonkeyPatch,
    store: RequestTelemetryStore,
    code: int,
    stream: bool,
) -> None:
    with gateway(monkeypatch, store, [(CLI_ID, cli_refuses(code))]) as gw:
        status, _headers, _raw = post(gw.port, stream=stream)
    assert status == code
    assert gw.cli_calls == [CLI_ID]
    assert_single_record(gw, status=code, error_type="RouteRefusal")
    assert gw.log_lines(f"done route=cli status={code} ")
    assert not gw.log_lines("done route=cli status=0 ")
    assert not [r for r in gw.rows() if r["status_code"] == 500]


# ---- OPEN-01: AFTER-FAILOVER-200 (final-status-wins) ---------------------------------------------


@pytest.mark.parametrize("stream", [False, True])
def test_cli_429_failover_to_passthrough_200_records_single_200(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore, stream: bool
) -> None:
    with gateway(
        monkeypatch, store, [(CLI_ID, cli_refuses(429)), (PT_A, upstream_ok(stream))]
    ) as gw:
        status, _headers, raw = post(gw.port, stream=stream)
    assert status == 200 and b"from-pt" in raw
    assert gw.cli_calls == [CLI_ID] and gw.upstreams[PT_A].post_count == 1
    row = assert_single_record(gw, status=200, error_type=None)
    assert row["route_mode"] == "passthrough" and row["backend_id"] == PT_A
    assert_cli_done_before_passthrough_done(gw)
    assert not gw.log_lines("route_failure ")


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("failover", [False, True], ids=["direct", "after-failover"])
def test_success_path_records_before_routes_finally(
    monkeypatch: pytest.MonkeyPatch,
    store: RequestTelemetryStore,
    failover: bool,
    stream: bool,
) -> None:
    """RW-201: запись телеметрии на успешном пути происходит ДО входа в finally _run_routes."""
    entered: list[dict[str, Any]] = []
    original = facade.finalize_routes_exit

    def spy(route: Any, reservation: Any) -> None:
        handler = route.handler
        entered.append(
            {
                "recorded": bool(getattr(handler, "_req_recorded", False)),
                "queued": store._queue.qsize(),
            }
        )
        original(route, reservation)

    monkeypatch.setattr(facade, "finalize_routes_exit", spy)
    routes: list[Route] = (
        [(CLI_ID, cli_refuses(429)), (PT_A, upstream_ok(stream))]
        if failover
        else [(PT_A, upstream_ok(stream))]
    )
    with gateway(monkeypatch, store, routes) as gw:
        status, _headers, _raw = post(gw.port, stream=stream)
    assert status == 200
    assert entered == [{"recorded": True, "queued": 1}]
    assert_single_record(gw, status=200, error_type=None)
