"""Route circuit-breaker configuration, provider key lookup, and shared state records."""

from __future__ import annotations

import math
import os
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

PROVIDER_AUTH_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "invalid_api_key",
        "expired_token",
        "account_suspended",
        "account_disabled",
        "org_disabled",
        "billing",
        "insufficient_quota",
        "quota_exceeded",
    }
)
ROUTE_LOCAL_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "model_not_found",
        "unsupported_model",
        "model_access_denied",
        "deployment_not_found",
    }
)
_UNPROVEN_DEQUE_MAX: Final[int] = 64
_DEFAULT_THRESHOLD: Final[int] = 3
_DEFAULT_COOLDOWN_S: Final[float] = 90.0
_MIN_COOLDOWN_S: Final[float] = 60.0
_MAX_COOLDOWN_S: Final[float] = 120.0
_DEFAULT_WINDOW_S: Final[float] = 300.0
_LEGACY_THRESHOLD: Final[int] = 3
_LEGACY_COOLDOWN_S: Final[float] = 30.0

RouteTupleKey = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class RouteCBConfig:
    """Validated route circuit-breaker configuration."""

    enabled: bool = True
    failure_threshold: int = _DEFAULT_THRESHOLD
    cooldown_s: float = _DEFAULT_COOLDOWN_S
    window_s: float = _DEFAULT_WINDOW_S
    single_route_protect: bool = False
    events_enabled: bool = True


@dataclass(frozen=True, slots=True)
class FailureOutcome:
    """Normalized outcome passed to RouteCB.record_failure."""

    status: int | None = None
    error: BaseException | None = None
    detail: str = ""
    reason: str = ""
    route_count: int = 0


@dataclass(slots=True)
class RouteProbeLease:
    """Single-flight half-open lease handle released via finally."""

    key: RouteTupleKey
    provider_lease: bool = False
    tuple_lease: bool = False
    done: bool = False
    route_count: int = 0


@dataclass(slots=True)
class _TupleState:
    failures: int = 0
    first_fail_ts: float | None = None
    open_until: float | None = None
    probe_in_flight: bool = False
    open_status: int | None = None


@dataclass(slots=True)
class _ProviderState:
    open_until: float | None = None
    probe_in_flight: bool = False
    unproven: deque[tuple[RouteTupleKey, float]] = field(
        default_factory=lambda: deque(maxlen=_UNPROVEN_DEQUE_MAX)
    )


def is_route_cb_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return False only when BRIDGE_ROUTE_CB_ENABLED explicitly disables new CB."""
    raw = (os.environ if env is None else env).get("BRIDGE_ROUTE_CB_ENABLED")
    if raw is None or not raw.strip():
        return True
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _parse_bool(src: Mapping[str, str], key: str, default: bool) -> bool:
    val = src.get(key, "").strip().lower()
    if val in {"true", "1", "yes", "on"}:
        return True
    if val in {"false", "0", "no", "off"}:
        return False
    return default


def _parse_int(src: Mapping[str, str], key: str, default: int, min_v: int) -> int:
    raw = src.get(key)
    if raw is None:
        return default
    try:
        val = int(raw.strip())
    except ValueError:
        return default
    return val if val >= min_v else default


def _parse_float(
    src: Mapping[str, str], key: str, default: float, bounds: tuple[float, float | None]
) -> float:
    raw = src.get(key)
    if raw is None:
        return default
    try:
        val = float(raw.strip())
    except ValueError:
        return default
    hi = bounds[1]
    if not math.isfinite(val) or val < bounds[0] or (hi is not None and val > hi):
        return default
    return val


def load_route_cb_config(env: Mapping[str, str] | None = None) -> RouteCBConfig:
    """Load strictly either BRIDGE_ROUTE_CB_* or legacy BRIDGE_TRANSPORT_CIRCUIT_*."""
    src = os.environ if env is None else env
    events_enabled = _parse_bool(src, "BRIDGE_ROUTE_CB_EVENTS", True)
    if not is_route_cb_enabled(src):
        return RouteCBConfig(
            enabled=False,
            failure_threshold=_parse_int(
                src, "BRIDGE_TRANSPORT_CIRCUIT_FAILURE_THRESHOLD", _LEGACY_THRESHOLD, 1
            ),
            cooldown_s=_parse_float(
                src,
                "BRIDGE_TRANSPORT_CIRCUIT_COOLDOWN_S",
                _LEGACY_COOLDOWN_S,
                (0.0, None),
            ),
            window_s=_DEFAULT_WINDOW_S,
            single_route_protect=False,
            events_enabled=events_enabled,
        )
    return RouteCBConfig(
        enabled=True,
        failure_threshold=_parse_int(
            src, "BRIDGE_ROUTE_CB_FAILURE_THRESHOLD", _DEFAULT_THRESHOLD, 1
        ),
        cooldown_s=_parse_float(
            src,
            "BRIDGE_ROUTE_CB_COOLDOWN_S",
            _DEFAULT_COOLDOWN_S,
            (_MIN_COOLDOWN_S, _MAX_COOLDOWN_S),
        ),
        window_s=_parse_float(
            src, "BRIDGE_ROUTE_CB_WINDOW_S", _DEFAULT_WINDOW_S, (1e-6, None)
        ),
        single_route_protect=_parse_bool(
            src, "BRIDGE_ROUTE_CB_SINGLE_ROUTE_PROTECTION", False
        ),
        events_enabled=events_enabled,
    )


def resolve_provider(route: Any, spec: Any) -> str:
    """Resolve logical provider identifier for route spec without touching credentials."""
    prov = getattr(spec, "provider", None)
    if isinstance(prov, str) and prov:
        return prov
    registries = getattr(getattr(route, "host", None), "BACKENDS", None)
    adapter = registries.get(spec.backend) if isinstance(registries, Mapping) else None
    cfg = getattr(adapter, "config", None) if adapter is not None else None
    if isinstance(cfg, Mapping):
        for key in ("provider", "provider_id"):
            val = cfg.get(key)
            if isinstance(val, str) and val:
                return val
    return spec.backend or "unknown"
