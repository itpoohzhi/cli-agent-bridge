from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from typing import TypeVar


T = TypeVar("T")


def get_env_str(name: str, default: str) -> str:
    """Return an environment value or its default when it is unset."""
    value = os.getenv(name)
    return default if value is None else value


def get_env_int(name: str, default: int) -> int:
    """Safely read an integer environment value."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def get_env_float(name: str, default: float) -> float:
    """Safely read a floating-point environment value."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return default


def get_env_bool(name: str, default: bool) -> bool:
    """Safely read a boolean environment value."""
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def get_env_list(
    name: str,
    default: Iterable[T],
    item_parser: Callable[[str], T] = str,
) -> list[T]:
    """Read a comma-separated environment value, falling back atomically."""
    value = os.getenv(name)
    if value is None:
        return list(default)

    items = [item.strip() for item in value.split(",") if item.strip()]
    try:
        return [item_parser(item) for item in items]
    except (TypeError, ValueError):
        return list(default)


BRIDGE_RESIDENT_MODELS: str = get_env_str("BRIDGE_RESIDENT_MODELS", "")
BRIDGE_RESIDENT_REQUIRED: str = get_env_str("BRIDGE_RESIDENT_REQUIRED", "all")
BRIDGE_PREWARM_STARTUP_TIMEOUT_S: float = get_env_float(
    "BRIDGE_PREWARM_STARTUP_TIMEOUT_S", 180.0
)
BRIDGE_PREWARM_CONCURRENCY: int = get_env_int("BRIDGE_PREWARM_CONCURRENCY", 4)
BRIDGE_HEALTH_PROBE_TIMEOUT_S: float = get_env_float(
    "BRIDGE_HEALTH_PROBE_TIMEOUT_S", 10.0
)
BRIDGE_RESET_TIMEOUT_S: float = get_env_float("BRIDGE_RESET_TIMEOUT_S", 20.0)
BRIDGE_RESTART_BACKOFF_S: list[float] = get_env_list(
    "BRIDGE_RESTART_BACKOFF_S",
    [1.0, 2.0, 5.0, 15.0, 60.0],
    float,
)
BRIDGE_UNPINNED_IDLE_TTL_S: float = get_env_float(
    "BRIDGE_UNPINNED_IDLE_TTL_S", 300.0
)
BRIDGE_STRICT_STARTUP: bool = get_env_bool("BRIDGE_STRICT_STARTUP", False)
BRIDGE_EFFORT_LEVELS: frozenset[str] = frozenset(
    get_env_list(
        "BRIDGE_EFFORT_LEVELS",
        ["off", "low", "medium", "high", "xhigh", "max"],
    )
)
BRIDGE_MUSE_STARTUP_TIMEOUT_S: float = get_env_float(
    "BRIDGE_MUSE_STARTUP_TIMEOUT_S", 180.0
)


__all__ = [
    "BRIDGE_RESIDENT_MODELS",
    "BRIDGE_RESIDENT_REQUIRED",
    "BRIDGE_PREWARM_STARTUP_TIMEOUT_S",
    "BRIDGE_PREWARM_CONCURRENCY",
    "BRIDGE_HEALTH_PROBE_TIMEOUT_S",
    "BRIDGE_RESET_TIMEOUT_S",
    "BRIDGE_RESTART_BACKOFF_S",
    "BRIDGE_UNPINNED_IDLE_TTL_S",
    "BRIDGE_STRICT_STARTUP",
    "BRIDGE_EFFORT_LEVELS",
    "BRIDGE_MUSE_STARTUP_TIMEOUT_S",
    "get_env_str",
    "get_env_int",
    "get_env_float",
    "get_env_bool",
    "get_env_list",
]
