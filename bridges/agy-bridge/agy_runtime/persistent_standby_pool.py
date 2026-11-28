"""Управляемый пул прогретых standby-воркеров agy-bridge поверх ResidentProcessPool."""

from __future__ import annotations

import collections
import contextlib
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast, final

from core.stdio_resident.process_io import EOF, LINE, ResidentProcessHandle, StdioIoError
from core.stdio_resident.process_pool import PoolClosedError, ResidentProcessPool, SlotLeaseTimeoutError
from core.stdio_resident.process_reaper import extract_handle_pgid, get_pgid_rss_bytes, is_pgid_alive
from core.stdio_resident.standby_pool_fsm import ProfileKey, StandbyLimits, WarmSlotHandle, parse_limits
from core.stdio_resident.types import SlotAffinityKey

from .persistent_worker_config import PersistentWorkerSettings

__all__ = ["AgyStandbyAdapter", "AgyStandbyManager", "StandbyProfileKey", "StandbyReadySlot",
           "demand_limits", "standby_argv_digest"]

_LOGGER = logging.getLogger(__name__)
_OWNER_HASH = _BACKEND_ID = "agy-bridge"
_STANDBY_PREFIX = "__standby__:"
_FORBIDDEN_ARGS = ("--add-dir", "--resume")
_PREWARM_ERRORS = (SlotLeaseTimeoutError, PoolClosedError, OSError, StdioIoError, RuntimeError)


def demand_limits() -> StandbyLimits:
    """Лимиты demand-standby из os.environ (BRIDGE_DEMAND_STANDBY_*); по умолчанию OFF."""
    return parse_limits(os.environ, None)


def standby_argv_digest(argv: Sequence[str]) -> str | None:
    """Хеш launch-argv для изоляции профилей; None если argv содержит --add-dir или --resume."""
    if any(arg == bad or arg.startswith(f"{bad}=") for arg in argv for bad in _FORBIDDEN_ARGS):
        return None
    return hashlib.sha256("\0".join(argv).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class StandbyProfileKey:
    """Точный профиль совместимости для выдачи прогретого standby-воркера на turn 0."""
    model: str
    effort: str
    cwd: str
    env_digest: str
    review_profile: str
    argv_digest: str = ""


@dataclass(frozen=True)
class StandbyReadySlot:
    """Прогретый слот ResidentProcessPool, уже отдавший событие `init`."""
    standby_chat_key: str
    slot_id: str
    generation: int
    init_line: str
    cid: str
    created_mono: float
    pool_id: int
    pgid: int = 0


def _parse_init_line(line: str) -> tuple[bool, str]:
    try:
        raw = cast(object, json.loads(line))
    except ValueError:
        return False, ""
    ev = cast(dict[str, object], raw) if isinstance(raw, dict) else {}
    is_init = (ev.get("event") or ev.get("type")) == "init"
    return is_init, str(ev.get("conversation_id") or ev.get("session_id") or "") if is_init else ""


@final
class AgyStandbyManager:
    """Ограниченный фоновый прогрев standby-слотов; sliding TTL при BRIDGE_DEMAND_STANDBY_ENABLED=1."""

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._epoch: int = 0
        self._ready: collections.OrderedDict[StandbyProfileKey, StandbyReadySlot] = collections.OrderedDict()
        self._inflight: set[StandbyProfileKey] = set()
        self._demand: dict[StandbyProfileKey, float] = {}
        self._chat_alias: collections.OrderedDict[str, str] = collections.OrderedDict()
        self._standby_hits = self._standby_prewarms = 0

    def resolve_alias(self, chat_key: str) -> str:
        with self._lock:
            if (target := self._chat_alias.get(chat_key)) is not None:
                self._chat_alias.move_to_end(chat_key)
            return target or chat_key

    def bind_alias(self, chat_key: str, standby_chat_key: str, max_slots: int) -> None:
        if chat_key and standby_chat_key:
            with self._lock:
                self._chat_alias[chat_key] = standby_chat_key
                self._chat_alias.move_to_end(chat_key)
                while len(self._chat_alias) > max(16, max_slots * 8):
                    _ = self._chat_alias.popitem(last=False)

    def drop_alias(self, chat_key: str) -> None:
        with self._lock:
            _ = self._chat_alias.pop(chat_key, None)

    def has_alias(self, chat_key: str) -> bool:
        with self._lock:
            return chat_key in self._chat_alias

    @staticmethod
    def _close_idle_slots(pool: ResidentProcessPool | None, slots: Sequence[StandbyReadySlot]) -> None:
        if pool is None:
            return
        for slot in (s for s in slots if s.pool_id == id(pool)):
            try:
                _ = pool.close_if_idle(slot.slot_id, slot.generation)
            except _PREWARM_ERRORS as exc:
                _LOGGER.debug("standby idle close skipped: %s", exc)

    def close_slot(self, pool: ResidentProcessPool, slot: StandbyReadySlot) -> None:
        self._close_idle_slots(pool, (slot,))

    @staticmethod
    def _policy(cfg: PersistentWorkerSettings) -> tuple[bool, bool, float, int, float]:
        lim = demand_limits()
        on = lim.enabled
        cap = min(lim.global_max_slots if on else cfg.standby_max_slots, max(0, cfg.max_slots - 2))
        return (on, cfg.enabled and (cfg.standby_enabled or on), lim.sliding_ttl_s if on else cfg.standby_ttl_s,
                cap, lim.warmup_timeout_s if on else cfg.standby_init_timeout_s)

    def _prune_expired_locked(self, now: float, pool_id: int, ttl_s: float, sliding: bool) -> list[StandbyReadySlot]:
        """Протухшие слоты: sliding TTL от последнего спроса профиля (REQ-002) либо legacy created_mono."""
        expired: list[StandbyReadySlot] = []
        for pkey, slot in list(self._ready.items()):
            ref = self._demand.get(pkey, slot.created_mono) if sliding else slot.created_mono
            if slot.pool_id != pool_id or (now - ref) > ttl_s:
                _ = self._ready.pop(pkey, None)
                expired.append(slot)
        self._demand = {k: v for k, v in self._demand.items() if now - v <= ttl_s}
        return expired

    @staticmethod
    def _affinity_for(chat_key: str, pk: StandbyProfileKey) -> SlotAffinityKey:
        return SlotAffinityKey(_OWNER_HASH, chat_key, _BACKEND_ID, pk.model, pk.effort, pk.cwd,
                               env_digest=pk.env_digest, review_profile=pk.review_profile)

    def claim_ready(self, profile_key: StandbyProfileKey, pool: ResidentProcessPool,
                    cfg: PersistentWorkerSettings) -> StandbyReadySlot | None:
        """Забрать живой standby-слот для turn 0; спрос профиля продлевает его sliding TTL."""
        on, active, ttl_s, _cap, _init_s = self._policy(cfg)
        if not active or (profile_key.review_profile == "zero-canon" and not on):
            return None
        now = time.monotonic()
        with self._lock:
            expired = self._prune_expired_locked(now, id(pool), ttl_s, on)
            if on:
                self._demand[profile_key] = now
            slot = self._ready.pop(profile_key, None)
        self._close_idle_slots(pool, expired)
        if slot is None:
            return None
        binding = pool.idle_binding(self._affinity_for(slot.standby_chat_key, profile_key))
        if binding is None or binding.slot_id != slot.slot_id or binding.generation != slot.generation:
            self._close_idle_slots(pool, (slot,))
            return None
        with self._lock:
            self._standby_hits += 1
        return slot

    def schedule_prewarm(
        self, profile_key: StandbyProfileKey, pool: ResidentProcessPool, argv_builder: Callable[[], list[str]],
        cwd: str, env: Mapping[str, str], cfg: PersistentWorkerSettings,
    ) -> None:
        """Фоновый прогрев standby-слота; спрос профиля продлевает sliding TTL."""
        on, active, ttl_s, cap, init_s = self._policy(cfg)
        if not active or cap <= 0 or (profile_key.review_profile == "zero-canon" and not on):
            return
        now = time.monotonic()
        with self._lock:
            expired = self._prune_expired_locked(now, id(pool), ttl_s, on)
            if on:
                self._demand[profile_key] = now
            epoch = self._epoch
            start = profile_key not in {*self._ready, *self._inflight} and len(self._ready) + len(self._inflight) < cap
            if start:
                self._inflight.add(profile_key)
                self._standby_prewarms += 1
        self._close_idle_slots(pool, expired)
        if start:
            spec: _SpawnSpec = (profile_key, argv_builder, cwd, dict(env))
            threading.Thread(
                target=self._run_prewarm, args=(epoch, pool, spec, init_s),
                name="agy-standby-prewarm", daemon=True,
            ).start()

    def _stale(self, epoch: int | None) -> bool:
        return epoch is not None and self._epoch != epoch

    def warm(self, pool: ResidentProcessPool, spec: _SpawnSpec, init_timeout_s: float,
             epoch: int | None = None) -> StandbyReadySlot | None:
        """Синхронно прогреть слот до `init`; None при сбое или устаревшей эпохе (слот снесён)."""
        profile_key, argv_builder, cwd, env = spec
        key = f"{_STANDBY_PREFIX}{uuid.uuid4().hex[:12]}"
        entry = None
        try:
            entry = pool.acquire(self._affinity_for(key, profile_key), argv_builder=argv_builder, cwd=cwd,
                                 env=dict(env), is_ephemeral=False)
            init_line, cid = self._await_init(entry.handle, init_timeout_s, epoch)
            ok = bool(init_line) and not self._stale(epoch)
            leased, entry = entry, None
            kept = pool.release(leased.slot_id, success=ok, cancel=not ok, lease_id=leased.lease_id)
            return StandbyReadySlot(key, leased.slot_id, leased.handle.generation, init_line, cid, time.monotonic(),
                                    id(pool), extract_handle_pgid(leased.handle)) if ok and kept else None
        except _PREWARM_ERRORS as exc:
            _LOGGER.debug("standby prewarm skipped/failed: %s", exc)
            return None
        finally:
            if entry is not None:
                with contextlib.suppress(BaseException):
                    _ = pool.release(entry.slot_id, success=False, cancel=True, lease_id=entry.lease_id)

    def _run_prewarm(self, epoch: int, pool: ResidentProcessPool, spec: _SpawnSpec, init_s: float) -> None:
        profile_key = spec[0]
        try:
            if (slot := self.warm(pool, spec, init_s, epoch)) is not None:
                with self._lock:
                    fresh = self._epoch == epoch
                    if fresh:
                        self._ready[profile_key] = slot
                        self._ready.move_to_end(profile_key)
                if not fresh:
                    self._close_idle_slots(pool, (slot,))
        finally:
            with self._lock:
                self._inflight.discard(profile_key)

    def _await_init(self, handle: ResidentProcessHandle, timeout_s: float, epoch: int | None) -> tuple[str, str]:
        deadline = time.monotonic() + max(0.5, timeout_s)
        while time.monotonic() < deadline and not self._stale(epoch):
            kind, tagged = handle.read_stdout_line_outcome(timeout_s=min(0.25, max(0.05, deadline - time.monotonic())))
            if kind == LINE and tagged is not None:
                if (line := tagged.line.strip()) and (init := _parse_init_line(line))[0]:
                    return line, init[1]
            elif kind == EOF or not handle.is_alive():
                break
        return "", ""

    def clear(self, *, drop_aliases: bool = True, pool: ResidentProcessPool | None = None) -> None:
        """Сбросить все готовые standby-записи, отменить in-flight прогревы и закрыть idle standby."""
        with self._lock:
            if self._ready or self._inflight:
                self._epoch += 1
            evicted = list(self._ready.values())
            self._ready.clear()
            self._demand.clear()
            if drop_aliases:
                self._chat_alias.clear()
        self._close_idle_slots(pool, evicted)

    def stats(self) -> tuple[int, int, int]:
        with self._lock:
            return len(self._ready), self._standby_hits, self._standby_prewarms

_SpawnSpec = tuple[StandbyProfileKey, Callable[[], list[str]], str, Mapping[str, str]]

@final
class AgyStandbyAdapter:
    """Тонкий транслятор `StandbyAdapter` (VER-012) поверх AgyStandbyManager; RSS — по всей PGID-группе."""

    def __init__(self, manager: AgyStandbyManager, pool: ResidentProcessPool,
                 spec_of: Callable[[ProfileKey], _SpawnSpec]) -> None:
        self._manager, self._pool, self._spec_of = manager, pool, spec_of

    def spawn_warm(self, profile: ProfileKey, *, timeout_s: float) -> WarmSlotHandle:
        if (slot := self._manager.warm(self._pool, self._spec_of(profile), timeout_s)) is None:
            raise RuntimeError("standby warmup failed")
        return slot

    def is_alive(self, handle: WarmSlotHandle) -> bool:
        return is_pgid_alive(cast(StandbyReadySlot, handle).pgid)

    def claim(self, handle: WarmSlotHandle) -> object:
        return handle

    def dispose(self, handle: WarmSlotHandle) -> None:
        self._manager.close_slot(self._pool, cast(StandbyReadySlot, handle))

    def rss_mb(self, handle: WarmSlotHandle) -> float:
        return (get_pgid_rss_bytes(cast(StandbyReadySlot, handle).pgid) or 0) / (1024 * 1024)
