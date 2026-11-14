"""Детерминированные отказы CLI: повтор и фолбэк на другую попытку бессмысленны."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from functools import lru_cache

ENV_DETERMINISTIC_RE = "BRIDGE_CLI_DETERMINISTIC_ERROR_RE"
DEFAULT_DETERMINISTIC_RE = (
    r"invalid model selection|is not supported for model|requires --effort"
)
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
    if not isinstance(err, str) or not err:
        return False
    source = os.environ if env is None else env
    pattern = (source.get(ENV_DETERMINISTIC_RE) or "").strip()
    return _compiled(pattern or DEFAULT_DETERMINISTIC_RE).search(err) is not None
