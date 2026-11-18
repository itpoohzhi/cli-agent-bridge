import sys
from pathlib import Path

import pytest


BRIDGE_DIR = Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge"
sys.path.insert(0, str(BRIDGE_DIR))

from agy_runtime.retry_budget import should_allow_retry_attempt  # noqa: E402


@pytest.mark.parametrize(
    "attempt,cancelled,can_start,expected",
    [
        (2, True, True, (False, "client_gone")),
        (2, False, False, (False, "request_budget_exhausted")),
        (1, False, True, (True, "")),
    ],
)
def test_retry_attempt_budget(attempt, cancelled, can_start, expected):
    assert should_allow_retry_attempt(
        attempt=attempt,
        cancelled=cancelled,
        can_start=can_start,
    ) == expected


def test_server_has_no_global_account_pool_initialization():
    source = (BRIDGE_DIR / "server.py").read_text(encoding="utf-8")
    assert "_account_pool = AccountPool(" not in source
