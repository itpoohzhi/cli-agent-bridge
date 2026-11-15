"""AST/graph/state и expected-red оракул LOCAL-pt-at-error; без импорта продукта."""
from __future__ import annotations
import argparse
from collections.abc import Iterable, Mapping, Sequence
import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import cast
import xml.etree.ElementTree as ET

Fn = ast.FunctionDef | ast.AsyncFunctionDef
Result = dict[str, str | int]
BASE = "cc741edcb9e59d77e02a36790bd3c6e406dbdebb"
BRIDGE = "bridges/agy-bridge/server.py"
CORE = ("core/turn_outcome_policy.py", "core/stream_interruption_recovery.py",
        "core/turn_finalization.py")
STAGES = (("W0", ("tests/test_causal_turn_recovery_flow.py",
                  "tests/test_causal_recovery_architecture.py")),
          ("W1-A", (CORE[0], "tests/test_causal_turn_recovery.py")),
          ("W1-B", (CORE[1],)), ("W1-C", (CORE[2],)), ("W2", (BRIDGE,)),
          ("W3", ("tests/test_route_health_policy.py",)))
NEW = frozenset((CORE[0], CORE[2], "tests/test_causal_turn_recovery.py",
                 "tests/test_causal_turn_recovery_flow.py",
                 "tests/test_causal_recovery_architecture.py"))
PURE = frozenset(CORE[:2])
LIBS = frozenset(("__future__", "dataclasses", "hashlib", "re", "typing",
                  "collections.abc"))
EXPECTED = """self._finish_done(
    run, DoneRequest(payload, result_ev, (result_error, cleared_error)),
    DonePorts(state, add_content, deliver, lambda: gone[0], turn_complete),
)"""

def git(root: Path, *args: str) -> str:
    """Прочитать Git без изменения индекса."""
    return subprocess.check_output(("git", "-C", str(root), *args), text=True)

def source(root: Path, rel: str, base: bool = False) -> str:
    """Прочитать текущий либо исходный модуль."""
    if base:
        return "" if rel in NEW else git(root, "show", BASE + ":" + rel)
    return (root / rel).read_text(encoding="utf-8")

def functions(tree: ast.Module) -> dict[str, Fn]:
    """Собрать функции с квалифицированными именами."""
    result: dict[str, Fn] = {}
    def visit(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                if not isinstance(node, ast.ClassDef):
                    result[name] = node
                visit(node.body, name + ".")
    visit(tree.body)
    return result

def dump(node: ast.AST) -> str:
    """Сравнить синтаксис без смещений строк."""
    return ast.dump(node, include_attributes=False)

def done_branch(node: ast.AST) -> ast.If:
    """Найти единственную транспортную ветвь done."""
    test = ast.parse("kind == 'done'", mode="eval").body
    branches = [n for n in ast.walk(node)
                if isinstance(n, ast.If) and dump(n.test) == dump(test)]
    assert len(branches) == 1, "ambiguous done branch"
    return branches[0]

def shell(node: Fn) -> str:
    """Скрыть только done body для проверки legacy-shell."""
    node = copy.deepcopy(node)
    done_branch(node).body = [ast.Pass()]
    return dump(node)

def end(node: ast.stmt) -> int:
    """Вернуть конечную строку узла."""
    assert node.end_lineno is not None
    return node.end_lineno

def delegation(old: Fn, node: Fn) -> None:
    """Разрешить только точное минимальное делегирование в _execute."""
    assert shell(old) == shell(node), "legacy shell/signature changed"
    body = done_branch(node).body
    assert len(body) == 1 and isinstance(body[0], ast.Return)
    assert body[0].value is not None
    assert dump(body[0].value) == dump(ast.parse(EXPECTED, mode="eval").body)
    assert end(body[0]) - body[0].lineno + 1 <= 5
    assert end(node) - node.lineno + 1 <= end(old) - old.lineno + 1

def bounds(rel: str, name: str, node: Fn) -> None:
    """Проверить физические строки и все виды параметров."""
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    args = node.args
    count = (len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
             + int(args.vararg is not None) + int(args.kwarg is not None))
    assert end(node) - start + 1 <= 50, (rel, name, "lines")
    assert count <= 5, (rel, name, "parameters")

def mutable(node: ast.expr | None) -> bool:
    """Распознать синтаксические mutable-конструкторы состояния."""
    literal = isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp,
                                ast.DictComp, ast.SetComp))
    ctor = isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in (
        "list", "dict", "set", "defaultdict")
    return literal or ctor

def frozen_record(node: ast.ClassDef) -> bool:
    """Проверить frozen=True у нового/изменённого DTO."""
    return any(isinstance(d, ast.Call) and any(
        k.arg == "frozen" and dump(k.value) == dump(ast.parse("True", mode="eval").body)
        for k in d.keywords) for d in node.decorator_list)

def state_guard(old: ast.AST, tree: ast.Module) -> None:
    """Запретить новые global mutable и новые self-collection state."""
    baseline = {dump(n) for n in ast.walk(old)}
    globals_now = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
    assert not any(mutable(n.value) and dump(n) not in baseline for n in globals_now)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or dump(node) in baseline:
            continue
        targets: Sequence[ast.expr] = node.targets if isinstance(node, ast.Assign) else [node.target]
        own = any(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                  and t.value.id == "self" for t in targets)
        assert not (own and mutable(node.value)), "new mutable self collection"
    endings = ("Request", "Ports", "Snapshot", "Policy", "Decision", "Facts", "Identity", "Input", "Config")
    records = [n for n in tree.body if isinstance(n, ast.ClassDef)
               and dump(n) not in baseline and n.name.endswith(endings)]
    assert all(frozen_record(n) for n in records), "non-frozen DTO"

def imports(rel: str, tree: ast.AST) -> set[str]:
    """Проверить разрешённые импорты и отсутствие dynamic import."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(n.name for n in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import requires explicit mapping"
            names.add(node.module or "")
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else "")
            assert name not in ("__import__", "import_module", "eval", "exec"), name
            if rel in PURE:
                assert name not in ("open", "read_text", "read_bytes", "getenv"), name
    if rel in PURE:
        assert names <= LIBS | {"core.turn_outcome_policy", "core.route_health_policy"}, (rel, names)
    else:
        allowed = LIBS | {"argparse", "json", "math", "os", "pathlib", "time",
                          "core.runtime_env", "core.stream_interruption_recovery",
                          "core.turn_outcome_policy"}
        assert names <= allowed, (rel, names)
    return names

def acyclic(graph: Mapping[str, Iterable[str]]) -> None:
    """Проверить DAG новых зависимостей."""
    visited: set[str] = set()
    active: set[str] = set()
    def visit(name: str) -> None:
        assert name not in active, ("cycle", name)
        if name in visited:
            return
        active.add(name)
        for nxt in graph.get(name, ()):
            if nxt in graph:
                visit(nxt)
        active.remove(name)
        visited.add(name)
    for name in graph:
        visit(name)

def selected(stage: str) -> tuple[str, ...]:
    """Получить накопительный scope без фиктивных будущих файлов."""
    if stage == "BASELINE":
        return (CORE[1], BRIDGE)
    result: list[str] = []
    for name, paths in STAGES:
        result.extend(paths)
        if name == stage:
            return tuple(dict.fromkeys(result))
    raise AssertionError(stage)

def protected(root: Path) -> Result:
    """Сохранить telemetry guard и его scope без ослабления baseline failure."""
    tree = ast.parse(source(root, "tests/test_request_telemetry.py"))
    pairs = [n for n in tree.body if isinstance(n, ast.Assign)
             and isinstance(n.targets[0], ast.Name)
             and n.targets[0].id in ("MODULES", "TEST_FILES")]
    paths = tuple(p for n in pairs for p in cast(Iterable[str], ast.literal_eval(n.value)))
    paths += ("server.py", "core/runtime_env.py", "core/activity_window.py",
              "core/passthrough_sliding_window.py", "adapters/passthrough_adapter.py")
    for path in paths:
        assert source(root, path) == source(root, path, True), ("protected", path)
    assert len(source(root, "server.py").splitlines()) == 8932
    return {"existing_telemetry_guard": "FAIL_UNCHANGED", "actual": 8932, "limit": 8801}

def scope_guard(root: Path, paths: Sequence[str]) -> None:
    """Учесть tracked, untracked и ignored исходники."""
    changed = git(root, "diff", "--name-only", BASE).splitlines()
    changed += git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    changed += git(root, "ls-files", "--others", "--ignored", "--exclude-standard").splitlines()
    relevant = [p for p in changed if p.endswith(".py") and not p.startswith(".ai-team/")
                and not any(x in Path(p).parts for x in (".venv", "__pycache__", ".pytest_cache"))]
    assert set(relevant) <= set(paths), ("outside wave scope", set(relevant) - set(paths))

def lint_functions(nodes: list[ast.stmt]) -> None:
    """Проверить C901/PLR0913 только на новых/изменённых функциях."""
    if not nodes:
        return
    program = ast.unparse(ast.Module(body=nodes, type_ignores=[]))
    command = [str(Path(sys.executable).with_name("ruff")), "check", "--no-cache",
               "--isolated", "--select", "C901,PLR0913",
               "--config", "lint.mccabe.max-complexity=10",
               "--config", "lint.pylint.max-args=5", "-"]
    result = subprocess.run(command, input=program, text=True, capture_output=True,
                            check=False)
    assert result.returncode == 0, result.stdout + result.stderr

def check(root: Path, stage: str) -> Result:
    """Выполнить code oracle без импорта продуктовых модулей."""
    paths = selected(stage)
    graph: dict[str, set[str]] = {}
    changed_nodes: list[ast.stmt] = []
    scope_guard(root, paths)
    for rel in paths:
        text, old_text = source(root, rel), source(root, rel, True)
        assert len(text.splitlines()) <= (8483 if rel == BRIDGE else 300), rel
        tree, old = ast.parse(text), ast.parse(old_text)
        state_guard(old, tree)
        before, after = functions(old), functions(tree)
        for name, node in after.items():
            if name in before and dump(before[name]) == dump(node):
                continue
            if rel == BRIDGE and name == "Handler._execute":
                delegation(before[name], node)
            else:
                bounds(rel, name, node)
                changed_nodes.append(node)
        if rel in CORE:
            graph[rel[:-3].replace("/", ".")] = imports(rel, tree)
        if rel == BRIDGE and stage in ("W2", "W3"):
            required = ("Handler._finish_done", "Handler._snapshot_done", "_ToolTurn.recovery_snapshot")
            assert all(name in after for name in required), "missing bridge helpers"
    lint_functions(changed_nodes)
    acyclic(graph)
    return protected(root)

def expected_red(root: Path, temp_root: Path) -> Result:
    """Принять только согласованные assertion failures W0."""
    names = ("test_replay_primary", "test_replay_sister", "test_recovered_terminal_has_no_sse_error")
    with tempfile.TemporaryDirectory(prefix="causal-red-", dir=temp_root) as folder:
        report = Path(folder) / "report.xml"
        command = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "--junitxml", str(report), "--basetemp", str(Path(folder) / "pytest"),
                   *("tests/test_causal_turn_recovery_flow.py::" + n for n in names)]
        result = subprocess.run(command, cwd=root, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                capture_output=True, text=True, check=False)
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        cases = ET.parse(report).findall(".//testcase")
        assert result.returncode == 1 and len(cases) == 3
        assert {c.attrib["name"] for c in cases} == set(names)
        assert all(c.find("error") is None and c.find("failure") is not None for c in cases)
        assert all("AssertionError" in (f.attrib.get("message", "") + (f.text or ""))
                   for c in cases if (f := c.find("failure")) is not None)
    return {"expected_red": "PASS", "failures": 3}

class Args(argparse.Namespace):
    """Типизированные аргументы CLI."""
    root: Path = Path()
    stage: str = "W3"
    phase: str = "code"
    temp_root: Path | None = None

def main() -> None:
    """CLI без конфликтов shell-кавычек."""
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--root", type=Path, required=True)
    _ = parser.add_argument("--stage", default="W3")
    _ = parser.add_argument("--phase", choices=("code", "expected-red"), default="code")
    _ = parser.add_argument("--temp-root", type=Path)
    args = parser.parse_args(namespace=Args())
    if args.phase == "expected-red":
        assert args.temp_root is not None, "--temp-root is required"
        result = expected_red(args.root, args.temp_root)
    else:
        result = check(args.root, args.stage)
    print(json.dumps({"oracle": "PASS", "phase": args.phase, "stage": args.stage,
                      "baseline_disposition": result}, ensure_ascii=False))

if __name__ == "__main__":
    main()
