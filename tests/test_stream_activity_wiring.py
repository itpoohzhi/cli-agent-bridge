"""Production wiring скользящего ActivityRuntime и single-writer done."""

from __future__ import annotations

import ast
import importlib
import queue
import time
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

import pytest

from tests.stream_resilience_fakes import FakeClock
from tests.test_stream_activity_edges import _load_server
from tests.test_stream_activity_window import _runner

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "dynamic.json"))
    monkeypatch.setenv("AGY_EXTENDED_TIMEOUT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S", "300")
    monkeypatch.setenv("BRIDGE_STREAM_SLIDING_IDLE_TIMEOUT_S", "300")
    monkeypatch.setenv("BRIDGE_STREAM_BACKOFF_JITTER_RATIO", "0")


def _config(monkeypatch, sliding=True, buffering=True, midstream=True):
    values = {
        "MIDSTREAM_RETRY_ENABLED": midstream,
        "TOOL_ROLLBACK_ENABLED": buffering and not midstream,
        "SLIDING_ACTIVITY_WINDOW_ENABLED": sliding,
    }
    for name, enabled in values.items():
        monkeypatch.setenv(f"BRIDGE_STREAM_{name}", str(enabled).lower())
    env = {
        f"BRIDGE_STREAM_{name}": str(enabled).lower()
        for name, enabled in values.items()
    }
    env.update(
        BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S="300",
        BRIDGE_STREAM_SLIDING_IDLE_TIMEOUT_S="300",
    )
    rt = importlib.import_module("core.stream_resilience_runtime")
    return rt.StreamResilienceConfig.from_env(env)


class _ScriptedQueue:
    def __init__(self, clock, script):
        self.clock, self.script = clock, list(script)

    def get(self, timeout=1.0):
        at, kind, payload = self.script.pop(0)
        self.clock.advance(at - self.clock.now_s)
        if kind == "empty":
            raise queue.Empty
        return kind, payload

    def empty(self):
        return not self.script


def _run(clock, script):
    run = NS(
        q=_ScriptedQueue(clock, script),
        controller=NS(on_activity=lambda _kind: None),
        proc=NS(pid=1, returncode=0, poll=lambda: 0),
        got_event=False,
        started=0.0,
        err_box=[],
        policy=NS(effective_max_timeout_s=338.166, idle_timeout_s=1050.0),
        last_producer_activity_ts=0.0,
        transcript_activity_ts=None,
        closed=False,
    )
    run.close = lambda: setattr(run, "closed", True)
    return run


def _wire_runner(monkeypatch, server, clock, run, modes):
    buffering, midstream, sliding = (*modes, True)[:3]
    config = _config(monkeypatch, sliding, buffering, midstream)
    runner, _old_handler, _logs = _runner(monkeypatch, config, clock)
    runner.buffering = buffering
    handler = server.Handler.__new__(server.Handler)
    handler._job_client_gone = lambda: False
    handler._log_done = lambda *_args: None

    def registered(_ctx, callbacks):
        try:
            return handler._execute(run, *callbacks)
        finally:
            run.close()

    handler._run_registered_attempt = registered
    runner.s.handler = handler
    runner.s.on_tool_trace = lambda _event: True
    return runner, handler


def _patch_clock(server, clock):
    fake = NS(
        monotonic=clock.monotonic,
        sleep=lambda _seconds: None,
        strftime=time.strftime,
        time=time.time,
    )
    return mock.patch.object(server, "time", fake), mock.patch.object(
        server, "_log", lambda *_a: None
    )


@pytest.mark.parametrize("kind", ["reasoning", "tool_trace"])
@pytest.mark.parametrize(
    "buffering,midstream", [(False, False), (True, False), (True, True)]
)
def test_useful_deltas_drive_shared_attempt_runtime(
    monkeypatch, kind, buffering, midstream
):
    clock = FakeClock()
    script = [
        (200, kind, "thinking" if kind == "reasoning" else {"type": "tool_use"}),
        (400, kind, "more" if kind == "reasoning" else {"type": "tool_result"}),
        (450, "done", (0, "", {})),
    ]
    run = _run(clock, script)
    monkeypatch.setenv("BRIDGE_STREAM_MIDSTREAM_RETRY_ENABLED", str(midstream).lower())
    monkeypatch.setenv(
        "BRIDGE_STREAM_TOOL_ROLLBACK_ENABLED", str(buffering and not midstream).lower()
    )
    server = _load_server(monkeypatch)
    runner, handler = _wire_runner(
        monkeypatch, server, clock, run, (buffering, midstream)
    )
    run.got_event = True
    patches = _patch_clock(server, clock)
    with patches[0], patches[1]:
        out = runner.attempt(0, 1014.5)
    assert (out["state"], out["rc"], clock.now_s) == ("done", 0, 450)
    assert run.closed is True
    assert handler._activity_runtime is None


@pytest.mark.parametrize(
    "buffering,midstream", [(False, False), (True, False), (True, True)]
)
def test_idle_expires_in_execute_and_cancels_upstream(
    monkeypatch, buffering, midstream
):
    clock = FakeClock()
    run = _run(clock, [(200, "reasoning", "progress"), (500, "empty", None)])
    monkeypatch.setenv("BRIDGE_STREAM_MIDSTREAM_RETRY_ENABLED", str(midstream).lower())
    monkeypatch.setenv(
        "BRIDGE_STREAM_TOOL_ROLLBACK_ENABLED", str(buffering and not midstream).lower()
    )
    server = _load_server(monkeypatch)
    runner, _handler = _wire_runner(
        monkeypatch, server, clock, run, (buffering, midstream)
    )
    run.got_event = True
    patches = _patch_clock(server, clock)
    with patches[0], patches[1]:
        out = runner.attempt(0, 1014.5)
    assert clock.now_s == 500
    assert (out["state"], out["rc"], out["err"]) == (
        "timeout",
        124,
        "retry_budget_exhausted",
    )
    assert out["timeout_limit_s"] == 300 and run.closed is True


def test_keepalive_and_empty_delta_do_not_extend_runtime(monkeypatch):
    clock = FakeClock()
    run = _run(clock, [(100, "reasoning", ""), (300, "empty", None)])
    server = _load_server(monkeypatch)
    runner, _handler = _wire_runner(monkeypatch, server, clock, run, (True, True))
    patches = _patch_clock(server, clock)
    with patches[0], patches[1]:
        out = runner.attempt(0, 1014.5)
    assert clock.now_s == 300
    assert (out["state"], out["rc"]) == ("timeout", 124)


def test_sliding_off_preserves_legacy_338_166_cap(monkeypatch):
    clock = FakeClock()
    run = _run(clock, [(338.166, "empty", None)])
    server = _load_server(monkeypatch)
    runner, _handler = _wire_runner(monkeypatch, server, clock, run, (False, False))
    runner.buffering = False
    run.got_event = True
    monkeypatch.setenv("BRIDGE_STREAM_SLIDING_ACTIVITY_WINDOW_ENABLED", "false")
    patches = _patch_clock(server, clock)
    with patches[0], patches[1]:
        out = runner.attempt(0, 338.166)
    assert clock.now_s == pytest.approx(338.166)
    assert (out["state"], out["rc"], out["timeout_limit_s"]) == (
        "timeout", 124, 338.166,
    )


@pytest.mark.parametrize("outcome", ["done", "error", "exception"])
@pytest.mark.parametrize("sliding", [False, True])
@pytest.mark.parametrize("buffering", [False, True])
def test_single_writer_done_for_every_attempt(monkeypatch, outcome, sliding, buffering):
    clock = FakeClock()
    server = _load_server(monkeypatch)
    config = _config(
        monkeypatch, sliding=sliding, buffering=buffering, midstream=buffering
    )
    runner, _old_handler, _logs = _runner(monkeypatch, config, clock)
    runner.buffering = buffering
    handler = server.Handler.__new__(server.Handler)
    runner.s.handler = handler
    raw = {
        "state": "done" if outcome == "done" else "agy_error",
        "rc": 0 if outcome == "done" else 1,
        "err": "" if outcome == "done" else "upstream failed",
    }

    def registered(_ctx, _callbacks):
        if outcome == "exception":
            raise RuntimeError("attempt exploded")
        handler._log_done("m", raw, 0.0, "test")
        return raw

    handler._run_registered_attempt = registered
    lines = []
    patches = _patch_clock(server, clock)
    with patches[0], mock.patch.object(server, "_log", lines.append):
        if outcome == "exception":
            with pytest.raises(RuntimeError, match="attempt exploded"):
                runner.attempt(0, 1014.5)
        else:
            runner.attempt(0, 1014.5)
    done = [line for line in lines if line.startswith("done ")]
    assert len(done) == 1
    expected = ("error", 1) if outcome == "exception" else (raw["state"], raw["rc"])
    assert f"rc={expected[1]} state={expected[0]}" in done[0]
    assert handler._defer_done_log is False


@pytest.mark.parametrize("sliding,budget", [(True, 1014.5), (False, 300.0)])
def test_non_buffering_body_uses_sliding_budget(monkeypatch, sliding, budget):
    clock = FakeClock()
    script = [(250, "reasoning", "a"), (500, "reasoning", "b"),
              (750, "reasoning", "c"), (800, "done", (0, "", {}))]
    run = _run(clock, script if sliding else [(0, "done", (0, "", {}))])
    run.got_event = True
    server = _load_server(monkeypatch)
    runner, _ = _wire_runner(monkeypatch, server, clock, run, (False, False, sliding))
    runner.s.finalize_stream = lambda out: out.update(graceful_done=True)
    runner.replay.arm_attempt = arm = mock.Mock(wraps=runner.replay.arm_attempt)
    with (patches := _patch_clock(server, clock))[0], patches[1]:
        runner._run_body()
    assert arm.call_args == (mock.call(budget) if sliding else None)
    assert (runner._attempt_budget, clock.now_s) == (budget, 800 if sliding else 0)
    assert (runner._last_out["state"], runner._last_out["rc"]) == ("done", 0)


def _has_call(tree, attr):
    return any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == attr
        for n in ast.walk(tree)
    )


def test_ast_proves_runner_activity_wiring():
    runner_tree = ast.parse(
        (_ROOT / "bridges/agy-bridge/agy_runtime/sse_body_runner.py").read_text()
    )
    runner_dump = ast.dump(runner_tree)
    assert "activity_runtime" in runner_dump and "ActivityRuntime" in runner_dump


def test_ast_proves_runner_execute_and_cancellation_wiring():
    server_tree = ast.parse((_ROOT / "bridges/agy-bridge/server.py").read_text())
    execute = next(
        n
        for n in ast.walk(server_tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_execute"
    )
    calls = {
        n.func.attr
        for n in ast.walk(execute)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    assert {"current_deadline", "check_expired"} <= calls
    impl = next(
        n
        for n in ast.walk(server_tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_run_once_impl"
    )
    assert _has_call(impl, "close")
