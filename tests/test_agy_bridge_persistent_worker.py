"""L1/L2 тесты подключения ResidentProcessPool в bridges/agy-bridge (:9887)."""

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
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
AGY_BRIDGE_DIR = REPO_ROOT / "bridges" / "agy-bridge"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(AGY_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(AGY_BRIDGE_DIR))

from agy_runtime.persistent_run_hooks import (  # noqa: E402
    RunSpawnContext,
    resolve_run_chat_key,
    start_run_process,
)
from agy_runtime.persistent_worker_adapter import (  # noqa: E402
    AgyPersistentWorkerPool,
    PersistentAcquireRequest,
    PersistentReleaseParams,
    compute_env_digest,
)
from agy_runtime.persistent_worker_config import (  # noqa: E402
    PersistentWorkerSettings,
    persistent_worker_settings,
)


def _load_agy_server():
    mod_name = "agy_bridge_server_persistent_test"
    cached = sys.modules.get(mod_name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(mod_name, AGY_BRIDGE_DIR / "server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(mod_name, None)
        raise
    return mod


FAKE_AGY_SCRIPT = r"""#!/usr/bin/env python3
import json
import os
import sys
import time

cid = os.environ.get("FAKE_AGY_CID", "cid-persistent-001")
pid = os.getpid()
mode = os.environ.get("FAKE_AGY_MODE", "ok")
turn = 0

for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    turn += 1
    msg = json.loads(raw)
    text_in = ""
    content = (msg.get("message") or {}).get("content")
    if isinstance(content, list) and content:
        text_in = str(content[0].get("text") or "")
    elif isinstance(content, str):
        text_in = content

    if turn == 1:
        print(json.dumps({"event": "init", "conversation_id": cid, "init": {"tools": []}}), flush=True)

    if mode == "slow_cancel":
        time.sleep(10.0)
        break

    if mode == "error_on_turn2" and turn == 2:
        print(json.dumps({
            "event": "result",
            "conversation_id": cid,
            "result": {"conversation_id": cid, "status": "ERROR", "error": "boom"},
        }), flush=True)
        continue

    reply = f"pid={pid} turn={turn} echo={text_in}"
    print(json.dumps({
        "event": "step_update",
        "conversation_id": cid,
        "step_update": {"step_type": "agent_response", "step_index": turn, "text_delta": reply},
    }), flush=True)
    print(json.dumps({
        "event": "result",
        "conversation_id": cid,
        "result": {"conversation_id": cid, "status": "SUCCESS", "response": reply, "num_turns": turn},
    }), flush=True)

    if mode == "stale_leak_after_result":
        time.sleep(0.05)
        print(json.dumps({"event": "step_update", "step_update": {"step_type": "agent_response", "text_delta": "STALE"}}), flush=True)
"""


def _write_fake_launcher(tmp_dir: Path) -> Path:
    launcher = tmp_dir / "fake-agy.py"
    launcher.write_text(FAKE_AGY_SCRIPT, encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return launcher


class TestPersistentWorkerConfig(unittest.TestCase):
    def test_defaults_off_and_clamped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "dynamic_config.json"
            cfg_path.write_text("{}", encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=False):
                for k in list(os.environ):
                    if k.startswith("AGY_BRIDGE_PERSISTENT_") or k.startswith("AGY_BRIDGE_DRAIN_"):
                        os.environ.pop(k, None)
                cfg = persistent_worker_settings(config_path=cfg_path)
            self.assertFalse(cfg.enabled)
            self.assertEqual(cfg.max_slots, 8)
            self.assertAlmostEqual(cfg.lease_wait_s, 0.25)
            self.assertAlmostEqual(cfg.pump_tick_s, 0.5)
            self.assertAlmostEqual(cfg.persistent_drain_window_s, 0.10)
            self.assertAlmostEqual(cfg.drain_window_s, 0.35)
            self.assertEqual(cfg.max_turns, 50)

    def test_dynamic_config_and_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "dynamic_config.json"
            cfg_path.write_text(
                json.dumps(
                    {
                        "BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True,
                        "persistent_worker_max_slots": 4,
                        "persistent_worker_max_turns": 12,
                        "persistent_drain_window_s": 0.08,
                        "drain_window_s": 0.20,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ, {"AGY_BRIDGE_PERSISTENT_MAX_SLOTS": "6"}, clear=False
            ):
                cfg = persistent_worker_settings(config_path=cfg_path)
            self.assertTrue(cfg.enabled)
            self.assertEqual(cfg.max_slots, 6)  # env > dynamic_config
            self.assertEqual(cfg.max_turns, 12)
            self.assertAlmostEqual(cfg.persistent_drain_window_s, 0.08)
            self.assertAlmostEqual(cfg.drain_window_s, 0.20)


class TestAgyPersistentWorkerPool(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.launcher = _write_fake_launcher(self.tmp_path)
        self.pool = AgyPersistentWorkerPool()
        self.cfg = PersistentWorkerSettings(
            enabled=True,
            max_slots=2,
            lease_wait_s=0.15,
            idle_timeout_s=60.0,
            ttl_s=300.0,
            max_rss_mb=512,
            max_turns=3,
            pump_tick_s=0.1,
            persistent_drain_window_s=0.05,
            drain_window_s=0.15,
        )

    def tearDown(self) -> None:
        self.pool.shutdown()
        self.tmp.cleanup()

    def _acquire(self, chat_key: str = "chat-1", cid: str = "", extra_env: dict[str, str] | None = None, resume_base_idx: int = 0):
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        req = PersistentAcquireRequest(
            chat_key=chat_key,
            cid=cid,
            resume_base_idx=resume_base_idx,
            model="gemini-4-neon",
            effort="high",
            cwd=str(self.tmp_path),
            env_digest=compute_env_digest("plan", True, str(self.tmp_path)),
            review_profile="zero-canon",
            argv_builder=lambda: [sys.executable, str(self.launcher)],
            env=env,
        )
        return self.pool.acquire(req, self.cfg)

    def _release(self, lease, *, success: bool, cancel: bool = False, cid: str = "", still_enabled: bool = True) -> None:
        self.pool.release(
            lease,
            PersistentReleaseParams(
                success=success,
                cancel=cancel,
                cid=cid,
                still_enabled=still_enabled,
                max_slots=self.cfg.max_slots,
            ),
        )

    def _run_turn_on_lease(self, lease, text: str) -> tuple[int, int, str]:
        payload = json.dumps({"event": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}) + "\n"
        lease.handle.write(payload.encode("utf-8"))
        cid = ""
        resp = ""
        while True:
            kind, tagged = lease.handle.read_stdout_line_outcome(timeout_s=2.0)
            self.assertEqual(kind, "line")
            assert tagged is not None
            ev = json.loads(tagged.line)
            if ev.get("event") == "init":
                cid = ev.get("conversation_id", "")
            elif ev.get("event") == "result":
                res = ev["result"]
                cid = res.get("conversation_id", cid)
                resp = res.get("response", "")
                break
        return lease.handle.pid, int(res.get("num_turns", 0)), cid or resp

    def test_multi_turn_same_pid_and_cid_lookup(self) -> None:
        lease1 = self._acquire(chat_key="hermes-session-1", cid="")
        assert lease1 is not None
        self.assertFalse(lease1.reused)
        pid1, t1, cid = self._run_turn_on_lease(lease1, "hello-1")
        self.assertEqual(t1, 1)
        self._release(lease1, success=True, cid=cid)

        # Turn 2 arrives with only cid (no chat_key) -> must reuse same PID via cid LRU!
        lease2 = self._acquire(chat_key="", cid=cid, resume_base_idx=1)
        assert lease2 is not None
        self.assertTrue(lease2.reused)
        self.assertEqual(lease2.handle.pid, pid1)
        pid2, t2, _ = self._run_turn_on_lease(lease2, "hello-2")
        self.assertEqual(pid2, pid1)
        self.assertEqual(t2, 2)
        self._release(lease2, success=True, cid=cid)

        snap = self.pool.health_snapshot(enabled=True)
        self.assertEqual(snap["hits"], 1)
        self.assertEqual(snap["misses"], 1)
        self.assertEqual(snap["slots"], 1)

    def test_stateless_empty_chat_key_and_cid_returns_none_no_slot_pollution(self) -> None:
        lease = self._acquire(chat_key="", cid="")
        self.assertIsNone(lease)
        snap = self.pool.health_snapshot(enabled=True)
        self.assertEqual(snap["slots"], 0)
        self.assertEqual(snap["misses"], 0)

    def test_max_turns_rotation_tears_down_worker(self) -> None:
        # cfg.max_turns = 3 -> turn 3 triggers rotation (teardown after release)
        cid = "cid-rot"
        pids = []
        for idx in range(1, 5):
            lease = self._acquire(chat_key="rot-chat", cid=cid if idx > 1 else "", extra_env={"FAKE_AGY_CID": cid}, resume_base_idx=idx - 1)
            assert lease is not None
            pid, _, _ = self._run_turn_on_lease(lease, f"t-{idx}")
            pids.append(pid)
            self._release(lease, success=True, cid=cid)
        self.assertEqual(pids[0], pids[1])
        self.assertEqual(pids[1], pids[2])
        self.assertNotEqual(pids[2], pids[3])  # rotated on turn 4!

    def test_stale_stdout_triggers_fail_closed_desync_eviction(self) -> None:
        lease1 = self._acquire(chat_key="leak-chat", extra_env={"FAKE_AGY_MODE": "stale_leak_after_result"})
        assert lease1 is not None
        self._run_turn_on_lease(lease1, "t1")
        self._release(lease1, success=True, cid="cid-leak")
        time.sleep(0.15)  # allow fake worker to emit stale stdout line after result

        # Stale line arrived after release (tagged with next generation) -> fail-closed eviction!
        lease2 = self._acquire(chat_key="leak-chat", cid="cid-leak")
        self.assertIsNone(lease2)
        snap = self.pool.health_snapshot(enabled=True)
        self.assertEqual(snap["desync_evictions"], 1)
        self.assertEqual(snap["slots"], 0)
        self.assertFalse(lease1.handle.is_alive())

    def test_pool_overflow_returns_none_for_cold_fallback(self) -> None:
        # max_slots = 2 -> 3rd concurrent acquire returns None after lease_wait_s
        l1 = self._acquire(chat_key="c1")
        l2 = self._acquire(chat_key="c2")
        assert l1 is not None and l2 is not None
        l3 = self._acquire(chat_key="c3")
        self.assertIsNone(l3)
        snap = self.pool.health_snapshot(enabled=True)
        self.assertGreaterEqual(int(snap["fallbacks"]), 1)
        self._release(l1, success=False, cancel=True)
        self._release(l2, success=False, cancel=True)

    def test_kill_switch_disable_shuts_down_idle_and_tears_down_active(self) -> None:
        l1 = self._acquire(chat_key="ks-chat")
        assert l1 is not None
        pid1, _, cid = self._run_turn_on_lease(l1, "before-off")
        self._release(l1, success=True, cid=cid)

        # Toggle enabled=False -> pool detaches and shuts down idle worker immediately!
        disabled_cfg = PersistentWorkerSettings(enabled=False)
        l2 = self.pool.acquire(
            PersistentAcquireRequest(
                chat_key="ks-chat",
                cid=cid,
                model="gemini-4-neon",
                effort="high",
                cwd=str(self.tmp_path),
                env_digest="d",
                review_profile="zero-canon",
                argv_builder=lambda: [sys.executable, str(self.launcher)],
                env=os.environ,
            ),
            disabled_cfg,
        )
        self.assertIsNone(l2)
        time.sleep(0.1)
        self.assertFalse(l1.handle.is_alive())
        snap = self.pool.health_snapshot(enabled=False)
        self.assertEqual(snap["slots"], 0)


def _anchored_plan(srv, resumed: bool):
    """AD-002: resume-ход несёт якорь base_idx=1 (srv.Run не принимает resume_base_idx — он из plan)."""
    plan = srv._TurnPlan()
    plan.base_idx = 1 if resumed else 0
    return plan


class TestRunPersistentIntegration(unittest.TestCase):
    def test_run_end_to_end_reuses_worker_when_enabled(self) -> None:
        srv = _load_agy_server()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            launcher = _write_fake_launcher(td_path)
            dyn_cfg = td_path / "dynamic_config.json"
            dyn_cfg.write_text(
                json.dumps(
                    {
                        "BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True,
                        "persistent_worker_max_slots": 4,
                        "persistent_drain_window_s": 0.02,
                        "persistent_worker_pump_tick_s": 0.05,
                    }
                ),
                encoding="utf-8",
            )
            srv._PERSISTENT_POOL.shutdown()
            try:
                with (
                    mock.patch.object(srv, "DYNAMIC_CONFIG_PATH", dyn_cfg),
                    mock.patch.object(srv, "_launcher", return_value=str(launcher)),
                    mock.patch.object(srv, "_launch_env", return_value=os.environ.copy()),
                    mock.patch.object(srv, "_prespawn_plan", lambda _c, resumed, *_a, **_k: _anchored_plan(srv, resumed)),
                ):
                    run1 = srv.Run(
                        "ping-1",
                        "gemini-4-neon",
                        "high",
                        "req",
                        str(td_path),
                        "t1",
                        chat_key="hermes-chat-1",
                    )
                    done1 = None
                    while True:
                        kind, payload = run1.q.get(timeout=5.0)
                        self.assertNotEqual(kind, "pump_error", f"unexpected pump_error: {payload}")
                        if kind == "done":
                            done1 = payload
                            break
                    pid1 = run1.proc.pid
                    self.assertIsNotNone(run1._persistent_lease)
                    self.assertFalse(run1._persistent_reused)
                    run1.close()
                    assert done1 is not None
                    self.assertEqual(done1[0], 0)
                    self.assertIn("turn=1", done1[1])

                    # Turn 2 with cid from turn 1 -> must reuse exact same PID and spawn_ms == 0!
                    run2 = srv.Run("ping-2", "gemini-4-neon", "high", "req", str(td_path), "t2",
                                   conversation_id="cid-persistent-001", chat_key="hermes-chat-1")
                    done2 = None
                    while True:
                        kind, payload = run2.q.get(timeout=5.0)
                        self.assertNotEqual(kind, "pump_error", f"unexpected pump_error: {payload}")
                        if kind == "done":
                            done2 = payload
                            break
                    pid2 = run2.proc.pid
                    self.assertEqual(pid2, pid1)
                    self.assertTrue(run2._persistent_reused)
                    self.assertEqual(run2.spawn_ms, 0)
                    run2.close()
                    srv._cid_release("cid-persistent-001", run2.turn_id)
                    assert done2 is not None
                    self.assertEqual(done2[0], 0)
                    self.assertIn("turn=2", done2[1])
            finally:
                srv._PERSISTENT_POOL.shutdown()

    def test_run_cancel_persistent_kills_worker_and_is_idempotent(self) -> None:
        srv = _load_agy_server()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            launcher = _write_fake_launcher(td_path)
            dyn_cfg = td_path / "dynamic_config.json"
            dyn_cfg.write_text(
                json.dumps(
                    {
                        "BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True,
                        "persistent_worker_pump_tick_s": 0.05,
                        "persistent_drain_window_s": 0.02,
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["FAKE_AGY_MODE"] = "slow_cancel"
            srv._PERSISTENT_POOL.shutdown()
            try:
                with (
                    mock.patch.object(srv, "DYNAMIC_CONFIG_PATH", dyn_cfg),
                    mock.patch.object(srv, "_launcher", return_value=str(launcher)),
                    mock.patch.object(srv, "_launch_env", return_value=env),
                ):
                    run = srv.Run("hang", "gemini-4-neon", "high", "req", str(td_path), "tc", chat_key="cancel-chat")
                    lease = run._persistent_lease
                    assert lease is not None
                    time.sleep(0.15)
                    # Call cancel_persistent concurrently with close() -> idempotent, zero crash, worker dead
                    t1 = threading.Thread(target=run.cancel_persistent)
                    t2 = threading.Thread(target=run.close)
                    t1.start()
                    t2.start()
                    t1.join(timeout=5.0)
                    t2.join(timeout=5.0)
                    self.assertFalse(lease.handle.is_alive())
                    snap = srv._PERSISTENT_POOL.health_snapshot(enabled=True)
                    self.assertEqual(snap["slots"], 0)
                    self.assertGreaterEqual(int(snap["teardowns_cancel"]), 1)
            finally:
                srv._PERSISTENT_POOL.shutdown()

    def test_run_add_dirs_bypasses_persistent_pool(self) -> None:
        srv = _load_agy_server()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            launcher = _write_fake_launcher(td_path)
            dyn_cfg = td_path / "dynamic_config.json"
            dyn_cfg.write_text(
                json.dumps({"BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True}),
                encoding="utf-8",
            )
            srv._PERSISTENT_POOL.shutdown()
            try:
                with (
                    mock.patch.object(srv, "DYNAMIC_CONFIG_PATH", dyn_cfg),
                    mock.patch.object(srv, "_launcher", return_value=str(launcher)),
                    mock.patch.object(srv, "_launch_env", return_value=os.environ.copy()),
                ):
                    run = srv.Run(
                        "ping-add-dir",
                        "gemini-4-neon",
                        "high",
                        "req",
                        str(td_path),
                        "tad",
                        add_dir=td_path,
                        chat_key="add-dir-chat",
                    )
                    done = None
                    while True:
                        kind, payload = run.q.get(timeout=5.0)
                        if kind == "done":
                            done = payload
                            break
                    self.assertIsNone(run._persistent_lease)
                    run.close()
                    assert done is not None
                    self.assertEqual(done[0], 0)
            finally:
                srv._PERSISTENT_POOL.shutdown()

    def test_run_error_on_turn2_tears_down_worker(self) -> None:
        srv = _load_agy_server()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            launcher = _write_fake_launcher(td_path)
            dyn_cfg = td_path / "dynamic_config.json"
            dyn_cfg.write_text(
                json.dumps(
                    {
                        "BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True,
                        "persistent_worker_pump_tick_s": 0.05,
                        "persistent_drain_window_s": 0.02,
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["FAKE_AGY_MODE"] = "error_on_turn2"
            env["FAKE_AGY_CID"] = "cid-persistent-err"  # AD-002: bound_cid == run_cid на turn 2
            srv._PERSISTENT_POOL.shutdown()
            try:
                with (
                    mock.patch.object(srv, "DYNAMIC_CONFIG_PATH", dyn_cfg),
                    mock.patch.object(srv, "_launcher", return_value=str(launcher)),
                    mock.patch.object(srv, "_launch_env", return_value=env),
                    mock.patch.object(srv, "_prespawn_plan", lambda _c, resumed, *_a, **_k: _anchored_plan(srv, resumed)),
                ):
                    run1 = srv.Run("ok-1", "gemini-4-neon", "high", "req", str(td_path), "e1", chat_key="err-chat")
                    while True:
                        kind, payload = run1.q.get(timeout=5.0)
                        self.assertNotEqual(kind, "pump_error", f"unexpected pump_error: {payload}")
                        if kind == "done":
                            break
                    pid1 = run1.proc.pid
                    run1.close()

                    run2 = srv.Run("fail-2", "gemini-4-neon", "high", "req", str(td_path), "e2",
                                   conversation_id="cid-persistent-err", chat_key="err-chat")
                    done2 = None
                    while True:
                        kind, payload = run2.q.get(timeout=5.0)
                        self.assertNotEqual(kind, "pump_error", f"unexpected pump_error: {payload}")
                        if kind == "done":
                            done2 = payload
                            break
                    self.assertEqual(run2.proc.pid, pid1)
                    run2.close()
                    srv._cid_release("cid-persistent-err", run2.turn_id)
                    assert done2 is not None
                    self.assertNotEqual(done2[0], 0)

                    snap = srv._PERSISTENT_POOL.health_snapshot(enabled=True)
                    self.assertEqual(snap["slots"], 0)
                    self.assertGreaterEqual(int(snap["teardowns_error"]), 1)
            finally:
                srv._PERSISTENT_POOL.shutdown()

    def test_resolve_run_chat_key_priority_and_explicit_state(self) -> None:
        class _Exp:
            handled: bool = True
            session_key: str = "exp-key-42"

        k1 = resolve_run_chat_key({"sess_key": ("m", "c"), "explicit_state": _Exp(), "chat_id": "cid"})
        k2 = resolve_run_chat_key({"sess_key": ("m", "c"), "explicit_state": _Exp(), "chat_id": "cid"})
        k3 = resolve_run_chat_key({"sess_key": ("m", "other"), "explicit_state": _Exp(), "chat_id": "cid"})
        self.assertEqual(k1, k2)
        self.assertNotEqual(k1, k3)
        self.assertEqual(len(k1), 32)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in k1))
        self.assertEqual(
            resolve_run_chat_key({"sess_key": None, "explicit_state": _Exp(), "chat_id": ""}),
            "exp-key-42",
        )
        self.assertEqual(
            resolve_run_chat_key({"sess_key": (), "explicit_state": _Exp(), "chat_id": "cid"}),
            "exp-key-42",
        )
        self.assertEqual(
            resolve_run_chat_key({"sess_key": [], "explicit_state": _Exp(), "chat_id": "cid"}),
            "exp-key-42",
        )
        self.assertEqual(
            resolve_run_chat_key({"sess_key": (), "explicit_state": None, "chat_id": "chat-99"}),
            "chat-99",
        )
        self.assertEqual(
            resolve_run_chat_key({"sess_key": [], "explicit_state": None, "chat_id": "chat-99"}),
            "chat-99",
        )
        # F-002: пустые/None/пробельные элементы в кортеже/строке уходят в fallback
        self.assertEqual(
            resolve_run_chat_key({"sess_key": ("", ""), "explicit_state": _Exp(), "chat_id": "cid"}),
            "exp-key-42",
        )
        self.assertEqual(
            resolve_run_chat_key({"sess_key": (None, "   "), "explicit_state": None, "chat_id": "chat-99"}),
            "chat-99",
        )
        self.assertEqual(
            resolve_run_chat_key({"sess_key": "   ", "explicit_state": _Exp(), "chat_id": "cid"}),
            "exp-key-42",
        )
        # F-004: инъективное JSON-кодирование — без коллизий разделителя и скаляр vs кортеж
        self.assertNotEqual(
            resolve_run_chat_key({"sess_key": ("a\x1fb", "c")}),
            resolve_run_chat_key({"sess_key": ("a", "b\x1fc")}),
        )
        self.assertNotEqual(
            resolve_run_chat_key({"sess_key": ("x",)}),
            resolve_run_chat_key({"sess_key": "x"}),
        )
        self.assertEqual(
            resolve_run_chat_key({"sess_key": None, "explicit_state": None, "chat_id": "chat-99"}),
            "chat-99",
        )
        self.assertEqual(resolve_run_chat_key({}), "")

    def test_reconcile_disabled_shuts_down_idle_workers_on_next_start_run(self) -> None:
        srv = _load_agy_server()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            launcher = _write_fake_launcher(td_path)
            dyn_cfg = td_path / "dynamic_config.json"
            dyn_cfg.write_text(
                json.dumps({"BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True, "persistent_drain_window_s": 0.02}),
                encoding="utf-8",
            )
            srv._PERSISTENT_POOL.shutdown()
            try:
                with (
                    mock.patch.object(srv, "DYNAMIC_CONFIG_PATH", dyn_cfg),
                    mock.patch.object(srv, "_launcher", return_value=str(launcher)),
                    mock.patch.object(srv, "_launch_env", return_value=os.environ.copy()),
                ):
                    run1 = srv.Run("hi-1", "gemini-4-neon", "high", "req", str(td_path), "r1", chat_key="ks-live")
                    while True:
                        kind, _ = run1.q.get(timeout=5.0)
                        if kind == "done":
                            break
                    lease1 = run1._persistent_lease
                    assert lease1 is not None
                    run1.close()
                    self.assertTrue(lease1.handle.is_alive())

                    # Flip flag OFF on a fresh config file -> next Run reconciles & tears down idle worker!
                    dyn_off = td_path / "dynamic_config_off.json"
                    dyn_off.write_text(json.dumps({"BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": False}), encoding="utf-8")
                    with mock.patch.object(srv, "DYNAMIC_CONFIG_PATH", dyn_off):
                        run2 = srv.Run("hi-2", "gemini-4-neon", "high", "req", str(td_path), "r2", chat_key="ks-live")
                        while True:
                            kind, _ = run2.q.get(timeout=5.0)
                            if kind == "done":
                                break
                        self.assertIsNone(run2._persistent_lease)
                        run2.close()
                    self.assertFalse(lease1.handle.is_alive())
                    self.assertEqual(srv._PERSISTENT_POOL.health_snapshot(enabled=False)["slots"], 0)
            finally:
                srv._PERSISTENT_POOL.shutdown()

    def test_start_run_process_releases_cid_on_acquire_exception(self) -> None:
        class _BoomPool:
            def reconcile_disabled(self) -> None:
                return None

            def acquire(self, *_a: object, **_kw: object) -> None:
                raise RuntimeError("boom acquire")

        class _DummyRun:
            run_cid: str = "cid-boom"

        released: list[str] = []
        with tempfile.TemporaryDirectory() as td:
            cfg_on = Path(td) / "dynamic_config.json"
            cfg_on.write_text(json.dumps({"BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True}), encoding="utf-8")
            ctx = RunSpawnContext(
                pool=_BoomPool(),
                config_path=cfg_on,
                cmd=["true"],
                work_dir=td,
                launch_env={},
                model="gemini-4-neon",
                effort="high",
                cli_mode="plan",
                zero_canon=False,
                settings_arg="",
                add_dir=None,
                chat_key="c",
                spawn_cold=lambda: None,  # type: ignore[return-value]
                on_cold_fail=lambda: released.append("released"),
            )
            with self.assertRaises(RuntimeError):
                start_run_process(_DummyRun(), ctx)
        self.assertEqual(released, ["released"])

    def test_persistent_run_skips_p12_pgid_bind_reaper_and_quarantine(self) -> None:
        """F-001: реальный Handler._run_once_impl не отдаёт persistent PID в job.pgid, bind_reaper и p12."""
        srv = _load_agy_server()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            launcher = _write_fake_launcher(td_path)
            dyn_on = td_path / "dyn_on.json"
            dyn_on.write_text(
                json.dumps({"BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True, "persistent_drain_window_s": 0.02}),
                encoding="utf-8",
            )
            dyn_off = td_path / "dyn_off.json"
            dyn_off.write_text(json.dumps({"BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": False}), encoding="utf-8")
            srv._PERSISTENT_POOL.shutdown()

            def _run_through_handler(cfg_path: Path) -> tuple[object, list[tuple[int, object]], list[object], list[object], list[object]]:
                bind_reaper_calls: list[tuple[int, object]] = []
                bind_cancel_calls: list[object] = []
                release_slot_runs: list[object] = []
                capture_calls: list[object] = []
                fake_job = SimpleNamespace(pgid=0, cancelled=threading.Event())

                class _FakeHygiene:
                    def acquire(self, *_a: object, **_kw: object) -> object:
                        return SimpleNamespace(admitted=True, ticket_id="t-1")

                    def bind_reaper(self, pgid: int, fn: object) -> None:
                        bind_reaper_calls.append((pgid, fn))

                    def release(self, *_a: object, **_kw: object) -> None:
                        return None

                class _FakeP12:
                    def release_slot_after_run(self, release_fn: object, run: object, _tid: str) -> bool:
                        release_slot_runs.append(run)
                        if callable(release_fn):
                            release_fn()
                        return True

                class _FakeRegistry:
                    def bind_cancel(self, _job: object, fn: object) -> None:
                        bind_cancel_calls.append(fn)

                handler = object.__new__(srv.Handler)
                handler._registry_job = fake_job
                handler._acquire_slot = lambda _ka: ""
                handler._execute = lambda run, *_a, **_kw: (
                    [None for _ in iter(lambda: run.q.get(timeout=5.0)[0], "done")]
                    and {"state": "done", "text": "ok", "rc": 0}
                ) or {"state": "done", "text": "ok", "rc": 0}
                handler._attach_resolved_usage = lambda *_a, **_kw: None
                handler._log_done = lambda *_a, **_kw: None

                ctx = {
                    "model": "gemini-4-neon",
                    "effort": "high",
                    "effort_source": "request",
                    "prompt": "hi-p12",
                    "cwd": str(td_path),
                    "tag": "r-p12",
                    "tools_count": 0,
                    "model_len": 1,
                    "chat_id": "p12-chat",
                }
                with (
                    mock.patch.object(srv, "DYNAMIC_CONFIG_PATH", cfg_path),
                    mock.patch.object(srv, "_launcher", return_value=str(launcher)),
                    mock.patch.object(srv, "_launch_env", return_value=os.environ.copy()),
                    mock.patch.object(srv, "_hygiene_rt", return_value=_FakeHygiene()),
                    mock.patch.object(srv, "_p12_seam", return_value=_FakeP12()),
                    mock.patch.object(srv, "_JOB_REGISTRY", _FakeRegistry()),
                    mock.patch.object(srv, "capture_run_identity", side_effect=lambda r: capture_calls.append(r)),
                    mock.patch.object(srv._slots, "release"),
                ):
                    out = srv.Handler._run_once_impl(handler, ctx, lambda _t: None, lambda _e: None, lambda _r: None, lambda: None)
                self.assertEqual(out["state"], "done")
                return (fake_job, bind_reaper_calls, bind_cancel_calls, release_slot_runs, capture_calls)

            try:
                job_p, reapers_p, cancels_p, p12_runs_p, cap_p = _run_through_handler(dyn_on)
                self.assertEqual(job_p.pgid, 0)
                self.assertEqual(reapers_p, [])
                self.assertEqual(cap_p, [])
                self.assertEqual(len(cancels_p), 2)
                self.assertTrue(callable(cancels_p[0]) and getattr(cancels_p[0], "__name__", "") == "cancel_persistent")
                self.assertIsNone(cancels_p[1])
                self.assertEqual(p12_runs_p, [None])
                self.assertEqual(srv._PERSISTENT_POOL.health_snapshot(enabled=True)["slots"], 1)

                # Ephemeral cold run MUST still register job.pgid, bind_reaper, capture_run_identity, and p12 release!
                job_c, reapers_c, cancels_c, p12_runs_c, cap_c = _run_through_handler(dyn_off)
                self.assertGreater(job_c.pgid, 0)
                self.assertEqual(len(reapers_c), 2)
                self.assertEqual(reapers_c[0][0], job_c.pgid)
                self.assertTrue(callable(reapers_c[0][1]))
                self.assertEqual(reapers_c[1], (job_c.pgid, None))
                self.assertEqual(len(cap_c), 1)
                self.assertEqual(len(p12_runs_c), 1)
                self.assertIsNotNone(p12_runs_c[0])
                self.assertEqual(len(cancels_c), 2)
                self.assertIsNone(cancels_c[1])
            finally:
                srv._PERSISTENT_POOL.shutdown()


if __name__ == "__main__":
    unittest.main()
