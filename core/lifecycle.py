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
4. Контроль интервала SSE keepalive (`KeepaliveController`, `<= 10.0` с).
"""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from typing import Any

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
    """Контроллер интервала SSE keepalive (`<= 10.0` с для защиты от обрыва прокси/туннеля)."""

    def __init__(self, max_interval_s: float = MAX_KEEPALIVE_INTERVAL_S) -> None:
        self.max_interval_s = max(0.05, min(float(max_interval_s), MAX_KEEPALIVE_INTERVAL_S))

    def effective_interval(self, requested_s: float | int | None = None) -> float:
        """Возвращает эффективный интервал keepalive, не превышающий `10.0` с."""
        if requested_s is None:
            return self.max_interval_s
        try:
            val = float(requested_s)
        except (TypeError, ValueError):
            return self.max_interval_s
        if val <= 0:
            return self.max_interval_s
        return min(val, self.max_interval_s)

    @staticmethod
    def sse_comment() -> str:
        """Возвращает стандартный SSE-комментарий keepalive."""
        return ": keepalive\n\n"

    @staticmethod
    def sse_data_chunk(
        *,
        completion_id: str,
        created: int,
        model: str,
    ) -> str:
        """Возвращает пустой SSE data-чанк keepalive в формате OpenAI `chat.completion.chunk`."""
        payload = json.dumps(
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": int(created),
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
            },
            ensure_ascii=False,
        )
        return f"data: {payload}\n\n"


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
            self.turn_manager.active_count()
            if self.turn_manager is not None
            else (self._active_turns_fn() if self._active_turns_fn is not None else 0)
        )
        self._log(
            f"drain_started signal={self.last_signal or 0} "
            f"active_turns={active_before} timeout_s={eff_timeout:.1f}"
        )

        remaining = []
        deadline = time.monotonic() + max(0.0, eff_timeout)
        if self.turn_manager is not None:
            if eff_timeout > 0:
                remaining = self.turn_manager.wait_for_active_turns(timeout=eff_timeout)
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
        elif self._active_turns_fn is not None and eff_timeout > 0:
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

