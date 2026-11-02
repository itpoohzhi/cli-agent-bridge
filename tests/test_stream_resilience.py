"""Регрессии разделения прогресса процесса, клиентского heartbeat и безопасного retry."""

from __future__ import annotations

import io
import json
import os
import queue
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator, Mapping
from http.client import HTTPConnection
from types import SimpleNamespace
from typing import Protocol, TypedDict, Unpack, cast, override
from unittest.mock import Mock

import pytest

from adapters.passthrough_adapter import (
    PassthroughLimits,
    ResponseSink,
    StreamOutcome,
    relay_sse,
)
from core.lifecycle import KeepaliveController
from core.turn_session_manager import TurnSessionManager
from core.watchdog import AdaptiveTimeoutController, ProcessWatchdog, WatchdogMetrics
from tests.rpc_testlib import RpcCase
from tests.test_http_presend_resilience import json_reply, stand


class Delta(TypedDict, total=False):
    content: str
    reasoning_content: str


class Choice(TypedDict):
    delta: Delta
    finish_reason: str | None


class Chunk(TypedDict):
    id: str
    object: str
    created: int
    model: str
    choices: list[Choice]


class ErrorDetail(TypedDict):
    type: str
    code: int


class ErrorBody(TypedDict):
    error: ErrorDetail


class ControllerOptions(TypedDict, total=False):
    io_wait_cap_s: float
    safety_cap_s: float


class HandleArguments(TypedDict):
    path: str
    raw_body: bytes
    request: Mapping[str, object]
    headers: Mapping[str, str]
    sink: ResponseSink


class HandlerFixture(Protocol):
    path: str
    headers: dict[str, str]
    wfile: io.BytesIO
    connection: Mock
    send_response: Mock
    send_header: Mock
    end_headers: Callable[[], None]
    request_version: str

    def handle_expect_100(self) -> bool: ...


class MockSink(Protocol):
    start: Mock
    write: Mock
    client_gone: Callable[[], bool]


class OpenConnection(Protocol):
    def __call__(
        self,
        path: str,
        raw_body: bytes,
        headers: Mapping[str, str],
        *,
        presend_deadline: float | None,
    ) -> HTTPConnection: ...


def serve_passthrough(
    handler: HandlerFixture,
    adapter: object,
    raw: bytes,
    request: dict[str, object],
    model: str,
) -> None:
    """Типизирует динамический шов настоящего Handler, не подменяя реализацию."""
    method = cast(
        Callable[[object, bytes, dict[str, object], str], None],
        getattr(handler, "_serve_passthrough"),
    )
    method(adapter, raw, request, model)


def serve_sse(handler: HandlerFixture, context: dict[str, object]) -> None:
    method = cast(
        Callable[[dict[str, object]], None], getattr(handler, "_serve_sse_body")
    )
    method(context)


def discard(_value: object) -> None:
    return None


@pytest.fixture(autouse=True)
def fake_client_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    import server

    def connected(_sock: object) -> bool:
        return False

    monkeypatch.setattr(server, "_client_gone", connected)


class Clock:
    """Управляемое монотонное время без ожиданий в тестах."""

    def __init__(self) -> None:
        self.now: float = 1000.0

    def __call__(self) -> float:
        return self.now


def metrics(
    state: str = "S", *, alive: bool = True, cpu: float = 0.0
) -> WatchdogMetrics:
    return WatchdogMetrics(4242, alive, (), (), cpu, cpu, states=[state])


def controller(
    clock: Clock, state: str = "S", **kwargs: Unpack[ControllerOptions]
) -> AdaptiveTimeoutController:
    watchdog = Mock(spec=ProcessWatchdog)
    cast(Mock, getattr(watchdog, "sample")).return_value = metrics(state)
    ctrl = AdaptiveTimeoutController(
        idle_timeout_s=10,
        finish_reserve_s=0,
        clock=clock,
        watchdog=cast(ProcessWatchdog, watchdog),
        **kwargs,
    )
    ctrl.register_pgid(4242)
    return ctrl


def test_active_keepalive_resets_watchdog() -> None:
    # Предикат pi-ai: только truthy content/reasoning_content считается прогрессом.
    frame = KeepaliveController.sse_data_chunk(model="test")
    chunk = cast(Chunk, json.loads(frame.removeprefix("data: ").strip()))
    delta = chunk["choices"][0]["delta"]
    idle_deadline = 300
    for now in range(10, 1001, 10):
        assert now < idle_deadline
        if delta.get("content") or delta.get("reasoning_content"):
            idle_deadline = now + 300
    assert chunk["id"].startswith("chatcmpl-ping-")
    assert chunk["object"] == "chat.completion.chunk"
    assert chunk["choices"][0]["finish_reason"] is None
    assert delta == {"reasoning_content": " "}
    assert (
        cast(
            Chunk, json.loads(KeepaliveController.sse_data_chunk(reasoning=False)[6:])
        )["choices"][0]["delta"]
        == {}
    )


@pytest.mark.parametrize("state", ["S", "S+", "Ss", "D", "D<", "I", "I+", "U", "U+"])
def test_process_watchdog_io_grace(state: str) -> None:
    clock = Clock()
    ctrl = controller(clock, state, io_wait_cap_s=900)
    clock.now += 120
    assert ctrl.check()[0] is False
    assert ctrl.last_activity_ts == 1000
    clock.now = 1899.9
    assert ctrl.check()[0] is False
    clock.now = 1900
    assert ctrl.check()[:2] == (True, "idle_timeout")


def test_process_watchdog_terminates_after_cap() -> None:
    clock = Clock()
    ctrl = controller(clock, safety_cap_s=3600)
    clock.now += 3600
    ctrl.record_activity("cpu")
    assert ctrl.check()[:2] == (True, "absolute_cap")


@pytest.mark.parametrize("state", ["R", "T", "Z", "X", "?", ""])
def test_unknown_or_dead_states_get_no_io_grace(state: str) -> None:
    clock = Clock()
    ctrl = controller(clock, state)
    clock.now += 11
    assert ctrl.check()[:2] == (True, "idle_timeout")
    assert not metrics(state, alive=False).is_waiting_io()


def test_disabled_grace_and_idle_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_IO_GRACE_ENABLED", "false")
    clock = Clock()
    ctrl = controller(clock)
    clock.now += 11
    assert ctrl.check()[:2] == (True, "idle_timeout")
    assert AdaptiveTimeoutController(idle_timeout_s=1).idle_timeout_s >= 10


def test_safety_cap_despite_cpu_progress() -> None:
    clock = Clock()
    ctrl = controller(clock, safety_cap_s=30)
    cast(Mock, getattr(ctrl.watchdog, "sample")).return_value = metrics("R", cpu=1)
    for offset in (11, 22):
        clock.now = 1000 + offset
        assert ctrl.check()[0] is False
    clock.now = 1030
    assert ctrl.check()[:2] == (True, "absolute_cap")


def test_env_configuration_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.lifecycle import PreSendRetry

    for key, value in {
        "BRIDGE_IO_WAIT_CAP_S": "321.5",
        "BRIDGE_SAFETY_CAP_S": "700.5",
        "BRIDGE_MAX_RETRIES": "2",
        "BRIDGE_RETRY_BUDGET_S": "19.5",
        "BRIDGE_KEEPALIVE_INTERVAL_S": "0.1",
        "BRIDGE_IO_GRACE_ENABLED": "off",
    }.items():
        monkeypatch.setenv(key, value)
    ctrl = AdaptiveTimeoutController()
    assert (ctrl.io_wait_cap_s, ctrl.safety_cap_s, ctrl.io_grace_enabled) == (
        321.5,
        700.5,
        False,
    )
    retry = PreSendRetry()
    assert (retry.max_retries, retry.budget_s) == (2, 19.5)
    assert KeepaliveController().effective_interval() == 0.1


@pytest.mark.parametrize("bad", ["nan", "inf", "-1", "0", "broken", ""])
def test_invalid_env_uses_safe_fallback(
    monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    from core.lifecycle import PreSendRetry

    for key in (
        "IO_WAIT_CAP_S",
        "SAFETY_CAP_S",
        "RETRY_BUDGET_S",
        "KEEPALIVE_INTERVAL_S",
        "MAX_RETRIES",
        "IO_GRACE_ENABLED",
    ):
        monkeypatch.setenv("BRIDGE_" + key, bad)
    ctrl = AdaptiveTimeoutController()
    assert (ctrl.io_wait_cap_s, ctrl.safety_cap_s) == (900, 3600)
    assert KeepaliveController().effective_interval() == 10
    assert PreSendRetry().budget_s == 60
    assert PreSendRetry().max_retries == (0 if bad == "0" else 3)


def test_state_sampling_reads_actual_sleeping_group() -> None:
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; print('ready', flush=True); time.sleep(60)",
        ],
        start_new_session=True,
        stdout=subprocess.PIPE,
    )
    try:
        assert cast(io.BufferedReader, proc.stdout).readline() == b"ready\n"
        sample = ProcessWatchdog().sample(proc.pid)
        assert sample.alive
        assert sample.states
        assert sample.is_waiting_io()
        assert all(state[0] not in "ZX" for state in sample.states)
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        _ = proc.wait(timeout=5)


def test_turn_manager_heartbeat_preserves_identity_and_history(tmp_path: Path) -> None:
    manager = TurnSessionManager(state_root=tmp_path)
    turn, _ = manager.create_or_attach_turn(
        model="test", backend="test", cwd=str(tmp_path), messages=[]
    )
    started = turn.timeout_controller.last_activity_ts
    frames = manager.iter_sse_stream(turn, keepalive_interval_s=0.01)
    try:
        heartbeat = next(frames)
        data = next(
            line[6:] for line in heartbeat.splitlines() if line.startswith("data: ")
        )
        chunk = cast(Chunk, json.loads(data))
        assert chunk["id"] == f"chatcmpl-turn-{turn.turn_id}"
        assert chunk["model"] == "test"
        assert chunk["choices"][0]["delta"].get("reasoning_content")
        assert turn.buffer.get_reasoning_text() == ""
        assert turn.buffer.get_content_text() == ""
        assert turn.timeout_controller.last_activity_ts == started
    finally:
        cast(Generator[str, None, None], frames).close()
        manager.finalize_abandoned_turn(turn)


def make_handler() -> HandlerFixture:
    import server

    handler = cast(HandlerFixture, cast(object, server.Handler.__new__(server.Handler)))
    setattr(handler, "_trace", None)
    handler.path = "/v1/chat/completions"
    handler.headers = {}
    handler.wfile = io.BytesIO()
    handler.connection = Mock()
    setattr(handler, "_current_lease", lambda: Mock())
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()
    return handler


@pytest.mark.parametrize("status", [502, 503, None])
def test_presend_retry_resilience(
    monkeypatch: pytest.MonkeyPatch, status: int | None
) -> None:
    from core.backend_adapter import PreSendTransientError

    monkeypatch.setenv("BRIDGE_RETRY_BACKOFF_S", "0.001")
    handler = make_handler()
    attempts: list[int] = []

    def handle(**kwargs: Unpack[HandleArguments]) -> None:
        attempts.append(1)
        if len(attempts) < 3:
            raise PreSendTransientError("not dispatched", status_code=status)
        sink = kwargs["sink"]
        sink.start(200, [])
        sink.write(b"ok")

    adapter = SimpleNamespace(id="test", handle=handle)
    serve_passthrough(handler, adapter, b"{}", {}, "test")
    assert len(attempts) == 3
    assert handler.wfile.getvalue() == b"ok"
    cast(Mock, getattr(handler, "send_response")).assert_called_once_with(200)


@pytest.mark.parametrize("emission", ["headers", "heartbeat", "content"])
def test_no_retry_after_first_downstream_emission(
    monkeypatch: pytest.MonkeyPatch, emission: str
) -> None:
    from core.backend_adapter import PreSendTransientError

    monkeypatch.setenv("BRIDGE_RETRY_BACKOFF_S", "0.001")
    handler = make_handler()
    attempts: list[int] = []

    def handle(**kwargs: Unpack[HandleArguments]) -> None:
        attempts.append(1)
        sink = kwargs["sink"]
        sink.start(200, [])
        if emission != "headers":
            sink.write(
                KeepaliveController.sse_data_chunk().encode()
                if emission == "heartbeat"
                else b"first"
            )
        raise PreSendTransientError("late transport error", status_code=502)

    with pytest.raises(PreSendTransientError):
        serve_passthrough(
            handler, SimpleNamespace(id="test", handle=handle), b"{}", {}, "test"
        )
    assert len(attempts) == 1


def test_ambiguous_upstream_response_is_never_replayed() -> None:
    handler = make_handler()
    calls: list[int] = []

    def handle(**kwargs: Unpack[HandleArguments]) -> None:
        calls.append(1)
        kwargs["sink"].start(502, [])
        kwargs["sink"].write(b"upstream may have started")

    serve_passthrough(
        handler, SimpleNamespace(id="test", handle=handle), b"{}", {}, "test"
    )
    assert len(calls) == 1


def test_retry_exhaustion_budget_and_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.backend_adapter import PreSendTransientError
    from core.lifecycle import PreSendRetry

    monkeypatch.setenv("BRIDGE_MAX_RETRIES", "2")
    clock = Clock()
    waits: list[float] = []

    def wait(delay: float) -> bool:
        waits.append(delay)
        clock.now += delay
        return False

    op = Mock(side_effect=PreSendTransientError("connect refused"))
    with pytest.raises(PreSendTransientError):
        PreSendRetry(clock=clock, wait=wait, rng=lambda _lo, hi: hi).run(op)
    assert op.call_count == 3
    assert len(waits) == 2
    monkeypatch.setenv("BRIDGE_RETRY_BUDGET_S", "0.1")
    op.reset_mock()
    with pytest.raises(PreSendTransientError):
        PreSendRetry(clock=clock, wait=wait, rng=lambda _lo, hi: hi).run(op)
    assert op.call_count == 1
    monkeypatch.setenv("BRIDGE_RETRY_BUDGET_S", "60")
    op.reset_mock()
    cancelled_wait = Mock(return_value=True)
    with pytest.raises(PreSendTransientError):
        PreSendRetry(wait=cancelled_wait).run(op)
    assert op.call_count == 1
    cancelled_wait.assert_called_once()


def test_zero_retries_disables_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.backend_adapter import PreSendTransientError
    from core.lifecycle import PreSendRetry

    monkeypatch.setenv("BRIDGE_MAX_RETRIES", "0")
    op = Mock(side_effect=PreSendTransientError("not sent"))
    with pytest.raises(PreSendTransientError):
        PreSendRetry().run(op)
    assert op.call_count == 1


def test_real_backoff_is_cancelled_promptly(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.backend_adapter import PreSendTransientError
    from core.lifecycle import PreSendRetry

    monkeypatch.setenv("BRIDGE_RETRY_CANCEL_POLL_S", "0.01")
    cancelled, attempted, stopped = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )

    def operation() -> None:
        attempted.set()
        raise PreSendTransientError("not sent")

    def run() -> None:
        try:
            PreSendRetry(cancelled=cancelled.is_set, rng=lambda _lo, hi: hi).run(
                operation
            )
        except PreSendTransientError:
            stopped.set()

    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert attempted.wait(1)
        cancelled.set()
        assert stopped.wait(0.5), "отмена должна прерывать реальный backoff"
    finally:
        cancelled.set()
        worker.join(timeout=2)


def test_slow_successful_headers_keep_normal_read_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from http.server import BaseHTTPRequestHandler

    monkeypatch.setenv("BRIDGE_RETRY_BUDGET_S", "0.01")

    def slow(handler: BaseHTTPRequestHandler) -> None:
        _ = threading.Event().wait(0.05)
        json_reply(200)(handler)

    with stand([slow]) as instance:
        status, _body = instance.response()
        assert status == 200
        assert len(instance.requests) == 1


@pytest.mark.parametrize("status", [502, 503])
def test_exhaustion_preserves_upstream_body_and_retry_after(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    from http.client import HTTPResponse
    from http.server import BaseHTTPRequestHandler

    monkeypatch.setenv("BRIDGE_MAX_RETRIES", "1")
    payload = b'{"error":{"code":"backend_overloaded","detail":"preserve me"}}'

    def reject(handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(payload)))
        handler.send_header("Retry-After", "7")
        handler.end_headers()
        _ = handler.wfile.write(payload)
        handler.wfile.flush()

    with stand([reject]) as instance:
        with instance.connect() as sock:
            response = HTTPResponse(sock)
            response.begin()
            assert response.status == status
            assert response.getheader("Retry-After") == "7"
            assert response.read() == payload
        assert len(instance.requests) == 2


def test_transient_error_oversize_body_keeps_bounded_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from functools import partial
    from adapters.passthrough_adapter import PassthroughLimits
    from tests import test_http_presend_resilience as http_tests

    monkeypatch.setattr(
        http_tests, "PassthroughLimits", partial(PassthroughLimits, max_body_bytes=8)
    )
    with stand([json_reply(503, b"0123456789")]) as instance:
        status, body = instance.response()
        assert status == 502
        assert (
            cast(ErrorBody, json.loads(body))["error"]["type"]
            == "upstream_response_too_large"
        )


def test_keepalive_bounds_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_KEEPALIVE_INTERVAL_S", "20")
    keepalive = KeepaliveController()
    assert keepalive.effective_interval() == 20
    assert keepalive.effective_interval(0.00001) == 0.05
    monkeypatch.setenv("BRIDGE_KEEPALIVE_MIN_INTERVAL_S", "0.02")
    assert KeepaliveController().effective_interval(0.001) == 0.02


def test_legacy_safety_cap_is_consistent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BRIDGE_SAFETY_CAP_S", raising=False)
    monkeypatch.setenv("DROID_DSH_BRIDGE_SAFETY_CAP_S", "612")
    assert AdaptiveTimeoutController().safety_cap_s == 612
    assert TurnSessionManager(state_root=tmp_path).safety_cap_s == 612


def test_connect_deadline_and_timeout_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import http.client
    from adapters.passthrough_adapter import PassthroughAdapter
    from core.backend_adapter import PreSendTransientError

    adapter = PassthroughAdapter(
        "test", {"base_url": "http://127.0.0.1:12345/v1"}, dict
    )
    conn = Mock()
    cast(Mock, getattr(conn, "connect")).side_effect = TimeoutError("connect timeout")
    factory = Mock(return_value=conn)
    open_connection = cast(OpenConnection, getattr(adapter, "_open"))
    monkeypatch.setattr(http.client, "HTTPConnection", factory)
    with pytest.raises(PreSendTransientError):
        _ = open_connection(
            "/v1/chat/completions",
            b"{}",
            {},
            presend_deadline=time.monotonic() + 0.2,
        )
    assert 0 < factory.call_args.kwargs["timeout"] <= 0.2
    with pytest.raises(PreSendTransientError):
        _ = open_connection("/v1/chat/completions", b"{}", {}, presend_deadline=None)
    assert factory.call_args.kwargs["timeout"] == adapter.limits.connect_timeout_s
    with pytest.raises(PreSendTransientError) as exhausted:
        _ = open_connection(
            "/v1/chat/completions", b"{}", {}, presend_deadline=time.monotonic() - 1
        )
    assert exhausted.value.status_code == 504
    # Duck-typed standalone sink без нового capability сохраняет прежний 504.
    sink = cast(
        MockSink,
        cast(
            object,
            SimpleNamespace(start=Mock(), write=Mock(), client_gone=lambda: False),
        ),
    )
    adapter.handle(
        path="/v1/chat/completions",
        raw_body=b"{}",
        request={},
        headers={},
        sink=cast(ResponseSink, cast(object, sink)),
    )
    assert cast(Mock, getattr(sink, "start")).call_args.args[0] == 504
    assert (
        cast(
            ErrorBody,
            json.loads(
                cast(bytes, cast(Mock, getattr(sink, "write")).call_args.args[0])
            ),
        )["error"]["type"]
        == "upstream_timeout"
    )
    monkeypatch.setenv("BRIDGE_MAX_RETRIES", "0")
    handler = make_handler()
    serve_passthrough(handler, adapter, b"{}", {}, "test")
    assert cast(Mock, getattr(handler, "send_response")).call_args.args[0] == 504
    assert cast(ErrorBody, json.loads(handler.wfile.getvalue()))["error"]["code"] == 504


def test_handler_commit_outside_sink_prevents_retry() -> None:
    from core.backend_adapter import PreSendTransientError

    handler = make_handler()
    operation = Mock(side_effect=PreSendTransientError("not sent"))
    setattr(handler, "_downstream_committed", True)
    with pytest.raises(PreSendTransientError):
        serve_passthrough(
            handler, SimpleNamespace(id="test", handle=operation), b"{}", {}, "test"
        )
    operation.assert_called_once()


def test_interim_100_already_commits_first_client_bytes() -> None:
    import server
    from types import MethodType
    from core.backend_adapter import PreSendTransientError

    handler = make_handler()
    handler.request_version = "HTTP/1.1"
    handler.end_headers = cast(
        Callable[[], None], MethodType(server.Handler.end_headers, handler)
    )
    assert handler.handle_expect_100()
    assert handler.wfile.getvalue().startswith(b"HTTP/1.1 100 Continue\r\n")
    assert cast(bool, getattr(handler, "_downstream_committed"))
    operation = Mock(side_effect=PreSendTransientError("not sent"))
    with pytest.raises(PreSendTransientError):
        serve_passthrough(
            handler, SimpleNamespace(id="test", handle=operation), b"{}", {}, "test"
        )
    operation.assert_called_once()


@pytest.mark.parametrize(
    "alias", ["BRIDGE_KEEPALIVE_S", "DROID_DSH_BRIDGE_KEEPALIVE_S"]
)
def test_shared_keepalive_resolver_aliases(
    monkeypatch: pytest.MonkeyPatch, alias: str
) -> None:
    monkeypatch.delenv("BRIDGE_KEEPALIVE_INTERVAL_S", raising=False)
    monkeypatch.delenv("BRIDGE_KEEPALIVE_S", raising=False)
    monkeypatch.delenv("DROID_DSH_BRIDGE_KEEPALIVE_S", raising=False)
    monkeypatch.setenv(alias, "30")
    assert KeepaliveController().effective_interval() == 30
    assert KeepaliveController().effective_interval(30) == 30


@pytest.mark.parametrize(
    "scenario", ["io_grace", "io_cap", "safety_cap", "disabled", "cached_cpu"]
)
def test_facade_io_grace_caps_and_ps_throttle(
    monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    import server

    clock = Clock()
    samples: list[float] = []
    monkeypatch.setattr(
        server,
        "time",
        SimpleNamespace(**{**vars(time), "monotonic": clock, "sleep": discard}),
    )
    monkeypatch.setattr(server, "TIMEOUT_S", 100)
    monkeypatch.setattr(server, "SAFETY_CAP_S", 20 if scenario == "safety_cap" else 100)
    monkeypatch.setattr(server, "SILENCE_WATCHDOG_S", 10)
    monkeypatch.setenv(
        "BRIDGE_WATCHDOG_INTERVAL_S", "30" if scenario == "cached_cpu" else "5"
    )
    monkeypatch.setenv("BRIDGE_IO_WAIT_CAP_S", "20" if scenario == "io_cap" else "900")
    monkeypatch.setenv(
        "BRIDGE_IO_GRACE_ENABLED",
        "false" if scenario in ("disabled", "cached_cpu") else "true",
    )
    monkeypatch.setenv("BRIDGE_ADAPTIVE_WATCHDOG_ENABLED", "true")

    def sample(_pgid: int) -> WatchdogMetrics:
        samples.append(clock())
        return metrics(
            "S", cpu=1 if scenario == "cached_cpu" and len(samples) == 1 else 0
        )

    watchdog = Mock(spec=ProcessWatchdog)
    cast(Mock, getattr(watchdog, "sample")).side_effect = sample

    def watchdog_factory(**_kwargs: object) -> Mock:
        return watchdog

    monkeypatch.setattr(server, "ProcessWatchdog", watchdog_factory)

    class Queue:
        def get(self, **_kwargs: object) -> tuple[str, tuple[int, str]]:
            clock.now += 1
            if clock.now < (1050 if scenario == "cached_cpu" else 1025):
                raise queue.Empty
            return "done", (0, "ok")

    run = SimpleNamespace(
        q=Queue(),
        proc=SimpleNamespace(pid=4242),
        got_event=True,
        started=1000.0,
        last_progress=1000.0,
        cancel=threading.Event(),
        live_invalidated=False,
        _last_error="",
        err_box=[],
    )
    execute = cast(
        Callable[[object, None, bool], dict[str, object]],
        getattr(make_handler(), "_execute"),
    )
    result = execute(run, None, False)
    assert cast(float, getattr(run, "last_progress")) == (
        1011 if scenario == "cached_cpu" else 1000
    )
    assert all(b - a >= 5 for a, b in zip(samples, samples[1:]))
    assert result["state"] == ("done" if scenario == "io_grace" else "timeout")
    if scenario == "io_grace":
        assert samples == [1011, 1016, 1021]
    if scenario == "cached_cpu":
        assert samples == [1011, 1041]


def test_actual_transport_connect_reset_retries_only_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import http.client
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from adapters.passthrough_adapter import PassthroughAdapter

    requests: list[bytes] = []

    class Upstream(BaseHTTPRequestHandler):
        @override
        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_POST(self) -> None:
            requests.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            _ = self.wfile.write(b"{}")

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    worker = threading.Thread(target=upstream.serve_forever, daemon=True)
    worker.start()
    original = http.client.HTTPConnection.connect
    connections: list[http.client.HTTPConnection] = []

    def connect(conn: http.client.HTTPConnection) -> None:
        connections.append(conn)
        if len(connections) < 3:
            raise ConnectionResetError("reset before request bytes")
        original(conn)

    monkeypatch.setenv("BRIDGE_RETRY_BACKOFF_S", "0.001")
    monkeypatch.setattr(http.client.HTTPConnection, "connect", connect)
    handler = make_handler()
    adapter = PassthroughAdapter(
        "test", {"base_url": f"http://127.0.0.1:{upstream.server_port}/v1"}, dict
    )
    try:
        serve_passthrough(handler, adapter, b"{}", {}, "test")
        assert len(connections) == 3
        assert requests == [b"{}"]
        assert handler.wfile.getvalue() == b"{}"
        assert adapter.active_count() == 0
    finally:
        upstream.shutdown()
        upstream.server_close()
        worker.join(timeout=2)


def test_facade_keepalive_while_backend_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    import server

    monkeypatch.setattr(server, "KEEPALIVE_S", 0.01)
    handler = make_handler()
    heartbeat = threading.Event()
    original_emit = cast(Callable[[str], bool], getattr(handler, "_emit"))

    def emit(frame: str) -> bool:
        written = original_emit(frame)
        if '"reasoning_content": " "' in frame:
            heartbeat.set()
        return written

    def dispatch(*_args: object) -> dict[str, object]:
        assert heartbeat.wait(1), (
            "нет независимого heartbeat при заблокированном backend"
        )
        return {"state": "done", "rc": 0, "text": "", "usage": {}, "events": []}

    setattr(handler, "_emit", emit)
    setattr(handler, "_dispatch", dispatch)
    setattr(handler, "_reserve_delivery", discard)
    setattr(handler, "_record_turn_outcome", Mock())
    serve_sse(handler, {"model": "test"})
    chunks = [
        cast(Chunk, json.loads(line[6:]))
        for line in handler.wfile.getvalue().decode().splitlines()
        if line.startswith("data: ") and "[DONE]" not in line
    ]
    ping = next(c for c in chunks if c["choices"][0]["delta"].get("reasoning_content"))
    assert (ping["id"], ping["model"], ping["created"]) == (
        chunks[0]["id"],
        chunks[0]["model"],
        chunks[0]["created"],
    )


def test_facade_heartbeat_close_race_is_not_client_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import server

    class Stop:
        closed: bool = False
        timed_out: bool = False

        def set(self) -> None:
            self.closed = True

        def is_set(self) -> bool:
            return self.closed

        def wait(self, _delay: float) -> bool:
            # wait успел вернуть timeout перед set(); поток продолжился после set().
            if not self.timed_out:
                self.timed_out = True
                return False
            return self.closed

    class Worker:
        def __init__(self, *, target: Callable[[], None], **_kwargs: object) -> None:
            self.target: Callable[[], None] = target

        def start(self) -> None:
            pass

        def join(self, **_kwargs: object) -> None:
            self.target()

    monkeypatch.setattr(
        server,
        "threading",
        SimpleNamespace(**{**vars(threading), "Event": Stop, "Thread": Worker}),
    )
    handler = make_handler()

    def dispatch(*_args: object) -> dict[str, object]:
        return {
            "state": "done",
            "rc": 0,
            "text": "ok",
            "events": [("content", "ok")],
            "usage": {},
        }

    setattr(handler, "_dispatch", dispatch)
    setattr(handler, "_reserve_delivery", discard)
    setattr(handler, "_record_turn_outcome", Mock())
    serve_sse(handler, {"model": "test"})
    assert not cast(bool, getattr(handler, "_client_write_dead"))
    assert b'"finish_reason": "stop"' in handler.wfile.getvalue()


def test_facade_heartbeat_cadence_after_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import server

    clock = Clock()
    clock.now = 0
    waits: list[float] = []
    targets: list[Callable[[], None]] = []
    writers: list[Callable[[str, str], bool]] = []

    class Stop:
        closed: bool = False

        def set(self) -> None:
            self.closed = True

        def is_set(self) -> bool:
            return self.closed

        def wait(self, delay: float) -> bool:
            waits.append(delay)
            if len(waits) == 1:
                clock.now = 0.5
                _ = writers[0]("content", "fresh content")
                clock.now = 10
                return False
            return True

    class Worker:
        def __init__(self, *, target: Callable[[], None], **_kwargs: object) -> None:
            targets.append(target)

        def start(self) -> None:
            pass

        def join(self, **_kwargs: object) -> None:
            pass

    monkeypatch.setattr(
        server,
        "threading",
        SimpleNamespace(**{**vars(threading), "Event": Stop, "Thread": Worker}),
    )
    monkeypatch.setattr(
        server, "time", SimpleNamespace(monotonic=clock, time=time.time)
    )
    monkeypatch.setattr(server, "KEEPALIVE_S", 10)
    handler = make_handler()

    def dispatch(
        _ctx: object, _keepalive: object, writer: Callable[[str, str], bool]
    ) -> dict[str, object]:
        writers.append(writer)
        targets[0]()
        return {"state": "done", "rc": 0, "events": [], "usage": {}}

    setattr(handler, "_dispatch", dispatch)
    setattr(handler, "_reserve_delivery", discard)
    setattr(handler, "_record_turn_outcome", Mock())
    serve_sse(handler, {"model": "test"})
    assert waits == [10, 0.5]


@pytest.mark.skipif(
    not Path(
        "/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness"
    ).exists(),
    reason="интеграция требует установленный Electron/DSH; вендор только читается",
)
def test_installed_pi_ai_parser_and_idle_watchdog() -> None:
    heartbeat = KeepaliveController.sse_data_chunk(model="bridge-probe")
    script = r"""
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root='/Applications/DeepSeek Harness.app/Contents/Resources/app.asar/dsh/node_modules/';
const {stream}=await import(pathToFileURL(root+'@earendil-works/pi-ai/dist/api/openai-completions.js'));
const {idleWatchdog}=await import(pathToFileURL(root+'@deepseek-ai/dsh-timeout/lib/index.js'));
const heartbeat=__HEARTBEAT__;
const parsed=JSON.parse(heartbeat.slice(6));
const terminal='data: '+JSON.stringify({...parsed,choices:[{index:0,delta:{},finish_reason:'stop'}]})+'\n\ndata: [DONE]\n\n';
const model={id:'bridge-probe',name:'Bridge probe',api:'openai-completions',provider:'openai',baseUrl:'https://probe.invalid/v1',reasoning:true,input:['text'],cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:4096,maxTokens:64};
const context={messages:[{role:'user',content:'probe',timestamp:Date.now()}]};
const controller=new AbortController(), timers=[], encoder=new TextEncoder();
const result=stream(model,context,{apiKey:'probe-only',maxRetries:0,signal:controller.signal,fetch:async()=>new Response(new ReadableStream({start(c){for(let i=1;i<=8;i++)timers.push(setTimeout(()=>c.enqueue(encoder.encode(heartbeat)),i*40));timers.push(setTimeout(()=>{c.enqueue(encoder.encode(terminal));c.close();},360));}}),{headers:{'content-type':'text/event-stream'}})});
async function* relevant(){for await(const e of result)if(['thinking_delta','done','error'].includes(e.type))yield e;}
const iterator=relevant(), watchdog=idleWatchdog(controller.signal,160,'LLM_STREAM_IDLE_TIMEOUT');
const started=Date.now();let seen=0,done=false;
try {
 while(true){const n=await watchdog.next(iterator);if(n.done)break;if(n.value.type==='thinking_delta'){assert.equal(n.value.delta,' ');seen++;}if(n.value.type==='done')done=true;if(n.value.type==='error')throw new Error('provider error');}
 const final=await result.result();
 const thinking=final.content.filter(c=>c.type==='thinking').map(c=>c.thinking).join('');
 const text=final.content.filter(c=>c.type==='text').map(c=>c.text).join('');
 assert.equal(seen,8);assert(done);assert(Date.now()-started>160);assert.equal(thinking,' '.repeat(8));assert.equal(text,'');
 console.log(JSON.stringify({heartbeats:seen,terminal:done,aborted:watchdog.signal.aborted,thinkingLength:thinking.length,textLength:text.length}));
} finally {watchdog[Symbol.dispose]();controller.abort();timers.forEach(clearTimeout);}
""".replace("__HEARTBEAT__", json.dumps(heartbeat))
    proc = subprocess.run(
        [
            "/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness",
            "--expose-internals",
            "--input-type=module",
        ],
        input=script,
        text=True,
        capture_output=True,
        timeout=20,
        env={**os.environ, "ELECTRON_RUN_AS_NODE": "1"},
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {
        "heartbeats": 8,
        "terminal": True,
        "aborted": False,
        "thinkingLength": 8,
        "textLength": 0,
    }


def sse_chunk(content: str | None, finish_reason: str | None = None) -> bytes:
    delta: Delta = {} if content is None else {"content": content}
    chunk: Chunk = {
        "id": "chatcmpl-sliding",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "m",
        "choices": [{"delta": delta, "finish_reason": finish_reason}],
    }
    return b"data: " + json.dumps(chunk).encode() + b"\n"


def paced_readline(chunks: int | None, interval_s: float) -> Callable[[int], bytes]:
    """Построчный upstream: полезный чанк каждые `interval_s`; `chunks=None` — бесконечно."""

    def lines() -> Generator[bytes, None, None]:
        sent = 0
        while chunks is None or sent < chunks:
            time.sleep(interval_s)
            sent += 1
            yield sse_chunk("x")
            yield b"\n"
        yield sse_chunk(None, "stop")
        yield b"\n"
        yield b"data: [DONE]\n"
        yield b"\n"
        while True:
            yield b""

    source = lines()

    def readline(_limit: int) -> bytes:
        return next(source)

    return readline


def test_passthrough_safety_limits_defaults_and_env() -> None:
    assert PassthroughLimits().safety_cap_s == 3600.0
    assert PassthroughLimits.from_env({}).safety_cap_s == 3600.0
    assert (
        PassthroughLimits.from_env({"BRIDGE_SAFETY_CAP_S": "90"}).safety_cap_s == 90.0
    )
    assert (
        PassthroughLimits.from_env({"BRIDGE_SAFETY_CAP_S": "-1"}).safety_cap_s == 3600.0
    )


def test_passthrough_sliding_activity_window_extends_stream() -> None:
    # Полезные чанки идут чаще idle_timeout_s, но суммарно дольше total_timeout_s.
    limits = PassthroughLimits(
        total_timeout_s=0.5,
        idle_timeout_s=0.3,
        safety_cap_s=30.0,
        heartbeat_interval_s=30.0,
        poll_interval_s=0.01,
    )
    written: list[bytes] = []
    started = time.monotonic()
    outcome = relay_sse(
        paced_readline(12, 0.1),
        written.append,
        tool_schemas=None,
        limits=limits,
    )
    elapsed = time.monotonic() - started
    assert elapsed > limits.total_timeout_s
    assert outcome.done and not outcome.incomplete
    assert sum(1 for frame in written if b'"content": "x"' in frame) == 12


def test_passthrough_safety_cap_terminates_infinite_stream() -> None:
    # Апстрим активен вечно: идле не срабатывает, обрывает только аварийный потолок.
    limits = PassthroughLimits(
        total_timeout_s=0.2,
        idle_timeout_s=30.0,
        safety_cap_s=0.6,
        heartbeat_interval_s=30.0,
        poll_interval_s=0.01,
    )
    written: list[bytes] = []
    outcome = StreamOutcome()
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="safety cap exceeded"):
        _ = relay_sse(
            paced_readline(None, 0.05),
            written.append,
            tool_schemas=None,
            limits=limits,
            state=outcome,
        )
    elapsed = time.monotonic() - started
    assert limits.safety_cap_s <= elapsed < limits.safety_cap_s + 1.0
    assert any(b'"content": "x"' in frame for frame in written)
    assert not outcome.done


def test_passthrough_idle_timeout_not_reset_by_own_heartbeat() -> None:
    # Тишина upstream: свои keepalive клиенту не продлевают окно неактивности.
    limits = PassthroughLimits(
        idle_timeout_s=0.3,
        safety_cap_s=30.0,
        heartbeat_interval_s=0.05,
        poll_interval_s=0.01,
    )
    written: list[bytes] = []
    stop = threading.Event()

    def silent(_limit: int) -> bytes:
        _ = stop.wait(30)
        return b""

    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError, match="idle timeout exceeded"):
            _ = relay_sse(silent, written.append, tool_schemas=None, limits=limits)
    finally:
        stop.set()
    assert time.monotonic() - started < 2.0
    assert b": keepalive\n\n" in written


def test_cap_terminates_real_group_term_then_kill(tmp_path: Path) -> None:
    from core.backend_adapter import TurnResult

    clock = Clock()
    manager = TurnSessionManager(
        state_root=tmp_path,
        clock=clock,
        safety_cap_s=5,
        finish_reserve_s=0,
        watchdog_interval_s=0.01,
        cancel_grace_s=0.05,
    )
    turn, _ = manager.create_or_attach_turn(
        model="test", backend="test", cwd=str(tmp_path), messages=[]
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready',flush=True); time.sleep(60)",
        ],
        start_new_session=True,
        stdout=subprocess.PIPE,
    )
    try:
        assert cast(io.BufferedReader, proc.stdout).readline() == b"ready\n"
        turn.bind_process(pgid=proc.pid)
        clock.now += 6

        def runner(_turn: object) -> TurnResult:
            return TurnResult(state="done", rc=proc.wait(timeout=3))

        worker = manager.spawn_detached_execution(turn, runner)
        assert turn.done_event.wait(5)
        worker.join(timeout=1)
        assert proc.returncode == -signal.SIGKILL
        assert turn.status == "TIMED_OUT_CAP"
        error = turn.buffer.error
        assert error is not None
        assert error["code"] == "timed_out_cap"
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            _ = proc.wait(timeout=2)


class TestUncertainCliTurn(RpcCase):
    """Реальный RPC-эмулятор не перезапускается после неоднозначного сбоя хода."""

    def test_failed_cli_turn_is_dispatched_once(self) -> None:
        import server

        last_ok = cast(list[float], getattr(server, "_last_ok"))
        last_ok[0] = time.monotonic()
        script = cast(
            Callable[[list[dict[str, object]]], None], getattr(self.hub, "script")
        )
        script(
            [
                {"steps": [{"op": "exit", "rc": 1}]},
                {"steps": [{"op": "text", "text": "must not be replayed"}]},
            ]
        )
        conv = cast(Callable[[str], object], getattr(self, "conv"))(
            "no-uncertain-replay"
        )
        ask = cast(Callable[[str], tuple[int, object]], getattr(conv, "ask"))
        status, _body = ask("one turn")
        assert status == 502
        assert self.hub.sent_texts() == ["one turn"]
        assert last_ok[0] == 0
