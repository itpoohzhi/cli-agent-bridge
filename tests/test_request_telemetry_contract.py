"""Контракт /v1/telemetry (RW-006..RW-008): канонические имена + UI-алиасы, топология и usage passthrough."""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent
for _p in (str(_TESTS), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.telemetry_hooks import TelemetryHooksMixin  # noqa: E402
from core.telemetry_usage import extract_usage  # noqa: E402

import server  # noqa: E402

CANON_ALIASES = {
    "p50_ttfb_ms": "ttfb_p50_ms", "p95_ttfb_ms": "ttfb_p95_ms", "p99_ttfb_ms": "ttfb_p99_ms",
    "p50_total_ms": "total_p50_ms", "p95_total_ms": "total_p95_ms", "p99_total_ms": "total_p99_ms",
    "max_total_ms": "total_max_ms",
}
ROW_ALIASES = {"backend_id": "backend", "ts_epoch": "ts", "status_code": "status", "stream_chunks": "chunks"}


def _flow_of(topology):
    from core.telemetry_flow import build_architecture_flow

    return build_architecture_flow([], [], {"total_requests": 0}, topology)


def test_flow_nodes_without_traffic_report_explicit_zero():
    """Узлы топологии без трафика отдаются с нулём, а не пропускаются."""
    flow = _flow_of({
        "tier1_entry_callers": {"nodes": [{"id": "quiet", "name": "q"}]},
        "tier2_l7_bridges": {"nodes": [{"id": "b", "port": 1, "backends": ["none"]}]},
        "tier3_l4_egress_proxies": {"nodes": [{"id": "e", "port": 2, "match": [":2"]}]},
    })
    assert [n["requests"] for n in flow["tier1_entry_callers"]["nodes"]] == [0, 0]  # узел + агрегат «other»
    assert [n["requests"] for n in flow["tier2_l7_bridges"]["nodes"]] == [0]
    assert [n["requests"] for n in flow["tier3_l4_egress_proxies"]["nodes"]] == [0]


def test_clean_row_marks_rate_only_for_aggregates():
    """ok_rate_pct добавляется только агрегатам: строки журнала не получают лишний ключ."""
    from core.telemetry_sql import clean_row

    assert "ok_rate_pct" not in clean_row({"requests": 3, "ok_requests": 2})
    assert clean_row({"requests": 3, "ok_requests": 3}, True)["ok_rate_pct"] == 100.0
    assert clean_row({"total_requests": 0}, True)["ok_rate_pct"] == 0.0


def test_payload_has_canonical_and_ui_alias_fields(telemetry_payload):
    _, payload = telemetry_payload
    summary = payload["summary"]
    for canon, alias in CANON_ALIASES.items():
        assert alias in summary and summary[alias] == summary[canon] is not None, canon
    assert (summary["total_p50_ms"], summary["ttfb_p95_ms"]) == (250.0, 38.5)
    assert payload["dropped_events"] == 0 and "prune_errors" in payload
    for section in ("by_model", "by_backend"):
        row = payload[section][0]
        assert row["backend"] == row["backend_id"] and row["p50_ms"] == row["p50_total_ms"] == row["total_p50_ms"]
        assert row["avg_ms"] == row["avg_total_ms"] and row["errors"] == row["error_requests"]
    routes = {r["model"]: (r["outbound_target"], r["egress_proxy"]) for r in payload["by_model"]}
    assert routes == {"m-a": (":9887", ":10820 (xray SOCKS5)"), "m-b": (":9886", "direct")}  # колонка «Маршрут выхода» UI
    recent = payload["recent_requests"][0]
    for canon, alias in ROW_ALIASES.items():
        assert recent[alias] == recent[canon], canon
    assert recent["chunks"] == 7 and recent["status"] == 200 and recent["ts"] == recent["ts_epoch"]
    json.dumps(payload)  # JSON-сериализуемость реального ответа


def test_empty_or_disabled_payload_keeps_alias_keys(telemetry_store):
    summary = telemetry_store.get_telemetry_payload()["summary"]
    assert all(alias in summary for alias in CANON_ALIASES.values()) and summary["ttfb_p50_ms"] is None


def test_architecture_flow_aliases_and_dynamic_topology(telemetry_store, telemetry_event, monkeypatch):
    topology = {
        "tier1_entry_callers": {"layer": "l1", "description": "d", "nodes": [{"id": "ci", "name": "CI", "ua": ["ci-bot"]}]},
        "tier2_l7_bridges": {"layer": "l2", "description": "d", "nodes": [
            {"id": "universal", "name": "hub", "port": 9882, "all": True},
            {"id": "extra-9999", "name": "extra", "port": 9999, "backends": ["extra"]}]},
        "tier3_l4_egress_proxies": {"layer": "l3", "description": "d", "nodes": [
            {"id": "px", "name": "px", "port": 7777, "match": [":7777"]}]},
    }
    monkeypatch.setenv("BRIDGE_TELEMETRY_TOPOLOGY_JSON", json.dumps(topology))
    telemetry_store.record_request(telemetry_event(backend_id="extra", egress_proxy=":7777 (px)", user_agent="ci-bot/1"))
    telemetry_store.flush()
    flow = telemetry_store.get_telemetry_payload()["architecture_flow"]
    tier2 = {n["id"]: n for n in flow["tier2_l7_bridges"]["nodes"]}
    assert tier2["extra-9999"]["requests"] == 1 and tier2["universal"]["requests"] == 1
    assert flow["bridges"] == flow["tier2_l7_bridges"]["nodes"] and flow["egress"] == flow["tier3_l4_egress_proxies"]["nodes"]
    assert flow["callers"] == flow["tier1_entry_callers"]["nodes"]
    assert {n["id"]: n["requests"] for n in flow["egress"]} == {"px": 1}
    assert {n["id"]: n["requests"] for n in flow["callers"]}["ci"] == 1
    assert all("port" in node for node in flow["bridges"])


def _parity_events(telemetry_event):
    """Детерминированный набор: успехи, ошибка, стрим с токенами и сабагент с двумя моделями/бэкендами."""
    now = time.time()
    return [
        telemetry_event(request_id="p1", ts_epoch=now - 50, total_ms=100.0, ttfb_ms=10.0, queue_ms=1.0),
        telemetry_event(request_id="p2", ts_epoch=now - 40, total_ms=200.0, ttfb_ms=20.0, queue_ms=2.0),
        telemetry_event(request_id="p3", ts_epoch=now - 30, total_ms=300.0, ttfb_ms=30.0, queue_ms=3.0,
                        status_code=503, error_type="overloaded", model="m-b", backend_id="muse", route_mode="cli",
                        outbound_target=":9886", egress_proxy="direct"),
        telemetry_event(request_id="p4", ts_epoch=now - 20, total_ms=400.0, ttfb_ms=40.0, queue_ms=4.0, stream=True,
                        stream_chunks=3, prompt_tokens=20, completion_tokens=10, cached_tokens=0, total_tokens=30),
        telemetry_event(request_id="p5", ts_epoch=now - 10, total_ms=500.0, ttfb_ms=50.0, queue_ms=5.0,
                        subagent_id="coder-1", user_agent="claude-cli/2.0", response_bytes=1024),
    ]


def _parity_snapshots(tmp_path, events):
    """Снимок агрегатов за окно на DuckDB и на sqlite3-фолбэке с одинаковыми событиями."""
    from core.request_telemetry import RequestTelemetryStore

    stores = []
    try:
        for force_sqlite, engine in ((False, "duckdb"), (True, "sqlite3")):
            store = RequestTelemetryStore(str(tmp_path / engine / "bridge_telemetry.duckdb"),
                                          force_sqlite=force_sqlite, autostart=False, enabled=True)
            assert store.ensure_open() and store.engine == engine
            stores.append(store)
            assert [store.record_request(ev) for ev in events] == [True] * len(events)
            assert store.flush() == len(events)
        return [store.get_telemetry_payload(window_hours=24.0, limit=50) for store in stores]
    finally:
        for store in stores:
            store.close()


def test_duckdb_and_sqlite_aggregate_parity(tmp_path, telemetry_event):
    """F-027: DuckDB и sqlite3-фолбэк отдают одинаковый снимок агрегатов на одинаковых событиях."""
    pytest.importorskip("duckdb")
    duck, sqlite = _parity_snapshots(tmp_path, _parity_events(telemetry_event))
    volatile = {"engine", "db_path", "generated_at"}
    assert set(duck) == set(sqlite)
    assert {k: v for k, v in duck.items() if k not in volatile} == {k: v for k, v in sqlite.items() if k not in volatile}
    summary = duck["summary"]
    assert (summary["total_requests"], summary["ok_requests"], summary["error_requests"], summary["ok_rate_pct"]) == (
        5, 4, 1, 80.0)
    assert (summary["avg_ttfb_ms"], summary["avg_total_ms"], summary["max_total_ms"]) == (30.0, 300.0, 500.0)
    assert (summary["p50_ttfb_ms"], summary["p95_ttfb_ms"]) == (30.0, 48.0)
    assert (summary["p50_total_ms"], summary["p95_total_ms"]) == (300.0, 480.0)
    assert (summary["prompt_tokens"], summary["total_tokens"]) == (60, 90)
    for section in ("by_model", "by_backend", "by_client", "by_hour", "recent_requests"):
        assert len(duck[section]) == len(sqlite[section]) > 0, section
    assert duck["architecture_flow"] == sqlite["architecture_flow"]


class _Sink:
    recent_limit = 100

    def __init__(self):
        self.events = []

    def record_request(self, event):
        self.events.append(event)
        return True


class _Handler(TelemetryHooksMixin):
    headers = {}
    command = "POST"
    path = "/v1/chat/completions"
    client_address = ("127.0.0.1", 1)
    wfile = io.BytesIO()
    connection = None

    def flush(self):
        return None


def _passthrough(chunks, status=200):
    """Passthrough через настоящий _HandlerSink: байты ответа идут в клиента и в хвост телеметрии."""
    store = _Sink()
    handler = _Handler()
    handler.wfile = io.BytesIO()
    handler.wfile.flush = lambda: None
    handler._telemetry_srv = lambda: SimpleNamespace(
        REQUEST_TELEMETRY=store, BACKENDS={}, _bridge_env=lambda _n, d="": d, _log=lambda _m: None, _err_summary=str)
    handler._telemetry_begin()
    sink = server._HandlerSink(handler)
    for chunk in chunks:
        sink.write(chunk)
    handler._telemetry_passthrough_done(status)
    return store.events[0], handler.wfile.getvalue()


def test_passthrough_sse_usage_reaches_telemetry():
    pad = b'data: {"choices":[{"delta":{"content":"' + b"x" * 6000 + b'"}}]}\n\n'
    final = b'data: {"choices":[],"usage":{"prompt_tokens":11,"completion_tokens":4,"total_tokens":15,' \
            b'"prompt_tokens_details":{"cached_tokens":3}}}\n\ndata: [DONE]\n\n'
    event, sent = _passthrough([pad, final[:40], final[40:]])
    assert sent == pad + final  # поток ретранслируется как есть
    assert (event["prompt_tokens"], event["completion_tokens"], event["cached_tokens"], event["total_tokens"]) == (11, 4, 3, 15)
    assert event["stream_chunks"] == 3 and event["response_bytes"] == len(sent)
    assert _Handler._req_tail == b""  # хвост живёт на экземпляре, класс не загрязняется


def test_passthrough_json_usage_and_missing_usage():
    body = json.dumps({"id": "x", "choices": [{"message": {"content": "y" * 9000}}],
                       "usage": {"input_tokens": 5, "output_tokens": 0, "cache_read_input_tokens": 2}}).encode()
    event, _ = _passthrough([body])
    assert (event["prompt_tokens"], event["completion_tokens"], event["cached_tokens"], event["total_tokens"]) == (5, 0, 2, 5)
    event, _ = _passthrough([b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'])
    assert [event[k] for k in ("prompt_tokens", "completion_tokens", "cached_tokens", "total_tokens")] == [None] * 4


@pytest.mark.parametrize(("tail", "expected"), [
    (b'"usage": null, "usage": {"prompt_tokens": 1, "completion_tokens": 2}', {"input_tokens": 1, "output_tokens": 2}),
    (b'{"usage":{"input_tokens":7}} {"usage":{"output_tokens":9}}', {"input_tokens": 7, "output_tokens": 9}),
    (b'"usage": {"prompt_tokens": 1, "compl', None),
    (b"no usage here", None),
    (b'"usage": [1, 2]', None),
    (b"", None),
])
def test_extract_usage_edge_cases(tail, expected):
    result = extract_usage(tail)
    assert result == expected
