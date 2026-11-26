"""Чистый per-slot `CODEX_HOME` и нейтральный fallback-CWD для Codex в Standard-режиме."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import atexit
import os
import re
import shutil
import tempfile
import threading
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from core.subbridge_zero_canon import dump_toml
from core.zero_canon_fs import (
    ensure_private_dir,
    read_gigarc_bool,
    read_regular_file_nofollow,
    replace_atomic_0600,
    resolve_hub_dynamic_config,
    sanitize_zero_canon_env,
)

CODEX_STD_CLEAN_HOME_FLAG: Final[str] = "BRIDGE_CODEX_STD_CLEAN_HOME_ENABLED"
CODEX_STD_NEUTRAL_CWD_FLAG: Final[str] = "BRIDGE_CODEX_STD_NEUTRAL_CWD_ENABLED"
CODEX_USAGE_FRAME_GUARD_FLAG: Final[str] = "BRIDGE_CODEX_USAGE_FRAME_GUARD_ENABLED"

# Секции хостового config.toml, которые нельзя протаскивать в Standard clean HOME на любой глубине.
_DENIED_SECTIONS: Final[frozenset[str]] = frozenset({"mcp_servers", "plugins", "notify", "hooks"})
_PID_DIR_RE: Final[re.Pattern[str]] = re.compile(r"^pid-(\d+)-")
_OWNED_LOCK: Final[threading.Lock] = threading.Lock()
_OWNED_DIRS: set[Path] = set()
_ATEXIT_STATE: dict[str, bool] = {"registered": False}


def _flag(name: str, environ: Mapping[str, str] | None, config_path: Path | None) -> bool:
    path = config_path if config_path is not None else resolve_hub_dynamic_config(environ)
    return read_gigarc_bool(name, path, environ=environ, default=False)


def is_codex_std_clean_home_enabled(
    environ: Mapping[str, str] | None = None, config_path: Path | None = None
) -> bool:
    """Kill-switch чистого `CODEX_HOME` Standard-режима (default `False`)."""
    return _flag(CODEX_STD_CLEAN_HOME_FLAG, environ, config_path)


def is_codex_std_neutral_cwd_enabled(
    environ: Mapping[str, str] | None = None, config_path: Path | None = None
) -> bool:
    """Kill-switch пустого per-slot fallback-CWD (default `False`)."""
    return _flag(CODEX_STD_NEUTRAL_CWD_FLAG, environ, config_path)


def is_codex_usage_frame_guard_enabled(
    environ: Mapping[str, str] | None = None, config_path: Path | None = None
) -> bool:
    """Kill-switch guard-а ghost-usage кадров чужого thread/turn (default `False`)."""
    return _flag(CODEX_USAGE_FRAME_GUARD_FLAG, environ, config_path)


def _clean_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _clean_value(v) for k, v in value.items() if str(k) not in _DENIED_SECTIONS}
    if isinstance(value, list):
        return [_clean_value(item) for item in value]
    return value


def filter_codex_standard_config(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Копия `config.toml` без `mcp_servers`/`plugins`/`notify`/`hooks` на любой глубине (в т.ч. `profiles.*`).

    `project_doc_max_bytes` не трогается: явный `extra_body.cwd` сохраняет проектный `AGENTS.md`.
    """
    if not isinstance(raw, Mapping):
        raise TypeError(f"Expected a mapping, got {type(raw).__name__}")
    result: dict[str, Any] = _clean_value(raw)
    features = result.get("features")
    result["features"] = {**features, "hooks": False} if isinstance(features, dict) else {"hooks": False}
    return result


def _owned_cleanup() -> None:
    with _OWNED_LOCK:
        owned = list(_OWNED_DIRS)
        _OWNED_DIRS.clear()
    for path in owned:
        cleanup_std_home_dir(path)


def _register_owned(path: Path) -> None:
    with _OWNED_LOCK:
        _OWNED_DIRS.add(path)
        if not _ATEXIT_STATE["registered"]:
            _ATEXIT_STATE["registered"] = True
            atexit.register(_owned_cleanup)


def _pid_is_dead(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return False
    return False


def cleanup_stale_pid_homes(base_dir: str | Path) -> None:
    """Удаляет `pid-<мёртвый_pid>-*` под `base_dir`; живые PID и симлинки не трогает."""
    base = Path(base_dir)
    try:
        entries = list(base.iterdir())
    except OSError:
        return
    for entry in entries:
        match = _PID_DIR_RE.match(entry.name)
        if match is None or entry.is_symlink() or not entry.is_dir():
            continue
        if _pid_is_dead(int(match.group(1))):
            cleanup_std_home_dir(entry)


def _retry_after_chmod(func: Any, path: str, _exc: BaseException) -> None:
    """`rmtree`-обработчик: открывает права на каталог (не следуя симлинкам) и повторяет удаление."""
    for target in (os.path.dirname(path), path):
        try:
            if not os.path.islink(target):
                os.chmod(target, 0o700)
        except OSError:
            pass
    try:
        func(path)
    except OSError:
        pass


def cleanup_std_home_dir(path: str | Path | None) -> None:
    """Безопасно удаляет каталог слота, не следуя по симлинкам."""
    if path is None:
        return
    target = Path(path)
    with _OWNED_LOCK:
        _OWNED_DIRS.discard(target)
    if target.is_symlink():
        target.unlink(missing_ok=True)
        return
    if not target.is_dir():
        return
    try:
        os.chmod(target, 0o700)
    except OSError:
        pass
    shutil.rmtree(target, onexc=_retry_after_chmod)


def _owned_base_dir() -> Path:
    base = Path(tempfile.gettempdir()) / f"codex-std-homes-{os.getuid()}"
    ensure_private_dir(base, 0o700)
    if base.stat().st_uid != os.getuid():
        raise RuntimeError(f"Refusing foreign-owned directory: {base}")
    return base


def _stable_owned_dir(suffix: str) -> Path:
    """Стабильный process-scoped приватный `pid-<pid>-<suffix>` под базой (идемпотентен в рамках процесса).

    Dead-PID GC запускается при первом создании; повторные вызовы возвращают тот же путь
    (удалённый извне каталог безопасно пересоздаётся с `0o700`).
    """
    base = _owned_base_dir()
    path = base / f"pid-{os.getpid()}-{suffix}"
    if not path.exists():
        cleanup_stale_pid_homes(base)
    with _OWNED_LOCK:
        ensure_private_dir(path, 0o700)
        if path.is_symlink() or path.stat().st_uid != os.getuid():
            raise RuntimeError(f"Refusing unsafe directory: {path}")
    _register_owned(path)
    return path


def create_neutral_fallback_cwd() -> str:
    """Возвращает стабильный пустой `0o700` каталог (без `AGENTS.md`) fallback-CWD процесса.

    Путь постоянен между вызовами, чтобы `SlotAffinityKey.cwd_norm` не менялся между ходами.
    """
    return str(_stable_owned_dir("neutral-cwd"))


def _read_optional(path: Path) -> bytes | None:
    """Читает обычный файл без следования по симлинкам; симлинк/не-файл — fail-closed `OSError`."""
    try:
        return read_regular_file_nofollow(path)
    except FileNotFoundError:
        return None


def _source_codex_dir(base_env: Mapping[str, str]) -> Path | None:
    src_home = base_env.get("HOME", "")
    raw = base_env.get("CODEX_HOME") or (f"{src_home}/.codex" if src_home else "")
    return Path(raw) if raw else None


def _sync_codex_files(src_codex: Path | None, dst_codex: Path, raw_cfg_out: dict[str, Any]) -> None:
    """Читает хостовые `config.toml`/`auth.json` (без симлинков) и атомарно обновляет копии слота."""
    cfg_bytes = _read_optional(src_codex / "config.toml") if src_codex is not None else None
    auth_bytes = _read_optional(src_codex / "auth.json") if src_codex is not None else None
    if cfg_bytes is not None:
        raw_cfg_out.update(tomllib.loads(cfg_bytes.decode("utf-8")))
    cfg_text = dump_toml(filter_codex_standard_config(raw_cfg_out))
    with _OWNED_LOCK:
        if auth_bytes is not None:
            replace_atomic_0600(dst_codex / "auth.json", auth_bytes)
        else:
            (dst_codex / "auth.json").unlink(missing_ok=True)
        replace_atomic_0600(dst_codex / "config.toml", cfg_text.encode("utf-8"))


def prepare_codex_std_home(base_env: Mapping[str, str], root: str | Path | None = None) -> dict[str, str]:
    """Готовит чистый `HOME`/`CODEX_HOME` (`0o700`): `auth.json` (`0o600`) и filtered `config.toml`.

    Без `root` используется стабильный process-scoped каталог (нет утечки каталогов на warm-ходах);
    файлы обновляются при каждом вызове. Симлинк на `auth.json`/`config.toml` — fail-closed.
    """
    home_root = Path(root) if root is not None else _stable_owned_dir("std-home")
    dst_codex = home_root / ".codex"
    for directory in (home_root, dst_codex, home_root / "cwd"):
        ensure_private_dir(directory, 0o700)
    _sync_codex_files(_source_codex_dir(base_env), dst_codex, {})
    env = sanitize_zero_canon_env(base_env, home_root)
    env["CODEX_HOME"] = str(dst_codex)
    env["BRIDGE_CODEX_STD_CLEAN_HOME"] = "1"
    return env
