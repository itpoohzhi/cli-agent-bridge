"""Stateless-хелперы пула постоянных воркеров agy-bridge (BND-002): сигнатура, сборка пула, stdout-precheck."""

from __future__ import annotations

import logging

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_io import EOF, LINE, ResidentProcessHandle, StdioIoError
from core.stdio_resident.process_pool import ResidentProcessPool

from .persistent_worker_config import PersistentWorkerSettings

__all__ = ["PoolSig", "build_pool", "has_stale_stdout_or_eof", "pool_sig_of"]

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
