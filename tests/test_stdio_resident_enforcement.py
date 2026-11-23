"""Тесты runtime-enforcement параметров ResidentProcessPool."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sqlite3
import sys
import threading
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
        assert pool.start_maintenance() is False
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


def test_start_maintenance_return_values_and_guards() -> None:
    """start_maintenance возвращает bool и проверяет _closed, _stop_event и живой поток."""
    pool = ResidentProcessPool(
        StdioPoolConfig(enabled=True, reap_interval_s=0.01, shutdown_timeout_s=1.0)
    )
    try:
        assert pool.start_maintenance() is True
        first_thread = pool._maint_thread
        assert first_thread is not None and first_thread.is_alive()
        assert pool.start_maintenance() is False
        assert pool._maint_thread is first_thread
        pool.shutdown()
        assert pool.start_maintenance() is False
        assert not first_thread.is_alive()
    finally:
        pool.shutdown()

    closed_pool = ResidentProcessPool(StdioPoolConfig(enabled=True, reap_interval_s=0.01))
    closed_pool._closed = True
    assert not closed_pool._stop_event.is_set()
    assert closed_pool.start_maintenance() is False
    assert closed_pool._maint_thread is None

    stopped_pool = ResidentProcessPool(StdioPoolConfig(enabled=True, reap_interval_s=0.01))
    stopped_pool._stop_event.set()
    assert stopped_pool._closed is False
    assert stopped_pool.start_maintenance() is False
    assert stopped_pool._maint_thread is None


_BRIDGE_PY = Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge" / "server.py"
_SRV_CACHE: list[object] = []


def _load_bridge(monkeypatch: pytest.MonkeyPatch) -> object:
    if _SRV_CACHE:
        return _SRV_CACHE[0]
    bridge_dir = str(_BRIDGE_PY.parent)
    if bridge_dir not in sys.path:
        sys.path.insert(0, bridge_dir)
    monkeypatch.setenv(
        "AGY_BRIDGE_KEY",
        os.environ.get("AGY_BRIDGE_KEY", "test-key-stdio-enforcement"),
    )
    spec = importlib.util.spec_from_file_location(
        "agy_bridge_server_for_wal_test", _BRIDGE_PY
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _SRV_CACHE.append(mod)
    return mod


class _FakeCursor:
    def fetchmany(self, _size: int) -> list[tuple[object, ...]]:
        return []

    def close(self) -> None:
        return None


class _FakeConn:
    def execute(self, _sql: str, _params: tuple[object, ...]) -> _FakeCursor:
        return _FakeCursor()


def test_handle_cold_wal_wait_and_resolve_counter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Холодное ожидание WAL, счётчик, sqlite-wal-resolved и non-cold OperationalError."""
    srv = _load_bridge(monkeypatch)
    logs: list[str] = []
    monkeypatch.setattr(srv, "_log", logs.append)

    tracker_cls = next(
        obj
        for obj in vars(srv).values()
        if isinstance(obj, type) and hasattr(obj, "_handle_cold_wal_wait")
    )
    db_path = tmp_path / "cascade.pb"
    wal_path = Path(str(db_path) + "-wal")

    tracker = tracker_cls.__new__(tracker_cls)
    tracker._db_path = db_path
    tracker.selects_ok = 0
    tracker.failed = False
    tracker._open_fail_logged = False
    tracker._interrupted = False
    tracker.stop_event = threading.Event()
    tracker.poll_watermark = 0
    tracker.base_idx = 0
    tracker.dead = False
    tracker._cid8 = lambda: "cid12345"
    tracker._sqlite_permitted = lambda: True
    tracker._advance_watermark = lambda: None
    tracker._sqlite_off = lambda _reason: None

    cold_exc = sqlite3.OperationalError("unable to open database file")
    assert tracker._on_sqlite_error(cold_exc) is None
    assert tracker.failed is False
    assert tracker._get_wal_wait_polls() == 1
    assert logs == ["sqlite-wal-wait cid=cid12345 err=OperationalError"]

    wal_path.write_text("", encoding="utf-8")
    assert tracker._handle_cold_wal_wait(cold_exc) is True
    assert tracker._get_wal_wait_polls() == 2
    assert len(logs) == 1

    assert tracker._select_rows(_FakeConn()) == (0, 0)
    assert tracker.selects_ok == 1
    assert tracker._get_wal_wait_polls() == 0
    assert logs[-1] == "sqlite-wal-resolved cid=cid12345 waited_polls=2"

    log_count = len(logs)
    tracker._resolve_wal_wait()
    assert len(logs) == log_count

    wal_path.unlink()
    assert tracker._handle_cold_wal_wait(cold_exc) is True
    assert tracker._get_wal_wait_polls() == 1
    tracker._resolve_wal_wait()
    assert tracker._get_wal_wait_polls() == 0

    wal_path.write_text("", encoding="utf-8")
    non_cold_exc = sqlite3.OperationalError("disk I/O error")
    assert tracker._handle_cold_wal_wait(non_cold_exc) is False
    assert tracker._on_sqlite_error(non_cold_exc) is None
    assert tracker.failed is True
    assert any("sqlite-open-fail" in entry and "cold=0" in entry for entry in logs)


def test_start_maintenance_guards_closed_stop_event_and_thread_state() -> None:
    """Гарды start_maintenance различают _closed/_stop_event и живой/мёртвый/None поток."""
    closed_only = ResidentProcessPool(
        StdioPoolConfig(enabled=True, reap_interval_s=0.01, shutdown_timeout_s=0.5)
    )
    try:
        closed_only._closed = True
        assert not closed_only._stop_event.is_set()
        assert closed_only.start_maintenance() is False
        assert closed_only._maint_thread is None
    finally:
        closed_only.shutdown()

    stop_only = ResidentProcessPool(
        StdioPoolConfig(enabled=True, reap_interval_s=0.01, shutdown_timeout_s=0.5)
    )
    try:
        stop_only._stop_event.set()
        assert stop_only._closed is False
        assert stop_only.start_maintenance() is False
        assert stop_only._maint_thread is None
    finally:
        stop_only.shutdown()

    dead_thread = threading.Thread(target=lambda: None, name="dead-maint-test")
    dead_thread.start()
    dead_thread.join(timeout=1.0)
    assert not dead_thread.is_alive()

    pool = ResidentProcessPool(
        StdioPoolConfig(enabled=True, reap_interval_s=0.01, shutdown_timeout_s=0.5)
    )
    first_thread: threading.Thread | None = None
    try:
        pool._maint_thread = dead_thread
        assert pool.start_maintenance() is True
        first_thread = pool._maint_thread
        assert first_thread is not None and first_thread is not dead_thread
        assert first_thread.is_alive()

        assert pool.start_maintenance() is False

        pool._maint_thread = None
        assert pool.start_maintenance() is True
        second_thread = pool._maint_thread
        assert second_thread is not None and second_thread is not first_thread
        assert second_thread.is_alive()
    finally:
        pool.shutdown()
        if first_thread is not None:
            first_thread.join(timeout=1.0)
            assert not first_thread.is_alive()


def test_drain_and_shutdown_closed_with_slot_and_already_closed_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """drain_and_shutdown разбирает слот при _closed=True и возвращает None на пустом закрытом пуле."""
    handle = _FakeHandle(pid=7171, pgid=7171, created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    monkeypatch.setattr(pool_mod, "get_pgid_rss_bytes", lambda _pgid: 1024)

    pool_with_slot = ResidentProcessPool(
        StdioPoolConfig(
            enabled=True,
            idle_timeout_s=300.0,
            reap_interval_s=0.01,
            rss_check_interval_s=60.0,
            shutdown_timeout_s=0.5,
        )
    )
    try:
        entry = pool_with_slot.acquire(_key("owner-closed-slot"), lambda: ["echo"], cwd=".")
        pool_with_slot.release(entry.slot_id)
        assert len(pool_with_slot._slots) == 1
        slot_thread = pool_with_slot._maint_thread
        assert slot_thread is not None and slot_thread.is_alive()

        pool_with_slot._closed = True
        assert asyncio.run(pool_with_slot.drain_and_shutdown(timeout_s=0.5)) is None
        assert len(pool_with_slot._slots) == 0
        assert len(handle.terminated_calls) == 1
        assert handle.is_alive() is False
        assert not slot_thread.is_alive()
    finally:
        pool_with_slot.shutdown()

    open_empty = ResidentProcessPool(
        StdioPoolConfig(enabled=True, reap_interval_s=0.01, shutdown_timeout_s=0.5)
    )
    try:
        assert open_empty.start_maintenance() is True
        open_thread = open_empty._maint_thread
        assert open_thread is not None and open_thread.is_alive()
        assert asyncio.run(open_empty.drain_and_shutdown(timeout_s=0.5)) is None
        assert open_empty._closed is True
        assert not open_thread.is_alive()
    finally:
        open_empty.shutdown()

    closed_empty = ResidentProcessPool(
        StdioPoolConfig(enabled=True, reap_interval_s=0.01, shutdown_timeout_s=0.5)
    )
    try:
        assert closed_empty.start_maintenance() is True
        closed_thread = closed_empty._maint_thread
        assert closed_thread is not None and closed_thread.is_alive()
        closed_empty._closed = True
        assert not closed_empty._slots
        assert asyncio.run(closed_empty.drain_and_shutdown(timeout_s=0.5)) is None
        assert closed_empty._stop_event.is_set()
        assert not closed_thread.is_alive()
    finally:
        closed_empty.shutdown()
