#!/usr/bin/env python3
"""Живая матрица модель × уровень против запущенного моста (НЕ входит в pytest-сбор).

Для каждой активной модели и каждого уровня шлёт `Reply with exact word OK` с
`reasoning_effort=<уровень>` и проверяет:

* `/v1/models` = каталог из state/zen-catalog.json (или встроенный снимок);
* HTTP 200 и слово OK в ответе;
* в logs/bridge.log команда `-m opencode/<id>[#<variant>] --standalone [--thinking]`
  ровно по эталону (без `#` для моделей без variants и для off/none), ни одной
  строки `Variant unavailable`.

Запуск (Python 3.9, stdlib):
    /usr/bin/python3 -I tests/live_matrix.py --base http://127.0.0.1:9883 \
        --levels off,minimal,low,medium,high,xhigh,max [--aliases] [--models a,b]
Ключ — из OPENCODE_ZEN_BRIDGE_KEY или ~/.dsh/.env. Код возврата 0 — всё сошлось.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import zen_catalog as zc

BRIDGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LEVELS = "off,minimal,low,medium,high,xhigh,max"
OWNER_ALIASES = ("minimax-m3.1-flash-free", "longcat-2.5-preview-free",
                 "muse-spark-1.3-contributor-free", "qwen3.6-plus-free")
# Отказы самого Zen (квоты free-уровня, регион), а не моста: показываются отдельно.
UPSTREAM_MARKERS = ("Free usage limit reached", "not available in your country", "Endpoint is unavailable")
EXEC_RE = re.compile(r"\bexec model=\S+ -m (\S+)((?: --\w+)*)")


def read_key() -> str:
    key = os.environ.get("OPENCODE_ZEN_BRIDGE_KEY", "").strip()
    if key:
        return key
    env_file = os.path.expanduser("~/.dsh/.env")
    try:
        with open(env_file, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("OPENCODE_ZEN_BRIDGE_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    raise SystemExit("OPENCODE_ZEN_BRIDGE_KEY is not set (env or ~/.dsh/.env)")


def http_json(url: str, key: str, body: Optional[Dict[str, Any]], timeout: float) -> Tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET", headers={
        "Authorization": "Bearer %s" % key, "Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        finally:
            exc.close()
    except (OSError, ValueError) as exc:
        return 0, {"error": str(exc)}


def expected_variant(entry: Dict[str, Any], level: str) -> str:
    bridge = entry["bridge"]
    if not bridge.get("supports_variant") or level in ("off", "none"):
        return ""
    return str(bridge["variant_map"][level])


def run_one(base: str, key: str, model: str, level: str, timeout: float) -> Tuple[str, str, int, str]:
    status, payload = http_json("%s/v1/chat/completions" % base, key, {
        "model": model, "reasoning_effort": level, "stream": False,
        "messages": [{"role": "user", "content": "Reply with exact word OK"}]}, timeout)
    text = ""
    if status == 200:
        try:
            text = str(payload["choices"][0]["message"].get("content") or "")
        except (KeyError, IndexError, TypeError, AttributeError):
            text = ""
    elif isinstance(payload, dict):
        error = payload.get("error")
        text = str(error.get("message") if isinstance(error, dict) else error or "")
    return model, level, status, text


def is_upstream_failure(code: int, text: str) -> bool:
    return code != 200 and any(marker in text for marker in UPSTREAM_MARKERS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="http://127.0.0.1:9883")
    parser.add_argument("--levels", default=DEFAULT_LEVELS)
    parser.add_argument("--models", default="", help="список id через запятую (по умолчанию — вся активная выдача)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--log", default=os.path.join(BRIDGE_DIR, "logs", "bridge.log"))
    parser.add_argument("--aliases", action="store_true", help="дополнительно прогнать устаревшие id владельца")
    parser.add_argument("--allow-upstream-limits", action="store_true",
                        help="не считать провалом отказы Zen (квота free, регион); команды в логе проверяются всё равно")
    args = parser.parse_args()

    key = read_key()
    base = args.base.rstrip("/")
    levels = [x.strip() for x in args.levels.split(",") if x.strip()]
    state = zc.load_state_file(os.path.join(BRIDGE_DIR, "state", "zen-catalog.json")) or zc.fallback_state()
    entries = {e["id"]: e for e in state["models"]}
    failures: List[str] = []

    status, payload = http_json("%s/v1/models" % base, key, None, 30)
    listed = sorted(item["id"] for item in payload.get("data", [])) if status == 200 else []
    if status != 200 or listed != sorted(entries):
        failures.append("/v1/models %s != catalog %s (http %s)" % (listed, sorted(entries), status))
    print("catalog: %d models: %s" % (len(listed), ", ".join(listed)))

    models = [m.strip() for m in args.models.split(",") if m.strip()] or sorted(entries)
    unknown = [m for m in models if m not in entries]
    if unknown:
        raise SystemExit("unknown models: %s" % unknown)

    log_offset = os.path.getsize(args.log) if os.path.exists(args.log) else 0
    jobs = [(m, lvl) for m in models for lvl in levels]
    started = time.time()
    results: List[Tuple[str, str, int, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(run_one, base, key, m, lvl, args.timeout) for m, lvl in jobs]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    expected: "collections.Counter[Tuple[str, bool]]" = collections.Counter()
    for model, level, code, text in sorted(results):
        variant = expected_variant(entries[model], level)
        ok = code == 200 and re.search(r"\bOK\b", text, re.IGNORECASE) is not None
        upstream = is_upstream_failure(code, text)
        print("%-30s %-8s -> %-30s http=%s %s" % (
            model, level, "#" + variant if variant else "(no variant)", code,
            "OK" if ok else ("UPSTREAM %r" if upstream else "FAIL %r") % text[:70]))
        if not ok and not (upstream and args.allow_upstream_limits):
            failures.append("%s/%s: http=%s text=%r" % (model, level, code, text[:80]))
        spec = "opencode/%s%s" % (model, "#" + variant if variant else "")
        expected[(spec, bool(variant))] += 1

    if args.aliases:
        for old in OWNER_ALIASES:
            _model, _lvl, code, text = run_one(base, key, old, "high", args.timeout)
            ok = code == 200 and re.search(r"\bOK\b", text, re.IGNORECASE) is not None
            upstream = is_upstream_failure(code, text)
            print("alias %-34s http=%s %s" % (
                old, code, "OK" if ok else ("UPSTREAM %r" if upstream else "FAIL %r") % text[:70]))
            if not ok and not (upstream and args.allow_upstream_limits):
                failures.append("alias %s: http=%s" % (old, code))

    time.sleep(1.0)
    observed: "collections.Counter[Tuple[str, bool]]" = collections.Counter()
    bad_lines = 0
    try:
        with open(args.log, "rb") as handle:
            handle.seek(log_offset)
            chunk = handle.read().decode("utf-8", errors="replace")
    except OSError as exc:
        chunk = ""
        failures.append("cannot read log %s: %s" % (args.log, exc))
    for line in chunk.splitlines():
        if "Variant unavailable" in line:
            bad_lines += 1
        match = EXEC_RE.search(line)
        if match and "stream exec" not in line:
            flags = match.group(2)
            if "--standalone" not in flags:
                failures.append("log command without --standalone: %s" % line.strip()[:160])
            observed[(match.group(1), "--thinking" in flags)] += 1
    if bad_lines:
        failures.append("'Variant unavailable' in log: %d lines" % bad_lines)
    for key_, count in sorted(expected.items()):
        if observed[key_] < count:
            failures.append("log lacks command %s thinking=%s: expected >= %d, got %d" % (
                key_[0], key_[1], count, observed[key_]))

    print("matrix: %d calls in %.0fs; log commands checked: %d" % (len(jobs), time.time() - started, sum(expected.values())))
    if failures:
        print("FAILED (%d):" % len(failures))
        for item in failures:
            print("  - %s" % item)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
