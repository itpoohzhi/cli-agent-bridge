"""Регрессии накопленного safety-вето и канонического переключателя."""
from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path

import pytest

import test_causal_turn_recovery_flow as flow
from core import stream_interruption_recovery as recovery
from core.turn_finalization import read_recovery_switch
from core.turn_outcome_policy import is_fatal_safety_error


@pytest.mark.parametrize("marker", ("policy%5fviolation", "policy+violation", "SAFETY", "BLOCK_REASON: SAFETY", "PROHIBITED_CONTENT", "RECITATION"))
def test_encoded_and_machine_safety_codes(marker: str) -> None:
    assert is_fatal_safety_error(marker)


@pytest.mark.parametrize("marker", (r"\u0073afety: request rejected", "&#x73;afety: request rejected", "content%255fpolicy%255fviolation", "%2573afety: connection reset", "content%25255fpolicy%25255fviolation", "content_safety", "safety_filter", "fatal_safety_error: connection reset", '{"block_reason": "OTHER"}', *("%" + "25" * depth + "73afety: connection reset" for depth in (8, 9, 35)), "%" + "25" * 35 + "41"))
def test_nested_encoded_safety_veto(marker: str) -> None:
    assert is_fatal_safety_error(marker)


@pytest.mark.parametrize("text", ("safety_cap_s exceeded", "thread_safety lock error", "thread-safety lock error", '{"block_reason": null}', '{"block_reason": "NONE"}', 'block_reason: none', *('{"finish_reason": "' + reason + '"}' for reason in ("null", "none", "stop", "length", "tool_calls", "end_turn", "tool_use", "max_tokens", "stop_sequence"))))
def test_operational_safety_and_neutral_block_reason(text: str) -> None:
    assert not is_fatal_safety_error(text)


@pytest.mark.parametrize("job", (False, True))
@pytest.mark.parametrize("fail", (False, True))
def test_json_initial_attempt_scope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, job: bool, fail: bool) -> None:
    import sys

    bridge = flow._load_bridge(monkeypatch, tmp_path)
    runtime = sys.modules["agy_runtime.sse_body_runner"]
    handler = bridge.Handler.__new__(bridge.Handler)
    observed: list[tuple[object, ...]] = []
    sent: list[tuple[int, object]] = []
    handler._send = lambda code, body: sent.append((code, body))
    def invoke(*_args: object) -> flow._Outcome:
        observed.append(flow._start_attempt_tail(bridge, monkeypatch))
        if fail:
            raise RuntimeError("attempt failed")
        return flow._Outcome(state="done", text="final", rc=0, err="")
    handler._run_once_impl = invoke
    setattr(handler, "connection", None)
    monkeypatch.setattr(bridge, "_client_gone", lambda _conn: False)
    ctx = dict(model="test", full_prompt="test", emulate_tools=False, step_job_id=f"json-{fail}" if job else "")
    with pytest.raises(RuntimeError, match="attempt failed") if fail and not job else nullcontext():
        getattr(handler, "_serve_json")(ctx)
    assert observed == [(0, 0, 0, 0)]
    assert getattr(runtime, "current_attempt_index")() == -1
    assert fail or sent[0][0] == 200


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


@pytest.mark.parametrize("field,value", (("block_reason", "OTHER"), ("block_reason", "SAFETY"), ("finish_reason", "SAFETY"), ("reason", "SAFETY"), ("error", "content_filter"), ("message", "Policy violation"), ("details", {"block_reason": "OTHER"}), ("blockReason", "OTHER"), ("stop_reason", "refusal"), ("finishReason", "SAFETY"), ("promptFeedback", {"blockReason": "OTHER"})))
def test_structured_record_safety_blocks_recovery(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, value: str | dict[str, str]) -> None:
    bridge = flow._load_bridge(monkeypatch, tmp_path)
    monkeypatch.setattr(flow, "_ERROR", "connection reset by peer")
    tail = flow._make_tail(bridge, (1,), 2)
    rec = {"type": "ERROR_MESSAGE", "step_index": 2, "content": flow._ERROR, field: value}
    tail._emit_record(json.dumps(rec).encode())
    tail._emit_record(json.dumps(dict(type="PLANNER_RESPONSE", step_index=3, content=flow._FINAL)).encode())
    assert getattr(tail, "had_safety_error", False)
    _, out = flow._serve_replay(bridge, flow._make_run(tail))
    assert (out["state"], out["rc"], out["text"]) == ("agy_error", 1, "")


@pytest.mark.parametrize("legacy", (None, "false"))
def test_canonical_switch_needs_no_legacy_opt_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, legacy: str | None) -> None:
    bridge = flow._load_bridge(monkeypatch, tmp_path)
    monkeypatch.delenv("AGY_CAUSAL_RECOVERY_ENABLED")
    monkeypatch.delenv("AGY_SELF_HEAL_INTERRUPTED_TURN")
    if legacy is not None:
        monkeypatch.setenv("AGY_SELF_HEAL_INTERRUPTED_TURN", legacy)
    chunks, out = flow._serve_replay(bridge, flow._make_run(flow._make_tail(bridge, (1,), 2)))
    if legacy == "false":
        assert (out["state"], out["rc"], out["text"]) == ("agy_error", 1, "")
    else:
        flow._assert_final_preserved(chunks, out)


def test_resolver_safety_config_vetoes_legacy_transient() -> None:
    from test_causal_turn_recovery import _facts
    from dataclasses import replace

    facts = _facts()
    facts = replace(facts, config=replace(facts.config, is_fatal_safety=True))
    assert not recovery.evaluate_done_causal_recovery(facts, "connection reset").clear_error
    result = recovery.resolve_done_turn_outcome(rc=1, result_error="connection reset", result_status="ERROR", final_text="Финал", emitted_text="", completion_done_without_tools=True, last_completion_seq=2, last_error_seq=1, drain_complete=True, causal_input=facts)
    assert (result.rc, result.self_healed, result.reason) == (1, False, "fatal_safety_error")


@pytest.mark.parametrize("canonical", (False, True))
def test_json_self_heal_kill_switch(tmp_path: Path, canonical: bool) -> None:
    local = tmp_path / "dynamic_config.json"
    flags = {"self_heal_interrupted_turn": False}
    if canonical:
        flags["BRIDGE_CAUSAL_TURN_RECOVERY_ENABLED"] = True
    local.write_text(json.dumps(flags), encoding="utf-8")
    assert not read_recovery_switch(
        local, 4096, env={"BRIDGE_CAUSAL_TURN_RECOVERY_ENABLED": "true"},
        global_path=tmp_path / "missing.json",
    )


@pytest.mark.parametrize("marker", ("&amp;#x73;afety: request rejected; connection reset by peer", r"\U00000073afety", r"\u0026amp;#x73;afety; connection reset", "&amp;" + "amp;" * 35 + "#x73;afety; connection reset"))
def test_composite_encoding_safety_veto(marker: str) -> None:
    assert is_fatal_safety_error(marker)
    assert not recovery.is_transient_stream_interruption(marker)


def test_normalized_safety_veto() -> None:
    assert not recovery.is_transient_stream_interruption("sa\u200bfety; connection reset by peer")


@pytest.mark.parametrize("reason", ("OTHER", "NONE"))
def test_non_json_error_metadata(reason: str) -> None:
    tail = recovery.InterruptionTailState()
    tail.note_error_record("ERROR_MESSAGE", {"blockReason": reason, "content": "connection reset by peer", "metadata": object()}, idx=1)
    assert tail.had_safety_error is (reason == "OTHER")


@pytest.mark.parametrize("marker", (
    *("sa" + char + "fety: request rejected" for char in "\u200b\u200c\u200d\ufeff\xad\u200e\u202a\u2060"),
    r"\x73afety: request rejected", r"\163afety: request rejected",
    "s%E2%80%8Bafety: request rejected", r"\\x73afety", r"\\163afety",
    r"\x5cu0073afety", "ｓａｆｅｔｙ: request rejected",
    "finishReason: SAFETY", "blockReason: OTHER",
))
def test_obfuscated_safety_veto(marker: str) -> None:
    assert is_fatal_safety_error(marker)
    tail = recovery.InterruptionTailState()
    tail.note_error_record("ERROR_MESSAGE", {"content": marker}, idx=1)
    assert tail.had_safety_error


@pytest.mark.parametrize("field", ("finish_reason", "finishReason", "stop_reason", "stopReason"))
@pytest.mark.parametrize("reason", ("MALFORMED_FUNCTION_CALL", "error", "OTHER", "stop", "length", "tool_calls", "end_turn", "tool_use", "max_tokens"))
def test_non_safety_finish_reason_allows_causal_recovery(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, reason: str) -> None:
    assert not is_fatal_safety_error(f"{field}: {reason}")
    bridge = flow._load_bridge(monkeypatch, tmp_path)
    tail = flow._make_tail(bridge, (1,), 2)
    tail._emit_record(json.dumps({"type": "ERROR_MESSAGE", "step_index": 2, "content": flow._ERROR, field: reason}).encode())
    tail._emit_record(json.dumps(dict(type="PLANNER_RESPONSE", step_index=3, content=flow._FINAL)).encode())
    assert not getattr(tail, "had_safety_error", False)
    flow._assert_final_preserved(*flow._serve_replay(bridge, flow._make_run(tail)))


@pytest.mark.parametrize("marker", (
    *("sa" + char + "fety: request rejected" for char in "\u0301\u034f\ufe0f\u061c"),
    r'{\"blockReason\": \"OTHER\"}',
    '{"blockReason": {"code": "OTHER"}}', '{"block_reason": ["OTHER"]}',
))
def test_combining_and_structured_safety_veto(marker: str) -> None:
    assert is_fatal_safety_error(marker)


@pytest.mark.parametrize("value", ('""', "''", "[]", "[ ]", "{}", "{ }", "null", '"NONE"'))
def test_empty_block_reason_is_neutral(value: str) -> None:
    assert not is_fatal_safety_error(f'{{"blockReason": {value}}}')


@pytest.mark.parametrize("metadata", (
    {"finishReason": "SAFETY"}, {"blockReason": {"code": "OTHER"}},
    {"block_reason": ["OTHER"]},
))
def test_planner_safety_invalidates_previous_completion(metadata: dict[str, object]) -> None:
    tail = recovery.InterruptionTailState()
    tail.note_planner_record({"content": "Previous final", "status": "DONE"}, 1, attempt=0)
    assert tail.final_planner
    tail.note_planner_record({"content": "New final", "status": "DONE", **metadata}, 2, attempt=0)
    assert tail.had_safety_error
    assert not tail.final_planner
    assert tail.final_planner_content == ""
    assert tail.has_open_planner_after_completion


def test_planner_safety_blocks_replay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = flow._load_bridge(monkeypatch, tmp_path)
    tail = flow._make_tail(bridge, (1,), 2)
    tail._emit_record(json.dumps(dict(type="PLANNER_RESPONSE", step_index=3, content=flow._FINAL, finishReason="SAFETY")).encode())
    assert getattr(tail, "had_safety_error", False)
    _, out = flow._serve_replay(bridge, flow._make_run(tail))
    assert (out["state"], out["rc"], out["text"]) == ("agy_error", 1, "")


@pytest.mark.parametrize("value", ("none-other", "null/blocked", "none other", "none+other", "null, blocked"))
def test_nonempty_block_reason_with_neutral_prefix_is_safety(value: str) -> None:
    assert is_fatal_safety_error(json.dumps({"blockReason": value}))


@pytest.mark.parametrize("text", ("Rust ensures memory safety at compile time", "safety policy overview", "refusal", "recitation", "sa\u0301fety: request rejected"))
@pytest.mark.parametrize("field", ("content", "thinking"))
def test_planner_free_prose_is_not_safety_metadata(text: str, field: str) -> None:
    tail = recovery.InterruptionTailState()
    tail.note_planner_record({"content": "Final answer", "status": "DONE", field: text}, 1)
    assert not tail.had_safety_error
    assert tail.final_planner
    assert tail.final_planner_content == (text if field == "content" else "Final answer")


@pytest.mark.parametrize("idx", (3, None))
@pytest.mark.parametrize("metadata", ({"finishReason": "SAFETY"}, {"promptFeedback": {"blockReason": "OTHER"}}, {"candidates": [{"finishReason": "SAFETY"}]}, {"details": {"blockReason": "OTHER"}}))
def test_planner_safety_prevents_live_delivery(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, idx: int | None, metadata: dict[str, object]) -> None:
    bridge = flow._load_bridge(monkeypatch, tmp_path)
    tail = flow._make_tail(bridge, (1,), 2)
    delivered: list[tuple[object, ...]] = []
    monkeypatch.setattr(tail, "emit_content", lambda *args: delivered.append(args) or True)
    tail._emit_record(json.dumps(dict(type="PLANNER_RESPONSE", step_index=idx, content="Blocked answer", **metadata)).encode())
    assert delivered == []
    assert getattr(tail, "had_safety_error", False)
    assert not getattr(tail, "final_planner", False)


def test_safety_veto_is_sticky_across_planner_records() -> None:
    tail = recovery.InterruptionTailState()
    tail.note_planner_record({"content": "Previous final"}, 0)
    tail.note_planner_record({"content": "Blocked", "promptFeedback": {"blockReason": "OTHER"}}, 1)
    assert tail.had_safety_error
    tail.note_planner_record({"content": "Later final"}, 2)
    assert tail.had_safety_error
    assert not tail.final_planner
    assert tail.final_planner_content == ""
    assert tail.has_open_planner_after_completion
