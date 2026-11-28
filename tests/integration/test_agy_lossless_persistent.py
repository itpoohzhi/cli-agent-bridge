"""L2 red repros for lossless delivery and persistent-worker ownership."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGY_DIR = REPO_ROOT / "bridges" / "agy-bridge"
if str(AGY_DIR) not in sys.path:
    sys.path.insert(0, str(AGY_DIR))

from agy_runtime.lossless_prompt_facade import (  # noqa: E402
    feed_run_stdin_or_lossless,
    iter_run_stdout_or_lossless,
    prepare_run_lossless_state,
    release_run_lossless_resources,
)
from agy_runtime.lossless_streaming_delivery import resolve_log_fn  # noqa: E402
from agy_runtime.persistent_run_hooks import (  # noqa: E402
    RunCloseContext,
    RunSpawnContext,
    close_run_resources,
    feed_run_stdin,
    iter_run_stdout_lines,
    release_run_persistent,
    start_run_process,
)
from agy_runtime.persistent_worker_adapter import AgyPersistentWorkerPool  # noqa: E402

CHUNKED_PROMPT = "x" * 20_000

STUB = """import json, os, sys, time
mode = os.environ.get('STUB_MODE', 'ok')
count = 0
for raw in sys.stdin:
    if not raw.strip(): continue
    count += 1
    if mode == 'silent': continue
    if mode == 'eof': sys.exit(0)
    if mode == 'idle' and count >= 2: time.sleep(30); break
    obj = json.loads(raw)
    n = int(obj.get('chunk', 1))
    if mode == 'slow':
        print(json.dumps({'type':'step_update','chunk':n}), flush=True)
        time.sleep(float(os.environ.get('STUB_PAUSE', '0.05')))
    print(json.dumps({'type':'result','chunk':n}), flush=True)
"""


def _server() -> ModuleType:
    name = "agy_server_lossless_persistent_red"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, AGY_DIR / "server.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "dynamic.json"
    cfg.write_text('{"lossless_delivery_enabled":true,"safe_frame_bytes":64,"lossless_max_chunks":8,"BRIDGE_AGY_PERSISTENT_WORKER_ENABLED":true,"persistent_worker_max_slots":2,"persistent_worker_lease_wait_s":0.1,"persistent_worker_idle_timeout_s":60.0,"persistent_worker_ttl_s":300.0,"persistent_worker_max_turns":50}', encoding="utf-8")  # fmt: skip
    return cfg


def _run_context(
    run: object,
    cfg: Path,
    pool: AgyPersistentWorkerPool,
    script: Path,
    *,
    resume_base_idx: int = 0,
) -> None:
    guard = getattr(run, "_lossless_guard")
    env = os.environ.copy()
    env["STUB_MODE"] = os.environ.get("STUB_MODE", "ok")
    cmd = [sys.executable, str(script)]

    def spawn() -> subprocess.Popen[bytes]:
        return guard.spawn_isolated(cmd, env=env)

    ctx = RunSpawnContext(
        pool, cfg, cmd, str(script.parent), env, "stub", "high", "plan",
        True, "", None, "chat", spawn, lambda: None,
        resume_base_idx=resume_base_idx,
    )
    start_run_process(run, ctx)
    setattr(
        run,
        "_release_persistent",
        lambda **kw: release_run_persistent(run, pool, cfg, **kw),
    )


def _prepare(srv: ModuleType, cfg: Path, prompt: str) -> SimpleNamespace:
    events: list[str] = []
    run = SimpleNamespace(
        proc=None, _stop_watch=threading.Event(), _proc_done=threading.Event(),
        run_cid="cid", _events=events, _log=events.append,
    )
    run.stdin_line = prepare_run_lossless_state(
        run, prompt, head_pruning_enabled=False, ensure_fit_fn=lambda x: x,
        ndjson_user_line_fn=srv._ndjson_user_line, config_path=cfg,
    )
    return run


def _close(run: object, guard: object) -> None:
    tail = SimpleNamespace(
        thread=threading.current_thread(), interrupt_active_query=lambda: None
    )
    setattr(run, "_tail", tail)
    setattr(run, "controller", SimpleNamespace(close=lambda: None))
    ctx = RunCloseContext(guard.teardown_process, lambda proc: None, 0.1)
    close_run_resources(run, ctx)


def _finish(run: object) -> None:
    _close(run, run._lossless_guard)
    release_run_lossless_resources(run)
    snap = run._lossless_guard.snapshot()
    assert snap.active == 0 and snap.active_pgids == ()


def test_chunked_with_persistent_enabled_uses_cold_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    srv, cfg, script = _server(), _make_config(tmp_path), tmp_path / "stub.py"
    script.write_text(STUB, encoding="utf-8")
    monkeypatch.setenv("AGY_BRIDGE_PERSISTENT_WORKER_ENABLED", "true")
    pool = AgyPersistentWorkerPool()
    run = _prepare(srv, cfg, CHUNKED_PROMPT)
    try:
        _run_context(run, cfg, pool, script)
        assert (
            run._lossless_chunked
            and run._persistent_mode is False
            and run._persistent_lease is None
        )
        feed_run_stdin_or_lossless(run, feed_run_stdin)
        assert list(iter_run_stdout_or_lossless(run, iter_run_stdout_lines))
        result = run._lossless_result
        assert result.ok and result.chunks_delivered >= 2
        assert "chunk_ack_timeout" not in str(getattr(run, "_lossless_result", ""))
    finally:
        _finish(run)
        pool.reconcile_disabled()


def test_single_delivery_keeps_persistent_worker_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGY_BRIDGE_PERSISTENT_WORKER_ENABLED", "true")
    srv, cfg, script = _server(), _make_config(tmp_path), tmp_path / "stub.py"
    script.write_text(STUB, encoding="utf-8")
    pool = AgyPersistentWorkerPool()
    run = _prepare(srv, cfg, "short")
    try:
        _run_context(run, cfg, pool, script)
        assert run._persistent_mode is True
        pid = run.proc.pid
        feed_run_stdin_or_lossless(run, feed_run_stdin)
        got = []
        for line in iter_run_stdout_or_lossless(run, iter_run_stdout_lines):
            got.append(line)
            if json.loads(line).get("type") == "result":
                break
        assert got
        run._persistent_turn_ok = True
        _close(run, run._lossless_guard)
        release_run_lossless_resources(run)
        assert run.proc.poll() is None
        again = _prepare(srv, cfg, "short")
        _run_context(again, cfg, pool, script, resume_base_idx=1)
        try:
            assert again._persistent_reused and again.proc.pid == pid
        finally:
            again._persistent_turn_ok = True
            _finish(again)
    finally:
        pool.reconcile_disabled()


def test_chunked_final_turn_streams_progressively(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STUB_MODE", "slow")
    monkeypatch.setenv("STUB_PAUSE", "0.05")
    srv, cfg, script = _server(), _make_config(tmp_path), tmp_path / "stub.py"
    script.write_text(STUB, encoding="utf-8")
    pool, run = AgyPersistentWorkerPool(), _prepare(srv, cfg, CHUNKED_PROMPT)
    try:
        _run_context(run, cfg, pool, script)
        run._lossless_limits = replace(
            run._lossless_limits,
            chunk_ack_timeout_s=0.35, final_turn_idle_timeout_s=0.45,
        )
        feed_run_stdin_or_lossless(run, feed_run_stdin)
        stream = iter_run_stdout_or_lossless(run, iter_run_stdout_lines)
        first = next(stream)
        assert json.loads(first)["type"] == "step_update"
        assert list(stream)
    finally:
        _finish(run)
        pool.reconcile_disabled()


def _failure_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, reason: str
) -> None:
    monkeypatch.setenv("STUB_MODE", mode)
    srv, cfg, script = _server(), _make_config(tmp_path), tmp_path / "stub.py"
    script.write_text(STUB, encoding="utf-8")
    pool, run = AgyPersistentWorkerPool(), _prepare(srv, cfg, CHUNKED_PROMPT)
    try:
        _run_context(run, cfg, pool, script)
        run._lossless_limits = replace(
            run._lossless_limits,
            chunk_ack_timeout_s=0.35, final_turn_idle_timeout_s=0.45,
        )
        feed_run_stdin_or_lossless(run, feed_run_stdin)
        list(iter_run_stdout_or_lossless(run, iter_run_stdout_lines))
        assert reason in str(getattr(run, "_lossless_result", ""))
        assert sum(f"event={reason}" in ev for ev in run._events) == 1
        assert (
            sum(
                "event=teardown" in ev and f"reason={reason}" in ev
                for ev in run._events
            )
            == 1
        )
    finally:
        _finish(run)
        pool.reconcile_disabled()


def test_final_turn_idle_timeout_tears_down_and_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _failure_case(tmp_path, monkeypatch, "idle", "final_turn_idle_timeout")


def test_chunk_ack_timeout_logs_and_tears_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STUB_MODE", "silent")
    _failure_case(tmp_path, monkeypatch, "silent", "chunk_ack_timeout")


def test_chunk_ack_eof_logs_and_tears_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _failure_case(tmp_path, monkeypatch, "eof", "chunk_ack_eof")


_LOGGED: list[str] = []


def _log(line: str) -> None:
    _LOGGED.append(line)


class _ModuleRun:
    req_id = "req-002"


def test_resolve_log_fn_targets_module_log() -> None:
    _LOGGED.clear()
    resolve_log_fn(_ModuleRun())("lossless_event event=delivery_result")
    assert _LOGGED == ["lossless_event event=delivery_result"]


def test_chunked_repeat_20x_no_race(tmp_path: Path) -> None:
    srv, cfg, script = _server(), _make_config(tmp_path), tmp_path / "stub.py"
    script.write_text(STUB, encoding="utf-8")
    pool = AgyPersistentWorkerPool()
    try:
        for _ in range(20):
            run = _prepare(srv, cfg, CHUNKED_PROMPT)
            try:
                _run_context(run, cfg, pool, script)
                feed_run_stdin_or_lossless(run, feed_run_stdin)
                assert list(iter_run_stdout_or_lossless(run, iter_run_stdout_lines))
            finally:
                _finish(run)
    finally:
        pool.reconcile_disabled()
