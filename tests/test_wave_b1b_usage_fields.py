"""Unit tests for core/usage_fields.py (PR B1b)."""
from __future__ import annotations

from types import SimpleNamespace

from core.usage_fields import (
    _nested,
    _resolve_turn_source,
    _usage_present,
    enrich_turn_usage_dict,
    extract_reasoning_tokens,
    normalize_usage_fields,
    telemetry_usage_updates,
)


def test_b1b_nested_presence_and_reasoning() -> None:
    assert (_nested({"a": {"x": 1}}, "a"), _nested({"a": "not-dict"}, "a")) == ({"x": 1}, {})
    assert (_usage_present({"usage_present": False, "prompt_tokens": 10}), _usage_present({"cached_tokens": 5}), _usage_present({"prompt_tokens": 0})) == (False, True, False)
    assert extract_reasoning_tokens({"reasoning_tokens": True, "completion_tokens_details": {"reasoning_tokens": 12}}) == 12
    assert extract_reasoning_tokens({"output_tokens_details": {"reasoning_tokens": 7}}) == 7
    assert extract_reasoning_tokens({"reasoning_tokens": -1}) is None


def test_b1b_normalize_usage_fields_cases() -> None:
    assert normalize_usage_fields(None) == {
        "input_tokens": None, "output_tokens": None, "cache_read_tokens": None,
        "reasoning_tokens": None, "cache_creation_tokens": None, "usage_present": None,
        "usage_source": None, "usage_missing_reason": None,
    }
    zero = normalize_usage_fields({"prompt_tokens": 0, "completion_tokens": 0})
    explicit_false = normalize_usage_fields({"prompt_tokens": 10, "usage_present": False})
    pos = normalize_usage_fields({"prompt_tokens": 0, "prompt_tokens_details": {"cached_tokens": 120}, "reasoning_tokens": 64, "source": "codex_app_server_v2"})
    assert (zero["usage_present"], zero["usage_missing_reason"], explicit_false["usage_present"], explicit_false["usage_missing_reason"]) == (False, "empty_zero_usage", False, "omitted")
    assert (pos["usage_present"], pos["cache_read_tokens"], pos["reasoning_tokens"], pos["usage_source"], pos["usage_missing_reason"]) == (True, 120, 64, "codex_v2_turn", None)


def test_b1b_enrich_turn_and_telemetry_updates() -> None:
    absent = enrich_turn_usage_dict({"input_tokens": 0, "usage_present": False}, None)
    explicit_override = enrich_turn_usage_dict({"input_tokens": 10, "usage_present": False}, None)
    empty_dict = enrich_turn_usage_dict({}, None)
    kept_positive = enrich_turn_usage_dict({"input_tokens": 10}, None)
    assert (absent["input_tokens"], absent["usage_present"], absent["usage_missing_reason"]) == (None, False, "empty_zero_usage")
    assert (explicit_override["usage_present"], explicit_override["usage_missing_reason"], empty_dict["usage_missing_reason"], kept_positive["usage_present"]) == (False, "omitted", "usage_missing_in_stream", True)
    tu = SimpleNamespace(prompt_tokens=10, completion_tokens=5, cache_read_tokens=None, reasoning_tokens=3, source="codex_app_server_v2")
    pos = enrich_turn_usage_dict({"usage_missing_reason": "broken_stream", "usage_present": False}, tu)
    assert (pos["usage_present"], pos["usage_source"], pos["usage_missing_reason"], pos["reasoning_tokens"]) == (True, "codex_v2_turn", None, 3)


def test_b1b_turn_source_and_telemetry_updates() -> None:
    tu = SimpleNamespace(source="codex_app_server_v2")
    assert (_resolve_turn_source({"usage_source": "upstream_report"}, tu), _resolve_turn_source({}, None)) == ("upstream_report", "upstream_report")
    assert telemetry_usage_updates(None) == {"usage_present": False, "usage_source": None, "usage_missing_reason": "usage_missing_in_stream"}
    upd = telemetry_usage_updates({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "usage_source": "upstream_report"})
    upd_no_tot = telemetry_usage_updates({"prompt_tokens": 10, "total_tokens": 0})
    assert (upd["total_tokens"], upd["usage_present"], "total_tokens" in upd_no_tot, upd_no_tot["usage_source"]) == (15, True, False, "upstream_report")
