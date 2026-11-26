"""Тесты Wave 5: строгий cache-hit (B-27), классификатор валидности usage и eligible-агрегация."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.usage_analytics import (  # noqa: E402
    aggregate_records,
    compute_cache_hit_pct,
    compute_cache_hit_pct_strict,
)
from core.usage_schema import (  # noqa: E402
    USAGE_LOG_FIELDS,
    USAGE_LOG_V2_OPTIONAL_FIELDS,
    classify_usage_validity,
    is_cache_eligible,
    normalize_usage_record_aliases,
)


def test_b27_strict_cache_hit_invalid_is_none_not_100() -> None:
    """B-27: cached > prompt = invalid (None), cached=None != measured zero."""
    assert compute_cache_hit_pct_strict(5000, 1000) is None
    assert compute_cache_hit_pct_strict(None, 2000) is None
    assert compute_cache_hit_pct_strict(2000, None) is None
    assert compute_cache_hit_pct_strict(0, 2000) == 0.0
    assert compute_cache_hit_pct_strict(1500, 2000) == 75.0
    assert compute_cache_hit_pct_strict(-1, 2000) is None
    assert compute_cache_hit_pct_strict(0, 0) is None
    # Легаси-функция сохраняет прежнее поведение (кламп) для обратной совместимости.
    assert compute_cache_hit_pct(5000, 1000) == 100.0


def test_classify_usage_validity_all_classes() -> None:
    """Четыре класса валидности кэш-счётчиков."""
    assert classify_usage_validity({"prompt_tokens": 2000, "cached_tokens": 1000}) == "valid"
    assert classify_usage_validity({"prompt_tokens": 2000, "cached_tokens": None}) == "valid"
    assert classify_usage_validity({"prompt_tokens": 2000, "usage_present": False}) == "missing"
    assert classify_usage_validity({"cached_tokens": 5}) == "missing"
    assert classify_usage_validity({"prompt_tokens": "2000"}) == "missing"
    assert classify_usage_validity({"prompt_tokens": 1000, "cached_tokens": 5000}) == "invalid_cached_gt_prompt"
    assert classify_usage_validity({"prompt_tokens": 1000, "cached_tokens": -1}) == "invalid_cached_gt_prompt"
    assert classify_usage_validity(
        {"prompt_tokens": 2000, "cached_tokens": 100, "usage_scope": "session_counter"}
    ) == "session_counter_suppressed"


def test_is_cache_eligible_threshold_and_bool() -> None:
    """eligible только для int >= порога; bool и не-int отвергаются."""
    assert is_cache_eligible(1024) is True
    assert is_cache_eligible(1023) is False
    assert is_cache_eligible(True) is False
    assert is_cache_eligible(None) is False
    assert is_cache_eligible(2048.0) is False
    assert is_cache_eligible(500, min_tokens=100) is True


def test_aggregate_records_mixed_sample_eligible_hit_rate() -> None:
    """Смешанная выборка: eligible_cache_hit_pct не искажается битыми и пустыми строками."""
    records: list[dict[str, Any]] = [
        {"prompt_tokens": 2000, "cached_tokens": 1000, "usage_present": True, "http_status": 200},
        {"prompt_tokens": 2000, "cached_tokens": 500, "usage_present": True, "http_status": 200},
        {"prompt_tokens": 500, "cached_tokens": 500, "usage_present": True, "http_status": 200},
        {"prompt_tokens": 3000, "cached_tokens": None, "usage_present": True, "http_status": 200},
        {"prompt_tokens": 1500, "cached_tokens": 9000, "usage_present": True, "http_status": 200},
        {"http_status": 500, "usage_present": False},
    ]
    summary = aggregate_records(records)["summary"]
    assert summary["total_requests"] == 6
    assert summary["usage_present_requests"] == 5
    assert summary["invalid_usage_requests"] == 1
    # Только строки 1-2: (1000 + 500) / (2000 + 2000) = 37.5%.
    assert summary["eligible_cache_hit_pct"] == 37.5


def test_aggregate_records_no_eligible_rows_gives_none() -> None:
    """Нет eligible строк -> None, а не измеренный ноль."""
    summary = aggregate_records(
        [{"prompt_tokens": 100, "cached_tokens": 0, "usage_present": True}, {"http_status": 500, "usage_present": False}]
    )["summary"]
    assert summary["eligible_cache_hit_pct"] is None
    assert summary["invalid_usage_requests"] == 0


def test_normalize_usage_record_aliases_keeps_legacy_and_adds_v2() -> None:
    """route=cli и легаси-поля сохраняются; добавляются usage_validity и cache_eligible."""
    record = {
        "route": "cli", "status_code": 200, "total_ms": 12, "ts": "2026-11-26T00:00:00Z",
        "prompt_tokens": 2000, "cached_tokens": 500, "usage_present": True,
    }
    out = normalize_usage_record_aliases(record)
    assert out["route"] == "cli"
    assert out["http_status"] == 200 and out["status_code"] == 200
    assert out["elapsed_ms"] == 12.0 and out["total_ms"] == 12.0
    assert out["ts_epoch"] == 1795651200.0
    assert out["uncached_prompt_tokens"] == 1500
    assert out["usage_validity"] == "valid"
    assert out["cache_eligible"] is True
    broken = normalize_usage_record_aliases({"prompt_tokens": 100, "cached_tokens": 900})
    assert broken["usage_validity"] == "invalid_cached_gt_prompt"
    assert broken["cache_eligible"] is False


def test_usage_log_fields_untouched_and_v2_fields_additive() -> None:
    """Базовые 16 полей на местах; v2-поля — отдельный аддитивный кортеж."""
    assert len(USAGE_LOG_FIELDS) == 16
    assert USAGE_LOG_FIELDS[5] == "route"
    assert "usage_validity" in USAGE_LOG_V2_OPTIONAL_FIELDS
    assert "pck_digest" in USAGE_LOG_V2_OPTIONAL_FIELDS
    assert not set(USAGE_LOG_V2_OPTIONAL_FIELDS) & {"ts", "route", "model"}
