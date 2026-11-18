"""NDJSON JSON-RPC 2.0 codec and error normalization for Meta Muse MSP v1."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from core.stdio_resident.protocol_driver import DecodedChunk

ALLOWED_ERROR_CODES: frozenset[str] = frozenset({
    "protocol_error", "turn_timeout", "turn_failed", "auth_error",
    "rate_limited", "cancelled", "sandbox_error", "internal_error",
    "process_crashed", "invalid_request",
    "binary_sha256_missing", "binary_sha256_mismatch",
})

_ERROR_ALIASES: dict[str, str] = {
    "timeout": "turn_timeout", "timed_out": "turn_timeout",
    "turntimeout": "turn_timeout", "etimedout": "turn_timeout",
    "deadline_exceeded": "turn_timeout", "rate_limit": "rate_limited",
    "too_many_requests": "rate_limited", "429": "rate_limited",
    "unauthorized": "auth_error", "unauthenticated": "auth_error",
    "forbidden": "auth_error", "invalid_api_key": "auth_error",
    "401": "auth_error", "403": "auth_error",
    "canceled": "cancelled", "aborted": "cancelled", "interrupted": "cancelled",
    "permission_denied": "sandbox_error", "eacces": "sandbox_error", "eperm": "sandbox_error",
    "-32700": "protocol_error", "-32600": "protocol_error",
    "-32601": "protocol_error", "-32602": "invalid_request", "-32603": "internal_error",
}

_SECRET_RE = re.compile(
    r"(?i)\b(?:bearer\s+[A-Za-z0-9._\-]+|"
    r"(?:api[_-]?key|token|secret|password|authorization)\s*[:=]\s*[^\s,;]+|"
    r"(?:sk|ghp|gho|akia|xox[baprs])[A-Za-z0-9_\-]{6,})"
)
_PATH_RE = re.compile(r"(?:[A-Za-z]:\\[^\s'\"]+|(?<![\w.])~?(?:/[\w.\-]+)+)")
_UUID7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass
class MuseDecodedChunk(DecodedChunk):
    """Decoded MSP v1 frame with normalized error code and optional auto-reply."""

    error: str | None = None
    reply_bytes: bytes | None = None


def uuid7() -> str:
    """Generate an RFC 9562 UUIDv7 string using millisecond time and os.urandom."""
    ms_bytes = (time.time_ns() // 1_000_000).to_bytes(6, "big")
    rand = bytearray(os.urandom(10))
    rand[0] = (rand[0] & 0x0F) | 0x70
    rand[2] = (rand[2] & 0x3F) | 0x80
    raw = (ms_bytes + bytes(rand)).hex()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def is_uuid7(value: Any) -> bool:
    """Return True if value is a string matching UUIDv7 8-4-4-4-12 format."""
    return isinstance(value, str) and bool(_UUID7_RE.match(value))


def sanitize_error_text(text: str) -> str:
    """Redact credentials, tokens, and filesystem paths from error text."""
    return _PATH_RE.sub("[PATH]", _SECRET_RE.sub("[REDACTED]", text)).strip()


def normalize_msp_error(raw_error: Any, default: str = "protocol_error") -> str:
    """Map an arbitrary MSP or JSON-RPC error into the closed whitelist."""
    fallback = default if default in ALLOWED_ERROR_CODES else "protocol_error"
    code_str, msg_str = "", ""
    if isinstance(raw_error, Mapping):
        raw_code = raw_error.get("code")
        if raw_code is not None:
            raw_text = str(raw_code).strip()
            code_str = raw_text if raw_text.lstrip("-").isdigit() else raw_text.lower().replace("-", "_").replace(" ", "_")
        raw_msg = raw_error.get("message") or raw_error.get("reason") or raw_error.get("detail")
        if isinstance(raw_msg, str):
            msg_str = sanitize_error_text(raw_msg).lower()
    elif isinstance(raw_error, str):
        cleaned = sanitize_error_text(raw_error)
        code_str = cleaned.lower().replace("-", "_").replace(" ", "_")
        msg_str = cleaned.lower()

    for candidate in (code_str, _ERROR_ALIASES.get(code_str, "")):
        if candidate in ALLOWED_ERROR_CODES:
            return candidate
    for needle, mapped in (
        ("timeout", "turn_timeout"), ("timed out", "turn_timeout"),
        ("rate limit", "rate_limited"), ("rate_limit", "rate_limited"),
        ("429", "rate_limited"), ("quota", "rate_limited"),
        ("unauthorized", "auth_error"), ("forbidden", "auth_error"),
        ("cancel", "cancelled"), ("sandbox", "sandbox_error"),
        ("sha256_mismatch", "binary_sha256_mismatch"),
        ("sha256_missing", "binary_sha256_missing"),
    ):
        if needle in msg_str:
            return mapped
    return fallback


def _encode_rpc(
    method: str, params: Mapping[str, Any] | None = None, request_id: int | str | None = None
) -> bytes:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        payload["id"] = request_id
    if params is not None:
        payload["params"] = dict(params)
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def build_initialize_msg(request_id: int | str = 1) -> bytes:
    """Build an MSP v1 ``initialize`` JSON-RPC request line."""
    return _encode_rpc("initialize", {"clientInfo": {"name": "cli_agent_bridge", "version": "1.0.0"}}, request_id)


def build_initialized_msg() -> bytes:
    """Build an MSP v1 ``initialized`` JSON-RPC notification line."""
    return _encode_rpc("initialized")


def build_session_start_msg(
    session_id: str,
    model_id: str = "muse-wonder-1.0",
    approval_mode: str = "denyUnmatched",
    command_id: str | None = None,
    request_id: int | str = 2,
) -> bytes:
    """Build an MSP v1 ``session/start`` JSON-RPC request line."""
    params = {
        "commandId": command_id or uuid7(),
        "sessionId": session_id,
        "modelId": model_id,
        "approvalMode": approval_mode,
    }
    return _encode_rpc("session/start", params, request_id)


def build_turn_start_msg(
    session_id: str,
    effort: str,
    prompt: str,
    command_id: str | None = None,
    request_id: int | str = 3,
) -> bytes:
    """Build an MSP v1 ``turn/start`` JSON-RPC request line."""
    params = {
        "commandId": command_id or uuid7(),
        "sessionId": session_id,
        "input": [{"type": "text", "text": prompt}],
        "reasoningEffort": effort,
    }
    return _encode_rpc("turn/start", params, request_id)


def build_session_leave_msg(
    session_id: str,
    command_id: str | None = None,
    request_id: int | str | None = None,
) -> bytes:
    """Build an MSP v1 ``session/leave`` JSON-RPC teardown request line."""
    cmd_id = command_id or uuid7()
    params = {"commandId": cmd_id, "sessionId": session_id, "stop": True}
    return _encode_rpc("session/leave", params, cmd_id if request_id is None else request_id)


def _pick_str(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    for container in ("delta", "content"):
        nested = payload.get(container)
        if isinstance(nested, Mapping):
            found = _pick_str(nested, keys)
            if found:
                return found
    return ""


def _extract_item_text(item: Mapping[str, Any]) -> str:
    direct = _pick_str(item, ("text", "reasoning", "thought", "reasoning_content", "content"))
    if direct:
        return direct
    content = item.get("content")
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, Mapping) and isinstance(p.get("text"), str))
    return ""


def _extract_tool_calls(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("tool_calls", "tool_call", "toolCalls", "toolCall"):
        candidate = payload.get(key)
        if isinstance(candidate, dict):
            return [cast(dict[str, Any], candidate)]
        if isinstance(candidate, list):
            return [cast(dict[str, Any], item) for item in candidate if isinstance(item, dict)]
    return []


def _build_approval_deny(payload: Mapping[str, Any], params: Mapping[str, Any]) -> bytes:
    reply_params: dict[str, Any] = {"choiceId": "deny"}
    for key in ("approvalId", "requestId", "sessionId", "runId", "itemId"):
        if params.get(key) is not None:
            reply_params[key] = params[key]
    req_id = payload.get("id")
    if "requestId" not in reply_params and req_id is not None:
        reply_params["requestId"] = req_id
    return _encode_rpc("approval/decide", reply_params, req_id if req_id is not None else "approval-deny")


def decode_msp_line(raw_line: str) -> DecodedChunk:
    """Decode one NDJSON MSP v1 line into a normalized DecodedChunk."""
    line = raw_line.strip()
    if not line:
        return MuseDecodedChunk()
    try:
        parsed = cast(object, json.loads(line))
    except (json.JSONDecodeError, TypeError):
        return MuseDecodedChunk(error="protocol_error", is_terminal=True)
    if not isinstance(parsed, dict) or parsed.get("jsonrpc") != "2.0":
        return MuseDecodedChunk(error="protocol_error", is_terminal=True, raw=cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {})

    payload = cast(dict[str, Any], parsed)
    if payload.get("error") is not None:
        return MuseDecodedChunk(error=normalize_msp_error(payload["error"]), is_terminal=True, reply_bytes=None, raw=payload)

    method = payload.get("method")
    raw_params = payload.get("params")
    if method is None:
        if "result" in payload and "id" in payload:
            return MuseDecodedChunk(raw=payload)
        return MuseDecodedChunk(error="protocol_error", is_terminal=True, raw=payload)
    if not isinstance(method, str) or (raw_params is not None and not isinstance(raw_params, Mapping)):
        return MuseDecodedChunk(error="protocol_error", is_terminal=True, raw=payload)

    params: Mapping[str, Any] = cast(Mapping[str, Any], raw_params) if raw_params is not None else {}
    if method not in {"run.terminal.failed", "turn/failed", "turn/completed"} and params.get("error") is not None:
        return MuseDecodedChunk(error=normalize_msp_error(params["error"]), is_terminal=True, reply_bytes=None, raw=payload)

    if method == "run.output.delta":
        return MuseDecodedChunk(text=_pick_str(params, ("delta", "text", "content", "output")), reasoning=_pick_str(params, ("reasoning", "thought", "reasoning_content")), raw=payload)
    if method in {"item.delta", "item/delta"}:
        text = _pick_str(params, ("delta", "text", "content"))
        reasoning = _pick_str(params, ("reasoning", "thought", "reasoning_content"))
        if (params.get("kind") or params.get("itemKind") or params.get("type")) in {"reasoning", "thought"} and not reasoning and text:
            reasoning, text = text, ""
        return MuseDecodedChunk(text=text, reasoning=reasoning, tool_calls=_extract_tool_calls(params), raw=payload)
    if method == "item/completed":
        item = params.get("item")
        if not isinstance(item, Mapping):
            return MuseDecodedChunk(raw=payload)
        kind = item.get("kind") or item.get("type")
        if kind == "userMessage":
            return MuseDecodedChunk(raw=payload)
        text = _extract_item_text(item)
        if kind in {"reasoning", "thought"} and text:
            return MuseDecodedChunk(reasoning=text, raw=payload)
        if kind in {"assistantMessage", "agentMessage", "message"} and text:
            return MuseDecodedChunk(text=text, raw=payload)
        return MuseDecodedChunk(raw=payload)
    if method == "turn/completed" and (params.get("terminal") == "failed" or params.get("error") is not None):
        return MuseDecodedChunk(error=normalize_msp_error(params.get("error") or params, default="turn_failed"), is_terminal=True, raw=payload)
    if method in {"run.terminal.completed", "turn/completed"}:
        tool_stop = params.get("stopReason") in {"tool", "tool_stop", "tool_call"} or params.get("is_tool_stop") is True
        return MuseDecodedChunk(text=_pick_str(params, ("text", "content", "output")), reasoning=_pick_str(params, ("reasoning", "thought", "reasoning_content")), is_terminal=True, is_tool_stop=tool_stop, raw=payload)
    if method in {"run.terminal.failed", "turn/failed"}:
        err_src = params["error"] if params.get("error") is not None else params
        return MuseDecodedChunk(error=normalize_msp_error(err_src, default="turn_failed"), is_terminal=True, reply_bytes=None, raw=payload)
    if method in {"approval.request", "approval/request"}:
        return MuseDecodedChunk(reply_bytes=_build_approval_deny(payload, params), raw=payload)
    return MuseDecodedChunk(raw=payload)
