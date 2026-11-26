from __future__ import annotations

# Контракт сборки тела/заголовков loopback Zero-Canon proxy.

import pytest

from core.native_turn_context import build_native_turn_payload
from core.stdio_resident.bridge_proxy_payload import (
    BridgeProxyOptions,
    build_bridge_proxy_body,
    build_bridge_proxy_headers,
)

NATIVE_BODY: dict[str, object] = {
    "messages": [{"role": "user", "content": "native"}],
    "tools": [{"type": "function", "function": {"name": "f"}}],
    "tool_choice": "auto",
    "prompt_cache_key": "native-key",
    "stream_options": {"include_usage": True},
}


@pytest.fixture(autouse=True)
def _no_bridge_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_P_BRIDGE_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_BRIDGE_KEY", raising=False)


def test_body_full_allowlist() -> None:
    native = build_native_turn_payload(NATIVE_BODY)
    opts = BridgeProxyOptions(reasoning_effort="high", native_payload=native)
    body = build_bridge_proxy_body("m", "legacy", opts)
    assert body == {
        "model": "m",
        "messages": NATIVE_BODY["messages"],
        "stream": False,
        "prompt_cache_key": "native-key",
        "reasoning_effort": "high",
        "tools": NATIVE_BODY["tools"],
        "tool_choice": "auto",
        "stream_options": {"include_usage": True},
    }


def test_body_legacy_fallback_without_options() -> None:
    body = build_bridge_proxy_body("m", "hello")
    assert body == {
        "model": "m",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
    }


def test_body_explicit_cache_key_has_priority() -> None:
    native = build_native_turn_payload(NATIVE_BODY)
    opts = BridgeProxyOptions(prompt_cache_key="explicit", native_payload=native)
    assert build_bridge_proxy_body("m", "p", opts)["prompt_cache_key"] == "explicit"


def test_body_stream_always_false_and_isolated_copies() -> None:
    native = build_native_turn_payload({**NATIVE_BODY, "stream": True})
    assert native is not None
    body = build_bridge_proxy_body("m", "p", BridgeProxyOptions(native_payload=native))
    assert body["stream"] is False
    messages = body["messages"]
    assert isinstance(messages, list)
    messages[0]["content"] = "mutated"
    assert native.to_messages_list() == NATIVE_BODY["messages"]


def test_body_native_without_messages_uses_prompt() -> None:
    native = build_native_turn_payload({"tools": NATIVE_BODY["tools"]})
    body = build_bridge_proxy_body(
        "m", "fallback", BridgeProxyOptions(native_payload=native)
    )
    assert body["messages"] == [{"role": "user", "content": "fallback"}]
    assert body["tools"] == NATIVE_BODY["tools"]
    assert "tool_choice" not in body


def test_headers_base_and_review_profile() -> None:
    headers = build_bridge_proxy_headers(None)
    assert headers == {
        "Content-Type": "application/json",
        "X-Review-Profile": "zero-canon",
    }


def test_headers_valid_chat_id_forwarded() -> None:
    headers = build_bridge_proxy_headers({}, chat_id="chat-42")
    assert headers["X-DSH-Chat-Id"] == "chat-42"


@pytest.mark.parametrize("bad", [None, "", "   ", "a\nb", "x" * 600])
def test_headers_invalid_chat_id_fail_open(bad: str | None) -> None:
    headers = build_bridge_proxy_headers({}, chat_id=bad)
    assert "X-DSH-Chat-Id" not in headers
    assert headers["X-Review-Profile"] == "zero-canon"


def test_headers_unknown_filtered_and_known_passed() -> None:
    base = {
        "X-Evil": "1",
        "x-subagent-id": "sub-1",
        "Authorization": "Bearer t",
        "X-Review-Profile": "standard",
    }
    headers = build_bridge_proxy_headers(base)
    assert headers == {
        "Content-Type": "application/json",
        "X-Review-Profile": "zero-canon",
        "X-Subagent-Id": "sub-1",
        "Authorization": "Bearer t",
    }


def test_headers_env_bridge_key_sets_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_BRIDGE_KEY", "secret")
    assert build_bridge_proxy_headers(None)["Authorization"] == "Bearer secret"
