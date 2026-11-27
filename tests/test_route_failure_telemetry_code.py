"""Tests for Wave 6 route_failure_telemetry bounded code scan and ContextVar dedupe."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from core.route_attempts import RouteRefusal
from core.route_failure_telemetry import (
    emit_route_failure,
    extract_safe_refusal_code,
    route_failure_request_scope,
)


class _DummySink:
    def start(self, _status, _headers):
        pass

    def write(self, _body):
        pass


class _DummyHost:
    def __init__(self) -> None:
        self.logs: list[str] = []

    def _HandlerSink(self, _handler, extra_headers=None):
        return _DummySink()

    def _trace_headers(self, _trace):
        return []

    def _log(self, msg: str) -> None:
        self.logs.append(msg)


class _DummyHandler:
    __slots__ = ("_trace", "_response_status", "recorded")

    def __init__(self) -> None:
        self._trace = None
        self._response_status = 0
        self.recorded: list[tuple[int, str]] = []

    def _trace_log_fields(self) -> str:
        return "trace=t1"

    def _telemetry_meta(self, **_kw) -> None:
        pass

    def _telemetry_note(self, _n: int) -> None:
        pass

    def _record_telemetry(self, status_code: int = 0, error_type: str = "", **_kw) -> None:
        self.recorded.append((status_code, error_type))


class _DummyRoute:
    __slots__ = ("handler", "host", "model_id")

    def __init__(self, handler, host, model_id="gpt-6.1-sol") -> None:
        self.handler = handler
        self.host = host
        self.model_id = model_id


def test_extract_safe_refusal_code_and_allowlist_and_512b_bound() -> None:
    assert extract_safe_refusal_code(b"slow down") is None
    assert extract_safe_refusal_code(b'{"error":{"code":"turn_timeout"}}') == "turn_timeout"
    assert extract_safe_refusal_code(b'{"error":{"code":"unknown_custom_code"}}') == "unknown"
    assert extract_safe_refusal_code(b'{"error":{"code":"BAD-CODE!"}}') == "unknown"
    beyond_512 = b"{" + (b" " * 520) + b'"code":"turn_timeout"}'
    assert extract_safe_refusal_code(beyond_512) is None


def test_contextvar_dedupe_sequential_and_concurrent_without_mutating_route_or_handler() -> None:
    host = _DummyHost()
    handler = _DummyHandler()
    route = _DummyRoute(handler, host)
    err = RouteRefusal(504, [("Content-Type", "application/json")], b'{"error":{"code":"turn_timeout"}}')

    # Sequential scopes on the same route/handler each emit once
    for _ in range(2):
        with route_failure_request_scope():
            emit_route_failure(route, err, [], [], None)
            emit_route_failure(route, err, [], [], None)
    assert len(handler.recorded) == 2
    assert all("code=turn_timeout" in line for line in host.logs)

    # Concurrent threads with shared route/handler each emit once in their own ContextVar
    def _worker(_idx: int) -> None:
        with route_failure_request_scope():
            emit_route_failure(route, err, [], [], None)
            emit_route_failure(route, err, [], [], None)

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(_worker, range(4)))
    assert len(handler.recorded) == 6
