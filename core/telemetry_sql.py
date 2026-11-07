"""SQL-слой телеметрии: схема bridge_requests и агрегаты, общие для duckdb и sqlite3."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

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


