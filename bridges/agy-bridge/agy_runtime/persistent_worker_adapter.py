"""Тонкий адаптер agy-bridge поверх универсального core.stdio_resident.ResidentProcessPool."""

from __future__ import annotations

import collections
import logging
import threading
from typing import final

from core.stdio_resident.process_io import StdioIoError, StdioWriteError
from core.stdio_resident.process_pool import PoolClosedError, ResidentProcessPool, SlotLeaseTimeoutError
from core.stdio_resident.process_pool import _SlotEntry  # pyright: ignore[reportPrivateUsage]
from core.stdio_resident.types import SlotAffinityKey, SlotState

from .persistent_pool_support import PoolSig, build_pool, has_stale_stdout_or_eof, pool_sig_of
from .persistent_standby_pool import AgyStandbyManager, StandbyProfileKey, StandbyReadySlot, standby_argv_digest
from .persistent_worker_config import (
    PersistentAcquireRequest, PersistentLease, PersistentReleaseParams,
    PersistentWorkerSettings, compute_env_digest,
)
from .worker_rotation_policy import ReuseProbe, SlotBinding, SlotReuseVerdict, decide_slot_reuse

__all__ = [
    "AgyPersistentWorkerPool", "PersistentAcquireRequest", "PersistentLease",
    "PersistentReleaseParams", "StdioIoError", "StdioWriteError", "compute_env_digest",
]

_LOGGER = logging.getLogger(__name__)
_OWNER_HASH = "agy-bridge"
_BACKEND_ID = "agy-bridge"
_SHUTDOWN_ERRORS = (OSError, StdioIoError, PoolClosedError, RuntimeError)


@final
class AgyPersistentWorkerPool:
    """Потокобезопасная обёртка над ResidentProcessPool с cid-LRU и fail-closed откатом."""

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._pool: ResidentProcessPool | None = None
        self._pool_sig: PoolSig | None = None
        self._detached_pools: dict[int, ResidentProcessPool] = {}
        self._pool_active: dict[int, int] = {}
        self._slot_bindings: dict[str, SlotBinding] = {}
        self._cid_to_chat_key: collections.OrderedDict[str, str] = collections.OrderedDict()
        self._standby: AgyStandbyManager = AgyStandbyManager()
        self._hits = self._misses = self._fallbacks = 0
        self._teardowns_error = self._teardowns_cancel = self._desync_evictions = 0
        self._fresh_rotations = self._cold_rotations = 0

    def _detach_current_locked(self) -> ResidentProcessPool | None:
        old = self._pool
        self._pool = None
        self._pool_sig = None
        self._standby.clear(drop_aliases=True)
        if old is None:
            return None
        pid_key = id(old)
        if self._pool_active.get(pid_key, 0) <= 0:
            _ = self._pool_active.pop(pid_key, None)
            return old
        self._detached_pools[pid_key] = old
        return None

    @staticmethod
    def _safe_shutdown_pool(pool: ResidentProcessPool | None, timeout_s: float | None = None) -> None:
        if pool is None:
            return
        try:
            pool.shutdown(timeout_s)
        except _SHUTDOWN_ERRORS as exc:
            _LOGGER.warning("persistent pool shutdown error: %s", exc)

    def _ensure_pool(self, cfg: PersistentWorkerSettings) -> ResidentProcessPool | None:
        to_shutdown: ResidentProcessPool | None = None
        with self._lock:
            if not cfg.enabled:
                to_shutdown = self._detach_current_locked()
                pool = None
            else:
                sig = pool_sig_of(cfg)
                if self._pool is None or self._pool_sig != sig:
                    to_shutdown = self._detach_current_locked()
                    self._pool = build_pool(cfg)
                    self._pool_sig = sig
                pool = self._pool
        self._safe_shutdown_pool(to_shutdown)
        return pool

    def _resolve_chat_key_locked(self, chat_key: str, cid: str) -> str:
        if cid and cid in self._cid_to_chat_key:
            self._cid_to_chat_key.move_to_end(cid)
            return self._cid_to_chat_key[cid]
        return chat_key or cid

    def reconcile_disabled(self) -> None:
        """Мгновенно отцепить и остановить idle-пул при live-откате флага в False (O(1) fast-path)."""
        if self._pool is None:
            return
        with self._lock:
            to_shutdown = self._detach_current_locked()
        self._safe_shutdown_pool(to_shutdown)

    def _record_cid_locked(self, cid: str, chat_key: str, max_slots: int) -> None:
        if not cid or not chat_key:
            return
        cap = max(16, max_slots * 8)
        self._cid_to_chat_key[cid] = chat_key
        self._cid_to_chat_key.move_to_end(cid)
        while len(self._cid_to_chat_key) > cap:
            _ = self._cid_to_chat_key.popitem(last=False)

    def _evict_desynced(
        self, pool: ResidentProcessPool, entry: _SlotEntry, cid: str, chat_key: str = "", *, cold: bool = False
    ) -> None:
        """Единый eviction-путь: release(cancel=True) + сброс привязки; cold => cold_rotations."""
        try:
            _ = pool.release(entry.slot_id, success=False, cancel=True, lease_id=entry.lease_id or "")
        except _SHUTDOWN_ERRORS as exc:
            _LOGGER.warning("persistent desync eviction release error: %s", exc)
        if chat_key:
            self._standby.drop_alias(chat_key)
        with self._lock:
            _ = self._slot_bindings.pop(entry.slot_id, None)
            if cid:
                _ = self._cid_to_chat_key.pop(cid, None)
            self._cold_rotations += int(cold)
            self._desync_evictions += int(not cold)
            self._fallbacks += 1

    def _verdict_locked(
        self, entry: _SlotEntry, req: PersistentAcquireRequest, strict: bool, fresh_standby: bool
    ) -> tuple[SlotReuseVerdict, int, bool]:
        """Вердикт reuse: (verdict, turns_before, live); standby turn-0 — свежий claim, не reused."""
        binding = self._slot_bindings.get(entry.slot_id)
        turns_before = binding.turns if binding is not None else 0
        live = turns_before > 0 or entry.handle.generation > 0
        probe = ReuseProbe(
            strict=strict, reused=live and not (fresh_standby and turns_before == 0),
            run_cid=req.cid, resume_base_idx=req.resume_base_idx,
        )
        return decide_slot_reuse(probe, binding), turns_before, live

    def _claim_standby(
        self, req: PersistentAcquireRequest, cfg: PersistentWorkerSettings, pool: ResidentProcessPool, chat_key: str
    ) -> tuple[StandbyProfileKey | None, StandbyReadySlot | None]:
        profile_key: StandbyProfileKey | None = None
        if cfg.standby_enabled and not req.cid and req.review_profile != "zero-canon":
            if (ad := standby_argv_digest(req.argv_builder())) is not None:
                profile_key = StandbyProfileKey(req.model, req.effort, req.cwd, req.env_digest, req.review_profile, ad)
        standby = self._standby.claim_ready(profile_key, pool, cfg) if (profile_key and not self._standby.has_alias(chat_key)) else None
        if standby is not None:
            self._standby.bind_alias(chat_key, standby.standby_chat_key, cfg.max_slots)
        return profile_key, standby

    def acquire(self, req: PersistentAcquireRequest, cfg: PersistentWorkerSettings) -> PersistentLease | None:
        """Арендовать живой слот (включая standby на turn 0) или вернуть None для cold-spawn."""
        pool = self._ensure_pool(cfg)
        if pool is None:
            return None
        if not cfg.standby_enabled:
            self._standby.clear(drop_aliases=False, pool=pool)
        with self._lock:
            eff_chat_key = self._resolve_chat_key_locked(req.chat_key, req.cid)
        if not eff_chat_key:
            return None
        profile_key, standby = self._claim_standby(req, cfg, pool, eff_chat_key)
        affinity = SlotAffinityKey(
            owner_hash=_OWNER_HASH, chat_key=self._standby.resolve_alias(eff_chat_key),
            backend_id=_BACKEND_ID, model=req.model, effort=req.effort, cwd_norm=req.cwd,
            env_digest=req.env_digest, review_profile=req.review_profile,
        )
        try:
            entry = pool.acquire(affinity, argv_builder=req.argv_builder, cwd=req.cwd, env=req.env, is_ephemeral=False)
        except (SlotLeaseTimeoutError, PoolClosedError, OSError, StdioIoError):
            if standby is not None:
                self._standby.drop_alias(eff_chat_key)
                self._standby.close_slot(pool, standby)
            with self._lock:
                self._fallbacks += 1
            return None
        lease_id = entry.lease_id or ""
        standby_matched = standby is not None and entry.slot_id == standby.slot_id and entry.handle.generation == standby.generation
        prefetched_init = standby.init_line if (standby_matched and standby is not None) else ""
        if standby is not None and not standby_matched:
            self._standby.close_slot(pool, standby)
        with self._lock:
            verdict, turns_before, live = self._verdict_locked(entry, req, cfg.strict_cold_rotation, standby_matched)
        stale = live and has_stale_stdout_or_eof(entry.handle)
        if stale or verdict.evicts_slot:
            self._evict_desynced(pool, entry, req.cid, eff_chat_key, cold=not stale)
            return None
        reused = verdict is SlotReuseVerdict.REUSE
        with self._lock:
            self._pool_active[id(pool)] = self._pool_active.get(id(pool), 0) + 1
            self._hits += int(reused or standby_matched)
            self._misses += int(not (reused or standby_matched))
        if profile_key is not None:
            self._standby.schedule_prewarm(profile_key, pool, req.argv_builder, req.cwd, req.env, cfg)
        return PersistentLease(
            pool=pool, slot_id=entry.slot_id, lease_id=lease_id, handle=entry.handle,
            chat_key=eff_chat_key, reused=reused, turns_before=turns_before,
            max_turns=cfg.max_turns, pump_tick_s=cfg.pump_tick_s,
            drain_window_s=cfg.persistent_drain_window_s, prefetched_init_line=prefetched_init,
            fast_drain_enabled=cfg.fast_drain_enabled, fast_drain_min_s=cfg.fast_drain_min_s,
            standby_claimed=standby_matched,
        )

    def _decide_release_locked(self, lease: PersistentLease, params: PersistentReleaseParams) -> bool | None:
        if lease.released:
            return None
        lease.released = True
        turns_after = lease.turns_before + 1
        keep = bool(
            params.success and not params.rotate and not params.cancel and params.still_enabled
            and lease.pool is self._pool and lease.handle.is_alive()
            and turns_after < lease.max_turns
        )
        if keep:
            self._slot_bindings[lease.slot_id] = SlotBinding(turns=lease.turns_before).after_turn(params.cid)
            self._record_cid_locked(params.cid, lease.chat_key, params.max_slots)
            return True
        _ = self._slot_bindings.pop(lease.slot_id, None)
        self._standby.drop_alias(lease.chat_key)
        if params.cid and (params.cancel or not params.success):
            _ = self._cid_to_chat_key.pop(params.cid, None)
        self._fresh_rotations += int(params.rotate)
        self._teardowns_cancel += int(not params.rotate and params.cancel)
        self._teardowns_error += int(not params.rotate and not params.cancel and not params.success)
        return False

    def release(self, lease: PersistentLease, params: PersistentReleaseParams) -> None:
        """Идемпотентно освободить аренду; при сбое/отмене/ротации/откате — немедленный teardown."""
        with self._lock:
            keep = self._decide_release_locked(lease, params)
        if keep is None:
            return
        try:
            _ = lease.pool.release(
                lease.slot_id, success=keep, cancel=params.cancel or not keep, lease_id=lease.lease_id
            )
        except _SHUTDOWN_ERRORS as exc:
            _LOGGER.warning("persistent lease release error: %s", exc)
        to_shutdown: ResidentProcessPool | None = None
        with self._lock:
            pid_key = id(lease.pool)
            rem = max(0, self._pool_active.get(pid_key, 1) - 1)
            if rem == 0:
                _ = self._pool_active.pop(pid_key, None)
                if pid_key in self._detached_pools:
                    to_shutdown = self._detached_pools.pop(pid_key)
                elif not params.still_enabled and lease.pool is self._pool:
                    to_shutdown = self._detach_current_locked()
            else:
                self._pool_active[pid_key] = rem
        self._safe_shutdown_pool(to_shutdown)

    def health_snapshot(self, *, enabled: bool) -> dict[str, object]:
        """Снимок телеметрии пула для `/health` без утечки внутренних путей."""
        to_shutdown: ResidentProcessPool | None = None
        with self._lock:
            if not enabled and self._pool is not None:
                to_shutdown = self._detach_current_locked()
            pool = self._pool
            counters = (
                self._hits, self._misses, self._fallbacks,
                self._teardowns_error, self._teardowns_cancel, self._desync_evictions,
                self._cold_rotations, self._fresh_rotations,
            )
        self._safe_shutdown_pool(to_shutdown)
        slots = busy = idle = 0
        if pool is not None:
            with pool._cv:  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
                for entry in pool._slots.values():  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
                    if entry.dead:
                        continue
                    slots += 1
                    busy += int(entry.lease_id is not None)
                    idle += int(entry.lease_id is None and entry.state is SlotState.READY)
        return {
            "enabled": enabled, "slots": slots, "busy": busy, "idle": idle,
            "hits": counters[0], "misses": counters[1], "fallbacks": counters[2],
            "teardowns_error": counters[3], "teardowns_cancel": counters[4],
            "desync_evictions": counters[5], "cold_rotations": counters[6],
            "fresh_rotations": counters[7],
        }

    def shutdown(self, timeout_s: float | None = None) -> None:
        """Завершить активный и все отцепленные пулы при остановке моста."""
        pools: list[ResidentProcessPool] = []
        with self._lock:
            self._standby.clear(drop_aliases=True)
            if self._pool is not None:
                pools.append(self._pool)
                self._pool = self._pool_sig = None
            pools.extend(self._detached_pools.values())
            for store in (self._detached_pools, self._pool_active, self._slot_bindings, self._cid_to_chat_key):
                store.clear()
        for pool in pools:
            self._safe_shutdown_pool(pool, timeout_s=timeout_s)
