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
from types import MappingProxyType
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
_QUOTED_STOP_RE: Final[Mapping[str, re.Pattern[str]]] = MappingProxyType({
    '"': re.compile(r"[\\\"]"),
    "'": re.compile(r"[\\']"),
})
# Префикс секрета, которым заканчивается содержимое пары кавычек (`" truncated api_key="`): закрывающая
# кавычка пары на деле открывает значение этого префикса. `\Z` учитывает `endpos` поиска. Префикс вместе с
# кавычкой другого типа (`password='`) тоже хвостовой: кавычка уже открыла значение следующего секрета.
_TAIL_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:\b(?:bearer|basic)\s+|"
    + _CREDENTIAL_KEY_PREFIX_RE.pattern
    + r")(?P<glue>\\{0,%d}[\"'])?\Z" % _MAX_ESCAPE_LEVEL,
    re.IGNORECASE,
)
# Длина самого длинного префикса секрета в `_TAIL_PREFIX_RE` с запасом на пробелы вокруг разделителя.
_TAIL_PREFIX_SPAN: Final[int] = 64 + 16 + 3 * (_MAX_ESCAPE_LEVEL + 1) + 64
# Граница поля или строки: значение не начинается с неё.
_VALUE_BOUNDARY: Final[str] = ",;&}])"
_SPACES_RE: Final[re.Pattern[str]] = re.compile(r"\s*")
_QUOTES_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"[\\\"']*")
# Первый символ значения: не пробел и не граница поля/строки (`,;&}])` и кавычки).
_VALUE_START_RE: Final[re.Pattern[str]] = re.compile(r"[^\s,;&}\])\"']")
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


# Кавычка, которую отсечение хвостового префикса признало открывающей значение: (позиция значения за префиксом,
# позиция самой кавычки-открывающей). `(-1, -1)` — отсечения не было; позиции равны, если склейки нет.
_Approval = tuple[int, int]
_NO_APPROVAL: Final[_Approval] = (-1, -1)

# Стек открытых объемлющих строк: (кавычка, уровень экранирования серией `\`).
_QuoteFrame = tuple[str, int]


def _quote_run(text: str, pos: int) -> tuple[int, str]:
    """Конец серии `\\` от `pos` и символ сразу за ней (кавычка или пустая строка)."""
    end = _skip(_BACKSLASHES_RE, text, pos)
    return end, text[end : end + 1]


def _is_escaped_single(slashes: int) -> bool:
    """`'` после серии из `slashes` слэшей экранирован (нечётная серия) и строк не открывает и не закрывает."""
    return slashes % 2 != 0


def _closes_frame(level: int, slashes: int) -> bool:
    """Серия из `slashes` слэшей перед `"` закрывает строку уровня `level`.

    Кавычка уровня `L` закрывается серией, у которой остаток от деления на `2L+2` равен `L`
    (буквальная кавычка внутри — остаток `2L+1`, буквальный слэш — остаток `2L+2`).
    """
    return slashes % (2 * level + 2) == level


def _closing_index(stack: list[_QuoteFrame], quote: str, slashes: int) -> int | None:
    """Индекс кадра стека, который закрывает кавычка с серией `slashes`, иначе None.

    Кавычка ищет закрываемый кадр во всём стеке, а не только на вершине: серия может закрыть нижнюю строку
    поверх непарной вложенной (`\\"` внутри `"`), а непарная `"` внутри `'…'` не блокирует закрытие `'`.
    """
    if quote not in ('"', "'") or (quote == "'" and _is_escaped_single(slashes)):
        return None
    for index in range(len(stack) - 1, -1, -1):
        frame_quote, level = stack[index]
        if frame_quote != quote:
            continue
        if quote == "'" or _closes_frame(level, slashes):
            return index
    return None


def _closing_run(stack: list[_QuoteFrame], quote: str, slashes: int) -> int | None:
    """Длина закрывающей серии слэшей, если кавычка закрывает объемлющую строку, иначе None."""
    index = _closing_index(stack, quote, slashes)
    return None if index is None else stack[index][1]


def _closing_quote(
    text: str, pos: int, stack: list[_QuoteFrame]
) -> tuple[int, int] | None:
    """Кавычка в `pos` закрывает объемлющую строку: (конец серии слэшей, длина закрывающей серии)."""
    slashes_end, quote = _quote_run(text, pos)
    level = _closing_run(stack, quote, slashes_end - pos)
    return None if level is None else (slashes_end, level)


def _unwinds_inner_frames(text: str, pos: int, stack: list[_QuoteFrame]) -> bool:
    """Кавычка в `pos` закрывает объемлющую строку поверх незакрытых вложенных кадров (`'tis x=" y api_key='`)."""
    slashes_end, quote = _quote_run(text, pos)
    index = _closing_index(stack, quote, slashes_end - pos)
    return index is not None and index < len(stack) - 1


def _apply_double_quote(stack: list[_QuoteFrame], slashes: int) -> None:
    """`"` с серией `slashes`: закрывает объемлющую строку, открывает вложенную либо остаётся содержимым."""
    index = _closing_index(stack, '"', slashes)
    if index is not None:
        # Вместе с закрытой строкой уходят незакрытые вложенные кадры (`'…` или непарная `\"`).
        del stack[index:]
        return
    # Серия мельче уровня кадра закрыть его не может: кадр остался от несбалансированной кавычки.
    while stack and stack[-1][0] == '"' and stack[-1][1] >= slashes:
        stack.pop()
    if not stack:
        # Вне строки известны два уровня лога: обычная кавычка и однократно экранированная (`\"`).
        if slashes <= 1:
            stack.append(('"', slashes))
    elif slashes <= _MAX_ESCAPE_LEVEL:
        stack.append(('"', slashes))


def _apply_single_quote(stack: list[_QuoteFrame], prev: str, slashes: int = 0) -> None:
    """`'` закрывает открытую одиночную строку; вне слова открывает новую (апострофы `don't` — не кавычки)."""
    if _is_escaped_single(slashes):
        # Экранированный апостроф (`\'`) — содержимое строки, а не её граница.
        return
    index = _closing_index(stack, "'", 0)
    if index is not None:
        del stack[index:]
    elif not (prev.isalnum() or prev == "_") and (not stack or prev != "\\"):
        # Одиночная строка открывается и внутри двойной (`"msg='api_key=' password='x'"`).
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
                _apply_single_quote(stack, text[j - 1 : j], j - i)
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


def _find_enclosing_close(
    text: str, start: int, frame: _QuoteFrame, limit: int
) -> int | None:
    """Граница объемлющей строки `frame` (кавычка не включена) в `text[start:limit]`; None — закрытия нет.

    Неэкранированная `"` закрывает только строку уровня 0: в строке уровня `L` она — не закрытие.
    """
    quote, level = frame
    stop = _QUOTED_STOP_RE[quote]
    i = start
    while (match := stop.search(text, i, limit)) is not None:
        j = match.start()
        if text[j] != "\\":
            if text[j] == quote and level == 0:
                return j
            i = j + 1
            continue
        end = _skip(_BACKSLASHES_RE, text, j)
        if end >= limit:
            return None
        if text[end] != quote:
            i = end
            continue
        if _closes_frame(level, end - j):
            return end - level
        i = end + 1
    return None


def _enclosing_frames(stack: list[_QuoteFrame]) -> list[_QuoteFrame]:
    """Строки, границей которых ограничено значение: одиночная строка внутри двойной их не заменяет."""
    return [frame for frame in stack if frame != ("'", 0)] or stack[-1:]


def _nearest_close(
    text: str, start: int, frames: list[_QuoteFrame], limit: int
) -> int | None:
    """Ближайшая граница любой из объемлющих строк в `text[start:limit]`; None — ни одна не закрывается.

    Вложенный кадр не переживёт внешний: незакрытая вложенная кавычка (`\"` без пары) не должна прятать
    закрытие внешней строки. Каждый следующий поиск ограничен уже найденной границей.
    """
    best: int | None = None
    for frame in frames:
        close = _find_enclosing_close(text, start, frame, limit)
        if close is not None:
            best = close if best is None else min(best, close)
            limit = min(limit, close + frame[1] + 1)
    return best


def _enclosing_close(text: str, start: int, frames: list[_QuoteFrame]) -> int:
    """Граница консервативной маски незакрытого значения: объемлющая кавычка (не включая) либо конец текста."""
    close = _nearest_close(text, start, frames, len(text)) if frames else None
    return len(text) if close is None else close


def _content_end(pos: int, open_end: int, end: int) -> int:
    """Начало закрывающей кавычки пары `text[pos:end]` с открывающей кавычкой до `open_end`.

    Открывающая и закрывающая серии (`\\`×L + кавычка) имеют одну длину, поэтому содержимое кончается там же.
    """
    return end - (open_end - pos)


def _trim_tail_prefix(
    text: str, open_end: int, content_end: int, failed_until: _FailedUntil
) -> tuple[int, int] | None:
    """Начало префикса секрета и позиция его значения (первая кавычка за префиксом), иначе None.

    Префикс — хвост `text[open_end:content_end]`; значение начинается с кавычки-склейки (`api_key='"`), а не
    с закрывающей кавычки пары `content_end`: основной цикл сверяет её с позицией, где его regex кончает префикс.

    Строка `password=" truncated api_key="` образована кавычкой соседнего поля: её закрытие открывает значение
    `api_key=`, поэтому маска не должна его поглощать (иначе `hunter2` после неё остаётся открытым). Префикс
    разбирают заново, если кавычка за ним открывает значение; префиксы внутри этого значения и кавычка другого
    типа отсечению не мешают. Поиск ограничен хвостом длины префикса.
    """
    tail = _TAIL_PREFIX_RE.search(
        text, max(open_end, content_end - _TAIL_PREFIX_SPAN), content_end
    )
    if tail is None:
        return None
    # Без кавычки (конец текста) разбирать нечего: префикс остаётся без значения, а не поглощается маской.
    if content_end < len(text) and not _opens_value(text, content_end, failed_until):
        return None
    glue = tail.start("glue")
    return tail.start(), (content_end if glue < 0 else glue)


def _is_empty_pair(pos: int, open_end: int, end: int) -> bool:
    """Пара кавычек без содержимого (`""` или экранированная): прятать нечего."""
    return _content_end(pos, open_end, end) == open_end


def _is_quote_pair(text: str, pos: int, open_end: int, end: int) -> bool:
    """Пара без содержимого либо только из кавычек и слэшей (`'"'`, `\"`): крайние кавычки одного типа спарились
    вокруг кавычки другого типа.

    Значение продолжается за парой (`api_key='"'hunter2'`, в JSON-строке `api_key='"\"'hunter2'`). Проверка
    встаёт на первом символе, не являющемся кавычкой или слэшем, поэтому читает не больше содержимого пары.
    """
    return (
        _QUOTES_ONLY_RE.fullmatch(text, open_end, _content_end(pos, open_end, end))
        is not None
    )


def _cut_or(
    end: int, trimmed: tuple[int, int] | None, opener: int
) -> tuple[int, _Approval]:
    """Результат разбора: `end` без отсечения, иначе начало отсечённого префикса и одобрение его кавычки."""
    if trimmed is None:
        return end, _NO_APPROVAL
    cut, value_pos = trimmed
    return cut, (value_pos, opener)


def _scan_credential_value(
    text: str,
    pos: int,
    is_scheme: bool,
    failed_until: _FailedUntil,
    stack: list[_QuoteFrame],
) -> tuple[int, _Approval]:
    """Конец значения секрета в `pos` (`pos` — значения нет) и кавычка, признанная открывающей следующее значение.

    Второй элемент — `_Approval` кавычки, которую отсечение хвостового префикса (`password=" truncated api_key="`)
    уже разобрало как открывающую значение (`_NO_APPROVAL` — отсечения не было): пробел после неё не мешает
    значению, и основной цикл обязан судить её по той же семантике, иначе значение утечёт
    (`password=" trunc api_key=" x`, `msg='password=" trunc api_key=\'" x`).
    Каждый символ читается O(1) раз.

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
        return len(text), _NO_APPROVAL
    frames = _enclosing_frames(stack)
    start = pos
    end = _scan_quoted_value(text, pos, failed_until)
    open_quote_end = _open_quote_end(text, pos)
    hollow = True
    while end is not None and _is_quote_pair(text, pos, open_quote_end, end):
        # `api_key=""hunter2`, `api_key="""hunter2"""`, `api_key='"'hunter2'`: значение продолжается сразу за
        # пустой парой или парой из одних кавычек и слэшей (в том числе новой парой кавычек любого типа); иначе
        # прятать нечего, а такая пара — само значение.
        hollow = hollow and _is_empty_pair(pos, open_quote_end, end)
        if _quote_run(text, end)[1] in ('"', "'"):
            pos = end
            end = _scan_quoted_value(text, pos, failed_until)
            open_quote_end = _open_quote_end(text, pos)
            continue
        # Следом префикс другого секрета (`password=""api_key=`): он не значение, его разберёт основной цикл.
        if (
            _VALUE_START_RE.match(text, end) is None
            or _CREDENTIAL_PREFIX_RE.match(text, end) is not None
        ):
            return (start if hollow else end), _NO_APPROVAL
        if text[pos] in ('"', "'") and text[end - 1] in ('"', "'"):
            # Закрывающая кавычка пары на деле открывает закавыченное значение (`api_key='"'hunter2;x'`):
            # его разделители не обрывают маску. Чужой префикс внутри найденной пары означает рассинхронизацию
            # кавычек, как и «закрывающая» кавычка слитно со следующим значением (`api_key='"'hunter2 x='abc;def'`,
            # `api_key='"'hunter2 x="abc'def"`: пара кончается на кавычке чужого значения, хвост утёк бы), поэтому
            # такая пара не принимается. Fail-closed: без подходящей закрывающей кавычки (обрыв лога) значение
            # маскируется до границы объемлющей строки или конца текста.
            quoted = _scan_quoted_value(text, end - 1, failed_until)
            if (
                quoted is not None
                and _attached_value_start(text, quoted - 1) == 0
                and _CREDENTIAL_PREFIX_RE.search(text, end, quoted) is None
            ):
                return quoted, _NO_APPROVAL
            return _enclosing_close(text, end, frames), _NO_APPROVAL
        value_end = _skip(_SCHEME_VALUE_RE if is_scheme else _KEY_VALUE_RE, text, end)
        if value_end < len(text) and text[value_end] in ('"', "'"):
            # В JSON-строке `\` перед закрывающей кавычкой — экранирование, а не часть значения.
            while value_end > end and text[value_end - 1] == "\\":
                value_end -= 1
        return value_end, _NO_APPROVAL
    if end is None and 0 < open_quote_end < len(text):
        close = _enclosing_close(text, open_quote_end, frames)
        while close < len(text) and (after := _attached_value_start(text, close)):
            # Кавычка слитно со значением (`password='"hunter2"`) закрытием не бывает: значение идёт дальше.
            close = _enclosing_close(text, after, frames)
        return _cut_or(
            close, _trim_tail_prefix(text, open_quote_end, close, failed_until), close
        )
    paired = end is not None
    if end is None:
        end = _scan_unquoted(text, pos, is_scheme)
    if frames:
        # Значение не выходит за объемлющую строку: пара кавычек соседнего поля не поглощает его префикс.
        # Поиск ограничен `end`, поэтому суммарно читается не больше значения, которое уже разобрано.
        # Без префикса в поглощённой части границу не сужаем: хвост пары не разберёт никто, и он утёк бы.
        floor = open_quote_end or pos
        close = _nearest_close(text, floor, frames, end)
        while close is not None and (after := _attached_value_start(text, close)):
            # Как и у незакрытого значения: кавычка слитно со значением (`api_key="'hunter2' x=1`) закрытием
            # не бывает, граница маски уходит за слитное значение, а не остаётся перед ним.
            close = _nearest_close(text, after, frames, end)
        if close is not None and _CREDENTIAL_PREFIX_RE.search(text, close, end):
            return _cut_or(
                close, _trim_tail_prefix(text, floor, close, failed_until), close
            )
    if paired:
        content_end = _content_end(pos, open_quote_end, end)
        cut = _trim_tail_prefix(text, open_quote_end, content_end, failed_until)
        return _cut_or(end, cut, content_end)
    return end, _NO_APPROVAL


def _attached_value_start(text: str, pos: int) -> int:
    """Позиция значения, слитного с кавычкой в `pos` (без пробела и границы поля), иначе 0."""
    after = _open_quote_end(text, pos)
    if (
        0 < after < len(text)
        and not text[after].isspace()
        and text[after] not in _VALUE_BOUNDARY
    ):
        return after
    return 0


def _opens_value(
    text: str, pos: int, failed_until: _FailedUntil, spaced: bool = True
) -> bool:
    """Кавычка в `pos` открывает значение секрета, а не закрывает объемлющую строку.

    Закрытие не бывает слитно со значением: непарная кавычка, за которой идёт что угодно кроме границы поля,
    открывает значение (`api_key="'hunter2'`); с пробелом перед значением (`api_key=' hunter2`) — только при
    `spaced` (иначе `\\"api_key=\\" invalid` из JSON-строки превратилось бы в секрет). Пара, внутри
    которой есть чужой префикс, — закрытие, только если содержимое начинается с пробела или границы поля
    (`msg='api_key=' password='x'`); при значении без отступа префикс внутри значения не мешает
    (`api_key="hunter2 password=x"`). Пара без префиксов открывает значение всегда.
    """
    open_end = _open_quote_end(text, pos)
    paired = _scan_quoted_value(text, pos, failed_until)
    if paired is None:
        after = _skip(_SPACES_RE, text, open_end)
        if open_end == 0 or after >= len(text) or text[after] in _VALUE_BOUNDARY:
            return False
        # Кавычка после пробела — скорее граница соседней строки, чем начало значения (`Bearer \\" Bearer \\" "`).
        return after == open_end or (spaced and text[after] not in "\"'\\")
    if _CREDENTIAL_PREFIX_RE.search(text, open_end, paired) is None:
        return True
    first = text[open_end : open_end + 1]
    return not (first.isspace() or first in _VALUE_BOUNDARY)


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
    # Кавычка, которую отсечение хвостового префикса уже признало открывающей значение (см. `_scan_credential_value`).
    approved = _NO_APPROVAL
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
        if closing is not None and _opens_value(
            text,
            pos,
            failed_until,
            spaced=approved[0] == pos or _unwinds_inner_frames(text, pos, stack),
        ):
            closing = None
        if closing is None:
            prior = approved
            end, approved = _scan_credential_value(
                text, pos, value_is_scheme, failed_until, stack
            )
            if (
                end <= m.end()
                and prior[0] == pos
                and pos < prior[1] < len(text)
                and _closing_quote(text, prior[1], stack) is None
            ):
                # Склейка кавычек перед одобренной кавычкой (`api_key=\'" x` в `'…'`) значения не открывает:
                # значение начинает одобренная кавычка, иначе оно осталось бы вне маски.
                end, approved = _scan_credential_value(
                    text, prior[1], value_is_scheme, failed_until, stack
                )
        else:
            # Кавычка закрывает объемлющую строку: значением остаются только лишние слэши перед ней.
            end = closing[0] - closing[1]
            approved = _NO_APPROVAL
        # Цепочка без значения маскируется целиком: повторный разбор с каждого её звена был бы O(n^2).
        if end <= m.end():
            parts.append(text[cursor : m.end()])
            cursor = m.end()
            approved = _NO_APPROVAL
            continue
        start = (
            m.end("lead") if not is_scheme and _opens_enclosing_string(m) else m.start()
        )
        parts.append(text[cursor:start])
        parts.append(MASK)
        cursor = end
        if approved != _NO_APPROVAL:
            # Отсечённый префикс разбирается заново, поэтому учёт кавычек продолжается за маской: поглощённая ею
            # кавычка иначе перечитывается как открывающая, а кавычка нового значения — как её пара
            # (`password=" trunc api_key=" hunter2`).
            scanned = end
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
