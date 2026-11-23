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
from typing import Final, TypeVar, cast

_Num = TypeVar("_Num", int, float)
_T = TypeVar("_T")
_ConnMap = dict[str, sqlite3.Connection]


class _ThreadState:
    def __init__(self) -> None:
        self.conns: _ConnMap = {}


def _close_quietly(conn: sqlite3.Connection) -> None:
    try:
        conn.close()
    except sqlite3.Error:
        pass


def _cleanup_thread_conns(
    guard: threading.Lock, all_conns: set[sqlite3.Connection], conns: _ConnMap
) -> None:
    items = list(conns.values())
    conns.clear()
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
        floats = ("open_timeout_s", "base_backoff_s", "max_backoff_s", "jitter_ratio")
        if min(self.busy_timeout_ms, self.max_retries) < 0:
            raise ValueError("busy_timeout_ms/max_retries must be >= 0")
        for name in floats:
            value = cast("float", getattr(self, name))
            bad = not math.isfinite(value) or value < 0.0
            bad = bad or (name == "open_timeout_s" and value == 0.0)
            bad = bad or (name == "jitter_ratio" and value > 1.0)
            if bad:
                raise ValueError(f"{name} out of range, got {value!r}")


def _parse_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    """Строгий bool из окружения: неизвестное значение — `ValueError`."""
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
    """Число из окружения; нечисло — `ValueError`, диапазон проверяет `validate`."""
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return conv(raw.strip())
    except ValueError:
        raise ValueError(f"{key} must be a number, got {raw!r}") from None


def load_sqlite_ro_pool_config(env: Mapping[str, str]) -> SqliteRoPoolConfig:
    """Собирает конфиг из явного окружения (без прямого `os.environ`)."""
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
    """URI только на чтение; `immutable=0` — WAL не обходится, файл не создаётся."""
    text = str(path).replace("%", "%25").replace("?", "%3f").replace("#", "%23")
    return f"file:{text}?mode=ro&immutable=0"


def _is_retryable(exc: sqlite3.OperationalError) -> bool:
    """Ретраибельны только блокировки (`locked`/`busy`), не прочие сбои открытия."""
    return any(m in str(exc).lower() for m in ("locked", "busy"))


class SqliteRoPool:
    """Thread-local RO-соединения на каждый db-path; единственный владелец состояния."""

    def __init__(
        self,
        config: SqliteRoPoolConfig,
        *,
        sleep_fn: Callable[[float], None] | None = None,
        rng: random.Random | Callable[[], float] | None = None,
    ) -> None:
        config.validate()
        self._config: SqliteRoPoolConfig = config
        self._sleep: Callable[[float], None] = sleep_fn or time.sleep
        self._rng: random.Random | Callable[[], float] = rng or random.Random()
        self._guard: threading.Lock = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._local: threading.local = threading.local()
        self._all_conns: set[sqlite3.Connection] = set()
        keys = ("opens", "reuses", "retries", "failures")
        self._metrics: dict[str, int] = dict.fromkeys(keys, 0)

    def _unit(self) -> float:
        rng = self._rng
        raw = rng.random() if isinstance(rng, random.Random) else rng()
        return min(1.0, max(0.0, raw)) if math.isfinite(raw) else 0.0

    def _backoff_s(self, attempt: int) -> float:
        """Экспоненциальный backoff с потолком и jitter; `attempt` — номер ретрая от 0."""
        cfg = self._config
        capped = min(cfg.max_backoff_s, math.ldexp(cfg.base_backoff_s, attempt))
        return capped * (1.0 + cfg.jitter_ratio * self._unit())

    def _bump(self, key: str) -> None:
        with self._guard:
            self._metrics[key] = self._metrics.get(key, 0) + 1

    def _local_map(self) -> _ConnMap:
        state: _ThreadState | None = getattr(self._local, "state", None)
        if state is None:
            state = _ThreadState()
            _ = weakref.finalize(
                state, _cleanup_thread_conns, self._guard, self._all_conns, state.conns
            )
            setattr(self._local, "state", state)
        return state.conns

    def _db_lock(self, key: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                if len(self._locks) >= 512:
                    stale = [k for k, lk in self._locks.items() if not lk.locked()]
                    for k in stale[: len(stale) // 2 + 1]:
                        _ = self._locks.pop(k, None)
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def _open(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(
            _ro_uri(path),
            uri=True,
            timeout=self._config.open_timeout_s,
            check_same_thread=False,
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
        local = self._local_map()
        existing = local.get(key)
        if existing is not None:
            with self._guard:
                tracked = existing in self._all_conns
            if tracked:
                self._bump("reuses")
                return existing
            _ = local.pop(key, None)
        with self._db_lock(key):
            conn = self._open(path)
            with self._guard:
                self._all_conns.add(conn)
                self._metrics["opens"] = self._metrics.get("opens", 0) + 1
            local[key] = conn
            return conn

    def _evict(self, key: str) -> None:
        conn = self._local_map().pop(key, None)
        if conn is not None:
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
        path = Path(db_path)
        key = str(path)
        attempt = 0
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
        """Выполняет RO-запрос thread-local соединением; блокировки ретраятся ограниченно."""
        return self.run_ro(
            db_path,
            lambda c: cast(
                "list[tuple[object, ...]]", c.execute(sql, params).fetchall()
            ),
        )

    def release_thread(self) -> None:
        """Закрывает и освобождает RO-соединения текущего потока."""
        state: _ThreadState | None = getattr(self._local, "state", None)
        if state is not None:
            _cleanup_thread_conns(self._guard, self._all_conns, state.conns)

    def snapshot_metrics(self) -> dict[str, int]:
        """Возвращает НОВЫЙ dict метрик; внутренние реестры наружу не отдаются."""
        with self._guard:
            snap = dict(self._metrics)
            snap["tracked_dbs"] = len(self._locks)
            snap["active_conns"] = len(self._all_conns)
            return snap

    def close_all(self) -> None:
        """Закрывает все соединения и очищает реестры; повторный вызов безопасен."""
        with self._guard:
            conns = list(self._all_conns)
            self._all_conns.clear()
            self._locks.clear()
        state: _ThreadState | None = getattr(self._local, "state", None)
        if state is not None:
            state.conns.clear()
        for conn in conns:
            _close_quietly(conn)
