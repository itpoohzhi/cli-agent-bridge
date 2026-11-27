"""Single O(1) bounded PGID reaper thread per bridge process (W03)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from core.p12_flag_and_params import ValidatedCleanupParams
from core.pgid_cleanup_driver import PosixProcProbe, ProcProbePort, ReapLeaderFn, execute_cleanup_step
from core.pgid_cleanup_policy import (
    EVICTABLE_STATES,
    CleanupAction,
    CleanupKey,
    CleanupRecord,
    CleanupState,
    handle_flag_off,
    mark_released,
)

DEFAULT_REAPER_BOUND: Final[int] = 128

ReleaseCallback = Callable[[], None]
AlertCallback = Callable[[CleanupKey, str], None]


@dataclass
class _Entry:
    record: CleanupRecord
    reap_leader: ReapLeaderFn | None
    on_release: ReleaseCallback
    term_grace_s: float
    release_invoked: bool = False


class ReaperCapacityError(RuntimeError):
    """Raised when non-evictable entries saturate reaper capacity."""


class BoundedPgidReaper:
    """O(1)-thread bounded PGID cleanup & quarantine manager.

    Invariants:
    - Never evicts LIVE, TERM_SENT, KILL_SENT, or QUARANTINED entries.
    - Invokes on_release AT MOST ONCE and STRICTLY on dead_confirmed==True.
    - Graceful shutdown stops ticker WITHOUT releasing quarantined slots.
    - flag_off on active/quarantined entries is a fail-closed NOOP.
    """

    def __init__(
        self,
        params: ValidatedCleanupParams,
        *,
        bound: int = DEFAULT_REAPER_BOUND,
        probe: ProcProbePort | None = None,
        on_alert: AlertCallback | None = None,
    ) -> None:
        self._params = params
        self._bound = max(DEFAULT_REAPER_BOUND, int(bound))
        self._probe: ProcProbePort = probe or PosixProcProbe()
        self._on_alert = on_alert
        self._lock = threading.Lock()
        self._entries: dict[tuple[str, int], _Entry] = {}
        self._stop_ev = threading.Event()
        self._thread: threading.Thread | None = None

    def _evict_terminal_locked(self) -> None:
        stale = [k for k, e in self._entries.items() if e.record.state in EVICTABLE_STATES]
        for k in stale:
            del self._entries[k]

    def _ensure_thread_locked(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_ev.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"pgid-reaper-{self._params.service}",
            daemon=True,
        )
        self._thread.start()

    def register_and_cancel(
        self,
        key: CleanupKey,
        on_release: ReleaseCallback,
        *,
        reap_leader: ReapLeaderFn | None = None,
        start_ticker: bool = True,
    ) -> CleanupRecord:
        """Register PGID attempt and immediately issue TERM; fail-closed if saturated."""
        slot_id = (key.turn_id, key.attempt_epoch)
        with self._lock:
            if slot_id in self._entries:
                return self._entries[slot_id].record
            if len(self._entries) >= self._bound:
                self._evict_terminal_locked()
            if len(self._entries) >= self._bound:
                raise ReaperCapacityError(f"reaper saturated at bound={self._bound}")
            rec = CleanupRecord(key=key)
            res = execute_cleanup_step(rec, reap_leader, self._params.term_grace_s, self._probe)
            self._entries[slot_id] = _Entry(
                record=res.record,
                reap_leader=reap_leader,
                on_release=on_release,
                term_grace_s=self._params.term_grace_s,
            )
            if start_ticker:
                self._ensure_thread_locked()
            return res.record

    def _step_one_entry(self, entry: _Entry) -> tuple[bool, CleanupKey | None]:
        res = execute_cleanup_step(entry.record, entry.reap_leader, entry.term_grace_s, self._probe)
        entry.record = res.record
        alert_key = entry.record.key if res.action is CleanupAction.ALERT_QUARANTINE else None
        should_release = res.dead_confirmed and not entry.release_invoked
        if should_release:
            entry.release_invoked = True
            entry.record = mark_released(entry.record, entry.record.key.attempt_epoch)
        return should_release, alert_key

    def _collect_tick_locked(self) -> tuple[list[ReleaseCallback], list[CleanupKey]]:
        releases: list[ReleaseCallback] = []
        alerts: list[CleanupKey] = []
        for k in list(self._entries):
            entry = self._entries[k]
            if entry.record.state in EVICTABLE_STATES:
                continue
            do_release, alert_key = self._step_one_entry(entry)
            if do_release:
                releases.append(entry.on_release)
            if alert_key is not None:
                alerts.append(alert_key)
        return releases, alerts

    def tick_once(self) -> int:
        """Advance all non-terminal entries by one deterministic step."""
        with self._lock:
            releases, alerts = self._collect_tick_locked()
        for cb in releases:
            cb()
        if self._on_alert is not None:
            for akey in alerts:
                self._on_alert(akey, "pgid_quarantined")
        return len(releases)

    def notify_flag_off(self) -> None:
        """Idempotent rollback signal: active/quarantined slots stay held."""
        with self._lock:
            for entry in self._entries.values():
                res = handle_flag_off(entry.record)
                entry.record = res.record

    def snapshot_counts(self) -> dict[str, int]:
        """Observability counts without mutating /health 7-key schema."""
        with self._lock:
            quarantined = sum(1 for e in self._entries.values() if e.record.state is CleanupState.QUARANTINED)
            active = sum(1 for e in self._entries.values() if e.record.state not in EVICTABLE_STATES)
            return {"active": active, "quarantined": quarantined, "bound": self._bound}

    def get_state(self, turn_id: str, attempt_epoch: int) -> CleanupState | None:
        with self._lock:
            entry = self._entries.get((turn_id, attempt_epoch))
            return entry.record.state if entry is not None else None

    def _run_loop(self) -> None:
        cadence = self._params.poll_interval_s
        while not self._stop_ev.wait(timeout=cadence):
            self.tick_once()
            with self._lock:
                has_active = any(e.record.state not in EVICTABLE_STATES for e in self._entries.values())
                if not has_active:
                    return

    def shutdown(self, timeout_s: float = 1.0) -> None:
        """Graceful ticker stop; NEVER invokes on_release for active/quarantined entries."""
        self._stop_ev.set()
        with self._lock:
            thr = self._thread
        if thr is not None and thr.is_alive():
            thr.join(timeout=max(0.0, timeout_s))
