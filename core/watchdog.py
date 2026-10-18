"""Адаптивный таймер неактивности и мониторинг дерева процессов (ADR-0005 / AD-002).

Модуль реализует двухконтурный контроль времени хода исключительно средствами
стандартной библиотеки Python на macOS (Darwin):
1. Контур активности (`IDLE_TIMEOUT_S = 300.0` с): таймер неактивности сбрасывается
   только при наличии реального прогресса — протокольных событий от CLI (`on_activity`),
   положительного прироста процессорного времени (`cputime` delta > 0) в группе `pgid`,
   или появления новых дочерних PID (`new_descendants`). Спящий дочерний процесс
   без прироста CPU и без новых потомков таймер не сбрасывает (RW-005).
2. Предохранительный потолок (`SAFETY_CAP_S = 3600.0` с, `FINISH_RESERVE_S = 35.0` с):
   абсолютный потолок длительности хода независимо от активности.

При деградации/таймауте вызова `ps` применяется политика fail-closed: событие
фиксируется в логе (`watchdog_ps_degraded`), а `last_activity_ts` не обновляется.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
import re
import subprocess
import threading
import time

IDLE_TIMEOUT_S: float = 300.0
SAFETY_CAP_S: float = 3600.0
FINISH_RESERVE_S: float = 35.0
WATCHDOG_INTERVAL_S: float = 5.0
PS_TIMEOUT_S: float = 2.0

DEFAULT_IDLE_TIMEOUT_S: float = IDLE_TIMEOUT_S
DEFAULT_SAFETY_CAP_S: float = SAFETY_CAP_S
DEFAULT_FINISH_RESERVE_S: float = FINISH_RESERVE_S


_PS_LINE_RE = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s*(.*)$"
)


def parse_cputime(raw: str) -> float:
    """Разбирает поле `cputime` вывода `ps` (`[[dd-]hh:]mm:ss[.xx]`) в секунды."""
    token = (raw or "").strip()
    if not token:
        return 0.0
    days = 0
    if "-" in token:
        day_part, token = token.split("-", 1)
        try:
            days = int(day_part)
        except ValueError:
            return 0.0
    parts = token.split(":")
    try:
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
        elif len(parts) == 2:
            hours = 0
            minutes = int(parts[0])
            seconds = float(parts[1])
        elif len(parts) == 1:
            hours = 0
            minutes = 0
            seconds = float(parts[0])
        else:
            return 0.0
    except ValueError:
        return 0.0
    total = ((days * 24 + hours) * 60 + minutes) * 60 + seconds
    return max(0.0, float(total))


@dataclass(frozen=True)
class WatchdogMetrics:
    """Снимок состояния процессной группы `pgid` на одном тике `ProcessWatchdog`."""

    pgid: int
    alive: bool
    descendant_pids: tuple[int, ...]
    new_descendants: tuple[int, ...]
    cpu_time_s: float
    cpu_delta_s: float
    ps_degraded: bool = False
    sample_ts: float = 0.0

    @property
    def has_progress(self) -> bool:
        """Есть ли подтверждённый прогресс (новые потомки или прирост CPU > 0)."""
        if self.ps_degraded or not self.alive:
            return False
        return bool(self.new_descendants) or self.cpu_delta_s > 0.0

    has_activity = has_progress


class ProcessWatchdog:
    """Мониторинг процессной группы `pgid` на macOS/POSIX через `os.killpg` и `ps`."""

    def __init__(
        self,
        ps_timeout_s: float = PS_TIMEOUT_S,
        log_fn: Callable[[str], None] | None = None,
        rid: str = "",
        turn_id: str = "",
    ) -> None:
        self.ps_timeout_s = float(ps_timeout_s)
        self._log_fn = log_fn
        self.rid = rid
        self.turn_id = turn_id
        self._lock = threading.Lock()
        self._prev_cpu_by_pgid: dict[int, dict[int, float]] = {}
        self._seen_descendants_by_pgid: dict[int, set[int]] = {}
        self._seeded_pgids: set[int] = set()

    def _log(self, msg: str) -> None:
        if self._log_fn is not None:
            try:
                self._log_fn(msg)
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def is_group_alive(pgid: int) -> bool:
        """Проверяет живость процессной группы `os.killpg(pgid, 0)`."""
        if not isinstance(pgid, int) or pgid <= 0:
            return False
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def forget(self, pgid: int) -> None:
        """Очищает накопленное состояние группы после завершения хода."""
        with self._lock:
            self._prev_cpu_by_pgid.pop(pgid, None)
            self._seen_descendants_by_pgid.pop(pgid, None)
            self._seeded_pgids.discard(pgid)

    def _run_ps(self, pgid: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["ps", "-o", "pid=,ppid=,pgid=,stat=,cputime=,command=", "-g", str(pgid)],
            capture_output=True,
            text=True,
            timeout=self.ps_timeout_s,
            check=False,
        )

    def _parse_ps_output(
        self, stdout: str, target_pgid: int
    ) -> tuple[list[int], dict[int, float], bool]:
        """Возвращает `(descendant_pids, cpu_by_pid, any_non_zombie_in_group)`."""
        descendants: list[int] = []
        cpu_by_pid: dict[int, float] = {}
        any_alive_proc = False
        for raw_line in (stdout or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = _PS_LINE_RE.match(line)
            if match is None:
                continue
            try:
                pid = int(match.group(1))
                _ppid = int(match.group(2))
                pgid_col = int(match.group(3))
            except ValueError:
                continue
            if pgid_col != target_pgid:
                continue
            stat = match.group(4) or ""
            cputime_str = match.group(5) or ""
            if stat.upper().startswith("Z"):
                continue
            any_alive_proc = True
            cpu_by_pid[pid] = parse_cputime(cputime_str)
            if pid != target_pgid:
                descendants.append(pid)
        descendants.sort()
        return descendants, cpu_by_pid, any_alive_proc

    def seed(
        self, pgid: int, *, rid: str = "", turn_id: str = ""
    ) -> WatchdogMetrics:
        """Фиксирует базовый срез PID и cputime группы при старте хода без сброса таймера."""
        metrics = self.sample(pgid, rid=rid, turn_id=turn_id, _seed_only=True)
        return metrics

    def sample(
        self,
        pgid: int,
        *,
        rid: str = "",
        turn_id: str = "",
        _seed_only: bool = False,
    ) -> WatchdogMetrics:
        """Опрашивает группу `pgid` и вычисляет прирост `cputime` и новых потомков."""
        now = time.monotonic()
        eff_rid = rid or self.rid or "-"
        eff_turn = turn_id or self.turn_id or "-"
        if not self.is_group_alive(pgid):
            return WatchdogMetrics(
                pgid=pgid,
                alive=False,
                descendant_pids=(),
                new_descendants=(),
                cpu_time_s=0.0,
                cpu_delta_s=0.0,
                ps_degraded=False,
                sample_ts=now,
            )

        try:
            proc = self._run_ps(pgid)
        except (subprocess.TimeoutExpired, OSError) as exc:
            if not self.is_group_alive(pgid):
                return WatchdogMetrics(
                    pgid=pgid,
                    alive=False,
                    descendant_pids=(),
                    new_descendants=(),
                    cpu_time_s=0.0,
                    cpu_delta_s=0.0,
                    ps_degraded=False,
                    sample_ts=now,
                )
            self._log(
                f"watchdog_ps_degraded rid={eff_rid} turn_id={eff_turn} "
                f"pgid={pgid} reason={exc.__class__.__name__}"
            )
            return WatchdogMetrics(
                pgid=pgid,
                alive=True,
                descendant_pids=(),
                new_descendants=(),
                cpu_time_s=0.0,
                cpu_delta_s=0.0,
                ps_degraded=True,
                sample_ts=now,
            )

        if proc.returncode != 0:
            if not self.is_group_alive(pgid):
                return WatchdogMetrics(
                    pgid=pgid,
                    alive=False,
                    descendant_pids=(),
                    new_descendants=(),
                    cpu_time_s=0.0,
                    cpu_delta_s=0.0,
                    ps_degraded=False,
                    sample_ts=now,
                )
            self._log(
                f"watchdog_ps_degraded rid={eff_rid} turn_id={eff_turn} "
                f"pgid={pgid} reason=rc_{proc.returncode}"
            )
            return WatchdogMetrics(
                pgid=pgid,
                alive=True,
                descendant_pids=(),
                new_descendants=(),
                cpu_time_s=0.0,
                cpu_delta_s=0.0,
                ps_degraded=True,
                sample_ts=now,
            )

        descendants, cpu_s, any_alive = self._parse_ps_output(proc.stdout, pgid)
        if not any_alive and not self.is_group_alive(pgid):
            return WatchdogMetrics(
                pgid=pgid,
                alive=False,
                descendant_pids=(),
                new_descendants=(),
                cpu_time_s=0.0,
                cpu_delta_s=0.0,
                ps_degraded=False,
                sample_ts=now,
            )

        with self._lock:
            prev_cpu = self._prev_cpu_by_pgid.setdefault(pgid, {})
            seen_desc = self._seen_descendants_by_pgid.setdefault(pgid, set())
            if _seed_only:
                for pid, val in cpu_s.items():
                    prev_cpu[pid] = max(prev_cpu.get(pid, 0.0), val)
                seen_desc.update(descendants)
                self._seeded_pgids.add(pgid)
                total_cpu = sum(cpu_s.values())
                return WatchdogMetrics(
                    pgid=pgid,
                    alive=True,
                    descendant_pids=tuple(descendants),
                    new_descendants=(),
                    cpu_time_s=total_cpu,
                    cpu_delta_s=0.0,
                    ps_degraded=False,
                    sample_ts=now,
                )

            cpu_delta = sum(
                max(0.0, val - prev_cpu.get(pid, 0.0)) for pid, val in cpu_s.items()
            )
            new_desc = tuple(sorted(set(descendants) - seen_desc))
            for pid, val in cpu_s.items():
                prev_cpu[pid] = max(prev_cpu.get(pid, 0.0), val)
            seen_desc.update(descendants)
            self._seeded_pgids.add(pgid)
            total_cpu = sum(cpu_s.values())

        return WatchdogMetrics(
            pgid=pgid,
            alive=True,
            descendant_pids=tuple(descendants),
            new_descendants=new_desc,
            cpu_time_s=total_cpu,
            cpu_delta_s=cpu_delta,
            ps_degraded=False,
            sample_ts=now,
        )


class AdaptiveTimeoutController:
    """Контроллер двухконтурного таймаута хода (`idle_timeout` + `absolute_cap`)."""

    def __init__(
        self,
        idle_timeout_s: float = IDLE_TIMEOUT_S,
        safety_cap_s: float = SAFETY_CAP_S,
        finish_reserve_s: float = FINISH_RESERVE_S,
        watchdog: ProcessWatchdog | None = None,
        watchdog_enabled: bool = True,
        clock: Callable[[], float] = time.monotonic,
        rid: str = "",
        turn_id: str = "",
        log_fn: Callable[[str], None] | None = None,
    ) -> None:
        self.idle_timeout_s = float(idle_timeout_s)
        self.safety_cap_s = float(safety_cap_s)
        self.finish_reserve_s = float(finish_reserve_s)
        self.watchdog_enabled = bool(watchdog_enabled)
        self._clock = clock
        self.rid = rid
        self.turn_id = turn_id
        self._log_fn = log_fn
        self.watchdog = watchdog or ProcessWatchdog(
            log_fn=log_fn, rid=rid, turn_id=turn_id
        )
        self._lock = threading.Lock()
        now = self._clock()
        self.started_at: float = now
        self.last_activity_ts: float = now
        self.last_activity_kind: str = "start"
        self.pgid: int | None = None
        self.terminated_reason: str = ""

    def effective_cap_s(self) -> float:
        """Эффективный бюджет времени до срабатывания `absolute_cap`."""
        if self.safety_cap_s > self.finish_reserve_s:
            return self.safety_cap_s - self.finish_reserve_s
        return max(0.01, self.safety_cap_s)

    def record_activity(self, kind: str = "protocol") -> None:
        """Сбрасывает таймер простоя при получении протокольного события от бэкенда."""
        now = self._clock()
        with self._lock:
            self.last_activity_ts = now
            self.last_activity_kind = kind or "protocol"

    def on_activity(self, kind: str = "protocol") -> None:
        """Синоним `record_activity` для прямой передачи в `TurnContext.on_activity`."""
        self.record_activity(kind)

    def register_pgid(self, pgid: int) -> None:
        """Привязывает PGID дочернего процесса и снимает стартовый базовый срез."""
        if not isinstance(pgid, int) or pgid <= 0:
            return
        with self._lock:
            self.pgid = pgid
        if self.watchdog_enabled and self.watchdog is not None:
            self.watchdog.seed(pgid, rid=self.rid, turn_id=self.turn_id)

    def check(
        self, pgid: int | None = None
    ) -> tuple[bool, str, WatchdogMetrics | None]:
        """Проверяет условия завершения хода.

        Возвращает кортеж `(should_stop, reason, metrics)`, где `reason` при
        `should_stop == True` принимает одно из значений:
        - `"absolute_cap"` — превышен предохранительный потолок `SAFETY_CAP_S`;
        - `"idle_timeout"` — превышен порог неактивности `IDLE_TIMEOUT_S`;
        - `"child_exited"` — процессная группа завершилась.
        """
        with self._lock:
            target_pgid = pgid if pgid is not None else self.pgid
            started_at = self.started_at

        now = self._clock()
        if now - started_at >= self.effective_cap_s():
            with self._lock:
                self.terminated_reason = "absolute_cap"
            return True, "absolute_cap", None

        metrics: WatchdogMetrics | None = None
        if (
            self.watchdog_enabled
            and self.watchdog is not None
            and isinstance(target_pgid, int)
            and target_pgid > 0
        ):
            metrics = self.watchdog.sample(
                target_pgid, rid=self.rid, turn_id=self.turn_id
            )
            if not metrics.alive:
                with self._lock:
                    self.terminated_reason = "child_exited"
                return True, "child_exited", metrics
            if metrics.has_progress:
                with self._lock:
                    self.last_activity_ts = now
                    self.last_activity_kind = (
                        "new_descendants"
                        if metrics.new_descendants
                        else "cpu_delta"
                    )

        with self._lock:
            idle_elapsed = now - self.last_activity_ts
            if idle_elapsed >= self.idle_timeout_s:
                self.terminated_reason = "idle_timeout"
                return True, "idle_timeout", metrics

        return False, "", metrics

    def close(self) -> None:
        """Освобождает состояние отслеживаемой группы в `ProcessWatchdog`."""
        with self._lock:
            pgid = self.pgid
        if pgid is not None and self.watchdog is not None:
            self.watchdog.forget(pgid)
