"""Эмиттер usage прямого терминального CLI-раннера в `cli-usage.jsonl` (fail-open, exit 0 всегда)."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.cli_usage_sink import CliUsageSink, parse_cli_usage_payload  # noqa: E402

_DIRECT = "cli-direct"


def build_parser() -> argparse.ArgumentParser:
    """Аргументы CLI-эмиттера."""
    p = argparse.ArgumentParser(description="Записать usage CLI-вызова в cli-usage.jsonl")
    p.add_argument("--input", default="-", help="файл JSON/NDJSON или `-` (stdin)")
    p.add_argument("--model")
    p.add_argument("--backend-id", default=_DIRECT)
    p.add_argument("--route", default=_DIRECT)
    p.add_argument("--transport-kind", default=_DIRECT)
    p.add_argument("--request-id")
    p.add_argument("--subagent-role")
    p.add_argument("--elapsed-ms", type=float)
    p.add_argument("--http-status", type=int)
    p.add_argument("--path", help="переопределить путь cli-usage.jsonl")
    p.add_argument("--verbose", action="store_true", help="напечатать JSON-статус в stdout")
    return p


def _read_input(source: str) -> str:
    """Прочитать stdin (`-`) или файл."""
    if source == "-":
        return sys.stdin.read()
    return Path(source).expanduser().read_text(encoding="utf-8", errors="replace")


def build_record(ns: argparse.Namespace, usage: dict[str, Any] | None) -> dict[str, Any]:
    """Слить usage из payload с метаданными CLI (явные аргументы приоритетнее payload)."""
    record: dict[str, Any] = dict(usage or {"usage_present": False, "usage_missing_reason": "no_usage_in_payload"})
    meta: dict[str, Any] = {
        "model": ns.model, "backend_id": ns.backend_id, "route": ns.route,
        "transport_kind": ns.transport_kind, "subagent_role": ns.subagent_role,
        "elapsed_ms": ns.elapsed_ms, "http_status": ns.http_status,
        "request_id": ns.request_id or record.get("request_id") or uuid.uuid4().hex,
    }
    record.update({k: v for k, v in meta.items() if v is not None})
    return record


def run(argv: Sequence[str] | None = None) -> dict[str, Any]:
    """Выполнить эмиссию; возвращает статус `{written, usage_present}` (ошибки не бросает)."""
    ns = build_parser().parse_args(argv)
    try:
        usage = parse_cli_usage_payload(_read_input(ns.input))
    except (OSError, ValueError):
        usage = None
    written = CliUsageSink(ns.path).write(build_record(ns, usage))
    return {"written": written, "usage_present": usage is not None}


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа: всегда exit 0; статус печатается только с `--verbose`."""
    wanted = list(sys.argv[1:] if argv is None else argv)
    try:
        status = run(wanted)
    except SystemExit:
        raise
    except Exception as exc:  # fail-open: эмиттер не должен ломать CLI-раннер
        status = {"written": False, "error": type(exc).__name__}
    if "--verbose" in wanted:
        sys.stdout.write(json.dumps(status) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
