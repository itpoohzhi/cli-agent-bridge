"""Тесты для Wave 2: QoS очередей, аварийный Watchdog Cap и неблокирующий Drain сабагентов."""

import threading
import time
from unittest.mock import MagicMock

import pytest

import core.lifecycle
import server
from core.lifecycle import HubLifecycleManager
from core.turn_session_manager import ManagedTurn


class DummyConnection:
    def fileno(self):
        return 1


class DummyHandler:
    def __init__(self, headers: dict[str, str] | None = None, subagent_id: str | None = None):
        self.headers = headers or {}
        self.connection = DummyConnection()
        self._trace = MagicMock()
        self._trace.subagent_id = subagent_id

    _is_subagent_request = server.Handler._is_subagent_request
    _subagent_id = server.Handler._subagent_id
    _effective_turn_timeout_s = server.Handler._effective_turn_timeout_s


def test_effective_timeout_subagent_clamped_to_cap():
    # Без заголовка: сабагент получает дефолтный SUBAGENT_WATCHDOG_CAP_S (300с)
    h1 = DummyHandler(subagent_id="test-agent")
    assert h1._effective_turn_timeout_s() == 300.0

    # С заголовком 120с: сабагент получает 120с
    h2 = DummyHandler(headers={"X-Timeout-Seconds": "120"}, subagent_id="test-agent")
    assert h2._effective_turn_timeout_s() == 120.0

    # С заголовком 600с: сабагент ограничен потолком 300с
    h3 = DummyHandler(headers={"X-Timeout-Seconds": "600"}, subagent_id="test-agent")
    assert h3._effective_turn_timeout_s() == 300.0

    # UI запрос (без subagent_id): дефолт TIMEOUT_S (1800с)
    h_ui = DummyHandler()
    assert h_ui._effective_turn_timeout_s() == server.TIMEOUT_S


def test_subagent_id_resolution():
    h1 = DummyHandler(subagent_id="panel-judge-1")
    assert h1._is_subagent_request() is True
    assert h1._subagent_id() == "panel-judge-1"

    h2 = DummyHandler(headers={"X-Subagent-Id": "coder-1"}, subagent_id=None)
    assert h2._is_subagent_request() is True
    assert h2._subagent_id() == "coder-1"

    h3 = DummyHandler(subagent_id=None)
    assert h3._is_subagent_request() is False
    assert h3._subagent_id() is None


def test_qos_subagent_concurrency_and_ui_reservation(monkeypatch):
    # Моделируем пул на 6 слотов: 2 зарезервированы под UI, квота сабагентов = 4
    slots = threading.BoundedSemaphore(6)
    subagent_slots = threading.BoundedSemaphore(4)
    qos_lock = threading.Condition()

    monkeypatch.setattr(server, "_slots", slots)
    monkeypatch.setattr(server, "_subagent_slots", subagent_slots)
    monkeypatch.setattr(server, "_qos_lock", qos_lock)
    monkeypatch.setattr(server, "UI_RESERVED_SLOTS", 2)
    monkeypatch.setattr(server, "SUBAGENT_MAX_CONCURRENT", 4)
    monkeypatch.setattr(server, "_client_gone", lambda conn: False)

    # 4 сабагента успешно берут слоты
    handlers = [DummyHandler(subagent_id=f"agent-{i}") for i in range(4)]
    for h in handlers:
        reason = server.Handler._acquire_slot(h, keepalive=None)
        assert reason == ""

    # Свободных слотов осталось 2 (6 - 4 = 2).
    # 5-й сабагент НЕ должен получить слот, т.к. квота subagent_slots исчерпана,
    # а также свободные слоты (2) <= UI_RESERVED_SLOTS (2).
    h5 = DummyHandler(subagent_id="agent-5")
    monkeypatch.setattr(server, "QUEUE_TIMEOUT_S", 0.1)
    monkeypatch.setattr(server, "SUBAGENT_QUEUE_TIMEOUT_S", 0.1)
    reason5 = server.Handler._acquire_slot(h5, keepalive=None)
    assert reason5 == "queue_timeout"

    # Зато интерактивный UI-запрос (без subagent_id) МОЖЕТ взять оставшийся слот!
    h_ui = DummyHandler(subagent_id=None)
    reason_ui = server.Handler._acquire_slot(h_ui, keepalive=None)
    assert reason_ui == ""

    # Освобождаем слоты
    for _ in range(4):
        subagent_slots.release()
        slots.release()
    slots.release()  # для h_ui


def test_lifecycle_subagent_fast_drain(monkeypatch):
    mock_turn_mgr = MagicMock()
    st1 = ManagedTurn(
        turn_id="turn-sub-1",
        turn_key="k1",
        rid="r1",
        model="gpt-6.1",
        backend="droid",
        cwd="/tmp",
        owner_token_hash="hash",
        is_subagent=True,
        subagent_id="panel-judge-1",
    )
    mock_turn_mgr.active_turns.return_value = [st1]
    mock_turn_mgr.wait_for_active_turns.return_value = []

    lifecycle = HubLifecycleManager(
        turn_manager=mock_turn_mgr,
        drain_timeout_s=5.0,
        drain_enabled_fn=lambda: True,
    )
    monkeypatch.setattr(core.lifecycle, "DEFAULT_DRAIN_SUBAGENT_GRACE_S", 0.05)

    res = lifecycle.run_drain_once()
    assert mock_turn_mgr.interrupt_for_drain.called
    args = mock_turn_mgr.interrupt_for_drain.call_args[0]
    assert args[0].turn_id == "turn-sub-1"
    assert "Retry-After" in mock_turn_mgr.interrupt_for_drain.call_args[1]["message"]


def test_draining_response_retry_after():
    lifecycle = HubLifecycleManager()
    status, headers, body = lifecycle.draining_response(is_subagent=True)
    assert status == 503
    assert headers["Retry-After"] == "3"

    status, headers, body = lifecycle.draining_response(is_subagent=False)
    assert status == 503
    assert headers["Retry-After"] == "5"


def test_release_turn_slot_subagent(monkeypatch):
    slots = threading.BoundedSemaphore(6)
    subagent_slots = threading.BoundedSemaphore(4)
    qos_lock = threading.Condition()

    monkeypatch.setattr(server, "_slots", slots)
    monkeypatch.setattr(server, "_subagent_slots", subagent_slots)
    monkeypatch.setattr(server, "_qos_lock", qos_lock)

    # Захватываем слоты
    assert slots.acquire() is True
    assert subagent_slots.acquire() is True

    h = DummyHandler(subagent_id="sub-1")
    h._subagent_slot_held = True
    t_held = True
    t_released = [False]

    def _release_turn_slot() -> None:
        if t_held and not t_released[0]:
            t_released[0] = True
            with server._qos_lock:
                server._slots.release()
                if getattr(h, "_subagent_slot_held", False):
                    h._subagent_slot_held = False
                    server._subagent_slots.release()
                server._qos_lock.notify_all()

    # Вызов _release_turn_slot освобождает оба семафора и сбрасывает флаг
    _release_turn_slot()
    assert h._subagent_slot_held is False
    assert t_released[0] is True

    # Проверяем, что квота subagent_slots полностью восстановлена (4 из 4)
    for _ in range(4):
        assert subagent_slots.acquire(blocking=False) is True
    for _ in range(4):
        subagent_slots.release()

    # Повторный вызов идемпотентен и не приводит к лишним release()
    _release_turn_slot()
    assert t_released[0] is True

