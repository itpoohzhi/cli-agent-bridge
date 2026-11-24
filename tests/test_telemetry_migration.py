"""Миграция схемы bridge_requests 29 -> 31 (reasoning_tokens, usage_present) и Fail-Open хук usage-лога."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from core.request_telemetry import RequestTelemetryStore
from core.telemetry_sql import (
    CLIENT_COLS,
    COLUMNS,
    DAY_COLS,
    MIGRATION_COLUMNS,
    MODEL_COLS,
    NAMES,
    ROLE_COLS,
    SUMMARY_COLS,
    make_row,
    make_usage_log_record,
)

try:  # DuckDB опционален: миграцию проверяем и на нём, если он установлен.
    import duckdb  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
except Exception:  # noqa: BLE001 - любой сбой импорта = миграция проверяется только на sqlite3
    duckdb = None

LEGACY_COLUMNS = COLUMNS[:-2]
LEGACY_SCHEMA = ", ".join(f"{name} {typ}" for name, typ in LEGACY_COLUMNS)
_LEGACY_INSERT = f"INSERT INTO bridge_requests VALUES ({', '.join('?' * len(LEGACY_COLUMNS))})"


def _legacy_row(request_id: str) -> tuple[Any, ...]:
    """Строка старого формата: первые 29 значений текущего make_row (порядок прежних колонок не менялся)."""
    return make_row({"request_id": request_id, "model": "gpt-4o-mini", "status_code": 200})[: len(LEGACY_COLUMNS)]


def _new_event() -> dict[str, Any]:
    """Событие нового формата: usage передан, reasoning_tokens=77, usage_present=True."""
    return {
        "request_id": "req_new", "model": "gpt-4o-mini", "backend_id": "agy", "status_code": 200,
        "stream": True, "prompt_tokens": 10, "completion_tokens": 20, "cached_tokens": 5,
        "reasoning_tokens": 77, "total_tokens": 30, "usage_present": True,
    }


def _store(base: str, *, force_sqlite: bool) -> RequestTelemetryStore:
    """Стор без фонового writer-потока: открытие и flush выполняются в тесте явно (детерминированно)."""
    return RequestTelemetryStore(
        db_path=base, force_sqlite=force_sqlite, autostart=False, enabled=True, batch_size=16, flush_interval_ms=5
    )


def _recent_by_id(store: RequestTelemetryStore) -> dict[str, Mapping[str, Any]]:
    """request_id -> строка recent_requests из публичного снимка стора."""
    return {row["request_id"]: row for row in store.get_telemetry_payload()["recent_requests"]}


def _check_migrated(store: RequestTelemetryStore) -> None:
    """Миграция состоялась: legacy-строка с NULL в новых колонках, новая строка читается без ошибок."""
    store.flush()
    rows = _recent_by_id(store)
    assert set(rows) == {"req_legacy", "req_new"}
    assert rows["req_legacy"]["reasoning_tokens"] is None
    assert rows["req_legacy"]["usage_present"] is None
    assert rows["req_new"]["reasoning_tokens"] == 77
    assert bool(rows["req_new"]["usage_present"]) is True
    assert store.get_telemetry_payload()["summary"]["reasoning_tokens"] == 77


def test_schema_contract() -> None:
    """Схема 31 колонка: новые строго в конце, прежние 29 не тронуты, разрезы дополнены аддитивно."""
    assert len(NAMES) == 31
    assert NAMES[-2:] == ("reasoning_tokens", "usage_present")
    assert NAMES[:-2] == tuple(name for name, _ in LEGACY_COLUMNS)
    assert MIGRATION_COLUMNS == (("reasoning_tokens", "INTEGER"), ("usage_present", "BOOLEAN"))
    assert "reasoning_tokens" not in LEGACY_SCHEMA
    for cols in (SUMMARY_COLS, MODEL_COLS, CLIENT_COLS):
        assert "reasoning_tokens" in cols
    assert ROLE_COLS == DAY_COLS


def test_sqlite_migration_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Стор поверх legacy 29-колоночной sqlite3-БД: миграция проходит, повторное открытие не падает."""
    monkeypatch.delenv("BRIDGE_TELEMETRY_ENABLED", raising=False)
    base = str(tmp_path / "legacy.duckdb")
    con = sqlite3.connect(str(tmp_path / "legacy.sqlite3"))
    con.execute(f"CREATE TABLE bridge_requests ({LEGACY_SCHEMA})")
    con.execute(_LEGACY_INSERT, _legacy_row("req_legacy"))
    con.commit()
    con.close()
    store = _store(base, force_sqlite=True)
    assert store.ensure_open() and store.engine == "sqlite3"
    assert store.record_request(_new_event())
    _check_migrated(store)
    store.close()
    reopened = _store(base, force_sqlite=True)  # повторная миграция идемпотентна
    assert reopened.ensure_open()
    assert len(_recent_by_id(reopened)) == 2
    reopened.close()


@pytest.mark.skipif(duckdb is None, reason="duckdb не установлен")
def test_duckdb_migration_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """То же для duckdb: ADD COLUMN IF NOT EXISTS поверх legacy-файла, повторное открытие не падает."""
    monkeypatch.delenv("BRIDGE_TELEMETRY_ENABLED", raising=False)
    base = str(tmp_path / "legacy.duckdb")
    con = duckdb.connect(base)
    con.execute(f"CREATE TABLE bridge_requests ({LEGACY_SCHEMA})")
    con.execute(_LEGACY_INSERT, _legacy_row("req_legacy"))
    con.close()
    store = _store(base, force_sqlite=False)
    assert store.ensure_open() and store.engine == "duckdb"
    assert store.record_request(_new_event())
    _check_migrated(store)
    store.close()
    reopened = _store(base, force_sqlite=False)  # повторная миграция идемпотентна
    assert reopened.ensure_open()
    assert len(_recent_by_id(reopened)) == 2
    reopened.close()


def test_make_row_preserves_usage_and_redacts() -> None:
    """make_row сохраняет reasoning_tokens/usage_present и редактирует секреты в строковых полях."""
    event = {**_new_event(), "user_agent": "cli Bearer sk-abcd123456 token=supersecret"}
    data = dict(zip(NAMES, make_row(event)))
    assert data["reasoning_tokens"] == 77
    assert data["usage_present"] is True
    assert "[REDACTED]" in data["user_agent"]
    assert "sk-abcd" not in data["user_agent"]
    assert "supersecret" not in data["user_agent"]


def test_make_row_usage_absent_and_false() -> None:
    """Без usage новые колонки NULL; явный usage_present=False остаётся False (провайдер без usage)."""
    absent = dict(zip(NAMES, make_row({"request_id": "r1", "status_code": 200})))
    assert absent["reasoning_tokens"] is None
    assert absent["usage_present"] is None
    explicit = dict(zip(NAMES, make_row({"request_id": "r2", "usage_present": False})))
    assert explicit["usage_present"] is False


def test_make_usage_log_record_fields() -> None:
    """JSONL-запись usage-лога: ровно 16 полей из санитизированной строки, без повторной regex-редакции."""
    record = make_usage_log_record(dict(zip(NAMES, make_row(_new_event()))))
    assert len(record) == 16
    assert record["request_id"] == "req_new"
    assert record["model"] == "gpt-4o-mini"
    assert record["reasoning_tokens"] == 77
    assert record["usage_present"] is True
    assert record["total_tokens"] == 30


class _BoomUsageLog:
    """Фейковый ротационный usage-лог: методы бросают — стор обязан это пережить (Fail-Open)."""

    def write_rows(self, _batch: list[tuple], _names: tuple[str, ...]) -> None:
        raise RuntimeError("usage log write failed")

    def status_snapshot(self) -> dict[str, Any]:
        return {"enabled": True, "rotations": 0}

    def close(self) -> None:
        raise RuntimeError("usage log close failed")


def test_usage_log_hook_fail_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Хук usage-лога: без модуля {"enabled": False}; ломающийся лог не роняет запись в БД и close."""
    monkeypatch.delenv("BRIDGE_TELEMETRY_ENABLED", raising=False)
    store = _store(str(tmp_path / "fresh.duckdb"), force_sqlite=True)
    assert store.usage_log_status()["enabled"] is False
    assert store.ensure_open()
    store._usage_log = _BoomUsageLog()
    assert store.record_request(_new_event())
    assert store.flush() == 1
    assert len(_recent_by_id(store)) == 1
    assert store.usage_log_status() == {"enabled": True, "rotations": 0}
    store.close()  # close() лога бросает — close стора не падает
    assert store.usage_log_status() == {"enabled": False}
