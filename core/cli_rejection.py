"""Детерминированные отказы CLI: повтор и фолбэк на другую попытку бессмысленны."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from functools import lru_cache
from typing import Final

from core.runtime_env import positive_int

ENV_DETERMINISTIC_RE: Final[str] = "BRIDGE_CLI_DETERMINISTIC_ERROR_RE"
ENV_DETERMINISTIC_ERR_MAX_LEN: Final[str] = "BRIDGE_CLI_DETERMINISTIC_ERR_MAX_LEN"
DEFAULT_DETERMINISTIC_RE: Final[str] = (
    r"invalid model selection|is not supported for model|requires --effort"
)
DEFAULT_ERR_SCAN_LEN: Final[int] = 2048
_DISABLE_TOKENS: Final[frozenset[str]] = frozenset({"", "0", "false", "off", "no"})
_LOG = logging.getLogger(__name__)


@lru_cache(maxsize=32)
def _compiled(pattern: str) -> re.Pattern[str]:
    """Кэш по строке паттерна: битый regex предупреждает один раз."""
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        _LOG.warning("%s: invalid regex, using default: %s", ENV_DETERMINISTIC_RE, exc)
        return re.compile(DEFAULT_DETERMINISTIC_RE, re.IGNORECASE)


def is_deterministic_cli_rejection(
    err: object, env: Mapping[str, str] | None = None
) -> bool:
    """Текст ошибки CLI совпал с паттерном детерминированного отказа."""
    rejected = False
    if isinstance(err, str) and err:
        source = os.environ if env is None else env
        raw = source.get(ENV_DETERMINISTIC_RE)
        pattern = DEFAULT_DETERMINISTIC_RE
        if raw is not None:
            pattern = raw.strip()
        if pattern.lower() not in _DISABLE_TOKENS:
            max_len = positive_int(
                source, ENV_DETERMINISTIC_ERR_MAX_LEN, DEFAULT_ERR_SCAN_LEN
            )
            rejected = bool(_compiled(pattern).search(err[:max_len]))
    return rejected
