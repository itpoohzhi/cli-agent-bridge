"""Приватные HOME-песочницы Zero-Canon и флаги GigaRC."""

from __future__ import annotations

import os
import re
import secrets
import stat
from collections.abc import Mapping
from pathlib import Path

from core.zero_canon_fs import read_gigarc_bool, read_regular_file_nofollow, resolve_hub_dynamic_config, write_atomic_0600

DEFAULT_ZC_SLOTS_ROOT = Path.home() / ".dsh/run/zc-slots"
_DEFAULT_KEY_PATH = Path.home() / ".dsh/run/internal_directive.key"
_SAFE_SLOT = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FORBIDDEN_ROOTS = {Path("/tmp"), Path("/private/tmp")}
_FLAG_NAMES = (
    "BRIDGE_SESSION_PLANE_ENABLED", "BRIDGE_ZERO_CANON_KEYED_RESIDENT_ENABLED",
    "BRIDGE_AGY_DRAIN_EARLY_EXIT_ENABLED", "BRIDGE_AGY_SIGNED_DIRECTIVE_ENABLED",
    "BRIDGE_PASSTHROUGH_CANONICAL_AFFINITY_ENABLED",
)


def _checked_root(root: Path) -> Path:
    root = Path(root).expanduser()
    if root.is_symlink():
        raise ValueError("base_root must not be a symlink")
    resolved = root.resolve(strict=False)
    if resolved in _FORBIDDEN_ROOTS:
        raise ValueError("base_root must not be /tmp")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or stat.S_IMODE(root.stat().st_mode) != 0o700:
        os.chmod(root, 0o700)
    return resolved


def load_or_create_directive_key(path: Path | None = None) -> bytes:
    """Читает или атомарно создаёт приватный 32-байтный ключ."""
    target = Path(path) if path is not None else _DEFAULT_KEY_PATH
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.parent.is_symlink() or target.is_symlink():
        raise ValueError("directive key path must not contain a symlink")
    try:
        data = read_regular_file_nofollow(target)
    except FileNotFoundError:
        data = secrets.token_bytes(32)
        try:
            write_atomic_0600(target, data)
        except FileExistsError:
            data = read_regular_file_nofollow(target)
    if len(data) != 32:
        raise ValueError("directive key must be 32 bytes")
    mode = stat.S_IMODE(target.stat().st_mode)
    if mode != 0o600:
        raise ValueError("directive key must have mode 0600")
    return data


def allocate_zc_slot_home(slot_id: str, *, base_root: Path | None = None) -> Path:
    """Выделяет `<base>/<slot>/home` с правами 0700."""
    if not isinstance(slot_id, str) or _SAFE_SLOT.fullmatch(slot_id) is None:
        raise ValueError("unsafe slot_id")
    root = _checked_root(base_root or DEFAULT_ZC_SLOTS_ROOT)
    slot_dir = root / slot_id
    if slot_dir.exists() and slot_dir.is_symlink():
        raise ValueError("slot directory must not be a symlink")
    slot_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(slot_dir, 0o700)
    home = slot_dir / "home"
    if home.exists() and home.is_symlink():
        raise ValueError("slot home must not be a symlink")
    home.mkdir(mode=0o700, exist_ok=True)
    os.chmod(home, 0o700)
    return home


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
        return True
    except (FileNotFoundError, ValueError):
        return False


def verify_zc_slot_home(home_dir: Path, *, base_root: Path | None = None) -> tuple[bool, str]:
    """Проверяет владельца, права, containment и отсутствие утечек в HOME."""
    try:
        root = _checked_root(base_root or DEFAULT_ZC_SLOTS_ROOT)
        home = Path(home_dir)
        if home.is_symlink() or not home.is_dir() or not _inside(home, root):
            return False, "invalid_home_path"
        st = home.stat()
        if stat.S_IMODE(st.st_mode) != 0o700:
            return False, "invalid_mode"
        if st.st_uid != os.getuid():
            return False, "invalid_owner"
        for current, dirs, files in os.walk(home, topdown=False, followlinks=False):
            for name in (*dirs, *files):
                item = Path(current) / name
                if item.is_symlink():
                    return False, "symlink_detected"
                if item.name.lower() == "history.jsonl" or (item.name.lower().startswith("mcp") and item.name.lower().endswith(".json")):
                    return False, "forbidden_file"
        return True, "ok"
    except (OSError, ValueError):
        return False, "verification_error"


def cleanup_zc_slot_home(home_dir: Path, *, base_root: Path | None = None) -> None:
    """Удаляет HOME только после строгой проверки containment."""
    root = _checked_root(base_root or DEFAULT_ZC_SLOTS_ROOT)
    home = Path(home_dir)
    if not home.exists():
        return
    if home.is_symlink() or not _inside(home, root):
        raise ValueError("refusing cleanup outside base_root")
    for current, dirs, files in os.walk(home, topdown=False, followlinks=False):
        for name in (*files, *dirs):
            item = Path(current) / name
            if item.is_symlink() or item.is_file():
                item.unlink(missing_ok=True)
            elif item.is_dir():
                item.rmdir()
    home.rmdir()


def _flag(name: str, environ: Mapping[str, str] | None, config_path: Path | None) -> bool:
    cfg = config_path if config_path is not None else resolve_hub_dynamic_config(environ)
    return read_gigarc_bool(name, cfg, environ=environ, default=False)


def is_session_plane_enabled(environ: Mapping[str, str] | None = None, *, config_path: Path | None = None) -> bool:
    return _flag(_FLAG_NAMES[0], environ, config_path)


def is_zero_canon_keyed_resident_enabled(environ: Mapping[str, str] | None = None, *, config_path: Path | None = None) -> bool:
    return _flag(_FLAG_NAMES[1], environ, config_path)


def is_agy_drain_early_exit_enabled(environ: Mapping[str, str] | None = None, *, config_path: Path | None = None) -> bool:
    return _flag(_FLAG_NAMES[2], environ, config_path)


def is_agy_signed_directive_enabled(environ: Mapping[str, str] | None = None, *, config_path: Path | None = None) -> bool:
    return _flag(_FLAG_NAMES[3], environ, config_path)


def is_passthrough_canonical_affinity_enabled(environ: Mapping[str, str] | None = None, *, config_path: Path | None = None) -> bool:
    return _flag(_FLAG_NAMES[4], environ, config_path)
