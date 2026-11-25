"""Unit tests for core/passthrough_facade.py (PR B8)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from core.passthrough_facade import _RUNTIME, _breaker, _emit_route_failure, _run_routes
from core.retry_control import CircuitPolicy, RouteCircuitBreaker
from core.route_attempts import RouteFailover, RouteRefusal
from core.route_cb_guard import get_route_cb
from core.route_cb_policy import FailureOutcome


def test_b8_breaker_and_run_routes_all_open(monkeypatch: Any) -> None:
    brk_legacy = RouteCircuitBreaker(CircuitPolicy(3, 30.0))
    monkeypatch.setattr(_RUNTIME, "route_cb", None)
    monkeypatch.setattr(_RUNTIME, "route_cb_config", None)
    monkeypatch.setattr(_RUNTIME, "breaker", brk_legacy)
    monkeypatch.setenv("BRIDGE_ROUTE_CB_ENABLED", "1")
    cb_on = _breaker()
    cb_live = get_route_cb(_RUNTIME)[0]
    assert cb_live is not None
    for _ in range(3):
        lease = cb_live.try_acquire(("p1", "m1", "b1"))
        cb_live.record_failure(("p1", "m1", "b1"), FailureOutcome(503), lease=lease)
    sink_calls: list[tuple[int, dict[str, str]]] = []
    sink = SimpleNamespace(start=lambda s, h: sink_calls.append((s, dict(h))), write=lambda p: None)
    route = SimpleNamespace(
        model_id="m1", model={"routing": {}}, alias_effort=None, request={"messages": []},
        handler=SimpleNamespace(connection=object(), _trace=SimpleNamespace(subagent_id="s-1")),
        reject=lambda *a: None,
        host=SimpleNamespace(_client_gone=lambda c: False, _trace_headers=lambda t: {}, _HandlerSink=lambda h, extra_headers=None: sink),
    )
    seen_models: list[dict[str, Any]] = []
    monkeypatch.setattr("core.passthrough_facade.prepare_post_body", lambda _route: b"{}")
    monkeypatch.setattr("core.passthrough_facade.route_order", lambda _mid, model, *_a: seen_models.append(model) or ("b1",))
    monkeypatch.setattr("core.passthrough_facade._eligible", lambda *a: True)
    monkeypatch.setattr("core.passthrough_facade.resolve_provider", lambda *a: "p1")
    _run_routes(route, [SimpleNamespace(backend="b1", credential_ref=None)], "seed", None)
    _emit_route_failure(route, RouteRefusal(429, (), b"{}"), [], [], None)
    monkeypatch.setenv("BRIDGE_ROUTE_CB_ENABLED", "0")
    assert (seen_models[0]["routing"]["enabled"], isinstance(cb_on, RouteCircuitBreaker), _breaker() is brk_legacy, len(sink_calls), sink_calls[0][0], "Retry-After" in sink_calls[0][1], sink_calls[1][0]) == (True, True, True, 2, 503, True, 429)


def test_b8_emit_route_failure_no_retry_after() -> None:
    rejected: list[tuple[int, str]] = []
    sink_calls: list[tuple[int, dict[str, str], bytes]] = []
    sink = SimpleNamespace(start=lambda s, h: sink_calls.append((s, dict(h), b"")), write=lambda p: sink_calls.append((-1, {}, p)))
    route_429 = SimpleNamespace(reject=lambda s, k, _m: rejected.append((s, k)), host=SimpleNamespace(_trace_headers=lambda _t: {}, _HandlerSink=lambda _h, extra_headers=None: sink), handler=SimpleNamespace(_trace=SimpleNamespace()))
    _emit_route_failure(route_429, RuntimeError("boom"), [], [], None)
    opt_refusal = [("b1", RouteRefusal(404, (), b"nf"), RouteFailover(statuses=frozenset({404})))]
    _emit_route_failure(route_429, RuntimeError("transient"), opt_refusal, [], None)
    q_skip = [("b2", RouteRefusal(429, (("Retry-After", "45"),), b"q"), RouteFailover())]
    _emit_route_failure(route_429, RuntimeError("quota"), opt_refusal, q_skip, None)
    assert (rejected, sink_calls[0][0], sink_calls[0][1]["Retry-After"], sink_calls[1][2]) == ([(503, "route_unavailable"), (503, "route_unavailable")], 429, "45", b"q")


def test_b8_run_routes_first_attempt_ignores_empty_retry_tokens(monkeypatch: Any) -> None:
    monkeypatch.setenv("BRIDGE_ROUTE_CB_ENABLED", "0")
    monkeypatch.setattr(_RUNTIME, "breaker", RouteCircuitBreaker(CircuitPolicy(5, 30.0)))
    seen: list[str] = []
    route = SimpleNamespace(
        model_id="m1", model={"routing": {}}, alias_effort=None, request={"messages": []},
        handler=SimpleNamespace(connection=object(), _trace=SimpleNamespace()),
        reject=lambda *a: seen.append("reject"), host=SimpleNamespace(_client_gone=lambda c: False),
    )
    monkeypatch.setattr("core.passthrough_facade.prepare_post_body", lambda _r: b"{}")
    monkeypatch.setattr("core.passthrough_facade.route_order", lambda *_a: ("b1", "b2"))
    monkeypatch.setattr("core.passthrough_facade._eligible", lambda *a: True)
    monkeypatch.setattr("core.passthrough_facade.resolve_provider", lambda *a: "p1")
    monkeypatch.setattr("core.passthrough_facade._retry_token", lambda _res: False)
    from core.route_attempts import PreSendTransientError
    monkeypatch.setattr("core.passthrough_facade._attempt", lambda _r, spec, _b, _a: seen.append(spec.backend) or (_ for _ in ()).throw(PreSendTransientError("b1")))
    _run_routes(route, [SimpleNamespace(backend="b1", credential_ref=None), SimpleNamespace(backend="b2", credential_ref=None)], "seed", None)
    assert seen == ["b1", "reject"]
