"""Exhaustive L1 Zero-I/O matrix tests for AGY orphan_coordinator.py (W05, VER-002)."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

from core.pgid_cleanup_policy import CleanupState

_MOD_PATH = Path(__file__).resolve().parents[1] / "bridges/agy-bridge/agy_runtime/orphan_coordinator.py"
_SPEC = importlib.util.spec_from_file_location("agy_orphan_coordinator", _MOD_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["agy_orphan_coordinator"] = _MOD
_SPEC.loader.exec_module(_MOD)

CoordinatorContext = _MOD.CoordinatorContext
CoordinatorDecision = _MOD.CoordinatorDecision
CoordinatorEvent = _MOD.CoordinatorEvent
OrphanPhase = _MOD.OrphanPhase
OrphanState = _MOD.OrphanState
decide_agy_action = _MOD.decide_agy_action


def _orphan(
    *,
    tools: bool = True,
    active: int = 1,
    orphan_max: int = 5,
    ttfc: bool = True,
    phase: OrphanPhase = OrphanPhase.NONE,
    fast_enabled: bool = True,
) -> OrphanState:
    return OrphanState(
        tools_active=tools,
        active_orphans=active,
        orphan_max=orphan_max,
        ttfc_seen=ttfc,
        phase=phase,
        fast_client_gone_enabled=fast_enabled,
    )


def test_stale_epoch_always_noop_stale() -> None:
    for ev in CoordinatorEvent:
        for st in CleanupState:
            ctx = CoordinatorContext(ev, _orphan(), readers=0, dead_confirmed=True, cleanup_state=st, epoch_ok=False)
            assert decide_agy_action(ctx) is CoordinatorDecision.NOOP_STALE


def test_dead_confirmed_always_release_ok() -> None:
    for ev in CoordinatorEvent:
        ctx = CoordinatorContext(ev, _orphan(), readers=0, dead_confirmed=True, cleanup_state=CleanupState.KILL_SENT, epoch_ok=True)
        assert decide_agy_action(ctx) is CoordinatorDecision.RELEASE_OK


def test_readers_multi_and_transition_2_to_1_to_0() -> None:
    # readers 2 -> disconnect -> still 1 reader -> KEEP (never orphan, never teardown)
    ctx_two = CoordinatorContext(CoordinatorEvent.READER_DISCONNECT, _orphan(tools=False), readers=2, dead_confirmed=False, cleanup_state=CleanupState.LIVE, epoch_ok=True)
    assert decide_agy_action(ctx_two) is CoordinatorDecision.KEEP

    ctx_one = CoordinatorContext(CoordinatorEvent.READER_DISCONNECT, _orphan(tools=False), readers=1, dead_confirmed=False, cleanup_state=CleanupState.LIVE, epoch_ok=True)
    assert decide_agy_action(ctx_one) is CoordinatorDecision.KEEP

    # readers 1 -> 0 with eligible tools post-TTFC -> ORPHAN_KEEP
    ctx_zero_elig = CoordinatorContext(CoordinatorEvent.READER_DISCONNECT, _orphan(tools=True, ttfc=True, active=2, orphan_max=5), readers=0, dead_confirmed=False, cleanup_state=CleanupState.LIVE, epoch_ok=True)
    assert decide_agy_action(ctx_zero_elig) is CoordinatorDecision.ORPHAN_KEEP

    # readers 1 -> 0 with orphan_max reached -> TEARDOWN_REQUEST
    ctx_zero_cap = CoordinatorContext(CoordinatorEvent.READER_DISCONNECT, _orphan(tools=True, ttfc=True, active=5, orphan_max=5), readers=0, dead_confirmed=False, cleanup_state=CleanupState.LIVE, epoch_ok=True)
    assert decide_agy_action(ctx_zero_cap) is CoordinatorDecision.TEARDOWN_REQUEST

    # readers 1 -> 0 pre-TTFC or tools=0 -> TEARDOWN_REQUEST
    ctx_no_ttfc = CoordinatorContext(CoordinatorEvent.READER_DISCONNECT, _orphan(tools=True, ttfc=False), readers=0, dead_confirmed=False, cleanup_state=CleanupState.LIVE, epoch_ok=True)
    assert decide_agy_action(ctx_no_ttfc) is CoordinatorDecision.TEARDOWN_REQUEST


def test_orphan_active_protected_and_expired_teardown() -> None:
    for ph in (OrphanPhase.ORPHAN_CANDIDATE, OrphanPhase.ORPHAN_ACTIVE):
        ctx = CoordinatorContext(CoordinatorEvent.HYGIENE_TICK, _orphan(tools=False, phase=ph), readers=0, dead_confirmed=False, cleanup_state=CleanupState.LIVE, epoch_ok=True)
        assert decide_agy_action(ctx) is CoordinatorDecision.ORPHAN_KEEP

    ctx_exp = CoordinatorContext(CoordinatorEvent.HYGIENE_TICK, _orphan(phase=OrphanPhase.ORPHAN_EXPIRED), readers=0, dead_confirmed=False, cleanup_state=CleanupState.LIVE, epoch_ok=True)
    assert decide_agy_action(ctx_exp) is CoordinatorDecision.TEARDOWN_REQUEST


def test_reader_attach_rejected_409_during_cancelling_or_quarantined() -> None:
    for st in (CleanupState.TERM_SENT, CleanupState.KILL_SENT, CleanupState.QUARANTINED):
        ctx_att = CoordinatorContext(CoordinatorEvent.READER_ATTACH, _orphan(), readers=1, dead_confirmed=False, cleanup_state=st, epoch_ok=True)
        assert decide_agy_action(ctx_att) is CoordinatorDecision.REJECT_409_CANCELLING
        ctx_tick = CoordinatorContext(CoordinatorEvent.HYGIENE_TICK, _orphan(), readers=0, dead_confirmed=False, cleanup_state=st, epoch_ok=True)
        assert decide_agy_action(ctx_tick) is CoordinatorDecision.HOLD_QUARANTINE

    ctx_live = CoordinatorContext(CoordinatorEvent.READER_ATTACH, _orphan(phase=OrphanPhase.ORPHAN_ACTIVE), readers=1, dead_confirmed=False, cleanup_state=CleanupState.LIVE, epoch_ok=True)
    assert decide_agy_action(ctx_live) is CoordinatorDecision.KEEP


def test_all_cleanup_states_covered_and_zero_io() -> None:
    # Contract test F-020: every CleanupState enum value produces a valid CoordinatorDecision
    for st in CleanupState:
        for ev in CoordinatorEvent:
            res = decide_agy_action(CoordinatorContext(ev, _orphan(), readers=0, dead_confirmed=False, cleanup_state=st, epoch_ok=True))
            assert isinstance(res, CoordinatorDecision)

    tree = ast.parse(_MOD_PATH.read_text(encoding="utf-8"))
    forbidden = {"os", "subprocess", "socket", "time", "pathlib", "ctypes"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden
