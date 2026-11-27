"""W2-B3: сквозные интеграционные тесты телеметрии отказов маршрутов (DEL-1).

По образу test_resident_precommit_failover.py, но с ВКЛЮЧЁННОЙ телеметрией: реальный
RequestTelemetryStore (DuckDB либо sqlite3-фолбэк) + usage.jsonl в tmp_path и захват server._log.
Проверяется наблюдаемое поведение через реальный HTTP-вход: wire-ответ клиенту, строки bridge.log,
записи БД (34 колонки) и usage.jsonl (18 полей) — ровно одна запись на request_id.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
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
from core.backend_adapter import BackendAdapter, StreamSink, TurnContext, TurnResult  # noqa: E402
from core.request_telemetry import RequestTelemetryStore  # noqa: E402
from core.route_attempts import RouteRefusal  # noqa: E402
from core.route_cb import FailureOutcome  # noqa: E402
from core.route_failure_telemetry import ALL_ROUTES_OPEN_BODY, ALLOWED_REFUSAL_STATUSES  # noqa: E402
from core.route_health_policy import RetryBudgetConfig  # noqa: E402
from core.telemetry_sql import NAMES  # noqa: E402
from core.usage_schema import USAGE_LOG_FIELDS  # noqa: E402
from tests.test_resident_precommit_failover import (  # noqa: E402
    HUB_KEY,
    MODEL_ID,
    _FakeClaudeAdapter,
    _Registry,
    _resident_error,
)
from tests.transport_wire_support import (  # noqa: E402
    RecordingUpstream,
    RunningHTTPServer,
    WireSettings,
)

CLI_ID = "claude-p"
PT_A, PT_B = "agy", "agy2"
REFUSAL_CODES = sorted(ALLOWED_REFUSAL_STATUSES)

Upstream = Callable[[RecordingUpstream, Any, bytes], None]
Route = tuple[str, Callable[..., Any]]


# ---- инфраструктура -------------------------------------------------------------------------


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
        "BRIDGE_TELEMETRY_ENABLED": "true",
        "BRIDGE_ROUTE_CB_EVENTS": "false",
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


@pytest.fixture
def store(tmp_path: Path) -> Iterator[RequestTelemetryStore]:
    """Реальный стор: БД и usage.jsonl в tmp_path, ручной flush (без фонового writer)."""
    telemetry = RequestTelemetryStore(
        str(tmp_path / "telemetry.duckdb"),
        enabled=True,
        autostart=False,
        usage_log_enabled=True,
        usage_log_path=str(tmp_path / "usage.jsonl"),
    )
    try:
        yield telemetry
    finally:
        telemetry.close()


@dataclass
class Gateway:
    """Поднятый HTTP-вход моста с захваченным bridge.log и доступом к записанной телеметрии."""

    port: int
    store: RequestTelemetryStore
    logs: list[str]
    upstreams: dict[str, RecordingUpstream]
    adapters: dict[str, BackendAdapter]
    cli_calls: list[str]

    def rows(self) -> list[dict[str, Any]]:
        """Все строки bridge_requests (34 колонки) после flush очереди writer."""
        self.store.flush()
        if not self.store.ensure_open():
            return []
        with self.store._db_lock:
            raw = self.store._con.execute(
                f"SELECT {', '.join(NAMES)} FROM bridge_requests ORDER BY ts_epoch"
            ).fetchall()
        return [dict(zip(NAMES, row, strict=True)) for row in raw]

    def usage(self) -> list[dict[str, Any]]:
        """Записи usage.jsonl (18 полей allowlist)."""
        self.store.flush()
        path = Path(self.store.usage_log_status()["path"])
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text("utf-8").splitlines()
            if line.strip()
        ]

    def log_lines(self, prefix: str) -> list[str]:
        return [line for line in self.logs if line.startswith(prefix)]


def _catalog(specs: Sequence[tuple[str, str | None]]) -> dict[str, Any]:
    """Каталог: spec = (backend_id, base_url | None); None — CLI (stdio_resident), иначе passthrough."""
    first = specs[0][0]
    routes = [
        {
            "route_id": name,
            "backend": name,
            "weight": 100 if idx == 0 else 0,
            "priority": 10 * (idx + 1),
        }
        for idx, (name, _) in enumerate(specs)
    ]
    active = json.dumps(
        [{"backend": first, "route_id": first, "weight": 100}],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    model = {
        "id": MODEL_ID,
        "backend": first,
        "efforts": ["low", "medium", "high", "max"],
        "default_effort": "high",
        "context_window": 200000,
        "max_tokens": 64000,
        "input": ["text"],
        "images": {"status": "unsupported", "method": None},
        "routing": {
            "enabled": True,
            "algorithm": "weighted-sha256-v1",
            "catalog_hash": hashlib.sha256(active).hexdigest(),
            "legacy_backend": first,
            "disabled_backend": first,
            "routes": routes,
        },
    }
    backends: dict[str, Any] = {}
    for name, url in specs:
        if url is None:
            backends[name] = {
                "kind": "stdio_resident",
                "enabled": True,
                "owned_by": f"{name}-bridge",
            }
        else:
            backends[name] = {
                "kind": "passthrough",
                "base_url": url,
                "enabled": True,
                "max_concurrent": 1,
                "owned_by": f"{name}-bridge",
            }
    return {
        "schema": 3,
        "models": {MODEL_ID: model},
        "order": [MODEL_ID],
        "backends": backends,
        "backend_order": [name for name, _ in specs],
        "image_limits": {"max_body_bytes": WireSettings().max_body_bytes},
    }


@contextmanager
def _gateway(
    monkeypatch: pytest.MonkeyPatch,
    store: RequestTelemetryStore,
    routes: Sequence[Route],
) -> Iterator[Gateway]:
    """routes — упорядоченные (backend_id, обработчик): CLI_ID -> on_turn(ctx, sse), иначе upstream(up, handler, body)."""
    logs: list[str] = []
    cli_calls: list[str] = []
    with ExitStack() as stack:
        upstreams: dict[str, RecordingUpstream] = {}
        for name, fn in routes:
            if name == CLI_ID:
                continue
            up = stack.enter_context(RecordingUpstream())
            up.respond = lambda handler, body, up=up, fn=fn: fn(up, handler, body)
            upstreams[name] = up
        catalog = _catalog(
            [
                (name, upstreams[name].base_url if name in upstreams else None)
                for name, _ in routes
            ]
        )
        adapters: dict[str, BackendAdapter] = {}
        for name, fn in routes:
            cfg = catalog["backends"][name]
            if name == CLI_ID:
                adapters[name] = _FakeClaudeAdapter(
                    name, cfg, lambda: catalog, _counting(fn, cli_calls)
                )
            else:
                adapters[name] = PassthroughAdapter(name, cfg, lambda: catalog, server)
        stack.callback(lambda: [adapter.shutdown() for adapter in adapters.values()])
        monkeypatch.setattr(server, "FLEET", catalog)
        monkeypatch.setattr(server, "BACKENDS", _Registry(adapters))
        monkeypatch.setattr(server, "AUTH_KEY", HUB_KEY)
        monkeypatch.setattr(server, "BRIDGE_KEY", HUB_KEY)
        monkeypatch.setattr(
            server,
            "TOKEN_CACHE",
            server.TokenCache(
                path=server.ROOT / ".absent-tok.env", environ={"BRIDGE_KEY": HUB_KEY}
            ),
        )
        monkeypatch.setattr(
            server,
            "_PENALTY_TRACKER",
            SimpleNamespace(
                get_model_status=lambda _m: {"is_penalized": False},
                record_start_success=lambda _m: None,
                record_start_failure=lambda _m, _r: None,
            ),
        )
        monkeypatch.setattr(
            server, "GUARD", SimpleNamespace(snapshot=lambda: ("safe", (), 1 << 20))
        )
        monkeypatch.setattr(server, "_shutting_down", False)
        monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
        monkeypatch.setattr(server, "_log", logs.append)
        monkeypatch.setattr(server, "REQUEST_TELEMETRY", store)
        # Сервер закрывается ДО возврата управления тесту: однопоточный HTTPServer завершил обработку запроса.
        with RunningHTTPServer(server.Handler) as httpd:
            gateway = Gateway(httpd.port, store, logs, upstreams, adapters, cli_calls)
            yield gateway


def _counting(
    fn: Callable[..., Any], calls: list[str]
) -> Callable[[TurnContext, StreamSink | None], TurnResult]:
    def wrapped(ctx: TurnContext, sse: StreamSink | None) -> TurnResult:
        calls.append(CLI_ID)
        return fn(ctx, sse)

    return wrapped


def _post(port: int, *, stream: bool) -> tuple[int, dict[str, str], bytes]:
    """POST chat; обрыв без ответа (клиент ушёл / сервер не ответил) -> статус 0."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    payload = json.dumps(
        {
            "model": MODEL_ID,
            "stream": stream,
            "messages": [{"role": "user", "content": "ping"}],
        }
    ).encode("utf-8")
    headers = {"Authorization": f"Bearer {HUB_KEY}", "Content-Type": "application/json"}
    try:
        conn.request("POST", "/v1/chat/completions", body=payload, headers=headers)
        resp = conn.getresponse()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
    except (http.client.HTTPException, OSError):
        return 0, {}, b""
    finally:
        conn.close()


def _cli_refuses(code: int) -> Callable[[TurnContext, StreamSink | None], TurnResult]:
    def refuse(_ctx: TurnContext, _sse: StreamSink | None) -> TurnResult:
        raise _resident_error(
            code, "resident_dispatch_failed", f"resident refused {code}"
        )

    return refuse


def _upstream_error(code: int) -> Upstream:
    def respond(up: RecordingUpstream, handler: Any, _body: bytes) -> None:
        up.json(
            handler,
            {
                "error": {
                    "type": "upstream_error",
                    "code": "upstream_refused",
                    "message": f"upstream {code}",
                }
            },
            status=code,
        )

    return respond


def _upstream_ok(stream: bool) -> Upstream:
    def respond(up: RecordingUpstream, handler: Any, _body: bytes) -> None:
        if stream:
            up.sse(
                handler,
                b'data: {"id":"ok-sse","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"from-pt"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
            )
        else:
            up.json(
                handler,
                {
                    "id": "ok-1",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "from-pt"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

    return respond


def _open_all_route_breakers(backends: Sequence[str]) -> None:
    """Открывает РЕАЛЬНЫЙ RouteCB для всех маршрутов (ключ — (provider, model, backend))."""
    route_cb, _legacy = facade.get_route_cb(facade._RUNTIME)
    assert route_cb is not None
    for backend in backends:
        key = (backend, MODEL_ID, backend)
        for _ in range(route_cb._config.failure_threshold):
            route_cb.record_failure(key, FailureOutcome(status=503))
        assert route_cb.try_acquire(key, time.monotonic()) is None, (
            f"breaker {backend} must be open"
        )


def _assert_single_record(
    gw: Gateway, *, status: int, error_type: str | None, model: str = MODEL_ID
) -> dict[str, Any]:
    """Ровно одна запись в БД (34 колонки) и в usage.jsonl (18 полей) с одним request_id."""
    rows, usage = gw.rows(), gw.usage()
    assert len(rows) == 1, rows
    assert len(usage) == 1, usage
    row, rec = rows[0], usage[0]
    assert len(row) == len(NAMES) == 34
    assert set(rec) == set(USAGE_LOG_FIELDS) and len(rec) == 18
    assert (row["status_code"], row["error_type"], row["model"]) == (
        status,
        error_type,
        model,
    )
    assert (rec["http_status"], rec["model"]) == (status, model)
    assert row["request_id"] and rec["request_id"] == row["request_id"]
    return row


# ---- AC-1: 503 all_routes_open -----------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True])
def test_all_routes_open_returns_503_and_records_telemetry(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore, stream: bool
) -> None:
    routes: list[Route] = [(CLI_ID, _cli_refuses(502)), (PT_A, _upstream_ok(stream))]
    with _gateway(monkeypatch, store, routes) as gw:
        _open_all_route_breakers([CLI_ID, PT_A])
        status, headers, raw = _post(gw.port, stream=stream)
    assert status == 503
    assert headers["retry-after"].isdigit() and int(headers["retry-after"]) > 0
    assert "application/json" in headers["content-type"]
    assert raw == ALL_ROUTES_OPEN_BODY
    assert json.loads(raw)["error"]["type"] == "all_routes_open"
    assert gw.cli_calls == [] and gw.upstreams[PT_A].post_count == 0
    _assert_single_record(gw, status=503, error_type="all_routes_open")
    failure = gw.log_lines("route_failure ")
    assert len(failure) == 1
    assert (
        "status=503" in failure[0]
        and "all_routes_open" in failure[0]
        and f"model={MODEL_ID}" in failure[0]
    )


# ---- AC-2: терминальный CLI RouteRefusal ---------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("code", REFUSAL_CODES)
def test_cli_route_refusal_terminal_records_refusal_status(
    monkeypatch: pytest.MonkeyPatch,
    store: RequestTelemetryStore,
    code: int,
    stream: bool,
) -> None:
    with _gateway(monkeypatch, store, [(CLI_ID, _cli_refuses(code))]) as gw:
        status, _headers, _raw = _post(gw.port, stream=stream)
    assert status == code
    assert gw.cli_calls == [CLI_ID]
    _assert_single_record(gw, status=code, error_type="RouteRefusal")
    assert gw.log_lines(f"done route=cli status={code} ")
    assert not gw.log_lines("done route=cli status=0 ")
    assert not [r for r in gw.rows() if r["status_code"] == 500]


# ---- OPEN-01: AFTER-FAILOVER-200 (final-status-wins) ---------------------------------------------


@pytest.mark.parametrize("stream", [False, True])
def test_cli_429_failover_to_passthrough_200_records_single_200(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore, stream: bool
) -> None:
    with _gateway(
        monkeypatch, store, [(CLI_ID, _cli_refuses(429)), (PT_A, _upstream_ok(stream))]
    ) as gw:
        status, _headers, raw = _post(gw.port, stream=stream)
    assert status == 200 and b"from-pt" in raw
    assert gw.cli_calls == [CLI_ID] and gw.upstreams[PT_A].post_count == 1
    row = _assert_single_record(gw, status=200, error_type=None)
    assert row["route_mode"] == "passthrough" and row["backend_id"] == PT_A
    cli_done, pt_done = (
        gw.log_lines("done route=cli status=429 "),
        gw.log_lines("done route=passthrough status=200 "),
    )
    assert len(cli_done) == 1 and len(pt_done) == 1
    assert gw.logs.index(cli_done[0]) < gw.logs.index(pt_done[0])
    assert not gw.log_lines("route_failure ")


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("failover", [False, True], ids=["direct", "after-failover"])
def test_success_path_records_before_routes_finally(
    monkeypatch: pytest.MonkeyPatch,
    store: RequestTelemetryStore,
    failover: bool,
    stream: bool,
) -> None:
    """RW-201: запись телеметрии на успешном пути происходит ДО входа в finally _run_routes."""
    entered: list[dict[str, Any]] = []
    original = facade.finalize_routes_exit

    def spy(route: Any, reservation: Any) -> None:
        handler = route.handler
        entered.append(
            {
                "recorded": bool(getattr(handler, "_req_recorded", False)),
                "queued": store._queue.qsize(),
            }
        )
        original(route, reservation)

    monkeypatch.setattr(facade, "finalize_routes_exit", spy)
    routes: list[Route] = (
        [(CLI_ID, _cli_refuses(429)), (PT_A, _upstream_ok(stream))]
        if failover
        else [(PT_A, _upstream_ok(stream))]
    )
    with _gateway(monkeypatch, store, routes) as gw:
        status, _headers, _raw = _post(gw.port, stream=stream)
    assert status == 200
    assert entered == [{"recorded": True, "queued": 1}]
    _assert_single_record(gw, status=200, error_type=None)


# ---- passthrough failover 429 -> 200 -------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True])
def test_passthrough_429_failover_to_200_records_single_200(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore, stream: bool
) -> None:
    with _gateway(
        monkeypatch, store, [(PT_A, _upstream_error(429)), (PT_B, _upstream_ok(stream))]
    ) as gw:
        status, _headers, raw = _post(gw.port, stream=stream)
    assert status == 200 and b"from-pt" in raw
    assert gw.upstreams[PT_A].post_count == 1 and gw.upstreams[PT_B].post_count == 1
    row = _assert_single_record(gw, status=200, error_type=None)
    assert row["backend_id"] == PT_B
    assert gw.log_lines("done route=passthrough status=429 ") and gw.log_lines(
        "done route=passthrough status=200 "
    )


# ---- strict exactly-once (F-001 / RW-201) --------------------------------------------------------


def test_disconnect_between_attempts_records_single_499(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore
) -> None:
    gone = {"flag": False}
    original_attempt = facade._attempt

    def attempt_then_disconnect(route: Any, spec: Any, body: Any, attempt: Any) -> None:
        try:
            original_attempt(route, spec, body, attempt)
        except RouteRefusal:
            gone["flag"] = (
                True  # клиент пропал сразу после pre-commit отказа маршрута 1
            )
            raise

    monkeypatch.setattr(facade, "_attempt", attempt_then_disconnect)
    monkeypatch.setattr(server, "_client_gone", lambda _sock: gone["flag"])
    with _gateway(
        monkeypatch, store, [(PT_A, _upstream_error(429)), (PT_B, _upstream_ok(False))]
    ) as gw:
        _post(gw.port, stream=False)
    assert gone["flag"] is True
    assert gw.upstreams[PT_A].post_count == 1 and gw.upstreams[PT_B].post_count == 0
    _assert_single_record(gw, status=499, error_type="client_disconnected")


@pytest.mark.parametrize("where", ["before_serve", "inside_passthrough"])
def test_non_refusal_exception_on_route2_records_single_500(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore, where: str
) -> None:
    original_attempt = facade._attempt
    calls = {"n": 0}

    def attempt_or_boom(route: Any, spec: Any, body: Any, attempt: Any) -> None:
        calls["n"] += 1
        if where == "before_serve" and calls["n"] == 2:
            raise RuntimeError("route 2 exploded")
        original_attempt(route, spec, body, attempt)

    monkeypatch.setattr(facade, "_attempt", attempt_or_boom)
    with _gateway(
        monkeypatch, store, [(PT_A, _upstream_error(429)), (PT_B, _upstream_ok(False))]
    ) as gw:
        if where == "inside_passthrough":

            def explode(**_kwargs: Any) -> None:
                raise RuntimeError("route 2 exploded")

            monkeypatch.setattr(gw.adapters[PT_B], "handle", explode)
        _post(gw.port, stream=False)
    assert calls["n"] == 2
    assert gw.upstreams[PT_A].post_count == 1
    _assert_single_record(gw, status=500, error_type="RuntimeError")


# ---- security regression (THREAT-001 / RW-001) -----------------------------------------------------


@pytest.mark.parametrize("stream", [False, True])
def test_passthrough_strips_spoofed_upstream_x_bridge_draining(
    monkeypatch: pytest.MonkeyPatch, store: RequestTelemetryStore, stream: bool
) -> None:
    def spoofing_upstream(up: RecordingUpstream, handler: Any, _body: bytes) -> None:
        up.json(
            handler,
            {
                "error": {
                    "type": "upstream_error",
                    "code": "upstream_unavailable",
                    "message": "spoofed drain",
                }
            },
            status=503,
            extra=(("X-Bridge-Draining", "true"), ("Retry-After", "5")),
        )

    with _gateway(monkeypatch, store, [(PT_A, spoofing_upstream)]) as gw:
        status, headers, _raw = _post(
            gw.port, stream=stream
        )  # клиент — loopback (127.0.0.1)
    assert status == 503
    assert gw.upstreams[PT_A].post_count == 1
    assert "x-bridge-draining" not in headers
    assert (
        headers.get("retry-after") == "5"
    )  # остальные заголовки апстрима проходят — вырезан именно drain-спуф
