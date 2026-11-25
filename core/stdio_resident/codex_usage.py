"""Stateless Codex app-server (v2 & legacy) usage extraction and chunk builder."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.stdio_resident.codex_protocol_fsm import EffectKind, ProtocolEffect
from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.usage_extract import UsageExtractPolicy, extract_usage_by_policy
from core.turn_usage import UsageScope, UsageUpdate

_CODEX_IN = ("input_tokens", "inputTokens", "prompt_tokens", "promptTokens")
_CODEX_OUT = ("output_tokens", "outputTokens", "completion_tokens", "completionTokens")
_CODEX_CACHE_READ = (
    "cached_input_tokens",
    "cachedInputTokens",
    "cached_tokens",
    "cachedTokens",
    "cache_read_tokens",
    "cacheReadTokens",
)
_CODEX_REASONING = (
    "reasoning_output_tokens",
    "reasoningOutputTokens",
    "reasoning_tokens",
    "reasoningTokens",
)
_CODEX_TOTAL = ("total_tokens", "totalTokens")

_CODEX_V2_TURN_POLICY = UsageExtractPolicy(
    source="codex_app_server_v2",
    paths=(
        ("params", "tokenUsage", "last"),
        ("params", "info", "last_token_usage"),
        ("params", "usage"),
        ("params", "turn", "usage"),
    ),
    input_keys=_CODEX_IN,
    output_keys=_CODEX_OUT,
    cache_read_keys=_CODEX_CACHE_READ,
    reasoning_keys=_CODEX_REASONING,
    total_keys=_CODEX_TOTAL,
    input_includes_cache=True,
    output_includes_reasoning=True,
    scope=UsageScope.TURN_SNAPSHOT,
)

_CODEX_V2_SESSION_POLICY = UsageExtractPolicy(
    source="codex_app_server_v2",
    paths=(
        ("params", "info", "total_token_usage"),
        ("params", "tokenUsage", "total"),
    ),
    input_keys=_CODEX_IN,
    output_keys=_CODEX_OUT,
    cache_read_keys=_CODEX_CACHE_READ,
    reasoning_keys=_CODEX_REASONING,
    total_keys=_CODEX_TOTAL,
    input_includes_cache=True,
    output_includes_reasoning=True,
    scope=UsageScope.SESSION_COUNTER,
)

_CODEX_LEGACY_POLICY = UsageExtractPolicy(
    source="codex_app_server",
    paths=(("result", "usage"), ("params", "usage"), ("params", "tokenUsage")),
    input_keys=_CODEX_IN,
    output_keys=_CODEX_OUT,
    cache_read_keys=_CODEX_CACHE_READ,
    reasoning_keys=_CODEX_REASONING,
    total_keys=_CODEX_TOTAL,
    input_includes_cache=True,
    output_includes_reasoning=True,
    scope=UsageScope.TURN_SNAPSHOT,
)


def _has_positive_usage(usage: UsageUpdate) -> bool:
    """Return True iff at least one token counter in UsageUpdate is positive."""
    return any(
        isinstance(v, int) and not isinstance(v, bool) and v > 0
        for v in (
            usage.input_tokens,
            usage.output_tokens,
            usage.cache_read_tokens,
            usage.cache_creation_tokens,
            usage.reasoning_tokens,
            usage.reported_total_tokens,
        )
    )


def extract_codex_v2_usage(payload: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract per-turn snapshot or fail-closed SESSION_COUNTER from Codex v2 frame."""
    turn_usage = extract_usage_by_policy(payload, _CODEX_V2_TURN_POLICY)
    if turn_usage is not None:
        return turn_usage if _has_positive_usage(turn_usage) else None
    session_usage = extract_usage_by_policy(payload, _CODEX_V2_SESSION_POLICY)
    if session_usage is not None and _has_positive_usage(session_usage):
        return session_usage
    return None


def extract_codex_legacy_usage(payload: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract per-turn usage from legacy Codex app-server JSON-RPC frame."""
    usage = extract_usage_by_policy(payload, _CODEX_LEGACY_POLICY)
    return usage if usage is not None and _has_positive_usage(usage) else None


def _frame_identifier(params: Mapping[str, Any], *keys: str) -> str | None:
    """Return the first non-empty string identifier from a mapping."""
    for key in keys:
        value = params.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_frame_ids(params: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Extract thread and turn identifiers from a Codex v2 params mapping."""
    thread_id = _frame_identifier(params, "threadId", "thread_id")
    turn_id = _frame_identifier(params, "turnId", "turn_id")
    turn = params.get("turn")
    if not turn_id and isinstance(turn, Mapping):
        turn_id = _frame_identifier(turn, "id")
    return thread_id, turn_id


def _ids_match_active(
    frame_ids: tuple[str | None, str | None],
    active_thread_id: str | None,
    active_turn_id: str | None,
) -> bool:
    """Return whether present frame identifiers match the active request."""
    thread_id, turn_id = frame_ids
    if active_thread_id and thread_id and thread_id != active_thread_id:
        return False
    if active_turn_id and turn_id and turn_id != active_turn_id:
        return False
    return True


def is_frame_usage_allowed(
    payload: Mapping[str, Any],
    active_thread_id: str | None = None,
    active_turn_id: str | None = None,
) -> bool:
    """Check whether a Codex v2 usage frame belongs to the active turn."""
    method = payload.get("method")
    params = payload.get("params")
    if not isinstance(params, Mapping):
        return False
    if not _ids_match_active(
        _extract_frame_ids(params), active_thread_id, active_turn_id
    ):
        return False
    if method == "thread/tokenUsage/updated":
        return isinstance(params.get("tokenUsage"), Mapping)
    if method == "turn/completed":
        return isinstance(params.get("turn"), Mapping)
    return False


def format_codex_effect_error(payload: Mapping[str, object]) -> str:
    """Format an EMIT_ERROR effect payload consistently."""
    code, msg = str(payload.get("code") or ""), str(payload.get("message") or "")
    if code and msg:
        return f"{code}: {msg}"
    return code or msg or "resident_protocol_failed"


def _guarded_usage(
    effects: tuple[ProtocolEffect, ...],
    payload: Mapping[str, Any],
    active_thread_id: str | None,
    active_turn_id: str | None,
    guard_enabled: bool,
) -> UsageUpdate | None:
    """Extract usage and apply optional frame and identifier guards."""
    usage = extract_codex_v2_usage(payload)
    if not guard_enabled:
        return usage
    if not is_frame_usage_allowed(payload, active_thread_id, active_turn_id):
        return None
    if effects:
        return usage
    params = payload.get("params")
    thread_id, turn_id = _extract_frame_ids(params)
    if not any((active_thread_id, active_turn_id)):
        return usage
    if active_thread_id == thread_id is not None:
        return usage
    if active_turn_id == turn_id is not None:
        return usage
    return None


def _collect_effect_parts(
    effects: tuple[ProtocolEffect, ...],
) -> tuple[str, str, str | None, bool]:
    """Collect text, reasoning, error, and terminal state from protocol effects."""
    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    error: str | None = None
    is_term = False
    for eff in effects:
        if eff.kind is EffectKind.EMIT_DELTA:
            target = (reasoning_parts, text_parts)[eff.payload.get("channel") == "content"]
            target.append(str(eff.payload.get("delta", "")))
        elif eff.kind is EffectKind.EMIT_ERROR:
            error = format_codex_effect_error(eff.payload)
        elif eff.kind is EffectKind.EMIT_TERMINAL:
            is_term = True
            if eff.payload.get("status") == "interrupted" and error is None:
                error = "turn_interrupted"
    return "".join(text_parts), "".join(reasoning_parts), error, is_term


def codex_v2_effects_to_chunk(
    effects: tuple[ProtocolEffect, ...],
    payload: dict[str, Any],
    *,
    active_thread_id: str | None = None,
    active_turn_id: str | None = None,
    guard_enabled: bool = False,
) -> DecodedChunk | None:
    """Convert Codex v2 FSM effects plus stateless usage extraction into DecodedChunk."""
    usage = _guarded_usage(
        effects, payload, active_thread_id, active_turn_id, guard_enabled
    )
    if not effects and usage is None:
        return None
    text, reasoning, error, is_term = _collect_effect_parts(effects)
    return DecodedChunk(
        text=text,
        reasoning=reasoning,
        is_terminal=is_term,
        raw=payload,
        error=error,
        usage=usage,
    )
