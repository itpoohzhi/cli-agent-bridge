"""Global pytest configuration and bridge isolation fixtures.

T-ISO-I2: шесть доменов guard'а (GUARD_DOMAINS) на общем session-loop: threads, unfinished async tasks,
sockets, descriptors, environment, module singletons/caches. В дельте только имена env, без значений.
Утечка роняет тест в strict-режиме (BRIDGE_STRICT_ISOLATION_ASSERT=1 или маркер strict_leak_check).
"""

from __future__ import annotations

import asyncio
import atexit
import gc
import hashlib
import os
import shutil
import socket
import stat
import sys
import tempfile
import threading
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Generator

import pytest
import pytest_asyncio

# Телеметрия запросов не должна писать в ~/.dsh владельца: БД тестового прогона — во временном каталоге.
_TELEMETRY_TMP = tempfile.mkdtemp(prefix="bridge-telemetry-tests-")
os.environ.setdefault("BRIDGE_TELEMETRY_DB_PATH", os.path.join(_TELEMETRY_TMP, "bridge_telemetry.duckdb"))
atexit.register(shutil.rmtree, _TELEMETRY_TMP, ignore_errors=True)

GUARD_DOMAINS = ("threads", "async_tasks", "sockets", "descriptors", "environment", "singletons")
_IGNORED_ENV = frozenset({"PYTEST_CURRENT_TEST"})
_WARM = {"done": False}


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for isolation testing."""
    config.addinivalue_line("markers", "strict_leak_check: fail-fast if test leaks singletons, env or resources")


def _is_strict(node: Any) -> bool:
    marker = node.get_closest_marker("strict_leak_check") if node is not None else None
    return os.environ.get("BRIDGE_STRICT_ISOLATION_ASSERT") == "1" or marker is not None


def _env_digests() -> dict[str, str]:
    """key -> sha256(value); surrogateescape: не-UTF-8 значения окружения не роняют guard."""
    return {k: hashlib.sha256(v.encode("utf-8", "surrogateescape")).hexdigest() for k, v in os.environ.items()
            if k not in _IGNORED_ENV}


def _fd_numbers() -> frozenset[int]:
    """Открытые дескрипторы процесса (без дескриптора самого листинга)."""
    for root in ("/dev/fd", "/proc/self/fd"):
        try:
            handle = os.open(root, os.O_RDONLY)
        except OSError:
            continue
        try:
            return frozenset(int(name) for name in os.listdir(handle)) - {handle}
        finally:
            os.close(handle)
    return frozenset()


def _is_socket(fd: int) -> bool:
    try:
        return stat.S_ISSOCK(os.fstat(fd).st_mode)
    except OSError:
        return False


def _live_tasks() -> frozenset[Any]:
    try:
        return frozenset(t for t in asyncio.all_tasks() if not t.done())
    except RuntimeError:
        return frozenset()


def _snapshot() -> dict[str, Any]:
    return {"threads": frozenset(threading.enumerate()), "fds": _fd_numbers(), "tasks": _live_tasks(),
            "env": _env_digests(), "env_raw": dict(os.environ), "path": list(sys.path)}


def _leaks(base: dict[str, Any]) -> list[str]:
    """Дельта доменов threads/async_tasks/sockets/descriptors/environment к baseline (без значений env)."""
    new_fds = _fd_numbers() - base["fds"]
    if new_fds:
        gc.collect()  # дескрипторы, ещё удерживаемые циклическим мусором, утечкой не считаются
        new_fds = _fd_numbers() - base["fds"]
    socks = {fd for fd in new_fds if _is_socket(fd)}
    env = _env_digests()
    found: dict[str, Any] = {
        "threads": sorted(t.name for t in threading.enumerate() if t not in base["threads"] and t.is_alive()),
        "async_tasks": len(_live_tasks() - base["tasks"] - {asyncio.current_task()}),
        "sockets": len(socks),
        "descriptors": len(new_fds - socks),
        "environment": sorted(k for k in env.keys() | base["env"].keys() if env.get(k) != base["env"].get(k)),
    }
    return [f"{domain}={value}" for domain, value in found.items() if value]


async def _warm_runtime_once() -> None:
    """Один прогрев loop и default executor до copied baseline: их поток не считается утечкой."""
    if not _WARM["done"]:
        await asyncio.get_running_loop().run_in_executor(None, hash, "warm")
        socket.getfqdn("127.0.0.1")  # server_bind: resolver лениво открывает process-wide unix-сокет
        _WARM["done"] = True


def _reset_flags(mod: Any, tag: str, full: bool, dirty: list[str]) -> None:
    """Флаги `_shutting_down`/`_budget` модуля: при full — записать грязное, затем вернуть чистое."""
    for attr, clean in (("_shutting_down", False), ("_budget", None)):
        if full and getattr(mod, attr, clean) != clean:
            dirty.append(f"dirty_{tag}singleton={attr}")
        if not tag or hasattr(mod, attr):
            setattr(mod, attr, clean)


def _drain_procs(mod: Any, tag: str, dirty: list[str]) -> None:
    """RPC-процессы модуля: записать утечку, закрыть процессы сервера, очистить реестр."""
    procs = getattr(mod, "_rpc_procs", None)
    if not isinstance(procs, dict):
        return
    with getattr(mod, "_active_lock", threading.Lock()):
        held = list(procs.values())
    if held:
        dirty.append(f"leaked_{tag or 'rpc_'}procs={len(held)}")
    for proc in held if not tag else ():
        try:
            proc.close(mode="term", term_wait=0.1, kill_wait=0.1)
        except Exception:
            pass
    procs.clear()


def _run_hooks(mod: Any, full: bool) -> None:
    """Сброс LIFECYCLE и (при full) RPC-состояния; сбой хука не ломает guard."""
    hooks = [getattr(getattr(mod, "LIFECYCLE", None), "reset", None)]
    hooks += [getattr(mod, "_reset_rpc_state", None)] * full
    for hook in filter(callable, hooks):
        try:
            hook()
        except Exception:
            pass


def _reset_singletons(full: bool, dirty: list[str]) -> None:
    """Домен module singletons/caches: сбросить синглтоны моста; при full — записать грязное состояние."""
    for mod in (sys.modules.get("server"), sys.modules.get("agy_bridge_server_under_test")):
        if mod is None:
            continue
        tag = "" if mod.__name__ == "server" else "agy_"
        _reset_flags(mod, tag, full, dirty)
        if full:
            _drain_procs(mod, tag, dirty)
        _run_hooks(mod, full)
        if full and not tag and hasattr(mod, "_active_turns"):
            mod._active_turns = None


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def async_leak_guard(request: pytest.FixtureRequest) -> AsyncGenerator[None, None]:
    """Шестидоменный guard на общем session-loop: warmup, baseline, дельта после teardown и monkeypatch undo."""
    await _warm_runtime_once()
    base = _snapshot()
    yield
    for task in _live_tasks() - base["tasks"] - {asyncio.current_task()}:
        task.cancel()
    dirty = _leaks(base)
    for key in (set(os.environ) | set(base["env_raw"])) - _IGNORED_ENV:
        if key in base["env_raw"]:
            os.environ[key] = base["env_raw"][key]
        else:
            os.environ.pop(key, None)
    sys.path[:] = base["path"]
    if dirty and _is_strict(getattr(request, "node", None)):
        raise AssertionError(f"State leak detected in {request.node.nodeid}: {'; '.join(dirty)}")


@pytest.fixture(autouse=True)
def guarded_monkeypatch(verify_and_reset_bridge_state: None, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """monkeypatch откатывается раньше аудита окружения и async-guard: те сравнивают состояние уже после undo."""
    yield
    monkeypatch.undo()


def _execute_bridge_isolation(request: Any) -> Generator[None, None, None]:
    """Синглтоны моста, окружение и sys.path: чистое состояние до теста; после — аудит, откат и (в strict) отказ."""
    env_before, path_before = dict(os.environ), list(sys.path)
    _reset_singletons(False, [])
    yield
    dirty: list[str] = []
    _reset_singletons(True, dirty)
    added = sorted((set(os.environ) - set(env_before)) - _IGNORED_ENV)
    changed = sorted(k for k, v in env_before.items() if k not in _IGNORED_ENV and os.environ.get(k) != v)
    dirty += [f"mutated_env_{label}={keys}" for label, keys in (("added", added), ("changed", changed)) if keys]
    for key in added:
        os.environ.pop(key, None)
    os.environ.update({k: env_before[k] for k in changed})
    sys.path[:] = path_before
    node = getattr(request, "node", None)
    if dirty and _is_strict(node):
        raise AssertionError(f"State leak detected in {getattr(node, 'nodeid', 'unknown_test')}: {'; '.join(dirty)}")


@pytest.fixture(autouse=True)
def verify_and_reset_bridge_state(async_leak_guard: None, request: pytest.FixtureRequest) -> Generator[None, None, None]:
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
    db = str(tmp_path / "telemetry" / "bridge_telemetry.duckdb")
    store = RequestTelemetryStore(db, force_sqlite=request.param != "duckdb", autostart=False, enabled=True)
    assert store.ensure_open() and store.engine == request.param
    yield store
    store.close()


@pytest.fixture
def telemetry_make_store(tmp_path: Path) -> Any:
    """Фабрика стора на временной БД с произвольными настройками очереди/ретенции."""
    from core.request_telemetry import RequestTelemetryStore

    def make(engine: str = "sqlite3", *, name: str = "telemetry", **cfg: Any) -> Any:
        cfg.setdefault("autostart", False)
        cfg.setdefault("enabled", True)
        store = RequestTelemetryStore(str(tmp_path / name / "bridge_telemetry.duckdb"), force_sqlite=engine != "duckdb", **cfg)
        assert store.ensure_open() and store.engine == engine
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
        telemetry_event(request_id="c", total_ms=300.0, ttfb_ms=30.0, ts_epoch=now - 8, status_code=503, error_type="overloaded"),
        telemetry_event(
            request_id="d", total_ms=400.0, ttfb_ms=40.0, ts_epoch=now - 7, stream=True, stream_chunks=7, model="m-b",
            backend_id="muse", route_mode="cli", outbound_target=":9886", egress_proxy="direct",
            subagent_id="coder-1", user_agent="claude-cli/2.0",
        ),
    ]
    assert [telemetry_store.record_request(ev) for ev in events] == [True] * 4
    assert telemetry_store.flush() == 4
    return now, telemetry_store.get_telemetry_payload(window_hours=1, limit=10)
