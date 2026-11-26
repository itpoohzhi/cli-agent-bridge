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
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, final

from core.chat_key import SOURCES_SESSION_ID, resolve_chat_key
from core.subbridge_zero_canon import REVIEW_PROFILE_HEADER, STANDARD_PROFILE

ENV_ENABLED: Final[str] = "CLAUDE_P_BRIDGE_SESSION_REUSE"
ENV_MAX_ENTRIES: Final[str] = "CLAUDE_P_BRIDGE_SESSION_MAX_ENTRIES"
ENV_TTL_S: Final[str] = "CLAUDE_P_BRIDGE_SESSION_TTL_S"
DEFAULT_MAX_ENTRIES: Final[int] = 256
DEFAULT_TTL_S: Final[float] = 3600.0
NO_PERSISTENCE_FLAG: Final[str] = "--no-session-persistence"
_FORBIDDEN_LONG_FLAGS: Final[frozenset[str]] = frozenset(
    {"--resume", "--continue", "--session-id", "--append-system-prompt", "--fork-session"}
)
_FORBIDDEN_SHORT_FLAGS: Final[frozenset[str]] = frozenset({"-r", "-c"})
SESSION_FORBIDDEN_IN_ZERO_CANON: Final[frozenset[str]] = _FORBIDDEN_LONG_FLAGS | _FORBIDDEN_SHORT_FLAGS
_TRUE: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_ALLOWED_PROFILES: Final[frozenset[str]] = frozenset({"", STANDARD_PROFILE})


class SessionMode(StrEnum):
    STATELESS = "stateless"
    CREATE = "create"
    RESUME = "resume"


def _parse_number(raw: str | None, cast: Callable[[str], float], default: float, floor: float) -> float:
    text = raw.strip() if raw else ""
    try:
        value = cast(text)
        ok = all((math.isfinite(value), value >= floor))
    except (ValueError, OverflowError):
        return default
    chosen = value if ok else default
    return chosen


@dataclass(frozen=True)
class SessionConfig:
    """Конфиг переиспользования сессий (по умолчанию выключено)."""

    enabled: bool = False
    max_entries: int = DEFAULT_MAX_ENTRIES
    ttl_s: float = DEFAULT_TTL_S

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> SessionConfig:
        src = os.environ if env is None else env
        max_entries = max(1, int(_parse_number(src.get(ENV_MAX_ENTRIES), int, DEFAULT_MAX_ENTRIES, -1e18)))
        ttl_s = _parse_number(src.get(ENV_TTL_S), float, DEFAULT_TTL_S, 1e-9)
        flag = bool(_TRUE.intersection({src.get(ENV_ENABLED, "").strip().lower()}))
        return cls(flag, max_entries, ttl_s)


@dataclass(frozen=True)
class SessionLease:
    """Активная сериализованная аренда сессии внутри `with store.lease(...)`."""

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


@dataclass
class _KeyGate:
    lock: threading.Lock
    refs: int = 0


@final
class SessionStore:
    """Потокобезопасный LRU+TTL реестр сессий с refcounted per-key gate."""

    def __init__(self, config: SessionConfig | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self.config = config if config else SessionConfig()
        self._clock = clock
        self._entries: OrderedDict[str, _SessionRecord] = OrderedDict()
        self._gates: dict[str, _KeyGate] = {}
        self._guard = threading.Lock()

    def _maybe_gc_gate(self, key_digest: str) -> None:
        gate = self._gates.get(key_digest)
        if all((gate, not getattr(gate, "refs", 1), not self._entries.get(key_digest))):
            _ = self._gates.pop(key_digest, None)

    def _drop_entry(self, key_digest: str) -> None:
        _ = self._entries.pop(key_digest, None)
        self._maybe_gc_gate(key_digest)

    def _evict_expired_head(self, now: float) -> int:
        evicted = 0
        while self._entries:
            oldest_key, rec = next(iter(self._entries.items()))
            if now - rec.touched <= self.config.ttl_s:
                break
            if getattr(self._gates.get(oldest_key), "refs", 0):
                rec.touched = now
                self._entries.move_to_end(oldest_key)
                continue
            self._drop_entry(oldest_key)
            evicted += 1
        return evicted

    def _open_locked(self, key_digest: str, lock: threading.Lock) -> SessionLease:
        with self._guard:
            now = self._clock()
            _ = self._evict_expired_head(now)
            existing = self._entries.get(key_digest)
            mode = SessionMode.RESUME if existing else SessionMode.CREATE
            record = existing if existing else _SessionRecord(str(uuid.uuid4()), now)
            record.touched = now
            self._entries[key_digest] = record
            self._entries.move_to_end(key_digest)
            while len(self._entries) > self.config.max_entries:
                self._drop_entry(next(iter(self._entries)))
            return SessionLease(key_digest, record.session_id, mode, lock)

    def _acquire_gate(self, key_digest: str) -> _KeyGate:
        with self._guard:
            gate = self._gates.setdefault(key_digest, _KeyGate(threading.Lock()))
            gate.refs += 1
            return gate

    def _release_gate(self, key_digest: str, gate: _KeyGate) -> None:
        with self._guard:
            rec = self._entries.get(key_digest)
            if rec:
                rec.touched = self._clock()
                self._entries.move_to_end(key_digest)
            gate.refs -= 1
            self._maybe_gc_gate(key_digest)

    @contextmanager
    def lease(self, key_digest: str) -> Generator[SessionLease, None, None]:
        """Сериализует CREATE/RESUME per-key lock'ом и защищает gate refcount'ом."""
        gate = self._acquire_gate(key_digest)
        _ = gate.lock.acquire()
        try:
            yield self._open_locked(key_digest, gate.lock)
        finally:
            try:
                self._release_gate(key_digest, gate)
            finally:
                gate.lock.release()

    def invalidate(self, key_digest: str, session_id: str | None = None) -> None:
        with self._guard:
            record = self._entries.get(key_digest)
            if all((record, session_id in (None, getattr(record, "session_id", None)))):
                self._drop_entry(key_digest)

    def evict_expired(self) -> int:
        with self._guard:
            return self._evict_expired_head(self._clock())

    def snapshot(self) -> tuple[SessionSnapshot, ...]:
        with self._guard:
            now = self._clock()
            return tuple(SessionSnapshot(k, r.session_id, now - r.touched) for k, r in self._entries.items())


def is_session_reuse_allowed_profile(headers: Mapping[str, str] | None) -> bool:
    """True только если `X-Review-Profile` отсутствует/пуст/`standard` (fail-closed)."""
    name = REVIEW_PROFILE_HEADER.lower()
    hdrs: Mapping[str, str] = headers if headers else {}
    values = [v for k, v in hdrs.items() if str(k).lower() == name]
    return all(_ALLOWED_PROFILES.intersection({v.strip().lower()}) if isinstance(v, str) else False for v in values)


@contextmanager
def plan_session(
    store: SessionStore,
    body: Mapping[str, object] | None,
    headers: Mapping[str, str] | None,
    extra_body: Mapping[str, object] | None = None,
    *,
    append_system_prompt: str = "",
) -> Generator[tuple[SessionPlan, SessionLease | None], None, None]:
    """Сериализованный план сессии; STATELESS при reuse=off, профиле или без chat-id."""
    chat = resolve_chat_key(body, headers, extra_body, sources=SOURCES_SESSION_ID)
    allowed = all((store.config.enabled, is_session_reuse_allowed_profile(headers), chat.keyed))
    if not allowed:
        yield SessionPlan(), None
    else:
        with store.lease(chat.digest) as active:
            yield SessionPlan(active.mode, active.session_id, append_system_prompt), active


def build_session_argv(plan: SessionPlan | None) -> tuple[str, ...]:
    """Флаги сессии для `claude -p`; STATELESS -> `--no-session-persistence`."""
    active = plan if plan else SessionPlan()
    flag = {SessionMode.CREATE: "--session-id", SessionMode.RESUME: "--resume"}.get(active.mode)
    extra = ("--append-system-prompt", active.append_system_prompt) if active.append_system_prompt else ()
    result = (flag, active.session_id, *extra) if flag else (NO_PERSISTENCE_FLAG,)
    return result


def _is_forbidden_session_token(token: str) -> bool:
    head = token.split("=", 1)[0]
    is_long_abbrev = all((head.startswith("--"), len(head) >= 4, any(f.startswith(head) for f in _FORBIDDEN_LONG_FLAGS)))
    is_short_bundle = all((head.startswith("-"), not head.startswith("--"), len(head) > 1, bool({"r", "c"}.intersection({head[1:2]}))))
    return any((bool(SESSION_FORBIDDEN_IN_ZERO_CANON.intersection({head})), is_long_abbrev, is_short_bundle))


def assert_zero_canon_argv_safe(argv: Sequence[str], *, zero_canon: bool) -> None:
    """Pre-spawn guard: Zero-Canon argv без флагов сессии (вкл. =value/префиксы) и с `--no-session-persistence`."""
    bad = any((not {NO_PERSISTENCE_FLAG}.intersection(argv), any(map(_is_forbidden_session_token, argv))))
    if all((zero_canon, bad)):
        raise ValueError("zero_canon_session_flag_forbidden")
