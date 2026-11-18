import pytest

from core.nonstream_aggregator import NonstreamAggregator, NonstreamError, aggregate_events


@pytest.mark.parametrize(
    "client_gone, expected_status, expected_error_type",
    [
        (False, 502, "upstream_incomplete_stream"),
        (True, 499, "client_closed"),
    ],
)
def test_incomplete_stream_classification(
    client_gone, expected_status, expected_error_type
):
    aggregator = NonstreamAggregator(1 << 20)

    with pytest.raises(NonstreamError) as exc_info:
        if client_gone:
            aggregator.finalize(client_gone=True)
        else:
            aggregator.finalize()

    assert exc_info.value.status == expected_status
    assert exc_info.value.code == expected_error_type


@pytest.mark.parametrize(
    "client_gone, expected_status, expected_error_type",
    [
        (True, 499, "client_closed"),
        (False, 502, "upstream_incomplete_stream"),
    ],
)
def test_aggregate_events_passes_client_gone(
    client_gone: bool, expected_status: int, expected_error_type: str
) -> None:
    from core.nonstream_aggregator import aggregate_events

    events = [(b'data: {"choices":[{"index":0,"delta":{"content":"hi"}}]}\n\n', None)]
    with pytest.raises(NonstreamError) as exc_info:
        aggregate_events(events, None, 1024, client_gone=lambda: client_gone)

    assert exc_info.value.status == expected_status
    assert exc_info.value.code == expected_error_type


def test_aggregate_events_classifies_io_error_as_499_when_client_gone():
    def events():
        yield (b'data: {"choices":[{"index":0,"delta":{"content":"hello"}}]}\n\n', None)
        raise OSError("broken pipe")

    with pytest.raises(NonstreamError) as exc_info:
        aggregate_events(events(), None, 1024, client_gone=lambda: True)

    assert exc_info.value.status == 499
    assert exc_info.value.code == "client_closed"


def test_aggregate_sse_does_not_retry_on_499_client_closed(monkeypatch):
    from types import SimpleNamespace

    from adapters.passthrough_adapter import PassthroughAdapter

    adapter = PassthroughAdapter.__new__(PassthroughAdapter)

    def read_agg_once(*args, **kwargs):
        raise NonstreamError(499, "client_closed", "client disconnected")

    def retry_must_not_run(*args, **kwargs):
        raise AssertionError("retry must not run on 499")

    monkeypatch.setattr(adapter, "_read_agg_once", read_agg_once)
    monkeypatch.setattr(
        "adapters.passthrough_adapter.retry_incomplete_once", retry_must_not_run
    )
    window = SimpleNamespace(_state=None, s_count=0, internal_stream=True)

    with pytest.raises(NonstreamError) as exc_info:
        adapter._aggregate_sse(None, window)

    assert exc_info.value.status == 499
    assert exc_info.value.code == "client_closed"

