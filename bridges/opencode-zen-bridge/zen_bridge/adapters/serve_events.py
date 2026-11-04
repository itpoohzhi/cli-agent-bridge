"""Функции чтения SSE-событий serve и финализации шага инструментов."""

from __future__ import annotations

import http.client
import json
import queue
import threading
from collections.abc import Callable
from typing import Any

_MAX_SSE_LINE_BYTES = 1024 * 1024
_MAX_SERVE_QUEUE_BYTES = 16 * 1024 * 1024
_MAX_SERVE_ACCUMULATED_BYTES = 16 * 1024 * 1024


def _parse_sse_line_payload(
    line: bytes,
    cur_max_line: int,
    loads_serve_object_fn: Callable[[str], dict[str, object] | None] | None,
    protocol_error_cls: type[Exception],
) -> tuple[bool, dict[str, object] | None]:
    """Разбирает одну строку SSE, возвращая (keep_going, parsed_object)."""
    if len(line) > cur_max_line:
        return False, {"type": "__invalid_json__", "data": {}}
    text_line = line.decode("utf-8", "replace").strip()
    if not text_line.startswith("data:"):
        return True, None
    payload = text_line[5:].strip()
    if not payload or payload == "[DONE]":
        return True, None
    try:
        obj = (
            loads_serve_object_fn(payload)
            if loads_serve_object_fn is not None
            else json.loads(payload)
        )
        return True, obj
    except protocol_error_cls:
        return True, {"type": "__invalid_json__", "data": {}}


def _put_event_with_stop(
    events: queue.Queue[dict[str, object] | None],
    item: dict[str, object] | None,
    stop_event: threading.Event,
) -> bool:
    """Неблокирующая постановка с проверкой stop_event."""
    while not stop_event.is_set():
        try:
            events.put(item, timeout=0.25)
            return True
        except queue.Full:
            continue
    return False


def _read_serve_events(
    sse_resp: http.client.HTTPResponse,
    events: queue.Queue[dict[str, object] | None],
    stop_event: threading.Event,
    queued_bytes: list[int],
    queue_bytes_lock: threading.Lock,
    release_event: Callable[[dict[str, object]], None],
    loads_serve_object_fn: Callable[[str], dict[str, object] | None] | None = None,
    protocol_error_cls: type[Exception] = Exception,
    max_line_bytes_fn: Callable[[], int] | None = None,
    max_queue_bytes_fn: Callable[[], int] | None = None,
) -> None:
    """Читать SSE с ограничением байтов очереди в пределах одной попытки."""
    try:
        while not stop_event.is_set():
            max_line = max_line_bytes_fn() if max_line_bytes_fn else _MAX_SSE_LINE_BYTES
            max_queue = max_queue_bytes_fn() if max_queue_bytes_fn else _MAX_SERVE_QUEUE_BYTES
            try:
                line = sse_resp.readline(max_line + 1)
            except (OSError, ValueError, AttributeError, http.client.HTTPException):
                break
            if not line:
                break
            keep, obj = _parse_sse_line_payload(line, max_line, loads_serve_object_fn, protocol_error_cls)
            if not keep:
                _put_event_with_stop(events, obj, stop_event)
                break
            if obj is None:
                continue
            with queue_bytes_lock:
                overflow = queued_bytes[0] + len(line) > max_queue
                if not overflow:
                    queued_bytes[0] += len(line)
                    obj["_raw_bytes"] = len(line)
            if overflow:
                _put_event_with_stop(events, {"type": "__invalid_json__", "data": {}}, stop_event)
                break
            if not _put_event_with_stop(events, obj, stop_event):
                release_event(obj)
                break
    except (OSError, ValueError, AttributeError, http.client.HTTPException):
        pass
    finally:
        _put_event_with_stop(events, None, stop_event)


def _serve_step_message_id(
    data: dict[str, object], session_id: str, step_closed: bool, current: str
) -> str:
    """Запомнить ID только открытого шага текущей сессии."""
    msg_id = data.get("assistantMessageID")
    if (
        data.get("sessionID") == session_id
        and not step_closed
        and isinstance(msg_id, str)
        and msg_id
    ):
        return msg_id
    return current


def _serve_tool_state_bytes(tool_state: Any) -> int:
    """UTF-8 объём ID, имён, text и сериализованных input native вызовов."""
    total = 0
    tools = getattr(tool_state, "tools", {})
    for call_id, item in tools.items():
        total += len(str(call_id).encode("utf-8", "replace"))
        total += len(str(item.get("name", "")).encode("utf-8", "replace"))
        total += len(str(item.get("text", "")).encode("utf-8", "replace"))
        args = item.get("input")
        if isinstance(args, dict):
            total += len(
                json.dumps(
                    args, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8", "replace")
            )
    return total


def _serve_accumulated_bytes(
    current: int,
    event_type: str,
    payload: dict[str, object],
    tool_state: Any = None,
    protocol_error_cls: type[Exception] = Exception,
    max_accumulated_bytes_fn: Callable[[], int] | None = None,
) -> int:
    """Учесть общий UTF-8 бюджет reasoning/text и удерживаемого tool_state."""
    if event_type in ("reasoning", "text"):
        text_value = str(
            payload.get("reasoning_content" if event_type == "reasoning" else "content")
            or ""
        )
        current += len(text_value.encode("utf-8", "replace"))
    held = _serve_tool_state_bytes(tool_state) if tool_state is not None else 0
    cap = max_accumulated_bytes_fn() if max_accumulated_bytes_fn is not None else _MAX_SERVE_ACCUMULATED_BYTES
    if current + held > cap:
        raise protocol_error_cls("serve accumulated output exceeded byte cap")
    return current


def _finish_serve_tool_step(
    drain_fn: Callable[..., bool],
    events: queue.Queue[dict[str, object] | None],
    session_id: str,
    assistant_message_id: object,
    deadline: float,
    tool_state: Any,
    result: dict[str, Any],
    on_tool: Callable[[dict[str, object]], None],
    release_event: Callable[[dict[str, object]], None],
    *,
    pending_calls: list[dict[str, object]] | None = None,
    is_client_gone: Callable[[], bool] | None = None,
    protocol_error_cls: type[Exception] = Exception,
    disconnect_error_cls: type[Exception] = Exception,
    **drain_kwargs: Any,
) -> bool:
    """Закрыть инструментальный шаг только после подтверждённого step.ended."""
    confirmed = drain_fn(
        events, session_id, assistant_message_id, deadline,
        result["usage"], tool_state, result, on_tool, release_event,
        pending_calls=pending_calls, is_client_gone=is_client_gone, **drain_kwargs,
    )
    if result["error"] is not None:
        return False
    if not confirmed:
        raise protocol_error_cls("incomplete tool step without step.ended")
    if is_client_gone is not None and is_client_gone():
        raise disconnect_error_cls("client disconnected")
    if pending_calls is not None:
        for call in pending_calls:
            result["native_calls"].append(call)
            on_tool(call)
    result["terminal"] = "tool_calls"
    result["step_closed"] = True
    return True
