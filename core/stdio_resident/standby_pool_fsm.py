"""Чистая FSM demand-driven warm standby pool (AD-001..AD-004, AD-007, BND-001): Zero-I/O, Zero-Clock."""
from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol, TypeVar

_T = TypeVar("_T")
_PFX = "BRIDGE_DEMAND_STANDBY_"

@dataclass(frozen=True, slots=True)
class ProfileKey:
    """Ключ профиля слота; `session_key` сюда НЕ входит (F-022)."""
    backend_id: str
    model: str
    effort: str
    review_profile: str
    env_digest: str
    cwd_class: str

    @property
    def is_zero_canon(self) -> bool:
        return self.review_profile.strip().lower() == "zero-canon"

@dataclass(frozen=True, slots=True)
class StandbyLimits:
    enabled: bool = False
    sliding_ttl_s: float = 300.0
    max_slots_per_profile: int = 1
    global_max_slots: int = 3
    max_total_rss_mb: int = 1024
    warmup_timeout_s: float = 30.0
    reap_interval_s: float = 5.0

def _to_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    t = value.strip().lower() if isinstance(value, str) else ""
    return True if t in ("1", "true", "yes", "on") else False if t in ("0", "false", "no", "off") else None

def _to_pos_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        n = float(value)
    except ValueError:
        return None
    return n if math.isfinite(n) and n > 0 else None

def _to_pos_int(value: object) -> int | None:
    n = _to_pos_float(value)
    return int(n) if n is not None and n >= 1 else None

def _pick(env: Mapping[str, object] | None, dyn: Mapping[str, object] | None, name: str,
          conv: Callable[[object], _T | None], default: _T) -> _T:
    for src, key in ((env, _PFX + name.upper()), (dyn, name)):
        if src is not None and key in src and (parsed := conv(src[key])) is not None:
            return parsed
    return default

def parse_limits(env_mapping: Mapping[str, object] | None,
                 dyn_mapping: Mapping[str, object] | None = None) -> StandbyLimits:
    """env > dyn > default; невалидные значения (мусор/NaN/inf/<=0) игнорируются."""
    d, e, y = StandbyLimits(), env_mapping, dyn_mapping
    glob = _pick(e, y, "global_max_slots", _to_pos_int, d.global_max_slots)
    per = _pick(e, y, "max_slots_per_profile", _to_pos_int, d.max_slots_per_profile)
    return StandbyLimits(
        _pick(e, y, "enabled", _to_bool, d.enabled), _pick(e, y, "sliding_ttl_s", _to_pos_float, d.sliding_ttl_s),
        min(per, glob), glob, _pick(e, y, "max_total_rss_mb", _to_pos_int, d.max_total_rss_mb),
        _pick(e, y, "warmup_timeout_s", _to_pos_float, d.warmup_timeout_s),
        _pick(e, y, "reap_interval_s", _to_pos_float, d.reap_interval_s))

class WarmSlotHandle(Protocol): ...
class StandbyAdapter(Protocol):
    def spawn_warm(self, profile: ProfileKey, *, timeout_s: float) -> WarmSlotHandle: ...
    def is_alive(self, handle: WarmSlotHandle) -> bool: ...
    def claim(self, handle: WarmSlotHandle) -> object: ...
    def dispose(self, handle: WarmSlotHandle) -> None: ...
    def rss_mb(self, handle: WarmSlotHandle) -> float: ...

class SlotLifecycleState(Enum):
    WARMING, READY, CLAIMED, DISPOSING, CLOSED = "warming", "ready", "claimed", "disposing", "closed"

class PoolEventKind(Enum):
    DEMAND, WARMUP_OK, WARMUP_FAILED, CLAIM = "demand", "warmup_ok", "warmup_failed", "claim"
    TURN_DONE, SLOT_DEAD, REAP_TICK, DRAIN = "turn_done", "slot_dead", "reap_tick", "drain"

class ActionKind(Enum):
    SPAWN, KILL, CLEANUP_HOME, REPLENISH = "spawn", "kill", "cleanup_home", "replenish"

S, E = SlotLifecycleState, PoolEventKind
_LIVE, _STANDBY = frozenset((S.WARMING, S.READY, S.CLAIMED)), frozenset((S.WARMING, S.READY))
_TO_DISPOSING = frozenset((E.SLOT_DEAD, E.REAP_TICK, E.DRAIN))

@dataclass(frozen=True, slots=True)
class PoolAction:
    kind: ActionKind
    slot_id: str
    profile: ProfileKey
    epoch: int
    reason: str = ""

@dataclass(frozen=True, slots=True)
class SlotRecord:
    slot_id: str
    profile: ProfileKey
    state: SlotLifecycleState
    epoch: int
    created_mono: float
    rss_mb: float = 0.0
    zc_home: str = ""
    session_key: str | None = None

@dataclass(frozen=True, slots=True)
class PoolState:
    slots: tuple[SlotRecord, ...] = ()
    profile_last_demand: tuple[tuple[ProfileKey, float], ...] = ()
    epoch_seq: int = 0
    draining: bool = False

@dataclass(frozen=True, slots=True)
class PoolBudget:
    limits: StandbyLimits
    now_mono: float
    total_rss_mb: float = 0.0

Plan = tuple[PoolState, tuple[PoolAction, ...]]

_SIMPLE_TRANS = {
    (S.WARMING, E.WARMUP_OK): S.READY,
    (S.WARMING, E.WARMUP_FAILED): S.DISPOSING,
    (S.READY, E.CLAIM): S.CLAIMED,
    (S.DISPOSING, E.SLOT_DEAD): S.CLOSED,
}

def transition_slot(state: SlotLifecycleState, event: PoolEventKind, *, is_zero_canon: bool,
                    has_session_key: bool = False) -> SlotLifecycleState:
    """AD-003/F-022: `CLAIMED -> READY` только для standard + session_key."""
    if (nxt := _SIMPLE_TRANS.get((state, event))) is not None:
        return nxt
    if state is S.CLAIMED and event is E.TURN_DONE:
        return S.READY if has_session_key and not is_zero_canon else S.DISPOSING
    if state in _LIVE and event in _TO_DISPOSING:
        return S.DISPOSING
    return state

def can_claim_slot(slot: SlotRecord, profile: ProfileKey, session_key: str | None = None) -> bool:
    return slot.state is S.READY and slot.profile == profile and slot.session_key in (None, session_key)

def _find(ps: PoolState, slot_id: str) -> SlotRecord | None:
    return next((s for s in ps.slots if s.slot_id == slot_id), None)
def _put(ps: PoolState, rec: SlotRecord) -> PoolState:
    return replace(ps, slots=tuple(rec if s.slot_id == rec.slot_id else s for s in ps.slots))
def _touch(ps: PoolState, profile: ProfileKey, now: float) -> PoolState:
    return replace(ps, profile_last_demand=tuple(i for i in ps.profile_last_demand if i[0] != profile) + ((profile, now),))
def _kill(rec: SlotRecord, epoch: int, reason: str) -> tuple[PoolAction, ...]:
    return tuple(PoolAction(k, rec.slot_id, rec.profile, epoch, reason) for k in (ActionKind.KILL, ActionKind.CLEANUP_HOME))

def _dispose(ps: PoolState, recs: Iterable[SlotRecord], event: PoolEventKind, reason: str) -> Plan:
    ids = {r.slot_id: r for r in recs}
    moved = tuple(replace(s, state=transition_slot(s.state, event, is_zero_canon=s.profile.is_zero_canon,
                                                   has_session_key=s.session_key is not None))
                  if s.slot_id in ids else s for s in ps.slots)
    return replace(ps, slots=moved), tuple(a for r in ids.values() for a in _kill(r, r.epoch, reason))

def _evict_for_cap(ps: PoolState, profile: ProfileKey, kind: ActionKind) -> Plan | None:
    if kind is not ActionKind.SPAWN:
        return None
    demand = dict(ps.profile_last_demand)
    idle = [s for s in ps.slots if s.state is S.READY and s.profile != profile]
    victim = min(idle, key=lambda s: (demand.get(s.profile, s.created_mono), s.created_mono), default=None)
    return _dispose(ps, (victim,), E.REAP_TICK, "lru-evict") if victim is not None else None

def _try_spawn(ps: PoolState, profile: ProfileKey, bud: PoolBudget, kind: ActionKind) -> Plan:
    lim = bud.limits
    blocked = not lim.enabled or ps.draining or bud.total_rss_mb >= lim.max_total_rss_mb
    if blocked or sum(s.profile == profile and s.state in _STANDBY for s in ps.slots) >= lim.max_slots_per_profile:
        return ps, ()
    pre: tuple[PoolAction, ...] = ()
    if sum(s.state in _LIVE for s in ps.slots) >= lim.global_max_slots:
        evicted = _evict_for_cap(ps, profile, kind)
        if evicted is None:
            return ps, ()
        ps, pre = evicted
    epoch = ps.epoch_seq + 1
    rec = SlotRecord(f"slot-{epoch}", profile, S.WARMING, epoch, bud.now_mono)
    return replace(ps, slots=ps.slots + (rec,), epoch_seq=epoch), pre + (PoolAction(kind, rec.slot_id, profile, epoch, "demand"),)

def plan_demand(ps: PoolState, profile: ProfileKey, limits: StandbyLimits, now_mono: float, total_rss_mb: float) -> Plan:
    return _try_spawn(_touch(ps, profile, now_mono), profile, PoolBudget(limits, now_mono, total_rss_mb), ActionKind.SPAWN)

def plan_warmup_complete(ps: PoolState, slot_id: str, epoch: int, ok: bool, rss_mb: float) -> Plan:
    rec = _find(ps, slot_id)
    if rec is None:
        return ps, ()
    if epoch != rec.epoch:
        return ps, _kill(rec, epoch, "stale-epoch")
    if rec.state is not S.WARMING:
        return ps, ()
    if ps.draining or not ok:
        return _dispose(ps, (rec,), E.DRAIN if ps.draining else E.WARMUP_FAILED, "draining" if ps.draining else "warmup-failed")
    return _put(ps, replace(rec, state=transition_slot(rec.state, E.WARMUP_OK, is_zero_canon=rec.profile.is_zero_canon), rss_mb=rss_mb)), ()

def plan_claim_result(ps: PoolState, slot_id: str, alive: bool, budget: PoolBudget) -> Plan:
    rec = _find(ps, slot_id)
    if rec is None or rec.state is not S.READY:
        return ps, ()
    if alive:
        ps, acts = _put(ps, replace(rec, state=transition_slot(rec.state, E.CLAIM, is_zero_canon=rec.profile.is_zero_canon))), ()
    else:
        ps, acts = _dispose(ps, (rec,), E.SLOT_DEAD, "claim-dead")
    ps, spawn = _try_spawn(_touch(ps, rec.profile, budget.now_mono), rec.profile, budget, ActionKind.REPLENISH)
    return ps, acts + spawn

def plan_turn_done(ps: PoolState, slot_id: str, limits: StandbyLimits, now_mono: float, total_rss_mb: float) -> Plan:
    rec = _find(ps, slot_id)
    if rec is None or rec.state is not S.CLAIMED:
        return ps, ()
    nxt = transition_slot(rec.state, E.TURN_DONE, is_zero_canon=rec.profile.is_zero_canon, has_session_key=rec.session_key is not None)
    if nxt is S.READY:
        return _put(ps, replace(rec, state=nxt)), ()
    ps, acts = _dispose(ps, (rec,), E.TURN_DONE, "turn-done")
    last = dict(ps.profile_last_demand).get(rec.profile)
    if last is None or now_mono - last > limits.sliding_ttl_s:
        return ps, acts
    ps, spawn = _try_spawn(ps, rec.profile, PoolBudget(limits, now_mono, total_rss_mb), ActionKind.REPLENISH)
    return ps, acts + spawn

def plan_reap_tick(ps: PoolState, limits: StandbyLimits, now_mono: float) -> Plan:
    demand = dict(ps.profile_last_demand)
    live = tuple(s for s in ps.slots if s.state in _LIVE)
    stale = tuple(s for s in live
                  if (s.state is S.READY and now_mono - demand.get(s.profile, s.created_mono) > limits.sliding_ttl_s)
                  or (s.state is S.WARMING and now_mono - s.created_mono > limits.warmup_timeout_s))
    fresh = tuple(i for i in ps.profile_last_demand if now_mono - i[1] <= limits.sliding_ttl_s)
    return _dispose(replace(ps, slots=live, profile_last_demand=fresh), stale, E.REAP_TICK, "reap")

def plan_drain(ps: PoolState) -> Plan:
    ps, acts = _dispose(ps, (s for s in ps.slots if s.state in _LIVE), E.DRAIN, "drain")
    return replace(ps, draining=True), acts

def compute_env_digest(env_items: Mapping[str, str], allowlist: Iterable[str]) -> str:
    pairs = "".join(f"{len(k)}:{k}={len(env_items[k])}:{env_items[k]};" for k in sorted(set(allowlist)) if k in env_items)
    return hashlib.sha256(pairs.encode()).hexdigest()
