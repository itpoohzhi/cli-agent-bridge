"""Тесты runtime-enforcement параметров ResidentProcessPool."""

from __future__ import annotations

import asyncio
import sys
import time as real_time
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.stdio_resident.process_pool as pool_mod  # noqa: E402
from core.stdio_resident.config import StdioPoolConfig  # noqa: E402
from core.stdio_resident.process_pool import ResidentProcessPool  # noqa: E402
from core.stdio_resident.types import SlotAffinityKey  # noqa: E402


class _FakeHandle:
    """Мок ResidentProcessHandle без запуска реальных подпроцессов."""

    def __init__(
        self,
        *,
        pid: int = 1001,
        pgid: int = 1001,
        alive: bool = True,
        created_at_mono: float = 100.0,
        pgid_dead_on_terminate: bool = True,
    ) -> None:
        self.pid: int = pid
        self._pgid: int = pgid
        self._alive: bool = alive
        self.created_at_mono: float = created_at_mono
        self._pgid_dead: bool = False
        self._pgid_dead_on_terminate: bool = pgid_dead_on_terminate
        self.terminated_calls: list[float] = []
        self.generations: int = 0

    def is_alive(self) -> bool:
        return self._alive

    def advance_generation(self) -> int:
        self.generations += 1
        return self.generations

    def terminate_gracefully(self, grace_s: float = 5.0) -> bool:
        self.terminated_calls.append(grace_s)
        self._alive = False
        self._pgid_dead = self._pgid_dead_on_terminate
        return True


class _FakeTimeProxy:
    """Локальная подмена time.monotonic только для модуля process_pool."""

    def __init__(self, now_ref: list[float]) -> None:
        self._now_ref = now_ref

    def monotonic(self) -> float:
        return self._now_ref[0]

    def __getattr__(self, name: str) -> object:
        return getattr(real_time, name)


def _wait_until(predicate: Callable[[], bool], timeout_s: float = 2.0) -> None:
    """Дождаться выполнения условия с реальным таймаутом."""
    deadline = real_time.monotonic() + timeout_s
    while real_time.monotonic() < deadline:
        if predicate():
            return
        real_time.sleep(0.005)
    assert predicate()


def _key(owner: str = "owner-1") -> SlotAffinityKey:
    return SlotAffinityKey(
        owner_hash=owner,
        chat_key="chat",
        backend_id="agy",
        model="model",
        effort="high",
        cwd_norm="/tmp",
    )


def test_disabled_pool_does_not_start_maintenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """При enabled=False фоновый поток обслуживания не запускается."""
    handle = _FakeHandle(created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    pool = ResidentProcessPool(StdioPoolConfig(enabled=False, reap_interval_s=0.01))
    try:
        entry = pool.acquire(_key(), lambda: ["echo"], cwd=".")
        pool.release(entry.slot_id)
        pool.start_maintenance()
        assert pool._maint_thread is None
    finally:
        pool.shutdown()


def test_maintenance_starts_lazily_and_stops_idempotently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Поток стартует на первом acquire() и идемпотентно останавливается в shutdown()."""
    handle = _FakeHandle(created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    pool = ResidentProcessPool(
        StdioPoolConfig(enabled=True, reap_interval_s=0.01, shutdown_timeout_s=1.0)
    )
    try:
        assert pool._maint_thread is None
        entry = pool.acquire(_key(), lambda: ["echo"], cwd=".")
        pool.release(entry.slot_id)
        thread = pool._maint_thread
        assert thread is not None
        assert thread.daemon is True
        assert thread.is_alive()
        pool.shutdown()
        assert not thread.is_alive()
        pool.shutdown()
    finally:
        pool.shutdown()


def test_drain_and_shutdown_stops_maintenance(monkeypatch: pytest.MonkeyPatch) -> None:
    """drain_and_shutdown() обязан останавливать поток обслуживания и быть идемпотентным."""
    handle = _FakeHandle(created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    pool = ResidentProcessPool(
        StdioPoolConfig(enabled=True, reap_interval_s=0.01, shutdown_timeout_s=1.0)
    )
    entry = pool.acquire(_key(), lambda: ["echo"], cwd=".")
    pool.release(entry.slot_id)
    thread = pool._maint_thread
    assert thread is not None and thread.is_alive()
    asyncio.run(pool.drain_and_shutdown())
    assert not thread.is_alive()
    asyncio.run(pool.drain_and_shutdown())


def test_idle_ready_slot_closed_after_idle_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """READY-слот закрывается циклом обслуживания при превышении idle_timeout_s."""
    now = [100.0]
    monkeypatch.setattr(pool_mod, "time", _FakeTimeProxy(now))
    handle = _FakeHandle(created_at_mono=100.0)
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    monkeypatch.setattr(pool_mod, "get_pgid_rss_bytes", lambda _pgid: 1024)
    pool = ResidentProcessPool(
        StdioPoolConfig(
            enabled=True,
            idle_timeout_s=5.0,
            reap_interval_s=0.01,
            rss_check_interval_s=60.0,
            shutdown_timeout_s=1.0,
        )
    )
    try:
        entry = pool.acquire(_key(), lambda: ["echo"], cwd=".")
        pool.release(entry.slot_id)
        now[0] = 104.0
        real_time.sleep(0.05)
        assert len(pool._slots) == 1
        now[0] = 106.0
        _wait_until(lambda: len(pool._slots) == 0)
        assert len(handle.terminated_calls) == 1
    finally:
        pool.shutdown()


def test_rss_enforcement_throttled_and_closes_exceeding_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Замеры RSS выполняются не чаще rss_check_interval_s и закрывают слот при RSS > max_rss_bytes."""
    now = [100.0]
    monkeypatch.setattr(pool_mod, "time", _FakeTimeProxy(now))
    handle = _FakeHandle(pid=4242, pgid=4242, created_at_mono=100.0)
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    rss_value = [10 * 1024 * 1024]
    rss_calls: list[int] = []

    def _fake_rss(pgid: int) -> int | None:
        rss_calls.append(pgid)
        return rss_value[0]

    monkeypatch.setattr(pool_mod, "get_pgid_rss_bytes", _fake_rss)
    pool = ResidentProcessPool(
        StdioPoolConfig(
            enabled=True,
            max_rss_bytes=50 * 1024 * 1024,
            rss_check_interval_s=10.0,
            reap_interval_s=0.01,
            idle_timeout_s=300.0,
            shutdown_timeout_s=1.0,
        )
    )
    try:
        entry = pool.acquire(_key(), lambda: ["echo"], cwd=".")
        pool.release(entry.slot_id)
        _wait_until(lambda: len(rss_calls) >= 1)
        assert len(pool._slots) == 1

        rss_value[0] = 100 * 1024 * 1024
        now[0] = 105.0
        real_time.sleep(0.05)
        assert len(rss_calls) == 1
        assert len(pool._slots) == 1

        now[0] = 110.5
        _wait_until(lambda: len(pool._slots) == 0)
        assert len(rss_calls) >= 2
        assert len(handle.terminated_calls) == 1
    finally:
        pool.shutdown()


def test_maintenance_reaps_dead_and_quarantined_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Обслуживание переводит умерший READY-слот в карантин и убирает после смерти pgid."""
    handle = _FakeHandle(
        pid=5151,
        pgid=5151,
        created_at_mono=real_time.monotonic(),
        pgid_dead_on_terminate=False,
    )
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    pgid_alive = [True]
    monkeypatch.setattr(pool_mod, "is_pgid_alive", lambda _pgid: pgid_alive[0])
    monkeypatch.setattr(pool_mod, "get_pgid_rss_bytes", lambda _pgid: 1024)
    pool = ResidentProcessPool(
        StdioPoolConfig(
            enabled=True,
            reap_interval_s=0.01,
            rss_check_interval_s=60.0,
            shutdown_timeout_s=1.0,
        )
    )
    try:
        entry = pool.acquire(_key(), lambda: ["echo"], cwd=".")
        pool.release(entry.slot_id)
        handle._alive = False
        _wait_until(lambda: entry.dead is True)
        assert entry.slot_id in pool._slots
        pgid_alive[0] = False
        _wait_until(lambda: entry.slot_id not in pool._slots)
    finally:
        pool.shutdown()


def test_maintenance_loop_survives_step_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Исключение в одном проходе цикла обслуживания не убивает daemon-поток."""
    handle = _FakeHandle(pid=6161, pgid=6161, created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    attempts = [0]

    def _flaky_rss(_pgid: int) -> int | None:
        attempts[0] += 1
        if attempts[0] == 1:
            raise RuntimeError("transient ps error")
        return 100 * 1024 * 1024

    monkeypatch.setattr(pool_mod, "get_pgid_rss_bytes", _flaky_rss)
    pool = ResidentProcessPool(
        StdioPoolConfig(
            enabled=True,
            max_rss_bytes=50 * 1024 * 1024,
            rss_check_interval_s=0.01,
            reap_interval_s=0.01,
            shutdown_timeout_s=1.0,
        )
    )
    try:
        entry = pool.acquire(_key(), lambda: ["echo"], cwd=".")
        pool.release(entry.slot_id)
        _wait_until(lambda: len(pool._slots) == 0)
        assert attempts[0] >= 2
        assert len(handle.terminated_calls) == 1
    finally:
        pool.shutdown()
