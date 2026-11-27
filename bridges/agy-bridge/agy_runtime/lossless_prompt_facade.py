"""Lossless prompt facade for agy-bridge: two-profile routing (legacy vs lossless chunked, 0 silent loss)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from core.lossless_chunker import ChunkLimitExceededError, iter_ndjson_frames
from core.lossless_contracts import LosslessLimits, LossReceipt, build_loss_receipt, resolve_lossless_limits
from core.lossless_gate import GateAction, evaluate_delivery_gate

from .input_guard_policy import ClientCompactionRequired
from .loss_receipt_context import send_client_compaction_required


class LosslessRejectionError(ClientCompactionRequired):
    """Fail-closed HTTP 413/400 rejection carrying a THREAT-001 redacted x_bridge_loss receipt."""

    def __init__(self, receipt: LossReceipt) -> None:
        Exception.__init__(self, f"lossless_rejected:{receipt.reason}")
        self.http_status: int = receipt.http_status
        self.receipt: LossReceipt = receipt
        self.body: dict[str, object] = {
            "error": {
                "type": "invalid_request_error",
                "code": "prompt_too_large" if receipt.http_status == 413 else "context_length_exceeded",
                "param": "messages",
                "x_reason": receipt.reason,
                "message": (
                    f"Lossless delivery refused ({receipt.reason}): "
                    f"prompt_bytes={receipt.prompt_bytes}, chunks={receipt.chunk_count}"
                ),
                "x_bridge_loss": receipt.to_wire_dict(),
            }
        }


@dataclass(frozen=True)
class PromptRenderDeps:
    """Injected pure/server callbacks keeping facade decoupled from server.py globals."""

    render_message: Callable[..., str]
    attachments_block: Callable[[list[dict[str, object]]], str]
    join_parts: Callable[[list[str], str], str]
    prompt_budget: Callable[[int], int]
    ndjson_bytes: Callable[[str], int]
    prune_or_compact: Callable[[list[tuple[int, str, str]], str, int], str]
    with_notice: Callable[..., str]
    record_lossless: Callable[[], None]
    head_pruning_enabled: Callable[[], bool]
    truncation_notice_enabled: Callable[[], bool]
    notice_policy: object
    config_path: Path


def _read_dynamic_cfg(config_path: Path) -> dict[str, object]:
    try:
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except (OSError, ValueError):
        return {}


def read_agy_lossless_limits(config_path: Path) -> LosslessLimits:
    """Resolve agy-bridge LosslessLimits (os.environ > dynamic_config.json > safe default)."""
    return resolve_lossless_limits(os.environ, _read_dynamic_cfg(config_path))


def render_messages_prompt(
    messages: list[Any],
    deps: PromptRenderDeps,
    *,
    images: list[dict[str, object]] | None = None,
    img_start: int = 0,
    reserve_bytes: int = 0,
    sort_keys: bool = False,
) -> str:
    """Render full turn prompt; in lossless mode never silently compacts/truncates."""
    counter = [0]
    img_counter = [img_start]
    blocks: list[tuple[int, str, str]] = []
    for index, msg in enumerate(messages):
        rendered = deps.render_message(msg, counter, img_counter, sort_keys=sort_keys)
        if rendered:
            role = str(msg.get("role") or "user") if isinstance(msg, dict) else ""
            blocks.append((index, role, rendered))
    tail_block = deps.attachments_block(images) if images else ""
    text = deps.join_parts([b[2] for b in blocks], tail_block)
    if not text:
        return "Reply with exactly: PONG"

    limits = read_agy_lossless_limits(deps.config_path)
    if limits.lossless_enabled:
        decision = evaluate_delivery_gate(text, limits)
        if decision.action is GateAction.REJECT and decision.receipt is not None:
            raise LosslessRejectionError(decision.receipt)
        deps.record_lossless()
        return text

    limit = deps.prompt_budget(reserve_bytes)
    if not deps.head_pruning_enabled() or deps.ndjson_bytes(text) <= limit:
        deps.record_lossless()
        return text
    pruned = deps.prune_or_compact(blocks, tail_block, limit)
    if not deps.truncation_notice_enabled():
        return pruned
    rp = partial(deps.prune_or_compact, blocks, tail_block)
    return deps.with_notice(pruned, blocks, rp, deps.notice_policy, limit)


def ensure_prompt_fits_or_pass(
    prompt: str,
    *,
    limit: int,
    ndjson_bytes_fn: Callable[[str], int],
    middle_prune_fn: Callable[[str, int], str],
    log_fn: Callable[[str], None],
    config_path: Path,
) -> str:
    """Legacy middle-prune guard; bypassed cleanly when lossless chunked delivery is enabled."""
    if read_agy_lossless_limits(config_path).lossless_enabled:
        return prompt
    size = ndjson_bytes_fn(prompt)
    if size <= limit:
        return prompt
    pruned = middle_prune_fn(prompt, limit - ndjson_bytes_fn(""))
    log_fn(f"prompt middle-pruned: ndjson bytes {size} -> {ndjson_bytes_fn(pruned)}")
    return pruned


def build_run_stdin_line(
    prompt: str,
    *,
    head_pruning_enabled: bool,
    ensure_fit_fn: Callable[[str], str],
    ndjson_user_line_fn: Callable[[str], str],
    config_path: Path,
) -> str:
    """Build NDJSON stdin payload: sequential lossless frames when enabled, single line in legacy."""
    limits = read_agy_lossless_limits(config_path)
    if limits.lossless_enabled:
        parts: list[str] = []
        try:
            for frame in iter_ndjson_frames(
                prompt,
                safe_frame_bytes=limits.safe_frame_bytes,
                max_chunks=limits.max_chunks,
            ):
                parts.append(frame.ndjson_bytes.decode("utf-8"))
        except ChunkLimitExceededError as exc:
            receipt = build_loss_receipt(
                reason="chunk_limit_exceeded",
                http_status=413,
                prompt_raw=prompt.encode("utf-8"),
                chunk_count=exc.estimated_chunks,
                digest_mode=limits.digest_mode,
            )
            raise LosslessRejectionError(receipt) from exc
        return "".join(parts)

    if head_pruning_enabled:
        prompt = ensure_fit_fn(prompt)
    return ndjson_user_line_fn(prompt)


def send_rejection_response(handler: Any, error: ClientCompactionRequired) -> None:
    """Send 413/400 for LosslessRejectionError or delegate to legacy 400 compaction response."""
    if isinstance(error, LosslessRejectionError):
        handler._send(error.http_status, error.body)  # noqa: SLF001
        return
    send_client_compaction_required(handler, error)
