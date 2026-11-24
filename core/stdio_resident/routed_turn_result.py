"""Typed RoutedTurnResult, loopback Zero-Canon proxy, and routed turn execution."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from typing import Any

from core.stdio_resident.turn_error_sse import (
    DONE_FRAME,
    ResidentTurnError,
    TurnErrorResponse,
    build_turn_error,
)
from core.subbridge_zero_canon import (
    REVIEW_PROFILE_HEADER,
    ZERO_CANON_PROFILE,
    is_zero_canon_profile,
)
from core.turn_usage import TurnUsage
from core.usage_wire import build_turn_wire_usage, positive_wire_usage, turn_usage_from_wire

KIND_RESIDENT, KIND_BRIDGE, KIND_EPHEMERAL = "resident", "bridge", "ephemeral"


@dataclass(frozen=True, slots=True)
class RoutedTurnResult:
    """Routed turn output carrying typed TurnUsage without wire round-trip loss."""

    text: str
    reasoning: str
    usage: TurnUsage | None = None


@dataclass(frozen=True, slots=True)
class ProxyBridgeOptions:
    """Configuration bundle for local loopback Zero-Canon bridge proxy."""

    validate_url_fn: Callable[[str], str]
    resolve_timeout_fn: Callable[[float | None], float]
    opener_factory: Callable[..., Any] = urllib.request.build_opener
    timeout_s: float | None = None
    usage_enabled: bool = True


@dataclass(frozen=True, slots=True)
class RoutedExecOptions:
    """Execution options bundle for routed resident turns."""

    bridge_proxy_fn: Callable[..., RoutedTurnResult]
    headers: Mapping[str, str] | None = None
    usage_enabled: bool = True


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        raise urllib.error.HTTPError(newurl, code, f"redirect blocked ({msg})", headers, fp)


def _build_proxy_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    req_headers: dict[str, str] = {
        "Content-Type": "application/json",
        REVIEW_PROFILE_HEADER: ZERO_CANON_PROFILE,
    }
    if headers:
        for key, value in headers.items():
            if key.lower() == "x-subagent-id" and value:
                req_headers["X-Subagent-Id"] = value
    bridge_key = os.environ.get("CLAUDE_P_BRIDGE_KEY") or os.environ.get("CLAUDE_BRIDGE_KEY") or ""
    if bridge_key:
        req_headers["Authorization"] = f"Bearer {bridge_key}"
    return req_headers


def _parse_proxy_response(parsed: object, usage_enabled: bool) -> RoutedTurnResult:
    if not isinstance(parsed, dict):
        return RoutedTurnResult("", "", None)
    usage = (
        turn_usage_from_wire(parsed.get("usage"), "claude_zero_canon_bridge")
        if usage_enabled
        else None
    )
    choices = parsed.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    msg = first.get("message") if isinstance(first, dict) else None
    if not isinstance(msg, dict):
        return RoutedTurnResult("", "", usage)
    return RoutedTurnResult(
        str(msg.get("content") or ""), str(msg.get("reasoning_content") or ""), usage
    )


def proxy_zero_canon_bridge_turn_result(
    base_url: str,
    model: str,
    prompt: str,
    headers: Mapping[str, str] | None,
    options: ProxyBridgeOptions,
) -> RoutedTurnResult:
    """Proxy a Zero-Canon Claude turn to local :9881 and preserve OpenAI wire usage."""
    effective_timeout = options.resolve_timeout_fn(options.timeout_s)
    url = options.validate_url_fn(base_url) + "/chat/completions"
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=_build_proxy_headers(headers), method="POST")
    opener = options.opener_factory(urllib.request.ProxyHandler({}), _NoRedirectHandler())
    with opener.open(req, timeout=effective_timeout) as resp:
        parsed = json.loads(resp.read().decode("utf-8"))
    return _parse_proxy_response(parsed, options.usage_enabled)


def build_routed_turn_error(exc: BaseException, live_sent: int) -> TurnErrorResponse:
    """Build sanitized TurnErrorResponse for routed resident errors."""
    if isinstance(exc, RuntimeError) and str(exc).startswith("zero_canon_unsupported_by_driver:"):
        status = 503 if not live_sent else 200
        code, message = "zero_canon_unsupported_by_driver", str(exc)[:500]
        body: dict[str, object] = {"error": {"message": message, "type": "zero_canon_unsupported", "code": code}}
        sse = "data: " + json.dumps(body, ensure_ascii=False) + "\n\n" + DONE_FRAME
        return TurnErrorResponse(status, "zero_canon_unsupported", code, message, sse, body)
    return build_turn_error(exc, live_sent=live_sent)


def _attach_error_usage(
    err: TurnErrorResponse, usage: TurnUsage | None, live_sent: int
) -> ResidentTurnError:
    resp = err
    if usage is not None and live_sent > 0:
        wire = positive_wire_usage(build_turn_wire_usage(usage))
        if wire is not None:
            body = {**err.body, "usage": wire}
            sse = "data: " + json.dumps(body, ensure_ascii=False) + "\n\n" + DONE_FRAME
            resp = replace(err, body=body, sse=sse)
    wrapped = ResidentTurnError(resp)
    if usage is not None:
        setattr(wrapped, "turn_usage", usage)
    return wrapped


def _emit_part(
    kind: str,
    value: str,
    parts: dict[str, list[str]],
    sse_writer: Callable[[str, str], Any] | None,
    live_sent: int,
) -> int:
    parts[kind].append(value)
    if sse_writer is not None:
        _ = sse_writer(kind, value)
        return live_sent + 1
    return live_sent


def _run_bridge_route(
    route: Any,
    request: dict[str, Any],
    sse_writer: Callable[[str, str], Any] | None,
    options: RoutedExecOptions,
) -> RoutedTurnResult:
    parts: dict[str, list[str]] = {"content": [], "reasoning_content": []}
    live_sent = 0
    proxied = options.bridge_proxy_fn(
        route.base_url,
        str(request.get("model") or "default"),
        str(request.get("prompt") or ""),
        options.headers,
        usage_enabled=options.usage_enabled,
    )
    if proxied.text:
        live_sent = _emit_part("content", proxied.text, parts, sse_writer, live_sent)
    if proxied.reasoning:
        live_sent = _emit_part("reasoning_content", proxied.reasoning, parts, sse_writer, live_sent)
    return RoutedTurnResult(
        "".join(parts["content"]), "".join(parts["reasoning_content"]),
        proxied.usage if options.usage_enabled else None,
    )


def _extract_chunk_usage(chunk: Mapping[str, Any], enabled: bool) -> TurnUsage | None:
    if enabled and isinstance(raw_u := chunk.get("usage"), Mapping):
        return turn_usage_from_wire(raw_u, "stdio_resident_chat")
    return None


def _pick_last_usage(
    sink: list[TurnUsage], fallback: TurnUsage | None, enabled: bool
) -> TurnUsage | None:
    if not enabled:
        return None
    return sink[-1] if sink else fallback


def _consume_delta(
    delta: Mapping[str, Any],
    parts: dict[str, list[str]],
    sse_writer: Callable[[str, str], Any] | None,
    live_sent: int,
) -> int:
    for field_name in ("content", "reasoning_content"):
        if isinstance(val := delta.get(field_name), str):
            live_sent = _emit_part(field_name, val, parts, sse_writer, live_sent)
    return live_sent


def execute_routed_turn_result(
    execute_chat: Callable[[dict[str, Any]], Iterator[dict[str, Any]]],
    route: Any,
    request: dict[str, Any],
    sse_writer: Callable[[str, str], Any] | None,
    options: RoutedExecOptions,
) -> RoutedTurnResult:
    """Execute routed turn preserving lossless TurnUsage on success and mid-stream error."""
    parts: dict[str, list[str]] = {"content": [], "reasoning_content": []}
    live_sent, usage_sink, wire_fallback = 0, [], None
    try:
        if route.kind == KIND_BRIDGE:
            return _run_bridge_route(route, request, sse_writer, options)
        if is_zero_canon_profile(str(request.get("review_profile") or "")) and route.kind == KIND_RESIDENT:
            raise RuntimeError("zero_canon_resident_route_forbidden")
        routed_req: dict[str, Any] = {
            **request,
            "is_ephemeral": bool(request.get("is_ephemeral")) or route.is_ephemeral,
            "_usage_enabled": options.usage_enabled,
            "_turn_usage_sink": usage_sink,
        }
        for chunk in execute_chat(routed_req):
            if (parsed_u := _extract_chunk_usage(chunk, options.usage_enabled)) is not None:
                wire_fallback = parsed_u
            live_sent = _consume_delta(chunk["choices"][0]["delta"], parts, sse_writer, live_sent)
    except Exception as exc:
        last_u = _pick_last_usage(usage_sink, wire_fallback, options.usage_enabled)
        raise _attach_error_usage(build_routed_turn_error(exc, live_sent), last_u, live_sent) from exc
    final_u = _pick_last_usage(usage_sink, wire_fallback, options.usage_enabled)
    return RoutedTurnResult("".join(parts["content"]), "".join(parts["reasoning_content"]), final_u)
