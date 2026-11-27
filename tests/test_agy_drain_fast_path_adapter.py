"""W3-A: unit-тесты read-only адаптера быстрого выхода из дрена (AD-001/AD-002).

Fail-closed дефолты флага/authoritative_read_done, dynamic_config/env-алиас,
clean-кейсы, нечистые ветки, реальная форма tail, fail-closed, debug-лог ошибок.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

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
    collect_drain_facts,
    is_drain_fast_path_enabled,
    should_drain_fast_exit,
)
from agy_runtime.drain_fast_path_domain import decide_fast_exit  # noqa: E402

_LOGGER_NAME = "agy_runtime.drain_fast_path_adapter"


@pytest.fixture(autouse=True)
def _isolate_flag_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DRAIN_FAST_PATH_ENV, raising=False)
    long_session_config._CACHE.clear()


def _write_config(tmp_path: Path, enabled: bool | None) -> Path:
    path = tmp_path / "dynamic_config.json"
    data: dict[str, Any] = {} if enabled is None else {DRAIN_FAST_PATH_FLAG: enabled}
    path.write_text(json.dumps(data), encoding="utf-8")
    long_session_config._CACHE.clear()
    return path


def _fast(tail: Any, cfg: Path) -> bool:
    return should_drain_fast_exit(tail, cfg, authoritative_read_done=True)


def _clean_tail(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "_proc": SimpleNamespace(returncode=0),
        "_buf": b"",
        "_tool_step_indices": set(),
        "_has_tool_trace": False,
        "_progressive_chunks_emitted": False,
        "_failed": False,
        "_interrupted": False,
        "_stop_event": threading.Event(),
        "_pending_steps": 0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _real_tail(**overrides: Any) -> SimpleNamespace:
    """Реальная форма _TranscriptTail: без выдуманных trace/progressive полей."""
    base: dict[str, Any] = {
        "run_ref": SimpleNamespace(proc=SimpleNamespace(returncode=0)),
        "_buf": b"",
        "_tool_step_indices": set(),
        "emitted": 0,
        "_interrupted": False,
        "failed": False,
        "stop_event": threading.Event(),
        "_pending_steps": lambda: 0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_flag_default_off_even_for_clean_tail(tmp_path: Path) -> None:
    """Дефолт флага False: clean tail не даёт быстрый выход; missing файл — False."""
    cfg = _write_config(tmp_path, None)
    tail = _clean_tail()
    assert is_drain_fast_path_enabled(cfg) is False
    assert is_drain_fast_path_enabled(tmp_path / "missing.json") is False
    assert should_drain_fast_exit(tail, cfg) is False


def test_dynamic_config_enable_and_instant_rollback(tmp_path: Path) -> None:
    """Включение через dynamic_config.json и мгновенный откат на false."""
    tail = _clean_tail()
    cfg = _write_config(tmp_path, True)
    assert is_drain_fast_path_enabled(cfg) is True
    assert _fast(tail, cfg) is True
    cfg = _write_config(tmp_path, False)
    assert is_drain_fast_path_enabled(cfg) is False
    assert _fast(tail, cfg) is False


def test_env_alias_enables_and_overrides_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env-алиас AGY_BRIDGE_DRAIN_FAST_PATH_ENABLED включает и приоритетнее файла."""
    cfg = _write_config(tmp_path, False)
    monkeypatch.setenv(DRAIN_FAST_PATH_ENV, "1")
    assert is_drain_fast_path_enabled(cfg) is True
    assert _fast(_clean_tail(), cfg) is True
    monkeypatch.setenv(DRAIN_FAST_PATH_ENV, "0")
    assert is_drain_fast_path_enabled(_write_config(tmp_path, True)) is False


def test_corrupt_config_fail_closed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Битый JSON и не-путь дают fail-closed False; ошибка чтения — debug-лог %s."""
    path = tmp_path / "dynamic_config.json"
    path.write_text("{not valid json", encoding="utf-8")
    long_session_config._CACHE.clear()
    assert is_drain_fast_path_enabled(path) is False
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        assert is_drain_fast_path_enabled(cast("Any", 123)) is False
    rec = next(r for r in caplog.records if "config read failed" in r.message)
    assert rec.msg == "drain_fast_path config read failed: %s"
    assert isinstance(rec.args[0], Exception)


def test_persistent_clean_turn_ok(tmp_path: Path) -> None:
    """Persistent-режим: _persistent_turn_ok=True решает даже при rc!=0 у proc."""
    cfg = _write_config(tmp_path, True)
    tail = _clean_tail(
        _proc=SimpleNamespace(returncode=1),
        _persistent_mode=True,
        _persistent_turn_ok=True,
    )
    assert _fast(tail, cfg) is True
    dirty = _clean_tail(_persistent_mode=True, _persistent_turn_ok=False)
    assert _fast(dirty, cfg) is False


def test_real_server_field_names_via_run_ref(tmp_path: Path) -> None:
    """Реальные имена server.py: proc/_persistent_* на run_ref, failed/stop_event
    публичные, _pending_steps — метод."""
    cfg = _write_config(tmp_path, True)
    tail = _real_tail()
    assert _fast(tail, cfg) is True
    run = tail.run_ref
    run._persistent_mode = True
    run._persistent_turn_ok = True
    run.proc.returncode = 1
    assert _fast(tail, cfg) is True


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({}, id="clean_real_shape"),
        pytest.param({"emitted": 1}, id="emitted_one"),
        pytest.param({"emitted": True}, id="emitted_bool"),
        pytest.param({"_tool_step_indices": {3}}, id="tool_indices"),
    ],
)
def test_real_tail_fallback_fields(tmp_path: Path, overrides: dict[str, Any]) -> None:
    """RW-003: trace из _tool_step_indices, progressive из emitted (int, не bool)."""
    cfg = _write_config(tmp_path, True)
    assert _fast(_real_tail(**overrides), cfg) is (overrides == {})


def test_real_tail_without_both_fields_fail_closed(tmp_path: Path) -> None:
    """RW-003: нет ни _tool_step_indices, ни emitted (и явных полей) -> fail-closed."""
    cfg = _write_config(tmp_path, True)
    tail = _real_tail()
    del tail.emitted
    del tail._tool_step_indices
    assert _fast(tail, cfg) is False
    facts = collect_drain_facts(tail, flag_enabled=True, authoritative_read_done=True)
    assert facts.has_tool_trace is True
    assert facts.has_progressive_chunks is True


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"_pending_steps": 1}, id="pending_step"),
        pytest.param({"_pending_steps": -1}, id="negative_pending"),
        pytest.param({"_buf": b"event"}, id="buffered_event"),
        pytest.param({"_proc": SimpleNamespace(returncode=1)}, id="rc_1"),
        pytest.param({"_proc": SimpleNamespace(returncode=None)}, id="rc_none"),
        pytest.param({"_proc": None}, id="proc_none"),
        pytest.param({"_has_tool_trace": True}, id="tool_trace"),
        pytest.param({"_tool_step_indices": {3}}, id="tool_indices"),
        pytest.param({"_progressive_chunks_emitted": True}, id="progressive_chunks"),
        pytest.param({"_failed": True}, id="failed"),
        pytest.param({"_interrupted": True}, id="interrupted"),
    ],
)
def test_non_clean_branch_rejects(tmp_path: Path, overrides: dict[str, Any]) -> None:
    """Каждая нечистая ветка по отдельности запрещает быстрый выход."""
    cfg = _write_config(tmp_path, True)
    assert _fast(_clean_tail(**overrides), cfg) is False


def test_stop_event_set_rejects(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, True)
    event = threading.Event()
    event.set()
    assert _fast(_clean_tail(_stop_event=event), cfg) is False


def test_authoritative_read_done_fail_closed_default(tmp_path: Path) -> None:
    """RW-001: дефолт authoritative_read_done=False — без явного True выхода нет."""
    cfg = _write_config(tmp_path, True)
    tail = _clean_tail()
    assert should_drain_fast_exit(tail, cfg) is False
    assert should_drain_fast_exit(tail, cfg, authoritative_read_done=False) is False
    assert should_drain_fast_exit(tail, cfg, authoritative_read_done=True) is True


@pytest.mark.parametrize(
    "field",
    "_proc _buf _tool_step_indices _pending_steps "
    "_progressive_chunks_emitted _failed _interrupted _stop_event".split(),
)
def test_missing_field_fail_closed(tmp_path: Path, field: str) -> None:
    """Отсутствующее поле -> fail-closed False (неизвестное не чисто)."""
    cfg = _write_config(tmp_path, True)
    tail = _clean_tail()
    delattr(tail, field)
    assert _fast(tail, cfg) is False


def test_empty_tail_fail_closed(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, True)
    assert _fast(SimpleNamespace(), cfg) is False
    assert _fast(None, cfg) is False


def test_flag_off_zero_tail_access(tmp_path: Path) -> None:
    """Выключенный флаг: tail не читается вообще (нулевой оверхед)."""

    class _ExplodingTail:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"tail touched: {name}")

    cfg = _write_config(tmp_path, False)
    assert should_drain_fast_exit(_ExplodingTail(), cfg) is False


def test_broken_tail_read_fail_closed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Ошибка чтения атрибута -> fail-closed facts и debug-лог %s, не исключение."""

    class _BrokenTail:
        @property
        def _proc(self) -> Any:
            raise RuntimeError("boom")

    cfg = _write_config(tmp_path, True)
    bt = _BrokenTail()
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        facts = collect_drain_facts(bt, flag_enabled=True, authoritative_read_done=True)
        assert _fast(bt, cfg) is False
    assert decide_fast_exit(facts).should_fast_exit is False
    rec = next(r for r in caplog.records if "fact collection failed" in r.message)
    assert rec.msg == "drain_fast_path fact collection failed: %s"
    assert "boom" in rec.getMessage()


def test_collect_facts_flag_disabled_rejects(tmp_path: Path) -> None:
    """collect_drain_facts с flag_enabled=False не разрешает выход даже для clean."""
    tail = _clean_tail()
    facts = collect_drain_facts(tail, flag_enabled=False, authoritative_read_done=True)
    assert facts.flag_enabled is False
    assert decide_fast_exit(facts).reason == "flag_disabled"


def test_tail_attributes_not_mutated(tmp_path: Path) -> None:
    """Адаптер read-only: ни clean-, ни reject-проход не меняет атрибуты tail."""
    cfg = _write_config(tmp_path, True)
    for overrides in ({}, {"_failed": True}):
        tail = _clean_tail(**overrides)
        before = dict(vars(tail))
        proc_before = dict(vars(tail._proc))
        expected = overrides == {}
        assert _fast(tail, cfg) is expected
        facts = collect_drain_facts(
            tail, flag_enabled=True, authoritative_read_done=True
        )
        assert decide_fast_exit(facts).should_fast_exit is expected
        assert vars(tail) == before
        assert vars(tail._proc) == proc_before
