"""Тесты fresh-rotate persistent-пула agy-bridge: конфиг, ротация, standby, B-03."""

# pyright: basic, reportAny=false, reportExplicitAny=false
# pyright: reportPrivateUsage=false, reportUnknownMemberType=false
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

_R = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_R), str(_R / "bridges" / "agy-bridge")]


def _mod(name: str) -> Any:
    """Импорт модуля после настройки sys.path без reportMissingImports."""
    return cast(Any, importlib.import_module(name))


_PFR = _mod("agy_runtime.persistent_fresh_rotate")
_PWC = _mod("agy_runtime.persistent_worker_config")
_FAKE = (
    "import json, os, sys\nfor n, _ in enumerate(sys.stdin, 1):\n"
    "    p = os.getpid()\n    ev = {'type': 'tool_use', 'step_index': n, "
    "'pid': p, 'tool_name': f'tool-{p}', 'conversation_id': f'cid-{p}'}\n"
    "    print(json.dumps(ev), flush=True)\n"
)
_PROMPT = b"go\n"
_BASELINE = (
    "enabled slots busy idle hits misses fallbacks "
    "teardowns_error teardowns_cancel desync_evictions fresh_rotations"
).split()


def _clean_env(extra: dict[str, str]) -> dict[str, str]:
    """Копия os.environ без persistent/standby-флагов плюс заданные ключи."""
    skip = ("PERSISTENT_", "STANDBY_")
    base = {k: v for k, v in os.environ.items() if not any(s in k for s in skip)}
    return {**base, **extra}


def _pid(lease: Any) -> int:
    """PID процесса за арендой."""
    return int(lease.handle.proc.pid)


def _wait(pred: Any, timeout: float = 5.0) -> bool:
    """Детерминированное ожидание условия с верхней границей."""
    end = time.monotonic() + timeout
    while time.monotonic() < end and not pred():
        time.sleep(0.01)
    return bool(pred())


def _lease(turns: int = 0, standby: bool = False, slot: str = "s1") -> Any:
    """Подмена PersistentLease с полями для guard и standby."""
    pid = 100 + int("".join(c for c in slot if c.isdigit()) or "0")
    ns = SimpleNamespace(turns_before=turns, slot_id=slot, chat_key="chat-A")
    ns.reused = ns.standby_claimed = standby
    ns.handle = SimpleNamespace(generation=int(standby), proc=SimpleNamespace(pid=pid))
    ns.prefetched_init_line = "INIT" if standby else ""
    return ns


class _StubPool:
    """Подменённый пул со скриптованной выдачей аренд и журналом release."""

    def __init__(self, seq: list[Any], exc: Exception | None = None) -> None:
        self.seq, self.exc = list(seq), exc
        self.acquired = self.fresh_rotations = 0
        self.released: list[tuple[Any, Any]] = []
        self.aliases = {"chat-A"}

    def acquire(self, req: object, cfg: object) -> Any:
        self.acquired += 1
        return self.seq.pop(0)

    def release(self, lease: Any, params: Any) -> None:
        self.released.append((lease, params))
        self.aliases.discard(lease.chat_key)
        self.fresh_rotations += int(bool(getattr(params, "rotate", False)))
        if self.exc is not None:
            raise self.exc


class _Base(unittest.TestCase):
    """Общая оснастка: fake-agy, реальный пул и аренда ходов."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        script = self.tmp / "fake_agy.py"
        script.write_text(_FAKE, encoding="utf-8")
        self.argv = [sys.executable, "-I", str(script)]
        self.cfg = _PWC.PersistentWorkerSettings(True, 4, 5.0)
        self.pool = self.new_pool()

    def new_pool(self) -> Any:
        pool = _mod("agy_runtime.persistent_worker_adapter").AgyPersistentWorkerPool()
        self.addCleanup(pool.shutdown)
        return pool

    def req(self, cid: str = "", chat: str = "chat-A") -> Any:
        args = (chat, cid, "m", "e", str(self.tmp), "d", "standard")
        return _PWC.PersistentAcquireRequest(*args, self.argv.copy, dict(os.environ))

    def read_event(self, lease: Any) -> dict[str, Any]:
        kind, tagged = lease.handle.read_stdout_line_outcome(timeout_s=10.0)
        assert kind == _mod("core.stdio_resident.process_io").LINE
        assert tagged is not None
        return cast(dict[str, Any], json.loads(tagged.line))

    def turn(self, cid: str = "", chat: str = "chat-A") -> tuple[Any, dict[str, Any]]:
        """Один полный ход: аренда, промпт, чтение события и release."""
        lease = _PFR.acquire_with_fresh_guard(self.pool, self.req(cid, chat), self.cfg)
        assert lease is not None
        lease.handle.write(_PROMPT)
        ev = self.read_event(lease)
        rel = _PWC.PersistentReleaseParams(True, cid=ev["conversation_id"])
        self.pool.release(lease, rel)
        return lease, ev

    def snap(self) -> dict[str, object]:
        return cast(dict[str, object], self.pool.health_snapshot(enabled=True))


class FreshRotateTests(_Base):
    """Сквозные, конкурентные, standby, kill-switch и B-03 тесты."""

    def test_kill_switch_priority(self) -> None:
        ck = "BRIDGE_AGY_PERSISTENT_FRESH_ROTATE_ENABLED"
        ek = "AGY_BRIDGE_PERSISTENT_FRESH_ROTATE_ENABLED"
        rows = [({}, {}, False), ({ck: True}, {}, True), ({ck: True}, {ek: "0"}, False)]
        for idx, (cfg_j, env, want) in enumerate(rows):
            p = self.tmp / f"c{idx}" / "dynamic_config.json"
            p.parent.mkdir()
            p.write_text(json.dumps(cfg_j), encoding="utf-8")
            with mock.patch.dict(os.environ, _clean_env(env), clear=True):
                cfg = _PWC.persistent_worker_settings(config_path=p)
                self.assertEqual(cfg.fresh_rotate_enabled, want)

    def test_cid_loss_shadow_rotate_and_rollback(self) -> None:
        for reason in ("SLOT_EXPIRED", "live_parser_error", "invalidate"):
            with self.subTest(reason=reason):
                self.pool = self.new_pool()
                self.cfg = replace(self.cfg, fresh_rotate_enabled=False)
                l1, e1 = self.turn()
                self.assertEqual((l1.turns_before, l1.reused), (0, False))
                self.assertEqual(e1["conversation_id"], f"cid-{_pid(l1)}")
                l2, _ = self.turn(e1["conversation_id"])
                self.assertEqual((_pid(l2), l2.turns_before), (_pid(l1), 1))
                l3, _ = self.turn()  # cid потерян в shadow-режиме
                self.assertEqual((_pid(l3), l3.turns_before), (_pid(l1), 2))
                self.assertEqual(self.snap()["fresh_rotations"], 0)
                self.cfg = replace(self.cfg, fresh_rotate_enabled=True)
                l4, e4 = self.turn()
                self.assertNotEqual(_pid(l4), _pid(l1))
                self.assertEqual((l4.turns_before, l4.reused), (0, False))
                self.assertTrue(_wait(lambda: not l3.handle.is_alive()))
                s = self.snap()
                self.assertEqual((s["fresh_rotations"], s["teardowns_cancel"]), (1, 0))
                self.assertTrue(s["teardowns_error"] == 0 and set(_BASELINE) <= set(s))
                self.assertEqual(e4["conversation_id"], f"cid-{_pid(l4)}")
                self.cfg = replace(self.cfg, fresh_rotate_enabled=False)
                l5, _ = self.turn()
                self.assertEqual(_pid(l5), _pid(l4))
                self.assertEqual(self.snap()["fresh_rotations"], 1)

    def test_history_diverged_supersede_with_single_slot(self) -> None:
        self.cfg = replace(self.cfg, max_slots=1, fresh_rotate_enabled=True)
        l1, e1 = self.turn()
        l2, _ = self.turn(e1["conversation_id"])
        self.assertEqual(_pid(l2), _pid(l1))
        l3, _ = self.turn()  # история разошлась, max_slots=1 (F-004)
        s = self.snap()
        self.assertTrue(_pid(l3) != _pid(l1) and l3.turns_before == 0)
        self.assertEqual((s["fresh_rotations"], s["fallbacks"]), (1, 0))

    def test_repeated_release_with_stale_lease_id_is_noop(self) -> None:
        old, ev = self.turn()
        cid = ev["conversation_id"]
        new = _PFR.acquire_with_fresh_guard(self.pool, self.req(cid), self.cfg)
        assert new is not None and new is not old
        self.pool.release(old, _PWC.PersistentReleaseParams(False, True, rotate=True))
        self.assertTrue(new.handle.is_alive() and self.snap()["fresh_rotations"] == 0)
        self.pool.release(new, _PWC.PersistentReleaseParams(True, False, cid))

    def test_concurrent_threads_on_stale_slot_rotate_once(self) -> None:
        self.cfg = replace(self.cfg, fresh_rotate_enabled=True)
        _, e1 = self.turn()
        self.turn(e1["conversation_id"])
        barrier, out, errs = threading.Barrier(2), [], []

        def worker() -> None:
            try:
                barrier.wait(5.0)
                lease = _PFR.acquire_with_fresh_guard(self.pool, self.req(), self.cfg)
                out.append(None if lease is None else lease.turns_before)
                if lease is not None:
                    self.pool.release(lease, _PWC.PersistentReleaseParams(False, True))
            except Exception as exc:  # noqa: BLE001
                errs.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30.0)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertTrue(all(v in (0, None) for v in out) and 0 in out)
        self.assertEqual((errs, len(out), self.snap()["fresh_rotations"]), ([], 2, 1))

    def _guard(self, pool: _StubPool, standby: bool = False) -> Any:
        """Вызов acquire_with_fresh_guard на подменённом пуле."""
        cfg = replace(self.cfg, fresh_rotate_enabled=True, standby_enabled=standby)
        return _PFR.acquire_with_fresh_guard(cast(Any, pool), self.req(), cfg)

    def test_cold_fallback_paths(self) -> None:
        cases = (
            ("stale_reacquire", [_lease(5), _lease(5)], None, 2, 2),
            ("reacquire_none", [_lease(5), None], None, 2, 1),
            ("release_error", [_lease(5)], RuntimeError("boom"), 1, 1),
        )
        for reason, seq, exc, acq, rel in cases:
            with self.subTest(reason=reason), self.assertLogs(level="WARNING") as cm:
                pool = _StubPool(seq, exc)
                self.assertIsNone(self._guard(pool))
                self.assertEqual((pool.acquired, len(pool.released)), (acq, rel))
                msg = f"action=cold_fallback reason={reason}"
                self.assertTrue(any(msg in m for m in cm.output), cm.output)
                self.assertTrue(all(p.rotate for _, p in pool.released))

    def test_standby_turn0_is_not_evicted(self) -> None:
        lease = _lease(0, True, "sb")
        pool = _StubPool([lease])
        got = self._guard(pool, standby=True)
        self.assertTrue(got is lease and pool.acquired == 1 and not pool.released)
        self.assertEqual((pool.fresh_rotations, got.prefetched_init_line), (0, "INIT"))

    def test_standby_alias_evicted_and_reclaimed_after_used_turn(self) -> None:
        used, fresh = _lease(1, True, "sb1"), _lease(0, True, "sb2")
        pool = _StubPool([used, fresh])
        got = self._guard(pool, standby=True)
        self.assertTrue(got is fresh and [ls for ls, _ in pool.released] == [used])
        self.assertTrue(pool.released[0][1].rotate and "chat-A" not in pool.aliases)
        self.assertTrue(_pid(got) != _pid(used) and got.standby_claimed)
        self.assertEqual((pool.fresh_rotations, got.turns_before), (1, 0))

    def _run_turn(self, cp: Path, cid: str) -> tuple[Any, dict[str, Any], Any]:
        run = SimpleNamespace(run_cid=cid)
        a = (self.pool, cp, list(self.argv), str(self.tmp), dict(os.environ))
        b = ("m", "e", "cli", False, "", None, "chat-A")
        ctx = _PWC.RunSpawnContext(*a, *b, lambda: self.fail("cold"), lambda: None)
        prh = _mod("agy_runtime.persistent_run_hooks")
        prh.start_run_process(run, ctx)
        lease = run._persistent_lease
        lease.handle.write(_PROMPT)
        ev = self.read_event(lease)
        coll = _mod("agy_runtime.midstream_resilience").AgyToolTraceCollector()
        coll.record_cli_event(ev)
        run._persistent_resolved_cid = ev["conversation_id"]
        prh.release_run_persistent(run, self.pool, cp, success=True, cancel=False)
        return lease, ev, coll

    def test_run_turn31_cold_fresh_rotate_zero_replay_and_b03_collector(self) -> None:
        cp = self.tmp / "dynamic_config.json"
        cp.write_text(
            '{"BRIDGE_AGY_PERSISTENT_WORKER_ENABLED": true, '
            '"BRIDGE_AGY_PERSISTENT_FRESH_ROTATE_ENABLED": true}',
            encoding="utf-8",
        )
        with mock.patch.dict(os.environ, _clean_env({}), clear=True):
            old, ev1, _ = self._run_turn(cp, "")
            new, ev2, coll = self._run_turn(cp, "")
        self.assertNotEqual(_pid(new), _pid(old))
        self.assertEqual(ev2["conversation_id"], f"cid-{_pid(new)}")
        self.assertNotEqual(ev2["conversation_id"], ev1["conversation_id"])
        self.assertEqual((new.turns_before, ev2["step_index"]), (0, 1))
        self.assertEqual((ev2["pid"], self.snap()["fresh_rotations"]), (_pid(new), 1))
        self.assertTrue(_wait(lambda: not old.handle.is_alive()))
        self.assertTrue(coll.ledger.trace_complete)
