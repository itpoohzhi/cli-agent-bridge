"""Backward-compatible TurnResult subclass carrying canonical TurnUsage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.backend_adapter import TurnResult, Usage
from core.turn_usage import TurnUsage


@dataclass(frozen=True)
class TurnResultWithUsage(TurnResult):
    """TurnResult sidecar preserving canonical TurnUsage across finalize_turn."""

    turn_usage: TurnUsage | None = None


def turn_usage_to_legacy(usage: TurnUsage) -> Usage:
    """Convert inclusive canonical TurnUsage into legacy backend_adapter.Usage."""
    return Usage(
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_creation_tokens=usage.cache_creation_tokens,
    )


def make_turn_result(
    text: str,
    reasoning: str,
    turn_usage: TurnUsage | None = None,
    **kwargs: Any,
) -> TurnResult:
    """Build TurnResultWithUsage when turn_usage is present, else plain TurnResult."""
    if turn_usage is None:
        return TurnResult(text=text, reasoning=reasoning, **kwargs)
    return TurnResultWithUsage(
        text=text,
        reasoning=reasoning,
        usage=turn_usage_to_legacy(turn_usage),
        turn_usage=turn_usage,
        **kwargs,
    )


def turn_usage_of(result: object) -> TurnUsage | None:
    """Extract TurnUsage from a TurnResult-like object if present and typed."""
    value: object = getattr(result, "turn_usage", None)
    return value if isinstance(value, TurnUsage) else None
