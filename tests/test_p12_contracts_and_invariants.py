"""P1.2 final contract, flag-precedence, LOC-bound, and zero-touch invariant tests (W16)."""

from __future__ import annotations

import ast
from pathlib import Path

from core.p12_flag_and_params import (
    ALL_P12_FLAGS,
    PGID_PROVENANCE_GATED_FLAGS,
    resolve_flag,
    resolve_flag_with_params,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

NEW_P12_MODULES = (
    "core/p12_flag_and_params.py",
    "core/pgid_cleanup_policy.py",
    "core/pgid_cleanup_driver.py",
    "core/pgid_reaper.py",
    "core/turn_mode_cancel_policy.py",
    "core/p12_hub_cancel_seam.py",
    "bridges/agy-bridge/agy_runtime/orphan_coordinator.py",
    "bridges/agy-bridge/agy_runtime/p12_cleanup_seam.py",
    "bridges/opencode-zen-bridge/zen_bridge/p12_cleanup_seam.py",
)

ZERO_IO_MODULES = (
    "core/p12_flag_and_params.py",
    "core/pgid_cleanup_policy.py",
    "core/turn_mode_cancel_policy.py",
    "bridges/agy-bridge/agy_runtime/orphan_coordinator.py",
)

FORBIDDEN_ZERO_IO = frozenset({"os", "subprocess", "socket", "time", "selectors", "select", "ctypes", "pathlib"})


def test_all_seven_p12_flags_default_false_and_param_source_scoping() -> None:
    assert len(ALL_P12_FLAGS) == 7
    for flag in ALL_P12_FLAGS:
        res = resolve_flag(flag, None, {})
        assert res.enabled is False
        assert res.origin == "default_false"
        # Dynamic JSON False overrides env True
        res_override = resolve_flag(flag, {flag: False}, {flag: "1"})
        assert res_override.enabled is False
        # ParamSourceMissing disables ONLY #1-#2, never #3-#7
        res_missing = resolve_flag_with_params(flag, {flag: True}, {}, None)
        if flag in PGID_PROVENANCE_GATED_FLAGS:
            assert res_missing.enabled is False
            assert res_missing.origin == "param_source_missing"
        else:
            assert res_missing.enabled is True


def _has_waitpid_negative_call(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            is_wp = (isinstance(fn, ast.Attribute) and fn.attr == "waitpid") or (
                isinstance(fn, ast.Name) and fn.id == "waitpid"
            )
            if is_wp and node.args and isinstance(node.args[0], ast.UnaryOp) and isinstance(node.args[0].op, ast.USub):
                return True
    return False


def test_zero_waitpid_negative_pgid_in_core_agy_and_zen() -> None:
    scan_roots = (
        REPO_ROOT / "core",
        REPO_ROOT / "bridges" / "agy-bridge",
        REPO_ROOT / "bridges" / "opencode-zen-bridge",
    )
    hits: list[str] = []
    for root in scan_roots:
        for py in root.rglob("*.py"):
            if "tests" in py.parts:
                continue
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"), filename=str(py))
            if _has_waitpid_negative_call(tree):
                hits.append(str(py.relative_to(REPO_ROOT)))
    assert hits == [], f"Forbidden os.waitpid(-pgid) call found in: {hits}"


def test_dead_detach_on_disconnect_removed_from_hub_handler() -> None:
    srv_src = (REPO_ROOT / "server.py").read_text(encoding="utf-8")
    assert "_detach_on_disconnect" not in srv_src


def test_new_p12_modules_within_300_loc_and_zero_io_pure() -> None:
    for rel in NEW_P12_MODULES:
        p = REPO_ROOT / rel
        assert p.is_file(), f"Missing module {rel}"
        loc = p.read_bytes().count(b"\n")
        assert loc <= 300, f"{rel} has {loc} LOC > 300"
    for rel in ZERO_IO_MODULES:
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in FORBIDDEN_ZERO_IO
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in FORBIDDEN_ZERO_IO


def test_admission_limit_128_and_health_contract_untouched() -> None:
    srv_src = (REPO_ROOT / "server.py").read_text(encoding="utf-8")
    # /health schema must not add new top-level P1.2 keys
    assert "pgid_quarantined" not in srv_src
    assert "p12_reaper" not in srv_src
    # Admission bound 128 in BoundedPgidReaper must match BRIDGE_ADMISSION_LIMIT=128
    from core.pgid_reaper import DEFAULT_REAPER_BOUND
    assert DEFAULT_REAPER_BOUND == 128
