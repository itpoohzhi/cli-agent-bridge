"""Pure policies and value objects for lossless delivery."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, Protocol

DEFAULT_CHUNK_ACK_TIMEOUT_S: Final[float] = 60.0
CHUNK_ACK_TIMEOUT_BOUNDS: Final[tuple[float, float]] = (1.0, 600.0)
DEFAULT_FINAL_TURN_IDLE_TIMEOUT_S: Final[float] = 180.0
FINAL_TURN_IDLE_TIMEOUT_BOUNDS: Final[tuple[float, float]] = (5.0, 1800.0)
MAX_ACK_PHASE_DEADLINE_S: Final[float] = 600.0
MAX_FINAL_TURN_TOTAL_S: Final[float] = 1800.0
ENV_CHUNK_ACK_TIMEOUT_S: Final[str] = "AGY_BRIDGE_LOSSLESS_CHUNK_ACK_TIMEOUT_S"
ENV_FINAL_TURN_IDLE_TIMEOUT_S: Final[str] = (
    "AGY_BRIDGE_LOSSLESS_FINAL_TURN_IDLE_TIMEOUT_S"
)
CFG_CHUNK_ACK_TIMEOUT_S: Final[str] = "lossless_chunk_ack_timeout_s"
CFG_FINAL_TURN_IDLE_TIMEOUT_S: Final[str] = "lossless_final_turn_idle_timeout_s"
LOSSLESS_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "delivery_start",
        "chunk_ack_timeout",
        "chunk_ack_eof",
        "teardown",
        "ack_phase_timeout",
        "final_turn_idle_timeout",
        "delivery_result",
    }
)


class CancelFlag(Protocol):
    """Minimal cancellation contract, independent of a threading primitive."""

    def is_set(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class DeliveryTimeouts:
    """Resolved timeout values used by the two delivery phases."""

    chunk_ack_timeout_s: float
    final_turn_idle_timeout_s: float


@dataclass(frozen=True, slots=True)
class DeliveryHooks:
    """Optional callbacks shared by transport and delivery policy code."""

    cancel_event: CancelFlag | None = None
    on_line: Callable[[str], None] | None = None
    on_snapshot: Callable[[object], None] | None = None
    salt: bytes | None = None


@dataclass(frozen=True, slots=True)
class ChunkDeliveryOptions:
    """Options for one chunked delivery attempt."""

    chunk_ack_timeout_s: float
    request_id: str
    log_fn: Callable[[str], None]
    epoch: int = 1
    hooks: DeliveryHooks | None = None


def parse_ack_event(raw_line: str) -> tuple[bool, int | None]:
    """Recognize a JSON result event and return its optional integer epoch."""
    res: tuple[bool, int | None] = (False, None)
    try:
        obj = json.loads(raw_line)
    except (TypeError, ValueError):
        obj = None
    if isinstance(obj, dict):
        tp, ev = obj.get("type"), obj.get("event")
        raw_kind = tp if tp else (ev if ev else "")
        if str(raw_kind).strip().lower() == "result":
            raw_ep = obj.get("epoch")
            ep = raw_ep if type(raw_ep) is int else None
            res = (True, ep)
    return res


def parse_timeout(raw: object) -> float | None:
    """Parse a finite positive timeout, returning ``None`` for invalid input."""
    result: float | None = None
    if not isinstance(raw, bool):
        text = str(raw).strip() if isinstance(raw, (int, float, str)) else ""
        if text:
            try:
                val = float(text)
            except (TypeError, ValueError):
                val = 0.0
            if math.isfinite(val) and val > 0:
                result = val
    return result


def resolve_timeout(
    env_raw: object,
    cfg_raw: object,
    default: float,
    bounds: tuple[float, float],
) -> float:
    """Resolve env over config over default, then clamp to supplied bounds."""
    parsed = [p for raw in (env_raw, cfg_raw, default) if (p := parse_timeout(raw))]
    val = parsed[0] if parsed else bounds[0]
    return max(bounds[0], min(bounds[1], val))


def resolve_delivery_timeouts(
    env: Mapping[str, str], dynamic_cfg: Mapping[str, object] | None = None
) -> DeliveryTimeouts:
    """Resolve both delivery timeouts without reading process-global state."""
    cfg: Mapping[str, object] = dynamic_cfg if isinstance(dynamic_cfg, Mapping) else {}
    return DeliveryTimeouts(
        chunk_ack_timeout_s=resolve_timeout(
            env.get(ENV_CHUNK_ACK_TIMEOUT_S),
            cfg.get(CFG_CHUNK_ACK_TIMEOUT_S),
            DEFAULT_CHUNK_ACK_TIMEOUT_S,
            CHUNK_ACK_TIMEOUT_BOUNDS,
        ),
        final_turn_idle_timeout_s=resolve_timeout(
            env.get(ENV_FINAL_TURN_IDLE_TIMEOUT_S),
            cfg.get(CFG_FINAL_TURN_IDLE_TIMEOUT_S),
            DEFAULT_FINAL_TURN_IDLE_TIMEOUT_S,
            FINAL_TURN_IDLE_TIMEOUT_BOUNDS,
        ),
    )


def ack_phase_deadline_s(
    n_chunks: int, chunk_ack_timeout_s: float, kill_grace_s: float
) -> float:
    """Return a bounded deadline for acknowledging all delivery frames."""
    if isinstance(n_chunks, bool) or n_chunks < 1:
        raise ValueError("n_chunks must be at least one")
    return min(n_chunks * chunk_ack_timeout_s + kill_grace_s, MAX_ACK_PHASE_DEADLINE_S)


def lossless_owns_process(
    *, slot_held: bool, persistent_mode: bool, has_lease: bool
) -> bool:
    """Whether lossless teardown owns the underlying process."""
    return slot_held and not persistent_mode and not has_lease


def _sanitize(raw: object) -> str:
    text = str(raw).replace(" ", "_").replace("\t", "_")
    text = text.replace("\r", "_").replace("\n", "_")
    return text[:120]


def format_lossless_event(event: str, fields: Mapping[str, object]) -> str:
    """Format a single-line structured event with bounded, safe field values."""
    if event not in LOSSLESS_EVENTS:
        raise ValueError(f"unknown lossless event: {event}")
    parts = [f"lossless_event event={_sanitize(event)}"]
    parts.extend(
        f"{_sanitize(key)}={_sanitize(fields[key])}" for key in sorted(fields, key=str)
    )
    return " ".join(parts)
