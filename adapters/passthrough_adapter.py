"""Сквозной OpenAI-совместимый passthrough хаба (ADR 0011, AD-003/AD-005/AD-007).

Отдельный raw HTTP-шов вне `TurnContext`/`TurnResult`: запрос уходит upstream (`base_url`
из `fleet.json`, например `codex-lb` на `127.0.0.1:2455`) дословно, ответ возвращается с
единственной нормализацией — санитизацией `tool_calls` общим ядром `core.tool_emulation`.
Модуль не знает ни об одном конкретном upstream, клиенте или модели и не импортирует `server`.

Стриминг: `content`/`reasoning` идут без задержки; дельты `tool_calls` копятся по составному
ключу `(choice.index, tool_call.index)` и выпускаются только вместе с терминальным
`finish_reason` своей choice. Конец потока без `finish_reason` (обрыв upstream, RW-002)
сбрасывает буфер choice: недособранные вызовы downstream не уходят, клиент получает
терминальный error-chunk без `[DONE]`.

Лимиты не зашиты в код: чтение env — здесь (адаптер, не ядро; BND-001), значения по
умолчанию — параметры `PassthroughLimits`, ядру они передаются аргументами.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import socket
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Mapping, Optional

from core.backend_adapter import (
    SESSIONS_NONE,
    STREAMING_NATIVE,
    BackendAdapter,
    BackendModel,
    BackendNotSupported,
    Capabilities,
    Qualification,
    StreamSink,
    TurnContext,
    TurnResult,
)
from core.tool_emulation import (
    DEFAULT_MAX_PARALLEL_CALLS,
    DEFAULT_MAX_PARALLEL_DEPTH,
    build_tool_schemas,
    sanitize_tool_call,
)

# Имена env (таблица AD-005) и значения по умолчанию: defaults — не потолки, переопределяются.
ENV_MAX_PARALLEL_CALLS = "BRIDGE_MAX_PARALLEL_CALLS"
ENV_MAX_PARALLEL_DEPTH = "BRIDGE_MAX_PARALLEL_DEPTH"
ENV_MAX_BODY_BYTES = "BRIDGE_PASSTHROUGH_MAX_BODY_BYTES"
ENV_ACC_MAX_BYTES = "BRIDGE_ACCUMULATOR_MAX_BYTES"
ENV_ACC_MAX_KEYS = "BRIDGE_ACCUMULATOR_MAX_KEYS"
ENV_ACC_MAX_PROCESS_BYTES = "BRIDGE_ACCUMULATOR_MAX_PROCESS_BYTES"
ENV_CONNECT_TIMEOUT_S = "BRIDGE_PASSTHROUGH_CONNECT_TIMEOUT_S"
ENV_READ_TIMEOUT_S = "BRIDGE_PASSTHROUGH_READ_TIMEOUT_S"

DEFAULT_MAX_BODY_BYTES = 16 * 1024 * 1024
DEFAULT_ACC_MAX_BYTES = 8 * 1024 * 1024
DEFAULT_ACC_MAX_KEYS = 64
DEFAULT_ACC_MAX_PROCESS_BYTES = 32 * 1024 * 1024
DEFAULT_CONNECT_TIMEOUT_S = 10.0
DEFAULT_READ_TIMEOUT_S = 1800.0
DEFAULT_QUEUE_TIMEOUT_S = 900.0  # ожидание слота `max_concurrent`, если хост своего не задал

KIND = "passthrough"

# Заголовки соединения (RFC 9110 §7.6.1) не пробрасываются; Host/Content-Length ставит шов.
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "proxy-connection",
        "te",
        "trailer",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)
_REQUEST_DROP = _HOP_BY_HOP | {"host", "content-length", "accept-encoding"}
_RESPONSE_DROP = _HOP_BY_HOP | {"content-length"}


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    try:
        value = int(str(environ.get(name, "")).strip())
    except ValueError:
        return default
    return value if value > 0 else default


def _positive_float(environ: Mapping[str, str], name: str, default: float) -> float:
    try:
        value = float(str(environ.get(name, "")).strip())
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class PassthroughLimits:
    """Эффективные лимиты шва; ядру `max_parallel_*` передаются параметрами."""

    max_parallel_calls: int = DEFAULT_MAX_PARALLEL_CALLS
    max_parallel_depth: int = DEFAULT_MAX_PARALLEL_DEPTH
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    accumulator_max_bytes: int = DEFAULT_ACC_MAX_BYTES
    accumulator_max_keys: int = DEFAULT_ACC_MAX_KEYS
    accumulator_max_process_bytes: int = DEFAULT_ACC_MAX_PROCESS_BYTES
    connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S
    read_timeout_s: float = DEFAULT_READ_TIMEOUT_S

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "PassthroughLimits":
        """Лимиты из окружения; нечисловое и неположительное значение -> default."""
        env = os.environ if environ is None else environ
        return cls(
            max_parallel_calls=_positive_int(
                env, ENV_MAX_PARALLEL_CALLS, DEFAULT_MAX_PARALLEL_CALLS
            ),
            max_parallel_depth=_positive_int(
                env, ENV_MAX_PARALLEL_DEPTH, DEFAULT_MAX_PARALLEL_DEPTH
            ),
            max_body_bytes=_positive_int(env, ENV_MAX_BODY_BYTES, DEFAULT_MAX_BODY_BYTES),
            accumulator_max_bytes=_positive_int(
                env, ENV_ACC_MAX_BYTES, DEFAULT_ACC_MAX_BYTES
            ),
            accumulator_max_keys=_positive_int(env, ENV_ACC_MAX_KEYS, DEFAULT_ACC_MAX_KEYS),
            accumulator_max_process_bytes=_positive_int(
                env, ENV_ACC_MAX_PROCESS_BYTES, DEFAULT_ACC_MAX_PROCESS_BYTES
            ),
            connect_timeout_s=_positive_float(
                env, ENV_CONNECT_TIMEOUT_S, DEFAULT_CONNECT_TIMEOUT_S
            ),
            read_timeout_s=_positive_float(env, ENV_READ_TIMEOUT_S, DEFAULT_READ_TIMEOUT_S),
        )


class ClientGone(Exception):
    """Запись клиенту невозможна (отмена/обрыв): upstream закрывается, повторов нет."""


class AccumulatorOverflow(Exception):
    """Бюджет аккумулятора `tool_calls` (запрос/ключи/процесс) исчерпан."""


class UpstreamBodyTooLarge(Exception):
    """Тело или строка upstream превысили лимит."""


class ProcessBudget:
    """Суммарный бюджет аккумуляторов процесса по параллельным passthrough-запросам."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._used = 0
        self._lock = threading.Lock()

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    def reserve(self, size: int) -> bool:
        with self._lock:
            if self._used + size > self._limit:
                return False
            self._used += size
            return True

    def release(self, size: int) -> None:
        with self._lock:
            self._used = max(0, self._used - size)


class ResponseSink:
    """Куда шов пишет ответ клиенту; реализует хаб (`server.py`). Любая ошибка записи -> ClientGone."""

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        raise NotImplementedError

    def write(self, data: bytes) -> None:
        raise NotImplementedError


def new_call_id() -> str:
    return "call_" + uuid.uuid4().hex[:24]


@dataclass
class _PartialCall:
    """Собираемый вызов одного ключа `(choice.index, tool_call.index)`."""

    id: str = ""
    type: str = "function"
    name: str = ""
    arguments: list[str] = field(default_factory=list)


class ToolCallAccumulator:
    """Дельты `tool_calls` по составному ключу `(choice.index, tool_call.index)`.

    Рост буфера проверяется ДО добавления фрагмента (запрос, число ключей, процесс);
    освобождение бюджета — `pop_choice`/`drop_choice`/`close` (идемпотентно).
    """

    def __init__(self, limits: PassthroughLimits, process: Optional[ProcessBudget] = None) -> None:
        self._limits = limits
        self._process = process
        self._entries: dict[tuple[int, int], _PartialCall] = {}
        self._bytes = 0
        self._last_index: dict[int, int] = {}

    @property
    def size_bytes(self) -> int:
        return self._bytes

    def _grow(self, size: int) -> None:
        if size <= 0:
            return
        if self._bytes + size > self._limits.accumulator_max_bytes:
            raise AccumulatorOverflow("accumulator_bytes")
        if self._process is not None and not self._process.reserve(size):
            raise AccumulatorOverflow("accumulator_process_bytes")
        self._bytes += size

    def _tool_index(self, choice: int, delta: Mapping[str, Any]) -> int:
        raw = delta.get("index")
        if isinstance(raw, int) and not isinstance(raw, bool):
            idx = raw
        elif delta.get("id") and choice in self._last_index:
            idx = self._last_index[choice] + 1  # без index: новый id — новый вызов
        else:
            idx = self._last_index.get(choice, 0)
        self._last_index[choice] = idx
        return idx

    def add(self, choice: int, deltas: Any) -> None:
        for delta in deltas if isinstance(deltas, list) else ():
            if not isinstance(delta, dict):
                continue
            key = (choice, self._tool_index(choice, delta))
            entry = self._entries.get(key)
            if entry is None:
                if len(self._entries) >= self._limits.accumulator_max_keys:
                    raise AccumulatorOverflow("accumulator_keys")
                entry = _PartialCall()
                self._entries[key] = entry
            fn = delta.get("function") if isinstance(delta.get("function"), dict) else {}
            call_id = delta.get("id")
            if isinstance(call_id, str) and call_id and not entry.id:
                self._grow(len(call_id.encode("utf-8")))
                entry.id = call_id
            if isinstance(delta.get("type"), str) and delta["type"]:
                entry.type = delta["type"]
            name = fn.get("name")
            if isinstance(name, str) and name and not entry.name:
                self._grow(len(name.encode("utf-8")))
                entry.name = name
            fragment = fn.get("arguments")
            if isinstance(fragment, str) and fragment:
                self._grow(len(fragment.encode("utf-8")))
                entry.arguments.append(fragment)

    def has_choice(self, choice: int) -> bool:
        return any(key[0] == choice for key in self._entries)

    def pending_choices(self) -> list[int]:
        return sorted({key[0] for key in self._entries})

    def _release(self, entry: _PartialCall) -> None:
        size = (
            len(entry.id.encode("utf-8"))
            + len(entry.name.encode("utf-8"))
            + sum(len(part.encode("utf-8")) for part in entry.arguments)
        )
        self._bytes = max(0, self._bytes - size)
        if self._process is not None:
            self._process.release(size)

    def pop_choice(self, choice: int) -> list[dict[str, Any]]:
        """Собранные вызовы choice в порядке `tool_call.index` (OpenAI-форма); буфер освобождается."""
        keys = sorted(key for key in self._entries if key[0] == choice)
        calls: list[dict[str, Any]] = []
        for key in keys:
            entry = self._entries.pop(key)
            self._release(entry)
            calls.append(
                {
                    "index": key[1],
                    "id": entry.id or new_call_id(),
                    "type": entry.type,
                    "function": {"name": entry.name, "arguments": "".join(entry.arguments)},
                }
            )
        self._last_index.pop(choice, None)
        return calls

    def drop_choice(self, choice: int) -> None:
        self.pop_choice(choice)

    def close(self) -> None:
        for choice in self.pending_choices():
            self.drop_choice(choice)


def sanitize_choice_calls(
    calls: list[dict[str, Any]],
    tool_schemas: Optional[dict[str, Any]],
    limits: PassthroughLimits,
) -> list[dict[str, Any]]:
    """Санитизация вызовов одной choice; `index` меняется только если `parallel` изменил число вызовов."""
    groups = [
        sanitize_tool_call(
            call,
            tool_schemas,
            max_parallel_calls=limits.max_parallel_calls,
            max_parallel_depth=limits.max_parallel_depth,
        )
        for call in calls
    ]
    flat = [item for group in groups for item in group]
    unpacked = any(
        len(group) != 1 or group[0].get("id") != call.get("id")
        for group, call in zip(groups, calls)
    )
    if not unpacked:
        return flat
    return [dict(item, index=i) if "index" in item else item for i, item in enumerate(flat)]


def sanitize_completion_body(
    body: bytes,
    tool_schemas: Optional[dict[str, Any]],
    limits: PassthroughLimits,
) -> bytes:
    """Тело non-stream `chat.completion`: санитизируются только `choices[].message.tool_calls`.

    Невалидный JSON, форма без `choices` и ответ без изменений возвращаются байт-в-байт.
    """
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return body
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list):
        return body
    changed = False
    for choice in choices:
        message = choice.get("message") if isinstance(choice, dict) else None
        if not isinstance(message, dict):
            continue
        calls = message.get("tool_calls")
        if not isinstance(calls, list) or not calls or not all(isinstance(c, dict) for c in calls):
            continue
        cleaned = sanitize_choice_calls(calls, tool_schemas, limits)
        if cleaned != calls:
            message["tool_calls"] = cleaned
            changed = True
    return json.dumps(data, ensure_ascii=False).encode("utf-8") if changed else body


def _data_frame(payload: Mapping[str, Any]) -> bytes:
    return b"data: " + json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n\n"


def _error_frame(chunk: Mapping[str, Any], code: str, message: str) -> bytes:
    """Терминальный error-chunk в форме `chat.completion.chunk` (как fail-close кадр фасада)."""
    return _data_frame(
        {
            "id": chunk.get("id") or "chatcmpl-passthrough",
            "object": "chat.completion.chunk",
            "created": chunk.get("created") or int(time.time()),
            "model": chunk.get("model") or "",
            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
            "error": {"message": message, "type": "stream_error", "code": code, "param": None},
        }
    )


def iter_sse_events(readline: Callable[[int], bytes], max_line_bytes: int) -> Iterator[tuple[bytes, Optional[str]]]:
    """SSE-события upstream: (сырые байты события, склеенный `data:` либо None)."""
    raw = bytearray()
    data: list[str] = []
    while True:
        line = readline(max_line_bytes + 1)
        if len(line) > max_line_bytes:
            raise UpstreamBodyTooLarge("sse_line")
        if not line:
            # Оборванная посреди строки (без перевода строки) запись — не событие: клиенту не уходит.
            if raw and raw.endswith(b"\n"):
                yield bytes(raw), ("\n".join(data) if data else None)
            return
        raw += line
        if len(raw) > max_line_bytes * 2:
            raise UpstreamBodyTooLarge("sse_event")
        text = line.rstrip(b"\r\n")
        if text == b"":
            yield bytes(raw), ("\n".join(data) if data else None)
            raw = bytearray()
            data = []
        elif text.startswith(b"data:"):
            value = text[5:].decode("utf-8", errors="replace")
            data.append(value[1:] if value.startswith(" ") else value)


@dataclass
class StreamOutcome:
    """Итог пробрасывания SSE (для журнала и тестов)."""

    done: bool = False
    incomplete: bool = False
    overflow: bool = False
    tool_calls_published: int = 0


def relay_sse(
    readline: Callable[[int], bytes],
    write: Callable[[bytes], None],
    *,
    tool_schemas: Optional[dict[str, Any]],
    limits: PassthroughLimits,
    process: Optional[ProcessBudget] = None,
    sanitize: bool = True,
) -> StreamOutcome:
    """Пробросить SSE-поток upstream клиенту с санитизацией `tool_calls` (AD-005).

    Исходный порядок событий сохраняется; единственное изменение — вызовы choice выходят
    одним кадром прямо перед терминальным чанком своей choice, после санитизации.
    """
    outcome = StreamOutcome()
    acc = ToolCallAccumulator(limits, process)
    seen: set[int] = set()
    finished: set[int] = set()
    last_chunk: dict[str, Any] = {}
    try:
        for raw, data in iter_sse_events(readline, limits.max_body_bytes):
            if data is None:
                write(raw)  # комментарий/keepalive/event без data — дословно
                continue
            if data.strip() == "[DONE]":
                if acc.pending_choices():
                    acc.close()  # [DONE] без finish_reason у choice с вызовами: успеха нет
                    outcome.incomplete = True
                    write(_error_frame(last_chunk, "upstream_incomplete_stream",
                                       "upstream stream ended before finish_reason"))
                    return outcome
                outcome.done = True
                write(raw)
                return outcome
            try:
                chunk = json.loads(data)
            except ValueError:
                write(raw)
                continue
            choices = chunk.get("choices") if isinstance(chunk, dict) else None
            if not isinstance(choices, list) or not sanitize:
                write(raw)
                continue
            last_chunk = {k: chunk.get(k) for k in ("id", "created", "model")}
            modified = False
            terminal: list[int] = []
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                raw_index = choice.get("index")
                index = raw_index if isinstance(raw_index, int) and not isinstance(raw_index, bool) else 0
                seen.add(index)
                delta = choice.get("delta")
                if isinstance(delta, dict) and "tool_calls" in delta:
                    acc.add(index, delta["tool_calls"])
                    delta = {k: v for k, v in delta.items() if k != "tool_calls"}
                    choice["delta"] = delta
                    modified = True
                if choice.get("finish_reason"):
                    finished.add(index)
                    terminal.append(index)
            for index in sorted(terminal):
                if not acc.has_choice(index):
                    continue
                calls = sanitize_choice_calls(acc.pop_choice(index), tool_schemas, limits)
                outcome.tool_calls_published += len(calls)
                write(
                    _data_frame(
                        {
                            **{k: chunk[k] for k in chunk if k not in ("choices", "usage", "error")},
                            "choices": [
                                {"index": index, "delta": {"tool_calls": calls}, "finish_reason": None}
                            ],
                        }
                    )
                )
            if not modified:
                write(raw)
                continue
            only_empty = all(
                isinstance(c, dict) and not c.get("delta") and not c.get("finish_reason")
                for c in choices
            )
            if choices and only_empty and "usage" not in chunk and "error" not in chunk:
                continue  # чанк состоял только из дельт tool_calls
            write(_data_frame(chunk))
        # EOF без [DONE]: недособранное сбрасывается, незавершённые choices — ошибка.
        unfinished = seen - finished
        if acc.pending_choices() or unfinished:
            acc.close()
            outcome.incomplete = True
            write(_error_frame(last_chunk, "upstream_incomplete_stream",
                               "upstream stream ended before finish_reason"))
        return outcome
    except AccumulatorOverflow:
        acc.close()
        outcome.overflow = True
        write(_error_frame(last_chunk, "upstream_response_too_large",
                           "upstream tool_calls exceed the bridge limit"))
        return outcome
    except UpstreamBodyTooLarge:
        acc.close()
        outcome.overflow = True
        write(_error_frame(last_chunk, "upstream_response_too_large",
                           "upstream event exceeds the bridge limit"))
        return outcome
    finally:
        acc.close()


def _json_error(status: int, error_type: str, message: str) -> tuple[list[tuple[str, str]], bytes]:
    body = json.dumps(
        {"error": {"message": message, "type": error_type, "code": status}}, ensure_ascii=False
    ).encode("utf-8")
    return [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))], body


def _read_bounded(resp: http.client.HTTPResponse, limit: int) -> bytes:
    """Тело upstream не больше `limit`: проверка заявленного размера и инкрементальное чтение."""
    declared = resp.getheader("Content-Length")
    if declared is not None and declared.strip().isdigit() and int(declared) > limit:
        raise UpstreamBodyTooLarge("content_length")
    chunks: list[bytes] = []
    total = 0
    while True:
        piece = resp.read(min(65536, limit + 1 - total))
        if not piece:
            return b"".join(chunks)
        total += len(piece)
        if total > limit:
            raise UpstreamBodyTooLarge("body")
        chunks.append(piece)


class PassthroughAdapter(BackendAdapter):
    """Бэкенд `kind=passthrough`: модели каталога, раw-шов исполнения вместо `execute_turn`."""

    kind = KIND
    capabilities = Capabilities(sessions=SESSIONS_NONE, streaming=STREAMING_NATIVE, usage="exact")

    def __init__(
        self,
        backend_id: str,
        config: Mapping[str, Any],
        catalog_source: Callable[[], Mapping[str, Any]],
        host: Any = None,
        *,
        limits: Optional[PassthroughLimits] = None,
        process_budget: Optional[ProcessBudget] = None,
        sanitize: Optional[bool] = None,
    ) -> None:
        super().__init__(backend_id, config, catalog_source, host)
        self.limits = limits or PassthroughLimits.from_env()
        self.process_budget = process_budget or ProcessBudget(
            self.limits.accumulator_max_process_bytes
        )
        self._sanitize = sanitize
        self._active = 0
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(self.max_concurrent)
        base_url = self.config.get("base_url")
        if not isinstance(base_url, str) or not re.fullmatch(
            r"http://(?:127\.0\.0\.1|localhost):[0-9]{1,5}/v1", base_url
        ):
            raise ValueError("backend_base_url_invalid")
        parts = urllib.parse.urlsplit(base_url)
        if parts.hostname is None or parts.port is None or not 1 <= parts.port <= 65535:
            raise ValueError("backend_base_url_invalid")
        self._host = parts.hostname
        self._port = parts.port
        self._base_path = parts.path.rstrip("/")

    # -- контракт BackendAdapter ---------------------------------------------------------
    def get_models(self) -> list[BackendModel]:
        return self._catalog_models()

    def qualify(self) -> Qualification:
        return Qualification(True, "")

    def is_healthy(self) -> bool:
        return True  # stateless: процессов нет, недоступность upstream — 502/504 на запросе

    def active_count(self) -> int:
        with self._lock:
            return self._active

    def spawn_session(self, ctx: TurnContext) -> object:
        raise BackendNotSupported("passthrough_no_sessions")

    def execute_turn(self, ctx: TurnContext, sse_writer: Optional[StreamSink]) -> TurnResult:
        raise BackendNotSupported("passthrough_raw_seam")

    def close_session(self, sid: str) -> None:
        return None

    def shutdown(self) -> None:
        return None

    # -- raw-шов -------------------------------------------------------------------------
    def _log(self, message: str) -> None:
        logger = getattr(self.host, "_log", None)
        if callable(logger):
            logger(message)

    def _sanitize_enabled(self) -> bool:
        if self._sanitize is not None:
            return self._sanitize
        return bool(getattr(self.host, "BRIDGE_SANITIZE_TOOL_CALLS", True))

    def handle(
        self,
        *,
        path: str,
        raw_body: bytes,
        request: Mapping[str, Any],
        headers: Mapping[str, str],
        sink: ResponseSink,
    ) -> None:
        """Один запрос: байты тела уходят upstream без мутаций, ответ пишется в `sink`."""
        queue_timeout = float(getattr(self.host, "QUEUE_TIMEOUT_S", DEFAULT_QUEUE_TIMEOUT_S))
        if not self._slots.acquire(timeout=queue_timeout):
            self._fail(sink, 503, "overloaded", "passthrough backend is saturated")
            return
        with self._lock:
            self._active += 1
        conn: Optional[http.client.HTTPConnection] = None
        try:
            try:
                conn = self._open(path, raw_body, headers)
                resp = conn.getresponse()
            except socket.timeout:
                self._fail(sink, 504, "upstream_timeout", "upstream did not respond in time")
                return
            except (OSError, http.client.HTTPException):
                self._fail(sink, 502, "upstream_unavailable", "upstream is unavailable")
                return
            self._respond(resp, request, sink)
        except ClientGone:
            self._log("passthrough client_gone")
        finally:
            if conn is not None:
                conn.close()
            with self._lock:
                self._active -= 1
            self._slots.release()

    def _open(self, path: str, raw_body: bytes, headers: Mapping[str, str]) -> http.client.HTTPConnection:
        conn = http.client.HTTPConnection(self._host, self._port, timeout=self.limits.connect_timeout_s)
        conn.connect()
        if conn.sock is not None:
            conn.sock.settimeout(self.limits.read_timeout_s)
        forwarded = {k: v for k, v in headers.items() if k.lower() not in _REQUEST_DROP}
        forwarded["Host"] = f"{self._host}:{self._port}"
        forwarded["Content-Length"] = str(len(raw_body))
        forwarded["Accept-Encoding"] = "identity"  # тело нужно разобрать, а не передать сжатым
        forwarded["Connection"] = "close"
        route, _, query = path.partition("?")
        suffix = route[len("/v1"):] if route.startswith("/v1/") else route
        target = self._base_path + suffix + ("?" + query if query else "")
        conn.request("POST", target, body=raw_body, headers=forwarded)
        return conn

    def _fail(self, sink: ResponseSink, status: int, error_type: str, message: str) -> None:
        self._log(f"passthrough fail status={status} type={error_type}")
        headers, body = _json_error(status, error_type, message)
        sink.start(status, headers)
        sink.write(body)

    def _response_headers(self, resp: http.client.HTTPResponse) -> list[tuple[str, str]]:
        return [(k, v) for k, v in resp.getheaders() if k.lower() not in _RESPONSE_DROP]

    def _respond(
        self,
        resp: http.client.HTTPResponse,
        request: Mapping[str, Any],
        sink: ResponseSink,
    ) -> None:
        content_type = (resp.getheader("Content-Type") or "").lower()
        encoded = (resp.getheader("Content-Encoding") or "identity").lower() != "identity"
        sanitize = self._sanitize_enabled()
        schemas = build_tool_schemas(request.get("tools")) if sanitize else None
        if resp.status == 200 and "text/event-stream" in content_type:
            self._relay_stream(resp, schemas, sink, sanitize)
            return
        try:
            body = _read_bounded(resp, self.limits.max_body_bytes)
        except UpstreamBodyTooLarge:
            self._fail(sink, 502, "upstream_response_too_large", "upstream response exceeds the bridge limit")
            return
        except socket.timeout:
            self._fail(sink, 504, "upstream_timeout", "upstream did not respond in time")
            return
        except (OSError, http.client.HTTPException):
            self._fail(sink, 502, "upstream_unavailable", "upstream is unavailable")
            return
        if sanitize and resp.status == 200 and "json" in content_type and not encoded:
            body = sanitize_completion_body(body, schemas, self.limits)
        headers = self._response_headers(resp) + [("Content-Length", str(len(body)))]
        sink.start(resp.status, headers)
        sink.write(body)

    def _relay_stream(
        self,
        resp: http.client.HTTPResponse,
        schemas: Optional[dict[str, Any]],
        sink: ResponseSink,
        sanitize: bool,
    ) -> None:
        headers = [(k, v) for k, v in self._response_headers(resp) if k.lower() != "content-type"]
        headers += [
            ("Content-Type", "text/event-stream"),
            ("Cache-Control", "no-cache"),
            ("X-Accel-Buffering", "no"),
        ]
        sink.start(200, headers)
        try:
            outcome = relay_sse(
                resp.readline,
                sink.write,
                tool_schemas=schemas,
                limits=self.limits,
                process=self.process_budget,
                sanitize=sanitize,
            )
        except (socket.timeout, OSError, http.client.HTTPException):
            sink.write(_error_frame({}, "upstream_stream_error", "upstream stream failed"))
            return
        if outcome.incomplete or outcome.overflow:
            self._log(
                f"passthrough stream incomplete={outcome.incomplete} overflow={outcome.overflow}"
            )
