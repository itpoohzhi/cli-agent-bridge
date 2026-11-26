"""Переиспользование сессий Claude CLI (AD-004): LRU+TTL хранилище и сборка argv.

Всё mutable-состояние живёт только в полях экземпляра `SessionStore` (никаких
module-level коллекций). Время — только `time.monotonic()` (инъекция `clock`).
Fail-closed: Zero-Canon и любой неизвестный `X-Review-Profile` -> STATELESS.
Ключ сессии — `digest` явного chat-id (`SOURCES_SESSION_ID`), не `prompt_cache_key`.
"""

from __future__ import annotations

import math
import os
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import final

from core.chat_key import SOURCES_SESSION_ID, resolve_chat_key
from core.subbridge_zero_canon import REVIEW_PROFILE_HEADER, STANDARD_PROFILE

ENV_ENABLED = "CLAUDE_P_BRIDGE_SESSION_REUSE"
ENV_MAX_ENTRIES = "CLAUDE_P_BRIDGE_SESSION_MAX_ENTRIES"
ENV_TTL_S = "CLAUDE_P_BRIDGE_SESSION_TTL_S"
NO_PERSISTENCE_FLAG = "--no-session-persistence"
SESSION_FORBIDDEN_IN_ZERO_CANON = frozenset(
    {"--resume", "-r", "-c", "--continue", "--session-id", "--append-system-prompt"}
)
_TRUE = frozenset({"1", "true", "yes", "on"})
_ALLOWED_PROFILES = frozenset({"", STANDARD_PROFILE})


class SessionMode(StrEnum):
    STATELESS = "stateless"
    CREATE = "create"
    RESUME = "resume"


def _parse_number(raw: str | None, cast: Callable[[str], float], default: float, floor: float) -> float:
    text = raw.strip() if raw else ""
    try:
        value = cast(text)
    except ValueError:
        return default
    ok = math.isfinite(value) and value >= floor
    chosen = value if ok else default
    return chosen


@dataclass(frozen=True)
class SessionConfig:
    """Конфиг переиспользования сессий (по умолчанию выключено)."""

    enabled: bool = False
    max_entries: int = 256
    ttl_s: float = 3600.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> SessionConfig:
        src = os.environ if env is None else env
        max_entries = max(1, int(_parse_number(src.get(ENV_MAX_ENTRIES), int, 256, -1e18)))
        ttl_s = _parse_number(src.get(ENV_TTL_S), float, 3600.0, 1e-9)
        flag = src.get(ENV_ENABLED, "").strip().lower() in _TRUE
        return cls(flag, max_entries, ttl_s)


@dataclass(frozen=True)
class SessionLease:
    """Результат `begin`: режим, id сессии и per-key lock (держит вызывающий)."""

    key_digest: str
    session_id: str
    mode: SessionMode
    lock: threading.Lock


@dataclass(frozen=True)
class SessionSnapshot:
    """Неизменяемый снимок записи хранилища (без сырых chat-id)."""

    key_digest: str
    session_id: str
    age_s: float


@dataclass(frozen=True)
class SessionPlan:
    """План запуска claude: режим, id сессии и необязательный system-prompt."""

    mode: SessionMode = SessionMode.STATELESS
    session_id: str = ""
    append_system_prompt: str = ""


@dataclass
class _SessionRecord:
    session_id: str
    touched: float


@final
class SessionStore:
    """Потокобезопасный LRU+TTL реестр сессий; ключ — только `chat.digest`."""

    def __init__(self, config: SessionConfig | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self.config = config if config else SessionConfig()
        self._clock = clock
        self._entries: OrderedDict[str, _SessionRecord] = OrderedDict()
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _drop(self, key_digest: str) -> None:
        _ = (self._entries.pop(key_digest, None), self._locks.pop(key_digest, None))

    def _expired_keys(self) -> list[str]:
        now = self._clock()
        return [k for k, r in self._entries.items() if now - r.touched > self.config.ttl_s]

    def begin(self, key_digest: str) -> SessionLease:
        with self._guard:
            for stale in self._expired_keys():
                self._drop(stale)
            existing = self._entries.get(key_digest)
            mode = SessionMode.RESUME if existing else SessionMode.CREATE
            record = existing if existing else _SessionRecord(str(uuid.uuid4()), 0.0)
            record.touched = self._clock()
            self._entries[key_digest] = record
            self._entries.move_to_end(key_digest)
            while len(self._entries) > self.config.max_entries:
                self._drop(next(iter(self._entries)))
            lock = self._locks.setdefault(key_digest, threading.Lock())
            return SessionLease(key_digest, record.session_id, mode, lock)

    def invalidate(self, key_digest: str, session_id: str | None = None) -> None:
        with self._guard:
            record = self._entries.get(key_digest)
            if record:
                if session_id in (None, record.session_id):
                    self._drop(key_digest)

    def evict_expired(self) -> int:
        with self._guard:
            stale = self._expired_keys()
            for key in stale:
                self._drop(key)
            return len(stale)

    def snapshot(self) -> tuple[SessionSnapshot, ...]:
        with self._guard:
            now = self._clock()
            return tuple(SessionSnapshot(k, r.session_id, now - r.touched) for k, r in self._entries.items())


def is_session_reuse_allowed_profile(headers: Mapping[str, str] | None) -> bool:
    """True только если `X-Review-Profile` отсутствует/пуст/`standard` (fail-closed)."""
    name = REVIEW_PROFILE_HEADER.lower()
    hdrs = headers if headers else {}
    values = [v for k, v in hdrs.items() if str(k).lower() == name]
    return all(v.strip().lower() in _ALLOWED_PROFILES if isinstance(v, str) else False for v in values)


def plan_session(
    store: SessionStore,
    body: Mapping[str, object] | None,
    headers: Mapping[str, str] | None,
    extra_body: Mapping[str, object] | None = None,
    *,
    append_system_prompt: str = "",
) -> tuple[SessionPlan, SessionLease | None]:
    """План сессии запроса; STATELESS при выключенном reuse, профиле или без chat-id."""
    chat = resolve_chat_key(body, headers, extra_body, sources=SOURCES_SESSION_ID)
    allowed = all((store.config.enabled, is_session_reuse_allowed_profile(headers), chat.keyed))
    if not allowed:
        return SessionPlan(), None
    lease = store.begin(chat.digest)
    return SessionPlan(lease.mode, lease.session_id, append_system_prompt), lease


def build_session_argv(plan: SessionPlan | None) -> tuple[str, ...]:
    """Флаги сессии для `claude -p`; STATELESS -> `--no-session-persistence`."""
    active = plan if plan else SessionPlan()
    flag = {SessionMode.CREATE: "--session-id", SessionMode.RESUME: "--resume"}.get(active.mode)
    extra = ("--append-system-prompt", active.append_system_prompt) if active.append_system_prompt else ()
    result = (flag, active.session_id, *extra) if flag else (NO_PERSISTENCE_FLAG,)
    return result


def assert_zero_canon_argv_safe(argv: Sequence[str], *, zero_canon: bool) -> None:
    """Pre-spawn guard: Zero-Canon argv без флагов сессии и с `--no-session-persistence`."""
    has_no_persist = bool({NO_PERSISTENCE_FLAG}.intersection(argv))
    has_forbidden = bool(SESSION_FORBIDDEN_IN_ZERO_CANON.intersection(argv))
    if zero_canon:
        if any((not has_no_persist, has_forbidden)):
            raise ValueError("zero_canon_session_flag_forbidden")
