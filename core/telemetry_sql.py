"""SQL-слой телеметрии: схема bridge_requests, агрегаты и нормализация события в строку стора."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from core import defaults as D
from core.telemetry_util import as_float, as_int, as_str, first

SCHEMA = (
    "request_id VARCHAR, ts_epoch DOUBLE, ts_iso VARCHAR, client_ip VARCHAR, client_port INTEGER, "
    "user_agent VARCHAR, subagent_id VARCHAR, subagent_role VARCHAR, client_kind VARCHAR, "
    "auth_mode VARCHAR, http_method VARCHAR, endpoint VARCHAR, model VARCHAR, backend_id VARCHAR, "
    "route_mode VARCHAR, outbound_target VARCHAR, egress_proxy VARCHAR, stream BOOLEAN, "
    "status_code INTEGER, error_type VARCHAR, queue_ms DOUBLE, ttfb_ms DOUBLE, total_ms DOUBLE, "
    "stream_chunks INTEGER, prompt_tokens INTEGER, completion_tokens INTEGER, cached_tokens INTEGER, "
    "total_tokens INTEGER, response_bytes BIGINT"
)
COLUMNS: tuple[tuple[str, str], ...] = tuple((n, t) for n, t in (part.split() for part in SCHEMA.split(", ")))
NAMES = tuple(name for name, _ in COLUMNS)
_OK = "(status_code >= 200 AND status_code < 400)"
_Q = "quantile_cont({}, {})"
_E = {  # SQL-выражения агрегатов; одни и те же для duckdb и sqlite3
    "requests": "COUNT(*)",
    "total_requests": "COUNT(*)",
    "ok_requests": f"COALESCE(SUM(CASE WHEN {_OK} THEN 1 ELSE 0 END), 0)",
    "error_requests": f"COALESCE(SUM(CASE WHEN {_OK} THEN 0 ELSE 1 END), 0)",
    "stream_requests": "COALESCE(SUM(CASE WHEN stream THEN 1 ELSE 0 END), 0)",
    "subagent_requests": "COALESCE(SUM(CASE WHEN client_kind = 'subagent' THEN 1 ELSE 0 END), 0)",
    "interactive_requests": "COALESCE(SUM(CASE WHEN client_kind = 'subagent' THEN 0 ELSE 1 END), 0)",
    "avg_queue_ms": "AVG(queue_ms)",
    "avg_ttfb_ms": "AVG(ttfb_ms)",
    "avg_total_ms": "AVG(total_ms)",
    "max_total_ms": "MAX(total_ms)",
    "total_response_bytes": "COALESCE(SUM(response_bytes), 0)",
    "last_seen_ts": "MAX(ts_epoch)",
    **{f"p{q}_{c}_ms": _Q.format(f"{c}_ms", q / 100) for q in (50, 95, 99) for c in ("ttfb", "total")},
    **{t: f"COALESCE(SUM({t}), 0)" for t in ("prompt_tokens", "completion_tokens", "cached_tokens", "total_tokens")},
}
SUMMARY_COLS = (
    "total_requests ok_requests error_requests stream_requests subagent_requests interactive_requests "
    "avg_queue_ms avg_ttfb_ms p50_ttfb_ms p95_ttfb_ms p99_ttfb_ms avg_total_ms p50_total_ms p95_total_ms "
    "p99_total_ms max_total_ms prompt_tokens completion_tokens cached_tokens total_tokens total_response_bytes"
).split()
MODEL_COLS = "requests ok_requests error_requests avg_ttfb_ms p50_total_ms p95_total_ms avg_total_ms max_total_ms prompt_tokens completion_tokens cached_tokens total_tokens".split()
BACKEND_COLS = "requests ok_requests error_requests avg_ttfb_ms p50_total_ms p95_total_ms avg_total_ms total_tokens".split()
CLIENT_COLS = "requests ok_requests error_requests avg_total_ms total_tokens last_seen_ts".split()
HOUR_COLS = "requests ok_requests error_requests total_tokens avg_total_ms".split()


class Quantile:
    """quantile_cont для sqlite3 (линейная интерполяция, как в duckdb)."""

    def __init__(self) -> None:
        self.values: list[float] = []
        self.q = 0.5

    def step(self, value: Any, q: float) -> None:
        if value is not None:
            self.values.append(value)
            self.q = q

    def finalize(self) -> float | None:
        if not self.values:
            return None
        v = sorted(self.values)
        pos = (len(v) - 1) * self.q
        lo, hi = int(pos), min(int(pos) + 1, len(v) - 1)
        return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def select_aggregates(names: Sequence[str]) -> str:
    return ", ".join(f"{_E[n]} AS {n}" for n in names)


_COERCE: dict[str, Callable[[Any], Any]] = {"VARCHAR": str, "INTEGER": int, "BIGINT": int, "DOUBLE": float, "BOOLEAN": bool}
_REDACT = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"sk-[A-Za-z0-9._\-]{6,}"),
    re.compile(r"(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{10,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|key)\s*[:=]\s*[^\s,;]+"),
)
_GETTERS = {bool: D.get_env_bool, int: D.get_env_int, float: D.get_env_float, str: D.get_env_str}


def opt(key: str, cfg: Mapping[str, Any]) -> Any:
    """Явное значение > переменная окружения BRIDGE_TELEMETRY_<KEY> > core.defaults."""
    name = f"BRIDGE_TELEMETRY_{key.upper()}"
    default = getattr(D, name)
    return cfg.get(key, _GETTERS[type(default)](name, default))


def _coerce(typ: str, value: Any) -> Any:
    """Приведение к типу колонки; None и мусор дают None."""
    result: Any = None
    if value is not None:
        try:
            result = _COERCE[typ](value)
        except (TypeError, ValueError):
            result = None
    return result


def sanitize_scalar(value: Any, max_len: int | None = None) -> Any:
    """Скаляр или None: числа/bool как есть, строки редактируются и усекаются, остальное отбрасывается."""
    limit = as_int(first(max_len, D.get_env_int("BRIDGE_TELEMETRY_MAX_FIELD_LEN", D.BRIDGE_TELEMETRY_MAX_FIELD_LEN)))
    if isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if not isinstance(value, str):
        return None
    for pattern in _REDACT:
        value = pattern.sub("[REDACTED]", value)
    return value[:limit]


def classify_caller(subagent_id: Any = None, subagent_role: Any = None) -> dict[str, str]:
    """subagent_id/role/client_kind; первым аргументом можно передать карту заголовков/событие."""
    mapping = subagent_id if isinstance(subagent_id, Mapping) else {}
    low = {str(key).lower(): value for key, value in mapping.items()}
    raw_id = first(low.get("x-subagent-id"), low.get("subagent_id"), first(subagent_id, None) if not mapping else None)
    raw_role = first(low.get("x-subagent-role"), low.get("subagent_role"), subagent_role)
    sid = as_str(sanitize_scalar(raw_id)).strip()
    role = as_str(sanitize_scalar(raw_role)).strip().lower()
    role = first(role, sid.split("-", 1)[0].lower() if sid else "interactive")
    return {"subagent_id": sid, "subagent_role": role, "client_kind": "subagent" if sid else "interactive"}


def make_row(event: Mapping[str, Any]) -> tuple:
    """Событие -> кортеж по COLUMNS; только allowlist-скаляры, типы приводятся, мусор -> None."""
    vals: dict[str, Any] = {name: sanitize_scalar(event.get(name)) for name in NAMES}
    vals.update(classify_caller(event.get("subagent_id"), event.get("subagent_role")))
    stamp = as_float(event.get("ts_epoch"), math.nan)
    ts = stamp if math.isfinite(stamp) else time.time()
    vals["ts_epoch"], vals["ts_iso"] = ts, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
    vals["request_id"] = as_str(vals["request_id"])
    vals["auth_mode"] = first(vals["auth_mode"], "none")
    return tuple(_coerce(typ, vals[name]) for name, typ in COLUMNS)


def clean_row(row: dict[str, Any], rate: bool = False) -> dict[str, Any]:
    """Ответ SQL -> скаляры с округлением; для агрегатов — ещё и ok_rate_pct."""
    out = {key: round(value, 2) if isinstance(value, float) else value for key, value in row.items()}
    if rate:
        total = as_int(first(out.get("requests"), out.get("total_requests")))
        out["ok_rate_pct"] = round(100.0 * as_int(out.get("ok_requests")) / total, 2) if total else 0.0
    return out

