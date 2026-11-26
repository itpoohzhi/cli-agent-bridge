"""Универсальный graceful-drain саб-мостов (agy / claude-p / opencode-zen): барьер `503`, ожидание ходов, уборка сирот; `SIGTERM`/`SIGINT` только присваивают атрибуты (RW-007)."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.dataclass_compat import DC_SLOTS
from core.drain_policy import DEFAULT_RETRY_AFTER_S, resolve_retry_after_s
from core.lifecycle import DrainState, HubLifecycleManager
from core.proc_groups import (
    child_process_groups,
    spawn_registered,
    terminate_proc_groups_parallel,
)
from core.subbridge_config import SubbridgeDrainConfig
from core.subbridge_drain import DrainCompleted, DrainObsEvent, DrainObsState
from core.subbridge_drain import transition as drain_transition

HEALTH_PATHS = ("/health", "/v1/health")
WORKSPACE_ENV = "BRIDGE_WORKSPACE"
DEFAULT_WORKSPACE = Path.home() / ".cache" / "cli-agent-bridge"
Rejection = tuple[int, dict[str, str], dict[str, Any]]
_block_spawns: Callable[[bool], None] = getattr(spawn_registered, "set_blocked")


@dataclass(frozen=True, **DC_SLOTS)
class SubbridgeHooks:
    procs_fn: Callable[[], list[subprocess.Popen[Any]]] | None = None
    active_procs_fn: Callable[[], int] | None = None
    force_kill_fn: Callable[[], None] | None = None
    cleanup_fn: Callable[[], None] | None = None
    log_fn: Callable[[str], None] | None = None


class SubbridgeLifecycle(HubLifecycleManager):
    def __init__(
        self,
        config: SubbridgeDrainConfig | None = None,
        hooks: SubbridgeHooks | None = None,
        workspace: Path | str | None = None,
    ) -> None:
        self.config = config or SubbridgeDrainConfig.from_env()
        self.hooks = hooks or SubbridgeHooks()
        self._turns_lock = threading.Lock()
        self._reset_flags()
        super().__init__(
            workspace=workspace or os.environ.get(WORKSPACE_ENV) or DEFAULT_WORKSPACE,
            active_turns_fn=self.active_count,
            force_kill_fn=self.force_kill,
            drain_timeout_s=self.config.effective_drain_timeout_s,
            retry_after_s=self.config.retry_after_s,
            log_fn=self.hooks.log_fn,
        )

    def handle_signal(self, signum: int, _frame: Any = None) -> None:
        self._signal_received = self._shutdown_requested = True  # bool (RW-007)
        self.last_signal = signum

    def is_draining(self) -> bool:
        flags = (self._signal_received, self._shutdown_requested)
        return any(flags) or super().is_draining()

    def reset(self) -> None:
        super().reset()
        self._reset_flags()
        ev = DrainObsEvent("reset_epoch")
        self._drain_obs, _ = drain_transition(self._drain_obs, ev)
        _block_spawns(False)  # новый цикл остановки не наследует барьер spawn

    def _reset_flags(self) -> None:
        self._signal_received = self._shutdown_requested = False
        self.forced_kill = self._cleanup_done = False
        self.active_http_turns = 0
        self._drain_obs, self.drain_log_errors = DrainObsState(), 0

    def enter_turn(self, path: str) -> Rejection | None:
        """Атомарный допуск: проверка drain и учёт хода под одним замком."""
        with self._turns_lock:
            rejection = self.admission_rejection(path)
            if rejection is None:
                self.active_http_turns += 1
            return rejection

    @contextlib.contextmanager
    def track_turn(self, path: str = "") -> Iterator[Rejection | None]:
        rejection = self.enter_turn(path)
        try:
            yield rejection
        finally:
            if rejection is None:
                with self._turns_lock:
                    self.active_http_turns -= 1

    def active_count(self) -> int:
        hooks = self.hooks
        try:
            if hooks.active_procs_fn is not None:
                procs = hooks.active_procs_fn()
            else:
                procs = len(hooks.procs_fn()) if hooks.procs_fn else 0
        except Exception:  # noqa: BLE001 — гонка с мутацией реестра не должна ронять drain
            procs = 0
        return max(self.active_http_turns, procs)

    def apply_health(self, payload: dict[str, Any]) -> dict[str, Any]:
        draining = {"ok": False, "draining": True}
        return {**payload, **draining} if self.is_draining() else payload

    def admission_rejection(self, path: str) -> Rejection | None:
        if not self.is_draining() or path.split("?", 1)[0].endswith("/cancel"):
            return None
        ra = self.config.retry_after_s
        use_env = "BRIDGE_RETRY_AFTER_S" in os.environ or ra == DEFAULT_RETRY_AFTER_S
        retry_s = resolve_retry_after_s(
            os.environ,
            explicit=None if use_env else ra,
            is_subagent=False,
            legacy_default=ra,
        )
        headers = {"Retry-After": str(retry_s), "X-Bridge-Draining": "true"}
        msg = "Bridge is draining for restart, please retry"
        body = {"error": {"message": msg, "type": "overloaded", "code": 503}}
        return 503, headers, body

    def _log(self, message: str) -> None:
        if self.hooks.log_fn is not None:
            with contextlib.suppress(Exception):  # сбой лога не должен срывать drain
                self.hooks.log_fn(message)

    def _emit_drain_line(self, message: str) -> None:
        if message and self.hooks.log_fn is not None:
            try:
                self.hooks.log_fn(message)
            except Exception:  # noqa: BLE001 — сбой лога не срывает drain
                self.drain_log_errors += 1

    def _cleanup(self) -> None:
        if self._cleanup_done:
            return
        self._cleanup_done = True
        if self.hooks.cleanup_fn is not None:
            with contextlib.suppress(Exception):
                self.hooks.cleanup_fn()

    def force_kill(self) -> None:
        if self.forced_kill:
            return
        self.forced_kill = True
        _block_spawns(True)
        try:
            if self.hooks.force_kill_fn is not None:
                self.hooks.force_kill_fn()
            else:
                term, kill, _flush = self.config.effective_timers()
                own = self.hooks.procs_fn() if self.hooks.procs_fn else []
                groups = {p.pid: p for p in [*child_process_groups(), *own]}
                terminate_proc_groups_parallel(list(groups.values()), term, kill)
        except Exception as exc:  # noqa: BLE001 — остановка не должна падать на зачистке
            self._log(f"drain_force_kill_error err={type(exc).__name__}")

    def _wait_until(self, done: Callable[[], bool], budget_s: float) -> bool:
        end = time.monotonic() + budget_s
        while not done():
            if time.monotonic() >= end:
                return False
            time.sleep(self.config.poll_interval_s)
        return True

    def run_drain_once(self, server: Any = None) -> dict[str, Any]:
        """Drain: ждать ходы, при таймауте погасить процессы, дать дописать кадры, остановить сервер."""
        with self._turns_lock:  # барьер: допущенные ходы посчитаны, новые получат 503
            sig = self.last_signal or 0
            if self.state in (DrainState.DRAINING, DrainState.STOPPED):
                ev, dup_state = DrainObsEvent("reentry", signal=sig), self.state
            else:
                self._shutdown_requested, self.state = True, DrainState.DRAINING
                ev, dup_state = DrainObsEvent("start", signal=sig), ""
            self._drain_obs, effs = drain_transition(self._drain_obs, ev)
        if dup_state:
            self._emit_drain_line(effs[0].line)  # строго вне `_turns_lock`
            result = {"active_turns_before": 0, "state": dup_state}
            result["drain_log_errors"] = self.drain_log_errors
            return result
        cfg, target = self.config, self._server if server is None else server
        _block_spawns(True)  # новых процессов не порождаем
        self.shutdown_requested.set()
        started_ms, active_before = time.monotonic(), self.active_count()
        try:
            budget = cfg.effective_drain_timeout_s if cfg.enabled else 0.0
            self._log(f"drain_started signal={sig} active={active_before}")
            if not self._wait_until(lambda: self.active_count() == 0, budget):
                left = self.active_count()
                self._log(f"drain_timeout active={left} budget_s={budget:.1f}")
                self.force_kill()
                flush_s = cfg.effective_timers()[2]
                self._wait_until(lambda: self.active_http_turns == 0, flush_s)
                self._cleanup()  # после flush: не режем каталоги живых ходов
        finally:  # без shutdown мост застрял бы в вечном 503
            result = self._finish_drain(target, started_ms, active_before)
        return result

    def _finish_drain(self, target: Any, t0: float, before: int) -> dict[str, Any]:
        ok = True
        try:
            target.shutdown()
        except Exception as exc:  # noqa: BLE001
            ok = False
            self._log(f"drain_shutdown_error err={type(exc).__name__}")
        sig, epoch = self.last_signal or 0, self._drain_obs.epoch
        left, fk = self.active_count(), self.forced_kill
        ms = int((time.monotonic() - t0) * 1000)
        ev = DrainObsEvent(
            "complete", outcome=DrainCompleted(sig, before, left, fk, ms, ok, epoch)
        )
        self._drain_obs, effs = drain_transition(self._drain_obs, ev)
        self._emit_drain_line(effs[0].line)  # строго до STOPPED / Event.set()
        self.state = DrainState.STOPPED
        self.drain_completed.set()
        result = {"state": self.state, "active_turns_before": before, "remaining": left}
        result["forced_kill"], result["shutdown_ok"] = fk, ok
        result["drain_log_errors"] = self.drain_log_errors
        return result

    def _watch(self, server: Any) -> None:
        while not (self._signal_received or self._shutdown_requested):
            time.sleep(self.config.poll_interval_s)
        self.run_drain_once(server)

    def serve_forever(self, server: Any, install_signals: bool = True) -> int:
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
            needs_kill = not self._signal_received or self.active_count() > 0
            if not self.forced_kill and needs_kill:
                self.force_kill()
            self._cleanup()
        return 0

    def install(self, handler_cls: Any) -> Any:
        orig_get, orig_post, life = handler_cls.do_GET, handler_cls.do_POST, self

        def reply(h: Any, code: int, headers: Mapping[str, str], body: Any) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            h.close_connection = True
            h.send_response(code)
            for key, value in {"Content-Type": "application/json", **headers}.items():
                h.send_header(key, value)
            h.send_header("Content-Length", str(len(data)))
            h.end_headers()
            h.wfile.write(data)

        def do_get(h: Any) -> None:
            try:
                if life.is_draining() and h.path.split("?", 1)[0] in HEALTH_PATHS:
                    active = life.active_count()
                    payload = life.apply_health({"ok": True, "active": active})
                    return reply(h, 200, life.health_headers(), payload)
                return orig_get(h)
            finally:
                if life.is_draining():
                    h.close_connection = True

        def do_post(h: Any) -> None:
            try:
                with life.track_turn(h.path) as rejection:
                    if rejection is not None:
                        return reply(h, *rejection)
                    return orig_post(h)
            finally:  # keep-alive не должен держать сервер в drain
                if life.is_draining():
                    h.close_connection = True

        handler_cls.do_GET, handler_cls.do_POST = do_get, do_post
        return handler_cls
