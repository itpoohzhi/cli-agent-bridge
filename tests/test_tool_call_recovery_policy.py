"""L1: recovery «ошибка functionCall → валидный tool_call» по INV-S1..S8 (AD-005, VER-007)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.tool_call_recovery_policy import evaluate_recovery  # noqa: E402
from core.transport_failure_contracts import (  # noqa: E402
    DeliveryFacts,
    ParsedToolCall,
    StepRecord,
    TurnStepsSnapshot,
)

_ERR = "Malformed function call: Function call is empty Retries remaining: 3"


class _StrictParser:
    """Тестовый strict-порт: все `<tool_call>` без остатка, иначе `None`; `id` берётся из JSON."""

    def parse_all(self, text: str) -> tuple[ParsedToolCall, ...] | None:
        blocks = re.findall(r"<tool_call>(.*?)</tool_call>", text, re.S)
        if not blocks or "".join(f"<tool_call>{b}</tool_call>" for b in blocks) != text:
            return None
        try:
            items = [json.loads(b) for b in blocks]
            return tuple(
                ParsedToolCall(str(i.get("id", "")), i["name"], json.dumps(i["arguments"])) for i in items
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            return None


def _call(path: str, call_id: str | None = None) -> str:
    body: dict[str, object] = {"name": "read", "arguments": {"file_path": path}}
    if call_id is not None:
        body["id"] = call_id
    return f"<tool_call>{json.dumps(body)}</tool_call>"


def _snap(text: str, *, err_at: int = 5, step_at: int = 6, complete: bool = True, attempted: bool = False) -> TurnStepsSnapshot:
    steps = (StepRecord(err_at, "error", _ERR), StepRecord(step_at, "planner", text, complete))
    return TurnStepsSnapshot(steps, attempted)


def _paths(decision: object) -> list[str]:
    return [json.loads(c.arguments_json)["file_path"] for c in decision.calls]  # type: ignore[attr-defined]


def test_valid_retry_after_error_is_recovered() -> None:
    decision = evaluate_recovery(_snap(_call("/a") + _call("/b")), _StrictParser())
    assert decision.recovered is True
    assert _paths(decision) == ["/a", "/b"]
    assert decision.reason == "recovered"


def test_nine_of_ten_is_rejected_entirely() -> None:
    """INV-S3: один битый из десяти → REJECT целиком, ни одного вызова."""
    text = "".join(_call(f"/p{i}") for i in range(9)) + "<tool_call>{broken</tool_call>"
    decision = evaluate_recovery(_snap(text), _StrictParser())
    assert (decision.recovered, decision.calls, decision.reason) == (False, (), "strict_parse_failed")


@pytest.mark.parametrize("text", ["", "   ", "plain text", _call("/a") + " tail", "head " + _call("/a")])
def test_remainder_or_empty_step_is_rejected(text: str) -> None:
    assert evaluate_recovery(_snap(text), _StrictParser()).recovered is False


@pytest.mark.parametrize(
    "facts",
    [DeliveryFacts(tool_events=1), DeliveryFacts(content_bytes=1), DeliveryFacts(tool_events=2, content_bytes=9)],
)
def test_inv_s1_delivered_output_blocks_recovery(facts: DeliveryFacts) -> None:
    decision = evaluate_recovery(_snap(_call("/a")), _StrictParser(), facts)
    assert (decision.recovered, decision.reason) == (False, "client_output_already_delivered")


def test_inv_s1_keepalive_and_reasoning_do_not_block() -> None:
    facts = DeliveryFacts(keepalive_count=4, reasoning_bytes=2390)
    assert evaluate_recovery(_snap(_call("/a")), _StrictParser(), facts).recovered is True


def test_inv_s2_step_must_be_strictly_after_error() -> None:
    same = evaluate_recovery(_snap(_call("/a"), err_at=6, step_at=6), _StrictParser())
    before = evaluate_recovery(_snap(_call("/a"), err_at=7, step_at=6), _StrictParser())
    assert (same.reason, before.reason) == ("no_step_after_error", "no_step_after_error")


def test_inv_s2_incomplete_candidate_is_rejected_not_replaced_by_older_step() -> None:
    steps = (
        StepRecord(5, "error", _ERR),
        StepRecord(6, "planner", _call("/old")),
        StepRecord(7, "planner", _call("/new"), complete=False),
    )
    decision = evaluate_recovery(TurnStepsSnapshot(steps), _StrictParser())
    assert (decision.recovered, decision.reason) == (False, "candidate_incomplete")


def test_no_error_step_means_nothing_to_recover() -> None:
    snap = TurnStepsSnapshot((StepRecord(4, "planner", _call("/a")),))
    assert evaluate_recovery(snap, _StrictParser()).reason == "no_error_step"


def test_latest_error_defines_the_boundary() -> None:
    steps = (
        StepRecord(1, "error", _ERR),
        StepRecord(2, "planner", _call("/before")),
        StepRecord(3, "error", _ERR),
        StepRecord(4, "planner", _call("/after")),
    )
    assert _paths(evaluate_recovery(TurnStepsSnapshot(steps), _StrictParser())) == ["/after"]


def test_inv_s6_once_per_turn() -> None:
    decision = evaluate_recovery(_snap(_call("/a"), attempted=True), _StrictParser())
    assert (decision.recovered, decision.reason) == (False, "once_per_turn")


def test_inv_s5_half_mirror_without_call_id_collapses_pairs() -> None:
    """5 вызовов, каждый дважды: [c1..c5, c1..c5] → 5, не 10."""
    block = "".join(_call(f"/f{i}") for i in range(5))
    decision = evaluate_recovery(_snap(block + block), _StrictParser())
    assert _paths(decision) == [f"/f{i}" for i in range(5)]


def test_inv_s5_distinct_calls_without_id_are_all_kept() -> None:
    decision = evaluate_recovery(_snap(_call("/a") + _call("/b") + _call("/c")), _StrictParser())
    assert _paths(decision) == ["/a", "/b", "/c"]


@pytest.mark.parametrize(
    "paths",
    [["/a", "/a", "/b"], ["/a", "/b", "/a"], ["/a", "/b", "/b", "/a"], ["/a", "/a", "/a"]],
)
def test_inv_s5_ambiguous_multiplicity_without_call_id_is_rejected(paths: list[str]) -> None:
    decision = evaluate_recovery(_snap("".join(_call(p) for p in paths)), _StrictParser())
    assert (decision.recovered, decision.reason) == (False, "ambiguous_multiplicity")


def test_inv_s5_same_nonempty_call_id_collapses_identical_duplicates() -> None:
    text = _call("/a", "id1") + _call("/a", "id1") + _call("/b", "id2")
    assert _paths(evaluate_recovery(_snap(text), _StrictParser())) == ["/a", "/b"]


def test_inv_s5_different_call_ids_keep_identical_intentional_calls() -> None:
    """Разные непустые call_id сохраняются все, даже при совпадении имени и аргументов."""
    text = _call("/a", "id1") + _call("/a", "id2")
    decision = evaluate_recovery(_snap(text), _StrictParser())
    assert decision.recovered is True
    assert [c.call_id for c in decision.calls] == ["id1", "id2"]


def test_inv_s5_half_mirror_is_not_applied_when_call_ids_differ() -> None:
    text = _call("/a", "id1") + _call("/b", "id2") + _call("/a", "id3") + _call("/b", "id4")
    assert len(evaluate_recovery(_snap(text), _StrictParser()).calls) == 4


def test_inv_s5_same_call_id_with_different_content_is_rejected() -> None:
    decision = evaluate_recovery(_snap(_call("/a", "id1") + _call("/b", "id1")), _StrictParser())
    assert decision.recovered is False


def test_inv_s5_mixed_empty_and_nonempty_call_ids_are_rejected() -> None:
    decision = evaluate_recovery(_snap(_call("/a", "id1") + _call("/b")), _StrictParser())
    assert (decision.recovered, decision.reason) == (False, "ambiguous_multiplicity")


def test_inv_s4_decision_never_carries_raw_markup() -> None:
    decision = evaluate_recovery(_snap(_call("/a")), _StrictParser())
    dump = repr(decision)
    assert "<tool_call>" not in dump
    assert "Retries remaining" not in dump
    rejected = evaluate_recovery(_snap("<tool_call>{x</tool_call>"), _StrictParser())
    assert "<tool_call>" not in repr(rejected)


def test_parser_returning_empty_tuple_is_rejected() -> None:
    class _Empty:
        def parse_all(self, text: str) -> tuple[ParsedToolCall, ...] | None:
            return ()

    assert evaluate_recovery(_snap(_call("/a")), _Empty()).reason == "strict_parse_failed"


def test_evaluation_is_pure_snapshot_is_not_mutated() -> None:
    snap = _snap(_call("/a"))
    before = snap
    _ = evaluate_recovery(snap, _StrictParser())
    assert snap == before
