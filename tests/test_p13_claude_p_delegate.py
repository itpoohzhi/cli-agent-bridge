"""Delegate tests for claude-p-bridge/server.py P1.3 log rotation (W04)."""
from __future__ import annotations

import importlib.util
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from core import log_rotation_adapters as adapters

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_claude_p() -> Any:
    spec = importlib.util.spec_from_file_location(
        "claude_p_server_p13_test",
        REPO_ROOT / "bridges/claude-p-bridge/server.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_claude_p_off_capsys_and_on_rotation_redaction_and_kill_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _load_claude_p()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    cfg = tmp_path / "claude_p_dyn.json"
    monkeypatch.setenv("CLAUDE_P_BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("CLAUDE_P_BRIDGE_LOG_ROTATION_MAX_BYTES", "80")
    monkeypatch.setenv("CLAUDE_P_BRIDGE_LOG_ROTATION_BACKUP_COUNT", "2")

    # 1) Default OFF -> writes to dynamic sys.stderr (capsys), creates 0 log files
    mod._log("off-message Bearer sk-secret-12345678901234567890")
    captured = capsys.readouterr()
    assert "off-message" in captured.err
    assert not (tmp_path / "logs" / "bridge.log").exists()

    # 2) ON via dynamic JSON -> rotates 0600, suppresses stderr, redacts secret
    cfg.write_text('{"CLAUDE_P_BRIDGE_LOG_ROTATION_ENABLED": true}\n', encoding="utf-8")
    for i in range(5):
        mod._log(f"on-msg-{i} Authorization: Bearer sk-secret-9999999999999999999999")
    assert capsys.readouterr().err == ""
    log0 = tmp_path / "logs" / "bridge.log"
    log1 = tmp_path / "logs" / "bridge.log.1"
    assert log0.exists() and log1.exists()
    assert stat.S_IMODE(os.stat(log0).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(log1).st_mode) == 0o600
    combined = log0.read_text(encoding="utf-8") + log1.read_text(encoding="utf-8")
    assert "sk-secret-9999999999999999999999" not in combined

    # 3) Instant kill-switch via dynamic JSON false -> closes FDs and resumes stderr
    cfg.write_text('{"CLAUDE_P_BRIDGE_LOG_ROTATION_ENABLED": false}\n', encoding="utf-8")
    mod._log("after-killswitch")
    assert "after-killswitch" in capsys.readouterr().err
    assert adapters.get_rotation_snapshot("claude_p")["state"] == "CLOSED"

    # 4) Malformed JSON -> fail-closed even when env=1
    monkeypatch.setenv("CLAUDE_P_BRIDGE_LOG_ROTATION_ENABLED", "1")
    cfg.write_text("{corrupt", encoding="utf-8")
    mod._log("malformed-fail-closed")
    assert "malformed-fail-closed" in capsys.readouterr().err
