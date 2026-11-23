"""Stream delta formatting and turn execution helpers for StdioResidentAdapter."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from typing import Any

from core.backend_adapter import StreamSink, TurnContext, TurnResult
from core.runtime_env import stdio_usage_contract_enabled
from core.stdio_resident.codex_attestation_wire import (
    record_v2_turn_completion,
    should_wire_v2_zero_canon,
    wrap_v2_sse_writer,
)
from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.turn_stream import AssembledStreamDelta, TurnStreamAssembler
from core.stdio_resident.zero_canon_router import execute_routed_turn_result
from core.subbridge_zero_canon import review_profile_from_headers
from core.turn_usage import TurnUsage
from core.turn_usage_result import make_turn_result
from core.usage_wire import build_turn_wire_usage


def format_stream_delta(
    delta: AssembledStreamDelta, *, usage_enabled: bool = True
) -> dict[str, Any]:
    """Serialize one AssembledStreamDelta to an OpenAI chat.completion.chunk dict."""
    payload: dict[str, Any] = {}
    if delta.content:
        payload["content"] = delta.content
    if delta.reasoning_content:
        payload["reasoning_content"] = delta.reasoning_content
    if delta.tool_calls:
        payload["tool_calls"] = delta.tool_calls
    stop = "tool_calls" if delta.is_tool_stop else "stop"
    reason = stop if delta.is_terminal else None
    out: dict[str, Any] = {
        "choices": [{"index": 0, "delta": payload, "finish_reason": reason}]
    }
    if usage_enabled and delta.usage is not None:
        out["usage"] = build_turn_wire_usage(delta.usage)
    return out


def stream_assembled_deltas(
    chunks: Iterator[DecodedChunk],
    *,
    usage_enabled: bool = True,
    usage_sink: list[TurnUsage] | None = None,
) -> Iterator[dict[str, Any]]:
    """Assemble DecodedChunks, record lossless TurnUsage into usage_sink, and yield OpenAI chunks."""
    assembler = TurnStreamAssembler(usage_enabled=usage_enabled)
    for chunk in chunks:
        delta = assembler.process_chunk(chunk)
        if usage_enabled and usage_sink is not None and assembler.current_usage is not None:
            if not usage_sink or usage_sink[-1] != assembler.current_usage:
                usage_sink.append(assembler.current_usage)
        yield format_stream_delta(delta, usage_enabled=usage_enabled)


def sample_usage_enabled(data: Mapping[str, Any]) -> bool:
    """Resolve turn-scoped kill-switch (explicit internal override or DynamicFlagSource)."""
    override = data.get("_usage_enabled")
    if isinstance(override, bool):
        return override
    return stdio_usage_contract_enabled()


def _build_turn_request(
    adapter_id: str, ctx: TurnContext, profile: str
) -> dict[str, Any]:
    return {
        "chat_key": ctx.turn_id or ctx.rid or "default",
        "backend_id": adapter_id,
        "model": ctx.model,
        "effort": ctx.effort,
        "cwd": ctx.cwd or os.getcwd(),
        "prompt": ctx.prompt,
        "env": ctx.fwd_env,
        "review_profile": profile,
        "turn_context": {"model": ctx.model, "effort": ctx.effort, "review_profile": profile},
    }


def execute_stdio_turn(
    adapter: Any,
    protocol: str,
    ctx: TurnContext,
    sse_writer: StreamSink | None,
) -> TurnResult:
    """Run one StdioResidentAdapter turn with turn-boundary kill-switch and typed TurnUsage."""
    usage_enabled = stdio_usage_contract_enabled()
    handler = getattr(ctx, "handler", None)
    raw_headers = getattr(handler, "headers", None)
    profile = review_profile_from_headers(raw_headers)
    request = _build_turn_request(adapter.id, ctx, profile)
    request["_usage_enabled"] = usage_enabled
    hdr_map = dict(raw_headers.items()) if hasattr(raw_headers, "items") else None
    driver = getattr(adapter, "_driver", None)
    wire_zc = should_wire_v2_zero_canon(protocol, profile, handler)
    writer = (
        wrap_v2_sse_writer(sse_writer, driver, handler, ctx.model, ctx.effort)
        if wire_zc
        else sse_writer
    )
    routed = execute_routed_turn_result(
        adapter.execute_chat, protocol, request, writer, headers=hdr_map
    )
    if wire_zc:
        record_v2_turn_completion(
            driver, handler, model=ctx.model, effort=ctx.effort, has_sse=sse_writer is not None
        )
    return make_turn_result(routed.text, routed.reasoning, routed.usage if usage_enabled else None)
