"""Thread-safe resident runtime orchestrating single-flight locks, pool, and FSM."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from typing import Any, cast

from core.resident_canonical import _fail_if
from core.resident_history import (
    ResidentHistoryTracker,
    build_assistant_transcript_item,
    plan_history_transition,
)
from core.resident_identity import ResidentAuthError as ResidentAuthError
from core.resident_identity import ResidentRequestError as ResidentRequestError
from core.p12_hub_cancel_seam import bind_resident_slot_pgid
from core.resident_turn_envelope import ResidentTurnEnvelope
from core.session_plane.zc_env_guard import is_zero_canon_keyed_resident_enabled
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_pool import ResidentProcessPool, SlotLeaseTimeoutError
from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.runtime_types import (
    PreDispatchResidentError as PreDispatchResidentError,
    ResidentCancelledError as ResidentCancelledError,
    ResidentStreamError as ResidentStreamError,
    ResidentTurnOptions as ResidentTurnOptions,
    ResourceLimitError as ResourceLimitError,
    _LockEntry,
    _TurnState,
)
from core.stdio_resident.runtime_wire import cancel_driver_turn, prepare_runtime_spec, stream_driver_turn, teardown_driver_turn
from core.stdio_resident.types import SlotAffinityKey, SlotBinding
from core.stdio_resident.zero_canon_router import ZeroCanonIsolation, zero_canon_isolation
from core.subbridge_zero_canon import is_zero_canon_profile

_LOGGER = logging.getLogger(__name__)


def _binding_of(item: Any) -> SlotBinding | None:
    return SlotBinding(item.slot_id, item.generation) if item else None


def _is_keyed_zc(envelope: ResidentTurnEnvelope) -> bool:
    """Keyed Zero-Canon: ZC-профиль + неэфемерная идентичность + kill-switch ON (иначе 100% legacy)."""
    return all((is_zero_canon_profile(envelope.review_profile), not envelope.identity.ephemeral, is_zero_canon_keyed_resident_enabled()))


def _resolve_driver_method(driver: Any) -> Any:
    return next((c for n in ("stream_turn", "execute_turn", "run_turn") if callable(c := getattr(driver, n, None))), None)


class ResidentBridgeRuntime:
    """Single-flight session runtime over ResidentProcessPool and ResidentHistoryTracker."""

    def __init__(self, pool: ResidentProcessPool, driver: Any, config: StdioPoolConfig | None = None, *, clock: Callable[[], float] | None = None) -> None:
        cfg = config if config else cast(StdioPoolConfig, getattr(pool, "_config"))
        self._pool, self._driver, self._config, self._clock = pool, driver, cfg, clock
        self._cap = max(cfg.max_slots * 4, 16)
        self._tracker = ResidentHistoryTracker(max_entries=self._cap)
        self._session_locks: dict[str, _LockEntry] = {}
        self._locks_mutex = threading.Lock()

    @contextmanager
    def session_barrier(self, session_key: str) -> Iterator[None]:
        """Acquire and refcount a per-session lock."""
        with self._locks_mutex:
            entry = self._session_locks.setdefault(session_key, _LockEntry())
            entry.waiters += 1
        try:
            with entry.lock:
                yield
        finally:
            self._drop_waiter(session_key, entry)

    def execute_turn(self, envelope: ResidentTurnEnvelope, options: ResidentTurnOptions) -> Iterator[DecodedChunk]:
        """Execute one turn under bounded single-flight lock with atomic slot lifecycle."""
        cancelled = bool(options.cancel_event.is_set()) if options.cancel_event else False
        _fail_if(cancelled, ResidentCancelledError("resident turn cancelled"))
        _fail_if(all((not str(envelope.identity.principal_hash or "").strip(), bool(options.require_auth))), ResidentAuthError(401, "auth_required"))
        with self._admit_turn(envelope) as (current, session_key), zero_canon_isolation(
            self._driver, current.review_profile, keyed_slot_id=session_key, persist=_is_keyed_zc(current)
        ) as iso:
            yield from self._run_isolated_turn(current, session_key, iso, options)

    def _run_isolated_turn(
        self, current: ResidentTurnEnvelope, session_key: str, iso: ZeroCanonIsolation, options: ResidentTurnOptions
    ) -> Iterator[DecodedChunk]:
        keyed_zc = bool(iso.persist)
        committed, plan, affinity_key, eph = self._plan_and_reset_stale(current, session_key)
        argv, cwd, spawn_env = prepare_runtime_spec(self._driver, current, options.argv_builder(), iso)
        sandbox = tempfile.mkdtemp(prefix="turn-")
        os.chmod(sandbox, 0o700)
        turn_ctx = {**dict(options.extra_turn_context if options.extra_turn_context else {}), "turn_sandbox": sandbox, "cwd": cwd, "review_profile": current.review_profile, "zero_canon_root": iso.root, "keyed_zero_canon": keyed_zc}
        opts = replace(options, extra_turn_context=turn_ctx)
        slot_eph = eph or (bool(iso.active) and not keyed_zc)
        slot: Any = None
        try:
            zc_root = iso.root if keyed_zc else None
            slot, plan = self._acquire_checked_slot(current, committed, affinity_key, (slot_eph, argv, cwd, spawn_env), zc_root)
            turn_ctx["new_thread"] = bool(plan.logical_context_reset)
            bind_resident_slot_pgid(slot.handle, turn_ctx)
            runnable = bool(current.rpc.runnable) if current.rpc else False
            state = _TurnState(current, opts, session_key, slot, plan, any((slot_eph, not runnable)))
            yield from self._stream_and_commit_turn(state)
        finally:
            if isinstance(options.extra_turn_context, dict) and "_committed_slot" in turn_ctx:
                options.extra_turn_context["_committed_slot"] = turn_ctx["_committed_slot"]
            shutil.rmtree(sandbox, ignore_errors=True)
            if keyed_zc and slot is None and iso.root:
                self._discard_unbound_zc_home(iso.root)

    def _discard_unbound_zc_home(self, root: str) -> None:
        discard = getattr(self._pool, "discard_unbound_zc_home", None)
        if callable(discard):
            discard(root)

    @contextmanager
    def _admit_turn(self, envelope: ResidentTurnEnvelope) -> Iterator[tuple[ResidentTurnEnvelope, str]]:
        session_key = envelope.identity.scoped_session_id
        entry: _LockEntry | None = None
        stale: SlotBinding | None = None
        with self._locks_mutex:
            if not envelope.identity.ephemeral:
                existing = self._session_locks.get(session_key)
                if existing:
                    entry = existing
                    entry.waiters += 1
                elif len(self._session_locks) >= self._cap:
                    envelope = envelope.with_ephemeral_identity("admission_cap")
                    stale = _binding_of(self._tracker.invalidate(session_key))
                else:
                    entry = _LockEntry(waiters=1)
                    self._session_locks[session_key] = entry
        self._close_binding(stale)
        if not entry:
            yield envelope, envelope.identity.scoped_session_id
        else:
            try:
                with entry.lock:
                    self._tracker.pin(session_key)
                    try:
                        yield envelope, session_key
                    finally:
                        self._tracker.unpin(session_key)
            finally:
                self._drop_waiter(session_key, entry)

    def _drop_waiter(self, session_key: str, entry: _LockEntry) -> None:
        with self._locks_mutex:
            entry.waiters -= 1
            if all((not entry.waiters, not bool({id(self._session_locks.get(session_key))} - {id(entry)}))):
                self._session_locks.pop(session_key, None)

    def _plan_and_reset_stale(self, envelope: ResidentTurnEnvelope, session_key: str) -> tuple[Any, Any, SlotAffinityKey, bool]:
        affinity_key = envelope.affinity_key()
        committed = self._tracker.get(session_key)
        slot_bound = self._pool.idle_binding(affinity_key)
        plan = plan_history_transition(committed, envelope, slot_bound)
        eph = any((envelope.identity.ephemeral, plan.ephemeral_slot, bool(envelope.images)))
        if plan.requires_slot_reset:
            c_bind = _binding_of(committed)
            self._close_binding(c_bind)
            if bool({slot_bound} - {c_bind}):
                self._close_binding(slot_bound)
            self._tracker.invalidate(session_key)
            committed = None
            plan = plan_history_transition(None, envelope, None)
        return committed, plan, affinity_key, eph

    def _acquire_checked_slot(
        self,
        envelope: ResidentTurnEnvelope,
        committed: Any,
        affinity_key: SlotAffinityKey,
        spawn_cfg: tuple[bool, list[str], str, dict[str, str] | None],
        zc_home_root: str | None = None,
    ) -> tuple[Any, Any]:
        ephemeral, argv, cwd, spawn_env = spawn_cfg
        runnable = bool(envelope.rpc.runnable) if envelope.rpc else False
        non_committable = any((ephemeral, not runnable))
        chosen: tuple[Any, Any] | None = None
        for attempt in range(2):
            slot = self._acquire_slot(affinity_key, non_committable, (argv, cwd, spawn_env), zc_home_root)
            plan = plan_history_transition(committed, envelope, SlotBinding(slot.slot_id, slot.handle.generation))
            if all((plan.requires_slot_reset, bool(slot.handle.generation))):
                self._pool.release(slot.slot_id, cancel=True, lease_id=slot.lease_id)
                _fail_if(attempt == 1, PreDispatchResidentError())
                continue
            if not slot.handle.is_alive():
                self._pool.release(slot.slot_id, cancel=True, lease_id=slot.lease_id)
                self._tracker.invalidate(envelope.identity.scoped_session_id)
                _fail_if(True, PreDispatchResidentError("resident_process_not_alive"))
            chosen = (slot, plan)
            break
        _fail_if(not chosen, PreDispatchResidentError())
        return cast(tuple[Any, Any], chosen)

    def _acquire_slot(self, affinity_key: SlotAffinityKey, non_committable: bool, spec: tuple[list[str], str, dict[str, str] | None], zc_home_root: str | None = None) -> Any:
        argv, cwd, spawn_env = spec
        extra: dict[str, Any] = {"zc_home_root": zc_home_root} if zc_home_root else {}
        try:
            return self._pool.acquire(affinity_key, lambda: list(argv), cwd, spawn_env, is_ephemeral=non_committable, **extra)
        except SlotLeaseTimeoutError as exc:
            full = "slot_wait_queue_full" in str(exc)
            raise PreDispatchResidentError("slot_wait_queue_full" if full else "slot_lease_timeout", 503) from exc

    def _stream_and_commit_turn(self, state: _TurnState) -> Iterator[DecodedChunk]:
        parts: list[str] = []
        tool_calls: list[dict[str, object]] = []
        byte_count = 0
        last_hb = time.monotonic()
        try:
            for decoded in self._driver_chunks(state):
                state.dispatched = any((state.dispatched, bool(getattr(decoded, "dispatched", False))))
                text, encoded = self._encoded_chunk(decoded)
                parts.append(text)
                tool_calls.extend(cast(list[dict[str, object]], tc) if isinstance(tc := getattr(decoded, "tool_calls", None), list) else ())
                byte_count += encoded
                cap = state.options.max_output_bytes
                _fail_if(bool(cap) and byte_count > cast(int, cap), ResourceLimitError("output_limit_exceeded"))
                ev = state.options.cancel_event
                _fail_if(ev.is_set() if ev else False, ResidentCancelledError("resident turn cancelled"))
                last_hb = self._tick_keepalive(state.options.keepalive, last_hb)
                if all((decoded.is_terminal, not decoded.error)):
                    self._commit_terminal(state, "".join(parts), tool_calls or None)
                yield decoded
        except (ResidentCancelledError, ResourceLimitError, ResidentStreamError):
            raise
        except Exception as exc:
            _fail_if(not state.dispatched, PreDispatchResidentError("resident_dispatch_failed"))
            raise exc
        finally:
            self._cleanup_turn(state)

    def _commit_terminal(self, state: _TurnState, text: str, tool_calls: list[dict[str, object]] | None = None) -> None:
        if state.options.terminal_validator:
            state.options.terminal_validator(text)
        item = build_assistant_transcript_item(text, tool_calls)
        leave_s = float(getattr(self._config, "leave_timeout_s", 2.0))
        teardown_driver_turn(self._driver, state.slot.handle, state.options.extra_turn_context, leave_s)
        state.slot_released = self._pool.release(state.slot.slot_id, success=True, lease_id=state.slot.lease_id)
        _fail_if(not state.slot_released, PreDispatchResidentError("lease_lost_before_release"))
        state.released_gen = cast(int, state.slot.handle.generation)
        if all((not state.non_committable, state.plan.next_state)):
            binding = SlotBinding(state.slot.slot_id, state.released_gen)
            state.evicted = [b for _, b in self._tracker.commit(state.session_key, state.plan, binding, item)]
            self._close_all(state.evicted)
            state.evicted.clear()
            if isinstance(ctx := state.options.extra_turn_context, dict):
                ctx["_committed_slot"] = (state.session_key, binding)
                if isinstance(sink := ctx.get("_committed_slot_sink"), list):
                    cast(list[Any], sink).append((state.session_key, binding))
        else:
            self._close_binding(_binding_of(self._tracker.invalidate(state.session_key)))
        state.committed_ok = True

    def rebind_assistant_item(self, session_key: str, binding: SlotBinding, item: Any) -> bool:
        return self._tracker.rebind_assistant_item(session_key, binding, item)

    def _cleanup_turn(self, state: _TurnState) -> None:
        try:
            if not state.slot_released:
                if state.dispatched:
                    cancel_driver_turn(self._driver, state.slot.handle, state.options.extra_turn_context)
                self._pool.release(state.slot.slot_id, cancel=True, lease_id=state.slot.lease_id)
                gen = state.slot.handle.generation
                self._close_binding(SlotBinding(state.slot.slot_id, gen) if gen else None)
            elif all((not state.committed_ok, isinstance(state.released_gen, int))):
                self._pool.close_if_idle(state.slot.slot_id, cast(int, state.released_gen))
        except Exception:
            _LOGGER.exception("resident slot cleanup failed")
        if not state.committed_ok:
            try:
                self._close_binding(_binding_of(self._tracker.invalidate(state.session_key)))
                self._close_all(state.evicted)
            except Exception:
                _LOGGER.exception("resident history cleanup failed")

    def _driver_chunks(self, state: _TurnState) -> Iterator[DecodedChunk]:
        hs_s = float(getattr(self._config, "handshake_timeout_s", 10.0))
        idle_s = float(getattr(self._config, "idle_timeout_s", 30.0))
        ctx: dict[str, Any] = {
            "plan": state.plan,
            "history_plan": state.plan,
            "cancel_event": state.options.cancel_event,
            "extra_turn_context": state.options.extra_turn_context,
            "prompt": state.plan.prompt_to_send,
            "timeouts": (hs_s, idle_s),
            "mcp_config": self._config,
        }

        def mark_dispatched() -> None:
            state.dispatched = True

        return stream_driver_turn(self._driver, state.slot.handle, state.envelope, ctx, mark_dispatched)

    @staticmethod
    def _tick_keepalive(cb: Callable[[], bool] | None, last_hb: float) -> float:
        now = time.monotonic()
        res = last_hb
        if all((bool(cb), now - last_hb >= 15.0)):
            _ = cast(Callable[[], bool], cb)()
            res = now
        return res

    @staticmethod
    def _encoded_chunk(decoded: DecodedChunk) -> tuple[str, int]:
        text = str(decoded.text) if decoded.text else ""
        try:
            return text, len(text.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise ResidentStreamError("invalid_upstream_encoding") from exc

    def _close_binding(self, binding: SlotBinding | None) -> None:
        if binding:
            self._pool.close_if_idle(binding.slot_id, binding.generation)

    def _close_all(self, bindings: list[SlotBinding]) -> None:
        for binding in bindings:
            self._close_binding(binding)
