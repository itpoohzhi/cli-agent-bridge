from __future__ import annotations  # noqa: E402

"""Thread-safe lifecycle management for resident stdio processes."""

import asyncio  # noqa: E402
import logging  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from collections.abc import Callable, Iterable, Mapping  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

from core.stdio_resident.config import StdioPoolConfig  # noqa: E402
from core.stdio_resident.process_io import ResidentProcessHandle, StdioProcessTerminated  # noqa: E402
from core.stdio_resident.process_reaper import get_pgid_rss_bytes, is_pgid_alive  # noqa: E402
from core.stdio_resident.types import (  # noqa: E402
    SlotAffinityKey, SlotEffect, SlotEvent, SlotState, step_slot_fsm,
)

_LOGGER = logging.getLogger(__name__)


class SlotLeaseTimeoutError(Exception):
    """Raised when no resident-process slot becomes available in time."""


class PoolClosedError(Exception):
    """Raised when a lease is requested from a closed process pool."""


@dataclass
class _SlotEntry:
    """Mutable state owned by one process-pool slot.

    Attributes:
        rss_evict_pending: Помечает арендованный слот на обязательный teardown
            при следующем успешном release() после превышения max_rss_bytes.
    """

    slot_id: str
    affinity_key: SlotAffinityKey
    handle: ResidentProcessHandle
    state: SlotState
    last_used_mono: float
    lease_id: str | None = None
    is_ephemeral: bool = False
    dead: bool = False
    rss_evict_pending: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock)


class ResidentProcessPool:
    """Allocate reusable subprocesses while enforcing bounded capacity."""

    def __init__(self, config: StdioPoolConfig | None = None) -> None:
        self._config: StdioPoolConfig = config or StdioPoolConfig.from_env()
        self._lock: threading.RLock = threading.RLock()
        self._cv: threading.Condition = threading.Condition(self._lock)
        self._slots: dict[str, _SlotEntry] = {}
        self._closed: bool = False
        self._stop_event: threading.Event = threading.Event()
        self._maint_thread: threading.Thread | None = None
        self._last_rss_check_mono: float | None = None

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
            if self._closed:
                raise PoolClosedError("resident process pool is closed")
            _ = self.start_maintenance()
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
            if entry.rss_evict_pending:
                _ = self._transition(entry, SlotEvent.Shutdown)
                try:
                    self._finish_teardown(entry, self._config.cancel_grace_s)
                finally:
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

    def start_maintenance(self) -> bool:
        """Запустить фоновый daemon-поток обслуживания пула при enabled=True.

        Возвращает True, если поток запущен этим вызовом, и False если запуск
        пропущен (пул выключен, закрыт, остановлен или поток уже жив).
        """
        if not self._config.enabled:
            return False
        with self._cv:
            if self._closed or self._stop_event.is_set():
                return False
            if self._maint_thread is not None and self._maint_thread.is_alive():
                return False
            thread = threading.Thread(
                target=self._maintenance_loop,
                name="stdio-resident-maintenance",
                daemon=True,
            )
            self._maint_thread = thread
            thread.start()
            return True

    async def drain_and_shutdown(self, timeout_s: float | None = None) -> None:
        """Close idle slots, wait for active leases up to timeout, then shut down."""
        grace_s = max(0.0, self._config.shutdown_timeout_s if timeout_s is None else timeout_s)
        deadline = time.monotonic() + grace_s
        idle_entries: list[_SlotEntry] = []
        already_empty = False
        with self._cv:
            self._stop_event.set()
            thread = self._maint_thread
            if self._closed and not self._slots:
                already_empty = True
            else:
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
        if already_empty:
            await asyncio.to_thread(self._join_maintenance, thread, grace_s)
            return
        try:
            if idle_entries:
                await asyncio.to_thread(
                    self._terminate_victims,
                    idle_entries,
                    min(grace_s, self._config.cancel_grace_s),
                )
            while time.monotonic() < deadline:
                with self._cv:
                    if not any(e.lease_id is not None for e in self._slots.values()):
                        break
                await asyncio.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
            final_thread, remaining_entries = self._collect_all_for_shutdown()
            if final_thread is not None:
                thread = final_thread
            if remaining_entries:
                await asyncio.to_thread(self._terminate_victims, remaining_entries, grace_s)
        finally:
            await asyncio.to_thread(self._join_maintenance, thread, grace_s)

    def _collect_all_for_shutdown(self) -> tuple[threading.Thread | None, list[_SlotEntry]]:
        """Пометить пул закрытым под _cv и забрать поток обслуживания и все слоты."""
        entries: list[_SlotEntry] = []
        with self._cv:
            self._stop_event.set()
            thread = self._maint_thread
            if not (self._closed and not self._slots):
                self._closed = True
                entries = list(self._slots.values())
                for entry in entries:
                    entry.lease_id = None
                    _ = self._transition(entry, SlotEvent.Shutdown)
                self._slots.clear()
                self._cv.notify_all()
        return thread, entries

    def shutdown(self, timeout_s: float | None = None) -> None:
        """Close the pool and terminate every child process."""
        grace_s = max(0.0, self._config.shutdown_timeout_s if timeout_s is None else timeout_s)
        thread, entries = self._collect_all_for_shutdown()
        try:
            if entries:
                self._terminate_victims(entries, grace_s)
        finally:
            self._join_maintenance(thread, grace_s)

    def _maintenance_loop(self) -> None:
        """Фоновый цикл обслуживания: шаг reap_interval_s, устойчив к ошибкам прохода."""
        interval = max(0.001, self._config.reap_interval_s)
        while not self._stop_event.wait(timeout=interval):
            try:
                self._maintenance_step()
            except Exception:
                _LOGGER.exception("resident pool maintenance step failed")

    def _maintenance_step(self) -> None:
        """Один проход обслуживания: мёртвые/карантинные, idle READY и RSS > max_rss_bytes."""
        idle_victims: list[_SlotEntry] = []
        rss_targets: list[tuple[str, ResidentProcessHandle, int]] = []
        with self._cv:
            if self._closed or self._stop_event.is_set():
                return
            before_count = len(self._slots)
            self._reap_quarantined_slots()
            self._remove_dead_ready_slots()
            now = time.monotonic()
            closed_any = len(self._slots) != before_count
            for entry in list(self._slots.values()):
                if (
                    not entry.dead
                    and entry.state is SlotState.READY
                    and entry.lease_id is None
                    and (now - entry.last_used_mono) > self._config.idle_timeout_s
                ):
                    _ = self._transition(entry, SlotEvent.Shutdown)
                    _ = self._slots.pop(entry.slot_id, None)
                    idle_victims.append(entry)
                    closed_any = True
            if closed_any:
                self._cv.notify_all()
            if (
                self._last_rss_check_mono is None
                or (now - self._last_rss_check_mono) >= self._config.rss_check_interval_s
            ):
                for entry in self._slots.values():
                    if not entry.dead:
                        pgid = self._entry_pgid(entry)
                        if pgid > 0:
                            rss_targets.append((entry.slot_id, entry.handle, pgid))
                if rss_targets:
                    self._last_rss_check_mono = now

        if idle_victims:
            self._terminate_victims(idle_victims, self._config.cancel_grace_s, reason="idle")

        if not rss_targets:
            return

        over_limit: list[tuple[str, ResidentProcessHandle]] = []
        for slot_id, handle, pgid in rss_targets:
            if self._stop_event.is_set():
                return
            rss_bytes = get_pgid_rss_bytes(pgid)
            if rss_bytes is not None and rss_bytes > self._config.max_rss_bytes:
                over_limit.append((slot_id, handle))

        if not over_limit:
            return

        rss_victims: list[_SlotEntry] = []
        with self._cv:
            if self._closed or self._stop_event.is_set():
                return
            for slot_id, expected_handle in over_limit:
                entry = self._slots.get(slot_id)
                if entry is None or entry.dead or entry.handle is not expected_handle:
                    continue
                if entry.state is SlotState.READY and entry.lease_id is None:
                    _ = self._transition(entry, SlotEvent.Shutdown)
                    _ = self._slots.pop(slot_id, None)
                    rss_victims.append(entry)
                elif entry.lease_id is not None:
                    entry.rss_evict_pending = True
            if rss_victims:
                self._cv.notify_all()

        if rss_victims:
            self._terminate_victims(
                rss_victims, self._config.cancel_grace_s, reason="rss-exceeded"
            )

    def _terminate_victims(
        self,
        entries: list[_SlotEntry],
        grace_s: float,
        reason: str = "evict",
    ) -> None:
        """Вывести слоты из _slots под _cv, завершить вне _cv и вернуть в карантин при ошибке."""
        if not entries:
            return
        with self._cv:
            changed = False
            for entry in entries:
                if self._slots.get(entry.slot_id) is entry:
                    entry.lease_id = None
                    _ = self._transition(entry, SlotEvent.Shutdown)
                    _ = self._slots.pop(entry.slot_id, None)
                    changed = True
            if changed:
                self._cv.notify_all()

        failed_entries: list[_SlotEntry] = []
        for entry in entries:
            try:
                self._terminate(entry, grace_s)
            except Exception:
                _LOGGER.exception("failed to close %s slot %s", reason, entry.slot_id)
                failed_entries.append(entry)
                continue
            if not getattr(entry.handle, "_pgid_dead", True):
                failed_entries.append(entry)

        if failed_entries:
            with self._cv:
                for entry in failed_entries:
                    entry.lease_id = None
                    entry.dead = True
                    self._slots[entry.slot_id] = entry
                self._cv.notify_all()

    @staticmethod
    def _join_maintenance(thread: threading.Thread | None, timeout_s: float) -> None:
        """Дождаться завершения потока обслуживания без удержания _cv."""
        if thread is not None and thread is not threading.current_thread() and thread.is_alive():
            clamped_timeout = max(0.0, timeout_s)
            thread.join(timeout=clamped_timeout)
            if thread.is_alive():
                _LOGGER.warning(
                    "maintenance thread %s join timeout after %.3fs; still alive",
                    thread.name,
                    clamped_timeout,
                )

    @staticmethod
    def _entry_pgid(entry: _SlotEntry) -> int:
        """Извлечь положительный pgid или pid слота для замера RSS."""
        raw_pgid = getattr(entry.handle, "_pgid", None)
        if isinstance(raw_pgid, int) and not isinstance(raw_pgid, bool) and raw_pgid > 0:
            return raw_pgid
        raw_pid = getattr(entry.handle, "pid", 0)
        if isinstance(raw_pid, int) and not isinstance(raw_pid, bool) and raw_pid > 0:
            return raw_pid
        return 0

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
        terminated = False
        try:
            self._terminate(entry, grace_s)
            terminated = True
        except Exception:
            _LOGGER.exception("failed to terminate slot %s", entry.slot_id)
        finally:
            if terminated and getattr(entry.handle, "_pgid_dead", True):
                _ = self._slots.pop(entry.slot_id, None)
            else:
                entry.dead = True

    @staticmethod
    def _transition(entry: _SlotEntry, event: SlotEvent) -> list[SlotEffect]:
        next_state, effects = step_slot_fsm(entry.state, event)
        entry.state = next_state
        return effects

    @staticmethod
    def _terminate(entry: _SlotEntry, grace_s: float) -> None:
        _ = entry.handle.terminate_gracefully(grace_s=max(0.0, grace_s))
