"""Unit tests for core/route_cb_auth.py (PR B6a)."""
from __future__ import annotations

from core.route_cb_auth import (
    bump_tuple_fail,
    clear_probe_flags,
    compute_retry_after_s,
    handle_auth_failure,
    open_provider_wide,
    record_unproven,
)
from core.route_cb_policy import FailureOutcome, RouteCBConfig, RouteProbeLease, _ProviderState, _TupleState


def test_b6a_clear_probe_and_bump_tuple() -> None:
    k1 = ("p1", "m1", "b1")
    tuples = {k1: _TupleState(probe_in_flight=True)}
    providers = {"p1": _ProviderState(probe_in_flight=True)}
    state = (tuples, providers, RouteCBConfig(failure_threshold=2, cooldown_s=60.0, window_s=100.0))
    clear_probe_flags(state, None)
    lease = RouteProbeLease(k1, provider_lease=True, tuple_lease=True)
    clear_probe_flags(state, lease)
    clear_probe_flags(state, lease)
    assert (providers["p1"].probe_in_flight, tuples[k1].probe_in_flight, lease.done) == (False, False, True)
    providers["p1"].probe_in_flight = tuples[k1].probe_in_flight = True
    clear_probe_flags(state, RouteProbeLease(k1, provider_lease=True, tuple_lease=False))
    assert (providers["p1"].probe_in_flight, tuples[k1].probe_in_flight) == (False, True)
    providers["p1"].probe_in_flight = True
    clear_probe_flags(state, RouteProbeLease(k1, provider_lease=False, tuple_lease=True))
    assert (providers["p1"].probe_in_flight, tuples[k1].probe_in_flight) == (True, False)
    clear_probe_flags(state, RouteProbeLease(("missing", "m", "b"), provider_lease=True, tuple_lease=True))


def test_b6a_bump_tuple_fail() -> None:
    k1 = ("p1", "m1", "b1")
    tuples: dict[tuple[str, str, str], _TupleState] = {}
    state = (tuples, {}, RouteCBConfig(failure_threshold=2, cooldown_s=60.0, window_s=100.0))
    bump_tuple_fail(state, k1, 1000.0, False)
    bump_tuple_fail(state, k1, 1101.0, False)
    assert (tuples[k1].failures, tuples[k1].open_until) == (1, None)
    bump_tuple_fail(state, k1, 1110.0, False)
    assert (tuples[k1].open_until, tuples[k1].failures) == (1170.0, 0)
    bump_tuple_fail(state, ("p1", "m2", "b1"), 1200.0, True)
    assert tuples[("p1", "m2", "b1")].open_until == 1260.0


def test_b6a_unproven_auth_and_retry_after() -> None:
    k1, k2 = ("pa", "m1", "b1"), ("pa", "m2", "b1")
    tuples: dict[tuple[str, str, str], _TupleState] = {}
    providers: dict[str, _ProviderState] = {"idle_p": _ProviderState(open_until=None)}
    state = (tuples, providers, RouteCBConfig(failure_threshold=3, cooldown_s=90.0, window_s=100.0))
    record_unproven(state, "pa", k1, 1000.0)
    record_unproven(state, "pa", k2, 1101.0)
    assert providers["pa"].open_until is None
    assert handle_auth_failure(state, k1, FailureOutcome(403, detail="model_not_found"), None, 1110.0) == "route_local"
    assert handle_auth_failure(state, k1, FailureOutcome(403, detail="permission_denied"), None, 1115.0) == "unproven"
    assert providers["pa"].open_until == 1205.0
    lease = RouteProbeLease(("pb", "m1", "b1"), provider_lease=True)
    assert handle_auth_failure(state, ("pb", "m1", "b1"), FailureOutcome(403, detail="other"), lease, 1120.0) == "unproven"
    assert (providers["pb"].open_until, compute_retry_after_s(tuples, providers, [k1, k2], 1204.2)) == (1210.0, 1)
    assert (compute_retry_after_s(tuples, providers, [("pb", "m1", "b1")], 1120.0), compute_retry_after_s(tuples, providers, [("idle_p", "m1", "b1")], 1000.0)) == (90, 1)
    open_provider_wide(state, "pa", 2000.0)
    assert handle_auth_failure(state, ("pc", "m1", "b1"), FailureOutcome(401, detail="invalid_api_key"), None, 3000.0) == "provider_wide"
    assert (providers["pa"].open_until, list(providers["pa"].unproven), providers["pc"].open_until) == (2090.0, [], 3090.0)
