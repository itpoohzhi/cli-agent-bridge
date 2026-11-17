"""Universal JSON-RPC and ACP drivers for resident stdio processes."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, ClassVar, cast, override

from core.stdio_resident.protocol_driver import (
    DecodedChunk,
    DriverCapabilities,
    StdioProtocolDriver,
    StreamJsonDriver,
)


def _mapping(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return cast(dict[str, Any], value)


def _encode(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()


def _tool_stop(payload: Mapping[str, Any]) -> bool:
    result = _mapping(payload.get("result"))
    candidates: list[object] = [
        payload.get("is_tool_stop"),
        payload.get("tool_stop"),
        payload.get("stop_reason"),
        payload.get("status"),
    ]
    if result is not None:
        candidates.extend(
            (
                result.get("is_tool_stop"),
                result.get("tool_stop"),
                result.get("stop_reason"),
                result.get("status"),
                result.get("tool_call"),
                result.get("tool_calls"),
            )
        )
    return any(
        value is True or value in {"tool", "tool_stop", "tool_call", "tool_calls"}
        for value in candidates
        if isinstance(value, bool | str)
    ) or bool(
        result
        and (
            isinstance(result.get("tool_call"), dict)
            or isinstance(result.get("tool_calls"), list)
        )
    )


class StreamJsonRpcDriver(StreamJsonDriver):
    """Newline-delimited JSON-RPC 2.0 transport."""

    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(
        protocol_name="stream-jsonrpc",
        supports_soft_cancel=True,
        supports_multi_turn=True,
    )

    def __init__(self) -> None:
        self._next_id: int = 1

    @override
    def build_argv(self, base_argv: list[str], options: Mapping[str, Any]) -> list[str]:
        configured = dict(options)
        configured.setdefault("output_format", "stream-jsonrpc")
        return super().build_argv(base_argv, configured)

    @override
    def encode_turn(
        self,
        prompt: str,
        turn_context: Mapping[str, Any] | None = None,
    ) -> bytes:
        request_id = self._next_id
        self._next_id += 1
        params: dict[str, Any] = {"prompt": prompt}
        params.update(turn_context or {})
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "send_turn",
            "params": params,
        }
        return _encode(payload)

    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        payload = self._parse_object(raw_line)
        if payload is None or payload.get("jsonrpc") != "2.0":
            return None

        method = payload.get("method")
        terminal = "id" in payload and ("result" in payload or "error" in payload)
        content = _mapping(payload.get("params"))
        if terminal:
            content = _mapping(payload.get("result")) or _mapping(payload.get("error"))
        content = content or payload
        is_notification = method in {"progress", "stream"}
        return DecodedChunk(
            text=(
                self._extract_string(content, ("delta", "text", "content"))
                if is_notification or terminal
                else ""
            ),
            reasoning=self._extract_string(
                content, ("reasoning", "thought", "reasoning_content")
            ),
            tool_calls=self._extract_tool_calls(content),
            is_terminal=terminal,
            is_tool_stop=terminal and _tool_stop(payload),
            raw=payload,
        )

    @override
    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None and decoded.is_terminal:
            return True
        payload = self._parse_object(raw_line)
        return bool(
            payload
            and payload.get("jsonrpc") == "2.0"
            and "id" in payload
            and ("result" in payload or "error" in payload)
        )

    @override
    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None:
            return decoded.is_tool_stop
        payload = self._parse_object(raw_line)
        return bool(payload and payload.get("jsonrpc") == "2.0" and _tool_stop(payload))

    @override
    def build_cancel_payload(self) -> bytes | None:
        return b'{"jsonrpc": "2.0", "method": "cancel", "params": {}}\n'


class AcpDriver(StreamJsonDriver):
    """Newline-delimited Agent Communication Protocol transport."""

    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(
        protocol_name="acp",
        supports_soft_cancel=True,
        supports_multi_turn=True,
    )

    @override
    def build_argv(self, base_argv: list[str], options: Mapping[str, Any]) -> list[str]:
        configured = dict(options)
        configured.setdefault("output_format", "acp")
        return super().build_argv(base_argv, configured)

    @override
    def encode_turn(
        self,
        prompt: str,
        turn_context: Mapping[str, Any] | None = None,
    ) -> bytes:
        payload: dict[str, Any] = {"event": "turn", "payload": prompt}
        payload.update(turn_context or {})
        return _encode(payload)

    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        payload = self._parse_object(raw_line)
        if payload is None:
            return None
        event = payload.get("event")
        if not isinstance(event, str):
            return None
        content = _mapping(payload.get("payload")) or payload
        terminal = event in {"turn_complete", "tool_stop"}
        return DecodedChunk(
            text=(
                self._extract_string(content, ("payload", "text", "delta"))
                if event == "stream"
                else ""
            ),
            reasoning=self._extract_string(
                content, ("reasoning", "thought", "reasoning_content")
            ),
            tool_calls=self._extract_tool_calls(content),
            is_terminal=terminal,
            is_tool_stop=event == "tool_stop",
            raw=payload,
        )

    @override
    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None and decoded.is_terminal:
            return True
        payload = self._parse_object(raw_line)
        return bool(payload and payload.get("event") in {"turn_complete", "tool_stop"})

    @override
    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None:
            return decoded.is_tool_stop
        payload = self._parse_object(raw_line)
        return bool(payload and payload.get("event") == "tool_stop")

    @override
    def build_cancel_payload(self) -> bytes | None:
        return b'{"event": "cancel"}\n'


def create_protocol_driver(protocol_name: str) -> StdioProtocolDriver:
    """Create the driver registered for ``protocol_name``."""

    if protocol_name in {"claude-stream-json", "claude_stream_json"}:
        from core.stdio_resident.claude_driver import ClaudeStreamJsonDriver

        return ClaudeStreamJsonDriver()
    if protocol_name in {"codex-app-server", "codex_app_server"}:
        from core.stdio_resident.codex_driver import CodexAppServerDriver

        return CodexAppServerDriver()

    drivers: dict[str, type[StdioProtocolDriver]] = {
        "stream-json": StreamJsonDriver,
        "stream_json": StreamJsonDriver,
        "stream-jsonrpc": StreamJsonRpcDriver,
        "stream_jsonrpc": StreamJsonRpcDriver,
        "acp": AcpDriver,
    }
    try:
        driver_type = drivers[protocol_name]
    except KeyError as error:
        raise ValueError(f"unsupported stdio protocol: {protocol_name}") from error
    return driver_type()
