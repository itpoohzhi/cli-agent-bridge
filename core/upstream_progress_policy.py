"""Pure classifier for the reserved ``bridge_liveness`` SSE event."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, cast

ENV_LIVENESS_MAX_FRAME_BYTES = "BRIDGE_LIVENESS_MAX_FRAME_BYTES"
MIN_LIVENESS_MAX_FRAME_BYTES = 1
MAX_LIVENESS_MAX_FRAME_BYTES = 4096
DEFAULT_LIVENESS_MAX_FRAME_BYTES = MAX_LIVENESS_MAX_FRAME_BYTES
MAX_UPSTREAM_PROGRESS_EVENTS = 2
DEFAULT_UPSTREAM_PROGRESS_MAX_EVENTS = MAX_UPSTREAM_PROGRESS_EVENTS
MIN_UPSTREAM_PROGRESS_INTERVAL_S = 5.0
DEFAULT_UPSTREAM_PROGRESS_MIN_INTERVAL_S = MIN_UPSTREAM_PROGRESS_INTERVAL_S
BRIDGE_LIVENESS_MARKER = b"event: bridge_liveness"

ORDINARY = "ordinary"
STRIP = "strip"
ERROR = "error"
PROGRESS = "progress"
Disposition = Literal["ordinary", "strip", "error", "progress"]

_OUTER_KEYS = frozenset({"bridge_liveness"})
_INNER_KEYS = frozenset({"v", "kind", "seq", "source"})
_SOURCES = frozenset({"process", "transcript", "reasoning"})
_MAX_SEQ = (1 << 63) - 1


@dataclass(frozen=True)
class CompleteEventDecision:
    """Classification plus the next request-scoped sequence cursor."""

    disposition: Disposition
    highest_seq: int

    @property
    def reserved(self) -> bool:
        return self.disposition != ORDINARY


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def _wire_lines(raw: bytes) -> list[bytes]:
    lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        _ = lines.pop()
    return [line[:-1] if line.endswith(b"\r") else line for line in lines]


def classify_complete_sse_event(
    raw: bytes,
    highest_seq: int,
    max_frame_bytes: int,
) -> CompleteEventDecision:
    """Classify one completely assembled event without I/O or mutable state."""

    lines = _wire_lines(raw)
    if BRIDGE_LIVENESS_MARKER not in lines:
        return CompleteEventDecision(ORDINARY, highest_seq)
    if len(raw) > max_frame_bytes:
        return CompleteEventDecision(ERROR, highest_seq)

    event_fields = [line for line in lines if line.startswith(b"event:")]
    if event_fields != [BRIDGE_LIVENESS_MARKER]:
        return CompleteEventDecision(ERROR, highest_seq)

    if lines and lines[-1] == b"":
        _ = lines.pop()
    data_lines: list[bytes] = []
    for line in lines:
        if line == BRIDGE_LIVENESS_MARKER:
            continue
        if not line.startswith(b"data:"):
            return CompleteEventDecision(ERROR, highest_seq)
        value = line[5:]
        data_lines.append(value[1:] if value.startswith(b" ") else value)
    if not data_lines:
        return CompleteEventDecision(ERROR, highest_seq)

    try:
        payload = cast(
            object,
            json.loads(
                b"\n".join(data_lines).decode("utf-8"),
                object_pairs_hook=_unique_object,
            ),
        )
    except (UnicodeDecodeError, ValueError):
        return CompleteEventDecision(ERROR, highest_seq)
    if not isinstance(payload, dict):
        return CompleteEventDecision(ERROR, highest_seq)
    outer = cast(dict[str, object], payload)
    if frozenset(outer) != _OUTER_KEYS:
        return CompleteEventDecision(ERROR, highest_seq)
    evidence_value = outer.get("bridge_liveness")
    if not isinstance(evidence_value, dict):
        return CompleteEventDecision(ERROR, highest_seq)
    evidence = cast(dict[str, object], evidence_value)
    if frozenset(evidence) != _INNER_KEYS:
        return CompleteEventDecision(ERROR, highest_seq)

    version = evidence.get("v")
    kind = evidence.get("kind")
    seq = evidence.get("seq")
    source = evidence.get("source")
    if (
        type(version) is not int
        or version != 1
        or type(kind) is not str
        or kind != "progress"
        or type(source) is not str
        or source not in _SOURCES
        or type(seq) is not int
        or not 1 <= seq <= _MAX_SEQ
    ):
        return CompleteEventDecision(ERROR, highest_seq)
    if seq <= highest_seq:
        return CompleteEventDecision(STRIP, highest_seq)
    return CompleteEventDecision(PROGRESS, seq)
