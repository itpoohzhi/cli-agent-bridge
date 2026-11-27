"""Decoupled lossless kill-switch and opt-in 413 refuse policy for muse-bridge (context_pruner untouched)."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = str(Path(__file__).resolve().parents[3])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.lossless_contracts import (  # noqa: E402
    RefuseStatusMode,
    build_loss_receipt,
    resolve_lossless_limits,
)

from .context_pruner import PruneResult  # noqa: E402


@dataclass(frozen=True)
class MusePromptDecision:
    """Outcome of muse-bridge context evaluation before launching Muse CLI."""

    ok: bool
    prompt: str
    est_after: int
    prune_result: PruneResult
    http_status: int = 200
    error_body: dict[str, object] | None = None
    log_reason: str = ""


def read_muse_policy_flags(env: Mapping[str, str] | None = None) -> tuple[bool, RefuseStatusMode, str]:
    """Read independent MUSE_BRIDGE_LOSSLESS_ENABLED and MUSE_BRIDGE_REFUSE_STATUS_MODE flags."""
    source = os.environ if env is None else env
    limits = resolve_lossless_limits(source)
    return limits.muse_lossless_enabled, limits.muse_refuse_status_mode, limits.digest_mode


def allow_reactive_prune_retry(env: Mapping[str, str] | None = None) -> bool:
    """Forbid reactive 50% context prune-retry whenever lossless kill-switch is active."""
    lossless_enabled, _, _ = read_muse_policy_flags(env)
    return not lossless_enabled


def _build_refused_response(
    *,
    detail: str,
    err_msg: str,
    prompt_raw: bytes,
    mode: RefuseStatusMode,
    digest_mode: str,
    redact_fn: Callable[[str], str],
) -> tuple[int, dict[str, object]]:
    receipt = build_loss_receipt(
        reason="muse_context_exceeds_limit",
        http_status=413 if mode is RefuseStatusMode.FAIL_CLOSED_413 else 502,
        prompt_raw=prompt_raw,
        delivered_bytes=0,
        chunk_count=1,
        chunk_index=0,
        digest_mode=digest_mode,
    )
    if mode is RefuseStatusMode.FAIL_CLOSED_413:
        return (
            413,
            {
                "error": {
                    "message": redact_fn(err_msg),
                    "detail": redact_fn(detail)[:500],
                    "type": "invalid_request_error",
                    "code": "prompt_too_large",
                    "x_bridge_loss": receipt.to_wire_dict(),
                }
            },
        )
    return (
        502,
        {
            "error": {
                "message": redact_fn(err_msg),
                "detail": redact_fn(detail)[:500],
                "type": "proxy_error",
                "code": 502,
            }
        },
    )


def evaluate_muse_prompt_policy(
    raw_messages: list[Any],
    *,
    limit: int,
    target: int,
    tools: Any,
    tool_choice: Any,
    raw_tools: Any,
    prune_fn: Callable[..., PruneResult],
    assemble_fn: Callable[..., tuple[Any, Any, str]],
    estimate_fn: Callable[[str], int],
    redact_fn: Callable[[str], str],
    env: Mapping[str, str] | None = None,
) -> MusePromptDecision:
    """Evaluate muse prompt with decoupled lossless kill-switch and opt-in 413 status mapping."""
    lossless_enabled, refuse_mode, digest_mode = read_muse_policy_flags(env)

    if lossless_enabled:
        _, _, full_prompt = assemble_fn(
            raw_messages, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools
        )
        est_before = estimate_fn(full_prompt)
        total = len(raw_messages)
        if est_before <= limit:
            res = PruneResult(
                status="ok",
                messages=list(raw_messages),
                prompt=full_prompt,
                est_before=est_before,
                est_after=est_before,
                msgs_total=total,
                msgs_kept=total,
                msgs_dropped=0,
                mandatory_est=est_before,
                overhead_est=0,
            )
            return MusePromptDecision(ok=True, prompt=full_prompt, est_after=est_before, prune_result=res)

        res = PruneResult(
            status="refused",
            messages=[],
            prompt="",
            est_before=est_before,
            est_after=est_before,
            msgs_total=total,
            msgs_kept=0,
            msgs_dropped=0,
            mandatory_est=est_before,
            overhead_est=0,
        )
        detail = f"lossless context exceeds budget (est_tokens={est_before}, limit={limit})"
        err_msg = f"muse turn refused in lossless mode: {detail}"
        code, body = _build_refused_response(
            detail=detail,
            err_msg=err_msg,
            prompt_raw=full_prompt.encode("utf-8"),
            mode=refuse_mode,
            digest_mode=digest_mode,
            redact_fn=redact_fn,
        )
        return MusePromptDecision(
            ok=False,
            prompt="",
            est_after=est_before,
            prune_result=res,
            http_status=code,
            error_body=body,
            log_reason="refused_lossless",
        )

    prune_res = prune_fn(
        raw_messages, limit=limit, target=target, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools
    )
    if prune_res.status == "refused":
        detail = f"mandatory context exceeds budget (est_tokens={prune_res.mandatory_est}, limit={limit})"
        err_msg = f"muse turn failed (rc=1, state=terminal_failed): {detail}"
        code, body = _build_refused_response(
            detail=detail,
            err_msg=err_msg,
            prompt_raw=prune_res.prompt.encode("utf-8"),
            mode=refuse_mode,
            digest_mode=digest_mode,
            redact_fn=redact_fn,
        )
        return MusePromptDecision(
            ok=False,
            prompt="",
            est_after=prune_res.est_after,
            prune_result=prune_res,
            http_status=code,
            error_body=body,
            log_reason="refused_mandatory",
        )
    return MusePromptDecision(
        ok=True,
        prompt=prune_res.prompt,
        est_after=prune_res.est_after,
        prune_result=prune_res,
        log_reason="proactive_prune" if prune_res.status == "pruned" else "",
    )
