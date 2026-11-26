"""Wave 2 (REQ-001): single-route protection kill-switch and lock-free CB events."""

from __future__ import annotations

import concurrent.futures
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.route_cb import RouteCB
from core.route_cb_config import load_route_cb_config
from core.route_cb_policy import FailureOutcome, RouteCBConfig

if TYPE_CHECKING:
    from core.route_cb_decisions import RouteCBEvent

K: tuple[str, str, str] = ("p1", "m1", "b1")


def _cb(
    single_route_protect: bool = False,
    events_enabled: bool = True,
    event_sink: Callable[..., None] | None = None,
) -> tuple[list[float], RouteCB]:
    now = [1000.0]
    cfg = RouteCBConfig(
        enabled=True,
        failure_threshold=3,
        cooldown_s=90.0,
        window_s=300.0,
        single_route_protect=single_route_protect,
        events_enabled=events_enabled,
    )
    cb = RouteCB(cfg, clock=lambda: now[0], event_sink=event_sink)  # type: ignore[arg-type]
    return now, cb


def _cb_seq_strictly_increases(events: list[RouteCBEvent]) -> bool:
    seqs = [e.cb_seq for e in events]
    return seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


def test_config_defaults_and_single_route_protection_env() -> None:
    dflt = load_route_cb_config({})
    assert (dflt, dflt.single_route_protect, dflt.events_enabled) == (
        RouteCBConfig(),
        False,
        True,
    )
    for raw in ("true", "1", "yes", "on", "TRUE", "Yes"):
        cfg = load_route_cb_config({"BRIDGE_ROUTE_CB_SINGLE_ROUTE_PROTECTION": raw})
        assert cfg.single_route_protect is True, raw
    for raw in ("0", "false", "no", "off", "junk", ""):
        cfg = load_route_cb_config({"BRIDGE_ROUTE_CB_SINGLE_ROUTE_PROTECTION": raw})
        assert cfg.single_route_protect is False, raw
    legacy = load_route_cb_config(
        {
            "BRIDGE_ROUTE_CB_ENABLED": "0",
            "BRIDGE_ROUTE_CB_SINGLE_ROUTE_PROTECTION": "true",
        }
    )
    assert (legacy.enabled, legacy.single_route_protect, legacy.events_enabled) == (
        False,
        False,
        True,
    )


def test_config_events_env_parsing() -> None:
    for raw in ("0", "false", "no", "off", "FALSE", "Off"):
        cfg = load_route_cb_config({"BRIDGE_ROUTE_CB_EVENTS": raw})
        assert cfg.events_enabled is False, raw
    for raw in ("1", "true", "yes", "on", "junk", ""):
        cfg = load_route_cb_config({"BRIDGE_ROUTE_CB_EVENTS": raw})
        assert cfg.events_enabled is True, raw
    legacy = load_route_cb_config(
        {"BRIDGE_ROUTE_CB_ENABLED": "0", "BRIDGE_ROUTE_CB_EVENTS": "0"}
    )
    assert legacy.events_enabled is False


def test_default_config_keeps_baseline_contracts() -> None:
    events: list[RouteCBEvent] = []
    now, cb = _cb(event_sink=events.append)
    for _ in range(3):
        cb.record_failure(K, FailureOutcome(status=500, route_count=1))
    assert cb.try_acquire(K, route_count=1) is None
    assert cb.retry_after_s([K]) == 90
    assert [e.event for e in events] == ["open", "blocked"]


def test_single_route_protection_survives_transient_failures() -> None:
    events: list[RouteCBEvent] = []
    now, cb = _cb(single_route_protect=True, event_sink=events.append)
    for _ in range(4):
        cb.record_failure(K, FailureOutcome(status=500, route_count=1))
    cb.record_failure(K, FailureOutcome(error=TimeoutError(), route_count=1))
    lease = cb.try_acquire(K, route_count=1)
    assert lease is not None and lease.route_count == 1
    t = cb._tuples.get(K)
    assert t is None or t.open_until is None


def test_single_route_protection_events_monotonic() -> None:
    events: list[RouteCBEvent] = []
    now, cb = _cb(single_route_protect=True, event_sink=events.append)
    for _ in range(5):
        cb.record_failure(K, FailureOutcome(status=500, route_count=1))
    assert [e.event for e in events] == ["single_route_protection"] * 5
    assert all(e.retry_after_s == 0 and e.state == "protected" for e in events)
    assert _cb_seq_strictly_increases(events)
    assert cb.sink_errors == 0


def test_429_carveout_opens_tuple_despite_protection() -> None:
    events: list[RouteCBEvent] = []
    now, cb = _cb(single_route_protect=True, event_sink=events.append)
    for _ in range(3):
        cb.record_failure(K, FailureOutcome(status=429, route_count=1))
    t = cb._tuples[K]
    assert t.open_until is not None and t.open_until - now[0] == 90.0
    assert t.open_status == 429
    assert cb.try_acquire(K, route_count=1) is None
    assert cb.retry_after_s([K]) == 90
    assert [e.event for e in events] == ["open", "blocked"]
    assert events[0].state == "open" and events[0].retry_after_s == 90


def test_429_open_status_not_downgraded_by_concurrent_500_or_timeout() -> None:
    now, cb = _cb(single_route_protect=True)
    for _ in range(3):
        cb.record_failure(K, FailureOutcome(status=429, route_count=1))
    assert cb._tuples[K].open_status == 429
    cb.record_failure(K, FailureOutcome(status=500, route_count=2))
    cb.record_failure(K, FailureOutcome(error=TimeoutError(), route_count=2))
    assert cb._tuples[K].open_status == 429
    assert cb.try_acquire(K, route_count=1) is None


def test_500_open_status_escalates_to_429() -> None:
    now, cb = _cb(single_route_protect=True)
    for _ in range(3):
        cb.record_failure(K, FailureOutcome(status=500, route_count=2))
    assert cb._tuples[K].open_status == 500
    cb.record_failure(K, FailureOutcome(status=429, route_count=1))
    assert cb._tuples[K].open_status == 429
    assert cb.try_acquire(K, route_count=1) is None


def test_expired_429_cooldown_probe_fail_updates_open_status() -> None:
    now, cb = _cb(single_route_protect=True)
    for _ in range(3):
        cb.record_failure(K, FailureOutcome(status=429, route_count=1))
    now[0] += 91.0
    lease = cb.try_acquire(K, route_count=2)
    assert lease is not None and lease.tuple_lease
    cb.record_failure(K, FailureOutcome(status=500, route_count=2), lease=lease)
    t = cb._tuples[K]
    assert t.open_until == now[0] + 90.0 and t.open_status == 500
    fresh = cb.try_acquire(K, route_count=1)
    assert fresh is not None and not fresh.tuple_lease


def test_suppressed_expired_probe_clears_stale_open_status() -> None:
    now, cb = _cb(single_route_protect=True)
    for _ in range(3):
        cb.record_failure(K, FailureOutcome(status=429, route_count=1))
    now[0] += 91.0
    lease = cb.try_acquire(K, route_count=1)
    assert lease is not None and lease.tuple_lease
    res = cb.record_failure(K, FailureOutcome(status=500, route_count=1), lease=lease)
    assert res == "route_fail"
    assert cb._tuples[K].open_status is None


def test_auth_401_provider_wide_no_bypass() -> None:
    events: list[RouteCBEvent] = []
    now, cb = _cb(single_route_protect=True, event_sink=events.append)
    res = cb.record_failure(
        K, FailureOutcome(status=401, detail="invalid_api_key", route_count=1)
    )
    assert res == "provider_wide"
    assert cb._providers["p1"].open_until is not None
    assert cb.try_acquire(K, route_count=1) is None
    assert cb.retry_after_s([K]) == 90
    assert [e.event for e in events] == ["open", "blocked"]


def test_auth_401_route_local_no_bypass_on_single_route() -> None:
    events: list[RouteCBEvent] = []
    now, cb = _cb(single_route_protect=True, event_sink=events.append)
    for _ in range(3):
        cb.record_failure(
            K, FailureOutcome(status=401, detail="model_not_found", route_count=1)
        )
    t = cb._tuples[K]
    assert t.open_until is not None and t.open_status == 401
    p = cb._providers.get("p1")
    assert p is None or p.open_until is None
    assert cb.try_acquire(K, route_count=1) is None
    assert [e.event for e in events] == ["open", "blocked"]
    cb.record_success(K)
    assert t.open_until is None and t.open_status is None


def test_multi_route_failover_preserved() -> None:
    events: list[RouteCBEvent] = []
    now, cb = _cb(single_route_protect=True, event_sink=events.append)
    for _ in range(3):
        cb.record_failure(K, FailureOutcome(status=500, route_count=2))
    assert cb._tuples[K].open_until == now[0] + 90.0
    assert cb.try_acquire(K, route_count=2) is None
    assert [e.event for e in events] == ["open", "blocked"]


def test_acquire_single_route_protection_passes_open_tuple() -> None:
    events: list[RouteCBEvent] = []
    now, cb = _cb(single_route_protect=True, event_sink=events.append)
    for _ in range(3):
        cb.record_failure(K, FailureOutcome(status=500, route_count=2))
    lease = cb.try_acquire(K, route_count=1)
    assert lease is not None and not lease.tuple_lease and not lease.provider_lease
    assert [e.event for e in events] == ["open", "single_route_protection"]
    assert events[1].retry_after_s == 0 and events[1].state == "protected"


def test_half_open_probe_and_close_events() -> None:
    events: list[RouteCBEvent] = []
    now, cb = _cb(event_sink=events.append)
    for _ in range(3):
        cb.record_failure(K, FailureOutcome(status=500))
    now[0] += 90.0
    lease = cb.try_acquire(K)
    assert lease is not None and lease.tuple_lease
    cb.record_success(K, lease)
    assert cb.try_acquire(K) is not None
    assert [e.event for e in events] == ["open", "half_open_probe", "close"]
    assert events[1].state == "half_open" and events[2].state == "closed"


def test_events_disabled_gates_sink() -> None:
    events: list[RouteCBEvent] = []
    now, cb = _cb(
        single_route_protect=True, events_enabled=False, event_sink=events.append
    )
    for _ in range(3):
        cb.record_failure(K, FailureOutcome(status=500, route_count=1))
    assert events == [] and cb.sink_errors == 0
    assert cb.try_acquire(K, route_count=1) is not None


def test_lease_route_count_flows_into_suppression() -> None:
    now, cb = _cb(single_route_protect=True)
    for _ in range(4):
        lease = cb.try_acquire(K, route_count=1)
        assert lease is not None and lease.route_count == 1
        assert (
            cb.record_failure(K, FailureOutcome(status=500), lease=lease)
            == "route_fail"
        )
    t = cb._tuples.get(K)
    assert t is None or t.open_until is None
    assert cb.try_acquire(K, route_count=1) is not None


def test_event_sink_lock_free_no_deadlock() -> None:
    now = [1000.0]
    cfg = RouteCBConfig(failure_threshold=3, cooldown_s=90.0, single_route_protect=True)
    delivered: list[RouteCBEvent] = []

    def sink(ev: RouteCBEvent) -> None:
        cb.retry_after_s([K])  # instant deadlock if _emit_events ran under _lock
        delivered.append(ev)

    cb = RouteCB(cfg, clock=lambda: now[0], event_sink=sink)
    done: list[bool] = []

    def worker() -> None:
        for _ in range(3):
            cb.record_failure(K, FailureOutcome(status=500, route_count=1))
        done.append(True)

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    th.join(timeout=10.0)
    assert not th.is_alive() and done == [True]
    assert [e.event for e in delivered] == ["single_route_protection"] * 3


def test_throwing_sink_never_fails_request() -> None:
    def boom(ev: object) -> None:
        raise RuntimeError("sink down")

    now, cb = _cb(single_route_protect=True, event_sink=boom)
    for _ in range(3):
        assert (
            cb.record_failure(K, FailureOutcome(status=500, route_count=1))
            == "route_fail"
        )
    assert cb.try_acquire(K, route_count=1) is not None
    assert cb.sink_errors == 3


def test_concurrent_stress_128_threads() -> None:
    events: list[RouteCBEvent] = []
    sink_lock = threading.Lock()

    def sink(ev: RouteCBEvent) -> None:
        with sink_lock:
            events.append(ev)

    now, cb = _cb(single_route_protect=True, event_sink=sink)
    keys = [("p", f"m{i}", "b") for i in range(8)]
    barrier = threading.Barrier(128)

    def worker(i: int) -> None:
        barrier.wait()
        k = keys[i % len(keys)]
        for _ in range(20):
            lease = cb.try_acquire(k, route_count=i % 3)
            if lease is None or i % 2:
                cb.record_failure(k, FailureOutcome(status=500, route_count=i % 3))
            else:
                cb.record_success(k, lease)

    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as ex:
        list(ex.map(worker, range(128)))
    assert cb.sink_errors == 0
    assert _cb_seq_strictly_increases(events)


def test_route_cb_public_exports_preserved() -> None:
    import core.route_cb as route_cb_mod

    expected = (
        "FailureOutcome",
        "PROVIDER_AUTH_MARKERS",
        "ROUTE_LOCAL_MARKERS",
        "RouteCB",
        "RouteCBConfig",
        "RouteCircuitBreaker",
        "RouteProbeLease",
        "RouteTupleKey",
        "_with_retry_after",
        "classify_auth_failure",
        "is_client_gone",
        "is_recordable_failure",
        "is_route_cb_enabled",
        "load_route_cb_config",
        "resolve_provider",
    )
    assert set(expected) <= set(route_cb_mod.__all__)
    for name in expected:
        assert getattr(route_cb_mod, name, None) is not None
