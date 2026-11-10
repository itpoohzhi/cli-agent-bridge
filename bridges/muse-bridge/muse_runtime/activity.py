from __future__ import annotations

import json
from typing import Callable, Any


def message_has_useful_data(msg: Any) -> bool:
    """Determine whether a parsed Muse serve message contains useful data.

    Useful messages are those that carry payload fields such as text
    content, tool calls, or explicit result data and are not pure
    control/keepalive/assignment notifications.
    """
    if not isinstance(msg, dict):
        return False

    if "error" in msg:
        return True

    msg_type = msg.get("type")
    if isinstance(msg_type, str) and msg_type.lower() in {
        "keepalive",
        "heartbeat",
        "ping",
        "pong",
        "assignment",
        "assign",
        "ready",
    }:
        return False

    for key in (
        "result",
        "content",
        "delta",
        "text",
        "tool_calls",
        "tool_call",
        "data",
        "output",
    ):
        value = msg.get(key)
        if value is None:
            continue
        if isinstance(value, (str, list, dict)) and len(value) > 0:
            return True
        if isinstance(value, (int, float, bool)):
            return True

    return False


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
