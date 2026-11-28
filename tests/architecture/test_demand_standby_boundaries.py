"""AST-границы demand-driven standby pool (VER-008, VER-010, VER-011): владелец `_slots`, чистота FSM, бюджеты.

Проверки статические (ast.walk видит вложенные функции и `if TYPE_CHECKING`, чего не видит grep); без I/O кроме чтения исходников.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "core" / "stdio_resident"
AGY = ROOT / "bridges" / "agy-bridge" / "agy_runtime"
FSM, POOL = RES / "standby_pool_fsm.py", RES / "demand_standby_pool.py"
CODEX, CLAUDE = RES / "codex_standby_adapter.py", RES / "claude_standby_adapter.py"
NEW_MODULES = (FSM, POOL, CODEX, CLAUDE)
TOUCHED = (RES / "resident_runtime.py", AGY / "persistent_standby_pool.py", AGY / "persistent_worker_adapter.py",
           ROOT / "bridges" / "claude-p-bridge" / "server.py")
FSM_BANNED_IMPORTS = frozenset({"os", "subprocess", "threading", "time", "datetime", "signal", "tempfile", "pathlib",
                                "shutil", "socket", "demand_standby_pool"})
FSM_BANNED_CALLS = frozenset({"open", "print", "input"})
MUTATORS = frozenset({"pop", "popitem", "clear", "update", "setdefault", "append", "extend", "remove", "insert",
                      "add", "discard", "__setitem__", "__delitem__"})
LOC_BUDGET = {FSM: 250, POOL: 300, CODEX: 220, CLAUDE: 220, AGY / "persistent_standby_pool.py": 300,
              AGY / "persistent_worker_adapter.py": 300}
MAX_FUNC_LOC, MAX_ARGS, MAX_CC = 50, 5, 10


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(tree: ast.Module) -> list[str]:
    """Полные имена импортируемых модулей на любой глубине (вкл. функции и TYPE_CHECKING)."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = ("." * node.level) + (node.module or "")
            names.append(base)
            names.extend(f"{base}.{alias.name}" for alias in node.names)
    return names


def _is_slots_attr(node: ast.AST) -> bool:
    if isinstance(node, ast.Subscript):
        return _is_slots_attr(node.value)
    return isinstance(node, ast.Attribute) and node.attr == "_slots"


def _slots_mutations(tree: ast.Module) -> list[int]:
    """Номера строк записи/мутации `<expr>._slots` (присваивание, del, subscript-store, mutator-вызов)."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
            targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
            lines.extend(node.lineno for t in targets if _is_slots_attr(t))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in MUTATORS and _is_slots_attr(node.func.value):
                lines.append(node.lineno)
    return lines


def _slots_refs(tree: ast.Module) -> list[int]:
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "_slots"]


def _is_bridges(name: str) -> bool:
    return name.lstrip(".").split(".")[0] == "bridges"


def _own_nodes(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Узлы тела функции без вложенных def (они проверяются отдельно)."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(func.body)
    while stack:
        node = stack.pop()
        out.append(node)
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.extend(ast.iter_child_nodes(node))
    return out


def _complexity(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    branching = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.match_case, ast.IfExp)
    cc = 1 + sum(isinstance(n, branching) for n in _own_nodes(func))
    return cc + sum(isinstance(n, ast.comprehension) for n in _own_nodes(func))


def _arg_count(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    a = func.args
    names = [x.arg for x in (*a.posonlyargs, *a.args, *a.kwonlyargs)]
    names = [n for n in names if n not in ("self", "cls")]
    return len(names) + int(a.vararg is not None) + int(a.kwarg is not None)


def _functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _bridge_imports_in_core() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in sorted(RES.glob("*.py")):
        if found := [m for m in _imports(_tree(p)) if _is_bridges(m)]:
            out[p.name] = found
    return out


def _slots_offenders() -> tuple[dict[str, list[int]], list[str]]:
    writes = {p.name: m for p in (*NEW_MODULES, *TOUCHED) if p != POOL and (m := _slots_mutations(_tree(p)))}
    refs = [p.name for p in NEW_MODULES if p != POOL and _slots_refs(_tree(p))]
    return writes, refs


def test_state_owner_and_deps() -> None:
    """VER-010: `_slots` мутирует только DemandStandbyPool; core не знает bridges; адаптеры независимы."""
    assert _slots_mutations(_tree(POOL)), "владелец _slots не найден: проверка была бы пустой"
    writes, refs = _slots_offenders()
    assert writes == {}
    assert refs == []
    assert _bridge_imports_in_core() == {}
    assert [m for m in _imports(_tree(CODEX)) if m.endswith(CLAUDE.stem)] == []
    assert [m for m in _imports(_tree(CLAUDE)) if m.endswith(CODEX.stem)] == []


def test_fsm_zero_io_purity() -> None:
    """VER-008: FSM без I/O, часов, потоков и сигналов на любой глубине вложенности."""
    tree = _tree(FSM)
    banned = sorted(m for m in _imports(tree) if m.lstrip(".").split(".")[0] in FSM_BANNED_IMPORTS
                    or m.rsplit(".", 1)[-1] in FSM_BANNED_IMPORTS)
    assert banned == []
    calls = sorted(n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in FSM_BANNED_CALLS)
    assert calls == []
    env_access = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in ("environ", "getenv")]
    assert env_access == []


@pytest.mark.parametrize("path", list(LOC_BUDGET), ids=lambda p: p.name)
def test_file_and_function_budgets_loc(path: Path) -> None:
    """VER-011: бюджет строк файла (как `wc -l`)."""
    assert path.read_text(encoding="utf-8").count("\n") <= LOC_BUDGET[path]


@pytest.mark.parametrize("path", NEW_MODULES, ids=lambda p: p.name)
def test_file_and_function_budgets(path: Path) -> None:
    """VER-011: `from __future__ import annotations`, функции <= 50 LOC, <= 5 args, CC <= 10."""
    tree = _tree(path)
    future = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "__future__"]
    assert any(a.name == "annotations" for n in future for a in n.names)
    violations: list[str] = []
    for fn in _functions(tree):
        size = (fn.end_lineno or fn.lineno) - fn.lineno + 1
        for label, value, limit in (("loc", size, MAX_FUNC_LOC), ("args", _arg_count(fn), MAX_ARGS),
                                    ("cc", _complexity(fn), MAX_CC)):
            if value > limit:
                violations.append(f"{fn.name}:{fn.lineno} {label}={value}>{limit}")
    assert violations == []
