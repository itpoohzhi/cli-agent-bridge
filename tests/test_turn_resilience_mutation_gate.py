"""Mutation / Sabotage Gate (W3-C, Гейт 4): ≥5 диверсий, kill_rate ≥ 85 %, surviving_critical = 0.

Диверсии применяются к КОПИИ кода во временном каталоге (рабочее дерево не мутируется), набор
«убийц» (unit + wiring) обязан покраснеть на каждой. Выживший мутант = дыра в тестах.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mutation_turn_resilience_sabotage import MUTATIONS, REPO, apply_mutation, build_workspace, run_gate, tree_digest


def test_mutations_are_valid_and_cover_critical_branches() -> None:
    """Каждый фрагмент найден ровно один раз; покрыты Go-фразы, commit, kill-switch, 9/10, пауза, retain."""
    assert len(MUTATIONS) >= 5 and len({m.name for m in MUTATIONS}) == len(MUTATIONS)
    for mutation in MUTATIONS:
        source = (REPO / mutation.path).read_text(encoding="utf-8")
        assert source.count(mutation.old) == 1, mutation.name
        assert mutation.old != mutation.new and (REPO / "tests" / mutation.killers[0]).is_file()
    names = {m.name for m in MUTATIONS}
    assert {"go-phrases-off", "keepalive-commit-ban-restored", "kill-switch-bypassed", "failclosed-9of10-weakened", "pause-limit-broken", "retain-guard-off"} <= names


def test_apply_mutation_rejects_ambiguous_fragment(tmp_path: Path) -> None:
    build_workspace(tmp_path / "ws", ["test_failure_window.py"])
    broken = MUTATIONS[0].__class__("x", "core/failure_window.py", "self", "other", ("test_failure_window.py",))
    with pytest.raises(ValueError, match="found"):
        apply_mutation(tmp_path / "ws", broken)


def test_sabotage_gate_kills_all_critical_mutants_without_touching_worktree(tmp_path: Path) -> None:
    before = tree_digest()
    report = run_gate(tmp_path)
    assert report.baseline_ok, "базовая копия обязана быть зелёной, иначе гейт недействителен"
    assert report.surviving_critical == (), f"выжили критичные диверсии: {report.surviving_critical}"
    assert report.kill_rate >= 0.85, f"kill_rate={report.kill_rate:.2f}, выжили: {report.survivors}"
    assert report.state_leaks == 0 and tree_digest() == before
