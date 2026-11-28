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
def _to_bool(v: object) -> bool | None:
    if isinstance(v, bool):
        return v
    t = v.strip().lower() if isinstance(v, str) else ""
    return True if t in ("1", "true", "yes", "on") else False if t in ("0", "false", "no", "off") else None
def _to_pos_float(v: object) -> float | None:
    try:
        n = float(v) if not isinstance(v, bool) and isinstance(v, (int, float, str)) else math.nan
    except ValueError:
        return None
    return n if math.isfinite(n) and n > 0 else None
def _to_pos_int(v: object) -> int | None:
    return int(n) if (n := _to_pos_float(v)) is not None and n >= 1 else None
def _pick(e: Mapping[str, object] | None, y: Mapping[str, object] | None, name: str, conv: Callable[[object], _T | None], default: _T) -> _T:
    for src, key in ((e, _PFX + name.upper()), (y, name)):
        if src is not None and key in src and (p := conv(src[key])) is not None:
            return p
    return default
def parse_limits(env_mapping: Mapping[str, object] | None, dyn_mapping: Mapping[str, object] | None = None) -> StandbyLimits:
    """env > dyn > default; невалидные значения (мусор/NaN/inf/<=0) игнорируются."""
    d, e, y = StandbyLimits(), env_mapping, dyn_mapping
    glob = _pick(e, y, "global_max_slots", _to_pos_int, d.global_max_slots)
    per = min(_pick(e, y, "max_slots_per_profile", _to_pos_int, d.max_slots_per_profile), glob)
    return StandbyLimits(_pick(e, y, "enabled", _to_bool, d.enabled), _pick(e, y, "sliding_ttl_s", _to_pos_float, d.sliding_ttl_s), per, glob, _pick(e, y, "max_total_rss_mb", _to_pos_int, d.max_total_rss_mb), _pick(e, y, "warmup_timeout_s", _to_pos_float, d.warmup_timeout_s), _pick(e, y, "reap_interval_s", _to_pos_float, d.reap_interval_s))
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
_OCCUPYING = frozenset((S.WARMING, S.READY, S.CLAIMED, S.DISPOSING))
_TO_DISPOSING = frozenset((E.SLOT_DEAD, E.REAP_TICK, E.DRAIN))
_SIMPLE_TRANS = {(S.WARMING, E.WARMUP_OK): S.READY, (S.WARMING, E.WARMUP_FAILED): S.DISPOSING,
                 (S.READY, E.CLAIM): S.CLAIMED, (S.DISPOSING, E.SLOT_DEAD): S.CLOSED}
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
    pending_profiles: tuple[ProfileKey, ...] = ()
@dataclass(frozen=True, slots=True)
class PoolBudget:
    limits: StandbyLimits
    now_mono: float
    total_rss_mb: float = 0.0
@dataclass(frozen=True, slots=True)
class WarmupReport:
    ok: bool
    rss_mb: float
    max_total_rss_mb: float
    external_rss_mb: float = 0.0
@dataclass(frozen=True, slots=True)
class ClaimAttempt:
    slot_id: str
    profile: ProfileKey
    alive: bool
    session_key: str | None = None
Plan = tuple[PoolState, tuple[PoolAction, ...]]
def transition_slot(state: SlotLifecycleState, event: PoolEventKind, *, is_zero_canon: bool, has_session_key: bool = False) -> SlotLifecycleState:
    """AD-003/F-022: `CLAIMED -> READY` только для standard + session_key."""
    if (nxt := _SIMPLE_TRANS.get((state, event))) is not None:
        return nxt
    if state is S.CLAIMED and event is E.TURN_DONE:
        return S.READY if has_session_key and not is_zero_canon else S.DISPOSING
    return S.DISPOSING if state in _LIVE and event in _TO_DISPOSING else state
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
def _valid_rss(val: float) -> float | None:
    return val if math.isfinite(val) and val >= 0.0 else None
def _counts_for_profile(s: SlotRecord, profile: ProfileKey) -> bool:
    return s.profile == profile and (s.state in _STANDBY or (s.state is S.CLAIMED and not s.profile.is_zero_canon and s.session_key is not None))
def _dispose(ps: PoolState, recs: Iterable[SlotRecord], event: PoolEventKind, reason: str) -> Plan:
    ids = {r.slot_id: r for r in recs}
    moved = tuple(replace(s, state=transition_slot(s.state, event, is_zero_canon=s.profile.is_zero_canon, has_session_key=s.session_key is not None)) if s.slot_id in ids else s for s in ps.slots)
    return replace(ps, slots=moved), tuple(a for r in ids.values() for a in _kill(r, r.epoch, reason))
def _evict_for_cap(ps: PoolState, profile: ProfileKey, kind: ActionKind) -> Plan:
    ps_q = ps if profile in ps.pending_profiles else replace(ps, pending_profiles=ps.pending_profiles + (profile,))
    if kind is not ActionKind.SPAWN or any(s.state is S.DISPOSING for s in ps.slots):
        return ps_q, ()
    demand = dict(ps.profile_last_demand)
    victim = min((s for s in ps.slots if s.state is S.READY and s.profile != profile), key=lambda s: (demand.get(s.profile, s.created_mono), s.created_mono), default=None)
    return _dispose(ps_q, (victim,), E.REAP_TICK, "lru-evict") if victim is not None else (ps_q, ())
def _queue(ps: PoolState, profile: ProfileKey) -> PoolState:
    return ps if profile in ps.pending_profiles else replace(ps, pending_profiles=ps.pending_profiles + (profile,))
def _can_spawn(ps: PoolState, profile: ProfileKey, bud: PoolBudget) -> bool:
    lim = bud.limits
    return lim.enabled and not ps.draining and _valid_rss(bud.total_rss_mb) is not None and sum(_counts_for_profile(s, profile) for s in ps.slots) < lim.max_slots_per_profile
def _try_spawn(ps: PoolState, profile: ProfileKey, bud: PoolBudget, kind: ActionKind) -> Plan:
    if not _can_spawn(ps, profile, bud):
        return ps, ()
    if bud.total_rss_mb >= bud.limits.max_total_rss_mb:
        return (_queue(ps, profile), ()) if any(s.state is S.DISPOSING for s in ps.slots) else (ps, ())
    if sum(s.state in _OCCUPYING for s in ps.slots) >= bud.limits.global_max_slots:
        return _evict_for_cap(ps, profile, kind)
    epoch = ps.epoch_seq + 1
    rec = SlotRecord(f"slot-{epoch}", profile, S.WARMING, epoch, bud.now_mono)
    rem = tuple(p for p in ps.pending_profiles if p != profile)
    return replace(ps, slots=ps.slots + (rec,), epoch_seq=epoch, pending_profiles=rem), (PoolAction(kind, rec.slot_id, profile, epoch, "demand"),)
def plan_demand(ps: PoolState, profile: ProfileKey, limits: StandbyLimits, now_mono: float, total_rss_mb: float) -> Plan:
    return _try_spawn(_touch(ps, profile, now_mono), profile, PoolBudget(limits, now_mono, total_rss_mb), ActionKind.SPAWN)
def _warmup_fail_reason(ps: PoolState, slot_id: str, report: WarmupReport) -> str | None:
    if ps.draining or not report.ok:
        return "draining" if ps.draining else "warmup-failed"
    rss, ext = _valid_rss(report.rss_mb), _valid_rss(report.external_rss_mb)
    if rss is None or ext is None:
        return "rss-invalid"
    other = sum(s.rss_mb for s in ps.slots if s.state in _OCCUPYING and s.slot_id != slot_id)
    return "rss-cap" if other + ext + rss > report.max_total_rss_mb else None
def plan_warmup_complete(ps: PoolState, slot_id: str, epoch: int, report: WarmupReport) -> Plan:
    """No-op на stale epoch/не-WARMING; проверяет конечность и фактический RSS cap."""
    rec = _find(ps, slot_id)
    if rec is None or rec.state is not S.WARMING or epoch != rec.epoch:
        return ps, ()
    if (reason := _warmup_fail_reason(ps, slot_id, report)) is not None:
        return _dispose(ps, (rec,), E.DRAIN if ps.draining else E.WARMUP_FAILED, reason)
    nxt = transition_slot(rec.state, E.WARMUP_OK, is_zero_canon=rec.profile.is_zero_canon)
    return _put(ps, replace(rec, state=nxt, rss_mb=report.rss_mb)), ()
def plan_claim_result(ps: PoolState, attempt: ClaimAttempt, budget: PoolBudget) -> Plan:
    """Проверяет `can_claim_slot` по `attempt.profile`, биндит `session_key` и не пробивает per-profile cap."""
    rec = _find(ps, attempt.slot_id)
    if rec is None or not can_claim_slot(rec, attempt.profile, attempt.session_key):
        return ps, ()
    bound = None if rec.profile.is_zero_canon else attempt.session_key
    ps, acts = (_put(ps, replace(rec, state=transition_slot(rec.state, E.CLAIM, is_zero_canon=rec.profile.is_zero_canon), session_key=bound)), ()) if attempt.alive else _dispose(ps, (rec,), E.SLOT_DEAD, "claim-dead")
    ps = _touch(ps, rec.profile, budget.now_mono)
    if attempt.alive and bound is not None:
        return ps, acts
    ps, spawn = _try_spawn(ps, rec.profile, budget, ActionKind.REPLENISH)
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
def _drain_pending(ps: PoolState, budget: PoolBudget) -> Plan:
    demand = dict(ps.profile_last_demand)
    rem: list[ProfileKey] = []
    acts: list[PoolAction] = []
    for prof in ps.pending_profiles:
        last = demand.get(prof)
        if last is None or budget.now_mono - last > budget.limits.sliding_ttl_s:
            continue
        ps2, spawned = _try_spawn(ps, prof, budget, ActionKind.REPLENISH)
        if spawned:
            ps = ps2
            acts.extend(spawned)
        elif sum(s.state in _OCCUPYING for s in ps.slots) >= budget.limits.global_max_slots:
            rem.append(prof)
    return replace(ps, pending_profiles=tuple(rem)), tuple(acts)
def plan_dispose_done(ps: PoolState, slot_id: str, epoch: int, budget: PoolBudget | None = None) -> Plan:
    """DISPOSING -> CLOSED и запуск отложенного SPAWN/REPLENISH из `pending_profiles` без overshoot cap."""
    rec = _find(ps, slot_id)
    if rec is None or rec.state is not S.DISPOSING or rec.epoch != epoch:
        return ps, ()
    ps = _put(ps, replace(rec, state=transition_slot(rec.state, E.SLOT_DEAD, is_zero_canon=rec.profile.is_zero_canon)))
    return _drain_pending(ps, budget) if budget is not None and not ps.draining and ps.pending_profiles else (ps, ())
def _is_stale(s: SlotRecord, demand: Mapping[ProfileKey, float], lim: StandbyLimits, now: float) -> bool:
    return ((s.state is S.READY and now - demand.get(s.profile, s.created_mono) > lim.sliding_ttl_s)
            or (s.state is S.WARMING and now - s.created_mono > lim.warmup_timeout_s))
def plan_reap_tick(ps: PoolState, limits: StandbyLimits, now_mono: float) -> Plan:
    demand = dict(ps.profile_last_demand)
    kept = tuple(s for s in ps.slots if s.state in _OCCUPYING)
    stale = tuple(s for s in kept if _is_stale(s, demand, limits, now_mono))
    fresh = tuple(i for i in ps.profile_last_demand if now_mono - i[1] <= limits.sliding_ttl_s)
    pend = tuple(p for p in ps.pending_profiles if p in {k for k, _ in fresh})
    return _dispose(replace(ps, slots=kept, profile_last_demand=fresh, pending_profiles=pend), stale, E.REAP_TICK, "reap")
def plan_drain(ps: PoolState) -> Plan:
    ps, acts = _dispose(ps, (s for s in ps.slots if s.state in _LIVE), E.DRAIN, "drain")
    return replace(ps, draining=True, pending_profiles=()), acts
def compute_env_digest(env_items: Mapping[str, str], allowlist: Iterable[str]) -> str:
    pairs = "".join(f"{len(k)}:{k}={len(env_items[k])}:{env_items[k]};" for k in sorted(set(allowlist)) if k in env_items)
    return hashlib.sha256(pairs.encode()).hexdigest()
