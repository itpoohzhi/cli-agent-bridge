"""Тесты отказоустойчивости agy-bridge (ADR-0007, arch-spec r2 §6, RW-008).

Покрыто 15 сценариев: детекция неактивности группы, сброс таймера по CPU и по
протокольным событиям, fail-closed при деградации `ps`, троттлинг `check()` в
`_execute`, `child_exited` как штатное завершение, `absolute_cap` -> `timeout`,
kill-switch, контракт ошибки `idle_timeout` (HTTP 504 / SSE), зачистка группы
процессов и reap лидера, изоляция таймаута источника в `fetch_via_playwright.py`.

Мост `bridges/agy-bridge/server.py` лежит в каталоге с дефисом, поэтому грузится
через `importlib`. Таймауты малые (`idle_timeout_s=0.2`) либо мок-часы; процессы
создаются с `start_new_session=True` и убираются в `finally`.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import queue
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.watchdog import (  # noqa: E402
    AdaptiveTimeoutController,
    ProcessWatchdog,
    WatchdogMetrics,
)

_BRIDGE_PY = _REPO_ROOT / "bridges" / "agy-bridge" / "server.py"
_FETCH_SCRIPT = Path(
    os.environ.get("AIBUNKER_FETCH_SCRIPT")
    or "~/Мой диск/Workshop/aibunker-workshop/scripts/fetch_via_playwright.py"
).expanduser()

_POSIX = sys.platform != "win32"
_DARWIN = sys.platform == "darwin"


def _load_bridge() -> Any:
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-agy-resilience")
    os.environ.pop("AGY_BRIDGE_FLEET", None)
    spec = importlib.util.spec_from_file_location(
        "agy_bridge_server_under_test", _BRIDGE_PY
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


srv = _load_bridge()


class _FakeClock:
    """Ручные часы: время движется только через advance()."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _TickQueue:
    """Очередь, у которой пустое ожидание двигает мок-часы на `timeout` секунд."""

    def __init__(self, clock: _FakeClock, empty_ticks: int, events: list) -> None:
        self.clock = clock
        self.empty_ticks = empty_ticks
        self.events = list(events)

    def get(self, timeout: float = 0.0) -> Any:
        if self.empty_ticks > 0:
            self.empty_ticks -= 1
            self.clock.advance(float(timeout))
            raise queue.Empty
        if self.events:
            return self.events.pop(0)
        self.clock.advance(float(timeout))
        raise queue.Empty


class _SpyController:
    """Обёртка над реальным контроллером: считает check() и on_activity()."""

    def __init__(
        self, inner: AdaptiveTimeoutController, forced: tuple | None = None
    ) -> None:
        self.inner = inner
        self.forced = forced
        self.check_calls = 0
        self.activity: list[str] = []

    def on_activity(self, kind: str = "protocol") -> None:
        self.activity.append(kind)
        self.inner.on_activity(kind)

    def check(self, pgid: int | None = None) -> tuple:
        self.check_calls += 1
        if self.forced is not None:
            return self.forced
        return self.inner.check(pgid)


def _spawn(argv: list[str], **kwargs: Any) -> subprocess.Popen:
    return subprocess.Popen(argv, start_new_session=True, **kwargs)


def _hard_kill(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        pass


def _ps_stat(pid: int) -> str:
    out = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip()


def _group_gone(pgid: int, within_s: float = 2.0) -> bool:
    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        time.sleep(0.05)
    return False


class _Sock:
    """Пара сокетов для Handler.connection: пир открыт, данных нет -> клиент «на месте»."""

    def __enter__(self) -> socket.socket:
        self.a, self.b = socket.socketpair()
        return self.a

    def __exit__(self, *_exc: Any) -> None:
        self.a.close()
        self.b.close()


def _make_handler(connection: socket.socket) -> Any:
    handler = srv.Handler.__new__(srv.Handler)
    handler.connection = connection
    return handler


def _fake_run(
    clock: _FakeClock, controller: Any, events: list, empty_ticks: int
) -> SimpleNamespace:
    return SimpleNamespace(
        q=_TickQueue(clock, empty_ticks, events),
        controller=controller,
        proc=SimpleNamespace(pid=424242),
        got_event=True,
        started=clock(),
        err_box=[],
    )


def _fake_time(clock: _FakeClock) -> SimpleNamespace:
    return SimpleNamespace(
        monotonic=clock, sleep=lambda _s: None, strftime=time.strftime, time=time.time
    )


def _execute_with_clock(clock: _FakeClock, run: SimpleNamespace) -> dict:
    """Прогнать Handler._execute на мок-часах без реальных ожиданий."""
    with _Sock() as sock, mock.patch.object(srv, "time", _fake_time(clock)):
        handler = _make_handler(sock)
        return handler._execute(
            run, lambda _t: True, lambda _e: True, lambda _r: True, None
        )


class IdleDetectionTests(unittest.TestCase):
    @unittest.skipUnless(_DARWIN, "core.watchdog рассчитан на macOS ps")
    def test_idle_timeout_detected_for_sleeping_process(self) -> None:
        proc = _spawn(["sleep", "100"])
        try:
            ctrl = AdaptiveTimeoutController(
                idle_timeout_s=0.2, safety_cap_s=60.0, finish_reserve_s=0.0
            )
            ctrl.register_pgid(proc.pid)
            result: tuple = (False, "", None)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                result = ctrl.check(proc.pid)
                if result[0]:
                    break
                time.sleep(0.05)
            self.assertTrue(result[0])
            self.assertEqual(result[1], "idle_timeout")
            ctrl.close()
        finally:
            _hard_kill(proc)

    @unittest.skipUnless(_DARWIN, "core.watchdog рассчитан на macOS ps")
    def test_cpu_delta_resets_idle_timer(self) -> None:
        proc = _spawn([sys.executable, "-I", "-c", "while True: pass"])
        try:
            ctrl = AdaptiveTimeoutController(
                idle_timeout_s=0.2, safety_cap_s=60.0, finish_reserve_s=0.0
            )
            ctrl.register_pgid(proc.pid)
            end = time.monotonic() + 0.9  # заметно больше idle_timeout_s
            while time.monotonic() < end:
                should_stop, reason, _m = ctrl.check(proc.pid)
                self.assertFalse(should_stop, f"ложный {reason}: CPU растёт")
                time.sleep(0.05)
            self.assertEqual(ctrl.last_activity_kind, "cpu_delta")
            ctrl.close()
        finally:
            _hard_kill(proc)

    def test_on_activity_resets_idle_timer(self) -> None:
        for kind in ("text", "reasoning", "tool_trace", "init"):
            with self.subTest(kind=kind):
                clock = _FakeClock()
                ctrl = AdaptiveTimeoutController(
                    idle_timeout_s=0.2,
                    safety_cap_s=60.0,
                    finish_reserve_s=0.0,
                    watchdog_enabled=False,
                    clock=clock,
                )
                for _ in range(5):
                    clock.advance(0.15)
                    ctrl.on_activity(kind)
                    self.assertEqual(ctrl.check(), (False, "", None))
                self.assertEqual(ctrl.last_activity_kind, kind)
                clock.advance(0.25)
                should_stop, reason, _m = ctrl.check()
                self.assertTrue(should_stop)
                self.assertEqual(reason, "idle_timeout")

    @unittest.skipUnless(_POSIX, "нужны процессные группы POSIX")
    def test_ps_degraded_fail_closed(self) -> None:
        class _DegradedPs(ProcessWatchdog):
            def _run_ps(self, pgid: int) -> Any:
                raise subprocess.TimeoutExpired(cmd="ps", timeout=2.0)

        logs: list[str] = []
        proc = _spawn(["sleep", "100"])
        try:
            clock = _FakeClock()
            ctrl = AdaptiveTimeoutController(
                idle_timeout_s=0.2,
                safety_cap_s=60.0,
                finish_reserve_s=0.0,
                watchdog=_DegradedPs(log_fn=logs.append),
                clock=clock,
                log_fn=logs.append,
            )
            ctrl.register_pgid(proc.pid)
            self.assertEqual(ctrl.check(proc.pid)[:2], (False, ""))
            marker = ctrl.last_activity_ts
            clock.advance(0.25)
            should_stop, reason, metrics = ctrl.check(proc.pid)
            self.assertTrue(should_stop)
            self.assertEqual(reason, "idle_timeout")
            self.assertTrue(metrics is not None and metrics.ps_degraded)
            self.assertEqual(
                ctrl.last_activity_ts, marker, "fail-closed: таймер не сбрасывается"
            )
            self.assertTrue(any("watchdog_ps_degraded" in line for line in logs), logs)
        finally:
            _hard_kill(proc)

    def test_ps_degraded_stub_metrics_never_count_as_progress(self) -> None:
        degraded = WatchdogMetrics(
            pgid=1,
            alive=True,
            descendant_pids=(),
            new_descendants=(),
            cpu_time_s=9.0,
            cpu_delta_s=5.0,
            ps_degraded=True,
        )
        self.assertFalse(degraded.has_progress)


class ExecuteLoopTests(unittest.TestCase):
    def _controller(
        self, clock: _FakeClock, **kwargs: Any
    ) -> AdaptiveTimeoutController:
        params: dict[str, Any] = dict(
            idle_timeout_s=1000.0,
            safety_cap_s=1800.0,
            finish_reserve_s=0.0,
            watchdog_enabled=False,
            clock=clock,
        )
        params.update(kwargs)
        return AdaptiveTimeoutController(**params)

    def test_check_throttled_in_execute(self) -> None:
        # (а) 100 событий за 1 с реального времени: check() не вызывается чаще 1 раза.
        clock = _FakeClock()
        spy = _SpyController(self._controller(clock))
        events = [("text", "x")] * 100 + [("done", (0, "", {}))]
        out = _execute_with_clock(clock, _fake_run(clock, spy, events, empty_ticks=0))
        self.assertEqual(out["state"], "done")
        self.assertLessEqual(spy.check_calls, 1)
        self.assertEqual(spy.activity, ["text"] * 100)

        # (б) пустая очередь 12 тиков по 1 с: проверка идёт раз в WATCHDOG_INTERVAL_S.
        clock = _FakeClock()
        spy = _SpyController(self._controller(clock))
        out = _execute_with_clock(
            clock, _fake_run(clock, spy, [("done", (0, "ok", {}))], empty_ticks=12)
        )
        self.assertEqual(out["state"], "done")
        self.assertGreaterEqual(spy.check_calls, 1)
        self.assertLess(spy.check_calls, 12)
        self.assertEqual(spy.check_calls, 2)  # на 5-й и 10-й секундах

    def test_all_activity_kinds_reach_controller(self) -> None:
        clock = _FakeClock()
        spy = _SpyController(self._controller(clock))
        events = [
            ("init", {"conversation_id": "c1", "tools": 0, "permission_mode": ""}),
            ("reasoning", "r"),
            ("text", "t"),
            ("tool_trace", {"name": "run_command"}),
            ("result", {"status": "OK", "usage": {}}),
            ("done", (0, "t", {})),
        ]
        out = _execute_with_clock(clock, _fake_run(clock, spy, events, empty_ticks=0))
        self.assertEqual(out["state"], "done")
        # result/done — терминальные события и активностью не считаются.
        self.assertEqual(spy.activity, ["init", "reasoning", "text", "tool_trace"])

    def test_idle_timeout_returns_state_in_execute(self) -> None:
        clock = _FakeClock()
        ctrl = self._controller(clock, idle_timeout_s=8.0)
        out = _execute_with_clock(clock, _fake_run(clock, ctrl, [], empty_ticks=30))
        self.assertEqual(out["state"], "idle_timeout")
        self.assertEqual(out["rc"], 124)
        self.assertIn("idle timeout", out["err"])

    def test_child_exited_is_not_error(self) -> None:
        clock = _FakeClock()
        spy = _SpyController(
            self._controller(clock), forced=(True, "child_exited", None)
        )
        events = [("text", "hi"), ("done", (0, "hi", {}))]
        out = _execute_with_clock(clock, _fake_run(clock, spy, events, empty_ticks=7))
        self.assertGreaterEqual(spy.check_calls, 1)
        self.assertEqual(out["state"], "done")
        self.assertEqual(out["rc"], 0)
        self.assertEqual(out["text"], "hi")

    def test_absolute_cap_maps_to_timeout(self) -> None:
        clock = _FakeClock()
        pure = AdaptiveTimeoutController(
            idle_timeout_s=1000.0,
            safety_cap_s=0.2,
            finish_reserve_s=0.0,
            watchdog_enabled=False,
            clock=clock,
        )
        clock.advance(0.25)
        self.assertEqual(pure.check()[:2], (True, "absolute_cap"))

        clock = _FakeClock()
        ctrl = self._controller(clock, safety_cap_s=7.0)
        out = _execute_with_clock(clock, _fake_run(clock, ctrl, [], empty_ticks=30))
        self.assertEqual(out["state"], "timeout")
        self.assertEqual(out["rc"], 124)
        self.assertEqual(srv.Handler._error_body(out)["type"], "timeout")


class KillSwitchTests(unittest.TestCase):
    def test_flag_values(self) -> None:
        for value in ("0", "false", "no", "off", "False", "OFF"):
            with (
                self.subTest(value=value),
                mock.patch.dict(os.environ, {"BRIDGE_ENABLE_ADAPTIVE_WATCHDOG": value}),
            ):
                self.assertFalse(srv._is_watchdog_enabled())
        for value in ("1", "true", "yes", "on"):
            with (
                self.subTest(value=value),
                mock.patch.dict(os.environ, {"BRIDGE_ENABLE_ADAPTIVE_WATCHDOG": value}),
            ):
                self.assertTrue(srv._is_watchdog_enabled())
        with mock.patch.dict(os.environ):
            os.environ.pop("BRIDGE_ENABLE_ADAPTIVE_WATCHDOG", None)
            self.assertTrue(srv._is_watchdog_enabled())

    def test_idle_timeout_env_validation(self) -> None:
        for raw in ("abc", "-5", "0", "nan", "inf"):
            with (
                self.subTest(raw=raw),
                mock.patch.dict(os.environ, {"AGY_BRIDGE_IDLE_TIMEOUT": raw}),
                mock.patch.object(srv, "_log") as log,
            ):
                self.assertEqual(srv._idle_timeout_from_env(), 300.0)
                log.assert_called_once()
        with mock.patch.dict(os.environ, {"AGY_BRIDGE_IDLE_TIMEOUT": "12.5"}):
            self.assertEqual(srv._idle_timeout_from_env(), 12.5)
        with mock.patch.dict(os.environ):
            os.environ.pop("AGY_BRIDGE_IDLE_TIMEOUT", None)
            self.assertEqual(srv._idle_timeout_from_env(), 300.0)

    @unittest.skipUnless(_POSIX, "нужны процессные группы POSIX")
    def test_killswitch_disables_watchdog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            launcher = Path(tmp) / "fake-launcher.sh"
            launcher.write_text("#!/bin/sh\nexec sleep 100\n", encoding="utf-8")
            launcher.chmod(0o755)
            runs: list[Any] = []

            def make_run() -> Any:
                run = srv.Run("ping", "m", "low", "default", "", "tag")
                runs.append(run)
                return run

            try:
                with (
                    mock.patch.object(srv, "_launcher", return_value=str(launcher)),
                    mock.patch.object(srv, "WORKSPACE", Path(tmp) / "ws"),
                    mock.patch.object(ProcessWatchdog, "_run_ps") as run_ps,
                ):
                    with mock.patch.dict(
                        os.environ, {"BRIDGE_ENABLE_ADAPTIVE_WATCHDOG": "0"}
                    ):
                        off = make_run()
                        self.assertEqual(
                            off.controller.idle_timeout_s, float(srv.TIMEOUT_S)
                        )
                        self.assertIs(off.controller.watchdog_enabled, False)
                        self.assertEqual(
                            off.controller.safety_cap_s, float(srv.TIMEOUT_S)
                        )
                        self.assertEqual(off.controller.finish_reserve_s, 0.0)
                        off.controller.check(off.proc.pid)
                        run_ps.assert_not_called()  # ни seed, ни check не зовут ps
                    with mock.patch.dict(
                        os.environ, {"BRIDGE_ENABLE_ADAPTIVE_WATCHDOG": "1"}
                    ):
                        on = make_run()
                        self.assertEqual(
                            on.controller.idle_timeout_s, srv.IDLE_TIMEOUT_S
                        )
                        self.assertIs(on.controller.watchdog_enabled, True)
                        self.assertEqual(
                            on.controller.safety_cap_s, float(srv.TIMEOUT_S)
                        )
            finally:
                for run in runs:
                    run.close()


class ErrorContractTests(unittest.TestCase):
    def test_error_body_idle_timeout_http_504(self) -> None:
        body = srv.Handler._error_body({"state": "idle_timeout", "rc": 124})
        self.assertEqual(body["code"], 504)
        self.assertEqual(body["type"], "idle_timeout")
        self.assertIn(f"idle timeout after {srv.IDLE_TIMEOUT_S:g}s", body["message"])
        self.assertIn("idle timeout after 300s", body["message"])

    def _out(self) -> dict:
        return {
            "state": "idle_timeout",
            "rc": 124,
            "text": "",
            "usage": {},
            "result": {},
            "err": "x",
            "tool_calls": [],
            "tool_events": 0,
            "conversation_id": "",
        }

    def test_sse_error_chunk_idle_timeout(self) -> None:
        frames: list[str] = []
        handler = srv.Handler.__new__(srv.Handler)
        handler.send_response = lambda *_a, **_k: None
        handler.send_header = lambda *_a, **_k: None
        handler.end_headers = lambda: None
        handler._emit = lambda data: frames.append(data) or True
        handler._run_once = lambda *_a, **_k: self._out()
        handler._serve_sse({"model": "m"})
        self.assertGreaterEqual(len(frames), 3)
        self.assertEqual(frames[-1], "data: [DONE]\n\n")
        error_frame = frames[-2]
        self.assertTrue(
            error_frame.startswith("data: ") and error_frame.endswith("\n\n")
        )
        payload = json.loads(error_frame[len("data: ") :])
        self.assertEqual(payload["error"]["type"], "idle_timeout")
        self.assertEqual(payload["error"]["code"], 504)
        # ни finish_reason=stop, ни usage-кадра после ошибки быть не должно
        self.assertFalse(any('"finish_reason": "stop"' in f for f in frames))

    def test_json_mode_idle_timeout_is_504(self) -> None:
        sent: list[tuple] = []
        handler = srv.Handler.__new__(srv.Handler)
        handler._send = lambda code, payload: sent.append((code, payload))
        handler._run_once = lambda *_a, **_k: self._out()
        handler._serve_json({"model": "m"})
        self.assertEqual(len(sent), 1)
        code, payload = sent[0]
        self.assertEqual(code, 504)
        self.assertEqual(payload["error"]["type"], "idle_timeout")


@unittest.skipUnless(_POSIX, "нужны процессные группы POSIX")
class KillGroupTests(unittest.TestCase):
    def test_kill_group_cleans_descendants_and_reaps_zombie(self) -> None:
        proc = _spawn(["sh", "-c", "sleep 100 & sleep 100 & wait"])
        try:
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                out = subprocess.run(
                    ["ps", "-o", "pid=", "-g", str(proc.pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if len(out.stdout.split()) >= 3:  # лидер + два sleep
                    break
                time.sleep(0.05)
            self.assertGreaterEqual(len(out.stdout.split()), 3, "потомки не стартовали")
            srv._kill_group(proc)
            self.assertIsNotNone(proc.returncode)
            self.assertTrue(
                _group_gone(proc.pid), "потомки группы пережили _kill_group"
            )
            self.assertEqual(_ps_stat(proc.pid), "", "лидер остался зомби")
        finally:
            _hard_kill(proc)

    def test_kill_group_reaps_when_group_already_gone(self) -> None:
        proc = _spawn(["true"])
        try:
            deadline = time.monotonic() + 3.0
            while _ps_stat(proc.pid) != "Z" and time.monotonic() < deadline:
                time.sleep(0.05)  # лидер завершён и ещё не собран
            with (
                mock.patch.object(srv.os, "killpg", side_effect=ProcessLookupError),
                mock.patch.object(proc, "wait", wraps=proc.wait) as wait,
            ):
                srv._kill_group(proc)  # не должен падать
            wait.assert_called()
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(_ps_stat(proc.pid), "", "зомби не собран")
        finally:
            _hard_kill(proc)

    def test_kill_group_escalates_to_sigkill(self) -> None:
        self.assertEqual(srv.KILL_TERM_GRACE_S, 2.0)
        self.assertEqual(srv.KILL_WAIT_S, 5.0)
        proc = _spawn(
            ["sh", "-c", "trap '' TERM; echo ready; while :; do sleep 1; done"],
            stdout=subprocess.PIPE,
        )
        try:
            self.assertEqual(
                proc.stdout.readline().strip(), b"ready"
            )  # trap уже установлен
            started = time.monotonic()
            with mock.patch.object(srv, "KILL_TERM_GRACE_S", 0.4):
                srv._kill_group(proc)
            elapsed = time.monotonic() - started
            self.assertEqual(proc.returncode, -signal.SIGKILL)
            self.assertGreaterEqual(
                elapsed, 0.35, "SIGKILL раньше окончания grace-периода"
            )
            self.assertLess(elapsed, 2.0 + 5.0)
            self.assertTrue(_group_gone(proc.pid))
        finally:
            _hard_kill(proc)
            if proc.stdout is not None:
                proc.stdout.close()


def _load_fetch_script() -> Any:
    if not _FETCH_SCRIPT.is_file():
        raise unittest.SkipTest(f"нет {_FETCH_SCRIPT}")
    scripts_dir = str(_FETCH_SCRIPT.parent)
    spec = importlib.util.spec_from_file_location(
        "fetch_via_playwright_under_test", _FETCH_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    added = scripts_dir not in sys.path
    if added:
        sys.path.insert(
            0, scripts_dir
        )  # `from _paths import ...` при пустом __package__
    try:
        spec.loader.exec_module(module)
    finally:
        if added and scripts_dir in sys.path:
            sys.path.remove(scripts_dir)
    return module


class FetchViaPlaywrightHotfixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fetch = _load_fetch_script()

    def setUp(self) -> None:
        with self.fetch._progress["lock"]:
            self.fetch._progress["pending"].clear()
            self.fetch._progress["completed"] = 0

    def test_fetch_one_timeout_isolated(self) -> None:
        fetch = self.fetch
        cancelled: list[str] = []

        async def fetch_one(src: dict, ctx: Any, ctx_r: Any, cutoff: Any) -> tuple:
            try:
                await asyncio.sleep(30)
            finally:
                cancelled.append(src["id"])
            return src["id"], ["never"], None

        async def fetch_one_no_rss(src: dict, ctx: Any, cutoff: Any) -> tuple:
            return src["id"], ["ok"], None

        async def scenario() -> list:
            return await asyncio.gather(
                fetch._track_fetch_one({"id": "hung"}, None, None, None, fetch_one),
                fetch._track_fetch_one(
                    {"id": "good"}, None, None, None, fetch_one_no_rss
                ),
            )

        self.assertEqual(fetch.FETCH_ONE_TIMEOUT_S, 60.0)
        started = time.monotonic()
        with mock.patch.object(fetch, "FETCH_ONE_TIMEOUT_S", 0.1):
            results = asyncio.run(scenario())
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(results[0], ("hung", [], "timeout after 60s"))
        self.assertEqual(results[1], ("good", ["ok"], None))
        self.assertEqual(cancelled, ["hung"], "зависший источник должен быть отменён")
        self.assertEqual(fetch._progress["pending"], set())
        self.assertEqual(fetch._progress["completed"], 2)

    def test_page_close_bounded(self) -> None:
        fetch = self.fetch
        self.assertEqual(fetch.PAGE_CLOSE_TIMEOUT_S, 5.0)

        class _HungPage:
            async def close(self) -> None:
                await asyncio.sleep(30)

        class _BrokenPage:
            async def close(self) -> None:
                raise RuntimeError("Target closed")

        async def scenario() -> None:
            await fetch._safe_close_page(_HungPage())
            await fetch._safe_close_page(_BrokenPage())

        started = time.monotonic()
        with mock.patch.object(fetch, "PAGE_CLOSE_TIMEOUT_S", 0.1):
            asyncio.run(scenario())  # исключения подавлены
        self.assertLess(time.monotonic() - started, 2.0)

    def test_no_bare_page_close_left(self) -> None:
        text = _FETCH_SCRIPT.read_text(encoding="utf-8")
        bare = [
            n
            for n, line in enumerate(text.splitlines(), 1)
            if line.strip() == "await page.close()"
        ]
        self.assertEqual(bare, [], f"голые await page.close(): строки {bare}")


if __name__ == "__main__":
    unittest.main()
