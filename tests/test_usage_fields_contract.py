"""Контрактные тесты usage-полей: Usage-сентинелы, нулевые счётчики и признак присутствия usage."""

from __future__ import annotations

from dataclasses import asdict

from core.backend_adapter import Usage
from core.usage_fields import finalize_event_usage, normalize_usage_fields, telemetry_usage_updates


def test_usage_defaults_mark_absent() -> None:
    assert Usage().usage_present is False


def test_usage_zero_counters_mark_present() -> None:
    assert Usage(0, 0).usage_present is True


def test_usage_nonzero_counters_mark_present() -> None:
    assert Usage(10, 20).usage_present is True


def test_normalize_absent_usage_returns_none_fields() -> None:
    assert normalize_usage_fields(asdict(Usage())) == {
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "reasoning_tokens": None,
        "usage_present": False,
    }


def test_normalize_zero_counters_usage_keeps_zeros() -> None:
    fields = normalize_usage_fields(asdict(Usage(0, 0)))
    assert fields["input_tokens"] == 0
    assert fields["output_tokens"] == 0
    assert fields["usage_present"] is True


def test_normalize_vendor_zero_counters_present() -> None:
    fields = normalize_usage_fields({"prompt_tokens": 0, "completion_tokens": 0})
    assert fields["input_tokens"] == 0
    assert fields["output_tokens"] == 0
    assert fields["usage_present"] is True


def test_telemetry_updates_absent_usage_only_flag() -> None:
    assert telemetry_usage_updates(asdict(Usage())) == {"usage_present": False}


def test_telemetry_updates_zero_counters_keep_zeros() -> None:
    assert telemetry_usage_updates(asdict(Usage(0, 0))) == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "usage_present": True,
    }


def test_telemetry_updates_vendor_zero_counters() -> None:
    assert telemetry_usage_updates({"prompt_tokens": 0, "completion_tokens": 0}) == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "usage_present": True,
    }


def test_finalize_absent_usage_block_is_all_none() -> None:
    event = finalize_event_usage(telemetry_usage_updates(asdict(Usage())))
    assert event == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "cached_tokens": None,
        "reasoning_tokens": None,
        "total_tokens": None,
        "usage_present": False,
    }


def test_finalize_zero_counters_usage_block() -> None:
    event = finalize_event_usage(telemetry_usage_updates(asdict(Usage(0, 0))))
    assert event["prompt_tokens"] == 0
    assert event["completion_tokens"] == 0
    assert event["usage_present"] is True
    assert event["total_tokens"] is None
