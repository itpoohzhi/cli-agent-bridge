"""Tests for scripts/dsh_zero_canon_profiles.py strictly inside tmp_path."""

from __future__ import annotations

import json
import stat
import tomllib
from pathlib import Path

import pytest

from scripts.dsh_zero_canon_profiles import (
    collect_stale_backups,
    main,
    prepare_claude_zc_profile,
    prepare_codex_zc_profile,
    render_optin_cordis_snippet,
)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _seed_claude_src(root: Path) -> Path:
    src = root / "src_claude"
    src.mkdir(parents=True)
    (src / ".credentials.json").write_text('{"token": "secret-claude"}', encoding="utf-8")
    (src / "aeza-8788-ca.pem").write_text("-----BEGIN CERTIFICATE-----\nTEST\n", encoding="utf-8")
    (src / "bundle-with-aeza.pem").write_text("-----BEGIN CERTIFICATE-----\nBUNDLE\n", encoding="utf-8")
    (src / "policy-limits.json").write_text('{"max": 10}', encoding="utf-8")
    (src / "settings.json").write_text(
        json.dumps({
            "env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:9881", "HTTPS_PROXY": "http://127.0.0.1:8788"},
            "hooks": {"PreToolUse": [{"command": "evil"}]},
            "plugins": ["some-plugin"],
            "enabledPlugins": {"foo": True},
            "mcpServers": {"bad": {"command": "mcp"}},
        }),
        encoding="utf-8",
    )
    (src / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"email": "u@example.com"}, "projects": {"/secret": {}}}),
        encoding="utf-8",
    )
    (src / "CLAUDE.md").write_text("# Global Claude canon\n", encoding="utf-8")
    (src / "agents-global.md").write_text("# Agents global\n", encoding="utf-8")
    (src / "plugins").mkdir()
    (src / "plugins" / "plugin.json").write_text("{}", encoding="utf-8")
    (src / "hooks").mkdir()
    (src / "hooks" / "run.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    return src


def _seed_codex_src(root: Path) -> Path:
    src = root / "src_codex"
    src.mkdir(parents=True)
    (src / "auth.json").write_text('{"access_token": "secret-codex"}', encoding="utf-8")
    (src / "AGENTS.md").write_text("# Global Codex canon\n", encoding="utf-8")
    (src / "config.toml").write_text(
        "\n".join((
            'model = "gpt-5.4"',
            'model_reasoning_effort = "high"',
            'notify = ["bash", "-c", "echo hi"]',
            "",
            "[mcp_servers.bad]",
            'command = "mcp-bad"',
            "",
            "[plugins.demo]",
            "enabled = true",
            "",
            "[hooks]",
            'pre = "echo"',
            "",
            "[features]",
            "fast_mode = true",
            "",
        )),
        encoding="utf-8",
    )
    return src


def test_prepare_claude_zc_profile_filters_and_enforces_0600(tmp_path: Path) -> None:
    src = _seed_claude_src(tmp_path)
    dst = tmp_path / "dsh" / "zero-canon" / "claude"

    # Dry-run must not create or write anything
    dry_report = prepare_claude_zc_profile(src, dst, dry_run=True)
    assert dry_report["dry_run"] is True
    assert not dst.exists()

    # Pre-seed stale forbidden artifacts to ensure cleanup
    dst.mkdir(parents=True)
    (dst / "CLAUDE.md").write_text("stale", encoding="utf-8")
    (dst / "agents-global.md").write_text("stale", encoding="utf-8")
    (dst / "plugins").mkdir()
    (dst / "hooks").mkdir()

    report = prepare_claude_zc_profile(src, dst, dry_run=False)
    assert report["dry_run"] is False
    assert _mode(dst) == 0o700

    for filename in (".credentials.json", "aeza-8788-ca.pem", "bundle-with-aeza.pem", "policy-limits.json", "settings.json", ".claude.json"):
        target = dst / filename
        assert target.is_file()
        assert _mode(target) == 0o600

    settings = json.loads((dst / "settings.json").read_text(encoding="utf-8"))
    assert settings == {"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:9881", "HTTPS_PROXY": "http://127.0.0.1:8788"}}
    assert "hooks" not in settings
    assert "plugins" not in settings
    assert "mcpServers" not in settings

    state = json.loads((dst / ".claude.json").read_text(encoding="utf-8"))
    assert state == {"oauthAccount": {"email": "u@example.com"}}
    assert "projects" not in state

    for forbidden in ("CLAUDE.md", "agents-global.md", "AGENTS.md", "plugins", "hooks"):
        assert not (dst / forbidden).exists()


def test_prepare_codex_zc_profile_filters_toml_and_enforces_0600(tmp_path: Path) -> None:
    src = _seed_codex_src(tmp_path)
    dst = tmp_path / "dsh" / "zero-canon" / "codex"

    dry_report = prepare_codex_zc_profile(src, dst, dry_run=True)
    assert dry_report["dry_run"] is True
    assert not dst.exists()

    report = prepare_codex_zc_profile(src, dst, dry_run=False)
    assert report["dry_run"] is False
    assert _mode(dst) == 0o700
    assert _mode(dst / "auth.json") == 0o600
    assert _mode(dst / "config.toml") == 0o600
    assert not (dst / "AGENTS.md").exists()

    parsed = tomllib.loads((dst / "config.toml").read_text(encoding="utf-8"))
    assert parsed["model"] == "gpt-5.4"
    assert parsed["project_doc_max_bytes"] == 0
    assert parsed["features"] == {"fast_mode": True}
    for denied in ("mcp_servers", "plugins", "notify", "hooks"):
        assert denied not in parsed


def test_render_optin_cordis_snippet_contains_optin_zc_instances(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude-zc"
    codex_dir = tmp_path / "codex-zc"
    snippet = render_optin_cordis_snippet(claude_dir, codex_dir)

    assert "subagent_claude_code_zc" in snippet
    assert "subagent_codex_zc" in snippet
    assert f'CLAUDE_CONFIG_DIR: "{claude_dir}"' in snippet
    assert f'CODEX_HOME: "{codex_dir}"' in snippet
    assert "disabled: true" in snippet
    assert "dsh-canon-section" in snippet.splitlines()[1]
    assert "interactive" not in snippet.lower() or "remain untouched" in snippet.lower()


def test_collect_stale_backups_dynamic_discovery_and_dry_run(tmp_path: Path) -> None:
    dsh_dir = tmp_path / "dsh"
    (dsh_dir / "profiles" / "desktop").mkdir(parents=True)
    (dsh_dir / "profiles" / "web").mkdir(parents=True)
    b1 = dsh_dir / "cordis.patch.yml.bak-20261001"
    b2 = dsh_dir / "profiles" / "desktop" / "old.backup.yml"
    b3_dir = dsh_dir / "profiles" / "web" / "dir.bak"
    b3_dir.mkdir()
    (b3_dir / "nested.bak").write_text("nested", encoding="utf-8")
    keep = dsh_dir / "profiles" / "desktop" / "cordis.patch.yml"
    b1.write_text("bak1", encoding="utf-8")
    b2.write_text("bak2", encoding="utf-8")
    keep.write_text("active: true\n", encoding="utf-8")

    # 1-arg discovery does not mutate disk
    discovered = collect_stale_backups(dsh_dir)
    assert {p.name for p in discovered} == {"cordis.patch.yml.bak-20261001", "old.backup.yml", "dir.bak"}
    assert b1.exists() and b2.exists() and b3_dir.exists()

    # --dry-run does not mutate disk
    backup_dir = tmp_path / "backups" / "2026-11-21-dsh-zero-canon"
    dry_found = collect_stale_backups(dsh_dir, backup_dir, dry_run=True)
    assert len(dry_found) == 3
    assert not backup_dir.exists()
    assert b1.exists() and b2.exists() and b3_dir.exists()

    # Real move transfers stale backups and keeps active cordis.patch.yml untouched
    moved = collect_stale_backups(dsh_dir, backup_dir, dry_run=False)
    assert len(moved) == 3
    assert not b1.exists() and not b2.exists() and not b3_dir.exists()
    assert keep.read_text(encoding="utf-8") == "active: true\n"
    assert (backup_dir / "cordis.patch.yml.bak-20261001").is_file()
    assert (backup_dir / "profiles" / "desktop" / "old.backup.yml").is_file()
    assert (backup_dir / "profiles" / "web" / "dir.bak" / "nested.bak").is_file()


def test_cli_main_dry_run_and_apply_strictly_in_tmp_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dsh_dir = tmp_path / "dsh"
    (dsh_dir / "profiles" / "desktop").mkdir(parents=True)
    cordis = dsh_dir / "profiles" / "desktop" / "cordis.patch.yml"
    cordis.write_text("# dsh-canon-section\ninteractive: true\n", encoding="utf-8")
    stale = dsh_dir / "profiles" / "desktop" / "cordis.patch.yml.bak"
    stale.write_text("old", encoding="utf-8")
    claude_src = _seed_claude_src(tmp_path)
    codex_src = _seed_codex_src(tmp_path)
    backup_dir = tmp_path / "backups" / "run-1"

    rc_dry = main([
        "--dry-run",
        "--dsh-dir", str(dsh_dir),
        "--claude-src", str(claude_src),
        "--codex-src", str(codex_src),
        "--backup-dir", str(backup_dir),
    ])
    assert rc_dry == 0
    out_dry = capsys.readouterr().out
    assert "subagent_claude_code_zc" in out_dry
    assert "subagent_codex_zc" in out_dry
    assert not (dsh_dir / "zero-canon").exists()
    assert not backup_dir.exists()
    assert stale.exists()

    rc_apply = main([
        "--dsh-dir", str(dsh_dir),
        "--claude-src", str(claude_src),
        "--codex-src", str(codex_src),
        "--backup-dir", str(backup_dir),
    ])
    assert rc_apply == 0
    _ = capsys.readouterr().out
    assert (dsh_dir / "zero-canon" / "claude" / "settings.json").is_file()
    assert (dsh_dir / "zero-canon" / "codex" / "config.toml").is_file()
    assert not stale.exists()
    assert (backup_dir / "profiles" / "desktop" / "cordis.patch.yml.bak").is_file()
    assert cordis.read_text(encoding="utf-8") == "# dsh-canon-section\ninteractive: true\n"
