"""Circuit-breaker state transition helpers for tuple failures, provider-wide cooldown, and auth taxonomy."""
from __future__ import annotations

import math
from collections.abc import Iterable

from core.route_cb_policy import (
    FailureOutcome,
    RouteCBConfig,
    RouteProbeLease,
    RouteTupleKey,
    _ProviderState,
    _TupleState,
    classify_auth_failure,
)

CBState = tuple[dict[RouteTupleKey, _TupleState], dict[str, _ProviderState], RouteCBConfig]


def compute_retry_after_s(
    tuples: dict[RouteTupleKey, _TupleState],
    providers: dict[str, _ProviderState],
    keys: Iterable[RouteTupleKey],
    ts: float,
) -> int:
    """Compute clamped Retry-After >= 1 across blocking routes using max(tuple, provider) open_until."""
    waits: list[float] = []
    for key in keys:
        t = tuples.get(key)
        p = providers.get(key[0])
        t_until = t.open_until if t and t.open_until is not None else -math.inf
        p_until = p.open_until if p and p.open_until is not None else -math.inf
        eff_until = max(t_until, p_until)
        waits.append(eff_until - ts if eff_until > ts else 0.0)
    return max(1, math.ceil(min(waits) if waits else 0.0))


def clear_probe_flags(state: CBState, lease: RouteProbeLease | None) -> None:
    """Clear in-flight probe lease flags under caller lock."""
    tuples, providers, _ = state
    if lease is None or lease.done:
        return
    if lease.provider_lease and (p := providers.get(lease.key[0])) is not None:
        p.probe_in_flight = False
    if lease.tuple_lease and (t := tuples.get(lease.key)) is not None:
        t.probe_in_flight = False
    lease.done = True


def bump_tuple_fail(state: CBState, key: RouteTupleKey, ts: float, force_open: bool) -> None:
    """Increment tuple failure counter inside sliding window and open cooldown on threshold."""
    tuples, _, config = state
    t = tuples.setdefault(key, _TupleState())
    if t.first_fail_ts is None or (ts - t.first_fail_ts) > config.window_s:
        t.failures, t.first_fail_ts = 0, ts
    t.failures += 1
    if force_open or t.failures >= config.failure_threshold:
        t.open_until = ts + config.cooldown_s
        t.failures, t.first_fail_ts = 0, None


def open_provider_wide(state: CBState, provider: str, ts: float) -> None:
    """Open provider-wide cooldown and reset unproven failure queue."""
    _, providers, config = state
    p = providers.setdefault(provider, _ProviderState())
    p.open_until, p.probe_in_flight = ts + config.cooldown_s, False
    p.unproven.clear()


def record_unproven(state: CBState, provider: str, key: RouteTupleKey, ts: float) -> None:
    """Track unproven auth failure across distinct route tuples and escalate at >= 2 routes."""
    _, providers, config = state
    p = providers.setdefault(provider, _ProviderState())
    while p.unproven and (ts - p.unproven[0][1]) > config.window_s:
        p.unproven.popleft()
    p.unproven.append((key, ts))
    if len({entry_key for entry_key, _ in p.unproven}) >= 2:
        open_provider_wide(state, provider, ts)


def handle_auth_failure(
    state: CBState,
    key: RouteTupleKey,
    outcome: FailureOutcome,
    lease: RouteProbeLease | None,
    ts: float,
) -> str:
    """Apply route_local, provider_wide, or unproven 401/402/403 failure transitions."""
    kind = classify_auth_failure(outcome.status or 0, outcome.detail)
    tuple_probed = bool(lease and lease.tuple_lease)
    if kind == "route_local":
        bump_tuple_fail(state, key, ts, force_open=tuple_probed)
    elif kind == "provider_wide":
        open_provider_wide(state, key[0], ts)
    else:
        bump_tuple_fail(state, key, ts, force_open=tuple_probed)
        if lease and lease.provider_lease:
            open_provider_wide(state, key[0], ts)
        else:
            record_unproven(state, key[0], key, ts)
    clear_probe_flags(state, lease)
    return kind
