"""Turn-scoped MCP wire helpers and MSP v1 cancel builders for Meta Muse."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from typing import Any

from core.stdio_resident.mcp_capture_server import TurnWireSessionScope

MUSE_INITIALIZE_CAPABILITIES: dict[str, list[str]] = {
    "requestedCapabilities": ["sessionMcp"],
}


def _uuid7() -> str:
    ms_bytes = (time.time_ns() // 1_000_000).to_bytes(6, "big")
    rand = bytearray(os.urandom(10))
    rand[0] = (rand[0] & 0x0F) | 0x70
    rand[2] = (rand[2] & 0x3F) | 0x80
    raw = (ms_bytes + bytes(rand)).hex()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def build_turn_cancel_msg(
    session_id: str,
    turn_id: str,
    command_id: str | None = None,
    request_id: int | str = 4,
) -> bytes:
    """Build an MSP v1 ``turn/cancel`` JSON-RPC request line."""
    if not session_id or not turn_id:
        return b""
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "turn/cancel",
        "params": {
            "commandId": command_id or _uuid7(),
            "sessionId": session_id,
            "turnId": turn_id,
        },
    }
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _cancel_from_ctx(session_id: str, turn_ctx: Mapping[str, object]) -> bytes | None:
    turn_id = str(turn_ctx.get("turn_id") or turn_ctx.get("turnId") or "")
    if not session_id or not turn_id:
        return None
    return build_turn_cancel_msg(session_id, turn_id)


def apply_scope_to_session_start(
    params: dict[str, Any],
    *,
    clear_developer_prompt: bool,
) -> dict[str, Any]:
    """Attach turn-scoped MCP server config and cancel builder to ``session/start`` params."""
    scope = TurnWireSessionScope.current()
    cfg: dict[str, Any] = {}
    if clear_developer_prompt:
        cfg["developerPrompt"] = None
    if scope is not None:
        spec = scope.spec
        if spec.emulate_tools and spec.suppress_host_tools:
            cfg["developerPrompt"] = spec.developer_prompt
        if spec.mcp_url and spec.bearer_token:
            cfg["mcpServers"] = {
                spec.server_name: {
                    "transport": "streamableHttp",
                    "url": spec.mcp_url,
                    "headers": {"Authorization": f"Bearer {spec.bearer_token}"},
                    "mode": "required",
                }
            }
            params["approvalMode"] = "allowAll"
        sid = str(params.get("sessionId") or "")
        scope.register_cancel_builder(lambda turn_ctx: _cancel_from_ctx(sid, turn_ctx))
    if cfg:
        params["config"] = cfg
    return params
