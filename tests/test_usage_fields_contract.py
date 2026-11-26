"""Контрактные тесты usage-полей: Usage-сентинелы, нулевые счётчики и признак присутствия usage."""

from __future__ import annotations

from dataclasses import asdict

from core.usage_normalizer import Usage
from core.usage_fields import finalize_event_usage, normalize_usage_fields, telemetry_usage_updates


def test_usage_defaults_mark_absent() -> None:
    assert Usage().usage_present is False


def test_usage_zero_counters_mark_absent() -> None:
    assert Usage(0, 0).usage_present is False


def test_usage_nonzero_counters_mark_present() -> None:
    assert Usage(10, 20).usage_present is True


def test_normalize_absent_usage_returns_none_fields() -> None:
    fields = normalize_usage_fields(asdict(Usage()))
    assert fields["input_tokens"] is None
    assert fields["output_tokens"] is None
    assert fields["cache_read_tokens"] is None
    assert fields["reasoning_tokens"] is None
    assert fields["usage_present"] is False
    assert fields["usage_source"] is None
    assert fields["usage_missing_reason"] in {"empty_zero_usage", "omitted"}


def test_normalize_zero_counters_usage_marks_absent() -> None:
    fields = normalize_usage_fields(asdict(Usage(0, 0)))
    assert fields["input_tokens"] is None
    assert fields["output_tokens"] is None
    assert fields["usage_present"] is False
    assert fields["usage_source"] is None
    assert fields["usage_missing_reason"] in {"empty_zero_usage", "omitted"}


def test_normalize_vendor_zero_counters_absent() -> None:
    fields = normalize_usage_fields({"prompt_tokens": 0, "completion_tokens": 0})
    assert fields["input_tokens"] is None
    assert fields["output_tokens"] is None
    assert fields["usage_present"] is False
    assert fields["usage_source"] is None
    assert fields["usage_missing_reason"] == "empty_zero_usage"


def test_telemetry_updates_absent_usage_only_flag() -> None:
    updates = telemetry_usage_updates(asdict(Usage()))
    assert updates["usage_present"] is False
    assert updates["usage_source"] is None
    assert updates["usage_missing_reason"] in {"empty_zero_usage", "omitted"}
    assert set(updates) == {"usage_present", "usage_source", "usage_missing_reason"}


def test_telemetry_updates_zero_counters_mark_absent() -> None:
    updates = telemetry_usage_updates(asdict(Usage(0, 0)))
    assert updates["usage_present"] is False
    assert updates["usage_source"] is None
    assert updates["usage_missing_reason"] in {"empty_zero_usage", "omitted"}
    assert set(updates) == {"usage_present", "usage_source", "usage_missing_reason"}


def test_telemetry_updates_vendor_zero_counters() -> None:
    assert telemetry_usage_updates({"prompt_tokens": 0, "completion_tokens": 0}) == {
        "usage_present": False,
        "usage_source": None,
        "usage_missing_reason": "empty_zero_usage",
    }


def test_finalize_absent_usage_block_is_all_none() -> None:
    event = finalize_event_usage(telemetry_usage_updates(asdict(Usage())))
    assert {k: v for k, v in event.items() if k != "usage_missing_reason"} == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "cached_tokens": None,
        "reasoning_tokens": None,
        "cache_creation_tokens": None,
        "total_tokens": None,
        "usage_present": False,
        "usage_source": None,
    }
    assert event["usage_missing_reason"] in {"empty_zero_usage", "omitted"}


def test_finalize_zero_counters_usage_block() -> None:
    event = finalize_event_usage(telemetry_usage_updates(asdict(Usage(0, 0))))
    assert event["prompt_tokens"] is None
    assert event["completion_tokens"] is None
    assert event["usage_present"] is False
    assert event["usage_source"] is None
    assert event["usage_missing_reason"] in {"empty_zero_usage", "omitted"}
    assert event["total_tokens"] is None
