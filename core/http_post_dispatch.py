"""Исполнение разрешённого POST через поздно связанные порты host."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

from core import passthrough_effort_map as _pem
from core.http_post_context import PostRequestContext
from core.http_post_ingress import begin_post, read_post_request
from core.http_post_routing import PostRoute, PreparedPostBody, log_route, native_autonomy, native_effort, prepare_post_body, prepare_route_request, resolve_post_route, selected_route_allowed
from core.native_turn_context import build_native_turn_payload, native_payload_scope
from core.param_adapter import ThinkingBudgetConfigError, clamp_thinking_budget
from core.resident_identity import turn_ids_and_resident_ctx

_NATIVE_SCRATCH = frozenset({"requested_turn_id", "resume_turn_id", "messages", "raw_key", "keyed"})


def _apply_passthrough_transforms(
    prepared: dict[str, Any], route: PostRoute, body: PreparedPostBody, adapter: Any
) -> dict[str, Any]:
    bid = str(route.model.get("backend") or "")
    out = _pem.apply_prepared_off_patch(prepared, body.request, route.request, adapter, bid)
    return clamp_thinking_budget(_pem.drop_thinking_keep_effort(out) if _pem.drops_thinking_route(adapter, bid) else out)


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
    try:
        if host.flag_enabled("BRIDGE_TRANSPORT_ROUTING_ENABLED"):
            prepared = prepare_route_request(
                dict(body.request), route.model, route.model_id, route.alias_effort,
            )
        else:
            prepared = _prepare_legacy_passthrough(route, body)
        prepared = _apply_passthrough_transforms(prepared, route, body, adapter)
    except host.EffortValidationError as exc:
        route.reject(400, "unsupported_reasoning_effort", str(exc))
        return
    except ThinkingBudgetConfigError as exc:
        route.reject(400, "invalid_request", str(exc))
        return
    raw = body.raw if prepared == body.request else host.json.dumps(prepared, ensure_ascii=False).encode("utf-8")
    log_route(route, "passthrough")
    handler._serve_resilient(route.model["backend"], partial(
        handler._serve_passthrough, adapter, raw, prepared, route.model_id, _hub_auth_ok=route.ingress.hub_auth_ok))


def _prepare_legacy_passthrough(route: PostRoute, body: PreparedPostBody) -> dict[str, Any]:
    host = route.host
    opts = host.PassthroughOptions(alias=route.alias, alias_effort=route.alias_effort, effort_on=host.flag_enabled(host.FLAG_EFFORT_CATALOG))
    prepared, effort = host.prepare_passthrough_request(dict(body.request), route.model, route.model_id, opts)
    if effort.clamped_from is not None:
        host._log(host.describe_clamp("passthrough reasoning_effort", effort.clamped_from, effort.value, route.model_id, host._LOG_EFFORT_MAX))
    return prepared


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
    valid = turn_ids_and_resident_ctx(route, ctx, extra, adapter=adapter)
    return adapter if ctx["fwd_env"] is not False and valid else None


def _native_tools(route: PostRoute, ctx: dict[str, Any]) -> list[dict[str, Any]]:
    request, host = route.request, route.host
    messages = request.get("messages")
    ctx["messages"] = messages if isinstance(messages, list) else []
    raw_tools = request.get("tools")
    tools = [item for item in raw_tools if isinstance(item, dict)] if isinstance(raw_tools, list) else []
    ctx["native_payload"] = build_native_turn_payload(request)
    ctx["emulate_tools"] = bool(tools) and not host._tool_choice_none(request.get("tool_choice"))
    ctx["tool_schemas"] = host.build_tool_schemas(raw_tools)
    return tools


def _render_native(route: PostRoute, ctx: dict[str, Any], adapter: Any) -> bool:
    request, host, handler = route.request, route.host, route.handler
    tools = _native_tools(route, ctx)
    choice, images = request.get("tool_choice"), ctx["images"]
    chat = host.resolve_chat_key(request, namespace=host.RPC_NAMESPACE, sources=host.SOURCES_CACHE_KEY_ONLY, lenient=True)
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


def _legacy_muse_sleep(route: PostRoute, ctx: dict[str, Any], adapter: Any) -> bool:
    # Существующее транспортное исключение; новая общая политика здесь не вводится.
    if route.model["backend"] != "muse" or any((
        ctx["requested_turn_id"], ctx["resume_turn_id"], ctx["keyed"],
    )):
        return False
    mode = Path(getattr(adapter, "wrapper", "")).parent / "mode"
    return mode.is_file() and mode.read_text(encoding="utf-8", errors="ignore").strip() == "sleep"


def _detach_native(route: PostRoute, ctx: dict[str, Any], adapter: Any) -> bool:
    host = route.host
    return (
        host._is_detached_enabled()
        and (host._client_gone is host._DEFAULT_CLIENT_GONE
             or bool(ctx["requested_turn_id"] or ctx["resume_turn_id"]))
        and not _legacy_muse_sleep(route, ctx, adapter)
    )


def _create_turn(route: PostRoute, ctx: dict[str, Any]) -> tuple[Any, bool]:
    handler = route.handler
    return route.host.TURN_MANAGER.create_or_attach_turn(
        model=route.model_id, backend=route.model["backend"], cwd=ctx["cwd"],
        messages=ctx["messages"], session_id=ctx["raw_key"] if ctx["keyed"] else "",
        owner_token_hash=route.host._owner_token_hash(handler),
        requested_turn_id=ctx["requested_turn_id"] or None,
        resume_turn_id=ctx["resume_turn_id"] or None, stream=bool(route.request.get("stream")),
        emulate_tools=ctx["emulate_tools"], idle_timeout_s=handler._effective_idle_timeout_s(),
        safety_cap_s=handler._effective_safety_cap_s(),
    )


def _attach_native(route: PostRoute, ctx: dict[str, Any], adapter: Any) -> bool:
    host, handler = route.host, route.handler
    ctx["detach_on_disconnect"] = _detach_native(route, ctx, adapter)
    ctx["managed_turn"], ctx["attached_existing"] = None, False
    if host._is_detached_enabled():
        try:
            ctx["managed_turn"], ctx["attached_existing"] = _create_turn(route, ctx)
        except PermissionError:
            return route.reject(403, "forbidden", "turn belongs to another token")
        except ValueError as error:
            return route.reject(400, "invalid_request", str(error))
    managed = ctx["managed_turn"]
    handler._active_managed_turn = managed
    if managed is not None:
        managed.is_subagent = handler._is_subagent_request()
        managed.subagent_id = handler._subagent_id()
    ctx["turn_id"] = managed.turn_id if managed is not None else ""
    return True


def _serve_native(route: PostRoute, ctx: dict[str, Any]) -> None:
    handler, host = route.handler, route.host
    ctx["request_id"] = handler._trace.request_id if handler._trace else None
    ctx["subagent_id"] = handler._trace.subagent_id if handler._trace else None
    ctx["key_hash"] = host._key_hash(ctx["raw_key"]) if (
        ctx["route"] == "keyed" and isinstance(ctx["raw_key"], str)
    ) else ""
    ctx["tag"] = f"client={handler._client_tag()} ua={(handler.headers.get('User-Agent') or '-')[:60]}"
    ctx["stream"] = bool(route.request.get("stream"))
    log_route(route, "cli")
    turn_ctx = {k: v for k, v in ctx.items() if k not in _NATIVE_SCRATCH}
    serve = partial(handler._serve_sse if ctx["stream"] else handler._serve_json, turn_ctx)
    if ctx["attached_existing"]:
        # Уже идущий ход не создаёт новой попытки и не требует нового допуска.
        serve()
    else:
        handler._serve_resilient(route.model["backend"], serve)


def _run_native_scoped(route: PostRoute, ctx: dict[str, Any], adapter: Any) -> None:
    with native_payload_scope(ctx.pop("native_payload", None)):
        if _attach_native(route, ctx, adapter):
            _serve_native(route, ctx)


def dispatch_route(route: PostRoute, body: PreparedPostBody | None = None) -> None:
    """Разделяет raw passthrough и CLI, не повторяя исполненный POST."""
    if not selected_route_allowed(route):
        return
    adapter = route.host.BACKENDS.get(route.model["backend"])
    if isinstance(adapter, route.host.PassthroughAdapter):
        _passthrough(route, adapter, body)
        return
    ctx = _native_parameters(route)
    if ctx is None:
        return
    adapter = _native_inputs(route, ctx)
    if adapter is None or not _render_native(route, ctx, adapter):
        return
    try:
        _run_native_scoped(route, ctx, adapter)
    finally:
        managed = ctx.get("managed_turn")
        if managed is not None and not ctx["attached_existing"] and managed.is_active:
            route.host.TURN_MANAGER.finalize_abandoned_turn(managed)


def _cleanup_post(context: PostRequestContext) -> None:
    handler: Any = context.handler
    host: Any = context.host
    handler._active_managed_turn = None
    try:
        context.release_body()
    finally:
        host._DELIVERY_BUDGET.release(handler._delivery_reserved)
        handler._delivery_reserved = 0


def dispatch_post(context: PostRequestContext) -> None:
    """Владеет общим cleanup принятого тела, в том числе при раннем отказе."""
    try:
        route = resolve_post_route(context)
        if route is not None:
            dispatch_route(route)
    finally:
        _cleanup_post(context)


def handle_post(handler: Any, host: Any) -> None:
    """Точка композиции для короткого do_POST, без обратного импорта server."""
    context = begin_post(handler, host)
    if context is None:
        return
    accepted = False
    try:
        accepted = read_post_request(context)
        if accepted:
            dispatch_post(context)
    finally:
        if not accepted:
            _cleanup_post(context)
