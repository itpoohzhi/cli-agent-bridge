"""Verification tests for OpenCode ACP stdio resident protocol driver and adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters import ADAPTER_KINDS
from adapters.stdio_drivers import infer_protocol, is_opencode_resident_enabled
from adapters.stdio_drivers.opencode_driver import OpenCodeAcpDriver, OpenCodeDecodedChunk
from adapters.stdio_resident_adapter import StdioResidentAdapter
from core.provider_manifest import load_manifests
from core.stdio_resident.process_io import TaggedLine
from core.stdio_resident.rpc_drivers import create_protocol_driver


class _MockHandle:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def read_line(self, timeout_s: float | None = None) -> TaggedLine | None:
        _ = timeout_s
        if not self._responses:
            return None
        resp = self._responses.pop(0)
        line = json.dumps(resp, ensure_ascii=False) + "\n"
        return TaggedLine(line=line, generation=0, pid=12345, is_stderr=False)


def test_driver_framing() -> None:
    """[VER-001] Test ACP protocol capabilities, argv formatting, handshake, and error handling."""
    driver = OpenCodeAcpDriver()

    assert driver.capabilities.protocol_name == "opencode-acp"
    assert driver.capabilities.supports_soft_cancel is True
    assert driver.capabilities.supports_multi_turn is True

    # build_argv
    argv = driver.build_argv(["/usr/local/bin/opencode"], {})
    assert argv == ["/usr/local/bin/opencode", "acp"]

    # handshake payload
    req_id, handshake = driver.handshake_payload()
    assert req_id > 0
    assert handshake.endswith(b"\n")
    hs_obj = json.loads(handshake)
    assert hs_obj["id"] == req_id
    assert hs_obj["method"] == "initialize"
    assert hs_obj["params"]["protocolVersion"] == 1

    # decode streaming content_part_delta
    delta_chunk = driver.decode_line(
        json.dumps({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "ses-123",
                "update": {
                    "sessionUpdate": "content_part_delta",
                    "delta": {"text": "Hello world", "reasoning": "Thinking step"},
                },
            },
        })
    )
    assert delta_chunk is not None
    assert delta_chunk.text == "Hello world"
    assert delta_chunk.reasoning == "Thinking step"
    assert delta_chunk.is_terminal is False

    # decode agent_message_chunk and agent_thought_chunk
    msg_chunk = driver.decode_line(
        json.dumps({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "ses-123",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": "Message stream fragment",
                },
            },
        })
    )
    assert msg_chunk is not None
    assert msg_chunk.text == "Message stream fragment"

    thought_chunk = driver.decode_line(
        json.dumps({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "ses-123",
                "update": {
                    "sessionUpdate": "agent_thought_chunk",
                    "thought": "Deep thinking fragment",
                },
            },
        })
    )
    assert thought_chunk is not None
    assert thought_chunk.reasoning == "Deep thinking fragment"

    # decode tool call
    tool_chunk = driver.decode_line(
        json.dumps({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "ses-123",
                "update": {
                    "sessionUpdate": "tool_call",
                    "toolCall": {"name": "read_file", "arguments": {"path": "/tmp/a.txt"}},
                },
            },
        })
    )
    assert tool_chunk is not None
    assert tool_chunk.is_tool_stop is True
    assert driver.is_tool_stop("", tool_chunk) is True

    # permission handling generates auto-allow reply_bytes
    perm_chunk = driver.decode_line(
        json.dumps({
            "jsonrpc": "2.0",
            "id": 42,
            "method": "session/request_permission",
            "params": {"sessionId": "ses-123", "permission": "filesystem"},
        })
    )
    assert isinstance(perm_chunk, OpenCodeDecodedChunk)
    assert perm_chunk.reply_bytes is not None
    perm_reply = json.loads(perm_chunk.reply_bytes.decode("utf-8"))
    assert perm_reply["id"] == 42
    assert perm_reply["result"]["decision"] == "allow"

    # error handling propagates error field and marks terminal
    err_chunk = driver.decode_line(
        json.dumps({
            "jsonrpc": "2.0",
            "id": 99,
            "error": {"code": -32000, "message": "Auth failure"},
        })
    )
    assert isinstance(err_chunk, OpenCodeDecodedChunk)
    assert err_chunk.is_terminal is True
    assert err_chunk.error == "Auth failure"
    assert driver.is_terminal("", err_chunk) is True


def test_environment_and_db_isolation() -> None:
    """[VER-002] Test in-memory DB isolation, config merging, and credential preservation."""
    driver = OpenCodeAcpDriver()

    base_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/Users/test",
        "XDG_DATA_HOME": "/Users/test/.local/share",
        "DEEPSEEK_API_KEY": "sk-deepseek-test",
        "OPENCODE_CONFIG_CONTENT": json.dumps({
            "provider": {
                "opencode-go": {"options": {"baseURL": "http://127.0.0.1:10830/go/v1/v1beta"}}
            }
        }),
    }

    env = driver.build_env(base_env, turn_sandbox="/tmp/slot-123")

    # In-memory SQLite DB
    assert env["OPENCODE_DB"] == ":memory:"
    assert env["TMPDIR"] == "/tmp/slot-123"

    # Credentials preserved
    assert env["DEEPSEEK_API_KEY"] == "sk-deepseek-test"
    assert env["HOME"] == "/Users/test"
    assert env["XDG_DATA_HOME"] == "/Users/test/.local/share"

    # Config merging preserved provider routing and added permission
    merged_config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
    assert "provider" in merged_config
    assert "opencode-go" in merged_config["provider"]
    assert merged_config["provider"]["opencode-go"]["options"]["baseURL"] == "http://127.0.0.1:10830/go/v1/v1beta"
    assert merged_config["permission"]["*"] == "allow"


def test_session_lifecycle_and_hot_turns() -> None:
    """[VER-003] Test session/new creation, sessionId capture, and multi-turn prompt reuse."""
    driver = OpenCodeAcpDriver()

    # Create session/new payload
    req_id, new_bytes = driver.build_session_new_payload("/tmp/project", "opencode-go/deepseek-v4.1-flash", "high")
    assert req_id > 0
    new_obj = json.loads(new_bytes)
    assert new_obj["id"] == req_id
    assert new_obj["method"] == "session/new"
    assert new_obj["params"]["model"] == "opencode-go/deepseek-v4.1-flash"
    assert new_obj["params"]["effort"] == "high"
    assert new_obj["params"]["mcpServers"] == []

    # Simulate response from opencode acp with sessionId
    resp_line = json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {"sessionId": "ses_verified_999"},
    })
    driver.decode_line(resp_line)
    assert driver.active_session_id == "ses_verified_999"

    # Turn 1: encode_turn should use cached sessionId
    turn1_bytes = driver.encode_turn("Первый ход")
    turn1_obj = json.loads(turn1_bytes)
    assert turn1_obj["method"] == "session/prompt"
    assert turn1_obj["params"]["sessionId"] == "ses_verified_999"
    assert turn1_obj["params"]["prompt"][0]["text"] == "Первый ход"
    turn1_id = turn1_obj["id"]

    # Terminal completion of Turn 1
    term_line = json.dumps({"jsonrpc": "2.0", "id": turn1_id, "result": {}})
    term_chunk = driver.decode_line(term_line)
    assert term_chunk is not None
    assert term_chunk.is_terminal is True
    assert driver.is_terminal(term_line, term_chunk) is True

    # Turn 2: Hot turn reuses the exact same sessionId without session/new
    turn2_bytes = driver.encode_turn("Второй ход")
    turn2_obj = json.loads(turn2_bytes)
    assert turn2_obj["params"]["sessionId"] == "ses_verified_999"
    assert turn2_obj["params"]["prompt"][0]["text"] == "Второй ход"

    # Cancellation
    cancel_bytes = driver.build_cancel_payload()
    assert cancel_bytes is not None
    cancel_obj = json.loads(cancel_bytes)
    assert cancel_obj["method"] == "session/cancel"
    assert cancel_obj["params"]["sessionId"] == "ses_verified_999"


def test_handshake_and_prepare_turn_with_handle() -> None:
    """[VER-004] Test run_handshake and prepare_turn coordination with process handle."""
    driver = OpenCodeAcpDriver()

    # Cold start handshake
    mock_handle = _MockHandle([
        {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": 1}},
        {"jsonrpc": "2.0", "id": 2, "result": {"sessionId": "ses-auto-456"}},
    ])

    assert driver.run_handshake(mock_handle, timeout_s=2.0) is True
    assert len(mock_handle.writes) == 1
    hs_sent = json.loads(mock_handle.writes[0])
    assert hs_sent["method"] == "initialize"

    # Cold start prepare_turn sends session/new and captures sessionId
    turn_ctx = {"cwd": "/tmp/repo", "model": "opencode-go/deepseek-v4.1-flash"}
    assert driver.prepare_turn(mock_handle, turn_ctx, timeout_s=2.0) is True
    assert driver.active_session_id == "ses-auto-456"
    assert len(mock_handle.writes) == 2
    sn_sent = json.loads(mock_handle.writes[1])
    assert sn_sent["method"] == "session/new"

    # Hot turn prepare_turn returns True immediately without extra writes
    assert driver.prepare_turn(mock_handle, turn_ctx, timeout_s=2.0) is True
    assert len(mock_handle.writes) == 2


def test_kill_switch_and_preflight(monkeypatch: Any) -> None:
    """[VER-005] Test feature flag kill-switch gating and preflight checks."""
    adapter_config = {
        "kind": "stdio_resident",
        "provider_id": "opencode-resident",
        "options": {"protocol": "opencode-acp"},
    }

    # Enabled stdio pool but disabled opencode resident flag
    monkeypatch.setenv("BRIDGE_STDIO_RESIDENT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_OPENCODE_RESIDENT_ENABLED", "0")
    adapter = StdioResidentAdapter("opencode-resident", adapter_config)
    assert is_opencode_resident_enabled() is False
    assert adapter.preflight_check() is False
    assert adapter.qualify().ok is False

    # Enabled opencode resident flag
    monkeypatch.setenv("BRIDGE_OPENCODE_RESIDENT_ENABLED", "1")
    assert is_opencode_resident_enabled() is True
    assert adapter.preflight_check() is True
    assert adapter.qualify().ok is True


def test_protocol_registration() -> None:
    """[VER-006] Test protocol driver registration and StdioResidentAdapter options validation."""
    driver = create_protocol_driver("opencode-acp")
    assert isinstance(driver, OpenCodeAcpDriver)
    assert driver.capabilities.protocol_name == "opencode-acp"

    assert infer_protocol("opencode-resident", {}, {}) == "opencode-acp"
    assert infer_protocol("custom", {"wrapper": "/opt/bin/opencode"}, {}) == "opencode-acp"

    allowed_protocols = StdioResidentAdapter.CONSTRAINTS.options_schema.get("protocol", ())
    assert "opencode-acp" in allowed_protocols


def test_manifest_loaded_cleanly() -> None:
    """[VER-007] Test providers.d/opencode-resident.yaml validity and load_manifests acceptance."""
    repo_root = Path(__file__).resolve().parent.parent
    providers_dir = repo_root / "providers.d"
    loaded = load_manifests(providers_dir, ADAPTER_KINDS)
    assert "opencode-resident" not in dict(loaded.rejected_providers)
    opencode_manifest = next((m for m in loaded.manifests if m.provider_id == "opencode-resident"), None)
    assert opencode_manifest is not None
    assert opencode_manifest.kind == "stdio_resident"
    assert opencode_manifest.owned_by == "opencode"
    assert opencode_manifest.discovery.static == (
        "opencode-go/deepseek-v4.1-flash",
        "opencode-go/claude-haiku-5-5",
    )
