#!/usr/bin/env python3
"""Verification runner for Codex v2 & Zero-Canon gates: L0, L3, L4, and M-MOD."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._codex_mmod_check import (  # noqa: E402
    PURE_MODULES,
    check_pure_zero_io,
    git_changed_py,
    run_m_mod,
    run_pgid,
)
from tests import test_codex_mutation_sabotage as l4_mod  # noqa: E402

DEFAULT_BASE_REV = "18039277c2da6d2e072e7b5fcdb1fc987e1ab154"
REAL_SECRET_RE = re.compile(r"\bsk-(?:proj|live)-[A-Za-z0-9_-]{12,}\b")
L3_TESTS = (
    "tests/test_codex_l3_incident_corpus.py",
    "tests/test_codex_app_server_v2_contract.py",
    "tests/test_codex_app_server_v2_fsm.py",
    "tests/test_codex_zero_canon_contract.py",
    "tests/test_codex_zero_canon_policy.py",
    "tests/test_codex_catalogue_contract.py",
    "tests/test_stdio_process_io.py",
    "tests/test_stdio_resident_codex.py",
    "tests/test_subbridge_zero_canon_domain.py",
    "tests/test_subbridge_zero_canon_runtime.py",
)


def _check_ruff_and_secrets(files: Sequence[str]) -> tuple[bool, list[str], str]:
    ruff_exe = shutil.which("ruff")
    rc, out, err = run_pgid([ruff_exe, "check", *files], ROOT) if ruff_exe and files else (0, "", "")
    secret_hits = [p for p in files if REAL_SECRET_RE.search((ROOT / p).read_text(encoding="utf-8"))]
    return rc == 0, secret_hits, (out or err).strip()


def _collect_pure_zero_io_issues() -> list[str]:
    issues: list[str] = []
    for rel in sorted(PURE_MODULES):
        path = ROOT / rel
        if path.is_file():
            issues.extend(check_pure_zero_io(rel, ast.parse(path.read_text(encoding="utf-8"))))
    return issues


def run_l0(base_revision: str) -> tuple[bool, dict[str, Any]]:
    """Run L0 static verification: catalog sync, schemas, ruff, secrets, and pure Zero-I/O."""
    sync_rc, sync_out, sync_err = run_pgid([sys.executable, "scripts/sync_codex_catalog.py", "--check", "--json"], ROOT)
    codex_yaml = yaml.safe_load((ROOT / "providers.d" / "codex.yaml").read_text(encoding="utf-8"))
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    no_62_alias = "gpt-6.2-sol" not in fleet.get("aliases", {})
    sol_efforts = codex_yaml["models_overrides"]["gpt-6.1-sol"]["efforts"] == ["low", "medium", "high", "xhigh", "max"]
    ruff_ok, secret_hits, ruff_detail = _check_ruff_and_secrets(git_changed_py(base_revision))
    pure_issues = _collect_pure_zero_io_issues()
    ok = all((sync_rc == 0, no_62_alias, sol_efforts, ruff_ok, not secret_hits, not pure_issues))
    return ok, {
        "level": "L0",
        "ok": ok,
        "catalog_sync_ok": sync_rc == 0,
        "no_gpt_6_2_sol_alias": no_62_alias,
        "sol_efforts_ok": sol_efforts,
        "ruff_ok": ruff_ok,
        "secret_hits": secret_hits,
        "pure_zero_io_issues": pure_issues,
        "detail": (sync_out or sync_err or ruff_detail).strip()[:240],
    }


def run_l3(base_revision: str) -> tuple[bool, dict[str, Any]]:
    """Run L3 incident corpus and Codex contract suite in an isolated disposable HOME."""
    started = time.monotonic()
    before = l4_mod.tree_digest(ROOT)
    sync_rc, _, sync_err = run_pgid([sys.executable, "scripts/sync_codex_catalog.py", "--check"], ROOT)
    suite = [t for t in L3_TESTS if (ROOT / t).is_file()]
    with tempfile.TemporaryDirectory(prefix="codex-l3-") as tmp:
        iso = Path(tmp) / "home"
        iso.mkdir(mode=0o700)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BRIDGE_", "AGY_", "OPENAI_", "CODEX_"))}
        env.update(
            HOME=str(iso), CODEX_HOME=str(iso / ".codex"), XDG_CONFIG_HOME=str(iso / ".config"),
            XDG_DATA_HOME=str(iso / ".local" / "share"), XDG_CACHE_HOME=str(iso / ".cache"),
            XDG_STATE_HOME=str(iso / ".local" / "state"), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
        )
        rc, out, err = run_pgid(l4_mod.pytest_command([*suite, "-q", "-p", "no:cacheprovider"]), ROOT, env, 90.0)
    leaks = int(l4_mod.tree_digest(ROOT) != before)
    ok = sync_rc == 0 and rc == 0 and leaks == 0
    return ok, {
        "level": "L3",
        "base_revision": base_revision,
        "ok": ok,
        "catalog_sync_ok": sync_rc == 0,
        "tests_run": len(suite),
        "state_leaks": leaks,
        "elapsed_s": round(time.monotonic() - started, 3),
        "summary": (out.strip().splitlines()[-1] if out.strip() else (err or sync_err).strip()[:200]),
    }


def run_l4(base_revision: str) -> tuple[bool, dict[str, Any]]:
    """Run L4 AST diff-mutation and critical sabotage in a disposable temporary directory."""
    with tempfile.TemporaryDirectory(prefix="codex-l4-") as tmp:
        rep = l4_mod.run_l4_gate(Path(tmp), base_revision=base_revision)
    return rep.passed, {
        "level": "L4",
        "base_revision": base_revision,
        "ok": rep.passed,
        "baseline_ok": rep.baseline_ok,
        "total": rep.total,
        "killed": rep.killed,
        "kill_rate": round(rep.kill_rate, 4),
        "survivors": list(rep.survivors),
        "surviving_critical": list(rep.surviving_critical),
        "timeout_count": rep.timeout_count,
        "generated": rep.generated,
        "invalid": rep.invalid,
        "invalid_rate": round(rep.invalid_rate, 4),
        "elapsed_s": rep.elapsed_s,
        "state_leaks": rep.state_leaks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Codex v2 L0/L3/L4/M-MOD gates.")
    parser.add_argument("--level", required=True, choices=("L0", "L3", "L4", "M-MOD"))
    parser.add_argument("--base-revision", default=DEFAULT_BASE_REV)
    parser.add_argument("--paths", nargs="*", default=())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.level == "L0":
        ok, payload = run_l0(args.base_revision)
    elif args.level == "L3":
        ok, payload = run_l3(args.base_revision)
    elif args.level == "L4":
        ok, payload = run_l4(args.base_revision)
    else:
        ok, payload = run_m_mod(args.base_revision, args.paths)
    stream = sys.stdout if ok else sys.stderr
    print(json.dumps(payload, sort_keys=True, ensure_ascii=False), file=stream)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
