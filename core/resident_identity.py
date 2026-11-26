from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast

from core.chat_key import SOURCES_SESSION_ID, resolve_chat_key
from core.resident_canonical import _fail_if
from core.subbridge_zero_canon import is_zero_canon_profile
from core.zero_canon_fs import read_gigarc_bool, resolve_hub_dynamic_config

_FALLBACK_SECRET = b"resident-fallback-secret-v1"
CODEX_PCK_V1_FLAG = "BRIDGE_CODEX_PCK_V1_ENABLED"
_PCK_MAX_LEN = 512


class ResidentAuthError(Exception):
    def __init__(self, http_status: int = 401, code: str = "auth_required", message: str = "") -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code


class ResidentRequestError(Exception):
    def __init__(self, http_status: int = 400, code: str = "invalid_request", message: str = "") -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code


def validate_hmac_secret(secret: bytes) -> bytes:
    _fail_if(any((not isinstance(secret, bytes), len(secret) < 16)), ValueError("invalid_hmac_secret"))
    return secret


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentityInputs:
    request: Mapping[str, object] = field(repr=False)
    headers: Mapping[str, str] | None = field(repr=False)
    extra: Mapping[str, object] | None = field(repr=False)
    secret: bytes = field(repr=False, compare=False)
    trusted_principal_hash: Any = ""
    scope: Any = ""
    subagent_id: Any = ""
    review_profile: str = "standard"
    protocol: str = ""
    require_auth: bool = False
    force_ephemeral: bool = False
    turn_id: str = ""

    def __post_init__(self) -> None:
        validate_hmac_secret(self.secret)

    def __repr__(self) -> str:
        return (
            f"IdentityInputs(trusted_principal_hash={self.trusted_principal_hash!r}, "
            f"scope={self.scope!r}, subagent_id={self.subagent_id!r}, "
            f"review_profile={self.review_profile!r}, protocol={self.protocol!r}, "
            f"require_auth={self.require_auth!r}, force_ephemeral={self.force_ephemeral!r}, turn_id={self.turn_id!r})"
        )


@dataclass(frozen=True, slots=True)
class ResidentIdentity:
    principal_hash: str
    conversation_id: str
    ephemeral: bool
    cache_key: str = field(repr=False)
    turn_id: str
    scope: str
    subagent_id: str
    scoped_session_id: str
    degradation_reason: str = ""


def _valid_token(val: object) -> bool:
    return all((isinstance(val, str), bool(val), len(cast(str, val)) <= 4096, all(32 <= ord(c) != 127 and not 0xD800 <= ord(c) <= 0xDFFF for c in cast(str, val)))) if isinstance(val, str) else False


def _valid_optional_str(val: object) -> bool:
    return all((isinstance(val, str), any((not val, _valid_token(val)))))


def _scoped_id(inputs: IdentityInputs, principal: str, chat_id: str) -> str:
    payload = json.dumps([inputs.scope, principal, inputs.subagent_id, chat_id], separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hmac.new(inputs.secret, payload, hashlib.sha256).hexdigest()[:32]


def _ephemeral_identity(inputs: IdentityInputs, principal: str, conversation_id: str, reason: str) -> ResidentIdentity:
    return ResidentIdentity(principal, conversation_id, True, "", inputs.turn_id, inputs.scope, inputs.subagent_id, uuid.uuid4().hex, reason)


def _validate_principal(inputs: IdentityInputs) -> str:
    _fail_if(not all(_valid_optional_str(v) for v in (inputs.scope, inputs.subagent_id)), ResidentRequestError(400, "invalid_request"))
    raw = inputs.trusted_principal_hash
    absent = raw in (None, "")
    principal_err: Exception = ResidentAuthError(401, "auth_required") if bool(inputs.require_auth) else ResidentRequestError(400, "invalid_principal_hash")
    _fail_if(all((not absent, not _valid_token(raw))), principal_err)
    principal = raw if isinstance(raw, str) else ""
    _fail_if(all((not principal, bool(inputs.require_auth))), ResidentAuthError(401, "auth_required"))
    return principal


def derive_pck_digest(secret: bytes, key: str) -> str:
    """Короткий HMAC-дайджест `prompt_cache_key` для логов (сырой ключ не раскрывается)."""
    return hmac.new(secret, b"pck_v1_log\0" + key.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def is_pck_v1_enabled() -> bool:
    """Kill-switch opt-in аффинити по `prompt_cache_key` (`dynamic_config.json > env > False`)."""
    return read_gigarc_bool(CODEX_PCK_V1_FLAG, resolve_hub_dynamic_config(None), default=False)


def _pck_scoped_id(inputs: IdentityInputs, principal: str, raw_pck: str) -> str:
    parts = ["pck_v1", inputs.scope, principal, inputs.subagent_id, inputs.review_profile, raw_pck]
    payload = json.dumps(parts, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hmac.new(inputs.secret, payload, hashlib.sha256).hexdigest()[:32]


def _no_chat_identity(inputs: IdentityInputs, principal: str) -> ResidentIdentity:
    """Идентичность без валидного chat_id: эфемерная, либо `pck_v1` (opt-in, только с principal)."""
    raw_pck = inputs.request.get("prompt_cache_key")
    pck_ok = isinstance(raw_pck, str) and _valid_token(raw_pck) and len(raw_pck) <= _PCK_MAX_LEN
    if not (pck_ok and is_pck_v1_enabled()):
        return _ephemeral_identity(inputs, principal, "", "missing_or_invalid_chat_id")
    pck = cast(str, raw_pck)
    return ResidentIdentity(
        principal, "", False, derive_pck_digest(inputs.secret, pck), inputs.turn_id,
        inputs.scope, inputs.subagent_id, _pck_scoped_id(inputs, principal, pck), "pck_v1_affinity",
    )


def resolve_resident_identity(inputs: IdentityInputs) -> ResidentIdentity:
    principal = _validate_principal(inputs)
    if not principal:
        return _ephemeral_identity(inputs, "", "", "unauthenticated_ephemeral")
    chat = resolve_chat_key(
        inputs.request,
        headers=inputs.headers,
        extra=inputs.extra,
        namespace="resident",
        sources=SOURCES_SESSION_ID,
        lenient=False,
    )
    chat_valid = all((not chat.invalid, chat.keyed, _valid_token(chat.value)))
    conv = chat.value if chat_valid else ""
    if is_zero_canon_profile(inputs.review_profile):
        return _ephemeral_identity(inputs, principal, conv, "zero_canon_ephemeral")
    if inputs.force_ephemeral:
        return _ephemeral_identity(inputs, principal, conv, "forced_ephemeral")
    if not chat_valid:
        return _no_chat_identity(inputs, principal)
    raw_cache = inputs.request.get("prompt_cache_key")
    cache_key = raw_cache if isinstance(raw_cache, str) else ""
    return ResidentIdentity(principal, conv, False, cache_key, inputs.turn_id, inputs.scope, inputs.subagent_id, _scoped_id(inputs, principal, conv))


def _identity_config(adapter: Any) -> tuple[bytes, str, bool, bool]:
    config_fn = getattr(adapter, "resident_identity_config", None)
    res = (_FALLBACK_SECRET, "", False, False)
    if callable(config_fn):
        try:
            secret, protocol, require_auth = cast(tuple[bytes, str, bool], config_fn())
            res = (secret, protocol, bool(require_auth), True)
        except Exception:
            pass
    return res


def _route_headers(route: Any) -> tuple[Any, Any]:
    handler = getattr(route, "handler", None)
    headers = getattr(handler, "headers", None) if handler is not None else getattr(route, "headers", None)
    return handler, headers


def _trusted_owner(route: Any, handler: Any, headers: Any) -> Any:
    host = getattr(route, "host", None)
    owner_fn = getattr(host, "owner_token_hash", None)
    legacy_owner_fn = getattr(host, "_owner_token_hash", None)
    out: Any = ""
    try:
        if callable(owner_fn):
            out = owner_fn(headers)
        elif callable(legacy_owner_fn):
            owner_handler = handler if handler is not None else SimpleNamespace(headers=headers)
            out = legacy_owner_fn(owner_handler)
    except Exception:
        out = ""
    return out


def _identity_extras(extra: Mapping[str, Any]) -> tuple[Any, Any, bool]:
    try:
        scope = extra.get("scope", "")
        subagent_id = extra.get("subagent_id", "")
    except Exception as exc:
        raise ResidentRequestError(400, "invalid_request") from exc
    try:
        force_ephemeral = bool(extra.get("force_ephemeral", False))
    except Exception:
        force_ephemeral = True
    return scope, subagent_id, force_ephemeral


def _nz(val: Any, default: Any) -> Any:
    res = val if val else default
    return res


def populate_resident_ctx(route: Any, ctx: dict[str, Any], extra: Mapping[str, Any], *, adapter: Any = None) -> None:
    handler, headers = _route_headers(route)
    raw_owner = _trusted_owner(route, handler, headers)
    secret, protocol, require_auth, config_ok = _identity_config(adapter)
    scope, subagent_id, force_ephemeral = _identity_extras(extra)
    subagent_id = _nz(subagent_id, _header_val(route, "X-Subagent-Id").strip())
    identity = resolve_resident_identity(
        IdentityInputs(
            request=route.request,
            headers=headers,
            extra=extra,
            secret=secret,
            trusted_principal_hash=raw_owner,
            scope=scope,
            subagent_id=subagent_id,
            protocol=protocol,
            require_auth=require_auth,
            force_ephemeral=any((force_ephemeral, not config_ok)),
            turn_id=str(_nz(ctx.get("requested_turn_id"), "")),
        )
    )
    ctx["resident_identity"] = identity
    ctx["owner_hash"] = raw_owner
    ctx["conversation_id"] = identity.conversation_id
    ctx["conversation_ephemeral"] = identity.ephemeral
    ctx["cache_key"] = "" if identity.ephemeral else identity.scoped_session_id


def _turn_ids_valid(route: Any, values: tuple[str, str]) -> bool:
    try:
        return all(route.host.validate_turn_id(value) for value in values if value)
    except Exception:
        return False


def _header_val(route: Any, name: str) -> str:
    _, headers = _route_headers(route)
    res = str(_nz(headers.get(name), "")) if callable(getattr(headers, "get", None)) else ""
    return res


def turn_ids_and_resident_ctx(route: Any, ctx: dict[str, Any], extra: dict[str, Any], *, adapter: Any = None) -> bool:
    requested_turn_id = str(_nz(_header_val(route, "X-Turn-Id"), _nz(extra.get("turn_id"), ""))).strip()
    resume_turn_id = str(_nz(_header_val(route, "X-Resume-Turn-Id"), _nz(extra.get("resume_turn_id"), ""))).strip()
    ctx["requested_turn_id"] = requested_turn_id
    ctx["resume_turn_id"] = resume_turn_id
    ok = True
    if not _turn_ids_valid(route, (requested_turn_id, resume_turn_id)):
        route.reject(400, "invalid_request", "invalid turn_id")
        ok = False
    elif getattr(adapter, "uses_resident_identity", False):
        try:
            populate_resident_ctx(route, ctx, extra, adapter=adapter)
        except (ResidentAuthError, ResidentRequestError) as err:
            route.reject(err.http_status, err.code, str(err))
            ok = False
    return ok
