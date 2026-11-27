"""W3-B: интеграционные тесты fast_clean-выхода из дрена в монолите agy-bridge.

Реальный ``_TranscriptTail._drain_post_eof()`` с делегирующим фасадом AD-002
(``should_drain_fast_exit``): флаг false (дефолт) не меняет поведение и длительность,
флаг true даёт мгновенный ``exit=fast_clean`` на чистом ходе (с end_marker и без),
нечистые ветки сохраняют полный drain и доставку событий, откат true -> false
возвращает штатный drain. PR #135 ``fast_complete_drain`` при false не ломается.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = _ROOT / "bridges" / "agy-bridge"
if str(BRIDGE_DIR) not in sys.path:
    sys.path.append(str(BRIDGE_DIR))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agy_runtime import long_session_config  # noqa: E402
from agy_runtime.drain_fast_path_adapter import (  # noqa: E402
    DRAIN_FAST_PATH_ENV,
    DRAIN_FAST_PATH_FLAG,
)


@pytest.fixture(autouse=True)
def _isolate_flag_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DRAIN_FAST_PATH_ENV, raising=False)
    long_session_config._CACHE.clear()


def _load_server() -> ModuleType:
    name = "agy_bridge_server_drain_fast_path_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BRIDGE_DIR / "server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_flag(tmp_path: Path, enabled: bool | None) -> Path:
    path = tmp_path / "dynamic_config.json"
    data: dict[str, Any] = {} if enabled is None else {DRAIN_FAST_PATH_FLAG: enabled}
    path.write_text(json.dumps(data), encoding="utf-8")
    long_session_config._CACHE.clear()
    return path


def _make_tail(
    srv: Any, overrides: dict[str, Any] | None = None, window_s: float = 0.20
) -> Any:
    """Реальный класс tail без I/O: чистый ход, все поля AD-002 явно выставлены."""
    tail = object.__new__(srv._TranscriptTail)
    tail.stop_event = threading.Event()
    tail.sqlite_active = False
    tail.emitted = 0
    tail.end_marker = False
    tail.final_planner = True
    tail.drain_deadline = time.monotonic() + window_s
    tail.fast_complete_drain = False
    tail.fast_drain_min_s = 0.015
    tail.drain_outcome = ""
    tail.run_ref = SimpleNamespace(proc=SimpleNamespace(returncode=0))
    tail._buf = b""
    tail._tool_step_indices = set()
    tail._has_tool_trace = False
    tail._progressive_chunks_emitted = False
    tail.failed = False
    tail._interrupted = False
    tail._read_transcript = lambda: None
    tail._poll_sqlite = lambda: (0, 0)
    tail._pending_steps = lambda: 0
    tail._cid8 = lambda: "drainfb1"
    for key, value in (overrides or {}).items():
        setattr(tail, key, value)
    return tail


def _run_drain(
    srv: Any, tail: Any, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, float]:
    """Прогон реального _drain_post_eof; exit_kind из строки лога и длительность."""
    lines: list[str] = []
    monkeypatch.setattr(srv, "_log", lines.append)
    started = time.monotonic()
    tail._drain_post_eof()
    elapsed = time.monotonic() - started
    drain = [msg for msg in lines if msg.startswith("drain ")]
    assert len(drain) == 1, f"ожидалась одна строка drain-лога: {lines}"
    return drain[0].split("exit=")[1].split()[0], elapsed


def _enable(
    monkeypatch: pytest.MonkeyPatch, srv: Any, tmp_path: Path, enabled: bool | None
) -> None:
    cfg = _write_flag(tmp_path, enabled)
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)


def test_flag_off_default_keeps_stock_drain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_server()
    _enable(monkeypatch, srv, tmp_path, None)
    tail = _make_tail(srv, window_s=0.15)
    exit_kind, elapsed = _run_drain(srv, tail, monkeypatch)
    assert exit_kind == "window"
    assert elapsed >= 0.13
    assert tail.drain_outcome == "complete"


def test_flag_off_end_marker_still_exits_end_turn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_server()
    _enable(monkeypatch, srv, tmp_path, False)
    tail = _make_tail(srv, {"end_marker": True}, window_s=0.35)
    exit_kind, elapsed = _run_drain(srv, tail, monkeypatch)
    assert exit_kind == "end_turn"
    assert elapsed >= srv.DRAIN_MIN_S - 0.02


def test_flag_off_pr135_fast_complete_drain_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_server()
    _enable(monkeypatch, srv, tmp_path, False)
    tail = _make_tail(srv, {"fast_complete_drain": True}, window_s=0.35)
    exit_kind, elapsed = _run_drain(srv, tail, monkeypatch)
    assert exit_kind == "fast_complete"
    assert elapsed < 0.15
    assert tail.drain_outcome == "complete"


def test_flag_on_clean_with_end_marker_fast_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_server()
    _enable(monkeypatch, srv, tmp_path, True)
    tail = _make_tail(srv, {"end_marker": True}, window_s=0.35)
    exit_kind, elapsed = _run_drain(srv, tail, monkeypatch)
    assert exit_kind == "fast_clean"
    assert elapsed < 0.10
    assert tail.drain_outcome == "complete"


def test_flag_on_clean_without_end_marker_fast_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_server()
    _enable(monkeypatch, srv, tmp_path, True)
    tail = _make_tail(srv, window_s=0.15)
    exit_kind, elapsed = _run_drain(srv, tail, monkeypatch)
    assert exit_kind == "fast_clean"
    assert elapsed < 0.10
    assert tail.drain_outcome == "complete"


def _stopped_event() -> threading.Event:
    event = threading.Event()
    event.set()
    return event


_NONCLEAN_CASES = [
    ({"run_ref": SimpleNamespace(proc=SimpleNamespace(returncode=1))}, "window"),
    ({"_pending_steps": lambda: 1}, "window"),
    ({"_buf": b"event"}, "window"),
    ({"_has_tool_trace": True}, "window"),
    ({"_progressive_chunks_emitted": True}, "window"),
    ({"stop_event": _stopped_event()}, "stop"),
]
_NONCLEAN_IDS = [
    "rc_nonzero",
    "pending_steps",
    "buffered_event",
    "tool_trace",
    "progressive_chunks",
    "stop_event",
]


@pytest.mark.parametrize(("overrides", "expected"), _NONCLEAN_CASES, ids=_NONCLEAN_IDS)
def test_flag_on_nonclean_keeps_full_drain(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    overrides: dict[str, Any],
    expected: str,
) -> None:
    srv = _load_server()
    _enable(monkeypatch, srv, tmp_path, True)
    tail = _make_tail(srv, overrides, window_s=0.12)
    exit_kind, elapsed = _run_drain(srv, tail, monkeypatch)
    assert exit_kind == expected
    assert exit_kind != "fast_clean"
    if expected == "window":
        assert elapsed >= 0.10


def test_flag_on_buffered_event_still_delivered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_server()
    _enable(monkeypatch, srv, tmp_path, True)
    tail = _make_tail(srv, {"_buf": b"event"}, window_s=0.15)
    state = {"done": False}

    def _read_once() -> None:
        if not state["done"]:
            state["done"] = True
            tail.emitted += 1

    tail._read_transcript = _read_once
    exit_kind, elapsed = _run_drain(srv, tail, monkeypatch)
    assert exit_kind == "window"
    assert tail.emitted == 1
    assert elapsed >= 0.13


def test_rollback_true_to_false_restores_stock_drain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_server()
    _enable(monkeypatch, srv, tmp_path, True)
    kind_on, elapsed_on = _run_drain(srv, _make_tail(srv, window_s=0.15), monkeypatch)
    assert kind_on == "fast_clean"
    assert elapsed_on < 0.10
    _write_flag(tmp_path, False)
    kind_off, elapsed_off = _run_drain(srv, _make_tail(srv, window_s=0.15), monkeypatch)
    assert kind_off == "window"
    assert elapsed_off >= 0.13
    _write_flag(tmp_path, True)
    kind_back, _ = _run_drain(srv, _make_tail(srv, window_s=0.15), monkeypatch)
    assert kind_back == "fast_clean"
