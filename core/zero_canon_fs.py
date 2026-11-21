"""Общие файловые и GigaRC-примитивы для Universal Zero-Canon (`pol-env/3`)."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Final

_ENV_TRUE: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_ENV_FALSE: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})
_CFG_LOCK = threading.Lock()
_CFG_CACHE: dict[tuple[str, str], tuple[tuple[int, int, int], bool]] = {}


def read_gigarc_bool(
    flag_name: str,
    config_path: Path,
    *,
    environ: Mapping[str, str] | None = None,
    default: bool = False,
) -> bool:
    """Читает булев kill-switch из env или `dynamic_config.json` (fail-closed)."""
    env_val = str((os.environ if environ is None else environ).get(flag_name, "")).strip().lower()
    if env_val in _ENV_TRUE:
        return True
    if env_val in _ENV_FALSE:
        return False
    try:
        st = config_path.stat()
    except OSError:
        return default
    sig = (st.st_mtime_ns, st.st_size, st.st_ino)
    key = (str(config_path), flag_name)
    with _CFG_LOCK:
        hit = _CFG_CACHE.get(key)
        if hit is not None and hit[0] == sig:
            return hit[1]
    enabled = default
    try:
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(parsed, dict) and isinstance(parsed.get(flag_name), bool):
            enabled = bool(parsed[flag_name])
    except (OSError, ValueError):
        enabled = default
    with _CFG_LOCK:
        _CFG_CACHE[key] = (sig, enabled)
    return enabled


def ensure_private_dir(path: Path, mode: int = 0o700) -> None:
    """Создаёт приватный каталог без симлинков и выставляет права `mode`."""
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink directory: {path}")
    path.mkdir(mode=mode, parents=True, exist_ok=True)
    os.chmod(path, mode)


def remove_entry(path: Path) -> None:
    """Безопасно удаляет файл, симлинк или каталог, не переходя по симлинкам."""
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def write_atomic_0600(dst: Path, data: bytes) -> None:
    """Атомарно записывает байты в `dst` с правами `0o600` (O_CREAT|O_EXCL)."""
    if dst.is_symlink():
        dst.unlink()
    tmp = dst.parent / f".tmp_{dst.name}_{uuid.uuid4().hex}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp, 0o600)
        os.replace(tmp, dst)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def write_atomic_text_0600(dst: Path, text: str) -> None:
    """Атомарно записывает UTF-8 текст в `dst` с правами `0o600`."""
    write_atomic_0600(dst, text.encode("utf-8"))


def make_ephemeral_zc_cwd(parent: Path, prefix: str = "zc-cwd-") -> Path:
    """Создаёт уникальный пустой `cwd` (`0o700`) для одного Zero-Canon хода."""
    ensure_private_dir(parent, 0o700)
    turn_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=str(parent)))
    os.chmod(turn_dir, 0o700)
    return turn_dir.resolve()


def cleanup_ephemeral_zc_cwd(path: Path | None) -> None:
    """Удаляет одноразовый `cwd` хода."""
    if path is not None:
        shutil.rmtree(path, ignore_errors=True)
