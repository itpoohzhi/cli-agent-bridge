"""Общие файловые и GigaRC-примитивы для Universal Zero-Canon (`pol-env/3`)."""

from __future__ import annotations

import errno
import json
import os
import shutil
import stat
import tempfile
import threading
import tomllib
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Final

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
    """Читает булев kill-switch с каноническим приоритетом `dynamic_config.json > env > default`."""
    try:
        st = config_path.stat()
    except OSError:
        st = None
    if st is not None:
        sig = (st.st_mtime_ns, st.st_size, st.st_ino)
        key = (str(config_path), flag_name)
        with _CFG_LOCK:
            hit = _CFG_CACHE.get(key)
            if hit is not None and hit[0] == sig:
                return hit[1]
        try:
            parsed = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                return default
            if flag_name in parsed:
                if not isinstance(parsed[flag_name], bool):
                    return default
                val = bool(parsed[flag_name])
                with _CFG_LOCK:
                    _CFG_CACHE[key] = (sig, val)
                return val
        except (OSError, ValueError):
            return default  # fail-closed при битом конфиге
    env_val = str((os.environ if environ is None else environ).get(flag_name, "")).strip().lower()
    if env_val in _ENV_TRUE:
        return True
    if env_val in _ENV_FALSE:
        return False
    return default


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


def read_regular_file_nofollow(path: str | Path) -> bytes:
    """Атомарно читает только обычный файл через `O_RDONLY|O_NOFOLLOW` и `fstat(S_ISREG)`."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(os.fspath(path), flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise OSError(errno.EINVAL, "Refusing non-regular file", os.fspath(path))
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            return handle.read()
    finally:
        if fd >= 0:
            os.close(fd)


def _read_optional_regular_nofollow(path: Path) -> bytes | None:
    try:
        return read_regular_file_nofollow(path)
    except FileNotFoundError:
        return None


def write_atomic_0600(dst: Path, data: bytes) -> None:
    """Атомарно создаёт новый файл `dst` (`0o600`, `O_CREAT|O_EXCL`), fail-closed при существующем/symlink."""
    tmp = dst.parent / f".tmp_{dst.name}_{uuid.uuid4().hex}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(os.fspath(tmp), flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            _ = handle.write(data)
        os.link(os.fspath(tmp), os.fspath(dst))
    finally:
        if fd >= 0:
            os.close(fd)
        tmp.unlink(missing_ok=True)


def write_atomic_text_0600(dst: Path, text: str) -> None:
    """Атомарно записывает UTF-8 текст в `dst` с правами `0o600`."""
    write_atomic_0600(dst, text.encode("utf-8"))


def replace_atomic_0600(dst: Path, data: bytes) -> None:
    """Атомарно создаёт или обновляет файл `dst` (`0o600`) через `dir_fd` (`O_DIRECTORY|O_NOFOLLOW`) и `os.replace`.

    Отклоняет symlink-родитель (`O_NOFOLLOW`) и предварительно существующий symlink/каталог (`ELOOP`/`EISDIR`).
    На POSIX `renameat(2)` не разыменовывает симлинк-назначение (запись в цель симлинка исключена), но не
    обещает race-free `ELOOP` при внешней подмене `dst` в окне между `lstat` и `os.replace` (для строгого
    fail-closed создания в одноразовых каталогах используется `write_atomic_0600`).
    """
    parent = dst.parent
    name = dst.name
    dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    dir_fd = os.open(os.fspath(parent), dir_flags)
    tmp_name = f".tmp_{name}_{uuid.uuid4().hex}"
    fd = -1
    tmp_created = False
    try:
        try:
            st = os.lstat(name, dir_fd=dir_fd)
        except FileNotFoundError:
            st = None
        if st is not None:
            if stat.S_ISLNK(st.st_mode):
                raise OSError(errno.ELOOP, "Refusing symlink destination", os.fspath(dst))
            if stat.S_ISDIR(st.st_mode):
                raise IsADirectoryError(errno.EISDIR, "Refusing directory destination", os.fspath(dst))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(tmp_name, flags, 0o600, dir_fd=dir_fd)
        tmp_created = True
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            _ = handle.write(data)
        try:
            st2 = os.lstat(name, dir_fd=dir_fd)
        except FileNotFoundError:
            st2 = None
        if st2 is not None:
            if stat.S_ISLNK(st2.st_mode):
                raise OSError(errno.ELOOP, "Refusing symlink destination", os.fspath(dst))
            if stat.S_ISDIR(st2.st_mode):
                raise IsADirectoryError(errno.EISDIR, "Refusing directory destination", os.fspath(dst))
        os.replace(tmp_name, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        tmp_created = False
    finally:
        if fd >= 0:
            os.close(fd)
        if tmp_created:
            try:
                os.unlink(tmp_name, dir_fd=dir_fd)
            except FileNotFoundError:
                pass
        os.close(dir_fd)


def replace_atomic_text_0600(dst: Path, text: str) -> None:
    """Атомарно создаёт или обновляет UTF-8 файл `dst` (`0o600`) через `replace_atomic_0600`."""
    replace_atomic_0600(dst, text.encode("utf-8"))
def prepare_codex_zero_canon_home(base_env: Mapping[str, str], root: str | Path) -> dict[str, str]:
    """Готовит приватный per-turn Codex Zero-Canon HOME (`0o700`), filtered config и nofollow auth (`0o600`)."""
    from core.codex_zero_canon_slim import apply_codex_zero_canon_slim
    from core.subbridge_zero_canon import dump_toml, filter_codex_config
    from core.zc_static_cwd_and_source import is_source_header_enabled, resolve_codex_source_tag
    zc_root = Path(root)
    dst_codex = zc_root / ".codex"
    for directory in (zc_root, dst_codex, zc_root / "cwd"):
        ensure_private_dir(directory, 0o700)
    src_home = base_env.get("HOME", "")
    src_codex_raw = base_env.get("CODEX_HOME") or (f"{src_home}/.codex" if src_home else "")
    src_codex = Path(src_codex_raw) if src_codex_raw else None
    raw_cfg: dict[str, object] = {}
    if src_codex is not None:
        cfg_bytes = _read_optional_regular_nofollow(src_codex / "config.toml")
        if cfg_bytes is not None:
            raw_cfg = tomllib.loads(cfg_bytes.decode("utf-8"))
        auth_bytes = _read_optional_regular_nofollow(src_codex / "auth.json")
        if auth_bytes is not None:
            write_atomic_0600(dst_codex / "auth.json", auth_bytes)
    src_tag = resolve_codex_source_tag(is_zero_canon=True) if is_source_header_enabled(base_env) else None
    filtered_cfg = apply_codex_zero_canon_slim(filter_codex_config(raw_cfg, source_tag=src_tag), base_env)
    write_atomic_text_0600(dst_codex / "config.toml", dump_toml(filtered_cfg))
    cleaned = sanitize_zero_canon_env(base_env, zc_root)
    cleaned["CODEX_HOME"] = str(dst_codex)
    cleaned["BRIDGE_ZERO_CANON"] = "1"
    return cleaned


def make_ephemeral_zc_cwd(parent: Path, prefix: str = "zc-cwd-") -> Path:
    """Создаёт уникальный пустой `cwd` (`0o700`) для одного Zero-Canon хода."""
    ensure_private_dir(parent, 0o700)
    turn_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=str(parent)))
    os.chmod(turn_dir, 0o700)
    return turn_dir.resolve()


_SECRET_ENV_EXACT: Final[frozenset[str]] = frozenset({"BRIDGE_KEY", "BRIDGE_API_KEY", "INTERNAL_SERVICE_KEY", "META_API_KEY"})
_SECRET_ENV_SUFFIXES: Final[tuple[str, ...]] = ("_BRIDGE_KEY", "_SERVICE_KEY")


def sanitize_zero_canon_env(base_env: Mapping[str, str], root: str | Path) -> dict[str, str]:
    """Удаляет секреты хаба/моста и изолирует `XDG_{CONFIG,DATA,CACHE,STATE}_HOME` в `root`."""
    zc_root = Path(root)
    cleaned = {
        k: v
        for k, v in base_env.items()
        if k not in _SECRET_ENV_EXACT and not k.endswith(_SECRET_ENV_SUFFIXES)
    }
    cleaned["HOME"] = str(zc_root)
    cleaned["XDG_CONFIG_HOME"] = str(zc_root / ".config")
    cleaned["XDG_DATA_HOME"] = str(zc_root / ".local" / "share")
    cleaned["XDG_CACHE_HOME"] = str(zc_root / ".cache")
    cleaned["XDG_STATE_HOME"] = str(zc_root / ".local" / "state")
    return cleaned


def resolve_hub_dynamic_config(environ: Mapping[str, str] | None = None) -> Path:
    """Путь к `dynamic_config.json` хаба с учётом `environ['BRIDGE_DYNAMIC_CONFIG_PATH']`/`HOME`."""
    env = os.environ if environ is None else environ
    explicit = env.get("BRIDGE_DYNAMIC_CONFIG_PATH")
    if explicit:
        return Path(explicit)
    home = env.get("HOME") or str(Path.home())
    return Path(home) / ".config" / "cli-agent-bridge" / "dynamic_config.json"


def cleanup_ephemeral_zc_cwd(path: Path | None) -> None:
    """Удаляет одноразовый `cwd` хода."""
    if path is not None:
        shutil.rmtree(path, ignore_errors=True)


def prepare_opencode_zc_env(base_env: Mapping[str, str], env: dict[str, str], root: str) -> dict[str, str]:
    """Готовит изолированные HOME/XDG/cwd и `OPENCODE_CONFIG_CONTENT` для OpenCode."""
    from core.subbridge_zero_canon import filter_opencode_config

    zc_root = Path(root)
    zc_cfg, zc_oc_cfg = zc_root / ".config", zc_root / ".config" / "opencode"
    zc_data, zc_data_oc, zc_cwd = zc_root / ".local" / "share", zc_root / ".local" / "share" / "opencode", zc_root / "cwd"
    for directory in (zc_root, zc_cfg, zc_oc_cfg, zc_root / ".local", zc_data, zc_data_oc, zc_cwd):
        ensure_private_dir(directory, 0o700)
    src_data = Path(base_env.get("XDG_DATA_HOME") or f"{base_env.get('HOME', '')}/.local/share")
    auth_src = src_data / "opencode" / "auth.json"
    if auth_src.is_file() and not auth_src.is_symlink():
        write_atomic_0600(zc_data_oc / "auth.json", auth_src.read_bytes())
    raw_cfg: dict[str, object] = {}
    raw_str = base_env.get("OPENCODE_CONFIG_CONTENT", "")
    if raw_str:
        try:
            parsed = json.loads(raw_str)
            if isinstance(parsed, dict):
                raw_cfg = parsed
        except (ValueError, TypeError):
            pass
    env.update(
        {
            "HOME": str(zc_root),
            "XDG_CONFIG_HOME": str(zc_cfg),
            "XDG_DATA_HOME": str(zc_data),
            "OPENCODE_CONFIG_CONTENT": json.dumps(filter_opencode_config(raw_cfg), ensure_ascii=False),
            "BRIDGE_ZERO_CANON": "1",
        }
    )
    env.pop("OPENCODE_CONFIG", None)
    return env


def acquire_turn_lock(lock_path: str, handle: object) -> object:
    """Берёт эксклюзивный flock на `lock_path` с метаданными процесса."""
    import fcntl

    lock_file = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        pid = getattr(handle, "pid", 0)
        payload = {"pid": pid, "pgid": getattr(handle, "_pgid", pid), "start_time": getattr(handle, "_start_time", "")}
        lock_file.write(json.dumps(payload, separators=(",", ":")))
        lock_file.flush()
    except BaseException:
        lock_file.close()
        raise
    return lock_file


def cleanup_turn_sandbox(turn_sandbox: str, lock_file: IO[str] | None, lock_path: str | None) -> None:
    """Удаляет песочницу хода и освобождает lock-файл."""
    import fcntl
    from contextlib import suppress

    with suppress(FileNotFoundError):
        shutil.rmtree(turn_sandbox)
    if lock_file is not None:
        with suppress(OSError):
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        with suppress(OSError):
            lock_file.close()
    if lock_path is not None:
        with suppress(FileNotFoundError):
            os.unlink(lock_path)
