"""Регрессии реворка Cycle 25: F-001, F-002, F-013, F-015, F-019 на границах шлюза."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import Mock

import pytest

import server
from tests.rpc_testlib import RpcCase
from tests.test_request_attribution import route as route


@pytest.fixture
def cli_route(
    monkeypatch: pytest.MonkeyPatch, route: Callable[..., Any]
) -> Callable[..., Any]:
    for backend in ("droid", "muse"):
        monkeypatch.setattr(
            server.BACKENDS.get(backend), "preflight", lambda: (True, "")
        )
    monkeypatch.setattr(server.Handler, "_serve_json", Mock())
    monkeypatch.setattr(server.Handler, "_prompt_guard", lambda *_: (0, "-", 0))
    monkeypatch.setattr(server.Handler, "_context_gate", lambda _, req, *a: (req, None))
    monkeypatch.setattr(server, "_is_detached_enabled", lambda: False)
    monkeypatch.delenv("DROID_ALLOW_HIGH_AUTONOMY", raising=False)
    monkeypatch.delenv("DROID_MUTATING_SUBAGENT_PREFIXES", raising=False)
    return route


@pytest.fixture
def rpc_case() -> Iterator[Any]:
    case = RpcCase()
    case.setUp()
    try:
        yield case
    finally:
        case.tearDown()
        case.doCleanups()


# --- Cycle 25 (Council C24): F-001, F-002, F-013, F-015, F-019 --------------------


@pytest.mark.parametrize("autonomy", [5, {"level": "high"}, "ultra", ["low"]])
def test_non_droid_autonomy_format_is_rejected(
    cli_route: Callable[..., Any], autonomy: Any
) -> None:
    """F-001: прежний формат-контракт не-Droid моделей возвращает 400."""
    handler = cli_route(
        {
            "model": "muse-wonder-full-1.0",
            "autonomy": autonomy,
            "messages": [{"role": "user", "content": "hello"}],
        },
        {},
    )
    assert handler._send.call_args.args[0] == 400
    assert handler._send.call_args.args[1]["error"]["type"] == "unsupported_autonomy"
    handler._serve_json.assert_not_called()


@pytest.mark.parametrize("autonomy", ["off", "low", "medium", "high"])
def test_non_droid_autonomy_keeps_passing_through(
    cli_route: Callable[..., Any], autonomy: str
) -> None:
    """F-001: валидные уровни не-Droid модели по-прежнему уходят в контекст."""
    handler = cli_route(
        {
            "model": "muse-wonder-full-1.0",
            "autonomy": autonomy,
            "messages": [{"role": "user", "content": "hello"}],
        },
        {},
    )
    handler._send.assert_not_called()
    assert handler._serve_json.call_args.args[0]["autonomy"] == autonomy


def test_judge_cannot_bypass_deny_through_body(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-002: запрет судьям видит subagent_id из тела запроса."""
    monkeypatch.delenv("DROID_DENY_SUBAGENT_PREFIXES", raising=False)
    handler = cli_route(
        {
            "model": "gpt-6.1-sol",
            "subagent_id": "judge-1",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {},
    )
    assert handler._send.call_args.args[0] == 403
    assert (
        handler._send.call_args.args[1]["error"]["type"] == "droid_forbidden_for_role"
    )
    handler._serve_json.assert_not_called()


def test_judge_cannot_bypass_deny_through_renamed_header(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-002: переименованный SUBAGENT_ID_HEADER тоже попадает под запрет."""
    monkeypatch.delenv("DROID_DENY_SUBAGENT_PREFIXES", raising=False)
    monkeypatch.setattr(server, "SUBAGENT_ID_HEADER", "X-Role-Id")
    handler = cli_route(
        {"model": "gpt-6.1-sol", "messages": [{"role": "user", "content": "hello"}]},
        {"X-Role-Id": "judge-1"},
    )
    assert handler._send.call_args.args[0] == 403
    assert (
        handler._send.call_args.args[1]["error"]["type"] == "droid_forbidden_for_role"
    )
    handler._serve_json.assert_not_called()


def test_mutating_http_rejects_missing_role_despite_library_opt_out(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-013: HTTP-граница требует роль даже при DROID_REQUIRE_SUBAGENT_FOR_MUTATION=0."""
    monkeypatch.setenv("DROID_REQUIRE_SUBAGENT_FOR_MUTATION", "0")
    monkeypatch.setenv("DROID_MUTATING_SUBAGENT_PREFIXES", "coder-")
    handler = cli_route(
        {
            "model": "gpt-6.1-sol",
            "autonomy": "low",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {},
    )
    assert handler._send.call_args.args[0] == 400
    assert handler._send.call_args.args[1]["error"]["type"] == "autonomy_role_forbidden"
    handler._serve_json.assert_not_called()


def test_judge_role_does_not_block_non_droid_backend(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-002: запрет судьям действует только для backend=droid, Muse не блокируется."""
    monkeypatch.setattr(server, "REQUEST_ATTRIBUTION_ENABLED", False)
    handler = cli_route(
        {
            "model": "muse-wonder-full-1.0",
            "subagent_id": "judge-1",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {"X-Subagent-Id": "panel-judge-k1"},
    )
    handler._send.assert_not_called()
    handler._serve_json.assert_called_once()


def test_judge_deny_survives_disabled_attribution(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-002: при выключенной атрибуции запрет судьям всё равно читает тело запроса."""
    monkeypatch.delenv("DROID_DENY_SUBAGENT_PREFIXES", raising=False)
    monkeypatch.setattr(server, "REQUEST_ATTRIBUTION_ENABLED", False)
    handler = cli_route(
        {
            "model": "gpt-6.1-sol",
            "subagent_id": "judge-1",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {},
    )
    assert handler._send.call_args.args[0] == 403
    assert (
        handler._send.call_args.args[1]["error"]["type"] == "droid_forbidden_for_role"
    )
    handler._serve_json.assert_not_called()


def test_wire_enforces_coder_role_despite_library_opt_out(
    rpc_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-013: env opt-out библиотеки не отключает HTTP-проверку роли."""
    monkeypatch.setenv("DROID_REQUIRE_SUBAGENT_FOR_MUTATION", "0")
    monkeypatch.setenv("DROID_MUTATING_SUBAGENT_PREFIXES", "coder-")
    status, body = rpc_case._post_json(
        {
            "model": "gpt-6.1-sol",
            "autonomy": "low",
            "messages": [{"role": "user", "content": "hello"}],
        }
    )
    assert status == 400, body
    assert body["error"]["type"] == "autonomy_role_forbidden"
    assert not rpc_case.hub.spawns()


def test_wire_default_request_uses_off_autonomy(
    rpc_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-015: обычный запрос без autonomy и роли проходит, дефолт пишется в журнал."""
    monkeypatch.delenv("DROID_DEFAULT_AUTONOMY", raising=False)
    monkeypatch.delenv("DROID_ALLOW_HIGH_AUTONOMY", raising=False)
    with rpc_case.capture_logs() as logs:
        status, body = rpc_case._post_json(
            {
                "model": "gpt-6.1-sol",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )
    assert status == 200, body
    assert any("autonomy=off autonomy_source=default" in line for line in logs), logs
    assert rpc_case.hub.inits()[0]["params"]["autonomyLevel"] == "off"


def test_receipt_level_evidence_stays_internal(rpc_case: Any) -> None:
    """F-019: поуровневая квалификация не расширяет публичный HTTP-контракт."""
    health = rpc_case.health()
    assert "qualified_targets" not in health
    assert sorted(health) == [
        "active",
        "max_concurrent",
        "model",
        "ok",
        "tool_emulation",
        "transport",
        "uptime_s",
    ]
    status, models = rpc_case._get("/v1/models")
    assert status == 200
    assert "qualified_targets" not in json.dumps(models)
