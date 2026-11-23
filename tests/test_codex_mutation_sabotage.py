"""L4 AST diff-mutation and mandatory sabotage gate for Codex app-server v2 & Zero-Canon."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_BASE_REV = "18039277c2da6d2e072e7b5fcdb1fc987e1ab154"
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_STRIP_ENV_PREFIXES = ("BRIDGE_", "AGY_", "OPENAI_", "CODEX_")
_KILLER_MAP: Mapping[str, tuple[str, ...]] = {
    "core/stdio_resident/codex_protocol_fsm.py": ("test_codex_app_server_v2_fsm.py", "test_codex_app_server_v2_contract.py"),
    "core/codex_zero_canon_policy.py": ("test_codex_zero_canon_policy.py", "test_codex_l3_incident_corpus.py"),
    "core/zero_canon_http.py": ("test_codex_zero_canon_policy.py", "test_codex_l3_incident_corpus.py"),
    "core/zero_canon_fs.py": ("test_codex_zero_canon_contract.py", "test_codex_l3_incident_corpus.py"),
    "core/stdio_resident/turn_stream.py": ("test_codex_app_server_v2_fsm.py", "test_codex_app_server_v2_contract.py"),
    "core/stdio_resident/turn_error_sse.py": ("test_codex_zero_canon_policy.py", "test_codex_l3_incident_corpus.py"),
    "core/codex_recovery_fsm.py": ("test_codex_app_server_v2_fsm.py", "test_codex_l3_incident_corpus.py"),
    "core/route_catalog_contract.py": ("test_codex_app_server_v2_contract.py", "test_codex_l3_incident_corpus.py"),
}
_SUPPORT_TESTS = ("conftest.py",)
_CRITICAL_SPECS: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    ("any-terminal", "core/stdio_resident/codex_protocol_fsm.py", 'if status == "completed":', 'if status in ("completed", "failed", "interrupted"):', ("test_codex_app_server_v2_fsm.py", "test_codex_app_server_v2_contract.py")),
    ("drop-read-only", "core/stdio_resident/codex_protocol_fsm.py", 'params["sandbox"], params["approvalPolicy"] = "read-only", "never"', 'params["approvalPolicy"] = "never"', ("test_codex_app_server_v2_fsm.py",)),
    ("newline-insertion", "core/stdio_resident/turn_stream.py", "if sep and self._has_emitted_content:", 'sep = sep or "\\n\\n"\n        if sep and self._has_emitted_content:', ("test_codex_app_server_v2_fsm.py", "test_codex_app_server_v2_contract.py")),
    ("stale-turn", "core/stdio_resident/codex_protocol_fsm.py", "if event.epoch is not None and event.epoch != state.epoch:", "if False:", ("test_codex_app_server_v2_fsm.py",)),
    ("incomplete-success", "core/codex_zero_canon_policy.py", 'if phase == "completed" and actual.terminal_status != "completed":', "if False:", ("test_codex_zero_canon_policy.py", "test_codex_l3_incident_corpus.py")),
    ("503-to-502", "core/stdio_resident/turn_error_sse.py", 'return 503, "service_unavailable", "credential_unavailable"', 'return 502, "upstream_error", "resident_turn_failed"', ("test_codex_l3_incident_corpus.py",)),
    ("symlink-barrier", "core/zero_canon_fs.py", 'flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)', 'flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)', ("test_codex_zero_canon_contract.py", "test_codex_l3_incident_corpus.py")),
    ("drop-redaction", "core/stdio_resident/turn_error_sse.py", "redacted = redact_log_text(raw, extra_safe_tokens=_SAFE_ERROR_CODES)", "redacted = raw", ("test_codex_zero_canon_policy.py", "test_codex_l3_incident_corpus.py")),
    ("drop-cap", "core/stdio_resident/turn_stream.py", "if next_total > self._aggregate_output_bytes:", "if False:", ("test_codex_app_server_v2_fsm.py",)),
    ("drop-effort", "core/codex_zero_canon_policy.py", "if norm_effort not in allowed:", "if False:", ("test_codex_zero_canon_policy.py",)),
    ("drop-profile", "core/zero_canon_http.py", 'raise ZeroCanonHttpError("invalid_review_profile", f"unsupported X-Review-Profile: {raw!r}", http_status=400)', "return STANDARD_PROFILE", ("test_codex_zero_canon_policy.py", "test_codex_l3_incident_corpus.py")),
    ("drop-tool-block", "core/codex_zero_canon_policy.py", "if strict and is_upstream_tool_event(event):", "if False:", ("test_codex_zero_canon_policy.py",)),
)


@dataclass(frozen=True, slots=True)
class Mutant:
    """One isolated source mutation with killer test suite and criticality flag."""

    name: str
    path: str
    source: str
    killers: tuple[str, ...]
    critical: bool
    kind: str


@dataclass(frozen=True, slots=True)
class L4Report:
    """Aggregated L4 mutation and sabotage verification outcome."""

    total: int
    killed: int
    survivors: tuple[str, ...]
    surviving_critical: tuple[str, ...]
    timeout_count: int
    generated: int
    invalid: int
    elapsed_s: float
    baseline_ok: bool
    state_leaks: int

    @property
    def kill_rate(self) -> float:
        return self.killed / self.total if self.total else 0.0

    @property
    def invalid_rate(self) -> float:
        return self.invalid / self.generated if self.generated else 0.0

    @property
    def passed(self) -> bool:
        return (
            self.baseline_ok
            and self.total > 0
            and self.kill_rate >= 0.85
            and not self.surviving_critical
            and self.timeout_count == 0
            and self.invalid_rate <= 0.10
            and self.elapsed_s <= 60.0
            and self.state_leaks == 0
        )


def pytest_command(args: Sequence[str]) -> list[str]:
    """Resolve pytest executable using sys.executable when pytest is installed there."""
    if importlib.util.find_spec("pytest") is not None:
        return [sys.executable, "-m", "pytest", *args]
    exe = shutil.which("pytest")
    return [exe, *args] if exe else [sys.executable, "-m", "pytest", *args]


def _kill_owned_pgid(pgid: int) -> None:
    if pgid <= 1 or pgid == os.getpgrp():
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return


def run_cmd_pgid(
    cmd: Sequence[str], cwd: Path, env: Mapping[str, str], timeout_s: float
) -> tuple[int, bool]:
    """Run command in its own process group with guaranteed PGID teardown in finally."""
    proc = subprocess.Popen(
        list(cmd),
        cwd=str(cwd),
        env=dict(env),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    pgid = proc.pid
    timed_out = False
    try:
        return proc.wait(timeout=timeout_s), False
    except subprocess.TimeoutExpired:
        timed_out = True
        return -1, True
    finally:
        if timed_out or proc.poll() is None:
            _kill_owned_pgid(pgid)
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            _kill_owned_pgid(pgid)
            proc.wait()


def tree_digest(root: Path = REPO) -> str:
    """SHA-256 fingerprint of product sources proving the worktree is never mutated."""
    digest = hashlib.sha256()
    files: list[Path] = [root / "fleet.json", root / "server.py"]
    for sub in ("core", "adapters", "scripts", "providers.d"):
        files.extend(p for p in (root / sub).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    for path in sorted(set(files)):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def build_disposable_copy(dst: Path, tests: Sequence[str]) -> None:
    """Create a disposable copy of product code and required tests inside tmp dir."""
    skip = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    for sub in ("core", "adapters", "scripts", "providers.d"):
        if (REPO / sub).is_dir():
            shutil.copytree(REPO / sub, dst / sub, ignore=skip)
    shutil.copy2(REPO / "fleet.json", dst / "fleet.json")
    (dst / "tests").mkdir(parents=True, exist_ok=True)
    for name in sorted({*_SUPPORT_TESTS, *tests}):
        src = REPO / "tests" / name
        if src.is_file():
            shutil.copy2(src, dst / "tests" / name)


def _changed_lines(base_revision: str, paths: Sequence[str]) -> dict[str, set[int]]:
    cmd = ["git", "-C", str(REPO), "diff", "-U0", base_revision, "--", *paths]
    out = subprocess.check_output(cmd, text=True, timeout=15.0)
    result: dict[str, set[int]] = {}
    current = ""
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("@@ ") and current:
            match = _HUNK_RE.match(line)
            if match:
                start = int(match.group(1))
                count = 1 if match.group(2) is None else int(match.group(2))
                if count > 0:
                    result.setdefault(current, set()).update(range(start, start + count))
    return result


def _flip_op(op: ast.cmpop) -> ast.cmpop | None:
    if isinstance(op, ast.Eq):
        return ast.NotEq()
    if isinstance(op, ast.NotEq):
        return ast.Eq()
    if isinstance(op, ast.In):
        return ast.NotIn()
    if isinstance(op, ast.NotIn):
        return ast.In()
    if isinstance(op, ast.Gt):
        return ast.LtE()
    if isinstance(op, ast.Lt):
        return ast.GtE()
    return None


def _mutate_ast_site(tree: ast.Module, idx: int) -> bool:
    nodes = list(ast.walk(tree))
    node = nodes[idx]
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        flipped = _flip_op(node.ops[0])
        if flipped is not None:
            node.ops = [flipped]
            return True
    if isinstance(node, ast.BoolOp):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        return True
    return False


def _ast_mutants_for_file(
    rel: str, lines: set[int], killers: tuple[str, ...], per_file: int
) -> tuple[list[Mutant], int, int]:
    src = (REPO / rel).read_text(encoding="utf-8")
    tree = ast.parse(src, filename=rel)
    sites = [
        (i, getattr(n, "lineno", 0))
        for i, n in enumerate(ast.walk(tree))
        if getattr(n, "lineno", 0) in lines
        and ((isinstance(n, ast.Compare) and len(n.ops) == 1 and _flip_op(n.ops[0]) is not None) or isinstance(n, ast.BoolOp))
    ]
    mutants: list[Mutant] = []
    generated = invalid = 0
    step = max(1, len(sites) // max(1, per_file))
    for site_idx, lineno in sites[::step][:per_file]:
        generated += 1
        cloned = copy.deepcopy(tree)
        if not _mutate_ast_site(cloned, site_idx):
            invalid += 1
            continue
        rendered = ast.unparse(cloned) + "\n"
        try:
            ast.parse(rendered, filename=rel)
        except SyntaxError:
            invalid += 1
            continue
        slug = rel.rsplit("/", 1)[-1].replace(".py", "")
        mutants.append(Mutant(f"ast-{slug}-L{lineno}", rel, rendered, killers, False, "ast_diff"))
    return mutants, generated, invalid


def build_critical_mutants() -> list[Mutant]:
    """Build mandatory ADR-001 critical sabotage mutants with unique fragment check."""
    mutants: list[Mutant] = []
    for name, rel, old, new, killers in _CRITICAL_SPECS:
        src = (REPO / rel).read_text(encoding="utf-8")
        if src.count(old) != 1:
            raise ValueError(f"{name}: expected 1 match in {rel}, got {src.count(old)}")
        mutants.append(Mutant(name, rel, src.replace(old, new, 1), killers, True, "sabotage"))
    return mutants


def generate_ast_diff_mutants(base_revision: str, per_file: int = 1) -> tuple[list[Mutant], int, int]:
    """Generate syntax-validated AST diff mutants on changed executable lines."""
    changed = _changed_lines(base_revision, tuple(_KILLER_MAP))
    mutants: list[Mutant] = []
    generated = invalid = 0
    for rel, killers in _KILLER_MAP.items():
        lines = changed.get(rel)
        if not lines:
            continue
        file_m, gen, inv = _ast_mutants_for_file(rel, lines, killers, per_file)
        mutants.extend(file_m)
        generated += gen
        invalid += inv
    return mutants, generated, invalid


def _run_pytest_in_copy(root: Path, tests: Sequence[str], timeout_s: float) -> tuple[int, bool]:
    iso = root / ".iso_home"
    iso.mkdir(mode=0o700, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(_STRIP_ENV_PREFIXES)}
    env.update(
        HOME=str(iso),
        CODEX_HOME=str(iso / ".codex"),
        XDG_CONFIG_HOME=str(iso / ".config"),
        XDG_DATA_HOME=str(iso / ".local" / "share"),
        XDG_CACHE_HOME=str(iso / ".cache"),
        XDG_STATE_HOME=str(iso / ".local" / "state"),
        PYTHONPATH=str(root),
        PYTHONDONTWRITEBYTECODE="1",
    )
    cmd = pytest_command([*(f"tests/{t}" for t in tests), "-x", "-q", "-p", "no:cacheprovider"])
    return run_cmd_pgid(cmd, root, env, timeout_s)


def _eval_mutant(base: Path, mutant: Mutant, timeout_s: float) -> tuple[str, bool, bool]:
    work = base / mutant.name
    build_disposable_copy(work, mutant.killers)
    (work / mutant.path).write_text(mutant.source, encoding="utf-8")
    rc, timed_out = _run_pytest_in_copy(work, mutant.killers, timeout_s)
    return mutant.name, (rc != 0 and not timed_out), timed_out


def run_l4_gate(
    base: Path, base_revision: str = DEFAULT_BASE_REV, workers: int = 6, timeout_s: float = 20.0
) -> L4Report:
    """Execute baseline + mandatory sabotage + AST diff-mutation strictly in disposable copies."""
    started = time.monotonic()
    before = tree_digest()
    critical = build_critical_mutants()
    ast_mutants, ast_gen, ast_inv = generate_ast_diff_mutants(base_revision, per_file=1)
    mutants = [*critical, *ast_mutants]
    all_tests = tuple(sorted({t for m in mutants for t in m.killers}))
    baseline_dir = base / "baseline"
    build_disposable_copy(baseline_dir, all_tests)
    base_rc, base_to = _run_pytest_in_copy(baseline_dir, all_tests, timeout_s)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(lambda m: _eval_mutant(base, m, timeout_s), mutants))
    survivors = tuple(name for name, killed, timed_out in outcomes if not killed and not timed_out)
    timeouts = sum(1 for _, _, timed_out in outcomes if timed_out) + int(base_to)
    crit_names = {m.name for m in mutants if m.critical}
    surv_crit = tuple(n for n in survivors if n in crit_names)
    return L4Report(
        total=len(mutants),
        killed=sum(1 for _, killed, _ in outcomes if killed),
        survivors=survivors,
        surviving_critical=surv_crit,
        timeout_count=timeouts,
        generated=len(critical) + ast_gen,
        invalid=ast_inv,
        elapsed_s=round(time.monotonic() - started, 3),
        baseline_ok=(base_rc == 0 and not base_to),
        state_leaks=int(tree_digest() != before),
    )


def test_critical_sabotage_fragments_unique_and_complete() -> None:
    """All mandatory ADR-001 sabotage scenarios exist and match uniquely."""
    mutants = build_critical_mutants()
    names = {m.name for m in mutants}
    required = {
        "any-terminal", "drop-read-only", "newline-insertion", "stale-turn",
        "incomplete-success", "503-to-502", "symlink-barrier", "drop-redaction",
        "drop-cap", "drop-effort", "drop-profile", "drop-tool-block",
    }
    assert required <= names and len(mutants) == len(names)


def test_ast_diff_mutant_generation_is_valid() -> None:
    """AST diff-mutation produces valid Python on changed lines with <=10% invalid rate."""
    mutants, generated, invalid = generate_ast_diff_mutants(DEFAULT_BASE_REV, per_file=1)
    assert generated > 0 and len(mutants) > 0
    assert (invalid / generated) <= 0.10


def test_codex_l4_mutation_sabotage_gate(tmp_path: Path) -> None:
    """L4 gate meets kill>=85%, surviving_critical=0, timeouts=0, elapsed<=60s, leaks=0."""
    report = run_l4_gate(tmp_path, base_revision=DEFAULT_BASE_REV)
    assert report.baseline_ok, "baseline copy failed"
    assert report.surviving_critical == (), f"surviving critical: {report.surviving_critical}"
    assert report.kill_rate >= 0.85, f"kill_rate={report.kill_rate:.2f}, survivors={report.survivors}"
    assert report.timeout_count == 0 and report.invalid_rate <= 0.10
    assert report.elapsed_s <= 60.0 and report.state_leaks == 0
