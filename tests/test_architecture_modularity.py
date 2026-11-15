"""VER-002: неизменяемый baseline и архитектурные гейты M-MOD I1..I5."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # pytest console entry point, как в соседних тестах.
BASE_REVISION = "2c4b3e4cbf6358f7507a14ba9c6cd539844112e6"
CHANGED_MODULES = (
    "core/tool_emulation.py",
    "core/runtime_env.py",
    "adapters/passthrough_adapter.py",
    "bridges/claude-p-bridge/server.py",
)
Function = ast.FunctionDef | ast.AsyncFunctionDef


def _tree(path: str) -> ast.Module:
    return ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)


def _base_tree(path: str) -> ast.Module:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{BASE_REVISION}:{path}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return ast.parse(result.stdout, filename=f"{BASE_REVISION}:{path}")


def _functions(tree: ast.AST, prefix: str = "") -> dict[str, Function]:
    """Имена включают классы, вложенные функции и декораторы property.setter."""
    found: dict[str, Function] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = f"{prefix}{node.name}"
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = ",".join(ast.dump(d) for d in node.decorator_list)
                found[f"{name}|{decorators}"] = node
            found.update(_functions(node, f"{name}."))
        else:
            found.update(_functions(node, prefix))
    return found


def _parameter_names(node: Function) -> list[str]:
    args = node.args
    ordered = args.posonlyargs + args.args
    if args.vararg:
        ordered += [args.vararg]
    ordered += args.kwonlyargs
    if args.kwarg:
        ordered += [args.kwarg]
    return [arg.arg for arg in ordered]


def _complexity(node: Function) -> int:
    """Метрика из M-MOD; вложенные тела проверяются также самостоятельно."""
    branches = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.ExceptHandler,
        ast.With,
        ast.AsyncWith,
        ast.IfExp,
        ast.Assert,
    )
    score = 1
    for item in ast.walk(node):
        score += isinstance(item, branches)
        if isinstance(item, ast.BoolOp):
            score += len(item.values) - 1
        if isinstance(item, ast.comprehension):
            score += len(item.ifs)
    return score


def _assert_budgets(path: str, name: str, node: Function) -> None:
    label = f"{path}:{node.lineno} {name}"
    assert node.end_lineno is not None
    assert node.end_lineno - node.lineno + 1 <= 50, f"{label}: LOC > 50"
    assert len(_parameter_names(node)) <= 5, f"{label}: parameters > 5"
    assert _complexity(node) <= 10, f"{label}: CC > 10"


@pytest.fixture(scope="module")
def baseline() -> dict[str, Any]:
    data = json.loads((ROOT / "architecture/baseline-monoliths.json").read_bytes())
    assert data["schema_version"] == "1.0"
    assert data["base_revision"] == BASE_REVISION
    return {entry["path"]: entry for entry in data["files"]}


@pytest.mark.parametrize("path", ("server.py", "core/backend_adapter.py"))
def test_i1_untouched_monolith_sha256(path: str, baseline: dict[str, Any]) -> None:
    assert (
        hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        == baseline[path]["sha256"]
    )


@pytest.mark.parametrize("path", CHANGED_MODULES + ("core/tool_mode.py",))
def test_i1_line_ceilings(path: str, baseline: dict[str, Any]) -> None:
    if path == "core/tool_mode.py" and not (ROOT / path).exists():
        pytest.skip("W1 leaf module not created yet")
    limits = {"core/tool_mode.py": 150, "core/runtime_env.py": 180}
    ceiling = limits[path] if path in limits else baseline[path]["lines"]
    assert len((ROOT / path).read_text(encoding="utf-8").splitlines()) <= ceiling


def test_i2_stream_normalizer_constructor_signature_is_unchanged() -> None:
    current = _functions(_tree("core/tool_emulation.py"))["StreamNormalizer.__init__|"]
    old = _functions(_base_tree("core/tool_emulation.py"))["StreamNormalizer.__init__|"]
    assert _parameter_names(current) == [
        "self",
        "on_content",
        "on_reasoning",
        "on_tool_call",
        "strict_live",
        "reasoning_tags",
        "max_reasoning_depth",
    ]
    assert ast.dump(current.args) == ast.dump(old.args)


@pytest.mark.parametrize("path", CHANGED_MODULES + ("core/tool_mode.py",))
def test_i2_all_new_or_modified_functions_have_small_budgets(path: str) -> None:
    if path == "core/tool_mode.py" and not (ROOT / path).exists():
        pytest.skip("W1 leaf module not created yet")
    old = {} if path == "core/tool_mode.py" else _functions(_base_tree(path))
    for name, node in _functions(_tree(path)).items():
        # Единственное grandfathered исключение: публичный конструктор с 7 args.
        if path == "core/tool_emulation.py" and name == "StreamNormalizer.__init__|":
            continue
        if name not in old or ast.dump(node) != ast.dump(old[name]):
            _assert_budgets(path, name, node)


def test_gate_counts_all_parameter_kinds_and_complexity_terms() -> None:
    node = ast.parse(
        "def f(a, /, b, *args, c, d, **kwargs):\n"
        "    assert a and b and c\n"
        "    if a:\n"
        "        for x in b:\n"
        "            while c:\n"
        "                x = a if b else c\n"
        "    try:\n"
        "        with a:\n"
        "            return [x for x in b if x if c]\n"
        "    except ValueError:\n"
        "        return None\n"
    ).body[0]
    assert isinstance(node, ast.FunctionDef)
    assert len(_parameter_names(node)) == 6
    assert _complexity(node) == 13
