"""VER-002: DAG зависимостей, отсутствие env и изменяемых глобальных значений."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.unit.test_architecture_modularity import (
    CHANGED_MODULES,
    ROOT,
    _base_tree,
    _tree,
)


def _imports(tree: ast.Module, path: str) -> set[str]:
    """Разрешает absolute/relative imports, включая `from core import ...`."""
    imported: set[str] = set()
    package = Path(path).parts[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            parent = package[: len(package) - node.level + 1] if node.level else ()
            parts = (*parent, *((node.module or "").split(".")))
            module = ".".join(p for p in parts if p)
            imported.add(module)
            imported.update(f"{module}.{alias.name}".strip(".") for alias in node.names)
    return imported


def _os_import_names(tree: ast.Module) -> set[str]:
    return {"os"} | {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "os"
    }


def _direct_environment_imports(node: ast.AST) -> list[ast.alias]:
    if not isinstance(node, ast.ImportFrom) or node.module != "os":
        return []
    return [alias for alias in node.names if alias.name in ("environ", "getenv", "*")]


def _is_environment_read(node: ast.AST, os_names: set[str], direct: set[str]) -> bool:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id in os_names and node.attr in ("environ", "getenv")
    return (
        isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id in direct
    )


def _environment_reads(tree: ast.Module) -> list[ast.AST]:
    """Не пропускает `import os as ...` и `from os import getenv as ...`."""
    os_names = _os_import_names(tree)
    direct: set[str] = set()
    hits: list[ast.AST] = []
    for node in ast.walk(tree):
        aliases = _direct_environment_imports(node)
        if aliases:
            direct.update(alias.asname or alias.name for alias in aliases)
            hits.append(node)
    hits.extend(
        node for node in ast.walk(tree) if _is_environment_read(node, os_names, direct)
    )
    return hits


def _is_mutable_constructor(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id in ("dict", "list", "set")
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        return node.func.value.id == "builtins" and node.func.attr in (
            "dict",
            "list",
            "set",
        )
    return False


def _mutable_values(value: ast.AST | None) -> int:
    if value is None:
        return 0
    literals = (ast.Dict, ast.List, ast.Set, ast.DictComp, ast.ListComp, ast.SetComp)
    return sum(
        isinstance(item, literals) or _is_mutable_constructor(item)
        for item in ast.walk(value)
    )


def _module_mutables(tree: ast.AST) -> int:
    """Считает значения присваиваний вне функций/классов, в том числе под if/try."""
    count = 0
    for node in ast.iter_child_nodes(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            count += _mutable_values(node.value)
        else:
            count += _module_mutables(node)
    return count


@pytest.mark.parametrize(
    "path,forbidden",
    [
        ("core/tool_mode.py", ("core", "bridges", "adapters")),
        ("core/tool_emulation.py", ("core.runtime_env", "bridges", "adapters")),
        ("core/runtime_env.py", ("core.tool_emulation", "bridges", "adapters")),
    ],
)
def test_i3_dependency_dag(path: str, forbidden: tuple[str, ...]) -> None:
    if path == "core/tool_mode.py" and not (ROOT / path).exists():
        pytest.skip("W1 leaf module not created yet")
    violations = [
        name
        for name in _imports(_tree(path), path)
        if any(name == ban or name.startswith(ban + ".") for ban in forbidden)
    ]
    assert not violations, f"{path}: forbidden imports {violations}"


@pytest.mark.parametrize("path", ("core/tool_mode.py", "core/tool_emulation.py"))
def test_i3_domain_does_not_read_environment(path: str) -> None:
    if not (ROOT / path).exists():
        pytest.skip("W1 leaf module not created yet")
    tree = _tree(path)
    assert not _environment_reads(tree), f"{path}: environment coupling"
    if path == "core/tool_mode.py":
        assert "os" not in _imports(tree, path), "Leaf module must not import os"


def test_i3_tool_choice_none_is_one_shared_reexport() -> None:
    if not (ROOT / "core/tool_mode.py").exists():
        pytest.skip("W1 leaf module not created yet")
    core = importlib.import_module("core")
    emulation = importlib.import_module("core.tool_emulation")
    mode = importlib.import_module("core.tool_mode")
    assert emulation._tool_choice_none is core._tool_choice_none
    assert mode._tool_choice_none is core._tool_choice_none


@pytest.mark.parametrize("path", CHANGED_MODULES + ("core/tool_mode.py",))
def test_i4_no_new_module_level_mutable_collections(path: str) -> None:
    if path == "core/tool_mode.py" and not (ROOT / path).exists():
        pytest.skip("W1 leaf module not created yet")
    previous = 0 if path == "core/tool_mode.py" else _module_mutables(_base_tree(path))
    assert _module_mutables(_tree(path)) <= previous, path


@pytest.mark.parametrize(
    "source",
    (
        "import os as env\nx = env.environ",
        "from os import getenv as read\nx = read('X')",
    ),
)
def test_gate_detects_environment_aliases(source: str) -> None:
    assert _environment_reads(ast.parse(source))


@pytest.mark.parametrize(
    "source",
    (
        "from . import tool_emulation",
        "from .tool_emulation import StreamNormalizer",
        "from core import tool_emulation",
    ),
)
def test_gate_detects_relative_and_from_imports(source: str) -> None:
    assert "core.tool_emulation" in _imports(ast.parse(source), "core/tool_mode.py")


@pytest.mark.parametrize(
    "source",
    (
        "x = {}",
        "x = []",
        "x = {1}",
        "x = dict()",
        "x = list()",
        "x = set()",
        "x = [v for v in ()]",
        "x = {v for v in ()}",
        "x = {v: v for v in ()}",
        "if True:\n    x = []",
        "x: dict = {}",
    ),
)
def test_gate_detects_module_mutables(source: str) -> None:
    assert _module_mutables(ast.parse(source)) == 1


def test_gate_ignores_local_mutables_and_immutable_constants() -> None:
    tree = ast.parse(
        "x = ()\ny = frozenset()\ndef f():\n    local = []\nclass C:\n    field = {}"
    )
    assert _module_mutables(tree) == 0
