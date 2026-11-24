"""Zero-Canon допуск stateless georouter-шлюзов :10830/neuralwatt и :10830/go.

Допуск в `filter_zero_canon_providers` не расширяет границу заголовков:
`X-Review-Profile`/`X-Subagent-Id` на эти шлюзы по-прежнему не уходят.
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
NEURALWATT_URL = "http://127.0.0.1:10830/neuralwatt/v1"
GO_URL = "http://127.0.0.1:10830/go/v1"
ALLOWED: tuple[tuple[str, str], ...] = (
    ("neuralwatt", NEURALWATT_URL),
    ("neuralwatt-flex", NEURALWATT_URL),
    ("opencode-go", GO_URL),
    ("opencode-go-claude", GO_URL),
)
BACKEND_URLS: dict[str, str] = dict(ALLOWED)


def _kept_backends(providers: list[Any], **kwargs: Any) -> list[str]:
    kept = zhttp.filter_zero_canon_providers(providers, ZC, codex_v2_enabled=True, **kwargs)
    return [p["backend"] if isinstance(p, dict) else str(p) for p in kept]


@pytest.mark.parametrize(("backend", "url"), ALLOWED)
def test_filter_admits_stateless_georouter_backends(backend: str, url: str) -> None:
    assert _kept_backends([{"backend": backend, "base_url": url}]) == [backend]


def test_filter_admits_all_four_via_provider_configs() -> None:
    configs = {backend: {"base_url": url} for backend, url in ALLOWED}
    assert _kept_backends([backend for backend, _url in ALLOWED], provider_configs=configs) == [
        backend for backend, _url in ALLOWED
    ]


DENIED_URLS: tuple[tuple[str, str], ...] = (
    ("stateless-x", "http://127.0.0.1:10830/sg-deepseek/v1"),
    ("stateless-x", "http://127.0.0.1:10830/sg-openai/v1"),
    ("stateless-x", "http://127.0.0.1:10830/gone/v1"),
    ("stateless-x", "http://127.0.0.1:10830/neuralwatt2/v1"),
    ("neuralwatt", "http://127.0.0.1:9881/neuralwatt/v1"),
    ("neuralwatt", "https://127.0.0.1:10830/neuralwatt/v1"),
    ("neuralwatt", "http://example.com:10830/neuralwatt/v1"),
    ("neuralwatt", "http://user@127.0.0.1:10830/neuralwatt/v1"),
    ("opencode-go", "http://user:pass@127.0.0.1:10830/go/v1"),
    ("neuralwatt", "http://127.0.0.1:10830/neuralwatt/../sg-deepseek"),
    ("neuralwatt", "http://127.0.0.1:10830/neuralwatt/../claude/v1"),
    ("neuralwatt", "http://127.0.0.1:10830/neuralwatt/v1?next=/sg-deepseek"),
    ("neuralwatt", "http://127.0.0.1:10830/neuralwatt/v1#/sg-deepseek"),
    ("neuralwatt", "http://127.0.0.1:2455/neuralwatt/v1"),
    ("stateless-x", "http://127.0.0.1:2455/v1"),
)


@pytest.mark.parametrize(("backend", "url"), DENIED_URLS)
def test_filter_rejects_georouter_lookalikes(backend: str, url: str) -> None:
    assert _kept_backends([{"backend": backend, "base_url": url}]) == []


def test_filter_rejects_external_trust_and_unattested_georouter() -> None:
    external = {"backend": "neuralwatt", "base_url": NEURALWATT_URL, "trust_profile": "external"}
    unattested = {"backend": "opencode-go", "base_url": GO_URL, "zero_canon_attested": False}
    assert _kept_backends([external, unattested]) == []


def test_filter_mixed_keeps_only_stateless_georouter() -> None:
    providers: list[dict[str, Any]] = [{"backend": b, "base_url": u} for b, u in (*DENIED_URLS, *ALLOWED)]
    assert _kept_backends(providers) == [backend for backend, _url in ALLOWED]


def test_filter_standard_profile_is_noop_for_georouter() -> None:
    providers: list[dict[str, Any]] = [{"backend": b, "base_url": u} for b, u in DENIED_URLS]
    assert zhttp.filter_zero_canon_providers(providers, "standard", codex_v2_enabled=True) == providers


def test_url_allowed_empty_url_and_external_trust() -> None:
    assert zhttp._url_allowed("", "") is True
    assert zhttp._url_allowed("", "external") is False
    assert zhttp._url_allowed(NEURALWATT_URL, "external") is False
    assert zhttp._url_allowed(NEURALWATT_URL, "") is True
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
        "deepseek-v4.1-flash": {
            "backend": "neuralwatt",
            "routing": {
                "legacy_backend": "neuralwatt",
                "disabled_backend": "neuralwatt",
                "routes": [
                    {"route_id": "neuralwatt", "backend": "neuralwatt", "weight": 60, "priority": 5},
                    {"route_id": "opencode-go", "backend": "opencode-go", "weight": 40, "priority": 10},
                ],
            },
        },
        "glm-5.3-flex": {"backend": "neuralwatt-flex"},
        "sg-only-model": {"backend": "stateless-x"},
    }
    adapters = [_FakeAdapter(b, u) for b, u in ALLOWED]
    adapters.append(_FakeAdapter("stateless-x", "http://127.0.0.1:10830/sg-deepseek/v1"))
    backends = _FakeBackends(adapters)
    published = {mid: (adapters[0], cfg) for mid, cfg in models.items()}
    return SimpleNamespace(
        FLEET={"models": models},
        BACKENDS=backends,
        MODEL_ID="deepseek-v4.1-flash",
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


def test_resolve_post_route_zero_canon_deepseek_keeps_both_georouter_routes() -> None:
    route, handler = _resolve("deepseek-v4.1-flash")
    assert route is not None and not handler.rejects and not handler.replies
    assert route.model["backend"] == "neuralwatt"
    assert [r["backend"] for r in route.model["routing"]["routes"]] == ["neuralwatt", "opencode-go"]
    assert route.model["routing"]["zero_canon_backend"] == "neuralwatt"


def test_resolve_post_route_zero_canon_glm_flex_single_backend() -> None:
    route, handler = _resolve("glm-5.3-flex")
    assert route is not None and not handler.rejects and not handler.replies
    assert route.model["backend"] == "neuralwatt-flex"


def test_resolve_post_route_zero_canon_sg_only_model_still_503() -> None:
    route, handler = _resolve("sg-only-model")
    assert route is None
    assert handler.rejects and handler.rejects[0][:2] == (503, "route_unavailable")


CLIENT = {"X-Review-Profile": "Zero-Canon", "X-Subagent-Id": "coder-1", "X-Custom": "v"}
SCOPE = [("X-Request-Id", "rid-1"), ("X-Subagent-Id", "coder-1"), ("X-Review-Profile", "Zero-Canon")]


def _adapter(base_path: str) -> Any:
    return SimpleNamespace(
        config={}, _host="127.0.0.1", _port=10830, _base_path=base_path,
        _upstream_headers=lambda *_a, **_k: {},
    )


def _wire(adapter: Any) -> dict[str, str]:
    headers: Mapping[str, str] = exchange._wire_headers(adapter, CLIENT, 2, True)
    return {key.lower(): value for key, value in headers.items()}


@pytest.mark.parametrize("base_path", ["/neuralwatt/v1", "/go/v1"])
def test_header_boundary_still_blocks_georouter(base_path: str) -> None:
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


def test_resolve_post_route_zero_canon_callable_adapters_registry() -> None:
    """Боевой AdapterRegistry/GatedRegistry отдаёт adapters() методом, а deepseek-direct стоит первым с weight=0."""
    host = _make_host()
    host.BACKENDS = _FakeBackends([*host.BACKENDS.adapters(), _FakeAdapter("deepseek-direct", "http://127.0.0.1:10830/sg-deepseek")])
    host.FLEET["models"]["deepseek-v4.1-flash"]["routing"]["routes"] = [
        {"route_id": "deepseek-direct", "backend": "deepseek-direct", "weight": 0, "priority": 20},
        {"route_id": "neuralwatt", "backend": "neuralwatt", "weight": 60, "priority": 5},
        {"route_id": "opencode-go", "backend": "opencode-go", "weight": 40, "priority": 10},
    ]
    handler = _FakeHandler(headers={"X-Review-Profile": ZC})
    ctx = PostRequestContext(handler, host)  # type: ignore[arg-type]
    ctx.prepare_route(b"{}", {"model": "deepseek-v4.1-flash"})
    route = http_post_routing.resolve_post_route(ctx)
    assert route is not None and not handler.rejects and not handler.replies
    assert route.model["backend"] == "neuralwatt"
    assert [r["backend"] for r in route.model["routing"]["routes"]] == ["neuralwatt", "opencode-go"]
    assert route.model["routing"]["zero_canon_backend"] == "neuralwatt"


def test_apply_filtered_routes_prefers_positive_weight_over_zero_weight_reserve() -> None:
    """Даже если reserve-маршрут (weight=0) идёт первым в kept, выбирается активный маршрут с weight>0."""
    from core.routing_weights_runtime import base_model_routing

    routing: dict[str, Any] = {
        "enabled": True,
        "legacy_backend": "neuralwatt",
        "disabled_backend": "neuralwatt",
        "routes": [
            {"route_id": "reserve-a", "backend": "reserve-a", "weight": 0, "priority": 20},
            {"route_id": "neuralwatt", "backend": "neuralwatt", "weight": 60, "priority": 5},
            {"route_id": "opencode-go", "backend": "opencode-go", "weight": 40, "priority": 10},
        ],
    }
    route = SimpleNamespace(model={"id": "deepseek-v4.1-flash", "backend": "neuralwatt", "routing": routing})
    http_post_routing._apply_filtered_routes(route, routing, list(routing["routes"]))  # type: ignore[arg-type]
    assert route.model["backend"] == "neuralwatt"
    assert route.model["routing"]["zero_canon_backend"] == "neuralwatt"
    effective = base_model_routing(route.model)
    assert effective is not None
    assert [r["backend"] for r in effective["routes"]] == ["reserve-a", "neuralwatt", "opencode-go"]
