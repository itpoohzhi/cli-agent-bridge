"""Exhaustive L1 Zero-I/O tests for core/pgid_cleanup_policy.py (W02)."""

from __future__ import annotations

import ast
from pathlib import Path

from core.pgid_cleanup_policy import (
    EVICTABLE_STATES,
    NON_EVICTABLE_STATES,
    CleanupAction,
    CleanupKey,
    CleanupRecord,
    CleanupState,
    GroupProbeStatus,
    ProbeObservation,
    handle_flag_off,
    handle_quarantine_alert_tick,
    is_dead_confirmed,
    mark_released,
    request_cancel,
    step_probe,
)


def _key(epoch: int = 1) -> CleanupKey:
    return CleanupKey(turn_id="t-1", attempt_epoch=epoch, pgid=4200, leader_pid=4200, leader_start_time_us=123456789, uid=501)


def _obs(
    *,
    epoch: int = 1,
    now_s: float = 10.0,
    reaped: bool = False,
    leader_esrch: bool = False,
    mismatch: bool = False,
    group: GroupProbeStatus = GroupProbeStatus.ALIVE,
    grace: float = 2.0,
) -> ProbeObservation:
    return ProbeObservation(
        attempt_epoch=epoch,
        now_s=now_s,
        leader_reaped=reaped,
        leader_esrch=leader_esrch,
        start_time_mismatch=mismatch,
        group_status=group,
        term_grace_s=grace,
    )


def test_full_term_kill_release_lifecycle() -> None:
    rec = CleanupRecord(key=_key())
    r1 = request_cancel(rec, attempt_epoch=1, now_s=10.0)
    assert r1.action is CleanupAction.SEND_TERM
    assert r1.record.state is CleanupState.TERM_SENT

    # Duplicate cancel is idempotent NOOP
    dup = request_cancel(r1.record, attempt_epoch=1, now_s=10.5)
    assert dup.action is CleanupAction.NOOP
    assert dup.record.state is CleanupState.TERM_SENT

    # Before grace expires -> POLL_WAIT
    r2 = step_probe(r1.record, _obs(now_s=11.0, group=GroupProbeStatus.ALIVE))
    assert r2.action is CleanupAction.POLL_WAIT
    assert r2.record.state is CleanupState.TERM_SENT
    assert not is_dead_confirmed(r2.record)

    # Grace expires -> SEND_KILL
    r3 = step_probe(r2.record, _obs(now_s=12.0, group=GroupProbeStatus.ALIVE))
    assert r3.action is CleanupAction.SEND_KILL
    assert r3.record.state is CleanupState.KILL_SENT

    # Leader reaped + group ESRCH -> DEAD_CONFIRMED + RELEASE_SLOT once
    r4 = step_probe(r3.record, _obs(now_s=12.2, reaped=True, group=GroupProbeStatus.GONE_ESRCH))
    assert r4.action is CleanupAction.RELEASE_SLOT
    assert r4.dead_confirmed is True
    assert r4.record.state is CleanupState.DEAD_CONFIRMED

    # mark_released -> RELEASED; further probes/cancels are NOOP
    done = mark_released(r4.record, attempt_epoch=1)
    assert done.state is CleanupState.RELEASED
    assert step_probe(done, _obs(now_s=13.0, reaped=True, group=GroupProbeStatus.GONE_ESRCH)).action is CleanupAction.NOOP
    assert request_cancel(done, attempt_epoch=1, now_s=14.0).action is CleanupAction.NOOP


def test_quarantine_entry_hold_and_explicit_exit_on_dead_confirmed() -> None:
    rec = request_cancel(CleanupRecord(key=_key()), 1, 10.0).record
    kill_rec = step_probe(rec, _obs(now_s=12.5, group=GroupProbeStatus.ALIVE)).record
    assert kill_rec.state is CleanupState.KILL_SENT

    # EPERM on live group -> QUARANTINED + ALERT_QUARANTINE
    q1 = step_probe(kill_rec, _obs(now_s=13.0, reaped=True, group=GroupProbeStatus.EPERM))
    assert q1.record.state is CleanupState.QUARANTINED
    assert q1.action is CleanupAction.ALERT_QUARANTINE
    assert q1.dead_confirmed is False

    # Alert tick & flag_off NEVER release slot
    at = handle_quarantine_alert_tick(q1.record)
    assert at.action is CleanupAction.ALERT_QUARANTINE
    assert at.dead_confirmed is False
    fo = handle_flag_off(q1.record)
    assert fo.action is CleanupAction.NOOP
    assert fo.record.state is CleanupState.QUARANTINED
    assert fo.dead_confirmed is False

    # Still EPERM -> stays QUARANTINED
    q2 = step_probe(q1.record, _obs(now_s=600.0, reaped=True, group=GroupProbeStatus.EPERM))
    assert q2.record.state is CleanupState.QUARANTINED
    assert q2.action is CleanupAction.POLL_WAIT

    # Explicit exit: once group becomes ESRCH -> DEAD_CONFIRMED -> RELEASE_SLOT
    q3 = step_probe(q2.record, _obs(now_s=605.0, reaped=True, group=GroupProbeStatus.GONE_ESRCH))
    assert q3.record.state is CleanupState.DEAD_CONFIRMED
    assert q3.action is CleanupAction.RELEASE_SLOT
    assert q3.dead_confirmed is True


def test_start_time_mismatch_requires_group_gone_never_premature_release() -> None:
    rec = request_cancel(CleanupRecord(key=_key()), 1, 10.0).record
    # Leader PID reused (mismatch=True) while grandchildren STILL alive in pgid (group=ALIVE)
    r1 = step_probe(rec, _obs(now_s=11.0, mismatch=True, group=GroupProbeStatus.ALIVE))
    assert r1.record.leader_gone is True
    assert r1.record.group_gone is False
    assert r1.dead_confirmed is False
    assert r1.action is CleanupAction.POLL_WAIT

    # Escalates to KILL_SENT on grace expiry to kill remaining grandchildren in old pgid
    r2 = step_probe(r1.record, _obs(now_s=12.5, mismatch=True, group=GroupProbeStatus.ALIVE))
    assert r2.action is CleanupAction.SEND_KILL
    assert r2.record.state is CleanupState.KILL_SENT

    # Only when group_gone (ESRCH) -> RELEASE_SLOT
    r3 = step_probe(r2.record, _obs(now_s=13.0, mismatch=True, group=GroupProbeStatus.GONE_ESRCH))
    assert r3.action is CleanupAction.RELEASE_SLOT
    assert r3.dead_confirmed is True


def test_stale_epoch_is_strictly_noop_stale() -> None:
    rec = request_cancel(CleanupRecord(key=_key(epoch=2)), 2, 10.0).record
    assert request_cancel(rec, attempt_epoch=1, now_s=11.0).action is CleanupAction.NOOP_STALE
    res = step_probe(rec, _obs(epoch=1, now_s=20.0, reaped=True, group=GroupProbeStatus.GONE_ESRCH))
    assert res.action is CleanupAction.NOOP_STALE
    assert res.record.state is CleanupState.TERM_SENT
    assert not res.dead_confirmed


def test_evictable_partition_and_zero_io() -> None:
    assert EVICTABLE_STATES | NON_EVICTABLE_STATES == set(CleanupState)
    assert EVICTABLE_STATES & NON_EVICTABLE_STATES == set()
    src = Path(__file__).resolve().parents[1] / "core/pgid_cleanup_policy.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    forbidden = {"os", "subprocess", "socket", "time", "pathlib", "ctypes"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden
