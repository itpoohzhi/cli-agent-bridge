"""Общие фабрики StreamNormalizer для L1-тестов режимов инструментов."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import core.tool_emulation as emulation
from core.tool_mode import (
    NormalizerSinks,
    ToolMode,
    ToollessTagPolicy,
    build_mode_spec,
)

VALID_CALL = '<tool_call>{"name":"noop","arguments":{}}</tool_call>'
OTHER_CALL = '<tool_call>{"name":"other","arguments":{"k":1}}</tool_call>'
STRICT_MODES = (
    (ToolMode.OFF, ToollessTagPolicy.ERROR),
    (ToolMode.FORBID, ToollessTagPolicy.TEXT),
    (ToolMode.FORBID, ToollessTagPolicy.ERROR),
)


@dataclass
class Capture:
    """Нормализатор вместе с тем, что он отдал в sink-и."""

    normalizer: emulation.StreamNormalizer
    content: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def feed_chars(self, text: str) -> None:
        for char in text:
            self.normalizer.feed_text(char)

    @property
    def text(self) -> str:
        return "".join(self.content)


def make(
    mode: ToolMode,
    policy: ToollessTagPolicy = ToollessTagPolicy.TEXT,
    *,
    strict_live: bool = True,
) -> Capture:
    content: list[str] = []
    reasoning: list[str] = []
    calls: list[dict[str, Any]] = []
    sinks = NormalizerSinks(content.append, reasoning.append, calls.append)
    normalizer = emulation.StreamNormalizer.for_mode(
        build_mode_spec(mode, policy), sinks, strict_live=strict_live
    )
    return Capture(normalizer, content, reasoning, calls)
