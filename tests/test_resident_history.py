from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from core.resident_history import (
    ResidentHistoryTracker,
    build_assistant_transcript_item,
    plan_history_transition,
)
from core.resident_identity import ResidentIdentity
from core.resident_turn_envelope import (
    ResidentTurnEnvelope,
    _canon_key,
    _canonical,
    normalize_child_env,
)
from core.stdio_resident.types import SlotBinding
from core.backend_routing_models import Transcript, TranscriptItem

_SECRET = b"0123456789abcdef0123456789abcdef"


def _identity(*, ephemeral: bool = False) -> ResidentIdentity:
    return ResidentIdentity(
        "owner",
        "chat",
        ephemeral,
        "" if ephemeral else "label",
        "turn",
        "",
        "",
        "session-key",
        "forced_ephemeral" if ephemeral else "",
    )


def _item(role: str, text: str) -> TranscriptItem:
    import hashlib

    return TranscriptItem(role, text, hashlib.sha256(f"{role}:{text}".encode()).hexdigest())


def _rpc(items: tuple[TranscriptItem, ...], runnable: bool = True) -> Transcript:
    return cast(Transcript, SimpleNamespace(items=items, runnable=runnable))


def _envelope(
    items: tuple[TranscriptItem, ...] = (),
    *,
    images: tuple[Any, ...] = (),
    identity: ResidentIdentity | None = None,
    fwd_env: dict[str, str] | None = None,
) -> ResidentTurnEnvelope:
    return ResidentTurnEnvelope(
        identity=_identity() if identity is None else identity,
        backend_id="backend",
        model="model",
        effort="medium",
        cwd_norm="/work",
        secret=_SECRET,
        rpc=_rpc(items),
        full_prompt="FULL",
        images=cast(Any, images),
        fwd_env={} if fwd_env is None else fwd_env,
    )


def test_cold_bootstrap_for_unbound_slot() -> None:
    envelope = _envelope((_item("user", "U1"),))
    assert plan_history_transition(None, envelope, None).action == "cold_bootstrap"
    assert plan_history_transition(None, envelope, SlotBinding("slot", 0)).action == "cold_bootstrap"


def test_warm_binding_mismatch_rebases() -> None:
    envelope = _envelope((_item("user", "U1"),))
    cold = plan_history_transition(None, envelope)
    tracker = ResidentHistoryTracker()
    tracker.commit("session-key", cold, SlotBinding("slot-a", 1))
    committed = tracker.get("session-key")
    plan = plan_history_transition(committed, envelope, SlotBinding("slot-b", 1))
    assert plan.action == "rebase"
    assert plan.reason == "warm_slot_binding_mismatch"


def test_delta_after_tool_only_assistant_item() -> None:
    user_one = _item("user", "U1")
    initial = _envelope((user_one,))
    cold = plan_history_transition(None, initial)
    assistant = build_assistant_transcript_item(
        "",
        [{"id": "call-1", "type": "function", "function": {"name": "f", "arguments": "{}"}}],
    )
    assert assistant is not None
    tracker = ResidentHistoryTracker()
    binding = SlotBinding("slot", 1)
    tracker.commit("session-key", cold, binding, assistant)
    user_two = _item("user", "U2")
    extended = _envelope((user_one, assistant, user_two))
    plan = plan_history_transition(tracker.get("session-key"), extended, binding)
    assert plan.action == "delta"
    assert plan.prompt_to_send == "[user]\nU2"


def test_replay_shrink_and_edit_rebase() -> None:
    first = _item("user", "U1")
    second = _item("user", "U2")
    original = _envelope((first, second))
    tracker = ResidentHistoryTracker()
    binding = SlotBinding("slot", 1)
    tracker.commit("session-key", plan_history_transition(None, original), binding)
    committed = tracker.get("session-key")
    variants = (
        _envelope((first, second)),
        _envelope((first,)),
        _envelope((_item("user", "edited"), second)),
    )
    assert all(plan_history_transition(committed, value, binding).action == "rebase" for value in variants)


def test_images_use_ephemeral_slot() -> None:
    plan = plan_history_transition(None, _envelope(images=(object(),)))
    assert plan.action == "rebase"
    assert plan.ephemeral_slot
    assert plan.next_state is None


def test_canonical_is_injective_and_deterministic() -> None:
    first = {"tuple": (1, 2), "set": {3, 2}, "map": {"b": 2, "a": 1}}
    second = {"map": {"a": 1, "b": 2}, "set": {2, 3}, "tuple": (1, 2)}
    assert _canon_key(_canonical(first)) == _canon_key(_canonical(second))
    assert _canonical((1, 2)) != _canonical([1, 2])
    with pytest.raises(TypeError, match="unsupported non-JSON value"):
        _canonical(object())


def test_normalize_env_is_allowlist_first_and_denylist_wins() -> None:
    default = normalize_child_env(
        {
            "LANG": "C.UTF-8",
            "TZ": "UTC",
            "CLAUDE_CONFIG_DIR": "/x",
            "OPENAI_API_BASE": "https://example.invalid",
            "HF_TOKEN": "secret",
            "K": "value",
        }
    )
    assert dict(default) == {"LANG": "C.UTF-8", "TZ": "UTC"}
    explicit = normalize_child_env(
        {"LANG": "C", "K": "one", "HF_TOKEN": "secret", "OPENAI_API_BASE": "x"},
        allowed_keys=frozenset({"LANG", "K", "HF_TOKEN", "OPENAI_API_BASE"}),
        extra_denied_prefixes=("OPENAI_",),
    )
    assert dict(explicit) == {"LANG": "C", "K": "one"}
    changed = normalize_child_env(
        {"LANG": "C", "K": "two"},
        allowed_keys=frozenset({"LANG", "K"}),
    )
    assert _envelope(fwd_env=dict(explicit)).env_digest != _envelope(fwd_env=dict(changed)).env_digest


def test_envelope_secret_is_init_only_and_validated() -> None:
    envelope = _envelope()
    assert not hasattr(envelope, "secret")
    with pytest.raises(ValueError, match="invalid_hmac_secret"):
        ResidentTurnEnvelope(
            identity=_identity(),
            backend_id="backend",
            model="model",
            effort="medium",
            cwd_norm="/work",
            secret=b"short",
        )


def test_pin_aware_lru_eviction() -> None:
    tracker = ResidentHistoryTracker(max_entries=1)
    first_envelope = _envelope((_item("user", "A"),))
    second_envelope = _envelope((_item("user", "B"),))
    first_plan = plan_history_transition(None, first_envelope)
    second_plan = plan_history_transition(None, second_envelope)
    tracker.commit("first", first_plan, SlotBinding("slot-a", 1))
    tracker.pin("first")
    evicted = tracker.commit("second", second_plan, SlotBinding("slot-b", 1))
    assert evicted == [("second", SlotBinding("slot-b", 1))]
    assert tracker.get("first") is not None
    tracker.unpin("first")
    evicted = tracker.commit("second", second_plan, SlotBinding("slot-b", 1))
    assert evicted == [("first", SlotBinding("slot-a", 1))]



def test_invalidate_expected_slot_id_guard() -> None:
    tracker = ResidentHistoryTracker()
    tracker.commit("k", plan_history_transition(None, _envelope((_item("user", "A"),))), SlotBinding("s1", 1))
    assert tracker.invalidate("k", expected_slot_id="wrong") is None
    assert tracker.get("k") is not None
    assert tracker.invalidate("k", expected_slot_id="s1") is not None
    assert tracker.get("k") is None


def test_envelope_nesting_too_deep_vs_value_error() -> None:
    from core.resident_identity import ResidentRequestError
    from core.resident_turn_envelope import _translate_depth_error

    nested: Any = "leaf"
    for _ in range(70):
        nested = [nested]
    with pytest.raises(ResidentRequestError):
        ResidentTurnEnvelope(identity=_identity(), backend_id="b", model="m", effort="low", cwd_norm="/w", secret=_SECRET, tool_choice=nested)
    with pytest.raises(ValueError, match="other"):
        _translate_depth_error(ValueError("other"))
