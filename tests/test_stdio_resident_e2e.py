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
from core.backend_routing_models import Transcript, TranscriptItem
from core.resident_history import build_assistant_transcript_item
from core.stdio_resident.process_io import ResidentProcessHandle
from core.stdio_resident.protocol_driver import DecodedChunk, StreamJsonDriver
from core.stdio_resident.resident_runtime import ResidentBridgeRuntime
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


def _request(cwd: Path, chat_key: str, prompt: str, rpc: Any = None) -> dict[str, Any]:
    req: dict[str, Any] = {
        "owner_hash": "e2e-owner",
        "chat_key": chat_key,
        "chat_id": chat_key,
        "model": "fake-model",
        "effort": "medium",
        "cwd": str(cwd),
        "prompt": prompt,
    }
    if rpc is not None:
        req["rpc"] = rpc
    return req


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


def _tx(*items: TranscriptItem) -> Transcript:
    return Transcript(items=items, runnable=True)


def _u(text: str) -> TranscriptItem:
    import hashlib

    digest = hashlib.sha256(f"[user]\n{text}".encode("utf-8")).hexdigest()
    return TranscriptItem("user", text, digest)


def test_cold_start_then_hot_turn_reuses_pid_and_has_fast_ttft(
    resident_env: None,
    tmp_path: Path,
) -> None:
    adapter = StdioResidentAdapter(_config())
    try:
        u1 = _u("first turn")
        first_chunks = list(
            adapter.execute_chat(
                _request(tmp_path, "chat-hot", "first turn", rpc=_tx(u1)),
                trusted_owner_hash="e2e-owner",
            )
        )
        first_handle = _only_handle(adapter)
        first_pid = first_handle.pid

        a1 = build_assistant_transcript_item(_content(first_chunks))
        assert a1 is not None
        u2 = _u("second turn")
        started_at = time.monotonic()
        second_stream = adapter.execute_chat(
            _request(tmp_path, "chat-hot", "second turn", rpc=_tx(u1, a1, u2)),
            trusted_owner_hash="e2e-owner",
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


def _start_cancelled_turn(adapter: StdioResidentAdapter, tmp_path: Path, cancel_event: threading.Event) -> int:
    cwd = os.path.realpath(tmp_path)
    key = SlotAffinityKey(owner_hash="e2e-owner", chat_key="chat-cancel", backend_id=adapter.id, model="fake-model", effort="medium", cwd_norm=cwd, env_digest="")
    stream = adapter._session_manager.execute_turn_stream(affinity_key=key, prompt="cancelled history", argv_builder=adapter._build_argv, cwd=cwd, cancel_event=cancel_event)
    first_chunk = next(stream)
    handle = _only_handle(adapter)
    assert first_chunk.text == "echo: "
    cancel_event.set()
    assert list(stream) == []
    assert not handle.is_alive() and not adapter._pool._slots
    return handle.pid


def test_client_cancellation_uses_grace_and_next_turn_starts_clean_process(
    resident_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    observed_graces: list[float] = []
    original_terminate = ResidentProcessHandle.terminate_gracefully

    def record_terminate(self: ResidentProcessHandle, grace_s: float, timeout_s: float = 2.0) -> int:
        observed_graces.append(grace_s)
        return original_terminate(self, grace_s, timeout_s)

    monkeypatch.setattr(ResidentProcessHandle, "terminate_gracefully", record_terminate)
    adapter = StdioResidentAdapter(_config(delay_s=0.05))
    try:
        cancelled_pid = _start_cancelled_turn(adapter, tmp_path, threading.Event())
        assert observed_graces == [CANCEL_GRACE_S]
        fresh_chunks = list(adapter.execute_chat(_request(tmp_path, "chat-cancel", "fresh turn"), trusted_owner_hash="e2e-owner"))
        assert _only_handle(adapter).pid != cancelled_pid
        assert _content(fresh_chunks) == "echo: fresh turn"
        assert "cancelled history" not in _content(fresh_chunks)
    finally:
        adapter.shutdown(timeout_s=1.0)


def _slot_pids(adapter: StdioResidentAdapter) -> set[int]:
    slots = cast(dict[str, Any], adapter._pool._slots)
    return {entry.handle.pid for entry in slots.values()}


def test_chat_keys_are_isolated_while_each_chat_keeps_its_pid(
    resident_env: None, tmp_path: Path,
) -> None:
    adapter = StdioResidentAdapter(_config())
    try:
        ua1 = _u("a1")
        a1 = list(adapter.execute_chat(_request(tmp_path, "chat-a", "a1", rpc=_tx(ua1)), trusted_owner_hash="e2e-owner"))
        pids_a = _slot_pids(adapter)
        assert len(pids_a) == 1
        ub1 = _u("b1")
        b1 = list(adapter.execute_chat(_request(tmp_path, "chat-b", "b1", rpc=_tx(ub1)), trusted_owner_hash="e2e-owner"))
        pids_ab = _slot_pids(adapter)
        assert len(pids_ab) == 2 and pids_a.issubset(pids_ab)
        aa1 = build_assistant_transcript_item(_content(a1))
        assert aa1 is not None
        a2 = list(adapter.execute_chat(_request(tmp_path, "chat-a", "a2", rpc=_tx(ua1, aa1, _u("a2"))), trusted_owner_hash="e2e-owner"))
        assert _slot_pids(adapter) == pids_ab
        assert _content(a1) == "echo: a1" and _content(b1) == "echo: b1"
        assert _content(a2).endswith("a2") and "b1" not in _content(a2)
    finally:
        adapter.shutdown(timeout_s=1.0)


class _BlockFormattingDriver(StreamJsonDriver):
    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        decoded = super().decode_line(raw_line)
        if decoded is None or decoded.is_terminal:
            return decoded
        if decoded.text == "echo: ":
            decoded.text = "Block one."
        else:
            decoded.text = "Block two."
            decoded.raw["step_boundary"] = True
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
    adapter._runtime = ResidentBridgeRuntime(adapter._pool, driver, adapter._config)
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
