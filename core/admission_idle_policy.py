"""Чистая политика phase-idle admission, TTL-вытеснения и редактирования диагностики.

Zero-I/O модуль (M-MOD-I3): импортируются только math/re/dataclasses/collections.abc.
Все kill-switch флаги независимы и default=False (fail-closed); числовые параметры
валидируются по границам. Свежее чтение env/dynamic_config живёт в core.http_accept,
здесь — только детерминированные вычисления без побочных эффектов.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass

# Независимые kill-switch флаги (default False, fail-closed).
PHASE_IDLE_FLAG = "BRIDGE_HTTP_IDLE_ADMISSION_TIMEOUT_ENABLED"
TTL_SWEEP_FLAG = "BRIDGE_PASSTHROUGH_ACTIVE_TTL_SWEEP_ENABLED"
ADMISSION_TELEMETRY_FLAG = "BRIDGE_ADMISSION_TELEMETRY_ENABLED"
CLAUDE_STDERR_FLAG = "BRIDGE_CLAUDE_P_LOG_STDERR_ON_FAIL_ENABLED"

_PHASE_IDLE_TIMEOUT_ENV = "BRIDGE_HTTP_PHASE_IDLE_TIMEOUT_S"
_ACTIVE_SOCKET_TIMEOUT_ENV = "BRIDGE_HTTP_ACTIVE_SOCKET_TIMEOUT_S"
_CLAUDE_STDERR_MAX_ENV = "BRIDGE_CLAUDE_P_STDERR_LOG_MAX_CHARS"
_LEGACY_MAX_CONN_ENV = "BRIDGE_MAX_HTTP_CONNECTIONS"
_RESTART_ACTOR_ENV = "BRIDGE_RESTART_ACTOR"

# Границы числовых параметров (безопасные дефолты внутри диапазона).
PHASE_IDLE_TIMEOUT_BOUNDS = (0.02, 3600.0)
ACTIVE_SOCKET_TIMEOUT_BOUNDS = (1.0, 86400.0)
CLAUDE_STDERR_MAX_BOUNDS = (32.0, 2048.0)

# F-001/F-101: ANSI/C0/C1 → sentinel \x00 (не пробел), чтобы склейка со словом и вставка
# внутри токена не обходила _SECRET_RE; \x00 снимается после Pass 1, [\r\n\t]→пробел после Pass 2.
_STRIP_RE = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|\x1b[()][A-Z0-9]|\x1b[@-Z\\-_]|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)
_WS_CTRL_RE = re.compile(r"[\r\n\t]")
_SECRET_RE = re.compile(
    r"(?i)\b(?:authorization|cookie)[\"']?[ \t]*[:=][ \t]*[\"']?"
    r"(?:(?:bearer|basic)[ \t\x00]+)?[^\s\x00;]+(?:;[ \t]*[^\s\x00;]+)*"
    r"|\b(?:[A-Z0-9_]+_)?(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|AUTH|COOKIE)"
    r"[\"']?[ \t]*[:=][ \t]*[\"']?[^\s\x00]+"
    r"|\b(?:api[_-]?key|token|secret|password)[\"']?[ \t]*[:=][ \t]*[\"']?[^\s\x00]+"
    r"|\b(?:bearer|basic)[ \t\x00]+[^\s\x00]+"
    r"|\b(?:sk|pk|rk)[-_](?:[\x00\r\n\t]*[A-Za-z0-9_.-]){4,}"
    r"|\b(?:ghp|github_pat)_(?:[\x00\r\n\t]*[A-Za-z0-9_]){4,}"
    r"|\bAIza(?:[\x00\r\n\t]*[0-9A-Za-z_-]){8,}"
    r"|\beyJ(?:[\x00\r\n\t]*[A-Za-z0-9_-]){6,}"
    r"(?:[\x00\r\n\t]*\.(?:[\x00\r\n\t]*[A-Za-z0-9_-])+)*"
)


@dataclass(frozen=True, slots=True)
class AdmissionIdleConfig:
    """Неизменяемый снимок флагов и числовых параметров phase-idle admission."""

    phase_idle_timeout_enabled: bool = False
    active_ttl_sweep_enabled: bool = False
    admission_telemetry_enabled: bool = False
    claude_stderr_log_enabled: bool = False
    phase_idle_timeout_s: float = 30.0
    active_socket_timeout_s: float = 3600.0
    claude_stderr_max_chars: int = 240


def resolve_socket_timeout_for_phase(
    phase: str,
    cfg: AdmissionIdleConfig,
    configured_read_timeout_s: float | None = None,
) -> float:
    """Таймаут сокета для фазы; активный SSE никогда не режется idle-таймаутом.

    При выключенном флаге возвращается legacy-значение (configured либо active).
    Неизвестная фаза отклоняется через ValueError.
    """
    if phase not in ("idle", "active"):
        raise ValueError(f"unknown connection phase: {phase!r}")
    read_s = configured_read_timeout_s
    active = cfg.active_socket_timeout_s if read_s is None else read_s
    idle = (
        cfg.phase_idle_timeout_s
        if read_s is None
        else min(cfg.phase_idle_timeout_s, read_s)
    )
    return idle if (cfg.phase_idle_timeout_enabled and phase == "idle") else active


def sanitize_stderr_tail(raw: str, max_chars: int = 240) -> str:
    """Однострочный хвост: ANSI/C0/C1→sentinel \\x00, 2-pass редакция секретов, [\\r\\n\\t]→пробел."""
    marked = _STRIP_RE.sub("\x00", raw)
    pass1 = _SECRET_RE.sub("[REDACTED]", marked).replace("\x00", "")
    redacted = _WS_CTRL_RE.sub(" ", _SECRET_RE.sub("[REDACTED]", pass1))
    return (
        "..." + redacted[-max_chars:]
        if (max_chars > 0 and len(redacted) > max_chars)
        else redacted
    )


def check_legacy_max_http_connections_warning(
    env: Mapping[str, str], effective_admission_limit: int
) -> str | None:
    """Мёртвый BRIDGE_MAX_HTTP_CONNECTIONS: warning, если не равен effective лимиту.

    Отсутствует/пуст или валидный int == effective_limit → None (лимит не меняется).
    """
    raw = env.get(_LEGACY_MAX_CONN_ENV, "")
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        configured: int | None = int(stripped)
    except ValueError:
        configured = None
    sanitized = sanitize_stderr_tail(raw, 64)
    msg = (
        f"legacy_knob_ignored knob={_LEGACY_MAX_CONN_ENV} configured={sanitized} "
        f"effective_knob=BRIDGE_ADMISSION_LIMIT effective_limit={effective_admission_limit}"
    )
    return None if configured == effective_admission_limit else msg


def summarize_admission_snapshot(
    connections: Mapping[object, tuple[bool, float]],
    now: float,
    limit: int,
    overloaded_rejects: int,
) -> dict[str, int | float]:
    """Чистый снимок admission: active/idle/total/limit и возрасты (clamp >= 0, 3 знака)."""
    active = idle = 0
    max_idle_age = max_active_age = 0.0
    for is_active, changed_at in connections.values():
        age = _age_s(now, changed_at)
        if is_active:
            active += 1
            max_active_age = max(max_active_age, age)
        else:
            idle += 1
            max_idle_age = max(max_idle_age, age)
    return {
        "active": active,
        "idle": idle,
        "total": active + idle,
        "limit": limit,
        "max_idle_age_s": round(max_idle_age, 3),
        "max_active_age_s": round(max_active_age, 3),
        "overloaded_rejects": overloaded_rejects,
    }


def _age_s(now: float, changed_at: float) -> float:
    """Возраст >= 0.0; NaN/inf/отрицательная разница → 0.0."""
    delta = now - changed_at
    return delta if (math.isfinite(delta) and delta >= 0.0) else 0.0


def resolve_drain_actor(
    env: Mapping[str, str], pid: int, ppid: int, pgid: int
) -> dict[str, object]:
    """Атрибуция рестарта: sanitised BRIDGE_RESTART_ACTOR (иначе 'signal') + pid/ppid/pgid."""
    raw = env.get(_RESTART_ACTOR_ENV, "")
    actor = sanitize_stderr_tail(raw, 64).strip() if raw.strip() else ""
    return {"actor": actor or "signal", "pid": pid, "ppid": ppid, "pgid": pgid}


def format_claude_done_fields(
    turn_meta: tuple[str, str, str],
    out: Mapping[str, object],
    wall_s: float,
    cfg: AdmissionIdleConfig | None = None,
) -> str:
    """Строка done claude-p: 100% прежний формат; stderr_tail только при rc!=0 и флаге.

    turn_meta = (model, effort, tag); cfg=None означает fail-closed дефолты.
    Редактированный однострочный хвост err добавляется лишь когда
    cfg.claude_stderr_log_enabled и rc != 0 и err непуст; иначе формат прежний.
    """
    model, effort, tag = turn_meta
    settings = AdmissionIdleConfig() if cfg is None else cfg
    calls = out.get("tool_calls")
    text = out.get("text")
    rc = out.get("rc")
    line = (
        f"done model={model} effort={effort} rc={rc} state={out.get('state')} "
        f"tools={len(calls) if isinstance(calls, list) else 0} "
        f"out_bytes={len(text.encode()) if isinstance(text, str) else 0} "
        f"wall_s={wall_s:.1f} {tag}"
    )
    err = out.get("err")
    if settings.claude_stderr_log_enabled and rc != 0 and isinstance(err, str) and err:
        line += f" stderr_tail={sanitize_stderr_tail(err, settings.claude_stderr_max_chars)}"
    return line
