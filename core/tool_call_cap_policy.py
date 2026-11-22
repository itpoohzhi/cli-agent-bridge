"""Чистая Zero-I/O политика лимитов и graceful cap-cutoff вызовов инструментов (REQ-005)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CapAction = Literal["allow", "cap_cutoff", "limit_error"]
CapLimitKind = Literal["calls", "bytes"]


@dataclass(frozen=True, slots=True)
class ToolCallCapDecision:
    """Иммутабельное решение по лимиту числа вызовов или байтов хода."""

    action: CapAction
    limit_kind: CapLimitKind
    accept_count: int
    observed: int
    limit: int
    error_message: str = ""
    log_line: str = ""


def evaluate_call_cap(
    *,
    current_calls: int,
    incoming_calls: int,
    max_calls: int,
    cap_cutoff_enabled: bool,
) -> ToolCallCapDecision:
    """Оценивает лимит количества вызовов, включая частичный срез parallel-батча."""
    limit = int(max_calls)
    incoming = max(0, incoming_calls)
    observed = current_calls + incoming
    if observed <= limit:
        return ToolCallCapDecision("allow", "calls", incoming, observed, limit)
    if cap_cutoff_enabled and limit > 0:
        accept = max(0, limit - current_calls)
        accepted_total = current_calls + accept
        log_line = (
            f"tool_call_cap_cutoff kind=calls accepted={accepted_total}"
            f" observed={observed} limit={limit}"
        )
        return ToolCallCapDecision("cap_cutoff", "calls", accept, observed, limit, log_line=log_line)
    msg = f"tool call count exceeded limit ({limit})"
    log_line = f"tool_call_limit exceeded kind=calls observed={observed} limit={limit}"
    return ToolCallCapDecision("limit_error", "calls", 0, observed, limit, msg, log_line)


def evaluate_bytes_cap(
    *,
    current_bytes: int,
    chunk_bytes: int,
    max_bytes: int,
) -> ToolCallCapDecision:
    """Оценивает байтовый бюджет буфера tool-turn (fail-closed при лимите <= 0)."""
    limit = int(max_bytes)
    incoming = max(0, chunk_bytes)
    observed = current_bytes + incoming
    if observed <= limit:
        return ToolCallCapDecision("allow", "bytes", incoming, observed, limit)
    msg = f"tool call buffer exceeded max bytes ({limit})"
    log_line = f"tool_call_limit exceeded kind=bytes observed={observed} limit={limit}"
    return ToolCallCapDecision("limit_error", "bytes", 0, observed, limit, msg, log_line)
