"""W1-E: чистая политика входного гарда (VER-008, AD-010/AD-011).

Детерминированные unit-тесты домена: 0 сокетов, 0 sleep, 0 env-доступа.
"""

from __future__ import annotations

import ast
import dataclasses
import re
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

from agy_runtime.history_compaction_domain import (  # noqa: E402
    DEFAULT_INPUT_GUARD_BYTES,
    PromptBlock,
    _anchor_group_count,
    _group_blocks,
    json_text_bytes,
)
from agy_runtime.input_guard_policy import (  # noqa: E402
    ClientCompactionRequired,
    GuardDecision,
    GuardVerdict,
    InputGuardMode,
    build_rejection_body,
    select_bounded_window,
)

GUARD: Final = DEFAULT_INPUT_GUARD_BYTES  # 4194304 B


def _block(index: int, role: str, text: str) -> PromptBlock:
    return PromptBlock(index=index, role=role, rendered=text)


def _joined(blocks: tuple[PromptBlock, ...], separator: str = "\n\n") -> int:
    return json_text_bytes(separator.join(b.rendered for b in blocks))


def _over_guard_blocks() -> tuple[PromptBlock, ...]:
    """Якорь (system+user), 16 больших assistant-середин, активный tool-хвост."""
    blocks = [_block(0, "system", "system anchor"), _block(1, "user", "first user")]
    blocks += [_block(i, "assistant", "x" * 300_000) for i in range(2, 18)]
    blocks += [
        _block(18, "user", "active turn"),
        _block(19, "assistant", "[tool call t1] run"),
        _block(20, "tool", "[tool result t1] ok"),
        _block(21, "tool", "[tool result t1] done"),
    ]
    return tuple(blocks)


def _small_blocks() -> tuple[PromptBlock, ...]:
    """Точная арифметика (ASCII, JSON-escaped sep '\\n\\n'=4B): якорь 24B, актив 10B."""
    return (
        _block(0, "system", "s" * 10),
        _block(1, "user", "u" * 10),
        _block(2, "assistant", "a" * 5),
        _block(3, "assistant", "b" * 30),
        _block(4, "assistant", "c" * 10),
        _block(5, "user", "v" * 10),
    )


def _error(body: dict[str, object]) -> dict[str, object]:
    error = body["error"]
    assert isinstance(error, dict)
    return error


def test_mode_enum_values_and_unknown_fail_closed() -> None:
    assert InputGuardMode("legacy") is InputGuardMode.LEGACY
    assert InputGuardMode("compact_or_reject") is InputGuardMode.COMPACT_OR_REJECT
    with pytest.raises(ValueError):
        InputGuardMode("bogus")


@pytest.mark.parametrize("m", [InputGuardMode.LEGACY, "legacy"])
def test_legacy_mode_returns_legacy_verdict_unchanged(m: InputGuardMode | str) -> None:
    blocks = _over_guard_blocks()
    decision = select_bounded_window(blocks, mode=m)
    assert decision.verdict is GuardVerdict.LEGACY
    assert decision.window == blocks
    assert decision.dropped_messages == 0
    assert decision.input_bytes > GUARD


def test_fit_when_input_within_guard() -> None:
    blocks = _small_blocks()
    decision = select_bounded_window(blocks, guard_bytes=_joined(blocks))
    assert decision.verdict is GuardVerdict.FIT
    assert decision.window == blocks
    assert decision.dropped_messages == 0
    assert decision.input_bytes == _joined(blocks)


def test_empty_input_fit_even_with_zero_guard() -> None:
    decision = select_bounded_window((), guard_bytes=0)
    assert decision.verdict is GuardVerdict.FIT
    assert decision.window == ()
    assert decision.dropped_messages == 0
    assert decision.input_bytes == 0


def test_bounded_window_keeps_anchor_and_active_tail() -> None:
    blocks = _over_guard_blocks()
    decision = select_bounded_window(blocks)
    assert decision.verdict is GuardVerdict.WINDOW
    assert decision.input_bytes > GUARD
    assert _joined(decision.window) <= GUARD
    indices = [b.index for b in decision.window]
    assert indices == sorted(indices)
    assert 0 in indices and 1 in indices  # якорь целиком
    assert all(i in indices for i in (18, 19, 20, 21))  # активный ход + tool-группа
    assert 17 in indices and 2 not in indices  # новейшая середина есть, старшая dropped
    assert decision.dropped_messages == len(blocks) - len(decision.window) > 0
    assert all(b in blocks for b in decision.window)  # verbatim, без пересборки


def test_window_is_group_atomic() -> None:
    blocks = _over_guard_blocks()
    decision = select_bounded_window(blocks)
    window_indices = {b.index for b in decision.window}
    for group in _group_blocks(blocks):
        hits = [b.index in window_indices for b in group]
        assert all(hits) or not any(hits)


def test_exact_window_newest_first_with_break() -> None:
    # guard=70: якорь+актив=38B; newest 10B -> 52B; 30B -> 86B > 70 -> стоп,
    # старшая 5B-группа тоже dropped (break, а не skip — как в домене).
    decision = select_bounded_window(_small_blocks(), guard_bytes=70)
    assert decision.verdict is GuardVerdict.WINDOW
    assert tuple(b.index for b in decision.window) == (0, 1, 4, 5)
    assert decision.dropped_messages == 2
    assert _joined(decision.window) == 52


def test_mandatory_exact_guard_boundary_is_window_not_unfit() -> None:
    decision = select_bounded_window(_small_blocks(), guard_bytes=38)
    assert decision.verdict is GuardVerdict.WINDOW
    assert tuple(b.index for b in decision.window) == (0, 1, 5)
    assert decision.dropped_messages == 3
    assert _joined(decision.window) == 38


def test_unfit_when_mandatory_exceeds_guard_by_one_byte() -> None:
    decision = select_bounded_window(_small_blocks(), guard_bytes=37)
    assert decision.verdict is GuardVerdict.UNFIT
    assert decision.window == ()
    assert decision.dropped_messages == 6


def test_unfit_active_tool_group_over_default_guard() -> None:
    blocks = (
        _block(0, "system", "sys"),
        _block(1, "user", "turn"),
        _block(2, "assistant", "[tool call t1] run"),
        _block(3, "tool", "x" * (GUARD + 1)),
    )
    decision = select_bounded_window(blocks)
    assert decision.verdict is GuardVerdict.UNFIT
    assert decision.window == ()
    assert decision.dropped_messages == len(blocks)


def test_unfit_anchor_alone_over_guard() -> None:
    blocks = (_block(0, "system", "x" * (GUARD + 1)), _block(1, "user", "turn"))
    decision = select_bounded_window(blocks)
    assert decision.verdict is GuardVerdict.UNFIT
    assert decision.dropped_messages == 2


def test_selection_is_deterministic() -> None:
    blocks = _over_guard_blocks()
    assert select_bounded_window(blocks) == select_bounded_window(blocks)


def test_guard_decision_is_frozen() -> None:
    decision = select_bounded_window((_block(0, "user", "hi"),))
    assert isinstance(decision, GuardDecision)
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.dropped_messages = 5  # type: ignore[misc]


@pytest.mark.parametrize("mode", ["bogus", "", "LEGACY"])
def test_unknown_mode_fail_closed(mode: str) -> None:
    with pytest.raises(ValueError):
        select_bounded_window((), mode=mode)


@pytest.mark.parametrize("guard", [-1, 1.5, True, "4"])
def test_invalid_guard_fail_closed(guard: object) -> None:
    with pytest.raises(ValueError):
        select_bounded_window((), guard_bytes=guard)  # type: ignore[arg-type]


def test_invalid_separator_fail_closed() -> None:
    with pytest.raises(ValueError):
        select_bounded_window((), separator=2)  # type: ignore[arg-type]


def test_grouping_parity_with_compaction_domain() -> None:
    from agy_runtime import input_guard_policy as guard

    blocks = _over_guard_blocks()
    groups = _group_blocks(blocks)
    assert guard._group_blocks(blocks) == groups
    assert guard._anchor_group_count(groups) == _anchor_group_count(groups)


def test_rejection_body_ad010_contract() -> None:
    error = _error(build_rejection_body(5_000_000, GUARD, 1_000_000, 22))
    assert error["type"] == "invalid_request_error"
    assert error["code"] == "context_length_exceeded"
    assert error["param"] == "messages"
    assert error["x_reason"] == "client_compaction_required"
    assert error["message"] == (
        "client_compaction_required (context length exceeded): history of 5000000 "
        "bytes exceeds agy-bridge input_guard 4194304 bytes and the active tool group "
        "cannot be kept intact within the configured prompt cap 1000000 bytes; "
        "compact the conversation and retry"
    )
    assert "context length exceeded" in error["message"]  # type: ignore[operator]
    loss = error["x_bridge_loss"]
    assert isinstance(loss, dict)
    assert loss["schema_version"] == "loss-receipt/v1"
    assert loss["truncated"] is True
    assert loss["fallback_reason"] == "input_guard"
    assert loss["original_messages"] == 22
    assert loss["effective_messages"] == 0
    assert loss["dropped_messages"] == 22
    assert loss["original_prompt_bytes"] == 5_000_000
    assert loss["effective_prompt_bytes"] == 0
    assert loss["configured_prompt_cap_bytes"] == 1_000_000


def test_rejection_message_integers_only() -> None:
    error = _error(build_rejection_body(5_000_001, GUARD, 999_999, 3))
    tokens = re.findall(r"\d+(?:[.,]\d+)?", str(error["message"]))
    assert tokens == ["5000001", "4194304", "999999"]
    assert all(t.isdigit() for t in tokens)


@pytest.mark.parametrize("bad", [1.5, True, "10", -1, None])
def test_rejection_body_rejects_non_integer_inputs(bad: object) -> None:
    for pos in range(4):
        args: list[object] = [5_000_000, GUARD, 1_000_000, 22]
        args[pos] = bad
        with pytest.raises(ValueError):
            build_rejection_body(*args)  # type: ignore[arg-type]


def test_client_compaction_required_carries_ad010_body() -> None:
    exc = ClientCompactionRequired(5_000_000, GUARD, 1_000_000, 22)
    assert isinstance(exc, Exception)
    assert str(exc) == "client_compaction_required"
    assert exc.body == build_rejection_body(5_000_000, GUARD, 1_000_000, 22)


def test_module_is_pure_domain() -> None:
    source = (AGY_BRIDGE / "agy_runtime" / "input_guard_policy.py").read_text("utf-8")
    forbidden = set(
        "os subprocess threading socket httpx openai requests aiohttp urllib3 "
        "fastapi litestar starlette sqlalchemy redis time".split()
    )
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            assert all(a.name.split(".")[0] not in forbidden for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden
    assert "os.environ" not in source


def test_agentic_loop_845_messages_window_not_unfit() -> None:
    """Hermes: turn 1 без новых user — 420 старых tool-групп не mandatory."""
    blocks = [_block(0, "system", "sys"), _block(1, "user", "turn 1")]
    for i in range(421):
        blocks += [_block(2 + 2 * i, "assistant", f"[tool call t{i}] run")]
        blocks += [_block(3 + 2 * i, "tool", "x" * 10_000 if i < 420 else "ok")]
    blocks += [_block(844, "tool", "[tool result t420] done")]
    decision = select_bounded_window(tuple(blocks))
    assert len(blocks) == 845 and decision.verdict is GuardVerdict.WINDOW
    assert decision.input_bytes > GUARD and _joined(decision.window) <= GUARD
    indices = {b.index for b in decision.window}
    assert {0, 1, 842, 843, 844} <= indices and 2 not in indices
    assert decision.dropped_messages == 845 - len(decision.window) > 0
