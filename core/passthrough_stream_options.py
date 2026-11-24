"""Declarative ``stream_options.include_usage`` policy for passthrough.

Pure helpers: no I/O, no environment reads, no model-name hardcoding.

F-004: an explicit client ``include_usage`` is never overwritten.
F-010 (Threat Model): raw upstream 400 bodies never leak through this
module's API — they are consumed only by the classifier and never stored,
formatted into exceptions, or logged.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from typing import Any, Literal

CHAT_COMPLETIONS_PREFIX = "/v1/chat/completions"
_STREAM_OPTION_KEYS = ("stream_options", "include_usage")
_SCHEMA_REJECTION_MARKERS = (
    "unknown",
    "unsupported",
    "unrecognized",
    "extra",
    "invalid",
    "not permitted",
    "not allowed",
    "additional properties",
    "unexpected",
)

StreamOptionsCacheKey = tuple[str, str, str, str]
Classification = Literal["stream_options_rejected", "other_400", "not_400"]


def supports_stream_options(
    path: str, backend_config: Mapping[str, Any] | None
) -> bool:
    """Declarative capability flag; no model-name substring matching."""
    if not str(path).startswith(CHAT_COMPLETIONS_PREFIX):
        return False
    if backend_config is not None:
        value = backend_config.get("supports_stream_options")
        if value is not None:
            return bool(value)
    return True


def model_scope_hash(model: Any) -> str:
    """Opaque 12-hex scope id; never embeds the raw model string."""
    return hashlib.sha256(str(model or "").encode("utf-8")).hexdigest()[:12]


class BoundedNegativeCache:
    """Per-instance bounded TTL cache of upstream stream_options rejections.

    Keys are opaque 4-tuples (backend_id, upstream_endpoint_id,
    model_scope_hash, api_version_scope); no URLs, headers, or secrets.
    """

    def __init__(self, ttl_s: float = 900.0, max_entries: int = 256) -> None:
        self._ttl_s = float(ttl_s)
        self._max_entries = int(max_entries)
        self._lock = threading.Lock()
        self._entries: dict[StreamOptionsCacheKey, tuple[float, int]] = {}
        self._seq = 0

    def _purge_expired(self, now: float) -> None:
        stale = [
            key
            for key, (expires_at, _) in self._entries.items()
            if expires_at <= now
        ]
        for key in stale:
            del self._entries[key]

    def is_rejected(self, key: StreamOptionsCacheKey, now: float) -> bool:
        with self._lock:
            self._purge_expired(now)
            return key in self._entries

    def mark_rejected(self, key: StreamOptionsCacheKey, now: float) -> None:
        with self._lock:
            self._purge_expired(now)
            if key in self._entries:
                return
            if self._max_entries > 0 and len(self._entries) >= self._max_entries:
                victim = min(self._entries, key=lambda k: self._entries[k])
                del self._entries[victim]
            self._entries[key] = (now + self._ttl_s, self._seq)
            self._seq += 1

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"BoundedNegativeCache(ttl_s={self._ttl_s}, "
                f"max_entries={self._max_entries}, size={len(self._entries)})"
            )


def _body_text(body: bytes | str) -> str:
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


def classify_400_for_stream_options(
    status_code: int, body: bytes | str
) -> Classification:
    """Classify a 400 without ever persisting or re-emitting ``body``."""
    if status_code != 400:
        return "not_400"
    text = _body_text(body).lower()
    if not any(name in text for name in _STREAM_OPTION_KEYS):
        return "other_400"
    if any(marker in text for marker in _SCHEMA_REJECTION_MARKERS):
        return "stream_options_rejected"
    return "other_400"


def prepare_stream_usage_body(
    path: str,
    request: Mapping[str, Any],
    raw_body: bytes,
    *,
    enabled: bool,
    supports: bool,
    negative_hit: bool,
) -> tuple[bytes, bool]:
    """Return ``(effective_body, injected_by_hub)`` for the usage injection."""
    if (
        not enabled
        or not supports
        or negative_hit
        or not str(path).startswith(CHAT_COMPLETIONS_PREFIX)
    ):
        return raw_body, False
    try:
        data = json.loads(raw_body)
    except ValueError:
        return raw_body, False
    if not isinstance(data, dict) or not bool(data.get("stream")):
        return raw_body, False
    options = data.get("stream_options")
    if isinstance(options, Mapping) and "include_usage" in options:
        return raw_body, False
    data["stream_options"] = {
        **(options if isinstance(options, dict) else {}),
        "include_usage": True,
    }
    return json.dumps(data, ensure_ascii=False).encode("utf-8"), True


def strip_stream_options(raw_body: bytes) -> bytes:
    """Remove ``stream_options`` for a single pre-commit retry."""
    try:
        data = json.loads(raw_body)
    except ValueError:
        return raw_body
    if not isinstance(data, dict) or "stream_options" not in data:
        return raw_body
    data.pop("stream_options", None)
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def should_retry_stream_options(
    *,
    status_code: int,
    body: bytes | str,
    committed_to_client: bool,
    injected_by_hub: bool,
    attempt_index: int,
) -> bool:
    """Retry (with stream_options stripped) only on the first attempt."""
    return (
        attempt_index == 0
        and injected_by_hub
        and not committed_to_client
        and classify_400_for_stream_options(status_code, body)
        == "stream_options_rejected"
    )
