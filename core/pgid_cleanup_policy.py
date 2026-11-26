"""Pure Zero-I/O PGID cleanup and slot-quarantine FSM with Darwin EPERM & PID-reuse fencing (W02)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Final


class CleanupState(Enum):
    """Canonical lifecycle states of a PGID cleanup record."""

    LIVE = "live"
    TERM_SENT = "term_sent"
    KILL_SENT = "kill_sent"
    QUARANTINED = "quarantined"
    DEAD_CONFIRMED = "dead_confirmed"
    RELEASED = "released"


EVICTABLE_STATES: Final[frozenset[CleanupState]] = frozenset(
    {CleanupState.DEAD_CONFIRMED, CleanupState.RELEASED}
)
NON_EVICTABLE_STATES: Final[frozenset[CleanupState]] = frozenset(
    {CleanupState.LIVE, CleanupState.TERM_SENT, CleanupState.KILL_SENT, CleanupState.QUARANTINED}
)


class CleanupAction(Enum):
    """Side-effect instruction returned by pure FSM transitions for the I/O driver."""

    NOOP = "noop"
    NOOP_STALE = "noop_stale"
    SEND_TERM = "send_term"
    SEND_KILL = "send_kill"
    POLL_WAIT = "poll_wait"
    ALERT_QUARANTINE = "alert_quarantine"
    RELEASE_SLOT = "release_slot"


class GroupProbeStatus(Enum):
    """Normalized result of non-destructive PGID/group liveness check."""

    ALIVE = "alive"
    GONE_ESRCH = "gone_esrch"
    EPERM = "eperm"


@dataclass(frozen=True)
class CleanupKey:
    """Idempotency and fencing identity for one process-group attempt."""

    turn_id: str
    attempt_epoch: int
    pgid: int
    leader_pid: int
    leader_start_time_us: int
    uid: int = 0


@dataclass(frozen=True)
class CleanupRecord:
    """Immutable FSM state snapshot for a single tracked PGID."""

    key: CleanupKey
    state: CleanupState = CleanupState.LIVE
    leader_gone: bool = False
    group_gone: bool = False
    started_at_s: float = 0.0
    term_sent_at_s: float | None = None
    kill_sent_at_s: float | None = None
    alert_emitted: bool = False
    released: bool = False
    out_of_scope_setsid_logged: bool = False


@dataclass(frozen=True)
class ProbeObservation:
    """Pure snapshot produced by I/O driver (reap_leader + killpg(0) + proc_pidinfo)."""

    attempt_epoch: int
    now_s: float
    leader_reaped: bool
    leader_esrch: bool
    start_time_mismatch: bool
    group_status: GroupProbeStatus
    term_grace_s: float


@dataclass(frozen=True)
class TransitionResult:
    """Next immutable CleanupRecord and driver action."""

    record: CleanupRecord
    action: CleanupAction
    dead_confirmed: bool = False


def is_dead_confirmed(rec: CleanupRecord) -> bool:
    """Release gate: strictly leader_gone AND group_gone."""
    return rec.leader_gone and rec.group_gone


def request_cancel(rec: CleanupRecord, attempt_epoch: int, now_s: float) -> TransitionResult:
    """Initiate PGID cleanup idempotently; stale epochs and terminal states are NOOP."""
    if attempt_epoch != rec.key.attempt_epoch:
        return TransitionResult(rec, CleanupAction.NOOP_STALE)
    if rec.state is CleanupState.RELEASED or rec.state is CleanupState.DEAD_CONFIRMED:
        return TransitionResult(rec, CleanupAction.NOOP, dead_confirmed=True)
    if rec.state is CleanupState.LIVE:
        nxt = replace(rec, state=CleanupState.TERM_SENT, started_at_s=now_s, term_sent_at_s=now_s)
        return TransitionResult(nxt, CleanupAction.SEND_TERM)
    return TransitionResult(rec, CleanupAction.NOOP)


def _apply_probe_flags(rec: CleanupRecord, obs: ProbeObservation) -> CleanupRecord:
    # start_time_mismatch proves original leader exited (never signal leader_pid!),
    # while group_gone STILL requires killpg(pgid, 0) == ESRCH (no unsafe enterpgrp shortcut).
    leader_gone = rec.leader_gone or obs.leader_reaped or obs.leader_esrch or obs.start_time_mismatch
    group_gone = rec.group_gone or (obs.group_status is GroupProbeStatus.GONE_ESRCH)
    return replace(rec, leader_gone=leader_gone, group_gone=group_gone)


def _enter_dead_confirmed(rec: CleanupRecord) -> TransitionResult:
    if rec.released:
        nxt = replace(rec, state=CleanupState.RELEASED)
        return TransitionResult(nxt, CleanupAction.NOOP, dead_confirmed=True)
    nxt = replace(rec, state=CleanupState.DEAD_CONFIRMED, released=True)
    return TransitionResult(nxt, CleanupAction.RELEASE_SLOT, dead_confirmed=True)


def _handle_term_sent(rec: CleanupRecord, obs: ProbeObservation) -> TransitionResult:
    sent_at = rec.term_sent_at_s if rec.term_sent_at_s is not None else obs.now_s
    elapsed = obs.now_s - sent_at
    if elapsed >= max(0.0, obs.term_grace_s):
        nxt = replace(rec, state=CleanupState.KILL_SENT, kill_sent_at_s=obs.now_s)
        return TransitionResult(nxt, CleanupAction.SEND_KILL)
    return TransitionResult(rec, CleanupAction.POLL_WAIT)


def _handle_kill_sent(rec: CleanupRecord, obs: ProbeObservation) -> TransitionResult:
    if obs.group_status is GroupProbeStatus.EPERM or (rec.leader_gone and obs.group_status is GroupProbeStatus.ALIVE):
        should_alert = not rec.alert_emitted
        nxt = replace(rec, state=CleanupState.QUARANTINED, alert_emitted=True)
        return TransitionResult(nxt, CleanupAction.ALERT_QUARANTINE if should_alert else CleanupAction.POLL_WAIT)
    return TransitionResult(rec, CleanupAction.POLL_WAIT)


def _handle_quarantined(rec: CleanupRecord, _obs: ProbeObservation) -> TransitionResult:
    # Explicit exit from QUARANTINED happens at the top of step_probe when leader_gone AND group_gone!
    # Otherwise hold slot fail-closed; alert/flag_off/wall-clock NEVER release a quarantined slot.
    return TransitionResult(rec, CleanupAction.POLL_WAIT)


def step_probe(rec: CleanupRecord, obs: ProbeObservation) -> TransitionResult:
    """Advance PGID cleanup FSM using one pure probe observation."""
    if obs.attempt_epoch != rec.key.attempt_epoch:
        return TransitionResult(rec, CleanupAction.NOOP_STALE)
    if rec.state is CleanupState.RELEASED:
        return TransitionResult(rec, CleanupAction.NOOP, dead_confirmed=True)
    if rec.state is CleanupState.DEAD_CONFIRMED:
        return TransitionResult(replace(rec, state=CleanupState.RELEASED, released=True), CleanupAction.NOOP, dead_confirmed=True)
    updated = _apply_probe_flags(rec, obs)
    if is_dead_confirmed(updated):
        return _enter_dead_confirmed(updated)
    if updated.state is CleanupState.TERM_SENT:
        return _handle_term_sent(updated, obs)
    if updated.state is CleanupState.KILL_SENT:
        return _handle_kill_sent(updated, obs)
    if updated.state is CleanupState.QUARANTINED:
        return _handle_quarantined(updated, obs)
    return TransitionResult(updated, CleanupAction.NOOP)


def mark_released(rec: CleanupRecord, attempt_epoch: int) -> CleanupRecord:
    """Transition DEAD_CONFIRMED -> RELEASED after release callback succeeds."""
    if attempt_epoch != rec.key.attempt_epoch or not is_dead_confirmed(rec):
        return rec
    return replace(rec, state=CleanupState.RELEASED, released=True)


def handle_flag_off(rec: CleanupRecord) -> TransitionResult:
    """Idempotent rollback: disabling flag NEVER releases QUARANTINED or active cleanup."""
    if rec.state in (CleanupState.DEAD_CONFIRMED, CleanupState.RELEASED):
        return TransitionResult(rec, CleanupAction.NOOP, dead_confirmed=True)
    return TransitionResult(rec, CleanupAction.NOOP, dead_confirmed=False)


def handle_quarantine_alert_tick(rec: CleanupRecord) -> TransitionResult:
    """Event-driven alert tick in QUARANTINED: emits dedup alert, NEVER releases slot."""
    if rec.state is CleanupState.QUARANTINED:
        return TransitionResult(replace(rec, alert_emitted=True), CleanupAction.ALERT_QUARANTINE, dead_confirmed=False)
    return TransitionResult(rec, CleanupAction.NOOP, dead_confirmed=is_dead_confirmed(rec))
