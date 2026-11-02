"""Менеджер жизненного цикла хаба, неблокирующий Drain и уборка сирот (ADR-0005 / AD-004).

Модуль отвечает за:
1. Неблокирующий перехват `SIGTERM`/`SIGINT` (`RW-007`): обработчик сигнала выставляет
   только `threading.Event` (`shutdown_requested`), не захватывая мьютексы и не
   выполняя блокирующий ввод-вывод.
2. Координацию `DRAINING` в фоновом потоке (`DRAIN_TIMEOUT_S = 110.0` с при
   `ExitTimeOut = 120` с в launchd): новые запросы получают `HTTP 503 Service Unavailable`
   с заголовком `Retry-After: 5`, `/health` возвращает `ok: false` и заголовок
   `X-Bridge-Draining: true`, а активные ходы доводятся до конца либо корректно
   прерываются со сбросом `reasoning_content` и терминальным чанком `drain_timeout`.
3. Безопасную уборку сирот при старте (`reap_orphans_on_startup`, `RW-004`): сверка
   `workspace/state/children.json` через `os.kill(pid, 0)` и имя команды в `ps`,
   мягкое погашение `SIGTERM -> 1s -> SIGKILL` с логом `orphan_reaped`.
4. Контроль настраиваемого интервала SSE keepalive (`KeepaliveController`).
"""

from __future__ import annotations

from collections.abc import Callable
import json
import math
import os
from pathlib import Path
import random
import signal
import subprocess
import threading
import time
from typing import Any, TypeVar

from core.backend_adapter import PreSendTransientError
from core.resilience import RetryPolicy
from core.watchdog import positive_env

from core.turn_session_manager import (
    SNAPSHOT_SCHEMA_VERSION,
    TurnSessionManager,
    _atomic_write_json_0600,
)

DRAIN_TIMEOUT_S: float = 110.0
DEFAULT_DRAIN_SECONDS: float = DRAIN_TIMEOUT_S
RETRY_AFTER_S: int = 5
ORPHAN_SIGTERM_GRACE_S: float = 1.0
MAX_KEEPALIVE_INTERVAL_S: float = 10.0

KNOWN_CHILD_BINARIES = frozenset(
    {
        "muse",
        "muse-cli",
        "muse-cli.sh",
        "agy",
        "agy-cli.sh",
        "droid",
        "fake_droid",
        "fake_serve",
        "node",
        "python",
        "python3",
        "bash",
        "sh",
        "zsh",
        "sleep",
    }
)


class DrainState:
    """Фазы жизненного цикла HTTP-хаба при перезапуске."""

    READY = "READY"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"


class KeepaliveController:
    """Настраиваемый интервал SSE keepalive; по умолчанию не более 10 с."""

    def __init__(self, max_interval_s: float | None = None) -> None:
        configured = positive_env(
            "BRIDGE_KEEPALIVE_INTERVAL_S",
            positive_env(
                "BRIDGE_KEEPALIVE_S",
                positive_env("DROID_DSH_BRIDGE_KEEPALIVE_S", MAX_KEEPALIVE_INTERVAL_S),
            ),
        )
        self.min_interval_s = positive_env("BRIDGE_KEEPALIVE_MIN_INTERVAL_S", 0.05)
        value = configured if max_interval_s is None else float(max_interval_s)
        self.max_interval_s = max(
            self.min_interval_s,
            value if math.isfinite(value) and value > 0 else configured,
        )

    def effective_interval(self, requested_s: float | int | None = None) -> float:
        """Возвращает интервал в настроенных границах без busy-loop на малом значении."""
        if requested_s is None:
            return self.max_interval_s
        try:
            val = float(requested_s)
        except (TypeError, ValueError):
            return self.max_interval_s
        if not math.isfinite(val) or val <= 0:
            return self.max_interval_s
        return max(self.min_interval_s, min(val, self.max_interval_s))

    @staticmethod
    def sse_comment() -> str:
        """Возвращает стандартный SSE-комментарий keepalive."""
        return ": keepalive\n\n"

    @staticmethod
    def sse_data_chunk(
        model: str = "",
        reasoning: bool = True,
        *,
        completion_id: str | None = None,
        created: int | None = None,
    ) -> str:
        """Возвращает распознаваемый клиентским idle-watchdog чанк вне истории хода."""
        timestamp = int(time.time()) if created is None else int(created)
        payload = json.dumps(
            {
                "id": completion_id or f"chatcmpl-ping-{time.time_ns()}",
                "object": "chat.completion.chunk",
                "created": timestamp,
                "model": model or "bridge-keepalive",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"reasoning_content": " "} if reasoning else {},
                        "finish_reason": None,
                    }
                ],
            },
            ensure_ascii=False,
        )
        return f"data: {payload}\n\n"


_RetryResult = TypeVar("_RetryResult")


class PreSendRetry:
    """Общий ограниченный retry временного upstream-отказа до первого байта клиенту."""

    def __init__(
        self,
        *,
        committed: Callable[[], bool] | None = None,
        cancelled: Callable[[], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
        wait: Callable[[float], bool] | None = None,
        rng: Callable[[float, float], float] = random.uniform,
    ) -> None:
        raw = os.environ.get("BRIDGE_MAX_RETRIES", "3").strip()
        try:
            self.max_retries = int(raw) if raw.isdecimal() else 3
        except ValueError:
            self.max_retries = 3
        self.budget_s = positive_env("BRIDGE_RETRY_BUDGET_S", 60.0)
        self.backoff_s = positive_env("BRIDGE_RETRY_BACKOFF_S", 1.0)
        self.max_backoff_s = positive_env("BRIDGE_RETRY_MAX_BACKOFF_S", 10.0)
        self._committed = committed or (lambda: False)
        self._cancelled = cancelled or (lambda: False)
        self._clock = clock
        self.deadline = clock() + self.budget_s
        self._cancel_poll_s = positive_env("BRIDGE_RETRY_CANCEL_POLL_S", 0.1)
        self._wait = wait or self._interruptible_wait
        self._policy = RetryPolicy(
            max_attempts=self.max_retries + 1,
            base_delay_s=self.backoff_s,
            max_delay_s=self.max_backoff_s,
            rng=rng,
            is_transient=lambda exc: (
                isinstance(exc, PreSendTransientError)
                and exc.status_code in (None, 502, 503)
            ),
        )

    def _interruptible_wait(self, delay: float) -> bool:
        deadline = self._clock() + delay
        wake = threading.Event()
        while not self._cancelled():
            remaining = deadline - self._clock()
            if remaining <= 0:
                return False
            wake.wait(min(remaining, self._cancel_poll_s))
        return True

    def run(self, operation: Callable[[], _RetryResult]) -> _RetryResult:
        """Повторяет только типизированные upstream-отказы в едином бюджете и до commit."""
        deadline = self.deadline = self._clock() + self.budget_s
        retries = 0
        while True:
            try:
                return operation()
            except PreSendTransientError as exc:
                delay = self._policy.compute_delay(retries, deadline - self._clock())
                if (
                    not self._policy.should_retry(retries, self._committed(), exc)
                    or self._cancelled()
                    or delay is None
                ):
                    raise
                if (
                    self._wait(delay)
                    or self._cancelled()
                    or self._committed()
                    or self._clock() >= deadline
                ):
                    raise
                retries += 1


class HubLifecycleManager:
    """Координатор сигналов `SIGTERM`/`SIGINT`, фазы `DRAINING` и уборки сирот."""

    def __init__(
        self,
        workspace: Path | str | Callable[[], Path] | None = None,
        *,
        state_dir: Path | str | Callable[[], Path] | None = None,
        turn_manager: TurnSessionManager | None = None,
        active_turns_fn: Callable[[], int] | None = None,
        force_kill_fn: Callable[[], None] | None = None,
        drain_timeout_s: float = DRAIN_TIMEOUT_S,
        retry_after_s: int = RETRY_AFTER_S,
        orphan_grace_s: float = ORPHAN_SIGTERM_GRACE_S,
        drain_enabled_fn: Callable[[], bool] | None = None,
        log_fn: Callable[[str], None] | None = None,
        on_shutdown_complete: Callable[[], None] | None = None,
    ) -> None:
        ws_source = workspace if workspace is not None else (state_dir or ".")
        self._explicit_state_dir = state_dir
        self._workspace_fn: Callable[[], Path] = (
            (lambda: Path(ws_source))
            if isinstance(ws_source, (str, Path))
            else ws_source
        )
        self.turn_manager = turn_manager
        self._active_turns_fn = active_turns_fn
        self.drain_timeout_s = float(drain_timeout_s)
        self.retry_after_s = int(retry_after_s)
        self.orphan_grace_s = float(orphan_grace_s)
        self._drain_enabled_fn = drain_enabled_fn or (
            lambda: os.environ.get(
                "BRIDGE_DRAIN_ON_SHUTDOWN",
                os.environ.get("DSH_BRIDGE_DRAIN_ENABLED", "true"),
            )
            .strip()
            .lower()
            in ("1", "true", "yes", "on")
        )
        self._log_fn = log_fn
        self._on_shutdown_complete = on_shutdown_complete or force_kill_fn


        self.shutdown_requested = threading.Event()
        self.drain_started = threading.Event()
        self.drain_completed = threading.Event()
        self.state: str = DrainState.READY
        self.last_signal: int | None = None

        self._lock = threading.Lock()
        self._server: Any = None
        self._drain_thread: threading.Thread | None = None
        self.keepalive = KeepaliveController()

    @property
    def workspace(self) -> Path:
        return Path(self._workspace_fn())

    @property
    def children_path(self) -> Path:
        if self.turn_manager is not None:
            return self.turn_manager.children_path
        if self._explicit_state_dir is not None:
            sd = Path(
                self._explicit_state_dir()
                if callable(self._explicit_state_dir)
                else self._explicit_state_dir
            )
            if (sd / "children.json").exists() or not (sd / "state").is_dir():
                return sd / "children.json"
        return self.workspace / "state" / "children.json"

    def is_draining(self) -> bool:
        return (
            self.state in (DrainState.DRAINING, DrainState.STOPPED)
            or self.shutdown_requested.is_set()
        )

    def is_drain_enabled(self) -> bool:
        return bool(self._drain_enabled_fn())

    def _log(self, message: str) -> None:
        if self._log_fn is not None:
            try:
                self._log_fn(message)
            except Exception:  # noqa: BLE001
                pass

    def attach_server(self, server: Any) -> None:
        """Привязывает экземпляр `ThreadingHTTPServer` для остановки после drain."""
        with self._lock:
            self._server = server

    def start_signal_watcher(self, server: Any = None) -> threading.Thread:
        """Привязывает HTTP-сервер и запускает фоновый поток координации drain."""
        if server is not None:
            self.attach_server(server)
        return self.start_drain_worker()

    def handle_signal(self, signum: int, _frame: Any = None) -> None:
        """Неблокирующий обработчик `SIGTERM`/`SIGINT` (RW-007).

        В обработчике сигнала запрещены захват `Lock`, логирование и I/O:
        выставляется только атомарный `threading.Event`.
        """
        self.last_signal = int(signum)
        self.shutdown_requested.set()

    def start_drain_worker(self) -> threading.Thread:
        """Запускает фоновый поток, ожидающий `shutdown_requested`."""
        with self._lock:
            if self._drain_thread is not None and self._drain_thread.is_alive():
                return self._drain_thread
            worker = threading.Thread(
                target=self._drain_worker_loop,
                name="hub-drain-coordinator",
                daemon=True,
            )
            self._drain_thread = worker
            worker.start()
            return worker

    def install_signal_handlers(self, *, start_worker: bool = True) -> None:
        """Регистрирует `handle_signal` для `SIGTERM`/`SIGINT` и запускает drain-поток."""
        if start_worker:
            self.start_drain_worker()
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, self.handle_signal)
            signal.signal(signal.SIGINT, self.handle_signal)

    def trigger_shutdown(self, signum: int = signal.SIGTERM) -> None:
        """Инициирует процедуру Graceful Shutdown & Drain (безопасно из любого потока)."""
        self.start_drain_worker()
        self.handle_signal(signum, None)

    def _drain_worker_loop(self) -> None:
        self.shutdown_requested.wait()
        self.run_drain_once()

    def run_drain_once(self) -> dict[str, Any]:
        """Выполняет фазу `DRAINING` в фоновом потоке (идемпотентно)."""
        with self._lock:
            if self.state in (DrainState.DRAINING, DrainState.STOPPED):
                return {"interrupted_turn_ids": [], "state": self.state}
            self.state = DrainState.DRAINING
            self.drain_started.set()
            srv = self._server

        eff_timeout = self.drain_timeout_s if self.is_drain_enabled() else 0.0
        active_before = (
            self._active_turns_fn()
            if self._active_turns_fn is not None
            else (self.turn_manager.active_count() if self.turn_manager is not None else 0)
        )
        self._log(
            f"drain_started signal={self.last_signal or 0} "
            f"active_turns={active_before} timeout_s={eff_timeout:.1f}"
        )

        if srv is not None and hasattr(srv, "graceful_close_listener"):
            try:
                srv.graceful_close_listener()
            except Exception as exc:  # noqa: BLE001
                self._log(f"graceful_close_listener_failed err={exc!r}")

        remaining = []
        deadline = time.monotonic() + max(0.0, eff_timeout)
        if self.turn_manager is not None:
            if eff_timeout > 0:
                remaining = self.turn_manager.wait_for_active_turns(
                    timeout=max(0.0, deadline - time.monotonic())
                )
            else:
                remaining = self.turn_manager.active_turns()

            for turn in remaining:
                self._log(
                    f"drain_timeout_interrupt rid={turn.rid} turn_id={turn.turn_id} "
                    f"pgid={turn.pgid}"
                )
                self.turn_manager.interrupt_for_drain(
                    turn,
                    message="bridge restart drain timeout exceeded",
                )

        if self._active_turns_fn is not None and eff_timeout > 0:
            while time.monotonic() < deadline and self._active_turns_fn() > 0:
                time.sleep(0.05)

        if srv is not None:
            try:
                srv.shutdown()
            except Exception:  # noqa: BLE001
                pass

        if self._on_shutdown_complete is not None:
            try:
                self._on_shutdown_complete()
            except Exception:  # noqa: BLE001
                pass

        with self._lock:
            self.state = DrainState.STOPPED
            self.drain_completed.set()
        self._log(f"drain_completed interrupted_turns={len(remaining)}")
        return {
            "interrupted_turn_ids": [t.turn_id for t in remaining],
            "active_turns_before": active_before,
            "state": self.state,
        }

    def draining_response(self) -> tuple[int, dict[str, str], dict[str, Any]]:
        """Возвращает `(status_code, headers, body)` для отказа новым запросам при `DRAINING`."""
        headers = {
            "Retry-After": str(self.retry_after_s),
            "X-Bridge-Draining": "true",
        }
        body = {
            "error": {
                "message": "bridge is draining for restart",
                "type": "overloaded",
                "code": 503,
            }
        }
        return 503, headers, body

    def health_headers(self) -> dict[str, str]:
        """Возвращает дополнительные HTTP-заголовки для `/health` в режиме `DRAINING`."""
        if self.is_draining():
            return {"X-Bridge-Draining": "true"}
        return {}

    @staticmethod
    def _is_pid_or_group_alive(pid: int, pgid: int) -> bool:
        for target, fn in ((pgid, os.killpg), (pid, os.kill)):
            if isinstance(target, int) and target > 0:
                try:
                    fn(target, 0)
                    return True
                except ProcessLookupError:
                    continue
                except PermissionError:
                    return True
                except OSError:
                    continue
        return False

    @staticmethod
    def _matches_expected_command(pid: int, pgid: int, expected_cmd: str = "") -> bool:
        """Проверяет через `ps`, что процесс принадлежит CLI-потомку моста, а не чужому PID."""
        targets = []
        if isinstance(pid, int) and pid > 0:
            targets.append(("-p", str(pid)))
        if isinstance(pgid, int) and pgid > 0:
            targets.append(("-g", str(pgid)))
        if not targets:
            return False

        for flag, val in targets:
            try:
                proc = subprocess.run(
                    ["ps", "-o", "comm=,command=", flag, val],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=False,
                )
            except (subprocess.TimeoutExpired, OSError):
                continue
            if proc.returncode != 0 or not proc.stdout.strip():
                continue
            out_lower = proc.stdout.lower()
            if expected_cmd and expected_cmd.lower() in out_lower:
                return True
            for token in KNOWN_CHILD_BINARIES:
                if token in out_lower:
                    return True
        return False

    def reap_orphans_on_startup(
        self, children_file: Path | None = None
    ) -> list[int]:
        """Убирает осиротевшие группы процессов из `children.json` при старте хаба (RW-004)."""
        path = Path(children_file) if children_file is not None else self.children_path
        if not path.is_file():
            return []

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        entries: list[dict[str, Any]] = []
        if isinstance(raw, dict):
            if isinstance(raw.get("children"), list):
                entries = [item for item in raw["children"] if isinstance(item, dict)]
            else:
                for key, val in raw.items():
                    if key == "schema_version":
                        continue
                    if isinstance(val, dict):
                        entry = dict(val)
                        if "pid" not in entry and str(key).isdigit():
                            entry["pid"] = int(key)
                        entries.append(entry)
                    elif isinstance(val, int) and str(key).isdigit():
                        entries.append({"pid": int(key), "pgid": int(val)})
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    entries.append(item)
                elif isinstance(item, int):
                    entries.append({"pid": item, "pgid": item})

        reaped_pgids: list[int] = []
        seen_pgids: set[int] = set()
        for entry in entries:
            pid = int(entry.get("pid") or entry.get("pgid") or 0)
            pgid = int(entry.get("pgid") or pid or 0)
            turn_id = str(entry.get("turn_id") or "-")
            expected_cmd = str(entry.get("command") or entry.get("cmd") or "")
            if pgid <= 0 or pgid in seen_pgids:
                continue
            seen_pgids.add(pgid)
            if not self._is_pid_or_group_alive(pid, pgid):
                continue
            if not self._matches_expected_command(pid, pgid, expected_cmd):
                continue

            try:
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    if pid > 0:
                        os.kill(pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    pass

            deadline = time.monotonic() + max(0.05, self.orphan_grace_s)
            while time.monotonic() < deadline:
                if not self._is_pid_or_group_alive(pid, pgid):
                    break
                time.sleep(0.05)

            if self._is_pid_or_group_alive(pid, pgid):
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    try:
                        if pid > 0:
                            os.kill(pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError, OSError):
                        pass

            reaped_pgids.append(pgid)
            self._log(f"orphan_reaped pgid={pgid} turn_id={turn_id}")

        try:
            empty_payload: Any = (
                []
                if isinstance(raw, list)
                else {"schema_version": SNAPSHOT_SCHEMA_VERSION, "children": []}
            )
            _atomic_write_json_0600(path, empty_payload)
        except OSError:
            pass

        return reaped_pgids

    reap_startup_orphans = reap_orphans_on_startup

    def reset(self) -> None:
        """Сбрасывает состояние менеджера жизненного цикла (для тестов)."""
        with self._lock:
            self.shutdown_requested.clear()
            self.drain_started.clear()
            self.drain_completed.clear()
            self.state = DrainState.READY
            self.last_signal = None
            self._drain_thread = None

    reset_state = reset
    reset_for_tests = reset

