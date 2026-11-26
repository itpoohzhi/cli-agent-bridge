"""Regression tests for Codex argument and usage-frame cache handling."""

from __future__ import annotations

from typing import Any

from core.stdio_resident.codex_cli_args import (
    append_cli_args,
    build_codex_argv,
    build_zero_canon_argv,
    extract_cfg_arg,
    has_flag,
    is_denied_cfg_key,
    zero_canon_overrides,
)
from core.stdio_resident.codex_protocol_fsm import EffectKind, ProtocolEffect
from core.stdio_resident.codex_usage import codex_v2_effects_to_chunk, is_frame_usage_allowed
from core.turn_usage import UsageScope


def _updated(last: dict[str, Any] | None = None, total: dict[str, Any] | None = None, thread: str = "thr-1") -> dict[str, Any]:
    token_usage: dict[str, Any] = {}
    if last is not None:
        token_usage["last"] = last
    if total is not None:
        token_usage["total"] = total
    return {"method": "thread/tokenUsage/updated", "params": {"threadId": thread, "tokenUsage": token_usage}}


def _usage() -> dict[str, int]:
    return {"inputTokens": 11, "outputTokens": 7, "cachedInputTokens": 3, "totalTokens": 18}


def test_cli_config_pairs_are_kept_while_singleton_flags_are_deduped() -> None:
    argv = ["codex"]
    append_cli_args(argv, ["--verbose", "--verbose", "-c", "model=a", "-c", "model=b", "--config=foo=1"])
    assert argv == ["codex", "--verbose", "-c", "model=a", "-c", "model=b", "--config=foo=1"]
    assert extract_cfg_arg(argv, 2) == ("model=a", 2)
    assert has_flag(argv, "--verbose") and not has_flag(argv, "--missing")


def test_build_argv_and_zero_canon_contract() -> None:
    assert build_codex_argv(["codex"], {"cli_args": ["-c", "model=a", "-c", "model=b"], "--json": True}) == [
        "codex", "app-server", "-c", "model=a", "-c", "model=b", "--json"
    ]
    assert zero_canon_overrides("gpt-test", "high") == {
        "project_doc_max_bytes": "0", "model": '"gpt-test"', "model_reasoning_effort": '"high"'
    }
    result = build_zero_canon_argv(["codex", "app-server", "-c", "model=old", "-c", "foo=bar"], "gpt-test", "high")
    assert result == [
        "codex", "app-server", "-c", "foo=bar", "-c", "project_doc_max_bytes=0", "-c", 'model="gpt-test"',
        "-c", 'model_reasoning_effort="high"',
    ]


def test_zero_canon_denied_keys_are_fail_closed() -> None:
    for key in ("mcp_servers", "plugins.foo", "notify", "hooks.command"):
        assert is_denied_cfg_key(key)
        try:
            build_zero_canon_argv(["codex", "-c", f"{key}=x"])
        except ValueError as exc:
            assert str(exc) == f"forbidden_codex_zero_canon_config:{key}"
        else:
            raise AssertionError(key)


def test_flag_off_is_exactly_unchanged() -> None:
    frame = _updated(_usage())
    expected = codex_v2_effects_to_chunk((), frame)
    actual = codex_v2_effects_to_chunk((), frame, active_thread_id="wrong", active_turn_id="old", guard_enabled=False)
    assert actual == expected


def test_matching_updated_frame_is_allowed_without_effects() -> None:
    frame = _updated(_usage())
    assert is_frame_usage_allowed(frame, "thr-1", "turn-1")
    chunk = codex_v2_effects_to_chunk((), frame, active_thread_id="thr-1", active_turn_id="turn-1", guard_enabled=True)
    assert chunk is not None and chunk.usage is not None and chunk.usage.scope is UsageScope.TURN_SNAPSHOT


def test_missing_frame_identifier_is_not_by_itself_a_helper_rejection() -> None:
    frame = _updated(_usage())
    del frame["params"]["threadId"]
    assert is_frame_usage_allowed(frame, "thr-1", "turn-1")
    assert codex_v2_effects_to_chunk((), frame, active_thread_id="thr-1", active_turn_id="turn-1", guard_enabled=True) is None


def test_total_only_matching_updated_frame_remains_session_counter() -> None:
    frame = _updated(total={"inputTokens": 30, "outputTokens": 10})
    chunk = codex_v2_effects_to_chunk((), frame, active_thread_id="thr-1", guard_enabled=True)
    assert chunk is not None and chunk.usage is not None and chunk.usage.scope is UsageScope.SESSION_COUNTER


def test_ghost_and_wrong_thread_frames_are_rejected() -> None:
    frame = _updated(_usage(), thread="ghost")
    assert not is_frame_usage_allowed(frame, "thr-1", "turn-1")
    assert codex_v2_effects_to_chunk((), frame, active_thread_id="thr-1", guard_enabled=True) is None


def test_updated_frame_with_wrong_turn_is_rejected() -> None:
    frame = _updated(_usage())
    frame["params"]["turnId"] = "old-turn"
    assert not is_frame_usage_allowed(frame, "thr-1", "turn-1")
    assert codex_v2_effects_to_chunk(
        (), frame, active_thread_id="thr-1", active_turn_id="turn-1", guard_enabled=True
    ) is None


def test_late_old_turn_is_rejected_and_matching_completed_is_allowed() -> None:
    old = {"method": "turn/completed", "params": {"threadId": "thr-1", "turn": {"id": "old", "status": "completed", "usage": _usage()}}}
    valid = {"method": "turn/completed", "params": {"threadId": "thr-1", "turn": {"id": "turn-1", "status": "completed", "usage": _usage()}}}
    assert codex_v2_effects_to_chunk((), old, active_thread_id="thr-1", active_turn_id="turn-1", guard_enabled=True) is None
    effects = (ProtocolEffect(EffectKind.EMIT_TERMINAL, {"status": "completed"}),)
    chunk = codex_v2_effects_to_chunk(effects, valid, active_thread_id="thr-1", active_turn_id="turn-1", guard_enabled=True)
    assert chunk is not None and chunk.is_terminal and chunk.usage is not None
