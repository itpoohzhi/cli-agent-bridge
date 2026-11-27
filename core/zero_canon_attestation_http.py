"""HTTP-layer Zero-Canon two-phase attestation, spoof stripping, and header emission."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast, overload

from core.codex_zero_canon_policy import (
    ATTESTATION_HEADER,
    CODEX_BACKEND_ID,
    CODEX_V2_ROUTE_ID,
    EXECUTION_KIND_EPHEMERAL,
    CodexZeroCanonPolicyError,
    ZeroCanonAttestationReceipt,
    build_attestation_receipt,
    format_attestation_header,
    validate_codex_model_effort,
)
from core.zc_admission import is_valid_server_thread_id
KIND_EPHEMERAL: Final[str] = EXECUTION_KIND_EPHEMERAL
_ATTESTATION_LOWER: Final[str] = ATTESTATION_HEADER.lower()
_POSTURE: Final[tuple[str, ...]] = (CODEX_BACKEND_ID, CODEX_V2_ROUTE_ID, "off", "read-only", "never")


class ZeroCanonHttpError(CodexZeroCanonPolicyError):
    """Fail-closed HTTP-layer Zero-Canon rejection carrying code and HTTP status."""

    def __init__(self, code: str, detail: str = "", *, http_status: int = 400) -> None:
        msg = f"{code}: {detail}" if detail and code not in detail else (detail or code)
        super().__init__(code, msg, http_status=http_status)

    @property
    def status_code(self) -> int:
        return self.http_status


@dataclass(frozen=True, slots=True)
class ZeroCanonAdmissionProof:
    """Verified pre-stream admission proof for SSE ``phase=admitted`` attestation."""

    model: str
    effort: str
    thread_id: str
    turn_id: str
    execution_kind: str = KIND_EPHEMERAL
    clean_home_verified: bool = False
    handshake_acked: bool = False
    backend: str = CODEX_BACKEND_ID
    route_id: str = CODEX_V2_ROUTE_ID
    requested_model: str = ""
    requested_effort: str = ""
    tools: str = "off"
    sandbox: str = "read-only"
    approval: str = "never"


@dataclass(frozen=True, slots=True)
class ZeroCanonCompletionProof:
    """Verified terminal completion proof for non-stream ``phase=completed`` attestation."""

    admission: ZeroCanonAdmissionProof
    terminal_status: str = ""
    tool_events_seen: int = 0
    error_code: str | None = None


def _fail_attest(detail: str) -> ZeroCanonHttpError:
    return ZeroCanonHttpError("zero_canon_attestation_failed", detail, http_status=502)


def _pick(obj: object, names: tuple[str, ...]) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        mapping = cast(Mapping[str, Any], obj)
        return next((mapping[k] for k in names if mapping.get(k) is not None), None)
    return next((v for k in names if (v := getattr(obj, k, None)) is not None), None)


def _str_from(sources: tuple[object, ...], names: tuple[str, ...], default: str = "") -> str:
    for src in sources:
        val = _pick(src, names)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return default


@overload
def strip_upstream_attestation(headers: Mapping[str, str]) -> dict[str, str]: ...
@overload
def strip_upstream_attestation(headers: Sequence[tuple[str, str]]) -> list[tuple[str, str]]: ...
def strip_upstream_attestation(
    headers: Mapping[str, str] | Sequence[tuple[str, str]],
) -> dict[str, str] | list[tuple[str, str]]:
    """Case-insensitively remove any upstream ``X-Zero-Canon-Attestation`` header."""
    if isinstance(headers, Mapping):
        return {k: v for k, v in headers.items() if str(k).strip().lower() != _ATTESTATION_LOWER}
    return [(k, v) for k, v in headers if str(k).strip().lower() != _ATTESTATION_LOWER]


def _validate_requested_identity(proof: ZeroCanonAdmissionProof, model: str, effort: str) -> None:
    if proof.requested_model and proof.requested_model.strip().lower() != model:
        raise _fail_attest("requested/actual model mismatch")
    if proof.requested_effort and proof.requested_effort.strip().lower() != effort:
        raise _fail_attest("requested/actual effort mismatch")


def _validate_admission(proof: ZeroCanonAdmissionProof) -> tuple[str, str]:
    if not (proof.execution_kind == KIND_EPHEMERAL and proof.clean_home_verified and proof.handshake_acked):
        raise _fail_attest("unverified ephemeral admission")
    tid, turn_id = proof.thread_id.strip(), proof.turn_id.strip()
    if not is_valid_server_thread_id(tid) or not turn_id:
        raise _fail_attest("missing server-issued threadId/turnId")
    if (proof.backend, proof.route_id, proof.tools, proof.sandbox, proof.approval) != _POSTURE:
        raise _fail_attest("invalid Zero-Canon execution posture")
    model, effort = validate_codex_model_effort(proof.model, proof.effort, default_if_missing=False)
    _validate_requested_identity(proof, model, effort)
    return model, effort


def _admission_from_mapping(data: Mapping[str, Any]) -> ZeroCanonAdmissionProof:
    existing = data.get("admission")
    if isinstance(existing, ZeroCanonAdmissionProof):
        return existing
    srcs: tuple[object, ...] = (data,)
    return ZeroCanonAdmissionProof(
        model=_str_from(srcs, ("model",)), effort=_str_from(srcs, ("effort",)),
        thread_id=_str_from(srcs, ("thread_id", "threadId")), turn_id=_str_from(srcs, ("turn_id", "turnId")),
        execution_kind=_str_from(srcs, ("execution_kind",), KIND_EPHEMERAL),
        clean_home_verified=bool(data.get("clean_home_verified", False)),
        handshake_acked=bool(data.get("handshake_acked", False)),
        backend=_str_from(srcs, ("backend",), CODEX_BACKEND_ID),
        route_id=_str_from(srcs, ("route_id",), CODEX_V2_ROUTE_ID),
        requested_model=_str_from(srcs, ("requested_model",)), requested_effort=_str_from(srcs, ("requested_effort",)),
        tools=_str_from(srcs, ("tools",), "off"), sandbox=_str_from(srcs, ("sandbox",), "read-only"),
        approval=_str_from(srcs, ("approval",), "never"),
    )


def _attest_admission(proof: ZeroCanonAdmissionProof, phase: str | None) -> str:
    if (phase or "admitted") != "admitted":
        raise _fail_attest("admission DTO cannot attest completed")
    model, effort = _validate_admission(proof)
    return format_attestation_header(model, effort, phase="admitted", backend=proof.backend)


def _attest_completion(proof: ZeroCanonCompletionProof, phase: str | None) -> str:
    if (phase or "completed") != "completed":
        raise _fail_attest("completion DTO requires phase=completed")
    model, effort = _validate_admission(proof.admission)
    if proof.terminal_status != "completed" or proof.tool_events_seen != 0 or proof.error_code:
        raise _fail_attest("incomplete or errored turn")
    return format_attestation_header(model, effort, phase="completed", backend=proof.admission.backend)


def _attest_mapping(proof: Mapping[str, Any], phase: str | None) -> str:
    default_phase = "completed" if "terminal_status" in proof else "admitted"
    resolved = phase or _str_from((proof,), ("phase",), default_phase)
    adm = _admission_from_mapping(proof)
    if resolved == "completed":
        err = proof.get("error_code", proof.get("error"))
        comp = ZeroCanonCompletionProof(
            adm, _str_from((proof,), ("terminal_status",)), int(proof.get("tool_events_seen", 0)), str(err) if err else None
        )
        return _attest_completion(comp, "completed")
    return _attest_admission(adm, resolved)


def _attest_receipt(proof: ZeroCanonAttestationReceipt, phase: str | None) -> str:
    resolved = proof.phase if phase is None else phase
    if resolved != proof.phase:
        raise _fail_attest("receipt phase mismatch")
    _ = build_attestation_receipt(proof.requested, proof.actual, phase=resolved)
    adm = ZeroCanonAdmissionProof(
        proof.actual.model, proof.actual.effort, proof.actual.thread_id, proof.actual.turn_id,
        clean_home_verified=True, handshake_acked=True, backend=proof.actual.backend,
        route_id=proof.actual.route_id, requested_model=proof.requested.model, requested_effort=proof.requested.effort,
    )
    if resolved == "completed":
        return _attest_completion(ZeroCanonCompletionProof(adm, proof.actual.terminal_status, proof.actual.tool_events_seen), "completed")
    return _attest_admission(adm, "admitted")


def build_attestation_header(
    proof: ZeroCanonAdmissionProof | ZeroCanonCompletionProof | ZeroCanonAttestationReceipt | Mapping[str, Any],
    *,
    phase: str | None = None,
) -> str:
    """Build trusted ``X-Zero-Canon-Attestation`` value strictly from confirmed admission/completion DTO."""
    if isinstance(proof, Mapping):
        return _attest_mapping(proof, phase)
    if isinstance(proof, ZeroCanonAttestationReceipt):
        return _attest_receipt(proof, phase)
    if isinstance(proof, ZeroCanonAdmissionProof):
        return _attest_admission(proof, phase)
    if isinstance(proof, ZeroCanonCompletionProof):
        return _attest_completion(proof, phase)
    raise _fail_attest(f"unsupported proof type: {type(proof).__name__}")


def emit_passthrough_headers(
    handler: Any, headers: Sequence[tuple[str, str]], blocked: frozenset[str],
    extra_headers: Sequence[tuple[str, str]], allow_fn: Callable[[str, frozenset[str]], bool],
) -> None:
    """Emit passthrough headers while unconditionally stripping spoofed upstream attestation."""
    for key, value in strip_upstream_attestation(headers):
        if allow_fn(key, blocked):
            handler.send_header(key, value)
    for key, value in strip_upstream_attestation(extra_headers):
        handler.send_header(key, value)


def emit_turn_headers(
    handler: Any, managed_turn: Any, trace_headers: Sequence[tuple[str, str]],
    pruned: tuple[str, str | None], *, attestation: tuple[Any, str] | None = None,
) -> None:
    """Emit trusted turn headers and optional verified ``X-Zero-Canon-Attestation``, then end headers."""
    try:
        if managed_turn is not None:
            handler.send_header("X-Turn-Id", managed_turn.turn_id)
        for key, value in strip_upstream_attestation(trace_headers):
            handler.send_header(key, value)
        if pruned[1]:
            handler.send_header(pruned[0], pruned[1])
        if attestation is not None and attestation[0] is not None:
            handler.send_header(ATTESTATION_HEADER, build_attestation_header(attestation[0], phase=attestation[1]))
        handler.end_headers()
    finally:
        for attr in ("_zero_canon_admission", "_zero_canon_completion"):
            if hasattr(handler, attr):
                setattr(handler, attr, None)
