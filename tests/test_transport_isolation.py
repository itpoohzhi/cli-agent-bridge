"""Независимые контракты слоёв, владельцев состояния, волн и T-ISO."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

import pytest

from tests.test_transport_modularity import BASE, RUN, Snapshot, snapshot as snapshot
from tests.transport_test_support import semantic_equal

pytestmark = pytest.mark.strict_leak_check
CANON = Path.home() / "Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md"
PURE = frozenset({"core.routing_contract", "core.transport_routing", "core.catalog_routes"})
APPLICATION = frozenset({"core.route_eligibility", "core.route_attempts", "core.routing_schema"})
HOSTS = frozenset({"server", "core.provider_manifest", "core.fleet_compiler"})
OWNERS = (("core/transport_routing.py", "RouteDraw", "_remaining"),
    ("core/route_attempts.py", "RouteAttemptRunner", "_visited"),
    ("core/http_post_context.py", "PostRequestContext", "_request"),
    ("adapters/passthrough_pool.py", "PassthroughConnectionPool", "_idle"))
EXECUTABLE = frozenset(".py .ts .tsx .js .jsx .mjs .cjs .go .rs .java .kt .sql .sh".split())
JS = frozenset(".ts .tsx .js .jsx .mjs .cjs".split())

def module_name(path: str) -> str:
    return path.removesuffix(".py").replace("/", ".").removesuffix(".__init__")

def dynamic_target(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call) or ast.unparse(node.func) not in {"__import__", "importlib.import_module"}:
        return None
    argument = node.args[0] if node.args else None
    value = getattr(argument, "value", None)
    return value if isinstance(value, str) else "<unresolved_dynamic>"

def imports(source: bytes, module: str) -> frozenset[str]:
    """Учитывает относительные, локальные, TYPE_CHECKING и явные dynamic imports."""
    result = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = module.split(".")[:-node.level] if node.level else []
            target = ".".join([*prefix, node.module or ""]).strip(".")
            result.update(target + "." + alias.name for alias in node.names)
        elif dyn := dynamic_target(node):
            result.add(dyn)
    return frozenset(result)

def graph(blobs: tuple[tuple[str, bytes], ...]) -> dict[str, frozenset[str]]:
    sources = {module_name(p): b for p, b in blobs
               if p.endswith(".py") and (p.startswith(("core/", "adapters/")) or p == "server.py")}
    result = {}
    for module, source in sources.items():
        resolved = set()
        for target in imports(source, module):
            parts = target.split(".")
            while parts and ".".join(parts) not in sources:
                parts.pop()
            if parts:
                resolved.add(".".join(parts))
        result[module] = frozenset(resolved)
    return result

def reaches(edges: dict[str, frozenset[str]], start: str, target: str) -> bool:
    pending, visited = list(edges.get(start, ())), set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in visited:
            visited.add(node)
            pending.extend(edges.get(node, ()))
    return False

def test_dependency_directions_and_no_new_cycles(snapshot: Snapshot) -> None:
    before, after = graph(snapshot.before), graph(snapshot.after)
    changed = {module_name(p) for p in snapshot.changed}
    for module in changed & after.keys():
        if module in PURE:
            assert not (after[module] - PURE), module
        if module in APPLICATION:
            assert not any(m == "server" or m.startswith("adapters.") for m in after[module])
        if module not in HOSTS:
            assert not after[module] & HOSTS, module
        for target in after[module] - before.get(module, frozenset()):
            assert not reaches(after, target, module), (module, target)

def test_pure_modules_no_indirect_io(snapshot: Snapshot) -> None:
    """Белый список независим от импортов проверяемого кандидата."""
    allowed = PURE | {"__future__", "dataclasses", "typing", "collections", "enum",
                      "hashlib", "json", "math", "functools", "operator", "itertools"}
    sources = dict(snapshot.after)
    for module in PURE:
        path = module.replace(".", "/") + ".py"
        assert path in sources, module
        dependencies = imports(sources[path], module)
        assert all(d in PURE or d.split(".")[0] in allowed for d in dependencies)
        tree = ast.parse(sources[path])
        calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        assert not calls & {"open", "input", "print", "eval", "exec", "__import__"}

def mutable_value(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    return isinstance(node, ast.Call) and ast.unparse(node.func) in {"list", "dict", "set", "deque"}

def shared_values(node: ast.AST) -> tuple[ast.AST, ...]:
    if not isinstance(node, (ast.Module, ast.ClassDef)):
        return ()
    return tuple(n.value for n in node.body
                 if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None)

def state_errors(source: bytes) -> tuple[str, ...]:
    errors = []
    for node in ast.walk(ast.parse(source)):
        if any(mutable_value(value) for value in shared_values(node)):
            errors.append("shared_mutable")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defaults = (*node.args.defaults, *filter(None, node.args.kw_defaults))
            if any(mutable_value(n) for n in defaults):
                errors.append("mutable_default")
        if isinstance(node, ast.Return) and ast.unparse(node) in {"return self." + owner[2] for owner in OWNERS}:
            errors.append("owner_escape")
    return tuple(errors)

@pytest.mark.parametrize("source", ["cache = {}", "class Owner:\n    cache = []",
    "def f(items=[]):\n    return items", "class Owner:\n    def f(self):\n        return self._visited"])
def test_state_oracle_negative_canaries(source: str) -> None:
    assert state_errors(source.encode())

def test_new_runtime_state_has_private_request_or_pool_owner(snapshot: Snapshot) -> None:
    before, after = dict(snapshot.before), dict(snapshot.after)
    for path in snapshot.changed - before.keys():
        if path.endswith(".py") and path.startswith(("core/", "adapters/")):
            assert state_errors(after[path]) == (), path
    for path, owner, field in OWNERS:
        if path in after:
            classes = {n.name: n for n in ast.parse(after[path]).body if isinstance(n, ast.ClassDef)}
            assert owner in classes
            attributes = {n.attr for n in ast.walk(classes[owner]) if isinstance(n, ast.Attribute)}
            assert field in attributes

def collected_test(path: str) -> bool:
    p = PurePosixPath(path)
    if p.suffix == ".py":
        return p.name.startswith("test_") or p.stem.endswith("_test")
    if p.suffix == ".go":
        return p.name.endswith("_test.go")
    if p.suffix in JS:
        return not p.name.endswith(".d.ts") and (p.stem.endswith((".test", ".spec")) or
            ("__tests__" in p.parts[:-1] and not p.name.startswith("_")))
    return p.suffix in EXECUTABLE and (p.name.startswith("test_") or p.stem.endswith(("_test", ".test", ".spec")))

def neighbor(path: str, paths: frozenset[str]) -> str:
    parent = PurePosixPath(path).parent
    suffix = PurePosixPath(path).suffix
    family = JS if suffix in JS else {suffix}
    peers = sorted(p for p in paths if collected_test(p) and
                   PurePosixPath(p).parent == parent and PurePosixPath(p).suffix in family)
    return peers[(peers.index(path) + 1) % len(peers)]

def mutation_sample(ids: frozenset[str], critical: frozenset[str], span: str) -> tuple[str, ...]:
    assert critical <= ids and len(critical) <= 40
    chosen, remaining = sorted(critical), sorted(ids - critical)
    seed = hashlib.sha256(span.encode()).hexdigest()[:8]
    for index in range(min(40, len(ids)) - len(chosen)):
        digest = hashlib.sha256(f"{seed}:{index}".encode()).hexdigest()
        chosen.append(remaining.pop(int(digest, 16) % len(remaining)))
    return tuple(chosen)

def file_budget_valid(budget: object, targets: list[str], baseline: dict[str, int]) -> bool:
    """Разрешает общий лимит или точные per-file caps без роста baseline."""
    if type(budget) is int:
        return budget <= 300
    return isinstance(budget, dict) and set(budget) == set(targets) and all(
        type(cap) is int and cap <= max(300, baseline.get(path, 0)) for path, cap in budget.items())

def test_wave_dag_scope_bounds_and_baseline_frozen(snapshot: Snapshot) -> None:
    packet = json.loads((RUN / "architecture/architecture-packet.json").read_bytes())
    baseline = json.loads((RUN / "architecture/baseline-monoliths.json").read_bytes())
    base_locs = {entry["path"]: entry["line_count"] for entry in baseline["files"]}
    assert packet["base_revision"] == BASE
    cards, declared = packet["wave_plan"], set()
    edges = {c["wave_id"]: frozenset(c["depends_on"]) for c in cards}
    assert len(edges) == len(cards)
    for card in cards:
        assert edges[card["wave_id"]] <= edges.keys()
        assert not reaches(edges, card["wave_id"], card["wave_id"])
        targets = card["target_files"]
        assert 1 <= len(targets) <= 2 and len(set(targets)) == len(targets)
        assert file_budget_valid(card["file_line_budget"], targets, base_locs) and card["context_line_budget"] <= 400
        assert card["expected"] and card["wave_oracle_cmd"]
        declared.update(targets)
    assert snapshot.changed <= declared, sorted(snapshot.changed - declared)
    assert sorted(p["path"] for p in packet["modularity"]["product_files"]) == sorted(declared)

@pytest.mark.parametrize(("path", "expected"), [
    ("tests/test_a.py", True), ("tests/helper.py", False), ("tests/conftest.py", False),
    ("tests/data.json", False), ("web/__tests__/a.ts", True), ("web/a.d.ts", False)])
def test_t_iso_collection_vectors(path: str, expected: bool) -> None:
    assert collected_test(path) is expected

def test_t_iso_neighbor_excludes_infrastructure_and_other_runner() -> None:
    paths = frozenset({"tests/test_a.py", "tests/test_b.py", "tests/conftest.py",
                       "tests/helper.py", "tests/a.test.js", "other/test_c.py"})
    assert neighbor("tests/test_a.py", paths) == "tests/test_b.py"
    assert neighbor("tests/test_b.py", paths) == "tests/test_a.py"
    assert neighbor("tests/a.test.js", paths) == "tests/a.test.js"

def test_t_iso_sample_critical_first_and_independent_digest_vector() -> None:
    ids = frozenset(f"site-{i:02}" for i in range(42))
    sample = mutation_sample(ids, frozenset({"site-41"}), "abc..def")
    assert len(sample) == len(set(sample)) == 40 and sample[0] == "site-41"
    # Независимый FIPS-180-4 расчёт: первый digest 681412c9...5b1d26b7, mod 41 = 21.
    seed = hashlib.sha256(b"abc..def").hexdigest()[:8]
    assert seed == "517844fd"
    assert sample[1] == "site-21"
    assert ids - set(sample) == {"site-02", "site-40"}

def test_import_graph_local_relative_and_cycle_canaries() -> None:
    assert imports(b"def f():\n from .b import value", "core.a") == frozenset({"core.b.value"})
    edges = {"a": frozenset({"b"}), "b": frozenset({"a"})}
    assert reaches(edges, "a", "a")
    assert not reaches({"a": frozenset({"b"})}, "b", "a")

def categories(targets: frozenset[str]) -> frozenset[str]:
    """Longest-prefix из внешнего канона, без локальной копии его множеств."""
    source = CANON.read_text()
    groups = re.findall(r"`((?:TRANSPORT|PERSISTENCE|NET_PROC_IO)_IMPORTS) = (\{[^`]+\})`", source)
    assert len(groups) == 3
    prefixes = [(prefix, name) for name, literal in groups for prefix in ast.literal_eval(literal)]
    found = set()
    for target in targets:
        matches = [(prefix, name) for prefix, name in prefixes
                   if target == prefix or target.startswith(prefix + ".")]
        if matches:
            found.add(max(matches, key=lambda pair: len(pair[0]))[1])
    return frozenset(found)

def test_single_infrastructure_category_and_longest_prefix(snapshot: Snapshot) -> None:
    assert categories(frozenset({"aiohttp.web"})) == {"TRANSPORT_IMPORTS"}
    assert categories(frozenset({"aiohttp.client", "socket"})) == {"NET_PROC_IO_IMPORTS"}
    for path, source in snapshot.after:
        if path in snapshot.changed and path.endswith(".py") and path.startswith(("core/", "adapters/")):
            assert len(categories(imports(source, module_name(path)))) <= 1, path

@pytest.mark.parametrize("domain", ["threads", "async_tasks", "sockets", "descriptors", "environment", "singletons"])
@pytest.mark.asyncio(loop_scope="session")
async def test_six_domain_guard_negative_canaries(domain: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from tests import conftest as guard
    assert set(guard.GUARD_DOMAINS) == {"threads", "async_tasks", "sockets", "descriptors", "environment", "singletons"}
    base = guard._snapshot()
    if domain == "singletons":
        dirty = []
        guard._reset_flags(SimpleNamespace(_budget=object()), "", True, dirty)
        assert dirty == ["dirty_singleton=_budget"]
        return
    if domain == "threads":
        item = type("Canary", (), {"name": "canary", "is_alive": lambda _: True})()
        monkeypatch.setattr(guard.threading, "enumerate", lambda: [item])
    elif domain == "async_tasks":
        monkeypatch.setattr(guard, "_live_tasks", lambda: base["tasks"] | {object()})
    elif domain in {"sockets", "descriptors"}:
        monkeypatch.setattr(guard, "_fd_numbers", lambda: base["fds"] | {99999})
        monkeypatch.setattr(guard, "_is_socket", lambda _: domain == "sockets")
    else:
        monkeypatch.setattr(guard, "_env_digests", lambda: base["env"] | {"CANARY": "digest"})
    assert any(item.startswith(domain + "=") for item in guard._leaks(base))

@pytest.mark.semantic_red("request_state_owners_missing")
def test_required_request_state_owners(snapshot: Snapshot) -> None:
    missing = tuple(p for p, _, _ in OWNERS if p not in dict(snapshot.after))
    semantic_equal(missing, (), "request_state_owners_missing")

@pytest.mark.parametrize("listing", ["--cached", "--others", "--ignored"])
def test_current_blobs_filters_only_ignored_bridge_runtime(listing: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests import test_transport_modularity as oracle
    runtime = {"bridges/demo/workspace/a.txt", "bridges/demo/logs/nested/a.log"}
    kept = {".env", "bridges/demo/.env", "bridges/demo/workspace/.env", "bridges/demo/logs/.env",
            "bridges/demo/logs.py", "bridges/demo/workspaces/a.txt", "docs/demo/logs/a.txt",
            "bridges/demo/workspace/.env.local", "bridges/demo/logs/nested/.env.secret"}
    paths = runtime | kept
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"canary")

    def fake_git(arguments: tuple[str, ...], data: bytes | None = None) -> bytes:
        branch = "--ignored" if "--ignored" in arguments else arguments[2]
        return b"\0".join(path.encode() for path in sorted(paths)) if branch == listing else b""

    monkeypatch.setattr(oracle, "ROOT", tmp_path)
    monkeypatch.setattr(oracle, "git", fake_git)
    expected = kept if listing == "--ignored" else paths
    assert dict(oracle.current_blobs()) == dict.fromkeys(expected, b"canary")
    assert all(oracle.product(path) for path in kept)
