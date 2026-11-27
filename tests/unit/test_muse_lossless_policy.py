"""L1/L2 unit and contract tests for muse-bridge decoupled lossless kill-switch and opt-in 413."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MUSE_DIR = REPO_ROOT / "bridges" / "muse-bridge"
if str(MUSE_DIR) not in sys.path:
    sys.path.insert(0, str(MUSE_DIR))

from muse_runtime.context_pruner import _prune_messages  # noqa: E402
from muse_runtime.lossless_policy import (  # noqa: E402
    allow_reactive_prune_retry,
    evaluate_muse_prompt_policy,
    read_muse_policy_flags,
)
from muse_runtime.prompt_builder import _assemble_prompt  # noqa: E402
from muse_runtime.token_budget import _estimate_tokens  # noqa: E402


def _make_long_conversation(n_turns: int = 40) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = [{"role": "system", "content": "SYS_PROMPT"}]
    for i in range(n_turns):
        msgs.append({"role": "user", "content": f"MK_{i:02d} " + ("x" * 600)})
        msgs.append({"role": "assistant", "content": f"reply_{i:02d} " + ("y" * 600)})
    msgs.append({"role": "user", "content": "FINAL_USER_TURN"})
    return msgs


def test_context_pruner_loc_untouched_at_277() -> None:
    loc = len((MUSE_DIR / "muse_runtime" / "context_pruner.py").read_text(encoding="utf-8").splitlines())
    assert loc == 277


def test_default_flags_preserve_legacy_502_and_reactive_retry() -> None:
    lossless, mode, _ = read_muse_policy_flags({})
    assert lossless is False
    assert mode.value == "legacy_502"
    assert allow_reactive_prune_retry({}) is True

    msgs = _make_long_conversation(40)
    # Legacy proactive prune happens when limit is exceeded
    dec = evaluate_muse_prompt_policy(
        msgs,
        limit=2000,
        target=1600,
        tools=None,
        tool_choice=None,
        raw_tools=None,
        prune_fn=_prune_messages,
        assemble_fn=_assemble_prompt,
        estimate_fn=_estimate_tokens,
        redact_fn=lambda s: s,
        env={},
    )
    assert dec.ok is True
    assert dec.log_reason == "proactive_prune"
    assert dec.prune_result.msgs_dropped > 0

    # Mandatory refusal returns legacy HTTP 502 by default (REQ-MUSE-001 backward compat)
    huge_mandatory = [{"role": "system", "content": "A" * 15_000}, {"role": "user", "content": "hi"}]
    refused = evaluate_muse_prompt_policy(
        huge_mandatory,
        limit=100,
        target=80,
        tools=None,
        tool_choice=None,
        raw_tools=None,
        prune_fn=_prune_messages,
        assemble_fn=_assemble_prompt,
        estimate_fn=_estimate_tokens,
        redact_fn=lambda s: s,
        env={},
    )
    assert refused.ok is False
    assert refused.http_status == 502
    assert refused.error_body is not None
    assert refused.error_body["error"]["type"] == "proxy_error"  # type: ignore[index]


def test_lossless_kill_switch_disables_proactive_prune_and_reactive_retry() -> None:
    env = {"MUSE_BRIDGE_LOSSLESS_ENABLED": "true"}
    assert allow_reactive_prune_retry(env) is False
    msgs = _make_long_conversation(10)

    # Fits within limit -> full prompt delivered with 0 dropped messages
    ok_dec = evaluate_muse_prompt_policy(
        msgs,
        limit=50_000,
        target=40_000,
        tools=None,
        tool_choice=None,
        raw_tools=None,
        prune_fn=_prune_messages,
        assemble_fn=_assemble_prompt,
        estimate_fn=_estimate_tokens,
        redact_fn=lambda s: s,
        env=env,
    )
    assert ok_dec.ok is True
    assert ok_dec.log_reason == ""
    assert ok_dec.prune_result.msgs_dropped == 0
    for i in range(10):
        assert f"MK_{i:02d}" in ok_dec.prompt

    # Exceeds limit -> fail-closed refused (0 silent pruning!); status stays legacy_502 unless opted into 413
    ref_502 = evaluate_muse_prompt_policy(
        msgs,
        limit=500,
        target=400,
        tools=None,
        tool_choice=None,
        raw_tools=None,
        prune_fn=_prune_messages,
        assemble_fn=_assemble_prompt,
        estimate_fn=_estimate_tokens,
        redact_fn=lambda s: s,
        env=env,
    )
    assert ref_502.ok is False
    assert ref_502.http_status == 502
    assert ref_502.log_reason == "refused_lossless"


def test_decoupled_opt_in_413_returns_prompt_too_large_and_redacted_receipt() -> None:
    env = {
        "MUSE_BRIDGE_LOSSLESS_ENABLED": "true",
        "MUSE_BRIDGE_REFUSE_STATUS_MODE": "413",
    }
    msgs = [{"role": "user", "content": "SECRET_MUSE_TOKEN_777 " + ("Z" * 9_000)}]
    ref_413 = evaluate_muse_prompt_policy(
        msgs,
        limit=500,
        target=400,
        tools=None,
        tool_choice=None,
        raw_tools=None,
        prune_fn=_prune_messages,
        assemble_fn=_assemble_prompt,
        estimate_fn=_estimate_tokens,
        redact_fn=lambda s: s,
        env=env,
    )
    assert ref_413.ok is False
    assert ref_413.http_status == 413
    assert ref_413.error_body is not None
    serialized = json.dumps(ref_413.error_body)
    assert "SECRET_MUSE_TOKEN_777" not in serialized
    assert ref_413.error_body["error"]["code"] == "prompt_too_large"  # type: ignore[index]
    assert "x_bridge_loss" in ref_413.error_body["error"]  # type: ignore[operator]
