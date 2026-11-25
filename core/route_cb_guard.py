"""Per-attempt circuit-breaker guard and runtime lookup helpers."""
from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.quota_classifier import QuotaRules, classify_429
from core.retry_control import CircuitPolicy, CircuitProbe, HealthDomain, RouteCandidate, RouteCircuitBreaker
from core.route_attempts import RouteFailover, RouteRefusal
from core.route_cb import RouteCB
from core.route_cb_policy import (
    FailureOutcome,
    RouteProbeLease,
    RouteTupleKey,
    apply_quota_429,
    legacy_failure_action,
    load_route_cb_config,
    refusal_detail,
)

@dataclass(slots=True)
class CBAttemptGuard:
    """Unified per-attempt CB lifecycle guard for passthrough_facade."""
    candidate: RouteCandidate
    key: RouteTupleKey
    route_cb: RouteCB | None = None
    legacy: RouteCircuitBreaker | None = None
    lease: RouteProbeLease | None = None
    probe: CircuitProbe | None = None
    quota_refusal: RouteRefusal | None = None
    blocked_key: RouteTupleKey | None = None
    done: bool = False

    @property
    def blocked(self) -> bool:
        return self.blocked_key is not None or self.quota_refusal is not None

    def release(self) -> None:
        if self.done:
            return
        self.done = True
        if self.route_cb is not None:
            self.route_cb.release_lease(self.lease)
        elif self.legacy is not None and self.probe is not None:
            self.legacy.release_probe(self.probe)

    def succeed(self, now: float) -> None:
        if self.done:
            return
        self.done = True
        if self.route_cb is not None:
            self.route_cb.record_success(self.key, self.lease)
        elif self.legacy is not None and self.probe is not None:
            self.legacy.record_success(self.candidate, HealthDomain.ROUTE)
            self.legacy.record_success(self.candidate, HealthDomain.CREDENTIAL_SCOPE)
            self.probe.succeed(now)

    def record_exception(self, exc: BaseException) -> None:
        if self.done:
            return
        self.done = True
        if self.route_cb is not None:
            self.route_cb.record_failure(self.key, FailureOutcome(error=exc), self.lease)
        elif self.legacy is not None and self.probe is not None:
            self.legacy.release_probe(self.probe)

    def record_error(self, error: BaseException, host: Any, failover: RouteFailover, quota_rules: QuotaRules) -> RouteRefusal | None:
        if self.done:
            return None
        self.done = True
        if self.legacy is not None:
            return self._record_legacy_error(error, host, failover, quota_rules)
        recorded, status, detail = None, None, ""
        if isinstance(error, RouteRefusal):
            recorded, status = error, error.status_code
            detail = refusal_detail(error)
            if status == 429:
                qdec = classify_429(dict(error.response_headers), error.response_body, quota_rules)
                if qdec.is_quota:
                    recorded = apply_quota_429(error, qdec, host, f"{self.candidate.origin}@{self.candidate.route_id}")
        if self.route_cb is not None:
            self.route_cb.record_failure(self.key, FailureOutcome(status=status, error=error, detail=detail), self.lease)
        return recorded

    def _record_legacy_error(self, error: BaseException, host: Any, failover: RouteFailover, quota_rules: QuotaRules) -> RouteRefusal | None:
        now_err = time.monotonic()
        recorded = error if isinstance(error, RouteRefusal) else None
        action = legacy_failure_action(error, failover)
        if action == "quota":
            qdec = classify_429(dict(error.response_headers), error.response_body, quota_rules)
            if qdec.is_quota:
                self.legacy.record_failure(self.candidate, HealthDomain.CREDENTIAL_SCOPE, now_err, cooldown_s=qdec.reset_s, reason=qdec.reason)
                recorded = apply_quota_429(error, qdec, host, f"{self.candidate.origin}@{self.candidate.route_id}")
            else:
                self.legacy.record_failure(self.candidate, HealthDomain.ROUTE, now_err)
        elif action == "slot_refusal":
            self.legacy.record_failure(self.candidate, HealthDomain.CREDENTIAL_SCOPE, now_err, cooldown_s=quota_rules.cooldown_default_s, reason=f"http_{error.status_code}_slot_refusal")
        elif action == "route":
            self.legacy.record_failure(self.candidate, HealthDomain.ROUTE, now_err)
        if self.probe is not None:
            self.legacy.release_probe(self.probe)
        return recorded


def get_route_cb(runtime: Any, env: Mapping[str, str] | None = None) -> tuple[RouteCB | None, RouteCircuitBreaker | None]:
    """Select active RouteCB or legacy RouteCircuitBreaker singleton for runtime."""
    cfg = load_route_cb_config(env)
    with runtime.lock:
        if cfg.enabled:
            if getattr(runtime, "route_cb", None) is None or getattr(runtime, "route_cb_config", None) != cfg:
                runtime.route_cb, runtime.route_cb_config = RouteCB(cfg), cfg
            return runtime.route_cb, None
        policy = CircuitPolicy(cfg.failure_threshold, cfg.cooldown_s)
        runtime.breaker = runtime.breaker or RouteCircuitBreaker(policy)
        return None, runtime.breaker


def acquire_cb_guard(breakers: tuple[RouteCB | None, RouteCircuitBreaker | None], candidate: RouteCandidate, key: RouteTupleKey, now: float) -> CBAttemptGuard:
    """Acquire either RouteCB lease or legacy RouteCircuitBreaker probe."""
    route_cb, legacy = breakers
    if route_cb is not None:
        lease = route_cb.try_acquire(key, now)
        return CBAttemptGuard(candidate=candidate, key=key, route_cb=route_cb, lease=lease, blocked_key=key if lease is None else None, done=lease is None)
    probe = legacy.try_acquire(candidate, now)
    if probe is not None:
        return CBAttemptGuard(candidate=candidate, key=key, legacy=legacy, probe=probe)
    blocked, remaining_s, _reason = legacy.quota_block_info(candidate, now)
    refusal = RouteRefusal(429, (("Retry-After", str(max(60, int(remaining_s)))),), b'{"error":{"type":"rate_limit_error","message":"slot in quota cooldown"}}') if blocked else None
    return CBAttemptGuard(candidate=candidate, key=key, legacy=legacy, quota_refusal=refusal, blocked_key=key, done=True)
