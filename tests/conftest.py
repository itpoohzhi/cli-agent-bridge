"""Global pytest configuration and bridge isolation fixtures.

Guarantees order-invariance and zero state-leak across test execution:
1. Preserves and restores os.environ snapshot per test.
2. Cleans up leaked background asyncio tasks and child processes.
3. Resets bridge singletons (_shutting_down, _budget, LIFECYCLE, _rpc_procs).
4. Defensively avoids importing server during collection phase (zero blast-radius).
5. Detects dirty state leaks in canary/diversion runs (T-ISO-I2 sensitivity).
"""

from __future__ import annotations

import asyncio
import atexit
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Generator

import pytest

# Телеметрия запросов не должна писать в ~/.dsh владельца: БД тестового прогона — во временном каталоге.
_TELEMETRY_TMP = tempfile.mkdtemp(prefix="bridge-telemetry-tests-")
os.environ.setdefault("BRIDGE_TELEMETRY_DB_PATH", os.path.join(_TELEMETRY_TMP, "bridge_telemetry.duckdb"))
atexit.register(shutil.rmtree, _TELEMETRY_TMP, ignore_errors=True)


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for isolation testing."""
    config.addinivalue_line(
        "markers", "strict_leak_check: fail-fast if test leaks singletons or env"
    )


def _get_server_mod() -> Any | None:
    """Return imported server module from sys.modules without forcing import."""
    return sys.modules.get("server")


def _get_agy_bridge_mod() -> Any | None:
    """Return imported agy bridge module from sys.modules if present."""
    return sys.modules.get("agy_bridge_server_under_test")


def _execute_bridge_isolation(
    request: pytest.FixtureRequest | Any,
) -> Generator[None, None, None]:
    """Underlying generator performing bridge isolation snapshot and reset."""
    # --- PHASE 1: Pre-test snapshot ---
    env_snapshot = dict(os.environ)
    sys_path_snapshot = list(sys.path)

    baseline_tasks: set[asyncio.Task[Any]] = set()
    try:
        loop = asyncio.get_running_loop()
        if not loop.is_closed():
            baseline_tasks = {t for t in asyncio.all_tasks(loop) if not t.done()}
    except RuntimeError:
        pass

    srv = _get_server_mod()
    if srv is not None:
        if getattr(srv, "_shutting_down", False):
            srv._shutting_down = False
        if getattr(srv, "_budget", None) is not None:
            srv._budget = None
        if hasattr(srv, "LIFECYCLE") and hasattr(srv.LIFECYCLE, "reset"):
            try:
                srv.LIFECYCLE.reset()
            except Exception:
                pass

    agy_srv = _get_agy_bridge_mod()
    if agy_srv is not None:
        if getattr(agy_srv, "_shutting_down", False):
            agy_srv._shutting_down = False
        if getattr(agy_srv, "_budget", None) is not None:
            agy_srv._budget = None

    # --- PHASE 2: Yield to test execution ---
    yield

    # --- PHASE 3: Post-test audit & leak containment ---
    dirty_reasons: list[str] = []

    # 1. Drain & cancel orphaned asyncio tasks created during the test
    try:
        loop = asyncio.get_running_loop()
        if not loop.is_closed():
            current_tasks = {t for t in asyncio.all_tasks(loop) if not t.done()}
            orphaned = current_tasks - baseline_tasks
            if orphaned:
                dirty_reasons.append(f"leaked_tasks={len(orphaned)}")
            for task in orphaned:
                task.cancel()
    except RuntimeError:
        pass

    # 2. Reset and clean up main server module singletons
    srv = _get_server_mod()
    if srv is not None:
        if getattr(srv, "_shutting_down", False):
            dirty_reasons.append("dirty_singleton=_shutting_down")
        if getattr(srv, "_budget", None) is not None:
            dirty_reasons.append("dirty_singleton=_budget")

        if hasattr(srv, "_rpc_procs") and isinstance(srv._rpc_procs, dict):
            active_lock = getattr(srv, "_active_lock", threading.Lock())
            with active_lock:
                procs = list(srv._rpc_procs.values())
            if procs:
                dirty_reasons.append(f"leaked_rpc_procs={len(procs)}")
            for proc in procs:
                try:
                    if hasattr(proc, "close"):
                        proc.close(mode="term", term_wait=0.1, kill_wait=0.1)
                except Exception:
                    pass
            srv._rpc_procs.clear()

        if hasattr(srv, "_reset_rpc_state"):
            try:
                srv._reset_rpc_state()
            except Exception:
                pass

        srv._shutting_down = False
        srv._budget = None
        if hasattr(srv, "LIFECYCLE") and hasattr(srv.LIFECYCLE, "reset"):
            try:
                srv.LIFECYCLE.reset()
            except Exception:
                pass
        if hasattr(srv, "_active_turns"):
            srv._active_turns = None

    # 3. Reset standalone agy bridge module singletons
    agy_srv = _get_agy_bridge_mod()
    if agy_srv is not None:
        if getattr(agy_srv, "_shutting_down", False):
            dirty_reasons.append("dirty_agy_singleton=_shutting_down")
        if getattr(agy_srv, "_budget", None) is not None:
            dirty_reasons.append("dirty_agy_singleton=_budget")
        if hasattr(agy_srv, "_shutting_down"):
            agy_srv._shutting_down = False
        if hasattr(agy_srv, "_budget"):
            agy_srv._budget = None
        if hasattr(agy_srv, "_rpc_procs") and isinstance(agy_srv._rpc_procs, dict):
            if agy_srv._rpc_procs:
                dirty_reasons.append(f"leaked_agy_procs={len(agy_srv._rpc_procs)}")
            agy_srv._rpc_procs.clear()

    # 4. Audit & restore environment variables exactly
    ignored_env = {"PYTEST_CURRENT_TEST"}
    added_env = (set(os.environ.keys()) - set(env_snapshot.keys())) - ignored_env
    if added_env:
        dirty_reasons.append(f"mutated_env_added={sorted(added_env)}")
    mutated_env = {
        k: (env_snapshot[k], os.environ.get(k))
        for k in env_snapshot
        if os.environ.get(k) != env_snapshot[k] and k not in ignored_env
    }
    if mutated_env:
        dirty_reasons.append(f"mutated_env_changed={sorted(mutated_env.keys())}")

    for key in added_env:
        os.environ.pop(key, None)
    for key, val in env_snapshot.items():
        if os.environ.get(key) != val:
            os.environ[key] = val

    # 5. Restore sys.path to prevent module resolution poisoning across suites
    sys.path[:] = sys_path_snapshot

    # 5. Fail-fast if strict leak checking is active (canary diversion / T-ISO-I2)
    node = getattr(request, "node", None)
    is_strict = (
        os.environ.get("BRIDGE_STRICT_ISOLATION_ASSERT") == "1"
        or (node is not None and node.get_closest_marker("strict_leak_check") is not None)
    )
    if is_strict and dirty_reasons:
        test_name = getattr(node, "nodeid", "unknown_test")
        raise AssertionError(
            f"State leak detected in {test_name}: {'; '.join(dirty_reasons)}"
        )


@pytest.fixture(autouse=True)
def verify_and_reset_bridge_state(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Autouse fixture ensuring pristine state before and after each test."""
    yield from _execute_bridge_isolation(request)


@pytest.fixture(autouse=True)
def _fresh_config_snapshots(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Снимки динамического конфига: пустой кэш и TTL=0 — тест меняет файл и сразу видит значение."""
    from core import runtime_env

    runtime_env._SNAPSHOTS.clear()
    monkeypatch.setattr(runtime_env, "_SNAP_TTL_S", 0.0)
    yield
    runtime_env._SNAPSHOTS.clear()


# --- Телеметрия запросов: общие фикстуры юнит- и HTTP-тестов (чтобы модули тестов остались в лимите M-MOD-I1) ---
TELEMETRY_ENGINES = ("duckdb", "sqlite3")
_TELEMETRY_EVENT_BASE = {
    "request_id": "req-1", "client_ip": "127.0.0.1", "client_port": 5000, "user_agent": "pytest/1.0",
    "http_method": "POST", "endpoint": "/v1/chat/completions", "model": "m-a", "backend_id": "agy",
    "route_mode": "passthrough", "outbound_target": ":9887", "egress_proxy": ":10820 (xray SOCKS5)",
    "stream": False, "status_code": 200, "queue_ms": 1.0, "ttfb_ms": 10.0, "total_ms": 100.0,
    "stream_chunks": 0, "prompt_tokens": 10, "completion_tokens": 5, "cached_tokens": 2, "total_tokens": 15,
    "response_bytes": 512,
}


@pytest.fixture(params=TELEMETRY_ENGINES)
def telemetry_store(request: pytest.FixtureRequest, tmp_path: Path) -> Generator[Any, None, None]:
    """Стор телеметрии на временной БД: duckdb (если доступен) и sqlite3-fallback."""
    from core.request_telemetry import RequestTelemetryStore

    if request.param == "duckdb":
        pytest.importorskip("duckdb")
    store = RequestTelemetryStore(
        str(tmp_path / "telemetry" / "bridge_telemetry.duckdb"),
        force_sqlite=request.param != "duckdb",
        autostart=False,
    )
    assert store.engine == request.param
    yield store
    store.close()


@pytest.fixture
def telemetry_make_store(tmp_path: Path) -> Any:
    """Фабрика стора на временной БД с произвольными настройками очереди/ретенции."""
    from core.request_telemetry import RequestTelemetryStore

    def make(engine: str = "sqlite3", *, name: str = "telemetry", **cfg: Any) -> Any:
        cfg.setdefault("autostart", False)
        store = RequestTelemetryStore(
            str(tmp_path / name / "bridge_telemetry.duckdb"), force_sqlite=engine != "duckdb", **cfg
        )
        assert store.engine == engine
        return store

    return make


@pytest.fixture
def telemetry_event() -> Any:
    """Скалярное событие телеметрии с эталонными полями; любые поля переопределяются аргументом."""

    def event(**over: Any) -> dict[str, Any]:
        return {**_TELEMETRY_EVENT_BASE, **over}

    return event


@pytest.fixture
def telemetry_payload(telemetry_store: Any, telemetry_event: Any) -> tuple[float, dict[str, Any]]:
    """4 записи через горячий путь (503, стрим, сабагент, две модели) и снимок агрегатов за окно."""
    now = time.time()
    events = [
        telemetry_event(request_id="a", total_ms=100.0, ttfb_ms=10.0, ts_epoch=now - 10),
        telemetry_event(request_id="b", total_ms=200.0, ttfb_ms=20.0, ts_epoch=now - 9),
        telemetry_event(
            request_id="c", total_ms=300.0, ttfb_ms=30.0, ts_epoch=now - 8, status_code=503, error_type="overloaded"
        ),
        telemetry_event(
            request_id="d", total_ms=400.0, ttfb_ms=40.0, ts_epoch=now - 7, stream=True, stream_chunks=7, model="m-b",
            backend_id="muse", route_mode="cli", outbound_target=":9886", egress_proxy="direct",
            subagent_id="coder-1", user_agent="claude-cli/2.0",
        ),
    ]
    assert [telemetry_store.record_request(ev) for ev in events] == [True] * 4
    assert telemetry_store.flush() == 4
    return now, telemetry_store.get_telemetry_payload(window_hours=1, limit=10)
