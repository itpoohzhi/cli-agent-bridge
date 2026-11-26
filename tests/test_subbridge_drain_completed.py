"""Wave 4 (REQ-001 O6): гарантированные `drain_completed` и `drain_reentry` в SubbridgeLifecycle.

Оракулы: ровно один `drain_completed` на эпоху СТРОГО до `drain_completed.set()`/`STOPPED`,
`drain_reentry` вне `_turns_lock` (без deadlock), новая эпоха после `reset()`, счётчик
`drain_log_errors` при падающем `log_fn`, совместимость по orphan-процессам и кадрам SSE.
"""

from __future__ import annotations

import ast
import signal
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.proc_groups as pg  # noqa: E402
from core.drain_policy import DEFAULT_RETRY_AFTER_S, resolve_retry_after_s  # noqa: E402
from core.lifecycle import DrainState  # noqa: E402
from core.subbridge_config import SubbridgeDrainConfig  # noqa: E402
from core.subbridge_lifecycle import SubbridgeHooks, SubbridgeLifecycle  # noqa: E402


def make_life(**kwargs: Any) -> SubbridgeLifecycle:
    cfg = SubbridgeDrainConfig(
        drain_timeout_s=kwargs.pop("drain_timeout_s", 0.3),
        kill_term_grace_s=0.2,
        kill_wait_s=0.2,
        flush_grace_s=kwargs.pop("flush_grace_s", 0.3),
        poll_interval_s=0.005,
        safety_margin_s=0.1,
    )
    return SubbridgeLifecycle(cfg, SubbridgeHooks(**kwargs))


class FakeServer:
    """Двойник сервера: считает `shutdown()` и снимает счётчик ходов в момент остановки."""

    def __init__(self) -> None:
        self.shutdown_calls = 0
        self.turns_probe: Any = None
        self.turns_at_shutdown: int | None = None

    def shutdown(self) -> None:
        self.shutdown_calls += 1
        if self.turns_probe is not None:
            self.turns_at_shutdown = self.turns_probe()


class Recorder:
    """`log_fn` с проверкой порядка: `drain_completed` пишется ДО `Event.set()` и `STOPPED`.

    Сбой assert внутри `log_fn` гасится `_emit_drain_line` (счётчик `drain_log_errors`),
    поэтому каждый тест дополнительно проверяет число строк и `drain_log_errors == 0`.
    """

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.life: SubbridgeLifecycle | None = None

    def __call__(self, message: str) -> None:
        if message.startswith("drain_completed"):
            assert self.life is not None
            assert not self.life.drain_completed.is_set()
            assert self.life.state == DrainState.DRAINING
        self.lines.append(message)

    def completed(self) -> list[str]:
        return [ln for ln in self.lines if ln.startswith("drain_completed ")]

    def reentries(self) -> list[str]:
        return [ln for ln in self.lines if ln.startswith("drain_reentry ")]


def fields(line: str) -> dict[str, str]:
    return dict(tok.split("=", 1) for tok in line.split()[1:])


def test_idle_drain_emits_one_completed_before_event_set() -> None:
    """Путь 1: active=0 — ровно один `drain_completed` со всеми нулевыми/успешными полями."""
    rec = Recorder()
    life = make_life(log_fn=rec)
    rec.life = life
    server = FakeServer()
    result = life.run_drain_once(server)
    assert result == {
        "active_turns_before": 0,
        "remaining": 0,
        "forced_kill": False,
        "shutdown_ok": True,
        "drain_log_errors": 0,
        "state": DrainState.STOPPED,
    }
    assert len(rec.completed()) == 1 and rec.reentries() == []
    f = fields(rec.completed()[0])
    assert (
        f["epoch"],
        f["signal"],
        f["active_before"],
        f["remaining"],
        f["forced_kill"],
        f["shutdown_ok"],
    ) == ("1", "0", "0", "0", "0", "1")
    assert int(f["elapsed_ms"]) >= 0
    assert life.drain_completed.is_set() and server.shutdown_calls == 1
    assert life.drain_log_errors == 0


def test_drain_waits_for_active_turn_and_completes_cleanly() -> None:
    """Путь 2: активный ход завершается до таймаута — без force_kill, remaining=0."""
    rec = Recorder()
    life = make_life(log_fn=rec, drain_timeout_s=2.0)
    rec.life = life
    server = FakeServer()
    server.turns_probe = lambda: life.active_http_turns
    results: list[dict[str, Any]] = []
    with life.track_turn("/v1/chat/completions"):
        worker = threading.Thread(
            target=lambda: results.append(life.run_drain_once(server))
        )
        worker.start()
        deadline = time.monotonic() + 2
        while life.state != DrainState.DRAINING and time.monotonic() < deadline:
            time.sleep(0.005)
        assert life.state == DrainState.DRAINING and server.shutdown_calls == 0
    worker.join(3)
    assert not worker.is_alive() and len(results) == 1
    result = results[0]
    assert result["active_turns_before"] >= 1
    assert result["remaining"] == 0
    assert result["forced_kill"] is False and result["shutdown_ok"] is True
    assert server.turns_at_shutdown == 0 and server.shutdown_calls == 1
    assert len(rec.completed()) == 1 and life.drain_log_errors == 0
    f = fields(rec.completed()[0])
    assert int(f["active_before"]) >= 1
    assert (f["remaining"], f["forced_kill"], f["shutdown_ok"]) == ("0", "0", "1")
    assert not [ln for ln in rec.lines if ln.startswith("drain_timeout")]


def test_drain_timeout_force_kills_and_emits_completed() -> None:
    """Путь 3: таймаут — force_kill и cleanup до shutdown, `drain_completed` всё равно один."""
    kills: list[int] = []
    cleanups: list[int] = []
    rec = Recorder()
    life = make_life(
        log_fn=rec,
        drain_timeout_s=0.05,
        active_procs_fn=lambda: 1,
        force_kill_fn=lambda: kills.append(1),
        cleanup_fn=lambda: cleanups.append(1),
    )
    rec.life = life
    server = FakeServer()
    result = life.run_drain_once(server)
    assert kills == [1] and cleanups == [1]
    assert result["forced_kill"] is True and result["shutdown_ok"] is True
    assert result["active_turns_before"] == 1 and result["remaining"] == 1
    assert server.shutdown_calls == 1 and life.drain_completed.is_set()
    assert len(rec.completed()) == 1 and life.drain_log_errors == 0
    f = fields(rec.completed()[0])
    assert (f["active_before"], f["forced_kill"], f["shutdown_ok"]) == ("1", "1", "1")
    assert any(ln.startswith("drain_timeout ") for ln in rec.lines)


def test_shutdown_exception_still_emits_completed_shutdown_ok_0() -> None:
    """Путь 4: исключение в `target.shutdown()` — ошибка залогирована, completed с shutdown_ok=0."""

    class BrokenServer(FakeServer):
        def shutdown(self) -> None:
            super().shutdown()
            raise OSError("shutdown failed")

    rec = Recorder()
    life = make_life(log_fn=rec)
    rec.life = life
    server = BrokenServer()
    result = life.run_drain_once(server)
    assert server.shutdown_calls == 1 and result["shutdown_ok"] is False
    assert life.state == DrainState.STOPPED and life.drain_completed.is_set()
    err = "drain_shutdown_error err=OSError"
    assert err in rec.lines and len(rec.completed()) == 1
    assert fields(rec.completed()[0])["shutdown_ok"] == "0"
    assert rec.lines.index(err) < rec.lines.index(rec.completed()[0])
    assert life.drain_log_errors == 0


def test_concurrent_sixteen_threads_one_completed_fifteen_reentries() -> None:
    """16 потоков: 1 completed + 15 reentry, 1 shutdown; reentry строго вне `_turns_lock`."""
    lines: list[str] = []

    def log_fn(message: str) -> None:
        if message.startswith("drain_reentry"):
            # Взятие замка и enter_turn внутри log_fn не должны давать deadlock.
            assert life._turns_lock.acquire(timeout=2), "reentry под _turns_lock"
            life._turns_lock.release()
            assert life.enter_turn("/v1/chat/completions") is not None
        lines.append(message)

    life = make_life(log_fn=log_fn)
    server = FakeServer()
    barrier = threading.Barrier(16)
    results: list[dict[str, Any]] = []
    results_lock = threading.Lock()

    def worker() -> None:
        barrier.wait(5)
        result = life.run_drain_once(server)
        with results_lock:
            results.append(result)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert all(not t.is_alive() for t in threads) and len(results) == 16
    completed = [ln for ln in lines if ln.startswith("drain_completed ")]
    reentries = [ln for ln in lines if ln.startswith("drain_reentry ")]
    assert len(completed) == 1 and len(reentries) == 15
    assert server.shutdown_calls == 1 and life.drain_completed.is_set()
    # Если бы assert в log_fn упал (deadlock/порядок), строка пропала бы и вырос счётчик.
    assert life.drain_log_errors == 0
    winners = [r for r in results if "shutdown_ok" in r]
    assert len(winners) == 1 and winners[0]["state"] == DrainState.STOPPED
    for r in results:
        if "shutdown_ok" not in r:
            assert set(r) == {"active_turns_before", "state", "drain_log_errors"}
            assert r["active_turns_before"] == 0
            assert r["state"] in (DrainState.DRAINING, DrainState.STOPPED)


def test_reset_starts_epoch_two_and_full_second_drain() -> None:
    """`reset()` открывает новую эпоху: второй drain полноценный, с `epoch=2`."""
    rec = Recorder()
    life = make_life(log_fn=rec)
    rec.life = life
    first_server, second_server = FakeServer(), FakeServer()
    first = life.run_drain_once(first_server)
    assert first["state"] == DrainState.STOPPED
    life.reset()
    assert life.state == DrainState.READY and not life.drain_completed.is_set()
    assert life.drain_log_errors == 0
    second = life.run_drain_once(second_server)
    assert second["shutdown_ok"] is True and second["state"] == DrainState.STOPPED
    assert first_server.shutdown_calls == 1 and second_server.shutdown_calls == 1
    assert life.drain_completed.is_set()
    completed = rec.completed()
    assert len(completed) == 2
    assert fields(completed[0])["epoch"] == "1"
    assert fields(completed[1])["epoch"] == "2"
    assert rec.reentries() == []  # новая легитимная эпоха, а не повторный вход


def test_throwing_log_fn_counts_errors_and_reaches_stopped() -> None:
    """Падающий `log_fn` (OSError) не срывает drain: STOPPED/set достигнуты, ошибки учтены."""

    def broken(message: str) -> None:
        raise OSError("broken pipe")

    life = make_life(log_fn=broken)
    server = FakeServer()
    result = life.run_drain_once(server)
    assert life.state == DrainState.STOPPED and life.drain_completed.is_set()
    assert life.drain_log_errors >= 1
    assert result["drain_log_errors"] == life.drain_log_errors
    assert result["shutdown_ok"] is True and server.shutdown_calls == 1
    life.reset()
    assert life.drain_log_errors == 0


def test_duplicate_call_emits_reentry_with_signal_and_no_second_shutdown() -> None:
    """Повторный вызов после STOPPED: `drain_reentry` с сигналом, без второго shutdown."""
    rec = Recorder()
    life = make_life(log_fn=rec)
    rec.life = life
    life.handle_signal(signal.SIGTERM)
    server = FakeServer()
    first = life.run_drain_once(server)
    second = life.run_drain_once(server)
    assert first["state"] == DrainState.STOPPED
    assert second == {
        "active_turns_before": 0,
        "state": DrainState.STOPPED,
        "drain_log_errors": 0,
    }
    assert server.shutdown_calls == 1
    assert len(rec.completed()) == 1 and len(rec.reentries()) == 1
    assert fields(rec.completed()[0])["signal"] == str(signal.SIGTERM)
    assert rec.reentries()[0] == f"drain_reentry epoch=1 signal={signal.SIGTERM}"


def test_force_kill_drain_leaves_no_orphan_processes() -> None:
    """Совместимость orphan_pids=0: после таймаутного drain живых потомков не остаётся."""
    life = make_life(drain_timeout_s=0.05, procs_fn=pg.live_proc_groups)
    victim = pg.spawn_registered([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        result = life.run_drain_once(FakeServer())
        assert result["forced_kill"] is True and result["shutdown_ok"] is True
        assert victim.returncode is not None and victim.returncode < 0
        assert pg.live_proc_groups() == []  # orphan_pids=0
        assert life.drain_completed.is_set()
    finally:
        if victim.poll() is None:
            victim.kill()
        victim.wait(3)
        life.reset()
        pg.reset_proc_groups()


def test_active_turn_finishes_writing_before_server_shutdown() -> None:
    """Совместимость SSE `[DONE]`: ход дописывает кадры, shutdown только после нуля ходов."""
    life = make_life(drain_timeout_s=2.0)
    server = FakeServer()
    server.turns_probe = lambda: life.active_http_turns
    finished = threading.Event()
    results: list[dict[str, Any]] = []

    def turn() -> None:
        with life.track_turn("/v1/chat/completions"):
            time.sleep(0.05)  # «дописывает» терминальный кадр и [DONE]
        finished.set()

    worker = threading.Thread(target=turn)
    drain = threading.Thread(target=lambda: results.append(life.run_drain_once(server)))
    worker.start()
    deadline = time.monotonic() + 2
    while life.active_http_turns == 0 and time.monotonic() < deadline:
        time.sleep(0.005)
    assert life.active_http_turns == 1
    drain.start()
    drain.join(3)
    worker.join(1)
    assert finished.is_set() and not drain.is_alive() and len(results) == 1
    assert server.turns_at_shutdown == 0 and server.shutdown_calls == 1
    assert results[0]["remaining"] == 0 and results[0]["forced_kill"] is False


def test_drain_without_log_fn_and_empty_line_skip_logging() -> None:
    """L141: `log_fn=None` — drain без ошибок; пустая строка не доходит до `log_fn`."""
    life = make_life()
    result = life.run_drain_once(FakeServer())
    assert result["drain_log_errors"] == 0 and life.drain_log_errors == 0
    assert result["shutdown_ok"] is True and life.drain_completed.is_set()
    calls: list[str] = []
    spy_life = make_life(log_fn=calls.append)
    spy_life._emit_drain_line("")
    assert calls == []
    spy_life._emit_drain_line("drain_probe")
    assert calls == ["drain_probe"]


def test_run_drain_once_sets_shutdown_requested_until_reset() -> None:
    """L186: drain сам поднимает `_shutdown_requested` без сигнала; `reset()` опускает."""
    rec = Recorder()
    life = make_life(log_fn=rec)
    rec.life = life
    assert life._shutdown_requested is False and life._signal_received is False
    result = life.run_drain_once(FakeServer())
    assert life._shutdown_requested is True
    assert result["drain_log_errors"] == 0 and life.drain_log_errors == 0
    assert len(rec.completed()) == 1  # Recorder требует state==DRAINING на эмиссии
    life.reset()
    assert life._shutdown_requested is False


def test_idle_drain_blocks_spawns_until_reset() -> None:
    """L195: idle drain (active=0, без force_kill) блокирует spawn; `reset()` снимает."""
    life = make_life()
    proc: Any = None
    try:
        result = life.run_drain_once(FakeServer())
        assert result["forced_kill"] is False and result["remaining"] == 0
        with pytest.raises(RuntimeError):
            pg.spawn_registered([sys.executable, "-c", "pass"])
        life.reset()
        proc = pg.spawn_registered([sys.executable, "-c", "pass"])
        assert proc.wait(5) == 0
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(3)
        life.reset()
        pg.reset_proc_groups()


def test_admission_retry_after_explicit_vs_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """L123: ra!=default — без env-переменной `explicit=ra`, с ней `explicit=None`."""
    monkeypatch.delenv("BRIDGE_RETRY_AFTER_S", raising=False)
    monkeypatch.delenv("BRIDGE_RETRY_AFTER_MAX_S", raising=False)
    life = SubbridgeLifecycle(SubbridgeDrainConfig(retry_after_s=17))
    life.handle_signal(signal.SIGTERM)
    rej = life.admission_rejection("/v1/chat/completions")
    assert rej is not None and rej[0] == 503
    assert rej[1]["Retry-After"] == "17" and rej[1]["X-Bridge-Draining"] == "true"
    monkeypatch.setenv("BRIDGE_RETRY_AFTER_S", "42")
    rej = life.admission_rejection("/v1/chat/completions")
    assert rej is not None and rej[1]["Retry-After"] == "42"


def test_admission_default_retry_after_takes_env_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L123: ra==default и env пуст — `use_env=True`: resolve получает `explicit=None`."""
    monkeypatch.delenv("BRIDGE_RETRY_AFTER_S", raising=False)
    monkeypatch.delenv("BRIDGE_DRAIN_POLICY_ENABLED", raising=False)
    seen: list[Any] = []
    real = resolve_retry_after_s

    def spy(env: Mapping[str, str], **kwargs: Any) -> int:
        seen.append(kwargs.get("explicit"))
        return real(env, **kwargs)

    monkeypatch.setattr("core.subbridge_lifecycle.resolve_retry_after_s", spy)
    life = SubbridgeLifecycle(SubbridgeDrainConfig())
    assert life.config.retry_after_s == DEFAULT_RETRY_AFTER_S
    life.handle_signal(signal.SIGTERM)
    rej = life.admission_rejection("/v1/chat/completions")
    assert rej is not None and rej[1]["Retry-After"] == str(DEFAULT_RETRY_AFTER_S)
    assert seen == [None]


class ServeFakeServer:
    """Двойник сервера для `serve_forever`: опционально держит до конца drain."""

    def __init__(self, release: threading.Event | None = None) -> None:
        self.release = release
        self.close_calls = 0
        self.shutdown_calls = 0

    def serve_forever(self) -> None:
        if self.release is not None:
            assert self.release.wait(5)

    def server_close(self) -> None:
        self.close_calls += 1

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def make_serve_life(workspace: Path, **hooks: Any) -> SubbridgeLifecycle:
    cfg = SubbridgeDrainConfig(drain_timeout_s=2.0, poll_interval_s=0.005)
    return SubbridgeLifecycle(cfg, SubbridgeHooks(**hooks), workspace=workspace)


def test_serve_forever_signal_idle_drain_skips_force_kill(tmp_path: Path) -> None:
    """L253(а): сигнал + active=0 — штатный drain watcher'а, force_kill не вызывается."""
    kills: list[int] = []
    life = make_serve_life(tmp_path, force_kill_fn=lambda: kills.append(1))
    server = ServeFakeServer(life.drain_completed)
    life.handle_signal(signal.SIGTERM)
    try:
        assert life.serve_forever(server, install_signals=False) == 0
        assert kills == [] and life.forced_kill is False
        assert server.close_calls == 1 and server.shutdown_calls == 1
        assert life.drain_completed.is_set()
    finally:
        life.reset()
        pg.reset_proc_groups()


def test_serve_forever_signal_active_procs_force_kills(tmp_path: Path) -> None:
    """L253(б): сигнал есть, но active>0 — force_kill из `finally` serve_forever."""
    kills: list[int] = []
    active = [1]

    def kill() -> None:
        kills.append(1)
        active[0] = 0

    life = make_serve_life(
        tmp_path, active_procs_fn=lambda: active[0], force_kill_fn=kill
    )
    server = ServeFakeServer()
    life.handle_signal(signal.SIGTERM)
    try:
        assert life.serve_forever(server, install_signals=False) == 0
        assert kills == [1] and life.forced_kill is True
        assert life.drain_completed.wait(3)  # watcher завершает без второго kill
        assert server.close_calls == 1 and server.shutdown_calls == 1
    finally:
        life.reset()
        pg.reset_proc_groups()


def test_serve_forever_no_signal_force_kills_even_idle(tmp_path: Path) -> None:
    """L253(в): выход без сигнала — force_kill даже при active=0."""
    kills: list[int] = []
    life = make_serve_life(tmp_path, force_kill_fn=lambda: kills.append(1))
    server = ServeFakeServer()
    try:
        assert life.serve_forever(server, install_signals=False) == 0
        assert kills == [1] and life.forced_kill is True
        assert server.close_calls == 1 and server.shutdown_calls == 0
        life.handle_signal(signal.SIGTERM)  # останавливаем watcher-поток
        assert life.drain_completed.wait(3)
    finally:
        life.reset()
        pg.reset_proc_groups()


def test_lifecycle_module_limits_card() -> None:
    """Limits Card Wave 4: <= 296 LOC, функции <= 40 LOC и <= 5 параметров (без self)."""
    src = (ROOT / "core" / "subbridge_lifecycle.py").read_text(encoding="utf-8")
    assert len(src.splitlines()) <= 296
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef):
            assert node.end_lineno is not None
            assert node.end_lineno - node.lineno + 1 <= 40, node.name
            args = node.args.args
            n_args = len(args) + len(node.args.posonlyargs) + len(node.args.kwonlyargs)
            if args and args[0].arg == "self":
                n_args -= 1
            assert n_args <= 5, node.name
