"""AGY bridge P1.2 PGID quarantine & unified orphan coordinator seam (W06)."""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.p12_flag_and_params import (
    FLAG_AGY_ORPHAN_COORDINATOR,
    FLAG_AGY_PGID_QUARANTINE,
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
)
from core.pgid_cleanup_policy import CleanupKey, CleanupState, GroupProbeStatus
from core.pgid_reaper import AlertCallback, BoundedPgidReaper, ReleaseCallback

from .orphan_coordinator import (
    CoordinatorContext,
    CoordinatorDecision,
    CoordinatorEvent,
    OrphanPhase,
    OrphanState,
    decide_agy_action,
)
from .process_supervisor import ProcessSupervisorConfig


@dataclass(frozen=True)
class DisconnectInput:
    """Bundled disconnect metadata to keep seam calls <= 5 args."""

    turn_id: str
    attempt_epoch: int
    tools_count: int
    ttfc_received: bool
    readers: int
    active_orphans: int
    orphan_max: int
    allow_orphan: bool
    fast_client_gone_enabled: bool


def sourced_agy_cleanup_params(cfg: ProcessSupervisorConfig | None = None) -> CleanupParamSnapshot:
    """Build sourced AGY cleanup parameters strictly from ProcessSupervisorConfig."""
    c = cfg or ProcessSupervisorConfig()
    src = "agy_runtime.process_supervisor.ProcessSupervisorConfig"
    return CleanupParamSnapshot(
        service="agy-bridge",
        term_grace_s=SourcedParam(c.kill_term_grace_s, f"{src}.kill_term_grace_s"),
        poll_interval_s=SourcedParam(c.poll_interval_s, f"{src}.poll_interval_s"),
        leader_wait_s=SourcedParam(c.kill_wait_s, f"{src}.kill_wait_s"),
    )


def capture_run_identity(run: object | None) -> int:
    """O(1) Darwin libproc start_time_us capture right after spawn (zero fork)."""
    if run is None:
        return 0
    proc = getattr(run, "proc", None)
    pid = int(getattr(proc, "pid", 0) or 0)
    if pid <= 1:
        return 0
    ident = darwin_probe_live_pid(pid)
    start_us = ident.start_time_us if ident is not None else 0
    try:
        setattr(run, "_p12_start_time_us", start_us)
    except Exception:
        pass
    return start_us


def _is_already_dead(proc: Any, pgid: int, probe: ProcProbePort) -> bool:
    try:
        leader_reaped = proc.poll() is not None
    except OSError:
        leader_reaped = True
    if not leader_reaped:
        return False
    return probe.probe_group(pgid) is GroupProbeStatus.GONE_ESRCH


class AgyP12CleanupSeam:
    """Single-responsibility seam wiring BoundedPgidReaper and orphan_coordinator for AGY."""

    def __init__(
        self,
        config_path: Path | None = None,
        *,
        params_snapshot: CleanupParamSnapshot | None = None,
        probe: ProcProbePort | None = None,
        on_alert: AlertCallback | None = None,
    ) -> None:
        self._params_snap = params_snapshot if params_snapshot is not None else sourced_agy_cleanup_params()
        self._flags = CachedDynamicFlagReader(config_path, env_path_var="AGY_DYNAMIC_CONFIG_PATH")
        self._probe: ProcProbePort = probe or PosixProcProbe()
        self._on_alert = on_alert
        self._epoch_seq = itertools.count(1)
        self._lock = threading.Lock()
        self._reaper: BoundedPgidReaper | None = None
        self._last_pgid_flag = False

    def next_epoch(self) -> int:
        return next(self._epoch_seq)

    def pgid_quarantine_enabled(self) -> bool:
        res = self._flags.resolve(FLAG_AGY_PGID_QUARANTINE, self._params_snap)
        if self._last_pgid_flag and not res.enabled and self._reaper is not None:
            self._reaper.notify_flag_off()
        self._last_pgid_flag = res.enabled
        return res.enabled

    def orphan_coordinator_enabled(self) -> bool:
        return self._flags.resolve(FLAG_AGY_ORPHAN_COORDINATOR, None).enabled

    def _get_reaper(self) -> BoundedPgidReaper:
        with self._lock:
            if self._reaper is None:
                validated: ValidatedCleanupParams = validate_cleanup_params(self._params_snap)
                self._reaper = BoundedPgidReaper(validated, probe=self._probe, on_alert=self._on_alert)
            return self._reaper

    def release_slot_after_run(
        self,
        release_fn: ReleaseCallback,
        run: object | None,
        turn_id: str,
        attempt_epoch: int | None = None,
    ) -> bool:
        """Release slot immediately if dead_confirmed or flag=False; else quarantine in reaper."""
        if not self.pgid_quarantine_enabled() or run is None:
            release_fn()
            return True
        proc = getattr(run, "proc", None)
        pid = int(getattr(proc, "pid", 0) or 0)
        if proc is None or pid <= 1:
            release_fn()
            return True
        if _is_already_dead(proc, pid, self._probe):
            release_fn()
            return True
        epoch = attempt_epoch if attempt_epoch is not None else self.next_epoch()
        start_us = int(getattr(run, "_p12_start_time_us", 0) or 0)
        key = CleanupKey(
            turn_id=turn_id or f"agy-{pid}",
            attempt_epoch=epoch,
            pgid=pid,
            leader_pid=pid,
            leader_start_time_us=start_us,
        )
        self._get_reaper().register_and_cancel(key, release_fn, reap_leader=proc.poll)
        return False

    def cleanup_state_for(self, turn_id: str, attempt_epoch: int) -> CleanupState:
        if self._reaper is None:
            return CleanupState.LIVE
        st = self._reaper.get_state(turn_id, attempt_epoch)
        return st if st is not None else CleanupState.LIVE

    def decide_attach(self, turn_id: str, attempt_epoch: int) -> CoordinatorDecision | None:
        """Return REJECT_409_CANCELLING or KEEP when flag #3 is on; None when off."""
        if not self.orphan_coordinator_enabled():
            return None
        c_state = self.cleanup_state_for(turn_id, attempt_epoch)
        ctx = CoordinatorContext(
            event=CoordinatorEvent.READER_ATTACH,
            orphan_state=OrphanState(False, 0, 1, False, OrphanPhase.NONE, False),
            readers=0,
            dead_confirmed=c_state in (CleanupState.DEAD_CONFIRMED, CleanupState.RELEASED),
            cleanup_state=c_state,
            epoch_ok=True,
        )
        return decide_agy_action(ctx)

    def decide_disconnect(self, info: DisconnectInput) -> CoordinatorDecision | None:
        """Authoritative single decision for AGY disconnect when flag #3 is on; None when off."""
        if not self.orphan_coordinator_enabled():
            return None
        c_state = self.cleanup_state_for(info.turn_id, info.attempt_epoch)
        phase = OrphanPhase.NONE if info.allow_orphan else OrphanPhase.ORPHAN_EXPIRED
        orphan = OrphanState(
            tools_active=info.tools_count > 0,
            active_orphans=info.active_orphans,
            orphan_max=info.orphan_max,
            ttfc_seen=info.ttfc_received,
            phase=phase,
            fast_client_gone_enabled=info.fast_client_gone_enabled,
        )
        ctx = CoordinatorContext(
            event=CoordinatorEvent.READER_DISCONNECT,
            orphan_state=orphan,
            readers=info.readers,
            dead_confirmed=c_state in (CleanupState.DEAD_CONFIRMED, CleanupState.RELEASED),
            cleanup_state=c_state,
            epoch_ok=True,
        )
        return decide_agy_action(ctx)

    def snapshot_counts(self) -> dict[str, int]:
        if self._reaper is None:
            return {"active": 0, "quarantined": 0, "bound": 128}
        return self._reaper.snapshot_counts()

    def shutdown(self, timeout_s: float = 1.0) -> None:
        if self._reaper is not None:
            self._reaper.shutdown(timeout_s=timeout_s)
