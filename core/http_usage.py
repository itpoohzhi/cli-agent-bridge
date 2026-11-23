"""HTTP JSON/SSE/error usage routing helpers delegating wire format to core.usage_wire."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.turn_usage import TurnUsage
from core.usage_wire import build_turn_wire_usage, positive_wire_usage

LegacyWireFn = Callable[[object, object, object], dict[str, Any]]
CounterFn = Callable[[object], int]


@dataclass(frozen=True, slots=True)
class SseUsageMeta:
    """Metadata envelope for the single final OpenAI SSE usage chunk."""

    completion_id: str
    created: int
    shown_model: str
    finish_reason: str | None


def nonstream_wire_usage(
    out: Mapping[str, Any], legacy_wire_fn: LegacyWireFn
) -> dict[str, Any]:
    """Select canonical TurnUsage wire dict when present, else legacy wire_usage."""
    tu = out.get("turn_usage")
    if isinstance(tu, TurnUsage):
        return build_turn_wire_usage(tu)
    usage = out.get("usage") or {}
    return legacy_wire_fn(
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
        usage.get("cache_read_tokens"),
    )


def sse_usage_chunk(
    out: Mapping[str, Any],
    meta: SseUsageMeta,
    legacy_wire_fn: LegacyWireFn,
) -> str | None:
    """Build single final SSE usage chunk (emits observed TurnUsage even if 0/0; skips absent)."""
    tu = out.get("turn_usage")
    wire: dict[str, Any] | None = None
    if isinstance(tu, TurnUsage):
        wire = build_turn_wire_usage(tu)
    else:
        out_usage = out.get("usage") or {}
        prompt_toks = out_usage.get("input_tokens", 0)
        compl_toks = out_usage.get("output_tokens", 0)
        if prompt_toks or compl_toks:
            wire = legacy_wire_fn(
                prompt_toks, compl_toks, out_usage.get("cache_read_tokens")
            )
    if wire is None:
        return None
    payload = {
        "id": meta.completion_id,
        "object": "chat.completion.chunk",
        "created": meta.created,
        "model": meta.shown_model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": meta.finish_reason}],
        "usage": wire,
    }
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def error_wire_usage(
    out: Mapping[str, Any],
    err_turn_usage: TurnUsage | None = None,
    *,
    legacy_wire_fn: LegacyWireFn,
    counter_fn: CounterFn,
) -> dict[str, Any] | None:
    """Select positive-only wire usage for mid-stream error envelopes."""
    tu = (
        err_turn_usage
        if isinstance(err_turn_usage, TurnUsage)
        else (out.get("turn_usage") if isinstance(out.get("turn_usage"), TurnUsage) else None)
    )
    if tu is not None:
        return positive_wire_usage(build_turn_wire_usage(tu))
    err_usage = out.get("usage") or {}
    try:
        return positive_wire_usage(
            legacy_wire_fn(
                counter_fn(err_usage.get("input_tokens")),
                counter_fn(err_usage.get("output_tokens")),
                counter_fn(err_usage.get("cache_read_tokens")),
            )
        )
    except (TypeError, ValueError, AttributeError):
        return None
