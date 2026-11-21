"""OpenAI Codex CLI app-server JSON-RPC 2.0 protocol driver for resident stdio processes."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar, cast, override

from core.stdio_resident.protocol_driver import (
    DecodedChunk,
    DriverCapabilities,
    StreamJsonDriver,
)
from core.subbridge_zero_canon import dump_toml, filter_codex_config
from core.zero_canon_fs import ensure_private_dir, write_atomic_0600, write_atomic_text_0600


class CodexAppServerDriver(StreamJsonDriver):
    """Translate Codex app-server JSON-RPC frames to the resident contract."""

    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(
        protocol_name="codex-app-server",
        supports_soft_cancel=True,
        supports_multi_turn=True,
    )

    def __init__(self) -> None:
        self._next_id = 1

    @override
    def build_argv(self, base_argv: list[str], options: Mapping[str, Any]) -> list[str]:
        argv = list(base_argv)
        if "app-server" not in argv:
            argv.append("app-server")
        for name, value in options.items():
            if value is None or value is False:
                continue
            flag = name if name.startswith("--") else f"--{name.replace('_', '-')}"
            if self._has_flag(argv, flag):
                continue
            argv.append(flag)
            if value is not True:
                argv.append(str(value))
        return argv

    @override
    def encode_turn(
        self,
        prompt: str,
        turn_context: Mapping[str, Any] | None = None,
    ) -> bytes:
        request_id = self._next_id
        self._next_id += 1
        context = dict(turn_context or {})
        thread_id = str(
            context.get("thread_id") or context.get("threadId") or f"th-{request_id}"
        )
        action = str(context.get("action", "turn/start"))
        params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": prompt}],
        }
        if "model" in context:
            params["model"] = context["model"]
        if "effort" in context:
            params["effort"] = context["effort"]
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": action,
            "params": params,
        }
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode()

    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        payload = self._parse_object(raw_line)
        if payload is None or payload.get("jsonrpc") != "2.0":
            return None

        method = payload.get("method")
        params = self._mapping(payload.get("params")) or {}
        result = self._mapping(payload.get("result"))
        content = result or params
        delta = self._mapping(content.get("delta"))
        text = ""
        reasoning = ""
        if method in {"turn/delta", "turn/progress", "stream"}:
            raw_delta = content.get("delta")
            if isinstance(raw_delta, str):
                text = raw_delta
            elif delta is not None:
                text = self._extract_string(delta, ("content", "text"))
                reasoning = self._extract_string(delta, ("reasoning", "thought"))
            text = text or self._extract_string(content, ("text", "content"))
            reasoning = reasoning or self._extract_string(
                content, ("reasoning", "thought", "reasoning_content")
            )
        elif result is not None:
            text = self._extract_string(result, ("output", "content", "text"))
            reasoning = self._extract_string(
                result, ("reasoning", "thought", "reasoning_content")
            )

        tool_calls = self._extract_tool_calls(content)
        if not tool_calls:
            tool_calls = self._extract_tool_calls(payload)
        error = self._mapping(payload.get("error"))
        err_text = (
            str(error.get("message") or error)
            if error is not None
            else (str(payload["error"]) if "error" in payload and payload["error"] is not None else None)
        )
        is_terminal = method == "turn/completed" or (
            "id" in payload and ("result" in payload or "error" in payload)
        )
        is_tool_stop = bool(tool_calls) or self._tool_stop(content)
        return DecodedChunk(
            text=text,
            reasoning=reasoning,
            tool_calls=tool_calls,
            is_terminal=is_terminal,
            is_tool_stop=is_tool_stop,
            raw=error if error is not None else payload,
            error=err_text,
        )

    @override
    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None and decoded.is_terminal:
            return True
        payload = self._parse_object(raw_line)
        return bool(
            payload
            and payload.get("jsonrpc") == "2.0"
            and (
                payload.get("method") == "turn/completed"
                or ("id" in payload and ("result" in payload or "error" in payload))
            )
        )

    @override
    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None and decoded.is_tool_stop:
            return True
        payload = self._parse_object(raw_line)
        if payload is None or payload.get("jsonrpc") != "2.0":
            return False
        result = self._mapping(payload.get("result")) or payload
        return bool(self._extract_tool_calls(result)) or self._tool_stop(result)

    @override
    def build_cancel_payload(self) -> bytes | None:
        return b'{"jsonrpc": "2.0", "method": "turn/cancel", "params": {}}\n'

    def build_zero_canon_env(self, base_env: Mapping[str, str], root: str) -> dict[str, str]:
        """Изолированные HOME/CODEX_HOME: config.toml без mcp_servers/hooks, без AGENTS.md."""
        home = base_env.get("HOME", "")
        config = base_env.get("CODEX_HOME") or (f"{home}/.codex" if home else "")
        src = Path(config) if config else None
        dst = Path(root) / ".codex"
        ensure_private_dir(dst, 0o700)
        raw: dict[str, Any] = {}
        src_cfg = src / "config.toml" if src is not None else None
        if src_cfg is not None and src_cfg.is_file() and not src_cfg.is_symlink():
            try:
                raw = tomllib.loads(src_cfg.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = {}
        write_atomic_text_0600(dst / "config.toml", dump_toml(filter_codex_config(raw)))
        src_auth = src / "auth.json" if src is not None else None
        if src_auth is not None and src_auth.is_file() and not src_auth.is_symlink():
            write_atomic_0600(dst / "auth.json", src_auth.read_bytes())
        return {**base_env, "HOME": root, "CODEX_HOME": str(dst)}

    def build_zero_canon_argv(self, argv: list[str], model: str = "", effort: str = "") -> list[str]:
        """`codex app-server`: fail-closed на запрещённых `-c`/`--config`, принудительный `project_doc_max_bytes=0`."""
        denied_cfg = ("mcp_servers", "plugins", "notify", "hooks")
        overrides = {"project_doc_max_bytes": "0"}
        if model and model != "default":
            overrides["model"] = json.dumps(model)
        if effort and effort != "default":
            overrides["model_reasoning_effort"] = json.dumps(effort)
        cleaned: list[str] = []
        idx = 0
        while idx < len(argv):
            tok = argv[idx]
            cfg_val: str | None = None
            step = 1
            if tok in ("-c", "--config") and idx + 1 < len(argv):
                cfg_val, step = argv[idx + 1], 2
            elif tok.startswith(("-c=", "--config=")):
                cfg_val = tok.split("=", 1)[1]
            if cfg_val is not None:
                key_part = cfg_val.split("=", 1)[0].strip()
                if any(key_part == d or key_part.startswith(f"{d}.") for d in denied_cfg):
                    raise ValueError(f"forbidden_codex_zero_canon_config:{key_part}")
                if key_part in overrides:
                    idx += step
                    continue
            cleaned.append(tok)
            idx += 1
        result = cleaned if "app-server" in cleaned else [*cleaned, "app-server"]
        for key, value in overrides.items():
            result.extend(("-c", f"{key}={value}"))
        return result

    def handshake_payload(self) -> bytes:
        """Build the Codex app-server initialization request."""
        return b'{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "cli-agent-bridge", "version": "1.0"}}}\n'

    def run_handshake(self, handle: Any, timeout_s: float = 10.0) -> bool:
        """Send JSON-RPC initialize handshake and await response."""
        try:
            handle.write(self.handshake_payload())
            line_obj = handle.read_line(timeout_s=timeout_s)
            if line_obj is None:
                return False
            parsed = self._parse_object(line_obj.line)
            return parsed is not None and "error" not in parsed
        except Exception:
            return False

    @staticmethod
    def _mapping(value: object) -> dict[str, Any] | None:
        return cast(dict[str, Any], value) if isinstance(value, dict) else None

    @staticmethod
    def _has_flag(argv: list[str], flag: str) -> bool:
        return any(item == flag or item.startswith(f"{flag}=") for item in argv)

    @classmethod
    def _tool_stop(cls, payload: Mapping[str, Any]) -> bool:
        return any(
            payload.get(key) is True
            or payload.get(key) in ("tool", "tool_call", "tool_calls", "tool_stop")
            for key in ("is_tool_stop", "tool_stop", "stop_reason", "status")
        )
