"""Process-local route and provider circuit breaker with auth taxonomy."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from typing import Any

from core.retry_control import RouteCircuitBreaker
from core.route_cb_auth import CBState, compute_retry_after_s, handle_auth_failure
from core.route_cb_auth import bump_tuple_fail, clear_probe_flags, open_provider_wide
from core.route_cb_decisions import CBDecisionInput, CBDecisionState, RouteCBEvent
from core.route_cb_decisions import transition as decide_transition
from core.route_cb_policy import RouteCBConfig, RouteProbeLease, RouteTupleKey
from core.route_cb_policy import FailureOutcome, is_recordable_failure, resolve_provider
from core.route_cb_policy import _ProviderState, _TupleState, _UNPROVEN_DEQUE_MAX

__all__ = ["RouteCB", "RouteCBConfig", "RouteCircuitBreaker", "resolve_provider"]

EventList = list[RouteCBEvent]
LeaseN = RouteProbeLease | None
StateN = _TupleState | _ProviderState | None
Keys = Iterable[RouteTupleKey]


def _can_reset(open_until: float | None, lease: LeaseN, eff: LeaseN, attr: str) -> bool:
    return open_until is None or not lease or bool(getattr(eff, attr, False))


class RouteCB:
    def __init__(
        self,
        config: RouteCBConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
        event_sink: Callable[[RouteCBEvent], None] | None = None,
    ) -> None:
        self._config: RouteCBConfig = RouteCBConfig() if config is None else config
        self._clock: Callable[[], float] = clock
        self._tuples: dict[RouteTupleKey, _TupleState] = {}
        self._providers: dict[str, _ProviderState] = {}
        self._probes: dict[int, tuple[float, RouteProbeLease]] = {}
        self._lock: threading.Lock = threading.Lock()
        self._event_sink: Callable[[RouteCBEvent], None] | None = event_sink
        self._decision_state: CBDecisionState = CBDecisionState()
        self._sink_errors: int = 0
        self._ctx: CBState = (self._tuples, self._providers, self._config)

    @property
    def sink_errors(self) -> int:
        return self._sink_errors

    def _emit_events(self, events: EventList) -> None:
        if self._event_sink is not None and self._config.events_enabled:
            for ev in events:
                try:
                    self._event_sink(ev)
                except Exception:
                    with self._lock:
                        self._sink_errors += 1

    def _decide(self, key: RouteTupleKey, kind: str, evs: EventList, **kw: Any) -> str:
        kw["provider"], kw["model"], kw["backend"] = key
        kw.setdefault("single_route_protect", self._config.single_route_protect)
        pair = decide_transition(self._decision_state, CBDecisionInput(kind=kind, **kw))
        self._decision_state, effects = pair
        evs.extend(fx.event for fx in effects if fx.event is not None)
        return effects[-1].action

    def _state_blocks(self, st: StateN, ts: float) -> bool:
        if st is None or st.open_until is None:
            return False
        deadline = self._probes.get(id(st), (0.0, None))[0]
        return ts < st.open_until or (st.probe_in_flight and ts < deadline)

    def _claim_probe(self, st: StateN, ts: float, lease: RouteProbeLease) -> bool:
        if not st or st.open_until is None:
            return False
        st.probe_in_flight = True
        self._probes[id(st)] = (ts + self._config.cooldown_s, lease)
        return True

    def _active_lease(
        self, lease: LeaseN, key: RouteTupleKey
    ) -> RouteProbeLease | None:
        if not lease or lease.done or lease.key != key:
            return None
        t = self._tuples.get(lease.key)
        p = self._providers.get(lease.key[0])
        t_ok = lease.tuple_lease and self._probes.get(id(t), (0.0, None))[1] is lease
        p_ok = lease.provider_lease and self._probes.get(id(p), (0.0, None))[1] is lease
        out = RouteProbeLease(key=lease.key, route_count=lease.route_count)
        out.provider_lease, out.tuple_lease = bool(p_ok), bool(t_ok)
        return out if (t_ok or p_ok) else None

    def try_acquire(
        self, key: RouteTupleKey, now: float | None = None, route_count: int = 0
    ) -> RouteProbeLease | None:
        events: EventList = []
        with self._lock:
            ts = self._clock() if now is None else now
            lease = self._acquire_locked(key, ts, route_count, events)
        self._emit_events(events)
        return lease

    def _acquire_locked(
        self, key: RouteTupleKey, ts: float, route_count: int, events: EventList
    ) -> RouteProbeLease | None:
        p, t = self._providers.get(key[0]), self._tuples.get(key)
        p_blocks, t_blocks = self._state_blocks(p, ts), self._state_blocks(t, ts)
        if not (p_blocks or t_blocks):
            lease = RouteProbeLease(key=key, route_count=route_count)
            lease.provider_lease = self._claim_probe(p, ts, lease)
            lease.tuple_lease = self._claim_probe(t, ts, lease)
            if lease.provider_lease or lease.tuple_lease:
                self._decide(key, "acquire_probe", events, route_count=route_count)
            return lease
        kw: dict[str, Any] = {"provider_open": p_blocks, "tuple_open": t_blocks}
        kw["route_count"], kw["failures"] = route_count, t.failures if t else 0
        kw["retry_after_s"] = compute_retry_after_s(
            self._ctx[0], self._ctx[1], [key], ts
        )
        if self._decide(key, "acquire_blocked", events, **kw) == "allow":
            return RouteProbeLease(key=key, route_count=route_count)
        return None

    def release_lease(self, lease: RouteProbeLease | None) -> bool:
        with self._lock:
            if not lease or lease.done:
                return False
            self._clear_probe_flags(self._active_lease(lease, lease.key))
            lease.done = True
            return True

    def record_success(self, key: RouteTupleKey, lease: LeaseN = None) -> None:
        events: EventList = []
        with self._lock:
            if self._reset_success_locked(key, lease):
                kw = {
                    "was_open": True,
                    "route_count": lease.route_count if lease else 0,
                }
                self._decide(key, "record_success", events, **kw)
        self._emit_events(events)

    def _reset_success_locked(self, key: RouteTupleKey, lease: LeaseN) -> bool:
        eff_lease = self._active_lease(lease, key)
        was_open = False
        t = self._tuples.get(key)
        if t and _can_reset(t.open_until, lease, eff_lease, "tuple_lease"):
            was_open = t.open_until is not None
            t.failures, t.first_fail_ts = 0, None
            t.open_until, t.probe_in_flight = None, False
            self._probes.pop(id(t), None)
        if p := self._providers.get(key[0]):
            if p.open_until is None:
                kept = (e for e in p.unproven if e[0] != key)
                p.unproven = deque(kept, maxlen=_UNPROVEN_DEQUE_MAX)
            elif _can_reset(p.open_until, lease, eff_lease, "provider_lease"):
                p.open_until, p.probe_in_flight = None, False
                p.unproven.clear()
                self._probes.pop(id(p), None)
                was_open = True
        if lease and lease.key == key:
            lease.done = True
        return was_open

    def record_failure(
        self,
        key: RouteTupleKey,
        outcome: FailureOutcome | None = None,
        lease: RouteProbeLease | None = None,
        now: float | None = None,
    ) -> str:
        with self._lock:
            ts = self._clock() if now is None else now
            eff = outcome or FailureOutcome()
            res, events = self._record_failure_locked(key, eff, lease, ts)
        self._emit_events(events)
        return res

    def _record_failure_locked(
        self, key: RouteTupleKey, eff: FailureOutcome, lease: LeaseN, ts: float
    ) -> tuple[str, EventList]:
        events: EventList = []
        eff_lease = self._active_lease(lease, key)
        rc = eff.route_count or (lease.route_count if lease else 0)
        was_open = self._any_open(key)
        if not is_recordable_failure(eff.status, eff.error, eff.reason):
            res = "ignored"
        elif eff.status in (401, 402, 403):
            res = handle_auth_failure(self._ctx, key, eff, eff_lease, ts)
            if not was_open and self._any_open(key):
                kw: dict[str, Any] = {"is_auth": True, "route_count": rc}
                kw["retry_after_s"] = int(self._config.cooldown_s)
                self._decide(key, "record_failure", events, opened_now=True, **kw)
        else:
            res, evs = self._plain_failure_locked(key, eff, lease, ts)
            events.extend(evs)
        self._clear_probe_flags(eff_lease)
        if lease and lease.key == key:
            lease.done = True
        return res, events

    def _plain_failure_locked(
        self, key: RouteTupleKey, eff: FailureOutcome, lease: LeaseN, ts: float
    ) -> tuple[str, EventList]:
        events: EventList = []
        eff_lease = self._active_lease(lease, key)
        force_open = bool(eff_lease and eff_lease.tuple_lease)
        p_lease = bool(eff_lease and eff_lease.provider_lease)
        rc = eff.route_count or (lease.route_count if lease else 0)
        kw: dict[str, Any] = {"route_count": rc, "status": eff.status}
        kw["opened_now"] = self._bump_would_open(key, ts, force_open)
        kw["retry_after_s"] = int(self._config.cooldown_s)
        action = self._decide(key, "record_failure", events, **kw)
        if action != "suppress_tuple_cooldown":
            bump_tuple_fail(self._ctx, key, ts, force_open)
        if p_lease:
            open_provider_wide(self._ctx, key[0], ts)
        return "route_fail", events

    def _bump_would_open(self, key: RouteTupleKey, ts: float, force_open: bool) -> bool:
        t = self._tuples.get(key)
        if t is None or t.open_until is not None:
            return t is None and self._config.failure_threshold <= 1
        fresh = t.first_fail_ts is None or ts - t.first_fail_ts > self._config.window_s
        n = 1 if fresh else t.failures + 1
        return force_open or n >= self._config.failure_threshold

    def _any_open(self, key: RouteTupleKey) -> bool:
        t, p = self._tuples.get(key), self._providers.get(key[0])
        return bool(
            (t and t.open_until is not None) or (p and p.open_until is not None)
        )

    def retry_after_s(self, keys: Keys, now: float | None = None) -> int:
        with self._lock:
            ts = self._clock() if now is None else now
            return compute_retry_after_s(self._tuples, self._providers, keys, ts)

    def _clear_probe_flags(self, lease: LeaseN) -> None:
        if lease:
            t = self._tuples.get(lease.key) if lease.tuple_lease else None
            p = self._providers.get(lease.key[0]) if lease.provider_lease else None
            for st in filter(None, (t, p)):
                self._probes.pop(id(st), None)
            clear_probe_flags(self._ctx, lease)
