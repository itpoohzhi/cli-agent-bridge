"""Red-repro D-01..D-04: фейковые часы, без сокетов, subprocess и sleep."""
from __future__ import annotations

import importlib
import random
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from tests.stream_resilience_fakes import FakeClock

_AGY = str(Path(__file__).resolve().parents[1] / "bridges/agy-bridge")


@pytest.fixture(autouse=True)
def _isolated_dynamic_config(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "dynamic.json"))
    monkeypatch.setenv("BRIDGE_STREAM_MIDSTREAM_RETRY_ENABLED", "true")


def _config(monkeypatch, enabled=True):
    flag = str(enabled).lower()
    monkeypatch.setenv("BRIDGE_STREAM_SLIDING_ACTIVITY_WINDOW_ENABLED", flag)
    env = {
        "BRIDGE_STREAM_MIDSTREAM_RETRY_ENABLED": "true",
        "BRIDGE_STREAM_SLIDING_ACTIVITY_WINDOW_ENABLED": flag,
        "BRIDGE_STREAM_SLIDING_IDLE_TIMEOUT_S": "300",
        "BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S": "300",
        "BRIDGE_STREAM_BACKOFF_JITTER_RATIO": "0",
    }
    rt = importlib.import_module("core.stream_resilience_runtime")
    return rt.StreamResilienceConfig.from_env(env)


def _runner(monkeypatch, config, clock):
    monkeypatch.syspath_prepend(_AGY)
    rt = importlib.import_module("core.stream_resilience_runtime")
    p = importlib.import_module("core.stream_resilience_policy")
    module = importlib.import_module("agy_runtime.sse_body_runner")
    logs = []
    handler = NS(_log_done=lambda _m, out, _t, _tag: logs.append(dict(out)))
    session = NS(
        handler=handler,
        config=config,
        ctx={"conversation_id": "01234567", "model": "m", "tag": "test"},
        ledger=p.MidstreamStepLedger(),
        buffer=p.UncommittedTurnBuffer(),
        disconnected=False,
        coordinator=NS(await_headers_or_flush=lambda _ready: None),
        stream_text=lambda _value: True,
        stream_reasoning=lambda _value: True,
        keepalive=lambda: True,
    )
    runner = module._SseBodyRunner(session)
    runner.time = clock
    runner.replay = rt.MidstreamReplayOrchestrator(
        config, clock=clock.monotonic, sleeper=clock.sleep
    )
    runner.replay.buffer = session.buffer
    monkeypatch.setattr(runner, "prepare_buffer", lambda: None)
    monkeypatch.setattr(runner, "reconcile_trace", lambda _out: None)
    runner.buffering = True
    return runner, handler, logs


def _orchestrator(config, clock):
    rt = importlib.import_module("core.stream_resilience_runtime")
    return rt.MidstreamReplayOrchestrator(
        config, clock=clock.monotonic, sleeper=clock.sleep
    )


def test_default_off_and_useful_deltas_outlive_static_338s(monkeypatch):
    rt = importlib.import_module("core.stream_resilience_runtime")
    default = rt.StreamResilienceConfig.from_env({})
    assert getattr(default, "sliding_activity_window_enabled", False) is False
    clock = FakeClock()
    runner, handler, _logs = _runner(monkeypatch, _config(monkeypatch), clock)
    seen = []
    runner.s.stream_reasoning = lambda value: seen.append(value) or True

    def once(_ctx, *callbacks, **_named):
        for _ in range(2):
            clock.advance(200)
            callbacks[2]("reasoning")
        clock.advance(50)
        return {"state": "done", "rc": 0}

    handler._run_once = once
    out = runner.attempt(0, runner.replay.attempt_budget_s(0))
    assert clock.now_s == 450
    assert (out["state"], out["rc"]) == ("done", 0)
    assert seen == ["reasoning", "reasoning"]


def test_keepalive_and_empty_delta_do_not_extend_first_event_window(monkeypatch):
    clock = FakeClock()
    runner, handler, _logs = _runner(monkeypatch, _config(monkeypatch), clock)

    def once(_ctx, *callbacks, **_named):
        for _ in range(20):
            clock.advance(15)
            callbacks[3]()
            callbacks[2]("")
        return {"state": "done", "rc": 0}

    handler._run_once = once
    out = runner.attempt(0, runner.replay.attempt_budget_s(0))
    assert clock.now_s == 300
    assert (out["state"], out["rc"]) == ("timeout", 124)


def test_remaining_horizon_bounded_capacity_retries_and_legacy_budget(monkeypatch):
    config = _config(monkeypatch)
    clock = FakeClock()
    replay = _orchestrator(config, clock)
    budgets = []

    def attempt(index, budget):
        budgets.append(budget)
        clock.advance(10)
        if index < 2:
            return {"state": "agy_error", "status_code": 503, "err": "HTTP 503"}
        return {"state": "done", "rc": 0}

    p = importlib.import_module("core.stream_resilience_policy")
    out = replay.run_with_resilience(attempt, p.MidstreamStepLedger(), lambda: True)
    assert budgets[0] == pytest.approx(1014.5)
    assert budgets[1:] == pytest.approx([1003.0, 990.0])
    assert len(budgets) <= config.max_retries + 1 and out["state"] == "done"
    assert clock.now_s + config.retry_reserve_s <= config.retry_total_budget_s
    legacy = _orchestrator(_config(monkeypatch, enabled=False), FakeClock())
    assert legacy.attempt_budget_s(0) == pytest.approx(338.166)
    terminal_calls = []
    terminal = _orchestrator(config, FakeClock())
    terminal_out = terminal.run_with_resilience(
        lambda i, b: terminal_calls.append(i)
        or {"state": "timeout", "rc": 124, "err": "retry_budget_exhausted"},
        p.MidstreamStepLedger(), lambda: True,
    )
    assert terminal_calls == [0] and terminal_out["state"] == "timeout"


def test_timeout_overwrite_is_single_final_done_log(monkeypatch):
    clock = FakeClock()
    runner, handler, logs = _runner(monkeypatch, _config(monkeypatch), clock)

    def once(_ctx, *callbacks, defer_done_log=False, **_named):
        clock.advance(400)
        out = {"state": "done", "rc": 0}
        if not getattr(handler, "_defer_done_log", False):
            handler._log_done("m", out, 0, "test")
        return out

    handler._run_once = once
    out = runner.attempt(0, runner.replay.attempt_budget_s(0))
    assert (out["state"], out["rc"]) == ("timeout", 124)
    assert len(logs) == 1
    assert (logs[0]["state"], logs[0]["rc"]) == ("timeout", 124)


def _split(value, mode):
    if mode == "random":
        rng, chunks, offset = random.Random(42), [], 0
        while offset < len(value):
            end = min(len(value), offset + rng.randint(1, 7))
            chunks.append(value[offset:end])
            offset = end
        return chunks
    size = len(value) if mode == "whole" else int(mode[:-1])
    return [value[i:i + size] for i in range(0, len(value), size)]


def _chunk_run(monkeypatch, mode):
    clock = FakeClock()
    runner, handler, _logs = _runner(monkeypatch, _config(monkeypatch), clock)
    seen = {"content": [], "reasoning": []}
    runner.s.stream_text = lambda value: seen["content"].append(value) or True
    runner.s.stream_reasoning = lambda value: seen["reasoning"].append(value) or True

    def once(_ctx, *callbacks, **_named):
        clock.advance(10)
        callbacks[3]()
        callbacks[0]("")
        runner._note_progress("tool_calls", "")
        events = ((20, "content", "content-payload"),
                  (40, "reasoning", "reasoning-payload"),
                  (60, "tool_calls", '{"id":"call-1"}'))
        for at, kind, payload in events:
            clock.advance(at - clock.now_s)
            for chunk in _split(payload, mode):
                if kind == "content":
                    callbacks[0](chunk)
                elif kind == "reasoning":
                    callbacks[2](chunk)
                else:
                    runner._note_progress(kind, chunk)
        clock.advance(20)
        callbacks[3]()
        callbacks[2]("")
        runner._note_progress("tool_calls", "")
        clock.advance(20)
        return {"state": "done", "rc": 0}

    handler._run_once = once
    out = runner.attempt(0, runner.replay.attempt_budget_s(0))
    assert out["state"] == "done"
    snapshot = runner._activity_window.check_expired(clock.now_s)
    return snapshot, "".join(seen["content"]), "".join(seen["reasoning"])


@pytest.mark.parametrize("mode", ["whole", "1B", "7B", "random"])
def test_chunk_split_invariance_for_activity_and_text(monkeypatch, mode):
    activity = importlib.import_module("core.stream_activity_policy")
    snapshot, text, reasoning = _chunk_run(monkeypatch, mode)
    expected = activity.ActivitySnapshot(
        activity.ActivityState.COMPLETED, True, 360.0, "", 0.0, 100.0
    )
    assert snapshot == expected
    assert (text, reasoning) == ("content-payload", "reasoning-payload")


def test_total_safety_cap_expires_despite_regular_progress(monkeypatch):
    clock = FakeClock()
    runner, handler, logs = _runner(monkeypatch, _config(monkeypatch), clock)

    def once(_ctx, *callbacks, **_named):
        for _ in range(5):
            clock.advance(200)
            callbacks[0]("progress")
        clock.advance(14.5)
        callbacks[3]()
        return {"state": "done", "rc": 0}

    handler._run_once = once
    out = runner.attempt(0, runner.replay.attempt_budget_s(0))
    assert clock.now_s == pytest.approx(1014.5)
    assert (out["state"], out["rc"], out["had_progress"]) == ("timeout", 124, True)
    assert out["timeout_limit_s"] == pytest.approx(1014.5)
    assert out["err"] == "retry_budget_exhausted" and logs == [out]


def test_post_progress_keepalive_expires_at_sliding_idle_deadline(monkeypatch):
    clock = FakeClock()
    runner, handler, _logs = _runner(monkeypatch, _config(monkeypatch), clock)

    def once(_ctx, *callbacks, **_named):
        clock.advance(200)
        callbacks[0]("progress")
        clock.advance(300)
        callbacks[3]()
        return {"state": "done", "rc": 0}

    handler._run_once = once
    out = runner.attempt(0, runner.replay.attempt_budget_s(0))
    assert clock.now_s == 500
    assert (out["state"], out["rc"], out["had_progress"]) == ("timeout", 124, True)
    snapshot = runner._activity_window.check_expired(clock.now_s)
    reason = snapshot.state.value, snapshot.timeout_reason
    assert reason == ("idle_expired", "sliding_idle_timeout")
    assert (out["err"], out["timeout_limit_s"]) == ("retry_budget_exhausted", 300)


def test_client_disconnect_stops_retries_and_cleans_attempt(monkeypatch):
    clock = FakeClock()
    runner, handler, logs = _runner(monkeypatch, _config(monkeypatch), clock)
    attempts = []

    def once(ctx, *callbacks, **_named):
        attempts.append(ctx["attempt_index"])
        callbacks[0]("partial")
        runner.s.disconnected = True
        return {"state": "client_gone", "rc": 1}

    handler._run_once = once
    out = runner.replay.run_with_resilience(
        runner.attempt, runner.s.ledger, runner.s.keepalive, runner.cancelled
    )
    assert (out["state"], attempts) == ("client_gone", [0])
    assert runner.stop is None and "tool_stop" not in runner.s.ctx
    assert len(logs) == 1 and logs[0]["state"] == "client_gone"


def test_final_outcome_and_done_log_redact_secrets(monkeypatch):
    activity = importlib.import_module("core.stream_activity_policy")
    secrets = ("Bearer secret-token-123", "sk-live-secret-999", "api_key=topsecret")
    raw = {"state": "done", "rc": 0, "err": " ".join(secrets),
           "req_id": f"req {secrets[0]}", "cid": f"cid {secrets[2]}"}
    window = activity.SlidingActivityWindow(0, 300, 300, 1014.5)
    window.record_signal("content", "progress", 1)
    outcome = activity.render_final_outcome(raw, window.mark_completed(2))
    assert all(secret not in repr(outcome) for secret in secrets)

    clock = FakeClock()
    runner, handler, logs = _runner(monkeypatch, _config(monkeypatch), clock)
    runner.s.ctx["tag"], runner.cid = secrets[0], secrets[2]
    handler._run_once = lambda _ctx, *_args, **_named: raw
    runner.attempt(0, runner.replay.attempt_budget_s(0))
    assert all(secret not in repr(logs) for secret in secrets)
