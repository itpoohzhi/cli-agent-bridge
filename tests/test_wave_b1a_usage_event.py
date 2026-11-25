"""Unit tests for core/usage_event_fields.py (PR B1a)."""
from __future__ import annotations

from core.usage_event_fields import (
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


def test_b1a_predicates_and_resolvers() -> None:
    assert (_is_counter(0), _is_counter(-1), _is_counter(True), _is_counter(1.5)) == (True, False, False, False)
    assert (_is_number(0), _is_number(1.5), _is_number(True), _is_number("1")) == (True, True, False, False)
    assert (_is_positive(1), _is_positive(0), _is_positive(-1), _is_positive(True)) == (True, False, False, False)
    assert (_resolve_usage_source("upstream_report"), _resolve_usage_source("codex_app_server_v2"), _resolve_usage_source("codex_app_server"), _resolve_usage_source("bad"), _resolve_usage_source(1)) == ("upstream_report", "codex_v2_turn", "codex_legacy", None, None)
    assert (_resolve_missing_reason("broken_stream"), _resolve_missing_reason("bad"), _resolve_missing_reason(None)) == ("broken_stream", None, None)


def test_b1a_absent_reason_and_mark_absent() -> None:
    assert (_absent_reason("broken_stream", True, True), _absent_reason(None, True, True), _absent_reason(None, False, True), _absent_reason(None, False, False)) == ("broken_stream", "empty_zero_usage", "omitted", "usage_missing_in_stream")
    enriched = _mark_usage_absent({"prompt_tokens": 0, "reasoning_tokens": 0, "extra": 1}, (0, 0), False, False)
    assert (enriched["prompt_tokens"], enriched["reasoning_tokens"], enriched["usage_present"], enriched["usage_source"], enriched["usage_missing_reason"], enriched["extra"]) == (None, None, False, None, "empty_zero_usage", 1)
    assert _mark_usage_absent({"usage_missing_reason": None}, (), False, True)["usage_missing_reason"] == "omitted"


def test_b1a_total_tokens_and_finalize_positive() -> None:
    assert (_total_tokens(0, 0, True), _total_tokens(0, 0, 25), _total_tokens(None, None, None), _total_tokens(0, 0, None), _total_tokens(10, 5, None), _total_tokens(10, None, 0)) == (None, 25, None, None, 15, 10)
    meta = {"prompt_tokens": 10, "completion_tokens": 5, "usage_source": "codex_app_server_v2", "keep": "x"}
    ev = finalize_event_usage(meta)
    assert (ev, meta) == (
        {"prompt_tokens": 10, "completion_tokens": 5, "cached_tokens": None, "reasoning_tokens": None, "total_tokens": 15, "usage_present": True, "usage_source": "codex_v2_turn", "usage_missing_reason": None},
        {"keep": "x"},
    )
    assert finalize_event_usage({"cached_tokens": 4})["usage_source"] == "upstream_report"


def test_b1a_finalize_absent_variants() -> None:
    explicit_false = finalize_event_usage({"prompt_tokens": 10, "usage_present": False})
    zero_usage = finalize_event_usage({"prompt_tokens": 0, "completion_tokens": 0})
    empty = finalize_event_usage({})
    assert (explicit_false["usage_present"], explicit_false["usage_missing_reason"], explicit_false["prompt_tokens"]) == (False, "omitted", None)
    assert (zero_usage["usage_present"], zero_usage["usage_missing_reason"]) == (False, "empty_zero_usage")
    assert (empty["usage_present"], empty["usage_missing_reason"], empty["total_tokens"]) == (False, "usage_missing_in_stream", None)
