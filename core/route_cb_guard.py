"""Per-attempt circuit-breaker guard, bounded events, and runtime lookup."""

# Compact legacy guard stays within the mandated extraction LOC cap.
# fmt: off
from __future__ import annotations

import atexit
import contextlib
import logging
import queue
import threading
import time
import weakref
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.quota_classifier import QuotaRules, classify_429
from core.retry_control import CircuitPolicy, CircuitProbe, HealthDomain, RouteCandidate, RouteCircuitBreaker
from core.route_attempts import RouteFailover, RouteRefusal
from core.route_cb import RouteCB, RouteCBConfig
from core.route_cb_decisions import RouteCBEvent, format_cb_event
from core.route_cb_policy import FailureOutcome, RouteProbeLease, RouteTupleKey, apply_quota_429, legacy_failure_action, load_route_cb_config, refusal_detail


class BoundedRouteCBSink:
    """Non-blocking bounded event sink with exact dropped-event accounting."""
    def __init__(self, log_fn: Callable[[str], None], maxsize: int = 256, allowed_ids: frozenset[str] | None = None) -> None:
        self._log_fn = log_fn
        self._allowed_ids = allowed_ids
        self._queue: queue.Queue[RouteCBEvent] = queue.Queue(maxsize=maxsize)
        self._stop_event = threading.Event()
        self._start_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._dropped = 0
        self._closed = False
    @property
    def route_cb_events_dropped(self) -> int:
        with self._state_lock:
            return self._dropped
    def _add_dropped(self, count: int = 1) -> None:
        with self._state_lock:
            self._dropped += count
    def _ensure_started(self) -> None:
        if self._thread is None:
            with self._start_lock:
                if self._thread is None:
                    self._thread = threading.Thread(target=self._run, daemon=True)
                    self._thread.start()
    def __call__(self, ev: RouteCBEvent) -> None:
        with self._state_lock:
            if self._closed:
                self._dropped += 1
                return
            self._ensure_started()
            try:
                self._queue.put_nowait(ev)
            except queue.Full:
                self._dropped += 1

    emit = __call__
    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                ev = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                self._log_fn(format_cb_event(ev, self._allowed_ids))
            except Exception:
                self._add_dropped()
    def _drain_remaining(self) -> int:
        count = 0
        while True:
            try:
                self._queue.get_nowait()
                count += 1
            except queue.Empty:
                break
        if count:
            self._add_dropped(count)
        return count
    def reset(self) -> int:
        return self._drain_remaining()
    def close(self, timeout_s: float = 0.2) -> None:
        with self._state_lock:
            self._closed = True
            self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout_s)
        self._drain_remaining()


_ATEXIT_LOCK = threading.Lock()
_ATEXIT_REGISTERED = False
_ACTIVE_SINKS: weakref.WeakSet[BoundedRouteCBSink] = weakref.WeakSet()


def _close_active_sinks() -> None:
    for sink in list(_ACTIVE_SINKS):
        with contextlib.suppress(Exception):
            sink.close()


def _register_sink(sink: BoundedRouteCBSink) -> None:
    global _ATEXIT_REGISTERED
    with _ATEXIT_LOCK:
        _ACTIVE_SINKS.add(sink)
        if not _ATEXIT_REGISTERED:
            atexit.register(_close_active_sinks)
            _ATEXIT_REGISTERED = True  # pyright: ignore[reportConstantRedefinition]


def _new_sink(cfg: RouteCBConfig) -> BoundedRouteCBSink | None:
    if not cfg.events_enabled:
        return None
    sink = BoundedRouteCBSink(logging.getLogger("cli_agent_bridge.route_cb").info)
    _register_sink(sink)
    return sink


@dataclass(slots=True)
class CBAttemptGuard:
    """Unified per-attempt CB lifecycle guard for passthrough_facade."""
    candidate: RouteCandidate
    key: RouteTupleKey
    route_cb: RouteCB | None = None
    legacy: RouteCircuitBreaker | None = None
    lease: RouteProbeLease | None = None
    probe: CircuitProbe | None = None
    quota_refusal: RouteRefusal | None = None
    blocked_key: RouteTupleKey | None = None
    done: bool = False
    route_count: int = 0
    @property
    def blocked(self) -> bool:
        return self.blocked_key is not None or self.quota_refusal is not None
    def release(self) -> None:
        if self.done:
            return
        self.done = True
        if self.route_cb is not None:
            self.route_cb.release_lease(self.lease)
        elif self.legacy is not None and self.probe is not None:
            self.legacy.release_probe(self.probe)
    def succeed(self, now: float) -> None:
        if self.done:
            return
        self.done = True
        if self.route_cb is not None:
            self.route_cb.record_success(self.key, self.lease)
        elif self.legacy is not None and self.probe is not None:
            self.legacy.record_success(self.candidate, HealthDomain.ROUTE)
            self.legacy.record_success(self.candidate, HealthDomain.CREDENTIAL_SCOPE)
            self.probe.succeed(now)
    def _record_outcome(self, outcome: FailureOutcome) -> None:
        try:
            if self.route_cb is not None:
                self.route_cb.record_failure(self.key, outcome, self.lease)
            self.done = True
        except BaseException:
            self.release()
            raise
    def record_exception(self, exc: BaseException, now: float | None = None) -> None:
        if self.done:
            return
        if self.route_cb is not None:
            self._record_outcome(FailureOutcome(error=exc, route_count=self.route_count))
            return
        if self.legacy is not None:
            now_err = time.monotonic() if now is None else now
            try:
                self.legacy.record_failure(self.candidate, HealthDomain.ROUTE, now_err)
            finally:
                self.done = True
                if self.probe is not None:
                    self.legacy.release_probe(self.probe)
    def _apply_quota(self, error: RouteRefusal, qdec: Any, host: Any) -> RouteRefusal:
        scope = f"{self.candidate.origin}@{self.candidate.route_id}"
        return apply_quota_429(error, qdec, host, scope)
    def _route_error_details(self, error: BaseException, host: Any, quota_rules: QuotaRules) -> tuple[RouteRefusal | None, int | None, str]:
        if not isinstance(error, RouteRefusal):
            return None, None, ""
        recorded: RouteRefusal = error
        status = error.status_code
        detail = refusal_detail(error)
        if status == 429:
            qdec = classify_429(dict(error.response_headers), error.response_body, quota_rules)
            if qdec.is_quota:
                recorded = self._apply_quota(error, qdec, host)
        return recorded, status, detail
    def record_error(self, error: BaseException, host: Any, failover: RouteFailover, quota_rules: QuotaRules, now: float | None = None) -> RouteRefusal | None:
        if self.done:
            return None
        if self.legacy is not None:
            return self._record_legacy_error(error, host, failover, quota_rules, now)
        try:
            recorded, status, detail = self._route_error_details(error, host, quota_rules)
            outcome = FailureOutcome(status=status, error=error, detail=detail, route_count=self.route_count)
            self._record_outcome(outcome)
            return recorded
        except BaseException:
            self.release()
            raise
    def _record_legacy_quota(self, error: Any, host: Any, quota_rules: QuotaRules, now: float) -> RouteRefusal | None:
        qdec = classify_429(dict(error.response_headers), error.response_body, quota_rules)
        if qdec.is_quota:
            self.legacy.record_failure(self.candidate, HealthDomain.CREDENTIAL_SCOPE, now, cooldown_s=qdec.reset_s, reason=qdec.reason)
            return self._apply_quota(error, qdec, host)
        self.legacy.record_failure(self.candidate, HealthDomain.ROUTE, now)
        return error
    def _record_legacy_error(self, error: BaseException, host: Any, failover: RouteFailover, quota_rules: QuotaRules, now: float | None = None) -> RouteRefusal | None:
        now_err = time.monotonic() if now is None else now
        recorded = error if isinstance(error, RouteRefusal) else None
        try:
            action = legacy_failure_action(error, failover)
            if action == "quota":
                recorded = self._record_legacy_quota(error, host, quota_rules, now_err)
            elif action == "slot_refusal":
                self.legacy.record_failure(self.candidate, HealthDomain.CREDENTIAL_SCOPE, now_err, cooldown_s=quota_rules.cooldown_default_s, reason=f"http_{getattr(error, 'status_code', 0)}_slot_refusal")
            elif action == "route":
                self.legacy.record_failure(self.candidate, HealthDomain.ROUTE, now_err)
            return recorded
        finally:
            self.done = True
            if self.probe is not None:
                self.legacy.release_probe(self.probe)


def get_route_cb(runtime: Any, env: Mapping[str, str] | None = None) -> tuple[RouteCB | None, RouteCircuitBreaker | None]:
    """Select active RouteCB or legacy RouteCircuitBreaker singleton for runtime."""
    cfg = load_route_cb_config(env)
    old_sink = None
    with runtime.lock:
        if cfg.enabled:
            if getattr(runtime, "route_cb", None) is None or getattr(runtime, "route_cb_config", None) != cfg:
                old_sink = getattr(runtime, "route_cb_sink", None)
                new_sink = _new_sink(cfg)
                runtime.route_cb = RouteCB(cfg, event_sink=new_sink)
                runtime.route_cb_config, runtime.route_cb_sink = cfg, new_sink
            result = runtime.route_cb, None
        else:
            old_sink = getattr(runtime, "route_cb_sink", None)
            runtime.route_cb_sink = None
            policy = CircuitPolicy(cfg.failure_threshold, cfg.cooldown_s)
            runtime.breaker = runtime.breaker or RouteCircuitBreaker(policy)
            result = None, runtime.breaker
    if old_sink is not None:
        old_sink.close()
    return result


def acquire_cb_guard(breakers: tuple[RouteCB | None, RouteCircuitBreaker | None], candidate: RouteCandidate, key: RouteTupleKey, now: float, route_count: int = 0) -> CBAttemptGuard:
    """Acquire either RouteCB lease or legacy RouteCircuitBreaker probe."""
    route_cb, legacy = breakers
    if route_cb is not None:
        lease = route_cb.try_acquire(key, now, route_count=route_count)
        return CBAttemptGuard(candidate=candidate, key=key, route_cb=route_cb, lease=lease, route_count=route_count, blocked_key=key if lease is None else None, done=lease is None)
    probe = legacy.try_acquire(candidate, now)
    if probe is not None:
        return CBAttemptGuard(candidate=candidate, key=key, legacy=legacy, probe=probe, route_count=route_count)
    blocked, remaining_s, _reason = legacy.quota_block_info(candidate, now)
    refusal = RouteRefusal(429, (("Retry-After", str(max(60, int(remaining_s)))),), b'{"error":{"type":"rate_limit_error","message":"slot in quota cooldown"}}') if blocked else None
    return CBAttemptGuard(candidate=candidate, key=key, legacy=legacy, quota_refusal=refusal, blocked_key=key, done=True, route_count=route_count)
