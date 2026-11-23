"""L4 AST diff-mutation and mandatory sabotage gate for Codex app-server v2 & Zero-Canon."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tests._codex_l4_engine import (
    REPO as REPO,
)
from tests._codex_l4_engine import (
    L4Report as L4Report,
)
from tests._codex_l4_engine import (
    Mutant as Mutant,
)
from tests._codex_l4_engine import (
    ast_mutants_for_file,
    changed_lines,
    eval_mutant,
    run_pytest_in_copy,
)
from tests._codex_l4_engine import (
    build_disposable_copy as build_disposable_copy,
)
from tests._codex_l4_engine import (
    pytest_command as pytest_command,
)
from tests._codex_l4_engine import (
    run_cmd_pgid as run_cmd_pgid,
)
from tests._codex_l4_engine import (
    tree_digest as tree_digest,
)

DEFAULT_BASE_REV = "18039277c2da6d2e072e7b5fcdb1fc987e1ab154"
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
    changed = changed_lines(base_revision, tuple(_KILLER_MAP))
    mutants: list[Mutant] = []
    generated = invalid = 0
    for rel, killers in _KILLER_MAP.items():
        lines = changed.get(rel)
        if not lines:
            continue
        file_m, gen, inv = ast_mutants_for_file(rel, lines, killers, per_file)
        mutants.extend(file_m)
        generated += gen
        invalid += inv
    return mutants, generated, invalid


def _collect_outcome_stats(
    mutants: Sequence[Mutant], outcomes: Sequence[tuple[str, bool, bool]]
) -> tuple[int, tuple[str, ...], tuple[str, ...], int]:
    crit_names = {m.name for m in mutants if m.critical}
    killed_n, timeout_n = 0, 0
    survivors: list[str] = []
    surv_crit: list[str] = []
    for name, killed, timed_out in outcomes:
        if killed:
            killed_n += 1
        elif timed_out:
            timeout_n += 1
        else:
            survivors.append(name)
            if name in crit_names:
                surv_crit.append(name)
    return killed_n, tuple(survivors), tuple(surv_crit), timeout_n


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
    base_rc, base_to = run_pytest_in_copy(baseline_dir, all_tests, timeout_s)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(lambda m: eval_mutant(base, m, timeout_s), mutants))
    killed, survivors, surv_crit, timeouts = _collect_outcome_stats(mutants, outcomes)
    return L4Report(
        total=len(mutants),
        killed=killed,
        survivors=survivors,
        surviving_critical=surv_crit,
        timeout_count=timeouts + int(base_to),
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
