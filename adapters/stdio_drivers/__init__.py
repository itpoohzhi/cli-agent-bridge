"""Protocol driver registrations and lightweight helpers for resident stdio."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import dataclasses
import os
import re
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from adapters.stdio_drivers.agy_canary import (
    apply_canary_limits,
    load_agy_canary_config,
)
from adapters.stdio_drivers.agy_config import (
    build_agy_pool_config,
    is_agy_resident_enabled,
    load_agy_resident_config,
)
from adapters.stdio_drivers.agy_driver import AgyStreamJsonDriver
from adapters.stdio_drivers.muse_driver import MuseMspDriver
from adapters.stdio_drivers.opencode_driver import OpenCodeAcpDriver
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.protocol_driver import StdioProtocolDriver
from core.stdio_resident.rpc_drivers import (
    create_protocol_driver,
    register_protocol_driver,
)
from core.stdio_resident.types import SlotAffinityKey
from core.subbridge_zero_canon import (
    STDIO_RESIDENT_CLAUDE_CODEX_PROTOCOL_FLAG,
    normalize_review_profile,
)
from core.zero_canon_fs import read_gigarc_bool, resolve_hub_dynamic_config

_REPO_DYNAMIC_CONFIG: Path = Path(__file__).resolve().parents[2] / "dynamic_config.json"

register_protocol_driver("opencode-acp", OpenCodeAcpDriver)
register_protocol_driver("agy-stream-json", AgyStreamJsonDriver)

__all__ = [
    "AgyStreamJsonDriver",
    "CODEX_APP_SERVER_V2_FLAG",
    "CODEX_POOL_UNIFIED_CAP_FLAG",
    "MuseMspDriver",
    "OpenCodeAcpDriver",
    "build_affinity_key",
    "infer_protocol",
    "is_agy_resident_enabled",
    "is_claude_codex_resident_protocol_enabled",
    "is_codex_app_server_v2_enabled",
    "is_opencode_resident_enabled",
    "is_resident_enabled",
    "resolve_chat_key",
    "resolve_owner_hash",
    "resolve_pool_and_driver",
    "validate_cwd",
]

_SESSION_ID_KEYS: tuple[str, ...] = ("chat_key", "session_id", "conversation_id")
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}\Z")
_ENV_MUSE_RESIDENT_ENABLED = "BRIDGE_MUSE_RESIDENT_ENABLED"
_ENV_OPENCODE_RESIDENT_ENABLED = "BRIDGE_OPENCODE_RESIDENT_ENABLED"
CODEX_APP_SERVER_V2_FLAG = "BRIDGE_CODEX_APP_SERVER_V2_ENABLED"
CODEX_POOL_UNIFIED_CAP_FLAG = "BRIDGE_CODEX_POOL_UNIFIED_CAP_ENABLED"
_ENV_CODEX_POOL_TOTAL_CAP = "BRIDGE_CODEX_POOL_TOTAL_CAP"
_DEFAULT_CODEX_POOL_TOTAL_CAP = 20
_AGY_IDS = frozenset({"agy", "antigravity", "agy-bridge", "agy-cli"})
_CLAUDE_IDS = frozenset({"claude", "claude-p", "claude_p"})
_CODEX_IDS = frozenset({"codex", "codex-cli", "codex-app-server"})
_CODEX_V2_IDS = frozenset(
    {"codex", "codex-cli", "codex-app-server", "codex-app-server-v2"}
)
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
    candidates: list[Mapping[str, Any]] = [config]
    for section in ("bridge", "fingerprint"):
        sub = config.get(section)
        if isinstance(sub, Mapping):
            candidates.append(cast(Mapping[str, Any], sub))
    transport = config.get("transport")
    if isinstance(transport, Mapping):
        bridge = cast(Mapping[str, Any], transport).get("bridge")
        if isinstance(bridge, Mapping):
            candidates.append(cast(Mapping[str, Any], bridge))
    for mapping in candidates:
        for key in ("wrapper", "wrapper_path"):
            value = mapping.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def is_claude_codex_resident_protocol_enabled(
    environ: Mapping[str, str] | None = None,
    *,
    config_path: Path | None = None,
) -> bool:
    """Kill-switch переключения Claude/Codex на нативные протоколы (дефолт False)."""
    env = os.environ if environ is None else environ
    default_cfg = resolve_hub_dynamic_config(env)
    return read_gigarc_bool(
        STDIO_RESIDENT_CLAUDE_CODEX_PROTOCOL_FLAG,
        default_cfg if config_path is None else config_path,
        environ=env,
        default=False,
    )


def is_codex_app_server_v2_enabled(
    environ: Mapping[str, str] | None = None,
    *,
    config_path: Path | None = None,
) -> bool:
    """Kill-switch выбора Codex app-server v2 (`dynamic_config.json > env > False`)."""
    env = os.environ if environ is None else environ
    default_cfg = resolve_hub_dynamic_config(env)
    return read_gigarc_bool(
        CODEX_APP_SERVER_V2_FLAG,
        default_cfg if config_path is None else config_path,
        environ=env,
        default=False,
    )


def _infer_protocol_from_id(
    actual_id: str,
    *,
    codex_v2: bool,
    native_cc: bool,
    env: Mapping[str, str],
) -> str | None:
    if actual_id == "muse":
        return "msp-v1"
    if actual_id in ("opencode", "opencode-resident"):
        return "opencode-acp"
    lower_id = actual_id.lower()
    if lower_id in _AGY_IDS and is_agy_resident_enabled(env):
        return "agy-stream-json"
    if codex_v2 and lower_id in _CODEX_V2_IDS:
        return "codex-app-server-v2"
    if not native_cc:
        return None
    if lower_id in _CLAUDE_IDS:
        return "claude-stream-json"
    return "codex-app-server" if lower_id in _CODEX_IDS else None


def _infer_protocol_from_wrapper(
    wrapper_path: str,
    *,
    codex_v2: bool,
    native_cc: bool,
    env: Mapping[str, str],
) -> str:
    if not wrapper_path:
        return "stream-json"
    name = os.path.basename(wrapper_path.replace("\\", "/")).lower()
    if name == "muse-cli.sh":
        return "msp-v1"
    if "opencode" in name:
        return "opencode-acp"
    base = name.split(".")[0]
    if (base in _AGY_IDS or name.startswith("agy-cli")) and is_agy_resident_enabled(env):
        return "agy-stream-json"
    if codex_v2 and name.split()[0].split(".")[0] in _CODEX_V2_IDS:
        return "codex-app-server-v2"
    if not native_cc:
        return "stream-json"
    if base in _CLAUDE_IDS or name.startswith("claude-p-"):
        return "claude-stream-json"
    return "codex-app-server" if base in _CODEX_IDS else "stream-json"


def infer_protocol(
    actual_id: str,
    actual_config: Mapping[str, Any],
    options: Mapping[str, Any],
    *,
    environ: Mapping[str, str] | None = None,
    config_path: Path | None = None,
) -> str:
    """Infer driver protocol from explicit options, backend id, or wrapper basename."""
    env = os.environ if environ is None else environ
    codex_v2 = is_codex_app_server_v2_enabled(environ, config_path=config_path)
    native_cc = is_claude_codex_resident_protocol_enabled(
        environ, config_path=config_path
    )
    explicit = options.get("protocol")
    if isinstance(explicit, str) and explicit.strip():
        clean = explicit.strip()
        if clean == "codex-app-server-v2" and not codex_v2:
            return "codex-app-server" if native_cc else "stream-json"
        return clean
    by_id = _infer_protocol_from_id(
        actual_id, codex_v2=codex_v2, native_cc=native_cc, env=env
    )
    if by_id is not None:
        return by_id
    return _infer_protocol_from_wrapper(
        _extract_wrapper_path(actual_config),
        codex_v2=codex_v2,
        native_cc=native_cc,
        env=env,
    )


def _is_codex_pool_unified_cap_enabled(env: Mapping[str, str]) -> bool:
    return read_gigarc_bool(
        CODEX_POOL_UNIFIED_CAP_FLAG,
        resolve_hub_dynamic_config(env),
        environ=env,
        default=False,
    )


def _provider_max_concurrent(driver_config: Mapping[str, Any], *, flat: bool) -> int | None:
    """`limits.max_concurrent`; при `flat=True` — также плоское `max_concurrent` fleet.json."""
    limits = driver_config.get("limits")
    raw = limits.get("max_concurrent") if isinstance(limits, Mapping) else None
    if raw is None and flat:
        raw = driver_config.get("max_concurrent")
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 2:
        return None
    return raw


def _total_cap(env: Mapping[str, str]) -> int:
    raw = (env.get(_ENV_CODEX_POOL_TOTAL_CAP) or "").strip()
    return max(2, min(int(raw), 64)) if raw.isascii() and raw.isdigit() else _DEFAULT_CODEX_POOL_TOTAL_CAP


def _codex_pool_target(env: Mapping[str, str], driver_config: Mapping[str, Any]) -> int | None:
    unified = _is_codex_pool_unified_cap_enabled(env)
    raw_mc = _provider_max_concurrent(driver_config, flat=unified)
    if raw_mc is None:
        return None
    target = max(2, min(raw_mc, 64))
    return min(target, _total_cap(env)) if unified else target


def _env_unset(env: Mapping[str, str], name: str) -> bool:
    return not (env.get(name) or "").strip()


def _align_codex_v2_pool_slots(
    pool_cfg: StdioPoolConfig,
    env: Mapping[str, str],
    driver_config: Mapping[str, Any] | None,
) -> StdioPoolConfig:
    """Align Codex v2 ephemeral/hot slot caps with provider max_concurrent unless env overrides.

    Плоское поле `max_concurrent` (реальный fleet.json) читается только при
    `BRIDGE_CODEX_POOL_UNIFIED_CAP_ENABLED`; иначе поведение прежнее (`limits.max_concurrent`).
    """
    target = _codex_pool_target(env, driver_config) if isinstance(driver_config, Mapping) else None
    if target is None:
        return pool_cfg
    updates: dict[str, Any] = {}
    if _env_unset(env, "BRIDGE_STDIO_MAX_SLOTS"):
        new_max = max(pool_cfg.max_slots, target)
        updates["max_slots"] = new_max
        if _env_unset(env, "BRIDGE_STDIO_MAX_SLOTS_PER_PRINCIPAL"):
            updates["max_slots_per_principal"] = new_max
    if _env_unset(env, "BRIDGE_STDIO_MAX_EPHEMERAL_SLOTS"):
        updates["max_ephemeral_slots"] = min(target, updates.get("max_slots", pool_cfg.max_slots))
    return dataclasses.replace(pool_cfg, **updates) if updates else pool_cfg


def resolve_pool_and_driver(
    protocol: str,
    environ: Mapping[str, str] | None = None,
    *,
    driver_config: Mapping[str, Any] | None = None,
) -> tuple[StdioPoolConfig, StdioProtocolDriver]:
    """Создаёт `StdioPoolConfig` и драйвер; для `agy-stream-json` применяет `AgyResidentConfig`."""
    env = os.environ if environ is None else environ
    if protocol in ("agy-stream-json", "agy_stream_json"):
        agy_cfg = load_agy_resident_config(env)
        agy_cfg = apply_canary_limits(agy_cfg, load_agy_canary_config(env))
        return build_agy_pool_config(agy_cfg), create_protocol_driver(protocol, config=agy_cfg)
    pool_cfg = StdioPoolConfig.from_env(environ)
    if protocol in ("codex-app-server-v2", "codex_app_server_v2"):
        pool_cfg = _align_codex_v2_pool_slots(pool_cfg, env, driver_config)
    return pool_cfg, create_protocol_driver(
        protocol, config=driver_config
    )


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
    *,
    env_digest: str = "",
    review_profile: str = "standard",
    **_legacy: object,
) -> SlotAffinityKey:
    """Construct a complete resident-process affinity key.

    Устаревшие kwargs (`is_ephemeral`, `driver_fingerprint`) принимаются и игнорируются:
    в `SlotAffinityKey` таких полей нет.
    """
    return SlotAffinityKey(
        owner_hash=owner_hash,
        chat_key=chat_key,
        backend_id=backend_id,
        model=model,
        effort=effort,
        cwd_norm=cwd_norm,
        env_digest=env_digest,
        review_profile=normalize_review_profile(review_profile),
    )
