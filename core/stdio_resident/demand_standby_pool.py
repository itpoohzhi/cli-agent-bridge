"""Demand-driven warm standby pool: единственный владелец `_slots` (AD-001, AD-003, AD-004, AD-006, AD-007, BND-002)."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from typing import cast, final

from core.stdio_resident import standby_pool_fsm as fsm
from core.stdio_resident.standby_pool_fsm import (
    ActionKind, PoolAction, PoolBudget, PoolState, ProfileKey, SlotRecord, StandbyAdapter, StandbyLimits,
    WarmSlotHandle,
)
from core.zero_canon_fs import resolve_hub_dynamic_config

_log = logging.getLogger(__name__)
S = fsm.SlotLifecycleState
_GONE = frozenset((S.DISPOSING, S.CLOSED))
_SPAWNS = (ActionKind.SPAWN, ActionKind.REPLENISH)
_DYN_SECTION = "demand_standby"
Handle = tuple[StandbyAdapter, WarmSlotHandle]
ConfigProvider = Callable[[], tuple[Mapping[str, object], Mapping[str, object]]]

def load_dynamic_config(environ: Mapping[str, str] | None = None) -> Mapping[str, object]:
    try:
        parsed = cast("object", json.loads(resolve_hub_dynamic_config(environ).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    raw = cast("Mapping[str, object]", parsed)
    sec = raw.get(_DYN_SECTION)
    return cast("Mapping[str, object]", sec) if isinstance(sec, dict) else raw

@dataclass(frozen=True, slots=True)
class ClaimedSlot:
    slot_id: str
    profile: ProfileKey
    handle: WarmSlotHandle
    payload: object
    epoch: int

@final
class DemandStandbyPool:
    def __init__(self, adapters: Mapping[str, StandbyAdapter], *, config_provider: ConfigProvider | None = None,
                 clock: Callable[[], float] | None = None, max_workers: int | None = None) -> None:
        self._adapters, self._clock, self._max_workers = dict(adapters), clock or time.monotonic, max_workers
        self._config = config_provider or (lambda: (os.environ, load_dynamic_config()))
        self._lock = threading.RLock()
        self._slots: dict[str, SlotRecord] = {}
        self._handles: dict[str, Handle] = {}
        self._demand: dict[ProfileKey, float] = {}
        self._epoch_seq, self._draining, self._lim = 0, False, StandbyLimits()
        self._executor: ThreadPoolExecutor | None = None
        self._reaper: threading.Thread | None = None
        self._futures: set[Future[object]] = set()
        self._stop = threading.Event()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "disposes": 0}

    def snapshot(self) -> dict[str, object]:
        lim = self._limits()
        with self._lock:
            by = Counter(s.state for s in self._slots.values())
            return {"slots": len(self._slots), "ready": by[S.READY], "warming": by[S.WARMING],
                    "claimed": by[S.CLAIMED], "profiles": len({s.profile for s in self._slots.values()}),
                    "total_rss_mb": self._total_rss(), "enabled": lim.enabled, **self._stats}

    def submit_demand(self, profile: ProfileKey) -> None:
        lim = self._gate(profile)
        if lim is None:
            return
        with self._lock:
            ps, acts = fsm.plan_demand(self._state(), profile, lim, self._clock(), self._total_rss())
            doomed = self._commit(ps, acts)
        self._finish(doomed, acts)

    def claim(self, profile: ProfileKey, *, session_key: str | None = None) -> ClaimedSlot | None:
        lim = self._gate(profile)
        if lim is None:
            return None
        cand = self._pick(profile, session_key)
        if cand is None:
            with self._lock:
                self._stats["misses"] += 1
            self.submit_demand(profile)
            return None
        sid, epoch, (adapter, handle) = cand
        won = self._commit_claim(sid, epoch, self._safe_alive(adapter, handle), lim, session_key)
        if won is None:
            return None
        try:
            payload = adapter.claim(handle)
        except Exception as exc:
            _log.warning("claim failed env=%s err=%s", profile.env_digest[:12], type(exc).__name__)
            self.release_claimed(sid, success=False)
            return None
        return ClaimedSlot(sid, won.profile, handle, payload, won.epoch)

    def release_claimed(self, slot_id: str, *, success: bool = True) -> None:
        with self._lock:
            rec, entry = self._slots.get(slot_id), self._handles.get(slot_id)
        if rec is None or entry is None or rec.state is not S.CLAIMED:
            return
        keep = all((success, rec.session_key is not None, not rec.profile.is_zero_canon)) and self._safe_alive(*entry)
        with self._lock:
            cur = self._slots.get(slot_id)
            if cur is None or (cur.state, cur.epoch) != (S.CLAIMED, rec.epoch):
                return
            if self._draining or not keep:
                self._slots[slot_id] = replace(cur, session_key=None)
            ps, acts = fsm.plan_turn_done(self._state(), slot_id, self._limits(), self._clock(), self._total_rss())
            doomed = self._commit(ps, acts)
        self._finish(doomed, acts)

    def _evict_dead_ready(self, ready: list[tuple[str, int, Handle]]) -> list[Handle]:
        dead = {i: ep for i, ep, (ad, h) in ready if not self._safe_alive(ad, h)}
        with self._lock:
            for i, ep in dead.items():
                if (s := self._slots.get(i)) is not None and (s.state, s.epoch) == (S.READY, ep):
                    self._slots[i] = replace(s, state=S.DISPOSING)
            return self._prune()

    def reap_once(self) -> int:
        lim, now = self._limits(), self._clock()
        with self._lock:
            doomed = self._commit(fsm.plan_reap_tick(self._state(), lim, now)[0], ()) if lim.enabled else self._mark_idle()
            ready = [(i, s.epoch, self._handles[i]) for i, s in self._slots.items() if s.state is S.READY and i in self._handles]
        self._dispose_many(doomed)
        late = self._evict_dead_ready(ready)
        self._dispose_many(late)
        return len(doomed) + len(late)

    def drain_and_shutdown(self, timeout_s: float = 5.0) -> int:
        """Гасит ВСЕ слоты (WARMING/READY/CLAIMED), останавливает reaper/executor; возвращает число убитых handle."""
        with self._lock:
            ps, acts = fsm.plan_drain(self._state())
            doomed = self._commit(ps, acts)
            ex, reaper = self._executor, self._reaper
        self._stop.set()
        if ex is not None:
            ex.shutdown(wait=False, cancel_futures=True)
        if reaper is not None and reaper is not threading.current_thread():
            reaper.join(timeout_s)
        self._dispose_many(doomed)
        _ = wait(list(self._futures), timeout=timeout_s)
        return len(doomed)

    def _limits(self) -> StandbyLimits:
        env, dyn = self._config()
        self._lim = fsm.parse_limits(env, dyn)
        return self._lim

    def _state(self) -> PoolState:
        return PoolState(tuple(self._slots.values()), tuple(self._demand.items()), self._epoch_seq, self._draining)

    def _total_rss(self) -> float:
        return sum(s.rss_mb for s in self._slots.values() if s.state not in _GONE)

    def _prune(self) -> list[Handle]:
        gone = [i for i, s in self._slots.items() if s.state in _GONE]
        for i in gone:
            del self._slots[i]
        return [h for i in gone if (h := self._handles.pop(i, None)) is not None]

    def _commit(self, ps: PoolState, acts: tuple[PoolAction, ...]) -> list[Handle]:
        self._slots = {s.slot_id: s for s in ps.slots}
        self._demand = dict(ps.profile_last_demand)
        self._epoch_seq, self._draining = ps.epoch_seq, ps.draining
        self._stats["evictions"] += sum(a.kind is ActionKind.KILL and a.reason == "lru-evict" for a in acts)
        return self._prune()

    def _mark_idle(self) -> list[Handle]:
        for i, s in list(self._slots.items()):
            if s.state in (S.WARMING, S.READY):
                self._slots[i] = replace(s, state=S.DISPOSING)
        return self._prune()

    def _gate(self, profile: ProfileKey) -> StandbyLimits | None:
        lim = self._limits()
        if not lim.enabled:
            with self._lock:
                doomed = self._mark_idle()
            self._dispose_bg(doomed)
            return None
        if profile.backend_id not in self._adapters:
            return None
        self._ensure_started(lim)
        return lim

    def _ensure_started(self, lim: StandbyLimits) -> None:
        with self._lock:
            if self._draining or self._executor is not None:
                return
            workers = self._max_workers or max(2, lim.global_max_slots)
            self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="standby-pool")
            self._reaper = threading.Thread(target=self._reap_loop, name="standby-reaper", daemon=True)
            self._reaper.start()

    def _reap_loop(self) -> None:
        while not self._stop.wait(self._lim.reap_interval_s):
            try:
                _ = self.reap_once()
            except Exception:
                _log.exception("standby reap failed")

    def _pick(self, profile: ProfileKey, session_key: str | None) -> tuple[str, int, Handle] | None:
        with self._lock:
            self._demand[profile] = self._clock()
            ready = [s for s in self._slots.values()
                     if fsm.can_claim_slot(s, profile, session_key) and s.slot_id in self._handles]
            ready.sort(key=lambda s: s.session_key is None)
            return (ready[0].slot_id, ready[0].epoch, self._handles[ready[0].slot_id]) if ready else None

    def _commit_claim(self, sid: str, epoch: int, alive: bool, lim: StandbyLimits,
                      session_key: str | None) -> SlotRecord | None:
        with self._lock:
            cur = self._slots.get(sid)
            if cur is None or cur.state is not S.READY or cur.epoch != epoch:
                return None
            ps, acts = fsm.plan_claim_result(self._state(), sid, alive, PoolBudget(lim, self._clock(), self._total_rss()))
            doomed = self._commit(ps, acts)
            self._stats["hits" if alive else "misses"] += 1
            if alive:
                cur = self._slots[sid] = replace(self._slots[sid], session_key=session_key)
        self._finish(doomed, acts)
        return cur if alive else None

    def _spawn(self, action: PoolAction) -> None:
        adapter = self._adapters[action.profile.backend_id]
        handle: WarmSlotHandle | None = None
        rss = 0.0
        try:
            handle = adapter.spawn_warm(action.profile, timeout_s=self._lim.warmup_timeout_s)
            rss = adapter.rss_mb(handle)
        except Exception as exc:
            _log.warning("spawn_warm failed env=%s err=%s", action.profile.env_digest[:12], type(exc).__name__)
            if handle is not None:
                self._dispose_many([(adapter, handle)])
            handle = None
        self._complete(action, handle, rss)

    def _complete(self, action: PoolAction, handle: WarmSlotHandle | None, rss: float) -> None:
        adapter = self._adapters[action.profile.backend_id]
        with self._lock:
            ok = handle is not None and self._total_rss() + rss <= self._lim.max_total_rss_mb
            ps, acts = fsm.plan_warmup_complete(self._state(), action.slot_id, action.epoch, ok, rss)
            doomed = self._commit(ps, acts)
            cur = self._slots.get(action.slot_id)
            kept = ok and cur is not None and cur.epoch == action.epoch and cur.state is S.READY
            if kept and handle is not None:
                self._handles[action.slot_id] = (adapter, handle)
        self._dispose_many(doomed)
        if handle is not None and not kept:
            self._dispose_many([(adapter, handle)])

    def _submit(self, fn: Callable[..., object], *args: object) -> bool:
        with self._lock:
            if self._executor is None or self._draining:
                return False
            try:
                fut: Future[object] = self._executor.submit(fn, *args)
            except RuntimeError:
                return False
            self._futures.add(fut)
        fut.add_done_callback(self._futures.discard)
        return True

    def _finish(self, doomed: list[Handle], acts: tuple[PoolAction, ...]) -> None:
        self._dispose_bg(doomed)
        for a in acts:
            if a.kind in _SPAWNS and not self._submit(self._spawn, a):
                self._complete(a, None, 0.0)

    def _dispose_bg(self, doomed: list[Handle]) -> None:
        if doomed and not self._submit(self._dispose_many, doomed):
            self._dispose_many(doomed)

    def _dispose_many(self, doomed: list[Handle]) -> None:
        for adapter, handle in doomed:
            try:
                adapter.dispose(handle)
            except Exception as exc:
                _log.warning("dispose failed err=%s", type(exc).__name__)
            with self._lock:
                self._stats["disposes"] += 1

    @staticmethod
    def _safe_alive(adapter: StandbyAdapter, handle: WarmSlotHandle) -> bool:
        try:
            return bool(adapter.is_alive(handle))
        except Exception:
            return False
