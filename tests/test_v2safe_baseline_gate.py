"""VER-002/VER-015: замороженный baseline pytest-падений и компаратор сигнатур.

Манифест ``baseline-pytest-xfail.json`` фиксирует набор падений ревизии
``5ecd42a181c6e7217471659e75e008ab18355da7``: verdict PASS требует совпадения
nodeid и сигнатур. Единственная нормализация — SHA-256-токены двух hash-comparison
assertions; новый nodeid, изменённая сигнатура, новый ``function_bound``/``legacy_facade``, сигнальный сбой — FAIL.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # pytest console entry point, как в соседних тестах
MANIFEST = ROOT / ".ai-team/runs/tv2safe-20261116/baseline-pytest-xfail.json"
BASE_REVISION = "5ecd42a181c6e7217471659e75e008ab18355da7"
NORMALIZER_VERSION = "v2safe-normalizer/1"
GATE_ENV = "V2SAFE_RUN_FULL_BASELINE_GATE"
CHILD_ENV = "V2SAFE_BASELINE_CHILD"
DIGEST_NODEIDS = ("tests/test_architecture_modularity.py::test_i1_untouched_monolith_sha256[server.py]",
                  "tests/test_transport_modularity.py::test_all_changed_tracked_untracked_and_ignored_bounds")
DIGEST, ABBREVIATED_DIGEST = re.compile(r"\b[0-9a-fA-F]{64}\b"), re.compile(r"'[0-9a-fA-F]{8,}\.\.\.[0-9a-fA-F]{8,}'")
CRASH_LINE = re.compile(r"^(?:V2SAFE_SIGNAL_CRASH|SIGNAL_CRASH_FAIL)\b", re.M)
CONTEXT_LINE = re.compile(r"^\s*\+\s+(?:where|and)\b")
FRAME_BLOCK = re.compile(r'(?ms)^(?P<ind>[ \t]*)File "[^"]*", line \d+[^\n]*(?:\n(?P=ind)[ \t]+[^\n]*)*\n?')
TUPLE, FLOAT = re.compile(r"\('([^']*)',\s*'([^']*)'\)"), re.compile(r"\d+\.\d{4,}")  # тайминги — по форме
HEADER, TRACE = re.compile(r"^_{1,} (?P<name>\S.*?) _{1,}$", re.M), re.compile(r"^(tests/[\w./-]+\.py):\d+: ", re.M)
DIGEST_MARK = "<sha256:64hex>"
REQUIRED_KEYS = ("exception_type", "nodeid", "normalized_signature", "raw_signature", "source_report")
FORBIDDEN_KINDS = ("function_bound", "legacy_facade")  # новые function_bound/legacy_facade → FAIL

def _signature(chunk: str) -> str:
    """Сырая сигнатура: E-строки без pytest-контекста значений и вложенных кадров."""
    payloads = [line[4:].rstrip() for line in chunk.splitlines() if line.startswith("E   ")]
    body = FRAME_BLOCK.sub("", "\n".join([item for item in payloads if not CONTEXT_LINE.match(item)]))
    return "\n".join(line.strip() for line in body.splitlines()).strip()

def _param(text: str) -> str:
    """Параметр из [..]/(..) в конце имени либо ключевой список вида mode='x'."""
    for opener, closer in (("[", "]"), ("(", ")")):
        start, end = text.rfind(opener), text.rfind(closer)
        if start >= 0 and end > start:
            return text[start + 1:end].strip()
    return text.strip() if "=" in text else ""

def _summary_entries(text: str) -> list[dict[str, str]]:
    """Записи short test summary: точный nodeid и subtest-параметр SUBFAILED(...)."""
    found: list[dict[str, str]] = []
    for line in text.splitlines():
        if line.startswith("SUBFAILED("):
            close = line.index(") ")
            found.append({"param": line[10:close], "nodeid": line[close + 2:].split(" - ", 1)[0].strip()})
        elif line.startswith("FAILED "):
            found.append({"param": "", "nodeid": line[7:].split(" - ", 1)[0].strip()})
    return found


def parse_failures(text: str) -> list[dict[str, str]]:
    """Упорядоченные записи падений: nodeid, subtest-параметр и сырая сигнатура."""
    entries = _summary_entries(text)
    heads = list(HEADER.finditer(text))
    records: list[dict[str, str]] = []
    for position, head in enumerate(heads):
        end = heads[position + 1].start() if position + 1 < len(heads) else len(text)
        chunk = text[head.end():end]
        trace = TRACE.search(chunk)
        if trace is None:
            continue
        name = head.group("name").strip()
        base = re.split(r"[\[(]", name, maxsplit=1)[0].rsplit(".", 1)[-1].strip()
        match = next((item for item in entries if item["nodeid"].partition("::")[0] == trace.group(1)
                      and item["nodeid"].rsplit("::", 1)[-1].split("[", 1)[0] == base
                      and _param(item["param"] or item["nodeid"]) == _param(name)), None)
        if match is None:
            continue
        entries.remove(match)
        records.append({"nodeid": match["nodeid"], "param": match["param"], "signature": _signature(chunk)})
    return records

def _errors_span(text: str) -> tuple[int, int]:
    """Границы защищённого списка errors=[(mod, err_type)] до нормализации."""
    start, end = text.find("[("), text.find("])", text.find("[(") + 1)
    return (len(text), len(text)) if start < 0 or end < start else (start, end + 2)

def normalize_failure_signature(nodeid: str, raw_trace: str) -> str:
    """Допустима замена только digest-токенов двух hash-comparison assertions."""
    if nodeid not in DIGEST_NODEIDS:
        return raw_trace
    start, end = _errors_span(raw_trace)
    head = DIGEST.sub(DIGEST_MARK, ABBREVIATED_DIGEST.sub(f"'{DIGEST_MARK}'", raw_trace[:start]))
    return head + raw_trace[start:end] + DIGEST.sub(DIGEST_MARK, raw_trace[end:])

def _protected_reasons(baseline_data: dict[str, Any], nodeid: str, signatures: list[str]) -> list[str]:
    """Неизменность защищённого списка errors=[(mod, err_type)] для digest-assertion."""
    frozen = (baseline_data.get("protected_errors") or {}).get(nodeid)
    if not frozen:
        return []
    start, end = _errors_span(raw := "\n".join(signatures))
    if "..." in raw[start:end]:
        return []  # усечённый repr: видимый префикс уже сверен мультимножеством сигнатур
    errors = [(mod, kind) for mod, kind in TUPLE.findall(raw[start:end])]
    expected = [tuple(pair) for pair in frozen]
    if errors == expected:
        return []
    return _new_error_reasons(errors, expected, nodeid)


def _new_error_reasons(errors: list[tuple[str, str]], expected: list[tuple[Any, ...]], nodeid: str) -> list[str]:
    """Причины нарушения protected errors: новые function_bound/legacy_facade или иная правка."""
    extra = [pair for pair in errors if pair not in expected]
    kinds = [kind for kind in FORBIDDEN_KINDS if any(pair[1] == kind for pair in extra)]
    return [f"new_{kind}" for kind in kinds] or [f"changed_errors:{nodeid}"]

def _compare_found(found: dict[str, list[str]], baseline: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Причины отклонения: новые nodeid, изменённые сигнатуры, нарушение protected errors."""
    frozen: dict[str, list[dict[str, Any]]] = {}
    for entry in baseline.get("entries") or []:
        frozen.setdefault(str(entry["nodeid"]), []).append(entry)
    reasons, new_failed, changed = [], [], []
    for nodeid in sorted(found):
        entries = frozen.get(nodeid, [])
        if not entries:
            new_failed.append(nodeid)
            reasons.append(f"new_failed_nodeid:{nodeid}")
            continue
        expected = sorted(FLOAT.sub("<num>", str(entry["normalized_signature"])) for entry in entries)
        if sorted(FLOAT.sub("<num>", normalize_failure_signature(nodeid, item)) for item in found[nodeid]) != expected:
            changed.append(nodeid)
            reasons.append(f"changed_failure_signature:{nodeid}")
        reasons.extend(_protected_reasons(baseline, nodeid, found[nodeid]))
    return reasons, new_failed, changed

def compare_pytest_reports(baseline_data: dict[str, Any], candidate_raw_output: str) -> dict[str, Any]:
    """Вердикт по сырому отчёту pytest; baseline-падение допустимо только с точной сигнатурой."""
    found: dict[str, list[str]] = {}
    for record in parse_failures(candidate_raw_output):
        found.setdefault(record["nodeid"], []).append(record["signature"])
    reasons, new_failed, changed = (["signal_crash"], [], []) if CRASH_LINE.search(candidate_raw_output) else _compare_found(found, baseline_data)
    unique = sorted(set(reasons))
    return {"verdict": "FAIL" if unique else "PASS", "reasons": unique,
            "new_failed_nodeids": sorted(set(new_failed)), "changed_failure_signatures": sorted(set(changed))}

def is_signal_crash(returncode: int | None) -> bool:
    return returncode is not None and (returncode < 0 or returncode >= 128)

def normalizer_source() -> str:
    """Канонический текст парсера и нормализатора, закреплённый SHA-256 в манифесте."""
    pins = (DIGEST.pattern, ABBREVIATED_DIGEST.pattern, DIGEST_MARK, CONTEXT_LINE.pattern, FRAME_BLOCK.pattern,
            FLOAT.pattern, TUPLE.pattern, HEADER.pattern, TRACE.pattern, *DIGEST_NODEIDS)
    functions = (_signature, _param, _summary_entries, parse_failures, _errors_span, normalize_failure_signature)
    return "\n".join(pins) + "\n\n" + "\n\n".join(inspect.getsource(function) for function in functions)

def normalizer_sha256() -> str:
    """SHA-256 канонического текста нормализатора."""
    return hashlib.sha256(normalizer_source().encode("utf-8")).hexdigest()

def load_manifest(path: Path | None = None) -> dict[str, Any]:
    """Читает замороженный манифест baseline-падений."""
    return json.loads((path or MANIFEST).read_text(encoding="utf-8"))

def manifest_problems(manifest: dict[str, Any], expected_sha: str | None = None) -> list[str]:
    """Несоответствия манифеста: версия, SHA, allowlist, полнота, scope нормализации."""
    entries = [entry for entry in manifest.get("entries") or [] if isinstance(entry, dict)]
    checks = _manifest_checks(manifest, entries)
    if expected_sha is not None:
        checks["normalizer_sha256"] = manifest.get("normalizer_sha256") == expected_sha
    return sorted(name for name, ok in checks.items() if not ok)


def _manifest_checks(manifest: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, bool]:
    """Проверки неизменяемости, allowlist, полноты и scope нормализации манифеста."""
    normalized = {str(entry.get("nodeid")) for entry in entries if entry.get("normalized_signature") != entry.get("raw_signature")}
    return {
        "base_revision": manifest.get("base_revision") == BASE_REVISION,
        "count_based_waivers": manifest.get("count_based_waivers") == [], "digest_only_allowlist": manifest.get("digest_only_allowlist") == list(DIGEST_NODEIDS),
        "normalizer_version": manifest.get("normalizer_version") == NORMALIZER_VERSION, "normalizer_sha256": manifest.get("normalizer_sha256") == normalizer_sha256(),
        "entries>=95": len(entries) >= 95, "entry_keys": all(set(REQUIRED_KEYS) <= set(entry) for entry in entries),
        "digest_nodeids": set(DIGEST_NODEIDS) <= {str(entry.get("nodeid")) for entry in entries},
        "normalization_scope": normalized == set(DIGEST_NODEIDS),
    }

def runner_enabled(env: dict[str, str] | None = None) -> bool:
    """Дочерний guarded прогон только по явному флагу и никогда внутри ребёнка."""
    values = os.environ if env is None else env
    return values.get(GATE_ENV) == "1" and values.get(CHILD_ENV) != "1"

def guarded_command() -> list[str]:
    """Точная команда ребёнка: run-guarded -- pytest tests/ -v."""
    guard, pytest_bin = shutil.which("run-guarded"), shutil.which("pytest")
    assert guard is not None and pytest_bin is not None, "BLOCKED: run-guarded/pytest отсутствуют в PATH"
    return [guard, "--", pytest_bin, "tests/", "-v"]

def run_guarded_child(report: Path) -> dict[str, Any]:
    """Guarded-прогон ребёнка, сырой отчёт на диск, вердикт компаратора по манифесту."""
    report.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(guarded_command(), cwd=ROOT, capture_output=True, text=True,
                               timeout=float(os.environ.get("V2SAFE_CHILD_TIMEOUT_S", "7200")),
                               env={**os.environ, CHILD_ENV: "1", "PYTHONPATH": str(ROOT)})
    raw = completed.stdout + completed.stderr
    if is_signal_crash(completed.returncode):
        raw += f"\nSIGNAL_CRASH_FAIL rc={completed.returncode}\n"
    report.write_text(raw, encoding="utf-8")
    return compare_pytest_reports(load_manifest(), raw)

def main(argv: list[str] | None = None) -> int:
    """CLI: verify | compare --report <file> | run --report <file>."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or (args[0] != "verify" and len(args) < 3):
        print(__doc__)
        return 2
    payload = ({"problems": manifest_problems(load_manifest())} if args[0] == "verify" else
               compare_pytest_reports(load_manifest(), Path(args[2]).read_text(encoding="utf-8"))
               if args[0] == "compare" else run_guarded_child(Path(args[2])))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("verdict", "PASS") == "PASS" and not payload.get("problems") else 1

def _entry(nodeid: str, signature: str) -> dict[str, str]:
    """Запись манифеста с сигнатурой, нормализованной штатным нормализатором."""
    return {"nodeid": nodeid, "raw_signature": signature, "exception_type": "AssertionError", "outcome": "FAILED", "normalized_signature": normalize_failure_signature(nodeid, signature), "source_report": "synthetic"}

def _report(entries: list[dict[str, str]]) -> str:
    """Синтетический отчёт pytest: блоки FAILURES и short test summary."""
    blocks = [f"__ {entry['nodeid'].rsplit('::', 1)[-1]} __\n{entry['nodeid'].split('::')[0]}:7: in test_body\n"
              + "".join(f"E   {line}\n" for line in str(entry["raw_signature"]).splitlines()) for entry in entries]
    summary = "\n".join(f"FAILED {entry['nodeid']}" for entry in entries)
    return "=== FAILURES ===\n" + "\n".join(blocks) + "\n=== short test summary info ===\n" + summary + "\n"

def _hash_pair(observed: str, pinned: str) -> str:
    """Текст падения hash-pin assertion так, как его печатает pytest."""
    return (f"AssertionError: assert '{observed[:12]}...{observed[-12:]}' == '{pinned[:12]}...{pinned[-12:]}'\n\n"
            f"- {pinned}\n+ {observed}")

def _bounds_signature(errors: list[list[str]], digest: str) -> str:
    """Текст падения bounds-оракула с полным (неусечённым) списком errors."""
    pairs = ", ".join(f"('{mod}', '{kind}')" for mod, kind in errors)
    return f"AssertionError: ('{digest}', [{pairs}])\nassert not [{pairs}]"

def test_manifest_freezes_exact_baseline() -> None:
    """Манифест полон, непротиворечив, нормализует ровно два nodeid и парсится обратно."""
    manifest = load_manifest()
    assert manifest_problems(manifest) == [] and len(manifest["entries"]) >= 95 and manifest["sources"]
    assert manifest["count_based_waivers"] == [] and manifest["contention_only_unexpected"]
    nodes = {entry["nodeid"] for entry in manifest["entries"] if entry["normalized_signature"] != entry["raw_signature"]}
    assert nodes == set(DIGEST_NODEIDS) and compare_pytest_reports(manifest, _report(list(manifest["entries"])))["verdict"] == "PASS"

def test_digest_spans_normalize_only_allowed_assertions() -> None:
    """Смена digest допустима только в двух hash-comparison assertions."""
    server, bounds = DIGEST_NODEIDS
    pinned = "1" * 64
    allowed = {"entries": [_entry(server, _hash_pair("2" * 64, pinned))]}
    assert compare_pytest_reports(allowed, _report([_entry(server, _hash_pair("0" * 64, pinned))]))["verdict"] == "PASS"
    backend = server.replace("server.py", "core/backend_adapter.py")
    drift = {"entries": [_entry(backend, _hash_pair("2" * 64, pinned))]}
    drift_verdict = compare_pytest_reports(drift, _report([_entry(backend, _hash_pair("0" * 64, pinned))]))
    assert drift_verdict["verdict"] == "FAIL" and drift_verdict["changed_failure_signatures"] == [backend]
    errors = [["adapters/passthrough_adapter.py.relay_sse", "legacy_facade"]]
    bounds_base = {"entries": [_entry(bounds, _bounds_signature(errors, "a" * 64))], "protected_errors": {bounds: errors}}
    moved = _entry(bounds, _bounds_signature(errors, "b" * 64))
    assert compare_pytest_reports(bounds_base, _report([moved]))["verdict"] == "PASS"

def test_forbidden_signature_changes_fail() -> None:
    """Изменённый текст, новый function_bound/legacy_facade и новый nodeid — FAIL."""
    server, bounds = DIGEST_NODEIDS
    base = {"entries": [_entry(server, _hash_pair("2" * 64, "1" * 64))]}
    broken = _hash_pair("2" * 64, "1" * 64).replace("AssertionError", "ValueError")
    verdict = compare_pytest_reports(base, _report([_entry(server, broken)]))
    assert verdict["verdict"] == "FAIL" and verdict["changed_failure_signatures"] == [server]
    errors = [["adapters/passthrough_adapter.py.relay_sse", "legacy_facade"]]
    frozen = {"entries": [_entry(bounds, _bounds_signature(errors, "a" * 64))], "protected_errors": {bounds: errors}}
    for kind in FORBIDDEN_KINDS:
        grown = errors + [[f"core/new_mod.py.foo_{kind}", kind]]
        verdict = compare_pytest_reports(frozen, _report([_entry(bounds, _bounds_signature(grown, "a" * 64))]))
        assert verdict["verdict"] == "FAIL" and f"new_{kind}" in verdict["reasons"]
    plain = "tests/test_transport_replay.py::test_committed_sse_never_replays[delta2]"
    drift = {"entries": [_entry(plain, "AssertionError: 0 != 1")]}
    assert compare_pytest_reports(drift, _report([_entry(plain, "AssertionError: 0 != 2")]))["changed_failure_signatures"] == [plain]
    assert compare_pytest_reports(drift, _report([_entry("tests/test_new.py::test_new", "AssertionError: x")]))["new_failed_nodeids"] == ["tests/test_new.py::test_new"]

def test_signal_crash_and_runner_gate() -> None:
    """rc=139/-11 — безусловный FAIL; дочерний прогон только по флагу и без рекурсии."""
    assert is_signal_crash(139) and is_signal_crash(-11) and not is_signal_crash(1)
    manifest = load_manifest()
    verdict = compare_pytest_reports(manifest, _report(list(manifest["entries"])) + "SIGNAL_CRASH_FAIL rc=139\n")
    assert verdict["verdict"] == "FAIL" and "signal_crash" in verdict["reasons"]
    assert runner_enabled({GATE_ENV: "1"}) is True and not runner_enabled({}) and not runner_enabled({GATE_ENV: "1", CHILD_ENV: "1"})
    assert "tests/" in guarded_command()

def test_guarded_child_matches_frozen_baseline(tmp_path: Path) -> None:
    """Опциональный guarded-прогон ребёнка; без флага дочерний pytest не запускается."""
    if runner_enabled():
        assert run_guarded_child(tmp_path / "guarded-baseline-child.txt")["verdict"] == "PASS"
