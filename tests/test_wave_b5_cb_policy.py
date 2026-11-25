"""Unit tests for core/route_cb_policy.py (PR B5)."""
from __future__ import annotations

from core.route_cb_policy import classify_auth_failure, is_client_gone, is_recordable_failure


class ClientDisconnect(Exception):
    pass


class PreSendTransientError(Exception):
    pass


def test_b5_client_gone_and_auth_classification() -> None:
    assert (
        is_client_gone(status=499),
        is_client_gone(reason="CLIENT_GONE"),
        is_client_gone(reason="client_disconnected"),
        is_client_gone(error=BrokenPipeError()),
        is_client_gone(error=ClientDisconnect()),
        is_client_gone(status=500, error=RuntimeError("x"), reason="timeout"),
    ) == (True, True, True, True, True, False)
    assert (
        classify_auth_failure(403, "Model_Not_Found"),
        classify_auth_failure(401, "INVALID_API_KEY"),
        classify_auth_failure(402, "insufficient_quota"),
        classify_auth_failure(403, "permission_denied"),
        classify_auth_failure(401, "model_not_found"),
        classify_auth_failure(500, "invalid_api_key"),
    ) == ("route_local", "provider_wide", "provider_wide", "unproven", "unproven", "none")


def test_b5_is_recordable_failure_matrix() -> None:
    excluded = (
        {"status": 400}, {"status": 404}, {"status": 422},
        {"status": 499}, {"error": BrokenPipeError()}, {"reason": "client_gone"},
        {"status": 500, "reason": "client_disconnected"}, {"status": None, "error": None, "reason": ""},
    )
    included = (
        {"status": 429}, {"status": 401}, {"status": 402}, {"status": 403},
        {"status": 500}, {"status": 599}, {"reason": "broken_stream"},
        {"reason": "read_timeout"}, {"reason": "network_error"},
        {"error": TimeoutError()}, {"error": PreSendTransientError()},
    )
    assert all(is_recordable_failure(**kw) is False for kw in excluded)
    assert all(is_recordable_failure(**kw) is True for kw in included)
