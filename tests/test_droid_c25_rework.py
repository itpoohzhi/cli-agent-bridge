"""Регрессии реворка Cycle 25: F-001, F-002, F-013, F-015, F-019 на границах шлюза."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import Mock

import pytest

import server
from tests.bridge_testlib import droidify_raw_fleet, load_raw_fleet
from tests.rpc_testlib import RpcCase
from tests.test_request_attribution import route as route


def _install_droid_stand(monkeypatch: pytest.MonkeyPatch) -> None:
    """Прод-`fleet.json` держит `droid=false`: политика проверяется на стендовом каталоге."""
    catalog = server._build_catalog(droidify_raw_fleet(load_raw_fleet()))
    monkeypatch.setattr(server, "FLEET", catalog)
    monkeypatch.setattr(
        server,
        "BACKENDS",
        server.AdapterRegistry.from_fleet(
            catalog, server.ADAPTER_KINDS, lambda: server.FLEET, server
        ),
    )


@pytest.fixture
def cli_route(
    monkeypatch: pytest.MonkeyPatch, route: Callable[..., Any]
) -> Callable[..., Any]:
    _install_droid_stand(monkeypatch)
    for backend in ("droid", "muse"):
        adapter = server.BACKENDS.get(backend)
        if adapter is not None:
            monkeypatch.setattr(adapter, "preflight", lambda: (True, ""))
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


JUDGE_DENY_ENV = "panel-judge-,judge-,seat-"


def _assert_forbidden_for_role(handler: Any) -> None:
    assert handler._send.call_args.args[0] == 403
    assert (
        handler._send.call_args.args[1]["error"]["type"] == "droid_forbidden_for_role"
    )
    handler._serve_json.assert_not_called()


def _assert_served(handler: Any) -> None:
    handler._send.assert_not_called()
    handler._serve_json.assert_called_once()


def _assert_autonomy_role_forbidden(handler: Any) -> None:
    assert handler._send.call_args.args[0] == 400
    assert handler._send.call_args.args[1]["error"]["type"] == "autonomy_role_forbidden"
    handler._serve_json.assert_not_called()


@pytest.mark.parametrize("autonomy", [None, "off"])
def test_judge_read_only_passes_through_body(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, autonomy: str | None
) -> None:
    """AD-001: судья с subagent_id из тела и без мутации допускается к droid-маршруту."""
    monkeypatch.delenv("DROID_DENY_SUBAGENT_PREFIXES", raising=False)
    body: dict[str, Any] = {
        "model": "gpt-6.1-sol-droid",
        "subagent_id": "judge-1",
        "messages": [{"role": "user", "content": "hello"}],
    }
    if autonomy is not None:
        body["autonomy"] = autonomy
    _assert_served(cli_route(body, {}))


@pytest.mark.parametrize("role", ["judge-1", "panel-judge-k1", "seat-3"])
@pytest.mark.parametrize("autonomy", [None, "off"])
def test_judge_read_only_passes_with_role_header(
    cli_route: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    autonomy: str | None,
) -> None:
    """AD-001: все судейские префиксы в заголовке роли допускаются при autonomy off."""
    monkeypatch.delenv("DROID_DENY_SUBAGENT_PREFIXES", raising=False)
    body: dict[str, Any] = {
        "model": "gpt-6.1-sol-droid",
        "messages": [{"role": "user", "content": "hello"}],
    }
    if autonomy is not None:
        body["autonomy"] = autonomy
    _assert_served(cli_route(body, {"X-Subagent-Id": role}))


def test_judge_read_only_passes_through_renamed_header(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-001: переименованный SUBAGENT_ID_HEADER тоже не отвергает read-only судью."""
    monkeypatch.delenv("DROID_DENY_SUBAGENT_PREFIXES", raising=False)
    monkeypatch.setattr(server, "SUBAGENT_ID_HEADER", "X-Role-Id")
    handler = cli_route(
        {
            "model": "gpt-6.1-sol-droid",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {"X-Role-Id": "judge-1"},
    )
    _assert_served(handler)


def test_judge_read_only_passes_with_disabled_attribution(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-001: при выключенной атрибуции судья с autonomy off по-прежнему допускается."""
    monkeypatch.delenv("DROID_DENY_SUBAGENT_PREFIXES", raising=False)
    monkeypatch.setattr(server, "REQUEST_ATTRIBUTION_ENABLED", False)
    handler = cli_route(
        {
            "model": "gpt-6.1-sol-droid",
            "subagent_id": "judge-1",
            "autonomy": "off",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {},
    )
    _assert_served(handler)


@pytest.mark.parametrize("role", ["judge-1", "panel-judge-k1", "seat-3"])
@pytest.mark.parametrize("autonomy", ["low", "medium", "high"])
def test_judge_mutating_autonomy_is_rejected(
    cli_route: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    autonomy: str,
) -> None:
    """AD-001: судья с мутирующей автономностью получает 400 autonomy_role_forbidden."""
    monkeypatch.delenv("DROID_DENY_SUBAGENT_PREFIXES", raising=False)
    handler = cli_route(
        {
            "model": "gpt-6.1-sol-droid",
            "autonomy": autonomy,
            "messages": [{"role": "user", "content": "hello"}],
        },
        {"X-Subagent-Id": role},
    )
    _assert_autonomy_role_forbidden(handler)


@pytest.mark.parametrize("autonomy", ["low", "medium"])
def test_judge_mutating_autonomy_is_rejected_for_body_only_role(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, autonomy: str
) -> None:
    """AD-001: роль только в теле не даёт судье обойти запрет мутирующей автономности."""
    monkeypatch.delenv("DROID_DENY_SUBAGENT_PREFIXES", raising=False)
    handler = cli_route(
        {
            "model": "gpt-6.1-sol-droid",
            "subagent_id": "judge-1",
            "autonomy": autonomy,
            "messages": [{"role": "user", "content": "hello"}],
        },
        {},
    )
    _assert_autonomy_role_forbidden(handler)


def test_judge_mutating_autonomy_is_rejected_with_opt_in_high(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-001: opt-in на high уровня шлюза не снимает запрет мутации для судьи."""
    monkeypatch.setenv("DROID_ALLOW_HIGH_AUTONOMY", "1")
    monkeypatch.setenv("DROID_MUTATING_SUBAGENT_PREFIXES", "judge-,coder-")
    handler = cli_route(
        {
            "model": "gpt-6.1-sol-droid",
            "autonomy": "high",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {"X-Subagent-Id": "judge-1"},
    )
    _assert_autonomy_role_forbidden(handler)


def test_judge_explicit_deny_env_still_blocks_through_body(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-002: явный DROID_DENY_SUBAGENT_PREFIXES по-прежнему видит subagent_id из тела."""
    monkeypatch.setenv("DROID_DENY_SUBAGENT_PREFIXES", JUDGE_DENY_ENV)
    handler = cli_route(
        {
            "model": "gpt-6.1-sol-droid",
            "subagent_id": "judge-1",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {},
    )
    _assert_forbidden_for_role(handler)


def test_judge_explicit_deny_env_still_blocks_renamed_header(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-002: явный запрет видит и переименованный SUBAGENT_ID_HEADER."""
    monkeypatch.setenv("DROID_DENY_SUBAGENT_PREFIXES", JUDGE_DENY_ENV)
    monkeypatch.setattr(server, "SUBAGENT_ID_HEADER", "X-Role-Id")
    handler = cli_route(
        {
            "model": "gpt-6.1-sol-droid",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {"X-Role-Id": "judge-1"},
    )
    _assert_forbidden_for_role(handler)


def test_mutating_http_rejects_missing_role_despite_library_opt_out(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-013: HTTP-граница требует роль даже при DROID_REQUIRE_SUBAGENT_FOR_MUTATION=0."""
    monkeypatch.setenv("DROID_REQUIRE_SUBAGENT_FOR_MUTATION", "0")
    monkeypatch.setenv("DROID_MUTATING_SUBAGENT_PREFIXES", "coder-")
    handler = cli_route(
        {
            "model": "gpt-6.1-sol-droid",
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


def test_judge_explicit_deny_env_survives_disabled_attribution(
    cli_route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-002: при выключенной атрибуции явный запрет судьям читает тело запроса."""
    monkeypatch.setenv("DROID_DENY_SUBAGENT_PREFIXES", JUDGE_DENY_ENV)
    monkeypatch.setattr(server, "REQUEST_ATTRIBUTION_ENABLED", False)
    handler = cli_route(
        {
            "model": "gpt-6.1-sol-droid",
            "subagent_id": "judge-1",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {},
    )
    _assert_forbidden_for_role(handler)


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
