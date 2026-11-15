"""Контракты W1/W2: синтетический replay не доказывает ASM-001 реального CLI."""
from __future__ import annotations

import importlib
import io
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from tests.stream_resilience_fakes import FakeClock, build_incident_ledger, tool_events
from tests.test_precommit_sse_coordination import _incident, _tail_writer

_AGY = str(Path(__file__).resolve().parents[1] / "bridges/agy-bridge")

def test_policy_504_transient_vs_first_event_terminal():
    p = importlib.import_module("core.stream_resilience_policy")
    cfg = p.RetryBudgetConfig()
    for status in (502, 503, 504):
        detail = "upstream sent no response headers within 180s"
        category = p.normalize_stream_interruption(status, detail)
        assert category == p.FailureCategory.CAPACITY_EXHAUSTED
        assert p.compute_attempt_decision(cfg, 0, 0, category).allow_retry
    category = p.normalize_stream_interruption(504, "first_event_timeout_exceeded")
    assert category == p.FailureCategory.FATAL_REQUEST_ERROR
    assert not p.compute_attempt_decision(cfg, 0, 0, category).allow_retry

def test_policy_budget_1020s_attempt_decision_and_horizon_floor(monkeypatch):
    p = importlib.import_module("core.stream_resilience_policy")
    rt = importlib.import_module("core.stream_resilience_runtime")
    monkeypatch.setenv("BRIDGE_STREAM_RETRY_TOTAL_BUDGET_S", "1020.0")
    total = rt.StreamResilienceConfig.from_env().retry_total_budget_s
    assert total == 1020.0
    budget = p.RetryBudgetConfig(total, 5.5, 5.0, 3)
    for i, elapsed, want in ((0, 0, 338.166), (1, 308, 353.25), (2, 616, 398.5)):
        decision = p.compute_attempt_decision(budget, i, elapsed)
        assert decision.allow_retry and decision.attempt_budget_s == want
    elapsed = 0.0
    for attempt, expected in enumerate((338.166, 334.167, 326.167)):
        effective = p.effective_attempt_budget_s(budget, attempt, elapsed, 300, 8)
        assert effective == pytest.approx(expected, abs=0.000001)
        assert effective >= 300.0
        elapsed += effective + (8.0 if attempt < 2 else 0.0)
    assert elapsed == pytest.approx(1014.5)
    floor = replace(budget, total_budget_s=921.5)
    for i in range(3):
        assert p.effective_attempt_budget_s(floor, i, i * 308, 300, 8) == 300
    assert p.effective_attempt_budget_s(budget, 2, 714.501, 300, 8) == 0.0

@pytest.mark.parametrize("active", [355, 360])
def test_ledger_incident_scale_355_suppresses_committed_tools(active):
    p = importlib.import_module("core.stream_resilience_policy")
    ledger, arbiter = _incident(p, active), Mock()
    for record in build_incident_ledger(active):
        if ledger.should_forward_step(record["step_idx"]):
            arbiter(record)
    assert ledger.last_committed_step_idx == active - 1
    assert [call.args[0]["step_idx"] for call in arbiter.call_args_list] == [active]
    snapshot = ledger.snapshot()
    assert snapshot.trace_complete and sum(r.completed for r in snapshot.records) >= 218
    assert all(isinstance(r, p.ToolExecutionTraceRecord) for r in snapshot.records)
    assert snapshot.records[0].identity == (1, "history-1", "shell")
    for key in ("call_id", "tool_call_id", "id"):
        pair = tool_events(active, "same", "read_file", key)
        for event in pair + pair:
            ledger.record_tool_event(event, source="stdout")
    ids = [r.identity for r in ledger.snapshot().records]
    assert ids.count((active, "same", "read_file")) == 1
    for event in tool_events(None, "ordinal", "read_file") * 2:
        ledger.record_tool_event(event, source="stdout")
    ids = [r.identity for r in ledger.snapshot().records if r.call_id == "ordinal"]
    assert len(ids) == 1 and isinstance(ids[0][0], int)
    for events in ((tool_events(active)[1],), ({"type": "gap"},)):
        broken = _incident(p, active)
        for event in events:
            broken.record_tool_event(event, source="stdout")
        assert not broken.snapshot().trace_complete
    broken = _incident(p, active)
    broken.record_tool_event(tool_events(active, None)[0], source="stdout")
    broken.record_tool_event(tool_events(active, None)[1], source="transcript")
    assert not broken.snapshot().trace_complete

@pytest.mark.parametrize("tool,completed,broken,expected", [
    ("", False, "", True), ("read_file", True, "", True),
    ("read_file", False, "", False), ("bash", False, "", False),
    ("bash", True, "", False), ("unknown_tool", False, "", False),
    ("unknown_tool", True, "", False), ("", False, "trace_complete", False),
    ("", False, "trace_trusted", False),
    ("", False, "client_delivery_reconciled", False)])
def test_safety_can_safely_replay_turn_four_cases(tool, completed, broken, expected):
    p = importlib.import_module("core.stream_resilience_policy")
    ledger = _incident(p)
    if tool:
        pair = tool_events(355, "active", tool)
        for event in pair if completed else pair[:1]:
            ledger.record_tool_event(event, source="stdout")
    snapshot = ledger.snapshot()
    if broken:
        snapshot = replace(snapshot, **{broken: False})
    result = p.can_safely_replay_turn(snapshot, last_committed_step_idx=354)
    assert result is expected

@pytest.mark.parametrize("explicit", [240.0, 300.0])
def test_rollback_uncommitted_buffer_and_explicit_timeout_preserved(explicit):
    p = importlib.import_module("core.stream_resilience_policy")
    rt = importlib.import_module("core.stream_resilience_runtime")
    buffer = p.UncommittedTurnBuffer()
    parts = ('<tool_', 'call>{"name":"write_file","arguments":', '{"path":"private')
    for part in parts:
        buffer.stage_fragment(part)
    buffer.rollback_uncommitted()
    assert buffer.commit_boundary() == ""
    buffer.stage_fragment("Только новый ответ.")
    assert buffer.commit_boundary() == "Только новый ответ."
    env = {"BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S": str(explicit)}
    for flag in ("MIDSTREAM_RETRY", "PRECOMMIT_FLUSH",
                 "PASSTHROUGH_EARLY_FLUSH", "TOOL_ROLLBACK"):
        env[f"BRIDGE_STREAM_{flag}_ENABLED"] = "false"
    assert rt.StreamResilienceConfig.from_env(env).first_event_timeout_s == explicit
    assert rt.StreamResilienceConfig.from_env({}).first_event_timeout_s == 120.0

@pytest.mark.parametrize("alias", ["_S", ""])
def test_agy_first_event_snapshot_and_diagnostic_isolation(
    monkeypatch, tmp_path, alias):
    monkeypatch.syspath_prepend(_AGY)
    m = importlib.import_module("agy_runtime.midstream_resilience")
    for key in ("BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S",
                "AGY_BRIDGE_FIRST_TOKEN_TIMEOUT_S", "AGY_BRIDGE_FIRST_TOKEN_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(f"AGY_BRIDGE_FIRST_TOKEN_TIMEOUT{alias}", "240")
    run = NS()
    assert m.current_first_event_timeout_s(run, 120.0) == 240.0
    path = tmp_path / "dynamic.json"
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(path))
    path.write_text('{"first_event_timeout_s":300}', encoding="utf-8")
    monkeypatch.setenv("BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S", "260")
    assert m.current_first_event_timeout_s(NS(), 120.0) == 300.0
    assert m.current_first_event_timeout_s(run, 120.0) == 240.0
    outcomes = [{"state": "first_token_timeout", "err": f"no agy event within {n:g}s"}
                for n in (240, 300, 240, 300)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        limits = list(pool.map(
            lambda o: m.first_event_timeout_for_result(o, True, 120), outcomes))
    assert limits == [240, 300, 240, 300]
    for out in ({}, {"err": "no agy event within NaNs"},
                {"timeout_limit_s": 300, "err": "no agy event within 240s"}):
        with pytest.raises(ValueError):
            m.first_event_timeout_for_result(out, True, 120.0)
    assert m.first_event_timeout_for_result({}, False, 137.0) == 137.0
    clock, logs = FakeClock(), []
    monkeypatch.setattr(m, "time", clock)
    tail = NS(run_ref=run, _ready=NS(wait=lambda timeout: clock.advance(timeout)),
              stop_event=Event(), done_event=Event(), _cid8=lambda: "test")
    m.run_transcript_tail_loop(tail, (120.0, 0.1, logs.append))
    assert clock.now_s == pytest.approx(240.0, abs=0.051)
    assert any("240s" in line for line in logs)

def _assert_pump_tool_state(m, run, collector):
    state = m.PumpToolState(lambda value: int(value) if value is not None else None)
    for event in tool_events(355, "pump", "read_file"):
        state_name = "DONE" if event["type"] == "tool_result" else "RUNNING"
        step = dict(event, step_type="tool", state=state_name)
        m.capture_pump_tool_step(run, step, state)
        m.emit_done_tool_trace_if_any(run, step, "tool", state)
    rows = collector.snapshot().records
    assert any(r.call_id == "pump" and r.completed for r in rows)

@pytest.mark.parametrize("source", ["transcript", "sqlite"])
def test_agy_same_pass_tail_capture_and_pump_tool_state(monkeypatch, tmp_path, source):
    monkeypatch.syspath_prepend(_AGY)
    m = importlib.import_module("agy_runtime.midstream_resilience")
    collector = m.AgyToolTraceCollector()
    capture = Mock(wraps=collector.record_cli_event)
    monkeypatch.setattr(collector, "record_cli_event", capture)
    run = NS(q=Mock(), tool_trace_collector=collector)
    payload = json.dumps(build_incident_ledger()[0]).encode()
    path = tmp_path / "tail.jsonl"
    path.write_bytes(payload + b"\n")
    tail = NS(run_ref=run, dead=False, sqlite_active=True, _next_poll_at=0.0,
              _sqlite_permitted=Mock(return_value=True))
    tail._emit_record = lambda raw: run.q.put(("text", json.loads(raw)["content"]))
    release = Event()
    def publish(_chunk):
        capture.assert_called_once()
        release.set()
    run.q.put.side_effect = publish
    with sqlite3.connect(":memory:", check_same_thread=False) as db:
        db.execute("CREATE TABLE steps (payload BLOB)")
        db.execute("INSERT INTO steps VALUES (?)", (payload,))
        selects = []
        db.set_trace_callback(lambda s: selects.append(s) if "SELECT" in s else None)
        tail._read_transcript = Mock(side_effect=lambda: [
            tail._emit_record(line) for line in path.read_bytes().splitlines()
        ] if source == "transcript" else None)
        tail._poll_sqlite = Mock(side_effect=lambda: [tail._emit_record(row[0])
            for row in db.execute("SELECT payload FROM steps").fetchall()
        ] if source == "sqlite" else None)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_tail_writer, release, db, path, payload, source)
            m.tick_transcript_with_tool_capture(tail, 0.25)
            future.result(timeout=2)
    assert capture.call_count == 1 and run.q.put.call_count == 1
    assert tail._read_transcript.call_count == tail._poll_sqlite.call_count == 1
    assert len(selects) == (source == "sqlite")
    _assert_pump_tool_state(m, run, collector)

def test_sse_runner_replays_active_step_with_keepalive(monkeypatch):
    monkeypatch.syspath_prepend(_AGY)
    helpers = importlib.import_module("agy_runtime.sse_stream_helpers")
    runner = importlib.import_module("agy_runtime.sse_body_runner")
    p = importlib.import_module("core.stream_resilience_policy")
    ledger, wire, attempts = _incident(p), [], []
    handler = NS(wfile=io.BytesIO(), send_response=Mock(), send_header=Mock(),
                 end_headers=Mock(), _arm_flush_window=Mock(), _graceful_notice=Mock(),
                 _usage_payload=lambda *_: {}, _send=Mock(), close_connection=False,
                 _emit=lambda x: wire.append(x) or True,
                 _error_body=lambda out, _enabled: out.get("error"))
    ctx = {"model": "m", "conversation_id": "bbdb91e5", "step_ledger": ledger}
    hooks = (lambda _key, default=False: default, Mock(), lambda: "stop", Mock())
    session = helpers.SseStreamSession(handler, ctx, hooks)
    session.arbiter = Mock()
    session.handle_step_event("text", {"step_index": 354, "text": "Старая история."})
    assert not session.arbiter.mock_calls
    session.handle_step_event("text", {"step_index": 355, "text": "Новый шаг."})
    assert session.arbiter.mock_calls
    monkeypatch.setenv("BRIDGE_STREAM_MIDSTREAM_RETRY_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S", "300")
    def once(_ctx, *callbacks):
        attempts.append(_ctx.get("conversation_id"))
        if len(attempts) == 1:
            callbacks[0]('<tool_call>{"name":"write_file","arguments":{')
            callbacks[2]("Думаю.")
            return {"state": "agy_error", "err": "HTTP 504",
                    "conversation_id": "bbdb91e5", "trace_snapshot": ledger.snapshot()}
        callbacks[3]()
        callbacks[0]("Новый ответ.")
        return {"state": "done", "rc": 0, "conversation_id": "bbdb91e5"}
    handler._run_once = once
    runner.serve_sse_body(handler, ctx, hooks)
    wire = "".join(wire)
    assert attempts == ["bbdb91e5", "bbdb91e5"]
    assert ": keepalive\n\n" in wire and "Старая история." not in wire
    assert wire.count("Новый ответ.") == 1 and "write_file" not in wire
    assert wire.endswith("data: [DONE]\n\n")
