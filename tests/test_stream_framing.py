"""Tests for centralized stream error framing."""

import json

import pytest

from core.stream_framing import (
    build_stream_error_chunk,
    format_sse_event,
    format_stream_error_sse,
    is_graceful_error_framing_enabled,
    sanitize_error_message,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Authorization: Bearer abc_DEF-123.xyz", "Authorization: Bearer ***"),
        ("bearer aaaaaaaaaa+bbbbbbbbbb/cccc====", "Bearer ***"),
        ("BEARER secret~token.123", "Bearer ***"),
        ("Authorization: Basic dXNlcjpwYXNzMTIz", "Authorization: Basic ***"),
        ("API key sk-proj_ABC-123+xyz/test==", "API key sk-***"),
        ("Connect failed to https://user:secret@api.example.com/v1", "Connect failed to https://***:***@api.example.com/v1"),
        ("Error with api_key=secret-token-123 in url", "Error with api_key=*** in url"),
        ("password: topsecret123", "password=***"),
        ('{"password": "demo-password-456"}', '{password=***}'),
        ('{"password": "correct horse battery"}', '{password=***}'),
        ('{"client_secret": "my very secret value"}', '{client_secret=***}'),
        ("passwd=hunter2secret", "passwd=***"),
        ('{"passwd": "hunter2secret"}', '{passwd=***}'),
        ("pwd: mypass", "pwd=***"),
        ("private_key=secretkey123", "private_key=***"),
        ("GET /v1?access_key=AKIA1234567890ABCDEF", "GET /v1?access_key=***"),
        ("postgres://dbuser:dbpass123@db.internal:5432/app", "postgres://***:***@db.internal:5432/app"),
        ("https://glpat-token123@gitlab.example.com/repo", "https://***@gitlab.example.com/repo"),
        ("key AIzaSyD1234567890abcdefghijklmnopqrstuv rejected", "key AIza*** rejected"),
        ("failed with AKIAIOSFODNN7EXAMPLE", "failed with AKIA***"),
        ("{'token': 'demo-token-789'}", "{token=***}"),
        ('{"api_key": "my-secret-key-123"}', '{api_key=***}'),
        ('{"secret": "val", "credential": "cred"}', '{secret=***, credential=***}'),
        ("Cannot open /Users/alice/project/file.py", "Cannot open ~/project/file.py"),
        ("cwd=/Users/alice", "cwd=~"),
        ("Cannot open /home/ubuntu/app/server.py", "Cannot open ~/app/server.py"),
        ("path is /home/deploy in container", "path is ~ in container"),
        (
            "Bearer sk-secret.key sk-other.key /Users/alice/project",
            "Bearer *** sk-*** ~/project",
        ),
        ("ordinary message", "ordinary message"),
        ("", ""),
    ],
)
def test_sanitize_error_message(message, expected):
    assert sanitize_error_message(message) == expected


def test_graceful_framing_defaults_to_enabled(monkeypatch):
    monkeypatch.delenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", raising=False)
    assert is_graceful_error_framing_enabled() is True
    assert build_stream_error_chunk("failure")["choices"][0]["finish_reason"] == "stop"


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "YES"])
def test_graceful_framing_enabled(monkeypatch, value):
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", value)
    assert is_graceful_error_framing_enabled() is True
    chunk = build_stream_error_chunk("failure")
    assert chunk["choices"][0]["finish_reason"] == "stop"
    assert chunk["choices"][0]["delta"]["content"]


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "NO", "disabled"])
def test_graceful_framing_disabled(monkeypatch, value):
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", value)
    assert is_graceful_error_framing_enabled() is False
    chunk = build_stream_error_chunk("failure")
    assert chunk["choices"][0]["finish_reason"] is None
    assert json.loads(json.dumps(chunk))["choices"][0]["finish_reason"] is None
    assert chunk["choices"][0]["delta"] == {}


def test_configuration_is_read_at_call_time(monkeypatch):
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "true")
    assert build_stream_error_chunk("first")["choices"][0]["finish_reason"] == "stop"
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "false")
    assert build_stream_error_chunk("second")["choices"][0]["finish_reason"] is None


@pytest.mark.parametrize(
    ("enabled", "override"),
    [("true", None), ("false", "stop"), ("true", "length")],
)
def test_explicit_finish_reason_overrides_configuration(monkeypatch, enabled, override):
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", enabled)
    chunk = build_stream_error_chunk("failure", finish_reason=override)
    assert chunk["choices"][0]["finish_reason"] == override


def test_chunk_schema(monkeypatch):
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "true")
    chunk = build_stream_error_chunk(
        "failure",
        model="test-model",
        code="upstream_timeout",
        completion_id="chatcmpl-test",
        created=123,
    )
    assert chunk == {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 123,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "delta": {"content": "\n\n[⚠️ Ошибка шлюза: failure]"},
                "finish_reason": "stop",
            }
        ],
        "error": {
            "message": "failure",
            "type": "stream_error",
            "code": "upstream_timeout",
            "param": None,
        },
    }


def test_default_metadata(monkeypatch):
    monkeypatch.setattr("core.stream_framing.time.time", lambda: 1234.9)
    chunk = build_stream_error_chunk("failure")
    assert chunk["id"] == "chatcmpl-err-1234"
    assert chunk["created"] == 1234
    assert chunk["model"] == "bridge-stream"
    assert chunk["error"]["code"] == "stream_error"


def test_multi_choice_error_chunk(monkeypatch):
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "true")
    chunk = build_stream_error_chunk(
        "timeout on secondary choice",
        model="gpt-4o",
        choice_indices=[1, 2],
        completion_id="chatcmpl-multi-123",
        created=999,
    )
    assert chunk["id"] == "chatcmpl-multi-123"
    assert chunk["created"] == 999
    assert chunk["model"] == "gpt-4o"
    assert len(chunk["choices"]) == 2
    assert chunk["choices"][0]["index"] == 1
    assert chunk["choices"][0]["finish_reason"] == "stop"
    assert "timeout on secondary choice" in chunk["choices"][0]["delta"]["content"]
    assert chunk["choices"][1]["index"] == 2
    assert chunk["choices"][1]["finish_reason"] == "stop"
    assert "timeout on secondary choice" in chunk["choices"][1]["delta"]["content"]


def test_empty_choice_indices(monkeypatch):
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "true")
    chunk = build_stream_error_chunk("timeout", choice_indices=[])
    assert chunk["choices"] == []


def test_falsy_metadata_preservation():
    chunk = build_stream_error_chunk("failure", completion_id="", created=0, model="")
    assert chunk["id"] == ""
    assert chunk["created"] == 0
    assert chunk["model"] == ""


def test_sanitization_applies_to_both_message_locations():
    chunk = build_stream_error_chunk(
        "Bearer secret.token sk-private.key /Users/alice/project"
    )
    expected = "Bearer *** sk-*** ~/project"
    assert chunk["error"]["message"] == expected
    assert chunk["choices"][0]["delta"]["content"] == (
        f"\n\n[⚠️ Ошибка шлюза: {expected}]"
    )
    serialized = json.dumps(chunk, ensure_ascii=False)
    for secret in ("secret.token", "sk-private.key", "/Users/alice/"):
        assert secret not in serialized


def test_format_sse_event_dictionary():
    result = format_sse_event({"message": "Ошибка"}, event="message")
    assert result.startswith("event: message\ndata: ")
    assert result.endswith("\n\n")
    assert json.loads(result.split("data: ", 1)[1].strip()) == {"message": "Ошибка"}


def test_format_sse_event_multiline_string():
    assert format_sse_event("first\nsecond") == "data: first\ndata: second\n\n"


def test_terminal_sse_sequence(monkeypatch):
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "true")
    result = format_stream_error_sse(
        "failure",
        model="test-model",
        code="timeout",
        completion_id="chatcmpl-terminal",
        created=456,
    )
    assert result.endswith("\n\ndata: [DONE]\n\n")
    assert result.count("data: [DONE]") == 1
    events = result.split("\n\n")
    assert len(events) == 3
    assert events[1] == "data: [DONE]"
    assert events[2] == ""
    chunk = json.loads(events[0][len("data: "):])
    assert chunk["object"] == "chat.completion.chunk"
    assert chunk["id"] == "chatcmpl-terminal"
    assert chunk["created"] == 456
    assert chunk["model"] == "test-model"
    assert chunk["error"]["code"] == "timeout"
    assert chunk["choices"][0]["finish_reason"] == "stop"


def test_terminal_sse_respects_disabled_framing(monkeypatch):
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "false")
    result = format_stream_error_sse("failure")
    chunk = json.loads(result.split("\n\n", 1)[0][len("data: "):])
    assert chunk["choices"][0]["finish_reason"] is None
    assert result.endswith("data: [DONE]\n\n")


def test_terminal_sse_preserves_explicit_none(monkeypatch):
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "true")
    result = format_stream_error_sse("failure", finish_reason=None)
    chunk = json.loads(result.split("\n\n", 1)[0][len("data: "):])
    assert chunk["choices"][0]["finish_reason"] is None
