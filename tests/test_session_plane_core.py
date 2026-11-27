from __future__ import annotations

import base64
import json
from itertools import product

import pytest

from core.session_plane import (
    DEFAULT_CAPABILITIES,
    DriverCapabilities,
    PolicyLimits,
    SessionIdentityError,
    SessionIdentityInput,
    SlotRuntimeSnapshot,
    check_epoch_frame,
    decide_session_plan,
    effective_capabilities,
    encode_directive,
    extract_canonical_chat_id,
    resolve_canonical_identity,
    verify_directive,
)


def _identity(**kwargs):
    values = dict(principal_id="p1", backend_id="b1", model_id="m1", effort_level="high", review_profile="zero-canon")
    values.update(kwargs)
    return resolve_canonical_identity(SessionIdentityInput(**values))


def test_partition_matrix_has_no_collisions() -> None:
    parts = set()
    affinities = set()
    for principal, chat, profile, model, effort, backend in product(("p1", "p2"), ("chat-0001", "chat-0002"), ("standard", "zero-canon"), ("m1", "m2"), ("low", "high"), ("b1", "b2")):
        item = _identity(principal_id=principal, backend_id=backend, model_id=model, effort_level=effort, review_profile=profile, headers={"X-DSH-Chat-Id": chat})
        parts.add(item.partition_key)
        affinities.add(item.affinity_uuid5)
    assert len(parts) == len(affinities) == 64


@pytest.mark.parametrize("bad", ["../etc", "short", "   ", "bad\x00id", "x" * 129])
def test_invalid_chat_id_rejected(bad: str) -> None:
    with pytest.raises(SessionIdentityError) as error:
        extract_canonical_chat_id({"X-DSH-Chat-Id": bad}, None, None)
    assert (error.value.http_status, error.value.code) == (400, "ERR_INVALID_SESSION_ID")


def test_conflicts_and_auth() -> None:
    with pytest.raises(SessionIdentityError) as error:
        extract_canonical_chat_id({"X-DSH-Chat-Id": "chat-0001"}, {"session_id": "chat-0002"}, None)
    assert (error.value.http_status, error.value.code) == (409, "SESSION_ID_CONFLICT")
    assert extract_canonical_chat_id({"X-DSH-Chat-Id": "chat-0001"}, {"session_id": "chat-0001"}, None) == "chat-0001"
    with pytest.raises(SessionIdentityError) as error:
        resolve_canonical_identity(SessionIdentityInput(require_auth=True))
    assert (error.value.http_status, error.value.code) == (401, "AUTH_REQUIRED")


def test_unkeyed_zero_canon_is_ephemeral() -> None:
    item = _identity(headers=None)
    assert item.keyed is False and item.isolation_namespace.startswith("zc:eph:")
    plan = decide_session_plan(item, DEFAULT_CAPABILITIES["codex-app-server-v2"], "cold")
    assert plan.process_directive == "EPHEMERAL_KILL_AFTER_TURN"
    assert plan.decision_reason == "UNKEYED_ZC_EPHEMERAL"


def test_keyed_zero_canon_lifecycle() -> None:
    item = _identity(headers={"X-DSH-Chat-Id": "chat-0001"})
    caps = DEFAULT_CAPABILITIES["codex-app-server-v2"]
    cold = decide_session_plan(item, caps, "cold")
    assert (cold.process_directive, cold.context_directive, cold.next_epoch) == ("WARM_SLOT_REUSE", "CONTEXT_RESET_LOGICAL", 1)
    prefix = decide_session_plan(item, caps, "prefix_match", SlotRuntimeSnapshot(True, current_epoch=1))
    assert (prefix.context_directive, prefix.next_epoch) == ("CONTEXT_CONTINUE", 1)
    diverged = decide_session_plan(item, caps, "diverged", SlotRuntimeSnapshot(True, current_epoch=1))
    assert (diverged.context_directive, diverged.next_epoch) == ("CONTEXT_RESET_LOGICAL", 2)
    claude = decide_session_plan(item, DEFAULT_CAPABILITIES["claude-stream-json"], "diverged", SlotRuntimeSnapshot(True, current_epoch=1))
    assert claude.context_directive == "SLOT_HARD_RESET"


def test_capability_drift_and_epoch() -> None:
    caps = DriverCapabilities("v", "p", "stdio_resident", True, True, True, True, False, 1, 2, certified_binary_hash="good")
    assert effective_capabilities("p", runtime_binary_hash="good", registry={"p": caps}).supports_logical_context_reset is True
    assert effective_capabilities("p", runtime_binary_hash="bad", registry={"p": caps}).supports_logical_context_reset is False
    assert check_epoch_frame(1, 2) is False and check_epoch_frame(2, 2) is True


def test_directive_round_trip_and_fail_closed() -> None:
    plan = decide_session_plan(
        _identity(headers={"X-DSH-Chat-Id": "chat-0001"}),
        DEFAULT_CAPABILITIES["codex-app-server-v2"],
        "cold",
        limits=PolicyLimits(config_revision=3),
    )
    secret = b"s" * 32
    encoded = encode_directive(plan, secret, now_s=100.0)
    assert len(encoded.encode()) <= 640
    payload, reason = verify_directive(encoded, secret, now_s=101.0, min_config_revision=3)
    assert reason == "ok" and payload is not None and payload.thread_epoch == 1
    assert verify_directive(encoded[:-1] + ("0" if encoded[-1] != "0" else "1"), secret, now_s=101.0)[0] is None
    assert verify_directive(encoded, secret, now_s=131.0)[1] == "expired"
    assert verify_directive(encoded, secret, now_s=101.0, min_config_revision=4)[1] == "stale_revision"

    head, encoded_payload, signature = encoded.split(".")
    raw = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
    body = json.loads(raw)
    body["process_directive"] = "BAD"
    tampered = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode().rstrip("=")
    assert verify_directive(f"{head}.{tampered}.{signature}", secret)[0] is None


def test_directive_binds_chat_id_hash_and_rejects_oversized_before_decode() -> None:
    import hashlib

    secret = b"s" * 32
    plan = decide_session_plan(_identity(headers={"X-DSH-Chat-Id": "chat-0001"}), DEFAULT_CAPABILITIES["codex-app-server-v2"], "cold")
    payload, reason = verify_directive(encode_directive(plan, secret, now_s=100.0), secret, now_s=101.0)
    assert reason == "ok" and payload is not None
    assert payload.chat_id_hash == hashlib.sha256(b"chat-0001").hexdigest()[:16]
    unkeyed = decide_session_plan(_identity(headers=None), DEFAULT_CAPABILITIES["codex-app-server-v2"], "cold")
    payload2, _ = verify_directive(encode_directive(unkeyed, secret, now_s=100.0), secret, now_s=101.0)
    assert payload2 is not None and payload2.chat_id_hash == ""
    assert verify_directive("v1." + "A" * 700 + ".sig", secret) == (None, "oversized")
