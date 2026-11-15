"""Редактирование секретов в логах без порчи кодов причин (`non_transient_result_error` и др.).

Маска длинных токенов с точным исключением известных кодов + маска по контексту
(`Bearer …`, `api_key=…`, `sk-…`). Расширение словаря — env `BRIDGE_LOG_SAFE_TOKENS`.
Объемлющая строка и уровень её экранирования слэшами отслеживаются монотонно: закрывающая
кавычка не открывает значение следующего ключа, а незакрытое значение маскируется до её закрытия.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
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


def safe_log_tokens(
    extra: Iterable[str] = (), *, env: Mapping[str, str] | None = None
) -> frozenset[str]:
    """Коды причин + `BRIDGE_LOG_SAFE_TOKENS` + `extra`; `env` — источник настройки (дефолт — окружение процесса)."""
    source = os.environ if env is None else env
    configured = frozenset(
        i.strip() for i in source.get(SAFE_TOKENS_ENV, "").split(",")
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


# Стек открытых объемлющих строк: (кавычка, уровень экранирования серией `\`).
_QuoteFrame = tuple[str, int]


def _quote_run(text: str, pos: int) -> tuple[int, str]:
    """Конец серии `\\` от `pos` и символ сразу за ней (кавычка или пустая строка)."""
    end = _skip(_BACKSLASHES_RE, text, pos)
    return end, text[end : end + 1]


def _closing_run(stack: list[_QuoteFrame], quote: str, slashes: int) -> int | None:
    """Длина закрывающей серии слэшей, если кавычка закрывает верхнюю объемлющую строку, иначе None.

    Кавычка уровня `L` закрывается серией из `L` слэшей, когда длина серии кратна `2L+2`
    (буквальная кавычка внутри — остаток `2L+1`, буквальный слэш — остаток `2L+2`).
    """
    if not stack:
        return None
    top_quote, level = stack[-1]
    if quote != top_quote or slashes % (2 * level + 2) != level:
        return None
    return level


def _closing_quote(
    text: str, pos: int, stack: list[_QuoteFrame]
) -> tuple[int, int] | None:
    """Кавычка в `pos` закрывает объемлющую строку: (конец серии слэшей, длина закрывающей серии)."""
    slashes_end, quote = _quote_run(text, pos)
    level = _closing_run(stack, quote, slashes_end - pos)
    return None if level is None else (slashes_end, level)


def _apply_double_quote(stack: list[_QuoteFrame], slashes: int) -> None:
    """`"` с серией `slashes`: закрывает объемлющую строку, открывает вложенную либо остаётся содержимым."""
    while stack and stack[-1][0] == '"':
        level = stack[-1][1]
        if slashes % (2 * level + 2) == level:
            stack.pop()
            return
        if slashes > level:
            break
        # Серия мельче уровня кадра закрыть его не может: кадр остался от несбалансированной кавычки.
        stack.pop()
    if not stack:
        # Вне строки известны два уровня лога: обычная кавычка и однократно экранированная (`\"`).
        if slashes <= 1:
            stack.append(('"', slashes))
    elif slashes <= _MAX_ESCAPE_LEVEL:
        stack.append(('"', slashes))


def _apply_single_quote(stack: list[_QuoteFrame], prev: str) -> None:
    """`'` закрывает открытую одиночную строку; вне слова открывает новую (апострофы `don't` — не кавычки)."""
    if stack and stack[-1] == ("'", 0):
        stack.pop()
    elif not stack and not (prev.isalnum() or prev == "_"):
        stack.append(("'", 0))


def _track_quotes(text: str, start: int, end: int, stack: list[_QuoteFrame]) -> None:
    """Монотонно (каждый символ читается один раз) отследить открытые объемлющие строки в `text[start:end]`."""
    i = start
    while i < end:
        char = text[i]
        if char == "\\":
            j = i
            while j < end and text[j] == "\\":
                j += 1
            if j >= end:
                i = j
            elif text[j] == '"':
                _apply_double_quote(stack, j - i)
                i = j + 1
            elif text[j] == "'":
                # Экранированный апостроф (`\'`) — содержимое строки, а не её граница.
                if (j - i) % 2 == 0:
                    _apply_single_quote(stack, text[j - 1 : j])
                i = j + 1
            else:
                i = j
            continue
        if char == '"':
            _apply_double_quote(stack, 0)
        elif char == "'":
            _apply_single_quote(stack, text[i - 1 : i])
        i += 1


def _open_quote_end(text: str, pos: int) -> int:
    """Позиция сразу после открывающей кавычки значения в `pos`; 0 — открывающей кавычки нет."""
    if text[pos : pos + 1] in ('"', "'"):
        return pos + 1
    slashes_end, quote = _quote_run(text, pos)
    if quote == '"' and 1 <= slashes_end - pos <= _MAX_ESCAPE_LEVEL:
        return slashes_end + 1
    return 0


def _enclosing_close(text: str, start: int, frame: _QuoteFrame | None) -> int:
    """Граница консервативной маски незакрытого значения: объемлющая кавычка (не включая) либо конец текста."""
    if frame is None:
        return len(text)
    quote, level = frame
    stop = _QUOTED_STOP_RE[quote]
    i = start
    while (match := stop.search(text, i)) is not None:
        j = match.start()
        if text[j] != "\\":
            if text[j] == quote:
                return j
            i = j + 1
            continue
        end = _skip(_BACKSLASHES_RE, text, j)
        if text[end : end + 1] != quote:
            i = end
            continue
        if (end - j) % (2 * level + 2) == level:
            return end - level
        i = end + 1
    return len(text)


def _scan_credential_value(
    text: str,
    pos: int,
    is_scheme: bool,
    failed_until: _FailedUntil,
    stack: list[_QuoteFrame],
) -> int:
    """Конец значения секрета, начинающегося в `pos`; `pos` — значения нет. Каждый символ читается O(1) раз.

    `failed_until` запоминает, до какой позиции разбор данного типа кавычек уже провалился: следующая
    кавычка того же типа внутри этой зоны не перечитывается, поэтому суммарно разбор линеен по входу.
    Закрывающая кавычка значения может быть отсечена окном или потоком — тогда значение маскируется
    консервативно до конца объемлющей строки: обрывок секрета не должен попасть в сводку.
    """
    slashes_end, quote = _quote_run(text, pos)
    slashes = slashes_end - pos
    if quote == '"' and 1 < slashes <= _MAX_ESCAPE_LEVEL and not stack:
        # Вне объемлющей строки серия из двух и более `\` не даёт достоверной пары кавычек: парная кавычка
        # нашлась бы у следующего ключа (`password=\"..."` в логе уровня 2), поэтому маскируется весь остаток.
        return len(text)
    end = _scan_quoted_value(text, pos, failed_until)
    if end is not None:
        return end
    open_quote_end = _open_quote_end(text, pos)
    if 0 < open_quote_end < len(text):
        return _enclosing_close(text, open_quote_end, stack[-1] if stack else None)
    return _scan_unquoted(text, pos, is_scheme)


def _opens_enclosing_string(m: re.Match[str]) -> bool:
    """Ключ без закрывающей кавычки после имени: ведущая кавычка принадлежит объемлющей строке."""
    quotes = ('"', "'")
    return m.group("lead").endswith(quotes) and not m.group("trail").endswith(quotes)


def mask_credential_context(text: str) -> str:
    """Маска секретов по контексту (`Bearer x`, `api_key=x`, `sk-…`) любой длины; разбор линейный."""
    parts: list[str] = []
    cursor = 0
    # Позиция, до которой стек объемлющих кавычек уже просмотрен: каждый символ входа читается один раз.
    scanned = 0
    stack: list[_QuoteFrame] = []
    failed_until: _FailedUntil = {}
    # Поиск идёт от `cursor`, как у `re.sub`: значение уже разобрано, и префиксы внутри него не ищутся.
    while (m := _CREDENTIAL_PREFIX_RE.search(text, cursor)) is not None:
        is_scheme = m.group("scheme") is not None
        # `Bearer password=x`, `secret: api_key=x`: значение секрета — после последнего префикса цепочки,
        # а не имя ключа. Каждый шаг цепочки сдвигает позицию вперёд, поэтому разбор остаётся линейным.
        pos, value_is_scheme = m.end(), is_scheme
        while (nxt := _CREDENTIAL_PREFIX_RE.match(text, pos)) is not None:
            _track_quotes(text, scanned, pos, stack)
            scanned = pos
            # Закрывающая кавычка объемлющей строки не открывает значение следующего звена цепочки.
            if _closing_quote(text, pos, stack) is not None:
                break
            # Префикс целиком внутри парных кавычек (`"password=a b"`) — часть значения: его не вскрываем.
            quoted_end = _scan_quoted_value(text, pos, failed_until)
            if quoted_end is not None and nxt.end() < quoted_end:
                break
            pos, value_is_scheme = nxt.end(), nxt.group("scheme") is not None
        _track_quotes(text, scanned, pos, stack)
        scanned = pos
        closing = _closing_quote(text, pos, stack)
        if closing is None:
            end = _scan_credential_value(
                text, pos, value_is_scheme, failed_until, stack
            )
        else:
            # Кавычка закрывает объемлющую строку: значением остаются только лишние слэши перед ней.
            end = closing[0] - closing[1]
        # Цепочка без значения маскируется целиком: повторный разбор с каждого её звена был бы O(n^2).
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
    text: str,
    *,
    extra_safe_tokens: Iterable[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """Единый конвейер редактирования логов: секреты по контексту, затем длинные токены (кроме кодов причин)."""
    safe = safe_log_tokens(extra_safe_tokens or (), env=env)
    return mask_long_tokens(mask_credential_context(text), safe_tokens=safe)
