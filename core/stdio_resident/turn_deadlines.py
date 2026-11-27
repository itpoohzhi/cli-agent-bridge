"""Sliding timeout ladder wiring for resident stdio turns (AD-001, L-LIVE/v1)."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from core.runtime_env import ConfigError, env_bool
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.runtime_types import TurnTimeoutError as _BaseTurnTimeoutError
from core.timeout_ladder import (
    FLAG_TIMEOUT_LADDER,
    ActivityKind,
    SlidingActivityPolicy,
    TimeoutLadderConfig,
    load_timeout_ladder_config,
)

__all__ = [
    "DEFAULT_FIRST_PROGRESS_TIMEOUT_S",
    "DEFAULT_SAFETY_CAP_S",
    "DEFAULT_TURN_IDLE_TIMEOUT_S",
    "TurnTimeoutError",
    "_TurnDeadlines",
    "_resolve_deadlines",
]

DEFAULT_FIRST_PROGRESS_TIMEOUT_S: Final[float] = 720.0
DEFAULT_TURN_IDLE_TIMEOUT_S: Final[float] = 600.0
DEFAULT_SAFETY_CAP_S: Final[float] = 1800.0
_DEFAULT_POOL_TURN_IDLE_S: Final[float] = StdioPoolConfig.turn_idle_timeout_s
_DEFAULT_POOL_TURN_TOTAL_S: Final[float] = StdioPoolConfig.turn_total_timeout_s
_TIMEOUT_CODES: Final[dict[str, str]] = {
    "first_progress": "first_progress_timeout",
    "idle": "idle_timeout",
    "safety_cap": "safety_cap_timeout",
}


class TurnTimeoutError(_BaseTurnTimeoutError):
    """Typed timeout separating first-progress, idle, and safety cap."""

    http_status: int = 504

    def __init__(self, timeout_kind: str, message: str) -> None:
        self.timeout_kind: str = timeout_kind
        code = _TIMEOUT_CODES.get(timeout_kind, "turn_timeout")
        super().__init__(f"{code}: {message}", code=code)


@dataclass(slots=True)
class _TurnDeadlines:
    idle_s: float
    safety_deadline: float
    first_progress_deadline: float
    idle_deadline: float
    has_progress: bool = False
    policy: SlidingActivityPolicy | None = None
    _policy_now: list[float] | None = None

    def _sync_policy(self, now: float) -> SlidingActivityPolicy | None:
        if self.policy is not None and self._policy_now is not None:
            self._policy_now[0] = now
            return self.policy
        return None

    def record_useful(self, now: float, kind: ActivityKind = ActivityKind.CONTENT) -> None:
        if (policy := self._sync_policy(now)) is not None:
            self.idle_deadline = policy.record(kind)
            if kind in (ActivityKind.CONTENT, ActivityKind.REASONING, ActivityKind.TOOL_CALLS):
                self.has_progress = True
            return
        self.has_progress = True
        if now < self.safety_deadline:
            self.idle_deadline = max(self.idle_deadline, min(self.safety_deadline, now + self.idle_s))

    def next_timeout(self, now: float) -> float:
        if (policy := self._sync_policy(now)) is not None:
            if policy.is_expired():
                raise self.timeout_error(now)
            return policy.remaining()
        if now >= self.safety_deadline:
            raise TurnTimeoutError("safety_cap", "turn safety cap exceeded")
        active = min(self.idle_deadline if self.has_progress else self.first_progress_deadline, self.safety_deadline)
        if now >= active:
            kind = "idle" if self.has_progress else "first_progress"
            raise TurnTimeoutError(kind, f"resident process {kind} timeout exceeded")
        return active - now

    def timeout_error(self, now: float) -> TurnTimeoutError:
        if (policy := self._sync_policy(now)) is not None:
            reason = policy.expiry_reason()
            if reason == "safety_cap" or now >= self.safety_deadline:
                return TurnTimeoutError("safety_cap", "turn safety cap exceeded")
            if reason == "idle_timeout" or (reason is None and self.has_progress):
                return TurnTimeoutError("idle", "resident process idle timeout exceeded")
            return TurnTimeoutError("first_progress", "resident process first_progress timeout exceeded")
        active = self.idle_deadline if self.has_progress else self.first_progress_deadline
        if now >= self.safety_deadline or self.safety_deadline <= active:
            return TurnTimeoutError("safety_cap", "turn safety cap exceeded")
        kind = "idle" if self.has_progress else "first_progress"
        return TurnTimeoutError(kind, f"resident process {kind} timeout exceeded")


def _parse_pos_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) and parsed > 0.0 else None


def _pick_timeout(
    ctx: Mapping[str, Any], cfg: object, names: tuple[str, ...], env_key: str, env: Mapping[str, str]
) -> float | None:
    for name in names:
        if (val := _parse_pos_float(ctx.get(name))) is not None:
            return val
    for name in names:
        if (val := _parse_pos_float(getattr(cfg, name, None))) is not None:
            return val
    return _parse_pos_float(env.get(env_key))


def _load_timeout_ladder(env: Mapping[str, str]) -> TimeoutLadderConfig:
    try:
        return load_timeout_ladder_config(env)
    except ValueError:
        if env_bool(env, (FLAG_TIMEOUT_LADDER,), False):
            raise
        return TimeoutLadderConfig()


def _pick_ladder_override(
    ctx: Mapping[str, Any],
    cfg: object,
    names: tuple[str, ...],
    env_key: str,
    env: Mapping[str, str],
    class_default: float | None = None,
) -> float | None:
    for name in names:
        if (val := _parse_pos_float(ctx.get(name))) is not None:
            return val
    if (env_val := _parse_pos_float(env.get(env_key))) is not None:
        return env_val
    for name in names:
        if (val := _parse_pos_float(getattr(cfg, name, None))) is not None:
            if class_default is None or val != class_default:
                return val
    return None


def _parse_strict_total_timeout(ctx: Mapping[str, Any], cfg: object) -> tuple[float | None, bool]:
    if (raw := ctx.get("turn_total_timeout_s")) is not None:
        if (parsed := _parse_pos_float(raw)) is None:
            raise ConfigError(f"invalid turn_total_timeout_s in ctx: {raw!r}")
        return parsed, True
    if (raw := getattr(cfg, "turn_total_timeout_s", None)) is not None:
        if (parsed := _parse_pos_float(raw)) is None:
            raise ConfigError(f"invalid turn_total_timeout_s in cfg: {raw!r}")
        return (None, False) if parsed == _DEFAULT_POOL_TURN_TOTAL_S else (parsed, False)
    return None, False


def _pick_legacy_idle_timeout(ctx: Mapping[str, Any], cfg: object, env: Mapping[str, str]) -> float | None:
    if (val := _parse_pos_float(ctx.get("turn_idle_timeout_s"))) is not None:
        return val
    if (val := _parse_pos_float(ctx.get("idle_timeout_s"))) is not None:
        return val
    cfg_turn_idle = _parse_pos_float(getattr(cfg, "turn_idle_timeout_s", None))
    if cfg_turn_idle is not None and cfg_turn_idle != _DEFAULT_POOL_TURN_IDLE_S:
        return cfg_turn_idle
    if (val := _parse_pos_float(env.get("BRIDGE_STDIO_TURN_IDLE_TIMEOUT_S"))) is not None:
        return val
    if (val := _parse_pos_float(getattr(cfg, "idle_timeout_s", None))) is not None:
        return val
    return cfg_turn_idle


def _resolve_deadlines(
    cfg: object, ctx: Mapping[str, Any], now: float, *, environ: Mapping[str, str] | None = None
) -> _TurnDeadlines:
    env = os.environ if environ is None else environ
    explicit_total, total_from_ctx = _parse_strict_total_timeout(ctx, cfg)
    ladder = _load_timeout_ladder(env)
    if not ladder.enabled:
        idle_s = _pick_legacy_idle_timeout(ctx, cfg, env)
        idle_val = DEFAULT_TURN_IDLE_TIMEOUT_S if idle_s is None else idle_s
        first_raw = _pick_timeout(ctx, cfg, ("first_progress_timeout_s", "turn_first_progress_timeout_s"), "BRIDGE_STDIO_FIRST_PROGRESS_TIMEOUT_S", env)
        first_base = DEFAULT_FIRST_PROGRESS_TIMEOUT_S if first_raw is None else first_raw
        cap_raw = _pick_timeout(ctx, cfg, ("safety_cap_s", "turn_safety_cap_s"), "BRIDGE_STDIO_SAFETY_CAP_S", env)
        if cap_raw is not None:
            cap_val = min(cap_raw, explicit_total) if explicit_total is not None else cap_raw
        elif explicit_total is not None:
            cap_val = explicit_total
        else:
            cap_val = max(DEFAULT_SAFETY_CAP_S, idle_val, first_base)
        first_val = min(first_base, cap_val)
        eff_idle = min(idle_val, cap_val)
        safety_dl = now + cap_val
        return _TurnDeadlines(eff_idle, safety_dl, min(safety_dl, now + first_val), min(safety_dl, now + eff_idle))

    idle_ov = _pick_ladder_override(ctx, cfg, ("turn_idle_timeout_s",), "BRIDGE_STDIO_TURN_IDLE_TIMEOUT_S", env, _DEFAULT_POOL_TURN_IDLE_S)
    ctx_turn_idle = _parse_pos_float(ctx.get("turn_idle_timeout_s"))
    ctx_idle = _parse_pos_float(ctx.get("idle_timeout_s"))
    if ctx_turn_idle is not None:
        idle_val = ctx_turn_idle
    elif ctx_idle is not None:
        idle_val = ctx_idle
    elif idle_ov is not None:
        idle_val = idle_ov
    else:
        idle_val = ladder.effective_idle_s
    first_ov = _pick_ladder_override(ctx, cfg, ("first_progress_timeout_s", "turn_first_progress_timeout_s"), "BRIDGE_STDIO_FIRST_PROGRESS_TIMEOUT_S", env)
    first_val = ladder.effective_first_event_s if first_ov is None else first_ov
    cap_ov = _pick_ladder_override(ctx, cfg, ("safety_cap_s", "turn_safety_cap_s"), "BRIDGE_STDIO_SAFETY_CAP_S", env)
    if cap_ov is None:
        cap_val = min(ladder.safety_cap_s, explicit_total) if explicit_total is not None else max(ladder.safety_cap_s, first_val, idle_val)
    else:
        cap_val = min(cap_ov, explicit_total) if (total_from_ctx and explicit_total is not None) else cap_ov
    eff_first = min(first_val, cap_val)
    eff_idle = min(idle_val, cap_val)
    effective_cfg = TimeoutLadderConfig(
        enabled=True,
        connect_timeout_s=min(ladder.connect_timeout_s, cap_val),
        first_event_timeout_s=eff_first,
        idle_timeout_s=eff_idle,
        read_chunk_timeout_s=eff_idle,
        safety_cap_s=cap_val,
        legacy_first_event_s=min(ladder.legacy_first_event_s, cap_val),
        legacy_idle_s=min(ladder.legacy_idle_s, cap_val),
        legacy_read_chunk_s=min(ladder.legacy_read_chunk_s, cap_val),
    )
    clock_box = [now]
    policy = SlidingActivityPolicy(effective_cfg, lambda: clock_box[0])
    safety_dl = now + cap_val
    return _TurnDeadlines(
        eff_idle,
        safety_dl,
        min(safety_dl, now + eff_first),
        min(safety_dl, now + eff_idle),
        policy=policy,
        _policy_now=clock_box,
    )
