"""Чтение телеметрии: снимок агрегатов /v1/telemetry поверх соединения стора (общий замок с writer)."""

from __future__ import annotations

import math
import queue
import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any

from core.telemetry_flow import build_architecture_flow
from core.telemetry_sql import (
    BACKEND_COLS,
    CLIENT_COLS,
    HOUR_COLS,
    MODEL_COLS,
    NAMES,
    SUMMARY_COLS,
    add_aliases,
    clean_row,
    opt,
    select_aggregates,
)
from core.telemetry_util import as_float, as_int, first_truthy


CONFIG_KEYS = ("queue_maxsize", "flush_interval_ms", "batch_size", "retention_days", "max_rows", "recent_limit",
               "prune_interval_s", "window_min_h", "window_max_h", "limit_max", "flush_max_batches", "prune_retry_s",
               "max_field_len", "redact_scan_factor", "redact_scan_min")


class TelemetryReader:
    """Общее состояние стора (очередь, замки, счётчики) и чтение снимка; ensure_open() даёт RequestTelemetryStore."""

    def __init__(self, db_path: str | None, cfg: Mapping[str, Any]) -> None:
        self._c: dict[str, Any] = {key: opt(key, cfg) for key in CONFIG_KEYS}
        self._queue: queue.Queue[Mapping[str, Any]] = queue.Queue(maxsize=max(1, as_int(self._c["queue_maxsize"])))
        self._db_lock, self._stat_lock = threading.RLock(), threading.Lock()
        self._stats = {"dropped_events": 0, "prune_errors": 0, "rollback_errors": 0}
        self._con: Any = None
        self._ready = False
        self.recent_limit = as_int(self._c["recent_limit"])
        self.engine, self.db_path = "disabled", str(first_truthy(db_path, opt("db_path", cfg)))

    def ensure_open(self) -> bool:
        raise NotImplementedError

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
        live = self.ensure_open()
        with self._stat_lock:
            stats = dict(self._stats)
        payload: dict[str, Any] = {
            "enabled": live, "engine": self.engine, "db_path": self.db_path,
            "window_hours": self._window(window_hours), "generated_at": time.time(),
            "dropped_events": stats["dropped_events"], "prune_errors": stats["prune_errors"],
            "queue_size": self._queue.qsize(),
            "summary": add_aliases(dict.fromkeys([*SUMMARY_COLS, "ok_rate_pct"], 0)), "by_model": [],
            "by_backend": [], "by_client": [], "by_hour": [], "recent_requests": [],
        }
        with self._db_lock:
            since = payload["generated_at"] - payload["window_hours"] * 3600.0
            callers = self._fill(payload, since, self._limit(limit)) if all((live, self._ready)) else []
        payload["summary"]["dropped_events"] = stats["dropped_events"]  # KPI «движок БД» в UI читает summary
        payload["architecture_flow"] = build_architecture_flow(payload["by_backend"], callers, payload["summary"])
        return payload

    def _window(self, window_hours: float) -> float:
        """Окно в часах, зажатое в [window_min_h, window_max_h]; NaN и мусор -> 24 часа."""
        lo, hi = as_float(self._c["window_min_h"]), as_float(self._c["window_max_h"])
        value = as_float(window_hours, 24.0)
        return max(lo, min(hi, (value, 24.0)[math.isnan(value)]))

    def _limit(self, limit: int) -> int:
        """Лимит строк recent, зажатый в [1, limit_max]; мусор -> recent_limit."""
        return max(1, min(as_int(self._c["limit_max"]), as_int(limit, self.recent_limit)))

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
