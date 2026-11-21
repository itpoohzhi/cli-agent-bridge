"""Environment, binary verification, and fingerprinting for Meta Muse MSP v1."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.subbridge_zero_canon import filter_muse_settings
from core.zero_canon_fs import ensure_private_dir, remove_entry, write_atomic_0600

MUSE_ENV_ALLOWLIST: tuple[str, ...] = (
    "PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "MUSE_PROVIDER",
)
_REQUIRED_FINGERPRINT_FIELDS: tuple[str, ...] = ("wrapper_path", "wrapper_sha256", "binary_path", "binary_sha256")
_MUSE_FORBIDDEN_NAMES: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md", "hooks", "hooks.json", "plugins", "skills")


def resolve_pinned_path(raw_path: str) -> str:
    """Resolve user home, relative segments, and symlinks to a canonical path."""
    return os.path.realpath(os.path.abspath(os.path.expanduser(raw_path)))


def get_fingerprint_field(config: Mapping[str, Any], key: str) -> str:
    """Read a field from fingerprint, technical_ref, top-level config, or wrapper fallback."""
    for source in (config.get("fingerprint"), config.get("technical_ref"), config):
        if isinstance(source, Mapping):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if key == "wrapper_path":
        wrapper = config.get("wrapper")
        if isinstance(wrapper, str) and wrapper.strip():
            return wrapper.strip()
    return ""


def _verify_file_digest(raw_path: str, expected_sha256: str) -> tuple[bool, str]:
    pinned_path = resolve_pinned_path(raw_path)
    if not os.path.isfile(pinned_path):
        return (False, "binary_sha256_missing")
    if not expected_sha256:
        return (True, "")
    try:
        with open(pinned_path, "rb") as file_handle:
            actual_sha256 = hashlib.file_digest(file_handle, "sha256").hexdigest()
    except OSError:
        return (False, "binary_sha256_missing")
    if not hmac.compare_digest(actual_sha256.lower(), expected_sha256.lower()):
        return (False, "binary_sha256_mismatch")
    return (True, "")


def verify_binary(config: Mapping[str, Any]) -> tuple[bool, str]:
    """Fail-closed SHA-256 verification of the pinned Muse wrapper and binary."""
    if isinstance(config.get("technical_ref"), Mapping):
        binary_path, binary_sha256 = get_fingerprint_field(config, "binary_path"), get_fingerprint_field(config, "binary_sha256")
        if not binary_path or not binary_sha256:
            return (False, "binary_sha256_missing")
        pairs: list[tuple[str, str]] = [(binary_path, binary_sha256)]
        if wrapper_path := get_fingerprint_field(config, "wrapper_path"):
            pairs.append((wrapper_path, get_fingerprint_field(config, "wrapper_sha256")))
    else:
        fields: dict[str, str] = {}
        for field_name in _REQUIRED_FINGERPRINT_FIELDS:
            value = get_fingerprint_field(config, field_name)
            if not value:
                return (False, "binary_sha256_missing")
            fields[field_name] = value
        pairs = [(fields["wrapper_path"], fields["wrapper_sha256"]), (fields["binary_path"], fields["binary_sha256"])]
    for raw_path, expected_sha256 in pairs:
        ok, reason = _verify_file_digest(raw_path, expected_sha256)
        if not ok:
            return (False, reason)
    return (True, "")


def prepare_muse_zero_canon_home(
    source_home: str | Path, target_home: str | Path, *, source_xdg_config: str | Path | None = None
) -> Path:
    """Prepare isolated Muse HOME with only `auth.json` (0600) and filtered `settings.json`."""
    src_home, zc_home = Path(source_home), Path(target_home)
    if zc_home.is_symlink():
        raise RuntimeError(f"Refusing symlink Zero-Canon HOME: {zc_home}")
    zc_cfg = zc_home / ".config" / "muse"
    for directory in (zc_home, zc_home / ".config", zc_cfg):
        ensure_private_dir(directory, 0o700)
    candidates = ([Path(source_xdg_config) / "muse"] if source_xdg_config else []) + [
        src_home / ".config" / "muse", src_home / ".muse",
    ]
    auth_src = next((c / "auth.json" for c in candidates if (c / "auth.json").is_file() and not (c / "auth.json").is_symlink()), None)
    settings_src = next((c / "settings.json" for c in candidates if (c / "settings.json").is_file() and not (c / "settings.json").is_symlink()), None)
    raw_settings: dict[str, Any] = {}
    if settings_src is not None:
        try:
            parsed = json.loads(settings_src.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                raw_settings = parsed
        except (OSError, ValueError):
            raw_settings = {}
    filtered = (json.dumps(filter_muse_settings(raw_settings), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    targets = [zc_cfg]
    if (src_home / ".muse").is_dir():
        ensure_private_dir(zc_home / ".muse", 0o700)
        targets.append(zc_home / ".muse")
    for target in targets:
        if auth_src is not None:
            write_atomic_0600(target / "auth.json", auth_src.read_bytes())
        write_atomic_0600(target / "settings.json", filtered)
    for base in (zc_home, *targets):
        for name in _MUSE_FORBIDDEN_NAMES:
            remove_entry(base / name)
    return zc_home.resolve()


def build_muse_zero_canon_argv(argv: list[str]) -> list[str]:
    """Принудительно выставляет `--preset empty`, заменяя любой существующий `--preset`."""
    cleaned: list[str] = []
    idx = 0
    while idx < len(argv):
        tok = argv[idx]
        if tok == "--preset":
            idx += 2 if idx + 1 < len(argv) else 1
            continue
        if tok.startswith("--preset="):
            idx += 1
            continue
        cleaned.append(tok)
        idx += 1
    cleaned.extend(("--preset", "empty"))
    return cleaned


def build_muse_env(
    base_env: Mapping[str, str] | None,
    verified_binary_path: str,
    turn_sandbox: str | None = None,
    server_env: Mapping[str, str] | None = None,
    *,
    zero_canon_home: str | None = None,
) -> dict[str, str]:
    """Build a strictly allowlisted environment for a Muse resident process."""
    _ = base_env
    trusted_env: Mapping[str, str] = os.environ if server_env is None else server_env
    env: dict[str, str] = {key: val for key in MUSE_ENV_ALLOWLIST if isinstance((val := trusted_env.get(key)), str)}
    env["MUSE_BIN_PATH"] = verified_binary_path
    if turn_sandbox:
        env["TMPDIR"] = turn_sandbox
    if zero_canon_home:
        zc_home = prepare_muse_zero_canon_home(
            trusted_env.get("HOME") or str(Path.home()), zero_canon_home, source_xdg_config=trusted_env.get("XDG_CONFIG_HOME")
        )
        env["HOME"], env["XDG_CONFIG_HOME"], env["BRIDGE_ZERO_CANON"] = str(zc_home), str(zc_home / ".config"), "1"
    return env


def build_muse_zero_canon_env(
    base_env: Mapping[str, str] | None, verified_binary_path: str, root: str, *, server_env: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Build an isolated Zero-Canon environment for a Muse stdio turn."""
    cwd_dir = Path(root) / "cwd"
    cwd_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(cwd_dir, 0o700)
    return build_muse_env(base_env, verified_binary_path, turn_sandbox=root, server_env=server_env, zero_canon_home=str(Path(root) / "home"))


def compute_muse_fingerprint(
    config: Mapping[str, Any], sandbox_flags: list[str], cli_args: list[str], env: Mapping[str, str]
) -> str:
    """Compute a deterministic SHA-256 fingerprint for SlotAffinityKey."""
    canonical = (
        get_fingerprint_field(config, "version"),
        get_fingerprint_field(config, "wrapper_sha256"),
        get_fingerprint_field(config, "binary_sha256"),
        list(sandbox_flags),
        list(cli_args),
        sorted(env.items()),
    )
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
