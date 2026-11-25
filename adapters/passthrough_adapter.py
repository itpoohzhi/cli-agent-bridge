"""Универсальный OpenAI passthrough: raw HTTP, режимы инструментов и SSE.

Запрос сохраняется; общий нормализатор и санитайзер ядра обрабатывают ответы.
Вызовы буферизуются до finish_reason; ошибки закрывают поток одним [DONE].
Лимиты читаются из env и передаются ядру аргументами (BND-001).
"""

from __future__ import annotations

import copy
import hmac
import http.client
import io
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
from typing import Any, Callable, Iterator, Mapping, Optional, TypedDict, Unpack, cast

from adapters.passthrough_pool import (
    PassthroughConnectionPool as _PassthroughConnectionPool,
)

from core import passthrough_precommit
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

from core.passthrough_response_text import (
    _check_native as _check_native,
    _merge_parsed_calls as _merge_parsed_calls,
    _openai_call as _openai_call,
    _ResponseText as _ResponseText,
    _normalize_message as _normalize_message,
    new_call_id as new_call_id,
    sanitize_choice_calls as sanitize_choice_calls,
    sanitize_completion_body as sanitize_completion_body,
)
from core.tool_emulation import (
    DEFAULT_MAX_PARALLEL_CALLS,
    DEFAULT_MAX_PARALLEL_DEPTH,
    DEFAULT_MAX_REPETITION_REPEATS,
    DEFAULT_MAX_REPETITION_TOKEN_LEN,
    LiveParserError,
    RepetitionGuard,
    build_tool_schemas,
    has_any_unnamed_call,
)
from core.cli_runtime_config import NonstreamConfig
from core.transport_credentials import resolve_credential
from core.liveness_signals import SIGNAL_S, LivenessWindow, SseProgress, parse_sse_json
from core.liveness_signals import passthrough_window as passthrough_window
from core.nonstream_aggregator import NonstreamError, aggregate_events, choice_index
from core.nonstream_aggregator import request_deadlines as request_deadlines
from core.nonstream_resilience import NonstreamRetryBulkhead, NonstreamRetryPolicy
from core.nonstream_resilience import should_retry_incomplete_nonstream
from core.nonstream_retry_runtime import RetryRuntime, retry_incomplete_once
from core.passthrough_adapter_runtime import (
    HandleRequestOptions,
    PassthroughRequest,
    RuntimeOptions,
    fail_context,
    handle_request,
)
from core.passthrough_exchange import OpenRequestOptions, open_request
from core.passthrough_sliding_window import (
    FLAG_PASSTHROUGH_SLIDING_WINDOW,
    SlidingDeadline,
)
from core.runtime_env import DynamicFlagSource, bounded_int as _bounded_int
from core.runtime_env import env_bool, positive_int as _positive_int
from core.runtime_env import resolve_toolless_tag_policy
from core.timeout_ladder import FLAG_TIMEOUT_LADDER, TimeoutLadderConfig, load_timeout_ladder_config
from core.tool_mode import (
    DEFAULT_EMULATE_SPEC,
    NormalizerModeSpec,
    ToolMode,
    build_mode_spec,
    format_tool_mode_log,
    resolve_tool_mode,
)
from core.stream_framing import build_stream_error_chunk, format_sse_event
from core.stream_guard import StreamGuard
from core.stream_framing import (
    format_stream_error_sse,
    is_graceful_error_framing_enabled,
)
from core.session_affinity import (
    register_response_affinity,
    request_scope,
    session_affinity,
)
from core.telemetry_hooks import telemetry_usage
from core.usage_wire import positive_wire_usage

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
DEFAULT_IDLE_TIMEOUT_S = 600.0
DEFAULT_TOTAL_TIMEOUT_S = 1800.0
DEFAULT_QUEUE_TIMEOUT_S = 900.0

KIND = "passthrough"

# Loopback-upstream с `/v1` в конце либо `/sg-*`; допустимы вложенные префиксы перед `/v1`.
_LOOPBACK_V1_RE = re.compile(
    r"http://(?:127\.0\.0\.1|localhost):[0-9]{1,5}(?:(?:/[a-z0-9._-]+)*/v1|/sg-[a-z0-9._-]+)"
)
_NO_EFFORT_VALUES = frozenset({"", "off", "none"})
_BODY_CONTROLS = frozenset(
    {
        "transport_seed",
        "exclude_transports",
        "transport_controls",
        "bridge_transport_controls",
    }
)

# Заголовки соединения (RFC 9110 §7.6.1) не пробрасываются; Host/Content-Length ставит шов.
_HOP_BY_HOP = frozenset(
    "connection keep-alive proxy-authenticate proxy-authorization "
    "proxy-connection te trailer trailers transfer-encoding upgrade".split()
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


def _strip_body_controls(data: dict[str, Any]) -> bool:
    """Удаляет управляющие поля и сообщает, нужна ли пересериализация."""
    removed = _BODY_CONTROLS.intersection(data)
    for key in removed:
        del data[key]
    return bool(removed)


def _apply_body_defaults(data: dict[str, Any], extra: Mapping[str, Any]) -> bool:
    """Сохраняет приоритет клиента и не возвращает transport-поля из конфига."""
    effort = data.get("reasoning_effort")
    if isinstance(effort, str) and effort.strip().lower() not in _NO_EFFORT_VALUES:
        return (
            False  # клиент явно запросил рассуждение: дефолт «выключено» не навязываем
        )
    missing = {
        key: copy.deepcopy(value)
        for key, value in extra.items()
        if key not in data and key not in _BODY_CONTROLS
    }
    data.update(missing)
    return bool(missing)


def _extract_response_id(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    val = payload.get("id")
    if isinstance(val, str) and val:
        return val
    resp = payload.get("response")
    if isinstance(resp, Mapping):
        r_val = resp.get("id")
        if isinstance(r_val, str) and r_val:
            return r_val
    return None


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
    stream_safety_cap_s: float = 3600.0
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
    timeout_ladder: TimeoutLadderConfig = field(default_factory=TimeoutLadderConfig)

    @classmethod
    def from_env(
        cls, environ: Optional[Mapping[str, str]] = None
    ) -> "PassthroughLimits":
        """Лимиты из окружения; нечисловое и неположительное значение -> default."""
        env = os.environ if environ is None else environ
        ns = NonstreamConfig.from_env(env)
        pi, pf, bi = _positive_int, _positive_float, _bounded_int
        try:
            ladder = load_timeout_ladder_config(env)
        except ValueError:
            if env_bool(env, (FLAG_TIMEOUT_LADDER,), False):
                raise
            ladder = TimeoutLadderConfig()
        on = ladder.enabled
        c_def = pf(env, ENV_CONNECT_TIMEOUT_S, ladder.connect_timeout_s if on else DEFAULT_CONNECT_TIMEOUT_S)
        return cls(
            max_keepalive_connections=pi(env, "BRIDGE_PASSTHROUGH_MAX_KEEPALIVE", pi(env, "BRIDGE_MAX_KEEPALIVE_CONNECTIONS", 32)),
            keepalive_expiry_s=pf(env, "BRIDGE_KEEPALIVE_EXPIRY_S", 30.0),
            max_parallel_calls=pi(env, ENV_MAX_PARALLEL_CALLS, DEFAULT_MAX_PARALLEL_CALLS),
            max_parallel_depth=pi(env, ENV_MAX_PARALLEL_DEPTH, DEFAULT_MAX_PARALLEL_DEPTH),
            max_body_bytes=pi(env, ENV_MAX_BODY_BYTES, DEFAULT_MAX_BODY_BYTES),
            accumulator_max_bytes=pi(env, ENV_ACC_MAX_BYTES, DEFAULT_ACC_MAX_BYTES),
            accumulator_max_keys=pi(env, ENV_ACC_MAX_KEYS, max(DEFAULT_ACC_MAX_KEYS, pi(env, ENV_MAX_PARALLEL_CALLS, DEFAULT_MAX_PARALLEL_CALLS))),
            accumulator_max_process_bytes=pi(env, ENV_ACC_MAX_PROCESS_BYTES, DEFAULT_ACC_MAX_PROCESS_BYTES),
            connect_timeout_s=pf(env, "BRIDGE_CONNECT_TIMEOUT_S", c_def),
            read_timeout_s=pf(env, ENV_READ_TIMEOUT_S, ladder.effective_read_chunk_s if on else DEFAULT_READ_TIMEOUT_S),
            idle_timeout_s=pf(env, "BRIDGE_IDLE_TIMEOUT_S", ladder.effective_idle_s if on else DEFAULT_IDLE_TIMEOUT_S),
            total_timeout_s=pf(env, "BRIDGE_TOTAL_TIMEOUT_S", DEFAULT_TOTAL_TIMEOUT_S),
            stream_safety_cap_s=pf(env, "BRIDGE_STREAM_SAFETY_CAP_S", ladder.safety_cap_s if on else 3600.0),
            heartbeat_interval_s=pf(env, "BRIDGE_SSE_HEARTBEAT_INTERVAL_S", 12.0),
            poll_interval_s=ns.poll_interval_s,
            reader_join_timeout_s=pf(env, "BRIDGE_PASSTHROUGH_READER_JOIN_TIMEOUT_S", 0.2),
            read_queue_max_entries=pi(env, "BRIDGE_PASSTHROUGH_READ_QUEUE_MAX_ENTRIES", 1),
            repetition_max_repeats=bi(env, ENV_REPETITION_MAX_REPEATS, DEFAULT_MAX_REPETITION_REPEATS, 3, 1000),
            repetition_max_token_len=bi(env, ENV_REPETITION_MAX_TOKEN_LEN, DEFAULT_MAX_REPETITION_TOKEN_LEN, 8, 512),
            repetition_guard_enabled=env_bool(env, (ENV_REPETITION_GUARD_ENABLED,), False),
            invoke_normalization_enabled=env_bool(env, (ENV_INVOKE_NORMALIZATION_ENABLED,), False),
            nonstream=ns,
            timeout_ladder=ladder,
        )


class PassthroughConnectionPool(_PassthroughConnectionPool):
    """Сохраняет динамические hooks прежнего публичного пути импорта пула."""

    def __init__(
        self,
        max_keepalive: int = PassthroughLimits.max_keepalive_connections,
        keepalive_expiry_s: float = PassthroughLimits.keepalive_expiry_s,
        select_fn: Callable[..., Any] = lambda r, w, x, timeout=0: select.select(
            r, w, x, timeout
        ),
        monotonic_fn: Callable[[], float] = lambda: time.monotonic(),
        connection_fn: Callable[..., Any] = lambda host, port, timeout: (
            http.client.HTTPConnection(host, port, timeout=timeout)
        ),
    ) -> None:
        super().__init__(
            max_keepalive, keepalive_expiry_s, select_fn, monotonic_fn, connection_fn
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


class _GuardedSink(ResponseSink):
    """Передаёт события guard, сохраняя байты и единственного писателя relay."""

    def __init__(self, sink: ResponseSink, guard: StreamGuard | None) -> None:
        self.sink: ResponseSink = sink
        self.start: Callable[[int, list[tuple[str, str]]], None] = sink.start
        self.guard: StreamGuard = (
            guard if guard is not None else getattr(sink, "stream_guard", None)
        ) or StreamGuard()

    def _drain(self) -> None:
        records = cast(list[dict[str, object]], self.guard.drain())
        if records:
            self.sink.write(b"".join(cast(bytes, r["_wire"]) for r in records))

    def write(self, frame: bytes) -> None:
        try:
            for raw, data in iter_sse_events(io.BytesIO(frame).readline, len(frame)):
                record = cast(dict[str, object], parse_sse_json(data) or {})
                if data is None and raw.lstrip().startswith(b":"):
                    record["type"] = "keepalive"
                record["_wire"] = raw
                if not self.guard.submit(record):
                    return
                if data is not None and data.strip() == "[DONE]":
                    self.guard.close()
            self._drain()
        except BaseException:
            _ = self.guard.submit({"error": {}, "_wire": b""})
            self.guard.close()
            self._drain()
            raise

    def close(self) -> None:
        self.guard.close()
        self._drain()


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
            fn = {"name": entry.name, "arguments": "".join(entry.arguments)}
            cid = entry.id or new_call_id()
            calls.append(
                {"index": key[1], "id": cid, "type": entry.type, "function": fn}
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


def _data_frame(payload: Mapping[str, Any]) -> bytes:
    return b"data: " + json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n\n"


def _error_frame(
    chunk: Mapping[str, Any],
    code: str,
    message: str,
    usage: Optional[Mapping[str, Any]] = None,
) -> bytes:
    """Терминальный error-chunk `chat.completion.chunk`; `usage` потока не обнуляется ошибкой."""
    return (
        format_sse_event(
            build_stream_error_chunk(
                message=message,
                model=str(chunk.get("model") or ""),
                code=code,
                finish_reason=(
                    "stop"
                    if is_graceful_error_framing_enabled()
                    and code != "upstream_tool_mode_violation"
                    else None
                ),
                completion_id=str(chunk.get("id") or "chatcmpl-passthrough"),
                created=chunk.get("created"),
                usage=usage,
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
    error_emitted: bool = False
    last_chunk: Optional[dict[str, Any]] = None
    last_usage: Optional[dict[str, Any]] = None
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
                    remaining,
                    self.progress.last_progress + self.limits.idle_timeout_s - now,
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


class _RepetitionLoop(Exception):
    """Guard обнаружил повтор уже нормализованного текста."""


class _EmptyToolCall(Exception):
    """Неполный пакет вызовов не должен публиковаться клиенту."""


def _delta_frame(base: Mapping[str, Any], index: int, delta: dict[str, Any]) -> bytes:
    payload = {
        key: value
        for key, value in base.items()
        if key not in ("choices", "usage", "error")
    }
    payload.setdefault("id", "chatcmpl-passthrough")
    payload.setdefault("object", "chat.completion.chunk")
    payload.setdefault("created", int(time.time()))
    payload.setdefault("model", "")
    payload["choices"] = [{"index": index, "delta": delta, "finish_reason": None}]
    return _data_frame(payload)


def _published_call_count(calls: Any) -> int:
    if not isinstance(calls, list):
        return 0
    return sum(isinstance(call, dict) and bool(call.get("id")) for call in calls)


def _stream_error_info(error: Any) -> tuple[str, str]:
    info = error if isinstance(error, dict) else {}
    code = str(info.get("code") or info.get("type") or "upstream_stream_error")
    return code, str(info.get("message") or error)


class _SseRelay:
    """Состояние одного relay; парсеры и буферы изолированы по choice.index."""

    def __init__(
        self,
        write: Callable[[bytes], None],
        schemas: Any,
        limits: PassthroughLimits,
        options: Mapping[str, Any],
    ) -> None:
        self.client_write, self.schemas, self.limits = write, schemas, limits
        self.spec: NormalizerModeSpec = options.get("mode_spec", DEFAULT_EMULATE_SPEC)
        self.sanitize = bool(options.get("sanitize", True))
        self.trusted = bool(options.get("trusted_tools", False))
        self.outcome: StreamOutcome = options.get("state") or StreamOutcome()
        self.acc = ToolCallAccumulator(limits, options.get("process"))
        self.seen, self.finished, self.tool_choices = set(), set(), set()
        self.last_chunk, self.guards, self.texts = {}, {}, {}

    def write(self, frame: bytes) -> None:
        self.outcome.committed = True
        self.client_write(frame)

    def error(self, code: str, message: str, flag: str) -> StreamOutcome:
        self.acc.close()
        setattr(self.outcome, flag, True)
        self.write(
            _error_frame(self.last_chunk, code, message, self.outcome.last_usage)
        )
        return self.outcome

    def _check_repetition(self, index: int, text: str) -> None:
        if not self.limits.repetition_guard_enabled or not text:
            return
        if index not in self.guards:
            self.guards[index] = RepetitionGuard(
                max_repeats=self.limits.repetition_max_repeats,
                max_token_len=self.limits.repetition_max_token_len,
                enabled=True,
            )
        if self.guards[index].feed(text)[1]:
            raise _RepetitionLoop()

    def _text_for(self, index: int) -> _ResponseText:
        if index not in self.texts:
            enabled = self.sanitize and self.limits.invoke_normalization_enabled
            self.texts[index] = _ResponseText(self.spec, self.schemas, enabled)
        return self.texts[index]

    def _add_parsed_calls(self, index: int) -> None:
        text = self.texts[index]
        for call in text.calls:
            entry = _openai_call(call)
            entry["index"] = self.acc.next_tool_index(index)
            self.acc.add(index, [entry])
        text.calls.clear()

    def _native_delta(self, index: int, delta: dict[str, Any]) -> dict[str, Any]:
        try:
            _check_native(self.spec, delta.get("tool_calls"))
        except LiveParserError:
            if self.sanitize:
                self.acc.add(index, delta.get("tool_calls"))
            raise
        if not self.sanitize or "tool_calls" not in delta:
            return delta
        if self.trusted:
            self.outcome.tool_calls_published += _published_call_count(
                delta["tool_calls"]
            )
            return delta
        self.acc.add(index, delta["tool_calls"])
        return {key: value for key, value in delta.items() if key != "tool_calls"}

    def _consume_choice(self, choice: dict[str, Any]) -> bool:
        original = dict(choice)
        index = choice_index(choice.get("index"))
        self.seen.add(index)
        delta = choice.get("delta")
        if isinstance(delta, dict):
            delta = self._native_delta(index, delta)
            text = self._text_for(index)
            delta = text.feed(delta)
            self._add_parsed_calls(index)
            if "tool_calls" in delta or self.acc.has_choice(index):
                self.tool_choices.add(index)
            content = delta.get("content")
            if isinstance(content, str):
                if index in self.tool_choices and not content.strip():
                    delta = {k: v for k, v in delta.items() if k != "content"}
                else:
                    self._check_repetition(index, content)
            choice["delta"] = delta
        if choice.get("finish_reason"):
            self.finished.add(index)
        return choice != original

    def _flush_text(self, index: int, base: Mapping[str, Any]) -> None:
        text = self.texts.pop(index, None)
        if text is None:
            return
        delta = text.finish()
        for call in text.calls:
            entry = _openai_call(call)
            entry["index"] = self.acc.next_tool_index(index)
            self.acc.add(index, [entry])
        if delta:
            self._check_repetition(index, delta.get("content", ""))
            self.write(_delta_frame(base, index, delta))

    def _terminal(self, choice: dict[str, Any], base: Mapping[str, Any]) -> bool:
        index = choice_index(choice.get("index"))
        delta = choice.get("delta")
        modified = False
        if self.sanitize and isinstance(delta, dict) and delta.get("content"):
            self.write(_delta_frame(base, index, {"content": delta["content"]}))
            choice["delta"] = {
                key: value for key, value in delta.items() if key != "content"
            }
            modified = True
        self._flush_text(index, base)
        if self.acc.has_choice(index):
            calls = self._validated_calls(index)
            self.outcome.tool_calls_published += len(calls)
            self.write(_delta_frame(base, index, {"tool_calls": calls}))
        return modified

    def _validated_calls(self, index: int) -> list[dict[str, Any]]:
        raw_calls = self.acc.pop_choice(index)
        calls = sanitize_choice_calls(raw_calls, self.schemas, self.limits)
        if not calls or has_any_unnamed_call(
            raw_calls, max_parallel_depth=self.limits.max_parallel_depth
        ):
            raise _EmptyToolCall()
        return calls

    def _consume_chunk(self, chunk: dict[str, Any], choices: list[Any]) -> bool:
        self.last_chunk = {key: chunk.get(key) for key in ("id", "created", "model")}
        self.outcome.last_chunk = self.last_chunk
        modified = False
        terminals: list[dict[str, Any]] = []
        for choice in choices:
            if isinstance(choice, dict):
                modified = self._consume_choice(choice) or modified
                if choice.get("finish_reason"):
                    terminals.append(choice)
        self.outcome.unfinished_choices = self.seen - self.finished
        for choice in sorted(
            terminals, key=lambda item: choice_index(item.get("index"))
        ):
            modified = self._terminal(choice, chunk) or modified
        return modified

    def _other_chunk(self, chunk: dict[str, Any]) -> bool:
        meta = {
            key: chunk[key]
            for key in ("id", "created", "model")
            if chunk.get(key) is not None
        }
        if meta:
            self.last_chunk = {**self.last_chunk, **meta}
            self.outcome.last_chunk = {**(self.outcome.last_chunk or {}), **meta}
        error = chunk.get("error")
        if error is None or not self._pending():
            return False
        code, message = _stream_error_info(error)
        self.error(code, message, "incomplete")
        return True

    def _pending(self) -> bool:
        return bool(self.acc.pending_choices() or self.seen - self.finished)

    def _end(self, raw: bytes | None = None) -> StreamOutcome:
        for index in sorted(list(self.texts)):
            self._flush_text(index, self.last_chunk)
        if self._pending():
            return self.error(
                "upstream_incomplete_stream",
                "upstream stream ended before finish_reason",
                "incomplete",
            )
        if raw is not None:
            self.outcome.done = True
            self.write(raw)
        return self.outcome

    def _write_chunk(self, raw: bytes, chunk: dict[str, Any], modified: bool) -> None:
        if not modified:
            self.write(raw)
            return
        choices = chunk["choices"]
        empty = all(
            isinstance(choice, dict)
            and not choice.get("delta")
            and not choice.get("finish_reason")
            for choice in choices
        )
        if choices and empty and "usage" not in chunk and "error" not in chunk:
            return
        self.write(_data_frame(chunk))

    def run(self, reader: _TimedSseReader) -> StreamOutcome:
        for raw, data in iter_sse_events(reader.readline, self.limits.max_body_bytes):
            chunk = reader.progress.note(data)
            if isinstance(chunk, dict):
                self.outcome.last_usage = (
                    positive_wire_usage(chunk.get("usage")) or self.outcome.last_usage
                )
            if data is not None and data.strip() == "[DONE]":
                return self._end(raw)
            if chunk is None:
                self.write(raw)
                continue
            choices = chunk.get("choices")
            if not isinstance(choices, list):
                if self._other_chunk(chunk):
                    return self.outcome
                self.write(raw)
                continue
            self._write_chunk(raw, chunk, self._consume_chunk(chunk, choices))
        return self._end()


def relay_sse(
    readline: Callable[[int], bytes],
    write: Callable[[bytes], None],
    *,
    tool_schemas: Optional[dict[str, Any]],
    limits: PassthroughLimits,
    **kw: Any,
) -> StreamOutcome:
    """Пробрасывает SSE; kwargs сохраняют прежние опциональные параметры шва."""
    relay = _SseRelay(write, tool_schemas, limits, kw)
    deadline = kw.get("deadline")
    if deadline is None:
        deadline = time.monotonic() + limits.total_timeout_s
    reader = _TimedSseReader(readline, relay.write, limits, deadline, kw.get("window"))
    try:
        return relay.run(reader)
    except (
        _EmptyToolCall,
        LiveParserError,
        _RepetitionLoop,
        AccumulatorOverflow,
        UpstreamBodyTooLarge,
    ) as exc:
        return _relay_error(relay, exc)
    finally:
        relay.acc.close()
        reader.close()
        relay.outcome.reader_stopped = not reader.thread.is_alive()


def _relay_error(relay: _SseRelay, error: Exception) -> StreamOutcome:
    """Сохраняет классификацию терминальных ошибок обоих протокольных швов."""
    if isinstance(error, _EmptyToolCall):
        return relay.error(
            "tool_call_parse_error",
            "Upstream emitted tool_calls with empty function name",
            "error_emitted",
        )
    if isinstance(error, LiveParserError):
        return relay.error(
            "upstream_tool_mode_violation", "upstream tool mode violation", "incomplete"
        )
    if isinstance(error, _RepetitionLoop):
        return relay.error(
            "upstream_repetition_loop",
            "upstream repetition loop detected",
            "repetition_loop",
        )
    what = (
        "tool_calls exceed"
        if isinstance(error, AccumulatorOverflow)
        else "event exceeds"
    )
    return relay.error(
        "upstream_response_too_large", f"upstream {what} the bridge limit", "overflow"
    )


def _checked_events(
    events: Iterator[tuple[bytes, str | None]],
    spec: NormalizerModeSpec,
    limits: PassthroughLimits,
) -> Iterator[tuple[bytes, str | None]]:
    if spec.mode is ToolMode.EMULATE:
        yield from events
        return
    relay = _SseRelay(lambda _: None, None, limits, {"mode_spec": spec})
    try:
        for raw, data in events:
            chunk = parse_sse_json(data)
            choices = chunk.get("choices") if chunk is not None else None
            if isinstance(choices, list):
                relay._consume_chunk(chunk, choices)
            if data is not None and data.strip() == "[DONE]":
                relay._end()
            yield raw, data
        relay._end()
    finally:
        relay.acc.close()


def _response_timed_out(error: Exception, options: Mapping[str, Any]) -> bool:
    deadline, window = options.get("deadline"), options.get("window")
    return (
        isinstance(error, socket.timeout)
        or getattr(error, "status_code", 0) == 504
        or isinstance(error.__cause__, TimeoutError)
        or (deadline is not None and time.monotonic() >= deadline)
        or (window is not None and window.expired())
    )


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


class PassthroughInitOptions(TypedDict, total=False):
    """Сохраняет прежние keyword-параметры конструктора."""

    limits: PassthroughLimits | None
    process_budget: ProcessBudget | None
    sanitize: bool | None
    is_hub_key: Callable[[str], bool] | None


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
        **kwargs: Unpack[PassthroughInitOptions],
    ) -> None:
        super().__init__(backend_id, config, catalog_source, host)
        self._initialize(**kwargs)

    def _initialize(
        self,
        *,
        limits: PassthroughLimits | None = None,
        process_budget: ProcessBudget | None = None,
        sanitize: bool | None = None,
        is_hub_key: Callable[[str], bool] | None = None,
    ) -> None:
        """Инициализирует прежние ресурсы адаптера без дополнительного пула."""
        self._is_hub_key = is_hub_key
        self._limits = limits
        initial_limits = self.limits
        self._pool: PassthroughConnectionPool = PassthroughConnectionPool(
            initial_limits.max_keepalive_connections,
            initial_limits.keepalive_expiry_s,
            select_fn=lambda r, w, x, timeout=0: select.select(r, w, x, timeout),
            monotonic_fn=lambda: time.monotonic(),
        )
        self.process_budget = process_budget or ProcessBudget(
            initial_limits.accumulator_max_process_bytes
        )
        self._sanitize = sanitize
        self._active = 0
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(self.max_concurrent)
        self._retry_bulkhead = NonstreamRetryBulkhead.from_env()
        self._retry_bulkhead_env = os.environ.get("BRIDGE_NONSTREAM_RETRY_MAX_INFLIGHT")
        self._configure_endpoint()

    def _configure_endpoint(self) -> None:
        """Проверяет loopback URL и нормализует ошибку диапазона порта."""
        base_url = self.config.get("base_url")
        if not isinstance(base_url, str) or not _LOOPBACK_V1_RE.fullmatch(base_url):
            raise ValueError("backend_base_url_invalid")
        parts = urllib.parse.urlsplit(base_url)
        try:
            port = parts.port
        except ValueError as exc:
            raise ValueError("backend_base_url_invalid") from exc
        if parts.hostname is None or port is None or not 1 <= port <= 65535:
            raise ValueError("backend_base_url_invalid")
        self._host = parts.hostname
        self._port = port
        self._base_path = parts.path.rstrip("/")

    @property
    def _upstream_key(self) -> str:
        """Единый живой credential: ref → env → literal без обхода отзыва."""
        if (override := getattr(self, "_upstream_key_override", None)) is not None:
            return override
        return resolve_credential(self.config)

    @_upstream_key.setter
    def _upstream_key(self, value: Optional[str]) -> None:
        self._upstream_key_override = value

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
        key = self._upstream_key
        # Локальная UTF-8 аутентификация не ограничена ASCII HTTP-заголовка.
        if getattr(self, "_upstream_key_override", None) is None and all(
            self.config.get(field) in (None, "")
            for field in ("api_key_ref", "api_key_env")
        ):
            literal = self.config.get("api_key")
            key = literal if isinstance(literal, str) else ""
        if not key or not token:
            return False
        return hmac.compare_digest(token.encode("utf-8"), key.encode("utf-8"))

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
        """Совместимый вход чтения ref через общий ограниченный resolver."""
        return resolve_credential({"api_key_ref": self.config.get("api_key_ref")})

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

    def _supports_stream_options(self, path: str, request: Mapping[str, Any]) -> bool:
        from core.passthrough_stream_options import supports_stream_options
        return supports_stream_options(path, getattr(self, "config", None))

    def _upstream_headers(
        self,
        raw_body: bytes = b"",
        headers: Mapping[str, str] | None = None,
        affinity_out: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Заголовки, принудительно заменяющие клиентские: из файла, затем per-request."""
        if headers is None:
            headers = {}
        extra = self._read_json_headers()
        per_request = self.config.get("per_request_headers")
        computed_affinity: str | None = None
        computed_scope: str | None = None
        if isinstance(per_request, Mapping):
            for name, template in per_request.items():
                value = str(template).replace("{uuid4}", str(uuid.uuid4()))
                if "{session_affinity}" in value:
                    if computed_affinity is None:
                        computed_affinity = session_affinity(raw_body, headers, self.id)
                        computed_scope = request_scope(raw_body, headers, self.id)
                    value = value.replace("{session_affinity}", computed_affinity)
                extra[str(name)] = value
        if computed_affinity is not None:
            scope_val = computed_scope or ""
            if affinity_out is not None:
                affinity_out["affinity_uuid"] = computed_affinity
                affinity_out["affinity_scope"] = scope_val
        return extra

    def _with_body_defaults(self, raw_body: bytes) -> bytes:
        """Удаляет управляющие поля моста и подставляет отсутствующие дефолты."""
        try:
            data = json.loads(raw_body)
        except ValueError:
            return raw_body
        if not isinstance(data, dict):
            return raw_body
        changed = _strip_body_controls(data)
        extra = self.config.get("default_body_extra")
        if isinstance(extra, Mapping):
            changed = _apply_body_defaults(data, extra) or changed
        return (
            json.dumps(data, ensure_ascii=False).encode("utf-8")
            if changed
            else raw_body
        )

    # -- raw-шов -------------------------------------------------------------------------
    def _log(self, message: str) -> None:
        logger = getattr(self.host, "_log", None)
        if callable(logger):
            logger(message)

    def _sanitize_enabled(self) -> bool:
        if self._sanitize is not None:
            return self._sanitize
        return bool(getattr(self.host, "BRIDGE_SANITIZE_TOOL_CALLS", True))

    def _runtime_options(self) -> RuntimeOptions:
        """Передаёт настройки и динамический порт расчёта дедлайнов."""
        return RuntimeOptions(
            DEFAULT_QUEUE_TIMEOUT_S,
            _SLIDING_WIN_FLAG.enabled,
            lambda lim, intr: request_deadlines(lim, intr),
        )

    def handle(self, **kwargs: Unpack[HandleRequestOptions]) -> None:
        kwargs["sink"] = passthrough_precommit.wrap_sink(
            kwargs["sink"], kwargs["request"], format_stream_error_sse, ClientGone
        )
        handle_request(self, PassthroughRequest(**kwargs), self._runtime_options())

    def _open(
        self,
        path: str,
        raw_body: bytes,
        headers: Mapping[str, str],
        **kwargs: Unpack[OpenRequestOptions],
    ) -> http.client.HTTPConnection:
        return open_request(self, path, raw_body, headers, **kwargs)

    def _fail(
        self,
        sink: ResponseSink,
        status: int,
        error_type: str,
        message: str,
        *,
        model: str = "-",
        request_id: str = "-",
    ) -> None:
        detail = (
            re.sub(r"[^A-Za-z0-9_.:@/-]+", "_", str(message or "").strip()).strip("_")[:64]
            or "-"
        )
        self._log(
            f"passthrough fail status={status} type={error_type} "
            f"model={model} request_id={request_id} detail={detail}"
        )
        headers, body = _json_error(status, error_type, message)
        sink.start(status, headers)
        sink.write(body)

    def _fail_io(
        self,
        sink: ResponseSink,
        is_timeout: bool,
        *,
        model: str = "-",
        request_id: str = "-",
    ) -> bool:
        if is_timeout:
            self._fail(
                sink,
                504,
                "upstream_timeout",
                "upstream did not respond in time",
                model=model,
                request_id=request_id,
            )
        else:
            self._fail(
                sink,
                502,
                "upstream_unavailable",
                "upstream is unavailable",
                model=model,
                request_id=request_id,
            )
        return False

    def _response_headers(
        self, resp: http.client.HTTPResponse
    ) -> list[tuple[str, str]]:
        return [(k, v) for k, v in resp.getheaders() if k.lower() not in _RESPONSE_DROP]

    def _read_presend_body(self, resp: http.client.HTTPResponse) -> bytes:
        return _read_bounded(resp, self.limits.max_body_bytes)

    def _client_gone_exc(self) -> ClientGone:
        return ClientGone()

    def _request_mode(self, request: Mapping[str, Any]) -> NormalizerModeSpec:
        mode = resolve_tool_mode(request.get("tools"), request.get("tool_choice"))
        policy = resolve_toolless_tag_policy(os.environ)
        spec = build_mode_spec(mode, policy)
        self._log(
            "passthrough "
            + format_tool_mode_log(
                request.get("tools"),
                request.get("tool_choice"),
                spec,
            )
        )
        return spec

    def _response_body(
        self,
        resp: http.client.HTTPResponse,
        options: dict[str, Any],
    ) -> tuple[bytes, bool]:
        window = options.get("window")
        reopen: Callable[[], http.client.HTTPResponse] | None = options.get("reopen")
        sse = (
            resp.status == 200
            and "text/event-stream" in (resp.getheader("Content-Type") or "").lower()
        )
        aggregate = sse and window is not None and window.internal_stream
        deadline = options.get("deadline")

        def reopen_response() -> http.client.HTTPResponse:
            nonlocal resp
            assert reopen is not None
            resp = reopen()
            return resp

        if aggregate:
            callback = reopen_response if reopen is not None else None
            body = self._aggregate_sse(
                resp,
                window,
                headers=options.get("headers"),
                reopen=callback,
                deadline=deadline,
                mode_spec=options["mode_spec"],
                client_gone_fn=options.get("client_gone_fn"),
            )
        else:
            body = _read_bounded(resp, self.limits.max_body_bytes)
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("upstream total deadline exceeded")
        return body, aggregate

    def _normalize_body(
        self,
        resp: http.client.HTTPResponse,
        result: tuple[bytes, bool],
        options: dict[str, Any],
    ) -> bytes:
        body, aggregate = result
        media = (
            "application/json"
            if aggregate
            else (resp.getheader("Content-Type") or "").lower()
        )
        encoding = (resp.getheader("Content-Encoding") or "identity").lower()
        if resp.status == 200 and "json" in media and encoding == "identity":
            return sanitize_completion_body(
                body,
                options["tool_schemas"],
                self.limits,
                options["mode_spec"],
                sanitize=options["sanitize"],
            )
        return body

    def _response_error(
        self,
        sink: ResponseSink,
        error: Exception,
        options: dict[str, Any],
        *,
        model: str = "-",
        request_id: str = "-",
    ) -> bool:
        if isinstance(error, NonstreamError):
            self._fail(
                sink, error.status, error.code, error.message,
                model=model, request_id=request_id,
            )
        elif isinstance(error, UpstreamBodyTooLarge):
            self._fail(
                sink,
                502,
                "upstream_response_too_large",
                "upstream response exceeds the bridge limit",
                model=model,
                request_id=request_id,
            )
        elif isinstance(error, LiveParserError):
            self._fail(
                sink,
                502,
                "upstream_tool_mode_violation",
                "upstream tool mode violation",
                model=model,
                request_id=request_id,
            )
        else:
            return self._fail_io(
                sink,
                _response_timed_out(error, options),
                model=model,
                request_id=request_id,
            )
        return False

    def _emit_response(
        self,
        resp: http.client.HTTPResponse,
        sink: ResponseSink,
        result: tuple[bytes, bool],
    ) -> bool:
        body, aggregate = result
        headers = self._response_headers(resp) + [("Content-Length", str(len(body)))]
        if aggregate:
            headers = [
                header for header in headers if header[0].lower() != "content-type"
            ]
            headers.append(("Content-Type", "application/json; charset=utf-8"))
        sink.start(resp.status, headers)
        sink.write(body)
        return True

    def _respond(
        self,
        resp: http.client.HTTPResponse,
        request: Mapping[str, Any],
        *context: Any,
        **kw: Any,
    ) -> bool:
        """Сохраняет позиционный контракт (sink, deadline), группируя параметры исполнения."""
        sink = context[0]
        deadline = context[1] if len(context) > 1 else kw.get("deadline")
        sanitize = self._sanitize_enabled()
        kw.update(
            deadline=deadline,
            sanitize=sanitize,
            mode_spec=self._request_mode(request),
            tool_schemas=build_tool_schemas(request.get("tools")) if sanitize else None,
            client_gone_fn=sink.client_gone,
        )
        content_type = (resp.getheader("Content-Type") or "").lower()
        aggregate = getattr(kw.get("window"), "internal_stream", False)
        if resp.status == 200 and "text/event-stream" in content_type and not aggregate:
            kw["deadline"] = kw.get("slide") or deadline
            return self._relay_stream(resp, kw["tool_schemas"], sink, sanitize, **kw)
        try:
            body, aggregate = self._response_body(resp, kw)
            body = self._normalize_body(resp, (body, aggregate), kw)
        except (
            NonstreamError,
            UpstreamBodyTooLarge,
            LiveParserError,
            PreSendTransientError,
            OSError,
            http.client.HTTPException,
        ) as exc:
            model, request_id = fail_context(
                request, kw.get("headers") or {}, self.host
            )
            return self._response_error(
                sink, exc, kw, model=model, request_id=request_id
            )
        aff = kw.get("affinity_uuid")
        scope = kw.get("affinity_scope") or ""
        if resp.status == 200 and aff and isinstance(body, (bytes, str)):
            try:
                data = json.loads(body)
            except (ValueError, TypeError, UnicodeError):
                data = None
            resp_id = _extract_response_id(data)
            if resp_id:
                register_response_affinity(resp_id, aff, scope=scope)
        return self._emit_response(resp, sink, (body, aggregate))

    def _get_retry_bulkhead(self) -> NonstreamRetryBulkhead:
        raw = os.environ.get("BRIDGE_NONSTREAM_RETRY_MAX_INFLIGHT")
        if raw != self._retry_bulkhead_env:
            self._retry_bulkhead = NonstreamRetryBulkhead.from_env()
            self._retry_bulkhead_env = raw
        return self._retry_bulkhead

    def _read_agg_once(
        self,
        resp: http.client.HTTPResponse,
        window: LivenessWindow,
        sig_box: list[int],
        mode_spec: NormalizerModeSpec = DEFAULT_EMULATE_SPEC,
        *,
        client_gone_fn: Callable[[], bool] | None = None,
    ) -> bytes:
        lim = self.limits

        def on_sig(kind: str, keys: tuple[str, ...] = ()) -> None:
            if kind == SIGNAL_S:
                sig_box[0] += 1
            window.record_signal(kind, keys)

        reader = _TimedSseReader(
            resp.readline, lambda _f: None, lim, math.inf, window, True
        )
        try:
            events = iter_sse_events(reader.readline, lim.max_body_bytes)
            events = _checked_events(events, mode_spec, lim)
            return aggregate_events(
                events,
                on_sig,
                lim.max_body_bytes,
                window.expired,
                client_gone=client_gone_fn,
            )
        finally:
            reader.close()

    def _retry_runtime(
        self,
        error: NonstreamError,
        window: LivenessWindow,
        options: dict[str, Any],
    ) -> RetryRuntime:
        reopen = options.get("reopen")
        return RetryRuntime(
            error=error,
            window=window,
            reopen=reopen if callable(reopen) else None,
            deadline=options.get("deadline"),
            poll_interval_s=self.limits.poll_interval_s,
            bulkhead=self._get_retry_bulkhead(),
            read_once=lambda retry_resp: self._read_agg_once(
                retry_resp,
                window,
                [0],
                options.get("mode_spec", DEFAULT_EMULATE_SPEC),
                client_gone_fn=options.get("client_gone_fn"),
            ),
        )

    def _aggregate_sse(
        self,
        resp: http.client.HTTPResponse,
        window: LivenessWindow,
        **kw: Any,
    ) -> bytes:
        st = getattr(window, "_state", None)
        has_s0 = getattr(st, "first_s_at", None) is not None
        win_s0 = int(getattr(window, "s_count", 0)) or (1 if has_s0 else 0)
        sig_box = [0]
        try:
            return self._read_agg_once(
                resp,
                window,
                sig_box,
                kw.get("mode_spec", DEFAULT_EMULATE_SPEC),
                client_gone_fn=kw.get("client_gone_fn"),
            )
        except NonstreamError as exc:
            if exc.status == 499:
                raise
            pol = NonstreamRetryPolicy.from_env()
            sess = str(getattr(self.capabilities, "sessions", SESSIONS_NONE))
            ok_guard = should_retry_incomplete_nonstream(
                internal_stream=bool(window.internal_stream),
                aggregate_signals=sig_box[0],
                window_signals=win_s0 + sig_box[0],
                sessions=sess,
                headers=kw.get("headers") or {},
            )
            runtime = self._retry_runtime(exc, window, kw)
            result = retry_incomplete_once(
                runtime,
                policy_enabled=pol.max_retries >= 1,
                request_eligible=ok_guard,
            )
            if result is None:
                raise
            return result

    def _trusted_tools(self, resp: http.client.HTTPResponse, sanitize: bool) -> bool:
        flag = getattr(self.host, "is_trusted_tool_streaming_enabled", None)
        return (
            sanitize
            and self.config.get("trusted_tool_sanitizer") is True
            and bool(self._upstream_key)
            and self._host == "127.0.0.1"
            and callable(flag)
            and flag() is True
            and resp.getheader("X-Bridge-Tool-Sanitized") == "1"
        )

    def _stream_io_error(
        self,
        sink: ResponseSink,
        outcome: StreamOutcome,
        options: dict[str, Any],
    ) -> bool:
        error, on_timeout = options["error"], options.get("on_timeout")
        if isinstance(error, (TimeoutError, socket.timeout)) and on_timeout is not None:
            on_timeout()
        last = outcome.last_chunk or {}
        unfinished = outcome.unfinished_choices
        if unfinished is not None and len(unfinished) == 0:
            sink.write(b"data: [DONE]\n\n")
            return False
        error_options: dict[str, Any] = {
            "message": "upstream stream failed",
            "code": "upstream_stream_error",
            "model": str(last.get("model") or getattr(self, "id", "") or ""),
            "completion_id": last.get("id"),
            "created": last.get("created"),
            "choice_indices": sorted(unfinished) if unfinished is not None else [0],
            "usage": outcome.last_usage,
        }
        chunk = format_sse_event(build_stream_error_chunk(**error_options))
        sink.write((chunk + format_sse_event("[DONE]")).encode("utf-8"))
        return False

    def _stream_success(self, outcome: StreamOutcome) -> bool:
        if outcome.incomplete or outcome.overflow:
            self._log(
                f"passthrough stream incomplete={outcome.incomplete} overflow={outcome.overflow}"
            )
        return not (
            not outcome.reader_stopped
            or outcome.incomplete
            or outcome.overflow
            or outcome.repetition_loop
            or outcome.error_emitted
        )

    def _relay_stream(
        self,
        resp: http.client.HTTPResponse,
        schemas: Optional[dict[str, Any]],
        *context: Any,
        **kw: Any,
    ) -> bool:
        """Совместимый позиционный вход: sink, sanitize, deadline, on_timeout, window."""
        sink, sanitize = context[:2]
        telemetry_handler = getattr(sink, "_handler", None)
        sink = _GuardedSink(sink, kw.get("stream_guard"))
        kw.update(zip(("deadline", "on_timeout", "window"), context[2:]))
        trusted = self._trusted_tools(resp, sanitize)
        headers = [
            (key, value)
            for key, value in self._response_headers(resp)
            if key.lower() != "content-type"
        ] + [
            ("Content-Type", "text/event-stream"),
            ("Cache-Control", "no-cache"),
            ("X-Accel-Buffering", "no"),
        ]
        outcome = StreamOutcome(committed=True)
        kw.update(tool_schemas=schemas, limits=self.limits, process=self.process_budget)
        kw.update(sanitize=sanitize, trusted_tools=trusted, state=outcome)
        try:
            sink.start(200, headers)
            outcome = relay_sse(resp.readline, sink.write, **kw)
        except (socket.timeout, OSError, http.client.HTTPException) as exc:
            return self._stream_io_error(sink, outcome, {**kw, "error": exc})
        finally:
            telemetry_usage(telemetry_handler, outcome.last_usage)
            sink.close()
        ok = self._stream_success(outcome)
        if ok:
            last = getattr(outcome, "last_chunk", None) or {}
            resp_id = _extract_response_id(last)
            aff = kw.get("affinity_uuid")
            scope = kw.get("affinity_scope") or ""
            if resp_id and aff:
                register_response_affinity(resp_id, aff, scope=scope)
        return ok
