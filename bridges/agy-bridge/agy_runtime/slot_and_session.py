"""Вспомогательные политики очереди, сигналов, режимов и изоляции `X-Subagent-Id` для agy-bridge."""

from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Mapping
from typing import Any

from core.chat_key import resolve_chat_key
from core.session_continuity import session_key_for

SRC_HEADER_SUBAGENT_ID = "x-subagent-id"
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_MAX_COMBINED_KEY_LEN = 512
_ANTI_PLAN_DIRECTIVE = (
    "- Do NOT enter planning mode, do NOT ask for plan approval, and do NOT write "
    "implementation_plan.md; execute requested actions directly via <tool_call>."
)


def _env_float(
    name: str,
    default: float,
    low: float,
    high: float,
    environ: Mapping[str, str] | None = None,
) -> float:
    source = os.environ if environ is None else environ
    raw = str(source.get(name, "")).strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if not math.isfinite(value):
        return default
    return max(low, min(high, value))


def queue_poll_interval_s(environ: Mapping[str, str] | None = None) -> float:
    """Шаг проверки `client_gone` при ожидании слота в очереди `:9887`."""
    return _env_float("AGY_BRIDGE_QUEUE_POLL_S", 0.5, 0.05, 5.0, environ)


def kill_int_grace_s(environ: Mapping[str, str] | None = None) -> float:
    """Окно мягкого завершения после `SIGINT` перед эскалацией в `SIGTERM`."""
    return _env_float("AGY_BRIDGE_KILL_INT_GRACE_S", 0.25, 0.0, 30.0, environ)


def allow_job_orphan(
    tools_count: int, environ: Mapping[str, str] | None = None
) -> bool:
    """Безтуловые запросы (`tools_count == 0`) при уходе клиента отменяются, не осиротевают."""
    if tools_count > 0:
        return True
    source = os.environ if environ is None else environ
    return str(source.get("AGY_BRIDGE_ORPHAN_TOOLLESS_ENABLED", "")).strip().lower() in _TRUTHY


def resolve_cli_mode(
    mode: str,
    emulate_tools: bool = False,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Режим `--mode` для `agy.real` с разделением эмуляции tools и безтулового `ask`."""
    source = os.environ if environ is None else environ
    if emulate_tools or mode == "emulate":
        return str(source.get("AGY_BRIDGE_EMULATE_CLI_MODE", "plan")).strip() or "plan"
    if mode in ("ask", "plan"):
        return str(source.get("AGY_BRIDGE_ASK_CLI_MODE", "plan")).strip() or "plan"
    if mode in ("agent", "auto"):
        return str(source.get("AGY_BRIDGE_AGENT_CLI_MODE", "auto")).strip() or "auto"
    return mode


def resolve_subagent_id(headers: Mapping[str, Any] | None) -> tuple[str, bool]:
    """Нормализовать `X-Subagent-Id` по единому валидатору `core.chat_key`."""
    key = resolve_chat_key({}, headers, None, sources=(SRC_HEADER_SUBAGENT_ID,))
    return ("" if key.invalid else key.value), key.invalid


def _norm_profile(review_profile: str) -> str:
    cleaned = str(review_profile or "standard").strip().lower()
    return cleaned or "standard"


def combine_chat_and_subagent(
    chat_id: str,
    subagent_id: str,
    review_profile: str = "standard",
) -> str:
    """Пространство имён горячей сессии с изоляцией по `X-Subagent-Id` и `review_profile`."""
    profile = _norm_profile(review_profile)
    if not subagent_id:
        base = chat_id
    else:
        base = f"{chat_id}|sub:{subagent_id}" if chat_id else f"subagent:{subagent_id}"
    if profile != "standard" and base:
        base = f"{base}|profile:{profile}"
    if len(base) > _MAX_COMBINED_KEY_LEN:
        prefix = "zc:" if profile != "standard" else "sub:"
        return f"{prefix}{hashlib.sha256(base.encode('utf-8')).hexdigest()[:48]}"
    return base


def continuity_scope(
    model: object,
    subagent_id: str,
    review_profile: str = "standard",
) -> str:
    """Scope для `_CONTINUITY.resolve`: изолирует по `subagent_id` и `review_profile`."""
    profile = _norm_profile(review_profile)
    if profile == "standard":
        return f"{model or ''}\x00{subagent_id}\x00" if subagent_id else f"{model or ''}\x00"
    return f"{model or ''}\x00{subagent_id}\x00{profile}\x00"


def hot_session_key(
    model: str,
    cwd: object,
    effort: str,
    raw_chat_id: str = "",
    cwd_max_len: int = 1024,
    review_profile: str = "standard",
) -> tuple[str, ...]:
    """Ключ горячей сессии с разделением контуров `standard` и `zero-canon`."""
    base = session_key_for(model, cwd, effort, raw_chat_id, cwd_max_len)
    profile = _norm_profile(review_profile)
    if not base or profile == "standard":
        return base
    if len(base) == 4:
        chat = raw_chat_id.strip() if isinstance(raw_chat_id, str) else ""
        return session_key_for(model, cwd, effort, f"{chat}|profile:{profile}", cwd_max_len)
    return (base[0], base[1], f"{base[2]}|profile:{profile}")


def append_anti_plan_directive(section: str) -> str:
    """Добавить agy-специфичный запрет ухода в `/plan` только в секцию эмуляции agy-bridge."""
    return f"{section}\n{_ANTI_PLAN_DIRECTIVE}" if section else section


def health_queue_fields(slots: Any) -> dict[str, int]:
    """Аддитивные счётчики очереди и занятых слотов для `/health`."""
    return {
        "queued": int(getattr(slots, "waiters_count", 0)),
        "slots_active": int(getattr(slots, "active_count", 0)),
    }
