"""Детерминированные входы инцидента; не доказывают ASM-001 реального CLI."""

from __future__ import annotations

import json
import math
import socket
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
from typing import Any

Record = dict[str, Any]


@dataclass
class FakeClock:
    """Раздельные монотонные и настенные часы без реального ожидания."""

    now_s: float = 0.0
    wall_start_s: float = 1_700_000_000.0

    def monotonic(self) -> float:
        return self.now_s

    def time(self) -> float:
        return self.wall_start_s + self.now_s

    def advance(self, seconds: float) -> None:
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Время можно продвигать только на конечный интервал >= 0")
        self.now_s += seconds

    sleep = advance


@dataclass(frozen=True)
class MockResponse:
    """Гейты управляют заголовками и отдельными чанками без sleep."""

    status: int = 200
    chunks: tuple[bytes | tuple[Event, bytes], ...] = (b"data: [DONE]\n\n",)
    headers_gate: Event | None = None
    timeout_s: float = 0.05


class MockUpstream:
    """Однопоточный HTTP/SSE upstream: только loopback port=0, закрытие через with."""

    def __init__(self, response: MockResponse | None = None, port: int = 0) -> None:
        if port in {9882, 9887, 10830} or port != 0:
            raise ValueError("Разрешён только эфемерный порт 0, не живые порты мостов")
        self.response = response or MockResponse()
        self.timeout_s = self.response.timeout_s
        if not math.isfinite(self.timeout_s) or self.timeout_s <= 0:
            raise ValueError("timeout_s должен быть конечным и положительным")
        self.requested, self.disconnected, self.closed = Event(), Event(), Event()
        self.connection: socket.socket | None = None
        self.requests: list[tuple[str, str]] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            timeout = owner.timeout_s

            def do_GET(self) -> None:
                owner._respond(self)

            do_POST = do_GET

            def log_message(self, format: str, *args: object) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.host, self.port = self.server.server_address[:2]
        self.url = f"http://127.0.0.1:{self.port}"
        self.thread = Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": self.timeout_s},
            daemon=False,
        )

    def __enter__(self) -> MockUpstream:
        self.thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _wait(self, gate: Event | None) -> bool:
        while gate is not None and not gate.is_set():
            if self.disconnected.is_set() or self.closed.wait(self.timeout_s):
                return False
        return not (self.closed.is_set() or self.disconnected.is_set())

    def _respond(self, handler: BaseHTTPRequestHandler) -> None:
        self.connection = handler.connection
        self.disconnected.clear()
        self.requests.append((handler.command, handler.path))
        self.requested.set()
        try:
            handler.rfile.read(int(handler.headers.get("Content-Length", "0")))
            if not self._wait(self.response.headers_gate):
                return
            handler.send_response(self.response.status)
            handler.send_header("Content-Type", "text/event-stream")
            handler.send_header("Connection", "close")
            handler.end_headers()
            handler.wfile.flush()
            for chunk in self.response.chunks:
                gate, data = chunk if isinstance(chunk, tuple) else (None, chunk)
                if not self._wait(gate):
                    return
                handler.wfile.write(data)
                handler.wfile.flush()
        except OSError:
            self.disconnected.set()
        finally:
            self.connection = None
            handler.close_connection = True

    def disconnect(self) -> None:
        connection = self.connection
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.disconnected.set()

    def close(self) -> None:
        self.closed.set()
        self.disconnect()
        try:
            if self.thread.is_alive():
                self.server.shutdown()
        finally:
            self.server.server_close()
            if self.thread.ident is not None:
                self.thread.join(self.timeout_s * 2)
        if self.thread.is_alive():
            raise AssertionError("Поток mock upstream не завершился")


def tool_events(
    step_index: int | None,
    call_id: str | None = "call-1",
    tool_name: str = "read_file",
    id_key: str = "call_id",
) -> tuple[Record, Record]:
    """Пара start/end; срез/повтор пары моделирует orphan/duplicate, None убирает ID."""
    if id_key not in {"call_id", "tool_call_id", "id"}:
        raise ValueError("Неизвестное поле идентичности")
    identity = {} if call_id is None else {id_key: call_id}
    base = {"step_index": step_index, "tool_name": tool_name, **identity}
    return ({"type": "tool_use", **base}, {"type": "tool_result", **base})


def build_incident_transcript(
    active_step_idx: int = 355, tool_count: int = 218
) -> list[Record]:
    """История >=354 шагов и >=218 завершённых вызовов плюс чистый активный шаг."""
    if not 355 <= active_step_idx <= 512 or not 218 <= tool_count < active_step_idx:
        raise ValueError("Нужны >=354 шага истории, >=218 вызовов, <=512 сущностей")
    records = []
    for idx in range(1, active_step_idx + 1):
        calls = []
        if idx <= tool_count:
            name = "shell" if idx % 2 else "unknown_tool"
            function = {"name": name, "arguments": "{}"}
            call = dict(id=f"history-{idx}", type="function", function=function)
            calls = [dict(call, status="completed")]
        committed = idx < active_step_idx
        content = f"Шаг {idx}." if committed else ""
        record = dict(step_index=idx, committed=committed, content=content)
        records.append(dict(record, tool_calls=calls))
    return records


def build_incident_ledger(
    active_step_idx: int = 355, tool_count: int = 218
) -> list[Record]:
    """Независимые входные записи ledger с step_idx; без импорта будущего ядра."""
    records = build_incident_transcript(active_step_idx, tool_count)
    return [dict(rec, step_idx=rec["step_index"]) for rec in records]


class CliEventEmulator:
    """Синтетический --conversation; вывод истории не доказывает ASM-001."""

    n_entities_max = 512

    def __init__(
        self,
        clock: FakeClock | None = None,
        active_step_idx: int = 355,
        cid: str = "bbdb91e5",
    ) -> None:
        self.clock = clock if clock is not None else FakeClock()
        self.cid, self.active_step_idx = cid, active_step_idx
        self.transcript = build_incident_transcript(active_step_idx)
        self.invocations: list[tuple[str, ...]] = []
        self.disconnected = False

    def disconnect(self) -> None:
        self.disconnected = True

    def _history(self) -> Iterator[Record]:
        for rec in self.transcript[:-1]:
            for call in rec["tool_calls"]:
                name = call["function"]["name"]
                yield from tool_events(rec["step_index"], call["id"], name)
            yield {"type": "agent_response", **rec}

    def events(
        self,
        argv: Sequence[str],
        silent_s: float = 181.0,
        active_events: Iterable[Record] = (),
    ) -> Iterator[Record]:
        """Выдаёт историю, продвигает FakeClock, затем активные события и финал."""
        if tuple(argv) != ("--conversation", self.cid):
            raise ValueError("Ожидается --conversation с исходным cid")
        self.invocations.append(tuple(argv))
        for event in self._history():
            if self.disconnected:
                return
            yield event
        if self.disconnected:
            return
        self.clock.advance(silent_s)
        for event in active_events:
            if self.disconnected:
                return
            yield event
        if not self.disconnected:
            yield dict(self.transcript[-1], type="agent_response", content="Ответ.")

    def stdout(
        self,
        argv: Sequence[str],
        silent_s: float = 181.0,
        active_events: Iterable[Record] = (),
    ) -> Iterator[str]:
        events = self.events(argv, silent_s, active_events)
        return (json.dumps(event, ensure_ascii=False) + "\n" for event in events)
