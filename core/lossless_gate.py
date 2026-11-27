"""Pure fail-closed lossless delivery decision gate (BND-001: zero I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.lossless_chunker import (
    ENVELOPE_OVERHEAD_BYTES,
    JSON_QUOTES_OVERHEAD_BYTES,
    estimate_min_frames,
)
from core.lossless_contracts import (
    DeliveryMode,
    LosslessLimits,
    LossReceipt,
    build_loss_receipt,
)


class GateAction(str, Enum):
    """Terminal decision returned by the lossless delivery gate."""

    LEGACY = "legacy"
    DELIVER_SINGLE = "deliver_single"
    DELIVER_CHUNKED = "deliver_chunked"
    REJECT = "reject"


@dataclass(frozen=True)
class GateDecision:
    """Pure decision object governing prompt delivery without silent loss."""

    action: GateAction
    mode: DeliveryMode
    estimated_frames: int
    http_status: int = 200
    receipt: LossReceipt | None = None

    @property
    def allow_silent_truncation(self) -> bool:
        """Silent truncation is strictly forbidden whenever lossless mode is active."""
        return self.action is GateAction.LEGACY


def evaluate_delivery_gate(
    prompt_text: str,
    limits: LosslessLimits,
    *,
    salt: bytes | None = None,
) -> GateDecision:
    """Decide single-frame, sequential chunked, legacy, or fail-closed 413 rejection."""
    if not limits.lossless_enabled:
        return GateDecision(
            action=GateAction.LEGACY,
            mode=DeliveryMode.LEGACY,
            estimated_frames=1,
            http_status=200,
        )

    raw_bytes = prompt_text.encode("utf-8")
    raw_len = len(raw_bytes)
    single_budget = limits.safe_frame_bytes - ENVELOPE_OVERHEAD_BYTES - JSON_QUOTES_OVERHEAD_BYTES
    est_frames = estimate_min_frames(raw_len, limits.safe_frame_bytes)

    if est_frames > limits.max_chunks:
        receipt = build_loss_receipt(
            reason="chunk_limit_exceeded",
            http_status=413,
            prompt_raw=raw_bytes,
            delivered_bytes=0,
            chunk_count=est_frames,
            chunk_index=0,
            digest_mode=limits.digest_mode,
            salt=salt,
        )
        return GateDecision(
            action=GateAction.REJECT,
            mode=DeliveryMode.LOSSLESS_FAIL_CLOSED,
            estimated_frames=est_frames,
            http_status=413,
            receipt=receipt,
        )

    if raw_len <= single_budget and est_frames == 1:
        return GateDecision(
            action=GateAction.DELIVER_SINGLE,
            mode=DeliveryMode.LOSSLESS_CHUNKED,
            estimated_frames=1,
            http_status=200,
        )

    return GateDecision(
        action=GateAction.DELIVER_CHUNKED,
        mode=DeliveryMode.LOSSLESS_CHUNKED,
        estimated_frames=est_frames,
        http_status=200,
    )
