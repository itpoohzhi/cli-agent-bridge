from __future__ import annotations

# Контракт NativeTurnPayload: построение, изоляция мутаций, пустой запрос.

import copy

from core.native_turn_context import (
    NativeTurnPayload,
    build_native_turn_payload,
    get_current_native_payload,
    native_payload_scope,
)

FULL_BODY: dict[str, object] = {
    "model": "m",
    "messages": [{"role": "user", "content": "hi"}],
    "tools": [{"type": "function", "function": {"name": "f"}}],
    "tool_choice": {"type": "function", "function": {"name": "f"}},
    "prompt_cache_key": "key-1",
    "stream_options": {"include_usage": True},
    "scratch": "ignored",
}


def test_full_body_builds_payload() -> None:
    payload = build_native_turn_payload(FULL_BODY)
    assert payload is not None
    assert payload.to_messages_list() == FULL_BODY["messages"]
    assert payload.to_tools_list() == FULL_BODY["tools"]
    assert payload.tool_choice == FULL_BODY["tool_choice"]
    assert payload.prompt_cache_key == "key-1"
    assert payload.stream_options == {"include_usage": True}


def test_partial_body_keeps_only_present_fields() -> None:
    payload = build_native_turn_payload(
        {"messages": [{"role": "user", "content": "x"}]}
    )
    assert payload is not None
    assert payload.tools == ()
    assert payload.tool_choice is None
    assert payload.prompt_cache_key is None
    assert payload.stream_options is None


def test_empty_or_invalid_body_returns_none() -> None:
    assert build_native_turn_payload(None) is None
    assert build_native_turn_payload({}) is None
    assert (
        build_native_turn_payload({"messages": [], "tools": [], "prompt_cache_key": ""})
        is None
    )
    assert (
        build_native_turn_payload({"messages": "bad", "stream_options": "bad"}) is None
    )
    assert build_native_turn_payload(["not", "a", "mapping"]) is None  # type: ignore[arg-type]


def test_source_body_mutation_does_not_affect_payload() -> None:
    body = copy.deepcopy(FULL_BODY)
    payload = build_native_turn_payload(body)
    assert payload is not None
    messages = body["messages"]
    assert isinstance(messages, list)
    messages[0]["content"] = "mutated"
    messages.append({"role": "user", "content": "extra"})
    stream_options = body["stream_options"]
    assert isinstance(stream_options, dict)
    stream_options["include_usage"] = False
    assert payload.to_messages_list() == FULL_BODY["messages"]
    assert payload.stream_options == {"include_usage": True}


def test_returned_copies_do_not_mutate_payload() -> None:
    payload = build_native_turn_payload(FULL_BODY)
    assert payload is not None
    messages = payload.to_messages_list()
    messages[0]["content"] = "mutated"
    tools = payload.to_tools_list()
    tools.clear()
    choice = payload.to_tool_choice()
    assert isinstance(choice, dict)
    choice["type"] = "x"
    options = payload.to_stream_options()
    assert options is not None
    options["include_usage"] = False
    assert payload.to_messages_list() == FULL_BODY["messages"]
    assert payload.to_tools_list() == FULL_BODY["tools"]
    assert payload.tool_choice == FULL_BODY["tool_choice"]
    assert payload.stream_options == {"include_usage": True}


def test_payload_is_frozen_and_default_empty() -> None:
    payload = NativeTurnPayload()
    assert payload.messages == () and payload.tools == ()
    try:
        payload.prompt_cache_key = "x"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("NativeTurnPayload must be frozen")


def test_native_payload_scope_isolates_and_resets() -> None:
    payload = build_native_turn_payload(FULL_BODY)
    assert get_current_native_payload() is None
    with native_payload_scope(payload):
        assert get_current_native_payload() == payload
    assert get_current_native_payload() is None
