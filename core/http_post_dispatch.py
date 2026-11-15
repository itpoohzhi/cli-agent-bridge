"""Исполнение разрешённого POST через поздно связанные порты host."""

from __future__ import annotations

from functools import partial
from typing import Any

from core.http_post_routing import (
    PostRoute, PreparedPostBody, log_route, native_autonomy, native_effort,
    prepare_post_body, prepare_route_request,
)

_NATIVE_SCRATCH = frozenset({"requested_turn_id", "resume_turn_id", "messages", "raw_key", "keyed"})


def _passthrough(route: PostRoute, adapter: Any, body: PreparedPostBody | None) -> None:
    host, handler = route.host, route.handler
    if host.passthrough_autonomy_validation_enabled(True):
        try:
            host.validate_autonomy_request(route.request.get("autonomy"))
        except host.AutonomyViolation as error:
            route.reject(400, error.reason, str(error))
            return
    if route.raw_model != route.model_id and route.alias is None:
        handler._reject(400, "model_not_allowed", "passthrough requires an exact model id")
        return
    body = body if body is not None else prepare_post_body(route)
    if host.flag_enabled("BRIDGE_TRANSPORT_ROUTING_ENABLED"):
        prepared = prepare_route_request(
            dict(body.request), route.model, route.model_id, route.alias_effort,
        )
    else:
        prepared, effort = host.prepare_passthrough_request(
            dict(body.request), route.model, route.model_id, route.alias, route.alias_effort,
            host.flag_enabled(host.FLAG_EFFORT_CATALOG),
        )
        if effort.clamped_from is not None:
            host._log(host.describe_clamp(
                "passthrough reasoning_effort", effort.clamped_from, effort.value,
                route.model_id, host._LOG_EFFORT_MAX,
            ))
    raw = body.raw if prepared == body.request else host.json.dumps(
        prepared, ensure_ascii=False,
    ).encode("utf-8")
    log_route(route, "passthrough")
    handler._serve_resilient(route.model["backend"], partial(
        handler._serve_passthrough, adapter, raw, prepared, route.model_id,
        _hub_auth_ok=route.ingress.hub_auth_ok,
    ))


def _native_parameters(route: PostRoute) -> dict[str, Any] | None:
    effort = native_effort(route)
    if effort is None:
        return None
    autonomy = native_autonomy(route)
    if autonomy is None:
        return None
    if route.request.get("reasoning") is not None:
        route.reject(400, "unsupported_parameter", "reasoning parameter is not supported")
        return None
    return {
        "model": route.model_id,
        "target_model": route.host.resolve_target_model(route.model, route.model_id),
        "backend": route.model["backend"],
        "model_len": route.model_len,
        "effort": effort[0],
        "effort_source": effort[1],
        "autonomy": autonomy[0],
        "autonomy_source": autonomy[1],
    }


def _native_backend(route: PostRoute) -> Any:
    adapter = route.host.BACKENDS.get(route.model["backend"])
    ok, why = (False, "backend_disabled") if adapter is None else adapter.preflight()
    if not ok:
        route.reject(503, "launcher_unavailable",
                     "canonical launcher is missing or not executable"
                     if why == "launcher_unavailable"
                     else f"backend {route.model['backend']} is unavailable: {why}")
        return None
    return adapter


def _turn_ids(route: PostRoute, ctx: dict[str, Any], extra: dict[str, Any]) -> bool:
    handler, host = route.handler, route.host
    ctx["requested_turn_id"] = (
        handler.headers.get("X-Turn-Id") or str(extra.get("turn_id") or "")
    ).strip()
    ctx["resume_turn_id"] = (
        handler.headers.get("X-Resume-Turn-Id") or str(extra.get("resume_turn_id") or "")
    ).strip()
    for candidate in (ctx["requested_turn_id"], ctx["resume_turn_id"]):
        if candidate and not host.validate_turn_id(candidate):
            route.reject(400, "invalid_request", "invalid turn_id")
            return False
    return True


def _native_inputs(route: PostRoute, ctx: dict[str, Any]) -> Any:
    handler, host = route.handler, route.host
    gated = handler._context_gate(route.request, route.model_id, route.model, route.model_len)
    if gated is None:
        return None
    route.request, handler._context_pruned = gated
    try:
        ctx["images"] = host._collect_images(route.request, route.model, ctx["effort"])
    except host.ImageReject as error:
        route.reject(400, error.reason, f"image rejected: {error.reason}")
        return None
    adapter = _native_backend(route)
    if adapter is None:
        return None
    extra = route.request.get("extra_body")
    extra = extra if isinstance(extra, dict) else {}
    ctx["cwd"] = str(extra.get("cwd") or "")
    ctx["fwd_env"] = handler._forwarded_env(extra, route.model_id, route.model_len)
    return adapter if ctx["fwd_env"] is not False and _turn_ids(route, ctx, extra) else None


def _native_tools(route: PostRoute, ctx: dict[str, Any]) -> list[dict[str, Any]]:
    request, host = route.request, route.host
    messages = request.get("messages")
    ctx["messages"] = messages if isinstance(messages, list) else []
    raw_tools = request.get("tools")
    tools = (
        [item for item in raw_tools if isinstance(item, dict)]
        if isinstance(raw_tools, list) else []
    )
    ctx["emulate_tools"] = bool(tools) and not host._tool_choice_none(request.get("tool_choice"))
    ctx["tool_schemas"] = host.build_tool_schemas(raw_tools)
    return tools


def _render_native(route: PostRoute, ctx: dict[str, Any], adapter: Any) -> bool:
    request, host, handler = route.request, route.host, route.handler
    tools = _native_tools(route, ctx)
    choice, images = request.get("tool_choice"), ctx["images"]
    chat = host.resolve_chat_key(
        request, namespace=host.RPC_NAMESPACE, sources=host.SOURCES_CACHE_KEY_ONLY, lenient=True,
    )
    ctx["raw_key"] = chat.value if chat.keyed else request.get("prompt_cache_key")
    ctx["keyed"], ctx["route"] = chat.keyed, chat.route
    if images or host._is_title_request(ctx["messages"], tools, request):
        ctx["route"] = "image" if images else "title"
    overhead = host.compute_tools_budget_overhead(tools, choice, bool(images))
    handler._instr_truncated = False
    instr = handler._prompt_guard(
        ctx["messages"], ctx["route"], ctx["raw_key"], ctx["cwd"],
        route.model_id, route.model_len, adapter, overhead,
    )
    if instr is None:
        return False
    ctx["prompt"] = host._messages_to_prompt(ctx["messages"], tools, choice, images)
    transcript = host._transcribe(ctx["messages"], tools, choice, images)
    if not transcript["runnable"]:
        if ctx["route"] not in ("image", "title"):
            ctx["route"] = "fallback"
        transcript = {"system": None, "runnable": True, "items": [{
            "role": "user", "text": ctx["prompt"], "digest": host._digest(ctx["prompt"]),
        }]}
    ctx["rpc"] = transcript
    ctx["instr"] = instr if ctx["route"] in ("keyed", "nokey") else (0, "-", 0)
    return True

__all__ = ('_passthrough', '_native_parameters', '_native_backend', '_turn_ids', '_native_inputs', '_native_tools', '_render_native')
