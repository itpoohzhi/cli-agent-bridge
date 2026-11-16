"""Потокобезопасный владелец записей и жизненного цикла одного SSE-запроса."""

from __future__ import annotations

import threading
import time
from typing import Any, BinaryIO, cast

from core.stream_lifecycle import StreamLifecycleTracker


class StreamGuard:
    """Собирает записи производителей; сокет обслуживает вызывающий писатель.

    Any сохраняет непрозрачный контракт записей и файлового транспорта.
    """

    def __init__(self) -> None:
        self._records: list[Any] = []  # pyright: ignore[reportExplicitAny]
        self._lock: threading.Lock = threading.Lock()
        self._closed: bool = False
        self._tracker: StreamLifecycleTracker = StreamLifecycleTracker(time.monotonic)

    def submit(
        self,
        record: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    ) -> bool:
        """Принимает запись и учитывает её активность, пока guard не закрыт."""
        with self._lock:
            if self._closed:
                return False
            self._records.append(record)
            _ = self._tracker.record_event(cast(object, record))
            return True

    def drain(self) -> list[Any]:  # pyright: ignore[reportExplicitAny]
        """Атомарно передаёт накопленные записи, сохраняя их порядок."""
        with self._lock:
            records, self._records = self._records, []
            return records

    def close(self) -> None:
        """Закрывает приём, сохраняя записи и первый терминальный исход."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            _ = self._tracker.record_terminal()
            _ = self._tracker.take_terminal()

    def send_pre_token_comment(
        self,
        wfile: Any,  # pyright: ignore[reportAny, reportExplicitAny]
        comment: bytes = b": keepalive\n\n",
    ) -> bool:
        """Пишет комментарий из потока-владельца после auth/preflight."""
        writer = cast(BinaryIO, wfile)
        with self._lock:
            if self._closed:
                return False
            try:
                _ = writer.write(comment)
                writer.flush()
            except (BrokenPipeError, ConnectionResetError):
                return False
            _ = self._tracker.record_event(comment.decode("utf-8", errors="replace"))
            return True
