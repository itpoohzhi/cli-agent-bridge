"""L1: карта ошибок ответа/pre-send и выбор hub-key проверки в _open."""

from __future__ import annotations

import http.client
import json
import socket
import time
from typing import Any
from unittest.mock import Mock

import pytest

from adapters.passthrough_adapter import (
    PassthroughAdapter,
    UpstreamBodyTooLarge,
)
from core.backend_adapter import PreSendTransientError
from core.nonstream_aggregator import NonstreamError
from core.tool_emulation import LiveParserError
from tests.unit._passthrough_tool_branches import (
    adapter as adapter,
    isolated_env as isolated_env,
    make_adapter,
    sink as sink,
)
from tests.unit._passthrough_tool_sink import _CollectSink

REQUEST = {
    "model": "m",
    "stream": False,
    "messages": [{"role": "user", "content": "hi"}],
}


def _error(sink: _CollectSink) -> tuple[int | None, str]:
    return sink.status, json.loads(sink.body)["error"]["type"]


def _timed_out_cause() -> Exception:
    error = RuntimeError("wrapped")
    error.__cause__ = TimeoutError()
    return error


def test_nonstream_error_keeps_its_own_status_code_and_message(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    error = NonstreamError(418, "teapot", "short and stout")
    assert adapter._response_error(sink, error, {}) is False
    payload = json.loads(sink.body)["error"]
    assert (sink.status, payload["type"], payload["message"]) == (
        418,
        "teapot",
        "short and stout",
    )


def test_oversized_body_maps_to_502_too_large(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    adapter._response_error(sink, UpstreamBodyTooLarge("body"), {})
    assert _error(sink) == (502, "upstream_response_too_large")


def test_live_parser_error_maps_to_tool_mode_violation_without_leaking_detail(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    adapter._response_error(sink, LiveParserError("secret_fn leaked"), {})
    assert _error(sink) == (502, "upstream_tool_mode_violation")
    assert b"secret_fn" not in sink.body


@pytest.mark.parametrize(
    "error",
    (
        socket.timeout("t"),
        PreSendTransientError("late", status_code=504),
        _timed_out_cause(),
    ),
    ids=("socket-timeout", "status-504", "timeout-cause"),
)
def test_timeout_shaped_errors_map_to_504(
    adapter: PassthroughAdapter, sink: _CollectSink, error: Exception
) -> None:
    assert adapter._response_error(sink, error, {}) is False
    assert _error(sink) == (504, "upstream_timeout")


@pytest.mark.parametrize(
    "error",
    (
        OSError("reset"),
        http.client.IncompleteRead(b""),
        PreSendTransientError("down", status_code=502),
        PreSendTransientError("down"),
    ),
    ids=("oserror", "incomplete-read", "status-502", "no-status"),
)
def test_other_transport_errors_map_to_502(
    adapter: PassthroughAdapter, sink: _CollectSink, error: Exception
) -> None:
    assert adapter._response_error(sink, error, {}) is False
    assert _error(sink) == (502, "upstream_unavailable")


def test_expired_total_deadline_turns_transport_error_into_504(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    adapter._response_error(sink, OSError("x"), {"deadline": time.monotonic() - 1})
    assert _error(sink) == (504, "upstream_timeout")


def test_future_deadline_keeps_transport_error_a_502(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    adapter._response_error(sink, OSError("x"), {"deadline": time.monotonic() + 60})
    assert _error(sink) == (502, "upstream_unavailable")


@pytest.mark.parametrize("expired,expected", ((True, 504), (False, 502)))
def test_liveness_window_expiry_decides_504_versus_502(
    adapter: PassthroughAdapter, sink: _CollectSink, expired: bool, expected: int
) -> None:
    window = Mock(expired=Mock(return_value=expired))
    adapter._response_error(sink, OSError("x"), {"window": window})
    assert sink.status == expected


def _handle_with_open_error(
    adapter: PassthroughAdapter,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    sink: Any,
) -> None:
    monkeypatch.setattr(adapter, "_open", Mock(side_effect=error))
    adapter.handle(
        path="/v1/chat/completions",
        request=REQUEST,
        raw_body=json.dumps(REQUEST).encode("utf-8"),
        headers={},
        sink=sink,
    )


@pytest.mark.parametrize(
    "error,expected",
    (
        (PreSendTransientError("t", status_code=504), (504, "upstream_timeout")),
        (PreSendTransientError("t", status_code=502), (502, "upstream_unavailable")),
        (PreSendTransientError("t", status_code=429), (502, "upstream_unavailable")),
        (PreSendTransientError("t"), (502, "upstream_unavailable")),
    ),
    ids=("504", "502", "other-status", "no-status"),
)
def test_presend_status_maps_to_gateway_error(
    adapter: PassthroughAdapter,
    sink: _CollectSink,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected: tuple[int, str],
) -> None:
    _handle_with_open_error(adapter, monkeypatch, error, sink)
    assert _error(sink) == expected
    assert adapter.active_count() == 0


def test_presend_timeout_cause_maps_to_504_without_status(
    adapter: PassthroughAdapter, sink: _CollectSink, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = PreSendTransientError("connect failed")
    error.__cause__ = TimeoutError("connect")
    _handle_with_open_error(adapter, monkeypatch, error, sink)
    assert _error(sink) == (504, "upstream_timeout")


def test_sink_accepting_presend_errors_receives_the_exception_instead(
    adapter: PassthroughAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _RetrySink(_CollectSink):
        accepts_presend_errors = True

    retry_sink = _RetrySink()
    error = PreSendTransientError("t", status_code=504)
    with pytest.raises(PreSendTransientError) as caught:
        _handle_with_open_error(adapter, monkeypatch, error, retry_sink)
    assert caught.value is error
    assert retry_sink.status is None
    assert adapter.active_count() == 0


class _Pool:
    def __init__(self, conn: Mock) -> None:
        self.conn = conn

    def get_connection(
        self, host: str, port: int, timeout: float, *, fresh: bool = False
    ) -> Any:
        return self.conn, False

    def close_all(self) -> None:
        return None


def _sent_headers(
    adapter: PassthroughAdapter, headers: dict[str, str]
) -> dict[str, str]:
    conn = Mock(spec=http.client.HTTPConnection)
    conn.sock = None
    setattr(adapter, "_pool", _Pool(conn))
    adapter._open("/v1/chat/completions", b"{}", headers)
    return dict(conn.request.call_args.kwargs["headers"])


def _credentials(sent: dict[str, str]) -> dict[str, str]:
    return {
        k.lower(): v
        for k, v in sent.items()
        if k.lower() in ("authorization", "x-api-key")
    }


CLIENT_CREDS = {"Authorization": "Bearer hub-key", "X-Api-Key": "hub-key"}


@pytest.mark.usefixtures("isolated_env")
def test_own_hub_key_callback_strips_hub_credentials() -> None:
    adapter = make_adapter(is_hub_key=lambda token: token == "hub-key")
    assert _credentials(_sent_headers(adapter, CLIENT_CREDS)) == {}


@pytest.mark.usefixtures("isolated_env")
def test_own_hub_key_callback_forwards_non_hub_credentials() -> None:
    adapter = make_adapter(is_hub_key=lambda token: token == "hub-key")
    sent = _sent_headers(adapter, {"Authorization": "Bearer user-key"})
    assert _credentials(sent) == {"authorization": "Bearer user-key"}


@pytest.mark.usefixtures("isolated_env")
def test_host_callback_is_the_fallback_when_no_own_callback() -> None:
    host = Mock(is_hub_key=Mock(side_effect=lambda token: token == "hub-key"))
    adapter = make_adapter(host)
    assert _credentials(_sent_headers(adapter, CLIENT_CREDS)) == {}
    host.is_hub_key.assert_any_call("hub-key")
    forwarded = _sent_headers(adapter, {"x-api-key": "user-key"})
    assert _credentials(forwarded) == {"x-api-key": "user-key"}


@pytest.mark.usefixtures("isolated_env")
def test_own_callback_shadows_host_callback_even_when_it_says_no() -> None:
    host = Mock(is_hub_key=Mock(return_value=True))
    adapter = make_adapter(host, is_hub_key=lambda token: False)
    assert _credentials(_sent_headers(adapter, CLIENT_CREDS)) != {}
    host.is_hub_key.assert_not_called()


@pytest.mark.usefixtures("isolated_env")
@pytest.mark.parametrize("host_attr", (None, "not-callable", 0))
def test_without_a_usable_callback_client_credentials_are_forwarded(
    host_attr: Any,
) -> None:
    host = Mock(is_hub_key=host_attr)
    adapter = make_adapter(host)
    sent = _sent_headers(adapter, {"Authorization": "Bearer hub-key"})
    assert _credentials(sent) == {"authorization": "Bearer hub-key"}


@pytest.mark.usefixtures("isolated_env")
def test_no_client_credentials_means_callback_is_not_consulted() -> None:
    callback = Mock(return_value=True)
    adapter = make_adapter(is_hub_key=callback)
    assert _credentials(_sent_headers(adapter, {"X-Other": "1"})) == {}
    callback.assert_not_called()
