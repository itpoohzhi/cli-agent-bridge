"""Process-local route and provider circuit breaker with auth taxonomy."""
from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable, Iterable

from core.retry_control import RouteCircuitBreaker
from core.route_cb_auth import (
    bump_tuple_fail,
    clear_probe_flags,
    compute_retry_after_s,
    handle_auth_failure,
    open_provider_wide,
)
from core.route_cb_policy import FailureOutcome, RouteCBConfig, RouteProbeLease, RouteTupleKey
from core.route_cb_policy import PROVIDER_AUTH_MARKERS, ROUTE_LOCAL_MARKERS, classify_auth_failure, is_recordable_failure
from core.route_cb_policy import _ProviderState, _TupleState, _UNPROVEN_DEQUE_MAX
from core.route_cb_policy import _with_retry_after, load_route_cb_config
from core.route_cb_policy import is_client_gone, is_route_cb_enabled, resolve_provider

__all__ = [
    "FailureOutcome", "PROVIDER_AUTH_MARKERS", "ROUTE_LOCAL_MARKERS", "RouteCB",
    "RouteCBConfig", "RouteCircuitBreaker", "RouteProbeLease", "RouteTupleKey", "_with_retry_after",
    "classify_auth_failure", "is_client_gone", "is_recordable_failure",
    "is_route_cb_enabled", "load_route_cb_config", "resolve_provider",
]


class RouteCB:
    """In-memory route (provider, model, backend) and provider-wide circuit breaker."""

    def __init__(self, config: RouteCBConfig | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self._config: RouteCBConfig = RouteCBConfig() if config is None else config
        self._clock: Callable[[], float] = clock
        self._tuples: dict[RouteTupleKey, _TupleState] = {}
        self._providers: dict[str, _ProviderState] = {}
        self._probes: dict[int, tuple[float, RouteProbeLease]] = {}
        self._lock: threading.Lock = threading.Lock()

    def _state_blocks(self, state: _TupleState | _ProviderState | None, ts: float) -> bool:
        """Open state blocks during cooldown or while a half-open probe is within TTL."""
        deadline = self._probes.get(id(state), (0.0, None))[0]
        return bool(state and state.open_until is not None and (ts < state.open_until or (state.probe_in_flight and ts < deadline)))

    def _claim_probe(self, state: _TupleState | _ProviderState | None, ts: float, lease: RouteProbeLease) -> bool:
        """Flip probe_in_flight with owning lease and bounded deadline on an open state."""
        if not state or state.open_until is None:
            return False
        state.probe_in_flight = True
        self._probes[id(state)] = (ts + self._config.cooldown_s, lease)
        return True

    def _owns(self, flag: bool, state: _TupleState | _ProviderState | None, lease: RouteProbeLease) -> bool:
        return bool(flag and state and self._probes.get(id(state), (0.0, None))[1] is lease)

    def _active_lease(self, lease: RouteProbeLease | None) -> RouteProbeLease | None:
        if not lease or lease.done:
            return None
        t_ok = self._owns(lease.tuple_lease, self._tuples.get(lease.key), lease)
        p_ok = self._owns(lease.provider_lease, self._providers.get(lease.key[0]), lease)
        return RouteProbeLease(key=lease.key, provider_lease=p_ok, tuple_lease=t_ok) if (t_ok or p_ok) else None

    def try_acquire(self, key: RouteTupleKey, now: float | None = None) -> RouteProbeLease | None:
        """Acquire tuple/provider permission or single serialized half-open probe lease."""
        with self._lock:
            ts = self._clock() if now is None else now
            p, t = self._providers.get(key[0]), self._tuples.get(key)
            if self._state_blocks(p, ts) or self._state_blocks(t, ts):
                return None
            lease = RouteProbeLease(key=key)
            lease.provider_lease, lease.tuple_lease = self._claim_probe(p, ts, lease), self._claim_probe(t, ts, lease)
            return lease

    def release_lease(self, lease: RouteProbeLease | None) -> bool:
        """Release half-open probe flags without altering cooldowns or failure counters."""
        with self._lock:
            if not lease or lease.done:
                return False
            self._clear_probe_flags(self._active_lease(lease))
            lease.done = True
            return True

    def record_success(self, key: RouteTupleKey, lease: RouteProbeLease | None = None) -> None:
        """Reset tuple/provider state on success and release any held probe lease."""
        with self._lock:
            eff_lease = self._active_lease(lease)
            if t := self._tuples.get(key):
                t.failures, t.first_fail_ts, t.open_until, t.probe_in_flight = 0, None, None, False
                self._probes.pop(id(t), None)
            if p := self._providers.get(key[0]):
                if getattr(eff_lease, "provider_lease", False) or p.open_until is not None:
                    p.open_until, p.probe_in_flight = None, False
                    p.unproven.clear()
                    self._probes.pop(id(p), None)
                else:
                    p.unproven = deque(((k, ts) for k, ts in p.unproven if k != key), maxlen=_UNPROVEN_DEQUE_MAX)
            if lease: lease.done = True

    def record_failure(self, key: RouteTupleKey, outcome: FailureOutcome | None = None, lease: RouteProbeLease | None = None, now: float | None = None) -> str:
        """Classify outcome and update tuple/provider state; never logs credentials."""
        eff = outcome or FailureOutcome()
        with self._lock:
            ts, eff_lease = self._clock() if now is None else now, self._active_lease(lease)
            if not is_recordable_failure(eff.status, eff.error, eff.reason):
                self._clear_probe_flags(eff_lease)
                res = "ignored"
            elif eff.status in (401, 402, 403):
                res = self._handle_auth_failure(key, eff, eff_lease, ts)
            else:
                self._bump_tuple_fail(key, ts, force_open=bool(getattr(eff_lease, "tuple_lease", False)))
                if getattr(eff_lease, "provider_lease", False): self._open_provider_wide(key[0], ts)
                self._clear_probe_flags(eff_lease)
                res = "route_fail"
            if lease: lease.done = True
            return res

    def retry_after_s(self, keys: Iterable[RouteTupleKey], now: float | None = None) -> int:
        """Compute clamped Retry-After >= 1 across blocking routes using max(tuple, provider) open_until."""
        with self._lock:
            ts = self._clock() if now is None else now
            return compute_retry_after_s(self._tuples, self._providers, keys, ts)

    def _state_ctx(self) -> tuple[dict[RouteTupleKey, _TupleState], dict[str, _ProviderState], RouteCBConfig]:
        return (self._tuples, self._providers, self._config)

    def _clear_probe_flags(self, lease: RouteProbeLease | None) -> None:
        if not lease:
            return
        for st in (self._tuples.get(lease.key) if lease.tuple_lease else None, self._providers.get(lease.key[0]) if lease.provider_lease else None):
            if st: self._probes.pop(id(st), None)
        clear_probe_flags(self._state_ctx(), lease)

    def _bump_tuple_fail(self, key: RouteTupleKey, ts: float, force_open: bool) -> None:
        bump_tuple_fail(self._state_ctx(), key, ts, force_open)

    def _open_provider_wide(self, provider: str, ts: float) -> None:
        open_provider_wide(self._state_ctx(), provider, ts)

    def _handle_auth_failure(self, key: RouteTupleKey, outcome: FailureOutcome, lease: RouteProbeLease | None, ts: float) -> str:
        return handle_auth_failure(self._state_ctx(), key, outcome, lease, ts)
