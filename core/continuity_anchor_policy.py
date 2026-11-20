"""Чистые функции криптоякорей и хранилище пост-ходовой привязки continuity (D2)."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from collections import OrderedDict
from collections.abc import Sequence
from typing import Final, cast, final

BRIDGE_CALL_ID_RE: Final[re.Pattern[str]] = re.compile(r"^call_[0-9a-f]{24}$")


def mint_bridge_call_id() -> str:
    """Генерирует 96-битный криптографический идентификатор tool_call (^call_[0-9a-f]{24}$)."""
    return f"call_{secrets.token_hex(12)}"


def extract_valid_bridge_call_ids(tool_calls: object) -> tuple[str, ...]:
    """Извлекает отсортированные уникальные bridge call_id, прошедшие regex-валидацию."""
    items = cast("list[object]", tool_calls) if isinstance(tool_calls, (list, tuple)) else []
    found: set[str] = set()
    for item in items:
        raw: object = cast("dict[str, object]", item).get("id") if isinstance(item, dict) else item
        token = raw.strip() if isinstance(raw, str) else ""
        if BRIDGE_CALL_ID_RE.fullmatch(token):
            found.add(token)
    return tuple(sorted(found))


def build_post_turn_anchor_key(
    scope: str, prefix_digest: str, call_ids: Sequence[str]
) -> str | None:
    """Строит криптоключ якоря; при пустом наборе валидных bridge call_id возвращает None."""
    valid_ids = extract_valid_bridge_call_ids(list(call_ids))
    result: str | None = None
    if all((bool(prefix_digest), bool(valid_ids))):
        payload = {"scope": scope, "prefix": prefix_digest, "call_ids": list(valid_ids)}
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        result = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return result


@final
class PostTurnAnchorIndex:
    """Хранилище одноразовых пост-ходовых якорей (работает под замком ContinuityIndex)."""

    def __init__(self, max_links: int = 4096, ttl_s: float = 1800.0) -> None:
        self._max_links = max(1, int(max_links))
        self._ttl_s = max(0.0, float(ttl_s)) or 1800.0
        self._entries: OrderedDict[str, tuple[str | None, float]] = OrderedDict()

    def count(self) -> int:
        """Текущее число записей в пост-ходовом индексе."""
        return len(self._entries)

    def expire(self, now: float) -> None:
        """Удаляет просроченные записи по TTL."""
        while self._entries:
            ts = next(iter(self._entries.values()))[1]
            if (now - ts) <= self._ttl_s:
                break
            _ = self._entries.popitem(last=False)

    def register(self, key: str, chain: str, now: float) -> str:
        """Регистрирует якорь; конфликт разных chain переводит ключ в tombstone."""
        self.expire(now)
        existing = self._entries.get(key)
        conflict = bool(existing) and existing[0] != chain if existing else False
        status = "conflict_tombstone" if conflict else "registered"
        self._entries[key] = (None, now) if conflict else (chain, now)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_links:
            _ = self._entries.popitem(last=False)
        return status

    def claim(self, key: str, now: float) -> tuple[str | None, str]:
        """Одноразово забирает chain по ключу якоря (pop)."""
        self.expire(now)
        entry = self._entries.pop(key, None)
        result: tuple[str | None, str] = (None, "miss")
        if entry:
            result = (entry[0], "hit") if isinstance(entry[0], str) else (None, "tombstone")
        return result
