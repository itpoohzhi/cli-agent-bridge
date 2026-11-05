"""Validation tests for T-ISO-I2 Diversion Sensitivity.

Ensures that intentional state pollution (singletons, env) is caught immediately
by the verify_and_reset_bridge_state fixture when strict leak checking is enabled,
and that state is restored cleanly to prevent test pollution.
"""

from __future__ import annotations

import os
from unittest.mock import Mock
import pytest
import server
from tests.conftest import _execute_bridge_isolation


def test_clean_state_passes_strict_check() -> None:
    """A clean test leaves no trace and passes strict check."""
    assert server._shutting_down is False
    assert server._budget is None


def test_diversion_leak_caught_and_isolated() -> None:
    """Directly verifies that state pollution raises AssertionError under strict mode."""
    mock_request = Mock()
    mock_request.node.nodeid = "test_canary_node"
    mock_request.node.get_closest_marker.return_value = True  # strict_leak_check

    # Enter fixture
    gen = _execute_bridge_isolation(mock_request)
    next(gen)

    # Intentionally corrupt singleton state
    server._shutting_down = True
    os.environ["POLLUTED_KEY"] = "poison"

    # Teardown must raise AssertionError naming the culprit node and reasons
    with pytest.raises(AssertionError) as exc_info:
        try:
            next(gen)
        except StopIteration:
            pass

    err_msg = str(exc_info.value)
    assert "State leak detected in test_canary_node" in err_msg
    assert "dirty_singleton=_shutting_down" in err_msg
    assert "mutated_env_added=['POLLUTED_KEY']" in err_msg

    # Invariant: despite the leak, state was cleaned up
    assert server._shutting_down is False
    assert "POLLUTED_KEY" not in os.environ
