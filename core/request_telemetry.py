"""Универсальная телеметрия запросов моста: DuckDB (fallback sqlite3), неблокирующая очередь.

Хранит только скаляры: промпты, тела, карты заголовков и env не сохраняются, секреты
редактируются в фоновом writer до записи в БД. Агент-агностично: знает про backend_id, а не про агентов.
Стор ленивый: импорт модуля и конструктор не открывают БД и не запускают поток, это делает первое обращение
при включённом флаге BRIDGE_TELEMETRY_ENABLED (GigaRC > env > false), который проверяется на каждом запросе.
"""

from __future__ import annotations

import atexit
import itertools
import os
import queue
import sqlite3
import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any

from core.runtime_env import env_bool, flag_enabled
from core.telemetry_flow import build_architecture_flow
from core.telemetry_query import TelemetryReader
from core.telemetry_sql import (
    COLUMNS,
    NAMES,
    SCHEMA,
    Quantile,
    classify_caller,
    make_row,
    sanitize_scalar,
    scan_bound,
)
from core.telemetry_util import as_float, as_int, close_quietly, first_truthy

__all__ = ["COLUMNS", "RequestTelemetryStore", "build_architecture_flow", "classify_caller", "sanitize_scalar"]

try:  # DuckDB опционален: без него тот же SQL исполняется на stdlib sqlite3.
    import duckdb  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
except Exception:  # noqa: BLE001 - любой сбой импорта = fallback
    duckdb = None

_FLAG = "BRIDGE_TELEMETRY_ENABLED"
_GATES = {  # enabled из конструктора -> проверка «включено ли сейчас»; чужие значения = динамический флаг
    None: lambda: flag_enabled(_FLAG),
    True: lambda: env_bool(os.environ, (_FLAG,), True),
    False: lambda: False,
}
_INSERT = f"INSERT INTO bridge_requests VALUES ({', '.join('?' * len(NAMES))})"
_INDEX_SQL: dict[str, tuple[str, ...]] = {
    "sqlite3": ("CREATE INDEX IF NOT EXISTS idx_bridge_requests_ts ON bridge_requests (ts_epoch)",),
}


def _sqlite(base: str) -> tuple[Any, str, str]:
    """sqlite3-фолбэк на отдельном файле .sqlite3 (файл .duckdb в sqlite никогда не передаётся)."""
    path = os.path.splitext(base)[0] + ".sqlite3"
    con: Any = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    con.create_aggregate("quantile_cont", 2, Quantile)
    return con, "sqlite3", path


class RequestTelemetryStore(TelemetryReader):
    """Неблокирующая очередь + один фоновый writer; все операции с БД — под одним замком."""

    def __init__(self, db_path: str | None = None, *, force_sqlite: bool = False, autostart: bool = True, **cfg: Any) -> None:
        super().__init__(db_path, cfg)
        self._gate = _GATES.get(cfg.get("enabled"), _GATES[None])
        self._open_lock, self._stop = threading.Lock(), threading.Event()
        limit = as_int(self._c["max_field_len"])
        self._limits = (limit, scan_bound(limit, as_int(self._c["redact_scan_factor"]), as_int(self._c["redact_scan_min"])))
        self._last_prune = 0.0
        self._thread: threading.Thread | None = None
        self._opened = False
        self._force_sqlite, self._autostart = force_sqlite, autostart

    @property
    def enabled(self) -> bool:
        """Включена ли телеметрия прямо сейчас (kill-switch без рестарта)."""
        return bool(self._gate())

    is_enabled = enabled.fget

    def _bump(self, name: str, amount: int = 1) -> None:
        with self._stat_lock:
            self._stats[name] += amount

    def ensure_open(self) -> bool:
        """Включён ли стор и открыт ли он; первое обращение при включённом флаге открывает БД и поднимает writer."""
        enabled = self.enabled
        if all((enabled, not self._opened)):
            self._open_once()
        return all((enabled, self._ready))

    def _open_once(self) -> None:
        with self._open_lock:
            if not self._opened:
                self._open(self._force_sqlite)
                self._start_writer()
                self._opened = True

    def _start_writer(self) -> None:
        if all((self._ready, self._autostart)):
            self._thread = threading.Thread(target=self._writer_loop, name="bridge-telemetry-writer", daemon=True)
            self._thread.start()
            atexit.register(self.close)

    def _connect(self, base: str, force_sqlite: bool) -> tuple[Any, str, str]:
        """Соединение DuckDB либо sqlite3-фолбэк (отдельный файл) с агрегатом quantile_cont."""
        connect: Any = getattr(duckdb, "connect", None)
        try:
            con: Any = None if force_sqlite else connect(base)
        except Exception:  # noqa: BLE001 - занятый/повреждённый файл/lock -> sqlite3
            con = None
        return (con, "duckdb", base) if con is not None else _sqlite(base)

    def _open(self, force_sqlite: bool) -> None:
        """Открыть стор (DuckDB либо sqlite3); любой сбой не роняет мост, стор остаётся disabled."""
        base = os.path.expanduser(self.db_path)
        folder = first_truthy(os.path.dirname(base), ".")
        created = not os.path.isdir(folder)
        try:
            os.makedirs(folder, mode=0o700, exist_ok=True)
            if created:
                os.chmod(folder, 0o700)
            con, self.engine, self.db_path = self._connect(base, force_sqlite)
            con.execute(f"CREATE TABLE IF NOT EXISTS bridge_requests ({SCHEMA})")
            for statement in _INDEX_SQL.get(self.engine, ()):
                con.execute(statement)
            os.chmod(self.db_path, 0o600)
            self._con, self._ready = con, True
        except Exception:  # noqa: BLE001 - телеметрия не должна ронять мост
            self._con, self._ready, self.engine = None, False, "disabled"
        self._safe_prune()

    def record_request(self, event: Mapping[str, Any]) -> bool:
        """Горячий путь O(1): без regex, чтения окружения по полям и I/O; False — выключено, очередь полна, мусор."""
        return self._enqueue(event) if self.ensure_open() else False

    def _enqueue(self, event: Mapping[str, Any]) -> bool:
        try:
            self._queue.put_nowait(dict(event))
        except (queue.Full, TypeError, ValueError):
            self._bump("dropped_events")
            return False
        return True

    def _rows(self, events: Sequence[Mapping[str, Any]]) -> list[tuple]:
        """Сырые события -> строки (редакция секретов здесь, в writer); негодное событие учитывается как отброшенное."""
        rows: list[tuple] = []
        for event in events:
            try:
                rows.append(make_row(event, *self._limits))
            except (TypeError, ValueError):
                self._bump("dropped_events")
        return rows

    def _drain(self) -> list[tuple]:
        """Снять до batch_size событий из очереди без ожидания и превратить их в строки."""
        events: list[Mapping[str, Any]] = []
        for _ in range(as_int(self._c["batch_size"])):
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return self._rows(events)

    def _insert(self, batch: list[tuple]) -> None:
        con = self._con
        con.execute("BEGIN")
        try:
            con.executemany(_INSERT, batch)
            con.execute("COMMIT")
        except BaseException:
            self._rollback(con)
            raise

    def _rollback(self, con: Any) -> None:
        try:
            con.execute("ROLLBACK")
        except Exception:  # noqa: BLE001 - откат не должен маскировать исходную ошибку записи
            self._bump("rollback_errors")

    def _store_batch(self, batch: list[tuple]) -> int:
        """Одна транзакция INSERT; при сбое пачка учитывается как потерянная, writer не падает."""
        try:
            with self._db_lock:
                self._insert(batch)
        except Exception:  # noqa: BLE001
            self._bump("dropped_events", len(batch))
            return 0
        return len(batch)

    def flush(self, max_batches: int | None = None) -> int:
        """Записать очередь пачками batch_size; max_batches ограничивает число пачек (None — до пустой очереди)."""
        batches = itertools.islice(iter(self._drain, []), max_batches)
        return sum(self._store_batch(batch) for batch in batches)

    def _guarded_flush(self, max_batches: int | None = None) -> None:
        try:
            self.flush(max_batches)
        except Exception:  # noqa: BLE001 - транзиентный сбой БД не должен убивать writer
            self._bump("dropped_events")

    def prune(self) -> None:
        """Удалить строки старше retention_days и сверх max_rows (закрытый стор — no-op)."""
        with self._db_lock:
            if self._ready:
                cutoff = time.time() - as_float(self._c["retention_days"]) * 86400.0
                self._con.execute("DELETE FROM bridge_requests WHERE ts_epoch < ?", [cutoff])
                self._con.execute(
                    "DELETE FROM bridge_requests WHERE ts_epoch <= "
                    "(SELECT ts_epoch FROM bridge_requests ORDER BY ts_epoch DESC LIMIT 1 OFFSET ?)",
                    [as_int(self._c["max_rows"])],
                )
                self._last_prune = time.monotonic()

    def _safe_prune(self) -> None:
        """prune со счётчиком ошибок; повтор после сбоя планируется через prune_retry_s, а не через полный интервал."""
        try:
            self.prune()
        except Exception:  # noqa: BLE001
            self._bump("prune_errors")
            self._last_prune = time.monotonic() - as_float(self._c["prune_interval_s"]) + as_float(self._c["prune_retry_s"])

    def _prune_due(self) -> bool:
        """Пора ли чистить стор: с последнего prune прошёл prune_interval_s."""
        return time.monotonic() - self._last_prune >= as_float(self._c["prune_interval_s"])

    def _tick(self) -> None:
        self._guarded_flush(max(1, as_int(self._c["flush_max_batches"])))
        if self._prune_due():
            self._safe_prune()

    def _writer_loop(self) -> None:
        """Фоновый writer: ограниченные пачки по flush_interval_ms, периодический prune, финальный flush."""
        while not self._stop.wait(max(0.01, as_float(self._c["flush_interval_ms"]) / 1000.0)):
            self._tick()
        self._guarded_flush()

    def _join_writer(self) -> None:
        """Дождаться фонового writer; вызов из самого writer не блокирует (join с таймаутом)."""
        thread = self._thread
        join: Any = getattr(thread, "join", None)
        if all((callable(join), thread is not threading.current_thread())):
            join(timeout=5.0)

    def close(self) -> None:
        """Идемпотентно: остановить writer, дописать очередь, закрыть соединение."""
        self._stop.set()
        self._join_writer()
        self._guarded_flush()
        with self._db_lock:
            self._ready = False
            close_quietly(self._con)
            self._con = None
