from __future__ import annotations

import json
import logging
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
STATIC_CWD_FAIL_CLOSED_ENV = "BRIDGE_AGY_ZC_STATIC_CWD_FAIL_CLOSED"
DEFAULT_STATIC_DIR_NAME = "agy-zc-static-cwd"
_FALSY = frozenset({"0", "false", "no", "off"})
_TOLERATED_SYMLINKS = (Path("/tmp"), Path("/var"))
logger = logging.getLogger(__name__)


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
    # F-001: corrupt/unreadable/non-dict config must NEVER fail open.
    if os.geteuid() == 0 or os.getuid() == 0:
        return False
    env = os.environ if environ is None else environ
    if not env_bool(env, (STATIC_CWD_ENABLED_ENV,), True):
        return False
    if config_path is None or not config_path.exists():
        return True
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning(
            "agy_zc_static_cwd_config_unreadable path=%s reason=%s", config_path, exc
        )
        return False
    if not isinstance(raw, dict):
        logger.warning("agy_zc_static_cwd_config_invalid_root path=%s", config_path)
        return False
    if STATIC_CWD_ENABLED_KEY not in raw:
        return True
    val = raw[STATIC_CWD_ENABLED_KEY]
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() not in _FALSY
    logger.warning("agy_zc_static_cwd_config_bad_value path=%s", config_path)
    return False


def resolve_agy_static_cwd_path(
    mgr: Any, *, environ: Mapping[str, str] | None = None
) -> Path:
    env = os.environ if environ is None else environ
    override = str(env.get(STATIC_CWD_PATH_ENV, "")).strip()
    if override:
        return Path(override)
    return mgr.zc_cwd.with_name(DEFAULT_STATIC_DIR_NAME)


def verify_parent_safe(target: Path, mgr: Any) -> None:
    if not target.is_absolute():
        raise RuntimeError("zero_canon_static_cwd_unsafe:relative_path")
    if target.is_symlink():
        raise RuntimeError("zero_canon_static_cwd_unsafe:symlink")
    mgr._reject_overlap(target, "agy-zc-static-cwd")
    parent = target.parent
    if parent.is_symlink():
        raise RuntimeError("zero_canon_static_cwd_unsafe:parent_symlink")
    if not parent.exists():
        ancestor = parent
        while ancestor != ancestor.parent:
            if ancestor.is_symlink() and ancestor not in _TOLERATED_SYMLINKS:
                raise RuntimeError("zero_canon_static_cwd_unsafe:ancestor_symlink")
            ancestor = ancestor.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = os.lstat(parent)
    if not stat.S_ISDIR(st.st_mode):
        raise RuntimeError("zero_canon_static_cwd_unsafe:parent_not_dir")
    owned = st.st_uid == os.getuid() and (stat.S_IMODE(st.st_mode) & 0o022) == 0
    sticky = bool(st.st_mode & stat.S_ISVTX)
    if not owned and not sticky:
        raise RuntimeError("zero_canon_static_cwd_unsafe:parent_unsafe")


def _ensure_with_cold_race_retry(target: Path) -> Path:
    last_exc: RuntimeError = RuntimeError("zero_canon_static_cwd_unsafe:mode_0o700")
    for _ in range(4):  # initial call plus up to 3 mkdir/fchmod race retries
        try:
            return ensure_and_verify_static_codex_cwd(target)
        except RuntimeError as exc:
            last_exc = exc
            if "mode_0o700" not in str(exc):
                raise
            time.sleep(0.005)
    raise last_exc


def ensure_static_cwd(target: Path, mgr: Any) -> Path:
    """Strict fail-closed verification; never returns an unsafe path."""
    verify_parent_safe(target, mgr)
    return _ensure_with_cold_race_retry(target)


def acquire_turn_cwd(
    mgr: Any,
    config_path: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> ZeroCanonTurnCwd:
    if not is_agy_static_cwd_enabled(config_path, environ=environ):
        return ZeroCanonTurnCwd(mgr.create_turn_zc_cwd(), ephemeral=True)
    target = resolve_agy_static_cwd_path(mgr, environ=environ)
    env = os.environ if environ is None else environ
    try:
        verified = ensure_static_cwd(target, mgr)
    except RuntimeError as exc:
        if env_bool(env, (STATIC_CWD_FAIL_CLOSED_ENV,), False):
            raise
        # F-002: degrade loudly; never spawn in a compromised static dir and
        # never let one tampering event persistent-DoS the Zero-Canon service.
        logger.warning(
            "agy_zc_static_cwd_degraded path=%s reason=%s fallback=ephemeral",
            target,
            exc,
        )
        return ZeroCanonTurnCwd(mgr.create_turn_zc_cwd(), ephemeral=True)
    return ZeroCanonTurnCwd(verified, ephemeral=False)
