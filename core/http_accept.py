"""Настройка принятых сокетов и потокобезопасный admission без сетевого I/O."""

from __future__ import annotations

import socket
from threading import Lock
from typing import Any, cast

from core.bridge_io_config import BridgeIOConfig, load_bridge_io_config


# Any задан контрактом транспортной границы; внутри тип ограничен сокетом.
def configure_accepted_socket(
    sock: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    config: BridgeIOConfig | None = None,
) -> None:
    """Включает TCP_NODELAY; отсутствующий или неподдерживаемый сокет допустим."""
    if sock is None:
        return
    settings = load_bridge_io_config() if config is None else config
    if not settings.tcp_nodelay:
        return
    try:
        cast(socket.socket, sock).setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except (AttributeError, OSError, NotImplementedError):
        return


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
        self._lock: Lock = Lock()

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
            self._tickets[ticket_id] = (is_ui, is_header)
            self._ui_count += int(is_ui)
            self._header_count += int(is_header)
            return True

    def release(self, ticket_id: str) -> None:
        """Освобождает билет ровно раз; неизвестный билет не меняет бюджет."""
        with self._lock:
            flags = self._tickets.pop(ticket_id, None)
            if flags is not None:
                self._ui_count -= int(flags[0])
                self._header_count -= int(flags[1])
