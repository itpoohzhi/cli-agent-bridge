"""Unit tests: classify_route_failure и константы core/route_failure_telemetry.py (Wave W1-B1)."""

from __future__ import annotations

import json

import pytest

from core.route_attempts import RouteRefusal
from core.route_failure_telemetry import (
    ALL_ROUTES_OPEN_BODY,
    ALLOWED_REFUSAL_STATUSES,
    CLOSED_ERROR_TYPES,
    RouteFailureClassification,
    classify_route_failure,
)
from core.telemetry_hooks import known_model


def test_constants() -> None:
    assert ALLOWED_REFUSAL_STATUSES == frozenset({402, 408, 429, 502, 503, 504})
    assert CLOSED_ERROR_TYPES == frozenset(
        {"all_routes_open", "RouteRefusal", "pool_exhausted", "route_unavailable"}
    )
    assert (
        ALL_ROUTES_OPEN_BODY
        == b'{"error":{"type":"all_routes_open","code":"all_routes_open","message":"all routes are open or busy"}}'
    )
    assert json.loads(ALL_ROUTES_OPEN_BODY)["error"]["type"] == "all_routes_open"


@pytest.mark.parametrize("status", sorted({402, 408, 429, 502, 503, 504}))
def test_classify_allowed_refusal(status: int) -> None:
    got = classify_route_failure(RouteRefusal(status), "muse-ember-1.0")
    assert got == RouteFailureClassification(status, "RouteRefusal", "muse-ember-1.0")


def test_classify_is_frozen() -> None:
    got = classify_route_failure(RouteRefusal(429))
    with pytest.raises(AttributeError):
        got.status_code = 1  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]


def test_classify_anti_duck_typing() -> None:
    exc = ValueError("x")
    exc.status_code = 429  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
    assert classify_route_failure(exc) == RouteFailureClassification(
        500, "ValueError", None
    )


@pytest.mark.parametrize("status", [200, 418, 404, 500])
def test_classify_nonstandard_refusal(status: int) -> None:
    assert classify_route_failure(RouteRefusal(status)) == RouteFailureClassification(
        502, "RouteRefusal", None
    )


def test_classify_bool_status_is_nonstandard() -> None:
    err = RouteRefusal(429)
    err.status_code = True  # type: ignore[assignment]  # pyright: ignore[reportAttributeAccessIssue]
    assert classify_route_failure(err).status_code == 502


def test_classify_other_exceptions() -> None:
    assert classify_route_failure(KeyboardInterrupt()).error_type == "KeyboardInterrupt"
    assert classify_route_failure(KeyboardInterrupt()).status_code == 500
    assert classify_route_failure(None).status_code == 500


def test_model_normalisation() -> None:
    assert known_model("unknown") is None
    assert known_model("muse-ember-1.0") == "muse-ember-1.0"
    assert classify_route_failure(None, "unknown").model is None
    assert classify_route_failure(None, "").model is None
    assert classify_route_failure(None, None).model is None
    assert classify_route_failure(None, "muse-ember-1.0").model == "muse-ember-1.0"
    assert classify_route_failure(None, 5).model is None  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
