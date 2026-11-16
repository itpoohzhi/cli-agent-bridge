"""L1: классификация passthrough, долговечные исходы и терминальный fencing."""

from __future__ import annotations

import ast
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.passthrough_outcome import (
    LeaseFenced,
    PenaltyTarget,
    commit_outcome,
    finish_outcome,
)
from core.route_penalty_state import RoutePenaltyState
from core.stream_outcome import OutcomeKind, StreamOutcome, StreamOutcomeClassifier

JSON = "application/json"
SSE = "text/event-stream"
BODY = b'{"choices":[{"message":{"content":"ok"}}]}'
FRAME = b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
DONE = b"data: [DONE]\n\n"
HOOKS = ("fsm", "penalty", "tool_result", "sse_finalization")
CASES = [
    (JSON, BODY, OutcomeKind.OK),
    (SSE, FRAME + DONE, OutcomeKind.OK),
    (JSON, b"", OutcomeKind.EMPTY),
    (JSON, b"{}", OutcomeKind.EMPTY),
    (JSON, b'{"error":{}}', OutcomeKind.ERROR_BODY),
    (
        JSON,
        b'{"error":{},"choices":[{"message":{"content":"ok"}}]}',
        OutcomeKind.ERROR_BODY,
    ),
    (JSON, BODY.replace(b"ok", b"quota exceeded"), OutcomeKind.QUOTA_TEXT),
    ("text/plain", b"quota exceeded", OutcomeKind.QUOTA_TEXT),
    (SSE, b"", OutcomeKind.EMPTY),
    (SSE, DONE, OutcomeKind.EMPTY),
    (SSE, FRAME, OutcomeKind.STREAM_ERROR),
    (SSE, FRAME + b"data: [DONE]", OutcomeKind.STREAM_ERROR),
    (SSE, FRAME + b'data: {"error":{}}\n\n' + DONE, OutcomeKind.STREAM_ERROR),
    (SSE, FRAME.replace(b"ok", b"quota exceeded") + DONE, OutcomeKind.QUOTA_TEXT),
]


def _forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("L1 forbids sockets and sleep")


@pytest.fixture(autouse=True)
def no_network_or_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(time, "sleep", _forbidden)
    monkeypatch.setattr(time, "time", lambda: 1000.0)


@pytest.fixture
def target(tmp_path: Path) -> PenaltyTarget:
    store = RoutePenaltyState(tmp_path / "penalties.json")
    owner = dict(owner_host="l1", boot_id=1, owner_pid=123, owner_started_at_utc=1)
    lease = store.acquire("model::backend", owner)
    assert lease is not None
    return PenaltyTarget(store, "model::backend", lease, 37.0)


def _classifier(media: str, body: bytes, width: int = 7) -> StreamOutcomeClassifier:
    classifier = StreamOutcomeClassifier(200, media)
    for index in range(0, len(body), width):
        classifier.feed(body[index : index + width])
    return classifier


@pytest.mark.parametrize("media,body,kind", CASES)
@pytest.mark.parametrize("width", [1, 7, 10000])
def test_body_controls_penalty(
    target: PenaltyTarget, media: str, body: bytes, kind: OutcomeKind, width: int
) -> None:
    outcome = finish_outcome(_classifier(media, body, width), target)
    assert outcome.kind is kind
    expected = (False, 0.0) if kind is OutcomeKind.OK else (True, 37.0)
    assert target.store.is_penalized("model", "backend") == expected
    assert target.store.is_penalized("model", "other") == (False, 0.0)
    assert not target.store.owns(
        target.edge, target.lease.lease_epoch, target.lease.lease_token
    )


def test_abort_preserves_original_penalty(target: PenaltyTarget) -> None:
    outcome = finish_outcome(_classifier(JSON, BODY), target, client_aborted=True)
    assert outcome.kind is OutcomeKind.CLIENT_ABORT
    assert target.store.is_penalized("model", "backend") == (False, 0.0)
    assert '"OPEN"' in target.store.storage_path.read_text()


@pytest.mark.parametrize("media,body,kind", CASES)
def test_stale_lease_leaves_store_unchanged(
    target: PenaltyTarget, media: str, body: bytes, kind: OutcomeKind
) -> None:
    assert target.store.abort(
        target.edge, target.lease.lease_epoch, target.lease.lease_token
    )
    before = target.store.storage_path.read_bytes()
    with pytest.raises(LeaseFenced):
        finish_outcome(_classifier(media, body), target)
    assert target.store.storage_path.read_bytes() == before


@pytest.mark.parametrize("aborted", [False, True])
@pytest.mark.parametrize("failure", [LeaseFenced, RuntimeError, OSError])
def test_store_errors_are_not_swallowed(
    target: PenaltyTarget,
    monkeypatch: pytest.MonkeyPatch,
    aborted: bool,
    failure: type[Exception],
) -> None:
    error = failure("terminal")
    callback = Mock(side_effect=error)
    monkeypatch.setattr(target.store, "abort" if aborted else "finish", callback)
    before = target.store.storage_path.read_bytes()
    with pytest.raises(failure, match="terminal") as caught:
        finish_outcome(_classifier(JSON, BODY), target, client_aborted=aborted)
    assert caught.value is error
    assert callback.call_count == 1
    assert target.store.storage_path.read_bytes() == before


@pytest.mark.parametrize("aborted", [False, True])
def test_store_none_is_not_success(
    target: PenaltyTarget, monkeypatch: pytest.MonkeyPatch, aborted: bool
) -> None:
    monkeypatch.setattr(
        target.store, "abort" if aborted else "finish", Mock(return_value=None)
    )
    with pytest.raises(OSError):
        finish_outcome(_classifier(JSON, BODY), target, client_aborted=aborted)


@dataclass
class Guard:
    fail_at: int = -1
    checks: int = 0

    def check_current(self) -> None:
        self.checks += 1
        if self.checks == self.fail_at:
            raise LeaseFenced("revoked")


@dataclass
class Effects:
    calls: list[str] = field(default_factory=list)
    fail_at: str = ""

    def _record(self, name: str) -> None:
        if self.fail_at == name:
            raise LeaseFenced(name)
        self.calls.append(name)

    def fsm(self, outcome: StreamOutcome) -> None:
        self._record("fsm")

    def penalty(self, outcome: StreamOutcome) -> None:
        self._record("penalty")

    def tool_result(self, outcome: StreamOutcome) -> None:
        self._record("tool_result")

    def sse_finalization(self, outcome: StreamOutcome) -> None:
        self._record("sse_finalization")

    def retry(self, outcome: StreamOutcome) -> NoReturn:
        raise AssertionError("retry forbidden")

    def fallback(self, outcome: StreamOutcome) -> NoReturn:
        raise AssertionError("fallback forbidden")


@pytest.mark.parametrize("kind", list(OutcomeKind))
def test_commit_preserves_outcome_without_retry(kind: OutcomeKind) -> None:
    guard, effects, outcome = Guard(), Effects(), StreamOutcome(kind)
    assert commit_outcome(guard, outcome, effects) is outcome
    assert effects.calls == list(HOOKS)
    assert guard.checks == len(HOOKS)


@pytest.mark.parametrize("index", range(1, 5))
def test_revocation_stops_at_each_boundary(index: int) -> None:
    guard, effects = Guard(fail_at=index), Effects()
    with pytest.raises(LeaseFenced, match="revoked"):
        commit_outcome(guard, StreamOutcome(OutcomeKind.OK), effects)
    assert effects.calls == list(HOOKS[: index - 1])
    assert guard.checks == index


@pytest.mark.parametrize("boundary", HOOKS)
def test_effect_fence_stops_later_effects(boundary: str) -> None:
    guard, effects = Guard(), Effects(fail_at=boundary)
    with pytest.raises(LeaseFenced, match=boundary):
        commit_outcome(guard, StreamOutcome(OutcomeKind.OK), effects)
    assert effects.calls == list(HOOKS[: HOOKS.index(boundary)])


def test_exception_identity() -> None:
    from core.route_penalty_state import LeaseFenced as StoreLeaseFenced

    assert LeaseFenced is StoreLeaseFenced


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
        ("core/passthrough_outcome.py", 120),
        ("tests/test_passthrough_outcome.py", 300),
    ],
)
def test_architecture_caps(relative: str, cap: int) -> None:
    source = (Path(__file__).resolve().parents[1] / relative).read_text()
    assert len(source.splitlines()) <= cap
    nodes = [
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for node in nodes:
        args = node.args
        count = (
            len(args.posonlyargs + args.args + args.kwonlyargs)
            + bool(args.vararg)
            + bool(args.kwarg)
        )
        assert (node.end_lineno or node.lineno) - node.lineno + 1 <= 40, node.name
        assert count <= 5, node.name
        assert _complexity(node) <= 10, node.name
