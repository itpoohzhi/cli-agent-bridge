"""Разрешение runtime-каталогов agy в zero_canon и сбор защищённых explicit ZC cid (AD-002 / BUG-B2, RISK-B3).

Каталоги conversations/brain изолируются в agy-home-zc при zero_canon; активные cid
(in-flight + живые слоты ExplicitSessionStore) защищаются от maybe_rotate_agy_runtime_artifacts.
"""
from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from time import time as _time
from typing import Any

__all__ = ["resolve_agy_runtime_dirs", "collect_protected_zc_cids"]


def resolve_agy_runtime_dirs(
    zero_canon: bool,
    *,
    clean_home: Path,
    zc_home: Path | None = None,
    default_conv_dir: Path | None = None,
    default_brain_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Пара (conversations, brain): zc-режим изолирован в agy-home-zc, иначе дефолты clean_home."""
    if zero_canon:
        base = zc_home if zc_home is not None else clean_home.with_name(f"{clean_home.name}-zc")
        return (base / ".gemini" / "antigravity-cli" / "conversations", base / ".gemini" / "antigravity-cli" / "brain")
    return (
        default_conv_dir or (clean_home / ".gemini" / "antigravity-cli" / "conversations"),
        default_brain_dir or (clean_home / ".gemini" / "antigravity-cli" / "brain"),
    )


def _store_active_cids(store: Any, now_s: float) -> list[str]:
    """Read-only сбор cid живых слотов: активный lease ИЛИ не просрочен по idle/max TTL."""
    cids: list[str] = []
    slots = getattr(store, "_slots", None)
    if not isinstance(slots, dict):
        return cids
    policy = getattr(store, "_policy", None)
    idle_ttl = float(getattr(policy, "idle_ttl_s", 0.0) or 0.0)
    max_ttl = float(getattr(policy, "max_ttl_s", 0.0) or 0.0)
    for rec in list(slots.values()):
        cid = getattr(rec, "cid", "")
        if not isinstance(cid, str) or not cid:
            continue
        if getattr(rec, "lease_token", ""):
            cids.append(cid)
            continue
        idle = now_s - float(getattr(rec, "last_used_s", 0.0) or 0.0)
        age = now_s - float(getattr(rec, "created_s", 0.0) or 0.0)
        if (idle_ttl > 0 and idle > idle_ttl) or (max_ttl > 0 and age > max_ttl):
            continue
        cids.append(cid)
    return cids


def collect_protected_zc_cids(
    in_flight_cids: Iterable[str],
    explicit_adapter: Any | None = None,
    *,
    now_s: float | None = None,
) -> frozenset[str]:
    """Объединяет непустые in_flight_cids с активными cid ExplicitSessionStore адаптера.

    Любая ошибка чтения store подавляется: возвращается хотя бы in_flight_cids.
    """
    now = _time() if now_s is None else float(now_s)
    result = {cid for cid in in_flight_cids if isinstance(cid, str) and cid}
    with suppress(Exception):
        store = None if explicit_adapter is None else getattr(explicit_adapter, "_store", None)
        if store is not None:
            lock = getattr(store, "_lock", None)
            if lock is not None:
                with lock:
                    result.update(_store_active_cids(store, now))
            else:
                result.update(_store_active_cids(store, now))
    return frozenset(result)
