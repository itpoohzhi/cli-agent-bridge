"""L1: чистая FSM standby-пула (VER-007, VER-008, AD-001..AD-004, F-022)."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from core.stdio_resident import standby_pool_fsm as fsm
from core.stdio_resident.standby_pool_fsm import (
    ActionKind as A,
    PoolEventKind as E,
    PoolState,
    ProfileKey,
    SlotLifecycleState as S,
    SlotRecord,
    StandbyLimits,
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
    got = fsm.parse_limits(env, dyn)
    assert got == StandbyLimits(False, 60.0, 2, 4, 2048, 7.5, 1.0)

@pytest.mark.parametrize("bad", ["abc", "", "nan", "inf", "-inf", "-5", "0", None, [], True, float("nan")])
def test_limits_parse_garbage_falls_back_to_defaults(bad: object) -> None:
    env = {f"BRIDGE_DEMAND_STANDBY_{k}": bad for k in (
        "SLIDING_TTL_S", "MAX_SLOTS_PER_PROFILE", "GLOBAL_MAX_SLOTS", "MAX_TOTAL_RSS_MB",
        "WARMUP_TIMEOUT_S", "REAP_INTERVAL_S")}
    assert fsm.parse_limits(env) == StandbyLimits()

def test_limits_parse_garbage_env_falls_through_to_valid_dyn() -> None:
    got = fsm.parse_limits({"BRIDGE_DEMAND_STANDBY_SLIDING_TTL_S": "nan"}, {"sliding_ttl_s": 42})
    assert got.sliding_ttl_s == 42.0

def test_limits_parse_clamps_per_profile_to_global() -> None:
    got = fsm.parse_limits({"BRIDGE_DEMAND_STANDBY_MAX_SLOTS_PER_PROFILE": "9",
                            "BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS": "2"})
    assert (got.max_slots_per_profile, got.global_max_slots) == (2, 2)

# ---- transition_slot / can_claim_slot ----

@pytest.mark.parametrize("zc,keyed,expected", [
    (True, False, S.DISPOSING), (True, True, S.DISPOSING),
    (False, False, S.DISPOSING), (False, True, S.READY),
])
def test_transition_turn_done_never_returns_zero_canon_or_stateless_to_ready(
        zc: bool, keyed: bool, expected: S) -> None:
    got = fsm.transition_slot(S.CLAIMED, E.TURN_DONE, is_zero_canon=zc, has_session_key=keyed)
    assert got is expected

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
    (rec("a", STD, S.READY), STD, None, True),
    (rec("a", STD, S.READY), STD, "s1", True),
    (rec("a", STD, S.READY), OTHER, None, False),
    (rec("a", STD, S.WARMING), STD, None, False),
    (rec("a", STD, S.CLAIMED), STD, None, False),
    (rec("a", STD, S.READY, session_key="s1"), STD, "s1", True),
    (rec("a", STD, S.READY, session_key="s1"), STD, "s2", False),
    (rec("a", STD, S.READY, session_key="s1"), STD, None, False),
])
def test_can_claim_slot_session_affinity(slot: SlotRecord, profile: ProfileKey, key: str | None,
                                         expected: bool) -> None:
    assert fsm.can_claim_slot(slot, profile, key) is expected

def test_profile_key_zero_canon_flag_is_case_insensitive() -> None:
    assert replace(ZC, review_profile=" Zero-Canon ").is_zero_canon
    assert not STD.is_zero_canon

# ---- plan_demand ----

def test_demand_cold_start_spawns_and_records_demand() -> None:
    ps, acts = fsm.plan_demand(PoolState(), STD, LIM, 10.0, 0.0)
    assert kinds(acts) == [A.SPAWN] and acts[0].profile == STD and acts[0].epoch == 1
    assert states(ps) == {acts[0].slot_id: S.WARMING}
    assert dict(ps.profile_last_demand) == {STD: 10.0} and ps.epoch_seq == 1

def test_demand_disabled_is_noop_for_spawn() -> None:
    _, acts = fsm.plan_demand(PoolState(), STD, StandbyLimits(), 1.0, 0.0)
    assert acts == ()

def test_demand_slides_ttl_without_second_spawn_per_profile() -> None:
    start = pool(rec("s1", STD, S.READY), demand=((STD, 1.0),))
    ps, acts = fsm.plan_demand(start, STD, LIM, 50.0, 0.0)
    assert acts == () and dict(ps.profile_last_demand) == {STD: 50.0} and ps.slots == start.slots

def test_demand_draining_blocks_spawn() -> None:
    assert fsm.plan_demand(pool(draining=True), STD, LIM, 1.0, 0.0)[1] == ()

def test_demand_rss_cap_blocks_spawn() -> None:
    ps, acts = fsm.plan_demand(PoolState(), STD, LIM, 1.0, float(LIM.max_total_rss_mb))
    assert acts == () and ps.slots == ()

def test_demand_global_cap_evicts_lru_idle_profile_then_spawns() -> None:
    lim = replace(LIM, global_max_slots=2)
    p_old = replace(STD, model="old")
    p_new = replace(STD, model="new")
    start = pool(rec("o", p_old, S.READY, 1), rec("n", p_new, S.READY, 2),
                 demand=((p_old, 5.0), (p_new, 20.0)))
    ps, acts = fsm.plan_demand(start, STD, lim, 30.0, 0.0)
    assert kinds(acts) == [A.KILL, A.CLEANUP_HOME, A.SPAWN]
    assert {a.slot_id for a in acts[:2]} == {"o"}
    assert states(ps)["o"] is S.DISPOSING and states(ps)["n"] is S.READY

def test_demand_global_cap_without_idle_victim_does_nothing() -> None:
    lim = replace(LIM, global_max_slots=1)
    start = pool(rec("c", OTHER, S.CLAIMED))
    assert fsm.plan_demand(start, STD, lim, 1.0, 0.0)[1] == ()

# ---- plan_warmup_complete ----

def test_warmup_ok_commits_ready_with_rss() -> None:
    ps, acts = fsm.plan_warmup_complete(pool(rec("s", STD, S.WARMING)), "s", 1, True, 77.5)
    assert acts == () and ps.slots[0].state is S.READY and ps.slots[0].rss_mb == 77.5

@pytest.mark.parametrize("epoch,ok,draining", [(9, True, False), (1, True, True), (1, False, False)])
def test_warmup_stale_drain_or_failed_kills_without_ready(epoch: int, ok: bool, draining: bool) -> None:
    start = pool(rec("s", STD, S.WARMING), draining=draining)
    ps, acts = fsm.plan_warmup_complete(start, "s", epoch, ok, 1.0)
    assert kinds(acts) == [A.KILL, A.CLEANUP_HOME]
    assert S.READY not in states(ps).values()

def test_warmup_unknown_or_duplicate_is_noop() -> None:
    start = pool(rec("s", STD, S.DISPOSING))
    assert fsm.plan_warmup_complete(start, "zzz", 1, True, 1.0) == (start, ())
    assert fsm.plan_warmup_complete(start, "s", 1, True, 1.0) == (start, ())

# ---- plan_claim_result ----

def test_claim_dead_slot_kills_cleans_and_replenishes() -> None:
    ps, acts = fsm.plan_claim_result(pool(rec("s", STD, S.READY)), "s", False, fsm.PoolBudget(LIM, 10.0, 0.0))
    assert kinds(acts) == [A.KILL, A.CLEANUP_HOME, A.REPLENISH]
    assert states(ps)["s"] is S.DISPOSING and acts[2].slot_id != "s"

def test_claim_alive_slot_marks_claimed_and_replenishes() -> None:
    ps, acts = fsm.plan_claim_result(pool(rec("s", STD, S.READY)), "s", True, fsm.PoolBudget(LIM, 10.0, 0.0))
    assert kinds(acts) == [A.REPLENISH]
    assert states(ps)["s"] is S.CLAIMED and states(ps)[acts[0].slot_id] is S.WARMING

def test_claim_alive_no_replenish_when_limits_block() -> None:
    lim = replace(LIM, global_max_slots=1)
    ps, acts = fsm.plan_claim_result(pool(rec("s", STD, S.READY)), "s", True, fsm.PoolBudget(lim, 1.0, 0.0))
    assert acts == () and states(ps) == {"s": S.CLAIMED}

def test_claim_result_ignores_non_ready_slot() -> None:
    start = pool(rec("s", STD, S.WARMING))
    assert fsm.plan_claim_result(start, "s", True, fsm.PoolBudget(LIM, 1.0, 0.0)) == (start, ())

# ---- plan_turn_done ----

def test_turn_done_zero_canon_disposes_and_replenishes_while_ttl_alive() -> None:
    start = pool(rec("z", ZC, S.CLAIMED), demand=((ZC, 100.0),))
    ps, acts = fsm.plan_turn_done(start, "z", LIM, 150.0, 0.0)
    assert kinds(acts) == [A.KILL, A.CLEANUP_HOME, A.REPLENISH]
    assert states(ps)["z"] is S.DISPOSING

def test_turn_done_zero_canon_no_replenish_after_ttl() -> None:
    start = pool(rec("z", ZC, S.CLAIMED), demand=((ZC, 100.0),))
    ps, acts = fsm.plan_turn_done(start, "z", LIM, 100.0 + LIM.sliding_ttl_s + 1, 0.0)
    assert kinds(acts) == [A.KILL, A.CLEANUP_HOME] and len(ps.slots) == 1

def test_turn_done_standard_with_session_returns_ready() -> None:
    start = pool(rec("s", STD, S.CLAIMED, session_key="k"), demand=((STD, 1.0),))
    ps, acts = fsm.plan_turn_done(start, "s", LIM, 2.0, 0.0)
    assert acts == () and ps.slots[0].state is S.READY and ps.slots[0].session_key == "k"

def test_turn_done_standard_stateless_is_disposed_not_reused() -> None:
    start = pool(rec("s", STD, S.CLAIMED), demand=((STD, 1.0),))
    ps, acts = fsm.plan_turn_done(start, "s", LIM, 2.0, 0.0)
    assert A.KILL in kinds(acts) and states(ps)["s"] is S.DISPOSING

# ---- plan_reap_tick / plan_drain ----

def test_reap_closes_expired_ready_and_hung_warming_only() -> None:
    start = pool(
        rec("old", STD, S.READY), rec("fresh", OTHER, S.READY),
        SlotRecord("hung", ZC, S.WARMING, 1, 0.0), SlotRecord("boot", replace(ZC, model="x"), S.WARMING, 1, 390.0),
        rec("busy", replace(STD, model="b"), S.CLAIMED),
        demand=((STD, 0.0), (OTHER, 350.0), (ZC, 390.0)),
    )
    ps, acts = fsm.plan_reap_tick(start, LIM, 400.0)
    assert {a.slot_id for a in acts if a.kind is A.KILL} == {"old", "hung"}
    assert {a.slot_id for a in acts if a.kind is A.CLEANUP_HOME} == {"old", "hung"}
    got = states(ps)
    assert got["fresh"] is S.READY and got["boot"] is S.WARMING and got["busy"] is S.CLAIMED
    assert STD not in dict(ps.profile_last_demand) and OTHER in dict(ps.profile_last_demand)

def test_reap_sweeps_disposing_without_new_actions() -> None:
    ps, acts = fsm.plan_reap_tick(pool(rec("d", STD, S.DISPOSING), rec("c", STD, S.CLOSED)), LIM, 1.0)
    assert acts == () and ps.slots == ()

def test_drain_kills_all_live_slots_and_sets_flag() -> None:
    start = pool(rec("a", STD, S.READY), rec("b", ZC, S.CLAIMED), rec("c", OTHER, S.WARMING),
                 rec("d", STD, S.DISPOSING))
    ps, acts = fsm.plan_drain(start)
    assert ps.draining and {a.slot_id for a in acts} == {"a", "b", "c"}
    assert sorted(kinds(acts), key=lambda k: k.value) == [A.CLEANUP_HOME] * 3 + [A.KILL] * 3
    assert set(states(ps).values()) == {S.DISPOSING}

def test_plan_functions_do_not_mutate_input() -> None:
    start = pool(rec("a", STD, S.READY), demand=((STD, 1.0),))
    snapshot = (start.slots, start.profile_last_demand, start.epoch_seq, start.draining)
    for _ in (fsm.plan_drain(start), fsm.plan_reap_tick(start, LIM, 1e6),
              fsm.plan_demand(start, OTHER, LIM, 2.0, 0.0)):
        assert (start.slots, start.profile_last_demand, start.epoch_seq, start.draining) == snapshot

# ---- compute_env_digest ----

def test_env_digest_deterministic_and_order_independent() -> None:
    a = fsm.compute_env_digest({"A": "1", "B": "2"}, ["B", "A"])
    assert a == fsm.compute_env_digest({"B": "2", "A": "1"}, ("A", "B", "A"))
    assert len(a) == 64 and a != fsm.compute_env_digest({"A": "1", "B": "3"}, ["A", "B"])

def test_env_digest_ignores_non_allowlisted_keys() -> None:
    base = fsm.compute_env_digest({"A": "1"}, ["A"])
    assert base == fsm.compute_env_digest({"A": "1", "SECRET": "x"}, ["A"])
    assert fsm.compute_env_digest({"A": "1"}, []) == fsm.compute_env_digest({}, ["A"])

def test_env_digest_does_not_leak_raw_values_and_resists_concat_collisions() -> None:
    secret = "sk-very-secret-token"
    assert secret not in fsm.compute_env_digest({"KEY": secret}, ["KEY"])
    assert fsm.compute_env_digest({"A": "b=1;c", "D": ""}, ["A", "D"]) != \
        fsm.compute_env_digest({"A": "b", "D": "1;c"}, ["A", "D"])

# ---- VER-008: чистота модуля ----

def test_module_is_io_and_clock_free() -> None:
    tree = ast.parse(Path(fsm.__file__).read_text(encoding="utf-8"))
    allowed = {"__future__", "hashlib", "math", "collections", "dataclasses", "enum", "typing"}
    mods = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    mods |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert mods <= allowed
