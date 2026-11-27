"""Механически выделенные auth, admission и чтение POST из HTTP-фасада."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from core.http_post_context import PostHandler, PostHost, PostRequestContext
from core.message_history_sanitizer import sanitize_request_payload
from core.p12_hub_cancel_seam import strip_http_message_turn_mode
from core.passthrough_autonomy import strip_passthrough_request
from core.passthrough_exchange import internal_trace_scope
from core.zero_canon_http import (
    ZERO_CANON_HEADER_VALUE,
    ZeroCanonHttpError,
    parse_review_profile_headers,
    parse_strict_review_profile,
)


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
    if "transport_seed" in clean:
        clean = dict(clean)
        del clean["transport_seed"]
        raw = json.dumps(clean, ensure_ascii=False).encode("utf-8")
    return sanitize_request_payload(raw, clean)


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
    handler = context.handler
    path = urlparse(handler.path).path
    if path in ("/v1/models/refresh", "/models/refresh") or re.match(
        r"^/v1/providers/[^/]+/v1/models/refresh$", path,
    ):
        handler._handle_models_refresh()
        return True
    return False


def begin_post(handler: PostHandler, host: PostHost) -> PostRequestContext | None:
    """Инициализирует POST; None означает уже отправленный ранний ответ."""
    strip_http_message_turn_mode(getattr(handler, "headers", None))
    handler._headers_already_sent = False
    handler._trace = None
    handler._response_status = 0
    handler._telemetry_begin()
    context = PostRequestContext(handler, host)
    if context.path == "/v1/quarantine":
        handler._handle_quarantine_post()
        return None
    match = re.fullmatch(r"/v1/turns/([^/]+)/cancel", context.path) if host._is_detached_enabled() else None
    context.cancel_turn_id = match.group(1) if match is not None else None
    if not _authorize(context) or not _admit_drain(context):
        return None
    if _serve_control_endpoint(context):
        return None
    handler._trace = None
    handler._response_status = 0
    host._enforce_forward_kill_switch()
    handler._active_managed_turn = handler._turn_mode = handler._context_pruned = None
    return context


def _content_length(context: PostRequestContext) -> int | None:
    handler = context.handler
    # (1) framing: Transfer-Encoding не поддерживаем, Content-Length строго числовой.
    if handler.headers.get_all("Transfer-Encoding") is not None:
        handler._reject(400, "invalid_request", "Transfer-Encoding is not supported")
        return None
    lengths = handler.headers.get_all("Content-Length")
    if lengths is None:
        return 0
    values = [str(value).strip() for value in lengths]
    if len(set(values)) != 1 or not re.fullmatch(r"[0-9]+", values[0]):
        handler._reject(400, "invalid_request", "invalid Content-Length")
        return None
    return int(values[0])


def _admit_body(context: PostRequestContext) -> bool:
    length = _content_length(context)
    if length is None:
        return False
    # (2) длина тела: 413 до чтения.
    limit = int((context.host.FLEET.get("image_limits") or {}).get("max_body_bytes") or 0)
    if length > limit:
        context.handler._reject(
            413, "payload_too_large", "request body exceeds the bridge limit",
        )
        return False
    # (3) admission: резерв байт по заявленному Content-Length до чтения тела.
    if not context.reserve_body(length):
        context.handler._reject(
            503, "overloaded", "bridge overloaded: body budget exhausted",
        )
        return False
    return True


def _cancel_turn(context: PostRequestContext) -> None:
    handler, host = context.handler, context.host
    turn_id = context.cancel_turn_id
    if turn_id is None:
        raise RuntimeError("missing_cancel_turn_id")
    if not host.validate_turn_id(turn_id):
        handler._reject(400, "invalid_request", "invalid turn_id")
        return
    owner_hash = host._owner_token_hash(handler)
    try:
        host.TURN_MANAGER.cancel_turn(turn_id, owner_token_hash=owner_hash)
        snapshot = host.TURN_MANAGER.get_turn_snapshot(turn_id, owner_token_hash=owner_hash)
    except KeyError:
        context.send_error(404, "not_found", f"turn not found: {turn_id}")
        return
    except PermissionError:
        context.send_error(403, "forbidden", "turn belongs to another token")
        return
    handler._send(200, snapshot)


def _serve_fallback_alias(context: PostRequestContext) -> bool:
    """Алиас цепочки fallback обслуживается до проверки каталога моделей, как в хуке upstream."""
    from core import fallback_http_hook

    handler = context.handler
    if getattr(handler, "_review_profile", None) == ZERO_CANON_HEADER_VALUE:
        if fallback_http_hook.is_alias_request(context.request):
            handler._reject(
                503,
                "zero_canon_unsupported_by_driver",
                "fallback alias is forbidden under Zero-Canon",
            )
            return True
        return False

    def upstream(adapter: Any, request: dict[str, Any], sink: Any) -> None:
        adapter.handle(
            path=handler.path, raw_body=json.dumps(request).encode("utf-8"), request=request,
            headers=dict(handler.headers.items()), sink=sink,
        )

    trace_fn: Any = getattr(context.host, "_trace_headers", None)
    trace_hdrs: list[tuple[str, str]] = list(trace_fn(handler._trace)) if callable(trace_fn) else []
    scoped = [
        *trace_hdrs,
        *(
            (name, value) for name, value in handler.headers.items()
            if name.lower() == "x-review-profile"
        ),
    ]
    with internal_trace_scope(scoped):
        return fallback_http_hook.dispatch(
            handler, context.request, context.host, upstream, context.provider_id,
        )


def _validate_review_profile(context: PostRequestContext) -> bool:
    """Строго валидирует X-Review-Profile до выбора провайдера и роутинга."""
    handler = context.handler
    try:
        profile = parse_strict_review_profile(
            parse_review_profile_headers(getattr(handler, "headers", None)),
        )
    except ZeroCanonHttpError as exc:
        handler._reject(exc.status_code, exc.code, str(exc))
        return False
    setattr(handler, "_review_profile", profile)
    return True


def _resolve_chat_path(context: PostRequestContext) -> bool:
    handler, host = context.handler, context.host
    # (7) путь.
    match = host._PROVIDER_CHAT_RE.match(context.path)
    context.provider_id = match.group(1) if match else None
    if match is not None:
        if not host._auth_ok(handler):
            context.send_error(401, "auth_error", "unauthorized")
            return False
        if context.provider_id not in host.PROVIDER_SCOPES:
            handler._reply_error(404, "Unknown provider", "invalid_request_error")
            return False
        context.path = "/v1/chat/completions"
        handler.path = "/v1/chat/completions"
    if context.path not in ("/v1/chat/completions", "/chat/completions"):
        context.send_error(404, "not_found", f"not found: {context.path}")
        return False
    if not _validate_review_profile(context):
        return False
    return not _serve_fallback_alias(context)


def _parse_request(context: PostRequestContext) -> bool:
    handler, host = context.handler, context.host
    # (5) JSON и (6) JSON-объект.
    try:
        request = json.loads(context.raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        handler._reject(400, "invalid_request", "invalid json")
        return False
    if not isinstance(request, dict):
        handler._reject(400, "invalid_request", "request must be a JSON object")
        return False
    handler._parsed_req = request
    handler._telemetry_meta_request(request)
    handler._trace = host._resolve_trace(dict(handler.headers.items()), request) if (
        host.REQUEST_ATTRIBUTION_ENABLED
    ) else None
    context.prepare_route(context.raw, request)
    context.consume_controls()
    return _resolve_chat_path(context)


def _read_request(context: PostRequestContext) -> bool:
    length = context.content_length
    context.raw = context.handler.rfile.read(length) if length else b""
    # (4) короткое тело.
    if len(context.raw) < length:
        context.handler._reject(400, "invalid_request", "request body truncated")
        return False
    if context.cancel_turn_id is not None:
        _cancel_turn(context)
        return False
    return _parse_request(context)


def read_post_request(context: PostRequestContext) -> bool:
    """Читает принятый POST; успешный dispatch затем освобождает body budget.

    False означает завершённый HTTP-ответ, включая успешную отмену хода.
    Исключение чтения/телеметрии тоже не оставляет резерв ingress.
    """
    if not _admit_body(context):
        return False
    try:
        accepted = _read_request(context)
    except BaseException:
        context.release_body()
        raise
    if not accepted:
        context.release_body()
    return accepted
