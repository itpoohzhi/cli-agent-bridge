"""End-to-end 4-service wiring, flag independence, ratchet, and Py 3.9.6 gate tests (W08)."""
from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from core import log_rotation_adapters as adapters
from core.bridge_io_config import BridgeIOConfig
from core.log_rotation_policy import SERVICE_SPECS, ServiceSpec

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_module(name: str, rel_path: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_agy_delegate_off_on_allowlist_and_strict_json_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _load_module("agy_server_p13_test", "bridges/agy-bridge/server.py")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    cfg = tmp_path / "dynamic_config.json"
    monkeypatch.setenv("AGY_BRIDGE_LOG_ROTATION_MAX_BYTES", "90")
    monkeypatch.setenv("AGY_BRIDGE_LOG_ROTATION_BACKUP_COUNT", "2")

    # OFF -> writes to dynamic sys.stderr
    mod._log("agy-off-event")
    assert "[agy-bridge]" in capsys.readouterr().err
    assert not (tmp_path / "logs").exists()

    # ON via dynamic JSON overrides env=0 (proving NOT inverted agy._new_flag!)
    monkeypatch.setenv("AGY_BRIDGE_LOG_ROTATION_ENABLED", "0")
    cfg.write_text('{"AGY_BRIDGE_LOG_ROTATION_ENABLED": true}\n', encoding="utf-8")
    safe_ev = next(iter(mod._LOG_EVENT_NAMES))
    for i in range(5):
        mod._log(f"ev={safe_ev} idx={i} Bearer sk-agysecret-123456789012345678901234")
    assert capsys.readouterr().err == ""
    log0 = tmp_path / "logs" / "bridge.log"
    log1 = tmp_path / "logs" / "bridge.log.1"
    assert log0.exists() and log1.exists()
    assert stat.S_IMODE(os.stat(log0).st_mode) == 0o600
    combined = log0.read_text(encoding="utf-8") + log1.read_text(encoding="utf-8")
    assert safe_ev in combined
    assert "sk-agysecret-123456789012345678901234" not in combined


def test_zen_delegate_off_dual_write_on_single_write_and_truncate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _load_module("zen_server_p13_test", "bridges/opencode-zen-bridge/server.py")
    zen_log = tmp_path / "logs" / "bridge.log"
    monkeypatch.setattr(mod, "_ZEN_ROOT", str(tmp_path))
    monkeypatch.setattr(mod, "LOG_PATH", zen_log)
    cfg = tmp_path / "dynamic_config.json"
    monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_LOG_ROTATION_MAX_BYTES", "80")
    monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_LOG_ROTATION_BACKUP_COUNT", "2")

    # OFF -> exact legacy dual-write (sys.stderr AND LOG_PATH)
    mod._log("zen-off-dual")
    assert "zen-off-dual" in capsys.readouterr().err
    assert "zen-off-dual" in zen_log.read_text(encoding="utf-8")

    # ON -> single write to rotated bridge.log, stderr suppressed, in-place truncate visible
    zen_log.unlink()
    cfg.write_text('{"OPENCODE_ZEN_BRIDGE_LOG_ROTATION_ENABLED": true}\n', encoding="utf-8")
    for i in range(5):
        mod._log(f"zen-on-single-{i} Bearer sk-zensecret-123456789012345678901234")
    assert capsys.readouterr().err == ""
    assert zen_log.exists() and (tmp_path / "logs" / "bridge.log.1").exists()
    assert stat.S_IMODE(os.stat(zen_log).st_mode) == 0o600
    combined = zen_log.read_text(encoding="utf-8") + (tmp_path / "logs" / "bridge.log.1").read_text(encoding="utf-8")
    assert "sk-zensecret-123456789012345678901234" not in combined
    os.truncate(zen_log, 0)
    mod._log("after-truncate")
    assert "after-truncate" in zen_log.read_text(encoding="utf-8")


def test_four_flags_independent_and_declarative_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BRIDGE_LOG_ROTATION_ENABLED", "1")
    adapters.emit_service_log("hub", "hub-only-on", tmp_path / "hub")
    adapters.emit_service_log("agy", "agy-stays-off", tmp_path / "agy")
    adapters.emit_service_log("claude_p", "cp-stays-off", tmp_path / "cp")
    adapters.emit_service_log("zen", "zen-stays-off", tmp_path / "zen")
    err = capsys.readouterr().err
    assert "hub-only-on" not in err
    assert "agy-stays-off" in err and "cp-stays-off" in err and "zen-stays-off" in err
    assert (tmp_path / "hub" / "logs" / "bridge.log").exists()
    for off_svc in ("agy", "cp", "zen"):
        assert not (tmp_path / off_svc / "logs" / "bridge.log").exists()
    # Declarative ServiceSpec extension works without modifying runtime
    monkeypatch.setitem(
        SERVICE_SPECS,
        "future_svc",
        ServiceSpec("future_svc", "FUTURE", "FUTURE_LOG_ROTATION_ENABLED", None, "dynamic_config.json"),
    )
    monkeypatch.setenv("FUTURE_LOG_ROTATION_ENABLED", "1")
    adapters.emit_service_log("future_svc", "future-line", tmp_path / "future")
    assert (tmp_path / "future" / "logs" / "bridge.log").exists()


def test_legacy_ratchet_zero_touch_and_py39_zen_gate() -> None:
    baselines = {
        "server.py": 7829,
        "bridges/agy-bridge/server.py": 8184,
        "bridges/claude-p-bridge/server.py": 1056,
        "bridges/opencode-zen-bridge/server.py": 8425,
        "tests/conftest.py": 340,
    }
    for rel, max_loc in baselines.items():
        actual = (REPO_ROOT / rel).read_bytes().count(10)
        assert actual <= max_loc, f"{rel} grew: {actual} > {max_loc}"
    assert BridgeIOConfig().admission_limit == 128
    # Zero-touch bridges/muse-bridge/*
    diff = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    changed = [ln.strip() for ln in diff.stdout.splitlines() if ln.strip()]
    assert not any(p.startswith("bridges/muse-bridge/") for p in changed), changed
    # Python 3.9.6 import check of all 3 P1.3 core modules
    proc = subprocess.run(
        ["/usr/bin/python3", "-c", f"import sys; sys.path.insert(0, {str(REPO_ROOT)!r}); import core.log_rotation_policy, core.userspace_log_rotation, core.log_rotation_adapters"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
