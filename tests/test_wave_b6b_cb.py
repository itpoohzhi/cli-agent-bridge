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
    assert (lease3 is not None, cb.record_failure(k3, FailureOutcome(status=500), lease=lease3), cb.try_acquire(("pa", "m4", "b1")) is None) == (True, "route_fail", True)
    cb.record_success(k1)
    assert cb.try_acquire(("pa", "m4", "b1")) is not None
    cb.record_failure(k1, FailureOutcome(status=401, detail="invalid_api_key"))
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
    assert (reclaimed is not None, cb.release_lease(abandoned), cb.try_acquire(k1) is None) == (True, True, True)
    cb.record_success(k1, reclaimed)
    assert cb.try_acquire(k1) is not None
    assert cb.record_failure(k1, FailureOutcome(status=500), lease=abandoned) == "route_fail"
    assert cb.try_acquire(k1) is not None
    assert cb.release_lease(abandoned) is False


def test_b6b_ignored_sets_done() -> None:
    now, cb = _clock_cb()
    k1 = ("p2", "m1", "b1")
    for _ in range(3):
        cb.record_failure(k1, FailureOutcome(status=500))
    now[0] += 90.0
    lease_a = cb.try_acquire(k1)
    assert lease_a is not None and cb.record_failure(k1, FailureOutcome(status=400), lease=lease_a) == "ignored"
    assert lease_a.done is True
    lease_b = cb.try_acquire(k1)
    assert (lease_b is not None, cb.release_lease(lease_a), cb.try_acquire(k1) is None) == (True, False, True)
    cb.record_success(k1, lease_b)
    assert lease_b.done is True


def test_b6b_concurrent_half_open() -> None:
    import concurrent.futures
    now, cb = _clock_cb()
    k1 = ("p3", "m1", "b1")
    for _ in range(3):
        cb.record_failure(k1, FailureOutcome(status=500))
    now[0] += 90.0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        got = list(ex.map(lambda _: cb.try_acquire(k1), range(4)))
    assert sum(1 for x in got if x is not None) == 1


def test_b6b_abandoned_provider_probe() -> None:
    now, cb = _clock_cb()
    k1, k2, k3 = ("p4", "m1", "b1"), ("p4", "m2", "b1"), ("p4", "m3", "b1")
    cb.record_failure(k1, FailureOutcome(status=401, detail="invalid_api_key"))
    now[0] += 90.0
    abandoned = cb.try_acquire(k2)
    assert abandoned is not None and abandoned.provider_lease is True
    now[0] += 90.0
    reclaimed = cb.try_acquire(k3)
    assert (reclaimed is not None, cb.release_lease(abandoned), cb.try_acquire(k2) is None) == (True, True, True)
    cb.record_success(k3, reclaimed)
    assert cb.record_failure(k2, FailureOutcome(status=500), lease=abandoned) == "route_fail"
    assert cb.try_acquire(k3) is not None


def test_b6b_pre_outage_and_late_success_do_not_reclose_open_or_evict_probe() -> None:
    now, cb = _clock_cb()
    k1 = ("p5", "m1", "b1")
    stale_closed = cb.try_acquire(k1)
    for _ in range(3):
        cb.record_failure(k1, FailureOutcome(status=500))
    cb.record_success(k1, stale_closed)
    assert cb.try_acquire(k1) is None
    now[0] += 90.0
    probe_a = cb.try_acquire(k1)
    now[0] += 90.0
    probe_b = cb.try_acquire(k1)
    cb.record_success(k1, probe_a)
    assert (probe_b is not None, cb.try_acquire(k1) is None) == (True, True)
    cb.record_failure(k1, FailureOutcome(status=500), lease=probe_b)
    assert cb.try_acquire(k1) is None


def test_b6b_late_provider_success_and_auth_probe_clears_probes() -> None:
    now, cb = _clock_cb()
    k1, k2, k3 = ("p6", "m1", "b1"), ("p6", "m2", "b1"), ("p6", "m3", "b1")
    stale_closed = cb.try_acquire(k1)
    cb.record_failure(k1, FailureOutcome(status=401, detail="invalid_api_key"))
    cb.record_success(k1, stale_closed)
    assert cb.try_acquire(k2) is None
    now[0] += 90.0
    probe_a = cb.try_acquire(k2)
    now[0] += 90.0
    probe_b = cb.try_acquire(k3)
    cb.record_success(k2, probe_a)
    assert cb.try_acquire(k2) is None
    cb.record_failure(k3, FailureOutcome(status=401, detail="invalid_api_key"), lease=probe_b)
    assert (id(cb._providers["p6"]) not in cb._probes, cb.try_acquire(k2) is None) == (True, True)


def test_b6b_mismatched_key_lease_ignored_in_success_and_failure() -> None:
    now, cb = _clock_cb()
    k1, k_other = ("p7", "m1", "b1"), ("p8", "m2", "b1")
    for _ in range(3):
        cb.record_failure(k1, FailureOutcome(status=500))
    now[0] += 90.0
    lease1 = cb.try_acquire(k1)
    assert lease1 is not None and lease1.tuple_lease is True
    cb.record_failure(k_other, FailureOutcome(status=500), lease=lease1)
    cb.record_success(k_other, lease=lease1)
    assert (lease1.done, cb.try_acquire(k_other) is not None, cb.try_acquire(k1) is None) == (False, True, True)
    assert cb.release_lease(lease1) is True
