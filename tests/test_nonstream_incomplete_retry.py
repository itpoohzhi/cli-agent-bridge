from __future__ import annotations

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
