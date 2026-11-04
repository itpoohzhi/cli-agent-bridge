"""Потокобезопасное завершение процессов, групп и потоков запуска."""

from __future__ import annotations

import math
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol


class _Closable(Protocol):
    """Поток, поддерживающий закрытие."""

    def close(self) -> object:
        """Закрывает поток."""
        ...


class _Run(Protocol):
    """Минимальное состояние запуска, необходимое для зачистки."""

    proc: subprocess.Popen[Any]
    dead_confirmed: bool


@dataclass(frozen=True)
class ProcessSupervisorConfig:
    """Ограничения ожиданий и длительности карантина в секундах."""

    kill_term_grace_s: float = 0.5
    kill_wait_s: float = 5.0
    group_exit_wait_s: float = 2.0
    quarantine_max_s: float = 60.0
    poll_interval_s: float = 0.01

    def __post_init__(self) -> None:
        """Проверяет конечность и допустимость интервалов."""
        for name, value in vars(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Недопустимое значение {name}: {value}")
        if self.poll_interval_s == 0:
            raise ValueError("Интервал опроса должен быть положительным")


class ProcessSupervisor:
    """Изолирует процессы и сериализует подтверждение их смерти."""

    def __init__(self, config: ProcessSupervisorConfig | None = None) -> None:
        self.config: ProcessSupervisorConfig = config or ProcessSupervisorConfig()
        self._lock: threading.RLock = threading.RLock()

    def group_alive(self, pgid: int) -> bool:
        """Консервативно проверяет существование процессной группы."""
        if pgid <= 0:
            return False
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def kill_group(self, proc: subprocess.Popen[Any]) -> None:
        """Убить всю группу процессов хода: SIGKILL с fallback proc.kill()."""
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.kill()
            except OSError:
                pass

    def wait_group_exit(
        self,
        pgid: int,
        timeout: float | None = None,
        leader_reaped: bool = False,
    ) -> bool:
        """Ожидает исчезновения группы; после реапа лидера killpg шлется единожды."""
        duration = self.config.group_exit_wait_s if timeout is None else timeout
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("Ожидание должно быть конечным и неотрицательным")
        deadline = time.monotonic() + duration
        control_sent = False
        while self.group_alive(pgid) and time.monotonic() < deadline:
            if not (leader_reaped and control_sent):
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass
                control_sent = True
            time.sleep(min(self.config.poll_interval_s, max(0.01, deadline - time.monotonic())))
        return not self.group_alive(pgid)

    def terminate_run(
        self,
        run: Any,
        streams: tuple[Any, ...] = (),
        kill_group_fn: Any = None,
    ) -> None:
        """Убить группу хода и подтвердить её смерть; результат — run.dead_confirmed."""
        proc = getattr(run, "proc", None)
        if proc is None:
            return
        cleanup_lock = getattr(run, "_cleanup_lock", self._lock)
        with cleanup_lock:
            if getattr(run, "_closed", False):
                return
            setattr(run, "_closed", True)
            setattr(run, "dead_confirmed", False)
            killer = kill_group_fn or self.kill_group
            killer(proc)
            try:
                proc.wait(timeout=self.config.kill_wait_s)
            except subprocess.TimeoutExpired:
                killer(proc)
                try:
                    proc.wait(timeout=self.config.kill_wait_s)
                except subprocess.TimeoutExpired:
                    pass
            run.dead_confirmed = self.wait_group_exit(
                proc.pid,
                timeout=self.config.group_exit_wait_s,
                leader_reaped=proc.poll() is not None,
            )
            if not run.dead_confirmed:
                return
            for stream in streams:
                try:
                    if stream is not None:
                        stream.close()
                except OSError:
                    pass

    def spawn(self, cmd: list[str] | str, **kwargs: Any) -> subprocess.Popen[Any]:
        """Запускает команду исключительно в новой сессии."""
        kwargs["start_new_session"] = True
        return subprocess.Popen(cmd, **kwargs)


_default = ProcessSupervisor()
group_alive = _default.group_alive
kill_group = _default.kill_group
wait_group_exit = _default.wait_group_exit
terminate_run = _default.terminate_run
spawn = _default.spawn
