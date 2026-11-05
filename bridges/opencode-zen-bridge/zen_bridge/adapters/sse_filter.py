"""Фильтрация SSE-кадров стриминга с защитой от пустых/усечённых ответов."""

from __future__ import annotations

import json
import os
from typing import Any


def _positive_int_val(val: object, default: int) -> int:
    try:
        n = int(str(val))
        return n if n > 0 else default
    except (ValueError, TypeError):
        return default


class _ZenSseFilter:
    """Инспекция штатных SSE-кадров без накопления текста; ошибка вместо ложного stop."""

    def __init__(self, inner: Any, prompt: str, bypass: bool, zen_error_fn: Any = None) -> None:
        self.inner = inner
        self.prompt = prompt
        self.bypass = bypass
        self.content_bytes = 0
        self.has_tools = False
        self.failed = False
        self.terminated = False
        self._zen_error_fn = zen_error_fn

    def _is_empty_upstream(self, terminal: bool) -> bool:
        min_prompt = _positive_int_val(os.environ.get("BRIDGE_ZEN_SHORT_PROMPT_BYTES"), 64)
        min_content = _positive_int_val(os.environ.get("BRIDGE_ZEN_MIN_CONTENT_BYTES"), 32)
        return (
            terminal
            and not self.failed
            and not self.has_tools
            and not self.bypass
            and len(self.prompt.encode("utf-8")) >= min_prompt
            and self.content_bytes < min_content
        )

    def _emit_empty_upstream_error(self) -> None:
        err = (
            self._zen_error_fn(502)
            if self._zen_error_fn
            else {
                "error": {
                    "message": "Empty upstream response",
                    "type": "bad_gateway",
                    "param": None,
                    "code": 502,
                }
            }
        )
        self.inner.write(
            ("data: " + json.dumps(err) + "\n\ndata: [DONE]\n\n").encode("utf-8")
        )
        self.inner.flush()
        self.failed = self.terminated = True

    def write(self, data: bytes) -> int:
        if self.terminated:
            return len(data)
        if not data.startswith(b"data:"):
            return self.inner.write(data)
        for raw in data.split(b"\n\n"):
            if not raw:
                continue
            frame = raw + b"\n\n"
            payload = raw[5:].strip() if raw.startswith(b"data:") else b""
            try:
                obj = json.loads(payload) if payload != b"[DONE]" else None
            except ValueError:
                obj = None
            terminal = payload == b"[DONE]"
            if isinstance(obj, dict):
                self.failed = self.failed or bool(obj.get("error"))
                for choice in obj.get("choices") or []:
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if isinstance(content, str):
                        self.content_bytes += len(content.encode("utf-8"))
                    self.has_tools = self.has_tools or bool(delta.get("tool_calls"))
                    terminal = terminal or bool(choice.get("finish_reason"))
            if self._is_empty_upstream(terminal):
                self._emit_empty_upstream_error()
                break
            self.inner.write(frame)
        return len(data)

    def flush(self) -> None:
        self.inner.flush()
