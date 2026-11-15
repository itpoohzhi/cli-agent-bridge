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
# Серия `\` у кавычек ограничена (вложенность JSON ≤ 16): `L` слэшей открывают и закрывают значение.
_MAX_ESCAPE_LEVEL: Final[int] = 16
# Регулярка находит только ПРЕФИКС (`Bearer `, `api_key=`), значение разбирает линейный сканер: значение
# в кавычках с откатом (backtracking) на незакрытых `\\<char>` даёт экспоненту. Ключ может иметь префикс
# (`OPENAI_API_KEY`, `openaiApiKey`): `_` входит в `\w`, поэтому `\b` перед именем ключа не подходит.
# `(?<!\\)`: матч начинается только с начала серии `\`, иначе серия из n слэшей даёт O(n^2) на старте с каждой позиции.
# `lead`/`trail` — кавычки вокруг имени ключа: если закрывающей кавычки нет, ведущая открывает значение
# объемлющей строки (`"api_key=x"`) и не входит в маску.
_CREDENTIAL_KEY_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<!\\)(?P<lead>\\*[\"']?)[A-Za-z0-9_\-]{0,64}"
    + _CREDENTIAL_KEYS
    + r"\b(?P<trail>\\{0,%d}[\"']?)\s*[=:]\s*" % _MAX_ESCAPE_LEVEL,
    re.IGNORECASE,
)
_CREDENTIAL_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?P<scheme>bearer|basic)\s+|" + _CREDENTIAL_KEY_PREFIX_RE.pattern, re.IGNORECASE
)
_BACKSLASHES_RE: Final[re.Pattern[str]] = re.compile(r"\\*")
_ESCAPE_OR_DQ_RE: Final[re.Pattern[str]] = re.compile(r"[\\\"]")
_QUOTED_STOP_RE: Final[dict[str, re.Pattern[str]]] = {
    '"': re.compile(r"[\\\"]"),
    "'": re.compile(r"[\\']"),
}
_SCHEME_VALUE_RE: Final[re.Pattern[str]] = re.compile(r"[^\s,;\"']*")
_KEY_VALUE_RE: Final[re.Pattern[str]] = re.compile(r"[^\s,;&\"']*")
_PREFIXED_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:sk|fk|rk|pk)-[A-Za-z0-9_\-]{6,}|\bgh[pousr]_[A-Za-z0-9]{8,}|\bAIza[A-Za-z0-9_\-]{8,}"
    r"|\bya29\.[A-Za-z0-9._\-]{8,}|\beyJ[A-Za-z0-9_\-]{4,}(?:\.[A-Za-z0-9_\-]+){1,2}"
)


def safe_log_tokens(extra: Iterable[str] = ()) -> frozenset[str]:
    """Коды причин + `BRIDGE_LOG_SAFE_TOKENS` + `extra`."""
    configured = frozenset(
        i.strip() for i in os.environ.get(SAFE_TOKENS_ENV, "").split(",")
    ) - {""}
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


_FailedUntil = dict[str | int, int]


def _scan_plain_quoted(text: str, pos: int, failed_until: _FailedUntil) -> int | None:
    """Значение в `"…"`/`'…'` с `\\x`-экранированием: позиция после закрывающей кавычки, None — не закрыто."""
    quote = text[pos]
    if pos + 1 <= failed_until.get(quote, -1):
        return None
    stop = _QUOTED_STOP_RE[quote]
    n = len(text)
    j = pos + 1
    while (m := stop.search(text, j)) is not None:
        j = m.start()
        if text[j] == quote:
            return j + 1
        j += 2
    failed_until[quote] = n
    return None


def _skip(pattern: re.Pattern[str], text: str, pos: int) -> int:
    match = pattern.match(text, pos)
    return match.end() if match else pos


def _scan_escaped_dq(text: str, pos: int, failed_until: _FailedUntil) -> int | None:
    """Значение, экранированное `L` слэшами (`\\"x\\"` — L=1, JSON в JSON — L=3).

    Закрывается ровно `L` слэшами и кавычкой; внутри кавычка — `2L+1` слэшей, буквальный слэш — `2L+2`.
    Поэтому серия слэшей перед кавычкой классифицируется по остатку от деления на `2L+2`.
    """
    n = len(text)
    k = pos
    stop = min(n, pos + _MAX_ESCAPE_LEVEL + 1)
    while k < stop and text[k] == "\\":
        k += 1
    level = k - pos
    if (
        not 1 <= level <= _MAX_ESCAPE_LEVEL
        or k >= n
        or text[k] != '"'
        or k + 1 <= failed_until.get(level, -1)
    ):
        return None
    j = k + 1
    while (m := _ESCAPE_OR_DQ_RE.search(text, j)) is not None:
        j = m.start()
        if text[j] == '"':
            break
        j = _skip(_BACKSLASHES_RE, text, j)
        if j >= n or text[j] != '"':
            continue
        rem = (j - m.start()) % (2 * level + 2)
        if rem == level:
            return j + 1
        if rem != 2 * level + 1:
            break
        j += 1
    else:
        j = n
    failed_until[level] = j
    return None


def _scan_unquoted(text: str, pos: int, is_scheme: bool) -> int:
    """Значение без парных кавычек: серия `\\`, необязательная кавычка и хотя бы один символ значения.

    Нет символа значения — значением считается сама серия `\\` (как при откате прежнего regex).
    """
    slashes_end = _skip(_BACKSLASHES_RE, text, pos)
    u = (
        slashes_end + 1
        if text[slashes_end : slashes_end + 1] in ('"', "'")
        else slashes_end
    )
    end = _skip(_SCHEME_VALUE_RE if is_scheme else _KEY_VALUE_RE, text, u)
    if u == pos and end < len(text) and text[end] in ('"', "'"):
        # В JSON-строке `\` перед закрывающей кавычкой — экранирование, а не часть значения.
        while end > u and text[end - 1] == "\\":
            end -= 1
    if end > u:
        return end
    # Серия `\` перед кавычкой без значения экранирует эту кавычку, а не является значением.
    return slashes_end if u == slashes_end else pos


def _scan_quoted_value(text: str, pos: int, failed_until: _FailedUntil) -> int | None:
    """Конец значения в парных кавычках (обычных или `\\"`-экранированных); None — значение не закавычено."""
    if pos >= len(text):
        return None
    if text[pos] in "\"'":
        return _scan_plain_quoted(text, pos, failed_until)
    return _scan_escaped_dq(text, pos, failed_until)


def _scan_credential_value(
    text: str, pos: int, is_scheme: bool, failed_until: _FailedUntil
) -> int:
    """Конец значения секрета, начинающегося в `pos`; `pos` — значения нет. Каждый символ читается O(1) раз.

    `failed_until` запоминает, до какой позиции разбор данного типа кавычек уже провалился: следующая
    кавычка того же типа внутри этой зоны не перечитывается, поэтому суммарно разбор линеен по входу.
    """
    end = _scan_quoted_value(text, pos, failed_until)
    return end if end is not None else _scan_unquoted(text, pos, is_scheme)


def _opens_enclosing_string(m: re.Match[str]) -> bool:
    """Ключ без закрывающей кавычки после имени: ведущая кавычка принадлежит объемлющей строке."""
    quotes = ('"', "'")
    return m.group("lead").endswith(quotes) and not m.group("trail").endswith(quotes)


def mask_credential_context(text: str) -> str:
    """Маска секретов по контексту (`Bearer x`, `api_key=x`, `sk-…`) любой длины; разбор линейный."""
    parts: list[str] = []
    cursor = 0
    failed_until: _FailedUntil = {}
    # Поиск идёт от `cursor`, как у `re.sub`: значение уже разобрано, и префиксы внутри него не ищутся.
    while (m := _CREDENTIAL_PREFIX_RE.search(text, cursor)) is not None:
        is_scheme = m.group("scheme") is not None
        # `Bearer password=x`, `secret: api_key=x`: значение секрета — после последнего префикса цепочки,
        # а не имя ключа. Каждый шаг цепочки сдвигает позицию вперёд, поэтому разбор остаётся линейным.
        pos, value_is_scheme = m.end(), is_scheme
        while (nxt := _CREDENTIAL_PREFIX_RE.match(text, pos)) is not None:
            # Префикс целиком внутри парных кавычек (`"password=a b"`) — часть значения: его не вскрываем.
            quoted_end = _scan_quoted_value(text, pos, failed_until)
            if quoted_end is not None and nxt.end() < quoted_end:
                break
            pos, value_is_scheme = nxt.end(), nxt.group("scheme") is not None
        # Цепочка без значения маскируется целиком: повторный разбор с каждого её звена был бы O(n^2).
        end = max(_scan_credential_value(text, pos, value_is_scheme, failed_until), pos)
        if end <= m.end():
            parts.append(text[cursor : m.end()])
            cursor = m.end()
            continue
        start = (
            m.end("lead") if not is_scheme and _opens_enclosing_string(m) else m.start()
        )
        parts.append(text[cursor:start])
        parts.append(MASK)
        cursor = end
    parts.append(text[cursor:])
    return _PREFIXED_TOKEN_RE.sub(MASK, "".join(parts))


def redact_log_text(
    text: str, *, extra_safe_tokens: Iterable[str] | None = None
) -> str:
    """Единый конвейер редактирования логов: секреты по контексту, затем длинные токены (кроме кодов причин)."""
    safe = safe_log_tokens(extra_safe_tokens or ())
    return mask_long_tokens(mask_credential_context(text), safe_tokens=safe)
