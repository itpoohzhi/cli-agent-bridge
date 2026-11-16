"""L1: загрузчик `load_bridge` отдаёт изолированные копии настоящего Claude-моста.

Неизменяемый код-объект `server.py` общий, а модуль, классы, очереди и блокировки
создаются заново при каждой загрузке; откат `sys.modules` и `sys.path` проверяется
на управляемом контексте `MonkeyPatch`.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from tests.unit._claude_bridge_tool_fakes import BRIDGE_SERVER, load_bridge

MUTABLE_GLOBALS = ("_active", "_active_lock", "_slots", "_LIFECYCLE")
MUTABLE_CLASSES = ("Handler", "_Execution", "_Callbacks")
NAME_PREFIX = "claude_p_bridge_inmem"


@pytest.fixture
def twins(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
    return load_bridge(monkeypatch), load_bridge(monkeypatch)


def _bridge_modules() -> list[str]:
    return [name for name in sys.modules if name.startswith(NAME_PREFIX)]


def test_loads_get_distinct_modules_classes_and_state(twins: tuple[Any, Any]) -> None:
    first, second = twins
    assert first is not second
    assert first.__name__ != second.__name__
    assert first.__file__ == second.__file__ == str(BRIDGE_SERVER)
    for name in (*MUTABLE_GLOBALS, *MUTABLE_CLASSES):
        assert getattr(first, name) is not getattr(second, name), name
    assert first.Handler.__module__ == first.__name__
    assert second.Handler.__module__ == second.__name__


def test_mutating_one_load_does_not_affect_the_other(twins: tuple[Any, Any]) -> None:
    first, second = twins
    first._active[1234] = object()
    first.Handler.marker = "first"
    first.AUTH_KEY = "mutated"
    with first._active_lock:
        assert second._active_lock.acquire(blocking=False)
        second._active_lock.release()
    assert second._active == {}
    assert not hasattr(second.Handler, "marker")
    assert second.AUTH_KEY != "mutated"


def test_shared_code_never_shares_function_globals(twins: tuple[Any, Any]) -> None:
    first, second = twins
    first_send, second_send = first.Handler._send, second.Handler._send
    assert first_send is not second_send
    assert first_send.__code__ is second_send.__code__
    assert first_send.__globals__ is first.__dict__
    assert second_send.__globals__ is second.__dict__
    assert first_send.__globals__ is not second_send.__globals__


def test_exit_of_patch_context_rolls_back_modules_and_path() -> None:
    modules_before = set(_bridge_modules())
    path_before = list(sys.path)
    path_object = sys.path
    with pytest.MonkeyPatch.context() as patch:
        module = load_bridge(patch)
        sys.path.append("/nonexistent/bridge-isolation-probe")
        assert sys.modules[module.__name__] is module
        assert sys.path is not path_object
    assert module.__name__ not in sys.modules
    assert set(_bridge_modules()) == modules_before
    assert sys.path is path_object
    assert sys.path == path_before
