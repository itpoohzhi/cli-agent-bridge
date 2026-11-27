"""L1 Zero-I/O tests for core/log_rotation_policy.py (Python 3.14 & 3.9.6 compatible)."""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from core.log_rotation_policy import (
    DEFAULT_BACKUP_COUNT,
    DEFAULT_MAX_BYTES,
    FSM_EVENTS,
    SERVICE_SPECS,
    WriterState,
    encode_log_line,
    format_transition_notice,
    parse_bounded_int,
    parse_dynamic_json_doc,
    parse_env_bool,
    plan_rollover_ops,
    resolve_flag,
    resolve_rotation_config,
    should_reopen,
    should_rollover,
    stat_signature,
    step_fsm,
    validate_stat,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_POLICY_IMPORTS = frozenset({"os", "pathlib", "io", "sys", "logging", "time", "stat", "fcntl", "threading", "tomllib"})


def test_policy_zero_io_imports_and_py39_compat() -> None:
    src = (REPO_ROOT / "core/log_rotation_policy.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    assert not (found & FORBIDDEN_POLICY_IMPORTS), f"Forbidden I/O imports: {found & FORBIDDEN_POLICY_IMPORTS}"
    proc = subprocess.run(
        ["/usr/bin/python3", "-c", f"import sys; sys.path.insert(0, {str(REPO_ROOT)!r}); import core.log_rotation_policy as p; assert len(p.SERVICE_SPECS)==4"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("raw,expected", [
    ("1", True), ("true", True), ("TRUE", True), (" yes ", True), ("On", True),
    ("0", False), ("false", False), ("no", False), ("off", False), ("", False), ("maybe", False), (None, False),
])
def test_parse_env_bool(raw: str | None, expected: bool) -> None:
    assert parse_env_bool(raw) is expected


def test_strict_flag_precedence_and_fail_closed_json() -> None:
    flag = "BRIDGE_LOG_ROTATION_ENABLED"
    assert resolve_flag(None, False, {}, flag) is False
    assert resolve_flag(None, False, {flag: "1"}, flag) is True
    assert resolve_flag({"OTHER": True}, False, {flag: "1"}, flag) is True
    assert resolve_flag({flag: False}, False, {flag: "1"}, flag) is False
    assert resolve_flag({flag: True}, False, {flag: "0"}, flag) is True
    # Fail-closed WITHOUT env fallback on corrupt or non-bool JSON
    assert resolve_flag(None, True, {flag: "1"}, flag) is False
    for bad in ("true", 1, 0, None, [], {}):
        assert resolve_flag({flag: bad}, False, {flag: "1"}, flag) is False
    assert parse_dynamic_json_doc(None) == (None, False)
    assert parse_dynamic_json_doc("{broken") == (None, True)
    assert parse_dynamic_json_doc("[1, 2]") == (None, True)
    assert parse_dynamic_json_doc('{"a": true}') == ({"a": True}, False)


def test_resolve_rotation_config_and_bounds() -> None:
    spec = SERVICE_SPECS["zen"]
    cfg_default = resolve_rotation_config(spec, (None, False), {}, "/tmp/r", "/tmp/zen/custom.log")
    assert cfg_default.enabled is False
    assert cfg_default.max_bytes == DEFAULT_MAX_BYTES
    assert cfg_default.backup_count == DEFAULT_BACKUP_COUNT
    assert cfg_default.log_path == "/tmp/zen/custom.log"

    doc = {
        "OPENCODE_ZEN_BRIDGE_LOG_ROTATION_ENABLED": True,
        "OPENCODE_ZEN_BRIDGE_LOG_ROTATION_MAX_BYTES": 1024,
        "OPENCODE_ZEN_BRIDGE_LOG_ROTATION_BACKUP_COUNT": 0,
        "OPENCODE_ZEN_BRIDGE_LOG_ROTATION_PATH": "/tmp/override/bridge.log",
    }
    cfg_on = resolve_rotation_config(spec, (doc, False), {}, "/tmp/r", "/tmp/zen/custom.log")
    assert cfg_on.enabled is True
    assert cfg_on.max_bytes == 1024
    assert cfg_on.backup_count == 0
    assert cfg_on.log_path == "/tmp/override/bridge.log"
    assert parse_bounded_int(True, 5, 0) == 5
    assert parse_bounded_int(-1, 5, 0) == 5
    assert parse_bounded_int(0, 10, 1) == 10


def test_predicates_fsm_40_cells_and_notices() -> None:
    assert stat_signature(1, 2, 3, 4, 5) == (1, 2, 3, 4, 5)
    assert validate_stat(True, 501, 1, 501) is None
    assert validate_stat(False, 501, 1, 501) == "not_regular_file"
    assert validate_stat(True, 0, 1, 501) == "foreign_uid"
    assert validate_stat(True, 501, 2, 501) == "hardlink_detected"
    assert should_reopen((1, 10), (1, 10), True) is False
    assert should_reopen((1, 10), (1, 11), True) is True
    assert should_reopen((1, 10), None, False) is True
    assert should_rollover(0, 500, 100) is False  # oversized single line on empty file allowed once
    assert should_rollover(10, 91, 100) is True
    assert should_rollover(10, 90, 100) is False
    assert plan_rollover_ops("bridge.log", 0) == ()
    assert plan_rollover_ops("bridge.log", 3) == (
        ("bridge.log.2", "bridge.log.3"),
        ("bridge.log.1", "bridge.log.2"),
        ("bridge.log", "bridge.log.1"),
    )
    assert encode_log_line("привет\n") == "привет\n".encode("utf-8")
    assert len(list(WriterState)) * len(FSM_EVENTS) == 40
    for st in WriterState:
        for ev in FSM_EVENTS:
            nxt, action = step_fsm(st, ev)
            assert isinstance(nxt, WriterState) and isinstance(action, str) and action
    assert format_transition_notice(WriterState.OPEN, WriterState.DEGRADED_FAIL_OPEN, "hub", "ENOSPC") is not None
    assert format_transition_notice(WriterState.DEGRADED_FAIL_OPEN, WriterState.DEGRADED_FAIL_OPEN, "hub", "ENOSPC") is None
    assert format_transition_notice(WriterState.DEGRADED_FAIL_OPEN, WriterState.OPEN, "hub", "dropped=3") is not None
    assert format_transition_notice(WriterState.OPEN, WriterState.OPEN, "hub", "ok") is None
