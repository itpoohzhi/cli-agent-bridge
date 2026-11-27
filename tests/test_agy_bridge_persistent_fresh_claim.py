"""Тесты чистого модуля persistent_fresh_claim: таблица, инварианты, AST, perf."""

# pyright: basic
from __future__ import annotations

import ast
import importlib.util
import itertools
import sys
import time
from pathlib import Path

import pytest

_SRC = (
    Path(__file__)
    .resolve()
    .parents[1]
    .joinpath("bridges", "agy-bridge", "agy_runtime", "persistent_fresh_claim.py")
)
_ALLOWED_IMPORTS = {"__future__", "dataclasses", "enum", "typing"}
TURNS = (-1, 0, 1, 30)
GENS = (-1, 0, 1, 2)
BOOLS = (False, True)


def _load():
    """Загружает модуль по пути файла (каталог bridges/agy-bridge не пакет)."""
    name = "_agy_persistent_fresh_claim_under_test"
    spec = importlib.util.spec_from_file_location(name, _SRC)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_M = _load()
State = _M.FreshClaimState
Verdict = _M.FreshClaimVerdict
Lease = _M.LeaseFacts
Claim = _M.ClaimInput


def _leases():
    combos = itertools.product(TURNS, BOOLS, BOOLS, GENS)
    return [
        Lease(turns_before=t, reused=r, standby_claimed=s, generation=g)
        for t, r, s, g in combos
    ]


def _all_inputs():
    leases = [*_leases(), None]
    grid = itertools.product(BOOLS, BOOLS, (0, 1), leases)
    return [Claim(has_cid=c, enabled=e, attempt=a, lease=ls) for c, e, a, ls in grid]


def _expected_verdict(has_cid, lease):
    """Эталон классификации, записанный независимо от реализации."""
    if lease is None:
        return Verdict.NO_LEASE
    if has_cid:
        return Verdict.KEEP_RESUME
    turns = lease.turns_before
    if turns < 0 or lease.generation < 0:
        return Verdict.ROTATE_INVALID
    if turns == 0 and lease.standby_claimed:
        return Verdict.KEEP_STANDBY
    if turns > 0:
        return Verdict.ROTATE_HISTORY
    return Verdict.ROTATE_REUSED if lease.reused else Verdict.KEEP_FRESH


def _expected(inp):
    """Эталонное решение: (verdict, discard, reacquire, cold, next, shadow)."""
    verdict = _expected_verdict(inp.has_cid, inp.lease)
    if not verdict.name.startswith("ROTATE_"):
        return (verdict, False, False, False, State.DONE_KEEP, False)
    if not inp.enabled:
        return (verdict, False, False, False, State.DONE_KEEP, True)
    if inp.attempt == 0:
        return (verdict, True, True, False, State.ROTATED_ONCE, False)
    return (verdict, True, False, True, State.DONE_COLD_FALLBACK, False)


def _fields(d):
    return (
        d.verdict,
        d.discard_current,
        d.reacquire,
        d.cold_fallback,
        d.next_state,
        d.shadow_would_rotate,
    )


def _decide(lease, *, has_cid=False, enabled=True, attempt=0):
    inp = Claim(has_cid=has_cid, enabled=enabled, attempt=attempt, lease=lease)
    return _M.decide_fresh_claim(inp)


def test_full_grid_decision_matches_reference():
    inputs = _all_inputs()
    assert len(inputs) == 520
    for inp in inputs:
        assert _fields(_M.decide_fresh_claim(inp)) == _expected(inp), inp


def test_full_grid_classification_matches_reference():
    for has_cid in BOOLS:
        for lease in [*_leases(), None]:
            got = _M.classify_fresh_lease(has_cid, lease)
            assert got == _expected_verdict(has_cid, lease), (has_cid, lease)


def test_standby_turn0_is_kept_not_rotated():
    lease = Lease(turns_before=0, reused=True, standby_claimed=True, generation=1)
    d = _decide(lease, has_cid=False, enabled=True)
    assert d.verdict == Verdict.KEEP_STANDBY
    assert d.discard_current is False
    assert d.reacquire is False
    assert d.cold_fallback is False


def test_history_beats_standby_flag():
    lease = Lease(turns_before=1, reused=True, standby_claimed=True, generation=1)
    d = _decide(lease)
    assert d.verdict == Verdict.ROTATE_HISTORY
    assert d.discard_current is True


def test_none_lease_and_cid_resume_never_rotate():
    assert _decide(None).verdict == Verdict.NO_LEASE
    lease = Lease(turns_before=30, reused=True, standby_claimed=False, generation=2)
    d = _decide(lease, has_cid=True)
    assert d.verdict == Verdict.KEEP_RESUME
    assert d.discard_current is False


@pytest.mark.parametrize("attempt", [0, 1])
def test_shadow_mode_never_discards(attempt):
    rotate_leases = (
        Lease(turns_before=1, reused=False, standby_claimed=False, generation=1),
        Lease(turns_before=0, reused=True, standby_claimed=False, generation=1),
        Lease(turns_before=-1, reused=False, standby_claimed=False, generation=0),
    )
    for lease in rotate_leases:
        d = _decide(lease, enabled=False, attempt=attempt)
        assert d.verdict.name.startswith("ROTATE_")
        assert d.discard_current is False
        assert d.reacquire is False
        assert d.cold_fallback is False
        assert d.shadow_would_rotate is True
        assert d.next_state == State.DONE_KEEP


def test_shadow_flag_false_for_keep_verdicts():
    lease = Lease(turns_before=0, reused=False, standby_claimed=False, generation=1)
    d = _decide(lease, enabled=False)
    assert d.verdict == Verdict.KEEP_FRESH
    assert d.shadow_would_rotate is False


def test_first_attempt_rotates_and_reacquires():
    lease = Lease(turns_before=3, reused=True, standby_claimed=False, generation=1)
    d = _decide(lease, attempt=0)
    assert d.discard_current is True
    assert d.reacquire is True
    assert d.cold_fallback is False
    assert d.next_state == State.ROTATED_ONCE


def test_second_attempt_fails_closed_to_cold():
    lease = Lease(turns_before=3, reused=True, standby_claimed=False, generation=1)
    d = _decide(lease, attempt=1)
    assert d.discard_current is True
    assert d.reacquire is False
    assert d.cold_fallback is True
    assert d.next_state == State.DONE_COLD_FALLBACK


@pytest.mark.parametrize("attempt", [-1, 2, 99])
def test_invalid_attempt_raises(attempt):
    with pytest.raises(ValueError, match="attempt must be 0 or 1"):
        _decide(None, attempt=attempt)


def test_transition_table_is_total_for_live_states():
    table = _M.FRESH_CLAIM_TRANSITIONS
    for state in (State.INITIAL, State.ROTATED_ONCE):
        for verdict in Verdict:
            assert (state, verdict) in table
    assert len(table) == 2 * len(Verdict)


def test_transition_from_terminal_state_raises():
    for state in (State.DONE_KEEP, State.DONE_COLD_FALLBACK):
        with pytest.raises(ValueError, match="invalid transition"):
            _M.next_fresh_claim_state(state, Verdict.KEEP_FRESH)


def test_ast_imports_are_pure():
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            roots.add((node.module or "").split(".")[0])
    assert roots <= _ALLOWED_IMPORTS, roots - _ALLOWED_IMPORTS


def test_ast_size_limits():
    text = _SRC.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 150
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        assert node.end_lineno is not None
        assert node.end_lineno - node.lineno + 1 <= 40, node.name
        a = node.args
        count = len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs)
        count += int(a.vararg is not None) + int(a.kwarg is not None)
        assert count <= 5, node.name


def test_decide_perf_mean_and_p99():
    """CLM-08 / N-4: 100 000 вызовов, среднее < 50 мкс, p99 батча < 500 мкс."""
    inputs = _all_inputs()
    size = len(inputs)
    decide = _M.decide_fresh_claim
    batches = []
    for b in range(100):
        start = time.perf_counter()
        for i in range(1000):
            decide(inputs[(b * 1000 + i) % size])
        batches.append((time.perf_counter() - start) / 1000)
    mean_s = sum(batches) / len(batches)
    p99_s = sorted(batches)[98]
    assert mean_s < 50e-6, mean_s
    assert p99_s < 500e-6, p99_s
