"""Pure Zero-I/O hub TurnMode immutability, external header strip, and client-cancel policy (W10)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Final

INTERNAL_TURN_MODE_HEADER: Final[str] = "X-Bridge-Internal-Turn-Mode"
_INTERNAL_TURN_MODE_LOWER: Final[str] = INTERNAL_TURN_MODE_HEADER.lower()


class TurnMode(Enum):
    """Explicit immutable turn lifecycle mode (replaces dead Handler._detach_on_disconnect)."""

    UNKNOWN = "unknown"
    DETACHED = "detached"
    NON_DETACHED = "non_detached"


class CancelDecision(Enum):
    """Authoritative hub decision on client_write_dead / client_gone."""

    NO_CANCEL = "no_cancel"
    MARK_DETACHED = "mark_detached"
    CANCEL_NONDETACHED = "cancel_nondetached"


class SlotReleaseDecision(Enum):
    """Whether hub turn slot release may proceed immediately or must await PGID dead_confirmed."""

    RELEASE_IMMEDIATE = "release_immediate"
    WAIT_PGID_CONFIRMED_DEAD = "wait_pgid_confirmed_dead"


@dataclass(frozen=True)
class ResolvedTurnMode:
    """Immutable wrapper enforcing single-resolution invariant for TurnMode."""

    mode: TurnMode

    def lock_with(self, next_mode: TurnMode) -> ResolvedTurnMode:
        """Once resolved to DETACHED or NON_DETACHED, mode is immutable and cannot change."""
        if self.mode is not TurnMode.UNKNOWN:
            return self
        return ResolvedTurnMode(mode=next_mode)


@dataclass(frozen=True)
class ClientDisconnectContext:
    """Bundled disconnect inputs for pure 3x3 flag-matrix evaluation (args=1 <= 5)."""

    mode: TurnMode
    flag_nondetached_cancel: bool
    flag_resident_wiring: bool
    flag_turn_mode_propagation: bool
    is_resident: bool = False
    cancel_wired: bool = True


def resolve_turn_mode(detach_requested: bool | None) -> TurnMode:
    """Resolve explicit TurnMode from validated hub detach policy; None stays UNKNOWN."""
    if detach_requested is True:
        return TurnMode.DETACHED
    if detach_requested is False:
        return TurnMode.NON_DETACHED
    return TurnMode.UNKNOWN


def strip_external_turn_mode_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Unconditionally strip spoofed X-Bridge-Internal-Turn-Mode from external ingress."""
    return {
        k: v
        for k, v in headers.items()
        if str(k).strip().lower() != _INTERNAL_TURN_MODE_LOWER
    }


def build_internal_turn_mode_header(
    mode: TurnMode,
    propagation_enabled: bool,
) -> tuple[str, str] | None:
    """Emit internal propagation header ONLY when flag #6 is True and mode is resolved."""
    if not propagation_enabled or mode is TurnMode.UNKNOWN:
        return None
    return (INTERNAL_TURN_MODE_HEADER, mode.value)


def decide_client_disconnect(ctx: ClientDisconnectContext) -> CancelDecision:
    """Evaluate hub disconnect action across all #4/#5/#6 combinations (fail-closed)."""
    if ctx.mode is TurnMode.DETACHED:
        return CancelDecision.MARK_DETACHED
    if ctx.mode is TurnMode.UNKNOWN:
        return CancelDecision.NO_CANCEL
    if not ctx.flag_nondetached_cancel:
        return CancelDecision.NO_CANCEL
    if ctx.is_resident and (not ctx.flag_resident_wiring or not ctx.cancel_wired):
        return CancelDecision.NO_CANCEL
    return CancelDecision.CANCEL_NONDETACHED


def decide_slot_release(
    flag_nondetached_cancel: bool,
    pgid_registered: bool,
    pgid_dead_confirmed: bool,
) -> SlotReleaseDecision:
    """Gate hub slot release on PGID dead_confirmed ONLY when flag #4 on AND pgid registered."""
    if not flag_nondetached_cancel or not pgid_registered or pgid_dead_confirmed:
        return SlotReleaseDecision.RELEASE_IMMEDIATE
    return SlotReleaseDecision.WAIT_PGID_CONFIRMED_DEAD
