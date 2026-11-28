"""Contract tests for standby adapters, Zero-Canon 1-turn isolation, session affinity, and redaction."""
from __future__ import annotations

import logging
import os
import stat
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.stdio_resident.claude_standby_adapter import (
    ClaudeRunRequest, ClaudeStandbyAdapter, ClaudeWarmHandle, acquire_claude_run_proc, encode_claude_stdin_prompt,
)
from core.stdio_resident.codex_standby_adapter import (
    CodexStandbyAdapter, CodexWarmHandle, maybe_run_codex_standby_hook,
)
from core.stdio_resident.demand_standby_pool import DemandStandbyPool
from core.stdio_resident.process_reaper import is_pgid_alive as _pgid_alive
from core.stdio_resident.standby_pool_fsm import ProfileKey

REPO_ROOT = Path(__file__).resolve().parents[3]
AGY_DIR = REPO_ROOT / "bridges" / "agy-bridge"
if str(AGY_DIR) not in sys.path:
    sys.path.insert(0, str(AGY_DIR))

from agy_runtime.persistent_standby_pool import AgyStandbyManager  # noqa: E402
from agy_runtime.persistent_worker_adapter import AgyPersistentWorkerPool  # noqa: E402
from agy_runtime.persistent_worker_config import (  # noqa: E402
    PersistentAcquireRequest,
    PersistentReleaseParams,
    compute_env_digest,
    persistent_worker_settings,
)

_FAKE_CLAUDE = """
import json, os, sys
for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    env_ok = "HOST_SECRET_CANARY" not in os.environ and "CLAUDE_P_BRIDGE_KEY" not in os.environ
    print(json.dumps({"type": "result", "env_ok": env_ok, "home": os.environ.get("HOME", "")}), flush=True)
    break
"""

_FAKE_CODEX = """
import json, os, sys
for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    req = json.loads(line)
    if req.get("method") == "initialize":
        env_ok = "HOST_SECRET_CANARY" not in os.environ and "OPENAI_API_KEY" not in os.environ
        print(json.dumps({"jsonrpc": "2.0", "id": req.get("id", 1), "result": {"env_ok": env_ok}}), flush=True)
"""

_FAKE_AGY = """#!/usr/bin/env python3
import json, os, sys, uuid
cid = f"cid-zc-{os.getpid()}-{uuid.uuid4().hex[:6]}"
print(json.dumps({"event": "init", "conversation_id": cid}), flush=True)
for raw in sys.stdin:
    if raw.strip():
        print(json.dumps({"event": "result", "status": "SUCCESS", "conversation_id": cid}), flush=True)
"""


def _write_script(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body.lstrip("\n"), encoding="utf-8")
    p.chmod(0o755)
    return p


def _wait_ready(pool: DemandStandbyPool, n: int = 1, timeout_s: float = 5.0) -> None:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if int(pool.snapshot()["ready"]) >= n:  # type: ignore[arg-type]
            return
        time.sleep(0.02)
    raise AssertionError(f"pool did not reach ready>={n}: {pool.snapshot()}")


def _wait_gone(pgid: int, path: str, timeout_s: float = 3.0) -> None:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end and (_pgid_alive(pgid) or (path and Path(path).exists())):
        time.sleep(0.02)
    assert not _pgid_alive(pgid) and not (path and Path(path).exists())


def _assert_claude_zc_roundtrip(pool: DemandStandbyPool) -> None:
    pc = ProfileKey("claude-p", "m1", "low", "zero-canon", "d1", "zc")
    assert pool.claim(pc) is None
    _wait_ready(pool, 1)
    cl = pool.claim(pc)
    assert cl is not None and isinstance(cl.handle, ClaudeWarmHandle)
    h = cl.handle
    assert stat.S_IMODE(Path(h.zc_home_root).stat().st_mode) == 0o700
    assert h.proc.stdin is not None and h.proc.stdout is not None
    h.proc.stdin.write(encode_claude_stdin_prompt("ping", stream_json_input=True))
    h.proc.stdin.flush()
    assert '"env_ok": true' in h.proc.stdout.readline().decode("utf-8")
    old_pgid, old_home = h.pgid, h.zc_home_root
    pool.release_claimed(cl.slot_id, success=True)
    _wait_gone(old_pgid, old_home)
    _wait_ready(pool, 1)
    cl2 = pool.claim(pc)
    assert cl2 is not None and isinstance(cl2.handle, ClaudeWarmHandle) and cl2.handle.zc_home_root != old_home
    pool.release_claimed(cl2.slot_id, success=True)


def test_zero_canon_single_turn_isolation(tmp_path: Path) -> None:
    claude_py = _write_script(tmp_path, "fake_claude.py", _FAKE_CLAUDE)
    codex_py = _write_script(tmp_path, "fake_codex.py", _FAKE_CODEX)
    base_env = {**os.environ, "HOST_SECRET_CANARY": "secret-val-99", "CLAUDE_P_BRIDGE_KEY": "k1", "OPENAI_API_KEY": "k2"}
    c_ad = ClaudeStandbyAdapter(argv_factory=lambda _p: [sys.executable, str(claude_py)], base_env_provider=lambda: base_env, settle_s=0.05)
    x_ad = CodexStandbyAdapter(argv_factory=lambda _p: [sys.executable, str(codex_py)], base_env_provider=lambda: base_env)
    cfg = {"BRIDGE_DEMAND_STANDBY_ENABLED": "1", "BRIDGE_DEMAND_STANDBY_SLIDING_TTL_S": "30",
           "BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS": "3", "BRIDGE_DEMAND_STANDBY_MAX_TOTAL_RSS_MB": "2048"}
    pool = DemandStandbyPool({"claude-p": c_ad, "codex": x_ad}, config_provider=lambda: (cfg, {}))
    try:
        _assert_claude_zc_roundtrip(pool)
        px = ProfileKey("codex", "m2", "low", "zero-canon", "d2", "zc")
        assert pool.claim(px) is None
        _wait_ready(pool, 1)
        cx = pool.claim(px)
        assert cx is not None and isinstance(cx.handle, CodexWarmHandle)
        assert stat.S_IMODE(Path(cx.handle.zc_home_root).stat().st_mode) == 0o700
        x_home = cx.handle.zc_home_root
        pool.release_claimed(cx.slot_id, success=True)
        _wait_gone(0, x_home)
    finally:
        pool.drain_and_shutdown(timeout_s=3.0)


def test_standard_compat(tmp_path: Path) -> None:
    claude_py = _write_script(tmp_path, "fake_std.py", _FAKE_CLAUDE)
    ad = ClaudeStandbyAdapter(argv_factory=lambda _p: [sys.executable, str(claude_py)], settle_s=0.05)
    cfg = {"BRIDGE_DEMAND_STANDBY_ENABLED": "1", "BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS": "2",
           "BRIDGE_DEMAND_STANDBY_MAX_SLOTS_PER_PROFILE": "1", "BRIDGE_DEMAND_STANDBY_MAX_TOTAL_RSS_MB": "2048"}
    pool = DemandStandbyPool({"claude-p": ad}, config_provider=lambda: (cfg, {}))
    try:
        p = ProfileKey("claude-p", "m1", "high", "standard", "d-std", "std")
        pool.submit_demand(p)
        _wait_ready(pool, 1)
        c1 = pool.claim(p, session_key="sess-A")
        assert c1 is not None
        pool.release_claimed(c1.slot_id, success=True)
        # Cross-session isolation (F-022): sess-B MUST NEVER receive sess-A's pinned slot
        assert pool.claim(p, session_key="sess-B") is None
        c_same = pool.claim(p, session_key="sess-A")
        assert c_same is not None and c_same.slot_id == c1.slot_id
        pool.release_claimed(c_same.slot_id, success=False)
        # Stateless standard (session_key=None) retires after 1 turn
        _wait_ready(pool, 1)
        c_none = pool.claim(p, session_key=None)
        assert c_none is not None
        pool.release_claimed(c_none.slot_id, success=True)
        assert pool.claim(p, session_key="sess-C") is None or pool.snapshot()["disposes"] >= 2  # type: ignore[operator]
    finally:
        pool.drain_and_shutdown(timeout_s=3.0)


def test_adapter_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    claude_py = _write_script(tmp_path, "fake_c2.py", _FAKE_CLAUDE)
    codex_py = _write_script(tmp_path, "fake_x2.py", _FAKE_CODEX)
    agy_py = _write_script(tmp_path, "fake_agy.py", _FAKE_AGY)
    for ad, pk in (
        (ClaudeStandbyAdapter(argv_factory=lambda _p: [sys.executable, str(claude_py)], settle_s=0.05),
         ProfileKey("claude-p", "m1", "low", "zero-canon", "d1", "zc")),
        (CodexStandbyAdapter(argv_factory=lambda _p: [sys.executable, str(codex_py)]),
         ProfileKey("codex", "m1", "low", "zero-canon", "d1", "zc")),
    ):
        h = ad.spawn_warm(pk, timeout_s=5.0)
        try:
            assert ad.is_alive(h) and ad.claim(h) is h and ad.rss_mb(h) >= 0.0
        finally:
            ad.dispose(h)
        assert not ad.is_alive(h)
    # Agy adapter unlocks zero-canon + empty chat_key when BRIDGE_DEMAND_STANDBY_ENABLED=1 and retires after 1 turn
    monkeypatch.setenv("BRIDGE_DEMAND_STANDBY_ENABLED", "1")
    cfg_path = tmp_path / "dyn.json"
    cfg_path.write_text('{"BRIDGE_AGY_PERSISTENT_WORKER_ENABLED":true,"BRIDGE_AGY_STANDBY_ENABLED":true,"persistent_worker_max_slots":6}', encoding="utf-8")
    cfg = persistent_worker_settings(config_path=cfg_path)
    apool = AgyPersistentWorkerPool()
    try:
        req = PersistentAcquireRequest(
            chat_key="", cid="", model="gemini-4-neon", effort="high", cwd=str(tmp_path),
            env_digest=compute_env_digest("plan", False, str(tmp_path)), review_profile="zero-canon",
            argv_builder=lambda: [sys.executable, str(agy_py)], env=os.environ.copy(),
        )
        lease = apool.acquire(req, cfg)
        assert lease is not None and lease.max_turns == 1 and isinstance(apool._standby, AgyStandbyManager)
        apool.release(lease, PersistentReleaseParams(success=True, cid="c1"))
        assert lease.slot_id not in apool._slot_bindings
    finally:
        apool.shutdown()


@pytest.mark.skipif(os.environ.get("BRIDGE_LIVE_STANDBY") != "1", reason="live standby probe opt-in")
def test_live_handshake() -> None:
    ad = CodexStandbyAdapter()
    h = ad.spawn_warm(ProfileKey("codex", "gpt-6.1-terra", "low", "zero-canon", "live", "zc"), timeout_s=20.0)
    try:
        time.sleep(2.0)
        assert ad.is_alive(h) and ad.rss_mb(h) > 0.0
    finally:
        ad.dispose(h)


def test_kill_switch_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_DEMAND_STANDBY_ENABLED", "0")
    sentinel = SimpleNamespace(pid=42)
    req_a = ClaudeRunRequest("m1", "high", cmd=["claude", "--model", "m1"], child_env={"HOME": "/a"})
    req_b = ClaudeRunRequest("m1", "high", cmd=["claude", "--model", "m1", "--strict"], child_env={"HOME": "/b"})
    proc, warm, rel = acquire_claude_run_proc(req_a, lambda: sentinel)  # type: ignore[arg-type,return-value]
    assert proc is sentinel and warm is False
    rel()
    rel()  # idempotent double close
    from core.stdio_resident.claude_standby_adapter import _once, _req_digest
    assert _req_digest(req_a) != _req_digest(req_b)
    calls: list[int] = []
    guarded = _once(lambda: calls.append(1))
    guarded()
    guarded()
    assert calls == [1]
    # Codex hook returns immediately without raising or creating pool when disabled
    maybe_run_codex_standby_hook(object(), SimpleNamespace(), SimpleNamespace(active=True), SimpleNamespace())  # type: ignore[arg-type]


def test_api_surface_unchanged() -> None:
    for rel in ("bridges/claude-p-bridge/server.py", "bridges/agy-bridge/server.py"):
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "/standby" not in src and "/v1/standby" not in src


def test_profile_exact_match_and_redaction(caplog: pytest.LogCaptureFixture) -> None:
    class _FailAdapter:
        def spawn_warm(self, profile: ProfileKey, *, timeout_s: float) -> object:
            raise RuntimeError("boom")
        def is_alive(self, handle: object) -> bool:
            return False
        def claim(self, handle: object) -> object:
            return handle
        def dispose(self, handle: object) -> None:
            return None
        def rss_mb(self, handle: object) -> float:
            return 0.0

    cfg = {"BRIDGE_DEMAND_STANDBY_ENABLED": "1", "BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS": "2"}
    pool = DemandStandbyPool({"b1": _FailAdapter()}, config_provider=lambda: (cfg, {}))
    try:
        with caplog.at_level(logging.DEBUG):
            p = ProfileKey("b1", "m1", "high", "zero-canon", "digest-safe-1234", "zc")
            pool.submit_demand(p)
            time.sleep(0.1)
            assert pool.claim(ProfileKey("b1", "m1", "low", "zero-canon", "digest-safe-1234", "zc")) is None
        logs = "\n".join(r.getMessage() for r in caplog.records)
        assert "digest-safe-" in logs and "HOST_SECRET_CANARY" not in logs
    finally:
        pool.drain_and_shutdown()


def test_dispose_exception_preserves_zc_cleanup_and_keeps_live_slot_in_rss(tmp_path: Path) -> None:
    zc_dir = tmp_path / "zc-claude-err"
    zc_dir.mkdir(mode=0o700)
    fake_proc = SimpleNamespace(pid=999999, stdin=SimpleNamespace(close=lambda: (_ for _ in ()).throw(RuntimeError("reentrant"))),
                                stdout=None, stderr=None, poll=lambda: 0, wait=lambda timeout=0: 0)
    ClaudeStandbyAdapter().dispose(ClaudeWarmHandle(fake_proc, ProfileKey("claude-p", "m1", "low", "zero-canon", "d", "zc"), str(zc_dir), str(zc_dir)))  # type: ignore[arg-type]
    assert not zc_dir.exists()
    state = {"alive": True, "calls": 0}
    def _disp(_h: object) -> None:
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("kill failed")
        state["alive"] = False
    ad = SimpleNamespace(spawn_warm=lambda p, *, timeout_s: SimpleNamespace(profile=p), is_alive=lambda _h: state["alive"],
                         claim=lambda h: h, dispose=_disp, rss_mb=lambda _h: 500.0)
    cfg = {"BRIDGE_DEMAND_STANDBY_ENABLED": "1", "BRIDGE_DEMAND_STANDBY_GLOBAL_MAX_SLOTS": "1", "BRIDGE_DEMAND_STANDBY_MAX_TOTAL_RSS_MB": "500"}
    pool = DemandStandbyPool({"b1": ad}, config_provider=lambda: (cfg, {}))  # type: ignore[dict-item]
    try:
        p = ProfileKey("b1", "m1", "high", "zero-canon", "d", "zc")
        pool.submit_demand(p)
        _wait_ready(pool, 1)
        cl = pool.claim(p)
        assert cl is not None
        pool.release_claimed(cl.slot_id, success=True)
        end = time.monotonic() + 2.0
        while time.monotonic() < end and state["calls"] < 1:
            time.sleep(0.01)
        time.sleep(0.05)
        assert pool.snapshot()["slots"] == 1 and pool.snapshot()["total_rss_mb"] == 500.0 and pool.snapshot()["ready"] == 0
        assert pool.reap_once() >= 1
        _wait_ready(pool, 1)
    finally:
        pool.drain_and_shutdown()
