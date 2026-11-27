"""Чистая канонизация идентичности сессии."""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from core.subbridge_zero_canon import normalize_review_profile

CHAT_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._:-]{8,128}\Z")
NAMESPACE_DSH: Final[uuid.UUID] = uuid.uuid5(uuid.NAMESPACE_URL, "urn:cli-agent-bridge:dsh")
_CHAT_HEADER_NAMES: Final[tuple[str, ...]] = ("x-dsh-chat-id", "x-session-id")


class SessionIdentityError(ValueError):
    """Ошибка входной идентичности с HTTP-кодом и машинным кодом."""

    def __init__(self, http_status: int, code: str, message: str = "") -> None:
        self.http_status = http_status
        self.code = code
        super().__init__(message or code)


@dataclass(frozen=True, slots=True)
class SessionIdentityInput:
    principal_id: str = ""
    backend_id: str = ""
    model_id: str = ""
    effort_level: str = ""
    review_profile: str = "standard"
    headers: Mapping[str, object] | None = None
    request_body: Mapping[str, object] | None = None
    extra: Mapping[str, object] | None = None
    cwd_norm: str = ""
    subagent_id: str = ""
    require_auth: bool = False
    allow_prompt_cache_key: bool = False


@dataclass(frozen=True, slots=True)
class CanonicalSessionIdentity:
    principal_id: str
    backend_id: str
    model_id: str
    effort_level: str
    review_profile: str
    canonical_chat_id: str | None
    keyed: bool
    isolation_namespace: str
    partition_key: str
    affinity_uuid5: str


def _mapping_value(mapping: Mapping[str, object] | None, wanted: str) -> object | None:
    if mapping is None:
        return None
    wanted_lower = wanted.lower()
    for key, value in mapping.items():
        if str(key).lower() == wanted_lower:
            return value
    return None


def _explicit_value(value: object, source: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SessionIdentityError(400, "ERR_INVALID_SESSION_ID", f"Invalid {source}")
    normalized = value.strip()
    if not normalized or CHAT_ID_RE.fullmatch(normalized) is None:
        raise SessionIdentityError(400, "ERR_INVALID_SESSION_ID", f"Invalid {source}")
    return normalized


def extract_canonical_chat_id(
    headers: Mapping[str, object] | None,
    body: Mapping[str, object] | None,
    extra: Mapping[str, object] | None,
    *,
    allow_prompt_cache_key: bool = False,
) -> str | None:
    """Извлекает chat id из всех поддержанных полей и отклоняет расхождения."""
    candidates: list[str] = []
    for header_name in _CHAT_HEADER_NAMES:
        value = _explicit_value(_mapping_value(headers, header_name), header_name)
        if value is not None:
            candidates.append(value)
    for field_name in ("session_id", "conversation_id", "chat_id"):
        value = _explicit_value(_mapping_value(body, field_name), field_name)
        if value is not None:
            candidates.append(value)
    value = _explicit_value(_mapping_value(extra, "chat_id"), "extra.chat_id")
    if value is not None:
        candidates.append(value)
    unique = set(candidates)
    if len(unique) > 1:
        raise SessionIdentityError(409, "SESSION_ID_CONFLICT", "Conflicting session identifiers")
    if candidates:
        return candidates[0]
    if allow_prompt_cache_key:
        return _explicit_value(_mapping_value(body, "prompt_cache_key"), "prompt_cache_key")
    return None


def _effective_cwd_hash(profile: str, cwd_norm: str) -> str:
    if profile == "zero-canon":
        return "zc-none"
    raw = str(cwd_norm or "").strip().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def resolve_canonical_identity(inp: SessionIdentityInput) -> CanonicalSessionIdentity:
    """Строит стабильный partition key и UUID affinity для одного запроса."""
    principal = str(inp.principal_id or "").strip()
    if inp.require_auth and not principal:
        raise SessionIdentityError(401, "AUTH_REQUIRED", "principal_id is required")
    profile = normalize_review_profile(inp.review_profile)
    chat_id = extract_canonical_chat_id(
        inp.headers, inp.request_body, inp.extra, allow_prompt_cache_key=inp.allow_prompt_cache_key
    )
    keyed = chat_id is not None
    if profile == "zero-canon":
        isolation = f"zc:{hashlib.sha256(chat_id.encode()).hexdigest()[:16]}" if keyed else f"zc:eph:{uuid.uuid4()}"
    elif keyed:
        isolation = f"std:{chat_id}"
    else:
        isolation = f"std:eph:{uuid.uuid4()}"
    cwd_hash = _effective_cwd_hash(profile, inp.cwd_norm)
    parts = (principal, inp.backend_id, profile, isolation, chat_id or isolation, inp.model_id, inp.effort_level, cwd_hash)
    partition = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return CanonicalSessionIdentity(
        principal_id=principal,
        backend_id=inp.backend_id,
        model_id=inp.model_id,
        effort_level=inp.effort_level,
        review_profile=profile,
        canonical_chat_id=chat_id,
        keyed=keyed,
        isolation_namespace=isolation,
        partition_key=partition,
        affinity_uuid5=str(uuid.uuid5(NAMESPACE_DSH, partition)),
    )
