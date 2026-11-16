"""L1: исходы turn, долговечные штрафы и остановка при fencing."""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.route_penalty_state import LeaseFenced, RoutePenaltyState
from core.stream_outcome import OutcomeKind, StreamOutcome, StreamOutcomeClassifier
from core.turn_outcome import (
    PenaltyTarget,
    TurnResponse,
    commit_outcome,
    finish_outcome,
    finish_turn,
)

BODY = b'{"choices":[{"message":{"content":"ok"}}]}'
FRAME = b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
DONE = b"data: [DONE]\n\n"
HOOKS = ("fsm", "penalty", "tool_result", "sse_finalization")
CASES = [
    (200, "application/json", BODY, OutcomeKind.OK),
    (200, "application/json", b'{"error":{}}', OutcomeKind.ERROR_BODY),
    (503, "application/json", BODY, OutcomeKind.ERROR_BODY),
    (200, "application/json", b"{", OutcomeKind.ERROR_BODY),
    (200, "application/json", b"", OutcomeKind.EMPTY),
    (200, "application/json", b"{}", OutcomeKind.EMPTY),
    (
        200,
        "application/json",
        BODY.replace(b"ok", b"quota exceeded"),
        OutcomeKind.QUOTA_TEXT,
    ),
    (200, "text/plain", b"rate limit exceeded", OutcomeKind.QUOTA_TEXT),
    (200, "text/event-stream", FRAME + DONE, OutcomeKind.OK),
    (200, "text/event-stream", FRAME, OutcomeKind.STREAM_ERROR),
    (
        200,
        "text/event-stream",
        FRAME + b"event: error\n\n" + DONE,
        OutcomeKind.STREAM_ERROR,
    ),
    (503, "text/event-stream", FRAME + DONE, OutcomeKind.STREAM_ERROR),
    (200, "text/event-stream", DONE, OutcomeKind.EMPTY),
    (
        200,
        "text/event-stream",
        FRAME.replace(b"ok", b"quota exceeded") + DONE,
        OutcomeKind.QUOTA_TEXT,
    ),
    (
        200,
        "application/json",
        b'{"choices":[{"message":{"tool_calls":[{"function":{"name":"x","arguments":"{}"}}]}}]}',
        OutcomeKind.OK,
    ),
]


@pytest.fixture
def target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PenaltyTarget:
    monkeypatch.setattr("core.route_penalty_state.time.time", lambda: 1000.0)
    store = RoutePenaltyState(tmp_path / "penalties.json")
    owner = dict(owner_host="l1", boot_id=1, owner_pid=123, owner_started_at_utc=1)
    lease = store.acquire("model::backend", owner)
    assert lease is not None
    return PenaltyTarget(store, "model::backend", lease, 37.0)


@pytest.mark.parametrize("status,media,body,kind", CASES)
def test_turn_persists_classified_result(
    target: PenaltyTarget, status: int, media: str, body: bytes, kind: OutcomeKind
) -> None:
    outcome = finish_turn(TurnResponse(body, status, media), target)
    assert outcome.kind is kind
    store = RoutePenaltyState(target.store.storage_path)
    expected = (False, 0.0) if kind is OutcomeKind.OK else (True, 37.0)
    assert store.is_penalized("model", "backend") == expected
    assert store.is_penalized("model", "other") == (False, 0.0)
    assert not store.owns(
        target.edge, target.lease.lease_epoch, target.lease.lease_token
    )


def test_default_response_is_json(target: PenaltyTarget) -> None:
    assert finish_turn(TurnResponse(BODY), target).kind is OutcomeKind.OK


@pytest.mark.parametrize("kind", list(OutcomeKind))
def test_shared_commit_forwards_every_outcome(kind: OutcomeKind) -> None:
    lease, effects, outcome = Mock(), Mock(), StreamOutcome(kind)
    assert commit_outcome(lease, outcome, effects) is outcome
    assert lease.check_current.call_count == 4
    assert [call[0] for call in effects.mock_calls] == list(HOOKS)
    for name in HOOKS:
        getattr(effects, name).assert_called_once_with(outcome)


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("source", ["guard", "effect"])
def test_fencing_stops_effects(index: int, source: str) -> None:
    lease, effects = Mock(), Mock()
    error = LeaseFenced("revoked")
    if source == "guard":
        lease.check_current.side_effect = [None] * index + [error]
    else:
        getattr(effects, HOOKS[index]).side_effect = error
    with pytest.raises(LeaseFenced) as caught:
        commit_outcome(lease, StreamOutcome(OutcomeKind.OK), effects)
    assert caught.value is error
    expected = index if source == "guard" else index + 1
    assert [call[0] for call in effects.mock_calls] == list(HOOKS[:expected])
    assert lease.check_current.call_count == index + 1


@pytest.mark.parametrize("width", [1, 7, 10000])
def test_stream_entry_uses_same_result(target: PenaltyTarget, width: int) -> None:
    classifier = StreamOutcomeClassifier()
    body = FRAME.replace(b"ok", "Ответ".encode()) + DONE
    for index in range(0, len(body), width):
        classifier.feed(body[index : index + width])
    assert finish_outcome(classifier, target).kind is OutcomeKind.OK
    assert target.store.is_penalized("model", "backend") == (False, 0.0)


@pytest.mark.parametrize("body", [BODY, b'{"error":{}}', b""])
def test_abort_preserves_original_deadline(
    target: PenaltyTarget, monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    assert target.store.finish(target.edge, target.lease, 10) is not None
    monkeypatch.setattr("core.route_penalty_state.time.time", lambda: 1011.0)
    owner = dict(owner_host="l1", boot_id=1, owner_pid=123, owner_started_at_utc=1)
    lease = target.store.acquire(target.edge, owner)
    assert lease is not None
    target = replace(target, lease=lease)
    outcome = finish_turn(TurnResponse(body), target, client_aborted=True)
    assert outcome.kind is OutcomeKind.CLIENT_ABORT
    state = json.loads(target.store.storage_path.read_text())[target.edge]
    assert state["phase"] == "OPEN"
    assert state["penalized_until"] == 1010.0
    assert state["lease_token"] == "" and state["lease_until"] == 0


@pytest.mark.parametrize("aborted", [False, True])
@pytest.mark.parametrize("mismatch", ["epoch", "token", "released"])
def test_stale_turn_cannot_write(
    target: PenaltyTarget, aborted: bool, mismatch: str
) -> None:
    if mismatch == "released":
        assert target.store.abort(
            target.edge, target.lease.lease_epoch, target.lease.lease_token
        )
    elif mismatch == "epoch":
        target = replace(target, lease=replace(target.lease, lease_epoch=0))
    else:
        target = replace(target, lease=replace(target.lease, lease_token="stale"))
    before = target.store.storage_path.read_bytes()
    with pytest.raises(LeaseFenced):
        finish_turn(TurnResponse(BODY), target, client_aborted=aborted)
    assert target.store.storage_path.read_bytes() == before


@pytest.mark.parametrize("aborted", [False, True])
@pytest.mark.parametrize("failure", [LeaseFenced, RuntimeError, OSError])
def test_write_exception_is_terminal(
    target: PenaltyTarget,
    monkeypatch: pytest.MonkeyPatch,
    aborted: bool,
    failure: type[Exception],
) -> None:
    error = failure("terminal")
    callback = Mock(side_effect=error)
    monkeypatch.setattr(target.store, "abort" if aborted else "finish", callback)
    before = target.store.storage_path.read_bytes()
    with pytest.raises(failure) as caught:
        finish_turn(TurnResponse(BODY), target, client_aborted=aborted)
    assert caught.value is error
    assert callback.call_count == 1
    assert target.store.storage_path.read_bytes() == before


@pytest.mark.parametrize("aborted", [False, True])
def test_failed_persistence_is_not_success(
    target: PenaltyTarget, monkeypatch: pytest.MonkeyPatch, aborted: bool
) -> None:
    callback = Mock(return_value=None)
    monkeypatch.setattr(target.store, "abort" if aborted else "finish", callback)
    with pytest.raises(OSError):
        finish_turn(TurnResponse(BODY), target, client_aborted=aborted)
    assert callback.call_count == 1


def test_repeated_completion_is_fenced(target: PenaltyTarget) -> None:
    assert finish_turn(TurnResponse(BODY), target).kind is OutcomeKind.OK
    before = target.store.storage_path.read_bytes()
    with pytest.raises(LeaseFenced):
        finish_turn(TurnResponse(BODY), target)
    assert target.store.storage_path.read_bytes() == before


def _complexity(node: ast.AST) -> int:
    branches = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.ExceptHandler,
        ast.With,
        ast.AsyncWith,
        ast.IfExp,
        ast.Assert,
    )
    return (
        1
        + sum(isinstance(n, branches) for n in ast.walk(node))
        + sum(len(n.values) - 1 for n in ast.walk(node) if isinstance(n, ast.BoolOp))
        + sum(len(n.ifs) for n in ast.walk(node) if isinstance(n, ast.comprehension))
    )


@pytest.mark.parametrize(
    "relative,cap",
    [
        ("core/turn_outcome.py", 100),
        ("tests/test_turn_outcome.py", 300),
    ],
)
def test_architecture_caps(relative: str, cap: int) -> None:
    source = (Path(__file__).resolve().parents[1] / relative).read_text()
    assert len(source.splitlines()) <= cap
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        count = len(args.posonlyargs + args.args + args.kwonlyargs)
        assert count + bool(args.vararg) + bool(args.kwarg) <= 5, node.name
        assert (node.end_lineno or node.lineno) - node.lineno + 1 <= 40, node.name
        assert _complexity(node) <= 10, node.name
