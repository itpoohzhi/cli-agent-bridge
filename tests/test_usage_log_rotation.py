"""Тесты ротации, allowlist-редакции и fail-open поведения core/usage_log.py."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from core.telemetry_sql import NAMES, make_row
from core.usage_log import (
    USAGE_LOG_FIELDS,
    create_usage_log_writer,
    row_to_usage_record,
)


def _sample_event(**overrides: Any) -> dict[str, Any]:
    """Формирует типовое событие телеметрии для тестов JSONL-журнала."""
    event: dict[str, Any] = {
        "request_id": "req-001",
        "ts_epoch": 1_760_000_000.0,
        "model": "gpt-5",
        "subagent_id": "coder-1",
        "subagent_role": "coder",
        "route_mode": "passthrough",
        "backend_id": "agy",
        "stream": True,
        "status_code": 200,
        "total_ms": 123.456,
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "cached_tokens": 20,
        "reasoning_tokens": 10,
        "usage_present": True,
    }
    event.update(overrides)
    return event


def test_disabled_by_default_performs_no_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """При выключенном флаге BRIDGE_USAGE_LOG_ENABLED файлы и каталоги не создаются."""
    monkeypatch.setenv(
        "BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "missing_dynamic.json")
    )
    monkeypatch.delenv("BRIDGE_USAGE_LOG_ENABLED", raising=False)
    log_dir = tmp_path / "telemetry"
    log_path = log_dir / "usage.jsonl"

    writer = create_usage_log_writer({"usage_log_path": str(log_path)})
    written = writer.write_rows([_sample_event()])
    snap = writer.status_snapshot()

    assert written == 0
    assert snap["enabled"] is False
    assert snap["written"] == 0
    assert not log_path.exists()
    assert not log_dir.exists()


def test_enabled_creates_secure_permissions_and_redacts_secrets(
    tmp_path: Path,
) -> None:
    """Проверяет права 0o700/0o600, 16 allowlist-полей и редакцию секретов."""
    log_dir = tmp_path / "telemetry"
    log_path = log_dir / "usage.jsonl"
    writer = create_usage_log_writer(
        {"usage_log_enabled": True, "usage_log_path": str(log_path)}
    )
    dirty = _sample_event(
        request_id="req api_key=sk-secret99887766",
        model="gpt-5 Bearer my-super-secret-token",
        prompt="full user prompt must be dropped",
        headers={"Authorization": "Bearer header-secret"},
        secret="top-secret-value",
    )

    assert writer.write_rows([dirty]) == 1
    assert (log_dir.stat().st_mode & 0o777) == 0o700
    assert (log_path.stat().st_mode & 0o777) == 0o600

    raw_text = log_path.read_text(encoding="utf-8")
    record = json.loads(raw_text.splitlines()[0])

    assert tuple(record.keys()) == USAGE_LOG_FIELDS
    assert len(record) == 16
    assert record["route"] == "passthrough"
    assert record["http_status"] == 200
    assert record["elapsed_ms"] == 123.46
    assert "sk-secret99887766" not in raw_text
    assert "my-super-secret-token" not in raw_text
    assert "full user prompt must be dropped" not in raw_text
    assert "header-secret" not in raw_text
    assert "[REDACTED]" in record["request_id"]
    assert "[REDACTED]" in record["model"]


def test_tuple_rows_with_col_names_and_dynamic_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверяет преобразование кортежей make_row через col_names и GigaRC-флаг."""
    monkeypatch.setenv(
        "BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "missing_dynamic.json")
    )
    monkeypatch.setenv("BRIDGE_USAGE_LOG_ENABLED", "true")
    log_path = tmp_path / "usage.jsonl"
    writer = create_usage_log_writer({"usage_log_path": str(log_path)})

    row = make_row(_sample_event(total_ms=42.129))
    assert writer.write_rows([row], col_names=NAMES) == 1

    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert set(record.keys()) == set(USAGE_LOG_FIELDS)
    assert record["elapsed_ms"] == 42.13
    assert record["ts"].endswith("Z")
    assert row_to_usage_record({"ts_iso": "2026-01-01T00:00:00Z"})["ts"] == (
        "2026-01-01T00:00:00Z"
    )


def test_size_rotation_caps_backups(tmp_path: Path) -> None:
    """При превышении max_bytes сохраняются .1..3, файл .4 не создаётся."""
    log_path = tmp_path / "usage.jsonl"
    writer = create_usage_log_writer(
        {
            "usage_log_enabled": True,
            "usage_log_path": str(log_path),
            "usage_log_max_bytes": 400,
            "usage_log_backup_count": 3,
            "usage_log_rotate_daily": False,
        }
    )

    for idx in range(20):
        assert writer.write_rows([_sample_event(request_id=f"req-{idx:03d}")]) == 1

    snap = writer.status_snapshot()
    assert snap["written"] == 20
    assert snap["rotations"] >= 2
    assert log_path.exists()
    for suffix in (1, 2, 3):
        backup = tmp_path / f"usage.jsonl.{suffix}"
        assert backup.exists()
        assert (backup.stat().st_mode & 0o777) == 0o600
    assert not (tmp_path / "usage.jsonl.4").exists()


def test_daily_rotation_by_yesterday_mtime(tmp_path: Path) -> None:
    """Непустой файл со вчерашним UTC mtime ротируется в .1 при новой записи."""
    log_path = tmp_path / "usage.jsonl"
    writer = create_usage_log_writer(
        {
            "usage_log_enabled": True,
            "usage_log_path": str(log_path),
            "usage_log_max_bytes": 10_485_760,
            "usage_log_backup_count": 3,
            "usage_log_rotate_daily": True,
        }
    )

    assert writer.write_rows([_sample_event(request_id="req-yesterday")]) == 1
    yesterday = time.time() - 86_400 - 120
    os.utime(log_path, (yesterday, yesterday))

    assert writer.write_rows([_sample_event(request_id="req-today")]) == 1
    backup_1 = tmp_path / "usage.jsonl.1"
    assert backup_1.exists()
    assert "req-yesterday" in backup_1.read_text(encoding="utf-8")
    assert "req-today" in log_path.read_text(encoding="utf-8")
    assert "req-yesterday" not in log_path.read_text(encoding="utf-8")
    assert writer.status_snapshot()["rotations"] >= 1


def test_retention_prune_removes_expired_archives(tmp_path: Path) -> None:
    """Архивы старше retention_days удаляются, а свежие сохраняются."""
    log_path = tmp_path / "usage.jsonl"
    fresh_archive = tmp_path / "usage.jsonl.1"
    stale_archive = tmp_path / "usage.jsonl.2"
    fresh_archive.write_text('{"request_id":"fresh"}\n', encoding="utf-8")
    stale_archive.write_text('{"request_id":"stale"}\n', encoding="utf-8")
    now = time.time()
    os.utime(fresh_archive, (now - 86_400, now - 86_400))
    os.utime(stale_archive, (now - 20 * 86_400, now - 20 * 86_400))

    writer = create_usage_log_writer(
        {
            "usage_log_enabled": True,
            "usage_log_path": str(log_path),
            "usage_log_retention_days": 14,
            "usage_log_backup_count": 5,
        }
    )
    assert writer.write_rows([_sample_event()]) == 1

    assert fresh_archive.exists()
    assert not stale_archive.exists()
    assert writer.status_snapshot()["pruned_files"] >= 1


def test_fail_open_on_unwritable_path_and_snapshot_copy(tmp_path: Path) -> None:
    """Ошибка записи не бросает исключение наружу и увеличивает usage_log_errors."""
    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("blocker", encoding="utf-8")
    writer = create_usage_log_writer(
        {
            "usage_log_enabled": True,
            "usage_log_path": str(blocking_file / "usage.jsonl"),
        }
    )

    assert writer.write_rows([_sample_event()]) == 0
    snap = writer.status_snapshot()
    assert snap["usage_log_errors"] == 1
    assert snap["written"] == 0

    snap["usage_log_errors"] = 999
    assert writer.status_snapshot()["usage_log_errors"] == 1
    writer.close()
