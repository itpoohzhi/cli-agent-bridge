"""CLI-отчёт по расходу токенов и детекции аномалий prompt_tokens."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib import error as url_err, parse as url_parse, request as url_req

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import core.usage_analytics as ua  # noqa: E402
from core.usage_report_db import load_db_records as _load_db  # noqa: E402
from core.usage_report_render import (  # noqa: E402
    collect_jsonl_files as _collect_jsonl_files,
    filter_and_sort as _filter_and_sort,
    format_report as _format_report,
    load_jsonl as _load_jsonl,
    load_jsonl_sources,
    record_epoch as _record_epoch,
    render_table as _render_table,
)

__all__ = ("main", "_format_report", "_load_jsonl", "_filter_and_sort", "_record_epoch", "_collect_jsonl_files", "_render_table")

DEFAULT_JSONL_PATH = "~/.dsh/telemetry/usage.jsonl"


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    """Преобразовать последовательность отображений в список dict[str, Any]."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [{str(k): v for k, v in item.items()} for item in value if isinstance(item, Mapping)]


def _fetch_url_json(url: str, token_env: str | None) -> dict[str, Any]:
    """Выполнить HTTP(S) GET и вернуть корневой JSON-объект."""
    if url_parse.urlsplit(url).scheme not in ("http", "https"):
        raise ValueError("URL must use http or https scheme")
    token = os.environ.get(token_env, "") if token_env else ""
    headers = {"Accept": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})}
    with url_req.urlopen(url_req.Request(url, headers=headers, method="GET"), timeout=15.0) as resp:
        raw_payload: Any = json.loads(resp.read().decode("utf-8"))
    if not isinstance(raw_payload, Mapping):
        raise ValueError("Telemetry response must be a JSON object")
    return {str(k): v for k, v in raw_payload.items()}


def _enrich_url_group(raw_items: Any) -> list[dict[str, Any]]:
    """Обогатить группу /v1/telemetry полями cache_hit_pct и cache_creation_tokens."""
    enriched = ua.enrich_with_cache_hit(_as_dict_list(raw_items))
    return [{**r, "cache_creation_tokens": ua.int_or_zero(r.get("cache_creation_tokens"))} for r in enriched]


def _normalize_url_summary(raw_summary: Mapping[str, Any]) -> dict[str, Any]:
    """Нормализовать summary из /v1/telemetry с расчётом cache_hit_pct и cache_creation_tokens."""
    summary: dict[str, Any] = {str(k): v for k, v in raw_summary.items()}
    summary["cache_creation_tokens"] = ua.int_or_zero(summary.get("cache_creation_tokens"))
    summary["cache_hit_pct"] = ua.compute_cache_hit_pct(
        int(summary.get("cached_tokens") or 0), int(summary.get("prompt_tokens") or 0)
    )
    summary["uncached_prompt_tokens"] = ua.compute_uncached_prompt_tokens(
        summary.get("prompt_tokens"), summary.get("cached_tokens")
    )
    return summary


def _load_url(url: str, token_env: str | None, thresholds: ua.AnomalyThresholds) -> dict[str, Any]:
    """Загрузить данные телеметрии по HTTP(S) и преобразовать в структуру отчёта."""
    payload = _fetch_url_json(url, token_env)
    if isinstance(payload.get("records"), list):
        return ua.aggregate_records(_as_dict_list(payload["records"]), thresholds)
    if not isinstance(raw_summary := payload.get("summary"), Mapping):
        raise ValueError("Unsupported telemetry payload structure")
    groups = {k: _enrich_url_group(payload.get(k)) for k in ("by_model", "by_role", "by_route", "by_day")}
    turns = _as_dict_list(payload.get("recent_requests") or payload.get("recent_turns"))
    anomalies = ua.detect_prompt_anomalies(groups["by_day"], turns, thresholds)
    if not anomalies and not turns and isinstance(payload.get("prompt_anomalies"), list):
        anomalies = _as_dict_list(payload["prompt_anomalies"])
    return {"summary": _normalize_url_summary(raw_summary), **groups, "prompt_anomalies": anomalies}


def _build_parser() -> argparse.ArgumentParser:
    """Создать парсер аргументов CLI."""
    p = argparse.ArgumentParser(description="Сводка usage-телеметрии и алерты всплесков prompt_tokens.")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--jsonl", "--path", dest="jsonl", type=str, default=None, help=f"Путь к JSONL-файлу (по умолчанию {DEFAULT_JSONL_PATH})")
    src.add_argument("--db", type=str, default=None, help="Путь к DuckDB или SQLite БД с таблицей bridge_requests")
    src.add_argument("--url", type=str, default=None, help="URL эндпоинта /v1/telemetry")
    p.add_argument("--cli-path", type=str, default=None, help="Явный путь к companion cli-usage.jsonl (read-only)")
    p.add_argument("--no-cli", action="store_true", help="Не подхватывать companion cli-usage.jsonl рядом с usage.jsonl")
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
    path = args.jsonl or DEFAULT_JSONL_PATH
    records, skipped, sources = load_jsonl_sources(path, args.cli_path, args.no_cli, args.days)
    return {"source": path, "sources": sources, "skipped_lines": skipped, **ua.aggregate_records(records, th)}


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа CLI-скрипта usage_report."""
    args = _build_parser().parse_args(argv)
    try:
        report = _run_report(args)
    except (OSError, ValueError, RuntimeError, url_err.URLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else _format_report(report))
    return 2 if args.fail_on_anomaly and report["prompt_anomalies"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
