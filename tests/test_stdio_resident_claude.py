"""Contract tests for the Claude Code resident stdio driver."""

from __future__ import annotations

import json

from core.stdio_resident.claude_driver import ClaudeStreamJsonDriver


def test_claude_driver_capabilities() -> None:
    driver = ClaudeStreamJsonDriver()

    assert driver.capabilities.protocol_name == "claude-stream-json"
    assert driver.capabilities.supports_soft_cancel is True
    assert driver.capabilities.supports_multi_turn is True


def test_claude_driver_build_argv() -> None:
    driver = ClaudeStreamJsonDriver()
    base_argv = ["claude", "--model", "sonnet"]

    argv = driver.build_argv(base_argv, {"permission_mode": "default"})

    assert base_argv == ["claude", "--model", "sonnet"]
    assert argv[:3] == base_argv
    assert "--print" in argv
    assert argv[argv.index("--input-format") + 1] == "stream-json"
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert argv[argv.index("--permission-mode") + 1] == "default"


def test_claude_driver_encode_turn() -> None:
    driver = ClaudeStreamJsonDriver()

    encoded = driver.encode_turn("Привет", {"session_id": "session-1"})

    assert encoded.endswith(b"\n")
    assert json.loads(encoded) == {
        "type": "user",
        "message": {"role": "user", "content": "Привет"},
        "session_id": "session-1",
    }


def test_claude_driver_decode_stream_events() -> None:
    driver = ClaudeStreamJsonDriver()
    text = driver.decode_line(
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"delta":{"type":"text_delta","text":"hello"}}}'
    )
    thinking = driver.decode_line(
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"delta":{"type":"thinking_delta","thinking":"considering"}}}'
    )
    terminal = driver.decode_line(
        '{"type":"result","result":"done","is_error":false}'
    )
    error = driver.decode_line(
        '{"type":"result","is_error":true,"result":"rate limit"}'
    )
    tool = driver.decode_line(
        '{"type":"stream_event","event":{"type":"content_block_start",'
        '"content_block":{"type":"tool_use","id":"tool-1",'
        '"name":"Read","input":{"path":"README.md"}}}}'
    )

    assert text is not None and text.text == "hello"
    assert thinking is not None and thinking.reasoning == "considering"
    assert terminal is not None and terminal.text == "done"
    assert terminal.is_terminal is True
    assert driver.is_terminal("", terminal) is True
    assert error is not None and error.text == "rate limit"
    assert error.is_terminal is True
    assert error.raw["is_error"] is True
    assert tool is not None and tool.tool_calls[0]["name"] == "Read"
    assert driver.is_tool_stop("", tool) is True
    assert driver.decode_line("") is None
    assert driver.decode_line("# comment") is None
    assert driver.decode_line("not-json") is None


def test_claude_driver_handshake_liveness() -> None:
    class Handle:
        def __init__(self) -> None:
            self.calls = 0

        def is_alive(self) -> bool:
            self.calls += 1
            return True

    driver = ClaudeStreamJsonDriver()
    handle = Handle()

    assert driver.handshake(handle) is True
    assert handle.calls == 1
