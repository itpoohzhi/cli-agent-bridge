"""Контракт /v1/telemetry (RW-006..RW-008): канонические имена + UI-алиасы, топология и usage passthrough."""

from __future__ import annotations

import io
import json
import sys
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
