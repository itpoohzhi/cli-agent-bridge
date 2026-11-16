"""VER-001/003: независимые gates frozen-пакета и фактического CAB diff."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from graphlib import TopologicalSorter
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_architecture_modularity_dag import _environment_reads, _imports
from tests.test_transport_modularity import exceeds, function_source, functions, metrics

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / ".ai-team/runs/tv2safe-20261116"
BASE = "5ecd42a181c6e7217471659e75e008ab18355da7"
BASELINE_SHA = "169193f264c3d1f153925d8a10fab2d7f2fa2d820b9c2443c413e398b2cf8d91"
NETWORK = {"socket", "http", "httpx", "requests", "urllib", "aiohttp"}
PURE = {"core/route_eligibility.py", "core/catalog_routes.py", "core/stream_outcome.py"}
PURE_FUNCTIONS = {"core/route_penalty_state.py": ("step",), "core/model_notes_parse.py": ("parse_model_notes",)}
IO_CALLS = {"open", "read_text", "read_bytes", "write_text", "write_bytes", "stat", "unlink",
            "mkdir", "connect", "urlopen", "Popen", "run", "system"}

def load_packet() -> dict[str, Any]:
    return json.loads((RUN / "architecture/frozen-packet.json").read_bytes())

def git(*arguments: str) -> bytes:
    result = subprocess.run(["git", "-C", str(ROOT), *arguments], capture_output=True,
                            timeout=float(os.environ.get("V2SAFE_GIT_TIMEOUT_S", "10")), check=True)
    return result.stdout

def wave_targets(packet: dict[str, Any]) -> set[str]:
    return {path for card in packet["wave_plan"] if card["repo"] == "CAB" for path in card["target_files"]}

def audit_paths() -> list[Path]:
    targets = wave_targets(load_packet())
    changed = set(os.fsdecode(git("diff", "--name-only", "-z", BASE)).split("\0"))
    paths = (changed & targets) | {str(p.relative_to(ROOT)) for p in ROOT.glob("tests/test_v2safe_*.py")}
    paths |= {p for p in targets if p.startswith("core/") and not git("ls-tree", BASE, "--", p)}
    return sorted(ROOT / path for path in paths if path.endswith(".py") and (ROOT / path).is_file())

def function_violations(path: Path) -> list[tuple[str, tuple[int, int, int]]]:
    relative, current = str(path.relative_to(ROOT)), path.read_bytes()
    exists = bool(git("ls-tree", BASE, "--", relative))
    previous = git("show", f"{BASE}:{relative}") if exists else b""
    old = functions(previous)
    failures = []
    for name, node in functions(current).items():
        if name in old and function_source(previous, old[name]) == function_source(current, node):
            continue
        if exceeds(metrics(node)):
            failures.append((relative + name, metrics(node)))
    return failures

def check_dag(cards: list[dict[str, Any]]) -> dict[str, set[str]]:
    graph = {card["id"]: set(card["depends_on"]) for card in cards}
    assert len(graph) == len(cards), "duplicate wave id"
    assert set().union(*graph.values()) <= graph.keys(), "unknown dependency"
    order = list(TopologicalSorter(graph).static_order())
    assert set(graph) - set().union(*graph.values()) == {"S3-12"}, "sole sink"
    ancestors: dict[str, set[str]] = {}
    for key in order:
        ancestors[key] = graph[key] | set().union(*(ancestors[parent] for parent in graph[key]))
    return ancestors

def test_packet_wave_inventory_and_ordered_writers() -> None:
    packet = load_packet()
    waves = json.loads((RUN / "wave-plan.json").read_bytes())
    roles = json.loads((RUN / "architecture/role-plan.json").read_bytes())
    cards = waves["wave_plan"]
    assert cards == packet["wave_plan"]
    assert len(cards) == waves["wave_count"] == roles["wave_count"] == 92
    assert Counter(card["phase"] for card in cards) == {"W0": 18, "W1": 15, "W2": 46, "W3": 13}
    assert waves["phase_counts"] == roles["phase_counts"] == dict(Counter(card["phase"] for card in cards))
    check_ordered_writers(cards, check_dag(cards))
    inventories = [set(roles[k + "_files"]) for k in ("product", "test", "document", "artifact")]
    assert list(map(len, inventories)) == [53, 72, 6, 4]
    assert sum(map(len, inventories)) == len(set.union(*inventories)), "overlapping inventories"
    assert {p for card in cards for p in card["target_files"]} == set.union(*inventories)

def check_ordered_writers(cards: list[dict[str, Any]], ancestors: dict[str, set[str]]) -> None:
    writers: dict[tuple[str, str], list[str]] = {}
    for card in cards:
        assert card["repo"] in {"CAB", "SKILS"}
        assert 1 <= len(card["target_files"]) <= 2
        assert len(set(card["target_files"])) == len(card["target_files"])
        for path in card["target_files"]:
            assert not Path(path).is_absolute() and ".." not in Path(path).parts
            key = (card["repo"], path)
            for previous in writers.get(key, []):
                assert previous in ancestors[card["id"]] or card["id"] in ancestors[previous], key
            writers.setdefault(key, []).append(card["id"])

def test_immutable_163_baseline() -> None:
    raw = (RUN / "baseline-monoliths.json").read_bytes()
    baseline, modularity = json.loads(raw), load_packet()["modularity"]
    assert hashlib.sha256(raw).hexdigest() == modularity["baseline_sha256"] == BASELINE_SHA
    assert len(baseline["files"]) == modularity["baseline_files"] == 163
    assert baseline["cab_base_commit"] == modularity["base_revision"] == BASE
    keys = [(item["repo"], item["path"]) for item in baseline["files"]]
    assert len(set(keys)) == 163

def file_cap_violations() -> list[tuple[str, int, int]]:
    packet = load_packet()
    policy = packet["modularity"]
    baseline = json.loads((RUN / "baseline-monoliths.json").read_bytes())
    legacy = {item["path"]: item["lines"] for item in baseline["files"]
              if item["repo"] == policy["repo_ids"]["cab"]["frozen_legacy_repo_value"]}
    changed = set(os.fsdecode(git("diff", "--name-only", "-z", BASE)).split("\0"))
    changed.update(os.fsdecode(git("ls-files", "--others", "--exclude-standard", "-z", "--", "*.py")).split("\0"))
    changed.update(str(path.relative_to(ROOT)) for path in audit_paths())
    paths = wave_targets(packet) | legacy.keys() | changed
    if os.environ.get("V2SAFE_STRICT_ALL_CAPS") != "1":
        paths &= changed
    errors = []
    for path in sorted(paths):
        source = ROOT / path
        if not source.is_file() or (not path.endswith(".py") and path not in policy["file_caps"]):
            continue
        cap = policy["file_caps"].get(path, legacy.get(path, policy["default_file_cap"]))
        count = len(source.read_bytes().splitlines())
        if count > cap:
            errors.append((path, count, cap))
    return errors

def test_all_existing_target_file_caps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packet = load_packet()
    packet["modularity"]["file_caps"]["custom.json"] = 1
    sizes = dict.fromkeys(("changed.py", "new.py", "audit.py", "fleet.json", "notes.yaml", "CHANGELOG.md"), 301)
    sizes.update({"custom.json": 2, "server.py": 7993, "core/http_post_dispatch.py": 300})
    for path, count in sizes.items():
        source = tmp_path / path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"\n" * count)
    changed = b"changed.py\0custom.json\0fleet.json\0notes.yaml\0CHANGELOG.md\0"
    expected = [("audit.py", 301, 300), ("changed.py", 301, 300), ("custom.json", 2, 1), ("new.py", 301, 300)]
    with monkeypatch.context() as scoped:
        scoped.setattr(sys.modules[__name__], "ROOT", tmp_path)
        scoped.setattr(sys.modules[__name__], "load_packet", lambda: packet)
        scoped.setattr(sys.modules[__name__], "audit_paths", lambda: [tmp_path / "audit.py"])
        scoped.setattr(sys.modules[__name__], "git", lambda *args: changed if args[0] == "diff" else b"new.py\0")
        scoped.setenv("V2SAFE_STRICT_ALL_CAPS", "0")
        assert file_cap_violations() == expected
        (tmp_path / "new.py").write_bytes(b"\n" * 300)
        assert file_cap_violations() == expected[:-1]
        (tmp_path / "new.py").write_bytes(b"\n" * 301)
        strict = sorted(expected + [("server.py", 7993, 7992), ("core/http_post_dispatch.py", 300, 295)])
        scoped.setenv("V2SAFE_STRICT_ALL_CAPS", "1")
        assert file_cap_violations() == strict
        scoped.setenv("V2SAFE_STRICT_ALL_CAPS", "0")
        changed += b"server.py\0core/http_post_dispatch.py\0"
        assert file_cap_violations() == strict
    assert not (errors := file_cap_violations()), errors

def test_all_new_or_modified_functions_zero_exceptions() -> None:
    failures = [failure for path in audit_paths() for failure in function_violations(path)]
    assert not failures, failures

@pytest.mark.parametrize("source,expected", [
    ("def f():\n" + "    pass\n" * 39 + "    return 1\n", (41, 0, 1)),
    ("def f(a,b,c,d,e,f):\n    pass\n", (2, 6, 1)),
    ("def f(x):\n" + "    if x: pass\n" * 10, (11, 1, 11)),
    ("def f(a,b,c,d,e):\n" + "    pass\n" * 38 + "    return a\n", (40, 5, 1)),
])
def test_ast_metric_boundary_canaries(source: str, expected: tuple[int, int, int]) -> None:
    actual = metrics(functions(source.encode())[".f"])
    assert actual == expected
    assert exceeds(actual) is any(a > b for a, b in zip(expected, (40, 5, 10), strict=True))

def test_changed_v2safe_ruff_and_no_blanket_noqa() -> None:
    paths = audit_paths()
    assert paths
    blanket = re.compile(r"#\s*(?:ruff:\s*)?noqa(?!\s*:)", re.I)
    assert not [str(p) for p in paths if blanket.search(p.read_text())]
    executable = shutil.which("ruff")
    assert executable is not None, "ruff required"
    result = subprocess.run([executable, "check", "--select", "E4,E7,E9,F", *map(str, paths)],
                            cwd=ROOT, capture_output=True, text=True,
                            timeout=float(os.environ.get("V2SAFE_LINT_TIMEOUT_S", "30")))
    assert result.returncode == 0, result.stdout + result.stderr

def _io_calls(tree: ast.AST) -> list[ast.Call]:
    aliases = {alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
               for alias in node.names if alias.name in IO_CALLS}
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and (getattr(node.func, "attr", None) or getattr(node.func, "id", None)) in IO_CALLS | aliases]

def _domain_violations(path: str, tree: ast.Module) -> list[str]:
    reads = [*_environment_reads(tree), *_io_calls(tree)]
    if path in PURE or path == "core/http_post_dispatch_guard.py":
        return ["domain I/O/env"] * bool(reads)
    return ["domain I/O/env" for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in PURE_FUNCTIONS.get(path, ())
            and any(node.lineno <= int(getattr(item, "lineno")) <= (node.end_lineno or node.lineno) for item in reads)]

def boundary_violations(path: str, source: str) -> list[str]:
    tree = ast.parse(source)
    imports = _imports(tree, path)
    roots = {item.split(".")[0] for item in imports}
    failures = []
    if path.startswith("core/"):
        failures += ["outward import"] * bool(roots & {"adapters", "bridges", "server"})
    if path != "core/model_notes_filter.py":
        failures += ["network import"] * bool(roots & NETWORK)
    if path == "core/http_post_dispatch_guard.py":
        failures += ["presentation import"] * any("published_model_status" in item.split(".") for item in imports)
    if path == "core/stream_outcome.py":
        failures += ["subprocess import"] * ("subprocess" in roots)
    return failures + _domain_violations(path, tree)

def test_cab_import_boundaries_bnd_001_through_013() -> None:
    packet = load_packet()
    assert {b["id"] for b in packet["boundaries"]} == {f"BND-{n:03}" for n in range(1, 14)}
    paths = {b["component"] for b in packet["boundaries"] if b["component"].startswith("core/")}
    failures = {p: boundary_violations(p, (ROOT / p).read_text()) for p in paths if (ROOT / p).exists()}
    assert not {p: errors for p, errors in failures.items() if errors}

@pytest.mark.parametrize("path,source", [
    ("core/http_post_dispatch_guard.py", "from . import published_model_status"),
    ("core/http_post_dispatch_guard.py", "from core.published_model_status import status"),
    ("core/stream_outcome.py", "import subprocess"),
    ("core/route_eligibility.py", "import os as e\nx=e.getenv('X')"),
    ("core/catalog_routes.py", "from os import environ as e\nx=e['X']"),
    ("core/route_penalty_state.py", "def step():\n    return open('x')"),
    ("core/route_penalty_state.py", "from os import getenv as e\ndef step():\n    return e('X')"),
    ("core/route_penalty_state.py", "from builtins import open as o\ndef step():\n    return o('x')"),
    ("core/model_notes_parse.py", "def parse_model_notes():\n    return source.read_text()"),
    ("core/lease_identity.py", "import requests"),
])
def test_boundary_negative_canaries(path: str, source: str) -> None:
    assert boundary_violations(path, source)

def signal_result(returncode: int) -> str:
    return "SIGNAL_CRASH_FAIL" if returncode < 0 or returncode >= 128 else "normal"

@pytest.mark.parametrize("rc", [-11, -15, 128, 139, 255])
def test_signal_crash_predicate(rc: int) -> None:
    assert signal_result(rc) == "SIGNAL_CRASH_FAIL"
    assert signal_result(0) == signal_result(1) == signal_result(127) == "normal"

def test_run_guarded_detects_signal_exit() -> None:
    guard = shutil.which("run-guarded")
    assert guard is not None, "run-guarded required"
    # Shell-style SIGSEGV не создаёт реальный crash-report в родительском прогоне.
    result = subprocess.run([guard, "--settle", "0", "--", sys.executable, "-c", "raise SystemExit(139)"],
                            capture_output=True, text=True,
                            timeout=float(os.environ.get("V2SAFE_GUARD_TIMEOUT_S", "30")))
    assert result.returncode != 0 and "SIGSEGV" in result.stderr
    assert signal_result(139) == "SIGNAL_CRASH_FAIL"
