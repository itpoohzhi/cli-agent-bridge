import dataclasses
import os
import subprocess
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from core.cli_runtime_config import NonstreamConfig
from core.liveness_signals import (
    FLAG_SOFT_LIVENESS,
    LivenessSnapshot,
    LivenessWindow,
    WindowSpec,
    classify_cli_activity,
    classify_sse_data,
)
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

    def test_adaptive_controller_accepts_legacy_claude_p_kwargs(self):
        ctrl = AdaptiveTimeoutController(
            io_wait_cap_s=120.0,
            watchdog_interval_s=0.25,
        )
        self.assertEqual(ctrl.io_wait_cap_s, 120.0)
        self.assertEqual(ctrl.watchdog_interval_s, 0.25)

    def test_controller_accepts_bridge_timing_options(self) -> None:
        default = AdaptiveTimeoutController()
        self.assertIsNone(default.io_wait_cap_s)
        self.assertEqual(default.watchdog_interval_s, 5.0)

        logs: list[str] = []
        ctrl = AdaptiveTimeoutController(
            idle_timeout_s=300.0,
            safety_cap_s=3600.0,
            io_wait_cap_s=900.0,
            watchdog_interval_s=2.5,
            log_fn=logs.append,
        )
        self.assertEqual(ctrl.io_wait_cap_s, 900.0)
        self.assertEqual(ctrl.watchdog_interval_s, 2.5)
        self.assertTrue(any("ignored by 2-contour check()" in line for line in logs))

        clock = _FakeClock(100.0)
        ctrl = AdaptiveTimeoutController(
            idle_timeout_s=300.0,
            safety_cap_s=3600.0,
            io_wait_cap_s=10.0,
            watchdog_enabled=False,
            clock=clock,
        )
        clock.advance(8.0)
        ctrl.record_activity("protocol")
        clock.advance(8.0)  # 16s since start (> io_wait_cap_s), but only 8s idle
        self.assertFalse(ctrl.check()[0])
        clock.advance(301.0)
        self.assertEqual(ctrl.check(), (True, "idle_timeout", None))


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# ADR-0015 / AD-002 (VER-002): классификатор S/P/T, LivenessWindow, интеграция
# ---------------------------------------------------------------------------


def _delta(**fields: Any) -> str:
    import json

    return json.dumps({"choices": [{"index": 0, "delta": fields}]})


@pytest.mark.parametrize(
    "data",
    [
        None,
        "",
        "   ",
        "\n\t ",
        "ping",
        " ping ",
        "keepalive",
        "[DONE]",
        " [DONE] ",
        "{not json",
        "{}",
        "[]",
        "null",
        "42",
        '"text"',
        _delta(role="assistant"),
        _delta(),
        '{"usage": {"total_tokens": 3}}',
        '{"choices": [], "usage": {"total_tokens": 3}}',
        '{"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}',
        '{"choices": [{"index": 0, "finish_reason": "stop"}]}',
        '{"choices": "oops"}',
        '{"choices": [null, 5, "x"]}',
        _delta(content=""),
        _delta(reasoning_content=""),
        _delta(reasoning=""),
        _delta(reasoning_text=""),
        _delta(tool_calls=[]),
        _delta(content=None),
        _delta(function_call={}),
    ],
)
def test_classifier_transport_signals_are_t(data: str | None) -> None:
    kind, keys = classify_sse_data(data)
    assert kind == "T"
    assert keys == frozenset()


@pytest.mark.parametrize(
    "delta, expected",
    [
        ({"content": "x"}, {"content"}),
        ({"reasoning_content": "r"}, {"reasoning_content"}),
        ({"reasoning": "r"}, {"reasoning"}),
        ({"reasoning_text": "r"}, {"reasoning_text"}),
        ({"tool_calls": [{"index": 0}]}, {"tool_calls"}),
        ({"function_call": {"name": "f"}}, {"function_call"}),
        ({"content": "x", "reasoning_content": "r"}, {"content", "reasoning_content"}),
        ({"role": "assistant", "content": " "}, {"content"}),
    ],
)
def test_classifier_useful_delta_is_s(delta: dict[str, Any], expected: set[str]) -> None:
    kind, keys = classify_sse_data(_delta(**delta))
    assert kind == "S"
    assert keys == frozenset(expected)


def test_classifier_collects_keys_from_all_choices() -> None:
    import json

    chunk = json.dumps(
        {
            "choices": [
                {"index": 0, "delta": {"content": "a"}},
                {"index": 1, "delta": {"reasoning": "b"}},
                {"index": 2, "delta": {"content": ""}},
            ]
        }
    )
    assert classify_sse_data(chunk) == ("S", frozenset({"content", "reasoning"}))


def _spec(**overrides: Any) -> WindowSpec:
    base: dict[str, Any] = dict(
        first_timeout_s=20.0,
        idle_timeout_s=30.0,
        safety_cap_s=100.0,
        soft_budget_s=100.0,
        min_cpu_delta_s=0.05,
        process_progress=False,
    )
    base.update(overrides)
    return WindowSpec(**base)


def _window(
    clock: _FakeClock, soft: bool = True, **overrides: Any
) -> LivenessWindow:
    return LivenessWindow(_spec(**overrides), clock=clock, soft_enabled=lambda: soft)


def _at(clock: _FakeClock, t: float) -> None:
    clock.now = t


def test_passthrough_first_deadline_is_started_plus_first_timeout() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock)
    assert win.remaining_s() == pytest.approx(20.0)
    assert win.expired() == ""
    _at(clock, 1019.999)
    assert win.expired() == ""
    _at(clock, 1020.0)
    assert win.expired() == "first_progress_timeout"


def test_passthrough_t_and_p_never_shift_deadline() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock)
    _at(clock, 1010.0)
    win.record_signal("T")
    win.record_signal("P")
    win.record_process(cpu_delta_s=9.0, new_children=3, alive=True)
    assert win.remaining_s() == pytest.approx(10.0)
    snap = win.snapshot()
    assert snap.last_progress_kind == "none"
    assert snap.last_keepalive_age_s == 0.0
    assert snap.process_alive is None
    assert snap.soft_budget_used_s is None
    _at(clock, 1020.0)
    assert win.expired() == "first_progress_timeout"


def test_passthrough_first_s_switches_to_sliding_idle() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock)
    _at(clock, 1015.0)
    win.record_signal("S", frozenset({"content"}))
    assert win.remaining_s() == pytest.approx(30.0)  # deadline 1045
    _at(clock, 1040.0)
    assert win.expired() == ""
    win.record_signal("S", frozenset({"content"}))  # sliding: 1070
    assert win.remaining_s() == pytest.approx(30.0)
    _at(clock, 1060.0)
    win.record_signal("T")  # T не сдвигает
    assert win.remaining_s() == pytest.approx(10.0)
    _at(clock, 1069.9)
    assert win.expired() == ""
    _at(clock, 1070.0)
    assert win.expired() == "idle_timeout"


def test_safety_cap_is_absolute_and_has_priority() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock)
    for t in (1015.0, 1040.0, 1065.0, 1090.0):
        _at(clock, t)
        win.record_signal("S", frozenset({"content"}))
        assert win.expired() == ""
    # S на 1090 хотел бы дать 1120, но потолок = 1100
    assert win.remaining_s() == pytest.approx(10.0)
    assert win.snapshot().safety_cap_remaining_s == pytest.approx(10.0)
    _at(clock, 1099.9)
    assert win.expired() == ""
    _at(clock, 1100.0)
    assert win.expired() == "safety_cap"
    _at(clock, 1100.0 + 1e6)
    win.record_signal("S", frozenset({"content"}))
    assert win.expired() == "safety_cap"


def test_first_timeout_clamped_by_safety_cap() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock, first_timeout_s=500.0, safety_cap_s=50.0)
    assert win.remaining_s() == pytest.approx(50.0)
    _at(clock, 1050.0)
    assert win.expired() == "safety_cap"


def test_cli_soft_budget_exact_numbers_before_first_s() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock, process_progress=True, safety_cap_s=1000.0)  # first=20 idle=30 budget=100
    assert win.remaining_s() == pytest.approx(20.0)  # deadline 1020

    def p(t: float) -> LivenessSnapshot:
        _at(clock, t)
        win.record_signal("P")
        return win.snapshot()

    s = p(1010.0)  # dt=10 acc=10 ext=1010+min(30,90)=1040
    assert s.soft_budget_used_s == pytest.approx(10.0)
    assert win.remaining_s() == pytest.approx(30.0)
    assert s.last_progress_kind == "P"
    s = p(1030.0)  # dt=20 acc=30 ext=1060
    assert s.soft_budget_used_s == pytest.approx(30.0)
    assert win.remaining_s() == pytest.approx(30.0)
    s = p(1030.0)  # тот же timestamp -> dt=0
    assert s.soft_budget_used_s == pytest.approx(30.0)
    assert win.remaining_s() == pytest.approx(30.0)
    s = p(1031.0)  # частые P: начисляется ровно фактическое время (dt=1)
    assert s.soft_budget_used_s == pytest.approx(31.0)
    s = p(1031.5)
    assert s.soft_budget_used_s == pytest.approx(31.5)
    s = p(1070.0)  # dt=38.5 acc=70 rem=30 ext=1100
    assert s.soft_budget_used_s == pytest.approx(70.0)
    assert win.remaining_s() == pytest.approx(30.0)
    s = p(1090.0)  # dt=20 acc=90 rem=10 ext=1100 (дедлайн не растёт)
    assert s.soft_budget_used_s == pytest.approx(90.0)
    assert win.remaining_s() == pytest.approx(10.0)
    assert win.expired() == ""
    s = p(1099.0)  # dt=9 acc=99 rem=1 ext=1100
    assert s.soft_budget_used_s == pytest.approx(99.0)
    assert win.remaining_s() == pytest.approx(1.0)
    s = p(1100.0)  # dt=1 acc=100 rem=0 ext=1100
    assert s.soft_budget_used_s == pytest.approx(100.0)
    assert win.expired() == "first_progress_timeout"


def test_cli_soft_budget_exhausted_p_only_reflected_in_snapshot() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock, process_progress=True, soft_budget_s=15.0, safety_cap_s=1000.0)
    _at(clock, 1010.0)
    win.record_signal("P")  # acc=10 rem=5 ext=1015 deadline max(1020,1015)=1020
    _at(clock, 1018.0)
    win.record_signal("P")  # dt=8 -> min(8,5)=5 acc=15 rem=0 ext=1018 -> 1020
    snap = win.snapshot()
    assert snap.soft_budget_used_s == pytest.approx(15.0)
    assert win.remaining_s() == pytest.approx(2.0)
    _at(clock, 1100.0)
    win.record_signal("P")  # бюджет исчерпан: дедлайн не растёт, P лишь в snapshot
    snap = win.snapshot()
    assert snap.last_progress_kind == "P"
    assert snap.soft_budget_used_s == pytest.approx(15.0)
    assert win.remaining_s() <= 0.0
    assert win.expired() == "first_progress_timeout"
    _at(clock, 1110.0)
    win.record_signal("P")
    assert win.remaining_s() <= 0.0
    assert win.snapshot().soft_budget_used_s == pytest.approx(15.0)


def test_cli_single_p_cannot_spend_more_than_remaining_budget() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock, process_progress=True, soft_budget_s=10.0)
    _at(clock, 1019.0)
    win.record_signal("P")  # dt=19, но остаток 10
    assert win.snapshot().soft_budget_used_s == pytest.approx(10.0)


def test_cli_s_resets_budget_and_makes_window_sliding() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock, process_progress=True)
    _at(clock, 1010.0)
    win.record_signal("P")
    _at(clock, 1030.0)
    win.record_signal("P")
    assert win.snapshot().soft_budget_used_s == pytest.approx(30.0)
    win.record_signal("S", frozenset({"content"}))
    snap = win.snapshot()
    assert snap.soft_budget_used_s == 0.0
    assert snap.last_progress_kind == "S"
    assert win.remaining_s() == pytest.approx(30.0)  # idle после S
    _at(clock, 1059.0)
    assert win.expired() == ""
    _at(clock, 1060.0)
    assert win.expired() == "idle_timeout"
    # P после S: бюджет считается заново от момента S
    _at(clock, 1060.0)
    win2 = _window(clock, process_progress=True)
    win2.record_signal("S", frozenset({"content"}))
    _at(clock, 1070.0)
    win2.record_signal("P")
    assert win2.snapshot().soft_budget_used_s == pytest.approx(10.0)


def test_cli_process_sample_thresholds_when_soft_enabled() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock, process_progress=True, min_cpu_delta_s=0.05)
    _at(clock, 1005.0)
    win.record_process(cpu_delta_s=0.049, new_children=0, alive=True)
    assert win.snapshot().last_progress_kind == "none"
    win.record_process(cpu_delta_s=0.0, new_children=0, alive=True)
    assert win.snapshot().last_progress_kind == "none"
    assert win.snapshot().soft_budget_used_s == 0.0
    win.record_process(cpu_delta_s=0.05, new_children=0, alive=True)
    assert win.snapshot().last_progress_kind == "P"
    assert win.snapshot().soft_budget_used_s == pytest.approx(5.0)
    win = _window(clock, process_progress=True, min_cpu_delta_s=0.05)
    win.record_process(cpu_delta_s=0.0, new_children=2, alive=True)
    assert win.snapshot().last_progress_kind == "P"


def test_cli_process_sample_dead_group_is_not_progress() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock, process_progress=True)
    win.record_process(cpu_delta_s=5.0, new_children=2, alive=False)
    snap = win.snapshot()
    assert snap.last_progress_kind == "none"
    assert snap.process_alive is False


def test_cli_soft_disabled_p_is_unbounded_legacy() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock, soft=False, process_progress=True, safety_cap_s=10000.0)
    # min_cpu_delta не применяется: любой положительный CPU — прогресс
    _at(clock, 1010.0)
    win.record_process(cpu_delta_s=0.001, new_children=0, alive=True)
    assert win.remaining_s() == pytest.approx(30.0)  # 1040
    _at(clock, 1500.0)
    win.record_signal("P")  # без бюджета: now + idle
    assert win.remaining_s() == pytest.approx(30.0)
    _at(clock, 1520.0)
    win.record_signal("P")
    assert win.expired() == ""
    snap = win.snapshot()
    assert snap.soft_budget_used_s == 0.0
    assert snap.last_progress_kind == "P"


def test_cli_soft_disabled_p_still_bounded_by_safety_cap() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock, soft=False, process_progress=True)
    for t in range(1010, 1200, 10):
        _at(clock, float(t))
        win.record_signal("P")
    assert win.expired() == "safety_cap"


def test_snapshot_wire_has_eleven_keys_and_ages() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock)
    wire = win.snapshot().to_wire()
    assert set(wire) == {
        "internal_stream",
        "stream_requested",
        "last_token_age_s",
        "last_reasoning_age_s",
        "last_progress_kind",
        "last_keepalive_age_s",
        "process_alive",
        "soft_budget_used_s",
        "soft_budget_limit_s",
        "idle_remaining_s",
        "safety_cap_remaining_s",
    }
    assert wire["last_token_age_s"] is None
    assert wire["last_reasoning_age_s"] is None
    assert wire["last_keepalive_age_s"] is None
    assert wire["last_progress_kind"] == "none"
    assert wire["process_alive"] is None
    assert wire["soft_budget_used_s"] is None
    assert wire["soft_budget_limit_s"] is None
    assert wire["idle_remaining_s"] == pytest.approx(20.0)
    assert wire["safety_cap_remaining_s"] == pytest.approx(100.0)

    win.record_signal("S", frozenset({"content"}))
    _at(clock, 1005.0)
    win.record_signal("T")
    _at(clock, 1008.0)
    win.record_signal("S", frozenset({"reasoning_content"}))
    _at(clock, 1010.0)
    wire = win.snapshot().to_wire()
    assert wire["last_token_age_s"] == pytest.approx(10.0)
    assert wire["last_reasoning_age_s"] == pytest.approx(2.0)
    assert wire["last_keepalive_age_s"] == pytest.approx(5.0)
    assert wire["last_progress_kind"] == "S"


def test_snapshot_mixed_keys_update_both_ages_and_reasoning_only_skips_token() -> None:
    clock = _FakeClock(1000.0)
    win = _window(clock)
    win.record_signal("S", frozenset({"reasoning"}))
    snap = win.snapshot()
    assert snap.last_reasoning_age_s == 0.0
    assert snap.last_token_age_s is None
    win.record_signal("S", frozenset({"content", "reasoning_text"}))
    snap = win.snapshot()
    assert snap.last_token_age_s == 0.0
    assert snap.last_reasoning_age_s == 0.0


def test_snapshot_cli_has_numbers_and_spec_flags() -> None:
    clock = _FakeClock(1000.0)
    win = LivenessWindow(
        _spec(process_progress=True, internal_stream=True, stream_requested=False),
        clock=clock,
        soft_enabled=lambda: True,
    )
    win.record_process(cpu_delta_s=1.0, new_children=0, alive=True)
    snap = win.snapshot()
    assert snap.process_alive is True
    assert snap.soft_budget_used_s == 0.0
    assert snap.soft_budget_limit_s == 100.0
    assert snap.internal_stream is True
    assert snap.stream_requested is False


def test_snapshot_is_frozen() -> None:
    win = _window(_FakeClock(1000.0))
    snap = win.snapshot()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.last_progress_kind = "S"  # type: ignore[misc]
    assert isinstance(snap, LivenessSnapshot)
    # срез не меняется при дальнейших сигналах окна
    win.record_signal("S", frozenset({"content"}))
    assert snap.last_progress_kind == "none"


def test_nonstream_config_window_spec_maps_fields() -> None:
    cfg = NonstreamConfig()
    cli = cfg.window_spec(True)
    assert (cli.first_timeout_s, cli.idle_timeout_s, cli.safety_cap_s) == (90.0, 300.0, 3600.0)
    assert (cli.soft_budget_s, cli.min_cpu_delta_s, cli.process_progress) == (120.0, 0.05, True)
    pt = cfg.window_spec(False, internal_stream=True, stream_requested=False)
    assert pt.process_progress is False
    assert pt.internal_stream is True and pt.stream_requested is False


def test_liveness_window_thread_safety() -> None:
    win = LivenessWindow(
        _spec(
            first_timeout_s=3000.0,
            idle_timeout_s=3000.0,
            safety_cap_s=6000.0,
            process_progress=True,
        ),
        soft_enabled=lambda: True,
    )
    errors: list[BaseException] = []
    kinds = ("S", "T", "P")

    def worker(idx: int) -> None:
        try:
            for i in range(500):
                kind = kinds[(idx + i) % 3]
                keys = frozenset({"content"}) if kind == "S" else frozenset()
                win.record_signal(kind, keys)
                snap = win.snapshot()
                assert snap.last_progress_kind in {"none", "S", "P"}
                assert 0.0 <= (snap.idle_remaining_s or 0.0) <= 6000.0
                assert 0.0 <= (snap.safety_cap_remaining_s or 0.0) <= 6000.0
                assert 0.0 <= (snap.soft_budget_used_s or 0.0) <= 100.0
                for age in (snap.last_token_age_s, snap.last_keepalive_age_s):
                    assert age is None or age >= 0.0
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(30)
    assert not errors
    assert win.expired() == ""


# --- AdaptiveTimeoutController: интеграция с bounded-P --------------------


def _soft_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, enabled: bool) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    if enabled:
        monkeypatch.setenv(FLAG_SOFT_LIVENESS, "true")
    else:
        monkeypatch.delenv(FLAG_SOFT_LIVENESS, raising=False)


def _active(pgid: int = 4321, **kw: Any) -> WatchdogMetrics:
    fields: dict[str, Any] = dict(
        pgid=pgid,
        alive=True,
        descendant_pids=(pgid,),
        new_descendants=(),
        cpu_time_s=1.0,
        cpu_delta_s=1.0,
        ps_degraded=False,
        sample_ts=0.0,
    )
    fields.update(kw)
    return WatchdogMetrics(**fields)


def _controller(clock: _FakeClock, wd: ProcessWatchdog | None, **kw: Any) -> AdaptiveTimeoutController:
    params: dict[str, Any] = dict(
        idle_timeout_s=300.0,
        safety_cap_s=3600.0,
        watchdog=wd,
        watchdog_enabled=wd is not None,
        clock=clock,
        first_token_timeout_s=30.0,
    )
    params.update(kw)
    return AdaptiveTimeoutController(**params)


def test_controller_soft_enabled_sparse_cpu_does_not_extend_forever(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _soft_env(monkeypatch, tmp_path, enabled=True)
    clock = _FakeClock(1000.0)
    ctrl = _controller(clock, _StubWatchdog(_active()))
    ctrl.register_pgid(4321)
    # budget=120 (default), first_token=30: P на 1020 -> дедлайн 1120
    for step in (20.0, 40.0, 59.0):  # 1020, 1060, 1119
        clock.advance(step)
        assert ctrl.check(4321)[:2] == (False, "")
    assert ctrl.liveness_snapshot().soft_budget_used_s == pytest.approx(119.0)
    clock.advance(2.0)  # 1121: бюджет исчерпан
    should_stop, reason, metrics = ctrl.check(4321)
    assert (should_stop, reason) == (True, "idle_timeout")
    assert metrics is not None
    assert ctrl.terminated_reason == "idle_timeout"


def test_controller_soft_disabled_keeps_legacy_unbounded_cpu_trust(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _soft_env(monkeypatch, tmp_path, enabled=False)
    clock = _FakeClock(1000.0)
    ctrl = _controller(clock, _StubWatchdog(_active()))
    ctrl.register_pgid(4321)
    for _ in range(20):  # 2000с редких CPU-тиков: прежнее поведение не рвёт ход
        clock.advance(100.0)
        assert ctrl.check(4321)[:2] == (False, "")
    # без P-прогресса прежний idle-таймаут срабатывает как раньше
    idle = WatchdogMetrics.empty(4321, clock.now, alive=True)
    ctrl.watchdog._metrics = idle  # type: ignore[attr-defined]
    clock.advance(301.0)
    assert ctrl.check(4321)[:2] == (True, "idle_timeout")


def test_controller_first_token_timeout_applies_only_when_soft_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    idle_metrics = WatchdogMetrics.empty(4321, 0.0, alive=True)
    _soft_env(monkeypatch, tmp_path, enabled=True)
    clock = _FakeClock(1000.0)
    ctrl = _controller(clock, _StubWatchdog(idle_metrics))
    clock.advance(31.0)
    assert ctrl.check(4321)[:2] == (True, "idle_timeout")

    _soft_env(monkeypatch, tmp_path, enabled=False)
    clock = _FakeClock(1000.0)
    ctrl = _controller(clock, _StubWatchdog(idle_metrics))
    clock.advance(31.0)
    assert ctrl.check(4321)[:2] == (False, "")
    clock.advance(270.0)
    assert ctrl.check(4321)[:2] == (True, "idle_timeout")


def test_controller_activity_kinds_lifecycle_are_t_semantic_output_is_s(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _soft_env(monkeypatch, tmp_path, enabled=True)
    clock = _FakeClock(1000.0)
    ctrl = _controller(clock, None)  # без process sampler
    clock.advance(10.0)
    for kind in ("start", "done", "protocol", "keepalive", "heartbeat", ""):  # lifecycle/transport -> T
        ctrl.record_activity(kind)
    snap = ctrl.liveness_snapshot()
    assert snap.last_progress_kind == "none"
    assert snap.last_keepalive_age_s == 0.0
    assert snap.last_token_age_s is None
    clock.advance(21.0)  # 1031 > first-token дедлайн 1030: T не продлевал окно
    assert ctrl.check() == (True, "idle_timeout", None)

    clock = _FakeClock(1000.0)
    ctrl = _controller(clock, None)
    clock.advance(10.0)
    ctrl.record_activity("content")  # смысловой вывод -> S
    assert ctrl.liveness_snapshot().last_progress_kind == "S"
    clock.advance(21.0)  # окно перешло в пост-S: now + idle(300)
    assert ctrl.check() == (False, "", None)
    clock.advance(270.0)  # 1301 < 1010 + 300
    assert ctrl.check() == (False, "", None)
    clock.advance(20.0)  # 1321 >= 1310
    assert ctrl.check() == (True, "idle_timeout", None)


def test_controller_liveness_snapshot_reports_process_alive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _soft_env(monkeypatch, tmp_path, enabled=True)
    clock = _FakeClock(1000.0)
    ctrl = _controller(clock, _StubWatchdog(_active()))
    assert ctrl.liveness_snapshot().process_alive is None  # ещё не сэмплировали
    ctrl.register_pgid(4321)
    clock.advance(5.0)
    ctrl.check(4321)
    snap = ctrl.liveness_snapshot()
    assert isinstance(snap, LivenessSnapshot)
    assert snap.process_alive is True
    assert snap.last_progress_kind == "P"
    assert snap.soft_budget_limit_s == pytest.approx(NonstreamConfig().soft_budget_s)
    assert snap.safety_cap_remaining_s == pytest.approx(3565.0 - 5.0)


def test_controller_absolute_cap_has_priority_with_soft_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _soft_env(monkeypatch, tmp_path, enabled=True)
    clock = _FakeClock(1000.0)
    ctrl = _controller(clock, _StubWatchdog(_active()), safety_cap_s=100.0)
    ctrl.register_pgid(4321)
    ctrl.record_activity("content")  # S: окно было бы продлено
    clock.advance(66.0)  # effective cap = 100 - 35 = 65
    assert ctrl.check(4321) == (True, "absolute_cap", None)
    assert ctrl.terminated_reason == "absolute_cap"


def test_controller_window_cap_equals_effective_cap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _soft_env(monkeypatch, tmp_path, enabled=True)
    clock = _FakeClock(1000.0)
    ctrl = _controller(clock, None, safety_cap_s=100.0)
    assert ctrl.liveness.snapshot().safety_cap_remaining_s == pytest.approx(65.0)


def test_controller_child_exited_unchanged_with_soft_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _soft_env(monkeypatch, tmp_path, enabled=True)
    clock = _FakeClock(1000.0)
    dead = WatchdogMetrics.empty(4321, 0.0, alive=False)
    ctrl = _controller(clock, _StubWatchdog(dead))
    clock.advance(1.0)
    assert ctrl.check(4321) == (True, "child_exited", dead)


def test_watchdog_metrics_empty_equals_manual_constructors() -> None:
    now = 1234.5
    manual_dead = WatchdogMetrics(
        pgid=7,
        alive=False,
        descendant_pids=(),
        new_descendants=(),
        cpu_time_s=0.0,
        cpu_delta_s=0.0,
        ps_degraded=False,
        sample_ts=now,
    )
    assert WatchdogMetrics.empty(7, now, alive=False) == manual_dead
    manual_degraded = dataclasses.replace(manual_dead, alive=True, ps_degraded=True)
    assert WatchdogMetrics.empty(7, now, alive=True, degraded=True) == manual_degraded
    alive_ok = WatchdogMetrics.empty(7, now, alive=True)
    assert alive_ok.ps_degraded is False and alive_ok.alive is True
    assert not alive_ok.has_progress
    assert not WatchdogMetrics.empty(7, now, alive=True, degraded=True).has_progress
    assert not WatchdogMetrics.empty(7, now, alive=False).has_progress


@pytest.mark.parametrize("kind", ["content", "reasoning", "reasoning_content", "tool_calls", "function_call", "text_delta", "reasoning_delta", "tool_call"])
def test_classify_cli_activity_semantic_output_is_s(kind: str) -> None:
    assert classify_cli_activity(kind) == "S"


@pytest.mark.parametrize("kind", ["start", "done", "protocol", "keepalive", "heartbeat", "", "unknown-lifecycle"])
def test_classify_cli_activity_transport_and_lifecycle_are_t(kind: str) -> None:
    assert classify_cli_activity(kind) == "T"


def test_watchdog_import_has_no_env_side_effects() -> None:
    """F-018: `import core.watchdog` не читает и не валидирует BRIDGE_WATCHDOG_*/BRIDGE_NONSTREAM_* при импорте."""
    import subprocess
    import sys

    env = {**os.environ, "BRIDGE_WATCHDOG_IDLE_TIMEOUT_S": "bad", "BRIDGE_NONSTREAM_IDLE_TIMEOUT_S": "bad"}
    env.pop("PYTHONPATH", None)
    code = "import core.watchdog as w; print(w.IDLE_TIMEOUT_S, w.SAFETY_CAP_S, w.PS_TIMEOUT_S)"
    out = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(Path(__file__).resolve().parent.parent), capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.split() == ["300.0", "3600.0", "2.0"], out.stderr
    lazy = "from core.watchdog import ProcessWatchdog; ProcessWatchdog()"  # ленивый from_env падает только здесь
    bad = subprocess.run([sys.executable, "-c", lazy], env=env, cwd=str(Path(__file__).resolve().parent.parent), capture_output=True, text=True)
    assert bad.returncode != 0 and "invalid config parameter: BRIDGE_WATCHDOG_" in bad.stderr


def test_controller_resolves_watchdog_env_lazily_and_preserves_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRIDGE_WATCHDOG_IDLE_TIMEOUT_S", "77")
    monkeypatch.setenv("BRIDGE_WATCHDOG_FINISH_RESERVE_S", "0")
    ctrl = AdaptiveTimeoutController(watchdog_enabled=False)
    assert (ctrl.idle_timeout_s, ctrl.finish_reserve_s) == (77.0, 0.0)
    assert AdaptiveTimeoutController(idle_timeout_s=5, watchdog_enabled=False).idle_timeout_s == 5.0
    _soft_env(monkeypatch, tmp_path, enabled=True)
    ctrl0 = AdaptiveTimeoutController(first_token_timeout_s=0.0, watchdog_enabled=False)  # 0.0 не подменяется default
    assert ctrl0.liveness.expired() == "first_progress_timeout"  # окно построено с first=0.0 (а не 90 с)
