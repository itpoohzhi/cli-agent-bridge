from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from core.stdio_resident.protocol_driver import (
    DecodedChunk,
    StdioProtocolDriver,
    StreamJsonDriver,
)


def test_stream_json_driver_capabilities() -> None:
    driver = StreamJsonDriver()

    assert isinstance(driver, StdioProtocolDriver)
    assert driver.capabilities.protocol_name == "stream-json"
    assert driver.capabilities.supports_soft_cancel is True
    assert driver.capabilities.supports_multi_turn is True


def test_stream_json_driver_build_argv() -> None:
    driver = StreamJsonDriver()
    original = ["resident-process", "--verbose"]

    assert driver.build_argv(original, {}) == [
        "resident-process",
        "--verbose",
        "--output-format",
        "stream-json",
    ]
    assert original == ["resident-process", "--verbose"]
    assert driver.build_argv(["resident-process", "--output-format=json"], {}) == [
        "resident-process",
        "--output-format=json",
    ]
    assert driver.build_argv(
        ["resident-process"],
        {"output_format_args": ["--emit", "stream-json"]},
    ) == ["resident-process", "--emit", "stream-json"]


def test_stream_json_driver_encode_turn() -> None:
    driver = StreamJsonDriver()
    encoded = driver.encode_turn("Привет", {"session_id": "turn-1"})

    assert encoded.endswith(b"\n")
    assert json.loads(encoded) == {"prompt": "Привет", "session_id": "turn-1"}
    assert driver.encode_turn("ignored", {"raw_line": "plain turn\n"}) == (
        b"plain turn\n"
    )


def test_stream_json_driver_decode_chunks() -> None:
    driver = StreamJsonDriver()

    text = driver.decode_line('{"type":"content","delta":"hello"}')
    reasoning = driver.decode_line(
        '{"delta":{"reasoning":"considering"},"type":"progress"}'
    )
    tools = driver.decode_line('{"tool_calls":[{"id":"call-1","name":"lookup"}]}')

    assert text is not None and text.text == "hello"
    assert reasoning is not None and reasoning.reasoning == "considering"
    assert tools is not None
    assert tools.tool_calls == [{"id": "call-1", "name": "lookup"}]
    assert tools.raw["tool_calls"] == tools.tool_calls


def test_stream_json_driver_terminal_detection() -> None:
    driver = StreamJsonDriver()
    done = cast(DecodedChunk, driver.decode_line('{"type":"done"}'))
    tool_stop = cast(DecodedChunk, driver.decode_line('{"type":"tool_turn_stop"}'))

    assert done.is_terminal is True
    assert driver.is_terminal("", done) is True
    assert done.is_tool_stop is False
    assert tool_stop.is_terminal is True
    assert tool_stop.is_tool_stop is True
    assert driver.is_tool_stop("", tool_stop) is True
    assert driver.is_terminal('{"done":true}', None) is True
    assert driver.is_tool_stop('{"type":"tool_turn_stop"}', None) is True


def test_stream_json_driver_invalid_json_graceful() -> None:
    driver = StreamJsonDriver()

    assert driver.decode_line("") is None
    assert driver.decode_line("   ") is None
    assert driver.decode_line("# ready") is None
    assert driver.decode_line("not-json") is None
    assert driver.decode_line("[]") is None
    assert driver.is_terminal("not-json", None) is False


def test_stream_json_driver_cancel_payload() -> None:
    payload = StreamJsonDriver().build_cancel_payload()

    assert payload == b'{"type": "cancel"}\n'
    assert json.loads(payload) == {"type": "cancel"}


def test_stream_json_driver_with_fake_agent() -> None:
    driver = StreamJsonDriver()
    script = Path(__file__).with_name("stdio_fake_agent.py")
    completed = subprocess.run(
        [sys.executable, str(script), "--protocol", "stream-json"],
        input=driver.encode_turn("resident hello"),
        capture_output=True,
        check=True,
        timeout=5,
    )

    chunks: list[DecodedChunk] = []
    for raw_line in completed.stdout.decode().splitlines():
        decoded = driver.decode_line(raw_line)
        if decoded is None:
            continue
        chunks.append(decoded)
        if driver.is_terminal(raw_line, decoded):
            break

    assert "".join(chunk.text for chunk in chunks) == "echo: resident hello"
    assert chunks[-1].is_terminal is True
