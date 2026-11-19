"""Process-local бюджет повторов и per-route circuit breaker без I/O."""

from __future__ import annotations

import math
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import Enum
from typing import Final, TypeGuard

MAX_TOTAL_ATTEMPTS_LIMIT: Final[int] = 3
MAX_RETRY_RATIO: Final[float] = 0.20


def _is_finite_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True, slots=True)
class RetrySizing:
    """Sizing бюджета; любое сомнение трактуется как failover disabled."""

    capacity: float
    retry_ratio: float
    max_total_attempts: int

    @property
    def failover_enabled(self) -> bool:
        return (
            _is_finite_number(self.capacity) and self.capacity > 0 and _is_finite_number(self.retry_ratio)
            and 0 < self.retry_ratio <= MAX_RETRY_RATIO and type(self.max_total_attempts) is int
            and 1 <= self.max_total_attempts <= MAX_TOTAL_ATTEMPTS_LIMIT
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, object] | None) -> RetrySizing:
        if not isinstance(data, Mapping):
            return _DISABLED_SIZING
        capacity, ratio, attempts = data.get("capacity"), data.get("retry_ratio"), data.get("max_total_attempts")
        if not _is_finite_number(capacity) or not _is_finite_number(ratio) or type(attempts) is not int:
            return _DISABLED_SIZING
        return cls(float(capacity), float(ratio), attempts)

_DISABLED_SIZING: Final[RetrySizing] = RetrySizing(0.0, 0.0, 0)

def validate_retry_sizing(sizing: RetrySizing | Mapping[str, object] | None) -> RetrySizing:
    """Нормализует sizing fail-closed: невалидный вход отключает failover."""
    if isinstance(sizing, RetrySizing):
        return sizing
    return RetrySizing.from_mapping(sizing) if isinstance(sizing, Mapping) else _DISABLED_SIZING

class RetryReservation:
    """Upfront-резервация токенов одного logical request."""

    def __init__(self, bucket: RetryTokenBucket, reserved: int, generation: int) -> None:
        self._bucket: RetryTokenBucket = bucket
        self._reserved, self._remaining = reserved, reserved
        self._generation, self._released = generation, False

    @property
    def reserved(self) -> int:
        return self._reserved

    @property
    def max_total_attempts(self) -> int:
        return 1 + self._reserved

    def consume(self) -> bool:
        with self._bucket._lock:
            available = not self._released and self._generation == self._bucket._generation and self._remaining > 0
            self._remaining -= 1 if available else 0
            return available

    def release_unused(self) -> int:
        """Возвращает неиспользованные токены ровно один раз."""
        with self._bucket._lock:
            if self._released or self._generation != self._bucket._generation:
                self._released = True
                return 0
            unused, self._remaining, self._released = self._remaining, 0, True
            self._bucket._credit(Decimal(unused))
            return unused

class RetryTokenBucket:
    """Владелец токенов: старт пустой, restart/reload токены не досыпает."""

    def __init__(self, sizing: RetrySizing | Mapping[str, object] | None) -> None:
        self._sizing: RetrySizing = validate_retry_sizing(sizing)
        self._tokens: Decimal = Decimal(0)
        self._generation: int = 0
        self._lock: threading.Lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._sizing.failover_enabled

    @property
    def tokens(self) -> float:
        return float(self._tokens)

    def _credit(self, amount: Decimal) -> None:
        if self.enabled:
            self._tokens = min(Decimal(str(self._sizing.capacity)), self._tokens + amount)

    def admit_primary(self) -> None:
        """Начисляет дробный запас за новый logical request."""
        with self._lock:
            self._credit(Decimal(str(self._sizing.retry_ratio)))

    def reserve(self, eligible_routes: int) -> RetryReservation:
        """Списывает upfront не больше attempt-cap, маршрутов и целых токенов."""
        with self._lock:
            reserved = 0
            if self.enabled and type(eligible_routes) is int:
                whole = int(self._tokens.to_integral_value(rounding=ROUND_FLOOR))
                reserved = max(0, min(whole, eligible_routes - 1, self._sizing.max_total_attempts - 1))
            self._tokens -= Decimal(reserved)
            return RetryReservation(self, reserved, self._generation)

    def reconfigure(self, sizing: RetrySizing | Mapping[str, object] | None) -> None:
        """Применяет новый sizing без досыпки; резервации инвалидируются."""
        with self._lock:
            self._generation += 1
            self._sizing = validate_retry_sizing(sizing)
            self._tokens = Decimal(0) if not self.enabled else min(Decimal(str(self._sizing.capacity)), self._tokens)

class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class HealthDomain(str, Enum):
    ROUTE = "route"
    ORIGIN = "origin"
    NODE = "node"
    CREDENTIAL_SCOPE = "credential_scope"

@dataclass(frozen=True, slots=True)
class CircuitPolicy:
    failure_threshold: int = 3
    cooldown_s: float = 30.0

    @property
    def is_valid(self) -> bool:
        return type(self.failure_threshold) is int and self.failure_threshold >= 1 and _is_finite_number(self.cooldown_s) and self.cooldown_s >= 0

@dataclass(frozen=True, slots=True)
class RouteCandidate:
    route_id: str
    origin: str
    node: str
    credential_scope: str
    identity: str
    credential_valid: bool = True
    enabled: bool = True

@dataclass(frozen=True, slots=True)
class PanicOpenContext:
    visited: frozenset[str]
    required_identity: str
    retry_tokens: int
    attempts_remaining: int
    min_routes: int

@dataclass(slots=True)
class _DomainHealth:
    failures: int = 0
    opened_at: float | None = None
    probe_in_flight: bool = False
    hard_blocked: bool = False
    cooldown_until: float | None = None
    reason: str = ""

_HealthKey = tuple[HealthDomain, str]

def _route_is_usable(route: RouteCandidate) -> bool:
    fields = (route.route_id, route.origin, route.node, route.credential_scope, route.identity)
    return route.enabled and route.credential_valid and all(fields)

class CircuitProbe:
    """Разрешение на попытку; для HALF_OPEN владеет единственным probe."""

    def __init__(self, breaker: RouteCircuitBreaker, probed: tuple[_HealthKey, ...]) -> None:
        self._breaker: RouteCircuitBreaker = breaker
        self._probed: tuple[_HealthKey, ...] = probed
        self._done: bool = False

    def succeed(self, now: float) -> bool:
        return self._breaker._finish_probe(self, now, success=True)

    def fail(self, now: float) -> bool:
        return self._breaker._finish_probe(self, now, success=False)

class RouteCircuitBreaker:
    """Владелец здоровья по доменам route/origin/node/credential_scope."""

    def __init__(self, policy: CircuitPolicy) -> None:
        self._policy: CircuitPolicy = policy if isinstance(policy, CircuitPolicy) else CircuitPolicy(0, -1.0)
        self._health: dict[_HealthKey, _DomainHealth] = {}
        self._lock: threading.Lock = threading.Lock()

    @staticmethod
    def _key(route: RouteCandidate, domain: HealthDomain) -> _HealthKey:
        values = {HealthDomain.ROUTE: route.route_id, HealthDomain.ORIGIN: route.origin, HealthDomain.NODE: route.node, HealthDomain.CREDENTIAL_SCOPE: route.credential_scope}
        return (domain, values[domain])

    def _entries(self, route: RouteCandidate) -> list[_DomainHealth]:
        return [entry for domain in HealthDomain if (entry := self._health.get(self._key(route, domain)))]

    def _cooldown_deadline(self, entry: _DomainHealth) -> float:
        if entry.cooldown_until is not None:
            return entry.cooldown_until
        return (entry.opened_at or 0.0) + self._policy.cooldown_s

    def state(self, route: RouteCandidate, domain: HealthDomain, now: float) -> CircuitState:
        entry = self._health.get(self._key(route, domain))
        if entry is None or (entry.opened_at is None and not entry.hard_blocked and not entry.probe_in_flight):
            return CircuitState.CLOSED
        if entry.hard_blocked or not _is_finite_number(now) or entry.opened_at is None:
            return CircuitState.HALF_OPEN if entry.probe_in_flight and not entry.hard_blocked else CircuitState.OPEN
        if entry.probe_in_flight or now >= self._cooldown_deadline(entry):
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    def record_failure(
        self,
        route: RouteCandidate,
        domain: HealthDomain,
        now: float,
        *,
        cooldown_s: float | None = None,
        reason: str = "",
    ) -> None:
        with self._lock:
            entry = self._health.setdefault(self._key(route, domain), _DomainHealth())
            entry.failures += 1
            entry.probe_in_flight = False
            if cooldown_s is not None and _is_finite_number(cooldown_s) and cooldown_s > 0:
                entry.opened_at = float(now)
                entry.cooldown_until = float(now) + float(cooldown_s)
                entry.reason = reason
                return
            if domain is HealthDomain.CREDENTIAL_SCOPE:
                entry.hard_blocked = True
                entry.opened_at = float(now)
                entry.reason = reason
            elif entry.failures >= self._policy.failure_threshold:
                entry.opened_at = float(now)
                entry.cooldown_until = None
                entry.reason = reason

    def record_success(self, route: RouteCandidate, domain: HealthDomain) -> None:
        with self._lock:
            entry = self._health.get(self._key(route, domain))
            if entry is not None and not entry.hard_blocked and not entry.probe_in_flight:
                entry.failures, entry.opened_at, entry.cooldown_until, entry.reason = 0, None, None, ""

    def reset(self, route: RouteCandidate, domain: HealthDomain) -> None:
        with self._lock:
            _ = self._health.pop(self._key(route, domain), None)

    def quota_block_info(self, route: RouteCandidate, now: float) -> tuple[bool, float, str]:
        """Возвращает `(blocked, remaining_s, reason)` для домена `CREDENTIAL_SCOPE`."""
        with self._lock:
            entry = self._health.get(self._key(route, HealthDomain.CREDENTIAL_SCOPE))
            if entry is None or (entry.opened_at is None and not entry.hard_blocked):
                return False, 0.0, ""
            if entry.hard_blocked:
                return True, max(60.0, self._policy.cooldown_s), entry.reason
            if not _is_finite_number(now) or entry.opened_at is None:
                return True, max(60.0, self._policy.cooldown_s), entry.reason
            remaining = self._cooldown_deadline(entry) - now
            if remaining > 0:
                return True, remaining, entry.reason
            return False, 0.0, ""

    def try_acquire(self, route: RouteCandidate, now: float) -> CircuitProbe | None:
        with self._lock:
            if not self._policy.is_valid or not _is_finite_number(now) or not _route_is_usable(route):
                return None
            probed: list[_HealthKey] = []
            for domain in HealthDomain:
                key = self._key(route, domain)
                entry = self._health.get(key)
                if entry is None or entry.opened_at is None and not entry.hard_blocked:
                    continue
                if entry.hard_blocked or entry.probe_in_flight or entry.opened_at is None or now < self._cooldown_deadline(entry):
                    return None
                probed.append(key)
            for key in probed:
                self._health[key].probe_in_flight = True
            return CircuitProbe(self, tuple(probed))

    def release_probe(self, probe: CircuitProbe) -> bool:
        """Освобождает probe без оздоровления: домен остаётся OPEN до cooldown."""
        return self._finish_probe(probe, 0.0, success=None)

    def _finish_probe(self, probe: CircuitProbe, now: float, success: bool | None) -> bool:
        with self._lock:
            if probe._done or (success is not None and not _is_finite_number(now)):
                return False
            probe._done = True
            for key in probe._probed:
                entry = self._health.get(key)
                if entry is None or not entry.probe_in_flight:
                    continue
                entry.probe_in_flight = False
                if success is not None:
                    entry.failures = 0 if success else self._policy.failure_threshold
                    entry.opened_at = None if success else float(now)
                    if success:
                        entry.cooldown_until = None
                        entry.reason = ""
            return True

    def _is_available(self, route: RouteCandidate, now: float) -> bool:
        return all(not e.hard_blocked and not e.probe_in_flight and (e.opened_at is None or now >= self._cooldown_deadline(e)) for e in self._entries(route))

    def _is_panic_eligible(self, route: RouteCandidate, now: float) -> bool:
        return not self._is_available(route, now) and all(not e.hard_blocked and not e.probe_in_flight for e in self._entries(route))

    def panic_open(self, candidates: Iterable[RouteCandidate], context: PanicOpenContext, now: float) -> tuple[RouteCandidate, ...]:
        """Выбирает безопасные непройденные маршруты, не обходя бюджет и fences."""
        cap, safe = self._panic_cap(context, now), self._safe_candidates(candidates, context)
        if cap <= 0 or sum(self._is_available(route, now) for route in safe) >= context.min_routes:
            return ()
        return tuple(route for route in safe if self._is_panic_eligible(route, now))[:cap]

    def _panic_cap(self, context: PanicOpenContext, now: float) -> int:
        counts = (context.retry_tokens, context.attempts_remaining, context.min_routes)
        if not self._policy.is_valid or not _is_finite_number(now) or not context.required_identity or any(type(item) is not int for item in counts):
            return 0
        return min(context.retry_tokens, context.attempts_remaining) if context.min_routes > 0 else 0

    def _safe_candidates(self, candidates: Iterable[RouteCandidate], context: PanicOpenContext) -> list[RouteCandidate]:
        by_id: dict[str, RouteCandidate] = {}
        for route in candidates:
            _ = by_id.setdefault(route.route_id, route)
        return [route for route in by_id.values() if route.route_id not in context.visited and _route_is_usable(route) and route.identity == context.required_identity]
