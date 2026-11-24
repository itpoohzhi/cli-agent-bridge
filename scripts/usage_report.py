"""CLI-отчёт по расходу токенов и детекции аномалий prompt_tokens."""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import math
import os
import sqlite3
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as url_err, parse as url_parse, request as url_req

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import core.usage_analytics as ua  # noqa: E402

DEFAULT_JSONL_PATH = "~/.dsh/telemetry/usage.jsonl"
_TABLES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("BY MODEL", "by_model", ("model", "backend"), ("model", "backend_id")),
    ("BY ROLE", "by_role", ("role", "subagent_id"), ("subagent_role", "subagent_id")),
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


def _record_epoch(record: Mapping[str, Any]) -> float | None:
    """Извлечь epoch-время записи из полей ts_epoch, ts или ts_iso."""
    return next((ep for k in ("ts_epoch", "ts", "ts_iso") if (ep := _parse_ts_value(record.get(k))) is not None), None)


def _filter_and_sort(records: list[dict[str, Any]], days: float) -> list[dict[str, Any]]:
    """Отфильтровать записи по окну days (0 — без фильтра) и отсортировать по ts."""
    if days > 0.0:
        cutoff = time.time() - days * 86400.0
        records = [r for r in records if (ep := _record_epoch(r)) is not None and ep >= cutoff]
    return sorted(
        records,
        key=lambda r: (_record_epoch(r) or 0.0, str(r.get("ts") or r.get("ts_iso") or ""), str(r.get("request_id") or "")),
    )


def _collect_jsonl_files(active: Path) -> tuple[Path, ...]:
    """Собрать ротированные архивы .N (от старых к новым) и активный JSONL-файл."""
    prefix = f"{active.name}."
    entries = active.parent.iterdir() if active.parent.is_dir() else ()
    archives = sorted(
        ((int(p.name[len(prefix):]), p) for p in entries
         if p.is_file() and p.name.startswith(prefix) and p.name[len(prefix):].isdigit()),
        key=lambda item: item[0], reverse=True,
    )
    return tuple(p for _, p in archives) + ((active,) if active.is_file() else ())


def _load_jsonl(path: str, days: float) -> tuple[list[dict[str, Any]], int]:
    """Прочитать активный JSONL и архивы .1..N, безопасно пропуская битые строки."""
    records: list[dict[str, Any]] = []
    skipped = 0
    for file_path in _collect_jsonl_files(Path(path).expanduser()):
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
    return _filter_and_sort(records, days), skipped


def _load_db(path: str, days: float) -> list[dict[str, Any]]:
    """Прочитать таблицу bridge_requests (read-only) из DuckDB или sqlite3."""
    if not (db_path := Path(path).expanduser()).is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")
    with db_path.open("rb") as handle:
        is_sqlite = handle.read(16) == b"SQLite format 3\x00"
    with contextlib.closing(
        sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
        if is_sqlite
        else getattr(importlib.import_module("duckdb"), "connect")(str(db_path), read_only=True)
    ) as conn:
        cur = conn.execute("SELECT * FROM bridge_requests ORDER BY ts_epoch ASC")
        cols = tuple(c[0] for c in (cur.description or ()))
        return _filter_and_sort([dict(zip(cols, r, strict=False)) for r in cur.fetchall()], days)


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    """Преобразовать последовательность отображений в список dict[str, Any]."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [{str(k): v for k, v in item.items()} for item in value if isinstance(item, Mapping)]


def _load_url(url: str, token_env: str | None, thresholds: ua.AnomalyThresholds) -> dict[str, Any]:
    """Загрузить данные телеметрии по HTTP(S) и преобразовать в структуру отчёта."""
    if url_parse.urlsplit(url).scheme not in ("http", "https"):
        raise ValueError("URL must use http or https scheme")
    token = os.environ.get(token_env, "") if token_env else ""
    headers = {"Accept": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})}
    with url_req.urlopen(url_req.Request(url, headers=headers, method="GET"), timeout=15.0) as resp:
        raw_payload: Any = json.loads(resp.read().decode("utf-8"))
    if not isinstance(raw_payload, Mapping):
        raise ValueError("Telemetry response must be a JSON object")
    payload: dict[str, Any] = {str(k): v for k, v in raw_payload.items()}
    if isinstance(payload.get("records"), list):
        return ua.aggregate_records(_as_dict_list(payload["records"]), thresholds)
    if not isinstance(raw_summary := payload.get("summary"), Mapping):
        raise ValueError("Unsupported telemetry payload structure")
    summary: dict[str, Any] = {str(k): v for k, v in raw_summary.items()}
    summary["cache_hit_pct"] = ua.compute_cache_hit_pct(
        int(summary.get("cached_tokens") or 0), int(summary.get("prompt_tokens") or 0)
    )
    summary["uncached_prompt_tokens"] = ua.compute_uncached_prompt_tokens(
        summary.get("prompt_tokens"), summary.get("cached_tokens")
    )
    groups: dict[str, list[dict[str, Any]]] = {
        k: ua.enrich_with_cache_hit(_as_dict_list(payload.get(k))) for k in ("by_model", "by_role", "by_day")
    }
    turns = _as_dict_list(payload.get("recent_requests") or payload.get("recent_turns"))
    anomalies = ua.detect_prompt_anomalies(groups["by_day"], turns, thresholds)
    if not anomalies and not turns and isinstance(payload.get("prompt_anomalies"), list):
        anomalies = _as_dict_list(payload["prompt_anomalies"])
    return {"summary": summary, **groups, "prompt_anomalies": anomalies}


def _render_table(title: str, headers: tuple[str, ...], keys: tuple[str, ...], items: Sequence[Mapping[str, Any]]) -> str:
    """Отрисовать компактную текстовую таблицу по заголовкам и записям."""
    if not items:
        return f"{title}:\n  (empty)"
    hdrs = (*headers, "reqs", "prompt", "compl", "cached", "cache%", "reason", "total")
    rows = [
        (
            *(str(r.get(k) or "") for k in keys),
            *(str(int(r.get(k) or 0)) for k in ("requests", "prompt_tokens", "completion_tokens", "cached_tokens")),
            f"{float(r.get('cache_hit_pct') or 0.0):.2f}%",
            *(str(int(r.get(k) or 0)) for k in ("reasoning_tokens", "total_tokens")),
        )
        for r in items
    ]
    widths = [max(len(hdrs[i]), *(len(row[i]) for row in rows)) for i in range(len(hdrs))]
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
    sep = "  " + "  ".join("-" * w for w in widths)
    return "\n".join([f"{title}:", fmt.format(*hdrs), sep, *(fmt.format(*row) for row in rows)])


def _format_report(report: Mapping[str, Any]) -> str:
    """Отформатировать отчёт в человекочитаемом табличном виде."""
    s = report["summary"]
    head = (
        f"Source: {report['source']} (skipped_lines={report.get('skipped_lines', 0)})\n"
        f"Summary: requests={s.get('total_requests', 0)} ok={s.get('ok_requests', 0)} "
        f"err={s.get('error_requests', 0)} prompt={s.get('prompt_tokens', 0)} "
        f"completion={s.get('completion_tokens', 0)} cached={s.get('cached_tokens', 0)} "
        f"({float(s.get('cache_hit_pct') or 0.0):.2f}%) "
        f"uncached={s.get('uncached_prompt_tokens', ua.compute_uncached_prompt_tokens(s.get('prompt_tokens'), s.get('cached_tokens')))} "
        f"reasoning={s.get('reasoning_tokens', 0)} total={s.get('total_tokens', 0)}"
    )
    anomalies = report["prompt_anomalies"]
    fmt = "  - [{scope}] {key}: prompt={prompt_tokens} baseline={baseline_tokens} ratio={ratio}x ({reason})"
    defs = {"scope": "?", "key": "", "prompt_tokens": 0, "baseline_tokens": 0, "ratio": 0, "reason": "anomaly"}
    alerts = "\n".join(["ALERTS:", *(fmt.format_map({**defs, **a}) for a in anomalies)]) if anomalies else "ALERTS: none"
    tables = [_render_table(t, hdrs, keys, report[fld]) for t, fld, hdrs, keys in _TABLES]
    return "\n\n".join((head, *tables, alerts))


def _build_parser() -> argparse.ArgumentParser:
    """Создать парсер аргументов CLI."""
    p = argparse.ArgumentParser(description="Сводка usage-телеметрии и алерты всплесков prompt_tokens.")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--jsonl", type=str, default=None, help=f"Путь к JSONL-файлу (по умолчанию {DEFAULT_JSONL_PATH})")
    src.add_argument("--db", type=str, default=None, help="Путь к DuckDB или SQLite БД с таблицей bridge_requests")
    src.add_argument("--url", type=str, default=None, help="URL эндпоинта /v1/telemetry")
    p.add_argument("--token-env", type=str, default=None, help="Имя env-переменной с Bearer-токеном для --url")
    p.add_argument("--days", type=float, default=7.0, help="Окно фильтрации в днях для jsonl/db (0 — без фильтра)")
    p.add_argument("--spike-ratio", type=float, default=2.0, help="Порог кратности всплеска prompt_tokens")
    p.add_argument("--min-turn-tokens", type=int, default=100000, help="Порог prompt_tokens на ход для алерта")
    p.add_argument("--min-day-tokens", type=int, default=5000000, help="Порог prompt_tokens за день для алерта")
    p.add_argument("--json", action="store_true", help="Вывести строгий JSON в stdout")
    p.add_argument("--fail-on-anomaly", action="store_true", help="Выйти с кодом 2 при наличии аномалий")
    return p


def _run_report(args: argparse.Namespace) -> dict[str, Any]:
    """Загрузить данные из выбранного источника и сформировать отчёт."""
    th = ua.AnomalyThresholds(
        ratio_threshold=args.spike_ratio, min_turn_prompt_tokens=args.min_turn_tokens, min_day_prompt_tokens=args.min_day_tokens,
    )
    if args.url:
        return {"source": args.url, "skipped_lines": 0, **_load_url(args.url, args.token_env, th)}
    if args.db:
        return {"source": args.db, "skipped_lines": 0, **ua.aggregate_records(_load_db(args.db, args.days), th)}
    records, skipped = _load_jsonl(path := args.jsonl or DEFAULT_JSONL_PATH, args.days)
    return {"source": path, "skipped_lines": skipped, **ua.aggregate_records(records, th)}


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа CLI-скрипта usage_report."""
    args = _build_parser().parse_args(argv)
    try:
        report = _run_report(args)
    except (OSError, ValueError, RuntimeError, url_err.URLError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else _format_report(report))
    return 2 if args.fail_on_anomaly and report["prompt_anomalies"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
