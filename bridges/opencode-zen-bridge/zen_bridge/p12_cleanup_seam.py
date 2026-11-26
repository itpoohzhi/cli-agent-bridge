"""OpenCode Zen bridge P1.2 PGID quarantine & fallback dead-confirmation seam (W08)."""

from __future__ import annotations

import itertools
import threading
import time
from pathlib import Path
from typing import Any

from core.p12_flag_and_params import (
    FLAG_ZEN_PGID_QUARANTINE,
    CleanupParamSnapshot,
    SourcedParam,
    ValidatedCleanupParams,
    validate_cleanup_params,
)
from core.pgid_cleanup_driver import (
    CachedDynamicFlagReader,
    PosixProcProbe,
    ProcProbePort,
    darwin_probe_live_pid,
    execute_cleanup_step,
)
from core.pgid_cleanup_policy import CleanupKey, CleanupRecord, CleanupState, GroupProbeStatus
from core.pgid_reaper import AlertCallback, BoundedPgidReaper, ReleaseCallback


def sourced_zen_cleanup_params(
    *,
    term_grace_s: float = 0.5,
    poll_interval_s: float = 0.05,
    leader_wait_s: float = 2.0,
) -> CleanupParamSnapshot:
    """Sourced opencode-zen cleanup timings from _stop_proc (0.5s/0.05s) and _ServeLease (2.0s)."""
    src = "bridges/opencode-zen-bridge/server.py:_stop_proc&_ServeLease.cleanup"
    return CleanupParamSnapshot(
        service="opencode-zen-bridge",
        term_grace_s=SourcedParam(term_grace_s, f"{src}.term_grace_s"),
        poll_interval_s=SourcedParam(poll_interval_s, f"{src}.poll_interval_s"),
        leader_wait_s=SourcedParam(leader_wait_s, f"{src}.leader_wait_s"),
    )


def capture_proc_identity(proc: Any | None) -> int:
    """O(1) Darwin libproc start_time_us capture right after spawn."""
    pid = int(getattr(proc, "pid", 0) or 0)
    if pid <= 1:
        return 0
    ident = darwin_probe_live_pid(pid)
    start_us = ident.start_time_us if ident is not None else 0
    try:
        setattr(proc, "_p12_start_time_us", start_us)
    except Exception:
        pass
    return start_us


def _is_proc_group_dead(proc: Any, pgid: int, probe: ProcProbePort) -> bool:
    try:
        leader_reaped = proc.poll() is not None
    except OSError:
        leader_reaped = True
    return leader_reaped and probe.probe_group(pgid) is GroupProbeStatus.GONE_ESRCH


def _resolve_pid_pgid(proc: Any | None, pgid: int | None) -> tuple[int, int] | None:
    if proc is None:
        return None
    pid = int(getattr(proc, "pid", 0) or 0)
    eff_pgid = int(pgid) if (pgid is not None and pgid > 1) else pid
    if pid <= 1 or eff_pgid <= 1:
        return None
    return pid, eff_pgid


def _build_key(turn_id: str, prefix: str, epoch: int, ids: tuple[int, int], proc: Any) -> CleanupKey:
    pid, eff_pgid = ids
    start_us = int(getattr(proc, "_p12_start_time_us", 0) or 0)
    return CleanupKey(
        turn_id=turn_id or f"{prefix}-{pid}",
        attempt_epoch=epoch,
        pgid=eff_pgid,
        leader_pid=pid,
        leader_start_time_us=start_us,
    )


class ZenP12CleanupSeam:
    """Bounded PGID quarantine & pre-fallback dead confirmation for opencode-zen-bridge."""

    def __init__(
        self,
        config_path: Path | None = None,
        *,
        params_snapshot: CleanupParamSnapshot | None = None,
        probe: ProcProbePort | None = None,
        on_alert: AlertCallback | None = None,
    ) -> None:
        self._params_snap = params_snapshot if params_snapshot is not None else sourced_zen_cleanup_params()
        self._flags = CachedDynamicFlagReader(config_path, env_path_var="OPENCODE_ZEN_DYNAMIC_CONFIG_PATH")
        self._probe: ProcProbePort = probe or PosixProcProbe()
        self._on_alert = on_alert
        self._epoch_seq = itertools.count(1)
        self._lock = threading.Lock()
        self._reaper: BoundedPgidReaper | None = None
        self._last_flag = False

    def next_epoch(self) -> int:
        return next(self._epoch_seq)

    def pgid_quarantine_enabled(self) -> bool:
        res = self._flags.resolve(FLAG_ZEN_PGID_QUARANTINE, self._params_snap)
        if self._last_flag and not res.enabled and self._reaper is not None:
            self._reaper.notify_flag_off()
        self._last_flag = res.enabled
        return res.enabled

    def _get_reaper(self) -> BoundedPgidReaper:
        with self._lock:
            if self._reaper is None:
                validated: ValidatedCleanupParams = validate_cleanup_params(self._params_snap)
                self._reaper = BoundedPgidReaper(validated, probe=self._probe, on_alert=self._on_alert)
            return self._reaper

    def release_slot_after_proc(
        self,
        release_fn: ReleaseCallback,
        proc: Any | None,
        turn_id: str,
        pgid: int | None = None,
    ) -> bool:
        """Release slot immediately if flag=False or dead_confirmed; else quarantine PGID."""
        ids = _resolve_pid_pgid(proc, pgid)
        if not self.pgid_quarantine_enabled() or ids is None:
            release_fn()
            return True
        if _is_proc_group_dead(proc, ids[1], self._probe):
            release_fn()
            return True
        key = _build_key(turn_id, "zen", self.next_epoch(), ids, proc)
        self._get_reaper().register_and_cancel(key, release_fn, reap_leader=proc.poll)
        return False

    def _wait_cleanup_confirm(self, key: CleanupKey, proc: Any, validated: ValidatedCleanupParams) -> bool:
        rec = CleanupRecord(key=key)
        deadline = self._probe.now_s() + validated.term_grace_s + validated.leader_wait_s
        while True:
            res = execute_cleanup_step(rec, proc.poll, validated.term_grace_s, self._probe)
            rec = res.record
            if res.dead_confirmed:
                return True
            if rec.state is CleanupState.QUARANTINED or self._probe.now_s() >= deadline:
                return False
            time.sleep(validated.poll_interval_s)

    def confirm_dead_before_fallback(
        self,
        proc: Any | None,
        turn_id: str,
        pgid: int | None = None,
    ) -> bool:
        """Before spawning fallback CLI, require prior serve PGID dead_confirmed (fail-closed)."""
        ids = _resolve_pid_pgid(proc, pgid)
        if not self.pgid_quarantine_enabled() or ids is None:
            return True
        if _is_proc_group_dead(proc, ids[1], self._probe):
            return True
        validated = validate_cleanup_params(self._params_snap)
        key = _build_key(turn_id, "zen-fb", self.next_epoch(), ids, proc)
        return self._wait_cleanup_confirm(key, proc, validated)

    def snapshot_counts(self) -> dict[str, int]:
        if self._reaper is None:
            return {"active": 0, "quarantined": 0, "bound": 128}
        return self._reaper.snapshot_counts()

    def shutdown(self, timeout_s: float = 1.0) -> None:
        if self._reaper is not None:
            self._reaper.shutdown(timeout_s=timeout_s)
