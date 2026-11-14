"""Матрица строгого каузального восстановления без транспортных зависимостей."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace

import pytest

from core import stream_interruption_recovery as facade
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
@pytest.mark.parametrize("case", ("exact", "suffix", "attempt", "unstructured", "missing", "open", "tools", "late_error"))
def test_tail_causal_facade_agrees_on_text_and_error(case: str) -> None:
    tail = facade.InterruptionTailState()
    if case != "missing":
        tail.note_error_record("ERROR_MESSAGE", {"content": _LONG_ERROR}, 321)
    tail.note_planner_record({"content": "Финал", "status": "DONE"}, 370)
    if case == "attempt":
        tail.last_error_attempt = 1
    if case == "unstructured":
        tail.error_from_structured_record = False
    if case in ("open", "tools"):
        tail.note_planner_record({"content": "Продолжаю", "status": "RUNNING", "tool_calls": ["call"] if case == "tools" else []}, 371)
    if case == "late_error":
        tail.note_error_record(371, text=_LONG_ERROR)
    snapshot, facts = facade.tail_causal_facts(tail), _tail_facts(tail)
    error = _LONG_ERROR + (" suffix" if case == "suffix" else "")
    result = facade.resolve_done_turn_outcome(rc=1, result_error=error, result_status="ERROR",
        final_text="Финал", emitted_text="", causal_input=facts, **facade.tail_turn_facts(tail))
    trusted = facade.trusted_final_text("Финал", error, tail, causal_input=facts)
    assert result.self_healed is (case == "exact")
    assert bool(trusted) is result.self_healed
    assert (result.error == "") is result.self_healed
    assert snapshot.error.sha256 == error_identity_digest("" if case == "missing" else _LONG_ERROR)
    assert snapshot.error.length == (0 if case == "missing" else len(_LONG_ERROR))
    assert snapshot.completion.completion_attempt == 0
    assert facade.tail_turn_facts(tail)["last_error_seq"] == snapshot.error.seq
    with pytest.raises(FrozenInstanceError):
        setattr(snapshot, "has_late_error_or_open_step", False)
    if case == "open":
        tail.note_planner_record({"content": "Новый финал", "status": "DONE"}, 372)
        assert not facade.tail_causal_facts(tail).has_late_error_or_open_step
        assert snapshot.has_late_error_or_open_step
def test_tail_legacy_calls_and_unproven_text() -> None:
    tail = facade.InterruptionTailState()
    tail.note_error_record(1)
    tail.note_planner_record({"content": "Финал"}, 2)
    assert facade.trusted_final_text("Финал", _LONG_ERROR, tail) == ""
    assert (facade.trusted_final_text("Финал", "", tail), facade.trusted_final_text("Финал", "stream was interrupted", tail)) == ("Финал", "Финал")
    assert not facade.evaluate_done_causal_recovery(_facts(text="")).recovered
    tail.note_error_record(rtype="ERROR_MESSAGE", rec={"message": _LONG_ERROR}, idx=3, attempt=4)
    assert facade.tail_causal_facts(tail).error.attempt == 4
    assert facade.settle_error("", _LONG_ERROR, "ERROR") == _LONG_ERROR
def _tail_facts(tail: facade.InterruptionTailState) -> CausalOutcomeInput:
    snapshot, facts = facade.tail_causal_facts(tail), _facts()
    return replace(facts, error=replace(facts.error, identity=snapshot.error, error_from_structured_record=snapshot.error_from_structured_record), completion=snapshot.completion,
        terminal=replace(facts.terminal, has_late_error_or_open_step=snapshot.has_late_error_or_open_step))
def test_zero_indices_strict_order_and_drain() -> None:
    tail = facade.InterruptionTailState()
    tail.note_planner_record({"content": "Начало", "status": "DONE"}, 0)
    assert tail.last_planner_step_index == 0
    tail.note_error_record("ERROR_MESSAGE", {"content": _LONG_ERROR}, 0)
    assert tail.has_open_planner_after_completion is True
    for seq in (0, 1):
        tail.note_planner_record({"content": "Финал", "status": "DONE"}, seq)
        facts = _tail_facts(tail)
        assert facts.error.identity.seq == 0
        assert facts.completion.last_completion_seq == seq
        assert facts.terminal.has_late_error_or_open_step is (seq == 0)
        assert evaluate_causal_turn_recovery(facts).recovered is (seq > 0)
        if seq == 0:
            assert facade.trusted_final_text("Финал", _LONG_ERROR, tail, facts) == ""
    for outcome in ("ok", "timeout"):
        setattr(tail, "drain_outcome", outcome)
        assert facade.tail_turn_facts(tail)["drain_complete"] is (outcome == "ok")
def _resolve(**changes: object) -> facade.TurnOutcomeResolution:
    args: dict[str, object] = dict(rc=1, result_error=_LONG_ERROR, result_status="ERROR", final_text="Финал", emitted_text="", causal_input=_facts())
    return facade.resolve_done_turn_outcome(**{**args, **changes})
def test_causal_resolution_reason_and_rc_precedence() -> None:
    assert _resolve().self_healed
    inconsistent = _resolve(rc=2)
    assert (inconsistent.self_healed, inconsistent.reason, inconsistent.rc) == (False, "inconsistent_causal_facts", 2)
    suffix = _LONG_ERROR + " suffix"
    unrecovered = _resolve(result_error=suffix, has_unclosed_tool_call=True)
    assert (unrecovered.reason, unrecovered.rc, unrecovered.error) == ("error_identity_mismatch", 1, suffix)
    assert _resolve(rc=0, result_error=suffix).rc == 1
@pytest.mark.parametrize("rc,error,status,clean", ((0, "", "DONE", True), (1, "", "DONE", False), (0, "", "ERROR", False), (0, "boom", "DONE", False)))
def test_clean_done_requires_zero_rc_no_error_and_non_error_status(rc: int, error: str, status: str, clean: bool) -> None:
    result = facade.resolve_done_turn_outcome(rc=rc, result_error=error, result_status=status, final_text="Финал", emitted_text="")
    assert (result.reason == "clean_done") is clean
    assert (result.state == "done") is clean
def test_transient_recovery_requires_completion_strictly_after_error() -> None:
    facts: dict[str, object] = dict(rc=1, result_error="stream was interrupted", result_status="ERROR", final_text="Финал", emitted_text="",
        completion_done_without_tools=True, drain_complete=True, had_transient_error=True, last_error_seq=4)
    assert facade.resolve_done_turn_outcome(**{**facts, "last_completion_seq": 5}).self_healed
    for seq in (4, 3):
        assert not facade.resolve_done_turn_outcome(**{**facts, "last_completion_seq": seq}).self_healed
def test_error_record_with_same_or_newer_seq_replaces_identity() -> None:
    tail = facade.InterruptionTailState()
    tail.note_error_record(5, text="first")
    tail.note_error_record(5, text="second")
    assert tail.last_error_sha256 == error_identity_digest("second")
    tail.note_error_record(4, text="older")
    assert (tail.last_error_step_index, tail.last_error_sha256) == (5, error_identity_digest("second"))
def test_trusted_final_text_prefers_model_text_over_tail_planner() -> None:
    tail = facade.InterruptionTailState()
    tail.note_planner_record({"content": "Хвост", "status": "DONE"}, 2)
    assert facade.trusted_final_text("", "stream was interrupted", tail) == "Хвост"
    assert facade.trusted_final_text("Ответ", "stream was interrupted", tail) == "Ответ"
@pytest.mark.parametrize("attempt,expected", ((3, 3), (0, 0), (True, -1), ("1", -1), (None, -1), (1.0, -1)))
def test_error_attempt_keeps_only_exact_int(attempt: object, expected: int) -> None:
    tail = facade.InterruptionTailState()
    tail.note_error_record(1, text="first")
    assert tail.last_error_attempt == 0
    tail.note_error_record(1, text="second", attempt=attempt)
    assert tail.last_error_attempt == expected
def test_open_step_flag_is_exact_bool_and_defaults_closed() -> None:
    assert facade.tail_causal_facts(object()).has_late_error_or_open_step is False
    tail = facade.InterruptionTailState()
    tail.note_planner_record({"content": "Финал", "status": "DONE"}, 1)
    assert facade.tail_causal_facts(tail).has_late_error_or_open_step is False
    tail.note_planner_record({"content": "Шаг", "status": "RUNNING"}, 2)
    assert facade.tail_causal_facts(tail).has_late_error_or_open_step is True
def test_healed_causal_resolution_is_clean_done() -> None:
    healed = _resolve()
    assert (healed.state, healed.rc, healed.error, healed.self_healed, healed.final) == ("done", 0, "", True, True)
    failed = _resolve(rc=2)
    assert (failed.state, failed.rc, failed.error, failed.final) == ("agy_error", 2, _LONG_ERROR, True)
