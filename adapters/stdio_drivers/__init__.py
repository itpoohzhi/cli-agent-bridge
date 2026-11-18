"""Protocol driver registrations and lightweight helpers for resident stdio."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import dataclasses
import os
import re
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from adapters.stdio_drivers.muse_driver import MuseMspDriver
from adapters.stdio_drivers.opencode_driver import OpenCodeAcpDriver
from core.stdio_resident.rpc_drivers import register_protocol_driver
from core.stdio_resident.types import SlotAffinityKey

register_protocol_driver("opencode-acp", OpenCodeAcpDriver)

__all__ = [
    "MuseMspDriver",
    "OpenCodeAcpDriver",
    "build_affinity_key",
    "infer_protocol",
    "is_opencode_resident_enabled",
    "is_resident_enabled",
    "resolve_chat_key",
    "resolve_owner_hash",
    "validate_cwd",
]

_SESSION_ID_KEYS: tuple[str, ...] = ("chat_key", "session_id", "conversation_id")
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}\Z")
_ENV_MUSE_RESIDENT_ENABLED = "BRIDGE_MUSE_RESIDENT_ENABLED"
_ENV_OPENCODE_RESIDENT_ENABLED = "BRIDGE_OPENCODE_RESIDENT_ENABLED"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on", "enabled"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", "disabled"})


def resolve_chat_key(data: Mapping[str, Any]) -> tuple[str, bool]:
    """Validate and resolve session identifier into ``(chat_key, is_ephemeral)``."""
    found: list[str] = []
    for key in _SESSION_ID_KEYS:
        raw = data.get(key)
        if raw is None:
            continue
        if not isinstance(raw, str) or not _SESSION_ID_RE.fullmatch(raw):
            raise ValueError("invalid_session_id")
        found.append(raw)
    if not found:
        return (uuid.uuid4().hex, True)
    if len(set(found)) > 1:
        raise ValueError("conflicting_session_identifiers")
    return (found[0], False)


def is_resident_enabled(control_file: str | None = None) -> bool:
    """Return runtime resident toggle from control file or ``BRIDGE_MUSE_RESIDENT_ENABLED``."""
    if control_file:
        try:
            raw = Path(control_file).read_text(encoding="utf-8").strip().lower()
        except OSError:
            raw = ""
        if raw in _FALSE_VALUES:
            return False
        if raw in _TRUE_VALUES:
            return True
    env_val = os.environ.get(_ENV_MUSE_RESIDENT_ENABLED)
    if env_val is None or not env_val.strip():
        return True
    return env_val.strip().lower() in _TRUE_VALUES


def is_opencode_resident_enabled() -> bool:
    """Return whether OpenCode resident adapter is enabled via env."""
    val = os.environ.get(_ENV_OPENCODE_RESIDENT_ENABLED)
    if val is None or not val.strip():
        return False
    return val.strip().lower() in _TRUE_VALUES


def resolve_owner_hash(
    data: Mapping[str, Any],
    protocol: str,
    *,
    trusted_owner_hash: str | None = None,
    auth_owner_hash: str | None = None,
    require_auth: bool = False,
) -> str:
    """Resolve owner hash strictly from trusted server arguments, never from ``data``."""
    _ = data
    for candidate in (trusted_owner_hash, auth_owner_hash):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    if require_auth or protocol == "msp-v1":
        raise PermissionError("auth_required_for_resident_pool")
    return ""


def _extract_wrapper_path(config: Mapping[str, Any]) -> str:
    for key in ("wrapper", "wrapper_path"):
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    fingerprint = config.get("fingerprint")
    if isinstance(fingerprint, Mapping):
        value = fingerprint.get("wrapper_path")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def infer_protocol(
    actual_id: str,
    actual_config: Mapping[str, Any],
    options: Mapping[str, Any],
) -> str:
    """Infer driver protocol from explicit options, backend id, or wrapper basename."""
    explicit = options.get("protocol")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if actual_id == "muse":
        return "msp-v1"
    if actual_id in ("opencode", "opencode-resident"):
        return "opencode-acp"
    wrapper_path = _extract_wrapper_path(actual_config)
    if wrapper_path and os.path.basename(wrapper_path.replace("\\", "/")) == "muse-cli.sh":
        return "msp-v1"
    if wrapper_path and "opencode" in os.path.basename(wrapper_path.replace("\\", "/")):
        return "opencode-acp"
    return "stream-json"


def validate_cwd(data: Mapping[str, Any]) -> str:
    """Normalize and validate working directory, defaulting to process cwd."""
    raw_cwd = data.get("cwd")
    if raw_cwd is None or raw_cwd == "":
        return os.path.realpath(os.getcwd())
    if not isinstance(raw_cwd, str):
        raise ValueError("invalid_cwd")
    resolved = os.path.realpath(os.path.abspath(os.path.expanduser(raw_cwd)))
    if not os.path.isdir(resolved):
        raise ValueError("invalid_cwd")
    return resolved


def build_affinity_key(
    owner_hash: str,
    chat_key: str,
    backend_id: str,
    model: str,
    effort: str,
    cwd_norm: str,
    is_ephemeral: bool = False,
    driver_fingerprint: str = "",
) -> SlotAffinityKey:
    """Construct ``SlotAffinityKey`` with optional wave fields supported by types."""
    kwargs: dict[str, Any] = {
        "owner_hash": owner_hash,
        "chat_key": chat_key,
        "backend_id": backend_id,
        "model": model,
        "effort": effort,
        "cwd_norm": cwd_norm,
    }
    if dataclasses.is_dataclass(SlotAffinityKey):
        fields = {f.name for f in dataclasses.fields(SlotAffinityKey)}
        if "is_ephemeral" in fields:
            kwargs["is_ephemeral"] = is_ephemeral
        if "driver_fingerprint" in fields:
            kwargs["driver_fingerprint"] = driver_fingerprint
        elif "fingerprint" in fields:
            kwargs["fingerprint"] = driver_fingerprint
    return SlotAffinityKey(**kwargs)
