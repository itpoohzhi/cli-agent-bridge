"""Сквозной OpenAI-совместимый passthrough хаба (ADR 0011, AD-003/AD-005/AD-007).

Отдельный raw HTTP-шов вне `TurnContext`/`TurnResult`: запрос уходит upstream (`base_url`
из `fleet.json`, например `codex-lb` на `127.0.0.1:2455`) дословно, ответ возвращается с
единственной нормализацией — санитизацией `tool_calls` общим ядром `core.tool_emulation`.
Модуль не знает ни об одном конкретном upstream, клиенте или модели; для скрытия мастер-ключа хаба проверка токена инжектируется callback'ом `is_hub_key` (параметр конструктора или host), модуль `server` не импортируется.

Стриминг: `content`/`reasoning` идут без задержки; дельты `tool_calls` копятся по составному
ключу `(choice.index, tool_call.index)` и выпускаются только вместе с терминальным
`finish_reason` своей choice. Конец потока без `finish_reason` (обрыв upstream, RW-002)
сбрасывает буфер choice: недособранные вызовы downstream не уходят, клиент получает
терминальный error-chunk без `[DONE]`.

Лимиты не зашиты в код: чтение env — здесь (адаптер, не ядро; BND-001), значения по
умолчанию — параметры `PassthroughLimits`, ядру они передаются аргументами.
"""

from __future__ import annotations

import copy
import hmac
import http.client
import json
import math
import os
import queue
import re
import select
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
    KindConstraints,
    Qualification,
    PreSendTransientError,
    StreamSink,
    TurnContext,
    TurnResult,
)

try:
    from core.tool_emulation import (
        DEFAULT_MAX_PARALLEL_CALLS,
        DEFAULT_MAX_PARALLEL_DEPTH,
        DEFAULT_MAX_REPETITION_REPEATS,
        DEFAULT_MAX_REPETITION_TOKEN_LEN,
        RepetitionGuard,
        ToolCallParser,
        build_tool_schemas,
        sanitize_tool_call,
    )
except ImportError:
    from core.tool_emulation import (  # type: ignore[no-redef]
        DEFAULT_MAX_PARALLEL_CALLS,
        DEFAULT_MAX_PARALLEL_DEPTH,
        ToolCallParser,
        build_tool_schemas,
        sanitize_tool_call,
    )

    DEFAULT_MAX_REPETITION_REPEATS = 20
    DEFAULT_MAX_REPETITION_TOKEN_LEN = 64
    RepetitionGuard = None  # type: ignore[assignment,misc]
from core.cli_runtime_config import NonstreamConfig
from core.liveness_signals import LivenessWindow, SseProgress, passthrough_window
from core.nonstream_aggregator import NonstreamError, aggregate_events, choice_index, internal_stream_body, request_deadlines
from core.passthrough_sliding_window import FLAG_PASSTHROUGH_SLIDING_WINDOW, SlidingDeadline, open_sliding_deadline
from core.runtime_env import DynamicFlagSource, bounded_int as _bounded_int, env_bool, positive_int as _positive_int
from core.stream_framing import (
    build_stream_error_chunk,
    format_sse_event,
    format_stream_error_sse,
    is_graceful_error_framing_enabled,
)
_SLIDING_WIN_FLAG = DynamicFlagSource(FLAG_PASSTHROUGH_SLIDING_WINDOW)

# Имена env (таблица AD-005) и значения по умолчанию: defaults — не потолки, переопределяются.
ENV_MAX_PARALLEL_CALLS = "BRIDGE_MAX_PARALLEL_CALLS"
ENV_MAX_PARALLEL_DEPTH = "BRIDGE_MAX_PARALLEL_DEPTH"
ENV_MAX_BODY_BYTES = "BRIDGE_PASSTHROUGH_MAX_BODY_BYTES"
ENV_ACC_MAX_BYTES = "BRIDGE_ACCUMULATOR_MAX_BYTES"
ENV_ACC_MAX_KEYS = "BRIDGE_ACCUMULATOR_MAX_KEYS"
ENV_ACC_MAX_PROCESS_BYTES = "BRIDGE_ACCUMULATOR_MAX_PROCESS_BYTES"
ENV_CONNECT_TIMEOUT_S = "BRIDGE_PASSTHROUGH_CONNECT_TIMEOUT_S"
ENV_READ_TIMEOUT_S = "BRIDGE_PASSTHROUGH_READ_TIMEOUT_S"
# ADR-0020: env читает адаптер (не ядро, BND-001) и передаёт значения аргументами.
ENV_REPETITION_MAX_REPEATS = "BRIDGE_REPETITION_MAX_REPEATS"
ENV_REPETITION_MAX_TOKEN_LEN = "BRIDGE_REPETITION_MAX_TOKEN_LEN"
ENV_REPETITION_GUARD_ENABLED = "BRIDGE_REPETITION_GUARD_ENABLED"
ENV_INVOKE_NORMALIZATION_ENABLED = "BRIDGE_INVOKE_NORMALIZATION_ENABLED"

DEFAULT_MAX_BODY_BYTES = 16 * 1024 * 1024
DEFAULT_ACC_MAX_BYTES = 8 * 1024 * 1024
DEFAULT_ACC_MAX_KEYS = 64
DEFAULT_ACC_MAX_PROCESS_BYTES = 32 * 1024 * 1024
DEFAULT_CONNECT_TIMEOUT_S = 10.0
DEFAULT_READ_TIMEOUT_S = 1800.0
DEFAULT_IDLE_TIMEOUT_S = 300.0
DEFAULT_TOTAL_TIMEOUT_S = 420.0
DEFAULT_QUEUE_TIMEOUT_S = (
    900.0  # ожидание слота `max_concurrent`, если хост своего не задал
)

KIND = "passthrough"

# Loopback-upstream с `/v1` в конце; допустимы вложенные префиксы (`http://127.0.0.1:10830/go/v1`).
_LOOPBACK_V1_RE = re.compile(
    r"http://(?:127\.0\.0\.1|localhost):[0-9]{1,5}(?:/[a-z0-9._-]+)*/v1"
)
_NO_EFFORT_VALUES = frozenset({"", "off", "none"})

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
_TOOL_SANITIZED_HEADER = "x-bridge-tool-sanitized"
_REQUEST_DROP = _HOP_BY_HOP | {
    "host",
    "content-length",
    "accept-encoding",
    "x-turn-owner-token",
    _TOOL_SANITIZED_HEADER,
}
_RESPONSE_DROP = _HOP_BY_HOP | {"content-length", _TOOL_SANITIZED_HEADER}

def _positive_float(environ: Mapping[str, str], name: str, default: float) -> float:
    try:
        value = float(str(environ.get(name, "")).strip())
    except ValueError:
        return default
    return value if math.isfinite(value) and value > 0 else default


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
    read_timeout_s: float = DEFAULT_READ_TIMEOUT_S  # совместимость старого конструктора
    idle_timeout_s: float = DEFAULT_IDLE_TIMEOUT_S
    total_timeout_s: float = DEFAULT_TOTAL_TIMEOUT_S
    stream_safety_cap_s: float = 3600.0  # потолок активного stream=True при скользящем окне
    heartbeat_interval_s: float = 12.0
    poll_interval_s: float = 0.1
    reader_join_timeout_s: float = 0.2
    read_queue_max_entries: int = 1
    repetition_max_repeats: int = DEFAULT_MAX_REPETITION_REPEATS
    repetition_max_token_len: int = DEFAULT_MAX_REPETITION_TOKEN_LEN
    repetition_guard_enabled: bool = False
    invoke_normalization_enabled: bool = False
    max_keepalive_connections: int = 32
    keepalive_expiry_s: float = 30.0
    nonstream: NonstreamConfig = field(default_factory=NonstreamConfig)

    @classmethod
    def from_env(
        cls, environ: Optional[Mapping[str, str]] = None
    ) -> "PassthroughLimits":
        """Лимиты из окружения; нечисловое и неположительное значение -> default."""
        env = os.environ if environ is None else environ
        ns = NonstreamConfig.from_env(env)
        return cls(
            max_keepalive_connections=_positive_int(
                env, "BRIDGE_MAX_KEEPALIVE_CONNECTIONS", 32
            ),
            keepalive_expiry_s=_positive_float(env, "BRIDGE_KEEPALIVE_EXPIRY_S", 30.0),
            max_parallel_calls=_positive_int(
                env, ENV_MAX_PARALLEL_CALLS, DEFAULT_MAX_PARALLEL_CALLS
            ),
            max_parallel_depth=_positive_int(
                env, ENV_MAX_PARALLEL_DEPTH, DEFAULT_MAX_PARALLEL_DEPTH
            ),
            max_body_bytes=_positive_int(
                env, ENV_MAX_BODY_BYTES, DEFAULT_MAX_BODY_BYTES
            ),
            accumulator_max_bytes=_positive_int(
                env, ENV_ACC_MAX_BYTES, DEFAULT_ACC_MAX_BYTES
            ),
            accumulator_max_keys=_positive_int(
                env, ENV_ACC_MAX_KEYS, DEFAULT_ACC_MAX_KEYS
            ),
            accumulator_max_process_bytes=_positive_int(
                env, ENV_ACC_MAX_PROCESS_BYTES, DEFAULT_ACC_MAX_PROCESS_BYTES
            ),
            connect_timeout_s=_positive_float(
                env,
                "BRIDGE_CONNECT_TIMEOUT_S",
                _positive_float(env, ENV_CONNECT_TIMEOUT_S, DEFAULT_CONNECT_TIMEOUT_S),
            ),
            read_timeout_s=_positive_float(
                env, ENV_READ_TIMEOUT_S, DEFAULT_READ_TIMEOUT_S
            ),
            idle_timeout_s=_positive_float(
                env, "BRIDGE_IDLE_TIMEOUT_S", DEFAULT_IDLE_TIMEOUT_S
            ),
            total_timeout_s=_positive_float(
                env, "BRIDGE_TOTAL_TIMEOUT_S", DEFAULT_TOTAL_TIMEOUT_S
            ),
            stream_safety_cap_s=_positive_float(env, "BRIDGE_STREAM_SAFETY_CAP_S", 3600.0),
            heartbeat_interval_s=_positive_float(
                env, "BRIDGE_SSE_HEARTBEAT_INTERVAL_S", 12.0
            ),
            poll_interval_s=ns.poll_interval_s,
            reader_join_timeout_s=_positive_float(
                env, "BRIDGE_PASSTHROUGH_READER_JOIN_TIMEOUT_S", 0.2
            ),
            read_queue_max_entries=_positive_int(
                env, "BRIDGE_PASSTHROUGH_READ_QUEUE_MAX_ENTRIES", 1
            ),
            repetition_max_repeats=_bounded_int(
                env, ENV_REPETITION_MAX_REPEATS, DEFAULT_MAX_REPETITION_REPEATS, 3, 1000
            ),
            repetition_max_token_len=_bounded_int(
                env,
                ENV_REPETITION_MAX_TOKEN_LEN,
                DEFAULT_MAX_REPETITION_TOKEN_LEN,
                8,
                512,
            ),
            repetition_guard_enabled=env_bool(env, (ENV_REPETITION_GUARD_ENABLED,), False),
            invoke_normalization_enabled=env_bool(env, (ENV_INVOKE_NORMALIZATION_ENABLED,), False),
            nonstream=ns,
        )


class PassthroughConnectionPool:
    """Потокобезопасный LIFO-пул свободных соединений без состояния запроса."""

    def __init__(
        self, max_keepalive: int = 32, keepalive_expiry_s: float = 30.0
    ) -> None:
        self._max_keepalive: int = max_keepalive
        self._keepalive_expiry_s: float = keepalive_expiry_s
        self._idle: dict[
            tuple[str, int], list[tuple[http.client.HTTPConnection, float]]
        ] = {}
        self._lock: threading.Lock = threading.Lock()
        self._closed: bool = False

    def get_connection(
        self, host: str, port: int, timeout: float, *, fresh: bool = False
    ) -> tuple[http.client.HTTPConnection, bool]:
        """Выдать живое свободное соединение либо подключить новое."""
        while not fresh:
            with self._lock:
                entries = self._idle.get((host, port))
                entry = entries.pop() if entries else None
                if not entries:
                    _ = self._idle.pop((host, port), None)
            if entry is None:
                break
            conn, last_used = entry
            sock = conn.sock
            try:
                if (
                    sock is not None
                    and time.monotonic() - last_used <= self._keepalive_expiry_s
                ):
                    readable, _, _ = select.select([sock], [], [], 0)
                    if not readable:
                        conn.timeout = timeout
                        _ = sock.settimeout(timeout)
                        return conn, True
                    # EOF и незапрошенные данные одинаково запрещают переиспользование.
                    _ = sock.recv(1, socket.MSG_PEEK)
            except (OSError, ValueError):
                pass
            conn.close()
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        try:
            conn.connect()
        except BaseException:
            conn.close()
            raise
        return conn, False

    def release_connection(
        self,
        host: str,
        port: int,
        conn: http.client.HTTPConnection,
        can_reuse: bool = True,
    ) -> None:
        """Вернуть полностью прочитанное соединение или закрыть его."""
        if can_reuse and conn.sock is not None:
            with self._lock:
                if not self._closed:
                    entries = self._idle.setdefault((host, port), [])
                    if len(entries) < self._max_keepalive:
                        entries.append((conn, time.monotonic()))
                        return
        conn.close()

    def close_all(self) -> None:
        """Закрыть пул; соединения в работе закроются при возврате."""
        with self._lock:
            self._closed = True
            idle, self._idle = self._idle, {}
        for entries in idle.values():
            for conn, _ in entries:
                conn.close()


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

    accepts_presend_errors = False

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        raise NotImplementedError

    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def client_gone(self) -> bool:
        """Необязательный неблокирующий сигнал отмены от HTTP-фасада."""
        return False

    def error_type(self) -> str:
        """Тип ошибки отданного ответа для классификации исхода lease ('' — ошибки нет)."""
        return ""


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

    def __init__(
        self, limits: PassthroughLimits, process: Optional[ProcessBudget] = None
    ) -> None:
        self._limits = limits
        self._process = process
        self._entries: dict[tuple[int, int], _PartialCall] = {}
        self._bytes = 0
        self._last_index: dict[int, int] = {}
        self._remap: dict[tuple[int, int], int] = {}

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

    def next_tool_index(self, choice: int) -> int:
        """Следующий свободный индекс `tool_call` внутри `choice` (без коллизий с нативными)."""
        indices = [key[1] for key in self._entries if key[0] == choice]
        if choice in self._last_index:
            indices.append(self._last_index[choice])
        return (max(indices) + 1) if indices else 0

    def _tool_index(self, choice: int, delta: Mapping[str, Any]) -> int:
        raw = delta.get("index")
        if isinstance(raw, int) and not isinstance(raw, bool):
            call_id = delta.get("id")
            if isinstance(call_id, str) and call_id:
                existing = self._entries.get((choice, raw))
                if existing is not None and existing.id and existing.id != call_id:
                    idx = self.next_tool_index(choice)
                    self._remap[(choice, raw)] = idx
                else:
                    self._remap.pop((choice, raw), None)
                    idx = raw
            else:
                idx = self._remap.get((choice, raw), raw)
        elif delta.get("id") and choice in self._last_index:
            idx = self.next_tool_index(choice)  # без index: новый id — новый вызов
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
            fn = (
                delta.get("function") if isinstance(delta.get("function"), dict) else {}
            )
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
                    "function": {
                        "name": entry.name,
                        "arguments": "".join(entry.arguments),
                    },
                }
            )
        self._last_index.pop(choice, None)
        for remap_key in [k for k in self._remap if k[0] == choice]:
            self._remap.pop(remap_key, None)
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
    return [
        dict(item, index=i) if "index" in item else item for i, item in enumerate(flat)
    ]


def sanitize_completion_body(
    body: bytes,
    tool_schemas: Optional[dict[str, Any]],
    limits: PassthroughLimits,
) -> bytes:
    """Тело non-stream `chat.completion`: санитизируются `choices[].message.tool_calls`
    и (при `limits.invoke_normalization_enabled`) извлекаются `<invoke>` из `message.content`.

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
        raw_calls = message.get("tool_calls")
        has_valid_native = (
            isinstance(raw_calls, list)
            and bool(raw_calls)
            and all(isinstance(c, dict) for c in raw_calls)
        )
        merged_calls: list[dict[str, Any]] = list(raw_calls) if has_valid_native else []
        extracted_calls: list[dict[str, Any]] = []
        if limits.invoke_normalization_enabled:
            content = message.get("content")
            if isinstance(content, str) and content:
                content_parts: list[str] = []
                parsed_calls: list[dict[str, Any]] = []
                parser = ToolCallParser(
                    content_parts.append,
                    parsed_calls.append,
                    invoke_normalization_enabled=True,
                    repetition_guard_enabled=False,
                )
                parser.feed(content)
                parser.finish()
                new_content = "".join(content_parts)
                if parsed_calls or new_content != content:
                    message["content"] = new_content
                    changed = True
                has_index = any("index" in c for c in merged_calls)
                next_idx = (
                    max(
                        (
                            c["index"]
                            for c in merged_calls
                            if isinstance(c.get("index"), int)
                            and not isinstance(c.get("index"), bool)
                        ),
                        default=len(merged_calls) - 1,
                    )
                    + 1
                )
                for call in parsed_calls:
                    arguments = call.get("arguments")
                    entry: dict[str, Any] = {
                        "id": str(call.get("id") or new_call_id()),
                        "type": "function",
                        "function": {
                            "name": str(call.get("name") or ""),
                            "arguments": arguments
                            if isinstance(arguments, str)
                            else json.dumps(arguments or {}, ensure_ascii=False),
                        },
                    }
                    if has_index:
                        entry["index"] = next_idx
                        next_idx += 1
                    extracted_calls.append(entry)
                if extracted_calls:
                    merged_calls.extend(extracted_calls)
        if not merged_calls:
            continue
        cleaned = sanitize_choice_calls(merged_calls, tool_schemas, limits)
        if extracted_calls or cleaned != raw_calls:
            message["tool_calls"] = cleaned
            changed = True
    return json.dumps(data, ensure_ascii=False).encode("utf-8") if changed else body


def _data_frame(payload: Mapping[str, Any]) -> bytes:
    return b"data: " + json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n\n"


def _error_frame(chunk: Mapping[str, Any], code: str, message: str) -> bytes:
    """Терминальный error-chunk в форме `chat.completion.chunk` (как fail-close кадр фасада)."""
    return (
        format_sse_event(
            build_stream_error_chunk(
                message=message,
                model=str(chunk.get("model") or ""),
                code=code,
                finish_reason="stop" if is_graceful_error_framing_enabled() else None,
                completion_id=str(chunk.get("id") or "chatcmpl-passthrough"),
                created=chunk.get("created"),
            )
        ).encode("utf-8")
        + b"data: [DONE]\n\n"
    )


def iter_sse_events(
    readline: Callable[[int], bytes], max_line_bytes: int
) -> Iterator[tuple[bytes, Optional[str]]]:
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
    committed: bool = False
    repetition_loop: bool = False
    last_chunk: Optional[dict[str, Any]] = None
    unfinished_choices: Optional[set[int]] = None
    reader_stopped: bool = False


class _TimedSseReader:
    """Один bounded reader; ожидание I/O не мешает heartbeat и дедлайну."""

    def __init__(
        self,
        readline: Callable[[int], bytes],
        write: Callable[[bytes], None],
        limits: PassthroughLimits,
        deadline: float | SlidingDeadline,
        window: LivenessWindow | None = None,
        enforce: bool = False,
    ) -> None:
        self.limits = limits
        self.cell = SlidingDeadline.wrap(deadline)
        self.write = write
        self.progress = SseProgress(window, enforce, self.cell)
        self.items: queue.Queue[bytes | Exception] = queue.Queue(
            maxsize=limits.read_queue_max_entries
        )
        self.stop = threading.Event()
        self.request_read: threading.Semaphore = threading.Semaphore(0)
        self.last_input = time.monotonic()

        def read() -> None:
            try:
                while not self.stop.is_set():
                    # Без чтения вперёд: после [DONE]/ошибки поток не должен
                    # удерживать lock HTTPResponse в блокирующем readline.
                    if not self.request_read.acquire(timeout=limits.poll_interval_s):
                        continue
                    if self.stop.is_set():
                        return
                    line = readline(limits.max_body_bytes + 1)
                    while not self.stop.is_set():
                        try:
                            self.items.put(line, timeout=limits.poll_interval_s)
                            break
                        except queue.Full:
                            continue
                    if not line:
                        return
            except (OSError, http.client.HTTPException, ValueError) as exc:
                while not self.stop.is_set():
                    try:
                        self.items.put(exc, timeout=limits.poll_interval_s)
                        return
                    except queue.Full:
                        continue

        self.thread = threading.Thread(target=read, daemon=True, name="passthrough-sse")
        self.thread.start()

    def readline(self, _limit: int) -> bytes:
        self.request_read.release()
        while True:
            now = time.monotonic()
            remaining = self.progress.remaining(self.cell.deadline_s - now)
            if self.progress.last_progress is not None:
                remaining = min(
                    remaining, self.progress.last_progress + self.limits.idle_timeout_s - now
                )
            if remaining <= 0:
                raise TimeoutError("upstream stream deadline exceeded")
            heartbeat_due = self.last_input + self.limits.heartbeat_interval_s - now
            if heartbeat_due <= 0:
                self.write(b": keepalive\n\n")
                self.last_input = time.monotonic()
                heartbeat_due = self.limits.heartbeat_interval_s
            try:
                item = self.items.get(
                    timeout=min(remaining, heartbeat_due, self.limits.poll_interval_s)
                )
            except queue.Empty:
                continue
            if time.monotonic() >= self.cell.deadline_s:
                raise TimeoutError("upstream stream deadline exceeded")
            if isinstance(item, Exception):
                raise item
            if item:
                self.last_input = time.monotonic()
            return item

    def close(self) -> None:
        self.stop.set()
        self.request_read.release()
        self.thread.join(timeout=self.limits.reader_join_timeout_s)


def relay_sse(
    readline: Callable[[int], bytes],
    write: Callable[[bytes], None],
    *,
    tool_schemas: Optional[dict[str, Any]],
    limits: PassthroughLimits,
    process: Optional[ProcessBudget] = None,
    sanitize: bool = True,
    trusted_tools: bool = False,
    state: StreamOutcome | None = None,
    deadline: float | SlidingDeadline | None = None,
    window: LivenessWindow | None = None,
) -> StreamOutcome:
    """Пробросить SSE-поток upstream клиенту с санитизацией `tool_calls` (AD-005).

    Исходный порядок событий сохраняется; единственное изменение — вызовы choice выходят
    одним кадром прямо перед терминальным чанком своей choice, после санитизации.
    """
    reader = _TimedSseReader(
        readline,
        write,
        limits,
        deadline if deadline is not None else time.monotonic() + limits.total_timeout_s,
        window,
    )
    outcome = state if state is not None else StreamOutcome()
    client_write = write

    def write(frame: bytes) -> None:
        """До вызова sink: даже частичная запись запрещает повтор запроса."""
        outcome.committed = True
        client_write(frame)

    acc = ToolCallAccumulator(limits, process)
    seen: set[int] = set()
    finished: set[int] = set()
    last_chunk: dict[str, Any] = {}
    guards: dict[int, RepetitionGuard] = {}
    parsers: dict[int, ToolCallParser] = {}
    parser_content: dict[int, list[str]] = {}
    parser_calls: dict[int, list[dict]] = {}

    def guard_for(index: int) -> RepetitionGuard:
        if index not in guards:
            guards[index] = RepetitionGuard(
                max_repeats=limits.repetition_max_repeats,
                max_token_len=limits.repetition_max_token_len,
                enabled=limits.repetition_guard_enabled,
            )
        return guards[index]

    def repetition_error() -> StreamOutcome:
        acc.close()
        outcome.repetition_loop = True
        write(
            _error_frame(
                last_chunk,
                "upstream_repetition_loop",
                "upstream repetition loop detected",
            )
        )
        return outcome

    def check_repetition(index: int, text: str) -> bool:
        if not limits.repetition_guard_enabled or not text:
            return False
        return guard_for(index).feed(text)[1]

    def parser_for(index: int) -> ToolCallParser:
        if index not in parsers:
            parser_content[index] = []
            parser_calls[index] = []
            parsers[index] = ToolCallParser(
                parser_content[index].append,
                parser_calls[index].append,
                tool_schemas=tool_schemas,
                repetition_guard_enabled=False,
            )
        return parsers[index]

    def add_invoke_calls(index: int) -> None:
        for call in parser_calls.get(index, ()):
            arguments = call.get("arguments")
            acc.add(
                index,
                [
                    {
                        "index": acc.next_tool_index(index),
                        "id": str(call.get("id") or new_call_id()),
                        "type": "function",
                        "function": {
                            "name": str(call.get("name") or ""),
                            "arguments": arguments
                            if isinstance(arguments, str)
                            else json.dumps(arguments or {}, ensure_ascii=False),
                        },
                    }
                ],
            )
        if index in parser_calls:
            parser_calls[index].clear()

    def content_frame(base: Mapping[str, Any], index: int, text: str) -> bytes:
        payload: dict[str, Any] = {
            k: base[k] for k in base if k not in ("choices", "usage", "error")
        }
        payload.setdefault("id", last_chunk.get("id") or "chatcmpl-passthrough")
        payload.setdefault("object", "chat.completion.chunk")
        payload.setdefault("created", last_chunk.get("created") or int(time.time()))
        payload.setdefault("model", last_chunk.get("model") or "")
        payload["choices"] = [
            {"index": index, "delta": {"content": text}, "finish_reason": None}
        ]
        return _data_frame(payload)

    def flush_parser(index: int, base: Mapping[str, Any]) -> Optional[StreamOutcome]:
        """`finish()` парсера choice: удержанный content уходит перед терминалом."""
        if index not in parsers:
            return None
        parser_content[index].clear()
        add_invoke_calls(index)
        parsers[index].finish()
        flushed = "".join(parser_content[index])
        parser_content[index].clear()
        if flushed:
            if check_repetition(index, flushed):
                return repetition_error()
            write(content_frame(base, index, flushed))
        add_invoke_calls(index)
        del parsers[index]
        return None

    try:
        for raw, data in iter_sse_events(reader.readline, limits.max_body_bytes):
            chunk = reader.progress.note(data)
            if data is None:
                write(raw)  # комментарий/keepalive/event без data — дословно
                continue
            if data.strip() == "[DONE]":
                for pending_index in sorted(list(parsers)):
                    flushed_outcome = flush_parser(pending_index, last_chunk)
                    if flushed_outcome is not None:
                        return flushed_outcome
                if acc.pending_choices() or (trusted_tools and seen - finished):
                    acc.close()  # [DONE] без finish_reason у choice с вызовами: успеха нет
                    outcome.incomplete = True
                    write(
                        _error_frame(
                            last_chunk,
                            "upstream_incomplete_stream",
                            "upstream stream ended before finish_reason",
                        )
                    )
                    return outcome
                outcome.done = True
                write(raw)
                return outcome
            if chunk is None:
                write(raw)
                continue
            choices = chunk.get("choices") if isinstance(chunk, dict) else None
            if not isinstance(choices, list):
                if isinstance(chunk, dict):
                    meta = {
                        k: chunk.get(k)
                        for k in ("id", "created", "model")
                        if chunk.get(k) is not None
                    }
                    if meta:
                        outcome.last_chunk = {**(outcome.last_chunk or {}), **meta}
                write(raw)
                continue
            if not sanitize:
                outcome.last_chunk = {
                    k: chunk.get(k) for k in ("id", "created", "model")
                }
                for choice in choices:
                    if isinstance(choice, dict):
                        idx = choice_index(choice.get("index"))
                        seen.add(idx)
                        if choice.get("finish_reason"):
                            finished.add(idx)
                        if limits.repetition_guard_enabled:
                            delta = choice.get("delta")
                            text_value = (
                                delta.get("content")
                                if isinstance(delta, dict)
                                else None
                            )
                            if isinstance(text_value, str) and check_repetition(
                                idx, text_value
                            ):
                                return repetition_error()
                outcome.unfinished_choices = set(seen - finished)
                write(raw)
                continue
            last_chunk = {k: chunk.get(k) for k in ("id", "created", "model")}
            outcome.last_chunk = last_chunk
            modified = False
            terminal: list[int] = []
            terminal_content: dict[int, str] = {}
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                index = choice_index(choice.get("index"))
                seen.add(index)
                delta = choice.get("delta")
                if isinstance(delta, dict) and "tool_calls" in delta:
                    if trusted_tools:
                        calls = delta["tool_calls"]
                        if isinstance(calls, list):
                            outcome.tool_calls_published += sum(
                                isinstance(call, dict) and bool(call.get("id"))
                                for call in calls
                            )
                    else:
                        acc.add(index, delta["tool_calls"])
                        delta = {k: v for k, v in delta.items() if k != "tool_calls"}
                        choice["delta"] = delta
                        modified = True
                if isinstance(delta, dict):
                    content_value = delta.get("content")
                    if isinstance(content_value, str) and content_value:
                        text_out = content_value
                        if limits.invoke_normalization_enabled:
                            parser_content[index] = parser_content.get(index, [])
                            parser = parser_for(index)
                            parser_content[index].clear()
                            parser.feed(content_value)
                            text_out = "".join(parser_content[index])
                            parser_content[index].clear()
                            had_calls = bool(parser_calls.get(index))
                            add_invoke_calls(index)
                            if text_out != content_value or had_calls:
                                delta = dict(delta)
                                if text_out:
                                    delta["content"] = text_out
                                else:
                                    delta.pop("content", None)
                                choice["delta"] = delta
                                modified = True
                        if check_repetition(index, text_out):
                            return repetition_error()
                if choice.get("finish_reason"):
                    finished.add(index)
                    terminal.append(index)
                    if (
                        isinstance(delta, dict)
                        and isinstance(delta.get("content"), str)
                        and delta["content"]
                    ):
                        terminal_content[index] = delta["content"]
                        delta = {k: v for k, v in delta.items() if k != "content"}
                        choice["delta"] = delta
                        modified = True
            outcome.unfinished_choices = set(seen - finished)
            for index in sorted(terminal):
                if index in terminal_content:
                    write(content_frame(chunk, index, terminal_content[index]))
                flushed_outcome = flush_parser(index, chunk)
                if flushed_outcome is not None:
                    return flushed_outcome
                if not acc.has_choice(index):
                    continue
                calls = sanitize_choice_calls(
                    acc.pop_choice(index), tool_schemas, limits
                )
                outcome.tool_calls_published += len(calls)
                write(
                    _data_frame(
                        {
                            **{
                                k: chunk[k]
                                for k in chunk
                                if k not in ("choices", "usage", "error")
                            },
                            "choices": [
                                {
                                    "index": index,
                                    "delta": {"tool_calls": calls},
                                    "finish_reason": None,
                                }
                            ],
                        }
                    )
                )
            if not modified:
                write(raw)
                continue
            only_empty = all(
                isinstance(c, dict)
                and not c.get("delta")
                and not c.get("finish_reason")
                for c in choices
            )
            if choices and only_empty and "usage" not in chunk and "error" not in chunk:
                continue  # чанк состоял только из дельт tool_calls
            write(_data_frame(chunk))
        # EOF без [DONE]: недособранное сбрасывается, незавершённые choices — ошибка.
        for pending_index in sorted(list(parsers)):
            flushed_outcome = flush_parser(pending_index, last_chunk)
            if flushed_outcome is not None:
                return flushed_outcome
        unfinished = seen - finished
        if acc.pending_choices() or unfinished:
            acc.close()
            outcome.incomplete = True
            write(
                _error_frame(
                    last_chunk,
                    "upstream_incomplete_stream",
                    "upstream stream ended before finish_reason",
                )
            )
        return outcome
    except AccumulatorOverflow:
        acc.close()
        outcome.overflow = True
        write(
            _error_frame(
                last_chunk,
                "upstream_response_too_large",
                "upstream tool_calls exceed the bridge limit",
            )
        )
        return outcome
    except UpstreamBodyTooLarge:
        acc.close()
        outcome.overflow = True
        write(
            _error_frame(
                last_chunk,
                "upstream_response_too_large",
                "upstream event exceeds the bridge limit",
            )
        )
        return outcome
    finally:
        acc.close()
        reader.close()
        outcome.reader_stopped = not reader.thread.is_alive()


def _json_error(
    status: int, error_type: str, message: str
) -> tuple[list[tuple[str, str]], bytes]:
    body = json.dumps(
        {"error": {"message": message, "type": error_type, "code": status}},
        ensure_ascii=False,
    ).encode("utf-8")
    return [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ], body


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
    CONSTRAINTS = KindConstraints(base_url_allowed=True, api_key_env_allowed=True)
    capabilities = Capabilities(
        sessions=SESSIONS_NONE, streaming=STREAMING_NATIVE, usage="exact"
    )

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
        is_hub_key: Optional[Callable[[str], bool]] = None,
    ) -> None:
        super().__init__(backend_id, config, catalog_source, host)
        self._is_hub_key = is_hub_key
        api_key_env = self.config.get("api_key_env")
        api_key = self.config.get("api_key")
        self._upstream_key = (
            os.environ.get(api_key_env) if isinstance(api_key_env, str) else ""
        ) or (api_key if isinstance(api_key, str) else "")
        self._limits = limits
        initial_limits = self.limits
        self._pool: PassthroughConnectionPool = PassthroughConnectionPool(
            initial_limits.max_keepalive_connections, initial_limits.keepalive_expiry_s
        )
        self.process_budget = process_budget or ProcessBudget(
            initial_limits.accumulator_max_process_bytes
        )
        self._sanitize = sanitize
        self._active = 0
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(self.max_concurrent)
        base_url = self.config.get("base_url")
        if not isinstance(base_url, str) or not _LOOPBACK_V1_RE.fullmatch(base_url):
            raise ValueError("backend_base_url_invalid")
        parts = urllib.parse.urlsplit(base_url)
        if parts.hostname is None or parts.port is None or not 1 <= parts.port <= 65535:
            raise ValueError("backend_base_url_invalid")
        self._host = parts.hostname
        self._port = parts.port
        self._base_path = parts.path.rstrip("/")

    @property
    def limits(self) -> PassthroughLimits:
        return (
            self._limits if self._limits is not None else PassthroughLimits.from_env()
        )

    @limits.setter
    def limits(self, value: Optional[PassthroughLimits]) -> None:
        self._limits = value

    # -- контракт BackendAdapter ---------------------------------------------------------
    def validate_client_token(self, token: str) -> bool:
        """Проверяет клиентский токен по собственному настроенному ключу upstream."""
        if not self._upstream_key or not token:
            return False
        return hmac.compare_digest(
            token.encode("utf-8"), self._upstream_key.encode("utf-8")
        )

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

    def execute_turn(
        self, ctx: TurnContext, sse_writer: Optional[StreamSink]
    ) -> TurnResult:
        raise BackendNotSupported("passthrough_raw_seam")

    def close_session(self, sid: str) -> None:
        return None

    def shutdown(self) -> None:
        self._pool.close_all()

    # -- upstream-параметры шва (api_key_ref / headers_from_json / per_request_headers) ----
    def _read_key_ref(self) -> str:
        """Токен из `api_key_ref` (`file:<путь>`); читается на каждый запрос (ротация ключа)."""
        ref = self.config.get("api_key_ref")
        if not isinstance(ref, str) or not ref.startswith("file:"):
            return ""
        try:
            with open(os.path.expanduser(ref[len("file:") :]), encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError:
            self._log("passthrough api_key_ref unreadable")
            return ""

    def _read_json_headers(self) -> dict[str, str]:
        """Заголовки `headers_from_json`: узел `json_path` файла, ключи из `pick` (без регистра)."""
        spec = self.config.get("headers_from_json")
        if not isinstance(spec, Mapping):
            return {}
        json_path = spec.get("json_path")
        if not isinstance(json_path, list):
            return {}
        try:
            with open(os.path.expanduser(str(spec["file"])), encoding="utf-8") as fh:
                node: Any = json.load(fh)
            for part in json_path:
                node = node[str(part)]
        except (OSError, ValueError, KeyError, TypeError):
            self._log("passthrough headers_from_json unreadable")
            return {}
        if not isinstance(node, dict):
            return {}
        pick = spec.get("pick")
        if not isinstance(pick, list):
            return {}
        by_lower = {str(k).lower(): (str(k), v) for k, v in node.items()}
        picked: dict[str, str] = {}
        for name in pick:
            found = by_lower.get(str(name).lower())
            if found is not None and isinstance(found[1], str) and found[1]:
                picked[str(name)] = found[1]
        return picked

    def _upstream_headers(self) -> dict[str, str]:
        """Заголовки, принудительно заменяющие клиентские: из файла, затем per-request."""
        extra = self._read_json_headers()
        per_request = self.config.get("per_request_headers")
        if isinstance(per_request, Mapping):
            for name, template in per_request.items():
                extra[str(name)] = str(template).replace("{uuid4}", str(uuid.uuid4()))
        return extra

    def _with_body_defaults(self, raw_body: bytes) -> bytes:
        """Подставляет `default_body_extra` в JSON-тело для ключей, которых клиент не задал."""
        extra = self.config.get("default_body_extra")
        if not isinstance(extra, Mapping) or not extra:
            return raw_body
        try:
            data = json.loads(raw_body)
        except ValueError:
            return raw_body
        if not isinstance(data, dict):
            return raw_body
        effort = data.get("reasoning_effort")
        if isinstance(effort, str) and effort.strip().lower() not in _NO_EFFORT_VALUES:
            return raw_body  # клиент явно запросил рассуждение: дефолт «выключено» не навязываем
        missing = {k: copy.deepcopy(v) for k, v in extra.items() if k not in data}
        if not missing:
            return raw_body
        return json.dumps({**data, **missing}, ensure_ascii=False).encode("utf-8")

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
        window: LivenessWindow | None = None,
    ) -> None:
        """One request: body goes upstream unmodified (AD-001: internal stream=true), response goes to `sink`."""
        raw_body = self._with_body_defaults(raw_body)
        internal = internal_stream_body(path, request, raw_body)
        if internal is not None:
            raw_body, window = internal, window or passthrough_window(self.limits, path, request)
        deadline, open_deadline = request_deadlines(self.limits, internal is not None)
        slide = open_sliding_deadline(deadline, self.limits, internal is not None, request, _SLIDING_WIN_FLAG.enabled)
        queue_timeout = min(
            float(getattr(self.host, "QUEUE_TIMEOUT_S", DEFAULT_QUEUE_TIMEOUT_S)),
            self.limits.total_timeout_s,
        )
        if not self._slots.acquire(timeout=queue_timeout):
            self._fail(sink, 503, "overloaded", "passthrough backend is saturated")
            return
        with self._lock:
            self._active += 1
        conn: Optional[http.client.HTTPConnection] = None
        opened_pooling: list[bool] = []
        transport: list[socket.socket] = []
        stop = threading.Event()
        aborted = threading.Event()
        transport_lock = threading.Lock()
        resp: http.client.HTTPResponse | None = None
        successful = False

        def abort() -> None:
            with transport_lock:
                if stop.is_set():
                    return
                aborted.set()
                for sock in transport:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        continue

        def watch() -> None:
            while not stop.wait(min(self.limits.poll_interval_s, max(0.0, slide.deadline_s - time.monotonic()))):
                if time.monotonic() >= slide.deadline_s or sink.client_gone():
                    abort()
                    return

        def on_socket(sock: socket.socket) -> None:
            with transport_lock:
                if aborted.is_set():
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    sock.close()
                    raise ClientGone() if sink.client_gone() else TimeoutError()
                transport.append(sock)

        watcher = threading.Thread(
            target=watch, daemon=True, name="passthrough-deadline"
        )
        watcher.start()
        try:
            try:
                if sink.client_gone():
                    raise ClientGone()
                if aborted.is_set() or time.monotonic() >= deadline:
                    raise TimeoutError()
                conn = self._open(
                    path,
                    raw_body,
                    headers,
                    deadline=open_deadline,
                    on_socket=on_socket,
                    presend_deadline=getattr(sink, "presend_deadline", None),
                    on_pooling=opened_pooling.append,
                )
                if sink.client_gone():
                    raise ClientGone()
                if aborted.is_set() or time.monotonic() >= deadline:
                    raise TimeoutError()
                resp = conn.getresponse()
                if time.monotonic() >= deadline:
                    raise TimeoutError()
                slide.relax_socket(conn.sock, self.limits.read_timeout_s, internal is not None)
                if resp.status in (502, 503) and getattr(
                    sink, "accepts_presend_errors", False
                ):
                    try:
                        body = _read_bounded(resp, self.limits.max_body_bytes)
                    except UpstreamBodyTooLarge:
                        self._fail(
                            sink,
                            502,
                            "upstream_response_too_large",
                            "upstream response exceeds the bridge limit",
                        )
                        return
                    raise PreSendTransientError(
                        "transient upstream HTTP status",
                        status_code=resp.status,
                        response_headers=tuple(
                            self._response_headers(resp)
                            + [("Content-Length", str(len(body)))]
                        ),
                        response_body=body,
                    )
            except PreSendTransientError as exc:
                if getattr(sink, "accepts_presend_errors", False):
                    raise
                if exc.status_code == 504 or isinstance(exc.__cause__, TimeoutError):
                    self._fail(
                        sink,
                        504,
                        "upstream_timeout",
                        "upstream did not respond in time",
                    )
                else:
                    self._fail(
                        sink, 502, "upstream_unavailable", "upstream is unavailable"
                    )
                return
            except socket.timeout:
                self._fail(
                    sink, 504, "upstream_timeout", "upstream did not respond in time"
                )
                return
            except (OSError, http.client.HTTPException):
                if time.monotonic() >= deadline:
                    self._fail(
                        sink,
                        504,
                        "upstream_timeout",
                        "upstream did not respond in time",
                    )
                else:
                    self._fail(
                        sink, 502, "upstream_unavailable", "upstream is unavailable"
                    )
                return
            successful = self._respond(resp, request, sink, deadline, on_timeout=abort, window=window, slide=slide)
        except ClientGone:
            abort()
            self._log("passthrough client_gone")
        finally:
            # Watcher не должен сбросить сокет, уже выданный следующему запросу.
            with transport_lock:
                stop.set()
                transport.clear()
            watcher.join(timeout=self.limits.reader_join_timeout_s)
            if conn is not None:
                can_reuse = (
                    os.environ.get("BRIDGE_CONNECTION_POOLING_ENABLED", "1").lower()
                    not in ("0", "false", "no")
                    and bool(opened_pooling)
                    and opened_pooling[-1]
                    and successful
                    and not aborted.is_set()
                    and resp is not None
                    and resp.isclosed()
                    and not resp.will_close
                    and not (
                        "text/event-stream"
                        in (resp.getheader("Content-Type") or "").lower()
                        and resp.getheader("Content-Length") is None
                    )
                    and "close"
                    not in {
                        token.strip().lower()
                        for token in (resp.getheader("Connection") or "").split(",")
                    }
                )
                self._pool.release_connection(
                    self._host, self._port, conn, can_reuse=can_reuse
                )
            with self._lock:
                self._active -= 1
            self._slots.release()

    def _open(
        self,
        path: str,
        raw_body: bytes,
        headers: Mapping[str, str],
        *,
        deadline: float | None = None,
        on_socket: Callable[[socket.socket], None] | None = None,
        presend_deadline: float | None = None,
        on_reuse: Callable[[bool], None] | None = None,
        on_pooling: Callable[[bool], None] | None = None,
        fresh: bool = False,
    ) -> http.client.HTTPConnection:
        remaining = (
            self.limits.total_timeout_s
            if deadline is None
            else deadline - time.monotonic()
        )
        if remaining <= 0:
            raise TimeoutError("upstream total deadline exceeded")
        connect_remaining = remaining
        if presend_deadline is not None:
            connect_remaining = min(remaining, presend_deadline - time.monotonic())
            if connect_remaining <= 0:
                raise PreSendTransientError(
                    "upstream connect budget exhausted", status_code=504
                )
        is_pooling_enabled = os.environ.get(
            "BRIDGE_CONNECTION_POOLING_ENABLED", "1"
        ).strip().lower() in ("1", "true", "yes", "on")
        if not is_pooling_enabled:
            self._pool.close_all()
        try:
            conn, reused = self._pool.get_connection(
                self._host,
                self._port,
                min(self.limits.connect_timeout_s, connect_remaining),
                fresh=fresh or not is_pooling_enabled,
            )
        except (ConnectionError, socket.gaierror, TimeoutError) as exc:
            # Запрос ещё не посылался: это транспортный отказ, безопасный для общего retry.
            raise PreSendTransientError("upstream connect failed") from exc
        try:
            if on_pooling is not None:
                on_pooling(is_pooling_enabled)
            if on_reuse is not None:
                on_reuse(reused)
            if conn.sock is not None:
                if on_socket is not None:
                    on_socket(conn.sock)
                remaining = (
                    self.limits.total_timeout_s
                    if deadline is None
                    else deadline - time.monotonic()
                )
                if remaining <= 0:
                    conn.close()
                    raise TimeoutError("upstream total deadline exceeded")
                conn.sock.settimeout(min(self.limits.read_timeout_s, remaining))
            forwarded = {
                k: v for k, v in headers.items() if k.lower() not in _REQUEST_DROP
            }
            upstream_token = self._upstream_key or self._read_key_ref()
            if upstream_token:
                forwarded = {
                    k: v
                    for k, v in forwarded.items()
                    if k.lower() not in ("authorization", "x-api-key")
                }
                forwarded["Authorization"] = f"Bearer {upstream_token}"
            else:
                client_toks: list[str] = []
                for k, v in headers.items():
                    if k.lower() == "authorization" and v.strip():
                        parts = v.strip().split(None, 1)
                        if len(parts) == 2 and parts[0].lower() == "bearer":
                            if parts[1].strip():
                                client_toks.append(parts[1].strip())
                        elif len(parts) == 1:
                            client_toks.append(parts[0])
                    elif k.lower() == "x-api-key" and v.strip():
                        client_toks.append(v.strip())
                is_hub_credential = False
                if client_toks:
                    is_hub_key_cb = getattr(self, "_is_hub_key", None)
                    if is_hub_key_cb is None:
                        is_hub_key_cb = getattr(self.host, "is_hub_key", None)
                    if callable(is_hub_key_cb):
                        is_hub_credential = any(
                            is_hub_key_cb(client_tok) for client_tok in client_toks
                        )
                if is_hub_credential:
                    # Мастер-ключ хаба на upstream не уходит.
                    forwarded = {
                        k: v
                        for k, v in forwarded.items()
                        if k.lower() not in ("authorization", "x-api-key")
                    }
            upstream_headers = self._upstream_headers()
            if upstream_headers:
                replaced = {name.lower() for name in upstream_headers}
                forwarded = {
                    k: v for k, v in forwarded.items() if k.lower() not in replaced
                }
                forwarded.update(upstream_headers)
            forwarded["Host"] = f"{self._host}:{self._port}"
            forwarded["Content-Length"] = str(len(raw_body))
            forwarded["Accept-Encoding"] = (
                "identity"  # тело нужно разобрать, а не передать сжатым
            )
            forwarded["Connection"] = "keep-alive" if is_pooling_enabled else "close"
            route, _, query = path.partition("?")
            suffix = route[len("/v1") :] if route.startswith("/v1/") else route
            target = self._base_path + suffix + ("?" + query if query else "")
            try:
                conn.request("POST", target, body=raw_body, headers=forwarded)
            except http.client.CannotSendRequest:
                conn.close()
                if not reused or fresh:
                    raise
                # Повтор допустим только при CannotSendRequest: запрос ещё не отправлен. BrokenPipe/ConnectionReset пробрасываются в 502 — байты могли уже уйти.
                return self._open(
                    path,
                    raw_body,
                    headers,
                    deadline=deadline,
                    on_socket=on_socket,
                    presend_deadline=presend_deadline,
                    on_reuse=on_reuse,
                    on_pooling=on_pooling,
                    fresh=True,
                )
        except BaseException:
            conn.close()
            raise
        return conn

    def _fail(
        self, sink: ResponseSink, status: int, error_type: str, message: str
    ) -> None:
        self._log(f"passthrough fail status={status} type={error_type}")
        headers, body = _json_error(status, error_type, message)
        sink.start(status, headers)
        sink.write(body)

    def _response_headers(
        self, resp: http.client.HTTPResponse
    ) -> list[tuple[str, str]]:
        return [(k, v) for k, v in resp.getheaders() if k.lower() not in _RESPONSE_DROP]

    def _respond(
        self,
        resp: http.client.HTTPResponse,
        request: Mapping[str, Any],
        sink: ResponseSink,
        deadline: float | None = None,
        *,
        on_timeout: Callable[[], None] | None = None,
        window: LivenessWindow | None = None,
        slide: SlidingDeadline | None = None,
    ) -> bool:
        content_type = (resp.getheader("Content-Type") or "").lower()
        encoded = (
            resp.getheader("Content-Encoding") or "identity"
        ).lower() != "identity"
        sanitize = self._sanitize_enabled()
        schemas = build_tool_schemas(request.get("tools")) if sanitize else None
        sse = resp.status == 200 and "text/event-stream" in content_type
        agg = window if sse and window and window.internal_stream else None
        if sse and agg is None:
            return self._relay_stream(resp, schemas, sink, sanitize, slide or deadline, on_timeout, window)
        try:
            if agg is not None:
                body = self._aggregate_sse(resp, agg)
                content_type = "application/json"
            else:
                body = _read_bounded(resp, self.limits.max_body_bytes)
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("upstream total deadline exceeded")
        except NonstreamError as exc:
            self._fail(sink, exc.status, exc.code, exc.message)
            return False
        except UpstreamBodyTooLarge:
            self._fail(
                sink,
                502,
                "upstream_response_too_large",
                "upstream response exceeds the bridge limit",
            )
            return False
        except socket.timeout:
            self._fail(
                sink, 504, "upstream_timeout", "upstream did not respond in time"
            )
            return False
        except (OSError, http.client.HTTPException):
            if deadline is not None and time.monotonic() >= deadline:
                self._fail(
                    sink, 504, "upstream_timeout", "upstream did not respond in time"
                )
            else:
                self._fail(sink, 502, "upstream_unavailable", "upstream is unavailable")
            return False
        if sanitize and resp.status == 200 and "json" in content_type and not encoded:
            body = sanitize_completion_body(body, schemas, self.limits)
        headers = self._response_headers(resp) + [("Content-Length", str(len(body)))]
        if agg is not None:
            headers = [h for h in headers if h[0].lower() != "content-type"]
            headers.append(("Content-Type", "application/json; charset=utf-8"))
        sink.start(resp.status, headers)
        sink.write(body)
        return True

    def _aggregate_sse(self, resp: http.client.HTTPResponse, window: LivenessWindow) -> bytes:
        lim = self.limits
        reader = _TimedSseReader(resp.readline, lambda _f: None, lim, math.inf, window, True)
        try:
            events = iter_sse_events(reader.readline, lim.max_body_bytes)
            return aggregate_events(events, window.record_signal, lim.max_body_bytes, window.expired)
        finally:
            reader.close()

    def _relay_stream(
        self,
        resp: http.client.HTTPResponse,
        schemas: Optional[dict[str, Any]],
        sink: ResponseSink,
        sanitize: bool,
        deadline: float | SlidingDeadline | None = None,
        on_timeout: Callable[[], None] | None = None,
        window: LivenessWindow | None = None,
    ) -> bool:
        # Выбор доверия фиксируется до sink.start (первой записи клиенту).
        # Маркер допустим только от настроенного аутентифицированного loopback peer.
        flag = getattr(self.host, "is_trusted_tool_streaming_enabled", None)
        trusted = (
            sanitize
            and self.config.get("trusted_tool_sanitizer") is True
            and bool(self._upstream_key)
            and self._host == "127.0.0.1"
            and callable(flag)
            and flag() is True
            and resp.getheader("X-Bridge-Tool-Sanitized") == "1"
        )
        headers = [
            (k, v)
            for k, v in self._response_headers(resp)
            if k.lower() != "content-type"
        ]
        headers += [
            ("Content-Type", "text/event-stream"),
            ("Cache-Control", "no-cache"),
            ("X-Accel-Buffering", "no"),
        ]
        outcome = StreamOutcome(committed=True)
        sink.start(200, headers)  # Заголовки тоже фиксируют ответ; повтор уже запрещён.
        try:
            outcome = relay_sse(
                resp.readline,
                sink.write,
                tool_schemas=schemas,
                limits=self.limits,
                process=self.process_budget,
                sanitize=sanitize,
                trusted_tools=trusted,
                state=outcome,
                deadline=deadline,
                window=window,
            )
        except (socket.timeout, OSError, http.client.HTTPException) as exc:
            if (
                isinstance(exc, (TimeoutError, socket.timeout))
                and on_timeout is not None
            ):
                on_timeout()
            last_chunk = getattr(outcome, "last_chunk", None) or {}
            unfinished_set = getattr(outcome, "unfinished_choices", None)
            if unfinished_set is not None and len(unfinished_set) == 0:
                sink.write(b"data: [DONE]\n\n")
                return False

            unfinished = sorted(unfinished_set) if unfinished_set is not None else [0]
            sink.write(
                format_stream_error_sse(
                    message="upstream stream failed",
                    code="upstream_stream_error",
                    model=str(last_chunk.get("model") or getattr(self, "id", "") or ""),
                    completion_id=last_chunk.get("id"),
                    created=last_chunk.get("created"),
                    choice_indices=unfinished,
                ).encode("utf-8")
            )
            return False
        if outcome.incomplete or outcome.overflow:
            self._log(
                f"passthrough stream incomplete={outcome.incomplete} overflow={outcome.overflow}"
            )
        return (
            outcome.reader_stopped
            and not outcome.incomplete
            and not outcome.overflow
            and not outcome.repetition_loop
        )
