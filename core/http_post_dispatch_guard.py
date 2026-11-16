"""Первичный допуск POST: ограниченный envelope и политика notes из памяти."""

from __future__ import annotations
from io import BytesIO
from typing import Any
from core import http_post_ingress as ingress
from core.http_post_context import PostRequestContext

def read_envelope(context: PostRequestContext) -> bool:
    """Кэширует исходный JSON один раз; резерв остаётся у контекста до cleanup."""
    cached = getattr(context, "_ingress_envelope_ok", None)
    if cached is not None:
        return bool(cached)
    setattr(context, "_ingress_envelope_ok", False)
    if not ingress._admit_body(context):
        return False
    try:
        length = context.content_length
        raw = context.handler.rfile.read(length) if length else b""
        if len(raw) < length:
            context.handler._reject(400, "invalid_request", "request body truncated")
            return False
        request = ingress.json.loads(raw.decode("utf-8")) if (
            raw or context.path.endswith(("/chat/completions", "/messages"))
        ) else {}
        if not isinstance(request, dict):
            context.handler._reject(400, "invalid_request", "request must be a JSON object")
            return False
        context.prepare_route(raw, request)
        setattr(context, "_ingress_envelope_ok", True)
        return True
    except (ValueError, UnicodeDecodeError):
        context.handler._reject(400, "invalid_request", "invalid json")
        return False
    finally:
        if not getattr(context, "_ingress_envelope_ok"):
            context.release_body()

def _notes_allowed(context: PostRequestContext, model: str, transport: str | None, effort: Any) -> bool:
    host: Any = context.host
    notes = getattr(host, "_MODEL_NOTES_FILTER", None)
    if notes is None or getattr(notes, "is_failed_closed", lambda: False)():
        return False
    if transport is not None and hasattr(notes, "is_failed_closed"):
        effort = host.FLEET.get("models", {}).get(model, {}).get("default_effort") if effort is None else effort
        return not notes.is_blocked(model, transport, effort)
    if notes.is_blocked(model):
        return False
    resolver = getattr(host, "_resolve_model_alias", lambda *_: None)
    alias = resolver(model, host.FLEET.get("models", {}))
    canonical = alias[0] if isinstance(alias, (tuple, list)) else alias
    return not canonical or not notes.is_blocked(canonical)

def enforce_ingress(
    context: PostRequestContext, model_id: str | None = None,
    transport: str | None = None, effort: Any = None, request: dict[str, Any] | None = None,
) -> bool:
    """Отказывает до выбора/попытки; probe сильнее notes, bypass не учитывается."""
    headers = context.handler.headers
    if any(str(key).lower() in {"x-probe", "x-bridge-probe"} for key in headers):
        context.release_body()
        context.send_error(400, "invalid_request_error", "probe controls are reserved")
        return False
    if request is None:
        if not read_envelope(context):
            return False
        request = context.request
    if "is_probe" in request:
        context.release_body()
        context.send_error(400, "invalid_request_error", "probe controls are reserved")
        return False
    host: Any = context.host
    model = model_id or request.get("model") or getattr(host, "MODEL_ID", "")
    if _notes_allowed(context, str(model).strip(), transport, effort):
        return True
    context.release_body()
    context.send_error(503, "notes_unavailable", "model notes do not permit dispatch")
    return False

def begin_post(handler: Any, host: Any) -> PostRequestContext | None:
    """Проверяет envelope до прежнего auth/drain/control ingress без второго read."""
    handler._headers_already_sent, handler._trace, handler._response_status = False, None, 0
    context = PostRequestContext(handler, host)
    stream = handler.rfile
    try:
        if not enforce_ingress(context):
            return None
        handler.rfile = BytesIO(context.raw)
        started = ingress.begin_post(handler, host)
        if started is not None:
            for name in ("cancel_turn_id", "hub_auth_ok", "deferred_passthrough_auth"):
                setattr(context, name, getattr(started, name))
            return context
    except BaseException:
        context.release_body()
        raise
    finally:
        handler.rfile = stream
    context.release_body()
    return None

def read_post_request(context: PostRequestContext) -> bool:
    """Продолжает ingress из кэша, сохраняя telemetry, controls и cancel-контракт."""
    if not enforce_ingress(context):
        return False
    if context.cancel_turn_id is not None:
        ingress._cancel_turn(context)
        return False
    if not context.raw:
        context.handler._reject(400, "invalid_request", "invalid json")
        return False
    handler, host = context.handler, context.host
    request = context.request
    handler._parsed_req = request
    handler._telemetry_meta_request(request)
    handler._trace = host._resolve_trace(dict(handler.headers.items()), request) if (
        host.REQUEST_ATTRIBUTION_ENABLED
    ) else None
    context.consume_controls()
    return ingress._resolve_chat_path(context)
