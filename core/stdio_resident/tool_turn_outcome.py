"""Outcome normalization and live SSE bridging for stdio-resident tool turns."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
import hashlib
import json
import secrets
from typing import cast

from core.backend_routing_models import (
    ToolCall,
    ToolFunction,
    TranscriptItem,
    TurnEvent,
    TurnResult,
)
from core.resident_history import build_assistant_transcript_item
from core.tool_emulation import StreamNormalizer
from core.tool_emulation import sanitize_tool_call  # pyright: ignore[reportUnknownVariableType]
from core.tool_mode import NormalizerModeSpec, NormalizerSinks, ToolMode, resolve_tool_mode
from core.turn_usage import TurnUsage
from core.turn_usage_result import make_turn_result


def mint_turn_call_id(turn_seed: str, index: int) -> str:
    """Mint deterministic OpenAI-style call_<24 hex> identifier for a turn call."""
    digest = hashlib.sha256(f"{turn_seed}:{index}".encode("utf-8")).hexdigest()[:24]
    return f"call_{digest}"


def _serialize_arguments(raw_args: object) -> str:
    if isinstance(raw_args, str):
        return raw_args
    return json.dumps({} if raw_args is None else raw_args, ensure_ascii=False)


def tool_call_to_dict(call: ToolCall | Mapping[str, object]) -> dict[str, object]:
    """Normalize a ToolCall or mapping into a canonical OpenAI function-call dict."""
    if isinstance(call, ToolCall):
        return {
            "id": call.id,
            "type": "function",
            "function": {"name": call.function.name, "arguments": call.function.arguments},
        }
    fn_raw = call.get("function")
    fn: Mapping[str, object] = cast(Mapping[str, object], fn_raw) if isinstance(fn_raw, Mapping) else {}
    raw_args = fn.get("arguments")
    if raw_args is None and "arguments" in call:
        raw_args = call.get("arguments")
    return {
        "id": str(call.get("id") or ""),
        "type": "function",
        "function": {
            "name": str(fn.get("name") or call.get("name") or ""),
            "arguments": _serialize_arguments(raw_args),
        },
    }


def build_committed_assistant_item(
    text: str,
    tool_calls: Sequence[ToolCall | Mapping[str, object]] | None = None,
) -> TranscriptItem | None:
    """Build a TranscriptItem representing the final committed assistant turn."""
    calls = [tool_call_to_dict(call) for call in (tool_calls or ())]
    return build_assistant_transcript_item(text, calls)


class LiveToolStreamBridge:
    """Single owner of live tool/text stream normalization and final turn outcome."""

    def __init__(
        self,
        *,
        emulate_tools: bool,
        sse_writer: Callable[[str, str], object] | None,
        tool_schemas: Mapping[str, object] | None = None,
        tool_choice: object = None,
        turn_seed: str | None = None,
    ) -> None:
        self._structural_calls: list[dict[str, object]] = []
        self._turn_seed: str = turn_seed or secrets.token_hex(16)
        self._emitted_content: list[str] = []
        self._emitted_reasoning: list[str] = []
        self._writer: Callable[[str, str], object] | None = sse_writer
        self._tool_schemas: dict[str, object] | None = dict(tool_schemas) if tool_schemas else None
        self._normalizer: StreamNormalizer | None = None
        if emulate_tools:
            mode = resolve_tool_mode(tool_schemas or {"_": {}}, tool_choice)
            if mode is ToolMode.OFF:
                mode = ToolMode.EMULATE
            self._normalizer = StreamNormalizer.for_mode(
                NormalizerModeSpec(mode),
                sinks=NormalizerSinks(on_content=self._emit_content, on_reasoning=self._emit_reasoning),
                strict_live=True,
                tool_schemas=self._tool_schemas,
            )

    def _emit_content(self, text: str) -> None:
        if not text:
            return
        self._emitted_content.append(text)
        if self._writer is not None:
            _ = self._writer("content", text)

    def _emit_reasoning(self, text: str) -> None:
        if not text:
            return
        self._emitted_reasoning.append(text)
        if self._writer is not None:
            _ = self._writer("reasoning", text)

    def on_sse_event(self, kind: str, chunk: str) -> bool:
        """Route a live SSE reasoning/content chunk through the active normalizer."""
        if not chunk:
            return True
        if kind == "reasoning":
            if self._normalizer is not None:
                self._normalizer.feed_thinking(chunk)
            else:
                self._emit_reasoning(chunk)
        elif kind == "content":
            if self._normalizer is not None:
                self._normalizer.feed_text(chunk)
            else:
                self._emit_content(chunk)
        return True

    def on_delta_tool_calls(self, tool_calls: Sequence[Mapping[str, object]]) -> None:
        """Record structural tool-call deltas emitted during the live turn."""
        for call in tool_calls:
            self._structural_calls.append(dict(call))

    def _flush_normalizer(self) -> None:
        if self._normalizer is None:
            return
        if self._structural_calls:
            pending = cast(list[object] | None, getattr(self._normalizer, "_pending_content", None))
            if isinstance(pending, list) and pending:
                preamble = "".join(str(piece) for piece in pending)
                if preamble.strip():
                    self._emit_reasoning(preamble)
            self._normalizer.suppress_tail()
            return
        self._normalizer.finish()

    def _normalize_calls(self) -> list[ToolCall]:
        raw_calls: Sequence[Mapping[str, object]]
        if self._structural_calls:
            raw_calls = self._structural_calls
        elif self._normalizer is not None:
            raw_calls = cast(Sequence[Mapping[str, object]], self._normalizer.tool_calls)
        else:
            raw_calls = ()
        final_calls: list[ToolCall] = []
        seen_ids: set[str] = set()
        for raw_idx, raw_call in enumerate(raw_calls):
            norm = tool_call_to_dict(raw_call)
            fn = cast(Mapping[str, object], norm["function"])
            name = str(fn["name"])
            if not name.strip():
                continue
            entry = ToolCall(
                index=raw_idx,
                id=mint_turn_call_id(self._turn_seed, raw_idx),
                function=ToolFunction(name=name, arguments=str(fn["arguments"])),
            )
            sanitized = cast(list[ToolCall], sanitize_tool_call(entry, self._tool_schemas)) if self._tool_schemas else [entry]
            for item in sanitized:
                out_idx = len(final_calls)
                call_id = (
                    item.id
                    if item.id.startswith("call_") and item.id not in seen_ids
                    else mint_turn_call_id(self._turn_seed, out_idx)
                )
                seen_ids.add(call_id)
                final_calls.append(replace(item, index=out_idx, id=call_id))
        return final_calls

    def finalize(
        self,
        *,
        raw_text: str = "",
        raw_reasoning: str = "",
        usage: TurnUsage | None = None,
        structural_calls: Sequence[Mapping[str, object]] | None = None,
    ) -> TurnResult:
        """Finalize stream state, flush remaining content, and build TurnResult."""
        if structural_calls:
            self.on_delta_tool_calls(structural_calls)
        self._flush_normalizer()
        final_calls = self._normalize_calls()
        final_reasoning = "".join(self._emitted_reasoning) or raw_reasoning
        final_text = "" if final_calls else ("".join(self._emitted_content) or raw_text)
        events: list[TurnEvent] = []
        if final_reasoning:
            events.append(TurnEvent("reasoning", final_reasoning))
        if final_text and not final_calls:
            events.append(TurnEvent("content", final_text))
        events.extend(TurnEvent("tool_call", tc) for tc in final_calls)
        base = make_turn_result(final_text, final_reasoning, usage)
        return replace(base, tool_calls=tuple(final_calls), events=tuple(events))

    def committed_assistant_item(self, result: TurnResult) -> TranscriptItem | None:
        """Build the final TranscriptItem for resident history rebinding."""
        return build_committed_assistant_item(result.text, result.tool_calls)
