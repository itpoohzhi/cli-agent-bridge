"""Настройка принятых сокетов и потокобезопасный admission без сетевого I/O."""

from __future__ import annotations

import socket
from typing import Any, cast

from core.bridge_io_config import (
    AdmissionBudget as AdmissionBudget,
    BridgeIOConfig,
    load_bridge_io_config,
)


# Any задан контрактом транспортной границы; внутри тип ограничен сокетом.
def configure_accepted_socket(
    sock: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    config: BridgeIOConfig | None = None,
) -> None:
    """Настраивает TCP и общий timeout; неподдерживаемые опции допустимы."""
    if sock is None:
        return
    settings = load_bridge_io_config() if config is None else config
    connection = cast(socket.socket, sock)
    options = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
    if settings.tcp_nodelay:
        options.append((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1))
    for level, option, value in options:
        try:
            connection.setsockopt(level, option, value)
        except (AttributeError, OSError, NotImplementedError):
            continue
    # У Python-сокета один timeout для чтения и записи: соблюдаем оба потолка.
    timeouts = [
        value
        for value in (settings.read_timeout_s, settings.write_timeout_s)
        if value is not None
    ]
    try:
        if timeouts:
            connection.settimeout(min(timeouts))
    except (AttributeError, OSError, NotImplementedError):
        return
