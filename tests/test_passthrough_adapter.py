"""Passthrough-шов (ADR 0011 AD-003/AD-005/AD-007): стриминг, составной ключ, EOF, лимиты, маршрут."""

from __future__ import annotations

import http.client
import io
import json
import os
import socket
from socketserver import BaseServer
import sys
import tempfile
import threading
from types import SimpleNamespace
from typing import Any, Mapping, cast
import unittest
import unittest.mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from core.backend_adapter import TurnResult  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402
from adapters.passthrough_adapter import (  # noqa: E402
    _TimedSseReader,
    ClientGone,
    PassthroughAdapter,
    PassthroughLimits,
    ResponseSink,
    relay_sse,
)
from bridge_testlib import BridgeCase, load_raw_fleet  # noqa: E402
from core.backend_adapter import (
    AdapterRegistry,
)  # noqa: E402
from core.passthrough_sliding_window import (  # noqa: E402
    SlidingDeadline,
    init_sliding_stream,
)
from core.precommit_timeout_policy import (  # noqa: E402
    classify_precommit_generic_failure,
)


from tests.passthrough_stream_testlib import (
    STR as STR,
    SCHEMAS as SCHEMAS,
    TOOLS as TOOLS,
    DONE as DONE,
    frame as frame,
    chunk as chunk,
    content as content,
    tool_delta as tool_delta,
    finish as finish,
    run_stream as run_stream,
    payloads as payloads,
    published_calls as published_calls,
    args_of as args_of,
)  # noqa: E402 - сохраняем прежние точки обнаружения тестов

from tests.passthrough_stream_cases import (
    TestStreamRelay as TestStreamRelay,
)  # noqa: E402 - сохраняем прежние точки обнаружения тестов

from tests.passthrough_limits_cases import (
    TestAccumulatorLimits as TestAccumulatorLimits,
    TestLimitsFromEnv as TestLimitsFromEnv,
    TestNonStreamBody as TestNonStreamBody,
)  # noqa: E402 - сохраняем прежние точки обнаружения тестов

from tests.passthrough_catalog_cases import (
    TestFleetPassthroughKind as TestFleetPassthroughKind,
    TestBridgeSecrets as TestBridgeSecrets,
    TestClientTokenValidation as TestClientTokenValidation,
    TestDirectLoopbackValidation as TestDirectLoopbackValidation,
    TestNeutralTimeoutLabel as TestNeutralTimeoutLabel,
)  # noqa: E402 - сохраняем прежние точки обнаружения тестов

from tests.passthrough_nonstream_cases import (
    TestNonstreamLimitsFromEnv as TestNonstreamLimitsFromEnv,
)  # noqa: E402 - сохраняем прежние точки обнаружения тестов
# ---- SSE-помощники ------------------------------------------------------------------


def test_stream_upstream_failure_has_stop_and_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "true")
    outcome, out = run_stream(content("partial"))
    assert outcome.incomplete
    assert not outcome.done
    terminal = payloads(out)[-1]
    assert terminal["error"]["code"] == "upstream_incomplete_stream"
    assert terminal["choices"][0]["finish_reason"] == "stop"
    assert b"".join(out).endswith(DONE)
    assert b"".join(out).count(DONE) == 1


def test_stream_upstream_failure_preserves_legacy_framing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "false")
    outcome, out = run_stream(content("partial"))
    assert outcome.incomplete
    assert payloads(out)[-1]["choices"][0]["finish_reason"] is None
    assert b"".join(out).endswith(DONE)


class TestCliRouteToolSchemas(unittest.TestCase):
    """F-002: схемы `request.tools` доходят до санитизатора на CLI-маршрутах фасада."""

    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "keep_empty",
                "parameters": {
                    "type": "object",
                    "properties": {"note": {"type": "string"}},
                    "required": ["note"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "drop_empty",
                "parameters": {
                    "type": "object",
                    "properties": {"note": {"type": "string"}},
                },
            },
        },
    ]

    def raw_turn(self):
        text = (
            '<tool_call>{"name": "drop_empty", "arguments": {"note": ""}}</tool_call>'
            '<tool_call>{"name": "keep_empty", "arguments": {"note": ""}}</tool_call>'
        )
        return TurnResult(state="done", rc=0, text=text)

    def finalized_args(self, tool_schemas):
        return [
            json.loads(call["function"]["arguments"])
            for call in self.dispatch(self.raw_turn(), tool_schemas)["tool_calls"]
        ]

    def dispatch(
        self, raw, schemas, stream=False, managed_turn=None, model="m", sanitize=True
    ):
        ctx = {
            "backend": "droid",
            "model": model,
            "effort": "high",
            "prompt": "p",
            "rpc": {"system": "", "runnable": "", "items": []},
            "images": [],
            "emulate_tools": True,
            "tool_schemas": schemas,
            "stream": stream,
            "managed_turn": managed_turn,
        }
        adapter = SimpleNamespace(kind="droid", execute_turn=lambda turn, writer: raw)
        with (
            unittest.mock.patch.object(server, "BRIDGE_SANITIZE_TOOL_CALLS", sanitize),
            unittest.mock.patch.object(server.BACKENDS, "get", return_value=adapter),
        ):
            return server.Handler._dispatch(SimpleNamespace(connection=None), ctx, None)

    def test_dispatch_sanitizes_once_after_finalize_and_matches_events(self):
        schemas = server.build_tool_schemas(self.TOOLS)
        for stream in (False, True):
            for prebuilt in (False, True):
                raw = self.raw_turn()
                if prebuilt:
                    raw = server.finalize_turn(raw, True)
                order = []
                original_finalize = server.finalize_turn
                original_sanitize = server.sanitize_tool_call

                def finalize(*args, **kwargs):
                    order.append("finalize")
                    return original_finalize(*args, **kwargs)

                def sanitize(*args, **kwargs):
                    order.append("sanitize")
                    return original_sanitize(*args, **kwargs)

                with (
                    unittest.mock.patch.object(
                        server, "finalize_turn", side_effect=finalize
                    ),
                    unittest.mock.patch.object(
                        server, "sanitize_tool_call", side_effect=sanitize
                    ) as spy,
                ):
                    out = self.dispatch(raw, schemas, stream)
                self.assertEqual(spy.call_count, 2)
                self.assertEqual(order, ["finalize", "sanitize", "sanitize"])
                self.assertEqual(
                    out["tool_calls"],
                    [value for kind, value in out["events"] if kind == "tool_call"],
                )
                self.assertEqual(
                    [
                        json.loads(call["function"]["arguments"])
                        for call in out["tool_calls"]
                    ],
                    [{}, {"note": ""}],
                )

    def test_dispatch_kill_switch_skips_sanitizer(self):
        with unittest.mock.patch.object(server, "sanitize_tool_call") as spy:
            out = self.dispatch(
                self.raw_turn(), server.build_tool_schemas(self.TOOLS), sanitize=False
            )
        spy.assert_not_called()
        self.assertEqual(
            json.loads(out["tool_calls"][0]["function"]["arguments"]), {"note": ""}
        )

    def test_managed_completion_receives_sanitized_result(self):
        managed = object()
        with unittest.mock.patch.object(
            server.TURN_MANAGER, "complete_turn_from_result"
        ) as complete:
            out = self.dispatch(
                self.raw_turn(),
                server.build_tool_schemas(self.TOOLS),
                managed_turn=managed,
            )
        self.assertIs(complete.call_args.args[0], managed)
        result = complete.call_args.args[1]
        self.assertEqual(json.loads(result.tool_calls[0].function.arguments), {})
        self.assertEqual(
            [event.value for event in result.events if event.kind == "tool_call"],
            list(result.tool_calls),
        )
        self.assertEqual(
            out["tool_calls"][0]["function"]["arguments"],
            result.tool_calls[0].function.arguments,
        )

    def test_managed_replay_returns_finalized_calls_without_sanitizing(self):
        final = self.dispatch(self.raw_turn(), server.build_tool_schemas(self.TOOLS))
        managed = SimpleNamespace(done_event=threading.Event(), final_dict=final)
        managed.done_event.set()
        with unittest.mock.patch.object(server, "sanitize_tool_call") as spy:
            replay = server.Handler._dispatch(
                SimpleNamespace(),
                {"attached_existing": True, "managed_turn": managed},
                None,
            )
        spy.assert_not_called()
        self.assertEqual(replay, final)

    def test_finalize_uses_request_tool_schemas(self):
        schemas = server.build_tool_schemas(self.TOOLS)
        self.assertEqual(self.finalized_args(schemas), [{}, {"note": ""}])

    def test_finalize_without_schemas_is_fail_conservative(self):
        self.assertEqual(self.finalized_args(None), [{"note": ""}, {"note": ""}])

    def test_turn_context_carries_tool_schemas(self):
        schemas = server.build_tool_schemas(self.TOOLS)
        self.assertIs(
            server.TurnContext("m", "high", "p", tool_schemas=schemas).tool_schemas,
            schemas,
        )


# ---- реальный upstream и шов ------------------------------------------------------
class FakeUpstream:
    """Локальный OpenAI-совместимый upstream; сценарий задаёт `respond(handler, body)`."""

    def __init__(self, keep_alive=False):
        self.requests: list = []
        self.respond = lambda handler, body: None
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1" if keep_alive else "HTTP/1.0"

            def log_message(self, *args):  # noqa: D401
                return

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                outer.requests.append(
                    {"path": self.path, "headers": dict(self.headers), "body": body}
                )
                outer.respond(self, body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    @staticmethod
    def json(handler, payload, status=200, extra=()):
        data = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(data)))
        for key, value in extra:
            handler.send_header(key, value)
        handler.end_headers()
        handler.wfile.write(data)

    @staticmethod
    def sse(handler, body: bytes):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        handler.wfile.write(body)
        handler.wfile.flush()


class CollectSink(ResponseSink):
    def __init__(self):
        self.status = None
        self.headers = []
        self.chunks: list = []
        self.fail_after = None

    def start(self, status, headers):
        self.status, self.headers = status, headers

    def write(self, data):
        if self.fail_after is not None and len(self.chunks) >= self.fail_after:
            raise ClientGone()
        self.chunks.append(data)

    @property
    def body(self) -> bytes:
        return b"".join(self.chunks)

    def header(self, name):
        return next((v for k, v in self.headers if k.lower() == name.lower()), None)


def make_adapter(
    port: int, limits: PassthroughLimits | None = None, **kw: Any
) -> PassthroughAdapter:
    config = {
        "kind": "passthrough",
        "base_url": "http://127.0.0.1:%d/v1" % port,
        "max_concurrent": 4,
    }
    kw.setdefault("is_hub_key", server.is_hub_key)
    return PassthroughAdapter(
        "codex", config, lambda: {}, None, limits=limits or PassthroughLimits(), **kw
    )


def _call_passthrough(
    adapter: PassthroughAdapter, headers: Mapping[str, str]
) -> CollectSink:
    sink = CollectSink()
    adapter.handle(
        path="/v1/chat/completions",
        raw_body=b"{}",
        request={},
        headers=headers,
        sink=sink,
    )
    assert sink.status == 200
    return sink


def _credential_values(sent_headers: Mapping[str, str]) -> list[str]:
    return [
        v
        for k, v in sent_headers.items()
        if k.lower() in ("authorization", "x-api-key")
    ]


def test_adapter_module_has_no_server_import() -> None:
    import ast

    source = (
        Path(__file__).resolve().parent.parent / "adapters" / "passthrough_adapter.py"
    ).read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not [
        name for name in imported if name == "server" or name.startswith("server.")
    ]


def test_injected_is_hub_key_strips_both_credentials_and_keeps_request_drop() -> None:
    upstream = FakeUpstream()
    upstream.respond = lambda handler, body: FakeUpstream.json(handler, {"ok": True})
    adapter = make_adapter(upstream.port, is_hub_key=lambda tok: tok == "hub-key")
    try:
        _call_passthrough(
            adapter,
            {
                "Authorization": "Bearer own-key",
                "X-Api-Key": "hub-key",
                "X-Custom": "keep",
                "Proxy-Authorization": "secret",
            },
        )
        sent = upstream.requests[-1]["headers"]
        assert _credential_values(sent) == []
        assert sent["X-Custom"] == "keep"
        assert [v for k, v in sent.items() if k.lower() == "proxy-authorization"] == []
    finally:
        adapter.shutdown()
        upstream.close()


def test_injected_is_hub_key_false_and_missing_forward_credentials() -> None:
    upstream = FakeUpstream()
    upstream.respond = lambda handler, body: FakeUpstream.json(handler, {"ok": True})
    adapters = [
        make_adapter(upstream.port, is_hub_key=lambda tok: False),
        make_adapter(upstream.port, is_hub_key=None),
    ]
    try:
        for adapter in adapters:
            _call_passthrough(
                adapter,
                {"authorization": "bearer client-key", "x-api-key": "client-x-api-key"},
            )
            assert sorted(_credential_values(upstream.requests[-1]["headers"])) == [
                "bearer client-key",
                "client-x-api-key",
            ]
    finally:
        for adapter in adapters:
            adapter.shutdown()
        upstream.close()


def test_host_is_hub_key_callback_strips_mixed_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        server, "TOKEN_CACHE", SimpleNamespace(is_valid=lambda tok: False)
    )
    upstream = FakeUpstream()
    upstream.respond = lambda handler, body: FakeUpstream.json(handler, {"ok": True})
    adapter = PassthroughAdapter(
        "codex",
        {
            "kind": "passthrough",
            "base_url": "http://127.0.0.1:%d/v1" % upstream.port,
            "max_concurrent": 4,
        },
        lambda: {},
        SimpleNamespace(is_hub_key=lambda tok: tok == "hub-key"),
        limits=PassthroughLimits(),
        sanitize=True,
    )
    try:
        _call_passthrough(
            adapter, {"Authorization": "Bearer own-key", "x-api-key": "hub-key"}
        )
        assert _credential_values(upstream.requests[-1]["headers"]) == []
    finally:
        adapter.shutdown()
        upstream.close()


def test_constructor_is_hub_key_overrides_host_callback() -> None:
    upstream = FakeUpstream()
    upstream.respond = lambda handler, body: FakeUpstream.json(handler, {"ok": True})
    config = {
        "kind": "passthrough",
        "base_url": "http://127.0.0.1:%d/v1" % upstream.port,
        "max_concurrent": 4,
    }
    adapters = [
        PassthroughAdapter(
            "codex",
            config,
            lambda: {},
            SimpleNamespace(is_hub_key=lambda tok: True),
            limits=PassthroughLimits(),
            sanitize=True,
            is_hub_key=lambda tok: False,
        ),
        PassthroughAdapter(
            "codex",
            config,
            lambda: {},
            SimpleNamespace(is_hub_key=lambda tok: False),
            limits=PassthroughLimits(),
            sanitize=True,
            is_hub_key=lambda tok: tok == "hub-key",
        ),
    ]
    try:
        _call_passthrough(adapters[0], {"Authorization": "Bearer hub-key"})
        assert _credential_values(upstream.requests[-1]["headers"]) == [
            "Bearer hub-key"
        ]
        _call_passthrough(
            adapters[1], {"Authorization": "Bearer hub-key", "x-api-key": "own-key"}
        )
        assert _credential_values(upstream.requests[-1]["headers"]) == []
    finally:
        for adapter in adapters:
            adapter.shutdown()
        upstream.close()


def test_server_is_hub_key_delegates_to_token_cache_and_host_integration(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        server, "TOKEN_CACHE", SimpleNamespace(is_valid=lambda tok: tok == "hub-key")
    )
    assert server.is_hub_key("hub-key") is True
    assert server.is_hub_key("own-key") is False
    upstream = FakeUpstream()
    upstream.respond = lambda handler, body: FakeUpstream.json(handler, {"ok": True})
    adapter = PassthroughAdapter(
        "codex",
        {
            "kind": "passthrough",
            "base_url": "http://127.0.0.1:%d/v1" % upstream.port,
            "max_concurrent": 4,
        },
        lambda: {},
        server,
        limits=PassthroughLimits(),
        sanitize=True,
    )
    try:
        _call_passthrough(
            adapter, {"authorization": "bearer hub-key", "X-API-KEY": "own-key"}
        )
        assert _credential_values(upstream.requests[-1]["headers"]) == []
    finally:
        adapter.shutdown()
        upstream.close()


def test_connection_pool_reuses_socket_and_isolates_headers(monkeypatch) -> None:
    monkeypatch.setattr(
        server, "TOKEN_CACHE", SimpleNamespace(is_valid=lambda tok: False)
    )
    upstream = FakeUpstream(keep_alive=True)
    sockets = []

    def respond(handler, body):
        sockets.append(handler.connection)
        FakeUpstream.json(handler, {"ok": True})

    upstream.respond = respond
    adapter = make_adapter(upstream.port)
    try:
        for headers in (
            {"Authorization": "Bearer first", "X-Subagent-Id": "first"},
            {"Authorization": "Bearer second", "X-Subagent-Id": "second"},
            {},
        ):
            sink = CollectSink()
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=b"{}",
                request={},
                headers=headers,
                sink=sink,
            )
            assert sink.status == 200
        assert sockets[0] is sockets[1] is sockets[2]
        assert upstream.requests[0]["headers"]["Authorization"] == "Bearer first"
        assert upstream.requests[1]["headers"]["Authorization"] == "Bearer second"
        assert upstream.requests[1]["headers"]["X-Subagent-Id"] == "second"
        assert "Authorization" not in upstream.requests[2]["headers"]
        assert "X-Subagent-Id" not in upstream.requests[2]["headers"]
    finally:
        adapter.shutdown()
        upstream.close()


def test_parallel_requests_do_not_share_inflight_connection_or_headers(
    monkeypatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(
        server, "TOKEN_CACHE", SimpleNamespace(is_valid=lambda tok: False)
    )

    upstream = FakeUpstream(keep_alive=True)
    adapter = make_adapter(upstream.port)
    barrier = threading.Barrier(4)
    sockets = []

    def respond(handler, body):
        sockets.append(handler.connection)
        barrier.wait(timeout=5)
        FakeUpstream.json(
            handler,
            {
                "auth": handler.headers.get("Authorization"),
                "subagent": handler.headers.get("X-Subagent-Id"),
            },
        )

    def call(index):
        key = str(index)
        sink = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={},
            headers={"Authorization": key, "X-Subagent-Id": key},
            sink=sink,
        )
        assert sink.status == 200
        assert json.loads(sink.body) == {"auth": key, "subagent": key}

    upstream.respond = respond
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(call, range(4)))
        assert len({id(sock) for sock in sockets}) == 4
        assert adapter.active_count() == 0
    finally:
        adapter.shutdown()
        upstream.close()


def test_connection_close_response_is_never_pooled() -> None:
    upstream = FakeUpstream(keep_alive=True)
    adapter = make_adapter(upstream.port)
    sockets = []

    def respond(handler, body):
        sockets.append(handler.connection)
        FakeUpstream.json(handler, {"ok": True}, extra=[("Connection", "close")])

    upstream.respond = respond
    try:
        for _ in range(2):
            sink = CollectSink()
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=b"{}",
                request={},
                headers={},
                sink=sink,
            )
            assert sink.status == 200
        assert sockets[0] is not sockets[1]
    finally:
        adapter.shutdown()
        upstream.close()


@pytest.mark.parametrize(
    "value",
    ["0", "false", "no", "FALSE", "No", "off", " Off ", " 0 ", "unexpected", "", "   "],
)
def test_pooling_kill_switch_closes_and_never_reuses(value, monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", value)
    upstream = FakeUpstream(keep_alive=True)
    sockets = []

    def respond(handler, body):
        sockets.append(handler.connection)
        FakeUpstream.json(handler, {"ok": True})

    upstream.respond = respond
    adapter = make_adapter(upstream.port)
    try:
        for _ in range(2):
            sink = CollectSink()
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=b"{}",
                request={},
                headers={},
                sink=sink,
            )
            assert sink.status == 200
        assert sockets[0] is not sockets[1]
        for req in upstream.requests:
            headers = {k.lower(): v for k, v in req["headers"].items()}
            assert headers["connection"] == "close"
        assert adapter._pool._idle == {}
    finally:
        adapter.shutdown()
        upstream.close()


@pytest.mark.parametrize(
    "value", ["1", "true", "yes", "on", " On ", " TRUE ", " 1 ", "YES"]
)
def test_pooling_enabled_keeps_alive_and_reuses(value, monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", value)
    upstream = FakeUpstream(keep_alive=True)
    sockets = []

    def respond(handler, body):
        sockets.append(handler.connection)
        FakeUpstream.json(handler, {"ok": True})

    upstream.respond = respond
    adapter = make_adapter(upstream.port)
    try:
        for _ in range(2):
            sink = CollectSink()
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=b"{}",
                request={},
                headers={},
                sink=sink,
            )
            assert sink.status == 200
        assert sockets[0] is sockets[1]
        for req in upstream.requests:
            headers = {k.lower(): v for k, v in req["headers"].items()}
            assert headers["connection"] == "keep-alive"
    finally:
        adapter.shutdown()
        upstream.close()


def test_pooling_disabled_after_idle_does_not_take_pooled_socket(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "1")
    upstream = FakeUpstream(keep_alive=True)
    sockets = []

    def respond(handler, body):
        sockets.append(handler.connection)
        FakeUpstream.json(handler, {"ok": True})

    upstream.respond = respond
    adapter = make_adapter(upstream.port)
    try:
        sink = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={},
            headers={},
            sink=sink,
        )
        assert sink.status == 200
        assert adapter._pool._idle
        monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "0")
        sink = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={},
            headers={},
            sink=sink,
        )
        assert sink.status == 200
        assert sockets[0] is not sockets[1]
        headers = {k.lower(): v for k, v in upstream.requests[-1]["headers"].items()}
        assert headers["connection"] == "close"
    finally:
        adapter.shutdown()
        upstream.close()


def test_pooling_disabled_drains_idle_before_next_open(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "1")
    upstream = FakeUpstream(keep_alive=True)
    sockets = []

    def respond(handler, body):
        sockets.append(handler.connection)
        FakeUpstream.json(handler, {"ok": True})

    upstream.respond = respond
    adapter = make_adapter(upstream.port)
    try:
        sink = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={},
            headers={},
            sink=sink,
        )
        assert sink.status == 200
        assert adapter._pool._idle
        idle_conn, _ = next(iter(adapter._pool._idle.values()))[0]
        assert idle_conn.sock is not None
        idle_sock = idle_conn.sock
        assert idle_sock.fileno() != -1
        events = []
        orig_close = adapter._pool.close_all
        orig_get = adapter._pool.get_connection

        def track_close():
            events.append("close_all")
            orig_close()

        def track_get(*args, **kwargs):
            events.append(("get", idle_sock.fileno()))
            return orig_get(*args, **kwargs)

        monkeypatch.setattr(adapter._pool, "close_all", track_close)
        monkeypatch.setattr(adapter._pool, "get_connection", track_get)
        monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "off")
        sink = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={},
            headers={},
            sink=sink,
        )
        assert sink.status == 200
        assert events[0] == "close_all"
        assert events[1] == ("get", -1)
        assert idle_sock.fileno() == -1
        assert adapter._pool._idle == {}
        assert sockets[0] is not sockets[1]
    finally:
        adapter.shutdown()
        upstream.close()


def test_pooling_disabled_during_request_does_not_pool(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "1")
    upstream = FakeUpstream(keep_alive=True)

    def respond(handler, body):
        monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "0")
        FakeUpstream.json(handler, {"ok": True})

    upstream.respond = respond
    adapter = make_adapter(upstream.port)
    try:
        sink = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={},
            headers={},
            sink=sink,
        )
        assert sink.status == 200
        assert adapter._pool._idle == {}
    finally:
        adapter.shutdown()
        upstream.close()


def test_pooling_enabled_during_request_closes_and_does_not_pool(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "0")
    upstream = FakeUpstream(keep_alive=True)
    server_sockets = []
    client_sockets = []

    def respond(handler, body):
        server_sockets.append(handler.connection)
        monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "1")
        FakeUpstream.json(handler, {"ok": True})

    upstream.respond = respond
    adapter = make_adapter(upstream.port)
    orig_get_connection = adapter._pool.get_connection

    def track_get_connection(*args, **kwargs):
        conn, reused = orig_get_connection(*args, **kwargs)
        assert conn.sock is not None
        client_sockets.append(conn.sock)
        return conn, reused

    monkeypatch.setattr(adapter._pool, "get_connection", track_get_connection)
    try:
        sink = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={},
            headers={},
            sink=sink,
        )
        assert sink.status == 200
        first_headers = {
            k.lower(): v for k, v in upstream.requests[0]["headers"].items()
        }
        assert first_headers["connection"] == "close"
        assert adapter._pool._idle == {}
        assert len(client_sockets) == 1
        assert client_sockets[0].fileno() == -1

        sink2 = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={},
            headers={},
            sink=sink2,
        )
        assert sink2.status == 200
        assert server_sockets[0] is not server_sockets[1]
        assert client_sockets[0] is not client_sockets[1]
    finally:
        adapter.shutdown()
        upstream.close()


def test_pool_limits_from_env() -> None:
    limits = PassthroughLimits.from_env(
        {
            "BRIDGE_MAX_KEEPALIVE_CONNECTIONS": "7",
            "BRIDGE_KEEPALIVE_EXPIRY_S": "12.5",
        }
    )
    assert limits.max_keepalive_connections == 7
    assert limits.keepalive_expiry_s == 12.5


def test_keepalive_expiry_defaults_to_30() -> None:
    from adapters.passthrough_adapter import PassthroughConnectionPool

    assert PassthroughLimits().keepalive_expiry_s == 30.0
    assert PassthroughLimits.from_env({}).keepalive_expiry_s == 30.0
    assert PassthroughConnectionPool()._keepalive_expiry_s == 30.0


def test_handler_sink_flushes_every_chunk() -> None:
    handler = unittest.mock.Mock()
    sink = server._HandlerSink(handler)
    sink.write(content("first"))
    sink.write(DONE)
    assert handler.wfile.method_calls == [
        unittest.mock.call.write(content("first")),
        unittest.mock.call.flush(),
        unittest.mock.call.write(DONE),
        unittest.mock.call.flush(),
    ]


def test_pool_lifo_expiry_capacity_and_shutdown(monkeypatch) -> None:
    from adapters.passthrough_adapter import PassthroughConnectionPool

    clock = [1.0]
    monkeypatch.setattr("adapters.passthrough_adapter.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "adapters.passthrough_adapter.select.select", lambda *args: ([], [], [])
    )
    pool = PassthroughConnectionPool(max_keepalive=2, keepalive_expiry_s=10)
    connections = [unittest.mock.Mock() for _ in range(4)]
    with unittest.mock.patch(
        "http.client.HTTPConnection", side_effect=connections
    ) as factory:
        first, reused = pool.get_connection("localhost", 1234, 2)
        assert not reused
        second, _ = pool.get_connection("localhost", 1234, 2)
        third, _ = pool.get_connection("localhost", 1234, 2)
        pool.release_connection("localhost", 1234, first)
        pool.release_connection("localhost", 1234, second)
        pool.release_connection("localhost", 1234, third)
        third.close.assert_called_once()
        current, reused = pool.get_connection("localhost", 1234, 5)
        assert current is second and reused
        current.sock.settimeout.assert_called_with(5)
        pool.release_connection("localhost", 1234, current)
        clock[0] += 11
        current, reused = pool.get_connection("localhost", 1234, 1)
        assert current is connections[3] and not reused
        first.close.assert_called_once()
        second.close.assert_called_once()
        assert factory.call_count == 4
        pool.release_connection("localhost", 1234, current)
        pool.close_all()
        current.close.assert_called_once()
        pool.release_connection("localhost", 1234, third)
        assert third.close.call_count == 2


@pytest.mark.parametrize("peek", [b"", b"unexpected", OSError("reset")])
def test_pool_rejects_readable_idle_socket(peek, monkeypatch) -> None:
    from adapters.passthrough_adapter import PassthroughConnectionPool

    old, new = unittest.mock.Mock(), unittest.mock.Mock()
    old.sock.recv.side_effect = [peek]
    monkeypatch.setattr(
        "adapters.passthrough_adapter.select.select", lambda *args: ([old.sock], [], [])
    )
    pool = PassthroughConnectionPool()
    pool.release_connection("localhost", 1234, old)
    with unittest.mock.patch("http.client.HTTPConnection", return_value=new):
        conn, reused = pool.get_connection("localhost", 1234, 1)
    assert conn is new and not reused
    old.sock.recv.assert_called_once_with(1, socket.MSG_PEEK)
    old.close.assert_called_once()
    new.close()


@pytest.mark.parametrize(
    "method,error,expected_status,expected_get_count,expected_fresh",
    [
        ("request", BrokenPipeError, 502, 1, False),
        ("request", ConnectionResetError, 502, 1, False),
        ("request", http.client.CannotSendRequest, 200, 2, True),
    ],
)
def test_reused_connection_race_retries_once_on_fresh_socket(
    method, error, expected_status, expected_get_count, expected_fresh
) -> None:
    upstream = FakeUpstream(keep_alive=True)
    upstream.respond = lambda handler, body: FakeUpstream.json(handler, {"ok": True})
    adapter = make_adapter(upstream.port)
    try:

        def call(status=200):
            sink = CollectSink()
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=b"{}",
                request={},
                headers={},
                sink=sink,
            )
            assert sink.status == status

        call()
        old, reused = adapter._pool.get_connection("127.0.0.1", upstream.port, 2)
        assert reused
        adapter._pool.release_connection("127.0.0.1", upstream.port, old)
        with (
            unittest.mock.patch.object(
                old, method, side_effect=error("stale")
            ) as failed,
            unittest.mock.patch.object(
                adapter._pool, "get_connection", wraps=adapter._pool.get_connection
            ) as get,
        ):
            call(expected_status)
            failed.assert_called_once()
            assert get.call_count == expected_get_count
            assert get.call_args.kwargs["fresh"] is expected_fresh
        assert old.sock is None
    finally:
        adapter.shutdown()
        upstream.close()


@pytest.mark.parametrize(
    ("armed", "now_s", "expected_status", "expected_type"),
    [
        (False, 109.0, 502, "upstream_unavailable"),
        (False, 110.0, 504, "upstream_timeout"),
        (True, 120.0, 502, "upstream_unavailable"),
        (True, 165.0, 504, "upstream_timeout"),
        (True, 200.0, 504, "upstream_timeout"),
    ],
    ids=[
        "unarmed-live",
        "unarmed-equality",
        "armed-after-static-live",
        "armed-current-equality",
        "armed-cap-equality",
    ],
)
def test_generic_failure_uses_sliding_deadline_once(
    monkeypatch: pytest.MonkeyPatch,
    armed: bool,
    now_s: float,
    expected_status: int,
    expected_type: str,
) -> None:
    adapter = make_adapter(1234)
    static_deadline_s = 110.0
    cell = SlidingDeadline(static_deadline_s)
    if armed:
        cell.arm(
            init_sliding_stream(
                now=100.0,
                initial_timeout_s=10.0,
                idle_timeout_s=50.0,
                safety_cap_s=100.0,
                enabled=True,
            )
        )
        cell.advance(now=115.0, is_useful_chunk=True)
        assert cell.state is not None
        assert static_deadline_s < 120.0 < cell.deadline_s < cell.state.cap_deadline_s

    clock = unittest.mock.Mock(return_value=min(now_s, static_deadline_s - 1.0))

    def fail_open(*_args, **_kwargs):
        clock.reset_mock()
        clock.return_value = now_s
        raise OSError("generic upstream failure")

    monkeypatch.setattr(
        "adapters.passthrough_adapter.request_deadlines",
        lambda _limits, _internal: (static_deadline_s, static_deadline_s),
    )
    monkeypatch.setattr(
        "adapters.passthrough_adapter.open_sliding_deadline",
        lambda *_args, **_kwargs: cell,
    )
    monkeypatch.setattr("adapters.passthrough_adapter.time.monotonic", clock)
    monkeypatch.setattr(adapter, "_open", fail_open)
    window = unittest.mock.MagicMock()
    window.expired.side_effect = AssertionError(
        "generic pre-commit handler must not call LivenessWindow.expired()"
    )
    try:
        with unittest.mock.patch(
            "adapters.passthrough_adapter.classify_precommit_generic_failure",
            wraps=classify_precommit_generic_failure,
        ) as classifier_spy:
            sink = CollectSink()
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=b"{}",
                request={"stream": True},
                headers={},
                sink=sink,
                window=window,
            )
    finally:
        adapter.shutdown()

    assert sink.status == expected_status
    assert json.loads(sink.body)["error"]["type"] == expected_type
    classifier_spy.assert_called_once()
    assert classifier_spy.call_args.args == ()
    assert set(classifier_spy.call_args.kwargs) == {
        "now_s",
        "current_deadline_s",
        "cap_deadline_s",
    }
    assert classifier_spy.call_args.kwargs["now_s"] == now_s
    window.expired.assert_not_called()


def test_precommit_socket_timeout_stays_504(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = make_adapter(1234)
    connection = unittest.mock.MagicMock()
    connection.getresponse.side_effect = socket.timeout("upstream read timed out")
    monkeypatch.setattr(adapter, "_open", lambda *_args, **_kwargs: connection)
    try:
        sink = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={"stream": True},
            headers={},
            sink=sink,
        )
    finally:
        adapter.shutdown()

    assert sink.status == 504
    assert json.loads(sink.body)["error"]["type"] == "upstream_timeout"


def test_postcommit_sse_generic_failure_stays_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = make_adapter(1234)
    response = unittest.mock.MagicMock()
    response.getheaders.return_value = [("Content-Type", "text/event-stream")]
    response.getheader.return_value = None
    sink = CollectSink()
    monkeypatch.setattr(
        "adapters.passthrough_adapter.relay_sse",
        unittest.mock.Mock(side_effect=OSError("stream failed after commit")),
    )
    try:
        assert not adapter._relay_stream(response, None, sink, False)
    finally:
        adapter.shutdown()

    assert sink.status == 200
    assert b"upstream_stream_error" in sink.body


@pytest.mark.parametrize(
    ("now_s", "expected_status", "expected_type"),
    [
        (109.0, 502, "upstream_unavailable"),
        (110.0, 504, "upstream_timeout"),
    ],
    ids=["live", "equality"],
)
def test_response_body_generic_failure_uses_one_clock_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    now_s: float,
    expected_status: int,
    expected_type: str,
) -> None:
    adapter = make_adapter(1234)
    response = unittest.mock.MagicMock()
    response.status = 200
    response.getheader.side_effect = lambda name: {
        "Content-Type": "application/json"
    }.get(name)
    response.read.side_effect = OSError("generic response-body failure")
    sink = CollectSink()
    clock = unittest.mock.Mock(return_value=now_s)
    monkeypatch.setattr("adapters.passthrough_adapter.time.monotonic", clock)
    try:
        assert not adapter._respond(response, {}, sink, 110.0)
    finally:
        adapter.shutdown()

    assert sink.status == expected_status
    assert json.loads(sink.body)["error"]["type"] == expected_type
    assert clock.call_count == 1


@pytest.mark.parametrize(
    "error",
    [ConnectionResetError, http.client.BadStatusLine, http.client.ResponseNotReady],
)
@pytest.mark.parametrize("accepts_presend_errors", [False, True])
def test_reused_connection_response_failure_never_replays_post(
    error, accepts_presend_errors
) -> None:
    upstream = FakeUpstream(keep_alive=True)
    received = threading.Event()

    def respond(handler, body):
        FakeUpstream.json(handler, {"ok": True})
        received.set()

    upstream.respond = respond
    adapter = make_adapter(upstream.port)
    try:
        first = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={},
            headers={},
            sink=first,
        )
        assert first.status == 200
        old, reused = adapter._pool.get_connection("127.0.0.1", upstream.port, 2)
        assert reused
        adapter._pool.release_connection("127.0.0.1", upstream.port, old)
        received.clear()

        def fail_response():
            assert received.wait(2)
            raise error("response lost after POST execution")

        with (
            unittest.mock.patch.object(old, "getresponse", side_effect=fail_response),
            unittest.mock.patch.object(
                adapter._pool, "get_connection", wraps=adapter._pool.get_connection
            ) as get,
        ):
            sink = CollectSink()
            sink.accepts_presend_errors = accepts_presend_errors
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=b"{}",
                request={},
                headers={},
                sink=sink,
            )
            assert sink.status == 502
            assert get.call_count == 1
        assert len(upstream.requests) == 2
        assert old.sock is None
    finally:
        adapter.shutdown()
        upstream.close()


def test_successful_sse_without_content_length_closes_connection(monkeypatch) -> None:
    adapter = make_adapter(1234)
    conn = unittest.mock.Mock()
    response = conn.getresponse.return_value
    response.isclosed.return_value = True
    response.will_close = False
    response.getheader.side_effect = lambda name: {
        "Content-Type": "text/event-stream",
        "Transfer-Encoding": "chunked",
    }.get(name)
    monkeypatch.setattr(
        adapter._pool, "get_connection", lambda *args, **kwargs: (conn, False)
    )
    monkeypatch.setattr(
        "adapters.passthrough_adapter.select.select", lambda *args: ([], [], [])
    )
    monkeypatch.setattr(adapter, "_respond", lambda *args, **kwargs: True)
    try:
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={"stream": True},
            headers={},
            sink=CollectSink(),
        )
        conn.close.assert_called_once()
        assert adapter.active_count() == 0
    finally:
        adapter.shutdown()


def test_stream_first_chunk_arrives_before_upstream_finishes_and_socket_reused() -> (
    None
):
    upstream = FakeUpstream(keep_alive=True)
    first_received = threading.Event()
    streamed_before_end = []
    sockets = []
    first = content("first")
    rest = finish(0, "stop") + DONE

    def respond(handler, body):
        sockets.append(handler.connection)
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Content-Length", str(len(first + rest)))
        handler.end_headers()
        handler.wfile.write(first)
        handler.wfile.flush()
        streamed_before_end.append(first_received.wait(3))
        handler.wfile.write(rest)
        handler.wfile.flush()

    class StreamingSink(CollectSink):
        def write(self, data):
            super().write(data)
            if data == first:
                first_received.set()

    upstream.respond = respond
    adapter = make_adapter(upstream.port, sanitize=False)
    try:
        for _ in range(2):
            first_received.clear()
            sink = StreamingSink()
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=b"{}",
                request={},
                headers={},
                sink=sink,
            )
            assert sink.body == first + rest
        assert streamed_before_end == [True, True]
        assert sockets[0] is sockets[1]
    finally:
        adapter.shutdown()
        upstream.close()


@pytest.mark.parametrize("send_done", [True, False])
def test_stream_cleanup_does_not_wait_for_next_http_chunk(send_done) -> None:
    upstream = FakeUpstream(keep_alive=True)
    returned = threading.Event()
    observed = threading.Event()
    returned_before_upstream_eof = []

    def respond(handler, body):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Transfer-Encoding", "chunked")
        handler.end_headers()
        data = content("first") + (finish(0, "stop") + DONE if send_done else b"")
        handler.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
        handler.wfile.flush()
        returned_before_upstream_eof.append(returned.wait(3))
        observed.set()
        try:
            handler.wfile.write(b"0\r\n\r\n")
            handler.wfile.flush()
        except OSError:
            pass

    upstream.respond = respond
    adapter = make_adapter(
        upstream.port,
        limits=PassthroughLimits(
            idle_timeout_s=0.05,
            total_timeout_s=5,
            read_timeout_s=5,
            heartbeat_interval_s=0.01,
            poll_interval_s=0.01,
        ),
        sanitize=False,
    )
    try:
        sink = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={},
            headers={},
            sink=sink,
        )
        returned.set()
        assert observed.wait(1)
        assert returned_before_upstream_eof == [True]
        assert adapter.active_count() == 0
        if send_done:
            assert sink.body.endswith(DONE)
        else:
            assert b"upstream_stream_error" in sink.body
    finally:
        returned.set()
        adapter.shutdown()
        upstream.close()


class SeamCase(unittest.TestCase):
    def setUp(self):
        self.upstream = FakeUpstream()
        self.addCleanup(self.upstream.close)
        # Детерминированно: мастер-ключом хаба считается только hub-key.
        patcher = unittest.mock.patch.object(
            server,
            "TOKEN_CACHE",
            SimpleNamespace(is_valid=lambda tok: tok == "hub-key"),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(
        self,
        request: dict,
        adapter=None,
        headers=None,
        raw=None,
        path="/v1/chat/completions",
    ):
        adapter = adapter or make_adapter(self.upstream.port, sanitize=True)
        raw = raw if raw is not None else json.dumps(request).encode("utf-8")
        sink = CollectSink()
        adapter.handle(
            path=path,
            raw_body=raw,
            request=request,
            headers=headers or {"Authorization": "Bearer upstream-key"},
            sink=sink,
        )
        return sink


class TestSeamNonStream(SeamCase):
    def completion(self, args):
        return {
            "id": "x",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "subagent",
                                    "arguments": json.dumps(args),
                                },
                            }
                        ],
                    },
                }
            ],
        }

    def test_request_forwarded_verbatim_and_response_sanitized(self):
        self.upstream.respond = lambda h, b: FakeUpstream.json(
            h, self.completion({"prompt": "p", "provider": ""})
        )
        request = {
            "model": "gpt-6.1-terra",
            "reasoning_effort": "xhigh",
            "tools": TOOLS,
            "messages": [{"role": "user", "content": "hi"}],
        }
        raw = json.dumps(request, indent=2).encode(
            "utf-8"
        )  # нестандартная сериализация: байты не пересобираются
        sink = self.call(request, raw=raw)
        sent = self.upstream.requests[0]
        self.assertEqual(sent["body"], raw)
        self.assertEqual(sent["path"], "/v1/chat/completions")
        self.assertEqual(sent["headers"]["Authorization"], "Bearer upstream-key")
        self.assertEqual(sink.status, 200)
        data = json.loads(sink.body)
        self.assertEqual(
            args_of(data["choices"][0]["message"]["tool_calls"][0]), {"prompt": "p"}
        )
        self.assertEqual(sink.header("Content-Length"), str(len(sink.body)))

    def test_missing_authorization_stays_missing_and_hop_by_hop_dropped(self):
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, {"ok": True})
        self.call(
            {"model": "m"},
            headers={
                "X-Custom": "1",
                "Connection": "keep-alive",
                "Accept-Encoding": "gzip",
                "Proxy-Authorization": "secret",
            },
        )
        headers = {
            k.lower(): v for k, v in self.upstream.requests[0]["headers"].items()
        }
        self.assertNotIn("authorization", headers)
        self.assertNotIn("proxy-authorization", headers)
        self.assertEqual(headers["x-custom"], "1")
        self.assertEqual(headers["accept-encoding"], "identity")

    def test_upstream_auth_override(self) -> None:
        self.upstream.respond = lambda handler, body: FakeUpstream.json(
            handler, {"ok": True}
        )
        cases = (
            (
                {"api_key_env": "TEST_UPSTREAM_KEY"},
                {"TEST_UPSTREAM_KEY": "env-key"},
                "env-key",
            ),
            ({"api_key": "config-key"}, {}, "config-key"),
            (
                {"api_key_env": "TEST_UPSTREAM_KEY", "api_key": "config-key"},
                {"TEST_UPSTREAM_KEY": "env-key"},
                "env-key",
            ),
            (
                {"api_key_env": "TEST_UPSTREAM_KEY", "api_key": "config-key"},
                {},
                "config-key",
            ),
        )
        for config, environ, expected in cases:
            for header in ("Authorization", "authorization", "AUTHORIZATION"):
                for api_key_header in ("x-api-key", "X-Api-Key", "X-API-KEY"):
                    with (
                        self.subTest(
                            config=config,
                            header=header,
                            api_key_header=api_key_header,
                        ),
                        unittest.mock.patch.dict(os.environ, environ, clear=True),
                    ):
                        adapter = PassthroughAdapter(
                            "test",
                            {
                                "base_url": f"http://127.0.0.1:{self.upstream.port}/v1",
                                **config,
                            },
                            dict,
                        )
                        headers = {
                            header: "Bearer client-key",
                            api_key_header: "client-x-api-key",
                            "X-Custom": "keep",
                        }
                        sink = self.call(
                            {"model": "m"}, adapter=adapter, headers=headers
                        )
                        sent = self.upstream.requests[-1]["headers"]
                        self.assertEqual(sink.status, 200)
                        self.assertEqual(
                            [
                                v
                                for k, v in sent.items()
                                if k.lower() == "authorization"
                            ],
                            [f"Bearer {expected}"],
                        )
                        self.assertEqual(
                            [v for k, v in sent.items() if k.lower() == "x-api-key"],
                            [],
                        )
                        self.assertEqual(sent["X-Custom"], "keep")
                        self.assertEqual(headers[header], "Bearer client-key")
                        self.assertEqual(headers[api_key_header], "client-x-api-key")

    def test_upstream_auth_override_without_client_authorization_and_with_streaming(
        self,
    ) -> None:
        events = content("hello") + finish(0, "stop") + DONE
        self.upstream.respond = lambda handler, body: FakeUpstream.sse(handler, events)
        adapter = PassthroughAdapter(
            "test",
            {
                "base_url": f"http://127.0.0.1:{self.upstream.port}/v1",
                "api_key": "config-key",
            },
            dict,
        )
        sink = self.call(
            {"model": "m", "stream": True},
            adapter=adapter,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual((sink.status, sink.body), (200, events))
        self.assertEqual(
            self.upstream.requests[-1]["headers"]["Authorization"], "Bearer config-key"
        )

    def test_upstream_auth_unconfigured_preserves_own_client_authorization(
        self,
    ) -> None:
        self.upstream.respond = lambda handler, body: FakeUpstream.json(
            handler, {"ok": True}
        )
        cases = (
            ({}, {}),
            ({"api_key_env": "TEST_UPSTREAM_KEY"}, {}),
            ({"api_key_env": "TEST_UPSTREAM_KEY"}, {"TEST_UPSTREAM_KEY": ""}),
            ({"api_key": ""}, {}),
        )
        for config, environ in cases:
            for api_key_header in ("x-api-key", "X-Api-Key", "X-API-KEY"):
                with (
                    self.subTest(config=config, api_key_header=api_key_header),
                    unittest.mock.patch.dict(os.environ, environ, clear=True),
                ):
                    adapter = PassthroughAdapter(
                        "test",
                        {
                            "base_url": f"http://127.0.0.1:{self.upstream.port}/v1",
                            **config,
                        },
                        dict,
                    )
                    sink = self.call(
                        {"model": "m"},
                        adapter=adapter,
                        headers={
                            "authorization": "Bearer client-key",
                            api_key_header: "client-x-api-key",
                        },
                    )
                    self.assertEqual(sink.status, 200)
                    sent = self.upstream.requests[-1]["headers"]
                    self.assertEqual(
                        sorted(
                            v
                            for k, v in sent.items()
                            if k.lower() in ("authorization", "x-api-key")
                        ),
                        ["Bearer client-key", "client-x-api-key"],
                    )

    def test_unconfigured_hub_credential_is_hidden_from_upstream(self) -> None:
        self.upstream.respond = lambda handler, body: FakeUpstream.json(
            handler, {"ok": True}
        )
        for headers in (
            {"Authorization": "Bearer hub-key", "X-Api-Key": "own-key"},
            {"Authorization": "Bearer own-key", "x-api-key": "hub-key"},
            {"authorization": "bearer hub-key"},
            {"AUTHORIZATION": "Bearer hub-key"},
            {"X-API-KEY": "hub-key"},
            {"x-api-key": "hub-key"},
        ):
            with self.subTest(headers=headers):
                sink = self.call({"model": "m"}, headers=headers)
                self.assertEqual(sink.status, 200)
                sent = self.upstream.requests[-1]["headers"]
                self.assertEqual(
                    [
                        v
                        for k, v in sent.items()
                        if k.lower() in ("authorization", "x-api-key")
                    ],
                    [],
                )

    def test_token_cache_error_does_not_leak_credentials_upstream(self) -> None:
        self.upstream.respond = lambda handler, body: FakeUpstream.json(
            handler, {"ok": True}
        )
        is_valid = unittest.mock.Mock(side_effect=RuntimeError("token check boom"))
        with unittest.mock.patch.object(
            server, "TOKEN_CACHE", SimpleNamespace(is_valid=is_valid)
        ):
            with self.assertRaisesRegex(RuntimeError, "token check boom"):
                self.call(
                    {"model": "m"},
                    headers={
                        "Authorization": "Bearer client-key",
                        "x-api-key": "client-x-api-key",
                    },
                )
        is_valid.assert_called_once_with("client-key")
        self.assertEqual(self.upstream.requests, [])

    def test_injected_is_hub_key_error_does_not_leak_credentials_upstream(self) -> None:
        self.upstream.respond = lambda handler, body: FakeUpstream.json(
            handler, {"ok": True}
        )
        is_hub_key = unittest.mock.Mock(side_effect=RuntimeError("token check boom"))
        adapter = make_adapter(self.upstream.port, sanitize=True, is_hub_key=is_hub_key)
        with self.assertRaisesRegex(RuntimeError, "token check boom"):
            self.call(
                {"model": "m"},
                adapter=adapter,
                headers={
                    "Authorization": "Bearer client-key",
                    "x-api-key": "client-x-api-key",
                },
            )
        is_hub_key.assert_called_once_with("client-key")
        self.assertEqual(self.upstream.requests, [])

    def test_abort_before_getresponse_and_late_socket_cleanup(self) -> None:
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, {"ok": True})
        adapter = make_adapter(
            self.upstream.port,
            PassthroughLimits(poll_interval_s=0.01),
            sanitize=True,
        )
        self.addCleanup(adapter.shutdown)

        # 1. ClientGone right before conn.getresponse() skips getresponse and cleans up.
        gone_after_open = False
        orig_open = adapter._open

        def open_then_gone(*args, **kwargs):
            nonlocal gone_after_open
            conn = orig_open(*args, **kwargs)
            conn.getresponse = unittest.mock.MagicMock(  # type: ignore[method-assign]
                side_effect=AssertionError("getresponse must not be called")
            )
            gone_after_open = True
            return conn

        sink1 = CollectSink()
        sink1.client_gone = lambda: gone_after_open  # type: ignore[method-assign]
        with unittest.mock.patch.object(adapter, "_open", side_effect=open_then_gone):
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=b"{}",
                request={"model": "m"},
                headers={},
                sink=sink1,
            )
        self.assertIsNone(sink1.status)
        self.assertEqual(adapter.active_count(), 0)

        # 2. Late socket arriving in on_socket after watcher abort closes socket immediately.
        late_sockets: list[socket.socket] = []
        connect_entered = threading.Event()
        orig_get_conn = adapter._pool.get_connection

        def delayed_get_conn(
            host: str, port: int, timeout: float, *, fresh: bool = False
        ):
            conn, reused = orig_get_conn(host, port, timeout, fresh=fresh)
            assert conn.sock is not None
            late_sockets.append(conn.sock)
            conn.request = unittest.mock.MagicMock(  # type: ignore[method-assign]
                side_effect=AssertionError("request must not be sent on aborted socket")
            )
            connect_entered.set()
            for thread in threading.enumerate():
                if thread.name == "passthrough-deadline":
                    thread.join(timeout=1.0)
            return conn, reused

        sink2 = CollectSink()
        sink2.client_gone = lambda: connect_entered.is_set()  # type: ignore[method-assign]
        before_requests = len(self.upstream.requests)
        with unittest.mock.patch.object(
            adapter._pool, "get_connection", side_effect=delayed_get_conn
        ):
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=b"{}",
                request={"model": "m"},
                headers={},
                sink=sink2,
            )
        self.assertEqual(len(late_sockets), 1)
        self.assertEqual(late_sockets[0].fileno(), -1)
        self.assertEqual(len(self.upstream.requests), before_requests)
        self.assertIsNone(sink2.status)
        self.assertEqual(adapter.active_count(), 0)

    def test_stream_relay_socket_timeout_triggers_on_timeout_py39_compat(self) -> None:
        class LegacySocketTimeout(OSError):
            pass

        adapter = make_adapter(self.upstream.port, sanitize=True)
        self.addCleanup(adapter.shutdown)
        resp = unittest.mock.MagicMock()
        resp.getheaders.return_value = [("Content-Type", "text/event-stream")]
        resp.getheader.return_value = None
        sink = CollectSink()
        timed_out = False

        def on_timeout() -> None:
            nonlocal timed_out
            timed_out = True

        with (
            unittest.mock.patch(
                "adapters.passthrough_adapter.socket.timeout", LegacySocketTimeout
            ),
            unittest.mock.patch(
                "adapters.passthrough_adapter.relay_sse",
                side_effect=LegacySocketTimeout("read timed out"),
            ),
        ):
            ok = adapter._relay_stream(resp, None, sink, False, on_timeout=on_timeout)
        self.assertFalse(ok)
        self.assertTrue(timed_out)

    def test_non_200_status_and_body_verbatim(self):
        error = b'{"error": {"message": "rate limited", "type": "rate"}}'
        self.upstream.respond = lambda h, b: FakeUpstream.json(
            h, error, status=429, extra=[("Retry-After", "7")]
        )
        sink = self.call({"model": "m", "tools": TOOLS})
        self.assertEqual((sink.status, sink.body), (429, error))
        self.assertEqual(sink.header("Retry-After"), "7")

    def test_non_json_200_body_verbatim(self):
        def respond(h, b):
            h.send_response(200)
            h.send_header("Content-Type", "text/plain")
            h.send_header("Content-Length", "5")
            h.end_headers()
            h.wfile.write(b"hello")

        self.upstream.respond = respond
        sink = self.call({"model": "m"})
        self.assertEqual((sink.status, sink.body), (200, b"hello"))

    def test_body_limit_minus_equal_plus(self):
        payload = json.dumps({"id": "x", "choices": []}).encode("utf-8")
        for delta, expected in ((-1, 200), (0, 200), (1, 502)):
            with self.subTest(delta=delta):
                limits = PassthroughLimits(max_body_bytes=len(payload) - delta)
                self.upstream.respond = lambda h, b: FakeUpstream.json(h, payload)
                sink = self.call(
                    {"model": "m"},
                    adapter=make_adapter(self.upstream.port, limits, sanitize=True),
                )
                self.assertEqual(sink.status, expected)
                if expected == 502:
                    self.assertEqual(
                        json.loads(sink.body)["error"]["type"],
                        "upstream_response_too_large",
                    )

    def test_huge_non_tool_body_rejected_without_chunked_length(self):
        def respond(h, b):
            h.send_response(200)
            h.send_header("Content-Type", "application/json")
            h.end_headers()  # без Content-Length: читаем до закрытия
            h.wfile.write(b" " * 4096)

        self.upstream.respond = respond
        sink = self.call(
            {"model": "m"},
            adapter=make_adapter(
                self.upstream.port,
                PassthroughLimits(max_body_bytes=1024),
                sanitize=True,
            ),
        )
        self.assertEqual(sink.status, 502)

    def test_upstream_unavailable_is_502_and_not_retried(self):
        free = socket.socket()
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
        free.close()
        sink = self.call({"model": "m"}, adapter=make_adapter(port, sanitize=True))
        self.assertEqual(sink.status, 502)
        self.assertEqual(json.loads(sink.body)["error"]["type"], "upstream_unavailable")

    def test_upstream_read_timeout_is_504(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        self.upstream.respond = lambda h, b: gate.wait(5)
        limits = PassthroughLimits(read_timeout_s=0.3)
        sink = self.call(
            {"model": "m"},
            adapter=make_adapter(self.upstream.port, limits, sanitize=True),
        )
        self.assertEqual(sink.status, 504)

    def test_sanitize_kill_switch_returns_body_untouched(self):
        raw = json.dumps(self.completion({"prompt": "p", "provider": ""})).encode(
            "utf-8"
        )
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, raw)
        sink = self.call(
            {"model": "m", "tools": TOOLS},
            adapter=make_adapter(self.upstream.port, sanitize=False),
        )
        self.assertEqual(sink.body, raw)

    def test_saturated_backend_returns_503(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        self.upstream.respond = lambda h, b: (
            gate.wait(3),
            FakeUpstream.json(h, {"ok": 1}),
        )
        adapter = make_adapter(self.upstream.port, sanitize=True)
        adapter.config["max_concurrent"] = 1
        adapter._slots = threading.BoundedSemaphore(1)
        adapter.host = type("Host", (), {"QUEUE_TIMEOUT_S": 0.2})()
        first = threading.Thread(
            target=lambda: self.call({"model": "m"}, adapter=adapter)
        )
        first.start()
        for _ in range(100):
            if adapter.active_count():
                break
            threading.Event().wait(0.02)
        sink = self.call({"model": "m"}, adapter=adapter)
        self.assertEqual(sink.status, 503)
        gate.set()
        first.join(5)
        self.assertEqual(adapter.active_count(), 0)


class TestSeamStream(SeamCase):
    def test_stream_end_to_end_sanitizes_and_keeps_order(self):
        events = (
            content("hi")
            + tool_delta(
                0, 0, call_id="c", name="subagent", args='{"prompt":"p","provider":""}'
            )
            + finish(0)
            + DONE
        )
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        sink = self.call({"model": "m", "stream": True, "tools": TOOLS})
        self.assertEqual(sink.status, 200)
        self.assertEqual(sink.header("Content-Type"), "text/event-stream")
        self.assertEqual(args_of(published_calls(sink.chunks)[0]), {"prompt": "p"})
        self.assertEqual(sink.chunks[-1], DONE)

    def test_stream_upstream_429_is_plain_http_response_not_sse(self):
        error = b'{"error": {"message": "slow down"}}'
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, error, status=429)
        sink = self.call({"model": "m", "stream": True})
        self.assertEqual((sink.status, sink.body), (429, error))
        self.assertNotEqual(sink.header("Content-Type"), "text/event-stream")

    def test_stream_eof_without_finish_reason_end_to_end(self):
        events = (
            tool_delta(0, 0, call_id="c", name="subagent", args='{"prompt":"p"') + b""
        )
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        sink = self.call({"model": "m", "stream": True, "tools": TOOLS})
        self.assertEqual(published_calls(sink.chunks), [])
        self.assertEqual(
            payloads(sink.chunks)[-1]["error"]["code"], "upstream_incomplete_stream"
        )
        self.assertTrue(sink.body.endswith(DONE))

    def test_stream_client_gone_closes_upstream_and_releases_budget(self):
        events = (
            b"".join(content("x%d" % i) for i in range(50)) + finish(0, "stop") + DONE
        )
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        adapter = make_adapter(self.upstream.port, sanitize=True)
        sink = CollectSink()
        sink.fail_after = 2
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b"{}",
            request={"stream": True},
            headers={},
            sink=sink,
        )
        self.assertEqual(adapter.active_count(), 0)
        self.assertEqual(adapter.process_budget.used, 0)

    def test_stream_overflow_in_started_sse_is_error_frame(self):
        events = (
            tool_delta(0, 0, call_id="c", name="subagent", args="{" + "x" * 500)
            + finish(0)
            + DONE
        )
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        adapter = make_adapter(
            self.upstream.port,
            PassthroughLimits(accumulator_max_bytes=100),
            sanitize=True,
        )
        sink = self.call({"model": "m", "stream": True}, adapter=adapter)
        self.assertEqual(sink.status, 200)
        self.assertEqual(published_calls(sink.chunks), [])
        self.assertEqual(
            payloads(sink.chunks)[-1]["error"]["code"], "upstream_response_too_large"
        )
        self.assertEqual(adapter.process_budget.used, 0)

    def test_stream_choices_interleaved_end_to_end(self):
        events = (
            tool_delta(0, 0, call_id="c0", name="subagent", args='{"prompt":"a"')
            + tool_delta(1, 0, call_id="c1", name="subagent", args='{"prompt":"b"')
            + tool_delta(0, 0, args="}")
            + tool_delta(1, 0, args="}")
            + finish(1)
            + finish(0)
            + DONE
        )
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        sink = self.call({"model": "m", "stream": True, "tools": TOOLS})
        self.assertEqual(
            [args_of(c) for c in published_calls(sink.chunks, 0)], [{"prompt": "a"}]
        )
        self.assertEqual(
            [args_of(c) for c in published_calls(sink.chunks, 1)], [{"prompt": "b"}]
        )


# ---- fleet kind=passthrough ---------------------------------------------------------


# ---- маршрут хаба: допуск, /v1/models, дословность ------------------------------------


class TestPassthroughAuthFlagSource(unittest.TestCase):
    def test_default_false_and_env_fallback(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            unittest.mock.patch.dict(
                os.environ,
                {"BRIDGE_DYNAMIC_CONFIG_PATH": str(Path(directory) / "missing.json")},
                clear=True,
            ),
        ):
            source = server._PassthroughAuthFlagSource()
            self.assertFalse(source.enabled())
            for value, expected in (
                ("true", True),
                ("false", False),
                ("invalid", False),
            ):
                with self.subTest(value=value):
                    os.environ[server.PASSTHROUGH_AUTH_FLAG] = value
                    self.assertEqual(source.enabled(), expected)

    def test_snapshot_override_kill_switch_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            with unittest.mock.patch.dict(
                os.environ,
                {
                    "BRIDGE_DYNAMIC_CONFIG_PATH": str(path),
                    server.PASSTHROUGH_AUTH_FLAG: "true",
                },
                clear=True,
            ):
                source = server._PassthroughAuthFlagSource()
                for payload, expected in (
                    ({server.PASSTHROUGH_AUTH_FLAG: True}, True),
                    ({server.PASSTHROUGH_AUTH_FLAG: False}, False),
                    ({}, True),
                    ([], False),
                ):
                    with self.subTest(payload=payload):
                        path.write_text(json.dumps(payload))
                        self.assertEqual(source.enabled(), expected)
                path.write_text("{broken")
                self.assertFalse(source.enabled())

    def test_handler_dual_tolerance_depends_on_flag(self) -> None:
        """Реальный Handler допускает собственный ключ passthrough только при включённом флаге."""
        data = load_raw_fleet()
        data["backends"]["codex"].update(enabled=True, api_key="own-test-key")
        data["backends"]["codex"].pop("api_key_env", None)
        catalog = server._build_catalog(data)
        registry = AdapterRegistry.from_fleet(
            catalog, ADAPTER_KINDS, lambda: catalog, server
        )

        class Connection:
            def __init__(self, request: bytes) -> None:
                self.input = io.BytesIO(request)
                self.output = bytearray()

            def makefile(self, *args: object) -> io.BytesIO:
                return self.input

            def settimeout(self, timeout: float) -> None:
                pass

            def sendall(self, chunk: bytes) -> None:
                self.output.extend(chunk)

        captured_hub_auth: list[bool] = []

        def serve(
            handler: server.Handler,
            adapter: PassthroughAdapter,
            raw: bytes,
            request: dict,
            model: str,
            _hub_auth_ok: bool,
        ) -> None:
            captured_hub_auth.append(_hub_auth_ok)
            handler._send(200, {"accepted": True})

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            with (
                unittest.mock.patch.dict(
                    os.environ, {"BRIDGE_DYNAMIC_CONFIG_PATH": str(path)}, clear=True
                ),
                unittest.mock.patch.object(
                    server,
                    "PASSTHROUGH_AUTH_FLAG_SOURCE",
                    server._PassthroughAuthFlagSource(),
                ),
                unittest.mock.patch.object(server, "FLEET", catalog),
                unittest.mock.patch.object(server, "BACKENDS", registry),
                unittest.mock.patch.object(server, "AUTH_KEY", "hub-test-key"),
                unittest.mock.patch.object(
                    server,
                    "TOKEN_CACHE",
                    server.TokenCache(
                        path=Path(directory) / ".env",
                        environ={"BRIDGE_KEY": "hub-test-key"},
                    ),
                ),
                unittest.mock.patch.object(server, "_budget", None),
                unittest.mock.patch.object(server, "_shutting_down", False),
                unittest.mock.patch.object(server, "_is_drain_enabled", lambda: False),
                unittest.mock.patch.object(
                    server, "_is_detached_enabled", lambda: False
                ),
                unittest.mock.patch.object(server.Handler, "_serve_passthrough", serve),
            ):
                for enabled in (False, True, False):
                    path.write_text(json.dumps({server.PASSTHROUGH_AUTH_FLAG: enabled}))
                    for token, expected in (
                        ("own-test-key", 200 if enabled else 401),
                        ("hub-test-key", 200),
                        ("wrong-key", 401),
                    ):
                        for stream in (False, True):
                            with self.subTest(
                                enabled=enabled, token=token, stream=stream
                            ):
                                captured_hub_auth.clear()
                                body = json.dumps(
                                    {
                                        "model": "gpt-6.1-terra",
                                        "messages": [{"role": "user", "content": "hi"}],
                                        "stream": stream,
                                    }
                                ).encode()
                                headers = [
                                    "POST /v1/chat/completions HTTP/1.1",
                                    "Host: localhost",
                                    "Connection: close",
                                    f"Content-Length: {len(body)}",
                                    f"Authorization: Bearer {token}",
                                ]
                                conn = Connection(
                                    ("\r\n".join(headers) + "\r\n\r\n").encode() + body
                                )
                                # Фейки реализуют используемый Handler протокол без ОС-сокета.
                                server.Handler(
                                    cast(socket.socket, cast(object, conn)),
                                    ("127.0.0.1", 1),
                                    cast(BaseServer, cast(object, SimpleNamespace())),
                                )
                                self.assertEqual(
                                    int(bytes(conn.output).split(b" ", 2)[1]), expected
                                )
                                self.assertEqual(
                                    captured_hub_auth,
                                    [token == "hub-test-key"]
                                    if expected == 200
                                    else [],
                                )
                                if expected == 401:
                                    self.assertEqual(
                                        json.loads(
                                            bytes(conn.output).split(b"\r\n\r\n", 1)[1]
                                        ),
                                        {
                                            "error": {
                                                "message": "unauthorized",
                                                "type": "auth_error",
                                                "code": 401,
                                            }
                                        },
                                    )


class TestHubRoute(BridgeCase):
    HUB_KEY = "test-key"  # BridgeCase.AUTH_KEY

    def setUp(self):
        super().setUp()
        self.upstream = FakeUpstream()
        self.addCleanup(self.upstream.close)
        data = load_raw_fleet()
        data["backends"]["codex"]["enabled"] = True
        data["backends"]["codex"]["base_url"] = (
            "http://127.0.0.1:%d/v1" % self.upstream.port
        )
        # Эти сценарии проверяют прежний контракт без настроенного upstream-ключа.
        data["backends"]["codex"].pop("api_key_env", None)
        server.FLEET = server._build_catalog(data)
        saved = server.BACKENDS
        self.addCleanup(setattr, server, "BACKENDS", saved)
        server.BACKENDS = AdapterRegistry.from_fleet(
            server.FLEET, ADAPTER_KINDS, lambda: server.FLEET, server
        )
        self.upstream.respond = lambda h, b: FakeUpstream.json(
            h,
            {
                "id": "x",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "subagent",
                                        "arguments": '{"prompt":"p","provider":""}',
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    def post(
        self,
        body: dict,
        auth: str | None = "Bearer test-key",
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            headers = {"Content-Type": "application/json"}
            if auth is not None:
                headers["Authorization"] = auth
            headers.update(extra_headers or {})
            conn.request(
                "POST", "/v1/chat/completions", body=json.dumps(body), headers=headers
            )
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def request_body(self, **extra):
        return {
            "model": "gpt-6.1-terra",
            "reasoning_effort": "xhigh",
            "tools": TOOLS,
            "messages": [{"role": "user", "content": "hi"}],
            **extra,
        }

    def test_authorized_request_reserves_body_budget_before_upstream(self):
        budget = server._ByteBudget(1)
        with (
            unittest.mock.patch.object(server, "_budget", budget),
            unittest.mock.patch.object(
                budget, "reserve", wraps=budget.reserve
            ) as reserve,
        ):
            status, _ = self.post(self.request_body())
            self.assertEqual(status, 503)
            reserve.assert_called_once_with(
                len(json.dumps(self.request_body()).encode())
            )
        self.assertEqual(budget._used, 0)
        self.assertEqual(self.upstream.requests, [])

    def test_default_passthrough_requires_explicit_exact_model(self):
        with unittest.mock.patch.object(server, "MODEL_ID", "gpt-6.1-terra"):
            for extra in (
                {},
                {"model": None},
                {"model": ""},
                {"model": " "},
                {"model": " gpt-6.1-terra "},
            ):
                body = {"messages": [{"role": "user", "content": "hi"}], **extra}
                status, _ = self.post(body)
                self.assertIn(status, (400, 401))
        self.assertEqual(self.upstream.requests, [])

    def test_unknown_string_model_is_404(self):
        status, raw = self.post(
            self.request_body(model="unknown-model"), auth="Bearer " + self.HUB_KEY
        )
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(raw)["error"]["type"], "model_not_found")
        self.assertEqual(self.upstream.requests, [])

    def test_passthrough_model_with_hub_key_routes_verbatim_and_sanitizes(self):
        status, raw = self.post(self.request_body())
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(
            args_of(data["choices"][0]["message"]["tool_calls"][0]), {"prompt": "p"}
        )
        sent = self.upstream.requests[0]
        self.assertNotIn("Authorization", sent["headers"])
        body = json.loads(sent["body"])
        self.assertEqual(
            (body["model"], body["reasoning_effort"]), ("gpt-6.1-terra", "xhigh")
        )  # без клампа

    def test_passthrough_model_without_authorization_is_rejected_by_hub(self):
        self.upstream.respond = lambda h, b: FakeUpstream.json(
            h, {"error": {"message": "no key"}}, status=401
        )
        status, raw = self.post(self.request_body(), auth=None)
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(raw)["error"]["message"], "unauthorized")
        self.assertEqual(self.upstream.requests, [])

    def test_hub_key_still_works_for_passthrough_model(self):
        status, _ = self.post(self.request_body(), auth="Bearer " + self.HUB_KEY)
        self.assertEqual(status, 200)

    def configure_upstream_key(self) -> None:
        """Настраивает фиктивный ключ выбранного passthrough-маршрута."""
        server.FLEET["backends"]["codex"]["api_key"] = "config-key"
        server.BACKENDS = AdapterRegistry.from_fleet(
            server.FLEET, ADAPTER_KINDS, lambda: server.FLEET, server
        )

    @unittest.mock.patch(
        "server.PASSTHROUGH_AUTH_FLAG_SOURCE.enabled", return_value=True
    )
    def test_upstream_key_accepted_when_tolerance_flag_enabled(
        self, flag: unittest.mock.Mock
    ) -> None:
        self.configure_upstream_key()
        events = content("ok") + finish(0, "stop") + DONE
        for auth, extra_headers in (
            ("Bearer config-key", {}),
            ("config-key", {}),
            (None, {"x-api-key": "config-key"}),
        ):
            for stream in (False, True):
                with self.subTest(auth=auth, stream=stream):
                    if stream:
                        self.upstream.respond = lambda handler, body: FakeUpstream.sse(
                            handler, events
                        )
                    else:
                        self.upstream.respond = lambda handler, body: FakeUpstream.json(
                            handler, {"ok": True}
                        )
                    status, raw = self.post(
                        self.request_body(stream=stream),
                        auth=auth,
                        extra_headers=extra_headers,
                    )
                    self.assertEqual(status, 200)
                    self.assertTrue(self.upstream.requests)
                    self.upstream.requests.clear()

    def test_dual_tolerance_bridge_key_accepted(self) -> None:
        self.configure_upstream_key()
        status, _ = self.post(self.request_body(), auth="Bearer " + self.HUB_KEY)
        self.assertEqual(status, 200)
        self.assertEqual(
            self.upstream.requests[-1]["headers"]["Authorization"], "Bearer config-key"
        )

    @unittest.mock.patch(
        "server.PASSTHROUGH_AUTH_FLAG_SOURCE.enabled", return_value=False
    )
    def test_disabled_flag_rejects_configured_upstream_key(
        self, flag: unittest.mock.Mock
    ) -> None:
        self.configure_upstream_key()
        for auth, extra_headers in (
            ("Bearer config-key", {}),
            ("config-key", {}),
            (None, {"x-api-key": "config-key"}),
        ):
            for stream in (False, True):
                with self.subTest(auth=auth, stream=stream):
                    status, raw = self.post(
                        self.request_body(stream=stream),
                        auth=auth,
                        extra_headers=extra_headers,
                    )
                    self.assertEqual(status, 401)
                    self.assertEqual(
                        json.loads(raw),
                        {
                            "error": {
                                "message": "unauthorized",
                                "type": "auth_error",
                                "code": 401,
                            }
                        },
                    )
        self.assertEqual(self.upstream.requests, [])

    @unittest.mock.patch(
        "server.PASSTHROUGH_AUTH_FLAG_SOURCE.enabled", return_value=True
    )
    def test_dual_tolerance_invalid_key_rejected_401(
        self, flag: unittest.mock.Mock
    ) -> None:
        self.configure_upstream_key()
        for auth in (None, "Bearer wrong-key", "Bearer ", "wrong-key"):
            for stream in (False, True):
                with self.subTest(auth=auth, stream=stream):
                    status, raw = self.post(self.request_body(stream=stream), auth=auth)
                    self.assertEqual(status, 401)
                    self.assertEqual(
                        json.loads(raw),
                        {
                            "error": {
                                "message": "unauthorized",
                                "type": "auth_error",
                                "code": 401,
                            }
                        },
                    )
        self.assertEqual(self.upstream.requests, [])

    @unittest.mock.patch(
        "server.PASSTHROUGH_AUTH_FLAG_SOURCE.enabled", return_value=True
    )
    def test_dual_tolerance_wrong_backend_key_rejected_401(
        self, flag: unittest.mock.Mock
    ) -> None:
        self.configure_upstream_key()
        other_config = {
            "base_url": f"http://127.0.0.1:{self.upstream.port}/v1",
            "api_key": "other-backend-key",
        }
        server.BACKENDS.register(PassthroughAdapter("other", other_config, dict))
        for stream in (False, True):
            with self.subTest(stream=stream):
                status, raw = self.post(
                    self.request_body(stream=stream), auth="Bearer other-backend-key"
                )
                self.assertEqual(status, 401)
                self.assertEqual(json.loads(raw)["error"]["type"], "auth_error")
        self.assertEqual(self.upstream.requests, [])

    def test_upstream_auth_override_through_hub(self) -> None:
        server.FLEET["backends"]["codex"]["api_key"] = "config-key"
        server.BACKENDS = AdapterRegistry.from_fleet(
            server.FLEET, ADAPTER_KINDS, lambda: server.FLEET, server
        )
        status, raw = self.post(self.request_body(), auth="Bearer " + self.HUB_KEY)
        self.assertEqual(status, 200)
        self.assertEqual(
            self.upstream.requests[-1]["headers"]["Authorization"], "Bearer config-key"
        )
        self.assertEqual(
            args_of(json.loads(raw)["choices"][0]["message"]["tool_calls"][0]),
            {"prompt": "p"},
        )

    def test_unauthorized_with_upstream_key_is_401(self) -> None:
        server.FLEET["backends"]["codex"]["api_key"] = "config-key"
        server.BACKENDS = AdapterRegistry.from_fleet(
            server.FLEET, ADAPTER_KINDS, lambda: server.FLEET, server
        )
        for auth in (None, "Bearer wrong-key"):
            for stream in (False, True):
                with self.subTest(auth=auth, stream=stream):
                    status, raw = self.post(self.request_body(stream=stream), auth=auth)
                    self.assertEqual(status, 401)
                    self.assertEqual(
                        json.loads(raw),
                        {
                            "error": {
                                "message": "unauthorized",
                                "type": "auth_error",
                                "code": 401,
                            }
                        },
                    )
                    self.assertEqual(self.upstream.requests, [])

    def test_other_routes_still_require_hub_key(self):
        status, raw = self.post(
            {"model": server.MODEL_ID, "messages": [{"role": "user", "content": "x"}]},
            auth="Bearer upstream-key",
        )
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(raw)["error"]["type"], "auth_error")
        self.assertEqual(self.upstream.requests, [])

    def test_unknown_path_with_upstream_key_is_401(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(
                "POST",
                "/v1/other",
                body=b"{}",
                headers={"Authorization": "Bearer upstream-key"},
            )
            self.assertEqual(conn.getresponse().status, 401)
        finally:
            conn.close()

    def test_models_listing_rejects_upstream_key_and_includes_passthrough_model_with_hub_key(
        self,
    ):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(
                "GET", "/v1/models", headers={"Authorization": "Bearer upstream-key"}
            )
            resp = conn.getresponse()
            err_data = json.loads(resp.read())
        finally:
            conn.close()
        self.assertEqual(resp.status, 401)
        self.assertEqual(err_data["error"]["type"], "authentication_error")
        self.assertEqual(resp.getheader("WWW-Authenticate"), "Bearer")
        self.assertEqual(self.upstream.requests, [])

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(
                "GET", "/v1/models", headers={"Authorization": f"Bearer {self.HUB_KEY}"}
            )
            resp = conn.getresponse()
            data = json.loads(resp.read())
        finally:
            conn.close()
        self.assertEqual(resp.status, 200)
        ids = [m["id"] for m in data["data"]]
        self.assertIn("gpt-6.1-terra", ids)
        self.assertEqual(self.upstream.requests, [])  # каталог без вызова upstream

    def test_other_get_routes_keep_hub_auth(self):
        status, _ = self._get("/v1/turns/abc", auth=False)
        self.assertEqual(status, 401)

    def test_passthrough_stream_through_hub(self):
        events = (
            tool_delta(
                0, 0, call_id="c", name="subagent", args='{"prompt":"p","provider":""}'
            )
            + finish(0)
            + DONE
        )
        self.upstream.respond = lambda h, b: FakeUpstream.sse(h, events)
        status, raw = self.post(self.request_body(stream=True))
        self.assertEqual(status, 200)
        frames = [line for line in raw.split(b"\n\n") if line]
        calls = published_calls([f + b"\n\n" for f in frames])
        self.assertEqual(args_of(calls[0]), {"prompt": "p"})
        self.assertTrue(raw.endswith(DONE))


class TestHubWithoutPassthrough(BridgeCase):
    def test_default_fleet_keeps_legacy_401_for_upstream_style_key(self):
        data = load_raw_fleet()
        data["backends"]["codex"]["enabled"] = False
        server.FLEET = server._build_catalog(data)
        self.addCleanup(setattr, server, "BACKENDS", server.BACKENDS)
        server.BACKENDS = AdapterRegistry.from_fleet(
            server.FLEET, ADAPTER_KINDS, lambda: server.FLEET, server
        )
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(
                "POST",
                "/v1/chat/completions",
                body=b"{}",
                headers={
                    "Authorization": "Bearer other",
                    "Content-Type": "application/json",
                },
            )
            self.assertEqual(conn.getresponse().status, 401)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()


# ---- ADR-0015 / VER-001: non-stream liveness, конфигурация и окна relay_sse ---------------
import time  # noqa: E402

from core.liveness_signals import LivenessWindow, WindowSpec  # noqa: E402

NONSTREAM_FLAGS = (
    "BRIDGE_NONSTREAM_VIA_STREAM_ENABLED",
    "BRIDGE_NONSTREAM_SOFT_LIVENESS_ENABLED",
    "BRIDGE_NONSTREAM_TELEMETRY_ENABLED",
)


@pytest.fixture
def ns_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    """Изоляция флагов ADR-0015: реальный dynamic_config недоступен, флаги выключены."""
    monkeypatch.setenv(
        "BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "missing-dynamic-config.json")
    )
    for name in NONSTREAM_FLAGS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        server, "TOKEN_CACHE", SimpleNamespace(is_valid=lambda tok: False)
    )
    return monkeypatch


class ScriptedReader:
    """`readline` над расписанием [(пауза_c, байты_кадра)]; после конца ждёт `tail_s` и отдаёт EOF."""

    def __init__(self, script, tail_s: float = 0.0):
        self.stop = threading.Event()
        self.tail_s = tail_s
        self.lines: list = []
        for delay, frame_bytes in script:
            for number, line in enumerate(frame_bytes.splitlines(keepends=True)):
                self.lines.append((delay if number == 0 else 0.0, line))

    def readline(self, _limit: int = -1) -> bytes:
        if not self.lines:
            if self.tail_s:
                self.stop.wait(self.tail_s)
            return b""
        delay, line = self.lines.pop(0)
        if delay:
            self.stop.wait(delay)
        return line


def relay_scripted(script, *, idle: float = 0.3, window=None, tail_s: float = 0.0):
    """relay_sse поверх расписания; heartbeat клиенту отключён, окна мелкие и детерминированные."""
    reader = ScriptedReader(script, tail_s)
    limits = PassthroughLimits(
        idle_timeout_s=idle,
        total_timeout_s=10.0,
        heartbeat_interval_s=30.0,
        poll_interval_s=0.01,
        reader_join_timeout_s=0.05,
    )
    out: list = []
    started = time.monotonic()
    try:
        outcome = relay_sse(
            reader.readline,
            out.append,
            tool_schemas=SCHEMAS,
            limits=limits,
            window=window,
        )
    finally:
        reader.stop.set()
    return outcome, out, time.monotonic() - started


T_FRAMES = [  # всегда транспортный пульс (T): ни при каких флагах не двигает окно простоя
    b": keepalive\n\n",
    b"data: {}\n\n",
    b'data: {"choices":[{"index":0,"delta":{"role":"assistant"}}]}\n\n',
]
NON_JSON_FRAMES = [b"data: keepalive\n\n", b"data: ping\n\n", b"data: {not json\n\n"]


@pytest.mark.parametrize("t_frame", T_FRAMES)
def test_relay_transport_pulse_does_not_shift_idle_window(ns_env, t_frame) -> None:
    script = (
        [(0.0, content("a"))]
        + [(0.1, t_frame)] * 12
        + [(0.0, finish(0, "stop")), (0.0, DONE)]
    )
    with pytest.raises(TimeoutError):
        relay_scripted(script, idle=0.3)


@pytest.mark.parametrize("frame", NON_JSON_FRAMES)
def test_relay_non_json_data_is_t_when_soft_liveness_enabled(ns_env, frame) -> None:
    ns_env.setenv(
        "BRIDGE_NONSTREAM_SOFT_LIVENESS_ENABLED", "true"
    )  # строгая семантика: прогресс только S
    script = [(0.0, content("a"))] + [(0.1, frame)] * 12 + [(0.0, DONE)]
    with pytest.raises(TimeoutError):
        relay_scripted(script, idle=0.3)


@pytest.mark.parametrize(
    "data, shifts",
    [  # F-002: все флаги выключены — семантика `last_progress` идентична базовой ревизии 1d8e96c
        ("{not json", True),
        ("ping", True),
        ("keepalive", True),
        ("  x  ", True),  # непустой не-JSON
        ("", False),
        (None, False),
        ("[DONE]", False),
        ("{}", False),
        ("null", False),
        ('{"choices":[{"index":0,"delta":{"role":"assistant"}}]}', False),
        (
            '{"usage":{"total_tokens":1}}',
            False,
        ),  # кадры без choices/без полезной дельты
        ('{"choices":[{"index":0,"delta":{"content":"a"}}]}', True),
        ('{"choices":[{"index":0,"delta":{"tool_calls":[{"index":0}]}}]}', True),
    ],
)
def test_legacy_flags_off_progress_matches_baseline(ns_env, data, shifts) -> None:
    reader = _TimedSseReader(
        lambda _n: b"", lambda _f: None, PassthroughLimits(), time.monotonic() + 5
    )
    try:
        reader.progress.note(data)
        assert (reader.progress.last_progress is not None) is shifts
    finally:
        reader.close()


@pytest.mark.parametrize("data", ["{not json", "ping", "keepalive", "  x  "])
def test_strict_mode_non_json_does_not_shift_progress(ns_env, data) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_SOFT_LIVENESS_ENABLED", "true")
    reader = _TimedSseReader(
        lambda _n: b"", lambda _f: None, PassthroughLimits(), time.monotonic() + 5
    )
    try:
        reader.progress.note(data)
        assert reader.progress.last_progress is None
    finally:
        reader.close()


@pytest.mark.parametrize("frame", NON_JSON_FRAMES)
def test_relay_legacy_non_json_data_shifts_idle_window_as_baseline(
    ns_env, frame
) -> None:
    script = (
        [(0.0, content("a"))]
        + [(0.1, frame)] * 8
        + [(0.0, finish(0, "stop")), (0.0, DONE)]
    )
    outcome, _, elapsed = relay_scripted(script, idle=0.3)
    assert outcome.done and elapsed > 0.3  # окно скользило, как в базовой ревизии


def test_relay_useful_chunk_shifts_idle_window(ns_env) -> None:
    script = (
        [(0.0, content("a"))]
        + [(0.1, content("b"))] * 8
        + [(0.0, finish(0, "stop")), (0.0, DONE)]
    )
    outcome, out, elapsed = relay_scripted(script, idle=0.3)
    assert outcome.done and not outcome.incomplete
    assert elapsed > 0.3  # суммарное время больше idle: окно скользило
    assert b"".join(out).count(b'"content"') == 9


def test_relay_pre_progress_pulses_do_not_arm_idle_window(ns_env) -> None:
    # До первого S скользящее idle-окно не действует: действует лишь общий дедлайн запроса.
    script = [(0.1, b": keepalive\n\n")] * 5 + [
        (0.0, content("a")),
        (0.0, finish(0, "stop")),
        (0.0, DONE),
    ]
    outcome, _, _ = relay_scripted(script, idle=0.3)
    assert outcome.done


def test_relay_window_receives_signals_s_and_t(ns_env) -> None:
    window = LivenessWindow(
        WindowSpec(first_timeout_s=5.0, idle_timeout_s=5.0, safety_cap_s=30.0)
    )
    events = b": keepalive\n\n" + content("a") + finish(0, "stop") + DONE
    outcome, _ = run_stream(events, window=window)
    snap = window.snapshot()
    assert outcome.done
    assert snap.last_progress_kind == "S"
    assert snap.last_token_age_s is not None
    assert snap.last_keepalive_age_s is not None


def test_relay_window_transport_only_keeps_progress_none(ns_env) -> None:
    window = LivenessWindow(
        WindowSpec(first_timeout_s=5.0, idle_timeout_s=5.0, safety_cap_s=30.0)
    )
    run_stream(b": keepalive\n\n" + b"data: ping\n\n", window=window)
    snap = window.snapshot()
    assert snap.last_progress_kind == "none"
    assert snap.last_token_age_s is None and snap.last_reasoning_age_s is None
    assert snap.last_keepalive_age_s is not None


def test_relay_window_reasoning_only_marks_reasoning_age(ns_env) -> None:
    window = LivenessWindow(
        WindowSpec(first_timeout_s=5.0, idle_timeout_s=5.0, safety_cap_s=30.0)
    )
    reasoning = frame(
        chunk(
            [{"index": 0, "delta": {"reasoning_content": "hm"}, "finish_reason": None}]
        )
    )
    run_stream(reasoning + finish(0, "stop") + DONE, window=window)
    snap = window.snapshot()
    assert snap.last_progress_kind == "S"
    assert snap.last_reasoning_age_s is not None
    assert snap.last_token_age_s is None


def test_relay_without_window_and_flags_off_stays_verbatim(ns_env) -> None:
    events = (
        b": keepalive\n\n"
        + content("a")
        + b"data: {broken\n\n"
        + finish(0, "stop")
        + DONE
    )
    outcome, out = run_stream(events)
    assert b"".join(out) == events
    assert outcome.done


class TestNonstreamFlagOffRegression(SeamCase):
    """VIA_STREAM=false: байты запроса и ответ статического non-stream пути прежние."""

    def completion(self, args):
        return {
            "id": "x",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "subagent",
                                    "arguments": json.dumps(args),
                                },
                            }
                        ],
                    },
                }
            ],
        }

    def run_case(self, flag_value):
        patcher = unittest.mock.patch.dict(
            os.environ,
            {
                "BRIDGE_DYNAMIC_CONFIG_PATH": os.path.join(
                    tempfile.mkdtemp(), "missing.json"
                ),
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in NONSTREAM_FLAGS:
            os.environ.pop(name, None)
        if flag_value is not None:
            os.environ["BRIDGE_NONSTREAM_VIA_STREAM_ENABLED"] = flag_value
        self.upstream.respond = lambda h, b: FakeUpstream.json(
            h, self.completion({"prompt": "p", "provider": ""})
        )
        request = {
            "model": "m",
            "stream": False,
            "tools": TOOLS,
            "messages": [{"role": "user", "content": "hi"}],
        }
        raw = json.dumps(request, indent=2).encode("utf-8")
        return raw, self.call(request, raw=raw)

    def test_request_bytes_and_response_unchanged_when_flag_is_off(self):
        for value in (None, "false", "0", "off", ""):
            with self.subTest(flag=value):
                self.upstream.requests.clear()
                raw, sink = self.run_case(value)
                sent = self.upstream.requests[0]
                self.assertEqual(sent["body"], raw)
                self.assertIs(json.loads(sent["body"])["stream"], False)
                self.assertEqual(sink.status, 200)
                self.assertTrue(
                    sink.header("Content-Type").startswith("application/json")
                )
                self.assertEqual(sink.header("Content-Length"), str(len(sink.body)))
                self.assertIsNone(sink.header("X-Turn-Id"))
                data = json.loads(sink.body)
                self.assertEqual(
                    args_of(data["choices"][0]["message"]["tool_calls"][0]),
                    {"prompt": "p"},
                )


class TestOwnerTokenNotForwardedUpstream(SeamCase):
    """`X-Turn-Owner-Token` — внутренний заголовок моста: upstream его не получает (ADR-0015 / AD-003)."""

    def test_owner_token_header_is_dropped_before_upstream(self):
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, {"ok": True})
        headers = {
            "Authorization": "Bearer upstream-key",
            "X-Turn-Owner-Token": "owner-secret-NOT-REAL",
            "X-Custom": "1",
        }
        sink = self.call({"model": "m"}, headers=headers)
        self.assertEqual(sink.status, 200)
        sent = {k.lower(): v for k, v in self.upstream.requests[0]["headers"].items()}
        self.assertNotIn("x-turn-owner-token", sent)
        self.assertEqual(sent["x-custom"], "1")
