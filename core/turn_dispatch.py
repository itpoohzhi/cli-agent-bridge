"""Изолированный контекст схем инструментов и диспетчеризация хода адаптера."""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, replace
from typing import Any

from core.backend_adapter import (
    ImageAttachment,
    ToolCall,
    Transcript,
    TranscriptItem,
    TurnContext,
)
from core.runtime_env import synthesize_required_bash_desc_enabled
from core.turn_usage_result import turn_usage_of
from core.usage_fields import enrich_turn_usage_dict

_UNBOUND: object = object()
_TURN_OMIT_KEYS = frozenset(
    {
        "rpc",
        "request_id",
        "subagent_id",
        "images",
        "attached_existing",
        "on_activity",
        "register_pgid",
        "cancel_event",
    }
)


class ToolSchemaScope:
    """Владелец потоко- и корутино-изолированного ``ContextVar`` схем инструментов."""

    def __init__(self) -> None:
        self._schemas_var: ContextVar[Any] = ContextVar(
            "active_request_tool_schemas", default=_UNBOUND
        )

    @classmethod
    def _owner(cls) -> "ToolSchemaScope":
        return _TOOL_SCHEMA_SCOPE

    @classmethod
    @contextmanager
    def bind(cls, schemas: dict[str, Any] | None) -> Iterator[None]:
        token = cls.set_current(schemas)
        try:
            yield
        finally:
            cls.reset_current(token)

    @classmethod
    def set_current(cls, schemas: dict[str, Any] | None) -> Token[Any]:
        return cls._owner()._schemas_var.set(schemas)

    @classmethod
    def reset_current(cls, token: Token[Any]) -> None:
        cls._owner()._schemas_var.reset(token)

    @classmethod
    def get_current(cls) -> dict[str, Any] | None:
        value = cls._owner()._schemas_var.get()
        return None if value is _UNBOUND else value

    @classmethod
    def update_if_bound(cls, schemas: dict[str, Any] | None) -> None:
        if cls._owner()._schemas_var.get() is not _UNBOUND:
            cls._owner()._schemas_var.set(schemas)


_TOOL_SCHEMA_SCOPE = ToolSchemaScope()


def _server_module(handler: Any) -> Any:
    mod = sys.modules.get(type(handler).__module__)
    if mod is not None and hasattr(mod, "BACKENDS"):
        return mod
    return sys.modules.get("server")


def _try_attached_replay(ctx: dict[str, Any], managed_turn: Any, srv: Any) -> dict[str, Any] | None:
    if not (ctx.get("attached_existing") and managed_turn is not None):
        return None
    eff_fn = getattr(srv, "_effective_turn_timeout_s", None)
    eff_to = eff_fn() if callable(eff_fn) else getattr(srv, "TIMEOUT_S", 1800)
    managed_turn.done_event.wait(timeout=eff_to)
    if managed_turn.final_dict is not None:
        return dict(managed_turn.final_dict)
    return None


def _build_turn_context(
    handler: Any, ctx: dict[str, Any], keepalive: Any, managed_turn: Any, adapter_id: str
) -> TurnContext:
    srv = _server_module(handler)
    transcript = ctx["rpc"]
    turn_manager = getattr(srv, "TURN_MANAGER", None)
    client_gone_fn = getattr(srv, "_client_gone", lambda _conn: False)
    register_pgid = ctx.get("register_pgid") or (
        (lambda pgid: turn_manager.register_child_pgid(pgid, backend=adapter_id, turn_id=getattr(managed_turn, "turn_id", "")))
        if managed_turn is not None and getattr(managed_turn, "turn_id", None) is not None and turn_manager is not None
        else None
    )
    cancel_event = ctx.get("cancel_event") or (getattr(managed_turn, "cancel_event", None) if managed_turn is not None else None)
    on_activity = ctx.get("on_activity") or (getattr(managed_turn, "touch_activity", None) if managed_turn is not None else None)
    return TurnContext(
        **{k: v for k, v in ctx.items() if k not in _TURN_OMIT_KEYS},
        rpc=Transcript(
            system=transcript["system"],
            runnable=transcript["runnable"],
            items=tuple(TranscriptItem(**item) for item in transcript["items"]),
        ),
        images=tuple(ImageAttachment(**img) for img in ctx["images"]),
        handler=handler,
        keepalive=keepalive,
        client_gone=lambda: client_gone_fn(handler.connection),
        on_activity=on_activity,
        register_pgid=register_pgid,
        cancel_event=cancel_event,
    )


def _sanitize_result_calls(result: Any, turn: TurnContext, srv: Any) -> Any:
    if not getattr(srv, "BRIDGE_SANITIZE_TOOL_CALLS", True):
        return result
    sanitize_fn = srv.sanitize_tool_call
    limits = dict(getattr(srv, "_SANITIZE_LIMITS", {}))
    synth = synthesize_required_bash_desc_enabled()
    calls: list[ToolCall] = []
    by_id: dict[str, list[ToolCall]] = {}
    for call in result.tool_calls:
        cleaned = [
            replace(item, index=len(calls) + index)
            for index, item in enumerate(
                sanitize_fn(call, turn.tool_schemas, **limits, synthesize_required_description=synth)
            )
        ]
        by_id[call.id] = cleaned
        calls.extend(cleaned)
    events = tuple(
        item
        for event in result.events or ()
        for item in (
            [replace(event, value=call) for call in by_id[event.value.id]]
            if event.kind == "tool_call" and isinstance(event.value, ToolCall)
            else [event]
        )
    )
    return replace(result, tool_calls=tuple(calls), events=events)


def _format_turn_output(result: Any, backend_kind: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "state": result.state,
        "rc": result.rc,
        "text": result.text,
        "reasoning": result.reasoning,
        "err": result.err,
        "usage": asdict(result.usage),
        "result": {},
        "tool_calls": [asdict(call) for call in result.tool_calls],
        "events": [
            (ev.kind, asdict(ev.value) if not isinstance(ev.value, str) else ev.value)
            for ev in result.events or ()
        ],
        "backend_kind": backend_kind,
    }
    if (turn_usage := turn_usage_of(result)) is not None:
        out["usage"] = enrich_turn_usage_dict(out["usage"], turn_usage)
        out["turn_usage"] = turn_usage
    return out


def dispatch_turn(
    handler: Any, ctx: dict[str, Any], keepalive: Any, sse_writer: Any = None
) -> dict[str, Any]:
    """Выполнить ход через адаптер, нормализовать ``tool_calls`` и оформить DTO фасада."""
    srv = _server_module(handler)
    managed_turn = ctx.get("managed_turn") or getattr(handler, "_active_managed_turn", None)
    if (replay := _try_attached_replay(ctx, managed_turn, srv)) is not None:
        return replay
    adapter = srv.BACKENDS.get(ctx["backend"])
    if adapter is None:
        return {"state": "launcher_unavailable", "rc": 1, "text": "", "usage": {}, "result": {}, "err": "", "tool_calls": [], "events": []}
    turn = _build_turn_context(handler, ctx, keepalive, managed_turn, getattr(adapter, "id", ""))
    t0 = time.monotonic()
    with ToolSchemaScope.bind(turn.tool_schemas):
        raw_turn_result = adapter.execute_turn(turn, sse_writer)
    limits = srv.PassthroughLimits.from_env()
    result = srv.finalize_turn(
        raw_turn_result,
        turn.emulate_tools,
        tool_schemas=turn.tool_schemas,
        invoke_normalization_enabled=limits.invoke_normalization_enabled,
        repetition_guard_enabled=limits.repetition_guard_enabled,
    )
    result = _sanitize_result_calls(result, turn, srv)
    if managed_turn is not None:
        srv.TURN_MANAGER.complete_turn_from_result(managed_turn, result, backend_kind=adapter.kind)
    out = _format_turn_output(result, adapter.kind)
    if adapter.kind != "droid":
        srv._log(
            f"done model={ctx['model']} backend={adapter.id} rc={out.get('rc')} "
            f"state={out.get('state')} out_bytes={len(str(out.get('text') or '').encode())} "
            f"wall_s={time.monotonic() - t0:.1f} "
            f"err_bytes={len(str(out.get('err') or '').encode())} {ctx['tag']}"
        )
    return out
