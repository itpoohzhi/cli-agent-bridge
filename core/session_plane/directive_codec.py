"""Zero-I/O подпись межпроцессных директив сессии."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import time
from dataclasses import dataclass

from .lifecycle_policy import ContextDirective, ProcessDirective, SessionExecutionPlan

DIRECTIVE_HEADER = "X-DSH-Session-Directive"
DIRECTIVE_TTL_S = 30.0
MAX_DIRECTIVE_BYTES = 640
_PROCESSES = {"WARM_SLOT_REUSE", "EPHEMERAL_KILL_AFTER_TURN"}
_CONTEXTS = {"CONTEXT_CONTINUE", "CONTEXT_RESET_LOGICAL", "SLOT_HARD_RESET"}


@dataclass(frozen=True, slots=True)
class SignedDirectivePayload:
    partition_key: str
    review_profile: str
    process_directive: ProcessDirective
    context_directive: ContextDirective
    thread_epoch: int
    config_revision: int
    exp_ts: float
    decision_reason: str
    chat_id_hash: str = ""


def chat_id_hash_of(chat_id: str | None) -> str:
    """16 hex sha256(chat_id) для привязки директивы к чату; пустой chat_id -> ``""``."""
    return hashlib.sha256(chat_id.encode("utf-8")).hexdigest()[:16] if chat_id else ""


_FIELDS = frozenset({"partition_key", "review_profile", "process_directive", "context_directive", "thread_epoch", "config_revision", "exp_ts", "decision_reason", "chat_id_hash"})


def _now(value: float | None) -> float:
    return time.time() if value is None else float(value)


def _payload(plan: SessionExecutionPlan, exp_ts: float) -> dict[str, object]:
    return {
        "partition_key": plan.partition_key, "review_profile": plan.review_profile,
        "process_directive": plan.process_directive, "context_directive": plan.context_directive,
        "thread_epoch": plan.next_epoch, "config_revision": plan.config_revision,
        "exp_ts": exp_ts, "decision_reason": plan.decision_reason,
        "chat_id_hash": chat_id_hash_of(plan.canonical_chat_id),
    }


def encode_directive(plan: SessionExecutionPlan, secret: bytes, *, now_s: float | None = None, ttl_s: float = DIRECTIVE_TTL_S) -> str:
    """Кодирует компактный JSON и HMAC-SHA256 в URL-safe заголовок."""
    if len(secret) < 16:
        raise ValueError("directive secret must contain at least 16 bytes")
    exp_ts = _now(now_s) + float(ttl_s)
    raw = json.dumps(_payload(plan, exp_ts), separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    signing_input = f"v1.{encoded}".encode("ascii")
    signature = hmac.new(secret, signing_input, hashlib.sha256).hexdigest()
    result = f"v1.{encoded}.{signature}"
    if len(result.encode("ascii")) > MAX_DIRECTIVE_BYTES:
        raise ValueError("directive exceeds maximum size")
    return result


def _decode_payload(encoded: str) -> SignedDirectivePayload | None:
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if not isinstance(data, dict) or set(data) != _FIELDS:
            return None
        process, context = data["process_directive"], data["context_directive"]
        if process not in _PROCESSES or context not in _CONTEXTS:
            return None
        if not isinstance(data["partition_key"], str) or not isinstance(data["review_profile"], str) or not isinstance(data["decision_reason"], str) or not isinstance(data["chat_id_hash"], str):
            return None
        epoch, revision = data["thread_epoch"], data["config_revision"]
        exp_ts = data["exp_ts"]
        if isinstance(epoch, bool) or not isinstance(epoch, int) or isinstance(revision, bool) or not isinstance(revision, int) or isinstance(exp_ts, bool) or not isinstance(exp_ts, (int, float)) or not math.isfinite(float(exp_ts)):
            return None
        return SignedDirectivePayload(data["partition_key"], data["review_profile"], process, context, epoch, revision, float(exp_ts), data["decision_reason"], data["chat_id_hash"])
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return None


def verify_directive(header_value: str | None, secret: bytes, *, now_s: float | None = None, min_config_revision: int = 0) -> tuple[SignedDirectivePayload | None, str]:
    """Проверяет формат, подпись, TTL, ревизию и допустимые директивы."""
    if len(secret) < 16:
        return None, "weak_secret"
    if not isinstance(header_value, str) or not header_value:
        return None, "empty"
    if len(header_value.encode("ascii", errors="ignore")) > MAX_DIRECTIVE_BYTES or not header_value.isascii():
        return None, "oversized"
    parts = header_value.split(".")
    if len(parts) != 3 or parts[0] != "v1" or not parts[1] or not parts[2]:
        return None, "malformed"
    expected = hmac.new(secret, f"v1.{parts[1]}".encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, parts[2]):
        return None, "invalid_signature"
    payload = _decode_payload(parts[1])
    if payload is None:
        return None, "invalid_payload"
    if _now(now_s) > payload.exp_ts:
        return None, "expired"
    if payload.config_revision < min_config_revision:
        return None, "stale_revision"
    return payload, "ok"
