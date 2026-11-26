"""Pure, deterministic state machine for progressive stream delivery."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from enum import Enum
import json
from typing import Any, cast


class DeliveryPhase(Enum):
    LEGACY_BUFFERED = "legacy_buffered"
    PRECOMMIT = "precommit"
    LIVE = "live"
    CLOSED = "closed"


class DeliveryEventKind(Enum):
    CONTENT = "content"
    REASONING = "reasoning"
    TOOL_CALLS = "tool_calls"
    TOOL_TRACE = "tool_trace"
    ERROR = "error"
    DONE = "done"


@dataclass(frozen=True)
class DeliveryEvent:
    epoch: int
    seq: int
    kind: DeliveryEventKind
    channel: str
    payload: str
    deliverable: bool = True
    now_ms: float = 0.0


@dataclass(frozen=True)
class DeliveryAction:
    kind: str
    channel: str = ""
    payload: str = ""
    seq: int = -1


@dataclass(frozen=True)
class DeliveryState:
    progressive: bool = False
    phase: DeliveryPhase = DeliveryPhase.LEGACY_BUFFERED
    epoch: int = 0
    wire_committed: bool = False
    last_sent_seq: int = -1
    emitted_events: int = 0
    precommit_started_ms: float = 0.0
    max_precommit_hold_ms: float = 15000.0
    pending_bytes: int = 0
    max_precommit_bytes: int = 262144
    stale_dropped: int = 0


def initial_delivery_state(
    progressive: bool,
    epoch: int = 0,
    precommit_started_ms: float = 0.0,
    max_precommit_hold_ms: float = 15000.0,
) -> DeliveryState:
    phase = DeliveryPhase.PRECOMMIT if progressive else DeliveryPhase.LEGACY_BUFFERED
    return DeliveryState(
        progressive=progressive,
        phase=phase,
        epoch=epoch,
        precommit_started_ms=precommit_started_ms,
        max_precommit_hold_ms=max_precommit_hold_ms,
    )


@dataclass(frozen=True)
class TurnSummaryMetrics:
    b05_skipped_chars: int = 0
    b05_flushed_tail_chars: int = 0
    midstream_replay_blocked: bool = False
    post_live_replay_attempted: bool = False
    client_gone: bool = False
    tool_turn_active: bool = False
    tool_parse_error: bool = False
    upstream_rc: int | None = None
    ttft_ms: float | None = None
    total_ms: float = 0.0


def _finish(
    state: DeliveryState, event: DeliveryEvent
) -> tuple[DeliveryState, tuple[DeliveryAction, ...]]:
    closed = replace(state, phase=DeliveryPhase.CLOSED)
    return closed, (DeliveryAction("finish", "", event.payload, event.seq),)


def _step_precommit(event: DeliveryEvent) -> tuple[DeliveryAction, ...]:
    textual = {
        DeliveryEventKind.CONTENT,
        DeliveryEventKind.REASONING,
        DeliveryEventKind.TOOL_CALLS,
    }
    if event.kind in textual and event.deliverable and event.payload:
        return (
            DeliveryAction("flush_and_emit", event.channel, event.payload, event.seq),
        )
    if event.kind is DeliveryEventKind.TOOL_TRACE:
        return (DeliveryAction("stage", "tool_trace", event.payload, event.seq),)
    return (DeliveryAction("stage", event.channel, event.payload, event.seq),)


def step_delivery(
    state: DeliveryState, event: DeliveryEvent
) -> tuple[DeliveryState, tuple[DeliveryAction, ...]]:
    if event.epoch != state.epoch:
        stale = replace(state, stale_dropped=state.stale_dropped + 1)
        return stale, (DeliveryAction("drop_stale"),)
    if state.phase is DeliveryPhase.CLOSED:
        return state, (DeliveryAction("drop_stale"),)
    if event.kind in {DeliveryEventKind.DONE, DeliveryEventKind.ERROR}:
        return _finish(state, event)
    if not state.progressive:
        return state, (
            DeliveryAction("stage", event.channel, event.payload, event.seq),
        )
    if state.phase is DeliveryPhase.PRECOMMIT:
        return state, _step_precommit(event)
    return state, (DeliveryAction("emit", event.channel, event.payload, event.seq),)


def mark_sent(state: DeliveryState, seq: int) -> DeliveryState:
    phase = DeliveryPhase.LIVE if state.progressive else state.phase
    return replace(
        state,
        wire_committed=True,
        phase=phase,
        last_sent_seq=max(state.last_sent_seq, seq),
        emitted_events=state.emitted_events + 1,
        pending_bytes=0,
    )


def can_retry_after_failure(state: DeliveryState) -> bool:
    return not state.wire_committed


def next_retry_epoch(state: DeliveryState, now_ms: float = 0.0) -> DeliveryState:
    if state.wire_committed:
        return state
    phase = (
        DeliveryPhase.PRECOMMIT if state.progressive else DeliveryPhase.LEGACY_BUFFERED
    )
    return replace(
        state,
        epoch=state.epoch + 1,
        pending_bytes=0,
        precommit_started_ms=now_ms,
        phase=phase,
    )


def canonical_trace_key(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def _strip_emitted_chunk(chunk: str, emitted: str, pos: int) -> tuple[str, int, int]:
    if pos < 0 or pos >= len(emitted):
        return chunk, pos, 0
    if chunk == emitted[pos : pos + len(chunk)]:
        size = len(chunk)
        return "", pos + size, size
    remainder = emitted[pos:]
    if len(chunk) > len(remainder) and chunk.startswith(remainder):
        return chunk[len(remainder) :], len(emitted), len(remainder)
    return chunk, -1, 0


def filter_unemitted_retained(
    retained: Sequence[tuple[str, Any]],  # pyright: ignore[reportExplicitAny]
    *,
    emitted_content: str = "",
    emitted_reasoning: str = "",
    emitted_tool_traces: Sequence[str] = (),
) -> tuple[list[tuple[str, Any]], int]:  # pyright: ignore[reportExplicitAny]
    filtered: list[tuple[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    positions = {"text": 0, "reasoning": 0}
    emitted = {"text": emitted_content, "reasoning": emitted_reasoning}
    trace_pos = 0
    skipped = 0
    for kind, payload in retained:  # pyright: ignore[reportAny]
        if kind in positions:
            chunk, new_pos, count = _strip_emitted_chunk(
                cast(str, payload), emitted[kind], positions[kind]
            )
            positions[kind] = new_pos
            skipped += count
            if chunk:
                filtered.append((kind, chunk))
        elif kind == "tool_trace":
            key = canonical_trace_key(payload)  # pyright: ignore[reportAny]
            if (
                trace_pos < len(emitted_tool_traces)
                and key == emitted_tool_traces[trace_pos]
            ):
                trace_pos += 1
                skipped += len(key)
            else:
                filtered.append((kind, payload))
        else:
            filtered.append((kind, payload))
    return filtered, skipped


def sanitizer_headers(tool_turn_active: bool) -> tuple[tuple[str, str], ...]:
    if tool_turn_active is True:
        return (("X-Bridge-Tool-Sanitized", "1"),)
    return ()


def format_turn_summary(state: DeliveryState, metrics: TurnSummaryMetrics) -> str:
    summary: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
        "event": "agy_turn_delivery_summary",
        "mode": "progressive" if state.progressive else "legacy",
        "phase_end": state.phase.value,
        "emitted_events": state.emitted_events,
    }
    summary.update(asdict(metrics))
    return json.dumps(
        summary, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
