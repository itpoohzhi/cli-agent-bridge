from __future__ import annotations

import json
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from core.runtime_env import env_bool
from core.zero_canon_fs import cleanup_ephemeral_zc_cwd
from core.zc_static_cwd_and_source import ensure_and_verify_static_codex_cwd

STATIC_CWD_ENABLED_KEY = "bridge_agy_zc_static_cwd_enabled"
STATIC_CWD_ENABLED_ENV = "BRIDGE_AGY_ZC_STATIC_CWD_ENABLED"
STATIC_CWD_PATH_ENV = "BRIDGE_AGY_ZC_STATIC_CWD_PATH"
DEFAULT_STATIC_DIR_NAME = "agy-zc-static-cwd"
_FALSY = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class ZeroCanonTurnCwd:
    """Turn-scoped CWD handle: static shared 0o555 dir or ephemeral turn-*."""

    path: Path
    ephemeral: bool

    def release(self) -> None:
        if self.ephemeral:
            cleanup_ephemeral_zc_cwd(self.path)


def is_agy_static_cwd_enabled(
    config_path: Path | None = None, *, environ: Mapping[str, str] | None = None
) -> bool:
    if os.geteuid() == 0 or os.getuid() == 0:
        return False
    env = os.environ if environ is None else environ
    if not env_bool(env, (STATIC_CWD_ENABLED_ENV,), True):
        return False
    if config_path is None or not config_path.is_file():
        return True
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    if not isinstance(raw, dict) or STATIC_CWD_ENABLED_KEY not in raw:
        return True
    val = raw[STATIC_CWD_ENABLED_KEY]
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() not in _FALSY
    return True


def resolve_agy_static_cwd_path(
    mgr: Any, *, environ: Mapping[str, str] | None = None
) -> Path:
    env = os.environ if environ is None else environ
    override = str(env.get(STATIC_CWD_PATH_ENV, "")).strip()
    if override:
        return Path(override)
    return mgr.zc_cwd.with_name(DEFAULT_STATIC_DIR_NAME)


def verify_parent_safe(target: Path, mgr: Any) -> None:
    if not str(target) or target.is_symlink():
        raise RuntimeError("zero_canon_static_cwd_unsafe:symlink")
    mgr._reject_overlap(target, "agy-zc-static-cwd")
    parent = target.parent
    if parent.is_symlink():
        raise RuntimeError("zero_canon_static_cwd_unsafe:parent_symlink")
    if not parent.exists():
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = os.lstat(parent)
    if not stat.S_ISDIR(st.st_mode):
        raise RuntimeError("zero_canon_static_cwd_unsafe:parent_not_dir")
    owned = st.st_uid == os.getuid() and (stat.S_IMODE(st.st_mode) & 0o022) == 0
    sticky = bool(st.st_mode & stat.S_ISVTX)
    if not owned and not sticky:
        raise RuntimeError("zero_canon_static_cwd_unsafe:parent_unsafe")


def _ensure_with_cold_race_retry(target: Path) -> Path:
    attempts = 4  # initial call plus up to 3 retries for the mkdir/fchmod race
    for attempt in range(attempts):
        try:
            return ensure_and_verify_static_codex_cwd(target)
        except RuntimeError as exc:
            if "mode_0o700" not in str(exc) or attempt == attempts - 1:
                raise
            time.sleep(0.005)
    raise RuntimeError("zero_canon_static_cwd_unsafe:mode_0o700")


def acquire_turn_cwd(
    mgr: Any,
    config_path: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> ZeroCanonTurnCwd:
    if not is_agy_static_cwd_enabled(config_path, environ=environ):
        return ZeroCanonTurnCwd(mgr.create_turn_zc_cwd(), ephemeral=True)
    target = resolve_agy_static_cwd_path(mgr, environ=environ)
    verify_parent_safe(target, mgr)
    verified = _ensure_with_cold_race_retry(target)
    return ZeroCanonTurnCwd(verified, ephemeral=False)
