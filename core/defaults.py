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

# --- Телеметрия запросов (core/request_telemetry.py). Значения ниже — fallback: каждое
# переопределяется переменной окружения с тем же именем (читается при создании стора).
BRIDGE_TELEMETRY_ENABLED: bool = True
BRIDGE_TELEMETRY_DB_PATH: str = "~/.dsh/telemetry/bridge_telemetry.duckdb"
BRIDGE_TELEMETRY_QUEUE_MAXSIZE: int = 4096
BRIDGE_TELEMETRY_FLUSH_INTERVAL_MS: int = 500
BRIDGE_TELEMETRY_BATCH_SIZE: int = 100
BRIDGE_TELEMETRY_RETENTION_DAYS: int = 14
BRIDGE_TELEMETRY_MAX_ROWS: int = 500000
BRIDGE_TELEMETRY_RECENT_LIMIT: int = 100
BRIDGE_TELEMETRY_PRUNE_INTERVAL_S: float = 60.0
BRIDGE_TELEMETRY_MAX_FIELD_LEN: int = 160
BRIDGE_TELEMETRY_WINDOW_MIN_H: float = 0.1
BRIDGE_TELEMETRY_WINDOW_MAX_H: float = 720.0
BRIDGE_TELEMETRY_LIMIT_MAX: int = 500
# Карта backend_id -> (outbound_target, egress_proxy); JSON-override:
# BRIDGE_TELEMETRY_BACKEND_TOPOLOGY_JSON='{"agy": [":9887", "direct"]}'.
BRIDGE_TELEMETRY_BACKEND_TOPOLOGY: dict[str, tuple[str, str]] = {
    "droid": ("cli:droid", "direct"),
    "muse": (":9886", ":10820 (xray SOCKS5)"),
    "claude-p": (":9881", "direct"),
    "opencode-zen": (":9883", ":10816 (pproxy HTTP)"),
    "opencode": (":9883", ":10816 (pproxy HTTP)"),
    "agy": (":9887", ":10820 (xray SOCKS5)"),
    "codex": (":2455", ":10820 (xray SOCKS5)"),
    "georouter": (":10830", ":10820 (xray SOCKS5)"),
    "litellm": (":10830", ":10820 (xray SOCKS5)"),
}
# Трёхъярусная карта потока для architecture_flow; JSON-override:
# BRIDGE_TELEMETRY_TOPOLOGY_JSON. Узлы tier1 сопоставляются первым совпадением
# (roles / subagent / ua), tier2 — по backends (all=true — весь хаб), tier3 — по match.
BRIDGE_TELEMETRY_TOPOLOGY: dict[str, dict] = {
    "tier1_entry_callers": {
        "layer": "L7 inbound callers",
        "description": "Клиенты и агенты, которые обращаются к хабу :9882 (Bearer BRIDGE_KEY).",
        "nodes": [
            {"id": "council", "name": "launch_seat.py / Council", "roles": ["seat", "skeptic"]},
            {"id": "subagents", "name": "Subagents (X-Subagent-Id)", "subagent": True},
            {"id": "claude-code", "name": "Claude Code", "ua": ["claude"]},
            {"id": "codex-cli", "name": "Codex CLI", "ua": ["codex"]},
            {"id": "factory-droid", "name": "Factory Droid", "ua": ["droid", "factory"]},
            {"id": "dsh", "name": "DSH Desktop/Web", "ua": ["dsh", "electron", "mozilla"]},
        ],
    },
    "tier2_l7_bridges": {
        "layer": "L7 AI protocol bridges",
        "description": (
            "Переводят протокол в OpenAI /v1/chat/completions: санитизация tool-calls, SSE-фрейминг, "
            "circuit breaker, карантин моделей, управление сессиями."
        ),
        "nodes": [
            {"id": "universal-9882", "name": "cli-agent-bridge (Universal Hub)", "port": 9882, "all": True},
            {"id": "claude-9881", "name": "claude-p-bridge", "port": 9881, "backends": ["claude-p"]},
            {"id": "opencode-9883", "name": "opencode-zen-bridge", "port": 9883, "backends": ["opencode-zen", "opencode"]},
            {"id": "agy-9887", "name": "agy-bridge", "port": 9887, "backends": ["agy"]},
            {"id": "muse-9886", "name": "muse-bridge", "port": 9886, "backends": ["muse"]},
            {"id": "codex-2455", "name": "codex-lb", "port": 2455, "backends": ["codex"]},
            {"id": "georouter-10830", "name": "eye-litellm / OpenCode Go", "port": 10830, "backends": ["georouter", "litellm"]},
        ],
    },
    "tier3_l4_egress_proxies": {
        "layer": "L4/L7 network egress proxies",
        "description": (
            "Транспорт TCP/TLS/SOCKS5/HTTP-туннеля до провайдера; не меняют LLM JSON/SSE полезную нагрузку."
        ),
        "nodes": [
            {"id": "xray-10820", "name": "xray SOCKS5 (Amsterdam Aeza)", "port": 10820, "match": [":10820"]},
            {"id": "pproxy-10816", "name": "pproxy HTTP-to-SOCKS5 shim", "port": 10816, "match": [":10816"]},
            {"id": "xray-10809", "name": "xray Timeweb fallback", "port": 10809, "match": [":10809", ":10801"]},
        ],
    },
}


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
    "BRIDGE_TELEMETRY_ENABLED",
    "BRIDGE_TELEMETRY_DB_PATH",
    "BRIDGE_TELEMETRY_QUEUE_MAXSIZE",
    "BRIDGE_TELEMETRY_FLUSH_INTERVAL_MS",
    "BRIDGE_TELEMETRY_BATCH_SIZE",
    "BRIDGE_TELEMETRY_RETENTION_DAYS",
    "BRIDGE_TELEMETRY_MAX_ROWS",
    "BRIDGE_TELEMETRY_RECENT_LIMIT",
    "BRIDGE_TELEMETRY_PRUNE_INTERVAL_S",
    "BRIDGE_TELEMETRY_MAX_FIELD_LEN",
    "BRIDGE_TELEMETRY_WINDOW_MIN_H",
    "BRIDGE_TELEMETRY_WINDOW_MAX_H",
    "BRIDGE_TELEMETRY_LIMIT_MAX",
    "BRIDGE_TELEMETRY_BACKEND_TOPOLOGY",
    "BRIDGE_TELEMETRY_TOPOLOGY",
    "get_env_str",
    "get_env_int",
    "get_env_float",
    "get_env_bool",
    "get_env_list",
]
