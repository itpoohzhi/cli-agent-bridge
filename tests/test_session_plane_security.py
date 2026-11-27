from __future__ import annotations

import ast
import json
import os
import stat
from pathlib import Path

import pytest

from core.session_plane import (
    allocate_zc_slot_home,
    cleanup_zc_slot_home,
    is_agy_drain_early_exit_enabled,
    is_agy_signed_directive_enabled,
    is_passthrough_canonical_affinity_enabled,
    is_session_plane_enabled,
    is_zero_canon_keyed_resident_enabled,
    load_or_create_directive_key,
    verify_zc_slot_home,
)


def test_key_and_slot_home_are_private(tmp_path: Path) -> None:
    key_path = tmp_path / "private" / "directive.key"
    key = load_or_create_directive_key(key_path)
    assert len(key) == 32 and key == load_or_create_directive_key(key_path)
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    root = tmp_path / "slots"
    home = allocate_zc_slot_home("slot-1", base_root=root)
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    assert verify_zc_slot_home(home, base_root=root) == (True, "ok")
    cleanup_zc_slot_home(home, base_root=root)
    assert not home.exists()


def test_slot_root_rejects_system_tmp(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        allocate_zc_slot_home("slot-1", base_root=Path("/tmp"))
    with pytest.raises(ValueError):
        allocate_zc_slot_home("slot-1", base_root=Path("/private/tmp"))


def test_slot_root_rejects_subdirs_of_system_tmp() -> None:
    for bad in (Path("/tmp/sub/dir"), Path("/private/tmp/sub")):
        with pytest.raises(ValueError):
            allocate_zc_slot_home("slot-1", base_root=bad)


@pytest.mark.parametrize("mode", [0o777, 0o720])
def test_directive_key_rejects_unsafe_parent_dir(tmp_path: Path, mode: int) -> None:
    parent = tmp_path / "shared"
    parent.mkdir()
    os.chmod(parent, mode)
    with pytest.raises(ValueError):
        load_or_create_directive_key(parent / "directive.key")


def test_symlink_and_forbidden_files_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "slots"
    home = allocate_zc_slot_home("slot-2", base_root=root)
    outside = tmp_path / "outside"
    outside.mkdir()
    (home / ".codex").symlink_to(outside, target_is_directory=True)
    assert verify_zc_slot_home(home, base_root=root) == (False, "symlink_detected")
    (home / ".codex").unlink()
    (home / "mcp-config.json").write_text("{}", encoding="utf-8")
    assert verify_zc_slot_home(home, base_root=root) == (False, "forbidden_file")


def test_codex_arg0_runtime_symlinks_allowed_and_abuse_rejected(tmp_path: Path) -> None:
    root = tmp_path / "slots"
    home = allocate_zc_slot_home("slot-arg0", base_root=root)
    codex_bin = tmp_path / "codex_bin"
    codex_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    arg0 = home / ".codex" / "tmp" / "arg0-macos" / "codex-arg0ABC"
    arg0.mkdir(parents=True)
    (arg0 / "applypatch").symlink_to(codex_bin)
    (arg0 / "apply_patch").symlink_to(codex_bin)
    assert verify_zc_slot_home(home, base_root=root) == (True, "ok")
    # Злоупотребления fail-closed.
    (arg0 / "evil").symlink_to(codex_bin)
    assert verify_zc_slot_home(home, base_root=root) == (False, "symlink_detected")
    (arg0 / "evil").unlink()
    (arg0 / "applypatch").unlink()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (arg0 / "applypatch").symlink_to(outside_dir, target_is_directory=True)
    assert verify_zc_slot_home(home, base_root=root) == (False, "symlink_detected")
    (arg0 / "applypatch").unlink()
    (arg0 / "applypatch").symlink_to(codex_bin)
    (home / ".codex" / "applypatch").symlink_to(codex_bin)
    assert verify_zc_slot_home(home, base_root=root) == (False, "symlink_detected")
    (home / ".codex" / "applypatch").unlink()
    assert verify_zc_slot_home(home, base_root=root) == (True, "ok")
    cleanup_zc_slot_home(home, base_root=root)
    assert not home.exists()
    assert codex_bin.is_file() and outside_dir.is_dir()


def test_flags_default_false_and_dynamic_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "dynamic_config.json"
    env = {"BRIDGE_SESSION_PLANE_ENABLED": "true"}
    funcs = (is_session_plane_enabled, is_zero_canon_keyed_resident_enabled, is_agy_drain_early_exit_enabled, is_agy_signed_directive_enabled, is_passthrough_canonical_affinity_enabled)
    assert all(not fn(environ={}, config_path=tmp_path / "missing.json") for fn in funcs)
    cfg.write_text(json.dumps({"BRIDGE_SESSION_PLANE_ENABLED": True, "BRIDGE_AGY_SIGNED_DIRECTIVE_ENABLED": True}), encoding="utf-8")
    assert is_session_plane_enabled(environ=env, config_path=cfg) is True
    assert is_agy_signed_directive_enabled(environ={}, config_path=cfg) is True
    assert is_zero_canon_keyed_resident_enabled(environ=env, config_path=cfg) is False
    monkeypatch.setenv("BRIDGE_AGY_DRAIN_EARLY_EXIT_ENABLED", "true")
    assert is_agy_drain_early_exit_enabled(environ=os.environ, config_path=tmp_path / "missing.json") is True


_ZERO_IO_MODULES = ("identity.py", "capabilities.py", "lifecycle_policy.py", "directive_codec.py")
_FORBIDDEN_IO_IMPORTS = frozenset({"os", "pathlib", "shutil", "subprocess", "socket", "urllib", "io", "tempfile", "fcntl"})


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("name", _ZERO_IO_MODULES)
def test_zero_io_policy_modules_have_no_os_fs_imports(name: str) -> None:
    path = Path(__file__).resolve().parents[1] / "core" / "session_plane" / name
    found = _imported_roots(ast.parse(path.read_text(encoding="utf-8"))) & _FORBIDDEN_IO_IMPORTS
    assert not found, f"{name} must be Zero-I/O, found imports: {sorted(found)}"
