"""Unit tests for core/route_cb_guard.py (PR B7)."""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from core.quota_classifier import QuotaRules
from core.retry_control import CircuitPolicy, HealthDomain, RouteCandidate, RouteCircuitBreaker
from core.route_attempts import RouteFailover, RouteRefusal
from core.route_cb_guard import acquire_cb_guard, get_route_cb


def _new_runtime() -> SimpleNamespace:
    return SimpleNamespace(lock=threading.Lock(), bucket=None, sizing=None, breaker=None, route_cb=None, route_cb_config=None)


def test_b7_get_route_cb_and_guard_blocked() -> None:
    rt = _new_runtime()
    cb_off, leg_off = get_route_cb(rt, {"BRIDGE_ROUTE_CB_ENABLED": "0"})
    cb_on, leg_on = get_route_cb(rt, {"BRIDGE_ROUTE_CB_ENABLED": "1", "BRIDGE_ROUTE_CB_COOLDOWN_S": "60"})
    cb_reinit, _ = get_route_cb(rt, {"BRIDGE_ROUTE_CB_ENABLED": "1", "BRIDGE_ROUTE_CB_COOLDOWN_S": "120"})
    assert (cb_off is None, leg_off is not None, cb_on is not None, leg_on is None, cb_reinit is not cb_on) == (True, True, True, True, True)
    k1 = ("p1", "m1", "b1")
    cand = RouteCandidate("r1", "p1", "b1", "s", "id")
    t0 = time.monotonic()
    for _ in range(3):
        g = acquire_cb_guard((cb_reinit, None), cand, k1, t0)
        g.record_exception(TimeoutError("t"))
        g.record_exception(TimeoutError("ignored_after_done"))
        g.release()
    blocked_g = acquire_cb_guard((cb_reinit, None), cand, k1, t0 + 1.0)
    assert (blocked_g.blocked, blocked_g.blocked_key) == (True, k1)
    g2 = acquire_cb_guard((cb_reinit, None), cand, ("p1", "m2", "b1"), t0 + 1.0)
    g2.succeed(t0 + 2.0)
    g2.succeed(t0 + 3.0)
    assert (g2.done, g2.record_error(TimeoutError("after_done"), SimpleNamespace(), RouteFailover(), QuotaRules.from_config())) == (True, None)


def test_b7_guard_new_error_and_legacy_paths() -> None:
    rt = _new_runtime()
    cb, _ = get_route_cb(rt, {"BRIDGE_ROUTE_CB_ENABLED": "1"})
    cand = RouteCandidate("r1", "m1", "b1", "s", "id")
    k = ("p1", "m1", "b1")
    g = acquire_cb_guard((cb, None), cand, k, 100.0)
    seen_q: list[str] = []
    q_host = SimpleNamespace(_QUOTA_CB_CACHE=SimpleNamespace(record_429=lambda rid, **_kw: seen_q.append(rid)))
    rec = g.record_error(RouteRefusal(429, (), b'{"error":{"type":"insufficient_quota","message":"quota exceeded"}}'), q_host, RouteFailover(statuses=frozenset()), QuotaRules.from_config())
    assert (rec is not None and rec.status_code == 429 and int(dict(rec.response_headers).get("Retry-After", "0")) >= 60, len(seen_q)) == (True, 1)
    assert acquire_cb_guard((cb, None), cand, k, 100.0).record_error(RuntimeError("x"), SimpleNamespace(), RouteFailover(), QuotaRules.from_config()) is None
    leg = RouteCircuitBreaker(CircuitPolicy(1, 30.0))
    gl_ok = acquire_cb_guard((None, leg), cand, k, 200.0)
    gl_ok.succeed(201.0)
    from core.route_cb_guard import CBAttemptGuard
    CBAttemptGuard(cand, k, legacy=leg, probe=None).succeed(201.0)
    CBAttemptGuard(cand, k, legacy=leg, probe=None).record_exception(TimeoutError("x"))
    gl_exc = acquire_cb_guard((None, leg), cand, k, 202.0)
    gl_exc.record_exception(TimeoutError("x"))
    gl_err = acquire_cb_guard((None, leg), cand, k, 203.0)
    assert gl_err.record_error(RouteRefusal(500, (), b"err"), SimpleNamespace(), RouteFailover(), QuotaRules.from_config()).status_code == 500
    assert acquire_cb_guard((None, leg), cand, k, 204.0).blocked is True


def test_b7_legacy_error_matrix() -> None:
    cand = RouteCandidate("r1", "m1", "b1", "s", "id")
    k = ("p1", "m1", "b1")
    leg = RouteCircuitBreaker(CircuitPolicy(5, 30.0))
    g1 = acquire_cb_guard((None, leg), cand, k, 10.0)
    r429 = g1.record_error(RouteRefusal(429, (), b'{"error":{"message":"rate_limit_exceeded"}}'), SimpleNamespace(), RouteFailover(), QuotaRules.from_config())
    g2 = acquire_cb_guard((None, leg), RouteCandidate("r2", "m1", "b2", "s", "id2"), k, 11.0)
    r_slot = g2.record_error(RouteRefusal(404, (), b""), SimpleNamespace(), RouteFailover(statuses=frozenset({404})), QuotaRules.from_config())
    g3 = acquire_cb_guard((None, leg), RouteCandidate("r3", "m1", "b3", "s", "id3"), k, 12.0)
    g3.release()
    assert (r429 is not None and r429.status_code == 429, r_slot is not None and r_slot.status_code == 404, leg.try_acquire(RouteCandidate("r2", "m1", "b2", "s", "id2"), 12.0) is None, g3.done) == (True, True, True, True)
    leg.record_success(cand, HealthDomain.ROUTE)
