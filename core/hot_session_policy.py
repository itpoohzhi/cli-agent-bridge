from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac


class ExecutionMode(Enum):
    PLAIN = "plain"
    AGENTIC = "agentic"


class SlotState(Enum):
    EMPTY = "empty"
    UNCONFIRMED = "unconfirmed"
    READY = "ready"
    IN_FLIGHT = "in_flight"
    EXPIRED = "expired"
    CORRUPT = "corrupt"


class SlotEvent(Enum):
    CLAIM_RESUME = "claim_resume"
    TURN_COMMIT_PENDING = "turn_commit_pending"
    PERSIST_OK = "persist_ok"
    PERSIST_FAIL = "persist_fail"
    TURN_ABORT_PRE_SPAWN = "turn_abort_pre_spawn"
    TURN_ABORT_POST_SPAWN = "turn_abort_post_spawn"
    TTL_EXCEEDED = "ttl_exceeded"
    INVALIDATE = "invalidate"
    CORRUPT_DETECTED = "corrupt_detected"
    EVICT = "evict"
    EPOCH_CHANGED = "epoch_changed"


class DecisionAction(Enum):
    RESUME = "resume"
    COLD_SEED = "cold_seed"
    COLD_BYPASS = "cold_bypass"
    COLD_REJECT = "cold_reject"


class DecisionReason(Enum):
    APPEND_ONLY_MATCH = "append_only_match"
    DISABLED = "disabled"
    MISSING_OWNER_TOKEN = "missing_owner_token"
    NO_EXPLICIT_CHAT_ID = "no_explicit_chat_id"
    UNOWNED_EXPLICIT_CID = "unowned_explicit_cid"
    GUARD_BOUND_BYTES = "guard_bound_bytes"
    GUARD_BOUND_MSGS = "guard_bound_msgs"
    SLOT_EMPTY = "slot_empty"
    SLOT_EXPIRED = "slot_expired"
    SLOT_CORRUPT = "slot_corrupt"
    SLOT_IN_FLIGHT = "slot_in_flight"
    SLOT_UNCONFIRMED = "slot_unconfirmed"
    NO_ASSISTANT_HISTORY = "no_assistant_history"
    HISTORY_DIVERGED_SUPERSEDE = "history_diverged_supersede"
    HISTORY_DIVERGED_RATE_LIMITED = "history_diverged_rate_limited"


@dataclass(frozen=True, slots=True)
class SessionKeyParts:
    schema_version: str
    owner_token_hash: str
    explicit_chat_id: str
    subagent_id: str
    model: str
    effort: str
    effective_mode: ExecutionMode
    profile_marker: str
    location_marker: str
    context_digest: str


@dataclass(frozen=True, slots=True)
class ProjectedMessage:
    role: str
    text: str
    name: str
    tool_call_id: str
    tool_calls_canonical: str


@dataclass(frozen=True, slots=True)
class HistoryFingerprints:
    message_count: int
    assistant_count: int
    prefix_digest: str
    full_digest: str
    raw_bytes: int
    bounded: bool
    bound_reason: DecisionReason | None


@dataclass(frozen=True, slots=True)
class SlotSnapshot:
    state: SlotState
    cid: str
    stored_digest: str
    stored_len: int
    stored_asst: int
    gen: int
    epoch: int
    created_s: float
    last_used_s: float
    turns: int
    in_flight_since_s: float = 0.0
    unconfirmed_since_s: float = 0.0


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    enabled: bool = False
    guard_max_bytes: int = 2097152
    guard_max_messages: int = 512
    idle_ttl_s: float = 2700.0
    max_ttl_s: float = 86400.0
    max_turns: int = 30
    in_flight_max_s: float = 960.0
    unconfirmed_max_s: float = 30.0
    supersede_max_per_min: int = 3
    allow_keyed_single_turn: bool = False


@dataclass(frozen=True, slots=True)
class TurnPolicyInput:
    owner_verified: bool
    owner_token_hash: str
    explicit_chat_id: str
    client_cid: str
    history: HistoryFingerprints
    now_s: float
    config_epoch: int
    recent_supersedes: int = 0


@dataclass(frozen=True, slots=True)
class TurnDecision:
    action: DecisionAction
    reason: DecisionReason
    allow_commit: bool
    cid: str = ""
    supersede: bool = False
    expected_gen: int = 0
    expected_stored_digest: str = ""
    evict_expired_first: bool = False


@dataclass(frozen=True, slots=True)
class TransitionOutcome:
    next_state: SlotState
    valid: bool
    no_op: bool = False


_A, _R, _S, _E = DecisionAction, DecisionReason, SlotState, SlotEvent
_CM = (_S.EMPTY, _S.UNCONFIRMED, _S.READY, _S.IN_FLIGHT)
_RS = (_E.PERSIST_FAIL, _E.CORRUPT_DETECTED, _E.INVALIDATE, _E.EPOCH_CHANGED)
SLOT_TRANSITIONS: Mapping[tuple[SlotState, SlotEvent], SlotState] = {
    **{(s, _E.TURN_COMMIT_PENDING): _S.UNCONFIRMED for s in _CM},
    **{(s, _E.EVICT): _S.EMPTY for s in (_S.UNCONFIRMED, _S.READY, _S.EXPIRED)},
    **{(s, _E.TTL_EXCEEDED): _S.EMPTY for s in (_S.UNCONFIRMED, _S.IN_FLIGHT)},
    **{(s, e): _S.EMPTY for s in _S for e in _RS},
    (_S.UNCONFIRMED, _E.PERSIST_OK): _S.READY,
    (_S.READY, _E.CLAIM_RESUME): _S.IN_FLIGHT,
    (_S.READY, _E.TTL_EXCEEDED): _S.EXPIRED,
    (_S.IN_FLIGHT, _E.TURN_ABORT_PRE_SPAWN): _S.READY,
    (_S.IN_FLIGHT, _E.TURN_ABORT_POST_SPAWN): _S.EMPTY,
}


def encode_length_prefixed(parts: Sequence[str]) -> bytes:
    raws = [p.encode("utf-8") for p in parts]
    return b"".join(f"{len(b)}:".encode("ascii") + b + b";" for b in raws)


def compute_owner_hmac(
    hmac_key: bytes, verified_token: str, client_principal: str = ""
) -> str:
    if not hmac_key or len(verified_token) < 8:
        return ""
    msg = encode_length_prefixed(("owner:v1", verified_token, client_principal))
    return hmac.new(hmac_key, msg, hashlib.sha256).hexdigest()


def build_session_key(parts: SessionKeyParts) -> str:
    p = parts
    if not p.owner_token_hash or not p.explicit_chat_id or not p.context_digest:
        return ""
    a = (p.schema_version, p.owner_token_hash, p.explicit_chat_id, p.subagent_id)
    b = (p.model, p.effort, p.effective_mode.value, p.profile_marker)
    c = (p.location_marker, p.context_digest)
    return hashlib.sha256(encode_length_prefixed(a + b + c)).hexdigest()


def compute_history_fingerprints(
    messages: Sequence[ProjectedMessage],
    target_prefix_len: int,
    hmac_key: bytes,
    raw_bytes: int,
    cfg: PolicyConfig,
) -> HistoryFingerprints:
    n = len(messages)
    if raw_bytes > cfg.guard_max_bytes:
        return HistoryFingerprints(n, 0, "", "", raw_bytes, False, _R.GUARD_BOUND_BYTES)
    if n > cfg.guard_max_messages:
        return HistoryFingerprints(n, 0, "", "", raw_bytes, False, _R.GUARD_BOUND_MSGS)
    hm, asst, prefix = hmac.new(hmac_key, digestmod=hashlib.sha256), 0, ""
    for idx, m in enumerate(messages):
        asst += int(m.role == "assistant")
        row = (m.role, m.text, m.name, m.tool_call_id, m.tool_calls_canonical)
        hm.update(encode_length_prefixed(row))
        if idx + 1 == target_prefix_len:
            prefix = hm.copy().hexdigest()
    return HistoryFingerprints(n, asst, prefix, hm.hexdigest(), raw_bytes, True, None)


def transition(state: SlotState, event: SlotEvent) -> TransitionOutcome:
    nxt = SLOT_TRANSITIONS.get((state, event))
    return TransitionOutcome(nxt or _S.EMPTY, nxt is not None)


def is_slot_expired(slot: SlotSnapshot, now_s: float, cfg: PolicyConfig) -> bool:
    s = slot.state
    if s == _S.READY:
        a, b = now_s - slot.last_used_s, now_s - slot.created_s
        return a > cfg.idle_ttl_s or b > cfg.max_ttl_s or slot.turns >= cfg.max_turns
    if s == _S.IN_FLIGHT:
        return now_s - slot.in_flight_since_s > cfg.in_flight_max_s
    if s == _S.UNCONFIRMED:
        return now_s - slot.unconfirmed_since_s > cfg.unconfirmed_max_s
    return s == _S.EXPIRED


def _check_pre(req: TurnPolicyInput, cfg: PolicyConfig) -> TurnDecision | None:
    checks = (
        (cfg.enabled, _R.DISABLED),
        (req.owner_verified and bool(req.owner_token_hash), _R.MISSING_OWNER_TOKEN),
        (bool(req.explicit_chat_id), _R.NO_EXPLICIT_CHAT_ID),
        (req.history.bounded, req.history.bound_reason or _R.GUARD_BOUND_BYTES),
    )
    r = next((rsn for ok, rsn in checks if not ok), None)
    return None if r is None else TurnDecision(_A.COLD_BYPASS, r, False)


def _ready(slot: SlotSnapshot, req: TurnPolicyInput, cfg: PolicyConfig) -> TurnDecision:
    if req.client_cid and req.client_cid != slot.cid:
        return TurnDecision(_A.COLD_REJECT, _R.UNOWNED_EXPLICIT_CID, False)
    if req.history.assistant_count < 1 and not cfg.allow_keyed_single_turn:
        return TurnDecision(_A.COLD_REJECT, _R.NO_ASSISTANT_HISTORY, False)
    h, ok = req.history, req.history.message_count > slot.stored_len
    if ok and h.assistant_count >= slot.stored_asst and slot.stored_asst >= 1:
        if hmac.compare_digest(h.prefix_digest, slot.stored_digest):
            return TurnDecision(_A.RESUME, _R.APPEND_ONLY_MATCH, True, cid=slot.cid)
    if req.recent_supersedes < cfg.supersede_max_per_min:
        return TurnDecision(_A.COLD_SEED, _R.HISTORY_DIVERGED_SUPERSEDE, True, "", True, slot.gen, slot.stored_digest)
    return TurnDecision(_A.COLD_REJECT, _R.HISTORY_DIVERGED_RATE_LIMITED, False)


def decide_turn(
    slot: SlotSnapshot, req: TurnPolicyInput, cfg: PolicyConfig
) -> TurnDecision:
    if (blocked := _check_pre(req, cfg)) is not None:
        return blocked
    st, td = slot.state, TurnDecision
    if st in (_S.IN_FLIGHT, _S.UNCONFIRMED):
        if is_slot_expired(slot, req.now_s, cfg):
            return td(_A.COLD_SEED, _R.SLOT_EXPIRED, True, "", False, 0, "", True)
        r = _R.SLOT_IN_FLIGHT if st == _S.IN_FLIGHT else _R.SLOT_UNCONFIRMED
        return td(_A.COLD_REJECT, r, False)
    if st == _S.CORRUPT:
        return td(_A.COLD_SEED, _R.SLOT_CORRUPT, True, "", False, 0, "", True)
    if st in (_S.EMPTY, _S.EXPIRED) or is_slot_expired(slot, req.now_s, cfg):
        if req.client_cid:
            return td(_A.COLD_REJECT, _R.UNOWNED_EXPLICIT_CID, False)
        rsn = _R.SLOT_EMPTY if st == _S.EMPTY else _R.SLOT_EXPIRED
        return td(_A.COLD_SEED, rsn, True, "", False, 0, "", st != _S.EMPTY)
    return _ready(slot, req, cfg)
