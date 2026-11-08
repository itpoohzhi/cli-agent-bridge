"""Unit tests for StreamMachine coordinator and pure step function (F-FSM-I1..I3)."""


from core.stream_fsm.machine import StreamMachine, step
from core.stream_fsm.types import (
    CancelRequested,
    ChunkReceived,
    EmitChunk,
    EmitSSE,
    RecordMetric,
    StreamState,
    TriggerKillpg,
    UpstreamEOF,
)


def test_pure_step_transitions():
    """Тест чистоты и детерминизма функции step (F-FSM-I1)."""
    state = StreamState.IDLE

    # ChunkReceived переводит IDLE в STREAMING
    state, eff1 = step(state, ChunkReceived(chunk="test", epoch=1))
    assert state == StreamState.STREAMING
    assert eff1 == []

    # CancelRequested переводит в CLOSED и эмитирует TriggerKillpg
    state, eff2 = step(state, CancelRequested(pgid=4242, epoch=2, reason="abort"))
    assert state == StreamState.CLOSED
    assert len(eff2) == 1
    assert isinstance(eff2[0], TriggerKillpg)
    assert eff2[0].pgid == 4242

    # UpstreamEOF переводит в COMPLETED и эмитирует [DONE]
    state_c, eff3 = step(StreamState.STREAMING, UpstreamEOF(epoch=1))
    assert state_c == StreamState.COMPLETED
    assert len(eff3) == 1
    assert isinstance(eff3[0], EmitSSE)
    assert eff3[0].data == "[DONE]"


def test_machine_stale_epoch_rejection():
    """Тест отброса чанков с устаревшим session_epoch (F-FSM-I3)."""
    machine = StreamMachine(session_epoch=5)
    assert machine.feed("stale chunk", epoch=4) == []
    assert machine.feed("current chunk", epoch=5) == [EmitChunk(text="current chunk", is_reasoning=False)]


def test_machine_cancellation_fencing():
    """Тест идемпотентной отмены и защиты от повторных чанков (F-FSM-I3)."""
    machine = StreamMachine(session_epoch=1)
    effects = machine.cancel(pgid=9999, epoch=1, reason="User cancelled")

    assert len(effects) == 1
    assert isinstance(effects[0], TriggerKillpg)
    assert effects[0].pgid == 9999
    assert machine.session_epoch == 2
    assert machine.state == StreamState.CLOSED

    # Все последующие чанки старой эпохи или в закрытом состоянии отбрасываются
    assert machine.feed("ignored", epoch=1) == []
    assert machine.feed("also ignored", epoch=2) == []


def test_machine_utf8_multibyte_stream():
    """Тест корректной склейки многобайтовых символов UTF-8 при байтовом вводе."""
    machine = StreamMachine()
    cyrillic_str = "Тест кириллицы"
    raw_bytes = cyrillic_str.encode("utf-8")

    # Подаем по 1 байту
    collected = []
    for b in raw_bytes:
        effs = machine.feed(bytes([b]))
        for eff in effs:
            if isinstance(eff, EmitChunk):
                collected.append(eff.text)

    # Завершаем поток
    effs_end = machine.finish()
    for eff in effs_end:
        if isinstance(eff, EmitChunk):
            collected.append(eff.text)

    assert "".join(collected) == cyrillic_str


def test_machine_repetition_guard_integration():
    """Тест интеграции RepetitionGuard в StreamMachine с эмиссией метрик и закрытием."""
    machine = StreamMachine(max_repeats=3)
    loop_text = "повтор повтор повтор повтор "
    effects = machine.feed(loop_text)

    assert machine.loop_detected is True
    assert machine.state == StreamState.CLOSED
    has_error_sse = any(isinstance(e, EmitSSE) and e.event == "error" for e in effects)
    has_metric = any(isinstance(e, RecordMetric) and e.name == "repetition_guard_triggered" for e in effects)
    assert has_error_sse is True
    assert has_metric is True
