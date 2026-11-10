"""F-FSM-I3: Test suite for stream cancellation and session_epoch fencing."""


from core.stream_fsm.machine import StreamMachine
from core.stream_fsm.types import (
    EmitChunk,
    StreamState,
    TriggerKillpg,
)


def test_cancellation_emits_trigger_killpg():
    """Проверка генерации TriggerKillpg при вызове cancel()."""
    machine = StreamMachine(session_epoch=1)
    effects = machine.cancel(pgid=5555, epoch=1, reason="Client closed tab")

    assert len(effects) == 1
    eff = effects[0]
    assert isinstance(eff, TriggerKillpg)
    assert eff.pgid == 5555
    assert eff.epoch == 2
    assert machine.session_epoch == 2
    assert machine.state == StreamState.CLOSED


def test_cancellation_epoch_fencing_drops_stale_chunks():
    """Проверка отброса всех чанков со старым session_epoch после отмены."""
    machine = StreamMachine(session_epoch=1)
    # Нормальный чанк активной эпохи
    eff1 = machine.feed("chunk-epoch-1", epoch=1)
    assert len(eff1) == 1

    # Отмена сессии
    machine.cancel(pgid=1234, epoch=1, reason="Abort")

    # Чанки старой эпохи 1 отбрасываются
    eff_stale1 = machine.feed("stale-1", epoch=1)
    assert eff_stale1 == []

    # Чанки в закрытом состоянии даже с новой эпохой отбрасываются до сброса
    eff_closed = machine.feed("during-closed", epoch=2)
    assert eff_closed == []


def test_machine_reset_allows_new_epoch_execution():
    """Проверка возобновления работы FSM после сброса с новой эпохой."""
    machine = StreamMachine(session_epoch=1)
    machine.cancel(pgid=1000, epoch=1)
    assert machine.state == StreamState.CLOSED

    # Новый ход с epoch=3
    machine.reset(new_epoch=3)
    assert machine.state == StreamState.IDLE
    assert machine.session_epoch == 3

    # Старая эпоха 2 всё еще отклоняется
    assert machine.feed("old", epoch=2) == []

    # Новая эпоха 3 принимается
    eff_new = machine.feed("fresh data", epoch=3)
    assert eff_new == [EmitChunk(text="fresh data", is_reasoning=False)]
