"""Непрерывность чата без клиентского chat id: цепочка по дайджесту префикса.

Чистый домен (stdlib, без I/O и env): дайджест префикса и пост-ходовой
криптоякорь assistant.tool_calls[].id (одноразовый pop + tombstone).
"""

from __future__ import annotations

import hashlib
import json
import os.path
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast, final

from core.continuity_anchor_policy import (
    PostTurnAnchorIndex,
    build_post_turn_anchor_key,
    extract_valid_bridge_call_ids,
)

_DEFAULT_TTL_S = 1800.0
_PART_KEYS = (
    *"type text image_url url detail source media_type data".split(),
    *"input_audio file id name input tool_use_id content".split(),
)


@dataclass(frozen=True)
class ContinuityConfig:
    """Параметры индекса; некорректные значения безопасно зажимаются."""

    max_links: int = 4096
    ttl_s: float = _DEFAULT_TTL_S
    log_fn: Callable[[str], None] | None = None
    post_turn_anchor_enabled: bool | Callable[[], bool] = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_links", max(1, int(self.max_links)))
        if not self.ttl_s > 0:
            object.__setattr__(self, "ttl_s", _DEFAULT_TTL_S)


def _norm_value(value: object) -> object:
    if isinstance(value, list):
        return [_norm_value(v) for v in cast("list[object]", value)]
    if isinstance(value, dict):
        return _norm_part(cast("dict[str, object]", value))
    return value


def _norm_part(part: dict[str, object]) -> dict[str, object]:
    return {k: _norm_value(part[k]) for k in _PART_KEYS if k in part}


def _norm_tool_calls(calls: object) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for call in cast("list[object]", calls) if isinstance(calls, list) else []:
        if not isinstance(call, dict):
            continue
        item = cast("dict[str, object]", call)
        fn_raw = item.get("function")
        fn = cast("dict[str, object]", fn_raw) if isinstance(fn_raw, dict) else {}
        out.append(
            {
                "id": item.get("id"),
                "name": fn.get("name", item.get("name")),
                "arguments": fn.get("arguments", item.get("arguments")),
            }
        )
    return out


def _canon_message(msg: object) -> dict[str, object]:
    if not isinstance(msg, dict):
        return {"raw": str(msg)}
    item = cast("dict[str, object]", msg)
    out: dict[str, object] = {
        "role": item.get("role"),
        "content": _norm_value(item.get("content")),
    }
    if item.get("tool_calls"):
        out["tool_calls"] = _norm_tool_calls(item.get("tool_calls"))
    for key in ("tool_call_id", "name"):
        if item.get(key) is not None:
            out[key] = item[key]
    return out


def _digest(canon: list[dict[str, object]], scope: str) -> str:
    payload = {"scope": scope, "messages": canon}
    raw = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8", "surrogatepass")).hexdigest()


def canonical_digest(messages: Sequence[object], scope: str = "") -> str:
    """sha256 устойчивых полей сообщений; метаданные клиента игнорируются."""
    return _digest([_canon_message(m) for m in messages], scope)


def _default_chain() -> str:
    return f"cont-{uuid.uuid4().hex}"


def _has_tool_call_anchor(canon_slice: Sequence[dict[str, object]]) -> bool:
    """Есть assistant-сообщение с tool_calls, где хотя бы один id непуст."""
    return any(
        msg.get("role") == "assistant"
        and any(
            bool(str(c.get("id") or "").strip())
            for c in _norm_tool_calls(msg.get("tool_calls"))
        )
        for msg in canon_slice
    )


def _last_assistant_index(canon: list[dict[str, object]]) -> int:
    hits = [i for i, m in enumerate(canon) if dict(assistant=True).get(str(m.get("role")), False)]
    return hits[-1] if hits else -1


def _prefix_digest(canon: list[dict[str, object]], scope: str) -> str | None:
    """Дайджест истории до последнего assistant; None — нет якорного префикса."""
    last = _last_assistant_index(canon)
    ok = all((last > 0, _has_tool_call_anchor(canon[: max(0, last)])))
    result = _digest(canon[:last], scope) if ok else None
    return result


def _post_anchor_key(canon: list[dict[str, object]], scope: str) -> str | None:
    """Ключ пост-ходового якоря по (scope, digest(canon[:last]), bridge call_ids в canon[last])."""
    last = _last_assistant_index(canon)
    result: str | None = None
    if last > 0:
        call_ids = extract_valid_bridge_call_ids(canon[last].get("tool_calls"))
        result = build_post_turn_anchor_key(scope, _digest(canon[:last], scope), call_ids)
    return result


@final
class ContinuityIndex:
    """Потокобезопасный индекс «дайджест истории → chain» с TTL и LRU."""

    def __init__(
        self,
        config: ContinuityConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
        new_chain: Callable[[], str] | None = None,
    ) -> None:
        self._config = config or ContinuityConfig()
        self._clock = clock
        self._new_chain = new_chain or _default_chain
        self._lock = threading.Lock()
        self._links: OrderedDict[str, tuple[str | None, float]] = OrderedDict()
        self._post_anchors = PostTurnAnchorIndex(self._config.max_links, self._config.ttl_s)

    def _post_enabled(self) -> bool:
        flag = self._config.post_turn_anchor_enabled
        return bool(flag()) if callable(flag) else bool(flag)

    def link_count(self) -> int:
        with self._lock:
            return len(self._links)

    def _expire(self, now: float) -> None:
        ttl = self._config.ttl_s
        while self._links:
            ts = next(iter(self._links.values()))[1]
            if now - ts <= ttl:
                break
            _ = self._links.popitem(last=False)
        self._post_anchors.expire(now)

    def _take_chain(
        self, prefix: str | None, post_key: str | None = None, now: float = 0.0
    ) -> tuple[str, str]:
        entry = self._links.pop(prefix, None) if isinstance(prefix, str) else None
        result: tuple[str, str] | None = None
        if isinstance(entry, tuple):
            result = (entry[0], "hit") if isinstance(entry[0], str) else (self._new_chain(), "tombstone")
        elif all((isinstance(post_key, str), self._post_enabled())):
            chain, pstatus = self._post_anchors.claim(str(post_key), now)
            if isinstance(chain, str):
                result = (chain, "post_hit")
            elif dict(tombstone=True).get(pstatus, False):
                result = (self._new_chain(), "tombstone")
        fallback = (self._new_chain(), "miss" if isinstance(prefix, str) else "init")
        return result if isinstance(result, tuple) else fallback

    def _register(self, full: str, chain: str, now: float, status: str) -> str:
        existing = self._links.get(full)
        if existing is not None and existing[0] != chain:
            self._links[full] = (None, now)
            self._links.move_to_end(full)
            return "conflict_tombstone"
        self._links[full] = (chain, now)
        self._links.move_to_end(full)
        while len(self._links) > self._config.max_links:
            _ = self._links.popitem(last=False)
        return status

    def register_post_turn(
        self,
        messages: object,
        scope: str,
        chain: str,
        emitted_call_ids: Sequence[str],
        *,
        enabled: bool = True,
    ) -> bool:
        """Регистрирует пост-ходовой криптоякорь (вызывать строго после tool_turn.finish())."""
        ok = False
        if all((enabled, self._post_enabled(), isinstance(messages, list), bool(messages), bool(chain))):
            canon = [_canon_message(m) for m in cast("list[object]", messages)]
            key = build_post_turn_anchor_key(scope, _digest(canon, scope), emitted_call_ids)
            if isinstance(key, str):
                with self._lock:
                    _ = self._post_anchors.register(key, chain, self._clock())
                ok = True
        return ok

    def resolve(self, messages: object, scope: str = "") -> str:
        """chain для истории; пустая строка — истории нет."""
        if not isinstance(messages, list) or not messages:
            return ""
        canon = [_canon_message(m) for m in cast("list[object]", messages)]
        prefix = _prefix_digest(canon, scope)
        post_key = _post_anchor_key(canon, scope)
        full = _digest(canon, scope) if _has_tool_call_anchor(canon) else None
        with self._lock:
            now = self._clock()
            self._expire(now)
            chain, status = self._take_chain(prefix, post_key, now)
            if full is not None:
                status = self._register(full, chain, now, status)
            count = len(self._links)
        log_fn = self._config.log_fn
        if log_fn is not None:
            log_fn(f"continuity status={status} links={count}")
        return chain


def _has_bad_char(text: str) -> bool:
    return any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in text)


def _normalize_cwd(cwd: object, max_len: int) -> str | None:
    """Нормализованный cwd; "" — штатно нет; None — невалидный (fail-closed)."""
    if cwd is None:
        return ""
    if not isinstance(cwd, str):
        return None
    val = cwd.strip()
    if not val:
        return ""
    if len(val) > max_len or not os.path.isabs(val) or _has_bad_char(val):
        return None
    return os.path.normpath(val)


def session_key_for(
    model: str,
    cwd: object,
    effort: str,
    raw_chat_id: str = "",
    cwd_max_len: int = 1024,
) -> tuple[str, ...]:
    """Ключ горячей сессии: токен чата, иначе cwd; без обоих ключ пуст.

    Сырой chat id наружу не попадает — только его полный SHA-256. Невалидный
    переданный cwd (не строка, относительный, длинный, с контролами) — ключа нет.
    """
    raw = cast("object", raw_chat_id)
    chat = raw.strip() if isinstance(raw, str) else ""
    if _has_bad_char(chat):
        return ()
    cwd_norm = _normalize_cwd(cwd, cwd_max_len)
    if cwd_norm is None:
        return ()
    if chat:
        token = hashlib.sha256(chat.encode("utf-8")).hexdigest()
        return (token, model, cwd_norm, effort)
    if cwd_norm:
        return (model, cwd_norm, effort)
    return ()
