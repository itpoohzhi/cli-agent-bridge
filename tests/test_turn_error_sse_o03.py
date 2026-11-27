"""Tests for O-03 turn_error_sse status mapping and Retry-After invariants."""

from __future__ import annotations

import pytest

from core.stdio_resident.runtime_types import BridgeDrainingError, TurnTimeoutError as WireTurnTimeoutError
from core.stdio_resident.turn_deadlines import TurnTimeoutError as DeadlineTurnTimeoutError
from core.stdio_resident.turn_error_sse import TURN_TIMEOUT_502_ENV, build_turn_error


def test_turn_timeout_defaults_to_504_without_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TURN_TIMEOUT_502_ENV, raising=False)
    for err in (
        WireTurnTimeoutError("resident_turn_timeout"),
        DeadlineTurnTimeoutError("first_progress", "timed out"),
    ):
        resp = build_turn_error(err, live_sent=0)
        assert resp.status == 504
        assert resp.error_type == "timeout_error"
        assert "Retry-After" not in resp.headers


def test_turn_timeout_502_flag_maps_504_to_502_without_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TURN_TIMEOUT_502_ENV, "true")
    for err in (
        WireTurnTimeoutError("resident_turn_timeout"),
        DeadlineTurnTimeoutError("idle", "timed out"),
    ):
        resp = build_turn_error(err, live_sent=0)
        assert resp.status == 502
        assert resp.error_type == "timeout_error"
        assert "Retry-After" not in resp.headers


def test_bridge_draining_always_503_even_when_502_flag_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TURN_TIMEOUT_502_ENV, "true")
    resp = build_turn_error(BridgeDrainingError(), live_sent=0)
    assert resp.status == 503
    assert resp.error_type == "service_unavailable"
    assert resp.code == "bridge_draining"


def test_turn_timeout_post_commit_returns_200_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TURN_TIMEOUT_502_ENV, raising=False)
    resp = build_turn_error(WireTurnTimeoutError("resident_turn_timeout"), live_sent=12)
    assert resp.status == 200
    assert resp.code == "turn_timeout"
    assert "data: [DONE]\n\n" in resp.sse


def test_non_turn_504_not_mapped_to_502_when_flag_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TURN_TIMEOUT_502_ENV, "true")

    class _Other504(RuntimeError):
        http_status = 504
        code = "upstream_gateway_timeout"

    resp = build_turn_error(_Other504("gw timeout"), live_sent=0)
    assert resp.status == 504
    assert resp.code == "upstream_gateway_timeout"
