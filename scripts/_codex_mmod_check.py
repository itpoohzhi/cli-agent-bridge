"""M-MOD modularity checker and shared PGID/AST helpers for Codex verification gates."""

from __future__ import annotations

import ast
import os
import signal
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
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
_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


def kill_pgid(pgid: int) -> None:
    if pgid <= 1 or pgid == os.getpgrp():
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return


def run_pgid(
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
        kill_pgid(pgid)
        out, err = proc.communicate(timeout=5.0)
        return -1, out, f"timeout_expired\n{err}"
    finally:
        if proc.poll() is None:
            kill_pgid(pgid)
            proc.wait()


def _existing_py(paths: Iterable[str]) -> list[str]:
    return sorted({p for p in paths if p and p.endswith(".py") and (ROOT / p).is_file()})


def git_changed_py(base_revision: str, explicit: Sequence[str] = ()) -> list[str]:
    if explicit:
        return _existing_py(explicit)
    rc1, diff_out, _ = run_pgid(["git", "diff", "--name-only", base_revision, "--", "*.py"], ROOT)
    rc2, unt_out, _ = run_pgid(["git", "ls-files", "--others", "--exclude-standard", "--", "*.py"], ROOT)
    if rc1 != 0 or rc2 != 0:
        raise RuntimeError(f"git_diff_failed: base={base_revision}")
    return _existing_py(ln.strip() for ln in (diff_out + "\n" + unt_out).splitlines())


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
                if (mod == name or mod.startswith(f"{name}.")) and (best is None or len(name) > best[0]):
                    best = (len(name), cat)
        if best is not None:
            cats.add(best[1])
    return cats


def check_pure_zero_io(rel: str, tree: ast.AST) -> list[str]:
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


def _check_loc_budget(rel: str, b_loc: int, a_loc: int, monolith_deltas: dict[str, int]) -> str | None:
    if rel in MONOLITH_PATHS or b_loc > 500:
        monolith_deltas[rel] = a_loc - b_loc
        return f"{rel}: monolith grew {b_loc}->{a_loc}" if a_loc > b_loc else None
    if b_loc == 0 and a_loc > 300:
        return f"{rel}: new module {a_loc} > 300 LOC"
    if b_loc > 0 and a_loc > 500:
        return f"{rel}: changed module {a_loc} > 500 LOC"
    return None


def _fn_budget_violation(
    rel: str, name: str, node: ast.FunctionDef | ast.AsyncFunctionDef, is_new: bool
) -> str | None:
    floc, params, cc = _fn_metrics(node)
    if floc > 50 or cc > 10 or (params > 5 and is_new):
        return f"{rel}:{name} loc={floc} params={params} cc={cc}"
    return None


def _check_fn_budgets(rel: str, before: bytes, tree: ast.Module, out: list[str]) -> None:
    if rel in MONOLITH_PATHS or _phys_loc(before) > 500:
        return
    if "from __future__ import annotations" not in (ROOT / rel).read_text(encoding="utf-8"):
        out.append(f"{rel}: missing future annotations")
    old_fns = _functions(ast.parse(before.decode("utf-8"))) if before else {}
    for name, node in _functions(tree).items():
        if name in old_fns and ast.dump(old_fns[name]) == ast.dump(node):
            continue
        if (msg := _fn_budget_violation(rel, name, node, name not in old_fns)) is not None:
            out.append(msg)


def _check_file_m_mod(
    rel: str, base_revision: str, violations: dict[str, list[str]], monolith_deltas: dict[str, int]
) -> tuple[ast.Module, set[str]]:
    raw = (ROOT / rel).read_bytes()
    before = _base_bytes(base_revision, rel)
    tree = ast.parse(raw.decode("utf-8"), filename=rel)
    imports = _collect_imports(tree)
    cats = _infra_categories(imports)
    if len(cats) > 1 or (rel in PURE_MODULES and cats):
        violations["M-MOD-I1"].append(f"{rel}: categories={sorted(cats)}")
    if (loc_err := _check_loc_budget(rel, _phys_loc(before), _phys_loc(raw), monolith_deltas)) is not None:
        violations["M-MOD-I2"].append(loc_err)
    if rel in PURE_MODULES:
        violations["M-MOD-I3"].extend(check_pure_zero_io(rel, tree))
    _check_fn_budgets(rel, before, tree, violations["M-MOD-I4"])
    return tree, imports


def _mmod_report(
    base_revision: str, files_checked: int, monolith_deltas: dict[str, int], violations: dict[str, list[str]]
) -> tuple[bool, dict[str, Any]]:
    code_pass = all(not v for v in violations.values())
    return code_pass, {
        "level": "M-MOD",
        "base_revision": base_revision,
        "plan_pass": None,
        "code_pass": code_pass,
        "files_checked": files_checked,
        "monolith_deltas": monolith_deltas,
        "gates": {k: not v for k, v in violations.items()},
        "violations": {k: v for k, v in violations.items() if v},
    }


def run_m_mod(base_revision: str, paths: Sequence[str] = ()) -> tuple[bool, dict[str, Any]]:
    """Evaluate M-MOD code-PASS strictly separate from plan-PASS."""
    files = git_changed_py(base_revision, paths)
    violations: dict[str, list[str]] = {f"M-MOD-I{i}": [] for i in range(1, 6)}
    monolith_deltas: dict[str, int] = {}
    mod_map = {p[:-3].replace("/", "."): p for p in files}
    edges: dict[str, set[str]] = {}
    for rel in files:
        _, imports = _check_file_m_mod(rel, base_revision, violations, monolith_deltas)
        edges[rel[:-3].replace("/", ".")] = imports & mod_map.keys()
    for cyc in _tarjan_cycles(set(mod_map), edges):
        violations["M-MOD-I5"].append("cycle:" + "->".join(cyc))
    return _mmod_report(base_revision, len(files), monolith_deltas, violations)
