"""Тонкий адаптер agy-bridge поверх универсального core.stdio_resident.ResidentProcessPool."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from typing import final

from core.stdio_resident.process_io import StdioIoError, StdioWriteError
from core.stdio_resident.process_pool import PoolClosedError, ResidentProcessPool, SlotLeaseTimeoutError
from core.stdio_resident.process_pool import _SlotEntry  # pyright: ignore[reportPrivateUsage]
from core.stdio_resident.types import SlotAffinityKey, SlotState

from .persistent_pool_support import PoolSig, build_pool, has_stale_stdout_or_eof, pool_sig_of
from .persistent_standby_pool import AgyStandbyManager, StandbyProfileKey, StandbyReadySlot, demand_limits, standby_argv_digest
from .persistent_worker_config import (
    PersistentAcquireRequest, PersistentLease, PersistentReleaseParams, PersistentWorkerSettings, compute_env_digest,
)
from .worker_rotation_policy import ReuseProbe, SlotBinding, SlotReuseVerdict, decide_slot_reuse

__all__ = [
    "AgyPersistentWorkerPool", "PersistentAcquireRequest", "PersistentLease",
    "PersistentReleaseParams", "StdioIoError", "StdioWriteError", "compute_env_digest",
]
_LOGGER = logging.getLogger(__name__)
_OWNER_HASH = _BACKEND_ID = "agy-bridge"
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
        old, self._pool, self._pool_sig = self._pool, None, None
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
        if pool is not None:
            try:
                pool.shutdown(timeout_s)
            except _SHUTDOWN_ERRORS as exc:
                _LOGGER.warning("persistent pool shutdown error: %s", exc)

    def _ensure_pool(self, cfg: PersistentWorkerSettings) -> ResidentProcessPool | None:
        to_shutdown: ResidentProcessPool | None = None
        with self._lock:
            if not cfg.enabled:
                to_shutdown, pool = self._detach_current_locked(), None
            else:
                sig = pool_sig_of(cfg)
                if self._pool is None or self._pool_sig != sig:
                    to_shutdown = self._detach_current_locked()
                    self._pool, self._pool_sig = build_pool(cfg), sig
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
        if not (cid and chat_key):
            return
        self._cid_to_chat_key[cid] = chat_key
        self._cid_to_chat_key.move_to_end(cid)
        while len(self._cid_to_chat_key) > max(16, max_slots * 8):
            _ = self._cid_to_chat_key.popitem(last=False)

    def _evict_desynced(
        self, pool: ResidentProcessPool, entry: _SlotEntry, cid: str, chat_key: str = "", *, cold: bool = False
    ) -> None:
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
        demand_on = demand_limits().enabled
        if (cfg.standby_enabled or demand_on) and not req.cid and (demand_on or req.review_profile != "zero-canon"):
            if (ad := standby_argv_digest(req.argv_builder())) is not None:
                profile_key = StandbyProfileKey(req.model, req.effort, req.cwd, req.env_digest, req.review_profile, ad)
        standby = self._standby.claim_ready(profile_key, pool, cfg) if (profile_key and not self._standby.has_alias(chat_key)) else None
        if standby is not None:
            self._standby.bind_alias(chat_key, standby.standby_chat_key, cfg.max_slots)
        return profile_key, standby

    def _resolve_eff_chat_key(
        self, req: PersistentAcquireRequest, cfg: PersistentWorkerSettings, pool: ResidentProcessPool
    ) -> str:
        demand_on = demand_limits().enabled
        if not (cfg.standby_enabled or demand_on):
            self._standby.clear(drop_aliases=False, pool=pool)
        with self._lock:
            eff_chat_key = self._resolve_chat_key_locked(req.chat_key, req.cid)
        return eff_chat_key or (f"__zc__:{uuid.uuid4().hex[:12]}" if demand_on else "")

    def _acquire_pool_entry(
        self, pool: ResidentProcessPool, req: PersistentAcquireRequest, eff_chat_key: str, standby: StandbyReadySlot | None
    ) -> _SlotEntry | None:
        affinity = SlotAffinityKey(
            owner_hash=_OWNER_HASH, chat_key=self._standby.resolve_alias(eff_chat_key),
            backend_id=_BACKEND_ID, model=req.model, effort=req.effort, cwd_norm=req.cwd,
            env_digest=req.env_digest, review_profile=req.review_profile,
        )
        try:
            return pool.acquire(affinity, argv_builder=req.argv_builder, cwd=req.cwd, env=req.env, is_ephemeral=False)
        except (SlotLeaseTimeoutError, PoolClosedError, OSError, StdioIoError):
            if standby is not None:
                self._standby.drop_alias(eff_chat_key)
                self._standby.close_slot(pool, standby)
            with self._lock:
                self._fallbacks += 1
            return None

    def _build_lease(
        self, pool: ResidentProcessPool, req: PersistentAcquireRequest, cfg: PersistentWorkerSettings,
        meta: tuple[_SlotEntry, str, bool, int, bool, StandbyReadySlot | None],
    ) -> PersistentLease:
        entry, eff_chat_key, reused, turns_before, matched, standby = meta
        return PersistentLease(
            pool=pool, slot_id=entry.slot_id, lease_id=entry.lease_id or "", handle=entry.handle, chat_key=eff_chat_key,
            reused=reused, turns_before=turns_before, max_turns=1 if req.review_profile == "zero-canon" else cfg.max_turns,
            pump_tick_s=cfg.pump_tick_s, drain_window_s=cfg.persistent_drain_window_s,
            prefetched_init_line=standby.init_line if matched and standby is not None else "",
            fast_drain_enabled=cfg.fast_drain_enabled, fast_drain_min_s=cfg.fast_drain_min_s, standby_claimed=matched,
        )

    def _finish_acquire(
        self, pool: ResidentProcessPool, req: PersistentAcquireRequest, cfg: PersistentWorkerSettings,
        bundle: tuple[_SlotEntry, str, StandbyProfileKey | None, StandbyReadySlot | None],
    ) -> PersistentLease | None:
        entry, eff_chat_key, profile_key, standby = bundle
        matched = standby is not None and (entry.slot_id, entry.handle.generation) == (standby.slot_id, standby.generation)
        if standby is not None and not matched:
            self._standby.close_slot(pool, standby)
        with self._lock:
            verdict, turns_before, live = self._verdict_locked(entry, req, cfg.strict_cold_rotation, matched)
        stale = live and has_stale_stdout_or_eof(entry.handle)
        if stale or verdict.evicts_slot:
            self._evict_desynced(pool, entry, req.cid, eff_chat_key, cold=not stale)
            return None
        reused = verdict is SlotReuseVerdict.REUSE
        hit = int(any((reused, matched)))
        with self._lock:
            self._pool_active[id(pool)] = self._pool_active.get(id(pool), 0) + 1
            self._hits += hit
            self._misses += 1 - hit
        if profile_key is not None:
            self._standby.schedule_prewarm(profile_key, pool, req.argv_builder, req.cwd, req.env, cfg)
        return self._build_lease(pool, req, cfg, (entry, eff_chat_key, reused, turns_before, matched, standby))

    def acquire(self, req: PersistentAcquireRequest, cfg: PersistentWorkerSettings) -> PersistentLease | None:
        """Арендовать живой слот (включая standby на turn 0) или вернуть None для cold-spawn."""
        pool = self._ensure_pool(cfg)
        if pool is None or not (eff_chat_key := self._resolve_eff_chat_key(req, cfg, pool)):
            return None
        profile_key, standby = self._claim_standby(req, cfg, pool, eff_chat_key)
        if (entry := self._acquire_pool_entry(pool, req, eff_chat_key, standby)) is None:
            return None
        return self._finish_acquire(pool, req, cfg, (entry, eff_chat_key, profile_key, standby))

    def _decide_release_locked(self, lease: PersistentLease, params: PersistentReleaseParams) -> bool | None:
        if lease.released:
            return None
        lease.released = True
        keep = all((params.success, not params.rotate, not params.cancel, params.still_enabled,
                    lease.pool is self._pool, lease.handle.is_alive(), lease.turns_before + 1 < lease.max_turns))
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
        with self._lock:
            keep = self._decide_release_locked(lease, params)
        if keep is None:
            return
        try:
            _ = lease.pool.release(lease.slot_id, success=keep, cancel=params.cancel or not keep, lease_id=lease.lease_id)
        except _SHUTDOWN_ERRORS as exc:
            _LOGGER.warning("persistent lease release error: %s", exc)
        to_shutdown: ResidentProcessPool | None = None
        with self._lock:
            pid_key = id(lease.pool)
            rem = max(0, self._pool_active.get(pid_key, 1) - 1)
            if rem:
                self._pool_active[pid_key] = rem
            else:
                _ = self._pool_active.pop(pid_key, None)
                to_shutdown = self._detached_pools.pop(pid_key, None) or (
                    self._detach_current_locked() if not params.still_enabled and lease.pool is self._pool else None
                )
        self._safe_shutdown_pool(to_shutdown)

    def health_snapshot(self, *, enabled: bool) -> dict[str, object]:
        to_shutdown: ResidentProcessPool | None = None
        with self._lock:
            if not enabled and self._pool is not None:
                to_shutdown = self._detach_current_locked()
            pool = self._pool
            c = (
                self._hits, self._misses, self._fallbacks, self._teardowns_error, self._teardowns_cancel,
                self._desync_evictions, self._cold_rotations, self._fresh_rotations,
            )
        self._safe_shutdown_pool(to_shutdown)
        slots = busy = idle = 0
        if pool is not None:
            with pool._cv:  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
                for entry in pool._slots.values():  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
                    if not entry.dead:
                        slots += 1
                        busy += int(entry.lease_id is not None)
                        idle += int(entry.lease_id is None and entry.state is SlotState.READY)
        return {
            "enabled": enabled, "slots": slots, "busy": busy, "idle": idle, "hits": c[0], "misses": c[1],
            "fallbacks": c[2], "teardowns_error": c[3], "teardowns_cancel": c[4], "desync_evictions": c[5],
            "cold_rotations": c[6], "fresh_rotations": c[7],
        }

    def shutdown(self, timeout_s: float | None = None) -> None:
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
