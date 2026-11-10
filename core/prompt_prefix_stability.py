"""Контракт настройки стабильного префикса промпта."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

_FLAG_NAME = "BRIDGE_STABLE_PROMPT_PREFIX_ENABLED"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


class _Environment(Protocol):
    def get(self, key: str, default: str = "") -> str: ...


@dataclass(frozen=True)
class PrefixStabilityConfig:
    """Хранит флаг включения стабильного префикса промпта."""

    enabled: bool = True

    @classmethod
    def from_env(cls, environ: _Environment | None = None) -> PrefixStabilityConfig:
        """Строит конфигурацию из переданного окружения или ``os.environ``."""
        source = os.environ if environ is None else environ
        raw = str(source.get(_FLAG_NAME, "")).strip().lower()
        if raw in _TRUE_VALUES:
            return cls(enabled=True)
        if raw in _FALSE_VALUES:
            return cls(enabled=False)
        return cls()
