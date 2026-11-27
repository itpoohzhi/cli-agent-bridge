"""W2-G: адаптер input_guard + квитанции потерь (VER-017, AD-006/AD-010/AD-011).

Детерминированно: 0 сокетов, 0 sleep; env через monkeypatch, конфиг в tmp_path.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
AGY_BRIDGE: Final = ROOT / "bridges" / "agy-bridge"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AGY_BRIDGE) not in sys.path:
    sys.path.append(str(AGY_BRIDGE))

import agy_runtime.history_compaction_adapter as adapter  # noqa: E402
from agy_runtime.history_compaction_adapter import (  # noqa: E402
    CompactionAdapterRequest,
    RawBlock,
    render_or_compact_blocks,
)
from agy_runtime.input_guard_policy import ClientCompactionRequired  # noqa: E402
from agy_runtime.loss_receipt import LossReceipt  # noqa: E402
from agy_runtime.loss_receipt_context import begin_request_scope  # noqa: E402

LIMIT: Final = 64 * 1024
MODE_ENV: Final = "AGY_BRIDGE_INPUT_GUARD_MODE"


class LegacySpy:
    """Legacy-делегат: считает вызовы, возвращает только якорь истории."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, blocks: Sequence[RawBlock], tail: str, limit: int) -> str:
        self.calls += 1
        return "LEGACY-PRUNED"


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (MODE_ENV, "AGY_BRIDGE_LOSS_RECEIPT_ENABLED", "AGY_BRIDGE_ATOMIC_ACTIVE_TOOLS_ENABLED"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def receipts(monkeypatch: pytest.MonkeyPatch) -> list[LossReceipt]:
    recorded: list[LossReceipt] = []
    monkeypatch.setattr(adapter, "record_build", recorded.append)
    return recorded


def _history(turns: int, body: int = 2000) -> list[tuple[int, str, str]]:
    blocks = [(0, "system", "### 0. system\nrules"), (1, "user", "### 1. user\nfirst question")]
    for turn in range(turns):
        base, cid = 2 + turn * 3, f"c{turn:02d}"
        blocks.append((base, "user", f"### {base}. user\nstep {turn}"))
        blocks.append((base + 1, "assistant", f"### {base + 1}. assistant\n[tool call {cid}] f()"))
        blocks.append((base + 2, "tool", f"### {base + 2}. tool\n[tool result {cid}] " + "x" * body))
    blocks.append((2 + turns * 3, "user", f"### {2 + turns * 3}. user\nfinal question"))
    return blocks


def _active_tool_history(body: int) -> list[tuple[int, str, str]]:
    """История, чья активная группа (после последнего реального user) — tool-цикл."""
    return [
        (0, "system", "### 0. system\nrules"),
        (1, "user", "### 1. user\nrun it"),
        (2, "assistant", "### 2. assistant\n[tool call a1] f()"),
        (3, "tool", "### 3. tool\n[tool result a1]\n" + "y" * body),
    ]


def _request(
    tmp_path: Path,
    blocks: list[tuple[int, str, str]],
    spy: LegacySpy,
    **opts: int,
) -> CompactionAdapterRequest:
    """opts: enabled (0/1), guard, limit; дефолты — компакция вкл., гард 4 МиБ."""
    return CompactionAdapterRequest(
        blocks=blocks,
        tail_block="",
        limit_bytes=opts.get("limit", LIMIT),
        enabled=bool(opts.get("enabled", 1)),
        legacy_prune=spy,
        config_path=tmp_path / "dynamic_config.json",
        input_guard_bytes=opts.get("guard", 1 << 22),
    )


def test_legacy_flag_off_is_byte_identical_and_lossless_receipt(
    tmp_path: Path, receipts: list[LossReceipt]
) -> None:
    spy, blocks = LegacySpy(), _history(1)
    prompt = render_or_compact_blocks(_request(tmp_path, blocks, spy, enabled=0))
    assert prompt == "LEGACY-PRUNED"
    assert spy.calls == 1
    assert len(receipts) == 1
    assert receipts[0].compaction_mode == "legacy"
    assert receipts[0].original_messages == len(blocks)


def test_legacy_prune_loss_is_reported_honestly(
    tmp_path: Path, receipts: list[LossReceipt]
) -> None:
    blocks = _history(3)
    render_or_compact_blocks(_request(tmp_path, blocks, LegacySpy(), enabled=0))
    (receipt,) = receipts
    assert receipt.truncated is True
    assert receipt.dropped_messages == len(blocks)
    assert receipt.effective_messages == 0
    assert receipt.configured_prompt_cap_bytes == LIMIT


def test_compact_lossless_records_one_receipt_without_legacy(
    tmp_path: Path, receipts: list[LossReceipt]
) -> None:
    spy, blocks = LegacySpy(), _history(2, body=100)
    prompt = render_or_compact_blocks(_request(tmp_path, blocks, spy))
    assert spy.calls == 0
    assert prompt == "\n\n".join(b[2] for b in blocks)
    (receipt,) = receipts
    assert (receipt.truncated, receipt.dropped_messages) == (False, 0)
    assert receipt.compaction_mode == "compact"
    assert receipt.effective_messages == receipt.original_messages == len(blocks)


def test_compact_or_reject_oversize_never_calls_legacy_prune(
    tmp_path: Path, receipts: list[LossReceipt]
) -> None:
    spy, blocks = LegacySpy(), _history(40)
    prompt = render_or_compact_blocks(_request(tmp_path, blocks, spy, guard=16 * 1024))
    assert spy.calls == 0
    assert "first question" in prompt
    assert "final question" in prompt
    (receipt,) = receipts
    assert receipt.truncated is True
    assert receipt.dropped_messages > 0
    assert receipt.compaction_mode == "compact"
    assert receipt.fallback_reason == ""
    total = receipt.effective_messages + receipt.digested_messages + receipt.dropped_messages
    assert total == receipt.original_messages == len(blocks)


def test_unfit_active_group_raises_client_compaction_required(
    tmp_path: Path, receipts: list[LossReceipt]
) -> None:
    spy, blocks = LegacySpy(), _history(2, body=4000)
    with pytest.raises(ClientCompactionRequired) as caught:
        render_or_compact_blocks(_request(tmp_path, blocks, spy, guard=64))
    error = caught.value.body["error"]
    assert isinstance(error, dict)
    assert error["x_reason"] == "client_compaction_required"
    assert error["code"] == "context_length_exceeded"
    assert error["x_bridge_loss"]["original_messages"] == len(blocks)
    assert error["x_bridge_loss"]["fallback_reason"] == "input_guard"
    assert spy.calls == 0
    assert receipts == []


def test_atomic_unfit_after_guard_fit_raises(tmp_path: Path, receipts: list[LossReceipt]) -> None:
    spy, blocks = LegacySpy(), _history(1, body=100)
    with pytest.raises(ClientCompactionRequired) as caught:
        render_or_compact_blocks(_request(tmp_path, blocks, spy, limit=50))
    assert caught.value.body["error"]["x_bridge_loss"]["original_messages"] == len(blocks)
    assert spy.calls == 0
    assert receipts == []


def test_guard_legacy_mode_falls_back_with_honest_receipt(
    tmp_path: Path, receipts: list[LossReceipt], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(MODE_ENV, "legacy")
    spy, blocks = LegacySpy(), _history(40)
    prompt = render_or_compact_blocks(_request(tmp_path, blocks, spy, guard=16 * 1024))
    assert (prompt, spy.calls) == ("LEGACY-PRUNED", 1)
    (receipt,) = receipts
    assert receipt.truncated is True
    assert receipt.fallback_reason == "input_guard"
    assert receipt.compaction_mode == "fallback"


def test_guard_legacy_mode_atomic_unfit_degrades_to_legacy_not_reject(
    tmp_path: Path, receipts: list[LossReceipt], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(MODE_ENV, "legacy")
    spy = LegacySpy()
    prompt = render_or_compact_blocks(_request(tmp_path, _history(1, body=100), spy, limit=50))
    assert (prompt, spy.calls) == ("LEGACY-PRUNED", 1)
    assert receipts[0].fallback_reason == "over_limit"


def test_compact_error_falls_back_and_records_reason(
    tmp_path: Path, receipts: list[LossReceipt], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("domain failure")

    monkeypatch.setattr(adapter, "compact_prompt_blocks", boom)
    spy = LegacySpy()
    prompt = render_or_compact_blocks(_request(tmp_path, _history(3), spy))
    assert (prompt, spy.calls) == ("LEGACY-PRUNED", 1)
    (receipt,) = receipts
    assert (receipt.compaction_mode, receipt.fallback_reason) == ("fallback", "compact_error")


def test_receipt_disabled_flag_records_nothing(
    tmp_path: Path, receipts: list[LossReceipt], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGY_BRIDGE_LOSS_RECEIPT_ENABLED", "false")
    render_or_compact_blocks(_request(tmp_path, _history(1), LegacySpy()))
    assert receipts == []


def test_request_scope_collects_receipt_per_build(tmp_path: Path) -> None:
    with begin_request_scope() as collector:
        render_or_compact_blocks(_request(tmp_path, _history(40), LegacySpy(), guard=16 * 1024))
        merged = collector.merged()
    assert merged is not None
    assert merged.truncated is True
    assert merged.dropped_messages > 0


def test_active_tool_loss_counted_when_active_group_pruned(
    tmp_path: Path, receipts: list[LossReceipt]
) -> None:
    blocks = _active_tool_history(40000)
    render_or_compact_blocks(_request(tmp_path, blocks, LegacySpy(), limit=8 * 1024))
    (receipt,) = receipts
    assert receipt.truncated is True
    assert receipt.truncated_active_tools >= 1
