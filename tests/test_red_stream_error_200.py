"""C0-2 / VER-004,005,007: RED-контракты исходов, probe и fencing.

Будущие швы: StreamOutcomeClassifier.feed/finish, build_half_open_probe(call,
lease), passthrough_outcome.commit_outcome(lease, outcome, effects).
Импорты отложены до теста: отсутствие реализации — FAIL, не ошибка collection.
"""

from __future__ import annotations

import ast
import importlib
import json
import socket
import sys
import time
from collections.abc import Iterator
from email.message import Message
from io import BytesIO
from pathlib import Path
from random import Random
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
SSE = "text/event-stream"
JSON = "application/json"
DONE = b"data: [DONE]\r\n\r\n"


def _frame(value: dict[str, Any]) -> bytes:
    return b"data: " + json.dumps(value, ensure_ascii=False).encode() + b"\r\n\r\n"


def _completion(text: str) -> bytes:
    return _frame({"choices": [{"delta": {"content": text}, "finish_reason": "stop"}]})


CASES = [
    (SSE, _frame({"error": {"message": "upstream failed"}}) + DONE, False, "STREAM_ERROR"),
    (SSE, b"event: error\r\ndata: {\"message\":\"failed\"}\r\n\r\n" + DONE, False, "STREAM_ERROR"),
    (SSE, _completion("Quota exceeded: лимит \u263a") + DONE, False, "QUOTA_TEXT"),
    (SSE, _completion("") + DONE, False, "EMPTY"),
    (SSE, b"", False, "EMPTY"),
    (SSE, _completion("часть"), False, "STREAM_ERROR"),
    (SSE, b'data: {"choices":[{"delta":{"content":"partial', False, "STREAM_ERROR"),
    (SSE, _completion("успех") + DONE, True, "CLIENT_ABORT"),
    (JSON, b'{"error":{"message":"failed","type":"server_error"}}', False, "ERROR_BODY"),
    (JSON, b'{"choices":[{"message":{"content":"quota exceeded"},"finish_reason":"stop"}]}', False, "QUOTA_TEXT"),
    (JSON, b'{"choices":[{"message":{"content":""},"finish_reason":"stop"}]}', False, "EMPTY"),
    (JSON, b"", False, "EMPTY"),
    (JSON, b'{"choices":[{"message":{"content":"partial', False, "ERROR_BODY"),
    (JSON, b'{"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}]}', True, "CLIENT_ABORT"),
    ("text/plain", b"quota exceeded", False, "QUOTA_TEXT"),
]


def _forbidden(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("L1 forbids real sockets and sleep")


@pytest.fixture(autouse=True)
def no_network_or_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(time, "sleep", _forbidden)


def _chunks(body: bytes, width: int) -> Iterator[bytes]:
    random = Random(507)
    offset = 0
    while offset < len(body):
        size = width if width else random.randint(1, 13)
        yield body[offset:offset + size]
        offset += size


def _classify(case: tuple[str, bytes, bool, str], width: int) -> str:
    module = importlib.import_module("core.stream_outcome")
    content_type, body, aborted, _ = case
    classifier = module.StreamOutcomeClassifier(status=200, content_type=content_type)
    for chunk in _chunks(body, width):
        classifier.feed(chunk)
    return classifier.finish(client_aborted=aborted).kind.name


@pytest.mark.parametrize("case", CASES)
def test_http_200_error_outcome_is_chunk_invariant(case: tuple[str, bytes, bool, str]) -> None:
    """VER-005/007: целое, 1/7 байт и seeded-разбиение дают один НЕ-OK."""
    results = [_classify(case, width) for width in (max(1, len(case[1])), 1, 7, 0)]
    assert results == [case[3]] * 4
    assert "OK" not in results


@pytest.mark.parametrize("width", [1, 7, 0])
def test_complete_useful_sse_is_ok(width: int) -> None:
    """Положительный контроль не позволяет классификатору отвергать всё."""
    case = (SSE, _completion('Ответ 😀: "да"\\нет') + DONE, False, "OK")
    assert _classify(case, width) == "OK"


def _probe_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.keyword):
        return node.arg == "is_probe" and isinstance(node.value, ast.Constant) and node.value.value is True
    if isinstance(node, ast.Dict):
        return any(_probe_literal(ast.keyword(arg=key.value, value=value))
                   for key, value in zip(node.keys, node.values)
                   if isinstance(key, ast.Constant) and key.value == "is_probe")
    return False


def test_probe_true_is_constructed_only_in_facade() -> None:
    root = Path(__file__).resolve().parents[1]
    owners: set[str] = set()
    for path in (root / "core").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(_probe_literal(node) for node in ast.walk(tree)):
            owners.add(path.relative_to(root).as_posix())
    assert owners == {"core/passthrough_facade.py"}


class Recorder:
    def __init__(self, result: Any = None) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.result = result

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return self.result


def _handler(body: dict[str, Any]) -> Any:
    raw = json.dumps(body).encode()
    headers = Message()
    headers["Content-Length"] = str(len(raw))
    headers["Authorization"] = "Bearer synthetic-l1"
    return SimpleNamespace(
        path="/v1/chat/completions", headers=headers, rfile=BytesIO(raw),
        wfile=BytesIO(), connection=SimpleNamespace(close=Recorder()),
        _headers_already_sent=False, close_connection=False, _reject=Recorder(),
        _reply_error=Recorder(), _send=Recorder(), _response_status=0,
    )


def _post_seam(monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]) -> Any:
    facade = importlib.import_module("core.passthrough_facade")
    handler = _handler(body)
    host = SimpleNamespace(_auth_ok=lambda _: True)
    context = SimpleNamespace(handler=handler, host=host, request=body, raw=json.dumps(body).encode())
    route = SimpleNamespace(handler=handler, host=host, request=body)
    dispatch, cleanup, resolve = Recorder(), Recorder(), Recorder(route)
    monkeypatch.setattr(facade, "begin_post", lambda *_: context)
    monkeypatch.setattr(facade, "read_post_request", lambda _: True)
    monkeypatch.setattr(facade, "resolve_post_route", resolve)
    monkeypatch.setattr(facade, "_dispatch", dispatch)
    monkeypatch.setattr(facade, "_cleanup_post", cleanup)
    return SimpleNamespace(facade=facade, handler=handler, host=host,
                           dispatch=dispatch, cleanup=cleanup, resolve=resolve)


@pytest.mark.parametrize("value", [True, False, None, ""])
def test_external_probe_body_presence_rejected(monkeypatch: pytest.MonkeyPatch, value: Any) -> None:
    seam = _post_seam(monkeypatch, {"model": "test", "is_probe": value})
    seam.facade.handle_post(seam.handler, seam.host)
    assert seam.handler._reject.calls, "probe body reached routing without HTTP 400"
    assert seam.handler._reject.calls[0][0][:2] == (400, "invalid_request_error")
    assert not seam.resolve.calls
    assert not seam.dispatch.calls


@pytest.mark.parametrize("header", ["X-Probe", "x-pRoBe", "X-Bridge-Probe", "x-bridge-probe"])
@pytest.mark.parametrize("value", ["", "false"])
def test_external_probe_headers_rejected(monkeypatch: pytest.MonkeyPatch, header: str, value: str) -> None:
    seam = _post_seam(monkeypatch, {"model": "test"})
    seam.handler.headers[header] = value
    seam.facade.handle_post(seam.handler, seam.host)
    assert seam.handler._reject.calls, "probe header reached routing without HTTP 400"
    assert seam.handler._reject.calls[0][0][:2] == (400, "invalid_request_error")
    assert not seam.resolve.calls
    assert not seam.dispatch.calls


def _user_call(facade: Any) -> Any:
    body = {"model": "test", "messages": [{"role": "user", "content": "private user turn"}],
            "tools": [{"type": "function", "function": {"name": "write"}}]}
    return facade.PassthroughCall(adapter=None, raw=json.dumps(body).encode(),
                                  request=body, model_id="test")


def test_internal_probe_key_is_deterministic_and_never_inherited(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-007: probe — отдельный PONG, реальный POST остаётся нетронутым."""
    facade = importlib.import_module("core.passthrough_facade")
    user = _user_call(facade)
    original = user.raw
    lease = SimpleNamespace(edge_key="test:backend", lease_epoch=7, lease_token="l1-token")
    probe = facade.build_half_open_probe(user, lease)
    again = facade.build_half_open_probe(user, lease)
    assert probe.is_probe is True
    assert probe.idempotency_key == again.idempotency_key == "ho:test:backend:7:l1-token"
    assert probe.request["tools"] == []
    assert "PONG" in json.dumps(probe.request["messages"])
    assert b"private user turn" not in probe.raw
    assert json.loads(probe.raw) == probe.request
    seam = _post_seam(monkeypatch, user.request)
    seam.facade.handle_post(seam.handler, seam.host)
    sent = seam.dispatch.calls[0][0][0].request
    real = facade.PassthroughCall(adapter=None, raw=json.dumps(sent).encode(), request=sent, model_id="test")
    assert (real.is_probe, real.idempotency_key) == (False, None)
    assert real.raw == user.raw == original
    assert json.loads(original) == user.request


@pytest.mark.parametrize("headers_sent", [False, True])
def test_lease_fenced_is_terminal_at_http_boundary(monkeypatch: pytest.MonkeyPatch, headers_sent: bool) -> None:
    outcome = importlib.import_module("core.passthrough_outcome")
    seam = _post_seam(monkeypatch, {"model": "test"})
    seam.handler._headers_already_sent = headers_sent
    raised: list[str] = []

    def fenced(_: Any) -> None:
        raised.append("dispatch")
        raise outcome.LeaseFenced("stale lease")

    monkeypatch.setattr(seam.facade, "_dispatch", fenced)
    seam.facade.handle_post(seam.handler, seam.host)
    assert raised == ["dispatch"]
    if headers_sent:
        wire = seam.handler.wfile.getvalue()
        assert b"error" in wire
        assert b"[DONE]" not in wire
        assert seam.handler.close_connection
        assert not seam.handler._reject.calls
    else:
        assert seam.handler._reject.calls[0][0][0] == 503


@pytest.mark.parametrize("boundary", ["fsm", "penalty", "tool_result", "sse_finalization"])
def test_fence_prevents_all_outcome_effects(boundary: str) -> None:
    """VER-004: потеря токена до commit запрещает каждый побочный эффект."""
    outcome = importlib.import_module("core.passthrough_outcome")
    effects = SimpleNamespace(**{name: Recorder() for name in
                                ("fsm", "penalty", "tool_result", "sse_finalization", "retry", "fallback")})

    def check_current(*args: Any, **kwargs: Any) -> None:
        raise outcome.LeaseFenced(f"stale lease before {boundary}")

    lease = SimpleNamespace(check_current=check_current)
    with pytest.raises(outcome.LeaseFenced, match="stale lease"):
        outcome.commit_outcome(lease, SimpleNamespace(kind="OK", boundary=boundary), effects)
    assert all(not recorder.calls for recorder in vars(effects).values())


class UnknownPostPorts:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.sent: list[str] = []
        self.retry_token = Recorder(True)
        self.lease = SimpleNamespace(finish=Recorder(), close=Recorder())

    def cancelled(self) -> bool:
        return False

    def ready(self, backend: str) -> bool:
        return True

    def acquire(self, backend: str, remaining_deadline_s: float) -> Any:
        return self.lease

    def execute(self, backend: str, attempt: Any) -> Any:
        module = importlib.import_module("core.route_attempts")
        attempt.advance(module.AttemptPhase.SENDING)
        self.sent.append(backend)
        raise self.error


@pytest.mark.parametrize("error_type", [TimeoutError, ConnectionError, RuntimeError])
def test_unknown_user_post_outcome_never_retries_or_falls_back(error_type: type[Exception]) -> None:
    module = importlib.import_module("core.route_attempts")
    policy = importlib.import_module("core.route_health_policy")
    ports = UnknownPostPorts(error_type("unknown user POST outcome"))
    runner = module.RouteAttemptRunner(("primary", "fallback"), ports, policy.RetryBudgetConfig(), lambda: 0.0)
    with pytest.raises(error_type, match="unknown user POST outcome"):
        runner.run()
    assert ports.sent == ["primary"]
    assert not ports.retry_token.calls
    assert len(ports.lease.close.calls) == 1
