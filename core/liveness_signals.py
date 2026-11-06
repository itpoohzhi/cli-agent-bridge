"""S/P/T liveness policy (ADR-0015)."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from core.runtime_env import flag_enabled

SIGNAL_S, SIGNAL_P, SIGNAL_T = "S", "P", "T"
FLAG_VIA_STREAM = "BRIDGE_NONSTREAM_VIA_STREAM_ENABLED"
FLAG_SOFT_LIVENESS = "BRIDGE_NONSTREAM_SOFT_LIVENESS_ENABLED"
FLAG_TELEMETRY = "BRIDGE_NONSTREAM_TELEMETRY_ENABLED"
REASON_FIRST, REASON_IDLE, REASON_CAP = "first_progress_timeout", "idle_timeout", "safety_cap"
T_LITERALS = frozenset({"ping", "keepalive", "[DONE]"})
SEMANTIC_TEXT_KEYS = ("content", "reasoning_content", "reasoning", "reasoning_text", "refusal")
SEMANTIC_CALL_KEYS = ("tool_calls", "function_call")
_REASONING_KEYS = frozenset(SEMANTIC_TEXT_KEYS[1:4])
_S_KINDS = frozenset(
    "content reasoning reasoning_content tool_calls function_call text_delta reasoning_delta tool_call text thinking result".split()
)


def parse_sse_json(data: str | None) -> Any:
    text = (data or "").strip()
    try:
        return None if not text or text in T_LITERALS else json.loads(text)
    except ValueError:
        return None


def classify_chunk(chunk: Any) -> tuple[str, frozenset[str]]:
    choices = chunk.get("choices") if isinstance(chunk, dict) else None
    keys: set[str] = set()
    for choice in choices if isinstance(choices, list) else ():
        delta = choice.get("delta") if isinstance(choice, dict) else None
        if isinstance(delta, dict):
            keys.update(k for k in (*SEMANTIC_TEXT_KEYS, *SEMANTIC_CALL_KEYS) if delta.get(k))
    return (SIGNAL_S if keys else SIGNAL_T), frozenset(keys)


def classify_sse_data(data: str | None) -> tuple[str, frozenset[str]]:
    return classify_chunk(parse_sse_json(data))


def classify_cli_activity(kind: str) -> str:
    """CLI activity: semantic output is S, rest T."""
    return SIGNAL_S if kind in _S_KINDS else SIGNAL_T


@dataclass(frozen=True)
class WindowSpec:
    first_timeout_s: float
    idle_timeout_s: float
    safety_cap_s: float
    soft_budget_s: float = 0.0
    min_cpu_delta_s: float = 0.05
    process_progress: bool = False
    internal_stream: bool = False
    stream_requested: bool | None = None


@dataclass(frozen=True)
class LivenessSnapshot:
    internal_stream: bool = False
    stream_requested: bool | None = None
    last_token_age_s: float | None = None
    last_reasoning_age_s: float | None = None
    last_progress_kind: str = "none"
    last_keepalive_age_s: float | None = None
    process_alive: bool | None = None
    soft_budget_used_s: float | None = None
    soft_budget_limit_s: float | None = None
    idle_remaining_s: float | None = None
    safety_cap_remaining_s: float | None = None

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _State:
    deadline: float
    cap_deadline: float
    last_p_at: float
    accrued_p_s: float = 0.0
    first_s_at: float | None = None
    last_token_at: float | None = None
    last_reasoning_at: float | None = None
    last_keepalive_at: float | None = None
    kind: str = "none"
    process_alive: bool | None = None


def _age(now: float, stamp: float | None) -> float | None:
    return None if stamp is None else round(max(0.0, now - stamp), 3)


class LivenessWindow:
    """Turn window: pre-S/post-S, bounded P budget, absolute cap."""

    def __init__(self, spec: WindowSpec, *, clock: Callable[[], float] = time.monotonic, soft_enabled: Callable[[], bool] = lambda: False) -> None:
        self._spec, self._clock, self._soft_enabled = spec, clock, soft_enabled
        self._lock = threading.Lock()
        now = clock()
        cap = now + spec.safety_cap_s
        self._state = _State(min(cap, now + spec.first_timeout_s), cap, now)

    @property
    def internal_stream(self) -> bool:
        return self._spec.internal_stream

    @property
    def soft(self) -> bool:
        return self._soft_enabled()

    def record_signal(self, kind: str, keys: frozenset[str] = frozenset()) -> None:
        soft = kind == SIGNAL_P and self._soft_enabled()
        with self._lock:
            now = self._clock()
            if kind == SIGNAL_S:
                self._apply_s(now, keys)
            elif kind == SIGNAL_P:
                self._apply_p(now, soft)
            else:
                self._state.last_keepalive_at = now

    def record_process(self, cpu_delta_s: float, new_children: int, alive: bool = True) -> None:
        soft = self._soft_enabled()
        with self._lock:
            self._state.process_alive = alive
            if alive and self._spec.process_progress:
                floor = self._spec.min_cpu_delta_s if soft else 0.0
                if new_children > 0 or (cpu_delta_s > 0.0 and cpu_delta_s >= floor):
                    self._apply_p(self._clock(), soft)

    def _apply_s(self, now: float, keys: frozenset[str]) -> None:
        st = self._state
        st.first_s_at = now if st.first_s_at is None else st.first_s_at
        st.deadline = min(st.cap_deadline, now + self._spec.idle_timeout_s)
        st.accrued_p_s, st.last_p_at, st.kind = 0.0, now, SIGNAL_S
        if keys & _REASONING_KEYS:
            st.last_reasoning_at = now
        if not keys or keys - _REASONING_KEYS:
            st.last_token_at = now

    def _apply_p(self, now: float, soft: bool) -> None:
        st, spec = self._state, self._spec
        if not spec.process_progress:
            return
        st.kind, idle = SIGNAL_P, spec.idle_timeout_s
        if soft:
            st.accrued_p_s += min(max(0.0, now - st.last_p_at), max(0.0, spec.soft_budget_s - st.accrued_p_s))
            idle = min(idle, max(0.0, spec.soft_budget_s - st.accrued_p_s))
        st.deadline, st.last_p_at = min(st.cap_deadline, max(st.deadline, now + idle)), now

    def expired(self) -> str:
        with self._lock:
            now, st = self._clock(), self._state
            if now >= st.cap_deadline:
                return REASON_CAP
            if now >= st.deadline:
                return REASON_FIRST if st.first_s_at is None else REASON_IDLE
            return ""

    def stop_reason(self) -> str:
        reason = self.expired()
        return "absolute_cap" if reason == REASON_CAP else "idle_timeout" if reason else ""

    def remaining_s(self) -> float:
        with self._lock:
            return min(self._state.deadline, self._state.cap_deadline) - self._clock()

    def snapshot(self) -> LivenessSnapshot:
        with self._lock:
            now, st, spec = self._clock(), self._state, self._spec
            proc = spec.process_progress
            return LivenessSnapshot(
                spec.internal_stream, spec.stream_requested, _age(now, st.last_token_at), _age(now, st.last_reasoning_at),
                st.kind, _age(now, st.last_keepalive_at), st.process_alive if proc else None,
                round(st.accrued_p_s, 3) if proc else None, spec.soft_budget_s if proc else None,
                round(max(0.0, st.deadline - now), 3), round(max(0.0, st.cap_deadline - now), 3),
            )


class SseProgress:
    """SSE frame S/T tracker; legacy `last_progress` semantics when flags are off."""

    def __init__(self, window: LivenessWindow | None, enforce: bool) -> None:
        self.window, self.enforce, self.last_progress = window, enforce, None
        self.strict = enforce or flag_enabled(FLAG_SOFT_LIVENESS)

    def remaining(self, default: float) -> float:
        return self.window.remaining_s() if self.enforce and self.window else default

    def note(self, data: str | None) -> Any:
        chunk = parse_sse_json(data)
        kind, keys = classify_chunk(chunk)
        if self.window is not None:
            self.window.record_signal(kind, keys)
        legacy = chunk is None and not self.strict and (data or "").strip() not in ("", "[DONE]", "null")
        if kind == SIGNAL_S or legacy:
            self.last_progress = time.monotonic()
        return chunk


def internal_stream_requested(path: str, request: Mapping[str, Any]) -> bool:
    route_ok = path.split("?", 1)[0].endswith("/chat/completions")
    return flag_enabled(FLAG_VIA_STREAM) and not request.get("stream") and route_ok


def passthrough_window(limits: Any, path: str, request: Mapping[str, Any]) -> LivenessWindow:
    internal = internal_stream_requested(path, request)
    total = limits.total_timeout_s
    legacy = {} if internal else {"first_timeout_s": total, "idle_timeout_s": limits.idle_timeout_s, "safety_cap_s": total}
    spec = limits.nonstream.window_spec(False, internal_stream=internal, stream_requested=bool(request.get("stream")), **legacy)
    return LivenessWindow(spec)
