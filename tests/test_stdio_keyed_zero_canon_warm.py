"""W2: keyed Zero-Canon warm reuse (`stdio_resident`), logical context reset, bounded wait queue."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from core.backend_routing_models import Transcript, TranscriptItem
from core.resident_history import CommittedSessionState, build_assistant_transcript_item, plan_history_transition
from core.resident_identity import IdentityInputs, ResidentIdentity, resolve_resident_identity
from core.resident_turn_envelope import ResidentTurnEnvelope
from core.session_plane import zc_env_guard
from core.stdio_resident.codex_driver import CodexAppServerV2Driver
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_pool import ResidentProcessPool, SlotLeaseTimeoutError
from core.stdio_resident.resident_runtime import PreDispatchResidentError, ResidentBridgeRuntime, ResidentTurnOptions
from core.stdio_resident.types import SlotBinding
from core.stdio_resident.zero_canon_router import KIND_EPHEMERAL, KIND_RESIDENT, decide_zero_canon_route, zero_canon_isolation

FLAG = "BRIDGE_ZERO_CANON_KEYED_RESIDENT_ENABLED"
_SECRET = b"0123456789abcdef0123456789abcdef"
_FAKE = """
import json, os, sys
LOG, PID, n = os.environ["FAKE_LOG"], os.getpid(), 0
def log(ev, **kw):
    with open(LOG, "a") as fh:
        fh.write(json.dumps({"ev": ev, "pid": PID, "home": os.environ.get("HOME", ""), **kw}) + "\\n")
def send(obj):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", **obj}) + "\\n"); sys.stdout.flush()
log("spawn")
for line in sys.stdin:
    m = json.loads(line); meth, rid, p = m.get("method"), m.get("id"), m.get("params") or {}
    if meth == "initialize":
        log("initialize"); send({"id": rid, "result": {"userAgent": "fake"}})
    elif meth == "thread/start":
        n += 1; tid = "th-%d-%d" % (PID, n); log("thread/start", thread=tid); send({"id": rid, "result": {"thread": {"id": tid}}})
    elif meth == "turn/start":
        tid, tu = p["threadId"], "tu-%d" % n
        text = p["input"][0]["text"] if p.get("input") else p.get("prompt", "")
        send({"id": rid, "result": {"turn": {"id": tu}}})
        send({"method": "item/agentMessage/delta", "params": {"threadId": tid, "turnId": tu, "itemId": "i", "delta": json.dumps({"pid": PID, "thread": tid, "prompt": text})}})
        send({"method": "turn/completed", "params": {"threadId": tid, "turn": {"id": tu, "status": "completed"}}})
"""


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "home").mkdir()
    for key, val in {"HOME": str(tmp_path / "home"), "BRIDGE_DYNAMIC_CONFIG_PATH": str(tmp_path / "none.json"),
                     "BRIDGE_ZC_STATIC_CWD_ENABLED": "0", "FAKE_LOG": str(tmp_path / "log.jsonl"), FLAG: "1"}.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setattr(zc_env_guard, "DEFAULT_ZC_SLOTS_ROOT", tmp_path / "zc-slots")
    (tmp_path / "fake.py").write_text(_FAKE)
    return tmp_path


class _Rig:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.driver = CodexAppServerV2Driver()
        self.released = 0
        orig = self.driver._release_handle_state

        def spy(handle: Any) -> None:
            self.released += 1
            orig(handle)

        self.driver._release_handle_state = spy  # type: ignore[method-assign]
        self.pool = ResidentProcessPool(StdioPoolConfig(max_slots=4, lease_wait_s=2.0, cancel_grace_s=1.0, enabled=False))
        self.rt = ResidentBridgeRuntime(self.pool, self.driver)

    @property
    def spawns(self) -> int:
        return len(self.events("spawn"))

    def argv(self) -> list[str]:
        return [sys.executable, str(self.root / "fake.py")]

    def events(self, ev: str | None = None) -> list[dict[str, Any]]:
        path = self.root / "log.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
        return [r for r in rows if ev in (None, r["ev"])]

    def turn(self, chat: str, items: tuple[TranscriptItem, ...], profile: str = "zero-canon") -> dict[str, Any]:
        headers = {"X-DSH-Chat-Id": chat} if chat else {}
        ident = resolve_resident_identity(IdentityInputs(request={}, headers=headers, extra={}, secret=_SECRET, trusted_principal_hash="own", review_profile=profile, protocol="codex-app-server-v2"))
        env = ResidentTurnEnvelope(identity=ident, backend_id="codex", model="m", effort="low", cwd_norm=str(self.root), secret=_SECRET, review_profile=profile, rpc=Transcript(items=items, runnable=True), full_prompt="P:" + items[-1].text)
        chunks = list(self.rt.execute_turn(env, ResidentTurnOptions(argv_builder=self.argv)))
        return json.loads("".join(c.text or "" for c in chunks))


def _u(text: str) -> TranscriptItem:
    return TranscriptItem("user", text, "d-" + text)


@pytest.fixture
def rig(env: Path):
    r = _Rig(env)
    yield r
    r.pool.shutdown()


def test_kill_switch_off_is_legacy(env: Path, monkeypatch: pytest.MonkeyPatch, rig: _Rig) -> None:
    monkeypatch.delenv(FLAG)
    monkeypatch.setenv(FLAG, "0")
    ident = resolve_resident_identity(IdentityInputs(request={}, headers={"X-DSH-Chat-Id": "A"}, extra={}, secret=_SECRET, trusted_principal_hash="o", review_profile="zero-canon"))
    assert ident.ephemeral and ident.degradation_reason == "zero_canon_ephemeral"
    assert decide_zero_canon_route("zero-canon", "codex-app-server-v2", ephemeral_identity=False).kind == KIND_EPHEMERAL
    rig.turn("A", (_u("a"),))
    rig.turn("A", (_u("b"),))
    assert len(rig.events("spawn")) == 2 and rig.released >= 2
    assert not (env / "zc-slots").exists() or not list((env / "zc-slots").iterdir())
    ident2 = ResidentIdentity("o", "A", False, "", "t", "", "", "sid")
    cs = CommittedSessionState("s", 1, "o", "codex", "", "x", "", "m", "low", "/w", "zero-canon", ("d1",))
    e2 = ResidentTurnEnvelope(identity=ident2, backend_id="codex", model="m", effort="low", cwd_norm="/w", secret=_SECRET, review_profile="zero-canon", rpc=Transcript(items=(_u("z"),)), full_prompt="z")
    plan = plan_history_transition(cs, e2, SlotBinding("s", 1))
    assert plan.requires_slot_reset and not plan.logical_context_reset


def test_keyed_five_turns_one_pid_and_five_threads(rig: _Rig) -> None:
    replies = []
    history: tuple[TranscriptItem, ...] = (_u("r1"),)
    replies.append(rig.turn("A", history))
    assistant = build_assistant_transcript_item(json.dumps(replies[0]))
    assert assistant is not None
    replies.append(rig.turn("A", (*history, assistant, _u("r2"))))  # append-only
    for name in ("d1", "d2", "d3"):  # history_diverged
        replies.append(rig.turn("A", (_u(name),)))
    assert rig.spawns == 1 and len(rig.events("spawn")) == 1
    assert len({r["pid"] for r in replies}) == 1
    assert len({r["thread"] for r in replies}) == 5
    assert len(rig.events("initialize")) == 1 and len(rig.events("thread/start")) == 5
    assert [r["prompt"] for r in replies][2:] == ["P:d1", "P:d2", "P:d3"] and replies[1]["prompt"] == "P:r2"


def test_chat_isolation_and_private_homes(rig: _Rig) -> None:
    a1, b1, a2 = rig.turn("A", (_u("a1"),)), rig.turn("B", (_u("b1"),)), rig.turn("A", (_u("a2"),))
    assert a1["pid"] == a2["pid"] != b1["pid"]
    homes = {r["pid"]: r["home"] for r in rig.events("spawn")}
    assert len(set(homes.values())) == 2
    for home in homes.values():
        assert os.path.basename(home).startswith("zc-") and stat.S_IMODE(os.stat(home).st_mode) == 0o700
    std = rig.turn("A", (_u("s1"),), profile="standard")
    assert std["pid"] not in homes and rig.spawns == 3
    ids = {resolve_resident_identity(IdentityInputs(request={}, headers={"X-DSH-Chat-Id": c}, extra={}, secret=_SECRET, trusted_principal_hash="o", review_profile=p)).scoped_session_id for c, p in (("A", "zero-canon"), ("B", "zero-canon"), ("A", "standard"))}
    assert len(ids) == 3


def test_empty_chat_id_stays_ephemeral(rig: _Rig) -> None:
    rig.turn("", (_u("e1"),))
    rig.turn("", (_u("e2"),))
    assert rig.spawns == 2 and len(rig.events("spawn")) == 2


def test_teardown_and_eviction_remove_home(env: Path, rig: _Rig) -> None:
    rig.turn("A", (_u("a"),))
    rig.turn("B", (_u("b"),))
    homes = [Path(r["home"]) for r in rig.events("spawn")]
    assert all(h.is_dir() for h in homes)
    victim = next(e for e in rig.pool._slots.values() if e.zc_home_root == str(homes[0]))
    assert rig.pool.close_if_idle(victim.slot_id, victim.handle.generation)
    assert not homes[0].exists() and not homes[0].parent.exists() and homes[1].is_dir()
    rig.pool.shutdown()
    assert not homes[1].exists() and not list((env / "zc-slots").iterdir())


def test_unsupported_protocol_and_process_level_change_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FLAG, "1")
    ident = ResidentIdentity("o", "A", False, "", "t", "", "", "sid")

    def env_of(backend: str, model: str = "m", sys_text: str = "s") -> ResidentTurnEnvelope:
        rpc = Transcript(items=(TranscriptItem("system", sys_text, "ds"), _u("n")))
        return ResidentTurnEnvelope(identity=ident, backend_id=backend, model=model, effort="low", cwd_norm="/w", secret=_SECRET, review_profile="zero-canon", rpc=rpc, full_prompt="n")

    def committed(backend: str, model: str = "m", sys_text: str = "s") -> CommittedSessionState:
        e = env_of(backend, model, sys_text)
        return CommittedSessionState("s", 1, "o", backend, e.env_digest, e.system_digest, e.tool_contract_fingerprint, model, "low", "/w", "zero-canon", ("old",))

    warm = SlotBinding("s", 1)
    claude = plan_history_transition(committed("claude"), env_of("claude"), warm)
    assert claude.requires_slot_reset and not claude.logical_context_reset and claude.reason == "history_diverged"
    codex = plan_history_transition(committed("codex"), env_of("codex"), warm)
    assert codex.logical_context_reset and not codex.requires_slot_reset and codex.reason == "history_diverged_logical_reset"
    thread_level = plan_history_transition(committed("codex", sys_text="other"), env_of("codex"), warm)
    assert thread_level.logical_context_reset and not thread_level.requires_slot_reset
    process_level = plan_history_transition(committed("codex", model="other"), env_of("codex"), warm)
    assert process_level.requires_slot_reset and not process_level.logical_context_reset and process_level.reason == "header_changed"
    monkeypatch.setenv(FLAG, "0")
    assert plan_history_transition(committed("codex"), env_of("codex"), warm).requires_slot_reset


def test_router_persisted_home_is_stable_and_fail_closed(env: Path) -> None:
    driver = CodexAppServerV2Driver()
    assert decide_zero_canon_route("zero-canon", "codex-app-server-v2", ephemeral_identity=False).kind == KIND_RESIDENT
    assert decide_zero_canon_route("zero-canon", "codex-app-server-v2").kind == KIND_EPHEMERAL
    with zero_canon_isolation(driver, "zero-canon", keyed_slot_id="sid", persist=True) as iso1:
        first = iso1.env(dict(os.environ))
        assert iso1.route_kind == KIND_RESIDENT and not iso1.is_ephemeral and iso1.active
    root = Path(str(iso1.root))
    assert root.is_dir() and root.name.startswith("zc-") and stat.S_IMODE(root.stat().st_mode) == 0o700
    with zero_canon_isolation(driver, "zero-canon", keyed_slot_id="sid", persist=True) as iso2:
        second = iso2.env(dict(os.environ))  # no FileExistsError on turn 2
    assert iso2.root == iso1.root and second is not None and first is not None
    assert second["HOME"] == str(root) and second["CODEX_HOME"] == str(root / ".codex") and second["BRIDGE_ZERO_CANON"] == "1"
    (root / ".codex" / "history.jsonl").write_text("leak")
    with zero_canon_isolation(driver, "zero-canon", keyed_slot_id="sid", persist=True) as iso3, pytest.raises(RuntimeError, match="zero_canon_dirty_home"):
        iso3.env(dict(os.environ))


def test_bounded_wait_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = ResidentProcessPool(StdioPoolConfig(max_slots=2, lease_wait_s=0.1, enabled=False))
    monkeypatch.setenv(FLAG, "1")
    pool._waiters = 4
    with pool._cv, pytest.raises(SlotLeaseTimeoutError, match="slot_wait_queue_full"):
        pool._wait_for_slot(0.01, False)
    monkeypatch.setenv(FLAG, "0")
    with pool._cv, pytest.raises(SlotLeaseTimeoutError, match="timed out"):
        pool._wait_for_slot(0.01, False)

    class _Full:
        _config = StdioPoolConfig(max_slots=1, enabled=False)

        def acquire(self, *_a: Any, **_k: Any) -> Any:
            raise SlotLeaseTimeoutError("slot_wait_queue_full")

    with pytest.raises(PreDispatchResidentError) as err:
        ResidentBridgeRuntime(_Full(), object())._acquire_slot(None, False, ([], "", None))  # type: ignore[arg-type]
    assert err.value.code == "slot_wait_queue_full" and err.value.http_status == 503
