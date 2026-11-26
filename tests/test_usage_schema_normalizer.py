"""Табличные unit-тесты чистых модулей core/usage_schema и core/usage_normalizer."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

import pytest

from core.usage_normalizer import (
    OMITTED,
    Usage,
    reconcile_turn_usage,
    resolve_usage_presence,
)
from core.usage_schema import (
    USAGE_DB_SOURCE_MAP,
    USAGE_FIELD_ALIASES,
    USAGE_LOG_FIELDS,
    compute_uncached_prompt_tokens,
    normalize_elapsed_ms,
    normalize_status_code,
    normalize_usage_record_aliases,
    parse_ts_epoch,
    resolve_usage_log_source_value,
)

_ISO_UTC = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc).timestamp()


def test_usage_log_fields_exact() -> None:
    assert USAGE_LOG_FIELDS == (
        "ts", "request_id", "model", "subagent_id", "subagent_role",
        "route", "backend_id", "stream", "http_status", "elapsed_ms",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "cached_tokens", "reasoning_tokens", "usage_present",
        "cache_creation_tokens", "usage_missing_reason",
    )
    assert len(USAGE_LOG_FIELDS) == 18
    assert USAGE_DB_SOURCE_MAP == {
        "ts": "ts_iso", "route": "route_mode",
        "http_status": "status_code", "elapsed_ms": "total_ms",
    }
    assert USAGE_FIELD_ALIASES == {
        "ts": ("ts_epoch", "ts_iso", "ts"),
        "route": ("route", "route_mode"),
        "http_status": ("http_status", "status_code"),
        "elapsed_ms": ("elapsed_ms", "total_ms"),
    }


@pytest.mark.parametrize(
    ("row_map", "field", "expected"),
    [
        ({"ts_iso": "2024-01-01", "ts": "fallback"}, "ts", "2024-01-01"),
        ({"ts_iso": None, "ts": "fallback"}, "ts", "fallback"),
        ({"status_code": 0, "http_status": None}, "http_status", 0),
        ({"route_mode": False, "route": "x"}, "route", False),
        ({"total_ms": 12.5}, "elapsed_ms", 12.5),
        ({"model": "g"}, "model", "g"),
        ({"model": "g"}, "missing_field", None),
    ],
)
def test_resolve_usage_log_source_value(
    row_map: dict[str, Any], field: str, expected: object
) -> None:
    assert resolve_usage_log_source_value(row_map, field) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, None),
        (False, None),
        (0, 0.0),
        (1700000000, 1700000000.0),
        (1700000000.25, 1700000000.25),
        (float("inf"), None),
        (None, None),
        ("not-a-date", None),
        ("2024-01-02T03:04:05Z", _ISO_UTC),
        ("2024-01-02T03:04:05+02:00", _ISO_UTC - 7200.0),
        ("2024-01-02T03:04:05", _ISO_UTC),
    ],
)
def test_parse_ts_epoch(value: object, expected: float | None) -> None:
    assert parse_ts_epoch(value) == expected

@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"http_status": 201, "status_code": 500}, 201),
        ({"http_status": True, "status_code": 500}, 500),
        ({"http_status": 500.0, "status_code": 404}, 404),
        ({"status_code": 404}, 404),
        ({"http_status": 0}, 0),
        ({}, None),
        ({"http_status": "500", "status_code": "404"}, None),
    ],
)
def test_normalize_status_code(record: dict[str, Any], expected: int | None) -> None:
    assert normalize_status_code(record) == expected


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"elapsed_ms": 12.5, "total_ms": 1.0}, 12.5),
        ({"total_ms": 7}, 7.0),
        ({"elapsed_ms": True, "total_ms": 3}, 3.0),
        ({"elapsed_ms": -1, "total_ms": -2}, None),
        ({"elapsed_ms": float("inf")}, None),
        ({"elapsed_ms": "12"}, None),
        ({}, None),
    ],
)
def test_normalize_elapsed_ms(record: dict[str, Any], expected: float | None) -> None:
    assert normalize_elapsed_ms(record) == expected


@pytest.mark.parametrize(
    ("prompt_tokens", "cached_tokens", "expected"),
    [
        (100, 40, 60),
        (10, 40, 0),
        (None, None, 0),
        (True, False, 0),
        ("x", 5, 0),
        (100.0, 40.0, 60),
    ],
)
def test_compute_uncached_prompt_tokens(
    prompt_tokens: object, cached_tokens: object, expected: int
) -> None:
    assert compute_uncached_prompt_tokens(prompt_tokens, cached_tokens) == expected


def test_normalize_usage_record_aliases() -> None:
    original: dict[str, Any] = {
        "ts_epoch": 1700000000.0, "status_code": 404, "total_ms": 12.5,
        "prompt_tokens": 100, "cached_tokens": 40,
    }
    normalized = normalize_usage_record_aliases(original)
    assert normalized is not original
    assert normalized["http_status"] == 404 and normalized["status_code"] == 404
    assert normalized["elapsed_ms"] == 12.5 and normalized["total_ms"] == 12.5
    assert normalized["ts_epoch"] == 1700000000.0
    assert normalized["uncached_prompt_tokens"] == 60
    assert "http_status" not in original and "uncached_prompt_tokens" not in original


def test_normalize_usage_record_aliases_http_and_iso_priority() -> None:
    record: dict[str, Any] = {
        "http_status": 201, "status_code": 500, "ts_iso": "2024-01-02T03:04:05Z",
    }
    out = normalize_usage_record_aliases(record)
    assert out["status_code"] == 201
    assert out["ts_epoch"] == _ISO_UTC
    assert out["elapsed_ms"] is None and out["total_ms"] is None
    assert out["uncached_prompt_tokens"] == 0


@pytest.mark.parametrize(
    ("explicit", "values", "expected"),
    [
        (True, (OMITTED,), False),
        (False, (1, 2), False),
        (None, (), False),
        (None, (OMITTED, OMITTED), False),
        (None, (0, OMITTED), False),
        (None, (False,), False),
        (None, (1, OMITTED), True),
    ],
)
def test_resolve_usage_presence(
    explicit: bool | None, values: tuple[object, ...], expected: bool
) -> None:
    assert resolve_usage_presence(explicit=explicit, supplied_values=values) is expected


def test_usage_presence_matrix() -> None:
    assert Usage().usage_present is False
    assert Usage(0, 0).usage_present is False
    assert Usage(10, 20).usage_present is True
    assert Usage(0, 0, usage_present=False).usage_present is False
    assert Usage(usage_present=True).usage_present is False


def test_usage_defaults_and_asdict() -> None:
    empty = Usage()
    assert dataclasses.asdict(empty) == {
        "input_tokens": 0, "output_tokens": 0,
        "cache_read_tokens": None, "cache_creation_tokens": None,
        "usage_present": False,
    }
    full = Usage(1, 2, 3, 4)
    assert (full.input_tokens, full.output_tokens) == (1, 2)
    assert (full.cache_read_tokens, full.cache_creation_tokens) == (3, 4)
    assert full.usage_present is True


def test_usage_omitted_never_leaks_and_frozen() -> None:
    usage = Usage()
    for value in dataclasses.astuple(usage):
        assert not isinstance(value, type(OMITTED))
    with pytest.raises(dataclasses.FrozenInstanceError):
        usage.input_tokens = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    ("raw_in", "raw_out", "raw_total", "raw_thinking", "expected"),
    [
        (0, 0, 0, 0, (0, 0, 0, None, False, "ambiguous")),
        (10, 20, 0, 0, (10, 20, 30, None, False, "ambiguous")),
        (10, 20, 30, 0, (10, 20, 30, None, False, "output_includes_reasoning")),
        (15334, 16310, 31644, 14976, (15334, 16310, 31644, 14976, False, "output_includes_reasoning")),
        (100, 50, 170, 20, (100, 70, 170, 20, False, "output_excludes_reasoning")),
        (10, 5, 0, 20, (10, 5, 15, None, True, "ambiguous")),
        (10, 20, 40, 6, (10, 20, 30, 6, False, "ambiguous")),
        (True, False, True, False, (0, 0, 0, None, False, "ambiguous")),
        (-5, -20, -30, -40, (0, 0, 0, None, False, "ambiguous")),
        (10.0, 20.0, 30.0, 0.0, (10, 20, 30, None, False, "output_includes_reasoning")),
        ("x", "y", "z", "w", (0, 0, 0, None, False, "ambiguous")),
    ],
)
def test_reconcile_turn_usage(
    raw_in: object,
    raw_out: object,
    raw_total: object,
    raw_thinking: object,
    expected: tuple[int, int, int, int | None, bool, str],
) -> None:
    result = reconcile_turn_usage(
        raw_input=raw_in, raw_output=raw_out, raw_total=raw_total, raw_thinking=raw_thinking
    )
    assert dataclasses.astuple(result) == expected


def test_reconciled_usage_frozen() -> None:
    result = reconcile_turn_usage(raw_input=1, raw_output=2, raw_total=3, raw_thinking=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.relation = "x"  # type: ignore[misc]


def test_legacy_16_field_rows_read_with_none_defaults() -> None:
    """Старые 16-польные JSONL-строки читаются без ошибок: новых полей нет -> None по умолчанию."""
    legacy = {name: None for name in USAGE_LOG_FIELDS[:16]}
    legacy.update(prompt_tokens=10, cached_tokens=4, usage_present=True, http_status=200)
    normalized = normalize_usage_record_aliases(legacy)
    assert normalized["uncached_prompt_tokens"] == 6
    assert normalized["usage_validity"] == "valid"
    assert normalized.get("cache_creation_tokens") is None
    assert normalized.get("usage_missing_reason") is None
    assert tuple(legacy) == USAGE_LOG_FIELDS[:16]
