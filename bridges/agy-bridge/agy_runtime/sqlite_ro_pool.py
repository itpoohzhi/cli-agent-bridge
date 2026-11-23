"""Per-db RO-пул SQLite (AD-002): thread-local `mode=ro&immutable=0`, per-db lock только на открытие, ограниченный retry с jitter; состояние — только у класса (M-MOD-I4)."""

from __future__ import annotations

import math
import random
import sqlite3
import threading
import time
import weakref
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeVar, cast, final

_Num = TypeVar("_Num", int, float)
_T = TypeVar("_T")
_ConnMap = dict[str, sqlite3.Connection]


class _LockBox:
    def __init__(self) -> None:
        self.lock: threading.Lock = threading.Lock()


class _ThreadState:
    def __init__(self) -> None:
        self.conns: _ConnMap = {}
        self.locks: dict[str, _LockBox] = {}


def _close_quietly(conn: sqlite3.Connection) -> None:
    try:
        conn.close()
    except sqlite3.Error:
        pass


def _cleanup_thread(
    guard: threading.Lock,
    all_conns: set[sqlite3.Connection],
    conns: _ConnMap,
    locks: dict[str, _LockBox],
) -> None:
    items = list(conns.values())
    conns.clear()
    locks.clear()
    with guard:
        all_conns.difference_update(items)
    for conn in items:
        _close_quietly(conn)


FLAG_SQLITE_RO_POOL: Final[str] = "AGY_SQLITE_RO_POOL_ENABLED"
_TRUE: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on", "y", "t"})
_FALSE: Final[frozenset[str]] = frozenset({"0", "false", "no", "off", "n", "f", ""})


@dataclass(frozen=True)
class SqliteRoPoolConfig:
    """Иммутабельная конфигурация RO-пула; невалидные значения — fail-closed."""

    enabled: bool = False
    busy_timeout_ms: int = 500
    open_timeout_s: float = 0.5
    max_retries: int = 3
    base_backoff_s: float = 0.01
    max_backoff_s: float = 0.1
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Fail-closed: конечность и диапазоны всех эксплуатационных окон."""
        if min(self.busy_timeout_ms, self.max_retries) < 0:
            raise ValueError("busy_timeout_ms/max_retries must be >= 0")
        for name in (
            "open_timeout_s",
            "base_backoff_s",
            "max_backoff_s",
            "jitter_ratio",
        ):
            value = cast("float", getattr(self, name))
            bad = not math.isfinite(value) or value < 0.0
            if (
                bad
                or (name == "open_timeout_s" and value == 0.0)
                or (name == "jitter_ratio" and value > 1.0)
            ):
                raise ValueError(f"{name} out of range, got {value!r}")


def _parse_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None:
        return default
    norm = raw.strip().lower()
    if norm in _TRUE or norm in _FALSE:
        return norm in _TRUE
    raise ValueError(f"{key} must be a boolean, got {raw!r}")


def _parse_num(
    env: Mapping[str, str], key: str, conv: Callable[[str], _Num], default: _Num
) -> _Num:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return conv(raw.strip())
    except ValueError:
        raise ValueError(f"{key} must be a number, got {raw!r}") from None


def load_sqlite_ro_pool_config(env: Mapping[str, str]) -> SqliteRoPoolConfig:
    d, p = SqliteRoPoolConfig(), _parse_num
    return SqliteRoPoolConfig(
        enabled=_parse_bool(env, FLAG_SQLITE_RO_POOL, d.enabled),
        busy_timeout_ms=p(env, "AGY_SQLITE_BUSY_TIMEOUT_MS", int, d.busy_timeout_ms),
        open_timeout_s=p(env, "AGY_SQLITE_OPEN_TIMEOUT_S", float, d.open_timeout_s),
        max_retries=p(env, "AGY_SQLITE_MAX_RETRIES", int, d.max_retries),
        base_backoff_s=p(env, "AGY_SQLITE_BASE_BACKOFF_S", float, d.base_backoff_s),
        max_backoff_s=p(env, "AGY_SQLITE_MAX_BACKOFF_S", float, d.max_backoff_s),
        jitter_ratio=p(env, "AGY_SQLITE_JITTER_RATIO", float, d.jitter_ratio),
    )


def _ro_uri(path: Path) -> str:
    text = str(path).replace("%", "%25").replace("?", "%3f").replace("#", "%23")
    return f"file:{text}?mode=ro&immutable=0"


def _is_retryable(exc: sqlite3.OperationalError) -> bool:
    return any(m in str(exc).lower() for m in ("locked", "busy"))


@final
class SqliteRoPool:
    def __init__(
        self,
        config: SqliteRoPoolConfig,
        *,
        sleep_fn: Callable[[float], None] | None = None,
        rng: random.Random | Callable[[], float] | None = None,
    ) -> None:
        config.validate()
        self._config = config
        self._sleep: Callable[[float], None] = sleep_fn or time.sleep
        self._rng: random.Random | Callable[[], float] = rng or random.Random()
        self._guard = threading.Lock()
        self._locks: weakref.WeakValueDictionary[str, _LockBox] = (
            weakref.WeakValueDictionary()
        )
        self._local = threading.local()
        self._all_conns: set[sqlite3.Connection] = set()
        self._metrics = dict.fromkeys(("opens", "reuses", "retries", "failures"), 0)

    def _unit(self) -> float:
        raw = (
            self._rng.random() if isinstance(self._rng, random.Random) else self._rng()
        )
        return min(1.0, max(0.0, raw)) if math.isfinite(raw) else 0.0

    def _backoff_s(self, attempt: int) -> float:
        cfg = self._config
        capped = min(cfg.max_backoff_s, math.ldexp(cfg.base_backoff_s, attempt))
        return capped * (1.0 + cfg.jitter_ratio * self._unit())

    def _bump(self, key: str) -> None:
        with self._guard:
            self._metrics[key] = self._metrics.get(key, 0) + 1

    def _thread_state(self) -> _ThreadState:
        state: _ThreadState | None = getattr(self._local, "state", None)
        if state is None:
            state = _ThreadState()
            args = (self._guard, self._all_conns, state.conns, state.locks)
            _ = weakref.finalize(state, _cleanup_thread, *args)
            setattr(self._local, "state", state)
        return state

    def _db_lock(self, key: str) -> _LockBox:
        with self._guard:
            if (box := self._locks.get(key)) is None:
                box = _LockBox()
                self._locks[key] = box
            return box

    def _open(self, path: Path) -> sqlite3.Connection:
        t = self._config.open_timeout_s
        conn = sqlite3.connect(
            _ro_uri(path), uri=True, timeout=t, check_same_thread=False
        )
        try:
            _ = conn.execute(
                f"PRAGMA busy_timeout = {int(self._config.busy_timeout_ms)}"
            )
            _ = conn.execute("PRAGMA query_only = ON")
        except BaseException:
            conn.close()
            raise
        return conn

    def _get_conn(self, key: str, path: Path) -> sqlite3.Connection:
        st = self._thread_state()
        if (existing := st.conns.get(key)) is not None:
            with self._guard:
                tracked = existing in self._all_conns
            if tracked:
                self._bump("reuses")
                return existing
            _ = st.conns.pop(key, None)
            _ = st.locks.pop(key, None)
        box = self._db_lock(key)
        with box.lock:
            conn = self._open(path)
            with self._guard:
                self._all_conns.add(conn)
                self._metrics["opens"] += 1
            st.conns[key], st.locks[key] = conn, box
            return conn

    def _evict(self, key: str) -> None:
        st = self._thread_state()
        _ = st.locks.pop(key, None)
        if (conn := st.conns.pop(key, None)) is not None:
            with self._guard:
                self._all_conns.discard(conn)
            _close_quietly(conn)

    def run_ro(
        self,
        db_path: str | Path,
        fn: Callable[[sqlite3.Connection], _T],
        *,
        on_conn: Callable[[sqlite3.Connection | None], None] | None = None,
    ) -> _T:
        """Выполняет RO-коллбэк на thread-local соединении с ограниченным retry."""
        path = Path(db_path).resolve()
        key, attempt = str(path), 0
        while True:
            try:
                conn = self._get_conn(key, path)
                if on_conn is not None:
                    on_conn(conn)
                try:
                    return fn(conn)
                finally:
                    if on_conn is not None:
                        on_conn(None)
            except sqlite3.OperationalError as exc:
                if _is_retryable(exc) and attempt < self._config.max_retries:
                    self._evict(key)
                    self._bump("retries")
                    self._sleep(self._backoff_s(attempt))
                    attempt += 1
                    continue
                self._bump("failures")
                raise
            except sqlite3.Error:
                self._bump("failures")
                raise

    def query_rows(
        self, db_path: str | Path, sql: str, params: tuple[object, ...] = ()
    ) -> list[tuple[object, ...]]:
        return self.run_ro(
            db_path,
            lambda c: cast(
                "list[tuple[object, ...]]", c.execute(sql, params).fetchall()
            ),
        )

    def release_thread(self) -> None:
        st: _ThreadState | None = getattr(self._local, "state", None)
        if st is not None:
            _cleanup_thread(self._guard, self._all_conns, st.conns, st.locks)

    def snapshot_metrics(self) -> dict[str, int]:
        with self._guard:
            return {
                **self._metrics,
                "tracked_dbs": len(self._locks),
                "active_conns": len(self._all_conns),
            }

    def close_all(self) -> None:
        with self._guard:
            conns = list(self._all_conns)
            self._all_conns.clear()
            self._locks.clear()
        st: _ThreadState | None = getattr(self._local, "state", None)
        if st is not None:
            st.conns.clear()
            st.locks.clear()
        for conn in conns:
            _close_quietly(conn)
