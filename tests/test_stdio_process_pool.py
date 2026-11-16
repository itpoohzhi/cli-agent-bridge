"""Tests for bounded resident-process allocation and teardown."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_pool import (
    ResidentProcessPool,
    SlotLeaseTimeoutError,
)
from core.stdio_resident.types import SlotAffinityKey

ROOT = Path(__file__).resolve().parents[1]
FAKE_PROCESS = ROOT / "tests" / "stdio_fake_agent.py"


def _config(*, max_slots: int = 2, lease_wait_s: float = 0.1) -> StdioPoolConfig:
    return StdioPoolConfig(
        max_slots=max_slots,
        idle_timeout_s=30.0,
        ttl_s=30.0,
        max_rss_bytes=128 * 1024 * 1024,
        lease_wait_s=lease_wait_s,
        cancel_grace_s=0.2,
        shutdown_timeout_s=0.2,
        enabled=True,
    )


def _key(name: str) -> SlotAffinityKey:
    return SlotAffinityKey(
        owner_hash=f"owner-{name}",
        chat_key=f"chat-{name}",
        backend_id="stdio",
        model="test-model",
        effort="test",
        cwd_norm=str(ROOT),
    )


def _argv() -> list[str]:
    return [sys.executable, str(FAKE_PROCESS), "--protocol", "stream-json"]


def test_pool_acquire_and_reuse_affinity() -> None:
    pool = ResidentProcessPool(_config())
    try:
        first = pool.acquire(_key("same"), _argv, str(ROOT))
        first_pid = first.handle.pid
        pool.release(first.slot_id)

        second = pool.acquire(_key("same"), _argv, str(ROOT))

        assert second.slot_id == first.slot_id
        assert second.handle.pid == first_pid
        pool.release(second.slot_id)
    finally:
        pool.shutdown()


def test_pool_lru_eviction_ready_only() -> None:
    pool = ResidentProcessPool(_config(max_slots=2))
    try:
        oldest = pool.acquire(_key("oldest"), _argv, str(ROOT))
        oldest_pid = oldest.handle.pid
        pool.release(oldest.slot_id)
        time.sleep(0.01)

        newest = pool.acquire(_key("newest"), _argv, str(ROOT))
        newest_pid = newest.handle.pid
        pool.release(newest.slot_id)

        replacement = pool.acquire(_key("replacement"), _argv, str(ROOT))

        assert not oldest.handle.is_alive()
        assert newest.handle.is_alive()
        assert replacement.handle.pid not in {oldest_pid, newest_pid}
        pool.release(replacement.slot_id)
    finally:
        pool.shutdown()


def test_pool_backpressure_when_full_busy() -> None:
    pool = ResidentProcessPool(_config(max_slots=1, lease_wait_s=0.1))
    held = pool.acquire(_key("held"), _argv, str(ROOT))
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                pool.acquire,
                _key("waiting"),
                _argv,
                str(ROOT),
            )
            error = future.exception(timeout=1.0)
            assert isinstance(error, SlotLeaseTimeoutError)
    finally:
        pool.release(held.slot_id, cancel=True)
        pool.shutdown()


def test_pool_cancel_tears_down_and_spawns_new_pid() -> None:
    pool = ResidentProcessPool(_config(max_slots=1))
    try:
        canceled = pool.acquire(_key("cancel"), _argv, str(ROOT))
        old_pid = canceled.handle.pid

        pool.release(canceled.slot_id, cancel=True)
        replacement = pool.acquire(_key("cancel"), _argv, str(ROOT))

        assert not canceled.handle.is_alive()
        assert replacement.handle.pid != old_pid
        pool.release(replacement.slot_id)
    finally:
        pool.shutdown()


def test_pool_configurable_shutdown() -> None:
    pool = ResidentProcessPool(_config(max_slots=2))
    first = pool.acquire(_key("first"), _argv, str(ROOT))
    second = pool.acquire(_key("second"), _argv, str(ROOT))

    pool.shutdown()

    assert not first.handle.is_alive()
    assert not second.handle.is_alive()
