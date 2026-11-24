"""Регрессионные тесты HTTP 503 и Retry-After для overloaded в agy-bridge (SSE и JSON)."""

from __future__ import annotations

import io
import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_AGY_DIR = str(_ROOT / "bridges/agy-bridge")
if _AGY_DIR not in sys.path:
    sys.path.append(_AGY_DIR)

try:
    from resilience_wiring_support import load_server
except ImportError:
    from tests.resilience_wiring_support import load_server

from agy_runtime.sse_body_runner import _SseBodyRunner  # noqa: E402
from agy_runtime.sse_stream_helpers import SseStreamSession  # noqa: E402
from core.adaptive_admission import AdmissionDecision, AdmissionKey  # noqa: E402
from core.stream_resilience_runtime import StreamResilienceConfig  # noqa: E402


class _RecordingSseHandler:
    def __init__(self, *, two_arg_send: bool = False) -> None:
        self.client_address = ("127.0.0.1", 5555)
        self.close_connection = False
        self.wfile = None
        self.sent: list[tuple[int, dict[str, Any], dict[str, str] | None]] = []
        if two_arg_send:
            self._send = self._send_two_arg  # type: ignore[method-assign]

    def _send(
        self,
        code: int,
        payload: dict[str, Any],
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.sent.append((code, payload, extra_headers))

    def _send_two_arg(self, code: int, payload: dict[str, Any]) -> None:
        self.sent.append((code, payload, None))

    def _error_body(
        self, out: dict[str, Any], _resilience: bool
    ) -> dict[str, Any] | None:
        st = out.get("state")
        if st == "overloaded":
            return {
                "message": str(out.get("err") or "bridge busy: admission shed"),
                "type": "overloaded",
                "code": 503,
            }
        if st == "queue_timeout":
            return {
                "message": "bridge busy: queue full",
                "type": "overloaded",
                "code": 503,
            }
        if st == "agy_error":
            return {
                "message": str(out.get("err") or "agy error"),
                "type": "agy_error",
                "code": 502,
            }
        return None


def _make_runner(handler: _RecordingSseHandler) -> _SseBodyRunner:
    hooks = (lambda _k, d=False: d, lambda _m: None, lambda: "stop", None)
    ctx: dict[str, Any] = {
        "model": "gemini-4-hydrogen-high",
        "resilience_config": StreamResilienceConfig(),
    }
    session = SseStreamSession(handler, ctx, hooks)
    return _SseBodyRunner(session)


@dataclass
class _ShedRuntime:
    retry_after_s: float = 1.25

    def acquire(
        self, key: AdmissionKey, config_path: Path | None = None
    ) -> AdmissionDecision:
        _ = config_path
        return AdmissionDecision(
            admitted=False,
            ticket_id=0,
            status_code=503,
            retry_after_s=self.retry_after_s,
            reason="child_limit",
            bucket_key=key,
        )


def _new_real_handler(
    server: ModuleType,
) -> tuple[Any, list[int], list[tuple[str, str]], io.BytesIO]:
    handler_cls = cast(type[Any], getattr(server, "Handler"))
    handler = object.__new__(handler_cls)
    statuses: list[int] = []
    headers: list[tuple[str, str]] = []
    body = io.BytesIO()
    handler._registry_job = None
    handler._pending_response_headers = None
    handler.close_connection = False
    handler.client_address = ("127.0.0.1", 5555)
    handler.wfile = body
    handler.send_response = lambda code: statuses.append(code)
    handler.send_header = lambda k, v: headers.append((k, v))
    handler.end_headers = lambda: None
    handler._log_reject = lambda *_a: None
    handler._log_done = lambda *_a: None
    return handler, statuses, headers, body


def test_sse_precommit_overloaded_returns_503_and_retry_after() -> None:
    handler = _RecordingSseHandler()
    runner = _make_runner(handler)
    out = {
        "state": "overloaded",
        "rc": 1,
        "err": "adaptive admission shed",
        "retry_after_s": 1.2,
    }
    runner.finish(out)
    assert len(handler.sent) == 1
    code, payload, extra = handler.sent[0]
    assert code == 503
    assert payload == {
        "error": {
            "message": "adaptive admission shed",
            "type": "overloaded",
            "code": 503,
        }
    }
    assert extra == {"Retry-After": "2"}
    assert handler.close_connection is True


def test_sse_precommit_queue_timeout_returns_503_with_two_arg_send_compat() -> None:
    handler = _RecordingSseHandler(two_arg_send=True)
    runner = _make_runner(handler)
    runner.finish({"state": "queue_timeout", "rc": 1, "err": ""})
    assert len(handler.sent) == 1
    code, payload, extra = handler.sent[0]
    assert code == 503
    assert payload["error"]["type"] == "overloaded"
    assert extra is None


def test_sse_precommit_agy_error_stays_502_without_retry_after() -> None:
    handler = _RecordingSseHandler(two_arg_send=True)
    runner = _make_runner(handler)
    runner.finish(
        {"state": "agy_error", "rc": 1, "err": "upstream boom", "retry_after_s": 5.0}
    )
    assert len(handler.sent) == 1
    code, payload, extra = handler.sent[0]
    assert code == 502
    assert payload["error"]["type"] == "agy_error"
    assert extra is None


@pytest.mark.parametrize("bad_code", [None, 0, 502])
def test_sse_precommit_overloaded_forces_503_even_without_code_or_with_502(
    bad_code: int | None,
) -> None:
    handler = _RecordingSseHandler()
    err_dict: dict[str, Any] = {"message": "busy", "type": "overloaded"}
    if bad_code is not None:
        err_dict["code"] = bad_code
    handler._error_body = lambda _out, _res: dict(err_dict)  # type: ignore[method-assign]
    runner = _make_runner(handler)
    runner.finish({"state": "overloaded", "rc": 1, "err": "busy", "retry_after_s": 1.0})
    assert len(handler.sent) == 1
    code, _, extra = handler.sent[0]
    assert code == 503
    assert extra == {"Retry-After": "1"}


@pytest.mark.parametrize(
    ("raw_retry", "expected"),
    [
        (0.001, {"Retry-After": "1"}),
        (1.0, {"Retry-After": "1"}),
        (1.01, {"Retry-After": "2"}),
        (2.5, {"Retry-After": "3"}),
        (999999.0, {"Retry-After": "86400"}),
        (0.0, None),
        (-3.0, None),
        (math.nan, None),
        (math.inf, None),
        (True, None),
        ("5", None),
        (None, None),
    ],
)
def test_sse_overloaded_retry_after_edges(
    raw_retry: object, expected: dict[str, str] | None
) -> None:
    handler = _RecordingSseHandler()
    runner = _make_runner(handler)
    out: dict[str, Any] = {
        "state": "overloaded",
        "rc": 1,
        "err": "adaptive admission shed",
    }
    if raw_retry is not None:
        out["retry_after_s"] = raw_retry
    runner.finish(out)
    assert len(handler.sent) == 1
    code, _, extra = handler.sent[0]
    assert code == 503
    assert extra == expected


def test_real_handler_sse_and_json_shed_emit_503_and_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = load_server()
    monkeypatch.setattr(server, "_HYGIENE_RT", _ShedRuntime(retry_after_s=2.1))
    handler, statuses, headers, body = _new_real_handler(server)
    ctx_base: dict[str, Any] = {
        "model": "gemini-4-hydrogen-high",
        "effort": "high",
        "tag": "t-shed",
        "model_len": 22,
    }
    out = cast(
        "dict[str, Any]",
        cast(Callable[..., object], getattr(handler, "_run_once_impl"))(
            dict(ctx_base),
            lambda _v: True,
            lambda _v: True,
            lambda _v: True,
            lambda: True,
        ),
    )
    assert out["state"] == "overloaded"
    assert out["retry_after_s"] == pytest.approx(2.1)

    # SSE pre-commit path через настоящий Handler._send
    hooks = (lambda _k, d=False: d, lambda _m: None, lambda: "stop", None)
    sse_ctx: dict[str, Any] = {
        "model": "gemini-4-hydrogen-high",
        "resilience_config": StreamResilienceConfig(),
    }
    runner = _SseBodyRunner(SseStreamSession(handler, sse_ctx, hooks))
    runner.finish(out)
    assert statuses == [503]
    assert ("Retry-After", "3") in headers
    assert json.loads(body.getvalue().decode("utf-8"))["error"]["type"] == "overloaded"

    # JSON path через настоящий Handler._serve_json_body -> Handler._send
    handler2, statuses2, headers2, body2 = _new_real_handler(server)
    handler2._run_once = lambda *_a, **_kw: dict(out)
    json_ctx: dict[str, Any] = {
        "model": "gemini-4-hydrogen-high",
        "emulate_tools": False,
        "stream_resilience_enabled": True,
        "tools": [],
    }
    cast(Callable[..., object], getattr(handler2, "_serve_json_body"))(json_ctx)
    assert statuses2 == [503]
    assert ("Retry-After", "3") in headers2
    assert json.loads(body2.getvalue().decode("utf-8"))["error"]["code"] == 503

    # JSON path при обычной ошибке без Retry-After совместим с 2-аргументным _send
    handler3, _, _, _ = _new_real_handler(server)
    sent3: list[tuple[int, dict[str, Any]]] = []
    handler3._run_once = lambda *_a, **_kw: {
        "state": "agy_error",
        "rc": 1,
        "err": "boom",
    }
    handler3._send = lambda code, payload: sent3.append((code, payload))
    cast(Callable[..., object], getattr(handler3, "_serve_json_body"))(dict(json_ctx))
    assert len(sent3) == 1 and sent3[0][0] == 502
