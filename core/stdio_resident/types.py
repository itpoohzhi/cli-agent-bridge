"""Typed state and transition contracts for resident stdio slots."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class SlotState(Enum):
    """Lifecycle state of a resident process slot."""

    SPAWNING = auto()
    READY = auto()
    BUSY = auto()
    CANCELING = auto()
    DRAINING = auto()
    BROKEN = auto()
    CLOSED = auto()


class SlotEvent(Enum):
    """Input event accepted by the slot state machine."""

    InitOk = auto()
    Lease = auto()
    TurnTerminal = auto()
    CancelRequested = auto()
    CancelConfirmed = auto()
    CancelGraceExpired = auto()
    WriteError = auto()
    Eof = auto()
    Invalidate = auto()
    TtlExpired = auto()
    Drain = auto()
    Shutdown = auto()
    TeardownDone = auto()


class SlotEffect(Enum):
    """Effect requested by a slot state transition."""

    BindTurn = auto()
    SendTurn = auto()
    CommitTurn = auto()
    DiscardBuffer = auto()
    AdvanceGeneration = auto()
    ReturnToPool = auto()
    SendCancel = auto()
    StartCancelGrace = auto()
    Teardown = auto()
    ReportError = auto()
    Reject = auto()
    ReleaseSlot = auto()


def step_slot_fsm(
    state: SlotState,
    event: SlotEvent,
) -> tuple[SlotState, list[SlotEffect]]:
    """Return the next slot state and declarative effects for an event."""

    if state is SlotState.SPAWNING:
        if event is SlotEvent.InitOk:
            return SlotState.READY, []
        if event is SlotEvent.Lease:
            return SlotState.SPAWNING, [SlotEffect.Reject]
        if event in (SlotEvent.Drain, SlotEvent.Invalidate, SlotEvent.Shutdown):
            return SlotState.CLOSED, [SlotEffect.Teardown]
        if event in (SlotEvent.WriteError, SlotEvent.Eof, SlotEvent.TtlExpired):
            return SlotState.BROKEN, [SlotEffect.Teardown, SlotEffect.ReportError]
        return SlotState.SPAWNING, []

    if state is SlotState.READY:
        if event is SlotEvent.Lease:
            return SlotState.BUSY, [SlotEffect.BindTurn, SlotEffect.SendTurn]
        if event in (
            SlotEvent.Drain,
            SlotEvent.Invalidate,
            SlotEvent.TtlExpired,
            SlotEvent.Shutdown,
            SlotEvent.Eof,
        ):
            return SlotState.CLOSED, [SlotEffect.Teardown]
        if event is SlotEvent.WriteError:
            return SlotState.BROKEN, [SlotEffect.Teardown, SlotEffect.ReportError]
        return SlotState.READY, []

    if state is SlotState.BUSY:
        if event is SlotEvent.TurnTerminal:
            return SlotState.READY, [
                SlotEffect.CommitTurn,
                SlotEffect.AdvanceGeneration,
                SlotEffect.ReturnToPool,
            ]
        if event is SlotEvent.CancelRequested:
            return SlotState.CANCELING, [
                SlotEffect.SendCancel,
                SlotEffect.StartCancelGrace,
            ]
        if event in (SlotEvent.Drain, SlotEvent.Invalidate):
            return SlotState.DRAINING, []
        if event in (SlotEvent.WriteError, SlotEvent.Eof):
            return SlotState.BROKEN, [
                SlotEffect.DiscardBuffer,
                SlotEffect.Teardown,
                SlotEffect.ReportError,
            ]
        if event is SlotEvent.Shutdown:
            return SlotState.CLOSED, [
                SlotEffect.DiscardBuffer,
                SlotEffect.Teardown,
            ]
        if event is SlotEvent.Lease:
            return SlotState.BUSY, [SlotEffect.Reject]
        return SlotState.BUSY, []

    if state is SlotState.CANCELING:
        if event is SlotEvent.Lease:
            return SlotState.CANCELING, [SlotEffect.Reject]
        if event in (
            SlotEvent.CancelRequested,
            SlotEvent.InitOk,
            SlotEvent.TeardownDone,
        ):
            return SlotState.CANCELING, []
        if event in (SlotEvent.WriteError, SlotEvent.Eof):
            return SlotState.CLOSED, [
                SlotEffect.DiscardBuffer,
                SlotEffect.Teardown,
                SlotEffect.ReportError,
            ]
        if event in (
            SlotEvent.TurnTerminal,
            SlotEvent.CancelConfirmed,
            SlotEvent.CancelGraceExpired,
            SlotEvent.Drain,
            SlotEvent.Invalidate,
            SlotEvent.TtlExpired,
            SlotEvent.Shutdown,
        ):
            return SlotState.CLOSED, [
                SlotEffect.DiscardBuffer,
                SlotEffect.Teardown,
            ]

    if state is SlotState.DRAINING:
        if event is SlotEvent.TurnTerminal:
            return SlotState.CLOSED, [
                SlotEffect.CommitTurn,
                SlotEffect.AdvanceGeneration,
                SlotEffect.Teardown,
            ]
        if event in (SlotEvent.CancelRequested, SlotEvent.Shutdown):
            return SlotState.CLOSED, [
                SlotEffect.DiscardBuffer,
                SlotEffect.Teardown,
            ]
        if event in (SlotEvent.WriteError, SlotEvent.Eof):
            return SlotState.BROKEN, [
                SlotEffect.DiscardBuffer,
                SlotEffect.Teardown,
                SlotEffect.ReportError,
            ]
        if event is SlotEvent.Lease:
            return SlotState.DRAINING, [SlotEffect.Reject]
        return SlotState.DRAINING, []

    if state is SlotState.BROKEN:
        if event is SlotEvent.TeardownDone:
            return SlotState.CLOSED, [SlotEffect.ReleaseSlot]
        return SlotState.BROKEN, []

    if state is SlotState.CLOSED:
        if event is SlotEvent.TeardownDone:
            return SlotState.CLOSED, [SlotEffect.ReleaseSlot]
        return SlotState.CLOSED, []


@dataclass(frozen=True)
class SlotAffinityKey:
    """Stable affinity dimensions for selecting a resident slot."""

    owner_hash: str
    chat_key: str
    backend_id: str
    model: str
    effort: str
    cwd_norm: str


@dataclass(frozen=True)
class ExecutionFingerprint:
    """Digest of process arguments, environment, and normalized cwd."""

    digest: str


@dataclass
class StdioTurnState:
    """Mutable runtime state associated with one active turn."""

    turn_id: str
    generation: int
    started_at_mono: float
    last_activity_mono: float
    deadline_mono: float
    buffer: list[str] = field(default_factory=list)
    terminal_received: bool = False


@dataclass
class SlotAllocation:
    """Lease metadata returned when a slot is allocated."""

    slot_id: str
    generation: int
    affinity_key: SlotAffinityKey


@dataclass
class ResidentProcessInfo:
    """Observed resource and lifetime metadata for a resident process."""

    pid: int
    created_at_mono: float
    rss_bytes: int = 0
    turns_completed: int = 0
