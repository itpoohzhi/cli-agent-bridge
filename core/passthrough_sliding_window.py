"""Чистый конечный автомат скользящего окна активности SSE-стрима (Sliding Activity Window).

Инвариант `AGENTS.md` (L2): каждый полезный чанк (`SIGNAL_S`: content / reasoning /
tool_calls) сдвигает дедлайн вперёд на `idle_timeout_s`, но не дальше абсолютного
предохранителя `safety_cap_s`. Транспортные пульсы (`SIGNAL_T`: keepalive, пустые
дельты) дедлайн не двигают. КА не знает о времени, сокетах и потоках: текущее время
передаётся аргументом (`F-FSM-I1`), состояние иммутабельно, чужая эпоха отбрасывается
(`F-FSM-I3`). Единственный изменяемый объект — `SlidingDeadline`: ячейка с публичным
`deadline_s`, которую пишет один поток-потребитель, а читает сторожевой поток
(присваивание атрибута атомарно, блокировки не нужны). Время и сокет трогают только ячейка
и фабрика `open_sliding_deadline` (граница с адаптером), КА остаётся чистым.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from core.dataclass_compat import DC_SLOTS
from core.nonstream_aggregator import relax_socket_timeout

FLAG_PASSTHROUGH_SLIDING_WINDOW = "BRIDGE_PASSTHROUGH_SLIDING_WINDOW_ENABLED"


@dataclass(frozen=True, **DC_SLOTS)
class SlidingStreamState:
    """Иммутабельное состояние окна; все поля — секунды на монотонных часах вызывающего."""

    start_s: float
    initial_timeout_s: float
    idle_timeout_s: float
    safety_cap_s: float
    deadline_s: float
    cap_deadline_s: float
    saw_useful_chunk: bool = False
    epoch: int = 0


def init_sliding_stream(
    now: float,
    initial_timeout_s: float,
    idle_timeout_s: float,
    safety_cap_s: float,
    enabled: bool = False,
) -> SlidingStreamState:
    """Начальное окно: до первого полезного чанка действует `initial_timeout_s`.

    Предохранитель никогда не короче начального окна (`max`), поэтому ошибочно малый
    `safety_cap_s` не обрывает поток раньше прежнего статического потолка. При
    выключенном флаге окно статично: `cap == deadline == now + initial_timeout_s`.
    """
    initial_deadline = now + initial_timeout_s
    cap = now + max(initial_timeout_s, safety_cap_s) if enabled else initial_deadline
    return SlidingStreamState(
        start_s=now,
        initial_timeout_s=initial_timeout_s,
        idle_timeout_s=idle_timeout_s,
        safety_cap_s=safety_cap_s,
        deadline_s=min(cap, initial_deadline),
        cap_deadline_s=cap,
    )


def step_sliding_stream(
    state: SlidingStreamState,
    now: float,
    is_useful_chunk: bool,
    enabled: bool = False,
    epoch: int | None = None,
) -> SlidingStreamState:
    """Один шаг КА: полезный чанк монотонно продлевает дедлайн (не короче стартового окна, не дальше предохранителя)."""
    if epoch is not None and epoch < state.epoch:
        return state
    if not enabled or not is_useful_chunk:
        return state
    return replace(
        state,
        saw_useful_chunk=True,
        epoch=state.epoch + 1,
        deadline_s=min(
            state.cap_deadline_s, max(state.deadline_s, now + state.idle_timeout_s)
        ),
    )


def remaining_sliding_s(state: SlidingStreamState, now: float) -> float:
    """Сколько секунд осталось до ближайшего из дедлайнов (отрицательно — истёк)."""
    return min(state.deadline_s, state.cap_deadline_s) - now


class SlidingDeadline:
    """Ячейка дедлайна запроса: статичная, пока не вооружена состоянием КА."""

    def __init__(
        self, deadline_s: float, enabled_fn: Callable[[], bool] | None = None
    ) -> None:
        self.deadline_s: float = deadline_s
        self.state: SlidingStreamState | None = None
        self._enabled_fn = enabled_fn

    def arm(self, state: SlidingStreamState) -> None:
        """Подключает КА; дедлайн ячейки только растёт (F-008), эпоха не убывает."""
        if self.state is not None:
            state = replace(state, epoch=max(state.epoch, self.state.epoch + 1))
        self.state = state
        self.deadline_s = max(self.deadline_s, float(state.deadline_s))

    def enabled(self) -> bool:
        """Живой kill-switch: выключение флага посреди стрима прекращает продление дедлайна."""
        return True if self._enabled_fn is None else bool(self._enabled_fn())

    def relax_socket(
        self, sock: Any, read_timeout_s: float, force: bool = False
    ) -> None:
        """Ослабляет таймаут чтения сокета до предохранителя: для вооружённой ячейки или при `force`."""
        if self.state is not None or force:
            cap_s = self.deadline_s if self.state is None else self.state.cap_deadline_s
            relax_socket_timeout(sock, cap_s, read_timeout_s)

    def arm_for(self, now: float, limits: Any) -> None:
        """Вооружает ячейку лимитами адаптера (`total_timeout_s`, `idle_timeout_s`, `stream_safety_cap_s`)."""
        self.arm(
            init_sliding_stream(
                now,
                limits.total_timeout_s,
                limits.idle_timeout_s,
                limits.stream_safety_cap_s,
                True,
            )
        )

    def advance(
        self, now: float, is_useful_chunk: bool, epoch: int | None = None
    ) -> None:
        """Применяет чанк к КА (если ячейка вооружена) и публикует новый дедлайн.

        Транспортные пульсы флаг не читают: снимок GigaRC опрашивается только на полезных чанках.
        """
        if self.state is None or not is_useful_chunk:
            return
        self.state = step_sliding_stream(self.state, now, True, self.enabled(), epoch)
        self.deadline_s = self.state.deadline_s

    @staticmethod
    def wrap(deadline: float | SlidingDeadline) -> SlidingDeadline:
        """Принимает прежний статический `float`-дедлайн или готовую ячейку."""
        if isinstance(deadline, SlidingDeadline):
            return deadline
        return SlidingDeadline(float(deadline))


def open_sliding_deadline(
    deadline: float,
    limits: Any,
    is_internal: bool,
    request: Mapping[str, Any],
    flag_enabled_fn: Callable[[], bool],
    now_s: float | None = None,
) -> SlidingDeadline:
    """Ячейка дедлайна запроса; вооружается только для клиентского `stream=True` при включённом флаге."""
    cell = SlidingDeadline(deadline, enabled_fn=flag_enabled_fn)
    if not is_internal and request.get("stream") is True and flag_enabled_fn():
        cell.arm_for(time.monotonic() if now_s is None else now_s, limits)
    return cell
