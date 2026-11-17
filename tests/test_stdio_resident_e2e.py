from __future__ import annotations

# pyright: reportAny=false, reportExplicitAny=false, reportPrivateUsage=false

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast, override

import pytest

from adapters.stdio_resident_adapter import StdioResidentAdapter
from core.stdio_resident.process_io import ResidentProcessHandle
from core.stdio_resident.protocol_driver import DecodedChunk, StreamJsonDriver
from core.stdio_resident.session_manager import StdioSessionManager
from core.stdio_resident.types import SlotAffinityKey

ROOT = Path(__file__).resolve().parents[1]
FAKE_AGENT = ROOT / "tests" / "stdio_fake_agent.py"
HOT_TURN_TTFT_LIMIT_S = 0.45
CANCEL_GRACE_S = 0.1


def _config(*, delay_s: float = 0.0) -> dict[str, Any]:
    argv = [
        sys.executable,
        str(FAKE_AGENT),
        "--protocol",
        "stream-json",
    ]
    if delay_s:
        argv.extend(("--delay", str(delay_s)))
    return {
        "bridge": {
            "options": {
                "protocol": "stream-json",
                "cli_argv": argv,
                "output_format_args": [],
            }
        }
    }


def _request(cwd: Path, chat_key: str, prompt: str) -> dict[str, Any]:
    return {
        "owner_hash": "e2e-owner",
        "chat_key": chat_key,
        "model": "fake-model",
        "effort": "medium",
        "cwd": str(cwd),
        "prompt": prompt,
    }


def _content(chunks: list[dict[str, Any]]) -> str:
    return "".join(
        str(chunk["choices"][0]["delta"].get("content", ""))
        for chunk in chunks
    )


def _only_handle(adapter: StdioResidentAdapter) -> ResidentProcessHandle:
    slots = cast(dict[str, Any], adapter._pool._slots)
    assert len(slots) == 1
    return cast(ResidentProcessHandle, next(iter(slots.values())).handle)


@pytest.fixture
def resident_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_STDIO_RESIDENT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_STDIO_MAX_SLOTS", "4")
    monkeypatch.setenv("BRIDGE_STDIO_CANCEL_GRACE_S", str(CANCEL_GRACE_S))


def test_cold_start_then_hot_turn_reuses_pid_and_has_fast_ttft(
    resident_env: None,
    tmp_path: Path,
) -> None:
    adapter = StdioResidentAdapter(_config())
    try:
        first_chunks = list(
            adapter.execute_chat(_request(tmp_path, "chat-hot", "first turn"))
        )
        first_handle = _only_handle(adapter)
        first_pid = first_handle.pid

        started_at = time.monotonic()
        second_stream = adapter.execute_chat(
            _request(tmp_path, "chat-hot", "second turn")
        )
        first_hot_chunk = next(second_stream)
        hot_ttft_s = time.monotonic() - started_at
        second_chunks = [first_hot_chunk, *second_stream]
        second_handle = _only_handle(adapter)

        assert _content(first_chunks) == "echo: first turn"
        assert _content(second_chunks).endswith("second turn")
        assert "first turn" not in _content(second_chunks)
        assert first_handle.generation == 2
        assert second_handle.pid == first_pid
        assert hot_ttft_s < HOT_TURN_TTFT_LIMIT_S
        assert second_chunks[-1]["choices"][0]["finish_reason"] == "stop"
    finally:
        adapter.shutdown(timeout_s=1.0)


def test_client_cancellation_uses_grace_and_next_turn_starts_clean_process(
    resident_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed_graces: list[float] = []
    original_terminate = ResidentProcessHandle.terminate_gracefully

    def record_terminate(
        self: ResidentProcessHandle,
        grace_s: float,
        timeout_s: float = 2.0,
    ) -> int:
        observed_graces.append(grace_s)
        return original_terminate(self, grace_s, timeout_s)

    monkeypatch.setattr(
        ResidentProcessHandle,
        "terminate_gracefully",
        record_terminate,
    )
    adapter = StdioResidentAdapter(_config(delay_s=0.05))
    cancel_event = threading.Event()
    cwd = os.path.realpath(tmp_path)
    affinity_key = SlotAffinityKey(
        owner_hash="e2e-owner",
        chat_key="chat-cancel",
        backend_id=adapter.id,
        model="fake-model",
        effort="medium",
        cwd_norm=cwd,
    )
    try:
        cancelled_stream = adapter._session_manager.execute_turn_stream(
            affinity_key=affinity_key,
            prompt="cancelled history",
            argv_builder=adapter._build_argv,
            cwd=cwd,
            cancel_event=cancel_event,
        )
        first_chunk = next(cancelled_stream)
        cancelled_handle = _only_handle(adapter)
        cancelled_pid = cancelled_handle.pid
        assert first_chunk.text == "echo: "

        cancel_event.set()
        assert list(cancelled_stream) == []
        assert observed_graces == [CANCEL_GRACE_S]
        assert not cancelled_handle.is_alive()
        assert not adapter._pool._slots

        fresh_chunks = list(
            adapter.execute_chat(_request(tmp_path, "chat-cancel", "fresh turn"))
        )
        fresh_handle = _only_handle(adapter)
        assert fresh_handle.pid != cancelled_pid
        assert _content(fresh_chunks) == "echo: fresh turn"
        assert "cancelled history" not in _content(fresh_chunks)
    finally:
        adapter.shutdown(timeout_s=1.0)


def test_chat_keys_are_isolated_while_each_chat_keeps_its_pid(
    resident_env: None,
    tmp_path: Path,
) -> None:
    adapter = StdioResidentAdapter(_config())
    try:
        chat_a_first = list(adapter.execute_chat(_request(tmp_path, "chat-a", "a1")))
        slots = cast(dict[str, Any], adapter._pool._slots)
        pid_a = next(iter(slots.values())).handle.pid

        chat_b = list(adapter.execute_chat(_request(tmp_path, "chat-b", "b1")))
        pids_after_b = {
            entry.affinity_key.chat_key: entry.handle.pid
            for entry in slots.values()
        }
        chat_a_second = list(
            adapter.execute_chat(_request(tmp_path, "chat-a", "a2"))
        )
        pids_final = {
            entry.affinity_key.chat_key: entry.handle.pid
            for entry in slots.values()
        }

        assert pids_after_b["chat-a"] == pid_a
        assert pids_after_b["chat-b"] != pid_a
        assert pids_final == pids_after_b
        assert _content(chat_a_first) == "echo: a1"
        assert _content(chat_b) == "echo: b1"
        assert _content(chat_a_second).endswith("a2")
        assert "b1" not in _content(chat_a_second)
    finally:
        adapter.shutdown(timeout_s=1.0)


class _BlockFormattingDriver(StreamJsonDriver):
    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        decoded = super().decode_line(raw_line)
        if decoded is None or decoded.is_terminal:
            return decoded
        decoded.text = "Block one." if decoded.text == "echo: " else "Block two."
        return decoded


class _ReasoningIsolationDriver(StreamJsonDriver):
    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        decoded = super().decode_line(raw_line)
        if decoded is None or decoded.is_terminal:
            return decoded
        if decoded.text == "echo: ":
            decoded.text = ""
            decoded.tool_calls = [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "probe", "arguments": "{}"},
                }
            ]
        return decoded


def _install_driver(
    adapter: StdioResidentAdapter,
    driver: StreamJsonDriver,
) -> None:
    adapter._driver = driver
    adapter._session_manager = StdioSessionManager(adapter._pool, driver)


def test_stream_blocks_are_separated_and_post_tool_text_is_reasoning(
    resident_env: None,
    tmp_path: Path,
) -> None:
    formatting_adapter = StdioResidentAdapter(_config())
    reasoning_adapter = StdioResidentAdapter(_config())
    try:
        _install_driver(formatting_adapter, _BlockFormattingDriver())
        formatted = list(
            formatting_adapter.execute_chat(
                _request(tmp_path, "chat-format", "format blocks")
            )
        )
        assert _content(formatted) == "Block one.\n\nBlock two."

        _install_driver(reasoning_adapter, _ReasoningIsolationDriver())
        isolated = list(
            reasoning_adapter.execute_chat(
                _request(tmp_path, "chat-reasoning", "private reasoning")
            )
        )
        deltas = [chunk["choices"][0]["delta"] for chunk in isolated]
        assert any(delta.get("tool_calls") for delta in deltas)
        assert "".join(str(delta.get("content", "")) for delta in deltas) == ""
        assert (
            "".join(str(delta.get("reasoning_content", "")) for delta in deltas)
            == "private reasoning"
        )
    finally:
        formatting_adapter.shutdown(timeout_s=1.0)
        reasoning_adapter.shutdown(timeout_s=1.0)
