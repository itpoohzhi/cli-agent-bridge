"""Универсальная телеметрия запросов моста: DuckDB (fallback sqlite3), неблокирующая очередь.

Хранит только скаляры: промпты, тела, карты заголовков и env не сохраняются, секреты
редактируются до постановки в очередь. Агент-агностично: знает про backend_id, а не про агентов.
"""

from __future__ import annotations

import atexit
import math
import os
import queue
import re
import sqlite3
import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any

from core import defaults as D
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
    select_aggregates,
)

try:  # DuckDB опционален: без него тот же SQL исполняется на stdlib sqlite3.
    import duckdb  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
except Exception:  # noqa: BLE001 - любой сбой импорта = fallback
    duckdb = None

_COERCE = {"VARCHAR": str, "INTEGER": int, "BIGINT": int, "DOUBLE": float, "BOOLEAN": bool}
_REDACT = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"sk-[A-Za-z0-9._\-]{6,}"),
    re.compile(r"(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{10,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|key)\s*[:=]\s*[^\s,;]+"),
)
_GETTERS = {bool: D.get_env_bool, int: D.get_env_int, float: D.get_env_float, str: D.get_env_str}


def _opt(key: str, cfg: Mapping[str, Any]) -> Any:
    """Явное значение > переменная окружения BRIDGE_TELEMETRY_<KEY> > core.defaults."""
    name = f"BRIDGE_TELEMETRY_{key.upper()}"
    default = getattr(D, name)
    return cfg[key] if key in cfg else _GETTERS[type(default)](name, default)


def sanitize_scalar(value: Any, max_len: int | None = None) -> Any:
    """Скаляр или None: числа/bool как есть, строки редактируются и усекаются, остальное отбрасывается."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if not isinstance(value, str):
        return None  # dict/list/bytes (тела, заголовки, env) не хранятся
    for pattern in _REDACT:
        value = pattern.sub("[REDACTED]", value)
    return value[: max_len or D.get_env_int("BRIDGE_TELEMETRY_MAX_FIELD_LEN", D.BRIDGE_TELEMETRY_MAX_FIELD_LEN)]


def classify_caller(subagent_id: Any = None, subagent_role: Any = None) -> dict[str, str]:
    """subagent_id/role/client_kind; первым аргументом можно передать карту заголовков/событие."""
    if isinstance(subagent_id, Mapping):
        low = {str(k).lower(): v for k, v in subagent_id.items()}
        subagent_id = low.get("x-subagent-id") or low.get("subagent_id")
        subagent_role = low.get("x-subagent-role") or low.get("subagent_role")
    sid = str(sanitize_scalar(subagent_id) or "").strip()
    role = str(sanitize_scalar(subagent_role) or "").strip().lower()
    role = role or (sid.split("-", 1)[0].lower() if sid else "interactive")
    return {"subagent_id": sid, "subagent_role": role, "client_kind": "subagent" if sid else "interactive"}


def _make_row(event: Mapping[str, Any]) -> tuple:
    """Событие -> кортеж по COLUMNS; только allowlist-скаляры, типы приводятся, мусор -> None."""
    vals: dict[str, Any] = {n: sanitize_scalar(event.get(n)) for n in NAMES}
    vals.update(classify_caller(event.get("subagent_id"), event.get("subagent_role")))
    ts = event.get("ts_epoch")
    ts = float(ts) if isinstance(ts, (int, float)) and math.isfinite(ts) else time.time()
    vals["ts_epoch"], vals["ts_iso"] = ts, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
    vals["request_id"] = vals["request_id"] or ""
    vals["auth_mode"] = vals["auth_mode"] or "none"
    row = []
    for name, typ in COLUMNS:
        try:
            row.append(None if vals[name] is None else _COERCE[typ](vals[name]))
        except (TypeError, ValueError):
            row.append(None)
    return tuple(row)


def _clean(row: dict[str, Any], rate: bool = False) -> dict[str, Any]:
    out = {k: round(v, 2) if isinstance(v, float) else v for k, v in row.items()}
    if rate:
        total = out.get("requests", out.get("total_requests")) or 0
        out["ok_rate_pct"] = round(100.0 * (out.get("ok_requests") or 0) / total, 2) if total else 0.0
    return out


class RequestTelemetryStore:
    """Неблокирующая очередь + один фоновый writer; все операции с БД — под одним замком."""

    def __init__(self, db_path: str | None = None, *, force_sqlite: bool = False, autostart: bool = True, **cfg: Any) -> None:
        self.enabled = bool(_opt("enabled", cfg))
        keys = ("queue_maxsize", "flush_interval_ms", "batch_size", "retention_days", "max_rows", "recent_limit",
                "prune_interval_s", "window_min_h", "window_max_h", "limit_max")
        self._c = {k: _opt(k, cfg) for k in keys}
        self._queue: queue.Queue[tuple] = queue.Queue(maxsize=max(1, int(self._c["queue_maxsize"])))
        self._db_lock, self._stat_lock, self._stop = threading.Lock(), threading.Lock(), threading.Event()
        self.recent_limit = int(self._c["recent_limit"])
        self._dropped_events, self._last_prune = 0, 0.0
        self._thread: threading.Thread | None = None
        self._con: Any = None
        self.engine, self.db_path = "disabled", str(db_path or _opt("db_path", cfg))
        if self.enabled:
            self._open(force_sqlite)
        if self._con is not None and autostart:
            self._thread = threading.Thread(target=self._writer_loop, name="bridge-telemetry-writer", daemon=True)
            self._thread.start()
            atexit.register(self.close)

    def _open(self, force_sqlite: bool) -> None:
        base = os.path.expanduser(self.db_path)
        try:
            os.makedirs(os.path.dirname(base) or ".", mode=0o700, exist_ok=True)
            if duckdb is not None and not force_sqlite:
                try:
                    self._con, self.engine, self.db_path = duckdb.connect(base), "duckdb", base
                except Exception:  # noqa: BLE001 - повреждённый файл/lock -> sqlite3
                    self._con = None
            if self._con is None:
                path = os.path.splitext(base)[0] + ".sqlite3"
                self._con = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
                self._con.create_aggregate("quantile_cont", 2, Quantile)
                self.engine, self.db_path = "sqlite3", path
            self._con.execute(f"CREATE TABLE IF NOT EXISTS bridge_requests ({SCHEMA})")
            if self.engine == "sqlite3":
                self._con.execute("CREATE INDEX IF NOT EXISTS idx_bridge_requests_ts ON bridge_requests (ts_epoch)")
            os.chmod(self.db_path, 0o600)
            self.prune()
        except Exception:  # noqa: BLE001 - телеметрия не должна ронять мост
            self._con, self.engine = None, "disabled"

    def record_request(self, event: Mapping[str, Any]) -> bool:
        """Горячий путь: без I/O и ожиданий; False — отключено, мусор в событии или очередь полна."""
        if self._con is None:
            return False
        try:
            row = _make_row(event)
            self._queue.put_nowait(row)
            return True
        except queue.Full:
            with self._stat_lock:
                self._dropped_events += 1
        except Exception:  # noqa: BLE001
            pass
        return False

    def flush(self) -> int:
        """Синхронно записать всё из очереди пачками batch_size (writer, тесты, shutdown)."""
        written = 0
        while self._con is not None:
            batch: list[tuple] = []
            while len(batch) < int(self._c["batch_size"]):
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if not batch:
                break
            try:
                with self._db_lock:
                    self._con.execute("BEGIN")
                    self._con.executemany(f"INSERT INTO bridge_requests VALUES ({', '.join('?' * len(NAMES))})", batch)
                    self._con.execute("COMMIT")
                written += len(batch)
            except Exception:  # noqa: BLE001
                with self._stat_lock:
                    self._dropped_events += len(batch)
                with self._db_lock:
                    try:
                        self._con.execute("ROLLBACK")
                    except Exception:  # noqa: BLE001
                        pass
        return written

    def prune(self) -> None:
        """Удалить строки старше retention_days и сверх max_rows."""
        if self._con is None:
            return
        cutoff = time.time() - float(self._c["retention_days"]) * 86400.0
        with self._db_lock:
            self._con.execute("DELETE FROM bridge_requests WHERE ts_epoch < ?", [cutoff])
            self._con.execute(
                "DELETE FROM bridge_requests WHERE ts_epoch <= "
                "(SELECT ts_epoch FROM bridge_requests ORDER BY ts_epoch DESC LIMIT 1 OFFSET ?)",
                [int(self._c["max_rows"])],
            )
        self._last_prune = time.monotonic()

    def _writer_loop(self) -> None:
        while not self._stop.wait(max(0.01, float(self._c["flush_interval_ms"]) / 1000.0)):
            self.flush()
            if time.monotonic() - self._last_prune >= float(self._c["prune_interval_s"]):
                try:
                    self.prune()
                except Exception:  # noqa: BLE001
                    self._last_prune = time.monotonic()

    def close(self) -> None:
        """Идемпотентно: остановить writer, дописать очередь, закрыть соединение."""
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=5.0)
        self.flush()
        with self._db_lock:
            if self._con is not None:
                self._con.close()
                self._con = None

    def _query(self, sql: str, params: Sequence[Any] = (), rate: bool = False) -> list[dict[str, Any]]:
        with self._db_lock:
            cur = self._con.execute(sql, list(params))
            cols = [d[0] for d in cur.description]
            return [_clean(dict(zip(cols, r)), rate) for r in cur.fetchall()]

    def _group(self, keys: str, names: Sequence[str], bounds: tuple[float, int], rate: bool = True) -> list[dict[str, Any]]:
        return self._query(
            f"SELECT {keys}, {select_aggregates(names)} FROM bridge_requests WHERE ts_epoch >= ? "
            f"GROUP BY {keys} ORDER BY requests DESC, {keys} LIMIT ?", list(bounds), rate)

    def get_telemetry_payload(self, window_hours: float = 24.0, limit: int = 100) -> dict[str, Any]:
        """Агрегаты за окно: summary, by_model/backend/client/hour, recent_requests, architecture_flow."""
        lo, hi = float(self._c["window_min_h"]), float(self._c["window_max_h"])
        try:
            window = min(max(float(window_hours), lo), hi)
        except (TypeError, ValueError):
            window = 24.0
        try:
            lim = min(max(int(limit), 1), int(self._c["limit_max"]))
        except (TypeError, ValueError):
            lim = int(self._c["recent_limit"])
        now = time.time()
        payload: dict[str, Any] = {
            "enabled": self.enabled and self._con is not None, "engine": self.engine, "db_path": self.db_path,
            "window_hours": window, "generated_at": now, "dropped_events": self._dropped_events,
            "queue_size": self._queue.qsize(), "summary": dict.fromkeys([*SUMMARY_COLS, "ok_rate_pct"], 0), "by_model": [],
            "by_backend": [], "by_client": [], "by_hour": [], "recent_requests": [],
        }
        callers: list[dict[str, Any]] = []
        if self._con is not None:
            since = now - window * 3600.0
            payload["summary"] = self._query(f"SELECT {select_aggregates(SUMMARY_COLS)} FROM bridge_requests WHERE ts_epoch >= ?", [since], True)[0]
            payload["by_model"] = self._group("model, backend_id", MODEL_COLS, (since, lim))
            payload["by_backend"] = self._group("backend_id, route_mode, outbound_target, egress_proxy", BACKEND_COLS, (since, lim))
            payload["by_client"] = self._group("client_kind, subagent_role, subagent_id, user_agent, client_ip", CLIENT_COLS, (since, lim), False)
            callers = self._query(
                "SELECT client_kind, subagent_role, user_agent, COUNT(*) AS requests FROM bridge_requests "
                "WHERE ts_epoch >= ? GROUP BY client_kind, subagent_role, user_agent", [since])
            hours = self._query(
                f"SELECT substr(ts_iso, 1, 13) AS hour_bucket, {select_aggregates(HOUR_COLS)} FROM bridge_requests "
                "WHERE ts_epoch >= ? GROUP BY substr(ts_iso, 1, 13) ORDER BY hour_bucket", [since])
            payload["by_hour"] = [{**h, "hour_bucket": f"{h['hour_bucket']}:00:00Z"} for h in hours]
            recent = [n for n in NAMES if n not in ("client_port", "auth_mode")]
            rows = self._query(f"SELECT {', '.join(recent)} FROM bridge_requests WHERE ts_epoch >= ? ORDER BY ts_epoch DESC LIMIT ?", [since, lim])
            payload["recent_requests"] = [{**r, "stream": bool(r["stream"])} for r in rows]
        payload["architecture_flow"] = build_architecture_flow(payload["by_backend"], callers, payload["summary"])
        return payload
