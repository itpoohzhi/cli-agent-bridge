"""Матрица строгого каузального восстановления без транспортных зависимостей."""
from __future__ import annotations
from dataclasses import FrozenInstanceError, fields, replace
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import cast
import pytest
from core import stream_interruption_recovery as facade
from core import turn_finalization as done
from core.route_health_policy import RetryBudgetConfig
from core.stream_interruption_recovery import tail_turn_facts as extract_tail_facts
from core.turn_outcome_policy import CausalCompletionFacts, CausalDrainFacts, CausalErrorFacts, CausalErrorIdentity, CausalOutcomeDecision, CausalOutcomeInput, CausalProcessFacts, CausalRecoveryConfig, CausalTerminalFacts, error_identity_digest, evaluate_causal_turn_recovery, normalize_error_identity
_LONG_ERROR = "PT_AT_ERROR " + "x" * 600
_FLAG = "BRIDGE_CAUSAL_TURN_RECOVERY_ENABLED"
def _facts(error_seq: int = 321, completion_seq: int = 370, returncode: int | None = 1, text: str = _LONG_ERROR) -> CausalOutcomeInput:
    normalized, digest = normalize_error_identity(text), error_identity_digest(text)
    return CausalOutcomeInput(CausalRecoveryConfig(True, True, 0), CausalErrorFacts(CausalErrorIdentity(error_seq, 0, digest, len(normalized)), True, "ERROR", digest), CausalCompletionFacts(completion_seq, 0, True, True), CausalTerminalFacts(CausalDrainFacts(True, True, True), CausalProcessFacts(True, returncode, False), "closed", False))
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
@pytest.mark.parametrize("group,field,value,reason", (("config", "master_self_heal", False, "self_heal_disabled"), ("config", "causal_recovery_enabled", False, "causal_recovery_disabled"), ("identity", "seq", -1, "missing_structured_error"), ("error", "error_from_structured_record", False, "unstructured_error"), ("identity", "sha256", "", "missing_error_identity"), ("completion", "last_completion_seq", 321, "completion_not_after_error"), ("completion", "last_completion_seq", 320, "completion_not_after_error"),
    ("identity", "attempt", 1, "attempt_mismatch"), ("completion", "completion_attempt", -1, "attempt_mismatch"), ("error", "result_error_sha256", "", "error_identity_mismatch"), ("error", "result_error_sha256", "other", "error_identity_mismatch"), ("completion", "completion_done_without_tools", False, "completion_has_tools"), ("completion", "has_final_text", False, "missing_final_text"), ("terminal", "has_late_error_or_open_step", True, "late_error_or_open_step"), ("process", "has_fatal_error", True, "fatal_error"), ("drain", "explicit_drain_complete", False, "drain_not_explicit"), ("drain", "drain_complete", False, "drain_incomplete"),
    ("drain", "producer_stopped", False, "producer_not_stopped"), ("terminal", "tool_status", "open", "tools_not_closed"), ("terminal", "tool_status", "unknown", "tools_not_closed"), ("terminal", "tool_status", "malformed", "tools_not_closed"), ("process", "process_exited", False, "process_not_exited"), *(("process", "returncode", rc, "unsupported_returncode") for rc in (None, -11, 139, 128, 2)),))
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
@pytest.mark.parametrize("text,expected", ((None, ""), ("", ""), (" \t\r\n ", ""), (" \tError\r\nNext\rEnd \n", "Error\nNext\nEnd"), ("Error  Next", "Error  Next"), ("ERROR", "ERROR")))
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
    result = facade.resolve_done_turn_outcome(rc=1, result_error=error, result_status="ERROR", final_text="Финал", emitted_text="", causal_input=facts, **facade.tail_turn_facts(tail))
    trusted = facade.trusted_final_text("Финал", error, tail, causal_input=facts)
    assert result.self_healed is (case == "exact")
    assert result.rc == (0 if case == "exact" else 1)
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
def test_tail_facts_missing_transient_error_defaults_false() -> None:
    tail = SimpleNamespace(final_planner=False, last_planner_step_index=-1, last_error_step_index=-1, drain_outcome="done")
    assert extract_tail_facts(tail, "")["had_transient_error"] is False
def test_tail_legacy_calls_and_unproven_text() -> None:
    assert not any(facade.is_transient_stream_interruption("connection reset " + t) for t in ("; code: 401", '{"status": "400"}', "status_code='404'", "http_status=400", "response_status: 422")) and facade.is_transient_stream_interruption("connection reset status: 429")
    fresh = facade.InterruptionTailState()
    assert (fresh.last_planner_step_index, fresh.last_error_step_index, fresh.last_error_attempt, fresh.last_completion_attempt) == (-1, -1, -1, -1)
    assert (fresh.final_planner, fresh.had_transient_error, fresh.error_from_structured_record, fresh.last_error_length) == (False, False, False, 0)
    assert facade.tail_causal_facts(fresh).has_late_error_or_open_step is False
    fresh.note_error_record(0, text="connection reset")
    assert fresh.has_open_planner_after_completion is False
    tail = facade.InterruptionTailState()
    tail.note_error_record(1)
    tail.note_planner_record({"content": "Финал"}, 2)
    assert facade.trusted_final_text("Финал", _LONG_ERROR, tail) == ""
    assert (facade.trusted_final_text("Финал", "", tail), facade.trusted_final_text("Финал", "stream was interrupted", tail)) == ("Финал", "Финал")
    assert not facade.evaluate_done_causal_recovery(_facts(text="")).recovered
    tail.note_error_record(rtype="ERROR_MESSAGE", rec={"message": _LONG_ERROR}, idx=3, attempt=4)
    assert facade.tail_causal_facts(tail).error.attempt == 4
    tail.note_error_record(4, text="e", attempt=True)
    assert facade.tail_causal_facts(tail).error.attempt == -1
    assert facade.tail_causal_facts(object()).has_late_error_or_open_step is False
    assert facade.settle_error("", _LONG_ERROR, "ERROR") == _LONG_ERROR
def test_legacy_turn_defaults_and_retry_guards() -> None:
    facts: dict[str, object] = dict(rc=1, result_error="connection reset", result_status="ERROR", final_text="Финал", emitted_text="")
    assert facade.resolve_done_turn_outcome(**facts, completion_done_without_tools=True, last_completion_seq=0, drain_complete=True).self_healed is True
    assert facade.resolve_done_turn_outcome(**facts, completion_done_without_tools=True, last_error_seq=-2, drain_complete=True).self_healed is False
    assert facade.resolve_done_turn_outcome(**facts, last_completion_seq=0, drain_complete=True).self_healed is False
    assert facade.resolve_done_turn_outcome(**facts, completion_done_without_tools=True, last_completion_seq=0).self_healed is False
    assert facade.resolve_done_turn_outcome(rc=1, result_error="", result_status="DONE", final_text="Финал", emitted_text="", completion_done_without_tools=True, last_completion_seq=0, drain_complete=True).self_healed is False
    ok_retry = facade.evaluate_stream_retry_eligibility(error_text="connection reset", delivered=False, attempt=0, max_attempts=1)
    assert (ok_retry.can_retry, ok_retry.keep_hot_session, ok_retry.reason) == (True, True, "transient_pre_delivery_retry") and ok_retry.attempt_budget_s > 0
    blocked, hot = facade.RetryDecision(False, False, "retry_blocked", 0.0), facade.RetryDecision(False, True, "retry_blocked", 0.0)
    assert facade.evaluate_stream_retry_eligibility(error_text="connection reset", delivered=False, unknown=1) == blocked
    assert facade.evaluate_stream_retry_eligibility(error_text=123, delivered=False) == blocked
    assert facade.evaluate_stream_retry_eligibility(error_text="connection reset", delivered=False, attempt=-1, max_attempts=1) == blocked
    assert facade.evaluate_stream_retry_eligibility(error_text="connection reset", delivered=False, attempt=0, max_attempts=0) == hot
    assert facade.evaluate_stream_retry_eligibility(error_text="connection reset", delivered=False, budget_config=RetryBudgetConfig(max_attempts=0)) == hot
@pytest.mark.parametrize("dto,legacy,limit", ((3, "absent", 3), (4, "absent", 4), (4, 2, 2), (2, 4, 2), (None, "absent", 2), (None, None, 2), (4, None, 4)))
def test_retry_limit_sources(dto: int | None, legacy: int | str | None, limit: int) -> None:
    kw: dict[str, object] = {} if dto is None else {"budget_config": RetryBudgetConfig(max_attempts=dto)}
    kw |= {} if legacy == "absent" else {"max_attempts": legacy}
    def decide(attempt: int) -> facade.RetryDecision:
        return facade.evaluate_stream_retry_eligibility(error_text="connection reset", delivered=False, attempt=attempt, **kw)
    assert decide(limit - 1).can_retry and decide(limit - 1).attempt_budget_s > 0
    assert not decide(limit).can_retry
def _tail_facts(tail: facade.InterruptionTailState) -> CausalOutcomeInput:
    snapshot, facts = facade.tail_causal_facts(tail), _facts()
    return replace(facts, error=replace(facts.error, identity=snapshot.error, error_from_structured_record=snapshot.error_from_structured_record), completion=snapshot.completion, terminal=replace(facts.terminal, has_late_error_or_open_step=snapshot.has_late_error_or_open_step))
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
@pytest.mark.parametrize("env_value,json_value,expected", (
    ("", None, True), ("true", True, True), ("false", True, False), ("true", False, False), ("0", True, False), ("NO", True, False), (" off ", True, False), ("invalid", True, False),))
def test_recovery_switch_veto(tmp_path: Path, env_value: str, json_value: bool | None, expected: bool) -> None:
    path = tmp_path / "local.json"
    if json_value is not None:
        _ = path.write_text(json.dumps({_FLAG: json_value}))
    assert done.read_recovery_switch(path, 256, {_FLAG: env_value}, tmp_path / "absent") is expected
    assert done.read_recovery_switch(path, 256, {"AGY_SELF_HEAL_INTERRUPTED_TURN": "false"}) is False
    for limit in (0, True):
        assert done.read_recovery_switch(path, limit, {}, tmp_path / "absent") is False
@pytest.mark.parametrize("body", (b"{", b"[]", b"[true]", b"\xff", b" " * 257, b'{"BRIDGE_CAUSAL_TURN_RECOVERY_ENABLED":1}', b'{"BRIDGE_CAUSAL_TURN_RECOVERY_ENABLED":"true"}', b'{"causal_turn_recovery_enabled":null}'))
def test_recovery_switch_bad_config(tmp_path: Path, body: bytes) -> None:
    _ = (path := tmp_path / "bad.json").write_bytes(body)
    assert done.read_recovery_switch(path, 256, {}, tmp_path / "absent") is False
    assert done._read_config_flag(path, 256) is False  # pyright: ignore[reportPrivateUsage]
def test_recovery_switch_paths_freshness_and_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, other, link = (tmp_path / name for name in ("local", "global", "link"))
    _ = path.write_text("{}")
    _ = other.write_text(json.dumps({_FLAG: False}))
    assert not done.read_recovery_switch(path, 256, {}, other)
    assert done.read_recovery_switch(other, 256, {"BRIDGE_DYNAMIC_CONFIG_PATH": str(path)})
    _ = path.write_text(json.dumps({"causal_turn_recovery_enabled": False}))
    assert not done.read_recovery_switch(path, 256, {}, tmp_path / "absent")
    _ = path.write_text("{}")
    assert done.read_recovery_switch(path, 2, {}, tmp_path / "absent") is True
    assert done.read_recovery_switch(path, 1, {}, tmp_path / "absent") is False
    assert done._read_config_flag(path, 1) is False  # pyright: ignore[reportPrivateUsage]
    with monkeypatch.context() as patch:
        patch.setattr(os, "fstat", lambda _fd=0: os.stat_result((stat.S_IFDIR, 0, 0, 0, 0, 0, 0, 0, 0, 0)))
        assert done.read_recovery_switch(path, 2, {}, tmp_path / "absent") is False
        assert done._read_config_flag(path, 2) is False  # pyright: ignore[reportPrivateUsage]
    assert done.read_recovery_switch(None, 256, {}, tmp_path / "absent")
    read = os.read
    def swap(fd: int, size: int) -> bytes:
        _ = path.rename(tmp_path / "old")
        _ = path.write_text(json.dumps({_FLAG: False}))
        return read(fd, size)
    monkeypatch.setattr(os, "read", swap)
    assert done.read_recovery_switch(path, 256, {}, tmp_path / "absent")
    monkeypatch.setattr(os, "read", read)
    link.symlink_to(path)
    assert not done.read_recovery_switch(link, 256, {}, tmp_path / "absent")
    os.mkfifo(tmp_path / "fifo")
    assert not done.read_recovery_switch(tmp_path / "fifo", 256, {}, tmp_path / "absent")
    assert not done.read_recovery_switch(tmp_path, 256, {}, tmp_path / "absent")
    assert done.read_recovery_switch(path / "missing", 256, {}, path / "other")
    def denied(*_args: object) -> int:
        raise PermissionError
    monkeypatch.setattr(os, "open", denied)
    assert not done.read_recovery_switch(path, 256, {}, tmp_path / "absent")
@pytest.mark.parametrize("case", ("exact", "suffix", "timeout", "window_complete", "live", "tools", "disabled", "tail_only", "cleared", "zero_rc", "process_live", "fatal", "rc2", "unknown", "usage", "non_stream"))
def test_finalize_done_orders_and_redacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    events: list[object] = []
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(path := tmp_path / "config"))
    monkeypatch.delenv(_FLAG, raising=False)
    monkeypatch.delenv("AGY_SELF_HEAL_INTERRUPTED_TURN", raising=False)
    tail = facade.InterruptionTailState()
    error = _LONG_ERROR + (" suffix" if case == "suffix" else "")
    def drain() -> list[object]:
        events.append("drain")
        tail.note_error_record(321, text=_LONG_ERROR)
        tail.note_planner_record({"content": "Финал"}, 370)
        _ = path.write_text(json.dumps({_FLAG: case != "disabled"}))
        return ["tail-event"]
    def reconcile(text: str) -> str:
        assert events[:2] == ["drain", ["tail-event"]]
        events.append("reconcile")
        return text
    def snapshot() -> done.DoneSnapshot:
        assert events[:2] == ["drain", ["tail-event"]]
        return done.DoneSnapshot(done.DoneTextFacts("" if case == "tail_only" else "Финал", "", "" if case == "cleared" else error, error if case == "cleared" else ""),
            done.DoneResultFacts("ERROR", {"zero_rc": 0, "rc2": 2}.get(case, 1), case != "process_live", 0, case == "fatal"),
            done.DoneDeliveryFacts(case not in ("usage", "non_stream"), True, reconcile, False),
            done.DoneRecoveryFacts(True, tail, done.DoneDrainFacts(case if case in ("timeout", "window_complete") else "complete", case != "live"),
                {"tools": "open", "unknown": "unknown"}.get(case, "closed")))
    ports = done.DonePorts(lambda *args: args, events.append, events.append, lambda: False)
    result = done.finalize_done(done.DoneRequest((1, "Финал", None), {}, (error[:500], "")), ports, done.DoneRuntimePorts(snapshot, drain), done.DoneConfig(path, 256, case != "usage", case == "usage"), events.append)
    recovered = case in ("exact", "tail_only", "cleared", "zero_rc", "usage", "non_stream")
    assert result == (("done", 0, "") if recovered else ("agy_error", 2 if case == "rc2" else 1, error))
    assert ("reconcile" in events) is (recovered and case not in ("usage", "non_stream"))
    if recovered:
        assert "Финал" in events
        diagnostic = cast(object, json.loads(str(events[-1])))
        assert diagnostic == dict(reason="causal_echo_recovered", last_error_seq=321, last_completion_seq=370, rc=0 if case == "zero_rc" else 1)
        assert _LONG_ERROR not in str(events)
@pytest.mark.parametrize("case", ("clean", "gone", "error", "nonzero", "fallback", "empty_final", "payload_rc", "result_rc"))
def test_finalize_done_legacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent"))
    content: list[str] = []
    rc = None if case == "payload_rc" else 2 if case == "result_rc" else int(case in ("error", "nonzero"))
    emitted = "Первое." if case in ("nonzero", "fallback") else ""
    tail = facade.InterruptionTailState()
    tail.note_planner_record({"content": "Старый финал"}, 1)
    final = "" if case == "empty_final" else "Финал"
    snapshot = done.DoneSnapshot(done.DoneTextFacts(final, emitted, "", ""), done.DoneResultFacts("ERROR" if case == "error" else "DONE", rc, True, 0), done.DoneDeliveryFacts(case == "fallback", not emitted, lambda _text: "", lambda: True), done.DoneRecoveryFacts(True, tail, done.DoneDrainFacts(), "closed"))
    ports = done.DonePorts(lambda *args: args, content.append, lambda _events: None, lambda: case == "gone")
    result = done.finalize_done(done.DoneRequest((7 if case in ("payload_rc", "result_rc") else int(rc or 0), final, {"error": _LONG_ERROR}), {}, ("", "")), ports, done.DoneRuntimePorts(lambda: snapshot, stderr=lambda: " stderr "), done.DoneConfig(None, 256), lambda _line: pytest.fail("unexpected recovery"))
    expected = {"gone": ("client_gone", 1), "error": ("agy_error", 1, _LONG_ERROR[:500]), "payload_rc": ("agy_error", 7, _LONG_ERROR[:500]), "result_rc": ("agy_error", 2, _LONG_ERROR[:500])}
    assert result == expected.get(case, ("done", rc, "stderr"))
    assert content == ([] if case in ("error", "nonzero", "empty_final", "payload_rc", "result_rc") else ["\n\nФинал" if case == "fallback" else "Финал"])
@pytest.mark.parametrize("outcome", ("timeout", "ok"))
def test_finalize_transient_drain_veto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent"))
    monkeypatch.setenv(_FLAG, "false")
    monkeypatch.delenv("AGY_SELF_HEAL_INTERRUPTED_TURN", raising=False)
    error, tail = "connection reset by peer", facade.InterruptionTailState()
    tail.note_error_record(1, text=error)
    tail.note_planner_record({"content": "Финал", "status": "DONE"}, 2)
    snapshot = done.DoneSnapshot(done.DoneTextFacts("Финал", "", error, ""), done.DoneResultFacts("ERROR", 1, True, 0), done.DoneDeliveryFacts(False, True, lambda text: text, False), done.DoneRecoveryFacts(True, tail, done.DoneDrainFacts(outcome, True), "closed"))
    ports = done.DonePorts(lambda *args: args, lambda _text: None, lambda _events: None, lambda: False)
    assert done.finalize_done(done.DoneRequest((1, "Финал", None), {}, ("", "")), ports, done.DoneRuntimePorts(lambda: snapshot), done.DoneConfig(None, 256), lambda _line: None) == (("agy_error", 1, error) if outcome == "timeout" else ("done", 0, ""))
