import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "core").is_dir():
    ROOT = ROOT / "cli-agent-bridge"

GATE_PATH = ROOT / "core/agy_anthropic_gate.py"
PROBE_PATH = ROOT / "core/agy_anthropic_probe.py"
RUNTIME_PATH = ROOT / "bridges/agy-bridge/anthropic_runtime.py"
SERVER_PATH = ROOT / "bridges/agy-bridge/server.py"
NEW_SOURCE_PATHS = (GATE_PATH, PROBE_PATH, RUNTIME_PATH)
FORBIDDEN_GATE_IMPORTS = frozenset(
    {"subprocess", "os", "threading", "time", "pathlib", "httpx", "urllib"}
)
MAX_FILE_LOC = 300
MAX_FUNCTION_LOC = 40
MAX_FUNCTION_ARGS = 5
SERVER_BASELINE_LOC = 8407


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_roots(tree: ast.Module) -> set[str]:
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def _target_names(
    node: ast.Assign | ast.AnnAssign,
) -> list[str]:
    targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
    return [target.id for target in targets if isinstance(target, ast.Name)]


def _is_mutable_collection(value: ast.AST | None) -> bool:
    if isinstance(value, (ast.Dict, ast.List, ast.Set)):
        return True
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id in {"dict", "list", "set"}
    )


def _mutable_module_assignments(tree: ast.Module) -> list[str]:
    violations = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        if _is_mutable_collection(node.value):
            violations.extend(_target_names(node))
    return violations


def _argument_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    positional = list(node.args.posonlyargs + node.args.args)
    if positional and positional[0].arg in {"self", "cls"}:
        positional = positional[1:]
    return (
        len(positional)
        + len(node.args.kwonlyargs)
        + int(node.args.vararg is not None)
        + int(node.args.kwarg is not None)
    )


def _function_violations(path: Path) -> list[str]:
    violations = []
    for node in ast.walk(_tree(path)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end_line = node.end_lineno or node.lineno
        function_loc = end_line - node.lineno + 1
        if function_loc > MAX_FUNCTION_LOC:
            violations.append(f"{node.name}: loc={function_loc}")
        argument_count = _argument_count(node)
        if argument_count > MAX_FUNCTION_ARGS:
            violations.append(f"{node.name}: args={argument_count}")
    return violations


def _all_new_files() -> list[Path]:
    paths = list(NEW_SOURCE_PATHS)
    paths.extend(sorted((ROOT / "tests").glob("test_agy_anthropic_*.py")))
    return paths


class AnthropicModularityTests(unittest.TestCase):
    def test_gate_has_no_io_concurrency_or_network_imports(self) -> None:
        imported = _imported_roots(_tree(GATE_PATH))
        self.assertTrue(
            imported.isdisjoint(FORBIDDEN_GATE_IMPORTS),
            msg=f"Forbidden gate imports: {sorted(imported)}",
        )

    def test_probe_and_gate_have_no_mutable_module_collections(self) -> None:
        for path in (PROBE_PATH, GATE_PATH):
            with self.subTest(path=path.name):
                violations = _mutable_module_assignments(_tree(path))
                self.assertEqual(violations, [])

    def test_new_files_respect_size_and_function_limits(self) -> None:
        for path in _all_new_files():
            with self.subTest(path=str(path.relative_to(ROOT))):
                source = path.read_text(encoding="utf-8")
                self.assertLessEqual(len(source.splitlines()), MAX_FILE_LOC)
                self.assertEqual(_function_violations(path), [])

    def test_server_has_not_grown_beyond_baseline(self) -> None:
        server_loc = len(SERVER_PATH.read_text(encoding="utf-8").splitlines())
        delta = server_loc - SERVER_BASELINE_LOC
        self.assertLessEqual(server_loc, SERVER_BASELINE_LOC)
        self.assertLessEqual(delta, 0)


if __name__ == "__main__":
    unittest.main()
