"""Tests for Wave 7b single-route keepalive 2x2 matrix and inert D4 drain DI."""

from __future__ import annotations

import pytest

from core.resident_failover import (
    DRAIN_REFUSAL_ENV,
    PRECOMMIT_CODE_LOG_ENV,
    SINGLE_ROUTE_KEEPALIVE_ENV,
    check_precommit_drain_refusal,
    handle_json_resident_error,
    should_defer_sse_headers,
)
from core.route_attempts import RouteRefusal
from tests.test_resident_failover_unit import _FakeHandler, _FakeLease, _attempt, _resident_error


@pytest.mark.parametrize(
    ("flag_val", "route_count", "expected_defer"),
    [
        ("false", 1, True),
        ("false", 2, True),
        ("true", 1, False),
        ("true", 2, True),
    ],
)
def test_single_route_keepalive_2x2_matrix(flag_val: str, route_count: int, expected_defer: bool) -> None:
    handler = _FakeHandler(attempt=_attempt(committed=False), headers_sent=False)
    defer = should_defer_sse_headers(
        handler,
        {"route_count": route_count},
        environ={SINGLE_ROUTE_KEEPALIVE_ENV: flag_val},
    )
    assert defer is expected_defer


def test_inert_d4_drain_di_requires_both_draining_and_flag() -> None:
    # Default: inert even if draining=True
    check_precommit_drain_refusal(draining=True, request_id="req-1", environ={})
    check_precommit_drain_refusal(draining=False, request_id="req-1", environ={DRAIN_REFUSAL_ENV: "true"})

    with pytest.raises(RouteRefusal) as exc_info:
        check_precommit_drain_refusal(
            draining=True,
            request_id="req-123",
            environ={DRAIN_REFUSAL_ENV: "true"},
        )
    assert exc_info.value.status_code == 503
    headers = dict(exc_info.value.response_headers)
    assert int(headers["Retry-After"]) >= 1
    assert b"bridge_draining" in exc_info.value.response_body


def test_precommit_code_log_can_be_disabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PRECOMMIT_CODE_LOG_ENV, "false")
    handler = _FakeHandler(attempt=_attempt(committed=False), headers_sent=False)
    lease = _FakeLease()
    logs: list[str] = []
    exc = _resident_error(504, "turn_timeout", "timed out")
    with pytest.raises(RouteRefusal):
        handle_json_resident_error(handler, lease, exc, logs.append)
    assert logs == []
