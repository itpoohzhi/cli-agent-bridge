"""Pure domain recovery FSM separating route and credential health for Codex."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Final

CREDENTIAL_ERROR_CODES: Final[frozenset[str]] = frozenset(
    "credential_unavailable rate_limit_transient quota_exhausted rate_limit_unknown auth_failed auth_refresh_exhausted".split()
)
_VALID_PHASES: Final[frozenset[str]] = frozenset(("admitted", "completed"))
_INF: Final[float] = float("inf")


class HealthDomain(str, Enum):  # noqa: UP042
    ROUTE, CREDENTIAL = "route", "credential"


class RecoveryPhase(str, Enum):  # noqa: UP042
    HEALTHY, BLOCKED, PROBE_DUE, PONG_IN_FLIGHT, COOLDOWN = "HEALTHY", "BLOCKED", "PROBE_DUE", "PONG_IN_FLIGHT", "COOLDOWN"


class EvidenceKind(str, Enum):  # noqa: UP042
    PONG_RECEIPT, HEALTH_200, EMPTY_DONE, UNIT_TEST, COUNTER_RESET = "pong_receipt", "health_200", "empty_done", "unit_test", "counter_reset"


class RecoveryEventKind(str, Enum):  # noqa: UP042
    FAILURE, TICK, SCHEDULE_PROBE, PROBE_STARTED = "failure", "tick", "schedule_probe", "probe_started"
    PONG_RECEIPT, PROBE_FAILED, NON_PONG_SIGNAL = "pong_receipt", "probe_failed", "non_pong_signal"


class RecoveryEffectKind(str, Enum):  # noqa: UP042
    MARK_BLOCKED, ENTER_COOLDOWN, PROBE_READY, START_PONG_PROBE = "mark_blocked", "enter_cooldown", "probe_ready", "start_pong_probe"
    MARK_HEALTHY, EMIT_RECOVERY_RECEIPT, REJECT_TRANSITION = "mark_healthy", "emit_recovery_receipt", "reject_transition"


@dataclass(frozen=True, slots=True)
class RecoveryPolicy:
    probe_cooldown_s: float = 30.0
    max_cooldown_s: float = 3600.0
    cooldown_backoff_factor: float = 2.0
    transient_default_cooldown_s: float = 15.0


DEFAULT_RECOVERY_POLICY: Final[RecoveryPolicy] = RecoveryPolicy()


@dataclass(frozen=True, slots=True)
class ProbeExpectation:
    model_id: str
    effort: str = ""
    backend: str = ""
    route_id: str = ""
    profile: str = ""


@dataclass(frozen=True, slots=True)
class PongReceipt:
    probe_id: str
    requested_model: str
    actual_model: str
    requested_effort: str
    actual_effort: str
    backend: str
    route_id: str
    profile: str
    attestation: str
    done_received: bool
    complete: bool
    content: str
    finish_reason: str = "stop"
    error_count: int = 0
    tool_event_count: int = 0
    evidence_kind: EvidenceKind = EvidenceKind.PONG_RECEIPT


@dataclass(frozen=True, slots=True)
class DomainHealthState:
    domain: HealthDomain
    phase: RecoveryPhase = RecoveryPhase.BLOCKED
    cooldown_until_s: float | None = None
    active_probe_id: str | None = None
    consecutive_failures: int = 0
    last_error_code: str = ""
    last_receipt: PongReceipt | None = None


@dataclass(frozen=True, slots=True)
class CodexRecoveryState:
    expectation: ProbeExpectation
    credential_id: str
    route: DomainHealthState
    credential: DomainHealthState
    @property
    def is_route_healthy(self) -> bool: return self.route.phase is RecoveryPhase.HEALTHY
    @property
    def is_credential_healthy(self) -> bool: return self.credential.phase is RecoveryPhase.HEALTHY
    @property
    def is_healthy(self) -> bool: return self.is_route_healthy and self.is_credential_healthy


@dataclass(frozen=True, slots=True)
class RecoveryEvent:
    kind: RecoveryEventKind
    now_s: float = 0.0
    domain: HealthDomain | None = None
    error_code: str = ""
    cooldown_s: float | None = None
    proven_reset: bool = False
    probe_id: str = ""
    receipt: PongReceipt | None = None
    evidence_kind: EvidenceKind | None = None


@dataclass(frozen=True, slots=True)
class RecoveryEffect:
    kind: RecoveryEffectKind
    domain: HealthDomain
    reason: str = ""
    cooldown_until_s: float | None = None
    probe_id: str = ""
    receipt: PongReceipt | None = None


_HD, _RP, _EV, _EK = HealthDomain, RecoveryPhase, RecoveryEventKind, RecoveryEffectKind
_DS, _EV_T, _POL, _EXP = DomainHealthState, RecoveryEvent, RecoveryPolicy, ProbeExpectation
_OUT = tuple[DomainHealthState, tuple[RecoveryEffect, ...]]


def create_recovery_state(
    expectation: ProbeExpectation, credential_id: str,
    route_phase: RecoveryPhase = RecoveryPhase.BLOCKED, credential_phase: RecoveryPhase = RecoveryPhase.BLOCKED,
) -> CodexRecoveryState:
    """Create dual-domain recovery state (fail-closed BLOCKED by default)."""
    return CodexRecoveryState(expectation, credential_id, _DS(_HD.ROUTE, route_phase), _DS(_HD.CREDENTIAL, credential_phase))


def classify_failure_domain(error_code: str) -> HealthDomain:
    return _HD.CREDENTIAL if error_code.strip().lower() in CREDENTIAL_ERROR_CODES else _HD.ROUTE


def parse_attestation(raw: str) -> dict[str, str] | None:
    if not raw.strip():
        return None
    out: dict[str, str] = {}
    for part in raw.strip().split(";"):
        if "=" not in part:
            return None
        key, val = part.split("=", 1)
        k, v = key.strip().lower(), val.strip()
        if not (k and v) or k in out:
            return None
        out[k] = v
    return out


def _attest_ok(r: PongReceipt) -> bool:
    kv = parse_attestation(r.attestation)
    if kv is None:
        return False
    prof = r.profile.strip().lower()
    if (kv.get("profile", "").lower(), kv.get("backend"), kv.get("model"), kv.get("effort")) != (prof, r.backend, r.actual_model, r.actual_effort):
        return False
    ph = kv.get("phase")
    if prof != "zero-canon":
        return ph is None or ph in _VALID_PHASES
    return (kv.get("tools"), kv.get("sandbox"), kv.get("approval")) == ("off", "read-only", "never") and ph in _VALID_PHASES


def _field_ok(actual: str, expected: str) -> bool: return bool(actual) and expected in ("", actual)
def _identity_ok(req: str, actual: str, expected: str) -> bool: return _field_ok(actual, expected) and req == actual


def validate_pong_receipt(receipt: PongReceipt, expected: _EXP) -> tuple[bool, str]:
    """Validate complete attested PONG receipt required for HEALTHY."""
    r, e = receipt, expected
    checks = (
        ("non_pong_evidence", r.evidence_kind is EvidenceKind.PONG_RECEIPT), ("incomplete_receipt", r.complete and r.done_received),
        ("invalid_terminal", (r.finish_reason, r.error_count, r.tool_event_count) == ("stop", 0, 0)), ("empty_pong_content", bool(r.content.strip())),
        ("model_mismatch", _identity_ok(r.requested_model, r.actual_model, e.model_id)), ("effort_mismatch", _identity_ok(r.requested_effort, r.actual_effort, e.effort)),
        ("backend_mismatch", _field_ok(r.backend, e.backend)), ("route_mismatch", _field_ok(r.route_id, e.route_id)),
        ("profile_mismatch", _field_ok(r.profile.strip().lower(), e.profile.strip().lower())),
    )
    for reason, ok in checks:
        if not ok:
            return False, reason
    return (True, "") if _attest_ok(r) else (False, "invalid_attestation")


def _bounded(val: float | None, limit: float) -> float | None:
    if val is None or not (0.0 < val < _INF):
        return None
    return min(val, limit) if 0.0 < limit < _INF else val


def _rej(domain: HealthDomain, reason: str) -> tuple[RecoveryEffect, ...]: return (RecoveryEffect(_EK.REJECT_TRANSITION, domain, reason),)


def _cooldown_for(ev: _EV_T, pol: _POL, fails: int, in_flight: bool) -> float | None:
    code, cap = ev.error_code.strip().lower(), pol.max_cooldown_s
    if code in ("rate_limit_unknown", "credential_unavailable"):
        return None
    if code == "quota_exhausted":
        return _bounded(ev.cooldown_s, 0.0) if ev.proven_reset else None
    if code == "rate_limit_transient":
        d = _bounded(ev.cooldown_s, cap)
        return d if d is not None else _bounded(pol.transient_default_cooldown_s, cap)
    if not in_flight:
        return None
    if (exp := _bounded(ev.cooldown_s, cap)) is not None:
        return exp
    if (base := _bounded(pol.probe_cooldown_s, cap)) is None:
        return None
    return _bounded(base * (max(1.0, pol.cooldown_backoff_factor) ** max(0, fails - 1)), cap)


def _fail_domain(ds: _DS, ev: _EV_T, pol: _POL, reason: str) -> _OUT:
    fails = ds.consecutive_failures + 1
    delay = _cooldown_for(ev, pol, fails, ds.phase is _RP.PONG_IN_FLIGHT)
    until = None if delay is None else ev.now_s + delay
    if until is not None and ds.cooldown_until_s is not None:
        until = max(until, ds.cooldown_until_s)
    ph, ek = (_RP.BLOCKED, _EK.MARK_BLOCKED) if until is None else (_RP.COOLDOWN, _EK.ENTER_COOLDOWN)
    return _DS(ds.domain, ph, until, None, fails, reason, ds.last_receipt), (RecoveryEffect(ek, ds.domain, reason, until),)


def _apply_pong(ds: _DS, ev: _EV_T, exp: _EXP, pol: _POL) -> _OUT:
    if ds.phase is not _RP.PONG_IN_FLIGHT:
        return ds, _rej(ds.domain, "not_in_flight")
    rcpt = ev.receipt
    if rcpt is not None and ds.active_probe_id and rcpt.probe_id != ds.active_probe_id:
        return ds, _rej(ds.domain, "stale_probe_id")
    ok, why = (False, "missing_receipt") if rcpt is None else validate_pong_receipt(rcpt, exp)
    if not ok or rcpt is None:
        nxt, eff = _fail_domain(ds, ev, pol, why)
        return nxt, (*_rej(ds.domain, why), *eff)
    pid = rcpt.probe_id
    effs = (RecoveryEffect(_EK.MARK_HEALTHY, ds.domain, "", None, pid, rcpt), RecoveryEffect(_EK.EMIT_RECOVERY_RECEIPT, ds.domain, "", None, pid, rcpt))
    return _DS(ds.domain, _RP.HEALTHY, last_receipt=rcpt), effs


def _apply_probe(ds: _DS, ev: _EV_T, pol: _POL) -> _OUT:
    if ev.kind is _EV.PROBE_STARTED:
        pid = ev.probe_id.strip()
        if ds.phase is not _RP.PROBE_DUE or not pid:
            return ds, _rej(ds.domain, "missing_probe_id" if not pid else "probe_not_due")
        return replace(ds, phase=_RP.PONG_IN_FLIGHT, active_probe_id=pid), (RecoveryEffect(_EK.START_PONG_PROBE, ds.domain, "", None, pid),)
    if ds.phase is not _RP.PONG_IN_FLIGHT:
        return ds, _rej(ds.domain, "not_in_flight")
    if ev.probe_id and ds.active_probe_id and ev.probe_id != ds.active_probe_id:
        return ds, _rej(ds.domain, "stale_probe_id")
    return _fail_domain(ds, ev, pol, ev.error_code.strip() or "probe_failed")


def _apply_schedule_or_tick(ds: _DS, ev: _EV_T) -> _OUT:
    if ev.kind is _EV.SCHEDULE_PROBE:
        due = ds.phase is _RP.BLOCKED
    else:
        due = ds.phase is _RP.COOLDOWN and ds.cooldown_until_s is not None and ev.now_s >= ds.cooldown_until_s
    if due:
        return replace(ds, phase=_RP.PROBE_DUE, cooldown_until_s=None), (RecoveryEffect(_EK.PROBE_READY, ds.domain),)
    return ds, (() if ev.kind is _EV.TICK else _rej(ds.domain, "probe_schedule_invalid_phase"))


def _step_domain(ds: _DS, ev: _EV_T, exp: _EXP, pol: _POL) -> _OUT:
    if ev.kind is _EV.NON_PONG_SIGNAL:
        return ds, _rej(ds.domain, ev.evidence_kind.value if ev.evidence_kind else "non_pong_signal")
    if ev.kind in (_EV.TICK, _EV.SCHEDULE_PROBE):
        return _apply_schedule_or_tick(ds, ev)
    if ev.kind is _EV.FAILURE:
        return _fail_domain(ds, ev, pol, ev.error_code.strip() or "failure")
    return _apply_pong(ds, ev, exp, pol) if ev.kind is _EV.PONG_RECEIPT else _apply_probe(ds, ev, pol)


def transition(state: CodexRecoveryState, event: _EV_T, policy: _POL = DEFAULT_RECOVERY_POLICY) -> tuple[CodexRecoveryState, tuple[RecoveryEffect, ...]]:
    """Pure FSM transition(state, event) -> (new_state, effects) without I/O."""
    if not (-_INF < event.now_s < _INF):
        return state, _rej(event.domain or _HD.ROUTE, "invalid_timestamp")
    if event.domain is not None:
        targets: tuple[HealthDomain, ...] = (event.domain,)
    elif event.kind is _EV.TICK:
        targets = (_HD.ROUTE, _HD.CREDENTIAL)
    elif event.kind is _EV.FAILURE:
        targets = (classify_failure_domain(event.error_code),)
    else:
        return state, _rej(_HD.ROUTE, "missing_domain")
    route, cred, effects = state.route, state.credential, list[RecoveryEffect]()
    for target in targets:
        if target is _HD.ROUTE:
            route, eff = _step_domain(route, event, state.expectation, policy)
        else:
            cred, eff = _step_domain(cred, event, state.expectation, policy)
        effects.extend(eff)
    return replace(state, route=route, credential=cred), tuple(effects)


step = transition
