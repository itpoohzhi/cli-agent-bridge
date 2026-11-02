"""Shared OpenAI-compatible stream error framing and SSE serialization."""

import json
import os
import re
import time
from typing import Any, Mapping, Optional, Union


def sanitize_error_message(message: str) -> str:
    """Redact credentials, tokens, and local user directories."""
    # 1. Redact credentials in URLs/DSNs (e.g. postgres://user:pass@host, http://user:pass@host, https://token@host)
    message = re.sub(
        r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^:\s/@]+):([^@\s/]+)@",
        r"\1***:***@",
        message,
    )
    message = re.sub(
        r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^@\s/:]+)@",
        r"\1***@",
        message,
    )
    # 2. Redact Bearer tokens (case-insensitive, greedy for token characters)
    message = re.sub(
        r"(?i)\bBearer\s+[a-zA-Z0-9_\-\.\+/=~]+",
        "Bearer ***",
        message,
    )
    # 3. Redact Basic authentication tokens
    message = re.sub(
        r"(?i)\bBasic\s+[a-zA-Z0-9_\-\.\+/=~]+",
        "Basic ***",
        message,
    )
    # 4. Redact OpenAI sk-*, Google AIza*, and AWS AKIA* keys
    message = re.sub(
        r"\bsk-[a-zA-Z0-9_\-\.\+/=~]+",
        "sk-***",
        message,
    )
    message = re.sub(
        r"\bAIza[0-9A-Za-z-_]{35}\b",
        "AIza***",
        message,
    )
    message = re.sub(
        r"\bAKIA[0-9A-Z]{16}\b",
        "AKIA***",
        message,
    )
    # 5. Redact credentials in key-value pairs (JSON, Python dicts, query params, headers)
    # Handles both quoted multi-word values (with spaces) and unquoted tokens.
    pattern = re.compile(
        r"""(?ix)
        (?P<quote>[\x27\x22])?
        (?P<key>[a-zA-Z0-9_-]*(?:api[_-]?key|passwd|password|pwd|client[_-]?secret|private[_-]?key|access[_-]?key|secret[_-]?key|secret|token|credential)[a-zA-Z0-9_-]*)
        (?P=quote)?
        \s*[:=]\s*
        (?:
            (?P<vquote>[\x27\x22])(?P<qval>[^\x27\x22]*)(?P=vquote)
            |
            (?P<uval>[^\s\x27\x22<>;&,}{]+)
        )
        """
    )
    message = pattern.sub(r"\g<key>=***", message)
    # 6. Redact local macOS and Linux user home paths (with or without trailing slash)
    message = re.sub(
        r"/(?:Users|home)/[^/\s]+(?=/|\b|\s|$)",
        "~",
        message,
    )
    return message


def is_graceful_error_framing_enabled() -> bool:
    """Read the kill-switch at call time, defaulting to graceful framing."""
    return os.getenv("BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED", "true").strip().lower() in (
        "true",
        "1",
        "yes",
    )


def build_stream_error_chunk(
    message: str,
    model: Optional[str] = None,
    code: str = "stream_error",
    error_type: str = "stream_error",
    finish_reason: Optional[str] = ...,  # type: ignore[assignment]
    completion_id: Optional[str] = None,
    created: Optional[int] = None,
    choice_indices: Optional[list[int]] = None,
) -> dict:
    """Build an error chunk, distinguishing omitted finish_reason from None."""
    sanitized_msg = sanitize_error_message(message)
    graceful = is_graceful_error_framing_enabled()
    if finish_reason is ...:
        finish_reason = "stop" if graceful else None

    if finish_reason == "stop":
        content = f"\n\n[⚠️ Ошибка шлюза: {sanitized_msg}]"
    else:
        content = ""

    now = int(time.time())
    if choice_indices is not None and len(choice_indices) == 0:
        choices = []
    else:
        indices = choice_indices if choice_indices is not None else [0]
        choices = []
        for idx in indices:
            delta: dict[str, Any] = {}
            if content:
                delta["content"] = content
            choices.append(
                {
                    "index": idx,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            )

    return {
        "id": completion_id if completion_id is not None else f"chatcmpl-err-{now}",
        "object": "chat.completion.chunk",
        "created": created if created is not None else now,
        "model": model if model is not None else "bridge-stream",
        "choices": choices,
        "error": {
            "message": sanitized_msg,
            "type": error_type,
            "code": code,
            "param": None,
        },
    }


def format_sse_event(
    data: Union[dict, str],
    event: Optional[str] = None,
) -> str:
    """Serialize one SSE event, including its terminating blank line."""
    payload = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else data
    payload = payload.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    if event is not None:
        sanitized_event = event.replace("\r", "").replace("\n", "")
        lines.append(f"event: {sanitized_event}")
    lines.extend(f"data: {line}" for line in payload.split("\n"))
    return "\n".join(lines) + "\n\n"


def format_stream_error_sse(
    message: str,
    model: Optional[str] = None,
    code: str = "stream_error",
    error_type: str = "stream_error",
    finish_reason: Optional[str] = ...,  # type: ignore[assignment]
    completion_id: Optional[str] = None,
    created: Optional[int] = None,
    choice_indices: Optional[list[int]] = None,
) -> str:
    """Serialize a terminal error chunk followed by the SSE DONE marker."""
    chunk = build_stream_error_chunk(
        message=message,
        model=model,
        code=code,
        error_type=error_type,
        finish_reason=finish_reason,
        completion_id=completion_id,
        created=created,
        choice_indices=choice_indices,
    )
    return format_sse_event(chunk) + format_sse_event("[DONE]")
