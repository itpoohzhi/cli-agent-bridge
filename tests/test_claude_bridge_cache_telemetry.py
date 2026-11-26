from __future__ import annotations

from core.claude_bridge_telemetry import format_done_usage_suffix, project_wire_usage
from core.claude_prompt import wire_cache_creation_enabled
from core.usage_wire import turn_usage_from_wire

WIRE = {"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105}
RAW = {"cache_creation_input_tokens": 40, "cache_read_input_tokens": 10}


def test_done_suffix_full_usage_and_digest() -> None:
    usage = {
        "input_tokens": 1,
        "output_tokens": 2,
        "cache_read_input_tokens": 3,
        "cache_creation_input_tokens": 4,
    }
    suffix = format_done_usage_suffix(usage, "abcdef0123456789")
    assert suffix == (
        "input_tokens=1 output_tokens=2 cache_read_input_tokens=3 "
        "cache_creation_input_tokens=4 chat_key=abcdef0123456789"
    )


def test_done_suffix_missing_usage_uses_dash() -> None:
    expected = (
        "input_tokens=- output_tokens=- cache_read_input_tokens=- "
        "cache_creation_input_tokens=- chat_key=-"
    )
    assert format_done_usage_suffix(None, None) == expected
    assert format_done_usage_suffix({}, "") == expected


def test_done_suffix_partial_usage_and_none_values() -> None:
    suffix = format_done_usage_suffix({"input_tokens": 7, "output_tokens": None}, None)
    assert "input_tokens=7 output_tokens=- " in suffix
    assert "cache_read_input_tokens=-" in suffix


def test_done_suffix_truncates_digest_and_zero_kept() -> None:
    digest = "0123456789abcdef" + "SECRET-TAIL"
    suffix = format_done_usage_suffix({"input_tokens": 0}, digest)
    assert suffix.endswith("chat_key=0123456789abcdef")
    assert "SECRET" not in suffix
    assert "input_tokens=0 " in suffix


def test_project_wire_usage_flag_off_keeps_ad004_shape() -> None:
    wire = {**WIRE, "prompt_tokens_details": {"cached_tokens": 10}}
    projected = project_wire_usage(wire, RAW, include_cache_creation=False)
    assert projected == wire
    assert projected is not wire
    assert not [k for k in projected if k.startswith("cache_creation")]


def test_project_wire_usage_flag_off_strips_creation_keys() -> None:
    polluted = {**WIRE, "cache_creation_input_tokens": 1}
    projected = project_wire_usage(polluted, RAW, include_cache_creation=False)
    assert projected == WIRE


def test_project_wire_usage_flag_on_adds_top_level_creation() -> None:
    projected = project_wire_usage(WIRE, RAW, include_cache_creation=True)
    assert projected == {**WIRE, "cache_creation_input_tokens": 40}
    assert WIRE == {"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105}


def test_project_wire_usage_flag_on_without_raw_creation() -> None:
    assert project_wire_usage(WIRE, None, include_cache_creation=True) == WIRE
    assert project_wire_usage(WIRE, {}, include_cache_creation=True) == WIRE


def test_turn_usage_from_wire_reads_creation_when_present() -> None:
    wire = {**WIRE, "cache_creation_input_tokens": 40}
    usage = turn_usage_from_wire(wire, "test")
    assert usage is not None
    assert usage.cache_creation_tokens == 40


def test_turn_usage_from_wire_creation_absent_is_none() -> None:
    usage = turn_usage_from_wire(WIRE, "test")
    assert usage is not None
    assert usage.cache_creation_tokens is None


def test_wire_cache_creation_flag_default_off() -> None:
    assert wire_cache_creation_enabled({}) is False
    assert wire_cache_creation_enabled({"CLAUDE_P_BRIDGE_WIRE_CACHE_CREATION": "0"}) is False
    assert wire_cache_creation_enabled({"CLAUDE_P_BRIDGE_WIRE_CACHE_CREATION": "junk"}) is False


def test_wire_cache_creation_flag_truthy_values() -> None:
    for value in ("1", "true", "YES", " on "):
        env = {"CLAUDE_P_BRIDGE_WIRE_CACHE_CREATION": value}
        assert wire_cache_creation_enabled(env) is True
