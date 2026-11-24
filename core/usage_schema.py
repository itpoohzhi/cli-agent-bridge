"""Чистые контракты usage-схемы JSONL-лога: поля, алиасы, нормализация записей (0 I/O)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

USAGE_LOG_FIELDS: tuple[str, ...] = (
    "ts", "request_id", "model", "subagent_id", "subagent_role",
    "route", "backend_id", "stream", "http_status", "elapsed_ms",
    "prompt_tokens", "completion_tokens", "total_tokens",
    "cached_tokens", "reasoning_tokens", "usage_present",
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
    return normalized


__all__: tuple[str, ...] = (
    "USAGE_LOG_FIELDS", "USAGE_DB_SOURCE_MAP", "USAGE_FIELD_ALIASES",
    "resolve_usage_log_source_value", "parse_ts_epoch", "normalize_status_code",
    "normalize_elapsed_ms", "compute_uncached_prompt_tokens",
    "normalize_usage_record_aliases",
)
