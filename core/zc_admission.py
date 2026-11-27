"""Pure Zero-Canon admission domain: validation, attestation, and wire params (zero I/O).

Leaf module: receives effort_matrix/default_efforts as arguments; imports no repo modules.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_WS_OR_CONTROL = re.compile(r"[\s\x00-\x1f\x7f]")


class ZeroCanonAdmissionError(ValueError):
    """Typed fail-closed admission error with machine code and HTTP status."""

    def __init__(self, code: str, message: str, *, http_status: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.message = message


def is_valid_server_thread_id(thread_id: str | None) -> bool:
    """Single-source syntactic validator for server-issued thread ids."""
    if not isinstance(thread_id, str) or not thread_id.strip():
        return False
    lowered = thread_id.lower()
    if lowered.startswith("th-") or lowered == "probe":
        return False
    return _WS_OR_CONTROL.search(thread_id) is None


def sanitize_model_id(raw: str | None, max_len: int = 128) -> str:
    """Strip control chars, trim whitespace, and truncate to max_len."""
    if not isinstance(raw, str):
        return ""
    return _CONTROL_CHARS.sub("", raw).strip()[:max_len]


def error_body(
    code: str, message: str, *, err_type: str = "upstream_error", model_id: str | None = None
) -> bytes:
    """Deterministic UTF-8 JSON error body; model_id is sanitized before inclusion."""
    text = message
    if model_id is not None:
        text = f"{message} (model={sanitize_model_id(model_id)})"
    payload = {"error": {"message": text, "type": err_type, "code": code}}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def decide_ingress(
    model: str | None,
    effort: str | None,
    effort_matrix: Mapping[str, tuple[str, ...]],
    default_efforts: Mapping[str, str],
) -> tuple[str, str]:
    """Normalize and validate (model, effort); never clamp unsupported effort silently."""
    norm_model = model.strip().lower() if isinstance(model, str) else ""
    allowed = effort_matrix.get(norm_model)
    if not norm_model or allowed is None:
        raise ZeroCanonAdmissionError(
            "unsupported_model", f"Unsupported Codex model: {sanitize_model_id(model)!r}", http_status=400
        )
    if effort is None or not str(effort).strip():
        return norm_model, default_efforts[norm_model]
    norm_eff = str(effort).strip().lower()
    if norm_eff not in allowed:
        raise ZeroCanonAdmissionError(
            "unsupported_model_effort",
            f"Unsupported effort {norm_eff!r} for model {norm_model!r}",
            http_status=400,
        )
    return norm_model, norm_eff


@dataclass(slots=True)
class TurnProofRecorder:
    """Mutable per-turn proof accumulator; snapshot() yields an independent copy."""

    handshake_acked: bool = False
    clean_home_verified: bool = False
    issued_thread_id: str = ""
    issued_turn_id: str = ""
    turn_epoch: int = 0
    tool_events_seen: int = 0
    inherited_state: bool = False

    def record_handshake(self, acked: bool) -> None:
        self.handshake_acked = bool(acked)

    def record_clean_home(self, verified: bool) -> None:
        self.clean_home_verified = bool(verified)

    def record_thread(self, thread_id: str, epoch: int) -> None:
        self.issued_thread_id = thread_id.strip()
        self.turn_epoch = epoch

    def record_turn(self, turn_id: str, epoch: int) -> None:
        self.issued_turn_id = turn_id.strip()
        self.turn_epoch = epoch

    def record_tool_event(self) -> None:
        self.tool_events_seen += 1

    def snapshot(self) -> TurnProofRecorder:
        return replace(self)


def _attest(detail: str) -> ZeroCanonAdmissionError:
    return ZeroCanonAdmissionError("zero_canon_attestation_failed", detail, http_status=502)


def _check_base_proof(recorder: TurnProofRecorder, require_zero_tools: bool) -> None:
    if recorder.handshake_acked is not True:
        raise _attest("handshake not acked")
    if recorder.clean_home_verified is not True:
        raise _attest("clean home not verified")
    if recorder.inherited_state is not False:
        raise _attest("inherited state detected")
    if require_zero_tools and recorder.tool_events_seen != 0:
        raise _attest(f"tool events seen: {recorder.tool_events_seen}")


def _check_identity(recorder: TurnProofRecorder, thread_id: str | None, turn_id: str | None) -> None:
    tid = (thread_id or "").strip()
    if not (
        is_valid_server_thread_id(tid)
        and is_valid_server_thread_id(recorder.issued_thread_id)
        and tid == recorder.issued_thread_id
    ):
        raise _attest("thread id missing, invalid, or mismatched")
    trid = (turn_id or "").strip()
    issued_turn = recorder.issued_turn_id.strip()
    if not trid or not issued_turn or trid != issued_turn:
        raise _attest("turn id missing or mismatched")


def _check_epoch(recorder: TurnProofRecorder, epoch: int) -> None:
    epoch_ok = isinstance(epoch, int) and not isinstance(epoch, bool) and epoch >= 1
    if not epoch_ok or recorder.turn_epoch < 1 or epoch != recorder.turn_epoch:
        raise _attest("turn epoch missing, non-positive, or mismatched")


def evaluate_admission(
    recorder: TurnProofRecorder | None,
    thread_id: str | None,
    turn_id: str | None,
    epoch: int,
    *,
    require_zero_tools: bool = True,
) -> None:
    """Enforce ALL Zero-Canon admission invariants fail-closed (502 on any failure)."""
    if recorder is None:
        raise _attest("missing turn proof recorder")
    _check_base_proof(recorder, require_zero_tools)
    _check_identity(recorder, thread_id, turn_id)
    _check_epoch(recorder, epoch)


def build_thread_params(ctx: Mapping[str, Any], zc: bool) -> dict[str, object]:
    """Pure thread/start wire params (parity with codex_driver._build_thread_params)."""
    params: dict[str, object] = {"ephemeral": True, "zero_canon": zc}
    model, cwd = ctx.get("model"), ctx.get("cwd")
    if isinstance(model, str) and model and model != "default":
        params["model"] = model
    if isinstance(cwd, str) and cwd:
        params["cwd"] = cwd
    return params


def build_turn_params(prompt: str, ctx: Mapping[str, Any], zc: bool) -> dict[str, object]:
    """Pure turn/start wire params (parity with codex_driver._build_turn_params)."""
    params: dict[str, object] = {"prompt": prompt, "zero_canon": zc}
    if isinstance(ctx.get("input"), list):
        params["input"] = ctx["input"]
    for key in ("model", "effort"):
        val = ctx.get(key)
        if isinstance(val, str) and val and val != "default":
            params[key] = val
    return params
