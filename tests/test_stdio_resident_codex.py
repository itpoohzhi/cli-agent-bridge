"""Contract tests for the Codex app-server resident stdio driver."""

from __future__ import annotations

import json

from core.stdio_resident.codex_driver import CodexAppServerDriver


def test_codex_driver_capabilities() -> None:
    driver = CodexAppServerDriver()

    assert driver.capabilities.protocol_name == "codex-app-server"
    assert driver.capabilities.supports_soft_cancel is True
    assert driver.capabilities.supports_multi_turn is True


def test_codex_driver_build_argv() -> None:
    driver = CodexAppServerDriver()

    assert driver.build_argv(["codex"], {}) == ["codex", "app-server"]
    assert driver.build_argv(["codex", "app-server"], {}) == [
        "codex",
        "app-server",
    ]


def test_codex_driver_encode_turn() -> None:
    driver = CodexAppServerDriver()

    first = driver.encode_turn("Привет", {"thread_id": "thread-1"})
    second = driver.encode_turn("Ещё", {"threadId": "thread-1"})

    assert first.endswith(b"\n")
    assert second.endswith(b"\n")
    assert json.loads(first) == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "turn/start",
        "params": {
            "threadId": "thread-1",
            "input": [{"type": "text", "text": "Привет"}],
        },
    }
    assert json.loads(second)["id"] == 2


def test_codex_driver_decode_stream_events() -> None:
    driver = CodexAppServerDriver()
    text = driver.decode_line(
        '{"jsonrpc":"2.0","method":"turn/delta","params":{"delta":{"content":"hello"}}}'
    )
    reasoning = driver.decode_line(
        '{"jsonrpc":"2.0","method":"turn/progress",'
        '"params":{"delta":{"reasoning":"considering"}}}'
    )
    terminal = driver.decode_line(
        '{"jsonrpc":"2.0","method":"turn/completed","params":{}}'
    )

    assert text is not None and text.text == "hello"
    assert reasoning is not None and reasoning.reasoning == "considering"
    assert terminal is not None and terminal.is_terminal is True
    assert driver.is_terminal("", terminal) is True
    assert driver.decode_line("not-json") is None
    assert driver.decode_line('{"jsonrpc":"1.0"}') is None


def test_codex_driver_error_handling() -> None:
    driver = CodexAppServerDriver()
    error = {"code": -32601, "message": "Method not found"}

    chunk = driver.decode_line(json.dumps({"jsonrpc": "2.0", "id": 2, "error": error}))

    assert chunk is not None and chunk.is_terminal is True
    assert chunk.raw == error
    assert driver.is_terminal("", chunk) is True


def test_codex_driver_cancel_and_handshake() -> None:
    driver = CodexAppServerDriver()

    cancel = driver.build_cancel_payload()
    handshake = driver.handshake_payload()

    assert cancel is not None
    assert json.loads(cancel)["method"] == "turn/cancel"
    assert json.loads(handshake)["method"] == "initialize"
