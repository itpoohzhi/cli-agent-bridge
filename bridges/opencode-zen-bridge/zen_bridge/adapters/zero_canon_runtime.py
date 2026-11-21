"""Изолированный Zero-Canon рантайм и GigaRC kill-switch для opencode-zen-bridge."""

from __future__ import annotations

import contextvars
import json
import os
import subprocess
import sys
import tempfile
import threading
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
    OPENCODE_ZERO_CANON_FLAG,
    filter_opencode_config,
    is_zero_canon_profile,
    review_profile_from_headers,
)
from core.zero_canon_fs import (  # noqa: E402
    cleanup_ephemeral_zc_cwd,
    ensure_private_dir,
    make_ephemeral_zc_cwd,
    read_gigarc_bool,
    remove_entry,
    sanitize_zero_canon_env,
    write_atomic_0600,
)

DEFAULT_CONFIG_PATH: Final[Path] = Path(__file__).resolve().parents[2] / "dynamic_config.json"
_FORBIDDEN_NAMES: Final[tuple[str, ...]] = ("AGENTS.md", "CLAUDE.md", ".opencode", "opencode.json", "plugins", "mcp")
_PREP_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class OpenCodeZeroCanonContext:
    """Контекст активного Zero-Canon хода для opencode-zen-bridge."""

    enabled: bool
    zc_home: Path
    zc_xdg_config: Path
    zc_cwd: Path


_ACTIVE_ZC: contextvars.ContextVar[OpenCodeZeroCanonContext | None] = contextvars.ContextVar(
    "opencode_zero_canon_ctx", default=None
)


def is_opencode_zero_canon_enabled(
    config_path: Path | None = None, *, environ: Mapping[str, str] | None = None
) -> bool:
    """GigaRC kill-switch `OPENCODE_ZERO_CANON_ENABLED` (дефолт False, fail-closed)."""
    return read_gigarc_bool(
        OPENCODE_ZERO_CANON_FLAG,
        DEFAULT_CONFIG_PATH if config_path is None else Path(config_path),
        environ=environ,
        default=False,
    )


def _parse_json_dict(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw) if raw else {}
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def prepare_opencode_zero_canon_dirs(
    workspace: Path,
    *,
    real_home: Path | None = None,
    source_xdg_data: Path | None = None,
    turn_cwd: Path | None = None,
) -> OpenCodeZeroCanonContext:
    """Готовит изолированные HOME/XDG_CONFIG_HOME и пустой `cwd` для OpenCode Zen."""
    src_home = (real_home if real_home is not None else Path.home()).resolve()
    zc_home = workspace / "opencode-home-zc"
    zc_cwd = turn_cwd if turn_cwd is not None else make_ephemeral_zc_cwd(workspace / "opencode-zc-cwd", prefix="turn-")
    if zc_home.is_symlink() or zc_cwd.is_symlink():
        raise RuntimeError("Refusing symlink Zero-Canon target directory")
    if zc_home.resolve() == src_home or zc_home.resolve() in src_home.parents:
        raise RuntimeError(f"Invalid opencode Zero-Canon HOME overlaps real HOME: {zc_home}")
    with _PREP_LOCK:
        zc_xdg_cfg, zc_oc_cfg = zc_home / ".config", zc_home / ".config" / "opencode"
        zc_data_oc = zc_home / ".local" / "share" / "opencode"
        for d in (zc_home, zc_xdg_cfg, zc_oc_cfg, zc_home / ".local", zc_home / ".local" / "share", zc_data_oc, zc_cwd):
            ensure_private_dir(d, 0o700)
        auth_src = (source_xdg_data or src_home / ".local" / "share") / "opencode" / "auth.json"
        if auth_src.is_file() and not auth_src.is_symlink():
            write_atomic_0600(zc_data_oc / "auth.json", auth_src.read_bytes())
        for base in (zc_home, zc_xdg_cfg, zc_oc_cfg):
            for name in _FORBIDDEN_NAMES:
                remove_entry(base / name)
        return OpenCodeZeroCanonContext(True, zc_home.resolve(), zc_xdg_cfg.resolve(), zc_cwd.resolve())


@contextmanager
def zero_canon_scope(
    headers: object,
    config_path: Path | None = None,
    *,
    workspace: Path | None = None,
    real_home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Iterator[OpenCodeZeroCanonContext | None]:
    """Привязывает Zero-Canon контекст с уникальным per-request `zc_cwd`."""
    active = is_zero_canon_profile(review_profile_from_headers(headers)) and is_opencode_zero_canon_enabled(
        config_path, environ=environ
    )
    ctx: OpenCodeZeroCanonContext | None = None
    turn_cwd: Path | None = None
    if active:
        env = os.environ if environ is None else environ
        src_home = real_home if real_home is not None else Path(env.get("HOME") or str(Path.home()))
        xdg_data = env.get("XDG_DATA_HOME")
        root = workspace if workspace is not None else Path(tempfile.gettempdir()) / "opencode-zero-canon"
        turn_cwd = make_ephemeral_zc_cwd(root / "opencode-zc-cwd", prefix="turn-")
        ctx = prepare_opencode_zero_canon_dirs(
            root,
            real_home=src_home,
            source_xdg_data=Path(xdg_data) if xdg_data else None,
            turn_cwd=turn_cwd,
        )
    token = _ACTIVE_ZC.set(ctx)
    try:
        yield ctx
    finally:
        _ACTIVE_ZC.reset(token)
        cleanup_ephemeral_zc_cwd(turn_cwd)


def apply_zero_canon_env(
    env: Mapping[str, str], *, ctx: OpenCodeZeroCanonContext | None = None
) -> dict[str, str]:
    """Применяет Zero-Canon изоляцию env, XDG_* и секретов с `permission: {'*': 'ask'}`."""
    active = ctx if ctx is not None else _ACTIVE_ZC.get()
    if active is None or not active.enabled:
        return dict(env)
    filtered = filter_opencode_config(_parse_json_dict(env.get("OPENCODE_CONFIG_CONTENT", "")))
    result = sanitize_zero_canon_env(env, active.zc_home)
    result.update(
        {
            "XDG_CONFIG_HOME": str(active.zc_xdg_config),
            "OPENCODE_CONFIG_CONTENT": json.dumps(filtered, ensure_ascii=False),
            "BRIDGE_ZERO_CANON": "1",
        }
    )
    result.pop("OPENCODE_CONFIG", None)
    return result


def apply_serve_zero_canon_env(
    env: Mapping[str, str],
    default_config_raw: str,
    permission_effect: str,
    *,
    ctx: OpenCodeZeroCanonContext | None = None,
) -> dict[str, str]:
    """Финализирует `OPENCODE_CONFIG_CONTENT` для serve (не ослабляет `deny` до `ask`)."""
    result = dict(env)
    config = _parse_json_dict(result.get("OPENCODE_CONFIG_CONTENT") or default_config_raw)
    config["permission"] = {"*": permission_effect}
    result["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, ensure_ascii=False)
    out = apply_zero_canon_env(result, ctx=ctx)
    if permission_effect == "deny" and out.get("BRIDGE_ZERO_CANON") == "1":
        strict_cfg = _parse_json_dict(out.get("OPENCODE_CONFIG_CONTENT", ""))
        strict_cfg["permission"] = {"*": "deny"}
        out["OPENCODE_CONFIG_CONTENT"] = json.dumps(strict_cfg, ensure_ascii=False)
    return out


class _ZeroCanonSpawnProxy:
    """Прозрачная обёртка `core.proc_groups.spawn_registered` для Zero-Canon cwd/env."""

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.Popen[Any]:
        if (active := _ACTIVE_ZC.get()) is not None and active.enabled:
            kwargs = {
                **kwargs,
                "cwd": str(active.zc_cwd),
                "env": apply_zero_canon_env(os.environ if kwargs.get("env") is None else kwargs["env"], ctx=active),
            }
        return _proc_groups.spawn_registered(cmd, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(_proc_groups.spawn_registered, name)


spawn_registered = _ZeroCanonSpawnProxy()
