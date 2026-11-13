"""Линейная (O(N)) редакция секретов в URL: userinfo `scheme://user:pass@host` и `scheme://user:pass`.

Поиск `@` через backtracking-регулярку при каждом `scheme://` даёт квадратичное время
на входах вида `http://u:p x://x://...`, поэтому окно userinfo считается явным проходом:
после неудачи пропускается весь первый токен, после успеха — весь редактируемый фрагмент.
"""
from __future__ import annotations

import re
from typing import Final

_SCHEME: Final[str] = r"[a-z][a-z0-9+.-]{0,31}://"
_START_RE: Final[re.Pattern[str]] = re.compile(rf"(?i)(?:(?<=\\[bfnrtv])|(?<![a-z0-9+.-])){_SCHEME}(?!\s)")
# Окно userinfo: первый токен и до 4 токенов-продолжений, не начинающихся с новой схемы.
_WINDOW_RE: Final[re.Pattern[str]] = re.compile(rf"(?i)(\S+)(?:\s+(?!{_SCHEME})\S+){{0,4}}")
_TAIL_RE: Final[re.Pattern[str]] = re.compile(r"[^\s\"']*")
# `user:pass` без `@`; `host:8080` (порт) не считается секретом.
_USERPASS_RE: Final[re.Pattern[str]] = re.compile(rf"{_START_RE.pattern}[^\s/\"'@:]*:(?![0-9]{{1,5}}(?:[/?#\s\"']|$))[^\s/\"'@]+")


def _last_userinfo_at(text: str, start: int, stop: int) -> int:
    at = text.rfind("@", start + 1, stop)
    while at > 0 and text[at - 1].isspace():
        at = text.rfind("@", start + 1, at)
    return at


def redact_url_secrets(text: str, token: str) -> str:
    if "://" not in text:
        return text
    parts: list[str] = []
    copied = scan = 0
    while (start := _START_RE.search(text, scan)) is not None:
        window = _WINDOW_RE.match(text, start.end())
        if window is None:
            break
        at = _last_userinfo_at(text, start.end(), window.end())
        if at < 0:
            scan = window.end(1)
            continue
        tail = _TAIL_RE.match(text, at + 1)
        parts += (text[copied : start.start()], token)
        copied = scan = tail.end() if tail else at + 1
    return _USERPASS_RE.sub(token, "".join(parts) + text[copied:])
