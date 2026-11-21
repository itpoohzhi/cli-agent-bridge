"""OpenCode ACP (Agent Client Protocol) resident stdio protocol driver."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import collections.abc
import hashlib
import json
import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, cast, override

from core.stdio_resident.protocol_driver import DecodedChunk, DriverCapabilities
from core.stdio_resident.rpc_drivers import AcpDriver
from core.subbridge_zero_canon import filter_opencode_config, is_zero_canon_profile
from core.zero_canon_fs import ensure_private_dir, write_atomic_0600

_OPENCODE_ENV_ALLOWLIST: tuple[str, ...] = (
    "PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    "XDG_DATA_HOME", "XDG_CONFIG_HOME", "OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT",
    "DEEPSEEK_API_KEY", "OPENCODE_API_KEY",
)


@dataclass
class OpenCodeDecodedChunk(DecodedChunk):
    """Normalized protocol frame with ACP error and permission reply handling."""

    error: str | None = None
    reply_bytes: bytes | None = None


def _parse_config_content(existing_raw: str) -> dict[str, Any]:
    if existing_raw:
        try:
            parsed = json.loads(existing_raw)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def _merge_config_content(existing_raw: str) -> str:
    config_obj = _parse_config_content(existing_raw)
    config_obj.setdefault("permission", {"*": "allow"})
    return json.dumps(config_obj, ensure_ascii=False)


class OpenCodeAcpDriver(AcpDriver):
    """Driver translating OpenCode ACP JSON-RPC 2.0 stdio communication."""

    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(
        protocol_name="opencode-acp", supports_soft_cancel=True, supports_multi_turn=True,
    )

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        super().__init__()
        self._config = dict(config or {})
        self._id_counter, self._id_lock = 0, threading.Lock()
        self._last_error: dict[str, Any] | None = None
        self._zc_local: threading.local = threading.local()

    @property
    def _active_session_id(self) -> str | None:
        return cast(str | None, getattr(self._zc_local, "session_id", None))

    @_active_session_id.setter
    def _active_session_id(self, value: str | None) -> None:
        self._zc_local.session_id = value

    @property
    def _active_prompt_id(self) -> int | None:
        return cast(int | None, getattr(self._zc_local, "prompt_id", None))

    @_active_prompt_id.setter
    def _active_prompt_id(self, value: int | None) -> None:
        self._zc_local.prompt_id = value

    @property
    def _zero_canon_active(self) -> bool:
        return bool(getattr(self._zc_local, "active", False))

    @_zero_canon_active.setter
    def _zero_canon_active(self, value: bool) -> None:
        self._zc_local.active = bool(value)

    def _allocate_id(self) -> int:
        with self._id_lock:
            self._id_counter += 1
            return self._id_counter

    @property
    def capabilities(self) -> DriverCapabilities:
        return self._capabilities

    @property
    def active_session_id(self) -> str | None:
        return self._active_session_id

    @override
    def build_argv(self, base_argv: list[str], options: Mapping[str, Any]) -> list[str]:
        argv = list(base_argv)
        if "acp" not in argv:
            argv.append("acp")
        return argv

    @override
    def build_env(self, base_env: Mapping[str, str] | None, turn_sandbox: str | None = None) -> dict[str, str]:
        source = os.environ if base_env is None else base_env
        env: dict[str, str] = {k: source[k] for k in _OPENCODE_ENV_ALLOWLIST if k in source}
        env["OPENCODE_DB"] = ":memory:"
        if turn_sandbox:
            env["TMPDIR"] = turn_sandbox
        env["OPENCODE_CONFIG_CONTENT"] = _merge_config_content(source.get("OPENCODE_CONFIG_CONTENT", ""))
        return env

    def build_zero_canon_env(self, base_env: Mapping[str, str], root: str) -> dict[str, str]:
        """Isolated HOME/XDG_CONFIG_HOME, empty cwd, and forced `permission={'*': 'ask'}`."""
        self._zero_canon_active = True
        env, zc_root = self.build_env(base_env, turn_sandbox=root), Path(root)
        zc_cfg, zc_oc_cfg = zc_root / ".config", zc_root / ".config" / "opencode"
        zc_data, zc_data_oc, zc_cwd = zc_root / ".local" / "share", zc_root / ".local" / "share" / "opencode", zc_root / "cwd"
        for directory in (zc_root, zc_cfg, zc_oc_cfg, zc_root / ".local", zc_data, zc_data_oc, zc_cwd):
            ensure_private_dir(directory, 0o700)
        src_data = Path(base_env.get("XDG_DATA_HOME") or f"{base_env.get('HOME', '')}/.local/share")
        auth_src = src_data / "opencode" / "auth.json"
        if auth_src.is_file() and not auth_src.is_symlink():
            write_atomic_0600(zc_data_oc / "auth.json", auth_src.read_bytes())
        raw_cfg = _parse_config_content(base_env.get("OPENCODE_CONFIG_CONTENT", ""))
        env.update({
            "HOME": str(zc_root), "XDG_CONFIG_HOME": str(zc_cfg), "XDG_DATA_HOME": str(zc_data),
            "OPENCODE_CONFIG_CONTENT": json.dumps(filter_opencode_config(raw_cfg), ensure_ascii=False),
            "BRIDGE_ZERO_CANON": "1",
        })
        env.pop("OPENCODE_CONFIG", None)
        return env

    def build_zero_canon_argv(self, argv: list[str], model: str = "", effort: str = "") -> list[str]:
        """Ensure `opencode acp` argv under Zero-Canon."""
        _ = (model, effort)
        return self.build_argv(argv, {})

    def handshake_payload(self) -> tuple[int, bytes]:
        req_id = self._allocate_id()
        payload = {
            "jsonrpc": "2.0", "id": req_id, "method": "initialize",
            "params": {"protocolVersion": 1, "clientInfo": {"name": "cli-agent-bridge", "version": "1.0"}, "clientCapabilities": {}},
        }
        return req_id, (json.dumps(payload, ensure_ascii=False) + "\n").encode()

    def _wait_response(self, handle: Any, req_id: int, timeout_s: float) -> dict[str, Any] | None:
        deadline = None if timeout_s <= 0 else time.monotonic() + timeout_s
        while True:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if deadline is not None and remaining == 0.0:
                return None
            line_obj = handle.read_line(timeout_s=remaining)
            if line_obj is None:
                return None
            parsed = self._parse_object(line_obj.line)
            if parsed and parsed.get("id") == req_id:
                return parsed

    def run_handshake(self, handle: Any, timeout_s: float = 10.0) -> bool:
        """Run ACP initialize handshake over the resident process handle."""
        req_id, data = self.handshake_payload()
        try:
            handle.write(data)
            resp = self._wait_response(handle, req_id, timeout_s)
            return resp is not None and "error" not in resp
        except Exception:
            return False

    def build_session_new_payload(self, cwd: str, model: str, effort: str | None = None) -> tuple[int, bytes]:
        req_id = self._allocate_id()
        params: dict[str, Any] = {"cwd": cwd, "model": model, "mcpServers": []}
        if effort:
            params["effort"] = effort
        payload = {"jsonrpc": "2.0", "id": req_id, "method": "session/new", "params": params}
        return req_id, (json.dumps(payload, ensure_ascii=False) + "\n").encode()

    def _handle_session_response(self, resp: dict[str, Any] | None) -> bool:
        if not resp:
            return False
        if "error" in resp:
            self._last_error = self._mapping(resp["error"])
            return False
        res = resp.get("result")
        if isinstance(res, dict) and "sessionId" in res:
            self._active_session_id = str(res["sessionId"])
            return True
        return False

    def prepare_turn(self, handle: Any, turn_context: Any, timeout_s: float = 10.0) -> bool:
        """Ensure an active ACP session exists before the prompt turn."""
        ctx = dict(turn_context) if isinstance(turn_context, collections.abc.Mapping) else {}
        if "review_profile" in ctx:
            self._zero_canon_active = is_zero_canon_profile(str(ctx.get("review_profile") or ""))
        if self._active_session_id is not None:
            return True
        cwd, model = str(ctx.get("cwd") or os.getcwd()), str(ctx.get("model") or "default")
        req_id, data = self.build_session_new_payload(cwd, model, ctx.get("effort"))
        try:
            handle.write(data)
            return self._handle_session_response(self._wait_response(handle, req_id, timeout_s))
        except Exception:
            return False

    @override
    def encode_turn(self, prompt: str, turn_context: Mapping[str, Any] | None = None) -> bytes:
        context = dict(turn_context or {})
        session_id = context.get("sessionId") or context.get("session_id") or self._active_session_id or "default"
        req_id = self._allocate_id()
        self._active_prompt_id = req_id
        payload = {
            "jsonrpc": "2.0", "id": req_id, "method": "session/prompt",
            "params": {"sessionId": session_id, "prompt": [{"type": "text", "text": prompt}]},
        }
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode()

    def _parse_update(self, params: Mapping[str, Any]) -> tuple[str, str, list[dict[str, Any]], bool]:
        update = self._mapping(params.get("update")) or {}
        kind = update.get("sessionUpdate") or update.get("type")
        if kind in ("content_part_delta", "delta"):
            delta = self._mapping(update.get("delta")) or update
            return self._extract_string(delta, ("text", "content")), self._extract_string(delta, ("reasoning", "thought")), [], False
        if kind in ("agent_message_chunk", "message_chunk", "agent_message"):
            return self._extract_string(update, ("content", "text", "delta")), "", [], False
        if kind in ("agent_thought_chunk", "thought_chunk", "agent_thought"):
            return "", self._extract_string(update, ("content", "thought", "reasoning", "delta")), [], False
        if kind == "tool_call":
            return "", "", [self._mapping(update.get("toolCall")) or update], True
        return "", "", [], False

    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        payload = self._parse_object(raw_line)
        if payload is None or payload.get("jsonrpc") != "2.0":
            return None
        if "error" in payload:
            err_dict = self._mapping(payload["error"])
            return OpenCodeDecodedChunk(error=str(err_dict.get("message") if err_dict else payload["error"]), is_terminal=True, raw=payload)
        res = payload.get("result")
        if isinstance(res, dict) and "sessionId" in res:
            self._active_session_id = str(res["sessionId"])
        method = payload.get("method")
        if method == "session/request_permission":
            decision = "deny" if self._zero_canon_active else "allow"
            reply = json.dumps({"jsonrpc": "2.0", "id": payload.get("id"), "result": {"decision": decision}}) + "\n"
            return OpenCodeDecodedChunk(reply_bytes=reply.encode("utf-8"), raw=payload)
        params = self._mapping(payload.get("params")) or {}
        text, reasoning, tool_calls, is_tool_stop = self._parse_update(params) if method == "session/update" else ("", "", [], False)
        return OpenCodeDecodedChunk(
            text=text, reasoning=reasoning, tool_calls=tool_calls,
            is_terminal=self._check_terminal(payload), is_tool_stop=is_tool_stop, raw=payload,
        )

    def _check_terminal(self, payload: Mapping[str, Any]) -> bool:
        if self._active_prompt_id is not None and payload.get("id") == self._active_prompt_id:
            self._active_prompt_id = None
            return True
        return False

    @override
    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None and decoded.is_terminal:
            return True
        payload = self._parse_object(raw_line)
        return bool(payload and payload.get("jsonrpc") == "2.0" and self._check_terminal(payload))

    @override
    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None:
            return decoded.is_tool_stop
        payload = self._parse_object(raw_line)
        if not payload or payload.get("jsonrpc") != "2.0":
            return False
        update = self._mapping((self._mapping(payload.get("params")) or {}).get("update")) or {}
        return update.get("sessionUpdate") == "tool_call"

    @override
    def build_cancel_payload(self) -> bytes | None:
        payload = {"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": self._active_session_id or "default"}}
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode()

    def set_session_id(self, session_id: str) -> None:
        self._active_session_id = session_id

    def compute_fingerprint(self) -> str:
        return hashlib.sha256(f"opencode-acp:{self._config.get('binary', 'opencode')}".encode()).hexdigest()

    @staticmethod
    def _mapping(value: object) -> dict[str, Any] | None:
        return cast(dict[str, Any], value) if isinstance(value, dict) else None
