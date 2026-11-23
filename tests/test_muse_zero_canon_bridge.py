"""Regression tests for Muse Zero-Canon bridge wiring (:9882 and :9886)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from adapters.stdio_drivers.muse_codec import build_session_start_msg
from adapters.stdio_drivers.muse_driver import MuseMspDriver
from adapters.stdio_drivers.muse_env import build_muse_env, build_muse_zero_canon_env
from adapters.stdio_resident_adapter import StdioResidentAdapter
from core.subbridge_zero_canon import filter_muse_settings


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stdio_resident_adapter_passes_config_to_muse_driver(tmp_path: Path) -> None:
    fake_bin = tmp_path / "muse"
    fake_bin.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    fake_bin.chmod(0o755)
    fake_wrapper = tmp_path / "muse-cli.sh"
    fake_wrapper.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    fake_wrapper.chmod(0o755)
    cfg: dict[str, Any] = {
        "kind": "stdio_resident",
        "enabled": True,
        "wrapper": str(fake_wrapper),
        "technical_ref": {
            "version": "1.4.25-R9361.1",
            "binary_path": str(fake_bin),
            "binary_sha256": _sha256_file(fake_bin),
        },
    }
    adapter = StdioResidentAdapter("muse", cfg)
    assert isinstance(adapter._driver, MuseMspDriver)
    assert adapter._driver.verify_environment() == (True, "")


def test_build_muse_env_sets_muse_bin_and_disables_auto_update(tmp_path: Path) -> None:
    src_home = tmp_path / "src_home"
    cfg_dir = src_home / ".config" / "muse"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "auth.json").write_text('{"providers":{"meta":{"access_token":"tok"}}}\n', encoding="utf-8")
    (cfg_dir / "settings.json").write_text(
        json.dumps({
            "schema_version": 1,
            "provider": "meta",
            "provider_retry": {"base_delay_ms": 500, "retry_after_cap_ms": 2000},
            "contributor_mode_enabled": False,
            "contributor_mode_disclosure_acknowledged": True,
            "hooks": {"Stop": [{"hooks": [{"command": "evil"}]}]},
            "permissions": {"default_profile": ":unrestricted"},
        }),
        encoding="utf-8",
    )
    (cfg_dir / "AGENTS.md").write_text("SECRET_RULES", encoding="utf-8")
    (src_home / "Library" / "Keychains").mkdir(parents=True)
    (src_home / "Library" / "Keychains" / "login.keychain-db").write_text("KC", encoding="utf-8")
    (src_home / "Library" / "Cookies").mkdir(parents=True)

    zc_root = tmp_path / "zc_root"
    env = build_muse_zero_canon_env(
        None,
        "/real/path/muse",
        str(zc_root),
        server_env={"HOME": str(src_home), "PATH": "/usr/bin", "MUSE_PROXY_PORT": "10820"},
    )
    assert env["MUSE_BIN"] == "/real/path/muse"
    assert env["MUSE_BIN_PATH"] == "/real/path/muse"
    assert env["MUSE_NO_AUTO_UPDATE"] == "1"
    assert env["MUSE_PROXY_PORT"] == "10820"
    assert env["BRIDGE_ZERO_CANON"] == "1"
    assert env["HOME"] == str((zc_root / "home").resolve())
    assert env["XDG_CONFIG_HOME"] == str((zc_root / "home").resolve() / ".config")
    assert not (zc_root / "home" / ".config" / "muse" / "AGENTS.md").exists()
    assert not (zc_root / "home" / "Library" / "Cookies").exists()
    import sys as _sys
    if _sys.platform == "darwin":
        assert (zc_root / "home" / "Library" / "Keychains").is_symlink()
    zc_settings = json.loads((zc_root / "home" / ".config" / "muse" / "settings.json").read_text(encoding="utf-8"))
    assert zc_settings["provider_retry"] == {"base_delay_ms": 500, "retry_after_cap_ms": 2000}
    assert zc_settings["contributor_mode_enabled"] is False
    assert "hooks" not in zc_settings
    assert "permissions" not in zc_settings


def test_build_muse_env_standard_also_disables_auto_update() -> None:
    env = build_muse_env(None, "/real/muse", server_env={"PATH": "/usr/bin", "HOME": "/tmp/h"})
    assert env["MUSE_BIN"] == "/real/muse"
    assert env["MUSE_BIN_PATH"] == "/real/muse"
    assert env["MUSE_NO_AUTO_UPDATE"] == "1"


def test_filter_muse_settings_preserves_retry_and_strips_hooks() -> None:
    filtered = filter_muse_settings({
        "schema_version": 1,
        "provider": "meta",
        "provider_retry": {"base_delay_ms": 500},
        "contributor_mode_enabled": False,
        "contributor_mode_disclosure_acknowledged": True,
        "hooks": {"SessionStart": []},
        "permissions": {"default_profile": ":unrestricted"},
        "mcpServers": {"evil": {}},
    })
    assert set(filtered) == {
        "schema_version",
        "provider",
        "provider_retry",
        "contributor_mode_enabled",
        "contributor_mode_disclosure_acknowledged",
    }


def test_session_start_clears_developer_prompt_only_in_zero_canon() -> None:
    std_msg = json.loads(build_session_start_msg("01a207b5-1059-769b-811d-f883fc588969"))
    assert "config" not in std_msg["params"]
    zc_msg = json.loads(
        build_session_start_msg(
            "01a207b5-1059-769b-811d-f883fc588969",
            clear_developer_prompt=True,
        )
    )
    assert zc_msg["params"]["config"] == {"developerPrompt": None}
    drv = MuseMspDriver({})
    sent: list[dict[str, Any]] = []
    drv._send_and_wait_ack = lambda _h, payload, _pred, _t: (sent.append(json.loads(payload)), True)[1]  # type: ignore[method-assign]
    for ctx in ({"review_profile": "Zero-Canon"}, {"review_profile": "zero_canon"}, {"zero_canon": True}):
        assert drv.prepare_turn(object(), ctx) is True
        assert sent[-1]["params"]["config"] == {"developerPrompt": None}


def test_muse_driver_default_serve_args_include_preset_empty_and_dedup_item_completed() -> None:
    drv = MuseMspDriver({"technical_ref": {"binary_path": "/bin/muse", "binary_sha256": "abc"}})
    args = drv._cli_args()
    assert "--preset" in args and args[args.index("--preset") + 1] == "empty"
    delta_line = json.dumps({
        "jsonrpc": "2.0", "method": "item/delta",
        "params": {"sessionId": "s1", "itemId": "i1", "field": "text", "delta": "PONG"},
    })
    completed_line = json.dumps({
        "jsonrpc": "2.0", "method": "item/completed",
        "params": {"sessionId": "s1", "item": {"itemId": "i1", "kind": "agentMessage", "text": "PONG"}},
    })
    completed_only_line = json.dumps({
        "jsonrpc": "2.0", "method": "item/completed",
        "params": {"sessionId": "s1", "item": {"itemId": "i2", "kind": "agentMessage", "text": "FALLBACK"}},
    })
    term_line = json.dumps({
        "jsonrpc": "2.0", "method": "turn/completed",
        "params": {"sessionId": "s1", "terminal": "completed"},
    })
    c1 = drv.decode_line(delta_line)
    c2 = drv.decode_line(completed_line)
    c3 = drv.decode_line(completed_only_line)
    c4 = drv.decode_line(term_line)
    assert c1 is not None and c1.text == "PONG"
    assert c2 is not None and c2.text == ""
    assert c3 is not None and c3.text == "FALLBACK"
    assert c4 is not None and c4.is_terminal is True
    assert "s1" not in drv._streamed_items


def test_subbridge_prepare_muse_launch_sets_muse_bin(tmp_path: Path) -> None:
    import importlib.util
    import sys
    mod_path = Path(__file__).resolve().parents[1] / "bridges" / "muse-bridge" / "muse_runtime" / "zero_canon_runtime.py"
    spec = importlib.util.spec_from_file_location("muse_zc_rt_test", mod_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["muse_zc_rt_test"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop("muse_zc_rt_test", None)
    zc_home = tmp_path / "zc_home"
    zc_cwd = tmp_path / "zc_cwd"
    zc_home.mkdir()
    ctx = mod.MuseZeroCanonContext(enabled=True, zc_home=zc_home, zc_cwd=zc_cwd)
    _, env, _ = mod.prepare_muse_launch(
        ["~/.config/muse-launch/muse-cli.sh", "serve"],
        {"HOME": "/Users/example", "PATH": "/usr/bin"},
        tmp_path,
        ctx=ctx,
    )
    assert env["MUSE_BIN"] == "/Users/example/.local/bin/muse"
    assert env["MUSE_BIN_PATH"] == "/Users/example/.local/bin/muse"
    assert env["MUSE_NO_AUTO_UPDATE"] == "1"
    assert env["HOME"] == str(zc_home)
