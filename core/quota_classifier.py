"""Настраиваемая классификация квотных и временных HTTP 429."""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import cast

_BODY_DEFAULT = (r"quota|usage[_ ]?limit|insufficient_quota|billing",)
_RESET_DEFAULT = (r"\bresets?\s+in\s+(?P<duration>(?:\d+(?:\.\d+)?\s*[dhms]\s*)+)",)
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)\s*([dhms])", re.IGNORECASE)
_UNIT_SECONDS = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def _number(env: Mapping[str, str], name: str, default: float) -> float:
    value = float(env.get(name, str(default)))
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return value


def _entries(
    config: Mapping[str, object], env: Mapping[str, str], key: str, default: tuple[str, ...]
) -> tuple[str, ...]:
    values = config.get(key, default)
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{key} must be a list of strings")
    items = cast(Sequence[object], values)
    if any(not isinstance(v, str) for v in items):
        raise ValueError(f"{key} must be a list of strings")
    extra = [v.strip() for v in env.get("BRIDGE_QUOTA_" + key.upper(), "").split(",")]
    return cast(tuple[str, ...], tuple(items)) + tuple(v for v in extra if v)


@dataclass(frozen=True, slots=True, kw_only=True)
class QuotaRules:
    """Скомпилированные правила и пределы, неизменяемые после загрузки."""

    body_patterns: tuple[re.Pattern[str], ...]
    error_codes: frozenset[str]
    reset_body_patterns: tuple[re.Pattern[str], ...]
    cooldown_max_s: float
    cooldown_default_s: float
    reset_threshold_s: float
    transient_max_wait_s: float
    body_max_bytes: int
    epoch_threshold_s: float = 1_000_000_000

    @classmethod
    def from_config(
        cls,
        quota_rules: Mapping[str, object] | None = None,
        *,
        env: Mapping[str, str] | None = None,
    ) -> QuotaRules:
        """Дополняет правила YAML переменными окружения, без вендорских исключений."""
        config: Mapping[str, object] = {} if quota_rules is None else quota_rules
        environ = os.environ if env is None else env
        return cls(
            body_patterns=tuple(
                re.compile(p, re.IGNORECASE)
                for p in _entries(config, environ, "body_patterns", _BODY_DEFAULT)
            ),
            error_codes=frozenset(
                v.casefold()
                for v in _entries(config, environ, "error_codes", ("insufficient_quota",))
            ),
            reset_body_patterns=tuple(
                re.compile(p, re.IGNORECASE)
                for p in _entries(config, environ, "reset_body_patterns", _RESET_DEFAULT)
            ),
            cooldown_max_s=_number(environ, "BRIDGE_QUOTA_COOLDOWN_MAX_S", 604800),
            cooldown_default_s=_number(environ, "BRIDGE_QUOTA_COOLDOWN_DEFAULT_S", 3600),
            reset_threshold_s=_number(environ, "BRIDGE_QUOTA_RESET_THRESHOLD_S", 3600),
            transient_max_wait_s=_number(environ, "BRIDGE_TRANSIENT_429_MAX_WAIT_S", 5),
            body_max_bytes=max(1, int(_number(environ, "BRIDGE_QUOTA_BODY_MAX_BYTES", 65536))),
            epoch_threshold_s=_number(environ, "BRIDGE_QUOTA_EPOCH_THRESHOLD", 1_000_000_000),
        )


@dataclass(frozen=True, slots=True)
class QuotaClassification:
    """Решение классификатора; квота всегда запрещает повтор той же модели."""

    is_quota: bool
    reason: str
    reset_s: float
    retry_after_s: float | None
    retry_allowed: bool


def _duration_seconds(text: str) -> float | None:
    cursor, total = 0, 0.0
    for match in _DURATION_PART.finditer(text):
        if text[cursor : match.start()].strip():
            return None
        total += float(match[1]) * _UNIT_SECONDS[match[2].lower()]
        cursor = match.end()
    return total if cursor and not text[cursor:].strip() else None


def _header_seconds(
    value: str, now_s: float, epoch: bool = False, epoch_threshold_s: float = 1_000_000_000
) -> float | None:
    """Числа меньше порога epoch — относительные секунды, а не Unix-время 1970 года."""
    numeric = True
    try:
        seconds = float(value)
    except ValueError:
        numeric = False
        duration = _duration_seconds(value)
        if duration is not None:
            return duration
        try:
            date = parsedate_to_datetime(value)
            seconds = date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp()
        except (ValueError, TypeError, OverflowError):
            return None
        epoch = True
    if not math.isfinite(seconds):
        return None
    if numeric and epoch and seconds < epoch_threshold_s:
        epoch = False
    return max(0.0, seconds - now_s if epoch else seconds)


def _body_resets(text: str, rules: QuotaRules) -> list[float]:
    values: list[float] = []
    for pattern in rules.reset_body_patterns:
        for match in pattern.finditer(text):
            duration = match.groupdict().get("duration")
            value = _duration_seconds(duration if duration is not None else match[0])
            if value is not None:
                values.append(value)
    return values


def _quota_body(text: str, rules: QuotaRules) -> bool:
    if any(pattern.search(text) for pattern in rules.body_patterns):
        return True
    try:
        payload = cast(object, json.loads(text))
    except (ValueError, RecursionError):
        return False
    error = cast(Mapping[str, object], payload).get("error") if isinstance(payload, dict) else None
    return isinstance(error, dict) and any(
        isinstance(value, str) and value.casefold() in rules.error_codes
        for key in ("code", "type")
        for value in (cast(Mapping[str, object], error).get(key),)
    )


def classify_429(
    headers: Mapping[str, str] | Sequence[tuple[str, str]],
    body: bytes,
    rules: QuotaRules,
    now_s: float | None = None,
) -> QuotaClassification:
    """Классифицирует 429 по ограниченному телу и максимуму сроков сброса."""
    now = time.time() if now_s is None else now_s
    text = body[: rules.body_max_bytes].decode("utf-8", errors="replace")
    resets = _body_resets(text, rules)
    retry_after = None
    pairs = headers.items() if isinstance(headers, Mapping) else headers
    for name, value in pairs:
        name = name.lower()
        if name != "retry-after" and not name.startswith("x-ratelimit-reset-"):
            continue
        seconds = _header_seconds(
            value, now, epoch=name != "retry-after", epoch_threshold_s=rules.epoch_threshold_s
        )
        if seconds is not None:
            resets.append(seconds)
            if name == "retry-after":
                retry_after = max(retry_after or 0, seconds)
    is_quota = _quota_body(text, rules) or max(resets, default=0) > rules.reset_threshold_s
    reset_s = min(rules.cooldown_max_s, max(resets, default=rules.cooldown_default_s))
    return QuotaClassification(
        is_quota,
        "quota" if is_quota else "transient",
        reset_s,
        retry_after,
        not is_quota and retry_after is not None and retry_after <= rules.transient_max_wait_s,
    )
