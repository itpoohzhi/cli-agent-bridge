"""Универсальный фасад несекретных watchdog-настроек мостов (AD-002, ADR-0014/0015).

Каскад чтения: `os.environ` -> allowlisted `~/.dsh/.env` -> fallback-ключ -> default.
Секреты (например `{prefix}KEY`) не читаются; `os.environ` никогда не мутируется.
Числовые пределы иммутабельны на время жизни процесса (ADR-0015): смена `.env`
требует рестарта сервиса.
"""

from __future__ import annotations

import logging
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from core.env_hot_reload import parse_env_text

_LOGGER = logging.getLogger(__name__)

ALLOWED_WATCHDOG_SETTINGS_KEYS: frozenset[str] = frozenset((
    "CLAUDE_P_BRIDGE_WATCHDOG_ENABLED", "CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S",
    "CLAUDE_P_BRIDGE_IO_WAIT_CAP_S", "CLAUDE_P_BRIDGE_SAFETY_CAP_S",
    "CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S", "BRIDGE_IDLE_TIMEOUT_S",
    "BRIDGE_IO_WAIT_CAP_S", "BRIDGE_SAFETY_CAP_S", "BRIDGE_WATCHDOG_INTERVAL_S",
    "BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S",
))
_LEGACY_SUFFIXES: tuple[str, ...] = (
    "WATCHDOG_ENABLED", "IDLE_TIMEOUT_S", "IO_WAIT_CAP_S", "SAFETY_CAP_S", "WATCHDOG_INTERVAL_S",
)
_EMPTY_ENV: Mapping[str, str] = MappingProxyType({})


def _read_allowlisted_env(path: Path | None, allowed: frozenset[str]) -> Mapping[str, str]:
    """Несекретный снимок `.env` по allowlist; сбой чтения — пустой снимок, без мутаций."""
    if path is None:
        path = Path.home() / ".dsh" / ".env"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return _EMPTY_ENV
    parsed = parse_env_text(text)
    return MappingProxyType({k: v for k, v in parsed.items() if k in allowed})


@dataclass(frozen=True)
class BridgeWatchdogFacade:
    """Иммутабельный read-only фасад watchdog-настроек одного моста (агент-агностик)."""

    first_token_timeout_s: float | None = None
    _prefix: str = ""
    _allowed_keys: frozenset[str] = ALLOWED_WATCHDOG_SETTINGS_KEYS
    _first_progress_keys: tuple[str, ...] = ("BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S",)
    _env_file_values: Mapping[str, str] = field(default=_EMPTY_ENV, repr=False)

    @classmethod
    def for_prefix(
        cls,
        prefix: str,
        *,
        first_progress_keys: tuple[str, ...] = ("BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S",),
        env_path: Path | None = None,
    ) -> BridgeWatchdogFacade:
        """Фасад для `{prefix}*` и общих `BRIDGE_*` ключей; `env_path` — только для тестов."""
        allowed = ALLOWED_WATCHDOG_SETTINGS_KEYS | frozenset(
            prefix + suffix for suffix in _LEGACY_SUFFIXES
        ) | frozenset(first_progress_keys)
        facade = cls(
            _prefix=prefix, _allowed_keys=allowed, _first_progress_keys=first_progress_keys,
            _env_file_values=_read_allowlisted_env(env_path, allowed),
        )
        return cls(
            first_token_timeout_s=facade.get_bounded_float(first_progress_keys),
            _prefix=prefix, _allowed_keys=allowed, _first_progress_keys=first_progress_keys,
            _env_file_values=facade._env_file_values,
        )

    @property
    def env_file_values(self) -> Mapping[str, str]:
        """Read-only проекция allowlisted снимка `.env` (MappingProxyType)."""
        return self._env_file_values

    def get_setting(self, name: str, fallback_name: str | None = None, default: str = "") -> str:
        """Каскад `os.environ` -> `.env` для name, затем fallback_name, затем default."""
        for key in (name, fallback_name) if fallback_name else (name,):
            value = os.environ.get(key)
            if value is not None and value.strip():
                return value.strip()
            value = self._env_file_values.get(key)
            if value is not None and value.strip():
                return value.strip()
        return default

    def get_positive_float(self, name: str, fallback_name: str | None = None, default: float = 0.0) -> float:
        """Конечное положительное число; пустое/невалидное значение — безопасный default."""
        raw = self.get_setting(name, fallback_name)
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            return default
        return value if math.isfinite(value) and value > 0.0 else default

    def is_watchdog_enabled(self) -> bool:
        """Legacy kill-switch `{prefix}WATCHDOG_ENABLED` (по умолчанию включён)."""
        raw = self.get_setting(self._prefix + "WATCHDOG_ENABLED", default="1").lower()
        return raw not in ("0", "false", "no", "off")

    def get_bounded_float(
        self, keys: tuple[str, ...], *, min_value: float = 1.0, max_value: float = 3600.0
    ) -> float | None:
        """Первый заданный ключ: конечный float в [min_value, max_value].

        Невалидное/неконечное/вне границ значение — `logger.warning` и fallback `None`
        (штатный дефолт конфигурации потребителя). Отсутствующие ключи — `None` без warning.
        """
        for key in keys:
            raw = self.get_setting(key)
            if not raw:
                continue
            try:
                value = float(raw)
            except ValueError:
                value = math.nan
            if math.isfinite(value) and min_value <= value <= max_value:
                return value
            _LOGGER.warning(
                "bridge watchdog setting %s=%r invalid (finite float in [%s, %s] required); using default",
                key, raw, min_value, max_value,
            )
            return None
        return None
