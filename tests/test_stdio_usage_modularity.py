"""VER-004 modularity oracle (M-MOD-I1..I5): LOC, fn LOC, params, CC, purity, monolith net<=0."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NEW_PROD_FILES = (
    "core/turn_usage.py",
    "core/turn_usage_accumulator.py",
    "core/turn_usage_result.py",
    "core/http_usage.py",
    "core/stdio_resident/usage_extract.py",
    "core/stdio_resident/codex_usage.py",
    "core/stdio_resident/routed_turn_result.py",
    "adapters/stdio_resident_delta.py",
)

MODIFIED_SMALL_FILES = (
    "core/usage_wire.py",
    "core/runtime_env.py",
    "core/turn_dispatch.py",
    "core/stdio_resident/protocol_driver.py",
    "core/stdio_resident/turn_stream.py",
    "core/stdio_resident/rpc_drivers.py",
    "core/stdio_resident/claude_driver.py",
    "adapters/stdio_drivers/muse_codec.py",
    "adapters/stdio_drivers/agy_driver.py",
    "adapters/stdio_drivers/opencode_driver.py",
)

PURE_NO_ENV_FILES = (
    "core/turn_usage.py",
    "core/turn_usage_accumulator.py",
    "core/turn_usage_result.py",
    "core/http_usage.py",
    "core/stdio_resident/usage_extract.py",
    "core/stdio_resident/codex_usage.py",
)

ZERO_DIFF_MONOLITHS = (
    "adapters/stdio_drivers/muse_driver.py",
    "core/stdio_resident/session_manager.py",
)

TOUCHED_MONOLITHS = (
    "core/backend_adapter.py",  # REQ-004: `params` в BACKEND_KEYS, added <= deleted
    "core/fleet_compiler.py",
    "core/http_post_routing.py",
    "core/stdio_resident/codex_driver.py",
    "core/stdio_resident/zero_canon_router.py",
    "adapters/stdio_resident_adapter.py",
    "server.py",
)


def _cyclomatic(node: ast.AST) -> int:
    branches = (
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
        ast.With, ast.AsyncWith, ast.IfExp, ast.comprehension,
    )
    score = 1
    for child in ast.walk(node):
        if isinstance(child, branches):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += len(child.values) - 1
    return score


def test_new_prod_files_meet_modularity_caps() -> None:
    for rel in NEW_PROD_FILES:
        path = ROOT / rel
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 250, f"{rel} has {len(lines)} LOC (>250)"
        tree = ast.parse("\n".join(lines), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_loc = (node.end_lineno or node.lineno) - node.lineno + 1
                assert fn_loc <= 50, f"{rel}:{node.name} has {fn_loc} LOC (>50)"
                args = node.args
                total_params = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
                if args.args and args.args[0].arg in ("self", "cls"):
                    total_params -= 1
                assert total_params <= 5 or node.name == "redirect_request", (
                    f"{rel}:{node.name} has {total_params} params (>5)"
                )
                cc = _cyclomatic(node)
                assert cc <= 10, f"{rel}:{node.name} CC={cc} (>10)"


def test_modified_small_files_stay_under_300_loc() -> None:
    for rel in MODIFIED_SMALL_FILES:
        loc = len((ROOT / rel).read_text(encoding="utf-8").splitlines())
        assert loc <= 300, f"{rel} grew to {loc} LOC (>300)"


def test_pure_modules_have_no_os_environ_or_vendor_branching() -> None:
    for rel in PURE_NO_ENV_FILES:
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "os.environ" not in src, f"{rel} must not read os.environ"
    for rel in ("core/turn_usage.py", "core/turn_usage_accumulator.py", "core/turn_usage_result.py", "core/http_usage.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "adapters." not in src, f"{rel} must not import adapters"
        for vendor in ("muse", "claude", "codex", "opencode", "agy"):
            assert vendor not in src.lower(), f"{rel} contains vendor-specific term {vendor!r}"


def test_frozen_monoliths_net_diff_non_positive() -> None:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--numstat", "origin/dev"],
        capture_output=True,
        text=True,
        check=True,
    )
    deltas: dict[str, tuple[int, int]] = {}
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            deltas[parts[2]] = (int(parts[0]), int(parts[1]))
    for rel in ZERO_DIFF_MONOLITHS:
        assert rel not in deltas, f"Zero-diff monolith {rel} was modified: {deltas.get(rel)}"
    for rel in TOUCHED_MONOLITHS:
        if rel in deltas:
            added, deleted = deltas[rel]
            assert added - deleted <= 0, f"Monolith {rel} grew: +{added}/-{deleted}"
