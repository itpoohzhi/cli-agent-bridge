from __future__ import annotations

"""Конфигурация резидентного драйвера `agy` и быстрый JSON-сериализатор (AD-003)."""

import importlib  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
from collections.abc import Callable, Mapping  # noqa: E402
from dataclasses import dataclass, replace  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import TypeVar, cast  # noqa: E402

from core.stdio_resident.config import StdioPoolConfig  # noqa: E402

try:
    from agy_runtime.agy_resident_canary import AgyResidentCanaryConfig  # noqa: E402
except ImportError:
    _BRIDGE_DIR = Path(__file__).resolve().parents[2] / "bridges" / "agy-bridge"
    if str(_BRIDGE_DIR) not in sys.path:
        sys.path.insert(0, str(_BRIDGE_DIR))
    from agy_runtime.agy_resident_canary import AgyResidentCanaryConfig  # noqa: E402

__all__ = [
    "FLAG_AGY_RESIDENT",
    "AgyResidentConfig",
    "apply_canary_limits",
    "build_agy_pool_config",
    "encode_json_bytes",
    "is_agy_resident_enabled",
    "load_agy_canary_config",
    "load_agy_resident_config",
]

_Num = TypeVar("_Num", int, float)
FLAG_AGY_RESIDENT = "AGY_RESIDENT_ENABLED"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on", "y", "t", "enabled"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", "n", "f", "disabled"})


def _build_json_encoder() -> Callable[[object, bool], bytes]:
    """Data-plane сериализатор: предпочитает `orjson`/`msgspec`, fallback — stdlib."""
    try:
        orjson = importlib.import_module("orjson")
        dumps_fn = cast("Callable[..., bytes]", getattr(orjson, "dumps"))
        opt_sort = int(getattr(orjson, "OPT_SORT_KEYS", 0))
        return lambda obj, sk: dumps_fn(obj, option=opt_sort if sk else 0)
    except ImportError:
        pass
    try:
        msgspec_json = importlib.import_module("msgspec.json")
        enc_fn = cast("Callable[..., bytes]", getattr(msgspec_json, "encode"))
        return lambda obj, sk: enc_fn(obj, order="sorted" if sk else None)
    except ImportError:
        pass
    std_json = importlib.import_module("json")
    std_dumps = cast("Callable[..., str]", getattr(std_json, "dumps"))
    return lambda obj, sk: std_dumps(
        obj, ensure_ascii=False, separators=(",", ":"), sort_keys=sk
    ).encode("utf-8")


_JSON_ENCODE: Callable[[object, bool], bytes] = _build_json_encoder()


def encode_json_bytes(obj: object, *, sort_keys: bool = False) -> bytes:
    """Кодирует объект в UTF-8 JSON bytes через доступный быстрый сериализатор."""
    return _JSON_ENCODE(obj, sort_keys)


@dataclass(frozen=True)
class AgyResidentConfig:
    enabled: bool = False
    max_slots: int = 8
    idle_timeout_s: float = 600.0
    ttl_s: float = 3600.0
    max_rss_mb: int = 1024
    lease_wait_timeout_s: float = 30.0

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Fail-closed: проверка всех числовых диапазонов на границе конфигурации."""
        if self.max_slots < 1 or self.max_rss_mb < 64:
            raise ValueError("max_slots>=1 and max_rss_mb>=64 required")
        for name, val in (
            ("idle_timeout_s", self.idle_timeout_s),
            ("ttl_s", self.ttl_s),
            ("lease_wait_timeout_s", self.lease_wait_timeout_s),
        ):
            if not math.isfinite(val) or val <= 0.0:
                raise ValueError(f"{name} must be finite and > 0, got {val!r}")
        if self.ttl_s < self.idle_timeout_s:
            raise ValueError("ttl_s must be >= idle_timeout_s")


def is_agy_resident_enabled(env: Mapping[str, str]) -> bool:
    """Читает только kill-switch `AGY_RESIDENT_ENABLED` без парсинга прочих AGY_* переменных."""
    raw = _raw(env, FLAG_AGY_RESIDENT)
    if raw is None:
        return False
    return raw.lower() in _TRUE_VALUES


def _raw(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key)
    return (value.strip() or None) if value is not None else None


def _parse_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    if (raw := _raw(env, key)) is None:
        return default
    norm = raw.lower()
    if norm in _TRUE_VALUES or norm in _FALSE_VALUES:
        return norm in _TRUE_VALUES
    raise ValueError(f"{key} must be a boolean, got {raw!r}")


def _parse_num(
    env: Mapping[str, str], key: str, conv: Callable[[str], _Num], default: _Num
) -> _Num:
    if (raw := _raw(env, key)) is None:
        return default
    try:
        value = conv(raw)
    except ValueError:
        raise ValueError(f"{key} must be a number, got {raw!r}") from None
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{key} must be finite, got {raw!r}")
    return value


def load_agy_resident_config(
    env: Mapping[str, str], ladder_idle_s: float = 600.0
) -> AgyResidentConfig:
    """Конфиг из явного окружения без `os.environ`; idle — env или лестница (не 180 c)."""
    if not math.isfinite(ladder_idle_s) or ladder_idle_s <= 0.0:
        raise ValueError(f"ladder_idle_s must be finite > 0, got {ladder_idle_s!r}")
    d, p = AgyResidentConfig(), _parse_num
    return AgyResidentConfig(
        enabled=_parse_bool(env, FLAG_AGY_RESIDENT, d.enabled),
        max_slots=p(env, "AGY_RESIDENT_MAX_SLOTS", int, d.max_slots),
        idle_timeout_s=p(
            env, "AGY_RESIDENT_IDLE_TIMEOUT_S", float, float(ladder_idle_s)
        ),
        ttl_s=p(env, "AGY_RESIDENT_TTL_S", float, d.ttl_s),
        max_rss_mb=p(env, "AGY_RESIDENT_MAX_RSS_MB", int, d.max_rss_mb),
        lease_wait_timeout_s=p(
            env, "AGY_RESIDENT_LEASE_WAIT_S", float, d.lease_wait_timeout_s
        ),
    )


def load_agy_canary_config(env: Mapping[str, str]) -> AgyResidentCanaryConfig:
    """Загрузить канареечные пороги `AGY_CANARY_*` из явного окружения без `os.environ`."""
    d, p = AgyResidentCanaryConfig(), _parse_num
    baseline_max_slots = p(
        env, "AGY_CANARY_BASELINE_MAX_SLOTS", int, d.baseline_max_slots
    )
    max_slots = p(env, "AGY_CANARY_MAX_SLOTS", int, d.max_slots)
    rss_per_slot = p(
        env, "AGY_CANARY_RSS_CEILING_PER_SLOT_MB", int, d.rss_ceiling_per_slot_mb
    )
    rss_total = p(env, "AGY_CANARY_RSS_CEILING_TOTAL_MB", int, d.rss_ceiling_total_mb)
    fd_limit = p(env, "AGY_CANARY_FD_LIMIT_PER_SLOT", int, d.fd_limit_per_slot)
    error_rate_stop = p(
        env, "AGY_CANARY_ERROR_RATE_STOP_PCT", float, d.error_rate_stop_pct
    )
    fd_leak_stop = _parse_bool(env, "AGY_CANARY_FD_LEAK_STOP", d.fd_leak_stop)
    is_baseline = _parse_bool(env, "AGY_CANARY_BASELINE", False)
    if is_baseline:
        AgyResidentCanaryConfig(
            baseline_max_slots=baseline_max_slots,
            max_slots=max_slots,
            rss_ceiling_per_slot_mb=rss_per_slot,
            rss_ceiling_total_mb=rss_total,
            fd_limit_per_slot=fd_limit,
            error_rate_stop_pct=error_rate_stop,
            fd_leak_stop=fd_leak_stop,
        )
        max_slots = min(max_slots, baseline_max_slots)
    return AgyResidentCanaryConfig(
        baseline_max_slots=baseline_max_slots,
        max_slots=max_slots,
        rss_ceiling_per_slot_mb=rss_per_slot,
        rss_ceiling_total_mb=rss_total,
        fd_limit_per_slot=fd_limit,
        error_rate_stop_pct=error_rate_stop,
        fd_leak_stop=fd_leak_stop,
    )


def apply_canary_limits(
    cfg: AgyResidentConfig,
    canary: AgyResidentCanaryConfig,
    *,
    baseline: bool = False,
    env: Mapping[str, str] | None = None,
) -> AgyResidentConfig:
    """Клампит лимиты резидентного конфига потолками канарейки и возвращает новый инстанс."""
    cfg.validate()
    canary.validate()
    use_baseline = baseline or (
        env is not None and _parse_bool(env, "AGY_CANARY_BASELINE", False)
    )
    slot_cap = canary.baseline_max_slots if use_baseline else canary.max_slots
    return replace(
        cfg,
        max_slots=min(cfg.max_slots, slot_cap),
        max_rss_mb=min(cfg.max_rss_mb, canary.rss_ceiling_per_slot_mb),
    )


def build_agy_pool_config(cfg: AgyResidentConfig) -> StdioPoolConfig:
    """Маппинг всех полей `AgyResidentConfig` в `StdioPoolConfig` (рециркуляция: idle/ttl/rss)."""
    cfg.validate()
    return StdioPoolConfig(
        max_slots=cfg.max_slots,
        idle_timeout_s=cfg.idle_timeout_s,
        ttl_s=cfg.ttl_s,
        max_rss_bytes=cfg.max_rss_mb * 1024 * 1024,
        lease_wait_s=cfg.lease_wait_timeout_s,
        enabled=cfg.enabled,
        turn_idle_timeout_s=cfg.idle_timeout_s,
    )
