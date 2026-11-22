"""L1 contracts for resident-turn failures crossing the SSE facade."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stdio_resident.sse_error_bridge import SseErrorContext, handle_sse_stream_exception  # noqa: E402
from core.stdio_resident.turn_error_sse import DONE_FRAME, ResidentTurnError, TurnErrorResponse  # noqa: E402
from core.stdio_resident.zero_canon_router import execute_routed_turn  # noqa: E402

UNSUPPORTED = "zero_canon_unsupported_by_driver:StreamJsonDriver"


class _Lease:
    def __init__(self) -> None:
        self.failures: list[BaseException] = []
        self.discards: list[str] = []

    def record_failure(self, exc: BaseException) -> None:
        self.failures.append(exc)

    def record_discard(self, reason: str) -> None:
        self.discards.append(reason)


def _bridge(*, headers: bool = True, dead: bool = False):
    handler = SimpleNamespace(
        _client_write_dead=dead,
        _headers_already_sent=headers,
        _response_status=200,
    )
    lease = _Lease()
    emitted: list[str] = []
    logs: list[str] = []
    stream_error = Mock(return_value="data: synthetic-error\n\n")
    ctx = SseErrorContext(
        handler,
        lease,
        lambda frame: emitted.append(frame) or True,
        stream_error,
        logs.append,
    )
    return handler, lease, emitted, logs, stream_error, ctx


def _resident(
    message: str = UNSUPPORTED,
    status: int = 503,
    error_type: str = "zero_canon_unsupported",
    code: str = "zero_canon_unsupported_by_driver",
) -> ResidentTurnError:
    body = {"error": {"message": message, "type": error_type, "code": code}}
    sse = "data: " + json.dumps(body) + "\n\n" + DONE_FRAME
    return ResidentTurnError(TurnErrorResponse(status, error_type, code, message, sse, body))


def _error_payload(sse: str) -> dict:
    frame, done, tail = sse.split("\n\n")
    assert frame.startswith("data: ")
    assert (done, tail) == ("data: [DONE]", "")
    return json.loads(frame[len("data: ") :])["error"]


def _routed_failure(exc: BaseException, live: int = 0, profile: str = "zero-canon"):
    def execute(_request: dict):
        if live:
            yield {"choices": [{"delta": {"content": "partial"}}]}
        raise exc

    writes: list[tuple[str, str]] = []
    request = {"review_profile": profile, "model": "gpt-6.1-terra"}
    with pytest.raises(ResidentTurnError) as caught:
        execute_routed_turn(execute, "stream-json", request, lambda k, v: writes.append((k, v)))
    return caught.value, writes


def test_disconnect_suppresses_failure_and_all_frames() -> None:
    handler, lease, emitted, logs, stream_error, ctx = _bridge(dead=True)
    exc = RuntimeError("boom")

    assert handle_sse_stream_exception(exc, 9, ctx) is True
    assert emitted == [] and lease.failures == []
    assert lease.discards == ["client_disconnected"]
    assert handler._response_status == 200 and stream_error.call_count == 0
    assert logs == [f"client_write_dead: dispatch error suppressed err={repr(exc)!r}"]


def test_pre_headers_error_is_reraised_without_mutating_response() -> None:
    handler, lease, emitted, logs, stream_error, ctx = _bridge(headers=False)
    handler._response_status = 418
    exc = RuntimeError("before headers")

    assert handle_sse_stream_exception(exc, 0, ctx) is False
    assert handler._response_status == 418
    assert emitted == [] and logs == []
    assert lease.failures == [] and lease.discards == []
    stream_error.assert_not_called()


@pytest.mark.parametrize(
    ("exc", "status"),
    [(_resident(), 503), (_resident("429 rate limit", 429, "rate_limit_error", "rate_limit_exceeded"), 429)],
)
def test_prechunk_resident_error_uses_exact_response(exc: ResidentTurnError, status: int) -> None:
    handler, lease, emitted, logs, stream_error, ctx = _bridge()

    assert handle_sse_stream_exception(exc, 0, ctx) is True
    assert handler._response_status == status
    assert lease.failures == [exc] and emitted == [exc.response.sse]
    assert _error_payload(emitted[0]) == exc.response.body["error"]
    assert f"status={status}" in logs[0] and f"code={exc.response.code}" in logs[0]
    stream_error.assert_not_called()


@pytest.mark.parametrize(
    ("exc", "status", "error_type", "code"),
    [
        (RuntimeError("boom"), 502, "upstream_error", "resident_turn_failed"),
        (TimeoutError("idle"), 504, "timeout_error", "turn_timeout"),
    ],
)
def test_prechunk_generic_error_builds_json_sse(exc, status, error_type, code) -> None:
    handler, lease, emitted, _logs, stream_error, ctx = _bridge()

    assert handle_sse_stream_exception(exc, 0, ctx) is True
    assert handler._response_status == status and lease.failures == [exc]
    assert len(emitted) == 1
    assert _error_payload(emitted[0]) == {
        "message": str(exc), "type": error_type, "code": code
    }
    stream_error.assert_not_called()


def test_midstream_generic_error_preserves_rw_211_framing() -> None:
    handler, lease, emitted, _logs, stream_error, ctx = _bridge()
    exc = RuntimeError("mid-stream fail")

    assert handle_sse_stream_exception(exc, 1, ctx) is True
    assert handler._response_status == 200 and lease.failures == [exc]
    assert emitted == ["data: synthetic-error\n\n", DONE_FRAME]
    assert stream_error.call_args == call("mid-stream fail", finish_reason=None)


def test_midstream_resident_error_does_not_rewrite_http_200() -> None:
    handler, lease, emitted, _logs, stream_error, ctx = _bridge()
    exc = _resident()

    assert handle_sse_stream_exception(exc, 12, ctx) is True
    assert handler._response_status == 200 and lease.failures == [exc]
    assert emitted == [exc.response.sse]
    assert _error_payload(emitted[0]) == exc.response.body["error"]
    stream_error.assert_not_called()


@pytest.mark.parametrize(("live", "status"), [(0, 503), (1, 200)])
def test_zero_canon_driver_rejection_becomes_resident_error(live: int, status: int) -> None:
    exc, writes = _routed_failure(RuntimeError(UNSUPPORTED), live)

    assert exc.status == status and exc.response.status == status
    assert exc.response.error_type == "zero_canon_unsupported"
    assert exc.response.code == "zero_canon_unsupported_by_driver"
    assert exc.response.message == UNSUPPORTED
    assert _error_payload(exc.response.sse) == exc.response.body["error"]
    assert writes == ([("content", "partial")] if live else [])


@pytest.mark.parametrize(
    ("failure", "status", "error_type"),
    [
        (RuntimeError("429 rate limit"), 429, "rate_limit_error"),
        (ValueError(UNSUPPORTED), 502, "upstream_error"),
        (RuntimeError("prefix " + UNSUPPORTED), 502, "upstream_error"),
    ],
)
def test_other_routed_failures_still_use_standard_classifier(failure, status, error_type) -> None:
    exc, writes = _routed_failure(failure, profile="standard")

    assert exc.status == status and exc.response.error_type == error_type
    assert _error_payload(exc.response.sse)["message"] == str(failure)
    assert writes == []


def test_server_sse_facade_emits_zero_canon_error_without_raising() -> None:
    import server

    error = _resident()
    lease = _Lease()
    written: list[str] = []
    handler = object.__new__(server.Handler)
    handler._headers_already_sent = True
    handler._trace = None
    handler._context_pruned = ""
    handler._active_managed_turn = None
    handler._current_lease = lambda: lease
    handler._emit = lambda frame: written.append(frame) or True

    def fail_dispatch(*_args):
        raise error

    handler._dispatch = fail_dispatch
    handler._serve_sse_body({"model": "gpt-6.1-terra"})

    assert handler._response_status == 503 and lease.failures == [error]
    assert lease.discards == [] and len(written) == 2
    assert _error_payload(written[1]) == error.response.body["error"]
    assert "".join(written).endswith(DONE_FRAME)
