"""Редактирование секретов в логах без порчи кодов причин (`non_transient_result_error` и др.).

Маска длинных токенов с точным исключением известных кодов + маска по контексту
(`Bearer …`, `api_key=…`, `sk-…`). Расширение словаря — env `BRIDGE_LOG_SAFE_TOKENS`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from typing import Final

from core.agy_capacity_guard import CAPACITY_REASON
from core.stream_interruption_recovery import TURN_REASON_CODES

SAFE_TOKENS_ENV: Final[str] = "BRIDGE_LOG_SAFE_TOKENS"
MASK: Final[str] = "***"

SYSTEM_REASON_CODES: Final[frozenset[str]] = frozenset(
    (
        *TURN_REASON_CODES,
        CAPACITY_REASON,
        "upstream_incomplete_stream",
        "upstream_repetition_loop",
        "upstream_response_too_large",
        "upstream_stream_error",
        "tool_call_parse_error",
        "live_prefix_invalidated",
    )
)

LONG_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_\-]{24,}")
_CREDENTIAL_CONTEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:bearer|basic)\s+[^\s,;\"']+"
    r"|\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|refresh[_-]?token|client[_-]?secret|secret|password|passwd)"
    r"\b\s*[=:]\s*[^\s,;&\"']+"
)
_PREFIXED_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:sk|fk|rk|pk)-[A-Za-z0-9_\-]{6,}|\bgh[pousr]_[A-Za-z0-9]{8,}|\bAIza[A-Za-z0-9_\-]{8,}|\bya29\.[A-Za-z0-9._\-]{8,}"
)


def safe_log_tokens(extra: Iterable[str] = ()) -> frozenset[str]:
    """Коды причин + `BRIDGE_LOG_SAFE_TOKENS` + `extra`."""
    configured = frozenset(i.strip() for i in os.environ.get(SAFE_TOKENS_ENV, "").split(",")) - {""}
    return SYSTEM_REASON_CODES | configured | frozenset(extra)


def mask_long_tokens(
    text: str,
    pattern: re.Pattern[str] = LONG_TOKEN_RE,
    safe_tokens: frozenset[str] | None = None,
) -> str:
    """Заменить совпадения `pattern` на `***`, кроме `safe_tokens`."""
    safe = safe_log_tokens() if safe_tokens is None else safe_tokens

    def _sub(match: re.Match[str]) -> str:
        token = match.group(0)
        return token if token in safe else MASK

    return pattern.sub(_sub, text)


def mask_credential_context(text: str) -> str:
    """Маска секретов по контексту (`Bearer x`, `api_key=x`, `sk-…`) любой длины."""
    masked = _CREDENTIAL_CONTEXT_RE.sub(MASK, text)
    return _PREFIXED_TOKEN_RE.sub(MASK, masked)
