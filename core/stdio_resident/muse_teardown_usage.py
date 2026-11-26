"""Helpers for Muse late ``session/tokenUsage`` capture and item/completed deduplication."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from core.stdio_resident.usage_extract import extract_muse_usage
from core.turn_usage import UsageUpdate

_LATE_USAGE_METHODS: frozenset[str] = frozenset({"session/tokenUsage", "turn/tokenUsage", "run.tokenUsage"})


def late_usage_from_frame(frame: Mapping[str, object]) -> UsageUpdate | None:
    """Return the UsageUpdate carried by a late tokenUsage notification, else None."""
    method = frame.get("method")
    params = frame.get("params")
    if method not in _LATE_USAGE_METHODS or not isinstance(params, Mapping):
        return None
    return extract_muse_usage(str(method), params)  # pyright: ignore[reportUnknownArgumentType]


def _dedup_completed(chunk: Any, sid: str, params: Mapping[str, Any], lock: threading.Lock, streamed: dict[str, set[str]]) -> Any:
    """Clear duplicate text/reasoning on item/completed while preserving usage."""
    item = params.get("item") if isinstance(params.get("item"), Mapping) else {}
    if not (item_id := str(item.get("itemId") or "")):
        return chunk
    with lock:
        seen = streamed.get(sid)
        already = bool(seen and item_id in seen)
        if seen is not None:
            seen.discard(item_id)
    return replace(chunk, text="", reasoning="") if already else chunk


def dedup_item_chunk(chunk: Any, sid: str, method: Any, params: Mapping[str, Any], state: tuple[threading.Lock, dict[str, set[str]]]) -> Any:
    """Track streamed item/delta IDs and deduplicate subsequent item/completed chunks."""
    lock, streamed = state
    if method in {"item.delta", "item/delta"} and (chunk.text or chunk.reasoning):
        if item_id := str(params.get("itemId") or ""):
            with lock:
                streamed.setdefault(sid, set()).add(item_id)
        return chunk
    return _dedup_completed(chunk, sid, params, lock, streamed) if method == "item/completed" else chunk
