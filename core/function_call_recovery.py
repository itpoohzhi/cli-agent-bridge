"""Распознавание исправимых ошибок functionCall с настраиваемым пределом текста."""

from __future__ import annotations

import re

from core.runtime_env import error_classify_max_chars

_FUNCTION_CALL_ERROR_PHRASES = (
    "malformed function call",
    "malformed_function_call",
    "pt_at_error",
    "function call is empty",
    "improperly formatted function call",
    "failed to parse function call",
)
FUNCTION_CALL_ERROR_RE = re.compile(
    "|".join(map(re.escape, _FUNCTION_CALL_ERROR_PHRASES)), re.IGNORECASE
)
FUNCTION_CALL_HEAL_REASON = "self_healed_after_malformed_function_call"


def is_recoverable_function_call_error(
    text: str | None, *, source: str = "cli_error"
) -> bool:
    """Распознаёт ошибку, не принимая решения о допустимости самоисцеления."""
    if not isinstance(text, str) or source != "cli_error":
        return False
    return bool(FUNCTION_CALL_ERROR_RE.search(text[: error_classify_max_chars()]))
