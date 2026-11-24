"""Terminal usage emission policy for the claude-p bridge (pure)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def should_emit_terminal_usage(
    stream_options: Any, *, emit_when_unspecified: bool = False
) -> bool:
    """Emit final usage chunk only when the client asked for it.

    Safe default ``False`` (compat with harnesses that treat unsolicited
    usage chunks as protocol violations). F-004: an explicit client
    ``include_usage`` (True or False) is always honoured as-is.
    """
    if isinstance(stream_options, Mapping) and "include_usage" in stream_options:
        return stream_options.get("include_usage") is True
    return bool(emit_when_unspecified)
