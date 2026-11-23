"""Tests for slot/session orphan hygiene helpers."""

import sys
from pathlib import Path

_BRIDGE_ROOT = (
    Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge"
)
if str(_BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_ROOT))

from agy_runtime.slot_and_session import (  # noqa: E402
    allow_job_orphan,
    evaluate_disconnect_action,
    should_detach_job_orphan,
)


def test_off_mode_parity_detaches() -> None:
    """Off mode keeps legacy detach for tool requests."""
    assert (
        should_detach_job_orphan(
            tools_count=2,
            ttfc_received=False,
            fast_enabled=False,
        )
        is True
    )
    assert (
        evaluate_disconnect_action(
            tools_count=2,
            ttfc_received=False,
            fast_enabled=False,
        )
        == "detach"
    )


def test_pre_ttfc_disconnect_cancels_sync() -> None:
    """Fast mode before TTFC cancels synchronously."""
    assert (
        should_detach_job_orphan(
            tools_count=3,
            ttfc_received=False,
            fast_enabled=True,
        )
        is False
    )
    assert (
        evaluate_disconnect_action(
            tools_count=3,
            ttfc_received=False,
            fast_enabled=True,
        )
        == "cancel_sync"
    )


def test_post_ttfc_disconnect_respects_orphan_max() -> None:
    """Post-TTFC detach is bounded by the orphan maximum."""
    assert (
        should_detach_job_orphan(
            tools_count=2,
            ttfc_received=True,
            active_orphans=4,
            fast_enabled=True,
        )
        is True
    )
    assert (
        evaluate_disconnect_action(
            tools_count=2,
            ttfc_received=True,
            active_orphans=4,
            fast_enabled=True,
        )
        == "detach"
    )
    assert (
        should_detach_job_orphan(
            tools_count=2,
            ttfc_received=True,
            active_orphans=5,
            fast_enabled=True,
        )
        is False
    )
    assert (
        evaluate_disconnect_action(
            tools_count=2,
            ttfc_received=True,
            active_orphans=5,
            fast_enabled=True,
        )
        == "cancel_sync"
    )


def test_existing_allow_job_orphan_intact() -> None:
    """Legacy allow_job_orphan behavior is unchanged."""
    assert allow_job_orphan(0, {}) is False
    assert allow_job_orphan(2, {}) is True
