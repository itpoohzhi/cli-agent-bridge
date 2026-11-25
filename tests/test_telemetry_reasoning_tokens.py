"""Тесты reasoning-токенов и usage-полей: чистые контракты core.usage_fields и разбор хвоста telemetry_usage."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from core.telemetry_hooks import TelemetryHooksMixin
from core.telemetry_usage import extract_usage, normalize_usage
from core.turn_dispatch import _format_turn_output
from core.turn_usage import TurnUsage
from core.turn_usage_result import make_turn_result
from core.usage_fields import (
    enrich_turn_usage_dict,
    extract_reasoning_tokens,
    finalize_event_usage,
    normalize_usage_fields,
    telemetry_usage_updates,
)

USAGE_FIELDS_PATH = Path(__file__).resolve().parents[1] / "core" / "usage_fields.py"


class _DummyTelemetryHandler(TelemetryHooksMixin):
    headers: Any = {}

    def _telemetry_srv(self) -> SimpleNamespace:
        return SimpleNamespace(
            REQUEST_TELEMETRY=SimpleNamespace(is_enabled=lambda: True),
            BACKENDS={},
            _bridge_env=lambda _key, default: default,
        )


def test_extract_reasoning_tokens_flat_key() -> None:
    assert extract_reasoning_tokens({"reasoning_tokens": 7}) == 7


def test_extract_reasoning_tokens_zero_is_valid() -> None:
    assert extract_reasoning_tokens({"reasoning_tokens": 0}) == 0


def test_extract_reasoning_tokens_from_completion_details() -> None:
    raw = {"completion_tokens_details": {"reasoning_tokens": 3}}
    assert extract_reasoning_tokens(raw) == 3


def test_extract_reasoning_tokens_from_output_details() -> None:
    raw = {"output_tokens_details": {"reasoning_tokens": 9}}
    assert extract_reasoning_tokens(raw) == 9


def test_extract_reasoning_tokens_bool_is_rejected() -> None:
    assert extract_reasoning_tokens({"reasoning_tokens": True}) is None


def test_extract_reasoning_tokens_negative_is_rejected() -> None:
    assert extract_reasoning_tokens({"reasoning_tokens": -1}) is None


def test_extract_reasoning_tokens_invalid_type_is_rejected() -> None:
    assert extract_reasoning_tokens({"reasoning_tokens": "3"}) is None


def test_extract_reasoning_tokens_missing_is_none() -> None:
    assert extract_reasoning_tokens({}) is None


def test_normalize_usage_fields_openai_keys() -> None:
    fields = normalize_usage_fields({"prompt_tokens": 10, "completion_tokens": 5})
    assert fields == {
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_tokens": None,
        "reasoning_tokens": None,
        "usage_present": True,
        "usage_source": "upstream_report",
        "usage_missing_reason": None,
    }


def test_normalize_usage_fields_zero_counters_are_not_present() -> None:
    """Контракт B1b: нулевые счётчики не подтверждают usage, причина — empty_zero_usage."""
    fields = normalize_usage_fields({"prompt_tokens": 0, "completion_tokens": 0})
    assert fields["usage_present"] is False
    assert fields["usage_missing_reason"] == "empty_zero_usage"
    assert fields["usage_source"] is None


def test_normalize_usage_fields_empty_mapping_is_not_present() -> None:
    assert normalize_usage_fields({})["usage_present"] is False


def test_normalize_usage_fields_none_gives_all_none() -> None:
    assert normalize_usage_fields(None) == {
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "reasoning_tokens": None,
        "usage_present": None,
        "usage_source": None,
        "usage_missing_reason": None,
    }


def test_normalize_usage_fields_explicit_flag() -> None:
    """Контракт B1b: явный usage_present=True без положительных счётчиков не принимается."""
    assert normalize_usage_fields({"prompt_tokens": 1, "usage_present": True})["usage_present"] is True
    bare = normalize_usage_fields({"usage_present": True})
    assert bare["usage_present"] is False
    assert bare["usage_missing_reason"] == "usage_missing_in_stream"


def test_normalize_usage_fields_cache_variants() -> None:
    anthropic = normalize_usage_fields({"input_tokens": 4, "cache_read_input_tokens": 1})
    assert anthropic["cache_read_tokens"] == 1
    openai = normalize_usage_fields({"prompt_tokens": 4, "cached_tokens": 2})
    assert openai["cache_read_tokens"] == 2
    detailed = normalize_usage_fields({"prompt_tokens": 4, "prompt_tokens_details": {"cached_tokens": 3}})
    assert detailed["cache_read_tokens"] == 3


def test_normalize_usage_fields_reasoning_from_details() -> None:
    raw = {"completion_tokens": 5, "completion_tokens_details": {"reasoning_tokens": 3}}
    fields = normalize_usage_fields(raw)
    assert fields["reasoning_tokens"] == 3
    assert fields["usage_present"] is True


def test_normalize_usage_returns_reasoning_without_presence_flag() -> None:
    fields = normalize_usage({"prompt_tokens": 1, "output_tokens_details": {"reasoning_tokens": 2}})
    assert fields == {"input_tokens": 1, "output_tokens": None, "cache_read_tokens": None, "reasoning_tokens": 2,
                      "usage_source": "upstream_report", "usage_missing_reason": None}


def test_extract_usage_openai_with_reasoning() -> None:
    tail = b'{"usage":{"prompt_tokens":10,"completion_tokens":5,"completion_tokens_details":{"reasoning_tokens":3}}}'
    assert extract_usage(tail) == {
        "input_tokens": 10,
        "output_tokens": 5,
        "reasoning_tokens": 3,
        "usage_source": "upstream_report",
    }


def test_extract_usage_anthropic_keys() -> None:
    tail = b'{"usage":{"input_tokens":7,"output_tokens":4,"cache_read_input_tokens":2}}'
    assert extract_usage(tail) == {
        "input_tokens": 7,
        "output_tokens": 4,
        "cache_read_tokens": 2,
        "usage_source": "upstream_report",
    }


def test_extract_usage_zero_counters_are_not_confirmed() -> None:
    """Контракт B1b: нулевой usage не подтверждает присутствие, причина empty_zero_usage."""
    tail = b'{"usage":{"prompt_tokens":0,"completion_tokens":0}}'
    usage = extract_usage(tail)
    assert usage == {"usage_missing_reason": "empty_zero_usage"}
    updates = telemetry_usage_updates(usage)
    assert updates["usage_present"] is False
    assert updates["usage_missing_reason"] == "empty_zero_usage"


def test_extract_usage_cli_contract_without_presence_flag() -> None:
    tail = b'"usage": {"prompt_tokens": 1, "completion_tokens": 2}'
    usage = extract_usage(tail)
    assert usage == {"input_tokens": 1, "output_tokens": 2, "usage_source": "upstream_report"}
    assert telemetry_usage_updates(usage)["usage_present"] is True


def test_extract_usage_without_usage_key_is_none() -> None:
    assert extract_usage(b'{"choices":[{"text":"hi"}]}') is None


def test_enrich_turn_usage_dict_overwrites_and_marks_present() -> None:
    base = {"input_tokens": 1, "output_tokens": 1}
    turn = TurnUsage(prompt_tokens=10, completion_tokens=5, cache_read_tokens=2, reasoning_tokens=3)
    assert enrich_turn_usage_dict(base, turn) == {
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_tokens": 2,
        "reasoning_tokens": 3,
        "usage_present": True,
        "usage_source": "upstream_report",
        "usage_missing_reason": None,
    }
    assert base == {"input_tokens": 1, "output_tokens": 1}


def test_enrich_turn_usage_dict_skips_absent_optional_fields() -> None:
    turn = TurnUsage(prompt_tokens=10, completion_tokens=5)
    assert enrich_turn_usage_dict({}, turn) == {
        "input_tokens": 10,
        "output_tokens": 5,
        "usage_present": True,
        "usage_source": "upstream_report",
        "usage_missing_reason": None,
    }


def test_telemetry_usage_updates_maps_keys() -> None:
    usage = {"input_tokens": 10, "output_tokens": 5, "cache_read_tokens": 2, "reasoning_tokens": 3}
    assert telemetry_usage_updates(usage) == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "cached_tokens": 2,
        "reasoning_tokens": 3,
        "usage_present": True,
        "usage_source": "upstream_report",
        "usage_missing_reason": None,
    }


def test_telemetry_usage_updates_none_usage() -> None:
    assert telemetry_usage_updates(None) == {
        "usage_present": False,
        "usage_source": None,
        "usage_missing_reason": "usage_missing_in_stream",
    }


def test_finalize_event_usage_full_block() -> None:
    meta = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "cached_tokens": 2,
        "reasoning_tokens": 3,
        "usage_present": True,
        "event": "turn",
    }
    assert finalize_event_usage(meta) == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "cached_tokens": 2,
        "reasoning_tokens": 3,
        "total_tokens": 15,
        "usage_present": True,
        "usage_source": "upstream_report",
        "usage_missing_reason": None,
    }
    assert meta == {"event": "turn"}


def test_finalize_event_usage_derives_presence_and_total() -> None:
    usage = finalize_event_usage({"prompt_tokens": 7})
    assert usage["usage_present"] is True
    assert usage["total_tokens"] == 7


def test_finalize_event_usage_empty_meta() -> None:
    assert finalize_event_usage({}) == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "cached_tokens": None,
        "reasoning_tokens": None,
        "total_tokens": None,
        "usage_present": False,
        "usage_source": None,
        "usage_missing_reason": "usage_missing_in_stream",
    }


def test_finalize_event_usage_zero_total_stays_none() -> None:
    """Контракт B1b: нулевые счётчики при явном usage_present=True остаются без usage."""
    raw = {"prompt_tokens": 0, "completion_tokens": 0, "usage_present": True}
    usage = finalize_event_usage(raw)
    assert usage["total_tokens"] is None
    assert usage["usage_present"] is False
    assert usage["usage_missing_reason"] == "empty_zero_usage"


def test_format_turn_output_propagates_reasoning_tokens_and_presence() -> None:
    turn_usage = TurnUsage(prompt_tokens=10, completion_tokens=5, reasoning_tokens=42)
    result = make_turn_result("ok", "", turn_usage=turn_usage)
    out = _format_turn_output(result, "cli")
    assert out["usage"]["reasoning_tokens"] == 42
    assert out["usage"]["usage_present"] is True
    assert out["turn_usage"] == turn_usage


def test_telemetry_hooks_preserve_reasoning_tokens_and_presence() -> None:
    handler = _DummyTelemetryHandler()
    handler._telemetry_begin()
    handler._telemetry_usage({"input_tokens": 10, "output_tokens": 5, "reasoning_tokens": 42})
    event = handler._telemetry_event(dict(handler._req_meta or {}), 200)
    assert event["prompt_tokens"] == 10
    assert event["completion_tokens"] == 5
    assert event["reasoning_tokens"] == 42
    assert event["total_tokens"] == 15
    assert event["usage_present"] is True


def test_telemetry_hooks_mark_absent_usage() -> None:
    handler = _DummyTelemetryHandler()
    handler._telemetry_begin()
    event = handler._telemetry_event(dict(handler._req_meta or {}), 200)
    assert event["usage_present"] is False
    assert event["reasoning_tokens"] is None
    assert event["total_tokens"] is None


def test_usage_fields_module_never_touches_environ_or_io() -> None:
    source = USAGE_FIELDS_PATH.read_text(encoding="utf-8")
    assert "import os" not in source
    assert "from os" not in source
    assert "os.environ" not in source
    assert "open(" not in source


def test_usage_fields_module_has_no_mutable_module_level_collections() -> None:
    tree = ast.parse(USAGE_FIELDS_PATH.read_text(encoding="utf-8"))
    forbidden = (ast.Dict, ast.List, ast.Set)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            assert not isinstance(node.value, forbidden)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            assert not isinstance(node.value, forbidden)
