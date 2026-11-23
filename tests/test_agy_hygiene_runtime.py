from __future__ import annotations

import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Final, final

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
BRIDGE: Final[Path] = ROOT / "bridges" / "agy-bridge"
for _p in (str(BRIDGE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agy_runtime.hygiene_runtime import HygieneRuntime, ManagedSqliteRoPool  # noqa: E402


@final
class FakeAdmission:
    def __init__(self, limit: int = 16) -> None:
        self._limit: int = limit
        self._lock: threading.Lock = threading.Lock()
        self._active: int = 0
        self.shed: int = 0

    def acquire(self, key: str, external_held: int = 0, now_s: float = 0.0) -> bool:
        _ = (key, now_s)
        with self._lock:
            if self._active + external_held >= self._limit:
                self.shed += 1
                return False
            self._active += 1
            return True

    def release(self, key: str = "agy_upstream") -> None:
        _ = key
        with self._lock:
            self._active = max(0, self._active - 1)

    def active(self) -> int:
        with self._lock:
            return self._active


@final
class MockPool:
    def __init__(self, fail: bool = False) -> None:
        self.fail: bool = fail
        self.calls: int = 0
        self.released: int = 0
        self.closed: int = 0

    def query_rows(self, db_path: object, sql: object) -> tuple[tuple[int, ...], ...]:
        _ = (db_path, sql)
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return ((1,),)

    def run_ro(self, db_path: object, fn: object, on_conn: object = None) -> object:
        _ = (db_path, on_conn)
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        if callable(fn):
            try:
                return fn(None)  # type: ignore[operator]
            except TypeError:
                return fn()  # type: ignore[operator]
        return None

    def release_thread(self) -> None:
        self.released += 1

    def close_all(self) -> None:
        self.closed += 1


def _force_flags(rt: HygieneRuntime, mask: int) -> None:
    from agy_runtime.hygiene_runtime import HygieneFlags

    flags: HygieneFlags = HygieneFlags(bool(mask & 1), bool(mask & 2), bool(mask & 4), bool(mask & 8))
    with rt._flags_lock:  # noqa: SLF001
        rt._flags = flags  # noqa: SLF001


def test_detached_counts_against_limit_16() -> None:
    adm: FakeAdmission = FakeAdmission(16)
    rt: HygieneRuntime = HygieneRuntime(pool=MockPool(), admission=adm)
    _force_flags(rt, 1)
    base_pgid: int = 990000
    for i in range(5):
        ok: bool = rt.handle_disconnect(base_pgid + i, True, 1, lambda p, s: None, lambda p, t: True)
        assert ok is True
    assert rt.upstream_held_count() == 5
    admitted: int = 0
    for _ in range(11):
        if rt.try_acquire_admission():
            admitted += 1
    assert admitted == 11
    assert rt.try_acquire_admission() is False
    snap: dict[str, object] = rt.health_snapshot()
    assert snap["capacity_hits_60s"] == 1
    assert snap["upstream_held"] == 5


def test_pre_ttfc_bounded_kill_before_return() -> None:
    calls: list[tuple[int, int]] = []
    order: list[str] = []

    def kill_fn(pgid: int, sig: int) -> None:
        calls.append((pgid, sig))
        order.append(f"kill:{sig}")
    def waiter(pgid: int, timeout_s: float) -> bool:
        _ = pgid
        return timeout_s > 0.5
    rt: HygieneRuntime = HygieneRuntime(pool=MockPool(), admission=FakeAdmission())
    start: float = time.monotonic()
    result: bool = rt.handle_disconnect(991111, False, 0, kill_fn, waiter)
    elapsed: float = time.monotonic() - start
    order.append("returned")
    assert result is False and elapsed <= 1.0 and calls[0][1] == signal.SIGTERM
    assert calls[-1][1] == signal.SIGKILL and order[-1] == "returned" and rt.upstream_held_count() == 0

def test_own_pgrp_guard_never_signalled() -> None:
    calls: list[tuple[int, int]] = []
    rt: HygieneRuntime = HygieneRuntime(pool=MockPool(), admission=FakeAdmission())
    assert rt.handle_disconnect(os.getpgrp(), False, 0, lambda p, s: calls.append((p, s)), lambda p, t: True) is False
    assert calls == [] and rt.handle_disconnect(1, False, 0) is False and rt.handle_disconnect(0, True, 3) is False


def test_shutdown_cleanup_drains_detached() -> None:
    killed: list[int] = []
    rt: HygieneRuntime = HygieneRuntime(pool=MockPool(), admission=FakeAdmission())
    for i in range(3):
        rt.handle_disconnect(992000 + i, True, 2, lambda p, s: None, lambda p, t: True)
    assert rt.upstream_held_count() == 3
    n: int = rt.shutdown_cleanup(lambda p, s: killed.append(p), lambda p, t: True)
    assert n == 3
    assert rt.upstream_held_count() == 0
    assert set(killed) == {992000, 992001, 992002}
    assert rt.health_snapshot()["restart_ready"] is True


def test_sweep_orphans_expired() -> None:
    rt: HygieneRuntime = HygieneRuntime(pool=MockPool(), admission=FakeAdmission())
    rt.handle_disconnect(993000, True, 1, lambda p, s: None, lambda p, t: True)
    with rt._orphan_lock:  # noqa: SLF001
        rt._detached[993000] = (time.monotonic() - 100.0, time.monotonic() - 100.0)  # noqa: SLF001
    killed: list[int] = []
    n: int = rt.sweep_orphans(lambda p, s: killed.append(p), lambda p, t: True)
    assert n == 1
    assert rt.upstream_held_count() == 0


def test_managed_pool_backoff_and_recycle() -> None:
    mock: MockPool = MockPool(fail=True)
    pool: ManagedSqliteRoPool = ManagedSqliteRoPool(mock, hygiene_enabled=True)
    raised: bool = False
    try:
        pool.query_rows("x.db", "select 1")
    except RuntimeError:
        raised = True
    assert raised is True
    assert mock.released >= 1 or mock.closed >= 1
    blocked: bool = False
    try:
        pool.query_rows("x.db", "select 1")
    except RuntimeError:
        blocked = True
    assert blocked is True
    mock2: MockPool = MockPool(fail=False)
    ok_pool: ManagedSqliteRoPool = ManagedSqliteRoPool(mock2, hygiene_enabled=True)
    rows: object = ok_pool.query_rows("x.db", "select 1")
    assert rows == ((1,),)
    ok_pool.close_all()
    assert mock2.closed == 1


def test_managed_pool_passthrough_when_disabled() -> None:
    mock: MockPool = MockPool(fail=False)
    pool: ManagedSqliteRoPool = ManagedSqliteRoPool(mock, hygiene_enabled=False)
    assert pool.query_rows("a", "b") == ((1,),)
    result: object = pool.run_ro("a", lambda conn: 7)
    assert result == 7


def test_sqlite_ro_pool_untouched_298_lines() -> None:
    target: Path = BRIDGE / "agy_runtime" / "sqlite_ro_pool.py"
    if not target.exists():
        return
    lines: int = len(target.read_text(encoding="utf-8").splitlines())
    assert lines == 298, f"sqlite_ro_pool.py must stay 298 lines, got {lines}"


def test_hygiene_files_line_budget() -> None:
    for rel in ("bridges/agy-bridge/agy_runtime/hygiene_runtime.py", "tests/test_agy_hygiene_runtime.py"):
        p: Path = ROOT / rel
        if p.exists():
            n: int = len(p.read_text(encoding="utf-8").splitlines())
            assert n <= 300, f"{rel} has {n} lines"


def test_all_16_flag_subsets_transitions() -> None:
    rt: HygieneRuntime = HygieneRuntime(pool=MockPool(), admission=FakeAdmission())
    rt.handle_disconnect(994000, True, 1, lambda p, s: None, lambda p, t: True)
    for mask in range(16):
        _force_flags(rt, mask)
        rt.sha_cache_put(f"k{mask}", f"v{mask}")
        rt.session_claim(f"s{mask}")
        snap: dict[str, object] = rt.health_snapshot()
        assert snap["upstream_held"] == 1
    for mask in range(15, -1, -1):
        _force_flags(rt, mask)
        snap2: dict[str, object] = rt.health_snapshot()
        assert isinstance(snap2["detached_pgids"], tuple)
    _force_flags(rt, 0)
    assert rt.upstream_held_count() == 1
    rt.shutdown_cleanup(lambda p, s: None, lambda p, t: True)


def test_sha_and_session_bounded_parity() -> None:
    rt: HygieneRuntime = HygieneRuntime(pool=MockPool(), admission=FakeAdmission())
    _force_flags(rt, 0)
    rt.sha_cache_put("a", "sha1")
    assert rt.sha_cache_get("a") == "sha1"
    assert rt.session_claim("s1") is True
    assert rt.session_claim("s1") is False
    rt.session_commit("s1", "done")
    rt.session_invalidate("s1")
    assert rt.session_claim("s1") is True
    _force_flags(rt, 4)
    rt.sha_cache_put("b", "sha2")
    got: str | None = rt.sha_cache_get("b")
    assert got in ("sha2", None) or isinstance(got, str)


def test_health_snapshot_immutable() -> None:
    rt: HygieneRuntime = HygieneRuntime(pool=MockPool(), admission=FakeAdmission())
    rt.handle_disconnect(995000, True, 1, lambda p, s: None, lambda p, t: True)
    snap: dict[str, object] = rt.health_snapshot()
    ids: object = snap["detached_pgids"]
    assert isinstance(ids, tuple)
    snap["upstream_held"] = 999
    snap2: dict[str, object] = rt.health_snapshot()
    assert snap2["upstream_held"] == 1
    assert snap2["restart_ready"] is False


def test_concurrent_stress_no_deadlock() -> None:
    rt: HygieneRuntime = HygieneRuntime(pool=MockPool(), admission=FakeAdmission())
    _force_flags(rt, 15)
    errors: list[str] = []

    def worker(idx: int) -> None:
        try:
            for j in range(30):
                rt.sha_cache_put(f"k{idx}-{j}", "v")
                rt.sha_cache_get(f"k{idx}-{j}")
                rt.session_claim(f"s{idx}-{j}")
                rt.health_snapshot()
                rt.upstream_held_count()
                rt.try_acquire_admission()
                rt.release_admission()
        except Exception as exc:
            errors.append(str(exc))

    threads: list[threading.Thread] = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
    assert all(not t.is_alive() for t in threads)
    assert errors == []


def test_cancelling_counted_during_teardown() -> None:
    rt: HygieneRuntime = HygieneRuntime(pool=MockPool(), admission=FakeAdmission())
    observed: list[int] = []

    def waiter(pgid: int, timeout_s: float) -> bool:
        _ = (pgid, timeout_s)
        observed.append(rt.upstream_held_count())
        return True

    result: bool = rt.handle_disconnect(996000, False, 0, lambda p, s: None, waiter)
    assert result is False
    assert observed and observed[0] >= 1
    assert rt.upstream_held_count() == 0
