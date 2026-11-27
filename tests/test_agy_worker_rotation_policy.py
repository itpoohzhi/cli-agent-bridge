"""W1-B: чистая политика ротации слотов (VER-005, AD-001/AD-002).

Детерминированные unit-тесты домена: 0 сокетов, 0 sleep, 0 env-доступа.
Legacy-режим (strict=False) обязан воспроизводить дофиксовые вердикты.
"""

from __future__ import annotations

import ast
import dataclasses
import itertools
import sys
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
AGY_BRIDGE: Final = ROOT / "bridges" / "agy-bridge"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AGY_BRIDGE) not in sys.path:
    sys.path.append(str(AGY_BRIDGE))

from agy_runtime.worker_rotation_policy import (  # noqa: E402
    ReuseProbe,
    SlotBinding,
    SlotReuseVerdict,
    decide_slot_reuse,
)

V: Final = SlotReuseVerdict


def _bound(cid: str, turns: int = 1) -> SlotBinding:
    return SlotBinding(turns=turns, bound_cid=cid)


@pytest.mark.parametrize("base_idx", [1, 7, 10_000])
@pytest.mark.parametrize("turns", [0, 1, 30])
def test_strict_reuse_only_with_full_conjunction(base_idx: int, turns: int) -> None:
    probe = ReuseProbe(strict=True, reused=True, run_cid="cid-a", resume_base_idx=base_idx)
    assert decide_slot_reuse(probe, _bound("cid-a", turns)) is V.REUSE


@pytest.mark.parametrize(
    ("probe", "binding", "expected"),
    [
        # AD-001: холодный запрос (пустой run_cid) никогда не reuse-ит живой слот.
        (ReuseProbe(reused=True, run_cid=""), None, V.ROTATE_COLD),
        (ReuseProbe(reused=True, run_cid=""), _bound(""), V.ROTATE_COLD),
        (ReuseProbe(reused=True, run_cid=""), _bound("cid-a"), V.ROTATE_COLD),
        # AD-002: несовпадение cid, включая отсутствие/пустоту привязки.
        (ReuseProbe(reused=True, run_cid="cid-b", resume_base_idx=3), _bound("cid-a"), V.ROTATE_MISMATCH),
        (ReuseProbe(reused=True, run_cid="cid-a", resume_base_idx=3), None, V.ROTATE_MISMATCH),
        (ReuseProbe(reused=True, run_cid="cid-a", resume_base_idx=3), _bound(""), V.ROTATE_MISMATCH),
        # AD-002: cid совпал, но pre-spawn якорь не доказан (base_idx <= 0).
        (ReuseProbe(reused=True, run_cid="cid-a", resume_base_idx=0), _bound("cid-a"), V.ROTATE_UNANCHORED),
        (ReuseProbe(reused=True, run_cid="cid-a", resume_base_idx=-1), _bound("cid-a"), V.ROTATE_UNANCHORED),
    ],
)
def test_strict_rotations(
    probe: ReuseProbe, binding: SlotBinding | None, expected: SlotReuseVerdict
) -> None:
    assert decide_slot_reuse(probe, binding) is expected
    assert expected.evicts_slot is True


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("run_cid", ["", "cid-a"])
@pytest.mark.parametrize("binding", [None, _bound("cid-a"), _bound("cid-b")])
def test_fresh_slot_never_rotates(
    strict: bool, run_cid: str, binding: SlotBinding | None
) -> None:
    probe = ReuseProbe(strict=strict, reused=False, run_cid=run_cid, resume_base_idx=0)
    assert decide_slot_reuse(probe, binding) is V.FRESH


@pytest.mark.parametrize("reused", [True, False])
@pytest.mark.parametrize("run_cid", ["", "cid-a", "cid-b"])
@pytest.mark.parametrize("base_idx", [-1, 0, 5])
@pytest.mark.parametrize("binding", [None, _bound("cid-a"), _bound("cid-b")])
def test_legacy_mode_reproduces_pre_fix_verdicts(
    reused: bool, run_cid: str, base_idx: int, binding: SlotBinding | None
) -> None:
    """Дофиксовое правило: reused = turns_before > 0 or generation > 0."""
    probe = ReuseProbe(strict=False, reused=reused, run_cid=run_cid, resume_base_idx=base_idx)
    pre_fix = V.REUSE if reused else V.FRESH
    assert decide_slot_reuse(probe, binding) is pre_fix


_GRID_BINDINGS: Final = (None, SlotBinding(), _bound("cid-a"), _bound("cid-b", 3))
_GRID_PROBES: Final = tuple(
    ReuseProbe(strict=strict, reused=reused, run_cid=cid, resume_base_idx=base)
    for strict, reused, cid, base in itertools.product(
        (True, False), (True, False), ("", "cid-a", "cid-b"), (-1, 0, 1, 9)
    )
)


def _verdicts_in_order(
    probes: tuple[ReuseProbe, ...], bindings: tuple[SlotBinding | None, ...]
) -> list[SlotReuseVerdict]:
    return [decide_slot_reuse(p, b) for p, b in itertools.product(probes, bindings)]


def test_total_table_reuse_iff_conjunction_and_order_invariance() -> None:
    """Полная таблица probe x binding: тотальность, REUSE-критерий, T-ISO-I2."""
    forward = _verdicts_in_order(_GRID_PROBES, _GRID_BINDINGS)
    reverse = _verdicts_in_order(_GRID_PROBES[::-1], _GRID_BINDINGS[::-1])
    assert len(forward) == len(_GRID_PROBES) * len(_GRID_BINDINGS) == 192
    assert forward == reverse[::-1], "state_leaks must be 0 (forward/reverse parity)"
    for (probe, binding), verdict in zip(
        itertools.product(_GRID_PROBES, _GRID_BINDINGS), forward, strict=True
    ):
        assert isinstance(verdict, V)
        bound = binding.bound_cid if binding is not None else ""
        reuse_allowed = probe.reused and (
            not probe.strict
            or (probe.run_cid != "" and bound == probe.run_cid and probe.resume_base_idx > 0)
        )
        assert (verdict is V.REUSE) == reuse_allowed
        assert verdict.evicts_slot == (
            verdict in (V.ROTATE_COLD, V.ROTATE_MISMATCH, V.ROTATE_UNANCHORED)
        )
        if probe.strict and probe.reused:
            assert verdict is not V.FRESH, "live slot under strict mode must be classified"


@pytest.mark.parametrize(
    ("verdict", "evicts"),
    [
        (V.FRESH, False),
        (V.REUSE, False),
        (V.ROTATE_COLD, True),
        (V.ROTATE_MISMATCH, True),
        (V.ROTATE_UNANCHORED, True),
    ],
)
def test_evicts_slot_property(verdict: SlotReuseVerdict, evicts: bool) -> None:
    assert verdict.evicts_slot is evicts


def test_slot_binding_after_turn_is_pure_transition() -> None:
    original = _bound("cid-a", turns=2)
    advanced = original.after_turn("cid-b")
    assert advanced == SlotBinding(turns=3, bound_cid="cid-b")
    assert original == SlotBinding(turns=2, bound_cid="cid-a"), "input must stay immutable"
    assert original.after_turn("") == SlotBinding(turns=3, bound_cid="")


def test_slot_binding_is_frozen() -> None:
    binding = _bound("cid-a")
    with pytest.raises(dataclasses.FrozenInstanceError):
        binding.turns = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"turns": -1},
        {"turns": True},
        {"turns": 1.5},
        {"bound_cid": None},
        {"bound_cid": 42},
    ],
)
def test_slot_binding_validation_fail_closed(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="must be"):
        SlotBinding(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"strict": 1},
        {"reused": "yes"},
        {"run_cid": None},
        {"resume_base_idx": "3"},
        {"resume_base_idx": 1.0},
    ],
)
def test_reuse_probe_validation_fail_closed(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="must be"):
        ReuseProbe(**kwargs)  # type: ignore[arg-type]


def test_defaults_are_strict_and_cold() -> None:
    probe = ReuseProbe()
    assert (probe.strict, probe.reused, probe.run_cid, probe.resume_base_idx) == (
        True,
        False,
        "",
        0,
    )
    assert decide_slot_reuse(probe, None) is V.FRESH
    assert SlotBinding() == SlotBinding(turns=0, bound_cid="")


_BANNED_IMPORTS: Final = frozenset(
    {
        "os",
        "subprocess",
        "threading",
        "socket",
        "httpx",
        "openai",
        "requests",
        "aiohttp",
        "urllib3",
        "fastapi",
        "litestar",
        "starlette",
        "sqlalchemy",
        "redis",
        "time",
    }
)
_MUTABLE_CTOR: Final = frozenset({"dict", "list", "set", "defaultdict", "deque"})


def test_module_is_pure_domain_no_io_env_or_mutable_state() -> None:
    """M-MOD-I3/I4: статическая чистота домена (BND-001)."""
    import agy_runtime.worker_rotation_policy as policy

    module_file = policy.__file__
    assert module_file is not None
    tree = ast.parse(Path(module_file).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
            assert not roots & _BANNED_IMPORTS, f"banned import: {roots}"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in _BANNED_IMPORTS
        elif isinstance(node, ast.Attribute):
            assert not (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr == "environ"
            ), "os.environ access in pure domain"
    for stmt in tree.body:
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [getattr(stmt, "target", None)]
        if any(isinstance(t, ast.Name) and t.id in ("__all__", "__slots__") for t in targets):
            continue
        value = stmt.value if isinstance(stmt, (ast.Assign, ast.AnnAssign)) else None
        if value is None:
            continue
        assert not isinstance(
            value, (ast.Dict, ast.List, ast.Set, ast.DictComp, ast.ListComp, ast.SetComp)
        ), "module-level mutable collection"
        if isinstance(value, ast.Call):
            name = (
                value.func.id
                if isinstance(value.func, ast.Name)
                else getattr(value.func, "attr", "")
            )
            assert name not in _MUTABLE_CTOR, "module-level mutable collection"
