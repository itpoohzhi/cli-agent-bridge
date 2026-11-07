"""Поведенческие регрессии ADR-0021: дедлайны, replay и честные ошибки."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest

from adapters.passthrough_adapter import PassthroughLimits

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def agy(monkeypatch: pytest.MonkeyPatch) -> Any:
    return load_bridge("agy-bridge", monkeypatch)


@pytest.fixture
def zen(monkeypatch: pytest.MonkeyPatch) -> Any:
    return load_bridge("opencode-zen-bridge", monkeypatch)


def load_bridge(name: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    spec = importlib.util.spec_from_file_location(
        "speedup_" + name.replace("-", "_"), ROOT / "bridges" / name / "server.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_log", lambda *_args: None)
    return module


def test_passthrough_deadline_env() -> None:
    limits = PassthroughLimits.from_env(
        {
            "BRIDGE_CONNECT_TIMEOUT_S": "2",
            "BRIDGE_IDLE_TIMEOUT_S": "3",
            "BRIDGE_TOTAL_TIMEOUT_S": "4",
            "BRIDGE_SSE_HEARTBEAT_INTERVAL_S": "0.05",
        }
    )
    assert (
        limits.connect_timeout_s,
        limits.idle_timeout_s,
        limits.total_timeout_s,
        limits.heartbeat_interval_s,
    ) == (2, 3, 4, 0.05)
    defaults = PassthroughLimits.from_env({})
    # Note: DEFAULT_IDLE_TIMEOUT_S = 300.0 on HEAD in adapters/passthrough_adapter.py:92 (commit 0215805227)
    assert (
        defaults.connect_timeout_s,
        defaults.idle_timeout_s,
        defaults.total_timeout_s,
        defaults.heartbeat_interval_s,
    ) == (10, 300, 420, 12)


@pytest.mark.parametrize(
    "req,mode",
    [
        ({}, "ask"),
        ({"tools": []}, "ask"),
        ({"tools": [{}]}, "agent"),
        ({"functions": [{}]}, "agent"),
        ({"agent_tools": True}, "agent"),
        ({"agent_tools": False}, "ask"),
    ],
)
def test_agy_mode(agy: Any, req: dict, mode: str) -> None:
    assert agy.resolve_agy_mode(req) == mode


def test_registry_attach_replay_and_conflict(agy: Any) -> None:
    registry = agy.JobRegistry()
    job, owner = registry.attach("same", "m", "prompt")
    assert owner
    job2, owner2 = registry.attach("same", "m", "prompt")
    assert job2 is job and not owner2
    assert registry.publish(job, "text", "one")
    assert registry.publish(job, "text", "two")
    registry.finish(job, {"state": "done", "text": "onetwo", "rc": 0})
    assert registry.read(job, 0, 0.01)[0] == [("text", "one"), ("text", "two")]
    with pytest.raises(agy.JobConflict):
        registry.attach("same", "m", "different")
    with pytest.raises(agy.JobConflict):
        registry.attach("same", "other", "prompt")
    registry.detach(job)
    registry.detach(job2)


def test_registry_capacity(agy: Any) -> None:
    registry = agy.JobRegistry(
        max_buffer_bytes=128, max_entries=1, ttl_s=0.03, orphan_max=0
    )
    job, _ = registry.attach("overflow", "m", "p")
    assert not registry.publish(job, "text", "x" * 129)
    assert job.cancelled.is_set()
    assert registry.read(job, 0, 0)[1]["state"] == "buffer_overflow"
    registry.finish(job, {"state": "client_gone"})
    registry.detach(job)
    orphan, _ = registry.attach("orphan", "m", "p")
    cancelled = threading.Event()
    registry.bind_cancel(orphan, cancelled.set)
    registry.detach(orphan)
    assert cancelled.is_set()
    assert orphan.cancelled.is_set()
    registry.finish(orphan, {"state": "client_gone"})
    new, _ = registry.attach("new", "m", "p")
    registry.finish(new, {"state": "done"})
    assert "overflow" not in registry.jobs
    time.sleep(0.04)
    replacement, owner = registry.attach("new", "m", "p")
    assert owner and replacement is not new


def test_zen_byte_timeout_selection(zen: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ZEN_LARGE_PROMPT_BYTES", "8")
    monkeypatch.setenv("BRIDGE_ZEN_TIMEOUT_S", "0.1")
    assert zen._zen_execution_timeout("deepseek-v4.1-flash-free", "я" * 5) == 0.1
    assert (
        zen._zen_execution_timeout("deepseek-v4.1-flash-free", "я" * 4) == zen.TIMEOUT_S
    )
    assert zen._zen_execution_timeout("unrelated-free", "x" * 100) == zen.TIMEOUT_S
    monkeypatch.setenv("BRIDGE_ZEN_TIMEOUT_MODELS", "explicit-model")
    assert zen._zen_execution_timeout("explicit-model", "x" * 9) == 0.1


def test_zen_split_timeouts(zen: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "BRIDGE_ZEN_TTFT_TIMEOUT_S",
        "BRIDGE_ZEN_TIMEOUT_S",
        "BRIDGE_ZEN_IDLE_TIMEOUT_S",
        "BRIDGE_ZEN_TOTAL_TIMEOUT_S",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BRIDGE_ZEN_LARGE_PROMPT_BYTES", "8")
    model, big = "deepseek-v4.1-flash-free", "x" * 9
    assert zen._zen_ttft_timeout(model, big) == 25.0
    assert zen._zen_idle_timeout(model, big) == 15.0
    assert zen._zen_total_timeout(model, big) == 180.0
    # Нецелевой запрос сохраняет прежний единый дедлайн.
    assert zen._zen_ttft_timeout("unrelated-free", big) == zen.TIMEOUT_S
    assert zen._zen_idle_timeout("unrelated-free", big) == zen.TIMEOUT_S
    assert zen._zen_total_timeout("unrelated-free", big) == zen.TIMEOUT_S
    # Старое имя переменной остаётся fallback для TTFT, новое имеет приоритет.
    monkeypatch.setenv("BRIDGE_ZEN_TIMEOUT_S", "7")
    assert zen._zen_ttft_timeout(model, big) == 7.0
    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "3")
    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "2")
    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "60")
    assert zen._zen_ttft_timeout(model, big) == 3.0
    assert zen._zen_idle_timeout(model, big) == 2.0
    assert zen._zen_total_timeout(model, big) == 60.0
    assert zen._zen_execution_timeout(model, big) == 3.0
    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "bad")
    assert zen._zen_idle_timeout(model, big) == 15.0
    attempts = zen._RequestAttempts(zen._Resilience(), time.monotonic() + 1)
    assert attempts.t0 <= time.monotonic()


def test_zen_short_content_and_pong(zen: Any) -> None:
    assert zen._zen_short_response("x" * 100, "short", [])
    assert not zen._zen_short_response("ping", "PONG", [])
    assert not zen._zen_short_response(
        "x" * 100, "", [{"function": {"name": "tool", "arguments": "{}"}}]
    )
    assert not zen._zen_short_response("x" * 100, "я" * 16, [])


def test_preflight_concrete_models_only() -> None:
    import server

    text = """| Модель / транспорт | Статус | Причина |
|---|---|---|
| `muse-wonder-full-1.0` / `muse` (и все слоты `muse-*`) | `LIMIT BLOCKED` (`quota_window`) | quota |
| `available` | OK | prose mentions BANNED |
| Группа | Что | Статус |
|---|---|---|
| Транспорты | `cursor-agent`, все модели | BANNED |
| Модели | `blocked-id` | BANNED |
"""
    assert server._parse_blocked_models(text) == frozenset(
        {"muse-wonder-full-1.0", "blocked-id"}
    )


def test_model_notes_msk_expiration() -> None:
    from datetime import datetime, timezone
    import server

    text = """| Модель | Статус |
|---|---|
| `claude-sonnet-5-5` | LIMIT BLOCKED (до 2030-01-01 12:00 MSK) |
"""
    reset = datetime(2030, 1, 1, 9, tzinfo=timezone.utc).timestamp()
    assert server._parse_blocked_models(text, reset - 1) == frozenset(
        {"claude-sonnet-5-5"}
    )
    assert server._parse_blocked_models(text, reset) == frozenset({"claude-sonnet-5-5"})
    assert not server._parse_blocked_models(text, reset + 1)


def test_model_notes_msk_expiration_without_parentheses() -> None:
    from datetime import datetime, timezone
    import server

    text = """| Модель | Статус |
|---|---|
| `claude-sonnet-5-5` | LIMIT BLOCKED до 2030-01-01 12:00 MSK |
"""
    reset = datetime(2030, 1, 1, 9, tzinfo=timezone.utc).timestamp()
    assert server._parse_blocked_models(text, reset - 1) == frozenset(
        {"claude-sonnet-5-5"}
    )
    assert server._parse_blocked_models(text, reset) == frozenset({"claude-sonnet-5-5"})
    assert not server._parse_blocked_models(text, reset + 1)


def test_client_gone_safely_handles_none_and_socketless_objects() -> None:
    import server

    assert server._client_gone(None) is False

    class DummyObj:
        pass

    assert server._client_gone(cast(Any, DummyObj())) is False


def test_passthrough_upstream_model_rewriting(monkeypatch, tmp_path) -> None:
    from core.model_penalty import ModelPenaltyTracker
    from email.message import Message
    import server
    monkeypatch.setattr(server, "_PENALTY_TRACKER", ModelPenaltyTracker(tmp_path / "penalties.json"))
    captured = []

    def _fake_passthrough(self, a, raw, req, model_id, _hub_auth_ok=False):
        captured.append((raw, req, model_id))

    monkeypatch.setattr(server.Handler, "_serve_passthrough", _fake_passthrough)
    monkeypatch.setattr(server, "_auth_ok", lambda _h: True)
    monkeypatch.setattr(server, "_enforce_forward_kill_switch", lambda: None)

    # Модель с upstream_model
    model_cfg = {
        "id": "gpt-6.1-sol",
        "backend": "codex-lb",
        "upstream_model": "gpt-5.6-sol",
        "default_effort": "high",
        "efforts": ["high"],
    }
    monkeypatch.setitem(server.FLEET["models"], "gpt-6.1-sol", model_cfg)
    adapter = object.__new__(server.PassthroughAdapter)
    monkeypatch.setattr(server.BACKENDS, "get", lambda bid: adapter if bid == "codex-lb" else None)

    instance = cast(Any, object.__new__(server.Handler))
    instance.headers = Message()
    body = json.dumps({"model": "gpt-6.1-sol", "messages": [{"role": "user", "content": "hi"}]}).encode()
    instance.headers["Content-Length"] = str(len(body))
    instance.rfile = io.BytesIO(body)
    instance.wfile = io.BytesIO()
    instance.path = "/v1/chat/completions"
    instance.client_address = ("127.0.0.1", 1)
    instance.statuses = []
    instance.send_response = instance.statuses.append
    instance.send_header = lambda *_a: None
    instance.end_headers = lambda: None

    instance.do_POST()
    assert len(captured) == 1
    raw, req, mid = captured[0]
    assert mid == "gpt-6.1-sol"
    assert req["model"] == "gpt-5.6-sol"
    assert json.loads(raw)["model"] == "gpt-5.6-sol"


def test_quota_cache_ttl_and_effort_suffix(tmp_path, monkeypatch) -> None:
    import server

    clock = [1000.0]
    monkeypatch.setattr(server.time, "time", lambda: clock[0])
    path = tmp_path / "quota.json"
    cache = server.QuotaCircuitBreakerCache(path)
    monkeypatch.setattr(server, "_QUOTA_CB_CACHE", cache)
    cache.record_429("claude-sonnet-5-5", ttl_s=30)
    assert cache.is_blocked("claude-sonnet-5-5-high")
    assert server.QuotaCircuitBreakerCache(path).is_blocked("claude-sonnet-5-5")
    notes = server.ModelNotesFilter(tmp_path / "missing")
    assert notes.is_blocked("claude-sonnet-5-5-high")
    clock[0] = 1031.0
    assert not cache.is_blocked("claude-sonnet-5-5-high")
    notes.blocked = frozenset({"claude-sonnet-5-5"})
    notes.expires_at = server.time.monotonic() + 60
    assert notes.is_blocked("claude-sonnet-5-5-high")
    assert not notes.is_blocked("unrelated")


class Sink:
    def __init__(self, disconnect: bool = False) -> None:
        self.status = 0
        self.chunks: list[bytes] = []
        self.disconnect = disconnect
        self.written = threading.Event()

    def start(self, status: int, _headers: list) -> None:
        self.status = status

    def write(self, data: bytes) -> None:
        from adapters.passthrough_adapter import ClientGone

        if self.disconnect:
            raise ClientGone()
        self.chunks.append(data)
        self.written.set()

    def client_gone(self) -> bool:
        return False


@pytest.fixture
def upstream() -> Any:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from contextlib import contextmanager

    @contextmanager
    def serve(callback: Any) -> Any:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                try:
                    callback(self)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def log_message(self, format: str, *args: Any) -> None:
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(
            target=httpd.serve_forever, kwargs={"poll_interval": 0.01}
        )
        thread.start()
        try:
            yield httpd.server_port
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(1)

    return serve


def passthrough(port: int, **limits: Any) -> Any:
    from adapters.passthrough_adapter import PassthroughAdapter

    return PassthroughAdapter(
        "test",
        {"base_url": f"http://127.0.0.1:{port}/v1", "max_concurrent": 1},
        dict,
        limits=PassthroughLimits(
            poll_interval_s=0.005, reader_join_timeout_s=0.02, **limits
        ),
    )


def invoke(adapter: Any, sink: Any) -> None:
    adapter.handle(
        path="/v1/chat/completions",
        raw_body=b"{}",
        request={"stream": True},
        headers={},
        sink=sink,
    )


@pytest.mark.parametrize("empty_role_first", [False, True])
def test_slow_ttft_gets_heartbeats_before_content(
    upstream: Any, empty_role_first: bool
) -> None:
    def serve(handler: Any) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        if empty_role_first:
            handler.wfile.write(
                b'data: {"choices":[{"delta":{"role":"assistant","content":""},"finish_reason":null}]}\n\n'
            )
            handler.wfile.flush()
        time.sleep(0.15)
        handler.wfile.write(
            b'data: {"choices":[{"delta":{"reasoning_content":"thinking"},"finish_reason":null}]}\n\n'
        )
        handler.wfile.write(
            b'data: {"choices":[{"delta":{"content":"answer"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
        )
        handler.wfile.flush()

    with upstream(serve) as port:
        sink = Sink()
        adapter = passthrough(
            port, idle_timeout_s=0.04, total_timeout_s=0.5, heartbeat_interval_s=0.025
        )
        invoke(adapter, sink)
        body = b"".join(sink.chunks)
        assert sink.status == 200 and body.endswith(b"data: [DONE]\n\n")
        assert body.count(b": keepalive\n\n") >= 3
        assert body.index(b": keepalive") < body.index(b"thinking")
        assert adapter.active_count() == 0


@pytest.mark.parametrize("first_chunk", [False, True])
def test_idle_and_total_do_not_count_heartbeat_as_progress(
    upstream: Any, first_chunk: bool
) -> None:
    def serve(handler: Any) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        if first_chunk:
            handler.wfile.write(
                b'data: {"choices":[{"delta":{"content":"x"},"finish_reason":null}]}\n\n'
            )
            handler.wfile.flush()
        for _ in range(30):
            handler.wfile.write(b": upstream-heartbeat\n\n")
            handler.wfile.flush()
            time.sleep(0.01)

    with upstream(serve) as port:
        adapter = passthrough(
            port, idle_timeout_s=0.05, total_timeout_s=0.14, heartbeat_interval_s=0.02
        )
        sink = Sink()
        started = time.monotonic()
        invoke(adapter, sink)
        elapsed = time.monotonic() - started
        assert elapsed < 0.28
        if not first_chunk:
            assert elapsed >= 0.12
        assert b"upstream_stream_error" in b"".join(sink.chunks)
        assert adapter.active_count() == 0


def test_disconnect_closes_upstream_and_frees_slot(upstream: Any) -> None:
    closed = threading.Event()

    def serve(handler: Any) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        import select

        ready, _, _ = select.select([handler.connection], [], [], 1)
        if ready and handler.connection.recv(1) == b"":
            closed.set()

    with upstream(serve) as port:
        adapter = passthrough(
            port, idle_timeout_s=0.03, total_timeout_s=0.5, heartbeat_interval_s=0.02
        )
        invoke(adapter, Sink(disconnect=True))
        assert closed.wait(0.5)
        assert adapter.active_count() == 0
        assert adapter._slots.acquire(blocking=False)
        adapter._slots.release()


def test_total_deadline_before_headers_is_504(upstream: Any) -> None:
    def serve(handler: Any) -> None:
        time.sleep(0.2)
        handler.send_response(200)
        handler.end_headers()

    with upstream(serve) as port:
        adapter = passthrough(port, total_timeout_s=0.06)
        sink = Sink()
        invoke(adapter, sink)
        assert sink.status == 504
        assert adapter.active_count() == 0


def test_registry_concurrent_attach_and_lru(agy: Any) -> None:
    registry = agy.JobRegistry(max_entries=2)
    barrier = threading.Barrier(8)
    owners: list[bool] = []
    jobs: list[Any] = []

    def attach() -> None:
        barrier.wait()
        job, owner = registry.attach("same", "m", "p")
        jobs.append(job)
        owners.append(owner)

    threads = [threading.Thread(target=attach) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(1)
    assert len(jobs) == 8 and sum(owners) == 1
    assert len({id(job) for job in jobs}) == 1
    registry.finish(jobs[0], {"state": "done"})
    second, _ = registry.attach("second", "m", "p")
    registry.finish(second, {"state": "done"})
    registry.attach("same", "m", "p")
    third, _ = registry.attach("third", "m", "p")
    registry.finish(third, {"state": "done"})
    assert (
        "same" in registry.jobs
        and "third" in registry.jobs
        and "second" not in registry.jobs
    )


def test_orphan_limit_attach_restores_capacity_and_cancel_outside_lock(
    agy: Any,
) -> None:
    registry = agy.JobRegistry(orphan_max=1)
    first, _ = registry.attach("first", "m", "p")
    registry.detach(first)
    assert registry.orphans == 1
    first2, _ = registry.attach("first", "m", "p")
    assert first2 is first and registry.orphans == 0
    registry.detach(first)
    second, _ = registry.attach("second", "m", "p")
    acquired: list[bool] = []

    def cancel() -> None:
        ok = registry.condition.acquire(blocking=False)
        acquired.append(ok)
        if ok:
            registry.condition.release()

    registry.bind_cancel(second, cancel)
    registry.detach(second)
    assert acquired == [True]
    assert second.cancelled.is_set()
    registry.finish(first, {"state": "done"})
    assert registry.orphans == 0


def test_agy_http_reconnect_and_conflict(
    agy: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import http.client

    monkeypatch.setattr(agy, "AUTH_KEY", "test")
    monkeypatch.setattr(agy, "_JOB_REGISTRY", agy.JobRegistry())
    entered = threading.Event()
    finish = threading.Event()
    calls: list[dict] = []

    def execute(
        _self: Any,
        ctx: dict,
        on_text: Any,
        _tool: Any,
        _reasoning: Any,
        _keepalive: Any,
    ) -> dict:
        calls.append(ctx)
        entered.set()
        finish.wait(2)
        on_text("response")
        return {"state": "done", "text": "response", "rc": 0, "usage": {}}

    monkeypatch.setattr(agy.Handler, "_run_once_impl", execute)
    monkeypatch.setenv("BRIDGE_SSE_HEARTBEAT_INTERVAL_S", ".02")
    httpd = agy.Server(("127.0.0.1", 0), agy.Handler)
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}
    )
    thread.start()
    conns: list[Any] = []

    def request(prompt: str = "hello", stream: bool = True) -> Any:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=2)
        conns.append(conn)
        body = {
            "model": agy.MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }
        conn.request(
            "POST",
            "/v1/chat/completions",
            json.dumps(body),
            {"Authorization": "Bearer test", "X-Idempotency-Key": "step"},
        )
        return conn

    try:
        conn = request()
        response = conn.getresponse()
        assert response.status == 200 and entered.wait(1)
        conn.close()
        conflict = request("changed").getresponse()
        assert conflict.status == 409
        conflict.read()
        conn2 = request()
        finish.set()
        response2 = conn2.getresponse()
        assert response2.status == 200
        assert b"response" in response2.read()
        replay = request(stream=False).getresponse()
        assert replay.status == 200
        assert (
            json.loads(replay.read())["choices"][0]["message"]["content"] == "response"
        )
        assert len(calls) == 1
    finally:
        finish.set()
        for conn in conns:
            conn.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join(1)


def zen_handler(zen: Any) -> tuple[Any, list[int]]:
    handler = object.__new__(zen.Handler)
    handler.wfile = io.BytesIO()
    handler.headers = {}
    statuses: list[int] = []
    handler.send_response = statuses.append
    handler.send_header = lambda *_args: None
    handler.end_headers = lambda: None
    return handler, statuses


def test_zen_timeout_error_before_and_after_headers(
    zen: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRIDGE_ZEN_LARGE_PROMPT_BYTES", "8")
    handler, statuses = zen_handler(zen)
    handler._set_zen_policy("deepseek-v4.1-flash-free", "x" * 9)
    handler._exit()["exit_reason"] = "timeout"
    handler._send(502, {"error": {"message": "old timeout"}})
    assert statuses == [504]
    assert json.loads(handler.wfile.getvalue()) == zen._zen_error(504)
    handler.wfile = io.BytesIO()
    handler._sse_error({"error": {"message": "old timeout"}})
    frames = handler.wfile.getvalue()
    assert frames.count(b"data: [DONE]") == 1
    assert json.loads(frames.split(b"\n\n")[0][6:]) == zen._zen_error(504)
    assert statuses == [504] and handler.close_connection


@pytest.mark.parametrize(
    "content,calls,expected",
    [
        ("short", [], 502),
        ("я" * 16, [], 200),
        ("", [{"function": {"name": "tool", "arguments": "{}"}}], 200),
    ],
)
def test_zen_json_short_filter(
    zen: Any, content: str, calls: list, expected: int
) -> None:
    handler, statuses = zen_handler(zen)
    handler._set_zen_policy("other", "x" * 100)
    handler._send(
        200, {"choices": [{"message": {"content": content, "tool_calls": calls}}]}
    )
    assert statuses == [expected]
    if expected == 502:
        assert json.loads(handler.wfile.getvalue()) == zen._zen_error(502)


def test_zen_stream_short_filter_and_tool_only(zen: Any) -> None:
    def frame(delta: dict, finish: str | None = None) -> bytes:
        return (
            "data: "
            + json.dumps({"choices": [{"delta": delta, "finish_reason": finish}]})
            + "\n\n"
        ).encode()

    raw = io.BytesIO()
    filtered = zen._ZenSseFilter(raw, "x" * 100, False)
    filtered.write(frame({"content": "short"}))
    filtered.write(frame({}, "stop"))
    filtered.write(b"data: [DONE]\n\n")
    assert b"Empty upstream response" in raw.getvalue()
    assert b'"finish_reason": "stop"' not in raw.getvalue()
    assert raw.getvalue().count(b"data: [DONE]") == 1
    raw = io.BytesIO()
    filtered = zen._ZenSseFilter(raw, "x" * 100, False)
    filtered.write(
        frame({"tool_calls": [{"function": {"name": "tool", "arguments": "{}"}}]})
    )
    filtered.write(frame({}, "tool_calls"))
    filtered.write(b"data: [DONE]\n\n")
    assert b"Empty upstream" not in raw.getvalue()


def test_preflight_ttl_failopen_and_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import server

    notes = tmp_path / "model-notes.md"
    notes.write_text("| Модель | Статус |\n|---|---|\n| `blocked` | TEMP OFF |\n")
    cache = server.ModelNotesFilter(notes, ttl_s=0.04)
    assert cache.is_blocked("blocked")
    notes.write_text("unstructured prose BANNED blocked")
    assert cache.is_blocked("blocked")
    time.sleep(0.05)
    assert not cache.is_blocked("blocked")
    notes.unlink()
    cache.expires_at = 0
    assert not cache.is_blocked("blocked")
    started = time.monotonic()
    slow_read_done = threading.Event()

    def slow_stat(_self: Any) -> Any:
        slow_read_done.wait(0.3)
        raise OSError("unavailable")

    monkeypatch.setattr(Path, "stat", slow_stat)
    cache.expires_at = 0
    try:
        assert not cache.is_blocked("blocked")
        assert time.monotonic() - started < 0.05
    finally:
        slow_read_done.set()


def test_gateway_preflight_bypass_and_idempotency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from email.message import Message
    import server

    captured: list[tuple[bytes, dict]] = []
    hub_auth_ok: list[bool] = []
    checks: list[str] = []

    class Filter:
        def is_blocked(self, model: str) -> bool:
            checks.append(model)
            return True

    monkeypatch.setattr(server, "_MODEL_NOTES_FILTER", Filter())
    monkeypatch.setattr(server, "_auth_ok", lambda _h: True)
    monkeypatch.setattr(server, "_enforce_forward_kill_switch", lambda: None)

    def _fake_passthrough(self, a, raw, req, model, _hub_auth_ok=False):
        hub_auth_ok.append(_hub_auth_ok)
        captured.append((raw, req))

    monkeypatch.setattr(server.Handler, "_serve_passthrough", _fake_passthrough)
    model = "gpt-6.1-terra"

    def handler(bypass: bool) -> Any:
        instance: Any = object.__new__(server.Handler)
        instance.headers = Message()
        body = json.dumps(
            {"model": model, "messages": [{"role": "user", "content": "test"}]}
        ).encode()
        instance.headers["Content-Length"] = str(len(body))
        instance.headers["X-Idempotency-Key"] = "idempotent-step"
        if bypass:
            instance.headers["X-Bypass-Model-Filter"] = "1"
        instance.rfile = io.BytesIO(body)
        instance.wfile = io.BytesIO()
        instance.path = "/v1/chat/completions"
        instance.client_address = ("127.0.0.1", 1)
        instance.statuses = []
        instance.send_response = instance.statuses.append
        instance.send_header = lambda *_args: None
        instance.end_headers = lambda: None
        return instance

    first = handler(False)
    first.do_POST()
    assert first.statuses == [503]
    assert json.loads(first.wfile.getvalue())["error"]["type"] == "model_limit_blocked"
    third = handler(True)
    third.do_POST()
    assert len(captured) == 1
    assert hub_auth_ok == [True]
    assert captured[0][1]["step_job_id"] == "idempotent-step"
    assert json.loads(captured[0][0])["step_job_id"] == "idempotent-step"
    second = handler(True)

    # Маршрут останавливаем сразу после preflight, не вызывая настоящий CLI.
    def resolve(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("routing reached")

    monkeypatch.setattr(server, "_resolve_model_alias", resolve)
    with pytest.raises(RuntimeError, match="routing reached"):
        second.do_POST()
    assert len(checks) == 1
    # JSON-перевод проверяем до маршрутизации перехватом alias на входе.
    assert second.rfile.tell() > 0


def test_registry_overflow_keeps_running_orphan_reserved_until_cleanup(
    agy: Any,
) -> None:
    registry = agy.JobRegistry(max_buffer_bytes=100, orphan_max=1)
    job, _ = registry.attach("one", "m", "p")
    registry.detach(job)
    assert registry.orphans == 1
    assert not registry.publish(job, "text", "x" * 101)
    # Terminal replay доступен сразу, но работа ещё не покинула finally.
    assert registry.orphans == 1
    retry, owner = registry.attach("one", "m", "p")
    assert retry is job and not owner
    registry.detach(retry)
    registry.finish(job, {"state": "client_gone"})
    assert registry.orphans == 0


@pytest.mark.parametrize("stream", [False, True])
def test_zen_real_fake_child_timeout_is_cleaned(
    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stream: bool
) -> None:
    import http.client

    fake = tmp_path / "fake-opencode"
    fake.write_text("#!" + sys.executable + "\nimport time\ntime.sleep(5)\n")
    fake.chmod(0o700)
    monkeypatch.setenv("BRIDGE_ZEN_LARGE_PROMPT_BYTES", "8")
    monkeypatch.setenv("BRIDGE_ZEN_TIMEOUT_S", ".12")
    monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_TRANSPORT", "run")
    monkeypatch.setattr(zen, "AUTH_KEY", "test")
    monkeypatch.setattr(
        zen,
        "ALLOWED_MODELS",
        {"deepseek-v4.1-flash-free": {"context_length": 10000, "max_output": 1000}},
    )
    monkeypatch.setattr(zen, "_maybe_reload_catalog", lambda: None)
    monkeypatch.setattr(zen, "_resolve_launcher", lambda: str(fake))
    monkeypatch.setattr(zen, "DEFAULTWORKDIR", tmp_path)
    monkeypatch.setattr(zen, "FIRST_STATUS_DELAY_S", 100)
    monkeypatch.setattr(zen, "FAIL_RETRY_LIMIT", 0)
    monkeypatch.setattr(zen, "_run_env", lambda _model: {})
    procs: list[Any] = []
    spawn = zen._spawn_with_stdin

    def capture(*args: Any, **kwargs: Any) -> Any:
        proc = spawn(*args, **kwargs)
        procs.append(proc)
        return proc

    monkeypatch.setattr(zen, "_spawn_with_stdin", capture)
    httpd = zen.Server(("127.0.0.1", 0), zen.Handler)
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}
    )
    thread.start()
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=3)
    try:
        conn.request(
            "POST",
            "/v1/chat/completions",
            json.dumps(
                {
                    "model": "deepseek-v4.1-flash-free",
                    "messages": [{"role": "user", "content": "x" * 100}],
                    "stream": stream,
                }
            ),
            {"Authorization": "Bearer test"},
        )
        response = conn.getresponse()
        body = response.read()
        if stream:
            assert response.status == 200
            assert b"Gateway Timeout in zen-bridge" in body
            assert body.count(b"data: [DONE]") == 1
        else:
            assert response.status == 504
            assert json.loads(body) == zen._zen_error(504)
        assert procs and all(proc.poll() is not None for proc in procs)
    finally:
        conn.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join(1)
        for proc in procs:
            if proc.poll() is None:
                zen._stop_proc(proc)


def test_agy_detach_at_zero_orphan_capacity_kills_child_and_releases_bulkhead(
    agy: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import http.client
    import subprocess

    fake = tmp_path / "fake-agy"
    argv_log = tmp_path / "argv.json"
    fake.write_text(
        "#!"
        + sys.executable
        + "\nimport sys,time,json\nopen("
        + repr(str(argv_log))
        + ', "w").write(json.dumps(sys.argv))\nprint(json.dumps({"event":"step_update","step_update":{"step_type":"agent_response","text_delta":"ready"}}), flush=True)\ntime.sleep(30)\n'
    )
    fake.chmod(0o700)
    monkeypatch.setattr(agy, "AUTH_KEY", "test")
    monkeypatch.setattr(agy, "_JOB_REGISTRY", agy.JobRegistry(orphan_max=0))
    monkeypatch.setattr(agy, "_launcher", lambda: str(fake))
    monkeypatch.setattr(agy, "_launch_env", lambda: {})
    monkeypatch.setattr(agy, "WORKSPACE", tmp_path)
    monkeypatch.setattr(agy, "_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr(agy, "_is_watchdog_enabled", lambda: False)
    monkeypatch.setattr(
        agy,
        "_new_flag",
        lambda name, default=False: name == "AGY_BRIDGE_STREAM_RESILIENCE_ENABLED",
    )
    monkeypatch.setenv("BRIDGE_SSE_HEARTBEAT_INTERVAL_S", ".02")
    child_spawned = threading.Event()
    procs: list[Any] = []
    original_popen = subprocess.Popen

    def spawn(args: list, *pos: Any, **kwargs: Any) -> Any:
        proc = original_popen(args, *pos, **kwargs)
        if args[0] == str(fake):
            procs.append(proc)
            child_spawned.set()
        return proc

    monkeypatch.setattr(agy.subprocess, "Popen", spawn)
    httpd = agy.Server(("127.0.0.1", 0), agy.Handler)
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}
    )
    thread.start()
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=2)
    try:
        conn.request(
            "POST",
            "/v1/chat/completions",
            json.dumps(
                {
                    "model": agy.MODEL_ID,
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": True,
                }
            ),
            {"Authorization": "Bearer test", "X-Idempotency-Key": "detach"},
        )
        response = conn.getresponse()
        assert response.status == 200 and child_spawned.wait(1)
        lines: list[bytes] = []
        startup_deadline = time.monotonic() + 3
        while time.monotonic() < startup_deadline:
            line = response.readline()
            lines.append(line)
            if b"ready" in line or not line:
                break
        assert b"ready" in b"".join(lines)
        assert argv_log.exists()
        argv = json.loads(argv_log.read_text())
        assert argv[argv.index("--mode") + 1] in ("ask", "plan")
        response.close()
        conn.close()
        assert procs[0].wait(timeout=2) != 0
        job = agy._JOB_REGISTRY.jobs["detach"]
        with agy._JOB_REGISTRY.condition:
            assert agy._JOB_REGISTRY.condition.wait_for(
                lambda: not job.running, timeout=2
            )
        assert job.cancelled.is_set()
        assert agy._slots.acquire(blocking=False)
        agy._slots.release()
        assert len(procs) == 1
    finally:
        conn.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join(1)
        for proc in procs:
            if proc.poll() is None:
                agy._kill_group(proc)


def test_zen_probe_and_explicit_bypass_with_long_system(zen: Any) -> None:
    assert zen._zen_probe_request(
        {
            "messages": [
                {"role": "system", "content": "system " * 100},
                {"role": "user", "content": "Reply exactly PONG"},
            ]
        }
    )
    assert not zen._zen_probe_request(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "explain why PONG is returned by this long operation",
                }
            ]
        }
    )
    handler, statuses = zen_handler(zen)
    handler._zen_probe = True
    handler._set_zen_policy("other", "system " * 100 + "User: ping")
    handler._send(200, {"choices": [{"message": {"content": "PONG"}}]})
    assert statuses == [200]
    handler, statuses = zen_handler(zen)
    handler.headers["X-Bypass-Short-Filter"] = "1"
    handler._set_zen_policy("other", "x" * 100)
    handler._send(200, {"choices": [{"message": {"content": "short"}}]})
    assert statuses == [200]


def test_passthrough_total_budget_includes_admission_queue() -> None:
    adapter = passthrough(1, total_timeout_s=0.025)
    assert adapter._slots.acquire(blocking=False)
    try:
        sink = Sink()
        started = time.monotonic()
        invoke(adapter, sink)
        assert time.monotonic() - started < 0.15
        assert sink.status == 503
        assert adapter.active_count() == 0
    finally:
        adapter._slots.release()


def test_nonstream_total_deadline_cannot_become_partial_200(upstream: Any) -> None:
    def serve(handler: Any) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(b'{"choices":[')
        handler.wfile.flush()
        time.sleep(0.2)

    with upstream(serve) as port:
        adapter = passthrough(port, total_timeout_s=0.05)
        sink = Sink()
        invoke(adapter, sink)
        assert sink.status == 504
        assert b"choices" not in b"".join(sink.chunks)


def _zen_fake_stream_child(
    tmp_path: Path,
    chunks: int,
    gap_s: float,
    lead_s: float = 0.0,
    tool_s: float = 0.0,
) -> Path:
    """Фейковый `opencode run`: пауза lead_s, chunks text-событий с паузой gap_s, затем step_finish.

    tool_s > 0: после первого чанка идёт tool (running -> пауза tool_s -> completed) без токенов.
    """
    fake = tmp_path / "fake-opencode"
    tool = (
        "    if i == 0 and %r:\n" % tool_s
        + "        print(json.dumps({'type':'tool_use','part':{'tool':'bash','id':'c1','state':{'status':'running'}}}),flush=True)\n"
        + f"        time.sleep({tool_s})\n"
        + "        print(json.dumps({'type':'tool_use','part':{'tool':'bash','id':'c1','state':{'status':'completed'}}}),flush=True)\n"
    )
    fake.write_text(
        "#!"
        + sys.executable
        + "\nimport json,sys,time\n"
        + f"time.sleep({lead_s})\n"
        + f"for i in range({chunks}):\n"
        + "    print(json.dumps({'type':'text','part':{'text':'t%d ' % i}}),flush=True)\n"
        + tool
        + f"    time.sleep({gap_s})\n"
        + "print(json.dumps({'type':'step_finish','part':{'tokens':{}}}),flush=True)\n"
    )
    fake.chmod(0o700)
    return fake


def _zen_stream_request(
    zen: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake: Path,
    stream: bool = True,
) -> tuple[int, bytes, list[Any]]:
    import http.client

    monkeypatch.setenv("BRIDGE_ZEN_LARGE_PROMPT_BYTES", "8")
    monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_TRANSPORT", "run")
    monkeypatch.setattr(zen, "AUTH_KEY", "test")
    monkeypatch.setattr(
        zen,
        "ALLOWED_MODELS",
        {"deepseek-v4.1-flash-free": {"context_length": 10000, "max_output": 1000}},
    )
    monkeypatch.setattr(zen, "_maybe_reload_catalog", lambda: None)
    monkeypatch.setattr(zen, "_resolve_launcher", lambda: str(fake))
    monkeypatch.setattr(zen, "DEFAULTWORKDIR", tmp_path)
    monkeypatch.setattr(zen, "FIRST_STATUS_DELAY_S", 100)
    monkeypatch.setattr(zen, "FAIL_RETRY_LIMIT", 0)
    monkeypatch.setattr(zen, "_run_env", lambda _model: {})
    procs: list[Any] = []
    spawn = zen._spawn_with_stdin

    def capture(*args: Any, **kwargs: Any) -> Any:
        proc = spawn(*args, **kwargs)
        procs.append(proc)
        return proc

    monkeypatch.setattr(zen, "_spawn_with_stdin", capture)
    httpd = zen.Server(("127.0.0.1", 0), zen.Handler)
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}
    )
    thread.start()
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
    try:
        conn.request(
            "POST",
            "/v1/chat/completions",
            json.dumps(
                {
                    "model": "deepseek-v4.1-flash-free",
                    "messages": [{"role": "user", "content": "x" * 100}],
                    "stream": stream,
                }
            ),
            {"Authorization": "Bearer test", "X-Bypass-Short-Filter": "1"},
        )
        response = conn.getresponse()
        return response.status, response.read(), procs
    finally:
        conn.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join(1)
        for proc in procs:
            if proc.poll() is None:
                zen._stop_proc(proc)


def test_zen_stream_continues_past_ttft(
    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Поток, начавшийся в пределах TTFT, живёт дольше TTFT, пока чанки идут чаще Idle."""
    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "1.0")
    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "0.6")
    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "10")
    fake = _zen_fake_stream_child(tmp_path, chunks=30, gap_s=0.05)
    started = time.monotonic()
    status, body, procs = _zen_stream_request(zen, monkeypatch, tmp_path, fake)
    elapsed = time.monotonic() - started
    assert status == 200
    assert elapsed > 1.0
    assert b"Gateway Timeout in zen-bridge" not in body
    for i in range(30):
        assert f"t{i} ".encode() in body
    assert body.count(b"data: [DONE]") == 1
    assert procs and all(proc.poll() is not None for proc in procs)


def test_zen_stream_idle_timeout_after_first_token(
    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """После первого токена тишина дольше Idle обрывает поток и чистит дочерний процесс."""
    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "2")
    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "0.2")
    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
    fake = _zen_fake_stream_child(tmp_path, chunks=1, gap_s=10)
    started = time.monotonic()
    status, body, procs = _zen_stream_request(zen, monkeypatch, tmp_path, fake)
    assert time.monotonic() - started < 5
    assert status == 200
    assert b"t0 " in body
    # Idle-обрыв — честная terminal SSE-ошибка, а не успешное завершение потока:
    # [DONE] только как рамка после error-кадра, без finish_reason=stop.
    assert b"Gateway Timeout in zen-bridge" in body
    assert b"timeout_error" in body
    assert body.index(b"timeout_error") < body.index(b"data: [DONE]")
    assert b'"finish_reason": "stop"' not in body
    assert procs and all(proc.poll() is not None for proc in procs)


@pytest.mark.parametrize("stream", [True, False])
def test_zen_stream_ttft_timeout_returns_504(
    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stream: bool
) -> None:
    """Провайдер завис (0 токенов за TTFT): честный 504 / terminal SSE error с timeout_error."""
    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "0.3")
    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "5")
    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
    fake = _zen_fake_stream_child(tmp_path, chunks=1, gap_s=0, lead_s=10)
    started = time.monotonic()
    status, body, procs = _zen_stream_request(
        zen, monkeypatch, tmp_path, fake, stream=stream
    )
    assert time.monotonic() - started < 5
    assert b"timeout_error" in body
    assert b"Gateway Timeout in zen-bridge" in body
    assert b"t0 " not in body
    assert b'"finish_reason": "stop"' not in body
    if stream:
        assert body.count(b"data: [DONE]") == 1
        assert body.index(b"timeout_error") < body.index(b"data: [DONE]")
    else:
        assert status == 504, body
    assert procs and all(proc.poll() is not None for proc in procs)


def test_zen_idle_and_total_independent_of_ttft(
    zen: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FU-001: оператор поднимает TTFT выше TIMEOUT_S, Idle/Total для целевой модели сохраняются."""
    monkeypatch.setenv("BRIDGE_ZEN_LARGE_PROMPT_BYTES", "8")
    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", str(zen.TIMEOUT_S * 10))
    monkeypatch.delenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", raising=False)
    monkeypatch.delenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", raising=False)
    model, big = "deepseek-v4.1-flash-free", "x" * 9
    assert zen._zen_ttft_timeout(model, big) == zen.TIMEOUT_S
    assert zen._zen_idle_timeout(model, big) == min(zen.TIMEOUT_S, 15.0)
    assert zen._zen_total_timeout(model, big) == min(zen.TIMEOUT_S, 180.0)
    assert zen._zen_targeted(model, big)
    assert not zen._zen_targeted("unrelated-free", big)
    assert not zen._zen_targeted(model, "x")


def test_attempts_t0_is_lazy(zen: Any) -> None:
    """FU-002: при наличии t0 deadline и env не читаются; заглушка без t0 выводится из deadline."""

    class WithT0:
        t0 = 12.5

        @property
        def deadline(self) -> float:
            raise AssertionError("deadline не должен читаться при наличии t0")

    class Stub:
        deadline = 1000.0

    assert zen._attempts_t0(WithT0(), "m", "p") == 12.5
    assert zen._attempts_t0(Stub(), "m", "p") == 1000.0 - zen.TIMEOUT_S


def test_zen_idle_expired_skips_active_tools(zen: Any) -> None:
    """RW-003: Idle не срабатывает, пока исполняется tool; без tool — срабатывает на пороге."""
    assert zen._zen_idle_expired(20.0, 0.0, 15.0, False)
    assert not zen._zen_idle_expired(20.0, 0.0, 15.0, True)
    assert not zen._zen_idle_expired(10.0, 0.0, 15.0, False)


def test_tool_activity_tracks_running_tools(zen: Any) -> None:
    """RW-003: pending/running включают активность, завершённый статус выключает."""
    activity = zen._ToolActivity()
    assert not activity
    running = {"part": {"id": "c1", "tool": "task", "state": {"status": "running"}}}
    done = {"part": {"id": "c1", "tool": "task", "state": {"status": "completed"}}}
    activity.observe("text", running)
    assert not activity
    activity.observe("tool_use", running)
    assert activity
    activity.observe("tool_use", done)
    assert not activity


def test_tool_activity_parallel_calls_not_collapsed(zen: Any) -> None:
    """RW-004: завершение одного вызова не снимает защиту с остальных активных вызовов того же tool."""

    def event(call_id: str | None, status: str) -> dict[str, Any]:
        part: dict[str, Any] = {"tool": "bash", "state": {"status": status}}
        if call_id:
            part["callID"] = call_id
        return {"part": part}

    activity = zen._ToolActivity()
    activity.observe("tool_use", event("a", "running"))
    activity.observe("tool_use", event("b", "running"))
    activity.observe("tool_use", event("a", "completed"))
    assert activity
    activity.observe("tool_use", event("b", "completed"))
    assert not activity

    # Без callID/id вызовы одного tool считаются счётчиком, а не одним ключом.
    anonymous = zen._ToolActivity()
    anonymous.observe("tool_use", event(None, "running"))
    anonymous.observe("tool_use", event(None, "running"))
    anonymous.observe("tool_use", event(None, "completed"))
    assert anonymous
    anonymous.observe("tool_use", event(None, "completed"))
    assert not anonymous
    anonymous.observe("tool_use", event(None, "completed"))
    assert not anonymous


def test_serve_tool_state_has_active(zen: Any) -> None:
    """RW-003: вызов активен с первого фрагмента и до complete()."""
    state = zen._ServeToolState()
    assert not state.has_active()
    state.feed({"id": "c1", "name": "bash"})
    assert state.has_active()
    state.feed({"id": "c1", "name": "bash", "input": {"command": "pwd"}})
    assert state.complete("c1", "session.tool.called") is not None
    assert not state.has_active()


def test_zen_stream_retry_ttft_counts_from_attempt_start(
    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RW-002: запрос, стартовавший давно (очередь/первая попытка), не режется TTFT текущей попытки."""
    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "3")
    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "3")
    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
    real_t0 = zen._attempts_t0
    monkeypatch.setattr(
        zen,
        "_attempts_t0",
        lambda *a, **k: min(real_t0(*a, **k), time.monotonic() - 100.0),
    )
    fake = _zen_fake_stream_child(tmp_path, chunks=2, gap_s=0.05, lead_s=0.4)
    status, body, procs = _zen_stream_request(zen, monkeypatch, tmp_path, fake)
    assert status == 200
    assert b"Gateway Timeout in zen-bridge" not in body
    assert b"t0 " in body and b"t1 " in body
    assert body.count(b"data: [DONE]") == 1


def test_zen_run_retry_ttft_counts_from_attempt_start(
    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RW-002: тот же сценарий для не-стримингового Run."""
    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "3")
    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "3")
    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
    real_t0 = zen._attempts_t0
    monkeypatch.setattr(
        zen,
        "_attempts_t0",
        lambda *a, **k: min(real_t0(*a, **k), time.monotonic() - 100.0),
    )
    fake = _zen_fake_stream_child(tmp_path, chunks=2, gap_s=0.05, lead_s=0.4)
    status, body, _procs = _zen_stream_request(
        zen, monkeypatch, tmp_path, fake, stream=False
    )
    assert status == 200, body
    assert b"t0 t1" in body


def test_zen_stream_long_tool_not_cut_by_idle(
    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RW-003: tool дольше Idle без токенов не обрывает стриминговый поток."""
    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "2")
    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "0.3")
    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
    fake = _zen_fake_stream_child(tmp_path, chunks=2, gap_s=0.05, tool_s=1.2)
    status, body, procs = _zen_stream_request(zen, monkeypatch, tmp_path, fake)
    assert status == 200
    assert b"Gateway Timeout in zen-bridge" not in body
    assert b"t0 " in body and b"t1 " in body
    assert body.count(b"data: [DONE]") == 1
    assert procs and all(proc.poll() is not None for proc in procs)


def test_zen_run_long_tool_not_cut_by_idle(
    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RW-003: tool дольше Idle не обрывает не-стриминговый Run."""
    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "2")
    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "0.3")
    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
    fake = _zen_fake_stream_child(tmp_path, chunks=2, gap_s=0.05, tool_s=1.2)
    status, body, _procs = _zen_stream_request(
        zen, monkeypatch, tmp_path, fake, stream=False
    )
    assert status == 200, body
    assert b"t0 t1" in body
