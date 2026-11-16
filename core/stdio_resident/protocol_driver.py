"""Protocol-independent framing for resident stdio processes."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol, cast, runtime_checkable


@dataclass(frozen=True)
class DriverCapabilities:
    """Features exposed by a stdio protocol driver."""

    protocol_name: str
    supports_soft_cancel: bool = False
    supports_multi_turn: bool = True


@dataclass
class DecodedChunk:
    """A protocol frame normalized for the resident-process core."""

    text: str = ""
    reasoning: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    is_terminal: bool = False
    is_tool_stop: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class StdioProtocolDriver(Protocol):
    """Protocol for framing, encoding and decoding stdio communication."""

    @property
    def capabilities(self) -> DriverCapabilities: ...

    def build_argv(
        self, base_argv: list[str], options: Mapping[str, Any]
    ) -> list[str]: ...

    def encode_turn(
        self,
        prompt: str,
        turn_context: Mapping[str, Any] | None = None,
    ) -> bytes: ...

    def decode_line(self, raw_line: str) -> DecodedChunk | None: ...

    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool: ...

    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool: ...

    def build_cancel_payload(self) -> bytes | None: ...


class StreamJsonDriver:
    """Newline-delimited JSON driver for streaming turn events."""

    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(
        protocol_name="stream-json",
        supports_soft_cancel=True,
        supports_multi_turn=True,
    )

    @property
    def capabilities(self) -> DriverCapabilities:
        return self._capabilities

    def build_argv(self, base_argv: list[str], options: Mapping[str, Any]) -> list[str]:
        argv = list(base_argv)
        if any(
            argument == "--output-format" or argument.startswith("--output-format=")
            for argument in argv
        ):
            return argv

        configured_args = options.get("output_format_args")
        if configured_args is not None:
            argv.extend(self._string_list(configured_args))
            return argv

        flag = options.get("output_format_flag", "--output-format")
        value = options.get("output_format", "stream-json")
        argv.extend((str(flag), str(value)))
        return argv

    def encode_turn(
        self,
        prompt: str,
        turn_context: Mapping[str, Any] | None = None,
    ) -> bytes:
        context = dict(turn_context or {})
        raw_line = context.get("raw_line")
        if raw_line is not None:
            return (str(raw_line).rstrip("\r\n") + "\n").encode()

        payload: dict[str, Any] = {"prompt": prompt}
        payload.update(context)
        return (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode()

    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        payload = self._parse_object(raw_line)
        if payload is None:
            return None

        event_type = payload.get("type")
        is_tool_stop = event_type == "tool_turn_stop"
        return DecodedChunk(
            text=self._extract_string(payload, ("content", "delta", "text")),
            reasoning=self._extract_string(payload, ("reasoning", "thought")),
            tool_calls=self._extract_tool_calls(payload),
            is_terminal=(
                event_type in {"done", "tool_turn_stop"} or payload.get("done") is True
            ),
            is_tool_stop=is_tool_stop,
            raw=payload,
        )

    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None and decoded.is_terminal:
            return True
        payload = self._parse_object(raw_line)
        if payload is None:
            return False
        return payload.get("type") in {"done", "tool_turn_stop"} or (
            payload.get("done") is True
        )

    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None:
            return decoded.is_tool_stop
        payload = self._parse_object(raw_line)
        return payload is not None and payload.get("type") == "tool_turn_stop"

    def build_cancel_payload(self) -> bytes | None:
        return b'{"type": "cancel"}\n'

    @staticmethod
    def _parse_object(raw_line: str) -> dict[str, Any] | None:
        line = raw_line.strip()
        if not line or line.startswith(("#", "//")):
            return None
        try:
            payload = cast(object, json.loads(line))
        except (json.JSONDecodeError, TypeError):
            return None
        return cast(dict[str, Any], payload) if isinstance(payload, dict) else None

    @classmethod
    def _extract_string(cls, payload: Mapping[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str):
                return value
        for container_key in ("delta", "content"):
            container = payload.get(container_key)
            if isinstance(container, dict):
                nested = cls._extract_string(cast(dict[str, Any], container), keys)
                if nested:
                    return nested
        return ""

    @staticmethod
    def _extract_tool_calls(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        candidates: list[Any] = [payload.get("tool_calls"), payload.get("tool_call")]
        delta = payload.get("delta")
        if isinstance(delta, dict):
            typed_delta = cast(dict[str, Any], delta)
            candidates.extend(
                (typed_delta.get("tool_calls"), typed_delta.get("tool_call"))
            )

        for candidate in candidates:
            if isinstance(candidate, dict):
                return [cast(dict[str, Any], candidate)]
            if isinstance(candidate, list):
                items = cast(list[object], candidate)
                return [
                    cast(dict[str, Any], item)
                    for item in items
                    if isinstance(item, dict)
                ]
        return []

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list | tuple):
            return [str(item) for item in cast(Sequence[object], value)]
        raise TypeError("output_format_args must be a string or sequence")
