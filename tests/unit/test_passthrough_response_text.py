"""L1: локальные шовные функции passthrough (choice-вызовы, текст delta, счётчики)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from adapters.passthrough_adapter import (
    PassthroughLimits,
    _published_call_count,
    _ResponseText,
    _stream_error_info,
    sanitize_choice_calls,
)
from tests.unit._passthrough_tool_branches import (
    EMULATE_SPEC,
    FORBID_SPEC,
    OFF_SPEC,
    isolated_env as isolated_env,
    limits as limits,
)

VALID_CALL = '<tool_call>{"name":"noop","arguments":{}}</tool_call>'


def _plain(call_id: str, index: int | None) -> dict[str, Any]:
    call: dict[str, Any] = {
        "id": call_id,
        "type": "function",
        "function": {"name": "plain", "arguments": "{}"},
    }
    if index is not None:
        call["index"] = index
    return call


def _parallel(call_id: str, index: int | None) -> dict[str, Any]:
    uses = [
        {"recipient_name": "functions.a", "parameters": {}},
        {"recipient_name": "functions.b", "parameters": {}},
    ]
    call = _plain(call_id, index)
    call["function"] = {
        "name": "parallel",
        "arguments": json.dumps({"tool_uses": uses}),
    }
    return call


def _names(calls: list[dict[str, Any]]) -> list[str]:
    return [call["function"]["name"] for call in calls]


def test_unpacked_parallel_renumbers_every_indexed_call(
    limits: PassthroughLimits,
) -> None:
    calls = [_plain("c1", 5), _parallel("c2", 6)]
    result = sanitize_choice_calls(calls, None, limits)
    assert _names(result) == ["plain", "a", "b"]
    assert [call["index"] for call in result] == [0, 1, 2]


def test_unpacked_parallel_without_index_keys_stays_index_free(
    limits: PassthroughLimits,
) -> None:
    result = sanitize_choice_calls(
        [_plain("c1", None), _parallel("c2", None)], None, limits
    )
    assert _names(result) == ["plain", "a", "b"]
    assert all("index" not in call for call in result)


def test_unpacked_parallel_mixes_present_and_absent_index_keys(
    limits: PassthroughLimits,
) -> None:
    result = sanitize_choice_calls(
        [_plain("c1", None), _parallel("c2", 9)], None, limits
    )
    assert "index" not in result[0]
    assert [call.get("index") for call in result[1:]] == [1, 2]


def test_plain_calls_keep_their_original_indices(limits: PassthroughLimits) -> None:
    calls = [_plain("c1", 5), _plain("c2", 7)]
    result = sanitize_choice_calls(calls, None, limits)
    assert [(call["id"], call["index"]) for call in result] == [("c1", 5), ("c2", 7)]


def test_dropped_nameless_call_renumbers_survivors_contiguously(
    limits: PassthroughLimits,
) -> None:
    nameless = _plain("c0", 0)
    nameless["function"]["name"] = ""
    result = sanitize_choice_calls([nameless, _plain("c1", 4)], None, limits)
    assert [(call["id"], call["index"]) for call in result] == [("c1", 0)]


@pytest.mark.parametrize("spec", (OFF_SPEC, FORBID_SPEC))
def test_forbidding_modes_route_content_through_normalizer(spec: Any) -> None:
    text = _ResponseText(spec, None, True)
    assert text.feed({"content": "hello"}) == {"content": "hello"}
    assert text.finish() == {}


def test_off_text_holds_a_tag_prefix_until_finish() -> None:
    text = _ResponseText(OFF_SPEC, None, True)
    assert text.feed({"content": "hi <t"}) == {"content": "hi "}
    assert text.finish() == {"content": "<t"}


@pytest.mark.parametrize("value", ("", None, 5, ["x"], {"a": 1}))
def test_off_non_string_or_empty_content_is_left_untouched(value: Any) -> None:
    text = _ResponseText(OFF_SPEC, None, True)
    assert text.feed({"content": value, "role": "assistant"}) == {
        "content": value,
        "role": "assistant",
    }


def test_off_reasoning_string_is_routed_to_reasoning_output() -> None:
    text = _ResponseText(OFF_SPEC, None, True)
    result = text.feed({"reasoning_content": "why", "content": "a"})
    assert result == {"content": "a", "reasoning_content": "why"}


def test_off_empty_reasoning_string_is_consumed_and_omitted() -> None:
    text = _ResponseText(OFF_SPEC, None, True)
    assert text.feed({"reasoning_content": ""}) == {}


@pytest.mark.parametrize("value", (None, 5, ["x"]))
def test_off_non_string_reasoning_is_left_untouched(value: Any) -> None:
    text = _ResponseText(OFF_SPEC, None, True)
    assert text.feed({"reasoning_content": value}) == {"reasoning_content": value}


def test_emulate_without_parser_returns_a_copy_unchanged() -> None:
    text = _ResponseText(EMULATE_SPEC, None, False)
    delta = {"content": VALID_CALL, "reasoning_content": "r"}
    result = text.feed(delta)
    assert result == delta and result is not delta
    assert text.finish() == {} and text.calls == []


def test_emulate_parser_extracts_call_and_removes_content_key() -> None:
    text = _ResponseText(EMULATE_SPEC, None, True)
    result = text.feed({"content": VALID_CALL, "role": "assistant"})
    assert result == {"role": "assistant"}
    assert [call["name"] for call in text.calls] == ["noop"]


@pytest.mark.parametrize("value", ("", None, 7))
def test_emulate_parser_ignores_empty_or_non_string_content(value: Any) -> None:
    text = _ResponseText(EMULATE_SPEC, None, True)
    assert text.feed({"content": value}) == {"content": value}
    assert text.calls == []


def test_emulate_parser_never_takes_reasoning() -> None:
    text = _ResponseText(EMULATE_SPEC, None, True)
    result = text.feed({"reasoning_content": VALID_CALL})
    assert result == {"reasoning_content": VALID_CALL}
    assert text.calls == []


@pytest.mark.parametrize("calls", (None, {"id": "x"}, "x", 3))
def test_published_count_of_non_list_is_zero(calls: Any) -> None:
    assert _published_call_count(calls) == 0


@pytest.mark.parametrize(
    "calls,expected",
    (
        ([], 0),
        (["call", 5, None, ["id"]], 0),
        ([{"function": {"name": "x"}}], 0),
        ([{"id": ""}, {"id": None}], 0),
        ([{"id": "c1"}], 1),
        ([{"id": "a"}, "x", {"id": ""}, {"id": "b"}, {}], 2),
    ),
)
def test_published_count_counts_only_dicts_with_a_nonempty_id(
    calls: Any, expected: int
) -> None:
    assert _published_call_count(calls) == expected


@pytest.mark.parametrize(
    "error,expected",
    (
        ({"code": "rate", "message": "slow"}, ("rate", "slow")),
        ({"type": "overloaded", "message": "busy"}, ("overloaded", "busy")),
        ({"code": "c", "type": "t", "message": "m"}, ("c", "m")),
        ({}, ("upstream_stream_error", "{}")),
        ("boom", ("upstream_stream_error", "boom")),
    ),
)
def test_stream_error_info_prefers_code_then_type_then_default(
    error: Any, expected: tuple[str, str]
) -> None:
    assert _stream_error_info(error) == expected
