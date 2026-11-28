from __future__ import annotations

# Чистая сборка тела и заголовков loopback Zero-Canon proxy (allowlist, stream по запросу).

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from core.chat_key import SRC_HEADER_CHAT_ID, resolve_chat_key  # pyright: ignore[reportUnknownVariableType]
from core.native_turn_context import NativeTurnPayload
from core.subbridge_zero_canon import REVIEW_PROFILE_HEADER, ZERO_CANON_PROFILE

CHAT_ID_HEADER = "X-DSH-Chat-Id"
_PASS_HEADERS = {"x-subagent-id": "X-Subagent-Id", "authorization": "Authorization"}
_BRIDGE_KEY_ENVS = ("CLAUDE_P_BRIDGE_KEY", "CLAUDE_BRIDGE_KEY")


@dataclass(frozen=True)
class BridgeProxyOptions:
    """Опции сборки тела proxy-запроса."""

    reasoning_effort: str | None = None
    chat_id: str | None = None
    prompt_cache_key: str | None = None
    native_payload: NativeTurnPayload | None = None


def _optional_fields(options: BridgeProxyOptions) -> dict[str, object]:
    native = options.native_payload if options.native_payload else NativeTurnPayload()
    candidates: dict[str, object] = {
        "prompt_cache_key": options.prompt_cache_key if options.prompt_cache_key else native.prompt_cache_key,
        "reasoning_effort": options.reasoning_effort,
        "tools": native.to_tools_list(),
        "tool_choice": native.to_tool_choice(),
        "stream_options": native.to_stream_options(),
    }
    return {k: v for k, v in candidates.items() if bool(v)}


def build_bridge_proxy_body(
    model: str,
    prompt: str,
    options: BridgeProxyOptions | None = None,
    *,
    stream: bool = False,
) -> dict[str, object]:
    """Тело `/chat/completions`: allowlist полей; `stream=False` по умолчанию (обратная совместимость)."""
    opts = options if options else BridgeProxyOptions()
    native = opts.native_payload
    messages = native.to_messages_list() if native else []
    rendered = messages if messages else [{"role": "user", "content": prompt}]
    body = {
        "model": model,
        "messages": rendered,
        "stream": bool(stream),
        **_optional_fields(opts),
    }
    if stream:
        existing = body.get("stream_options")
        stream_options = dict(cast(dict[str, object], existing)) if isinstance(existing, dict) else {}
        stream_options["include_usage"] = True
        body["stream_options"] = stream_options
    return body


def _valid_chat_id(chat_id: str | None) -> str | None:
    raw = chat_id if chat_id else ""
    key = resolve_chat_key({}, {SRC_HEADER_CHAT_ID: raw}, sources=(SRC_HEADER_CHAT_ID,))
    val = key.value if key.keyed else None
    return val


def build_bridge_proxy_headers(
    base_headers: Mapping[str, str] | None, *, chat_id: str | None = None
) -> dict[str, str]:
    """Allowlist заголовков; невалидный/пустой `chat_id` — fail-open (без заголовка)."""
    out = {
        "Content-Type": "application/json",
        REVIEW_PROFILE_HEADER: ZERO_CANON_PROFILE,
    }
    hdrs = base_headers if base_headers else {}
    for name, value in hdrs.items():
        target = _PASS_HEADERS.get(name.lower())
        if target:
            if value:
                out[target] = value
    env_key = next((v for n in _BRIDGE_KEY_ENVS if (v := os.environ.get(n))), "")
    if env_key:
        out["Authorization"] = f"Bearer {env_key}"
    valid = _valid_chat_id(chat_id)
    if valid:
        out[CHAT_ID_HEADER] = valid
    return out
