"""Единый источник правды о ключе чата/кэша (`prompt_cache_key`) для всех мостов.

Чистый модуль: никакого I/O и логирования. Ключ никогда не попадает в argv или
путь процесса — наружу для хранения и корреляции отдаётся только `digest`
(sha256). Невалидный ключ (передан, но не подходит) помечается `invalid=True`;
что с ним делать (400 или маршрут `nokey`) решает вызывающий слой.

Порядок источников (первый переданный, т.е. не `None`, решает окончательно —
невалидный приоритетный источник не даёт fallback на другой чат):
`prompt_cache_key` (OpenAI), заголовки `x-dsh-chat-id` и `x-session-id`,
`extra.chat_id`, `req.chat_id`.
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

DEFAULT_SOURCES: tuple[str, ...] = (
    SRC_PROMPT_CACHE_KEY,
    SRC_HEADER_CHAT_ID,
    SRC_HEADER_SESSION_ID,
    SRC_EXTRA_CHAT_ID,
    SRC_REQ_CHAT_ID,
)

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


# Значение на момент импорта: для читателей, которым нужна константа.
KEY_MAX_LEN = key_max_len()


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


def _is_valid(value: object, max_len: int) -> bool:
    if not isinstance(value, str):
        return False
    if not value.strip() or len(value) > max_len:
        return False
    return not any(
        ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value
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
    sources: Sequence[str] = DEFAULT_SOURCES,
) -> ChatKey:
    """Ключ чата запроса: первый переданный источник из `sources`.

    `sources` позволяет потребителю сузить набор источников (фасад читает
    только `prompt_cache_key`), не ветвясь по имени агента. `namespace` входит
    в `digest` (фасад сохраняет прежний `sha256(ns\\0key)`).
    """
    body: Mapping = req if isinstance(req, Mapping) else {}
    limit = key_max_len()
    for source in sources:
        raw = _pick(source, body, headers, extra)
        if raw is None:
            continue
        if not _is_valid(raw, limit):
            return ChatKey(False, ROUTE_NOKEY, "", "", True, source)
        value = str(raw)
        return ChatKey(
            True, ROUTE_KEYED, value, digest_of(value, namespace), False, source
        )
    return ChatKey(False, ROUTE_NOKEY, "", "", False, "")
