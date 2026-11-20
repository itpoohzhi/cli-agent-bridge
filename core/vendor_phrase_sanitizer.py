"""Маскирование вендорной фразы `Retries remaining: N` в user-visible ошибке (AD-006, BND-001).

Применяется только к тексту, который уходит пользователю; вход парсера и классификатора
не трогается. Диагностика сохраняется (маскируется лишь сама фраза), операция идемпотентна.
"""

from __future__ import annotations

import re

DEFAULT_PATTERNS: tuple[str, ...] = (r"Retries remaining:\s*\d+",)
DEFAULT_REPLACEMENT = ""
_SPACES = re.compile(r"[ \t]{2,}")


def _compiled(patterns: tuple[str, ...]) -> list[re.Pattern[str]]:
    """Скомпилировать валидные regex; невалидные пропускаются (текст остаётся как есть)."""
    out: list[re.Pattern[str]] = []
    for raw in patterns:
        try:
            out.append(re.compile(raw, re.IGNORECASE))
        except re.error:
            continue
    return out


def mask_vendor_phrases(
    text: object,
    patterns: tuple[str, ...] = DEFAULT_PATTERNS,
    replacement: str = DEFAULT_REPLACEMENT,
) -> str:
    """Замаскировать фразы по regex; не-строка → `""`, текст без совпадений не меняется."""
    if not isinstance(text, str) or not text:
        return ""
    result = text
    for pattern in _compiled(tuple(patterns)):
        result = pattern.sub(replacement, result)
    if result == text:
        return text
    return _SPACES.sub(" ", result).rstrip()
