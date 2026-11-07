"""Юнит-тесты телеметрии: стор DuckDB/sqlite3, атрибуция, редакция секретов, инварианты; фикстуры — `tests/conftest.py`."""

from __future__ import annotations

import ast
import json
import sys
import threading
import time
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent
for _p in (str(_TESTS), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import core.request_telemetry as rt  # noqa: E402
from core import defaults  # noqa: E402
from core.request_telemetry import COLUMNS, RequestTelemetryStore, build_architecture_flow, classify_caller, sanitize_scalar  # noqa: E402

MODULES = ("core/request_telemetry.py", "core/telemetry_flow.py", "core/telemetry_sql.py", "core/telemetry_hooks.py")
TEST_FILES = ("tests/test_request_telemetry.py", "tests/test_request_telemetry_http.py")
EXPECTED_COLUMNS = (
    "request_id ts_epoch ts_iso client_ip client_port user_agent subagent_id subagent_role client_kind "
    "auth_mode http_method endpoint model backend_id route_mode outbound_target egress_proxy stream "
    "status_code error_type queue_ms ttfb_ms total_ms stream_chunks prompt_tokens completion_tokens "
    "cached_tokens total_tokens response_bytes"
).split()


def test_schema_and_primary_engine(telemetry_store, tmp_path):
    assert [name for name, _ in COLUMNS] == EXPECTED_COLUMNS
    assert telemetry_store._query("SELECT * FROM bridge_requests") == []
    with telemetry_store._db_lock:
        assert [d[0] for d in telemetry_store._con.execute("SELECT * FROM bridge_requests").description] == EXPECTED_COLUMNS
    pytest.importorskip("duckdb")
    st = RequestTelemetryStore(str(tmp_path / "t" / "bridge_telemetry.duckdb"), autostart=False)
    try:
        assert st.engine == "duckdb" and (tmp_path / "t" / "bridge_telemetry.duckdb").exists()
        assert (tmp_path / "t").stat().st_mode & 0o777 == 0o700
    finally:
        st.close()


def test_payload_contract(telemetry_payload, telemetry_store):
    """Полный контракт снимка: summary, разрезы по модели/бэкенду/клиенту/часу, recent, архитектурный поток."""
    now, payload = telemetry_payload
    s = payload["summary"]
    assert (payload["enabled"], payload["engine"]) == (True, telemetry_store.engine)
    assert (payload["dropped_events"], payload["queue_size"]) == (0, 0)
    assert (s["total_requests"], s["ok_requests"], s["error_requests"], s["ok_rate_pct"]) == (4, 3, 1, 75.0)
    assert (s["stream_requests"], s["subagent_requests"], s["interactive_requests"]) == (1, 1, 3)
    assert (s["avg_total_ms"], s["max_total_ms"], s["p50_total_ms"], s["p95_total_ms"]) == (250.0, 400.0, 250.0, 385.0)
    assert (s["p50_ttfb_ms"], s["p99_ttfb_ms"], s["avg_queue_ms"]) == (25.0, 39.7, 1.0)
    assert (s["prompt_tokens"], s["completion_tokens"], s["cached_tokens"], s["total_tokens"]) == (40, 20, 8, 60)
    assert s["total_response_bytes"] == 2048
    by_model = {(r["model"], r["backend_id"]): r for r in payload["by_model"]}
    assert (by_model[("m-a", "agy")]["requests"], by_model[("m-a", "agy")]["error_requests"]) == (3, 1)
    assert by_model[("m-a", "agy")]["ok_rate_pct"] == round(200 / 3, 2)
    assert by_model[("m-b", "muse")]["p95_total_ms"] == 400.0
    assert payload["by_model"][0]["model"] == "m-a"  # сортировка по числу запросов
    by_backend = {r["backend_id"]: r for r in payload["by_backend"]}
    assert (by_backend["agy"]["egress_proxy"], by_backend["agy"]["requests"]) == (":10820 (xray SOCKS5)", 3)
    assert (by_backend["muse"]["outbound_target"], by_backend["muse"]["total_tokens"]) == (":9886", 15)
    clients = {(r["client_kind"], r["subagent_role"], r["subagent_id"]): r for r in payload["by_client"]}
    assert clients[("subagent", "coder", "coder-1")]["requests"] == 1
    assert clients[("interactive", "interactive", "")]["requests"] == 3
    assert clients[("interactive", "interactive", "")]["last_seen_ts"] >= now - 10
    assert sum(h["requests"] for h in payload["by_hour"]) == 4
    assert all(h["hour_bucket"].endswith(":00:00Z") for h in payload["by_hour"])
    recent = payload["recent_requests"]
    assert [r["request_id"] for r in recent] == ["d", "c", "b", "a"]  # новые первыми
    assert recent[0]["stream"] is True and recent[1]["error_type"] == "overloaded"
    assert "auth_mode" not in recent[0] and "client_port" not in recent[0]
    flow = payload["architecture_flow"]
    tier1 = {n["id"]: n["requests"] for n in flow["tier1_entry_callers"]["nodes"]}
    assert (flow["total_requests"], tier1["subagents"], tier1["other"]) == (4, 1, 3)
    tier2 = {n["id"]: n["requests"] for n in flow["tier2_l7_bridges"]["nodes"]}
    assert (tier2["universal-9882"], tier2["agy-9887"], tier2["muse-9886"], tier2["codex-2455"]) == (4, 3, 1, 0)
    tier3 = {n["id"]: n["requests"] for n in flow["tier3_l4_egress_proxies"]["nodes"]}
    assert (tier3["xray-10820"], flow["tier3_l4_egress_proxies"]["direct_requests"]) == (3, 1)


def test_window_and_limit_clamp_and_filtering(telemetry_store, telemetry_event):
    now = time.time()
    telemetry_store.record_request(telemetry_event(request_id="old", ts_epoch=now - 3 * 3600))
    telemetry_store.record_request(telemetry_event(request_id="new", ts_epoch=now - 60))
    telemetry_store.flush()
    assert telemetry_store.get_telemetry_payload(window_hours=1)["summary"]["total_requests"] == 1
    assert telemetry_store.get_telemetry_payload(window_hours=24)["summary"]["total_requests"] == 2
    assert telemetry_store.get_telemetry_payload(window_hours=-5)["window_hours"] == 0.1
    assert telemetry_store.get_telemetry_payload(window_hours=10**6)["window_hours"] == 720.0
    assert len(telemetry_store.get_telemetry_payload(limit=0)["recent_requests"]) == 1
    assert len(telemetry_store.get_telemetry_payload(limit=10**6)["recent_requests"]) == 2


def test_caller_attribution_and_storage(telemetry_store, telemetry_event):
    assert classify_caller({"X-Subagent-Id": "coder-1"}) == {
        "subagent_id": "coder-1", "subagent_role": "coder", "client_kind": "subagent",
    }
    assert (classify_caller("skeptic-r1")["subagent_role"], classify_caller("seat-1")["subagent_role"]) == ("skeptic", "seat")
    assert classify_caller("analyst-4")["subagent_role"] == "analyst"
    assert classify_caller({"x-subagent-id": "coder-1", "X-Subagent-Role": "Reviewer"})["subagent_role"] == "reviewer"
    assert classify_caller({}) == {"subagent_id": "", "subagent_role": "interactive", "client_kind": "interactive"}
    assert (classify_caller(None, None)["client_kind"], classify_caller("   ")["client_kind"]) == ("interactive", "interactive")
    telemetry_store.record_request(telemetry_event(subagent_id="coder-1"))
    telemetry_store.record_request(telemetry_event(request_id="req-2"))
    telemetry_store.flush()
    rows = {r["request_id"]: r for r in telemetry_store.get_telemetry_payload()["recent_requests"]}
    assert (rows["req-1"]["client_kind"], rows["req-1"]["subagent_role"]) == ("subagent", "coder")
    assert (rows["req-2"]["client_kind"], rows["req-2"]["subagent_role"]) == ("interactive", "interactive")


def test_queue_full_and_concurrent_producers(telemetry_make_store, telemetry_event):
    st = telemetry_make_store(queue_maxsize=2, name="queue")  # writer не запущен: очередь не освобождается
    try:
        started = time.perf_counter()
        results = [st.record_request(telemetry_event(request_id=f"r{i}")) for i in range(50)]
        elapsed = time.perf_counter() - started
        assert results[:2] == [True, True] and not any(results[2:])
        assert elapsed < 1.0  # ни одного ожидания на горячем пути
        payload = st.get_telemetry_payload()
        assert (payload["dropped_events"], payload["queue_size"]) == (48, 2)
        assert st.flush() == 2 and st.record_request(telemetry_event(request_id="after")) is True
    finally:
        st.close()
    wide = telemetry_make_store(queue_maxsize=1000, name="concurrent")

    def produce(n):
        for i in range(50):
            wide.record_request(telemetry_event(request_id=f"t{n}-{i}"))

    threads = [threading.Thread(target=produce, args=(n,)) for n in range(8)]
    try:
        for t in threads:
            t.start()
        wide.get_telemetry_payload()  # чтение параллельно записи не падает
        for t in threads:
            t.join()
        assert wide.flush() + 0 >= 0
        assert wide.get_telemetry_payload()["summary"]["total_requests"] == 400
    finally:
        wide.close()


def test_sanitize_scalar_redacts_secrets_and_keeps_scalars():
    secrets = ("secret123", "abcdef12345678", "xyz987", "abc.def-1", "t0k3n", "hunter2", "abcdefghij1234567890")
    for raw in ("Bearer secret123", "sk-abcdef12345678", "api_key=xyz987", "Authorization: Bearer abc.def-1",
                "token: t0k3n", "x password=hunter2 y", "ghp_abcdefghij1234567890"):
        cleaned = sanitize_scalar(raw)
        assert "[REDACTED]" in cleaned, raw
        assert not any(secret in cleaned for secret in secrets), raw
    assert sanitize_scalar("x" * 1000) == "x" * 160 and sanitize_scalar("abcdef", max_len=3) == "abc"
    assert sanitize_scalar(7) == 7 and sanitize_scalar(True) is True and sanitize_scalar(None) is None
    assert sanitize_scalar(float("nan")) is None
    assert sanitize_scalar({"messages": ["secret prompt"]}) is None
    assert sanitize_scalar(["a"]) is None and sanitize_scalar(b"raw") is None


def test_secrets_and_bodies_never_reach_storage(telemetry_store, telemetry_event):
    telemetry_store.record_request(
        telemetry_event(
            user_agent="agent Bearer secret123 sk-abcdef12345678",
            error_type="failed api_key=xyz987",
            messages=[{"role": "user", "content": "TOP-SECRET-PROMPT"}],
            headers={"Authorization": "Bearer secret123"},
            env={"SOME_VAR": "ENV-VALUE-MARKER-9"},
        )
    )
    telemetry_store.flush()
    dump = json.dumps(telemetry_store.get_telemetry_payload()) + json.dumps(telemetry_store._query("SELECT * FROM bridge_requests"))
    leaked = ("secret123", "sk-abcdef12345678", "xyz987", "TOP-SECRET-PROMPT", "ENV-VALUE-MARKER-9")
    assert not any(item in dump for item in leaked)
    assert "[REDACTED]" in dump


@pytest.mark.parametrize("mode", ["forced", "no_duckdb", "connect_fails"])
def test_sqlite_fallback_paths(tmp_path, monkeypatch, mode, telemetry_event):
    if mode == "no_duckdb":
        monkeypatch.setattr(rt, "duckdb", None)
    elif mode == "connect_fails":
        class Broken:
            @staticmethod
            def connect(*_a, **_k):
                raise RuntimeError("database is locked")

        monkeypatch.setattr(rt, "duckdb", Broken)
    st = RequestTelemetryStore(str(tmp_path / "t" / "bridge_telemetry.duckdb"), force_sqlite=mode == "forced", autostart=False)
    try:
        assert st.engine == "sqlite3" and st.db_path.endswith(".sqlite3") and Path(st.db_path).exists()
        st.record_request(telemetry_event())
        st.flush()
        assert st.get_telemetry_payload()["summary"]["total_requests"] == 1
    finally:
        st.close()


def test_configuration_and_degraded_store(tmp_path, monkeypatch, telemetry_event):
    monkeypatch.setenv("BRIDGE_TELEMETRY_BATCH_SIZE", "7")
    monkeypatch.setenv("BRIDGE_TELEMETRY_QUEUE_MAXSIZE", "11")
    monkeypatch.setenv("BRIDGE_TELEMETRY_RECENT_LIMIT", "3")
    monkeypatch.setenv("BRIDGE_TELEMETRY_DB_PATH", str(tmp_path / "env" / "t.duckdb"))
    st = RequestTelemetryStore(force_sqlite=True, autostart=False)
    try:
        assert (st._c["batch_size"], st._queue.maxsize, st.recent_limit) == (7, 11, 3)
        assert st.db_path == str(tmp_path / "env" / "t.sqlite3")
    finally:
        st.close()
    monkeypatch.setenv("BRIDGE_TELEMETRY_BATCH_SIZE", "junk")
    st = RequestTelemetryStore(str(tmp_path / "e2" / "t.duckdb"), force_sqlite=True, autostart=False)
    try:
        assert st._c["batch_size"] == defaults.BRIDGE_TELEMETRY_BATCH_SIZE == 100
    finally:
        st.close()
    monkeypatch.setenv("BRIDGE_TELEMETRY_ENABLED", "0")
    off = RequestTelemetryStore(str(tmp_path / "t" / "x.duckdb"))
    payload = off.get_telemetry_payload()
    assert off.record_request(telemetry_event()) is False and off.flush() == 0
    assert (payload["enabled"], payload["engine"], payload["summary"]["total_requests"]) == (False, "disabled", 0)
    assert payload["recent_requests"] == []
    assert all(key in payload for key in ("by_model", "by_backend", "by_client", "by_hour", "architecture_flow"))
    assert not (tmp_path / "t").exists()
    monkeypatch.delenv("BRIDGE_TELEMETRY_ENABLED")
    (tmp_path / "file").write_text("x")
    broken = RequestTelemetryStore(str(tmp_path / "file" / "sub" / "x.duckdb"), autostart=False)
    assert (broken.engine, broken.record_request(telemetry_event())) == ("disabled", False)
    assert broken.get_telemetry_payload()["enabled"] is False


def test_prune_and_background_writer(telemetry_make_store, telemetry_event):
    st = telemetry_make_store(retention_days=1, max_rows=3, name="prune")
    try:
        now = time.time()
        for i in range(6):
            st.record_request(telemetry_event(request_id=f"n{i}", ts_epoch=now - i))
        st.record_request(telemetry_event(request_id="stale", ts_epoch=now - 3 * 86400))
        st.flush()
        st.prune()
        ids = {r["request_id"] for r in st._query("SELECT request_id FROM bridge_requests")}
        assert "stale" not in ids and len(ids) <= 4 and {"n0", "n1", "n2"} <= ids
    finally:
        st.close()
    writer = telemetry_make_store(flush_interval_ms=20, batch_size=3, autostart=True, name="writer")  # фоновый writer
    try:
        for i in range(10):
            writer.record_request(telemetry_event(request_id=f"w{i}"))
        deadline = time.time() + 5
        while time.time() < deadline and writer.get_telemetry_payload()["summary"]["total_requests"] < 10:
            time.sleep(0.02)
        assert writer.get_telemetry_payload()["summary"]["total_requests"] == 10
    finally:
        writer.close()
        writer.close()  # идемпотентно


def test_architecture_flow_topology_shape():
    flow = build_architecture_flow([], [], {"total_requests": 0})
    assert list(flow)[1:] == ["tier1_entry_callers", "tier2_l7_bridges", "tier3_l4_egress_proxies"]
    assert {n["port"] for n in flow["tier2_l7_bridges"]["nodes"]} == {9882, 9881, 9883, 9887, 9886, 2455, 10830}
    assert {n["port"] for n in flow["tier3_l4_egress_proxies"]["nodes"]} == {10820, 10816, 10809}
    assert all(flow[tier]["description"] for tier in list(flow)[1:])


def test_module_size_invariants():
    """M-MOD-I1: файл <= 300 строк, функция <= 50 строк и <= 5 параметров; server.py — базовая линия 8746 строк."""
    for rel in (*MODULES, *TEST_FILES):
        src = (_ROOT / rel).read_text(encoding="utf-8")
        assert len(src.splitlines()) <= 300, (rel, len(src.splitlines()))
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                params = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs) + bool(args.vararg) + bool(args.kwarg)
                assert (node.end_lineno or 0) - node.lineno + 1 <= 50, (rel, node.name)
                assert params <= 5, (rel, node.name)
    assert len((_ROOT / "server.py").read_text(encoding="utf-8").splitlines()) <= 8746
