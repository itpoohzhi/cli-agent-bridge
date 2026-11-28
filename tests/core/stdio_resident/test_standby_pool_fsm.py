"""L1: чистая FSM standby-пула (VER-007, VER-008, AD-001..AD-004, F-022)."""
from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from core.stdio_resident import standby_pool_fsm as fsm
from core.stdio_resident.standby_pool_fsm import (
    ActionKind as A, ClaimAttempt, PoolBudget, PoolEventKind as E, PoolState, ProfileKey,
    SlotLifecycleState as S, SlotRecord, StandbyLimits, WarmupReport,
)

ZC = ProfileKey("codex", "m1", "high", "zero-canon", "d1", "repo")
STD = replace(ZC, review_profile="standard")
OTHER = replace(STD, model="m2")
LIM = StandbyLimits(enabled=True)

def rec(slot_id: str, profile: ProfileKey, state: S, epoch: int = 1,
        session_key: str | None = None) -> SlotRecord:
    return SlotRecord(slot_id, profile, state, epoch, 0.0, session_key=session_key)
def pool(*slots: SlotRecord, demand: tuple[tuple[ProfileKey, float], ...] = (), draining: bool = False,
         seq: int = 5) -> PoolState:
    return PoolState(slots=slots, profile_last_demand=demand, epoch_seq=seq, draining=draining)
def kinds(actions: tuple[fsm.PoolAction, ...]) -> list[A]:
    return [a.kind for a in actions]
def states(ps: PoolState) -> dict[str, S]:
    return {s.slot_id: s.state for s in ps.slots}

# ---- parse_limits (VER-007) ----
def test_limits_parse_defaults() -> None:
    assert fsm.parse_limits(None) == StandbyLimits(False, 300.0, 1, 3, 1024, 30.0, 5.0)
    assert fsm.parse_limits({}, {}) == StandbyLimits()
@pytest.mark.parametrize("raw,expected", [
    ("1", True), ("TRUE", True), (" yes ", True), ("on", True), (True, True),
    ("0", False), ("false", False), ("No", False), ("off", False), (False, False),
])
def test_limits_parse_bool_forms(raw: object, expected: bool) -> None:
    assert fsm.parse_limits({"BRIDGE_DEMAND_STANDBY_ENABLED": raw}).enabled is expected
def test_limits_parse_priority_env_over_dyn_over_default() -> None:
    env = {"BRIDGE_DEMAND_STANDBY_SLIDING_TTL_S": "60", "BRIDGE_DEMAND_STANDBY_ENABLED": "0"}
    dyn = {"sliding_ttl_s": 120, "enabled": True, "warmup_timeout_s": 7.5, "global_max_slots": 4,
           "max_slots_per_profile": 2, "max_total_rss_mb": 2048, "reap_interval_s": 1}
    assert fsm.parse_limits(env, dyn) == StandbyLimits(False, 60.0, 2, 4, 2048, 7.5, 1.0)
@pytest.mark.parametrize("bad", ["abc", "", "nan", "inf", "-inf", "-5", "0", None, [], True, float("nan")])
def test_limits_parse_garbage_falls_back_to_defaults(bad: object) -> None:
    env = {f"BRIDGE_DEMAND_STANDBY_{k}": bad for k in (
        "SLIDING_TTL_S", "MAX_SLOTS_PER_PROFILE", "GLOBAL_MAX_SLOTS", "MAX_TOTAL_RSS_MB",
        "WARMUP_TIMEOUT_S", "REAP_INTERVAL_S")}
    assert fsm.parse_limits(env) == StandbyLimits()
def test_limits_parse_garbage_env_falls_through_to_valid_dyn() -> None:
    assert fsm.parse_limits({"BRIDGE_DEMAND_STANDBY_SLIDING_TTL_S": "nan"}, {"sliding_ttl_s": 42}).sliding_ttl_s == 42.0
def test_limits_parse_clamps_per_profile_to_global() -> None:
    got = fsm.parse_limits({"BRIDGE_DEMAND_STANDBY_MAX_SLOTS_PER_PROFILE": "9",
                            "BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS": "2"})
    assert (got.max_slots_per_profile, got.global_max_slots) == (2, 2)

# ---- transition_slot / can_claim_slot ----
@pytest.mark.parametrize("zc,keyed,expected", [
    (True, False, S.DISPOSING), (True, True, S.DISPOSING), (False, False, S.DISPOSING), (False, True, S.READY),
])
def test_transition_turn_done_never_returns_zero_canon_or_stateless_to_ready(zc: bool, keyed: bool, expected: S) -> None:
    assert fsm.transition_slot(S.CLAIMED, E.TURN_DONE, is_zero_canon=zc, has_session_key=keyed) is expected
@pytest.mark.parametrize("state,event,expected", [
    (S.WARMING, E.WARMUP_OK, S.READY), (S.WARMING, E.WARMUP_FAILED, S.DISPOSING),
    (S.WARMING, E.DRAIN, S.DISPOSING), (S.WARMING, E.CLAIM, S.WARMING),
    (S.READY, E.CLAIM, S.CLAIMED), (S.READY, E.REAP_TICK, S.DISPOSING),
    (S.READY, E.SLOT_DEAD, S.DISPOSING), (S.READY, E.TURN_DONE, S.READY),
    (S.CLAIMED, E.SLOT_DEAD, S.DISPOSING), (S.CLAIMED, E.DRAIN, S.DISPOSING),
    (S.CLAIMED, E.DEMAND, S.CLAIMED), (S.DISPOSING, E.SLOT_DEAD, S.CLOSED),
    (S.DISPOSING, E.CLAIM, S.DISPOSING), (S.CLOSED, E.WARMUP_OK, S.CLOSED),
])
def test_transition_table(state: S, event: E, expected: S) -> None:
    assert fsm.transition_slot(state, event, is_zero_canon=False, has_session_key=True) is expected
@pytest.mark.parametrize("slot,profile,key,expected", [
    (rec("a", STD, S.READY), STD, None, True), (rec("a", STD, S.READY), STD, "s1", True),
    (rec("a", STD, S.READY), OTHER, None, False), (rec("a", STD, S.WARMING), STD, None, False),
    (rec("a", STD, S.CLAIMED), STD, None, False), (rec("a", STD, S.READY, session_key="s1"), STD, "s1", True),
    (rec("a", STD, S.READY, session_key="s1"), STD, "s2", False), (rec("a", STD, S.READY, session_key="s1"), STD, None, False),
])
def test_can_claim_slot_session_affinity(slot: SlotRecord, profile: ProfileKey, key: str | None, expected: bool) -> None:
    assert fsm.can_claim_slot(slot, profile, key) is expected
def test_profile_key_zero_canon_flag_is_case_insensitive() -> None:
    assert replace(ZC, review_profile=" Zero-Canon ").is_zero_canon and not STD.is_zero_canon

# ---- plan_demand ----
def test_demand_cold_start_spawns_and_records_demand() -> None:
    ps, acts = fsm.plan_demand(PoolState(), STD, LIM, 10.0, 0.0)
    assert kinds(acts) == [A.SPAWN] and acts[0].profile == STD and acts[0].epoch == 1
    assert states(ps) == {acts[0].slot_id: S.WARMING}
    assert dict(ps.profile_last_demand) == {STD: 10.0} and ps.epoch_seq == 1
def test_demand_disabled_is_noop_for_spawn() -> None:
    assert fsm.plan_demand(PoolState(), STD, StandbyLimits(), 1.0, 0.0)[1] == ()
def test_demand_slides_ttl_without_second_spawn_per_profile() -> None:
    start = pool(rec("s1", STD, S.READY), demand=((STD, 1.0),))
    ps, acts = fsm.plan_demand(start, STD, LIM, 50.0, 0.0)
    assert acts == () and dict(ps.profile_last_demand) == {STD: 50.0} and ps.slots == start.slots
def test_demand_draining_and_rss_cap_block_spawn() -> None:
    assert fsm.plan_demand(pool(draining=True), STD, LIM, 1.0, 0.0)[1] == ()
    ps, acts = fsm.plan_demand(PoolState(), STD, LIM, 1.0, float(LIM.max_total_rss_mb))
    assert acts == () and ps.slots == ()
    assert fsm.plan_demand(PoolState(), STD, LIM, 1.0, float("nan"))[1] == ()
def test_demand_global_cap_evicts_once_and_spawns_on_dispose_done() -> None:
    lim = replace(LIM, global_max_slots=2)
    p_old, p_new = replace(STD, model="old"), replace(STD, model="new")
    start = pool(rec("o", p_old, S.READY, 1), rec("n", p_new, S.READY, 2), demand=((p_old, 5.0), (p_new, 20.0)))
    ps, acts = fsm.plan_demand(start, STD, lim, 30.0, 0.0)
    assert kinds(acts) == [A.KILL, A.CLEANUP_HOME] and {a.slot_id for a in acts} == {"o"}
    assert states(ps)["o"] is S.DISPOSING and ps.pending_profiles == (STD,)
    # Burst demand while victim is still DISPOSING MUST NOT evict second READY slot ("n")
    ps_b, acts_b = fsm.plan_demand(ps, STD, lim, 30.5, 0.0)
    assert acts_b == () and states(ps_b)["n"] is S.READY
    # Completing dispose of "o" closes it and spawns queued STD without overshoot
    ps2, acts2 = fsm.plan_dispose_done(ps_b, "o", 1, PoolBudget(lim, 31.0, 0.0))
    assert kinds(acts2) == [A.REPLENISH] and acts2[0].profile == STD and states(ps2)["o"] is S.CLOSED
    assert sum(s.state in (S.WARMING, S.READY, S.CLAIMED, S.DISPOSING) for s in ps2.slots) == 2
def test_demand_global_cap_without_idle_victim_does_nothing() -> None:
    lim = replace(LIM, global_max_slots=1)
    assert fsm.plan_demand(pool(rec("c", OTHER, S.CLAIMED)), STD, lim, 1.0, 0.0)[1] == ()
def test_demand_does_not_overshoot_per_profile_for_keyed_claimed_standard() -> None:
    start = pool(rec("s", STD, S.CLAIMED, session_key="sess-1"), demand=((STD, 1.0),))
    ps, acts = fsm.plan_demand(start, STD, LIM, 2.0, 0.0)
    assert acts == () and len(ps.slots) == 1

# ---- plan_warmup_complete ----
def test_warmup_ok_and_rss_cap_and_nan_fail_closed() -> None:
    ps, acts = fsm.plan_warmup_complete(pool(rec("s", STD, S.WARMING)), "s", 1, WarmupReport(True, 77.5, 1024.0))
    assert acts == () and ps.slots[0].state is S.READY and ps.slots[0].rss_mb == 77.5
    ps_hi, acts_hi = fsm.plan_warmup_complete(pool(rec("s", STD, S.WARMING)), "s", 1, WarmupReport(True, 2048.0, 1024.0))
    assert kinds(acts_hi) == [A.KILL, A.CLEANUP_HOME] and states(ps_hi)["s"] is S.DISPOSING
    ps_nan, acts_nan = fsm.plan_warmup_complete(pool(rec("s", STD, S.WARMING)), "s", 1, WarmupReport(True, float("nan"), 1024.0))
    assert kinds(acts_nan) == [A.KILL, A.CLEANUP_HOME] and states(ps_nan)["s"] is S.DISPOSING
def test_warmup_stale_epoch_and_unknown_are_noop() -> None:
    live = pool(rec("s", STD, S.CLAIMED, epoch=2))
    assert fsm.plan_warmup_complete(live, "s", 1, WarmupReport(True, 10.0, 1024.0)) == (live, ())
    disp = pool(rec("s", STD, S.DISPOSING))
    assert fsm.plan_warmup_complete(disp, "zzz", 1, WarmupReport(True, 1.0, 1024.0)) == (disp, ())
    assert fsm.plan_warmup_complete(disp, "s", 1, WarmupReport(True, 1.0, 1024.0)) == (disp, ())
@pytest.mark.parametrize("ok,draining", [(True, True), (False, False)])
def test_warmup_drain_or_failed_kills_without_ready(ok: bool, draining: bool) -> None:
    ps, acts = fsm.plan_warmup_complete(pool(rec("s", STD, S.WARMING), draining=draining), "s", 1, WarmupReport(ok, 1.0, 1024.0))
    assert kinds(acts) == [A.KILL, A.CLEANUP_HOME] and S.READY not in states(ps).values()

# ---- plan_claim_result ----
def test_claim_dead_slot_kills_cleans_and_replenishes() -> None:
    ps, acts = fsm.plan_claim_result(pool(rec("s", STD, S.READY)), ClaimAttempt("s", STD, False), PoolBudget(LIM, 10.0, 0.0))
    assert kinds(acts) == [A.KILL, A.CLEANUP_HOME, A.REPLENISH]
    assert states(ps)["s"] is S.DISPOSING and acts[2].slot_id != "s"
def test_claim_alive_binds_key_validates_profile_and_replenishes_stateless() -> None:
    ps, acts = fsm.plan_claim_result(pool(rec("s", STD, S.READY)), ClaimAttempt("s", STD, True), PoolBudget(LIM, 10.0, 0.0))
    assert kinds(acts) == [A.REPLENISH] and states(ps)["s"] is S.CLAIMED
    # Profile mismatch is rejected inside FSM (non-tautological can_claim_slot)
    base = pool(rec("s", STD, S.READY))
    assert fsm.plan_claim_result(base, ClaimAttempt("s", OTHER, True), PoolBudget(LIM, 10.0, 0.0)) == (base, ())
    # Keyed standard binds key and skips duplicate REPLENISH
    ps2, acts2 = fsm.plan_claim_result(base, ClaimAttempt("s", STD, True, "sess-1"), PoolBudget(LIM, 10.0, 0.0))
    assert acts2 == () and ps2.slots[0].state is S.CLAIMED and ps2.slots[0].session_key == "sess-1"
    ps3, acts3 = fsm.plan_turn_done(ps2, "s", LIM, 11.0, 0.0)
    assert acts3 == () and len(ps3.slots) == 1 and ps3.slots[0].state is S.READY
def test_claim_alive_no_replenish_at_cap_and_ignores_non_ready() -> None:
    lim = replace(LIM, global_max_slots=1)
    ps, acts = fsm.plan_claim_result(pool(rec("s", STD, S.READY)), ClaimAttempt("s", STD, True), PoolBudget(lim, 1.0, 0.0))
    assert acts == () and states(ps) == {"s": S.CLAIMED}
    warm = pool(rec("s", STD, S.WARMING))
    assert fsm.plan_claim_result(warm, ClaimAttempt("s", STD, True), PoolBudget(LIM, 1.0, 0.0)) == (warm, ())

# ---- plan_turn_done ----
def test_turn_done_zero_canon_disposes_and_replenishes_including_at_global_cap() -> None:
    start = pool(rec("z", ZC, S.CLAIMED), demand=((ZC, 100.0),))
    ps, acts = fsm.plan_turn_done(start, "z", LIM, 150.0, 0.0)
    assert kinds(acts) == [A.KILL, A.CLEANUP_HOME, A.REPLENISH] and states(ps)["z"] is S.DISPOSING
    # At global_max_slots=1: queues pending ZC, then plan_dispose_done emits REPLENISH cleanly
    lim1 = replace(LIM, global_max_slots=1)
    ps1, acts1 = fsm.plan_turn_done(start, "z", lim1, 150.0, 0.0)
    assert kinds(acts1) == [A.KILL, A.CLEANUP_HOME] and ps1.pending_profiles == (ZC,)
    ps2, acts2 = fsm.plan_dispose_done(ps1, "z", 1, PoolBudget(lim1, 151.0, 0.0))
    assert kinds(acts2) == [A.REPLENISH] and acts2[0].profile == ZC
def test_turn_done_zero_canon_no_replenish_after_ttl() -> None:
    start = pool(rec("z", ZC, S.CLAIMED), demand=((ZC, 100.0),))
    ps, acts = fsm.plan_turn_done(start, "z", LIM, 100.0 + LIM.sliding_ttl_s + 1, 0.0)
    assert kinds(acts) == [A.KILL, A.CLEANUP_HOME] and len(ps.slots) == 1
def test_turn_done_standard_keyed_vs_stateless() -> None:
    ps, acts = fsm.plan_turn_done(pool(rec("s", STD, S.CLAIMED, session_key="k"), demand=((STD, 1.0),)), "s", LIM, 2.0, 0.0)
    assert acts == () and ps.slots[0].state is S.READY and ps.slots[0].session_key == "k"
    ps2, acts2 = fsm.plan_turn_done(pool(rec("s", STD, S.CLAIMED), demand=((STD, 1.0),)), "s", LIM, 2.0, 0.0)
    assert A.KILL in kinds(acts2) and states(ps2)["s"] is S.DISPOSING

# ---- plan_reap_tick / plan_drain ----
def test_reap_closes_expired_ready_and_hung_warming_and_retains_disposing() -> None:
    start = pool(
        rec("old", STD, S.READY), rec("fresh", OTHER, S.READY),
        SlotRecord("hung", ZC, S.WARMING, 1, 0.0), SlotRecord("boot", replace(ZC, model="x"), S.WARMING, 1, 390.0),
        rec("busy", replace(STD, model="b"), S.CLAIMED),
        demand=((STD, 0.0), (OTHER, 350.0), (ZC, 390.0)),
    )
    ps, acts = fsm.plan_reap_tick(start, LIM, 400.0)
    assert {a.slot_id for a in acts if a.kind is A.KILL} == {"old", "hung"}
    got = states(ps)
    assert got["fresh"] is S.READY and got["boot"] is S.WARMING and got["busy"] is S.CLAIMED
    ps_d, _ = fsm.plan_reap_tick(pool(rec("d", STD, S.DISPOSING), rec("c", STD, S.CLOSED)), LIM, 1.0)
    assert states(ps_d) == {"d": S.DISPOSING}
    ps_c, _ = fsm.plan_dispose_done(ps_d, "d", 1)
    assert fsm.plan_reap_tick(ps_c, LIM, 2.0)[0].slots == ()
def test_drain_kills_all_live_slots_and_plan_functions_are_pure() -> None:
    start = pool(rec("a", STD, S.READY), rec("b", ZC, S.CLAIMED), rec("c", OTHER, S.WARMING), rec("d", STD, S.DISPOSING))
    ps, acts = fsm.plan_drain(start)
    assert ps.draining and {a.slot_id for a in acts} == {"a", "b", "c"} and set(states(ps).values()) == {S.DISPOSING}
    snap = (start.slots, start.profile_last_demand, start.epoch_seq, start.draining)
    for _ in (fsm.plan_drain(start), fsm.plan_reap_tick(start, LIM, 1e6), fsm.plan_demand(start, OTHER, LIM, 2.0, 0.0)):
        assert (start.slots, start.profile_last_demand, start.epoch_seq, start.draining) == snap

# ---- compute_env_digest & VER-008 ----
def test_env_digest_deterministic_allowlist_and_collision_safe() -> None:
    a = fsm.compute_env_digest({"A": "1", "B": "2"}, ["B", "A"])
    assert a == fsm.compute_env_digest({"B": "2", "A": "1"}, ("A", "B", "A")) and len(a) == 64
    assert fsm.compute_env_digest({"A": "1"}, ["A"]) == fsm.compute_env_digest({"A": "1", "SECRET": "x"}, ["A"])
    assert "sk-secret" not in fsm.compute_env_digest({"KEY": "sk-secret"}, ["KEY"])
    assert fsm.compute_env_digest({"A": "b=1;c", "D": ""}, ["A", "D"]) != fsm.compute_env_digest({"A": "b", "D": "1;c"}, ["A", "D"])
def test_module_is_io_and_clock_free() -> None:
    tree = ast.parse(Path(fsm.__file__).read_text(encoding="utf-8"))
    allowed = {"__future__", "hashlib", "math", "collections", "dataclasses", "enum", "typing"}
    mods = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    mods |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert mods <= allowed
