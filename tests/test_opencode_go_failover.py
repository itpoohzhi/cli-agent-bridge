"""Multi-slot failover OpenCode Go: per-provider 403/402 и сводный 429."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters import ADAPTER_KINDS
from adapters.passthrough_adapter import PassthroughAdapter, PassthroughLimits, ResponseSink
from core.fleet_compiler import backend_entry
from core.passthrough_adapter_runtime import PassthroughRouteRefusal
from core.provider_manifest import read_yaml_file, validate_manifest
from core.presend_retry_policy import resolve_presend_response
from core.route_attempts import (
    AttemptPhase,
    RouteAttemptRunner,
    RouteFailover,
    RouteRefusal,
    build_pool_exhausted_error,
    decide_attempt,
    is_route_refusal_status,
)
from core.route_health_policy import RetryBudgetConfig

ROOT = Path(__file__).resolve().parents[1]
GO_TYPES = ("permission_error", "credit_exhausted", "payment_required")
GO_MARKERS = ("credit", "subscription", "usage limit", "go usage", "payment")
GO_EXTRA = {"extra_statuses": (402, 403), "extra_error_types": GO_TYPES,
            "message_markers": GO_MARKERS}
GO_FAILOVER = RouteFailover(
    statuses=frozenset({402, 403}), error_types=frozenset(GO_TYPES),
    message_markers=GO_MARKERS, pool="opencode-go", pool_label="OpenCode Go",
)
SUB1_403 = b'{"error":{"type":"permission_error","message":"subscription required"}}'
FORBIDDEN_MODEL_403 = b'{"error":{"type":"internal_model_forbidden","message":"model forbidden"}}'


def _budget() -> RetryBudgetConfig:
    return RetryBudgetConfig(total_budget_s=20, reserve_s=2, min_attempt_budget_s=1,
                             max_attempts=3, idle_timeout_s=5)


def _outcome(status: int) -> dict[str, Any]:
    return {"status_code": status, "phase": "RESPONSE_HEADERS", "body_sent": True, "committed": False}


# ---- классификатор отказов ----------------------------------------------------


@pytest.mark.parametrize(("status", "body", "expected"), [
    (403, SUB1_403, True),
    (403, b'{"error":{"type":"credit_exhausted","message":"no credits left"}}', True),
    (402, b'{"error":{"type":"payment_required","message":"pay"}}', True),
    (403, FORBIDDEN_MODEL_403, False),
    (403, b'{"error":{"type":"permission_error"}}', True),
    (429, b"{}", True),
    (200, b"{}", False),
])
def test_go_refusal_classified_per_provider(status: int, body: bytes, expected: bool) -> None:
    assert is_route_refusal_status(status, body, **GO_EXTRA) is expected


@pytest.mark.parametrize("status", [402, 403])
def test_without_provider_opt_in_402_403_are_not_failover(status: int) -> None:
    assert is_route_refusal_status(status, SUB1_403) is False
    assert decide_attempt(_budget(), 1, 0.0, _outcome(status)).allow_retry is False


def test_decide_attempt_allows_go_403_only_with_extra_statuses() -> None:
    assert decide_attempt(_budget(), 1, 0.0, _outcome(403), extra_statuses=(402, 403)).allow_retry is True
    assert decide_attempt(_budget(), 1, 0.0, _outcome(403), extra_statuses=()).allow_retry is False
    # Per-route контракт: исход судит failover именно отказавшего маршрута.
    assert decide_attempt(_budget(), 1, 0.0, _outcome(403), failover=GO_FAILOVER).allow_retry is True
    assert decide_attempt(_budget(), 1, 0.0, _outcome(402), failover=RouteFailover()).allow_retry is False


def test_markers_are_declarative_not_global_heuristics() -> None:
    body = b'{"error":{"type":"other_error","message":"Subscription required"}}'
    # Без объявленных маркеров ядро чужих эвристик не применяет (раньше — True).
    assert is_route_refusal_status(403, body, extra_statuses=(403,),
                                   extra_error_types=("permission_error",)) is False
    assert is_route_refusal_status(403, body, extra_statuses=(403,),
                                   message_markers=("subscription",)) is True
    # 402 не форсируется ядром вопреки объявленным типам/маркерам маршрута.
    assert is_route_refusal_status(
        402, b'{"error":{"type":"other_error","message":"nope"}}', **GO_EXTRA) is False


# ---- runner: sub1 (403) -> sub2 (успех), тест 1 и 3 ---------------------------


class _Clock:
    def __call__(self) -> float:
        return 0.0


def _runner(execute: Callable[[str, Any], Any], backends: list[str]) -> RouteAttemptRunner:
    lease = SimpleNamespace(finish=lambda *a: None, close=lambda: None)
    ports = SimpleNamespace(
        ready=lambda _: True, acquire=lambda *_: lease, execute=execute,
        retry_token=lambda: True, cancelled=lambda: False,
    )
    per_route = {backend: GO_FAILOVER for backend in backends
                 if backend.startswith("opencode-go-")}
    return RouteAttemptRunner(backends, ports, _budget(), _Clock(),
                              failover_by_backend=per_route)


def test_runner_fails_over_from_sub1_403_to_sub2() -> None:
    seen: list[str] = []

    def execute(backend: str, attempt: Any) -> Any:
        seen.append(backend)
        attempt.advance(AttemptPhase.SENDING)
        if backend == "opencode-go-sub1":
            attempt.advance(AttemptPhase.RESPONSE_HEADERS, 403)
            raise RouteRefusal(403, (), SUB1_403)
        return "ok-sub2"

    assert _runner(execute, ["opencode-go-sub1", "opencode-go-sub2"]).run() == "ok-sub2"
    assert seen == ["opencode-go-sub1", "opencode-go-sub2"]


def test_runner_mixed_model_non_opt_in_backend_is_not_failed_over() -> None:
    seen: list[str] = []

    def execute(backend: str, attempt: Any) -> Any:
        seen.append(backend)
        attempt.advance(AttemptPhase.SENDING)
        attempt.advance(AttemptPhase.RESPONSE_HEADERS, 402)
        raise RouteRefusal(402, (), b'{"error":{"type":"payment_required","message":"pay"}}')

    with pytest.raises(RouteRefusal):
        _runner(execute, ["deepseek-direct", "opencode-go-sub1"]).run()
    # Non-opt-in бэкенд смешанной модели не наследует {402, 403} соседа по пулу.
    assert seen == ["deepseek-direct"]


def test_runner_returns_first_slot_200_without_second_attempt() -> None:
    seen: list[str] = []

    def execute(backend: str, attempt: Any) -> Any:
        seen.append(backend)
        return "ok-sub1"

    assert _runner(execute, ["opencode-go-sub1", "opencode-go-sub2"]).run() == "ok-sub1"
    assert seen == ["opencode-go-sub1"]


# ---- сводный 429 при исчерпании пула, тест 2 ----------------------------------


def test_pool_exhausted_is_composite_429_without_masked_lexicon() -> None:
    refusals = [
        ("opencode-go-sub1", RouteRefusal(403, (("Retry-After", "120"),), SUB1_403)),
        ("opencode-go-sub2", RouteRefusal(402, (), b'{"error":{"type":"payment_required","message":"insufficient quota"}}')),
    ]
    status, headers, body = build_pool_exhausted_error(refusals, pool_label="OpenCode Go")
    payload = json.loads(body)
    message = payload["error"]["message"]
    assert status == 429
    assert "OpenCode Go" in message
    assert payload["error"]["type"] == "rate_limit_error"
    assert "opencode-go-sub1" in message and "403" in message
    assert "opencode-go-sub2" in message and "402" in message
    lowered = (message + payload["error"]["type"]).lower()
    for forbidden in ("permission_error", "authentication_error", "insufficient quota",
                      "insufficient balance", "quota exhausted", "out of credits"):
        assert forbidden not in lowered
    assert dict(headers)["Retry-After"] == "120"


# ---- адаптер: 403 permission_error становится отказом маршрута -----------------


class _Upstream:
    def __init__(self, status: int, body: bytes) -> None:
        outer = self
        self.requests = 0

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: Any) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                outer.requests += 1
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = int(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class _Sink(ResponseSink):
    def __init__(self) -> None:
        self.status: int | None = None
        self.headers: list[tuple[str, str]] = []
        self.chunks: list[bytes] = []
        self.accepts_presend_errors = True

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        self.status, self.headers = status, headers

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    @property
    def body(self) -> bytes:
        return b"".join(self.chunks)


def _adapter(port: int, backend_id: str) -> PassthroughAdapter:
    return PassthroughAdapter(
        backend_id,
        {"kind": "passthrough", "base_url": f"http://127.0.0.1:{port}/v1",
         "max_concurrent": 2, "failover_statuses": [402, 403],
         "failover_error_types": ["permission_error", "credit_exhausted"]},
        lambda: {}, limits=PassthroughLimits(), sanitize=False,
    )


def _call(adapter: PassthroughAdapter, sink: _Sink) -> _Sink:
    adapter.handle(path="/v1/chat/completions", raw_body=b'{"stream":false}',
                   request={"stream": False}, headers={}, sink=sink)
    return sink


def test_adapter_sub1_403_raises_refusal_then_sub2_200_succeeds() -> None:
    dead, alive = _Upstream(403, SUB1_403), _Upstream(200, b'{"choices":[{"message":{"content":"ok"}}]}')
    sub1, sub2 = _adapter(dead.port, "opencode-go-sub1"), _adapter(alive.port, "opencode-go-sub2")
    try:
        with pytest.raises(PassthroughRouteRefusal) as raised:
            _call(sub1, _Sink())
        assert raised.value.status_code == 403
        assert raised.value.response_body == SUB1_403
        sink = _call(sub2, _Sink())
        assert sink.status == 200
        assert b'"ok"' in sink.body
        assert (dead.requests, alive.requests) == (1, 1)
    finally:
        sub1.shutdown()
        sub2.shutdown()
        dead.close()
        alive.close()


def test_adapter_non_go_403_is_forwarded_not_replayed() -> None:
    upstream = _Upstream(403, FORBIDDEN_MODEL_403)
    adapter = _adapter(upstream.port, "opencode-go-sub1")
    try:
        sink = _call(adapter, _Sink())
        assert sink.status == 403
        assert sink.body == FORBIDDEN_MODEL_403
        assert upstream.requests == 1
    finally:
        adapter.shutdown()
        upstream.close()


# ---- фасад: per-route изоляция и пул в `_run_routes`, presend-контракт ---------


def _facade_run(monkeypatch: pytest.MonkeyPatch, outcomes: dict[str, int]) -> tuple[list[str], Any]:
    from core import passthrough_facade as facade

    seen: list[str] = []
    sink = SimpleNamespace(status=None, payload=b"")
    sink.start = lambda status, headers: setattr(sink, "status", status)
    sink.write = lambda data: setattr(sink, "payload", sink.payload + data)
    go_config = {"failover_statuses": [402, 403], "failover_error_types": list(GO_TYPES),
                 "failover_message_markers": list(GO_MARKERS),
                 "failover_pool": "opencode-go", "failover_pool_label": "OpenCode Go"}
    backends = {name: SimpleNamespace(config=dict(go_config) if name.startswith("opencode-go-") else {})
                for name in outcomes}
    host = SimpleNamespace(
        BACKENDS=backends, _client_gone=lambda conn: False,
        _HandlerSink=lambda handler, extra_headers=None: sink,
        _trace_headers=lambda trace: [],
    )
    handler = SimpleNamespace(connection=object(), _trace=SimpleNamespace(subagent_id=None))
    route = SimpleNamespace(
        host=host, handler=handler, model_id="deepseek-v4.1-flash",
        model={"backend": next(iter(outcomes)), "routing": {}},
        reject=lambda *args: setattr(sink, "status", args[0]),
    )

    def attempt_fn(route_: Any, spec: Any, body: Any, attempt: Any) -> None:
        seen.append(spec.backend)
        attempt.advance(AttemptPhase.SENDING)
        attempt.advance(AttemptPhase.RESPONSE_HEADERS, outcomes[spec.backend])
        raise RouteRefusal(outcomes[spec.backend], (), SUB1_403)

    monkeypatch.setattr(facade, "prepare_post_body", lambda route_: object())
    monkeypatch.setattr(facade, "route_order", lambda *args: list(outcomes))
    monkeypatch.setattr(facade, "_eligible", lambda *args: True)
    monkeypatch.setattr(facade, "_attempt", attempt_fn)
    specs = [SimpleNamespace(backend=name) for name in outcomes]
    facade._run_routes(route, specs, "seed", None)
    return seen, sink


def test_facade_mixed_model_forwards_non_opt_in_refusal_without_failover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen, sink = _facade_run(monkeypatch, {"deepseek-direct": 403, "opencode-go-sub1": 403})
    assert seen == ["deepseek-direct"]
    assert sink.status == 403
    assert sink.payload == SUB1_403


def test_facade_pool_exhaustion_names_pool_label(monkeypatch: pytest.MonkeyPatch) -> None:
    seen, sink = _facade_run(monkeypatch, {"opencode-go-sub1": 403, "opencode-go-sub2": 402})
    assert seen == ["opencode-go-sub1", "opencode-go-sub2"]
    assert sink.status == 429
    message = json.loads(sink.payload)["error"]["message"]
    assert "OpenCode Go" in message
    assert "opencode-go-sub1" in message and "opencode-go-sub2" in message


def test_presend_buffered_body_returned_without_response_mutation() -> None:
    response = SimpleNamespace(status=403)
    adapter = SimpleNamespace(
        config={"failover_statuses": [402, 403], "failover_error_types": list(GO_TYPES),
                "failover_message_markers": list(GO_MARKERS)},
        _read_presend_body=lambda resp: FORBIDDEN_MODEL_403,
        _response_headers=lambda resp: [("Content-Type", "application/json")],
        _client_gone_exc=lambda: RuntimeError("client_gone"),
    )
    sink = SimpleNamespace(accepts_presend_errors=True, client_gone=lambda: False)
    conn = SimpleNamespace()
    result = resolve_presend_response(adapter, conn, response, sink, lambda: pytest.fail("retried"))
    assert result == (conn, response, False, FORBIDDEN_MODEL_403)
    assert not hasattr(response, "presend_body")


# ---- манифесты слотов ----------------------------------------------------------


@pytest.mark.parametrize(("slot", "key_name"), [("sub1", "OPENCODE_GO_SUB1_KEY"), ("sub2", "OPENCODE_GO_SUB2_KEY")])
def test_slot_manifest_loads_and_compiles(slot: str, key_name: str) -> None:
    path = ROOT / "providers.d" / f"opencode-go-{slot}.yaml"
    assert key_name in path.read_text(encoding="utf-8")
    result = validate_manifest(read_yaml_file(path), ADAPTER_KINDS, filename=path.name)
    assert result.errors == ()
    assert result.manifest is not None
    manifest = result.manifest
    assert manifest.limits.quota_group == f"opencode-go-{slot}"
    assert manifest.failover.statuses == (402, 403)
    assert "permission_error" in manifest.failover.error_types
    assert "subscription" in manifest.failover.message_markers
    assert manifest.failover.pool == "opencode-go"
    assert manifest.failover.pool_label == "OpenCode Go"
    entry = backend_entry(manifest)
    assert entry["base_url"] == "http://127.0.0.1:10830/go/v1"
    assert entry["api_key_ref"] == f"file:~/.config/opencode-go-account-switch/profiles/{slot}/opencode-go.key"
    assert entry["failover_statuses"] == [402, 403]
    assert entry["failover_message_markers"] == list(manifest.failover.message_markers)
    assert entry["failover_pool"] == "opencode-go"
    assert entry["failover_pool_label"] == "OpenCode Go"
