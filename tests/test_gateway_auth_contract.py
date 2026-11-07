"""Перенесённые оракулы авторизации и безопасных умолчаний шлюза."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import server
from tests.test_request_attribution import wire as wire


def test_deepseek_fleet_default_is_off() -> None:
    catalog = server._build_catalog(
        json.loads((server.ROOT / "fleet.json").read_text())
    )
    assert catalog["models"]["deepseek-v4.1-flash"]["default_effort"] == "off"


def test_auth_ok_rejects_patched_module_keys_with_isolated_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Модульные ключи не принимаются; без файла действует только _env."""
    from email.message import Message

    monkeypatch.setattr(server, "AUTH_KEY", "module-auth-key")
    monkeypatch.setattr(server, "BRIDGE_KEY", "module-bridge-key")
    cache = server.TokenCache(
        path=tmp_path / "missing", environ={"BRIDGE_KEY": "cache-key"}
    )
    monkeypatch.setattr(server, "TOKEN_CACHE", cache)
    assert not cache.is_valid("module-auth-key")
    assert not cache.is_valid("module-bridge-key")

    def make_handler(headers: dict[str, str]) -> server.Handler:
        message = Message()
        for name, value in headers.items():
            message[name] = value
        handler = object.__new__(server.Handler)
        handler.headers = message
        return handler

    assert not server._auth_ok(
        make_handler({"Authorization": "Bearer module-auth-key"})
    )
    assert not server._auth_ok(make_handler({"Authorization": "module-bridge-key"}))
    assert not server._auth_ok(make_handler({"x-api-key": "module-auth-key"}))
    assert server._auth_ok(make_handler({"Authorization": "Bearer cache-key"}))
    assert not server._auth_ok(make_handler({"Authorization": "Bearer wrong-key"}))
    assert not server._auth_ok(make_handler({}))


def test_auth_ok_revokes_stale_module_keys_when_file_key_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Файловый ключ исключителен: устаревший модульный ключ через _auth_ok отозван."""
    from email.message import Message

    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=current-file-key\n")
    monkeypatch.setattr(server, "AUTH_KEY", "revoked-global-key")
    monkeypatch.setattr(server, "BRIDGE_KEY", "revoked-global-key")
    cache = server.TokenCache(path=path, environ={})
    monkeypatch.setattr(server, "TOKEN_CACHE", cache)

    def make_handler(token: str) -> server.Handler:
        message = Message()
        message["Authorization"] = f"Bearer {token}"
        handler = object.__new__(server.Handler)
        handler.headers = message
        return handler

    assert server._auth_ok(make_handler("current-file-key"))
    assert not server._auth_ok(make_handler("revoked-global-key"))


def test_effort_alias_keeps_explicit_effort(wire: Any) -> None:
    assert (
        wire.call({"model": "gpt-6.1-terra-high", "reasoning_effort": "low"})[0] == 200
    )
    assert json.loads(wire.records[-1][1])["reasoning_effort"] == "low"
