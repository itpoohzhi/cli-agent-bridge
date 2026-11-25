"""Unit tests for core/route_cb_legacy.py (PR B4b)."""
from __future__ import annotations

from types import SimpleNamespace

from core.route_attempts import RouteFailover, RouteRefusal
from core.route_cb_legacy import _with_retry_after, apply_quota_429, legacy_failure_action, refusal_detail


def test_b4b_refusal_detail_and_retry_after() -> None:
    assert refusal_detail(RouteRefusal(403, (), b"x" * 5000)) == "x" * 4096
    assert refusal_detail(RouteRefusal(403, (), "y" * 5000)) == "y" * 4096
    kept = _with_retry_after(RouteRefusal(429, (("Retry-After", "120"), ("X-A", "1")), b""), 60)
    bumped = _with_retry_after(RouteRefusal(429, (("retry-after", "30"), ("retry-after", "bad"), ("X-A", "1")), b""), 60)
    assert dict(kept.response_headers)["Retry-After"] == "120"
    assert dict(bumped.response_headers) == {"X-A": "1", "Retry-After": "60"}


def test_b4b_apply_quota_and_legacy_action() -> None:
    recorded: list[tuple[str, float, str]] = []
    cache = SimpleNamespace(record_429=lambda rid, ttl_s, reason: recorded.append((rid, ttl_s, reason)))
    out = apply_quota_429(RouteRefusal(429, (), b""), SimpleNamespace(reset_s=15, reason="rpm"), SimpleNamespace(_QUOTA_CB_CACHE=cache), "r1")
    out_nocache = apply_quota_429(RouteRefusal(429, (), b""), SimpleNamespace(reset_s=90, reason="tpm"), SimpleNamespace(_QUOTA_CB_CACHE=SimpleNamespace()), "r2")
    assert (recorded, dict(out.response_headers)["Retry-After"], dict(out_nocache.response_headers)["Retry-After"]) == ([("r1", 15, "rpm")], "60", "90")
    fo_on = RouteFailover(statuses=frozenset({502}), quota_failover_opt_in=True)
    fo_statuses = RouteFailover(statuses=frozenset({404}), quota_failover_opt_in=False)
    fo_off = RouteFailover()
    assert (
        legacy_failure_action(RouteRefusal(429, (), b""), fo_on),
        legacy_failure_action(RouteRefusal(502, (), b""), fo_on),
        legacy_failure_action(RouteRefusal(404, (), b""), fo_on),
        legacy_failure_action(RouteRefusal(404, (), b""), fo_statuses),
        legacy_failure_action(RouteRefusal(400, (), b""), fo_off),
        legacy_failure_action(RouteRefusal(403, (), b""), fo_off),
        legacy_failure_action(RuntimeError("x"), fo_on),
    ) == ("quota", "slot_refusal", "ignore", "slot_refusal", "ignore", "route", "route")
