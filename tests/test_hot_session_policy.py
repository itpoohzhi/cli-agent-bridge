from __future__ import annotations

import ast
import itertools
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.hot_session_policy import (  # noqa: E402
    SLOT_TRANSITIONS,
    DecisionAction,
    DecisionReason,
    ExecutionMode,
    HistoryFingerprints,
    PolicyConfig,
    ProjectedMessage,
    SessionKeyParts,
    SlotEvent,
    SlotSnapshot,
    SlotState,
    TransitionOutcome,
    TurnDecision,
    TurnPolicyInput,
    build_session_key,
    compute_history_fingerprints,
    compute_owner_hmac,
    decide_turn,
    encode_length_prefixed,
    is_slot_expired,
    transition,
)

_KEY = b"super-secret-hmac-key-for-tests!"
_CFG = PolicyConfig(enabled=True)


def _msg(role: str, text: str) -> ProjectedMessage:
    return ProjectedMessage(role, text, "", "", "")


def _slot(
    state: SlotState = SlotState.READY,
    *,
    cid: str = "cid-1",
    stored_digest: str = "",
    gen: int = 1,
    turns: int = 1,
    since_s: float = 0.0,
) -> SlotSnapshot:
    return SlotSnapshot(
        state, cid, stored_digest, 2, 1, gen, 1, 100.0, 100.0, turns, since_s, since_s
    )


def _req(
    history: HistoryFingerprints,
    *,
    owner_verified: bool = True,
    chat_id: str = "chat-1",
    client_cid: str = "",
    now_s: float = 200.0,
    supersedes: int = 0,
) -> TurnPolicyInput:
    return TurnPolicyInput(
        owner_verified, "owner-hash", chat_id, client_cid, history, now_s, 1, supersedes
    )


def _chk(
    sl: SlotSnapshot,
    rq: TurnPolicyInput,
    act: DecisionAction,
    rsn: DecisionReason,
    mode: int = 0,
    cfg: PolicyConfig = _CFG,
) -> None:
    d = decide_turn(sl, rq, cfg)
    commit, evict = mode >= 1, mode == 2
    assert (d.action, d.reason, d.allow_commit, d.evict_expired_first) == (
        act,
        rsn,
        commit,
        evict,
    )


def test_all_66_slot_transitions_and_illegal_targets() -> None:
    s, e = SlotState, SlotEvent
    expected: dict[tuple[SlotState, SlotEvent], SlotState] = {
        (s.EMPTY, e.TURN_COMMIT_PENDING): s.UNCONFIRMED,
        (s.UNCONFIRMED, e.PERSIST_OK): s.READY,
        (s.UNCONFIRMED, e.TURN_COMMIT_PENDING): s.UNCONFIRMED,
        (s.UNCONFIRMED, e.TTL_EXCEEDED): s.EMPTY,
        (s.UNCONFIRMED, e.EVICT): s.EMPTY,
        (s.READY, e.CLAIM_RESUME): s.IN_FLIGHT,
        (s.READY, e.TURN_COMMIT_PENDING): s.UNCONFIRMED,
        (s.READY, e.TTL_EXCEEDED): s.EXPIRED,
        (s.READY, e.EVICT): s.EMPTY,
        (s.IN_FLIGHT, e.TURN_COMMIT_PENDING): s.UNCONFIRMED,
        (s.IN_FLIGHT, e.TURN_ABORT_PRE_SPAWN): s.READY,
        (s.IN_FLIGHT, e.TURN_ABORT_POST_SPAWN): s.EMPTY,
        (s.IN_FLIGHT, e.TTL_EXCEEDED): s.EMPTY,
        (s.EXPIRED, e.EVICT): s.EMPTY,
    }
    resets = (e.PERSIST_FAIL, e.CORRUPT_DETECTED, e.INVALIDATE, e.EPOCH_CHANGED)
    for st in SlotState:
        for ev in resets:
            expected[(st, ev)] = s.EMPTY
    assert dict(SLOT_TRANSITIONS) == expected
    pairs = list(itertools.product(SlotState, SlotEvent))
    assert len(pairs) == 66
    for st, ev in pairs:
        out = transition(st, ev)
        if (st, ev) in expected:
            assert out == TransitionOutcome(expected[(st, ev)], valid=True)
        else:
            assert out == TransitionOutcome(s.EMPTY, valid=False)
            assert out.next_state not in (s.READY, s.IN_FLIGHT)


def test_build_session_key_axes_and_required_fields() -> None:
    def key(
        own: str = "own1",
        chat: str = "chat1",
        sub: str = "sub1",
        mode: ExecutionMode = ExecutionMode.PLAIN,
        ctx: str = "ctx1",
    ) -> str:
        return build_session_key(
            SessionKeyParts("v1", own, chat, sub, "m1", "high", mode, "p", "l", ctx)
        )

    k0 = key()
    assert len(k0) == 64
    assert k0 != key(own="own2") and k0 != key(chat="chat2") and k0 != key(sub="sub2")
    assert k0 != key(mode=ExecutionMode.AGENTIC) and k0 != key(ctx="ctx2")
    assert key(own="") == "" and key(chat="") == "" and key(ctx="") == ""


def test_compute_owner_hmac_validation_and_collision_resistance() -> None:
    assert compute_owner_hmac(b"", "abcdefgh") == ""
    assert compute_owner_hmac(_KEY, "") == ""
    assert compute_owner_hmac(_KEY, "1234567") == ""
    h1 = compute_owner_hmac(_KEY, "abcdefgh|x", "y")
    h2 = compute_owner_hmac(_KEY, "abcdefgh", "x|y")
    assert len(h1) == 64 and h1 != h2
    assert h1 != compute_owner_hmac(b"another-secret-key!", "abcdefgh|x", "y")
    assert encode_length_prefixed(("a|b", "c")) != encode_length_prefixed(("a", "b|c"))


def test_decide_turn_append_only_turn2_supersede_and_rate_limit() -> None:
    a, r = DecisionAction, DecisionReason
    turn1 = [_msg("user", "u1"), _msg("assistant", "a1")]
    fp1 = compute_history_fingerprints(turn1, 2, _KEY, 100, _CFG)
    slot = _slot(SlotState.READY, stored_digest=fp1.full_digest, gen=7)
    turn2 = [*turn1, _msg("user", "u2")]
    fp2 = compute_history_fingerprints(turn2, 2, _KEY, 150, _CFG)
    assert decide_turn(slot, _req(fp2), _CFG) == TurnDecision(
        a.RESUME, r.APPEND_ONLY_MATCH, True, cid="cid-1"
    )
    assert decide_turn(slot, _req(fp1), _CFG).reason == r.HISTORY_DIVERGED_SUPERSEDE

    forged = [_msg("user", "u1"), _msg("assistant", "a1_forged"), _msg("user", "u2")]
    fp_bad = compute_history_fingerprints(forged, 2, _KEY, 150, _CFG)
    sup = decide_turn(slot, _req(fp_bad, supersedes=2), _CFG)
    assert sup == TurnDecision(
        a.COLD_SEED, r.HISTORY_DIVERGED_SUPERSEDE, True, "", True, 7, fp1.full_digest
    )
    _chk(
        slot, _req(fp_bad, supersedes=3), a.COLD_REJECT, r.HISTORY_DIVERGED_RATE_LIMITED
    )


def test_decide_turn_guards_rejects_and_expiry() -> None:
    s, a, r = SlotState, DecisionAction, DecisionReason
    fp = compute_history_fingerprints(
        [_msg("user", "u1"), _msg("assistant", "a1")], 2, _KEY, 100, _CFG
    )
    rq = _req(fp)
    _chk(_slot(s.EMPTY), rq, a.COLD_BYPASS, r.DISABLED, cfg=PolicyConfig())
    _chk(
        _slot(s.EMPTY),
        _req(fp, owner_verified=False),
        a.COLD_BYPASS,
        r.MISSING_OWNER_TOKEN,
    )
    _chk(_slot(s.EMPTY), _req(fp, chat_id=""), a.COLD_BYPASS, r.NO_EXPLICIT_CHAT_ID)

    fp_na = compute_history_fingerprints([_msg("user", "u1")], 1, _KEY, 50, _CFG)
    _chk(
        _slot(s.READY, stored_digest=fp.full_digest),
        _req(fp_na),
        a.COLD_REJECT,
        r.NO_ASSISTANT_HISTORY,
    )
    for st in (s.EMPTY, s.EXPIRED):
        _chk(
            _slot(st),
            _req(fp, client_cid="foreign"),
            a.COLD_REJECT,
            r.UNOWNED_EXPLICIT_CID,
        )
    _chk(
        _slot(s.READY, cid="cid-1"),
        _req(fp, client_cid="other"),
        a.COLD_REJECT,
        r.UNOWNED_EXPLICIT_CID,
    )

    inf = _slot(s.IN_FLIGHT, since_s=150.0)
    snap = repr(inf)
    _chk(inf, rq, a.COLD_REJECT, r.SLOT_IN_FLIGHT)
    assert repr(inf) == snap
    _chk(
        _slot(s.IN_FLIGHT, since_s=0.0),
        _req(fp, now_s=1000.0),
        a.COLD_SEED,
        r.SLOT_EXPIRED,
        2,
    )
    _chk(_slot(s.UNCONFIRMED, since_s=190.0), rq, a.COLD_REJECT, r.SLOT_UNCONFIRMED)
    _chk(_slot(s.UNCONFIRMED, since_s=0.0), rq, a.COLD_SEED, r.SLOT_EXPIRED, 2)
    _chk(_slot(s.CORRUPT), rq, a.COLD_SEED, r.SLOT_CORRUPT, 2)
    _chk(_slot(s.EXPIRED), rq, a.COLD_SEED, r.SLOT_EXPIRED, 2)
    _chk(_slot(s.EMPTY), rq, a.COLD_SEED, r.SLOT_EMPTY, 1)
    assert is_slot_expired(_slot(s.READY, turns=30), 150.0, _CFG) is True


def test_history_guard_bounds_short_circuit_before_hashing() -> None:
    a, r = DecisionAction, DecisionReason
    cfg = PolicyConfig(enabled=True, guard_max_bytes=100, guard_max_messages=2)
    msgs = [_msg("user", "x"), _msg("assistant", "y"), _msg("user", "z")]
    fp_b = compute_history_fingerprints(msgs, 2, _KEY, 101, cfg)
    assert (fp_b.bounded, fp_b.bound_reason, fp_b.full_digest) == (
        False,
        r.GUARD_BOUND_BYTES,
        "",
    )
    _chk(
        _slot(SlotState.EMPTY), _req(fp_b), a.COLD_BYPASS, r.GUARD_BOUND_BYTES, cfg=cfg
    )

    fp_m = compute_history_fingerprints(msgs, 2, _KEY, 50, cfg)
    assert (fp_m.bounded, fp_m.bound_reason, fp_m.full_digest) == (
        False,
        r.GUARD_BOUND_MSGS,
        "",
    )
    _chk(_slot(SlotState.EMPTY), _req(fp_m), a.COLD_BYPASS, r.GUARD_BOUND_MSGS, cfg=cfg)


def _mccabe_cc(fn: ast.AST) -> int:
    branches = (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.IfExp)
    return 1 + sum(
        1 if isinstance(n, branches) else len(n.values) - 1
        for n in ast.walk(fn)
        if isinstance(n, (*branches, ast.BoolOp))
    )


def test_policy_module_ast_and_purity_invariants() -> None:
    src = (_REPO / "core" / "hot_session_policy.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    assert lines[0] == "from __future__ import annotations"
    assert len(lines) <= 280
    low = src.lower()
    for vendor in ("agy", "gemini", "dsh", "zero-canon", "zero_canon"):
        assert vendor not in low, f"forbidden vendor literal: {vendor}"

    allowed = set("__future__ collections dataclasses enum hashlib hmac typing".split())
    forbidden = set("json os pathlib time subprocess bridges adapters".split())
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed and top not in forbidden
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            assert top in allowed and top not in forbidden
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.end_lineno is not None
            assert (node.end_lineno - node.lineno + 1) <= 40, node.name
            argc = (
                len(node.args.posonlyargs)
                + len(node.args.args)
                + len(node.args.kwonlyargs)
            )
            argc += int(node.args.vararg is not None) + int(node.args.kwarg is not None)
            assert argc <= 5, node.name
            assert _mccabe_cc(node) <= 10, node.name
