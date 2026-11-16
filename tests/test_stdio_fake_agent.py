from __future__ import annotations

import json
import select
import signal
import subprocess
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]
SCRIPT = Path(__file__).with_name("stdio_fake_agent.py")
READ_TIMEOUT_SECONDS = 3.0
STOP_TIMEOUT_SECONDS = 3.0


def _stop_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.stdin is not None and not proc.stdin.closed:
        proc.stdin.close()
    if proc.poll() is None:
        proc.terminate()
        try:
            _ = proc.wait(timeout=STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            _ = proc.wait(timeout=STOP_TIMEOUT_SECONDS)
    else:
        _ = proc.wait(timeout=STOP_TIMEOUT_SECONDS)


@contextmanager
def _running_agent(protocol: str) -> Generator[subprocess.Popen[bytes]]:
    proc = subprocess.Popen(
        [
            sys.executable,
            str(SCRIPT),
            "--protocol",
            protocol,
            "--init-banner",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    try:
        assert _read_line(proc) == {"type": "init", "status": "ready"}
        yield proc
    finally:
        _stop_process(proc)


def _send(proc: subprocess.Popen[bytes], payload: str | JsonObject) -> None:
    assert proc.stdin is not None
    line = payload if isinstance(payload, str) else json.dumps(payload)
    _ = proc.stdin.write((line + "\n").encode())
    _ = proc.stdin.flush()


def _to_json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        return [_to_json_value(item) for item in cast(list[object], value)]
    if isinstance(value, dict):
        result: JsonObject = {}
        for key, item in cast(dict[object, object], value).items():
            assert isinstance(key, str)
            result[key] = _to_json_value(item)
        return result
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _read_line(proc: subprocess.Popen[bytes]) -> JsonObject:
    assert proc.stdout is not None
    ready, _, _ = select.select([proc.stdout.fileno()], [], [], READ_TIMEOUT_SECONDS)
    assert ready, "timed out waiting for stdout"
    line = cast(bytes, proc.stdout.readline())
    assert line, f"stdout closed with return code {proc.poll()}"
    payload = _to_json_value(cast(object, json.loads(line.decode())))
    assert isinstance(payload, dict)
    return payload


def _read_until(
    proc: subprocess.Popen[bytes],
    terminal: Callable[[JsonObject], bool],
) -> list[JsonObject]:
    messages: list[JsonObject] = []
    for _ in range(8):
        message = _read_line(proc)
        messages.append(message)
        if terminal(message):
            return messages
    raise AssertionError("terminal message was not emitted")


def test_fake_agent_stream_json_turn() -> None:
    with _running_agent("stream-json") as proc:
        _send(proc, {"prompt": "hello"})
        messages = _read_until(proc, lambda item: item.get("type") == "done")

    assert [item["delta"] for item in messages[:-1]] == ["echo: ", "hello"]
    assert messages[-1] == {"type": "done"}


def test_fake_agent_stream_jsonrpc_turn() -> None:
    with _running_agent("stream-jsonrpc") as proc:
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 17,
                "method": "turn",
                "params": {"prompt": "hello"},
            },
        )
        messages = _read_until(proc, lambda item: "result" in item)

    progress = messages[:-1]
    assert progress == [
        {
            "jsonrpc": "2.0",
            "method": "progress",
            "params": {"delta": "echo: "},
        },
        {
            "jsonrpc": "2.0",
            "method": "progress",
            "params": {"delta": "hello"},
        },
    ]
    assert messages[-1] == {
        "jsonrpc": "2.0",
        "id": 17,
        "result": {"status": "ok"},
    }


def test_fake_agent_acp_turn() -> None:
    with _running_agent("acp") as proc:
        _send(proc, "turn")
        messages = _read_until(proc, lambda item: item.get("event") == "turn_complete")

    assert [item["payload"] for item in messages[:-1]] == ["echo: ", "turn"]
    assert messages[-1] == {"event": "turn_complete"}


def test_fake_agent_tool_turn_stop() -> None:
    with _running_agent("stream-json") as proc:
        _send(proc, {"prompt": "tool", "tool_call": True})
        messages = _read_until(proc, lambda item: item.get("type") == "tool_turn_stop")

    assert messages[-1] == {"type": "tool_turn_stop"}


def test_fake_agent_crash_detection() -> None:
    with _running_agent("stream-json") as proc:
        _send(proc, "__CRASH__")
        return_code = proc.wait(timeout=STOP_TIMEOUT_SECONDS)

    assert return_code != 0


def test_fake_agent_graceful_sigterm() -> None:
    with _running_agent("stream-json") as proc:
        proc.send_signal(signal.SIGTERM)
        return_code = proc.wait(timeout=STOP_TIMEOUT_SECONDS)

    assert return_code == 0
