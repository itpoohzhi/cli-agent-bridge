"""Регрессии накопленного safety-вето и канонического переключателя."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import test_causal_turn_recovery_flow as flow
from core import stream_interruption_recovery as recovery
from core.turn_outcome_policy import is_fatal_safety_error


@pytest.mark.parametrize("marker", ("policy%5fviolation", "policy+violation", "SAFETY", "BLOCK_REASON: SAFETY", "PROHIBITED_CONTENT", "RECITATION"))
def test_encoded_and_machine_safety_codes(marker: str) -> None:
    assert is_fatal_safety_error(marker)


@pytest.mark.parametrize("error", ("connection reset by peer", "Malformed function call"))
@pytest.mark.parametrize("safety_seq", (0, 2, None))
def test_safety_history_blocks_terminal_recovery(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error: str, safety_seq: int | None) -> None:
    bridge = flow._load_bridge(monkeypatch, tmp_path)
    monkeypatch.setattr(flow, "_ERROR", error)
    tail = flow._make_tail(bridge, (1,), 3)
    tail._emit_record(json.dumps(dict(type="ERROR_MESSAGE", step_index=safety_seq, content="Policy violation")).encode())
    tail._emit_record(json.dumps(dict(type="ERROR_MESSAGE", step_index=4, content=error)).encode())
    tail._emit_record(json.dumps(dict(type="PLANNER_RESPONSE", step_index=5, content=flow._FINAL)).encode())
    assert getattr(tail, "had_safety_error", False)
    chunks, out = flow._serve_replay(bridge, flow._make_run(tail))
    assert (out["state"], out["rc"], out["text"]) == ("agy_error", 1, "")
    assert any("error" in chunk for chunk in chunks)


@pytest.mark.parametrize("legacy", (None, "false"))
def test_canonical_switch_needs_no_legacy_opt_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, legacy: str | None) -> None:
    bridge = flow._load_bridge(monkeypatch, tmp_path)
    monkeypatch.delenv("AGY_CAUSAL_RECOVERY_ENABLED")
    monkeypatch.delenv("AGY_SELF_HEAL_INTERRUPTED_TURN")
    if legacy is not None:
        monkeypatch.setenv("AGY_SELF_HEAL_INTERRUPTED_TURN", legacy)
    flow._assert_final_preserved(*flow._serve_replay(bridge, flow._make_run(flow._make_tail(bridge, (1,), 2))))


def test_resolver_safety_config_vetoes_legacy_transient() -> None:
    from test_causal_turn_recovery import _facts
    from dataclasses import replace

    facts = _facts()
    facts = replace(facts, config=replace(facts.config, is_fatal_safety=True))
    assert not recovery.evaluate_done_causal_recovery(facts, "connection reset").clear_error
    result = recovery.resolve_done_turn_outcome(rc=1, result_error="connection reset", result_status="ERROR", final_text="Финал", emitted_text="", completion_done_without_tools=True, last_completion_seq=2, last_error_seq=1, drain_complete=True, causal_input=facts)
    assert (result.rc, result.self_healed, result.reason) == (1, False, "fatal_safety_error")
