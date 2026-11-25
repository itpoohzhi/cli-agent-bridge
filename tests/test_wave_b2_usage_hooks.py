"""Unit tests for core/usage_normalizer.py, core/telemetry_hooks.py, codex_usage.py (PR B2)."""
from __future__ import annotations

from core.stdio_resident.codex_usage import _has_positive_usage, extract_codex_legacy_usage, extract_codex_v2_usage
from core.telemetry_hooks import TelemetryHooksMixin, _resolve_subagent_role
from core.telemetry_sql import MIGRATION_COLUMNS, NAMES, make_row
from core.turn_usage import UsageUpdate, normalize_usage_update
from core.usage_fields import enrich_turn_usage_dict
from core.usage_normalizer import Usage, resolve_usage_presence


def test_b2_usage_normalizer_and_codex() -> None:
    assert (Usage(0, 0).usage_present, Usage(0, 0, cache_read_tokens=12).usage_present) == (False, True)
    assert (resolve_usage_presence(explicit=True, supplied_values=[0, 0]), resolve_usage_presence(explicit=None, supplied_values=[0, 64])) == (False, True)
    assert (_has_positive_usage(UsageUpdate(input_tokens=True, output_tokens=0)), _has_positive_usage(UsageUpdate(input_tokens=5, output_tokens=0))) == (False, True)
    v2_turn = extract_codex_v2_usage({"params": {"tokenUsage": {"last": {"inputTokens": 5, "outputTokens": 3}}}})
    v2_sess = extract_codex_v2_usage({"params": {"tokenUsage": {"total": {"inputTokens": 8, "outputTokens": 2}}}})
    v2_zero = extract_codex_v2_usage({"params": {"tokenUsage": {"last": {"inputTokens": 0}, "total": {"inputTokens": 0}}}})
    assert (extract_codex_v2_usage({}), extract_codex_legacy_usage({}), v2_turn is not None, v2_sess is not None, v2_zero is None) == (None, None, True, True, True)


def test_b2_codex_broken_and_telemetry_hooks() -> None:
    broken_empty = enrich_turn_usage_dict({"usage_missing_reason": "broken_stream"}, None)
    norm_pos = normalize_usage_update(UsageUpdate(input_tokens=10, output_tokens=5, source="codex_v2_turn"))
    assert (broken_empty["usage_present"], norm_pos.usage is not None) == (False, True)

    class _H(TelemetryHooksMixin):
        def __init__(self) -> None:
            self._req_meta: dict[str, object] = {"stream": False}

    h = _H()
    h._telemetry_usage(None)
    assert (h._req_meta["usage_present"], h._req_meta["usage_missing_reason"]) == (False, "usage_missing_in_stream")
    h._telemetry_usage({"prompt_tokens": 5})
    assert (h._req_meta["usage_present"], "usage_missing_reason" not in h._req_meta) == (True, True)
    h._telemetry_usage(None)
    assert (h._req_meta["usage_present"], h._req_meta["prompt_tokens"]) == (True, 5)
    h._req_meta = None  # type: ignore[assignment]
    h._telemetry_usage({"prompt_tokens": 5})
    assert h._req_meta is None


def test_b2_role_and_sql_schema() -> None:
    roles = (
        _resolve_subagent_role("Answer-Review", "other", "skeptic-1"),
        _resolve_subagent_role("answer-review-repair", None, "skeptic-1"),
        _resolve_subagent_role(None, "Answer-Review", "skeptic-1"),
        _resolve_subagent_role(None, None, "Skeptic-42"),
        _resolve_subagent_role("bad role!", None, None),
    )
    assert roles == ("answer-review", "answer-review-repair", "answer-review", "skeptic", None)
    assert (len(NAMES), NAMES[-4:], MIGRATION_COLUMNS) == (
        33,
        ("reasoning_tokens", "usage_present", "usage_source", "usage_missing_reason"),
        (("reasoning_tokens", "INTEGER"), ("usage_present", "BOOLEAN"), ("usage_source", "TEXT"), ("usage_missing_reason", "TEXT")),
    )
    row = make_row({"subagent_id": "skeptic-1", "subagent_role": "answer-review", "usage_present": False, "usage_source": None, "usage_missing_reason": "empty_zero_usage"})
    assert dict(zip(NAMES, row))["usage_missing_reason"] == "empty_zero_usage"
