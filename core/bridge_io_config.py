"""Проверенная конфигурация сокетов и общего бюджета HTTP-соединений."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BridgeIOConfig:
    """Резервы входят в общий лимит; keepalive не имеет верхнего потолка."""

    tcp_nodelay: bool = True
    admission_limit: int = 128
    ui_reserve: int = 2
    header_headroom: int = 2
    keepalive_s: float = 3.0

    def __post_init__(self) -> None:
        if type(self.tcp_nodelay) is not bool:
            raise ValueError("tcp_nodelay must be boolean")
        for name, value in (
            ("admission_limit", self.admission_limit),
            ("ui_reserve", self.ui_reserve),
            ("header_headroom", self.header_headroom),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.admission_limit == 0:
            raise ValueError("admission_limit must be positive")
        if self.subagent_http_occupants < 0:
            raise ValueError("admission_limit must cover UI and header reserves")
        if not math.isfinite(self.keepalive_s) or self.keepalive_s <= 0:
            raise ValueError("keepalive_s must be positive and finite")

    @property
    def subagent_http_occupants(self) -> int:
        """Возвращает вместимость без расходования обоих резервов."""
        return self.admission_limit - self.ui_reserve - self.header_headroom


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be boolean")


def load_bridge_io_config() -> BridgeIOConfig:
    """Читает env; невалидные значения отклоняет через ValueError."""
    defaults = BridgeIOConfig()
    return BridgeIOConfig(
        tcp_nodelay=_env_bool("BRIDGE_TCP_NODELAY", defaults.tcp_nodelay),
        admission_limit=int(
            os.environ.get("BRIDGE_ADMISSION_LIMIT", str(defaults.admission_limit))
        ),
        ui_reserve=int(os.environ.get("BRIDGE_UI_RESERVE", str(defaults.ui_reserve))),
        header_headroom=int(
            os.environ.get("BRIDGE_HEADER_HEADROOM", str(defaults.header_headroom))
        ),
        keepalive_s=float(os.environ.get("KEEPALIVE_S", str(defaults.keepalive_s))),
    )
