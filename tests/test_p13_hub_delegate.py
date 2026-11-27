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


def test_f012_pending_adopt_survives_archive_unsafe_and_f001_nul_path_rejected(tmp_path: Path) -> None:
    from core import userspace_log_rotation as ulr
    from core.log_rotation_policy import SERVICE_SPECS, RotationConfig, resolve_rotation_config

    # F-001: NUL or trailing-slash PATH falls back to default safely
    cfg_nul = resolve_rotation_config(SERVICE_SPECS["hub"], ({"BRIDGE_LOG_ROTATION_PATH": "/tmp/bad\x00log"}, False), {}, str(tmp_path))
    assert "\x00" not in cfg_nul.log_path and cfg_nul.log_path.endswith("logs/bridge.log")

    # F-012: 0644 active + symlink .1 -> first write degrades after fchmod, removing .1 MUST still roll over onto fresh 0600 inode
    d = tmp_path / "f012" / "logs"
    d.mkdir(parents=True)
    log_p = d / "bridge.log"
    log_p.write_text("legacy\n", encoding="utf-8")
    os.chmod(log_p, 0o644)
    old_inode = os.stat(log_p).st_ino
    old_reader = open(log_p, "r", encoding="utf-8")
    try:
        old_reader.read()
        victim = tmp_path / "v.txt"
        victim.write_text("SAFE", encoding="utf-8")
        os.symlink(victim, d / "bridge.log.1")
        w = ulr.PrivateWatchedRotatingWriter("hub")
        cfg = RotationConfig(True, str(log_p), max_bytes=4096, backup_count=2)
        assert w.write_bytes(cfg, b"blocked-by-symlink\n") is False
        assert stat.S_IMODE(os.stat(log_p).st_mode) == 0o600
        (d / "bridge.log.1").unlink()
        assert w.write_bytes(cfg, b"after-recovery-new-inode\n") is True
        assert os.stat(log_p).st_ino != old_inode
        assert old_reader.read() == ""
        assert (d / "bridge.log.1").exists() and stat.S_IMODE(os.stat(d / "bridge.log.1").st_mode) == 0o600
        w.close()
    finally:
        old_reader.close()


def test_f001_concurrent_on_off_on_keeps_singleton_writer_and_zero_fd_leak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    cfg = tmp_path / "dyn.json"
    cfg.write_text('{"BRIDGE_LOG_ROTATION_ENABLED": true}\n', encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    entered = threading.Event()
    release = threading.Event()

    def slow_redact(text: str) -> str:
        entered.set()
        release.wait(timeout=2.0)
        return text

    t = threading.Thread(target=adapters.emit_service_log, args=("hub", "in-flight", tmp_path, slow_redact))
    t.start()
    assert entered.wait(timeout=2.0)
    w_before = adapters._WRITERS["hub"]
    cfg.write_text('{"BRIDGE_LOG_ROTATION_ENABLED": false}\n', encoding="utf-8")
    adapters.emit_service_log("hub", "off-during-redact", tmp_path)
    cfg.write_text('{"BRIDGE_LOG_ROTATION_ENABLED": true}\n', encoding="utf-8")
    adapters.emit_service_log("hub", "on-again", tmp_path)
    assert adapters._WRITERS["hub"] is w_before  # zero split-brain!
    release.set()
    t.join(timeout=2.0)
    cfg.write_text('{"BRIDGE_LOG_ROTATION_ENABLED": false}\n', encoding="utf-8")
    adapters.emit_service_log("hub", "final-off", tmp_path)
    assert not w_before.is_active() and w_before._dir_fd == -1 and w_before._file_fd == -1
