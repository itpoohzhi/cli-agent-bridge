"""Атрибуция и effort aliases на настоящем HTTP-шве фасада, без внешних провайдеров."""

from __future__ import annotations

import http.client
import io
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402
from core.backend_adapter import AdapterRegistry  # noqa: E402

ALIASES = (
    "gemini-4-argon-high",
    "gemini-4-argon-medium",
    "gemini-4-argon-low",
    "gpt-6.1-terra-high",
    "gpt-6.1-terra-medium",
    "gpt-6.1-terra-low",
    "claude-opus-5-5-high",
    "deepseek-v4.1-flash-free-max",
)


@pytest.fixture
def route(monkeypatch, tmp_path):
    """Выполнить do_POST без сокета, сохранив наблюдаемую границу адаптера."""
    monkeypatch.setattr(server, "AUTH_KEY", "hub-test-key")
    monkeypatch.setattr(server, "BRIDGE_KEY", "hub-test-key")
    monkeypatch.setattr(
        server,
        "TOKEN_CACHE",
        server.TokenCache(
            path=tmp_path / "missing-route.env",
            environ={"AUTH_KEY": "hub-test-key", "BRIDGE_KEY": "hub-test-key"},
        ),
    )
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    monkeypatch.setattr(server, "_budget", server._ByteBudget(1_000_000))

    def post(body, headers=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        h = object.__new__(server.Handler)
        h.path = "/v1/chat/completions"
        h.client_address = ("127.0.0.1", 12345)
        h.headers = Message()
        h.headers["Content-Length"] = str(len(raw))
        h.headers["Authorization"] = "Bearer hub-test-key"
        for k, v in (headers or {}).items():
            h.headers[k] = v
        h.rfile = io.BytesIO(raw)
        h._send = Mock()
        h._serve_passthrough = Mock()
        h.do_POST()
        assert server._budget._used == 0
        return h

    return post


@pytest.fixture
def wire(monkeypatch, tmp_path):
    """Два loopback HTTP-сервера: реальный фасад и записывающий upstream."""
    records, logs = [], []
    lock = threading.Lock()

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_POST(self):  # noqa: N802
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            with lock:
                records.append((dict(self.headers.items()), raw))
            req = json.loads(raw)
            stream = req.get("stream", False)
            payload = {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            }
            body = (
                b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
                if stream
                else json.dumps(payload).encode()
            )
            self.send_response(200)
            self.send_header(
                "Content-Type", "text/event-stream" if stream else "application/json"
            )
            self.send_header("Content-Length", str(len(body)))
            self.send_header("x-request-id", "upstream-other")
            self.send_header("X-SUBAGENT-ID", "upstream-child")
            self.end_headers()
            self.wfile.write(body)

    class TestServer(ThreadingHTTPServer):
        request_queue_size = 64

    upstream = TestServer(("127.0.0.1", 0), Upstream)
    upstream.daemon_threads = True
    upstream.request_queue_size = 64
    threading.Thread(
        target=upstream.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    ).start()
    data = json.loads((server.ROOT / "fleet.json").read_text())
    for cfg in data["backends"].values():
        if cfg["kind"] == "passthrough":
            cfg.update(
                base_url=f"http://127.0.0.1:{upstream.server_port}/v1",
                api_key="",
                api_key_env="",
                enabled=True,
            )
    fleet = server._build_catalog(data)
    monkeypatch.setattr(server, "FLEET", fleet)
    monkeypatch.setattr(
        server,
        "BACKENDS",
        AdapterRegistry.from_fleet(fleet, ADAPTER_KINDS, lambda: server.FLEET, server),
    )
    monkeypatch.setattr(server, "AUTH_KEY", "hub-test-key")
    monkeypatch.setattr(server, "BRIDGE_KEY", "hub-test-key")
    monkeypatch.setattr(
        server,
        "TOKEN_CACHE",
        server.TokenCache(
            path=tmp_path / "missing-wire.env",
            environ={"AUTH_KEY": "hub-test-key", "BRIDGE_KEY": "hub-test-key"},
        ),
    )
    monkeypatch.setattr(server, "_log", logs.append)
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    monkeypatch.setattr(server, "_is_detached_enabled", lambda: False)
    monkeypatch.setattr(server, "_budget", server._ByteBudget(1_000_000))
    bridge = TestServer(("127.0.0.1", 0), server.Handler)
    bridge.daemon_threads = True
    bridge.request_queue_size = 64
    threading.Thread(
        target=bridge.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    ).start()

    def call(body=None, headers=None, path="/v1/chat/completions", method="POST"):
        raw = (
            body
            if isinstance(body, bytes)
            else json.dumps(body or {"model": "gemini-4-argon"}).encode()
        )
        conn = http.client.HTTPConnection("127.0.0.1", bridge.server_port, timeout=10)
        try:
            conn.request(
                method,
                path,
                body=raw if method == "POST" else None,
                headers={
                    "Authorization": "Bearer hub-test-key",
                    "Content-Type": "application/json",
                    **(headers or {}),
                },
            )
            resp = conn.getresponse()
            return resp.status, resp.getheaders(), resp.read()
        finally:
            conn.close()

    try:
        yield SimpleNamespace(call=call, records=records, logs=logs)
    finally:
        bridge.shutdown()
        bridge.server_close()
        upstream.shutdown()
        upstream.server_close()


def header_values(headers, name):
    return [v for k, v in headers if k.lower() == name.lower()]


@pytest.mark.parametrize("stream", [False, True])
def test_request_id_from_header_is_echoed_and_forwarded(wire, stream):
    status, headers, _ = wire.call(
        {"model": "gemini-4-argon", "stream": stream},
        {"x-request-id": "req_test1", "X-Subagent-Id": "architect-1"},
    )
    assert status == 200
    assert header_values(headers, "x-request-id") == ["req_test1"]
    assert header_values(headers, "x-subagent-id") == ["architect-1"]
    sent = {k.lower(): v for k, v in wire.records[-1][0].items()}
    assert sent["x-request-id"] == "req_test1"
    assert sent["x-subagent-id"] == "architect-1"
    assert (
        server._resolve_trace({"x-request-id": "req_test1"}, {}).request_id_source
        == "header"
    )


def test_request_id_precedence_header_extra_body_body():
    req = {
        "extra_body": {"request_id": "extra", "subagent_id": "extra-sub"},
        "request_id": "body",
        "subagent_id": "body-sub",
    }
    assert server._resolve_trace(
        {"x-request-id": "head", "x-subagent-id": "head-sub"}, req
    ) == server.RequestTrace("head", "head-sub", "header")
    assert server._resolve_trace({}, req) == server.RequestTrace(
        "extra", "extra-sub", "extra_body"
    )
    req.pop("extra_body")
    assert server._resolve_trace({}, req) == server.RequestTrace(
        "body", "body-sub", "body"
    )
    assert server._resolve_trace({}, {}).request_id_source == "generated"
    assert (
        server._resolve_trace({"x-request-id": "bad value"}, req).request_id == "body"
    )


def test_generated_request_id_format(monkeypatch):
    assert re.fullmatch(r"req_[0-9a-f]{12}", server._resolve_trace({}, {}).request_id)
    monkeypatch.setattr(server, "REQUEST_ID_PREFIX", "child:")
    assert re.fullmatch(r"child:[0-9a-f]{12}", server._resolve_trace({}, {}).request_id)


@pytest.mark.parametrize(
    "value", ["a\r\nX-Evil: 1", "a b", "ü", "x" * 65, "", 123, {"bad": True}, None]
)
def test_crlf_and_injection_ids_rejected(wire, value):
    status, headers, _ = wire.call(
        {"model": "gemini-4-argon", "request_id": value, "subagent_id": value}
    )
    assert status == 200
    assert re.fullmatch(r"req_[0-9a-f]{12}", header_values(headers, "x-request-id")[0])
    assert header_values(headers, "x-subagent-id") == []
    sent = {k.lower(): v for k, v in wire.records[-1][0].items()}
    assert "x-subagent-id" not in sent
    rejected = [line for line in wire.logs if line.startswith("trace_id_rejected")]
    assert len(rejected) == 2
    assert all(
        re.fullmatch(
            r"trace_id_rejected field=(request_id|subagent_id) source=body len=\d+",
            line,
        )
        for line in rejected
    )
    if isinstance(value, str) and value:
        assert all(value not in line for line in wire.logs)
        assert value not in dict(headers).values() and value not in sent.values()
    assert (
        server._resolve_trace({"X-Request-Id": value}, {}).request_id_source
        == "generated"
    )


def test_upstream_duplicate_headers_case_insensitive(wire):
    _, headers, _ = wire.call(
        headers={"X-Request-Id": "ours", "X-Subagent-Id": "child"}
    )
    assert header_values(headers, "x-request-id") == ["ours"]
    assert header_values(headers, "x-subagent-id") == ["child"]


def test_parallel_requests_no_cross_talk(wire):
    def call(i):
        rid, sid = f"req_parallel_{i}", f"child-{i}"
        status, headers, _ = wire.call(
            headers={"X-Request-Id": rid, "X-Subagent-Id": sid}
        )
        assert status == 200
        assert header_values(headers, "x-request-id") == [rid]
        assert header_values(headers, "x-subagent-id") == [sid]
        return rid, sid

    with ThreadPoolExecutor(max_workers=16) as executor:
        pairs = list(executor.map(call, range(16)))
    # Чтение HTTP-тела завершается немного раньше finally маршрута; ждём конечный факт.
    deadline = time.monotonic() + 2
    while (
        len([line for line in wire.logs if line.startswith("done route=passthrough")])
        < 16
        and time.monotonic() < deadline
    ):
        threading.Event().wait(0.005)
    assert len(wire.records) == 16
    sent_pairs = {
        (
            dict((k.lower(), v) for k, v in h.items())["x-request-id"],
            dict((k.lower(), v) for k, v in h.items())["x-subagent-id"],
        )
        for h, _ in wire.records
    }
    assert sent_pairs == set(pairs)
    for rid, sid in pairs:
        for prefix in ["passthrough route", "done route=passthrough"]:
            assert (
                len(
                    [
                        line
                        for line in wire.logs
                        if line.startswith(prefix)
                        and f"request_id={rid} subagent_id={sid} " in line + " "
                    ]
                )
                == 1
            )


def test_log_lines_contain_ids(wire, monkeypatch, tmp_path):
    completed = threading.Event()

    def record_completion(line: str) -> None:
        wire.logs.append(line)
        if line.startswith("done route="):
            completed.set()

    monkeypatch.setattr(server, "_log", record_completion)
    wire.call(headers={"X-Request-Id": "req_logs", "X-Subagent-Id": "child-logs"})
    # HTTP-тело может прийти раньше серверного finally с конечным логом.
    assert completed.wait(timeout=2), "passthrough completion log missing"
    for prefix in ["chat route", "passthrough route", "done route=passthrough"]:
        assert any(
            line.startswith(prefix)
            and "request_id=req_logs subagent_id=child-logs" in line
            for line in wire.logs
        )
    # Настоящий CLI-путь с существующим fake_droid, а не самостоятельно написанный exec-лог.
    # Плоский pytest-стенд добавлен в sys.path выше, пакет tests здесь не требуется.
    from bridge_testlib import FakeDroidHub, TEST_FACTORY_KEY, droidify_raw_fleet  # pyright: ignore[reportImplicitRelativeImport]

    hub = FakeDroidHub(tmp_path / "fake")
    monkeypatch.setenv("FAKE_DROID_DIR", str(hub.base))
    monkeypatch.setenv("FACTORY_API_KEY", TEST_FACTORY_KEY)
    monkeypatch.setattr(server, "LAUNCHER", str(hub.launcher))
    monkeypatch.setattr(server, "RECEIPT_REQUIRED", False)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(server, "WORKSPACE", workspace)
    fleet = server._build_catalog(
        droidify_raw_fleet(json.loads((server.ROOT / "fleet.json").read_text()))
    )
    monkeypatch.setattr(server, "FLEET", fleet)
    monkeypatch.setattr(
        server,
        "BACKENDS",
        AdapterRegistry.from_fleet(fleet, ADAPTER_KINDS, lambda: server.FLEET, server),
    )
    monkeypatch.setattr(server.Handler, "_prompt_guard", lambda *_a: (0, "-", 0))
    monkeypatch.setattr(
        server.Handler, "_context_gate", lambda _self, req, *_a: (req, None)
    )
    try:
        for stream in [False, True]:
            completed.clear()
            status, headers, body = wire.call(
                {
                    "model": "gemini-3.8-flash",
                    "stream": stream,
                    "messages": [{"role": "user", "content": "hello"}],
                },
                {"X-Request-Id": "req_cli", "X-Subagent-Id": "child-cli"},
            )
            assert status == 200, body
            assert completed.wait(timeout=2), "CLI completion log missing"
            assert header_values(headers, "x-request-id") == ["req_cli"]
            assert header_values(headers, "x-subagent-id") == ["child-cli"]
        for prefix in ["chat route=cli", "exec model=", "done route=cli status=200"]:
            assert any(
                line.startswith(prefix)
                and "request_id=req_cli subagent_id=child-cli" in line
                for line in wire.logs
            )
        status, _, body = wire.call(
            {
                "model": "gemini-3.8-flash-low",
                "messages": [{"role": "user", "content": "alias"}],
            },
            {"X-Request-Id": "req_cli_alias"},
        )
        assert status == 200, body
        assert any(
            line.startswith(
                "exec model=gemini-3.8-flash effort=low effort_source=alias"
            )
            and "request_id=req_cli_alias" in line
            for line in wire.logs
        )
        status, _, body = wire.call(
            {
                "model": "deepseek-v4.1-flash",
                "messages": [{"role": "user", "content": "default"}],
            },
            {"X-Request-Id": "req_deepseek_default"},
        )
        assert status == 200, body
        assert any(
            line.startswith(
                "exec model=deepseek-v4.1-flash effort=off effort_source=default autonomy=off autonomy_source=default"
            )
            and "request_id=req_deepseek_default" in line
            for line in wire.logs
        )
    finally:
        server._reset_rpc_state()


def test_attribution_disabled_kill_switch(wire, monkeypatch):
    monkeypatch.setattr(server, "REQUEST_ATTRIBUTION_ENABLED", False)
    _, headers, _ = wire.call(headers={"X-Request-Id": "legacy"})
    assert header_values(headers, "x-request-id") == ["upstream-other"]
    assert {k.lower(): v for k, v in wire.records[-1][0].items()}[
        "x-request-id"
    ] == "legacy"
    assert server._trace_headers(server.RequestTrace("rid", "sid", "header")) == []


@pytest.mark.parametrize("alias", ALIASES)
def test_effort_alias_resolves_passthrough(wire, alias):
    status, _, _ = wire.call({"model": alias})
    base, _, effort = alias.rpartition("-")
    assert status == 200
    assert json.loads(wire.records[-1][1]) == {
        "model": base,
        "reasoning_effort": effort,
    }


def test_effort_alias_keeps_explicit_effort(wire):
    assert (
        wire.call({"model": "gpt-6.1-terra-high", "reasoning_effort": "low"})[0] == 200
    )
    assert json.loads(wire.records[-1][1])["reasoning_effort"] == "low"


def test_exact_id_body_untouched(wire):
    raw = b'{ "model" : "gemini-4-argon", "reasoning_effort": "low", "messages": [] }\n'
    assert wire.call(raw)[0] == 200
    assert wire.records[-1][1] == raw
    assert (
        server._resolve_model_alias(
            "gemini-4-argon-high", {"gemini-4-argon-high": {}, "gemini-4-argon": {}}
        )
        is None
    )


def test_unknown_suffix_404(wire):
    status, headers, body = wire.call(
        {"model": "gemini-4-argon-turbo"}, {"X-Request-Id": "req_unknown"}
    )
    assert status == 404 and json.loads(body)["error"]["code"] == "model_not_found"
    assert header_values(headers, "x-request-id") == ["req_unknown"]
    assert not wire.records


def test_alias_kill_switch_404(wire, monkeypatch):
    monkeypatch.setattr(server, "EFFORT_ALIAS_ENABLED", False)
    assert wire.call({"model": "gemini-4-argon-high"})[0] == 404
    assert wire.call({"model": "gemini-4-argon"})[0] == 200


def test_models_lists_advertised_aliases(wire, monkeypatch):
    monkeypatch.setattr(
        server, "ADVERTISED_EFFORT_ALIASES", ALIASES + (ALIASES[0], "unknown-high")
    )
    status, _, body = wire.call(path="/v1/models", method="GET")
    ids = [m["id"] for m in json.loads(body)["data"]]
    assert status == 200 and set(ALIASES) <= set(ids) and len(ids) == len(set(ids))
    monkeypatch.setattr(server, "ADVERTISED_EFFORT_ALIASES", ())
    assert not set(ALIASES) & {
        m["id"]
        for m in json.loads(wire.call(path="/v1/models", method="GET")[2])["data"]
    }


def test_models_default_does_not_advertise_aliases(wire, monkeypatch):
    for prefix in ("BRIDGE_", "DROID_DSH_BRIDGE_"):
        monkeypatch.delenv(prefix + "ADVERTISE_EFFORT_ALIASES", raising=False)
    cfg = server._load_request_config()
    assert cfg["ADVERTISED_EFFORT_ALIASES"] == ()
    assert server.ADVERTISED_EFFORT_ALIASES == ()
    monkeypatch.setattr(
        server, "ADVERTISED_EFFORT_ALIASES", cfg["ADVERTISED_EFFORT_ALIASES"]
    )
    status, _, body = wire.call(path="/v1/models", method="GET")
    assert status == 200
    assert not set(ALIASES) & {model["id"] for model in json.loads(body)["data"]}


def test_models_env_enables_only_requested_aliases(wire, monkeypatch):
    requested = ("gemini-4-argon-high", "gpt-6.1-terra-high")
    monkeypatch.setenv("BRIDGE_ADVERTISE_EFFORT_ALIASES", ",".join(requested))
    cfg = server._load_request_config()
    assert cfg["ADVERTISED_EFFORT_ALIASES"] == requested
    monkeypatch.setattr(
        server, "ADVERTISED_EFFORT_ALIASES", cfg["ADVERTISED_EFFORT_ALIASES"]
    )
    status, _, body = wire.call(path="/v1/models", method="GET")
    assert status == 200
    assert set(ALIASES) & {model["id"] for model in json.loads(body)["data"]} == set(
        requested
    )


@pytest.mark.parametrize("alias", ALIASES)
def test_all_ecosystem_effort_aliases_keep_resolving(alias):
    base, _, effort = alias.rpartition("-")
    assert server.EFFORT_ALIAS_ENABLED is True
    assert server._resolve_model_alias(alias, server.FLEET["models"]) == (base, effort)


def test_trace_resolution_overhead():
    start = time.perf_counter()
    for _ in range(10_000):
        server._resolve_trace({}, {})
    assert time.perf_counter() - start < 1.0


def test_invalid_config_falls_back_to_defaults(monkeypatch):
    logs = []
    monkeypatch.setattr(server, "_log", logs.append)
    for prefix in ["BRIDGE_", "DROID_DSH_BRIDGE_"]:
        for name in [
            "REQUEST_ID_HEADER",
            "SUBAGENT_ID_HEADER",
            "TRACE_ID_MAX_LEN",
            "EFFORT_SUFFIXES",
            "REQUEST_ID_PREFIX",
            "REQUEST_ATTRIBUTION_ENABLED",
            "EFFORT_ALIAS_ENABLED",
            "ADVERTISE_EFFORT_ALIASES",
        ]:
            monkeypatch.delenv(prefix + name, raising=False)
    for key, value in {
        "REQUEST_ID_HEADER": "bad:header",
        "TRACE_ID_MAX_LEN": "999",
        "EFFORT_SUFFIXES": "bogus",
        "REQUEST_ID_PREFIX": "bad prefix",
        "REQUEST_ATTRIBUTION_ENABLED": "bogus",
    }.items():
        monkeypatch.setenv("BRIDGE_" + key, value)
    cfg = server._load_request_config()
    assert cfg["REQUEST_ID_HEADER"] == "X-Request-Id" and cfg["TRACE_ID_MAX_LEN"] == 64
    assert (
        cfg["REQUEST_ID_PREFIX"] == "req_"
        and cfg["REQUEST_ATTRIBUTION_ENABLED"] is True
    )
    assert cfg["EFFORT_SUFFIXES"] == (
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    )
    assert len(logs) == 5 and all(
        line.startswith("bridge_config_invalid") for line in logs
    )
    monkeypatch.setenv("BRIDGE_ADVERTISE_EFFORT_ALIASES", "off")
    assert server._load_request_config()["ADVERTISED_EFFORT_ALIASES"] == ()
    monkeypatch.setenv("BRIDGE_REQUEST_ID_HEADER", "X-Subagent-Id")
    cfg = server._load_request_config()
    assert cfg["REQUEST_ID_HEADER"].lower() != cfg["SUBAGENT_ID_HEADER"].lower()
    monkeypatch.setenv("BRIDGE_EFFORT_SUFFIXES", "low,bogus,high")
    assert server._load_request_config()["EFFORT_SUFFIXES"] == ("low", "high")


def test_trace_reset_on_keepalive_and_validation_error(route):
    h = route({"model": "not-in-catalogue"}, {"X-Request-Id": "first"})
    assert h._trace.request_id == "first"
    h.rfile = io.BytesIO(b"{")
    h.headers.replace_header("Content-Length", "1")
    h.do_POST()
    assert h._trace is None


def test_configured_headers_and_short_generated_ids(wire, monkeypatch):
    monkeypatch.setattr(server, "REQUEST_ID_HEADER", "X-Task-Request")
    monkeypatch.setattr(server, "SUBAGENT_ID_HEADER", "X-Task-Child")
    _, headers, _ = wire.call(
        headers={"x-task-request": "custom", "X-Task-Child": "child"}
    )
    assert header_values(headers, "x-task-request") == ["custom"]
    assert header_values(headers, "x-task-child") == ["child"]
    monkeypatch.setattr(server, "TRACE_ID_MAX_LEN", 8)
    monkeypatch.setattr(server, "REQUEST_ID_PREFIX", "long-prefix-")
    ids = {server._resolve_trace({}, {}).request_id for _ in range(16)}
    assert len(ids) == 16 and all(re.fullmatch(r"[0-9a-f]{8}", rid) for rid in ids)
