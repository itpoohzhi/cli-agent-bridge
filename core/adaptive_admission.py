from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import final


@final
class Phase(str, Enum):
    OPEN = "open"
    SHEDDING = "shedding"
    RECOVERING = "recovering"


@final
class OutcomeKind(str, Enum):
    OK = "ok"
    CAPACITY_EXHAUSTED = "capacity_exhausted"
    CANCELLED = "cancelled"
    ERROR = "error"


@final
@dataclass(frozen=True, slots=True)
class AdmissionConfig:
    backend_ceiling: int = 16
    init_limit: int = 8
    parent_init_limit: int = 8
    max_keys: int = 128
    overflow_limit: int = 1
    base_cooldown_s: float = 1.0
    max_cooldown_s: float = 60.0
    stale_pin_ttl_s: float = 300.0
    ewma_gate_ms: float = 90000.0


@final
@dataclass(frozen=True, slots=True)
class AdmissionKey:
    route: str
    backend: str
    model: str


def canonical_key(route: str, backend: str, model: str) -> AdmissionKey:
    return AdmissionKey(route.strip().lower()[:32], backend.strip().lower()[:32], model.strip().lower()[:64])


@final
@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    admitted: bool
    ticket_id: int
    status_code: int
    retry_after_s: float
    reason: str
    bucket_key: AdmissionKey
    overflowed: bool = False


@final
@dataclass(frozen=True, slots=True)
class AdmissionSnapshot:
    capacity_hits_60s: int
    total_in_flight: int
    shed_total: int
    admitted_total: int
    pinned_buckets: int
    overflow_active: bool
    parent_limits: tuple[tuple[str, int], ...]
    bucket_limits: tuple[tuple[AdmissionKey, int], ...]


@final
@dataclass(slots=True)
class KeyState:
    limit: int
    last_active_s: float
    in_flight: int = 0
    phase: Phase = Phase.OPEN
    cooldown_until_s: float = 0.0
    probe_in_flight: bool = False
    failure_streak: int = 0
    ok_window: int = 0
    ttfc_ewma_ms: float = 0.0


@final
@dataclass(slots=True)
class ParentState:
    limit: int
    in_flight: int = 0


@final
@dataclass(frozen=True, slots=True)
class AdmissionTicket:
    state: KeyState
    parent: ParentState
    probe: bool


@final
class AdaptiveAdmissionRegistry:
    def __init__(self, config: AdmissionConfig | None = None) -> None:
        self._config = config or AdmissionConfig()
        self._ceiling = max(1, min(16, self._config.backend_ceiling))
        self._max_keys = max(1, min(128, self._config.max_keys))
        self._overflow_cap = 1
        self._buckets: OrderedDict[AdmissionKey, KeyState] = OrderedDict()
        self._parents: dict[str, ParentState] = {}
        self._tickets: dict[int, AdmissionTicket] = {}
        self._overflow = KeyState(limit=self._overflow_cap, last_active_s=0.0)
        self._request_seq = 0
        self._ticket_seq = 0
        self._shed_total = 0
        self._admitted_total = 0
        self._capacity_current = 0
        self._capacity_previous = 0
        self._capacity_bucket_start_s = 0.0

    def _parent_for(self, backend: str) -> ParentState:
        parent = self._parents.get(backend)
        if parent is None:
            initial = max(1, min(self._config.parent_init_limit, self._ceiling))
            parent = ParentState(limit=initial)
            self._parents[backend] = parent
        return parent

    def _can_evict(self, state: KeyState, now_s: float) -> bool:
        if state.in_flight != 0:
            return False
        if now_s - state.last_active_s >= self._config.stale_pin_ttl_s:
            return True
        return state.phase is Phase.OPEN and state.limit >= self._config.init_limit

    def _bucket_for(self, key: AdmissionKey, now_s: float) -> tuple[KeyState, bool]:
        state = self._buckets.get(key)
        if state is not None:
            self._buckets.move_to_end(key)
            return state, False
        victim: AdmissionKey | None = None
        if len(self._buckets) >= self._max_keys:
            for candidate, candidate_state in self._buckets.items():
                if self._can_evict(candidate_state, now_s):
                    victim = candidate
                    break
            if victim is None:
                self._overflow.last_active_s = now_s
                return self._overflow, True
            del self._buckets[victim]
        initial = max(1, min(self._config.init_limit, self._ceiling))
        state = KeyState(limit=initial, last_active_s=now_s)
        self._buckets[key] = state
        return state, False

    def _refresh_phase(self, state: KeyState, now_s: float) -> None:
        if state.phase is Phase.SHEDDING and now_s >= state.cooldown_until_s:
            state.phase = Phase.RECOVERING
            state.probe_in_flight = False

    def _retry_after(self, window_s: float) -> float:
        value = (self._request_seq * 1103515245 + 12345) % 501
        factor = 0.75 + float(value) / 1000.0
        return max(0.001, window_s * factor)

    def _reject(self, key: AdmissionKey, reason: str, window_s: float, overflowed: bool = False) -> AdmissionDecision:
        self._shed_total += 1
        return AdmissionDecision(False, 0, 503, self._retry_after(window_s), reason, key, overflowed)

    def acquire(self, key: AdmissionKey, now_s: float, *, external_held: int = 0) -> AdmissionDecision:
        self._request_seq += 1
        parent = self._parent_for(key.backend)
        if parent.in_flight + max(0, external_held) >= min(parent.limit, self._ceiling):
            return self._reject(key, "backend_ceiling", self._config.base_cooldown_s)
        state, overflowed = self._bucket_for(key, now_s)
        self._refresh_phase(state, now_s)
        if state.phase is Phase.SHEDDING:
            return self._reject(key, "cooldown", max(0.001, state.cooldown_until_s - now_s), overflowed)
        if state.phase is Phase.RECOVERING and state.probe_in_flight:
            return self._reject(key, "recovering_probe", self._config.base_cooldown_s, overflowed)
        if state.in_flight >= min(state.limit, parent.limit, self._ceiling):
            return self._reject(key, "child_limit", self._config.base_cooldown_s, overflowed)
        probe = state.phase is Phase.RECOVERING
        state.probe_in_flight = probe
        state.in_flight += 1
        state.last_active_s = now_s
        parent.in_flight += 1
        self._ticket_seq += 1
        ticket_id = self._ticket_seq
        self._tickets[ticket_id] = AdmissionTicket(state, parent, probe)
        self._admitted_total += 1
        return AdmissionDecision(True, ticket_id, 200, 0.0, "admitted", key, overflowed)

    def _roll_capacity(self, now_s: float) -> None:
        elapsed = now_s - self._capacity_bucket_start_s
        if elapsed >= 60.0:
            self._capacity_current = 0
            self._capacity_previous = 0
            self._capacity_bucket_start_s = now_s
        elif elapsed >= 30.0:
            self._capacity_previous = self._capacity_current
            self._capacity_current = 0
            self._capacity_bucket_start_s = now_s

    def _record_capacity(self, now_s: float) -> None:
        self._roll_capacity(now_s)
        self._capacity_current += 1

    def _reward_state(self, state: KeyState, ttfc_ms: float | None) -> bool:
        if ttfc_ms is not None:
            obs = max(0.0, ttfc_ms)
            state.ttfc_ewma_ms = obs if state.ttfc_ewma_ms <= 0.0 else state.ttfc_ewma_ms * 0.875 + obs * 0.125
        state.ok_window += 1
        cap = self._overflow_cap if state is self._overflow else self._ceiling
        if state.ok_window < state.limit or state.ttfc_ewma_ms > self._config.ewma_gate_ms:
            return False
        state.ok_window = 0
        old_limit = state.limit
        state.limit = min(cap, state.limit + 1)
        return state.limit > old_limit

    def _on_capacity(self, ticket: AdmissionTicket, now_s: float) -> None:
        state = ticket.state
        state.limit = max(1, state.limit // 2)
        state.ok_window = 0
        state.failure_streak += 1
        cooldown = min(self._config.max_cooldown_s, self._config.base_cooldown_s * float(1 << min(state.failure_streak, 4)))
        state.phase = Phase.SHEDDING
        state.cooldown_until_s = now_s + cooldown
        state.probe_in_flight = False
        ticket.parent.limit = max(1, ticket.parent.limit - 1)
        self._record_capacity(now_s)

    def release(self, ticket_id: int, now_s: float, *, outcome: OutcomeKind, ttfc_ms: float | None = None) -> None:
        ticket = self._tickets.pop(ticket_id, None)
        if ticket is None:
            return
        state = ticket.state
        state.in_flight = max(0, state.in_flight - 1)
        state.last_active_s = now_s
        ticket.parent.in_flight = max(0, ticket.parent.in_flight - 1)
        if ticket.probe:
            state.probe_in_flight = False
        if outcome is OutcomeKind.CAPACITY_EXHAUSTED:
            self._on_capacity(ticket, now_s)
            return
        if outcome is not OutcomeKind.OK:
            return
        if ticket.probe:
            state.phase = Phase.OPEN
            state.failure_streak = 0
        if self._reward_state(state, ttfc_ms):
            ticket.parent.limit = min(self._ceiling, ticket.parent.limit + 1)

    def health_snapshot(self, now_s: float) -> AdmissionSnapshot:
        self._roll_capacity(now_s)
        parents = tuple(sorted((name, state.limit) for name, state in self._parents.items()))
        limits = tuple((key, state.limit) for key, state in self._buckets.items())
        pinned = sum(1 for state in self._buckets.values() if not self._can_evict(state, now_s))
        return AdmissionSnapshot(
            capacity_hits_60s=self._capacity_current + self._capacity_previous,
            total_in_flight=sum(state.in_flight for state in self._parents.values()),
            shed_total=self._shed_total,
            admitted_total=self._admitted_total,
            pinned_buckets=pinned,
            overflow_active=self._overflow.in_flight > 0 or self._overflow.phase is not Phase.OPEN,
            parent_limits=parents,
            bucket_limits=limits,
        )

    def reset(self, now_s: float) -> None:
        self._buckets.clear()
        self._parents.clear()
        self._tickets.clear()
        self._overflow = KeyState(limit=self._overflow_cap, last_active_s=now_s)
        self._request_seq = 0
        self._ticket_seq = 0
        self._shed_total = 0
        self._admitted_total = 0
        self._capacity_current = 0
        self._capacity_previous = 0
        self._capacity_bucket_start_s = now_s
