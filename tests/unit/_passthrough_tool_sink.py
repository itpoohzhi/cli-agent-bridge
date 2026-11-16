"""Транспортные заглушки passthrough L1-тестов: sink и in-memory сокет."""

from __future__ import annotations

import io

from adapters.passthrough_adapter import ResponseSink


class _CollectSink(ResponseSink):
    """Настоящий интерфейс sink, без импорта HTTP-фасада и его синглтонов."""

    def __init__(self) -> None:
        self.status: int | None = None
        self.headers: list[tuple[str, str]] = []
        self.chunks: list[bytes] = []

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        assert self.status is None, "Response must start exactly once"
        self.status = status
        self.headers = headers

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    @property
    def body(self) -> bytes:
        return b"".join(self.chunks)


class _MemorySocket:
    """HTTPResponse разбирает реальные HTTP-заголовки, но сеть не открывается."""

    def __init__(self, body: bytes, stream: bool) -> None:
        media = "text/event-stream" if stream else "application/json"
        head = (
            "HTTP/1.1 200 OK\r\n"
            f"Content-Type: {media}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        self.buffer = io.BytesIO(head + body)

    def makefile(self, mode: str) -> io.BytesIO:
        assert mode == "rb"
        return self.buffer
