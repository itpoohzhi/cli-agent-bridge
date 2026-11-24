"""Тесты CLI-отчёта scripts/usage_report.py и AST-гарды инвариантов M-MOD."""

from __future__ import annotations

import ast
import json
import sqlite3
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from core import request_telemetry as _rt_mod
from core.telemetry_sql import COLUMNS, SCHEMA, make_row
from scripts import usage_report

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "usage_report.py"
NEW_MODULES: tuple[str, ...] = (
    "core/usage_fields.py",
    "core/usage_log.py",
    "core/usage_analytics.py",
    "scripts/usage_report.py",
)
PURE_MODULES: tuple[str, ...] = ("core/usage_fields.py", "core/usage_analytics.py")
FORBIDDEN_IO_IMPORTS: frozenset[str] = frozenset(
    {"pathlib", "urllib", "http", "socket", "subprocess", "duckdb", "sqlite3", "io", "os"}
)


def _write_jsonl(path: Path, lines: list[str]) -> None:
    """Записать строки в JSONL-файл."""
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mccabe_complexity(node: ast.AST) -> int:
    """Вычислить цикломатическую сложность McCabe для функции без вложенных def."""
    score = 1
    stack = list(ast.iter_child_nodes(node))
    while stack:
        cur = stack.pop()
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(cur, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp)):
            score += 1
        elif isinstance(cur, ast.comprehension):
            score += len(cur.ifs)
        elif hasattr(ast, "Match") and isinstance(cur, ast.Match):
            score += len(cur.cases)
        stack.extend(ast.iter_child_nodes(cur))
    return score


def _func_param_count(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Посчитать параметры функции без учёта self/cls."""
    pos = [a.arg for a in (*fn.args.posonlyargs, *fn.args.args)]
    if pos and pos[0] in ("self", "cls"):
        pos = pos[1:]
    return len(pos) + len(fn.args.kwonlyargs) + int(fn.args.vararg is not None) + int(fn.args.kwarg is not None)


def _has_mutable_collection(expr: ast.AST | None) -> bool:
    """Проверить, содержит ли AST-выражение литерал или конструктор dict/list/set."""
    if expr is None:
        return False
    for node in ast.walk(expr):
        if isinstance(node, (ast.Dict, ast.List, ast.Set, ast.DictComp, ast.ListComp, ast.SetComp)):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("dict", "list", "set"):
            return True
    return False


def _self_assigned_attrs(tree: ast.AST) -> dict[str, set[str]]:
    """Собрать приватные self-атрибуты, присваиваемые внутри каждого класса."""
    by_class: dict[str, set[str]] = {}
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        attrs: set[str] = set()
        for sub in ast.walk(cls):
            targets = sub.targets if isinstance(sub, ast.Assign) else ([sub.target] if isinstance(sub, ast.AnnAssign) else [])
            for tgt in targets:
                if isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) and tgt.value.id == "self":
                    attrs.add(tgt.attr)
        by_class[cls.name] = attrs
    return by_class


def test_cli_help_exits_zero() -> None:
    """Флаг --help завершается с кодом 0 без сети и секретов."""
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), "--help"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    for flag in ("--jsonl", "--db", "--url", "--fail-on-anomaly"):
        assert flag in proc.stdout


def test_jsonl_and_rotated_archive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Чтение active + .1 архива с битой строкой даёт точные агрегаты и таблицы."""
    active = tmp_path / "usage.jsonl"
    archive = tmp_path / "usage.jsonl.1"
    _write_jsonl(archive, [
        json.dumps({"ts": "2026-11-20T10:00:00Z", "request_id": "r1", "model": "m-a", "backend_id": "b1",
                    "subagent_role": "coder", "subagent_id": "coder-1", "http_status": 200,
                    "prompt_tokens": 1000, "completion_tokens": 200, "cached_tokens": 500, "reasoning_tokens": 50, "total_tokens": 1200, "usage_present": True}),
        "{broken json line",
    ])
    _write_jsonl(active, [
        json.dumps({"ts": "2026-11-21T11:00:00Z", "request_id": "r2", "model": "m-b", "backend_id": "b2",
                    "subagent_role": "", "subagent_id": "", "http_status": 500,
                    "prompt_tokens": 2000, "completion_tokens": 300, "cached_tokens": 1000, "reasoning_tokens": 100, "total_tokens": 2300, "usage_present": True}),
    ])
    assert usage_report.main(["--jsonl", str(active), "--days", "0", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["skipped_lines"] == 1
    assert data["summary"]["total_requests"] == 2
    assert data["summary"]["ok_requests"] == 1
    assert data["summary"]["error_requests"] == 1
    assert data["summary"]["reasoning_tokens"] == 150
    assert data["summary"]["cache_hit_pct"] == 50.0
    assert {r["subagent_role"] for r in data["by_role"]} == {"coder", "interactive"}
    assert usage_report.main(["--jsonl", str(active), "--days", "0"]) == 0
    table_out = capsys.readouterr().out
    assert "BY MODEL" in table_out and "BY ROLE" in table_out and "BY DAY" in table_out
    assert "50.00%" in table_out and "ALERTS: none" in table_out


def test_db_sqlite_fixture(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Чтение bridge_requests из sqlite3-фикстуры совместимой с RequestTelemetryStore."""
    assert hasattr(_rt_mod, "RequestTelemetryStore")
    db_path = tmp_path / "telemetry.sqlite"
    placeholders = ", ".join("?" for _ in COLUMNS)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f"CREATE TABLE bridge_requests ({SCHEMA})")
        rows = [
            make_row({"request_id": "db-1", "ts_epoch": 1700000000.0, "model": "m-db", "backend_id": "b1",
                      "subagent_id": "coder-1", "subagent_role": "coder", "status_code": 200,
                      "prompt_tokens": 400, "completion_tokens": 100, "cached_tokens": 200, "reasoning_tokens": 20, "total_tokens": 500, "usage_present": True}),
            make_row({"request_id": "db-2", "ts_epoch": 1700000060.0, "model": "m-db", "backend_id": "b1",
                      "status_code": 200, "prompt_tokens": 600, "completion_tokens": 150, "cached_tokens": 300, "reasoning_tokens": 30, "total_tokens": 750, "usage_present": True}),
        ]
        conn.executemany(f"INSERT INTO bridge_requests VALUES ({placeholders})", rows)
        conn.commit()
    finally:
        conn.close()
    assert usage_report.main(["--db", str(db_path), "--days", "0", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["total_requests"] == 2
    assert data["summary"]["prompt_tokens"] == 1000
    assert data["summary"]["reasoning_tokens"] == 50
    assert data["summary"]["cache_hit_pct"] == 50.0


def test_url_source_with_mock_http_server(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Чтение --url с Bearer-токеном из --token-env без утечки секрета в вывод."""
    received_auth: list[str] = []
    payload: dict[str, Any] = {
        "summary": {"total_requests": 1, "ok_requests": 1, "error_requests": 0, "prompt_tokens": 1000,
                    "completion_tokens": 200, "cached_tokens": 400, "reasoning_tokens": 40, "total_tokens": 1200},
        "by_model": [{"model": "m-url", "backend_id": "b1", "requests": 1, "prompt_tokens": 1000,
                      "completion_tokens": 200, "cached_tokens": 400, "reasoning_tokens": 40, "total_tokens": 1200}],
        "by_role": [{"subagent_role": "interactive", "subagent_id": "", "requests": 1, "prompt_tokens": 1000,
                     "completion_tokens": 200, "cached_tokens": 400, "reasoning_tokens": 40, "total_tokens": 1200}],
        "by_day": [{"day": "2026-11-23", "requests": 1, "prompt_tokens": 1000, "completion_tokens": 200,
                    "cached_tokens": 400, "reasoning_tokens": 40, "total_tokens": 1200}],
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            received_auth.append(self.headers.get("Authorization", ""))
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("BRIDGE_TEST_TOKEN", "secret-token-xyz")
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1/telemetry?window_hours=24"
        rc = usage_report.main(["--url", url, "--token-env", "BRIDGE_TEST_TOKEN", "--json"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
    captured = capsys.readouterr()
    assert rc == 0
    assert received_auth == ["Bearer secret-token-xyz"]
    assert "secret-token-xyz" not in captured.out and "secret-token-xyz" not in captured.err
    assert json.loads(captured.out)["summary"]["cache_hit_pct"] == 40.0


def test_prompt_anomaly_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """При всплеске prompt_tokens без --fail-on-anomaly exit 0, а с флагом — exit 2."""
    log = tmp_path / "usage.jsonl"
    recs = [
        json.dumps({"ts": f"2026-11-22T10:0{i}:00Z", "request_id": f"n{i}", "model": "m1",
                    "http_status": 200, "prompt_tokens": 10000, "total_tokens": 10500, "usage_present": True})
        for i in range(4)
    ]
    recs.append(json.dumps({
        "ts": "2026-11-22T10:10:00Z", "request_id": "spike", "model": "m1", "subagent_role": "coder",
        "http_status": 200, "prompt_tokens": 250000, "total_tokens": 251000, "usage_present": True,
    }))
    _write_jsonl(log, recs)
    assert usage_report.main(["--jsonl", str(log), "--days", "0"]) == 0
    out = capsys.readouterr().out
    assert "ALERTS:" in out and "turn_prompt_spike" in out
    assert usage_report.main(["--jsonl", str(log), "--days", "0", "--fail-on-anomaly"]) == 2
    assert "turn_prompt_spike" in capsys.readouterr().out


def test_ast_and_architecture_guards() -> None:
    """AST-гард по VER-004: лимиты LOC/McCabe, чистота pure-модулей и владельцы состояния."""
    assert len(Path(__file__).read_text(encoding="utf-8").splitlines()) <= 295
    for rel in NEW_MODULES:
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert len(src.splitlines()) <= 240, f"{rel} > 240 LOC"
        tree = ast.parse(src, filename=rel)
        for stmt in tree.body:
            if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                assert not _has_mutable_collection(stmt.value), f"{rel} has module-level mutable collection"
        for fn in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            assert (fn.end_lineno or fn.lineno) - fn.lineno + 1 <= 50, f"{rel}:{fn.name} > 50 LOC"
            assert _func_param_count(fn) <= 5, f"{rel}:{fn.name} > 5 params"
            assert _mccabe_complexity(fn) <= 10, f"{rel}:{fn.name} McCabe > 10"
        if rel != "core/usage_log.py":
            for cls_attrs in _self_assigned_attrs(tree).values():
                assert not (cls_attrs & {"_queue", "_stats", "_usage_log", "_lock", "_cfg"})
    for rel in PURE_MODULES:
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        tree = ast.parse(src, filename=rel)
        assert "os.environ" not in src
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not ({a.name.split(".")[0] for a in node.names} & FORBIDDEN_IO_IMPORTS), rel
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN_IO_IMPORTS, rel
            elif isinstance(node, ast.Attribute):
                assert node.attr not in ("environ", "getenv"), rel
            elif isinstance(node, ast.Name):
                assert node.id != "getenv", rel
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "open", rel
    store_attrs: dict[str, set[str]] = {}
    for rel in ("core/request_telemetry.py", "core/telemetry_query.py"):
        for cls_name, attrs in _self_assigned_attrs(ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))).items():
            store_attrs.setdefault(cls_name, set()).update(attrs)
    owner_attrs = store_attrs.get("RequestTelemetryStore", set()) | store_attrs.get("TelemetryReader", set())
    assert {"_queue", "_stats", "_usage_log"} <= owner_attrs
    for cls_name, attrs in store_attrs.items():
        if cls_name not in ("RequestTelemetryStore", "TelemetryReader"):
            assert not (attrs & {"_queue", "_stats", "_usage_log"})
    writer_attrs = _self_assigned_attrs(ast.parse((REPO_ROOT / "core/usage_log.py").read_text(encoding="utf-8")))
    assert {"_stats", "_lock", "_cfg"} <= writer_attrs.get("RotatingUsageLogWriter", set())
    for cls_name, attrs in writer_attrs.items():
        if cls_name != "RotatingUsageLogWriter":
            assert not (attrs & {"_stats", "_lock", "_cfg"})
