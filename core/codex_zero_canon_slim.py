"""Env-configurable Zero-Canon prefix slimming for Codex app-server (config + baseInstructions)."""

from __future__ import annotations

import copy
import os
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, cast

SLIM_ENABLED_ENV: Final[str] = "BRIDGE_CODEX_ZERO_CANON_SLIM_ENABLED"
BASE_INSTRUCTIONS_ENV: Final[str] = "BRIDGE_CODEX_ZERO_CANON_BASE_INSTRUCTIONS"
DISABLE_FEATURES_ENV: Final[str] = "BRIDGE_CODEX_ZERO_CANON_DISABLE_FEATURES"

_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off", "disabled"})
_OMIT_SENTINELS: Final[frozenset[str]] = frozenset({"0", "false", "no", "off", "none", "disabled"})

DEFAULT_ZERO_CANON_BASE_INSTRUCTIONS: Final[str] = (
    "You are a stateless assistant. Follow only the prompt in the current turn. "
    "Do not assume local files, tools, or prior conversation."
)
DEFAULT_SLIM_DISABLE_FEATURES: Final[tuple[str, ...]] = (
    "js_repl",
    "plugins",
    "apps",
    "browser_use",
    "computer_use",
    "image_generation",
    "view_image",
    "sleep_tool",
    "skill_search",
    "tool_suggest",
    "goals",
    "shell_tool",
    "unified_exec",
)
SLIM_DENY_SECTIONS: Final[tuple[str, ...]] = ("agents", "marketplaces", "projects")
SLIM_FORCED_CONFIG: Final[Mapping[str, object]] = MappingProxyType(
    {
        "include_permissions_instructions": False,
        "include_apps_instructions": False,
        "include_collaboration_mode_instructions": False,
        "include_environment_context": False,
        "include_environment_context_time": False,
        "web_search": "disabled",
    }
)


def _env_source(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def is_slim_zero_canon_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Default-on flag; kill-switch via `0`/`false`/`no`/`off`/`disabled`."""
    raw = _env_source(env).get(SLIM_ENABLED_ENV)
    if raw is None or not raw.strip():
        return True
    return raw.strip().lower() not in _FALSY


def resolve_base_instructions(env: Mapping[str, str] | None = None) -> str | None:
    """Return neutral baseInstructions for Zero-Canon, or None when disabled/omitted."""
    src = _env_source(env)
    if not is_slim_zero_canon_enabled(src):
        return None
    raw = src.get(BASE_INSTRUCTIONS_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_ZERO_CANON_BASE_INSTRUCTIONS
    cleaned = raw.strip()
    return None if cleaned.lower() in _OMIT_SENTINELS else cleaned


def resolve_disabled_features(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Return tuple of Codex [features] flags to disable in Zero-Canon; empty when disabled."""
    src = _env_source(env)
    if not is_slim_zero_canon_enabled(src):
        return ()
    raw = src.get(DISABLE_FEATURES_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_SLIM_DISABLE_FEATURES
    stripped = raw.strip()
    if stripped.lower() in _OMIT_SENTINELS:
        return ()
    return tuple(part.strip() for part in stripped.split(",") if part.strip())


def apply_codex_zero_canon_slim(
    cfg: Mapping[str, object], env: Mapping[str, str] | None = None
) -> dict[str, object]:
    """Deep-copy config, strip bloated sections, and disable unused agent tools/prompts."""
    src = _env_source(env)
    if not is_slim_zero_canon_enabled(src):
        return {str(k): copy.deepcopy(v) for k, v in cfg.items()}
    result: dict[str, object] = {
        str(k): copy.deepcopy(v) for k, v in cfg.items() if k not in SLIM_DENY_SECTIONS
    }
    result.update(SLIM_FORCED_CONFIG)
    result["agents"] = {"enabled": False}
    disabled = resolve_disabled_features(src)
    if disabled:
        raw_features = result.get("features")
        features: dict[str, object] = (
            {str(k): v for k, v in cast(Mapping[object, object], raw_features).items()}
            if isinstance(raw_features, Mapping)
            else {}
        )
        for feat in disabled:
            features[feat] = False
        result["features"] = features
    return result


def enrich_zero_canon_thread_params(
    params: Mapping[str, object], zc: bool, env: Mapping[str, str] | None = None
) -> dict[str, object]:
    """Attach Zero-Canon base_instructions when enabled; strip it when disabled or non-ZC."""
    out = dict(params)
    if not zc or not is_slim_zero_canon_enabled(env):
        _ = out.pop("base_instructions", None)
        return out
    if "base_instructions" not in out:
        base = resolve_base_instructions(env)
        if base is not None:
            out["base_instructions"] = base
    return out
