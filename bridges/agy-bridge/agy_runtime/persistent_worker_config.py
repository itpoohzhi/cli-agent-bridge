"""Конфигурация и типы контракта пула постоянных воркеров agy-bridge (os.environ > dynamic_config.json > default)."""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from core.stdio_resident.process_io import ResidentProcessHandle
from core.stdio_resident.process_pool import ResidentProcessPool

from .long_session_config import (
    classify_cloud_mode,
    read_bool_setting,
    read_float_setting,
    read_int_setting,
)

__all__ = [
    "PersistentAcquireRequest",
    "PersistentLease",
    "PersistentReleaseParams",
    "PersistentWorkerSettings",
    "RunCloseContext",
    "RunPumpDrainContext",
    "RunSpawnContext",
    "compute_env_digest",
    "persistent_worker_settings",
]


def compute_env_digest(
    cli_mode: str,
    zero_canon: bool,
    clean_home: str,
    settings_arg: str = "",
    launch_env: Mapping[str, str] | None = None,
) -> str:
    """Стабильный отпечаток среды запуска слота (исключает смешение профилей).

    При ``launch_env is None`` digest побитово совместим с прежней 3/4-аргументной
    формулой; иначе добавляется сегмент сетевого режима (direct vs georouter).
    """
    raw = f"mode={cli_mode}|zc={int(zero_canon)}|home={clean_home}|cfg={settings_arg}"
    if launch_env is not None:
        raw = f"{raw}|net={classify_cloud_mode(launch_env)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class PersistentWorkerSettings:
    """Параметры пула живых воркеров и окон SQLite-drain без захардкоженных лимитов."""

    enabled: bool = False
    max_slots: int = 8
    lease_wait_s: float = 0.25
    idle_timeout_s: float = 300.0
    ttl_s: float = 1800.0
    max_rss_mb: int = 768
    max_turns: int = 50
    pump_tick_s: float = 0.5
    persistent_drain_window_s: float = 0.10
    drain_window_s: float = 0.35
    standby_enabled: bool = False
    standby_max_slots: int = 1
    standby_init_timeout_s: float = 30.0
    standby_ttl_s: float = 300.0
    fast_drain_enabled: bool = False
    fast_drain_min_s: float = 0.015
    fresh_rotate_enabled: bool = False


@dataclass(frozen=True)
class PersistentAcquireRequest:
    """Параметры запроса на аренду живого слота."""

    chat_key: str
    cid: str
    model: str
    effort: str
    cwd: str
    env_digest: str
    review_profile: str
    argv_builder: Callable[[], list[str]]
    env: Mapping[str, str]


@dataclass(frozen=True)
class PersistentReleaseParams:
    """Параметры освобождения арендованного слота после хода."""

    success: bool
    cancel: bool = False
    cid: str = ""
    still_enabled: bool = True
    max_slots: int = 8
    rotate: bool = False


@dataclass
class PersistentLease:
    """Аренда одного живого процесса из ResidentProcessPool на время одного хода."""

    pool: ResidentProcessPool
    slot_id: str
    lease_id: str
    handle: ResidentProcessHandle
    chat_key: str
    reused: bool
    turns_before: int
    max_turns: int
    pump_tick_s: float
    drain_window_s: float
    released: bool = False
    prefetched_init_line: str = ""
    fast_drain_enabled: bool = False
    fast_drain_min_s: float = 0.015
    standby_claimed: bool = False


@dataclass(frozen=True)
class RunSpawnContext:
    """Контекст старта процесса для Run (persistent-слот либо cold-spawn)."""

    pool: object
    config_path: Path
    cmd: list[str]
    work_dir: str
    launch_env: Mapping[str, str]
    model: str
    effort: str
    cli_mode: str
    zero_canon: bool
    settings_arg: str
    add_dir: Path | None
    chat_key: str
    spawn_cold: Callable[[], subprocess.Popen[bytes]]
    on_cold_fail: Callable[[], None]


@dataclass(frozen=True)
class RunPumpDrainContext:
    """Параметры финального drain после завершения stdout-потока хода."""

    config_path: Path
    proc_exit_wait_s: float
    drain_max_s: float
    result_ev: Mapping[str, object]


@dataclass(frozen=True)
class RunCloseContext:
    """Зависимости закрытия cold/persistent ресурсов в Run.close."""

    kill_group: Callable[[subprocess.Popen[bytes]], None]
    unregister_proc: Callable[[subprocess.Popen[bytes]], None]
    join_timeout_s: float


def _read_lifecycle_bounds(
    config_path: Path | None,
) -> tuple[float, float, int, int]:
    idle_s = read_float_setting(
        "persistent_worker_idle_timeout_s", "AGY_BRIDGE_PERSISTENT_IDLE_S",
        300.0, (30.0, 3600.0), config_path=config_path,
    )
    ttl_s = max(
        idle_s,
        read_float_setting(
            "persistent_worker_ttl_s", "AGY_BRIDGE_PERSISTENT_TTL_S",
            1800.0, (60.0, 14400.0), config_path=config_path,
        ),
    )
    max_rss_mb = read_int_setting(
        "persistent_worker_max_rss_mb", "AGY_BRIDGE_PERSISTENT_MAX_RSS_MB",
        768, (128, 4096), config_path=config_path,
    )
    max_turns = read_int_setting(
        "persistent_worker_max_turns", "AGY_BRIDGE_PERSISTENT_MAX_TURNS",
        50, (1, 500), config_path=config_path,
    )
    return idle_s, ttl_s, max_rss_mb, max_turns


def _read_drain_windows(config_path: Path | None) -> tuple[float, float, float]:
    pump_tick_s = read_float_setting(
        "persistent_worker_pump_tick_s", "AGY_BRIDGE_PERSISTENT_PUMP_TICK_S",
        0.5, (0.05, 5.0), config_path=config_path,
    )
    persistent_drain_s = read_float_setting(
        "persistent_drain_window_s", "AGY_BRIDGE_PERSISTENT_DRAIN_WINDOW_S",
        0.10, (0.0, 0.50), config_path=config_path,
    )
    drain_s = read_float_setting(
        "drain_window_s", "AGY_BRIDGE_DRAIN_WINDOW_S",
        0.35, (0.05, 0.50), config_path=config_path,
    )
    return pump_tick_s, persistent_drain_s, drain_s


def _read_standby_and_fast_drain(
    config_path: Path | None,
) -> tuple[bool, int, float, float, bool, float]:
    st_en = read_bool_setting(
        "BRIDGE_AGY_STANDBY_ENABLED", "AGY_BRIDGE_STANDBY_ENABLED",
        False, config_path=config_path,
    )
    st_max = read_int_setting(
        "persistent_standby_max_slots", "AGY_BRIDGE_STANDBY_MAX_SLOTS",
        1, (1, 4), config_path=config_path,
    )
    st_init = read_float_setting(
        "persistent_standby_init_timeout_s", "AGY_BRIDGE_STANDBY_INIT_TIMEOUT_S",
        30.0, (5.0, 60.0), config_path=config_path,
    )
    st_ttl = read_float_setting(
        "persistent_standby_ttl_s", "AGY_BRIDGE_STANDBY_TTL_S",
        300.0, (30.0, 1800.0), config_path=config_path,
    )
    fd_en = read_bool_setting(
        "BRIDGE_AGY_PERSISTENT_FAST_DRAIN_ENABLED", "AGY_BRIDGE_PERSISTENT_FAST_DRAIN_ENABLED",
        False, config_path=config_path,
    )
    fd_min = read_float_setting(
        "persistent_fast_drain_min_s", "AGY_BRIDGE_PERSISTENT_FAST_DRAIN_MIN_S",
        0.015, (0.005, 0.10), config_path=config_path,
    )
    return st_en, st_max, st_init, st_ttl, fd_en, fd_min


def persistent_worker_settings(
    *, config_path: Path | None = None
) -> PersistentWorkerSettings:
    """Читает kill-switch и параметры пула постоянных воркеров без хардкода."""
    enabled = read_bool_setting(
        "BRIDGE_AGY_PERSISTENT_WORKER_ENABLED",
        "AGY_BRIDGE_PERSISTENT_WORKER_ENABLED",
        False,
        config_path=config_path,
    )
    max_slots = read_int_setting(
        "persistent_worker_max_slots", "AGY_BRIDGE_PERSISTENT_MAX_SLOTS",
        8, (1, 32), config_path=config_path,
    )
    lease_wait_s = read_float_setting(
        "persistent_worker_lease_wait_s", "AGY_BRIDGE_PERSISTENT_LEASE_WAIT_S",
        0.25, (0.05, 30.0), config_path=config_path,
    )
    idle_s, ttl_s, max_rss_mb, max_turns = _read_lifecycle_bounds(config_path)
    pump_tick_s, persistent_drain_s, drain_s = _read_drain_windows(config_path)
    st_en, st_max, st_init, st_ttl, fd_en, fd_min = _read_standby_and_fast_drain(config_path)
    fresh_rotate_enabled = read_bool_setting(
        "BRIDGE_AGY_PERSISTENT_FRESH_ROTATE_ENABLED",
        "AGY_BRIDGE_PERSISTENT_FRESH_ROTATE_ENABLED",
        False,
        config_path=config_path,
    )
    return PersistentWorkerSettings(
        enabled=enabled, max_slots=max_slots, lease_wait_s=lease_wait_s,
        idle_timeout_s=idle_s, ttl_s=ttl_s, max_rss_mb=max_rss_mb,
        max_turns=max_turns, pump_tick_s=pump_tick_s,
        persistent_drain_window_s=persistent_drain_s, drain_window_s=drain_s,
        standby_enabled=st_en, standby_max_slots=st_max,
        standby_init_timeout_s=st_init, standby_ttl_s=st_ttl,
        fast_drain_enabled=fd_en, fast_drain_min_s=fd_min,
        fresh_rotate_enabled=fresh_rotate_enabled,
    )
