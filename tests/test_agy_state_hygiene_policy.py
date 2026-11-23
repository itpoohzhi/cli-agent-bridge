"""Tests for pure state-hygiene policy."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_BRIDGE = _ROOT / "bridges" / "agy-bridge"
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))
_SRC = _BRIDGE / "agy_runtime" / "state_hygiene_policy.py"

from agy_runtime.state_hygiene_policy import (  # noqa: E402
    BoundedLruTtl,
    CachePolicyConfig,
    DisconnectOutcome,
    HygieneFlags,
    OrphanConfig,
    OrphanFsm,
    OrphanSweepAction,
    PoolHealthConfig,
    PoolHealthFSM,
    PoolState,
    compute_epoch_delta,
    session_store_config,
    sha_cache_config,
)

_FORBIDDEN_MODS: frozenset[str] = frozenset(
    {"os", "sys", "socket", "subprocess", "sqlite3", "threading", "time", "datetime", "pathlib", "shutil", "tempfile"}
)
_ALLOWED_MODS: frozenset[str] = frozenset({"__future__", "collections", "dataclasses", "enum", "typing"})
_FORBIDDEN_BUILTINS: frozenset[str] = frozenset({"open", "print", "input", "__import__", "eval", "exec"})


def _flags(code: int) -> HygieneFlags:
    return HygieneFlags(
        adaptive_admission_enabled=bool(code & 1),
        fast_client_gone_enabled=bool(code & 2),
        bounded_state_enabled=bool(code & 4),
        sqlite_ro_hygiene_enabled=bool(code & 8),
    )


def test_zero_io_ast_guard() -> None:
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in _FORBIDDEN_MODS
                assert root in _ALLOWED_MODS
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            assert root not in _FORBIDDEN_MODS
            assert root in _ALLOWED_MODS
        elif isinstance(node, ast.Name):
            assert node.id not in _FORBIDDEN_BUILTINS
        elif isinstance(node, ast.Attribute):
            assert node.attr not in _FORBIDDEN_BUILTINS


def test_epoch_all_16_combinations() -> None:
    off = HygieneFlags()
    for code in range(16):
        flags = _flags(code)
        up = compute_epoch_delta(off, flags, epoch=7)
        assert up.next_epoch == 7
        assert not up.changed
        down = compute_epoch_delta(flags, off, epoch=7)
        if code == 0:
            assert down.next_epoch == 7
            assert not down.changed
        else:
            assert down.next_epoch == 8
            assert down.changed
        same = compute_epoch_delta(flags, flags, epoch=3)
        assert same.next_epoch == 3
        assert not same.changed


def test_epoch_per_component_resets() -> None:
    prev = HygieneFlags(True, True, True, True)
    nxt = HygieneFlags(False, True, False, True)
    delta = compute_epoch_delta(prev, nxt, epoch=10)
    assert delta.next_epoch == 11
    assert delta.reset_admission
    assert not delta.reset_orphan_policy
    assert delta.reset_caches
    assert not delta.reset_pool_health
    enable = compute_epoch_delta(HygieneFlags(), prev, epoch=10)
    assert enable.next_epoch == 10
    assert not enable.changed


def test_orphan_off_mode_legacy_parity() -> None:
    fsm = OrphanFsm()
    assert fsm.cfg == OrphanConfig(True, 5.0, 30.0, 5, 0.4, 1.0)
    for ttfc in (True, False):
        for orphans in (0, 5, 99):
            got = fsm.decide_disconnect(ttfc, tools_count=1, active_orphans=orphans, fast_enabled=False)
            assert got is DisconnectOutcome.DETACH_ORPHAN
            got0 = fsm.decide_disconnect(ttfc, tools_count=0, active_orphans=orphans, fast_enabled=False)
            assert got0 is DisconnectOutcome.CANCEL_SYNC_RELEASE_AFTER_KILL


def test_orphan_fast_pre_ttfc_kill_and_cap() -> None:
    fsm = OrphanFsm(OrphanConfig(orphan_max=5))
    pre = fsm.decide_disconnect(False, tools_count=3, active_orphans=0, fast_enabled=True)
    assert pre is DisconnectOutcome.CANCEL_SYNC_RELEASE_AFTER_KILL
    no_tools = fsm.decide_disconnect(True, tools_count=0, active_orphans=0, fast_enabled=True)
    assert no_tools is DisconnectOutcome.CANCEL_SYNC_RELEASE_AFTER_KILL
    for active in range(5):
        got = fsm.decide_disconnect(True, tools_count=3, active_orphans=active, fast_enabled=True)
        assert got is DisconnectOutcome.DETACH_ORPHAN
    sixth = fsm.decide_disconnect(True, tools_count=3, active_orphans=5, fast_enabled=True)
    assert sixth is DisconnectOutcome.CANCEL_SYNC_RELEASE_AFTER_KILL
    over = fsm.decide_disconnect(True, tools_count=3, active_orphans=6, fast_enabled=True)
    assert over is DisconnectOutcome.CANCEL_SYNC_RELEASE_AFTER_KILL


def test_orphan_expiry_soft_progress_and_hard() -> None:
    fsm = OrphanFsm()
    assert fsm.check_expiry(0.0, 0.0, 4.9) is OrphanSweepAction.KEEP
    assert fsm.check_expiry(0.0, 0.0, 5.0) is OrphanSweepAction.EXPIRE_SOFT_GRACE
    assert fsm.check_expiry(0.0, 10.0, 14.9) is OrphanSweepAction.KEEP
    assert fsm.check_expiry(0.0, 10.0, 15.0) is OrphanSweepAction.EXPIRE_SOFT_GRACE
    assert fsm.check_expiry(0.0, 29.0, 30.0) is OrphanSweepAction.EXPIRE_HARD_TTL
    assert fsm.check_expiry(0.0, 0.0, 30.0) is OrphanSweepAction.EXPIRE_HARD_TTL
    assert fsm.check_expiry(100.0, 100.0, 104.0) is OrphanSweepAction.KEEP


def test_cache_presets() -> None:
    session = session_store_config()
    assert (session.max_entries, session.max_bytes, session.ttl_s) == (1024, 4 * 1024 * 1024, 1800.0)
    sha = sha_cache_config()
    assert (sha.max_entries, sha.max_bytes, sha.ttl_s) == (64, 64 * 1024, 300.0)


def test_cache_entry_caps_64_and_1024() -> None:
    sha: BoundedLruTtl[int] = BoundedLruTtl(sha_cache_config())
    for idx in range(65):
        assert sha.put(f"k{idx}", idx, size_bytes=1, now_s=0.0)
    assert sha.stats().entries == 64
    assert sha.get("k0", now_s=1.0) is None
    assert sha.get("k64", now_s=1.0) == 64
    session: BoundedLruTtl[int] = BoundedLruTtl(session_store_config())
    for idx in range(1025):
        assert session.put(f"s{idx}", idx, size_bytes=1, now_s=0.0)
    assert session.stats().entries == 1024
    assert session.get("s0", now_s=1.0) is None


def test_cache_byte_cap_and_oversized() -> None:
    cfg = CachePolicyConfig(max_entries=10, max_bytes=10, ttl_s=100.0)
    cache: BoundedLruTtl[str] = BoundedLruTtl(cfg)
    assert cache.put("a", "A", size_bytes=6, now_s=0.0)
    assert cache.put("b", "B", size_bytes=6, now_s=0.0)
    assert cache.stats().total_bytes == 6
    assert cache.get("a", now_s=1.0) is None
    assert cache.get("b", now_s=1.0) == "B"
    assert not cache.put("big", "X", size_bytes=11, now_s=1.0)
    assert cache.get("big", now_s=1.0) is None
    assert cache.stats().entries == 1
    sha: BoundedLruTtl[int] = BoundedLruTtl(sha_cache_config())
    assert not sha.put("huge", 1, size_bytes=64 * 1024 + 1, now_s=0.0)
    big: BoundedLruTtl[int] = BoundedLruTtl(session_store_config())
    assert not big.put("huge", 1, size_bytes=4 * 1024 * 1024 + 1, now_s=0.0)


def test_cache_ttl_and_lru_ordering() -> None:
    cfg = CachePolicyConfig(max_entries=3, max_bytes=1000, ttl_s=300.0)
    cache: BoundedLruTtl[int] = BoundedLruTtl(cfg)
    assert cache.put("a", 1, size_bytes=1, now_s=0.0)
    assert cache.put("b", 2, size_bytes=1, now_s=0.0)
    assert cache.put("c", 3, size_bytes=1, now_s=0.0)
    assert cache.get("a", now_s=1.0) == 1
    assert cache.put("d", 4, size_bytes=1, now_s=1.0)
    assert cache.get("b", now_s=2.0) is None
    assert cache.get("a", now_s=2.0) == 1
    assert cache.stats().evictions == 1
    assert cache.get("c", now_s=299.0) == 3
    assert cache.get("c", now_s=300.0) is None
    assert cache.stats().expired >= 1
    assert cache.stats().hits >= 3
    assert cache.stats().misses >= 2


def test_cache_update_and_clear() -> None:
    cache: BoundedLruTtl[int] = BoundedLruTtl(CachePolicyConfig(4, 100, 10.0))
    assert cache.put("x", 1, size_bytes=10, now_s=0.0)
    assert cache.put("x", 2, size_bytes=20, now_s=1.0)
    assert cache.stats().entries == 1
    assert cache.stats().total_bytes == 20
    assert cache.get("x", now_s=2.0) == 2
    assert cache.remove("x")
    assert not cache.remove("x")
    assert cache.put("y", 3, size_bytes=1, now_s=0.0)
    cache.clear()
    assert len(cache) == 0
    assert cache.stats().total_bytes == 0


def test_pool_recycle_idle_and_max_age() -> None:
    fsm = PoolHealthFSM()
    assert fsm.snapshot().state is PoolState.HEALTHY
    assert not fsm.should_recycle(created_s=0.0, last_used_s=0.0, now_s=59.9)
    assert fsm.should_recycle(created_s=0.0, last_used_s=0.0, now_s=60.0)
    assert not fsm.should_recycle(created_s=0.0, last_used_s=590.0, now_s=599.9)
    assert fsm.should_recycle(created_s=0.0, last_used_s=599.0, now_s=600.0)
    cfg = PoolHealthConfig(idle_ttl_s=60.0, max_age_s=600.0, base_backoff_s=0.05, max_backoff_s=2.0)
    assert PoolHealthFSM(cfg).should_recycle(0.0, 0.0, 61.0)


def test_pool_backoff_sequence_and_recovery() -> None:
    fsm = PoolHealthFSM()
    expected: tuple[float, ...] = (0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 2.0, 2.0)
    for want in expected:
        assert fsm.record_error(now_s=100.0) == want
    assert fsm.state is PoolState.DEGRADED_BACKOFF
    assert fsm.error_streak == 8
    assert fsm.total_errors == 8
    assert fsm.backoff_until_s == 102.0
    assert not fsm.can_checkout(now_s=101.9)
    assert fsm.can_checkout(now_s=102.0)
    fsm.record_success()
    assert fsm.state is PoolState.HEALTHY
    assert fsm.error_streak == 0
    assert fsm.can_checkout(now_s=102.0)
    assert fsm.record_error(now_s=200.0) == 0.05


def test_pool_drain_and_reset() -> None:
    fsm = PoolHealthFSM()
    assert fsm.can_checkout(now_s=0.0)
    fsm.begin_drain()
    assert fsm.state is PoolState.DRAINING
    assert not fsm.can_checkout(now_s=0.0)
    _ = fsm.record_error(now_s=0.0)
    assert fsm.state is PoolState.DRAINING
    fsm.finish_drain()
    assert fsm.state is PoolState.HEALTHY
    assert fsm.can_checkout(now_s=0.0)
    assert fsm.error_streak == 0
    fsm.record_recycle()
    _ = fsm.record_error(now_s=10.0)
    snap = fsm.snapshot()
    assert snap.total_recycled == 1
    assert snap.total_errors == 2
    fsm.reset()
    snap2 = fsm.snapshot()
    assert snap2.state is PoolState.HEALTHY
    assert (snap2.error_streak, snap2.total_recycled, snap2.total_errors) == (0, 0, 0)
    assert snap2.backoff_until_s == 0.0
