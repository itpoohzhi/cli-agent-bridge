"""Контракты process-local retry budget и per-route circuit breaker."""

from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.retry_control import (
    CircuitPolicy,
    CircuitState,
    HealthDomain,
    PanicOpenContext,
    RetrySizing,
    RetryTokenBucket,
    RouteCandidate,
    RouteCircuitBreaker,
    validate_retry_sizing,
)


def _route(
    route_id: str = "route-a",
    *,
    identity: str = "model:effort",
    credential_scope: str = "cred-a",
) -> RouteCandidate:
    return RouteCandidate(
        route_id=route_id,
        origin="api.example",
        node=f"node-{route_id}",
        credential_scope=credential_scope,
        identity=identity,
    )


def _sizing() -> RetrySizing:
    return RetrySizing(capacity=2.0, retry_ratio=0.20, max_total_attempts=3)


def test_sizing_is_fail_closed() -> None:
    assert validate_retry_sizing(None).failover_enabled is False
    assert RetrySizing(capacity=2.0, retry_ratio=0.21, max_total_attempts=3).failover_enabled is False
    assert RetrySizing(capacity=2.0, retry_ratio=0.20, max_total_attempts=4).failover_enabled is False
    assert RetrySizing(capacity=-1.0, retry_ratio=0.20, max_total_attempts=3).failover_enabled is False
    assert RetrySizing.from_mapping({"capacity": 2.0}).failover_enabled is False
    assert _sizing().failover_enabled is True


def test_bucket_starts_empty_and_mints_fractional_credit() -> None:
    bucket = RetryTokenBucket(_sizing())
    assert bucket.tokens == 0.0
    for _ in range(4):
        bucket.admit_primary()
    assert bucket.reserve(eligible_routes=3).reserved == 0
    bucket.admit_primary()
    reservation = bucket.reserve(eligible_routes=3)
    assert reservation.reserved == 1
    assert reservation.max_total_attempts == 2
    assert reservation.consume() is True
    assert reservation.consume() is False
    assert bucket.tokens == 0.0


def test_upfront_reservation_is_capped_and_returned_once() -> None:
    bucket = RetryTokenBucket(_sizing())
    for _ in range(10):
        bucket.admit_primary()
    reservation = bucket.reserve(eligible_routes=20)
    assert reservation.reserved == 2
    assert reservation.max_total_attempts == 3
    assert reservation.consume() is True
    assert reservation.release_unused() == 1
    assert reservation.release_unused() == 0
    assert bucket.tokens == 1.0


def test_restart_and_reload_never_mint_tokens() -> None:
    bucket = RetryTokenBucket(_sizing())
    for _ in range(5):
        bucket.admit_primary()
    assert bucket.tokens == 1.0
    bucket.reconfigure(RetrySizing(capacity=5.0, retry_ratio=0.10, max_total_attempts=3))
    assert bucket.tokens == 1.0
    assert RetryTokenBucket(_sizing()).tokens == 0.0
    bucket.reconfigure(RetrySizing(capacity=5.0, retry_ratio=0.21, max_total_attempts=3))
    assert bucket.enabled is False
    assert bucket.tokens == 0.0


def test_breaker_tracks_health_domains_separately() -> None:
    breaker = RouteCircuitBreaker(CircuitPolicy(failure_threshold=1, cooldown_s=5.0))
    route = _route()
    breaker.record_failure(route, HealthDomain.ORIGIN, now=1.0)
    assert breaker.state(route, HealthDomain.ORIGIN, now=1.0) is CircuitState.OPEN
    assert breaker.state(route, HealthDomain.NODE, now=1.0) is CircuitState.CLOSED
    assert breaker.state(route, HealthDomain.CREDENTIAL_SCOPE, now=1.0) is CircuitState.CLOSED


def test_half_open_allows_one_concurrent_probe() -> None:
    breaker = RouteCircuitBreaker(CircuitPolicy(failure_threshold=1, cooldown_s=5.0))
    route = _route()
    breaker.record_failure(route, HealthDomain.ROUTE, now=1.0)
    assert breaker.try_acquire(route, now=5.9) is None
    probe = breaker.try_acquire(route, now=6.0)
    assert probe is not None
    assert breaker.state(route, HealthDomain.ROUTE, now=6.0) is CircuitState.HALF_OPEN
    assert breaker.try_acquire(route, now=6.0) is None
    assert probe.succeed(now=6.1) is True
    assert breaker.state(route, HealthDomain.ROUTE, now=6.1) is CircuitState.CLOSED


def test_credential_denial_blocks_sibling_routes_until_reset() -> None:
    breaker = RouteCircuitBreaker(CircuitPolicy(failure_threshold=3, cooldown_s=1.0))
    first = _route("route-a", credential_scope="shared")
    sibling = _route("route-b", credential_scope="shared")
    breaker.record_failure(first, HealthDomain.CREDENTIAL_SCOPE, now=1.0)
    assert breaker.try_acquire(sibling, now=100.0) is None
    breaker.reset(sibling, HealthDomain.CREDENTIAL_SCOPE)
    assert breaker.try_acquire(sibling, now=100.0) is not None


def test_panic_open_preserves_all_safety_fences() -> None:
    breaker = RouteCircuitBreaker(CircuitPolicy(failure_threshold=1, cooldown_s=30.0))
    safe = _route("safe")
    visited = _route("visited")
    wrong_identity = _route("wrong", identity="other")
    invalid_credential = RouteCandidate(
        "invalid", "api.example", "node-invalid", "cred-invalid", "model:effort",
        credential_valid=False,
    )
    disabled = RouteCandidate(
        "disabled", "api.example", "node-disabled", "cred-disabled", "model:effort",
        enabled=False,
    )
    candidates = (safe, visited, wrong_identity, invalid_credential, disabled)
    for candidate in candidates:
        breaker.record_failure(candidate, HealthDomain.ROUTE, now=1.0)
    context = PanicOpenContext(
        visited=frozenset({"visited"}),
        required_identity="model:effort",
        retry_tokens=1,
        attempts_remaining=2,
        min_routes=2,
    )
    assert breaker.panic_open(candidates, context, now=2.0) == (safe,)
    no_budget = PanicOpenContext(frozenset(), "model:effort", 0, 2, 2)
    assert breaker.panic_open(candidates, no_budget, now=2.0) == ()


def test_sizing_rejects_non_finite_values() -> None:
    for bad in (float("nan"), float("inf")):
        assert RetrySizing(capacity=bad, retry_ratio=0.1, max_total_attempts=3).failover_enabled is False
        assert RetrySizing(capacity=2.0, retry_ratio=bad, max_total_attempts=3).failover_enabled is False
    assert RetrySizing.from_mapping(
        {"capacity": 2.0, "retry_ratio": 0.1, "max_total_attempts": 2}
    ).failover_enabled is True
    assert RetryTokenBucket(None).enabled is False
    assert RetryTokenBucket(None).reserve(eligible_routes=3).reserved == 0


def test_bucket_caps_mint_release_and_single_route() -> None:
    bucket = RetryTokenBucket(_sizing())
    for _ in range(50):
        bucket.admit_primary()
    assert bucket.tokens == 2.0
    assert bucket.reserve(eligible_routes=1).reserved == 0
    reservation = bucket.reserve(eligible_routes=3)
    assert reservation.reserved == 2
    for _ in range(10):
        bucket.admit_primary()
    assert reservation.release_unused() == 2
    assert bucket.tokens == 2.0
    assert reservation.consume() is False


def test_failed_probe_reopens_circuit_for_new_cooldown() -> None:
    breaker = RouteCircuitBreaker(CircuitPolicy(failure_threshold=1, cooldown_s=5.0))
    route = _route()
    breaker.record_failure(route, HealthDomain.ROUTE, now=1.0)
    probe = breaker.try_acquire(route, now=6.0)
    assert probe is not None
    assert probe.fail(now=6.5) is True
    assert probe.succeed(now=6.6) is False
    assert breaker.state(route, HealthDomain.ROUTE, now=6.6) is CircuitState.OPEN
    assert breaker.try_acquire(route, now=11.4) is None
    assert breaker.try_acquire(route, now=11.5) is not None


def test_panic_open_skips_when_enough_routes_are_healthy() -> None:
    breaker = RouteCircuitBreaker(CircuitPolicy(failure_threshold=1, cooldown_s=30.0))
    healthy = (_route("h1"), _route("h2"))
    context = PanicOpenContext(frozenset(), "model:effort", 2, 2, 2)
    assert breaker.panic_open(healthy, context, now=1.0) == ()


def test_concurrent_reservations_never_oversell() -> None:
    bucket = RetryTokenBucket(_sizing())
    for _ in range(5):
        bucket.admit_primary()
    barrier = threading.Barrier(8)

    def reserve(_index: int) -> int:
        barrier.wait()
        return bucket.reserve(eligible_routes=3).reserved

    with ThreadPoolExecutor(max_workers=8) as pool:
        reserved = list(pool.map(reserve, range(8)))
    assert sum(reserved) == 1
    assert bucket.tokens == 0.0


def test_concurrent_admits_do_not_lose_credit() -> None:
    sizing = RetrySizing(capacity=100.0, retry_ratio=0.20, max_total_attempts=3)
    bucket = RetryTokenBucket(sizing)
    barrier = threading.Barrier(4)

    def admit(_index: int) -> None:
        barrier.wait()
        for _ in range(10):
            bucket.admit_primary()

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(admit, range(4)))
    assert bucket.tokens == 8.0


def test_concurrent_half_open_probe_is_single() -> None:
    breaker = RouteCircuitBreaker(CircuitPolicy(failure_threshold=1, cooldown_s=5.0))
    route = _route()
    breaker.record_failure(route, HealthDomain.ROUTE, now=1.0)
    barrier = threading.Barrier(8)

    def acquire(_index: int) -> object:
        barrier.wait()
        return breaker.try_acquire(route, now=6.0)

    with ThreadPoolExecutor(max_workers=8) as pool:
        probes = list(pool.map(acquire, range(8)))
    assert sum(probe is not None for probe in probes) == 1


def test_release_probe_frees_slot_without_healing() -> None:
    breaker = RouteCircuitBreaker(CircuitPolicy(failure_threshold=1, cooldown_s=5.0))
    route = _route()
    breaker.record_failure(route, HealthDomain.ROUTE, now=1.0)
    probe = breaker.try_acquire(route, now=6.0)
    assert probe is not None
    assert breaker.try_acquire(route, now=6.0) is None
    assert breaker.release_probe(probe) is True
    assert breaker.release_probe(probe) is False
    assert breaker.state(route, HealthDomain.ROUTE, now=6.0) is CircuitState.HALF_OPEN
    assert breaker.try_acquire(route, now=6.0) is not None


def test_panic_open_never_bypasses_credential_hard_block() -> None:
    breaker = RouteCircuitBreaker(CircuitPolicy(failure_threshold=1, cooldown_s=30.0))
    blocked = _route("blocked", credential_scope="denied")
    breaker.record_failure(blocked, HealthDomain.CREDENTIAL_SCOPE, now=1.0)
    context = PanicOpenContext(frozenset(), "model:effort", 2, 2, 1)
    assert breaker.panic_open((blocked,), context, now=2.0) == ()
