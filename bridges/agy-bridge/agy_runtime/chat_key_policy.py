"""Флаг-политика prompt_cache_key для идентичности чата agy-bridge (default OFF)."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

from agy_runtime.long_session_config import read_bool_setting
from core import chat_key as _chat_key
from core.chat_key import ChatKey

FLAG_HOT_PCK = "BRIDGE_HOT_PROMPT_CACHE_KEY_ENABLED"
CONFIG_KEY_HOT_PCK = "bridge_hot_prompt_cache_key_enabled"
_resolve_chat_key = cast("Callable[..., ChatKey]", _chat_key.resolve_chat_key)


def is_prompt_cache_key_enabled(config_path: Path | None = None) -> bool:
    """OFF по умолчанию: prompt_cache_key игнорируется как идентичность сессии."""
    return read_bool_setting(CONFIG_KEY_HOT_PCK, FLAG_HOT_PCK, False, config_path=config_path)


def resolve_agy_chat_key(
    req: Mapping[str, object] | None,
    headers: Mapping[str, object] | None = None,
    extra: Mapping[str, object] | None = None,
    *,
    config_path: Path | None = None,
) -> ChatKey:
    """SOURCES_DEFAULT при включённом флаге, иначе SOURCES_SESSION_ID."""
    sources = _chat_key.SOURCES_DEFAULT if is_prompt_cache_key_enabled(config_path) else _chat_key.SOURCES_SESSION_ID
    return _resolve_chat_key(req, headers, extra, sources=sources)
