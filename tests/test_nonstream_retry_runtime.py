"""Контракт runtime однократного nonstream retry: дедлайн до слота, слот не держится во сне."""

from __future__ import annotations

import time

import pytest

from core import nonstream_retry_runtime as runtime_module
from core.nonstream_aggregator import NonstreamError
from core.nonstream_retry_runtime import RetryRuntime, retry_incomplete_once


class _Window:
    def expired(self) -> bool:
        return False


class _Bulkhead:
    def __init__(self, outcomes: list[bool]) -> None:
        self._outcomes = list(outcomes)
        self.held = 0
        self.acquires = 0
        self.releases = 0

    def try_acquire(self) -> bool:
        self.acquires += 1
        ok = self._outcomes.pop(0) if self._outcomes else True
        self.held += int(ok)
        return ok

    def release(self) -> None:
        self.releases += 1
        self.held -= 1


def _runtime(bulkhead: _Bulkhead, deadline: float | None) -> RetryRuntime:
    return RetryRuntime(
        error=NonstreamError(502, "upstream_incomplete_stream", "x"),
        window=_Window(),
        reopen=lambda: object(),  # type: ignore[return-value]
        deadline=deadline,
        poll_interval_s=0.2,
        bulkhead=bulkhead,
        read_once=lambda _response: b"ok",
    )


def test_expired_deadline_never_acquires_bulkhead_slot() -> None:
    bulkhead = _Bulkhead([True])
    runtime = _runtime(bulkhead, deadline=time.monotonic() - 1.0)
    with pytest.raises(NonstreamError) as error:
        retry_incomplete_once(runtime, policy_enabled=True, request_eligible=True)
    assert error.value.code == "upstream_timeout"
    assert bulkhead.acquires == 0 and bulkhead.held == 0


def test_bulkhead_slot_released_during_retry_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bulkhead = _Bulkhead([True, True])
    held_during_sleep: list[int] = []
    monkeypatch.setattr(
        runtime_module.time, "sleep", lambda _s: held_during_sleep.append(bulkhead.held)
    )
    monkeypatch.setattr(runtime_module.random, "uniform", lambda *_: 0.5)
    runtime = _runtime(bulkhead, deadline=time.monotonic() + 10.0)
    assert (
        retry_incomplete_once(runtime, policy_enabled=True, request_eligible=True)
        == b"ok"
    )
    assert held_during_sleep == [0]
    assert (bulkhead.acquires, bulkhead.releases, bulkhead.held) == (2, 2, 0)


def test_bulkhead_reacquire_failure_skips_retry_without_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bulkhead = _Bulkhead([True, False])
    monkeypatch.setattr(runtime_module.time, "sleep", lambda _s: None)
    monkeypatch.setattr(runtime_module.random, "uniform", lambda *_: 0.5)
    runtime = _runtime(bulkhead, deadline=time.monotonic() + 10.0)
    assert (
        retry_incomplete_once(runtime, policy_enabled=True, request_eligible=True)
        is None
    )
    assert (bulkhead.acquires, bulkhead.releases, bulkhead.held) == (2, 1, 0)
