"""Deterministic L1 corpus for Codex v2 FSM, stream splits, and recovery."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.codex_recovery_fsm as rec  # noqa: E402
import core.stdio_resident.codex_protocol_fsm as fsm  # noqa: E402
from core.stdio_resident.protocol_driver import DecodedChunk  # noqa: E402
from core.stdio_resident.turn_stream import (  # noqa: E402
    AggregateOutputLimitError,
    StepBoundary,
    TurnStreamAssembler,
)

SOL, TERRA = "gpt-6.1-sol", "gpt-6.1-terra"
ATTEST_SOL = (
    "profile=zero-canon;backend=codex;tools=off;"
    "sandbox=read-only;approval=never;model=gpt-6.1-sol;effort=high;phase=completed"
)
EV, PH, EF = fsm.EventKind, fsm.ProtocolPhase, fsm.EffectKind
REV, RPH, REF = rec.RecoveryEventKind, rec.RecoveryPhase, rec.RecoveryEffectKind
CRED, REv = rec.HealthDomain.CREDENTIAL, rec.RecoveryEvent
EXP = rec.ProbeExpectation(SOL, "high", "codex", "codex-app-server-v2", "zero-canon")


def _ntf(method: str, params: dict[str, object]) -> dict[str, object]:
    return {"method": method, "params": params}


def _step(
    s: fsm.ProtocolState, frame: dict[str, object], epoch: int | None = None
) -> fsm.TransitionResult:
    ep = s.epoch if epoch is None else epoch
    return fsm.transition(s, fsm.ProtocolEvent(EV.SERVER_FRAME, frame, ep))


def _boot(
    *, zero_canon: bool = True, with_jsonrpc: bool = True
) -> tuple[fsm.ProtocolState, dict[str, object], dict[str, object]]:
    """Drive FSM: IDLE -> INITIALIZED -> THREAD_READY -> TURN_ACTIVE (bound)."""
    s, fx = fsm.transition(fsm.ProtocolState(), fsm.ProtocolEvent(EV.START_INITIALIZE))
    assert s.phase is PH.INITIALIZING and s.pending_request_id == 1
    assert fx[0].payload["method"] == "initialize"

    init_ok: dict[str, object] = {"id": 1, "result": {"userAgent": "codex/0.171.0"}}
    if with_jsonrpc:
        init_ok["jsonrpc"] = "2.0"
    s, fx = _step(s, init_ok)
    assert s.phase is PH.INITIALIZED
    assert fx[0].payload == {"jsonrpc": "2.0", "method": "initialized"}

    tp = {"model": SOL, "cwd": "/tmp/zc", "ephemeral": True, "zero_canon": zero_canon}
    s, thr_fx = fsm.transition(s, fsm.ProtocolEvent(EV.START_THREAD, tp))
    res = {"thread": {"id": "thr-1"}, "model": SOL, "reasoningEffort": "high"}
    s, _ = _step(s, {"id": s.pending_request_id, "result": res})
    assert s.phase is PH.THREAD_READY and s.thread_id == "thr-1"

    up = {"prompt": "PING", "model": SOL, "effort": "high", "zero_canon": zero_canon}
    s, turn_fx = fsm.transition(s, fsm.ProtocolEvent(EV.START_TURN, up))
    s, ack_fx = _step(s, {"id": s.pending_request_id, "result": {"turn": {"id": "t1"}}})
    assert s.phase is PH.TURN_ACTIVE and s.turn_id == "t1"
    assert ack_fx[0].kind is EF.EMIT_TURN_ACK
    return s, dict(thr_fx[0].payload), dict(turn_fx[0].payload)


def _pong(*, probe_id: str = "p1", done: bool = True) -> rec.PongReceipt:
    return rec.PongReceipt(
        probe_id,
        SOL,
        SOL,
        "high",
        "high",
        "codex",
        "codex-app-server-v2",
        "zero-canon",
        ATTEST_SOL,
        done,
        done,
        "PONG",
    )


@pytest.mark.parametrize("with_jsonrpc", [True, False])
def test_fsm_lifecycle_optional_jsonrpc_and_deltas(with_jsonrpc: bool) -> None:
    """ADR-001 FSM #1-#9: optional jsonrpc, Zero-Canon params, deltas, completed."""
    s, thr_req, turn_req = _boot(zero_canon=True, with_jsonrpc=with_jsonrpc)
    assert thr_req["params"] == {
        "ephemeral": True,
        "model": SOL,
        "cwd": "/tmp/zc",
        "sandbox": "read-only",
        "approvalPolicy": "never",
    }
    assert turn_req["params"] == {
        "threadId": "thr-1",
        "input": [{"type": "text", "text": "PING"}],
        "model": SOL,
        "effort": "high",
        "approvalPolicy": "never",
        "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
    }
    deltas = (
        ("item/reasoning/textDelta", "reasoning", "think"),
        ("item/reasoning/summaryTextDelta", "reasoning_summary", "sum"),
        ("item/agentMessage/delta", "content", "PONG"),
    )
    for method, chan, text in deltas:
        p = {"threadId": "thr-1", "turnId": "t1", "itemId": "i1", "delta": text}
        s, fx = _step(s, {"method": method, "params": p})
        assert fx[0].kind is EF.EMIT_DELTA
        assert (fx[0].payload["channel"], fx[0].payload["delta"]) == (chan, text)

    done = {"threadId": "thr-1", "turn": {"id": "t1", "status": "completed"}}
    s, fx = _step(s, {"method": "turn/completed", "params": done})
    assert s.phase is PH.COMPLETED and fx[0].kind is EF.EMIT_TERMINAL
    assert fx[0].payload["status"] == "completed"


def test_fsm_bad_jsonrpc_no_client_thread_id_and_turn_started() -> None:
    """ADR-001 FSM #2/#5/#7: bad jsonrpc fails; no th-1; deferred turn/started binds."""
    s, _ = fsm.transition(fsm.ProtocolState(), fsm.ProtocolEvent(EV.START_INITIALIZE))
    f1, fx1 = _step(s, {"jsonrpc": "1.0", "id": 1, "result": {}})
    assert (
        f1.phase is PH.FAILED and fx1[0].payload["code"] == "resident_protocol_failed"
    )

    no_tid = fsm.ProtocolState(phase=PH.THREAD_READY)
    f2, fx2 = fsm.transition(no_tid, fsm.ProtocolEvent(EV.START_TURN, {}))
    assert (
        f2.phase is PH.FAILED and fx2[0].payload["code"] == "resident_protocol_failed"
    )

    ready = fsm.ProtocolState(
        phase=PH.THREAD_READY, epoch=2, next_request_id=4, thread_id="thr-2"
    )
    p = {"prompt": "hi", "model": TERRA, "effort": "medium"}
    s, _ = fsm.transition(ready, fsm.ProtocolEvent(EV.START_TURN, p))
    s, _ = _step(s, {"id": s.pending_request_id, "result": {}})
    assert s.turn_id is None and s.phase is PH.TURN_ACTIVE

    started = {"threadId": "thr-2", "turn": {"id": "trn-2"}}
    s, fx_b = _step(s, {"method": "turn/started", "params": started})
    assert s.turn_id == "trn-2" and fx_b[0].kind is EF.EMIT_TURN_ACK


def test_fsm_correlation_epoch_fencing_and_cancel_interrupt() -> None:
    """ADR-001 FSM #8-#12: stale frames dropped; cancel sends turn/interrupt; epoch fences."""
    s, _, _ = _boot(zero_canon=True)
    stale = (
        _ntf(
            "item/agentMessage/delta", {"threadId": "x", "turnId": "t1", "delta": "a"}
        ),
        _ntf(
            "item/agentMessage/delta",
            {"threadId": "thr-1", "turnId": "x", "delta": "a"},
        ),
        _ntf(
            "turn/completed",
            {"threadId": "thr-1", "turn": {"id": "x", "status": "completed"}},
        ),
        {"id": 999, "result": {"ok": True}},
    )
    for frame in stale:
        assert _step(s, frame) == (s, ())

    s_c, fx_c = fsm.transition(s, fsm.ProtocolEvent(EV.CANCEL_TURN))
    assert fx_c[0].payload["method"] == "turn/interrupt"
    assert fx_c[0].payload["params"] == {"threadId": "thr-1", "turnId": "t1"}
    s_ack, fx_ack = _step(s_c, {"id": s_c.interrupt_request_id, "result": {}})
    assert s_ack.phase is PH.TURN_ACTIVE and fx_ack == ()

    s_adv, _ = fsm.transition(s_ack, fsm.ProtocolEvent(EV.ADVANCE_EPOCH))
    assert s_adv.epoch == s.epoch + 1 and s_adv.phase is PH.THREAD_READY
    done = _ntf(
        "turn/completed",
        {"threadId": "thr-1", "turn": {"id": "t1", "status": "completed"}},
    )
    assert _step(s_adv, done, s.epoch) == (s_adv, ())


def test_fsm_error_paths_zero_canon_tool_block_and_transport_error() -> None:
    """ADR-001 FSM #9/#12: willRetry ignored, tool event fails closed, failed terminal."""
    s, _, _ = _boot(zero_canon=True)
    retry = _ntf("error", {"threadId": "thr-1", "willRetry": True})
    assert _step(s, retry) == (s, ())

    s_t, fx_t = _step(s, _ntf("item/tool/call", {"threadId": "thr-1"}))
    assert s_t.phase is PH.FAILED
    assert fx_t[0].payload["code"] == "zero_canon_tool_event_forbidden"

    fail_t = {"id": "t1", "status": "failed", "error": {"message": "x"}}
    s_f, fx_f = _step(s, _ntf("turn/completed", {"threadId": "thr-1", "turn": fail_t}))
    assert s_f.phase is PH.FAILED
    assert [e.kind for e in fx_f] == [EF.EMIT_ERROR, EF.EMIT_TERMINAL]

    intr = {"threadId": "thr-1", "turn": {"id": "t1", "status": "interrupted"}}
    s_i, fx_i = _step(s, _ntf("turn/completed", intr))
    assert s_i.phase is PH.CANCELLED and fx_i[0].payload["status"] == "interrupted"

    s_tr, fx_tr = fsm.transition(s, fsm.ProtocolEvent(EV.TRANSPORT_ERROR, {}))
    assert s_tr.phase is PH.FAILED
    assert fx_tr[0].payload["code"] == "upstream_incomplete_stream"


def test_stream_chunk_splits_step_boundary_cap_and_fake_clock() -> None:
    """ADR-001 Stream: 1/1B/7B/seeded-random splits, StepBoundary, cap, fake clock."""
    expected = "Привет, мир! Step1.Step2 — PONG 🚀"
    rng, rand_parts, pos = random.Random(42), list[str](), 0
    while pos < len(expected):
        step = rng.randint(1, 5)
        rand_parts.append(expected[pos : pos + step])
        pos += step
    by7 = [expected[i : i + 7] for i in range(0, len(expected), 7)]

    for parts in ([expected], list(expected), by7, rand_parts):
        clock = [100.0, 190.0]
        asm = TurnStreamAssembler(
            lambda c=clock: c.__setitem__(1, c[0] + 90.0), aggregate_output_bytes=1024
        )
        out: list[str] = []
        for idx, part in enumerate(parts):
            clock[0] = 100.0 + idx * 10.0
            out.append(asm.process_chunk(DecodedChunk(text=part)).content)
        assert "".join(out) == expected and clock[1] == clock[0] + 90.0

    stepped = TurnStreamAssembler(aggregate_output_bytes=64)
    a = stepped.process_chunk(DecodedChunk(text="Alpha.")).content
    _ = stepped.process_chunk(StepBoundary())
    assert (
        a + stepped.process_chunk(DecodedChunk(text="Beta.")).content
        == "Alpha.\n\nBeta."
    )

    capped = TurnStreamAssembler(aggregate_output_bytes=6)
    _ = capped.process_chunk(DecodedChunk(text="abcd"))
    with pytest.raises(AggregateOutputLimitError, match="output_limit_exceeded"):
        _ = capped.process_chunk(DecodedChunk(reasoning="efgh"))


def test_recovery_fsm_domain_isolation_and_cooldown_tick() -> None:
    """ADR-001 Recovery FSM: route/credential isolation, non-PONG rejection, fake-clock tick."""
    st = rec.create_recovery_state(EXP, "c1", RPH.HEALTHY, RPH.HEALTHY)
    st, _ = rec.transition(st, REv(REV.FAILURE, 10.0, error_code="quota_exhausted"))
    assert st.is_route_healthy and st.credential.phase is RPH.BLOCKED

    h200 = REv(
        REV.NON_PONG_SIGNAL, 12.0, CRED, evidence_kind=rec.EvidenceKind.HEALTH_200
    )
    st, rej = rec.transition(st, h200)
    assert rej[0].kind is REF.REJECT_TRANSITION and st.credential.phase is RPH.BLOCKED

    cd = REv(
        REV.FAILURE,
        20.0,
        error_code="quota_exhausted",
        cooldown_s=30.0,
        proven_reset=True,
    )
    st, _ = rec.transition(st, cd)
    assert (
        st.credential.phase is RPH.COOLDOWN and st.credential.cooldown_until_s == 50.0
    )
    st, early = rec.transition(st, REv(REV.TICK, 49.9))
    assert early == () and st.credential.phase is RPH.COOLDOWN
    st, due = rec.transition(st, REv(REV.TICK, 50.0))
    assert due[0].kind is REF.PROBE_READY and st.credential.phase is RPH.PROBE_DUE


def test_recovery_fsm_pong_receipt_validation() -> None:
    """ADR-001 Recovery FSM: incomplete/stale PONG rejected; complete PONG restores HEALTHY."""
    st = rec.create_recovery_state(EXP, "c1", RPH.HEALTHY, RPH.PROBE_DUE)
    st, _ = rec.transition(st, REv(REV.PROBE_STARTED, 51.0, CRED, probe_id="p1"))

    st_s, fx_s = rec.transition(
        st, REv(REV.PONG_RECEIPT, 52.0, CRED, receipt=_pong(probe_id="x"))
    )
    assert st_s == st and fx_s[0].kind is REF.REJECT_TRANSITION

    inc = REv(REV.PONG_RECEIPT, 52.0, CRED, receipt=_pong(done=False))
    st_bad, fx_bad = rec.transition(st, inc, rec.RecoveryPolicy(probe_cooldown_s=15.0))
    assert fx_bad[0].kind is REF.REJECT_TRANSITION
    assert st_bad.credential.phase is RPH.COOLDOWN

    st_ok, fx_ok = rec.transition(
        st, REv(REV.PONG_RECEIPT, 52.0, CRED, receipt=_pong())
    )
    assert st_ok.is_healthy
    assert [e.kind for e in fx_ok] == [REF.MARK_HEALTHY, REF.EMIT_RECOVERY_RECEIPT]
