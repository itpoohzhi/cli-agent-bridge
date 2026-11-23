"""Pure state-hygiene policy: flags, orphan FSM, bounded cache, pool health."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar, final

T = TypeVar("T")


@final
@dataclass(frozen=True, slots=True)
class HygieneFlags:
    adaptive_admission_enabled: bool = False
    fast_client_gone_enabled: bool = False
    bounded_state_enabled: bool = False
    sqlite_ro_hygiene_enabled: bool = False


@final
@dataclass(frozen=True, slots=True)
class EpochDelta:
    next_epoch: int
    reset_admission: bool
    reset_orphan_policy: bool
    reset_caches: bool
    reset_pool_health: bool

    @property
    def changed(self) -> bool:
        return self.reset_admission or self.reset_orphan_policy or self.reset_caches or self.reset_pool_health


def compute_epoch_delta(prev: HygieneFlags, nxt: HygieneFlags, epoch: int) -> EpochDelta:
    r_adm = prev.adaptive_admission_enabled and not nxt.adaptive_admission_enabled
    r_orp = prev.fast_client_gone_enabled and not nxt.fast_client_gone_enabled
    r_cac = prev.bounded_state_enabled and not nxt.bounded_state_enabled
    r_pol = prev.sqlite_ro_hygiene_enabled and not nxt.sqlite_ro_hygiene_enabled
    changed = r_adm or r_orp or r_cac or r_pol
    return EpochDelta(epoch + 1 if changed else epoch, r_adm, r_orp, r_cac, r_pol)


@final
@dataclass(frozen=True, slots=True)
class OrphanConfig:
    require_post_ttfc: bool = True
    soft_grace_s: float = 5.0
    hard_ttl_s: float = 30.0
    orphan_max: int = 5
    teardown_grace_s: float = 0.4
    teardown_total_cap_s: float = 1.0


@final
class DisconnectOutcome(str, Enum):
    DETACH_ORPHAN = "detach_orphan"
    CANCEL_SYNC_RELEASE_AFTER_KILL = "cancel_sync_release_after_kill"


@final
class OrphanSweepAction(str, Enum):
    KEEP = "keep"
    EXPIRE_SOFT_GRACE = "expire_soft_grace"
    EXPIRE_HARD_TTL = "expire_hard_ttl"


@final
class OrphanFsm:
    __slots__ = ("_cfg",)

    def __init__(self, cfg: OrphanConfig | None = None) -> None:
        self._cfg: OrphanConfig = cfg if cfg is not None else OrphanConfig()

    @property
    def cfg(self) -> OrphanConfig:
        return self._cfg

    def decide_disconnect(self, ttfc_received: bool, tools_count: int, active_orphans: int, fast_enabled: bool) -> DisconnectOutcome:
        if not fast_enabled:
            return DisconnectOutcome.DETACH_ORPHAN if tools_count > 0 else DisconnectOutcome.CANCEL_SYNC_RELEASE_AFTER_KILL
        ttfc_ok = ttfc_received or not self._cfg.require_post_ttfc
        if ttfc_ok and tools_count > 0 and active_orphans < self._cfg.orphan_max:
            return DisconnectOutcome.DETACH_ORPHAN
        return DisconnectOutcome.CANCEL_SYNC_RELEASE_AFTER_KILL

    def check_expiry(self, detached_s: float, last_progress_s: float, now_s: float) -> OrphanSweepAction:
        if now_s - detached_s >= self._cfg.hard_ttl_s:
            return OrphanSweepAction.EXPIRE_HARD_TTL
        anchor_s = detached_s if detached_s >= last_progress_s else last_progress_s
        if now_s - anchor_s >= self._cfg.soft_grace_s:
            return OrphanSweepAction.EXPIRE_SOFT_GRACE
        return OrphanSweepAction.KEEP


@final
@dataclass(frozen=True, slots=True)
class CachePolicyConfig:
    max_entries: int
    max_bytes: int
    ttl_s: float


def session_store_config() -> CachePolicyConfig:
    return CachePolicyConfig(max_entries=1024, max_bytes=4 * 1024 * 1024, ttl_s=1800.0)


def sha_cache_config() -> CachePolicyConfig:
    return CachePolicyConfig(max_entries=64, max_bytes=64 * 1024, ttl_s=300.0)


@final
@dataclass(frozen=True, slots=True)
class CacheStats:
    entries: int
    total_bytes: int
    hits: int
    misses: int
    evictions: int
    expired: int


@final
@dataclass(slots=True)
class _Entry(Generic[T]):
    value: T
    size_bytes: int
    expires_s: float


@final
class BoundedLruTtl(Generic[T]):
    __slots__ = ("_cfg", "_entries", "_evictions", "_expired", "_hits", "_misses", "_total_bytes")

    def __init__(self, cfg: CachePolicyConfig) -> None:
        self._cfg: CachePolicyConfig = cfg
        self._entries: OrderedDict[str, _Entry[T]] = OrderedDict()
        self._total_bytes: int = 0
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0
        self._expired: int = 0

    def __len__(self) -> int:
        return len(self._entries)

    def _purge_expired(self, now_s: float) -> None:
        stale: list[str] = [k for k, e in self._entries.items() if e.expires_s <= now_s]
        for key in stale:
            entry = self._entries.pop(key)
            self._total_bytes -= entry.size_bytes
            self._expired += 1

    def get(self, key: str, now_s: float) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.expires_s <= now_s:
            dropped = self._entries.pop(key)
            self._total_bytes -= dropped.size_bytes
            self._expired += 1
            self._misses += 1
            return None
        self._entries.move_to_end(key)
        self._hits += 1
        return entry.value

    def put(self, key: str, value: T, size_bytes: int, now_s: float) -> bool:
        if size_bytes < 0 or size_bytes > self._cfg.max_bytes or self._cfg.max_entries <= 0 or self._cfg.max_bytes <= 0:
            return False
        self._purge_expired(now_s)
        old = self._entries.pop(key, None)
        if old is not None:
            self._total_bytes -= old.size_bytes
        self._entries[key] = _Entry(value=value, size_bytes=size_bytes, expires_s=now_s + self._cfg.ttl_s)
        self._total_bytes += size_bytes
        while len(self._entries) > self._cfg.max_entries or self._total_bytes > self._cfg.max_bytes:
            _, evicted = self._entries.popitem(last=False)
            self._total_bytes -= evicted.size_bytes
            self._evictions += 1
        return key in self._entries

    def remove(self, key: str) -> bool:
        entry = self._entries.pop(key, None)
        if entry is None:
            return False
        self._total_bytes -= entry.size_bytes
        return True

    def clear(self) -> None:
        self._entries.clear()
        self._total_bytes = 0

    def purge_expired(self, now_s: float) -> int:
        before = self._expired
        self._purge_expired(now_s)
        return self._expired - before

    def stats(self) -> CacheStats:
        return CacheStats(len(self._entries), self._total_bytes, self._hits, self._misses, self._evictions, self._expired)


@final
class PoolState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED_BACKOFF = "degraded_backoff"
    DRAINING = "draining"


@final
@dataclass(frozen=True, slots=True)
class PoolHealthConfig:
    idle_ttl_s: float = 60.0
    max_age_s: float = 600.0
    base_backoff_s: float = 0.05
    max_backoff_s: float = 2.0


@final
@dataclass(frozen=True, slots=True)
class PoolHealthSnapshot:
    state: PoolState
    error_streak: int
    backoff_until_s: float
    total_recycled: int
    total_errors: int


@final
class PoolHealthFSM:
    __slots__ = ("_backoff_until_s", "_cfg", "_error_streak", "_state", "_total_errors", "_total_recycled")

    def __init__(self, cfg: PoolHealthConfig | None = None) -> None:
        self._cfg: PoolHealthConfig = cfg if cfg is not None else PoolHealthConfig()
        self._state: PoolState = PoolState.HEALTHY
        self._error_streak: int = 0
        self._backoff_until_s: float = 0.0
        self._total_recycled: int = 0
        self._total_errors: int = 0

    @property
    def state(self) -> PoolState: return self._state
    @property
    def error_streak(self) -> int: return self._error_streak
    @property
    def backoff_until_s(self) -> float: return self._backoff_until_s
    @property
    def total_recycled(self) -> int: return self._total_recycled
    @property
    def total_errors(self) -> int: return self._total_errors

    def can_checkout(self, now_s: float) -> bool:
        if self._state is PoolState.DRAINING:
            return False
        if self._state is PoolState.DEGRADED_BACKOFF:
            return now_s >= self._backoff_until_s
        return True

    def should_recycle(self, created_s: float, last_used_s: float, now_s: float) -> bool:
        if now_s - created_s >= self._cfg.max_age_s:
            return True
        return now_s - last_used_s >= self._cfg.idle_ttl_s

    def record_recycle(self) -> None:
        self._total_recycled += 1

    def record_success(self) -> None:
        self._error_streak = 0
        self._backoff_until_s = 0.0
        if self._state is PoolState.DEGRADED_BACKOFF:
            self._state = PoolState.HEALTHY

    def record_error(self, now_s: float) -> float:
        self._total_errors += 1
        self._error_streak += 1
        shift = self._error_streak - 1
        backoff = self._cfg.base_backoff_s * float(1 << min(shift, 6))
        if backoff > self._cfg.max_backoff_s:
            backoff = self._cfg.max_backoff_s
        self._backoff_until_s = now_s + backoff
        if self._state is not PoolState.DRAINING:
            self._state = PoolState.DEGRADED_BACKOFF
        return backoff

    def begin_drain(self) -> None:
        self._state = PoolState.DRAINING

    def finish_drain(self) -> None:
        self._state, self._error_streak, self._backoff_until_s = PoolState.HEALTHY, 0, 0.0

    def reset(self) -> None:
        self._state, self._error_streak, self._backoff_until_s = PoolState.HEALTHY, 0, 0.0
        self._total_recycled = self._total_errors = 0

    def snapshot(self) -> PoolHealthSnapshot:
        return PoolHealthSnapshot(self._state, self._error_streak, self._backoff_until_s, self._total_recycled, self._total_errors)
