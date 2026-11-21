"""Граница X-Review-Profile: локальные суб-мосты получают, внешние и /sg-* — нет."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
if str(_Path(__file__).resolve().parents[1]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

import pytest

from core import fallback_http_hook, passthrough_exchange as exchange
from core.http_post_ingress import _serve_fallback_alias
from core.passthrough_headers import outbound_headers

CLIENT = {"X-Review-Profile": "Zero-Canon", "X-Subagent-Id": "coder-1", "X-Custom": "v"}
SCOPE = [("X-Request-Id", "rid-1"), ("X-Subagent-Id", "coder-1"), ("X-Review-Profile", "Zero-Canon")]


def _adapter(base_path: str = "/claude", trust: str | None = None) -> Any:
    config: dict[str, object] = {}
    if trust is not None:
        config["trust_profile"] = trust
    return SimpleNamespace(
        config=config, _host="127.0.0.1", _port=9881, _base_path=base_path,
        _upstream_headers=lambda *_a, **_k: {},
    )


def _wire(adapter: Any, headers: Mapping[str, str] | None = None) -> dict[str, str]:
    return exchange._wire_headers(adapter, CLIENT if headers is None else headers, 2, True)


def _lower(headers: Mapping[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


def test_private_header_set_blocks_review_profile_from_client() -> None:
    forwarded = _lower(outbound_headers(CLIENT, {}, ""))
    assert "x-review-profile" not in forwarded
    assert "x-subagent-id" not in forwarded
    assert forwarded["x-custom"] == "v"
    # Конфигурационные overrides не возвращают приватный заголовок.
    assert "x-review-profile" not in _lower(outbound_headers({}, {"X-Review-Profile": "zero-canon"}, ""))


def test_review_profile_forwarded_to_trusted_local_submodels() -> None:
    with exchange.internal_trace_scope(SCOPE):
        wire = _lower(_wire(_adapter()))
    assert wire["x-review-profile"] == "zero-canon"
    assert wire["x-subagent-id"] == "coder-1"


@pytest.mark.parametrize(("base_path", "trust"), [("/sg-gemini", None), ("/claude", "external"), ("/sg-a", "external")])
def test_review_profile_stripped_for_external_and_sg_routes(base_path: str, trust: str | None) -> None:
    with exchange.internal_trace_scope(SCOPE):
        wire = _lower(_wire(_adapter(base_path, trust)))
    assert "x-review-profile" not in wire
    assert "x-subagent-id" not in wire


def test_standard_or_missing_profile_is_not_injected() -> None:
    with exchange.internal_trace_scope([("X-Review-Profile", "standard"), ("X-Subagent-Id", "s-1")]):
        wire = _lower(_wire(_adapter(), {"X-Custom": "v"}))
    assert "x-review-profile" not in wire and wire["x-subagent-id"] == "s-1"
    with exchange.internal_trace_scope([]):
        assert "x-review-profile" not in _lower(_wire(_adapter(), {}))
    assert "x-review-profile" not in _lower(_wire(_adapter(), {}))


def test_review_profile_survives_failover_and_retry_inside_one_scope() -> None:
    with exchange.internal_trace_scope(SCOPE):
        first = _lower(_wire(_adapter("/claude-a")))
        retry = _lower(_wire(_adapter("/claude-a")))
        failover = _lower(_wire(_adapter("/claude-b")))
        external = _lower(_wire(_adapter("/sg-failover")))
    assert first["x-review-profile"] == retry["x-review-profile"] == failover["x-review-profile"] == "zero-canon"
    assert "x-review-profile" not in external


def test_client_header_fallback_applies_when_scope_has_no_profile() -> None:
    """Passthrough-фасад передаёт заголовки клиента; профиль не теряется и без scope."""
    with exchange.internal_trace_scope([("X-Subagent-Id", "coder-1")]):
        assert _lower(_wire(_adapter()))["x-review-profile"] == "zero-canon"
        assert "x-review-profile" not in _lower(_wire(_adapter("/sg-x")))


def test_scope_restores_previous_context() -> None:
    with exchange.internal_trace_scope(SCOPE):
        with exchange.internal_trace_scope([]):
            assert exchange._INTERNAL_REVIEW_PROFILE.get() == ""
            assert exchange._INTERNAL_SUBAGENT.get() == ""
        assert exchange._INTERNAL_REVIEW_PROFILE.get() == "Zero-Canon"
    assert exchange._INTERNAL_REVIEW_PROFILE.get() == ""
    assert exchange._INTERNAL_SUBAGENT.get() == ""


class _Headers(dict[str, str]):
    """Минимальный аналог HTTPMessage для handler.headers."""


def _context(headers: Mapping[str, str]) -> Any:
    host = SimpleNamespace(_trace_headers=lambda trace: [("X-Request-Id", "rid-9"), ("X-Subagent-Id", "coder-9")])
    handler = SimpleNamespace(path="/v1/chat/completions", headers=_Headers(headers), _trace=object())
    return SimpleNamespace(handler=handler, host=host, request={"model": "alias"}, provider_id=None)


def test_fallback_alias_wraps_dispatch_in_trace_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def fake_dispatch(handler: Any, request: Any, host: Any, upstream: Any, scope: Any) -> bool:
        seen["subagent"] = exchange._INTERNAL_SUBAGENT.get()
        seen["profile"] = exchange._INTERNAL_REVIEW_PROFILE.get()
        with exchange.internal_trace_scope([]):  # вложенный scope не ломает внешний
            pass
        seen["after_nested"] = exchange._INTERNAL_REVIEW_PROFILE.get()
        return True

    monkeypatch.setattr(fallback_http_hook, "dispatch", fake_dispatch)
    context = _context({"X-Review-Profile": "Zero-Canon", "X-Subagent-Id": "ignored"})
    assert _serve_fallback_alias(context) is True
    assert seen == {"subagent": "coder-9", "profile": "Zero-Canon", "after_nested": "Zero-Canon"}
    assert exchange._INTERNAL_SUBAGENT.get() == ""
    assert exchange._INTERNAL_REVIEW_PROFILE.get() == ""


def test_fallback_alias_without_profile_header_and_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_dispatch(*_args: Any) -> bool:
        seen.append(exchange._INTERNAL_REVIEW_PROFILE.get())
        raise OSError("boom")

    monkeypatch.setattr(fallback_http_hook, "dispatch", fake_dispatch)
    with pytest.raises(OSError):
        _serve_fallback_alias(_context({"X-Other": "1"}))
    assert seen == [""]
    assert exchange._INTERNAL_SUBAGENT.get() == ""
    assert exchange._INTERNAL_REVIEW_PROFILE.get() == ""


def test_fallback_upstream_headers_keep_trusted_profile_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Внутри dispatch upstream-вызов собирает wire-заголовки с профилем для локального моста."""
    wires: dict[str, dict[str, str]] = {}

    def fake_dispatch(handler: Any, request: Any, host: Any, upstream: Any, scope: Any) -> bool:
        wires["local"] = _lower(_wire(_adapter(), dict(handler.headers.items())))
        wires["sg"] = _lower(_wire(_adapter("/sg-z"), dict(handler.headers.items())))
        return True

    monkeypatch.setattr(fallback_http_hook, "dispatch", fake_dispatch)
    _serve_fallback_alias(_context({"X-Review-Profile": "zero-canon"}))
    assert wires["local"]["x-review-profile"] == "zero-canon"
    assert wires["local"]["x-subagent-id"] == "coder-9"
    assert "x-review-profile" not in wires["sg"] and "x-subagent-id" not in wires["sg"]
