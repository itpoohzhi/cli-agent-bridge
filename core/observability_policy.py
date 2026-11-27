from __future__ import annotations

# Pure Zero-I/O observability policy: loopback gate, rate limit, allowlist.
# No I/O, no clocks, no mutable module state; caller owns the bucket dict.

import ipaddress
import math
from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType
from typing import cast

OBSERVABILITY_SCHEMA_VERSION = "1.0"
ADMISSION_ALLOWLIST_KEYS = (
    "active",
    "idle",
    "total",
    "limit",
    "max_idle_age_s",
    "overloaded_rejects",
)
P12_PGID_ALLOWLIST_KEYS = ("active", "quarantined", "bound")
_ROTATION_KEY_BLOCKLIST = ("path", "token", "secret", "detached_pgids")


def is_loopback_ip(peer_host: str | None) -> bool:
    """True only for loopback IPs, incl. IPv4-mapped IPv6; junk -> False."""
    raw = (peer_host or "").strip()
    stripped = raw[1:-1] if raw.startswith("[") and raw.endswith("]") else raw
    host = stripped.split("%", 1)[0]
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    mapped = cast("ipaddress.IPv4Address | None", getattr(addr, "ipv4_mapped", None))
    return bool(addr.is_loopback or (mapped is not None and mapped.is_loopback))


_ALLOWED_HEADER_VALS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "origin": ("",),
        "sec-fetch-site": ("", "none", "same-origin"),
        "x-forwarded-for": ("",),
        "forwarded": ("",),
    }
)


def _has_forbidden_security_headers(headers: object) -> bool:
    """Fail-closed header scan: reject invalid containers, duplicates, bad values."""
    try:
        items_fn = cast("Callable[[], Iterable[object]]", getattr(headers, "items"))
        raw = list(items_fn())
    except (AttributeError, TypeError):
        return True
    seen: set[str] = set()
    for e in raw:
        if not (isinstance(e, tuple) and len(p := cast("tuple[object, ...]", e)) == 2):
            return True
        name = str(p[0]).strip().lower()
        val = str(p[1]).strip().lower()
        if allowed := _ALLOWED_HEADER_VALS.get(name):
            if name in seen or val not in allowed:
                return True
            seen.add(name)
    return False


def is_observability_request_allowed(peer_host: str | None, headers: object) -> bool:
    """Loopback-only gate rejecting cross-site, proxied, and conflicting headers."""
    return is_loopback_ip(peer_host) and not _has_forbidden_security_headers(headers)


def step_token_bucket(
    state: dict[str, float],
    now_ts: float,
    rate_per_s: float = 10.0,
    burst: float = 20.0,
) -> bool:
    """Consume one token from the caller-owned bucket; True if allowed."""
    bad_cfg = not all(map(math.isfinite, (now_ts, rate_per_s, burst)))
    if bad_cfg or rate_per_s < 0.0 or burst < 1.0:
        raise ValueError("token bucket requires finite rate_per_s >= 0 and burst >= 1")
    tokens = float(state.get("tokens", burst))
    last_ts = float(state.get("last_ts", now_ts))
    elapsed = max(0.0, float(now_ts) - last_ts)
    tokens = min(float(burst), tokens + elapsed * float(rate_per_s))
    allowed = tokens >= 1.0
    state["tokens"] = tokens - 1.0 if allowed else tokens
    state["last_ts"] = float(now_ts)
    return allowed


def _numeric_or_zero(v: object, default: float) -> int | float:
    return v if type(v) is int or (type(v) is float and math.isfinite(v)) else default


def _project_counts(
    source: Mapping[str, object], keys: tuple[str, ...], float_key: str
) -> dict[str, int | float]:
    defaults: dict[str, int | float] = {float_key: 0.0}
    return {
        key: _numeric_or_zero(source.get(key), defaults.get(key, 0)) for key in keys
    }


def _project_rotation(source: Mapping[str, object]) -> dict[str, bool | int | float]:
    out: dict[str, bool | int | float] = {}
    for key, v in source.items():
        if any(map(key.lower().__contains__, _ROTATION_KEY_BLOCKLIST)):
            continue
        if isinstance(v, int) or (isinstance(v, float) and math.isfinite(v)):
            out[key] = v
    return out


def project_observability_payload(
    admission: Mapping[str, object],
    p12_pgid: Mapping[str, object],
    p13_rotation: Mapping[str, object],
    service: str = "hub",
) -> dict[str, object]:
    """Project exactly five top-level keys with strict per-section allowlists."""
    return {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "service": service,
        "admission": _project_counts(
            admission, ADMISSION_ALLOWLIST_KEYS, "max_idle_age_s"
        ),
        "p12_pgid": _project_counts(p12_pgid, P12_PGID_ALLOWLIST_KEYS, ""),
        "p13_rotation": _project_rotation(p13_rotation),
    }
