"""Рантайм стора телеметрии (RW-002..RW-005): ленивое открытие, kill-switch, O(1) горячий путь, устойчивость writer."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent
for _p in (str(_TESTS), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import core.request_telemetry as rt  # noqa: E402
from core import defaults, runtime_env  # noqa: E402
from core.request_telemetry import RequestTelemetryStore  # noqa: E402


@pytest.fixture(autouse=True)
def _no_dynamic_config(tmp_path, monkeypatch):
    """Флаг GigaRC читается из файла, которого нет: решают env и дефолт (false)."""
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent-dynamic-config.json"))
    monkeypatch.delenv("BRIDGE_TELEMETRY_ENABLED", raising=False)


def _unpinned(tmp_path, **cfg):
    return RequestTelemetryStore(str(tmp_path / "rt" / "t.duckdb"), force_sqlite=True, autostart=False, **cfg)


def test_default_is_disabled_and_lazy(tmp_path, telemetry_event):
    assert defaults.BRIDGE_TELEMETRY_ENABLED is False
    st = _unpinned(tmp_path)
    assert (st.enabled, st.record_request(telemetry_event()), st.flush()) == (False, False, 0)
    payload = st.get_telemetry_payload()
    assert (payload["enabled"], payload["engine"], st._thread, st._ready) == (False, "disabled", None, False)
    assert not (tmp_path / "rt").exists() and st.prune() is None


def test_import_server_has_no_side_effects(tmp_path):
    db = tmp_path / "import" / "t.duckdb"
    code = (
        "import json, sys, threading, os\n"
        f"sys.path.insert(0, {str(_ROOT)!r})\n"
        "import server\n"
        f"print(json.dumps([os.path.exists({str(db)!r}), os.path.exists({str(db.parent)!r}),"
        " [t.name for t in threading.enumerate()], server.REQUEST_TELEMETRY._ready]))\n"
    )
    env = {**os.environ, "BRIDGE_TELEMETRY_DB_PATH": str(db), "BRIDGE_TELEMETRY_ENABLED": "1"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120, check=True)
    file_exists, dir_exists, threads, ready = json.loads(out.stdout.strip().splitlines()[-1])
    assert (file_exists, dir_exists, ready) == (False, False, False)
    assert "bridge-telemetry-writer" not in threads


def test_runtime_kill_switch_without_restart(tmp_path, monkeypatch, telemetry_event):
    st = _unpinned(tmp_path)
    try:
        monkeypatch.setenv("BRIDGE_TELEMETRY_ENABLED", "1")
        assert st.record_request(telemetry_event(request_id="on-1")) is True and st.engine == "sqlite3"
        monkeypatch.setenv("BRIDGE_TELEMETRY_ENABLED", "0")
        assert st.record_request(telemetry_event(request_id="off")) is False
        assert st.get_telemetry_payload()["enabled"] is False
        monkeypatch.setenv("BRIDGE_TELEMETRY_ENABLED", "true")
        assert st.record_request(telemetry_event(request_id="on-2")) is True
        st.flush()
        assert {r["request_id"] for r in st._query("SELECT request_id FROM bridge_requests")} == {"on-1", "on-2"}
    finally:
        st.close()


def test_explicit_enabled_argument_and_env_kill_switch(tmp_path, monkeypatch, telemetry_event):
    pinned_on, pinned_off = _unpinned(tmp_path / "a", enabled=True), _unpinned(tmp_path / "b", enabled=False)
    try:
        assert pinned_on.record_request(telemetry_event()) is True
        monkeypatch.setenv("BRIDGE_TELEMETRY_ENABLED", "0")
        assert pinned_on.record_request(telemetry_event()) is False  # env=0 выключает и закреплённый стор
        monkeypatch.setenv("BRIDGE_TELEMETRY_ENABLED", "1")
        assert pinned_off.record_request(telemetry_event()) is False and not (tmp_path / "b").exists()
    finally:
        pinned_on.close()
        pinned_off.close()


def test_dynamic_config_file_flag_controls_unpinned_store(tmp_path, monkeypatch, telemetry_event):
    cfg = tmp_path / "dynamic.json"
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    st = _unpinned(tmp_path)
    try:
        cfg.write_text(json.dumps({"BRIDGE_TELEMETRY_ENABLED": True}), encoding="utf-8")
        assert st.record_request(telemetry_event()) is True
        cfg.write_text(json.dumps({"BRIDGE_TELEMETRY_ENABLED": False}), encoding="utf-8")
        assert st.record_request(telemetry_event()) is False
    finally:
        st.close()


def test_record_request_is_o1_without_regex_env_or_config_reads(
        tmp_path, telemetry_make_store, telemetry_event, monkeypatch):
    st = telemetry_make_store(queue_maxsize=20000, name="o1")
    env_reads, rows = [], []
    monkeypatch.setattr(rt, "make_row", lambda *a, **k: rows.append(a))
    monkeypatch.setattr(defaults, "get_env_int", lambda *a, **k: env_reads.append(a) or 160)
    try:
        event = telemetry_event(user_agent="Authorization: bearer " + "A" * 400)
        assert all(st.record_request(event) for _ in range(10000))
        assert (env_reads, rows) == ([], [])  # ни санитизации, ни чтения env на потоке запроса
        assert st._queue.qsize() == 10000
        st._queue.queue.clear()
    finally:
        st.close()
    cfg = tmp_path / "dynamic.json"
    cfg.write_text(json.dumps({"BRIDGE_TELEMETRY_ENABLED": True}), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    dyn, reads = RequestTelemetryStore(str(tmp_path / "o1-dyn" / "t.duckdb"), force_sqlite=True, autostart=False), []
    try:
        assert dyn.record_request(telemetry_event()) is True  # первый ход читает файл конфига один раз
        env_reads.clear()
        monkeypatch.setattr(runtime_env, "_load_snapshot", lambda path: reads.append(path) or {})
        assert all(dyn.record_request(telemetry_event()) for _ in range(100))
        assert (reads, env_reads) == ([], [])  # mtime_ns не менялся: файл конфига в горячем пути не читается
        dyn._queue.queue.clear()
    finally:
        dyn.close()


def test_rejected_events_are_counted_not_swallowed(telemetry_store, telemetry_event, monkeypatch):
    assert telemetry_store.record_request(123) is False  # не Mapping: учтено, без тихого pass
    assert telemetry_store.get_telemetry_payload()["dropped_events"] == 1

    def bad_row(*_a, **_k):
        raise ValueError("bad")

    monkeypatch.setattr(rt, "make_row", bad_row)
    assert telemetry_store.record_request(telemetry_event()) is True
    assert telemetry_store.flush() == 0
    assert telemetry_store.get_telemetry_payload()["dropped_events"] == 2


def test_busy_duckdb_falls_back_to_separate_sqlite_file(tmp_path, monkeypatch, telemetry_event):
    pytest.importorskip("duckdb")
    path = tmp_path / "busy" / "t.duckdb"
    first = RequestTelemetryStore(str(path), autostart=False, enabled=True)
    assert first.ensure_open() and first.engine == "duckdb"
    first.close()
    before = path.read_bytes()
    monkeypatch.setattr(rt, "duckdb", SimpleNamespace(connect=lambda *_a: (_ for _ in ()).throw(OSError("locked"))))
    second = RequestTelemetryStore(str(path), autostart=False, enabled=True)
    try:
        assert second.record_request(telemetry_event()) is True and second.engine == "sqlite3"
        assert second.db_path == str(path.with_suffix(".sqlite3")) and second.flush() == 1
    finally:
        second.close()
    assert path.read_bytes() == before  # .duckdb не передавался в sqlite3 и не изменён
    assert sqlite3.connect(str(path.with_suffix(".sqlite3"))).execute("SELECT COUNT(*) FROM bridge_requests").fetchone() == (1,)


def test_writer_survives_flush_errors_and_flushes_on_exit(telemetry_make_store, telemetry_event):
    st = telemetry_make_store(name="loop2")
    try:
        st.record_request(telemetry_event(request_id="a"))
        ticks, real_flush, calls = iter([False, False, True]), st.flush, []

        def flaky(max_batches=None):
            calls.append(max_batches)
            if len(calls) == 1:
                raise RuntimeError("db hiccup")
            return real_flush(max_batches)

        st.flush = flaky
        st._stop = SimpleNamespace(wait=lambda _t: next(ticks), set=lambda: None)
        st._writer_loop()
        assert calls[:2] == [defaults.BRIDGE_TELEMETRY_FLUSH_MAX_BATCHES] * 2 and calls[2] is None  # финальный flush без лимита
        assert st._stats["dropped_events"] == 1
        assert st._query("SELECT COUNT(*) AS n FROM bridge_requests")[0]["n"] == 1
    finally:
        st._stop = threading.Event()
        st.close()


def test_close_flushes_queue_and_is_idempotent(tmp_path, telemetry_event):
    st = RequestTelemetryStore(str(tmp_path / "cl" / "t.duckdb"), force_sqlite=True, autostart=True, enabled=True,
                               flush_interval_ms=60000)
    for i in range(5):
        assert st.record_request(telemetry_event(request_id=f"c{i}"))
    thread = st._thread
    st.close()
    st.close()
    assert thread is not None and not thread.is_alive() and st.record_request(telemetry_event()) is False
    assert sqlite3.connect(str(tmp_path / "cl" / "t.sqlite3")).execute("SELECT COUNT(*) FROM bridge_requests").fetchone() == (5,)


def test_flush_respects_max_batches(telemetry_make_store, telemetry_event):
    st = telemetry_make_store(batch_size=2, name="mb")
    try:
        for i in range(7):
            st.record_request(telemetry_event(request_id=f"m{i}"))
        assert (st.flush(max_batches=1), st._queue.qsize()) == (2, 5)
        assert (st.flush(max_batches=2), st._queue.qsize()) == (4, 1)
        assert (st.flush(), st._queue.qsize()) == (1, 0)
    finally:
        st.close()


def test_prune_runs_under_continuous_load_and_errors_are_counted(telemetry_make_store, telemetry_event, monkeypatch):
    st = telemetry_make_store(batch_size=2, flush_max_batches=1, prune_interval_s=60.0, prune_retry_s=5.0, name="pl")
    try:
        for i in range(20):
            st.record_request(telemetry_event(request_id=f"p{i}"))
        pruned = []
        real = st.prune
        st.prune = lambda: (pruned.append(1), real())[1]
        st._last_prune = time.monotonic() - 3600.0
        st._tick()
        assert pruned == [1] and st._queue.qsize() == 18  # prune не ждёт опустошения очереди
        monkeypatch.setattr(rt.time, "monotonic", lambda: 1000.0)
        st.prune = lambda: (_ for _ in ()).throw(RuntimeError("disk"))
        st._safe_prune()
        assert st._stats["prune_errors"] == 1
        monkeypatch.setattr(rt.time, "monotonic", lambda: 1004.0)
        assert st._prune_due() is False  # короче retry
        monkeypatch.setattr(rt.time, "monotonic", lambda: 1005.0)
        assert st._prune_due() is True  # повтор через prune_retry_s, не через полный интервал
        assert st.get_telemetry_payload()["prune_errors"] == 1
    finally:
        st.prune = real
        st.close()


def test_concurrent_writers_readers_and_close(telemetry_make_store, telemetry_event):
    st = telemetry_make_store(queue_maxsize=5000, name="race", autostart=True, flush_interval_ms=5)
    errors = []

    def produce(n):
        try:
            for i in range(200):
                st.record_request(telemetry_event(request_id=f"r{n}-{i}"))
        except Exception as err:  # noqa: BLE001
            errors.append(err)

    threads = [threading.Thread(target=produce, args=(n,)) for n in range(4)]
    [t.start() for t in threads]
    try:
        for _ in range(100):
            st.get_telemetry_payload()
        [t.join() for t in threads]
    finally:
        st.close()
    assert errors == [] and st.get_telemetry_payload()["enabled"] is False  # закрытый стор читается без исключений


def test_queue_maxsize_is_never_zero(telemetry_make_store):
    """Очередь с нулевым размером недопустима: нижняя граница — один элемент."""
    st = telemetry_make_store(queue_maxsize=0, name="zero")
    try:
        assert st._queue.maxsize == 1
    finally:
        st.close()


def test_open_is_idempotent_and_starts_single_writer(tmp_path):
    st = RequestTelemetryStore(str(tmp_path / "io" / "t.duckdb"), force_sqlite=True, autostart=True, enabled=True,
                               flush_interval_ms=60000)
    try:
        assert st.ensure_open() and st._opened is True
        thread = st._thread
        assert st.ensure_open() is True and st._thread is thread  # повторное обращение не переоткрывает стор
        assert sum(t.name == "bridge-telemetry-writer" for t in threading.enumerate()) == 1
    finally:
        st.close()


def test_tick_writes_queued_rows_without_waiting_for_empty_queue(telemetry_make_store, telemetry_event):
    st = telemetry_make_store(batch_size=2, flush_max_batches=1, name="tick")
    try:
        for i in range(5):
            st.record_request(telemetry_event(request_id=f"t{i}"))
        st._tick()
        assert st._query("SELECT COUNT(*) AS n FROM bridge_requests")[0]["n"] == 2 and st._queue.qsize() == 3
        st._tick()
        assert st._query("SELECT COUNT(*) AS n FROM bridge_requests")[0]["n"] == 4
    finally:
        st.close()


def test_window_is_clamped_and_nan_falls_back(telemetry_store):
    values = [telemetry_store._window(v) for v in (float("nan"), float("inf"), float("-inf"), -5, 1e12, "junk", None)]
    assert values == [24.0, 720.0, 0.1, 0.1, 720.0, 24.0, 24.0]
    assert [telemetry_store._limit(v) for v in (-1, 0, 10**9, "x", float("nan"))] == [1, 1, 500, 100, 100]
