"""Контракты общего бюджета, владения ресурсами и активности транспорта."""

from __future__ import annotations

import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytest

from adapters.passthrough_adapter import ClientGone, PassthroughConnectionPool
from core.liveness_signals import LivenessWindow, SseProgress, WindowSpec
from core.passthrough_sliding_window import SlidingDeadline, init_sliding_stream
from core.resilience import Bulkhead, CircuitBreaker, ResilienceLease
from core.route_attempts import AttemptCancelled, AttemptPhase, RouteAttemptRunner, RouteUnavailable
from core.route_health_policy import RetryBudgetConfig
from tests.test_transport_modularity import ROOT, violations
from tests.test_transport_eligibility import (
    request_body,
    stage_entry,
    transport_options as transport_options,
)
from tests.test_transport_replay import (
    _handle,
    _legacy_decision,
    _refuse,
    test_committed_sse_never_replays as test_committed_sse_never_replays,
    test_credential_revoke_after_readiness_prevents_wire_send as test_credential_revoke_after_readiness_prevents_wire_send,
    test_partial_write_never_sends_second_post as test_partial_write_never_sends_second_post,
    test_read_timeout_after_body_never_sends_second_post as test_read_timeout_after_body_never_sends_second_post,
    test_unknown_load_envelope_cannot_approve_first_call_bounds as test_unknown_load_envelope_cannot_approve_first_call_bounds,
)
from tests.transport_test_support import (
    RecordingSink,
    RecordingUpstream,
    make_adapter,
    semantic_equal,
)


class FakeClock:
    """Монотонное время без сна и зависимости от скорости хоста."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class CountedConnection:
    """Минимальное соединение, показывающее повторный cleanup."""

    def __init__(self) -> None:
        self.closes = 0
        self.sock: Any = None
        self.response = SimpleNamespace(
            status=200, will_close=True, getheader=lambda _: None, isclosed=lambda: True,
        )

    def close(self) -> None:
        self.closes += 1

    def connect(self) -> None:
        return

    def getresponse(self) -> Any:
        return self.response


def _budget() -> RetryBudgetConfig:
    return RetryBudgetConfig(
        total_budget_s=20, reserve_s=2, min_attempt_budget_s=1,
        max_attempts=3, idle_timeout_s=5,
    )


def _decide(index: int, elapsed: float, outcome: dict) -> Any:
    decide = stage_entry("core.route_attempts", "decide_attempt", _legacy_decision)
    return decide(_budget(), index, elapsed, outcome)


def _outcome(status: int, phase: str = "RESPONSE_HEADERS") -> dict[str, Any]:
    return {"status_code": status, "phase": phase, "body_sent": True, "committed": False}


def test_adversarial_files_obey_independent_ast_bounds() -> None:
    for name in ("replay", "resilience"):
        path = "tests/test_transport_" + name + ".py"
        assert violations(path, b"", (ROOT / path).read_bytes()) == []


@pytest.mark.semantic_red("phase_aware_attempt_budget")
@pytest.mark.parametrize("outcome,expected", [
    (_outcome(401), True), (_outcome(429), True), (_outcome(503), True),
    (_outcome(403), False), (_outcome(500), False),
    (_outcome(502), False), (_outcome(504), False),
    (_outcome(0, "SENDING"), False),
    ({**_outcome(0, "CONNECTING"), "body_sent": False}, True),
    ({**_outcome(503, "COMMITTED"), "committed": True}, False),
    ({**_outcome(503), "committed": True}, False),
    (_outcome(503, "TERMINAL"), False),
])
def test_stage_w2_b_attempt_budget_never_authorizes_ambiguous_replay(
    outcome: dict, expected: bool,
) -> None:
    clock = FakeClock()
    clock.now = 4.0
    decision = _decide(1, clock(), outcome)
    semantic_equal(decision.allow_retry, expected, "phase_aware_attempt_budget")
    assert decision.attempt_budget_s == (7.0 if expected else 0.0)


@pytest.mark.parametrize("index,elapsed,allowed,budget", [
    (1, 0.0, True, 9.0), (1, 7.0, True, 5.5), (1, 16.0, True, 1.0),
    (1, 17.0, False, 0.0), (1, 18.0, False, 0.0), (1, 20.0, False, 0.0),
    (0, 0.0, True, 6.0), (2, 0.0, True, 18.0), (3, 0.0, False, 0.0),
])
def test_stage_w2_b_elapsed_waits_consume_original_budget(
    index: int, elapsed: float, allowed: bool, budget: float,
) -> None:
    clock = FakeClock()
    clock.now = elapsed
    decision = _decide(index, clock(), _outcome(503))
    assert (decision.allow_retry, decision.attempt_budget_s) == (allowed, budget)


@pytest.mark.semantic_red("one_owner_no_nested_retry")
@pytest.mark.parametrize("stream", [False, True])
def test_stage_w2_d_weighted_attempt_has_no_nested_local_retry(stream: bool) -> None:
    with RecordingUpstream() as upstream:
        _refuse(upstream, 503)
        adapter, sink = make_adapter(upstream), RecordingSink()
        try:
            _handle(adapter, sink, request_body(stream))
        finally:
            adapter.shutdown()
        assert sink.status == 503
        actual = (upstream.post_count, upstream.body_bytes, adapter.active_count())
    size = len(json.dumps(request_body(stream)).encode())
    semantic_equal(actual, (1, size, 0), "one_owner_no_nested_retry")


@pytest.mark.parametrize("mode", ["success", "client_gone", "read_error"])
def test_stage_w2_d_cleanup_once_on_each_response_exit(
    monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    connection = CountedConnection()
    with RecordingUpstream() as upstream:
        adapter, sink = make_adapter(upstream), RecordingSink()
        monkeypatch.setattr(adapter, "_open", lambda *args, **kwargs: connection)

        def respond(*args: Any, **kwargs: Any) -> bool:
            if mode == "client_gone":
                raise ClientGone()
            if mode == "read_error":
                raise TimeoutError("fixture read failure")
            return True

        monkeypatch.setattr(adapter, "_respond", respond)
        try:
            if mode == "read_error":
                with pytest.raises(TimeoutError, match="fixture read failure"):
                    _handle(adapter, sink, request_body())
            else:
                _handle(adapter, sink, request_body())
            assert adapter.active_count() == 0
            assert adapter._slots.acquire(blocking=False)
            adapter._slots.release()
        finally:
            adapter.shutdown()
        assert connection.closes == 1
        assert (upstream.post_count, upstream.body_bytes) == (0, 0)


def test_overlapping_leases_cannot_release_another_requests_slot() -> None:
    bulkhead, observed = Bulkhead("shared-route", 2), []
    first = ResilienceLease("shared-route", bulkhead_lease=bulkhead.acquire())
    second = ResilienceLease("shared-route", bulkhead_lease=bulkhead.acquire())
    try:
        observed.append(bulkhead.active)
        first.close()
        observed.append(bulkhead.active)
        third = ResilienceLease("shared-route", bulkhead_lease=bulkhead.acquire())
        try:
            observed.append(bulkhead.active)
            first.close()
            observed.append(bulkhead.active)
            second.close()
            observed.append(bulkhead.active)
        finally:
            third.close()
    finally:
        first.close()
        second.close()
    assert observed + [bulkhead.active] == [2, 1, 2, 2, 1, 0]


def test_half_open_reserves_exactly_one_probe_under_contention() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(
        "shared-route", fail_threshold=1, cooldown_s=5, cooldown_jitter=0, clock=clock,
    )
    allowed, generation, _ = breaker.acquire()
    assert allowed
    breaker.record_failure(generation)
    clock.now = 4.999
    assert not breaker.acquire()[0]
    clock.now = 5.0
    with ThreadPoolExecutor(max_workers=8) as workers:
        admissions = list(workers.map(lambda _: breaker.acquire(), range(8)))
    assert sum(allowed for allowed, _, _ in admissions) == 1
    probe = next(result for result in admissions if result[0])
    assert probe[2] is True
    breaker.record_discard(probe[1], "client_gone")
    assert breaker.failures == 0
    assert breaker.acquire()[0:3:2] == (True, True)
    breaker.record_discard(breaker.generation, "test_cleanup")


def test_stage_w2_d_pool_expiry_and_shutdown_close_each_connection_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock, idle, replacement = FakeClock(), CountedConnection(), CountedConnection()
    idle.sock = SimpleNamespace(settimeout=lambda _: None)
    module = importlib.import_module(PassthroughConnectionPool.__module__)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=clock))
    monkeypatch.setattr(module, "http", SimpleNamespace(client=SimpleNamespace(
        HTTPConnection=lambda *args, **kwargs: replacement,
    )))
    pool = PassthroughConnectionPool(max_keepalive=1, keepalive_expiry_s=5)
    try:
        pool.release_connection("fixture", 1, idle)
        clock.now = 5.001
        connection, reused = pool.get_connection("fixture", 1, 1)
        assert connection is replacement and reused is False
        pool.close_all()
        pool.release_connection("fixture", 1, connection, can_reuse=False)
    finally:
        pool.close_all()
    assert (idle.closes, replacement.closes) == (1, 1)


@pytest.mark.parametrize("mode", ["cancel", "revoke", "deadline"])
def test_runner_rechecks_after_acquire_and_cleans_once(mode: str) -> None:
    clock, finished, closed, sent = FakeClock(), [], [], []
    state = {"cancel": False, "ready": True}
    lease = SimpleNamespace(finish=lambda *args: finished.append(args),
                            close=lambda: closed.append(True))

    def acquire(backend: str, remaining: float) -> Any:
        assert (backend, remaining) == ("first", 6.0)
        state.update(cancel=mode == "cancel", ready=mode != "revoke")
        clock.now = 20.0 if mode == "deadline" else 0.0
        return lease

    ports = SimpleNamespace(
        ready=lambda _: state["ready"], acquire=acquire,
        execute=lambda *args: sent.append(args), retry_token=lambda: False,
        cancelled=lambda: state["cancel"],
    )
    runner = RouteAttemptRunner(["first", "first"], ports, _budget(), clock)
    expected = AttemptCancelled if mode == "cancel" else RouteUnavailable
    with pytest.raises(expected):
        runner.run()
    assert (sent, closed, len(finished)) == ([], [True], 1)
    assert finished[0][0].phase == AttemptPhase.ELIGIBLE
    assert isinstance(finished[0][1], expected)
    with pytest.raises(RuntimeError, match="already_used"):
        runner.run()
    assert (sent, closed, len(finished)) == ([], [True], 1)


@pytest.mark.parametrize("finish", ["idle_timeout", "safety_cap"])
@pytest.mark.parametrize("key,value", [
    ("content", "answer"), ("reasoning_content", "thinking"),
    ("tool_calls", [{"index": 0, "function": {"name": "probe", "arguments": "{}"}}]),
    ("mixed", [{"content": "a"}, {"reasoning_content": "b"}, {"tool_calls": [{"function": {"arguments": "{}"}}]}]),
])
def test_useful_progress_slides_past_initial_deadline(key: str, value: Any, finish: str) -> None:
    clock = FakeClock()
    cell = SlidingDeadline(5)
    cell.arm(init_sliding_stream(clock(), 5, 4, 30, True))
    window = LivenessWindow(WindowSpec(5, 4, 30), clock=clock)
    progress = SseProgress(window, True, cell)
    times = range(4, 29, 3) if finish == "safety_cap" else (4, 7, 10)
    for now in times:
        clock.now = now
        delta = value[(now // 3) % len(value)] if key == "mixed" else {key: value}
        progress.note(json.dumps({"choices": [{"delta": delta}]}))
        assert (window.remaining_s(), cell.deadline_s) == (min(4, 30 - now), min(30, now + 4))
        assert not window.expired()
    clock.now = cell.deadline_s - 1
    progress.note("keepalive")
    assert window.remaining_s() == 1.0
    clock.now = cell.deadline_s
    assert window.expired() == finish
