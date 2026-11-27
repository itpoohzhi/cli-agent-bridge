from __future__ import annotations

# Hub loopback GET /v1/observability adapter (P0-S1): fail-closed kill-switch,
# loopback/CSRF gate, and per-server rate limiter; payload projected by pure policy.

import os
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final, cast

from core.http_server_error import resolved_config_path
from core.log_rotation_adapters import DynamicJsonBoolCache, get_rotation_snapshot
from core.observability_policy import (
    is_observability_request_allowed,
    project_observability_payload,
    step_token_bucket,
)
from core.p12_flag_and_params import resolve_flag

FLAG_LOOPBACK_OBSERVABILITY: Final[str] = "BRIDGE_LOOPBACK_OBSERVABILITY_ENABLED"

# Sole mutable module state lives inside these instances (no dict/list/set literals here).
_FLAG_CACHE = DynamicJsonBoolCache()
_LIMITER_LOCK = threading.Lock()


class ObservabilityRateLimiter:
    """Single owner of the mutable token-bucket state for one server instance."""

    def __init__(self, rate_per_s: float = 10.0, burst: float = 20.0) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._bucket: dict[str, float] = {}
        self._rate_per_s: float = float(rate_per_s)
        self._burst: float = float(burst)

    def allow(self, now_ts: float | None = None) -> bool:
        """Consume one token under the private lock; True when the request passes."""
        now = time.monotonic() if now_ts is None else now_ts
        with self._lock:
            return step_token_bucket(
                self._bucket, now, rate_per_s=self._rate_per_s, burst=self._burst
            )


def is_observability_enabled(config_path: Path | None = None) -> bool:
    """Read the kill-switch fail-closed: any JSON/I/O failure resolves to False."""
    doc, invalid = _FLAG_CACHE.read(resolved_config_path(config_path))
    return resolve_flag(
        FLAG_LOOPBACK_OBSERVABILITY, doc, os.environ, json_invalid=invalid
    ).enabled


def _error_envelope(message: str, err_type: str, code: int) -> dict[str, object]:
    """Canonical hub error envelope (matches server.py auth 401 shape)."""
    return {"error": {"message": message, "type": err_type, "code": code}}


def _peer_host(handler: Any) -> str | None:  # pyright: ignore[reportExplicitAny, reportAny]
    """Peer IP from handler.client_address; malformed addresses fail closed."""
    addr = cast("object", handler.client_address)
    return (
        str(cast("tuple[object, ...]", addr)[0])
        if isinstance(addr, tuple) and addr
        else None
    )


def _server_limiter(server: object) -> ObservabilityRateLimiter:
    """Get-or-create the per-server limiter under lock; no global singleton."""
    with _LIMITER_LOCK:
        existing = cast("object", getattr(server, "_observability_limiter", None))
        if isinstance(existing, ObservabilityRateLimiter):
            return existing
        created = ObservabilityRateLimiter()
        try:
            setattr(server, "_observability_limiter", created)
        except (AttributeError, TypeError):
            pass  # read-only/frozen server mock: use the fresh instance
        return created


def _active_limiter(
    handler: Any,  # pyright: ignore[reportExplicitAny, reportAny]
    limiter: ObservabilityRateLimiter | None,
) -> ObservabilityRateLimiter:
    srv = cast("object", handler.server)
    return limiter if limiter is not None else _server_limiter(srv)


def _admission_snapshot(
    handler: Any,  # pyright: ignore[reportExplicitAny, reportAny]
) -> Mapping[str, object]:
    """Read-only admission counters; safe empty fallback for mock servers."""
    server = cast("object", handler.server)
    snapshot_fn = cast("object", getattr(server, "admission_snapshot", None))
    raw = cast("Callable[[], object]", snapshot_fn)() if callable(snapshot_fn) else None
    return cast("Mapping[str, object]", raw) if isinstance(raw, Mapping) else {}


def _check_access(
    handler: Any,  # pyright: ignore[reportExplicitAny, reportAny]
    config_path: Path | None,
    limiter: ObservabilityRateLimiter | None,
) -> tuple[int, str, str, dict[str, str] | None] | None:
    if not is_observability_enabled(config_path):
        return (401, "unauthorized", "auth_error", None)
    if not is_observability_request_allowed(_peer_host(handler), handler.headers):  # pyright: ignore[reportAny]
        return (403, "forbidden", "forbidden", {"Cache-Control": "no-store"})
    if not _active_limiter(handler, limiter).allow():
        return (
            429,
            "rate limit exceeded",
            "rate_limit_exceeded",
            {"Retry-After": "1", "Cache-Control": "no-store"},
        )
    return None


def serve_observability_get(
    handler: Any,  # pyright: ignore[reportExplicitAny, reportAny]
    p12_seam: Any,  # pyright: ignore[reportExplicitAny, reportAny]
    config_path: Path | None = None,
    limiter: ObservabilityRateLimiter | None = None,
) -> None:
    """Serve GET /v1/observability: 401 disabled, 403 non-loopback, 429 limited, else 200."""
    send = cast("Callable[..., object]", handler._send)
    denied = _check_access(handler, config_path, limiter)
    if denied is not None:
        code, message, err_type, extra = denied
        _ = send(code, _error_envelope(message, err_type, code), extra_headers=extra)
    else:
        seam_counts = cast("Callable[[], object]", p12_seam.snapshot_counts)
        payload = project_observability_payload(
            _admission_snapshot(handler),
            cast("Mapping[str, object]", seam_counts()),
            get_rotation_snapshot("hub"),
            service="hub",
        )
        _ = send(200, payload, extra_headers={"Cache-Control": "no-store"})
