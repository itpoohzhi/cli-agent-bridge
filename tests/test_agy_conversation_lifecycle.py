"""Детерминированные проверки чистого жизненного цикла беседы agy."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import sys
from pathlib import Path
from typing import Final

import pytest

_ROOT: Final = Path(__file__).resolve().parents[1]
_BRIDGE: Final = _ROOT / "bridges" / "agy-bridge"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_BRIDGE) not in sys.path:
    sys.path.append(str(_BRIDGE))
_SOURCE: Final = _BRIDGE / "agy_runtime" / "conversation_lifecycle.py"

from agy_runtime.conversation_lifecycle import (  # noqa: E402
    ConversationLifecycle,
    LifecycleEvent,
    LifecyclePolicy,
    LifecycleState,
    is_conversation_expired,
)


def test_lifecycle_policy_defaults_match_legacy_session_store() -> None:
    policy = LifecyclePolicy()
    assert policy.max_turns == 30
    assert policy.idle_ttl_s == 2700.0
    assert policy.max_ttl_s == 86400.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_turns": 0},
        {"max_turns": -1},
        {"max_turns": True},
        {"max_turns": 1.5},
        {"idle_ttl_s": 0},
        {"idle_ttl_s": -1},
        {"idle_ttl_s": float("nan")},
        {"idle_ttl_s": float("inf")},
        {"idle_ttl_s": True},
        {"max_ttl_s": 0},
        {"max_ttl_s": -1},
        {"max_ttl_s": float("nan")},
        {"max_ttl_s": float("-inf")},
        {"max_ttl_s": False},
    ],
)
def test_lifecycle_policy_rejects_invalid_limits(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        LifecyclePolicy(**kwargs)  # type: ignore[arg-type]


def test_lifecycle_policy_is_immutable_and_accepts_custom_limits() -> None:
    policy = LifecyclePolicy(max_turns=2, idle_ttl_s=10, max_ttl_s=60)
    assert (policy.max_turns, policy.idle_ttl_s, policy.max_ttl_s) == (2, 10, 60)
    with pytest.raises(FrozenInstanceError):
        policy.max_turns = 3  # type: ignore[misc]


def _expected_transition(
    state: LifecycleState, event: LifecycleEvent
) -> LifecycleState:
    if event is LifecycleEvent.COLD_REQUEST:
        return LifecycleState.ACTIVE
    if event is LifecycleEvent.TOMBSTONE:
        return LifecycleState.TOMBSTONED
    if event in {LifecycleEvent.RESTART, LifecycleEvent.TEXT_ONLY_FALLBACK}:
        return LifecycleState.NONE
    if state is not LifecycleState.ACTIVE:
        return state
    if event in {
        LifecycleEvent.MAX_TURNS,
        LifecycleEvent.IDLE_TTL,
        LifecycleEvent.MAX_TTL,
        LifecycleEvent.CONTINUITY_MISS,
    }:
        return LifecycleState.EXPIRED
    return LifecycleState.ACTIVE


@pytest.mark.parametrize("state", list(LifecycleState))
@pytest.mark.parametrize("event", list(LifecycleEvent))
def test_transition_table_is_total_and_pure(
    state: LifecycleState, event: LifecycleEvent
) -> None:
    expected = _expected_transition(state, event)
    assert ConversationLifecycle.transition(state, event) is expected
    assert ConversationLifecycle.transition(state, event) is expected


def test_transition_exposes_domain_aliases_and_covers_36_pairs() -> None:
    assert ConversationLifecycle.State is LifecycleState
    assert ConversationLifecycle.Event is LifecycleEvent
    covered = {
        (state, event)
        for state in LifecycleState
        for event in LifecycleEvent
        if ConversationLifecycle.transition(state, event) in LifecycleState
    }
    assert len(covered) == len(LifecycleState) * len(LifecycleEvent) == 36


@pytest.mark.parametrize(
    ("created_s", "last_used_s", "turns", "now_s", "expected"),
    [
        (100.0, 100.0, 0, 100.0, False),
        (100.0, 100.0, 0, 2800.0, False),
        (100.0, 100.0, 0, 2800.000001, True),
        (100.0, 2000.0, 0, 2800.0, False),
        (100.0, 86500.0, 0, 86500.0, False),
        (100.0, 86500.0, 0, 86500.000001, True),
        (100.0, 100.0, 29, 200.0, False),
        (100.0, 100.0, 30, 200.0, True),
        (100.0, 100.0, 31, 200.0, True),
        (100.0, 200.0, 0, 150.0, False),
        (200.0, 200.0, 0, 150.0, False),
    ],
)
def test_expiry_predicate_matches_legacy_defaults(
    created_s: float, last_used_s: float, turns: int, now_s: float, expected: bool
) -> None:
    legacy = (
        now_s - last_used_s > 45 * 60.0 or now_s - created_s > 86400.0 or turns >= 30
    )
    actual = is_conversation_expired(created_s, last_used_s, turns, now_s)
    assert actual is legacy is expected


def test_expiry_predicate_uses_explicit_policy_and_short_circuits() -> None:
    policy = LifecyclePolicy(max_turns=2, idle_ttl_s=10.0, max_ttl_s=60.0)
    assert not is_conversation_expired(0.0, 0.0, 1, 10.0, policy)
    assert is_conversation_expired(0.0, 0.0, 1, 10.1, policy)
    assert is_conversation_expired(0.0, 59.0, 0, 60.1, policy)
    assert is_conversation_expired(0.0, 0.0, 2, 0.0, policy)


def test_domain_module_has_no_io_clock_or_mutable_module_collections() -> None:
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    forbidden_imports = {
        "os",
        "sys",
        "subprocess",
        "threading",
        "socket",
        "time",
        "datetime",
        "pathlib",
        "httpx",
        "openai",
        "requests",
        "aiohttp",
        "urllib3",
        "fastapi",
        "litestar",
        "starlette",
        "sqlalchemy",
        "redis",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                alias.name.split(".")[0] not in forbidden_imports
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden_imports
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            assert not isinstance(
                value,
                (ast.Dict, ast.List, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp),
            )
