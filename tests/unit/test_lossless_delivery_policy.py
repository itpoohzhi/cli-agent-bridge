"""L1 red contracts for pure lossless policy and delivery primitives."""

from __future__ import annotations

import math
import sys
import threading
from pathlib import Path

import pytest

AGY_DIR = Path(__file__).resolve().parents[2] / "bridges" / "agy-bridge"
if str(AGY_DIR) not in sys.path:
    sys.path.insert(0, str(AGY_DIR))

from agy_runtime.lossless_streaming_delivery import (  # noqa: E402
    FinalTurnIdleWatchdog,
    LosslessDeliveryChannel,
    summarize_receipt,
    terminal_http_status,
)
from core.lossless_delivery_policy import (  # noqa: E402
    MAX_ACK_PHASE_DEADLINE_S,
    ack_phase_deadline_s,
    format_lossless_event,
    lossless_owns_process,
    parse_ack_event,
    resolve_delivery_timeouts,
)
from core.lossless_fsm import SessionState  # noqa: E402


def test_timeouts_default_when_unset() -> None:
    got = resolve_delivery_timeouts({}, None)
    assert got.chunk_ack_timeout_s == pytest.approx(60.0)
    assert got.final_turn_idle_timeout_s == pytest.approx(180.0)


def test_env_overrides_dynamic_cfg() -> None:
    got = resolve_delivery_timeouts(
        {
            "AGY_BRIDGE_LOSSLESS_CHUNK_ACK_TIMEOUT_S": "7",
            "AGY_BRIDGE_LOSSLESS_FINAL_TURN_IDLE_TIMEOUT_S": "9",
        },
        {"lossless_chunk_ack_timeout_s": 2, "lossless_final_turn_idle_timeout_s": 3},
    )
    assert (got.chunk_ack_timeout_s, got.final_turn_idle_timeout_s) == (7.0, 9.0)


def test_dynamic_cfg_overrides_default() -> None:
    got = resolve_delivery_timeouts(
        {}, {"lossless_chunk_ack_timeout_s": 4, "lossless_final_turn_idle_timeout_s": 8}
    )
    assert (got.chunk_ack_timeout_s, got.final_turn_idle_timeout_s) == (4.0, 8.0)


def test_invalid_env_falls_back_to_dynamic_cfg() -> None:
    got = resolve_delivery_timeouts(
        {
            "AGY_BRIDGE_LOSSLESS_CHUNK_ACK_TIMEOUT_S": "oops",
            "AGY_BRIDGE_LOSSLESS_FINAL_TURN_IDLE_TIMEOUT_S": "nan",
        },
        {"lossless_chunk_ack_timeout_s": 4, "lossless_final_turn_idle_timeout_s": 8},
    )
    assert (got.chunk_ack_timeout_s, got.final_turn_idle_timeout_s) == (4.0, 8.0)


@pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "0", "-1", True, False])
def test_nan_inf_bool_nonpositive_rejected(raw: object) -> None:
    got = resolve_delivery_timeouts(
        {"AGY_BRIDGE_LOSSLESS_CHUNK_ACK_TIMEOUT_S": str(raw)},
        {"lossless_chunk_ack_timeout_s": 11},
    )
    assert math.isfinite(got.chunk_ack_timeout_s)
    assert got.chunk_ack_timeout_s == pytest.approx(11.0)


def test_values_clamped_to_bounds() -> None:
    got = resolve_delivery_timeouts(
        {
            "AGY_BRIDGE_LOSSLESS_CHUNK_ACK_TIMEOUT_S": "99999",
            "AGY_BRIDGE_LOSSLESS_FINAL_TURN_IDLE_TIMEOUT_S": "1",
        },
        None,
    )
    assert got.chunk_ack_timeout_s == pytest.approx(600.0)
    assert got.final_turn_idle_timeout_s == pytest.approx(5.0)


@pytest.mark.parametrize("slot", [False, True])
@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("lease", [False, True])
def test_lossless_owns_process_matrix(
    slot: bool, persistent: bool, lease: bool
) -> None:
    assert lossless_owns_process(
        slot_held=slot, persistent_mode=persistent, has_lease=lease
    ) is (slot and not persistent and not lease)


@pytest.mark.parametrize(("chunks", "expected"), [(1, 61.5), (2, 121.5), (4, 241.5)])
def test_ack_phase_deadline_formula(chunks: int, expected: float) -> None:
    assert ack_phase_deadline_s(chunks, 60.0, 1.5) == pytest.approx(expected)


def test_ack_phase_deadline_rejects_zero_chunks() -> None:
    with pytest.raises(ValueError):
        ack_phase_deadline_s(0, 60.0, 1.5)


def test_ack_phase_deadline_clamps_and_rejects_bool() -> None:
    assert MAX_ACK_PHASE_DEADLINE_S == pytest.approx(600.0)
    assert ack_phase_deadline_s(20, 60.0, 1.5) == pytest.approx(600.0)
    with pytest.raises(ValueError):
        ack_phase_deadline_s(True, 60.0, 1.5)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("not-json", (False, None)),
        ("[]", (False, None)),
        ('{"type":"step"}', (False, None)),
        ('{"event":"result","epoch":3}', (True, 3)),
        ('{"type":"result","epoch":true}', (True, None)),
    ],
)
def test_parse_ack_event_variants(raw: str, expected: tuple[bool, int | None]) -> None:
    assert parse_ack_event(raw) == expected


def test_format_lossless_event_single_line_sorted_sanitized() -> None:
    line = format_lossless_event("delivery_result", {"z": "a\nb", "a": "x\r"})
    assert line.startswith("lossless_event event=delivery_result ")
    assert "\n" not in line and "\r" not in line
    assert line.split().index("a=x_") < line.split().index("z=a_b")


def test_format_lossless_event_rejects_unknown_event() -> None:
    with pytest.raises(ValueError):
        format_lossless_event("unknown_event", {"a": "1"})


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (SessionState.COMPLETED, 200),
        (SessionState.REJECTED, 413),
        (SessionState.CANCELLED, 499),
        (SessionState.EPOCH_MISMATCH, 409),
        (SessionState.FAILED, 400),
    ],
)
def test_terminal_http_status_mapping(state: SessionState, expected: int) -> None:
    assert terminal_http_status(state) == expected


def test_summarize_receipt_none_and_allowlist() -> None:
    assert summarize_receipt(None) == ""
    summary = summarize_receipt(
        {"state": "FAILED", "reason": "ack_timeout", "http_status": 400, "prompt": "secret"}
    )
    assert summary != ""
    assert "FAILED" in summary and "ack_timeout" in summary
    assert "secret" not in summary and "prompt" not in summary


def test_channel_publish_then_wait() -> None:
    channel = LosslessDeliveryChannel(None)
    result = object()
    channel.publish(result)
    assert channel.wait(0.0) is True
    assert channel.result() is result


def test_channel_wait_timeout_unsignalled() -> None:
    channel = LosslessDeliveryChannel(None)
    assert channel.wait(0.01) is False


def test_channel_publish_none_signals_failure() -> None:
    channel = LosslessDeliveryChannel(None)
    channel.publish(None)
    assert channel.wait(0.0) is True
    assert channel.result() is None


def test_channel_mark_timed_out_blocks_late_publish() -> None:
    channel = LosslessDeliveryChannel(None)
    snap = {"state": "SENDING"}
    channel.record_snapshot(snap)
    assert channel.mark_timed_out() is snap
    channel.publish(object())
    assert channel.wait(0.0) is False
    assert channel.result() is None


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        value, self.value = self.value, self.value + 1.0
        return value


def test_watchdog_fires_once_after_idle() -> None:
    fired = threading.Event()
    hits: list[object] = []
    clock = _Clock()
    watchdog = FinalTurnIdleWatchdog(0.01, lambda: (hits.append(None), fired.set()), clock=clock)
    watchdog.start()
    assert fired.wait(1.0)
    fired.clear()
    assert not fired.wait(0.01)
    assert len(hits) == 1
    watchdog.stop()


def test_watchdog_touch_extends_window() -> None:
    fired = threading.Event()
    watchdog = FinalTurnIdleWatchdog(0.05, fired.set)
    watchdog.start()
    watchdog.touch()
    assert not fired.wait(0.01)
    assert fired.wait(1.0)
    watchdog.stop()


def test_watchdog_stop_prevents_fire() -> None:
    fired = threading.Event()
    watchdog = FinalTurnIdleWatchdog(0.05, fired.set)
    watchdog.start()
    watchdog.stop()
    assert not fired.wait(0.1)


def test_watchdog_respects_max_total_s_cap() -> None:
    fired = threading.Event()
    watchdog = FinalTurnIdleWatchdog(10.0, fired.set, max_total_s=0.01, clock=_Clock())
    watchdog.start()
    watchdog.touch()
    assert fired.wait(1.0)
    assert watchdog.fire_count == 1
    watchdog.stop()
