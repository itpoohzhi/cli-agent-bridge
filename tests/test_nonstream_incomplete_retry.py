from __future__ import annotations

import threading
from typing import Mapping

import pytest

from core import nonstream_resilience


def test_nonstream_retry_policy_contract() -> None:
    policy = nonstream_resilience.NonstreamRetryPolicy.from_env(
        {"BRIDGE_NONSTREAM_INCOMPLETE_RETRY_MAX": "1"}
    )
    assert policy.max_retries == 1

    with pytest.raises(ValueError, match="0 или 1"):
        nonstream_resilience.NonstreamRetryPolicy(max_retries=2)

    bulkhead = nonstream_resilience.NonstreamRetryBulkhead.from_env(
        {"BRIDGE_NONSTREAM_RETRY_MAX_INFLIGHT": "2"}
    )
    assert bulkhead.max_inflight == 2
    assert bulkhead.try_acquire()
    assert bulkhead.try_acquire()
    assert not bulkhead.try_acquire()

    bulkhead.release()
    assert bulkhead.try_acquire()

    independent_backend = nonstream_resilience.NonstreamRetryBulkhead(max_inflight=1)
    assert independent_backend.try_acquire()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0", 0), ("1", 1), ("-1", 1), ("2", 1), ("invalid", 1)],
)
def test_nonstream_retry_limit_from_env(raw: str, expected: int) -> None:
    policy = nonstream_resilience.NonstreamRetryPolicy.from_env(
        {"BRIDGE_NONSTREAM_INCOMPLETE_RETRY_MAX": raw}
    )
    assert policy.max_retries == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", 1), ("4", 4), ("0", 4), ("5", 4), ("invalid", 4)],
)
def test_nonstream_retry_bulkhead_limit_from_env(raw: str, expected: int) -> None:
    bulkhead = nonstream_resilience.NonstreamRetryBulkhead.from_env(
        {"BRIDGE_NONSTREAM_RETRY_MAX_INFLIGHT": raw}
    )
    assert bulkhead.max_inflight == expected


def test_incomplete_nonstream_retry_requires_zero_signals_and_stateless_request() -> (
    None
):
    assert nonstream_resilience.should_retry_incomplete_nonstream(
        internal_stream=True,
        aggregate_signals=0,
        window_signals=0,
        sessions="none",
        headers={"X-Request-Id": "req-stable"},
    )


@pytest.mark.parametrize(
    (
        "internal_stream",
        "aggregate_signals",
        "window_signals",
        "sessions",
        "headers",
    ),
    [
        (False, 0, 0, "none", {"Idempotency-Key": "turn-stable"}),
        (True, 1, 0, "none", {"Idempotency-Key": "turn-stable"}),
        (True, 0, 1, "none", {"Idempotency-Key": "turn-stable"}),
        (True, 0, 0, "resident", {"Idempotency-Key": "turn-stable"}),
        (True, 0, 0, "none", {}),
        (
            True,
            0,
            0,
            "none",
            {
                "X-Request-Id": "req-stable",
                "X-Bridge-No-Retry": "1",
            },
        ),
    ],
)
def test_incomplete_nonstream_retry_rejects_non_idempotent_cases(
    internal_stream: bool,
    aggregate_signals: int,
    window_signals: int,
    sessions: str,
    headers: Mapping[str, str],
) -> None:
    assert not nonstream_resilience.should_retry_incomplete_nonstream(
        internal_stream=internal_stream,
        aggregate_signals=aggregate_signals,
        window_signals=window_signals,
        sessions=sessions,
        headers=headers,
    )


def test_incomplete_nonstream_retry_accepts_preserved_idempotency_headers() -> None:
    for header in (
        "X-Request-Id",
        "x-request-id",
        "Idempotency-Key",
        "X-Idempotency-Key",
    ):
        headers = {header: "stable-value"}

        assert nonstream_resilience.should_retry_incomplete_nonstream(
            internal_stream=True,
            aggregate_signals=0,
            window_signals=0,
            sessions="none",
            headers=headers,
        )
        assert headers == {header: "stable-value"}


def test_nonstream_retry_bulkhead_caps_sixteen_parallel_large_requests() -> None:
    bulkhead = nonstream_resilience.NonstreamRetryBulkhead(max_inflight=4)
    payload = b"x" * 6145
    attempted = threading.Barrier(17)
    release_slots = threading.Event()
    counter_lock = threading.Lock()
    acquired = 0
    active = 0
    peak_active = 0

    def worker(body: bytes) -> None:
        nonlocal acquired, active, peak_active
        assert len(body) > 6144
        owns_slot = bulkhead.try_acquire()
        if owns_slot:
            with counter_lock:
                acquired += 1
                active += 1
                peak_active = max(peak_active, active)
        attempted.wait()
        if owns_slot:
            release_slots.wait()
            with counter_lock:
                active -= 1
            bulkhead.release()

    threads = [threading.Thread(target=worker, args=(payload,)) for _ in range(16)]
    for thread in threads:
        thread.start()

    attempted.wait()
    assert acquired == 4
    assert peak_active == 4

    release_slots.set()
    for thread in threads:
        thread.join()
    assert active == 0
