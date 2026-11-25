from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass, replace
from typing import cast

from core.backend_routing_models import TranscriptItem
from core.resident_canonical import _fail_if
from core.resident_turn_envelope import ResidentTurnEnvelope
from core.stdio_resident.types import SlotBinding
from core.tool_emulation import _render_message


@dataclass(frozen=True, slots=True)
class CommittedSessionState:
    slot_id: str
    generation: int
    principal_hash: str
    backend_id: str
    env_digest: str
    system_digest: str
    tool_fingerprint: str
    model: str
    effort: str
    cwd_norm: str
    review_profile: str
    item_digests: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HistoryPlan:
    action: str
    prompt_to_send: str
    requires_slot_reset: bool
    next_state: CommittedSessionState | None
    ephemeral_slot: bool
    reason: str


def build_assistant_transcript_item(text: str, tool_calls: list[dict[str, object]] | None = None) -> TranscriptItem | None:
    calls = tool_calls if tool_calls else []
    rendered = _render_message({"role": "assistant", "content": text, "tool_calls": calls})
    item: TranscriptItem | None = None
    if rendered:
        digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        item = TranscriptItem("assistant", rendered.removeprefix("[assistant]\n"), digest)
    return item


def render_delta_prompt(items: tuple[TranscriptItem, ...]) -> str:
    chat_roles = frozenset({"user", "assistant"})
    rendered = (f"[{item.role}]\n{item.text}" if bool({item.role} & chat_roles) else item.text for item in items)
    return "\n\n".join(rendered)


def _base_state(envelope: ResidentTurnEnvelope) -> CommittedSessionState:
    items = envelope.rpc.items if envelope.rpc else ()
    return CommittedSessionState(
        "",
        0,
        envelope.identity.principal_hash,
        envelope.backend_id,
        envelope.env_digest,
        envelope.system_digest,
        envelope.tool_contract_fingerprint,
        envelope.model,
        envelope.effort,
        envelope.cwd_norm,
        envelope.review_profile,
        tuple(item.digest for item in items),
    )


def _headers(state: CommittedSessionState) -> tuple[str, ...]:
    return (
        state.principal_hash,
        state.backend_id,
        state.env_digest,
        state.system_digest,
        state.tool_fingerprint,
        state.model,
        state.effort,
        state.cwd_norm,
        state.review_profile,
    )


def _plan(action: str, prompt: str, next_state: CommittedSessionState | None, flags: tuple[bool, bool, str]) -> HistoryPlan:
    reset, ephemeral, reason = flags
    return HistoryPlan(action, prompt, reset, next_state, ephemeral, reason)


def _committed_rebase_reason(
    committed: CommittedSessionState | None,
    envelope: ResidentTurnEnvelope,
    next_base: CommittedSessionState,
) -> str:
    reason = ""
    if committed:
        if _headers(committed) != _headers(next_base):
            reason = "header_changed"
        elif any((not envelope.rpc, not bool(getattr(envelope.rpc, "runnable", False)))):
            reason = "non_runnable_transcript"
    return reason


def _plan_ephemeral_or_images(committed: CommittedSessionState | None, envelope: ResidentTurnEnvelope, slot_bound: SlotBinding | None) -> HistoryPlan | None:
    images_present = bool(envelope.images)
    result: HistoryPlan | None = None
    if envelope.identity.ephemeral:
        gen = getattr(slot_bound, "generation", 0)
        reset = any((bool(committed), bool(gen)))
        fallback = envelope.identity.degradation_reason if envelope.identity.degradation_reason else "ephemeral"
        reason = "ephemeral_and_images" if images_present else fallback
        result = _plan("ephemeral", envelope.full_prompt, None, (reset, True, reason))
    elif images_present:
        result = _plan("rebase", envelope.full_prompt, None, (True, True, "images_present"))
    return result


def _plan_warm(committed: CommittedSessionState | None, envelope: ResidentTurnEnvelope, next_base: CommittedSessionState, slot_bound: SlotBinding) -> HistoryPlan:
    c_bind = (committed.slot_id, committed.generation) if committed else None
    result: HistoryPlan
    if any((not committed, (slot_bound.slot_id, slot_bound.generation) != c_bind)):
        result = _plan("rebase", envelope.full_prompt, next_base, (True, False, "warm_slot_binding_mismatch"))
    else:
        c_state = cast(CommittedSessionState, committed)
        count = len(c_state.item_digests)
        incoming = next_base.item_digests
        delta_items = envelope.rpc.items[count:] if envelope.rpc else ()
        extends = all((bool(c_state.item_digests), len(incoming) > count, incoming[:count] == c_state.item_digests))
        has_assistant = any(not bool({item.role} - {"assistant"}) for item in delta_items)
        if all((extends, not has_assistant)):
            result = _plan("delta", render_delta_prompt(delta_items), next_base, (False, False, "history_extended"))
        else:
            result = _plan("rebase", envelope.full_prompt, next_base, (True, False, "history_diverged"))
    return result


def plan_history_transition(
    committed: CommittedSessionState | None,
    envelope: ResidentTurnEnvelope,
    slot_bound: SlotBinding | None = None,
) -> HistoryPlan:
    result = _plan_ephemeral_or_images(committed, envelope, slot_bound)
    if not result:
        next_base = _base_state(envelope)
        rebase_reason = _committed_rebase_reason(committed, envelope, next_base)
        if rebase_reason:
            result = _plan("rebase", envelope.full_prompt, next_base, (True, False, rebase_reason))
        elif not bool(getattr(slot_bound, "generation", 0)):
            action = "rebase" if committed else "cold_bootstrap"
            result = _plan(action, envelope.full_prompt, next_base, (bool(committed), False, action))
        else:
            result = _plan_warm(committed, envelope, next_base, cast(SlotBinding, slot_bound))
    return result


class ResidentHistoryTracker:
    def __init__(self, max_entries: int = 16) -> None:
        _fail_if(max_entries < 1, ValueError("max_entries must be positive"))
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._states: OrderedDict[str, CommittedSessionState] = OrderedDict()
        self._pin_counts: dict[str, int] = {}

    def pin(self, key: str) -> None:
        with self._lock:
            self._pin_counts[key] = self._pin_counts.get(key, 0) + 1

    def unpin(self, key: str) -> None:
        with self._lock:
            count = self._pin_counts.get(key, 0)
            if not bool({count} & {0, 1}):
                self._pin_counts[key] = count - 1
            else:
                self._pin_counts.pop(key, None)

    def get(self, key: str) -> CommittedSessionState | None:
        with self._lock:
            state = self._states.get(key)
            if state:
                self._states.move_to_end(key)
            return state

    def invalidate(self, key: str, expected_slot_id: str | None = None) -> CommittedSessionState | None:
        with self._lock:
            state = self._states.get(key)
            sid = getattr(state, "slot_id", None)
            mismatch = all((not isinstance(expected_slot_id, type(None)), bool(state), sid != expected_slot_id))
            pop = all((bool(state), not mismatch))
            res = self._states.pop(key) if pop else None
            return res

    def _evict_locked(self) -> list[tuple[str, SlotBinding]]:
        evicted: list[tuple[str, SlotBinding]] = []
        while len(self._states) > self._max_entries:
            candidate = next((k for k in self._states if not self._pin_counts.get(k, 0)), None)
            if not candidate:
                break
            state = self._states.pop(candidate)
            evicted.append((candidate, SlotBinding(state.slot_id, state.generation)))
        return evicted

    def commit(
        self,
        key: str,
        plan: HistoryPlan,
        slot_binding: SlotBinding,
        assistant_item: TranscriptItem | None = None,
    ) -> list[tuple[str, SlotBinding]]:
        with self._lock:
            state = plan.next_state
            evicted: list[tuple[str, SlotBinding]] = []
            if state:
                extra = (assistant_item.digest,) if assistant_item else ()
                digests = state.item_digests + extra
                if digests:
                    self._states[key] = replace(state, slot_id=slot_binding.slot_id, generation=slot_binding.generation, item_digests=digests)
                    self._states.move_to_end(key)
                    evicted = self._evict_locked()
            return evicted
