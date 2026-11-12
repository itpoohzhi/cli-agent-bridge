"""Единый источник правды о ключе чата/кэша (`prompt_cache_key`) для всех мостов.

Чистый модуль: никакого I/O и логирования. Ключ никогда не попадает в argv или
путь процесса — наружу для хранения и корреляции отдаётся только `digest`
(sha256).

Единый контракт на невалидный ключ (передан, но не подходит): он помечается
`invalid=True`, маршрут `nokey`, а во ВСЕХ мостах запрос обслуживается как без
ключа — никакого `400`. Ключ — вспомогательный сигнал (кэш/корреляция), его
порча не должна создавать новый режим отказа доступности.

`prompt_cache_key` по OpenAI-семантике — аффинность кэша префикса, его штатно
шарят между разными чатами. Поэтому он НЕ идентичность чата: там, где ключ
становится идентичностью сессии (agy), используется набор `SOURCES_SESSION_ID`
без `prompt_cache_key`. Именованные наборы источников:
- `SOURCES_DEFAULT` — явные chat-id, затем `prompt_cache_key` (корреляция/лог:
  claude-p, opencode-zen);
- `SOURCES_SESSION_ID` — только явные chat-id (agy: идентичность горячей сессии);
- `SOURCES_CACHE_KEY_ONLY` — только `prompt_cache_key` (осознанное исключение:
  фасад и muse читали только его и до унификации; расширять нельзя — сменится
  идентичность сессии существующих клиентов).

Первый переданный (не `None`) источник решает окончательно — невалидный
приоритетный источник не даёт fallback на другой чат.

Нормализация: в строгом режиме значение и `digest` считаются от `strip()`-значения
(`"k"` и `" k "` — один ключ во всех мостах). Режим `lenient=True` — исключение для
фасада DSH (обратная совместимость): значение берётся как есть, невалиден только
не-`str`, пустой, длиннее предела или с суррогатами.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# Имя переменной окружения и безопасное значение по умолчанию (прежний предел фасада).
ENV_KEY_MAX_LEN = "BRIDGE_CHAT_KEY_MAX_LEN"
DEFAULT_KEY_MAX_LEN = 512

SRC_PROMPT_CACHE_KEY = "prompt_cache_key"
SRC_HEADER_CHAT_ID = "x-dsh-chat-id"
SRC_HEADER_SESSION_ID = "x-session-id"
SRC_EXTRA_CHAT_ID = "extra.chat_id"
SRC_REQ_CHAT_ID = "req.chat_id"

SOURCES_SESSION_ID: tuple[str, ...] = (
    SRC_HEADER_CHAT_ID,
    SRC_HEADER_SESSION_ID,
    SRC_EXTRA_CHAT_ID,
    SRC_REQ_CHAT_ID,
)
SOURCES_DEFAULT: tuple[str, ...] = SOURCES_SESSION_ID + (SRC_PROMPT_CACHE_KEY,)
SOURCES_CACHE_KEY_ONLY: tuple[str, ...] = (SRC_PROMPT_CACHE_KEY,)
DEFAULT_SOURCES = SOURCES_DEFAULT

ROUTE_KEYED = "keyed"
ROUTE_NOKEY = "nokey"


def key_max_len() -> int:
    """Предел длины ключа из env; не целое или <= 0 — значение по умолчанию."""
    raw = os.environ.get(ENV_KEY_MAX_LEN)
    if raw is None:
        return DEFAULT_KEY_MAX_LEN
    try:
        value = int(raw.strip())
    except ValueError:
        return DEFAULT_KEY_MAX_LEN
    return value if value > 0 else DEFAULT_KEY_MAX_LEN



@dataclass(frozen=True)
class ChatKey:
    """Результат разбора ключа чата."""

    keyed: bool
    route: str
    value: str
    digest: str
    invalid: bool
    source: str = ""


def digest_of(value: str, namespace: str = "") -> str:
    """sha256 (hex) ключа; непустой `namespace` входит в материал как `ns\\0key`."""
    material = f"{namespace}\0{value}" if namespace else value
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _has_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(c) <= 0xDFFF for c in value)


def _is_valid(value: object, max_len: int, lenient: bool) -> bool:
    if not isinstance(value, str) or not value or len(value) > max_len:
        return False
    if lenient:
        return not _has_surrogate(value)
    if not value.strip():
        return False
    return not any(ord(c) < 32 or ord(c) == 127 for c in value) and not _has_surrogate(
        value
    )


def _header(headers: Mapping | None, name: str) -> object:
    if headers is None:
        return None
    value = headers.get(name)
    if value is not None:
        return value
    # Обычный dict без регистронезависимого поиска (у http.server Message он есть).
    for key in headers:
        if isinstance(key, str) and key.lower() == name:
            return headers[key]
    return None


def _pick(
    source: str, req: Mapping, headers: Mapping | None, extra: Mapping | None
) -> object:
    if source == SRC_PROMPT_CACHE_KEY:
        return req.get("prompt_cache_key")
    if source == SRC_EXTRA_CHAT_ID:
        return None if extra is None else extra.get("chat_id")
    if source == SRC_REQ_CHAT_ID:
        return req.get("chat_id")
    return _header(headers, source)


def resolve_chat_key(
    req: Mapping | None,
    headers: Mapping | None = None,
    extra: Mapping | None = None,
    *,
    namespace: str = "",
    sources: Sequence[str] = SOURCES_DEFAULT,
    lenient: bool = False,
) -> ChatKey:
    """Ключ чата запроса: первый переданный источник из `sources`.

    `sources` — один из именованных наборов (`SOURCES_*`); `namespace` входит
    в `digest` (фасад сохраняет прежний `sha256(ns\\0key)`); `lenient` — режим
    совместимости фасада (см. docstring модуля).
    """
    body: Mapping = req if isinstance(req, Mapping) else {}
    limit = key_max_len()
    for source in sources:
        raw = _pick(source, body, headers, extra)
        if raw is None:
            continue
        if not _is_valid(raw, limit, lenient):
            return ChatKey(False, ROUTE_NOKEY, "", "", True, source)
        value = str(raw) if lenient else str(raw).strip()
        return ChatKey(
            True, ROUTE_KEYED, value, digest_of(value, namespace), False, source
        )
    return ChatKey(False, ROUTE_NOKEY, "", "", False, "")
