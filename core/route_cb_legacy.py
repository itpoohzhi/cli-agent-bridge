"""Legacy-error classification, Retry-After header normalization, and 429 quota helpers."""
from __future__ import annotations

from typing import Any

from core.route_attempts import RouteFailover, RouteRefusal


def refusal_detail(error: RouteRefusal) -> str:
    """First 4096 chars of a refusal body for lowercase marker classification."""
    raw = error.response_body
    if isinstance(raw, (bytes, bytearray)):
        return raw[:4096].decode("utf-8", errors="ignore")
    return str(raw)[:4096]


def _with_retry_after(error: RouteRefusal, retry_after_s: int) -> RouteRefusal:
    """Add or raise Retry-After header on a RouteRefusal."""
    headers = list(error.response_headers)
    existing = 0
    for k, v in headers:
        if k.lower() == "retry-after":
            try:
                existing = max(existing, int(float(v)))
            except ValueError:
                pass
    if retry_after_s > existing:
        headers = [(k, v) for k, v in headers if k.lower() != "retry-after"]
        headers.append(("Retry-After", str(retry_after_s)))
    return RouteRefusal(error.status_code, tuple(headers), error.response_body)


def apply_quota_429(error: RouteRefusal, qdec: Any, host: Any, origin_route_id: str) -> RouteRefusal:
    """Record quota cooldown in the host cache and augment the refusal with Retry-After."""
    if (cache := getattr(host, "_QUOTA_CB_CACHE", None)) is not None and hasattr(cache, "record_429"):
        cache.record_429(origin_route_id, ttl_s=qdec.reset_s, reason=qdec.reason)
    return _with_retry_after(error, max(60, int(qdec.reset_s)))


def legacy_failure_action(error: BaseException, failover: RouteFailover) -> str:
    """Classify legacy breaker action for an error: quota, slot_refusal, ignore, or route."""
    if isinstance(error, RouteRefusal):
        if error.status_code == 429:
            return "quota"
        if failover.opt_in and error.status_code in failover.statuses:
            return "slot_refusal"
        if 400 <= error.status_code < 500 and error.status_code not in (403, 429):
            return "ignore"
    return "route"
