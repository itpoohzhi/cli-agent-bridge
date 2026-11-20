"""Изолированный Zero-Canon рантайм и GigaRC kill-switch для opencode-zen-bridge."""

from __future__ import annotations

import contextvars
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import core.proc_groups as _proc_groups  # noqa: E402
from core.subbridge_zero_canon import (  # noqa: E402
    OPENCODE_ZERO_CANON_FLAG, filter_opencode_config, is_zero_canon_profile, review_profile_from_headers,
)

DEFAULT_CONFIG_PATH: Final[Path] = Path(__file__).resolve().parents[2] / "dynamic_config.json"
_ENV_TRUE: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_ENV_FALSE: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})
_FORBIDDEN_NAMES: Final[tuple[str, ...]] = ("AGENTS.md", "CLAUDE.md", ".opencode", "opencode.json", "plugins", "mcp")
_CFG_LOCK, _PREP_LOCK = threading.Lock(), threading.Lock()
_CFG_CACHE: dict[str, tuple[tuple[int, int, int], bool]] = {}


@dataclass(frozen=True, slots=True)
class OpenCodeZeroCanonContext:
    """Контекст активного Zero-Canon хода для opencode-zen-bridge."""

    enabled: bool
    zc_home: Path
    zc_xdg_config: Path
    zc_cwd: Path


_ACTIVE_ZC: contextvars.ContextVar[OpenCodeZeroCanonContext | None] = contextvars.ContextVar("opencode_zero_canon_ctx", default=None)


def is_opencode_zero_canon_enabled(config_path: Path | None = None, *, environ: Mapping[str, str] | None = None) -> bool:
    """GigaRC kill-switch `OPENCODE_ZERO_CANON_ENABLED` (дефолт False, fail-closed)."""
    env_val = str((os.environ if environ is None else environ).get(OPENCODE_ZERO_CANON_FLAG, "")).strip().lower()
    if env_val in _ENV_TRUE:
        return True
    if env_val in _ENV_FALSE:
        return False
    path = DEFAULT_CONFIG_PATH if config_path is None else Path(config_path)
    try:
        st = path.stat()
    except OSError:
        return False
    sig, key = (st.st_mtime_ns, st.st_size, st.st_ino), str(path)
    with _CFG_LOCK:
        if (hit := _CFG_CACHE.get(key)) is not None and hit[0] == sig:
            return hit[1]
    try:
        enabled = _parse_json_dict(path.read_text(encoding="utf-8")).get(OPENCODE_ZERO_CANON_FLAG) is True
    except OSError:
        enabled = False
    with _CFG_LOCK:
        _CFG_CACHE[key] = (sig, enabled)
    return enabled


def _write_atomic_0600(dst: Path, data: bytes) -> None:
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


def _remove_entry(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _ensure_private_dir(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink directory: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def _parse_json_dict(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw) if raw else {}
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def prepare_opencode_zero_canon_dirs(
    workspace: Path, *, real_home: Path | None = None, source_xdg_data: Path | None = None
) -> OpenCodeZeroCanonContext:
    """Готовит изолированные HOME/XDG_CONFIG_HOME и пустой `cwd` для OpenCode Zen."""
    src_home = (real_home if real_home is not None else Path.home()).resolve()
    zc_home, zc_cwd = workspace / "opencode-home-zc", workspace / "opencode-zc-cwd"
    if zc_home.is_symlink() or zc_cwd.is_symlink():
        raise RuntimeError("Refusing symlink Zero-Canon target directory")
    if zc_home.resolve() == src_home or zc_home.resolve() in src_home.parents:
        raise RuntimeError(f"Invalid opencode Zero-Canon HOME overlaps real HOME: {zc_home}")
    with _PREP_LOCK:
        zc_xdg_cfg, zc_oc_cfg = zc_home / ".config", zc_home / ".config" / "opencode"
        zc_data_oc = zc_home / ".local" / "share" / "opencode"
        for d in (zc_home, zc_xdg_cfg, zc_oc_cfg, zc_home / ".local", zc_home / ".local" / "share", zc_data_oc, zc_cwd):
            _ensure_private_dir(d)
        auth_src = (source_xdg_data or src_home / ".local" / "share") / "opencode" / "auth.json"
        if auth_src.is_file() and not auth_src.is_symlink():
            _write_atomic_0600(zc_data_oc / "auth.json", auth_src.read_bytes())
        for base in (zc_home, zc_xdg_cfg, zc_oc_cfg):
            for name in _FORBIDDEN_NAMES:
                _remove_entry(base / name)
        for entry in list(zc_cwd.iterdir()):
            _remove_entry(entry)
        return OpenCodeZeroCanonContext(True, zc_home.resolve(), zc_xdg_cfg.resolve(), zc_cwd.resolve())


@contextmanager
def zero_canon_scope(
    headers: object, config_path: Path | None = None, *, workspace: Path | None = None,
    real_home: Path | None = None, environ: Mapping[str, str] | None = None,
) -> Iterator[OpenCodeZeroCanonContext | None]:
    """Привязывает Zero-Canon контекст к текущему HTTP-запросу (или `None`)."""
    active = is_zero_canon_profile(review_profile_from_headers(headers)) and is_opencode_zero_canon_enabled(config_path, environ=environ)
    ctx: OpenCodeZeroCanonContext | None = None
    if active:
        env = os.environ if environ is None else environ
        src_home = real_home if real_home is not None else Path(env.get("HOME") or str(Path.home()))
        xdg_data = env.get("XDG_DATA_HOME")
        root = workspace if workspace is not None else Path(tempfile.gettempdir()) / "opencode-zero-canon"
        ctx = prepare_opencode_zero_canon_dirs(root, real_home=src_home, source_xdg_data=Path(xdg_data) if xdg_data else None)
    token = _ACTIVE_ZC.set(ctx)
    try:
        yield ctx
    finally:
        _ACTIVE_ZC.reset(token)


def apply_zero_canon_env(env: Mapping[str, str], *, ctx: OpenCodeZeroCanonContext | None = None) -> dict[str, str]:
    """Применяет Zero-Canon изоляцию env с обязательным `permission: {'*': 'ask'}`."""
    result = dict(env)
    active = ctx if ctx is not None else _ACTIVE_ZC.get()
    if active is None or not active.enabled:
        return result
    filtered = filter_opencode_config(_parse_json_dict(result.get("OPENCODE_CONFIG_CONTENT", "")))
    result.update({"HOME": str(active.zc_home), "XDG_CONFIG_HOME": str(active.zc_xdg_config), "XDG_DATA_HOME": str(active.zc_home / ".local" / "share"), "OPENCODE_CONFIG_CONTENT": json.dumps(filtered, ensure_ascii=False), "BRIDGE_ZERO_CANON": "1"})
    result.pop("OPENCODE_CONFIG", None)
    return result


def apply_serve_zero_canon_env(
    env: Mapping[str, str], default_config_raw: str, permission_effect: str, *, ctx: OpenCodeZeroCanonContext | None = None
) -> dict[str, str]:
    """Финализирует `OPENCODE_CONFIG_CONTENT` для serve (в Zero-Canon всегда `permission={'*': 'ask'}`)."""
    result = dict(env)
    config = _parse_json_dict(result.get("OPENCODE_CONFIG_CONTENT") or default_config_raw)
    config["permission"] = {"*": permission_effect}
    result["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, ensure_ascii=False)
    return apply_zero_canon_env(result, ctx=ctx)


class _ZeroCanonSpawnProxy:
    """Прозрачная обёртка `core.proc_groups.spawn_registered` для Zero-Canon cwd/env."""

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.Popen[Any]:
        if (active := _ACTIVE_ZC.get()) is not None and active.enabled:
            kwargs = {**kwargs, "cwd": str(active.zc_cwd), "env": apply_zero_canon_env(os.environ if kwargs.get("env") is None else kwargs["env"], ctx=active)}
        return _proc_groups.spawn_registered(cmd, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(_proc_groups.spawn_registered, name)


spawn_registered = _ZeroCanonSpawnProxy()
