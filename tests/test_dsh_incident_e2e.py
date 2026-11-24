from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.error_taxonomy import ClassifiedError, classify_upstream_error  # noqa: E402
from core.replay_policy import (  # noqa: E402
    ReplayProof,
    apply_budget_to_proof,
    build_replay_proof,
    calculate_retry_budget,
)


@dataclass
class StubTransport:
    outcomes: list[str]
    calls: int = 0

    def execute(self) -> str:
        outcome = self.outcomes[self.calls]
        self.calls += 1
        return outcome


def run_incident(
    transport: StubTransport,
    proof: ReplayProof,
    classify: Callable[[str, ReplayProof], ClassifiedError],
) -> ClassifiedError | None:
    budget = calculate_retry_budget(30, 1, remaining_s=30, backoff_s=0)
    bounded = apply_budget_to_proof(proof, budget)
    for attempt in range(budget.attempts):
        outcome = transport.execute()
        if outcome == "ok":
            return None
        error = classify(outcome, bounded)
        if not error.retryable or attempt + 1 == budget.attempts:
            return error
    raise AssertionError("unreachable")


def classify_with_proof(message: str, proof: ReplayProof) -> ClassifiedError:
    return classify_upstream_error(message, replay_proof=proof)


def test_transport_before_first_byte_is_uncertain_and_does_not_retry() -> None:
    transport = StubTransport(["connection reset before first byte", "ok"])
    proof = build_replay_proof(0, False, 0, "before_first_byte")
    assert run_incident(transport, proof, classify_with_proof) is not None
    assert transport.calls == 1


def test_confirmed_failure_before_execution_retries_once() -> None:
    transport = StubTransport(["connection reset before first byte", "ok"])
    proof = build_replay_proof(0, False, 0, "before_first_byte", True)
    assert run_incident(transport, proof, classify_with_proof) is None
    assert transport.calls == 2


def test_quota_is_429_and_never_reaches_cold_fallback() -> None:
    transport = StubTransport(["Individual quota reached", "ok"])
    proof = build_replay_proof(0, False, 0, "before_first_byte")
    result = run_incident(transport, proof, classify_with_proof)
    assert result is not None
    assert (result.category, result.http_status, transport.calls) == ("QUOTA", 429, 1)


def test_interrupted_is_fail_closed_without_fallback() -> None:
    transport = StubTransport(["PI_AI_ERROR: interrupted", "ok"])
    proof = build_replay_proof(0, False, 0, "before_first_byte")
    result = run_incident(transport, proof, classify_with_proof)
    assert result is not None
    assert result.cancellation_subtype == "unspecified"
    assert result.retryable is False
    assert transport.calls == 1


def test_transport_after_commit_does_not_retry() -> None:
    transport = StubTransport(["socket premature EOF", "ok"])
    proof = build_replay_proof(1, True, 0, "before_first_byte")
    result = run_incident(transport, proof, classify_with_proof)
    assert result is not None
    assert result.category == "TRANSPORT"
    assert transport.calls == 1
