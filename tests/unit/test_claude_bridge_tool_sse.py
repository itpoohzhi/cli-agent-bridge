"""W3: literal SSE выдаётся до завершения upstream, а не буферизуется до EOF."""

from __future__ import annotations

import http.client
import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.unit.test_claude_bridge_tool_mode import (
    _FakeRun,
    _set_toolless_policy,
    bridge as bridge,
    http_bridge as http_bridge,
    legacy,
)


def _read_literal_prefix(
    response: http.client.HTTPResponse, expected: str
) -> list[str]:
    parts: list[str] = []
    while "".join(parts) != expected:
        line = response.readline().decode()
        assert line
        for frame in legacy._sse_payloads(line):
            assert "error" not in frame
            parts.extend(
                choice["delta"].get("content", "") for choice in frame["choices"]
            )
    return parts


def _start_stream(conn: http.client.HTTPConnection) -> http.client.HTTPResponse:
    conn.request(
        "POST",
        "/v1/chat/completions",
        json.dumps({"stream": True, "messages": []}),
        {"Content-Type": "application/json", "Authorization": "Bearer test-key"},
    )
    return conn.getresponse()


def _assert_live_prefix(
    response: http.client.HTTPResponse, expected: str, queues: list[Any]
) -> None:
    assert response.status == 200
    parts = _read_literal_prefix(response, expected)
    assert len([part for part in parts if part]) > 2
    assert queues[0].empty()


def test_off_text_sse_emits_literal_before_upstream_done(
    http_bridge: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge, port = http_bridge
    _set_toolless_policy(monkeypatch, None)
    expected = 'P1<tool_call>{"name":"x"}</tool_call> <invoke> P2'
    queues = []

    class DeferredRun(_FakeRun):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            queues.append(self.q)

    monkeypatch.setattr(bridge, "Run", DeferredRun)
    _FakeRun.script = [("text", ch) for ch in expected]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        response = _start_stream(conn)
        try:
            _assert_live_prefix(response, expected, queues)
        finally:
            for events in queues:
                for event in legacy._done_script():
                    events.put(event)
        assert response.read().decode().endswith("data: [DONE]\n\n")
    finally:
        conn.close()
