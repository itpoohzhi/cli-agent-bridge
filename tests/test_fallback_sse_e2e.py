"""W3-A: HTTP-контракт алиаса, fail-fast квота и чистый SSE через фасад."""

from __future__ import annotations

import http.client
import json
import sys
import threading
from collections.abc import Callable, Generator, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402
from core.backend_adapter import AdapterRegistry  # noqa: E402
from core.model_fallback_chain import FallbackChain, load_chains  # noqa: E402

ALIAS = "compaction-resilient"
QUOTA = {"error": {"code": "GoUsageLimitError", "message": "resets in 2d 10h"}}
TEXT = "Шаг 1.\n\nИтог ✓"


def _chunks(model: str) -> list[dict[str, Any]]:
    deltas = [{"role": "assistant"}, {"reasoning_content": "Проверка"}, {"content": TEXT}, {}]
    return [
        {
            "id": "chatcmpl-fallback-e2e",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": "stop" if i == 3 else None}],
        }
        for i, delta in enumerate(deltas)
    ]


@dataclass
class _Scenario:
    chain: FallbackChain
    rejected: set[str] = field(default_factory=set)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def respond(self, handler: BaseHTTPRequestHandler, request: dict[str, Any]) -> None:
        self.calls.append(request)
        model = request["model"]
        status = 429 if model in self.rejected else 200
        content_type = "application/json"
        if status == 429:
            body = json.dumps(QUOTA).encode()
        elif request.get("stream"):
            content_type = "text/event-stream"
            body = b"".join(
                ("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode()
                for chunk in _chunks(model)
            ) + b"data: [DONE]\n\n"
        else:
            body = json.dumps({
                "id": "chatcmpl-fallback-e2e", "object": "chat.completion", "created": 1,
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": TEXT},
                             "finish_reason": "stop"}],
            }).encode()
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        handler.wfile.flush()


@contextmanager
def _http_server(handler: type[BaseHTTPRequestHandler]) -> Iterator[int]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        yield httpd.server_port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def _configure(monkeypatch: pytest.MonkeyPatch, scenario: _Scenario, port: int) -> Any:
    raw = json.loads((ROOT / "fleet.json").read_text())
    template = next(model for model in raw["models"] if model["backend"] == "codex")
    raw["models"] = [
        {**template, "id": c.model, "backend": "codex", "context_window": c.context_window}
        for c in scenario.chain.candidates
    ]
    raw["default_model"] = scenario.chain.candidates[0].model
    raw["aliases"] = {}
    raw["backends"] = {"codex": {
        "kind": "passthrough", "enabled": True, "required": False,
        "owned_by": "fallback-e2e", "max_concurrent": 4,
        "base_url": f"http://127.0.0.1:{port}/v1",
    }}
    catalog = server._build_catalog(raw)
    monkeypatch.setattr(server, "FLEET", catalog)
    backends = AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog, server)
    monkeypatch.setattr(server, "BACKENDS", backends)
    monkeypatch.setattr(server, "MODEL_ID", raw["default_model"])
    return backends


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[Callable[..., Any]]:
    monkeypatch.setenv("BRIDGE_MODEL_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "false")
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    monkeypatch.setattr(
        server, "TOKEN_CACHE",
        server.TokenCache(path=tmp_path / ".env", environ={"BRIDGE_KEY": "fallback-e2e-key"}),
    )
    failures = Mock(wraps=server._PENALTY_TRACKER.record_start_failure)
    monkeypatch.setattr(server._PENALTY_TRACKER, "record_start_failure", failures)

    with ExitStack() as stack:
        def start(exhausted_status: int = 429) -> Any:
            config = yaml.safe_load((ROOT / "fallback_chains.d/compaction.yaml").read_text())
            config["chains"][ALIAS]["exhausted_status_code"] = exhausted_status
            directory = tmp_path / "chains"
            directory.mkdir()
            (directory / "compaction.yaml").write_text(yaml.safe_dump(config))
            monkeypatch.setenv("BRIDGE_FALLBACK_CHAINS_PATH", str(directory))
            scenario = _Scenario(load_chains(directory).chains[ALIAS])

            class Upstream(BaseHTTPRequestHandler):
                def do_POST(self) -> None:  # noqa: N802
                    request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    scenario.respond(self, request)

                def log_message(self, fmt: str, *args: Any) -> None:
                    return

            upstream_port = stack.enter_context(_http_server(Upstream))
            backends = _configure(monkeypatch, scenario, upstream_port)
            for adapter in backends.adapters():
                stack.callback(adapter.shutdown)
            port = stack.enter_context(_http_server(server.Handler))
            return SimpleNamespace(port=port, scenario=scenario, failures=failures)

        yield start


def _request(port: int, request: dict[str, Any] | None = None, auth: bool = True,
             extra: dict[str, str] | None = None) -> Any:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Connection": "close", "Content-Type": "application/json", **(extra or {})}
    if auth:
        headers["Authorization"] = "Bearer fallback-e2e-key"
    try:
        method, path = ("GET", "/v1/models") if request is None else ("POST", "/v1/chat/completions")
        conn.request(method, path, body=None if request is None else json.dumps(request), headers=headers)
        response = conn.getresponse()
        result = SimpleNamespace(status=response.status, headers=dict(response.getheaders()),
                                 body=response.read())
        # Content-Length не означает завершение post-response учёта штрафов обработчиком.
        if conn.sock is not None:
            assert conn.sock.recv(1) == b""
        return result
    finally:
        conn.close()


def _chat(stream: bool, model: str = ALIAS) -> dict[str, Any]:
    return {"model": model, "stream": stream,
            "messages": [{"role": "user", "content": "Сожми этот диалог."}]}


def _assert_success(response: Any, stream: bool, model: str = ALIAS) -> None:
    assert response.status == 200, response.body
    if not stream:
        payload = json.loads(response.body)
        assert payload["model"] == model
        assert payload["choices"][0]["message"]["content"] == TEXT
        return
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert headers["content-type"].startswith("text/event-stream")
    frames = response.body.decode().replace("\r\n", "\n").split("\n\n")
    data = [frame[6:] for frame in frames if frame.startswith("data: ")]
    assert data[-1] == "[DONE]" and data.count("[DONE]") == 1
    chunks = [json.loads(frame) for frame in data[:-1]]
    assert chunks and all(chunk["model"] == model and "error" not in chunk for chunk in chunks)
    choices = [chunk["choices"][0] for chunk in chunks if chunk.get("choices")]
    assert "".join(choice["delta"].get("content", "") for choice in choices) == TEXT
    assert "".join(choice["delta"].get("reasoning_content", "") for choice in choices) == "Проверка"
    assert choices[-1]["finish_reason"] == "stop"
    assert b"GoUsageLimitError" not in response.body


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_models_advertise_alias_only_when_enabled(gateway: Any, monkeypatch: pytest.MonkeyPatch,
                                                  enabled: str) -> None:
    monkeypatch.setenv("BRIDGE_MODEL_FALLBACK_ENABLED", enabled)
    h = gateway()
    response = _request(h.port)
    assert response.status == 200
    cards = {model["id"]: model for model in json.loads(response.body)["data"]}
    if enabled == "true":
        assert ALIAS in cards
        assert cards[ALIAS]["context_window"] == h.scenario.chain.declared_context_window
    else:
        assert ALIAS not in cards
    assert not h.scenario.calls


@pytest.mark.parametrize("stream", [False, True])
def test_quota_before_first_byte_switches_without_penalty(gateway: Any, stream: bool) -> None:
    h = gateway()
    first, second = [c.model for c in h.scenario.chain.candidates[:2]]
    h.scenario.rejected.add(first)
    response = _request(h.port, _chat(stream))
    _assert_success(response, stream)
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert headers["x-bridge-fallback-model"] == second
    assert headers["x-bridge-fallback-attempts"] == "2"
    assert [call["model"] for call in h.scenario.calls] == [first, second]
    assert server._QUOTA_CB_CACHE.is_blocked(first)
    assert not server._QUOTA_CB_CACHE.is_blocked(ALIAS)
    h.failures.assert_not_called()
    _assert_success(_request(h.port, _chat(stream)), stream)
    assert [call["model"] for call in h.scenario.calls] == [first, second, second]
    h.failures.assert_not_called()


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("stream", [False, True])
def test_exhaustion_is_http_error_before_sse(gateway: Any, status: int, stream: bool) -> None:
    h = gateway(status)
    candidates = [c.model for c in h.scenario.chain.candidates]
    h.scenario.rejected.update(candidates)
    response = _request(h.port, _chat(stream))
    assert response.status == status, response.body
    error = json.loads(response.body)["error"]
    assert error["code"] == "fallback_chain_exhausted"
    assert [attempt["model"] for attempt in error["attempts"]] == candidates
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert 0 < int(headers["retry-after"]) <= 208800
    assert [call["model"] for call in h.scenario.calls] == candidates
    assert all(server._QUOTA_CB_CACHE.is_blocked(model) for model in candidates)
    h.failures.assert_not_called()
    assert _request(h.port, _chat(stream)).status == status
    assert [call["model"] for call in h.scenario.calls] == candidates


@pytest.mark.parametrize("stream", [False, True])
def test_kill_switch_off_hook_is_inert_for_alias(gateway: Any, monkeypatch: pytest.MonkeyPatch,
                                                 stream: bool) -> None:
    """F-016: выключенный флаг — хук не вмешивается; алиас не уходит ни на какую модель."""
    monkeypatch.setenv("BRIDGE_MODEL_FALLBACK_ENABLED", "false")
    h = gateway()
    response = _request(h.port, _chat(stream))
    assert response.status >= 400 and response.status != 429
    assert not h.scenario.calls
    h.failures.assert_not_called()


def test_disabled_target_avoids_exhausted_provider() -> None:
    """F-017: disabled_target — не исчерпанный opencode-go, у каждого кандидата есть quota_scope."""
    chain = load_chains(ROOT / "fallback_chains.d", env={}).chains[ALIAS]
    assert chain.disabled_target == "gemini-4-argon"
    assert {c.model: c.quota_scope for c in chain.candidates} == {
        "gemini-4-argon": "agy", "claude-haiku-5-5": "claude",
        "gpt-6.1-sol": "codex", "deepseek-v4.1-flash": "opencode-go",
    }


def test_quota_scope_blocks_all_models_of_account(gateway: Any) -> None:
    h = gateway()
    first = h.scenario.chain.candidates[0]
    h.scenario.rejected.add(first.model)
    assert _request(h.port, _chat(False)).status == 200
    assert server._QUOTA_CB_CACHE.is_blocked(first.model)
    assert server._QUOTA_CB_CACHE.is_blocked(f"scope:{first.quota_scope}")


def test_idempotency_key_is_forwarded_as_step_job_id(gateway: Any) -> None:
    h = gateway()
    response = _request(h.port, _chat(False), extra={"X-Idempotency-Key": " job-42 "})
    assert response.status == 200
    assert [call.get("step_job_id") for call in h.scenario.calls] == ["job-42"]


@pytest.mark.parametrize("bypass", [False, True])
def test_bypass_model_filter_header_is_honoured(gateway: Any, monkeypatch: pytest.MonkeyPatch,
                                                bypass: bool) -> None:
    h = gateway()
    first, second = [c.model for c in h.scenario.chain.candidates[:2]]
    monkeypatch.setattr(server._MODEL_NOTES_FILTER, "is_blocked", lambda model: model == first)
    extra = {"X-Bypass-Model-Filter": "1"} if bypass else None
    assert _request(h.port, _chat(False), extra=extra).status == 200
    assert [call["model"] for call in h.scenario.calls] == [first if bypass else second]


def test_success_is_recorded_on_penalty_tracker(gateway: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    success = Mock()
    monkeypatch.setattr(server._PENALTY_TRACKER, "record_start_success", success)
    h = gateway()
    assert _request(h.port, _chat(False)).status == 200
    success.assert_called_once_with(h.scenario.chain.candidates[0].model)


def test_permission_error_on_candidate_falls_through(gateway: Any,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    h = gateway()
    first, second = [c.model for c in h.scenario.chain.candidates[:2]]
    monkeypatch.setattr(
        server, "_quarantine_denial",
        lambda model, subagent: "denied" if model == first else None,
    )
    response = _request(h.port, _chat(False))
    assert response.status == 200
    assert [call["model"] for call in h.scenario.calls] == [second]


@pytest.mark.parametrize("stream", [False, True])
def test_disabled_direct_model_keeps_base_penalty(gateway: Any, monkeypatch: pytest.MonkeyPatch,
                                                stream: bool) -> None:
    monkeypatch.setenv("BRIDGE_MODEL_FALLBACK_ENABLED", "false")
    h = gateway()
    target = h.scenario.chain.candidates[0].model
    h.scenario.rejected.add(target)
    response = _request(h.port, _chat(stream, target))
    assert response.status == 429
    assert json.loads(response.body) == QUOTA
    assert [call["model"] for call in h.scenario.calls] == [target]
    h.failures.assert_called_once_with(target, "http_429")
    assert not server._QUOTA_CB_CACHE.is_blocked(target)
