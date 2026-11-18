"""Thread-safe lifecycle management for resident stdio processes."""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_io import ResidentProcessHandle, StdioProcessTerminated
from core.stdio_resident.process_reaper import is_pgid_alive
from core.stdio_resident.types import (
    SlotAffinityKey, SlotEffect, SlotEvent, SlotState, step_slot_fsm,
)


class SlotLeaseTimeoutError(Exception):
    """Raised when no resident-process slot becomes available in time."""


class PoolClosedError(Exception):
    """Raised when a lease is requested from a closed process pool."""


@dataclass
class _SlotEntry:
    """Mutable state owned by one process-pool slot."""

    slot_id: str
    affinity_key: SlotAffinityKey
    handle: ResidentProcessHandle
    state: SlotState
    last_used_mono: float
    lease_id: str | None = None
    is_ephemeral: bool = False
    dead: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock)


class ResidentProcessPool:
    """Allocate reusable subprocesses while enforcing bounded capacity."""

    def __init__(self, config: StdioPoolConfig | None = None) -> None:
        self._config: StdioPoolConfig = config or StdioPoolConfig.from_env()
        self._lock: threading.RLock = threading.RLock()
        self._cv: threading.Condition = threading.Condition(self._lock)
        self._slots: dict[str, _SlotEntry] = {}
        self._closed: bool = False

    def acquire(
        self,
        affinity_key: SlotAffinityKey,
        argv_builder: Callable[[], list[str]],
        cwd: str,
        env: Mapping[str, str] | None = None,
        is_ephemeral: bool = False,
    ) -> _SlotEntry:
        """Lease a live affinity-matched process or create one within capacity."""
        deadline = time.monotonic() + self._config.lease_wait_s
        with self._cv:
            while True:
                if self._closed:
                    raise PoolClosedError("resident process pool is closed")
                self._reap_quarantined_slots()
                self._remove_dead_ready_slots()
                if not is_ephemeral:
                    reusable = self._find_reusable(affinity_key)
                    if reusable is not None:
                        self._lease(reusable)
                        return reusable
                if self._try_make_room(affinity_key, is_ephemeral):
                    return self._spawn_and_lease(affinity_key, argv_builder, cwd, env, is_ephemeral)
                remaining_s = deadline - time.monotonic()
                if remaining_s <= 0.0:
                    raise SlotLeaseTimeoutError("timed out waiting for a resident process slot")
                has_dead = any(e.dead for e in self._slots.values())
                wait_s = min(remaining_s, 0.05) if has_dead else remaining_s
                if not self._cv.wait(timeout=wait_s) and not has_dead:
                    raise SlotLeaseTimeoutError("timed out waiting for a resident process slot")

    def release(
        self,
        slot_id: str,
        success: bool = True,
        cancel: bool = False,
        lease_id: str | None = None,
    ) -> None:
        """Return a successful lease or destroy an unsafe process."""
        with self._cv:
            entry = self._slots.get(slot_id)
            if entry is None or entry.lease_id is None:
                return
            if lease_id is not None and entry.lease_id != lease_id:
                return
            entry.lease_id = None
            if cancel or not success:
                start_ev = SlotEvent.CancelRequested if cancel else SlotEvent.WriteError
                end_ev = SlotEvent.CancelConfirmed if cancel else SlotEvent.TeardownDone
                _ = self._transition(entry, start_ev)
                try:
                    self._finish_teardown(entry, self._config.cancel_grace_s)
                finally:
                    _ = self._transition(entry, end_ev)
                    self._cv.notify_all()
                return
            effects = self._transition(entry, SlotEvent.TurnTerminal)
            if SlotEffect.AdvanceGeneration in effects:
                _ = entry.handle.advance_generation()
            now = time.monotonic()
            entry.last_used_mono = now
            expired = now - entry.handle.created_at_mono > self._config.ttl_s
            if entry.is_ephemeral or entry.state is not SlotState.READY or expired:
                if entry.state is SlotState.READY:
                    ev = SlotEvent.TtlExpired if expired else SlotEvent.Shutdown
                    _ = self._transition(entry, ev)
                try:
                    self._finish_teardown(entry, self._config.cancel_grace_s)
                finally:
                    self._cv.notify_all()
                return
            self._cv.notify_all()

    async def drain_and_shutdown(self, timeout_s: float | None = None) -> None:
        """Close idle slots, wait for active leases up to timeout, then shut down."""
        grace_s = max(0.0, self._config.shutdown_timeout_s if timeout_s is None else timeout_s)
        deadline = time.monotonic() + grace_s
        idle_entries: list[_SlotEntry] = []
        with self._cv:
            if self._closed and not self._slots:
                return
            self._closed = True
            for entry in list(self._slots.values()):
                if entry.dead:
                    continue
                if entry.state is SlotState.READY:
                    _ = self._transition(entry, SlotEvent.Drain)
                    _ = self._slots.pop(entry.slot_id, None)
                    idle_entries.append(entry)
                elif entry.lease_id is not None:
                    _ = self._transition(entry, SlotEvent.Drain)
            self._cv.notify_all()
        err = self._terminate_entries(idle_entries, min(grace_s, self._config.cancel_grace_s))
        while time.monotonic() < deadline:
            with self._cv:
                if not any(e.lease_id is not None for e in self._slots.values()):
                    break
            await asyncio.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
        try:
            self.shutdown(timeout_s=grace_s)
        except StdioProcessTerminated as exc:
            err = err or exc
        if err is not None:
            raise err

    def shutdown(self, timeout_s: float | None = None) -> None:
        """Close the pool and terminate every child process."""
        grace_s = self._config.shutdown_timeout_s if timeout_s is None else timeout_s
        with self._cv:
            if self._closed and not self._slots:
                return
            self._closed = True
            entries = list(self._slots.values())
            for entry in entries:
                entry.lease_id = None
                _ = self._transition(entry, SlotEvent.Shutdown)
            self._slots.clear()
            self._cv.notify_all()
        err = self._terminate_entries(entries, grace_s)
        if err is not None:
            raise err

    def _try_make_room(self, affinity_key: SlotAffinityKey, is_ephemeral: bool) -> bool:
        if is_ephemeral:
            eph_count = sum(1 for e in self._slots.values() if e.is_ephemeral)
            return eph_count < self._config.max_ephemeral_slots
        principal_limit = self._config.max_slots_per_principal or self._config.max_slots
        while True:
            hot_slots = [e for e in self._slots.values() if not e.is_ephemeral]
            principal_slots = [
                e for e in hot_slots if e.affinity_key.owner_hash == affinity_key.owner_hash
            ]
            if len(principal_slots) >= principal_limit:
                victim = self._least_recently_used_ready(principal_slots)
            elif len(hot_slots) < self._config.max_slots:
                return True
            else:
                victim = self._least_recently_used_ready(hot_slots)
            if victim is None:
                return False
            self._close_slot(victim, self._config.cancel_grace_s)

    def _find_reusable(self, affinity_key: SlotAffinityKey) -> _SlotEntry | None:
        for entry in self._slots.values():
            if (
                not entry.is_ephemeral and not entry.dead
                and entry.affinity_key == affinity_key
                and entry.state is SlotState.READY and entry.handle.is_alive()
            ):
                return entry
        return None

    def _reap_quarantined_slots(self) -> None:
        for entry in list(self._slots.values()):
            if not entry.dead:
                continue
            pgid = getattr(entry.handle, "_pgid", getattr(entry.handle, "pid", 0))
            if not is_pgid_alive(pgid):
                if hasattr(entry.handle, "_pgid_dead"):
                    entry.handle._pgid_dead = True
                _ = self._slots.pop(entry.slot_id, None)

    def _remove_dead_ready_slots(self) -> None:
        dead = [
            e for e in self._slots.values()
            if not e.dead and e.state is SlotState.READY and not e.handle.is_alive()
        ]
        for entry in dead:
            _ = self._transition(entry, SlotEvent.Eof)
            self._finish_teardown(entry, self._config.cancel_grace_s)

    @staticmethod
    def _least_recently_used_ready(entries: Iterable[_SlotEntry]) -> _SlotEntry | None:
        ready = [e for e in entries if not e.dead and e.state is SlotState.READY]
        return min(ready, key=lambda entry: entry.last_used_mono, default=None)

    def _spawn_and_lease(
        self, affinity_key: SlotAffinityKey, argv_builder: Callable[[], list[str]],
        cwd: str, env: Mapping[str, str] | None, is_ephemeral: bool = False,
    ) -> _SlotEntry:
        handle = ResidentProcessHandle.spawn(argv_builder(), cwd=cwd, env=env)
        entry = _SlotEntry(
            slot_id=uuid.uuid4().hex, affinity_key=affinity_key, handle=handle,
            state=SlotState.SPAWNING, last_used_mono=time.monotonic(),
            is_ephemeral=is_ephemeral,
        )
        _ = self._transition(entry, SlotEvent.InitOk)
        self._slots[entry.slot_id] = entry
        if entry.handle.is_alive():
            _ = self._transition(entry, SlotEvent.HandshakeOk)
        else:
            _ = self._transition(entry, SlotEvent.HandshakeFailed)
            self._finish_teardown(entry, self._config.cancel_grace_s)
            raise StdioProcessTerminated("resident process terminated during handshake")
        self._lease(entry)
        return entry

    def _lease(self, entry: _SlotEntry) -> None:
        _ = self._transition(entry, SlotEvent.Lease)
        entry.lease_id = uuid.uuid4().hex
        entry.last_used_mono = time.monotonic()

    def _close_slot(self, entry: _SlotEntry, grace_s: float) -> None:
        _ = self._transition(entry, SlotEvent.Shutdown)
        self._finish_teardown(entry, grace_s)

    def _finish_teardown(self, entry: _SlotEntry, grace_s: float) -> None:
        entry.lease_id = None
        try:
            self._terminate(entry, grace_s)
        finally:
            if getattr(entry.handle, "_pgid_dead", True):
                _ = self._slots.pop(entry.slot_id, None)
            else:
                entry.dead = True

    def _terminate_entries(
        self, entries: list[_SlotEntry], grace_s: float
    ) -> StdioProcessTerminated | None:
        err: StdioProcessTerminated | None = None
        for entry in entries:
            try:
                self._terminate(entry, grace_s)
            except StdioProcessTerminated as exc:
                err = err or exc
        return err

    @staticmethod
    def _transition(entry: _SlotEntry, event: SlotEvent) -> list[SlotEffect]:
        next_state, effects = step_slot_fsm(entry.state, event)
        entry.state = next_state
        return effects

    @staticmethod
    def _terminate(entry: _SlotEntry, grace_s: float) -> None:
        _ = entry.handle.terminate_gracefully(grace_s=max(0.0, grace_s))
