"""L1/L2: самоисцеление пустого functionCall, редактирование секретов, usage после commit,
запрет безымянных tool_calls, безопасный разбор env штрафов."""

from __future__ import annotations

import importlib
import json
import re

import pytest

from core.log_redaction import mask_credential_context, mask_long_tokens, safe_log_tokens
from core.stream_framing import build_stream_error_chunk
from core.stream_interruption_recovery import (
    InterruptionTailState,
    is_recoverable_function_call_error,
    is_self_healable_error,
    is_transient_stream_interruption,
    resolve_done_turn_outcome,
)
from core.tool_emulation import (
    StreamNormalizer,
    pure_text_protocol_instruction,
    sanitize_tool_call,
    tools_protocol_section,
)
from core.cli_turn_flags import text_turn_cli_flags
from core.usage_wire import positive_wire_usage

MALFORMED = (
    "Your previous response contained an improperly formatted function call: Malformed function call: "
    "Failed to parse function call: Function call is empty - no input to parse.\n"
    "Please retry with a properly formatted function call\nRetries remaining: 3"
)


def _facts(**over: object) -> dict[str, object]:
    base: dict[str, object] = dict(
        rc=1,
        result_error=MALFORMED[:500],
        result_status="ERROR",
        final_text="final answer",
        emitted_text="final answer",
        completion_done_without_tools=True,
        last_completion_seq=370,
        last_error_seq=321,
        drain_complete=True,
        had_transient_error=True,
    )
    base.update(over)
    return base


def test_function_call_error_classification() -> None:
    assert is_recoverable_function_call_error(MALFORMED)
    assert is_self_healable_error(MALFORMED)
    assert not is_transient_stream_interruption(MALFORMED)
    assert not is_recoverable_function_call_error("permission denied")
    assert not is_recoverable_function_call_error(None)
    assert not is_recoverable_function_call_error(MALFORMED, source="other")


def test_self_healed_after_malformed_function_call_resolves_done() -> None:
    res = resolve_done_turn_outcome(**_facts())
    assert (res.state, res.rc, res.error) == ("done", 0, "")
    assert res.self_healed and res.final
    assert res.reason == "self_healed_after_malformed_function_call"


def test_result_error_without_transcript_error_record_still_heals() -> None:
    # OPEN-01: result ERROR есть, ERROR_MESSAGE в транскрипте нет (last_error_seq == -1).
    res = resolve_done_turn_outcome(**_facts(last_error_seq=-1, had_transient_error=False))
    assert res.state == "done" and res.self_healed


@pytest.mark.parametrize(
    "over",
    [
        {"last_completion_seq": 100},  # ошибка позже последнего ответа
        {"completion_done_without_tools": False},  # нет валидного финального planner
        {"final_text": "", "emitted_text": ""},  # пустое тело
        {"drain_complete": False},
        {"has_unclosed_tool_call": True},
        {"self_heal_enabled": False},
    ],
)
def test_unrecovered_function_call_error_fails_closed(over: dict[str, object]) -> None:
    res = resolve_done_turn_outcome(**_facts(**over))
    assert res.state == "agy_error" and res.rc != 0 and not res.self_healed
    assert MALFORMED[:40] in res.error


def test_unrelated_non_transient_error_is_not_healed() -> None:
    res = resolve_done_turn_outcome(**_facts(result_error="quota exceeded for project", had_transient_error=False))
    assert res.state == "agy_error" and res.reason == "non_transient_result_error"


def test_tail_state_marks_function_call_error_as_healable() -> None:
    tail = InterruptionTailState()
    tail.note_error_record("ERROR_MESSAGE", {"error": MALFORMED}, 218)
    assert tail.had_transient_error and tail.last_error_step_index == 218
    tail.note_planner_record({"content": "done", "status": "DONE"}, 370)
    assert tail.final_planner and tail.last_planner_step_index == 370


def test_unnamed_tool_calls_never_reach_clients() -> None:
    for call in (
        {"id": "c", "type": "function", "function": {"name": "", "arguments": "{}"}},
        {"id": "c", "type": "function", "function": {"name": "   ", "arguments": ""}},
        {"name": None, "arguments": {}},
    ):
        assert sanitize_tool_call(call) == []
    got: list[dict] = []
    norm = StreamNormalizer(lambda _t: None, lambda _t: None, got.append)
    norm._emit_call({"id": "x", "name": "  ", "arguments": {}})
    norm._emit_call({"id": "y", "name": "read", "arguments": {}})
    assert [c["name"] for c in got] == ["read"]


def test_empty_tool_call_json_block_is_not_emitted() -> None:
    from core.tool_emulation import LiveParserError

    got: list[dict] = []
    norm = StreamNormalizer(lambda _t: None, lambda _t: None, got.append)
    with pytest.raises(LiveParserError):  # strict-live: fail-closed, а не пустой tool_call
        norm.feed('<tool_call>{"name": "", "arguments": {}}</tool_call>')
    assert got == []


# ---- REQ-02 -------------------------------------------------------------------------


def test_reason_codes_survive_while_secrets_are_masked() -> None:
    line = (
        "turn-resolved reason=non_transient_result_error state=agy_error "
        "model_capacity_exhausted self_healed_after_malformed_function_call "
        "Authorization: Bearer abcd1234 api_key=short sk-abcdef12 "
        "token_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3"
    )
    out = mask_credential_context(line)
    out = mask_long_tokens(out, safe_tokens=safe_log_tokens())
    for code in ("non_transient_result_error", "model_capacity_exhausted", "self_healed_after_malformed_function_call"):
        assert code in out
    for secret in ("abcd1234", "short", "sk-abcdef12", "A1b2C3d4E5f6G7h8I9j0K1l2M3"):
        assert secret not in out


def test_extra_safe_tokens_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    custom = "my_custom_diagnostic_reason_code"
    assert mask_long_tokens(custom, safe_tokens=safe_log_tokens()) == "***"
    monkeypatch.setenv("BRIDGE_LOG_SAFE_TOKENS", f"a, {custom}")
    assert mask_long_tokens(custom, safe_tokens=safe_log_tokens()) == custom


# ---- REQ-08 -------------------------------------------------------------------------


def test_positive_wire_usage_only() -> None:
    assert positive_wire_usage({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}) is None
    assert positive_wire_usage(None) is None
    kept = positive_wire_usage({"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7})
    assert kept == {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}


def test_error_chunk_preserves_accumulated_usage_but_not_zero() -> None:
    usage = {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}
    chunk = build_stream_error_chunk("boom", usage=usage)
    assert chunk["usage"] == usage and chunk["error"]["message"] == "boom"
    assert "usage" not in build_stream_error_chunk("boom")
    zero = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    assert "usage" not in build_stream_error_chunk("boom", usage=zero)


def test_model_penalty_import_survives_malformed_env(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    import core.model_penalty as mp

    for name, value in (
        ("BRIDGE_MAX_START_FAILS", "abc"),
        ("BRIDGE_INITIAL_COOLDOWN_SECONDS", ""),
        ("BRIDGE_STEP2_COOLDOWN_SECONDS", "nan"),
        ("BRIDGE_STEP3_COOLDOWN_SECONDS", "-5"),
        ("BRIDGE_MAX_COOLDOWN_SECONDS", "inf"),
    ):
        monkeypatch.setenv(name, value)
    try:
        with caplog.at_level("WARNING"):
            reloaded = importlib.reload(mp)
        assert reloaded.DEFAULT_MAX_START_FAILS == 3
        assert reloaded.DEFAULT_INITIAL_COOLDOWN_SECONDS == 10.0
        assert reloaded.DEFAULT_STEP2_COOLDOWN_SECONDS == 30.0
        assert reloaded.DEFAULT_STEP3_COOLDOWN_SECONDS == 120.0
        assert reloaded.DEFAULT_MAX_COOLDOWN_SECONDS == 300.0
        assert "Invalid BRIDGE_MAX_START_FAILS" in caplog.text
    finally:
        monkeypatch.undo()
        importlib.reload(mp)


def test_model_penalty_cooldown_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.model_penalty as mp

    monkeypatch.delenv("BRIDGE_INITIAL_COOLDOWN_SECONDS", raising=False)
    monkeypatch.setenv("BRIDGE_COOLDOWN_SECONDS", "42")
    try:
        assert importlib.reload(mp).DEFAULT_INITIAL_COOLDOWN_SECONDS == 42.0
        monkeypatch.setenv("BRIDGE_INITIAL_COOLDOWN_SECONDS", "7")
        assert importlib.reload(mp).DEFAULT_INITIAL_COOLDOWN_SECONDS == 7.0
    finally:
        monkeypatch.undo()
        importlib.reload(mp)


# ---- REQ-03 / REQ-05 ----------------------------------------------------------------

_TOOLS = [{"type": "function", "function": {"name": "read_image", "description": "d", "parameters": {"type": "object"}}}]


def test_slash_command_isolation_flags_for_text_modes() -> None:
    assert text_turn_cli_flags("ask", {}) == ["--disable-slash-commands"]
    assert text_turn_cli_flags("plan", {}) == ["--disable-slash-commands"]
    assert text_turn_cli_flags("agent", {}) == []
    assert text_turn_cli_flags("ask", {"AGY_BRIDGE_DISABLE_SLASH_COMMANDS": "0"}) == []


def test_tools_protocol_with_attachments_is_not_contradictory() -> None:
    plain = tools_protocol_section(_TOOLS, "auto")
    attached = tools_protocol_section(_TOOLS, "auto", has_attachments=True, attachment_tool="view_file")
    assert "here, except" not in plain and "except" not in plain.split("Available tools:")[0]
    head = attached.split("Available tools:")[0]
    assert re.search(r"listed here, except view_file on the attachment files listed under \[attachments\]\.", head)
    assert "here.," not in attached


def test_pure_text_protocol_attachment_exception() -> None:
    assert "except" not in pure_text_protocol_instruction()
    text = pure_text_protocol_instruction(has_attachments=True, attachment_tool="view_file")
    assert "DO NOT USE ANY TOOLS" in text and "except view_file" in text
    json.dumps(text)


# ---- L2: passthrough SSE --------------------------------------------------------------


def test_passthrough_unnamed_tool_call_is_dropped_and_finish_downgraded() -> None:
    from tests.passthrough_stream_testlib import finish, payloads, published_calls, run_stream, tool_delta, DONE

    events = tool_delta(0, 0, call_id="call_1", name="", args="") + finish(0) + DONE
    _outcome, out = run_stream(events)
    assert published_calls(out) == []
    reasons = [c.get("finish_reason") for p in payloads(out) for c in p.get("choices") or [] if c.get("finish_reason")]
    assert reasons == ["stop"]


def test_passthrough_named_tool_call_still_published() -> None:
    from tests.passthrough_stream_testlib import finish, published_calls, run_stream, tool_delta, DONE

    events = tool_delta(0, 0, call_id="call_1", name="subagent", args='{"prompt": "p"}') + finish(0) + DONE
    _outcome, out = run_stream(events)
    assert [c["function"]["name"] for c in published_calls(out)] == ["subagent"]


def test_passthrough_incomplete_stream_keeps_last_positive_usage() -> None:
    from tests.passthrough_stream_testlib import chunk, content, frame, payloads, run_stream

    usage = {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}
    events = content("partial") + frame(chunk([], usage=usage))  # обрыв без finish_reason и [DONE]
    outcome, out = run_stream(events)
    assert outcome.incomplete and outcome.last_usage == usage
    error_frames = [p for p in payloads(out) if "error" in p]
    assert error_frames and error_frames[-1]["usage"] == usage


def test_passthrough_error_frame_without_usage_has_no_usage_key() -> None:
    from tests.passthrough_stream_testlib import content, payloads, run_stream

    outcome, out = run_stream(content("partial"))
    assert outcome.last_usage is None
    assert all("usage" not in p for p in payloads(out))
