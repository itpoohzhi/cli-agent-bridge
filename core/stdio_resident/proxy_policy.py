"""Чистая политика loopback Zero-Canon proxy: URL, таймаут, запрет редиректов."""
# pyright: reportExplicitAny=false, reportAny=false, reportImplicitOverride=false

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from core.runtime_env import env_bool
from core.timeout_ladder import FLAG_TIMEOUT_LADDER, TimeoutLadderConfig, load_timeout_ladder_config

TIMEOUT_ENV = "HUB_ZERO_CANON_PROXY_TIMEOUT_S"
DEFAULT_PROXY_TIMEOUT_S = 180.0
_ALLOWED_ORIGINS = frozenset(("http", host) for host in ("127.0.0.1", "localhost", "::1"))


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Блокирует любые редиректы loopback-запроса."""

    def redirect_request(self, *args: Any, **_kwargs: Any) -> None:
        _, fp, code, msg, headers, newurl = args[:6]
        raise urllib.error.HTTPError(newurl, code, f"redirect blocked ({msg})", headers, fp)


def ensure_loopback_url(base_url: str) -> str:
    """Принимает только `http` + `127.0.0.1|localhost|::1`; возвращает URL без хвостового `/`."""
    parsed = urllib.parse.urlparse(base_url)
    if (parsed.scheme, parsed.hostname) not in _ALLOWED_ORIGINS:
        raise ValueError(f"non_loopback_zero_canon_bridge_url:{base_url}")
    return base_url.rstrip("/")


def _ladder_timeout_s(env: Mapping[str, str]) -> float:
    try:
        ladder = load_timeout_ladder_config(env)
    except ValueError:
        if env_bool(env, (FLAG_TIMEOUT_LADDER,), False):
            raise
        ladder = TimeoutLadderConfig()
    value = ladder.effective_first_event_s if ladder.enabled else DEFAULT_PROXY_TIMEOUT_S
    return value


def resolve_proxy_timeout_s(timeout_s: float | None, environ: Mapping[str, str] | None = None) -> float:
    """Явный таймаут > env `HUB_ZERO_CANON_PROXY_TIMEOUT_S` > timeout ladder > 180 s."""
    env = os.environ if environ is None else environ
    raw = env.get(TIMEOUT_ENV, "").strip()
    fallback = float(raw) if raw else _ladder_timeout_s(env)
    return fallback if timeout_s is None else timeout_s
