"""Unit tests for core/usage_normalizer.py, core/telemetry_hooks.py, codex_usage.py (PR B2)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from core.stdio_resident.codex_usage import _has_positive_usage, extract_codex_legacy_usage, extract_codex_v2_usage
from core.telemetry_hooks import TelemetryHooksMixin, _resolve_subagent_role
from core.request_telemetry import RequestTelemetryStore
from core.telemetry_sql import COLUMNS, MIGRATION_COLUMNS, NAMES, make_row
from core.telemetry_usage import extract_usage
from core.turn_usage import UsageUpdate, normalize_usage_update
from core.usage_event_fields import finalize_event_usage
from core.usage_fields import enrich_turn_usage_dict, normalize_usage_fields, telemetry_usage_updates
from core.usage_normalizer import Usage, resolve_usage_presence


def test_b2_usage_normalizer_and_codex() -> None:
    assert (Usage(0, 0).usage_present, Usage(0, 0, cache_read_tokens=12).usage_present) == (False, True)
    assert (resolve_usage_presence(explicit=True, supplied_values=[0, 0]), resolve_usage_presence(explicit=None, supplied_values=[0, 64])) == (False, True)
    assert (_has_positive_usage(UsageUpdate(input_tokens=True, output_tokens=0)), _has_positive_usage(UsageUpdate(input_tokens=5, output_tokens=0))) == (False, True)
    v2_turn = extract_codex_v2_usage({"params": {"tokenUsage": {"last": {"inputTokens": 5, "outputTokens": 3}}}})
    v2_sess = extract_codex_v2_usage({"params": {"tokenUsage": {"total": {"inputTokens": 8, "outputTokens": 2}}}})
    v2_zero = extract_codex_v2_usage({"params": {"tokenUsage": {"last": {"inputTokens": 0}, "total": {"inputTokens": 0}}}})
    assert (extract_codex_v2_usage({}), extract_codex_legacy_usage({}), v2_turn is not None, v2_sess is not None, v2_zero is None) == (None, None, True, True, True)


def test_b2_codex_broken_and_telemetry_hooks() -> None:
    broken_empty = enrich_turn_usage_dict({"usage_missing_reason": "broken_stream"}, None)
    norm_pos = normalize_usage_update(UsageUpdate(input_tokens=10, output_tokens=5, source="codex_v2_turn"))
    assert (broken_empty["usage_present"], norm_pos.usage is not None) == (False, True)

    class _H(TelemetryHooksMixin):
        def __init__(self) -> None:
            self._req_meta: dict[str, object] = {"stream": False}

    h = _H()
    h._telemetry_usage(None)
    assert (h._req_meta["usage_present"], h._req_meta["usage_missing_reason"]) == (False, "usage_missing_in_stream")
    h._telemetry_usage({"prompt_tokens": 5})
    assert (h._req_meta["usage_present"], "usage_missing_reason" not in h._req_meta) == (True, True)
    h._telemetry_usage(None)
    assert (h._req_meta["usage_present"], h._req_meta["prompt_tokens"]) == (True, 5)
    h._req_meta = None  # type: ignore[assignment]
    h._telemetry_usage({"prompt_tokens": 5})
    assert h._req_meta is None


def test_b2_role_and_sql_schema() -> None:
    roles = (
        _resolve_subagent_role("Answer-Review", "other", "skeptic-1"),
        _resolve_subagent_role("answer-review-repair", None, "skeptic-1"),
        _resolve_subagent_role(None, "Answer-Review", "skeptic-1"),
        _resolve_subagent_role(None, None, "Skeptic-42"),
        _resolve_subagent_role("bad role!", None, None),
    )
    assert roles == ("answer-review", "answer-review-repair", "answer-review", "skeptic", None)
    assert (len(NAMES), NAMES[-5:], MIGRATION_COLUMNS) == (
        34,
        ("reasoning_tokens", "usage_present", "usage_source", "usage_missing_reason", "cache_creation_tokens"),
        (
            ("reasoning_tokens", "INTEGER"), ("usage_present", "BOOLEAN"), ("usage_source", "TEXT"),
            ("usage_missing_reason", "TEXT"), ("cache_creation_tokens", "INTEGER"),
        ),
    )
    row = make_row({"subagent_id": "skeptic-1", "subagent_role": "answer-review", "usage_present": False, "usage_source": None, "usage_missing_reason": "empty_zero_usage"})
    assert dict(zip(NAMES, row))["usage_missing_reason"] == "empty_zero_usage"


@pytest.mark.parametrize("key", ["cache_creation_tokens", "cache_creation_input_tokens", "cacheCreationTokens", "cacheWriteTokens"])
def test_cache_creation_tokens_pass_through_all_aliases(key: str) -> None:
    """Все 4 алиаса cache_creation доходят до normalize -> telemetry updates -> finalize_event_usage."""
    raw = {"input_tokens": 10, "output_tokens": 5, key: 200}
    assert normalize_usage_fields(raw)["cache_creation_tokens"] == 200
    updates = telemetry_usage_updates(raw)
    assert updates["cache_creation_tokens"] == 200
    assert finalize_event_usage(dict(updates))["cache_creation_tokens"] == 200
    absent = finalize_event_usage({"usage_present": False})
    assert absent["cache_creation_tokens"] is None and absent["usage_missing_reason"] == "omitted"


def test_claude_p_passthrough_tail_keeps_cache_creation() -> None:
    """Хвост passthrough claude-p (SSE с cache_creation_input_tokens) сохраняет cache_creation_tokens."""
    usage = {"input_tokens": 7, "output_tokens": 3, "cache_read_input_tokens": 50, "cache_creation_input_tokens": 200}
    tail = f"data: {json.dumps({'type': 'message_delta', 'usage': usage})}\n\n".encode()
    extracted = extract_usage(tail)
    assert extracted is not None
    assert extracted["cache_creation_tokens"] == 200
    assert extracted["input_tokens"] == 7 and extracted["cache_read_tokens"] == 50
    assert "cache_creation_tokens" not in (extract_usage(b'{"usage":{"input_tokens":1}}') or {})


def test_old_sqlite_db_migrates_cache_creation_tokens(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OPEN-06: реальная sqlite БД без cache_creation_tokens мигрирует, строка с 200 читается обратно."""
    monkeypatch.delenv("BRIDGE_TELEMETRY_ENABLED", raising=False)
    legacy_cols = COLUMNS[:-1]
    assert "cache_creation_tokens" not in dict(legacy_cols)
    base = str(tmp_path / "legacy.duckdb")
    con = sqlite3.connect(str(tmp_path / "legacy.sqlite3"))
    con.execute(f"CREATE TABLE bridge_requests ({', '.join(f'{n} {t}' for n, t in legacy_cols)})")
    con.execute(
        f"INSERT INTO bridge_requests VALUES ({', '.join('?' * len(legacy_cols))})",
        make_row({"request_id": "req_old", "status_code": 200})[: len(legacy_cols)],
    )
    con.commit()
    con.close()
    store = RequestTelemetryStore(db_path=base, force_sqlite=True, autostart=False, enabled=True, batch_size=16, flush_interval_ms=5)
    assert store.ensure_open() and store.engine == "sqlite3"
    event = {"request_id": "req_cc", "status_code": 200, "prompt_tokens": 10, "usage_present": True, "cache_creation_tokens": 200}
    assert store.record_request(event)
    store.flush()
    rows = {row["request_id"]: row for row in store.get_telemetry_payload()["recent_requests"]}
    assert rows["req_old"]["cache_creation_tokens"] is None
    assert rows["req_cc"]["cache_creation_tokens"] == 200
    assert store.get_telemetry_payload()["by_model"][0]["cache_creation_tokens"] == 200
    store.close()
