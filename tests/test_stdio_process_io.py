"""Tests for generation-aware resident process I/O."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from core.stdio_resident.process_io import (
    ResidentProcessHandle,
    StdioWriteError,
    TaggedLine,
)

ROOT = Path(__file__).resolve().parents[1]
FAKE_PROCESS = ROOT / "tests" / "stdio_fake_agent.py"


def _spawn(*extra_args: str) -> ResidentProcessHandle:
    return ResidentProcessHandle.spawn(
        [sys.executable, str(FAKE_PROCESS), *extra_args],
        cwd=str(ROOT),
    )


def test_process_handle_spawn_and_lifecycle() -> None:
    handle = _spawn()
    try:
        assert handle.is_alive()
        returncode = handle.terminate_gracefully(grace_s=0.5)
        assert isinstance(returncode, int)
        assert not handle.is_alive()
    finally:
        if handle.is_alive():
            _ = handle.terminate_gracefully(grace_s=0.1)


def test_process_handle_write_and_read_lines() -> None:
    handle = _spawn()
    try:
        handle.write(b"hello\n")
        tagged = handle.read_line(timeout_s=2.0)

        assert tagged is not None
        assert tagged.line
        assert tagged.generation == handle.generation
        assert tagged.pid == handle.pid
        assert not tagged.is_stderr
    finally:
        _ = handle.terminate_gracefully(grace_s=0.5)


def test_process_handle_drops_late_events_on_generation_advance() -> None:
    handle = _spawn()
    try:
        previous_generation = handle.generation
        active_generation = handle.advance_generation()
        handle._queue.put(  # pyright: ignore[reportPrivateUsage]
            TaggedLine(
                line="late",
                generation=previous_generation,
                pid=handle.pid,
            )
        )
        expected = TaggedLine(
            line="current",
            generation=active_generation,
            pid=handle.pid,
        )
        handle._queue.put(expected)  # pyright: ignore[reportPrivateUsage]

        assert handle.read_line(timeout_s=0.5) == expected
    finally:
        _ = handle.terminate_gracefully(grace_s=0.5)


def test_process_handle_write_epipe_to_broken() -> None:
    handle = _spawn()
    try:
        handle.write(b"__CRASH__\n")
        _ = handle.proc.wait(timeout=2.0)

        with pytest.raises(StdioWriteError):
            handle.write(b"after-exit\n")
    finally:
        _ = handle.terminate_gracefully(grace_s=0.1)


def test_process_handle_sliding_activity() -> None:
    handle = _spawn()
    try:
        initial_activity = handle.last_activity_mono
        time.sleep(0.01)
        handle.write(b"activity\n")
        tagged = handle.read_line(timeout_s=2.0)

        assert tagged is not None
        assert tagged.timestamp_mono > initial_activity
        assert handle.last_activity_mono >= tagged.timestamp_mono
    finally:
        _ = handle.terminate_gracefully(grace_s=0.5)
