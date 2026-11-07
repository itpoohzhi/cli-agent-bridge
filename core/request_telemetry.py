"""Универсальная телеметрия запросов моста: DuckDB (fallback sqlite3), неблокирующая очередь.

Хранит только скаляры: промпты, тела, карты заголовков и env не сохраняются, секреты
редактируются до постановки в очередь. Агент-агностично: знает про backend_id, а не про агентов.
"""

from __future__ import annotations

import atexit
import os
import queue
import sqlite3
import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any

from core.telemetry_flow import build_architecture_flow
from core.telemetry_sql import (
    BACKEND_COLS,
    CLIENT_COLS,
    COLUMNS,
    HOUR_COLS,
    MODEL_COLS,
    NAMES,
    SCHEMA,
    SUMMARY_COLS,
    Quantile,
    classify_caller,
    clean_row,
    make_row,
    opt,
    sanitize_scalar,
    select_aggregates,
)
from core.telemetry_util import as_float, as_int, close_quietly, first

__all__ = ["COLUMNS", "RequestTelemetryStore", "build_architecture_flow", "classify_caller", "sanitize_scalar"]

try:  # DuckDB опционален: без него тот же SQL исполняется на stdlib sqlite3.
    import duckdb  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
except Exception:  # noqa: BLE001 - любой сбой импорта = fallback
    duckdb = None

_INDEX_SQL: dict[str, tuple[str, ...]] = {
    "sqlite3": ("CREATE INDEX IF NOT EXISTS idx_bridge_requests_ts ON bridge_requests (ts_epoch)",),
}


class RequestTelemetryStore:
    """Неблокирующая очередь + один фоновый writer; все операции с БД — под одним замком."""

    def __init__(self, db_path: str | None = None, *, force_sqlite: bool = False, autostart: bool = True, **cfg: Any) -> None:
        self.enabled = bool(opt("enabled", cfg))
        keys = ("queue_maxsize", "flush_interval_ms", "batch_size", "retention_days", "max_rows", "recent_limit",
                "prune_interval_s", "window_min_h", "window_max_h", "limit_max")
        self._c = {key: opt(key, cfg) for key in keys}
        self._queue: queue.Queue[tuple] = queue.Queue(maxsize=max(1, int(self._c["queue_maxsize"])))
        self._db_lock, self._stat_lock, self._stop = threading.Lock(), threading.Lock(), threading.Event()
        self.recent_limit = int(self._c["recent_limit"])
        self._dropped_events, self._last_prune = 0, 0.0
        self._thread: threading.Thread | None = None
        self._con: Any = None
        self.engine, self.db_path = "disabled", str(first(db_path, opt("db_path", cfg)))
        if self.enabled:
            self._open(force_sqlite)
        if all((self._con is not None, autostart)):
            self._thread = threading.Thread(target=self._writer_loop, name="bridge-telemetry-writer", daemon=True)
            self._thread.start()
            atexit.register(self.close)

    def _connect(self, base: str, force_sqlite: bool) -> tuple[Any, str, str]:
        """Соединение DuckDB либо sqlite3-фолбэк с агрегатом quantile_cont."""
        connect: Any = getattr(duckdb, "connect", None)
        try:
            con: Any = None if force_sqlite else connect(base)
        except Exception:  # noqa: BLE001 - занятый/повреждённый файл/lock -> sqlite3
            con = None
        if con is not None:
            return con, "duckdb", base
        path = os.path.splitext(base)[0] + ".sqlite3"
        con = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        con.create_aggregate("quantile_cont", 2, Quantile)
        return con, "sqlite3", path

    def _open(self, force_sqlite: bool) -> None:
        """Открыть стор (DuckDB либо sqlite3); любой сбой не роняет мост, стор остаётся disabled."""
        base = os.path.expanduser(self.db_path)
        try:
            os.makedirs(first(os.path.dirname(base), "."), mode=0o700, exist_ok=True)
            con, self.engine, self.db_path = self._connect(base, force_sqlite)
            con.execute(f"CREATE TABLE IF NOT EXISTS bridge_requests ({SCHEMA})")
            self._con = con
            for statement in _INDEX_SQL.get(self.engine, ()):
                con.execute(statement)
            os.chmod(self.db_path, 0o600)
            self.prune()
        except Exception:  # noqa: BLE001 - телеметрия не должна ронять мост
            self._con, self.engine = None, "disabled"

    def record_request(self, event: Mapping[str, Any]) -> bool:
        """Горячий путь: без I/O и ожиданий; False — отключено, мусор в событии или очередь полна."""
        if self._con is None:
            return False
        try:
            self._queue.put_nowait(make_row(event))
            return True
        except queue.Full:
            with self._stat_lock:
                self._dropped_events += 1
        except Exception:  # noqa: BLE001
            pass
        return False

    def _drain(self) -> list[tuple]:
        """Снять до batch_size строк из очереди без ожидания."""
        batch: list[tuple] = []
        while len(batch) < as_int(self._c["batch_size"]):
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _store_batch(self, batch: list[tuple]) -> int:
        """Одна транзакция INSERT; при сбое пачка учитывается как потерянная, откат не роняет writer."""
        try:
            with self._db_lock:
                self._con.execute("BEGIN")
                self._con.executemany(f"INSERT INTO bridge_requests VALUES ({', '.join('?' * len(NAMES))})", batch)
                self._con.execute("COMMIT")
            return len(batch)
        except Exception:  # noqa: BLE001
            with self._stat_lock:
                self._dropped_events += len(batch)
            with self._db_lock:
                try:
                    self._con.execute("ROLLBACK")
                except Exception:  # noqa: BLE001
                    pass
            return 0

    def flush(self) -> int:
        """Синхронно записать всё из очереди пачками batch_size (writer, тесты, shutdown)."""
        written = 0
        while self._con is not None:
            batch = self._drain()
            if not batch:
                break
            written += self._store_batch(batch)
        return written

    def prune(self) -> None:
        """Удалить строки старше retention_days и сверх max_rows."""
        if self._con is None:
            return
        cutoff = time.time() - as_float(self._c["retention_days"]) * 86400.0
        with self._db_lock:
            self._con.execute("DELETE FROM bridge_requests WHERE ts_epoch < ?", [cutoff])
            self._con.execute(
                "DELETE FROM bridge_requests WHERE ts_epoch <= "
                "(SELECT ts_epoch FROM bridge_requests ORDER BY ts_epoch DESC LIMIT 1 OFFSET ?)",
                [as_int(self._c["max_rows"])],
            )
        self._last_prune = time.monotonic()

    def _prune_due(self) -> bool:
        """Пора ли чистить стор: с последнего prune прошёл prune_interval_s."""
        return time.monotonic() - self._last_prune >= as_float(self._c["prune_interval_s"])

    def _writer_loop(self) -> None:
        """Фоновый writer: пачки по flush_interval_ms и периодический prune."""
        while not self._stop.wait(max(0.01, as_float(self._c["flush_interval_ms"]) / 1000.0)):
            self.flush()
            if self._prune_due():
                try:
                    self.prune()
                except Exception:  # noqa: BLE001
                    self._last_prune = time.monotonic()

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
        self.flush()
        with self._db_lock:
            close_quietly(self._con)
            self._con = None

    def _query(self, sql: str, params: Sequence[Any] = (), rate: bool = False) -> list[dict[str, Any]]:
        """SELECT под замком: строки приводятся к скалярам, агрегаты получают ok_rate_pct."""
        with self._db_lock:
            cur = self._con.execute(sql, list(params))
            cols = [d[0] for d in cur.description]
            return [clean_row(dict(zip(cols, row)), rate) for row in cur.fetchall()]

    def _group(self, keys: str, names: Sequence[str], bounds: tuple[float, int], rate: bool = True) -> list[dict[str, Any]]:
        """GROUP BY-разрез за окно: сортировка по числу запросов, затем по ключу."""
        return self._query(
            f"SELECT {keys}, {select_aggregates(names)} FROM bridge_requests WHERE ts_epoch >= ? "
            f"GROUP BY {keys} ORDER BY requests DESC, {keys} LIMIT ?", list(bounds), rate)

    def get_telemetry_payload(self, window_hours: float = 24.0, limit: int = 100) -> dict[str, Any]:
        """Агрегаты за окно: summary, by_model/backend/client/hour, recent_requests, architecture_flow."""
        payload: dict[str, Any] = {
            "enabled": all((self.enabled, self._con is not None)), "engine": self.engine, "db_path": self.db_path,
            "window_hours": self._window(window_hours), "generated_at": time.time(),
            "dropped_events": self._dropped_events, "queue_size": self._queue.qsize(),
            "summary": dict.fromkeys([*SUMMARY_COLS, "ok_rate_pct"], 0), "by_model": [],
            "by_backend": [], "by_client": [], "by_hour": [], "recent_requests": [],
        }
        callers: list[dict[str, Any]] = []
        if self._con is not None:
            since = payload["generated_at"] - payload["window_hours"] * 3600.0
            callers = self._fill(payload, since, self._limit(limit))
        payload["architecture_flow"] = build_architecture_flow(payload["by_backend"], callers, payload["summary"])
        return payload

    def _window(self, window_hours: float) -> float:
        """Окно в часах, зажатое в [window_min_h, window_max_h]; мусор -> 24 часа."""
        lo, hi = as_float(self._c["window_min_h"]), as_float(self._c["window_max_h"])
        try:
            return max(lo, min(hi, float(window_hours)))
        except (TypeError, ValueError):
            return 24.0

    def _limit(self, limit: int) -> int:
        """Лимит строк recent, зажатый в [1, limit_max]; мусор -> recent_limit."""
        try:
            return max(1, min(as_int(self._c["limit_max"]), int(limit)))
        except (TypeError, ValueError):
            return int(self._c["recent_limit"])

    def _fill(self, payload: dict[str, Any], since: float, limit: int) -> list[dict[str, Any]]:
        """Заполнить разрезы снимка одним окном и вернуть строки для карты потока."""
        payload["summary"] = self._query(
            f"SELECT {select_aggregates(SUMMARY_COLS)} FROM bridge_requests WHERE ts_epoch >= ?", [since], True)[0]
        payload["by_model"] = self._group("model, backend_id", MODEL_COLS, (since, limit))
        payload["by_backend"] = self._group("backend_id, route_mode, outbound_target, egress_proxy", BACKEND_COLS, (since, limit))
        payload["by_client"] = self._group(
            "client_kind, subagent_role, subagent_id, user_agent, client_ip", CLIENT_COLS, (since, limit), False)
        hours = self._query(
            f"SELECT substr(ts_iso, 1, 13) AS hour_bucket, {select_aggregates(HOUR_COLS)} FROM bridge_requests "
            "WHERE ts_epoch >= ? GROUP BY substr(ts_iso, 1, 13) ORDER BY hour_bucket", [since])
        payload["by_hour"] = [{**row, "hour_bucket": f"{row['hour_bucket']}:00:00Z"} for row in hours]
        recent = [name for name in NAMES if name not in ("client_port", "auth_mode")]
        rows = self._query(
            f"SELECT {', '.join(recent)} FROM bridge_requests WHERE ts_epoch >= ? ORDER BY ts_epoch DESC LIMIT ?", [since, limit])
        payload["recent_requests"] = [{**row, "stream": bool(row["stream"])} for row in rows]
        return self._query(
            "SELECT client_kind, subagent_role, user_agent, COUNT(*) AS requests FROM bridge_requests "
            "WHERE ts_epoch >= ? GROUP BY client_kind, subagent_role, user_agent", [since])
