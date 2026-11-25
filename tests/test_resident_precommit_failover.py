"""W0-01 characterization & Red Repro: pre-commit ResidentTurnError failover."""

from __future__ import annotations

import hashlib
import http.client
import json
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from adapters.passthrough_adapter import PassthroughAdapter  # noqa: E402
from core import passthrough_facade as facade  # noqa: E402
from core.backend_adapter import (  # noqa: E402
    ADAPTER_API, BackendAdapter, BackendModel, BackendNotSupported,
    Capabilities, Qualification, StreamSink, TurnContext, TurnResult,
)
from core.route_attempts import AttemptPhase, AttemptState  # noqa: E402
from core.route_health_policy import RetryBudgetConfig  # noqa: E402
from core.stdio_resident.turn_error_sse import (  # noqa: E402
    DONE_FRAME, ResidentTurnError, TurnErrorResponse,
)
from tests.transport_wire_support import (  # noqa: E402
    RecordingUpstream, RunningHTTPServer, WireSettings,
)

HUB_KEY = "resident-failover-test-key"
MODEL_ID = "claude-sonnet-5-5"


def _resident_error(status: int, code: str, message: str = "resident failed") -> ResidentTurnError:
    body: dict[str, object] = {"error": {"message": message, "type": "upstream_error", "code": code}}
    sse = "data: " + json.dumps(body, ensure_ascii=False) + "\n\n" + DONE_FRAME
    return ResidentTurnError(TurnErrorResponse(status, "upstream_error", code, message, sse, body))


class _FakeClaudeAdapter(BackendAdapter):
    kind = "stdio_resident"
    adapter_api = ADAPTER_API
    capabilities = Capabilities(sessions="resident", streaming="native")

    def __init__(self, backend_id: str, config: dict[str, Any], catalog_source: Any, on_turn: Callable[[TurnContext, StreamSink | None], TurnResult]) -> None:
        super().__init__(backend_id, config, catalog_source, server)
        self._on_turn = on_turn

    def get_models(self) -> list[BackendModel]:
        return self._catalog_models()

    def qualify(self) -> Qualification:
        return Qualification(True, "")

    def is_healthy(self) -> bool:
        return True

    def spawn_session(self, ctx: TurnContext) -> object:
        raise BackendNotSupported("none")

    def execute_turn(self, ctx: TurnContext, sse_writer: StreamSink | None) -> TurnResult:
        return self._on_turn(ctx, sse_writer)

    def close_session(self, sid: str) -> None:
        return None

    def shutdown(self) -> None:
        return None


class _Registry:
    def __init__(self, adapters: dict[str, BackendAdapter]) -> None:
        self._map = adapters

    def get(self, backend_id: str) -> BackendAdapter | None:
        return self._map.get(backend_id)

    def adapters(self) -> list[BackendAdapter]:
        return list(self._map.values())

    def models(self) -> list[tuple[BackendAdapter, BackendModel]]:
        return [(a, m) for a in self._map.values() for m in a.get_models()]


def _catalog(agy_url: str) -> dict[str, Any]:
    routes = [
        {"route_id": "claude-p", "backend": "claude-p", "weight": 100, "priority": 10},
        {"route_id": "agy", "backend": "agy", "weight": 0, "priority": 20},
    ]
    active = json.dumps([{"backend": "claude-p", "route_id": "claude-p", "weight": 100}], sort_keys=True, separators=(",", ":")).encode()
    model = {
        "id": MODEL_ID, "backend": "claude-p", "efforts": ["low", "medium", "high", "max"],
        "default_effort": "high", "context_window": 200000, "max_tokens": 64000, "input": ["text"],
        "images": {"status": "unsupported", "method": None},
        "routing": {
            "enabled": True, "algorithm": "weighted-sha256-v1",
            "catalog_hash": hashlib.sha256(active).hexdigest(),
            "legacy_backend": "claude-p", "disabled_backend": "claude-p", "routes": routes,
        },
    }
    backends = {
        "claude-p": {"kind": "stdio_resident", "enabled": True, "owned_by": "claude-p-bridge"},
        "agy": {"kind": "passthrough", "base_url": agy_url, "enabled": True, "max_concurrent": 1, "owned_by": "agy-bridge"},
    }
    return {
        "schema": 3, "models": {MODEL_ID: model}, "order": [MODEL_ID],
        "backends": backends, "backend_order": ["claude-p", "agy"],
        "image_limits": {"max_body_bytes": WireSettings().max_body_bytes},
    }


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "BRIDGE_TRANSPORT_ROUTING_ENABLED": "true",
        "BRIDGE_TRANSPORT_TEST_SEED_ENABLED": "false",
        "BRIDGE_ROUTING_WEIGHTS_ENABLED": "false",
        "BRIDGE_NONSTREAM_VIA_STREAM_ENABLED": "false",
        "BRIDGE_CONNECTION_POOLING_ENABLED": "false",
        "BRIDGE_PASSTHROUGH_PRESEND_MAX_RETRIES": "1",
        "BRIDGE_PASSTHROUGH_PRESEND_RETRY_DELAY_S": "0.001",
        "BRIDGE_PASSTHROUGH_PRESEND_RETRY_MAX_DELAY_S": "0.001",
        "BRIDGE_TELEMETRY_ENABLED": "false",
        "BRIDGE_RESILIENCE_ENABLED": "false",
        "BRIDGE_DETACHED_TURNS_ENABLED": "false",
    }
    for key, val in env.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setattr(facade, "_RUNTIME", facade._RuntimeState())
    facade._begin_retry_request(RetryBudgetConfig(), 1).release_unused()
    assert facade._RUNTIME.bucket is not None
    for _ in range(4):
        facade._RUNTIME.bucket.admit_primary()


@contextmanager
def _routed_gateway(
    monkeypatch: pytest.MonkeyPatch,
    on_claude_turn: Callable[[TurnContext, StreamSink | None], TurnResult],
    on_agy_post: Callable[[RecordingUpstream, Any, bytes], None],
) -> Iterator[tuple[int, RecordingUpstream]]:
    with RecordingUpstream() as agy_upstream:
        agy_upstream.respond = lambda handler, body: on_agy_post(agy_upstream, handler, body)
        catalog = _catalog(agy_upstream.base_url)
        claude = _FakeClaudeAdapter("claude-p", catalog["backends"]["claude-p"], lambda: catalog, on_claude_turn)
        agy = PassthroughAdapter("agy", catalog["backends"]["agy"], lambda: catalog, server)
        monkeypatch.setattr(server, "FLEET", catalog)
        monkeypatch.setattr(server, "BACKENDS", _Registry({"claude-p": claude, "agy": agy}))
        monkeypatch.setattr(server, "AUTH_KEY", HUB_KEY)
        monkeypatch.setattr(server, "BRIDGE_KEY", HUB_KEY)
        monkeypatch.setattr(server, "TOKEN_CACHE", server.TokenCache(path=server.ROOT / ".absent-tok.env", environ={"BRIDGE_KEY": HUB_KEY}))
        monkeypatch.setattr(server, "_PENALTY_TRACKER", SimpleNamespace(get_model_status=lambda _m: {"is_penalized": False}, record_start_success=lambda _m: None, record_start_failure=lambda _m, _r: None))
        monkeypatch.setattr(server, "GUARD", SimpleNamespace(snapshot=lambda: ("safe", (), 1 << 20)))
        monkeypatch.setattr(server, "_shutting_down", False)
        monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
        monkeypatch.setattr(server, "_log", lambda _m: None)
        try:
            with RunningHTTPServer(server.Handler) as httpd:
                yield httpd.port, agy_upstream
        finally:
            agy.shutdown()


def _post_chat(port: int, *, stream: bool) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    payload = json.dumps({"model": MODEL_ID, "stream": stream, "messages": [{"role": "user", "content": "ping"}]}).encode("utf-8")
    headers = {"Authorization": f"Bearer {HUB_KEY}", "Content-Type": "application/json"}
    try:
        conn.request("POST", "/v1/chat/completions", body=payload, headers=headers)
        resp = conn.getresponse()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
    finally:
        conn.close()


def _agy_json_ok(up: RecordingUpstream, handler: Any, _body: bytes) -> None:
    up.json(handler, {"id": "agy-1", "object": "chat.completion", "choices": [{"index": 0, "message": {"role": "assistant", "content": "from-agy"}, "finish_reason": "stop"}]})


def _agy_sse_ok(up: RecordingUpstream, handler: Any, _body: bytes) -> None:
    up.sse(handler, b'data: {"id":"agy-sse-1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"from-agy"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')


def test_json_precommit_resident_502_fails_over_to_agy(monkeypatch: pytest.MonkeyPatch) -> None:
    claude_calls: list[str] = []

    def fail_claude(_ctx: TurnContext, _sse: StreamSink | None) -> TurnResult:
        claude_calls.append("claude-p")
        raise _resident_error(502, "resident_dispatch_failed", "claude dispatch failed")

    with _routed_gateway(monkeypatch, fail_claude, _agy_json_ok) as (port, agy_up):
        status, _hdrs, raw = _post_chat(port, stream=False)
    assert claude_calls == ["claude-p"] and agy_up.post_count == 1 and status == 200
    assert json.loads(raw)["choices"][0]["message"]["content"] == "from-agy"


@pytest.mark.parametrize("mode", ["committed", "headers_sent"])
def test_json_postcommit_never_fails_over(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    claude_calls: list[str] = []

    def fail_postcommit(ctx: TurnContext, _sse: StreamSink | None) -> TurnResult:
        claude_calls.append(mode)
        handler: Any = ctx.handler
        if mode == "committed":
            attempt = getattr(handler, "_transport_attempt", None)
            assert attempt is not None
            attempt.advance_to(AttemptPhase.COMMITTED)
        else:
            handler._send(200, {"id": "early-commit", "choices": []})
            handler._headers_already_sent = True
        raise _resident_error(502, "resident_dispatch_failed", "post-commit failure")

    with _routed_gateway(monkeypatch, fail_postcommit, _agy_json_ok) as (port, agy_up):
        status, _hdrs, _raw = _post_chat(port, stream=False)
    assert claude_calls == [mode] and agy_up.post_count == 0
    assert status == (502 if mode == "committed" else 200)


def test_json_exhausted_routes_returns_terminal_error(monkeypatch: pytest.MonkeyPatch) -> None:
    claude_calls: list[str] = []

    def fail_claude(_ctx: TurnContext, _sse: StreamSink | None) -> TurnResult:
        claude_calls.append("claude-p")
        raise _resident_error(502, "resident_dispatch_failed", "claude down")

    def fail_agy(up: RecordingUpstream, handler: Any, _body: bytes) -> None:
        up.json(handler, {"error": {"type": "upstream_error", "code": "agy_down", "message": "agy down"}}, status=502)

    with _routed_gateway(monkeypatch, fail_claude, fail_agy) as (port, agy_up):
        status, _hdrs, raw = _post_chat(port, stream=False)
    assert claude_calls == ["claude-p"] and agy_up.post_count == 1
    assert status == 502 and "error" in json.loads(raw)


def test_stream_precommit_resident_502_fails_over_to_agy(monkeypatch: pytest.MonkeyPatch) -> None:
    claude_calls: list[str] = []

    def fail_claude_prechunk(_ctx: TurnContext, _sse: StreamSink | None) -> TurnResult:
        claude_calls.append("claude-p")
        raise _resident_error(502, "resident_turn_failed", "pre-chunk resident error")

    with _routed_gateway(monkeypatch, fail_claude_prechunk, _agy_sse_ok) as (port, agy_up):
        status, hdrs, raw = _post_chat(port, stream=True)
    assert claude_calls == ["claude-p"] and agy_up.post_count == 1
    assert status == 200 and "text/event-stream" in hdrs.get("content-type", "")
    assert b"from-agy" in raw and b"data: [DONE]" in raw
    assert b"HTTP/1." not in raw and b"Content-Type:" not in raw


def test_stream_postcommit_after_live_chunk_never_fails_over(monkeypatch: pytest.MonkeyPatch) -> None:
    claude_calls: list[str] = []

    def fail_after_live_chunk(_ctx: TurnContext, sse_writer: StreamSink | None) -> TurnResult:
        claude_calls.append("claude-p")
        assert sse_writer is not None and sse_writer("content", "partial-chunk") is True
        raise _resident_error(502, "resident_turn_failed", "mid-stream resident error")

    with _routed_gateway(monkeypatch, fail_after_live_chunk, _agy_sse_ok) as (port, agy_up):
        status, hdrs, raw = _post_chat(port, stream=True)
    assert claude_calls == ["claude-p"] and agy_up.post_count == 0
    assert status == 200 and "text/event-stream" in hdrs.get("content-type", "")
    assert b"partial-chunk" in raw and b"resident_turn_failed" in raw and raw.count(b"data: [DONE]") == 1


def test_replay_gate_allows_precommit_502_with_default_effort() -> None:
    route = SimpleNamespace(
        model_id=MODEL_ID, model={"default_effort": "high"},
        request={"model": MODEL_ID, "messages": [{"role": "user", "content": "ping"}]},
        alias_effort=None, handler=SimpleNamespace(path="/v1/chat/completions"),
    )
    state = AttemptState(phase=AttemptPhase.RESPONSE_HEADERS, body_sent=False, committed=False, status_code=502)
    assert facade._replay_gate(route, state, RetryBudgetConfig()) is True
