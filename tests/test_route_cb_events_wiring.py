"""Wave 3: bounded CB event sink and original route-count wiring."""

from __future__ import annotations

import atexit
import threading
import time
import weakref
from types import SimpleNamespace
from typing import Any

import pytest

from core import passthrough_facade as facade
from core import route_cb_guard as guard_module
from core.quota_classifier import QuotaRules
from core.retry_control import RouteCandidate
from core.route_attempts import RouteFailover, RouteRefusal
from core.route_cb import RouteCB
from core.route_cb_decisions import RouteCBEvent
from core.route_cb_guard import BoundedRouteCBSink, acquire_cb_guard, get_route_cb
from core.route_cb_policy import FailureOutcome, RouteCBConfig, RouteProbeLease
from core.routing_contract import parse_routes

KEY = ("p1", "m1", "b1")
CANARIES = (
    "sk-CANARY",
    "route/sk-CANARY",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.s1g",
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "Bearer CANARY",
)


def _event(seq: int = 0) -> RouteCBEvent:
    return RouteCBEvent("open", "p1", "m1", "b1", "open", 3, 90, 2, seq)


def _wait_for(predicate: Any) -> None:
    deadline = time.monotonic() + 2.0
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert predicate()


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(
        lock=threading.Lock(), breaker=None, route_cb=None, route_cb_config=None
    )


def test_slow_sink_never_blocks_caller_and_close_accounts_all_events() -> None:
    logged: list[str] = []

    def log(line: str) -> None:
        time.sleep(0.05)
        logged.append(line)

    sink = BoundedRouteCBSink(log)
    try:
        durations: list[int] = []
        for seq in range(300):
            started = time.perf_counter_ns()
            sink.emit(_event(seq))
            durations.append(time.perf_counter_ns() - started)
        thread = sink._thread
        assert thread is not None and thread.daemon is True
        started = time.monotonic()
        sink.close()
        durations.sort()
        assert time.monotonic() - started <= 0.5
        assert thread is not None and not thread.is_alive()
        assert durations[296] < 1_000_000 and durations[150] < 1_000_000
        assert sink.route_cb_events_dropped > 0
        assert len(logged) + sink.route_cb_events_dropped == 300
        dropped = sink.route_cb_events_dropped
        sink.close()
        sink.emit(_event())
        assert sink.route_cb_events_dropped == dropped + 1
    finally:
        sink.close()


def test_queue_full_and_reset_have_exact_loss_accounting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = BoundedRouteCBSink(lambda _line: None, maxsize=2)
    try:
        monkeypatch.setattr(sink, "_ensure_started", lambda: True)
        for seq in range(5):
            sink.emit(_event(seq))
        assert sink.route_cb_events_dropped == 3
        assert sink.reset() == 2
        assert sink.route_cb_events_dropped == 5
        assert sink.reset() == 0
    finally:
        sink.close()


def test_log_exception_is_counted_without_killing_consumer() -> None:
    def broken(_line: str) -> None:
        raise RuntimeError("log failed")

    sink = BoundedRouteCBSink(broken, maxsize=8)
    try:
        for seq in range(4):
            sink.emit(_event(seq))
        _wait_for(lambda: sink.route_cb_events_dropped == 4)
    finally:
        sink.close()
    assert sink.route_cb_events_dropped == 4


def test_canaries_never_reach_end_to_end_log_lines() -> None:
    logged: list[str] = []
    sink = BoundedRouteCBSink(logged.append)
    try:
        cb = RouteCB(RouteCBConfig(failure_threshold=1), event_sink=sink)
        for canary in CANARIES:
            for field in range(3):
                key = tuple(
                    canary if i == field else part for i, part in enumerate(KEY)
                )
                cb.record_failure(key, FailureOutcome(status=500, route_count=2))
        _wait_for(lambda: len(logged) == len(CANARIES) * 3)
    finally:
        sink.close()
    assert len(logged) == 15
    assert all(line.isascii() and len(line.encode("ascii")) <= 256 for line in logged)
    assert all(canary not in line for canary in CANARIES for line in logged)


def test_reload_closes_old_sink_and_registers_atexit_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered: list[Any] = []
    monkeypatch.setattr(atexit, "register", registered.append)
    monkeypatch.setattr(guard_module, "_ATEXIT_REGISTERED", False)
    monkeypatch.setattr(guard_module, "_ACTIVE_SINKS", weakref.WeakSet())
    rt = _runtime()
    try:
        base = {"BRIDGE_ROUTE_CB_ENABLED": "1", "BRIDGE_ROUTE_CB_EVENTS": "1"}
        get_route_cb(rt, base)
        first = rt.route_cb_sink
        get_route_cb(rt, base | {"BRIDGE_ROUTE_CB_SINGLE_ROUTE_PROTECTION": "true"})
        second = rt.route_cb_sink
        get_route_cb(rt, base | {"BRIDGE_ROUTE_CB_EVENTS": "0"})
        assert first._closed and second._closed and rt.route_cb_sink is None
        get_route_cb(rt, base)
        third = rt.route_cb_sink
        get_route_cb(rt, {"BRIDGE_ROUTE_CB_ENABLED": "0"})
        assert third._closed and rt.route_cb_sink is None and rt.breaker is not None
        assert len(registered) == 1
    finally:
        if rt.route_cb_sink is not None:
            rt.route_cb_sink.close()


def _facade_route(declared: int, sink: Any) -> SimpleNamespace:
    docs = [
        {"route_id": f"r{i}", "backend": f"b{i}", "weight": 1, "priority": 0}
        for i in range(1, declared + 1)
    ]
    host = SimpleNamespace(
        BACKENDS={},
        _client_gone=lambda _conn: False,
        _trace_headers=lambda _trace: {},
        _HandlerSink=lambda _handler, extra_headers=None: sink,
    )
    handler = SimpleNamespace(
        connection=object(), _trace=SimpleNamespace(subagent_id=None)
    )
    return SimpleNamespace(
        model_id="m1",
        model={"routing": {"routes": docs}},
        request={"messages": []},
        alias_effort=None,
        host=host,
        handler=handler,
        reject=lambda *_args: None,
    )


def _exercise_facade(
    monkeypatch: pytest.MonkeyPatch, declared: int, protect: bool
) -> tuple[bool, list[int]]:
    monkeypatch.setattr(facade, "_RUNTIME", facade._RuntimeState())
    monkeypatch.setenv("BRIDGE_ROUTE_CB_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_ROUTE_CB_EVENTS", "0")
    monkeypatch.setenv("BRIDGE_ROUTE_CB_SINGLE_ROUTE_PROTECTION", str(protect).lower())
    sink = SimpleNamespace(start=lambda *_args: None, write=lambda *_args: None)
    route = _facade_route(declared, sink)
    spec = SimpleNamespace(backend="b1", provider="p1", credential_ref="c1")
    monkeypatch.setattr(facade, "prepare_post_body", lambda _route: b"{}")
    monkeypatch.setattr(facade, "route_order", lambda *_args: ("b1",))
    monkeypatch.setattr(facade, "_eligible", lambda *_args: True)

    def fail(*_args: Any) -> None:
        raise RouteRefusal(500, (), b"{}")

    counts: list[int] = []
    original = facade.acquire_cb_guard

    def capture(*args: Any) -> Any:
        counts.append(args[4])
        return original(*args)

    monkeypatch.setattr(facade, "_attempt", fail)
    monkeypatch.setattr(facade, "acquire_cb_guard", capture)
    for _ in range(3):
        facade._run_routes(route, [spec], "seed", None)
    cb = facade._RUNTIME.route_cb
    state = cb._tuples.get(KEY)
    return state is not None and state.open_until is not None, counts


@pytest.mark.parametrize(
    ("declared", "protect", "expected_open"),
    [(2, True, True), (1, True, False), (1, False, True)],
)
def test_facade_uses_declared_route_count_for_single_route_decision(
    monkeypatch: pytest.MonkeyPatch, declared: int, protect: bool, expected_open: bool
) -> None:
    opened, counts = _exercise_facade(monkeypatch, declared, protect)
    assert opened is expected_open
    assert counts == [declared] * 3


def test_guard_outcomes_carry_route_count() -> None:
    outcomes: list[Any] = []
    cb = SimpleNamespace(
        try_acquire=lambda key, _now, route_count=0: RouteProbeLease(
            key, route_count=route_count
        ),
        record_failure=lambda _key, outcome, _lease: outcomes.append(outcome),
    )
    candidate = RouteCandidate("b1", "m1", "b1", "c1", "id")
    first = acquire_cb_guard((cb, None), candidate, KEY, 10.0, 2)
    first.record_exception(TimeoutError("boom"))
    assert first.done is True
    first.record_exception(TimeoutError("second"))
    assert len(outcomes) == 1
    second = acquire_cb_guard((cb, None), candidate, KEY, 10.0, 2)
    refusal = RouteRefusal(500)
    second.record_error(
        refusal, SimpleNamespace(), RouteFailover(), QuotaRules.from_config()
    )
    assert second.done is True
    assert (
        second.record_error(
            refusal, SimpleNamespace(), RouteFailover(), QuotaRules.from_config()
        )
        is None
    )
    assert len(outcomes) == 2
    assert first.route_count == second.route_count == 2
    assert [outcome.route_count for outcome in outcomes] == [2, 2]
    assert len(parse_routes(_facade_route(2, SimpleNamespace()).model)) == 2


def test_sink_rejects_non_positive_maxsize() -> None:
    for maxsize in (0, -1):
        with pytest.raises(ValueError, match="maxsize must be >= 1"):
            BoundedRouteCBSink(lambda _line: None, maxsize=maxsize)


def test_thread_start_failure_keeps_sink_safe_and_closeable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_self: threading.Thread) -> None:
        raise RuntimeError("cannot start thread")

    monkeypatch.setattr(threading.Thread, "start", boom)
    sink = BoundedRouteCBSink(lambda _line: None)
    sink.emit(_event())
    assert sink._thread is None
    assert sink.route_cb_events_dropped == 1
    sink.close()


def test_thread_start_never_holds_state_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = BoundedRouteCBSink(lambda _line: None)
    orig_start = threading.Thread.start
    seen: list[bool] = []

    def spy(self: threading.Thread) -> None:
        assert not sink._state_lock.locked()
        seen.append(True)
        orig_start(self)

    monkeypatch.setattr(threading.Thread, "start", spy)
    sink.emit(_event())
    assert seen == [True]
    sink.close()
