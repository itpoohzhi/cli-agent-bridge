"""HTTP-layer Zero-Canon profile parsing, provider filtering, spoof stripping, and two-phase attestation."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeVar, cast, overload
from urllib.parse import urlparse

from core.codex_zero_canon_policy import (
    ATTESTATION_HEADER,
    CODEX_BACKEND_ID,
    CODEX_EFFORT_MATRIX,
    CODEX_V2_ROUTE_ID,
    EXECUTION_KIND_EPHEMERAL,
    CodexZeroCanonPolicyError,
    ZeroCanonAttestationReceipt,
    build_attestation_receipt,
    format_attestation_header,
    validate_codex_model_effort,
)
from core.subbridge_zero_canon import (
    EXTERNAL_TRUST_PROFILE,
    REVIEW_PROFILE_HEADER,
    STANDARD_PROFILE,
    should_forward_review_profile,
)
from core.zero_canon_fs import read_gigarc_bool, resolve_hub_dynamic_config

CODEX_V2_FLAG: Final[str] = "BRIDGE_CODEX_APP_SERVER_V2_ENABLED"
ZERO_CANON_HEADER_VALUE: Final[str] = "Zero-Canon"
KIND_EPHEMERAL: Final[str] = EXECUTION_KIND_EPHEMERAL
_ATTESTATION_LOWER: Final[str] = ATTESTATION_HEADER.lower()
_REVIEW_PROFILE_LOWER: Final[str] = REVIEW_PROFILE_HEADER.lower()
_CODEX_IDS: Final[frozenset[str]] = frozenset(
    {"codex", "codex-app-server", "codex-app-server-v2", "codex_app_server", "codex_app_server_v2"}
)
_DENIED_BACKENDS: Final[frozenset[str]] = frozenset({"openai-key-3", "openai-key-2", "codex-passthrough", "codex-lb"})
_DENIED_PREFIXES: Final[tuple[str, ...]] = ("openai-key-", "sg-openai", "sg-")
_LEGACY_CONTRACTS: Final[tuple[str, ...]] = (
    "codex.app-server.v1@", "codex.app-server.legacy@", "codex.passthrough.", "openai.chat-completions.",
)
_LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "localhost", "::1"})
_POSTURE: Final[tuple[str, ...]] = (CODEX_BACKEND_ID, CODEX_V2_ROUTE_ID, "off", "read-only", "never")
_T = TypeVar("_T")


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


@dataclass(frozen=True, slots=True)
class _ProviderMeta:
    backend: str
    route_id: str
    base_url: str
    kind: str
    trust_profile: str
    contract: str
    attested: bool | None


def _fail_attest(detail: str) -> ZeroCanonHttpError:
    return ZeroCanonHttpError("zero_canon_attestation_failed", detail, http_status=502)


def is_codex_app_server_v2_enabled(
    environ: Mapping[str, str] | None = None, *, config_path: Path | None = None
) -> bool:
    """Read ``BRIDGE_CODEX_APP_SERVER_V2_ENABLED`` fail-closed (default ``False``)."""
    cfg = resolve_hub_dynamic_config(environ) if config_path is None else config_path
    return read_gigarc_bool(CODEX_V2_FLAG, cfg, environ=environ, default=False)


def parse_strict_review_profile(raw: str | None) -> str:
    """Strictly parse ``X-Review-Profile``; reject typos like ``Zero_Canon`` with HTTP 400."""
    if raw is None:
        return STANDARD_PROFILE
    if not isinstance(raw, str):
        raise ZeroCanonHttpError("invalid_review_profile", f"non-string profile: {type(raw).__name__}", http_status=400)
    low = raw.strip().lower()
    if low in ("", STANDARD_PROFILE):
        return STANDARD_PROFILE
    if low == "zero-canon":
        return ZERO_CANON_HEADER_VALUE
    raise ZeroCanonHttpError("invalid_review_profile", f"unsupported X-Review-Profile: {raw!r}", http_status=400)


def parse_review_profile_headers(headers: Any) -> str:
    """Extract and strictly validate ``X-Review-Profile`` from HTTP headers."""
    get_all = getattr(headers, "get_all", None)
    if callable(get_all):
        values = [str(v) for v in cast(Iterable[object], get_all(REVIEW_PROFILE_HEADER) or ())]
    elif hasattr(headers, "items"):
        items = cast(Iterable[tuple[Any, Any]], headers.items())
        values = [str(v) for k, v in items if str(k).lower() == _REVIEW_PROFILE_LOWER]
    else:
        return STANDARD_PROFILE
    parsed = {parse_strict_review_profile(val) for val in values}
    if len(parsed) > 1:
        raise ZeroCanonHttpError("invalid_review_profile", "conflicting X-Review-Profile headers", http_status=400)
    return next(iter(parsed), STANDARD_PROFILE)


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


def _bool_from(sources: tuple[object, ...], key: str) -> bool | None:
    for src in sources:
        val = _pick(src, (key,))
        if isinstance(val, bool):
            return val
    return None


def _extract_base_url(sources: tuple[object, ...]) -> str:
    direct = _str_from(sources, ("base_url", "url"))
    if direct:
        return direct
    nested: list[object] = []
    for src in sources:
        tr = _pick(src, ("transport", "bridge"))
        if tr is not None:
            nested.append(_pick(tr, ("bridge",)) or tr)
    return _str_from(tuple(nested), ("base_url", "url"))


def _provider_meta(item: object, configs: Mapping[str, Mapping[str, Any]] | None) -> _ProviderMeta:
    if isinstance(item, str):
        norm = item.strip().lower()
        cfg = (configs.get(item) or configs.get(norm)) if configs else None
        srcs: tuple[object, ...] = (cfg,)
        return _ProviderMeta(
            norm, norm, _extract_base_url(srcs), _str_from(srcs, ("backend_kind", "kind")).lower(),
            _str_from(srcs, ("trust_profile",)).lower(), _str_from(srcs, ("upstream_contract",)).lower(),
            _bool_from(srcs, "zero_canon_attested"),
        )
    backend = _str_from((item,), ("backend", "provider_id", "id", "route_id")).lower()
    route_id = _str_from((item,), ("route_id", "id", "backend", "provider_id"), backend).lower()
    cfg_entry = (configs.get(backend) or configs.get(route_id)) if configs else None
    item_cfg = _pick(item, ("config",))
    srcs = (item, item_cfg if isinstance(item_cfg, Mapping) else cfg_entry)
    return _ProviderMeta(
        backend, route_id, _extract_base_url(srcs), _str_from(srcs, ("backend_kind", "kind")).lower(),
        _str_from(srcs, ("trust_profile",)).lower(), _str_from(srcs, ("upstream_contract",)).lower(),
        _bool_from(srcs, "zero_canon_attested"),
    )


def _is_codex_meta(meta: _ProviderMeta) -> bool:
    return meta.backend in _CODEX_IDS or meta.route_id in _CODEX_IDS


def _url_allowed(url: str, trust_profile: str) -> bool:
    if not url:
        return trust_profile != EXTERNAL_TRUST_PROFILE
    parsed = urlparse(url)
    if "/sg-" in parsed.path.lower() or parsed.hostname not in _LOOPBACK_HOSTS or parsed.port == 2455:
        return False
    return should_forward_review_profile(parsed.path, trust_profile)


def _is_provider_allowed(meta: _ProviderMeta, v2_enabled: bool) -> bool:
    if any(ident in _DENIED_BACKENDS or ident.startswith(_DENIED_PREFIXES) for ident in (meta.backend, meta.route_id) if ident):
        return False
    if meta.attested is False or meta.trust_profile == EXTERNAL_TRUST_PROFILE:
        return False
    if any(meta.contract.startswith(p) for p in _LEGACY_CONTRACTS) or not _url_allowed(meta.base_url, meta.trust_profile):
        return False
    return (v2_enabled and meta.kind != "passthrough") if _is_codex_meta(meta) else True


def filter_zero_canon_providers(
    providers: Sequence[_T],
    review_profile: str | None = ZERO_CANON_HEADER_VALUE,
    *,
    codex_v2_enabled: bool | None = None,
    provider_configs: Mapping[str, Mapping[str, Any]] | None = None,
    model_id: str | None = None,
) -> list[_T]:
    """Filter routes/providers for strict Zero-Canon; fail closed with 503 for Codex when V2 is off."""
    if parse_strict_review_profile(review_profile) != ZERO_CANON_HEADER_VALUE:
        return list(providers)
    v2_on = is_codex_app_server_v2_enabled() if codex_v2_enabled is None else bool(codex_v2_enabled)
    kept: list[_T] = []
    saw_codex = bool(model_id and model_id.strip().lower() in CODEX_EFFORT_MATRIX)
    for item in providers:
        meta = _provider_meta(item, provider_configs)
        saw_codex = saw_codex or _is_codex_meta(meta)
        if _is_provider_allowed(meta, v2_on):
            kept.append(item)
    if not kept and saw_codex and not v2_on:
        raise ZeroCanonHttpError("zero_canon_unsupported_by_driver", "Codex Zero-Canon requires V2 enabled", http_status=503)
    return kept


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


def _validate_admission(proof: ZeroCanonAdmissionProof) -> tuple[str, str]:
    if not (proof.execution_kind == KIND_EPHEMERAL and proof.clean_home_verified and proof.handshake_acked):
        raise _fail_attest("unverified ephemeral admission")
    tid, turn_id = proof.thread_id.strip(), proof.turn_id.strip()
    if not tid or tid.lower().startswith("th-") or not turn_id:
        raise _fail_attest("missing server-issued threadId/turnId")
    if (proof.backend, proof.route_id, proof.tools, proof.sandbox, proof.approval) != _POSTURE:
        raise _fail_attest("invalid Zero-Canon execution posture")
    model, effort = validate_codex_model_effort(proof.model, proof.effort, default_if_missing=False)
    if proof.requested_model and proof.requested_model.strip().lower() != model:
        raise _fail_attest("requested/actual model mismatch")
    if proof.requested_effort and proof.requested_effort.strip().lower() != effort:
        raise _fail_attest("requested/actual effort mismatch")
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
        return build_attestation_header(ZeroCanonCompletionProof(adm, proof.actual.terminal_status, proof.actual.tool_events_seen), phase="completed")
    return build_attestation_header(adm, phase="admitted")


def build_attestation_header(
    proof: ZeroCanonAdmissionProof | ZeroCanonCompletionProof | ZeroCanonAttestationReceipt | Mapping[str, Any],
    *,
    phase: str | None = None,
) -> str:
    """Build trusted ``X-Zero-Canon-Attestation`` value strictly from confirmed admission/completion DTO."""
    if isinstance(proof, Mapping):
        resolved = phase or _str_from((proof,), ("phase",), "completed" if "terminal_status" in proof else "admitted")
        adm = _admission_from_mapping(proof)
        if resolved == "completed":
            err = proof.get("error_code", proof.get("error"))
            return build_attestation_header(ZeroCanonCompletionProof(adm, _str_from((proof,), ("terminal_status",)), int(proof.get("tool_events_seen", 0)), str(err) if err else None), phase="completed")
        return build_attestation_header(adm, phase=resolved)
    if isinstance(proof, ZeroCanonAttestationReceipt):
        return _attest_receipt(proof, phase)
    if isinstance(proof, ZeroCanonAdmissionProof):
        if (phase or "admitted") != "admitted":
            raise _fail_attest("admission DTO cannot attest completed")
        model, effort = _validate_admission(proof)
        return format_attestation_header(model, effort, phase="admitted", backend=proof.backend)
    if isinstance(proof, ZeroCanonCompletionProof):
        if (phase or "completed") != "completed":
            raise _fail_attest("completion DTO requires phase=completed")
        model, effort = _validate_admission(proof.admission)
        if proof.terminal_status != "completed" or proof.tool_events_seen != 0 or proof.error_code:
            raise _fail_attest("incomplete or errored turn")
        return format_attestation_header(model, effort, phase="completed", backend=proof.admission.backend)
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
