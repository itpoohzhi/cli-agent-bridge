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
    record_unproven,
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
        self._config: RouteCBConfig = config or RouteCBConfig()
        self._clock: Callable[[], float] = clock
        self._tuples: dict[RouteTupleKey, _TupleState] = {}
        self._providers: dict[str, _ProviderState] = {}
        self._probe_until: dict[int, float] = {}
        self._lock: threading.Lock = threading.Lock()

    def _state_blocks(self, state: _TupleState | _ProviderState | None, ts: float) -> bool:
        """Open state blocks during cooldown or while a half-open probe is within TTL."""
        if state is None or state.open_until is None:
            return False
        if ts < state.open_until:
            return True
        return state.probe_in_flight and ts < self._probe_until.get(id(state), 0.0)

    def _claim_probe(self, state: _TupleState | _ProviderState | None, ts: float) -> bool:
        """Flip probe_in_flight with bounded deadline on an open state and report claim."""
        if state is None or state.open_until is None:
            return False
        state.probe_in_flight = True
        self._probe_until[id(state)] = ts + self._config.cooldown_s
        return True

    def try_acquire(self, key: RouteTupleKey, now: float | None = None) -> RouteProbeLease | None:
        """Acquire tuple/provider permission or single serialized half-open probe lease."""
        ts = self._clock() if now is None else now
        with self._lock:
            if self._state_blocks(self._providers.get(key[0]), ts) or self._state_blocks(self._tuples.get(key), ts):
                return None
            provider_lease = self._claim_probe(self._providers.get(key[0]), ts)
            tuple_lease = self._claim_probe(self._tuples.get(key), ts)
            return RouteProbeLease(key=key, provider_lease=provider_lease, tuple_lease=tuple_lease)

    def release_lease(self, lease: RouteProbeLease | None) -> bool:
        """Release half-open probe flags without altering cooldowns or failure counters."""
        with self._lock:
            if lease is None or lease.done:
                return False
            self._clear_probe_flags(lease)
            lease.done = True
            return True

    def record_success(self, key: RouteTupleKey, lease: RouteProbeLease | None = None) -> None:
        """Reset tuple/provider state on success and release any held probe lease."""
        with self._lock:
            t = self._tuples.get(key)
            if t is not None:
                t.failures, t.first_fail_ts, t.open_until, t.probe_in_flight = 0, None, None, False
            p = self._providers.get(key[0])
            if p is not None:
                if getattr(lease, "provider_lease", False) or p.open_until is not None:
                    p.open_until, p.probe_in_flight = None, False
                    p.unproven.clear()
                else:
                    p.unproven = deque(((k, ts) for k, ts in p.unproven if k != key), maxlen=_UNPROVEN_DEQUE_MAX)
            if lease is not None:
                lease.done = True

    def record_failure(self, key: RouteTupleKey, outcome: FailureOutcome | None = None, lease: RouteProbeLease | None = None, now: float | None = None) -> str:
        """Classify outcome and update tuple/provider state; never logs credentials."""
        eff = outcome or FailureOutcome()
        ts = self._clock() if now is None else now
        with self._lock:
            if not is_recordable_failure(eff.status, eff.error, eff.reason):
                self._clear_probe_flags(lease)
                return "ignored"
            if eff.status in (401, 402, 403):
                return self._handle_auth_failure(key, eff, lease, ts)
            live_lease = None if getattr(lease, "done", False) else lease
            self._bump_tuple_fail(key, ts, force_open=bool(getattr(live_lease, "tuple_lease", False)))
            if getattr(live_lease, "provider_lease", False):
                self._open_provider_wide(key[0], ts)
            self._clear_probe_flags(live_lease)
            if lease is not None:
                lease.done = True
            return "route_fail"

    def retry_after_s(self, keys: Iterable[RouteTupleKey], now: float | None = None) -> int:
        """Compute clamped Retry-After >= 1 across blocking routes using max(tuple, provider) open_until."""
        ts = self._clock() if now is None else now
        with self._lock:
            return compute_retry_after_s(self._tuples, self._providers, keys, ts)

    def _state_ctx(self) -> tuple[dict[RouteTupleKey, _TupleState], dict[str, _ProviderState], RouteCBConfig]:
        return (self._tuples, self._providers, self._config)

    def _clear_probe_flags(self, lease: RouteProbeLease | None) -> None:
        clear_probe_flags(self._state_ctx(), lease)

    def _bump_tuple_fail(self, key: RouteTupleKey, ts: float, force_open: bool) -> None:
        bump_tuple_fail(self._state_ctx(), key, ts, force_open)

    def _open_provider_wide(self, provider: str, ts: float) -> None:
        open_provider_wide(self._state_ctx(), provider, ts)

    def _record_unproven(self, provider: str, key: RouteTupleKey, ts: float) -> None:
        record_unproven(self._state_ctx(), provider, key, ts)

    def _handle_auth_failure(self, key: RouteTupleKey, outcome: FailureOutcome, lease: RouteProbeLease | None, ts: float) -> str:
        return handle_auth_failure(self._state_ctx(), key, outcome, lease, ts)
