from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, cast


class _Writer(Protocol):
    def write(self, data: memoryview) -> Optional[int]: ...

    def flush(self) -> None: ...


@dataclass(frozen=True)
class StreamRelayConfig:
    """Пределы буферизации, ожидания записи и периода keepalive."""

    chunk_size: int = 1024
    keepalive_interval_s: float = 15.0
    write_timeout_s: float = 5.0

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("Размер блока должен быть положительным")
        for value in (self.keepalive_interval_s, self.write_timeout_s):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Интервалы должны быть положительными и конечными")


class StreamRelay:
    """Передает SSE блоками, не владея сокетом вызывающей стороны.

    Ожидание произвольного блокирующего wfile ограничивается отдельным
    потоком. При тайм-ауте сокет больше не используется; уже начавшийся
    системный вызов может завершиться позднее. Одновременно работает
    не более одного потока записи.
    """

    def __init__(
        self,
        wfile: Any = None,
        config: StreamRelayConfig | None = None,
        on_disconnect: Callable[[], None] | None = None,
    ) -> None:
        self.config: StreamRelayConfig = config or StreamRelayConfig()
        self._writer = cast(Optional[_Writer], wfile)
        self._on_disconnect = on_disconnect
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self.disconnected = False
        self._closed = False
        self._last_activity = time.monotonic()

    @property
    def is_disconnected(self) -> bool:
        with self._state_lock:
            return self.disconnected

    @property
    def keepalive_due(self) -> bool:
        """Позволяет внешнему планировщику определить необходимость ping."""
        with self._state_lock:
            return (
                not self._closed
                and not self.disconnected
                and time.monotonic() - self._last_activity
                >= self.config.keepalive_interval_s
            )

    def _inactive(self) -> bool:
        with self._state_lock:
            return self._closed or self.disconnected

    def _disconnect(self) -> None:
        with self._state_lock:
            if self.disconnected:
                return
            self.disconnected = True
            callback = self._on_disconnect
        if callback is not None:
            try:
                callback()
            except Exception:
                pass

    def format_chunk(
        self,
        completion_id: str,
        model: str,
        delta: Dict[str, Any],
        finish: str | None = None,
        usage: Dict[str, Any] | None = None,
        conversation_id: str = "",
    ) -> str:
        payload: Dict[str, Any] = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        if usage is not None:
            payload["usage"] = usage
        if conversation_id:
            payload["conversation_id"] = conversation_id
        return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"

    def emit(self, data: str) -> bool:
        """Пишет ограниченными блоками и ожидает не дольше заданного срока."""
        if self._inactive():
            return False
        deadline = time.monotonic() + self.config.write_timeout_s
        if not self._write_lock.acquire(timeout=self.config.write_timeout_s):
            self._disconnect()
            return False
        if self._inactive():
            self._write_lock.release()
            return False
        finished = threading.Event()
        success = False

        def write() -> None:
            nonlocal success
            try:
                writer = self._writer
                if writer is None:
                    raise OSError("Поток записи не задан")
                for offset in range(0, len(data), self.config.chunk_size):
                    block = data[offset : offset + self.config.chunk_size].encode("utf-8")
                    view = memoryview(block)
                    while view:
                        if self._inactive():
                            return
                        count = writer.write(view)
                        if count is None:
                            break
                        if count <= 0 or count > len(view):
                            raise OSError("Некорректная длина записи")
                        view = view[count:]
                if self._inactive():
                    return
                writer.flush()
                with self._state_lock:
                    if not self.disconnected and not self._closed:
                        self._last_activity = time.monotonic()
                        success = True
            except (BrokenPipeError, ConnectionResetError, OSError, TimeoutError):
                self._disconnect()
            finally:
                self._write_lock.release()
                finished.set()

        worker = threading.Thread(target=write, daemon=True, name="agy-sse-write")
        try:
            worker.start()
        except RuntimeError:
            self._write_lock.release()
            self._disconnect()
            return False
        if not finished.wait(max(0.0, deadline - time.monotonic())):
            self._disconnect()
            return False
        return success

    def emit_chunk(
        self,
        completion_id: str,
        model: str,
        delta: Dict[str, Any],
        finish: str | None = None,
        usage: Dict[str, Any] | None = None,
        conversation_id: str = "",
    ) -> bool:
        if self._inactive():
            return False
        return self.emit(
            self.format_chunk(completion_id, model, delta, finish, usage, conversation_id)
        )

    def emit_done(self) -> bool:
        return self.emit("data: [DONE]\n\n")

    def emit_ping(self, data: str = "ping") -> bool:
        """Передает SSE-комментарий; периодичностью управляет вызывающий код."""
        if self._inactive():
            return False
        text = data.replace("\r\n", "\n").replace("\r", "\n")
        return self.emit(": " + text.replace("\n", "\n: ") + "\n\n")

    def close(self) -> None:
        """Запрещает новые записи, не закрывая принадлежащий серверу сокет."""
        with self._state_lock:
            self._closed = True
