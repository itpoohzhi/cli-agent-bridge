"""Запросы к Handler Claude-моста через BytesIO и фейковое соединение, без сокетов."""

from __future__ import annotations

import http.client
import io
import json
from types import SimpleNamespace
from typing import Any, NamedTuple

import pytest

from tests.unit._claude_bridge_tool_fakes import RunFactory, bridge as bridge  # noqa: F401

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}, "note": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]
TOOL_TAGS = (
    '<tool_call>{"name":"x"}</tool_call>',
    "<invoke>",
    "<t",
    "<tool_c",
    "<i",
    "</t",
)
HEAD_END = b"\r\n\r\n"


class Reply(NamedTuple):
    status: int
    headers: Any
    body: str


class DummyConnection:
    """Фейк сокета: rfile и wfile — BytesIO, `sendall` дописывает ответ в wfile."""

    def __init__(self, request: bytes = b"") -> None:
        self.rfile = io.BytesIO(request)
        self.wfile = io.BytesIO()

    @classmethod
    def for_post(cls, payload: dict) -> DummyConnection:
        body = json.dumps(payload).encode("utf-8")
        head = [
            "POST /v1/chat/completions HTTP/1.1",
            "Host: bridge.test",
            "Content-Type: application/json",
            "Authorization: Bearer test-key",
            f"Content-Length: {len(body)}",
        ]
        return cls(("\r\n".join(head) + "\r\n\r\n").encode("ascii") + body)

    def makefile(self, mode: str, bufsize: int = -1) -> io.BytesIO:
        return self.rfile if "r" in mode else self.wfile

    def settimeout(self, value: float | None) -> None:
        return None

    def sendall(self, data: bytes) -> None:
        self.wfile.write(data)

    def written(self) -> bytes:
        return self.wfile.getvalue()


def parse_reply(raw: bytes) -> Reply:
    response = http.client.HTTPResponse(DummyConnection(raw))  # type: ignore[arg-type]
    response.begin()
    return Reply(response.status, response.msg, response.read().decode("utf-8"))


def split_raw(raw: bytes) -> tuple[str, str]:
    """Статусная строка и тело ещё не завершённого ответа."""
    head, _, body = raw.partition(HEAD_END)
    return head.decode("ascii").splitlines()[0], body.decode("utf-8")


class Harness:
    """Один Handler.handle_one_request на запрос, с подставленным `Run`."""

    def __init__(self, module: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        self.module = module
        self.monkeypatch = monkeypatch

    def play(self, script: list) -> RunFactory:
        runs = RunFactory(script)
        self.monkeypatch.setattr(self.module, "Run", runs)
        return runs

    def post(self, payload: dict, conn: DummyConnection | None = None) -> Reply:
        conn = conn or DummyConnection.for_post(payload)
        self.module.Handler(conn, ("127.0.0.1", 50000), SimpleNamespace())
        return parse_reply(conn.written())


@pytest.fixture
def harness(bridge: Any, monkeypatch: pytest.MonkeyPatch) -> Harness:
    return Harness(bridge, monkeypatch)


def set_toolless_policy(monkeypatch: pytest.MonkeyPatch, policy: str | None) -> None:
    if policy is None:
        monkeypatch.delenv("BRIDGE_TOOLLESS_TOOL_TAG_POLICY", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_TOOLLESS_TOOL_TAG_POLICY", policy)


def sse_payloads(body: str) -> list:
    return [
        json.loads(line[6:])
        for line in body.splitlines()
        if line.startswith("data: ") and line[6:] != "[DONE]"
    ]


def sse_delta_text(body: str, field: str) -> str:
    return "".join(
        choice["delta"].get(field) or ""
        for frame in sse_payloads(body)
        for choice in frame.get("choices") or []
    )


def sse_calls(frames: list) -> list:
    return [
        call
        for frame in frames
        for choice in frame.get("choices", [])
        for call in choice["delta"].get("tool_calls", [])
    ]
