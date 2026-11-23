"""Byte-preserving assembly of normalized chunks into client-facing stream deltas."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, cast

from core.runtime_env import (
    ConfigSnapshotError,
    env_first,
    read_config_snapshot,  # pyright: ignore[reportUnknownVariableType]
)
from core.stdio_resident.protocol_driver import DecodedChunk

DEFAULT_AGGREGATE_OUTPUT_BYTES: Final[int] = 16 * 1024 * 1024
AGGREGATE_OUTPUT_BYTES_ENV_KEYS: Final[tuple[str, ...]] = (
    "BRIDGE_STDIO_AGGREGATE_OUTPUT_BYTES",
    "BRIDGE_AGGREGATE_OUTPUT_BYTES",
)
_DYNAMIC_CONFIG_KEYS: Final[tuple[str, ...]] = (
    "BRIDGE_STDIO_AGGREGATE_OUTPUT_BYTES",
    "aggregate_output_bytes",
)
DEFAULT_STEP_SEPARATOR: Final[str] = "\n\n"
_DEFAULT_DYNAMIC_CONFIG_PATH: Final[str] = (
    "~/.config/cli-agent-bridge/dynamic_config.json"
)


class AggregateOutputLimitError(RuntimeError):
    """Typed resource failure raised when assembled output exceeds the byte cap."""

    code: str = "output_limit_exceeded"
    http_status: int = 502

    def __init__(self, limit_bytes: int, total_bytes: int) -> None:
        self.limit_bytes: int = limit_bytes
        self.total_bytes: int = total_bytes
        super().__init__(
            f"output_limit_exceeded: aggregate output {total_bytes}B exceeds cap {limit_bytes}B"
        )


@dataclass(frozen=True, slots=True)
class StepBoundary:
    """Explicit typed boundary between consecutive logical output steps."""

    separator: str = DEFAULT_STEP_SEPARATOR


@dataclass
class AssembledStreamDelta:
    """One assembled stream update ready for response serialization."""

    content: str = ""
    reasoning_content: str = ""
    tool_calls: list[dict[str, Any]] = field(  # pyright: ignore[reportExplicitAny]
        default_factory=list
    )
    is_terminal: bool = False
    is_tool_stop: bool = False


def _parse_positive_int(raw: object) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, str):
        try:
            value = int(raw.strip())
        except ValueError:
            return None
        return value if value > 0 else None
    return None


def _load_dynamic_snapshot(cfg_path: str) -> Mapping[str, object] | None:
    try:
        raw: object = read_config_snapshot(cfg_path)  # pyright: ignore[reportUnknownVariableType]
    except ConfigSnapshotError:
        return None
    return cast(Mapping[str, object], raw) if isinstance(raw, Mapping) else None


def resolve_aggregate_output_bytes(
    environ: Mapping[str, str] | None = None,
    *,
    default: int = DEFAULT_AGGREGATE_OUTPUT_BYTES,
) -> int:
    """Resolve configurable aggregate UTF-8 output byte cap from dynamic config or env."""
    env = os.environ if environ is None else environ
    cfg_path = env.get("BRIDGE_DYNAMIC_CONFIG_PATH") or os.path.expanduser(
        _DEFAULT_DYNAMIC_CONFIG_PATH
    )
    snapshot = _load_dynamic_snapshot(cfg_path)
    if snapshot is not None:
        for key in _DYNAMIC_CONFIG_KEYS:
            parsed = _parse_positive_int(snapshot.get(key))
            if parsed is not None:
                return parsed
    found = env_first(env, AGGREGATE_OUTPUT_BYTES_ENV_KEYS)
    if found is not None:
        parsed = _parse_positive_int(found[1])
        if parsed is not None:
            return parsed
    return default


def _is_chunk_step_boundary(chunk: DecodedChunk) -> bool:
    if getattr(chunk, "step_boundary", False) is True:
        return True
    raw: object = getattr(chunk, "raw", None)
    if not isinstance(raw, Mapping):
        return False
    mapping = cast(Mapping[str, object], raw)
    return (
        mapping.get("step_boundary") is True or mapping.get("type") == "step_boundary"
    )


def _delta_utf8_bytes(delta: AssembledStreamDelta) -> int:
    total = len(delta.content.encode("utf-8")) + len(
        delta.reasoning_content.encode("utf-8")
    )
    if delta.tool_calls:
        encoded = json.dumps(
            delta.tool_calls, ensure_ascii=False, separators=(",", ":")
        )
        total += len(encoded.encode("utf-8"))
    return total


class TurnStreamAssembler:
    """Byte-preserving stream assembler with typed step boundaries and aggregate byte cap."""

    def __init__(
        self,
        on_activity: Callable[[], None] | None = None,
        *,
        aggregate_output_bytes: int | None = None,
        step_separator: str = DEFAULT_STEP_SEPARATOR,
    ) -> None:
        cap = (
            resolve_aggregate_output_bytes()
            if aggregate_output_bytes is None
            else aggregate_output_bytes
        )
        if cap <= 0:
            raise ValueError("aggregate_output_bytes must be > 0")
        self._on_activity: Callable[[], None] | None = on_activity
        self._aggregate_output_bytes: int = cap
        self._step_separator: str = step_separator
        self._saw_tool_calls: bool = False
        self._has_emitted_content: bool = False
        self._pending_step_separator: str = ""
        self._last_content_tail: str = ""
        self._aggregate_bytes: int = 0

    @property
    def aggregate_bytes(self) -> int:
        """Total UTF-8 bytes emitted across content, reasoning, and tool payloads."""
        return self._aggregate_bytes

    @property
    def aggregate_output_bytes(self) -> int:
        """Configured maximum aggregate UTF-8 byte budget for this turn."""
        return self._aggregate_output_bytes

    def mark_step_boundary(self, separator: str | None = None) -> None:
        """Arm an explicit typed step boundary for the next content delta."""
        if self._has_emitted_content:
            self._pending_step_separator = (
                self._step_separator if separator is None else separator
            )

    def process_chunk(self, chunk: DecodedChunk | StepBoundary) -> AssembledStreamDelta:
        """Assemble one normalized chunk or typed step boundary into a response delta."""
        if isinstance(chunk, StepBoundary):
            self.mark_step_boundary(chunk.separator)
            return AssembledStreamDelta()

        if _is_chunk_step_boundary(chunk):
            self.mark_step_boundary()

        if chunk.text or chunk.reasoning or chunk.tool_calls:
            if self._on_activity is not None:
                self._on_activity()

        delta = AssembledStreamDelta(
            is_terminal=chunk.is_terminal,
            is_tool_stop=chunk.is_tool_stop,
        )
        if chunk.tool_calls:
            self._saw_tool_calls = True
            delta.tool_calls = list(chunk.tool_calls)
        if chunk.reasoning:
            delta.reasoning_content += chunk.reasoning
        if chunk.text:
            self._append_text(delta, chunk.text)

        self._account_bytes(delta)
        return delta

    def _append_text(self, delta: AssembledStreamDelta, text: str) -> None:
        if self._saw_tool_calls:
            delta.reasoning_content += text
            return
        content = text
        sep = self._pending_step_separator
        if sep and self._has_emitted_content:
            if not self._last_content_tail.endswith(sep) and not content.startswith(
                sep
            ):
                content = sep + content
            self._pending_step_separator = ""
        delta.content = content
        self._has_emitted_content = True
        tail_window = max(len(self._step_separator), 2)
        self._last_content_tail = (self._last_content_tail + content)[-tail_window:]

    def _account_bytes(self, delta: AssembledStreamDelta) -> None:
        next_total = self._aggregate_bytes + _delta_utf8_bytes(delta)
        if next_total > self._aggregate_output_bytes:
            raise AggregateOutputLimitError(self._aggregate_output_bytes, next_total)
        self._aggregate_bytes = next_total
