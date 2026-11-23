"""Runtime support for Anthropic turns and model-catalog filtering."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import inspect
import os
from pathlib import Path
from typing import Protocol

from core.agy_anthropic_gate import (
    canonicalize_claude_model,
    is_anthropic_flag_enabled,
    validate_claude_effort,
)
from core.agy_anthropic_probe import AgyAnthropicProbe, ProbeConfig
from core.effortless_policy import effort_cli_args


class _ProbeSnapshot(Protocol):
    @property
    def available(self) -> bool: ...
    @property
    def upstream_model(self) -> str | None: ...
    @property
    def reason(self) -> str: ...


class _ProbeLike(Protocol):
    def probe(self, model_id: str) -> _ProbeSnapshot: ...


__all__ = [
    "AgyAnthropicProbe",
    "BridgeAnthropicResolution",
    "ProbeConfig",
    "catalog_model_order",
    "canonicalize_claude_model",
    "effort_cli_args",
    "filter_anthropic_catalog_order",
    "is_bridge_anthropic_enabled",
    "read_allowed_models",
    "resolve_anthropic_turn",
    "validate_claude_effort",
]


@dataclass(frozen=True)
class BridgeAnthropicResolution:
    bypass: bool
    available: bool
    upstream_model: str | None
    effective_effort: str | None
    http_status: int
    error_type: str
    reason: str
    extra_env: dict[str, str]


def is_bridge_anthropic_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return is_anthropic_flag_enabled(source.get("BRIDGE_AGY_ANTHROPIC_ENABLED"))


def _bypass(model_id: str) -> BridgeAnthropicResolution:
    return BridgeAnthropicResolution(
        bypass=True,
        available=True,
        upstream_model=model_id,
        effective_effort=None,
        http_status=200,
        error_type="",
        reason="bypass_non_claude",
        extra_env={},
    )


def _failure(status: int, error_type: str, reason: str) -> BridgeAnthropicResolution:
    return BridgeAnthropicResolution(
        bypass=False,
        available=False,
        upstream_model=None,
        effective_effort=None,
        http_status=status,
        error_type=error_type,
        reason=reason,
        extra_env={},
    )


def _accepts_requested_effort(probe: _ProbeLike) -> bool:
    try:
        params = inspect.signature(probe.probe).parameters
    except (TypeError, ValueError):
        return False
    return "requested_effort" in params or any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    )


def resolve_anthropic_turn(
    model_id: str,
    requested_effort: object,
    probe: _ProbeLike,
    *,
    env: Mapping[str, str] | None = None,
) -> BridgeAnthropicResolution:
    if not model_id.startswith("claude-"):
        return _bypass(model_id)
    if canonicalize_claude_model(model_id) is None:
        return _failure(400, "model_not_allowed", "forbidden_or_unknown_model")
    if not is_bridge_anthropic_enabled(env):
        return _failure(503, "model_unavailable", "feature_flag_disabled")
    if not (requested_effort is None or isinstance(requested_effort, str)):
        return _failure(400, "unsupported_reasoning_effort", "invalid_effort")
    ok, _eff, err_msg = validate_claude_effort(requested_effort)
    if not ok:
        return _failure(400, "unsupported_reasoning_effort", err_msg)
    if requested_effort and _accepts_requested_effort(probe):
        snap = probe.probe(model_id, requested_effort=requested_effort)  # type: ignore[call-arg]
    else:
        snap = probe.probe(model_id)
    if not snap.available:
        return _failure(503, "model_unavailable", snap.reason)
    return BridgeAnthropicResolution(
        bypass=False,
        available=True,
        upstream_model=snap.upstream_model,
        effective_effort="off",
        http_status=200,
        error_type="",
        reason="ok",
        extra_env={"AGY_ANTHROPIC_ENABLED": "1"},
    )


def filter_anthropic_catalog_order(
    order: list[str],
    probe: _ProbeLike | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    if not is_bridge_anthropic_enabled(env) or probe is None:
        return [mid for mid in order if not mid.startswith("claude-")]
    return [
        mid
        for mid in order
        if not mid.startswith("claude-") or probe.probe(mid).available
    ]


def read_allowed_models(path: str) -> frozenset[str]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return frozenset()
    lines = (line.strip() for line in text.splitlines())
    return frozenset(line for line in lines if line and not line.startswith("#"))


def catalog_model_order(
    default_model: str,
    fleet_order: Sequence[str],
    allowed_path: str,
    log_fn: Callable[[str], None],
) -> list[str]:
    order = [default_model] + [mid for mid in fleet_order if mid != default_model]
    allowed = read_allowed_models(allowed_path)
    if not allowed:
        log_fn(
            f"models catalog: allowlist {allowed_path} missing or empty, "
            + "generation-guard filter disabled"
        )
        return order
    return [mid for mid in order if mid in allowed]
