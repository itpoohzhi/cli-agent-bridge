"""Contract tests for Agy Zero-Canon runtime isolation, GigaRC switch, sessions and rotation."""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = ROOT / "bridges" / "agy-bridge"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from agy_runtime import slot_and_session as ss  # noqa: E402
from agy_runtime import zero_canon_profile as zcp  # noqa: E402
from core.agy_zero_canon import AGY_CANON_FILE_NAMES, AGY_ZC_AUTH_RELPATHS  # noqa: E402

_AUTH_BODIES = {
    ".gemini/jetski-standalone-oauth-token": "oauth-1",
    ".gemini/projects.json": '{"projects": {}}',
    ".gemini/antigravity-cli/antigravity-oauth-token": "oauth-2",
    ".gemini/antigravity-cli/installation_id": "inst-123",
    ".gemini/antigravity-cli/jetski_state.pbtxt": "state: 1",
}


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


def _setup_real_home(tmp_path: Path, settings: dict[str, object] | None = None) -> tuple[Path, Path]:
    real_home = tmp_path / "real_home"
    clean_home = tmp_path / "runtime" / "agy-home"
    (real_home / "Library" / "Keychains").mkdir(parents=True)
    for rel, body in _AUTH_BODIES.items():
        p = real_home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    cli = real_home / ".gemini" / "antigravity-cli"
    (cli / "antigravity-account.json").write_text('{"email":"u@x"}', encoding="utf-8")
    (cli / "bin").mkdir(parents=True, exist_ok=True)
    (cli / "bin" / "helper").write_text("#!/bin/sh\n", encoding="utf-8")
    (cli / "settings.json").write_text(
        json.dumps(settings if settings is not None else {
            "selectedAuthType": "oauth-personal",
            "theme": "dark",
            "hooks": {"PreToolUse": ["x"]},
            "mcpServers": {"evil": {"command": "sh"}},
            "trustedWorkspaces": ["/Users/a"],
            "permissions": {"allow": ["Bash"]},
            "allowNonWorkspaceAccess": True,
            "model": "gemini-4",
            "artifactReviewPolicy": "always",
            "toolPermission": "auto",
        }),
        encoding="utf-8",
    )
    for name in AGY_CANON_FILE_NAMES:
        (real_home / ".gemini" / name).write_text("canon", encoding="utf-8")
        (cli / name).write_text("canon", encoding="utf-8")
    return real_home, clean_home


def _load_server() -> object:
    name = "agy_bridge_server_zc_contract_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BRIDGE_DIR / "server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    with mock.patch.dict(os.environ, {"AGY_BRIDGE_KEY": "test-zc-key"}):
        spec.loader.exec_module(mod)
    return mod


def test_gigarc_flag_defaults_kill_switch_and_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGY_ZERO_CANON_ENABLED", raising=False)
    cfg = tmp_path / "dynamic_config.json"
    assert zcp.is_agy_zero_canon_enabled(cfg, environ={}) is False

    cfg.write_text("{broken json", encoding="utf-8")
    assert zcp.is_agy_zero_canon_enabled(cfg, environ={}) is False

    cfg.write_text('{"AGY_ZERO_CANON_ENABLED": "not-bool"}', encoding="utf-8")
    assert zcp.is_agy_zero_canon_enabled(cfg, environ={}) is False

    cfg.write_text('{"AGY_ZERO_CANON_ENABLED": true}', encoding="utf-8")
    assert zcp.is_agy_zero_canon_enabled(cfg, environ={}) is True

    # Instant kill-switch without restart or TTL delay
    cfg.write_text('{"AGY_ZERO_CANON_ENABLED": false}', encoding="utf-8")
    assert zcp.is_agy_zero_canon_enabled(cfg, environ={}) is False

    cfg.write_text('{"AGY_ZERO_CANON_ENABLED": false}', encoding="utf-8")
    assert zcp.is_agy_zero_canon_enabled(cfg, environ={"AGY_ZERO_CANON_ENABLED": "true"}) is False


def test_zc_home_isolation_modes_settings_and_ro_builtin(tmp_path: Path) -> None:
    real_home, clean_home = _setup_real_home(tmp_path)
    mgr = zcp.AgyZeroCanonProfileManager(real_home, clean_home)
    zc_home = mgr.prepare_zc_home()
    assert zc_home == (clean_home.parent / "agy-home-zc").resolve()
    assert not clean_home.exists()

    assert (zc_home / "Library").is_symlink()
    assert os.readlink(zc_home / "Library") == str(real_home / "Library")

    for rel in AGY_ZC_AUTH_RELPATHS:
        dst = zc_home / rel
        assert dst.is_file() and not dst.is_symlink()
        assert dst.read_text(encoding="utf-8") == _AUTH_BODIES[rel]
        assert _mode(dst) == 0o600

    zc_cli = zc_home / ".gemini" / "antigravity-cli"
    assert not (zc_cli / "antigravity-account.json").exists()
    assert (zc_cli / "bin" / "helper").is_symlink()

    settings_path = zc_cli / "settings.json"
    assert _mode(settings_path) == 0o600
    assert json.loads(settings_path.read_text(encoding="utf-8")) == {
        "selectedAuthType": "oauth-personal",
        "theme": "dark",
        "hooks": {},
        "mcpServers": {},
    }

    for sub_name in ("skills", "plugins"):
        sub = zc_cli / "builtin" / sub_name
        assert sub.is_dir() and not sub.is_symlink()
        assert list(sub.iterdir()) == []
        assert _mode(sub) == 0o500
        if os.geteuid() != 0:
            with pytest.raises(PermissionError):
                (sub / "unpacked.txt").write_text("fail", encoding="utf-8")

    for name in AGY_CANON_FILE_NAMES:
        assert list(zc_home.rglob(name)) == []

    zc_cwd = mgr.ensure_zc_cwd()
    assert zc_cwd.is_dir() and list(zc_cwd.iterdir()) == []
    assert _mode(zc_cwd) == 0o700


def test_session_and_continuity_scope_isolation() -> None:
    assert ss.continuity_scope("m1", "") == "m1\x00"
    assert ss.continuity_scope("m1", "sub1") == "m1\x00sub1\x00"
    assert ss.continuity_scope("m1", "sub1", review_profile="zero-canon") != ss.continuity_scope("m1", "sub1")
    assert ss.continuity_scope("m1", "", review_profile="zero-canon") != ss.continuity_scope("m1", "")

    k_std_chat = ss.hot_session_key("m1", "/tmp/w", "high", "chat-1", review_profile="standard")
    k_zc_chat = ss.hot_session_key("m1", "/tmp/w", "high", "chat-1", review_profile="zero-canon")
    assert k_std_chat != k_zc_chat

    k_std_cwd = ss.hot_session_key("m1", "/tmp/w", "high", "", review_profile="standard")
    k_zc_cwd = ss.hot_session_key("m1", "/tmp/w", "high", "", review_profile="zero-canon")
    assert k_std_cwd != k_zc_cwd

    srv = _load_server()
    for key in (k_std_chat, k_zc_chat, k_std_cwd, k_zc_cwd):
        assert srv._session_key_valid(key)
        assert srv._session_key_from_json(list(key)) == key


def test_rotate_agy_runtime_artifacts_ttl_cap_and_active_protection(tmp_path: Path) -> None:
    real_home, clean_home = _setup_real_home(tmp_path)
    mgr = zcp.AgyZeroCanonProfileManager(real_home, clean_home)
    zc_home = mgr.prepare_zc_home()
    gemini = zc_home / ".gemini"
    cli = gemini / "antigravity-cli"
    now = 1_700_000_000.0

    for sub in ("log", "presence"):
        (cli / sub).mkdir(parents=True, exist_ok=True)
    old_log = cli / "log" / "old.log"
    new_log = cli / "log" / "new.log"
    extra_log = cli / "log" / "mid.log"
    for p, ts in ((old_log, now - 500), (extra_log, now - 20), (new_log, now - 5)):
        p.write_text("x", encoding="utf-8")
        os.utime(p, (ts, ts))

    old_tmp = cli / "jetbox_summaries_proto.pb.123.tmp"
    fresh_tmp = cli / "jetbox_summaries_proto.pb.456.tmp"
    old_tmp.write_text("orphan", encoding="utf-8")
    fresh_tmp.write_text("active", encoding="utf-8")
    os.utime(old_tmp, (now - 500, now - 500))
    os.utime(fresh_tmp, (now - 5, now - 5))

    active_db = cli / "conversations" / "cid-active.db"
    stale_db = cli / "conversations" / "cid-stale.db"
    active_brain = cli / "brain" / "cid-active"
    stale_brain = cli / "brain" / "cid-stale"
    active_brain.mkdir()
    stale_brain.mkdir()
    for p in (active_db, stale_db, active_brain, stale_brain):
        if p.is_file() or not p.exists():
            p.write_text("db", encoding="utf-8")
        os.utime(p, (now - 500, now - 500))

    removed = zcp.rotate_agy_runtime_artifacts(
        zc_home, max_age_s=100.0, max_files=1, active_cids={"cid-active"}, now=now
    )
    assert removed >= 5
    assert not old_log.exists() and not extra_log.exists() and new_log.exists()
    assert not old_tmp.exists() and fresh_tmp.exists()
    assert active_db.exists() and not stale_db.exists()
    assert active_brain.exists() and not stale_brain.exists()
    for rel in AGY_ZC_AUTH_RELPATHS:
        assert (zc_home / rel).is_file()
    assert (cli / "settings.json").is_file()


def test_server_run_uses_zero_canon_flags_home_and_kill_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    srv = _load_server()
    real_home, clean_home = _setup_real_home(tmp_path)
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text('{"AGY_ZERO_CANON_ENABLED": true}', encoding="utf-8")
    monkeypatch.delenv("AGY_ZERO_CANON_ENABLED", raising=False)
    monkeypatch.setattr(srv, "HOME", real_home)
    monkeypatch.setattr(srv, "CLEAN_HOME_DIR", clean_home)
    monkeypatch.setattr(srv, "BRAIN_DIR", clean_home / ".gemini" / "antigravity-cli" / "brain")
    monkeypatch.setattr(srv, "CONV_DIR", clean_home / ".gemini" / "antigravity-cli" / "conversations")
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)
    monkeypatch.setattr(srv, "_AGY_HOME_INITIALIZED", False)
    monkeypatch.setattr(srv, "_VERIFIED_CLEAN_HOME", None)
    monkeypatch.setattr(srv, "_launcher", lambda: "/bin/echo")

    captured: list[tuple[list[str], dict[str, str]]] = []
    def fake_spawn(cmd: list[str], **kwargs: object) -> object:
        captured.append((list(cmd), dict(kwargs["env"])))  # type: ignore[arg-type]
        return mock.MagicMock()

    monkeypatch.setattr(srv, "spawn_registered", fake_spawn)
    monkeypatch.setattr(srv, "_cid_acquire", lambda *_a, **_kw: True)
    monkeypatch.setattr(srv, "_prespawn_plan", lambda *_a, **_kw: mock.MagicMock())

    plan_on = zcp.resolve_turn_plan({"X-Review-Profile": "Zero-Canon"}, cfg, environ={})
    assert plan_on.enabled is True
    srv.Run("hi", "gemini-4", "low", "default", str(tmp_path), "t1", mode="agent", zero_canon=plan_on.enabled)
    cmd_zc, env_zc = captured[-1]
    assert "--disable-slash-commands" in cmd_zc
    assert any(cmd_zc[i] == "--settings" and cmd_zc[i + 1] == "{}" for i in range(len(cmd_zc) - 1))
    assert env_zc["HOME"] == str((clean_home.parent / "agy-home-zc").resolve())

    # Kill-switch disables Zero-Canon immediately -> standard agy-home & no --settings
    cfg.write_text('{"AGY_ZERO_CANON_ENABLED": false}', encoding="utf-8")
    plan_off = zcp.resolve_turn_plan({"X-Review-Profile": "Zero-Canon"}, cfg, environ={})
    assert plan_off.enabled is False
    srv.Run("hi", "gemini-4", "low", "default", str(tmp_path), "t2", mode="agent", zero_canon=plan_off.enabled)
    cmd_std, env_std = captured[-1]
    assert "--disable-slash-commands" not in cmd_std
    assert "--settings" not in cmd_std
    assert env_std["HOME"] == str(clean_home.resolve())


def test_prepare_zc_home_repeated_calls_overwrite_settings_and_auth_and_reject_symlink(
    tmp_path: Path,
) -> None:
    """Повторный prepare_zc_home() обязан атомарно обновлять settings.json/auth без FileExistsError."""
    import os
    import time

    from core import zero_canon_fs as zfs

    real_home = tmp_path / "real-home"
    real_cli = real_home / ".gemini" / "antigravity-cli"
    real_cli.mkdir(parents=True)
    settings_src = real_cli / "settings.json"
    token_src = real_cli / "antigravity-oauth-token"
    settings_src.write_text('{"theme": "dark", "mcpServers": {"bad": {}}}', encoding="utf-8")
    token_src.write_text("token-v1", encoding="utf-8")

    clean_home = tmp_path / "runtime" / "agy-home"
    mgr = zcp.AgyZeroCanonProfileManager(real_home, clean_home)

    # 1st call creates agy-home-zc/settings.json and auth
    zc_home = mgr.prepare_zc_home()
    zc_cli = zc_home / ".gemini" / "antigravity-cli"
    assert (zc_cli / "settings.json").is_file()
    assert (zc_cli / "antigravity-oauth-token").read_text(encoding="utf-8") == "token-v1"

    # Update source settings and auth with newer mtime, then invoke prepare_zc_home() a 2nd time
    settings_src.write_text('{"theme": "light", "mcpServers": {"bad": {}}}', encoding="utf-8")
    token_src.write_text("token-v2-updated", encoding="utf-8")
    future = time.time() + 10.0
    os.utime(token_src, (future, future))

    mgr.prepare_zc_home()
    assert (zc_cli / "antigravity-oauth-token").read_text(encoding="utf-8") == "token-v2-updated"
    assert (zc_cli / "settings.json").stat().st_mode & 0o777 == 0o600
    parsed = json.loads((zc_cli / "settings.json").read_text(encoding="utf-8"))
    assert parsed["theme"] == "light"
    assert parsed["mcpServers"] == {}

    # Reject pre-existing symlink, directory, or symlinked parent directory
    sym_target = tmp_path / "outside.txt"
    sym_target.write_text("keep", encoding="utf-8")
    sym = zc_cli / "sym-test.json"
    sym.symlink_to(sym_target)
    with pytest.raises(OSError):
        zfs.replace_atomic_0600(sym, b"overwrite")
    assert sym_target.read_text(encoding="utf-8") == "keep"

    dir_dst = zc_cli / "dir-test"
    dir_dst.mkdir()
    with pytest.raises(IsADirectoryError):
        zfs.replace_atomic_0600(dir_dst, b"overwrite")

    real_parent = tmp_path / "outside-dir"
    real_parent.mkdir()
    sym_parent = zc_cli / "sym-parent"
    sym_parent.symlink_to(real_parent)
    with pytest.raises(OSError):
        zfs.replace_atomic_0600(sym_parent / "file.json", b"overwrite")
    assert not (real_parent / "file.json").exists()

