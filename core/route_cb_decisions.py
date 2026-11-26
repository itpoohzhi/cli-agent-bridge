"""Pure Zero-I/O route circuit-breaker decision FSM and log-event sanitizer (REQ-001 Wave 1)."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Final

SAFE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
SECRET_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^a-z0-9])(?:sk-|ghp_|gho_|github_pat_|xoxb-|xoxp-|bearer|token|apikey|api_key|secret|password)",
    re.IGNORECASE,
)
ALLOWED_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {"open", "half_open_probe", "close", "blocked", "single_route_protection"}
)
ALLOWED_STATES: Final[frozenset[str]] = frozenset(
    {"closed", "open", "half_open", "protected"}
)
_INT_FIELD_MAX: Final[int] = 9999
_CB_SEQ_MAX: Final[int] = 9_999_999_999


def sanitize_field(value: object, allowed: frozenset[str] | None = None) -> str:
    """Return a log-safe identifier or "?" (strict allowlist mode when `allowed` is given)."""
    if not isinstance(value, str) or SECRET_TOKEN_RE.search(value) is not None:
        return "?"
    if allowed is not None:
        return value if value in allowed and len(value) <= 32 else "?"
    return value if SAFE_ID_RE.fullmatch(value) is not None else "?"


_safe = sanitize_field


@dataclass(frozen=True, slots=True)
class RouteCBEvent:
    """Fixed-shape sanitized circuit-breaker log event."""

    event: str
    provider: str
    model: str
    backend: str
    state: str
    failures: int
    retry_after_s: int
    route_count: int
    cb_seq: int


def format_cb_event(ev: RouteCBEvent, allowed: frozenset[str] | None = None) -> str:
    """Format the fixed allowlist of fields; worst-case ASCII length <= 247 B, cb_seq never cut."""
    ev_name = ev.event if ev.event in ALLOWED_EVENT_KINDS else "?"
    st = ev.state if ev.state in ALLOWED_STATES else "?"
    p = sanitize_field(ev.provider, allowed)
    m = sanitize_field(ev.model, allowed)
    b = sanitize_field(ev.backend, allowed)
    f = max(0, min(_INT_FIELD_MAX, int(ev.failures)))
    ra = max(0, min(_INT_FIELD_MAX, int(ev.retry_after_s)))
    rc = max(0, min(_INT_FIELD_MAX, int(ev.route_count)))
    seq = max(0, min(_CB_SEQ_MAX, int(ev.cb_seq)))
    return (
        f"route_cb event={ev_name} provider={p} model={m} backend={b} state={st}"
        f" failures={f} retry_after_s={ra} route_count={rc} cb_seq={seq}"
    )


@dataclass(frozen=True, slots=True)
class CBDecisionState:
    """Immutable FSM state: only the monotonic event sequence counter."""

    cb_seq: int = 0


@dataclass(frozen=True, slots=True)
class CBDecisionInput:
    """Normalized decision request; all flags are pre-computed by the caller."""

    kind: str
    provider: str
    model: str
    backend: str
    single_route_protect: bool = False
    route_count: int = 0
    status: int | None = None
    provider_open: bool = False
    tuple_open: bool = False
    was_open: bool = False
    failures: int = 0
    retry_after_s: int = 0
    opened_now: bool = False
    is_auth: bool = False


@dataclass(frozen=True, slots=True)
class CBDecisionEffect:
    """Action for the caller plus an optional sanitized event to log."""

    action: str
    event: RouteCBEvent | None = None


def should_suppress_single_route(
    protect: bool, route_count: int, status: int | None, is_auth: bool = False
) -> bool:
    """True only for a protected single route, non-auth, outside the 401/402/403/429 carve-out."""
    return (
        protect
        and route_count == 1
        and not is_auth
        and status not in (401, 402, 403, 429)
    )


def _event(kind: str, st: str, inp: CBDecisionInput, seq: int) -> RouteCBEvent:
    return RouteCBEvent(
        event=kind,
        provider=inp.provider,
        model=inp.model,
        backend=inp.backend,
        state=st,
        failures=inp.failures,
        retry_after_s=inp.retry_after_s,
        route_count=inp.route_count,
        cb_seq=seq,
    )


def _finish(
    state: CBDecisionState, seq: int, action: str, ev: RouteCBEvent | None
) -> tuple[CBDecisionState, tuple[CBDecisionEffect, ...]]:
    new_state = CBDecisionState(cb_seq=seq) if ev is not None else state
    return new_state, (CBDecisionEffect(action, ev),)


def _acquire_blocked(
    state: CBDecisionState, inp: CBDecisionInput, seq: int
) -> tuple[CBDecisionState, tuple[CBDecisionEffect, ...]]:
    if inp.provider_open:
        return _finish(state, seq, "deny", _event("blocked", "open", inp, seq))
    if inp.tuple_open and should_suppress_single_route(
        inp.single_route_protect, inp.route_count, inp.status, inp.is_auth
    ):
        ev = replace(
            _event("single_route_protection", "protected", inp, seq), retry_after_s=0
        )
        return _finish(state, seq, "allow", ev)
    return _finish(state, seq, "deny", _event("blocked", "open", inp, seq))


def _record_failure(
    state: CBDecisionState, inp: CBDecisionInput, seq: int
) -> tuple[CBDecisionState, tuple[CBDecisionEffect, ...]]:
    if inp.is_auth or inp.status in (401, 402, 403):
        ev = _event("open", "open", inp, seq) if inp.opened_now else None
        return _finish(state, seq, "auth_delegate", ev)
    if should_suppress_single_route(
        inp.single_route_protect, inp.route_count, inp.status, False
    ):
        ev = replace(
            _event("single_route_protection", "protected", inp, seq), retry_after_s=0
        )
        return _finish(state, seq, "suppress_tuple_cooldown", ev)
    ev = _event("open", "open", inp, seq) if inp.opened_now else None
    return _finish(state, seq, "bump_tuple_fail", ev)


def transition(
    state: CBDecisionState, inp: CBDecisionInput
) -> tuple[CBDecisionState, tuple[CBDecisionEffect, ...]]:
    """Pure deterministic F-FSM-I1 step; cb_seq grows by 1 only when an event is emitted."""
    seq = state.cb_seq + 1
    if inp.kind == "acquire_blocked":
        return _acquire_blocked(state, inp, seq)
    if inp.kind == "acquire_probe":
        return _finish(
            state, seq, "allow", _event("half_open_probe", "half_open", inp, seq)
        )
    if inp.kind == "record_failure":
        return _record_failure(state, inp, seq)
    if inp.kind == "record_success":
        if inp.was_open:
            ev = replace(
                _event("close", "closed", inp, seq), failures=0, retry_after_s=0
            )
            return _finish(state, seq, "noop", ev)
        return state, (CBDecisionEffect("noop"),)
    raise ValueError(f"unknown decision kind: {inp.kind}")
