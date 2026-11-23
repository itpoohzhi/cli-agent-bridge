# fmt: off
"""Снимок нейтральных настроек, кооперативный replay и единственный писатель SSE."""
from __future__ import annotations

import json
import os
import random
import threading
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, fields, replace
from typing import Protocol, Self, cast, final

import core.route_health_policy as routes
import core.runtime_env as cfg
import core.stream_activity_policy as activity
import core.stream_resilience_policy as policy
from core.passthrough_sliding_window import SlidingDeadline

Headers = Collection[tuple[str, str]]
_SSE_HEADERS = (("Content-Type", "text/event-stream"),)
class StreamSink(Protocol):
    def start(self, status: int, headers: list[tuple[str, str]]) -> object: ...
    def write(self, data: bytes) -> object: ...
class ReadyEvent(Protocol):
    def is_set(self) -> bool: ...
    def wait(self, timeout: float) -> object: ...
@dataclass(frozen=True)
class StreamResilienceConfig:
    idle_timeout_s: float = 300.0
    safety_cap_s: float = 3600.0
    heartbeat_interval_s: float = 12.0
    passthrough_read_timeout_s: float = 300.0
    midstream_retry_enabled: bool = False
    precommit_flush_enabled: bool = False
    passthrough_early_flush_enabled: bool = False
    tool_rollback_enabled: bool = False
    max_retries: int = 2
    retry_total_budget_s: float = 1020.0
    retry_reserve_s: float = 5.5
    retry_min_attempt_s: float = 5.0
    backoff_base_s: float = 1.5
    backoff_cap_s: float = 8.0
    backoff_jitter_ratio: float = 0.25
    first_event_timeout_s: float = 120.0
    precommit_flush_s: float = 15.0
    passthrough_flush_s: float = 20.0
    early_poll_interval_s: float = 0.25
    cross_hop_margin_s: float = 30.0
    ledger_max_entities: int = 512
    readonly_tools: frozenset[str] = frozenset()
    mutating_tools: frozenset[str] = policy.DEFAULT_MUTATING_TOOLS
    sliding_activity_window_enabled: bool = False
    sliding_idle_timeout_s: float = 300.0
    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Self:
        env = environ if policy.is_present(environ) else os.environ
        snapshot, broken = _snapshot(env)
        out: dict[str, object] = {}
        reused = ( "BRIDGE_IDLE_TIMEOUT_S", "BRIDGE_STREAM_SAFETY_CAP_S",
            "BRIDGE_SSE_HEARTBEAT_INTERVAL_S", "BRIDGE_PASSTHROUGH_READ_TIMEOUT_S", )
        for i, field in enumerate(fields(cls)):
            name, default = field.name, cast(object, field.default)
            key = dict(enumerate(reused)).get(i, f"BRIDGE_STREAM_{name.upper()}")
            raw = snapshot.get(name, snapshot.get(key, env.get(key)))
            if isinstance(default, bool):
                out[name] = all(
                    (not broken, cfg.env_bool({key: str(raw)}, (key,), False)) )
            elif isinstance(default, frozenset):
                out[name] = policy.parse_tool_names(raw, cast(frozenset[str], default))
            else:
                out[name] = _number(key, name, cast(float, default), raw)
        return replace(cls(), **out)
    def flag_enabled(self, name: str) -> bool:
        snapshot, broken = _snapshot(os.environ)
        key = f"BRIDGE_STREAM_{name.upper()}"
        fallback = os.environ.get(key, str(cast(object, getattr(self, name))))
        raw = snapshot.get(name, snapshot.get(key, fallback))
        return all((not broken, cfg.env_bool({key: str(raw)}, (key,), False)))
def _snapshot(environ: Mapping[str, str]) -> tuple[Mapping[str, object], bool]:
    key = "BRIDGE_DYNAMIC_CONFIG_PATH"
    fallback = os.path.expanduser("~/.config/cli-agent-bridge/dynamic_config.json")
    path = next(filter(None, (environ.get(key), os.environ.get(key))), fallback)
    try:
        reader = cast(Callable[[str], policy.Record | None], cfg.read_config_snapshot)
        return next(filter(None, (reader(path),)), dict[str, object]()), False
    except cfg.ConfigSnapshotError:
        return {}, True
def _number(key: str, name: str, default: float, raw: object) -> float:
    zero: dict[str, bool] = dict.fromkeys(("max_retries retry_reserve_s backoff_base_s "
        + "backoff_cap_s backoff_jitter_ratio cross_hop_margin_s").split(), True)
    high = {"backoff_jitter_ratio": 1.0, "max_retries": 999}.get(name, 86400)
    spec = cfg.NumSpec( (key,), default, 0, high,
        integer=isinstance(default, int), low_open=not zero.get(name, False), )
    env = {} if not policy.is_present(raw) else {key: str(raw)}
    return cast(float, cfg.parse_number(env, spec))
def sleep_with_keepalive( delay_s: float, emit_keepalive: Callable[[], object],
    config: StreamResilienceConfig,
    controls: tuple[Callable[[], float], Callable[[float], object], Callable[[], bool]]
    | None = None, ) -> bool:
    clock, sleeper, cancelled = next(
        filter(None, (controls,)), (time.monotonic, time.sleep, lambda: False) )
    end, pulse = clock() + delay_s, clock()
    ok = True
    while all((not cancelled(), clock() < end)):
        if clock() >= pulse:
            if emit_keepalive() is False:
                ok = False
                break
            pulse = clock() + config.heartbeat_interval_s
        _ = sleeper(min(config.early_poll_interval_s, max(0.0, end - clock())))
    return all((ok, not cancelled()))
@final
class MidstreamReplayOrchestrator:
    def __init__( self, config: StreamResilienceConfig,
        window: SlidingDeadline | activity.SlidingActivityWindow | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], object] = time.sleep, ) -> None:
        self.config, self._window = config, window
        self.clock, self.sleeper = clock, sleeper
        self.start_s, self.buffer = clock(), policy.UncommittedTurnBuffer()
    def attempt_budget_s( self, attempt_index: int, elapsed_s: float | None = None
    ) -> float:
        c = self.config
        elapsed = ( elapsed_s if policy.is_present(elapsed_s)
            else self.clock() - self.start_s )
        return activity.compute_sliding_attempt_budget_s(activity.SlidingBudgetInput(
            c.retry_total_budget_s, c.retry_reserve_s, elapsed,
            c.flag_enabled("sliding_activity_window_enabled"), c.max_retries + 1,
            attempt_index, c.first_event_timeout_s, c.backoff_cap_s, ))
    def arm_attempt(self, budget: float) -> activity.SlidingActivityWindow:
        c = self.config
        window = activity.SlidingActivityWindow( self.clock(), c.first_event_timeout_s,
            c.sliding_idle_timeout_s, budget, )
        self._window = window
        return window
    def deadline_s(self) -> float:
        window = self._window
        if isinstance(window, activity.SlidingActivityWindow):
            return window.current_deadline()
        return window.deadline_s if policy.is_present(window) else float("inf")
    def had_progress(self) -> bool:
        window = self._window
        if isinstance(window, activity.SlidingActivityWindow):
            return window.check_expired(self.clock()).had_progress
        return bool(window and window.state and window.state.saw_useful_chunk)
    def backoff_s(self, retry_index: int) -> float:
        c = self.config
        base = c.backoff_base_s * 2.0 ** min(max(0, retry_index), c.max_retries)
        return min( c.backoff_cap_s, base
            * random.uniform(1 - c.backoff_jitter_ratio, 1 + c.backoff_jitter_ratio), )
    def record_upstream_activity(self, is_useful_chunk: bool) -> None:
        window = self._window
        if isinstance(window, SlidingDeadline):
            window.advance(self.clock(), is_useful_chunk)
        elif policy.is_present(window) and is_useful_chunk:
            _ = window.record_signal("content", "progress", self.clock())
    def run_with_resilience( self, run_attempt: Callable[[int, float], policy.Record],
        ledger: policy.MidstreamStepLedger, emit_keepalive: Callable[[], object],
        cancelled: Callable[[], bool] = lambda: False, ) -> policy.Record:
        c = self.config
        self.start_s = self.clock()
        result: policy.Record = {"state": "error", "err": "retry_budget_exhausted"}
        for i in range(c.max_retries + 1):
            enabled = c.flag_enabled("midstream_retry_enabled")
            if any((cancelled(), all((i, not enabled)))):
                result = {"state": "cancelled"}
                break
            budget = self.attempt_budget_s(i) if enabled else c.first_event_timeout_s
            if not budget:
                result = {"state": "error", "err": "retry_budget_exhausted"}
                break
            result = run_attempt(i, budget)
            status = result.get("status_code", 0)
            category = policy.normalize_stream_interruption(
                status if isinstance(status, int) else 0, str(result.get("err", "")))
            if not all( ( enabled, c.flag_enabled("midstream_retry_enabled"),
                    category == routes.FailureCategory.CAPACITY_EXHAUSTED,
                    i < c.max_retries,
                    policy.can_safely_replay_turn(
                        ledger.snapshot(), ledger.last_committed_step_idx ), ) ):
                break
            self.buffer.rollback_uncommitted()
            if not sleep_with_keepalive( self.backoff_s(i), emit_keepalive, c,
                (self.clock, self.sleeper, cancelled), ):
                result = {"state": "cancelled"}
                break
        return result
def _error_sse(message: str, model: str) -> str:
    error = { "message": routes.redact_diagnostic_text(message), "type": "stream_error",
        "code": "stream_error", }
    chunk: dict[str, object] = { "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": None}], "error": error, }
    return "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\ndata: [DONE]\n\n"
@final
class EarlyCommitSinkCoordinator:
    def __init__( self, sink: StreamSink, config: StreamResilienceConfig,
        clock: Callable[[], float] = time.monotonic,
        error_formatter: Callable[..., str] = _error_sse, ) -> None:
        self.sink, self.config = sink, config
        self.clock, self.error_formatter = clock, error_formatter
        self._sink_lock = threading.Lock()
        self.headers_committed = self.cancelled = self._closed = False
        self._pending = b""
    def _write_locked(self, data: bytes | None, status: int = 200,
                      headers: Headers = _SSE_HEADERS) -> bool:
        ok = False
        if not any((self.cancelled, self._closed)):
            try:
                if getattr(self.sink, "client_gone", False):
                    policy.raise_error(BrokenPipeError())
                if not self.headers_committed:
                    _ = self.sink.start(status, list(headers))
                    self.headers_committed = True
                ok = True
                if policy.is_present(data):
                    ok = self.sink.write(data) is not False
            except (OSError, ValueError):
                self.cancelled, self._closed, self._pending = True, True, b""
                ok = False
        return ok
    def emit_chunk(self, data: bytes) -> bool:
        with self._sink_lock:
            ok = False
            if not any((self.cancelled, self._closed)):
                self._pending += data
                boundary = max(
                    (p + len(d) if (p := self._pending.rfind(d)) >= 0 else 0)
                    for d in (b"\n\n", b"\r\n\r\n") )
                frame, self._pending = (self._pending[:boundary],
                                       self._pending[boundary:])
                ok = self._write_locked(frame) if frame else True
                if frame.replace(b"\r\n", b"\n").count(b"data: [DONE]\n\n"):
                    self._closed = True
        return ok
    def write_keepalive(self) -> bool:
        with self._sink_lock:
            return self._write_locked(b": keepalive\n\n")
    def await_headers_or_flush(
        self, ready: ReadyEvent, *, flush_after_s: float | None = None ) -> None:
        threshold = ( flush_after_s if policy.is_present(flush_after_s)
            else self.config.precommit_flush_s )
        start = pulse = self.clock()
        while not any((ready.is_set(), self.cancelled, self._closed)):
            if getattr(self.sink, "client_gone", False):
                self.cancel()
                break
            elapsed = self.clock() - start
            enabled = any( ( self.config.flag_enabled("precommit_flush_enabled"),
                    self.config.flag_enabled("passthrough_early_flush_enabled"), ) )
            flush = policy.should_flush_precommit_headers(elapsed, threshold, False)
            if all((enabled, flush, self.clock() >= pulse)):
                _ = self.write_keepalive()
                pulse = self.clock() + self.config.heartbeat_interval_s
            _ = ready.wait(self.config.early_poll_interval_s)
    def emit_error_and_done(self, message: str, *, model: str = "bridge-stream"
                            ) -> None:
        with self._sink_lock:
            self._pending = b""
            clean = routes.redact_diagnostic_text(message)
            _ = self._write_locked(self.error_formatter(clean, model=model).encode())
            self._closed = True
    def cancel(self) -> None:
        with self._sink_lock:
            self.cancelled, self._closed, self._pending = True, True, b""
    cancel_on_disconnect = cancel
    write_chunk = emit_chunk
    def start_headers(self, status: int = 200, headers: Headers = _SSE_HEADERS) -> bool:
        with self._sink_lock:
            return self._write_locked(None, status, headers)
    def close(self) -> None:
        with self._sink_lock:
            self._closed, self._pending = True, b""
