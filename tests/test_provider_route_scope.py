"""W0-02 characterization & Red Repro: provider route scope + suffix/haiku/gate matrix."""

# fmt: off
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
from core import passthrough_effort_map as pem, passthrough_facade as facade  # noqa: E402
from core.backend_adapter import ADAPTER_API, BackendAdapter, BackendModel, BackendNotSupported, Capabilities, Qualification, StreamSink, TurnContext, TurnResult  # noqa: E402
from core.effort_policy import resolve_alias_effort  # noqa: E402
from core.http_post_context import PostRequestContext  # noqa: E402
from core.http_post_routing import PostRoute  # noqa: E402
from core.route_health_policy import RetryBudgetConfig  # noqa: E402
from tests.transport_wire_support import RecordingUpstream, RunningHTTPServer, WireSettings  # noqa: E402

HUB_KEY = "provider-route-scope-test-key"
EFFORT_CASES = (
    ("claude-sonnet-5-5", "claude-sonnet-5-5", "high"), ("claude-sonnet-5-5-low", "claude-sonnet-5-5", "low"),
    ("claude-sonnet-5-5-medium", "claude-sonnet-5-5", "medium"), ("claude-sonnet-5-5-high", "claude-sonnet-5-5", "high"),
    ("claude-opus-5-5", "claude-opus-5-5", "high"), ("claude-opus-5-5-low", "claude-opus-5-5", "low"), ("claude-opus-5-5-high", "claude-opus-5-5", "high"),
)


class _FakeClaudeAdapter(BackendAdapter):
    kind, adapter_api, capabilities = "stdio_resident", ADAPTER_API, Capabilities(sessions="resident", streaming="native")

    def __init__(self, bid: str, cfg: dict[str, Any], cat: Any, on_turn: Callable[[TurnContext, StreamSink | None], TurnResult]) -> None:
        super().__init__(bid, cfg, cat, server)
        self._on_turn = on_turn

    def get_models(self) -> list[BackendModel]: return self._catalog_models()
    def qualify(self) -> Qualification: return Qualification(True, "")
    def is_healthy(self) -> bool: return True
    def spawn_session(self, ctx: TurnContext) -> object: raise BackendNotSupported("none")
    def execute_turn(self, ctx: TurnContext, sse_writer: StreamSink | None) -> TurnResult: return self._on_turn(ctx, sse_writer)
    def close_session(self, sid: str) -> None: return None
    def shutdown(self) -> None: return None


class _Registry:
    def __init__(self, adapters: dict[str, BackendAdapter]) -> None: self._map = adapters
    def get(self, bid: str) -> BackendAdapter | None: return self._map.get(bid)
    def adapters(self) -> list[BackendAdapter]: return list(self._map.values())
    def models(self) -> list[tuple[BackendAdapter, BackendModel]]: return [(a, m) for a in self._map.values() for m in a.get_models()]


def _model_entry(mid: str, efforts: list[str]) -> dict[str, Any]:
    routes = [{"route_id": "claude-p", "backend": "claude-p", "weight": 100, "priority": 10}, {"route_id": "agy", "backend": "agy", "weight": 0, "priority": 20}]
    active = json.dumps([{"backend": "claude-p", "route_id": "claude-p", "weight": 100}], sort_keys=True, separators=(",", ":")).encode()
    return {"id": mid, "backend": "claude-p", "efforts": efforts, "default_effort": "high", "context_window": 200000, "max_tokens": 64000, "input": ["text"], "images": {"status": "unsupported", "method": None}, "routing": {"enabled": True, "algorithm": "weighted-sha256-v1", "catalog_hash": hashlib.sha256(active).hexdigest(), "legacy_backend": "claude-p", "disabled_backend": "claude-p", "routes": routes}}


def _catalog(agy_url: str) -> dict[str, Any]:
    models = {"claude-sonnet-5-5": _model_entry("claude-sonnet-5-5", ["low", "medium", "high", "max"]), "claude-opus-5-5": _model_entry("claude-opus-5-5", ["low", "medium", "high"])}
    backends = {"agy": {"kind": "passthrough", "base_url": agy_url, "enabled": True, "max_concurrent": 1, "owned_by": "agy-bridge"}, "claude-p": {"kind": "stdio_resident", "enabled": True, "owned_by": "claude-p-bridge"}}
    return {"schema": 3, "models": models, "order": ["claude-sonnet-5-5", "claude-opus-5-5"], "backends": backends, "backend_order": ["agy", "claude-p"], "image_limits": {"max_body_bytes": WireSettings().max_body_bytes}}


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("BRIDGE_TRANSPORT_TEST_SEED_ENABLED", "BRIDGE_ROUTING_WEIGHTS_ENABLED", "BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "BRIDGE_CONNECTION_POOLING_ENABLED", "BRIDGE_TELEMETRY_ENABLED", "BRIDGE_RESILIENCE_ENABLED", "BRIDGE_DETACHED_TURNS_ENABLED"):
        monkeypatch.setenv(key, "false")
    monkeypatch.setenv("BRIDGE_TRANSPORT_ROUTING_ENABLED", "true")
    monkeypatch.setattr(facade, "_RUNTIME", facade._RuntimeState())
    facade._begin_retry_request(RetryBudgetConfig(), 1).release_unused()


@contextmanager
def _routed_gateway(monkeypatch: pytest.MonkeyPatch, claude_calls: list[str], on_agy_post: Callable[[RecordingUpstream, Any, bytes], None]) -> Iterator[tuple[int, RecordingUpstream]]:
    def run_claude(_ctx: TurnContext, sse: StreamSink | None) -> TurnResult:
        claude_calls.append("claude-p")
        if sse is not None:
            sse("content", "from-claude")
        return TurnResult(state="done", text="from-claude")

    with RecordingUpstream() as agy_up:
        agy_up.respond = lambda handler, body: on_agy_post(agy_up, handler, body)
        cat = _catalog(agy_up.base_url)
        claude = _FakeClaudeAdapter("claude-p", cat["backends"]["claude-p"], lambda: cat, run_claude)
        agy = PassthroughAdapter("agy", cat["backends"]["agy"], lambda: cat, server)
        for attr, val in {"FLEET": cat, "BACKENDS": _Registry({"agy": agy, "claude-p": claude}), "AUTH_KEY": HUB_KEY, "BRIDGE_KEY": HUB_KEY, "TOKEN_CACHE": server.TokenCache(path=server.ROOT / ".absent-tok.env", environ={"BRIDGE_KEY": HUB_KEY}), "_PENALTY_TRACKER": SimpleNamespace(get_model_status=lambda _m: {"is_penalized": False}, record_start_success=lambda _m: None, record_start_failure=lambda _m, _r: None), "GUARD": SimpleNamespace(snapshot=lambda: ("safe", (), 1 << 20)), "_shutting_down": False, "_is_drain_enabled": lambda: False, "_log": lambda _m: None}.items():
            monkeypatch.setattr(server, attr, val)
        try:
            with RunningHTTPServer(server.Handler) as httpd:
                yield httpd.port, agy_up
        finally:
            agy.shutdown()


def _post_chat(port: int, model: str, *, stream: bool = False) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    body = json.dumps({"model": model, "stream": stream, "messages": [{"role": "user", "content": "ping"}]}).encode("utf-8")
    try:
        conn.request("POST", "/v1/providers/agy/v1/chat/completions", body=body, headers={"Authorization": f"Bearer {HUB_KEY}", "Content-Type": "application/json"})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


@pytest.mark.parametrize("model_id", ["claude-sonnet-5-5", "claude-opus-5-5"])
@pytest.mark.parametrize("stream", [False, True])
def test_provider_agy_routed_selects_only_agy(monkeypatch: pytest.MonkeyPatch, model_id: str, stream: bool) -> None:
    calls: list[str] = []
    respond = (lambda up, h, _b: up.sse(h, b'data: {"id":"a1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"from-agy"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')) if stream else (lambda up, h, _b: up.json(h, {"id": "a1", "object": "chat.completion", "choices": [{"index": 0, "message": {"role": "assistant", "content": "from-agy"}, "finish_reason": "stop"}]}))
    with _routed_gateway(monkeypatch, calls, respond) as (port, agy_up):
        status, raw = _post_chat(port, model_id, stream=stream)
    assert calls == [] and agy_up.post_count == 1 and status == 200 and b"from-agy" in raw


def test_provider_agy_single_route_flag_off_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_TRANSPORT_ROUTING_ENABLED", "false")
    calls: list[str] = []
    with _routed_gateway(monkeypatch, calls, lambda up, h, _b: up.json(h, {"ok": True})) as (port, agy_up):
        status, raw = _post_chat(port, "claude-sonnet-5-5", stream=False)
    err = json.loads(raw).get("error", {})
    assert calls == [] and agy_up.post_count == 0 and status == 503 and "provider_route_unavailable" in (err.get("type"), err.get("code"))


@pytest.mark.parametrize(("provider_id", "routing_on"), [("codex", "true"), ("codex", "false"), ("claude-p", "true"), ("claude-p", "false")])
def test_dispatch_empty_scope_and_unknown_provider_fail_closed(monkeypatch: pytest.MonkeyPatch, provider_id: str, routing_on: str) -> None:
    monkeypatch.setenv("BRIDGE_TRANSPORT_ROUTING_ENABLED", routing_on)
    cat = _catalog("http://127.0.0.1:9887/v1")
    monkeypatch.setattr(server, "FLEET", cat)
    monkeypatch.setattr(server, "BACKENDS", _Registry({"claude-p": _FakeClaudeAdapter("claude-p", cat["backends"]["claude-p"], lambda: cat, lambda *_a: TurnResult())}))
    dispatched: list[str] = []
    monkeypatch.setattr(facade, "dispatch_route", lambda *_a, **_kw: dispatched.append("dispatch_route"))
    monkeypatch.setattr(facade, "_run_routes", lambda *_a, **_kw: dispatched.append("run_routes"))
    rejects: list[tuple[int, str]] = []
    handler = SimpleNamespace(path="/v1/chat/completions", headers={}, connection=None, _trace=None, _reject=lambda code, reason, *_a, **_kw: rejects.append((code, reason)), _reply_error=lambda code, _m, et="invalid_request_error", code_kw=None, **_kw: rejects.append((code, str(code_kw or et))))
    ctx = PostRequestContext(handler, server)
    ctx.provider_id = provider_id
    model = {**cat["models"]["claude-sonnet-5-5"], "routing": {**cat["models"]["claude-sonnet-5-5"]["routing"], "routes": [cat["models"]["claude-sonnet-5-5"]["routing"]["routes"][0]]}}
    facade._dispatch(PostRoute(ctx, {"model": "claude-sonnet-5-5", "messages": [{"role": "user", "content": "hi"}]}, "claude-sonnet-5-5", "claude-sonnet-5-5", 17, model=model))
    assert dispatched == [] and rejects == [(503, "provider_route_unavailable")]


@pytest.mark.parametrize(("raw_model", "base_model", "expected_effort"), EFFORT_CASES)
def test_suffix_and_effort_matrix_reaches_agy_with_reasoning_effort(monkeypatch: pytest.MonkeyPatch, raw_model: str, base_model: str, expected_effort: str) -> None:
    cat = _catalog("http://127.0.0.1:9887/v1")
    alias = resolve_alias_effort(raw_model, cat["models"], server.EFFORT_SUFFIXES, True)
    resolved_base = alias[0] if alias else raw_model
    assert resolved_base == base_model and pem.logical_effort({}, alias[1] if alias else None, cat["models"][resolved_base]) == expected_effort
    calls: list[str] = []
    with _routed_gateway(monkeypatch, calls, lambda up, h, _b: up.json(h, {"id": "a1", "object": "chat.completion", "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]})) as (port, agy_up):
        status, _raw = _post_chat(port, raw_model, stream=False)
    sent = json.loads(agy_up.requests[0].body) if agy_up.requests else {}
    assert calls == [] and agy_up.post_count == 1 and status == 200 and sent.get("model") == base_model and sent.get("reasoning_effort") == expected_effort


def test_thinking_suffix_not_in_hub_effort_suffixes(monkeypatch: pytest.MonkeyPatch) -> None:
    cat = _catalog("http://127.0.0.1:9887/v1")
    assert "thinking" not in server.EFFORT_SUFFIXES and resolve_alias_effort("claude-sonnet-5-5-thinking", cat["models"], server.EFFORT_SUFFIXES, True) is None
    calls: list[str] = []
    with _routed_gateway(monkeypatch, calls, lambda up, h, _b: up.json(h, {"ok": True})) as (port, agy_up):
        status, raw = _post_chat(port, "claude-sonnet-5-5-thinking", stream=False)
    assert calls == [] and agy_up.post_count == 0 and status == 404 and json.loads(raw)["error"]["type"] == "model_not_found"


def test_haiku_stays_on_opencode_go_claude_without_agy_route() -> None:
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    haiku = next(item for item in fleet["models"] if item["id"] == "claude-haiku-5-5")
    assert haiku["backend"] == "opencode-go-claude" and all(r.get("backend") != "agy" and r.get("route_id") != "agy" for r in haiku.get("routing", {}).get("routes", []))


@pytest.mark.parametrize("upstream_status", [404, 403, 503])
def test_agy_gate_disabled_error_returned_without_fallback(monkeypatch: pytest.MonkeyPatch, upstream_status: int) -> None:
    calls: list[str] = []
    with _routed_gateway(monkeypatch, calls, lambda up, h, _b: up.json(h, {"error": {"type": "upstream_error", "code": "agy_anthropic_disabled", "message": "disabled"}}, status=upstream_status)) as (port, agy_up):
        status, raw = _post_chat(port, "claude-sonnet-5-5", stream=False)
    assert calls == [] and agy_up.post_count == 1 and status == upstream_status and b"agy_anthropic_disabled" in raw
# fmt: on


def _fake_route(provider_id: str | None, backend: str = "claude-p", backends: dict[str, Any] | None = None) -> tuple[Any, list[tuple[int, str, str]]]:
    rejects: list[tuple[int, str, str]] = []
    default_backends: dict[str, Any] = {"agy": SimpleNamespace(id="agy", owned_by="agy-bridge")}
    host = SimpleNamespace(PROVIDER_SCOPES={"agy": ("agy-bridge",)}, BACKENDS=default_backends if backends is None else backends)
    route = SimpleNamespace(ingress=SimpleNamespace(provider_id=provider_id), host=host, model={"backend": backend}, reject=lambda c, r, m: rejects.append((c, r, m)) or False)
    return route, rejects


def test_unit_backend_matches_provider_scopes_and_fail_closed() -> None:
    from core.provider_route_scope import backend_matches_provider

    scopes = {"agy": ("agy-bridge",)}
    backends = {
        "own": SimpleNamespace(owned_by="agy-bridge"),
        "prv": SimpleNamespace(config={"provider": "agy-bridge"}),
        "cfg": SimpleNamespace(config={"owned_by": "agy-bridge"}),
        "claude-p": SimpleNamespace(owned_by="claude-p-bridge"),
    }
    assert backend_matches_provider("claude-p", None, scopes, backends) is True
    for bid in ("agy-bridge", "own", "prv", "cfg"):
        assert backend_matches_provider(bid, "agy", scopes, backends) is True
    assert backend_matches_provider("agy", "agy", scopes, backends) is False
    assert backend_matches_provider("claude-p", "agy", scopes, backends) is False
    assert backend_matches_provider("claude-p", "claude-p", scopes, backends) is False
    assert backend_matches_provider("", "", scopes, backends) is False
    assert backend_matches_provider("agy", "agy", {"agy": ()}, backends) is False
    assert backend_matches_provider("agy", "agy", {"agy": {"agy-bridge": 1}}, backends) is False  # type: ignore[dict-item]
    assert backend_matches_provider("", "agy", {"agy": ""}, backends) is False
    assert backend_matches_provider("agy", "agy", {"agy": None}, backends) is False  # type: ignore[dict-item]
    assert backend_matches_provider("claude-p", "claude-p", {"claude-p": ("agy",)}, backends) is False


def test_unit_scope_routes_preserves_unscoped_and_fails_closed() -> None:
    from core.provider_route_scope import scope_routes

    scopes = {"agy": ("agy-bridge",)}
    rc, ra, rn = SimpleNamespace(backend="claude-p"), SimpleNamespace(backend="agy-c"), SimpleNamespace(backend=None)
    backends = {"agy-c": SimpleNamespace(config={"provider": "agy-bridge"})}
    assert scope_routes([rc, ra], None, scopes, backends) == (rc, ra)
    assert scope_routes([rc, ra, rn], "agy", scopes, backends) == (ra,)
    assert scope_routes([rc, ra], "claude-p", scopes, backends) == ()


def test_unit_filter_dispatch_routes_scope_and_rejects() -> None:
    from core.provider_route_scope import filter_dispatch_routes

    rc, ra = SimpleNamespace(backend="claude-p"), SimpleNamespace(backend="agy")
    r0, j0 = _fake_route(None)
    assert filter_dispatch_routes(r0, ()) is None and j0[0][:2] == (
        503,
        "route_unavailable",
    )
    r1, j1 = _fake_route(None)
    assert filter_dispatch_routes(r1, [rc, ra]) == (rc, ra) and j1 == []
    for pid in ("agy", "claude-p"):
        r_bad, j_bad = _fake_route(pid)
        assert filter_dispatch_routes(r_bad, [rc]) is None
        assert j_bad[0][:2] == (503, "provider_route_unavailable")
    r4, j4 = _fake_route("agy")
    assert filter_dispatch_routes(r4, [rc, ra]) == (ra,) and j4 == []


def test_unit_single_route_provider_allowed_and_dispatch_scoped_single() -> None:
    from core.provider_route_scope import (
        dispatch_scoped_single,
        single_route_provider_allowed,
    )

    rb, jb = _fake_route("agy", backend="claude-p")
    assert single_route_provider_allowed(rb, "claude-p") is False
    assert jb[0][:2] == (503, "provider_route_unavailable")
    ru, ju = _fake_route("claude-p", backend="claude-p")
    assert single_route_provider_allowed(ru) is False
    assert ju[0][:2] == (503, "provider_route_unavailable")
    ro, jo = _fake_route("agy", backend="agy")
    assert single_route_provider_allowed(ro) is True and jo == []

    sent: list[tuple[Any, Any]] = []
    rdb, jdb = _fake_route("agy", backend="claude-p")
    dispatch_scoped_single(
        rdb,
        {"disabled_backend": "claude-p"},
        lambda r, _a, b: (r, b),
        lambda _r: {"b": 1},
        lambda r, w: sent.append((r, w)),
    )
    assert sent == [] and jdb[0][:2] == (503, "provider_route_unavailable")
    rdo, jdo = _fake_route("agy", backend="claude-p", backends={"agy": SimpleNamespace(id="agy", owned_by="agy-bridge")})
    dispatch_scoped_single(
        rdo,
        {"disabled_backend": "agy"},
        lambda r, a, b: (r, (a.id, b)),
        lambda _r: {"b": 2},
        lambda r, w: sent.append((r.model["backend"], w)),
    )
    assert jdo == [] and sent == [("agy", ("agy", {"b": 2}))]
