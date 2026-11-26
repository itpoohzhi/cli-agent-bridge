"""Загрузка usage.jsonl + companion cli-usage.jsonl и текстовый рендер отчёта usage_report."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import core.usage_analytics as ua

__all__: tuple[str, ...] = (
    "CLI_USAGE_NAME", "collect_jsonl_files", "filter_and_sort", "format_report", "load_jsonl", "load_jsonl_sources",
    "record_epoch", "render_table",
)

CLI_USAGE_NAME = "cli-usage.jsonl"
_TABLES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("BY MODEL", "by_model", ("model", "backend"), ("model", "backend_id")),
    ("BY ROLE", "by_role", ("role", "subagent_id"), ("subagent_role", "subagent_id")),
    ("BY ROUTE", "by_route", ("route", "backend"), ("route", "backend_id")),
    ("BY DAY", "by_day", ("day",), ("day",)),
)


def _parse_ts_value(val: Any) -> float | None:
    """Разобрать timestamp (epoch или ISO-8601) в секунды UTC."""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val) if math.isfinite(float(val)) else None
    if not isinstance(val, str) or not (text := val.strip()):
        return None
    try:
        dt = datetime.fromisoformat(f"{text[:-1]}+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    return (dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)).timestamp()


def record_epoch(record: Mapping[str, Any]) -> float | None:
    """Извлечь epoch-время записи из полей ts_epoch, ts или ts_iso."""
    return next((ep for k in ("ts_epoch", "ts", "ts_iso") if (ep := _parse_ts_value(record.get(k))) is not None), None)


def filter_and_sort(records: list[dict[str, Any]], days: float) -> list[dict[str, Any]]:
    """Отфильтровать записи по окну days (0 — без фильтра) и отсортировать по ts."""
    if days > 0.0:
        cutoff = time.time() - days * 86400.0
        records = [r for r in records if (ep := record_epoch(r)) is not None and ep >= cutoff]
    return sorted(
        records,
        key=lambda r: (record_epoch(r) or 0.0, str(r.get("ts") or r.get("ts_iso") or ""), str(r.get("request_id") or "")),
    )


def collect_jsonl_files(active: Path) -> tuple[Path, ...]:
    """Собрать ротированные архивы .N (от старых к новым) и активный JSONL-файл."""
    prefix = f"{active.name}."
    entries = active.parent.iterdir() if active.parent.is_dir() else ()
    archives = sorted(
        ((int(p.name[len(prefix):]), p) for p in entries
         if p.is_file() and p.name.startswith(prefix) and p.name[len(prefix):].isdigit()),
        key=lambda item: item[0], reverse=True,
    )
    return tuple(p for _, p in archives) + ((active,) if active.is_file() else ())


def _read_files(files: Sequence[Path]) -> tuple[list[dict[str, Any]], int]:
    """Прочитать JSONL-файлы (read-only), безопасно пропуская битые строки."""
    records: list[dict[str, Any]] = []
    skipped = 0
    for file_path in files:
        with file_path.open("r", encoding="utf-8", errors="replace") as handle:
            for text in (line.strip() for line in handle if line.strip()):
                try:
                    raw = json.loads(text)
                except json.JSONDecodeError:
                    raw = None
                if not isinstance(raw, dict):
                    skipped += 1
                    continue
                obj = ua.normalize_usage_record_aliases(raw)
                if isinstance(obj.get("ts"), str):
                    obj.setdefault("ts_iso", obj["ts"])
                records.append(obj)
    return records, skipped


def load_jsonl(path: str, days: float) -> tuple[list[dict[str, Any]], int]:
    """Прочитать активный JSONL и архивы .1..N, безопасно пропуская битые строки."""
    records, skipped = _read_files(collect_jsonl_files(Path(path).expanduser()))
    return filter_and_sort(records, days), skipped


def load_jsonl_sources(
    path: str, cli_path: str | None, no_cli: bool, days: float,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Прочитать usage.jsonl и companion cli-usage.jsonl (авто или явный), вернуть записи, skipped и список файлов."""
    active = Path(path).expanduser()
    files = list(collect_jsonl_files(active))
    if not no_cli:
        cli_active = Path(cli_path).expanduser() if cli_path else active.with_name(CLI_USAGE_NAME)
        if cli_active != active:
            files.extend(collect_jsonl_files(cli_active))
    records, skipped = _read_files(files)
    return filter_and_sort(records, days), skipped, [str(f) for f in files]


_PRE_PCT_COLS: tuple[str, ...] = ("requests", "prompt_tokens", "completion_tokens", "cached_tokens", "cache_creation_tokens")
_POST_PCT_COLS: tuple[str, ...] = ("reasoning_tokens", "total_tokens")


def _format_table_row(item: Mapping[str, Any], keys: tuple[str, ...]) -> tuple[str, ...]:
    """Преобразовать одну строку агрегата в кортеж строковых ячеек."""
    dims = tuple(str(item.get(k) or "") for k in keys)
    pre = tuple(str(int(item.get(k) or 0)) for k in _PRE_PCT_COLS)
    pct = (f"{float(item.get('cache_hit_pct') or 0.0):.2f}%",)
    post = tuple(str(int(item.get(k) or 0)) for k in _POST_PCT_COLS)
    return dims + pre + pct + post


def render_table(title: str, headers: tuple[str, ...], keys: tuple[str, ...], items: Sequence[Mapping[str, Any]]) -> str:
    """Отрисовать компактную текстовую таблицу по заголовкам и записям."""
    if not items:
        return f"{title}:\n  (empty)"
    hdrs = (*headers, "reqs", "prompt", "compl", "cached", "create", "cache%", "reason", "total")
    rows = [_format_table_row(r, keys) for r in items]
    widths = [max(len(hdrs[i]), *(len(row[i]) for row in rows)) for i in range(len(hdrs))]
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
    sep = "  " + "  ".join("-" * w for w in widths)
    return "\n".join([f"{title}:", fmt.format(*hdrs), sep, *(fmt.format(*row) for row in rows)])


def _format_head(report: Mapping[str, Any]) -> str:
    """Шапка отчёта: источники и строка Summary (cache_creation, usage_missing_reason)."""
    s = report["summary"]
    sources = report.get("sources")
    src = f"Source: {report['source']} (skipped_lines={report.get('skipped_lines', 0)})"
    if isinstance(sources, list) and sources:
        src += "\nFiles: " + ", ".join(str(x) for x in sources)
    uncached = s.get("uncached_prompt_tokens", ua.compute_uncached_prompt_tokens(s.get("prompt_tokens"), s.get("cached_tokens")))
    line = (
        f"Summary: requests={s.get('total_requests', 0)} ok={s.get('ok_requests', 0)} "
        f"err={s.get('error_requests', 0)} prompt={s.get('prompt_tokens', 0)} "
        f"completion={s.get('completion_tokens', 0)} cached={s.get('cached_tokens', 0)} "
        f"({float(s.get('cache_hit_pct') or 0.0):.2f}%) cache_creation={s.get('cache_creation_tokens', 0)} "
        f"uncached={uncached} reasoning={s.get('reasoning_tokens', 0)} total={s.get('total_tokens', 0)}"
    )
    reasons = s.get("usage_missing_reasons")
    if isinstance(reasons, Mapping) and reasons:
        line += "\nUsage missing: " + ", ".join(f"{k}={v}" for k, v in reasons.items())
    return f"{src}\n{line}"


def format_report(report: Mapping[str, Any]) -> str:
    """Отформатировать отчёт в человекочитаемом табличном виде."""
    anomalies = report["prompt_anomalies"]
    fmt = "  - [{scope}] {key}: prompt={prompt_tokens} baseline={baseline_tokens} ratio={ratio}x ({reason})"
    defs = {"scope": "?", "key": "", "prompt_tokens": 0, "baseline_tokens": 0, "ratio": 0, "reason": "anomaly"}
    alerts = "\n".join(["ALERTS:", *(fmt.format_map({**defs, **a}) for a in anomalies)]) if anomalies else "ALERTS: none"
    tables = [render_table(t, hdrs, keys, report.get(fld) or []) for t, fld, hdrs, keys in _TABLES]
    return "\n\n".join((_format_head(report), *tables, alerts))
