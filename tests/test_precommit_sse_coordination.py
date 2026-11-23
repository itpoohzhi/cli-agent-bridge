"""Контракты single-writer SSE; сеть ограничена f.MockUpstream(port=0)."""
from __future__ import annotations

import ast
import importlib
import importlib.util
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
from pathlib import Path
from threading import Barrier, Event
from types import SimpleNamespace as NS

import pytest

from tests import stream_resilience_fakes as f

_FIELDS = (
    "idle_timeout_s safety_cap_s heartbeat_interval_s passthrough_read_timeout_s "
    "midstream_retry_enabled precommit_flush_enabled passthrough_early_flush_enabled "
    "tool_rollback_enabled max_retries retry_total_budget_s retry_reserve_s "
    "retry_min_attempt_s backoff_base_s backoff_cap_s backoff_jitter_ratio "
    "first_event_timeout_s precommit_flush_s passthrough_flush_s early_poll_interval_s "
    "cross_hop_margin_s ledger_max_entities readonly_tools mutating_tools "
    "sliding_activity_window_enabled sliding_idle_timeout_s"
).split()
_FLAGS = _FIELDS[4:8] + ["sliding_activity_window_enabled"]

class _Sink:
    accepts_presend_errors, error_type, client_gone = False, "", False

    def __init__(self):
        self.headers, self.chunks, self.statuses = [], [], []
        self.started, self.changed, self.busy = Event(), Event(), False

    def start(self, status, headers):
        assert not self.statuses, "Двойной HTTP commit"
        self.statuses.append(status)
        self.headers.extend(headers)
        self.started.set()

    def write(self, data):
        assert not self.busy, "Одновременные записи в SSE"
        self.busy = True
        try:
            time.sleep(0)
            if self.client_gone:
                raise BrokenPipeError
            self.chunks.append(data)
            self.changed.set()
        finally:
            self.busy = False

def _call(adapter, sink, window):
    body = {"model": "m", "stream": True}
    adapter.handle(path="/v1/chat/completions", raw_body=json.dumps(body).encode(),
                   request=body, headers={}, sink=sink, window=window)

def _tail_writer(release, db, path, payload, source):
    assert release.wait(2)
    if source == "sqlite":
        db.execute("INSERT INTO steps VALUES (?)", (payload,))
    else:
        path.write_bytes((payload + b"\n") * 2)

def _incident(p, active=355):
    ledger = p.MidstreamStepLedger(512, {"read_file", "bash"}, {"bash", "shell"})
    for rec in f.build_incident_ledger(active):
        fn = ledger.mark_step_completed if rec["committed"] else ledger.pin_active_step
        fn(rec)
    return ledger

def _profile(monkeypatch):
    for key, value in {"PASSTHROUGH_EARLY_FLUSH_ENABLED": "true",
                       "PASSTHROUGH_FLUSH_S": "20", "MIDSTREAM_RETRY_ENABLED": "true",
                       "FIRST_EVENT_TIMEOUT_S": "300"}.items():
        monkeypatch.setenv(f"BRIDGE_STREAM_{key}", value)
    monkeypatch.setenv("BRIDGE_IDLE_TIMEOUT_S", "1050")
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_READ_TIMEOUT_S", "330")

def _proxy(hop, handler):
    def start(status, headers):
        handler.send_response(status)
        for key, value in headers:
            handler.send_header(key, value)
        handler.end_headers()
    sink = NS(start=start, write=handler.wfile.write, client_gone=False,
              accepts_presend_errors=False, error_type="")
    _call(hop[0], sink, hop[1])

def test_config_25_neutral_params_and_five_flags_default_false(monkeypatch, tmp_path):
    rt = importlib.import_module("core.stream_resilience_runtime")
    config = rt.StreamResilienceConfig.from_env({})
    assert {f.name for f in fields(config)} == set(_FIELDS) and len(_FIELDS) == 25
    assert all(getattr(config, flag) is False for flag in _FLAGS)
    assert (config.first_event_timeout_s, config.idle_timeout_s) == (120, 300)
    assert (config.retry_total_budget_s, config.ledger_max_entities) == (1020, 512)
    path = tmp_path / "dynamic_config.json"
    path.write_text("{broken", encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(path))
    enabled = {f"BRIDGE_STREAM_{flag.upper()}": "true" for flag in _FLAGS}
    broken = rt.StreamResilienceConfig.from_env(enabled)
    assert all(getattr(broken, flag) is False for flag in _FLAGS)
    path.write_text('{"precommit_flush_enabled":true,"first_event_timeout_s":300}')
    refreshed = rt.StreamResilienceConfig.from_env(
        {"BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S": "240"})
    assert refreshed.precommit_flush_enabled and refreshed.first_event_timeout_s == 300
    assert config.first_event_timeout_s == 120 and not config.precommit_flush_enabled

@pytest.mark.parametrize("enabled", [False, True])
def test_cross_hop_timeout_validator_and_default_off_preservation(enabled):
    p = importlib.import_module("core.stream_resilience_policy")
    rt = importlib.import_module("core.stream_resilience_runtime")
    old = rt.StreamResilienceConfig.from_env({})
    assert (old.idle_timeout_s, old.passthrough_read_timeout_s) == (300, 300)
    assert old.first_event_timeout_s == 120
    cfg = replace(old, midstream_retry_enabled=enabled, idle_timeout_s=1050,
                  first_event_timeout_s=300, passthrough_read_timeout_s=330)
    for hop in ("passthrough", "backend"):
        p.validate_cross_hop_timeouts(cfg, hop=hop)
    p.validate_cross_hop_timeouts(old, hop="passthrough")
    for idle, read in ((1049.999 if enabled else 329.999, 330), (1050, 329.999)):
        with pytest.raises(ValueError):
            p.validate_cross_hop_timeouts(
                replace(cfg, idle_timeout_s=idle, passthrough_read_timeout_s=read),
                hop="passthrough")
    if enabled:
        with pytest.raises(ValueError):
            p.validate_cross_hop_timeouts(
                replace(cfg, retry_total_budget_s=921.499), hop="backend")


def test_cross_hop_sliding_activity_window_contract():
    p = importlib.import_module("core.stream_resilience_policy")
    rt = importlib.import_module("core.stream_resilience_runtime")
    old = rt.StreamResilienceConfig.from_env({})
    cfg = replace(old, midstream_retry_enabled=True, idle_timeout_s=1050,
                  first_event_timeout_s=300, passthrough_read_timeout_s=330)
    if hasattr(old, "sliding_activity_window_enabled"):
        cfg = replace(cfg, sliding_activity_window_enabled=True,
                      sliding_idle_timeout_s=300)
    assert getattr(cfg, "sliding_activity_window_enabled", False) is True
    sliding_idle = getattr(cfg, "sliding_idle_timeout_s", 300)
    assert cfg.first_event_timeout_s <= sliding_idle < cfg.passthrough_read_timeout_s
    assert cfg.retry_total_budget_s + 30 <= cfg.idle_timeout_s
    for hop in ("passthrough", "backend"):
        p.validate_cross_hop_timeouts(cfg, hop=hop)
    with pytest.raises(ValueError):
        p.validate_cross_hop_timeouts(
            replace(cfg, passthrough_read_timeout_s=sliding_idle), hop="passthrough")
    with pytest.raises(ValueError):
        p.validate_cross_hop_timeouts(
            replace(cfg, idle_timeout_s=cfg.retry_total_budget_s + 29.999),
            hop="passthrough")


@pytest.mark.parametrize("threshold", [15.0, 20.0])
def test_early_commit_single_writer_keepalive_and_disconnect(threshold):
    rt = importlib.import_module("core.stream_resilience_runtime")
    p = importlib.import_module("core.stream_resilience_policy")
    clock, sink = f.FakeClock(), _Sink()
    cfg = replace(rt.StreamResilienceConfig.from_env({}), precommit_flush_enabled=True,
                  passthrough_early_flush_enabled=True)
    coord = rt.EarlyCommitSinkCoordinator(sink, cfg, clock=clock.monotonic)
    ready = NS(is_set=lambda: clock.now_s >= threshold + 1)
    ready.wait = lambda delay: clock.advance(delay) or ready.is_set()
    assert not p.should_flush_precommit_headers(threshold - 0.001, threshold, False)
    assert p.should_flush_precommit_headers(threshold, threshold, False)
    coord.await_headers_or_flush(ready, flush_after_s=threshold)
    assert sink.statuses == [200]
    assert ("Content-Type", "text/event-stream") in sink.headers
    assert b": keepalive\n\n" in sink.chunks
    barrier = Barrier(8)
    def emit(index):
        barrier.wait(timeout=2)
        coord.emit_chunk(f"data: {index}\n\n".encode())
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(emit, range(8)))
    assert {f"data: {i}\n\n".encode() for i in range(8)} <= set(sink.chunks)
    sink.client_gone = True
    coord.emit_chunk(b": keepalive\n\n")
    coord.cancel()
    before = list(sink.chunks)
    clock.advance(30)
    coord.emit_chunk(b"data: forbidden\n\n")
    assert sink.chunks == before and coord.cancelled

def test_post_flush_sse_error_event_redacted_and_done():
    rt = importlib.import_module("core.stream_resilience_runtime")
    sink = _Sink()
    coord = rt.EarlyCommitSinkCoordinator(sink, rt.StreamResilienceConfig.from_env({}))
    coord.emit_chunk(b": keepalive\n\n")
    coord.emit_error_and_done("Authorization: Bearer synthetic-secret", model="test")
    wire = b"".join(sink.chunks).decode()
    assert sink.statuses == [200] and "synthetic-secret" not in wire
    frame = next(f for f in wire.split("\n\n") if '"error"' in f)
    error = json.loads(next(s[6:] for s in frame.splitlines() if s[:6] == "data: "))
    assert error["error"] and wire.endswith("data: [DONE]\n\n")
    assert wire.count("data: [DONE]") == 1

def _assert_passthrough_response(future, sink, status, silent):
    future.result(timeout=5)
    wire = b"".join(sink.chunks)
    assert sink.statuses == [200 if silent > 20 else status]
    assert status != 200 or wire.endswith(b"data: [DONE]\n\n")
    if status != 200 and silent > 20:
        assert b'"error"' in wire and wire.endswith(b"data: [DONE]\n\n")

@pytest.mark.parametrize("status,silent", [
    (200, 25), (200, 181), (502, 10), (504, 10), (504, 25),
    (200, 1014.5), (200, 1020.0)])
def test_passthrough_presend_coop_wait_and_multihop_1014s_no_signal_s(
    monkeypatch, status, silent):
    pt = importlib.import_module("core.passthrough_precommit")
    am = importlib.import_module("adapters.passthrough_adapter")
    sliding = importlib.import_module("core.passthrough_sliding_window")
    clock, gate, sink = f.FakeClock(now_s=time.monotonic()), Event(), _Sink()
    monkeypatch.setattr(pt, "time", NS(monotonic=clock.monotonic, sleep=clock.sleep))
    _profile(monkeypatch)
    start = clock.monotonic()
    hops = [sliding.SlidingDeadline(start + 1050) for _ in range(2)]
    for hop in hops:
        hop.arm(sliding.init_sliding_stream(start, 1050, 1050, 3600, enabled=True))
    limits = am.PassthroughLimits(
        read_timeout_s=330, idle_timeout_s=1050, total_timeout_s=1050)
    with f.MockUpstream(f.MockResponse(status, headers_gate=gate), port=0) as inner:
        with f.MockUpstream(port=0) as outer, ThreadPoolExecutor(max_workers=1) as pool:
            adapters = [am.PassthroughAdapter(str(i), {"base_url": u.url + "/v1"},
                    lambda: {}, limits=limits) for i, u in enumerate((inner, outer))]
            def forward(handler):
                _proxy((adapters[0], hops[0]), handler)
            monkeypatch.setattr(outer, "_respond", forward)
            future = pool.submit(_call, adapters[1], sink, hops[1])
            try:
                assert inner.requested.wait(2)
                clock.advance(min(silent, 20.001))
                if silent > 20:
                    assert sink.started.wait(2) and sink.statuses == [200]
                    assert sink.changed.wait(2) and b": keepalive\n\n" in sink.chunks
                    clock.advance(silent - 20.001)
                else:
                    assert not sink.statuses
                assert all(h.deadline_s == start + 1050 > clock.now_s for h in hops)
                gate.set()
                _assert_passthrough_response(future, sink, status, silent)
            finally:
                gate.set()
                inner.disconnect()
                for adapter in adapters:
                    adapter.shutdown()

def test_w2b_server_facade_request_snapshot_and_real_diagnostic(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    path = root / "bridges/agy-bridge/server.py"
    monkeypatch.syspath_prepend(str(path.parent))
    module = importlib.import_module("agy_runtime.midstream_resilience")
    monkeypatch.delenv("AGY_BRIDGE_FLEET", raising=False)
    monkeypatch.setenv("AGY_BRIDGE_KEY", "test-resilience-isolated")
    spec = importlib.util.spec_from_file_location("agy_resilience_facade_test", path)
    bridge = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, bridge)
    spec.loader.exec_module(bridge)
    before = bridge.FIRST_TOKEN_TIMEOUT_S
    monkeypatch.setenv("BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S", "240")
    assert module.current_first_event_timeout_s(NS(), 120) == 240
    monkeypatch.setenv("BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S", "300")
    out = {"state": "first_token_timeout", "err": "no agy event within 240s"}
    error = bridge.Handler._error_body(out, resilience=True)
    assert "240s" in error["message"] and bridge.FIRST_TOKEN_TIMEOUT_S == before
    tree = ast.parse(path.read_text(encoding="utf-8"))
    execute = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "_execute")
    attributes = {n.attr for n in ast.walk(execute) if isinstance(n, ast.Attribute)}
    assert "current_first_event_timeout_s" in attributes
