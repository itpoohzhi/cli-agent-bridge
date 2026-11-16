"""Проверенная конфигурация сокетов и общего бюджета HTTP-соединений."""

from __future__ import annotations

import math
import os
import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BridgeIOConfig:
    """Резервы входят в общий лимит; keepalive не имеет верхнего потолка."""

    tcp_nodelay: bool = True
    admission_limit: int = 128
    ui_reserve: int = 2
    header_headroom: int = 2
    keepalive_s: float = 3.0
    read_timeout_s: float | None = None
    write_timeout_s: float | None = None

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
        for name in ("read_timeout_s", "write_timeout_s"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be positive and finite")

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
        read_timeout_s=_env_timeout("BRIDGE_READ_TIMEOUT_S"),
        write_timeout_s=_env_timeout("BRIDGE_WRITE_TIMEOUT_S"),
    )


def _env_timeout(name: str) -> float | None:
    raw = os.environ.get(name)
    return None if raw is None else float(raw)


class AdmissionBudget:
    """Единственный владелец билетов и незанятых резервов UI/заголовков.

    UI и заголовки могут занимать общие слоты, но не незанятый чужой резерв.
    Обычные соединения не занимают ни один незанятый резерв.
    """

    def __init__(self, config: BridgeIOConfig | None = None) -> None:
        self._config: BridgeIOConfig = (
            load_bridge_io_config() if config is None else config
        )
        self._tickets: dict[str, tuple[bool, bool]] = {}
        self._ui_count: int = 0
        self._header_count: int = 0
        self._lock = threading.Lock()

    def acquire(
        self, ticket_id: str, is_ui: bool = False, is_header: bool = False
    ) -> bool:
        """Резервирует билет; повтор идемпотентен и не меняет его класс.

        Классы UI и заголовков взаимоисключающие: совмещение даёт ValueError.
        """
        if is_ui and is_header:
            raise ValueError("a ticket cannot be both UI and header")
        with self._lock:
            if ticket_id in self._tickets:
                return True
            ui_reserved = (
                0 if is_ui else max(0, self._config.ui_reserve - self._ui_count)
            )
            header_reserved = (
                0
                if is_header
                else max(0, self._config.header_headroom - self._header_count)
            )
            limit = self._config.admission_limit - ui_reserved - header_reserved
            if len(self._tickets) >= limit:
                return False
            counts = self._ui_count, self._header_count
            committed = False
            try:
                self._tickets[ticket_id] = (is_ui, is_header)
                self._ui_count += int(is_ui)
                self._header_count += int(is_header)
                committed = True
                return True
            finally:
                if not committed:
                    self._tickets.pop(ticket_id, None)
                    self._ui_count, self._header_count = counts

    def release(self, ticket_id: str) -> None:
        """Освобождает билет ровно раз; with гарантирует unlock при исключении."""
        with self._lock:
            flags = self._tickets.pop(ticket_id, None)
            if flags is not None:
                self._ui_count -= int(flags[0])
                self._header_count -= int(flags[1])
