"""Детекция зацикливаний текста и обработка Markdown-таблиц."""

from __future__ import annotations

import re

_LOOP_TAIL_CHARS = 600
_LOOP_MIN_REPEATS = 6
_LOOP_MIN_BLOCK_CHARS = 120
_CDATA_END_MIN = 6
_CDATA_GAP_MAX = 80

_TABLE_SEP_RE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*$",
    re.MULTILINE,
)


def _in_active_markdown_table(
    text: str, loop_start: int, sep_ends: list[int] | None = None
) -> bool:
    """Перед loop_start идёт строка-разделитель таблицы, а после неё нет пустой строки и все строки с «|»."""
    if sep_ends is None:
        sep_ends = [m.end() for m in _TABLE_SEP_RE.finditer(text, 0, loop_start)]
        last_end = sep_ends[-1] if sep_ends else None
    else:
        last_end = next((e for e in reversed(sep_ends) if e <= loop_start), None)
    if last_end is None:
        return False
    between = text[last_end:loop_start]
    for eol in ("\r\n", "\n"):
        if between.startswith(eol):
            between = between[len(eol) :]
            break
    lines = between.splitlines()
    if lines and not between.endswith(("\n", "\r")):
        lines.pop()
    return all(ln.strip() and "|" in ln and "||" not in ln for ln in lines)


def _is_table_block(unit: str, text: str = "", loop_start: int = 0) -> bool:
    """Блок содержит разделитель ячеек markdown-таблицы."""
    if "\n" not in unit:
        return False
    lines = [s.strip() for s in (unit * 3).splitlines()[1:-1] if s.strip()]
    if not lines:
        return False
    if not all("|" in s and "||" not in s for s in lines):
        return False
    if _in_active_markdown_table(text, loop_start):
        return True
    return all(
        s.startswith("|")
        or s.endswith("|")
        or s.count("|") >= 2
        or (" | " in s and not s.endswith((".", "!", "?", ";")))
        for s in lines
    )


def _cdata_loop_start(text: str) -> int | None:
    """Начало цикла «]]>»: >= _CDATA_END_MIN «]]>» вне таблиц в последних 300 символах."""
    recent_start = max(0, len(text) - 300)
    if text.count("]]>", recent_start) < _CDATA_END_MIN:
        return None
    seps = [m.end() for m in _TABLE_SEP_RE.finditer(text)]

    def is_terminator(pos: int) -> bool:
        return "<![CDATA[" not in text[
            max(0, pos - 300) : pos
        ] and not _in_active_markdown_table(text, pos, seps)

    recent: list[int] = []
    pos = text.find("]]>", recent_start)
    while pos >= 0:
        if is_terminator(pos):
            recent.append(pos)
        pos = text.find("]]>", pos + 3)
    if len(recent) < _CDATA_END_MIN:
        return None
    start = recent[0]
    while (
        prev := text.rfind("]]>", max(0, start - _CDATA_GAP_MAX), start)
    ) >= 0 and is_terminator(prev):
        start = prev
    return start


def _detect_repetition_loop(text: str) -> int | None:
    """Индекс начала зацикленного хвоста или None."""
    tail = text[-_LOOP_TAIL_CHARS:]
    base = len(text) - len(tail)
    if (
        "<![CDATA[" not in tail[-300:]
        and (cdata_idx := _cdata_loop_start(text)) is not None
    ):
        return cdata_idx
    size_total = len(tail)
    for size in range(4, 81):
        if size * _LOOP_MIN_REPEATS > size_total:
            break
        unit = tail[-size:]
        if len(set(unit) - set(" \t\r\n")) < 3:
            continue
        pos = size_total - size
        reps = 1
        while pos - size >= 0 and tail[pos - size : pos] == unit:
            reps += 1
            pos -= size
        if reps < _LOOP_MIN_REPEATS or size * reps < _LOOP_MIN_BLOCK_CHARS:
            continue
        full_pos = base + pos
        while full_pos - size >= 0 and text[full_pos - size : full_pos] == unit:
            full_pos -= size
        if _is_table_block(unit, text, full_pos):
            continue
        return full_pos
    return None
