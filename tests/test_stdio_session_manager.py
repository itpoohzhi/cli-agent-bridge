"""Tests for session-scoped resident stdio turn execution."""

from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_pool import ResidentProcessPool
from core.stdio_resident.protocol_driver import DecodedChunk, StreamJsonDriver
from core.stdio_resident.session_manager import (
    SessionTurnMode,
    StdioSessionManager,
)
from core.stdio_resident.types import SlotAffinityKey

ROOT = Path(__file__).resolve().parents[1]
FAKE_PROCESS = ROOT / "tests" / "stdio_fake_agent.py"


def _config(*, max_slots: int = 2) -> StdioPoolConfig:
    return StdioPoolConfig(
        max_slots=max_slots,
        idle_timeout_s=30.0,
        ttl_s=30.0,
        max_rss_bytes=128 * 1024 * 1024,
        lease_wait_s=0.2,
        cancel_grace_s=0.2,
        shutdown_timeout_s=0.2,
        enabled=True,
    )


def _key(chat_key: str, *, owner_hash: str = "owner") -> SlotAffinityKey:
    return SlotAffinityKey(
        owner_hash=owner_hash,
        chat_key=chat_key,
        backend_id="stdio",
        model="test-model",
        effort="test",
        cwd_norm=str(ROOT),
    )


def _argv(*extra: str) -> list[str]:
    return [
        sys.executable,
        str(FAKE_PROCESS),
        "--protocol",
        "stream-json",
        *extra,
    ]


def _text(result_chunks: list[DecodedChunk]) -> str:
    return "".join(chunk.text for chunk in result_chunks)


def test_session_manager_cold_then_hot_turns() -> None:
    pool = ResidentProcessPool(_config())
    manager = StdioSessionManager(pool, StreamJsonDriver())
    try:
        first = manager.execute_turn(_key("same"), "first", _argv, str(ROOT))
        second = manager.execute_turn(_key("same"), "second", _argv, str(ROOT))

        assert first.mode is SessionTurnMode.COLD
        assert second.mode is SessionTurnMode.HOT
        assert first.pid == second.pid
        assert _text(first.chunks) == "echo: first"
        assert _text(second.chunks).endswith("second")
    finally:
        pool.shutdown()


def test_session_manager_isolation_different_chats() -> None:
    pool = ResidentProcessPool(_config(max_slots=2))
    manager = StdioSessionManager(pool, StreamJsonDriver())
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(
                manager.execute_turn,
                _key("chat-1"),
                "alpha",
                _argv,
                str(ROOT),
            )
            second_future = executor.submit(
                manager.execute_turn,
                _key("chat-2"),
                "beta",
                _argv,
                str(ROOT),
            )
            first = first_future.result(timeout=2.0)
            second = second_future.result(timeout=2.0)

        assert first.pid != second.pid
        assert _text(first.chunks) == "echo: alpha"
        assert _text(second.chunks) == "echo: beta"
    finally:
        pool.shutdown()


def test_session_manager_fingerprint_invalidation() -> None:
    pool = ResidentProcessPool(_config(max_slots=1))
    manager = StdioSessionManager(pool, StreamJsonDriver())
    try:
        first = manager.execute_turn(
            _key("same"),
            "first",
            _argv,
            str(ROOT),
            env={"SESSION_TEST": "one"},
        )
        second = manager.execute_turn(
            _key("same"),
            "second",
            _argv,
            str(ROOT),
            env={"SESSION_TEST": "two"},
        )
        third = manager.execute_turn(
            _key("same"),
            "third",
            _argv,
            str(ROOT / "tests"),
            env={"SESSION_TEST": "two"},
        )
        fourth = manager.execute_turn(
            _key("same"),
            "fourth",
            lambda: _argv("--delay", "0.001"),
            str(ROOT / "tests"),
            env={"SESSION_TEST": "two"},
        )

        assert first.pid != second.pid
        assert second.pid != third.pid
        assert third.pid != fourth.pid
        assert second.mode is SessionTurnMode.COLD
        assert fourth.mode is SessionTurnMode.COLD
        assert _text(fourth.chunks) == "echo: fourth"
    finally:
        pool.shutdown()


def test_session_manager_stream_yields_all_chunks() -> None:
    pool = ResidentProcessPool(_config())
    manager = StdioSessionManager(pool, StreamJsonDriver())
    try:
        chunks = list(
            manager.execute_turn_stream(
                _key("stream"),
                "several chunks",
                _argv,
                str(ROOT),
            )
        )

        assert [chunk.text for chunk in chunks] == ["echo: ", "several chunks", ""]
        assert chunks[-1].is_terminal is True
    finally:
        pool.shutdown()


def test_session_manager_cancel_cleans_up_process() -> None:
    pool = ResidentProcessPool(_config(max_slots=1))
    manager = StdioSessionManager(pool, StreamJsonDriver())
    cancel_event = threading.Event()
    cancel_event.set()
    try:
        canceled = manager.execute_turn(
            _key("cancel"),
            "ignored",
            _argv,
            str(ROOT),
            cancel_event=cancel_event,
        )
        replacement = manager.execute_turn(
            _key("cancel"),
            "replacement",
            _argv,
            str(ROOT),
        )

        assert canceled.pid != replacement.pid
        assert replacement.mode is SessionTurnMode.COLD
        assert _text(replacement.chunks) == "echo: replacement"
    finally:
        pool.shutdown()
