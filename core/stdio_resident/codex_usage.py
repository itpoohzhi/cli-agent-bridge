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


def extract_codex_v2_usage(payload: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract per-turn snapshot or fail-closed SESSION_COUNTER from Codex v2 frame."""
    turn_usage = extract_usage_by_policy(payload, _CODEX_V2_TURN_POLICY)
    if turn_usage is not None:
        return turn_usage
    return extract_usage_by_policy(payload, _CODEX_V2_SESSION_POLICY)


def extract_codex_legacy_usage(payload: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract per-turn usage from legacy Codex app-server JSON-RPC frame."""
    return extract_usage_by_policy(payload, _CODEX_LEGACY_POLICY)


def format_codex_effect_error(payload: Mapping[str, object]) -> str:
    """Format an EMIT_ERROR effect payload consistently."""
    code, msg = str(payload.get("code") or ""), str(payload.get("message") or "")
    if code and msg:
        return f"{code}: {msg}"
    return code or msg or "resident_protocol_failed"


def codex_v2_effects_to_chunk(
    effects: tuple[ProtocolEffect, ...], payload: dict[str, Any]
) -> DecodedChunk | None:
    """Convert Codex v2 FSM effects plus stateless usage extraction into DecodedChunk."""
    usage = extract_codex_v2_usage(payload)
    if not effects and usage is None:
        return None
    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    error: str | None = None
    is_term = False
    for eff in effects:
        if eff.kind is EffectKind.EMIT_DELTA:
            target = text_parts if eff.payload.get("channel") == "content" else reasoning_parts
            target.append(str(eff.payload.get("delta", "")))
        elif eff.kind is EffectKind.EMIT_ERROR:
            error = format_codex_effect_error(eff.payload)
        elif eff.kind is EffectKind.EMIT_TERMINAL:
            is_term = True
            if eff.payload.get("status") == "interrupted" and error is None:
                error = "turn_interrupted"
    return DecodedChunk(
        text="".join(text_parts),
        reasoning="".join(reasoning_parts),
        is_terminal=is_term,
        raw=payload,
        error=error,
        usage=usage,
    )
