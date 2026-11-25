from types import SimpleNamespace
from typing import Any

import pytest

import adapters.passthrough_adapter as passthrough
import server
from core.telemetry_hooks import TelemetryHooksMixin

USAGE = {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}


class _BrokenWfile:
    def write(self, _data: bytes) -> None:
        raise BrokenPipeError

    def flush(self) -> None:
        raise AssertionError("flush must not run")


class _Sink:
    def __init__(self, handler: Any, fail: bool) -> None:
        self._handler = handler
        self._fail = fail
        self.closed = False

    def start(self, _status: int, _headers: list[tuple[str, str]]) -> None:
        pass

    def write(self, _data: bytes) -> None:
        if self._fail:
            raise server.ClientGone

    def close(self) -> None:
        self.closed = True


def test_handler_sink_tails_before_broken_pipe(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bytes] = []
    handler = SimpleNamespace(wfile=_BrokenWfile())
    sink = object.__new__(server._HandlerSink)
    sink._handler = handler
    sink._client_gone_flag = False
    monkeypatch.setattr(server, "telemetry_tail", lambda _handler, data: seen.append(data))

    with pytest.raises(server.ClientGone):
        sink.write(b"data: usage\n\n")

    assert seen == [b"data: usage\n\n"]
    assert sink._client_gone_flag is True


@pytest.mark.parametrize("client_gone", [True, False])
def test_relay_preserves_usage_after_disconnect_or_large_tail(
    monkeypatch: pytest.MonkeyPatch, client_gone: bool
) -> None:
    handler = SimpleNamespace(saved=None)
    handler._telemetry_usage = lambda usage: setattr(handler, "saved", usage)
    sink = _Sink(handler, client_gone)
    response = SimpleNamespace(readline=lambda: b"")
    adapter = SimpleNamespace(
        limits=None,
        process_budget=None,
        _trusted_tools=lambda _resp, _sanitize: False,
        _response_headers=lambda _resp: [],
        _stream_io_error=lambda *_args: False,
        _stream_success=lambda _outcome: True,
    )

    def relay(_readline: Any, write: Any, **kw: Any) -> Any:
        outcome = kw["state"]
        outcome.last_usage = USAGE
        write(b"data: usage\n\n")
        write(b"x" * 5000)
        return outcome

    monkeypatch.setattr(passthrough, "relay_sse", relay)
    try:
        passthrough.PassthroughAdapter._relay_stream(
            adapter, response, None, sink, False
        )
    except server.ClientGone:
        pass

    assert handler.saved == USAGE


def test_empty_tail_does_not_clear_recorded_usage() -> None:
    recorded: list[dict[str, Any]] = []
    handler = TelemetryHooksMixin()
    handler._req_meta = {"endpoint": "/v1/chat/completions", "route_mode": "passthrough"}
    handler._req_started_mono = 1.0
    handler._req_tracking = True
    handler._req_tail = b""
    handler._record_telemetry = lambda **kw: recorded.append({**(handler._req_meta or {}), **kw})  # type: ignore[method-assign]
    handler._telemetry_usage(USAGE)

    handler._telemetry_passthrough_done(200)

    assert len(recorded) == 1
    assert recorded[0]["prompt_tokens"] == 7
    assert recorded[0]["completion_tokens"] == 3
    assert recorded[0]["usage_present"] is True
