"""Завершение процессных групп потомков параллельно и с ограниченным бюджетом.

Вынесено из `core/subbridge_lifecycle.py`: порядок `SIGTERM -> общий grace -> SIGKILL`
для всех групп разом (`<= term_grace_s + kill_wait_s` независимо от их числа). Лидеров
забирает `poll()`, поэтому читатель вывода, ждущий `proc.wait()`, получает настоящий
`returncode` (`-15`/`-9`), а не ложный успех.
"""

from __future__ import annotations

import math
import os
import signal
import subprocess
import threading
import time
from typing import Any

_KILL_POLL_INTERVAL_ENV = "BRIDGE_KILL_POLL_INTERVAL_S"
_PROCESS_PROBE_TIMEOUT_ENV = "BRIDGE_PROCESS_PROBE_TIMEOUT_S"


def _env_seconds(name: str, default: float, low: float) -> float:
    """Читает секунды из окружения; мусор и значения ниже пола дают дефолт (без констант в коде)."""
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if math.isfinite(value) and value >= low else default


_LIVE_PROCS: dict[int, Any] = {}
_LIVE_LOCK = threading.Lock()


def _prune_finished() -> None:
    """Выбрасывает завершённых лидеров; вызывать только под `_LIVE_LOCK`."""
    for pid, proc in list(_LIVE_PROCS.items()):
        if proc.poll() is not None:
            _ = _LIVE_PROCS.pop(pid, None)


def register_proc_group(proc: Any) -> Any:
    """Регистрирует группу потомка: остановка гасит её напрямую, без сканирования `ps`.

    Завершённые лидеры вычищаются при каждой регистрации: в долгоживущем мосте реестр
    не растёт и не удерживает закрытые `Popen`, даже если `live_proc_groups` не зовут.
    """
    with _LIVE_LOCK:
        _prune_finished()
        _LIVE_PROCS[proc.pid] = proc
    return proc


def live_proc_groups() -> list[Any]:
    """Живые группы зарегистрированных потомков; завершённые лидеры выбывают при чтении."""
    with _LIVE_LOCK:
        _prune_finished()
        return list(_LIVE_PROCS.values())


def reset_proc_groups() -> None:
    """Очищает реестр (границы тестов и повторный запуск в одном процессе)."""
    with _LIVE_LOCK:
        _LIVE_PROCS.clear()


def spawn_registered(*args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
    """Запускает потомка и сразу регистрирует его группу: мосту не нужен отдельный вызов."""
    return register_proc_group(subprocess.Popen(*args, **kwargs))


def _kill_poll_interval_s() -> float:
    """Шаг опроса живости групп при зачистке (`BRIDGE_KILL_POLL_INTERVAL_S`, по умолчанию 0.05 с)."""
    return _env_seconds(_KILL_POLL_INTERVAL_ENV, 0.05, 0.005)


def _process_probe_timeout_s() -> float:
    """Бюджет `ps` при поиске групп потомков (`BRIDGE_PROCESS_PROBE_TIMEOUT_S`, по умолчанию 2.0 с)."""
    return _env_seconds(_PROCESS_PROBE_TIMEOUT_ENV, 2.0, 0.1)


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _wait_groups(procs: list[Any], budget_s: float) -> list[int]:
    """Ждёт общий бюджет; лидеров забирает `poll()`. Возвращает PGID ещё живых групп."""
    end = time.monotonic() + budget_s
    poll_s = _kill_poll_interval_s()
    while True:
        alive = [p.pid for p in procs if p.poll() is None or _group_alive(p.pid)]
        if not alive or time.monotonic() >= end:
            return alive
        time.sleep(poll_s)


def terminate_proc_groups_parallel(
    procs: list[Any], term_grace_s: float, kill_wait_s: float
) -> None:
    """`SIGTERM` всем группам разом, общий grace, затем `SIGKILL` выжившим: `<= grace + wait`."""
    own = os.getpgrp()
    owned = [p for p in procs if p.pid > 1 and p.pid != own]

    def send(pgids: list[int], sig: signal.Signals) -> None:
        for pgid in pgids:
            try:
                os.killpg(pgid, sig)
            except OSError:
                continue

    send([p.pid for p in owned], signal.SIGTERM)
    survivors = _wait_groups(owned, term_grace_s)
    if survivors:
        send(survivors, signal.SIGKILL)
        _wait_groups(owned, kill_wait_s)


class _ChildGroup:
    """Группа прямого потомка без `Popen`: `poll()` — `None`, пока жива хоть одна группа."""

    def __init__(self, pid: int) -> None:
        self.pid = pid

    def poll(self) -> int | None:
        return None if _group_alive(self.pid) else 0


def child_process_groups() -> list[_ChildGroup]:
    """Группы-лидеры (`start_new_session`) прямых потомков этого процесса, когда реестра `Popen` нет."""
    try:
        out = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid=,pgid="],
            capture_output=True,
            text=True,
            timeout=_process_probe_timeout_s(),
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows = [line.split() for line in out.splitlines()]
    triples = [
        tuple(map(int, r)) for r in rows if len(r) == 3 and all(x.isdigit() for x in r)
    ]
    return [
        _ChildGroup(pid)
        for pid, ppid, pgid in triples
        if ppid == os.getpid() and pgid == pid > 1
    ]
