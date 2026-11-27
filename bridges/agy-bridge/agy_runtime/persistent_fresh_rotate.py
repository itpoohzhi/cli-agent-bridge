"""Тонкая оболочка эффектов: аренда persistent-слота с защитой от «грязных» слотов."""

from __future__ import annotations

import logging

from .persistent_fresh_claim import (
    ClaimInput,
    FreshClaimDecision,
    LeaseFacts,
    decide_fresh_claim,
)
from .persistent_worker_adapter import AgyPersistentWorkerPool
from .persistent_worker_config import (
    PersistentAcquireRequest,
    PersistentLease,
    PersistentReleaseParams,
    PersistentWorkerSettings,
)

__all__ = ["acquire_with_fresh_guard"]

_LOGGER = logging.getLogger(__name__)

_IDENT = "verdict=%s chat=%s slot=%s"
_FIELDS = "turns_before=%d gen=%d standby_claimed=%s"
_FMT_SHADOW = " ".join(("event=fresh_claim action=shadow", _IDENT, _FIELDS))
_FMT_ROTATE = " ".join(("event=fresh_claim action=rotate", _IDENT, _FIELDS))
_FMT_STALE = " ".join(
    ("event=fresh_claim action=cold_fallback reason=stale_reacquire", _IDENT, _FIELDS)
)
_FMT_RELEASE_ERR = " ".join(
    ("event=fresh_claim action=cold_fallback reason=release_error", _IDENT)
)
_FMT_REACQUIRE_NONE = (
    "event=fresh_claim action=cold_fallback reason=reacquire_none chat=%s"
)


def _lease_facts(lease: PersistentLease | None) -> LeaseFacts | None:
    """Извлекает наблюдаемые факты об аренде (None, если аренды нет)."""
    if lease is None:
        return None
    return LeaseFacts(
        turns_before=lease.turns_before,
        reused=lease.reused,
        standby_claimed=lease.standby_claimed,
        generation=lease.handle.generation,
    )


def _log_args(
    decision: FreshClaimDecision, lease: PersistentLease
) -> tuple[object, ...]:
    """Собирает аргументы структурированной строки лога для вердикта и аренды."""
    return (
        decision.verdict.value,
        lease.chat_key,
        lease.slot_id,
        lease.turns_before,
        lease.handle.generation,
        lease.standby_claimed,
    )


def _release_stale(
    pool: AgyPersistentWorkerPool,
    lease: PersistentLease,
    cfg: PersistentWorkerSettings,
    decision: FreshClaimDecision,
) -> bool:
    """Освобождает stale-аренду с ротацией; False при сбое освобождения."""
    params = PersistentReleaseParams(
        success=False,
        cancel=False,
        cid="",
        still_enabled=cfg.enabled,
        max_slots=cfg.max_slots,
        rotate=True,
    )
    try:
        pool.release(lease, params)
    except Exception:  # noqa: BLE001  # сбой освобождения -> cold fallback
        _LOGGER.warning(
            _FMT_RELEASE_ERR, decision.verdict.value, lease.chat_key, lease.slot_id
        )
        return False
    return True


def _log_rotation(decision: FreshClaimDecision, lease: PersistentLease) -> None:
    """Логирует ротацию (INFO) либо cold fallback после повторной stale-аренды (WARNING)."""
    if decision.reacquire:
        _LOGGER.info(_FMT_ROTATE, *_log_args(decision, lease))
    elif decision.cold_fallback:
        _LOGGER.warning(_FMT_STALE, *_log_args(decision, lease))


def acquire_with_fresh_guard(
    pool: AgyPersistentWorkerPool,
    req: PersistentAcquireRequest,
    cfg: PersistentWorkerSettings,
) -> PersistentLease | None:
    """Арендует слот; при stale-аренде ротирует её и пробует ещё раз, иначе cold-spawn."""
    if not cfg.enabled:
        return None
    for attempt in (0, 1):
        lease = pool.acquire(req, cfg)
        if lease is None:
            if attempt == 1:
                _LOGGER.warning(_FMT_REACQUIRE_NONE, req.chat_key)
            return None
        decision = decide_fresh_claim(
            ClaimInput(
                has_cid=bool(req.cid),
                enabled=cfg.fresh_rotate_enabled,
                attempt=attempt,
                lease=_lease_facts(lease),
            )
        )
        if decision.shadow_would_rotate:
            _LOGGER.debug(_FMT_SHADOW, *_log_args(decision, lease))
            return lease
        if not decision.discard_current:
            return lease
        if not _release_stale(pool, lease, cfg, decision):
            return None
        _log_rotation(decision, lease)
        if decision.cold_fallback or not decision.reacquire:
            return None
    return None
