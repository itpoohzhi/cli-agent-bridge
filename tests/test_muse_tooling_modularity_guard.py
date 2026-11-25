"""AST modularity and architectural boundary guard M-MOD-I1..I5 (VER-006)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from core.stdio_resident.config import StdioPoolConfig

ROOT = Path(__file__).resolve().parents[1]
MONOLITH_CAPS: dict[str, int] = {
    "server.py": 7864,
    "adapters/stdio_drivers/muse_driver.py": 341,
    "core/stdio_resident/codex_driver.py": 572,
    "core/tool_emulation.py": 1981,
}
NEW_MODULE_PREFIXES: tuple[str, ...] = (
    "core.stdio_resident.mcp_tool_capture",
    "core.stdio_resident.mcp_capture_server",
    "core.stdio_resident.tool_turn_outcome",
    "adapters.stdio_drivers.muse_mcp_wire",
)

BND_001: tuple[str, ...] = (
    "core/stdio_resident/mcp_tool_capture.py",
    "core/stdio_resident/tool_turn_outcome.py",
    "core/resident_history.py",
    "core/stdio_resident/codex_protocol_fsm.py",
)
BND_002: tuple[str, ...] = (
    "core/stdio_resident/config.py",
    "core/stdio_resident/routed_turn_result.py",
    "core/stdio_resident/mcp_capture_server.py",
    "core/stdio_resident/runtime_wire.py",
    "core/stdio_resident/resident_runtime.py",
)
BND_003: tuple[str, ...] = (
    "adapters/stdio_resident_delta.py",
    "adapters/stdio_drivers/muse_mcp_wire.py",
    "adapters/stdio_drivers/muse_codec.py",
    "adapters/stdio_drivers/muse_env.py",
    "core/stdio_resident/claude_driver.py",
)
NEW_PRODUCT: tuple[str, ...] = (
    "core/stdio_resident/mcp_tool_capture.py",
    "core/stdio_resident/tool_turn_outcome.py",
    "core/stdio_resident/mcp_capture_server.py",
    "adapters/stdio_drivers/muse_mcp_wire.py",
)
ALL_PRODUCT: tuple[str, ...] = BND_001 + BND_002 + BND_003
MONOLITHS: tuple[str, ...] = (
    "server.py",
    "adapters/stdio_drivers/muse_driver.py",
    "core/stdio_resident/codex_driver.py",
    "core/tool_emulation.py",
)

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _read_lines(rel: str) -> list[str]:
    return (ROOT / rel).read_text(encoding="utf-8").splitlines()


def _nested_line_ranges(fn: FunctionNode) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for child in ast.walk(fn):
        if child is fn:
            continue
        if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            ranges.append((child.lineno, child.end_lineno or child.lineno))
    return ranges


def _own_nodes(fn: FunctionNode) -> list[ast.AST]:
    collected: list[ast.AST] = []
    stack: list[ast.AST] = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        collected.append(node)
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.extend(ast.iter_child_nodes(node))
    return collected


def _own_loc(fn: FunctionNode) -> int:
    start = fn.lineno
    end = fn.end_lineno or start
    nested = _nested_line_ranges(fn)
    return sum(
        1
        for line in range(start, end + 1)
        if not any(lo <= line <= hi for lo, hi in nested)
    )


def _param_count(fn: FunctionNode) -> int:
    args = fn.args
    return (
        len(args.posonlyargs)
        + len(args.args)
        + len(args.kwonlyargs)
        + (1 if args.vararg else 0)
        + (1 if args.kwarg else 0)
    )


def _mccabe(fn: FunctionNode) -> int:
    branches = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.ExceptHandler,
        ast.IfExp,
        ast.With,
        ast.AsyncWith,
    )
    score = 1
    for node in _own_nodes(fn):
        if isinstance(node, branches):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            score += 1 + len(node.ifs)
    return score


def _imports_of(rel: str) -> set[str]:
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"), filename=rel)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def _has_forbidden_import(imports: set[str], forbidden: tuple[str, ...]) -> list[str]:
    return [
        imp
        for imp in sorted(imports)
        if any(imp == bad or imp.startswith(f"{bad}.") for bad in forbidden)
    ]


def test_mod_i1_file_and_function_budgets() -> None:
    """All 14 product files <= 300 LOC; 4 new files <= 240 LOC with bounded functions."""
    for rel in ALL_PRODUCT:
        lines = _read_lines(rel)
        assert len(lines) <= 300, f"{rel}: {len(lines)} > 300"
    for rel in NEW_PRODUCT:
        lines = _read_lines(rel)
        assert len(lines) <= 240, f"{rel}: {len(lines)} > 240"
        tree = ast.parse("\n".join(lines), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                loc = _own_loc(node)
                params = _param_count(node)
                cc = _mccabe(node)
                assert loc <= 50, f"{rel}:{node.name} LOC={loc} > 50"
                assert params <= 6, f"{rel}:{node.name} params={params} > 6"
                assert cc <= 12, f"{rel}:{node.name} McCabe={cc} > 12"


def test_mod_i2_untouched_monoliths() -> None:
    """Frozen monoliths stay within LOC caps and never import new tool-capture modules."""
    for rel in MONOLITHS:
        lines = _read_lines(rel)
        cap = MONOLITH_CAPS[rel]
        assert len(lines) <= cap, f"{rel}: LOC={len(lines)} > cap {cap}"
        bad = _has_forbidden_import(_imports_of(rel), NEW_MODULE_PREFIXES)
        assert not bad, f"{rel} must not import new tool-capture modules: {bad}"


def test_mod_i3_layer_boundaries() -> None:
    """Layer boundaries BND-001..BND-003 and claude_driver isolation hold."""
    bnd1_forbidden = (
        "server",
        "adapters",
        "subprocess",
        "os",
        "http",
        "socket",
        "urllib",
        "httpx",
        "core.stdio_resident.config",
    )
    for rel in BND_001:
        bad = _has_forbidden_import(_imports_of(rel), bnd1_forbidden)
        assert not bad, f"{rel} violates BND-001: {bad}"
    for rel in BND_002:
        bad = _has_forbidden_import(_imports_of(rel), ("server", "adapters"))
        assert not bad, f"{rel} violates BND-002: {bad}"
    for rel in BND_003:
        bad = _has_forbidden_import(_imports_of(rel), ("server",))
        assert not bad, f"{rel} violates BND-003: {bad}"
    claude_forbidden = (
        "adapters",
        "core.stdio_resident.runtime_wire",
        "runtime_wire",
        "core.stdio_resident.resident_runtime",
        "resident_runtime",
        "core.stdio_resident.mcp_capture_server",
        "mcp_capture_server",
    )
    bad_claude = _has_forbidden_import(_imports_of("core/stdio_resident/claude_driver.py"), claude_forbidden)
    assert not bad_claude, f"claude_driver violates isolation: {bad_claude}"


def test_mod_i4_state_ownership_and_defaults() -> None:
    """Single owners for _captured_calls/_structural_calls; kill-switches default False."""
    cap_re = re.compile(r"(?<![A-Za-z0-9_])_captured_calls(?![A-Za-z0-9_])")
    struct_re = re.compile(r"(?<![A-Za-z0-9_])_structural_calls(?![A-Za-z0-9_])")
    cap_owners = [rel for rel in ALL_PRODUCT if cap_re.search((ROOT / rel).read_text(encoding="utf-8"))]
    struct_owners = [rel for rel in ALL_PRODUCT if struct_re.search((ROOT / rel).read_text(encoding="utf-8"))]
    assert cap_owners == ["core/stdio_resident/mcp_tool_capture.py"]
    assert struct_owners == ["core/stdio_resident/tool_turn_outcome.py"]

    cfg = StdioPoolConfig()
    assert cfg.mcp_tool_capture_enabled is False
    assert cfg.suppress_builtin_tools_enabled is False
    assert cfg.clean_cli_home_enabled is False
