"""Pure, fail-closed policy for replay and quota-group failover."""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Final

MAX_RETRIES: Final[int] = 2
_PRECOMMIT_STAGES: Final[frozenset[str]] = frozenset(
    {"connect", "send_headers", "before_first_byte"}
)


@dataclass(frozen=True)
class ReplayProof:
    """Facts proving that replay cannot duplicate observable work."""

    bytes_sent_to_client: int
    response_started: bool
    tool_calls_emitted: int
    fail_stage: str
    allow_retry: bool


@dataclass(frozen=True)
class RetryBudget:
    """Validated attempt sizing; invalid input disables every retry layer."""

    max_retries: int
    attempts: int
    total_s: float | None
    attempt_s: float | None
    remaining_s: float | None
    valid: bool
    allow_retry: bool


@dataclass(frozen=True)
class FailoverEligibility:
    """Result of the default-off, distinct-quota-group eligibility check."""

    eligible: bool
    target_quota_group: str = ""


def build_replay_proof(
    bytes_sent_to_client: int,
    response_started: bool,
    tool_calls_emitted: int,
    fail_stage: str,
) -> ReplayProof:
    """Permit replay only when all pre-commit facts are positively proven."""
    facts_valid = (
        type(bytes_sent_to_client) is int
        and bytes_sent_to_client == 0
        and type(response_started) is bool
        and response_started is False
        and type(tool_calls_emitted) is int
        and tool_calls_emitted == 0
        and fail_stage in _PRECOMMIT_STAGES
    )
    return ReplayProof(
        bytes_sent_to_client=bytes_sent_to_client,
        response_started=response_started,
        tool_calls_emitted=tool_calls_emitted,
        fail_stage=fail_stage,
        allow_retry=facts_valid,
    )


def parse_retry_budget(value: object) -> int:
    """Parse ``X-Bridge-Retry-Budget``; malformed input means zero retries."""
    if isinstance(value, str):
        value = value.strip()
        if not value or not value.isascii() or not value.isdecimal():
            return 0
        parsed = int(value)
    elif type(value) is int:
        parsed = value
    else:
        return 0
    return parsed if 0 <= parsed <= MAX_RETRIES else 0


def parse_retry_budget_header(headers: Mapping[str, object] | None) -> int:
    """Read the retry budget from a case-insensitive header mapping."""
    if not isinstance(headers, Mapping):
        return 0
    value = next(
        (item for key, item in headers.items() if key.lower() == "x-bridge-retry-budget"),
        None,
    )
    return parse_retry_budget(value)


def calculate_retry_budget(
    total_s: object,
    max_retries: object,
    remaining_s: object | None = None,
    backoff_s: object = 0.0,
) -> RetryBudget:
    """Size attempts within the total/remaining budget or disable retries."""
    retries = parse_retry_budget(max_retries)
    attempts = 1 + retries
    total = _positive_finite(total_s)
    remaining = total if remaining_s is None else _positive_finite(remaining_s)
    backoff = _nonnegative_finite(backoff_s)
    valid = total is not None and remaining is not None and backoff is not None
    if not valid:
        return RetryBudget(0, 1, total, None, remaining, False, False)
    usable = min(total, remaining) - (backoff * retries)
    if usable <= 0.0:
        return RetryBudget(0, 1, total, None, remaining, False, False)
    attempt_s = min(total / attempts, usable / attempts)
    return RetryBudget(retries, attempts, total, attempt_s, remaining, True, retries > 0)


def apply_budget_to_proof(proof: ReplayProof, budget: RetryBudget) -> ReplayProof:
    """Invalid or zero retry sizing overrides otherwise valid replay proof."""
    return replace(proof, allow_retry=proof.allow_retry and budget.allow_retry)


def quota_failover_eligibility(
    current_quota_group: object,
    candidate_quota_groups: Iterable[object],
    opt_in_enabled: bool = False,
) -> FailoverEligibility:
    """Allow quota failover only to a different, non-empty quota group."""
    if opt_in_enabled is not True or not isinstance(current_quota_group, str):
        return FailoverEligibility(False)
    current = current_quota_group.strip()
    if not current:
        return FailoverEligibility(False)
    for candidate in candidate_quota_groups:
        if isinstance(candidate, str) and (group := candidate.strip()) and group != current:
            return FailoverEligibility(True, group)
    return FailoverEligibility(False)


def quota_failover_eligible(
    current_quota_group: object,
    candidate_quota_groups: Iterable[object],
    opt_in_enabled: bool = False,
) -> bool:
    """Boolean compatibility facade for quota failover selection."""
    return quota_failover_eligibility(
        current_quota_group, candidate_quota_groups, opt_in_enabled
    ).eligible


def _positive_finite(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    result = float(value)
    return result if result > 0.0 and math.isfinite(result) else None


def _nonnegative_finite(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    result = float(value)
    return result if result >= 0.0 and math.isfinite(result) else None


# Explicit aliases keep the universal policy easy to consume from thin facades.
compute_retry_budget = calculate_retry_budget
compute_attempt_budget = calculate_retry_budget
parse_bridge_retry_budget = parse_retry_budget
is_quota_failover_eligible = quota_failover_eligible
