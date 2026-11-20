"""Tests for Muse and OpenCode Zen Zero-Canon runtimes and stdio drivers."""

from __future__ import annotations

import importlib.util
import json
import stat
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from adapters.stdio_drivers.muse_env import build_muse_env, build_muse_zero_canon_argv, build_muse_zero_canon_env
from adapters.stdio_drivers.opencode_driver import OpenCodeAcpDriver
from core.stdio_resident.zero_canon_router import zero_canon_isolation

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, rel_path: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / rel_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _seed_muse_home(root: Path) -> Path:
    home, cfg = root / "real_muse_home", root / "real_muse_home" / ".config" / "muse"
    cfg.mkdir(parents=True)
    (cfg / "auth.json").write_text('{"token": "muse-secret"}', encoding="utf-8")
    (cfg / "settings.json").write_text(json.dumps({
        "provider": "meta", "model": "muse-wonder-1.0", "proxy": "http://127.0.0.1:10816",
        "hooks": {"pre": ["echo evil"]}, "mcpServers": {"bad": {}},
    }), encoding="utf-8")
    (cfg / "AGENTS.md").write_text("# Muse AGENTS canon\n", encoding="utf-8")
    (home / "AGENTS.md").write_text("# Home AGENTS canon\n", encoding="utf-8")
    (cfg / "hooks").mkdir()
    (cfg / "hooks" / "hook.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    return home


def test_muse_kill_switch_defaults_false_and_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zc = _load_module("muse_zc_rt_test", "bridges/muse-bridge/muse_runtime/zero_canon_runtime.py")
    monkeypatch.delenv("MUSE_ZERO_CANON_ENABLED", raising=False)
    cfg = tmp_path / "dynamic_config.json"

    assert zc.is_muse_zero_canon_enabled(cfg) is False

    cfg.write_text('{"MUSE_ZERO_CANON_ENABLED": "true"}', encoding="utf-8")
    assert zc.is_muse_zero_canon_enabled(cfg) is False

    cfg.write_text("{broken json", encoding="utf-8")
    assert zc.is_muse_zero_canon_enabled(cfg) is False

    cfg.write_text('{"MUSE_ZERO_CANON_ENABLED": true}', encoding="utf-8")
    assert zc.is_muse_zero_canon_enabled(cfg) is True

    assert zc.is_muse_zero_canon_enabled(cfg, environ={"MUSE_ZERO_CANON_ENABLED": "0"}) is False
    assert zc.is_muse_zero_canon_enabled(tmp_path / "missing.json", environ={"MUSE_ZERO_CANON_ENABLED": "1"}) is True


def test_muse_zero_canon_runtime_isolates_home_cwd_and_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zc = _load_module("muse_zc_rt_iso", "bridges/muse-bridge/muse_runtime/zero_canon_runtime.py")
    monkeypatch.delenv("MUSE_ZERO_CANON_ENABLED", raising=False)
    real_home = _seed_muse_home(tmp_path)
    ws = tmp_path / "muse_ws"
    cfg = tmp_path / "dynamic_config.json"

    # Disabled flag -> standard launch (no --preset empty, original workdir)
    cfg.write_text('{"MUSE_ZERO_CANON_ENABLED": false}', encoding="utf-8")
    with zc.zero_canon_scope({"X-Review-Profile": "Zero-Canon"}, cfg, workspace=ws, real_home=real_home) as ctx:
        assert ctx is None
        cmd, env, cwd = zc.prepare_muse_launch(
            ["muse", "exec", "--workspace", str(ws), "--prompt-file", "/tmp/p.txt"],
            {"HOME": str(real_home), "META_API_KEY": "drop-me"},
            ws,
        )
        assert "--preset" not in cmd
        assert cwd == ws
        assert env["HOME"] == str(real_home)
        assert "META_API_KEY" not in env

    # Enabled flag + X-Review-Profile: Zero-Canon -> full isolation
    cfg.write_text('{"MUSE_ZERO_CANON_ENABLED": true}', encoding="utf-8")
    (ws / "muse-zc-cwd").mkdir(parents=True)
    (ws / "muse-zc-cwd" / "AGENTS.md").write_text("stale", encoding="utf-8")
    with zc.zero_canon_scope({"X-Review-Profile": "Zero-Canon"}, cfg, workspace=ws, real_home=real_home) as ctx:
        assert ctx is not None and ctx.enabled is True
        cmd, env, cwd = zc.prepare_muse_launch(
            ["muse", "exec", "--workspace", str(ws), "--prompt-file", "/tmp/p.txt"],
            {"HOME": str(real_home), "META_API_KEY": "drop-me"},
            ws,
        )
        assert "--preset" in cmd and cmd[cmd.index("--preset") + 1] == "empty"
        assert cmd[cmd.index("--workspace") + 1] == str(ctx.zc_cwd)
        assert cwd == ctx.zc_cwd
        assert list(cwd.iterdir()) == []
        assert env["HOME"] == str(ctx.zc_home)
        assert env["XDG_CONFIG_HOME"] == str(ctx.zc_home / ".config")
        assert env["BRIDGE_ZERO_CANON"] == "1"

        auth = ctx.zc_home / ".config" / "muse" / "auth.json"
        settings_path = ctx.zc_home / ".config" / "muse" / "settings.json"
        assert auth.is_file() and _mode(auth) == 0o600
        assert settings_path.is_file() and _mode(settings_path) == 0o600
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        assert settings == {"model": "muse-wonder-1.0", "provider": "meta", "proxy": "http://127.0.0.1:10816"}
        assert "hooks" not in settings and "mcpServers" not in settings
        assert not (ctx.zc_home / "AGENTS.md").exists()
        assert not (ctx.zc_home / ".config" / "muse" / "AGENTS.md").exists()
        assert not (ctx.zc_home / ".config" / "muse" / "hooks").exists()


def test_muse_stdio_env_zero_canon(tmp_path: Path) -> None:
    real_home = _seed_muse_home(tmp_path)
    zc_root = tmp_path / "muse_zc_slot"
    trusted = {"PATH": "/usr/bin:/bin", "HOME": str(real_home), "HTTP_PROXY": "http://127.0.0.1:10816"}

    env = build_muse_zero_canon_env(None, "/opt/bin/muse", str(zc_root), server_env=trusted)
    assert env["HOME"] == str((zc_root / "home").resolve())
    assert env["XDG_CONFIG_HOME"] == str((zc_root / "home").resolve() / ".config")
    assert env["BRIDGE_ZERO_CANON"] == "1"
    assert env["MUSE_BIN_PATH"] == "/opt/bin/muse"
    assert (zc_root / "cwd").is_dir() and list((zc_root / "cwd").iterdir()) == []
    auth = zc_root / "home" / ".config" / "muse" / "auth.json"
    settings_file = zc_root / "home" / ".config" / "muse" / "settings.json"
    assert _mode(auth) == 0o600 and _mode(settings_file) == 0o600
    assert "hooks" not in json.loads(settings_file.read_text(encoding="utf-8"))
    assert not (zc_root / "home" / ".config" / "muse" / "AGENTS.md").exists()

    env2 = build_muse_env(None, "/opt/bin/muse", server_env=trusted, zero_canon_home=str(tmp_path / "direct_zc"))
    assert env2["BRIDGE_ZERO_CANON"] == "1"
    assert build_muse_zero_canon_argv(["muse", "serve"]) == ["muse", "serve", "--preset", "empty"]
    assert build_muse_zero_canon_argv(["muse", "serve", "--preset", "empty"]) == ["muse", "serve", "--preset", "empty"]


def test_muse_bridge_server_facade_applies_zero_canon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "path", list(sys.path))
    server = _load_module("muse_zc_server_facade", "bridges/muse-bridge/server.py")
    wrapper = tmp_path / "muse-fake.sh"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    real_home = _seed_muse_home(tmp_path)
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text('{"MUSE_ZERO_CANON_ENABLED": true}', encoding="utf-8")
    monkeypatch.setattr(server, "MUSE_WRAPPER", str(wrapper))
    captured: dict[str, Any] = {}

    def fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["cmd"], captured["cwd"], captured["env"] = cmd, kwargs.get("cwd"), kwargs.get("env")
        raise OSError("stop-after-capture")

    monkeypatch.setattr(server.subprocess, "Popen", fake_popen)
    with server.zero_canon_scope({"X-Review-Profile": "Zero-Canon"}, cfg, workspace=tmp_path / "ws", real_home=real_home) as ctx:
        assert ctx is not None
        out = server.Run("muse-wonder-1.0", "hello", "high", tmp_path / "run_ws").execute()
        assert out["state"] == "spawn_failed"
        assert "--preset" in captured["cmd"] and captured["cmd"][captured["cmd"].index("--preset") + 1] == "empty"
        assert captured["cwd"] == str(ctx.zc_cwd)
        assert captured["env"]["HOME"] == str(ctx.zc_home)
        assert captured["env"]["BRIDGE_ZERO_CANON"] == "1"


def test_opencode_kill_switch_and_permission_ask_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zc = _load_module("oc_zc_rt_test", "bridges/opencode-zen-bridge/zen_bridge/adapters/zero_canon_runtime.py")
    monkeypatch.delenv("OPENCODE_ZERO_CANON_ENABLED", raising=False)
    cfg = tmp_path / "dynamic_config.json"
    assert zc.is_opencode_zero_canon_enabled(cfg) is False

    cfg.write_text('{"OPENCODE_ZERO_CANON_ENABLED": "yes"}', encoding="utf-8")
    assert zc.is_opencode_zero_canon_enabled(cfg) is False

    cfg.write_text('{"OPENCODE_ZERO_CANON_ENABLED": true}', encoding="utf-8")
    assert zc.is_opencode_zero_canon_enabled(cfg) is True

    real_home = tmp_path / "real_oc_home"
    (real_home / ".local" / "share" / "opencode").mkdir(parents=True)
    (real_home / ".local" / "share" / "opencode" / "auth.json").write_text('{"zen": "ok"}', encoding="utf-8")
    ws = tmp_path / "oc_ws"
    (ws / "opencode-zc-cwd").mkdir(parents=True)
    (ws / "opencode-zc-cwd" / "AGENTS.md").write_text("stale", encoding="utf-8")

    raw_env = {
        "HOME": str(real_home),
        "OPENCODE_CONFIG": "/etc/evil.json",
        "OPENCODE_CONFIG_CONTENT": json.dumps({
            "provider": {"opencode": {"options": {"baseURL": "http://127.0.0.1:10830/v1"}}},
            "mcp": {"bad": {}},
            "plugin": ["bad"],
            "instructions": ["AGENTS.md"],
            "permission": {"*": "deny"},
        }),
    }

    with zc.zero_canon_scope({"X-Review-Profile": "Zero-Canon"}, cfg, workspace=ws, real_home=real_home) as ctx:
        assert ctx is not None and ctx.enabled is True
        applied = zc.apply_zero_canon_env(raw_env)
        assert applied["HOME"] == str(ctx.zc_home)
        assert applied["XDG_CONFIG_HOME"] == str(ctx.zc_xdg_config)
        assert "OPENCODE_CONFIG" not in applied
        assert applied["BRIDGE_ZERO_CANON"] == "1"
        assert list(ctx.zc_cwd.iterdir()) == []
        auth = ctx.zc_home / ".local" / "share" / "opencode" / "auth.json"
        assert auth.is_file() and _mode(auth) == 0o600

        parsed_cfg = json.loads(applied["OPENCODE_CONFIG_CONTENT"])
        assert parsed_cfg["permission"] == {"*": "ask"}
        assert "provider" in parsed_cfg
        for denied in ("mcp", "plugin", "instructions"):
            assert denied not in parsed_cfg

        # Even if serve policy asks for "deny", Zero-Canon strictly keeps permission={"*": "ask"}
        serve_env = zc.apply_serve_zero_canon_env(raw_env, "{}", "deny")
        assert json.loads(serve_env["OPENCODE_CONFIG_CONTENT"])["permission"] == {"*": "ask"}


def test_opencode_zen_server_facade_and_spawn_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "path", list(sys.path))
    server = _load_module("zen_zc_server_facade", "bridges/opencode-zen-bridge/server.py")
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text('{"OPENCODE_ZERO_CANON_ENABLED": true}', encoding="utf-8")
    monkeypatch.setattr(server, "DYNAMIC_CONFIG_PATH", cfg)
    monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY", "deny")

    real_home = tmp_path / "home"
    real_home.mkdir()
    captured: dict[str, Any] = {}

    def fake_spawn(cmd: list[str], **kwargs: Any) -> Any:
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = kwargs.get("env")
        return MagicMock()

    monkeypatch.setattr("core.proc_groups.spawn_registered", fake_spawn)
    with server.zero_canon_scope(
        {"X-Review-Profile": "Zero-Canon"}, cfg, workspace=tmp_path / "ws", real_home=real_home
    ) as ctx:
        assert ctx is not None
        serve_env = server._serve_env("")
        assert json.loads(serve_env["OPENCODE_CONFIG_CONTENT"])["permission"] == {"*": "ask"}
        server.spawn_registered(["opencode", "run"], cwd=str(tmp_path), env={"HOME": str(real_home)})
        assert captured["cwd"] == str(ctx.zc_cwd)
        assert captured["env"]["HOME"] == str(ctx.zc_home)
        assert json.loads(captured["env"]["OPENCODE_CONFIG_CONTENT"])["permission"] == {"*": "ask"}


def test_opencode_acp_driver_zero_canon_isolation(tmp_path: Path) -> None:
    real_home = tmp_path / "oc_acp_home"
    (real_home / ".local" / "share" / "opencode").mkdir(parents=True)
    (real_home / ".local" / "share" / "opencode" / "auth.json").write_text('{"key": "v"}', encoding="utf-8")

    driver = OpenCodeAcpDriver()
    base_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(real_home),
        "OPENCODE_CONFIG": "/tmp/should-drop.json",
        "OPENCODE_CONFIG_CONTENT": json.dumps({
            "provider": {"opencode": {"options": {"baseURL": "http://127.0.0.1:10830/v1"}}},
            "mcp": {"srv": {}},
            "permission": {"*": "allow"},
        }),
    }
    with zero_canon_isolation(driver, "Zero-Canon") as iso:
        assert iso.active is True and iso.root is not None
        env = iso.env(base_env)
        assert env is not None
        assert env["HOME"] == iso.root
        assert env["XDG_CONFIG_HOME"] == str(Path(iso.root) / ".config")
        assert "OPENCODE_CONFIG" not in env
        assert env["BRIDGE_ZERO_CANON"] == "1"
        cfg = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        assert cfg["permission"] == {"*": "ask"}
        assert "mcp" not in cfg
        assert "provider" in cfg
        auth_copy = Path(iso.root) / ".local" / "share" / "opencode" / "auth.json"
        assert auth_copy.is_file() and _mode(auth_copy) == 0o600
        assert iso.argv(["opencode"], "m", "high") == ["opencode", "acp"]
