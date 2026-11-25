"""Чистые контракты usage-полей: нормализация, reasoning-токены, конвертации для ходов и телеметрии (0 I/O)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.telemetry_util import first, present
from core.usage_event_fields import (  # noqa: F401
    _COUNTER_KEYS,
    _SOURCE_PAIRS,
    VALID_USAGE_MISSING_REASONS,
    VALID_USAGE_SOURCES,
    _absent_reason,
    _is_counter,
    _is_number,
    _is_positive,
    _mark_usage_absent,
    _resolve_missing_reason,
    _resolve_usage_source,
    _total_tokens,
    finalize_event_usage,
)

_PRESENCE_KEYS: tuple[str, ...] = (
    "input_tokens",
    "prompt_tokens",
    "output_tokens",
    "completion_tokens",
    "cache_read_tokens",
    "cache_read_input_tokens",
    "cached_tokens",
    "reasoning_tokens",
    "total_tokens",
)
_TURN_USAGE_FIELDS: tuple[tuple[str, str], ...] = (
    ("input_tokens", "prompt_tokens"),
    ("output_tokens", "completion_tokens"),
    ("cache_read_tokens", "cache_read_tokens"),
    ("reasoning_tokens", "reasoning_tokens"),
)


def _nested(raw: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Вложенный mapping из usage по ключу; отсутствие или не-mapping дают пустой словарь."""
    value = raw.get(key)
    return value if isinstance(value, Mapping) else {}


def _extract_raw_counters(raw: Mapping[str, Any]) -> tuple[Any, Any, Any, Any, Any]:
    prompt = first(raw.get("input_tokens"), raw.get("prompt_tokens"))
    completion = first(raw.get("output_tokens"), raw.get("completion_tokens"))
    cached = first(
        raw.get("cache_read_tokens"),
        raw.get("cache_read_input_tokens"),
        raw.get("cached_tokens"),
        _nested(raw, "prompt_tokens_details").get("cached_tokens"),
    )
    reasoning = extract_reasoning_tokens(raw)
    return prompt, completion, cached, reasoning, raw.get("total_tokens")


def _usage_present(raw: Mapping[str, Any]) -> bool:
    """Usage реально передан: явный False доминирует; иначе требуется хотя бы один положительный счётчик."""
    if raw.get("usage_present") is False:
        return False
    return any(_is_positive(value) for value in _extract_raw_counters(raw))


def extract_reasoning_tokens(raw: Mapping[str, Any]) -> int | None:
    """reasoning_tokens из usage: прямой ключ, completion_tokens_details или output_tokens_details."""
    sources = (raw, _nested(raw, "completion_tokens_details"), _nested(raw, "output_tokens_details"))
    for source in sources:
        value = source.get("reasoning_tokens")
        if _is_counter(value):
            return value
    return None


def normalize_usage_fields(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Плоские нормализованные поля usage: input/output/cache_read/reasoning + usage_present (None -> все None)."""
    if raw is None:
        return {
            "input_tokens": None, "output_tokens": None, "cache_read_tokens": None,
            "reasoning_tokens": None, "usage_present": None,
            "usage_source": None, "usage_missing_reason": None,
        }
    counters = _extract_raw_counters(raw)
    prompt, completion, cached, reasoning, total = counters
    has_positive = any(_is_positive(value) for value in counters)
    explicit_false = raw.get("usage_present") is False
    if explicit_false or not has_positive:
        has_zero_num = any(_is_number(value) for value in counters) and not has_positive
        reason = _absent_reason(raw.get("usage_missing_reason"), has_zero_num, explicit_false)
        return {
            "input_tokens": None, "output_tokens": None, "cache_read_tokens": None,
            "reasoning_tokens": None, "usage_present": False,
            "usage_source": None, "usage_missing_reason": reason,
        }
    source = _resolve_usage_source(raw.get("usage_source")) or _resolve_usage_source(raw.get("source")) or "upstream_report"
    return {
        "input_tokens": prompt, "output_tokens": completion, "cache_read_tokens": cached,
        "reasoning_tokens": reasoning, "usage_present": True,
        "usage_source": source, "usage_missing_reason": None,
    }


def _merge_turn_usage_fields(enriched: dict[str, Any], turn_usage: Any) -> None:
    if turn_usage is None:
        return
    for key, attr in _TURN_USAGE_FIELDS:
        value = getattr(turn_usage, attr, None)
        if value is not None:
            enriched[key] = value


def _resolve_turn_source(enriched: Mapping[str, Any], turn_usage: Any) -> str:
    source = _resolve_usage_source(enriched.get("usage_source"))
    if source is not None:
        return source
    return _resolve_usage_source(getattr(turn_usage, "source", None)) or "upstream_report"


def enrich_turn_usage_dict(base_usage: Mapping[str, Any], turn_usage: Any) -> dict[str, Any]:
    """Копия базового usage хода, дополненная полями TurnUsage (None не перезаписывает базу); без воскрешения нулей."""
    enriched = dict(base_usage)
    _merge_turn_usage_fields(enriched, turn_usage)
    counters = tuple(enriched.get(key) for key in _COUNTER_KEYS)
    has_positive = any(_is_positive(value) for value in counters)
    explicit_false = turn_usage is None and enriched.get("usage_present") is False
    if explicit_false or not has_positive:
        return _mark_usage_absent(enriched, counters, has_positive, explicit_false)
    enriched["usage_present"] = True
    enriched["usage_source"] = _resolve_turn_source(enriched, turn_usage)
    enriched["usage_missing_reason"] = None
    return enriched


def telemetry_usage_updates(usage: Mapping[str, Any] | None) -> dict[str, Any]:
    """Поля usage -> метаданные телеметрии события: prompt/completion/cached/reasoning + usage_present."""
    if usage is None:
        return {"usage_present": False, "usage_source": None, "usage_missing_reason": "usage_missing_in_stream"}
    fields = normalize_usage_fields(usage)
    updates = present({
        "prompt_tokens": fields["input_tokens"], "completion_tokens": fields["output_tokens"],
        "cached_tokens": fields["cache_read_tokens"], "reasoning_tokens": fields["reasoning_tokens"],
    })
    reported_total = usage.get("total_tokens")
    if fields["usage_present"] and _is_counter(reported_total) and reported_total > 0:
        updates["total_tokens"] = reported_total
    updates["usage_present"] = bool(fields["usage_present"])
    updates["usage_source"] = fields["usage_source"]
    updates["usage_missing_reason"] = fields["usage_missing_reason"]
    return updates
