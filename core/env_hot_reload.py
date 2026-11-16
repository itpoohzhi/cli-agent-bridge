"""Горячая перезагрузка `.env`: сверка `(mtime_ns, size)` не чаще раза за TTL.

Env: `BRIDGE_ENV_FILE_PATH` (`~/.dsh/.env`), `BRIDGE_ENV_CACHE_TTL_S` (2.0, `0` — всегда),
`BRIDGE_ENV_CACHE_MAX_INSTANCES` (32, предел числа общих кэшей процесса).
Приоритет: файл (в т.ч. явное пустое значение `KEY=""`), `os.environ`, default; сбой чтения,
пустой разбор и усечение файла до нуля байт сохраняют прошлый снимок.
"""

from __future__ import annotations

import logging
import math
import os
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

ENV_FILE_PATH_ENV: Final[str] = "BRIDGE_ENV_FILE_PATH"
ENV_CACHE_TTL_ENV: Final[str] = "BRIDGE_ENV_CACHE_TTL_S"
DEFAULT_ENV_FILE_PATH: Final[str] = "~/.dsh/.env"
DEFAULT_ENV_CACHE_TTL_S: Final[float] = 2.0
ENV_CACHE_MAX_INSTANCES_ENV: Final[str] = "BRIDGE_ENV_CACHE_MAX_INSTANCES"
DEFAULT_ENV_CACHE_MAX_INSTANCES: Final[int] = 32

_LOGGER = logging.getLogger(__name__)
_INLINE_COMMENT_RE: Final[re.Pattern[str]] = re.compile(r"\s+#")


def resolve_env_file_path(environ: Mapping[str, str] | None = None) -> Path:
    """Путь к `.env` из `BRIDGE_ENV_FILE_PATH` (пусто — дефолт)."""
    src = os.environ if environ is None else environ
    return Path(str(src.get(ENV_FILE_PATH_ENV, "")).strip() or DEFAULT_ENV_FILE_PATH).expanduser()


def resolve_env_cache_ttl_s(environ: Mapping[str, str] | None = None) -> float:
    """TTL из `BRIDGE_ENV_CACHE_TTL_S`; невалидное или отрицательное — дефолт."""
    src = os.environ if environ is None else environ
    try:
        value = float(str(src.get(ENV_CACHE_TTL_ENV, "")).strip())
    except ValueError:
        return DEFAULT_ENV_CACHE_TTL_S
    return value if math.isfinite(value) and value >= 0 else DEFAULT_ENV_CACHE_TTL_S


def resolve_env_cache_max_instances(environ: Mapping[str, str] | None = None) -> int:
    """Предел общих кэшей из `BRIDGE_ENV_CACHE_MAX_INSTANCES`; невалидное или `<1` — дефолт."""
    src = os.environ if environ is None else environ
    try:
        value = int(str(src.get(ENV_CACHE_MAX_INSTANCES_ENV, "")).strip())
    except ValueError:
        return DEFAULT_ENV_CACHE_MAX_INSTANCES
    return value if value >= 1 else DEFAULT_ENV_CACHE_MAX_INSTANCES


def _parse_quoted(value: str) -> str | None:
    """Значение в кавычках; экраны: обратная косая перед кавычкой или перед самой собой. Без закрывающей кавычки или с мусором после — `None`."""
    quote, i = value[0], 1
    chars: list[str] = []
    while i < len(value):
        char = value[i]
        if char == "\\" and i + 1 < len(value) and value[i + 1] in ("'", '"', "\\"):
            chars.append(value[i + 1])
            i += 2
            continue
        if char == quote:
            tail = value[i + 1 :].strip()
            return None if tail and not tail.startswith("#") else "".join(chars)
        chars.append(char)
        i += 1
    return None


def _parse_value(raw: str) -> str | None:
    value = raw.strip()
    if value.startswith(("'", '"')):
        return _parse_quoted(value)
    return _INLINE_COMMENT_RE.split(value, maxsplit=1)[0].rstrip()


def parse_env_text(text: str) -> dict[str, str]:
    """Разбор `.env`: `NAME=value`, `export`, кавычки, комментарии."""
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, sep, raw = line.partition("=")
        name = name.strip()
        if sep and name and (value := _parse_value(raw)) is not None:
            parsed[name] = value
    return parsed


class EnvHotReloadCache:
    """Потокобезопасный кэш `.env`."""

    def __init__(
        self,
        path: Path | str | None = None,
        ttl_s: float | None = None,
        *,
        environ: Mapping[str, str] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._environ: Mapping[str, str] = os.environ if environ is None else environ
        self._path: Path = Path(path).expanduser() if path is not None else resolve_env_file_path(self._environ)
        ttl = resolve_env_cache_ttl_s(self._environ) if ttl_s is None else ttl_s
        self._ttl_s: float = ttl if math.isfinite(ttl) and ttl >= 0 else DEFAULT_ENV_CACHE_TTL_S
        self._clock = clock
        self._lock = threading.Lock()
        self._values: dict[str, str] = {}
        self._signature: tuple[int, int] | None = None
        self._next_check, self._state = 0.0, ""

    @property
    def path(self) -> Path:
        return self._path

    @property
    def ttl_s(self) -> float:
        return self._ttl_s

    def _warn_transition(self, state: str, detail: str) -> None:
        if state != self._state:
            _LOGGER.warning("env hot-reload %s path=%s detail=%s", state, self._path, detail)
        self._state = state

    def _refresh_locked(self) -> None:
        now = self._clock()
        if now < self._next_check:
            return
        self._next_check = now + self._ttl_s
        try:
            st = self._path.stat()
        except FileNotFoundError:
            self._values, self._signature = {}, None
            self._warn_transition("file_missing", "using process environment")
            return
        except OSError as exc:
            self._warn_transition("stat_failed", type(exc).__name__)
            return
        signature = (st.st_mtime_ns, st.st_size)
        if signature == self._signature:
            return
        if st.st_size == 0 and self._values:
            # Неатомарное усечение (`>` перед записью): подпись не фиксируется, файл перечитается после TTL.
            self._warn_transition("file_truncated", "keeping last valid snapshot")
            return
        try:
            text = self._path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self._warn_transition("read_failed", type(exc).__name__)
            return
        parsed = parse_env_text(text)
        if st.st_size > 0 and text.strip() and not parsed and self._values:
            self._warn_transition("parse_empty", "keeping last valid snapshot")
            return
        self._values, self._signature, self._state = parsed, signature, "ok"

    def snapshot(self) -> dict[str, str]:
        """Копия последнего валидного снимка."""
        with self._lock:
            self._refresh_locked()
            return dict(self._values)

    def get(self, name: str, default: str = "") -> str:
        """Значение: файл (явное пустое значение отзывает окружение), затем окружение, затем `default`."""
        with self._lock:
            self._refresh_locked()
            if name in self._values:
                return self._values[name]
        return str(self._environ.get(name, "")) or default

    def invalidate(self) -> None:
        """Следующее обращение перечитает файл."""
        with self._lock:
            self._signature, self._next_check = None, 0.0


_CACHES: OrderedDict[tuple[str, float], EnvHotReloadCache] = OrderedDict()
_CACHES_LOCK = threading.Lock()


def get_env_cache() -> EnvHotReloadCache:
    """Общий кэш процесса (LRU, предел — `BRIDGE_ENV_CACHE_MAX_INSTANCES`); env учитывается на каждом обращении."""
    key = (str(resolve_env_file_path()), resolve_env_cache_ttl_s())
    with _CACHES_LOCK:
        cache = _CACHES.get(key)
        if cache is None:
            cache = _CACHES[key] = EnvHotReloadCache(*key)
        _CACHES.move_to_end(key)
        limit = resolve_env_cache_max_instances()
        while len(_CACHES) > limit:
            _CACHES.popitem(last=False)
        return cache


def get_hot_env_value(name: str, default: str = "") -> str:
    """Значение переменной из общего кэша `.env` (fallback на окружение)."""
    return get_env_cache().get(name, default)
