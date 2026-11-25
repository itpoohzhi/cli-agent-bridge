"""Pure domain policy for bridge graceful drain and Retry-After semantics.

Leaf stdlib module (no I/O, OS, process, or network dependencies) shared by the
hub lifecycle manager, HTTP facade, and sub-bridges to compute bounded
`Retry-After` headers, launchd-safe drain budgets, and drain hold windows.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

DEFAULT_RETRY_AFTER_S: int = 5
DEFAULT_SUBAGENT_RETRY_AFTER_S: int = 3
MIN_RETRY_AFTER_S: int = 1
DEFAULT_RETRY_AFTER_MAX_S: int = 60

DEFAULT_DRAIN_TIMEOUT_S: float = 110.0
DEFAULT_DRAIN_TAIL_S: float = 7.0
DEFAULT_DRAIN_MARGIN_S: float = 5.0
DEFAULT_DRAIN_HOLD_MAX_S: float = 30.0
MIN_EFFECTIVE_DRAIN_TIMEOUT_S: float = 1.0

_FALSY_FLAGS: frozenset[str] = frozenset({"0", "false", "no", "off"})

__all__ = [
    "DEFAULT_DRAIN_HOLD_MAX_S",
    "DEFAULT_DRAIN_MARGIN_S",
    "DEFAULT_DRAIN_TAIL_S",
    "DEFAULT_DRAIN_TIMEOUT_S",
    "DEFAULT_RETRY_AFTER_MAX_S",
    "DEFAULT_RETRY_AFTER_S",
    "DEFAULT_SUBAGENT_RETRY_AFTER_S",
    "MIN_EFFECTIVE_DRAIN_TIMEOUT_S",
    "MIN_RETRY_AFTER_S",
    "DrainPolicyConfig",
    "effective_hub_drain_timeout_s",
    "is_drain_policy_enabled",
    "parse_exit_timeout_s",
    "resolve_drain_hold_timeout_s",
    "resolve_retry_after_s",
]


def _parse_positive_int(raw: str | None) -> int | None:
    """Parse a positive integer (>= MIN_RETRY_AFTER_S) without raising."""
    if raw is None:
        return None
    try:
        stripped = raw.strip()
        if not stripped:
            return None
        value = int(stripped)
    except (AttributeError, TypeError, ValueError):
        return None
    return value if value >= MIN_RETRY_AFTER_S else None


def _parse_finite_float(raw: str | None) -> float | None:
    """Parse a finite float without raising; returns None for NaN/Inf/invalid."""
    if raw is None:
        return None
    try:
        stripped = raw.strip()
        if not stripped:
            return None
        value = float(stripped)
    except (AttributeError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _resolve_retry_after_max_s(env: Mapping[str, str]) -> int:
    """Resolve upper ceiling for Retry-After from BRIDGE_RETRY_AFTER_MAX_S."""
    parsed = _parse_positive_int(env.get("BRIDGE_RETRY_AFTER_MAX_S"))
    return parsed if parsed is not None else DEFAULT_RETRY_AFTER_MAX_S


def _clamp_retry_after(value: int, ceiling: int) -> int:
    """Clamp Retry-After to [MIN_RETRY_AFTER_S, ceiling]."""
    return max(MIN_RETRY_AFTER_S, min(value, ceiling))


def _safe_positive_float(value: float, default: float) -> float:
    """Return value as float when finite and > 0, else default."""
    candidate = float(value)
    return candidate if math.isfinite(candidate) and candidate > 0.0 else default


def _safe_nonneg_float(value: float, default: float) -> float:
    """Return value as float when finite and >= 0, else default."""
    candidate = float(value)
    return candidate if math.isfinite(candidate) and candidate >= 0.0 else default


def _resolve_positive_float(env: Mapping[str, str], key: str, default: float) -> float:
    """Parse a positive finite float env var with safe fallback."""
    parsed = _parse_finite_float(env.get(key))
    return _safe_positive_float(parsed, default) if parsed is not None else default


def _resolve_nonneg_float(env: Mapping[str, str], key: str, default: float) -> float:
    """Parse a non-negative finite float env var with safe fallback."""
    parsed = _parse_finite_float(env.get(key))
    return _safe_nonneg_float(parsed, default) if parsed is not None else default


def is_drain_policy_enabled(env: Mapping[str, str]) -> bool:
    """Return True unless BRIDGE_DRAIN_POLICY_ENABLED is explicitly falsy."""
    raw = env.get("BRIDGE_DRAIN_POLICY_ENABLED")
    if raw is None:
        return True
    try:
        normalized = raw.strip().lower()
    except AttributeError:
        return True
    return not normalized or normalized not in _FALSY_FLAGS


def resolve_retry_after_s(
    env: Mapping[str, str],
    *,
    explicit: int | None = None,
    is_subagent: bool = False,
    legacy_default: int | None = None,
) -> int:
    """Resolve a safe, bounded Retry-After value in seconds without raising."""
    ceiling = _resolve_retry_after_max_s(env)
    if explicit is not None:
        return _clamp_retry_after(explicit, ceiling)
    parsed = _parse_positive_int(env.get("BRIDGE_RETRY_AFTER_S"))
    if parsed is not None:
        return _clamp_retry_after(parsed, ceiling)
    if not is_drain_policy_enabled(env) and legacy_default is not None:
        return _clamp_retry_after(legacy_default, ceiling)
    if is_subagent:
        subagent_env = _parse_positive_int(env.get("BRIDGE_SUBAGENT_RETRY_AFTER_S"))
        default_s = (
            subagent_env if subagent_env is not None else DEFAULT_SUBAGENT_RETRY_AFTER_S
        )
    else:
        default_s = DEFAULT_RETRY_AFTER_S
    return _clamp_retry_after(default_s, ceiling)


def effective_hub_drain_timeout_s(
    configured_drain_s: float,
    exit_timeout_s: float | None,
    *,
    tail_s: float = DEFAULT_DRAIN_TAIL_S,
    margin_s: float = DEFAULT_DRAIN_MARGIN_S,
) -> tuple[float, bool]:
    """Clamp hub drain timeout to fit under ExitTimeOut - tail_s - margin_s.

    Returns ``(effective_timeout_s, was_clamped)``.
    """
    configured = _safe_positive_float(configured_drain_s, DEFAULT_DRAIN_TIMEOUT_S)
    if exit_timeout_s is None:
        return (configured, False)
    exit_limit = float(exit_timeout_s)
    if not math.isfinite(exit_limit) or exit_limit <= 0.0:
        return (configured, False)
    safe_tail = _safe_nonneg_float(tail_s, DEFAULT_DRAIN_TAIL_S)
    safe_margin = _safe_nonneg_float(margin_s, DEFAULT_DRAIN_MARGIN_S)
    max_allowed = max(MIN_EFFECTIVE_DRAIN_TIMEOUT_S, exit_limit - safe_tail - safe_margin)
    if configured > max_allowed:
        return (max_allowed, True)
    return (configured, False)


def resolve_drain_hold_timeout_s(env: Mapping[str, str]) -> float:
    """Resolve BRIDGE_DRAIN_HOLD_TIMEOUT_S bounded to [0.0, hold_max_s]."""
    parsed = _parse_finite_float(env.get("BRIDGE_DRAIN_HOLD_TIMEOUT_S"))
    if parsed is None or parsed <= 0.0:
        return 0.0
    ceiling = _resolve_positive_float(
        env, "BRIDGE_DRAIN_HOLD_MAX_S", DEFAULT_DRAIN_HOLD_MAX_S
    )
    return min(parsed, ceiling)


def parse_exit_timeout_s(env: Mapping[str, str]) -> float | None:
    """Parse a positive finite BRIDGE_EXIT_TIMEOUT_S value, or return None."""
    parsed = _parse_finite_float(env.get("BRIDGE_EXIT_TIMEOUT_S"))
    if parsed is None or parsed <= 0.0:
        return None
    return parsed


@dataclass(frozen=True)
class DrainPolicyConfig:
    """Immutable snapshot of drain and Retry-After policy settings."""

    enabled: bool = True
    retry_after_s: int = DEFAULT_RETRY_AFTER_S
    subagent_retry_after_s: int = DEFAULT_SUBAGENT_RETRY_AFTER_S
    retry_after_max_s: int = DEFAULT_RETRY_AFTER_MAX_S
    drain_timeout_s: float = DEFAULT_DRAIN_TIMEOUT_S
    effective_drain_timeout_s: float = DEFAULT_DRAIN_TIMEOUT_S
    drain_timeout_clamped: bool = False
    exit_timeout_s: float | None = None
    drain_tail_s: float = DEFAULT_DRAIN_TAIL_S
    drain_margin_s: float = DEFAULT_DRAIN_MARGIN_S
    drain_hold_timeout_s: float = 0.0

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> DrainPolicyConfig:
        """Build a validated DrainPolicyConfig from an environment mapping."""
        configured_drain_s = _resolve_positive_float(
            env, "BRIDGE_DRAIN_TIMEOUT_S", DEFAULT_DRAIN_TIMEOUT_S
        )
        exit_timeout_s = parse_exit_timeout_s(env)
        tail_s = _resolve_nonneg_float(env, "BRIDGE_DRAIN_TAIL_S", DEFAULT_DRAIN_TAIL_S)
        margin_s = _resolve_nonneg_float(
            env, "BRIDGE_DRAIN_MARGIN_S", DEFAULT_DRAIN_MARGIN_S
        )
        effective_s, clamped = effective_hub_drain_timeout_s(
            configured_drain_s, exit_timeout_s, tail_s=tail_s, margin_s=margin_s
        )
        return cls(
            enabled=is_drain_policy_enabled(env),
            retry_after_s=resolve_retry_after_s(env, is_subagent=False),
            subagent_retry_after_s=resolve_retry_after_s(env, is_subagent=True),
            retry_after_max_s=_resolve_retry_after_max_s(env),
            drain_timeout_s=configured_drain_s,
            effective_drain_timeout_s=effective_s,
            drain_timeout_clamped=clamped,
            exit_timeout_s=exit_timeout_s,
            drain_tail_s=tail_s,
            drain_margin_s=margin_s,
            drain_hold_timeout_s=resolve_drain_hold_timeout_s(env),
        )
