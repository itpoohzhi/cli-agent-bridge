"""Настройка принятых сокетов, phase-idle admission и потокобезопасный учёт соединений.

Runtime-слой поверх чистой политики core.admission_idle_policy: свежее чтение
env/dynamic_config (fail-closed default=False), применение фазовых таймаутов,
трекер active/idle, прежний JSON 503 и telemetry-хуки. Сетевого I/O здесь нет.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from core.admission_idle_policy import (
    ADMISSION_TELEMETRY_FLAG,
    CLAUDE_STDERR_FLAG,
    PHASE_IDLE_FLAG,
    TTL_SWEEP_FLAG,
    AdmissionIdleConfig,
    check_legacy_max_http_connections_warning,
    resolve_socket_timeout_for_phase,
    summarize_admission_snapshot,
)
from core.bridge_io_config import (
    AdmissionBudget as AdmissionBudget,
    BridgeIOConfig,
    load_bridge_io_config,
)
from core.recovery_flags import (
    CONFIG_PATH_ENV,
    DEFAULT_CONFIG_PATH,
    load_config,
    read_number,
    read_recovery_switch,
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
    # Таймаут сокета ограничивает только готовность к чтению: не зажимаем
    # его коротким write-таймаутом, иначе длинный SSE-стрим обрывается.
    try:
        if settings.read_timeout_s is not None:
            connection.settimeout(settings.read_timeout_s)
    except (AttributeError, OSError, NotImplementedError):
        return


def load_admission_idle_config(
    env: Mapping[str, str] | None = None,
    config_path: Path | None = None,
) -> AdmissionIdleConfig:
    """Свежее чтение флагов/чисел (env + dynamic_config); fail-closed default=False."""
    values = os.environ if env is None else env
    path = config_path or Path(
        values.get(CONFIG_PATH_ENV, "").strip()
        or os.path.expanduser(DEFAULT_CONFIG_PATH)
    )
    loaded = load_config(path)
    config = loaded if isinstance(loaded, dict) else None

    def number(key: str, default: float, bounds: tuple[float, float]) -> float:
        return read_number(key, default, bounds, values, config)

    def switch(flag: str) -> bool:
        return read_recovery_switch(flag, env=values, config_path=config_path)

    return AdmissionIdleConfig(
        phase_idle_timeout_enabled=switch(PHASE_IDLE_FLAG),
        active_ttl_sweep_enabled=switch(TTL_SWEEP_FLAG),
        admission_telemetry_enabled=switch(ADMISSION_TELEMETRY_FLAG),
        claude_stderr_log_enabled=switch(CLAUDE_STDERR_FLAG),
        phase_idle_timeout_s=number(
            "BRIDGE_HTTP_PHASE_IDLE_TIMEOUT_S", 30.0, (0.02, 3600.0)
        ),
        active_socket_timeout_s=number(
            "BRIDGE_HTTP_ACTIVE_SOCKET_TIMEOUT_S", 3600.0, (1.0, 86400.0)
        ),
        claude_stderr_max_chars=int(
            number("BRIDGE_CLAUDE_P_STDERR_LOG_MAX_CHARS", 240.0, (32.0, 2048.0))
        ),
    )


def _restore_active_timeout(
    sock: socket.socket, settings: AdmissionIdleConfig, io: BridgeIOConfig
) -> float | None:
    """Мгновенный возврат legacy-таймаута при выключенном kill-switch (active)."""
    target = (
        settings.active_socket_timeout_s
        if io.read_timeout_s is None
        else io.read_timeout_s
    )
    applied: float | None = None
    try:
        current = sock.gettimeout()
        if current is not None and current < target:
            sock.settimeout(target)
            applied = target
    except (AttributeError, OSError, NotImplementedError):
        applied = None
    return applied


def apply_connection_phase_timeout(
    sock: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    phase: str,
    cfg: AdmissionIdleConfig | None = None,
    io_config: BridgeIOConfig | None = None,
) -> float | None:
    """Фазовый таймаут; выключенный флаг — no-op либо мгновенный возврат active."""
    if sock is None:
        return None
    settings = load_admission_idle_config() if cfg is None else cfg
    io = load_bridge_io_config() if io_config is None else io_config
    conn = cast(socket.socket, sock)
    if not settings.phase_idle_timeout_enabled:
        return (
            _restore_active_timeout(conn, settings, io) if phase == "active" else None
        )
    timeout = resolve_socket_timeout_for_phase(phase, settings, io.read_timeout_s)
    applied: float | None = timeout
    try:
        conn.settimeout(timeout)
    except (AttributeError, OSError, NotImplementedError):
        applied = None
    return applied


class ConnectionTracker:
    """Потокобезопасный учёт соединений (active/idle) с временем смены фазы.

    Совместим с прежним dict-контрактом: `request in tracker` и as_bool_map().
    Закрывает только idle-сокеты при drain; активные завершаются своими потоками.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: dict[socket.socket, tuple[bool, float]] = {}
        self._closing = False
        self._overloaded_rejects = 0

    def record_overload_reject(self) -> int:
        """Атомарный инкремент счётчика overload-reject; возвращает новое значение."""
        with self._lock:
            self._overloaded_rejects += 1
            return self._overloaded_rejects

    @property
    def overloaded_rejects(self) -> int:
        """Число overload-reject под lock (совместимо с прежним чтением атрибута)."""
        with self._lock:
            return self._overloaded_rejects

    def __contains__(self, sock: object) -> bool:
        with self._lock:
            return sock in self._connections

    def register(self, sock: socket.socket) -> None:
        """Регистрирует принятое соединение как idle с текущим monotonic-временем."""
        with self._lock:
            self._connections[sock] = (False, time.monotonic())

    def set_active(self, sock: socket.socket, active: bool) -> bool:
        """Атомарно меняет фазу; при закрытии (drain) возвращает False."""
        with self._lock:
            if self._closing:
                return False
            self._connections[sock] = (active, time.monotonic())
            return True

    def remove(self, sock: socket.socket) -> None:
        """Удаляет соединение из учёта (идемпотентно)."""
        with self._lock:
            self._connections.pop(sock, None)

    def close_idle(self) -> None:
        """Будит только idle-читателей shutdown; активные ответы не трогает."""
        with self._lock:
            self._closing = True
            idle = [
                sock for sock, (active, _) in self._connections.items() if not active
            ]
        for sock in idle:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def snapshot(
        self, limit: int, overloaded_rejects: int | None = None
    ) -> dict[str, int | float]:
        """Снимок admission для телеметрии (копия и счётчик под одним lock)."""
        with self._lock:
            conns = dict(self._connections)
            rej = self._overloaded_rejects
            rejects = rej if overloaded_rejects is None else overloaded_rejects
        return summarize_admission_snapshot(
            cast("Mapping[object, tuple[bool, float]]", conns),
            time.monotonic(),
            limit,
            rejects,
        )

    def as_bool_map(self) -> dict[socket.socket, bool]:
        """Совместимое представление active-флагов (без возрастов)."""
        with self._lock:
            return {sock: active for sock, (active, _) in self._connections.items()}


# Статический wire-ответ 503 (тело 96 байт, побайтово прежний json.dumps).
_OVERLOAD_503_WIRE = (
    b"HTTP/1.1 503 Service Unavailable\r\n"
    b"Content-Type: application/json; charset=utf-8\r\n"
    b"Content-Length: 96\r\n"
    b"Connection: close\r\n\r\n"
    b'{"error": {"message": "bridge overloaded: connection limit",'
    b' "type": "overloaded", "code": 503}}'
)


def send_overloaded_503(
    request: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    client_address: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    log_fn: Callable[[str], None],
    tracker: ConnectionTracker,
    budget: AdmissionBudget,
) -> None:
    """Прежний JSON 503 connection limit + лог reject; telemetry-поля при флаге."""
    rejects = tracker.record_overload_reject()
    try:
        peer = f"{client_address[0]}:{client_address[1]}"
    except (TypeError, IndexError):
        peer = "unknown"
    line = f"reject reason=overloaded model=unknown model_len=0 client={peer}"
    if load_admission_idle_config().admission_telemetry_enabled:
        snap = tracker.snapshot(budget.limit, rejects)
        line += (
            f" active={snap['active']} idle={snap['idle']} total={snap['total']}"
            f" limit={snap['limit']} max_idle_age_s={snap['max_idle_age_s']}"
        )
    log_fn(line)
    try:
        if isinstance(request, socket.socket):
            request.sendall(_OVERLOAD_503_WIRE)
    except OSError:
        pass


def emit_legacy_knob_warning(
    log_fn: Callable[[str], None],
    effective_limit: int,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Логирует предупреждение о мёртвом BRIDGE_MAX_HTTP_CONNECTIONS; True если выдано."""
    warning = check_legacy_max_http_connections_warning(
        os.environ if env is None else env, effective_limit
    )
    if warning:
        log_fn(warning)
    return bool(warning)


def attach_admission_telemetry(
    payload: dict[str, Any],
    server: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Добавляет блок admission только при включённом флаге и наличии снимка у server."""
    snapshot = getattr(server, "admission_snapshot", None)
    enabled = load_admission_idle_config(env).admission_telemetry_enabled
    return (
        {**payload, "admission": snapshot()}
        if (enabled and callable(snapshot))
        else payload
    )
