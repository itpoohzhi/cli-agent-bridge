"""Детерминированный парсер подмножества YAML на stdlib (запасной путь без PyYAML).

Поддерживается: JSON-документ целиком; комментарии ``#``; ``key: value``;
вложенные словари; списки ``- item`` и ``- key: value`` (в т.ч. списки словарей);
строки в одинарных/двойных кавычках; int/float/bool/null; пустые ``[]``/``{}``
и плоские flow-списки скаляров. Всё остальное (якоря, теги, блочные скаляры,
табы в отступах, дубликаты ключей) — явный ``ValueError``, без догадок.
"""

from __future__ import annotations

import json
import re
from typing import cast

_INT = re.compile(r"[-+]?\d+")
_FLOAT = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
_Line = tuple[int, str, int]  # (отступ, содержимое без комментария, номер строки)


def _strip_comment(raw: str) -> str:
    quote = ""
    i = 0
    while i < len(raw):
        ch = raw[i]
        if quote:
            if quote == '"' and ch == "\\":
                i += 1
            elif ch == quote:
                if quote == "'" and raw[i + 1 : i + 2] == "'":
                    i += 1
                else:
                    quote = ""
        elif ch in "'\"" and (i == 0 or raw[i - 1] in " \t[{,:-"):
            quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            return raw[:i]
        i += 1
    return raw


def _split_key(text: str) -> tuple[str, str] | None:
    """Делит ``key: rest`` по первому двоеточию вне кавычек; иначе None."""
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if quote == '"' and ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "'\"" and i == 0:
            quote = ch
        elif ch == ":" and (i + 1 == len(text) or text[i + 1] in " \t"):
            return text[:i].strip(), text[i + 1 :].strip()
        i += 1
    return None


def _scalar(text: str, lineno: int) -> object:
    if not text:
        return None
    first = text[0]
    if first == '"':
        try:
            value = cast(object, json.loads(text))
        except ValueError as exc:
            raise ValueError(f"line {lineno}: invalid double-quoted string") from exc
        if not isinstance(value, str):
            raise ValueError(f"line {lineno}: invalid double-quoted string")
        return value
    if first == "'":
        if len(text) < 2 or text[-1] != "'":
            raise ValueError(f"line {lineno}: unterminated single-quoted string")
        return text[1:-1].replace("''", "'")
    if first in "|>&*!@`%":
        raise ValueError(f"line {lineno}: unsupported YAML construct {first!r}")
    if first == "[":
        return _flow_list(text, lineno)
    if first == "{":
        if text == "{}":
            return {}
        raise ValueError(f"line {lineno}: non-empty flow mappings are not supported")
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~"):
        return None
    if _INT.fullmatch(text):
        return int(text)
    if _FLOAT.fullmatch(text):
        return float(text)
    return text


def _flow_list(text: str, lineno: int) -> list[object]:
    if text[-1] != "]":
        raise ValueError(f"line {lineno}: unterminated flow list")
    inner = text[1:-1].strip()
    if not inner:
        return []
    parts: list[str] = []
    quote, start, i = "", 0, 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            if quote == '"' and ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch in "[{":
            raise ValueError(f"line {lineno}: nested flow collections are not supported")
        elif ch == ",":
            parts.append(inner[start:i].strip())
            start = i + 1
        i += 1
    parts.append(inner[start:].strip())
    return [_scalar(p, lineno) for p in parts if p]


def _is_item(text: str) -> bool:
    return text == "-" or text.startswith("- ")


class _Parser:
    def __init__(self, lines: list[_Line]) -> None:
        self.lines = lines
        self.pos = 0

    def block(self, indent: int) -> object:
        _, text, _ = self.lines[self.pos]
        return self.sequence(indent) if _is_item(text) else self.mapping(indent)

    def sequence(self, indent: int) -> list[object]:
        items: list[object] = []
        while self.pos < len(self.lines):
            level, text, lineno = self.lines[self.pos]
            if level != indent or not _is_item(text):
                if level > indent:
                    raise ValueError(f"line {lineno}: unexpected indentation")
                break
            rest = text[1:].lstrip()
            if not rest:
                self.pos += 1
                if self.pos < len(self.lines) and self.lines[self.pos][0] > indent:
                    items.append(self.block(self.lines[self.pos][0]))
                else:
                    items.append(None)
            elif _is_item(rest):
                raise ValueError(f"line {lineno}: nested inline sequences are not supported")
            elif _split_key(rest) is not None and rest[0] not in "[{":
                # «- key: value»: содержимое элемента — словарь с отступом после «- ».
                offset = len(text) - len(rest)
                self.lines[self.pos] = (indent + offset, rest, lineno)
                items.append(self.mapping(indent + offset))
            else:
                items.append(_scalar(rest, lineno))
                self.pos += 1
        return items

    def mapping(self, indent: int) -> dict[str, object]:
        result: dict[str, object] = {}
        while self.pos < len(self.lines):
            level, text, lineno = self.lines[self.pos]
            if level < indent or (level == indent and _is_item(text)):
                break
            if level > indent:
                raise ValueError(f"line {lineno}: unexpected indentation")
            pair = _split_key(text)
            if pair is None:
                raise ValueError(f"line {lineno}: expected 'key: value'")
            raw_key, rest = pair
            key = _scalar(raw_key, lineno)
            if not isinstance(key, str):
                key = raw_key
            if key in result:
                raise ValueError(f"line {lineno}: duplicate key {key!r}")
            self.pos += 1
            if rest:
                result[key] = _scalar(rest, lineno)
                continue
            nxt = self.lines[self.pos] if self.pos < len(self.lines) else None
            if nxt is not None and (nxt[0] > indent or (nxt[0] == indent and _is_item(nxt[1]))):
                result[key] = self.block(nxt[0])
            else:
                result[key] = None
        return result


def loads(text: str) -> object:
    """Разбирает документ; при любой неподдерживаемой конструкции — ``ValueError``."""
    stripped = text.lstrip("﻿")
    if stripped.lstrip()[:1] in ("{", "["):
        try:
            return cast(object, json.loads(stripped))
        except ValueError:
            pass  # flow-YAML вне JSON разберёт построчный парсер или откажет явно
    lines: list[_Line] = []
    for number, raw in enumerate(stripped.splitlines(), start=1):
        body = _strip_comment(raw).rstrip()
        if not body.strip():
            continue
        if body.strip() in ("---", "..."):
            if lines or body.strip() == "...":
                raise ValueError(f"line {number}: multi-document YAML is not supported")
            continue
        leading = body[: len(body) - len(body.lstrip())]
        if "\t" in leading:
            raise ValueError(f"line {number}: tabs are not allowed in indentation")
        lines.append((len(leading), body.lstrip(), number))
    if not lines:
        return None
    parser = _Parser(lines)
    value = parser.block(lines[0][0])
    if parser.pos < len(lines):
        raise ValueError(f"line {lines[parser.pos][2]}: unexpected content")
    return value
