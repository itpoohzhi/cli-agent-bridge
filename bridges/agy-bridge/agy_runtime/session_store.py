from __future__ import annotations
from collections import OrderedDict
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass, field
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import cast, final
from core.hot_session_policy import PolicyConfig, SlotEvent, SlotSnapshot, SlotState, is_slot_expired, transition

_S, _E, _HMAC_LEN, _MODE_0600, _SCHEMA_VER, _STORE_FILE = SlotState, SlotEvent, 32, 0o600, 2, "sessions_explicit.json"
_DISK_KEYS = ("owner_token_hash", "cid", "stored_digest", "stored_len", "stored_asst", "gen", "epoch", "turns", "created_s", "last_used_s")
_EMPTY_SNAP = SlotSnapshot(_S.EMPTY, "", "", 0, 0, 0, 0, 0.0, 0.0, 0, 0.0, 0.0)

@dataclass(frozen=True, slots=True)
class StoreConfig:
    max_sessions: int = 1024
    max_per_owner: int = 256
    corrupt_keep: int = 3
    supersede_window_s: float = 60.0
@dataclass(frozen=True, slots=True)
class CommitPayload:
    key: str
    owner_token_hash: str
    cid: str
    stored_digest: str
    stored_len: int
    stored_asst: int
    epoch: int
    now_s: float
    lease_token: str = ""
    supersede: bool = False
    expected_gen: int = 0
    expected_stored_digest: str = ""
@dataclass(frozen=True, slots=True)
class StoreStats:
    total_slots: int
    ready_slots: int
    in_flight_slots: int
    persist_failures: int
    post_spawn_aborts: int
    corrupt_quarantines: int
    owner_counts: tuple[tuple[str, int], ...]
@dataclass(slots=True)
class _SlotRecord:
    key: str
    owner_token_hash: str
    cid: str
    state: SlotState
    stored_digest: str
    stored_len: int
    stored_asst: int
    gen: int
    epoch: int
    created_s: float
    last_used_s: float
    turns: int
    lease_token: str = ""
    in_flight_since_s: float = 0.0
    unconfirmed_since_s: float = 0.0
    supersede_ts: list[float] = field(default_factory=list)
    def snap(self) -> SlotSnapshot:
        return SlotSnapshot(self.state, self.cid, self.stored_digest, self.stored_len, self.stored_asst, self.gen, self.epoch, self.created_s, self.last_used_s, self.turns, self.in_flight_since_s, self.unconfirmed_since_s)

def _fsync_dir(dir_path: Path) -> None:
    fd = os.open(dir_path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
def _write_0600(path: Path, data: bytes) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _MODE_0600), "wb") as f:
        _, _, _ = f.write(data), f.flush(), os.fsync(f.fileno())
def load_or_create_hmac_key(key_path: Path) -> bytes:
    _, raw, tmp = key_path.parent.mkdir(parents=True, exist_ok=True), secrets.token_bytes(_HMAC_LEN), key_path.parent / f"{key_path.name}.tmp.{os.getpid()}.{secrets.token_hex(6)}"
    if key_path.exists() and len(data := key_path.read_bytes()) == _HMAC_LEN:
        return data
    try:
        _write_0600(tmp, raw)
        try:
            os.link(tmp, key_path)
        except FileExistsError:
            if key_path.exists() and len(ex := key_path.read_bytes()) == _HMAC_LEN:
                return ex
            with suppress(FileNotFoundError):
                os.replace(key_path, key_path.with_name(f"{key_path.name}.corrupt"))
            os.replace(tmp, key_path)
        return raw if _fsync_dir(key_path.parent) is None else raw
    finally:
        with suppress(OSError):
            os.unlink(tmp)
def _parse_entry(key: str, raw: object) -> _SlotRecord | None:
    if not key or not isinstance(raw, dict):
        return None
    v = [cast(dict[object, object], raw).get(k) for k in _DISK_KEYS]
    if not all((all(type(x) is str for x in v[:3]), all(type(x) is int for x in v[3:8]), all(type(x) in (int, float) for x in v[8:]), bool(v[0]), bool(v[1]))):
        return None
    return _SlotRecord(key, cast(str, v[0]), cast(str, v[1]), _S.READY, cast(str, v[2]), cast(int, v[3]), cast(int, v[4]), cast(int, v[5]), cast(int, v[6]), float(cast(float, v[8])), float(cast(float, v[9])), cast(int, v[7]))

@final
class ExplicitSessionStore:
    def __init__(self, state_dir: Path, policy: PolicyConfig | None = None, config: StoreConfig | None = None, epoch: int = 0) -> None:
        _, self._policy, self._cfg, self._store_path = state_dir.mkdir(parents=True, exist_ok=True), policy or PolicyConfig(enabled=True), config or StoreConfig(), state_dir / _STORE_FILE
        self._slots, self._owner_keys, self._lock = OrderedDict[str, _SlotRecord](), dict[str, OrderedDict[str, None]](), threading.Lock()
        self._cond, self._dirty, self._current_epoch, self._seq, self._flushed_seq, self._closed = threading.Condition(self._lock), threading.Event(), epoch, 0, 0, False
        self._persist_failures = self._post_spawn_aborts = self._corrupt_quarantines = 0
        _, self._worker = self._load_initial(), threading.Thread(target=self._persist_loop, name="explicit-store", daemon=True)
        self._worker.start()
    def peek(self, key: str, now_s: float) -> tuple[SlotSnapshot, int]:
        with self._lock:
            return (_EMPTY_SNAP, 0) if (rec := self._slots.get(key)) is None else (rec.snap(), sum(1 for t in rec.supersede_ts if now_s - t < self._cfg.supersede_window_s))
    def stats(self) -> StoreStats:
        with self._lock:
            return StoreStats(len(self._slots), sum(x.state == _S.READY for x in self._slots.values()), sum(x.state == _S.IN_FLIGHT for x in self._slots.values()), self._persist_failures, self._post_spawn_aborts, self._corrupt_quarantines, tuple((k, len(v)) for k, v in self._owner_keys.items()))
    def evict_if_expired(self, key: str, now_s: float) -> bool:
        with self._lock:
            if (rec := self._slots.get(key)) is None or (rec.state not in (_S.CORRUPT, _S.EXPIRED) and not is_slot_expired(rec.snap(), now_s, self._policy)):
                return False
            ev = _E.CORRUPT_DETECTED if rec.state == _S.CORRUPT else (_E.EVICT if rec.state == _S.EXPIRED else _E.TTL_EXCEEDED)
            _ = transition(_S.EXPIRED, _E.EVICT) if transition(rec.state, ev).next_state == _S.EXPIRED else None
            return self._rm(key, dirty=True)
    def claim_resume(self, key: str, expected_cid: str, now_s: float, epoch: int) -> str:
        with self._lock:
            if (rec := self._slots.get(key)) is None or (rec.state, rec.cid, rec.epoch, epoch) != (_S.READY, expected_cid, epoch, self._current_epoch) or is_slot_expired(rec.snap(), now_s, self._policy):
                return ""
            rec.state, rec.lease_token, rec.in_flight_since_s = transition(rec.state, _E.CLAIM_RESUME).next_state, secrets.token_hex(12), now_s
            return self._put(rec).lease_token
    def commit_pending(self, payload: CommitPayload) -> bool:
        with self._lock:
            if not all((payload.key, payload.owner_token_hash, payload.cid, payload.epoch == self._current_epoch)):
                return False
            rec = self._slots.get(payload.key)
            if payload.lease_token:
                ok = rec is not None and rec.state == _S.IN_FLIGHT and hmac.compare_digest(rec.lease_token, payload.lease_token)
                return self._apply(cast(_SlotRecord, rec), payload, cast(_SlotRecord, rec).turns + 1, cast(_SlotRecord, rec).created_s) if ok else False
            return self._commit_seed(rec, payload)
    def abort_turn(self, key: str, lease_token: str, post_spawn: bool) -> bool:
        with self._lock:
            if not (lease_token and (rec := self._slots.get(key)) is not None and rec.state == _S.IN_FLIGHT and hmac.compare_digest(rec.lease_token, lease_token)):
                return False
            if post_spawn:
                _, self._post_spawn_aborts = transition(rec.state, _E.TURN_ABORT_POST_SPAWN), self._post_spawn_aborts + 1
                return self._rm(key, dirty=True)
            rec.state, rec.lease_token, rec.in_flight_since_s, self._seq, _ = transition(rec.state, _E.TURN_ABORT_PRE_SPAWN).next_state, "", 0.0, self._seq + 1, self._dirty.set()
            return True
    def on_epoch_change(self, new_epoch: int) -> int:
        with self._lock:
            self._current_epoch, stale = new_epoch, [k for k, r in self._slots.items() if r.epoch != new_epoch]
            for k in stale:
                _, _ = transition(self._slots[k].state, _E.EPOCH_CHANGED), self._rm(k, dirty=True)
            return len(stale)
    def flush_now(self, timeout_s: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout_s
        with self._lock:
            want, _ = self._seq, self._dirty.set() if self._flushed_seq < self._seq else None
            while self._flushed_seq < want and not self._closed and (rem := deadline - time.monotonic()) > 0:
                _ = self._cond.wait(timeout=rem)
            return self._flushed_seq >= want
    def close(self) -> None:
        _ = self.flush_now()
        with self._lock:
            self._closed, _, _ = True, self._dirty.set(), self._cond.notify_all()
        _ = self._worker.join(timeout=2.0) if threading.current_thread() is not self._worker else None
    def _apply(self, rec: _SlotRecord, p: CommitPayload, turns: int, created_s: float) -> bool:
        rec.state, rec.cid, rec.stored_digest, rec.stored_len, rec.stored_asst = transition(rec.state, _E.TURN_COMMIT_PENDING).next_state, p.cid, p.stored_digest, p.stored_len, p.stored_asst
        rec.gen, rec.epoch, rec.created_s, rec.last_used_s, rec.turns, rec.lease_token, rec.in_flight_since_s, rec.unconfirmed_since_s = rec.gen + 1, p.epoch, created_s, p.now_s, turns, "", 0.0, p.now_s
        _, self._seq, _ = self._put(rec), self._seq + 1, self._dirty.set()
        return True
    def _commit_seed(self, rec: _SlotRecord | None, p: CommitPayload) -> bool:
        if rec is None or rec.state in (_S.EXPIRED, _S.CORRUPT):
            return self._insert_new(rec, p)
        if rec.state == _S.READY and p.supersede:
            recent = [t for t in rec.supersede_ts if p.now_s - t < self._cfg.supersede_window_s]
            if not all((rec.gen == p.expected_gen, hmac.compare_digest(rec.stored_digest, p.expected_stored_digest), len(recent) < self._policy.supersede_max_per_min)):
                return False
            rec.supersede_ts = [*recent, p.now_s]
            return self._apply(rec, p, 1, p.now_s)
        if rec.state == _S.IN_FLIGHT or p.stored_len <= rec.stored_len:
            return False
        turns, created = (rec.turns + 1, rec.created_s) if rec.cid == p.cid else (1, p.now_s)
        return self._apply(rec, p, turns, created)
    def _insert_new(self, old: _SlotRecord | None, p: CommitPayload) -> bool:
        prev_gen, _ = (old.gen, (transition(old.state, _E.EVICT if old.state == _S.EXPIRED else _E.CORRUPT_DETECTED), self._rm(old.key))) if old is not None else (0, None)
        b = self._owner_keys.get(p.owner_token_hash)
        if (b is not None and len(b) >= self._cfg.max_per_owner and not self._evict_one(b, p.now_s)) or (len(self._slots) >= self._cfg.max_sessions and not self._evict_one(self._slots, p.now_s)):
            return False
        return self._apply(_SlotRecord(p.key, p.owner_token_hash, p.cid, _S.EMPTY, "", 0, 0, prev_gen, p.epoch, p.now_s, p.now_s, 0), p, 1, p.now_s)
    def _evict_one(self, keys: Iterable[str], now_s: float) -> bool:
        cands = [k for k in list(keys) if self._slots[k].state != _S.IN_FLIGHT]
        exp = [k for k in cands if self._slots[k].state == _S.EXPIRED or is_slot_expired(self._slots[k].snap(), now_s, self._policy)]
        if (victim := exp[0] if exp else next((k for k in cands if self._slots[k].state in (_S.READY, _S.UNCONFIRMED)), None)) is None:
            return False
        return self._rm(victim) if transition(self._slots[victim].state, _E.EVICT).next_state == _S.EMPTY else False
    def _put(self, rec: _SlotRecord) -> _SlotRecord:
        self._slots[rec.key], _ = rec, self._slots.move_to_end(rec.key) if rec.key in self._slots else None
        b = self._owner_keys.setdefault(rec.owner_token_hash, OrderedDict())
        b[rec.key], _ = None, b.move_to_end(rec.key) if rec.key in b else None
        return rec
    def _rm(self, key: str, dirty: bool = False) -> bool:
        if (rec := self._slots.pop(key, None)) is not None and (b := self._owner_keys.get(rec.owner_token_hash)) is not None:
            _, _ = b.pop(key, None), self._owner_keys.pop(rec.owner_token_hash, None) if not b else None
        self._seq, _ = (self._seq + 1, self._dirty.set()) if dirty else (self._seq, None)
        return True
    def _persist_loop(self) -> None:
        while self._dirty.wait():
            with self._lock:
                if self._closed and self._flushed_seq >= self._seq:
                    return
            _, _ = self._dirty.clear(), self._persist_once()
    def _persist_once(self) -> None:
        with self._lock:
            if self._flushed_seq >= self._seq:
                return
            seq, ep, gens = self._seq, self._current_epoch, {k: r.gen for k, r in self._slots.items() if r.state == _S.UNCONFIRMED}
            entries = {k: {f: cast(str | int | float, getattr(r, f)) for f in _DISK_KEYS} for k, r in self._slots.items() if r.state in (_S.READY, _S.UNCONFIRMED)}
        raw = json.dumps({"schema_version": _SCHEMA_VER, "epoch": ep, "entries": entries}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        tmp, ok = self._store_path.parent / f"{self._store_path.name}.tmp.{os.getpid()}.{secrets.token_hex(6)}", False
        try:
            _, _, _, ok = _write_0600(tmp, raw), os.replace(tmp, self._store_path), _fsync_dir(self._store_path.parent), True
        except OSError:
            with suppress(OSError):
                os.unlink(tmp)
        self._finish(seq, ep, gens, ok)
    def _finish(self, seq: int, ep: int, gens: dict[str, int], ok: bool) -> None:
        with self._lock:
            self._persist_failures += int(not ok)
            for k, g in gens.items():
                if (rec := self._slots.get(k)) is not None and (rec.gen, rec.epoch, rec.state) == (g, ep, _S.UNCONFIRMED):
                    if ok:
                        rec.state, rec.unconfirmed_since_s = transition(rec.state, _E.PERSIST_OK).next_state, 0.0
                    else:
                        _, _ = transition(rec.state, _E.PERSIST_FAIL), self._rm(k)
            self._flushed_seq, _ = max(self._flushed_seq, seq), self._cond.notify_all()
    def _load_initial(self) -> None:
        if not self._store_path.exists():
            return
        try:
            obj = cast(object, json.loads(self._store_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return self._quarantine()
        doc = cast(dict[object, object], obj) if isinstance(obj, dict) else {}
        if not all((type(doc.get("schema_version")) is int, doc.get("schema_version") == _SCHEMA_VER, isinstance(doc.get("entries"), dict))):
            return self._quarantine()
        now_s = time.time()
        for k, v in cast(dict[object, object], doc["entries"]).items():
            if (rec := _parse_entry(k, v) if isinstance(k, str) else None) is not None and all((rec.epoch == self._current_epoch, not is_slot_expired(rec.snap(), now_s, self._policy), len(self._owner_keys.get(rec.owner_token_hash, ())) < self._cfg.max_per_owner, len(self._slots) < self._cfg.max_sessions)):
                _ = self._put(rec)
    def _quarantine(self) -> None:
        self._corrupt_quarantines, prefix = self._corrupt_quarantines + 1, f"{self._store_path.name}.corrupt-"
        with suppress(OSError):
            _, _ = os.replace(self._store_path, self._store_path.with_name(f"{prefix}{time.time_ns()}")), _fsync_dir(self._store_path.parent)
            for old in (files := sorted(self._store_path.parent.glob(f"{prefix}*"), key=lambda p: p.name))[: max(0, len(files) - self._cfg.corrupt_keep)]:
                os.unlink(old)
