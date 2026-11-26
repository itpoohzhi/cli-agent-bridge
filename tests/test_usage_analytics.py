"""Юнит- и интеграционные тесты для pure analytics и расширения /v1/telemetry."""

from __future__ import annotations

import ast
import time
from pathlib import Path
from typing import Any

import pytest

from core.request_telemetry import RequestTelemetryStore
from core.usage_analytics import (
    AnomalyThresholds,
    aggregate_records,
    compute_cache_hit_pct,
    detect_prompt_anomalies,
    enrich_with_cache_hit,
)

_LEGACY_KEYS: frozenset[str] = frozenset({
    "architecture_flow",
    "by_backend",
    "by_client",
    "by_hour",
    "by_model",
    "db_path",
    "dropped_events",
    "enabled",
    "engine",
    "generated_at",
    "prune_errors",
    "queue_size",
    "recent_requests",
    "summary",
    "window_hours",
})


def test_compute_cache_hit_pct_and_enrich() -> None:
    """Проверка расчёта cache_hit_pct: 0 при пустом prompt, точный процент и clamp [0, 100]."""
    assert compute_cache_hit_pct(0, 0) == 0.0
    assert compute_cache_hit_pct(None, None) == 0.0
    assert compute_cache_hit_pct(50, 0) == 0.0
    assert compute_cache_hit_pct(50, 100) == 50.0
    assert compute_cache_hit_pct(1, 3) == 33.33
    assert compute_cache_hit_pct(250, 100) == 100.0
    assert compute_cache_hit_pct(-10, 100) == 0.0

    rows = [{"model": "m1", "prompt_tokens": 200, "cached_tokens": 50}]
    enriched = enrich_with_cache_hit(rows)
    assert enriched == [{"model": "m1", "prompt_tokens": 200, "cached_tokens": 50, "cache_hit_pct": 25.0}]
    assert "cache_hit_pct" not in rows[0]


def test_aggregate_records_dimensions() -> None:
    """Агрегация по summary, by_model, by_role (пустая -> interactive), by_day и reasoning_tokens."""
    records: list[dict[str, Any]] = [
        {
            "ts_iso": "2026-11-22T10:00:00Z",
            "model": "gpt-5",
            "backend_id": "codex",
            "subagent_role": "",
            "status_code": 200,
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "cached_tokens": 500,
            "reasoning_tokens": 120,
            "total_tokens": 1200,
            "usage_present": True,
        },
        {
            "ts_iso": "2026-11-21T09:00:00Z",
            "model": "claude-sonnet",
            "backend_id": "claude-p",
            "subagent_role": "coder",
            "subagent_id": "coder-1",
            "status_code": 502,
            "prompt_tokens": 400,
            "completion_tokens": 100,
            "cached_tokens": 100,
            "reasoning_tokens": 30,
            "total_tokens": 500,
            "usage_present": False,
        },
    ]
    res = aggregate_records(records)
    summary = res["summary"]
    assert summary["total_requests"] == 2
    assert summary["ok_requests"] == 1
    assert summary["error_requests"] == 1
    assert summary["usage_present_requests"] == 1
    assert summary["prompt_tokens"] == 1400
    assert summary["reasoning_tokens"] == 150
    assert summary["cache_hit_pct"] == 42.86

    assert [d["day"] for d in res["by_day"]] == ["2026-11-21", "2026-11-22"]
    assert res["by_day"][1]["cache_hit_pct"] == 50.0
    assert res["by_role"][0]["subagent_role"] == "interactive"
    assert res["by_role"][1]["subagent_role"] == "coder"
    assert len(res["by_model"]) == 2
    assert res["prompt_anomalies"] == []


def test_detect_prompt_anomalies_low_traffic_vs_spikes() -> None:
    """Низкий трафик не даёт ложных тревог; всплески >=2x и >=min_threshold триггерят алерты."""
    low_days = [
        {"day": "2026-11-20", "prompt_tokens": 1000},
        {"day": "2026-11-21", "prompt_tokens": 50000},
    ]
    low_turns = [
        {"request_id": "r1", "model": "m1", "subagent_role": "coder", "prompt_tokens": 1000},
        {"request_id": "r2", "model": "m1", "subagent_role": "coder", "prompt_tokens": 1200},
        {"request_id": "r3", "model": "m1", "subagent_role": "coder", "prompt_tokens": 50000},
    ]
    assert detect_prompt_anomalies(low_days, low_turns) == []

    th = AnomalyThresholds(ratio_threshold=2.0, min_turn_prompt_tokens=100000, min_day_prompt_tokens=5000000)
    spike_days = [
        {"day": "2026-11-20", "prompt_tokens": 1000000},
        {"day": "2026-11-21", "prompt_tokens": 1200000},
        {"day": "2026-11-22", "prompt_tokens": 6000000},
    ]
    spike_turns = [
        {"request_id": "t1", "model": "m1", "subagent_role": "coder", "prompt_tokens": 20000},
        {"request_id": "t2", "model": "m1", "subagent_role": "coder", "prompt_tokens": 25000},
        {"request_id": "t3", "model": "m1", "subagent_role": "coder", "prompt_tokens": 22000},
        {"request_id": "t4", "model": "m1", "subagent_role": "coder", "subagent_id": "coder-7", "prompt_tokens": 250000},
    ]
    alerts = detect_prompt_anomalies(spike_days, spike_turns, th)
    assert len(alerts) == 2
    assert alerts[0]["scope"] == "day"
    assert alerts[0]["key"] == "2026-11-22"
    assert alerts[0]["reason"] == "day_prompt_spike"
    assert alerts[1]["scope"] == "turn"
    assert alerts[1]["key"] == "m1:coder"
    assert alerts[1]["request_id"] == "t4"
    assert alerts[1]["subagent_id"] == "coder-7"
    assert alerts[1]["reason"] == "turn_prompt_spike"


def test_telemetry_payload_preserves_legacy_and_adds_analytics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_telemetry_payload сохраняет все 15 legacy-ключей и добавляет новые разрезы usage."""
    monkeypatch.setenv("BRIDGE_TELEMETRY_ENABLED", "1")
    store = RequestTelemetryStore(str(tmp_path / "telemetry.duckdb"), force_sqlite=True, autostart=False, enabled=True)
    now = time.time()
    try:
        assert store.record_request({
            "request_id": "req-1",
            "ts_epoch": now - 60.0,
            "model": "gpt-5",
            "backend_id": "codex",
            "subagent_role": "reviewer",
            "subagent_id": "reviewer-1",
            "status_code": 200,
            "prompt_tokens": 1000,
            "completion_tokens": 250,
            "cached_tokens": 400,
            "reasoning_tokens": 80,
            "total_tokens": 1250,
            "usage_present": True,
            "total_ms": 420.0,
        })
        assert store.flush() == 1
        payload = store.get_telemetry_payload(window_hours=24.0, limit=50)
    finally:
        store.close()

    assert _LEGACY_KEYS.issubset(payload.keys())
    assert {"by_day", "by_role", "prompt_anomalies", "usage_log"}.issubset(payload.keys())
    assert payload["summary"]["cache_hit_pct"] == 40.0
    assert payload["summary"]["reasoning_tokens"] == 80
    assert payload["by_model"][0]["cache_hit_pct"] == 40.0
    assert len(payload["by_day"]) == 1
    assert payload["by_day"][0]["cache_hit_pct"] == 40.0
    assert len(payload["by_role"]) == 1
    assert payload["by_role"][0]["subagent_role"] == "reviewer"
    assert payload["by_role"][0]["cache_hit_pct"] == 40.0
    assert isinstance(payload["prompt_anomalies"], list)
    assert isinstance(payload["usage_log"], dict)
    assert "enabled" in payload["usage_log"]


def test_usage_analytics_is_pure_module() -> None:
    """core/usage_analytics.py не обращается к os.environ и не имеет module-level mutable коллекций."""
    src_path = Path(__file__).resolve().parent.parent / "core" / "usage_analytics.py"
    source = src_path.read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "getenv" not in source

    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            assert not isinstance(node.value, (ast.Dict, ast.List, ast.Set))


def test_cache_creation_tokens_aggregation_and_legacy_records() -> None:
    """cache_creation_tokens суммируется во всех разрезах; старые записи (нет поля/None/мусор) дают 0."""
    records: list[dict[str, Any]] = [
        {"ts": "2026-11-20T10:00:00Z", "model": "m", "backend_id": "b", "route": "r1", "subagent_role": "coder",
         "prompt_tokens": 100, "cached_tokens": 40, "cache_creation_tokens": 10, "usage_present": True},
        {"ts": "2026-11-20T11:00:00Z", "model": "m", "backend_id": "b", "route": "r1", "subagent_role": "coder",
         "prompt_tokens": 100, "cached_tokens": 10, "cache_creation_tokens": None, "usage_present": True},
        {"ts": "2026-11-21T11:00:00Z", "model": "m2", "backend_id": "b2", "route_mode": "r2",
         "prompt_tokens": 50, "cached_tokens": 0, "cache_creation_tokens": "oops", "usage_present": True},
        {"ts": "2026-11-21T12:00:00Z", "model": "m2", "backend_id": "b2", "prompt_tokens": 50, "usage_present": True},
    ]
    report = aggregate_records(records)
    summary = report["summary"]
    assert summary["cache_creation_tokens"] == 10
    assert summary["cache_hit_pct"] == round(100.0 * 50 / 300, 2)
    assert 0.0 <= summary["cache_hit_pct"] <= 100.0
    assert {r["model"]: r["cache_creation_tokens"] for r in report["by_model"]} == {"m": 10, "m2": 0}
    assert {r["subagent_role"]: r["cache_creation_tokens"] for r in report["by_role"]} == {"coder": 10, "interactive": 0}
    assert {r["day"]: r["cache_creation_tokens"] for r in report["by_day"]} == {"2026-11-20": 10, "2026-11-21": 0}
    assert {r["route"]: r["cache_creation_tokens"] for r in report["by_route"]} == {"r1": 10, "r2": 0, "": 0}


def test_usage_missing_reasons_summary() -> None:
    """usage_missing_reasons считает только записи без usage с непустой причиной."""
    records: list[dict[str, Any]] = [
        {"usage_present": False, "usage_missing_reason": "no_usage"},
        {"usage_present": False, "usage_missing_reason": "no_usage"},
        {"usage_present": False, "usage_missing_reason": " parse_error "},
        {"usage_present": False, "usage_missing_reason": ""},
        {"usage_present": True, "usage_missing_reason": "ignored"},
    ]
    assert aggregate_records(records)["summary"]["usage_missing_reasons"] == {"no_usage": 2, "parse_error": 1}
    assert aggregate_records([])["summary"]["usage_missing_reasons"] == {}
