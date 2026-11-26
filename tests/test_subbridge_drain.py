"""Wave 1 contract tests for `core.subbridge_drain` (pure Zero-I/O drain FSM, REQ-001)."""

from __future__ import annotations

import ast
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.subbridge_drain import (  # noqa: E402
    DrainCompleted,
    DrainObsEffect,
    DrainObsEvent,
    DrainObsState,
    format_drain_completed,
    format_drain_reentry,
    transition,
)

MODULE_PATH = ROOT / "core" / "subbridge_drain.py"
FORBIDDEN_IMPORTS = frozenset(
    {"os", "time", "logging", "threading", "subprocess", "server"}
)


def _outcome(**kw: object) -> DrainCompleted:
    base: dict[str, object] = {
        "signal": 15,
        "active_before": 3,
        "remaining": 1,
        "forced_kill": True,
        "elapsed_ms": 250,
        "shutdown_ok": False,
        "epoch": 2,
    }
    base.update(kw)
    return DrainCompleted(**base)  # type: ignore[arg-type]


# --- structural Zero-I/O / limits gate -------------------------------------------------


def test_module_zero_io_and_size_limits() -> None:
    src = MODULE_PATH.read_text(encoding="utf-8")
    assert len(src.splitlines()) <= 150
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in FORBIDDEN_IMPORTS
                assert alias.name.split(".")[0] not in FORBIDDEN_IMPORTS
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert mod not in FORBIDDEN_IMPORTS
            assert mod.split(".")[0] not in FORBIDDEN_IMPORTS
        elif isinstance(node, ast.FunctionDef):
            assert node.end_lineno is not None
            assert node.end_lineno - node.lineno + 1 <= 40, node.name
            n_args = (
                len(node.args.args)
                + len(node.args.posonlyargs)
                + len(node.args.kwonlyargs)
            )
            assert n_args <= 5, node.name


def test_all_dataclasses_frozen_and_slotted() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    assert {c.name for c in classes} == {
        "DrainCompleted",
        "DrainObsState",
        "DrainObsEvent",
        "DrainObsEffect",
    }
    for cls in classes:
        for dec in cls.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Name)
                and dec.func.id == "dataclass"
            ):
                kw = {k.arg: k.value for k in dec.keywords}
                assert (
                    isinstance(kw.get("frozen"), ast.Constant)
                    and kw["frozen"].value is True
                ), cls.name
                assert (
                    isinstance(kw.get("slots"), ast.Constant)
                    and kw["slots"].value is True
                ), cls.name


# --- formatters --------------------------------------------------------------------------


def test_format_drain_completed_exact_shape() -> None:
    assert format_drain_completed(_outcome()) == (
        "drain_completed epoch=2 signal=15 active_before=3 remaining=1 forced_kill=1 elapsed_ms=250 shutdown_ok=0"
    )


def test_format_drain_completed_defaults_and_clamps() -> None:
    outcome = DrainCompleted(
        signal=2,
        active_before=-2,
        remaining=-1,
        forced_kill=False,
        elapsed_ms=-10,
        shutdown_ok=True,
    )
    assert outcome.epoch == 1
    assert format_drain_completed(outcome) == (
        "drain_completed epoch=1 signal=2 active_before=0 remaining=0 forced_kill=0 elapsed_ms=0 shutdown_ok=1"
    )
    assert "epoch=1" in format_drain_completed(_outcome(epoch=0))
    assert "epoch=1" in format_drain_completed(_outcome(epoch=-5))


def test_format_drain_reentry_exact_shape_and_epoch_clamp() -> None:
    assert format_drain_reentry(15) == "drain_reentry epoch=1 signal=15"
    assert format_drain_reentry(2, 3) == "drain_reentry epoch=3 signal=2"
    assert format_drain_reentry(15, 0) == "drain_reentry epoch=1 signal=15"
    assert format_drain_reentry(15, -7) == "drain_reentry epoch=1 signal=15"
    assert format_drain_reentry(-1) == "drain_reentry epoch=1 signal=-1"


# --- transition: exhaustive State x Event -------------------------------------------------


def test_start_from_ready_enters_draining() -> None:
    state = DrainObsState(epoch=4, phase="ready", completed_emitted=False)
    new_state, effects = transition(state, DrainObsEvent("start", signal=15))
    assert new_state == DrainObsState(
        epoch=4, phase="draining", completed_emitted=False
    )
    assert effects == (DrainObsEffect("noop"),)
    assert effects[0].line == ""


@pytest.mark.parametrize("phase", ["draining", "stopped"])
def test_start_reentry_when_not_ready(phase: str) -> None:
    state = DrainObsState(epoch=3, phase=phase, completed_emitted=(phase == "stopped"))
    new_state, effects = transition(state, DrainObsEvent("start", signal=2))
    assert new_state is state
    assert effects == (
        DrainObsEffect("emit_reentry", "drain_reentry epoch=3 signal=2"),
    )


@pytest.mark.parametrize("phase", ["ready", "draining", "stopped"])
def test_reentry_event_always_emits_and_keeps_state(phase: str) -> None:
    state = DrainObsState(epoch=2, phase=phase, completed_emitted=(phase == "stopped"))
    new_state, effects = transition(state, DrainObsEvent("reentry", signal=15))
    assert new_state is state
    assert effects == (
        DrainObsEffect("emit_reentry", "drain_reentry epoch=2 signal=15"),
    )


def test_complete_emits_exactly_once_per_epoch() -> None:
    state = DrainObsState(epoch=1, phase="draining")
    outcome = _outcome(epoch=1)
    new_state, effects = transition(
        state, DrainObsEvent("complete", signal=15, outcome=outcome)
    )
    assert new_state == DrainObsState(epoch=1, phase="stopped", completed_emitted=True)
    assert effects == (
        DrainObsEffect("emit_completed", format_drain_completed(outcome)),
    )
    again_state, again_effects = transition(
        new_state, DrainObsEvent("complete", signal=15, outcome=outcome)
    )
    assert again_state is new_state
    assert again_effects == (DrainObsEffect("noop"),)
    third_state, third_effects = transition(
        again_state, DrainObsEvent("complete", signal=2, outcome=_outcome())
    )
    assert third_state is new_state
    assert third_effects == (DrainObsEffect("noop"),)


def test_complete_without_outcome_is_noop_and_does_not_latch() -> None:
    state = DrainObsState(epoch=1, phase="draining")
    new_state, effects = transition(
        state, DrainObsEvent("complete", signal=15, outcome=None)
    )
    assert new_state is state
    assert effects == (DrainObsEffect("noop"),)
    assert new_state.completed_emitted is False
    final_state, final_effects = transition(
        new_state, DrainObsEvent("complete", signal=15, outcome=_outcome(epoch=1))
    )
    assert final_state.phase == "stopped"
    assert final_effects[0].kind == "emit_completed"


def test_complete_from_ready_still_emits_once() -> None:
    state = DrainObsState(epoch=1, phase="ready")
    new_state, effects = transition(
        state, DrainObsEvent("complete", outcome=_outcome(epoch=1))
    )
    assert new_state == DrainObsState(epoch=1, phase="stopped", completed_emitted=True)
    assert effects[0].kind == "emit_completed"


@pytest.mark.parametrize("phase", ["ready", "draining", "stopped"])
def test_reset_epoch_advances_and_rearms(phase: str) -> None:
    state = DrainObsState(epoch=7, phase=phase, completed_emitted=(phase == "stopped"))
    new_state, effects = transition(state, DrainObsEvent("reset_epoch"))
    assert new_state == DrainObsState(epoch=8, phase="ready", completed_emitted=False)
    assert effects == (DrainObsEffect("noop"),)


def test_full_lifecycle_two_epochs_exactly_once_each() -> None:
    state = DrainObsState()
    state, effects = transition(state, DrainObsEvent("start", signal=15))
    assert state.phase == "draining" and effects[0].kind == "noop"
    state, effects = transition(
        state, DrainObsEvent("complete", outcome=_outcome(epoch=1))
    )
    assert effects[0].kind == "emit_completed" and state.epoch == 1
    state, effects = transition(
        state, DrainObsEvent("complete", outcome=_outcome(epoch=1))
    )
    assert effects[0].kind == "noop"
    state, effects = transition(state, DrainObsEvent("start", signal=15))
    assert effects[0].kind == "emit_reentry"
    state, effects = transition(state, DrainObsEvent("reset_epoch"))
    assert state == DrainObsState(epoch=2, phase="ready", completed_emitted=False)
    state, effects = transition(state, DrainObsEvent("start", signal=2))
    assert state.phase == "draining" and state.epoch == 2
    state, effects = transition(
        state, DrainObsEvent("complete", outcome=_outcome(epoch=2))
    )
    assert effects[0].kind == "emit_completed"
    assert "epoch=2" in effects[0].line
    state, effects = transition(
        state, DrainObsEvent("complete", outcome=_outcome(epoch=2))
    )
    assert effects[0].kind == "noop"


def test_state_epoch_preserved_even_if_outcome_epoch_differs() -> None:
    state = DrainObsState(epoch=5, phase="draining")
    new_state, effects = transition(
        state, DrainObsEvent("complete", outcome=_outcome(epoch=2))
    )
    assert new_state.epoch == 5
    assert effects[0].line.startswith("drain_completed epoch=2 ")


@pytest.mark.parametrize("kind", ["bogus", "", "START", "completed", "reset", "drain"])
def test_unknown_kind_raises(kind: str) -> None:
    with pytest.raises(ValueError, match=f"unknown drain event kind: {kind}"):
        transition(DrainObsState(), DrainObsEvent(kind))


def test_transition_deterministic_and_records_frozen() -> None:
    state = DrainObsState(epoch=2, phase="draining")
    event = DrainObsEvent("complete", outcome=_outcome(epoch=2))
    assert transition(state, event) == transition(state, event)
    assert state == DrainObsState(epoch=2, phase="draining")
    with pytest.raises(FrozenInstanceError):
        state.phase = "x"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        event.kind = "x"  # type: ignore[misc]
    outcome = _outcome()
    with pytest.raises(FrozenInstanceError):
        outcome.signal = 9  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        DrainObsEffect("noop").line = "x"  # type: ignore[misc]
