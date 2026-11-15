"""Механически выделенные auth, admission и чтение POST из HTTP-фасада."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from core.http_post_context import PostHandler, PostHost, PostRequestContext
from core.passthrough_autonomy import strip_passthrough_request


def clean_transport_request(
    raw: bytes, request: dict[str, Any],
    stripper: Callable[
        [bytes, dict[str, Any]], tuple[bytes, dict[str, Any]]
    ] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Очищает passthrough controls независимо от rollout, не меняя вход.

    Host передаёт актуальный _strip_passthrough_env третьим аргументом;
    самостоятельный вызов сохраняет прежнюю очистку env/autonomy.
    """
    raw, clean = (stripper or strip_passthrough_request)(raw, request)
    if "transport_seed" not in clean:
        return raw, clean
    clean = dict(clean)
    del clean["transport_seed"]
    return json.dumps(clean, ensure_ascii=False).encode("utf-8"), clean


def _allow_deferred_auth(context: PostRequestContext) -> bool:
    handler, host = context.handler, context.host
    if not (
        handler.client_address[0] in host._LOOPBACK_PEERS
        and urlparse(handler.path).path in host._CHAT_PATHS
        and host.PASSTHROUGH_AUTH_FLAG_SOURCE.enabled()
    ):
        return False
    return any(
        isinstance(adapter, host.PassthroughAdapter)
        and adapter.validate_client_token(host._extract_auth_token(handler))
        for adapter in host.BACKENDS.adapters()
    )


def _authorize(context: PostRequestContext) -> bool:
    context.hub_auth_ok = context.host._auth_ok(context.handler)
    if context.hub_auth_ok:
        return True
    if _allow_deferred_auth(context):
        context.deferred_passthrough_auth = True
        return True
    context.send_error(401, "auth_error", "unauthorized")
    return False


def _admit_drain(context: PostRequestContext) -> bool:
    handler, host = context.handler, context.host
    if context.cancel_turn_id is not None:
        return True
    if not (host._shutting_down or (host._is_drain_enabled() and host.LIFECYCLE.is_draining())):
        return True
    is_sub = handler._is_subagent_request()
    hold_ok = False
    if not host._shutting_down:
        hold_ok = host.LIFECYCLE.wait_for_drain_hold(is_subagent=is_sub)
    if not host._shutting_down and hold_ok and not host.LIFECYCLE.is_draining():
        return True
    code, headers, body = host.LIFECYCLE.draining_response(is_subagent=is_sub)
    error = body.get("error", {})
    handler._reject(
        code, error.get("type", "overloaded"),
        error.get("message", "bridge is shutting down"), extra_headers=headers,
    )
    return False


def _serve_control_endpoint(context: PostRequestContext) -> bool:
    handler, host = context.handler, context.host
    path = urlparse(handler.path).path
    if path in ("/v1/models/refresh", "/models/refresh") or re.match(
        r"^/v1/providers/[^/]+/v1/models/refresh$", path,
    ):
        handler._handle_models_refresh()
        return True
    if context.path != "/v1/quarantine":
        return False
    if not host._auth_ok(handler):
        context.send_error(401, "auth_error", "unauthorized", close=False)
    else:
        handler._handle_quarantine_post()
    return True


def begin_post(handler: PostHandler, host: PostHost) -> PostRequestContext | None:
    """Инициализирует POST; None означает уже отправленный ранний ответ."""
    handler._headers_already_sent = False
    handler._trace = None
    handler._response_status = 0
    handler._telemetry_begin()
    context = PostRequestContext(handler, host)
    match = re.fullmatch(r"/v1/turns/([^/]+)/cancel", context.path) if (
        host._is_detached_enabled()
    ) else None
    context.cancel_turn_id = match.group(1) if match is not None else None
    if not _authorize(context) or not _admit_drain(context):
        return None
    if _serve_control_endpoint(context):
        return None
    handler._trace = None
    handler._response_status = 0
    host._enforce_forward_kill_switch()
    handler._active_managed_turn = None
    handler._context_pruned = None
    return context

__all__ = ('clean_transport_request', '_allow_deferred_auth', '_authorize', '_admit_drain', '_serve_control_endpoint', 'begin_post')
