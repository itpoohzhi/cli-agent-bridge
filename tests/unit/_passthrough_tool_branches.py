"""Фабрики адаптера, HTTP-ответов и SSE для L1-тестов ветвей passthrough."""

from __future__ import annotations

import http.client
import io
import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from adapters.passthrough_adapter import PassthroughAdapter, PassthroughLimits
from core.tool_mode import NormalizerModeSpec, ToolMode, build_mode_spec
from tests.unit._passthrough_tool_sink import _CollectSink

BASE_URL = "http://127.0.0.1:9/v1"
OFF_SPEC = build_mode_spec(ToolMode.OFF)
FORBID_SPEC = build_mode_spec(ToolMode.FORBID)
EMULATE_SPEC: NormalizerModeSpec = build_mode_spec(ToolMode.EMULATE)


class _RawSocket:
    def __init__(self, raw: bytes) -> None:
        self.buffer = io.BytesIO(raw)

    def makefile(self, mode: str) -> io.BytesIO:
        assert mode == "rb"
        return self.buffer


def http_response(
    status: int, headers: Sequence[tuple[str, str]], body: bytes = b""
) -> http.client.HTTPResponse:
    """Настоящий HTTPResponse с заданными статусом и заголовками, без сети."""
    lines = [f"HTTP/1.1 {status} X"] + [f"{k}: {v}" for k, v in headers]
    lines.append(f"Content-Length: {len(body)}")
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + body
    response = http.client.HTTPResponse(_RawSocket(raw))  # type: ignore[arg-type]
    response.begin()
    return response


def completion_body(content: str = "ok", **message: Any) -> bytes:
    payload = {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content, **message},
                "finish_reason": "stop",
            }
        ],
    }
    return json.dumps(payload).encode("utf-8")


def sse_events(*payloads: Any, done: bool = True) -> bytes:
    """Склеивает payload-ы в SSE; `[DONE]` добавляется по умолчанию."""
    frames = [
        b"data: " + json.dumps(item).encode("utf-8") + b"\n\n" for item in payloads
    ]
    return b"".join(frames) + (b"data: [DONE]\n\n" if done else b"")


def delta_chunk(index: int, delta: dict[str, Any], finish: str | None = None) -> dict:
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "m",
        "choices": [{"index": index, "delta": delta, "finish_reason": finish}],
    }


def make_adapter(host: Any = None, **kwargs: Any) -> PassthroughAdapter:
    config = {"kind": "passthrough", "base_url": BASE_URL, "max_concurrent": 2}
    return PassthroughAdapter("p", config, lambda: {}, host, sanitize=True, **kwargs)


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_INVOKE_NORMALIZATION_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_REPETITION_GUARD_ENABLED", "false")


@pytest.fixture
def adapter(isolated_env: None) -> Iterator[PassthroughAdapter]:
    instance = make_adapter()
    try:
        yield instance
    finally:
        instance.shutdown()
        assert instance.active_count() == 0


@pytest.fixture
def limits(isolated_env: None) -> PassthroughLimits:
    return PassthroughLimits.from_env()


@pytest.fixture
def sink() -> _CollectSink:
    return _CollectSink()
