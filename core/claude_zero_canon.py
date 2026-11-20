"""Pure domain rules for Claude Zero-Canon isolation in cli-agent-bridge."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import Any

SCHEMA_VERSION = "1.0"
ENV_POLICY_VERSION = "pol-env/3"
REVIEW_PROFILE_HEADER = "X-Review-Profile"
REVIEW_PROFILE_VALUE = "Zero-Canon"

CLAUDE_SETTINGS_ALLOWLIST = frozenset((
    "env",
    "apiKeyHelper",
    "forceLoginMethod",
    "forceLoginOrgUUID",
))

CLAUDE_STATE_ALLOWLIST = frozenset((
    "oauthAccount",
    "userID",
    "hasCompletedOnboarding",
    "lastOnboardingVersion",
    "customApiKeyResponses",
))

CLAUDE_ENV_OVERLAY: Mapping[str, str] = MappingProxyType(
    dict((("CLAUDE_CONFIG_DIR", "/.claude"),))
)

CLAUDE_FORBIDDEN_FLAGS = frozenset((
    "--tools",
    "--allowedTools",
    "--disallowedTools",
    "--setting-sources",
    "--mcp-config",
    "--strict-mcp-config",
    "--dangerously-skip-permissions",
    "--allow-dangerously-skip-permissions",
    "--bare",
    "--settings",
    "--plugin-dir",
    "--add-dir",
    "-r",
    "--resume",
    "-c",
    "--continue",
))

CLAUDE_BASE_FLAGS = (
    "--disable-slash-commands",
    "--no-session-persistence",
    "--strict-mcp-config",
)

CLAUDE_PRESERVED_CA_FILES = frozenset((
    "aeza-8788-ca.pem",
    "bundle-with-aeza.pem",
    "policy-limits.json",
    "policy-limits.json.signature.json",
    "policy-limits.json.stamp.json",
))


@dataclass(frozen=True, slots=True)
class ClaudeProfileSpec:
    """Immutable Claude CLI Zero-Canon profile specification."""

    name: str
    setting_sources: str
    default_tools: str | None
    image_tools: str | None
    isolate_home: bool


CLAUDE_PROFILES: Mapping[str, ClaudeProfileSpec] = MappingProxyType(
    dict((
        ("strict", ClaudeProfileSpec("strict", "user", "", "Read", True)),
        ("ro", ClaudeProfileSpec("ro", "user", "Read,Grep,Glob", "Read,Grep,Glob", True)),
        ("coder", ClaudeProfileSpec("coder", "user,project", None, None, False)),
    ))
)

__all__ = (
    "SCHEMA_VERSION",
    "ENV_POLICY_VERSION",
    "REVIEW_PROFILE_HEADER",
    "REVIEW_PROFILE_VALUE",
    "CLAUDE_SETTINGS_ALLOWLIST",
    "CLAUDE_STATE_ALLOWLIST",
    "CLAUDE_ENV_OVERLAY",
    "CLAUDE_FORBIDDEN_FLAGS",
    "CLAUDE_BASE_FLAGS",
    "CLAUDE_PRESERVED_CA_FILES",
    "ClaudeProfileSpec",
    "CLAUDE_PROFILES",
    "get_claude_profile",
    "filter_claude_settings",
    "filter_claude_state",
    "build_claude_zero_canon_flags",
    "build_claude_env_overrides",
    "build_claude_zero_canon_env",
    "find_forbidden_claude_flags",
    "serialize_claude_json",
    "is_zero_canon_review_profile",
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


def _filter_allowlist(raw: Mapping[str, Any], allowlist: frozenset[str]) -> dict[str, Any]:
    """Copy allowlisted top-level keys from raw without mutating input."""
    if not isinstance(raw, Mapping):
        raise TypeError(f"Expected a mapping, got {type(raw).__name__}")
    return {str(k): _clone_value(v) for k, v in raw.items() if k in allowlist}


def _normalize_dir(path: str, label: str) -> str:
    """Validate absolute non-root directory path and strip trailing slashes."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"{label} must be a non-empty path string")
    cleaned = path.strip().rstrip("/")
    if not cleaned.startswith("/") or not cleaned[1:]:
        raise ValueError(f"{label} must be an absolute non-root path: {path!r}")
    return cleaned


def get_claude_profile(profile: str) -> ClaudeProfileSpec:
    """Return the immutable profile spec for a supported Zero-Canon profile."""
    spec = CLAUDE_PROFILES.get(profile)
    if spec is None:
        raise ValueError(f"Unsupported Claude Zero-Canon profile: {profile!r}")
    return spec


def filter_claude_settings(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Filter Claude settings.json to Zero-Canon allowlisted keys only."""
    return _filter_allowlist(raw, CLAUDE_SETTINGS_ALLOWLIST)


def filter_claude_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Filter .claude.json to Zero-Canon allowlisted state keys only."""
    return _filter_allowlist(raw, CLAUDE_STATE_ALLOWLIST)


def build_claude_zero_canon_flags(
    has_images: bool = False,
    profile: str = "strict",
    tools: str | None = None,
) -> tuple[str, ...]:
    """Build Zero-Canon CLI flags for Claude subprocess invocation."""
    spec = get_claude_profile(profile)
    flags: list[str] = ["--setting-sources", spec.setting_sources, *CLAUDE_BASE_FLAGS]
    effective_tools = tools if tools is not None else (
        spec.image_tools if has_images else spec.default_tools
    )
    if effective_tools is not None:
        flags.extend(("--tools", effective_tools))
    return tuple(flags)


def build_claude_env_overrides(
    clean_home: str,
    *,
    profile: str = "strict",
    config_dir: str | None = None,
) -> dict[str, str]:
    """Build explicit HOME and CLAUDE_CONFIG_DIR overrides for Claude."""
    spec = get_claude_profile(profile)
    home = _normalize_dir(clean_home, "clean_home")
    prefix = "" if home == "/" else home
    overrides: dict[str, str] = {}
    if spec.isolate_home:
        overrides["HOME"] = home
    for key, suffix in CLAUDE_ENV_OVERLAY.items():
        if key == "CLAUDE_CONFIG_DIR" and config_dir is not None:
            overrides[key] = _normalize_dir(config_dir, "config_dir")
        else:
            overrides[key] = f"{prefix}{suffix}"
    return overrides


def build_claude_zero_canon_env(
    base_env: Mapping[str, str],
    clean_home: str,
    *,
    profile: str = "strict",
    config_dir: str | None = None,
) -> dict[str, str]:
    """Return a copy of base_env with explicit Zero-Canon Claude overrides."""
    if not isinstance(base_env, Mapping):
        raise TypeError(f"Expected a mapping, got {type(base_env).__name__}")
    env = dict(base_env)
    env.pop("CLAUDE_CONFIG_DIR", None)
    env.update(build_claude_env_overrides(clean_home, profile=profile, config_dir=config_dir))
    return env


def find_forbidden_claude_flags(argv: Sequence[str]) -> tuple[str, ...]:
    """Return Claude flags in argv before '--' forbidden under Zero-Canon."""
    found: list[str] = []
    for token in argv:
        if token == "--":
            break
        if token.split("=", 1)[0] in CLAUDE_FORBIDDEN_FLAGS:
            found.append(token)
    return tuple(found)


def serialize_claude_json(payload: Mapping[str, Any]) -> str:
    """Serialize a filtered Claude JSON mapping deterministically."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def is_zero_canon_review_profile(value: str | None) -> bool:
    """Match a review profile header value against Zero-Canon case-insensitively."""
    return isinstance(value, str) and value.strip().lower() == REVIEW_PROFILE_VALUE.lower()
