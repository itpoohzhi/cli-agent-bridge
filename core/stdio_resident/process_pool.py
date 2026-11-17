"""Thread-safe lifecycle management for resident stdio processes."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_io import (
    ResidentProcessHandle,
    StdioProcessTerminated,
)
from core.stdio_resident.types import (
    SlotAffinityKey,
    SlotEffect,
    SlotEvent,
    SlotState,
    step_slot_fsm,
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
    ) -> _SlotEntry:
        """Lease a live affinity-matched process or create one within capacity."""

        deadline = time.monotonic() + self._config.lease_wait_s
        with self._cv:
            while True:
                if self._closed:
                    raise PoolClosedError("resident process pool is closed")

                reusable = self._find_reusable(affinity_key)
                if reusable is not None:
                    self._lease(reusable)
                    return reusable

                self._remove_dead_ready_slots()
                if len(self._slots) < self._config.max_slots:
                    return self._spawn_and_lease(
                        affinity_key=affinity_key,
                        argv_builder=argv_builder,
                        cwd=cwd,
                        env=env,
                    )

                victim = self._least_recently_used_ready()
                if victim is not None:
                    self._close_slot(victim, self._config.cancel_grace_s)
                    return self._spawn_and_lease(
                        affinity_key=affinity_key,
                        argv_builder=argv_builder,
                        cwd=cwd,
                        env=env,
                    )

                remaining_s = deadline - time.monotonic()
                if remaining_s <= 0.0 or not self._cv.wait(timeout=remaining_s):
                    raise SlotLeaseTimeoutError(
                        "timed out waiting for a resident process slot"
                    )

    def release(
        self,
        slot_id: str,
        success: bool = True,
        cancel: bool = False,
    ) -> None:
        """Return a successful lease or destroy an unsafe process."""

        with self._cv:
            entry = self._slots.get(slot_id)
            if entry is None:
                return

            if cancel:
                _ = self._transition(entry, SlotEvent.CancelRequested)
                try:
                    _ = self._terminate(entry, self._config.cancel_grace_s)
                finally:
                    _ = self._transition(entry, SlotEvent.CancelConfirmed)
                    _ = self._slots.pop(slot_id, None)
                    self._cv.notify()
                return

            if not success:
                _ = self._transition(entry, SlotEvent.WriteError)
                try:
                    _ = self._terminate(entry, self._config.cancel_grace_s)
                finally:
                    _ = self._transition(entry, SlotEvent.TeardownDone)
                    _ = self._slots.pop(slot_id, None)
                    self._cv.notify()
                return

            effects = self._transition(entry, SlotEvent.TurnTerminal)
            if SlotEffect.AdvanceGeneration in effects:
                _ = entry.handle.advance_generation()
            if entry.state is not SlotState.READY:
                return

            now = time.monotonic()
            entry.last_used_mono = now
            if now - entry.handle.created_at_mono > self._config.ttl_s:
                _ = self._transition(entry, SlotEvent.TtlExpired)
                _ = self._terminate(entry, self._config.cancel_grace_s)
                _ = self._slots.pop(slot_id, None)
            self._cv.notify()

    def shutdown(self, timeout_s: float | None = None) -> None:
        """Close the pool and terminate every child process."""

        grace_s = self._config.shutdown_timeout_s if timeout_s is None else timeout_s
        with self._cv:
            if self._closed and not self._slots:
                return
            self._closed = True
            entries = list(self._slots.values())
            for entry in entries:
                _ = self._transition(entry, SlotEvent.Shutdown)
            self._slots.clear()
            self._cv.notify_all()

        termination_error: StdioProcessTerminated | None = None
        for entry in entries:
            try:
                self._terminate(entry, grace_s)
            except StdioProcessTerminated as exc:
                if termination_error is None:
                    termination_error = exc
        if termination_error is not None:
            raise termination_error

    def _find_reusable(self, affinity_key: SlotAffinityKey) -> _SlotEntry | None:
        for entry in self._slots.values():
            if (
                entry.affinity_key == affinity_key
                and entry.state is SlotState.READY
                and entry.handle.is_alive()
            ):
                return entry
        return None

    def _remove_dead_ready_slots(self) -> None:
        dead = [
            entry
            for entry in self._slots.values()
            if entry.state is SlotState.READY and not entry.handle.is_alive()
        ]
        for entry in dead:
            _ = self._transition(entry, SlotEvent.Eof)
            _ = self._terminate(entry, self._config.cancel_grace_s)
            _ = self._slots.pop(entry.slot_id, None)

    def _least_recently_used_ready(self) -> _SlotEntry | None:
        ready = [
            entry for entry in self._slots.values() if entry.state is SlotState.READY
        ]
        return min(ready, key=lambda entry: entry.last_used_mono, default=None)

    def _spawn_and_lease(
        self,
        affinity_key: SlotAffinityKey,
        argv_builder: Callable[[], list[str]],
        cwd: str,
        env: Mapping[str, str] | None,
    ) -> _SlotEntry:
        handle = ResidentProcessHandle.spawn(argv_builder(), cwd=cwd, env=env)
        entry = _SlotEntry(
            slot_id=uuid.uuid4().hex,
            affinity_key=affinity_key,
            handle=handle,
            state=SlotState.SPAWNING,
            last_used_mono=time.monotonic(),
        )
        _ = self._transition(entry, SlotEvent.InitOk)
        if entry.handle.is_alive():
            _ = self._transition(entry, SlotEvent.HandshakeOk)
        else:
            _ = self._transition(entry, SlotEvent.HandshakeFailed)
            self._terminate(entry, self._config.cancel_grace_s)
            raise StdioProcessTerminated(
                "resident process terminated during handshake"
            )
        self._slots[entry.slot_id] = entry
        self._lease(entry)
        return entry

    def _lease(self, entry: _SlotEntry) -> None:
        _ = self._transition(entry, SlotEvent.Lease)
        entry.last_used_mono = time.monotonic()

    def _close_slot(self, entry: _SlotEntry, grace_s: float) -> None:
        _ = self._transition(entry, SlotEvent.Shutdown)
        _ = self._terminate(entry, grace_s)
        _ = self._slots.pop(entry.slot_id, None)

    @staticmethod
    def _transition(entry: _SlotEntry, event: SlotEvent) -> list[SlotEffect]:
        next_state, effects = step_slot_fsm(entry.state, event)
        entry.state = next_state
        return effects

    @staticmethod
    def _terminate(entry: _SlotEntry, grace_s: float) -> None:
        _ = entry.handle.terminate_gracefully(grace_s=max(0.0, grace_s))
