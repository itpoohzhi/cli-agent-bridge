"""VER-004: общий tool-mode шов всех реальных passthrough-конфигураций."""

from __future__ import annotations

import http.client
import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import core.tool_emulation as emulation  # noqa: E402 - pytest console entry point.
from adapters.passthrough_adapter import PassthroughAdapter  # noqa: E402
from tests.passthrough_stream_testlib import (  # noqa: E402
    DONE,
    content,
    finish,
    tool_delta,
)
from tests.unit._passthrough_tool_sink import (  # noqa: E402
    _CollectSink,
    _MemorySocket,
)

BACKENDS = (
    "agy",
    "agy-passthrough",
    "deepseek-direct",
    "openai-key-2",
    "openai-key-3",
    "opencode-go",
    "opencode-go-claude",
    "opencode-go-sub1",
    "opencode-go-sub2",
    "opencode-zen",
)
POLICY_ENV = "BRIDGE_TOOLLESS_TOOL_TAG_POLICY"
LITERAL = '<tool_call>{"name":"x"}</tool_call> <invoke> </tool_call> пример'
FORBIDDEN = '<tool_call>{"name":"secret_fn","arguments":{}}</tool_call>'


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "noop",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def _native_call() -> dict[str, Any]:
    return {
        "id": "c1",
        "type": "function",
        "function": {"name": "secret_fn", "arguments": "{}"},
    }


def _upstream_body(
    text: str, stream: bool, *, native: bool = False, eof: bool = False
) -> bytes:
    if stream:
        events = b"".join(content(char) for char in text)
        if native:
            events += tool_delta(0, 0, call_id="c1", name="secret_fn", args="{}")
        # EOF означает закрытие транспорта без finish_reason и [DONE].
        return (
            events
            if eof
            else events + finish(0, "tool_calls" if native else "stop") + DONE
        )
    message: dict[str, Any] = {"role": "assistant", "content": text}
    if native:
        message["tool_calls"] = [_native_call()]
    return json.dumps(
        {
            "id": "chatcmpl-mode",
            "object": "chat.completion",
            "model": "m",
            "created": 1,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls" if native else "stop",
                }
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")


def _payloads(sink: _CollectSink, stream: bool) -> list[dict[str, Any]]:
    if not stream or sink.status == 502:
        return [json.loads(sink.body)]
    values = []
    for line in sink.body.splitlines():
        if line.startswith(b"data:") and line[5:].strip() != b"[DONE]":
            values.append(json.loads(line[5:]))
    return values


def _messages(sink: _CollectSink, stream: bool) -> list[dict[str, Any]]:
    return [
        choice.get("delta" if stream else "message") or {}
        for item in _payloads(sink, stream)
        for choice in item.get("choices", ())
    ]


def _published_calls(sink: _CollectSink, stream: bool) -> list[dict[str, Any]]:
    return [
        call
        for message in _messages(sink, stream)
        for call in message.get("tool_calls") or ()
    ]


def _assert_sse_fail_closed(sink: _CollectSink, payloads: list[dict[str, Any]]) -> None:
    assert sink.status == 200
    assert any(item.get("error", {}).get("type") == "stream_error" for item in payloads)
    assert sink.body.endswith(DONE)
    assert sink.body.count(DONE) == 1


def _assert_fail_closed(sink: _CollectSink, stream: bool) -> None:
    payloads = _payloads(sink, stream)
    if stream and sink.status != 502:
        _assert_sse_fail_closed(sink, payloads)
    else:
        assert sink.status == 502
        assert payloads[0].get("error")
    assert not _published_calls(sink, stream)


@pytest.fixture(scope="module")
def manifests() -> dict[str, Any]:
    found: dict[str, Any] = {}
    for path in sorted((ROOT / "providers.d").glob("*.yaml")):
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        if manifest.get("kind") == "passthrough":
            provider = manifest["provider_id"]
            assert provider not in found, f"Duplicate provider_id: {provider}"
            found[provider] = manifest
    return found


@pytest.fixture(params=BACKENDS)
def adapter(
    request: pytest.FixtureRequest,
    manifests: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[PassthroughAdapter]:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setenv("BRIDGE_INVOKE_NORMALIZATION_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "false")
    monkeypatch.setenv("BRIDGE_REPETITION_GUARD_ENABLED", "false")
    monkeypatch.setenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "true")
    monkeypatch.setenv(POLICY_ENV, "text")
    manifest = manifests[request.param]
    # Проекция YAML в реальный constructor contract. Никаких api_key_ref/env:
    # тест не читает credentials и не подключается к указанному base_url.
    config = {
        "kind": manifest["kind"],
        "base_url": manifest["transport"]["bridge"]["base_url"],
        "max_concurrent": manifest["limits"]["max_concurrent"],
    }
    instance = PassthroughAdapter(request.param, config, lambda: {}, sanitize=True)
    assert instance.limits.invoke_normalization_enabled
    try:
        yield instance
    finally:
        instance.shutdown()
        assert instance.active_count() == 0
        assert instance.process_budget.used == 0


@pytest.fixture
def parser_spies() -> Iterator[tuple[Mock, Mock]]:
    # Перехватываем сам класс, а не одно импортированное имя адаптера:
    # spy видит и прямой парсер, и создание через StreamNormalizer.for_mode.
    parser = emulation.ToolCallParser
    with (
        patch.object(
            parser, "__init__", autospec=True, side_effect=parser.__init__
        ) as init,
        patch.object(parser, "feed", autospec=True, side_effect=parser.feed) as feed,
    ):
        yield init, feed


@pytest.fixture
def call_adapter(
    adapter: PassthroughAdapter, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., _CollectSink]:
    def call(request: dict[str, Any], upstream: bytes) -> _CollectSink:
        response = http.client.HTTPResponse(_MemorySocket(upstream, request["stream"]))
        response.begin()
        connection = Mock(spec=http.client.HTTPConnection)
        connection.sock = None
        connection.getresponse.return_value = response
        open_mock = Mock(return_value=connection)
        monkeypatch.setattr(adapter, "_open", open_mock)
        sink = _CollectSink()
        try:
            adapter.handle(
                path="/v1/chat/completions",
                request=request,
                raw_body=json.dumps(request).encode("utf-8"),
                headers={},
                sink=sink,
            )
            open_mock.assert_called_once()
            assert open_mock.call_args.args[0] == "/v1/chat/completions"
            return sink
        finally:
            response.close()
            connection.close()

    return call


def _request(
    stream: bool, *, tools: bool = False, choice: Any = None
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "model": "m",
        "stream": stream,
        "messages": [{"role": "user", "content": "hi"}],
    }
    if tools:
        request["tools"] = _tools()
    if choice is not None:
        request["tool_choice"] = choice
    return request


def _assert_success(sink: _CollectSink, stream: bool) -> None:
    assert sink.status == 200
    assert not any(item.get("error") for item in _payloads(sink, stream))


def _assert_text_transport(sink: _CollectSink, stream: bool) -> None:
    if stream:
        assert sink.body.endswith(DONE)
        assert sink.body.count(DONE) == 1
    else:
        assert sink.body == _upstream_body(LITERAL, False)
