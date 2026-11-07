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
_LIVE_LOCK = threading.RLock()  # `spawn_registered` регистрирует под тем же замком
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


def _prune_finished() -> list[Any]:
    """Выбрасывает собранных лидеров; вызывать под `_LIVE_LOCK`. Только чтение `returncode`.

    `poll()`/`waitpid` здесь запрещены: они гонятся с `proc.wait()`/`communicate()` рабочего
    потока (при `ECHILD` CPython выставляет `returncode = 0`) и собирают лидера до сигнала группе.
    """
    for pid, proc in list(_LIVE_PROCS.items()):
        if proc.returncode is not None:
            del _LIVE_PROCS[pid]
    return list(_LIVE_PROCS.values())


def register_proc_group(proc: Any) -> Any:
    """Регистрирует группу потомка: остановка гасит её напрямую, без сканирования `ps`."""
    with _LIVE_LOCK:
        _prune_finished()
        _LIVE_PROCS[proc.pid] = proc
    return proc


def live_proc_groups() -> list[Any]:
    """Несобранные лидеры; собранные выбывают при чтении."""
    with _LIVE_LOCK:
        return _prune_finished()


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
        return register_proc_group(subprocess.Popen(*args, **kwargs))


def _wait_groups(procs: list[Any], budget_s: float) -> list[Any]:
    """Ждёт общий бюджет без `poll()`; возвращает процессы, чья группа жива и лидер не собран.

    Собранный лидер освободил PID: такой группе сигнал слать нельзя (PID мог уйти чужой группе).
    """
    end = time.monotonic() + budget_s
    poll_s = _env_seconds("BRIDGE_KILL_POLL_INTERVAL_S", 0.05, 0.005)
    while True:
        alive = [p for p in procs if p.returncode is None and _group_alive(p.pid)]
        if not alive or time.monotonic() >= end:
            return alive
        time.sleep(poll_s)


def _reap(proc: Any, wait_s: float) -> None:
    """Дожидается лидера в пределах `wait_s`; из реестра выводит только собранного."""
    with contextlib.suppress(Exception):
        if proc.returncode is None:
            _ = proc.wait(timeout=max(0.0, wait_s))
    if proc.returncode is not None:
        with _LIVE_LOCK:
            _ = _LIVE_PROCS.pop(proc.pid, None)


def terminate_proc_groups_parallel(
    procs: list[Any], term_grace_s: float, kill_wait_s: float
) -> None:
    """`SIGTERM` всем группам разом, общий grace, затем `SIGKILL`: `<= term_grace_s + kill_wait_s`.

    Собранный лидер (`returncode is not None`) не сигналится никогда. Несобранный (даже зомби)
    держит PID в ядре, поэтому группа гасится до сбора. `SIGKILL`-ожидание и сбор лидеров
    в `finally` делят ОДИН дедлайн `kill_wait_s`, а не `kill_wait_s` на каждый процесс.
    """
    own, live = os.getpgrp(), []
    for p in filter(None, procs):
        if p.returncode is None and p.pid > 1 and p.pid != own and _group_alive(p.pid):
            live.append(p)
        else:
            _reap(p, 0.0)  # собран (PID чужой) либо группа мертва (зомби-лидер)
    reap_end = time.monotonic() + max(0.0, kill_wait_s)
    try:
        for p in live:
            _kill_group(p.pid, signal.SIGTERM)
        survivors = _wait_groups(live, term_grace_s)
        reap_end = time.monotonic() + max(0.0, kill_wait_s)
        for p in survivors:
            if p.returncode is None:  # мог быть собран рабочим потоком после SIGTERM
                _kill_group(p.pid, signal.SIGKILL)
        if survivors:
            _wait_groups(survivors, max(0.0, reap_end - time.monotonic()))
    finally:
        for p in live:
            _reap(p, reap_end - time.monotonic())


def _unregister_proc_group(proc: Any) -> None:
    """Вызывается рабочим потоком по завершении хода: гасит остатки группы и снимает `proc` с учёта."""
    grace = _env_seconds("BRIDGE_UNREGISTER_GRACE_S", 0.2, 0.0)
    if proc.returncode is None and _group_alive(proc.pid):
        for sig in (signal.SIGTERM, signal.SIGKILL):
            _kill_group(proc.pid, sig)
            if not _wait_groups([proc], grace):
                break
    _reap(proc, grace)
    with (
        _LIVE_LOCK
    ):  # лидера мог собрать `communicate()` этого же хода: запись всё равно снимается
        _ = _LIVE_PROCS.pop(proc.pid, None)


class _ChildGroup:
    """Группа прямого потомка без `Popen` (`returncode` всегда `None`: лидера собирает его владелец)."""

    def __init__(self, pid: int) -> None:
        self.pid, self.returncode = pid, None


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
