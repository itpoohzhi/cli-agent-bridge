"""AST/graph/state оракул LOCAL-pt-at-error: постоянные инварианты и явный исторический scope; без импорта продукта."""
from __future__ import annotations
import argparse
from collections.abc import Iterable, Mapping, Sequence
import ast
import copy
from graphlib import CycleError, TopologicalSorter
import json
from pathlib import Path
import pytest
import shutil
import subprocess
import sys
from typing import cast
Fn = ast.FunctionDef | ast.AsyncFunctionDef
Result = dict[str, str | int]
BASE = "a8e6e508d0a398625bc557f2e16f155a0c1ab171"
BRIDGE, RUNNER = "bridges/agy-bridge/server.py", "bridges/agy-bridge/agy_runtime/sse_body_runner.py"
CORE = ("core/turn_outcome_policy.py", "core/stream_interruption_recovery.py", "core/turn_finalization.py")
STAGES = (("W0", ("tests/test_causal_turn_recovery_flow.py", "tests/test_causal_recovery_architecture.py")),
          ("W1-A", (CORE[0], "tests/test_causal_turn_recovery.py")), ("W1-B", (CORE[1],)), ("W1-C", (CORE[2],)),
          ("W2", (BRIDGE, RUNNER)), ("W3", ("tests/test_route_health_policy.py", "core/route_health_policy.py")))
NEW = frozenset((CORE[0], CORE[2], *STAGES[0][1], "tests/test_causal_turn_recovery.py"))
RHP = "core/route_health_policy.py"
OWNED = NEW | {CORE[1]}
INTEGRATION = ("main", "master", "dev")
PURE = frozenset((*CORE[:2], RHP))
LIBS = frozenset(("__future__", "dataclasses", "hashlib", "re", "typing", "collections.abc"))
RHP_LIBS = frozenset(("decimal", "enum", "html", "math", "core.url_secret_redaction"))
EXPECTED = """self._finish_done(
    run, DoneRequest(payload, result_ev, (result_error, cleared_error)),
    DonePorts(state, add_content, deliver, lambda: gone[0], turn_complete),
)"""
def git(root: Path, *args: str) -> str:
    """Прочитать Git без изменения индекса."""
    return subprocess.check_output(("git", "-C", str(root), *args), text=True)
def ok(root: Path, *args: str) -> bool:
    """Вернуть успех Git-команды без исключения."""
    command = ("git", "-C", str(root), *args)
    return subprocess.run(command, capture_output=True, check=False).returncode == 0
def source(root: Path, rel: str, base: str = "") -> str:
    """Прочитать текущий модуль либо его версию в `base`."""
    if base:
        return "" if rel in NEW else git(root, "show", base + ":" + rel)
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
    branches = [n for n in ast.walk(node) if isinstance(n, ast.If) and dump(n.test) == dump(test)]
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
    assert len(body) == 1 and isinstance(body[0], ast.Return) and body[0].value is not None
    assert dump(body[0].value) == dump(ast.parse(EXPECTED, mode="eval").body)
    assert end(body[0]) - body[0].lineno + 1 <= 5
    assert end(node) - node.lineno + 1 <= end(old) - old.lineno + 1
def bounds(rel: str, name: str, node: Fn) -> None:
    """Проверить физические строки и все виды параметров."""
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    args = node.args
    count = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs) + bool(args.vararg) + bool(args.kwarg)
    assert end(node) - start + 1 <= 50, (rel, name, "lines")
    assert count <= 5, (rel, name, "parameters")
def mutable(node: ast.expr | None) -> bool:
    """Распознать синтаксические mutable-конструкторы состояния."""
    ctor = isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("list", "dict", "set", "defaultdict")
    return ctor or isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp))
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
        own = any(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self" for t in targets)
        assert not (own and mutable(node.value)), "new mutable self collection"
    endings = ("Request", "Ports", "Snapshot", "Policy", "Decision", "Facts", "Identity", "Input", "Config")
    records = [n for n in tree.body if isinstance(n, ast.ClassDef) and dump(n) not in baseline and n.name.endswith(endings)]
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
        deps = {"core.turn_outcome_policy", RHP[:-3].replace("/", ".")} | (RHP_LIBS if rel == RHP else frozenset[str]()) | ({"core.function_call_recovery"} if rel == CORE[1] else set())
        assert names <= LIBS | deps, (rel, names)
    else:
        allowed = ({"__future__", "json", "threading", "typing", "agy_runtime.midstream_resilience", "agy_runtime.sse_stream_helpers",
                    "core.route_health_policy", "core.stream_resilience_policy", "core.stream_resilience_runtime", "core.agy_capacity_guard", "core.usage_wire"} if rel == RUNNER else
                   LIBS | {"argparse", "json", "math", "os", "pathlib", "time", "core.runtime_env", "core.stream_interruption_recovery", "core.turn_outcome_policy"})
        assert names <= allowed, (rel, names)
    return names
def acyclic(graph: Mapping[str, Iterable[str]]) -> None:
    """Проверить DAG новых зависимостей."""
    try:
        _ = tuple(TopologicalSorter({k: set(v) for k, v in graph.items()}).static_order())
    except CycleError as error:
        raise AssertionError(("cycle", error.args[1])) from error
def selected(stage: str) -> tuple[str, ...]:
    """Получить накопительный scope без фиктивных будущих файлов."""
    if stage == "BASELINE":
        return (CORE[1], BRIDGE)
    names = [name for name, _ in STAGES]
    assert stage in names, stage
    return tuple(dict.fromkeys(p for _, ps in STAGES[:names.index(stage) + 1] for p in ps))
def protected(root: Path, base: str) -> Result:
    """Сохранить telemetry guard и его scope с актуальным baseline под лимитом."""
    tree = ast.parse(source(root, "tests/test_request_telemetry.py"))
    pairs = [n for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
             and n.targets[0].id in ("MODULES", "TEST_FILES")]
    paths = tuple(p for n in pairs for p in cast(Iterable[str], ast.literal_eval(n.value)))
    paths += ("server.py", "core/runtime_env.py", "core/activity_window.py",
              "core/passthrough_sliding_window.py", "adapters/passthrough_adapter.py")
    for path in paths:
        assert source(root, path) == source(root, path, base), ("protected", path)
    assert len(source(root, "server.py").splitlines()) == 7993
    return {"existing_telemetry_guard": "PASS_UNDER_LIMIT", "actual": 7993, "limit": 8801}
def scope_guard(root: Path, paths: Sequence[str], base: str = BASE) -> None:
    """Учесть tracked, untracked и ignored исходники диапазона `base`..рабочее дерево."""
    changed = git(root, "diff", "--name-only", base).splitlines()
    changed += git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    changed += git(root, "ls-files", "--others", "--ignored", "--exclude-standard").splitlines()
    relevant = [p for p in changed if p.endswith(".py") and not p.startswith(".ai-team/")
                and not any(x in Path(p).parts for x in (".venv", "__pycache__", ".pytest_cache"))]
    assert set(relevant) <= set(paths), ("outside wave scope", set(relevant) - set(paths))
def history(root: Path, scope: str, base: str = BASE) -> str:
    """Статус исторического proof диапазона фичи; недоступность не равна PASS."""
    if scope == "off":
        return "SKIPPED_BY_REQUEST"
    if not ok(root, "cat-file", "-e", base + "^{commit}"):
        assert scope != "strict", ("baseline unavailable", base)
        return "HISTORICAL_SCOPE_UNAVAILABLE"
    head = git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    merged = head in INTEGRATION or any(ok(root, "merge-base", "--is-ancestor", "HEAD", "origin/" + b) for b in INTEGRATION)
    clean = not git(root, "status", "--porcelain").strip()
    return "SKIPPED_POST_MERGE_MAIN" if scope == "auto" and merged and clean else "STRICT"
def lint_functions(nodes: list[ast.stmt]) -> None:
    """Проверить C901/PLR0913 только на новых/изменённых функциях."""
    if not nodes:
        return
    program = ast.unparse(ast.Module(body=nodes, type_ignores=[]))
    command = [sys.executable, "-m", "ruff", "check", "--no-cache",
               "--isolated", "--select", "C901,PLR0913",
               "--config", "lint.mccabe.max-complexity=10",
               "--config", "lint.pylint.max-args=5", "-"]
    result = subprocess.run(command, input=program, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
def fresh_nodes(rel: str, old: ast.Module, tree: ast.Module) -> list[ast.stmt]:
    """Проверить границы функций, изменённых относительно `old`."""
    before, after = functions(old), functions(tree)
    nodes: list[ast.stmt] = []
    for name, node in after.items():
        if name in before and dump(before[name]) == dump(node):
            continue
        if rel == BRIDGE and name == "Handler._execute":
            delegation(before[name], node)
        else:
            bounds(rel, name, node)
            nodes.append(node)
    return nodes
def inspect(root: Path, rel: str, ref: str) -> tuple[ast.Module, list[ast.stmt]]:
    """Постоянные проверки файла; сравнение с baseline — при доступном `ref`."""
    text = source(root, rel)
    assert len(text.splitlines()) <= (8483 if rel == BRIDGE else 250 if rel == RUNNER else 300), rel
    tree = ast.parse(text)
    old_text = source(root, rel, ref) if ref else ("" if rel in OWNED else None)
    if old_text is None:
        return tree, []
    old = ast.parse(old_text)
    state_guard(old, tree)
    return tree, fresh_nodes(rel, old, tree)
def check(root: Path, stage: str, scope: str = "auto", base: str = BASE) -> Result:
    """Постоянные инварианты всегда; исторический diff-scope только при доступном proof."""
    status = history(root, scope, base)
    ref = base if status == "STRICT" else ""
    paths = selected(stage)
    graph: dict[str, set[str]] = {}
    nodes: list[ast.stmt] = []
    if ref:
        scope_guard(root, paths, ref)
    for rel in paths:
        tree, fresh = inspect(root, rel, ref)
        nodes += fresh
        if rel in (*CORE, RUNNER):
            graph["agy_runtime.sse_body_runner" if rel == RUNNER else rel[:-3].replace("/", ".")] = imports(rel, tree)
        if rel == BRIDGE and stage in ("W2", "W3"):
            required = {"Handler._finish_done", "Handler._snapshot_done", "_ToolTurn.recovery_snapshot"}
            assert functions(tree).keys() >= required, "missing bridge helpers"
    _ = imports(RHP, ast.parse(source(root, RHP)))
    lint_functions(nodes)
    acyclic(graph)
    return {"historical_scope": status} | (protected(root, ref) if ref else {})
def _commit(repo: Path, name: str, text: str = "") -> str:
    """Создать коммит во временном репозитории и вернуть его SHA."""
    _ = (repo / name).write_text(text, encoding="utf-8")
    for args in (("add", "-A"), ("commit", "-qm", name)):
        _ = git(repo, "-c", "user.name=t", "-c", "user.email=t@t", *args)
    return git(repo, "rev-parse", "HEAD").strip()
def test_historical_scope_is_explicit(tmp_path: Path) -> None:
    """Диапазон фичи, нарушения, post-merge main и shallow clone различаются явно."""
    repo, allowed, shallow = tmp_path / "repo", ("ok.py",), tmp_path / "shallow"
    _ = git(tmp_path, "init", "-q", "-b", "main", "repo")
    base = _commit(repo, ".gitignore", "hidden.py\n")
    _ = git(repo, "checkout", "-q", "-b", "feature")
    _ = _commit(repo, "ok.py")
    scope_guard(repo, allowed, base)
    assert history(repo, "auto", base) == "STRICT"
    for stray in ("evil.py", "hidden.py"):
        _ = (repo / stray).write_text("", encoding="utf-8")
        with pytest.raises(AssertionError):
            scope_guard(repo, allowed, base)
        (repo / stray).unlink()
    _ = git(repo, "checkout", "-q", "main")
    _ = git(repo, "merge", "-q", "feature")
    _ = _commit(repo, "unrelated.py")
    assert (history(repo, "auto", base), history(repo, "strict", base)) == ("SKIPPED_POST_MERGE_MAIN", "STRICT")
    with pytest.raises(AssertionError):
        scope_guard(repo, allowed, base)
    _ = git(tmp_path, "clone", "-q", "--depth", "1", repo.as_uri(), "shallow")
    assert history(shallow, "auto", base) == "HISTORICAL_SCOPE_UNAVAILABLE"
    with pytest.raises(AssertionError):
        _ = history(shallow, "strict", base)
def test_permanent_invariants_hold_without_history(tmp_path: Path) -> None:
    """Без baseline AST/purity/line-count обязательны и по-прежнему ловят нарушения."""
    for rel in (*selected("W1-B"), RHP):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy(Path(__file__).resolve().parents[1] / rel, tmp_path / rel)
    assert check(tmp_path, "W1-B", base="0" * 40)["historical_scope"] == "HISTORICAL_SCOPE_UNAVAILABLE"
    target = tmp_path / CORE[1]
    good = target.read_text(encoding="utf-8")
    for bad in ("def long_one() -> None:\n" + "    pass\n" * 51, "import os\n", "\n" * 301):
        _ = target.write_text(good + bad, encoding="utf-8")
        with pytest.raises(AssertionError):
            _ = check(tmp_path, "W1-B", base="0" * 40)
class Args(argparse.Namespace):
    """Типизированные аргументы CLI."""
    root: Path = Path()
    stage: str = "W3"
    phase: str = "code"
    scope: str = "auto"
    base: str = BASE
def main() -> None:
    """CLI без конфликтов shell-кавычек."""
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--root", type=Path, required=True)
    _ = parser.add_argument("--stage", default="W3")
    _ = parser.add_argument("--phase", choices=("code",), default="code")
    _ = parser.add_argument("--scope", choices=("auto", "strict", "off"), default="auto")
    _ = parser.add_argument("--base", default=BASE)
    args = parser.parse_args(namespace=Args())
    result = check(args.root, args.stage, args.scope, args.base)
    verdict = "PASS" if result["historical_scope"] == "STRICT" else "PASS_PERMANENT_ONLY"
    print(json.dumps({"oracle": verdict, "phase": args.phase, "stage": args.stage, "baseline_disposition": result}, ensure_ascii=False))
if __name__ == "__main__":
    main()
