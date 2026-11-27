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
