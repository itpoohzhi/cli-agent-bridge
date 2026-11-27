"""Exhaustive L1 Zero-I/O tests for hub TurnMode & client-cancel policy (W10, VER-002)."""

from __future__ import annotations

import itertools

import pytest

from core.turn_mode_cancel_policy import (
    INTERNAL_TURN_MODE_HEADER,
    CancelDecision,
    ClientDisconnectContext,
    ResolvedTurnMode,
    SlotReleaseDecision,
    TurnMode,
    build_internal_turn_mode_header,
    decide_client_disconnect,
    decide_slot_release,
    resolve_turn_mode,
    strip_external_turn_mode_headers,
)


def test_turn_mode_resolution_and_immutability() -> None:
    assert resolve_turn_mode(True) is TurnMode.DETACHED
    assert resolve_turn_mode(False) is TurnMode.NON_DETACHED
    assert resolve_turn_mode(None) is TurnMode.UNKNOWN

    r0 = ResolvedTurnMode(TurnMode.UNKNOWN)
    r1 = r0.lock_with(TurnMode.DETACHED)
    assert r1.mode is TurnMode.DETACHED
    assert r1.lock_with(TurnMode.NON_DETACHED).mode is TurnMode.DETACHED
    assert r1.lock_with(TurnMode.UNKNOWN).mode is TurnMode.DETACHED

    r2 = r0.lock_with(TurnMode.NON_DETACHED)
    assert r2.lock_with(TurnMode.DETACHED).mode is TurnMode.NON_DETACHED


def test_unconditional_external_header_strip_case_insensitive() -> None:
    raw = {
        "Authorization": "Bearer tok",
        "X-Bridge-Internal-Turn-Mode": "detached",
        "x-bridge-internal-turn-mode": "non_detached",
        "X-BRIDGE-INTERNAL-TURN-MODE": "spoof",
        "X-Request-Id": "req-1",
    }
    cleaned = strip_external_turn_mode_headers(raw)
    assert cleaned == {"Authorization": "Bearer tok", "X-Request-Id": "req-1"}
    assert build_internal_turn_mode_header(TurnMode.DETACHED, propagation_enabled=False) is None
    assert build_internal_turn_mode_header(TurnMode.UNKNOWN, propagation_enabled=True) is None
    assert build_internal_turn_mode_header(TurnMode.DETACHED, propagation_enabled=True) == (
        INTERNAL_TURN_MODE_HEADER,
        "detached",
    )
    assert build_internal_turn_mode_header(TurnMode.NON_DETACHED, propagation_enabled=True) == (
        INTERNAL_TURN_MODE_HEADER,
        "non_detached",
    )


@pytest.mark.parametrize(
    ("f4", "f5", "f6"),
    list(itertools.product((False, True), repeat=3)),
)
def test_full_flag_matrix_detached_never_cancelled_and_unknown_fail_closed(
    f4: bool, f5: bool, f6: bool
) -> None:
    for is_res in (False, True):
        for wired in (False, True):
            det_ctx = ClientDisconnectContext(TurnMode.DETACHED, f4, f5, f6, is_resident=is_res, cancel_wired=wired)
            assert decide_client_disconnect(det_ctx) is CancelDecision.MARK_DETACHED
            unk_ctx = ClientDisconnectContext(TurnMode.UNKNOWN, f4, f5, f6, is_resident=is_res, cancel_wired=wired)
            assert decide_client_disconnect(unk_ctx) is CancelDecision.NO_CANCEL


def test_nondetached_cancel_and_resident_fail_closed_matrix() -> None:
    # Non-resident: follows flag #4 only
    assert decide_client_disconnect(ClientDisconnectContext(TurnMode.NON_DETACHED, False, False, False, False, True)) is CancelDecision.NO_CANCEL
    assert decide_client_disconnect(ClientDisconnectContext(TurnMode.NON_DETACHED, True, False, False, False, True)) is CancelDecision.CANCEL_NONDETACHED

    # Resident: requires #4=True AND #5=True AND cancel_wired=True (OPEN-16 fail-closed!)
    assert decide_client_disconnect(ClientDisconnectContext(TurnMode.NON_DETACHED, True, False, False, True, True)) is CancelDecision.NO_CANCEL
    assert decide_client_disconnect(ClientDisconnectContext(TurnMode.NON_DETACHED, True, True, False, True, False)) is CancelDecision.NO_CANCEL
    assert decide_client_disconnect(ClientDisconnectContext(TurnMode.NON_DETACHED, True, True, False, True, True)) is CancelDecision.CANCEL_NONDETACHED


def test_slot_release_gate_matrix() -> None:
    assert decide_slot_release(False, True, False) is SlotReleaseDecision.RELEASE_IMMEDIATE
    assert decide_slot_release(True, False, False) is SlotReleaseDecision.RELEASE_IMMEDIATE
    assert decide_slot_release(True, True, False) is SlotReleaseDecision.WAIT_PGID_CONFIRMED_DEAD
    assert decide_slot_release(True, True, True) is SlotReleaseDecision.RELEASE_IMMEDIATE
