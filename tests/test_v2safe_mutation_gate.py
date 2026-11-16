"""VER-016: AST-мутации только disposable-копий; crash/timeout никогда не kill."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
OPPOSITES = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.LtE: ast.Gt,
             ast.Gt: ast.LtE, ast.GtE: ast.Lt, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
             ast.In: ast.NotIn, ast.NotIn: ast.In}
STATUSES = {"ok": "error", "success": "failure", "allowed": "denied", "ALIVE": "DEAD",
            "UNKNOWN": "ALIVE", "DEAD": "ALIVE", "PASS": "FAIL", "FAIL": "PASS"}
RUNNER = """import json, os, signal, subprocess, sys
command, limit = json.loads(sys.argv[1]), float(sys.argv[2])
p = subprocess.Popen(command, start_new_session=True, env=json.loads(sys.argv[3]))
try:
    rc = p.wait(timeout=limit)
except subprocess.TimeoutExpired:
    os.killpg(p.pid, signal.SIGKILL)
    p.wait()
    print('V2SAFE_TIMEOUT', flush=True)
    sys.exit(124)
finally:
    try: os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError: pass
print('V2SAFE_RC=' + str(rc), flush=True)
sys.exit(rc if rc >= 0 else 128 - rc)
"""


@dataclass(frozen=True)
class MutationOptions:
    source_root: Path | None = None
    timeout_s: float = field(default_factory=lambda: float(os.environ.get("V2SAFE_MUTATION_TIMEOUT_S", "10")))
    guard: bool = True
    env: dict[str, str] = field(default_factory=dict)
    critical_lines: frozenset[int] | None = None


@dataclass
class MutationReport:
    sampled: int = 0
    killed: int = 0
    surviving_critical: int = 0
    outcomes: list[str] = field(default_factory=list)
    source_sha256: str = ""

    @property
    def kill_ratio(self) -> float:
        return self.killed / self.sampled if self.sampled else 0.0

    @property
    def passed(self) -> bool:
        return (self.sampled > 0 and self.kill_ratio >= 0.85 and self.surviving_critical == 0
                and not set(self.outcomes) & {"not_killed_crash", "timeout", "environment_error"})


def _replacements(node: ast.AST, parent: ast.AST | None) -> list[ast.AST]:
    if isinstance(node, ast.Compare):
        variants = []
        for index, op in enumerate(node.ops):
            replacement = copy.deepcopy(node)
            replacement.ops[index] = OPPOSITES[type(op)]()
            variants.append(replacement)
        return variants
    if isinstance(node, ast.BoolOp):
        return [ast.BoolOp(op=ast.Or() if isinstance(node.op, ast.And) else ast.And(), values=node.values)]
    if isinstance(node, ast.UnaryOp):
        opposites = {ast.USub: ast.UAdd, ast.UAdd: ast.USub}
        return [ast.UnaryOp(op=opposites[type(node.op)](), operand=node.operand)] if type(node.op) in opposites else [node.operand]
    if isinstance(node, ast.Constant):
        return _constant_replacements(node, parent)
    return []


def _constant_replacements(node: ast.Constant, parent: ast.AST | None) -> list[ast.AST]:
    value = node.value
    if isinstance(parent, ast.Return) and isinstance(value, bool):
        return [ast.Constant(value=not value)]
    if isinstance(parent, ast.Return) and isinstance(value, str) and value in STATUSES:
        return [ast.Constant(value=STATUSES[value])]
    if isinstance(parent, (ast.Compare, ast.Return)) and isinstance(value, (int, float)) and not isinstance(value, bool):
        return [ast.Constant(value=value + delta) for delta in (-1, 1)]
    return []


def ast_mutants(source: str) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    variants: list[tuple[int, str]] = []
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for index, node in enumerate(ast.walk(tree)):
        for replacement in _replacements(node, parents.get(node)):
            mutant = copy.deepcopy(tree)
            _replace_node(mutant, list(ast.walk(mutant))[index], replacement)
            variants.append((int(getattr(node, "lineno")), ast.unparse(ast.fix_missing_locations(mutant)) + "\n"))
    return list(dict.fromkeys(variants))


def _replace_node(tree: ast.AST, selected: ast.AST, replacement: ast.AST) -> None:
    for parent in ast.walk(tree):
        for name, value in ast.iter_fields(parent):
            if value is selected:
                setattr(parent, name, replacement)
            elif isinstance(value, list):
                setattr(parent, name, [replacement if item is selected else item for item in value])


def _thin_shape(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if len(node.body) != 1 or not isinstance(node.body[0], ast.Return):
        return False
    value = node.body[0].value
    allowed = (ast.Call, ast.Name, ast.Attribute, ast.Load, ast.Constant, ast.keyword)
    return (isinstance(value, ast.Call) and sum(isinstance(n, ast.Call) for n in ast.walk(value)) == 1
            and all(isinstance(n, allowed) for n in ast.walk(value)))


def thin_delegation_spy_verified(source: str, evidence: dict[str, object]) -> bool:
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(nodes) != 1:
        return False
    node = nodes[0]
    lines = (node.end_lineno or node.lineno) - node.lineno
    return (lines <= 5 and _thin_shape(node)
            and all(evidence.get(key) is True for key in ("arguments", "result", "error", "delegated_mutation"))
            and evidence.get("source_sha256") == hashlib.sha256(source.encode()).hexdigest())


def _ignore(directory: str, names: list[str]) -> list[str]:
    excluded = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "logs", "receipts"}
    return [name for name in names if name in excluded or name.startswith(".env")
            or (Path(directory) / name).is_symlink()]


def _isolated_env(root: Path, extra: dict[str, str]) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "LANG", "LC_ALL"}}
    env.update(extra)
    for name in ("home", "tmp", "state"):
        (root / name).mkdir(exist_ok=True)
    env.update(HOME=str(root / "home"), TMPDIR=str(root / "tmp"), PYTHONPATH=str(root / "tree"),
               PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", V2SAFE_RUN_FULL_MUTATION="0",
               V2SAFE_RUN_FULL_BASELINE_GATE="0")
    for name in ("MODEL_PENALTIES", "DYNAMIC_CONFIG", "TELEMETRY_DB", "MODEL_NOTES"):
        env["BRIDGE_" + name + "_PATH"] = str(root / "state" / (name.lower() + ".json"))
    return env


def _outcome(rc: int, output: str) -> str:
    codes = [int(code) for code in re.findall(r"^V2SAFE_RC=(-?\d+)$", output, re.M)]
    if "V2SAFE_TIMEOUT" in output:
        return "timeout"
    raw = codes[-1] if codes else rc
    if raw < 0 or raw >= 128 or "[crash-guard] КРЭШ:" in output:
        return "not_killed_crash"
    if not codes:
        return "environment_error"
    if (rc, raw) not in {(0, 0), (1, 1)}:
        return "environment_error"
    return "survived" if raw == 0 else "killed"


def _execute(command: list[str], root: Path, options: MutationOptions) -> str:
    runner = root / "runner.py"
    runner.write_text(RUNNER)
    env = _isolated_env(root, options.env)
    invocation = [sys.executable, str(runner), json.dumps(command), str(options.timeout_s), json.dumps(env)]
    guard = shutil.which("run-guarded")
    if options.guard and guard:
        invocation = [guard, "--settle", "0", "--", *invocation]
    # Обёртка run-guarded ищет свой Python через HOME; целевой ребёнок получает отдельный env.
    with subprocess.Popen(invocation, cwd=root / "tree", env={**env, "HOME": str(Path.home())},
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True) as child:
        try:
            output, _ = child.communicate(timeout=min(59.0, options.timeout_s + 5))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
            return "timeout"
    return _outcome(child.returncode, output)


def _sandbox_arg(argument: str, root: Path, tree: Path) -> str:
    prefix, sep, value = argument.partition("=") if argument.startswith("--") else ("", "", argument)
    path, colon, selector = value.partition("::")
    candidate = Path(path)
    if not candidate.is_absolute():
        return argument
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        return argument
    return prefix + sep + str(tree / resolved.relative_to(root)) + colon + selector


def run_ast_mutation_suite(target_path: Path, test_cmd: Sequence[str], tmp_path: Path,
                           options: MutationOptions | None = None) -> MutationReport:
    options = options or MutationOptions()
    assert 0 < options.timeout_s < 54, "child timeout must remain <60s including guard"
    target, root = target_path.resolve(), (options.source_root or target_path.parent).resolve()
    assert not tmp_path.resolve().is_relative_to(root), "sandbox must be outside live source"
    assert not target_path.is_symlink(), "symlink target forbidden"
    relative, original = target.relative_to(root), target.read_bytes()
    sandbox = tmp_path / "mutation"
    sandbox.mkdir(parents=True)
    shutil.copytree(root, sandbox / "tree", ignore=_ignore)
    command = [_sandbox_arg(arg, root, sandbox / "tree") for arg in test_cmd]
    report = MutationReport(source_sha256=hashlib.sha256(original).hexdigest())
    try:
        assert _execute(command, sandbox, options) == "survived", "unmutated suite must pass"
        for line, source in ast_mutants(original.decode()):
            (sandbox / "tree" / relative).write_text(source)
            outcome = _execute(command, sandbox, options)
            report.sampled += 1
            report.killed += outcome == "killed"
            report.surviving_critical += outcome != "killed" and (options.critical_lines is None or line in options.critical_lines)
            report.outcomes.append(outcome)
    finally:
        assert target.read_bytes() == original, "live tree modified"
    return report


def _fixture(tmp_path: Path, body: str) -> tuple[Path, list[str], Path]:
    root = tmp_path / "source"
    root.mkdir()
    target = root / "target.py"
    target.write_text("def allowed(x):\n    return x >= 2\n")
    (root / "suite.py").write_text("from target import allowed\n" + body)
    # Ненормализованный путь обязан запускать копию, а не live suite.
    return target, [sys.executable, "-B", str(root / ".." / "source" / "suite.py")], tmp_path / "isolated"


def test_real_mutations_strong_and_weak_suites(tmp_path: Path) -> None:
    target, command, isolated = _fixture(tmp_path, "assert [allowed(x) for x in (1,2,3)] == [False,True,True]\n")
    strong = run_ast_mutation_suite(target, command, isolated)
    assert strong.sampled == 3 and strong.kill_ratio == 1 and strong.passed
    (target.parent / "suite.py").write_text("from target import allowed\nassert isinstance(allowed(2), bool)\n")
    weak = run_ast_mutation_suite(target, command, tmp_path / "weak")
    assert weak.sampled > 0 and weak.kill_ratio == 0 and not weak.passed and weak.surviving_critical > 0


@pytest.mark.parametrize("mode,expected", [("crash", "not_killed_crash"), ("timeout", "timeout")])
@pytest.mark.parametrize("guard", [False, True])
def test_crash_and_timeout_are_not_kills(tmp_path: Path, mode: str, expected: str, guard: bool) -> None:
    # rc139 — shell-encoding SIGSEGV; реальный segfault испортил бы внешний crash-guard.
    action = "import os; os._exit(139)" if mode == "crash" else "import time; time.sleep(2)"
    body = "if [allowed(x) for x in (1,2,3)] != [False,True,True]:\n    " + action + "\n"
    target, command, isolated = _fixture(tmp_path, body)
    report = run_ast_mutation_suite(target, command, isolated, MutationOptions(timeout_s=0.5, guard=guard))
    assert report.sampled == 3 and set(report.outcomes) == {expected}
    assert report.killed == 0 and report.kill_ratio == 0 and not report.passed


def test_operator_families_and_thin_delegation() -> None:
    source = "def f(x):\n    return x and not x\n"
    assert len(ast_mutants(source)) == 2
    assert ast_mutants("def f():\n    return True\n")
    assert ast_mutants("def f():\n    return 'ok'\n")
    thin = "def f(x):\n    return delegate(x)\n"
    evidence = dict.fromkeys(("arguments", "result", "error", "delegated_mutation"), True)
    proof = {**evidence, "source_sha256": hashlib.sha256(thin.encode()).hexdigest()}
    assert thin_delegation_spy_verified(thin, proof)
    for source in ("def f(x):\n    return delegate(x) if x else None\n",
                   "def f(x):\n    return delegate(x > 1)\n", "def f(x):\n" + "    # line\n" * 5 + "    return delegate(x)\n"):
        assert not thin_delegation_spy_verified(source, {**proof, "source_sha256": hashlib.sha256(source.encode()).hexdigest()})
    assert not thin_delegation_spy_verified(thin, {})
    assert not MutationReport().passed
    assert MutationReport(sampled=20, killed=17).passed
    assert not MutationReport(sampled=20, killed=16).passed
    assert not MutationReport(sampled=20, killed=17, surviving_critical=1).passed
    assert _outcome(3, "V2SAFE_RC=-11\n") == "not_killed_crash"


def test_full_v2safe_mutation_opt_in(tmp_path: Path) -> None:
    if os.environ.get("V2SAFE_RUN_FULL_MUTATION") != "1":
        return
    from tests.test_v2safe_structure_gates import audit_paths, load_packet
    packet = load_packet()
    assert "VER-016" in {item["id"] for item in packet["verification_surface"]}
    modules = [p for p in audit_paths() if p.parent == ROOT / "core"]
    assert modules, "full mutation cannot PASS without executed-diff product modules"
    suites = json.loads(os.environ.get("WAVE_TESTS_JSON", "{}"))
    for index, target in enumerate(modules):
        relative = str(target.relative_to(ROOT))
        assert relative in suites and suites[relative], f"missing frozen test command: {relative}"
        report = run_ast_mutation_suite(target, suites[relative], tmp_path / str(index), MutationOptions(source_root=ROOT))
        assert report.passed, (relative, report)
