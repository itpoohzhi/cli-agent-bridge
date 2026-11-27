"""W3-A: unit-тесты read-only адаптера быстрого выхода из дрена (AD-001/AD-002).

Покрывают fail-closed дефолт флага, включение через dynamic_config.json и
env-алиас с мгновенным откатом, cold/persistent clean-кейсы, каждую нечистую
ветку по отдельности, fail-closed на отсутствующие поля, реальные имена полей
``server.py`` (run_ref/публичные failed/stop_event/метод _pending_steps) и
неизменность атрибутов ``tail`` (адаптер не мутирует tail).
"""

from __future__ import annotations

import json
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
    assert should_drain_fast_exit(tail, cfg) is True
    cfg = _write_config(tmp_path, False)
    assert is_drain_fast_path_enabled(cfg) is False
    assert should_drain_fast_exit(tail, cfg) is False


def test_env_alias_enables_and_overrides_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env-алиас AGY_BRIDGE_DRAIN_FAST_PATH_ENABLED включает и приоритетнее файла."""
    cfg = _write_config(tmp_path, False)
    monkeypatch.setenv(DRAIN_FAST_PATH_ENV, "1")
    assert is_drain_fast_path_enabled(cfg) is True
    assert should_drain_fast_exit(_clean_tail(), cfg) is True
    monkeypatch.setenv(DRAIN_FAST_PATH_ENV, "0")
    assert is_drain_fast_path_enabled(_write_config(tmp_path, True)) is False


def test_corrupt_config_fail_closed(tmp_path: Path) -> None:
    """Битый JSON и не-путь дают fail-closed False без исключения."""
    path = tmp_path / "dynamic_config.json"
    path.write_text("{not valid json", encoding="utf-8")
    long_session_config._CACHE.clear()
    assert is_drain_fast_path_enabled(path) is False
    assert is_drain_fast_path_enabled(cast("Any", 123)) is False


def test_cold_clean_returncode_zero(tmp_path: Path) -> None:
    """Cold-режим: returncode=0 и полный набор чистых фактов -> True."""
    cfg = _write_config(tmp_path, True)
    assert should_drain_fast_exit(_clean_tail(), cfg) is True


def test_persistent_clean_turn_ok(tmp_path: Path) -> None:
    """Persistent-режим: _persistent_turn_ok=True решает даже при rc!=0 у proc."""
    cfg = _write_config(tmp_path, True)
    tail = _clean_tail(
        _proc=SimpleNamespace(returncode=1),
        _persistent_mode=True,
        _persistent_turn_ok=True,
    )
    assert should_drain_fast_exit(tail, cfg) is True
    dirty = _clean_tail(_persistent_mode=True, _persistent_turn_ok=False)
    assert should_drain_fast_exit(dirty, cfg) is False


def test_real_server_field_names_via_run_ref(tmp_path: Path) -> None:
    """Реальные имена server.py: proc/_persistent_* на run_ref, failed/stop_event
    публичные, _pending_steps — метод; явные trace-поля добавлены wiring-ом."""
    cfg = _write_config(tmp_path, True)
    run = SimpleNamespace(proc=SimpleNamespace(returncode=0), _persistent_mode=False)
    tail = SimpleNamespace(
        run_ref=run,
        _buf=b"",
        _tool_step_indices=set(),
        _interrupted=False,
        failed=False,
        stop_event=threading.Event(),
        _pending_steps=lambda: 0,
        _has_tool_trace=False,
        _progressive_chunks_emitted=False,
    )
    assert should_drain_fast_exit(tail, cfg) is True
    run._persistent_mode = True
    run._persistent_turn_ok = True
    run.proc.returncode = 1
    assert should_drain_fast_exit(tail, cfg) is True


def test_bare_real_tail_fail_closed_without_trace_fields(tmp_path: Path) -> None:
    """Хвост без _has_tool_trace/_progressive_chunks_emitted — fail-closed False."""
    cfg = _write_config(tmp_path, True)
    run = SimpleNamespace(proc=SimpleNamespace(returncode=0))
    tail = SimpleNamespace(
        run_ref=run,
        _buf=b"",
        _tool_step_indices=set(),
        _interrupted=False,
        failed=False,
        stop_event=threading.Event(),
        _pending_steps=lambda: 0,
    )
    assert should_drain_fast_exit(tail, cfg) is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"_pending_steps": 1},
        {"_pending_steps": -1},
        {"_buf": b"event"},
        {"_proc": SimpleNamespace(returncode=1)},
        {"_proc": SimpleNamespace(returncode=None)},
        {"_proc": None},
        {"_has_tool_trace": True},
        {"_tool_step_indices": {3}},
        {"_progressive_chunks_emitted": True},
        {"_failed": True},
        {"_interrupted": True},
    ],
    ids=[
        "pending_step",
        "negative_pending",
        "buffered_event",
        "rc_1",
        "rc_none",
        "proc_none",
        "tool_trace",
        "tool_indices",
        "progressive_chunks",
        "failed",
        "interrupted",
    ],
)
def test_non_clean_branch_rejects(tmp_path: Path, overrides: dict[str, Any]) -> None:
    """Каждая нечистая ветка по отдельности запрещает быстрый выход."""
    cfg = _write_config(tmp_path, True)
    assert should_drain_fast_exit(_clean_tail(**overrides), cfg) is False


def test_stop_event_set_rejects(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, True)
    event = threading.Event()
    event.set()
    assert should_drain_fast_exit(_clean_tail(_stop_event=event), cfg) is False


def test_authoritative_read_not_done_rejects(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, True)
    tail = _clean_tail()
    assert should_drain_fast_exit(tail, cfg, authoritative_read_done=False) is False


@pytest.mark.parametrize(
    "field",
    [
        "_proc",
        "_buf",
        "_tool_step_indices",
        "_pending_steps",
        "_has_tool_trace",
        "_progressive_chunks_emitted",
        "_failed",
        "_interrupted",
        "_stop_event",
    ],
)
def test_missing_field_fail_closed(tmp_path: Path, field: str) -> None:
    """Любое отсутствующее поле -> fail-closed False (неизвестное не чисто)."""
    cfg = _write_config(tmp_path, True)
    tail = _clean_tail()
    delattr(tail, field)
    assert should_drain_fast_exit(tail, cfg) is False


def test_empty_tail_fail_closed(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, True)
    assert should_drain_fast_exit(SimpleNamespace(), cfg) is False
    assert should_drain_fast_exit(None, cfg) is False


def test_flag_off_zero_tail_access(tmp_path: Path) -> None:
    """Выключенный флаг: tail не читается вообще (нулевой оверхед)."""

    class _ExplodingTail:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"tail touched: {name}")

    cfg = _write_config(tmp_path, False)
    assert should_drain_fast_exit(_ExplodingTail(), cfg) is False


def test_broken_tail_read_fail_closed(tmp_path: Path) -> None:
    """Ошибка чтения атрибута -> fail-closed facts, не исключение наружу."""

    class _BrokenTail:
        @property
        def _proc(self) -> Any:
            raise RuntimeError("boom")

    cfg = _write_config(tmp_path, True)
    facts = collect_drain_facts(
        _BrokenTail(), flag_enabled=True, authoritative_read_done=True
    )
    assert decide_fast_exit(facts).should_fast_exit is False
    assert should_drain_fast_exit(_BrokenTail(), cfg) is False


def test_collect_facts_flag_disabled_rejects(tmp_path: Path) -> None:
    """collect_drain_facts с flag_enabled=False не разрешает выход даже для clean."""
    facts = collect_drain_facts(
        _clean_tail(), flag_enabled=False, authoritative_read_done=True
    )
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
        assert should_drain_fast_exit(tail, cfg) is expected
        facts = collect_drain_facts(
            tail, flag_enabled=True, authoritative_read_done=True
        )
        assert decide_fast_exit(facts).should_fast_exit is expected
        assert vars(tail) == before
        assert vars(tail._proc) == proc_before
