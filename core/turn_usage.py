"""Vendor-agnostic per-turn token usage domain contract (pure, 0 I/O)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Final

INT64_MAX: Final[int] = (1 << 63) - 1


class UsageScope(str, Enum):
    """Granularity of a raw vendor usage frame."""

    TURN_SNAPSHOT = "turn_snapshot"
    SESSION_COUNTER = "session_counter"


@dataclass(frozen=True, slots=True)
class UsageUpdate:
    """Raw normalized-key usage frame emitted by a protocol driver."""

    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    reasoning_tokens: int | None = None
    reported_total_tokens: int | None = None
    input_includes_cache: bool = True
    output_includes_reasoning: bool = True
    source: str = ""
    scope: UsageScope = UsageScope.TURN_SNAPSHOT
    rejection_reason: str | None = None


@dataclass(frozen=True, slots=True)
class TurnUsage:
    """Validated canonical per-turn usage (OpenAI inclusive semantics)."""

    prompt_tokens: int
    completion_tokens: int
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    reasoning_tokens: int | None = None
    source: str = ""

    @property
    def total_tokens(self) -> int:
        """Total tokens derived strictly from canonical prompt + completion."""
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class NormalizeResult:
    """Tagged outcome of normalizing one UsageUpdate; never both set or both None."""

    usage: TurnUsage | None
    reason: str | None
    advisory: str | None = None

    def __post_init__(self) -> None:
        if (self.usage is None) == (self.reason is None):
            raise ValueError("NormalizeResult requires exactly one of usage or reason")


def _validate_counter(value: object) -> str | None:
    if type(value) is not int:
        return "invalid_counter_type"
    if value < 0:
        return "negative_counter"
    if value > INT64_MAX:
        return "counter_overflow"
    return None


def _validate_optional(value: object) -> str | None:
    return None if value is None else _validate_counter(value)


def _check_all_counters(update: UsageUpdate) -> str | None:
    if update.input_tokens is None or update.output_tokens is None:
        return "missing_required_counters"
    for req in (update.input_tokens, update.output_tokens):
        if (err := _validate_counter(req)) is not None:
            return err
    for opt in (
        update.cache_read_tokens,
        update.cache_creation_tokens,
        update.reasoning_tokens,
    ):
        if (err := _validate_optional(opt)) is not None:
            return err
    return None


def _compute_prompt_tokens(update: UsageUpdate) -> int | str:
    assert update.input_tokens is not None
    cache_sum = (update.cache_read_tokens or 0) + (update.cache_creation_tokens or 0)
    if cache_sum > INT64_MAX:
        return "counter_overflow"
    if update.input_includes_cache:
        return "cache_exceeds_prompt" if cache_sum > update.input_tokens else update.input_tokens
    prompt = update.input_tokens + cache_sum
    return "counter_overflow" if prompt > INT64_MAX else prompt


def _compute_completion_tokens(update: UsageUpdate) -> int | str:
    assert update.output_tokens is not None
    reasoning = update.reasoning_tokens
    if update.output_includes_reasoning:
        if reasoning is not None and reasoning > update.output_tokens:
            return "reasoning_exceeds_completion"
        return update.output_tokens
    completion = update.output_tokens + (reasoning or 0)
    return "counter_overflow" if completion > INT64_MAX else completion


def _compute_totals(update: UsageUpdate) -> tuple[int, int] | str:
    prompt = _compute_prompt_tokens(update)
    if isinstance(prompt, str):
        return prompt
    completion = _compute_completion_tokens(update)
    if isinstance(completion, str):
        return completion
    if prompt + completion > INT64_MAX:
        return "total_overflow"
    return prompt, completion


def _soften_cache_creation(update: UsageUpdate) -> UsageUpdate | None:
    """Drop only an over-reported cache_creation when cache_read itself is valid."""
    if not update.input_includes_cache or update.cache_creation_tokens is None or update.input_tokens is None:
        return None
    read = update.cache_read_tokens or 0
    if read > update.input_tokens or read + update.cache_creation_tokens <= update.input_tokens:
        return None
    return replace(update, cache_creation_tokens=None)


def normalize_usage_update(update: UsageUpdate) -> NormalizeResult:
    """Validate and normalize a raw UsageUpdate into canonical TurnUsage."""
    if update.rejection_reason:
        return NormalizeResult(None, update.rejection_reason)
    if update.scope is UsageScope.SESSION_COUNTER:
        return NormalizeResult(None, "session_counter_not_exportable")
    if (err := _check_all_counters(update)) is not None:
        return NormalizeResult(None, err)
    softened = _soften_cache_creation(update)
    update = softened or update
    totals = _compute_totals(update)
    if isinstance(totals, str):
        return NormalizeResult(None, totals)
    prompt, completion = totals
    reported = update.reported_total_tokens
    advisory = (
        "usage_total_mismatch"
        if type(reported) is int and reported != prompt + completion
        else ("cache_creation_dropped" if softened else None)
    )
    return NormalizeResult(
        TurnUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            cache_read_tokens=update.cache_read_tokens,
            cache_creation_tokens=update.cache_creation_tokens,
            reasoning_tokens=update.reasoning_tokens,
            source=update.source,
        ),
        None,
        advisory,
    )
