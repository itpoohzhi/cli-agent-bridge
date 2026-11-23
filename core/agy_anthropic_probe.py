"""Bounded availability probing for Anthropic-compatible AGY models."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from typing import final

from core.agy_anthropic_gate import (
    canonicalize_claude_model,
    is_anthropic_flag_enabled,
    parse_agy_models_output,
    resolve_exact_5_5_upstream,
    validate_claude_effort,
)
from core.agy_models_stream_runner import (
    _OutputTooLarge as _OutputTooLarge,
    _kill_pg as _kill_pg,
    _validate_binary as _validate_binary,
    default_agy_models_runner as default_agy_models_runner,
)


@dataclass(frozen=True)
class ProbeSnapshot:
    """Immutable availability result with cache and circuit metadata."""

    canonical_model: str
    available: bool
    upstream_model: str | None
    reason: str
    checked_at: float
    expires_at: float
    live_models_hash: str
    circuit_open_until: float = 0.0


@dataclass(frozen=True)
class ProbeConfig:
    """Timing, output, and circuit-breaker limits for probes."""

    ttl_s: float = 120.0
    negative_ttl_s: float = 30.0
    timeout_s: float = 5.0
    circuit_cooldown_s: float = 30.0
    circuit_threshold: int = 2
    max_output_bytes: int = 1048576
    force_refresh_cooldown_s: float = 5.0
    wait_timeout_s: float | None = None


def _normalize_effort(requested_model: str, requested_effort: str | None) -> str:
    if requested_effort:
        return requested_effort
    for suffix in ("low", "medium", "high"):
        if requested_model.endswith(f"-{suffix}"):
            return suffix
    return ""


@final
class AgyAnthropicProbe:
    """Thread-safe, cached probe for the supported Claude 5.5 models."""

    def __init__(
        self,
        runner: Callable[[float, int], tuple[int, str]] | None = None,
        clock: Callable[[], float] = time.monotonic,
        config: ProbeConfig | None = None,
    ) -> None:
        self._runner = runner if runner is not None else default_agy_models_runner
        self._clock = clock
        self._config = config if config is not None else ProbeConfig()
        self._snapshots: dict[tuple[str, str], ProbeSnapshot] = {}
        self._inflight: dict[tuple[str, str], bool] = {}
        self._failures: dict[tuple[str, str], int] = {}
        self._last_force_refresh: dict[tuple[str, str], float] = {}
        self._condition = threading.Condition()

    def _wait_timeout(self) -> float:
        if self._config.wait_timeout_s is not None:
            return max(self._config.wait_timeout_s, 0.01)
        return max(self._config.timeout_s + 1.0, 1.0)

    def probe(
        self,
        requested_model: str,
        force_refresh: bool = False,
        requested_effort: str | None = None,
    ) -> ProbeSnapshot:
        """Return a cached result or execute one coordinated probe."""
        canonical = canonicalize_claude_model(requested_model)
        now = self._clock()
        if canonical is None:
            return self._failure_snapshot(
                requested_model, now, "forbidden_or_unknown_model"
            )
        ok_eff, _eff, eff_reason = validate_claude_effort(requested_effort)
        if not ok_eff:
            return self._failure_snapshot(canonical, now, eff_reason)
        cache_key = (canonical, _normalize_effort(requested_model, requested_effort))
        cached = self._cached_or_wait(cache_key, canonical, now, force_refresh)
        if cached is not None:
            return cached
        committed = False
        try:
            snap, clean = self._execute(
                requested_model, canonical, now, requested_effort
            )
            result = self._commit(cache_key, snap, clean)
            committed = True
            return result
        except Exception:
            fallback = self._failure_snapshot(canonical, now, "probe_failed")
            result = self._commit(cache_key, fallback, False)
            committed = True
            return result
        finally:
            if not committed:
                with self._condition:
                    self._inflight.pop(cache_key, None)
                    self._condition.notify_all()

    def _cached_or_wait(
        self,
        cache_key: tuple[str, str],
        canonical: str,
        now: float,
        force_refresh: bool,
    ) -> ProbeSnapshot | None:
        deadline = time.monotonic() + self._wait_timeout()
        with self._condition:
            waited_for_inflight = False
            while self._inflight.get(cache_key):
                waited_for_inflight = True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return self._failure_snapshot(
                        canonical, self._clock(), "probe_wait_timeout"
                    )
                self._condition.wait(timeout=remaining)
            if waited_for_inflight:
                waited = self._snapshots.get(cache_key)
                if waited is not None:
                    return self._apply_circuit_view(waited, self._clock())
            cached = self._usable_cached(cache_key, now, force_refresh)
            if cached is not None:
                return cached
            self._inflight[cache_key] = True
            if force_refresh:
                self._last_force_refresh[cache_key] = now
            return None

    def _usable_cached(
        self, cache_key: tuple[str, str], now: float, force_refresh: bool
    ) -> ProbeSnapshot | None:
        cached = self._snapshots.get(cache_key)
        if cached is None:
            return None
        if now < cached.circuit_open_until:
            return replace(cached, available=False, reason="circuit_open")
        last_force = self._last_force_refresh.get(cache_key)
        cooldown = self._config.force_refresh_cooldown_s
        if force_refresh and last_force is not None and now - last_force < cooldown:
            return cached
        if not force_refresh and now < cached.expires_at:
            return cached
        return None

    @staticmethod
    def _apply_circuit_view(snapshot: ProbeSnapshot, now: float) -> ProbeSnapshot:
        if now < snapshot.circuit_open_until:
            return replace(snapshot, available=False, reason="circuit_open")
        return snapshot

    def _failure_snapshot(
        self, canonical: str, now: float, reason: str
    ) -> ProbeSnapshot:
        return ProbeSnapshot(
            canonical, False, None, reason, now, now + self._config.negative_ttl_s, ""
        )

    def _execute(
        self,
        requested_model: str,
        canonical: str,
        now: float,
        requested_effort: str | None,
    ) -> tuple[ProbeSnapshot, bool]:
        try:
            rc, output = self._runner(
                self._config.timeout_s, self._config.max_output_bytes
            )
            if len(output.encode("utf-8")) > self._config.max_output_bytes:
                raise _OutputTooLarge("output_too_large")
            if rc != 0:
                return self._failure_snapshot(canonical, now, "probe_failed"), False
            decision = resolve_exact_5_5_upstream(
                requested_model,
                parse_agy_models_output(output),
                requested_effort=requested_effort,
            )
        except TimeoutError:
            return self._failure_snapshot(canonical, now, "probe_timeout"), False
        except _OutputTooLarge:
            return self._failure_snapshot(canonical, now, "output_too_large"), False
        except Exception:
            return self._failure_snapshot(canonical, now, "probe_failed"), False
        ttl = self._config.ttl_s if decision.available else self._config.negative_ttl_s
        snap = ProbeSnapshot(
            canonical,
            decision.available,
            decision.upstream_model,
            decision.reason,
            now,
            now + ttl,
            decision.live_models_hash,
        )
        return snap, True

    def _commit(
        self, cache_key: tuple[str, str], snapshot: ProbeSnapshot, clean_probe: bool
    ) -> ProbeSnapshot:
        with self._condition:
            if clean_probe:
                self._failures[cache_key] = 0
            else:
                self._failures[cache_key] = self._failures.get(cache_key, 0) + 1
                if self._failures[cache_key] >= self._config.circuit_threshold:
                    open_until = snapshot.checked_at + self._config.circuit_cooldown_s
                    snapshot = replace(snapshot, circuit_open_until=open_until)
            self._snapshots[cache_key] = snapshot
            self._inflight.pop(cache_key, None)
            self._condition.notify_all()
            return snapshot


def main(argv: list[str] | None = None) -> int:
    """Print one probe result as JSON."""
    if not is_anthropic_flag_enabled(os.environ.get("BRIDGE_AGY_ANTHROPIC_ENABLED")):
        print(json.dumps({"available": False, "reason": "feature_flag_disabled"}))
        return 0
    parser = argparse.ArgumentParser(description="Probe AGY Anthropic availability")
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args(argv)
    probe_obj = AgyAnthropicProbe()
    snapshot = (
        probe_obj.probe(args.model, force_refresh=True)
        if args.force_refresh
        else probe_obj.probe(args.model)
    )
    print(json.dumps(asdict(snapshot)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
