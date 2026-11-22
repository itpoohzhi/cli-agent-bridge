"""L1: контракты PostCallFSM, PostCallPolicy, редактирования логов и парсинга блоков."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from core.log_redaction import redact_log_text


def _policy_mod() -> Any:
    return pytest.importorskip("core.tool_post_call_policy")


def _parsing_mod() -> Any:
    return pytest.importorskip("core.tool_block_parsing")


def test_post_call_policy_defaults_and_custom_cutoff_window() -> None:
    mod = _policy_mod()
    default_policy = mod.PostCallPolicy()
    assert default_policy.cutoff_enabled is False
    assert default_policy.diagnostic_window_chars == 120
    assert default_policy.diagnostic_redact_margin_chars == 2048

    custom = mod.PostCallPolicy(
        cutoff_enabled=True,
        diagnostic_window_chars=64,
        diagnostic_redact_margin_chars=512,
    )
    assert custom.cutoff_enabled is True
    assert custom.diagnostic_window_chars == 64
    assert custom.diagnostic_redact_margin_chars == 512


def test_post_call_fsm_states_events_and_24_pair_table() -> None:
    mod = _policy_mod()
    states = tuple(mod.PostCallState)
    events = tuple(mod.PostCallEvent)
    assert [s.name for s in states] == ["ACTIVE", "POST_CALL_SUPPRESSED", "FAILED"]
    assert [e.name for e in events] == [
        "TEXT_CHUNK",
        "TOOL_OPEN",
        "TOOL_CALL_EMITTED",
        "ORPHAN_TOOL_CLOSE",
        "ORPHAN_REASONING_CLOSE",
        "ORPHAN_OTHER_SERVICE_TAG",
        "UNCLOSED_AT_EOF",
        "EOF",
    ]
    assert len(mod.POST_CALL_TRANSITIONS) == 24
    for state in states:
        for event in events:
            assert (state, event) in mod.POST_CALL_TRANSITIONS


def test_post_call_fsm_orphan_tool_close_suppress_and_continue_guards() -> None:
    mod = _policy_mod()
    S, E, Ctx = mod.PostCallState, mod.PostCallEvent, mod.PostCallContext

    # 1) cutoff_enabled & (strict_live or reject_tools) & not has_open_block & calls >= 1
    d1 = mod.PostCallFSM.decide(
        S.ACTIVE,
        E.ORPHAN_TOOL_CLOSE,
        Ctx(cutoff_enabled=True, strict_live=True, reject_tools=False, has_open_block=False, calls_count=7),
    )
    assert d1.next_state is S.POST_CALL_SUPPRESSED
    assert d1.log_cutoff_once is True
    assert d1.clear_tail_buf is True
    assert d1.drop_silently is True
    assert d1.raise_parse_error is False

    # 2) non-strict and non-reject -> ACTIVE (CONTINUE)
    for cutoff in (False, True):
        for calls in (0, 3):
            d2 = mod.PostCallFSM.decide(
                S.ACTIVE,
                E.ORPHAN_TOOL_CLOSE,
                Ctx(cutoff_enabled=cutoff, strict_live=False, reject_tools=False, has_open_block=False, calls_count=calls),
            )
            assert d2.next_state is S.ACTIVE
            assert d2.drop_silently is False
            assert d2.raise_parse_error is False


def test_post_call_fsm_orphan_tool_close_fails_when_guard_unmet() -> None:
    mod = _policy_mod()
    S, E, Ctx = mod.PostCallState, mod.PostCallEvent, mod.PostCallContext

    # 3) (strict_live or reject_tools) and (~cutoff or has_open_block or calls == 0) -> FAILED
    fail_cases = [
        Ctx(cutoff_enabled=False, strict_live=True, reject_tools=False, has_open_block=False, calls_count=7),
        Ctx(cutoff_enabled=True, strict_live=True, reject_tools=False, has_open_block=True, calls_count=7),
        Ctx(cutoff_enabled=True, strict_live=True, reject_tools=False, has_open_block=False, calls_count=0),
        Ctx(cutoff_enabled=True, strict_live=False, reject_tools=True, has_open_block=False, calls_count=0),
    ]
    for ctx in fail_cases:
        d3 = mod.PostCallFSM.decide(S.ACTIVE, E.ORPHAN_TOOL_CLOSE, ctx)
        assert d3.next_state is S.FAILED
        assert d3.raise_parse_error is True


def test_post_call_fsm_other_active_events() -> None:
    mod = _policy_mod()
    S, E, Ctx = mod.PostCallState, mod.PostCallEvent, mod.PostCallContext

    strict_ctx = Ctx(True, True, False, False, 1)
    loose_ctx = Ctx(True, False, False, False, 1)
    reject_ctx = Ctx(True, False, True, False, 1)

    for ev in (E.TEXT_CHUNK, E.TOOL_OPEN, E.TOOL_CALL_EMITTED, E.EOF):
        dec = mod.PostCallFSM.decide(S.ACTIVE, ev, strict_ctx)
        assert dec.next_state is S.ACTIVE
        assert dec.raise_parse_error is False

    assert mod.PostCallFSM.decide(S.ACTIVE, E.ORPHAN_REASONING_CLOSE, strict_ctx).next_state is S.FAILED
    assert mod.PostCallFSM.decide(S.ACTIVE, E.ORPHAN_REASONING_CLOSE, loose_ctx).next_state is S.ACTIVE

    assert mod.PostCallFSM.decide(S.ACTIVE, E.ORPHAN_OTHER_SERVICE_TAG, strict_ctx).next_state is S.FAILED
    assert mod.PostCallFSM.decide(S.ACTIVE, E.ORPHAN_OTHER_SERVICE_TAG, reject_ctx).next_state is S.FAILED
    assert mod.PostCallFSM.decide(S.ACTIVE, E.ORPHAN_OTHER_SERVICE_TAG, loose_ctx).next_state is S.ACTIVE

    unclosed = mod.PostCallFSM.decide(S.ACTIVE, E.UNCLOSED_AT_EOF, strict_ctx)
    assert unclosed.next_state is S.FAILED
    assert unclosed.raise_parse_error is True


def test_post_call_fsm_suppressed_and_failed_states() -> None:
    mod = _policy_mod()
    S, E, Ctx = mod.PostCallState, mod.PostCallEvent, mod.PostCallContext
    ctx = Ctx(True, True, False, False, 7)

    for ev in E:
        dec = mod.PostCallFSM.decide(S.POST_CALL_SUPPRESSED, ev, ctx)
        assert dec.raise_parse_error is False
        if ev is E.EOF:
            assert dec.clean_complete is True
        else:
            assert dec.next_state is S.POST_CALL_SUPPRESSED
            assert dec.drop_silently is True
            assert dec.log_cutoff_once is False

    for ev in E:
        dec = mod.PostCallFSM.decide(S.FAILED, ev, ctx)
        assert dec.next_state is S.FAILED
        assert dec.raise_parse_error is True


def test_diagnostic_window_redacts_secrets_without_sentinel_mutation() -> None:
    mod = _parsing_mod()
    secret_a = "sk-proj-secret_token_alpha_99999999"
    secret_b = "Bearer tok_very_secret_bearer_123456"
    pad_left = "x" * (5 * 1024 * 1024)
    raw = (
        f'{pad_left}{{"name":"bash","api_key":"{secret_a}",'
        f'"auth":"{secret_b}","broken":\'bad}}'
    )
    err_pos = raw.index(":'bad")
    seen_inputs: list[str] = []

    def spy_redact(chunk: str) -> str:
        seen_inputs.append(chunk)
        return redact_log_text(chunk)

    formatted = mod.format_malformed_tool_block_log(
        raw,
        err_pos=err_pos,
        window_chars=120,
        redact_margin_chars=2048,
        redact_fn=spy_redact,
    )
    assert formatted.startswith("malformed tool_call block raw=")
    assert secret_a not in formatted
    assert secret_b not in formatted
    assert ":'bad" in formatted
    assert seen_inputs
    for chunk in seen_inputs:
        assert chunk in raw
        assert len(chunk) <= 2 * (120 + 2048)


def test_repair_invalid_single_quote_escape_and_loads_tolerant_json() -> None:
    mod = _parsing_mod()

    src_invalid = r'''{"name":"bash","arguments":{"command":"echo \'ok\'"}}'''
    repaired = mod.repair_invalid_single_quote_escape(src_invalid)
    assert repaired == r'''{"name":"bash","arguments":{"command":"echo 'ok'"}}'''
    assert json.loads(repaired)["arguments"]["command"] == "echo 'ok'"

    src_preserved = r'''{"name":"bash","arguments":{"command":"echo \\'kept\\'"}}'''
    preserved = mod.repair_invalid_single_quote_escape(src_preserved)
    assert preserved == src_preserved
    assert json.loads(preserved)["arguments"]["command"] == r"echo \'kept\'"

    src_triple = r'''{"name":"bash","arguments":{"command":"echo \\\'triple\\\'"}}'''
    triple = mod.repair_invalid_single_quote_escape(src_triple)
    assert json.loads(triple)["arguments"]["command"] == r"echo \'triple\'"

    outside_valid = r'''{"name":"bash","arguments":{"command":"a\nb\tc\"d\'e"}}'''
    parsed = mod.loads_tolerant_json(outside_valid)
    assert parsed["arguments"]["command"] == "a\nb\tc\"d'e"


def test_tool_close_cursor_incremental_and_linear_time() -> None:
    mod = _parsing_mod()
    cursor = mod.ToolCloseCursor()

    payload = '{"command":"echo \\"hi\\" </tool_call> ok"}</tool_call>tail'
    pos = -1
    buf = ""
    for ch in payload:
        buf += ch
        pos = cursor.find_close(buf, start=0)
        if pos != -1:
            break
    assert pos == payload.rindex("</tool_call>")

    big_inner = '{"command":"' + ("a" * (2 * 1024 * 1024)) + '"}</tool_call>'
    big_cursor = mod.ToolCloseCursor()
    t0 = time.perf_counter()
    step = 4096
    found = -1
    for end in range(step, len(big_inner) + step, step):
        found = big_cursor.find_close(big_inner[:end], start=0)
        if found != -1:
            break
    elapsed = time.perf_counter() - t0
    assert found == len(big_inner) - len("</tool_call>")
    assert elapsed < 2.0
