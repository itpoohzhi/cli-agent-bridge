"""Чистая нормализация usage: presence-sentinel, Usage, сверка reasoning-токенов (0 I/O)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


class _Omitted:
    """Sentinel отсутствия значения (0/None передаются явно и считаются заданными)."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "OMITTED"


OMITTED: object = _Omitted()


def resolve_usage_presence(*, explicit: bool | None, supplied_values: Sequence[object]) -> bool:
    """Явный флаг доминирует; иначе usage передан, если есть хоть одно не-OMITTED значение."""
    if explicit is not None:
        return bool(explicit)
    return any(not isinstance(value, _Omitted) for value in supplied_values)


@dataclass(frozen=True, init=False)
class Usage:
    """Токены хода: OMITTED-аргументы превращаются в 0/None, usage_present выводится автоматически."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None
    cache_creation_tokens: int | None
    usage_present: bool

    def __init__(
        self,
        input_tokens: object = OMITTED,
        output_tokens: object = OMITTED,
        cache_read_tokens: object = OMITTED,
        cache_creation_tokens: object = OMITTED,
        *,
        usage_present: bool | None = None,
    ) -> None:
        supplied = (input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens)
        present = resolve_usage_presence(explicit=usage_present, supplied_values=supplied)
        object.__setattr__(
            self, "input_tokens", 0 if isinstance(input_tokens, _Omitted) else input_tokens
        )
        object.__setattr__(
            self, "output_tokens", 0 if isinstance(output_tokens, _Omitted) else output_tokens
        )
        object.__setattr__(
            self, "cache_read_tokens",
            None if isinstance(cache_read_tokens, _Omitted) else cache_read_tokens,
        )
        object.__setattr__(
            self, "cache_creation_tokens",
            None if isinstance(cache_creation_tokens, _Omitted) else cache_creation_tokens,
        )
        object.__setattr__(self, "usage_present", present)


@dataclass(frozen=True, slots=True)
class ReconciledTurnUsage:
    """Сверенные токены хода: relation фиксирует, входит ли reasoning в completion."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    reasoning_tokens: int | None
    reasoning_inconsistent: bool
    relation: str


def _sanitize_count(value: object) -> int:
    """Неотрицательный int; bool, мусор, отрицательные и не-конечные значения -> 0."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value)) if math.isfinite(value) else 0
    return 0


def reconcile_turn_usage(
    *, raw_input: object, raw_output: object, raw_total: object, raw_thinking: object
) -> ReconciledTurnUsage:
    """Сверяет input/output/total/thinking в строгом порядке; reasoning без clamp (NO CLAMP)."""
    in_t = _sanitize_count(raw_input)
    out_t = _sanitize_count(raw_output)
    total = _sanitize_count(raw_total)
    think_t = _sanitize_count(raw_thinking)
    if total > 0 and in_t + out_t == total:
        completion, final_total, relation = out_t, total, "output_includes_reasoning"
    elif total > 0 and think_t > 0 and in_t + out_t + think_t == total:
        completion, final_total, relation = out_t + think_t, total, "output_excludes_reasoning"
    else:
        completion, final_total, relation = out_t, in_t + out_t, "ambiguous"
    if think_t == 0:
        reasoning_tokens, inconsistent = None, False
    elif think_t <= completion:
        reasoning_tokens, inconsistent = think_t, False
    else:
        reasoning_tokens, inconsistent = None, True
    return ReconciledTurnUsage(
        prompt_tokens=in_t,
        completion_tokens=completion,
        total_tokens=final_total,
        reasoning_tokens=reasoning_tokens,
        reasoning_inconsistent=inconsistent,
        relation=relation,
    )


__all__: tuple[str, ...] = (
    "OMITTED", "Usage", "ReconciledTurnUsage",
    "resolve_usage_presence", "reconcile_turn_usage",
)
