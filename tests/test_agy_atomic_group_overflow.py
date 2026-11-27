"""W1-D: атомарный overflow групп (VER-007, AD-012, CD-009).

Детерминированные unit-тесты домена: 0 сокетов, 0 sleep, 0 env-доступа.
Группа assistant+tool_calls+tool_results хранится/вытесняется только
целиком; активная группа не вытесняется (floor 256 B, иначе UNFIT).
"""

# ruff: noqa: E402
from __future__ import annotations

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

from agy_runtime.atomic_group_overflow import (
    OverflowItem,
    build_overflow_items,
    shrink_atomic,
)
from agy_runtime.history_compaction_domain import (
    PromptBlock,
    json_text_bytes,
    middle_prune_text,
)
from agy_runtime import atomic_group_overflow as atomic_module
from agy_runtime import history_overflow_policy as policy_module
from agy_runtime.history_overflow_policy import (
    MIN_PROTECTED_FLOOR_BYTES,
    OverflowSpec,
)

MARKER: Final = "[pruned]"
SEP: Final = "\n\n"


def _spec(limit: int) -> OverflowSpec:
    return OverflowSpec(limit, SEP, MARKER, json_text_bytes, middle_prune_text)


def _block(index: int, role: str, token: str, pad: int) -> PromptBlock:
    body = f"{token} " + "x" * pad
    return PromptBlock(index=index, role=role, rendered=f"### {index}. {role}\n{body}")


def _tool_group(
    base: int, token: str, call_pad: int, result_pad: int
) -> tuple[PromptBlock, ...]:
    return (
        _block(base, "assistant", f"{token}-CALL [tool call t{base}]", call_pad),
        _block(base + 1, "tool", f"{token}-RESULT [tool result t{base}]", result_pad),
    )


def _items(
    *groups: tuple[PromptBlock, ...], carrier: tuple[PromptBlock, ...] | None = None
) -> tuple[OverflowItem, ...]:
    return build_overflow_items((), "", groups, carrier)


def test_build_order_ids_digest_and_active() -> None:
    anchor = (_block(0, "system", "SYS", 10),)
    user = (_block(1, "user", "USER", 10),)
    tail = _tool_group(2, "T", 10, 10)
    carrier = (_block(4, "user", "ACTIVE", 10),)
    items = build_overflow_items((anchor, user), "DIGEST", (tail, carrier), carrier)
    assert [it.group for it in items] == ["a0", "a1", "digest", "t0", "t0", "t1"]
    assert [it.role for it in items] == [
        "system",
        "user",
        "digest",
        "assistant",
        "tool",
        "user",
    ]
    assert [it.active for it in items] == [False, False, False, False, False, True]
    assert items[2].text == "DIGEST"


def test_build_synthetic_role_and_empty_digest() -> None:
    reminder = (_block(0, "user", "<system-reminder>goal</system-reminder>", 0),)
    real = (_block(1, "user", "REAL", 0),)
    items = build_overflow_items((reminder,), "", (real,), None)
    assert [it.role for it in items] == ["synthetic", "user"]
    assert all(not it.active for it in items)
    assert all(it.group != "digest" for it in items)


def test_fits_verbatim_and_empty_items() -> None:
    group = _tool_group(0, "T", 50, 50)
    items = _items(group)
    result = shrink_atomic(items, _spec(10_000))
    assert not result.unfit
    assert result.prompt == SEP.join(b.rendered for b in group)
    empty = shrink_atomic((), _spec(0))
    assert not empty.unfit and empty.prompt == ""


def test_tool_group_kept_as_unit_under_proportional_prune() -> None:
    group = _tool_group(0, "T", 2000, 4000)
    result = shrink_atomic(_items(group), _spec(2500))
    assert not result.unfit
    assert json_text_bytes(result.prompt) <= 2500
    assert "T-CALL" in result.prompt and "T-RESULT" in result.prompt
    assert MARKER in result.prompt


def test_tool_group_evicted_as_unit_no_orphan_results() -> None:
    anchor = (_block(0, "user", "ANCHOR", 20),)
    old = (
        _block(1, "assistant", "OLD-CALL [tool call t1]", 1000),
        _block(2, "tool", "OLD-R1 [tool result t1]", 1000),
        _block(3, "tool", "OLD-R2 [tool result t1]", 1000),
    )
    new = _tool_group(4, "NEW", 30, 30)
    items = build_overflow_items((anchor,), "", (old, new), None)
    # Бюджет OLD = 3 B < 2 сепараторов: пропорциональный prune невозможен,
    # группа вытесняется целиком, без осиротевших tool results.
    limit = (
        json_text_bytes(SEP.join([anchor[0].rendered, *(b.rendered for b in new)])) + 5
    )
    result = shrink_atomic(items, _spec(limit))
    assert not result.unfit
    assert json_text_bytes(result.prompt) <= limit
    assert all(token not in result.prompt for token in ("OLD-CALL", "OLD-R1", "OLD-R2"))
    assert "NEW-CALL" in result.prompt and "NEW-RESULT" in result.prompt
    assert "ANCHOR" in result.prompt


def test_active_group_never_evicted_only_pruned() -> None:
    active = _tool_group(0, "ACT", 3000, 3000)
    other = _tool_group(2, "OLD", 2000, 2000)
    items = build_overflow_items((), "", (other, active), active)
    result = shrink_atomic(items, _spec(1200))
    assert not result.unfit
    assert json_text_bytes(result.prompt) <= 1200
    assert "OLD-CALL" not in result.prompt and "OLD-RESULT" not in result.prompt
    assert "ACT-CALL" in result.prompt and "ACT-RESULT" in result.prompt


def test_active_group_unfit_below_floor() -> None:
    active = _tool_group(0, "ACT", 1000, 1000)
    limit = 2 * MIN_PROTECTED_FLOOR_BYTES - 1
    result = shrink_atomic(_items(active, carrier=active), _spec(limit))
    assert result.unfit
    assert result.prompt == ""


def test_active_group_fits_at_floor() -> None:
    active = _tool_group(0, "ACT", 1000, 1000)
    limit = 2 * (MIN_PROTECTED_FLOOR_BYTES + 40) + json_text_bytes(SEP)
    result = shrink_atomic(_items(active, carrier=active), _spec(limit))
    assert not result.unfit
    assert json_text_bytes(result.prompt) <= limit
    assert "ACT-CALL" in result.prompt and "ACT-RESULT" in result.prompt


def test_real_user_never_evicted() -> None:
    user = (_block(0, "user", "USER", 2000),)
    group = _tool_group(1, "T", 2000, 2000)
    result = shrink_atomic(_items(user, group), _spec(400))
    assert not result.unfit
    assert "USER" in result.prompt
    assert "T-CALL" not in result.prompt and "T-RESULT" not in result.prompt


def test_synthetic_evicted_before_tool_groups() -> None:
    reminder = "<system-reminder>goal</system-reminder>"
    synthetic = (PromptBlock(0, "user", "### 0. user\n" + reminder * 100),)
    group = _tool_group(1, "T", 2000, 2000)
    items = build_overflow_items((synthetic,), "", (group,), None)
    result = shrink_atomic(items, _spec(900))
    assert not result.unfit
    assert json_text_bytes(result.prompt) <= 900
    assert "system-reminder" not in result.prompt
    assert "T-CALL" in result.prompt and "T-RESULT" in result.prompt


def test_digest_shrunk_then_evicted_on_zero_budget() -> None:
    digest_item = OverflowItem(
        group="digest", role="digest", text="DIGEST " + "d" * 3000
    )
    group = _tool_group(0, "T", 100, 100)
    items = (digest_item, *build_overflow_items((), "", (group,), None))
    tight = shrink_atomic(items, _spec(600))
    assert not tight.unfit
    assert json_text_bytes(tight.prompt) <= 600
    assert "DIGEST" in tight.prompt and MARKER in tight.prompt
    assert "T-CALL" in tight.prompt and "T-RESULT" in tight.prompt
    evicted = shrink_atomic((digest_item,), _spec(0))
    assert not evicted.unfit and evicted.prompt == ""


@pytest.mark.parametrize("limit", [600, 1200, 2000, 3000, 5000])
def test_atomicity_and_budget_sweep(limit: int) -> None:
    anchor = (_block(0, "user", "ANCHOR", 100),)
    g1 = _tool_group(1, "G1", 1000, 1000)
    g2 = _tool_group(3, "G2", 1000, 1000)
    active = _tool_group(5, "ACT", 1000, 1000)
    items = build_overflow_items((anchor,), "", (g1, g2, active), active)
    result = shrink_atomic(items, _spec(limit))
    if result.unfit:
        assert result.prompt == ""
        return
    assert json_text_bytes(result.prompt) <= limit
    for token in ("G1", "G2", "ACT"):
        call, res = f"{token}-CALL" in result.prompt, f"{token}-RESULT" in result.prompt
        assert call == res, f"split-brain group {token} at limit={limit}"
    assert "ACT-CALL" in result.prompt and "ACT-RESULT" in result.prompt


def test_separator_accounting_three_member_group() -> None:
    group = (
        _block(0, "assistant", "A-CALL [tool call t0]", 900),
        _block(1, "tool", "A-R1 [tool result t0]", 900),
        _block(2, "tool", "A-R2 [tool result t0]", 900),
    )
    result = shrink_atomic(_items(group), _spec(1000))
    assert not result.unfit
    assert json_text_bytes(result.prompt) <= 1000
    assert all(token in result.prompt for token in ("A-CALL", "A-R1", "A-R2"))


def test_reuses_spec_prune_fn_and_deterministic() -> None:
    calls: list[int] = []

    def spy(text: str, budget: int, marker: str) -> str:
        calls.append(budget)
        return middle_prune_text(text, budget, marker)

    group = _tool_group(0, "T", 2000, 2000)
    items = _items(group)
    spec = OverflowSpec(1000, SEP, MARKER, json_text_bytes, spy)
    first = shrink_atomic(items, spec)
    assert calls, "shrink_atomic must reuse spec.prune_fn"
    second = shrink_atomic(items, spec)
    assert first == second
    assert [it.text for it in items] == [b.rendered for b in group]


def test_local_constants_mirror_overflow_policy() -> None:
    floor = policy_module.MIN_PROTECTED_FLOOR_BYTES
    assert atomic_module.MIN_PROTECTED_FLOOR_BYTES == floor
    assert atomic_module.SHRINK_ROLE_ORDER == policy_module.SHRINK_ROLE_ORDER
    assert atomic_module.EVICT_ROLE_ORDER == policy_module.EVICT_ROLE_ORDER


def test_no_runtime_import_of_overflow_policy() -> None:
    source = Path(atomic_module.__file__).read_text(encoding="utf-8")
    assert "from .history_overflow_policy" not in source
    assert "import history_overflow_policy" not in source
