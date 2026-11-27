"""W1-C: чистый домен loss-receipt/v1 (VER-006, AD-005/AD-006)."""

from __future__ import annotations

import ast
import dataclasses
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

from agy_runtime.loss_receipt import (  # noqa: E402
    LOSS_RECEIPT_SCHEMA_VERSION,
    LossReceipt,
    classify_blocks,
    merge_conservative,
    to_wire,
)

REQUIRED_WIRE_KEYS: Final = frozenset(
    {
        "schema_version",
        "truncated",
        "original_messages",
        "effective_messages",
        "original_prompt_bytes",
        "effective_prompt_bytes",
        "dropped_messages",
        "digested_messages",
        "truncated_active_tools",
        "fallback_reason",
        "configured_prompt_cap_bytes",
    }
)
OPTIONAL_WIRE_KEYS: Final = frozenset(
    {"partial_messages", "compaction_mode", "prompt_mode", "history_budget_bytes"}
)


def _receipt(**overrides: object) -> LossReceipt:
    values: dict[str, object] = {
        "truncated": False,
        "original_messages": 5,
        "effective_messages": 5,
        "original_prompt_bytes": 100,
        "effective_prompt_bytes": 100,
        "dropped_messages": 0,
        "digested_messages": 0,
        "truncated_active_tools": 0,
        "fallback_reason": "",
        "configured_prompt_cap_bytes": 100,
    }
    values.update(overrides)
    return LossReceipt(**values)  # type: ignore[arg-type]


def _block(index: int, body: str, role: str = "assistant") -> tuple[int, str, str]:
    return index, role, f"### {index + 1}. {role}\n{body}"


def _assert_conservation(receipt: LossReceipt) -> None:
    kept = receipt.effective_messages - receipt.partial_messages
    total = kept + receipt.partial_messages + receipt.digested_messages
    total += receipt.dropped_messages
    assert total == receipt.original_messages
    assert receipt.kept_messages == kept


def test_lossless_wire_has_exact_v1_required_allow_list() -> None:
    wire = _receipt().to_wire()
    assert set(wire) == REQUIRED_WIRE_KEYS
    assert wire["schema_version"] == LOSS_RECEIPT_SCHEMA_VERSION == "loss-receipt/v1"
    assert wire["truncated"] is False
    assert all(
        type(wire[key]) is int
        for key in REQUIRED_WIRE_KEYS
        - {"schema_version", "truncated", "fallback_reason"}
    )


def test_full_wire_admits_only_optional_contract_fields() -> None:
    receipt = _receipt(
        truncated=True,
        effective_messages=3,
        effective_prompt_bytes=60,
        dropped_messages=1,
        digested_messages=1,
        partial_messages=1,
        compaction_mode="compact",
        prompt_mode="overflow",
        history_budget_bytes=80,
        fallback_reason="input_guard",
    )
    wire = to_wire(receipt)
    assert set(wire) == REQUIRED_WIRE_KEYS | OPTIONAL_WIRE_KEYS
    assert wire["effective_messages"] == 3
    assert wire["partial_messages"] == 1
    assert None not in wire.values()
    _assert_conservation(receipt)


def test_receipt_is_frozen_and_v1_only() -> None:
    receipt = _receipt()
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.dropped_messages = 2  # type: ignore[misc]
    with pytest.raises(ValueError, match="schema_version"):
        _receipt(schema_version="loss-receipt/v2")


def test_classify_blocks_assigns_each_non_empty_block_exactly_once() -> None:
    blocks = [
        _block(10, "anchor", "system"),
        _block(20, "digest me"),
        _block(30, "also digest"),
        _block(40, "drop me"),
        _block(50, "tail", "user"),
        (60, "user", ""),
    ]
    anchor, _, _, _, tail, _ = blocks
    prompt = f"{anchor[2]}\n\n[сжатая история]\n\n{tail[2]}"
    counts = classify_blocks(blocks, prompt, digested_positions=(20, 30))
    assert counts.kept_messages == 2
    assert counts.partial_messages == 0
    assert counts.digested_messages == 2
    assert counts.dropped_messages == 1
    assert counts.original_messages == 5
    assert counts.effective_messages == 2


def test_partial_header_is_not_counted_as_dropped() -> None:
    original = _block(0, "HEAD " + "x" * 100 + " TAIL", "tool")[2]
    partial = "### 1. tool\nHEAD " + "x" * 10 + "\n[... middle ...]\n"
    counts = classify_blocks([(0, "tool", original)], partial)
    assert (counts.kept_messages, counts.partial_messages) == (0, 1)
    assert counts.dropped_messages == 0


def test_single_line_middle_prune_uses_head_and_marker() -> None:
    original = "UNIQUE_HEAD_" + "x" * 100 + "_UNIQUE_TAIL"
    partial = "UNIQUE_HEAD_xx[... middle ...]_UNIQUE_TAIL"
    counts = classify_blocks(
        [(0, "assistant", original)], partial, middle_pruned_marker="[... middle ...]"
    )
    assert counts.partial_messages == 1
    assert counts.dropped_messages == 0


def test_duplicate_verbatim_block_cannot_mask_a_drop() -> None:
    block = _block(0, "same")
    counts = classify_blocks([block, block], block[2])
    assert counts.kept_messages == 1
    assert counts.partial_messages == 0
    assert counts.dropped_messages == 1
    assert counts.original_messages == 2


def test_845_message_incident_has_one_unambiguous_dropped_count() -> None:
    """840 dropped + 3 verbatim + 2 partial active tools = 845, not 842."""
    blocks = [_block(0, "protocol", "system"), _block(1, "goal", "user")]
    blocks += [_block(i, f"historical-{i:03d}-" + "x" * 100) for i in range(2, 842)]
    blocks.append(_block(842, "run", "assistant"))
    blocks += [
        _block(i, "TOOL_BEGIN " + "y" * 200 + " TOOL_END", "tool") for i in (843, 844)
    ]
    partial_tools = [
        f"### {i + 1}. tool\nTOOL_BEGIN yy[... middle ...] TOOL_END" for i in (843, 844)
    ]
    prompt = "\n\n".join([blocks[0][2], blocks[1][2], blocks[842][2], *partial_tools])
    counts = classify_blocks(blocks, prompt)
    assert counts.original_messages == 845
    assert counts.kept_messages == 3
    assert counts.partial_messages == 2
    assert counts.digested_messages == 0
    assert counts.dropped_messages == 840
    assert counts.effective_messages == 5


def test_merge_conservative_prefers_truncated_then_greatest_message_loss() -> None:
    lossless = _receipt()
    small = _receipt(truncated=True, effective_messages=4, dropped_messages=1)
    large = _receipt(
        truncated=True, effective_messages=2, dropped_messages=1, digested_messages=2
    )
    assert merge_conservative([lossless, small]) is small
    assert merge_conservative([small, large, lossless]) is large
    assert merge_conservative([]) is None
    assert merge_conservative([small]) is small
    _assert_conservation(large)


@pytest.mark.parametrize(
    "overrides",
    [
        {"original_messages": -1},
        {"original_messages": True},
        {"effective_messages": 4},
        {"partial_messages": 6},
        {"dropped_messages": 1},
        {"fallback_reason": "input_guard"},
        {"history_budget_bytes": -1},
        {"truncated": 1},
    ],
)
def test_invalid_receipt_fails_closed(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _receipt(**overrides)


def test_module_is_pure_domain_without_io_or_module_mutable_collections() -> None:
    import agy_runtime.loss_receipt as domain

    module_file = domain.__file__
    assert module_file is not None
    tree = ast.parse(Path(module_file).read_text(encoding="utf-8"))
    banned = {
        "os",
        "subprocess",
        "threading",
        "socket",
        "httpx",
        "openai",
        "requests",
        "time",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {a.name.split(".")[0] for a in node.names} & banned
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned
    for stmt in tree.body:
        value = stmt.value if isinstance(stmt, (ast.Assign, ast.AnnAssign)) else None
        assert not isinstance(value, (ast.Dict, ast.List, ast.Set))
