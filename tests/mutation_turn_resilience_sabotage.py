"""Диверсии (Mutation / Sabotage Gate, Гейт 4): целевые поломки критических веток устойчивости хода.

Каждая диверсия — точная текстовая замена ОДНОГО фрагмента в КОПИИ кода (`tmp_path`); рабочее
дерево не мутируется. Копия гоняет набор «убийц» (unit + wiring), красный прогон = мутант убит.
Выжившая критичная диверсия означает дыру в тестах (`surviving_critical`).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SUPPORT = ("conftest.py", "resilience_wiring_support.py", "agy_stub_agent.py")
FACADE = "core/turn_resilience_facade.py"
POLICY = "core/tool_call_recovery_policy.py"
RETRY = "core/invisible_retry_policy.py"
WIRING = ("test_agy_bridge_transport_wiring.py", "test_agy_bridge_retry_gate_wiring.py", "test_agy_bridge_toolcall_recovery_wiring.py")


@dataclass(frozen=True)
class Mutation:
    """Одна диверсия: файл, точный фрагмент, замена и тесты-убийцы."""

    name: str
    path: str
    old: str
    new: str
    killers: tuple[str, ...]
    critical: bool = True


def _m(name: str, path: str, old: str, new: str, *killers: str) -> Mutation:
    return Mutation(name, path, old, new, killers)


MUTATIONS: tuple[Mutation, ...] = (
    _m("go-phrases-off", "core/transport_failure_contracts.py", '    r":\\s*eof\\b",\n', "", "test_transport_failure_classifier.py", WIRING[0]),
    _m("fm09-veto-off", "core/transport_failure_classifier.py", '    if hit:\n        return FailureClassification(FailureKind.FATAL, "fatal_veto", hit)\n', "", "test_transport_failure_classifier.py", WIRING[0]),
    _m("keepalive-commit-ban-restored", FACADE, "    relaxed = _flags().keepalive_only_preretry and isinstance(tracker, ContentDeliveryTracker)\n", "    relaxed = False\n", WIRING[1]),
    _m("non-network-relax", FACADE, "    return kind is FailureKind.NETWORK_TRANSIENT or (isinstance(text, str) and is_transient_stream_interruption(text))\n", "    return True\n", WIRING[1]),
    _m("kill-switch-bypassed", FACADE, "    if not _flags().transport_failure_classifier:\n        return False\n", "", WIRING[0]),
    _m("mask-always-on", FACADE, "        if not isinstance(body, dict) or not _flags().vendor_retry_phrase_mask:\n            return body\n", "        if not isinstance(body, dict):\n            return body\n", WIRING[2], "test_turn_resilience_adversarial.py"),
    _m("once-per-turn-off", FACADE, "    if tracker is None or ctx.get(_RECOVERY_KEY) or not tracker.try_begin_recovery():\n        return\n", "    if tracker is None:\n        return\n", WIRING[2]),
    _m("inv-s2-complete-ignored", FACADE, '        complete = str(rec.get("status") or "").upper() in _COMPLETE_STATUSES\n', "        complete = True\n", WIRING[2]),
    _m("failclosed-9of10-weakened", POLICY, "    if odd or keys[:half] != keys[half:] or len(set(keys[:half])) != half:\n", "    if len(set(keys[:half])) != half:\n", "test_tool_call_recovery_policy.py", WIRING[2]),
    _m("inv-s1-delivery-off", POLICY, '    if facts is not None and (facts.tool_events > 0 or facts.content_bytes > 0 or facts.tool_calls > 0):\n        return "client_output_already_delivered"\n', "", "test_tool_call_recovery_policy.py", WIRING[2]),
    _m("inv-s1-toolcalls-ignored", POLICY, "    if facts is not None and (facts.tool_events > 0 or facts.content_bytes > 0 or facts.tool_calls > 0):\n", "    if facts is not None and (facts.tool_events > 0 or facts.content_bytes > 0):\n", WIRING[2]),
    _m("pause-limit-broken", RETRY, "    return min(pause_max, pause_max * _unit(state.jitter_unit) + correlated)\n", "    return pause_max * _unit(state.jitter_unit) + correlated\n", "test_invisible_retry_policy.py", WIRING[0]),
    _m("budget-gate-off", RETRY, '    if remaining <= 0.0 or elapsed + pause + last > total:\n        return _deny("budget_exhausted")\n', '    if False:\n        return _deny("budget_exhausted")\n', "test_invisible_retry_policy.py", WIRING[1]),
    _m("retain-guard-off", "core/hot_session_retention_policy.py", '    if type(facts.turns) is not int or facts.turns != 0:\n        return HotSessionDecision(False, "session_mutated_turns")\n', "", "test_hot_session_retention_policy.py", WIRING[1]),
    _m("window-ttl-broken", "core/failure_window.py", "        horizon = now - span\n", "        horizon = now - span * 1e9\n", "test_failure_window.py", "test_turn_resilience_adversarial.py"),
    _m("flag-veto-broken", "core/recovery_flags.py", "    return bool(votes) and all(votes)\n", "    return bool(votes) and any(votes)\n", "test_recovery_flags.py", "test_turn_resilience_adversarial.py"),
)


@dataclass(frozen=True)
class GateReport:
    """Итог гейта: число убитых/выживших диверсий, выжившие критичные и утечки в рабочее дерево."""

    total: int
    killed: int
    survivors: tuple[str, ...]
    surviving_critical: tuple[str, ...]
    baseline_ok: bool
    state_leaks: int

    @property
    def kill_rate(self) -> float:
        return self.killed / self.total if self.total else 0.0


def tree_digest(root: Path = REPO) -> str:
    """Отпечаток исходников `core/` и монолита: доказательство, что рабочее дерево не мутировано."""
    digest = hashlib.sha256()
    for path in sorted([*(root / "core").glob("*.py"), root / "bridges" / "agy-bridge" / "server.py"]):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build_workspace(dst: Path, tests: Sequence[str]) -> None:
    """Скопировать `core/`, мост и нужные тесты в изолированный каталог (без `.git`, кэшей)."""
    skip = shutil.ignore_patterns("__pycache__", "workspace", "*.pyc")
    shutil.copytree(REPO / "core", dst / "core", ignore=skip)
    shutil.copytree(REPO / "bridges" / "agy-bridge", dst / "bridges" / "agy-bridge", ignore=skip)
    (dst / "tests").mkdir()
    for name in {*SUPPORT, *tests}:
        shutil.copy2(REPO / "tests" / name, dst / "tests" / name)


def apply_mutation(root: Path, mutation: Mutation) -> None:
    """Применить замену; фрагмент обязан встречаться ровно один раз (иначе диверсия невалидна)."""
    target = root / mutation.path
    source = target.read_text(encoding="utf-8")
    if source.count(mutation.old) != 1:
        raise ValueError(f"{mutation.name}: fragment found {source.count(mutation.old)} times in {mutation.path}")
    target.write_text(source.replace(mutation.old, mutation.new), encoding="utf-8")


def run_tests(root: Path, tests: Sequence[str]) -> int:
    """pytest в копии; возвращает код выхода (0 — мутант выжил)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("BRIDGE_", "AGY_"))}
    env.update(PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1", HOME=str(root))
    cmd = [sys.executable, "-m", "pytest", *(f"tests/{t}" for t in tests), "-x", "-q", "-p", "no:cacheprovider"]
    return subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, timeout=300, check=False).returncode  # noqa: S603


def _judge(base: Path, mutation: Mutation) -> tuple[str, bool]:
    root = base / mutation.name
    build_workspace(root, mutation.killers)
    apply_mutation(root, mutation)
    return mutation.name, run_tests(root, mutation.killers) != 0


def run_gate(base: Path, mutations: Sequence[Mutation] = MUTATIONS, workers: int = 4) -> GateReport:
    """Базовый прогон на неизменённой копии, затем диверсии параллельно; рабочее дерево не трогается."""
    before = tree_digest()
    every = tuple(sorted({t for m in mutations for t in m.killers}))
    build_workspace(base / "baseline", every)
    baseline_ok = run_tests(base / "baseline", every) == 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        verdicts = dict(pool.map(lambda m: _judge(base, m), mutations))
    survivors = tuple(n for n, killed in verdicts.items() if not killed)
    critical = tuple(m.name for m in mutations if m.critical and m.name in survivors)
    return GateReport(len(mutations), len(mutations) - len(survivors), survivors, critical, baseline_ok, int(tree_digest() != before))
