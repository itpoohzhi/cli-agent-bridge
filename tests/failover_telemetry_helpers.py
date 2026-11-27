"""W2-B3: сквозные интеграционные тесты телеметрии отказов маршрутов (DEL-1) — общая инфраструктура.

По образу test_resident_precommit_failover.py, но с ВКЛЮЧЁННОЙ телеметрией: реальный
RequestTelemetryStore (DuckDB либо sqlite3-фолбэк) + usage.jsonl в tmp_path и захват server._log.
Проверяется наблюдаемое поведение через реальный HTTP-вход: wire-ответ клиенту, строки bridge.log,
записи БД (34 колонки) и usage.jsonl (18 полей) — ровно одна запись на request_id.
"""

from __future__ import annotations

import http.client
import json
import sys
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
from core.route_failure_telemetry import ALLOWED_REFUSAL_STATUSES  # noqa: E402
from core.route_health_policy import RetryBudgetConfig  # noqa: E402
from core.telemetry_sql import NAMES  # noqa: E402
from tests.failover_telemetry_catalog import build_catalog  # noqa: E402
from tests.test_resident_precommit_failover import (  # noqa: E402
    HUB_KEY,
    MODEL_ID,
    _FakeClaudeAdapter,
    _Registry,
)
from tests.transport_wire_support import RecordingUpstream, RunningHTTPServer  # noqa: E402

CLI_ID = "claude-p"
PT_A, PT_B = "agy", "agy2"
REFUSAL_CODES = sorted(ALLOWED_REFUSAL_STATUSES)

Upstream = Callable[[RecordingUpstream, Any, bytes], None]
Route = tuple[str, Callable[..., Any]]

_RUNTIME_ENV = {
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


def setup_isolated_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Тело autouse-фикстуры isolated_runtime (фикстура объявляется в самом тест-модуле)."""
    for key, val in _RUNTIME_ENV.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setattr(facade, "_RUNTIME", facade._RuntimeState())
    facade._begin_retry_request(RetryBudgetConfig(), 1).release_unused()
    assert facade._RUNTIME.bucket is not None
    for _ in range(4):
        facade._RUNTIME.bucket.admit_primary()


def open_store(tmp_path: Path) -> Iterator[RequestTelemetryStore]:
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


def counting(
    fn: Callable[..., Any], calls: list[str]
) -> Callable[[TurnContext, StreamSink | None], TurnResult]:
    def wrapped(ctx: TurnContext, sse: StreamSink | None) -> TurnResult:
        calls.append(CLI_ID)
        return fn(ctx, sse)

    return wrapped


def _build_adapters(
    routes: Sequence[Route], catalog: dict[str, Any], cli_calls: list[str]
) -> dict[str, BackendAdapter]:
    adapters: dict[str, BackendAdapter] = {}
    for name, fn in routes:
        cfg = catalog["backends"][name]
        if name == CLI_ID:
            adapters[name] = _FakeClaudeAdapter(
                name, cfg, lambda: catalog, counting(fn, cli_calls)
            )
        else:
            adapters[name] = PassthroughAdapter(name, cfg, lambda: catalog, server)
    return adapters


def _patch_server(
    monkeypatch: pytest.MonkeyPatch,
    catalog: dict[str, Any],
    adapters: dict[str, BackendAdapter],
    store: RequestTelemetryStore,
    logs: list[str],
) -> None:
    monkeypatch.setattr(server, "FLEET", catalog)
    monkeypatch.setattr(server, "BACKENDS", _Registry(adapters))
    monkeypatch.setattr(server, "AUTH_KEY", HUB_KEY)
    monkeypatch.setattr(server, "BRIDGE_KEY", HUB_KEY)
    cache = server.TokenCache(
        path=server.ROOT / ".absent-tok.env", environ={"BRIDGE_KEY": HUB_KEY}
    )
    monkeypatch.setattr(server, "TOKEN_CACHE", cache)
    penalty = SimpleNamespace(
        get_model_status=lambda _m: {"is_penalized": False},
        record_start_success=lambda _m: None,
        record_start_failure=lambda _m, _r: None,
    )
    monkeypatch.setattr(server, "_PENALTY_TRACKER", penalty)
    guard = SimpleNamespace(snapshot=lambda: ("safe", (), 1 << 20))
    monkeypatch.setattr(server, "GUARD", guard)
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    monkeypatch.setattr(server, "_log", logs.append)
    monkeypatch.setattr(server, "REQUEST_TELEMETRY", store)


@contextmanager
def gateway(
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
        specs = [
            (n, upstreams[n].base_url if n in upstreams else None) for n, _ in routes
        ]
        catalog = build_catalog(specs)
        adapters = _build_adapters(routes, catalog, cli_calls)
        stack.callback(lambda: [adapter.shutdown() for adapter in adapters.values()])
        _patch_server(monkeypatch, catalog, adapters, store, logs)
        # Сервер закрывается ДО возврата управления тесту: однопоточный HTTPServer завершил обработку запроса.
        with RunningHTTPServer(server.Handler) as httpd:
            yield Gateway(httpd.port, store, logs, upstreams, adapters, cli_calls)


def post(port: int, *, stream: bool) -> tuple[int, dict[str, str], bytes]:
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
