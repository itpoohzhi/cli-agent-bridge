"""Транспортный смоук Claude-моста: один реальный HTTP-сервер на модуль."""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from tests.unit._claude_bridge_tool_fakes import RunFactory, load_bridge, text_script
from tests.unit._claude_bridge_tool_http import (
    TOOLS,
    set_toolless_policy,
    sse_calls,
    sse_payloads,
)

TAGGED = 'safe <tool_call>{"name":"x"}</tool_call>'
CALL = '<tool_call>{"name":"get_weather","arguments":{"city":"Oslo","note":""}}</tool_call>'


def _tracked_server(module: Any) -> Any:
    class Tracked(module.Server):
        handled: list[threading.Thread] = []

        def process_request_thread(self, request: Any, client_address: Any) -> None:
            self.handled.append(threading.current_thread())
            super().process_request_thread(request, client_address)

    return Tracked(("127.0.0.1", 0), module.Handler)


@pytest.fixture(scope="module")
def served() -> Iterator[SimpleNamespace]:
    with pytest.MonkeyPatch.context() as mp:
        module = load_bridge(mp)
        runs = RunFactory(())
        mp.setattr(module, "AUTH_KEY", "test-key")
        mp.setattr(module, "STDERR_DRAIN_S", 0.0)
        mp.setattr(module, "Run", runs)
        server = _tracked_server(module)
        serve = {"target": server.serve_forever, "kwargs": {"poll_interval": 0.01}}
        thread = threading.Thread(daemon=True, **serve)
        thread.start()
        try:
            yield SimpleNamespace(
                port=server.server_address[1], server=server, runs=runs
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            assert not thread.is_alive()


def _post(served: SimpleNamespace, script: list, payload: dict) -> tuple[int, str]:
    served.runs.script = tuple(script)
    served.runs.runs.clear()
    headers = {"Authorization": "Bearer test-key", "Connection": "close"}
    conn = http.client.HTTPConnection("127.0.0.1", served.port, timeout=5)
    try:
        conn.request("POST", "/v1/chat/completions", json.dumps(payload), headers)
        response = conn.getresponse()
        return response.status, response.read().decode("utf-8")
    finally:
        conn.close()
        for handler in list(served.server.handled):
            handler.join(timeout=5)
            assert not handler.is_alive()
        served.server.handled.clear()


def test_off_text_literal_over_http(
    served: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_toolless_policy(monkeypatch, "text")
    status, body = _post(served, text_script(TAGGED, 7), {"messages": []})
    message = json.loads(body)["choices"][0]["message"]
    assert (status, message["content"]) == (200, TAGGED)
    assert served.runs.closed == [True]


@pytest.mark.parametrize(
    "policy,extra",
    (("error", {}), ("text", {"tools": TOOLS, "tool_choice": "none"})),
    ids=("off-error", "forbid"),
)
def test_tag_stream_rejected_over_http(
    served: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, policy: str, extra: dict
) -> None:
    set_toolless_policy(monkeypatch, policy)
    status, body = _post(served, text_script(TAGGED, 7), {"messages": [], **extra})
    assert status == 502 and "<" not in body
    assert json.loads(body)["error"]["type"] == "proxy_error"
    assert served.runs.closed == [True]


def test_emulate_tool_call_json_over_http(served: SimpleNamespace) -> None:
    payload = {"tools": TOOLS, "messages": []}
    status, body = _post(served, text_script(CALL, 9), payload)
    choice = json.loads(body)["choices"][0]
    call = choice["message"]["tool_calls"][0]["function"]
    assert (status, choice["finish_reason"]) == (200, "tool_calls")
    assert call["name"] == "get_weather"
    assert json.loads(call["arguments"]) == {"city": "Oslo"}


def test_emulate_tool_call_sse_over_http(served: SimpleNamespace) -> None:
    payload = {"stream": True, "tools": TOOLS, "messages": []}
    status, body = _post(served, text_script(CALL, 9), payload)
    frames = sse_payloads(body)
    calls = sse_calls(frames)
    assert status == 200 and body.endswith("data: [DONE]\n\n")
    assert frames[-1]["choices"][0]["finish_reason"] == "tool_calls"
    assert [call["function"]["name"] for call in calls] == ["get_weather"]
    assert json.loads(calls[0]["function"]["arguments"]) == {"city": "Oslo"}
