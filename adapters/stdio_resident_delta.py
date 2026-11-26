"""Stream delta formatting and turn execution helpers for StdioResidentAdapter."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator, Mapping
from functools import partial
from typing import Any, cast

from adapters.stdio_resident_runtime import DEFAULT_HEARTBEAT_S, build_turn_request_from_ctx
from core.backend_adapter import StreamSink, TurnContext, TurnResult
from core.resident_canonical import thaw_frozen_value
from core.runtime_env import stdio_usage_contract_enabled
from core.stdio_resident.codex_attestation_wire import (
    record_v2_turn_completion,
    should_wire_v2_zero_canon,
    wrap_v2_sse_writer,
)
from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.runtime_types import ResourceLimitError
from core.stdio_resident.tool_turn_outcome import LiveToolStreamBridge
from core.stdio_resident.turn_stream import AssembledStreamDelta, TurnStreamAssembler
from core.stdio_resident.zero_canon_router import execute_routed_turn_result
from core.subbridge_zero_canon import review_profile_from_headers
from core.turn_usage import TurnUsage
from core.turn_usage_result import make_turn_result
from core.usage_wire import build_turn_wire_usage

logger = logging.getLogger(__name__)
_BRIDGE_STREAM_KINDS = frozenset({"content", "reasoning"})


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


def _build_turn_request(adapter_id: str, ctx: TurnContext, profile: str) -> dict[str, Any]:
    return build_turn_request_from_ctx(adapter_id, ctx, profile)


def _build_tool_stream_bridge(ctx: TurnContext, base_writer: StreamSink | None) -> LiveToolStreamBridge:
    raw_schemas = thaw_frozen_value(getattr(ctx, "tool_schemas", None))
    schemas = cast(Mapping[str, object], raw_schemas) if isinstance(raw_schemas, Mapping) else None
    return LiveToolStreamBridge(
        emulate_tools=bool(ctx.emulate_tools),
        sse_writer=base_writer,
        tool_schemas=schemas,
        tool_choice=thaw_frozen_value(getattr(ctx, "tool_choice", None)),
    )


def _wrap_bridge_sse_writer(
    bridge: LiveToolStreamBridge, base_writer: StreamSink | None, max_bytes: int, close_stream: Callable[[], None], keepalive: Callable[[], bool] | None = None
) -> StreamSink:
    limit = max(1024, int(max_bytes if max_bytes else 4194304))
    accumulated = 0
    last_hb = time.monotonic()

    def write(kind: str, val: str) -> bool:
        nonlocal accumulated, last_hb
        norm_kind = "reasoning" if kind == "reasoning_content" else kind
        if norm_kind not in _BRIDGE_STREAM_KINDS:
            return bool(base_writer(kind, val)) if base_writer is not None else True
        accumulated += len(val.encode("utf-8"))
        if accumulated > limit:
            close_stream()
            raise ResourceLimitError("output_limit_exceeded")
        now = time.monotonic()
        if keepalive is not None and now - last_hb >= DEFAULT_HEARTBEAT_S:
            _ = keepalive()
            last_hb = now
        return bridge.on_sse_event(norm_kind, val)

    return cast(StreamSink, write)


def _emulate_tools_setup(
    adapter: Any, ctx: TurnContext, writer: StreamSink | None, *, bridge: LiveToolStreamBridge | None = None
) -> tuple[StreamSink | None, Callable[[str], None] | None, Callable[[], bool] | None]:
    handler = getattr(ctx, "handler", None)

    def _close_stream() -> None:
        if handler:
            setattr(handler, "close_connection", True)

    def _keepalive() -> bool:
        output = getattr(handler, "wfile", None)
        if output:
            output.write(b": keepalive\n\n")
            output.flush()
        return bool(output)

    raw_cap = adapter._config.max_turn_output_bytes
    max_bytes = max(1024, int(raw_cap if raw_cap else 4194304))
    ka = _keepalive if handler else None
    validator = getattr(ctx, "terminal_validator", None)
    if ctx.emulate_tools:
        active_bridge = bridge if bridge is not None else _build_tool_stream_bridge(ctx, writer)
        return _wrap_bridge_sse_writer(active_bridge, writer, max_bytes, _close_stream, ka), validator, ka
    return writer, validator, None


def _attach_committed_slot_sink(request: dict[str, Any]) -> list[tuple[str, Any]]:
    committed_slots: list[tuple[str, Any]] = []
    if isinstance(turn_ctx := request.get("turn_context"), dict):
        turn_ctx["_committed_slot_sink"] = committed_slots
    return committed_slots


def _finalize_routed_result(
    routed: Any, bridge: LiveToolStreamBridge | None, usage_enabled: bool
) -> tuple[TurnResult, LiveToolStreamBridge | None]:
    usage = routed.usage if usage_enabled else None
    active = bridge if bridge is not None else (LiveToolStreamBridge(emulate_tools=False, sse_writer=None) if routed.tool_calls else None)
    if active is None:
        return make_turn_result(routed.text, routed.reasoning, usage), None
    return active.finalize(raw_text=routed.text, raw_reasoning=routed.reasoning, usage=usage, structural_calls=routed.tool_calls), active


def _rebind_tool_turn_slot(
    adapter: Any, request: Mapping[str, Any], committed_slots: list[tuple[str, Any]], bridge: LiveToolStreamBridge | None, result: TurnResult
) -> None:
    if bridge is None or not result.tool_calls:
        return
    slot_ref = committed_slots[-1] if committed_slots else request.get("_committed_slot")
    if not (isinstance(slot_ref, tuple) and len(slot_ref) == 2):
        return
    runtime = getattr(adapter, "_runtime", None)
    rebind = getattr(runtime, "rebind_assistant_item", None) or getattr(adapter, "rebind_assistant_item", None)
    item = bridge.committed_assistant_item(result)
    if callable(rebind) and item is not None:
        ok = bool(rebind(slot_ref[0], slot_ref[1], item))
        if not ok:
            logger.debug("resident_rebind_assistant_item_skipped: slot_mismatch")


def _attach_p12_resident_cancel(request: dict[str, Any], ctx: TurnContext) -> None:
    """OPEN-16: wire TurnContext.cancel_event and register_pgid when flag #5 is on."""
    from core.p12_hub_cancel_seam import get_hub_p12_seam
    if not get_hub_p12_seam().resident_wiring_enabled():
        return
    if ctx.cancel_event is not None and "_cancel_event" not in request:
        request["_cancel_event"] = ctx.cancel_event
    if ctx.register_pgid is not None:
        tctx = request.get("turn_context")
        if tctx is None:
            tctx = {}
            request["turn_context"] = tctx
        if isinstance(tctx, dict):
            tctx.setdefault("_register_pgid", ctx.register_pgid)


def execute_stdio_turn(adapter: Any, protocol: str, ctx: TurnContext, sse_writer: StreamSink | None) -> TurnResult:
    """Run one StdioResidentAdapter turn with turn-boundary kill-switch and typed TurnUsage."""
    usage_enabled = stdio_usage_contract_enabled()
    handler = getattr(ctx, "handler", None)
    raw_headers = getattr(handler, "headers", None)
    profile = review_profile_from_headers(raw_headers)
    request = _build_turn_request(adapter.id, ctx, profile)
    _attach_p12_resident_cancel(request, ctx)
    request["_usage_enabled"] = usage_enabled
    committed_slots = _attach_committed_slot_sink(request)
    hdr_map = dict(raw_headers.items()) if hasattr(raw_headers, "items") else None
    driver = getattr(adapter, "_driver", None)
    wire_zc = should_wire_v2_zero_canon(protocol, profile, handler)
    base_writer = wrap_v2_sse_writer(sse_writer, driver, handler, ctx.model, ctx.effort) if wire_zc else sse_writer
    bridge = _build_tool_stream_bridge(ctx, base_writer) if ctx.emulate_tools else None
    routed_writer, validator, keepalive = _emulate_tools_setup(adapter, ctx, base_writer, bridge=bridge)
    if validator:
        request["_terminal_validator"] = validator
    if keepalive:
        request["_keepalive"] = keepalive
    execute_chat = partial(adapter.execute_chat, trusted_owner_hash=ctx.owner_hash, trusted_identity=getattr(ctx, "resident_identity", None))
    routed = execute_routed_turn_result(execute_chat, protocol, request, routed_writer, headers=hdr_map)
    if wire_zc:
        record_v2_turn_completion(driver, handler, model=ctx.model, effort=ctx.effort, has_sse=bool(sse_writer))
    result, active_bridge = _finalize_routed_result(routed, bridge, usage_enabled)
    _rebind_tool_turn_slot(adapter, request, committed_slots, active_bridge, result)
    return result
