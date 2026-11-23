"""W0 red-repro: контракт `agy_runtime.sqlite_ro_pool` (AD-002).

Per-db RO-пул: thread-local соединения `mode=ro`, ограниченный retry
с jitter на `database is locked`, метрики копией. БД — только tmp_path,
0 реальных ожиданий (sleep_fn инъектируется), close_all в finally.
"""

from __future__ import annotations

import gc
import inspect
import random
import sqlite3
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

_AGY_BRIDGE = Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge"
if str(_AGY_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_AGY_BRIDGE))

import agy_runtime.sqlite_ro_pool as pool_mod  # noqa: E402
from agy_runtime.sqlite_ro_pool import (  # noqa: E402
    FLAG_SQLITE_RO_POOL,
    SqliteRoPool,
    SqliteRoPoolConfig,
    load_sqlite_ro_pool_config,
)


class FakeRng(random.Random):
    """rng допустим и как Random, и как callable[[], float]."""

    def __call__(self) -> float:
        return 0.5


def make_pool(
    config: SqliteRoPoolConfig,
    sleep_fn: Callable[[float], None] | None = None,
) -> SqliteRoPool:
    params = inspect.signature(SqliteRoPool).parameters
    kwargs: dict[str, Any] = {}
    if sleep_fn is not None:
        for name in ("sleep_fn", "sleep", "sleep_func"):
            if name in params:
                kwargs[name] = sleep_fn
                break
    for name in ("rng", "random_fn", "jitter_fn", "rand"):
        if name in params:
            kwargs[name] = FakeRng(0)
            break
    try:
        return SqliteRoPool(config, **kwargs)
    except TypeError:
        return SqliteRoPool(config=config, **kwargs)


def make_db(path: Path, rows: int = 5) -> Path:
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, v TEXT)")
        conn.executemany(
            "INSERT INTO items (v) VALUES (?)",
            [(f"v{i}",) for i in range(rows)],
        )
        conn.commit()
    finally:
        conn.close()
    return path


def test_default_flag_off_and_env_config_parsing() -> None:
    assert FLAG_SQLITE_RO_POOL == "AGY_SQLITE_RO_POOL_ENABLED"
    config = load_sqlite_ro_pool_config({})
    assert config.enabled is False
    assert config.busy_timeout_ms == 500
    assert config.open_timeout_s == 0.5
    assert config.max_retries == 3
    assert config.base_backoff_s == 0.01
    assert config.max_backoff_s == 0.1
    assert config.jitter_ratio == 0.2
    assert SqliteRoPoolConfig() == config
    custom = load_sqlite_ro_pool_config(
        {
            FLAG_SQLITE_RO_POOL: "true",
            "AGY_SQLITE_BUSY_TIMEOUT_MS": "750",
            "AGY_SQLITE_MAX_RETRIES": "5",
        }
    )
    assert custom.enabled is True
    assert custom.busy_timeout_ms == 750
    assert custom.max_retries == 5


def test_20_concurrent_readers_under_wal_writer_zero_operational_error(
    tmp_path: Path,
) -> None:
    db = make_db(tmp_path / "hot.db")
    pool = make_pool(SqliteRoPoolConfig(enabled=True))
    errors: list[BaseException] = []
    results: list[int] = []
    lock = threading.Lock()
    stop = threading.Event()

    def writer() -> None:
        conn = sqlite3.connect(db)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            n = 0
            while not stop.is_set() and n < 500:
                conn.execute("INSERT INTO items (v) VALUES ('w')")
                conn.commit()
                n += 1
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)
        finally:
            conn.close()

    def reader() -> None:
        try:
            for _ in range(10):
                rows = pool.query_rows(db, "SELECT count(*) FROM items")
                with lock:
                    results.append(int(rows[0][0]))
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=writer)]
    threads += [threading.Thread(target=reader) for _ in range(20)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads[1:]:
            thread.join(timeout=30.0)
    finally:
        stop.set()
        threads[0].join(timeout=30.0)
        pool.close_all()
    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert len(results) == 200
    assert pool.snapshot_metrics()["failures"] == 0


def test_per_db_lock_isolation_and_thread_local_reuse(tmp_path: Path) -> None:
    db1 = make_db(tmp_path / "one.db", rows=3)
    db2 = make_db(tmp_path / "two.db", rows=7)
    pool = make_pool(SqliteRoPoolConfig(enabled=True))
    try:
        assert pool.query_rows(db1, "SELECT count(*) FROM items") == [(3,)]
        assert pool.query_rows(db1, "SELECT count(*) FROM items") == [(3,)]
        assert pool.query_rows(db2, "SELECT count(*) FROM items") == [(7,)]
        assert pool.query_rows(db2, "SELECT v FROM items WHERE id = ?", (1,)) == [
            ("v0",)
        ]
        metrics = pool.snapshot_metrics()
        assert set(metrics) >= {
            "opens",
            "reuses",
            "retries",
            "failures",
            "tracked_dbs",
            "active_conns",
        }
        assert metrics["tracked_dbs"] == 2
        assert metrics["reuses"] > 0
        assert metrics["opens"] >= 2
        assert metrics["failures"] == 0
        metrics["opens"] = -999
        assert pool.snapshot_metrics()["opens"] != -999
    finally:
        pool.close_all()


def _patch_connect(monkeypatch: pytest.MonkeyPatch, fake: Callable[..., Any]) -> None:
    monkeypatch.setattr(sqlite3, "connect", fake)
    if hasattr(pool_mod, "connect"):
        monkeypatch.setattr(pool_mod, "connect", fake)


def test_bounded_retries_with_injected_clock_and_jitter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = make_db(tmp_path / "retry.db")
    real_connect = sqlite3.connect
    sleeps: list[float] = []
    calls = {"n": 0}

    def flaky(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise sqlite3.OperationalError("database is locked")
        return real_connect(*args, **kwargs)

    _patch_connect(monkeypatch, flaky)
    config = SqliteRoPoolConfig(enabled=True, max_retries=3)
    pool = make_pool(config, sleep_fn=sleeps.append)
    try:
        assert pool.query_rows(db, "SELECT count(*) FROM items") == [(5,)]
        metrics = pool.snapshot_metrics()
        assert metrics["retries"] == 2
        assert metrics["failures"] == 0
        assert len(sleeps) == 2
        assert all(0.0 <= delay <= 0.13 for delay in sleeps)
    finally:
        pool.close_all()

    sleeps.clear()

    def always_locked(*args: Any, **kwargs: Any) -> Any:
        raise sqlite3.OperationalError("database is locked")

    _patch_connect(monkeypatch, always_locked)
    pool2 = make_pool(config, sleep_fn=sleeps.append)
    try:
        with pytest.raises(sqlite3.OperationalError):
            pool2.query_rows(db, "SELECT count(*) FROM items")
        assert pool2.snapshot_metrics()["failures"] >= 1
        assert len(sleeps) >= 1
    finally:
        pool2.close_all()


def test_missing_db_fails_cleanly_without_creating_file(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.db"
    pool = make_pool(SqliteRoPoolConfig(enabled=True), sleep_fn=lambda delay: None)
    try:
        with pytest.raises(sqlite3.OperationalError):
            pool.query_rows(missing, "SELECT 1")
        assert pool.snapshot_metrics()["failures"] >= 1
    finally:
        pool.close_all()
    assert not missing.exists()


def test_short_lived_threads_cleanup_and_run_ro(tmp_path: Path) -> None:
    db = make_db(tmp_path / "ephemeral.db", rows=4)
    pool = make_pool(SqliteRoPoolConfig(enabled=True))
    bound: list[bool] = []
    try:

        def worker() -> None:
            cnt = pool.run_ro(
                db,
                lambda c: int(c.execute("SELECT count(*) FROM items").fetchone()[0]),
                on_conn=lambda c: bound.append(c is not None),
            )
            assert cnt == 4

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10.0)
        gc.collect()
        assert pool.snapshot_metrics()["active_conns"] == 0
        assert bound.count(True) == 10 and bound.count(False) == 10
        assert pool.query_rows(db, "SELECT count(*) FROM items") == [(4,)]
        assert pool.snapshot_metrics()["active_conns"] == 1
        pool.release_thread()
        assert pool.snapshot_metrics()["active_conns"] == 0
    finally:
        pool.close_all()
