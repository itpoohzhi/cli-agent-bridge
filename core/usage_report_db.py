"""Read-only загрузка bridge_requests из SQLite или DuckDB для usage_report."""

from __future__ import annotations

import contextlib
import importlib
import sqlite3
from pathlib import Path
from typing import Any

from core.usage_report_render import filter_and_sort


def load_db_records(path: str, days: float) -> list[dict[str, Any]]:
    """Прочитать таблицу bridge_requests (read-only) из DuckDB или sqlite3."""
    if not (db_path := Path(path).expanduser()).is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")
    with db_path.open("rb") as handle:
        is_sqlite = handle.read(16) == b"SQLite format 3\x00"
    try:
        conn = (
            sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
            if is_sqlite
            else getattr(importlib.import_module("duckdb"), "connect")(str(db_path), read_only=True)
        )
        with contextlib.closing(conn):
            cur = conn.execute("SELECT * FROM bridge_requests ORDER BY ts_epoch ASC")
            cols = tuple(c[0] for c in (cur.description or ()))
            return filter_and_sort([dict(zip(cols, r, strict=False)) for r in cur.fetchall()], days)
    except sqlite3.Error as exc:
        raise RuntimeError(f"SQLite read error: {exc}") from exc
