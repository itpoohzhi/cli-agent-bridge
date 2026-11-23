"""Regression tests for Code Council Cycle 1 blockers (F-001..F-004, F-011, F-014, F-015)."""

from __future__ import annotations

import re
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from adapters.stdio_drivers import infer_protocol
from adapters.stdio_resident_adapter import StdioResidentAdapter
from core import fallback_http_hook, http_post_ingress, http_post_routing
from core.http_post_context import PostRequestContext


class _FakeAdapter:
    def __init__(self, aid: str, *, kind: str, owned_by: str, config: dict[str, Any]) -> None:
        self.id, self.kind, self.owned_by, self.config = aid, kind, owned_by, config


class _FakeBackends:
    def __init__(self, adapters: list[_FakeAdapter]) -> None:
        self._map = {a.id: a for a in adapters}

    def adapters(self) -> list[_FakeAdapter]:
        return list(self._map.values())

    def get(self, backend_id: Any) -> _FakeAdapter | None:
        return self._map.get(str(backend_id)) if backend_id is not None else None


class _FakeHandler:
    def __init__(self, path: str = "/v1/chat/completions", headers: dict[str, str] | None = None) -> None:
        self.path, self.headers = path, Message()
        for k, v in (headers or {}).items():
            self.headers[k] = v
        self.rejects: list[tuple[Any, ...]] = []
        self.replies: list[tuple[Any, ...]] = []
        self._trace: Any = None

    def _reject(self, *args: Any, **_kw: Any) -> None:
        self.rejects.append(args)

    def _reply_error(self, *args: Any, **kw: Any) -> None:
        self.replies.append((args, kw))

    def _telemetry_meta(self, **_kw: Any) -> None:
        return None


def _make_host(
    models: dict[str, Any],
    adapters: list[_FakeAdapter],
    *,
    routing_enabled: bool = True,
    provider_scopes: dict[str, Any] | None = None,
) -> Any:
    backends = _FakeBackends(adapters)
    primary = adapters[0] if adapters else None
    published = {mid: (primary, cfg) for mid, cfg in models.items()}
    return SimpleNamespace(
        FLEET={"models": models},
        BACKENDS=backends,
        MODEL_ID=next(iter(models), "gpt-6.1-sol"),
        INTERNAL_MODEL_IDS=set(),
        PROVIDER_SCOPES=provider_scopes or {"openai": ("openai",)},
        _PROVIDER_CHAT_RE=re.compile(r"^/v1/providers/([^/]+)/v1/chat/completions$"),
        _MODEL_NOTES_FILTER=SimpleNamespace(is_blocked=lambda _m: False),
        _PENALTY_TRACKER=SimpleNamespace(get_model_status=lambda _m: {"is_penalized": False}),
        _get_published_models=lambda: published,
        _resolve_model_alias=lambda _m, _p: None,
        _auth_ok=lambda _h: True,
        _trace_headers=lambda _t: [],
        flag_enabled=lambda name: routing_enabled if name == "BRIDGE_TRANSPORT_ROUTING_ENABLED" else False,
    )


def _ctx(host: Any, handler: _FakeHandler, request: dict[str, Any], provider_id: str | None = None) -> PostRequestContext:
    ctx = PostRequestContext(handler, host)  # type: ignore[arg-type]
    ctx.prepare_route(b"{}", request)
    ctx.provider_id = provider_id
    return ctx


def _isolate_v2_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "missing_dynamic.json"))
    monkeypatch.setenv("BRIDGE_CODEX_APP_SERVER_V2_ENABLED", value)


def test_f001_zero_canon_route_switch_enforces_provider_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F-001: Switching from dropped route 0 to out-of-scope route 1 must return 400."""
    _isolate_v2_flag(monkeypatch, tmp_path, "1")
    model_cfg = {
        "backend": "openai-key-3",
        "routing": {
            "disabled_backend": "openai-key-3",
            "routes": [
                {"backend": "openai-key-3", "base_url": "http://127.0.0.1:9000/sg-openai/v1"},
                {"backend": "other-zc", "base_url": "http://127.0.0.1:9001/v1"},
            ],
        },
    }
    bad_adapters = [
        _FakeAdapter("openai-key-3", kind="passthrough", owned_by="openai", config={}),
        _FakeAdapter("other-zc", kind="stdio_resident", owned_by="other-owner", config={}),
    ]
    handler_bad = _FakeHandler(headers={"X-Review-Profile": "Zero-Canon"})
    host_bad = _make_host({"gpt-6.1-sol": model_cfg}, bad_adapters)
    res_bad = http_post_routing.resolve_post_route(
        _ctx(host_bad, handler_bad, {"model": "gpt-6.1-sol"}, provider_id="openai")
    )
    assert res_bad is None
    assert handler_bad.replies and handler_bad.replies[0][0][0] == 400
    assert handler_bad.replies[0][1].get("code") == "model_not_in_provider_scope"

    ok_adapters = [
        _FakeAdapter("openai-key-3", kind="passthrough", owned_by="openai", config={}),
        _FakeAdapter("other-zc", kind="stdio_resident", owned_by="openai", config={}),
    ]
    handler_ok = _FakeHandler(headers={"X-Review-Profile": "Zero-Canon"})
    host_ok = _make_host({"gpt-6.1-sol": model_cfg}, ok_adapters)
    res_ok = http_post_routing.resolve_post_route(
        _ctx(host_ok, handler_ok, {"model": "gpt-6.1-sol"}, provider_id="openai")
    )
    assert res_ok is not None and res_ok.model["backend"] == "other-zc" and not handler_ok.replies


def test_f002_f011_explicit_v2_downgraded_and_preflight_guard_and_zc_503(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F-002 + F-011: Explicit v2 respects kill-switch; preflight guards v2; Zero-Canon fails 503."""
    cfg = tmp_path / "missing_dynamic.json"
    opts = {"protocol": "codex-app-server-v2"}
    assert infer_protocol("codex", {}, opts, environ={"BRIDGE_CODEX_APP_SERVER_V2_ENABLED": "0"}, config_path=cfg) == "stream-json"
    env_cc = {"BRIDGE_CODEX_APP_SERVER_V2_ENABLED": "0", "STDIO_RESIDENT_CLAUDE_CODEX_PROTOCOL_ENABLED": "1"}
    assert infer_protocol("codex", {}, opts, environ=env_cc, config_path=cfg) == "codex-app-server"
    assert infer_protocol("codex", {}, opts, environ={"BRIDGE_CODEX_APP_SERVER_V2_ENABLED": "1"}, config_path=cfg) == "codex-app-server-v2"

    _isolate_v2_flag(monkeypatch, tmp_path, "0")
    adapter = StdioResidentAdapter("codex", {"options": {"protocol": "codex-app-server-v2"}})
    assert adapter._protocol == "stream-json"
    monkeypatch.setattr(adapter, "_sync_protocol", lambda: "codex-app-server-v2")
    assert adapter.preflight_check() is False

    host = _make_host(
        {"gpt-6.1-sol": {"backend": "codex"}},
        [_FakeAdapter("codex", kind="stdio_resident", owned_by="openai", config={})],
    )
    handler = _FakeHandler(headers={"X-Review-Profile": "Zero-Canon"})
    assert http_post_routing.resolve_post_route(_ctx(host, handler, {"model": "gpt-6.1-sol"})) is None
    assert handler.rejects and handler.rejects[0][:2] == (503, "zero_canon_unsupported_by_driver")


def test_f003_zero_canon_rejects_fallback_alias_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F-003: Zero-Canon rejects enabled fallback alias with 503 before dispatch; standard still dispatches."""
    chains_dir = tmp_path / "chains"
    chains_dir.mkdir()
    (chains_dir / "openai.yaml").write_text(
        "version: 1\nchains:\n  zc-alias:\n    declared_context_window: 128000\n"
        "    candidates:\n"
        "      - {model: openai-key-3, cost_class: paid, context_window: 128000}\n"
        "      - {model: sg-openai-backup, cost_class: paid, context_window: 128000}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BRIDGE_MODEL_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_FALLBACK_CHAINS_PATH", str(chains_dir))
    dispatched: list[str] = []

    def _fake_dispatch(_h: Any, req: dict[str, Any], *_a: Any) -> bool:
        dispatched.append(str(req.get("model")))
        return True

    monkeypatch.setattr(fallback_http_hook, "dispatch", _fake_dispatch)
    host = _make_host({"gpt-6.1-sol": {"backend": "codex"}}, [])

    zc_alias_handler = _FakeHandler(headers={"X-Review-Profile": "Zero-Canon"})
    assert http_post_ingress._resolve_chat_path(_ctx(host, zc_alias_handler, {"model": "zc-alias"})) is False
    assert zc_alias_handler.rejects and zc_alias_handler.rejects[0][:2] == (503, "zero_canon_unsupported_by_driver")
    assert dispatched == []

    zc_normal_handler = _FakeHandler(headers={"X-Review-Profile": "Zero-Canon"})
    assert http_post_ingress._resolve_chat_path(_ctx(host, zc_normal_handler, {"model": "gpt-6.1-sol"})) is True
    assert not zc_normal_handler.rejects and dispatched == []

    std_alias_handler = _FakeHandler()
    assert http_post_ingress._resolve_chat_path(_ctx(host, std_alias_handler, {"model": "zc-alias"})) is False
    assert dispatched == ["zc-alias"]


def test_f014_zero_canon_preserves_disabled_backend_when_routing_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F-014: Zero-Canon keeps disabled_backend untouched and records zero_canon_backend."""
    _isolate_v2_flag(monkeypatch, tmp_path, "1")
    model_cfg = {
        "backend": "openai-key-3",
        "routing": {
            "disabled_backend": "openai-key-3",
            "routes": [
                {"backend": "openai-key-3", "base_url": "http://127.0.0.1:9000/sg-openai/v1"},
                {"backend": "codex"},
            ],
        },
    }
    adapters = [
        _FakeAdapter("openai-key-3", kind="passthrough", owned_by="openai", config={}),
        _FakeAdapter("codex", kind="stdio_resident", owned_by="openai", config={}),
    ]
    host = _make_host({"gpt-6.1-sol": model_cfg}, adapters, routing_enabled=False)
    handler = _FakeHandler(headers={"X-Review-Profile": "Zero-Canon"})
    route = http_post_routing.resolve_post_route(_ctx(host, handler, {"model": "gpt-6.1-sol"}))
    assert route is not None
    assert route.model["backend"] == "codex"
    assert route.model["routing"]["disabled_backend"] == "openai-key-3"
    assert route.model["routing"]["zero_canon_backend"] == "codex"


def test_f004_authoritative_kind_and_f015_cached_review_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F-004 + F-015: Adapter kind overrides config spoof; cached _review_profile skips re-parsing."""
    _isolate_v2_flag(monkeypatch, tmp_path, "1")
    spoof_adapter = _FakeAdapter("codex", kind="passthrough", owned_by="openai", config={"kind": "stdio_resident"})
    host = _make_host({"gpt-6.1-sol": {"backend": "codex"}}, [spoof_adapter])
    cfgs = http_post_routing._backend_configs(host)
    assert cfgs is not None and cfgs["codex"]["kind"] == "passthrough"

    def _boom(_headers: Any) -> str:
        raise AssertionError("parse_review_profile_headers must not be called when cached")

    monkeypatch.setattr(http_post_routing, "parse_review_profile_headers", _boom)

    zc_handler = _FakeHandler(headers={"X-Review-Profile": "Zero-Canon"})
    zc_handler._review_profile = "Zero-Canon"
    assert http_post_routing.resolve_post_route(_ctx(host, zc_handler, {"model": "gpt-6.1-sol"})) is None
    assert zc_handler.rejects and zc_handler.rejects[0][:2] == (503, "route_unavailable")

    std_handler = _FakeHandler(headers={"X-Review-Profile": "Zero_Canon"})
    std_handler._review_profile = "standard"
    assert http_post_routing.resolve_post_route(_ctx(host, std_handler, {"model": "gpt-6.1-sol"})) is not None
