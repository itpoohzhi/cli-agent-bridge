"""Граничные L1-тесты activity window без сокетов, subprocess и ожиданий."""
from __future__ import annotations

import importlib
import importlib.util
import queue
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

import pytest

import core.stream_activity_policy as activity
from core.passthrough_sliding_window import SlidingDeadline, init_sliding_stream
from core.stream_resilience_runtime import (
    MidstreamReplayOrchestrator,
    StreamResilienceConfig,
)
from tests.stream_resilience_fakes import FakeClock
from tests.test_stream_activity_window import _config, _orchestrator, _runner


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "dynamic.json"))
    monkeypatch.setenv("BRIDGE_STREAM_MIDSTREAM_RETRY_ENABLED", "true")


def _budget(**over):
    values = dict(
        total_budget_s=1020.0, reserve_s=5.5, elapsed_s=0.0, sliding_enabled=True,
        max_attempts=3, attempt_index=0, first_event_timeout_s=120.0, backoff_cap_s=8.0,
    )
    values.update(over)
    return activity.SlidingBudgetInput(**values)


def _window(**over):
    values = dict(
        started_at=0.0, first_event_timeout_s=20.0,
        sliding_idle_timeout_s=20.0, safety_cap_s=100.0,
    )
    values.update(over)
    return activity.SlidingActivityWindow(**values)


@pytest.mark.parametrize("field,value", [
    ("total_budget_s", -1), ("total_budget_s", float("nan")),
    ("total_budget_s", float("inf")), ("total_budget_s", True),
    ("max_attempts", 0), ("max_attempts", True),
    ("attempt_index", -1), ("attempt_index", 3), ("attempt_index", True),
])
def test_sliding_budget_rejects_invalid_boundaries(field, value):
    with pytest.raises(ValueError):
        activity.compute_sliding_attempt_budget_s(_budget(**{field: value}))


@pytest.mark.parametrize("over", [
    {"started_at": float("nan")}, {"started_at": True}, {"first_event_timeout_s": 0},
])
def test_activity_window_rejects_invalid_timeouts(over):
    with pytest.raises(ValueError):
        _window(**over)


def test_legacy_attempt_budget_is_zero_when_retry_is_disallowed():
    value = _budget(sliding_enabled=False, elapsed_s=2000.0)
    assert activity.compute_sliding_attempt_budget_s(value) == 0.0
    assert activity._legacy_attempt_budget_s(value) == 0.0


def test_completed_window_ignores_late_signal():
    window = _window()
    assert window.mark_completed(10.0).state is activity.ActivityState.COMPLETED
    assert window.record_signal("content", "late", 11.0) is False
    assert window.check_expired(11.0).state is activity.ActivityState.COMPLETED


@pytest.mark.parametrize("raw_rc,raw_limit,expected", [
    ("bad", float("nan"), (0, 0.0)), (True, True, (0, 0.0)), (7, 42.5, (7, 42.5)),
])
def test_completed_final_outcome_normalizes_raw_numbers(raw_rc, raw_limit, expected):
    raw = {"state": "done", "rc": raw_rc, "timeout_limit_s": raw_limit}
    out = activity.render_final_outcome(raw, _window().mark_completed(1.0))
    assert out["state"] == "done"
    assert (out["rc"], out["timeout_limit_s"]) == expected


def test_orchestrator_without_window_is_inert():
    replay = MidstreamReplayOrchestrator(
        StreamResilienceConfig(), clock=FakeClock().monotonic
    )
    assert replay.deadline_s() == float("inf")
    assert replay.had_progress() is False
    replay.record_upstream_activity(True)
    replay.record_upstream_activity(False)
    assert replay.had_progress() is False


def test_orchestrator_sliding_deadline_moves_only_on_useful_activity(monkeypatch):
    clock = FakeClock()
    replay = _orchestrator(_config(monkeypatch), clock)
    replay.arm_attempt(1014.5)
    assert (replay.deadline_s(), replay.had_progress()) == (300.0, False)
    replay.record_upstream_activity(False)
    assert (replay.deadline_s(), replay.had_progress()) == (300.0, False)
    clock.advance(50)
    replay.record_upstream_activity(True)
    assert (replay.deadline_s(), replay.had_progress()) == (350.0, True)


def test_orchestrator_supports_legacy_sliding_deadline(monkeypatch):
    clock = FakeClock()
    window = SlidingDeadline(338.166, enabled_fn=lambda: True)
    window.arm(init_sliding_stream(0.0, 338.166, 300.0, 1000.0, True))
    replay = MidstreamReplayOrchestrator(
        _config(monkeypatch, enabled=False), window=window, clock=clock.monotonic
    )
    assert 0.0 < replay.deadline_s() <= 338.166
    assert replay.had_progress() is False
    replay.record_upstream_activity(True)
    assert replay.had_progress() is True


def _sse_module(monkeypatch):
    root = Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge"
    monkeypatch.syspath_prepend(str(root))
    return importlib.import_module("agy_runtime.sse_body_runner")


def test_invoke_legacy_defers_and_runner_writes_one_done_log(monkeypatch):
    clock = FakeClock()
    runner, handler, logs = _runner(
        monkeypatch, _config(monkeypatch, enabled=False), clock
    )
    seen = []

    def once(_ctx, *_args, **_named):
        seen.append(getattr(handler, "_defer_done_log", False))
        return {"state": "done", "rc": 0}

    handler._run_once = once
    assert runner._invoke()["state"] == "done"
    assert seen == [True]
    assert len(logs) == 1 and logs[0]["state"] == "done"


def test_log_final_guards_missing_callable_and_writes_owned_log(monkeypatch):
    runner, handler, logs = _runner(monkeypatch, _config(monkeypatch), FakeClock())
    handler._log_done = None
    runner._log_final({"state": "done"})
    handler._log_done = lambda *_args: logs.append("done")
    runner._log_final({"state": "done"})
    assert logs == ["done"]


class _CrossingQueue:
    def __init__(self, clock):
        self.clock = clock
        self.crossed = False

    def get(self, timeout=1.0):
        if not self.crossed:
            self.crossed = True
            self.clock.advance(400.0)
            raise queue.Empty
        return "done", (0, "", {})

    def empty(self):
        return False


def _load_server(monkeypatch):
    monkeypatch.setenv("AGY_BRIDGE_KEY", "test-key-w3d")
    monkeypatch.delenv("AGY_BRIDGE_FLEET", raising=False)
    path = Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge" / "server.py"
    spec = importlib.util.spec_from_file_location("agy_server_w3d_edges", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_execute_loop_default_defer_false_uses_extended_cap(monkeypatch):
    monkeypatch.setenv("AGY_EXTENDED_TIMEOUT_ENABLED", "1")
    server = _load_server(monkeypatch)
    clock = FakeClock()
    policy = NS(effective_max_timeout_s=1000.0, idle_timeout_s=1800.0)
    run = NS(
        q=_CrossingQueue(clock), controller=NS(), proc=NS(pid=1, returncode=0),
        got_event=True, started=0.0, err_box=[], policy=policy,
        last_producer_activity_ts=0.0, transcript_activity_ts=0.0,
    )
    handler = server.Handler.__new__(server.Handler)
    handler._attempt_budget_s = 300.0
    handler._job_client_gone = lambda: False
    assert not hasattr(handler, "_defer_done_log")
    fake_time = NS(
        monotonic=clock.monotonic, sleep=lambda _seconds: None,
        strftime=time.strftime, time=time.time,
    )
    with mock.patch.object(server, "time", fake_time), mock.patch.object(
        server, "_log", lambda *_args: None
    ):
        out = handler._execute(
            run, lambda _text: True, lambda _trace: True, lambda _reason: True, None
        )
    assert clock.now_s == 400.0
    assert (out["state"], out["rc"]) == ("done", 0)


def test_stage_tool_calls_tolerates_partial_json_and_ignores_empty_list(monkeypatch):
    clock = FakeClock()
    runner, _handler, _logs = _runner(monkeypatch, _config(monkeypatch), clock)
    runner.s.commit = lambda: True
    runner._activity_window = runner.replay.arm_attempt(300.0)
    runtime = importlib.import_module("agy_runtime.activity_runtime")
    runner._activity_runtime = runtime.ActivityRuntime(runner._activity_window)
    fragment = '{"partial": '
    assert runner.stage(fragment, "tool_calls") is True
    assert runner._activity_window.check_expired(clock.now_s).had_progress is True
    assert runner.s.buffer.commit_fragments() == (("tool_calls", fragment),)
    runner._activity_window = runner.replay.arm_attempt(300.0)
    runner._activity_runtime = runtime.ActivityRuntime(runner._activity_window)
    assert runner.stage("[]", "tool_calls") is True
    assert runner._activity_window.check_expired(clock.now_s).had_progress is False


def test_invoke_deferred_logs_redacted_error_exactly_once(monkeypatch):
    clock = FakeClock()
    runner, handler, logs = _runner(monkeypatch, _config(monkeypatch), clock)
    runner._activity_window = runner.replay.arm_attempt(300.0)
    runtime = importlib.import_module("agy_runtime.activity_runtime")
    runner._activity_runtime = runtime.ActivityRuntime(runner._activity_window)

    def once(_ctx, *_args, **_named):
        assert handler._defer_done_log is True
        raise RuntimeError("boom sk-secret-123")

    handler._run_once = once
    with pytest.raises(RuntimeError, match="boom"):
        runner._invoke()
    assert len(logs) == 1
    assert (logs[0]["state"], logs[0]["rc"]) == ("error", 1)
    assert "sk-secret-123" not in repr(logs)
    assert "<redacted>" in logs[0]["err"]


def test_successful_output_at_exact_deadline_is_not_rewritten(monkeypatch):
    clock = FakeClock()
    runner, handler, logs = _runner(monkeypatch, _config(monkeypatch), clock)

    def once(_ctx, *callbacks, **_named):
        callbacks[0]("progress")
        clock.advance(runner.deadline - clock.now_s)
        return {"state": "done", "rc": 0, "text": "ok"}

    handler._run_once = once
    out = runner.attempt(0, runner.replay.attempt_budget_s(0))
    assert clock.now_s == 300.0
    assert (out["state"], out["rc"], out["text"]) == ("done", 0, "ok")
    assert logs == [out]
