"""Environment, binary verification, and fingerprinting for Meta Muse MSP v1."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from typing import Any

MUSE_ENV_ALLOWLIST: tuple[str, ...] = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "MUSE_PROVIDER",
)

_REQUIRED_FINGERPRINT_FIELDS: tuple[str, ...] = (
    "wrapper_path",
    "wrapper_sha256",
    "binary_path",
    "binary_sha256",
)


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
    """Verify pinned file existence and, when provided, its SHA-256 digest."""
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
        binary_path = get_fingerprint_field(config, "binary_path")
        binary_sha256 = get_fingerprint_field(config, "binary_sha256")
        if not binary_path or not binary_sha256:
            return (False, "binary_sha256_missing")
        pairs: list[tuple[str, str]] = [(binary_path, binary_sha256)]
        wrapper_path = get_fingerprint_field(config, "wrapper_path")
        if wrapper_path:
            pairs.append((wrapper_path, get_fingerprint_field(config, "wrapper_sha256")))
    else:
        fields: dict[str, str] = {}
        for field_name in _REQUIRED_FINGERPRINT_FIELDS:
            value = get_fingerprint_field(config, field_name)
            if not value:
                return (False, "binary_sha256_missing")
            fields[field_name] = value
        pairs = [
            (fields["wrapper_path"], fields["wrapper_sha256"]),
            (fields["binary_path"], fields["binary_sha256"]),
        ]

    for raw_path, expected_sha256 in pairs:
        ok, reason = _verify_file_digest(raw_path, expected_sha256)
        if not ok:
            return (False, reason)
    return (True, "")


def build_muse_env(
    base_env: Mapping[str, str] | None,
    verified_binary_path: str,
    turn_sandbox: str | None = None,
    server_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a strictly allowlisted environment for a Muse resident process.

    ``base_env`` is accepted for caller compatibility and intentionally ignored so
    client/config dictionaries cannot override system or proxy variables.
    """
    _ = base_env
    trusted_env: Mapping[str, str] = os.environ if server_env is None else server_env
    env: dict[str, str] = {}
    for key in MUSE_ENV_ALLOWLIST:
        value = trusted_env.get(key)
        if isinstance(value, str):
            env[key] = value
    env["MUSE_BIN_PATH"] = verified_binary_path
    if turn_sandbox:
        env["TMPDIR"] = turn_sandbox
    return env


def compute_muse_fingerprint(
    config: Mapping[str, Any],
    sandbox_flags: list[str],
    cli_args: list[str],
    env: Mapping[str, str],
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
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
