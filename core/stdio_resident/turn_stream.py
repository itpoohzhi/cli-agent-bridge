"""Assembly of normalized chunks into client-facing stream deltas."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.stdio_resident.protocol_driver import DecodedChunk


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


class TurnStreamAssembler:
    """Route normalized chunks while preserving stream invariants."""

    def __init__(self, on_activity: Callable[[], None] | None = None) -> None:
        self._on_activity: Callable[[], None] | None = on_activity
        self._saw_tool_calls: bool = False
        self._has_emitted_content: bool = False
        self._last_char: str = ""

    def process_chunk(self, chunk: DecodedChunk) -> AssembledStreamDelta:
        """Assemble one normalized chunk into a response delta."""

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
            if self._saw_tool_calls:
                delta.reasoning_content += chunk.text
            else:
                content = chunk.text
                raw = getattr(chunk, "raw", None)
                is_delta = isinstance(raw, dict) and raw.get("method") in {
                    "item/delta", "item.delta", "run.output.delta",
                }
                if (
                    not is_delta
                    and self._has_emitted_content
                    and self._last_char
                    and self._last_char not in ("\n", " ")
                ):
                    content = "\n\n" + content
                delta.content = content
                self._has_emitted_content = True
                self._last_char = content[-1] if content else self._last_char

        return delta
