"""Unit-тесты домена MCP tool-capture (0 сокетов, 0 subprocess, 0 sleep)."""

from __future__ import annotations

# pyright: reportAny=false, reportExplicitAny=false
import json
from typing import Any

from core.stdio_resident.mcp_tool_capture import (
    McpToolCaptureSession,
    McpToolCaptureSpec,
)
from core.tool_mode import ToolMode

TOOL_SCHEMAS: dict[str, Any] = {
    "bash": {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command",
            "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}},
        },
    },
    "read_file": {
        "name": "read_file",
        "description": "Read a file",
        "parameters": {"properties": {"path": {"type": "string"}}},
    },
}


def _session(
    mode: ToolMode = ToolMode.EMULATE, max_calls: int = 32
) -> McpToolCaptureSession:
    spec = McpToolCaptureSpec.create(TOOL_SCHEMAS, tool_mode=mode, max_calls=max_calls)
    return McpToolCaptureSession(spec)


def _body(session: McpToolCaptureSession, payload: dict[str, Any]) -> dict[str, Any]:
    resp = session.handle_rpc_request(payload)
    assert resp.body is not None
    return resp.body


def _call(name: str, arguments: Any, req_id: Any = 7) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def test_initialize_returns_server_info() -> None:
    body = _body(
        _session(),
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    result = body["result"]
    assert result["protocolVersion"] == "2025-03-26"
    assert result["capabilities"] == {"tools": {}}
    assert result["serverInfo"] == {"name": "bridge", "version": "1.0.0"}


def test_notifications_return_202_without_body() -> None:
    session = _session()
    for method in ("notifications/initialized", "notifications/cancelled"):
        resp = session.handle_rpc_request({"jsonrpc": "2.0", "method": method})
        assert resp.http_status == 202
        assert resp.body is None


def test_ping_returns_empty_result() -> None:
    body = _body(_session(), {"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert body["result"] == {}
    assert body["id"] == 2


def test_unknown_method_returns_32601() -> None:
    body = _body(_session(), {"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
    assert body["error"]["code"] == -32601
    assert "method not found: resources/list" in body["error"]["message"]


def test_invalid_jsonrpc_and_method_return_32600() -> None:
    session = _session()
    bad_version = session.handle_rpc_request({"jsonrpc": "1.0", "id": 4, "method": "ping"})
    assert bad_version.body is not None
    assert bad_version.body["error"]["code"] == -32600
    bad_method = session.handle_rpc_request({"jsonrpc": "2.0", "id": 5, "method": ""})
    assert bad_method.body is not None
    assert bad_method.body["error"]["code"] == -32600


def test_tools_list_exports_openai_schemas() -> None:
    body = _body(_session(), {"jsonrpc": "2.0", "id": 6, "method": "tools/list"})
    tools = body["result"]["tools"]
    by_name = {tool["name"]: tool for tool in tools}
    assert set(by_name) == {"bash", "read_file"}
    assert by_name["bash"]["description"] == "Run a shell command"
    assert by_name["bash"]["inputSchema"]["type"] == "object"
    assert by_name["bash"]["inputSchema"]["properties"] == {"cmd": {"type": "string"}}
    assert by_name["read_file"]["inputSchema"]["type"] == "object"
    assert by_name["read_file"]["inputSchema"]["properties"] == {"path": {"type": "string"}}


def test_tools_list_empty_in_forbid_and_off_modes() -> None:
    for mode in (ToolMode.FORBID, ToolMode.OFF):
        body = _body(_session(mode), {"jsonrpc": "2.0", "id": 6, "method": "tools/list"})
        assert body["result"]["tools"] == []


def test_tools_call_captures_with_prefix_stripping() -> None:
    for raw_name in ("mcp__bridge__bash", "bridge__bash", "bridge:bash", "custom__bash", "bash"):
        session = _session()
        resp = session.handle_rpc_request(_call(raw_name, {"cmd": "ls"}))
        assert resp.captured_tool_call is True
        calls = session.snapshot_captured_calls()
        assert len(calls) == 1
        assert calls[0]["index"] == 0
        assert calls[0]["id"] == "call_mcp_0"
        assert calls[0]["type"] == "function"
        assert calls[0]["function"]["name"] == "bash"
        assert json.loads(calls[0]["function"]["arguments"]) == {"cmd": "ls"}
        assert session.has_captured_calls() is True


def test_tools_call_accepts_json_string_arguments() -> None:
    session = _session()
    resp = session.handle_rpc_request(_call("bash", '{"cmd": "echo hi"}'))
    assert resp.captured_tool_call is True
    calls = session.snapshot_captured_calls()
    assert json.loads(calls[0]["function"]["arguments"]) == {"cmd": "echo hi"}


def test_tools_call_forbidden_modes_fail_closed() -> None:
    for mode in (ToolMode.FORBID, ToolMode.OFF):
        session = _session(mode)
        resp = session.handle_rpc_request(_call("bash", {"cmd": "ls"}))
        assert resp.captured_tool_call is False
        assert resp.body is not None
        assert resp.body["error"]["code"] == -32001
        assert session.has_captured_calls() is False


def test_tools_call_unknown_tool_rejected() -> None:
    session = _session()
    resp = session.handle_rpc_request(_call("nosuch", {}))
    assert resp.captured_tool_call is False
    assert resp.body is not None
    assert resp.body["error"]["code"] == -32602
    assert "unknown tool: nosuch" in resp.body["error"]["message"]


def test_tools_call_invalid_arguments_rejected() -> None:
    session = _session()
    for arguments in ('{"broken', None, ["not", "a", "dict"]):
        resp = session.handle_rpc_request(_call("bash", arguments))
        assert resp.body is not None
        assert resp.body["error"]["code"] == -32602
    assert session.has_captured_calls() is False


def test_tools_call_limit_exceeded() -> None:
    session = _session(max_calls=1)
    first = session.handle_rpc_request(_call("bash", {"cmd": "ls"}, req_id=1))
    assert first.captured_tool_call is True
    second = session.handle_rpc_request(_call("bash", {"cmd": "pwd"}, req_id=2))
    assert second.captured_tool_call is False
    assert second.body is not None
    assert second.body["error"]["code"] == -32002
    assert "tool capture limit exceeded" in second.body["error"]["message"]
    assert len(session.snapshot_captured_calls()) == 1


def test_verify_auth_path_and_bearer() -> None:
    spec = McpToolCaptureSpec.create(TOOL_SCHEMAS)
    session = McpToolCaptureSession(spec)
    assert session.verify_auth("/mcp/wrong", f"Bearer {spec.bearer_token}") == (False, 403)
    assert session.verify_auth(spec.capability_path, None) == (False, 401)
    assert session.verify_auth(spec.capability_path, "Bearer wrong") == (False, 401)
    ok = session.verify_auth(spec.capability_path, f"Bearer {spec.bearer_token}")
    assert ok == (True, 200)


def test_spec_secrets_and_repr() -> None:
    spec = McpToolCaptureSpec.create(TOOL_SCHEMAS)
    assert len(spec.nonce) == 32
    assert len(spec.bearer_token) == 64
    assert spec.capability_path == f"/mcp/{spec.nonce}"
    text = repr(spec)
    assert spec.nonce not in text
    assert spec.bearer_token not in text
    assert "<redacted>" in text
    assert "bridge" in text
    assert "tools_count=2" in text


def test_snapshot_is_independent_and_reset_clears_state() -> None:
    session = _session()
    captured = session.handle_rpc_request(_call("bash", {"cmd": "ls"}))
    assert captured.captured_tool_call is True
    ping = session.handle_rpc_request({"jsonrpc": "2.0", "id": 8, "method": "ping"})
    assert ping.http_status == 200
    assert session.seen_methods() == frozenset({"tools/call", "ping"})
    snapshot = session.snapshot_captured_calls()
    snapshot[0]["function"]["name"] = "tampered"
    snapshot.append({"index": 99})
    fresh = session.snapshot_captured_calls()
    assert fresh[0]["function"]["name"] == "bash"
    assert len(fresh) == 1
    session.reset()
    assert session.has_captured_calls() is False
    assert session.snapshot_captured_calls() == []
    assert session.seen_methods() == frozenset()
