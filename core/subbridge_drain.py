"""Pure Zero-I/O sub-bridge drain observability FSM and event formatters (REQ-001 Wave 1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DrainCompleted:
    """Normalized drain outcome supplied by the caller."""

    signal: int
    active_before: int
    remaining: int
    forced_kill: bool
    elapsed_ms: int
    shutdown_ok: bool
    epoch: int = 1


@dataclass(frozen=True, slots=True)
class DrainObsState:
    """Immutable observability state: epoch, phase and exactly-once completion flag."""

    epoch: int = 1
    phase: str = "ready"
    completed_emitted: bool = False


@dataclass(frozen=True, slots=True)
class DrainObsEvent:
    """Incoming drain lifecycle event."""

    kind: str
    signal: int = 0
    outcome: DrainCompleted | None = None


@dataclass(frozen=True, slots=True)
class DrainObsEffect:
    """Emission instruction for the caller; `line` is pre-formatted."""

    kind: str
    line: str = ""


def format_drain_completed(outcome: DrainCompleted) -> str:
    """Fixed-shape drain_completed line with clamped non-negative fields."""
    return (
        f"drain_completed epoch={max(1, int(outcome.epoch))} signal={int(outcome.signal)}"
        f" active_before={max(0, int(outcome.active_before))} remaining={max(0, int(outcome.remaining))}"
        f" forced_kill={int(bool(outcome.forced_kill))} elapsed_ms={max(0, int(outcome.elapsed_ms))}"
        f" shutdown_ok={int(bool(outcome.shutdown_ok))}"
    )


def format_drain_reentry(signal: int, epoch: int = 1) -> str:
    """Fixed-shape drain_reentry line; epoch is clamped to >= 1."""
    return f"drain_reentry epoch={max(1, int(epoch))} signal={int(signal)}"


def transition(
    state: DrainObsState, event: DrainObsEvent
) -> tuple[DrainObsState, tuple[DrainObsEffect, ...]]:
    """Pure deterministic step; drain_completed is emitted exactly once per epoch."""
    if event.kind == "start":
        if state.phase == "ready":
            new_state = DrainObsState(
                epoch=state.epoch, phase="draining", completed_emitted=False
            )
            return new_state, (DrainObsEffect("noop"),)
        return state, (
            DrainObsEffect(
                "emit_reentry", format_drain_reentry(event.signal, state.epoch)
            ),
        )
    if event.kind == "reentry":
        return state, (
            DrainObsEffect(
                "emit_reentry", format_drain_reentry(event.signal, state.epoch)
            ),
        )
    if event.kind == "complete":
        if state.completed_emitted or event.outcome is None:
            return state, (DrainObsEffect("noop"),)
        new_state = DrainObsState(
            epoch=state.epoch, phase="stopped", completed_emitted=True
        )
        return new_state, (
            DrainObsEffect("emit_completed", format_drain_completed(event.outcome)),
        )
    if event.kind == "reset_epoch":
        new_state = DrainObsState(
            epoch=state.epoch + 1, phase="ready", completed_emitted=False
        )
        return new_state, (DrainObsEffect("noop"),)
    raise ValueError(f"unknown drain event kind: {event.kind}")
