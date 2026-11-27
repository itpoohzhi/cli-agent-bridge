"""W1: fast post-EOF drain, keyed single-turn policy и подписанная директива сессии."""

from __future__ import annotations

import importlib
import re
import sys
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = ROOT / "bridges" / "agy-bridge"
for _p in (ROOT, BRIDGE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.hot_session_policy import (  # noqa: E402
    DecisionAction as A, DecisionReason as R, HistoryFingerprints, PolicyConfig,
    SlotSnapshot, SlotState, TurnPolicyInput, decide_turn,
)
from core.session_plane.directive_codec import DIRECTIVE_HEADER, encode_directive  # noqa: E402
from core.session_plane.lifecycle_policy import SessionExecutionPlan  # noqa: E402

_DP = importlib.import_module("agy_runtime.drain_policy")
_SRA = importlib.import_module("agy_runtime.session_resume_adapter")
_SECRET = b"k" * 32
_CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
_CID = "11111111-1111-4111-8111-111111111111"


# ---------------------------------------------------------------- drain_policy
def _snap(**kw: Any) -> Any:
    base: dict[str, Any] = dict(eof_seen=True, tools_used=0, final_planner_seen=True, pending_steps=0,
                                elapsed_after_eof_ms=0.0, last_byte_age_ms=0.0, fast_drain_enabled=True)
    return _DP.DrainSnapshot(**{**base, **kw})


def test_decide_drain_predicate() -> None:
    d = _DP.decide_drain
    assert d(_snap(last_byte_age_ms=15.0)) == _DP.DrainDecision(True, 25.0, "final_planner_fast_exit")
    assert d(_snap(elapsed_after_eof_ms=25.0)).should_exit is True
    w = d(_snap(last_byte_age_ms=14.9, elapsed_after_eof_ms=24.9))
    assert (w.should_exit, w.max_wait_ms, w.reason) == (False, 25.0, "waiting_silence_floor")
    for off in ({"tools_used": 1}, {"pending_steps": 1}, {"fast_drain_enabled": False},
                {"final_planner_seen": False}, {"eof_seen": False}):
        legacy = d(_snap(last_byte_age_ms=500.0, elapsed_after_eof_ms=500.0, **off))
        assert (legacy.should_exit, legacy.max_wait_ms) == (False, 400.0)


class _Tail:
    def __init__(self, *, final_planner: bool = True, tool_steps: tuple[int, ...] = (), pending: int = 0,
                 tools_count: int = 0, end_marker: bool = False) -> None:
        self.stop_event, self.sqlite_active = threading.Event(), False
        self.drain_deadline, self.emitted, self.end_marker = 0.0, 0, end_marker
        self.final_planner, self._plain_final = False, final_planner
        self._tool_step_indices, self.seen = set(tool_steps), {i: object() for i in tool_steps}
        self.tools_count, self.run_ref, self.drain_outcome = tools_count, None, ""
        self._pending, self._last_byte_at = pending, time.monotonic() - 1.0

    def _read_transcript(self) -> None: ...
    def _pending_steps(self) -> int: return self._pending
    def _cid8(self) -> str: return "cid12345"


def _drain(tail: _Tail, *, fast: bool) -> tuple[str, float, list[str], int]:
    logs: list[str] = []
    pend: list[int] = []
    t0 = time.monotonic()
    _DP.run_post_eof_drain(tail, drain_window_s=0.2, drain_max_s=0.5, drain_min_s=0.15, poll_step_s=0.05,
                           fast_drain_enabled=fast, on_deadline_pending=lambda: pend.append(1), log_fn=logs.append)
    ms = (time.monotonic() - t0) * 1000.0
    return re.search(r"exit=(\S+)", logs[0]).group(1), ms, logs, len(pend)  # type: ignore[union-attr]


def test_fast_exit_when_tools0_final_planner_pending0_flag_on() -> None:
    kind, ms, _, _ = _drain(_Tail(), fast=True)
    assert kind == "final_planner_fast_exit" and ms <= 50.0


@pytest.mark.parametrize("tail,fast", [
    (_Tail(tool_steps=(3,)), True), (_Tail(tools_count=2), True), (_Tail(pending=1), True),
    (_Tail(), False), (_Tail(final_planner=False), True),
])
def test_legacy_full_window_otherwise(tail: _Tail, fast: bool) -> None:
    kind, ms, _, pend = _drain(tail, fast=fast)
    assert kind == "window" and ms >= 190.0
    assert pend == (1 if tail._pending else 0)


def test_end_marker_and_stop_exits_keep_legacy_semantics() -> None:
    kind, ms, _, _ = _drain(_Tail(final_planner=False, end_marker=True), fast=False)
    assert kind == "end_turn" and 140.0 <= ms < 190.0
    t = _Tail(final_planner=False)
    t.stop_event.set()
    assert _drain(t, fast=False)[0] == "stop"


def test_server_drain_is_thin_delegate_gated_by_flag() -> None:
    src = (BRIDGE_DIR / "server.py").read_text(encoding="utf-8")
    body = src.split("    def _drain_post_eof(self)", 1)[1].split("class JobConflict", 1)[0]
    assert "run_post_eof_drain(" in body and "BRIDGE_AGY_DRAIN_EARLY_EXIT_ENABLED" in body
    assert body.count("\n") <= 14


# ------------------------------------------------------------ hot_session_policy
def _hist(asst: int) -> HistoryFingerprints:
    return HistoryFingerprints(1, asst, "pd", "fd", 10, True, None)


def _ready_slot() -> SlotSnapshot:
    return SlotSnapshot(SlotState.READY, "cid-1", "sd", 2, 1, 7, 1, 100.0, 100.0, 1, 0.0, 0.0)


def _decide(cfg: PolicyConfig, supersedes: int = 0, profile: str = "zero-canon") -> Any:
    req = TurnPolicyInput(True, "oh", "chat", "", _hist(0), 200.0, 1, supersedes, profile)
    return decide_turn(_ready_slot(), req, cfg)


def test_keyed_single_turn_flag_off_is_legacy_reject() -> None:
    cfg = PolicyConfig(enabled=True)
    assert cfg.allow_keyed_single_turn is False
    d = _decide(cfg)
    assert (d.action, d.reason, d.allow_commit) == (A.COLD_REJECT, R.NO_ASSISTANT_HISTORY, False)


def test_keyed_single_turn_flag_on_supersedes() -> None:
    cfg = PolicyConfig(enabled=True, allow_keyed_single_turn=True, keyed_single_turn_profile="zero-canon")
    d = _decide(cfg)
    assert (d.action, d.reason, d.allow_commit, d.supersede) == (A.COLD_SEED, R.HISTORY_DIVERGED_SUPERSEDE, True, True)
    assert (d.expected_gen, d.expected_stored_digest) == (7, "sd")
    limited = _decide(cfg, supersedes=cfg.supersede_max_per_min)
    assert (limited.action, limited.reason) == (A.COLD_REJECT, R.HISTORY_DIVERGED_RATE_LIMITED)


@pytest.mark.parametrize("profile,action,reason", [
    ("zero-canon", A.COLD_SEED, R.HISTORY_DIVERGED_SUPERSEDE),
    ("standard", A.COLD_REJECT, R.NO_ASSISTANT_HISTORY),
])
def test_keyed_single_turn_is_zero_canon_only(profile: str, action: Any, reason: Any) -> None:
    d = _decide(PolicyConfig(enabled=True, allow_keyed_single_turn=True, keyed_single_turn_profile="zero-canon"), profile=profile)
    assert (d.action, d.reason) == (action, reason)


def test_keyed_single_turn_without_profile_is_default_deny() -> None:
    d = _decide(PolicyConfig(enabled=True, allow_keyed_single_turn=True), profile="zero-canon")
    assert (d.action, d.reason) == (A.COLD_REJECT, R.NO_ASSISTANT_HISTORY)


def test_turn_policy_input_review_profile_defaults_to_standard() -> None:
    assert TurnPolicyInput(True, "oh", "chat", "", _hist(0), 200.0, 1).review_profile == "standard"


# --------------------------------------------------------- session_resume_adapter
@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Callable[..., Path]]:
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    for k in ("BRIDGE_ZERO_CANON_KEYED_RESIDENT_ENABLED", "BRIDGE_AGY_SIGNED_DIRECTIVE_ENABLED", "BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(_SRA, "load_or_create_directive_key", lambda: _SECRET)
    _SRA.reset_explicit_adapters_for_tests()

    def _set(**flags: str) -> Path:
        for k, v in flags.items():
            monkeypatch.setenv(k, v)
        return cfg

    yield _set
    _SRA.reset_explicit_adapters_for_tests()


def _plan(process: str, context: str = "CONTEXT_CONTINUE", chat: str | None = "chat-1", profile: str = "standard") -> SessionExecutionPlan:
    return SessionExecutionPlan("v1", "pk", chat, "ns", "aff", profile, cast(Any, process), cast(Any, context),
                                1, False, False, 30, 600, 512, 1, "t")


def _prep(adapter: Any, messages: list[dict[str, str]], directive: str | None = None, now: float = 2000.0,
          chat: str = "chat-1", profile: str = "standard") -> Any:
    hdrs = {"X-DSH-Chat-Id": chat, "Authorization": "Bearer tok-owner-AAAA-1111"}
    if directive is not None:
        hdrs[DIRECTIVE_HEADER] = directive
    req = {"model": "m", "messages": messages}
    return adapter.prepare_turn(_SRA.TurnHttpMeta(hdrs, "127.0.0.1", profile, None),
                                _SRA.TurnPayloadMeta(req, {}, "m", "high", "/tmp/work", False, [], None, False), now)


def test_flags_default_off_and_read(env: Callable[..., Path]) -> None:
    f0 = _SRA.read_runtime_flags(env())
    assert (f0.keyed_single_turn_enabled, f0.signed_directive_enabled, f0.policy.allow_keyed_single_turn) == (False,) * 3
    f1 = _SRA.read_runtime_flags(env(BRIDGE_ZERO_CANON_KEYED_RESIDENT_ENABLED="1", BRIDGE_AGY_SIGNED_DIRECTIVE_ENABLED="1"))
    assert (f1.keyed_single_turn_enabled, f1.signed_directive_enabled, f1.policy.allow_keyed_single_turn) == (True,) * 3


@pytest.mark.parametrize("keyed,profile,reason,commit", [
    (False, "standard", "no_assistant_history", False),
    (False, "zero-canon", "no_assistant_history", False),
    (True, "standard", "no_assistant_history", False),
    (True, "zero-canon", "history_diverged_supersede", True),
])
def test_adapter_keyed_single_turn(env: Callable[..., Path], tmp_path: Path, keyed: bool, profile: str, reason: str, commit: bool) -> None:
    cfg = env(BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED="1", BRIDGE_HOT_ZC_PLAIN_ENABLED="1", **({"BRIDGE_ZERO_CANON_KEYED_RESIDENT_ENABLED": "1"} if keyed else {}))
    ad = _SRA.ExplicitResumeAdapter(tmp_path / "st", cfg)
    try:
        msgs = [{"role": "user", "content": "q"}]
        st1 = _prep(ad, msgs, profile=profile)
        assert st1.decision_reason == "slot_empty" and ad.finalize_turn(st1, {"conversation_id": _CID, "text": "a"}, "commit", _CID_RE)
        assert ad._store.flush_now(timeout_s=2.0) is True
        st2 = _prep(ad, msgs, profile=profile)
        assert (st2.decision_reason, st2.allow_commit, st2.is_resumed) == (reason, commit, False)
        assert st2.supersede is commit
    finally:
        ad.close()


def test_directive_valid_ephemeral_and_warm(env: Callable[..., Path], tmp_path: Path) -> None:
    cfg = env(BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED="1", BRIDGE_AGY_SIGNED_DIRECTIVE_ENABLED="1")
    ad = _SRA.ExplicitResumeAdapter(tmp_path / "st", cfg)
    try:
        msgs = [{"role": "user", "content": "q"}]
        eph = _prep(ad, msgs, encode_directive(_plan("EPHEMERAL_KILL_AFTER_TURN"), _SECRET, now_s=2000.0))
        assert (eph.handled, eph.force_cold, eph.allow_commit, eph.decision_reason) == (True, True, False, "directive_ephemeral")
        warm = _prep(ad, msgs, encode_directive(_plan("WARM_SLOT_REUSE"), _SECRET, now_s=2000.0))
        assert (warm.force_cold, warm.decision_reason) == (False, "slot_empty")
    finally:
        ad.close()


def test_directive_bad_or_expired_hmac_fails_closed(env: Callable[..., Path], tmp_path: Path) -> None:
    cfg = env(BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED="1", BRIDGE_AGY_SIGNED_DIRECTIVE_ENABLED="1")
    ad = _SRA.ExplicitResumeAdapter(tmp_path / "st", cfg)
    try:
        msgs = [{"role": "user", "content": "q"}]
        good = encode_directive(_plan("WARM_SLOT_REUSE"), _SECRET, now_s=2000.0)
        forged = encode_directive(_plan("WARM_SLOT_REUSE"), b"x" * 32, now_s=2000.0)
        expired = encode_directive(_plan("WARM_SLOT_REUSE"), _SECRET, now_s=1000.0)
        for hdr in (forged, expired, good[:-4] + "0000", "garbage", good.replace("v1.", "v9.", 1)):
            st = _prep(ad, msgs, hdr)
            assert (st.handled, st.force_cold, st.allow_commit) == (True, True, False)
            assert st.decision_reason.startswith("directive_hmac_reject:")
    finally:
        ad.close()


def _directive_state(env: Callable[..., Path], tmp_path: Path, directive: str | None, **prep_kw: Any) -> Any:
    cfg = env(BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED="1", BRIDGE_HOT_ZC_PLAIN_ENABLED="1", BRIDGE_AGY_SIGNED_DIRECTIVE_ENABLED="1")
    ad = _SRA.ExplicitResumeAdapter(tmp_path / "st", cfg)
    try:
        return _prep(ad, [{"role": "user", "content": "q"}], directive, **prep_kw)
    finally:
        ad.close()


def _enc(plan: SessionExecutionPlan) -> str:
    return encode_directive(plan, _SECRET, now_s=2000.0)


def _assert_fail_closed(st: Any, reason: str) -> None:
    assert (st.handled, st.force_cold, st.allow_commit, st.decision_reason) == (True, True, False, reason)


def test_directive_missing_header_fails_closed(env: Callable[..., Path], tmp_path: Path) -> None:
    _assert_fail_closed(_directive_state(env, tmp_path, None), "directive_missing")
    _assert_fail_closed(_directive_state(env, tmp_path, "  "), "directive_missing")


def test_directive_replay_other_chat_is_rejected(env: Callable[..., Path], tmp_path: Path) -> None:
    chat_a = _enc(_plan("WARM_SLOT_REUSE", chat="chat-A"))
    _assert_fail_closed(_directive_state(env, tmp_path, chat_a, chat="chat-B"), "directive_chat_mismatch")
    _assert_fail_closed(_directive_state(env, tmp_path, _enc(_plan("WARM_SLOT_REUSE", chat=None)), chat="chat-B"), "directive_chat_mismatch")


def test_directive_replay_other_profile_is_rejected(env: Callable[..., Path], tmp_path: Path) -> None:
    std = _enc(_plan("WARM_SLOT_REUSE", profile="standard"))
    _assert_fail_closed(_directive_state(env, tmp_path, std, profile="zero-canon"), "directive_profile_mismatch")


@pytest.mark.parametrize("process,context", [
    ("WARM_SLOT_REUSE", "SLOT_HARD_RESET"),
    ("EPHEMERAL_KILL_AFTER_TURN", "CONTEXT_CONTINUE"),
    ("EPHEMERAL_KILL_AFTER_TURN", "CONTEXT_RESET_LOGICAL"),
])
def test_directive_allowlist_rejects_everything_but_warm_continue_or_logical_reset(env: Callable[..., Path], tmp_path: Path, process: str, context: str) -> None:
    _assert_fail_closed(_directive_state(env, tmp_path, _enc(_plan(process, context))), "directive_ephemeral")


@pytest.mark.parametrize("profile", ["standard", "zero-canon"])
def test_directive_valid_bound_logical_reset_passes_to_warm_path(env: Callable[..., Path], tmp_path: Path, profile: str) -> None:
    d = _enc(_plan("WARM_SLOT_REUSE", "CONTEXT_RESET_LOGICAL", profile=profile))
    st = _directive_state(env, tmp_path, d, profile=profile)
    assert st.handled is True and st.force_cold is False and st.decision_reason == "slot_empty"


def test_directive_ignored_when_flag_off(env: Callable[..., Path], tmp_path: Path) -> None:
    cfg = env(BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED="1")
    ad = _SRA.ExplicitResumeAdapter(tmp_path / "st", cfg)
    try:
        st = _prep(ad, [{"role": "user", "content": "q"}], "garbage")
        assert st.decision_reason == "slot_empty" and st.force_cold is False
    finally:
        ad.close()


def test_policy_config_replace_keeps_parity() -> None:
    assert replace(PolicyConfig(), enabled=True).allow_keyed_single_turn is False
