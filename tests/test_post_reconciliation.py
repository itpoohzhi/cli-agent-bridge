"""Регрессии семантического слияния HTTP-фасада и origin/dev."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from core.http_post_context import PostRequestContext
from core.http_post_routing import PostRoute, _internal_allowed


def internal_route(position: str, key: str | None, supplied: str) -> PostRoute:
    handler = SimpleNamespace(
        path="/v1/chat/completions",
        headers={"X-Internal-Service-Key": supplied},
        _reject=Mock(),
    )
    host = SimpleNamespace(INTERNAL_MODEL_IDS={"internal"}, _INTERNAL_SERVICE_KEY=key)
    context = PostRequestContext(handler, host)
    route = PostRoute(context, {}, "public", "public", 6)
    if position in ("raw_model", "model_id"):
        setattr(route, position, "internal")
    return route


@pytest.mark.parametrize("position", ["raw_model", "requested", "model_id"])
@pytest.mark.parametrize("key", [None, ""])
def test_internal_without_configured_key_fails_closed(
    monkeypatch: pytest.MonkeyPatch, position: str, key: str | None
) -> None:
    monkeypatch.delenv("INTERNAL_SERVICE_KEY", raising=False)
    route = internal_route(position, key, "")
    requested = "internal" if position == "requested" else "public"
    assert _internal_allowed(route, requested) is False
    route.handler._reject.assert_called_once_with(
        403,
        "internal_model_forbidden",
        "Model reserved for internal review",
        "unknown",
        6,
    )


@pytest.mark.parametrize(
    "supplied,allowed", [("", False), ("wrong", False), ("ключ", True)]
)
@pytest.mark.parametrize("source", ["host", "env"])
def test_internal_requires_matching_nonempty_key(
    monkeypatch: pytest.MonkeyPatch, source: str, supplied: str, allowed: bool
) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_KEY", "ключ" if source == "env" else "other")
    route = internal_route("model_id", "ключ" if source == "host" else None, supplied)
    assert _internal_allowed(route, "public") is allowed
    assert route.handler._reject.call_count == int(not allowed)


def test_public_model_does_not_require_internal_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INTERNAL_SERVICE_KEY", raising=False)
    route = internal_route("public", None, "")
    assert _internal_allowed(route, "public") is True
    route.handler._reject.assert_not_called()


@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("effort", ["high", "off", None, 123, "unknown"])
def test_facade_passthrough_preserves_effortless_policy(
    monkeypatch: pytest.MonkeyPatch, weighted: bool, effort: Any
) -> None:
    from core.effortless_policy import EffortValidationError
    from core.passthrough_autonomy import (
        PassthroughOptions,
        prepare_passthrough_request,
    )

    monkeypatch.setenv("BRIDGE_EFFORTLESS_CLAMP_ENABLED", "true")
    request = {"model": "public", "reasoning_effort": effort}
    route = internal_route("public", None, "")
    route.request = request
    route.model = {"backend": "upstream", "efforts": ["off"], "default_effort": "off"}
    route.host.flag_enabled = lambda flag: (
        weighted if flag == "BRIDGE_TRANSPORT_ROUTING_ENABLED" else True
    )
    route.host.FLAG_EFFORT_CATALOG = "BRIDGE_EFFORT_CATALOG_ENABLED"
    route.host.PassthroughOptions = PassthroughOptions
    route.host.EffortValidationError = EffortValidationError
    route.host.prepare_passthrough_request = prepare_passthrough_request
    route.host.passthrough_autonomy_validation_enabled = lambda _: False
    _assert_passthrough(route, request, effort)


def _assert_passthrough(route: PostRoute, request: dict[str, Any], effort: Any) -> None:
    import json

    from core.http_post_dispatch import _passthrough
    from core.http_post_routing import PreparedPostBody

    route.host.json = json
    route.host._log, route.host.describe_clamp = Mock(), Mock()
    route.host._LOG_EFFORT_MAX = 32
    handler = route.handler
    handler._trace_log_fields = Mock(return_value="")
    handler._serve_passthrough, handler._serve_resilient = Mock(), Mock()
    _passthrough(route, object(), PreparedPostBody(b"{}", request))
    if effort in (123, "unknown"):
        assert handler._reject.call_args.args[:2] == (
            400,
            "unsupported_reasoning_effort",
        )
        handler._serve_resilient.assert_not_called()
        return
    handler._reject.assert_not_called()
    serve = handler._serve_resilient.call_args.args[1]
    serve()
    prepared = handler._serve_passthrough.call_args.args[2]
    assert "reasoning_effort" not in prepared
