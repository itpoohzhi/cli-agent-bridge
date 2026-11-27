"""Pure agent-agnostic lossless contracts, SSOT limits, and redacted receipts (BND-001: zero I/O)."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Final

DEFAULT_SAFE_FRAME_BYTES: Final[int] = 90112
HARD_FRAME_CLAMP_BYTES: Final[int] = 98304
MIN_FRAME_BYTES: Final[int] = 16384
DEFAULT_MAX_CHUNKS: Final[int] = 16
MIN_CHUNKS: Final[int] = 1
MAX_CHUNKS: Final[int] = 64

DEFAULT_MAX_CONCURRENCY: Final[int] = 4
DEFAULT_MAX_QUEUE: Final[int] = 2
DEFAULT_QUEUE_WAIT_S: Final[float] = 10.0
DEFAULT_KILL_GRACE_S: Final[float] = 1.5
DEFAULT_DIGEST_MODE: Final[str] = "salted_hmac"

_BOOL_MAP: Final[dict[str, bool]] = {
    "1": True,
    "true": True,
    "yes": True,
    "on": True,
    "0": False,
    "false": False,
    "no": False,
    "off": False,
}


class DeliveryMode(str, Enum):
    """Prompt delivery mode for a bridge request."""

    LEGACY = "legacy"
    LOSSLESS_CHUNKED = "lossless_chunked"
    LOSSLESS_FAIL_CLOSED = "lossless_fail_closed"


class RefuseStatusMode(str, Enum):
    """HTTP status mode when muse-bridge refuses an oversized mandatory context."""

    LEGACY_502 = "legacy_502"
    FAIL_CLOSED_413 = "413"


@dataclass(frozen=True)
class LosslessLimits:
    """Single source of truth for bridge lossless delivery and admission limits."""

    lossless_enabled: bool = False
    safe_frame_bytes: int = DEFAULT_SAFE_FRAME_BYTES
    hard_frame_clamp_bytes: int = HARD_FRAME_CLAMP_BYTES
    max_chunks: int = DEFAULT_MAX_CHUNKS
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    max_queue: int = DEFAULT_MAX_QUEUE
    queue_wait_s: float = DEFAULT_QUEUE_WAIT_S
    kill_grace_s: float = DEFAULT_KILL_GRACE_S
    muse_lossless_enabled: bool = False
    muse_refuse_status_mode: RefuseStatusMode = RefuseStatusMode.LEGACY_502
    digest_mode: str = DEFAULT_DIGEST_MODE


@dataclass(frozen=True)
class ChunkFrame:
    """Single valid UTF-8/JSON NDJSON user frame for stream-json delivery."""

    index: int
    total_hint: int
    ndjson_bytes: bytes
    text_bytes: int
    is_synthetic: bool
    epoch: int


@dataclass(frozen=True)
class ChunkSummary:
    """Streaming summary produced without retaining all frame buffers."""

    total_frames: int
    raw_utf8_bytes: int
    total_ndjson_bytes: int
    max_frame_bytes: int
    sha256_hex: str


@dataclass(frozen=True)
class LossReceipt:
    """Redacted metadata-only receipt (THREAT-001: 0 bytes of raw prompt payload)."""

    reason: str
    http_status: int
    prompt_bytes: int
    delivered_bytes: int
    chunk_count: int
    chunk_index: int
    digest_mode: str
    prompt_digest: str

    def to_wire_dict(self) -> dict[str, object]:
        """Serialize strictly allow-listed metadata for x_bridge_loss."""
        return {
            "schema": "x_bridge_loss/v2",
            "reason": self.reason,
            "http_status": self.http_status,
            "prompt_bytes": self.prompt_bytes,
            "delivered_bytes": self.delivered_bytes,
            "chunk_count": self.chunk_count,
            "chunk_index": self.chunk_index,
            "digest_mode": self.digest_mode,
            "prompt_digest": self.prompt_digest,
        }


def _pick_raw(
    env: Mapping[str, str],
    dynamic_cfg: Mapping[str, object] | None,
    env_key: str,
    dyn_key: str,
) -> object:
    env_val = env.get(env_key, "").strip()
    if env_val:
        return env_val
    if dynamic_cfg is not None:
        return dynamic_cfg.get(dyn_key)
    return None


def _parse_bool(raw: object, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    return _BOOL_MAP.get(str(raw).strip().lower(), default)


def _parse_int(raw: object, default: int, bounds: tuple[int, int]) -> int:
    if raw is None or isinstance(raw, bool):
        return default
    text = str(raw).strip()
    if not text:
        return default
    try:
        val = int(text)
    except ValueError:
        return default
    return max(bounds[0], min(bounds[1], val))


def _parse_float(raw: object, default: float, bounds: tuple[float, float]) -> float:
    if raw is None or isinstance(raw, bool):
        return default
    text = str(raw).strip()
    if not text:
        return default
    try:
        val = float(text)
    except ValueError:
        return default
    if val != val or val in (float("inf"), float("-inf")):
        return default
    return max(bounds[0], min(bounds[1], val))


def _parse_refuse_mode(raw: object) -> RefuseStatusMode:
    if isinstance(raw, RefuseStatusMode):
        return raw
    text = str(raw or "").strip().lower()
    if text in ("413", "fail_closed_413", "payload_too_large"):
        return RefuseStatusMode.FAIL_CLOSED_413
    return RefuseStatusMode.LEGACY_502


def _parse_digest_mode(raw: object) -> str:
    text = str(raw or "").strip().lower()
    if text in ("omitted", "none"):
        return "omitted"
    return DEFAULT_DIGEST_MODE


def resolve_lossless_limits(
    env: Mapping[str, str],
    dynamic_cfg: Mapping[str, object] | None = None,
) -> LosslessLimits:
    """Resolve LosslessLimits with strict priority: env > dynamic_cfg > safe default."""
    clamp = _parse_int(
        _pick_raw(env, dynamic_cfg, "AGY_BRIDGE_HARD_FRAME_CLAMP_BYTES", "hard_frame_clamp_bytes"),
        HARD_FRAME_CLAMP_BYTES,
        (MIN_FRAME_BYTES, HARD_FRAME_CLAMP_BYTES),
    )
    safe_frame = _parse_int(
        _pick_raw(env, dynamic_cfg, "AGY_BRIDGE_SAFE_FRAME_BYTES", "safe_frame_bytes"),
        DEFAULT_SAFE_FRAME_BYTES,
        (MIN_FRAME_BYTES, clamp),
    )
    return LosslessLimits(
        lossless_enabled=_parse_bool(
            _pick_raw(env, dynamic_cfg, "AGY_BRIDGE_LOSSLESS_ENABLED", "lossless_delivery_enabled"),
            False,
        ),
        safe_frame_bytes=safe_frame,
        hard_frame_clamp_bytes=clamp,
        max_chunks=_parse_int(
            _pick_raw(env, dynamic_cfg, "AGY_BRIDGE_LOSSLESS_MAX_CHUNKS", "lossless_max_chunks"),
            DEFAULT_MAX_CHUNKS,
            (MIN_CHUNKS, MAX_CHUNKS),
        ),
        max_concurrency=_parse_int(
            _pick_raw(env, dynamic_cfg, "AGY_BRIDGE_LOSSLESS_MAX_CONCURRENCY", "lossless_max_concurrency"),
            DEFAULT_MAX_CONCURRENCY,
            (1, 16),
        ),
        max_queue=_parse_int(
            _pick_raw(env, dynamic_cfg, "AGY_BRIDGE_LOSSLESS_MAX_QUEUE", "lossless_max_queue"),
            DEFAULT_MAX_QUEUE,
            (0, 16),
        ),
        queue_wait_s=_parse_float(
            _pick_raw(env, dynamic_cfg, "AGY_BRIDGE_LOSSLESS_QUEUE_WAIT_S", "lossless_queue_wait_s"),
            DEFAULT_QUEUE_WAIT_S,
            (0.1, 60.0),
        ),
        kill_grace_s=_parse_float(
            _pick_raw(env, dynamic_cfg, "AGY_BRIDGE_LOSSLESS_KILL_GRACE_S", "lossless_kill_grace_s"),
            DEFAULT_KILL_GRACE_S,
            (0.05, 10.0),
        ),
        muse_lossless_enabled=_parse_bool(
            _pick_raw(env, dynamic_cfg, "MUSE_BRIDGE_LOSSLESS_ENABLED", "muse_lossless_enabled"),
            False,
        ),
        muse_refuse_status_mode=_parse_refuse_mode(
            _pick_raw(env, dynamic_cfg, "MUSE_BRIDGE_REFUSE_STATUS_MODE", "muse_refuse_status_mode")
        ),
        digest_mode=_parse_digest_mode(
            _pick_raw(env, dynamic_cfg, "BRIDGE_LOSS_RECEIPT_DIGEST_MODE", "loss_receipt_digest_mode")
        ),
    )


def build_loss_receipt(
    *,
    reason: str,
    http_status: int,
    prompt_raw: bytes,
    delivered_bytes: int = 0,
    chunk_count: int = 0,
    chunk_index: int = 0,
    digest_mode: str = DEFAULT_DIGEST_MODE,
    salt: bytes | None = None,
) -> LossReceipt:
    """Create a THREAT-001 redacted LossReceipt with zero raw prompt bytes."""
    mode = _parse_digest_mode(digest_mode)
    if mode == "omitted":
        digest = ""
    else:
        key = salt if salt else b"bridge-loss-default-salt"
        digest = hmac.new(key, prompt_raw, hashlib.sha256).hexdigest()[:16]
    return LossReceipt(
        reason=reason,
        http_status=http_status,
        prompt_bytes=len(prompt_raw),
        delivered_bytes=max(0, delivered_bytes),
        chunk_count=max(0, chunk_count),
        chunk_index=max(0, chunk_index),
        digest_mode=mode,
        prompt_digest=digest,
    )
