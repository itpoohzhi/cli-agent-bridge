"""L1/L2 tests for DemandStandbyPool (VER-001..003, VER-006, VER-009, VER-016)."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from core.stdio_resident.demand_standby_pool import DemandStandbyPool
from core.stdio_resident.standby_pool_fsm import ProfileKey, WarmSlotHandle


@dataclass
class _FakeHandle:
    hid: int
    profile: ProfileKey
    alive: bool = True
    rss: float = 50.0
    zc_dir: str = ""
    pgid: int = 0
    proc: subprocess.Popen[bytes] | None = None


class _FakeAdapter:
    def __init__(self, *, rss_mb: float = 50.0, spawn_gate: threading.Event | None = None,
                 real_sleep: bool = False, tmp_root: Path | None = None) -> None:
        self.rss_val = rss_mb
        self.spawn_gate = spawn_gate
        self.real_sleep = real_sleep
        self.tmp_root = tmp_root
        self.lock = threading.Lock()
        self.spawned: list[_FakeHandle] = []
        self.disposed: list[_FakeHandle] = []
        self.claimed: list[_FakeHandle] = []
        self.spawn_started = threading.Event()

    def spawn_warm(self, profile: ProfileKey, *, timeout_s: float) -> WarmSlotHandle:
        self.spawn_started.set()
        if self.spawn_gate is not None:
            self.spawn_gate.wait(timeout=max(0.5, timeout_s))
        zc_dir = ""
        if self.tmp_root is not None and profile.is_zero_canon:
            zc_dir = tempfile.mkdtemp(prefix="zc-test-", dir=str(self.tmp_root))
            os.chmod(zc_dir, 0o700)
        proc: subprocess.Popen[bytes] | None = None
        pgid = 0
        if self.real_sleep:
            proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
            pgid = proc.pid
        with self.lock:
            h = _FakeHandle(len(self.spawned) + 1, profile, True, self.rss_val, zc_dir, pgid, proc)
            self.spawned.append(h)
            return h

    def is_alive(self, handle: WarmSlotHandle) -> bool:
        fh = handle
        assert isinstance(fh, _FakeHandle)
        return fh.alive and (fh.proc is None or fh.proc.poll() is None)

    def claim(self, handle: WarmSlotHandle) -> object:
        fh = handle
        assert isinstance(fh, _FakeHandle)
        with self.lock:
            self.claimed.append(fh)
        return f"payload-{fh.hid}"

    def dispose(self, handle: WarmSlotHandle) -> None:
        fh = handle
        assert isinstance(fh, _FakeHandle)
        fh.alive = False
        if fh.proc is not None and fh.proc.poll() is None:
            try:
                os.killpg(fh.pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            fh.proc.wait(timeout=2.0)
        if fh.zc_dir:
            shutil.rmtree(fh.zc_dir, ignore_errors=True)
        with self.lock:
            self.disposed.append(fh)

    def rss_mb(self, handle: WarmSlotHandle) -> float:
        assert isinstance(handle, _FakeHandle)
        return handle.rss


def _prof(model: str = "m1", rp: str = "zero-canon") -> ProfileKey:
    return ProfileKey("fake", model, "high", rp, "dig1", "neutral")


def _cfg(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "BRIDGE_DEMAND_STANDBY_ENABLED": "1", "BRIDGE_DEMAND_STANDBY_SLIDING_TTL_S": "30",
        "BRIDGE_DEMAND_STANDBY_MAX_SLOTS_PER_PROFILE": "1", "BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS": "3",
        "BRIDGE_DEMAND_STANDBY_MAX_TOTAL_RSS_MB": "500", "BRIDGE_DEMAND_STANDBY_WARMUP_TIMEOUT_S": "10",
        "BRIDGE_DEMAND_STANDBY_REAP_INTERVAL_S": "60",
    }
    base.update(overrides)
    return base
def _wait_ready(pool: DemandStandbyPool, count: int = 1, timeout_s: float = 3.0) -> None:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if int(pool.snapshot()["ready"]) >= count:  # type: ignore[arg-type]
            return
        time.sleep(0.01)
    raise AssertionError(f"ready<{count}: {pool.snapshot()}")
def test_cold_start_zero_slots() -> None:
    ad = _FakeAdapter()
    env = _cfg()
    pool = DemandStandbyPool({"fake": ad}, config_provider=lambda: (env, {}))
    try:
        snap = pool.snapshot()
        assert snap["slots"] == 0 and snap["ready"] == 0 and snap["enabled"] is True and ad.spawned == []
    finally:
        pool.drain_and_shutdown()


def test_first_request_cold_path_and_warmup() -> None:
    gate = threading.Event()
    ad = _FakeAdapter(spawn_gate=gate)
    now = [100.0]
    env = _cfg(BRIDGE_DEMAND_STANDBY_SLIDING_TTL_S="10")
    pool = DemandStandbyPool({"fake": ad}, config_provider=lambda: (env, {}), clock=lambda: now[0])
    try:
        t0 = time.monotonic()
        assert pool.claim(_prof()) is None
        assert time.monotonic() - t0 < 0.05
        assert ad.spawn_started.wait(1.0)
        gate.set()
        _wait_ready(pool, 1)
        now[0] = 108.0
        pool.submit_demand(_prof())
        now[0] = 115.0
        assert pool.reap_once() == 0 and pool.snapshot()["ready"] == 1
    finally:
        pool.drain_and_shutdown()


def test_warm_claim_liveness_fallback_replenish() -> None:
    ad = _FakeAdapter()
    env = _cfg()
    pool = DemandStandbyPool({"fake": ad}, config_provider=lambda: (env, {}))
    try:
        p = _prof("m-zc", "zero-canon")
        assert pool.claim(p) is None
        _wait_ready(pool, 1)
        first = pool.claim(p)
        assert first is not None and first.payload == "payload-1"
        pool.release_claimed(first.slot_id, success=True)
        _wait_ready(pool, 1)
        assert len(ad.disposed) >= 1 and ad.disposed[0].hid == 1
        # Dead slot -> transparent None + dispose + replenish
        live_ready = [h for h in ad.spawned if h.alive][-1]
        live_ready.alive = False
        assert pool.claim(p) is None
        _wait_ready(pool, 1)
        assert any(h.hid == live_ready.hid for h in ad.disposed)
    finally:
        pool.drain_and_shutdown()


def test_caps_lru_rss() -> None:
    ad = _FakeAdapter(rss_mb=120.0)
    now = [10.0]
    env = _cfg(BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS="2", BRIDGE_DEMAND_STANDBY_MAX_TOTAL_RSS_MB="300")
    pool = DemandStandbyPool({"fake": ad}, config_provider=lambda: (env, {}), clock=lambda: now[0])
    try:
        p1, p2, p3 = _prof("p1"), _prof("p2"), _prof("p3")
        pool.submit_demand(p1)
        _wait_ready(pool, 1)
        now[0] = 20.0
        pool.submit_demand(p2)
        _wait_ready(pool, 2)
        now[0] = 30.0
        pool.submit_demand(p3)
        end = time.monotonic() + 2.0
        while time.monotonic() < end and len(ad.disposed) < 1:
            time.sleep(0.01)
        assert len(ad.disposed) >= 1 and ad.disposed[0].profile == p1
        _wait_ready(pool, 2)
        # RSS cap blocks additional spawns
        env["BRIDGE_DEMAND_STANDBY_MAX_TOTAL_RSS_MB"] = "100"
        before = len(ad.spawned)
        pool.submit_demand(_prof("p4"))
        time.sleep(0.05)
        assert len(ad.spawned) == before
    finally:
        pool.drain_and_shutdown()


def test_ttl_expiry_drain_orphans(tmp_path: Path) -> None:
    ad = _FakeAdapter(real_sleep=True, tmp_root=tmp_path)
    now = [10.0]
    env = _cfg(BRIDGE_DEMAND_STANDBY_SLIDING_TTL_S="5")
    pool = DemandStandbyPool({"fake": ad}, config_provider=lambda: (env, {}), clock=lambda: now[0])
    try:
        pool.submit_demand(_prof("exp"))
        _wait_ready(pool, 1)
        h1 = ad.spawned[0]
        assert h1.zc_dir and Path(h1.zc_dir).is_dir()
        now[0] = 20.0
        assert pool.reap_once() == 1
        assert not Path(h1.zc_dir).exists()
        # Dead READY slot reaped by reap_once() while healthy READY slot stays intact
        pool.submit_demand(_prof("dead-reap"))
        _wait_ready(pool, 1)
        dead_h = ad.spawned[-1]
        pool.submit_demand(_prof("alive-keep"))
        _wait_ready(pool, 2)
        dead_h.alive = False
        assert pool.reap_once() == 1 and pool.snapshot()["ready"] == 1
        # Stale epoch in _evict_dead_ready MUST NOT evict a healthy READY slot (epoch fencing!)
        live_sid = next(iter(pool._slots))
        assert pool._evict_dead_ready([(live_sid, 999999, (ad, dead_h))]) == []
        assert pool.snapshot()["ready"] == 1
        # Live toggle enabled: True -> False drains idle slots immediately
        env["BRIDGE_DEMAND_STANDBY_ENABLED"] = "0"
        assert pool.claim(_prof("alive-keep")) is None and pool.snapshot()["ready"] == 0
        env["BRIDGE_DEMAND_STANDBY_ENABLED"] = "1"
        pool.submit_demand(_prof("drain"))
        _wait_ready(pool, 1)
        h2 = ad.spawned[-1]
        assert h2.pgid > 0
        killed = pool.drain_and_shutdown(timeout_s=3.0)
        assert killed >= 1 and pool.snapshot()["slots"] == 0
        try:
            os.killpg(h2.pgid, 0)
            alive = True
        except ProcessLookupError:
            alive = False
        assert not alive and not Path(h2.zc_dir).exists()
    finally:
        pool.drain_and_shutdown(timeout_s=2.0)


def test_epoch_fencing_concurrent_claim() -> None:
    ad = _FakeAdapter()
    env = _cfg(BRIDGE_DEMAND_STANDBY_MAX_SLOTS_PER_PROFILE="1", BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS="1")
    pool = DemandStandbyPool({"fake": ad}, config_provider=lambda: (env, {}))
    try:
        p = _prof("race", "standard")
        pool.submit_demand(p)
        _wait_ready(pool, 1)
        barrier = threading.Barrier(10)
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = [ex.submit(lambda: (barrier.wait(), pool.claim(p, session_key="s1"))[1]) for _ in range(10)]
            wins = [f.result() for f in futs if f.result() is not None]
        assert len(wins) == 1
    finally:
        pool.drain_and_shutdown()

    # Stale epoch: warmup completes after drain_and_shutdown -> immediately disposed, 0 slots
    gate = threading.Event()
    ad2 = _FakeAdapter(spawn_gate=gate)
    pool2 = DemandStandbyPool({"fake": ad2}, config_provider=lambda: (env, {}))
    pool2.submit_demand(_prof("stale"))
    assert ad2.spawn_started.wait(1.0)
    drainer = threading.Thread(target=pool2.drain_and_shutdown, kwargs={"timeout_s": 3.0})
    drainer.start()
    time.sleep(0.05)
    gate.set()
    drainer.join(timeout=4.0)
    assert pool2.snapshot()["slots"] == 0 and len(ad2.spawned) == 1 and len(ad2.disposed) == 1

def test_c3_concurrent_rss_cap_and_zero_canon_cap1() -> None:
    ad = _FakeAdapter(rss_mb=600.0)
    env = _cfg(BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS="2", BRIDGE_DEMAND_STANDBY_MAX_TOTAL_RSS_MB="1024")
    pool = DemandStandbyPool({"fake": ad}, config_provider=lambda: (env, {}))
    try:
        pool.submit_demand(_prof("r1"))
        pool.submit_demand(_prof("r2"))
        end = time.monotonic() + 2.0
        while time.monotonic() < end and (len(ad.spawned) < 2 or pool.snapshot()["warming"] != 0):
            time.sleep(0.01)
        assert pool.snapshot()["ready"] == 1 and pool.snapshot()["slots"] == 1 and len(ad.disposed) == 1
    finally:
        pool.drain_and_shutdown()
    ad1 = _FakeAdapter(rss_mb=500.0)
    env1 = _cfg(BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS="1", BRIDGE_DEMAND_STANDBY_MAX_TOTAL_RSS_MB="500")
    pool1 = DemandStandbyPool({"fake": ad1}, config_provider=lambda: (env1, {}))
    try:
        p = _prof("zc1", "zero-canon")
        pool1.submit_demand(p)
        _wait_ready(pool1, 1)
        cl = pool1.claim(p)
        assert cl is not None
        pool1.release_claimed(cl.slot_id, success=True)
        _wait_ready(pool1, 1)
        assert len(ad1.disposed) == 1 and len(ad1.spawned) == 2 and pool1.snapshot()["slots"] == 1
    finally:
        pool1.drain_and_shutdown()
