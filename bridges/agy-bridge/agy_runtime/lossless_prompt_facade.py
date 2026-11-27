"""Lossless prompt & runtime facade for agy-bridge (two-profile legacy vs chunked lossless, 0 silent loss)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from core.lossless_chunker import ChunkLimitExceededError, iter_ndjson_frames
from core.lossless_contracts import (
    LosslessLimits,
    LossReceipt,
    build_loss_receipt,
    resolve_lossless_limits,
)
from core.lossless_gate import GateAction, evaluate_delivery_gate

from .chunk_delivery_adapter import ChunkDeliveryResult, deliver_chunked_prompt
from .input_guard_policy import ClientCompactionRequired
from .loss_receipt_context import send_client_compaction_required
from .process_admission_guard import AdmissionOverloadError, ProcessAdmissionGuard

_GUARD_LOCK = threading.Lock()
_GUARDS: dict[str, ProcessAdmissionGuard] = {}
_EPOCH_COUNTER = 0


class LosslessRejectionError(ClientCompactionRequired):
    """Fail-closed HTTP 413/400 rejection carrying a THREAT-001 redacted x_bridge_loss receipt."""

    def __init__(self, receipt: LossReceipt) -> None:
        Exception.__init__(self, f"lossless_rejected:{receipt.reason}")
        self.http_status: int = receipt.http_status
        self.receipt: LossReceipt = receipt
        code = "prompt_too_large" if receipt.http_status == 413 else "context_length_exceeded"
        msg = f"Lossless delivery refused ({receipt.reason}): prompt_bytes={receipt.prompt_bytes}, chunks={receipt.chunk_count}"
        self.body: dict[str, object] = {
            "error": {
                "type": "invalid_request_error", "code": code, "param": "messages",
                "x_reason": receipt.reason, "message": msg, "x_bridge_loss": receipt.to_wire_dict(),
            }
        }


@dataclass(frozen=True)
class PromptRenderDeps:
    """Injected server callbacks keeping facade decoupled from server.py globals."""

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


def get_admission_guard(config_path: Path, limits: LosslessLimits | None = None) -> ProcessAdmissionGuard:
    """Return process-wide ProcessAdmissionGuard keyed by config_path + capacity tuple."""
    lim = read_agy_lossless_limits(config_path) if limits is None else limits
    key = f"{config_path}:{lim.max_concurrency}:{lim.max_queue}:{lim.queue_wait_s}:{lim.kill_grace_s}"
    with _GUARD_LOCK:
        guard = _GUARDS.get(key)
        if guard is None:
            guard = ProcessAdmissionGuard.from_limits(lim)
            _GUARDS[key] = guard
        return guard


def _next_epoch() -> int:
    global _EPOCH_COUNTER
    with _GUARD_LOCK:
        _EPOCH_COUNTER += 1
        return _EPOCH_COUNTER


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
    counter, img_counter = [0], [img_start]
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
    return deps.with_notice(pruned, blocks, partial(deps.prune_or_compact, blocks, tail_block), deps.notice_policy, limit)


def ensure_prompt_fits_or_pass(
    prompt: str, *, limit: int, ndjson_bytes_fn: Callable[[str], int],
    middle_prune_fn: Callable[[str, int], str], log_fn: Callable[[str], None], config_path: Path,
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
    prompt: str, *, head_pruning_enabled: bool, ensure_fit_fn: Callable[[str], str],
    ndjson_user_line_fn: Callable[[str], str], config_path: Path,
) -> str:
    """Build NDJSON stdin payload (single line in legacy or validated NDJSON sequence in lossless)."""
    limits = read_agy_lossless_limits(config_path)
    if limits.lossless_enabled:
        try:
            return "".join(
                f.ndjson_bytes.decode("utf-8")
                for f in iter_ndjson_frames(prompt, safe_frame_bytes=limits.safe_frame_bytes, max_chunks=limits.max_chunks)
            )
        except ChunkLimitExceededError as exc:
            receipt = build_loss_receipt(
                reason="chunk_limit_exceeded", http_status=413, prompt_raw=prompt.encode("utf-8"),
                chunk_count=exc.estimated_chunks, digest_mode=limits.digest_mode,
            )
            raise LosslessRejectionError(receipt) from exc
    if head_pruning_enabled:
        prompt = ensure_fit_fn(prompt)
    return ndjson_user_line_fn(prompt)


def prepare_run_lossless_state(
    run: Any, prompt: str, *, head_pruning_enabled: bool, ensure_fit_fn: Callable[[str], str],
    ndjson_user_line_fn: Callable[[str], str], config_path: Path,
) -> str:
    """Wire ProcessAdmissionGuard and chunk delivery metadata onto Run; returns stdin_line."""
    limits = read_agy_lossless_limits(config_path)
    setattr(run, "_lossless_slot_held", False)
    setattr(run, "_lossless_chunked", False)
    if not limits.lossless_enabled:
        return ndjson_user_line_fn(ensure_fit_fn(prompt) if head_pruning_enabled else prompt)

    decision = evaluate_delivery_gate(prompt, limits)
    if decision.action is GateAction.REJECT and decision.receipt is not None:
        raise LosslessRejectionError(decision.receipt)

    guard = get_admission_guard(config_path, limits)
    guard.acquire()
    try:
        stdin_payload = build_run_stdin_line(
            prompt, head_pruning_enabled=False, ensure_fit_fn=ensure_fit_fn,
            ndjson_user_line_fn=ndjson_user_line_fn, config_path=config_path,
        )
    except BaseException:
        guard.release()
        raise

    for key, val in (
        ("_lossless_guard", guard), ("_lossless_limits", limits), ("_lossless_prompt", prompt),
        ("_lossless_epoch", _next_epoch()), ("_lossless_slot_held", True),
        ("_lossless_chunked", decision.action is GateAction.DELIVER_CHUNKED),
        ("_lossless_done", threading.Event()), ("_lossless_result", None),
    ):
        setattr(run, key, val)
    return stdin_payload


def feed_run_stdin_or_lossless(run: Any, legacy_feed_fn: Callable[[Any], None]) -> None:
    """Dispatch Run._feed_stdin to sequential chunk_delivery_adapter when multi-chunk lossless is active."""
    if not bool(getattr(run, "_lossless_chunked", False)):
        legacy_feed_fn(run)
        return
    done: threading.Event = getattr(run, "_lossless_done")
    try:
        cancel_ev = getattr(run, "_stop_watch", None)
        res = deliver_chunked_prompt(
            getattr(run, "proc"), getattr(run, "_lossless_prompt"),
            getattr(run, "_lossless_limits"), getattr(run, "_lossless_guard"),
            epoch=int(getattr(run, "_lossless_epoch", 1)),
            cancel_event=cancel_ev if isinstance(cancel_ev, threading.Event) else None,
        )
        setattr(run, "_lossless_result", res)
    finally:
        done.set()


def iter_run_stdout_or_lossless(
    run: Any,
    legacy_iter_fn: Callable[[Any], Iterator[str]],
    *,
    wait_timeout_s: float | None = None,
) -> Iterator[str]:
    """Yield all stdout lines of the final turn in lossless mode with bounded wait (synthetic ACKs filtered)."""
    if not bool(getattr(run, "_lossless_chunked", False)):
        yield from legacy_iter_fn(run)
        return
    limits: LosslessLimits | None = getattr(run, "_lossless_limits", None)
    timeout = wait_timeout_s if wait_timeout_s is not None else ((limits.max_chunks if limits else 16) * 15.0 + 5.0)
    done: threading.Event = getattr(run, "_lossless_done")
    if not done.wait(timeout=max(0.05, timeout)):
        release_run_lossless_resources(run)
        return
    res: ChunkDeliveryResult | None = getattr(run, "_lossless_result", None)
    if res is None:
        return
    lines = res.final_turn_lines if res.final_turn_lines else res.stdout_lines[-1:]
    yield from lines


def run_with_lossless_cleanup(run: Any, init_fn: Callable[[], None]) -> None:
    """Execute Run initialization tail and guarantee slot/PGID release if any step raises."""
    try:
        init_fn()
    except BaseException:
        release_run_lossless_resources(run)
        raise


def release_run_lossless_resources(run: Any) -> None:
    """Idempotently teardown PGID (if active) and release ProcessAdmissionGuard slot on Run.close."""
    if not bool(getattr(run, "_lossless_slot_held", False)):
        return
    setattr(run, "_lossless_slot_held", False)
    guard: ProcessAdmissionGuard | None = getattr(run, "_lossless_guard", None)
    proc = getattr(run, "proc", None)
    if guard is not None:
        if isinstance(proc, subprocess.Popen):
            guard.teardown_process(proc)
        guard.release()


def send_rejection_response(handler: Any, error: Exception) -> None:
    """Send HTTP 413/429/400 for lossless/admission rejections or delegate to legacy 400 compaction."""
    if isinstance(error, AdmissionOverloadError):
        handler._send(429, {"error": {"type": "rate_limit_error", "code": "admission_overloaded", "message": str(error), "retry_after_s": error.retry_after_s}})  # noqa: SLF001
        return
    if isinstance(error, LosslessRejectionError):
        handler._send(error.http_status, error.body)  # noqa: SLF001
        return
    if isinstance(error, ClientCompactionRequired):
        send_client_compaction_required(handler, error)
