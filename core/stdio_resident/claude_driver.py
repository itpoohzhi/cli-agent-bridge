"""Claude Code CLI stream-json protocol driver for resident stdio processes."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar, cast, override

from core.claude_zero_canon import (
    CLAUDE_PRESERVED_CA_FILES,
    build_claude_zero_canon_env,
    build_claude_zero_canon_flags,
    filter_claude_settings,
    filter_claude_state,
    find_forbidden_claude_flags,
    serialize_claude_json,
)
from core.stdio_resident.config import suppress_builtin_tools_enabled
from core.stdio_resident.protocol_driver import (
    DecodedChunk,
    DriverCapabilities,
    StreamJsonDriver,
)
from core.stdio_resident.usage_extract import extract_claude_usage
from core.zero_canon_fs import ensure_private_dir, sanitize_zero_canon_env, write_atomic_0600, write_atomic_text_0600


class ClaudeStreamJsonDriver(StreamJsonDriver):
    """Translate Claude Code stream-json frames to the resident core contract."""

    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(
        protocol_name="claude-stream-json",
        supports_soft_cancel=True,
        supports_multi_turn=True,
    )
    FAST_FAIL_STATUSES: ClassVar[frozenset[int]] = frozenset({429})

    @override
    def build_argv(self, base_argv: list[str], options: Mapping[str, Any]) -> list[str]:
        argv = list(base_argv)
        if not self._has_flag(argv, "--print"):
            argv.append("--print")
        if not self._has_flag(argv, "--input-format"):
            argv.extend(("--input-format", "stream-json"))
        if not self._has_flag(argv, "--output-format"):
            argv.extend(("--output-format", "stream-json"))
        if self._should_suppress_builtin_tools(options) and not self._has_flag(argv, "--tools"):
            argv.extend(("--tools", ""))

        managed_options = {"print", "input_format", "output_format", "suppress_builtin_tools", "emulate_tools"}
        for name, value in options.items():
            normalized_name = name.removeprefix("--").replace("-", "_")
            if normalized_name in managed_options or value is None or value is False:
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
        payload: dict[str, Any] = {
            "type": "user",
            "message": {"role": "user", "content": prompt},
        }
        if turn_context:
            payload.update(turn_context)
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode()

    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        payload = self._parse_object(raw_line)
        if payload is None:
            return None

        text = ""
        reasoning = ""
        event = self._mapping(payload.get("event"))
        if payload.get("type") == "stream_event" and event is not None:
            if event.get("type") == "content_block_delta":
                delta = self._mapping(event.get("delta"))
                if delta is not None and delta.get("type") == "text_delta":
                    text = self._string(delta.get("text"))
                elif delta is not None and delta.get("type") == "thinking_delta":
                    reasoning = self._string(delta.get("thinking"))

        is_terminal = payload.get("type") == "result"
        is_error = payload.get("is_error") is True or payload.get("status") == "error"
        if is_terminal:
            result = payload.get("result")
            text = result if isinstance(result, str) else self._string(payload.get("text"))

        tool_calls = self._extract_claude_tool_calls(payload, event)
        tool_stop = bool(tool_calls) or self._has_tool_stop(payload, event)
        error = self._fast_error(payload, text, is_error)
        return DecodedChunk(
            text=text,
            reasoning=reasoning,
            tool_calls=tool_calls,
            is_terminal=is_terminal,
            is_tool_stop=tool_stop,
            raw=payload if is_error or error else {},
            error=error,
            usage=extract_claude_usage(payload),
        )

    @classmethod
    def _fast_error(cls, payload: Mapping[str, Any], text: str, is_error: bool) -> str | None:
        """Fail-fast: итоговая ошибка или api_retry с 429, без ожидания idle-таймаута."""
        status = payload.get("api_error_status", payload.get("error_status"))
        retry = payload.get("type") == "system" and payload.get("subtype") == "api_retry"
        if retry and status not in cls.FAST_FAIL_STATUSES:
            return None
        if not (is_error or retry):
            return None
        detail = text or cls._string(payload.get("error")) or "claude error"
        return f"claude_error status={status}: {detail}" if status else f"claude_error: {detail}"

    def build_zero_canon_env(self, base_env: Mapping[str, str], root: str) -> dict[str, str]:
        """Изолированные HOME/CLAUDE_CONFIG_DIR с отфильтрованными settings.json/.claude.json."""
        home = base_env.get("HOME", "")
        config = base_env.get("CLAUDE_CONFIG_DIR") or (f"{home}/.claude" if home else "")
        src = Path(config) if config else None
        dst = Path(root) / ".claude"
        ensure_private_dir(dst, 0o700)
        if src is not None:
            states = (src / ".claude.json", src.parent / ".claude.json")
            for name, keep, paths in (
                ("settings.json", filter_claude_settings, (src / "settings.json",)),
                (".claude.json", filter_claude_state, states),
            ):
                raw = next((r for r in map(self._read_json, paths) if r is not None), None)
                if raw is not None:
                    write_atomic_text_0600(dst / name, serialize_claude_json(keep(raw)))
            for name in (*CLAUDE_PRESERVED_CA_FILES, ".credentials.json", "credentials.json", "auth.json"):
                ca_src = src / name
                if ca_src.is_file() and not ca_src.is_symlink():
                    write_atomic_0600(dst / name, ca_src.read_bytes())
        return build_claude_zero_canon_env(sanitize_zero_canon_env(base_env, root), root, profile="strict", config_dir=str(dst))

    def build_zero_canon_argv(self, argv: list[str], model: str = "", effort: str = "") -> list[str]:
        """Fail-closed: отвергает запрещённые флаги (вкл. -c/-r) и вставляет Zero-Canon до `--`."""
        zc_flags = build_claude_zero_canon_flags()
        value_flags = frozenset({"--tools", "--setting-sources"})
        bool_flags = frozenset({"--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"})
        if "--" in argv:
            split_idx = argv.index("--")
            head, tail = list(argv[:split_idx]), list(argv[split_idx:])
        else:
            head, tail = list(argv), []
        cleaned: list[str] = []
        idx = 0
        while idx < len(head):
            tok = head[idx]
            if tok in ("-c", "-r"):
                raise ValueError(f"forbidden_claude_zero_canon_flags:{tok}")
            flag_name = tok.split("=", 1)[0]
            if flag_name in bool_flags:
                idx += 1
                continue
            if flag_name in value_flags:
                idx += 2 if ("=" not in tok and idx + 1 < len(head)) else 1
                continue
            cleaned.append(tok)
            idx += 1
        forbidden = find_forbidden_claude_flags(cleaned)
        if forbidden:
            raise ValueError(f"forbidden_claude_zero_canon_flags:{','.join(forbidden)}")
        cleaned.extend(zc_flags)
        for flag, value in (("--model", model), ("--effort", effort)):
            if value and value != "default" and not self._has_flag(cleaned, flag):
                cleaned.extend((flag, value))
        return [*cleaned, *tail]

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        if path.is_symlink():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return cast(dict[str, Any], raw) if isinstance(raw, dict) else None

    @override
    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None and decoded.is_terminal:
            return True
        payload = self._parse_object(raw_line)
        return payload is not None and payload.get("type") == "result"

    @override
    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None:
            return decoded.is_tool_stop
        payload = self._parse_object(raw_line)
        if payload is None:
            return False
        event = self._mapping(payload.get("event"))
        return bool(self._extract_claude_tool_calls(payload, event)) or self._has_tool_stop(
            payload, event
        )

    @override
    def build_cancel_payload(self) -> bytes | None:
        return b'{"type": "cancel"}\n'

    def handshake(self, handle: Any, timeout_s: float = 10.0) -> bool:
        """Confirm that the resident Claude process is still alive."""

        _ = timeout_s
        return bool(handle.is_alive())

    def slot_profile_key(self, options: Mapping[str, Any]) -> str:
        """Keep `--tools ""` slots separate from default slots in the resident pool."""
        return "tools-suppressed" if self._should_suppress_builtin_tools(options) else "default"

    @staticmethod
    def _should_suppress_builtin_tools(options: Mapping[str, Any]) -> bool:
        """Explicit per-call override wins; otherwise emulate_tools + env flag (default off)."""
        if "suppress_builtin_tools" in options:
            return bool(options["suppress_builtin_tools"])
        return bool(options.get("emulate_tools")) and suppress_builtin_tools_enabled()

    @staticmethod
    def _has_flag(argv: list[str], flag: str) -> bool:
        return any(item == flag or item.startswith(f"{flag}=") for item in argv)

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any] | None:
        return cast(dict[str, Any], value) if isinstance(value, dict) else None

    @staticmethod
    def _string(value: Any) -> str:
        return value if isinstance(value, str) else ""

    @classmethod
    def _extract_claude_tool_calls(
        cls,
        payload: Mapping[str, Any],
        event: Mapping[str, Any] | None,
    ) -> list[dict[str, Any]]:
        calls = cls._extract_tool_calls(payload)
        if event is not None:
            calls.extend(cls._extract_tool_calls(event))
            if event.get("type") == "content_block_start":
                content_block = cls._mapping(event.get("content_block"))
                if content_block is not None and content_block.get("type") == "tool_use":
                    calls.append(content_block)
        return calls

    @classmethod
    def _has_tool_stop(
        cls,
        payload: Mapping[str, Any],
        event: Mapping[str, Any] | None,
    ) -> bool:
        containers = [payload]
        if event is not None:
            containers.append(event)
            delta = cls._mapping(event.get("delta"))
            if delta is not None:
                containers.append(delta)
        return any(
            item.get("type") == "tool_turn_stop"
            or item.get("stop_reason") == "tool_use"
            for item in containers
        )
