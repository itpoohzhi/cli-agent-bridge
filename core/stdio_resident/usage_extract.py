"""Bounded-path vendor usage extractors producing pure UsageUpdate objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from core.turn_usage import UsageScope, UsageUpdate

_MUSE_IN = ("inputTokens", "promptTokens", "input_tokens", "prompt_tokens")
_MUSE_OUT = ("outputTokens", "completionTokens", "output_tokens", "completion_tokens")
_MUSE_CACHE_READ = ("cachedTokens", "cacheReadTokens", "cache_read_tokens", "cached_tokens")
_MUSE_CACHE_CREATE = ("cacheCreationTokens", "cache_creation_tokens")
_MUSE_REASONING = ("reasoningTokens", "reasoning_tokens")
_MUSE_TOTAL = ("totalTokens", "total_tokens")
_GENERIC_IN = ("input_tokens", "inputTokens")
_GENERIC_OUT = ("output_tokens", "outputTokens")
_GENERIC_CACHE = (
    "cached_tokens", "cachedTokens", "cache_read_tokens", "cacheReadTokens",
    "cache_read_input_tokens", "cache_creation_tokens", "cacheCreationTokens",
    "cache_creation_input_tokens",
)
_GENERIC_REASONING = ("reasoning_tokens", "reasoningTokens", "thinking_tokens", "thinkingTokens")


@dataclass(frozen=True, slots=True)
class UsageExtractPolicy:
    """Frozen declarative mapping from bounded JSON paths to UsageUpdate."""

    source: str
    paths: tuple[tuple[str, ...], ...]
    input_keys: tuple[str, ...]
    output_keys: tuple[str, ...]
    cache_read_keys: tuple[str, ...] = ()
    cache_creation_keys: tuple[str, ...] = ()
    reasoning_keys: tuple[str, ...] = ()
    total_keys: tuple[str, ...] = ("total_tokens", "totalTokens")
    input_includes_cache: bool = True
    output_includes_reasoning: bool = True
    scope: UsageScope = UsageScope.TURN_SNAPSHOT


def _walk_path(root: Mapping[str, Any], path: tuple[str, ...]) -> Mapping[str, Any] | None:
    cur: object = root
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cast(Mapping[str, Any], cur).get(key)
    return cast(Mapping[str, Any], cur) if isinstance(cur, Mapping) else None


def _first_present(mapping: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _nested(mapping: Mapping[str, Any], parent: str, child: str) -> Any:
    sub = mapping.get(parent)
    if isinstance(sub, Mapping):
        val = cast(Mapping[str, Any], sub).get(child)
        if val is not None:
            return val
    return None


def _build_from_mapping(
    mapping: Mapping[str, Any], policy: UsageExtractPolicy
) -> tuple[UsageUpdate, bool]:
    in_tok = _first_present(mapping, policy.input_keys)
    out_tok = _first_present(mapping, policy.output_keys)
    cache_read = _nested(mapping, "prompt_tokens_details", "cached_tokens")
    if cache_read is None:
        cache_read = _first_present(mapping, policy.cache_read_keys)
    reasoning = _nested(mapping, "completion_tokens_details", "reasoning_tokens")
    if reasoning is None:
        reasoning = _first_present(mapping, policy.reasoning_keys)
    update = UsageUpdate(
        input_tokens=in_tok,
        output_tokens=out_tok,
        cache_read_tokens=cache_read,
        cache_creation_tokens=_first_present(mapping, policy.cache_creation_keys),
        reasoning_tokens=reasoning,
        reported_total_tokens=_first_present(mapping, policy.total_keys),
        input_includes_cache=policy.input_includes_cache,
        output_includes_reasoning=policy.output_includes_reasoning,
        source=policy.source,
        scope=policy.scope,
    )
    return update, (in_tok is not None and out_tok is not None)


def _has_any_key(mapping: Mapping[str, Any], policy: UsageExtractPolicy) -> bool:
    keys = (
        *policy.input_keys, *policy.output_keys, *policy.cache_read_keys,
        *policy.cache_creation_keys, *policy.reasoning_keys, *policy.total_keys,
    )
    return any(k in mapping for k in keys)


def extract_usage_by_policy(
    payload: Mapping[str, Any], policy: UsageExtractPolicy
) -> UsageUpdate | None:
    """Evaluate bounded paths in order; first path with both input & output wins."""
    partial: UsageUpdate | None = None
    for path in policy.paths:
        mapping = _walk_path(payload, path)
        if mapping is None:
            continue
        update, has_req = _build_from_mapping(mapping, policy)
        if has_req:
            return update
        if partial is None and _has_any_key(mapping, policy):
            partial = update
    return partial


def _extract_openai_wire_mapping(mapping: Mapping[str, Any], source: str) -> UsageUpdate:
    cache_read = _nested(mapping, "prompt_tokens_details", "cached_tokens")
    if cache_read is None:
        cache_read = _first_present(mapping, ("cached_tokens",))
    reasoning = _nested(mapping, "completion_tokens_details", "reasoning_tokens")
    if reasoning is None:
        reasoning = _first_present(mapping, ("reasoning_tokens",))
    return UsageUpdate(
        input_tokens=mapping.get("prompt_tokens"),
        output_tokens=mapping.get("completion_tokens"),
        cache_read_tokens=cache_read,
        reasoning_tokens=reasoning,
        reported_total_tokens=mapping.get("total_tokens"),
        input_includes_cache=True,
        output_includes_reasoning=True,
        source=source,
    )


def _has_ambiguous_details(mapping: Mapping[str, Any]) -> bool:
    return (
        _first_present(mapping, _GENERIC_CACHE) is not None
        or _first_present(mapping, _GENERIC_REASONING) is not None
        or _nested(mapping, "prompt_tokens_details", "cached_tokens") is not None
        or _nested(mapping, "completion_tokens_details", "reasoning_tokens") is not None
    )


def _extract_multiprovider_mapping(
    mapping: Mapping[str, Any], source: str
) -> UsageUpdate | None:
    if mapping.get("prompt_tokens") is not None and mapping.get("completion_tokens") is not None:
        return _extract_openai_wire_mapping(mapping, source)
    in_tok = _first_present(mapping, _GENERIC_IN)
    out_tok = _first_present(mapping, _GENERIC_OUT)
    if in_tok is None or out_tok is None:
        return None
    if _has_ambiguous_details(mapping):
        return UsageUpdate(None, None, source=source, rejection_reason="ambiguous_accounting_semantics")
    return UsageUpdate(
        input_tokens=in_tok,
        output_tokens=out_tok,
        reported_total_tokens=_first_present(mapping, ("total_tokens", "totalTokens")),
        input_includes_cache=True,
        output_includes_reasoning=True,
        source=source,
    )


def extract_multiprovider_usage(
    payload: Mapping[str, Any], paths: tuple[tuple[str, ...], ...], source: str
) -> UsageUpdate | None:
    """Safe extractor for multi-provider/generic drivers (OpenAI wire or cacheless only)."""
    for path in paths:
        mapping = _walk_path(payload, path)
        if mapping is not None and (update := _extract_multiprovider_mapping(mapping, source)) is not None:
            return update
    return None


_MUSE_TOKEN_POLICY = UsageExtractPolicy(
    source="muse_msp_v1", paths=((),), input_keys=_MUSE_IN, output_keys=_MUSE_OUT,
    cache_read_keys=_MUSE_CACHE_READ, cache_creation_keys=_MUSE_CACHE_CREATE,
    reasoning_keys=_MUSE_REASONING, total_keys=_MUSE_TOTAL,
)
_MUSE_DONE_POLICY = UsageExtractPolicy(
    source="muse_msp_v1", paths=(("usage",), ("tokenUsage",)),
    input_keys=_MUSE_IN, output_keys=_MUSE_OUT,
    cache_read_keys=_MUSE_CACHE_READ, cache_creation_keys=_MUSE_CACHE_CREATE,
    reasoning_keys=_MUSE_REASONING, total_keys=_MUSE_TOTAL,
)
_CLAUDE_POLICY = UsageExtractPolicy(
    source="claude_stream_json", paths=(("usage",),),
    input_keys=("input_tokens",), output_keys=("output_tokens",),
    cache_read_keys=("cache_read_input_tokens", "cache_read_tokens"),
    cache_creation_keys=("cache_creation_input_tokens", "cache_creation_tokens"),
    total_keys=("total_tokens",), input_includes_cache=False, output_includes_reasoning=True,
)
_AGY_POLICY = UsageExtractPolicy(
    source="agy_stream_json", paths=(("usage",), ("result", "usage")),
    input_keys=_GENERIC_IN, output_keys=_GENERIC_OUT,
    cache_read_keys=("cache_read_tokens", "cacheReadTokens", "cached_tokens", "cachedTokens"),
    cache_creation_keys=("cache_creation_tokens", "cacheCreationTokens"),
    reasoning_keys=_GENERIC_REASONING, input_includes_cache=False, output_includes_reasoning=False,
)


def extract_muse_usage(method: str, params: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract Muse MSP v1 UsageUpdate from session/tokenUsage or turn/completed."""
    if method in {"session/tokenUsage", "turn/tokenUsage", "run.tokenUsage"}:
        return extract_usage_by_policy(params, _MUSE_TOKEN_POLICY)
    if method in {"run.terminal.completed", "turn/completed", "run.terminal.failed", "turn/failed"}:
        return extract_usage_by_policy(params, _MUSE_DONE_POLICY)
    return None


def extract_claude_usage(payload: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract Claude stream-json UsageUpdate from result frames."""
    return extract_usage_by_policy(payload, _CLAUDE_POLICY) if payload.get("type") == "result" else None


def extract_agy_usage(payload: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract Agy stream-json UsageUpdate from result frames."""
    return extract_usage_by_policy(payload, _AGY_POLICY)


def extract_opencode_usage(payload: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract unambiguous usage from OpenCode ACP frames."""
    return extract_multiprovider_usage(
        payload, (("result", "usage"), ("params", "update", "usage"), ("params", "usage")), "opencode_acp"
    )


def extract_stream_json_usage(payload: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract unambiguous usage from generic StreamJsonDriver frames."""
    return extract_multiprovider_usage(payload, (("usage",), ("result", "usage")), "stream_json")


def extract_jsonrpc_usage(payload: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract unambiguous usage from generic StreamJsonRpcDriver frames."""
    paths = (("result", "usage"), ("params", "update", "usage"), ("params", "tokenUsage"), ("params", "usage"))
    return extract_multiprovider_usage(payload, paths, "stream_jsonrpc")


def extract_acp_usage(payload: Mapping[str, Any]) -> UsageUpdate | None:
    """Extract unambiguous usage from generic AcpDriver frames."""
    return extract_multiprovider_usage(payload, (("payload", "usage"), ("usage",), ("result", "usage")), "acp")
