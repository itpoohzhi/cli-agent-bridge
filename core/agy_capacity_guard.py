"""Fast-fail детектор исчерпания ёмкости upstream-модели (503 «No capacity available»).

Классифицирует строки stdout/stderr CLI, не зная о процессах. Env (читаются при вызове):
`AGY_FAST_FAIL_ON_CAPACITY_503` (kill-switch, `1`), `AGY_CAPACITY_MARKERS` (маркеры через запятую
вместо встроенных), `AGY_CAPACITY_MAX_LINE_CHARS` (анализируемая длина строки, 8192),
`AGY_CAPACITY_REDACT_WINDOW_CHARS` (окно маскирования секретов до усечения, 4096),
`AGY_CAPACITY_REDACT_MARGIN_CHARS` (минимальный запас окна поверх длины сводки, 512),
`AGY_CAPACITY_RAW_MAX_CHARS` (потолок сырого входа до нормализации, 32768; не меньше окна * 4),
`AGY_CAPACITY_SUMMARY_MAX_CHARS` (длина сводки в очереди и теле 503, 200).

Сводка строится конвейером `bound -> normalize -> redact -> clamp` в `summarize_capacity_text`:
сырой вход ограничивается потолком, пробелы схлопываются, берётся окно маскирования,
секреты маскируются и только затем результат усекается до длины сводки.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from typing import Final

from core.log_redaction import mask_credential_context, mask_long_tokens, safe_log_tokens

CAPACITY_REASON: Final[str] = "model_capacity_exhausted"
CAPACITY_HTTP_STATUS: Final[int] = 503
FAST_FAIL_ENV: Final[str] = "AGY_FAST_FAIL_ON_CAPACITY_503"
MARKERS_ENV: Final[str] = "AGY_CAPACITY_MARKERS"
MAX_LINE_CHARS_ENV: Final[str] = "AGY_CAPACITY_MAX_LINE_CHARS"
DEFAULT_MAX_LINE_CHARS: Final[int] = 8192
REDACT_WINDOW_CHARS_ENV: Final[str] = "AGY_CAPACITY_REDACT_WINDOW_CHARS"
DEFAULT_REDACT_WINDOW_CHARS: Final[int] = 4096
REDACT_MARGIN_CHARS_ENV: Final[str] = "AGY_CAPACITY_REDACT_MARGIN_CHARS"
DEFAULT_REDACT_MARGIN_CHARS: Final[int] = 512
RAW_MAX_CHARS_ENV: Final[str] = "AGY_CAPACITY_RAW_MAX_CHARS"
DEFAULT_RAW_MAX_CHARS: Final[int] = 32768
_RAW_WINDOW_FACTOR: Final[int] = 4
SUMMARY_MAX_CHARS_ENV: Final[str] = "AGY_CAPACITY_SUMMARY_MAX_CHARS"
DEFAULT_SUMMARY_MAX_CHARS: Final[int] = 200
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


def _positive_int_env(source: Mapping[str, str], name: str, default: int) -> int:
    try:
        value = int(str(source.get(name, "")).strip())
    except ValueError:
        return default
    return value if value > 0 else default


def summary_max_chars(env: Mapping[str, str] | None = None) -> int:
    """Предел длины сводки ошибки, уходящей в очередь и HTTP 503."""
    return _positive_int_env(os.environ if env is None else env, SUMMARY_MAX_CHARS_ENV, DEFAULT_SUMMARY_MAX_CHARS)


def redact_margin_chars(env: Mapping[str, str] | None = None) -> int:
    """Минимальный запас окна маскирования поверх предела сводки."""
    return _positive_int_env(os.environ if env is None else env, REDACT_MARGIN_CHARS_ENV, DEFAULT_REDACT_MARGIN_CHARS)


def redact_window_chars(env: Mapping[str, str] | None = None) -> int:
    """Окно входной строки, в котором ищутся секреты до усечения (предел сводки + запас)."""
    source = os.environ if env is None else env
    window = _positive_int_env(source, REDACT_WINDOW_CHARS_ENV, DEFAULT_REDACT_WINDOW_CHARS)
    return max(window, summary_max_chars(source) + redact_margin_chars(source))


def raw_max_chars(env: Mapping[str, str] | None = None) -> int:
    """Потолок сырого входа до схлопывания пробелов (не меньше окна маскирования * 4)."""
    source = os.environ if env is None else env
    raw = _positive_int_env(source, RAW_MAX_CHARS_ENV, DEFAULT_RAW_MAX_CHARS)
    return max(raw, redact_window_chars(source) * _RAW_WINDOW_FACTOR)


def summarize_capacity_text(text: object, redact: Callable[[str], str], env: Mapping[str, str] | None = None) -> str:
    """Конвейер bound -> normalize -> redact -> clamp: секрет на границе окна или сводки маскируется целиком."""
    source = os.environ if env is None else env
    # Пробелы схлопываются ДО среза окна: длинный пробельный префикс не должен резать токен на границе.
    normalized = " ".join(str(text or "")[: raw_max_chars(source)].split())
    return redact(normalized[: redact_window_chars(source)])[: summary_max_chars(source)]


def capacity_error_body(detail: object = "") -> dict[str, object]:
    """Тело ошибки: HTTP 503, `type` — код причины."""
    summary = summarize_capacity_text(
        detail,
        lambda s: mask_long_tokens(mask_credential_context(s), safe_tokens=safe_log_tokens()),
    )
    message = "upstream model has no capacity available"
    return {"message": f"{message}: {summary}" if summary else message, "type": CAPACITY_REASON, "code": CAPACITY_HTTP_STATUS}
