"""Static read-only Zero-Canon CWD (AD-003) and allowlisted Codex source tag helper."""

from __future__ import annotations

import os
import stat
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from core.runtime_env import env_bool

DEFAULT_STATIC_CODEX_CWD: Final[str] = "/private/tmp/zc-codex-empty-cwd"
STATIC_CWD_ENABLED_ENV: Final[str] = "BRIDGE_ZC_STATIC_CWD_ENABLED"
STATIC_CWD_PATH_ENV: Final[str] = "BRIDGE_ZC_STATIC_CWD_PATH"
SOURCE_HEADER_ENABLED_ENV: Final[str] = "BRIDGE_CODEX_SOURCE_HEADER_ENABLED"

CODEX_PROTOCOLS: Final[frozenset[str]] = frozenset(
    {"codex-app-server", "codex-app-server-v2", "codex_app_server", "codex_app_server_v2"}
)
CODEX_BACKEND_IDS: Final[frozenset[str]] = frozenset(
    {"codex", "codex-app-server", "codex-app-server-v2"}
)

CODEX_SOURCE_TAG_DEFAULT: Final[str] = "bridge:unknown"
ALLOWED_CODEX_SOURCE_TAGS: Final[frozenset[str]] = frozenset(
    {
        "bridge:zero-canon",
        "bridge:standard",
        "bridge:arl",
        "bridge:council",
        "bridge:coder",
        "bridge:architect",
        "bridge:analyst",
        "bridge:reviewer",
        "bridge:verifier",
        "bridge:explorer",
        "bridge:panel",
        "bridge:cel",
        "bridge:unknown",
    }
)
_SOURCE_HEADERS: Final[tuple[str, ...]] = (
    "x-bridge-source",
    "x-codex-source",
    "x-source",
    "x-bridge-role",
)
_OPEN_DIR_FLAGS: Final[int] = (
    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
)
_CREATE_LOCK = threading.Lock()


def is_static_cwd_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return True unless BRIDGE_ZC_STATIC_CWD_ENABLED is explicitly falsy."""
    env = os.environ if environ is None else environ
    return env_bool(env, (STATIC_CWD_ENABLED_ENV,), True)


def is_source_header_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return True unless BRIDGE_CODEX_SOURCE_HEADER_ENABLED is explicitly falsy."""
    env = os.environ if environ is None else environ
    return env_bool(env, (SOURCE_HEADER_ENABLED_ENV,), True)


def _lookup_header_ci(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, val in headers.items():
        if str(key).strip().lower() == target:
            text = str(val).strip()
            if text:
                return text
    return None


def _normalize_allowlisted_tag(raw: str) -> str:
    norm = raw.strip().lower()
    if not norm or len(norm) > 64 or any(ch.isspace() for ch in norm):
        return CODEX_SOURCE_TAG_DEFAULT
    candidate = norm if norm.startswith("bridge:") else f"bridge:{norm}"
    return candidate if candidate in ALLOWED_CODEX_SOURCE_TAGS else CODEX_SOURCE_TAG_DEFAULT


def resolve_codex_source_tag(
    headers: Mapping[str, str] | None = None,
    *,
    is_zero_canon: bool = False,
) -> str:
    """Return a strictly allowlisted low-cardinality Codex source tag (never raw headers)."""
    if headers:
        for hdr_name in _SOURCE_HEADERS:
            raw = _lookup_header_ci(headers, hdr_name)
            if raw is not None:
                return _normalize_allowlisted_tag(raw)
        subagent_id = _lookup_header_ci(headers, "x-subagent-id")
        if subagent_id is not None:
            return _normalize_allowlisted_tag(subagent_id.split("-", 1)[0])
    return "bridge:zero-canon" if is_zero_canon else "bridge:standard"


def resolve_static_cwd_path(environ: Mapping[str, str] | None = None) -> Path:
    """Resolve static Codex Zero-Canon CWD path from environ or constant default."""
    env = os.environ if environ is None else environ
    override = str(env.get(STATIC_CWD_PATH_ENV, "")).strip()
    return Path(override) if override else Path(DEFAULT_STATIC_CODEX_CWD)


def _verify_static_cwd_fd(fd: int) -> None:
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode):
        raise RuntimeError("zero_canon_static_cwd_unsafe:not_directory")
    if st.st_uid != os.getuid():
        raise RuntimeError("zero_canon_static_cwd_unsafe:uid_mismatch")
    if stat.S_IMODE(st.st_mode) != 0o555:
        raise RuntimeError(f"zero_canon_static_cwd_unsafe:mode_{oct(stat.S_IMODE(st.st_mode))}")
    if os.listdir(fd) != []:
        raise RuntimeError("zero_canon_static_cwd_unsafe:not_empty")


def _verify_static_cwd(target: Path) -> None:
    try:
        fd = os.open(os.fspath(target), _OPEN_DIR_FLAGS)
    except OSError as exc:
        raise RuntimeError(f"zero_canon_static_cwd_unsafe:{exc.errno or 'open_failed'}") from exc
    try:
        _verify_static_cwd_fd(fd)
    finally:
        os.close(fd)


def _create_static_cwd(target: Path) -> None:
    if os.path.islink(target):
        raise RuntimeError("zero_canon_static_cwd_unsafe:symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.mkdir(os.fspath(target), 0o700)
    except FileExistsError:
        return
    try:
        fd = os.open(os.fspath(target), _OPEN_DIR_FLAGS)
    except OSError as exc:
        raise RuntimeError(f"zero_canon_static_cwd_unsafe:{exc.errno or 'open_failed'}") from exc
    try:
        if os.listdir(fd) != []:
            raise RuntimeError("zero_canon_static_cwd_unsafe:not_empty_on_create")
        os.fchmod(fd, 0o555)
    finally:
        os.close(fd)


def ensure_and_verify_static_codex_cwd(path: str | Path | None = None) -> Path:
    """Create (if absent) and fail-closed verify an empty 0o555 non-symlink static CWD."""
    target = resolve_static_cwd_path() if path is None else Path(path)
    if not str(target).strip():
        raise RuntimeError("zero_canon_static_cwd_unsafe:empty_path")
    if os.path.islink(target):
        raise RuntimeError("zero_canon_static_cwd_unsafe:symlink")
    if not target.exists():
        with _CREATE_LOCK:
            if os.path.islink(target):
                raise RuntimeError("zero_canon_static_cwd_unsafe:symlink")
            if not target.exists():
                _create_static_cwd(target)
    _verify_static_cwd(target)
    return target


def is_codex_driver(driver: object) -> bool:
    """Return True when driver represents a Codex backend or protocol."""
    if "codex" in type(driver).__name__.lower():
        return True
    proto = str(getattr(driver, "protocol", "") or "").strip().lower()
    if proto in CODEX_PROTOCOLS:
        return True
    caps = getattr(driver, "capabilities", None)
    cap_proto = str(getattr(caps, "protocol_name", "") or "").strip().lower()
    if cap_proto in CODEX_PROTOCOLS:
        return True
    backend = str(getattr(driver, "backend_id", "") or "").strip().lower()
    return backend in CODEX_BACKEND_IDS


def resolve_zero_canon_cwd(
    driver: object,
    root: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return verified static 0o555 CWD for Codex Zero-Canon, else per-turn `root/cwd`."""
    if not is_codex_driver(driver) or not is_static_cwd_enabled(environ):
        return os.path.join(root, "cwd")
    return str(ensure_and_verify_static_codex_cwd(resolve_static_cwd_path(environ)))
