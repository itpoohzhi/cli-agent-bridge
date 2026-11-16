"""Чистый жизненный цикл SSE: семантика, активность и однократный terminal."""

from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable, cast


class StreamState(str, Enum):
    """Фазы потока; TERMINAL означает ожидающий передачи исход."""

    INIT = "init"
    ACTIVE = "active"
    TERMINAL = "terminal"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StreamEventKind(str, Enum):
    """Семантический прогресс отделён от транспортной активности."""

    PROGRESS = "progress"
    KEEPALIVE = "keepalive"
    TERMINAL = "terminal"
    UNKNOWN = "unknown"


_FINAL_STATES = (StreamState.COMPLETED, StreamState.FAILED, StreamState.CANCELLED)
_PROGRESS_KEYS = "content reasoning_content reasoning reasoning_text refusal tool_calls function_call".split()


@dataclass(frozen=True, slots=True)
class TerminalOutcome:
    """Первый исход сохраняется независимо от очереди транспортного слоя."""

    state: StreamState
    detail: str = ""

    def __post_init__(self) -> None:
        if self.state not in _FINAL_STATES:
            raise ValueError("terminal outcome must be completed, failed or cancelled")


@dataclass(frozen=True, slots=True)
class StreamSnapshot:
    """Иммутабельное межсобытийное состояние одного потока."""

    state: StreamState = StreamState.INIT
    progress_count: int = 0
    keepalive_count: int = 0
    last_progress_at: float | None = None
    last_keepalive_at: float | None = None
    terminal: TerminalOutcome | None = None


def _mapping(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _has_progress(payload: dict[str, object]) -> bool:
    return any(payload.get(key) for key in _PROGRESS_KEYS)


def _classify_payload(payload: dict[str, object]) -> StreamEventKind:
    if "error" in payload and payload["error"] is not None:
        return StreamEventKind.TERMINAL
    if _has_progress(payload) or _has_progress(_mapping(payload.get("delta"))):
        return StreamEventKind.PROGRESS
    choices = payload.get("choices")
    if isinstance(choices, list):
        for choice in cast(list[object], choices):
            if _has_progress(_mapping(_mapping(choice).get("delta"))):
                return StreamEventKind.PROGRESS
        return StreamEventKind.KEEPALIVE
    if "delta" in payload or payload.get("type") in ("ping", "heartbeat", "keepalive"):
        return StreamEventKind.KEEPALIVE
    return StreamEventKind.UNKNOWN


def classify_event(event: object) -> StreamEventKind:
    """Принимает декодированный payload либо SSE-комментарий/маркер, не JSON."""
    if isinstance(event, str):
        text = event.strip()
        if text.startswith(":"):
            return StreamEventKind.KEEPALIVE
        text = text.removeprefix("data:").strip()
        if text == "[DONE]":
            return StreamEventKind.TERMINAL
        if text in ("ping", "heartbeat", "keepalive"):
            return StreamEventKind.KEEPALIVE
    return _classify_payload(_mapping(event))


def step(
    snapshot: StreamSnapshot,
    kind: StreamEventKind,
    now: float,
    terminal: TerminalOutcome | None = None,
) -> StreamSnapshot:
    """Чистый переход; после фиксации terminal поздние события игнорируются."""
    if snapshot.state not in (StreamState.INIT, StreamState.ACTIVE):
        return snapshot
    if kind is StreamEventKind.PROGRESS:
        return replace(
            snapshot,
            state=StreamState.ACTIVE,
            progress_count=snapshot.progress_count + 1,
            last_progress_at=now,
        )
    if kind is StreamEventKind.KEEPALIVE:
        return replace(
            snapshot,
            keepalive_count=snapshot.keepalive_count + 1,
            last_keepalive_at=now,
        )
    if kind is StreamEventKind.TERMINAL:
        outcome = terminal or TerminalOutcome(StreamState.COMPLETED)
        return replace(snapshot, state=StreamState.TERMINAL, terminal=outcome)
    return snapshot


def _take_terminal(
    snapshot: StreamSnapshot,
) -> tuple[StreamSnapshot, TerminalOutcome | None]:
    if snapshot.state is not StreamState.TERMINAL or snapshot.terminal is None:
        return snapshot, None
    return replace(snapshot, state=snapshot.terminal.state), snapshot.terminal


class StreamLifecycleTracker:
    """Однописательский фасад КА; часы и синхронизация принадлежат транспорту."""

    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock: Callable[[], float] = clock
        self._snapshot: StreamSnapshot = StreamSnapshot()

    @property
    def snapshot(self) -> StreamSnapshot:
        return self._snapshot

    @property
    def state(self) -> StreamState:
        return self._snapshot.state

    @property
    def terminal(self) -> TerminalOutcome | None:
        return self._snapshot.terminal

    def record_event(self, event: object) -> StreamEventKind:
        """Регистрирует классифицированную активность без транспортного I/O."""
        kind = classify_event(event)
        if kind is StreamEventKind.TERMINAL:
            outcome = (
                StreamState.FAILED if isinstance(event, dict) else StreamState.COMPLETED
            )
            _ = self.record_terminal(outcome)
        else:
            self._snapshot = step(self._snapshot, kind, self._clock())
        return kind

    def record_terminal(
        self,
        state: StreamState = StreamState.COMPLETED,
        detail: str = "",
    ) -> bool:
        """Резервирует первый исход вне очереди; повторы не заменяют его."""
        if self._snapshot.terminal is not None:
            return False
        outcome = TerminalOutcome(state, detail)
        kind = StreamEventKind.TERMINAL
        self._snapshot = step(self._snapshot, kind, self._clock(), outcome)
        return True

    def take_terminal(self) -> TerminalOutcome | None:
        """Передаёт исход вызывающему ровно раз; отправка в SSE остаётся снаружи."""
        self._snapshot, outcome = _take_terminal(self._snapshot)
        return outcome
