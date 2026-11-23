"""Pure strict Anthropic 5.5 gate for AGY model routing."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from types import MappingProxyType

CONTRACT_VERSION = "agy-anthropic-5.5-v2"
ENABLED_FLAG_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})
EFFORT_SUFFIXES: tuple[str, ...] = ("low", "medium", "high")
ALLOWED_AGY_CLAUDE_IDS: tuple[str, ...] = (
    "claude-sonnet-5-5",
    "claude-sonnet-5-5-low",
    "claude-sonnet-5-5-medium",
    "claude-sonnet-5-5-high",
    "claude-sonnet-5-5-thinking",
    "claude-opus-5-5",
    "claude-opus-5-5-low",
    "claude-opus-5-5-medium",
    "claude-opus-5-5-high",
    "claude-opus-5-5-thinking",
)
CANONICAL_FAMILY_IDS: MappingProxyType[str, tuple[str, ...]] = MappingProxyType(
    {
        "claude-sonnet-5-5": (
            "claude-sonnet-5-5",
            "claude-sonnet-5-5-low",
            "claude-sonnet-5-5-medium",
            "claude-sonnet-5-5-high",
            "claude-sonnet-5-5-thinking",
        ),
        "claude-opus-5-5": (
            "claude-opus-5-5",
            "claude-opus-5-5-low",
            "claude-opus-5-5-medium",
            "claude-opus-5-5-high",
            "claude-opus-5-5-thinking",
        ),
    }
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_SPINNER_RE = re.compile(
    r"^[\u2800-\u28ff\s]*Fetching available models\.{0,3}\s*"
)
_MODEL_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]*-[a-z0-9._-]*[a-z0-9]")


@dataclass(frozen=True)
class GateDecision:
    """Immutable result of resolving a requested model against live models."""

    canonical_model: str
    available: bool
    upstream_model: str | None
    reason: str
    live_models_hash: str
    efforts: tuple[str, ...] = ("off",)
    effective_effort: str = "off"


def is_anthropic_flag_enabled(raw: str | None) -> bool:
    """Parse shared truthy feature-flag values across all layers."""
    return isinstance(raw, str) and raw.strip().lower() in ENABLED_FLAG_VALUES


def canonicalize_claude_model(model_id: str) -> str | None:
    """Return the canonical family for an explicitly allowed Claude 5.5 ID."""
    for canonical_model, family_ids in CANONICAL_FAMILY_IDS.items():
        if model_id in family_ids:
            return canonical_model
    return None


def is_forbidden_claude_id(model_id: str) -> bool:
    """Reject every ID outside the exact strict 5.5 allowlist."""
    return model_id not in ALLOWED_AGY_CLAUDE_IDS


def parse_agy_models_output(raw_text: str) -> tuple[str, ...]:
    """Parse unique model IDs from line-oriented ``agy models`` output."""
    models: list[str] = []
    seen: set[str] = set()
    cleaned = _ANSI_RE.sub("", raw_text).replace("\r\n", "\n")
    for raw_line in cleaned.split("\n"):
        segments = [
            _SPINNER_RE.sub("", seg).strip() for seg in raw_line.split("\r")
        ]
        non_empty = [seg for seg in segments if seg]
        if not non_empty:
            continue
        line = non_empty[-1]
        if line.startswith("#"):
            continue
        line = line.lstrip("| \t")
        if line.startswith(("- ", "* ", "\u2022 ")):
            line = line[2:].lstrip()
        if not line or line.startswith("#"):
            continue
        token = line.split(None, 1)[0]
        if _MODEL_ID_PATTERN.fullmatch(token) is None or token in seen:
            continue
        seen.add(token)
        models.append(token)
    return tuple(models)


def _live_models_hash(live_models: tuple[str, ...] | list[str]) -> str:
    normalized = "\n".join(sorted(frozenset(live_models)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_claude_effort(
    requested_effort: str | None,
) -> tuple[bool, str | None, str]:
    """Validate effort input; reject xhigh/max and clamp supported values."""
    if requested_effort in (None, "", "off", "low", "medium", "high"):
        return (True, "off", "ok_clamped_off")
    if requested_effort in ("xhigh", "max"):
        return (False, None, "unsupported_reasoning_effort")
    return (False, None, "invalid_effort")


def _candidate_order(
    requested_model: str, canonical_model: str, requested_effort: str | None
) -> tuple[str, ...]:
    desired_eff = (
        requested_effort if requested_effort in EFFORT_SUFFIXES else "high"
    )
    if requested_model in (canonical_model, f"{canonical_model}-thinking"):
        ordered = [
            canonical_model,
            f"{canonical_model}-{desired_eff}",
            f"{canonical_model}-thinking",
        ]
    else:
        ordered = [
            requested_model,
            canonical_model,
            f"{canonical_model}-thinking",
        ]
    for suffix in ("high", "medium", "low"):
        variant = f"{canonical_model}-{suffix}"
        if variant not in ordered:
            ordered.append(variant)
    return tuple(ordered)


def _decision(
    canonical_model: str,
    available: bool,
    upstream_model: str | None,
    reason: str,
    live_models_hash: str,
) -> GateDecision:
    return GateDecision(
        canonical_model=canonical_model,
        available=available,
        upstream_model=upstream_model,
        reason=reason,
        live_models_hash=live_models_hash,
    )


def resolve_exact_5_5_upstream(
    requested_model: str,
    live_models: tuple[str, ...] | list[str],
    requested_effort: str | None = None,
) -> GateDecision:
    """Resolve a strict 5.5 request, preferring non-thinking upstream IDs."""
    models_hash = _live_models_hash(live_models)
    canonical_model = canonicalize_claude_model(requested_model)
    if canonical_model is None:
        return _decision(
            str(requested_model),
            False,
            None,
            "forbidden_or_unknown_model",
            models_hash,
        )
    ok_effort, _eff, effort_reason = validate_claude_effort(requested_effort)
    if not ok_effort:
        return _decision(
            canonical_model, False, None, effort_reason, models_hash
        )
    available_models = frozenset(live_models)
    for candidate in _candidate_order(
        requested_model, canonical_model, requested_effort
    ):
        if candidate in available_models:
            return _decision(canonical_model, True, candidate, "ok", models_hash)
    return _decision(
        canonical_model, False, None, "missing_5_5_on_account", models_hash
    )
