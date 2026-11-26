"""HTTP-layer Zero-Canon profile parsing, provider filtering, spoof stripping, and two-phase attestation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeVar, cast
from urllib.parse import ParseResult, unquote, urlparse

from core.codex_zero_canon_policy import CODEX_EFFORT_MATRIX
from core.subbridge_zero_canon import (
    EXTERNAL_TRUST_PROFILE,
    REVIEW_PROFILE_HEADER,
    STANDARD_PROFILE,
    should_forward_review_profile,
)
from core.zero_canon_attestation_http import (
    KIND_EPHEMERAL as KIND_EPHEMERAL,
)
from core.zero_canon_attestation_http import (
    ZeroCanonAdmissionProof as ZeroCanonAdmissionProof,
)
from core.zero_canon_attestation_http import (
    ZeroCanonCompletionProof as ZeroCanonCompletionProof,
)
from core.zero_canon_attestation_http import (
    ZeroCanonHttpError as ZeroCanonHttpError,
)
from core.zero_canon_attestation_http import (
    _pick,
    _str_from,
)
from core.zero_canon_attestation_http import (
    build_attestation_header as build_attestation_header,
)
from core.zero_canon_attestation_http import (
    emit_passthrough_headers as emit_passthrough_headers,
)
from core.zero_canon_attestation_http import (
    emit_turn_headers as emit_turn_headers,
)
from core.zero_canon_attestation_http import (
    strip_upstream_attestation as strip_upstream_attestation,
)
from core.zero_canon_fs import read_gigarc_bool, resolve_hub_dynamic_config

CODEX_V2_FLAG: Final[str] = "BRIDGE_CODEX_APP_SERVER_V2_ENABLED"
ZERO_CANON_HEADER_VALUE: Final[str] = "Zero-Canon"
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
_GEOROUTER_PORT: Final[int] = 10830
_STATELESS_GEOROUTER_SEGMENTS: Final[frozenset[str]] = frozenset({"neuralwatt", "go"})
_SG_QWEN_PATHS: Final[frozenset[str]] = frozenset(("/sg-qwen", "/sg-qwen/", "/sg-qwen/v1"))
_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class _ProviderMeta:
    backend: str
    route_id: str
    base_url: str
    kind: str
    trust_profile: str
    contract: str
    attested: bool | None


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


def _is_stateless_georouter_url(parsed: ParseResult, decoded: str, port: int | None) -> bool:
    """Exact allowlist of stateless georouter gateways on :10830 (DashScope SG / neuralwatt / go)."""
    if parsed.scheme != "http" or port != _GEOROUTER_PORT:
        return False
    if parsed.params or parsed.query or parsed.fragment:
        return False
    if parsed.path in _SG_QWEN_PATHS:
        return True
    if "/sg-" in decoded.lower():
        return False
    segments = (*decoded.split("/"), *parsed.path.split("/"))
    if any(seg in (".", "..") for seg in segments):
        return False
    first_seg = parsed.path.strip().strip("/").split("/", 1)[0].lower()
    return first_seg in _STATELESS_GEOROUTER_SEGMENTS


def _url_allowed(url: str, trust_profile: str) -> bool:
    if trust_profile == EXTERNAL_TRUST_PROFILE:
        return False
    if not url:
        return True
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError:
        return False
    if parsed.hostname not in _LOOPBACK_HOSTS or parsed.username is not None or parsed.password is not None:
        return False
    decoded = unquote(parsed.path)
    if port == 2455:
        return False
    if _is_stateless_georouter_url(parsed, decoded, port):
        return True
    if "/sg-" in decoded.lower():
        return False
    return should_forward_review_profile(parsed.path, trust_profile)


def _is_denied_ident(meta: _ProviderMeta) -> bool:
    for ident in (meta.backend, meta.route_id):
        if ident and (ident in _DENIED_BACKENDS or ident.startswith(_DENIED_PREFIXES)):
            return True
    return False


def _is_provider_allowed(meta: _ProviderMeta, v2_enabled: bool) -> bool:
    if _is_denied_ident(meta) or meta.attested is False or meta.trust_profile == EXTERNAL_TRUST_PROFILE:
        return False
    if meta.contract.startswith(_LEGACY_CONTRACTS) or not _url_allowed(meta.base_url, meta.trust_profile):
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
