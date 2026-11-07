"""Graceful drain саб-мостов (agy / claude-p / opencode-zen) при SIGTERM/SIGINT.

Корень инцидента «upstream stream ended before finish_reason»: обработчики сигналов мостов
падали (`TypeError` у agy), брали lock и звали `os._exit(0)` (claude-p) либо отсутствовали
(opencode-zen), поэтому in-flight SSE обрывались без `finish_reason` и `data: [DONE]`.

Тесты: L1 — чистая логика `core.subbridge_lifecycle` на виртуальных данных; L2 — реальные
подпроцессы мостов с настоящим `SIGTERM` (микро-тайминги) и in-process HTTP-проверки подключения.
"""

from __future__ import annotations

import ast
import contextlib
import http.client
import importlib
import importlib.util
import json
import os
import plistlib
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
BRIDGES = REPO / "bridges"
KEY = "drain-test-key"


def lifecycle_mod() -> Any:
    return importlib.import_module("core.subbridge_lifecycle")


def make_life(**kwargs: Any) -> Any:
    mod = lifecycle_mod()
    config = mod.SubbridgeDrainConfig(
        drain_timeout_s=kwargs.pop("drain_timeout_s", 0.3),
        kill_term_grace_s=0.2,
        kill_wait_s=0.2,
        flush_grace_s=kwargs.pop("flush_grace_s", 0.3),
        poll_interval_s=0.005,
        safety_margin_s=0.1,
    )
    return mod.SubbridgeLifecycle(config, mod.SubbridgeHooks(**kwargs))


class FakeServer:
    """Минимальный двойник `ThreadingHTTPServer`: serve_forever блокируется до shutdown."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self.shutdown_calls = 0
        self.closed = False
        self.turns_at_shutdown: int | None = None
        self.turns_probe: Any = None

    def serve_forever(self) -> None:
        self._stop.wait(5)

    def shutdown(self) -> None:
        self.shutdown_calls += 1
        if self.turns_probe is not None:
            self.turns_at_shutdown = self.turns_probe()
        self._stop.set()

    def server_close(self) -> None:
        self.closed = True


# ---- L1: конфигурация и чистая логика ------------------------------------------------
def test_config_defaults_match_core_lifecycle() -> None:
    cfg = lifecycle_mod().SubbridgeDrainConfig.from_env({})
    assert (
        cfg.enabled,
        cfg.drain_timeout_s,
        cfg.exit_timeout_s,
        cfg.retry_after_s,
    ) == (True, 110.0, 180.0, 5)
    assert (cfg.kill_term_grace_s, cfg.kill_wait_s, cfg.flush_grace_s) == (
        2.0,
        3.0,
        2.0,
    )
    assert (cfg.poll_interval_s, cfg.safety_margin_s) == (0.05, 5.0)
    assert cfg.effective_drain_timeout_s == 110.0


def test_config_reads_env_and_ignores_garbage() -> None:
    cfg = lifecycle_mod().SubbridgeDrainConfig.from_env(
        {
            "BRIDGE_ENABLE_GRACEFUL_DRAIN": "false",
            "BRIDGE_DRAIN_TIMEOUT_S": "7",
            "BRIDGE_RETRY_AFTER_S": "9",
            "BRIDGE_KILL_WAIT_S": "nan",
            "BRIDGE_DRAIN_FLUSH_GRACE_S": "-1",
        }
    )
    assert (cfg.enabled, cfg.drain_timeout_s, cfg.retry_after_s) == (False, 7.0, 9)
    assert (cfg.kill_wait_s, cfg.flush_grace_s) == (3.0, 2.0)


def test_effective_drain_timeout_is_clamped_below_exit_timeout() -> None:
    cfg_cls = lifecycle_mod().SubbridgeDrainConfig
    assert cfg_cls.from_env(
        {"BRIDGE_EXIT_TIMEOUT_S": "100"}
    ).effective_drain_timeout_s == pytest.approx(88.0)
    assert cfg_cls.from_env(
        {"BRIDGE_EXIT_TIMEOUT_S": "5"}
    ).effective_drain_timeout_s == pytest.approx(0.05)


def test_long_drain_is_clamped_to_real_exit_timeout_not_extending_it() -> None:
    """F-002 (Seat 1): удлинённый drain не раздувает `exit_timeout_s` (реальный `ExitTimeOut` launchd)."""
    cfg_cls = lifecycle_mod().SubbridgeDrainConfig
    explicit = cfg_cls.from_env(
        {"BRIDGE_EXIT_TIMEOUT_S": "180", "BRIDGE_DRAIN_TIMEOUT_S": "300"}
    )
    assert explicit.exit_timeout_s == 180.0
    assert explicit.effective_drain_timeout_s == pytest.approx(168.0)
    derived = cfg_cls.from_env({"BRIDGE_DRAIN_TIMEOUT_S": "300"})
    assert (
        derived.exit_timeout_s == 180.0
    )  # без `BRIDGE_EXIT_TIMEOUT_S` остаётся дефолт
    assert derived.effective_drain_timeout_s == pytest.approx(
        168.0
    )  # клампится под него
    short = cfg_cls.from_env({"BRIDGE_DRAIN_TIMEOUT_S": "20"})
    assert short.exit_timeout_s == 180.0
    assert short.effective_drain_timeout_s == pytest.approx(20.0)
    assert cfg_cls.from_env({}).exit_timeout_s == 180.0


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, True),
        ({"DSH_BRIDGE_DRAIN_ENABLED": "false"}, False),
        ({"BRIDGE_DRAIN_ON_SHUTDOWN": "0"}, False),
        ({"BRIDGE_DRAIN_ON_SHUTDOWN": "0", "DSH_BRIDGE_DRAIN_ENABLED": "true"}, False),
        (
            {"BRIDGE_ENABLE_GRACEFUL_DRAIN": "true", "BRIDGE_DRAIN_ON_SHUTDOWN": "0"},
            True,
        ),
        (
            {"BRIDGE_ENABLE_GRACEFUL_DRAIN": "off", "DSH_BRIDGE_DRAIN_ENABLED": "1"},
            False,
        ),
    ],
)
def test_drain_enabled_honours_hub_env_names(
    env: dict[str, str], expected: bool
) -> None:
    """F-003 (Seat 1): флаг drain саб-моста понимает и переменные `HubLifecycleManager`."""
    cfg = lifecycle_mod().SubbridgeDrainConfig.from_env(env)
    assert cfg.enabled is expected


def test_effective_timers_fit_kill_budget_under_short_exit_timeout() -> None:
    cfg_cls = lifecycle_mod().SubbridgeDrainConfig
    legacy = cfg_cls.from_env({"BRIDGE_EXIT_TIMEOUT_S": "5"}).effective_timers()
    assert legacy.kill_term_grace_s + legacy.kill_wait_s == pytest.approx(0.2)
    assert legacy.kill_term_grace_s / legacy.kill_wait_s == pytest.approx(2.0 / 3.0)
    mid = cfg_cls.from_env({"BRIDGE_EXIT_TIMEOUT_S": "14"}).effective_timers()
    assert mid.kill_term_grace_s + mid.kill_wait_s == pytest.approx(4.5)  # (14-5)*0.5
    roomy = cfg_cls.from_env({"BRIDGE_EXIT_TIMEOUT_S": "180"})
    assert roomy.effective_timers() is roomy


def test_force_kill_uses_clamped_timers_under_short_exit_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = lifecycle_mod()
    seen: list[tuple[float, float]] = []
    monkeypatch.setattr(
        mod,
        "terminate_proc_groups_parallel",
        lambda procs, term, wait: seen.append((term, wait)),
    )
    cfg = mod.SubbridgeDrainConfig.from_env({"BRIDGE_EXIT_TIMEOUT_S": "5"})
    mod.SubbridgeLifecycle(cfg, mod.SubbridgeHooks(procs_fn=lambda: [])).force_kill()
    assert len(seen) == 1 and sum(seen[0]) == pytest.approx(0.2)


def test_lifecycle_reuses_hub_manager_and_shared_defaults() -> None:
    """F-001 (Seat 3): единый координатор — наследник `HubLifecycleManager` с общими дефолтами."""
    from core.lifecycle import DEFAULT_DRAIN_SECONDS, RETRY_AFTER_S, HubLifecycleManager

    mod = lifecycle_mod()
    assert issubclass(mod.SubbridgeLifecycle, HubLifecycleManager)
    cfg = mod.SubbridgeDrainConfig()
    assert cfg.drain_timeout_s == DEFAULT_DRAIN_SECONDS == 110.0
    assert cfg.retry_after_s == RETRY_AFTER_S
    life = mod.SubbridgeLifecycle(cfg)
    assert life.drain_timeout_s == cfg.effective_drain_timeout_s
    assert life.retry_after_s == cfg.retry_after_s


def test_short_exit_timeout_threshold_is_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-005 (Seat 3): порог короткого `ExitTimeOut` настраивается, дефолт 15 с."""
    cfg = lifecycle_mod().SubbridgeDrainConfig.from_env({"BRIDGE_EXIT_TIMEOUT_S": "14"})
    assert cfg.effective_timers().kill_term_grace_s == pytest.approx(1.8)
    monkeypatch.setenv("BRIDGE_SHORT_EXIT_TIMEOUT_S", "1")
    assert cfg.effective_timers() is cfg  # порог ниже `ExitTimeOut`: сжатия нет
    monkeypatch.setenv("BRIDGE_SHORT_EXIT_TIMEOUT_S", "20")
    assert cfg.effective_timers().kill_term_grace_s == pytest.approx(1.8)


def test_force_kill_is_idempotent_per_shutdown_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-001 (Seat 1): повторной зачистки (и второго `ps`) в одном цикле остановки нет."""
    mod = lifecycle_mod()
    scans: list[int] = []
    monkeypatch.setattr(mod, "child_process_groups", lambda: scans.append(1) or [])
    life = make_life()
    life.force_kill()
    life.force_kill()
    assert scans == [1]
    life.reset()
    life.force_kill()
    assert scans == [1, 1]  # новый цикл остановки — новая зачистка


def test_serve_forever_reaps_orphans_on_startup() -> None:
    """F-001: саб-мосты чистят сирот при старте так же, как `dsh-hub` и `muse-bridge`."""
    life = make_life(force_kill_fn=lambda: None)
    reaped: list[int] = []
    life.reap_orphans_on_startup = lambda *a, **kw: reaped.append(1)
    server = FakeServer()
    thread, _ = run_serve(life, server)
    life.handle_signal(signal.SIGTERM)
    thread.join(3)
    assert reaped == [1]


def test_reap_failure_does_not_block_bridge_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    life = make_life(force_kill_fn=lambda: None)
    monkeypatch.setattr(life, "reap_orphans_on_startup", _raise(OSError("ps failed")))
    server = FakeServer()
    thread, rc = run_serve(life, server)
    life.handle_signal(signal.SIGTERM)
    thread.join(3)
    assert rc == [0] and server.shutdown_calls == 1


def test_track_turn_admits_and_counts_atomically_and_rejects_when_draining() -> None:
    life = make_life(procs_fn=lambda: [])
    with life.track_turn("/v1/chat/completions") as admitted:
        assert admitted is None and life.active_http_turns == 1
        life.handle_signal(signal.SIGTERM)
        with life.track_turn("/v1/chat/completions") as rejected:
            assert rejected is not None and rejected[0] == 503
            assert life.active_http_turns == 1  # отклонённый ход не учитывается
        with life.track_turn("/v1/cancel") as cancel:
            assert cancel is None and life.active_http_turns == 2
        assert life.active_http_turns == 1  # выход отклонённого хода счётчик не трогает
    assert life.active_http_turns == 0


def test_no_turn_is_admitted_uncounted_around_drain_barrier() -> None:
    life = make_life(procs_fn=lambda: [])
    admitted: list[int] = []
    start = threading.Barrier(9)

    def worker() -> None:
        start.wait()
        for _ in range(200):
            if life.enter_turn("/v1/chat/completions") is None:
                admitted.append(1)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    start.wait()
    life.run_drain_once(FakeServer())  # ставит барьер под тем же замком, что и допуск
    snapshot = life.active_http_turns
    for t in threads:
        t.join()
    assert (
        life.active_http_turns == snapshot == len(admitted)
    )  # после барьера допуска нет


def test_signal_handler_is_lock_free_assignment_only() -> None:
    """RW-007: в теле обработчика нет вызовов (Event.set / Lock / I/O / kill), только присваивания."""
    src = (REPO / "core" / "subbridge_lifecycle.py").read_text(encoding="utf-8")
    func = next(
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == "handle_signal"
    )
    calls = [
        n.func.id
        for n in ast.walk(func)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    ]
    assert calls == ["int"]
    assert not [
        n
        for n in ast.walk(func)
        if isinstance(n, ast.Attribute)
        and isinstance(n.ctx, ast.Load)
        and n.attr in {"set", "acquire", "release", "wait"}
    ]
    life = make_life()
    assert not life.is_draining()
    life.handle_signal(signal.SIGTERM, None)
    assert life.is_draining() and life.last_signal == signal.SIGTERM


def test_admission_rejection_and_health_when_draining() -> None:
    life = make_life()
    assert life.admission_rejection("/v1/chat/completions") is None
    assert (
        life.apply_health({"ok": True}) == {"ok": True} and life.health_headers() == {}
    )
    life.handle_signal(signal.SIGINT)
    status, headers, body = life.admission_rejection("/v1/chat/completions")
    assert status == 503 and headers == {
        "Retry-After": "5",
        "X-Bridge-Draining": "true",
    }
    assert body["error"] == {
        "message": "Bridge is draining for restart, please retry",
        "type": "overloaded",
        "code": 503,
    }
    assert life.admission_rejection("/v1/chat/completions/abc/cancel") is None
    assert life.apply_health({"ok": True, "active": 1}) == {
        "ok": False,
        "draining": True,
        "active": 1,
    }
    assert life.health_headers() == {"X-Bridge-Draining": "true"}


def test_track_turn_counts_until_exit_and_survives_errors() -> None:
    life = make_life(procs_fn=lambda: [])
    with life.track_turn():
        assert life.active_http_turns == 1 and life.active_count() == 1
        with pytest.raises(RuntimeError), life.track_turn():
            assert life.active_http_turns == 2
            raise RuntimeError("boom")
        assert life.active_http_turns == 1
    assert life.active_http_turns == 0 and life.active_count() == 0


def test_active_count_is_max_of_turns_and_processes() -> None:
    life = make_life(procs_fn=lambda: [object(), object()])  # type: ignore[list-item]
    assert life.active_count() == 2
    with life.track_turn():
        assert life.active_count() == 2


def spawn_sleeper(
    seconds: float = 30, ignore_term: bool = False
) -> subprocess.Popen[bytes]:
    code = "import signal,time\n" + (
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if ignore_term else ""
    )
    code += f"print('up',flush=True)\ntime.sleep({seconds})"
    proc = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, start_new_session=True
    )
    assert (
        proc.stdout is not None and proc.stdout.readline()
    )  # дождаться установки обработчика сигнала
    return proc


def test_terminate_groups_parallel_has_bounded_budget_and_kills_stubborn() -> None:
    procs = [spawn_sleeper(ignore_term=i % 2 == 1) for i in range(4)]
    start = time.monotonic()
    lifecycle_mod().terminate_proc_groups_parallel(procs, 0.3, 1.0)
    elapsed = time.monotonic() - start
    assert all(p.poll() is not None for p in procs)
    assert (
        elapsed < 0.3 + 1.0
    )  # не зависит от числа процессов: общий бюджет, а не сумма
    assert {p.returncode for p in procs} == {-signal.SIGTERM, -signal.SIGKILL}


def test_terminate_groups_skips_own_group_and_invalid_pgid() -> None:
    own = type("P", (), {"pid": os.getpgrp(), "poll": lambda self: None})()
    bad = type("P", (), {"pid": 1, "poll": lambda self: None})()
    lifecycle_mod().terminate_proc_groups_parallel([own, bad], 0.01, 0.01)  # type: ignore[list-item]


def run_serve(life: Any, server: FakeServer) -> tuple[threading.Thread, list[int]]:
    rc: list[int] = []
    thread = threading.Thread(
        target=lambda: rc.append(life.serve_forever(server, install_signals=False))
    )
    thread.start()
    return thread, rc


def test_serve_forever_waits_for_active_turn_then_exits_zero() -> None:
    kills: list[int] = []
    cleanups: list[int] = []
    life = make_life(
        drain_timeout_s=2.0,
        force_kill_fn=lambda: kills.append(1),
        cleanup_fn=lambda: cleanups.append(1),
    )
    server = FakeServer()
    server.turns_probe = lambda: life.active_http_turns
    thread, rc = run_serve(life, server)
    with life.track_turn():
        life.handle_signal(signal.SIGTERM)
        time.sleep(0.05)
        assert server.shutdown_calls == 0  # ход ещё идёт: сервер не останавливается
    thread.join(2)
    assert rc == [0] and server.shutdown_calls == 1 and server.turns_at_shutdown == 0
    assert server.closed and not life.forced_kill
    assert kills == []  # F-001: штатный drain не повторяет зачистку (и лишний `ps`)
    assert cleanups == [1]  # cleanup_fn всё равно вызывается один раз


def test_serve_forever_force_kills_outside_signal_and_waits_for_flush() -> None:
    killed = threading.Event()
    life = make_life(drain_timeout_s=0.05, force_kill_fn=killed.set)
    server = FakeServer()
    server.turns_probe = lambda: life.active_http_turns
    thread, rc = run_serve(life, server)

    def turn() -> None:
        with life.track_turn():
            killed.wait(2)  # ход завершается только после принудительной зачистки
            time.sleep(0.05)  # и ещё «дописывает» терминальный кадр + [DONE]

    worker = threading.Thread(target=turn)
    worker.start()
    time.sleep(0.02)
    life.handle_signal(signal.SIGTERM)
    thread.join(3)
    worker.join(1)
    assert life.forced_kill and killed.is_set()
    assert server.turns_at_shutdown == 0  # shutdown только после дозаписи кадров
    assert rc == [0]


def test_drain_disabled_skips_waiting() -> None:
    mod = lifecycle_mod()
    cfg = mod.SubbridgeDrainConfig(
        enabled=False, flush_grace_s=0.01, poll_interval_s=0.005
    )
    life = mod.SubbridgeLifecycle(cfg, mod.SubbridgeHooks(force_kill_fn=lambda: None))
    server = FakeServer()
    thread, _ = run_serve(life, server)
    with life.track_turn():
        life.handle_signal(signal.SIGTERM)
        thread.join(2)
    assert life.forced_kill and server.shutdown_calls == 1


def test_install_wraps_post_and_health_of_a_real_handler() -> None:
    from http.server import BaseHTTPRequestHandler

    class H(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def do_POST(self) -> None:  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

    life = make_life(procs_fn=lambda: [])
    life.install(H)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(
        target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True
    ).start()
    port = httpd.server_address[1]

    def call(method: str, path: str) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request(method, path, body=b"{}" if method == "POST" else None)
        resp = conn.getresponse()
        data = (resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read())
        conn.close()
        return data

    try:
        assert call("POST", "/v1/chat/completions")[2] == b"ok"
        assert call("GET", "/health")[2] == b"ok"
        life.handle_signal(signal.SIGTERM)
        status, headers, body = call("POST", "/v1/chat/completions")
        assert (status, headers["retry-after"], headers["x-bridge-draining"]) == (
            503,
            "5",
            "true",
        )
        assert json.loads(body)["error"]["code"] == 503
        assert call("POST", "/v1/chat/completions/x/cancel")[2] == b"ok"
        status, headers, body = call("GET", "/v1/health")
        assert status == 200 and headers["x-bridge-draining"] == "true"
        assert json.loads(body)["ok"] is False and json.loads(body)["draining"] is True
    finally:
        httpd.shutdown()
        httpd.server_close()


# ---- L2: реальные подпроцессы мостов с настоящим SIGTERM -----------------------------------
def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class BridgeProc:
    def __init__(
        self, script: Path, env: dict[str, str], port: int, wait: bool = True
    ) -> None:
        full = {**os.environ, **env, "PYTHONUNBUFFERED": "1"}
        self.port = port
        self.proc = subprocess.Popen(
            [sys.executable, str(script)],
            env=full,
            cwd=str(REPO),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if wait:
            self.wait_ready()

    def request(
        self, method: str, path: str, body: bytes | None = None, timeout: float = 5.0
    ) -> http.client.HTTPResponse:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
        conn.request(method, path, body=body, headers=headers)
        return conn.getresponse()

    def wait_ready(self) -> None:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError(
                    f"bridge exited early rc={self.proc.returncode}: {self.output()}"
                )
            try:
                if self.request("GET", "/health", timeout=0.5).status == 200:
                    return
            except OSError:
                time.sleep(0.02)
        raise AssertionError("bridge did not start")

    def output(self) -> str:
        if self.proc.stdout is None or self.proc.poll() is None:
            return ""
        return self.proc.stdout.read().decode("utf-8", "replace")[-2000:]

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(5)
        if self.proc.stdout is not None:
            self.proc.stdout.close()


@contextlib.contextmanager
def running(script: Path, env: dict[str, str], port: int) -> Iterator[BridgeProc]:
    bridge = BridgeProc(script, env, port)
    try:
        yield bridge
    finally:
        bridge.stop()


IDLE_BRIDGES = [
    ("agy-bridge/server.py", "AGY_BRIDGE", {"AGY_BRIDGE_KEY": KEY}),
    (
        "opencode-zen-bridge/server.py",
        "OPENCODE_ZEN_BRIDGE",
        {"OPENCODE_ZEN_BRIDGE_KEY": KEY},
    ),
    ("claude-p-bridge/server.py", "CLAUDE_P_BRIDGE", {"CLAUDE_P_BRIDGE_KEY": KEY}),
]


def test_idle_bridges_sigterm_exit_zero_without_crash(tmp_path: Path) -> None:
    """Три моста стартуют параллельно (запуск интерпретатора дороже самого теста), затем настоящий SIGTERM."""
    bridges: list[BridgeProc] = []
    try:
        for script, prefix, extra in IDLE_BRIDGES:
            port = free_port()
            env = {
                **extra,
                f"{prefix}_PORT": str(port),
                "BRIDGE_DRAIN_TIMEOUT_S": "2",
                "OPENCODE_ZEN_BRIDGE_WORKSPACE": str(tmp_path),
            }
            bridges.append(BridgeProc(BRIDGES / script, env, port, wait=False))
        for bridge in bridges:
            bridge.wait_ready()
        for bridge in bridges:
            bridge.proc.send_signal(signal.SIGTERM)
        for bridge in bridges:
            assert bridge.proc.wait(10) == 0, bridge.output()
            assert "TypeError" not in bridge.output()
    finally:
        for bridge in bridges:
            bridge.stop()


def fake_claude(path: Path, sleep_s: float) -> Path:
    path.write_text(
        f"#!{sys.executable}\n"
        "import json, sys, time\n"
        "sys.stdin.read()\n"
        "def ev(t):\n"
        "    print(json.dumps({'type': 'stream_event', 'event': {'type': 'content_block_delta',\n"
        "          'delta': {'type': 'text_delta', 'text': t}}}), flush=True)\n"
        "ev('Hello ')\n"
        f"time.sleep({sleep_s})\n"
        "ev('world')\n"
        "print(json.dumps({'type': 'result', 'usage': {'input_tokens': 1, 'output_tokens': 2}}), flush=True)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def claude_env(binary: Path, port: int, **extra: str) -> dict[str, str]:
    return {
        "CLAUDE_P_BRIDGE_KEY": KEY,
        "CLAUDE_P_BRIDGE_PORT": str(port),
        "CLAUDE_P_BRIDGE_BIN": str(binary),
        "CLAUDE_P_BRIDGE_POLL_INTERVAL_S": "0.02",
        "CLAUDE_P_BRIDGE_STDERR_DRAIN_S": "0.01",
        **extra,
    }


def stream_request(bridge: BridgeProc) -> tuple[http.client.HTTPResponse, bytes]:
    body = json.dumps(
        {
            "model": "claude-sonnet-5-5",
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        }
    )
    resp = bridge.request(
        "POST", "/v1/chat/completions", body.encode("utf-8"), timeout=15
    )
    assert resp.status == 200
    buf = b""
    while b"Hello" not in buf:  # первый полезный чанк получен: ход точно в полёте
        line = resp.fp.readline() if resp.fp is not None else b""
        assert line, f"stream closed before first chunk: {buf!r}"
        buf += line
    return resp, buf


def test_claude_p_active_sse_turn_completes_with_finish_reason_and_done_on_sigterm(
    tmp_path: Path,
) -> None:
    port = free_port()
    env = claude_env(
        fake_claude(tmp_path / "claude", 0.3), port, BRIDGE_DRAIN_TIMEOUT_S="10"
    )
    with running(BRIDGES / "claude-p-bridge/server.py", env, port) as bridge:
        resp, buf = stream_request(bridge)
        bridge.proc.send_signal(signal.SIGTERM)
        health = bridge.request("GET", "/health")
        health_body = json.loads(health.read())
        assert (health_body["ok"], health_body["draining"]) == (False, True)
        assert health.getheader("X-Bridge-Draining") == "true"
        rejected = bridge.request(
            "POST",
            "/v1/chat/completions",
            b'{"messages":[{"role":"user","content":"x"}]}',
        )
        assert rejected.status == 503 and rejected.getheader("Retry-After") == "5"
        assert rejected.getheader("X-Bridge-Draining") == "true"
        rejected.read()
        buf += resp.read()
        assert bridge.proc.wait(10) == 0, bridge.output()
    text = buf.decode("utf-8")
    assert "world" in text and '"finish_reason": "stop"' in text
    assert '"error"' not in text
    assert text.endswith("data: [DONE]\n\n")


def test_claude_p_overdue_turn_is_killed_outside_signal_and_gets_terminal_frame(
    tmp_path: Path,
) -> None:
    port = free_port()
    env = claude_env(
        fake_claude(tmp_path / "claude", 30),
        port,
        BRIDGE_DRAIN_TIMEOUT_S="0.1",
        BRIDGE_KILL_TERM_GRACE_S="0.5",
        BRIDGE_KILL_WAIT_S="1",
    )
    with running(BRIDGES / "claude-p-bridge/server.py", env, port) as bridge:
        resp, buf = stream_request(bridge)
        started = time.monotonic()
        bridge.proc.send_signal(signal.SIGTERM)
        buf += resp.read()
        assert bridge.proc.wait(10) == 0, bridge.output()
        assert time.monotonic() - started < 5
    text = buf.decode("utf-8")
    assert '"error"' in text and '"finish_reason": "stop"' in text
    assert text.endswith(
        "data: [DONE]\n\n"
    )  # без сырого EOF: клиент видит терминальный кадр


# ---- L2: подключение в самих мостах (in-process, без CLI) ------------------------------------
def load_bridge(name: str, env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> Any:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "path", list(sys.path))
    path = BRIDGES / name / "server.py"
    spec = importlib.util.spec_from_file_location(
        f"drain_under_test_{name.replace('-', '_')}", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("name", "env"),
    [
        ("agy-bridge", {"AGY_BRIDGE_KEY": KEY}),
        ("claude-p-bridge", {"CLAUDE_P_BRIDGE_KEY": KEY}),
        ("opencode-zen-bridge", {"OPENCODE_ZEN_BRIDGE_KEY": KEY}),
    ],
)
def test_bridge_handler_is_wired_to_lifecycle(
    name: str, env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_bridge(name, env, monkeypatch)
    life = module._LIFECYCLE
    assert isinstance(life, lifecycle_mod().SubbridgeLifecycle)
    assert life.workspace == Path(module.WORKSPACE)  # сироты ищутся в своём workspace
    assert (
        not hasattr(module, "_kill_all") or name == "agy-bridge"
    )  # claude-p: опасный _kill_all удалён
    monkeypatch.setattr(life, "_signal_received", True)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    threading.Thread(
        target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True
    ).start()
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=3)
    try:
        conn.request(
            "POST",
            "/v1/chat/completions",
            body=b"{}",
            headers={"Authorization": f"Bearer {KEY}"},
        )
        resp = conn.getresponse()
        assert resp.status == 503
        assert (
            resp.getheader("Retry-After") == "5"
            and resp.getheader("X-Bridge-Draining") == "true"
        )
        conn.close()
        conn = http.client.HTTPConnection(
            "127.0.0.1", httpd.server_address[1], timeout=3
        )
        conn.request("GET", "/health")
        health = conn.getresponse()
        assert health.getheader("X-Bridge-Draining") == "true"
        body = json.loads(health.read())
        assert body["ok"] is False and body["draining"] is True
    finally:
        conn.close()
        httpd.shutdown()
        httpd.server_close()


def test_opencode_zen_registers_live_process_groups_for_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-002 (Seat 1): `procs_fn` отдаёт живые группы, а не полагается на поиск через `ps`."""
    from core.proc_groups import spawn_registered

    module = load_bridge(
        "opencode-zen-bridge", {"OPENCODE_ZEN_BRIDGE_KEY": KEY}, monkeypatch
    )
    assert module._LIFECYCLE.hooks.procs_fn is module.live_proc_groups
    assert (
        module.spawn_registered is spawn_registered
    )  # запуск потомков идёт через ядро
    proc = spawn_registered(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    try:
        assert proc.pid in [p.pid for p in module._LIFECYCLE.hooks.procs_fn()]
    finally:
        proc.kill()
        proc.wait(3)
    assert proc.pid not in [
        p.pid for p in module.live_proc_groups()
    ]  # завершённый выбывает


class _FakeProc:
    """Двойник `Popen`: `poll()` — `None`, пока `rc` не выставлен."""

    def __init__(self, pid: int, rc: int | None = None) -> None:
        self.pid, self.rc = pid, rc

    def poll(self) -> int | None:
        return self.rc


def test_register_proc_group_prunes_finished_leaders_without_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-001 (BLOCKER Seat 1): реестр не растёт в демоне и не держит закрытые `Popen`."""
    import core.proc_groups as pg

    monkeypatch.setattr(pg, "_group_alive", lambda _pgid: False)  # фиктивные PID
    pg.reset_proc_groups()
    try:
        finished = [_FakeProc(10_000 + i, rc=0) for i in range(50)]
        for proc in finished:
            pg.register_proc_group(
                proc
            )  # `live_proc_groups` не зовём: рост был бы здесь
        assert (
            len(pg._LIVE_PROCS) == 1
        )  # прошлые завершённые вычищены новой регистрацией
        alive = _FakeProc(20_000)
        pg.register_proc_group(alive)
        assert set(pg._LIVE_PROCS) == {20_000}  # последний завершённый тоже выбыл
        alive_two = _FakeProc(20_001)
        assert pg.register_proc_group(alive_two) is alive_two
        alive.rc = -15
        pg.register_proc_group(_FakeProc(20_002))
        assert set(pg._LIVE_PROCS) == {20_001, 20_002}
        assert [p.pid for p in pg.live_proc_groups()] == [20_001, 20_002]
        pg.reset_proc_groups()
        assert pg.live_proc_groups() == []
    finally:
        pg.reset_proc_groups()


def test_proc_group_registry_is_thread_safe_under_churn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.proc_groups as pg

    monkeypatch.setattr(pg, "_group_alive", lambda _pgid: False)  # фиктивные PID
    pg.reset_proc_groups()
    errors: list[BaseException] = []
    start = threading.Barrier(5)

    def worker(base: int) -> None:
        try:
            start.wait()
            for i in range(300):
                pg.register_proc_group(_FakeProc(base + i, rc=0 if i % 2 else None))
                pg.live_proc_groups()
        except BaseException as exc:  # noqa: BLE001 — любой сбой гонки провалит тест
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(b * 1000,)) for b in range(1, 5)]
    try:
        for t in threads:
            t.start()
        start.wait()
        for t in threads:
            t.join(10)
        assert errors == []
        assert all(p.poll() is None for p in pg.live_proc_groups())
    finally:
        pg.reset_proc_groups()


def test_proc_groups_public_surface_is_at_most_six_functions() -> None:
    """M-MOD-I2 (Seat 2 F-005): публичные функции `core/proc_groups.py` — ровно шесть."""
    import core.proc_groups as pg

    tree = ast.parse(Path(pg.__file__).read_text(encoding="utf-8"))
    public = {
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
    }
    assert public == {
        "register_proc_group",
        "live_proc_groups",
        "reset_proc_groups",
        "spawn_registered",
        "terminate_proc_groups_parallel",
        "child_process_groups",
    }


def test_agy_signal_handlers_are_not_the_process_supervisor_kill_all() -> None:
    """Регрессия: `signal.signal(SIGTERM, kill_all)` вызывал TypeError (kill_all принимает 1 аргумент)."""
    src = (BRIDGES / "agy-bridge" / "server.py").read_text(encoding="utf-8")
    assert "signal.signal(signal.SIGTERM, _kill_all)" not in src
    assert "signal.signal(signal.SIGINT, _kill_all)" not in src


def test_claude_p_signal_path_has_no_lock_sigkill_or_os_exit() -> None:
    src = (BRIDGES / "claude-p-bridge" / "server.py").read_text(encoding="utf-8")
    assert (
        "os._exit" not in src and "signal.signal(signal.SIGTERM, _kill_all)" not in src
    )


def test_child_process_groups_fallback_finds_and_kills_direct_children() -> None:
    """Мост без реестра `Popen` (opencode-zen): drain находит группы прямых потомков через `ps`."""
    mod = lifecycle_mod()
    proc = spawn_sleeper()
    try:
        assert proc.pid in [g.pid for g in mod.child_process_groups()]
        life = make_life()  # ни procs_fn, ни force_kill_fn
        life.force_kill()
        assert proc.wait(3) == -signal.SIGTERM
    finally:
        if proc.poll() is None:
            proc.kill()
        if proc.stdout is not None:
            proc.stdout.close()


def _raise(exc: Exception) -> Any:
    def fail(*_args: Any) -> Any:
        raise exc

    return fail


def test_active_count_survives_registry_mutation_race() -> None:
    boom = _raise(RuntimeError("dictionary changed size during iteration"))
    assert make_life(procs_fn=boom).active_count() == 0
    assert make_life(active_procs_fn=boom).active_count() == 0
    life = make_life(procs_fn=boom)
    with life.track_turn():
        assert life.active_count() == 1  # счётчик ходов остаётся нижней границей


@pytest.mark.parametrize("failing", ["procs_fn", "active_procs_fn", "log_fn"])
def test_drain_thread_always_calls_shutdown_when_hook_raises(failing: str) -> None:
    hooks: dict[str, Any] = {"force_kill_fn": lambda: None}
    hooks[failing] = _raise(RuntimeError("hook failure"))
    life = make_life(**hooks)
    server = FakeServer()
    thread, rc = run_serve(life, server)
    life.handle_signal(signal.SIGTERM)
    thread.join(3)
    assert not thread.is_alive() and rc == [0]
    assert server.shutdown_calls == 1 and life.is_draining()


def test_drain_survives_failing_server_shutdown_and_body_errors() -> None:
    class BrokenServer(FakeServer):
        def shutdown(self) -> None:
            super().shutdown()
            raise OSError("shutdown failed")

    life = make_life(procs_fn=lambda: [])
    server = BrokenServer()
    life.run_drain_once(server)  # исключение shutdown() не уходит из потока drain
    assert server.shutdown_calls == 1

    class Exploding(lifecycle_mod().SubbridgeLifecycle):
        def force_kill(self) -> None:
            raise ValueError("kill failed")

    mod = lifecycle_mod()
    cfg = mod.SubbridgeDrainConfig(drain_timeout_s=0.02, flush_grace_s=0.01)
    exploding = Exploding(cfg, mod.SubbridgeHooks(active_procs_fn=lambda: 1))
    server = FakeServer()
    with pytest.raises(ValueError):
        exploding.run_drain_once(server)
    assert server.shutdown_calls == 1  # shutdown вызван, несмотря на исключение в теле


def test_legacy_process_supervisor_kill_all_raises_typeerror_on_signal_frame_while_lifecycle_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_bridge("agy-bridge", {"AGY_BRIDGE_KEY": KEY}, monkeypatch)
    with pytest.raises(TypeError):
        module._supervisor.kill_all(signal.SIGTERM, None)
    life = module._LIFECYCLE
    life.handle_signal(signal.SIGTERM, None)
    assert life.is_draining() is True


def test_launchd_subbridge_plists_declare_exit_timeout_180_matching_drain_config() -> (
    None
):
    paths = sorted((REPO / "deploy" / "launchd").glob("com.user.dsh-*-bridge.plist"))
    assert [p.name for p in paths] == [
        f"com.user.dsh-{n}-bridge.plist"
        for n in ("agy", "claude-p", "muse", "opencode-zen")
    ]
    cfg_cls = lifecycle_mod().SubbridgeDrainConfig
    for path in paths:
        plist = plistlib.loads(path.read_bytes())
        env = plist["EnvironmentVariables"]
        assert plist["ExitTimeOut"] == 180, path.name
        assert env["BRIDGE_EXIT_TIMEOUT_S"] == "180", path.name
        assert cfg_cls.from_env(env).effective_drain_timeout_s == 110.0, path.name


def test_child_process_groups_ignore_non_leaders_and_foreign_children() -> None:
    mod = lifecycle_mod()
    code = "import time; time.sleep(30)"
    same_group = subprocess.Popen(
        [sys.executable, "-c", code]
    )  # pgid == наш pgid, не лидер
    try:
        assert same_group.pid not in [g.pid for g in mod.child_process_groups()]
    finally:
        same_group.kill()
        same_group.wait(3)


def test_group_alive_treats_permission_error_as_dead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-004 (Seat 1): `EPERM` на `killpg(pgid, 0)` — PGID чужой/переиспользован, группа не наша."""
    import core.proc_groups as pg

    def raiser(exc: OSError) -> Any:
        def fake(_pgid: int, _sig: int) -> None:
            raise exc

        return fake

    monkeypatch.setattr(pg.os, "killpg", raiser(PermissionError()))
    assert pg._group_alive(4242) is False
    monkeypatch.setattr(pg.os, "killpg", raiser(ProcessLookupError()))
    assert pg._group_alive(4242) is False
    monkeypatch.setattr(pg.os, "killpg", raiser(OSError(5, "io")))
    assert pg._group_alive(4242) is True


def test_prune_keeps_finished_leader_while_group_has_survivors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.proc_groups as pg

    alive_groups = {31_001}
    monkeypatch.setattr(pg, "_group_alive", lambda pgid: pgid in alive_groups)
    pg.reset_proc_groups()
    try:
        pg.register_proc_group(_FakeProc(31_001, rc=0))  # лидер вышел, внук жив
        pg.register_proc_group(_FakeProc(31_002, rc=0))  # группа мертва
        assert [p.pid for p in pg.live_proc_groups()] == [31_001]
        alive_groups.clear()
        assert pg.live_proc_groups() == []
    finally:
        pg.reset_proc_groups()


def test_terminate_skips_reaped_leaders_with_dead_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-004: уже собранный лидер с мёртвой группой не получает сигнал (PID мог быть переиспользован)."""
    import core.proc_groups as pg

    sent: list[tuple[int, int]] = []
    monkeypatch.setattr(pg.os, "killpg", lambda pgid, sig: sent.append((pgid, sig)))
    monkeypatch.setattr(pg, "_group_alive", lambda pgid: pgid == 32_001)
    pg.terminate_proc_groups_parallel(
        [_FakeProc(32_000, rc=0), _FakeProc(32_001, rc=0)], 0.0, 0.0
    )
    assert {pgid for pgid, _ in sent} == {32_001}


def test_spawn_registered_makes_child_a_group_leader() -> None:
    import core.proc_groups as pg

    pg.reset_proc_groups()
    proc = pg.spawn_registered([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert os.getpgid(proc.pid) == proc.pid  # лидер сессии по умолчанию
    finally:
        pg.terminate_proc_groups_parallel([proc], 2.0, 2.0)
        proc.wait(3)
        pg.reset_proc_groups()


def test_signal_sets_shutdown_flag_and_drain_is_idempotent() -> None:
    """Seat 3 F-001: `handle_signal` ставит оба bool; повторный `run_drain_once` — no-op без второго shutdown."""
    life = make_life(procs_fn=lambda: [])

    class _Server:
        calls = 0

        def shutdown(self) -> None:
            type(self).calls += 1

    life.handle_signal(signal.SIGTERM)
    assert life._signal_received and life._shutdown_requested
    life._server = _Server()
    first = life.run_drain_once()
    second = life.run_drain_once()
    assert first["state"] == "STOPPED" and second["state"] == "STOPPED"
    assert _Server.calls == 1 and life.shutdown_requested.is_set()


def test_opencode_zen_counts_helper_processes_as_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seat 1 F-005: хелперы из `spawn_registered` учитываются как активные при drain."""
    module = load_bridge(
        "opencode-zen-bridge", {"OPENCODE_ZEN_BRIDGE_KEY": KEY}, monkeypatch
    )
    proc = module.spawn_registered(
        [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    try:
        assert module._LIFECYCLE.hooks.active_procs_fn() >= 1
    finally:
        proc.kill()
        proc.wait(3)
