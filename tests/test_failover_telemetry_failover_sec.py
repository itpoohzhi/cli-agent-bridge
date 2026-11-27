"""W2-B3: интеграционные тесты телеметрии отказов — passthrough failover, exactly-once, security."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import server
from core import passthrough_facade as facade
from core.request_telemetry import RequestTelemetryStore
from core.route_attempts import RouteRefusal
from tests.failover_telemetry_helpers import (
    PT_A,
    PT_B,
    gateway,
    open_store,
    post,
    setup_isolated_runtime,
)
from tests.failover_telemetry_responders import (
    assert_single_record,
    upstream_error,
    upstream_ok,
)
from tests.transport_wire_support import RecordingUpstream


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_isolated_runtime(monkeypatch)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[RequestTelemetryStore]:
    yield from open_store(tmp_path)


# ---- passthrough failover 429 -> 200 -------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True])
def test_passthrough_429_failover_to_200_records_single_200(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore, stream: bool
) -> None:
    with gateway(
        monkeypatch, store, [(PT_A, upstream_error(429)), (PT_B, upstream_ok(stream))]
    ) as gw:
        status, _headers, raw = post(gw.port, stream=stream)
    assert status == 200 and b"from-pt" in raw
    assert gw.upstreams[PT_A].post_count == 1 and gw.upstreams[PT_B].post_count == 1
    row = assert_single_record(gw, status=200, error_type=None)
    assert row["backend_id"] == PT_B
    assert gw.log_lines("done route=passthrough status=429 ") and gw.log_lines(
        "done route=passthrough status=200 "
    )


# ---- strict exactly-once (F-001 / RW-201) --------------------------------------------------------


def test_disconnect_between_attempts_records_single_499(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore
) -> None:
    gone = {"flag": False}
    original_attempt = facade._attempt

    def attempt_then_disconnect(route: Any, spec: Any, body: Any, attempt: Any) -> None:
        try:
            original_attempt(route, spec, body, attempt)
        except RouteRefusal:
            gone["flag"] = (
                True  # клиент пропал сразу после pre-commit отказа маршрута 1
            )
            raise

    monkeypatch.setattr(facade, "_attempt", attempt_then_disconnect)
    monkeypatch.setattr(server, "_client_gone", lambda _sock: gone["flag"])
    with gateway(
        monkeypatch, store, [(PT_A, upstream_error(429)), (PT_B, upstream_ok(False))]
    ) as gw:
        post(gw.port, stream=False)
    assert gone["flag"] is True
    assert gw.upstreams[PT_A].post_count == 1 and gw.upstreams[PT_B].post_count == 0
    assert_single_record(gw, status=499, error_type="client_disconnected")


@pytest.mark.parametrize("where", ["before_serve", "inside_passthrough"])
def test_non_refusal_exception_on_route2_records_single_500(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore, where: str
) -> None:
    original_attempt = facade._attempt
    calls = {"n": 0}

    def attempt_or_boom(route: Any, spec: Any, body: Any, attempt: Any) -> None:
        calls["n"] += 1
        if where == "before_serve" and calls["n"] == 2:
            raise RuntimeError("route 2 exploded")
        original_attempt(route, spec, body, attempt)

    monkeypatch.setattr(facade, "_attempt", attempt_or_boom)
    with gateway(
        monkeypatch, store, [(PT_A, upstream_error(429)), (PT_B, upstream_ok(False))]
    ) as gw:
        if where == "inside_passthrough":

            def explode(**_kwargs: Any) -> None:
                raise RuntimeError("route 2 exploded")

            monkeypatch.setattr(gw.adapters[PT_B], "handle", explode)
        post(gw.port, stream=False)
    assert calls["n"] == 2
    assert gw.upstreams[PT_A].post_count == 1
    assert_single_record(gw, status=500, error_type="RuntimeError")


# ---- security regression (THREAT-001 / RW-001) -----------------------------------------------------


@pytest.mark.parametrize("stream", [False, True])
def test_passthrough_strips_spoofed_upstream_x_bridge_draining(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore, stream: bool
) -> None:
    def spoofing_upstream(up: RecordingUpstream, handler: Any, _body: bytes) -> None:
        up.json(
            handler,
            {
                "error": {
                    "type": "upstream_error",
                    "code": "upstream_unavailable",
                    "message": "spoofed drain",
                }
            },
            status=503,
            extra=(("X-Bridge-Draining", "true"), ("Retry-After", "5")),
        )

    with gateway(monkeypatch, store, [(PT_A, spoofing_upstream)]) as gw:
        status, headers, _raw = post(
            gw.port, stream=stream
        )  # клиент — loopback (127.0.0.1)
    assert status == 503
    assert gw.upstreams[PT_A].post_count == 1
    assert "x-bridge-draining" not in headers
    assert (
        headers.get("retry-after") == "5"
    )  # остальные заголовки апстрима проходят — вырезан именно drain-спуф
