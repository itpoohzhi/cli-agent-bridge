from __future__ import annotations

import json
from typing import Any, Callable, Mapping


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def message_has_useful_data(msg: Any) -> bool:
    if not isinstance(msg, Mapping):
        return False
    for k in ("content", "reasoning_content", "tool_calls"):
        if _is_non_empty(msg.get(k)):
            return True
    for container in ("params", "event"):
        p = msg.get(container)
        if isinstance(p, Mapping):
            for k in ("content", "reasoning_content", "tool_calls", "text"):
                if _is_non_empty(p.get(k)):
                    return True
            delta = p.get("delta")
            if isinstance(delta, Mapping):
                for k in ("content", "reasoning_content", "tool_calls", "text"):
                    if _is_non_empty(delta.get(k)):
                        return True
            elif isinstance(delta, str) and delta.strip():
                return True
    return False


def touch_activity(activity: Any, msg: Any) -> bool:
    if activity is None:
        return False
    if not message_has_useful_data(msg):
        return False
    activity.touch()
    return True


class MuseServeMessageReader:
    def __init__(self, on_useful_chunk: Callable[[], None] | None = None) -> None:
        self.on_useful_chunk = on_useful_chunk
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> list[str]:
        self._buf.extend(chunk)
        lines = []
        while True:
            nl = self._buf.find(b"\n")
            if nl < 0:
                break
            raw_line = bytes(self._buf[:nl]).decode("utf-8", "replace").strip()
            del self._buf[: nl + 1]
            if not raw_line:
                continue
            try:
                msg = json.loads(raw_line)
                if message_has_useful_data(msg) and self.on_useful_chunk:
                    self.on_useful_chunk()
                lines.append(raw_line)
            except ValueError:
                continue
        return lines

    def flush(self) -> list[str]:
        if not self._buf:
            return []
        raw_line = bytes(self._buf).decode("utf-8", "replace").strip()
        self._buf.clear()
        if not raw_line:
            return []
        try:
            msg = json.loads(raw_line)
            if message_has_useful_data(msg) and self.on_useful_chunk:
                self.on_useful_chunk()
            return [raw_line]
        except ValueError:
            return []
