import os
import subprocess
import unittest
from typing import Any
from unittest.mock import patch

from core.watchdog import AdaptiveTimeoutController, ProcessWatchdog, WatchdogMetrics, parse_cputime


class _FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _StubWatchdog(ProcessWatchdog):
    def __init__(self, metrics: WatchdogMetrics) -> None:
        super().__init__(ps_timeout_s=2.0)
        self._metrics = metrics

    def seed(self, pgid: int, **_kwargs: Any) -> None:
        pass

    def sample(self, pgid: int, **_kwargs: Any) -> WatchdogMetrics:
        return self._metrics


class AdaptiveIdleWatchdogTests(unittest.TestCase):
    def test_parse_cputime_formats(self) -> None:
        self.assertAlmostEqual(parse_cputime("0:00.50"), 0.5)
        self.assertAlmostEqual(parse_cputime("01:30.25"), 90.25)
        self.assertAlmostEqual(parse_cputime("02:01:00.00"), 7260.0)
        self.assertAlmostEqual(parse_cputime("1-00:00:00"), 86400.0)

    def test_idle_300s_extended_by_cpu_or_descendant_progress(self) -> None:
        clock = _FakeClock(1000.0)
        active_metrics = WatchdogMetrics(
            pgid=4321,
            alive=True,
            descendant_pids=(4321, 4322),
            new_descendants=(4322,),
            cpu_time_s=2.5,
            cpu_delta_s=1.2,
            ps_degraded=False,
            sample_ts=1350.0,
        )
        wd = _StubWatchdog(active_metrics)
        ctrl = AdaptiveTimeoutController(
            idle_timeout_s=300.0,
            safety_cap_s=3600.0,
            watchdog=wd,
            watchdog_enabled=True,
            clock=clock,
        )
        ctrl.register_pgid(4321)

        # Advance 350s without stdout/protocol output, but child has CPU & descendant progress
        clock.advance(350.0)
        should_stop, reason, metrics = ctrl.check(4321)
        self.assertFalse(should_stop)
        self.assertEqual(reason, "")
        self.assertIsNotNone(metrics)
        self.assertTrue(metrics.has_progress)

        # Now child goes completely idle (no CPU delta, no new descendants) for another 305s
        wd._metrics = WatchdogMetrics(
            pgid=4321,
            alive=True,
            descendant_pids=(4321, 4322),
            new_descendants=(),
            cpu_time_s=2.5,
            cpu_delta_s=0.0,
            ps_degraded=False,
            sample_ts=1655.0,
        )
        clock.advance(305.0)
        should_stop, reason, _ = ctrl.check(4321)
        self.assertTrue(should_stop)
        self.assertEqual(reason, "idle_timeout")

    def test_ps_failure_fails_closed(self) -> None:
        live_pgid = os.getpgrp()
        wd = ProcessWatchdog(ps_timeout_s=0.05)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["ps"], timeout=0.05)):
            metrics = wd.sample(live_pgid)
        self.assertTrue(metrics.ps_degraded)
        self.assertFalse(metrics.has_progress)

        clock = _FakeClock(2000.0)
        ctrl = AdaptiveTimeoutController(
            idle_timeout_s=300.0,
            safety_cap_s=3600.0,
            watchdog=_StubWatchdog(metrics),
            watchdog_enabled=True,
            clock=clock,
        )
        ctrl.register_pgid(live_pgid)
        clock.advance(301.0)
        should_stop, reason, _ = ctrl.check(live_pgid)
        self.assertTrue(should_stop)
        self.assertEqual(reason, "idle_timeout")

    def test_hard_safety_cap_3600s_unconditional(self) -> None:
        clock = _FakeClock(5000.0)
        active_metrics = WatchdogMetrics(
            pgid=5555,
            alive=True,
            descendant_pids=(5555,),
            new_descendants=(5556,),
            cpu_time_s=100.0,
            cpu_delta_s=5.0,
            ps_degraded=False,
        )
        ctrl = AdaptiveTimeoutController(
            idle_timeout_s=300.0,
            safety_cap_s=3600.0,
            watchdog=_StubWatchdog(active_metrics),
            watchdog_enabled=True,
            clock=clock,
        )
        ctrl.register_pgid(5555)
        clock.advance(3601.0)
        ctrl.record_activity("stdout")
        should_stop, reason, _ = ctrl.check(5555)
        self.assertTrue(should_stop)
        self.assertEqual(reason, "absolute_cap")


if __name__ == "__main__":
    unittest.main()
