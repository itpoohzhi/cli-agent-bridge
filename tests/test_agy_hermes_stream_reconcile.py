# pyright: reportAny=false, reportExplicitAny=false, reportPrivateUsage=false
"""End-to-end AD-004 tests: terminal-text reconciliation in stream_driver_turn (W2-A).

Проверяем, что allowlist-протокол `agy-stream-json` теряет дубль terminal-текста
(progressive "PONG" + terminal "PONG" -> суммарно строго "PONG"), а все остальные
протоколы проходят через `stream_driver_turn` без модификации кадров.
"""

from __future__ import annotations

import json
import queue
from collections.abc import Iterator, Mapping
from types import SimpleNamespace
from typing import Any

import pytest

from core.stdio_resident.process_io import LINE, TIMEOUT
from core.stdio_resident.protocol_driver import DecodedChunk, DriverCapabilities
from core.stdio_resident.runtime_wire import stream_driver_turn
from core.turn_usage import UsageUpdate

_USAGE = UsageUpdate(input_tokens=11, output_tokens=7, source="agy-w2a-test")
_TOOL_CALLS: list[dict[str, Any]] = [
    {
        "id": "call-1",
        "type": "function",
        "function": {"name": "bash", "arguments": '{"command":"pwd"}'},
    }
]


class _FakeHandle:
    """Скриптованный stdout: отдаёт заранее заданные строки без реального I/O."""

    def __init__(self, lines: list[str]) -> None:
        self.generation = 1
        self.written: list[bytes] = []
        self._lines: queue.Queue[str] = queue.Queue()
        for line in lines:
            self._lines.put(line)

    def write(self, data: bytes) -> None:
        self.written.append(data)

    def read_line_outcome(self, timeout_s: float = 0.05) -> tuple[str, Any]:
        _ = timeout_s
        try:
            line = self._lines.get_nowait()
        except queue.Empty:
            return (TIMEOUT, None)
        return (LINE, SimpleNamespace(line=line, is_stderr=False))


class _ScriptedDriver:
    """Фейковый NDJSON-драйвер: строка -> готовый DecodedChunk."""

    def __init__(
        self,
        protocol: str,
        frames: list[tuple[str, DecodedChunk]],
        *,
        protocol_attr: str | None = None,
    ) -> None:
        self.capabilities = DriverCapabilities(protocol_name=protocol)
        self.protocol: str | None = protocol_attr
        self._frames: dict[str, DecodedChunk] = dict(frames)

    def encode_turn(
        self, prompt: str, turn_context: Mapping[str, Any] | None = None
    ) -> bytes:
        _ = turn_context
        return (json.dumps({"prompt": prompt}) + "\n").encode("utf-8")

    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        return self._frames.get(raw_line)

    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        _ = raw_line
        return bool(decoded is not None and decoded.is_terminal)


class _CustomStreamDriver(_ScriptedDriver):
    """Драйвер с собственным `stream_turn` (custom-путь runtime_wire)."""

    def __init__(self, protocol: str, chunks: list[DecodedChunk]) -> None:
        super().__init__(protocol, [])
        self._chunks = chunks

    def stream_turn(self, handle: Any, envelope: Any) -> Iterator[DecodedChunk]:
        _ = handle, envelope
        yield from self._chunks


def _run_turn(driver: Any, lines: list[str]) -> list[DecodedChunk]:
    handle = _FakeHandle(lines)
    envelope = SimpleNamespace(emulate_tools=False)
    ctx: dict[str, Any] = {"prompt": "ping", "timeouts": (1.0, 2.0)}
    dispatched: list[bool] = []
    chunks = list(
        stream_driver_turn(
            driver, handle, envelope, ctx, lambda: dispatched.append(True)
        )
    )
    custom = any(
        callable(getattr(driver, n, None))
        for n in ("stream_turn", "execute_turn", "run_turn")
    )
    if not custom:
        assert dispatched == [True]
        assert handle.written, "turn input must be dispatched to the handle"
    return chunks


def _terminal_pong() -> DecodedChunk:
    return DecodedChunk(
        text="PONG",
        reasoning="checked inputs",
        tool_calls=list(_TOOL_CALLS),
        is_terminal=True,
        usage=_USAGE,
    )


def test_agy_progressive_plus_terminal_dedup_to_single_pong() -> None:
    terminal = _terminal_pong()
    driver = _ScriptedDriver(
        "agy-stream-json",
        [
            ("p1", DecodedChunk(text="PO")),
            ("p2", DecodedChunk(text="NG")),
            ("t1", terminal),
        ],
    )
    chunks = _run_turn(driver, ["p1", "p2", "t1"])

    assert "".join(c.text for c in chunks) == "PONG"
    assert chunks[0].text == "PO" and chunks[1].text == "NG"
    last = chunks[-1]
    assert last.text == ""
    assert last.is_terminal is True and last.is_tool_stop is False
    assert last.reasoning == "checked inputs"
    assert last.tool_calls == _TOOL_CALLS
    assert last.usage is _USAGE


def test_agy_terminal_tail_after_progressive_is_kept() -> None:
    driver = _ScriptedDriver(
        "agy-stream-json",
        [
            ("p1", DecodedChunk(text="PONG")),
            ("t1", DecodedChunk(text="PONG!", is_terminal=True)),
        ],
    )
    chunks = _run_turn(driver, ["p1", "t1"])

    assert "".join(c.text for c in chunks) == "PONG!"
    assert chunks[-1].text == "!" and chunks[-1].is_terminal is True


def test_agy_divergent_terminal_text_passes_through() -> None:
    driver = _ScriptedDriver(
        "agy-stream-json",
        [
            ("p1", DecodedChunk(text="PONG")),
            ("t1", DecodedChunk(text="OTHER", is_terminal=True)),
        ],
    )
    chunks = _run_turn(driver, ["p1", "t1"])

    assert "".join(c.text for c in chunks) == "PONGOTHER"


@pytest.mark.parametrize(
    "protocol", ["codex-jsonl", "claude-stream-json", "muse-msp-v1", "stream-json"]
)
def test_non_agy_protocol_stream_is_not_modified(protocol: str) -> None:
    progressive = DecodedChunk(text="PONG")
    terminal = _terminal_pong()
    driver = _ScriptedDriver(protocol, [("p1", progressive), ("t1", terminal)])
    chunks = _run_turn(driver, ["p1", "t1"])

    assert "".join(c.text for c in chunks) == "PONGPONG"
    assert chunks[0] is progressive and chunks[1] is terminal
    assert chunks[1].reasoning == "checked inputs"
    assert chunks[1].tool_calls == _TOOL_CALLS and chunks[1].usage is _USAGE


def test_agy_custom_stream_path_is_reconciled() -> None:
    terminal = _terminal_pong()
    driver = _CustomStreamDriver(
        "agy-stream-json", [DecodedChunk(text="PO"), DecodedChunk(text="NG"), terminal]
    )
    chunks = _run_turn(driver, [])

    assert "".join(c.text for c in chunks) == "PONG"
    assert chunks[-1].text == "" and chunks[-1].is_terminal is True
    assert chunks[-1].reasoning == "checked inputs"
    assert chunks[-1].tool_calls == _TOOL_CALLS and chunks[-1].usage is _USAGE


def test_non_agy_custom_stream_path_is_not_modified() -> None:
    progressive = DecodedChunk(text="PONG")
    terminal = _terminal_pong()
    driver = _CustomStreamDriver("claude-stream-json", [progressive, terminal])
    chunks = _run_turn(driver, [])

    assert "".join(c.text for c in chunks) == "PONGPONG"
    assert chunks[0] is progressive and chunks[1] is terminal


def test_explicit_protocol_attribute_enables_reconcile() -> None:
    driver = _ScriptedDriver(
        "unknown-protocol",
        [
            ("p1", DecodedChunk(text="PONG")),
            ("t1", DecodedChunk(text="PONG", is_terminal=True)),
        ],
        protocol_attr="agy-stream-json",
    )
    chunks = _run_turn(driver, ["p1", "t1"])

    assert "".join(c.text for c in chunks) == "PONG"
    assert chunks[-1].text == "" and chunks[-1].is_terminal is True
