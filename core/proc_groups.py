"""Завершение процессных групп потомков параллельно и с ограниченным бюджетом.

Вынесено из `core/subbridge_lifecycle.py`: порядок `SIGTERM -> общий grace -> SIGKILL`
для всех групп разом (`<= term_grace_s + kill_wait_s` независимо от их числа). Лидеров
собирает `poll()` только ПОСЛЕ сигналов (до этого зомби держит PID в ядре), поэтому читатель
`proc.wait()` получает настоящий `returncode` (`-15`/`-9`), а PID не может уйти чужой группе.
"""

from __future__ import annotations

import contextlib
import math
import os
import signal
import subprocess
import threading
import time
from typing import Any


def _env_seconds(name: str, default: float, low: float) -> float:
    """Читает секунды из окружения; мусор и значения ниже пола дают дефолт (без констант в коде)."""
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if math.isfinite(value) and value >= low else default


_LIVE_PROCS: dict[int, Any] = {}
_LIVE_LOCK = threading.Lock()
_spawn_blocked = False


def _group_alive(pgid: int) -> bool:
    """Есть ли в группе живые члены; на macOS группа из одного зомби-лидера даёт `EPERM` (= мертва)."""
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return True
    return True


def _kill_group(pgid: int, sig: signal.Signals = signal.SIGKILL) -> None:
    with contextlib.suppress(OSError):
        os.killpg(pgid, sig)


def _prune_finished() -> None:
    """Реестр хранит только живых несобранных лидеров; вызывать только под `_LIVE_LOCK`.

    Собранный кем-то лидер (`returncode is not None`) выбывает без сигналов: его PID свободен
    и мог быть переиспользован. Лидер, завершившийся только что (его собрал `poll()` здесь),
    выбывает вместе с осиротевшими потомками своей группы: до освобождения PID группа занята.
    """
    for pid, proc in list(_LIVE_PROCS.items()):
        if proc.returncode is not None:
            del _LIVE_PROCS[pid]
        elif proc.poll() is not None:
            del _LIVE_PROCS[pid]
            if _group_alive(pid):
                _kill_group(pid)


def _register_locked(proc: Any) -> Any:
    _prune_finished()
    _LIVE_PROCS[proc.pid] = proc
    return proc


def register_proc_group(proc: Any) -> Any:
    """Регистрирует группу потомка: остановка гасит её напрямую, без сканирования `ps`."""
    with _LIVE_LOCK:
        return _register_locked(proc)


def live_proc_groups() -> list[Any]:
    """Живые несобранные лидеры; завершившиеся выбывают при чтении (вместе с сиротами)."""
    with _LIVE_LOCK:
        _prune_finished()
        return list(_LIVE_PROCS.values())


def reset_proc_groups() -> None:
    """Очищает реестр (границы тестов и повторный запуск в одном процессе)."""
    with _LIVE_LOCK:
        _LIVE_PROCS.clear()


def _set_spawn_blocked(blocked: bool) -> None:
    global _spawn_blocked
    with (
        _LIVE_LOCK
    ):  # после возврата ни один `spawn_registered` не «в полёте» без регистрации
        _spawn_blocked = bool(blocked)


def spawn_registered(*args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
    """Запускает потомка лидером новой сессии (`pgid == pid`) и регистрирует его атомарно.

    При остановке (`spawn_registered.set_blocked(True)`) новые потомки отклоняются: запрос,
    проснувшийся после снимка зачистки, не сможет породить процесс, который никто не погасит.
    """
    kwargs.setdefault("start_new_session", True)
    with _LIVE_LOCK:
        if _spawn_blocked:
            raise RuntimeError("Subbridge is shutting down; process spawn rejected")
        return _register_locked(subprocess.Popen(*args, **kwargs))


def _wait_groups(procs: list[Any], budget_s: float) -> list[int]:
    """Ждёт общий бюджет, НЕ собирая лидеров (`poll()` запрещён: PID держит зомби). Возвращает живые PGID."""
    end = time.monotonic() + budget_s
    poll_s = _env_seconds(
        "BRIDGE_KILL_POLL_INTERVAL_S", 0.05, 0.005
    )  # шаг опроса живости групп
    while True:
        alive = [p.pid for p in procs if _group_alive(p.pid)]
        if not alive or time.monotonic() >= end:
            return alive
        time.sleep(poll_s)


def _reap(proc: Any, wait_s: float = 0.0) -> None:
    """Собирает лидера только после сигналов и выводит его из реестра.

    `wait_s` > 0 дожидается выхода лидера: на macOS умирающий процесс на миг даёт `EPERM`.
    """
    with contextlib.suppress(Exception):
        if wait_s > 0 and hasattr(proc, "wait"):
            _ = proc.wait(timeout=wait_s)
        else:
            _ = proc.poll()
    with _LIVE_LOCK:
        if _LIVE_PROCS.get(getattr(proc, "pid", -1)) is proc:
            del _LIVE_PROCS[proc.pid]


def terminate_proc_groups_parallel(
    procs: list[Any], term_grace_s: float, kill_wait_s: float
) -> None:
    """`SIGTERM` всем группам разом, общий grace, затем `SIGKILL` выжившим: `<= grace + wait`.

    Уже собранный лидер (`returncode is not None`) не сигналится никогда: его PID мог перейти
    чужой группе. Несобранный лидер (даже зомби) держит PID в таблице ядра, поэтому группа
    гасится до `poll()`; лидеров собирает `finally`, и читатель `proc.wait()` видит `-15`/`-9`.
    """
    own, live = os.getpgrp(), []
    for p in filter(None, procs):
        if (
            getattr(p, "returncode", None) is None
            and p.pid > 1
            and p.pid != own
            and _group_alive(p.pid)
        ):
            live.append(p)
        else:
            _reap(p)  # собран (PID чужой) либо группа мертва (остался зомби-лидер)
    try:
        for p in live:
            _kill_group(p.pid, signal.SIGTERM)
        survivors = _wait_groups(live, term_grace_s)
        for pgid in survivors:
            _kill_group(pgid, signal.SIGKILL)
        if survivors:
            _wait_groups(live, kill_wait_s)
    finally:
        for p in live:
            _reap(p, kill_wait_s)


def _unregister_proc_group(proc: Any) -> None:
    """Снимает `proc` с учёта; несобранного лидера (и его группу) гасит и собирает."""
    with _LIVE_LOCK:
        if _LIVE_PROCS.get(proc.pid) is proc:
            del _LIVE_PROCS[proc.pid]
    if proc.returncode is None:
        grace = _env_seconds("BRIDGE_KILL_TERM_GRACE_S", 2.0, 0.0)
        terminate_proc_groups_parallel(
            [proc], grace, _env_seconds("BRIDGE_KILL_WAIT_S", 3.0, 0.0)
        )


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
            timeout=_env_seconds(
                "BRIDGE_PROCESS_PROBE_TIMEOUT_S", 2.0, 0.1
            ),  # бюджет `ps`
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows = [line.split() for line in out.splitlines()]
    me = str(os.getpid())
    return [
        _ChildGroup(int(pid))
        for pid, ppid, pgid in (
            r for r in rows if len(r) == 3 and all(x.isdigit() for x in r)
        )
        if ppid == me and pgid == pid and int(pid) > 1
    ]


for _name, _fn in (
    ("set_blocked", _set_spawn_blocked),
    ("unregister", _unregister_proc_group),
):
    setattr(
        spawn_registered, _name, _fn
    )  # атрибуты функции: публичных символов остаётся шесть
