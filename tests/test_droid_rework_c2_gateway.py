"""Быстрые оракулы перенесённых контрактов и форматированных границ шлюза."""

from __future__ import annotations

from collections.abc import Callable
import io
import queue
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest

import server
from tests.bridge_testlib import make_receipt
from tests.test_request_attribution import route as route
from tools.receipt_schema import validate_model_catalog, validate_receipt_components
from tools import droid_image


def test_receipt_components_accept_complete_qualification() -> None:
    receipt: dict[str, Any] = make_receipt(Path("/fake/image"), "a" * 64)
    validate_receipt_components(receipt)
    server._check_receipt_quad(receipt)


@pytest.mark.parametrize(
    "section,key",
    [
        ("protocol", "api_version"),
        ("protocol", "protocol_version"),
        ("tools_policy", "policy"),
        ("tools_policy", "digest"),
        ("settings_profile", "profile"),
        ("settings_profile", "digest"),
        ("probes", "spawn"),
    ],
)
def test_receipt_components_reject_tampering(section: str, key: str) -> None:
    receipt: dict[str, Any] = make_receipt(Path("/fake/image"), "a" * 64)
    receipt[section][key] = ""
    with pytest.raises(ValueError):
        validate_receipt_components(receipt)
    with pytest.raises(server.LauncherUnavailable):
        server._check_receipt_quad(receipt)


def test_model_catalog_accepts_only_matching_nonempty_list() -> None:
    qualified = {"model": ["Read", "Execute"]}
    validate_model_catalog(qualified, "model", ["Execute", "Read"], server.RpcError)
    for listed in ([], ["Read"], ["unexpected"]):
        with pytest.raises(server.RpcError):
            validate_model_catalog(qualified, "model", listed, server.RpcError)


@pytest.mark.parametrize("state", ["timeout", "droid_error"])
def test_error_body_preserves_reported_message(state: str) -> None:
    out: dict[str, Any] = {"state": state, "err": "reported failure", "timeout_s": 5}
    assert server.Handler._error_body(out)["message"] == "reported failure"
    out["err"] = ""
    assert server.Handler._error_body(out)["message"]


@pytest.mark.parametrize("enabled", [False, True])
def test_subagent_queue_heartbeat_and_optional_callback(
    monkeypatch: pytest.MonkeyPatch, enabled: bool
) -> None:
    slots = Mock()
    slots.acquire.return_value = False
    monkeypatch.setattr(server, "_subagent_slots", slots)
    monkeypatch.setattr(server, "_client_gone", Mock(side_effect=[False, True]))
    monkeypatch.setattr(server.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(server, "SUBAGENT_QUEUE_TIMEOUT_S", 100.0)
    monkeypatch.setattr(server, "KEEPALIVE_S", 1.0)
    handler: Any = SimpleNamespace(_is_subagent_request=lambda: True, connection=None)
    heartbeat = Mock(return_value=False) if enabled else None
    assert server.Handler._acquire_slot(handler, heartbeat) == "client_gone"
    if heartbeat is not None:
        heartbeat.assert_called_once_with()


def test_empty_upstream_mapping_keeps_public_model(
    route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = dict(server.FLEET["models"]["gpt-6.1-terra"], upstream_model="")
    monkeypatch.setitem(server.FLEET["models"], "gpt-6.1-terra", model)
    handler = route({"model": "gpt-6.1-terra"})
    handler._serve_passthrough.assert_called_once()
    assert handler._serve_passthrough.call_args.args[2]["model"] == "gpt-6.1-terra"


@pytest.mark.parametrize("timeout", [None, 0.25])
def test_probe_rpc_timeout_selection(
    monkeypatch: pytest.MonkeyPatch, timeout: float | None
) -> None:
    getter = Mock(return_value=2.75)
    monkeypatch.setattr(droid_image, "_get_probe_timeout_s", getter)
    rpc = object.__new__(droid_image._Rpc)
    rpc.proc = cast(Any, SimpleNamespace(stdin=io.BytesIO()))
    rpc._next = 0
    rpc.inbox = queue.Queue()
    rpc.inbox.put({"id": "p1", "result": {"checked": "ok"}})
    result, notes = rpc.call("test", {}, timeout=timeout)
    assert result == {"checked": "ok"}
    assert notes == []
    assert getter.call_count == (1 if timeout is None else 0)


def execute_case(monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]) -> dict:
    """Вызвать настоящий цикл шлюза с детерминированным временем и готовым terminal."""
    original_time = server.time
    ticks = iter((0.0, 0.0))
    clock = SimpleNamespace(
        monotonic=lambda: next(ticks, options["now"]),
        strftime=original_time.strftime,
        time=original_time.time,
        sleep=lambda _: None,
    )
    monkeypatch.setattr(server, "time", clock)
    monkeypatch.setenv("BRIDGE_ADAPTIVE_WATCHDOG_ENABLED", "false")
    monkeypatch.setattr(server, "FIRST_TOKEN_TIMEOUT_S", 10.0)
    monkeypatch.setattr(server, "_client_gone", lambda _: False)
    handler = object.__new__(server.Handler)
    handler.connection = cast(Any, object())
    handler._effective_safety_cap_s = Mock(return_value=options["safety"])
    handler._effective_idle_timeout_s = Mock(return_value=5.0)
    run = SimpleNamespace(
        got_event=options["got_event"],
        started=0.0,
        last_progress=options["progress"],
        live_invalidated=False,
        err_box=[],
        q=Mock(get=Mock(return_value=("done", (0, "")))),
        proc=None,
    )
    return handler._execute(cast(server.Run, cast(object, run)), lambda: True, False)


@pytest.mark.parametrize(
    "case",
    [
        (15.0, True, 14.0, 10.0, "safety_cap"),
        (15.0, False, None, 100.0, "first_token_timeout"),
        (15.0, True, 14.0, 100.0, "done"),
        (3.0, True, None, 100.0, "done"),
        (3.0, False, None, 100.0, "done"),
    ],
)
def test_execute_deadlines_and_sliding_progress(
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[float, bool, float | None, float, str],
) -> None:
    now, got_event, progress, safety, expected = case
    options = dict(now=now, got_event=got_event, progress=progress, safety=safety)
    assert execute_case(monkeypatch, options)["state"] == expected
