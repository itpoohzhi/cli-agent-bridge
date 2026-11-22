"""Чистый Zero-I/O разбор блоков `<tool_call>`, линейный курсор закрытия и диагностика."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, cast

from core.tool_json_repair import repair_invalid_json_escapes, repair_unescaped_json_quotes, resolve_odd_quote_tool_close

_DEFAULT_CLOSE_TAG: Final[str] = "</tool_call>"
_DEFAULT_MAX_EXTRA_BRACES: Final[int] = 16
_DEFAULT_WINDOW_CHARS: Final[int] = 120
_DEFAULT_REDACT_MARGIN_CHARS: Final[int] = 2048
_STRING_STOP_RE: Final[re.Pattern[str]] = re.compile(r'["\\]')
_OUTSIDE_STOP_RE: Final[re.Pattern[str]] = re.compile(r'["<]')


def _append_in_string_escape(text: str, index: int, out: list[str]) -> int:
    if index + 1 >= len(text):
        out.append(text[index])
        return index + 1
    nxt = text[index + 1]
    out.append("'" if nxt == "'" else text[index : index + 2])
    return index + 2


def repair_invalid_single_quote_escape(text: str) -> str:
    """Заменяет невалидное JSON-экранирование `\\'` на `'` только внутри JSON-строк."""
    if "\\'" not in text:
        return text
    out: list[str] = []
    in_string = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string and ch == "\\":
            i = _append_in_string_escape(text, i, out)
            continue
        out.append(ch)
        if ch == '"':
            in_string = not in_string
        i += 1
    return "".join(out)


def _is_trailing_comma(text: str, comma_pos: int) -> bool:
    j = comma_pos + 1
    n = len(text)
    while j < n and text[j] in " \t\r\n":
        j += 1
    return j < n and text[j] in "}]"


def _step_string_state(ch: str, escaped: bool) -> tuple[bool, bool]:
    if escaped:
        return False, True
    if ch == "\\":
        return True, True
    return False, ch != '"'


def _strip_trailing_commas(text: str) -> str:
    """Удаляет висячие запятые перед `}` и `]` только вне строковых литералов."""
    if "," not in text:
        return text
    out: list[str] = []
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            out.append(ch)
            escaped, in_string = _step_string_state(ch, escaped)
            continue
        if ch == "," and _is_trailing_comma(text, i):
            continue
        if ch == '"':
            in_string = True
        out.append(ch)
    return "".join(out)


def recover_trailing_braces(
    text: str,
    *,
    max_extra_braces: int = _DEFAULT_MAX_EXTRA_BRACES,
) -> dict[str, object] | None:
    """Первый JSON-объект, за которым идут только пробелы и 1..N лишних `}`; иначе None."""
    body = text.lstrip()
    try:
        obj, end = cast("tuple[object, int]", json.JSONDecoder(strict=False).raw_decode(body))
    except (ValueError, RecursionError):
        return None
    tail = body[end:]
    if (
        isinstance(obj, dict)
        and 1 <= tail.count("}") <= max_extra_braces
        and not tail.strip(" \t\r\n}")
    ):
        return cast("dict[str, object]", obj)
    return None


def _try_loads(text: str) -> tuple[bool, object]:
    try:
        return True, cast("object", json.loads(text, strict=False))
    except (ValueError, RecursionError):
        return False, None


def _recover_after_repair(candidate: str) -> tuple[bool, object]:
    cleaned = _strip_trailing_commas(candidate)
    if cleaned != candidate:
        ok, parsed = _try_loads(cleaned)
        if ok:
            return True, parsed
        recovered = recover_trailing_braces(cleaned)
        if recovered is not None:
            return True, recovered
    recovered = recover_trailing_braces(candidate)
    if recovered is not None:
        return True, recovered
    return False, None


def _try_candidate(candidate: str) -> tuple[bool, object]:
    ok, parsed = _try_loads(candidate)
    return (True, parsed) if ok else _recover_after_repair(candidate)


def loads_tolerant_json(
    text: str, *, json_repair_enabled: bool = False,
    allowed_arg_keys: frozenset[str] | None = None, required_arg_keys: frozenset[str] | None = None,
) -> object:
    """Единый толерантный JSON-конвейер: strict -> escape-repair -> opt-in quote-repair -> trailing."""
    try:
        return cast("object", json.loads(text, strict=False))
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, RecursionError):
            raise ValueError("JSON is nested too deeply") from exc
        escaped = repair_invalid_json_escapes(text) if json_repair_enabled else repair_invalid_single_quote_escape(text)
        ok, parsed = _try_candidate(escaped)
        if ok:
            return parsed
        if json_repair_enabled:
            quoted = repair_unescaped_json_quotes(
                escaped, allowed_arg_keys=allowed_arg_keys, required_arg_keys=required_arg_keys
            )
            if quoted is not None:
                ok, parsed = _try_candidate(repair_invalid_json_escapes(quoted))
                if ok:
                    return parsed
        raise


@dataclass(slots=True)
class ToolCloseCursor:
    """Инкрементальный однопроходный курсор поиска `</tool_call>` вне JSON-строк."""

    close_tag: str = _DEFAULT_CLOSE_TAG
    start: int = 0
    pos: int = 0
    in_string: bool = False
    escaped: bool = False
    found: int = -1

    def find_close(self, buf: str, start: int = 0) -> int:
        """Возвращает индекс закрывающего тега вне JSON-строки или -1 при ожидании данных."""
        return advance_tool_close_scan(self, buf, start=start)


def _scan_in_string(buf: str, pos: int, escaped: bool) -> tuple[int, bool, bool]:
    n = len(buf)
    if escaped and pos < n:
        escaped = False
        pos += 1
    while pos < n:
        match = _STRING_STOP_RE.search(buf, pos)
        if match is None:
            return n, True, False
        j = match.start()
        if buf[j] == '"':
            return j + 1, False, False
        if j + 1 < n:
            pos = j + 2
        else:
            return n, True, True
    return n, True, escaped


def _outside_stop_pattern(close_tag: str) -> re.Pattern[str]:
    if not close_tag or close_tag.startswith("<"):
        return _OUTSIDE_STOP_RE
    return re.compile('["' + re.escape(close_tag[0]) + "]")


def _scan_outside_string(buf: str, pos: int, close_tag: str) -> tuple[int, bool, int]:
    n = len(buf)
    tag_len = len(close_tag)
    pattern = _outside_stop_pattern(close_tag)
    while pos < n:
        match = pattern.search(buf, pos)
        if match is None:
            return n, False, -1
        j = match.start()
        if buf[j] == '"':
            return j + 1, True, -1
        if tag_len and buf.startswith(close_tag, j):
            return j, False, j
        if n - j < tag_len and close_tag.startswith(buf[j:]):
            return j, False, -1
        pos = j + 1
    return n, False, -1


def advance_tool_close_scan(cursor: ToolCloseCursor, buf: str, start: int = 0) -> int:
    """Инкрементально продвигает курсор `cursor` по `buf` за амортизированное время O(N)."""
    if start != cursor.start or len(buf) < cursor.pos or cursor.pos < start:
        cursor.start = start
        cursor.pos = start
        cursor.in_string = False
        cursor.escaped = False
        cursor.found = -1
    if cursor.found != -1 and buf.startswith(cursor.close_tag, cursor.found):
        return cursor.found
    cursor.found = -1
    n = len(buf)
    while cursor.pos < n:
        if cursor.in_string:
            cursor.pos, cursor.in_string, cursor.escaped = _scan_in_string(
                buf, cursor.pos, cursor.escaped
            )
            continue
        cursor.pos, cursor.in_string, found = _scan_outside_string(
            buf, cursor.pos, cursor.close_tag
        )
        if found != -1:
            cursor.found = found
            return found
        if not cursor.in_string:
            return -1
    return -1


def find_tool_close_outside_string(
    text: str,
    start: int = 0,
    close_tag: str = _DEFAULT_CLOSE_TAG,
) -> int:
    """Позиция `</tool_call>` вне строковых литералов JSON в `text[start:]`, или -1."""
    cursor = ToolCloseCursor(close_tag=close_tag, start=start, pos=start)
    return advance_tool_close_scan(cursor, text, start=start)


def format_malformed_tool_block_log(
    raw_block: str,
    *,
    err_pos: int | None = None,
    window_chars: int = _DEFAULT_WINDOW_CHARS,
    redact_margin_chars: int = _DEFAULT_REDACT_MARGIN_CHARS,
    redact_fn: Callable[[str], str] | None = None,
) -> str:
    """Редактирует O(1)-окрестность `err_pos` без инъекции sentinel и режет окно."""
    pos = max(0, min(len(raw_block), 0 if err_pos is None else err_pos))
    win = max(0, window_chars)
    margin = max(0, redact_margin_chars)
    span = win + margin
    pre_start = max(0, pos - span)
    pre_end = min(len(raw_block), pos + span)
    pre_window = raw_block[pre_start:pre_end]
    redacted = redact_fn(pre_window) if redact_fn is not None else pre_window
    rel_pos = pos - pre_start
    if redact_fn is None or len(redacted) == len(pre_window):
        center = rel_pos
    else:
        center = min(len(redacted), len(redact_fn(pre_window[:rel_pos])))
    snippet = redacted[max(0, center - win) : center + win]
    return f"malformed tool_call block raw={snippet}"


_ODD_SPAN_CACHE: dict[tuple[str, str], re.Pattern[str]] = {}


def odd_span_regex(open_tag: str, close_tag: str) -> re.Pattern[str]:
    key = (open_tag, close_tag)
    if key not in _ODD_SPAN_CACHE:
        _ODD_SPAN_CACHE[key] = re.compile(r"\}(?:\s*(?:```|~~~))?\s*" + re.escape(close_tag) + r"\s*" + re.escape(open_tag))
    return _ODD_SPAN_CACHE[key]


def split_merged_odd_block(inner: str, open_tag: str, close_tag: str, parse_fn: Callable[[str], object | None]) -> tuple[str, str] | None:
    if close_tag not in inner or not odd_span_regex(open_tag, close_tag).search(inner):
        return None
    idx = resolve_odd_quote_tool_close(inner + close_tag, 0, close_tag, parse_fn)
    return None if idx < 0 else (inner[:idx], inner[idx + len(close_tag) :] + close_tag)
