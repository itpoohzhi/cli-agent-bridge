"""L2-тесты AD-005 (часть 2): affinity persistent-слотов по cloud mode (AGY_DIRECT).

Реальный проход через persistent_run_hooks.start_run_process и живой
AgyPersistentWorkerPool: смена AGY_DIRECT обязана менять env_digest и слот,
эквивалентные georouter-значения ("", "0", отсутствие ключа) — reuse слота.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
AGY_BRIDGE_DIR = REPO_ROOT / "bridges" / "agy-bridge"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(AGY_BRIDGE_DIR) not in sys.path:
    sys.path.append(str(AGY_BRIDGE_DIR))

from agy_runtime.persistent_run_hooks import (  # noqa: E402
    RunSpawnContext,
    start_run_process,
)
from agy_runtime.persistent_worker_adapter import AgyPersistentWorkerPool  # noqa: E402
from agy_runtime.persistent_worker_config import (  # noqa: E402
    PersistentAcquireRequest,
    PersistentLease,
    PersistentReleaseParams,
    PersistentWorkerSettings,
    compute_env_digest,
    persistent_worker_settings,
)

FAKE_AGY_SCRIPT = r"""#!/usr/bin/env python3
import json
import os
import sys

cid = os.environ.get("FAKE_AGY_CID", "cid-affinity-001")
pid = os.getpid()
direct = os.environ.get("AGY_DIRECT", "")
turn = 0
for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    turn += 1
    msg = json.loads(raw)
    content = (msg.get("message") or {}).get("content")
    text = str(content[0].get("text") or "") if isinstance(content, list) and content else str(content or "")
    if turn == 1:
        print(json.dumps({"event": "init", "conversation_id": cid}), flush=True)
    reply = f"pid={pid} turn={turn} direct={direct} echo={text}"
    print(json.dumps({"event": "result", "conversation_id": cid, "result": {
        "conversation_id": cid, "status": "SUCCESS", "response": reply, "num_turns": turn,
    }}), flush=True)
"""


class _RecordingPool:
    """Прокси над реальным пулом: фиксирует каждый PersistentAcquireRequest."""

    def __init__(self) -> None:
        self.inner = AgyPersistentWorkerPool()
        self.requests: list[PersistentAcquireRequest] = []

    def acquire(
        self, req: PersistentAcquireRequest, cfg: PersistentWorkerSettings
    ) -> PersistentLease | None:
        self.requests.append(req)
        return self.inner.acquire(req, cfg)

    def reconcile_disabled(self) -> None:
        self.inner.reconcile_disabled()

    def release(self, lease: PersistentLease, params: PersistentReleaseParams) -> None:
        self.inner.release(lease, params)

    def health_snapshot(self, *, enabled: bool) -> dict[str, object]:
        return self.inner.health_snapshot(enabled=enabled)

    def shutdown(self, timeout_s: float | None = None) -> None:
        self.inner.shutdown(timeout_s)


class TestCloudModeAffinity(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.launcher = self.tmp_path / "fake-agy.py"
        self.launcher.write_text(FAKE_AGY_SCRIPT, encoding="utf-8")
        self.launcher.chmod(self.launcher.stat().st_mode | stat.S_IEXEC)
        self.cfg_path = self.tmp_path / "dynamic_config.json"
        self.cfg_path.write_text(
            json.dumps(
                {
                    "BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": True,
                    "persistent_worker_max_slots": 4,
                    "persistent_worker_lease_wait_s": 0.2,
                    "persistent_worker_idle_timeout_s": 60.0,
                    "persistent_worker_ttl_s": 300.0,
                    "persistent_worker_max_rss_mb": 512,
                    "persistent_worker_max_turns": 8,
                    "persistent_worker_pump_tick_s": 0.05,
                    "persistent_drain_window_s": 0.02,
                }
            ),
            encoding="utf-8",
        )
        env_patch = mock.patch.dict(os.environ, {}, clear=False)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        for k in list(os.environ):
            if k.startswith(("AGY_BRIDGE_", "BRIDGE_AGY_")):
                os.environ.pop(k, None)
        self.cfg = persistent_worker_settings(config_path=self.cfg_path)
        self.pool = _RecordingPool()
        self.addCleanup(self.pool.shutdown)

    @staticmethod
    def _cold_forbidden(env: Mapping[str, str]) -> subprocess.Popen[bytes]:
        raise AssertionError(
            f"cold fallback unexpected (env AGY_DIRECT={env.get('AGY_DIRECT')!r})"
        )

    def _start(
        self, extra_env: dict[str, str], chat_key: str, cid: str = ""
    ) -> SimpleNamespace:
        env = os.environ.copy()
        env.pop("AGY_DIRECT", None)
        env.update(extra_env)
        run = SimpleNamespace(run_cid=cid)
        ctx = RunSpawnContext(
            pool=self.pool,
            config_path=self.cfg_path,
            cmd=[sys.executable, str(self.launcher)],
            work_dir=str(self.tmp_path),
            launch_env=env,
            model="gemini-4-neon",
            effort="high",
            cli_mode="plan",
            zero_canon=True,
            settings_arg="",
            add_dir=None,
            chat_key=chat_key,
            spawn_cold=lambda: self._cold_forbidden(env),
            on_cold_fail=lambda: None,
            resume_base_idx=1 if cid else 0,
        )
        start_run_process(run, ctx)
        self.assertIsNotNone(run._persistent_lease)
        return run

    def _turn(self, run: SimpleNamespace, text: str) -> tuple[int, int, str, str]:
        lease = run._persistent_lease
        payload = json.dumps(
            {
                "event": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": text}],
                },
            }
        )
        lease.handle.write((payload + "\n").encode("utf-8"))
        cid, resp, turns = "", "", 0
        while True:
            kind, tagged = lease.handle.read_stdout_line_outcome(timeout_s=5.0)
            self.assertEqual(kind, "line")
            assert tagged is not None
            ev = json.loads(tagged.line)
            if ev.get("event") == "init":
                cid = str(ev.get("conversation_id", ""))
            elif ev.get("event") == "result":
                res = ev["result"]
                cid = str(res.get("conversation_id", cid))
                resp = str(res.get("response", ""))
                turns = int(res.get("num_turns", 0))
                break
        return lease.handle.pid, turns, cid, resp

    def _release(self, run: SimpleNamespace, cid: str) -> None:
        self.pool.release(
            run._persistent_lease,
            PersistentReleaseParams(
                success=True,
                cancel=False,
                cid=cid,
                still_enabled=True,
                max_slots=self.cfg.max_slots,
            ),
        )

    def _assert_digest_formula(self, req: PersistentAcquireRequest) -> None:
        """digest запроса обязан включать net-сегмент из launch_env (AD-005)."""
        expected = compute_env_digest(
            "plan", True, str(req.env.get("HOME") or ""), "", launch_env=req.env
        )
        self.assertEqual(req.env_digest, expected)

    def test_direct_vs_georouter_different_digest_and_slot(self) -> None:
        run1 = self._start({"AGY_DIRECT": "1"}, "aff-chat")
        lease1 = run1._persistent_lease
        self.assertFalse(lease1.reused)
        pid1, t1, cid1, resp1 = self._turn(run1, "hello-direct")
        self.assertEqual(t1, 1)
        self.assertIn("direct=1", resp1)
        self._release(run1, cid1)
        req1 = self.pool.requests[-1]
        self._assert_digest_formula(req1)

        # Тот же chat/cid, но AGY_DIRECT=0 -> другой digest и НОВЫЙ слот (без reuse).
        run2 = self._start({"AGY_DIRECT": "0"}, "aff-chat", cid=cid1)
        lease2 = run2._persistent_lease
        req2 = self.pool.requests[-1]
        self._assert_digest_formula(req2)
        self.assertNotEqual(req1.env_digest, req2.env_digest)
        self.assertFalse(lease2.reused)
        self.assertNotEqual(lease2.slot_id, lease1.slot_id)
        pid2, t2, _, resp2 = self._turn(run2, "hello-geo")
        self.assertNotEqual(pid2, pid1)
        self.assertEqual(t2, 1)
        self.assertIn("direct=0", resp2)
        self._release(run2, cid1)
        self.assertEqual(self.pool.health_snapshot(enabled=True)["slots"], 2)

    def test_georouter_empty_zero_absent_share_digest_and_reuse(self) -> None:
        run1 = self._start({"AGY_DIRECT": ""}, "geo-chat")
        pid1, t1, cid1, _ = self._turn(run1, "g1")
        self.assertEqual(t1, 1)
        self._release(run1, cid1)
        d_empty = self.pool.requests[-1].env_digest
        self._assert_digest_formula(self.pool.requests[-1])

        run2 = self._start({"AGY_DIRECT": "0"}, "geo-chat", cid=cid1)
        lease2 = run2._persistent_lease
        self.assertEqual(self.pool.requests[-1].env_digest, d_empty)
        self.assertTrue(lease2.reused)
        self.assertEqual(lease2.handle.pid, pid1)
        self.assertEqual(lease2.slot_id, run1._persistent_lease.slot_id)
        _, t2, _, _ = self._turn(run2, "g2")
        self.assertEqual(t2, 2)
        self._release(run2, cid1)

        run3 = self._start({}, "geo-chat", cid=cid1)
        lease3 = run3._persistent_lease
        self.assertEqual(self.pool.requests[-1].env_digest, d_empty)
        self.assertTrue(lease3.reused)
        self.assertEqual(lease3.handle.pid, pid1)
        _, t3, _, _ = self._turn(run3, "g3")
        self.assertEqual(t3, 3)
        self._release(run3, cid1)
        self.assertEqual(self.pool.health_snapshot(enabled=True)["slots"], 1)

    def test_flip_back_to_direct_reuses_original_direct_slot(self) -> None:
        run1 = self._start({"AGY_DIRECT": "1"}, "flip-chat")
        pid1, _, cid1, _ = self._turn(run1, "d1")
        self._release(run1, cid1)
        run2 = self._start({"AGY_DIRECT": "0"}, "flip-chat", cid=cid1)
        pid2, _, cid2, _ = self._turn(run2, "g1")
        self.assertNotEqual(pid2, pid1)
        self._release(run2, cid2)

        run3 = self._start({"AGY_DIRECT": "1"}, "flip-chat", cid=cid1)
        lease3 = run3._persistent_lease
        self.assertTrue(lease3.reused)
        self.assertEqual(lease3.handle.pid, pid1)
        self.assertEqual(lease3.slot_id, run1._persistent_lease.slot_id)
        _, t3, _, resp3 = self._turn(run3, "d2")
        self.assertEqual(t3, 2)
        self.assertIn("direct=1", resp3)
        self._release(run3, cid1)
        self.assertEqual(self.pool.health_snapshot(enabled=True)["slots"], 2)


if __name__ == "__main__":
    unittest.main()
