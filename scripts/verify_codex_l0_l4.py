#!/usr/bin/env python3
"""Verification runner for Codex v2 & Zero-Canon gates: L0, L3, L4, and M-MOD."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_codex_mutation_sabotage as l4_mod  # noqa: E402

DEFAULT_BASE_REV = "18039277c2da6d2e072e7b5fcdb1fc987e1ab154"
PURE_MODULES = frozenset({
    "core/stdio_resident/codex_protocol_fsm.py",
    "core/codex_zero_canon_policy.py",
    "core/route_catalog_contract.py",
    "core/codex_recovery_fsm.py",
})
FORBIDDEN_IO_24 = frozenset({
    "os", "sys", "socket", "ssl", "subprocess", "asyncio", "httpx", "aiohttp",
    "websockets", "requests", "urllib", "curl_cffi", "litestar", "sqlalchemy",
    "asyncpg", "psycopg", "sqlite3", "redis", "valkey", "aioboto3", "aiofiles",
    "pathlib", "shutil", "tempfile",
})
FORBIDDEN_CLOCKS = frozenset({"time", "datetime"})
FORBIDDEN_BUILTINS = frozenset({"open", "input", "print", "__import__"})
INFRA_CATEGORIES: Mapping[str, frozenset[str]] = {
    "TRANSPORT": frozenset({"fastapi", "litestar", "starlette", "flask", "aiohttp.web", "websockets", "typer", "click"}),
    "PERSISTENCE": frozenset({"sqlalchemy", "asyncpg", "psycopg", "sqlite3", "redis", "valkey", "aioboto3"}),
    "NET_PROC_IO": frozenset({"httpx", "aiohttp", "requests", "urllib", "curl_cffi", "subprocess", "socket"}),
}
MONOLITH_PATHS = frozenset({"server.py", "core/http_post_routing.py"})
REAL_SECRET_RE = re.compile(r"\bsk-(?:proj|live)-[A-Za-z0-9_-]{12,}\b")
L3_TESTS = (
    "tests/test_codex_l3_incident_corpus.py",
    "tests/test_codex_app_server_v2_contract.py",
    "tests/test_codex_app_server_v2_fsm.py",
    "tests/test_codex_zero_canon_contract.py",
    "tests/test_codex_zero_canon_policy.py",
    "tests/test_codex_catalogue_contract.py",
    "tests/test_stdio_process_io.py",
    "tests/test_stdio_resident_codex.py",
    "tests/test_subbridge_zero_canon_domain.py",
    "tests/test_subbridge_zero_canon_runtime.py",
)
_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


def _kill_pgid(pgid: int) -> None:
    if pgid <= 1 or pgid == os.getpgrp():
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return


def _run_pgid(
    cmd: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None, timeout_s: float = 60.0
) -> tuple[int, str, str]:
    proc = subprocess.Popen(
        list(cmd),
        cwd=str(cwd),
        env=dict(os.environ if env is None else env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    pgid = proc.pid
    try:
        out, err = proc.communicate(timeout=timeout_s)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        _kill_pgid(pgid)
        out, err = proc.communicate(timeout=5.0)
        return -1, out, f"timeout_expired\n{err}"
    finally:
        if proc.poll() is None:
            _kill_pgid(pgid)
            proc.wait()


def _git_changed_py(base_revision: str, explicit: Sequence[str] = ()) -> list[str]:
    if explicit:
        return sorted(p for p in explicit if (ROOT / p).is_file() and p.endswith(".py"))
    rc1, diff_out, _ = _run_pgid(["git", "diff", "--name-only", base_revision, "--", "*.py"], ROOT)
    rc2, unt_out, _ = _run_pgid(["git", "ls-files", "--others", "--exclude-standard", "--", "*.py"], ROOT)
    if rc1 != 0 or rc2 != 0:
        raise RuntimeError(f"git_diff_failed: base={base_revision}")
    found = {ln.strip() for ln in (diff_out + "\n" + unt_out).splitlines() if ln.strip()}
    return sorted(p for p in found if (ROOT / p).is_file())


def _base_bytes(base_revision: str, rel: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{base_revision}:{rel}"],
        capture_output=True,
        check=False,
        timeout=10.0,
    )
    return proc.stdout if proc.returncode == 0 else b""


def _phys_loc(data: bytes) -> int:
    return data.count(b"\n") + int(bool(data) and not data.endswith(b"\n"))


def _collect_imports(tree: ast.AST) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
            mods.update(f"{node.module}.{alias.name}" for alias in node.names)
    return mods


def _infra_categories(imports: set[str]) -> set[str]:
    cats: set[str] = set()
    for mod in imports:
        best: tuple[int, str] | None = None
        for cat, names in INFRA_CATEGORIES.items():
            for name in names:
                if mod == name or mod.startswith(f"{name}."):
                    if best is None or len(name) > best[0]:
                        best = (len(name), cat)
        if best is not None:
            cats.add(best[1])
    return cats


def _check_pure_zero_io(rel: str, tree: ast.AST) -> list[str]:
    issues: list[str] = []
    for mod in sorted(_collect_imports(tree)):
        root_mod = mod.split(".", 1)[0]
        if root_mod in FORBIDDEN_IO_24 or root_mod in FORBIDDEN_CLOCKS:
            issues.append(f"{rel}: forbidden pure import {mod}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_BUILTINS:
            issues.append(f"{rel}:{node.lineno}: forbidden builtin {node.func.id}")
    return issues


def _branch_weight(node: ast.AST) -> int:
    if isinstance(node, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
        return 1
    if isinstance(node, ast.BoolOp):
        return len(node.values) - 1
    if isinstance(node, ast.comprehension):
        return 1 + len(node.ifs)
    return 0


def _fn_metrics(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, int, int]:
    start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
    args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    params = sum(a.arg not in {"self", "cls"} for a in args) + int(node.args.vararg is not None) + int(node.args.kwarg is not None)
    branches, stack = 0, list(ast.iter_child_nodes(node))
    while stack:
        item = stack.pop()
        if isinstance(item, (*_FUNCS, ast.ClassDef, ast.Lambda)):
            continue
        branches += _branch_weight(item)
        stack.extend(ast.iter_child_nodes(item))
    return (node.end_lineno or start) - start + 1, params, 1 + branches


def _functions(tree: ast.AST, prefix: str = "") -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    found: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for ch in ast.iter_child_nodes(tree):
        if isinstance(ch, (*_FUNCS, ast.ClassDef)):
            name = f"{prefix}{ch.name}"
            if isinstance(ch, _FUNCS):
                found[name] = ch
            found.update(_functions(ch, f"{name}."))
        else:
            found.update(_functions(ch, prefix))
    return found


def _tarjan_cycles(nodes: set[str], edges: Mapping[str, set[str]]) -> list[list[str]]:
    index, stack, on_stack = 0, list[str](), set[str]()
    indices, lowlink, cycles = dict[str, int](), dict[str, int](), list[list[str]]()

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)
        for w in sorted(edges.get(v, ())):
            if w == v:
                cycles.append([v, v])
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])
        if lowlink[v] == indices[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                cycles.append(sorted(comp))

    for n in sorted(nodes):
        if n not in indices:
            strongconnect(n)
    return cycles


def _check_file_m_mod(
    rel: str, base_revision: str, violations: dict[str, list[str]], monolith_deltas: dict[str, int]
) -> tuple[ast.Module, set[str]]:
    raw = (ROOT / rel).read_bytes()
    before = _base_bytes(base_revision, rel)
    b_loc, a_loc = _phys_loc(before), _phys_loc(raw)
    tree = ast.parse(raw.decode("utf-8"), filename=rel)
    imports = _collect_imports(tree)
    cats = _infra_categories(imports)
    if len(cats) > 1 or (rel in PURE_MODULES and cats):
        violations["M-MOD-I1"].append(f"{rel}: categories={sorted(cats)}")
    if rel in MONOLITH_PATHS or b_loc > 500:
        monolith_deltas[rel] = a_loc - b_loc
        if a_loc > b_loc:
            violations["M-MOD-I2"].append(f"{rel}: monolith grew {b_loc}->{a_loc}")
    elif b_loc == 0 and a_loc > 300:
        violations["M-MOD-I2"].append(f"{rel}: new module {a_loc} > 300 LOC")
    elif b_loc > 0 and a_loc > 500:
        violations["M-MOD-I2"].append(f"{rel}: changed module {a_loc} > 500 LOC")
    if rel in PURE_MODULES:
        violations["M-MOD-I3"].extend(_check_pure_zero_io(rel, tree))
    _check_fn_budgets(rel, before, tree, violations["M-MOD-I4"])
    return tree, imports


def _check_fn_budgets(rel: str, before: bytes, tree: ast.Module, out: list[str]) -> None:
    if rel in MONOLITH_PATHS or _phys_loc(before) > 500:
        return
    if "from __future__ import annotations" not in (ROOT / rel).read_text(encoding="utf-8"):
        out.append(f"{rel}: missing future annotations")
    old_fns = _functions(ast.parse(before.decode("utf-8"))) if before else {}
    for name, node in _functions(tree).items():
        if name in old_fns and ast.dump(old_fns[name]) == ast.dump(node):
            continue
        floc, params, cc = _fn_metrics(node)
        if floc > 50 or cc > 10 or (params > 5 and name not in old_fns):
            out.append(f"{rel}:{name} loc={floc} params={params} cc={cc}")


def run_m_mod(base_revision: str, paths: Sequence[str] = ()) -> tuple[bool, dict[str, Any]]:
    """Evaluate M-MOD code-PASS strictly separate from plan-PASS."""
    files = _git_changed_py(base_revision, paths)
    violations: dict[str, list[str]] = {f"M-MOD-I{i}": [] for i in range(1, 6)}
    monolith_deltas: dict[str, int] = {}
    mod_map = {p[:-3].replace("/", "."): p for p in files}
    edges: dict[str, set[str]] = {m: set() for m in mod_map}
    for rel in files:
        _, imports = _check_file_m_mod(rel, base_revision, violations, monolith_deltas)
        src_mod = rel[:-3].replace("/", ".")
        edges[src_mod] = {imp for imp in imports if imp in mod_map}
    for cyc in _tarjan_cycles(set(mod_map), edges):
        violations["M-MOD-I5"].append("cycle:" + "->".join(cyc))
    code_pass = all(not v for v in violations.values())
    return code_pass, {
        "level": "M-MOD",
        "base_revision": base_revision,
        "plan_pass": None,
        "code_pass": code_pass,
        "files_checked": len(files),
        "monolith_deltas": monolith_deltas,
        "gates": {k: not v for k, v in violations.items()},
        "violations": {k: v for k, v in violations.items() if v},
    }


def run_l0(base_revision: str) -> tuple[bool, dict[str, Any]]:
    """Run L0 static verification: catalog sync, schemas, ruff, secrets, and pure Zero-I/O."""
    sync_rc, sync_out, sync_err = _run_pgid([sys.executable, "scripts/sync_codex_catalog.py", "--check", "--json"], ROOT)
    codex_yaml = yaml.safe_load((ROOT / "providers.d" / "codex.yaml").read_text(encoding="utf-8"))
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    no_62_alias = "gpt-6.2-sol" not in fleet.get("aliases", {})
    sol_efforts = codex_yaml["models_overrides"]["gpt-6.1-sol"]["efforts"] == ["low", "medium", "high", "xhigh", "max"]
    files = _git_changed_py(base_revision)
    ruff_exe = shutil.which("ruff")
    ruff_rc, ruff_out, ruff_err = _run_pgid([ruff_exe, "check", *files], ROOT) if ruff_exe and files else (0, "", "")
    secret_hits = [p for p in files if REAL_SECRET_RE.search((ROOT / p).read_text(encoding="utf-8"))]
    pure_issues = [
        issue for rel in sorted(PURE_MODULES) if (ROOT / rel).is_file()
        for issue in _check_pure_zero_io(rel, ast.parse((ROOT / rel).read_text(encoding="utf-8")))
    ]
    ok = sync_rc == 0 and no_62_alias and sol_efforts and ruff_rc == 0 and not secret_hits and not pure_issues
    return ok, {
        "level": "L0",
        "ok": ok,
        "catalog_sync_ok": sync_rc == 0,
        "no_gpt_6_2_sol_alias": no_62_alias,
        "sol_efforts_ok": sol_efforts,
        "ruff_ok": ruff_rc == 0,
        "secret_hits": secret_hits,
        "pure_zero_io_issues": pure_issues,
        "detail": (sync_out or sync_err or ruff_out or ruff_err).strip()[:240],
    }


def run_l3(base_revision: str) -> tuple[bool, dict[str, Any]]:
    """Run L3 incident corpus and Codex contract suite in an isolated disposable HOME."""
    started = time.monotonic()
    before = l4_mod.tree_digest(ROOT)
    sync_rc, _, sync_err = _run_pgid([sys.executable, "scripts/sync_codex_catalog.py", "--check"], ROOT)
    suite = [t for t in L3_TESTS if (ROOT / t).is_file()]
    with tempfile.TemporaryDirectory(prefix="codex-l3-") as tmp:
        iso = Path(tmp) / "home"
        iso.mkdir(mode=0o700)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BRIDGE_", "AGY_", "OPENAI_", "CODEX_"))}
        env.update(
            HOME=str(iso), CODEX_HOME=str(iso / ".codex"), XDG_CONFIG_HOME=str(iso / ".config"),
            XDG_DATA_HOME=str(iso / ".local" / "share"), XDG_CACHE_HOME=str(iso / ".cache"),
            XDG_STATE_HOME=str(iso / ".local" / "state"), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
        )
        rc, out, err = _run_pgid(l4_mod.pytest_command([*suite, "-q", "-p", "no:cacheprovider"]), ROOT, env, 90.0)
    leaks = int(l4_mod.tree_digest(ROOT) != before)
    ok = sync_rc == 0 and rc == 0 and leaks == 0
    return ok, {
        "level": "L3",
        "base_revision": base_revision,
        "ok": ok,
        "catalog_sync_ok": sync_rc == 0,
        "tests_run": len(suite),
        "state_leaks": leaks,
        "elapsed_s": round(time.monotonic() - started, 3),
        "summary": (out.strip().splitlines()[-1] if out.strip() else (err or sync_err).strip()[:200]),
    }


def run_l4(base_revision: str) -> tuple[bool, dict[str, Any]]:
    """Run L4 AST diff-mutation and critical sabotage in a disposable temporary directory."""
    with tempfile.TemporaryDirectory(prefix="codex-l4-") as tmp:
        rep = l4_mod.run_l4_gate(Path(tmp), base_revision=base_revision)
    return rep.passed, {
        "level": "L4",
        "base_revision": base_revision,
        "ok": rep.passed,
        "baseline_ok": rep.baseline_ok,
        "total": rep.total,
        "killed": rep.killed,
        "kill_rate": round(rep.kill_rate, 4),
        "survivors": list(rep.survivors),
        "surviving_critical": list(rep.surviving_critical),
        "timeout_count": rep.timeout_count,
        "generated": rep.generated,
        "invalid": rep.invalid,
        "invalid_rate": round(rep.invalid_rate, 4),
        "elapsed_s": rep.elapsed_s,
        "state_leaks": rep.state_leaks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Codex v2 L0/L3/L4/M-MOD gates.")
    parser.add_argument("--level", required=True, choices=("L0", "L3", "L4", "M-MOD"))
    parser.add_argument("--base-revision", default=DEFAULT_BASE_REV)
    parser.add_argument("--paths", nargs="*", default=())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.level == "L0":
        ok, payload = run_l0(args.base_revision)
    elif args.level == "L3":
        ok, payload = run_l3(args.base_revision)
    elif args.level == "L4":
        ok, payload = run_l4(args.base_revision)
    else:
        ok, payload = run_m_mod(args.base_revision, args.paths)
    stream = sys.stdout if ok else sys.stderr
    print(json.dumps(payload, sort_keys=True, ensure_ascii=False), file=stream)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
