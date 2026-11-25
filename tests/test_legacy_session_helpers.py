"""Unit-тесты для bridges/agy-bridge/agy_runtime/legacy_session_helpers.py."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

import json
import math
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_AGY_DIR = str(_ROOT / "bridges/agy-bridge")
if _AGY_DIR not in sys.path:
    sys.path.append(_AGY_DIR)

from agy_runtime.legacy_session_helpers import (  # noqa: E402
    LegacyLoadSpec,
    atomic_write_sessions_json,
    load_sessions_json_entries,
    normalize_request_cwd,
    session_entry_from_json,
    session_key_from_json,
    session_key_to_json,
    session_key_valid,
    validate_clean_cid,
)

_CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
_FP_VALID = "a" * 64


def _not_expired(entry: dict[str, Any], now: float) -> bool:
    return (now - float(entry["last_used"])) > 600.0


def test_session_key_valid_and_json_roundtrip() -> None:
    key4_abs = ("chat-1", "gemini", "/tmp/work/../proj", "high")
    assert session_key_valid(key4_abs) is True
    raw4 = session_key_to_json(key4_abs)
    assert raw4 == ["chat-1", "gemini", "/tmp/work/../proj", "high"]
    assert session_key_from_json(raw4) == ("chat-1", "gemini", "/tmp/proj", "high")

    key4_empty_cwd = ("chat-1", "gemini", "   ", "high")
    assert session_key_from_json(session_key_to_json(key4_empty_cwd)) == ("chat-1", "gemini", "", "high")

    key3 = ("gemini", "/tmp//sub", "medium")
    assert session_key_valid(key3) is True
    assert session_key_from_json(session_key_to_json(key3)) == ("gemini", "/tmp/sub", "medium")


def test_session_key_rejects_invalid_shapes() -> None:
    assert session_key_valid(("a", "b")) is False
    assert session_key_valid(("  ", "m", "/tmp", "high")) is False
    assert session_key_valid(("m", "  ", "high")) is False

    bad_inputs: list[object] = [
        "not-a-list",
        ["only", "two"],
        ["1", "2", "3", "4", "5"],
        ["chat", 123, "/tmp", "high"],
        ["  ", "gemini", "/tmp", "high"],
        ["chat", "gemini", "relative/path", "high"],
        ["gemini", "   ", "high"],
        ["gemini", "rel/dir", "high"],
    ]
    for raw in bad_inputs:
        assert session_key_from_json(raw) is None


def test_session_entry_from_json_valid_corrupt_and_expired() -> None:
    valid_raw: dict[str, object] = {
        "cid": "abcd1234-5678", "created": 100, "last_used": 150.5, "turns": 3, "tools_fp": _FP_VALID,
    }
    entry = session_entry_from_json(valid_raw, 200.0, _CID_RE, _not_expired)
    assert entry == {
        "cid": "abcd1234-5678", "created": 100.0, "last_used": 150.5, "turns": 3, "tools_fp": _FP_VALID,
    }
    no_fp = dict(valid_raw)
    del no_fp["tools_fp"]
    res_no_fp = session_entry_from_json(no_fp, 200.0, _CID_RE, _not_expired)
    assert res_no_fp is not None and res_no_fp["tools_fp"] == ""

    assert session_entry_from_json(valid_raw, 900.0, _CID_RE, _not_expired) is None

    bad_items: list[object] = [
        ["not-dict"],
        {**valid_raw, "cid": "bad!"},
        {**valid_raw, "created": True},
        {**valid_raw, "last_used": math.nan},
        {**valid_raw, "last_used": math.inf},
        {**valid_raw, "turns": -1},
        {**valid_raw, "turns": True},
        {**valid_raw, "tools_fp": "xyz"},
        {**valid_raw, "tools_fp": 123},
    ]
    for bad in bad_items:
        assert session_entry_from_json(bad, 200.0, _CID_RE, _not_expired) is None


def test_atomic_write_and_load_sessions_json_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "state" / "sessions.json"
    logs: list[str] = []
    key_ok = ("chat-1", "gemini", "/tmp/work", "high")
    key_expired = ("chat-2", "gemini", "/tmp/old", "low")
    snapshot: dict[tuple[str, ...], dict[str, Any]] = {
        key_ok: {"cid": "11112222-3333", "created": 100.0, "last_used": 500.0, "turns": 2, "tools_fp": _FP_VALID},
        key_expired: {"cid": "44445555-6666", "created": 10.0, "last_used": 20.0, "turns": 1},
    }
    atomic_write_sessions_json(target, 1, snapshot, logs.append)
    assert logs == []
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700

    spec = LegacyLoadSpec(version=1, now=700.0, cid_re=_CID_RE, is_expired=_not_expired)
    restored = load_sessions_json_entries(target, spec, logs.append)
    assert logs == []
    assert list(restored.keys()) == [key_ok]
    assert restored[key_ok]["cid"] == "11112222-3333"

    wrong_ver = LegacyLoadSpec(version=2, now=700.0, cid_re=_CID_RE, is_expired=_not_expired)
    assert load_sessions_json_entries(target, wrong_ver, logs.append) == {}


def test_load_and_write_fail_open_on_corrupt_or_os_error(tmp_path: Path) -> None:
    logs: list[str] = []
    spec = LegacyLoadSpec(version=1, now=700.0, cid_re=_CID_RE, is_expired=_not_expired)

    missing = tmp_path / "missing.json"
    assert load_sessions_json_entries(missing, spec, logs.append) == {}
    assert logs == []

    corrupt = tmp_path / "corrupt.json"
    _ = corrupt.write_text("{not-json", encoding="utf-8")
    assert load_sessions_json_entries(corrupt, spec, logs.append) == {}
    assert len(logs) == 1 and "sessions-load-error" in logs[0]

    mixed = tmp_path / "mixed.json"
    _ = mixed.write_text(
        json.dumps({"version": 1, "sessions": ["bad-item", {"key": ["bad"], "cid": "11112222"}]}),
        encoding="utf-8",
    )
    assert load_sessions_json_entries(mixed, spec, logs.append) == {}

    blocker = tmp_path / "not-a-dir"
    _ = blocker.write_text("x", encoding="utf-8")
    logs.clear()
    atomic_write_sessions_json(blocker / "sessions.json", 1, {}, logs.append)
    assert len(logs) == 1 and "sessions-persist-error" in logs[0]
    assert not any(p.name.startswith(".sessions-") for p in tmp_path.iterdir())


def test_validate_clean_cid_variants() -> None:
    logs: list[str] = []
    assert validate_clean_cid(None, _CID_RE, logs.append) == ("", False)
    assert validate_clean_cid("   ", _CID_RE, logs.append) == ("", False)
    assert validate_clean_cid("  abcd-1234  ", _CID_RE, logs.append) == ("abcd-1234", False)
    assert logs == []

    assert validate_clean_cid("bad_cid!", _CID_RE, logs.append) == ("", True)
    assert "cid-malformed-rejected" in logs[-1]
    assert validate_clean_cid(42, _CID_RE, logs.append) == ("", True)
    assert "cid-nonstring-rejected type=int" in logs[-1]


def test_normalize_request_cwd_variants() -> None:
    logs: list[str] = []
    assert normalize_request_cwd(None, 4096, logs.append) == ("", False)
    assert normalize_request_cwd("   ", 4096, logs.append) == ("", False)
    assert normalize_request_cwd("  /tmp/a/../b  ", 4096, logs.append) == (os.path.normpath("/tmp/a/../b"), False)
    assert logs == []

    for bad_cwd in ("relative/dir", "/" * 25 + "tmp", "/tmp/bad\x00dir", "/tmp/bad\ndir", "/tmp/bad\x7fdir", "/tmp/bad\ud800dir"):
        cwd, invalid = normalize_request_cwd(bad_cwd, 20, logs.append)
        assert cwd == "" and invalid is True
        assert "cwd-invalid-rejected" in logs[-1]

    cwd_non, invalid_non = normalize_request_cwd(999, 4096, logs.append)
    assert cwd_non == "" and invalid_non is True
    assert "cwd-nonstring-rejected type=int" in logs[-1]
