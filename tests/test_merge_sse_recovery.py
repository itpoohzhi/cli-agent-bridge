"""Регрессии завершения SSE и единого контракта credentials после merge."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from adapters.passthrough_adapter import (
    PassthroughAdapter,
    PassthroughLimits,
    sanitize_completion_body,
)
from core.tool_emulation import LiveParserError
from tests.test_empty_tool_call_recovery import _agy_server
from tests.test_merge_recovery_contracts import _handler, _runner
from tests.transport_test_support import RecordingSink


@pytest.mark.parametrize("buffering", [False, True])
@pytest.mark.parametrize("preamble", [False, True])
@pytest.mark.parametrize(
    "block",
    [
        '<tool_call>{"name":"","arguments":{}}</tool_call>',
        '<tool_call>{"name":"parallel","arguments":{"calls":[{"arguments":{}}]}}</tool_call>',
        '<tool_call>{"name":"parallel","arguments":{"calls":[{"name":"read","arguments":{}},{"arguments":{}}]}}</tool_call>',
        '<tool_call>{"name":"read","arguments":',
    ],
)
def test_real_runner_finishes_parser_error(
    monkeypatch: pytest.MonkeyPatch, buffering: bool, preamble: bool, block: str
) -> None:
    runner, wire = _runner(monkeypatch), []
    monkeypatch.setenv("BRIDGE_STREAM_TOOL_ROLLBACK_ENABLED", str(buffering).lower())
    handler = _handler(wire, {"state": "done", "rc": 0}, content=False)

    def once(_ctx: dict, text: Any, _trace: Any, reasoning: Any, _alive: Any) -> dict:
        if preamble:
            reasoning("uncommitted preamble")
        text(block)
        return {"state": "done", "rc": 0}

    handler._run_once = once
    ctx = {"model": "fixture", "emulate_tools": True}
    hooks = (
        lambda _key, default=False: default,
        Mock(),
        lambda: "stop",
        _agy_server()._ToolTurn,
    )
    runner.serve_sse_body(handler, ctx, hooks)
    _assert_parse_error(handler, ctx, wire, preamble)
    if buffering:
        assert "uncommitted preamble" not in "".join(wire)


def _assert_parse_error(
    handler: Any, ctx: dict, wire: list[str], preamble: bool
) -> None:
    if not preamble:
        assert not wire and not ctx["stream_committed"]
        status, body = handler._send.call_args.args
        assert status == 502 and body["error"]["type"] == "tool_call_parse_error"
    else:
        frames = [json.loads(part[6:]) for part in wire if part.startswith("data: {")]
        assert [f["error"]["type"] for f in frames if "error" in f] == [
            "tool_call_parse_error"
        ]
        assert wire.count("data: [DONE]\n\n") == 1
        assert wire[-1] == "data: [DONE]\n\n"
        assert all("tool_calls" not in c["delta"] for f in frames for c in f["choices"])


def _adapter(config: dict[str, Any]) -> PassthroughAdapter:
    return PassthroughAdapter(
        "fixture",
        {
            "base_url": "http://127.0.0.1:1/v1",
            "max_concurrent": 1,
            "trusted_tool_sanitizer": True,
            **config,
        },
        lambda: {},
        SimpleNamespace(is_trusted_tool_streaming_enabled=lambda: True),
    )


def _check_credentials(adapter: PassthroughAdapter, expected: str) -> None:
    assert adapter._upstream_key == expected
    assert adapter.validate_client_token(expected) is bool(expected)
    assert not adapter.validate_client_token("stale-static-key")
    response = Mock()
    response.getheader.return_value = "1"
    assert adapter._trusted_tools(response, True) is bool(expected)


@pytest.mark.parametrize("field", ["api_key_env", "api_key_ref"])
def test_adapter_auth_and_trust_follow_hot_env_revocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    env_file = tmp_path / ".env"
    monkeypatch.setenv("BRIDGE_ENV_FILE_PATH", str(env_file))
    monkeypatch.setenv("BRIDGE_ENV_CACHE_TTL_S", "0")
    monkeypatch.setenv("MERGE_AUTH_KEY", "stale-process-key")
    value = "env:MERGE_AUTH_KEY" if field == "api_key_ref" else "MERGE_AUTH_KEY"
    adapter = _adapter({field: value, "api_key": "stale-static-key"})
    try:
        for key in ("first-live-key", "rotated-live-key", ""):
            env_file.write_text(f'MERGE_AUTH_KEY="{key}"\n', encoding="utf-8")
            _check_credentials(adapter, key)
    finally:
        adapter.shutdown()


def test_adapter_auth_and_trust_follow_file_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key_file = tmp_path / "credential"
    monkeypatch.setenv("MERGE_AUTH_KEY", "lower-priority-env")
    adapter = _adapter(
        {
            "api_key_ref": f"file:{key_file}",
            "api_key_env": "MERGE_AUTH_KEY",
            "api_key": "stale-static-key",
        }
    )
    try:
        for key in ("first-file-key", "rotated-file-key", ""):
            key_file.write_text(key + "\n", encoding="utf-8")
            _check_credentials(adapter, key)
        key_file.unlink()
        _check_credentials(adapter, "")
        key_file.write_bytes(b"\xff")
        _check_credentials(adapter, "")
    finally:
        adapter.shutdown()


def test_upstream_key_override_remains_explicit() -> None:
    adapter = _adapter({"api_key": "configured-key"})
    try:
        adapter._upstream_key = "override-key"
        assert adapter.validate_client_token("override-key")
        adapter._upstream_key = ""
        assert not adapter.validate_client_token("configured-key")
        adapter._upstream_key = None
        assert adapter.validate_client_token("configured-key")
    finally:
        adapter.shutdown()


@pytest.mark.parametrize("source", [None, "api_key_env", "api_key_ref"])
def test_local_utf8_literal_never_bypasses_declared_source(source: str | None) -> None:
    config = {"api_key": "ключ"}
    if source is not None:
        config[source] = (
            "env:MERGE_ABSENT_KEY" if source == "api_key_ref" else "MERGE_ABSENT_KEY"
        )
    adapter = _adapter(config)
    try:
        assert adapter.validate_client_token("ключ") is (source is None)
        assert not adapter._upstream_key
        adapter._upstream_key = ""
        assert not adapter.validate_client_token("ключ")
    finally:
        adapter.shutdown()


@pytest.mark.parametrize("name", ["", " ", None])
@pytest.mark.parametrize("valid_sibling", [False, True])
def test_nonstream_unnamed_call_fails_closed(
    name: str | None, valid_sibling: bool
) -> None:
    calls = [
        {"id": "c", "type": "function", "function": {"name": name, "arguments": "{}"}}
    ]
    if valid_sibling:
        calls.insert(0, {"function": {"name": "read", "arguments": "{}"}})
    body = json.dumps(
        {"choices": [{"message": {"content": "", "tool_calls": calls}}]}
    ).encode()
    with pytest.raises(LiveParserError):
        sanitize_completion_body(body, None, PassthroughLimits())


@pytest.mark.parametrize("usage", [None, {"total_tokens": 0}, {"total_tokens": 15}])
def test_io_error_retains_only_positive_usage(usage: dict | None) -> None:
    adapter, sink = _adapter({}), RecordingSink()
    chunk = {
        "id": "fixture-completion",
        "created": 123,
        "model": "fixture-model",
        "choices": [
            {"index": 0, "delta": {"content": "partial"}, "finish_reason": None}
        ],
        "usage": usage,
    }
    response = Mock()
    response.getheaders.return_value = [("Content-Type", "text/event-stream")]
    response.getheader.return_value = None
    response.readline.side_effect = [
        ("data: " + json.dumps(chunk) + "\n").encode(),
        b"\n",
        OSError("fixture"),
    ]
    try:
        assert not adapter._relay_stream(response, None, sink, True)
    finally:
        adapter.shutdown()
    frames = sink.body.decode().strip().split("\n\n")
    error = json.loads(frames[-2][6:])
    assert error.get("usage") == (usage if usage and usage["total_tokens"] else None)
    assert ("usage" in error) is bool(usage and usage["total_tokens"])
    assert (error["id"], error["created"], error["model"]) == (
        "fixture-completion",
        123,
        "fixture-model",
    )
    assert frames[-1] == "data: [DONE]"
