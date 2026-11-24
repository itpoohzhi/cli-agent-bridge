"""Вспомогательные политики очереди, сигналов, режимов и изоляции `X-Subagent-Id` для agy-bridge."""

from __future__ import annotations

import hashlib
import math
import os
import sys
import threading
import time
import weakref
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from core.adaptive_admission import OutcomeKind
from core.chat_key import resolve_chat_key
from core.session_continuity import session_key_for

from . import sqlite_tail_lifecycle
from .state_hygiene_policy import DisconnectOutcome, OrphanConfig, OrphanFsm

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


_DEFAULT_ORPHAN_FSM = OrphanFsm()


def decide_disconnect_outcome(
    tools_count: int,
    ttfc_received: bool,
    active_orphans: int = 0,
    fast_enabled: bool = False,
    orphan_max: int = 5,
) -> DisconnectOutcome:
    """Return DisconnectOutcome enum for a disconnect."""
    fsm = _DEFAULT_ORPHAN_FSM if orphan_max == 5 else OrphanFsm(OrphanConfig(orphan_max=orphan_max))
    return fsm.decide_disconnect(ttfc_received, tools_count, active_orphans, fast_enabled)


def should_detach_job_orphan(
    tools_count: int,
    ttfc_received: bool,
    active_orphans: int = 0,
    fast_enabled: bool = False,
    orphan_max: int = 5,
) -> bool:
    """Return True when a disconnect should detach as an orphan."""
    return (
        decide_disconnect_outcome(
            tools_count,
            ttfc_received,
            active_orphans=active_orphans,
            fast_enabled=fast_enabled,
            orphan_max=orphan_max,
        )
        is DisconnectOutcome.DETACH_ORPHAN
    )


def _finite_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class SqliteRoPoolBackoffError(RuntimeError):
    """Пул SQLite RO находится в окне временного backoff."""


def is_cold_sqlite_wal_wait(exc: BaseException, db_path: Path | None) -> bool:
    """Распознаёт штатное ожидание появления холодного WAL при существующей читаемой БД."""
    return sqlite_tail_lifecycle.is_cold_wal_error(exc, db_path)


def extract_run_ttfc_ms(run: object) -> float | None:
    first_s = _finite_float(getattr(run, "first_content_at", None))
    started_s = _finite_float(getattr(run, "started", None))
    if first_s is None or started_s is None:
        return None
    ttfc_ms = (first_s - started_s) * 1000.0
    return max(0.0, ttfc_ms) if math.isfinite(ttfc_ms) else None


_OUTCOME_MAP: dict[str, OutcomeKind] = {
    "done": OutcomeKind.OK,
    "capacity_exhausted": OutcomeKind.CAPACITY_EXHAUSTED,
    "client_gone": OutcomeKind.CANCELLED,
}


def release_admission_for_state(
    release_fn: Callable[..., object],
    ticket_id: int,
    out: Mapping[str, object],
    run: object | None = None,
) -> None:
    """Release an adaptive admission ticket from a terminal state mapping."""
    st = str(out.get("state") or "")
    ttfc = _finite_float(out.get("ttfc_ms"))
    if ttfc is None:
        ttfc = extract_run_ttfc_ms(run)
    release_fn(ticket_id, outcome=_OUTCOME_MAP.get(st, OutcomeKind.ERROR), ttfc_ms=ttfc)


def start_orphan_reaper(runtime: Any, interval_s: float = 1.0) -> Any:
    """Запускает один daemon-reaper без сильной ссылки на runtime."""
    interval = max(0.005, float(interval_s))
    if getattr(runtime, "_orphan_reaper_stop", None) is not None:
        return runtime
    stop = threading.Event()
    ref = weakref.ref(runtime)
    setattr(runtime, "_orphan_reaper_stop", stop)

    def worker() -> None:
        while not stop.wait(interval):
            current = ref()
            if current is None:
                return
            sweep = getattr(current, "sweep_orphans", None)
            if callable(sweep):
                try:
                    sweep()
                except Exception as exc:
                    setattr(current, "_orphan_reaper_errors", int(getattr(current, "_orphan_reaper_errors", 0)) + 1)
                    now = time.monotonic()
                    last = float(getattr(current, "_orphan_reaper_last_error_s", now - 60.0))
                    if now - last >= 60.0:
                        print(f"agy-orphan-reaper: sweep failed ({type(exc).__name__})", file=sys.stderr)
                        setattr(current, "_orphan_reaper_last_error_s", now)
            del sweep, current

    thread = threading.Thread(target=worker, name="agy-orphan-reaper", daemon=True)
    setattr(runtime, "_orphan_reaper_thread", thread)
    thread.start()
    return runtime


def stop_orphan_reaper(runtime: object, join_timeout_s: float = 1.0) -> None:
    if (stop := getattr(runtime, "_orphan_reaper_stop", None)) is not None:
        stop.set()
        thr = getattr(runtime, "_orphan_reaper_thread", None)
        if isinstance(thr, threading.Thread) and thr.is_alive() and thr is not threading.current_thread():
            thr.join(timeout=join_timeout_s)


def shutdown_hygiene_runtime(runtime: object) -> None:
    stop_orphan_reaper(runtime)
    if callable(clean := getattr(runtime, "shutdown_cleanup", None)):
        clean()


def notify_orphan_progress(runtime: object, pgid: int | None) -> None:
    if pgid is not None and callable(touch := getattr(runtime, "touch_progress", None)):
        touch(pgid)


def release_detached_pgid(runtime: object, pgid: int | None) -> bool:
    if pgid is None or not callable(release := getattr(runtime, "release_detached", None)):
        return False
    return bool(release(pgid))
