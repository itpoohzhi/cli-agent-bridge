from __future__ import annotations

# Pure Zero-I/O observability policy: loopback gate, rate limit, allowlist.
# No I/O, no clocks, no mutable module state; caller owns the bucket dict.

import ipaddress
import math
from collections.abc import Iterable, Mapping
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


def _header_map(headers: object) -> dict[str, str]:
    items_fn = getattr(headers, "items", None)
    raw_items = cast("Iterable[object]", items_fn()) if callable(items_fn) else ()
    out: dict[str, str] = {}
    for entry in raw_items:
        if isinstance(entry, tuple):
            pair = cast("tuple[object, ...]", entry)
            if len(pair) == 2:
                out[str(pair[0]).lower()] = str(pair[1])
    return out


def is_observability_request_allowed(peer_host: str | None, headers: object) -> bool:
    """Loopback-only gate rejecting cross-site and proxied requests."""
    lowered = _header_map(headers)
    fetch_site = lowered.get("sec-fetch-site", "").strip().lower()
    proxied = any(
        lowered.get(hdr, "").strip() for hdr in ("x-forwarded-for", "forwarded")
    )
    return (
        is_loopback_ip(peer_host)
        and not lowered.get("origin", "").strip()
        and fetch_site in ("", "none", "same-origin")
        and not proxied
    )


def step_token_bucket(
    state: dict[str, float],
    now_ts: float,
    rate_per_s: float = 10.0,
    burst: float = 20.0,
) -> bool:
    """Consume one token from the caller-owned bucket; True if allowed."""
    if (
        not all(math.isfinite(v) for v in (now_ts, rate_per_s, burst))
        or rate_per_s < 0.0
        or burst < 1.0
    ):
        raise ValueError("token bucket requires finite rate_per_s >= 0 and burst >= 1")
    tokens = float(state.get("tokens", burst))
    last_ts = float(state.get("last_ts", now_ts))
    elapsed = max(0.0, float(now_ts) - last_ts)
    tokens = min(float(burst), tokens + elapsed * float(rate_per_s))
    allowed = tokens >= 1.0
    state["tokens"] = tokens - 1.0 if allowed else tokens
    state["last_ts"] = float(now_ts)
    return allowed


def _numeric_or_zero(value: object, default: float) -> int | float:
    return (
        value
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else default
    )


def _project_counts(
    source: Mapping[str, object], keys: tuple[str, ...], float_key: str
) -> dict[str, int | float]:
    return {
        key: _numeric_or_zero(source.get(key), 0.0 if key == float_key else 0)
        for key in keys
    }


def _project_rotation(source: Mapping[str, object]) -> dict[str, bool | int | float]:
    out: dict[str, bool | int | float] = {}
    for key, value in source.items():
        lowered = key.lower()
        if any(blocked in lowered for blocked in _ROTATION_KEY_BLOCKLIST):
            continue
        if isinstance(value, (bool, int, float)):
            out[key] = value
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
