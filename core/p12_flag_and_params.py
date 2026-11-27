"""Pure Zero-I/O flag precedence (dynamic JSON > env > False) and sourced cleanup parameter validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

FLAG_AGY_PGID_QUARANTINE: Final[str] = "AGY_BRIDGE_PGID_QUARANTINE_ENABLED"
FLAG_ZEN_PGID_QUARANTINE: Final[str] = "OPENCODE_ZEN_BRIDGE_PGID_QUARANTINE_ENABLED"
FLAG_AGY_ORPHAN_COORDINATOR: Final[str] = "AGY_ORPHAN_COORDINATOR_ENABLED"
FLAG_HUB_NONDETACHED_CANCEL: Final[str] = "BRIDGE_NONDETACHED_CLIENT_CANCEL_ENABLED"
FLAG_HUB_RESIDENT_WIRING: Final[str] = "BRIDGE_RESIDENT_CANCEL_WIRING_ENABLED"
FLAG_HUB_TURN_MODE_PROPAGATION: Final[str] = "BRIDGE_TURN_MODE_PROPAGATION_ENABLED"
FLAG_GEO_PRERELAY_DISCONNECT: Final[str] = "GEOROUTER_PRERELAY_DISCONNECT_ENABLED"

ALL_P12_FLAGS: Final[tuple[str, ...]] = (
    FLAG_AGY_PGID_QUARANTINE,
    FLAG_ZEN_PGID_QUARANTINE,
    FLAG_AGY_ORPHAN_COORDINATOR,
    FLAG_HUB_NONDETACHED_CANCEL,
    FLAG_HUB_RESIDENT_WIRING,
    FLAG_HUB_TURN_MODE_PROPAGATION,
    FLAG_GEO_PRERELAY_DISCONNECT,
)

PGID_PROVENANCE_GATED_FLAGS: Final[frozenset[str]] = frozenset(
    {FLAG_AGY_PGID_QUARANTINE, FLAG_ZEN_PGID_QUARANTINE}
)

_TRUE_STRINGS: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSE_STRINGS: Final[frozenset[str]] = frozenset({"0", "false", "no", "off", ""})


class ParamSourceMissingError(ValueError):
    """Raised when a cleanup timing parameter lacks explicit provenance."""


@dataclass(frozen=True)
class SourcedParam:
    """Single timing or limit parameter carrying explicit provenance."""

    value: float
    source: str


@dataclass(frozen=True)
class CleanupParamSnapshot:
    """Sourced PGID escalation and polling parameters for one bridge service."""

    service: str
    term_grace_s: SourcedParam | None
    poll_interval_s: SourcedParam | None
    leader_wait_s: SourcedParam | None


@dataclass(frozen=True)
class ValidatedCleanupParams:
    """Validated non-negative cleanup parameters with guaranteed provenance."""

    service: str
    term_grace_s: float
    poll_interval_s: float
    leader_wait_s: float
    sources: tuple[str, str, str]


@dataclass(frozen=True)
class FlagResolution:
    """Deterministic flag evaluation result with explicit reason."""

    name: str
    enabled: bool
    origin: str


def parse_bool_strict(raw: object) -> bool | None:
    """Parse boolean token fail-closed; returns None on unrecognized input."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        if raw in (0, 1):
            return bool(raw)
        return None
    if isinstance(raw, str):
        norm = raw.strip().lower()
        if norm in _TRUE_STRINGS:
            return True
        if norm in _FALSE_STRINGS:
            return False
    return None


def _lookup_json_flag(
    name: str,
    json_snapshot: Mapping[str, object] | None,
) -> tuple[bool, bool | None]:
    if json_snapshot is None:
        return False, None
    for key in (name, name.lower()):
        if key in json_snapshot:
            return True, parse_bool_strict(json_snapshot[key])
    return False, None


def resolve_flag(
    name: str,
    json_snapshot: Mapping[str, object] | None,
    env_snapshot: Mapping[str, str] | None,
    *,
    json_invalid: bool = False,
) -> FlagResolution:
    """Resolve feature flag with strict dynamic JSON > env > False precedence."""
    if json_invalid:
        return FlagResolution(name=name, enabled=False, origin="json_invalid_fail_closed")
    found, parsed = _lookup_json_flag(name, json_snapshot)
    if found:
        if parsed is None:
            return FlagResolution(name=name, enabled=False, origin="json_invalid_value_fail_closed")
        return FlagResolution(name=name, enabled=parsed, origin="dynamic_json")
    if env_snapshot is not None and name in env_snapshot:
        env_parsed = parse_bool_strict(env_snapshot[name])
        if env_parsed is not None:
            return FlagResolution(name=name, enabled=env_parsed, origin="env")
        return FlagResolution(name=name, enabled=False, origin="env_invalid_fail_closed")
    return FlagResolution(name=name, enabled=False, origin="default_false")


def _validate_one_param(param: SourcedParam | None, label: str, *, allow_zero: bool) -> tuple[float, str]:
    if param is None:
        raise ParamSourceMissingError(f"{label}: missing parameter")
    src = param.source.strip() if isinstance(param.source, str) else ""
    if not src:
        raise ParamSourceMissingError(f"{label}: missing provenance source")
    val = float(param.value)
    if val < 0.0 or (not allow_zero and val <= 0.0):
        raise ParamSourceMissingError(f"{label}: non-positive value {val}")
    return val, src


def validate_cleanup_params(snapshot: CleanupParamSnapshot) -> ValidatedCleanupParams:
    """Validate that every cleanup timing parameter has explicit provenance."""
    if not snapshot.service.strip():
        raise ParamSourceMissingError("service: empty service name")
    term_v, term_s = _validate_one_param(snapshot.term_grace_s, "term_grace_s", allow_zero=True)
    poll_v, poll_s = _validate_one_param(snapshot.poll_interval_s, "poll_interval_s", allow_zero=False)
    wait_v, wait_s = _validate_one_param(snapshot.leader_wait_s, "leader_wait_s", allow_zero=True)
    return ValidatedCleanupParams(
        service=snapshot.service.strip(),
        term_grace_s=term_v,
        poll_interval_s=poll_v,
        leader_wait_s=wait_v,
        sources=(term_s, poll_s, wait_s),
    )


def resolve_flag_with_params(
    name: str,
    json_snapshot: Mapping[str, object] | None,
    env_snapshot: Mapping[str, str] | None,
    params_snapshot: CleanupParamSnapshot | None,
    *,
    json_invalid: bool = False,
) -> FlagResolution:
    """Resolve flag; ParamSourceMissing forces False ONLY for PGID flags (#1-#2)."""
    base = resolve_flag(name, json_snapshot, env_snapshot, json_invalid=json_invalid)
    if not base.enabled or name not in PGID_PROVENANCE_GATED_FLAGS:
        return base
    if params_snapshot is None:
        return FlagResolution(name=name, enabled=False, origin="param_source_missing")
    try:
        _ = validate_cleanup_params(params_snapshot)
    except ParamSourceMissingError:
        return FlagResolution(name=name, enabled=False, origin="param_source_missing")
    return base
