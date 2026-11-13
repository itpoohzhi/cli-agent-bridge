"""Fast-fail детектор исчерпания ёмкости upstream-модели (503 «No capacity available»).

Классифицирует строки stdout/stderr CLI, не зная о процессах. Env (читаются при вызове):
`AGY_FAST_FAIL_ON_CAPACITY_503` (kill-switch, `1`), `AGY_CAPACITY_MARKERS` (маркеры через запятую
вместо встроенных), `AGY_CAPACITY_MAX_LINE_CHARS` (анализируемая длина строки, 8192).
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Final

from core.log_redaction import mask_credential_context, mask_long_tokens, safe_log_tokens

CAPACITY_REASON: Final[str] = "model_capacity_exhausted"
CAPACITY_HTTP_STATUS: Final[int] = 503
FAST_FAIL_ENV: Final[str] = "AGY_FAST_FAIL_ON_CAPACITY_503"
MARKERS_ENV: Final[str] = "AGY_CAPACITY_MARKERS"
MAX_LINE_CHARS_ENV: Final[str] = "AGY_CAPACITY_MAX_LINE_CHARS"
DEFAULT_MAX_LINE_CHARS: Final[int] = 8192
_FALSE: Final[frozenset[str]] = frozenset(("0", "false", "no", "off"))
# Встроенные маркеры ёмкости требуют признак статуса/ошибки: голая проза с кодом причины
# в stdout не должна убивать процесс. Явный `AGY_CAPACITY_MARKERS` признак не требует.
_CAPACITY_CODE: Final[str] = "model_capacity_exhausted"
_CAPACITY_PHRASE: Final[str] = "no capacity available"
# `error`/`status`/`code` считаются признаком только как ключ или префикс (`error:`, `"code":`), не как слово прозы.
_STATUS_HINT_RE: Final[re.Pattern[str]] = re.compile(r"\b503\b|unavailable|resource_exhausted|\b(?:error|status|code)\b[\"']?\s*[:=]")


def fast_fail_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Включён ли fast-fail (дефолт — да)."""
    source = os.environ if env is None else env
    return str(source.get(FAST_FAIL_ENV, "1")).strip().lower() not in _FALSE


def _max_line_chars(source: Mapping[str, str]) -> int:
    try:
        value = int(str(source.get(MAX_LINE_CHARS_ENV, "")).strip())
    except ValueError:
        return DEFAULT_MAX_LINE_CHARS
    return value if value > 0 else DEFAULT_MAX_LINE_CHARS


def _custom_markers(source: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(i.strip().lower() for i in str(source.get(MARKERS_ENV, "")).split(",") if i.strip())


def is_capacity_exhausted_text(text: object, env: Mapping[str, str] | None = None) -> bool:
    """Строка CLI сообщает об исчерпании ёмкости (без kill-switch)."""
    if not isinstance(text, str) or not text:
        return False
    source = os.environ if env is None else env
    haystack = text[: _max_line_chars(source)].lower()
    custom = _custom_markers(source)
    if custom:
        return any(marker in haystack for marker in custom)
    if _CAPACITY_CODE not in haystack and _CAPACITY_PHRASE not in haystack:
        return False
    return _STATUS_HINT_RE.search(haystack) is not None


def should_fast_fail_agy_capacity_503(text: object, env: Mapping[str, str] | None = None) -> bool:
    """Строка — capacity-503, ход нужно прервать."""
    return fast_fail_enabled(env) and is_capacity_exhausted_text(text, env)


def capacity_error_body(detail: object = "") -> dict[str, object]:
    """Тело ошибки: HTTP 503, `type` — код причины."""
    # Маскирование до усечения: обрезанный посередине токен уже не распознать.
    redacted = mask_long_tokens(mask_credential_context(" ".join(str(detail or "").split())), safe_tokens=safe_log_tokens())
    summary = redacted[:200]
    message = "upstream model has no capacity available"
    return {"message": f"{message}: {summary}" if summary else message, "type": CAPACITY_REASON, "code": CAPACITY_HTTP_STATUS}
