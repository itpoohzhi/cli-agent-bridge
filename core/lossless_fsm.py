"""Pure LosslessSessionFSM: terminal invariants, epoch fencing, sequence checks (BND-001: zero I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


class SessionState(str, Enum):
    """Finite states for sequential lossless frame delivery."""

    INIT = "INIT"
    DELIVERING = "DELIVERING"
    AWAITING_ACK = "AWAITING_ACK"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EPOCH_MISMATCH = "EPOCH_MISMATCH"
    FAILED = "FAILED"


TERMINAL_STATES: Final[frozenset[SessionState]] = frozenset(
    {
        SessionState.COMPLETED,
        SessionState.REJECTED,
        SessionState.CANCELLED,
        SessionState.EPOCH_MISMATCH,
        SessionState.FAILED,
    }
)


class EventKind(str, Enum):
    """Input events driving LosslessSessionFSM."""

    SEND_CHUNK = "SEND_CHUNK"
    ACK_OK = "ACK_OK"
    ACK_FINAL = "ACK_FINAL"
    CANCEL = "CANCEL"
    EPOCH_MISMATCH = "EPOCH_MISMATCH"
    OVERFLOW = "OVERFLOW"
    IO_ERROR = "IO_ERROR"


class EffectKind(str, Enum):
    """Pure side-effect descriptors emitted by FSM transitions."""

    WRITE_FRAME = "WRITE_FRAME"
    COMMIT_ANCHOR = "COMMIT_ANCHOR"
    EMIT_LOSS_RECEIPT = "EMIT_LOSS_RECEIPT"
    TEARDOWN_PGID = "TEARDOWN_PGID"


@dataclass(frozen=True)
class SessionEvent:
    """Single immutable event for LosslessSessionFSM."""

    kind: EventKind
    epoch: int
    seq: int = 0
    is_synthetic: bool = False
    reason: str = ""


@dataclass(frozen=True)
class SessionEffect:
    """Immutable effect requested by a pure transition."""

    kind: EffectKind
    http_status: int = 0
    seq: int = 0
    reason: str = ""


@dataclass(frozen=True)
class SessionSnapshot:
    """Immutable state snapshot of one chunked delivery session."""

    state: SessionState
    active_epoch: int
    expected_seq: int = 0
    acked_chunks: int = 0
    max_chunks: int = 16
    anchor_committed: bool = False
    terminal_reason: str = ""

    @property
    def is_terminal(self) -> bool:
        """Return True if the session is in an absorbing terminal state."""
        return self.state in TERMINAL_STATES


def _terminate(
    snap: SessionSnapshot,
    target: SessionState,
    reason: str,
    effects: tuple[SessionEffect, ...],
) -> tuple[SessionSnapshot, tuple[SessionEffect, ...]]:
    return (
        SessionSnapshot(
            state=target,
            active_epoch=snap.active_epoch,
            expected_seq=snap.expected_seq,
            acked_chunks=snap.acked_chunks,
            max_chunks=snap.max_chunks,
            anchor_committed=snap.anchor_committed,
            terminal_reason=reason,
        ),
        effects,
    )


def _handle_send_chunk(
    snap: SessionSnapshot, event: SessionEvent
) -> tuple[SessionSnapshot, tuple[SessionEffect, ...]]:
    if snap.state not in (SessionState.INIT, SessionState.DELIVERING):
        return _terminate(
            snap,
            SessionState.FAILED,
            "send_in_invalid_state",
            (
                SessionEffect(EffectKind.TEARDOWN_PGID, reason="send_in_invalid_state"),
                SessionEffect(EffectKind.EMIT_LOSS_RECEIPT, http_status=400, seq=event.seq, reason="send_in_invalid_state"),
            ),
        )
    if event.seq != snap.expected_seq:
        return _terminate(
            snap,
            SessionState.FAILED,
            "seq_gap",
            (
                SessionEffect(EffectKind.TEARDOWN_PGID, reason="seq_gap"),
                SessionEffect(EffectKind.EMIT_LOSS_RECEIPT, http_status=400, seq=event.seq, reason="seq_gap"),
            ),
        )
    if event.seq >= snap.max_chunks:
        return _terminate(
            snap,
            SessionState.REJECTED,
            "chunk_limit_exceeded",
            (
                SessionEffect(EffectKind.TEARDOWN_PGID, reason="chunk_limit_exceeded"),
                SessionEffect(EffectKind.EMIT_LOSS_RECEIPT, http_status=413, seq=event.seq, reason="chunk_limit_exceeded"),
            ),
        )
    next_snap = SessionSnapshot(
        state=SessionState.AWAITING_ACK,
        active_epoch=snap.active_epoch,
        expected_seq=snap.expected_seq,
        acked_chunks=snap.acked_chunks,
        max_chunks=snap.max_chunks,
        anchor_committed=False,
    )
    return next_snap, (SessionEffect(EffectKind.WRITE_FRAME, seq=event.seq),)


def _handle_ack(
    snap: SessionSnapshot, event: SessionEvent
) -> tuple[SessionSnapshot, tuple[SessionEffect, ...]]:
    if snap.state != SessionState.AWAITING_ACK or event.seq != snap.expected_seq:
        return _terminate(
            snap,
            SessionState.FAILED,
            "unexpected_ack",
            (
                SessionEffect(EffectKind.TEARDOWN_PGID, reason="unexpected_ack"),
                SessionEffect(EffectKind.EMIT_LOSS_RECEIPT, http_status=400, seq=event.seq, reason="unexpected_ack"),
            ),
        )
    if event.kind is EventKind.ACK_OK:
        next_snap = SessionSnapshot(
            state=SessionState.DELIVERING,
            active_epoch=snap.active_epoch,
            expected_seq=snap.expected_seq + 1,
            acked_chunks=snap.acked_chunks + 1,
            max_chunks=snap.max_chunks,
            anchor_committed=False,
        )
        return next_snap, ()
    # ACK_FINAL: commit continuity anchor only when non-synthetic final turn completes
    commit = not event.is_synthetic
    next_snap = SessionSnapshot(
        state=SessionState.COMPLETED,
        active_epoch=snap.active_epoch,
        expected_seq=snap.expected_seq + 1,
        acked_chunks=snap.acked_chunks + 1,
        max_chunks=snap.max_chunks,
        anchor_committed=commit,
        terminal_reason="completed",
    )
    effects = (SessionEffect(EffectKind.COMMIT_ANCHOR, seq=event.seq),) if commit else ()
    return next_snap, effects


def step(
    snap: SessionSnapshot, event: SessionEvent
) -> tuple[SessionSnapshot, tuple[SessionEffect, ...]]:
    """Pure deterministic state transition (zero side effects, zero escapes from terminal states)."""
    if snap.is_terminal:
        return snap, ()
    if event.kind is EventKind.EPOCH_MISMATCH or event.epoch != snap.active_epoch:
        return _terminate(
            snap,
            SessionState.EPOCH_MISMATCH,
            event.reason or "epoch_mismatch",
            (
                SessionEffect(EffectKind.TEARDOWN_PGID, reason="epoch_mismatch"),
                SessionEffect(EffectKind.EMIT_LOSS_RECEIPT, http_status=409, seq=event.seq, reason="epoch_mismatch"),
            ),
        )
    if event.kind is EventKind.OVERFLOW:
        return _terminate(
            snap,
            SessionState.REJECTED,
            event.reason or "chunk_limit_exceeded",
            (SessionEffect(EffectKind.EMIT_LOSS_RECEIPT, http_status=413, seq=event.seq, reason=event.reason or "chunk_limit_exceeded"),),
        )
    if event.kind is EventKind.CANCEL:
        return _terminate(
            snap,
            SessionState.CANCELLED,
            event.reason or "client_cancelled",
            (
                SessionEffect(EffectKind.TEARDOWN_PGID, reason=event.reason or "client_cancelled"),
                SessionEffect(EffectKind.EMIT_LOSS_RECEIPT, http_status=499, seq=event.seq, reason=event.reason or "client_cancelled"),
            ),
        )
    if event.kind is EventKind.IO_ERROR:
        return _terminate(
            snap,
            SessionState.FAILED,
            event.reason or "io_error",
            (
                SessionEffect(EffectKind.TEARDOWN_PGID, reason=event.reason or "io_error"),
                SessionEffect(EffectKind.EMIT_LOSS_RECEIPT, http_status=400, seq=event.seq, reason=event.reason or "io_error"),
            ),
        )
    if event.kind is EventKind.SEND_CHUNK:
        return _handle_send_chunk(snap, event)
    return _handle_ack(snap, event)
