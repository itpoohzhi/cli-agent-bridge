"""Unit tests: finalize_cli_serve / finalize_passthrough_serve / finalize_routes_exit (Wave W1-B1)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import core.route_failure_telemetry as rft
from core.route_attempts import RouteRefusal
from core.route_failure_telemetry import (
    _call,
    _trace_fields,
    finalize_cli_serve,
    finalize_passthrough_serve,
    finalize_routes_exit,
)


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


def _finalize_refusal(handler: Any, log_fn: Any) -> None:
    run_in_except(
        RouteRefusal(429),
        lambda: finalize_cli_serve(handler, rft.time.monotonic(), log_fn),
    )


@pytest.mark.parametrize(
    ("attempt", "calls"),
    [(object(), []), (None, [{"status_code": 429, "error_type": "RouteRefusal"}])],
)
def test_cli_refusal_keeps_prior_200(attempt: Any, calls: list[Any]) -> None:
    handler = make_handler(attempt=attempt, status=200)
    _finalize_refusal(handler, [].append)
    assert handler._response_status == 200 and handler.calls == calls


def test_cli_failover_log_error_leaves_status_clean() -> None:
    handler = make_handler(attempt=object(), status=0)

    def boom(_line: str) -> None:
        raise BrokenPipeError("log")

    with pytest.raises(BrokenPipeError):
        _finalize_refusal(handler, boom)
    assert handler._response_status == 0 and handler.calls == []


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


@pytest.mark.parametrize("exc", [RouteRefusal(429), ValueError("x")])
def test_passthrough_outside_failover_or_non_refusal_records(exc: Exception) -> None:
    handler, host, sink = make_passthrough(
        None if isinstance(exc, RouteRefusal) else object()
    )
    run_in_except(
        exc,
        lambda: finalize_passthrough_serve(handler, host, sink, rft.time.monotonic()),
    )
    assert handler.done == [429]


def test_passthrough_normal_200() -> None:
    handler, host, _ = make_passthrough(object())
    sink = SimpleNamespace(status=200)
    finalize_passthrough_serve(handler, host, sink, rft.time.monotonic())
    assert handler.done == [200]
    assert host.logs[0].startswith("done route=passthrough status=200 ")


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


@pytest.mark.parametrize("refusal", [False, True])
def test_exit_client_gone_records_even_on_refusal(refusal: bool) -> None:
    route, res = make_exit(gone=True)
    if refusal:
        run_in_except(RouteRefusal(429), lambda: finalize_routes_exit(route, res))
    else:
        finalize_routes_exit(route, res)
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


def test_finalize_routes_exit_minimal_handler_defaults() -> None:
    assert _call(SimpleNamespace(), "nonexistent") is None
    assert _trace_fields(SimpleNamespace()) == ""
    recs: list[dict[str, Any]] = []
    handler = SimpleNamespace(
        _record_telemetry=lambda **kw: recs.append(kw), connection=object()
    )
    route = SimpleNamespace(
        handler=handler, host=SimpleNamespace(_client_gone=lambda _c: False)
    )
    res = SimpleNamespace(release_unused=lambda: None)
    run_in_except(RuntimeError("x"), lambda: finalize_routes_exit(route, res))
    assert recs == [{"client_gone": False}]
