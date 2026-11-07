"""Скользящее окно активности `PassthroughAdapter` для `stream=True` (AGENTS.md, L2).

Корень: дедлайн запроса — неизменяемый `float` (`now + total_timeout_s`, 420 с): сторожевой
поток `passthrough-deadline` рвал сокет ровно по нему, даже когда upstream непрерывно слал
полезные чанки. L1 — чистый КА `core.passthrough_sliding_window`; L2 — реальный upstream.
"""

from __future__ import annotations

import ast
import importlib
import io
import json
import random
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from adapters.passthrough_adapter import PassthroughLimits, iter_sse_events
from core.liveness_signals import SIGNAL_S, classify_sse_data
from tests.test_passthrough_adapter import (
    DONE,
    CollectSink,
    FakeUpstream,
    content,
    finish,
    make_adapter,
)

REPO = Path(__file__).resolve().parents[1]
FLAG = "BRIDGE_PASSTHROUGH_SLIDING_WINDOW_ENABLED"
FORBIDDEN_IO = frozenset(
    "os sys io pathlib socket ssl http urllib subprocess threading multiprocessing asyncio concurrent "
    "selectors signal fcntl tempfile shutil glob sqlite3 logging ctypes importlib".split()
)  # `time` читает только фабрика `open_sliding_deadline`; КА-функции проверяются отдельно


def sw() -> Any:
    return importlib.import_module("core.passthrough_sliding_window")


def fresh(
    now: float = 100.0,
    initial: float = 10.0,
    idle: float = 5.0,
    cap: float = 60.0,
    enabled: bool = True,
) -> Any:
    return sw().init_sliding_stream(now, initial, idle, cap, enabled)


# ---- L1: чистый КА -------------------------------------------------------------------------
def test_init_enabled_uses_initial_deadline_and_absolute_cap() -> None:
    state = fresh()
    assert (state.start_s, state.deadline_s, state.cap_deadline_s) == (
        100.0,
        110.0,
        160.0,
    )
    assert (state.saw_useful_chunk, state.epoch) == (False, 0)


def test_init_cap_is_never_shorter_than_initial_window() -> None:
    state = fresh(initial=10.0, cap=3.0)
    assert state.cap_deadline_s == 110.0 and state.deadline_s == 110.0


def test_init_disabled_is_static() -> None:
    state = fresh(enabled=False)
    assert state.deadline_s == state.cap_deadline_s == 110.0


def test_useful_chunk_slides_deadline_by_idle_window() -> None:
    state = sw().step_sliding_stream(fresh(), 108.0, True, enabled=True)
    assert state.deadline_s == 113.0 and state.saw_useful_chunk is True


def test_step_default_is_kill_switch_off() -> None:
    """F-002: без явного `enabled=True` шаг не продлевает дедлайн (дефолт фичефлага — false)."""
    state = fresh()
    assert sw().step_sliding_stream(state, 108.0, True) is state
    assert sw().init_sliding_stream(0.0, 10.0, 5.0, 60.0).cap_deadline_s == 10.0


def test_slide_is_clamped_by_cap_and_never_moves_backwards_past_it() -> None:
    state = fresh(initial=10.0, idle=5.0, cap=20.0)
    for now in (101.0, 110.0, 118.0, 119.5, 150.0):
        state = sw().step_sliding_stream(state, now, True, enabled=True)
        assert state.deadline_s <= state.cap_deadline_s == 120.0
    assert state.deadline_s == 120.0


def test_transport_pulses_do_not_move_deadline() -> None:
    state = sw().step_sliding_stream(fresh(), 101.0, True, enabled=True)
    after = sw().step_sliding_stream(state, 104.0, False, enabled=True)
    assert after is state and after.deadline_s == 110.0


def test_disabled_step_is_identity() -> None:
    state = fresh()
    assert sw().step_sliding_stream(state, 101.0, True, enabled=False) is state


def test_stale_epoch_is_dropped_and_current_epoch_applied() -> None:
    state = sw().step_sliding_stream(fresh(), 101.0, True, enabled=True)
    assert state.epoch == 1  # каждый принятый полезный чанк увеличивает эпоху
    assert (
        sw().step_sliding_stream(state, 108.0, True, enabled=True, epoch=0) is state
    )  # устарела
    assert (
        sw().step_sliding_stream(state, 108.0, True, enabled=True, epoch=1).deadline_s
        == 113.0
    )
    assert (
        sw()
        .step_sliding_stream(state, 108.0, True, enabled=True, epoch=None)
        .deadline_s
        == 113.0
    )


def test_epoch_grows_only_on_accepted_useful_chunks() -> None:
    state = fresh()
    assert sw().step_sliding_stream(state, 101.0, False, enabled=True).epoch == 0
    assert sw().step_sliding_stream(state, 101.0, True, enabled=False).epoch == 0
    epochs = []
    for now in (101.0, 102.0, 103.0):
        state = sw().step_sliding_stream(state, now, True, enabled=True)
        epochs.append(state.epoch)
    assert epochs == [1, 2, 3]


def test_rearming_cell_never_decreases_epoch() -> None:
    cell = sw().SlidingDeadline(50.0)
    cell.arm(fresh())
    for now in (101.0, 102.0, 103.0):
        cell.advance(now, True)
    assert cell.state.epoch == 3
    cell.arm(fresh())  # свежее состояние с epoch=0 не откатывает счётчик
    assert cell.state.epoch == 4
    cell.arm(replace(fresh(), epoch=10))
    assert cell.state.epoch == 10


def test_rearm_never_rolls_deadline_back() -> None:
    """F-008: повторный `arm` меньшим дедлайном не откатывает опубликованный дедлайн назад."""
    cell = sw().SlidingDeadline(200.0)
    cell.arm(fresh())  # дедлайн состояния 110 < 200
    assert cell.deadline_s == 200.0
    cell.arm(fresh(now=150.0, initial=10.0))  # 160: всё ещё меньше уже опубликованного
    assert cell.deadline_s == 200.0
    cell.arm(fresh(now=195.0, initial=10.0))  # 205: двигаем только вперёд
    assert cell.deadline_s == 205.0


def test_remaining_is_distance_to_nearest_deadline() -> None:
    state = fresh()
    assert sw().remaining_sliding_s(state, 104.0) == pytest.approx(6.0)
    assert sw().remaining_sliding_s(state, 111.0) == pytest.approx(-1.0)


def test_state_is_frozen() -> None:
    with pytest.raises(AttributeError):
        fresh().deadline_s = 1.0  # type: ignore[misc]


def test_deadline_cell_static_until_armed_then_follows_state() -> None:
    cell = sw().SlidingDeadline(50.0)
    cell.advance(10.0, True)
    assert cell.deadline_s == 50.0  # не вооружена: статичный дедлайн запроса
    cell.arm(fresh())
    assert cell.deadline_s == 110.0
    cell.advance(103.0, False)
    assert cell.deadline_s == 110.0
    cell.advance(103.0, True)
    assert cell.deadline_s == 110.0  # не короче стартового окна (F-001)
    cell.advance(108.0, True)
    assert cell.deadline_s == 113.0
    cell.advance(109.0, True, epoch=1)  # к этому моменту эпоха ячейки уже 2
    assert cell.deadline_s == 113.0  # устаревшая эпоха отброшена


def test_early_useful_chunk_never_shortens_initial_window() -> None:
    state = fresh(initial=10.0, idle=2.0)
    early = sw().step_sliding_stream(state, 101.0, True, enabled=True)
    assert early.deadline_s == state.deadline_s == 110.0
    assert (
        sw().step_sliding_stream(early, 109.0, True, enabled=True).deadline_s == 111.0
    )
    deadlines = [
        (state := sw().step_sliding_stream(state, now, True, enabled=True)).deadline_s
        for now in (101.0, 104.0, 102.0, 109.0, 108.0)
    ]
    assert deadlines == sorted(deadlines)  # дедлайн монотонен


def test_state_has_slots_and_is_frozen() -> None:
    state = fresh()
    assert not hasattr(state, "__dict__")
    with pytest.raises(AttributeError):
        state.epoch = 1


class _Limits:
    total_timeout_s, idle_timeout_s, stream_safety_cap_s = 10.0, 5.0, 60.0


@pytest.mark.parametrize(
    ("internal", "request_body", "flag", "armed"),
    [
        (False, {"stream": True}, True, True),
        (True, {"stream": True}, True, False),
        (False, {"stream": False}, True, False),
        (False, {}, True, False),
        (False, {"stream": "true"}, True, False),
        (False, {"stream": True}, False, False),
    ],
)
def test_open_sliding_deadline_arms_only_for_client_stream_with_flag(
    internal: bool, request_body: dict[str, Any], flag: bool, armed: bool
) -> None:
    calls: list[bool] = []

    def flag_fn() -> bool:
        calls.append(flag)
        return flag

    cell = sw().open_sliding_deadline(
        110.0, _Limits(), internal, request_body, flag_fn, now_s=100.0
    )
    assert (cell.state is not None) is armed
    assert (
        cell.deadline_s == 110.0
    )  # внешний дедлайн вызывающего сохранён в обоих случаях
    if internal:
        assert calls == []  # флаг не читается, когда ячейка заведомо статична


def test_kill_switch_stops_extending_open_stream_mid_flight() -> None:
    """F-003: выключение флага посреди открытого стрима прекращает продление дедлайна."""
    enabled = [True]
    cell = sw().open_sliding_deadline(
        110.0, _Limits(), False, {"stream": True}, lambda: enabled[0], now_s=100.0
    )
    assert cell.state is not None and cell.deadline_s == 110.0
    cell.advance(108.0, True)
    assert cell.deadline_s == 113.0
    enabled[0] = False  # kill-switch GigaRC сработал на живом стриме
    cell.advance(112.0, True)
    assert cell.deadline_s == 113.0  # полезный чанк больше не продлевает окно
    enabled[0] = True
    cell.advance(112.5, True)
    assert cell.deadline_s > 113.0  # включение снова возвращает продление


def test_transport_pulses_do_not_poll_the_flag_but_useful_chunks_do() -> None:
    """F-001 (Seat 2): keep-alive/пустые дельты не читают снимок GigaRC, полезные чанки — читают."""
    reads: list[int] = []

    def flag() -> bool:
        reads.append(1)
        return True

    cell = sw().open_sliding_deadline(
        50.0, _Limits(), False, {"stream": True}, flag, now_s=100.0
    )
    reads.clear()  # чтение при вооружении ячейки не в счёт
    before = cell.deadline_s
    for tick in range(5):
        cell.advance(101.0 + tick, False)
    assert reads == [] and cell.deadline_s == before
    cell.advance(108.0, True)
    assert reads == [1] and cell.deadline_s == 113.0
    unarmed = sw().SlidingDeadline(50.0, enabled_fn=flag)
    unarmed.advance(1.0, True)  # не вооружена: флаг тоже не читается
    assert reads == [1] and unarmed.deadline_s == 50.0


def test_wrap_accepts_float_or_cell_and_public_surface_is_six() -> None:
    """F-005 (Seat 2): `as_cell` стал методом `SlidingDeadline`; публичных символов ровно шесть."""
    mod = sw()
    cell = mod.SlidingDeadline(5.0)
    assert mod.SlidingDeadline.wrap(cell) is cell
    wrapped = mod.SlidingDeadline.wrap(7)
    assert isinstance(wrapped, mod.SlidingDeadline) and wrapped.deadline_s == 7.0
    assert not hasattr(mod, "as_cell")
    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    public = {
        n.name
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")
    }
    assert public == {
        "SlidingStreamState",
        "init_sliding_stream",
        "step_sliding_stream",
        "remaining_sliding_s",
        "SlidingDeadline",
        "open_sliding_deadline",
    }


class _Sock:
    def __init__(self) -> None:
        self.timeouts: list[float] = []

    def settimeout(self, value: float) -> None:
        self.timeouts.append(value)


def test_relax_socket_targets_cap_when_armed_and_respects_force() -> None:
    sock = _Sock()
    static = sw().SlidingDeadline(time.monotonic() + 30.0)
    static.relax_socket(sock, 5.0)
    assert sock.timeouts == []  # не вооружена и не `force`: сокет не трогаем
    static.relax_socket(sock, 5.0, force=True)
    assert sock.timeouts == [pytest.approx(5.0)]  # internal-путь: прежнее поведение
    armed = sw().SlidingDeadline(time.monotonic() + 1.0)
    armed.arm_for(time.monotonic(), _Limits())
    armed.relax_socket(sock, 120.0)
    assert 55.0 < sock.timeouts[-1] <= 60.0  # предохранитель, а не статичный дедлайн
    armed.relax_socket(None, 5.0)  # сокета нет — без ошибок


def test_open_sliding_deadline_defaults_to_monotonic_clock() -> None:
    before = time.monotonic()
    cell = sw().open_sliding_deadline(
        0.0, _Limits(), False, {"stream": True}, lambda: True
    )
    assert (
        before + 5.0 <= cell.deadline_s <= time.monotonic() + 5.0
    )  # нет дедлайна: `idle_timeout_s`


def test_open_sliding_deadline_preserves_external_deadline_in_state() -> None:
    """Seat 1 F-002: окно КА строится от дедлайна вызывающего, а не от `total_timeout_s`."""
    cell = sw().open_sliding_deadline(
        107.0, _Limits(), False, {"stream": True}, lambda: True, now_s=100.0
    )
    assert cell.state is not None
    assert cell.state.initial_timeout_s == 7.0 and cell.state.deadline_s == 107.0
    assert cell.deadline_s == 107.0
    expired = sw().open_sliding_deadline(
        50.0, _Limits(), False, {"stream": True}, lambda: True, now_s=100.0
    )
    assert expired.state is not None and expired.state.initial_timeout_s == 0.0


def test_kill_switch_never_shrinks_cell_deadline_below_external() -> None:
    """Seat 1 F-002: выключенный флаг не сдвигает `deadline_s` назад к состоянию КА."""
    enabled = [False]
    cell = sw().SlidingDeadline(200.0, enabled_fn=lambda: enabled[0])
    cell.arm_for(100.0, _Limits(), 7.0)
    assert cell.deadline_s == 200.0
    cell.advance(101.0, True)
    assert cell.deadline_s == 200.0


def sse_stream() -> bytes:
    parts = [
        content("a"),
        b": keepalive\n\n",
        content("b" * 40),
        b"data: {}\n\n",
        content("Привет, мир   end"),
        b"\n",
        finish(0, "stop"),
        DONE,
    ]
    return b"".join(parts)


class Dribble(io.RawIOBase):
    """Сырой поток, отдающий данные порциями заданного размера (имитация TCP-сегментации)."""

    def __init__(self, data: bytes, sizes: list[int]) -> None:
        self.data, self.pos, self.sizes, self.n = data, 0, sizes, 0

    def readable(self) -> bool:
        return True

    def readinto(self, buf: Any) -> int:
        size = min(
            len(buf), self.sizes[self.n % len(self.sizes)], len(self.data) - self.pos
        )
        self.n += 1
        buf[:size] = self.data[self.pos : self.pos + size]
        self.pos += size
        return size


def final_state(data: bytes, sizes: list[int]) -> Any:
    reader = io.BufferedReader(Dribble(data, sizes), buffer_size=1)
    cell = sw().SlidingDeadline(0.0)
    cell.arm(fresh(now=0.0, initial=10.0, idle=5.0, cap=100.0))
    for tick, (_raw, event) in enumerate(
        iter_sse_events(reader.readline, 1 << 20), start=1
    ):
        cell.advance(float(tick), classify_sse_data(event)[0] == SIGNAL_S)
    return cell.state


def test_chunking_invariance_whole_split_1_7_random() -> None:
    data = sse_stream()
    rng = random.Random(20261106)
    variants = [[len(data)], [1], [7], [rng.randint(1, 13) for _ in range(64)]]
    states = [final_state(data, sizes) for sizes in variants]
    assert all(state == states[0] for state in states)
    assert states[0].saw_useful_chunk and states[0].deadline_s > 0


def test_module_is_pure_and_small() -> None:
    path = REPO / "core" / "passthrough_sliding_window.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        a.name.split(".")[0]
        for n in ast.walk(tree)
        if isinstance(n, ast.Import)
        for a in n.names
    }
    imported |= {
        n.module.split(".")[0]
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module
    }
    assert not imported & FORBIDDEN_IO
    assert len(path.read_text(encoding="utf-8").splitlines()) <= 300
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert all((n.end_lineno or 0) - n.lineno + 1 <= 35 for n in funcs)
    assert all(
        len(n.args.args) <= 5 for n in funcs if n.name != "open_sliding_deadline"
    )
    automaton = {"init_sliding_stream", "step_sliding_stream", "remaining_sliding_s"}
    for fn in (n for n in funcs if n.name in automaton):
        names = {x.id for x in ast.walk(fn) if isinstance(x, ast.Name)}
        assert "time" not in names  # чистый КА: время только аргументом


# ---- лимиты и флаг ------------------------------------------------------------------------------
def test_limits_safety_cap_default_and_env() -> None:
    assert PassthroughLimits().stream_safety_cap_s == 3600.0
    assert PassthroughLimits.from_env({}).stream_safety_cap_s == 3600.0
    assert (
        PassthroughLimits.from_env(
            {"BRIDGE_STREAM_SAFETY_CAP_S": "12.5"}
        ).stream_safety_cap_s
        == 12.5
    )
    assert (
        PassthroughLimits.from_env(
            {"BRIDGE_STREAM_SAFETY_CAP_S": "-3"}
        ).stream_safety_cap_s
        == 3600.0
    )
    assert (
        PassthroughLimits.from_env(
            {"BRIDGE_STREAM_SAFETY_CAP_S": "abc"}
        ).stream_safety_cap_s
        == 3600.0
    )


# ---- L2: реальный upstream ----------------------------------------------------------------------
@pytest.fixture(autouse=True)
def hermetic_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.delenv(FLAG, raising=False)


@pytest.fixture
def sliding_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Включает окно явно: дефолт фичефлага в коде — false (F-002), без GigaRC окна нет."""
    monkeypatch.setenv(FLAG, "true")


def drive(script: Any, limits: PassthroughLimits) -> tuple[CollectSink, float]:
    """Прогоняет `stream=True` запрос; `script(handler, stop)` пишет SSE в upstream."""
    stop = threading.Event()
    upstream = FakeUpstream()

    def respond(handler: Any, _body: bytes) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        try:
            script(handler, stop)
        except OSError:
            pass

    upstream.respond = respond  # pyright: ignore[reportAttributeAccessIssue]
    adapter = make_adapter(upstream.port, limits)
    sink = CollectSink()
    started = time.monotonic()
    try:
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=b'{"stream": true}',
            request={"stream": True},
            headers={},
            sink=sink,
        )
    finally:
        stop.set()
        adapter.shutdown()
        upstream.close()
    return sink, time.monotonic() - started


def emit(handler: Any, frame_bytes: bytes) -> None:
    handler.wfile.write(frame_bytes)
    handler.wfile.flush()


def error_frames(sink: CollectSink) -> list[dict[str, Any]]:
    """Разобранные `data:`-кадры с ошибкой из всего тела ответа клиенту."""
    parts = sink.body.decode("utf-8").split("\n\n")
    frames = [
        json.loads(p[5:]) for p in parts if p.startswith("data:") and "[DONE]" not in p
    ]
    return [f for f in frames if "error" in f]


def make_limits(cap: float, total: float = 0.4) -> PassthroughLimits:
    """Микро-тайминги: окно простоя 0.3 c, heartbeat выключен, частый опрос сторожа."""
    return PassthroughLimits(
        total_timeout_s=total,
        idle_timeout_s=0.3,
        heartbeat_interval_s=30.0,
        poll_interval_s=0.02,
        stream_safety_cap_s=cap,
    )


def test_active_stream_outlives_static_total_timeout(sliding_on: None) -> None:
    def script(handler: Any, _stop: threading.Event) -> None:
        for i in range(10):  # 10 * 0.1 c = 1.0 c > total_timeout_s = 0.4 c
            emit(handler, content(f"t{i} "))
            time.sleep(0.1)
        emit(handler, finish(0, "stop") + DONE)

    sink, elapsed = drive(script, make_limits(10.0))
    body = sink.body
    assert elapsed > 0.8
    assert not error_frames(sink)
    assert b"t9 " in body and b'"finish_reason": "stop"' in body and body.endswith(DONE)


def test_flag_off_restores_static_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FLAG, "false")

    def script(handler: Any, stop: threading.Event) -> None:
        for i in range(30):
            emit(handler, content(f"t{i} "))
            if stop.wait(0.05):
                return

    sink, elapsed = drive(script, make_limits(10.0))
    assert elapsed < 1.0
    assert error_frames(sink)[-1]["error"]["code"] == "upstream_stream_error"
    assert sink.body.endswith(DONE)


def test_absolute_safety_cap_still_aborts_a_chatty_stream(sliding_on: None) -> None:
    def script(handler: Any, stop: threading.Event) -> None:
        for i in range(200):
            emit(handler, content(f"t{i} "))
            if stop.wait(0.05):
                return

    sink, elapsed = drive(script, make_limits(0.6, total=0.3))
    assert (
        0.5 < elapsed < 2.0
    )  # cap = max(total, safety_cap) = 0.6 c, а не бесконечность
    assert error_frames(sink)[-1]["error"]["code"] == "upstream_stream_error"
    assert sink.body.endswith(DONE)


def test_stall_after_useful_chunk_aborts_by_idle_window_not_cap(
    sliding_on: None,
) -> None:
    def script(handler: Any, stop: threading.Event) -> None:
        emit(handler, content("first"))
        stop.wait(5)

    sink, elapsed = drive(script, make_limits(30.0))
    assert elapsed < 1.5
    assert error_frames(sink)[-1]["error"]["code"] == "upstream_stream_error"


def test_transport_pulses_after_first_useful_chunk_do_not_extend_window(
    sliding_on: None,
) -> None:
    def script(handler: Any, stop: threading.Event) -> None:
        emit(handler, content("first"))
        for _ in range(100):
            emit(handler, b": keepalive\n\n" + b"data: {}\n\n")
            if stop.wait(0.05):
                return

    sink, elapsed = drive(script, make_limits(30.0))
    assert elapsed < 1.5
    assert error_frames(sink)[-1]["error"]["code"] == "upstream_stream_error"


def test_silent_upstream_before_first_chunk_times_out_at_initial_window(
    sliding_on: None,
) -> None:
    def script(_handler: Any, stop: threading.Event) -> None:
        stop.wait(5)

    sink, elapsed = drive(script, make_limits(3600.0))
    assert (
        elapsed < 1.5
    )  # а не 3600 с: до первого полезного чанка действует total_timeout_s
    assert error_frames(sink)


def test_dynamic_flag_missing_snapshot_falls_back_to_env_and_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from core.runtime_env import DynamicFlagSource

    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.delenv(FLAG, raising=False)
    assert DynamicFlagSource(FLAG, True).enabled() is True  # default=True не теряется
    assert DynamicFlagSource(FLAG).enabled() is False
    monkeypatch.setenv(FLAG, "true")
    assert DynamicFlagSource(FLAG).enabled() is True
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"OTHER_FLAG": True}), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(other))
    assert DynamicFlagSource(FLAG).enabled() is True  # снимок без нашего ключа -> env

    class Sub(DynamicFlagSource):
        _flag_name = FLAG

        def __init__(self) -> None:  # pyright: ignore[reportMissingSuperCall]
            pass  # намеренно без super().__init__(): проверка атрибута класса

    monkeypatch.delenv(FLAG, raising=False)
    assert Sub().enabled() is False  # без AttributeError на `_default`


@pytest.mark.parametrize("content", ["{broken", "", "[]", "null", '"true"', "42"])
def test_dynamic_flag_broken_snapshot_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, content: str
) -> None:
    from core.runtime_env import DynamicFlagSource

    config = tmp_path / "broken.json"
    config.write_text(content, encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(config))
    monkeypatch.setenv(FLAG, "true")
    assert DynamicFlagSource(FLAG, True).enabled() is False  # default=True не спасает
    assert DynamicFlagSource(FLAG).enabled() is False  # env не обходит fail-closed


def test_adapter_flag_defaults_off_and_gigarc_switches_it_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F-002: адаптер создаёт источник без `default=True` — включение только через GigaRC/env."""
    from core.runtime_env import DynamicFlagSource

    src = (REPO / "adapters" / "passthrough_adapter.py").read_text(encoding="utf-8")
    assert "DynamicFlagSource(FLAG_PASSTHROUGH_SLIDING_WINDOW, True)" not in src
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.delenv(FLAG, raising=False)
    assert DynamicFlagSource(FLAG).enabled() is False
    config = tmp_path / "dyn.json"
    config.write_text(json.dumps({FLAG: True}), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(config))
    assert DynamicFlagSource(FLAG).enabled() is True


def test_dynamic_flag_default_is_configurable_and_config_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from core.runtime_env import DynamicFlagSource

    assert DynamicFlagSource(FLAG, True).enabled() is True  # env не задан: default=True
    assert DynamicFlagSource(FLAG).enabled() is False  # прежний default остаётся false
    monkeypatch.setenv(FLAG, "false")
    assert DynamicFlagSource(FLAG, True).enabled() is False
    config = tmp_path / "dyn.json"
    config.write_text(json.dumps({FLAG: True}), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(config))
    assert DynamicFlagSource(FLAG, True).enabled() is True  # GigaRC важнее env
    config.write_text("{broken", encoding="utf-8")
    monkeypatch.setenv(FLAG, "true")  # env не обходит fail-closed
    time.sleep(0.6)  # TTL снимка 0.5 c
    assert (
        DynamicFlagSource(FLAG, True).enabled() is False
    )  # нечитаемый конфиг: fail-closed
