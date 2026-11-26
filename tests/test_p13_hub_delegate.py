"""Delegate tests for hub server.py P1.3 log rotation (W05)."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

import server as hub_server
from core import log_rotation_adapters as adapters


def test_hub_off_compat_on_rotation_redaction_and_dynamic_toggle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(hub_server, "ROOT", tmp_path)
    cfg = tmp_path / "hub_dynamic.json"
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("BRIDGE_LOG_ROTATION_MAX_BYTES", "90")
    monkeypatch.setenv("BRIDGE_LOG_ROTATION_BACKUP_COUNT", "2")

    # OFF default -> writes to capsys stderr, no logs/ created
    hub_server._log("hub-off-check")
    assert "hub-off-check" in capsys.readouterr().err
    assert not (tmp_path / "logs").exists()

    # ON via dynamic JSON -> rotates 0600/0700, suppresses stderr, redacts secret
    cfg.write_text('{"BRIDGE_LOG_ROTATION_ENABLED": true}\n', encoding="utf-8")
    for i in range(6):
        hub_server._log(f"hub-on-{i} Bearer sk-hubsecret-123456789012345678901234")
    assert capsys.readouterr().err == ""
    log0 = tmp_path / "logs" / "bridge.log"
    log1 = tmp_path / "logs" / "bridge.log.1"
    assert log0.exists() and log1.exists()
    assert stat.S_IMODE(os.stat(log0.parent).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(log0).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(log1).st_mode) == 0o600
    combined = log0.read_text(encoding="utf-8") + log1.read_text(encoding="utf-8")
    assert "sk-hubsecret-123456789012345678901234" not in combined

    # Non-bool JSON value fails closed even if ENV=1
    monkeypatch.setenv("BRIDGE_LOG_ROTATION_ENABLED", "1")
    cfg.write_text('{"BRIDGE_LOG_ROTATION_ENABLED": "true"}\n', encoding="utf-8")
    hub_server._log("hub-nonbool-fail-closed")
    assert "hub-nonbool-fail-closed" in capsys.readouterr().err
    assert adapters.get_rotation_snapshot("hub")["state"] == "CLOSED"
