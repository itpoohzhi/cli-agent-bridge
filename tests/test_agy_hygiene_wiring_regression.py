# ruff: noqa: E402, SLF001

import inspect
import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_ROOT = ROOT / "bridges" / "agy-bridge"
for import_root in (BRIDGE_ROOT, ROOT):
    import_root_str = str(import_root)
    if import_root_str not in sys.path:
        sys.path.insert(0, import_root_str)

try:
    from resilience_wiring_support import load_server
except ImportError:
    from tests.resilience_wiring_support import load_server

from agy_runtime import slot_and_session
from agy_runtime.hygiene_runtime import HygieneRuntime, ManagedSqliteRoPool
from core.adaptive_admission import AdaptiveAdmissionRegistry, AdmissionKey

server = load_server()


class _InnerPool:
    def __init__(self) -> None:
        self.error: BaseException | None = None
        self.release_calls = 0

    def release_thread(self) -> None:
        self.release_calls += 1

    def run_ro(
        self,
        _db_path: Path,
        select_rows: Any,
        *,
        on_conn: Any = None,
    ) -> Any:
        if self.error is not None:
            raise self.error
        if on_conn is not None:
            on_conn(None)
        return select_rows(None)


class _FailingPool:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def run_ro(self, *_args: Any, **_kwargs: Any) -> Any:
        raise self.error


def _poll_tail(tmp_path: Path) -> Any:
    tail = object.__new__(server._TranscriptTail)
    tail._sqlite_permitted = lambda: True
    tail._db_path = tmp_path / "cold.db"
    tail.bucket = SimpleNamespace(take=lambda: True)
    tail._conn_lock = threading.Lock()
    tail._active_conn = None
    tail._select_rows = lambda _conn: (0, 0)
    tail.sqlite_active = True
    tail.stop_event = threading.Event()
    tail._interrupted = False
    tail.selects_ok = 0
    tail.failed = False
    tail._open_fail_logged = False
    tail.cid = "cid123456789"
    return tail


def test_managed_pool_release_thread_keeps_finish_cleanup_reachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inner = _InnerPool()
    pool = ManagedSqliteRoPool(inner)
    breaker_calls: list[tuple[int, int, bool]] = []
    cid_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(server, "_sqlite_ro_pool", lambda: pool)
    monkeypatch.setattr(
        server,
        "_breaker_report",
        lambda generation, selects_ok, failed: breaker_calls.append(
            (generation, selects_ok, failed)
        ),
    )
    monkeypatch.setattr(
        server,
        "_cid_release",
        lambda cid, turn_id: cid_calls.append((cid, turn_id)),
    )

    tail = object.__new__(server._TranscriptTail)
    tail._finished = False
    tail._conn_lock = threading.Lock()
    tail._active_conn = None
    tail.plan = SimpleNamespace(mode="LIVE")
    tail.probe_gen = 1
    tail.selects_ok = 2
    tail.failed = False
    tail._owned_cid = "cid-1"
    tail.turn_id = "turn-1"

    tail._finish()
    tail._finish()

    assert inner.release_calls == 1
    assert breaker_calls == [(1, 2, False)]
    assert cid_calls == [("cid-1", "turn-1")]


def test_cold_wal_wait_does_not_degrade_global_pool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "cold.db"
    db_path.touch()
    assert not Path(f"{db_path}-wal").exists()

    inner = _InnerPool()
    pool = ManagedSqliteRoPool(inner, hygiene_enabled=True)
    inner.error = sqlite3.OperationalError("unable to open database file")

    with pytest.raises(sqlite3.OperationalError, match="unable to open"):
        pool.run_ro(db_path, lambda _conn: (0, 0))

    assert pool.health_tuple()[1] == 0
    assert pool.health_tuple()[2] == 0.0

    monkeypatch.setattr(server, "_sqlite_ro_pool", lambda: pool)
    monkeypatch.setattr(server, "_log", lambda _message: None)
    tail = _poll_tail(tmp_path)

    assert tail._poll_sqlite() is None
    assert tail.sqlite_active is True
    assert pool.health_tuple()[1] == 0
    assert pool.health_tuple()[2] == 0.0

    inner.error = RuntimeError("boom")
    with pytest.raises(RuntimeError) as first_failure:
        pool.run_ro(db_path, lambda _conn: (0, 0))
    assert str(first_failure.value) in {"boom", "sqlite_ro_pool_backoff"}
    assert pool.health_tuple()[1] == 1
    assert pool.health_tuple()[2] > 0.0

    with pytest.raises(RuntimeError, match="^sqlite_ro_pool_backoff$"):
        pool.run_ro(db_path, lambda _conn: (0, 0))


def test_pool_backoff_skips_tick_without_disabling_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(server, "_log", lambda _message: None)

    backoff_pool = _FailingPool(RuntimeError("sqlite_ro_pool_backoff"))
    monkeypatch.setattr(server, "_sqlite_ro_pool", lambda: backoff_pool)
    tail = _poll_tail(tmp_path)

    assert tail._poll_sqlite() is None
    assert tail.last_poll == "skip"
    assert tail.sqlite_active is True

    failing_pool = _FailingPool(RuntimeError("boom"))
    monkeypatch.setattr(server, "_sqlite_ro_pool", lambda: failing_pool)
    tail = _poll_tail(tmp_path)

    assert tail._poll_sqlite() is None
    assert tail.last_poll == "error"
    assert tail.sqlite_active is False


def _admission_key(label: str) -> AdmissionKey:
    kwargs: dict[str, Any] = {}
    parameters = inspect.signature(AdmissionKey).parameters
    for name, parameter in parameters.items():
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if parameter.default is inspect.Parameter.empty:
            kwargs[name] = f"{label}-{name}"
    return AdmissionKey(**kwargs)


def _acquire(
    registry: AdaptiveAdmissionRegistry,
    key: AdmissionKey,
) -> Any:
    kwargs: dict[str, Any] = {}
    parameters = inspect.signature(registry.acquire).parameters
    for index, (name, parameter) in enumerate(parameters.items()):
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        lowered = name.lower()
        if index == 0 or "key" in lowered:
            kwargs[name] = key
        elif "limit" in lowered or "capacity" in lowered:
            kwargs[name] = 8
        elif parameter.default is inspect.Parameter.empty:
            kwargs[name] = 0
    return registry.acquire(**kwargs)


def _bucket_limit(registry: AdaptiveAdmissionRegistry, key: AdmissionKey, now_s: float = 100.0) -> int:
    return dict(registry.health_snapshot(now_s).bucket_limits)[key]


def _release_done(
    registry: AdaptiveAdmissionRegistry,
    decision: Any,
    *,
    started: float,
    first_content_at: float,
    now_s: float = 100.0,
) -> None:
    slot_and_session.release_admission_for_state(
        lambda tid, **kw: registry.release(tid, now_s, **kw),
        decision.ticket_id,
        {"state": "done"},
        run=SimpleNamespace(
            started=started,
            first_content_at=first_content_at,
        ),
    )


def test_run_ttfc_reaches_adaptive_registry_and_blocks_90s_growth() -> None:
    registry = AdaptiveAdmissionRegistry()
    slow_key = _admission_key("slow")

    for i in range(8):
        now_s = 100.0 + i
        decision = registry.acquire(slow_key, now_s)
        assert decision.admitted
        _release_done(
            registry,
            decision,
            started=10.0,
            first_content_at=101.0,
            now_s=now_s + 0.5,
        )
    assert _bucket_limit(registry, slow_key, 110.0) == 8

    fast_key = _admission_key("fast")
    for i in range(8):
        now_s = 200.0 + i
        decision = registry.acquire(fast_key, now_s)
        assert decision.admitted
        _release_done(
            registry,
            decision,
            started=10.0,
            first_content_at=11.0,
            now_s=now_s + 0.5,
        )
    assert _bucket_limit(registry, fast_key, 210.0) == 9

    captured: dict[str, Any] = {}

    def capture_release(*_args: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    slot_and_session.release_admission_for_state(
        capture_release,
        17,
        {"state": "done"},
        run=SimpleNamespace(started=True, first_content_at=11.0),
    )
    assert captured.get("ttfc_ms") is None


class _HookRuntime:
    def __init__(self, touch_hook: Any, release_hook: Any, sweep_hook: Any) -> None:
        self.touch_progress = touch_hook
        self.release_detached = release_hook
        self.sweep_orphans = sweep_hook
        self.shutdown_calls = 0

    def shutdown_cleanup(self) -> int:
        self.shutdown_calls += 1
        return 0


def test_detached_progress_release_and_periodic_reaper_are_wired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    touches: list[int] = []
    releases: list[int] = []
    second_reap = threading.Event()
    reap_calls = 0

    def sweep_hook() -> int:
        nonlocal reap_calls
        reap_calls += 1
        if reap_calls == 1:
            raise RuntimeError("transient reaper failure")
        second_reap.set()
        return 0

    hook_rt = _HookRuntime(
        lambda pgid: touches.append(pgid),
        lambda pgid: (releases.append(pgid) or True),
        sweep_hook,
    )
    monkeypatch.setattr(server, "_HYGIENE_RT", hook_rt)

    reg = server.JobRegistry()
    job, _owner = reg.attach("k-orphan", "gemini-3.8-flash", "prompt")
    job.orphan = True
    job.pgid = 73
    job.ttfc_received = False

    assert reg.publish(job, "text", "chunk") is True
    assert job.ttfc_received is False
    assert touches == [73]

    job.orphan = False
    reg.finish(job, {"state": "done", "text": "ok", "rc": 0})
    assert releases == [73]

    real_rt = HygieneRuntime()
    assert real_rt.handle_disconnect(
        990073, True, 1, lambda _p, _s: None, lambda _p, _t: True
    ) is True
    assert real_rt.upstream_held_count() == 1
    assert real_rt.release_detached(990073) is True
    assert real_rt.upstream_held_count() == 0
    assert real_rt.release_detached(990073) is False

    slot_and_session.start_orphan_reaper(hook_rt, interval_s=0.01)
    try:
        assert second_reap.wait(1.0)
        assert reap_calls >= 2
    finally:
        slot_and_session.shutdown_hygiene_runtime(hook_rt)
    assert hook_rt.shutdown_calls == 1


class _LegacyRuntime:
    pass


def test_optional_orphan_hooks_accept_legacy_fake_runtime() -> None:
    runtime = _LegacyRuntime()
    slot_and_session.notify_orphan_progress(runtime, 123)
    assert slot_and_session.release_detached_pgid(runtime, 123) is False
    slot_and_session.start_orphan_reaper(runtime, interval_s=0.01)
    slot_and_session.shutdown_hygiene_runtime(runtime)
