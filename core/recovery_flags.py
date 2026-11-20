"""Kill-switch флаги и числовые параметры устойчивости хода (AD-007, BND-003).

Шесть независимых флагов, default `False`. Источники: env и `dynamic_config.json`
(`BRIDGE_DYNAMIC_CONFIG_PATH`, иначе `~/.config/cli-agent-bridge/dynamic_config.json`).
Семантика `read_recovery_switch`: включает явный `true`, любой другой явный/битый источник —
вето; симлинк/FIFO/не-файл/oversize/невалидный JSON — fail-closed `False`. Чтение свежее на
каждый вызов (кэша нет). Числа: env > config > безопасный дефолт, вне диапазона → дефолт.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from pathlib import Path

from core.transport_failure_contracts import (
    FLAG_ENV_BY_FIELD,
    RecoveryFlagSnapshot,
    RetryBudgetConfig,
    TransportFailureConfig,
)

CONFIG_PATH_ENV = "BRIDGE_DYNAMIC_CONFIG_PATH"
CONFIG_MAX_BYTES_ENV = "BRIDGE_RECOVERY_CONFIG_MAX_BYTES"
DEFAULT_CONFIG_MAX_BYTES = 65536
DEFAULT_CONFIG_PATH = "~/.config/cli-agent-bridge/dynamic_config.json"
TRUE_VALUES = ("1", "true", "yes", "on")
ABSENT = None
INVALID = False
_REGULAR_FILE = 0o100000
_FILE_TYPE_MASK = 0o170000


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _read_bytes(path: Path, max_bytes: int) -> bytes | None:
    """Прочитать regular-файл без следования симлинку; любой дефект → `None`."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return None
    try:
        if (os.fstat(fd).st_mode & _FILE_TYPE_MASK) != _REGULAR_FILE:
            return None
        raw = os.read(fd, max_bytes + 1)
    except OSError:
        return None
    finally:
        os.close(fd)
    return raw if len(raw) <= max_bytes else None


def load_config(path: Path, max_bytes: int = DEFAULT_CONFIG_MAX_BYTES) -> dict[str, object] | bool | None:
    """`ABSENT` (нет файла) | `INVALID` (дефект, fail-closed) | словарь конфигурации."""
    if not os.path.lexists(path):
        return ABSENT
    raw = _read_bytes(path, max_bytes)
    if raw is None:
        return INVALID
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        return INVALID
    return data if isinstance(data, dict) else INVALID


def _config_path(env: Mapping[str, str], path: Path | None) -> Path:
    if path is not None:
        return path
    return Path(env.get(CONFIG_PATH_ENV, "").strip() or os.path.expanduser(DEFAULT_CONFIG_PATH))


def _max_bytes(env: Mapping[str, str]) -> int:
    try:
        value = int(env.get(CONFIG_MAX_BYTES_ENV, "").strip())
    except ValueError:
        return DEFAULT_CONFIG_MAX_BYTES
    return value if 0 < value <= 16 * 1024 * 1024 else DEFAULT_CONFIG_MAX_BYTES


def _load(env: Mapping[str, str], path: Path | None) -> dict[str, object] | bool | None:
    return load_config(_config_path(env, path), _max_bytes(env))


def _decide(name: str, env: Mapping[str, str], config: dict[str, object] | bool | None) -> bool:
    """Включено iff есть явный opt-in и нет ни одного вето; нет источников → `False`."""
    votes: list[bool] = []
    raw = env.get(name, "").strip().lower()
    if raw:
        votes.append(raw in TRUE_VALUES)
    if config is INVALID:
        return False
    if isinstance(config, dict) and name in config:
        votes.append(config[name] is True)
    return bool(votes) and all(votes)


def read_recovery_switch(
    name: str, env: Mapping[str, str] | None = None, config_path: Path | None = None
) -> bool:
    """Прочитать один флаг заново (env + dynamic_config, любое вето/дефект → `False`)."""
    values = _env(env)
    return _decide(name, values, _load(values, config_path))


def read_recovery_flags(
    env: Mapping[str, str] | None = None, config_path: Path | None = None
) -> RecoveryFlagSnapshot:
    """Свежий снимок шести флагов; конфиг читается один раз за вызов."""
    values = _env(env)
    config = _load(values, config_path)
    return RecoveryFlagSnapshot(**{field: _decide(name, values, config) for field, name in FLAG_ENV_BY_FIELD})


def read_number(
    name: str, default: float, bounds: tuple[float, float],
    env: Mapping[str, str] | None = None, config: object = None,
) -> float:
    """Число из env, затем из config (dict); невалидное/вне `bounds` → `default`."""
    values = _env(env)
    sources: list[object] = [values.get(name, "").strip()]
    if isinstance(config, dict):
        sources.append(config.get(name))
    for raw in sources:
        try:
            value = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and bounds[0] <= value <= bounds[1]:
            return value
    return default


def read_retry_budget_config(
    env: Mapping[str, str] | None = None, config_path: Path | None = None
) -> RetryBudgetConfig:
    """Параметры бюджета повтора из окружения/конфига с безопасными дефолтами."""
    values = _env(env)
    cfg = _load(values, config_path)
    base = RetryBudgetConfig()
    num = lambda n, d, hi: read_number(n, d, (0.0, hi), values, cfg)  # noqa: E731
    return RetryBudgetConfig(
        max_retries=int(num("BRIDGE_PRERETRY_MAX_RETRIES", base.max_retries, 10.0)),
        retry_total_budget_s=num("BRIDGE_RETRY_TOTAL_BUDGET_S", base.retry_total_budget_s, 86400.0),
        client_timeout_s=num("BRIDGE_CLIENT_TIMEOUT_S", base.client_timeout_s, 86400.0),
        pause_max_s=num("BRIDGE_RETRY_PAUSE_MAX_S", base.pause_max_s, 600.0),
        window_s=num("BRIDGE_FAILURE_WINDOW_S", base.window_s, 86400.0),
    )


def read_transport_failure_config(
    env: Mapping[str, str] | None = None, config_path: Path | None = None
) -> TransportFailureConfig:
    """`max_chars` из env/конфига; шаблоны — env `BRIDGE_TRANSPORT_TRANSIENT_PATTERNS` (`||`)."""
    values = _env(env)
    cfg = _load(values, config_path)
    base = TransportFailureConfig()
    limit = read_number("BRIDGE_TRANSPORT_FAILURE_MAX_CHARS", base.max_chars, (1.0, 65536.0), values, cfg)
    custom = tuple(p for p in values.get("BRIDGE_TRANSPORT_TRANSIENT_PATTERNS", "").split("||") if p)
    return TransportFailureConfig(custom or base.transient_patterns, base.fatal_patterns, int(limit))
