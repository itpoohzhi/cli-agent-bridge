"""Универсальный graceful-drain саб-мостов (agy / claude-p / opencode-zen).

Наследник `HubLifecycleManager` (`core/lifecycle.py`): единые дефолты drain и `Retry-After`,
фазы `DrainState` и штатная уборка сирот при старте. Обработчик `SIGTERM`/`SIGINT` только
присваивает атрибуты (RW-007: ни `Lock`, ни `Event.set()`, ни I/O, ни `os._exit`). Остановкой
управляет фоновый поток: новые ходы получают `503` + `Retry-After`, активные доводятся до
`effective_drain_timeout_s`, затем оставшиеся группы гасятся параллельно вне сигнала;
`_serve_sse` успевает дописать терминальный кадр и `[DONE]` (клиент не видит «upstream stream
ended before finish_reason»).
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.dataclass_compat import DC_SLOTS
from core.lifecycle import DrainState, HubLifecycleManager
from core.proc_groups import child_process_groups, terminate_proc_groups_parallel
from core.subbridge_config import SubbridgeDrainConfig

HEALTH_PATHS = ("/health", "/v1/health")
WORKSPACE_ENV = "BRIDGE_WORKSPACE"
DEFAULT_WORKSPACE = Path.home() / ".cache" / "cli-agent-bridge"
Rejection = tuple[int, dict[str, str], dict[str, Any]]


@dataclass(frozen=True, **DC_SLOTS)
class SubbridgeHooks:
    """Колбэки конкретного моста; все необязательны (без них процессы ищутся через `ps`)."""

    procs_fn: Callable[[], list[subprocess.Popen[Any]]] | None = None
    active_procs_fn: Callable[[], int] | None = None
    force_kill_fn: Callable[[], None] | None = None
    cleanup_fn: Callable[[], None] | None = None
    log_fn: Callable[[str], None] | None = None


class SubbridgeLifecycle(HubLifecycleManager):
    """Координатор остановки HTTP-саб-моста; `handle_signal` не блокируется и не пишет в I/O."""

    def __init__(
        self,
        config: SubbridgeDrainConfig | None = None,
        hooks: SubbridgeHooks | None = None,
        workspace: Path | str | None = None,
    ) -> None:
        self.config = config or SubbridgeDrainConfig.from_env()
        self.hooks = hooks or SubbridgeHooks()
        self._signal_received = False
        self._shutdown_requested = False
        self._server: Any = None
        self.forced_kill = False
        self._draining = False
        self.active_http_turns = 0
        self._turns_lock = threading.Lock()
        self._force_killed = False
        self._cleanup_done = False
        super().__init__(
            workspace=workspace or os.environ.get(WORKSPACE_ENV) or DEFAULT_WORKSPACE,
            active_turns_fn=self.active_count,
            force_kill_fn=self.force_kill,
            drain_timeout_s=self.config.effective_drain_timeout_s,
            retry_after_s=self.config.retry_after_s,
            log_fn=self.hooks.log_fn,
        )

    def handle_signal(self, signum: int, _frame: Any = None) -> None:
        self._signal_received = True
        self._shutdown_requested = (
            True  # примитивный bool: безопасно в обработчике сигнала (RW-007)
        )
        self.last_signal = int(signum)

    def is_draining(self) -> bool:
        return (
            self._draining
            or self._signal_received
            or self._shutdown_requested
            or super().is_draining()
        )

    def reset(self) -> None:
        """Сбрасывает состояние координатора (для тестов): фазы, флаги и счётчики ходов."""
        super().reset()
        self._signal_received = False
        self._shutdown_requested = False
        self._draining = False
        self.forced_kill = False
        self._force_killed = False
        self._cleanup_done = False
        self.active_http_turns = 0

    def enter_turn(self, path: str) -> Rejection | None:
        """Атомарный допуск: проверка drain и учёт хода под одним замком (нет окна «допущен, но не посчитан»)."""
        with self._turns_lock:
            rejection = self.admission_rejection(path)
            if rejection is None:
                self.active_http_turns += 1
            return rejection

    @contextmanager
    def track_turn(self, path: str = "") -> Iterator[Rejection | None]:
        """Допуск и учёт хода до полной записи ответа (включая `[DONE]`); при отказе счётчик не растёт."""
        rejection = self.enter_turn(path)
        try:
            yield rejection
        finally:
            if rejection is None:
                with self._turns_lock:
                    self.active_http_turns -= 1

    def active_count(self) -> int:
        try:
            if self.hooks.active_procs_fn is not None:
                procs = self.hooks.active_procs_fn()
            else:
                procs = len(self.hooks.procs_fn()) if self.hooks.procs_fn else 0
        except Exception:  # noqa: BLE001 — гонка с мутацией реестра не должна ронять drain
            procs = 0
        return max(self.active_http_turns, procs)

    def health_headers(self) -> dict[str, str]:
        return {"X-Bridge-Draining": "true"} if self.is_draining() else {}

    def apply_health(self, payload: dict[str, Any]) -> dict[str, Any]:
        return (
            {**payload, "ok": False, "draining": True}
            if self.is_draining()
            else payload
        )

    def admission_rejection(self, path: str) -> Rejection | None:
        if not self.is_draining() or path.split("?", 1)[0].endswith("/cancel"):
            return None
        headers = {
            "Retry-After": str(self.config.retry_after_s),
            "X-Bridge-Draining": "true",
        }
        message = "Bridge is draining for restart, please retry"
        return (
            503,
            headers,
            {"error": {"message": message, "type": "overloaded", "code": 503}},
        )

    def _log(self, message: str) -> None:
        if self.hooks.log_fn is not None:
            with contextlib.suppress(Exception):  # сбой лога не должен срывать drain
                self.hooks.log_fn(message)

    def _cleanup(self) -> None:
        """Вызывает `cleanup_fn` ровно один раз за цикл остановки (даже если зачистка не понадобилась)."""
        if self._cleanup_done:
            return
        self._cleanup_done = True
        if self.hooks.cleanup_fn is not None:
            with contextlib.suppress(Exception):
                self.hooks.cleanup_fn()

    def force_kill(self) -> None:
        """Мягкая параллельная зачистка групп; идемпотентна в рамках цикла остановки (без второго `ps`)."""
        if self._force_killed:
            return
        self._force_killed = True
        try:
            if self.hooks.force_kill_fn is not None:
                self.hooks.force_kill_fn()
            else:
                cfg = self.config.effective_timers()
                procs = (
                    self.hooks.procs_fn()
                    if self.hooks.procs_fn is not None
                    else child_process_groups()
                )
                terminate_proc_groups_parallel(
                    procs, cfg.kill_term_grace_s, cfg.kill_wait_s
                )
        except Exception as exc:  # noqa: BLE001 — остановка не должна падать на зачистке
            self._log(f"drain_force_kill_error err={type(exc).__name__}")
        self._cleanup()

    def _wait_until(self, done: Callable[[], bool], budget_s: float) -> bool:
        end = time.monotonic() + budget_s
        while not done():
            if time.monotonic() >= end:
                return False
            time.sleep(self.config.poll_interval_s)
        return True

    def run_drain_once(self, server: Any = None) -> dict[str, Any]:
        """Drain: ждать ходы, при таймауте погасить процессы, дать дописать кадры, остановить сервер."""
        cfg = self.config
        target = self._server if server is None else server
        with self._turns_lock:  # барьер: допущенные ходы посчитаны, новые получат 503
            if self.state in (DrainState.DRAINING, DrainState.STOPPED):
                return {
                    "active_turns_before": 0,
                    "state": self.state,
                }  # повторный вызов: drain уже идёт/завершён
            self._draining = True
            self._shutdown_requested = True
            self.state = DrainState.DRAINING
        self.shutdown_requested.set()
        active = self.active_count()
        try:
            budget = cfg.effective_drain_timeout_s if cfg.enabled else 0.0
            self._log(f"drain_started signal={self.last_signal or 0} active={active}")
            if not self._wait_until(lambda: self.active_count() == 0, budget):
                self.forced_kill, active = True, self.active_count()
                self._log(f"drain_timeout active={active} budget_s={budget:.1f}")
                self.force_kill()
                self._wait_until(lambda: self.active_http_turns == 0, cfg.flush_grace_s)
        finally:  # без shutdown мост застрял бы в вечном 503
            self.state = DrainState.STOPPED
            self.drain_completed.set()
            try:
                target.shutdown()
            except Exception as exc:  # noqa: BLE001
                self._log(f"drain_shutdown_error err={type(exc).__name__}")
        return {"active_turns_before": active, "state": self.state}

    def _watch(self, server: Any) -> None:
        while not (self._signal_received or self._shutdown_requested):
            time.sleep(self.config.poll_interval_s)
        self.run_drain_once(server)

    def serve_forever(self, server: Any, install_signals: bool = True) -> int:
        """Обслуживает сервер до остановки по сигналу; возвращает код выхода процесса."""
        self._server = server
        if install_signals and threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, self.handle_signal)
            signal.signal(signal.SIGINT, self.handle_signal)
        with contextlib.suppress(Exception):  # сироты не должны мешать старту моста
            self.reap_orphans_on_startup()
        threading.Thread(
            target=self._watch, args=(server,), daemon=True, name="subbridge-drain"
        ).start()
        try:
            server.serve_forever()
        finally:
            server.server_close()
            # Штатный drain уже всё погасил: второй зачистки и лишнего `ps` быть не должно.
            if not self._force_killed and (
                not self._signal_received or self.active_count() > 0
            ):
                self.force_kill()
            else:
                self._cleanup()
        return 0

    def install(self, handler_cls: Any) -> Any:
        """Декоратор класса: оборачивает `do_GET` (/health) и `do_POST` (admission + учёт хода)."""
        orig_get, orig_post, life = handler_cls.do_GET, handler_cls.do_POST, self

        def reply(
            h: Any, code: int, headers: Mapping[str, str], body: dict[str, Any]
        ) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            h.close_connection = True
            h.send_response(code)
            for key, value in {"Content-Type": "application/json", **headers}.items():
                h.send_header(key, value)
            h.send_header("Content-Length", str(len(data)))
            h.end_headers()
            h.wfile.write(data)

        def do_get(h: Any) -> None:
            if life.is_draining() and h.path.split("?", 1)[0] in HEALTH_PATHS:
                payload = life.apply_health({"ok": True, "active": life.active_count()})
                return reply(h, 200, life.health_headers(), payload)
            return orig_get(h)

        def do_post(h: Any) -> None:
            with life.track_turn(h.path) as rejection:
                if rejection is not None:
                    return reply(h, *rejection)
                return orig_post(h)

        handler_cls.do_GET, handler_cls.do_POST = do_get, do_post
        return handler_cls
