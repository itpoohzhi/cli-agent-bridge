"""Модуль дренажа шага serve с контекстом исполнения и безопасным прерыванием."""

from __future__ import annotations

import http.client
import queue
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DrainContext:
    """Контекст параметров и обратных вызовов для дренажа шага модели."""

    events: queue.Queue[dict[str, object] | None]
    session_id: str
    assistant_message_id: object
    deadline: float
    usage: dict[str, int]
    tool_state: Any
    result: dict[str, Any]
    on_tool: Callable[[dict[str, object]], None]
    release_event: Callable[[dict[str, object]], None]
    attempt_deadline: float | None = None
    is_client_gone: Callable[[], bool] | None = None
    pending_calls: list[dict[str, object]] | None = None
    ctrl_http: Callable[[str, str, dict[str, object] | None], tuple[int, dict[str, object]]] | None = None
    reasoning_cb: Callable[[str], None] | None = None
    text_cb: Callable[[str], None] | None = None
    emulate_tools: bool = False
    accumulated_bytes: list[int] | None = None
    t0: float = 0.0
    replied_permissions: set[str] = field(default_factory=set)
    cascade_reject_state: dict[str, bool] = field(default_factory=lambda: {"succeeded": False})
    as_dict_fn: Callable[[Any], dict[str, object]] = dict
    as_int_fn: Callable[[Any], int] = int
    map_serve_event_fn: Callable[[dict[str, object]], tuple[str, dict[str, object]] | None] | None = None
    serve_accumulated_bytes_fn: Callable[[int, str, dict[str, object], Any], int] | None = None
    is_transient_error_fn: Callable[[dict[str, object]], bool] | None = None
    protocol_error_cls: type[Exception] = Exception
    disconnect_error_cls: type[Exception] = Exception
    security_error_cls: type[Exception] = Exception
    unavailable_error_cls: type[Exception] = Exception
    deadline_error_cls: type[Exception] = Exception
    step_drain_window_s: float = 1.0
    stall_timeout_s: float = 30.0

    def __post_init__(self) -> None:
        if self.replied_permissions is None:
            self.replied_permissions = set()
        if self.cascade_reject_state is None:
            self.cascade_reject_state = {"succeeded": False}
        if self.pending_calls is None:
            self.pending_calls = []
        if self.usage is None:
            self.usage = {}


def _drain_handle_permission(
    payload: dict[str, object],
    session_id: str,
    replied_perms: set[str],
    cascade_state: dict[str, bool],
    ctrl_quiet_fn: Callable[[str], None],
    ctrl_http: Callable[[str, str, dict[str, object] | None], tuple[int, dict[str, object]]] | None,
    security_error_cls: type[Exception],
    err_classes: tuple[type[Exception], ...],
) -> None:
    """Обработать запрос прав на выполнение инструмента с безопасным откатом."""
    request_id = str(payload.get("id") or "").strip()
    if not request_id:
        ctrl_quiet_fn(f"/api/session/{session_id}/interrupt")
        raise security_error_cls("permission reject failed")
    if request_id in replied_perms:
        return
    reject_failed = ctrl_http is None
    if ctrl_http is not None:
        try:
            status, _ = ctrl_http("POST", f"/api/session/{session_id}/permission/{request_id}/reply", {"decision": "reject"})
            if status in (200, 204):
                cascade_state["succeeded"] = True
                replied_perms.add(request_id)
                reject_failed = False
            elif status == 404 and cascade_state.get("succeeded"):
                replied_perms.add(request_id)
                reject_failed = False
            else:
                reject_failed = True
        except err_classes:
            reject_failed = True
    if reject_failed:
        ctrl_quiet_fn(f"/api/session/{session_id}/interrupt")
        raise security_error_cls("permission reject failed")


def _drain_handle_content(
    mapped_kind: str,
    payload: dict[str, object],
    result: dict[str, Any],
    t0: float,
    reasoning_cb: Callable[[str], None] | None,
    text_cb: Callable[[str], None] | None,
) -> None:
    """Зафиксировать дельты текста или мыслей и тайминги TTFT."""
    is_reasoning = mapped_kind == "reasoning"
    key = "reasoning_content" if is_reasoning else "content"
    val = str(payload.get(key) or "")
    if not val:
        return
    if result["first_token_at"] is None and t0:
        result["first_token_at"] = time.monotonic()
        result["ttft_ms"] = int(((result["first_token_at"] or 0.0) - t0) * 1000)
    target = result["reasonings"] if is_reasoning else result["texts"]
    target.append(val)
    cb = reasoning_cb if is_reasoning else text_cb
    if cb is not None:
        cb(val)


def _drain_handle_step_finish(
    payload: dict[str, object],
    event_type: str,
    tool_state: Any,
    pending: list[dict[str, object]],
    usage: dict[str, int],
    result: dict[str, Any],
    on_tool: Callable[[dict[str, object]], None],
    as_int_fn: Callable[[Any], int],
    deliver_pending: bool,
) -> bool:
    """Финализировать шаг модели: агрегация usage и эмиссия накопленных вызовов."""
    if result["error"] is not None:
        return False
    for call_id in list(tool_state.tools):
        done = tool_state.complete(call_id, event_type)
        if done is not None:
            pending.append(done[1])
    for key in ("input", "output", "cached", "reasoning"):
        usage[key] = usage.get(key, 0) + as_int_fn(payload.get(key))
    if deliver_pending:
        for call in pending:
            result["native_calls"].append(call)
            on_tool(call)
    return True


def _filter_drain_event(
    event: dict[str, object],
    ctx: DrainContext,
    ctrl_quiet: Callable[[str], None],
) -> tuple[bool, str, dict[str, object]]:
    """Проверить принадлежность события шагу и валидность протокола."""
    ev_type = str(event.get("type") or "")
    if ev_type == "__invalid_json__":
        raise ctx.protocol_error_cls("invalid event while draining tool step")
    data = ctx.as_dict_fn(event.get("data"))
    if ev_type == "form.created":
        form = ctx.as_dict_fn(data.get("form"))
        if (form.get("sessionID") or data.get("sessionID")) == ctx.session_id:
            fid = form.get("id") or data.get("id")
            if isinstance(fid, str) and fid:
                ctrl_quiet(f"/api/session/{ctx.session_id}/form/{fid}/cancel")
            ctrl_quiet(f"/api/session/{ctx.session_id}/interrupt")
            raise ctx.security_error_cls("serve requested interactive form during tool drain")
        return False, ev_type, data
    sid = data.get("sessionID")
    if (sid != ctx.session_id and not (sid is None and ev_type in ("permission.asked", "permission.replied", "session.execution.failed", "session.step.failed"))):
        return False, ev_type, data
    ev_msg_id = data.get("assistantMessageID") or data.get("messageID")
    if ctx.assistant_message_id and ev_msg_id and ev_msg_id != ctx.assistant_message_id:
        return False, ev_type, data
    return True, ev_type, data


def _dispatch_drain_event(
    event: dict[str, object],
    ctx: DrainContext,
    pending: list[dict[str, object]],
    ctrl_quiet: Callable[[str], None],
    check_bytes: Callable[[str, dict[str, object]], None],
    err_classes: tuple[type[Exception], ...],
) -> tuple[bool, bool | None]:
    """Диспетчеризировать событие: вернуть (should_continue, finished_bool)."""
    ok, ev_type, _data = _filter_drain_event(event, ctx, ctrl_quiet)
    if not ok:
        return True, None
    mapped = ctx.map_serve_event_fn(event) if ctx.map_serve_event_fn else None
    if mapped is None:
        return True, None
    kind, payload = mapped
    if kind == "permission_replied":
        ctx.replied_permissions.add(str(payload.get("id") or "").strip())
    elif kind == "permission":
        _drain_handle_permission(payload, ctx.session_id, ctx.replied_permissions, ctx.cascade_reject_state, ctrl_quiet, ctx.ctrl_http, ctx.security_error_cls, err_classes)
    elif kind == "error":
        ctx.result["error"] = payload
        ctx.result["transient_error"] = ctx.is_transient_error_fn(payload) if ctx.is_transient_error_fn else False
        ctx.result["terminal"] = "failed"
        return False, False
    elif kind in ("reasoning", "text"):
        check_bytes(kind, payload)
        _drain_handle_content(kind, payload, ctx.result, ctx.t0, ctx.reasoning_cb, ctx.text_cb)
    elif kind == "tool_event":
        ctx.tool_state.feed(payload)
        check_bytes("tool_event", {})
        if ev_type in ("session.tool.called", "session.tool.failed", "session.tool.success"):
            done = ctx.tool_state.complete(str(payload.get("id") or ""), ev_type)
            if done is not None:
                pending.append(done[1])
    elif kind == "step_finish":
        res = _drain_handle_step_finish(payload, ev_type, ctx.tool_state, pending, ctx.usage, ctx.result, ctx.on_tool, ctx.as_int_fn, ctx.pending_calls is None)
        return False, res
    return True, None


def _poll_drain_event(
    events: queue.Queue[dict[str, object] | None], wait_deadline: float
) -> tuple[bool, dict[str, object] | None]:
    """Опросить очередь событий до дедлайна с коротким квантом ожидания."""
    try:
        return True, events.get(timeout=min(0.05, max(0.0, wait_deadline - time.monotonic())))
    except queue.Empty:
        return time.monotonic() < wait_deadline, None


def _drain_serve_step_usage(
    events: queue.Queue[dict[str, object] | None],
    session_id: str,
    assistant_message_id: object,
    deadline: float,
    usage: dict[str, int],
    tool_state: Any,
    result: dict[str, Any],
    on_tool: Callable[[dict[str, object]], None],
    release_event: Callable[[dict[str, object]], None],
    **kwargs: Any,
) -> bool:
    """Дочитать все события шага до подтверждённого конца того же шага."""
    ctx = DrainContext(events, session_id, assistant_message_id, deadline, usage, tool_state, result, on_tool, release_event, **kwargs)
    pending = ctx.pending_calls if ctx.pending_calls is not None else []
    err_classes = (OSError, http.client.HTTPException, ctx.unavailable_error_cls, ctx.protocol_error_cls)

    def _check_bytes(kind: str, payload: dict[str, object]) -> None:
        if ctx.serve_accumulated_bytes_fn:
            acc = ctx.accumulated_bytes[0] if ctx.accumulated_bytes else 0
            res = ctx.serve_accumulated_bytes_fn(acc, kind, payload, ctx.tool_state)
            if ctx.accumulated_bytes:
                ctx.accumulated_bytes[0] = res

    def _ctrl_quiet(path: str) -> None:
        if ctx.ctrl_http:
            try:
                _ = ctx.ctrl_http("POST", path, None)
            except (OSError, http.client.HTTPException, ctx.unavailable_error_cls, ctx.protocol_error_cls, ctx.disconnect_error_cls, ctx.deadline_error_cls):
                pass

    wait_deadline = min(ctx.attempt_deadline if ctx.attempt_deadline is not None else ctx.deadline, ctx.deadline)
    while time.monotonic() < wait_deadline:
        if ctx.is_client_gone and ctx.is_client_gone():
            raise ctx.disconnect_error_cls("client disconnected")
        alive, event = _poll_drain_event(ctx.events, wait_deadline)
        if not alive:
            return False
        if event is None:
            continue
        ctx.release_event(event)
        if ctx.is_client_gone and ctx.is_client_gone():
            raise ctx.disconnect_error_cls("client disconnected")
        if ctx.step_drain_window_s and ctx.step_drain_window_s > 0:
            wait_deadline = min(time.monotonic() + ctx.step_drain_window_s, ctx.deadline)
        cont, finished = _dispatch_drain_event(event, ctx, pending, _ctrl_quiet, _check_bytes, err_classes)
        if not cont:
            return bool(finished)
    return False
