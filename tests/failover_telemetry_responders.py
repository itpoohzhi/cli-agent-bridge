"""Ответчики маршрутов и проверки для интеграционных тестов телеметрии отказов (W2-B3)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from typing import Any

from core import passthrough_facade as facade
from core.backend_adapter import StreamSink, TurnContext, TurnResult
from core.route_cb import FailureOutcome
from core.route_failure_telemetry import ALL_ROUTES_OPEN_BODY
from core.telemetry_sql import NAMES
from core.usage_schema import USAGE_LOG_FIELDS
from tests.failover_telemetry_helpers import Gateway, Upstream
from tests.test_resident_precommit_failover import MODEL_ID, _resident_error
from tests.transport_wire_support import RecordingUpstream


def cli_refuses(code: int) -> Callable[[TurnContext, StreamSink | None], TurnResult]:
    def refuse(_ctx: TurnContext, _sse: StreamSink | None) -> TurnResult:
        raise _resident_error(
            code, "resident_dispatch_failed", f"resident refused {code}"
        )

    return refuse


def upstream_error(code: int) -> Upstream:
    def respond(up: RecordingUpstream, handler: Any, _body: bytes) -> None:
        up.json(
            handler,
            {
                "error": {
                    "type": "upstream_error",
                    "code": "upstream_refused",
                    "message": f"upstream {code}",
                }
            },
            status=code,
        )

    return respond


def upstream_ok(stream: bool) -> Upstream:
    def respond(up: RecordingUpstream, handler: Any, _body: bytes) -> None:
        if stream:
            up.sse(
                handler,
                b'data: {"id":"ok-sse","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"from-pt"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
            )
        else:
            up.json(
                handler,
                {
                    "id": "ok-1",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "from-pt"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

    return respond


def open_all_route_breakers(backends: Sequence[str]) -> None:
    """Открывает РЕАЛЬНЫЙ RouteCB для всех маршрутов (ключ — (provider, model, backend))."""
    route_cb, _legacy = facade.get_route_cb(facade._RUNTIME)
    assert route_cb is not None
    for backend in backends:
        key = (backend, MODEL_ID, backend)
        for _ in range(route_cb._config.failure_threshold):
            route_cb.record_failure(key, FailureOutcome(status=503))
        assert route_cb.try_acquire(key, time.monotonic()) is None, (
            f"breaker {backend} must be open"
        )


def _assert_columns(row: dict[str, Any], rec: dict[str, Any], model: str) -> None:
    assert len(row) == len(NAMES) == 34
    assert set(rec) == set(USAGE_LOG_FIELDS) and len(rec) == 18
    assert row["model"] == model and rec["model"] == model


def assert_single_record(
    gw: Gateway, *, status: int, error_type: str | None, model: str = MODEL_ID
) -> dict[str, Any]:
    """Ровно одна запись в БД (34 колонки) и в usage.jsonl (18 полей) с одним request_id."""
    rows, usage = gw.rows(), gw.usage()
    assert len(rows) == 1, rows
    assert len(usage) == 1, usage
    row, rec = rows[0], usage[0]
    _assert_columns(row, rec, model)
    assert (row["status_code"], row["error_type"]) == (status, error_type)
    assert rec["http_status"] == status
    assert row["request_id"] and rec["request_id"] == row["request_id"]
    return row


def assert_all_routes_open_wire(
    status: int, headers: dict[str, str], raw: bytes
) -> None:
    assert status == 503
    assert headers["retry-after"].isdigit() and int(headers["retry-after"]) > 0
    assert "application/json" in headers["content-type"]
    assert raw == ALL_ROUTES_OPEN_BODY
    assert json.loads(raw)["error"]["type"] == "all_routes_open"


def assert_route_failure_log(gw: Gateway) -> None:
    failure = gw.log_lines("route_failure ")
    assert len(failure) == 1
    assert (
        "status=503" in failure[0]
        and "all_routes_open" in failure[0]
        and f"model={MODEL_ID}" in failure[0]
    )


def assert_cli_done_before_passthrough_done(gw: Gateway) -> None:
    cli_done, pt_done = (
        gw.log_lines("done route=cli status=429 "),
        gw.log_lines("done route=passthrough status=200 "),
    )
    assert len(cli_done) == 1 and len(pt_done) == 1
    assert gw.logs.index(cli_done[0]) < gw.logs.index(pt_done[0])
