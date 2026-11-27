"""Чистая политика выбора процесса, контекста и эпохи сессии."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .capabilities import DriverCapabilities
from .identity import CanonicalSessionIdentity

ProcessDirective = Literal["WARM_SLOT_REUSE", "EPHEMERAL_KILL_AFTER_TURN"]
ContextDirective = Literal["CONTEXT_CONTINUE", "CONTEXT_RESET_LOGICAL", "SLOT_HARD_RESET"]
HistoryRelation = Literal["cold", "prefix_match", "diverged", "header_changed"]


@dataclass(frozen=True, slots=True)
class SlotRuntimeSnapshot:
    has_warm_slot: bool = False
    turn_count: int = 0
    current_epoch: int = 0
    rss_mb: float = 0.0
    home_verified: bool = True
    stdout_desync: bool = False
    binary_hash: str = ""


@dataclass(frozen=True, slots=True)
class PolicyLimits:
    max_turns_per_slot: int = 50
    idle_ttl_s: int = 180
    max_rss_mb: int = 512
    host_rss_cap_mb: int = 16384
    acquire_timeout_ms: int = 500
    config_revision: int = 0


@dataclass(frozen=True, slots=True)
class SessionExecutionPlan:
    schema_version: str
    partition_key: str
    canonical_chat_id: str | None
    isolation_namespace: str
    affinity_uuid5: str
    review_profile: str
    process_directive: ProcessDirective
    context_directive: ContextDirective
    next_epoch: int
    zc_clean_home_required: bool
    strip_outbound_tools: bool
    max_turns_per_slot: int
    idle_ttl_s: int
    max_rss_mb: int
    config_revision: int
    decision_reason: str


def _plan(identity: CanonicalSessionIdentity, limits: PolicyLimits, process: ProcessDirective, context: ContextDirective, epoch: int, reason: str, *, clean: bool, strip: bool) -> SessionExecutionPlan:
    return SessionExecutionPlan(
        "session-plan/v1", identity.partition_key, identity.canonical_chat_id, identity.isolation_namespace,
        identity.affinity_uuid5, identity.review_profile, process, context, epoch, clean, strip,
        limits.max_turns_per_slot, limits.idle_ttl_s, limits.max_rss_mb, limits.config_revision, reason,
    )


def decide_session_plan(
    identity: CanonicalSessionIdentity,
    caps: DriverCapabilities,
    history_relation: HistoryRelation,
    slot: SlotRuntimeSnapshot | None = None,
    *,
    tools_requested: bool = False,
    limits: PolicyLimits | None = None,
    keyed_zc_enabled: bool = True,
    host_rss_mb: float = 0.0,
) -> SessionExecutionPlan:
    """Выбирает безопасный план, сохраняя affinity при логическом сбросе."""
    limits = limits or PolicyLimits()
    slot = slot or SlotRuntimeSnapshot()
    zc = identity.review_profile == "zero-canon"
    clean = zc
    strip = zc and not tools_requested
    if not identity.keyed:
        reason = "UNKEYED_ZC_EPHEMERAL" if zc else "UNKEYED_EPHEMERAL"
        return _plan(identity, limits, "EPHEMERAL_KILL_AFTER_TURN", "SLOT_HARD_RESET", slot.current_epoch + 1, reason, clean=clean, strip=strip)
    if zc and not keyed_zc_enabled:
        return _plan(identity, limits, "EPHEMERAL_KILL_AFTER_TURN", "SLOT_HARD_RESET", slot.current_epoch + 1, "ZC_KEYED_FLAG_DISABLED", clean=True, strip=strip)
    if slot.stdout_desync or (zc and not slot.home_verified) or slot.rss_mb > limits.max_rss_mb or host_rss_mb > limits.host_rss_cap_mb or slot.turn_count >= limits.max_turns_per_slot:
        if zc and not slot.home_verified:
            process: ProcessDirective = "EPHEMERAL_KILL_AFTER_TURN"
            reason = "HOME_UNVERIFIED_FAIL_CLOSED"
        else:
            process = "WARM_SLOT_REUSE" if caps.supports_warm_zero_canon and caps.transport_class != "http_passthrough" else "EPHEMERAL_KILL_AFTER_TURN"
            reason = "HEALTH_FAIL_CLOSED"
        return _plan(identity, limits, process, "SLOT_HARD_RESET", slot.current_epoch + 1, reason, clean=clean, strip=strip)
    if caps.transport_class == "http_passthrough":
        process = "EPHEMERAL_KILL_AFTER_TURN"
        if history_relation == "prefix_match" and slot.has_warm_slot:
            return _plan(identity, limits, process, "CONTEXT_CONTINUE", slot.current_epoch, "PASSTHROUGH_PREFIX_MATCH", clean=clean, strip=strip)
        epoch = slot.current_epoch + 1 if slot.has_warm_slot else 1
        reason = "PASSTHROUGH_LOGICAL_RESET" if history_relation != "cold" else "PASSTHROUGH_COLD"
        return _plan(identity, limits, process, "CONTEXT_RESET_LOGICAL", epoch, reason, clean=clean, strip=strip)
    if not caps.supports_warm_zero_canon:
        return _plan(identity, limits, "EPHEMERAL_KILL_AFTER_TURN", "CONTEXT_RESET_LOGICAL", 1, "WARM_UNSUPPORTED", clean=clean, strip=strip)
    if not slot.has_warm_slot:
        return _plan(identity, limits, "WARM_SLOT_REUSE", "CONTEXT_RESET_LOGICAL", 1, "COLD_START", clean=clean, strip=strip)
    if history_relation == "prefix_match":
        return _plan(identity, limits, "WARM_SLOT_REUSE", "CONTEXT_CONTINUE", slot.current_epoch, "PREFIX_MATCH", clean=clean, strip=strip)
    if history_relation in ("diverged", "header_changed"):
        if caps.supports_logical_context_reset:
            return _plan(identity, limits, "WARM_SLOT_REUSE", "CONTEXT_RESET_LOGICAL", slot.current_epoch + 1, "HISTORY_DIVERGED_LOGICAL_RESET", clean=clean, strip=strip)
        return _plan(identity, limits, "WARM_SLOT_REUSE", "SLOT_HARD_RESET", slot.current_epoch + 1, "LOGICAL_RESET_UNSUPPORTED", clean=clean, strip=strip)
    return _plan(identity, limits, "WARM_SLOT_REUSE", "CONTEXT_RESET_LOGICAL", slot.current_epoch + 1, "COLD_RESEED", clean=clean, strip=strip)


def check_epoch_frame(frame_epoch: int, current_epoch: int) -> bool:
    """Принимает только кадры текущей эпохи."""
    return frame_epoch == current_epoch
