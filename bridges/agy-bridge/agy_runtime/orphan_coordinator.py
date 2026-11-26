"""Pure Zero-I/O unified AGY OrphanFsm x readers x dead_confirmed coordinator (W05, AD-002)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.pgid_cleanup_policy import CleanupState


class CoordinatorEvent(Enum):
    """Canonical lifecycle events entering the AGY orphan/teardown coordinator."""

    READER_ATTACH = "reader_attach"
    READER_DISCONNECT = "reader_disconnect"
    HYGIENE_TICK = "hygiene_tick"
    CLEANUP_POLL = "cleanup_poll"


class OrphanPhase(Enum):
    """Explicit phase of AGY intentional orphan turn protection."""

    NONE = "none"
    ORPHAN_CANDIDATE = "orphan_candidate"
    ORPHAN_ACTIVE = "orphan_active"
    ORPHAN_EXPIRED = "orphan_expired"


class CoordinatorDecision(Enum):
    """Single authoritative action emitted by AGY coordinator."""

    KEEP = "keep"
    ORPHAN_KEEP = "orphan_keep"
    TEARDOWN_REQUEST = "teardown_request"
    HOLD_QUARANTINE = "hold_quarantine"
    REJECT_409_CANCELLING = "reject_409_cancelling"
    RELEASE_OK = "release_ok"
    NOOP_STALE = "noop_stale"


@dataclass(frozen=True)
class OrphanState:
    """Complete AGY orphan-eligibility snapshot (sourced orphan_max from config)."""

    tools_active: bool
    active_orphans: int
    orphan_max: int
    ttfc_seen: bool
    phase: OrphanPhase
    fast_client_gone_enabled: bool = True


@dataclass(frozen=True)
class CoordinatorContext:
    """Single frozen input struct for decide_agy_action (args=1 <= 5)."""

    event: CoordinatorEvent
    orphan_state: OrphanState
    readers: int
    dead_confirmed: bool
    cleanup_state: CleanupState
    epoch_ok: bool


def is_orphan_eligible(orphan: OrphanState) -> bool:
    """Check AGY intentional orphan criteria (tools>0 post-TTFC, active_orphans<orphan_max)."""
    return (
        orphan.fast_client_gone_enabled
        and orphan.tools_active
        and orphan.ttfc_seen
        and orphan.active_orphans < orphan.orphan_max
    )


def _is_cancelling_or_quarantined(state: CleanupState) -> bool:
    return state in (CleanupState.TERM_SENT, CleanupState.KILL_SENT, CleanupState.QUARANTINED)


def _decide_attach(ctx: CoordinatorContext) -> CoordinatorDecision:
    if _is_cancelling_or_quarantined(ctx.cleanup_state):
        return CoordinatorDecision.REJECT_409_CANCELLING
    return CoordinatorDecision.KEEP


def _decide_disconnect_or_tick(ctx: CoordinatorContext) -> CoordinatorDecision:
    if _is_cancelling_or_quarantined(ctx.cleanup_state):
        return CoordinatorDecision.HOLD_QUARANTINE
    if ctx.readers >= 1:
        return CoordinatorDecision.KEEP
    phase = ctx.orphan_state.phase
    if phase in (OrphanPhase.ORPHAN_CANDIDATE, OrphanPhase.ORPHAN_ACTIVE):
        return CoordinatorDecision.ORPHAN_KEEP
    if phase is OrphanPhase.NONE and is_orphan_eligible(ctx.orphan_state):
        return CoordinatorDecision.ORPHAN_KEEP
    return CoordinatorDecision.TEARDOWN_REQUEST


def decide_agy_action(ctx: CoordinatorContext) -> CoordinatorDecision:
    """Single authoritative Zero-I/O decision function for AGY HygieneRuntime & JobRegistry."""
    if not ctx.epoch_ok:
        return CoordinatorDecision.NOOP_STALE
    if ctx.dead_confirmed or ctx.cleanup_state in (CleanupState.DEAD_CONFIRMED, CleanupState.RELEASED):
        return CoordinatorDecision.RELEASE_OK
    if ctx.event is CoordinatorEvent.READER_ATTACH:
        return _decide_attach(ctx)
    if ctx.event is CoordinatorEvent.CLEANUP_POLL:
        return CoordinatorDecision.HOLD_QUARANTINE
    return _decide_disconnect_or_tick(ctx)
