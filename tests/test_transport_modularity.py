"""Независимые Git/AST-оракулы W0-E; runtime-код не задаёт ожиданий."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.transport_test_support import semantic_equal, require_base, require_wave_artifacts

ROOT = Path(__file__).resolve().parents[1]
# BASE фиксирует инвентарь; UPSTREAM_DEV отделяет изменения целевой ветки от волны.
BASE = "cc741edcb9e59d77e02a36790bd3c6e406dbdebb"
UPSTREAM_DEV = "2c4b3e4cbf6358f7507a14ba9c6cd539844112e6"
RUN = ROOT / ".ai-team/runs/weighted-transport-dev"
BASELINE_SHA = "e18dc96bba91c204fd578af943a12fcae988b40641ccf93c9b1289c6b6cb662d"
BASE_TREE_SHA = "d7f72a3f001dfba242b0178b7cef6d1e8edd0e36d0727e2b0baffb95d50887a1"
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
BlobSet = tuple[tuple[str, bytes], ...]

def git(arguments: tuple[str, ...], data: bytes | None = None) -> bytes:
    """Читает Git без shell, фильтров рабочего дерева и смены индекса."""
    executable = shutil.which("git")
    assert executable is not None
    result = subprocess.run([executable, "-C", str(ROOT), *arguments], input=data, capture_output=True,
                            check=True, timeout=float(os.environ.get("TRANSPORT_AST_GIT_TIMEOUT_S", "10")))
    return result.stdout

def physical_lines(data: bytes) -> int:
    return data.count(b"\n") + int(bool(data) and not data.endswith(b"\n"))

def product(path: str) -> bool:
    """Исключает артефакты исполнения, но не ignored исходники/данные."""
    parts = Path(path).parts
    caches = {".git", ".ai-team", "analysis", "__pycache__", ".pytest_cache", ".ruff_cache"}
    return not bool(set(parts) & caches)

def fingerprint(blobs: BlobSet) -> str:
    digest = hashlib.sha256()
    for path, data in sorted(blobs):
        digest.update(path.encode() + b"\0" + hashlib.sha256(data).digest())
    return digest.hexdigest()

def base_blobs(revision: str = BASE) -> BlobSet:
    records = git(("ls-tree", "-rz", "--full-tree", revision)).split(b"\0")
    entries = [record.split(b"\t", 1) for record in records if record]
    entries = [(meta, path) for meta, path in entries if ".ai-team" not in Path(os.fsdecode(path)).parts]
    ids = [meta.split()[2] for meta, _ in entries]
    batch = git(("cat-file", "--batch"), b"\n".join(ids) + b"\n")
    offset, result = 0, []
    for (meta, path), oid in zip(entries, ids, strict=True):
        end = batch.index(b"\n", offset)
        actual, kind, size = batch[offset:end].split()
        assert (actual, kind) == (oid, b"blob"), meta
        start, length = end + 1, int(size)
        result.append((os.fsdecode(path), batch[start:start + length]))
        assert batch[start + length:start + length + 1] == b"\n"
        offset = start + length + 1
    assert offset == len(batch)
    return tuple(sorted(result))

def ignored_bridge_runtime(path: str) -> bool:
    parts = Path(path).parts
    return (len(parts) > 3 and parts[0] == "bridges" and parts[2] in {"workspace", "logs"}
            and not parts[-1].startswith(".env"))

def current_blobs() -> BlobSet:
    paths = set()
    for arguments in (("ls-files", "-z", "--cached"),
                      ("ls-files", "-z", "--others", "--exclude-standard"),
                      ("ls-files", "-z", "--others", "--ignored", "--exclude-standard")):
        for raw in filter(None, git(arguments).split(b"\0")):
            path = os.fsdecode(raw)
            if "--ignored" not in arguments or not ignored_bridge_runtime(path):
                paths.add(path)
    result = []
    for path in sorted(filter(product, paths)):
        source = ROOT / path
        if source.is_symlink():
            result.append((path, os.fsencode(os.readlink(source))))
        elif source.is_file():
            result.append((path, source.read_bytes()))
    return tuple(result)

@dataclass(frozen=True, slots=True)
class Snapshot:
    """Неизменяемые байты полного дерева, а не поздние чтения кандидата."""

    before: BlobSet
    after: BlobSet
    changed: frozenset[str]
    sha256: str

@pytest.fixture(scope="session")
def snapshot() -> Iterator[Snapshot]:
    require_base(ROOT, BASE)
    before, after = base_blobs(), current_blobs()
    old, new = dict(before), dict(after)
    changed = {p for p in old.keys() | new.keys() if old.get(p) != new.get(p)}
    diff = git(("diff", "--raw", "--no-abbrev", BASE))
    changed.update(os.fsdecode(p) for p in git(("diff", "--name-only", "-z", BASE)).split(b"\0") if p)
    yield Snapshot(before, after, frozenset(filter(product, changed)), fingerprint(after))
    assert current_blobs() == after, "Дерево изменилось во время оракула"
    assert git(("diff", "--raw", "--no-abbrev", BASE)) == diff

def functions(source: bytes) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    found = {}
    pending = [("", ast.parse(source))]
    while pending:
        prefix, parent = pending.pop()
        for node in ast.iter_child_nodes(parent):
            name = prefix
            if isinstance(node, (*FUNCTIONS, ast.ClassDef)):
                name = prefix + "." + node.name
            if isinstance(node, FUNCTIONS):
                key = name
                while key in found:
                    key += "#"
                found[key] = node
            pending.append((name, node))
    return found

def function_source(source: bytes, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bytes:
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    return b"\n".join(source.split(b"\n")[start - 1:node.end_lineno])

def branch_weight(node: ast.AST) -> int:
    """CC/ast-v1: ветви, handlers, bool-операнды, comprehensions и match."""
    if isinstance(node, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
        return 1
    if isinstance(node, ast.BoolOp):
        return len(node.values) - 1
    if isinstance(node, ast.comprehension):
        return 1 + len(node.ifs)
    if isinstance(node, ast.match_case):
        wildcard = isinstance(node.pattern, ast.MatchAs) and node.pattern.pattern is None
        return int(not wildcard) + int(node.guard is not None)
    return 0

def metrics(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, int, int]:
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    count = sum(a.arg not in {"self", "cls"} for a in args)
    count += int(node.args.vararg is not None) + int(node.args.kwarg is not None)
    branches, pending = 0, list(ast.iter_child_nodes(node))
    while pending:
        item = pending.pop()
        if isinstance(item, (*FUNCTIONS, ast.ClassDef, ast.Lambda)):
            continue
        branches += branch_weight(item)
        pending.extend(ast.iter_child_nodes(item))
    assert node.end_lineno is not None
    return node.end_lineno - start + 1, count, 1 + branches

def exceeds(bounds: tuple[int, int, int]) -> bool:
    return any(value > bound for value, bound in zip(bounds, (40, 5, 10), strict=True))

def facade_invalid(previous: ast.AST | None, node: ast.AST) -> bool:
    if previous is None or not exceeds(metrics(previous)):
        return False
    return metrics(node)[0] > 5 or not any(isinstance(n, ast.Call) for n in ast.walk(node))

def violations(path: str, before: bytes, after: bytes) -> list[tuple[str, str]]:
    cap = max(300, physical_lines(before))
    errors = [(path, "file_loc")] if physical_lines(after) > cap else []
    if not path.endswith(".py"):
        return errors
    old = functions(before)
    for name, node in functions(after).items():
        previous = old.get(name)
        if previous is not None and function_source(before, previous) == function_source(after, node):
            continue
        if exceeds(metrics(node)):
            errors.append((path + name, "function_bound"))
        if facade_invalid(previous, node):
            errors.append((path + name, "legacy_facade"))
    return errors

def test_complete_baseline_inventory_and_exact_hash(snapshot: Snapshot) -> None:
    require_wave_artifacts(RUN)
    raw = (RUN / "architecture/baseline-monoliths.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == BASELINE_SHA
    baseline = json.loads(raw)
    assert baseline["base_revision"] == BASE
    actual = [{"path": p, "line_count": physical_lines(b),
               "content_sha256": hashlib.sha256(b).hexdigest(), "byte_count": len(b)}
              for p, b in snapshot.before if physical_lines(b) > 300]
    assert len(actual) == 127
    assert sorted(baseline["files"], key=lambda entry: entry["path"]) == actual
    assert fingerprint(snapshot.before) == BASE_TREE_SHA

def test_all_changed_tracked_untracked_and_ignored_bounds(snapshot: Snapshot) -> None:
    before, after = dict(base_blobs(UPSTREAM_DEV)), dict(snapshot.after)
    errors = []
    for path in sorted(after):
        if before.get(path) != after[path]:
            errors.extend(violations(path, before.get(path, b""), after[path]))
    assert not errors, (snapshot.sha256, errors)

@pytest.mark.semantic_red("legacy_transport_facades_not_extracted")
def test_required_transport_extractions(snapshot: Snapshot) -> None:
    required = {
        "server.py": {"do_POST", "_serve_passthrough"},
        "adapters/passthrough_adapter.py": {"handle", "_open"},
        "core/provider_manifest.py": {"validate_manifest"},
        "core/fleet_compiler.py": {"compile_catalog"},
    }
    errors = []
    for path, names in required.items():
        source = dict(snapshot.after)[path]
        found = {name.rsplit(".", 1)[-1]: node for name, node in functions(source).items()}
        for name in sorted(names):
            node = found.get(name)
            if node is None or metrics(node)[0] > 5:
                errors.append((path, name))
    semantic_equal(tuple(errors), (), "legacy_transport_facades_not_extracted")

@pytest.mark.parametrize(("data", "expected"), [(b"", 0), (b"x", 1), (b"\n", 1),
                                                (b"a\nb", 2), (b"a\r\nb\r\n", 2)])
def test_physical_loc_includes_unterminated_line(data: bytes, expected: int) -> None:
    assert physical_lines(data) == expected

@pytest.mark.parametrize(("source", "expected"), [
    ("@decorator\nasync def f(a, /, b, *, c, **kw):\n    return a", (3, 4, 1)),
    ("def f(self, a):\n    return a if a and a > 1 else 0", (2, 1, 3)),
    ("def f():\n    def g():\n        if True:\n            return 1\n    return g()", (5, 0, 1)),
    ("def f(xs):\n    return [x for x in xs if x for y in x if y]", (2, 1, 5))])
def test_ast_metric_known_vectors(source: str, expected: tuple[int, int, int]) -> None:
    assert metrics(functions(source.encode())[".f"]) == expected

def test_bounds_reject_301st_no_lf_and_changed_legacy_body() -> None:
    assert violations("new.txt", b"", b"\n" * 300 + b"x") == [("new.txt", "file_loc")]
    assert violations("new.bin", b"", b"\xff\n" * 301) == [("new.bin", "file_loc")]
    before = b"def f():\n" + b"    # legacy\n" * 40 + b"    return 1\n"
    assert ("old.py.f", "function_bound") in violations("old.py", before, before.replace(b"1", b"2"))
    assert violations("old.py", before, before) == []

def test_w0_e_itself_obeys_every_bound() -> None:
    for path in ("tests/test_transport_modularity.py", "tests/test_transport_isolation.py"):
        assert violations(path, b"", (ROOT / path).read_bytes()) == []

def _check_stage_entry(card: str, entry: dict[str, object], w12: set[str], sources: dict[str, bytes]) -> None:
    assert entry["must_select_at_least_one"] is True
    files = list(entry["test_files"])
    assert files and set(files) <= sources.keys(), card
    if card not in w12:
        return
    prefix = "test_stage_" + card.lower().replace("-", "_") + "_"
    assert entry["required_name_prefix"] == prefix
    names = [name.rsplit(".", 1)[-1] for path in files for name in functions(sources[path])]
    whole = entry.get("selector") == "entire existing modules, no -k filtering"
    assert any(name.startswith("test_" if whole else prefix) for name in names), card

def test_stage_registry_has_fixed_names_and_nonempty_selection(snapshot: Snapshot) -> None:
    require_wave_artifacts(RUN)
    packet = json.loads((RUN / "architecture/architecture-packet.json").read_bytes())
    registry = packet["wave_execution_contract"]["stage_test_registry"]
    plans = [c["wave_id"] for c in packet["wave_plan"]]
    w12 = {w for w in plans if w.startswith(("W1-", "W2-"))}
    w3 = {w for w in plans if w.startswith("W3-")}
    assert w12 <= set(registry) <= (w12 | w3)
    sources = dict(snapshot.after)
    for card, entry in registry.items():
        _check_stage_entry(card, entry, w12, sources)

def test_product_excludes_run_artifacts_but_keeps_ignored_secrets() -> None:
    """Артефакты не входят в продукт; ignored секреты остаются под контролем."""
    assert not product("analysis/weighted-transport/evidence-ledger.md")
    assert not product(".ai-team/runs/evidence.json")
    assert product(".env")

@pytest.mark.parametrize("card", ["W1-A", "W2-V"])
def test_stage_entry_selection_negative_canaries(card: str) -> None:
    prefix, path = "test_stage_" + card.lower().replace("-", "_") + "_", "tests/test_existing.py"
    entry = {"must_select_at_least_one": True, "test_files": [path], "required_name_prefix": prefix}
    _check_stage_entry(card, entry, {card}, {path: f"def {prefix}ok(): pass".encode()})
    for invalid in ({}, {path: b""}, {path: b"def test_other(): pass"}):
        with pytest.raises(AssertionError):
            _check_stage_entry(card, entry, {card}, invalid)
    with pytest.raises(AssertionError):
        _check_stage_entry(card, entry | {"required_name_prefix": "wrong_"}, {card}, {path: b""})
    whole = entry | {"selector": "entire existing modules, no -k filtering"}
    _check_stage_entry(card, whole, {card}, {path: b"def test_existing(): pass"})
    for invalid in ({}, {path: b""}, {path: b"def helper(): pass"}):
        with pytest.raises(AssertionError):
            _check_stage_entry(card, whole, {card}, invalid)
    for cards in ({card}, set()):
        with pytest.raises(AssertionError):
            _check_stage_entry(card, whole | {"test_files": []}, cards, {})
        with pytest.raises(AssertionError):
            _check_stage_entry(card, whole, cards, {})
    _check_stage_entry(card, entry, set(), {path: b""})
