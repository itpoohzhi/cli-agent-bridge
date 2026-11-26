from __future__ import annotations

# Guard размера prompt и env-флаги claude-bridge (AD-006, BND-006, REQ-004).
#
# Prompt никогда не усекается: превышение лимита — явная ошибка 413.

import os
from collections.abc import Mapping
from dataclasses import dataclass

MAX_PROMPT_BYTES_ENV = "CLAUDE_P_BRIDGE_MAX_PROMPT_BYTES"
WIRE_CACHE_CREATION_ENV = "CLAUDE_P_BRIDGE_WIRE_CACHE_CREATION"
_TRUTHY: dict[str, bool] = {"1": True, "true": True, "yes": True, "on": True}


def _env_source(env: Mapping[str, str] | None) -> Mapping[str, str]:
    source = env if isinstance(env, Mapping) else os.environ
    return source


def _parse_non_negative(raw: str | None) -> int:
    """Неотрицательное целое из строки; мусор/пусто/отрицательное — `0`."""
    try:
        return max(0, int(str(raw)))
    except ValueError:
        return 0


@dataclass(frozen=True)
class PromptBudgetConfig:
    """Лимит размера prompt в байтах UTF-8 (`0` = выключено)."""

    max_prompt_bytes: int = 0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PromptBudgetConfig:
        raw = _env_source(env).get(MAX_PROMPT_BYTES_ENV)
        return cls(max_prompt_bytes=_parse_non_negative(raw))


@dataclass(frozen=True)
class PreparedPrompt:
    """Результат проверки prompt: сам prompt (без усечения) и данные ошибки."""

    prompt: str
    byte_length: int
    exceeded: bool
    max_prompt_bytes: int
    error_status: int | None
    error_body: dict[str, object] | None


def prepare_prompt_with_cap(prompt: str, config: PromptBudgetConfig) -> PreparedPrompt:
    """Измеряет prompt в UTF-8 байтах; сверх лимита — 413 `prompt_too_large`."""
    size = len(prompt.encode("utf-8"))
    exceeded = 0 < config.max_prompt_bytes < size
    message = f"prompt is {size} bytes, exceeds limit {config.max_prompt_bytes} bytes"
    error: dict[str, object] = {
        "error": {
            "message": message,
            "type": "invalid_request_error",
            "code": "prompt_too_large",
        }
    }
    return PreparedPrompt(
        prompt=prompt,
        byte_length=size,
        exceeded=exceeded,
        max_prompt_bytes=config.max_prompt_bytes,
        error_status=413 if exceeded else None,
        error_body=error if exceeded else None,
    )


def wire_cache_creation_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Флаг выдачи top-level `cache_creation_input_tokens` на wire (default OFF)."""
    raw = str(_env_source(env).get(WIRE_CACHE_CREATION_ENV, "")).strip().lower()
    return _TRUTHY.get(raw, False)
