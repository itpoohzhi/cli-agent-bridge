"""Единый адаптер конфигурации loss-контракта agy-bridge (W2-A, BND-002).

Читает 9 ключей (CD-008) по приоритету env > dynamic_config.json > default
через ``long_session_config``, разрешает ``LifecyclePolicy`` один раз на запрос
(AD-003) и отдаёт проекции для session store, hot-политики, пула воркеров и
решения compact_tools (AD-013). При ``unified_lifecycle_enabled=false`` каждая
проекция возвращает legacy-значения без изменений.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from core.hot_session_policy import PolicyConfig
from core.resumed_tools_policy import (
    CompactToolsMode,
    CompactToolsQuery,
    decide_compact_tools,
)

from .conversation_lifecycle import LifecyclePolicy, is_conversation_expired
from .input_guard_policy import InputGuardMode
from .long_session_config import (
    _present,
    _raw_setting,
    read_bool_setting,
    read_float_setting,
    read_int_setting,
)
from .persistent_worker_config import PersistentWorkerSettings

__all__ = [
    "LossContractSettings",
    "compact_tools_decision",
    "continuity_ttl_s",
    "hot_overrides",
    "read_input_guard_mode",
    "read_loss_contract_settings",
    "resolve_lifecycle_policy",
    "session_expired",
    "session_max_turns",
    "worker_bounds",
]

_TURNS_BOUNDS = (1, 1000)
_IDLE_BOUNDS = (1.0, 604_800.0)
_MAX_TTL_BOUNDS = (1.0, 2_592_000.0)
_WORKER_TURNS_CEIL = 500


@dataclass(frozen=True, slots=True)
class LossContractSettings:
    """Снимок 9 ключей loss-контракта, разрешённый один раз на запрос."""

    strict_cold_rotation: bool = True
    unified_lifecycle_enabled: bool = True
    lifecycle: LifecyclePolicy = LifecyclePolicy()
    loss_receipt_enabled: bool = True
    compact_tools_mode: CompactToolsMode = CompactToolsMode.PROVEN
    atomic_active_tools_enabled: bool = True
    input_guard_mode: InputGuardMode = InputGuardMode.COMPACT_OR_REJECT


def _flag(key: str, default: bool, config_path: Path | None) -> bool:
    return read_bool_setting(
        key, f"AGY_BRIDGE_{key.upper()}", default, config_path=config_path
    )


def resolve_lifecycle_policy(*, config_path: Path | None = None) -> LifecyclePolicy:
    """Единая политика беседы: max_turns/idle/max TTL; max_ttl >= idle_ttl."""
    max_turns = read_int_setting(
        "lifecycle_max_turns", "AGY_BRIDGE_LIFECYCLE_MAX_TURNS",
        30, _TURNS_BOUNDS, config_path=config_path,
    )
    idle_ttl_s = read_float_setting(
        "lifecycle_idle_ttl_s", "AGY_BRIDGE_LIFECYCLE_IDLE_TTL_S",
        2700.0, _IDLE_BOUNDS, config_path=config_path,
    )
    max_ttl_s = read_float_setting(
        "lifecycle_max_ttl_s", "AGY_BRIDGE_LIFECYCLE_MAX_TTL_S",
        86400.0, _MAX_TTL_BOUNDS, config_path=config_path,
    )
    return LifecyclePolicy(max_turns, idle_ttl_s, max(idle_ttl_s, max_ttl_s))


def read_input_guard_mode(*, config_path: Path | None = None) -> InputGuardMode:
    """Режим гарда; неизвестное значение -> безопасный дефолт compact_or_reject."""
    raw = _raw_setting("input_guard_mode", "AGY_BRIDGE_INPUT_GUARD_MODE", config_path)
    token = str(raw).strip().lower() if _present(raw) else ""
    if token == InputGuardMode.LEGACY.value:
        return InputGuardMode.LEGACY
    return InputGuardMode.COMPACT_OR_REJECT


def _read_compact_mode(config_path: Path | None) -> CompactToolsMode:
    raw = _raw_setting("compact_tools_mode", "AGY_BRIDGE_COMPACT_TOOLS_MODE", config_path)
    return CompactToolsMode.parse(raw if _present(raw) else None)


def read_loss_contract_settings(
    *, config_path: Path | None = None
) -> LossContractSettings:
    """Прочитать все 9 ключей (env > dynamic_config.json > default)."""
    return LossContractSettings(
        strict_cold_rotation=_flag("strict_cold_rotation", True, config_path),
        unified_lifecycle_enabled=_flag("unified_lifecycle_enabled", True, config_path),
        lifecycle=resolve_lifecycle_policy(config_path=config_path),
        loss_receipt_enabled=_flag("loss_receipt_enabled", True, config_path),
        compact_tools_mode=_read_compact_mode(config_path),
        atomic_active_tools_enabled=_flag("atomic_active_tools_enabled", True, config_path),
        input_guard_mode=read_input_guard_mode(config_path=config_path),
    )


def _unified(config_path: Path | None) -> bool:
    return _flag("unified_lifecycle_enabled", True, config_path)


def session_max_turns(*, config_path: Path | None = None) -> int:
    """Предел ходов session store: unified -> lifecycle, иначе legacy-ключ."""
    if _unified(config_path):
        return resolve_lifecycle_policy(config_path=config_path).max_turns
    return read_int_setting(
        "session_max_turns", "AGY_BRIDGE_SESSION_MAX_TURNS",
        30, _TURNS_BOUNDS, config_path=config_path,
    )


def _num(value: object) -> float:
    return float(cast("float | int | str", value))


def session_expired(
    entry: Mapping[str, object],
    now: float,
    legacy: tuple[float, float],
    *,
    config_path: Path | None = None,
) -> bool:
    """Expiry записи session store; legacy=(idle_ttl_s, max_ttl_s) при выключенном gate."""
    if _unified(config_path):
        policy = resolve_lifecycle_policy(config_path=config_path)
    else:
        policy = LifecyclePolicy(
            session_max_turns(config_path=config_path), legacy[0], legacy[1]
        )
    return is_conversation_expired(
        _num(entry["created"]),
        _num(entry["last_used"]),
        int(_num(entry["turns"])),
        now,
        policy,
    )


def hot_overrides(
    cfg: PolicyConfig, *, config_path: Path | None = None
) -> PolicyConfig:
    """Наложить lifecycle на hot-политику; kill-switch false -> cfg без изменений."""
    if not _unified(config_path):
        return cfg
    policy = resolve_lifecycle_policy(config_path=config_path)
    return replace(
        cfg,
        max_turns=policy.max_turns,
        idle_ttl_s=policy.idle_ttl_s,
        max_ttl_s=policy.max_ttl_s,
    )


def worker_bounds(
    settings: PersistentWorkerSettings, *, config_path: Path | None = None
) -> PersistentWorkerSettings:
    """Зажать воркер: max_turns := policy, idle/ttl <= conversation idle/max."""
    if not _unified(config_path):
        return settings
    policy = resolve_lifecycle_policy(config_path=config_path)
    idle_s = min(settings.idle_timeout_s, policy.idle_ttl_s)
    ttl_s = max(idle_s, min(settings.ttl_s, policy.max_ttl_s))
    return replace(
        settings,
        idle_timeout_s=idle_s,
        ttl_s=ttl_s,
        max_turns=min(policy.max_turns, _WORKER_TURNS_CEIL),
    )


def continuity_ttl_s(legacy_ttl_s: float, *, config_path: Path | None = None) -> float:
    """TTL continuity := idle_ttl_s при unified, иначе legacy-значение."""
    if not _unified(config_path):
        return legacy_ttl_s
    return resolve_lifecycle_policy(config_path=config_path).idle_ttl_s


def compact_tools_decision(
    query: CompactToolsQuery, *, config_path: Path | None = None
) -> bool:
    """Решение compact_tools с режимом из конфигурации (AD-013)."""
    mode = _read_compact_mode(config_path)
    return decide_compact_tools(replace(query, mode=mode))
