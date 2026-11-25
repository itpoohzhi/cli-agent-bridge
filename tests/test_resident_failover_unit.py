"""Unit-тесты для core/resident_failover.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.resident_failover import (  # noqa: E402
    cli_resident_refusal,
    handle_json_resident_error,
    is_precommit,
    maybe_raise_sse_precommit_refusal,
    should_defer_sse_headers,
)
from core.route_attempts import AttemptPhase, AttemptState, RouteRefusal  # noqa: E402
from core.stdio_resident.turn_error_sse import (  # noqa: E402
    DONE_FRAME,
    ResidentTurnError,
    TurnErrorResponse,
)


def _resident_error(
    status: int,
    code: str,
    message: str = "resident failure",
    body: Any = None,
) -> ResidentTurnError:
    payload = (
        body
        if body is not None
        else {"error": {"message": message, "type": "upstream_error", "code": code}}
    )
    sse_payload = (
        payload.decode("utf-8", errors="replace")
        if isinstance(payload, bytes)
        else (
            payload
            if isinstance(payload, str)
            else json.dumps(payload, ensure_ascii=False, default=str)
        )
    )
    sse = "data: " + sse_payload + "\n\n" + DONE_FRAME
    return ResidentTurnError(
        TurnErrorResponse(status, "upstream_error", code, message, sse, payload)
    )


def _attempt(*, committed: bool = False) -> SimpleNamespace:
    phase = AttemptPhase.COMMITTED if committed else AttemptPhase.CONNECTING
    return SimpleNamespace(state=AttemptState(phase=phase, committed=committed))


class _FakeLease:
    def __init__(self) -> None:
        self.failures: list[BaseException] = []

    def record_failure(self, exc: BaseException) -> None:
        self.failures.append(exc)


class _FakeHandler:
    def __init__(
        self,
        *,
        attempt: object | None = None,
        headers_sent: bool = False,
    ) -> None:
        self._transport_attempt = attempt
        self._headers_already_sent = headers_sent
        self.sent: list[tuple[int, dict[str, object]]] = []

    def _send(self, code: int, payload: dict[str, object]) -> None:
        self.sent.append((code, payload))


def test_is_precommit_true_only_when_all_guards_hold() -> None:
    handler = _FakeHandler(attempt=_attempt(committed=False), headers_sent=False)
    assert is_precommit(handler) is True
    assert is_precommit(handler, live_sent=0) is True


@pytest.mark.parametrize(
    ("attempt", "headers_sent", "live_sent"),
    [
        (None, False, 0),
        (_attempt(committed=False), True, 0),
        (_attempt(committed=False), False, 1),
        (_attempt(committed=False), False, -1),
        (_attempt(committed=True), False, 0),
    ],
)
def test_is_precommit_fail_closed_boundaries(
    attempt: object | None, headers_sent: bool, live_sent: int
) -> None:
    handler = _FakeHandler(attempt=attempt, headers_sent=headers_sent)
    assert is_precommit(handler, live_sent=live_sent) is False


@pytest.mark.parametrize("code", ["resident_dispatch_failed", "resident_turn_failed"])
def test_cli_resident_refusal_preserves_502_and_json_body(code: str) -> None:
    exc = _resident_error(502, code, "upstream boom")
    refusal = cli_resident_refusal(exc)
    assert isinstance(refusal, RouteRefusal)
    assert refusal.status_code == 502
    assert refusal.response_headers == (("Content-Type", "application/json"),)
    parsed = json.loads(refusal.response_body.decode("utf-8"))
    assert parsed["error"]["code"] == code
    assert parsed["error"]["message"] == "upstream boom"


@pytest.mark.parametrize("bad_status", [200, 0, -5])
def test_cli_resident_refusal_falls_back_to_502_for_non_error_status(
    bad_status: int,
) -> None:
    exc = _resident_error(bad_status, "resident_turn_failed", "invalid status")
    refusal = cli_resident_refusal(exc)
    assert refusal.status_code == 502


def test_cli_resident_refusal_handles_bytes_and_str_bodies() -> None:
    err_bytes = _resident_error(503, "slot_lease_timeout", body=b'{"error":"bytes"}')
    err_str = _resident_error(504, "turn_timeout", body='{"error":"str"}')
    assert cli_resident_refusal(err_bytes).status_code == 503
    assert cli_resident_refusal(err_bytes).response_body == b'{"error":"bytes"}'
    assert cli_resident_refusal(err_str).status_code == 504
    assert cli_resident_refusal(err_str).response_body == b'{"error":"str"}'


def test_should_defer_sse_headers_matrix() -> None:
    routed = _FakeHandler(attempt=_attempt(), headers_sent=False)
    assert should_defer_sse_headers(routed, {}) is True
    assert should_defer_sse_headers(routed, {"attached_existing": False}) is True
    assert should_defer_sse_headers(routed, {"attached_existing": True}) is False
    non_routed = _FakeHandler(attempt=None, headers_sent=False)
    assert should_defer_sse_headers(non_routed, {}) is False
    sent = _FakeHandler(attempt=_attempt(), headers_sent=True)
    assert should_defer_sse_headers(sent, {}) is False
    committed = _FakeHandler(attempt=_attempt(committed=True), headers_sent=False)
    assert should_defer_sse_headers(committed, {}) is False


def test_cli_resident_refusal_supports_httpstatus_and_unserializable_body() -> None:
    from http import HTTPStatus

    exc_enum = _resident_error(HTTPStatus.SERVICE_UNAVAILABLE, "busy", body={"obj": object()})
    refusal = cli_resident_refusal(exc_enum)
    assert refusal.status_code == 503
    assert b"object" in refusal.response_body


def test_handle_json_resident_error_precommit_raises_refusal() -> None:
    handler = _FakeHandler(attempt=_attempt(committed=False), headers_sent=False)
    lease = _FakeLease()
    logs: list[str] = []
    exc = _resident_error(502, "resident_dispatch_failed", "dispatch failed")
    with pytest.raises(RouteRefusal) as exc_info:
        handle_json_resident_error(handler, lease, exc, logs.append)
    assert exc_info.value.status_code == 502
    assert lease.failures == [exc]
    assert handler.sent == []
    assert logs == []


@pytest.mark.parametrize(
    ("attempt", "headers_sent"),
    [
        (_attempt(committed=True), False),
        (_attempt(committed=False), True),
        (None, False),
    ],
)
def test_handle_json_resident_error_postcommit_logs_and_sends(
    attempt: object | None, headers_sent: bool
) -> None:
    handler = _FakeHandler(attempt=attempt, headers_sent=headers_sent)
    lease = _FakeLease()
    logs: list[str] = []
    exc = _resident_error(
        502, "resident_turn_failed", "secret sk-1234567890abcdef1234567890"
    )
    handle_json_resident_error(handler, lease, exc, logs.append)
    assert lease.failures == [exc]
    assert handler.sent == [(502, exc.response.body)]
    assert len(logs) == 1
    assert "json_resident_error status=502 code=resident_turn_failed" in logs[0]
    assert "sk-1234567890abcdef1234567890" not in logs[0]


def test_maybe_raise_sse_precommit_refusal_precommit_raises() -> None:
    handler = _FakeHandler(attempt=_attempt(committed=False), headers_sent=False)
    lease = _FakeLease()
    exc = _resident_error(502, "resident_turn_failed", "sse precommit fail")
    with pytest.raises(RouteRefusal) as exc_info:
        maybe_raise_sse_precommit_refusal(handler, lease, exc, live_sent=0)
    assert exc_info.value.status_code == 502
    assert lease.failures == [exc]


@pytest.mark.parametrize(
    ("exc", "live_sent", "headers_sent", "committed"),
    [
        (_resident_error(502, "resident_turn_failed"), 12, False, False),
        (_resident_error(502, "resident_turn_failed"), -1, False, False),
        (_resident_error(502, "resident_turn_failed"), 0, True, False),
        (_resident_error(502, "resident_turn_failed"), 0, False, True),
        (RuntimeError("not resident"), 0, False, False),
    ],
)
def test_maybe_raise_sse_precommit_refusal_returns_none_when_ineligible(
    exc: BaseException, live_sent: int, headers_sent: bool, committed: bool
) -> None:
    handler = _FakeHandler(
        attempt=_attempt(committed=committed), headers_sent=headers_sent
    )
    lease = _FakeLease()
    result = maybe_raise_sse_precommit_refusal(handler, lease, exc, live_sent=live_sent)
    assert result is None
    assert lease.failures == []
