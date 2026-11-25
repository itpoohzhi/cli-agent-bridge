"""Adversarial security, resource, and kill-switch tests for MCP tool capture."""

from __future__ import annotations

import ast
import copy
import http.client
import json
import socket
import stat
import threading
from pathlib import Path
from typing import cast

from adapters.stdio_drivers.muse_env import build_muse_env, prepare_muse_zero_canon_home
from adapters.stdio_drivers.muse_mcp_wire import (
    apply_scope_to_session_start,
    redact_session_start_for_log,
)
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.mcp_capture_server import (
    McpLoopbackServer,
    TurnMcpSessionSpec,
    TurnWireSessionScope,
)
from core.stdio_resident.mcp_tool_capture import McpToolCaptureSession, McpToolCaptureSpec
from core.tool_mode import ToolMode

_SCHEMAS: dict[str, object] = {
    "echo": {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo text",
            "parameters": {"type": "object", "properties": {"msg": {"type": "string"}}},
        },
    }
}


def _post_raw(
    port: int,
    path: str,
    body: bytes,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
    try:
        conn.request("POST", path, body=body, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def _post_rpc(
    port: int,
    path: str,
    token: str,
    payload: dict[str, object],
) -> tuple[int, dict[str, object]]:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    status, body = _post_raw(
        port,
        path,
        raw,
        {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    parsed = cast("object", json.loads(body.decode("utf-8")))
    assert isinstance(parsed, dict)
    return status, cast("dict[str, object]", parsed)


def test_threat_001_unauthorized_path_and_bearer_rejected() -> None:
    """Wrong capability path returns 403; missing/wrong bearer returns 401; 0 calls."""
    spec = McpToolCaptureSpec.create(_SCHEMAS)
    session = McpToolCaptureSession(spec)
    call_body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "echo", "arguments": {}}}
    ).encode("utf-8")
    with McpLoopbackServer(session, cancel_wait_s=0.2) as srv:
        s_path, _ = _post_raw(srv.port, "/mcp/wrong", call_body, {"Authorization": f"Bearer {spec.bearer_token}"})
        s_missing, _ = _post_raw(srv.port, spec.capability_path, call_body, {})
        s_bad_tok, _ = _post_raw(srv.port, spec.capability_path, call_body, {"Authorization": "Bearer wrong"})
    assert s_path == 403
    assert s_missing == 401
    assert s_bad_tok == 401
    assert not session.has_captured_calls()
    assert session.snapshot_captured_calls() == []


def test_threat_004_oversized_body_returns_413_without_crash() -> None:
    """Requests exceeding max_request_bytes return HTTP 413 and keep server healthy."""
    spec = McpToolCaptureSpec.create(_SCHEMAS)
    session = McpToolCaptureSession(spec)
    big_body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {"pad": "a" * 5000}}
    ).encode("utf-8")
    assert len(big_body) > 4096
    auth = {"Authorization": f"Bearer {spec.bearer_token}", "Content-Type": "application/json"}
    with McpLoopbackServer(session, max_request_bytes=4096, cancel_wait_s=0.2) as srv:
        status, _ = _post_raw(srv.port, spec.capability_path, big_body, auth)
        ok_status, ok_body = _post_rpc(srv.port, spec.capability_path, spec.bearer_token, {"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert status == 413
    assert ok_status == 200
    assert ok_body["result"] == {}


def test_invalid_json_unknown_method_and_tool_errors() -> None:
    """Malformed JSON -> 400; unknown method -> -32601; FORBID -> -32001; unknown tool -> -32602."""
    spec = McpToolCaptureSpec.create(_SCHEMAS, tool_mode=ToolMode.EMULATE)
    session = McpToolCaptureSession(spec)
    auth = {"Authorization": f"Bearer {spec.bearer_token}", "Content-Type": "application/json"}
    with McpLoopbackServer(session, cancel_wait_s=0.2) as srv:
        bad_status, _ = _post_raw(srv.port, spec.capability_path, b"{broken-json", auth)
        _, meth_body = _post_rpc(srv.port, spec.capability_path, spec.bearer_token, {"jsonrpc": "2.0", "id": 1, "method": "unknown/method"})
        _, unk_body = _post_rpc(
            srv.port,
            spec.capability_path,
            spec.bearer_token,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "no_such_tool", "arguments": {}}},
        )
    assert bad_status == 400
    assert cast("dict[str, object]", meth_body["error"])["code"] == -32601
    assert cast("dict[str, object]", unk_body["error"])["code"] == -32602

    forbid_spec = McpToolCaptureSpec.create(_SCHEMAS, tool_mode=ToolMode.FORBID)
    forbid_session = McpToolCaptureSession(forbid_spec)
    with McpLoopbackServer(forbid_session, cancel_wait_s=0.2) as forbid_srv:
        _, f_body = _post_rpc(
            forbid_srv.port,
            forbid_spec.capability_path,
            forbid_spec.bearer_token,
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "echo", "arguments": {}}},
        )
    assert cast("dict[str, object]", f_body["error"])["code"] == -32001
    assert not forbid_session.has_captured_calls()


def test_threat_004_parallel_tools_call_coalescing_and_socket_cleanup() -> None:
    """Two concurrent tools/call requests are both captured and socket closes on exit."""
    spec = McpToolCaptureSpec.create(_SCHEMAS)
    session = McpToolCaptureSession(spec)
    barrier = threading.Barrier(2)
    results: list[tuple[int, dict[str, object]]] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def _worker(port: int, idx: int) -> None:
        try:
            _ = barrier.wait(timeout=2.0)
            res = _post_rpc(
                port,
                spec.capability_path,
                spec.bearer_token,
                {"jsonrpc": "2.0", "id": idx, "method": "tools/call", "params": {"name": "echo", "arguments": {"msg": f"m{idx}"}}},
            )
            with lock:
                results.append(res)
        except BaseException as exc:
            with lock:
                errors.append(exc)

    srv = McpLoopbackServer(session, cancel_wait_s=2.0, coalesce_ms=25)
    with srv:
        bound_port = srv.port
        threads = [threading.Thread(target=_worker, args=(bound_port, i)) for i in range(2)]
        for t in threads:
            t.start()
        assert srv.captured_event.wait(timeout=2.0)
        srv.wait_for_coalesce()
        srv.release()
        for t in threads:
            t.join(timeout=2.0)
            assert not t.is_alive()

    assert errors == []
    assert [status for status, _ in results] == [200, 200]
    assert len(session.snapshot_captured_calls()) == 2
    try:
        with socket.create_connection(("127.0.0.1", bound_port), timeout=0.5):
            raise AssertionError(f"port {bound_port} remained open after server close")
    except OSError:
        pass


def test_threat_003_repr_redacts_nonce_token_and_url() -> None:
    """repr() on McpToolCaptureSpec, TurnMcpSessionSpec, and McpLoopbackServer hides secrets."""
    spec = McpToolCaptureSpec.create(_SCHEMAS)
    session = McpToolCaptureSession(spec)
    wire_spec = TurnMcpSessionSpec(
        mcp_url=f"http://127.0.0.1:43210{spec.capability_path}",
        bearer_token=spec.bearer_token,
        server_name="bridge",
    )
    srv = McpLoopbackServer(session)
    with TurnWireSessionScope.bind(wire_spec) as scope:
        rendered = (repr(spec), repr(wire_spec), repr(scope.spec), repr(srv))
    for text in rendered:
        assert spec.nonce not in text
        assert spec.bearer_token not in text
        assert "43210" not in text


def _seed_muse_src_home(tmp_path: Path) -> Path:
    src_home = tmp_path / "src_home"
    src_cfg = src_home / ".config" / "muse"
    src_cfg.mkdir(parents=True)
    _ = (src_cfg / "auth.json").write_text('{"access":"tok"}', encoding="utf-8")
    _ = (src_cfg / "AGENTS.md").write_text("do not copy", encoding="utf-8")
    return src_home


def test_qa_005_and_threat_005_kill_switches_and_clean_home(tmp_path: Path) -> None:
    """Kill-switches default False, env overrides work, and clean HOME enforces 0700/0600."""
    defaults = StdioPoolConfig.from_env({})
    assert not defaults.mcp_tool_capture_enabled
    assert not defaults.suppress_builtin_tools_enabled
    assert not defaults.clean_cli_home_enabled
    enabled = StdioPoolConfig.from_env(
        {"BRIDGE_STDIO_MCP_TOOL_CAPTURE_ENABLED": "true", "BRIDGE_STDIO_MCP_MAX_REQUEST_BYTES": "65536"}
    )
    assert enabled.mcp_tool_capture_enabled is True
    assert enabled.mcp_max_request_bytes == 65536

    src_home = _seed_muse_src_home(tmp_path)
    direct_home = tmp_path / "direct_zc"
    (direct_home / ".config" / "muse").mkdir(parents=True)
    _ = (direct_home / "AGENTS.md").write_text("stale", encoding="utf-8")
    _ = (direct_home / ".config" / "muse" / "AGENTS.md").write_text("stale", encoding="utf-8")
    prepared = prepare_muse_zero_canon_home(src_home, direct_home)
    assert stat.S_IMODE(prepared.stat().st_mode) == 0o700
    assert stat.S_IMODE((prepared / ".config" / "muse" / "auth.json").stat().st_mode) == 0o600
    assert not (prepared / "AGENTS.md").exists()
    assert not (prepared / ".config" / "muse" / "AGENTS.md").exists()

    clean_root = tmp_path / "clean_root"
    (clean_root / "muse-clean-home").mkdir(parents=True)
    _ = (clean_root / "muse-clean-home" / "AGENTS.md").write_text("stale", encoding="utf-8")
    env = build_muse_env(
        None,
        "/usr/bin/true",
        turn_sandbox=str(tmp_path / "sandbox"),
        server_env={
            "HOME": str(src_home),
            "BRIDGE_STDIO_CLEAN_CLI_HOME_ENABLED": "1",
            "BRIDGE_STDIO_CLEAN_CLI_HOME_ROOT": str(clean_root),
        },
    )
    clean_home = Path(env["HOME"])
    assert stat.S_IMODE(clean_home.stat().st_mode) == 0o700
    assert stat.S_IMODE((clean_home / ".config" / "muse" / "auth.json").stat().st_mode) == 0o600
    assert not (clean_home / "AGENTS.md").exists()


def test_verify_auth_non_ascii_path_and_bearer_no_typeerror() -> None:
    """Non-ASCII path or Authorization header returns 403/401 deterministically without TypeError."""
    spec = McpToolCaptureSpec.create(_SCHEMAS)
    session = McpToolCaptureSession(spec)
    assert session.verify_auth("/mcp/тест", f"Bearer {spec.bearer_token}") == (False, 403)
    assert session.verify_auth(spec.capability_path, "Bearer токен") == (False, 401)
    assert session.verify_auth(spec.capability_path, None) == (False, 401)
    assert session.verify_auth(spec.capability_path, f"Bearer {spec.bearer_token}") == (True, 200)


def test_redact_session_start_for_log_strips_secrets_without_mutation() -> None:
    """redact_session_start_for_log removes mcp_url, nonce, and bearer_token without mutating input."""
    spec = McpToolCaptureSpec.create(_SCHEMAS)
    mcp_url = f"http://127.0.0.1:43210{spec.capability_path}"
    wire_spec = TurnMcpSessionSpec(
        mcp_url=mcp_url,
        bearer_token=spec.bearer_token,
        server_name="bridge",
        emulate_tools=True,
        suppress_host_tools=True,
    )
    params: dict[str, object] = {
        "sessionId": "sid-redact-1",
        "config": {"customFlag": True},
    }
    with TurnWireSessionScope.bind(wire_spec):
        _ = apply_scope_to_session_start(params, clear_developer_prompt=False)
    snapshot = copy.deepcopy(params)
    redacted = redact_session_start_for_log(params)

    assert params == snapshot
    for rendered in (repr(redacted), json.dumps(redacted)):
        assert mcp_url not in rendered
        assert spec.nonce not in rendered
        assert spec.bearer_token not in rendered
        assert "43210" not in rendered
    cfg = cast("dict[str, object]", redacted["config"])
    assert cfg["customFlag"] is True
    srv = cast("dict[str, object]", cast("dict[str, object]", cfg["mcpServers"])["bridge"])
    assert srv["url"] == "<redacted>"
    assert cast("dict[str, object]", srv["headers"])["Authorization"] == "<redacted>"


def test_static_safety_proof_no_session_start_or_bearer_token_logged() -> None:
    """Driver/transport sources never log session/start params, payload, or bearer_token."""
    root = Path(__file__).resolve().parents[1]
    targets = (
        "adapters/stdio_drivers/muse_driver.py",
        "adapters/stdio_drivers/muse_codec.py",
        "adapters/stdio_drivers/muse_mcp_wire.py",
        "core/stdio_resident/runtime_wire.py",
    )
    log_methods = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})
    sensitive_tokens = ("bearer_token", "session/start", "session_start", "authorization", "mcp_url", "payload", "params")
    for rel in targets:
        tree = ast.parse((root / rel).read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            is_print = isinstance(node.func, ast.Name) and node.func.id == "print"
            is_log_attr = isinstance(node.func, ast.Attribute) and node.func.attr in log_methods
            is_logger_obj = (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"logger", "logging", "log"}
            )
            if not (is_print or (is_log_attr and is_logger_obj)):
                continue
            call_text = ast.unparse(node).lower()
            for token in sensitive_tokens:
                assert token not in call_text, f"{rel} logs sensitive token {token!r}: {call_text}"
