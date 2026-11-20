"""L1: политика удержания горячей сессии (AD-004, VER-006)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.hot_session_retention_policy import should_retain_hot_session  # noqa: E402
from core.transport_failure_contracts import FailureKind, HotSessionFacts  # noqa: E402

_T = FailureKind.NETWORK_TRANSIENT


def test_retain_only_untouched_session_on_network_transient() -> None:
    decision = should_retain_hot_session(HotSessionFacts(_T, 0, "-"))
    assert (decision.retain, decision.reason) == (True, "transient_untouched_session")


@pytest.mark.parametrize("kind", [FailureKind.FATAL, FailureKind.UNCLASSIFIED])
def test_non_transient_kinds_invalidate(kind: FailureKind) -> None:
    decision = should_retain_hot_session(HotSessionFacts(kind, 0, "-"))
    assert (decision.retain, decision.reason) == (False, "not_network_transient")


@pytest.mark.parametrize("turns", [1, 2, 6, -1])
def test_mutated_turns_invalidate(turns: int) -> None:
    """Шаги idx4..idx6 (turns > 0) — сессия мутирована, как в базе."""
    decision = should_retain_hot_session(HotSessionFacts(_T, turns, "-"))
    assert (decision.retain, decision.reason) == (False, "session_mutated_turns")


@pytest.mark.parametrize("conversation", ["c83f5757", "", " ", "-x", "--", "None"])
def test_conversation_id_present_invalidates(conversation: str) -> None:
    decision = should_retain_hot_session(HotSessionFacts(_T, 0, conversation))
    assert (decision.retain, decision.reason) == (False, "session_mutated_conversation")


@pytest.mark.parametrize("turns", [0.0, True, False, "0", None])
def test_non_int_turns_fail_closed(turns: object) -> None:
    decision = should_retain_hot_session(HotSessionFacts(_T, turns, "-"))  # type: ignore[arg-type]
    assert decision.retain is False


def test_two_chats_with_same_start_do_not_stick_together() -> None:
    """Решение зависит только от фактов своего хода: больной чат не влияет на здоровый."""
    sick = should_retain_hot_session(HotSessionFacts(_T, 2, "c1"))
    healthy = should_retain_hot_session(HotSessionFacts(_T, 0, "-"))
    assert (sick.retain, healthy.retain) == (False, True)


def test_decision_is_pure_and_repeatable() -> None:
    facts = HotSessionFacts(_T, 0, "-")
    assert should_retain_hot_session(facts) == should_retain_hot_session(facts)
