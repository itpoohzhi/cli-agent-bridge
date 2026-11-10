"""SQL-слой телеметрии: схема bridge_requests, агрегаты и нормализация события в строку стора."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from core import defaults as D
from core.telemetry_util import as_float, as_int, as_str, first_truthy, value_or_else

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
    "outbound_target": "MAX(outbound_target)",
    "egress_proxy": "MAX(egress_proxy)",
    **{f"p{q}_{c}_ms": _Q.format(f"{c}_ms", q / 100) for q in (50, 95, 99) for c in ("ttfb", "total")},
    **{t: f"COALESCE(SUM({t}), 0)" for t in ("prompt_tokens", "completion_tokens", "cached_tokens", "total_tokens")},
}
SUMMARY_COLS = (
    "total_requests ok_requests error_requests stream_requests subagent_requests interactive_requests "
    "avg_queue_ms avg_ttfb_ms p50_ttfb_ms p95_ttfb_ms p99_ttfb_ms avg_total_ms p50_total_ms p95_total_ms "
    "p99_total_ms max_total_ms prompt_tokens completion_tokens cached_tokens total_tokens total_response_bytes"
).split()
MODEL_COLS = "outbound_target egress_proxy requests ok_requests error_requests avg_ttfb_ms p50_total_ms p95_total_ms avg_total_ms max_total_ms prompt_tokens completion_tokens cached_tokens total_tokens".split()
BACKEND_COLS = "requests ok_requests error_requests avg_ttfb_ms p50_total_ms p95_total_ms avg_total_ms max_total_ms total_tokens".split()
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
_MASK = "[REDACTED]"
# Порядок важен: многословные заголовки и схемы Bearer/Basic раньше «ключ=значение», чтобы не остался хвост токена.
_REDACT: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b(?:authorization|proxy-authorization)\s*[:=]\s*(?:bearer|basic|token|digest)\s+[^\s,;\"'}]+"), _MASK),
    (re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._\-+/~=]+"), _MASK),
    (re.compile(r"(?i)([a-z][a-z0-9+.\-]*://)[^/\s:@\"']+:[^@\s/\"']+@"), r"\1" + _MASK + "@"),
    (re.compile(
        r"\b(?:sk-[A-Za-z0-9_.\-]{6,}|sk_live_[A-Za-z0-9_\-]{6,}|rk-[A-Za-z0-9_\-]{6,}|AIza[0-9A-Za-z_\-]{8,}"
        r"|gh[pousr]_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{10,}|glpat-[A-Za-z0-9_\-]{6,}|AKIA[0-9A-Z]{12,}"
        r"|xox[baprs]-[A-Za-z0-9\-]{6,})"), _MASK),
    (re.compile(
        r"(?i)[\"']?(?:api[_-]?key|token|secret|password|passwd|pwd|authorization|client_secret|key)[\"']?\s*[:=]\s*"
        r"(?:[\"'][^\"']*(?:[\"']|$)|[^\s,;\"'}]+)"), _MASK),
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


def _same(value: Any, _max_len: int | None, _scan_len: int | None) -> Any:
    return value


def _finite(value: float, _max_len: int | None, _scan_len: int | None) -> float | None:
    result = value if math.isfinite(value) else None
    return result


def _drop(_value: Any, _max_len: int | None, _scan_len: int | None) -> None:
    return None


def scan_bound(limit: int, factor: int, floor: int) -> int:
    """До какой длины строка усекается перед regex-редакцией (регулярки не видят мегабайтных значений)."""
    return max(limit * factor, floor)


def _redacted(value: str, max_len: int | None, scan_len: int | None) -> str:
    """Строка: усечь по верхней границе, прогнать паттерны в заданном порядке, окончательно усечь до лимита."""
    limit = value_or_else(max_len, lambda: as_int(opt("max_field_len", {})))
    bound = value_or_else(
        scan_len, lambda: scan_bound(limit, as_int(opt("redact_scan_factor", {})), as_int(opt("redact_scan_min", {}))))
    text = value[:bound]
    for pattern, replacement in _REDACT:
        text = pattern.sub(replacement, text)
    return text[:limit]


_RULES: tuple[tuple[tuple[type, ...], Callable[[Any, int | None, int | None], Any]], ...] = (
    ((bool, int, type(None)), _same), ((float,), _finite), ((str,), _redacted),
)


def sanitize_scalar(value: Any, max_len: int | None = None, scan_len: int | None = None) -> Any:
    """Скаляр или None: числа/bool как есть, строки редактируются и усекаются, остальное отбрасывается.

    max_len/scan_len передаются числами (горячий путь не читает окружение); None — значения из BRIDGE_TELEMETRY_*.
    """
    rule = next((handler for types, handler in _RULES if isinstance(value, types)), _drop)
    return rule(value, max_len, scan_len)


def classify_caller(
    subagent_id: Any = None, subagent_role: Any = None, max_len: int | None = None, scan_len: int | None = None
) -> dict[str, str]:
    """subagent_id/role/client_kind; первым аргументом можно передать карту заголовков/событие."""
    mapping = subagent_id if isinstance(subagent_id, Mapping) else {}
    low = {str(key).lower(): value for key, value in mapping.items()}
    raw_id = first_truthy(
        low.get("x-subagent-id"), low.get("subagent_id"), first_truthy(subagent_id, None) if not mapping else None)
    raw_role = first_truthy(low.get("x-subagent-role"), low.get("subagent_role"), subagent_role)
    sid = as_str(sanitize_scalar(raw_id, max_len, scan_len)).strip()
    role = as_str(sanitize_scalar(raw_role, max_len, scan_len)).strip().lower()
    role = first_truthy(role, sid.split("-", 1)[0].lower() if sid else "interactive")
    return {"subagent_id": sid, "subagent_role": role, "client_kind": "subagent" if sid else "interactive"}


def make_row(event: Mapping[str, Any], max_len: int | None = None, scan_len: int | None = None) -> tuple:
    """Событие -> кортеж по COLUMNS; только allowlist-скаляры, типы приводятся, мусор -> None."""
    vals: dict[str, Any] = {name: sanitize_scalar(event.get(name), max_len, scan_len) for name in NAMES}
    vals.update(classify_caller(event.get("subagent_id"), event.get("subagent_role"), max_len, scan_len))
    stamp = as_float(event.get("ts_epoch"), math.nan)
    ts = stamp if math.isfinite(stamp) else time.time()
    vals["ts_epoch"], vals["ts_iso"] = ts, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
    vals["request_id"] = as_str(vals["request_id"])
    vals["auth_mode"] = first_truthy(vals["auth_mode"], "none")
    return tuple(_coerce(typ, vals[name]) for name, typ in COLUMNS)


_ALIASES: dict[str, tuple[str, ...]] = {  # канонические имена моста -> имена, которые читает UI control_panel
    **{f"p{q}_{c}_ms": (f"{c}_p{q}_ms",) for q in (50, 95, 99) for c in ("ttfb", "total")},
    "p50_total_ms": ("total_p50_ms", "p50_ms"), "p95_total_ms": ("total_p95_ms", "p95_ms"),
    "max_total_ms": ("total_max_ms", "max_ms"), "avg_total_ms": ("avg_ms",), "error_requests": ("errors",),
    "backend_id": ("backend",), "ts_epoch": ("ts",), "status_code": ("status",), "stream_chunks": ("chunks",),
}


def add_aliases(row: dict[str, Any]) -> dict[str, Any]:
    """Строка + UI-алиасы канонических ключей (единый mapping; канонические имена не удаляются)."""
    return {**row, **{alias: row[key] for key in row.keys() & _ALIASES.keys() for alias in _ALIASES[key]}}


def clean_row(row: dict[str, Any], rate: bool = False) -> dict[str, Any]:
    """Ответ SQL -> скаляры с округлением и алиасами; для агрегатов — ещё и ok_rate_pct."""
    out = {key: round(value, 2) if isinstance(value, float) else value for key, value in row.items()}
    if rate:
        total = as_int(first_truthy(out.get("requests"), out.get("total_requests")))
        out["ok_rate_pct"] = round(100.0 * as_int(out.get("ok_requests")) / total, 2) if total else 0.0
    return add_aliases(out)

