"""Unit tests for core/route_cb.py (PR B6b)."""
from __future__ import annotations

from core.route_cb import RouteCB
from core.route_cb_policy import FailureOutcome, RouteCBConfig


def _clock_cb() -> tuple[list[float], RouteCB]:
    now = [1000.0]
    cfg = RouteCBConfig(enabled=True, failure_threshold=3, cooldown_s=90.0, window_s=300.0)
    return now, RouteCB(cfg, clock=lambda: now[0])


def test_b6b_acquire_release_and_success() -> None:
    now, cb = _clock_cb()
    k1, k2 = ("p1", "m1", "b1"), ("p1", "m2", "b1")
    init_lease = cb.try_acquire(k1)
    assert RouteCB()._config == RouteCBConfig()
    assert (init_lease is not None, not init_lease.provider_lease if init_lease else False, not init_lease.tuple_lease if init_lease else False) == (True, True, True)
    assert cb.record_failure(k1) == "ignored"
    for _ in range(3):
        cb.record_failure(k1, FailureOutcome(status=500))
    assert (cb.try_acquire(k1) is None, cb.try_acquire(k2) is not None, cb.retry_after_s([k1])) == (True, True, 90)


def test_b6b_half_open_lease_and_reset() -> None:
    now, cb = _clock_cb()
    k1 = ("p1", "m1", "b1")
    for _ in range(3):
        cb.record_failure(k1, FailureOutcome(status=500))
    now[0] += 90.0
    lease = cb.try_acquire(k1)
    assert (lease is not None, lease.tuple_lease if lease else False, cb.try_acquire(k1) is None) == (True, True, True)
    assert (cb.release_lease(None), cb.release_lease(lease), cb.release_lease(lease)) == (False, True, False)
    cb.record_success(k1, cb.try_acquire(k1))
    assert (cb.try_acquire(k1) is not None, cb._tuples[k1].failures) == (True, 0)


def test_b6b_auth_unproven_prune_and_provider_wide() -> None:
    now, cb = _clock_cb()
    k1, k2 = ("pa", "m1", "b1"), ("pa", "m2", "b1")
    cb.record_failure(k1, FailureOutcome(status=403, detail="other"))
    assert len(cb._providers["pa"].unproven) == 1
    cb.record_success(k1)
    assert (cb.record_failure(k2, FailureOutcome(status=403, detail="other")), cb._providers["pa"].open_until) == ("unproven", None)
    assert (cb.record_failure(k1, FailureOutcome(status=400)), cb.record_failure(k1, FailureOutcome(status=401, detail="invalid_api_key")), cb.try_acquire(k2) is None) == ("ignored", "provider_wide", True)


def test_b6b_provider_half_open_probe_and_reopen() -> None:
    now, cb = _clock_cb()
    k1, k2, k3 = ("pa", "m1", "b1"), ("pa", "m2", "b1"), ("pa", "m3", "b1")
    cb.record_failure(k1, FailureOutcome(status=401, detail="invalid_api_key"))
    now[0] += 90.0
    lease = cb.try_acquire(k2)
    assert (lease is not None, lease.provider_lease if lease else False, cb.try_acquire(k3) is None) == (True, True, True)
    assert cb.record_failure(k2, FailureOutcome(status=403, detail="model_not_found"), lease=lease) == "route_local"
    lease3 = cb.try_acquire(k3)
    assert (lease3 is not None, cb.record_failure(k3, FailureOutcome(status=500), lease=lease3)) == (True, "route_fail")
    now[0] += 90.0
    cb.record_success(k3, cb.try_acquire(k3))
    assert cb.try_acquire(k1) is not None


def test_b6b_abandoned_probe_ttl_and_done_lease() -> None:
    now, cb = _clock_cb()
    k1 = ("p1", "m1", "b1")
    for _ in range(3):
        cb.record_failure(k1, FailureOutcome(status=500))
    now[0] += 90.0
    abandoned = cb.try_acquire(k1)
    assert (abandoned is not None and abandoned.tuple_lease, cb.try_acquire(k1) is None) == (True, True)
    now[0] += 90.0
    reclaimed = cb.try_acquire(k1)
    assert reclaimed is not None and cb.record_failure(k1, FailureOutcome(status=500), lease=abandoned) == "route_fail"
    assert cb.try_acquire(k1) is None
    assert cb.release_lease(abandoned) is False
