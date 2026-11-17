"""W0 contract tests for bridge-owned transport failover and replay fences."""

from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import passthrough_facade as facade
from core.retry_control import HealthDomain, RouteCandidate
from core.route_attempts import AttemptPhase, AttemptState, RouteAttempt, RouteRefusal
from core.route_health_policy import RetryBudgetConfig

_EXPECT_RED = os.getenv("FAILOVER_EXPECT_RED") == "1"
_MODULE = "core.route_attempts"
_STATELESS_ENDPOINTS = (
    "/v1/chat/completions",
    "/cloudcode/v1internal:streamGenerateContent",
)


class _EvaluateReplay(Protocol):
    def __call__(self, facts: Mapping[str, object], /) -> Mapping[str, object]: ...


class _RunFailover(Protocol):
    def __call__(
        self,
        facts: Mapping[str, object],
        attempt: Callable[[str, str], Mapping[str, object]],
        /,
    ) -> Mapping[str, object]: ...


class _BuildHeaders(Protocol):
    def __call__(self, facts: Mapping[str, object], /) -> Mapping[str, str]: ...


def _load_api() -> tuple[_EvaluateReplay, _RunFailover, _BuildHeaders] | None:
    module = import_module(_MODULE)
    namespace = vars(module)
    required = ("evaluate_replay", "run_failover", "build_georouter_headers")
    missing = [name for name in required if name not in namespace]
    if missing:
        if _EXPECT_RED:
            return None
        raise AssertionError(
            f"W0 contract API missing from {_MODULE}: {', '.join(missing)}"
        )
    return (
        cast(_EvaluateReplay, namespace["evaluate_replay"]),
        cast(_RunFailover, namespace["run_failover"]),
        cast(_BuildHeaders, namespace["build_georouter_headers"]),
    )


def _facts(**changes: object) -> dict[str, object]:
    facts: dict[str, object] = {
        "status_code": 503,
        "timed_out": False,
        "truncated": False,
        "wire_send_started": True,
        "endpoint": "/v1/chat/completions",
        "tool_side_effects": False,
        "downstream_committed": False,
        "retry_owner": "BRIDGE_OWNER",
        "max_total_attempts": 3,
        "canonical_model_id": "claude-sonnet-4-5",
        "effort": "high",
    }
    facts.update(changes)
    return facts


def _failure(_model: str, _effort: str) -> Mapping[str, object]:
    return {"status_code": 503, "timed_out": False, "truncated": False}


@pytest.mark.parametrize("status_code", [100, 201, 301, 400, 418, 500, 599])
def test_every_non_200_status_reaches_replay_evaluator(status_code: int) -> None:
    """VER-012: non-200 classification is not guarded by a status allowlist."""
    api = _load_api()
    if api is None:
        return
    decision = api[0](_facts(status_code=status_code))
    assert decision["evaluator_invoked"] is True


@pytest.mark.parametrize(
    "changes",
    [
        {"status_code": None, "timed_out": True},
        {"status_code": None, "truncated": True},
    ],
)
def test_timeout_and_precommit_truncation_reach_evaluator(
    changes: dict[str, object],
) -> None:
    """VER-012: timeout and pre-commit truncation use the same evaluator."""
    api = _load_api()
    if api is None:
        return
    decision = api[0](_facts(**changes))
    assert decision["evaluator_invoked"] is True


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (*_STATELESS_ENDPOINTS[:1], True),
        (*_STATELESS_ENDPOINTS[1:], True),
        ("/v1/responses", False),
        ("/v1/chat/completions/", False),
        ("/v1/chat/completions?stream=true", False),
        ("/tools/execute", False),
    ],
)
def test_wire_send_replay_has_exact_stateless_endpoint_allowlist(
    endpoint: str,
    expected: bool,
) -> None:
    """VER-013: only the two normalized stateless POST paths are replayable."""
    api = _load_api()
    if api is None:
        return
    decision = api[0](_facts(endpoint=endpoint))
    assert decision["replay_allowed"] is expected


@pytest.mark.parametrize(
    "changes",
    [
        {"tool_side_effects": True},
        {"tool_side_effects": None},
        {"downstream_committed": True},
    ],
)
def test_replay_fences_leave_exactly_one_attempt(changes: dict[str, object]) -> None:
    """VER-013: side effects, unknown ledger, or one client byte forbid replay."""
    api = _load_api()
    if api is None:
        return
    result = api[1](_facts(**changes), _failure)
    assert result["physical_attempts"] == 1
    assert result["replay_allowed"] is False


def test_bridge_owner_sets_georouter_no_retry_header() -> None:
    """VER-014: bridge authority disables nested georouter retries."""
    api = _load_api()
    if api is None:
        return
    headers = api[2](_facts())
    assert headers["X-Georouter-No-Retry"] == "1"


def test_total_attempt_cap_preserves_model_and_effort() -> None:
    """VER-014: failover is bounded and cannot substitute request identity."""
    api = _load_api()
    if api is None:
        return
    seen: list[tuple[str, str]] = []

    def record(model: str, effort: str) -> Mapping[str, object]:
        seen.append((model, effort))
        return _failure(model, effort)

    result = api[1](_facts(max_total_attempts=99), record)
    assert cast(int, result["physical_attempts"]) <= 3
    assert cast(int, result["max_total_attempts"]) <= 3
    assert seen and set(seen) == {("claude-sonnet-4-5", "high")}
    assert result["canonical_model_id"] == "claude-sonnet-4-5"
    assert result["effort"] == "high"


# --- Живой путь core.passthrough_facade (W6a): бюджет, fence и failover ---


class _Sink:
    def __init__(self, _handler: Any, extra_headers: Any = ()) -> None:
        self.status, self.body = 0, b""

    def start(self, status: int, _headers: Any) -> None:
        self.status = status

    def write(self, body: bytes) -> None:
        self.body = body


class _Handler:
    def __init__(self, path: str) -> None:
        self.path, self.connection = path, object()
        self._trace = SimpleNamespace(subagent_id=None)


class _Host:
    PassthroughAdapter = type("_PassthroughAdapter", (), {})
    _HandlerSink = _Sink
    _client_gone = staticmethod(lambda _connection: False)
    _trace_headers = staticmethod(lambda _trace: [])


class _Route:
    def __init__(self, path: str = "/v1/chat/completions", effort: str | None = None) -> None:
        self.model = {"routing": {}, "backend": "alpha", "default_effort": effort}
        self.model_id, self.request, self.alias_effort = "claude-sonnet-4-5", {}, None
        self.handler, self.host, self.rejections = _Handler(path), _Host(), []

    def reject(self, status: int, code: str, _message: str) -> None:
        self.rejections.append((status, code))


def _spec(backend: str) -> Any:
    return SimpleNamespace(backend=backend, credential_ref=None, params={})


@pytest.fixture()
def live(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setattr(facade, "_RUNTIME", facade._RuntimeState())
    monkeypatch.setattr(facade, "prepare_post_body", lambda _route: b"{}")
    monkeypatch.setattr(facade, "_eligible", lambda *_args: True)
    return monkeypatch


def _seed_tokens(primaries: int) -> None:
    """Начисляет primaries-запросов в process-wide bucket, не тратя их на резервацию.

    Первый `_begin_retry_request` создаёт bucket с sizing из окружения и сам начисляет
    primary; остальные досыпаются напрямую, иначе `_drive` съедал бы токены в резервации.
    """
    facade._begin_retry_request(RetryBudgetConfig(), 1).release_unused()
    bucket = facade._RUNTIME.bucket
    assert bucket is not None
    for _ in range(max(0, primaries - 1)):
        bucket.admit_primary()


def _drive(live: pytest.MonkeyPatch, backends: tuple[str, ...], outcome: Any, *, primaries: int = 5, path: str = "/v1/chat/completions") -> tuple[_Route, list[str]]:
    route, calls = _Route(path, "high"), []
    live.setattr(facade, "route_order", lambda *_args, **_kwargs: backends)

    def attempt(_route: Any, spec: Any, _body: Any, attempt: RouteAttempt) -> None:
        calls.append(spec.backend)
        outcome(len(calls), attempt)

    live.setattr(facade, "_attempt", attempt)
    _seed_tokens(primaries)
    facade._run_routes(route, [_spec(backend) for backend in backends], "seed", None)
    return route, calls


@pytest.mark.parametrize("status_code", [504, 500])
def test_live_run_routes_fails_over_on_non_allowlisted_status(
    live: pytest.MonkeyPatch, status_code: int
) -> None:
    """VER-012: 504/500 fail over через живой цикл, а не только 401/429/503."""

    def outcome(index: int, attempt: RouteAttempt) -> None:
        if index == 1:
            raise RouteRefusal(status_code)
        attempt.advance_to(AttemptPhase.COMMITTED)

    route, calls = _drive(live, ("alpha", "beta"), outcome)
    assert calls == ["alpha", "beta"]
    assert route.rejections == []


@pytest.mark.parametrize(("primaries", "expected"), [(1, ["alpha"]), (5, ["alpha", "beta"])])
def test_live_retry_budget_bounds_physical_attempts(
    live: pytest.MonkeyPatch, primaries: int, expected: list[str]
) -> None:
    """Cold-start: повторы открывает только накопленный retry_ratio 0.20."""

    def outcome(_index: int, _attempt: RouteAttempt) -> None:
        raise RouteRefusal(503)

    assert facade._retry_token(None) is False
    _route, calls = _drive(live, ("alpha", "beta", "gamma"), outcome, primaries=primaries)
    assert calls == expected


@pytest.mark.parametrize("status_code", [400, 401, 404, 405, 422, 451])
def test_client_4xx_refusal_keeps_circuit_closed(
    live: pytest.MonkeyPatch, status_code: int
) -> None:
    """F-005: клиентский 4xx — дефект запроса; circuit не открывается, маршрут жив."""
    live.setenv("BRIDGE_TRANSPORT_CIRCUIT_FAILURE_THRESHOLD", "1")

    def outcome(_index: int, _attempt: RouteAttempt) -> None:
        raise RouteRefusal(status_code)

    _first, first_calls = _drive(live, ("alpha",), outcome)
    _second, second_calls = _drive(live, ("alpha",), outcome)
    assert first_calls == second_calls == ["alpha"]


@pytest.mark.parametrize("status_code", [403, 429])
def test_route_health_4xx_refusal_opens_circuit(
    live: pytest.MonkeyPatch, status_code: int
) -> None:
    """Симметрия с model-georouter: 403 (блок региона/апстрима) и 429 (лимит) отравляют circuit."""
    live.setenv("BRIDGE_TRANSPORT_CIRCUIT_FAILURE_THRESHOLD", "1")

    def outcome(_index: int, _attempt: RouteAttempt) -> None:
        raise RouteRefusal(status_code)

    _first, first_calls = _drive(live, ("alpha",), outcome)
    second, second_calls = _drive(live, ("alpha",), outcome)
    assert first_calls == ["alpha"]
    assert second_calls == []
    # Circuit открыт: второго физического вызова нет, маршрут отсечён на входе.
    assert second.rejections == [(503, "route_unavailable")]


def test_transient_refusal_still_opens_circuit(live: pytest.MonkeyPatch) -> None:
    """Контроль к F-005: 5xx по-прежнему отравляет circuit и блокирует маршрут."""
    live.setenv("BRIDGE_TRANSPORT_CIRCUIT_FAILURE_THRESHOLD", "1")

    def outcome(_index: int, _attempt: RouteAttempt) -> None:
        raise RouteRefusal(503)

    _first, first_calls = _drive(live, ("alpha",), outcome)
    second, second_calls = _drive(live, ("alpha",), outcome)
    assert first_calls == ["alpha"]
    assert second_calls == []
    assert second.rejections == [(503, "route_unavailable")]


def test_open_circuit_does_not_consume_retry_token(live: pytest.MonkeyPatch) -> None:
    """F-006: открытый circuit пропускает маршрут, не списывая retry-токен."""
    reservation = _ReservationStub()
    live.setattr(facade, "_begin_retry_request", lambda *_args: reservation)
    live.setattr(facade, "route_order", lambda *_args, **_kwargs: ("alpha", "beta"))
    calls: list[str] = []

    def attempt(_route: Any, spec: Any, _body: Any, _attempt_obj: Any) -> None:
        calls.append(spec.backend)
        raise RouteRefusal(503)

    live.setattr(facade, "_attempt", attempt)
    candidate = RouteCandidate(route_id="beta", origin="claude-sonnet-4-5", node="beta", credential_scope="unscoped", identity="claude-sonnet-4-5:high")
    for _ in range(3):
        facade._breaker().record_failure(candidate, HealthDomain.ROUTE, time.monotonic())
    facade._run_routes(_Route(effort="high"), [_spec("alpha"), _spec("beta")], "seed", None)
    assert calls == ["alpha"]
    assert reservation.consumed == 0
    assert reservation.released == 1



    route = _Route()
    state = AttemptState(AttemptPhase.RESPONSE_HEADERS, False, False, 503)
    assert facade._replay_gate(route, state, RetryBudgetConfig()) is False


def test_replay_gate_blocks_after_downstream_commit(live: pytest.MonkeyPatch) -> None:
    route = _Route(effort="high")
    state = AttemptState(AttemptPhase.COMMITTED, True, True, 200)
    assert facade._replay_gate(route, state, RetryBudgetConfig()) is False


@pytest.mark.parametrize(
    ("path", "expected"),
    [("/v1/chat/completions?stream=true", True), ("/v1/responses?stream=true", False)],
)
def test_replay_gate_normalizes_query_string_endpoint(
    live: pytest.MonkeyPatch, path: str, expected: bool
) -> None:
    route = _Route(path, effort="high")
    state = AttemptState(AttemptPhase.RESPONSE_HEADERS, True, False, 504)
    assert facade._replay_gate(route, state, RetryBudgetConfig()) is expected



def test_pinned_effort_reaches_every_route_attempt(
    live: pytest.MonkeyPatch,
) -> None:
    """F-004: replay-effort закрепляется в payload и переживает смену маршрута."""
    route, seen = _Route(effort="high"), []
    live.setattr(facade, "route_order", lambda *_args, **_kwargs: ("alpha", "beta"))
    live.setattr(
        facade, "prepare_post_body",
        lambda item: SimpleNamespace(raw=b"{}", request=dict(item.request)),
    )

    def attempt(_route: Any, spec: Any, body: Any, _attempt_obj: Any) -> None:
        seen.append((spec.backend, body.request.get("reasoning_effort")))
        raise RouteRefusal(503)

    live.setattr(facade, "_attempt", attempt)
    _seed_tokens(5)
    facade._run_routes(route, [_spec("alpha"), _spec("beta")], "seed", None)
    assert seen == [("alpha", "high"), ("beta", "high")]


def test_pinned_effort_overrides_route_overlay_defaults() -> None:
    """F-004: route params не подменяют закреплённый effort на проводе."""
    routing, effort_policy = (
        import_module("core.http_post_routing"),
        import_module("core.effort_policy"),
    )
    request = effort_policy.pin_wire_effort({"model": "public", "messages": []}, "high")
    selected = {
        "upstream_model": "provider-id",
        "default_effort": "low",
        "params": {"reasoning_effort": "low", "temperature": 0.2},
    }
    prepared = routing.prepare_route_request(dict(request), selected, "public")
    assert prepared["reasoning_effort"] == "high"
    assert prepared["model"] == "provider-id"


# --- F-001 / F-002 / F-006: резервация на запрос, клиентский commit, 2xx-успех ---


class _ReservationStub:
    """Мнимая резервация: один consumable-токен и учёт вызовов."""

    def __init__(self) -> None:
        self.consumed, self.released = 0, 0

    def consume(self) -> bool:
        self.consumed += 1
        return self.consumed == 1

    def release_unused(self) -> int:
        self.released += 1
        return 0


def test_concurrent_requests_hold_independent_reservations(
    live: pytest.MonkeyPatch,
) -> None:
    """F-001: резервация принадлежит запросу, а не процессу."""
    reservations: list[_ReservationStub] = []
    seen: dict[int, list[str]] = {}
    lock, barrier = threading.Lock(), threading.Barrier(2, timeout=10)

    def begin(_config: RetryBudgetConfig, _routes: int) -> _ReservationStub:
        with lock:
            reservations.append(_ReservationStub())
            return reservations[-1]

    def attempt(route: Any, spec: Any, _body: Any, _attempt_obj: Any) -> None:
        with lock:
            seen.setdefault(id(route), []).append(spec.backend)
        if spec.backend == "alpha":
            barrier.wait()
            raise RouteRefusal(504)

    live.setattr(facade, "_begin_retry_request", begin)
    live.setattr(facade, "route_order", lambda *_args, **_kwargs: ("alpha", "beta"))
    live.setattr(facade, "_attempt", attempt)

    routes = [_Route(effort="high"), _Route(effort="high")]

    def run(route: _Route) -> None:
        facade._run_routes(route, [_spec("alpha"), _spec("beta")], "seed", None)

    threads = [threading.Thread(target=run, args=(route,)) for route in routes]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15)

    assert not any(thread.is_alive() for thread in threads)
    assert [seen[id(route)] for route in routes] == [["alpha", "beta"], ["alpha", "beta"]]
    assert len(reservations) == 2
    assert all(item.consumed == 1 and item.released == 1 for item in reservations)


def test_adapter_commit_before_failure_blocks_failover(
    live: pytest.MonkeyPatch,
) -> None:
    """F-002: реальный commit попытки запрещает повтор, даже если адаптер упал."""

    def outcome(_index: int, attempt: RouteAttempt) -> None:
        attempt.advance_to(AttemptPhase.COMMITTED)
        raise RouteRefusal(504)

    route, calls = _drive(live, ("alpha", "beta"), outcome)
    assert calls == ["alpha"]
    assert route.rejections == []


def test_handler_sink_start_marks_client_commit() -> None:
    """F-002: первый записанный клиенту байт фиксируется в состоянии попытки."""
    from server import _HandlerSink

    attempt = RouteAttempt(5.0, time.monotonic() + 5.0, time.monotonic)
    attempt.advance_to(AttemptPhase.SENDING)
    handler = SimpleNamespace(_transport_attempt=attempt, _headers_already_sent=True)
    _HandlerSink(handler, extra_headers=[]).start(200, [])
    assert attempt.state.committed is True


@pytest.mark.parametrize(
    ("status_code", "replay_allowed"),
    [(200, False), (201, False), (204, False), (299, False), (300, True)],
)
def test_any_2xx_status_is_success(status_code: int, replay_allowed: bool) -> None:
    """F-006: успех — любой 2xx int, а не только 200."""
    api = _load_api()
    if api is None:
        return
    decision = api[0](_facts(status_code=status_code))
    assert decision["replay_allowed"] is replay_allowed


def test_run_failover_stops_on_created_status() -> None:
    """F-006: 201 завершает failover как успех, второй попытки нет."""
    api = _load_api()
    if api is None:
        return
    calls: list[str] = []

    def attempt(model: str, effort: str) -> Mapping[str, object]:
        calls.append(model)
        return {"status_code": 201, "timed_out": False, "truncated": False}

    result = api[1](_facts(), attempt)
    assert result["physical_attempts"] == 1
    assert len(calls) == 1
