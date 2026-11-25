"""Адаптер явного продолжения сессий (Explicit Resume) и изоляции маршрутов agy-bridge."""
from __future__ import annotations
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from typing import cast, final
from agy_runtime.long_session_config import read_bool_setting, read_float_setting, read_int_setting
from agy_runtime.session_store import CommitPayload, ExplicitSessionStore, load_or_create_hmac_key
from agy_runtime.slot_and_session import resolve_subagent_id
from core import chat_key as _chat_key
from core.hot_session_policy import (
    DecisionAction, ExecutionMode, PolicyConfig, ProjectedMessage, SessionKeyParts, SlotSnapshot,
    SlotState, TurnPolicyInput, build_session_key, compute_history_fingerprints,
    compute_owner_hmac, decide_turn, encode_length_prefixed,
)

_LOOPBACK_HOSTS = frozenset(("127.0.0.1", "::1", "::ffff:127.0.0.1"))
_CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
_EMPTY_SNAP = SlotSnapshot(SlotState.EMPTY, "", "", 0, 0, 0, 0, 0.0, 0.0, 0, 0.0, 0.0)
_TOGGLE_EPOCH_STEP = 1_000_007
_resolve_chat_key = cast("Callable[..., _chat_key.ChatKey]", _chat_key.resolve_chat_key)
_INT_BOUNDS = (("guard_max_bytes", "BRIDGE_HOT_GUARD_MAX_BYTES", 2097152, (1024, 67_108_864)), ("guard_max_messages", "BRIDGE_HOT_GUARD_MAX_MESSAGES", 512, (4, 100_000)), ("max_turns", "BRIDGE_HOT_MAX_TURNS", 30, (1, 1000)), ("supersede_max_per_min", "BRIDGE_HOT_SUPERSEDE_MAX_PER_MIN", 3, (0, 1000)))
_FLT_BOUNDS = (("idle_ttl_s", "BRIDGE_HOT_IDLE_TTL_S", 2700.0, (1.0, 604_800.0)), ("max_ttl_s", "BRIDGE_HOT_MAX_TTL_S", 86400.0, (1.0, 2_592_000.0)), ("in_flight_max_s", "BRIDGE_HOT_IN_FLIGHT_MAX_S", 960.0, (1.0, 86_400.0)))
@dataclass(frozen=True, slots=True)
class RuntimeFlags:
    explicit_plain_enabled: bool = False
    zc_plain_enabled: bool = False
    zc_agentic_enabled: bool = False
    canonical_tools_enabled: bool = False
    epoch: int = 0
    policy: PolicyConfig = PolicyConfig()
@dataclass(frozen=True, slots=True)
class RouteClassification:
    handled: bool
    mode: ExecutionMode
    location_marker: str
@dataclass(frozen=True, slots=True)
class TurnHttpMeta:
    headers: Mapping[str, object]
    client_host: str
    profile_tag: str
    raw_cid: object = None
@dataclass(frozen=True, slots=True)
class TurnPayloadMeta:
    req: Mapping[str, object] | None
    extra: Mapping[str, object]
    model_id: str
    effort: str
    cwd: str
    cwd_invalid: bool
    tools: Sequence[object]
    tool_choice: object = None
    force_cold: bool = False
@dataclass(slots=True)
class ExplicitTurnState:
    handled: bool = False
    sort_keys: bool = False
    is_resumed: bool = False
    conversation_id: str = ""
    force_cold: bool = False
    allow_commit: bool = False
    decision_reason: str = ""
    session_key: str = ""
    owner_token_hash: str = ""
    lease_token: str = ""
    epoch: int = 0
    supersede: bool = False
    expected_gen: int = 0
    expected_stored_digest: str = ""
    projected_input: tuple[ProjectedMessage, ...] = ()
    input_asst_count: int = 0
    finalized: bool = False
def _cjson(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
def read_runtime_flags(config_path: Path | None = None) -> RuntimeFlags:
    rb = read_bool_setting
    ep = rb("bridge_hot_explicit_plain_enabled", "BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED", False, config_path=config_path)
    zp = rb("bridge_hot_zc_plain_enabled", "BRIDGE_HOT_ZC_PLAIN_ENABLED", False, config_path=config_path)
    za = rb("bridge_hot_zc_agentic_enabled", "BRIDGE_HOT_ZC_AGENTIC_ENABLED", False, config_path=config_path)
    cn = rb("bridge_hot_canonical_tools_enabled", "BRIDGE_HOT_CANONICAL_TOOLS_ENABLED", False, config_path=config_path)
    epoch = read_int_setting("bridge_hot_epoch", "BRIDGE_HOT_EPOCH", 0, (0, 1_000_000), config_path=config_path)
    kw: dict[str, int | float | bool] = {"enabled": any((ep, zp, za))}
    for k, env, d, b in _INT_BOUNDS:
        kw[k] = read_int_setting(f"bridge_hot_{k}", env, d, b, config_path=config_path)
    for k, env, d, b in _FLT_BOUNDS:
        kw[k] = read_float_setting(f"bridge_hot_{k}", env, d, b, config_path=config_path)
    return RuntimeFlags(ep, zp, za, cn, epoch, PolicyConfig(**cast("dict[str, object]", kw)))  # type: ignore[arg-type]
def _header_str(headers: Mapping[str, object] | None, name: str) -> str:
    if headers is None:
        return ""
    if (val := headers.get(name)) is not None:
        return str(val)
    return next((str(headers[k]) for k in headers if k.lower() == name.lower()), "")
def extract_verified_token(headers: Mapping[str, object] | None) -> str:
    auth = _header_str(headers, "Authorization").strip()
    is_b = auth.lower().startswith("bearer ")
    if is_b and (tok := auth[7:].strip()):
        return tok
    return key if (key := _header_str(headers, "x-api-key").strip()) else ("" if is_b else auth)
def _tool_choice_is_none(tool_choice: object) -> bool:
    return tool_choice.strip().lower() == "none" if isinstance(tool_choice, str) else (isinstance(tool_choice, Mapping) and str(cast("Mapping[str, object]", tool_choice).get("type") or "").strip().lower() == "none")
def classify_route(profile_tag: str, tools_count: int, explicit_chat_id: str, cwd: str, flags: RuntimeFlags) -> RouteClassification:
    if not explicit_chat_id:
        return RouteClassification(False, ExecutionMode.PLAIN, "")
    if profile_tag == "standard":
        return RouteClassification(tools_count == 0 and flags.explicit_plain_enabled, ExecutionMode.PLAIN, cwd if tools_count == 0 else "")
    if profile_tag == "zero-canon":
        en, mode = (flags.zc_plain_enabled, ExecutionMode.PLAIN) if tools_count == 0 else (flags.zc_agentic_enabled, ExecutionMode.AGENTIC)
        return RouteClassification(en, mode, "zero-canon-ephemeral")
    return RouteClassification(False, ExecutionMode.PLAIN, "")
def estimate_raw_messages_bytes(messages: Sequence[object], limit: int) -> int:
    total, stack = 0, list(messages)
    while stack:
        item = stack.pop()
        if isinstance(item, (str, bytes, bytearray)):
            total += len(item) if isinstance(item, (bytes, bytearray)) else len(item.encode("utf-8", "replace")) + 2
        elif isinstance(item, dict):
            d = cast("dict[object, object]", item)
            total, _ = total + 4 * len(d), [stack.extend((k, v)) for k, v in d.items()]
        elif isinstance(item, (list, tuple)):
            seq = cast("Sequence[object]", item)
            total, _ = total + 2 * len(seq), stack.extend(seq)
        else:
            total += len(str(item).encode("utf-8", "replace"))
        if total > limit:
            return total
    return total
def _parse_json_dict(raw: object) -> dict[str, object]:
    if isinstance(raw, dict):
        return cast("dict[str, object]", raw)
    if isinstance(raw, str) and raw.strip():
        with suppress(ValueError):
            return cast("dict[str, object]", p) if isinstance((p := cast("object", json.loads(raw))), dict) else {}
    return {}
def canonicalize_tool_calls(raw_calls: object) -> str:
    if not isinstance(raw_calls, (list, tuple)) or not raw_calls:
        return ""
    items = [{"id": str(c.get("id") or ""), "name": str(fn.get("name") or c.get("name") or ""), "arguments": _parse_json_dict(fn.get("arguments") if fn.get("arguments") is not None else c.get("arguments"))} for c in (cast("dict[str, object]", r) for r in cast("Sequence[object]", raw_calls) if isinstance(r, dict)) for fn in (cast("dict[str, object]", c["function"]) if isinstance(c.get("function"), dict) else {},)]
    return _cjson(items) if items else ""
def _extract_part(item: object, img_counter: list[int]) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return ""
    m = cast("dict[str, object]", item)
    if m.get("type") == "image_url":
        img_counter[0] += 1
        return f"[image {img_counter[0]}]"
    return "" if (t := m.get("text")) is None else str(t)
def _extract_text(content: object, img_counter: list[int]) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p for p in (_extract_part(x, img_counter) for x in cast("list[object]", content)) if p)
    return "" if content is None else str(content)
def project_messages(messages: Sequence[object]) -> list[ProjectedMessage]:
    ic = [0]
    return [ProjectedMessage(str(d.get("role") or "user").strip().lower() or "user", _extract_text(d.get("content"), ic), str(d.get("name") or ""), str(d.get("tool_call_id") or ""), canonicalize_tool_calls(d.get("tool_calls"))) for d in (cast("dict[str, object]", m) for m in messages if isinstance(m, dict))]
def _tool_sort_key(item: object) -> tuple[str, str]:
    if not isinstance(item, dict):
        return "", ""
    m = cast("dict[str, object]", item)
    fn = cast("dict[str, object]", m["function"]) if isinstance(m.get("function"), dict) else m
    return str(fn.get("name") or ""), _cjson(cast("dict[str, object]", rp) if isinstance((rp := fn.get("parameters")), dict) else {})
def compute_context_digest(messages: Sequence[object], tools: Sequence[object], tool_choice: object, sort_keys: bool) -> str:
    sys_items = [{"role": r, "name": str(d.get("name") or ""), "text": _extract_text(d.get("content"), [0])} for d in (cast("dict[str, object]", m) for m in messages if isinstance(m, dict)) if (r := str(d.get("role") or "").strip().lower()) in ("system", "developer")]
    ordered = sorted(tools, key=_tool_sort_key) if sort_keys else list(tools)
    return hashlib.sha256(encode_length_prefixed((_cjson(sys_items), _cjson(ordered), _cjson(tool_choice), "1" if sort_keys else "0"))).hexdigest()

def _cid_value_bad(raw_cid: object) -> tuple[str, bool]:
    if raw_cid is None:
        return "", False
    if not isinstance(raw_cid, str):
        return "", True
    val = raw_cid.strip()
    return (val, not _CID_RE.fullmatch(val)) if val else ("", False)
@final
class ExplicitResumeAdapter:
    def __init__(self, state_dir: Path, config_path: Path | None = None, *, store: ExplicitSessionStore | None = None) -> None:
        self._state_dir, self._config_path, self._lock = state_dir, config_path, threading.Lock()
        self._last_flags = read_runtime_flags(config_path)
        self._toggle_epoch, self._effective_epoch, self._store = 0, self._last_flags.epoch, store
        self._hmac_key = load_or_create_hmac_key(state_dir / ".owner_hmac_key") if store is not None else b""
    def _ensure_store(self, flags: RuntimeFlags) -> tuple[ExplicitSessionStore, bytes]:
        with self._lock:
            if not self._hmac_key:
                self._hmac_key = load_or_create_hmac_key(self._state_dir / ".owner_hmac_key")
            if self._store is None:
                self._store = ExplicitSessionStore(self._state_dir, policy=flags.policy, epoch=self._effective_epoch)
            return self._store, self._hmac_key
    def _sync_epoch(self, flags: RuntimeFlags) -> int:
        with self._lock:
            prev = self._last_flags
            turned_off = any(getattr(prev, k) and not getattr(flags, k) for k in ("explicit_plain_enabled", "zc_plain_enabled", "zc_agentic_enabled"))
            if turned_off or flags.epoch != prev.epoch:
                self._toggle_epoch += 1
                self._effective_epoch = flags.epoch + self._toggle_epoch * _TOGGLE_EPOCH_STEP
                if self._store is not None:
                    _ = self._store.on_epoch_change(self._effective_epoch)
            self._last_flags = flags
            return self._effective_epoch
    def prepare_turn(self, http_meta: TurnHttpMeta, payload_meta: TurnPayloadMeta, now_s: float | None = None) -> ExplicitTurnState:
        now, flags = time.time() if now_s is None else float(now_s), read_runtime_flags(self._config_path)
        epoch = self._sync_epoch(flags)
        chat = _resolve_chat_key(payload_meta.req, http_meta.headers, payload_meta.extra, sources=_chat_key.SOURCES_SESSION_ID)
        sub_id, sub_bad = resolve_subagent_id(http_meta.headers)
        explicit_cid = "" if any((chat.invalid, sub_bad)) else chat.value
        tools_cnt = 0 if _tool_choice_is_none(payload_meta.tool_choice) else len(payload_meta.tools)
        route = classify_route(http_meta.profile_tag, tools_cnt, explicit_cid, "" if payload_meta.cwd_invalid else payload_meta.cwd, flags)
        if not route.handled:
            return ExplicitTurnState(handled=False)
        val_c, cid_bad = _cid_value_bad(http_meta.raw_cid)
        if any((payload_meta.force_cold, cid_bad, all((http_meta.profile_tag == "standard", payload_meta.cwd_invalid)))):
            return ExplicitTurnState(handled=True, sort_keys=flags.canonical_tools_enabled, force_cold=True, allow_commit=False, decision_reason="force_cold", epoch=epoch)
        return self._decide_state((http_meta, payload_meta, route, flags), (explicit_cid, sub_id, val_c), now, epoch)
    def _decide_state(self, meta: tuple[TurnHttpMeta, TurnPayloadMeta, RouteClassification, RuntimeFlags], ids: tuple[str, str, str], now: float, epoch: int) -> ExplicitTurnState:
        hm, pm, route, flags = meta
        explicit_cid, sub_id, client_cid = ids
        store, hkey = self._ensure_store(flags)
        tok = extract_verified_token(hm.headers)
        principal = _header_str(hm.headers, "X-Client-Id").strip().encode("ascii", "ignore").decode("ascii")[:64]
        owner_ok, owner_hash = all((hm.client_host in _LOOPBACK_HOSTS, len(tok) >= 8)), compute_owner_hmac(hkey, tok, principal)
        raw_msgs = pm.req.get("messages") if isinstance(pm.req, Mapping) else None
        msgs = list(cast("Sequence[object]", raw_msgs)) if isinstance(raw_msgs, (list, tuple)) else []
        skey = build_session_key(SessionKeyParts("v2", owner_hash, explicit_cid, sub_id, pm.model_id, pm.effort, route.mode, hm.profile_tag, route.location_marker, compute_context_digest(msgs, pm.tools, pm.tool_choice, flags.canonical_tools_enabled)))
        slot, recent_sup = (_EMPTY_SNAP, 0) if not skey else (store.evict_if_expired(skey, now), store.peek(skey, now))[1]
        pol = replace(flags.policy, enabled=True)
        raw_bytes = estimate_raw_messages_bytes(msgs, pol.guard_max_bytes)
        proj = project_messages(msgs) if raw_bytes <= pol.guard_max_bytes else []
        fp = compute_history_fingerprints(proj, slot.stored_len, hkey, raw_bytes, pol)
        dec = decide_turn(slot, TurnPolicyInput(owner_ok, owner_hash, explicit_cid, client_cid, fp, now, epoch, recent_sup), pol)
        st = ExplicitTurnState(True, flags.canonical_tools_enabled, False, "", False, dec.allow_commit, dec.reason.value, skey, owner_hash, "", epoch, dec.supersede, dec.expected_gen, dec.expected_stored_digest, tuple(proj), fp.assistant_count)
        if dec.action == DecisionAction.RESUME:
            if (lease := store.claim_resume(skey, dec.cid, now, epoch)):
                st.is_resumed, st.conversation_id, st.lease_token, st.allow_commit = True, dec.cid, lease, True
            else:
                st.allow_commit, st.decision_reason = False, "claim_race"
        elif all((dec.action == DecisionAction.COLD_SEED, dec.evict_expired_first, skey)):
            _ = store.evict_if_expired(skey, now)
        return st
    def on_hot_failure(self, state: ExplicitTurnState, *, post_spawn: bool = True) -> None:
        if all((state.handled, state.lease_token, self._store is not None)):
            _ = cast("ExplicitSessionStore", self._store).abort_turn(state.session_key, state.lease_token, post_spawn=post_spawn)
            was_resumed = state.is_resumed
            state.lease_token, state.is_resumed, state.conversation_id, state.supersede, state.allow_commit = "", False, "", False, all((was_resumed, post_spawn))
    def finalize_turn(self, state: ExplicitTurnState, out: Mapping[str, object], commit_act: str, cid_re: re.Pattern[str]) -> bool:
        if any((not state.handled, state.finalized)):
            return False
        state.finalized, out_cid = True, str(out.get("conversation_id") or "")
        if all((commit_act == "commit", state.allow_commit, cid_re.fullmatch(out_cid), self._store is not None)):
            msgs = (*state.projected_input, ProjectedMessage("assistant", str(out.get("text") or ""), "", "", canonicalize_tool_calls(out.get("tool_calls"))))
            fp = compute_history_fingerprints(msgs, 0, self._hmac_key, 0, PolicyConfig(enabled=True, guard_max_bytes=10**9, guard_max_messages=10**6))
            ok = cast("ExplicitSessionStore", self._store).commit_pending(CommitPayload(state.session_key, state.owner_token_hash, out_cid, fp.full_digest, len(msgs), state.input_asst_count + 1, state.epoch, time.time(), state.lease_token, state.supersede, state.expected_gen, state.expected_stored_digest))
            state.lease_token = ""
            return ok
        if all((state.lease_token, self._store is not None)):
            _, state.lease_token = cast("ExplicitSessionStore", self._store).abort_turn(state.session_key, state.lease_token, post_spawn=True), ""
        return False
    def release_if_unfinalized(self, state: ExplicitTurnState, *, post_spawn: bool = False) -> None:
        if state.handled and not state.finalized and state.lease_token and self._store is not None:
            _ = self._store.abort_turn(state.session_key, state.lease_token, post_spawn=post_spawn)
            state.lease_token, state.finalized = "", True
    def close(self) -> None:
        if self._store is not None:
            self._store.close()
@final
class _AdapterRegistry:
    def __init__(self) -> None:
        self._lock, self._items = threading.Lock(), dict[tuple[Path, Path | None], ExplicitResumeAdapter]()
    def get(self, state_dir: Path, config_path: Path | None = None) -> ExplicitResumeAdapter:
        key = (state_dir.resolve(), None if config_path is None else config_path.resolve())
        with self._lock:
            if (adapter := self._items.get(key)) is None:
                adapter = self._items[key] = ExplicitResumeAdapter(key[0], key[1])
            return adapter
    def reset(self) -> None:
        with self._lock:
            items = list(self._items.values())
            self._items.clear()
        for adapter in items:
            adapter.close()
_REGISTRY = _AdapterRegistry()
def get_explicit_adapter(state_dir: Path, config_path: Path | None = None) -> ExplicitResumeAdapter:
    return _REGISTRY.get(state_dir, config_path)
def reset_explicit_adapters_for_tests() -> None:
    _REGISTRY.reset()
