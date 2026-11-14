"""Матрица строгого каузального восстановления без транспортных зависимостей."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace

import pytest

from core.turn_outcome_policy import (
    CausalCompletionFacts, CausalDrainFacts, CausalErrorFacts, CausalErrorIdentity, CausalOutcomeDecision, CausalOutcomeInput, CausalProcessFacts, CausalRecoveryConfig,
    CausalTerminalFacts, error_identity_digest, evaluate_causal_turn_recovery, normalize_error_identity,
)
_LONG_ERROR = "PT_AT_ERROR " + "x" * 600
def _facts(error_seq: int = 321, completion_seq: int = 370, returncode: int | None = 1, text: str = _LONG_ERROR) -> CausalOutcomeInput:
    normalized, digest = normalize_error_identity(text), error_identity_digest(text)
    return CausalOutcomeInput(CausalRecoveryConfig(True, True, 0),
        CausalErrorFacts(CausalErrorIdentity(error_seq, 0, digest, len(normalized)), True, "ERROR", digest),
        CausalCompletionFacts(completion_seq, 0, True, True), CausalTerminalFacts(CausalDrainFacts(True, True, True), CausalProcessFacts(True, returncode, False), "closed", False))
def _changed(group: str, **changes: object) -> CausalOutcomeInput:
    facts = _facts()
    if group == "identity":
        return replace(facts, error=replace(facts.error, identity=replace(facts.error.identity, **changes)))
    if group in ("config", "error", "completion"):
        record = {"config": facts.config, "error": facts.error, "completion": facts.completion}[group]
        return replace(facts, **{group: replace(record, **changes)})
    if group in ("drain", "process"):
        component = facts.terminal.drain if group == "drain" else facts.terminal.process
        return replace(facts, terminal=replace(facts.terminal, **{group: replace(component, **changes)}))
    if group == "terminal":
        return replace(facts, terminal=replace(facts.terminal, **changes))
    raise ValueError(group)
@pytest.mark.parametrize("error_seq,completion_seq", ((218, 370), (321, 370), (136, 283)))
def test_primary_and_sister_exact_echo(error_seq: int, completion_seq: int) -> None:
    facts = _facts(error_seq, completion_seq)
    assert facts.error.identity.length > 500
    decision = evaluate_causal_turn_recovery(facts)
    assert (decision.recovered, decision.allow_reconcile, decision.clear_error) == (True,) * 3
    assert (decision.outcome_mode, decision.reason) == ("causal_echo_only", "causal_echo_recovered")
@pytest.mark.parametrize("returncode,mode", ((1, "causal_echo_only"), (0, "causal_echo_zero_rc")))
def test_content_safety_echo(returncode: int, mode: str) -> None:
    decision = evaluate_causal_turn_recovery(_facts(returncode=returncode, text="Content safety: request rejected"))
    assert decision.recovered and decision.allow_reconcile and decision.clear_error
    assert decision.outcome_mode == mode
@pytest.mark.parametrize("group,field,value,reason", (
    ("config", "master_self_heal", False, "self_heal_disabled"), ("config", "causal_recovery_enabled", False, "causal_recovery_disabled"),
    ("identity", "seq", -1, "missing_structured_error"),
    ("completion", "last_completion_seq", 321, "completion_not_after_error"), ("completion", "last_completion_seq", 320, "completion_not_after_error"),
    ("identity", "attempt", 1, "attempt_mismatch"), ("completion", "completion_attempt", -1, "attempt_mismatch"),
    ("error", "error_from_structured_record", False, "unstructured_error"),
    ("identity", "sha256", "", "missing_error_identity"),
    ("error", "result_error_sha256", "", "error_identity_mismatch"), ("error", "result_error_sha256", "other", "error_identity_mismatch"),
    ("completion", "completion_done_without_tools", False, "completion_has_tools"), ("completion", "has_final_text", False, "missing_final_text"),
    ("terminal", "has_late_error_or_open_step", True, "late_error_or_open_step"),
    ("process", "has_fatal_error", True, "fatal_error"),
    ("drain", "explicit_drain_complete", False, "drain_not_explicit"), ("drain", "drain_complete", False, "drain_incomplete"),
    ("drain", "producer_stopped", False, "producer_not_stopped"), ("terminal", "tool_status", "open", "tools_not_closed"),
    ("terminal", "tool_status", "unknown", "tools_not_closed"), ("terminal", "tool_status", "malformed", "tools_not_closed"),
    ("process", "process_exited", False, "process_not_exited"),
    *(("process", "returncode", rc, "unsupported_returncode") for rc in (None, -11, 139, 128, 2)),
))
def test_fail_closed(group: str, field: str, value: object, reason: str) -> None:
    decision = evaluate_causal_turn_recovery(_changed(group, **{field: value}))
    assert (decision.recovered, decision.allow_reconcile, decision.clear_error) == (False,) * 3
    assert (decision.outcome_mode, decision.reason, decision.detail) == ("unrecovered", reason, "")
    assert _LONG_ERROR not in repr(decision)
def test_same_500_character_prefix_is_not_identity() -> None:
    first, second = _LONG_ERROR + " first", _LONG_ERROR + " second"
    assert first[:500] == second[:500]
    facts = _facts(text=first)
    facts = replace(facts, error=replace(facts.error, result_error_sha256=error_identity_digest(second)))
    assert evaluate_causal_turn_recovery(facts).reason == "error_identity_mismatch"
    assert not evaluate_causal_turn_recovery(facts).recovered
@pytest.mark.parametrize("text,expected", (
    (None, ""), ("", ""), (" \t\r\n ", ""), (" \tError\r\nNext\rEnd \n", "Error\nNext\nEnd"),
    ("Error  Next", "Error  Next"), ("ERROR", "ERROR"),
))
def test_exact_normalization(text: str | None, expected: str) -> None:
    assert normalize_error_identity(text) == expected
    assert error_identity_digest(text) == error_identity_digest(expected)
def test_digest_known_sha256_and_empty_identity() -> None:
    assert error_identity_digest(" abc\r\n") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert error_identity_digest(None) == error_identity_digest(" \r\n") == ""
    assert error_identity_digest("ERROR") != error_identity_digest("error") and error_identity_digest("a  b") != error_identity_digest("a b")
def test_crlf_and_outer_whitespace_echo_is_recovered() -> None:
    facts = _facts(text=" \tERROR\r\nnext\rline  ")
    facts = replace(facts, error=replace(facts.error, result_error_sha256=error_identity_digest("ERROR\nnext\nline")))
    assert evaluate_causal_turn_recovery(facts).recovered
def test_negative_matching_attempts_are_rejected() -> None:
    facts = _changed("identity", attempt=-1)
    facts = replace(facts, completion=replace(facts.completion, completion_attempt=-1))
    assert evaluate_causal_turn_recovery(facts).reason == "attempt_mismatch"
def test_grouped_records_are_frozen_and_constructors_are_bounded() -> None:
    facts = _facts()
    records = (facts, facts.config, facts.error, facts.error.identity, facts.completion, facts.terminal, facts.terminal.drain, facts.terminal.process, evaluate_causal_turn_recovery(facts))
    for record in records:
        assert len(fields(record)) <= 4
        with pytest.raises(FrozenInstanceError):
            setattr(record, fields(record)[0].name, None)
def test_attempt_metadata_does_not_replace_error_completion_identity() -> None:
    assert evaluate_causal_turn_recovery(_changed("config", attempt=9)).recovered
def test_decision_flags_are_derived_and_immutable() -> None:
    decision = CausalOutcomeDecision(True, "causal_echo_only", "causal_echo_recovered", "")
    assert decision.allow_reconcile and decision.clear_error
    with pytest.raises(FrozenInstanceError):
        setattr(decision, "clear_error", False)
def test_zero_error_seq_is_valid_identity_before_completion() -> None:
    assert evaluate_causal_turn_recovery(_facts(error_seq=0, completion_seq=1)).recovered
    assert evaluate_causal_turn_recovery(_facts(error_seq=0, completion_seq=0)).reason == "completion_not_after_error"
