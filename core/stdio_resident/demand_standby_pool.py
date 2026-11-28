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
    ActionKind, ClaimAttempt, PoolAction, PoolBudget, PoolState, ProfileKey, SlotRecord, StandbyAdapter,
    StandbyLimits, WarmSlotHandle, WarmupReport,
)
from core.zero_canon_fs import resolve_hub_dynamic_config

_log = logging.getLogger(__name__)
S, _SPAWNS, _DYN_SECTION = fsm.SlotLifecycleState, (ActionKind.SPAWN, ActionKind.REPLENISH), "demand_standby"
Handle = tuple[StandbyAdapter, WarmSlotHandle]
Doomed = tuple[str, int, Handle]
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
        self._lock, self._stop = threading.RLock(), threading.Event()
        self._slots: dict[str, SlotRecord] = {}
        self._handles: dict[str, Handle] = {}
        self._disposing: set[str] = set()
        self._demand: dict[ProfileKey, float] = {}
        self._pending: tuple[ProfileKey, ...] = ()
        self._epoch_seq, self._draining, self._lim = 0, False, StandbyLimits()
        self._executor: ThreadPoolExecutor | None = None
        self._reaper: threading.Thread | None = None
        self._futures: set[Future[object]] = set()
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
        won = self._commit_claim(sid, epoch, profile, self._safe_alive(adapter, handle), session_key)
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
    def _evict_dead_ready(self, ready: list[tuple[str, int, Handle]]) -> list[Doomed]:
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
        return PoolState(tuple(self._slots.values()), tuple(self._demand.items()),
                         self._epoch_seq, self._draining, self._pending)
    def _total_rss(self, exclude: str = "") -> float:
        return sum(s.rss_mb for s in self._slots.values() if s.state is not S.CLOSED and s.slot_id != exclude)
    def _prune(self) -> list[Doomed]:
        doomed: list[Doomed] = []
        for i, s in list(self._slots.items()):
            if s.state is S.CLOSED:
                del self._slots[i]
                _ = self._handles.pop(i, None)
            elif s.state is S.DISPOSING and i not in self._disposing:
                if (h := self._handles.pop(i, None)) is not None:
                    self._disposing.add(i)
                    doomed.append((i, s.epoch, h))
                else:
                    del self._slots[i]
        return doomed
    def _commit(self, ps: PoolState, acts: tuple[PoolAction, ...]) -> list[Doomed]:
        self._slots, self._demand = {s.slot_id: s for s in ps.slots}, dict(ps.profile_last_demand)
        self._epoch_seq, self._draining, self._pending = ps.epoch_seq, ps.draining, ps.pending_profiles
        self._stats["evictions"] += sum(a.kind is ActionKind.KILL and a.reason == "lru-evict" for a in acts)
        return self._prune()
    def _mark_idle(self) -> list[Doomed]:
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
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers or max(2, lim.global_max_slots),
                                                thread_name_prefix="standby-pool")
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
    def _commit_claim(self, sid: str, epoch: int, profile: ProfileKey, alive: bool,
                      session_key: str | None) -> SlotRecord | None:
        with self._lock:
            prev = self._slots.get(sid)
            if prev is None or prev.epoch != epoch or not fsm.can_claim_slot(prev, profile, session_key):
                return None
            bud = PoolBudget(self._limits(), self._clock(), self._total_rss())
            ps, acts = fsm.plan_claim_result(self._state(), ClaimAttempt(sid, profile, alive, session_key), bud)
            doomed = self._commit(ps, acts)
            cur = self._slots.get(sid)
            won = alive and cur is not None and cur.state is S.CLAIMED and cur.epoch == epoch
            self._stats["hits" if won else "misses"] += 1
        self._finish(doomed, acts)
        return cur if won else None
    def _spawn(self, action: PoolAction) -> None:
        adapter, handle, rss = self._adapters[action.profile.backend_id], cast("WarmSlotHandle | None", None), 0.0
        try:
            handle = adapter.spawn_warm(action.profile, timeout_s=self._limits().warmup_timeout_s)
            rss = adapter.rss_mb(handle)
        except Exception as exc:
            _log.warning("spawn_warm failed env=%s err=%s", action.profile.env_digest[:12], type(exc).__name__)
            if handle is not None:
                self._dispose_many([("", 0, (adapter, handle))])
            handle = None
        self._complete(action, handle, rss)
    def _complete(self, action: PoolAction, handle: WarmSlotHandle | None, rss: float) -> None:
        adapter, orphan, max_rss = self._adapters[action.profile.backend_id], handle, float(self._limits().max_total_rss_mb)
        with self._lock:
            cur0 = self._slots.get(action.slot_id)
            owned = orphan is not None and cur0 is not None and cur0.state is S.WARMING and cur0.epoch == action.epoch
            if owned and orphan is not None:
                self._handles[action.slot_id], orphan = (adapter, orphan), None
            ps, acts = fsm.plan_warmup_complete(self._state(), action.slot_id, action.epoch, WarmupReport(owned, rss, max_rss))
            doomed = self._commit(ps, acts)
        self._dispose_many(doomed)
        if orphan is not None:
            self._dispose_many([("", 0, (adapter, orphan))])
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
    def _finish(self, doomed: list[Doomed], acts: tuple[PoolAction, ...]) -> None:
        self._dispose_bg(doomed)
        for a in acts:
            if a.kind in _SPAWNS and not self._submit(self._spawn, a):
                self._complete(a, None, 0.0)
    def _dispose_bg(self, doomed: list[Doomed]) -> None:
        if doomed and not self._submit(self._dispose_many, doomed):
            self._dispose_many(doomed)
    def _finalize_disposed(self, sid: str, ep: int, entry: Handle, dead: bool) -> tuple[list[Doomed], tuple[PoolAction, ...]]:
        lim = self._limits() if (sid and dead) else self._lim
        with self._lock:
            if dead:
                self._stats["disposes"] += 1
            if not sid:
                if not dead:
                    _log.warning("orphan dispose left process alive")
                return [], ()
            self._disposing.discard(sid)
            if not dead:
                cur = self._slots.get(sid)
                if cur is not None and (cur.state, cur.epoch) == (S.DISPOSING, ep):
                    self._handles[sid] = entry
                return [], ()
            ps, acts = fsm.plan_dispose_done(self._state(), sid, ep, PoolBudget(lim, self._clock(), self._total_rss(exclude=sid)))
            return self._commit(ps, acts), acts
    def _dispose_many(self, doomed: list[Doomed]) -> None:
        for sid, ep, entry in doomed:
            adapter, handle = entry
            try:
                adapter.dispose(handle)
            except Exception as exc:
                _log.warning("dispose failed err=%s", type(exc).__name__)
            extra, acts = self._finalize_disposed(sid, ep, entry, self._safe_dead(adapter, handle))
            if extra or acts:
                self._finish(extra, acts)
    @staticmethod
    def _safe_alive(adapter: StandbyAdapter, handle: WarmSlotHandle) -> bool:
        try:
            return bool(adapter.is_alive(handle))
        except Exception:
            return False
    @staticmethod
    def _safe_dead(adapter: StandbyAdapter, handle: WarmSlotHandle) -> bool:
        try:
            return not bool(adapter.is_alive(handle))
        except Exception:
            return False
