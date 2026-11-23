"""Тесты runtime-enforcement параметров ResidentProcessPool."""

from __future__ import annotations  # noqa: E402

import asyncio  # noqa: E402
import importlib.util  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import sqlite3  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time as real_time  # noqa: E402
from collections.abc import Callable  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

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

    assert tracker._wal_wait_limit(None) == 32
    assert tracker._wal_wait_limit(7) == 7
    tracker._wal_wait_max_polls = 5
    assert tracker._wal_wait_limit(None) == 5
    del tracker._wal_wait_max_polls

    cold_exc = sqlite3.OperationalError("unable to open database file")
    assert tracker._on_sqlite_error(cold_exc) is None
    assert tracker.failed is False
    assert tracker._get_wal_wait_polls() == 1
    assert logs[-1] == "sqlite-wal-wait cid=cid12345 err=OperationalError wal=0"

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

    # при существующем -wal даже 'unable to open database file' считается реальной ошибкой
    wal_path.write_text("", encoding="utf-8")
    tracker.selects_ok = 0
    tracker.failed = False
    tracker._open_fail_logged = False
    assert tracker._handle_cold_wal_wait(cold_exc) is False
    assert tracker._on_sqlite_error(cold_exc) is None
    assert tracker.failed is True
    assert any("sqlite-open-fail" in entry and "cold=0" in entry for entry in logs)

    wal_path.unlink()
    tracker.selects_ok = 0
    tracker.failed = False
    tracker._open_fail_logged = False
    non_cold_exc = sqlite3.OperationalError("disk I/O error")
    assert tracker._handle_cold_wal_wait(non_cold_exc) is False
    assert tracker._on_sqlite_error(non_cold_exc) is None
    assert tracker.failed is True

    # 'database is locked' убран из whitelist даже при selects_ok == 0 и отсутствии -wal
    tracker.selects_ok = 0
    tracker.failed = False
    tracker._open_fail_logged = False
    locked_exc = sqlite3.OperationalError("database is locked")
    assert tracker._handle_cold_wal_wait(locked_exc) is False
    assert tracker._on_sqlite_error(locked_exc) is None
    assert tracker.failed is True

    # после первого успешного SELECT окно холодного ожидания закрыто
    tracker.selects_ok = 1
    tracker.failed = False
    assert tracker._handle_cold_wal_wait(cold_exc) is False
    assert tracker._get_wal_wait_polls() == 0

    # бюджет эскалации остаётся для 'unable to open database file' при отсутствии -wal
    tracker.selects_ok = 0
    tracker.failed = False
    while tracker._handle_cold_wal_wait(cold_exc):
        pass
    assert tracker._wal_wait_budget_exceeded is True
    tracker._open_fail_logged = False
    assert tracker._on_sqlite_error(cold_exc) is None
    assert tracker.failed is True
    assert any(
        "sqlite-open-fail" in entry and "wal_wait_budget_exceeded=1" in entry
        for entry in logs
    )


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


def test_drain_and_shutdown_terminates_ready_slot_with_cancel_grace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """drain_and_shutdown терминирует READY-слот в drain-фазе с cancel_grace_s."""
    handle = _FakeHandle(pid=7272, pgid=7272, created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    monkeypatch.setattr(pool_mod, "get_pgid_rss_bytes", lambda _pgid: 1024)

    pool = ResidentProcessPool(
        StdioPoolConfig(
            enabled=True,
            reap_interval_s=0.05,
            cancel_grace_s=0.3,
            shutdown_timeout_s=0.9,
            lease_wait_s=0.1,
        )
    )
    try:
        entry = pool.acquire(_key("owner-ready-drain-grace"), lambda: ["echo"], cwd=".")
        pool.release(entry.slot_id)
        pool._closed = True
        asyncio.run(pool.drain_and_shutdown(timeout_s=0.9))
        assert handle.terminated_calls == [0.3]
    finally:
        pool.shutdown()


def test_drain_and_shutdown_transitions_leased_slot_to_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """drain_and_shutdown переводит арендованный слот в Drain до ожидания lease."""
    handle = _FakeHandle(pid=7373, pgid=7373, created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    monkeypatch.setattr(pool_mod, "get_pgid_rss_bytes", lambda _pgid: 1024)

    pool = ResidentProcessPool(
        StdioPoolConfig(
            enabled=True,
            reap_interval_s=0.05,
            cancel_grace_s=0.3,
            shutdown_timeout_s=0.9,
            lease_wait_s=0.1,
        )
    )
    try:
        entry = pool.acquire(_key("owner-leased-drain"), lambda: ["echo"], cwd=".")
        assert entry.lease_id is not None

        orig_transition = pool._transition
        seen: list[tuple[str, pool_mod.SlotEvent]] = []

        def _record_transition(
            slot_entry: pool_mod._SlotEntry,
            event: pool_mod.SlotEvent,
        ) -> object:
            seen.append((slot_entry.slot_id, event))
            return orig_transition(slot_entry, event)

        monkeypatch.setattr(pool, "_transition", _record_transition)
        pool._closed = True
        asyncio.run(pool.drain_and_shutdown(timeout_s=0.3))
        assert (entry.slot_id, pool_mod.SlotEvent.Drain) in seen
    finally:
        pool.shutdown()


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


def test_leased_slot_rss_exceeded_marks_pending_and_tears_down_on_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S1: арендованный слот с RSS > потолка помечается и разбирается в release()."""
    now = [100.0]
    monkeypatch.setattr(pool_mod, "time", _FakeTimeProxy(now))
    handle = _FakeHandle(pid=8181, pgid=8181, created_at_mono=100.0)
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    rss_calls: list[int] = []

    def _high_rss(pgid: int) -> int:
        rss_calls.append(pgid)
        return 100 * 1024 * 1024

    monkeypatch.setattr(pool_mod, "get_pgid_rss_bytes", _high_rss)
    pool = ResidentProcessPool(
        StdioPoolConfig(
            enabled=True,
            max_rss_bytes=50 * 1024 * 1024,
            rss_check_interval_s=0.01,
            reap_interval_s=0.01,
            idle_timeout_s=300.0,
            shutdown_timeout_s=0.5,
        )
    )
    try:
        entry = pool.acquire(_key("owner-leased-rss"), lambda: ["echo"], cwd=".")
        _wait_until(lambda: entry.rss_evict_pending is True, timeout_s=0.25)
        assert len(rss_calls) >= 1
        assert entry.slot_id in pool._slots
        assert entry.lease_id is not None
        assert handle.terminated_calls == []
        assert handle.is_alive() is True

        pool.release(entry.slot_id)
        assert entry.slot_id not in pool._slots
        assert len(handle.terminated_calls) == 1
        assert handle.is_alive() is False
    finally:
        pool.shutdown()


def test_terminate_victims_exception_keeps_slot_quarantined(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """S2: ошибка _terminate оставляет слот карантинным в _slots для _reap_quarantined_slots."""
    handle = _FakeHandle(pid=8282, pgid=8282, created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    monkeypatch.setattr(pool_mod, "get_pgid_rss_bytes", lambda _pgid: 100 * 1024 * 1024)
    pgid_alive = [True]
    monkeypatch.setattr(pool_mod, "is_pgid_alive", lambda _pgid: pgid_alive[0])

    def _failing_terminate(_entry: pool_mod._SlotEntry, _grace_s: float) -> None:
        raise RuntimeError("terminate failed")

    pool = ResidentProcessPool(
        StdioPoolConfig(
            enabled=True,
            max_rss_bytes=50 * 1024 * 1024,
            rss_check_interval_s=0.01,
            reap_interval_s=0.01,
            idle_timeout_s=300.0,
            shutdown_timeout_s=0.5,
        )
    )
    monkeypatch.setattr(pool, "_terminate", _failing_terminate)
    try:
        with caplog.at_level(logging.ERROR, logger=pool_mod.__name__):
            entry = pool.acquire(_key("owner-quarantine-err"), lambda: ["echo"], cwd=".")
            pool.release(entry.slot_id)
            _wait_until(lambda: entry.dead is True, timeout_s=0.25)
        assert entry.slot_id in pool._slots
        assert entry.lease_id is None
        assert any(record.levelno == logging.ERROR for record in caplog.records)

        pgid_alive[0] = False
        _wait_until(lambda: entry.slot_id not in pool._slots, timeout_s=0.25)
    finally:
        pgid_alive[0] = False
        pool.shutdown()


def test_drain_and_shutdown_uses_to_thread_for_terminations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S3: все синхронные терминации и join в drain_and_shutdown идут через asyncio.to_thread."""
    handles = [
        _FakeHandle(pid=8381, pgid=8381, created_at_mono=real_time.monotonic()),
        _FakeHandle(pid=8382, pgid=8382, created_at_mono=real_time.monotonic()),
    ]
    spawn_iter = iter(handles)
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: next(spawn_iter)),
    )
    monkeypatch.setattr(pool_mod, "get_pgid_rss_bytes", lambda _pgid: 1024)

    to_thread_calls: list[object] = []

    async def _spy_to_thread(fn: Callable[..., object], *args: object, **kwargs: object) -> object:
        to_thread_calls.append(fn)
        return fn(*args, **kwargs)

    monkeypatch.setattr(pool_mod.asyncio, "to_thread", _spy_to_thread)
    pool = ResidentProcessPool(
        StdioPoolConfig(
            enabled=True,
            max_slots=4,
            reap_interval_s=0.05,
            cancel_grace_s=0.1,
            shutdown_timeout_s=0.1,
        )
    )
    try:
        ready_entry = pool.acquire(_key("owner-drain-ready"), lambda: ["echo"], cwd=".")
        pool.release(ready_entry.slot_id)
        _leased_entry = pool.acquire(_key("owner-drain-leased"), lambda: ["echo"], cwd=".")

        asyncio.run(pool.drain_and_shutdown(timeout_s=0.05))
        terminate_calls = [fn for fn in to_thread_calls if fn == pool._terminate_victims]
        join_calls = [fn for fn in to_thread_calls if fn == pool._join_maintenance]
        assert len(terminate_calls) == 2
        assert len(join_calls) == 1
        assert len(handles[0].terminated_calls) == 1
        assert len(handles[1].terminated_calls) == 1
        assert len(pool._slots) == 0
    finally:
        pool.shutdown()


def test_join_maintenance_logs_warning_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """S4: при таймауте join живой поток обслуживания логируется через warning."""
    entered = threading.Event()
    release_step = threading.Event()

    def _blocking_step() -> None:
        entered.set()
        release_step.wait(timeout=0.25)

    pool = ResidentProcessPool(
        StdioPoolConfig(enabled=True, reap_interval_s=0.005, shutdown_timeout_s=0.25)
    )
    monkeypatch.setattr(pool, "_maintenance_step", _blocking_step)
    try:
        assert pool.start_maintenance() is True
        assert entered.wait(timeout=0.25)
        thread = pool._maint_thread
        assert thread is not None
        with caplog.at_level(logging.WARNING, logger=pool_mod.__name__):
            pool.shutdown(timeout_s=0.0)
        assert any(
            record.levelno == logging.WARNING
            and thread.name in record.getMessage()
            and "timeout" in record.getMessage().lower()
            for record in caplog.records
        )
    finally:
        release_step.set()
        if pool._maint_thread is not None:
            pool._maint_thread.join(timeout=0.25)


@pytest.mark.parametrize("mode", ["cancel", "rss_evict"])
def test_release_teardown_runs_outside_cv_lock(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """R1: release() выполняет _finish_teardown вне self._cv для cancel и rss_evict_pending."""
    handle = _FakeHandle(pid=9101, pgid=9101, created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    pool = ResidentProcessPool(StdioPoolConfig(enabled=False, shutdown_timeout_s=0.5))
    entered = threading.Event()
    allow_finish = threading.Event()
    acquired_cv = threading.Event()

    def _blocking_terminate(slot_entry: pool_mod._SlotEntry, _grace_s: float) -> None:
        entered.set()
        assert allow_finish.wait(timeout=0.5)
        slot_entry.handle._alive = False
        slot_entry.handle._pgid_dead = True

    monkeypatch.setattr(pool, "_terminate", _blocking_terminate)
    try:
        entry = pool.acquire(_key(f"owner-r1-{mode}"), lambda: ["echo"], cwd=".")
        if mode == "rss_evict":
            entry.rss_evict_pending = True

        rel_thread = threading.Thread(
            target=lambda: pool.release(entry.slot_id, cancel=(mode == "cancel")),
        )
        rel_thread.start()
        assert entered.wait(timeout=0.5)

        def _probe_cv() -> None:
            with pool._cv:
                acquired_cv.set()

        probe = threading.Thread(target=_probe_cv)
        probe.start()
        assert acquired_cv.wait(timeout=0.25)
        probe.join(timeout=0.25)
        allow_finish.set()
        rel_thread.join(timeout=0.5)
        assert entry.slot_id not in pool._slots
    finally:
        allow_finish.set()
        pool.shutdown()


def test_shutdown_and_drain_propagate_stdio_terminated_and_respect_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R2: shutdown/drain пробрасывают StdioProcessTerminated после всех терминаций и не возвращают слот при _closed."""
    handles = [
        _FakeHandle(pid=9201, pgid=9201, created_at_mono=real_time.monotonic()),
        _FakeHandle(pid=9202, pgid=9202, created_at_mono=real_time.monotonic()),
    ]
    spawn_iter = iter(handles)
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: next(spawn_iter)),
    )
    terminated_pids: list[int] = []

    def _failing_on_first(slot_entry: pool_mod._SlotEntry, grace_s: float) -> None:
        terminated_pids.append(slot_entry.handle.pid)
        if slot_entry.handle.pid == 9201:
            raise pool_mod.StdioProcessTerminated("term failed")
        slot_entry.handle.terminate_gracefully(grace_s=grace_s)

    pool = ResidentProcessPool(StdioPoolConfig(enabled=False, max_slots=4, shutdown_timeout_s=0.5))
    monkeypatch.setattr(pool, "_terminate", _failing_on_first)
    e1 = pool.acquire(_key("owner-r2-1"), lambda: ["echo"], cwd=".")
    e2 = pool.acquire(_key("owner-r2-2"), lambda: ["echo"], cwd=".")
    pool.release(e1.slot_id)
    pool.release(e2.slot_id)
    with pytest.raises(pool_mod.StdioProcessTerminated):
        pool.shutdown()
    assert sorted(terminated_pids) == [9201, 9202]
    assert len(pool._slots) == 0

    h3 = _FakeHandle(pid=9203, pgid=9203, created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: h3),
    )
    pool2 = ResidentProcessPool(StdioPoolConfig(enabled=False, max_slots=2, shutdown_timeout_s=0.5))

    def _drain_fail(_slot_entry: pool_mod._SlotEntry, _grace_s: float) -> None:
        raise pool_mod.StdioProcessTerminated("drain term failed")

    monkeypatch.setattr(pool2, "_terminate", _drain_fail)
    e3 = pool2.acquire(_key("owner-r2-drain"), lambda: ["echo"], cwd=".")
    pool2.release(e3.slot_id)
    with pytest.raises(pool_mod.StdioProcessTerminated):
        asyncio.run(pool2.drain_and_shutdown(timeout_s=0.05))
    assert len(pool2._slots) == 0


def test_finish_teardown_propagates_stdio_terminated_on_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R2: _finish_teardown пробрасывает StdioProcessTerminated и помечает слот dead в карантин."""
    handle = _FakeHandle(pid=9301, pgid=9301, created_at_mono=real_time.monotonic())
    monkeypatch.setattr(
        pool_mod.ResidentProcessHandle,
        "spawn",
        staticmethod(lambda *args, **kwargs: handle),
    )
    pool = ResidentProcessPool(StdioPoolConfig(enabled=False, shutdown_timeout_s=0.5))
    allow_cleanup = [False]

    def _term(slot_entry: pool_mod._SlotEntry, _grace_s: float) -> None:
        if not allow_cleanup[0]:
            raise pool_mod.StdioProcessTerminated("cancel term failed")
        slot_entry.handle._alive = False

    monkeypatch.setattr(pool, "_terminate", _term)
    try:
        entry = pool.acquire(_key("owner-r2-rel"), lambda: ["echo"], cwd=".")
        with pytest.raises(pool_mod.StdioProcessTerminated):
            pool.release(entry.slot_id, cancel=True)
        assert entry.dead is True
        assert entry.slot_id in pool._slots
    finally:
        allow_cleanup[0] = True
        pool.shutdown()
