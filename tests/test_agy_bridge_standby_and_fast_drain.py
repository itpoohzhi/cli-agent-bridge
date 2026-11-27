"""L1/L2 тесты standby-пула (turn 0) и fast-complete выхода из SQLite-drain в agy-bridge."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
AGY_BRIDGE_DIR = REPO_ROOT / "bridges" / "agy-bridge"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(AGY_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(AGY_BRIDGE_DIR))

from agy_runtime.persistent_run_hooks import (  # noqa: E402
    RunPumpDrainContext,
    finish_run_pump_drain,
    iter_run_stdout_lines,
)
from agy_runtime.persistent_standby_pool import (  # noqa: E402
    StandbyProfileKey,
    StandbyReadySlot,
    standby_argv_digest,
)
from agy_runtime.persistent_worker_adapter import AgyPersistentWorkerPool  # noqa: E402
from agy_runtime.persistent_worker_config import (  # noqa: E402
    PersistentAcquireRequest,
    PersistentReleaseParams,
    compute_env_digest,
    persistent_worker_settings,
)

_FAKE_EAGER_INIT_AGY = """#!/usr/bin/env python3
import json, os, sys, uuid

cid = f"cid-sb-{os.getpid()}-{uuid.uuid4().hex[:6]}"
print(json.dumps({"event": "init", "conversation_id": cid, "tools": 60}), flush=True)
turn = 0
for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    turn += 1
    print(json.dumps({"event": "message", "role": "assistant", "content": f"PID={os.getpid()} T={turn}"}), flush=True)
    print(json.dumps({"event": "result", "status": "SUCCESS", "conversation_id": cid}), flush=True)
"""


def _write_fake_eager_launcher(tmp_dir: Path) -> Path:
    script = tmp_dir / "fake_eager_agy.py"
    script.write_text(_FAKE_EAGER_INIT_AGY, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


def _load_agy_server():
    mod_name = "_agy_bridge_server_standby_test"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, AGY_BRIDGE_DIR / "server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestStandbyAndFastDrain(unittest.TestCase):
    def test_defaults_off_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = persistent_worker_settings(config_path=Path(td) / "missing.json")
        self.assertFalse(cfg.standby_enabled)
        self.assertFalse(cfg.fast_drain_enabled)
        self.assertEqual(cfg.standby_max_slots, 1)
        self.assertEqual(cfg.standby_init_timeout_s, 30.0)
        self.assertEqual(cfg.fast_drain_min_s, 0.015)

    def test_standby_prewarm_claim_turn1_reuse_and_live_kill_switch(self) -> None:
        pool = AgyPersistentWorkerPool()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            launcher = _write_fake_eager_launcher(td_path)
            cfg_path = td_path / "dynamic_config.json"
            cfg_path.write_text(
                json.dumps({
                    "BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True,
                    "BRIDGE_AGY_STANDBY_ENABLED": True,
                    "BRIDGE_AGY_PERSISTENT_FAST_DRAIN_ENABLED": True,
                    "persistent_standby_max_slots": 1,
                    "persistent_worker_max_slots": 6,
                }),
                encoding="utf-8",
            )
            cfg = persistent_worker_settings(config_path=cfg_path)
            env_digest = compute_env_digest("plan", False, "/tmp/home")

            def _req(
                chat_key: str,
                cid: str = "",
                review_profile: str = "standard",
                extra_args: list[str] | None = None,
            ) -> PersistentAcquireRequest:
                argv = [sys.executable, str(launcher), *(extra_args or [])]
                return PersistentAcquireRequest(
                    chat_key=chat_key, cid=cid, model="gemini-4-neon", effort="high",
                    cwd=str(td_path), env_digest=env_digest, review_profile=review_profile,
                    argv_builder=lambda: list(argv), env=os.environ.copy(),
                    resume_base_idx=1 if cid else 0,
                )

            try:
                # 1. Chat A cold turn 0 triggers background standby prewarm
                lease_a = pool.acquire(_req("chat-A"), cfg)
                assert lease_a is not None
                self.assertFalse(lease_a.standby_claimed)
                _ = lease_a.handle.read_stdout_line_outcome(timeout_s=3.0)
                lease_a.handle.write(b'{"event":"user"}\n')
                _ = lease_a.handle.read_stdout_line_outcome(timeout_s=3.0)
                _ = lease_a.handle.read_stdout_line_outcome(timeout_s=3.0)
                pool.release(lease_a, PersistentReleaseParams(success=True, cid="cid-a"))

                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline and pool._standby.stats()[0] < 1:
                    time.sleep(0.05)
                self.assertEqual(pool._standby.stats()[0], 1)

                # 2. Zero-canon and --add-dir / --resume requests MUST NOT claim or prewarm standby (F-013/F-003)
                lease_zc = pool.acquire(_req("chat-ZC", review_profile="zero-canon"), cfg)
                assert lease_zc is not None
                self.assertFalse(lease_zc.standby_claimed)
                pool.release(lease_zc, PersistentReleaseParams(success=False, cancel=True))
                self.assertEqual(pool._standby.stats()[0], 1)

                lease_add = pool.acquire(_req("chat-ADD", extra_args=["--add-dir", "/tmp/x"]), cfg)
                assert lease_add is not None
                self.assertFalse(lease_add.standby_claimed)
                self.assertEqual(lease_add.prefetched_init_line, "")
                pool.release(lease_add, PersistentReleaseParams(success=False, cancel=True))
                self.assertEqual(pool._standby.stats()[0], 1)

                # 3. Chat B turn 0 claims warm standby slot; iter_run_stdout_lines replays init ONCE!
                lease_b0 = pool.acquire(_req("chat-B"), cfg)
                assert lease_b0 is not None
                self.assertTrue(lease_b0.standby_claimed)
                self.assertTrue(lease_b0.fast_drain_enabled)
                self.assertIn('"event": "init"', lease_b0.prefetched_init_line)
                pid_b0 = lease_b0.handle.proc.pid
                cid_b = json.loads(lease_b0.prefetched_init_line)["conversation_id"]
                lease_b0.handle.write(b'{"event":"user"}\n')
                fake_run = SimpleNamespace(
                    _persistent_lease=lease_b0, _stop_watch=threading.Event(), capacity_exhausted=""
                )
                lines: list[str] = []
                for line in iter_run_stdout_lines(fake_run):
                    lines.append(line)
                    if '"event": "result"' in line:
                        break
                self.assertEqual(len(lines), 3)
                self.assertIn('"event": "init"', lines[0])
                self.assertIn("T=1", lines[1])
                self.assertIn('"event": "result"', lines[2])
                self.assertEqual(lease_b0.prefetched_init_line, "")

                tail_stub = SimpleNamespace(drain_deadline=0.0, fast_complete_drain=False, fast_drain_min_s=0.0)
                drain_run = SimpleNamespace(
                    _persistent_lease=lease_b0, _tail=tail_stub, _proc_done=threading.Event(),
                    _join_source=lambda *_a, **_kw: None, _persistent_turn_ok=True, err_box=[],
                )
                rc = finish_run_pump_drain(
                    drain_run,
                    RunPumpDrainContext(result_ev=True, drain_max_s=1.0, proc_exit_wait_s=0.1, config_path=cfg_path),
                )
                self.assertEqual(rc, 0)
                self.assertTrue(tail_stub.fast_complete_drain)
                self.assertAlmostEqual(tail_stub.fast_drain_min_s, 0.015)
                pool.release(lease_b0, PersistentReleaseParams(success=True, cid=cid_b))

                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline and pool._standby.stats()[0] < 1:
                    time.sleep(0.05)
                self.assertEqual(pool._standby.stats()[0], 1)
                slots_before_off = pool.health_snapshot(enabled=True)["slots"]

                # 4. Chat B turn 1 (resume=1) hits the EXACT SAME PID via chat alias!
                lease_b1 = pool.acquire(_req("chat-B", cid=cid_b), cfg)
                assert lease_b1 is not None
                self.assertFalse(lease_b1.standby_claimed)
                self.assertEqual(lease_b1.prefetched_init_line, "")
                self.assertEqual(lease_b1.handle.proc.pid, pid_b0)
                pool.release(lease_b1, PersistentReleaseParams(success=True, cid=cid_b))

                # 5. Live toggle standby OFF evicts idle standby slot while keeping active chat-B PID!
                cfg_off_path = td_path / "dyn_off.json"
                cfg_off_path.write_text(
                    json.dumps({
                        "BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True,
                        "BRIDGE_AGY_STANDBY_ENABLED": False,
                        "persistent_worker_max_slots": 6,
                    }),
                    encoding="utf-8",
                )
                cfg_off = persistent_worker_settings(config_path=cfg_off_path)
                lease_b2 = pool.acquire(_req("chat-B", cid=cid_b), cfg_off)
                assert lease_b2 is not None
                self.assertEqual(lease_b2.handle.proc.pid, pid_b0)
                self.assertEqual(pool._standby.stats()[0], 0)
                self.assertLess(pool.health_snapshot(enabled=True)["slots"], slots_before_off)
                pool.release(lease_b2, PersistentReleaseParams(success=True, cid=cid_b))
            finally:
                pool.shutdown()

    def test_standby_stale_slot_keeps_turn1_reuse_and_never_replays_stale_init(self) -> None:
        """F-001/F-009/F-010: вытесненный standby не ломает reuse на Turn 1 и не реплеит старый init."""
        pool = AgyPersistentWorkerPool()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            launcher = _write_fake_eager_launcher(td_path)
            cfg_path = td_path / "dynamic_config.json"
            cfg_path.write_text(
                json.dumps({
                    "BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True,
                    "BRIDGE_AGY_STANDBY_ENABLED": True,
                    "persistent_standby_max_slots": 1,
                }),
                encoding="utf-8",
            )
            cfg = persistent_worker_settings(config_path=cfg_path)
            env_digest = compute_env_digest("plan", False, "/tmp/home")
            argv = [sys.executable, str(launcher)]
            argv_digest = standby_argv_digest(argv)
            assert argv_digest is not None

            def _req(chat_key: str, cid: str = "") -> PersistentAcquireRequest:
                return PersistentAcquireRequest(
                    chat_key=chat_key, cid=cid, model="gemini-4-neon", effort="high",
                    cwd=str(td_path), env_digest=env_digest, review_profile="standard",
                    argv_builder=lambda: list(argv), env=os.environ.copy(),
                    resume_base_idx=1 if cid else 0,
                )

            try:
                inner_pool = pool._ensure_pool(cfg)
                assert inner_pool is not None
                pkey = StandbyProfileKey("gemini-4-neon", "high", str(td_path), env_digest, "standard", argv_digest)
                pool._standby._ready[pkey] = StandbyReadySlot(
                    standby_chat_key="__standby__:gone",
                    slot_id="nonexistent-slot-id",
                    generation=1,
                    init_line='{"event":"init","conversation_id":"stale-cid"}',
                    cid="stale-cid",
                    created_mono=time.monotonic(),
                    pool_id=id(inner_pool),
                )
                lease0 = pool.acquire(_req("chat-stale"), cfg)
                assert lease0 is not None
                self.assertFalse(lease0.standby_claimed)
                self.assertEqual(lease0.prefetched_init_line, "")
                pid0 = lease0.handle.proc.pid
                _ = lease0.handle.read_stdout_line_outcome(timeout_s=3.0)
                lease0.handle.write(b'{"event":"user"}\n')
                _ = lease0.handle.read_stdout_line_outcome(timeout_s=3.0)
                _ = lease0.handle.read_stdout_line_outcome(timeout_s=3.0)
                pool.release(lease0, PersistentReleaseParams(success=True, cid="cid-stale-live"))

                # Turn 1 MUST reuse the exact same PID (no orphaned __standby__ slot!)
                lease1 = pool.acquire(_req("chat-stale", cid="cid-stale-live"), cfg)
                assert lease1 is not None
                self.assertEqual(lease1.handle.proc.pid, pid0)
                pool.release(lease1, PersistentReleaseParams(success=True, cid="cid-stale-live"))
            finally:
                pool.shutdown()

    def test_standby_ttl_expiry_prunes_profile_a_and_unblocks_profile_b_at_cap1(self) -> None:
        """F-002/F-014: протухший standby профиля A вычищается при запросе профиля B при cap=1."""
        pool = AgyPersistentWorkerPool()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            dir_a = td_path / "proj_a"
            dir_b = td_path / "proj_b"
            dir_a.mkdir()
            dir_b.mkdir()
            launcher = _write_fake_eager_launcher(td_path)
            cfg_path = td_path / "dynamic_config.json"
            cfg_path.write_text(
                json.dumps({
                    "BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True,
                    "BRIDGE_AGY_STANDBY_ENABLED": True,
                    "persistent_standby_max_slots": 1,
                    "persistent_standby_ttl_s": 30.0,
                    "persistent_worker_max_slots": 6,
                }),
                encoding="utf-8",
            )
            cfg = persistent_worker_settings(config_path=cfg_path)
            env_digest = compute_env_digest("plan", False, "/tmp/home")

            def _req(chat_key: str, cwd: Path) -> PersistentAcquireRequest:
                return PersistentAcquireRequest(
                    chat_key=chat_key, cid="", model="gemini-4-neon", effort="high",
                    cwd=str(cwd), env_digest=env_digest, review_profile="standard",
                    argv_builder=lambda: [sys.executable, str(launcher)], env=os.environ.copy(),
                )

            try:
                # Warm Profile A standby
                la = pool.acquire(_req("chat-a", dir_a), cfg)
                assert la is not None
                pool.release(la, PersistentReleaseParams(success=False, cancel=True))
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline and pool._standby.stats()[0] < 1:
                    time.sleep(0.05)
                self.assertEqual(pool._standby.stats()[0], 1)

                # Age Profile A standby past TTL (30s)
                for pkey, slot in list(pool._standby._ready.items()):
                    pool._standby._ready[pkey] = StandbyReadySlot(
                        standby_chat_key=slot.standby_chat_key, slot_id=slot.slot_id,
                        generation=slot.generation, init_line=slot.init_line, cid=slot.cid,
                        created_mono=time.monotonic() - 120.0, pool_id=slot.pool_id,
                    )

                # Request Profile B -> must prune & close expired A and prewarm B!
                lb = pool.acquire(_req("chat-b", dir_b), cfg)
                assert lb is not None
                pool.release(lb, PersistentReleaseParams(success=False, cancel=True))
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline and not any(k.cwd == str(dir_b) for k in pool._standby._ready):
                    time.sleep(0.05)
                self.assertTrue(any(k.cwd == str(dir_b) for k in pool._standby._ready))
                self.assertFalse(any(k.cwd == str(dir_a) for k in pool._standby._ready))
                self.assertEqual(pool.health_snapshot(enabled=True)["slots"], 1)
            finally:
                pool.shutdown()

    def test_argv_digest_rejects_add_dir_and_resume_and_separates_flags(self) -> None:
        self.assertIsNone(standby_argv_digest(["agy", "--add-dir", "/tmp/a"]))
        self.assertIsNone(standby_argv_digest(["agy", "--add-dir=/tmp/a"]))
        self.assertIsNone(standby_argv_digest(["agy", "--resume", "cid-1"]))
        self.assertIsNone(standby_argv_digest(["agy", "--resume=cid-1"]))
        d1 = standby_argv_digest(["agy", "--mode", "plan"])
        d2 = standby_argv_digest(["agy", "--mode", "edit"])
        self.assertIsNotNone(d1)
        self.assertIsNotNone(d2)
        self.assertNotEqual(d1, d2)

    def test_fast_complete_drain_exits_early_only_when_complete_quiet_and_no_pending(self) -> None:
        srv = _load_agy_server()

        def _make_tail(*, fast: bool, final_planner: bool, pending: int, window_s: float = 0.20, emit_once: bool = False):
            tail = object.__new__(srv._TranscriptTail)
            tail.stop_event = threading.Event()
            tail.sqlite_active = False
            tail.emitted = 0
            tail.end_marker = False
            tail.final_planner = final_planner
            tail.drain_deadline = time.monotonic() + window_s
            tail.fast_complete_drain = fast
            tail.fast_drain_min_s = 0.015
            tail.run_ref = None
            tail.drain_outcome = ""
            emitted_flag = {"done": False}

            def _fake_read() -> None:
                if emit_once and not emitted_flag["done"]:
                    emitted_flag["done"] = True
                    tail.emitted += 1

            tail._read_transcript = _fake_read
            tail._poll_sqlite = lambda: (0, 0)
            tail._pending_steps = lambda: pending
            tail._cid8 = lambda: "fast1234"
            return tail

        # 1. Fast drain ON + final_planner=True + pending=0 + quiet -> exits early
        t_fast = _make_tail(fast=True, final_planner=True, pending=0, window_s=0.22)
        t0 = time.monotonic()
        t_fast._drain_post_eof()
        self.assertLess(time.monotonic() - t0, 0.12)
        self.assertEqual(t_fast.drain_outcome, "complete")

        # 2. Fast drain ON + pending=1 -> waits full window
        t_pend = _make_tail(fast=True, final_planner=True, pending=1, window_s=0.14)
        t0 = time.monotonic()
        t_pend._drain_post_eof()
        self.assertGreaterEqual(time.monotonic() - t0, 0.12)

        # 3. Fast drain OFF (default) -> waits full window
        t_off = _make_tail(fast=False, final_planner=True, pending=0, window_s=0.14)
        t0 = time.monotonic()
        t_off._drain_post_eof()
        self.assertGreaterEqual(time.monotonic() - t0, 0.12)

        # 4. Fast drain ON + active emission on first iter -> does NOT exit on that active iter, completes after quiet iter
        t_emit = _make_tail(fast=True, final_planner=True, pending=0, window_s=0.22, emit_once=True)
        t0 = time.monotonic()
        t_emit._drain_post_eof()
        self.assertEqual(t_emit.emitted, 1)
        self.assertLess(time.monotonic() - t0, 0.14)


if __name__ == "__main__":
    unittest.main()
