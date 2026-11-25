"""Unit-тесты чистого Standard `CODEX_HOME`, neutral CWD и guard-а ghost-usage (Wave 1)."""

from __future__ import annotations

import json
import os
import stat
import tomllib
from pathlib import Path
from typing import Any

import pytest

from core.stdio_resident import codex_std_home
from core.stdio_resident.codex_driver import CodexAppServerV2Driver
from core.stdio_resident.codex_protocol_fsm import ProtocolPhase, ProtocolState
from core.stdio_resident.codex_std_home import (
    CODEX_STD_CLEAN_HOME_FLAG,
    CODEX_STD_NEUTRAL_CWD_FLAG,
    CODEX_USAGE_FRAME_GUARD_FLAG,
    cleanup_stale_pid_homes,
    cleanup_std_home_dir,
    create_neutral_fallback_cwd,
    filter_codex_standard_config,
    is_codex_std_clean_home_enabled,
    is_codex_std_neutral_cwd_enabled,
    is_codex_usage_frame_guard_enabled,
    prepare_codex_std_home,
)

_HOST_CONFIG = """
model = "gpt-test"
notify = ["say", "done"]

[features]
hooks = true
web_search = true

[mcp_servers.host]
command = "host-mcp"

[plugins.p]
enabled = true

[hooks.pre]
command = "x"

[profiles.dev]
model = "gpt-dev"

[profiles.dev.mcp_servers.leak]
command = "leak"

[profiles.dev.hooks.post]
command = "y"
"""


def _source_home(tmp_path: Path) -> tuple[dict[str, str], Path]:
    src = tmp_path / "host" / ".codex"
    src.mkdir(parents=True)
    (src / "config.toml").write_text(_HOST_CONFIG, encoding="utf-8")
    (src / "auth.json").write_text('{"token":"t"}', encoding="utf-8")
    env = {
        "HOME": str(tmp_path / "host"),
        "CODEX_HOME": str(src),
        "BRIDGE_KEY": "secret",
        "BRIDGE_CODEX_STD_CLEAN_HOME_ENABLED": "true",
        "BRIDGE_DYNAMIC_CONFIG_PATH": str(tmp_path / "missing_dynamic_config.json"),
    }
    return env, src


def test_flags_default_to_false_and_follow_env(tmp_path: Path) -> None:
    env = {"BRIDGE_DYNAMIC_CONFIG_PATH": str(tmp_path / "none.json")}
    assert not is_codex_std_clean_home_enabled(env)
    assert not is_codex_std_neutral_cwd_enabled(env)
    assert not is_codex_usage_frame_guard_enabled(env)
    on = {**env, CODEX_STD_CLEAN_HOME_FLAG: "1", CODEX_STD_NEUTRAL_CWD_FLAG: "true", CODEX_USAGE_FRAME_GUARD_FLAG: "on"}
    assert is_codex_std_clean_home_enabled(on)
    assert is_codex_std_neutral_cwd_enabled(on)
    assert is_codex_usage_frame_guard_enabled(on)


def test_flag_off_build_env_is_parity(tmp_path: Path) -> None:
    env, _ = _source_home(tmp_path)
    env["BRIDGE_CODEX_STD_CLEAN_HOME_ENABLED"] = "false"
    assert CodexAppServerV2Driver().build_env(env) == env


def test_flag_on_builds_private_clean_home(tmp_path: Path) -> None:
    env, _ = _source_home(tmp_path)
    root = tmp_path / "slot"
    out = CodexAppServerV2Driver().build_env(env, str(root))
    codex_home = Path(out["CODEX_HOME"])
    assert codex_home == root / ".codex" and out["HOME"] == str(root)
    assert out["BRIDGE_CODEX_STD_CLEAN_HOME"] == "1" and "BRIDGE_KEY" not in out
    for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        assert out[name].startswith(str(root))
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE(codex_home.stat().st_mode) == 0o700
    cwd = root / "cwd"
    assert stat.S_IMODE(cwd.stat().st_mode) == 0o700 and not list(cwd.iterdir())
    assert stat.S_IMODE((codex_home / "auth.json").stat().st_mode) == 0o600
    assert (codex_home / "auth.json").read_text(encoding="utf-8") == '{"token":"t"}'
    cfg = tomllib.loads((codex_home / "config.toml").read_text(encoding="utf-8"))
    assert cfg["model"] == "gpt-test" and "project_doc_max_bytes" not in cfg
    for denied in ("mcp_servers", "plugins", "notify", "hooks"):
        assert denied not in cfg
    assert cfg["features"] == {"hooks": False, "web_search": True}
    assert cfg["profiles"]["dev"] == {"model": "gpt-dev"}


def test_filter_forces_hooks_off_without_features_and_rejects_non_mapping() -> None:
    assert filter_codex_standard_config({"model": "m"}) == {"model": "m", "features": {"hooks": False}}
    with pytest.raises(TypeError):
        filter_codex_standard_config([])  # type: ignore[arg-type]


@pytest.mark.parametrize("victim", ["auth.json", "config.toml"])
def test_symlinked_source_file_is_fail_closed(tmp_path: Path, victim: str) -> None:
    env, src = _source_home(tmp_path)
    target = tmp_path / "elsewhere"
    target.write_text("{}" if victim == "auth.json" else "", encoding="utf-8")
    (src / victim).unlink()
    (src / victim).symlink_to(target)
    with pytest.raises(OSError):
        prepare_codex_std_home(env, tmp_path / "slot")


def test_stale_pid_cleanup_keeps_live_and_symlinks(tmp_path: Path) -> None:
    base = tmp_path / "base"
    dead = base / "pid-999999-aaaa"
    live = base / f"pid-{os.getpid()}-bbbb"
    other = base / "unrelated"
    outside = tmp_path / "outside"
    for d in (dead, live, other, outside):
        d.mkdir(parents=True)
    (dead / "f").write_text("x", encoding="utf-8")
    link = base / "pid-999998-link"
    link.symlink_to(outside)
    cleanup_stale_pid_homes(base)
    assert not dead.exists() and live.is_dir() and other.is_dir()
    assert link.is_symlink() and outside.is_dir()


def test_cleanup_std_home_dir_removes_readonly_tree_and_not_symlink_target(tmp_path: Path) -> None:
    slot = tmp_path / "slot"
    (slot / "inner").mkdir(parents=True)
    (slot / "inner" / "f").write_text("x", encoding="utf-8")
    os.chmod(slot / "inner", 0o500)
    outside = tmp_path / "outside"
    outside.mkdir()
    (slot / "lnk").symlink_to(outside)
    cleanup_std_home_dir(slot)
    cleanup_std_home_dir(None)
    assert not slot.exists() and outside.is_dir()


def test_owned_home_and_neutral_cwd_are_private_and_registered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(codex_std_home.tempfile, "gettempdir", lambda: str(tmp_path))
    env, _ = _source_home(tmp_path)
    out = prepare_codex_std_home(env)
    home_root = Path(out["HOME"])
    cwd = Path(create_neutral_fallback_cwd())
    try:
        assert home_root.parent == cwd.parent == tmp_path / f"codex-std-homes-{os.getuid()}"
        assert home_root.name.startswith(f"pid-{os.getpid()}-")
        assert stat.S_IMODE(cwd.stat().st_mode) == 0o700 and not list(cwd.iterdir())
        assert home_root in codex_std_home._OWNED_DIRS and cwd in codex_std_home._OWNED_DIRS
    finally:
        cleanup_std_home_dir(home_root)
        cleanup_std_home_dir(cwd)
    assert not home_root.exists() and not cwd.exists()


def test_build_argv_keeps_repeated_config_flags() -> None:
    argv = CodexAppServerV2Driver().build_argv(["codex"], {"cli_args": ["-c", "model=a", "-c", "model=b"]})
    assert argv == ["codex", "app-server", "-c", "model=a", "-c", "model=b"]


def _ghost_frame(thread: str = "other", turn: str | None = None) -> str:
    params: dict[str, Any] = {
        "threadId": thread,
        "tokenUsage": {"last": {"inputTokens": 11, "outputTokens": 7, "cachedInputTokens": 3, "totalTokens": 18}},
    }
    if turn is not None:
        params["turnId"] = turn
    return json.dumps({"method": "thread/tokenUsage/updated", "params": params})


def _active_driver() -> CodexAppServerV2Driver:
    drv = CodexAppServerV2Driver()
    drv._state = ProtocolState(phase=ProtocolPhase.TURN_ACTIVE, thread_id="thr-1", turn_id="turn-1")
    return drv


@pytest.mark.parametrize("frame", [_ghost_frame("other"), _ghost_frame("thr-1", "old-turn")])
def test_guard_drops_ghost_usage_only_when_enabled(monkeypatch: pytest.MonkeyPatch, frame: str) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", "/nonexistent/dynamic_config.json")
    monkeypatch.setenv(CODEX_USAGE_FRAME_GUARD_FLAG, "false")
    chunk = _active_driver().decode_line(frame)
    assert chunk is not None and chunk.usage is not None
    monkeypatch.setenv(CODEX_USAGE_FRAME_GUARD_FLAG, "true")
    guarded = _active_driver().decode_line(frame)
    assert guarded is None or guarded.usage is None


def test_guard_keeps_matching_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", "/nonexistent/dynamic_config.json")
    monkeypatch.setenv(CODEX_USAGE_FRAME_GUARD_FLAG, "true")
    chunk = _active_driver().decode_line(_ghost_frame("thr-1", "turn-1"))
    assert chunk is not None and chunk.usage is not None
