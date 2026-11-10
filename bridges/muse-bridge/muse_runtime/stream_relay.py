from __future__ import annotations

import json
import os
import math
import threading
import time
from _thread import LockType
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol, cast


class _Writer(Protocol):
    def write(self, data: memoryview) -> Optional[int]: ...

    def flush(self) -> None: ...


def _default_write_timeout_s() -> float:
    try:
        return float(os.environ.get("MUSE_STREAM_WRITE_TIMEOUT_S", "30.0"))
    except (TypeError, ValueError):
        return 30.0


@dataclass(frozen=True)
class StreamRelayConfig:
    """Пределы буферизации, ожидания записи и периода keepalive."""

    chunk_size: int = 1024
    keepalive_interval_s: float = 15.0
    write_timeout_s: float = field(default_factory=_default_write_timeout_s)

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("Размер блока должен быть положительным")
        for value in (self.keepalive_interval_s, self.write_timeout_s):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Интервалы должны быть положительными и конечными")


class StreamRelay:
    """Сериализует SSE-записи с ограниченным ожиданием.

    Блокирующий wfile обслуживается отдельным потоком, удерживающим lock
    до завершения операции. При тайм-ауте уже начавшийся системный вызов
    нельзя отменить, но новые потоки записи не накапливаются.
    """

    def __init__(
        self,
        wfile: Any = None,
        lock: LockType | None = None,
        config: StreamRelayConfig | None = None,
        on_disconnect: Callable[[], None] | None = None,
    ) -> None:
        self.config: StreamRelayConfig = config or StreamRelayConfig()
        self._writer = cast(Optional[_Writer], wfile)
        self._lock = lock if lock is not None else threading.Lock()
        self._state_lock = threading.Lock()
        self._on_disconnect = on_disconnect
        self.disconnected = False
        self._phase = "OPEN"
        self._last_activity = time.monotonic()
        self._last_keepalive = self._last_activity

    @property
    def is_disconnected(self) -> bool:
        with self._state_lock:
            return self.disconnected

    @property
    def keepalive_due(self) -> bool:
        """Позволяет внешнему планировщику определить необходимость ping."""
        with self._state_lock:
            return (
                self._phase == "OPEN"
                and not self.disconnected
                and time.monotonic() - max(self._last_activity, self._last_keepalive)
                >= self.config.keepalive_interval_s
            )

    def _inactive(self) -> bool:
        with self._state_lock:
            return self.disconnected or self._phase == "CLOSED"

    def _disconnect(self) -> None:
        with self._state_lock:
            if self.disconnected:
                return
            self.disconnected = True
            self._phase = "CLOSED"
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
        finish_reason: str | None = None,
    ) -> Dict[str, Any]:
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {"index": 0, "delta": delta, "finish_reason": finish_reason}
            ],
        }

    def write_frame(
        self, data: str, fatal: bool = True, keepalive: bool = False
    ) -> bool:
        """Пишет кадр под общей блокировкой без полной байтовой копии."""
        if self._inactive():
            return False
        deadline = time.monotonic() + self.config.write_timeout_s
        if not self._lock.acquire(timeout=self.config.write_timeout_s):
            if fatal:
                self._disconnect()
            return False
        if self._inactive():
            self._lock.release()
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
                        if self._inactive() or time.monotonic() >= deadline:
                            raise TimeoutError("Истек срок записи")
                        count = writer.write(view)
                        if count is None:
                            break
                        if count <= 0 or count > len(view):
                            raise OSError("Некорректная длина записи")
                        view = view[count:]
                if self._inactive() or time.monotonic() >= deadline:
                    raise TimeoutError("Истек срок записи")
                writer.flush()
                with self._state_lock:
                    if not self.disconnected and self._phase == "OPEN":
                        now = time.monotonic()
                        if keepalive:
                            self._last_keepalive = now
                        else:
                            self._last_activity = now
                        if data == "data: [DONE]\n\n":
                            self._phase = "CLOSED"
                        success = True
            except (BrokenPipeError, ConnectionResetError, OSError, TimeoutError):
                if fatal:
                    self._disconnect()
            finally:
                self._lock.release()
                finished.set()

        worker = threading.Thread(target=write, daemon=True, name="muse-sse-write")
        try:
            worker.start()
        except RuntimeError:
            self._lock.release()
            if fatal:
                self._disconnect()
            return False
        if not finished.wait(max(0.0, deadline - time.monotonic())):
            if fatal:
                self._disconnect()
            return False
        return success

    def emit_chunk(
        self,
        completion_id: str,
        model: str,
        delta: Dict[str, Any],
        finish_reason: str | None = None,
    ) -> bool:
        if self._inactive():
            return False
        payload = self.format_chunk(completion_id, model, delta, finish_reason)
        return self.write_frame(
            "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
        )

    def emit_done(self) -> bool:
        return self.write_frame("data: [DONE]\n\n")

    def emit_ping(self, data: str = "ping") -> bool:
        """Передает SSE-комментарий; периодичностью управляет вызывающий код."""
        if self._inactive():
            return False
        text = data.replace("\r\n", "\n").replace("\r", "\n")
        return self.write_frame(
            ": " + text.replace("\n", "\n: ") + "\n\n", keepalive=True
        )

    def close(self) -> None:
        """Закрывает фазу передачи, сохраняя владение сокетом у сервера."""
        with self._state_lock:
            self._phase = "CLOSED"
