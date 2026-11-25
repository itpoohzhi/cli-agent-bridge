from __future__ import annotations

import ast
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time
from typing import Protocol, cast

import pytest

_REPO = Path(__file__).resolve().parents[1]
_MOD_PATH = _REPO / "bridges" / "agy-bridge" / "agy_runtime" / "session_store.py"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.hot_session_policy import PolicyConfig, SlotSnapshot, SlotState  # noqa: E402


class _StoreConfigCtor(Protocol):
    def __call__(self, max_sessions: int = ..., max_per_owner: int = ..., corrupt_keep: int = ..., supersede_window_s: float = ...) -> object: ...


class _CommitPayloadCtor(Protocol):
    def __call__(self, key: str, owner_token_hash: str, cid: str, stored_digest: str, stored_len: int, stored_asst: int, epoch: int, now_s: float, lease_token: str = ..., supersede: bool = ..., expected_gen: int = ..., expected_stored_digest: str = ...) -> object: ...


class _StoreStats(Protocol):
    total_slots: int
    ready_slots: int
    in_flight_slots: int
    persist_failures: int
    post_spawn_aborts: int
    corrupt_quarantines: int
    owner_counts: tuple[tuple[str, int], ...]


class _StoreProto(Protocol):
    def peek(self, key: str, now_s: float) -> tuple[SlotSnapshot, int]: ...
    def stats(self) -> _StoreStats: ...
    def evict_if_expired(self, key: str, now_s: float) -> bool: ...
    def claim_resume(self, key: str, expected_cid: str, now_s: float, epoch: int) -> str: ...
    def commit_pending(self, payload: object) -> bool: ...
    def abort_turn(self, key: str, lease_token: str, post_spawn: bool) -> bool: ...
    def on_epoch_change(self, new_epoch: int) -> int: ...
    def flush_now(self, timeout_s: float = ...) -> bool: ...
    def close(self) -> None: ...


class _StoreCtor(Protocol):
    def __call__(self, state_dir: Path, policy: PolicyConfig | None = ..., config: object | None = ..., epoch: int = ...) -> _StoreProto: ...


class _LoadKeyFn(Protocol):
    def __call__(self, key_path: Path) -> bytes: ...


def _load_mod() -> tuple[_StoreCtor, _StoreConfigCtor, _CommitPayloadCtor, _LoadKeyFn]:
    spec = importlib.util.spec_from_file_location("agy_runtime_session_store_ut", _MOD_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return (
        cast(_StoreCtor, getattr(mod, "ExplicitSessionStore")),
        cast(_StoreConfigCtor, getattr(mod, "StoreConfig")),
        cast(_CommitPayloadCtor, getattr(mod, "CommitPayload")),
        cast(_LoadKeyFn, getattr(mod, "load_or_create_hmac_key")),
    )


ExplicitSessionStore, StoreConfig, CommitPayload, load_or_create_hmac_key = _load_mod()


def _pl(
    key: str = "k1",
    owner: str = "own1",
    cid: str = "cid-1",
    digest: str = "d1",
    slen: int = 2,
    *,
    epoch: int = 1,
    now_s: float | None = None,
    lease: str = "",
    supersede: bool = False,
    exp_gen: int = 0,
    exp_dig: str = "",
) -> object:
    return CommitPayload(key, owner, cid, digest, slen, 1, epoch, time.time() if now_s is None else now_s, lease, supersede, exp_gen, exp_dig)


def test_hmac_key_atomic_creation_and_corrupt_recovery(tmp_path: Path) -> None:
    kp = tmp_path / "state" / ".owner_hmac_key"
    k1 = load_or_create_hmac_key(kp)
    assert len(k1) == 32 and stat.S_IMODE(kp.stat().st_mode) == 0o600
    assert load_or_create_hmac_key(kp) == k1
    _ = kp.write_bytes(b"")
    k2 = load_or_create_hmac_key(kp)
    assert len(k2) == 32 and k2 != k1 and stat.S_IMODE(kp.stat().st_mode) == 0o600
    assert kp.with_name(".owner_hmac_key.corrupt").exists()


def test_full_lifecycle_posix_order_and_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    real_fsync, real_replace, store_file = os.fsync, os.replace, tmp_path / "sessions_explicit.json"

    def spy_fsync(fd: int) -> None:
        events.append("fsync_dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "fsync_tmp")
        real_fsync(fd)

    def spy_replace(src: object, dst: object) -> None:
        if Path(str(dst)) == store_file:
            events.append("replace")
        real_replace(cast(str, src), cast(str, dst))

    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(os, "replace", spy_replace)
    st = ExplicitSessionStore(tmp_path, epoch=1)
    try:
        now = time.time()
        assert st.peek("k1", now)[0].state == SlotState.EMPTY
        assert st.commit_pending(_pl(now_s=now)) is True and st.flush_now() is True
        assert events[:3] == ["fsync_tmp", "replace", "fsync_dir"]
        assert stat.S_IMODE(store_file.stat().st_mode) == 0o600
        raw = cast(dict[str, object], json.loads(store_file.read_text(encoding="utf-8")))
        assert raw["schema_version"] == 2 and "lease_token" not in json.dumps(raw)
        lease = st.claim_resume("k1", "cid-1", now, 1)
        assert lease and st.peek("k1", now)[0].state == SlotState.IN_FLIGHT
        assert st.commit_pending(_pl(slen=4, digest="d2", now_s=now + 1.0, lease=lease)) and st.flush_now()
        snap2, _ = st.peek("k1", now + 1.0)
        assert snap2.state == SlotState.READY and snap2.gen == 2 and snap2.turns == 2
    finally:
        st.close()
    st2 = ExplicitSessionStore(tmp_path, epoch=1)
    try:
        reloaded, _ = st2.peek("k1", time.time())
        assert reloaded.state == SlotState.READY and reloaded.stored_digest == "d2" and reloaded.gen == 2
    finally:
        st2.close()


def test_gen_bump_during_flush_never_promotes_stale_unconfirmed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_fsync = os.fsync
    e1, r1, e2, r2, calls = threading.Event(), threading.Event(), threading.Event(), threading.Event(), 0

    def gated_fsync(fd: int) -> None:
        nonlocal calls
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            calls += 1
            if calls == 1:
                e1.set()
                assert r1.wait(timeout=3.0)
            elif calls == 2:
                e2.set()
                assert r2.wait(timeout=3.0)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", gated_fsync)
    st = ExplicitSessionStore(tmp_path, epoch=1)
    try:
        now = time.time()
        assert st.commit_pending(_pl(slen=2, digest="d1", now_s=now)) and e1.wait(timeout=3.0)
        assert st.commit_pending(_pl(slen=4, digest="d2", now_s=now + 1.0))
        r1.set()
        assert e2.wait(timeout=3.0)
        snap, _ = st.peek("k1", now + 1.0)
        assert snap.state == SlotState.UNCONFIRMED and snap.gen == 2 and st.claim_resume("k1", "cid-1", now + 1.0, 1) == ""
        r2.set()
        assert st.flush_now() and st.peek("k1", now + 1.0)[0].state == SlotState.READY
    finally:
        r1.set()
        r2.set()
        st.close()


def test_supersede_cas_and_rate_limit(tmp_path: Path) -> None:
    st = ExplicitSessionStore(tmp_path, epoch=1)
    try:
        t0 = time.time()
        assert st.commit_pending(_pl(digest="d0", slen=2, now_s=t0)) and st.flush_now()
        assert not st.commit_pending(_pl(digest="bad", now_s=t0 + 1, supersede=True, exp_gen=99, exp_dig="d0"))
        assert not st.commit_pending(_pl(digest="bad", now_s=t0 + 1, supersede=True, exp_gen=1, exp_dig="wrong"))
        for i in range(3):
            snap, _ = st.peek("k1", t0 + 2 + i)
            assert st.commit_pending(_pl(cid=f"c{i+1}", digest=f"d{i+1}", now_s=t0 + 2 + i, supersede=True, exp_gen=snap.gen, exp_dig=snap.stored_digest)) and st.flush_now()
        snap3, recent = st.peek("k1", t0 + 10)
        assert recent == 3
        assert not st.commit_pending(_pl(cid="c4", digest="d4", now_s=t0 + 10, supersede=True, exp_gen=snap3.gen, exp_dig=snap3.stored_digest))
        assert st.commit_pending(_pl(cid="c4", digest="d4", now_s=t0 + 65, supersede=True, exp_gen=snap3.gen, exp_dig=snap3.stored_digest))
    finally:
        st.close()


def test_abort_turn_and_stale_lease_noop(tmp_path: Path) -> None:
    st = ExplicitSessionStore(tmp_path, epoch=1)
    try:
        now = time.time()
        assert st.commit_pending(_pl(now_s=now)) and st.flush_now()
        lease1 = st.claim_resume("k1", "cid-1", now, 1)
        assert not st.commit_pending(_pl(slen=5, now_s=now + 1))
        assert st.abort_turn("k1", lease1, post_spawn=False) and st.peek("k1", now + 1)[0].state == SlotState.READY
        assert not st.commit_pending(_pl(slen=5, now_s=now + 1, lease=lease1))
        lease2 = st.claim_resume("k1", "cid-1", now + 2, 1)
        assert lease2 and st.abort_turn("k1", lease2, post_spawn=True)
        assert st.peek("k1", now + 2)[0].state == SlotState.EMPTY and st.stats().post_spawn_aborts == 1
        assert not st.commit_pending(_pl(slen=6, now_s=now + 3, lease=lease2)) and st.peek("k1", now + 3)[0].state == SlotState.EMPTY
    finally:
        st.close()


def test_fault_injection_readonly_dir_and_corrupt_rotation(tmp_path: Path) -> None:
    ro = tmp_path / "ro"
    ro.mkdir()
    st = ExplicitSessionStore(ro, epoch=1)
    try:
        ro.chmod(0o500)
        assert st.commit_pending(_pl(now_s=time.time())) and st.flush_now()
        assert st.peek("k1", time.time())[0].state == SlotState.EMPTY and st.stats().persist_failures >= 1
    finally:
        ro.chmod(0o700)
        st.close()
    cor = tmp_path / "corrupt"
    cor.mkdir()
    sf = cor / "sessions_explicit.json"
    for payload in ("{bad", '{"schema_version":1,"entries":{}}', "{bad2", "[]", "{bad3"):
        _ = sf.write_text(payload, encoding="utf-8")
        s = ExplicitSessionStore(cor, epoch=1)
        assert s.stats().total_slots == 0 and s.stats().corrupt_quarantines == 1
        s.close()
    assert len(list(cor.glob("sessions_explicit.json.corrupt-*"))) <= 3


def test_lru_stress_isolation_and_inflight_protection(tmp_path: Path) -> None:
    st = ExplicitSessionStore(tmp_path, epoch=1)
    try:
        now = time.time()
        for i in range(5):
            assert st.commit_pending(_pl(key=f"b{i}", owner="ownB", cid=f"cb{i}", now_s=now))
        assert st.commit_pending(_pl(key="c0", owner="ownC", cid="cc0", now_s=now)) and st.flush_now()
        assert st.claim_resume("c0", "cc0", now, 1)
        for i in range(1000):
            assert st.commit_pending(_pl(key=f"a{i}", owner="ownA", cid=f"ca{i}", now_s=now + i * 0.001))
        counts = dict(st.stats().owner_counts)
        assert counts["ownA"] <= 256 and counts["ownB"] == 5 and st.peek("c0", now + 2)[0].state == SlotState.IN_FLIGHT
    finally:
        st.close()
    small = ExplicitSessionStore(tmp_path / "sm", config=StoreConfig(max_sessions=2, max_per_owner=2), epoch=1)
    try:
        now = time.time()
        assert small.commit_pending(_pl(key="x1", cid="cx1", now_s=now)) and small.commit_pending(_pl(key="x2", cid="cx2", now_s=now)) and small.flush_now()
        assert small.claim_resume("x1", "cx1", now, 1) and small.claim_resume("x2", "cx2", now, 1)
        assert not small.commit_pending(_pl(key="x3", cid="cx3", now_s=now)) and small.stats().in_flight_slots == 2
    finally:
        small.close()


def test_epoch_change_and_evict_if_expired(tmp_path: Path) -> None:
    st = ExplicitSessionStore(tmp_path, policy=PolicyConfig(enabled=True, idle_ttl_s=10.0), epoch=1)
    try:
        now = time.time()
        assert st.commit_pending(_pl(key="k1", now_s=now)) and st.flush_now()
        assert not st.evict_if_expired("k1", now + 5.0) and st.evict_if_expired("k1", now + 15.0)
        assert st.peek("k1", now + 15.0)[0].state == SlotState.EMPTY
        assert st.commit_pending(_pl(key="k2", now_s=now)) and st.flush_now()
        assert st.on_epoch_change(2) == 1
        assert not st.commit_pending(_pl(key="k3", epoch=1, now_s=now)) and st.commit_pending(_pl(key="k3", epoch=2, now_s=now))
    finally:
        st.close()


def _mccabe_cc(fn: ast.AST) -> int:
    br = (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.IfExp)
    return 1 + sum(1 if isinstance(n, br) else len(n.values) - 1 for n in ast.walk(fn) if isinstance(n, (*br, ast.BoolOp)))


def test_session_store_modularity_invariants() -> None:
    src = _MOD_PATH.read_text(encoding="utf-8")
    assert len(src.splitlines()) <= 260
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            assert not isinstance(node.value, (ast.Dict, ast.List, ast.Set))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.end_lineno is not None and (node.end_lineno - node.lineno + 1) <= 40, node.name
            argc = len(node.args.posonlyargs) + len(node.args.args) + len(node.args.kwonlyargs) + int(node.args.vararg is not None) + int(node.args.kwarg is not None)
            assert argc <= 5, node.name
            assert _mccabe_cc(node) <= 10, node.name
