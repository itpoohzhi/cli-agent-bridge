"""Atomic non-stream HTTP response framing barrier for Zero-Canon attestation (F-001).

Validates the Zero-Canon completion proof strictly BEFORE ``send_response(200)`` so a
missing/invalid proof can never yield a fail-open HTTP 200 or ``IncompleteRead``.
Replaces the legacy framing block at server.py:7348-7353. Imports no server/adapters/
process_pool modules; socket I/O errors during the 200 commit are never swallowed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from core.subbridge_zero_canon import is_zero_canon_profile
from core.zc_admission import ZeroCanonAdmissionError, error_body, is_valid_server_thread_id
from core.zero_canon_attestation_http import build_attestation_header, emit_turn_headers

_JSON_CONTENT_TYPE = "application/json; charset=utf-8"


def _clear_proofs(handler: Any) -> None:
    """Drop any cached admission/completion proofs from the handler (if present)."""
    for attr in ("_zero_canon_admission", "_zero_canon_completion"):
        if hasattr(handler, attr):
            setattr(handler, attr, None)


def _prevalidate(handler: Any, out: Mapping[str, Any]) -> Any:
    """Fail-closed pre-commit validation; raises before any 200 status is sent."""
    if out.get("tool_calls"):
        raise ZeroCanonAdmissionError(
            "zero_canon_attestation_failed", "zero_canon_tool_calls_forbidden", http_status=502
        )
    proof = out.get("zero_canon_completion") or getattr(handler, "_zero_canon_completion", None)
    if proof is None:
        raise ZeroCanonAdmissionError(
            "zero_canon_attestation_failed", "missing_completion_proof", http_status=502
        )
    admission = getattr(proof, "admission", proof)
    thread_id = getattr(admission, "thread_id", None)
    if thread_id is not None and not is_valid_server_thread_id(thread_id):
        raise ZeroCanonAdmissionError(
            "zero_canon_attestation_failed", "invalid server-issued thread id", http_status=502
        )
    # Pure deterministic pre-validation: if this succeeds, the post-commit rebuild
    # inside emit_turn_headers cannot fail for policy reasons.
    _ = build_attestation_header(proof, phase="completed")
    return proof


def _frame(handler: Any, status: int, length: int) -> None:
    """Set status/telemetry, then send the status line and JSON framing headers."""
    handler._response_status = status
    handler._telemetry_note(length, first_byte=True)
    handler.send_response(status)
    handler.send_header("Content-Type", _JSON_CONTENT_TYPE)
    handler.send_header("Content-Length", str(length))


def _fail(
    handler: Any,
    trace_headers: Sequence[tuple[str, str]],
    pruned: tuple[str, str | None],
    body: bytes,
    status: int,
) -> bool:
    """Emit a clean deterministic error response with exact Content-Length."""
    _clear_proofs(handler)
    _frame(handler, status, len(body))
    emit_turn_headers(
        handler, getattr(handler, "_active_managed_turn", None), trace_headers, pruned, attestation=None
    )
    handler.wfile.write(body)
    return False


def emit_nonstream_headers(
    handler: Any,
    total: int,
    trace_headers: Sequence[tuple[str, str]],
    pruned: tuple[str, str | None],
    out: Mapping[str, Any],
) -> bool:
    """Frame the non-stream response; True => caller writes the 200 body, False => done.

    Zero-Canon is derived explicitly from the review profile (never from proof presence).
    Attestation is validated before ``send_response(200)``; ValueError-family policy
    failures yield a deterministic 502, unexpected internal bugs yield a 500, and
    socket errors during the 200 commit propagate to the caller untouched.
    """
    zero_canon = is_zero_canon_profile(getattr(handler, "_review_profile", None))
    if not zero_canon:
        _frame(handler, 200, total)
        emit_turn_headers(
            handler, getattr(handler, "_active_managed_turn", None), trace_headers, pruned, attestation=None
        )
        return True
    try:
        proof = _prevalidate(handler, out)
    except ValueError as exc:
        body = error_body(
            "zero_canon_attestation_failed",
            str(exc) or "zero_canon_attestation_failed",
            err_type="upstream_error",
        )
        return _fail(handler, trace_headers, pruned, body, 502)
    except Exception:
        body = error_body("internal_error", "internal_attestation_error", err_type="server_error")
        return _fail(handler, trace_headers, pruned, body, 500)
    # Commit 200 OUTSIDE the pre-commit try/except: socket I/O errors are not swallowed.
    _frame(handler, 200, total)
    emit_turn_headers(
        handler,
        getattr(handler, "_active_managed_turn", None),
        trace_headers,
        pruned,
        attestation=(proof, "completed"),
    )
    return True
