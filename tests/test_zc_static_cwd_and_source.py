"""Tests for AD-003 static read-only Codex Zero-Canon CWD and allowlisted source tags."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.stdio_drivers.muse_driver import MuseMspDriver  # noqa: E402
from adapters.stdio_drivers.opencode_driver import OpenCodeAcpDriver  # noqa: E402
from core.stdio_resident.claude_driver import ClaudeStreamJsonDriver  # noqa: E402
from core.stdio_resident.codex_driver import CodexAppServerDriver, CodexAppServerV2Driver  # noqa: E402
from core.stdio_resident.protocol_driver import StreamJsonDriver  # noqa: E402
from core.stdio_resident.zero_canon_router import ZeroCanonIsolation, zero_canon_isolation  # noqa: E402
from core.zc_static_cwd_and_source import (  # noqa: E402
    ALLOWED_CODEX_SOURCE_TAGS,
    DEFAULT_STATIC_CODEX_CWD,
    ensure_and_verify_static_codex_cwd,
    is_source_header_enabled,
    is_static_cwd_enabled,
    resolve_codex_source_tag,
    resolve_zero_canon_cwd,
)


def _seed_codex_home(base: Path) -> dict[str, str]:
    codex_dir = base / ".codex"
    codex_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    (codex_dir / "config.toml").write_text('model = "gpt-6.1-sol"\n', encoding="utf-8")
    (codex_dir / "auth.json").write_text('{"OPENAI_API_KEY": "sk-dummy"}', encoding="utf-8")
    return {"HOME": str(base), "CODEX_HOME": str(codex_dir), "PATH": "/usr/bin:/bin"}


def test_codex_zero_canon_uses_static_0555_cwd_and_ephemeral_homes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    static_cwd = tmp_path / "static-codex-cwd"
    monkeypatch.setenv("BRIDGE_ZC_STATIC_CWD_PATH", str(static_cwd))
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    base_env = _seed_codex_home(tmp_path / "real_home")

    roots: list[Path] = []
    cwds: list[str | None] = []
    homes: list[str] = []
    codex_homes: list[str] = []

    for driver in (CodexAppServerDriver(), CodexAppServerV2Driver()):
        with zero_canon_isolation(driver, "Zero-Canon") as iso:
            assert iso.active and iso.root is not None
            root_path = Path(iso.root)
            roots.append(root_path)
            cwds.append(iso.cwd)
            assert stat.S_IMODE(root_path.stat().st_mode) == 0o700
            assert iso.cwd == str(static_cwd)
            assert stat.S_IMODE(static_cwd.stat().st_mode) == 0o555
            assert list(static_cwd.iterdir()) == []
            if os.geteuid() != 0:
                with pytest.raises(PermissionError):
                    (static_cwd / "probe.txt").write_text("x", encoding="utf-8")
            env = iso.env(base_env)
            assert env is not None
            homes.append(env["HOME"])
            codex_homes.append(env["CODEX_HOME"])
            assert stat.S_IMODE(Path(env["HOME"]).stat().st_mode) == 0o700
            assert stat.S_IMODE(Path(env["CODEX_HOME"]).stat().st_mode) == 0o700

    assert cwds == [str(static_cwd), str(static_cwd)]
    assert roots[0] != roots[1]
    assert homes[0] != homes[1] and codex_homes[0] != codex_homes[1]
    assert not roots[0].exists() and not roots[1].exists()
    assert static_cwd.is_dir() and list(static_cwd.iterdir()) == []


def test_non_codex_drivers_preserve_per_turn_root_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    static_cwd = tmp_path / "unused-static-cwd"
    monkeypatch.setenv("BRIDGE_ZC_STATIC_CWD_PATH", str(static_cwd))
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))

    class _CustomDriver(StreamJsonDriver):
        def build_zero_canon_env(self, base_env: dict[str, str], root: str) -> dict[str, str]:
            return {**base_env, "HOME": root}

    for driver in (ClaudeStreamJsonDriver(), OpenCodeAcpDriver(), MuseMspDriver(), _CustomDriver()):
        with zero_canon_isolation(driver, "zero-canon") as iso:
            assert iso.root is not None
            assert iso.cwd == os.path.join(iso.root, "cwd")
            assert Path(iso.cwd).is_dir()
            assert stat.S_IMODE(Path(iso.cwd).stat().st_mode) == 0o700
    assert not static_cwd.exists()


def test_static_cwd_fail_closed_on_symlink_bad_mode_and_non_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_empty = tmp_path / "real_empty"
    real_empty.mkdir(mode=0o700)
    os.chmod(real_empty, 0o555)
    sym = tmp_path / "symlink_cwd"
    sym.symlink_to(real_empty)
    with pytest.raises(RuntimeError, match="zero_canon_static_cwd_unsafe"):
        ensure_and_verify_static_codex_cwd(sym)

    broken = tmp_path / "broken_link"
    broken.symlink_to(tmp_path / "does_not_exist")
    with pytest.raises(RuntimeError, match="zero_canon_static_cwd_unsafe"):
        ensure_and_verify_static_codex_cwd(broken)

    reg_file = tmp_path / "not_a_dir"
    reg_file.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="zero_canon_static_cwd_unsafe"):
        ensure_and_verify_static_codex_cwd(reg_file)

    bad_mode = tmp_path / "bad_mode_0755"
    bad_mode.mkdir(mode=0o755)
    os.chmod(bad_mode, 0o755)
    with pytest.raises(RuntimeError, match="zero_canon_static_cwd_unsafe"):
        ensure_and_verify_static_codex_cwd(bad_mode)

    non_empty = tmp_path / "non_empty_0555"
    non_empty.mkdir(mode=0o700)
    (non_empty / "AGENTS.md").write_text("poison", encoding="utf-8")
    os.chmod(non_empty, 0o555)
    try:
        with pytest.raises(RuntimeError, match="zero_canon_static_cwd_unsafe"):
            ensure_and_verify_static_codex_cwd(non_empty)
        monkeypatch.setenv("BRIDGE_ZC_STATIC_CWD_PATH", str(non_empty))
        monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
        with pytest.raises(RuntimeError, match="zero_canon_static_cwd_unsafe"):
            with zero_canon_isolation(CodexAppServerDriver(), "zero-canon"):
                pass
        assert [p for p in tmp_path.iterdir() if p.name.startswith("zc-")] == []
    finally:
        os.chmod(non_empty, 0o700)


def test_static_cwd_kill_switch_and_driver_detection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert DEFAULT_STATIC_CODEX_CWD == "/private/tmp/zc-codex-empty-cwd"
    assert is_static_cwd_enabled({}) is True
    for falsy in ("0", "false", "FALSE", "no", "off"):
        assert is_static_cwd_enabled({"BRIDGE_ZC_STATIC_CWD_ENABLED": falsy}) is False

    static_cwd = tmp_path / "static-unused"
    monkeypatch.setenv("BRIDGE_ZC_STATIC_CWD_PATH", str(static_cwd))
    monkeypatch.setenv("BRIDGE_ZC_STATIC_CWD_ENABLED", "0")
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))

    with zero_canon_isolation(CodexAppServerDriver(), "zero-canon") as iso:
        assert iso.root is not None
        assert iso.cwd == os.path.join(iso.root, "cwd")
        assert Path(iso.cwd).is_dir()
    assert not static_cwd.exists()

    class _ProtoOnlyDriver:
        protocol = "codex-app-server-v2"

    class _BackendOnlyDriver:
        backend_id = "codex"

    target = tmp_path / "proto-static"
    env = {"BRIDGE_ZC_STATIC_CWD_PATH": str(target), "BRIDGE_ZC_STATIC_CWD_ENABLED": "1"}
    assert resolve_zero_canon_cwd(_ProtoOnlyDriver(), str(tmp_path / "r1"), environ=env) == str(target)
    assert resolve_zero_canon_cwd(_BackendOnlyDriver(), str(tmp_path / "r2"), environ=env) == str(target)
    assert ZeroCanonIsolation(CodexAppServerDriver(), None).cwd is None


def test_source_header_flag_and_allowlisted_source_tag() -> None:
    assert len(ALLOWED_CODEX_SOURCE_TAGS) <= 16
    assert is_source_header_enabled({}) is True
    for falsy in ("0", "false", "no", "off"):
        assert is_source_header_enabled({"BRIDGE_CODEX_SOURCE_HEADER_ENABLED": falsy}) is False

    assert resolve_codex_source_tag(None, is_zero_canon=True) == "bridge:zero-canon"
    assert resolve_codex_source_tag(None, is_zero_canon=False) == "bridge:standard"
    assert resolve_codex_source_tag({"X-Bridge-Source": "bridge:arl"}) == "bridge:arl"
    assert resolve_codex_source_tag({"X-Bridge-Source": "council"}) == "bridge:council"
    assert resolve_codex_source_tag({"X-Codex-Source": "ARCHITECT"}) == "bridge:architect"
    assert resolve_codex_source_tag({"X-Subagent-Id": "coder-1"}) == "bridge:coder"

    for secret in ("Bearer sk-secret-12345", "sk-proj-xyz", "ignore rules", "x" * 100):
        tag = resolve_codex_source_tag({"X-Bridge-Source": secret}, is_zero_canon=True)
        assert tag == "bridge:unknown" and "sk-" not in tag
    assert resolve_codex_source_tag({"Authorization": "Bearer sk-123"}, is_zero_canon=True) == "bridge:zero-canon"


def _seed_codex_home_with_lb(base: Path, *, with_existing_headers: bool = True) -> dict[str, str]:
    codex_dir = base / ".codex"
    codex_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    hdr_block = '\n[model_providers.codex-lb.http_headers]\nX-Existing = "keep-me"\n' if with_existing_headers else ""
    (codex_dir / "config.toml").write_text(
        'model = "gpt-6.1-sol"\n[mcp_servers.bad]\ncommand = "echo"\n'
        '[model_providers.codex-lb]\nname = "codex-lb"\nbase_url = "http://127.0.0.1:2455/v1"\n'
        + hdr_block,
        encoding="utf-8",
    )
    (codex_dir / "auth.json").write_text('{"OPENAI_API_KEY": "sk-dummy"}', encoding="utf-8")
    return {"HOME": str(base), "CODEX_HOME": str(codex_dir), "PATH": "/usr/bin:/bin"}


def test_prepare_codex_zero_canon_home_injects_x_codex_source_and_preserves_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tomllib
    from core.subbridge_zero_canon import filter_codex_config
    from core.zero_canon_fs import prepare_codex_zero_canon_home

    monkeypatch.delenv("BRIDGE_CODEX_SOURCE_HEADER_ENABLED", raising=False)
    base_env = _seed_codex_home_with_lb(tmp_path / "home_default", with_existing_headers=True)
    zc_root = tmp_path / "zc-default"
    isolated = prepare_codex_zero_canon_home(base_env, zc_root)
    dst_codex = Path(isolated["CODEX_HOME"])

    assert stat.S_IMODE(dst_codex.stat().st_mode) == 0o700
    assert stat.S_IMODE((dst_codex / "auth.json").stat().st_mode) == 0o600
    parsed = tomllib.loads((dst_codex / "config.toml").read_text(encoding="utf-8"))
    assert parsed["project_doc_max_bytes"] == 0
    assert "mcp_servers" not in parsed
    headers = parsed["model_providers"]["codex-lb"]["http_headers"]
    assert headers["X-Codex-Source"] == "bridge:zero-canon"
    assert headers["X-Existing"] == "keep-me"

    # When codex-lb is absent, section must not be synthesized; non-allowlisted raw secrets fail closed.
    no_lb_env = _seed_codex_home(tmp_path / "home_no_lb")
    out_no_lb = prepare_codex_zero_canon_home(no_lb_env, tmp_path / "zc-no-lb")
    parsed_no_lb = tomllib.loads((Path(out_no_lb["CODEX_HOME"]) / "config.toml").read_text(encoding="utf-8"))
    assert "model_providers" not in parsed_no_lb

    filtered = filter_codex_config({"model_providers": {"codex-lb": {"name": "codex-lb"}}}, source_tag="Bearer sk-secret")
    assert filtered["model_providers"]["codex-lb"]["http_headers"]["X-Codex-Source"] == "bridge:unknown"


def test_prepare_codex_zero_canon_home_kill_switch_omits_x_codex_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tomllib
    from core.zero_canon_fs import prepare_codex_zero_canon_home

    base_env = _seed_codex_home_with_lb(tmp_path / "home_off", with_existing_headers=True)
    out_env = prepare_codex_zero_canon_home({**base_env, "BRIDGE_CODEX_SOURCE_HEADER_ENABLED": "0"}, tmp_path / "zc-env-off")
    parsed_env = tomllib.loads((Path(out_env["CODEX_HOME"]) / "config.toml").read_text(encoding="utf-8"))
    hdrs_env = parsed_env["model_providers"]["codex-lb"]["http_headers"]
    assert "X-Codex-Source" not in hdrs_env and hdrs_env["X-Existing"] == "keep-me"

    monkeypatch.setenv("BRIDGE_CODEX_SOURCE_HEADER_ENABLED", "0")
    out_os = prepare_codex_zero_canon_home(base_env, tmp_path / "zc-os-off")
    parsed_os = tomllib.loads((Path(out_os["CODEX_HOME"]) / "config.toml").read_text(encoding="utf-8"))
    hdrs_os = parsed_os["model_providers"]["codex-lb"]["http_headers"]
    assert "X-Codex-Source" not in hdrs_os and hdrs_os["X-Existing"] == "keep-me"
