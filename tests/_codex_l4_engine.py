"""AST diff-mutation and isolated disposable runner engine for Codex L4 gate."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import os
import re
import shutil
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_STRIP_ENV_PREFIXES = ("BRIDGE_", "AGY_", "OPENAI_", "CODEX_")
_SUPPORT_TESTS = ("conftest.py",)


@dataclass(frozen=True, slots=True)
class Mutant:
    """One isolated source mutation with killer test suite and criticality flag."""

    name: str
    path: str
    source: str
    killers: tuple[str, ...]
    critical: bool
    kind: str


@dataclass(frozen=True, slots=True)
class L4Report:
    """Aggregated L4 mutation and sabotage verification outcome."""

    total: int
    killed: int
    survivors: tuple[str, ...]
    surviving_critical: tuple[str, ...]
    timeout_count: int
    generated: int
    invalid: int
    elapsed_s: float
    baseline_ok: bool
    state_leaks: int

    @property
    def kill_rate(self) -> float:
        return self.killed / self.total if self.total else 0.0

    @property
    def invalid_rate(self) -> float:
        return self.invalid / self.generated if self.generated else 0.0

    @property
    def passed(self) -> bool:
        return (
            self.baseline_ok
            and self.total > 0
            and self.kill_rate >= 0.85
            and not self.surviving_critical
            and self.timeout_count == 0
            and self.invalid_rate <= 0.10
            and self.elapsed_s <= 60.0
            and self.state_leaks == 0
        )


def pytest_command(args: Sequence[str]) -> list[str]:
    """Resolve pytest executable using sys.executable when pytest is installed there."""
    if importlib.util.find_spec("pytest") is not None:
        return [sys.executable, "-m", "pytest", *args]
    exe = shutil.which("pytest")
    return [exe, *args] if exe else [sys.executable, "-m", "pytest", *args]


def _kill_owned_pgid(pgid: int) -> None:
    if pgid <= 1 or pgid == os.getpgrp():
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return


def run_cmd_pgid(
    cmd: Sequence[str], cwd: Path, env: Mapping[str, str], timeout_s: float
) -> tuple[int, bool]:
    """Run command in its own process group with guaranteed PGID teardown in finally."""
    proc = subprocess.Popen(
        list(cmd),
        cwd=str(cwd),
        env=dict(env),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    pgid = proc.pid
    timed_out = False
    try:
        return proc.wait(timeout=timeout_s), False
    except subprocess.TimeoutExpired:
        timed_out = True
        return -1, True
    finally:
        if timed_out or proc.poll() is None:
            _kill_owned_pgid(pgid)
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            _kill_owned_pgid(pgid)
            proc.wait()


def tree_digest(root: Path = REPO) -> str:
    """SHA-256 fingerprint of product sources proving the worktree is never mutated."""
    digest = hashlib.sha256()
    files: list[Path] = [root / "fleet.json", root / "server.py"]
    for sub in ("core", "adapters", "scripts", "providers.d"):
        files.extend(p for p in (root / sub).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    for path in sorted(set(files)):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def build_disposable_copy(dst: Path, tests: Sequence[str]) -> None:
    """Create a disposable copy of product code and required tests inside tmp dir."""
    skip = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    for sub in ("core", "adapters", "scripts", "providers.d"):
        if (REPO / sub).is_dir():
            shutil.copytree(REPO / sub, dst / sub, ignore=skip)
    shutil.copy2(REPO / "fleet.json", dst / "fleet.json")
    (dst / "tests").mkdir(parents=True, exist_ok=True)
    helpers = tuple(p.name for p in (REPO / "tests").glob("_*.py"))
    for name in sorted({*_SUPPORT_TESTS, *helpers, *tests}):
        src = REPO / "tests" / name
        if src.is_file():
            shutil.copy2(src, dst / "tests" / name)


def changed_lines(base_revision: str, paths: Sequence[str]) -> dict[str, set[int]]:
    cmd = ["git", "-C", str(REPO), "diff", "-U0", base_revision, "--", *paths]
    out = subprocess.check_output(cmd, text=True, timeout=15.0)
    result: dict[str, set[int]] = {}
    current = ""
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("@@ ") and current:
            match = _HUNK_RE.match(line)
            if match:
                start = int(match.group(1))
                count = 1 if match.group(2) is None else int(match.group(2))
                if count > 0:
                    result.setdefault(current, set()).update(range(start, start + count))
    return result


def _flip_op(op: ast.cmpop) -> ast.cmpop | None:
    mapping: tuple[tuple[type[ast.cmpop], type[ast.cmpop]], ...] = (
        (ast.Eq, ast.NotEq),
        (ast.NotEq, ast.Eq),
        (ast.In, ast.NotIn),
        (ast.NotIn, ast.In),
        (ast.Gt, ast.LtE),
        (ast.Lt, ast.GtE),
    )
    for src_t, dst_t in mapping:
        if isinstance(op, src_t):
            return dst_t()
    return None


def _mutate_ast_site(tree: ast.Module, idx: int) -> bool:
    node = list(ast.walk(tree))[idx]
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        if (flipped := _flip_op(node.ops[0])) is not None:
            node.ops = [flipped]
            return True
    if isinstance(node, ast.BoolOp):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        return True
    return False


def _is_mutable_node(node: ast.AST) -> bool:
    if isinstance(node, ast.BoolOp):
        return True
    return isinstance(node, ast.Compare) and len(node.ops) == 1 and _flip_op(node.ops[0]) is not None


def ast_mutants_for_file(
    rel: str, lines: set[int], killers: tuple[str, ...], per_file: int
) -> tuple[list[Mutant], int, int]:
    src = (REPO / rel).read_text(encoding="utf-8")
    tree = ast.parse(src, filename=rel)
    sites = [(i, getattr(n, "lineno", 0)) for i, n in enumerate(ast.walk(tree)) if getattr(n, "lineno", 0) in lines and _is_mutable_node(n)]
    mutants: list[Mutant] = []
    generated = invalid = 0
    step = max(1, len(sites) // max(1, per_file))
    for site_idx, lineno in sites[::step][:per_file]:
        generated += 1
        cloned = copy.deepcopy(tree)
        if not _mutate_ast_site(cloned, site_idx):
            invalid += 1
            continue
        rendered = ast.unparse(cloned) + "\n"
        try:
            ast.parse(rendered, filename=rel)
        except SyntaxError:
            invalid += 1
            continue
        slug = rel.rsplit("/", 1)[-1].replace(".py", "")
        mutants.append(Mutant(f"ast-{slug}-L{lineno}", rel, rendered, killers, False, "ast_diff"))
    return mutants, generated, invalid


def run_pytest_in_copy(root: Path, tests: Sequence[str], timeout_s: float) -> tuple[int, bool]:
    iso = root / ".iso_home"
    iso.mkdir(mode=0o700, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(_STRIP_ENV_PREFIXES)}
    env.update(
        HOME=str(iso),
        CODEX_HOME=str(iso / ".codex"),
        XDG_CONFIG_HOME=str(iso / ".config"),
        XDG_DATA_HOME=str(iso / ".local" / "share"),
        XDG_CACHE_HOME=str(iso / ".cache"),
        XDG_STATE_HOME=str(iso / ".local" / "state"),
        PYTHONPATH=str(root),
        PYTHONDONTWRITEBYTECODE="1",
    )
    cmd = pytest_command([*(f"tests/{t}" for t in tests), "-x", "-q", "-p", "no:cacheprovider"])
    return run_cmd_pgid(cmd, root, env, timeout_s)


def eval_mutant(base: Path, mutant: Mutant, timeout_s: float) -> tuple[str, bool, bool]:
    work = base / mutant.name
    build_disposable_copy(work, mutant.killers)
    (work / mutant.path).write_text(mutant.source, encoding="utf-8")
    rc, timed_out = run_pytest_in_copy(work, mutant.killers, timeout_s)
    return mutant.name, (rc != 0 and not timed_out), timed_out
