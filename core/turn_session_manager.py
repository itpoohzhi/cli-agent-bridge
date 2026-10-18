"""Менеджер отвязанных сессий хода и кольцевой буфер событий (ADR-0005 / AD-001).

Модуль отделяет жизненный цикл выполнения хода (`ManagedTurn`) от жизненного цикла
клиентского HTTP/SSE-соединения:
- При разрыве клиентского сокета ход переходит из `RUNNING_ATTACHED` в `RUNNING_DETACHED`
  и продолжает чтение вывода дочернего CLI в фоновом потоке до терминального состояния.
- Детерминированный `turn_key` дедуплицирует только активные (нетерминальные) ходы;
  повторный запрос с тем же промптом после терминального состояния запускает новый ход
  с новым `turn_id` (поддержка Regenerate, RW-003).
- Кольцевой буфер `TurnBuffer` ограничен `MAX_TURN_TEXT_BYTES = 10 МиБ` на ход и
  `MAX_TURN_BUFFER_TOTAL_BYTES = 128 МиБ` / `MAX_BUFFERED_TURNS = 128` глобально.
- При вытеснении событий из кольцевого буфера запрос дочитки с устаревшим курсором
  (`from_seq < oldest_available_seq - 1`) порождает `GapDetectedError` для ответа
  `HTTP 410 Gone` (`code="GAP_DETECTED"`, RW-006).
- Модуль не импортирует `core.tool_emulation`, `http.server` или `adapters.*` (FU-003).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import queue
import re
import signal
import tempfile
import threading
import time
from typing import Any
import uuid

from core.backend_adapter import ToolCall, TurnResult, Usage
from core.watchdog import (
    FINISH_RESERVE_S,
    IDLE_TIMEOUT_S,
    SAFETY_CAP_S,
    WATCHDOG_INTERVAL_S,
    AdaptiveTimeoutController,
    ProcessWatchdog,
)

SNAPSHOT_SCHEMA_VERSION = "1.0"
TURN_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

KNOWN_EVENT_KINDS = frozenset(
    {"reasoning", "content", "tool_call", "error", "done", "status"}
)

MAX_TURN_TEXT_BYTES: int = 10 * 1024 * 1024
MAX_BUFFERED_TURNS: int = 128
MAX_TURN_BUFFER_TOTAL_BYTES: int = 128 * 1024 * 1024
TURN_RETENTION_S: float = 3600.0
CANCEL_SIGTERM_GRACE_S: float = 2.0

STATE_QUEUED = "QUEUED"
STATE_RUNNING_ATTACHED = "RUNNING_ATTACHED"
STATE_RUNNING_DETACHED = "RUNNING_DETACHED"
STATE_COMPLETED = "COMPLETED"
STATE_CANCELLED = "CANCELLED"
STATE_FAILED_BACKEND = "FAILED_BACKEND"
STATE_TIMED_OUT_IDLE = "TIMED_OUT_IDLE"
STATE_TIMED_OUT_CAP = "TIMED_OUT_CAP"
STATE_INTERRUPTED_DRAIN = "INTERRUPTED_DRAIN"

ACTIVE_TURN_STATES = frozenset(
    {STATE_QUEUED, STATE_RUNNING_ATTACHED, STATE_RUNNING_DETACHED}
)
TERMINAL_TURN_STATES = frozenset(
    {
        STATE_COMPLETED,
        STATE_CANCELLED,
        STATE_FAILED_BACKEND,
        STATE_TIMED_OUT_IDLE,
        STATE_TIMED_OUT_CAP,
        STATE_INTERRUPTED_DRAIN,
    }
)

_SECRET_PATTERNS = (
    re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(
        r"(?i)((?:DROID_DSH_BRIDGE_KEY|FACTORY_API_KEY|META_API_KEY|API_KEY|TOKEN|SECRET)\s*[=:]\s*)([^\s\"',;]+)"
    ),
    re.compile(r"\b(?:fk|sk)-[A-Za-z0-9_-]{10,}\b"),
)


def validate_turn_id(turn_id: Any) -> bool:
    """Проверяет идентификатор хода по строгому шаблону `^[a-zA-Z0-9_-]{1,64}$`."""
    return isinstance(turn_id, str) and bool(TURN_ID_RE.fullmatch(turn_id))


def hash_owner_token(token_or_peer: str | None) -> str:
    """Вычисляет SHA-256 хеш токена владельца или локального пира для изоляции хода."""
    raw = (token_or_peer or "anonymous").strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


hash_token = hash_owner_token


def _is_detached_enabled() -> bool:
    """Проверяет флаг включения фонового доведения ходов (`BRIDGE_DETACHED_TURNS_ENABLED` / `DSH_BRIDGE_DETACHED_ENABLED`)."""
    val = os.environ.get(
        "BRIDGE_DETACHED_TURNS_ENABLED",
        os.environ.get(
            "BRIDGE_ENABLE_DETACHED_TURNS",
            os.environ.get("DSH_BRIDGE_DETACHED_ENABLED", "true"),
        ),
    )
    return str(val).strip().lower() not in ("0", "false", "no", "off")


def _is_watchdog_enabled() -> bool:
    """Проверяет флаг включения адаптивного watchdog (`BRIDGE_ADAPTIVE_WATCHDOG_ENABLED` / `DSH_BRIDGE_WATCHDOG_ENABLED`)."""
    val = os.environ.get(
        "BRIDGE_ADAPTIVE_WATCHDOG_ENABLED",
        os.environ.get(
            "BRIDGE_ENABLE_ADAPTIVE_WATCHDOG",
            os.environ.get("DSH_BRIDGE_WATCHDOG_ENABLED", "true"),
        ),
    )
    return str(val).strip().lower() not in ("0", "false", "no", "off")


def _is_drain_enabled() -> bool:
    """Проверяет флаг включения неблокирующего drain (`BRIDGE_DRAIN_ON_SHUTDOWN` / `DSH_BRIDGE_DRAIN_ENABLED`)."""
    val = os.environ.get(
        "BRIDGE_DRAIN_ON_SHUTDOWN",
        os.environ.get(
            "BRIDGE_ENABLE_GRACEFUL_DRAIN",
            os.environ.get("DSH_BRIDGE_DRAIN_ENABLED", "true"),
        ),
    )
    return str(val).strip().lower() not in ("0", "false", "no", "off")



def verify_bearer_token(provided: str | None, expected: str | None) -> bool:
    """Константная по времени сверка Bearer-токена (`hmac.compare_digest`)."""
    if not expected:
        return True
    if not provided or not isinstance(provided, str):
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def mask_secrets(text: str, extra_secrets: tuple[str, ...] = ()) -> str:
    """Маскирует секреты и ключи авторизации перед записью снапшота на диск."""
    if not text:
        return ""
    masked = text
    for pat in _SECRET_PATTERNS:
        if pat.groups >= 2:
            masked = pat.sub(r"\1[REDACTED]", masked)
        else:
            masked = pat.sub("[REDACTED]", masked)
    for env_key in ("DROID_DSH_BRIDGE_KEY", "FACTORY_API_KEY", "META_API_KEY"):
        env_val = os.environ.get(env_key)
        if env_val and len(env_val) >= 6 and env_val in masked:
            masked = masked.replace(env_val, "[REDACTED]")
    for sec in extra_secrets:
        if sec and len(sec) >= 6 and sec in masked:
            masked = masked.replace(sec, "[REDACTED]")
    return masked


def compute_turn_key(
    cwd: str | None,
    model: str,
    session_id: str | None,
    messages: list[dict[str, Any]] | tuple[Any, ...],
    default_workspace: str = "",
) -> str:
    """Детерминированный `turn_key` по спецификации §4.1 (включая последнее сообщение)."""
    raw_cwd = (cwd or default_workspace or "").strip() or "."
    norm_cwd = os.path.normpath(raw_cwd)
    norm_model = (model or "").strip()
    norm_session = (session_id or "").strip()
    messages_canonical = json.dumps(
        list(messages) if messages is not None else [],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    messages_sha256 = hashlib.sha256(messages_canonical.encode("utf-8")).hexdigest()
    outer = json.dumps(
        [norm_cwd, norm_model, norm_session, messages_sha256],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(outer.encode("utf-8")).hexdigest()


class TurnNotFoundError(KeyError):
    """Запрошенный `turn_id` не найден в памяти и на диске (`HTTP 404`)."""


class TurnForbiddenError(PermissionError):
    """Попытка доступа к чужому ходу (`owner_token_hash` не совпадает, `HTTP 403`)."""


class InvalidTurnIdError(ValueError):
    """Некорректный формат `turn_id` (`HTTP 400`)."""


class GapDetectedError(Exception):
    """Запрошенный курсор `from_seq` вытеснен из кольцевого буфера 10 МиБ (`HTTP 410`)."""

    def __init__(
        self,
        *,
        turn_id: str,
        requested_from_seq: int,
        oldest_available_seq: int,
        last_seq: int,
        snapshot_url: str = "",
        state_dump_path: str = "",
    ) -> None:
        super().__init__(
            f"GAP_DETECTED turn_id={turn_id} requested_from_seq={requested_from_seq} "
            f"oldest_available_seq={oldest_available_seq} last_seq={last_seq}"
        )
        self.turn_id = turn_id
        self.requested_from_seq = int(requested_from_seq)
        self.oldest_available_seq = int(oldest_available_seq)
        self.last_seq = int(last_seq)
        self.snapshot_url = snapshot_url or f"/v1/turns/{turn_id}"
        self.state_dump_path = (
            state_dump_path or f"workspace/state/turns/{turn_id}.json"
        )

    def to_http_payload(self) -> dict[str, Any]:
        """Формирует JSON-ответ для `HTTP 410 Gone` по контракту §3.1 (RW-006)."""
        return {
            "error": {
                "message": (
                    "Requested sequence has been evicted from the 10 MiB ring buffer; "
                    f"fetch full state snapshot via GET /v1/turns/{self.turn_id}"
                ),
                "type": "stream_gap_error",
                "code": "GAP_DETECTED",
                "turn_id": self.turn_id,
                "requested_from_seq": self.requested_from_seq,
                "oldest_available_seq": self.oldest_available_seq,
                "last_seq": self.last_seq,
                "snapshot_url": self.snapshot_url,
                "state_dump_path": self.state_dump_path,
            }
        }


@dataclass(frozen=True)
class BufferedTurnEvent:
    """Событие хода в кольцевом буфере `TurnBuffer` с монотонным `seq`."""

    seq: int
    ts: float
    kind: str
    payload: Any
    byte_len: int

    def to_sse_frame(
        self,
        *,
        completion_id: str = "",
        created: int = 0,
        model: str = "",
    ) -> str:
        """Форматирует событие в SSE-кадр с заголовком `id: <seq>`."""
        cid = completion_id or f"chatcmpl-turn-{self.seq}"
        ts_created = created or int(self.ts)
        if self.kind in ("content", "reasoning"):
            field_name = "content" if self.kind == "content" else "reasoning_content"
            text_val = (
                self.payload
                if isinstance(self.payload, str)
                else str(self.payload or "")
            )
            data = json.dumps(
                {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": ts_created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {field_name: text_val},
                            "finish_reason": None,
                        }
                    ],
                },
                ensure_ascii=False,
            )
            return f"id: {self.seq}\ndata: {data}\n\n"
        if self.kind == "tool_call":
            call_dict = (
                self.payload
                if isinstance(self.payload, dict)
                else asdict(self.payload)
                if hasattr(self.payload, "__dataclass_fields__")
                else {"function": {"name": "unknown", "arguments": str(self.payload)}}
            )
            data = json.dumps(
                {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": ts_created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"tool_calls": [call_dict]},
                            "finish_reason": None,
                        }
                    ],
                },
                ensure_ascii=False,
            )
            return f"id: {self.seq}\ndata: {data}\n\n"
        if self.kind == "error":
            err_obj = (
                self.payload
                if isinstance(self.payload, dict)
                else {"message": str(self.payload), "type": "stream_error"}
            )
            data = json.dumps(
                {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": ts_created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                    "error": err_obj,
                },
                ensure_ascii=False,
            )
            return f"id: {self.seq}\ndata: {data}\n\n"
        if self.kind == "done":
            finish = "stop"
            usage_payload = None
            if isinstance(self.payload, dict):
                finish = str(self.payload.get("finish_reason") or "stop")
                usage_payload = self.payload.get("usage")
            chunk_obj: dict[str, Any] = {
                "id": cid,
                "object": "chat.completion.chunk",
                "created": ts_created,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
            }
            if usage_payload:
                chunk_obj["usage"] = usage_payload
            data = json.dumps(chunk_obj, ensure_ascii=False)
            return f"id: {self.seq}\ndata: {data}\n\ndata: [DONE]\n\n"
        # Расширяемый passthrough для status и неизвестных будущих типов событий (FU-002).
        raw_data = json.dumps(
            self.payload
            if isinstance(self.payload, (dict, list, str, int, float, bool))
            or self.payload is None
            else str(self.payload),
            ensure_ascii=False,
        )
        return f"event: {self.kind}\nid: {self.seq}\ndata: {raw_data}\n\n"


class StreamSubscriber:
    """Подписчик живого SSE-потока с неблокирующей очередью доставки."""

    def __init__(self, subscriber_id: str | None = None, maxsize: int = 4096) -> None:
        self.subscriber_id = subscriber_id or uuid.uuid4().hex[:12]
        self.queue: queue.Queue[BufferedTurnEvent | None] = queue.Queue(maxsize=maxsize)
        self.closed = False

    def publish(self, event: BufferedTurnEvent | None) -> bool:
        if self.closed:
            return False
        try:
            self.queue.put_nowait(event)
            return True
        except queue.Full:
            self.closed = True
            return False

    def close(self) -> None:
        self.closed = True
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass


class TurnBuffer:
    """Кольцевой буфер событий одного хода с лимитом `MAX_TURN_TEXT_BYTES` (10 МиБ)."""

    def __init__(self, max_bytes: int = MAX_TURN_TEXT_BYTES) -> None:
        self.max_bytes = max(1, int(max_bytes))
        self._lock = threading.RLock()
        self._events: deque[BufferedTurnEvent] = deque()
        self.oldest_available_seq: int = 1
        self.last_seq: int = 0
        self.total_bytes: int = 0
        self.evicted_bytes: int = 0
        self.evicted_count: int = 0
        self.sealed: bool = False

        self._reasoning_chunks: deque[str] = deque()
        self._reasoning_bytes: int = 0
        self._content_chunks: deque[str] = deque()
        self._content_bytes: int = 0
        self.tool_calls: list[dict[str, Any]] = []
        self.usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self.error: dict[str, Any] | None = None
        self._subscribers: dict[str, StreamSubscriber] = {}

    @staticmethod
    def _estimate_bytes(kind: str, payload: Any) -> int:
        if isinstance(payload, str):
            return max(1, len(payload.encode("utf-8", errors="replace")))
        try:
            encoded = json.dumps(payload, ensure_ascii=False).encode(
                "utf-8", errors="replace"
            )
            return max(1, len(encoded))
        except Exception:  # noqa: BLE001
            return max(1, len(str(payload).encode("utf-8", errors="replace")))

    def _append_bounded_text(
        self, chunks: deque[str], current_bytes: int, piece: str
    ) -> int:
        if not piece:
            return current_bytes
        piece_bytes = len(piece.encode("utf-8", errors="replace"))
        if piece_bytes > self.max_bytes:
            piece = piece.encode("utf-8", errors="replace")[-self.max_bytes :].decode(
                "utf-8", errors="ignore"
            )
            piece_bytes = len(piece.encode("utf-8", errors="replace"))
        chunks.append(piece)
        current_bytes += piece_bytes
        while current_bytes > self.max_bytes and len(chunks) > 1:
            removed = chunks.popleft()
            current_bytes -= len(removed.encode("utf-8", errors="replace"))
        return max(0, current_bytes)

    def append(self, kind: str, payload: Any) -> BufferedTurnEvent:
        """Добавляет событие в буфер, вытесняя старые записи при превышении `max_bytes`."""
        with self._lock:
            if self.sealed:
                raise RuntimeError("TurnBuffer is already sealed")
            self.last_seq += 1
            seq = self.last_seq
            byte_len = self._estimate_bytes(kind, payload)
            event = BufferedTurnEvent(
                seq=seq,
                ts=time.time(),
                kind=str(kind),
                payload=payload,
                byte_len=byte_len,
            )
            self._events.append(event)
            self.total_bytes += byte_len

            if kind == "reasoning" and isinstance(payload, str):
                self._reasoning_bytes = self._append_bounded_text(
                    self._reasoning_chunks, self._reasoning_bytes, payload
                )
            elif kind == "content" and isinstance(payload, str):
                self._content_bytes = self._append_bounded_text(
                    self._content_chunks, self._content_bytes, payload
                )
            elif kind == "tool_call":
                call_dict = (
                    dict(payload)
                    if isinstance(payload, dict)
                    else asdict(payload)
                    if hasattr(payload, "__dataclass_fields__")
                    else {"function": {"name": "unknown", "arguments": str(payload)}}
                )
                self.tool_calls.append(call_dict)
            elif kind == "error":
                self.error = (
                    dict(payload)
                    if isinstance(payload, dict)
                    else {"message": str(payload), "type": "stream_error"}
                )
            elif kind == "done" and isinstance(payload, dict):
                raw_usage = payload.get("usage")
                if isinstance(raw_usage, dict):
                    self.set_usage(raw_usage)

            # Вытеснение старых событий при превышении кольцевого лимита (RW-006).
            while self.total_bytes > self.max_bytes and self._events:
                evicted = self._events.popleft()
                self.total_bytes = max(0, self.total_bytes - evicted.byte_len)
                self.evicted_bytes += evicted.byte_len
                self.evicted_count += 1

            if self._events:
                self.oldest_available_seq = self._events[0].seq
            else:
                self.oldest_available_seq = self.last_seq + 1

            subscribers = list(self._subscribers.values())

        for sub in subscribers:
            sub.publish(event)
        return event

    def set_usage(self, usage: Usage | dict[str, Any]) -> None:
        """Обновляет счётчики токенов хода."""
        with self._lock:
            if isinstance(usage, Usage):
                in_tok = int(usage.input_tokens or 0)
                out_tok = int(usage.output_tokens or 0)
                cache_tok = usage.cache_read_tokens
            elif isinstance(usage, dict):
                in_tok = int(
                    usage.get("prompt_tokens")
                    or usage.get("input_tokens")
                    or 0
                )
                out_tok = int(
                    usage.get("completion_tokens")
                    or usage.get("output_tokens")
                    or 0
                )
                cache_tok = usage.get("cache_read_tokens")
            else:
                return
            self.usage = {
                "prompt_tokens": in_tok,
                "completion_tokens": out_tok,
                "total_tokens": in_tok + out_tok,
            }
            if cache_tok is not None:
                self.usage["cache_read_tokens"] = int(cache_tok)

    def get_reasoning_text(self) -> str:
        with self._lock:
            return "".join(self._reasoning_chunks)

    def get_content_text(self) -> str:
        with self._lock:
            return "".join(self._content_chunks)

    def seal(self) -> None:
        """Запечатывает буфер при переходе хода в терминальное состояние."""
        with self._lock:
            if self.sealed:
                return
            self.sealed = True
            subscribers = list(self._subscribers.values())
            self._subscribers.clear()
        for sub in subscribers:
            sub.close()

    def clear_ring_memory(self) -> int:
        """Освобождает кольцевой список событий в памяти после сброса снапшота на диск."""
        with self._lock:
            freed = self.total_bytes
            self._events.clear()
            self.total_bytes = 0
            return freed

    def check_gap(
        self,
        from_seq: int,
        *,
        turn_id: str = "",
        state_dump_path: str = "",
    ) -> None:
        """Проверяет, не вытеснено ли событие `from_seq + 1` из кольцевого буфера."""
        with self._lock:
            req_seq = max(0, int(from_seq))
            if self.oldest_available_seq > 1 and req_seq < self.oldest_available_seq - 1:
                raise GapDetectedError(
                    turn_id=turn_id,
                    requested_from_seq=req_seq,
                    oldest_available_seq=self.oldest_available_seq,
                    last_seq=self.last_seq,
                    snapshot_url=f"/v1/turns/{turn_id}",
                    state_dump_path=state_dump_path
                    or f"workspace/state/turns/{turn_id}.json",
                )

    def events_since(
        self,
        from_seq: int = 0,
        *,
        turn_id: str = "",
        state_dump_path: str = "",
    ) -> list[BufferedTurnEvent]:
        """Возвращает события с `seq > from_seq` или выбрасывает `GapDetectedError` (410)."""
        with self._lock:
            self.check_gap(
                from_seq, turn_id=turn_id, state_dump_path=state_dump_path
            )
            req_seq = max(0, int(from_seq))
            return [ev for ev in self._events if ev.seq > req_seq]

    get_since = events_since

    def subscribe(
        self,
        from_seq: int = 0,
        *,
        turn_id: str = "",
        state_dump_path: str = "",
    ) -> tuple[list[BufferedTurnEvent], StreamSubscriber | None]:
        """Атомарно проверяет gap, возвращает backlog `seq > from_seq` и регистрирует подписчика."""
        with self._lock:
            self.check_gap(
                from_seq, turn_id=turn_id, state_dump_path=state_dump_path
            )
            req_seq = max(0, int(from_seq))
            backlog = [ev for ev in self._events if ev.seq > req_seq]
            if self.sealed:
                return backlog, None
            sub = StreamSubscriber()
            self._subscribers[sub.subscriber_id] = sub
            return backlog, sub

    def unsubscribe(self, subscriber: StreamSubscriber | None) -> None:
        if subscriber is None:
            return
        subscriber.close()
        with self._lock:
            self._subscribers.pop(subscriber.subscriber_id, None)

    def active_subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)


@dataclass
class ManagedTurn:
    """Дескриптор управляемого хода в `TurnSessionManager`."""

    turn_id: str
    turn_key: str
    rid: str
    model: str
    backend: str
    cwd: str
    owner_token_hash: str
    stream: bool = True
    emulate_tools: bool = False
    status: str = STATE_QUEUED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_monotonic: float = field(default_factory=time.monotonic)
    pgid: int | None = None
    command_name: str = ""
    buffer: TurnBuffer = field(default_factory=TurnBuffer)
    timeout_controller: AdaptiveTimeoutController | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    done_event: threading.Event = field(default_factory=threading.Event)
    result: TurnResult | None = None
    final_dict: dict[str, Any] | None = None
    state_dump_path: str = ""
    _slot_release_fn: Callable[[], None] | None = None
    _slot_released: bool = False
    _cancel_callbacks: list[Callable[[], None]] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    @property
    def is_terminal(self) -> bool:
        with self._lock:
            return self.status in TERMINAL_TURN_STATES

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self.status in ACTIVE_TURN_STATES

    def add_cancel_callback(self, cb: Callable[[], None]) -> None:
        with self._lock:
            self._cancel_callbacks.append(cb)

    def mark_detached(self) -> None:
        """Переводит ход в состояние `RUNNING_DETACHED` при разрыве клиентского сокета."""
        with self._lock:
            if self.status == STATE_RUNNING_ATTACHED:
                self.status = STATE_RUNNING_DETACHED
                self.updated_at = time.time()

    def touch_activity(self, kind: str = "protocol") -> None:
        """Обновляет метку активности хода и сбрасывает таймер простоя."""
        if kind == "detached":
            self.mark_detached()
            return
        with self._lock:
            self.updated_at = time.time()
            ctrl = self.timeout_controller
        if ctrl is not None:
            ctrl.record_activity(kind or "protocol")

    def bind_process(
        self,
        *,
        pgid: int | None = None,
        terminate_fn: Callable[[], None] | None = None,
    ) -> None:
        """Привязывает PGID или callback прерывания к активному ходу."""
        with self._lock:
            if isinstance(pgid, int) and pgid > 0:
                self.pgid = pgid
                if self.timeout_controller is not None:
                    self.timeout_controller.register_pgid(pgid)
            if terminate_fn is not None and terminate_fn not in self._cancel_callbacks:
                self._cancel_callbacks.append(terminate_fn)

    def release_slot_once(self) -> bool:
        """Идемпотентно освобождает семафор конкурентности ровно один раз."""
        with self._lock:
            if self._slot_released:
                return False
            self._slot_released = True
            fn = self._slot_release_fn
            self._slot_release_fn = None
        if fn is not None:
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
            return True
        return False

    def to_snapshot_dict(self, *, scrub_secrets: bool = True) -> dict[str, Any]:
        """Формирует словарь состояния версии `1.0` для `GET /v1/turns/<turn_id>` и диска."""
        with self._lock:
            reasoning = self.buffer.get_reasoning_text()
            content = self.buffer.get_content_text()
            if not content and self.result is not None and self.result.text:
                content = self.result.text
            if not reasoning and self.result is not None and self.result.reasoning:
                reasoning = self.result.reasoning
            if scrub_secrets:
                reasoning = mask_secrets(reasoning)
                content = mask_secrets(content)
            err_obj = self.buffer.error
            if err_obj is not None and scrub_secrets:
                err_obj = {
                    k: mask_secrets(v) if isinstance(v, str) else v
                    for k, v in err_obj.items()
                }
            tool_calls = list(self.buffer.tool_calls)
            if not tool_calls and self.result is not None and self.result.tool_calls:
                tool_calls = [asdict(tc) for tc in self.result.tool_calls]
            return {
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
                "turn_id": self.turn_id,
                "turn_key": self.turn_key,
                "rid": self.rid,
                "model": self.model,
                "backend": self.backend,
                "status": self.status.lower(),
                "state": self.status,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "oldest_available_seq": self.buffer.oldest_available_seq,
                "last_seq": self.buffer.last_seq,
                "reasoning_content": reasoning,
                "content": content,
                "tool_calls": tool_calls,
                "usage": dict(self.buffer.usage),
                "error": err_obj,
                "owner_token_hash": self.owner_token_hash,
            }


def _atomic_write_json_0600(path: Path, payload: Any) -> None:
    """Атомарно записывает JSON-файл с правами `0600` в каталог с правами `0700`."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        parent.chmod(0o700)
    except OSError:
        pass
    raw = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(parent))
    tmp_path = Path(tmp_name)
    try:
        try:
            os.fchmod(fd, 0o600)
        except (AttributeError, OSError):
            pass
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


class TurnSessionManager:
    """Реестр и оркестратор отвязанных ходов (`ManagedTurn`) для всех адаптеров хаба."""

    def __init__(
        self,
        workspace: Path | str | Callable[[], Path] | None = None,
        *,
        state_root: Path | str | Callable[[], Path] | None = None,
        max_concurrent: int | None = None,
        max_turn_bytes: int = MAX_TURN_TEXT_BYTES,
        max_buffered_turns: int = MAX_BUFFERED_TURNS,
        max_total_buffer_bytes: int = MAX_TURN_BUFFER_TOTAL_BYTES,
        turn_retention_s: float = TURN_RETENTION_S,
        idle_timeout_s: float = IDLE_TIMEOUT_S,
        safety_cap_s: float = SAFETY_CAP_S,
        finish_reserve_s: float = FINISH_RESERVE_S,
        watchdog_interval_s: float = WATCHDOG_INTERVAL_S,
        cancel_grace_s: float = CANCEL_SIGTERM_GRACE_S,
        detached_enabled_fn: Callable[[], bool] | None = None,
        watchdog_enabled_fn: Callable[[], bool] | None = None,
        finalize_fn: Callable[[TurnResult, bool], TurnResult] | None = None,
        log_fn: Callable[[str], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        persist_children_file: bool = True,
    ) -> None:
        ws_source = workspace if workspace is not None else (state_root or ".")
        self._workspace_fn: Callable[[], Path] = (
            (lambda: Path(ws_source))
            if isinstance(ws_source, (str, Path))
            else ws_source
        )
        self._state_root_fn: Callable[[], Path] | None = (
            None
            if state_root is None
            else (
                (lambda: Path(state_root))
                if isinstance(state_root, (str, Path))
                else state_root
            )
        )
        self.max_concurrent = int(max_concurrent or 32)
        self.max_turn_bytes = int(max_turn_bytes)
        self.max_buffered_turns = int(max_buffered_turns)
        self.max_total_buffer_bytes = int(max_total_buffer_bytes)
        self.turn_retention_s = float(turn_retention_s)
        self.idle_timeout_s = float(idle_timeout_s)
        self.safety_cap_s = float(safety_cap_s)
        self.finish_reserve_s = float(finish_reserve_s)
        self.watchdog_interval_s = float(watchdog_interval_s)
        self.cancel_grace_s = float(cancel_grace_s)
        self.persist_children_file = bool(persist_children_file)
        self._detached_enabled_fn = detached_enabled_fn or _is_detached_enabled
        self._watchdog_enabled_fn = watchdog_enabled_fn or _is_watchdog_enabled
        self._finalize_fn = finalize_fn

        self._log_fn = log_fn
        self._clock = clock

        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._turns_by_id: dict[str, ManagedTurn] = {}
        self._active_by_key: dict[str, str] = {}
        self._children: dict[int, dict[str, Any]] = {}

    @property
    def workspace(self) -> Path:
        return Path(self._workspace_fn())

    @property
    def state_dir(self) -> Path:
        if self._state_root_fn is not None:
            sr = Path(self._state_root_fn())
            return sr.parent if sr.name == "turns" else sr
        ws = self.workspace
        if ws.name == "state":
            return ws
        if ws.name == "turns":
            return ws.parent
        return ws / "state"

    @property
    def turns_dir(self) -> Path:
        if self._state_root_fn is not None:
            sr = Path(self._state_root_fn())
            return sr if sr.name == "turns" else sr / "turns"
        ws = self.workspace
        if ws.name == "turns":
            return ws
        return self.state_dir / "turns"

    @property
    def children_path(self) -> Path:
        return self.state_dir / "children.json"

    def is_detached_enabled(self) -> bool:
        return bool(self._detached_enabled_fn())

    def is_watchdog_enabled(self) -> bool:
        return bool(self._watchdog_enabled_fn())

    def _log(self, message: str) -> None:
        if self._log_fn is not None:
            try:
                self._log_fn(message)
            except Exception:  # noqa: BLE001
                pass

    def ensure_state_dirs(self) -> None:
        """Создаёт каталоги `workspace/state` и `workspace/state/turns` с правами `0700`."""
        for directory in (self.state_dir, self.turns_dir):
            directory.mkdir(parents=True, exist_ok=True)
            try:
                directory.chmod(0o700)
            except OSError:
                pass

    def register_child_pgid(
        self,
        turn_id_or_pgid: str | int,
        pgid: int | None = None,
        *,
        pid: int | None = None,
        rid: str = "",
        command: str = "muse",
        backend: str = "",
        turn_id: str = "",
    ) -> None:
        """Регистрирует `pgid` дочернего процесса в `ManagedTurn` и `children.json`."""
        if isinstance(turn_id_or_pgid, int):
            actual_pgid = turn_id_or_pgid
            actual_turn_id = turn_id
        else:
            actual_turn_id = str(turn_id_or_pgid)
            actual_pgid = int(pgid or 0)
        cmd_name = backend or command or "muse"
        if not isinstance(actual_pgid, int) or actual_pgid <= 0:
            return
        with self._lock:
            turn = self._turns_by_id.get(actual_turn_id) if actual_turn_id else None
            if turn is not None:
                turn.pgid = actual_pgid
                turn.command_name = cmd_name
                if turn.timeout_controller is not None:
                    turn.timeout_controller.register_pgid(actual_pgid)
            self._children[actual_pgid] = {
                "pid": int(pid or actual_pgid),
                "pgid": int(actual_pgid),
                "turn_id": actual_turn_id,
                "rid": rid or (turn.rid if turn else ""),
                "started_at": time.time(),
                "command": cmd_name,
            }
            if self.persist_children_file:
                self._persist_children_locked()

    def unregister_child_pgid(self, pgid: int | None) -> None:
        """Удаляет `pgid` из реестра `children.json` после подтверждённой гибели группы."""
        if not isinstance(pgid, int) or pgid <= 0:
            return
        with self._lock:
            if pgid in self._children:
                self._children.pop(pgid, None)
                if self.persist_children_file:
                    self._persist_children_locked()

    def _persist_children_locked(self) -> None:
        try:
            self.ensure_state_dirs()
            payload = {
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
                "children": list(self._children.values()),
            }
            _atomic_write_json_0600(self.children_path, payload)
        except OSError:
            pass

    def persist_turn_snapshot(self, turn: ManagedTurn) -> Path | None:
        """Сохраняет снапшот хода в `workspace/state/turns/<turn_id>.json` с правами `0600`."""
        try:
            self.ensure_state_dirs()
            path = self.turns_dir / f"{turn.turn_id}.json"
            snapshot = turn.to_snapshot_dict(scrub_secrets=True)
            _atomic_write_json_0600(path, snapshot)
            turn.state_dump_path = str(path)
            return path
        except OSError as exc:
            self._log(
                f"turn_snapshot_write_failed turn_id={turn.turn_id} err={exc.__class__.__name__}"
            )
            return None

    def _enforce_memory_caps_locked(self) -> None:
        """Вытесняет старые терминальные ходы из RAM на диск при превышении лимитов."""
        now = time.time()
        expired_ids = [
            tid
            for tid, t in self._turns_by_id.items()
            if t.is_terminal and (now - t.updated_at) >= self.turn_retention_s
        ]
        for tid in expired_ids:
            turn = self._turns_by_id.pop(tid, None)
            if turn is not None:
                self.persist_turn_snapshot(turn)
                turn.buffer.clear_ring_memory()

        terminal_turns = sorted(
            (t for t in self._turns_by_id.values() if t.is_terminal),
            key=lambda item: item.updated_at,
        )
        while len(self._turns_by_id) > self.max_buffered_turns and terminal_turns:
            oldest = terminal_turns.pop(0)
            self.persist_turn_snapshot(oldest)
            oldest.buffer.clear_ring_memory()
            self._turns_by_id.pop(oldest.turn_id, None)

        total_ram = sum(t.buffer.total_bytes for t in self._turns_by_id.values())
        if total_ram > self.max_total_buffer_bytes:
            for oldest in terminal_turns:
                if total_ram <= self.max_total_buffer_bytes:
                    break
                if oldest.buffer.total_bytes > 0:
                    self.persist_turn_snapshot(oldest)
                    total_ram -= oldest.buffer.clear_ring_memory()

    def sweep_expired_snapshots(self) -> int:
        """Удаляет снапшоты на диске старше `TURN_RETENTION_S`."""
        removed = 0
        cutoff = time.time() - self.turn_retention_s
        try:
            if not self.turns_dir.exists():
                return 0
            for path in self.turns_dir.glob("*.json"):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink(missing_ok=True)
                        removed += 1
                except OSError:
                    pass
        except OSError:
            pass
        return removed

    def active_turns(self) -> list[ManagedTurn]:
        """Возвращает список всех нетерминальных ходов."""
        with self._lock:
            return [t for t in self._turns_by_id.values() if t.is_active]

    def active_count(self) -> int:
        """Количество активных (нетерминальных) ходов в менеджере."""
        with self._lock:
            return sum(1 for t in self._turns_by_id.values() if t.is_active)

    def find_active_by_key(
        self, turn_key: str, owner_token_hash: str | None = None
    ) -> ManagedTurn | None:
        """Находит активный ход по `turn_key` (терминальные ходы игнорируются, RW-003)."""
        with self._lock:
            tid = self._active_by_key.get(turn_key)
            if not tid:
                return None
            turn = self._turns_by_id.get(tid)
            if turn is None or not turn.is_active:
                self._active_by_key.pop(turn_key, None)
                return None
            if (
                owner_token_hash is not None
                and turn.owner_token_hash
                and turn.owner_token_hash != owner_token_hash
            ):
                return None
            return turn

    def get_turn(
        self,
        turn_id: str,
        *,
        owner_token_hash: str | None = None,
    ) -> ManagedTurn:
        """Возвращает `ManagedTurn` по `turn_id` с проверкой формата и владельца."""
        if not validate_turn_id(turn_id):
            raise InvalidTurnIdError(f"Invalid turn_id: {turn_id!r}")
        with self._lock:
            turn = self._turns_by_id.get(turn_id)
        if turn is None:
            raise TurnNotFoundError(turn_id)
        if (
            owner_token_hash is not None
            and turn.owner_token_hash
            and turn.owner_token_hash != owner_token_hash
        ):
            raise TurnForbiddenError(turn_id)
        return turn

    def get_turn_snapshot(
        self,
        turn_id: str,
        *,
        owner_token_hash: str | None = None,
    ) -> dict[str, Any]:
        """Возвращает снапшот хода из памяти или с диска (`workspace/state/turns/<id>.json`)."""
        if not validate_turn_id(turn_id):
            raise InvalidTurnIdError(f"Invalid turn_id: {turn_id!r}")
        with self._lock:
            turn = self._turns_by_id.get(turn_id)
        if turn is not None:
            if (
                owner_token_hash is not None
                and turn.owner_token_hash
                and turn.owner_token_hash != owner_token_hash
            ):
                raise TurnForbiddenError(turn_id)
            return turn.to_snapshot_dict(scrub_secrets=True)

        disk_path = self.turns_dir / f"{turn_id}.json"
        if not disk_path.is_file():
            raise TurnNotFoundError(turn_id)
        try:
            data = json.loads(disk_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TurnNotFoundError(turn_id) from exc
        saved_owner = data.get("owner_token_hash")
        if (
            owner_token_hash is not None
            and saved_owner
            and saved_owner != owner_token_hash
        ):
            raise TurnForbiddenError(turn_id)
        return data

    def create_or_attach_turn(
        self,
        *,
        model: str,
        backend: str,
        cwd: str,
        messages: list[dict[str, Any]] | tuple[Any, ...],
        session_id: str | None = None,
        owner_token_hash: str = "",
        rid: str = "",
        requested_turn_id: str | None = None,
        resume_turn_id: str | None = None,
        stream: bool = True,
        emulate_tools: bool = False,
        idle_timeout_s: float | None = None,
        safety_cap_s: float | None = None,
        slot_release_fn: Callable[[], None] | None = None,
    ) -> tuple[ManagedTurn, bool]:
        """Создаёт новый `ManagedTurn` или подключается к уже идущему активному ходу.

        Возвращает `(turn, is_existing_active)`.
        Терминальные ходы с тем же `turn_key` никогда не переиспользуются без явного
        `resume_turn_id`, чтобы кнопка Regenerate всегда создавала новый ход (RW-003).
        """
        if resume_turn_id is not None and resume_turn_id != "":
            if not validate_turn_id(resume_turn_id):
                raise InvalidTurnIdError(f"Invalid X-Turn-Resume-Id: {resume_turn_id!r}")
            existing = self.get_turn(
                resume_turn_id, owner_token_hash=owner_token_hash or None
            )
            with self._lock:
                if existing.status == STATE_RUNNING_DETACHED:
                    existing.status = STATE_RUNNING_ATTACHED
                    existing.updated_at = time.time()
            return existing, True

        if requested_turn_id is not None and requested_turn_id != "":
            if not validate_turn_id(requested_turn_id):
                raise InvalidTurnIdError(f"Invalid X-Turn-Id: {requested_turn_id!r}")

        turn_key = compute_turn_key(
            cwd=cwd,
            model=model,
            session_id=session_id,
            messages=messages,
            default_workspace=str(self.workspace),
        )

        with self._lock:
            if requested_turn_id and requested_turn_id in self._turns_by_id:
                existing_by_id = self._turns_by_id[requested_turn_id]
                if (
                    owner_token_hash
                    and existing_by_id.owner_token_hash
                    and existing_by_id.owner_token_hash != owner_token_hash
                ):
                    raise TurnForbiddenError(requested_turn_id)
                if existing_by_id.is_active:
                    if existing_by_id.status == STATE_RUNNING_DETACHED:
                        existing_by_id.status = STATE_RUNNING_ATTACHED
                        existing_by_id.updated_at = time.time()
                    return existing_by_id, True

            active_tid = self._active_by_key.get(turn_key)
            if active_tid:
                active_turn = self._turns_by_id.get(active_tid)
                if active_turn is not None and active_turn.is_active:
                    if (
                        active_turn.status == STATE_RUNNING_DETACHED
                        and (
                            not owner_token_hash
                            or not active_turn.owner_token_hash
                            or active_turn.owner_token_hash == owner_token_hash
                        )
                    ):
                        active_turn.status = STATE_RUNNING_ATTACHED
                        active_turn.updated_at = time.time()
                        self._log(
                            f"turn_reattached rid={rid or active_turn.rid} "
                            f"turn_id={active_turn.turn_id} turn_key={turn_key[:12]}"
                        )
                        return active_turn, True
                else:
                    self._active_by_key.pop(turn_key, None)

            turn_id = (
                requested_turn_id
                if (
                    requested_turn_id
                    and requested_turn_id not in self._turns_by_id
                )
                else f"turn_{uuid.uuid4().hex[:16]}"
            )
            eff_rid = rid or f"r-{uuid.uuid4().hex[:8]}"
            eff_idle = (
                float(idle_timeout_s)
                if idle_timeout_s is not None
                else self.idle_timeout_s
            )
            eff_cap = (
                float(safety_cap_s)
                if safety_cap_s is not None
                else self.safety_cap_s
            )
            controller = AdaptiveTimeoutController(
                idle_timeout_s=eff_idle,
                safety_cap_s=eff_cap,
                finish_reserve_s=self.finish_reserve_s,
                watchdog_enabled=self.is_watchdog_enabled(),
                clock=self._clock,
                rid=eff_rid,
                turn_id=turn_id,
                log_fn=self._log_fn,
            )
            dump_path = str(self.turns_dir / f"{turn_id}.json")
            turn = ManagedTurn(
                turn_id=turn_id,
                turn_key=turn_key,
                rid=eff_rid,
                model=model,
                backend=backend,
                cwd=cwd,
                owner_token_hash=owner_token_hash,
                stream=stream,
                emulate_tools=emulate_tools,
                status=STATE_RUNNING_ATTACHED,
                buffer=TurnBuffer(max_bytes=self.max_turn_bytes),
                timeout_controller=controller,
                state_dump_path=dump_path,
                _slot_release_fn=slot_release_fn,
            )
            self._turns_by_id[turn_id] = turn
            self._active_by_key[turn_key] = turn_id
            self._enforce_memory_caps_locked()
            return turn, False

    def finalize_abandoned_turn(self, turn: ManagedTurn | None) -> None:
        """Гарантирует освобождение ресурсов хода при выходе потока-исполнителя до финализации."""
        if turn is None:
            return
        turn.release_slot_once()
        with self._lock:
            if turn.is_terminal:
                return
            turn.status = STATE_CANCELLED
            turn.updated_at = time.time()
            if self._active_by_key.get(turn.turn_key) == turn.turn_id:
                self._active_by_key.pop(turn.turn_key, None)
            if not turn.buffer.sealed:
                turn.buffer.seal()
            if turn.timeout_controller is not None:
                turn.timeout_controller.close()
            turn.done_event.set()
            self._cond.notify_all()

    def mark_detached(self, turn_id: str) -> None:
        """Переводит активный ход в `RUNNING_DETACHED` при разрыве HTTP-соединения."""
        with self._lock:
            turn = self._turns_by_id.get(turn_id)
            if turn is not None and turn.status == STATE_RUNNING_ATTACHED:
                turn.status = STATE_RUNNING_DETACHED
                turn.updated_at = time.time()
                self._log(
                    f"turn_detached rid={turn.rid} turn_id={turn.turn_id} "
                    f"last_seq={turn.buffer.last_seq}"
                )

    def _terminate_pgid(self, pgid: int | None, grace_s: float) -> None:
        if not isinstance(pgid, int) or pgid <= 0:
            return
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            self.unregister_child_pgid(pgid)
            return
        deadline = time.monotonic() + max(0.05, grace_s)
        while time.monotonic() < deadline:
            if not ProcessWatchdog.is_group_alive(pgid):
                self.unregister_child_pgid(pgid)
                return
            time.sleep(0.05)
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        self.unregister_child_pgid(pgid)

    def cancel_turn(
        self,
        turn_id: str,
        *,
        owner_token_hash: str | None = None,
        reason: str = "client_cancelled",
    ) -> ManagedTurn:
        """Явно отменяет ход (`SIGTERM -> 2s -> SIGKILL`), немедленно освобождая слот (RW-001)."""
        turn = self.get_turn(turn_id, owner_token_hash=owner_token_hash)
        with self._lock:
            if turn.status == STATE_CANCELLED:
                return turn
            if turn.is_terminal:
                return turn
            turn.status = STATE_CANCELLED
            turn.updated_at = time.time()
            turn.cancel_event.set()
            if self._active_by_key.get(turn.turn_key) == turn.turn_id:
                self._active_by_key.pop(turn.turn_key, None)
            pgid = turn.pgid
            callbacks = list(turn._cancel_callbacks)

        # Немедленно возвращаем слот MAX_CONCURRENT до ожидания завершения потомка.
        turn.release_slot_once()

        for cb in callbacks:
            try:
                cb()
            except Exception:  # noqa: BLE001
                pass

        if pgid is not None:
            self._terminate_pgid(pgid, self.cancel_grace_s)

        with self._lock:
            if not turn.buffer.sealed:
                turn.buffer.append(
                    "error",
                    {
                        "message": f"Turn cancelled ({reason})",
                        "type": "cancelled",
                        "code": "turn_cancelled",
                    },
                )
                turn.buffer.seal()
            if turn.timeout_controller is not None:
                turn.timeout_controller.close()
            turn.done_event.set()
            self.persist_turn_snapshot(turn)
            self._cond.notify_all()
        self._log(f"turn_cancelled rid={turn.rid} turn_id={turn.turn_id} reason={reason}")
        return turn

    def interrupt_for_drain(
        self, turn: ManagedTurn, message: str = "bridge restart drain timeout exceeded"
    ) -> None:
        """Завершает ход при истечении `DRAIN_TIMEOUT_S` со сбросом reasoning и error-чанком."""
        with self._lock:
            if turn.is_terminal:
                return
            turn.status = STATE_INTERRUPTED_DRAIN
            turn.updated_at = time.time()
            turn.cancel_event.set()
            if self._active_by_key.get(turn.turn_key) == turn.turn_id:
                self._active_by_key.pop(turn.turn_key, None)
            pgid = turn.pgid
            callbacks = list(turn._cancel_callbacks)

        turn.release_slot_once()
        for cb in callbacks:
            try:
                cb()
            except Exception:  # noqa: BLE001
                pass
        if pgid is not None:
            self._terminate_pgid(pgid, self.cancel_grace_s)

        with self._lock:
            if not turn.buffer.sealed:
                turn.buffer.append(
                    "error",
                    {
                        "message": message,
                        "type": "overloaded",
                        "code": "drain_timeout",
                    },
                )
                turn.buffer.seal()
            if turn.timeout_controller is not None:
                turn.timeout_controller.close()
            turn.done_event.set()
            self.persist_turn_snapshot(turn)
            self._cond.notify_all()

    def complete_turn_from_result(
        self,
        turn: ManagedTurn,
        raw_result: TurnResult,
        *,
        backend_kind: str = "",
    ) -> dict[str, Any]:
        """Финализирует `ManagedTurn` по `TurnResult` от `BackendAdapter.execute_turn`."""
        final_res = (
            self._finalize_fn(raw_result, turn.emulate_tools)
            if self._finalize_fn is not None
            else raw_result
        )
        turn.release_slot_once()

        with self._lock:
            if turn.status in (STATE_CANCELLED, STATE_INTERRUPTED_DRAIN):
                if turn.final_dict is not None:
                    return turn.final_dict
                return {
                    "state": "client_gone",
                    "rc": 1,
                    "text": turn.buffer.get_content_text(),
                    "err": "cancelled",
                    "usage": dict(turn.buffer.usage),
                    "result": {},
                    "tool_calls": list(turn.buffer.tool_calls),
                    "events": [],
                    "backend_kind": backend_kind or turn.backend,
                    "turn_id": turn.turn_id,
                }

            turn.result = final_res
            turn.buffer.set_usage(final_res.usage)

            # Если адаптер не стримил события живьём, докладываем их в TurnBuffer.
            had_content = bool(turn.buffer.get_content_text())
            had_reasoning = bool(turn.buffer.get_reasoning_text())
            had_tool_calls = bool(turn.buffer.tool_calls)
            if not turn.buffer.sealed:
                for ev in final_res.events or ():
                    if ev.kind == "reasoning" and isinstance(ev.value, str):
                        if not had_reasoning:
                            turn.buffer.append("reasoning", ev.value)
                    elif ev.kind == "content" and isinstance(ev.value, str):
                        if not had_content:
                            turn.buffer.append("content", ev.value)
                    elif ev.kind == "tool_call" and not had_tool_calls:
                        call_val = (
                            asdict(ev.value)
                            if isinstance(ev.value, ToolCall)
                            else ev.value
                        )
                        turn.buffer.append("tool_call", call_val)
                if not final_res.events:
                    if final_res.reasoning and not had_reasoning:
                        turn.buffer.append("reasoning", final_res.reasoning)
                    if final_res.text and not had_content:
                        turn.buffer.append("content", final_res.text)
                    if not had_tool_calls:
                        for tc in final_res.tool_calls or ():
                            turn.buffer.append("tool_call", asdict(tc))

            res_state = str(final_res.state or "done")
            term_reason = (
                turn.timeout_controller.terminated_reason
                if turn.timeout_controller is not None
                else ""
            )
            if term_reason == "idle_timeout" or res_state == "idle_timeout":
                turn.status = STATE_TIMED_OUT_IDLE
            elif term_reason == "absolute_cap" or res_state in (
                "timeout",
                "safety_cap",
            ):
                turn.status = STATE_TIMED_OUT_CAP
            elif res_state == "done" and int(final_res.rc or 0) == 0:
                turn.status = STATE_COMPLETED
            elif res_state == "client_gone":
                turn.status = STATE_CANCELLED
            else:
                turn.status = STATE_FAILED_BACKEND

            if not turn.buffer.sealed:
                if turn.status == STATE_COMPLETED:
                    finish_reason = (
                        "tool_calls" if final_res.tool_calls else "stop"
                    )
                    turn.buffer.append(
                        "done",
                        {
                            "finish_reason": finish_reason,
                            "usage": dict(turn.buffer.usage),
                        },
                    )
                else:
                    turn.buffer.append(
                        "error",
                        {
                            "message": str(final_res.err or res_state),
                            "type": (
                                "timeout_error"
                                if turn.status
                                in (STATE_TIMED_OUT_IDLE, STATE_TIMED_OUT_CAP)
                                else "proxy_error"
                            ),
                            "code": turn.status.lower(),
                        },
                    )
                turn.buffer.seal()

            turn.updated_at = time.time()
            if self._active_by_key.get(turn.turn_key) == turn.turn_id:
                self._active_by_key.pop(turn.turn_key, None)
            if turn.pgid is not None:
                self.unregister_child_pgid(turn.pgid)
            if turn.timeout_controller is not None:
                turn.timeout_controller.close()

            out = {
                "state": (
                    "timeout"
                    if turn.status in (STATE_TIMED_OUT_IDLE, STATE_TIMED_OUT_CAP)
                    else final_res.state
                ),
                "rc": final_res.rc,
                "text": final_res.text,
                "err": final_res.err,
                "usage": asdict(final_res.usage),
                "result": {},
                "tool_calls": [asdict(call) for call in final_res.tool_calls],
                "events": [
                    (
                        event.kind,
                        asdict(event.value)
                        if not isinstance(event.value, str)
                        else event.value,
                    )
                    for event in final_res.events or ()
                ],
                "backend_kind": backend_kind or turn.backend,
                "turn_id": turn.turn_id,
                "turn_status": turn.status,
            }
            turn.final_dict = out
            turn.done_event.set()
            self.persist_turn_snapshot(turn)
            self._enforce_memory_caps_locked()
            self._cond.notify_all()
            return out

    def spawn_detached_execution(
        self,
        turn: ManagedTurn,
        runner_fn: Callable[[ManagedTurn], TurnResult],
        *,
        backend_kind: str = "",
    ) -> threading.Thread:
        """Запускает выполнение хода в отдельном daemon-потоке, отвязанном от HTTP-хендлера."""

        def _worker() -> None:
            watchdog_stop = threading.Event()

            def _watchdog_loop() -> None:
                while not watchdog_stop.wait(self.watchdog_interval_s):
                    if turn.is_terminal or turn.cancel_event.is_set():
                        return
                    ctrl = turn.timeout_controller
                    if ctrl is None:
                        continue
                    should_stop, reason, _metrics = ctrl.check(turn.pgid)
                    if should_stop and reason in ("idle_timeout", "absolute_cap"):
                        self._log(
                            f"watchdog_triggered rid={turn.rid} turn_id={turn.turn_id} "
                            f"reason={reason} pgid={turn.pgid}"
                        )
                        turn.cancel_event.set()
                        if turn.pgid is not None:
                            self._terminate_pgid(turn.pgid, self.cancel_grace_s)
                        return

            wd_thread: threading.Thread | None = None
            if self.is_watchdog_enabled() and turn.timeout_controller is not None:
                wd_thread = threading.Thread(
                    target=_watchdog_loop,
                    name=f"turn-wd-{turn.turn_id}",
                    daemon=True,
                )
                wd_thread.start()

            try:
                raw_res = runner_fn(turn)
                if (
                    turn.timeout_controller is not None
                    and turn.timeout_controller.terminated_reason
                    in ("idle_timeout", "absolute_cap")
                ):
                    reason = turn.timeout_controller.terminated_reason
                    raw_res = TurnResult(
                        state=(
                            "idle_timeout"
                            if reason == "idle_timeout"
                            else "timeout"
                        ),
                        rc=124,
                        text=raw_res.text,
                        reasoning=raw_res.reasoning,
                        usage=raw_res.usage,
                        err=f"Turn terminated by watchdog: {reason}",
                        events=raw_res.events,
                        tool_calls=raw_res.tool_calls,
                    )
                self.complete_turn_from_result(
                    turn, raw_res, backend_kind=backend_kind
                )
            except Exception as exc:  # noqa: BLE001
                err_res = TurnResult(
                    state="backend_error",
                    rc=1,
                    err=f"{exc.__class__.__name__}: {exc}",
                )
                self.complete_turn_from_result(
                    turn, err_res, backend_kind=backend_kind
                )
            finally:
                watchdog_stop.set()

        worker = threading.Thread(
            target=_worker,
            name=f"turn-exec-{turn.turn_id}",
            daemon=True,
        )
        worker.start()
        return worker

    def wait_for_active_turns(self, timeout: float) -> list[ManagedTurn]:
        """Ожидает завершения всех активных ходов до `timeout` секунд.

        Возвращает список ходов, оставшихся активными после истечения `timeout`.
        """
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._cond:
            while True:
                remaining_turns = [
                    t for t in self._turns_by_id.values() if t.is_active
                ]
                if not remaining_turns:
                    return []
                wait_s = deadline - time.monotonic()
                if wait_s <= 0:
                    return remaining_turns
                self._cond.wait(timeout=min(wait_s, 0.25))

    def iter_sse_stream(
        self,
        turn: ManagedTurn,
        *,
        from_seq: int = 0,
        keepalive_interval_s: float = 10.0,
        client_gone_fn: Callable[[], bool] | None = None,
    ) -> Iterator[str]:
        """Генерирует SSE-поток событий хода (`id: <seq>\\ndata: ...\\n\\n`) с поддержкой дочитки."""
        backlog, subscriber = turn.buffer.subscribe(
            from_seq=from_seq,
            turn_id=turn.turn_id,
            state_dump_path=turn.state_dump_path,
        )
        completion_id = f"chatcmpl-turn-{turn.turn_id}"
        created = int(turn.created_at)
        try:
            for ev in backlog:
                yield ev.to_sse_frame(
                    completion_id=completion_id,
                    created=created,
                    model=turn.model,
                )
            if subscriber is None:
                return
            while True:
                if client_gone_fn is not None and client_gone_fn():
                    self.mark_detached(turn.turn_id)
                    return
                try:
                    ev = subscriber.queue.get(
                        timeout=max(0.05, float(keepalive_interval_s))
                    )
                except queue.Empty:
                    if client_gone_fn is not None and client_gone_fn():
                        self.mark_detached(turn.turn_id)
                        return
                    if turn.is_terminal:
                        return
                    yield ": keepalive\n\n"
                    continue
                if ev is None:
                    return
                yield ev.to_sse_frame(
                    completion_id=completion_id,
                    created=created,
                    model=turn.model,
                )
        finally:
            turn.buffer.unsubscribe(subscriber)

    def kill_all_active(self) -> None:
        """Завершает все активные ходы при истечении drain или аварийной остановке."""
        with self._cond:
            active = [t for t in self._turns_by_id.values() if t.is_active]
        for turn in active:
            try:
                self.interrupt_for_drain(turn)
            except Exception:  # noqa: BLE001
                pass

    def reset(self) -> None:
        """Сбрасывает состояние менеджера (для изоляции тестов)."""
        with self._cond:
            active = [t for t in self._turns_by_id.values() if t.is_active]
        for turn in active:
            try:
                self.cancel_turn(turn.turn_id, reason="reset")
            except Exception:  # noqa: BLE001
                pass
        with self._cond:
            self._turns_by_id.clear()
            self._active_by_key.clear()
            self._children.clear()
            self._cond.notify_all()

    reset_state = reset

