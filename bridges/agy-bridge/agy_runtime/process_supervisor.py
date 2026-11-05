"""Управление изолированными процессами и их процессными группами."""

from __future__ import annotations

import math
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProcessSupervisorConfig:
    """Настройки ожидания завершения процессов в секундах."""

    kill_term_grace_s: float = 0.5
    kill_wait_s: float = 1.0
    stream_read_timeout_s: float = 30.0
    poll_interval_s: float = 0.01

    def __post_init__(self) -> None:
        """Проверяет конечность и допустимость интервалов."""
        for name, value in vars(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Недопустимое значение {name}: {value}")
        if self.poll_interval_s == 0:
            raise ValueError("Интервал опроса должен быть положительным")


class ProcessSupervisor:
    """Запускает процессы в отдельных сессиях и завершает их группы."""

    def __init__(self, config: ProcessSupervisorConfig | None = None) -> None:
        self.config: ProcessSupervisorConfig = config or ProcessSupervisorConfig()

    def group_alive(self, pgid: int) -> bool:
        """Проверяет существование группы, учитывая ограничения доступа."""
        if pgid <= 0:
            return False
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    @staticmethod
    def _signal_group(pgid: int, sig: signal.Signals) -> None:
        """Посылает сигнал группе, допуская ее одновременное исчезновение."""
        if pgid <= 0 or pgid == os.getpgrp():
            raise ValueError("Нельзя завершать собственную или некорректную группу")
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def kill_group(
        self, proc: subprocess.Popen[Any], grace_s: float | None = None
    ) -> None:
        """Завершает группу через TERM/KILL и обязательно забирает лидера."""
        grace = self.config.kill_term_grace_s if grace_s is None else grace_s
        try:
            if not math.isfinite(grace) or grace < 0:
                raise ValueError("Период мягкого завершения должен быть конечным")
            self._signal_group(proc.pid, signal.SIGTERM)
            deadline = time.monotonic() + grace
            while self.group_alive(proc.pid):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(self.config.poll_interval_s, remaining))
            if self.group_alive(proc.pid):
                self._signal_group(proc.pid, signal.SIGKILL)
        finally:
            try:
                proc.wait(timeout=self.config.kill_wait_s)
            except subprocess.TimeoutExpired:
                # Зависший в ядре процесс невозможно гарантированно забрать вовремя.
                pass

    def kill_all(self, procs: list[subprocess.Popen[Any]]) -> None:
        """Обрабатывает все процессы, затем сообщает о первой ошибке."""
        error: Exception | None = None
        for proc in procs:
            try:
                self.kill_group(proc)
            except Exception as exc:
                if error is None:
                    error = exc
        if error is not None:
            raise error

    def spawn(self, cmd: list[str] | str, **kwargs: Any) -> subprocess.Popen[Any]:
        """Запускает команду исключительно в новой сессии."""
        kwargs["start_new_session"] = True
        return subprocess.Popen(cmd, **kwargs)


_default = ProcessSupervisor()
group_alive = _default.group_alive
kill_group = _default.kill_group
kill_all = _default.kill_all
spawn = _default.spawn
