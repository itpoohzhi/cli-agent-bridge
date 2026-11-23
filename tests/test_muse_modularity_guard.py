"""W3 гард безопасности и модульности muse-1425 (VER-010/011)."""

from __future__ import annotations

import ast
import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT, BASE = Path(__file__).resolve().parents[1], "HEAD"
NEW_PRODUCT = ("core/muse_usage_client.py", "core/stdio_resident/muse_socket_probe.py", "core/stdio_resident/muse_warm_client.py")
MODIFIED_PRODUCT = ("core/stdio_resident/zero_canon_router.py", "core/telemetry_usage.py", "core/http_post_routing.py")
MONOLITH, MONOLITH_BASE_LINES = "core/http_post_routing.py", 303
UNTOUCHED = ("server.py", "adapters/stdio_drivers/muse_driver.py")
TEST_FILES = ("tests/test_muse_usage_client.py", "tests/test_muse_warm_stdio_contract.py", "tests/test_muse_router_usage_gate.py", "tests/test_muse_warm_stdio_adversarial.py", "tests/test_muse_modularity_guard.py")
W3_FILES, PRODUCT = TEST_FILES[3:], NEW_PRODUCT + MODIFIED_PRODUCT
WAVE_FILES = {"W1-B": ("core/muse_usage_client.py", "tests/test_muse_usage_client.py"),
              "W1-C": ("core/stdio_resident/muse_socket_probe.py", "core/stdio_resident/muse_warm_client.py"),
              "W2-C": ("core/telemetry_usage.py", "core/stdio_resident/zero_canon_router.py"),
              "W2-G": ("core/http_post_routing.py", "tests/test_muse_router_usage_gate.py"),
              "W3": ("tests/test_muse_warm_stdio_adversarial.py", "tests/test_muse_modularity_guard.py")}
BARE_SUFFIX = ".local/" + "bin/" + "mu" + "se"
CREDENTIAL = "museClient" + "Credential"
Function = ast.FunctionDef | ast.AsyncFunctionDef


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _base_source(path: str) -> str:
    done = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{path}"],
                          capture_output=True, text=True, check=False)
    if done.returncode != 0:
        pytest.skip(f"нет baseline {BASE}:{path}")
    return done.stdout


def _functions(tree: ast.AST, prefix: str = "") -> dict[str, Function]:
    found: dict[str, Function] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = f"{prefix}{node.name}"
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decor = ",".join(ast.dump(d) for d in node.decorator_list)
                found[f"{name}|{decor}"] = node
            found.update(_functions(node, f"{name}."))
        else:
            found.update(_functions(node, prefix))
    return found


def _nparams(node: Function) -> int:
    args = node.args
    return len(args.posonlyargs + args.args + args.kwonlyargs) + bool(args.vararg) + bool(args.kwarg)


def _mccabe(node: Function) -> int:
    branches = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp)
    score = 1
    for item in ast.walk(node):
        if isinstance(item, branches):
            score += 1
        elif isinstance(item, ast.BoolOp):
            score += len(item.values) - 1
        elif isinstance(item, ast.comprehension):
            score += 1 + len(item.ifs)
    return score


def _loc(node: Function) -> int:
    assert node.end_lineno is not None
    return node.end_lineno - node.lineno + 1


def _assert_strict(path: str, name: str, node: Function) -> None:
    label = f"{path}:{node.lineno} {name}"
    assert _loc(node) <= 50, f"{label}: LOC > 50"
    assert _nparams(node) <= 5, f"{label}: params > 5"
    assert _mccabe(node) <= 10, f"{label}: McCabe > 10"


def _imports_of(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def test_security_invariants_no_bare_muse_binary() -> None:
    for path in PRODUCT + TEST_FILES:
        assert BARE_SUFFIX not in _source(path), f"{path}: голый бинарник muse"
    for path in ("core/muse_usage_client.py", "core/stdio_resident/muse_warm_client.py"):
        assert "muse-cli.sh" in _source(path), f"{path}: запуск только через muse-cli.sh"


def test_security_invariants_no_credential_generation() -> None:
    holders = [p for p in PRODUCT if CREDENTIAL in _source(p)]
    # В продуктовом коде токен handshake упоминает только детектор отклонения в пробе.
    assert holders == ["core/stdio_resident/muse_socket_probe.py"]
    probe_tree = ast.parse(_source("core/stdio_resident/muse_socket_probe.py"))
    payload = next(n for n in ast.walk(probe_tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "_initialize_payload")
    constants = {n.value for n in ast.walk(payload) if isinstance(n, ast.Constant)}
    assert CREDENTIAL not in constants  # payload initialize не несёт credential
    probe = pytest.importorskip("core.stdio_resident.muse_socket_probe")
    assert '"rejected"' in _source("core/stdio_resident/muse_socket_probe.py")
    assert probe._DIR_MODE == 0o700 and probe._FILE_MODE == 0o600


def test_security_invariants_flags_default_false_and_no_secrets() -> None:
    probe = pytest.importorskip("core.stdio_resident.muse_socket_probe")
    warm = pytest.importorskip("core.stdio_resident.muse_warm_client")
    assert probe.probe_enabled({}) is False and warm.warm_stdio_enabled({}) is False
    owners = {"MUSE_UNIX_SOCKET_PROBE_ENABLED": "core/stdio_resident/muse_socket_probe.py",
              "MUSE_WARM_MSP_STDIO_ENABLED": "core/stdio_resident/muse_warm_client.py",
              "MUSE_USAGE_ROUTER_ENABLED": "core/http_post_routing.py"}
    for flag, path in owners.items():
        assert flag in _source(path), f"{flag} отсутствует в {path}"
    secret = re.compile(r"sk-[A-Za-z0-9]{16,}|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}")
    for path in PRODUCT + TEST_FILES:
        assert not secret.search(_source(path)), f"{path}: похоже на секрет"


def test_security_invariants_wrapper_resolution() -> None:
    for name in ("core.muse_usage_client", "core.stdio_resident.muse_warm_client"):
        mod = pytest.importorskip(name)
        resolved = mod.resolve_wrapper_path({"HOME": "/tmp/h"})
        assert resolved == "/tmp/h/.config/muse-launch/muse-cli.sh"
        assert mod.resolve_wrapper_path({"MUSE_CLI_WRAPPER": "/x/w.sh"}) == "/x/w.sh"


def test_modularity_m_mod_i1_file_line_budgets() -> None:
    for path in NEW_PRODUCT:
        assert len(_source(path).splitlines()) <= 240, f"{path}: новый модуль > 240"
    for path in MODIFIED_PRODUCT:
        limit = MONOLITH_BASE_LINES if path == MONOLITH else 300
        assert len(_source(path).splitlines()) <= limit, f"{path}: выше капа {limit}"
    for path in TEST_FILES:
        assert len(_source(path).splitlines()) <= 300, f"{path}: тест > 300"
    for path in W3_FILES:
        assert len(_source(path).splitlines()) <= 260, f"{path}: карточка W3 > 260"


def test_modularity_m_mod_i2_function_budgets() -> None:
    for path in NEW_PRODUCT + TEST_FILES:
        for name, node in _functions(ast.parse(_source(path))).items():
            _assert_strict(path, name, node)
    for path in MODIFIED_PRODUCT:
        old = _functions(ast.parse(_base_source(path)))
        for name, node in _functions(ast.parse(_source(path))).items():
            if name not in old:
                _assert_strict(path, name, node)
            elif ast.dump(node) != ast.dump(old[name]):
                _assert_no_regression(path, name, node, old[name])


def _assert_no_regression(path: str, name: str, node: Function, base: Function) -> None:
    label = f"{path}:{node.lineno} {name} (baseline-функция)"
    assert _loc(node) <= _loc(base), f"{label}: LOC вырос {_loc(base)}->{_loc(node)}"
    assert _nparams(node) <= max(5, _nparams(base)), f"{label}: параметров стало больше"
    ceiling = _mccabe(base) + 1 if _mccabe(base) > 10 else 10
    assert _mccabe(node) <= ceiling, f"{label}: McCabe {_mccabe(base)}->{_mccabe(node)}"


def test_modularity_m_mod_i3_baseline_monoliths_untouched() -> None:
    for path in UNTOUCHED:
        current = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        baseline = hashlib.sha256(_base_source(path).encode("utf-8")).hexdigest()
        assert current == baseline, f"{path}: замороженный монолит изменён (delta != 0)"
    delta = len(_source(MONOLITH).splitlines()) - len(_base_source(MONOLITH).splitlines())
    assert delta <= 0, f"{MONOLITH}: delta {delta} > 0 при фасадном сжатии AD-005"


def _import_graph() -> dict[str, set[str]]:
    modules = {"core." + p[len("core/"):].removesuffix(".py").replace("/", "."): p for p in PRODUCT}
    graph: dict[str, set[str]] = {}
    for mod, path in modules.items():
        deps: set[str] = set()
        for imported in _imports_of(ast.parse(_source(path))):
            deps.update(t for t in modules if t != mod and (imported == t or imported.startswith(t + ".")))
        graph[mod] = deps
    return graph


def _assert_acyclic(graph: dict[str, set[str]]) -> None:
    done: set[str] = set()
    stack: list[str] = []

    def visit(mod: str) -> None:
        assert mod not in stack, f"цикл импорта: {' -> '.join([*stack, mod])}"
        if mod in done:
            return
        stack.append(mod)
        for dep in graph.get(mod, set()):
            visit(dep)
        stack.pop()
        done.add(mod)

    for module in graph:
        visit(module)


def test_modularity_m_mod_i3_import_cycles_and_clean_domain() -> None:
    _assert_acyclic(_import_graph())
    leaves = ("core/muse_usage_client.py", "core/stdio_resident/muse_socket_probe.py")
    forbidden = ("server", "adapters", "core.http_post_routing", "core.stdio_resident.zero_canon_router")
    for path in leaves:
        imports = _imports_of(ast.parse(_source(path)))
        assert not any(i == f or i.startswith(f + ".") for i in imports for f in forbidden), path


def _assert_no_module_mutables(path: str) -> None:
    for node in ast.parse(_source(path)).body:
        val = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
        assert not isinstance(val, (ast.Dict, ast.List, ast.Set)), f"{path}: module-level mutable"
        if isinstance(val, ast.Call) and isinstance(val.func, ast.Name):
            assert val.func.id not in {"dict", "list", "set"}, f"{path}: module-level mutable"


def _class_self_attrs(path: str, cls_name: str) -> set[str]:
    cls = next(n for n in ast.walk(ast.parse(_source(path))) if isinstance(n, ast.ClassDef) and n.name == cls_name)
    out: set[str] = set()
    for node in ast.walk(cls):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                out.add(node.attr)
    return out


def test_modularity_m_mod_i4_single_state_owners() -> None:
    for path in PRODUCT:
        _assert_no_module_mutables(path)
    owners = {
        "core/muse_usage_client.py": ("MuseUsageClient", {"_cache", "_inflight", "_lock"}),
        "core/stdio_resident/muse_warm_client.py": ("MuseWarmStdioRegistry", {"_sessions", "_last_usage", "_lock", "_transport"}),
    }
    for path, (cls_name, expected) in owners.items():
        assert expected <= _class_self_attrs(path, cls_name), f"{cls_name}: нет состояния"


def test_modularity_m_mod_i5_wave_plan_shape() -> None:
    covered: set[str] = set()
    for wave, files in WAVE_FILES.items():
        assert 1 <= len(files) <= 2, f"{wave}: карточек файлов {len(files)} вне 1..2"
        assert all(not Path(f).is_absolute() for f in files), f"{wave}: нужен repo-relative путь"
        assert all((ROOT / f).exists() for f in files), f"{wave}: файл отсутствует"
        covered.update(files)
    wave_contract = "tests/test_muse_warm_stdio_contract.py"  # контракт W0 для W1-C/W2-C
    assert (set(PRODUCT) | set(TEST_FILES)) - covered == {wave_contract}
    assert (ROOT / wave_contract).exists()
