"""Zero-Canon допуск DashScope SG через геороутер :10830/sg-qwen (REQ-001..REQ-003).

Разрешены ровно три точные формы `_SG_QWEN_PATHS` (AD-001/AD-003); расширение
eligibility маршрута не расширяет границу заголовков (AD-002): X-Review-Profile
и X-Subagent-Id на внешний DashScope не уходят.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

if str(_Path(__file__).resolve().parents[1]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import re
from collections.abc import Mapping
from email.message import Message
from types import SimpleNamespace
from typing import Any

import pytest

from core import http_post_routing, passthrough_exchange as exchange, zero_canon_http as zhttp
from core.http_post_context import PostRequestContext
from core.subbridge_zero_canon import should_forward_review_profile

ZC = "Zero-Canon"
SG_QWEN = "http://127.0.0.1:10830/sg-qwen"
ALLOWED_URLS: tuple[str, ...] = (
    SG_QWEN,
    "http://127.0.0.1:10830/sg-qwen/",
    "http://127.0.0.1:10830/sg-qwen/v1",
)
DASHSCOPE_BACKENDS: tuple[str, ...] = (
    "dashscope-intl",
    "dashscope-intl-k2",
    "dashscope-intl-k3",
    "dashscope-intl-k4",
)
NEURALWATT_URL = "http://127.0.0.1:10830/neuralwatt/v1"
GO_URL = "http://127.0.0.1:10830/go/v1"
BYPASS_URL = "http://127.0.0.1:10830/sg-qwen/../neuralwatt/v1"


def _kept_backends(providers: list[Any], **kwargs: Any) -> list[str]:
    """`filter_zero_canon_providers` в Zero-Canon: имена выживших бэкендов."""
    kept = zhttp.filter_zero_canon_providers(providers, ZC, codex_v2_enabled=True, **kwargs)
    return [p["backend"] if isinstance(p, dict) else str(p) for p in kept]


@pytest.mark.parametrize("url", ALLOWED_URLS)
def test_filter_admits_three_sg_qwen_forms_direct(url: str) -> None:
    providers = [{"backend": b, "base_url": url} for b in DASHSCOPE_BACKENDS]
    assert _kept_backends(providers) == list(DASHSCOPE_BACKENDS)


@pytest.mark.parametrize("url", ALLOWED_URLS)
def test_filter_admits_three_sg_qwen_forms_via_configs(url: str) -> None:
    configs = {b: {"base_url": url} for b in DASHSCOPE_BACKENDS}
    assert _kept_backends(list(DASHSCOPE_BACKENDS), provider_configs=configs) == list(DASHSCOPE_BACKENDS)


def test_filter_no_regression_for_neuralwatt_and_go() -> None:
    providers = [
        {"backend": "neuralwatt", "base_url": NEURALWATT_URL},
        {"backend": "opencode-go", "base_url": GO_URL},
        {"backend": "dashscope-intl", "base_url": SG_QWEN},
    ]
    assert _kept_backends(providers) == ["neuralwatt", "opencode-go", "dashscope-intl"]


DENIED_URLS: tuple[str, ...] = (
    "http://127.0.0.1:10830/sg-openai/v1", "http://127.0.0.1:10830/sg-deepseek/v1",
    "http://127.0.0.1:10830/sg-qwen2", "http://127.0.0.1:10830/sg-qwen-extra/v1",
    "http://127.0.0.1:10830/sg-qwen/x", "http://127.0.0.1:10830/sg-qwen/sg-openai",
    "http://127.0.0.1:10830/sg-qwen/v1/sg-deepseek", "http://127.0.0.1:10830/sg-qwen%2fsg-openai",
    "http://127.0.0.1:10830/sg-qwen/SG-OPENAI", "http://127.0.0.1:10830/sg-qwen/./v1",
    "http://127.0.0.1:10830/sg-qwen/.", "http://127.0.0.1:10830/sg-qwen/../neuralwatt/v1",
    "http://127.0.0.1:10830/sg-qwen/%2e/v1", "http://127.0.0.1:10830/sg-qwen/%2e%2e/neuralwatt/v1",
    "http://127.0.0.1:10830/sg-qwen/%252e%252e/v1", "http://127.0.0.1:10830/sg-qwen\\v1",
    "http://127.0.0.1:10830/%73g-qwen/v1", "http://127.0.0.1:10830/sg-qwen?foo=bar",
    "http://127.0.0.1:10830/sg-qwen#frag", "http://127.0.0.1:10830/sg-qwen;a=1",
    "http://127.0.0.1:10830/sg-qwen;a=1/v1", "http://127.0.0.1:2455/sg-qwen",
    "http://127.0.0.1:9881/sg-qwen", "https://127.0.0.1:10830/sg-qwen",
    "http://example.com:10830/sg-qwen", "http://user@127.0.0.1:10830/sg-qwen",
)


@pytest.mark.parametrize("url", DENIED_URLS)
def test_filter_rejects_each_bypass_independently(url: str) -> None:
    """Независимые кейсы: traversal/encoding/query отказывают без sg-openai в причине."""
    assert _kept_backends([{"backend": "dashscope-intl", "base_url": url}]) == []


def test_filter_rejects_external_trust_and_unattested_dashscope() -> None:
    external = {"backend": "dashscope-intl", "base_url": SG_QWEN, "trust_profile": "external"}
    unattested = {"backend": "dashscope-intl-k2", "base_url": SG_QWEN, "zero_canon_attested": False}
    assert _kept_backends([external, unattested]) == []


def test_filter_mixed_keeps_only_exact_forms() -> None:
    providers: list[dict[str, Any]] = [{"backend": "dashscope-intl", "base_url": url} for url in DENIED_URLS]
    providers.append({"backend": "dashscope-intl-k2", "base_url": SG_QWEN})
    assert _kept_backends(providers) == ["dashscope-intl-k2"]


def test_url_allowed_fallback_for_local_subbridge_unchanged() -> None:
    assert zhttp._url_allowed(SG_QWEN, "") is True
    assert zhttp._url_allowed("http://127.0.0.1:10830/sg-qwen/v1", "") is True
    assert zhttp._url_allowed(SG_QWEN, "external") is False
    assert zhttp._url_allowed("http://127.0.0.1:9881/claude/v1", "") is True


class _FakeAdapter:
    def __init__(self, aid: str, base_url: str) -> None:
        self.id, self.kind, self.owned_by = aid, "passthrough", aid
        self.config: dict[str, Any] = {"base_url": base_url}


class _FakeBackends:
    def __init__(self, adapters: list[_FakeAdapter]) -> None:
        self._map = {a.id: a for a in adapters}

    def adapters(self) -> list[_FakeAdapter]:
        return list(self._map.values())

    def get(self, backend_id: Any) -> _FakeAdapter | None:
        return self._map.get(str(backend_id)) if backend_id is not None else None


class _FakeHandler:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.path, self.headers = "/v1/chat/completions", Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self.rejects: list[tuple[Any, ...]] = []
        self.replies: list[tuple[Any, ...]] = []
        self._trace: Any = None

    def _reject(self, *args: Any, **_kw: Any) -> None:
        self.rejects.append(args)

    def _reply_error(self, *args: Any, **kw: Any) -> None:
        self.replies.append((args, kw))

    def _telemetry_meta(self, **_kw: Any) -> None:
        return None


def _make_host() -> Any:
    models: dict[str, Any] = {
        "qwen4-max": {
            "backend": "dashscope-intl",
            "routing": {
                "legacy_backend": "dashscope-intl",
                "disabled_backend": "dashscope-intl",
                "routes": [
                    {"route_id": "dashscope-intl", "backend": "dashscope-intl", "weight": 60, "priority": 10},
                    {"route_id": "dashscope-intl-k2", "backend": "dashscope-intl-k2", "weight": 40, "priority": 11},
                ],
            },
        },
        "kimi-k3.1-pro": {"backend": "dashscope-intl-k3"},
        "sg-bypass-model": {"backend": "dashscope-intl-bypass"},
    }
    adapters = [_FakeAdapter(b, SG_QWEN) for b in DASHSCOPE_BACKENDS]
    adapters.append(_FakeAdapter("dashscope-intl-bypass", BYPASS_URL))
    published = {mid: (adapters[0], cfg) for mid, cfg in models.items()}
    return SimpleNamespace(
        FLEET={"models": models},
        BACKENDS=_FakeBackends(adapters),
        MODEL_ID="qwen4-max",
        INTERNAL_MODEL_IDS=set(),
        PROVIDER_SCOPES={},
        _PROVIDER_CHAT_RE=re.compile(r"^/v1/providers/([^/]+)/v1/chat/completions$"),
        _MODEL_NOTES_FILTER=SimpleNamespace(is_blocked=lambda _m: False),
        _PENALTY_TRACKER=SimpleNamespace(get_model_status=lambda _m: {"is_penalized": False}),
        _get_published_models=lambda: published,
        _resolve_model_alias=lambda _m, _p: None,
        _auth_ok=lambda _h: True,
        _trace_headers=lambda _t: [],
        flag_enabled=lambda name: name == "BRIDGE_TRANSPORT_ROUTING_ENABLED",
    )


def _resolve(model_id: str) -> tuple[Any, _FakeHandler]:
    handler = _FakeHandler(headers={"X-Review-Profile": ZC})
    ctx = PostRequestContext(handler, _make_host())  # type: ignore[arg-type]
    ctx.prepare_route(b"{}", {"model": model_id})
    return http_post_routing.resolve_post_route(ctx), handler


@pytest.mark.parametrize("model_id", ["qwen4-max", "kimi-k3.1-pro"])
def test_resolve_post_route_zero_canon_dashscope_models(model_id: str) -> None:
    """Обе модели DashScope обслужены в Zero-Canon без 503 (baseline: 503 route_unavailable)."""
    route, handler = _resolve(model_id)
    assert route is not None and not handler.rejects and not handler.replies
    assert str(route.model["backend"]).startswith("dashscope-intl")


def test_resolve_post_route_zero_canon_qwen_keeps_dashscope_routes() -> None:
    route, _handler = _resolve("qwen4-max")
    assert route is not None
    assert [r["backend"] for r in route.model["routing"]["routes"]] == ["dashscope-intl", "dashscope-intl-k2"]
    assert route.model["routing"]["zero_canon_backend"] == "dashscope-intl"


def test_resolve_post_route_zero_canon_bypass_model_still_503() -> None:
    route, handler = _resolve("sg-bypass-model")
    assert route is None
    assert handler.rejects and handler.rejects[0][:2] == (503, "route_unavailable")


CLIENT = {"X-Review-Profile": "Zero-Canon", "X-Subagent-Id": "coder-1", "X-Custom": "v"}
SCOPE = [("X-Request-Id", "rid-1"), ("X-Subagent-Id", "coder-1"), ("X-Review-Profile", "Zero-Canon")]


def _adapter(base_path: str) -> Any:
    return SimpleNamespace(
        config={}, _host="127.0.0.1", _port=10830, _base_path=base_path,
        _upstream_headers=lambda *_a, **_k: {},
    )


def _wire(adapter: Any, client: Mapping[str, str] = CLIENT) -> dict[str, str]:
    headers: Mapping[str, str] = exchange._wire_headers(adapter, client, 2, True)
    return {key.lower(): value for key, value in headers.items()}


@pytest.mark.parametrize("base_path", ["/sg-qwen", "/sg-qwen/v1"])
def test_header_boundary_blocks_dashscope_sg_qwen(base_path: str) -> None:
    """REQ-003/OPEN-02: X-Review-Profile и X-Subagent-Id не уходят на /sg-qwen*."""
    assert should_forward_review_profile(base_path, "") is False
    assert should_forward_review_profile(base_path, "local") is False
    with exchange.internal_trace_scope(SCOPE):
        wire = _wire(_adapter(base_path))
    assert "x-review-profile" not in wire
    assert "x-subagent-id" not in wire
    assert wire["x-custom"] == "v"


def test_header_boundary_positive_control_local_subbridge() -> None:
    assert should_forward_review_profile("/claude/v1", "") is True
    with exchange.internal_trace_scope(SCOPE):
        wire = _wire(_adapter("/claude"))
    assert wire["x-review-profile"] == "zero-canon"
    assert wire["x-subagent-id"] == "coder-1"


def test_header_boundary_strips_mixed_case_private_client_headers() -> None:
    client = {"x-review-profile": ZC, "x-subagent-id": "coder-1", "X-Custom": "v"}
    wire = _wire(_adapter("/sg-qwen"), client)
    assert "x-review-profile" not in wire
    assert "x-subagent-id" not in wire
    assert wire["x-custom"] == "v"
