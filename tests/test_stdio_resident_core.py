"""Contract tests for the resident stdio pool core."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.runtime_env import ConfigError  # noqa: E402
from core.stdio_resident.config import (  # noqa: E402
    FLAG_RESIDENT_ENABLED,
    StdioPoolConfig,
)
from core.stdio_resident.types import (  # noqa: E402
    SlotEffect,
    SlotEvent,
    SlotState,
    step_slot_fsm,
)


def test_slot_fsm_covers_complete_state_event_matrix() -> None:
    """Every one of the 8 x 15 input pairs has a typed transition."""

    pairs = 0
    for state in SlotState:
        for event in SlotEvent:
            next_state, effects = step_slot_fsm(state, event)

            assert isinstance(next_state, SlotState)
            assert isinstance(effects, list)
            assert all(isinstance(effect, SlotEffect) for effect in effects)
            pairs += 1

    assert pairs == len(SlotState) * len(SlotEvent)
    assert pairs == 120  # 8 states x 15 events


def test_handshake_state_transitions() -> None:
    """Verify FSM transitions into and out of HANDSHAKE state."""
    next_state, effects = step_slot_fsm(SlotState.SPAWNING, SlotEvent.InitOk)
    assert next_state is SlotState.HANDSHAKE
    assert effects == []

    next_state, effects = step_slot_fsm(SlotState.HANDSHAKE, SlotEvent.HandshakeOk)
    assert next_state is SlotState.READY
    assert effects == []

    next_state, effects = step_slot_fsm(
        SlotState.HANDSHAKE,
        SlotEvent.HandshakeFailed,
    )
    assert next_state is SlotState.BROKEN
    assert effects == [SlotEffect.Teardown, SlotEffect.ReportError]

    next_state, effects = step_slot_fsm(SlotState.HANDSHAKE, SlotEvent.Lease)
    assert next_state is SlotState.HANDSHAKE
    assert effects == [SlotEffect.Reject]

    next_state, effects = step_slot_fsm(SlotState.HANDSHAKE, SlotEvent.Shutdown)
    assert next_state is SlotState.CLOSED
    assert effects == [SlotEffect.Teardown]


def test_busy_cancel_request_starts_canceling_protocol() -> None:
    """AD-003/AD-016: cancellation begins without committing the turn."""

    next_state, effects = step_slot_fsm(SlotState.BUSY, SlotEvent.CancelRequested)

    assert next_state is SlotState.CANCELING
    assert effects == [SlotEffect.SendCancel, SlotEffect.StartCancelGrace]


def test_canceling_never_returns_to_ready() -> None:
    """AD-016: a canceling slot can only remain canceling or close."""

    for event in SlotEvent:
        next_state, _ = step_slot_fsm(SlotState.CANCELING, event)

        assert next_state in (SlotState.CANCELING, SlotState.CLOSED)
        assert next_state is not SlotState.READY


def test_canceling_terminal_discards_turn_and_tears_down() -> None:
    """AD-003: a terminal event after cancellation cannot commit the turn."""

    next_state, effects = step_slot_fsm(
        SlotState.CANCELING,
        SlotEvent.TurnTerminal,
    )

    assert next_state is SlotState.CLOSED
    assert effects == [SlotEffect.DiscardBuffer, SlotEffect.Teardown]
    assert SlotEffect.CommitTurn not in effects


def test_busy_terminal_commits_and_returns_slot_to_pool() -> None:
    """A normal terminal event commits and advances the reusable slot."""

    next_state, effects = step_slot_fsm(SlotState.BUSY, SlotEvent.TurnTerminal)

    assert next_state is SlotState.READY
    assert effects == [
        SlotEffect.CommitTurn,
        SlotEffect.AdvanceGeneration,
        SlotEffect.ReturnToPool,
    ]


def test_stdio_pool_config_defaults() -> None:
    """AD-017: absent environment values select safe disabled defaults."""

    config = StdioPoolConfig.from_env({})

    assert config == StdioPoolConfig()
    assert config.enabled is False
    assert config.shutdown_timeout_s == 10.0


def test_stdio_pool_config_custom_environment() -> None:
    """AD-017: every operational limit is environment-configurable."""

    config = StdioPoolConfig.from_env(
        {
            "BRIDGE_STDIO_MAX_SLOTS": "8",
            "BRIDGE_STDIO_IDLE_TIMEOUT_S": "45.5",
            "BRIDGE_STDIO_TTL_S": "7200",
            "BRIDGE_STDIO_MAX_RSS_BYTES": "2147483648",
            "BRIDGE_STDIO_LEASE_WAIT_S": "12.5",
            "BRIDGE_STDIO_CANCEL_GRACE_S": "2.5",
            "BRIDGE_STDIO_SHUTDOWN_TIMEOUT_S": "15.5",
            FLAG_RESIDENT_ENABLED: "1",
        }
    )

    assert config == StdioPoolConfig(
        max_slots=8,
        idle_timeout_s=45.5,
        ttl_s=7200.0,
        max_rss_bytes=2147483648,
        lease_wait_s=12.5,
        cancel_grace_s=2.5,
        shutdown_timeout_s=15.5,
        enabled=True,
    )


def test_stdio_pool_config_accepts_lower_boundaries() -> None:
    """NumSpec lower boundaries are inclusive for all pool limits."""

    config = StdioPoolConfig.from_env(
        {
            "BRIDGE_STDIO_MAX_SLOTS": "1",
            "BRIDGE_STDIO_IDLE_TIMEOUT_S": "1",
            "BRIDGE_STDIO_TTL_S": "10",
            "BRIDGE_STDIO_MAX_RSS_BYTES": "52428800",
            "BRIDGE_STDIO_LEASE_WAIT_S": "0.1",
            "BRIDGE_STDIO_CANCEL_GRACE_S": "0.1",
            "BRIDGE_STDIO_SHUTDOWN_TIMEOUT_S": "0.5",
        }
    )

    assert config.max_slots == 1
    assert config.idle_timeout_s == 1.0
    assert config.ttl_s == 10.0
    assert config.max_rss_bytes == 52428800
    assert config.lease_wait_s == 0.1
    assert config.cancel_grace_s == 0.1
    assert config.shutdown_timeout_s == 0.5


def test_stdio_pool_config_accepts_upper_boundaries() -> None:
    """Finite NumSpec upper boundaries are inclusive."""

    config = StdioPoolConfig.from_env(
        {
            "BRIDGE_STDIO_MAX_SLOTS": "64",
            "BRIDGE_STDIO_IDLE_TIMEOUT_S": "86400",
            "BRIDGE_STDIO_TTL_S": "86400",
            "BRIDGE_STDIO_LEASE_WAIT_S": "300",
            "BRIDGE_STDIO_CANCEL_GRACE_S": "60",
            "BRIDGE_STDIO_SHUTDOWN_TIMEOUT_S": "120",
        }
    )

    assert config.max_slots == 64
    assert config.idle_timeout_s == 86400.0
    assert config.ttl_s == 86400.0
    assert config.lease_wait_s == 300.0
    assert config.cancel_grace_s == 60.0
    assert config.shutdown_timeout_s == 120.0


def test_stdio_pool_config_rejects_values_outside_boundaries() -> None:
    """NumSpec rejects values immediately outside configured boundaries."""

    invalid_values = [
        ("BRIDGE_STDIO_MAX_SLOTS", "0"),
        ("BRIDGE_STDIO_MAX_SLOTS", "65"),
        ("BRIDGE_STDIO_MAX_RSS_BYTES", "52428799"),
        ("BRIDGE_STDIO_SHUTDOWN_TIMEOUT_S", "120.1"),
    ]
    for name, value in invalid_values:
        try:
            _ = StdioPoolConfig.from_env({name: value})
        except ConfigError as exc:
            assert str(exc) == f"invalid config parameter: {name}"
        else:
            raise AssertionError(f"{name}={value} must be rejected")
