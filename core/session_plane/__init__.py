"""Универсальный control plane для идентичности и жизненного цикла сессий."""

from .capabilities import DEFAULT_CAPABILITIES, DriverCapabilities, effective_capabilities
from .directive_codec import (
    DIRECTIVE_HEADER,
    DIRECTIVE_TTL_S,
    MAX_DIRECTIVE_BYTES,
    SignedDirectivePayload,
    encode_directive,
    verify_directive,
)
from .identity import (
    CanonicalSessionIdentity,
    NAMESPACE_DSH,
    SessionIdentityError,
    SessionIdentityInput,
    extract_canonical_chat_id,
    resolve_canonical_identity,
)
from .lifecycle_policy import (
    PolicyLimits,
    SessionExecutionPlan,
    SlotRuntimeSnapshot,
    check_epoch_frame,
    decide_session_plan,
)
from .zc_env_guard import (
    allocate_zc_slot_home,
    cleanup_zc_slot_home,
    is_agy_drain_early_exit_enabled,
    is_agy_signed_directive_enabled,
    is_passthrough_canonical_affinity_enabled,
    is_session_plane_enabled,
    is_session_plane_prompt_cache_key_enabled,
    is_zero_canon_keyed_resident_enabled,
    load_or_create_directive_key,
    verify_zc_slot_home,
)

__all__ = (
    "DEFAULT_CAPABILITIES", "DriverCapabilities", "effective_capabilities",
    "DIRECTIVE_HEADER", "DIRECTIVE_TTL_S", "MAX_DIRECTIVE_BYTES",
    "SignedDirectivePayload", "encode_directive", "verify_directive",
    "CanonicalSessionIdentity", "NAMESPACE_DSH", "SessionIdentityError",
    "SessionIdentityInput", "extract_canonical_chat_id", "resolve_canonical_identity",
    "PolicyLimits", "SessionExecutionPlan", "SlotRuntimeSnapshot",
    "check_epoch_frame", "decide_session_plan", "allocate_zc_slot_home",
    "cleanup_zc_slot_home", "is_agy_drain_early_exit_enabled",
    "is_agy_signed_directive_enabled", "is_passthrough_canonical_affinity_enabled",
    "is_session_plane_enabled", "is_session_plane_prompt_cache_key_enabled",
    "is_zero_canon_keyed_resident_enabled",
    "load_or_create_directive_key", "verify_zc_slot_home",
)
