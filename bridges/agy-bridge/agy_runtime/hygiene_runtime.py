"""Thread-safe single lock-owner runtime for adaptive admission, orphans, caches, and SQLite RO hygiene."""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final, Protocol, TypeVar, final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.adaptive_admission import AdaptiveAdmissionRegistry, AdmissionDecision, AdmissionKey, OutcomeKind, canonical_key  # noqa: E402

from . import long_session_config as _lsc  # noqa: E402
from .slot_and_session import SqliteRoPoolBackoffError, is_cold_sqlite_wal_wait  # noqa: E402
from .state_hygiene_policy import BoundedLruTtl, CachePolicyConfig, DisconnectOutcome, HygieneFlags, OrphanFsm, OrphanSweepAction, PoolHealthFSM, compute_epoch_delta, session_store_config, sha_cache_config  # noqa: E402

_T = TypeVar("_T")
UPSTREAM_LIMIT: Final[int] = 16
_FLAG_SPECS: Final[tuple[tuple[str, str], ...]] = (
    ("agy_adaptive_admission_enabled", "AGY_ADAPTIVE_ADMISSION_ENABLED"),
    ("agy_fast_client_gone_enabled", "AGY_FAST_CLIENT_GONE_ENABLED"),
    ("agy_bounded_state_enabled", "AGY_BOUNDED_STATE_ENABLED"),
    ("agy_sqlite_ro_hygiene_enabled", "AGY_SQLITE_RO_HYGIENE_ENABLED"),
)


class PoolLike(Protocol):
    def query_rows(self, db_path: Path, sql: str) -> object: ...
    def run_ro(self, db_path: Path, fn: Callable[..., _T], on_conn: Callable[..., None] | None = None) -> _T: ...
    def release_thread(self) -> None: ...
    def close_all(self) -> None: ...


class LegacyAdmissionLike(Protocol):
    def acquire(self, key: str, external_held: int = 0, now_s: float = 0.0) -> bool: ...
    def release(self, key: str = "agy_upstream") -> None: ...


def _invalid_pgid(pgid: int) -> bool:
    try:
        return pgid <= 1 or pgid == os.getpgrp()
    except OSError:
        return True


def _safe_kill(pgid: int, sig: int) -> None:
    if not _invalid_pgid(pgid):
        try:
            os.killpg(pgid, sig)
        except OSError:
            pass


def _default_waiter(pgid: int, timeout_s: float) -> bool:
    deadline = time.monotonic() + max(0.0, timeout_s)
    while time.monotonic() < deadline:
        try:
            if os.waitpid(-pgid, os.WNOHANG)[0] != 0:
                return True
            os.killpg(pgid, 0)
        except OSError:
            return True
        time.sleep(0.01)
    return False


def _bounded_teardown(pgid: int, kill_fn: Callable[[int, int], None] | None, waiter: Callable[[int, float], bool] | None) -> None:
    if _invalid_pgid(pgid):
        return
    k, w = kill_fn or _safe_kill, waiter or _default_waiter
    k(pgid, signal.SIGTERM)
    if not w(pgid, 0.4):
        k(pgid, signal.SIGKILL)
        _ = w(pgid, 0.6)
    try:
        _ = os.waitpid(-pgid, os.WNOHANG)
    except OSError:
        pass


@final
class _DualCache:
    def __init__(self, cfg: CachePolicyConfig) -> None:
        self._lock, self._lru, self._raw = threading.Lock(), BoundedLruTtl[str](cfg), dict[str, str]()
    def get(self, key: str, bounded: bool) -> str | None:
        with self._lock:
            return self._lru.get(key, time.monotonic()) if bounded else self._raw.get(key)
    def put(self, key: str, val: str, bounded: bool) -> None:
        with self._lock:
            _ = self._lru.put(key, val, len(val.encode("utf-8")), time.monotonic()) if bounded else self._raw.__setitem__(key, val)
    def claim(self, key: str, val: str, bounded: bool) -> bool:
        now = time.monotonic()
        with self._lock:
            if bounded:
                return False if self._lru.get(key, now) is not None else self._lru.put(key, val, len(val.encode("utf-8")), now)
            return False if key in self._raw else (self._raw.__setitem__(key, val) is None)
    def remove(self, key: str) -> None:
        with self._lock:
            _ = (self._raw.pop(key, None), self._lru.remove(key))
    def clear_or_prune(self, clear: bool, bounded: bool) -> int:
        with self._lock:
            if clear:
                self._raw.clear()
                self._lru.clear()
                return 0
            return self._lru.purge_expired(time.monotonic()) if bounded else 0
    def count(self, bounded: bool) -> int:
        with self._lock:
            return len(self._lru) if bounded else len(self._raw)


@final
class ManagedSqliteRoPool:
    def __init__(self, inner: PoolLike | None = None, hygiene_enabled: bool = False) -> None:
        self._inner, self._lock, self._enabled, self._fsm = inner, threading.Lock(), hygiene_enabled, PoolHealthFSM()
    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            if self._enabled and not enabled:
                self._fsm.reset()
            self._enabled = enabled
    def _exec(self, call: Callable[[PoolLike], _T], db_path: Path | None = None) -> _T:
        with self._lock:
            allowed = True if not self._enabled else self._fsm.can_checkout(time.monotonic())
        if not allowed:
            raise SqliteRoPoolBackoffError("sqlite_ro_pool_backoff")
        if self._inner is None:
            raise RuntimeError("sqlite_ro_pool_unavailable")
        try:
            res = call(self._inner)
        except Exception as exc:
            if not is_cold_sqlite_wal_wait(exc, db_path):
                with self._lock:
                    _ = self._fsm.record_error(time.monotonic()) if self._enabled else None
            self._inner.release_thread()
            raise
        with self._lock:
            _ = self._fsm.record_success() if self._enabled else None
        return res
    def query_rows(self, db_path: Path | str, sql: str) -> object:
        return self._exec(lambda p: p.query_rows(Path(db_path), sql), Path(db_path))
    def run_ro(self, db_path: Path | str, fn: Callable[..., _T], on_conn: Callable[..., None] | None = None) -> _T:
        p = Path(db_path) if isinstance(db_path, str) else db_path
        return self._exec(lambda pool: pool.run_ro(p, fn) if on_conn is None else pool.run_ro(p, fn, on_conn=on_conn), p)
    def release_thread(self) -> None:
        _ = self._inner.release_thread() if self._inner is not None else None
    def close_all(self) -> None:
        if self._inner is not None:
            self._inner.close_all()
    def release_thread(self) -> None:
        if self._inner is not None:
            self._inner.release_thread()
    def health_tuple(self) -> tuple[bool, int, float]:
        with self._lock:
            s = self._fsm.snapshot()
            return (self._enabled, s.error_streak, s.backoff_until_s)


@final
class HygieneRuntime:
    def __init__(self, pool: PoolLike | None = None, admission: LegacyAdmissionLike | None = None, config_path: Path | None = None) -> None:
        self._flags_lock, self._admission_lock = threading.Lock(), threading.Lock()
        self._orphan_lock, self._pool_lock = threading.Lock(), threading.Lock()
        self._config_path, self._flags, self._epoch = config_path, HygieneFlags(), 0
        self._detached, self._cancelling = dict[int, tuple[float, float]](), set[int]()
        self._orphan_fsm, self._reg = OrphanFsm(), AdaptiveAdmissionRegistry()
        self._legacy_adm, self._legacy_hits = admission, list[float]()
        self._sha, self._session = _DualCache(sha_cache_config()), _DualCache(session_store_config())
        self._pool: ManagedSqliteRoPool = ManagedSqliteRoPool(pool, False)

    @property
    def pool(self) -> ManagedSqliteRoPool:
        return self._pool

    def _cur_flags(self) -> HygieneFlags:
        with self._flags_lock:
            return self._flags

    def snapshot_flags(self, config_path: Path | None = None) -> HygieneFlags:
        cp = config_path or self._config_path
        v = tuple(_lsc.read_bool_setting(dk, ek, False, config_path=cp) for dk, ek in _FLAG_SPECS)
        nxt = HygieneFlags(v[0], v[1], v[2], v[3])
        with self._flags_lock:
            delta = compute_epoch_delta(self._flags, nxt, self._epoch)
            self._epoch, self._flags = delta.next_epoch, nxt
        if delta.reset_caches:
            _ = (self._sha.clear_or_prune(True, False), self._session.clear_or_prune(True, False))
        if delta.reset_admission:
            with self._admission_lock:
                self._reg.reset(time.monotonic())
                self._legacy_hits.clear()
        with self._pool_lock:
            self._pool.set_enabled(nxt.sqlite_ro_hygiene_enabled)
        return nxt

    def upstream_held_count(self) -> int:
        with self._orphan_lock:
            return len(self._detached) + len(self._cancelling)
    def acquire(self, key: AdmissionKey, config_path: Path | None = None) -> AdmissionDecision:
        cp = config_path or self._config_path
        flags = self.snapshot_flags(cp) if cp is not None else self._cur_flags()
        if not flags.adaptive_admission_enabled:
            return AdmissionDecision(True, 0, 200, 0.0, "flag_off", key)
        held = self.upstream_held_count()
        with self._admission_lock:
            return self._reg.acquire(key, time.monotonic(), external_held=held)
    def release(self, ticket_id: int, outcome: OutcomeKind = OutcomeKind.OK, ttfc_ms: float | None = None) -> None:
        if ticket_id > 0:
            with self._admission_lock:
                self._reg.release(ticket_id, time.monotonic(), outcome=outcome, ttfc_ms=ttfc_ms)
    def try_acquire_admission(self, key: str = "agy_upstream") -> bool:
        held, now_s = self.upstream_held_count(), time.monotonic()
        if not self._cur_flags().adaptive_admission_enabled:
            return held < UPSTREAM_LIMIT
        with self._admission_lock:
            adm = self._legacy_adm
            ok = adm.acquire(key, held, now_s) if adm else self._reg.acquire(canonical_key("chat", key, "default"), now_s, external_held=held).admitted
            if not ok:
                self._legacy_hits.append(now_s)
            return ok
    def release_admission(self, key: str = "agy_upstream") -> None:
        if self._legacy_adm is not None:
            with self._admission_lock:
                self._legacy_adm.release(key)
    def handle_disconnect(
        self, pgid: int, ttfc_received: bool, tools_count: int,
        kill_fn: Callable[[int, int], None] | None = None, waiter: Callable[[int, float], bool] | None = None,
    ) -> bool:
        if _invalid_pgid(pgid):
            return False
        fast = self.snapshot_flags(self._config_path).fast_client_gone_enabled if self._config_path else self._cur_flags().fast_client_gone_enabled
        now_s = time.monotonic()
        with self._orphan_lock:
            if self._orphan_fsm.decide_disconnect(ttfc_received, tools_count, len(self._detached), fast) is DisconnectOutcome.DETACH_ORPHAN:
                self._detached[pgid] = (now_s, now_s)
                return True
            self._cancelling.add(pgid)
            _ = self._detached.pop(pgid, None)
        try:
            _bounded_teardown(pgid, kill_fn, waiter)
        finally:
            with self._orphan_lock:
                self._cancelling.discard(pgid)
        return False
    def touch_progress(self, pgid: int) -> None:
        with self._orphan_lock:
            if (e := self._detached.get(pgid)) is not None:
                self._detached[pgid] = (e[0], time.monotonic())
    def release_detached(self, pgid: int) -> bool:
        with self._orphan_lock:
            return self._detached.pop(pgid, None) is not None
    def _drain_pgids(self, pgids: list[int], kill_fn: Callable[[int, int], None] | None, waiter: Callable[[int, float], bool] | None) -> int:
        for pgid in pgids:
            _bounded_teardown(pgid, kill_fn, waiter)
        with self._orphan_lock:
            for pgid in pgids:
                _ = (self._detached.pop(pgid, None), self._cancelling.discard(pgid))
        return len(pgids)
    def sweep_orphans(self, kill_fn: Callable[[int, int], None] | None = None, waiter: Callable[[int, float], bool] | None = None) -> int:
        now_s = time.monotonic()
        with self._orphan_lock:
            exp = [p for p, (d, pr) in self._detached.items() if self._orphan_fsm.check_expiry(d, pr, now_s) is not OrphanSweepAction.KEEP]
        return self._drain_pgids(exp, kill_fn, waiter)
    def shutdown_cleanup(self, kill_fn: Callable[[int, int], None] | None = None, waiter: Callable[[int, float], bool] | None = None) -> int:
        with self._orphan_lock:
            pgids = list(dict.fromkeys((*self._detached.keys(), *self._cancelling)))
        return self._drain_pgids(pgids, kill_fn, waiter)

    def sha_cache_get(self, key: str) -> str | None: return self._sha.get(key, self._cur_flags().bounded_state_enabled)
    def sha_cache_put(self, key: str, value: str) -> None: self._sha.put(key, value, self._cur_flags().bounded_state_enabled)
    def session_claim(self, key: str, value: str = "1") -> bool: return self._session.claim(key, value, self._cur_flags().bounded_state_enabled)
    def session_commit(self, key: str, value: str) -> None: self._session.put(key, value, self._cur_flags().bounded_state_enabled)
    def session_invalidate(self, key: str) -> None: self._session.remove(key)
    def session_prune(self) -> int: return self._session.clear_or_prune(False, self._cur_flags().bounded_state_enabled)

    def health_snapshot(self, config_path: Path | None = None) -> dict[str, object]:
        cp = config_path or self._config_path
        flags, now_s = (self.snapshot_flags(cp) if cp is not None else self._cur_flags()), time.monotonic()
        with self._flags_lock:
            epoch = self._epoch
        with self._orphan_lock:
            detached_ids, cancelling_n = tuple(self._detached.keys()), len(self._cancelling)
        with self._admission_lock:
            hits = self._reg.health_snapshot(now_s).capacity_hits_60s + sum(1 for t in self._legacy_hits if t >= now_s - 60.0)
        with self._pool_lock:
            pool_t = self._pool.health_tuple()
        held, bounded = len(detached_ids) + cancelling_n, flags.bounded_state_enabled
        return {
            "epoch": epoch, "upstream_limit": UPSTREAM_LIMIT, "upstream_held": held, "detached_count": len(detached_ids),
            "cancelling_count": cancelling_n, "detached_pgids": detached_ids, "sha_entries": self._sha.count(bounded),
            "session_entries": self._session.count(bounded), "capacity_hits_60s": hits, "pool_hygiene_enabled": pool_t[0],
            "pool_fail_streak": pool_t[1], "restart_ready": held == 0,
            "hygiene_flags": {
                "adaptive_admission_enabled": flags.adaptive_admission_enabled, "fast_client_gone_enabled": flags.fast_client_gone_enabled,
                "bounded_state_enabled": bounded, "sqlite_ro_hygiene_enabled": flags.sqlite_ro_hygiene_enabled,
            },
        }
