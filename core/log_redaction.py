"""Редактирование секретов в логах без порчи кодов причин (`non_transient_result_error` и др.).

Маска длинных токенов с точным исключением известных кодов + маска по контексту
(`Bearer …`, `api_key=…`, `sk-…`). Расширение словаря — env `BRIDGE_LOG_SAFE_TOKENS`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from typing import Final

SAFE_TOKENS_ENV: Final[str] = "BRIDGE_LOG_SAFE_TOKENS"
MASK: Final[str] = "***"

# Литералы вместо импорта `core.agy_capacity_guard`/`core.stream_interruption_recovery`:
# редактор логов — листовой модуль и не зависит от доменных модулей. Синхронность с
# `TURN_REASON_CODES` и `CAPACITY_REASON` закреплена тестом.
SYSTEM_REASON_CODES: Final[frozenset[str]] = frozenset(
    (
        "clean_done",
        "self_healed_after_transient_interruption",
        "self_healed_after_malformed_function_call",
        "self_heal_disabled",
        "non_transient_result_error",
        "unclassified_nonzero_rc",
        "drain_incomplete",
        "unclosed_tool_call",
        "not_recovered",
        "transient_pre_delivery_retry",
        "retry_blocked",
        "graceful_partial_close",
        "graceful_blocked",
        "model_capacity_exhausted",
        "upstream_incomplete_stream",
        "upstream_repetition_loop",
        "upstream_response_too_large",
        "upstream_stream_error",
        "tool_call_parse_error",
        "live_prefix_invalidated",
    )
)

LONG_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_\-]{24,}")
_CREDENTIAL_KEYS: Final[str] = (
    r"(?:api[_-]?key|access[_-]?token|auth[_-]?token|refresh[_-]?token|client[_-]?secret|secret|password|passwd)"
)
# Значение в кавычках: символ, либо любая экранированная пара (`\"`, `\\`); JSON-строка внутри JSON
# (`\"…\\\"…\"`) разбирается отдельной веткой, где `\\\"` и `\\` — часть значения, а `\"` закрывает его.
# Та же ветка нужна и после `Bearer`/`Basic` (`json.dumps({"e": 'Bearer "tok"'})`).
_DQ_VALUE: Final[str] = r"\"(?:[^\"\\]|\\.)*\""
_SQ_VALUE: Final[str] = r"'(?:[^'\\]|\\.)*'"
# Серия `\` у кавычек ограничена (вложенность JSON ≤ 16): неограниченный `\\+` на закрытии даёт O(n^2) на длинной серии слэшей.
# Значение, экранированное L слэшами (`\"x\"` — L=1, JSON в JSON — L=3), закрывается ровно L слэшами; внутри него
# кавычка — 2L+1 слэшей, буквальный слэш — 2L+2. Поэтому `\\\"…\\\"\"` закрывается на `\\\"`, а внешняя `\"` остаётся нетронутой.
def _escaped_dq_value(group: str) -> str:
    level = "(?P=" + group + ")"
    return (
        r"(?P<" + group + r">\\{1,16})\"(?:[^\"\\]|" + level + level + r"\\\"|" + level + level + r"\\\\|\\{1,16}[^\"\\])*" + level + r"\""
    )


# Ключ может иметь префикс (`OPENAI_API_KEY`, `app_secret`, `openaiApiKey`): `_` входит в `\w`,
# поэтому `\b` перед именем ключа не подходит. Длина префикса ограничена: разбор линеен по входу.
_CREDENTIAL_CONTEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:bearer|basic)\s+(?:"
    + _escaped_dq_value("bq")
    + "|"
    + _DQ_VALUE
    + "|"
    + _SQ_VALUE
    + r"|\\*[\"']?[^\s,;\"']+)"
    # `(?<!\\)`: матч начинается только с начала серии `\`, иначе серия из n слэшей даёт O(n^2) на старте с каждой позиции.
    r"|(?<!\\)\\*[\"']?[A-Za-z0-9_\-]{0,64}" + _CREDENTIAL_KEYS + r"\b\\*[\"']?\s*[=:]\s*"
    r"(?:" + _DQ_VALUE + "|" + _SQ_VALUE + "|" + _escaped_dq_value("kq") + r"|\\*[\"']?[^\s,;&\"']+)"
)
_PREFIXED_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:sk|fk|rk|pk)-[A-Za-z0-9_\-]{6,}|\bgh[pousr]_[A-Za-z0-9]{8,}|\bAIza[A-Za-z0-9_\-]{8,}"
    r"|\bya29\.[A-Za-z0-9._\-]{8,}|\beyJ[A-Za-z0-9_\-]{4,}(?:\.[A-Za-z0-9_\-]+){1,2}"
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
