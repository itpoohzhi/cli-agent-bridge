"""Чистые контракты usage-схемы JSONL-лога: поля, алиасы, нормализация записей (0 I/O)."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

USAGE_LOG_FIELDS: tuple[str, ...] = (
    "ts", "request_id", "model", "subagent_id", "subagent_role",
    "route", "backend_id", "stream", "http_status", "elapsed_ms",
    "prompt_tokens", "completion_tokens", "total_tokens",
    "cached_tokens", "reasoning_tokens", "usage_present",
)

USAGE_LOG_V2_OPTIONAL_FIELDS: tuple[str, ...] = (
    "session_mode", "review_profile", "uncached_prompt_tokens", "cache_eligible",
    "transport_kind", "usage_validity", "pck_digest",
)

USAGE_DB_SOURCE_MAP: dict[str, str] = {
    "ts": "ts_iso", "route": "route_mode",
    "http_status": "status_code", "elapsed_ms": "total_ms",
}

USAGE_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "ts": ("ts_epoch", "ts_iso", "ts"),
    "route": ("route", "route_mode"),
    "http_status": ("http_status", "status_code"),
    "elapsed_ms": ("elapsed_ms", "total_ms"),
}


def resolve_usage_log_source_value(row_map: Mapping[str, Any], field: str) -> Any:
    """Значение поля с приоритетом SQL-имени колонки; 0/False сохраняются (проверка is not None)."""
    source = USAGE_DB_SOURCE_MAP.get(field)
    if source is not None and row_map.get(source) is not None:
        return row_map.get(source)
    return row_map.get(field)


def parse_ts_epoch(value: Any) -> float | None:
    """Epoch-секунды из числа или ISO-8601 строки (naive -> UTC); bool и мусор -> None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except OverflowError:
            return None
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    return None


def normalize_status_code(record: Mapping[str, Any]) -> int | None:
    """HTTP-статус: http_status (int, не bool) > status_code (int, не bool) > None."""
    for key in ("http_status", "status_code"):
        value = record.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def normalize_elapsed_ms(record: Mapping[str, Any]) -> float | None:
    """Длительность хода: elapsed_ms > total_ms; конечное число >= 0, не bool; иначе None."""
    for key in ("elapsed_ms", "total_ms"):
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if isinstance(value, float) and not math.isfinite(value):
            continue
        if value >= 0:
            return float(value)
    return None


def _nonneg_int(value: Any) -> int:
    """Неотрицательный int из числа; bool, мусор и не-конечные значения -> 0."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    if isinstance(value, int):
        return max(0, value)
    return max(0, int(value)) if math.isfinite(value) else 0


def compute_uncached_prompt_tokens(prompt_tokens: Any, cached_tokens: Any) -> int:
    """max(0, prompt - cached) с безопасным приведением к int (bool отвергается)."""
    return max(0, _nonneg_int(prompt_tokens) - _nonneg_int(cached_tokens))


def _is_int(value: Any) -> bool:
    """True для int, исключая bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def classify_usage_validity(record: Mapping[str, Any]) -> str:
    """Валидность кэш-счётчиков: missing | invalid_cached_gt_prompt | session_counter_suppressed | valid."""
    prompt = record.get("prompt_tokens")
    cached = record.get("cached_tokens")
    if record.get("usage_present") is False or not _is_int(prompt):
        return "missing"
    if _is_int(cached) and (cached < 0 or prompt < 0 or cached > prompt):
        return "invalid_cached_gt_prompt"
    if record.get("usage_scope") == "session_counter":
        return "session_counter_suppressed"
    return "valid"


def is_cache_eligible(prompt_tokens: Any, min_tokens: int = 1024) -> bool:
    """True только для int (не bool) prompt_tokens >= min_tokens."""
    return _is_int(prompt_tokens) and prompt_tokens >= min_tokens


def compute_cache_hit_pct_strict(cached_tokens: int | None, prompt_tokens: int | None) -> float | None:
    """Строгая доля кэша: None при отсутствии счётчика или битом usage (cached > prompt), без кламп до 100."""
    if prompt_tokens is None or cached_tokens is None:
        return None
    if prompt_tokens <= 0 or cached_tokens < 0 or cached_tokens > prompt_tokens:
        return None
    return round(100.0 * cached_tokens / prompt_tokens, 2)


def eligible_cache_stats(records: Iterable[Mapping[str, Any]]) -> tuple[int, int, int]:
    """(invalid_usage_requests, eligible_cached, eligible_prompt) только по валидным измеренным строкам."""
    invalid = eligible_cached = eligible_prompt = 0
    for rec in records:
        validity = classify_usage_validity(rec)
        invalid += int(validity == "invalid_cached_gt_prompt")
        cached, prompt = rec.get("cached_tokens"), rec.get("prompt_tokens")
        if validity != "valid" or not _is_int(cached) or not is_cache_eligible(prompt):
            continue
        if 0 <= cached <= prompt:
            eligible_cached += cached
            eligible_prompt += prompt
    return invalid, eligible_cached, eligible_prompt


def normalize_usage_record_aliases(record: Mapping[str, Any]) -> dict[str, Any]:
    """Копия записи с согласованными алиасами статуса/длительности, ts_epoch и uncached-токенами."""
    normalized = dict(record)
    status = normalize_status_code(record)
    normalized["http_status"] = status
    normalized["status_code"] = status
    elapsed = normalize_elapsed_ms(record)
    normalized["elapsed_ms"] = elapsed
    normalized["total_ms"] = elapsed
    ts_epoch: float | None = None
    for alias in USAGE_FIELD_ALIASES["ts"]:
        ts_epoch = parse_ts_epoch(record.get(alias))
        if ts_epoch is not None:
            break
    normalized["ts_epoch"] = ts_epoch
    normalized["uncached_prompt_tokens"] = compute_uncached_prompt_tokens(
        record.get("prompt_tokens"), record.get("cached_tokens")
    )
    normalized["usage_validity"] = classify_usage_validity(record)
    normalized["cache_eligible"] = is_cache_eligible(record.get("prompt_tokens"))
    return normalized


__all__: tuple[str, ...] = (
    "USAGE_LOG_FIELDS", "USAGE_LOG_V2_OPTIONAL_FIELDS", "USAGE_DB_SOURCE_MAP", "USAGE_FIELD_ALIASES",
    "resolve_usage_log_source_value", "parse_ts_epoch", "normalize_status_code",
    "normalize_elapsed_ms", "compute_uncached_prompt_tokens",
    "normalize_usage_record_aliases", "classify_usage_validity", "is_cache_eligible",
    "compute_cache_hit_pct_strict", "eligible_cache_stats",
)
