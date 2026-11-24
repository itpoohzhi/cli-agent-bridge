"""W8: полнооконные кандидаты аномалий, флаг усечения и атомарность снимка телеметрии."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Mapping
from typing import Any

from core.telemetry_query import TelemetryReader
from core.telemetry_sql import COLUMNS, NAMES, SCHEMA, Quantile, make_row

BASE_CFG: dict[str, Any] = {
    "recent_limit": 5,
    "limit_max": 1000,
    "prompt_spike_ratio": 2.0,
    "prompt_spike_min_turn": 100000,
    "prompt_spike_min_day": 5000000,
    "anomaly_max_candidates": 10000,
    "window_min_h": 0.5,
    "window_max_h": 24.0,
}


class _SnapshotStore(TelemetryReader):
    """Минимальный reader поверх sqlite3 in-memory по общей схеме стора (без фоновой записи)."""

    def ensure_open(self) -> bool:
        with self._db_lock:
            if self._con is None:
                self._con = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
                self._con.create_aggregate("quantile_cont", 2, Quantile)
                self._con.execute(f"CREATE TABLE bridge_requests ({SCHEMA})")
                self._ready = True
            return bool(self._ready)

    def insert(self, event: Mapping[str, Any]) -> None:
        """Вставка события как writer стора — под общим db_lock (протокол стора)."""
        placeholders = ", ".join("?" for _ in COLUMNS)
        self.ensure_open()
        with self._db_lock:
            self._con.execute(
                f"INSERT INTO bridge_requests ({', '.join(NAMES)}) VALUES ({placeholders})", make_row(event))


def _event(request_id: str, prompt_tokens: int, ts: float) -> dict[str, Any]:
    """Событие хода: нормальный (малый prompt) или всплеск (большой prompt_tokens)."""
    return {
        "request_id": request_id,
        "ts_epoch": ts,
        "model": "claude-test",
        "backend_id": "be-1",
        "client_kind": "interactive",
        "stream": False,
        "status_code": 200,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": 16,
        "cached_tokens": 0,
        "total_tokens": prompt_tokens + 16,
        "usage_present": True,
    }


def _turn_anomalies(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Только походовые (turn) аномалии снимка."""
    return [a for a in payload["prompt_anomalies"] if a["scope"] == "turn"]


def test_turn_anomaly_beyond_recent_limit_is_detected() -> None:
    """AC-05/F-006: всплеск за пределами recent LIMIT 5 находится полнооконными кандидатами."""
    store = _SnapshotStore(":memory:", BASE_CFG)
    now = time.time()
    for i in range(20):
        store.insert(_event(f"norm-{i}", 1000, now - 60.0 * (i + 1)))
    store.insert(_event("old-spike", 250000, now - 3600.0))
    payload = store.get_telemetry_payload(24.0, limit=5)
    assert len(payload["recent_requests"]) == 5
    assert "old-spike" not in {row["request_id"] for row in payload["recent_requests"]}
    assert payload["anomalies_candidates_truncated"] is False
    assert "architecture_flow" in payload
    turns = _turn_anomalies(payload)
    assert [a["request_id"] for a in turns] == ["old-spike"]
    assert turns[0]["prompt_tokens"] == 250000
    assert turns[0]["baseline_tokens"] == 1000.0


def test_candidates_truncated_flag_when_cap_exceeded() -> None:
    """anomalies_candidates_truncated=True при числе кандидатов больше anomaly_max_candidates."""
    cfg = {**BASE_CFG, "anomaly_max_candidates": 3}
    store = _SnapshotStore(":memory:", cfg)
    now = time.time()
    for i in range(3):
        store.insert(_event(f"norm-{i}", 1000, now - 30.0 * (i + 1)))
    for i in range(5):
        store.insert(_event(f"spike-{i}", 120000 + i, now - 300.0 * (i + 1)))
    payload = store.get_telemetry_payload(24.0, limit=5)
    assert payload["anomalies_candidates_truncated"] is True


def test_snapshot_stays_atomic_under_parallel_inserts() -> None:
    """F-006/F-021: параллельная вставка не рассинхронизирует summary и prompt_anomalies."""
    store = _SnapshotStore(":memory:", BASE_CFG)
    now = time.time()
    for i in range(20):
        store.insert(_event(f"base-{i}", 1000, now - 20.0 * (i + 1)))
    spike_ids = [f"spike-{i}" for i in range(3)]
    done = threading.Event()

    def writer() -> None:
        for i in range(60):
            store.insert(_event(f"live-{i}", 1000, time.time()))
            if i in (15, 30, 45):
                store.insert(_event(spike_ids[i // 15 - 1], 250000, time.time()))
            time.sleep(0.002)
        done.set()

    thread = threading.Thread(target=writer)
    thread.start()
    seen = 0
    try:
        while not done.is_set():
            payload = store.get_telemetry_payload(24.0, limit=5)
            total = payload["summary"]["total_requests"]
            assert total >= seen
            seen = total
            anomaly_tokens = sum(a["prompt_tokens"] for a in _turn_anomalies(payload))
            assert anomaly_tokens <= payload["summary"]["prompt_tokens"]
    finally:
        thread.join()
    payload = store.get_telemetry_payload(24.0, limit=5)
    assert {a["request_id"] for a in _turn_anomalies(payload)} >= set(spike_ids)
    assert payload["summary"]["total_requests"] == 83


def test_architecture_flow_panel_vs_skeptic_and_modern_backends() -> None:
    """W9b: роли panel/skeptic с нормализацией, unknown -> other и все 4 новых backend_id в tier2."""
    from core.telemetry_flow import build_architecture_flow

    modern_backends = ("neuralwatt", "neuralwatt-flex", "opencode-go", "opencode-go-claude")
    by_backend = [
        {"backend_id": bid, "requests": i + 1, "total_tokens": (i + 1) * 100,
         "avg_total_ms": 15.0, "egress_proxy": ":10820 (xray SOCKS5)"}
        for i, bid in enumerate(modern_backends)
    ]
    callers = [
        {"subagent_role": "panel", "requests": 2, "user_agent": ""},
        {"subagent_role": " Panel ", "requests": 1, "user_agent": ""},
        {"subagent_role": "Skeptic", "requests": 4, "user_agent": ""},
        {"subagent_role": "unknown-caller", "requests": 5, "user_agent": "custom-client/1.0"},
    ]
    flow = build_architecture_flow(by_backend, callers, {"total_requests": 12})
    t1 = {str(n["id"]): n["requests"] for n in flow["tier1_entry_callers"]["nodes"]}
    assert t1["council-panel"] == 3
    assert t1["council-skeptic"] == 4
    assert t1["other"] == 5
    t2 = {str(n["id"]): n for n in flow["tier2_l7_bridges"]["nodes"]}
    assert t2["georouter-10830"]["requests"] == 10
    assert t2["georouter-10830"]["total_tokens"] == 1000
    assert t2["universal-9882"]["requests"] == 10
    assert set(modern_backends) <= set(t2["georouter-10830"]["backends"])
