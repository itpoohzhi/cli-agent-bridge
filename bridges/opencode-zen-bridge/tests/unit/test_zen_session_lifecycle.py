import io
import json
import urllib.error
from unittest.mock import Mock

import pytest

from zen_bridge.adapters import http_upstream
from zen_bridge.adapters.http_upstream import (
    CircuitBreaker,
    CircuitBreakerState,
    UpstreamLimits,
    ZenHttpUpstream,
)
from zen_bridge.domain.models import (
    DeadlineBudget,
    ErrorClassification,
    RequestEnvelope,
    ZenError,
)


ENDPOINT = "https://zen.invalid/v1/chat/completions"


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_budget(clock: FakeClock, seconds: float = 10.0) -> DeadlineBudget:
    deadline = clock() + seconds
    budget = Mock(spec=DeadlineBudget)
    budget.remaining_s.side_effect = lambda: max(0.0, deadline - clock())
    return budget


def make_upstream(breaker=None, cap: float = 60.0) -> ZenHttpUpstream:
    return ZenHttpUpstream(
        ENDPOINT,
        circuit_breaker=breaker,
        limits=UpstreamLimits(
            max_retries=0,
            backoff_base_s=0.0,
            read_timeout_cap_s=cap,
        ),
    )


def http_error(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        ENDPOINT, status, "Upstream failure", {}, io.BytesIO()
    )


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def envelope():
    request = Mock(spec=RequestEnvelope)
    request.payload = {
        "model": "zen",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
    }
    request.headers = {"Authorization": "Bearer test-token"}
    return request


@pytest.fixture(autouse=True)
def urlopen(monkeypatch):
    handler = Mock(
        side_effect=AssertionError("Unexpected HTTP request; sockets are forbidden")
    )
    monkeypatch.setattr(http_upstream.urllib.request, "urlopen", handler)
    return handler


def test_http_upstream_successful_stream(
    clock, envelope, urlopen, monkeypatch
):
    payloads = [{"delta": "Hello"}, {"delta": " world"}]
    wire = (
        b": keep-alive\n\n"
        b'data: {"delta": "Hello"}\n\n'
        b'data: {"delta": " world"}\n\n'
        b"data: [DONE]\n\n"
    )
    response = io.BytesIO(wire)
    urlopen.side_effect = None
    urlopen.return_value = response
    chunks = [object(), object()]
    chunk_factory = Mock(side_effect=chunks)
    monkeypatch.setattr(http_upstream, "StreamChunk", chunk_factory)

    result = list(make_upstream().execute_stream(envelope, make_budget(clock)))

    assert result == chunks
    assert [call.kwargs for call in chunk_factory.call_args_list] == [
        {"data": payload} for payload in payloads
    ]
    request = urlopen.call_args.args[0]
    assert request.full_url == ENDPOINT
    assert request.get_method() == "POST"
    assert json.loads(request.data) == envelope.payload
    assert request.get_header("Authorization") == "Bearer test-token"
    assert response.closed


@pytest.mark.parametrize("remaining", [0.0, 10.0])
def test_http_upstream_timeout_exhaustion_transient(
    clock, envelope, urlopen, remaining
):
    breaker = CircuitBreaker(failure_threshold=1, clock=clock)
    urlopen.side_effect = TimeoutError("read timed out")
    upstream = make_upstream(breaker)

    with pytest.raises(ZenError) as caught:
        list(upstream.execute_stream(envelope, make_budget(clock, remaining)))

    assert caught.value.classification is ErrorClassification.TRANSIENT
    assert caught.value.retryable is True
    assert breaker.state is CircuitBreakerState.OPEN
    assert urlopen.call_count == (1 if remaining > 0 else 0)


def test_http_upstream_503_raises_transient_zen_error(
    clock, envelope, urlopen
):
    breaker = CircuitBreaker(failure_threshold=1, clock=clock)
    urlopen.side_effect = http_error(503)

    with pytest.raises(ZenError) as caught:
        list(make_upstream(breaker).execute_stream(envelope, make_budget(clock)))

    assert caught.value.classification is ErrorClassification.TRANSIENT
    assert caught.value.retryable is True
    assert breaker.state is CircuitBreakerState.OPEN
    urlopen.assert_called_once()


def test_http_upstream_401_raises_fatal_zen_error(clock, envelope, urlopen):
    breaker = CircuitBreaker(failure_threshold=1, clock=clock)
    urlopen.side_effect = http_error(401)

    with pytest.raises(ZenError) as caught:
        list(make_upstream(breaker).execute_stream(envelope, make_budget(clock)))

    assert caught.value.classification is ErrorClassification.FATAL
    assert caught.value.retryable is False
    assert breaker.state is CircuitBreakerState.CLOSED
    urlopen.assert_called_once()


def test_circuit_breaker_trips_after_threshold(clock, envelope, urlopen):
    breaker = CircuitBreaker(clock=clock)
    upstream = make_upstream(breaker)
    urlopen.side_effect = urllib.error.URLError("connection refused")

    for index in range(3):
        with pytest.raises(ZenError):
            list(upstream.execute_stream(envelope, make_budget(clock)))
        expected = (
            CircuitBreakerState.OPEN
            if index == 2
            else CircuitBreakerState.CLOSED
        )
        assert breaker.state is expected

    assert breaker.is_available() is False
    with pytest.raises(ZenError) as caught:
        list(upstream.execute_stream(envelope, make_budget(clock)))

    assert caught.value.classification is ErrorClassification.TRANSIENT
    assert caught.value.retryable is True
    assert urlopen.call_count == 3


def test_circuit_breaker_half_open_recovery(clock, envelope, urlopen):
    breaker = CircuitBreaker(reset_timeout_s=30.0, clock=clock)
    for _ in range(3):
        breaker.record_failure()
    assert breaker.state is CircuitBreakerState.OPEN

    clock.advance(29.0)
    assert breaker.is_available() is False
    clock.advance(1.0)
    assert breaker.is_available() is True
    assert breaker.state is CircuitBreakerState.HALF_OPEN
    urlopen.side_effect = None
    urlopen.return_value = io.BytesIO(b"data: [DONE]\n\n")

    assert list(
        make_upstream(breaker).execute_stream(envelope, make_budget(clock))
    ) == []

    assert breaker.state is CircuitBreakerState.CLOSED
    assert breaker.is_available() is True
    breaker.record_failure()
    assert breaker.state is CircuitBreakerState.CLOSED


@pytest.mark.parametrize(
    ("seconds", "elapsed", "cap", "expected"),
    [(10.0, 2.5, 60.0, 7.5), (100.0, 2.5, 60.0, 60.0)],
)
def test_deadline_budget_passed_to_request_timeout(
    clock, envelope, urlopen, seconds, elapsed, cap, expected
):
    budget = make_budget(clock, seconds)
    clock.advance(elapsed)
    urlopen.side_effect = None
    urlopen.return_value = io.BytesIO(b"data: [DONE]\n\n")

    list(make_upstream(cap=cap).execute_stream(envelope, budget))

    assert urlopen.call_args.kwargs["timeout"] == expected
    assert budget.remaining_s.called


def test_server_get_chat_service_integration() -> None:
    """Проверяет интеграцию фабрики get_chat_service и конфигурацию сервиса."""
    import server

    svc = server.get_chat_service()
    assert svc is not None
    assert svc.http_upstream.base_url == "http://127.0.0.1:4096"
    assert svc.cli_fallback.cli_cmd == ["opencode", "run"]
    assert callable(svc.coordinate_stream_fallback)
