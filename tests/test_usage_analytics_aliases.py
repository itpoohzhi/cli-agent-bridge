"""Тесты чистой аналитики использования токенов: агрегаты, кэш-хиты, всплески и контракты волны W2."""

from __future__ import annotations

from typing import Any

import core.telemetry_sql
import core.usage_schema
from core import usage_analytics
from core.usage_analytics import (
    aggregate_records,
    compute_cache_hit_pct,
    detect_prompt_anomalies,
    enrich_with_cache_hit,
)


def _record(**overrides: Any) -> dict[str, Any]:
    """Типовая запись usage с переопределениями полей для конкретного теста."""
    base: dict[str, Any] = {
        "ts_iso": "2024-01-15T10:00:00Z",
        "request_id": "req-1",
        "model": "model-a",
        "backend_id": "backend-a",
        "subagent_role": "interactive",
        "status_code": 200,
        "prompt_tokens": 1000,
        "completion_tokens": 200,
        "cached_tokens": 400,
        "reasoning_tokens": 0,
        "total_tokens": 1200,
        "usage_present": True,
    }
    base.update(overrides)
    return base


def test_compute_cache_hit_pct_boundaries() -> None:
    assert compute_cache_hit_pct(400, 1000) == 40.0
    assert compute_cache_hit_pct(0, 0) == 0.0
    assert compute_cache_hit_pct(None, 1000) == 0.0
    assert compute_cache_hit_pct(5000, 1000) == 100.0


def test_enrich_with_cache_hit_adds_computed_fields() -> None:
    rows = enrich_with_cache_hit([{"prompt_tokens": 1000, "cached_tokens": 250}])
    assert rows == [{"prompt_tokens": 1000, "cached_tokens": 250, "cache_hit_pct": 25.0}]
    assert "uncached_prompt_tokens" not in rows[0]
    aggregated = aggregate_records([_record(prompt_tokens=1000, cached_tokens=250)])
    assert aggregated["summary"]["uncached_prompt_tokens"] == 750
    assert aggregated["by_model"][0]["uncached_prompt_tokens"] == 750


def test_aggregate_records_summary_and_buckets() -> None:
    records = [
        _record(),
        _record(model="model-b", prompt_tokens=2000, cached_tokens=0, status_code=500),
    ]
    result = aggregate_records(records)
    summary = result["summary"]
    assert summary["total_requests"] == 2
    assert summary["usage_present_requests"] == 2
    assert summary["ok_requests"] == 1
    assert summary["error_requests"] == 1
    assert summary["prompt_tokens"] == 3000
    assert summary["cached_tokens"] == 400
    assert summary["cache_hit_pct"] == 13.33
    assert {row["model"] for row in result["by_model"]} == {"model-a", "model-b"}
    assert [row["day"] for row in result["by_day"]] == ["2024-01-15"]


def test_aggregate_records_raw_http_status_without_status_code() -> None:
    records: list[dict[str, Any]] = []
    for index in range(3):
        record = _record(request_id=f"req-{index}")
        record.pop("status_code")
        record["http_status"] = 200
        records.append(record)
    summary = aggregate_records(records)["summary"]
    assert summary["ok_requests"] == 3
    assert summary["error_requests"] == 0


def test_aggregate_records_http_status_takes_priority_over_status_code() -> None:
    summary = aggregate_records([_record(http_status=200, status_code=500)])["summary"]
    assert summary["ok_requests"] == 1
    assert summary["error_requests"] == 0


def test_aggregate_records_uncached_prompt_tokens_in_all_buckets() -> None:
    records = [
        _record(prompt_tokens=1000, cached_tokens=400),
        _record(prompt_tokens=500, cached_tokens=100),
    ]
    result = aggregate_records(records)
    assert result["summary"]["uncached_prompt_tokens"] == 1000
    assert [row["uncached_prompt_tokens"] for row in result["by_model"]] == [1000]
    assert [row["uncached_prompt_tokens"] for row in result["by_role"]] == [1000]
    assert [row["uncached_prompt_tokens"] for row in result["by_day"]] == [1000]


def test_aggregate_records_day_from_numeric_epoch() -> None:
    result = aggregate_records([_record(ts_iso=None, ts_epoch=1705276800)])
    assert [row["day"] for row in result["by_day"]] == ["2024-01-15"]


def test_aggregate_records_day_rejects_bool_timestamp() -> None:
    result = aggregate_records([_record(ts_iso=None, ts_epoch=True)])
    assert [row["day"] for row in result["by_day"]] == ["unknown"]


def test_detect_prompt_anomalies_day_spike() -> None:
    by_day = [
        {"day": "2024-01-01", "prompt_tokens": 1_000_000},
        {"day": "2024-01-02", "prompt_tokens": 1_100_000},
        {"day": "2024-01-03", "prompt_tokens": 10_000_000},
    ]
    alerts = detect_prompt_anomalies(by_day, [])
    assert len(alerts) == 1
    assert alerts[0]["scope"] == "day"
    assert alerts[0]["key"] == "2024-01-03"
    assert alerts[0]["reason"] == "day_prompt_spike"


def test_detect_prompt_anomalies_turn_spike() -> None:
    turns = [
        {"model": "model-a", "prompt_tokens": 100_000, "request_id": "r1", "subagent_role": "coder"},
        {"model": "model-a", "prompt_tokens": 110_000, "request_id": "r2", "subagent_role": "coder"},
        {"model": "model-a", "prompt_tokens": 105_000, "request_id": "r3", "subagent_role": "coder"},
        {"model": "model-a", "prompt_tokens": 400_000, "request_id": "r4", "subagent_role": "coder"},
    ]
    alerts = detect_prompt_anomalies([], turns)
    assert len(alerts) == 1
    assert alerts[0]["scope"] == "turn"
    assert alerts[0]["request_id"] == "r4"


def test_usage_analytics_reexports_usage_schema_contracts() -> None:
    assert usage_analytics.compute_uncached_prompt_tokens(1000, 400) == 600
    normalized = usage_analytics.normalize_usage_record_aliases({"http_status": 200, "status_code": 500})
    assert normalized["http_status"] == 200
    assert normalized["status_code"] == 200


def test_telemetry_sql_usage_log_fields_is_usage_schema_constant() -> None:
    assert core.telemetry_sql.USAGE_LOG_FIELDS is core.usage_schema.USAGE_LOG_FIELDS
