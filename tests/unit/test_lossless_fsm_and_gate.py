"""Deterministic L1 unit tests for core/lossless_fsm.py and core/lossless_gate.py."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.lossless_contracts import DEFAULT_SAFE_FRAME_BYTES, LosslessLimits
from core.lossless_fsm import (
    TERMINAL_STATES,
    EffectKind,
    EventKind,
    SessionEvent,
    SessionSnapshot,
    SessionState,
    step,
)
from core.lossless_gate import GateAction, evaluate_delivery_gate

REPO_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IO_IMPORTS = frozenset({"asyncio", "subprocess", "socket", "urllib", "http", "pathlib"})


def test_bnd001_zero_io_imports_in_fsm_and_gate() -> None:
    for rel in ("core/lossless_fsm.py", "core/lossless_gate.py"):
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
        assert not (found & FORBIDDEN_IO_IMPORTS), f"Forbidden I/O in {rel}: {found & FORBIDDEN_IO_IMPORTS}"


@pytest.mark.parametrize("terminal", sorted(TERMINAL_STATES, key=lambda s: s.value))
@pytest.mark.parametrize("kind", list(EventKind))
def test_terminal_states_have_zero_escapes(terminal: SessionState, kind: EventKind) -> None:
    snap = SessionSnapshot(state=terminal, active_epoch=3, expected_seq=1, acked_chunks=1)
    nxt, effects = step(snap, SessionEvent(kind=kind, epoch=3, seq=1))
    assert nxt == snap
    assert effects == ()


def test_happy_path_multi_chunk_commits_anchor_only_on_final_non_synthetic_ack() -> None:
    snap = SessionSnapshot(state=SessionState.INIT, active_epoch=5, max_chunks=4)
    snap, eff = step(snap, SessionEvent(EventKind.SEND_CHUNK, epoch=5, seq=0, is_synthetic=True))
    assert snap.state is SessionState.AWAITING_ACK
    assert [e.kind for e in eff] == [EffectKind.WRITE_FRAME]

    snap, eff = step(snap, SessionEvent(EventKind.ACK_OK, epoch=5, seq=0, is_synthetic=True))
    assert snap.state is SessionState.DELIVERING
    assert snap.expected_seq == 1
    assert snap.anchor_committed is False
    assert eff == ()

    snap, eff = step(snap, SessionEvent(EventKind.SEND_CHUNK, epoch=5, seq=1, is_synthetic=False))
    assert snap.state is SessionState.AWAITING_ACK
    assert [e.kind for e in eff] == [EffectKind.WRITE_FRAME]

    snap, eff = step(snap, SessionEvent(EventKind.ACK_FINAL, epoch=5, seq=1, is_synthetic=False))
    assert snap.state is SessionState.COMPLETED
    assert snap.anchor_committed is True
    assert snap.acked_chunks == 2
    assert [e.kind for e in eff] == [EffectKind.COMMIT_ANCHOR]


def test_epoch_mismatch_seq_gap_cancel_and_overflow_are_fail_closed() -> None:
    base = SessionSnapshot(state=SessionState.INIT, active_epoch=7, max_chunks=2)

    # Stale epoch -> EPOCH_MISMATCH + PGID teardown
    s_ep, eff_ep = step(base, SessionEvent(EventKind.SEND_CHUNK, epoch=6, seq=0))
    assert s_ep.state is SessionState.EPOCH_MISMATCH
    assert EffectKind.TEARDOWN_PGID in {e.kind for e in eff_ep}

    # Sequence gap -> FAILED + PGID teardown
    s_gap, eff_gap = step(base, SessionEvent(EventKind.SEND_CHUNK, epoch=7, seq=2))
    assert s_gap.state is SessionState.FAILED
    assert s_gap.terminal_reason == "seq_gap"
    assert EffectKind.TEARDOWN_PGID in {e.kind for e in eff_gap}

    # Cancel mid-session -> CANCELLED + PGID teardown
    mid, _ = step(base, SessionEvent(EventKind.SEND_CHUNK, epoch=7, seq=0, is_synthetic=True))
    s_can, eff_can = step(mid, SessionEvent(EventKind.CANCEL, epoch=7, seq=0))
    assert s_can.state is SessionState.CANCELLED
    assert EffectKind.TEARDOWN_PGID in {e.kind for e in eff_can}

    # Overflow -> REJECTED + HTTP 413 receipt
    s_ov, eff_ov = step(base, SessionEvent(EventKind.OVERFLOW, epoch=7, seq=0))
    assert s_ov.state is SessionState.REJECTED
    assert any(e.kind is EffectKind.EMIT_LOSS_RECEIPT and e.http_status == 413 for e in eff_ov)


def test_delivery_gate_legacy_single_chunked_and_reject_413() -> None:
    legacy = evaluate_delivery_gate("x" * 300_000, LosslessLimits(lossless_enabled=False))
    assert legacy.action is GateAction.LEGACY
    assert legacy.allow_silent_truncation is True

    enabled = LosslessLimits(lossless_enabled=True, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES, max_chunks=4)
    small = evaluate_delivery_gate("hello world", enabled)
    assert small.action is GateAction.DELIVER_SINGLE
    assert small.allow_silent_truncation is False

    medium = evaluate_delivery_gate("а" * 120_000, enabled)
    assert medium.action is GateAction.DELIVER_CHUNKED
    assert medium.estimated_frames >= 2
    assert medium.allow_silent_truncation is False

    huge = evaluate_delivery_gate("SECRET_PASS " + ("x" * (DEFAULT_SAFE_FRAME_BYTES * 5)), enabled)
    assert huge.action is GateAction.REJECT
    assert huge.http_status == 413
    assert huge.receipt is not None
    assert "SECRET_PASS" not in str(huge.receipt.to_wire_dict())
