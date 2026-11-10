import json
from typing import Callable, Iterable, List


class MuseServeMessageReader:
    def __init__(self, on_useful_chunk: Callable[[], None] | None = None):
        self._buffer = b""
        self._on_useful_chunk = on_useful_chunk

    def _touch_if_useful(self, chunk: bytes) -> None:
        if not chunk:
            return
        if self._on_useful_chunk is not None and chunk.strip():
            self._on_useful_chunk()

    def feed(self, chunk: bytes) -> List[str]:
        if not chunk:
            return []
        self._touch_if_useful(chunk)
        self._buffer += chunk
        messages: List[str] = []
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                json.loads(text)
            except json.JSONDecodeError:
                continue
            messages.append(text)
        return messages

    def flush(self) -> List[str]:
        if not self._buffer:
            return []
        text = self._buffer.decode("utf-8", errors="replace").strip()
        self._buffer = b""
        if not text:
            return []
        try:
            json.loads(text)
        except json.JSONDecodeError:
            return []
        return [text]

    def iter_messages(self, chunks: Iterable[bytes]):
        for chunk in chunks:
            yield from self.feed(chunk)
        yield from self.flush()
