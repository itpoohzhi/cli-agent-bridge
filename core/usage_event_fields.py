"""Чистые хелперы event usage, absent-reason и финализации метаданных телеметрии (0 I/O)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeGuard

VALID_USAGE_SOURCES: frozenset[str] = frozenset(
    ("upstream_report", "codex_v2_turn", "codex_v2_session_delta", "codex_legacy")
)
VALID_USAGE_MISSING_REASONS: frozenset[str] = frozenset(
    ("usage_missing_in_stream", "omitted", "broken_stream", "empty_zero_usage")
)
_SOURCE_PAIRS: tuple[tuple[str, str], ...] = (
    ("codex_app_server_v2", "codex_v2_turn"),
    ("codex_app_server", "codex_legacy"),
)
CACHE_CREATION_RAW_KEYS: tuple[str, ...] = (
    "cache_creation_tokens", "cache_creation_input_tokens", "cacheCreationTokens", "cacheWriteTokens",
)
_COUNTER_KEYS: tuple[str, ...] = (
    "input_tokens", "output_tokens", "prompt_tokens", "completion_tokens",
    "cache_read_tokens", "cached_tokens", "cache_creation_tokens",
    "reasoning_tokens", "total_tokens",
)


def _is_counter(value: Any) -> TypeGuard[int]:
    """Целочисленный неотрицательный счётчик токенов: int без bool и без отрицательных значений."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_number(value: Any) -> TypeGuard[int | float]:
    """Числовое поле usage для признака usage_present: int/float, но не bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive(value: Any) -> bool:
    return _is_number(value) and value > 0


def _cache_creation_sources(raw: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """Собрать допустимые контейнеры поиска cache_creation: корень, вложенный usage и prompt_tokens_details."""
    sources: list[Mapping[str, Any]] = [raw]
    for parent in (raw, raw.get("usage")):
        if not isinstance(parent, Mapping):
            continue
        if parent is not raw:
            sources.append(parent)
        details = parent.get("prompt_tokens_details")
        if isinstance(details, Mapping):
            sources.append(details)
    return tuple(sources)


def extract_cache_creation(raw: Mapping[str, Any]) -> int | None:
    """cache_creation_tokens из usage (корень, вложенный usage или prompt_tokens_details); нет счётчика — None."""
    for source in _cache_creation_sources(raw):
        for key in CACHE_CREATION_RAW_KEYS:
            value = source.get(key)
            if _is_counter(value):
                return value
    return None


def _resolve_usage_source(raw_source: Any) -> str | None:
    if isinstance(raw_source, str):
        if raw_source in VALID_USAGE_SOURCES:
            return raw_source
        return next((dst for src_k, dst in _SOURCE_PAIRS if raw_source == src_k), None)
    return None


def _resolve_missing_reason(raw_reason: Any) -> str | None:
    return raw_reason if isinstance(raw_reason, str) and raw_reason in VALID_USAGE_MISSING_REASONS else None


def _absent_reason(raw_reason: Any, has_zero_num: bool, explicit_false: bool) -> str:
    if (reason := _resolve_missing_reason(raw_reason)) is not None:
        return reason
    if has_zero_num:
        return "empty_zero_usage"
    return "omitted" if explicit_false else "usage_missing_in_stream"


def _mark_usage_absent(
    enriched: dict[str, Any],
    counters: tuple[Any, ...],
    has_positive: bool,
    explicit_false: bool,
) -> dict[str, Any]:
    for key in _COUNTER_KEYS:
        if key in enriched:
            enriched[key] = None
    has_zero_num = not has_positive and any(_is_number(value) for value in counters)
    enriched["usage_present"] = False
    enriched["usage_source"] = None
    enriched["usage_missing_reason"] = _absent_reason(enriched.get("usage_missing_reason"), has_zero_num, explicit_false)
    return enriched


def _total_tokens(prompt: Any, completion: Any, reported_total: Any = None) -> int | None:
    """total_tokens: положительный reported_total или prompt + completion при положительной сумме; иначе None."""
    if _is_counter(reported_total) and reported_total > 0:
        return reported_total
    if not (_is_number(prompt) or _is_number(completion)):
        return None
    total = (int(prompt) if _is_number(prompt) else 0) + (int(completion) if _is_number(completion) else 0)
    return total if total > 0 else None


def finalize_event_usage(meta: dict[str, Any]) -> dict[str, Any]:
    """Блок usage события: pop полей из meta, total_tokens и вывод usage_present по положительным токенам."""
    prompt = meta.pop("prompt_tokens", None)
    completion = meta.pop("completion_tokens", None)
    cached = meta.pop("cached_tokens", None)
    reasoning = meta.pop("reasoning_tokens", None)
    cache_creation = meta.pop("cache_creation_tokens", None)
    reported_total = meta.pop("total_tokens", None)
    explicit_present = meta.pop("usage_present", None)
    raw_source = meta.pop("usage_source", None)
    raw_reason = meta.pop("usage_missing_reason", None)
    total = _total_tokens(prompt, completion, reported_total)
    has_positive = any(_is_positive(value) for value in (prompt, completion, cached, reasoning, cache_creation, total))
    if explicit_present is not False and has_positive:
        return {
            "prompt_tokens": prompt, "completion_tokens": completion, "cached_tokens": cached,
            "reasoning_tokens": reasoning, "cache_creation_tokens": cache_creation,
            "total_tokens": total, "usage_present": True,
            "usage_source": _resolve_usage_source(raw_source) or "upstream_report", "usage_missing_reason": None,
        }
    zero_fields = (prompt, completion, cached, reasoning, cache_creation, reported_total)
    has_zero_num = any(_is_number(value) for value in zero_fields) and not has_positive
    reason = _absent_reason(raw_reason, has_zero_num, explicit_present is False)
    return {
        "prompt_tokens": None, "completion_tokens": None, "cached_tokens": None, "reasoning_tokens": None,
        "cache_creation_tokens": None, "total_tokens": None, "usage_present": False, "usage_source": None, "usage_missing_reason": reason,
    }
