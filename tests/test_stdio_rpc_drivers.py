from __future__ import annotations

# pyright: reportAny=false, reportMissingImports=false, reportUnknownMemberType=false, reportUntypedFunctionDecorator=false

import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.stdio_resident.protocol_driver import (
    DecodedChunk,
    StdioProtocolDriver,
    StreamJsonDriver,
)
from core.stdio_resident.rpc_drivers import (
    AcpDriver,
    StreamJsonRpcDriver,
    create_protocol_driver,
)


def test_stream_jsonrpc_driver_contract() -> None:
    driver = StreamJsonRpcDriver()

    assert driver.capabilities.protocol_name == "stream-jsonrpc"
    assert driver.capabilities.supports_soft_cancel is True
    assert driver.build_argv(["process"], {}) == [
        "process",
        "--output-format",
        "stream-jsonrpc",
    ]
    request = json.loads(driver.encode_turn("hello", {"session_id": "s-1"}))
    assert request == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "send_turn",
        "params": {"prompt": "hello", "session_id": "s-1"},
    }
    assert json.loads(driver.encode_turn("again"))["id"] == 2

    progress = driver.decode_line(
        '{"jsonrpc":"2.0","method":"progress","params":'
        + '{"delta":"part","reasoning":"why"}}'
    )
    final = driver.decode_line('{"jsonrpc":"2.0","id":1,"result":{"text":"done"}}')
    tool_stop = driver.decode_line(
        '{"jsonrpc":"2.0","id":2,"result":{"tool_stop":true}}'
    )

    assert progress is not None
    assert progress.text == "part"
    assert progress.reasoning == "why"
    assert progress.is_terminal is False
    assert final is not None
    assert final.text == "done"
    assert final.is_terminal is True
    assert tool_stop is not None and tool_stop.is_tool_stop is True
    assert driver.is_terminal("", final) is True
    assert json.loads(driver.build_cancel_payload() or b"") == {
        "jsonrpc": "2.0",
        "method": "cancel",
        "params": {},
    }


def test_acp_driver_contract() -> None:
    driver = AcpDriver()

    assert driver.capabilities.protocol_name == "acp"
    assert driver.capabilities.supports_multi_turn is True
    assert driver.build_argv(["process"], {}) == [
        "process",
        "--output-format",
        "acp",
    ]
    assert json.loads(driver.encode_turn("hello", {"session_id": "s-1"})) == {
        "event": "turn",
        "payload": "hello",
        "session_id": "s-1",
    }

    stream = driver.decode_line('{"event":"stream","payload":"part"}')
    complete = driver.decode_line('{"event":"turn_complete"}')
    tool_stop = driver.decode_line('{"event":"tool_stop"}')

    assert stream is not None and stream.text == "part"
    assert stream.is_terminal is False
    assert complete is not None and complete.is_terminal is True
    assert tool_stop is not None and tool_stop.is_tool_stop is True
    assert driver.is_terminal("", complete) is True
    assert json.loads(driver.build_cancel_payload() or b"") == {"event": "cancel"}


def test_create_protocol_driver_factory() -> None:
    assert isinstance(create_protocol_driver("stream-json"), StreamJsonDriver)
    assert isinstance(create_protocol_driver("stream-jsonrpc"), StreamJsonRpcDriver)
    assert isinstance(create_protocol_driver("acp"), AcpDriver)
    with pytest.raises(ValueError, match="unsupported stdio protocol"):
        _ = create_protocol_driver("unknown")


def _exchange(protocol: str, driver: StdioProtocolDriver) -> list[DecodedChunk]:
    script = Path(__file__).with_name("stdio_fake_agent.py")
    completed = subprocess.run(
        [sys.executable, str(script), "--protocol", protocol],
        input=driver.encode_turn(
            "resident hello",
            {"prompt": "resident hello"} if protocol == "acp" else None,
        ),
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
    return chunks


def test_jsonrpc_driver_with_fake_agent() -> None:
    chunks = _exchange("stream-jsonrpc", StreamJsonRpcDriver())

    assert "".join(chunk.text for chunk in chunks) == "echo: resident hello"
    assert chunks[-1].is_terminal is True


def test_acp_driver_with_fake_agent() -> None:
    chunks = _exchange("acp", AcpDriver())

    assert "".join(chunk.text for chunk in chunks) == "echo: resident hello"
    assert chunks[-1].is_terminal is True


@pytest.mark.parametrize(
    ("name", "driver_type"),
    [
        ("stream-json", StreamJsonDriver),
        ("stream-jsonrpc", StreamJsonRpcDriver),
        ("acp", AcpDriver),
    ],
)
def test_shared_driver_protocol_compliance(
    name: str, driver_type: type[StdioProtocolDriver]
) -> None:
    driver = driver_type()

    assert isinstance(driver, StdioProtocolDriver)
    assert driver.capabilities.protocol_name == name
    assert isinstance(driver.build_argv(["process"], {}), list)
    assert driver.encode_turn("hello").endswith(b"\n")
    assert driver.decode_line("") is None
    assert driver.is_terminal("", None) is False
    assert driver.is_tool_stop("", None) is False
