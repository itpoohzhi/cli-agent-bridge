"""Pure domain rules for Agy Zero-Canon isolation in cli-agent-bridge."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import Any

SCHEMA_VERSION = "1.0"
ENV_POLICY_VERSION = "pol-env/3"
REVIEW_PROFILE_HEADER = "X-Review-Profile"
REVIEW_PROFILE_VALUE = "Zero-Canon"
AGY_ZERO_CANON_FLAG = "AGY_ZERO_CANON_ENABLED"

AGY_SETTINGS_ALLOWLIST = frozenset((
    "selectedAuthType",
    "theme",
    "security",
    "auth",
))

AGY_SETTINGS_OVERRIDES: dict[str, dict[str, Any]] = {
    "hooks": {},
    "mcpServers": {},
}

AGY_CANON_FILE_NAMES = ("AGENTS.md", "GEMINI.md", "hooks.json")

AGY_ZC_AUTH_RELPATHS = (
    ".gemini/jetski-standalone-oauth-token",
    ".gemini/projects.json",
    ".gemini/antigravity-cli/antigravity-oauth-token",
    ".gemini/antigravity-cli/installation_id",
    ".gemini/antigravity-cli/jetski_state.pbtxt",
)


@dataclass(frozen=True, slots=True)
class AgyZeroCanonPlan:
    """Immutable Zero-Canon isolation policy plan for a single Agy turn."""

    enabled: bool
    profile_tag: str
    use_zc_home: bool
    force_disable_slash_commands: bool
    use_empty_cwd: bool
    isolate_builtin_ro: bool
    settings_arg: str | None


__all__ = (
    "SCHEMA_VERSION",
    "ENV_POLICY_VERSION",
    "REVIEW_PROFILE_HEADER",
    "REVIEW_PROFILE_VALUE",
    "AGY_ZERO_CANON_FLAG",
    "AGY_SETTINGS_ALLOWLIST",
    "AGY_SETTINGS_OVERRIDES",
    "AGY_CANON_FILE_NAMES",
    "AGY_ZC_AUTH_RELPATHS",
    "AgyZeroCanonPlan",
    "is_zero_canon_review_profile",
    "filter_agy_settings",
    "zero_canon_settings_cli_arg",
    "zero_canon_profile_tag",
    "serialize_agy_json",
    "build_agy_zero_canon_plan",
)


def _clone_value(value: Any) -> Any:
    """Return a detached copy of nested mapping and sequence values."""
    if isinstance(value, Mapping):
        return {str(k): _clone_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clone_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_clone_value(item) for item in value)
    if isinstance(value, set):
        return {_clone_value(item) for item in value}
    return value


def is_zero_canon_review_profile(headers_or_value: Any) -> bool:
    """Match X-Review-Profile header or value against Zero-Canon case-insensitively."""
    target = REVIEW_PROFILE_VALUE.lower()
    if isinstance(headers_or_value, str):
        return headers_or_value.strip().lower() == target
    if isinstance(headers_or_value, Mapping) or hasattr(headers_or_value, "items"):
        header_name = REVIEW_PROFILE_HEADER.lower()
        for key, val in headers_or_value.items():
            if isinstance(key, str) and key.strip().lower() == header_name:
                return isinstance(val, str) and val.strip().lower() == target
    return False


def filter_agy_settings(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Filter Agy settings.json to allowlisted keys plus safe overrides."""
    if not isinstance(raw, Mapping):
        raise TypeError(f"Expected a mapping, got {type(raw).__name__}")
    filtered: dict[str, Any] = {
        str(k): _clone_value(v) for k, v in raw.items() if k in AGY_SETTINGS_ALLOWLIST
    }
    for key, val in AGY_SETTINGS_OVERRIDES.items():
        filtered[str(key)] = _clone_value(val)
    return filtered


def zero_canon_settings_cli_arg() -> str:
    """Return the inline JSON settings argument for agy.real --settings."""
    return "{}"


def zero_canon_profile_tag(is_zero_canon: bool) -> str:
    """Return the canonical review profile tag for session and scope isolation."""
    return "zero-canon" if is_zero_canon else "standard"


def serialize_agy_json(payload: Mapping[str, Any]) -> str:
    """Serialize a filtered Agy JSON mapping deterministically."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def build_agy_zero_canon_plan(
    headers_or_value: Any = None,
    *,
    flag_enabled: bool = True,
    is_zero_canon: bool | None = None,
) -> AgyZeroCanonPlan:
    """Build an immutable Zero-Canon turn plan from request profile and flag state."""
    requested = (
        is_zero_canon_review_profile(headers_or_value)
        if is_zero_canon is None
        else bool(is_zero_canon)
    )
    active = bool(flag_enabled and requested)
    return AgyZeroCanonPlan(
        enabled=active,
        profile_tag=zero_canon_profile_tag(active),
        use_zc_home=active,
        force_disable_slash_commands=active,
        use_empty_cwd=active,
        isolate_builtin_ro=active,
        settings_arg=zero_canon_settings_cli_arg() if active else None,
    )
