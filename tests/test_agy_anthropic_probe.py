import json
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import core.agy_anthropic_probe as probe_module
from core.agy_anthropic_probe import (
    AgyAnthropicProbe,
    ProbeConfig,
    ProbeSnapshot,
    default_agy_models_runner,
)

SONNET_MODELS = (
    "Fetching available models...\r"
    "claude-sonnet-5-5-low\n"
    "claude-sonnet-5-5-high\n"
    "claude-opus-5-5-high\n"
)
OLD_MODELS = "claude-sonnet-4-6\nclaude-opus-4-6-thinking\ngemini-3-pro\n"


class FakeClock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def _write_script(tmpdir: str, name: str, body: str, executable: bool = True) -> str:
    path = Path(tmpdir) / name
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(0o755 if executable else 0o644)
    return str(path)


class AgyAnthropicProbeTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.runner = mock.Mock(return_value=(0, SONNET_MODELS))
        self.probe = AgyAnthropicProbe(runner=self.runner, clock=self.clock)

    def test_positive_and_negative_cache_ttls(self):
        first = self.probe.probe("claude-sonnet-5-5")
        self.assertTrue(first.available)
        self.assertEqual(first.upstream_model, "claude-sonnet-5-5-high")
        self.assertAlmostEqual(first.expires_at - first.checked_at, 120.0)
        self.clock.advance(119.0)
        self.assertEqual(self.probe.probe("claude-sonnet-5-5"), first)
        self.assertEqual(self.runner.call_count, 1)
        self.clock.advance(2.0)
        self.assertTrue(self.probe.probe("claude-sonnet-5-5").available)
        self.assertEqual(self.runner.call_count, 2)
        self.runner.return_value = (0, OLD_MODELS)
        self.clock.advance(121.0)
        neg = self.probe.probe("claude-sonnet-5-5")
        self.assertFalse(neg.available)
        self.assertAlmostEqual(neg.expires_at - neg.checked_at, 30.0)
        self.clock.advance(29.0)
        self.assertEqual(self.probe.probe("claude-sonnet-5-5"), neg)

    def test_effort_cache_keys_and_xhigh_rejection(self):
        low = self.probe.probe("claude-sonnet-5-5", requested_effort="low")
        high = self.probe.probe("claude-sonnet-5-5", requested_effort="high")
        self.assertEqual(low.upstream_model, "claude-sonnet-5-5-low")
        self.assertEqual(high.upstream_model, "claude-sonnet-5-5-high")
        self.assertEqual(self.runner.call_count, 2)
        bad = self.probe.probe("claude-sonnet-5-5", requested_effort="xhigh")
        self.assertFalse(bad.available)
        self.assertEqual(bad.reason, "unsupported_reasoning_effort")
        self.assertEqual(self.runner.call_count, 2)

    def test_singleflight_and_cross_family_wakeup_safety(self):
        sonnet_entered, release_sonnet = threading.Event(), threading.Event()
        calls = {"sonnet": 0, "opus": 0}
        results: dict[str, ProbeSnapshot] = {}

        def runner(timeout_s, max_output_bytes):
            del timeout_s, max_output_bytes
            if not sonnet_entered.is_set():
                calls["sonnet"] += 1
                sonnet_entered.set()
                release_sonnet.wait(timeout=2.0)
                return 0, "claude-sonnet-5-5-high\n"
            calls["opus"] += 1
            return 0, "claude-opus-5-5-high\n"

        probe = AgyAnthropicProbe(runner=runner, clock=self.clock)
        probe._snapshots[("claude-sonnet-5-5", "")] = ProbeSnapshot(
            "claude-sonnet-5-5", False, None, "stale", 1.0, 2.0, ""
        )
        t1 = threading.Thread(target=lambda: results.setdefault("s1", probe.probe("claude-sonnet-5-5")))
        t2 = threading.Thread(target=lambda: results.setdefault("s2", probe.probe("claude-sonnet-5-5")))
        t1.start()
        self.assertTrue(sonnet_entered.wait(timeout=2.0))
        t2.start()
        time.sleep(0.05)
        self.assertTrue(probe.probe("claude-opus-5-5").available)
        time.sleep(0.05)
        self.assertNotIn("s2", results)
        release_sonnet.set()
        t1.join(timeout=2.0)
        t2.join(timeout=2.0)
        self.assertEqual(calls["sonnet"], 1)
        self.assertTrue(results["s1"].available)
        self.assertEqual(results["s2"], results["s1"])

    def test_unexpected_exceptions_release_inflight_and_wake_waiters(self):
        excs = (TypeError("t"), KeyError("k"), PermissionError("p"), UnicodeError("u"), RuntimeError("r"))
        for exc in excs:
            with self.subTest(exc=type(exc).__name__):
                entered, release = threading.Event(), threading.Event()
                state = {"n": 0}

                def flaky(timeout_s, max_output_bytes, _exc=exc):
                    del timeout_s, max_output_bytes
                    state["n"] += 1
                    if state["n"] == 1:
                        entered.set()
                        release.wait(timeout=2.0)
                        raise _exc
                    return 0, SONNET_MODELS

                probe = AgyAnthropicProbe(runner=flaky, clock=self.clock)
                out: list[ProbeSnapshot] = []
                t1 = threading.Thread(target=lambda: out.append(probe.probe("claude-sonnet-5-5")))
                t2 = threading.Thread(target=lambda: out.append(probe.probe("claude-sonnet-5-5")))
                t1.start()
                self.assertTrue(entered.wait(timeout=2.0))
                t2.start()
                time.sleep(0.03)
                release.set()
                t1.join(timeout=2.0)
                t2.join(timeout=2.0)
                self.assertFalse(t1.is_alive() or t2.is_alive())
                self.assertEqual(len(out), 2)
                self.assertTrue(all(not s.available and s.reason == "probe_failed" for s in out))
                self.clock.advance(31.0)
                self.assertTrue(probe.probe("claude-sonnet-5-5").available)

    def test_wait_timeout_returns_fail_closed_without_deadlock(self):
        entered, release = threading.Event(), threading.Event()

        def blocked(timeout_s, max_output_bytes):
            del timeout_s, max_output_bytes
            entered.set()
            release.wait(timeout=2.0)
            return 0, SONNET_MODELS

        probe = AgyAnthropicProbe(runner=blocked, clock=self.clock, config=ProbeConfig(wait_timeout_s=0.05))
        t1 = threading.Thread(target=lambda: probe.probe("claude-sonnet-5-5"))
        t1.start()
        self.assertTrue(entered.wait(timeout=2.0))
        try:
            waited = probe.probe("claude-sonnet-5-5")
            self.assertFalse(waited.available)
            self.assertEqual(waited.reason, "probe_wait_timeout")
        finally:
            release.set()
            t1.join(timeout=2.0)

    def test_force_refresh_cooldown_and_circuit_breaker(self):
        runner = mock.Mock(side_effect=[RuntimeError("1"), RuntimeError("2"), (0, SONNET_MODELS)])
        probe = AgyAnthropicProbe(runner=runner, clock=self.clock)
        self.assertEqual(probe.probe("claude-sonnet-5-5").reason, "probe_failed")
        self.clock.advance(31.0)
        self.assertEqual(probe.probe("claude-sonnet-5-5").reason, "probe_failed")
        self.assertEqual(probe.probe("claude-sonnet-5-5").reason, "circuit_open")
        self.clock.advance(31.0)
        self.assertTrue(probe.probe("claude-sonnet-5-5").available)
        self.probe.probe("claude-sonnet-5-5")
        self.clock.advance(5.1)
        self.probe.probe("claude-sonnet-5-5", force_refresh=True)
        self.probe.probe("claude-sonnet-5-5", force_refresh=True)
        self.assertEqual(self.runner.call_count, 2)


class StreamingRunnerSafetyTests(unittest.TestCase):
    def test_streaming_output_cap_aborts_before_buffering_2mib(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = _write_script(
                tmpdir,
                "flood_agy.py",
                "import sys\nchunk = b'a' * 16384\n"
                "for _ in range(256):\n    sys.stdout.buffer.write(chunk)\n"
                "    sys.stdout.buffer.flush()\n",
            )
            with mock.patch.dict(os.environ, {"AGY_BIN": script}), self.assertRaises(
                probe_module._OutputTooLarge
            ):
                default_agy_models_runner(timeout_s=3.0, max_output_bytes=65536)

    def test_timeout_kills_entire_process_group_including_child(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "child.pid"
            script = _write_script(
                tmpdir,
                "spawn_child.py",
                f"import subprocess, time\n"
                f"p = subprocess.Popen(['{sys.executable}', '-c', 'import time; time.sleep(30)'])\n"
                f"open({str(pid_file)!r}, 'w').write(str(p.pid))\n"
                f"time.sleep(30)\n",
            )
            with mock.patch.dict(os.environ, {"AGY_BIN": script}):
                with self.assertRaises(TimeoutError):
                    default_agy_models_runner(timeout_s=0.35, max_output_bytes=65536)
            self.assertTrue(pid_file.exists())
            child_pid = int(pid_file.read_text(encoding="utf-8").strip())
            time.sleep(0.1)
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)

    def test_invalid_agy_bin_rejected_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            non_exec = _write_script(tmpdir, "noexec.py", "pass\n", executable=False)
            bad_bins = ("agy", "/nonexistent/path/agy", tmpdir, non_exec, "/bin/echo;id", "/bin/$(id)")
            for bad in bad_bins:
                with self.subTest(bad=bad), mock.patch.dict(os.environ, {"AGY_BIN": bad}):
                    snap = AgyAnthropicProbe().probe("claude-sonnet-5-5")
                    self.assertFalse(snap.available)
                    self.assertEqual(snap.reason, "probe_failed")

    def test_kill_pg_handles_permission_and_lookup_errors(self):
        fake_proc = mock.Mock(pid=999999)
        fake_proc.poll.return_value = 0
        with mock.patch("os.getpgid", side_effect=PermissionError("denied")):
            probe_module._kill_pg(fake_proc, grace_s=0.01)
        with mock.patch("os.getpgid", return_value=999999), mock.patch(
            "os.killpg", side_effect=PermissionError("denied")
        ):
            probe_module._kill_pg(fake_proc, grace_s=0.01)


class ProbeCliTests(unittest.TestCase):
    def test_cli_flag_parity(self):
        for value in (None, "0", "false", "off", ""):
            with self.subTest(disabled=value), mock.patch.dict(os.environ, {}, clear=True):
                if value is not None:
                    os.environ["BRIDGE_AGY_ANTHROPIC_ENABLED"] = value
                output = StringIO()
                with mock.patch.object(probe_module, "AgyAnthropicProbe") as cls, redirect_stdout(output):
                    rc = probe_module.main(["--model", "claude-sonnet-5-5", "--json"])
                self.assertEqual(rc, 0)
                self.assertEqual(json.loads(output.getvalue())["reason"], "feature_flag_disabled")
                cls.assert_not_called()
        snapshot = ProbeSnapshot(
            "claude-sonnet-5-5", True, "claude-sonnet-5-5-high", "ok", 10.0, 130.0, "abc123"
        )
        for truthy in ("1", "true", "yes", "on", "ON"):
            with self.subTest(enabled=truthy):
                output = StringIO()
                with (
                    mock.patch.dict(os.environ, {"BRIDGE_AGY_ANTHROPIC_ENABLED": truthy}),
                    mock.patch.object(probe_module, "AgyAnthropicProbe") as cls,
                    redirect_stdout(output),
                ):
                    cls.return_value.probe.return_value = snapshot
                    rc = probe_module.main(["--model", "claude-sonnet-5-5", "--json"])
                self.assertEqual(rc, 0)
                cls.return_value.probe.assert_called_once_with("claude-sonnet-5-5")
                self.assertTrue(json.loads(output.getvalue())["available"])
