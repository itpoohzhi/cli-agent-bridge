"""Stateless-хелперы agy-bridge (BND-002): сигнатура/сборка пула, stdout-precheck, чистая проекция сообщений."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import cast

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_io import EOF, LINE, ResidentProcessHandle, StdioIoError
from core.stdio_resident.process_pool import ResidentProcessPool

from .persistent_worker_config import PersistentWorkerSettings

__all__ = [
    "PoolSig", "build_pool", "estimate_raw_messages_bytes", "extract_message_text",
    "has_stale_stdout_or_eof", "pool_sig_of",
]

PoolSig = tuple[int, float, float, int, float]
_LOGGER = logging.getLogger(__name__)


def pool_sig_of(cfg: PersistentWorkerSettings) -> PoolSig:
    """Сигнатура параметров пула: смена => пересоздание пула."""
    return (cfg.max_slots, cfg.idle_timeout_s, cfg.ttl_s, cfg.max_rss_mb, cfg.lease_wait_s)


def build_pool(cfg: PersistentWorkerSettings) -> ResidentProcessPool:
    """Собрать ResidentProcessPool из настроек воркера."""
    return ResidentProcessPool(StdioPoolConfig(
        max_slots=cfg.max_slots, max_slots_per_principal=cfg.max_slots,
        max_ephemeral_slots=cfg.max_slots, idle_timeout_s=cfg.idle_timeout_s,
        ttl_s=cfg.ttl_s, max_rss_bytes=cfg.max_rss_mb * 1024 * 1024,
        lease_wait_s=cfg.lease_wait_s, enabled=True, turn_idle_timeout_s=cfg.idle_timeout_s,
    ))


def has_stale_stdout_or_eof(handle: ResidentProcessHandle) -> bool:
    """True, если процесс мёртв или в stdout остался хвост/EOF прошлого хода."""
    if not handle.is_alive():
        return True
    try:
        kind, _tagged = handle.read_stdout_line_outcome(timeout_s=0.0)
    except (OSError, StdioIoError, RuntimeError) as exc:
        _LOGGER.warning("persistent stdout precheck failed: %s", exc)
        return True
    return kind in (LINE, EOF)


def estimate_raw_messages_bytes(messages: Sequence[object], limit: int) -> int:
    total, stack = 0, list(messages)
    while stack:
        item = stack.pop()
        if isinstance(item, (str, bytes, bytearray)):
            total += len(item) if isinstance(item, (bytes, bytearray)) else len(item.encode("utf-8", "replace")) + 2
        elif isinstance(item, dict):
            d = cast("dict[object, object]", item)
            total, _ = total + 4 * len(d), [stack.extend((k, v)) for k, v in d.items()]
        elif isinstance(item, (list, tuple)):
            seq = cast("Sequence[object]", item)
            total, _ = total + 2 * len(seq), stack.extend(seq)
        else:
            total += len(str(item).encode("utf-8", "replace"))
        if total > limit:
            return total
    return total


def _extract_part(item: object, img_counter: list[int]) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return ""
    m = cast("dict[str, object]", item)
    if m.get("type") == "image_url":
        img_counter[0] += 1
        return f"[image {img_counter[0]}]"
    return "" if (t := m.get("text")) is None else str(t)


def extract_message_text(content: object, img_counter: list[int]) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p for p in (_extract_part(x, img_counter) for x in cast("list[object]", content)) if p)
    return "" if content is None else str(content)
