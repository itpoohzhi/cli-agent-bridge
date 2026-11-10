#!/usr/bin/env python3
"""OpenAI-совместимый мост к Antigravity CLI (`agy`) для DeepSeek Harness.

Один запрос /v1/chat/completions = один headless-ход CLI через канонический
лончер ~/.config/agy-launch/agy-cli.sh (egress-пиннинг: xray HTTP :10815,
резерв hy2 :10811; прямой вызов запрещён — гео РФ):

    printf '%s\\n' '<NDJSON>' | launcher \\
        --input-format stream-json --output-format stream-json \\
        --dangerously-skip-permissions \\
        --model <MODEL_ID> --effort <EFFORT> --print-timeout=0

Промпт уходит ИСКЛЮЧИТЕЛЬНО на stdin строкой NDJSON
`{"event":"user","message":{"role":"user","content":[{"type":"text","text":...}]}}`.
Флаг `-p` НЕ передаётся НИКОГДА: `agy -p --input-format stream-json`
разбирается неверно (`-p` съедает следующий флаг). Это проверенный факт 1.3.1.

Каталог моделей — `fleet.json` (env `AGY_BRIDGE_FLEET`): читается один раз при
старте, структурно проверяется (нарушение класса I — отказ старта). `id` модели —
БАЗА (`gemini-3.8-flash`), уровень мышления — отдельная ось `--effort`; значение
берётся строго из `efforts` каталога (никаких клампов и алиасов) и передаётся
ВСЕГДА: при пустом `reasoning_effort` подставляется `default_effort`, потому что
agy отвергает базу без effort — `--model "gemini-3.8-flash" requires --effort
(available: low, medium, high)` (проверено 2026-10-07 на 1.3.1).

Инструменты (tools) эмулируются общим ядром `core.tool_emulation` (OpenAI function
calling поверх текста):

  * если запрос пришёл без `tools` или с `tool_choice: "none"` — это текстовый ход
    (роль судьи/ревьюера): вся выдача идёт в `content`, `finish_reason="stop"`;
  * если запрос пришёл с `tools` — в промпт добавляется протокол `<tool_call>` ядра,
    agy запускается без нативных инструментов (режим `ask`), текст хода проходит
    `StreamNormalizer(strict_live=True)`: блоки `<tool_call>` уходят клиенту как
    `delta.tool_calls` / `message.tool_calls` с `finish_reason="tool_calls"`. После
    первого закрытого `</tool_call>` ход завершается сразу (группа процессов agy
    гасится), не дожидаясь фоновых задач CLI. Аварийный выключатель — флаг
    `tool_emulation_enabled` в dynamic_config.json / `AGY_TOOL_EMULATION_ENABLED=0`
    (прежний агентный ход с нативными инструментами agy).

События NDJSON разбираются как: `step_update` (`agent_response` -> текст,
`step_type: tool` -> трассировка в stderr, `state: DONE` -> завершение) и
`result` (`response` -> финальный текст, `usage` -> токены, `status`/`error`).

Мышление шагов (`reasoning_content`) идёт клиенту в реальном времени: пока шаг ещё
генерируется (`status=8`), подполе 20.3 его `step_payload` растёт в SQLite разговора
`~/.gemini/antigravity-cli/conversations/<cid>.db`. База открывается только на чтение
(`mode=ro`), разбор wire-формата — на stdlib. Источник вспомогателен и fail-open:
транскрипт `transcript_full.jsonl` остаётся минимальным источником. Включение — флаг
`SQLITE_REASONING_ENABLED` в `dynamic_config.json` (по умолчанию выключен) и аварийный
выключатель `AGY_SQLITE_REASONING_ENABLED=0`.

Политика хода «тихий агент» (AD-001..AD-005) выключена по умолчанию (кодовый False) и
включается флагами `dynamic_config.json` (JSON bool, перечитывается с TTL 1 с) либо env;
env приоритетнее файла (0/false/no/off — hard-off, 1/true/yes/on — включение):

  * `planner_content_streaming_enabled` / `AGY_PLANNER_CONTENT_STREAMING_ENABLED` —
    live `PLANNER_RESPONSE.content` из транскрипта с дедупликацией против stdout;
  * `emit_tool_trace` / `AGY_BRIDGE_EMIT_TOOL_TRACE` — безопасные маркеры нативных
    инструментов в `reasoning_content` (без args/result/путей);
  * `extended_timeout_enabled` / `AGY_EXTENDED_TIMEOUT_ENABLED` — idle 1800 с по активности
    stdout/transcript и потолок 3600 с (`AGY_IDLE_TIMEOUT_S`, `AGY_TIMEOUT_S`);
  * `graceful_timeout_on_partial` / `AGY_GRACEFUL_TIMEOUT_ON_PARTIAL` — timeout и
    idle_timeout после частичной выдачи завершаются настраиваемым `finish_reason`
    (по умолчанию "stop") вместо 504: `AGY_GRACEFUL_TIMEOUT_FINISH_REASON` или
    `graceful_timeout_finish_reason` в dynamic_config.json;
  * `step_scoped_usage_enabled` / `AGY_STEP_SCOPED_USAGE_ENABLED` — `usage` по окну
    последнего шага (prompt = input + cache последнего `PLANNER_RESPONSE`, completion =
    сумма output шагов хода) вместо накопительного `result.usage`; без валидного шага —
    ограниченная оценка для успешного хода с окном модели.

Изображения (метод `workspace-read`): `image_url` в NDJSON парсер agy не принимает, поэтому
проверенные data-URL (PNG/JPEG/GIF/WebP) кладутся файлами в `WORKSPACE/img-<uuid>` на время
хода, каталог отдаётся CLI через `--add-dir`, а в промпте они идут как `[image N]` и блок
`[attachments]` с абсолютными путями (модель читает их нативным view_file). Вход выключен по
умолчанию: флаг `IMAGE_INPUT_ENABLED` в `dynamic_config.json` (env `AGY_IMAGE_INPUT_ENABLED`
решает сразу) и proof модели в fleet.json (sha256 бинаря agy, версия метода, форматы, effort).
Проверка идёт до слота и spawn; запись на диск — только после захвата слота, удаление — в finally.

Секреты с диска не читаются: ключ авторизации берётся только из окружения
AGY_BRIDGE_KEY (его подкладывает start.sh из ~/.dsh/.env); в окружение дочернего
процесса ключ моста не передаётся. Прокси-переменные выставляет сам лончер.
"""

from __future__ import annotations

import collections
import copy
import base64
import hashlib
import json
import math
import os
import queue
import random
import re
import select
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, NamedTuple, cast, final

_BRIDGE_DIR = str(Path(__file__).resolve().parent)
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)

from agy_runtime.process_supervisor import (  # noqa: E402 # pyright: ignore[reportImplicitRelativeImport]
    ProcessSupervisor,
    ProcessSupervisorConfig,
)
from agy_runtime.account_pool import AccountPool, AccountPoolConfig  # noqa: E402 # pyright: ignore[reportImplicitRelativeImport]
from agy_runtime.stream_relay import StreamRelay  # noqa: E402 # pyright: ignore[reportImplicitRelativeImport]
from agy_runtime.arbiter_types import _StepState  # noqa: E402 # pyright: ignore[reportImplicitRelativeImport]
from agy_runtime.content_arbiter import _ContentArbiter  # noqa: E402 # pyright: ignore[reportImplicitRelativeImport]
from agy_runtime.media_normalizer import (  # noqa: E402 # pyright: ignore[reportImplicitRelativeImport]
    _IMAGE_OMITTED,
    _lower_keys,
    _classify_part,
    _part_text,
    _content_items,
    _image_part_canonical,
    _media_part_counts,
    _collect_image_parts_universal,
    _json_copy,
    _flatten_content_stripped,
    _strip_media_from_messages,
    _universal_render_messages,
)
from agy_runtime.tool_progress import (  # noqa: E402 # pyright: ignore[reportImplicitRelativeImport]
    _ToolProgress,
    _safe_tool_name,
    _format_tool_marker,
)

# Корень репозитория cli-agent-bridge: resolve() раскрывает симлинк деплоя
# (~/.dsh/bridges/agy-bridge -> <repo>/bridges/agy-bridge), parents[2] = <repo>.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.watchdog import (  # noqa: E402
    IDLE_TIMEOUT_S as _CORE_IDLE_TIMEOUT_S,
    WATCHDOG_INTERVAL_S as _CORE_WATCHDOG_INTERVAL_S,
    AdaptiveTimeoutController,
)
from core.usage_wire import normalize_prompt_cache_details  # noqa: E402
from core.proc_groups import spawn_registered  # noqa: E402
from core.subbridge_lifecycle import SubbridgeHooks, SubbridgeLifecycle  # noqa: E402
from core.stream_interruption_recovery import (  # noqa: E402
    InterruptionTailState,
    evaluate_graceful_interruption,
    is_transient_stream_interruption,
    resolve_done_turn_outcome,
    settle_error,
    tail_turn_facts,
    trusted_final_text,
)
from core.tool_emulation import (  # noqa: E402
    LiveParserError,
    RepetitionLoopDetected,
    StreamNormalizer,
    _messages_to_prompt as _core_messages_to_prompt,
    _tool_choice_none,
    build_tool_schemas,
    sanitize_tool_call,
)

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
HOST = os.environ.get("AGY_BRIDGE_HOST", "127.0.0.1")
AUTH_KEY = os.environ.get("AGY_BRIDGE_KEY", "").strip()
LAUNCHER = os.environ.get(
    "AGY_LAUNCHER", str(HOME / ".config" / "agy-launch" / "agy-cli.sh")
)
FLEET_PATH = Path(os.environ.get("AGY_BRIDGE_FLEET", "") or str(ROOT / "fleet.json"))
ENV_MODEL = os.environ.get("AGY_BRIDGE_MODEL", "").strip()
WORKSPACE = ROOT / "workspace"
PRINT_TIMEOUT = os.environ.get("AGY_BRIDGE_PRINT_TIMEOUT", "0")

def _env_float(name: str, default: float, low: float, high: float) -> float:
    """Float из окружения; пустое/невалидное/неконечное/вне [low, high] -> default."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if not math.isfinite(value) or not (low <= value <= high):
        return default
    return value


def _env_bool(name: str, default: bool) -> bool:
    """Булев флаг окружения (1/true/yes/on, 0/false/no/off); иное значение -> default."""
    raw = os.environ.get(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def _env_int(name: str, default: int, low: int, high: int) -> int:
    """Целое из окружения, зажатое в [low, high]; невалидное значение -> default.

    Семантика зажатия (clamp), а не fallback при выходе за границы, сохранена
    как исторический контракт: существующий тест NDJSON-бюджета ожидает
    ``1000 -> low`` и ``200000 -> high`` для ``AGY_BRIDGE_MAX_PROMPT_BYTES``.
    """
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return min(high, max(low, value))


def _env_int_with_zero_cap(
    name: str, default: int, low: int, high: int, zero_cap: int
) -> int:
    """Целое из окружения; 0 -> zero_cap, вне [low, high]/невалидное -> default."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value == 0:
        return zero_cap
    if not (low <= value <= high):
        return default
    return value


def _chain_float(
    names: tuple[str, ...], default: float, low: float, high: float
) -> float:
    """Первое заданное имя из цепочки (каноническое -> легаси); иначе default."""
    for name in names:
        if os.environ.get(name, "").strip():
            return _env_float(name, default, low, high)
    return default


def _chain_int(names: tuple[str, ...], default: int, low: int, high: int) -> int:
    """Первое заданное имя из цепочки (каноническое -> легаси); иначе default."""
    for name in names:
        if os.environ.get(name, "").strip():
            return _env_int(name, default, low, high)
    return default


def _chain_bool(names: tuple[str, ...], default: bool) -> bool:
    """Первое заданное имя из цепочки (каноническое -> легаси); иначе default."""
    for name in names:
        if os.environ.get(name, "").strip():
            return _env_bool(name, default)
    return default


@dataclass(frozen=True)
class _BridgeConfig:
    """Единый снимок эксплуатационных параметров моста (ADR-0014).

    Дефолты равны историческим константам; значения читаются из
    ``AGY_BRIDGE_*`` с легаси-алиасами там, где они существовали.
    """

    port: int = 9887
    max_concurrent: int = 32  # Дефолт датакласса=32 и runtime default=32 в _build_bridge_config
    wal_max_bytes: int = 16 * 1024 * 1024
    queue_timeout_s: int = 900
    timeout_s: int = 1800
    keepalive_s: float = 15.0
    first_token_timeout_s: float = 120.0
    transcript_poll_s: float = 0.05
    req_budget_s: float = 3600.0
    reserve_s: float = 5.5
    min_attempt_s: float = 1.0
    ext_max_timeout_s: float = 3600.0
    ext_idle_timeout_s: float = 1800.0
    idle_timeout_s: float = 300.0
    watchdog_interval_s: float = 5.0
    kill_term_grace_s: float = 2.0
    proc_exit_wait_s: float = 0.05
    drain_window_s: float = 0.35
    drain_poll_step_s: float = 0.05
    join_timeout_s: float = 0.15
    final_flush_s: float = 5.0
    session_max_ttl_s: float = 86400.0
    session_max_turns: int = 30
    sweep_cutoff_s: float = 3600.0
    max_content_bytes_per_turn: int = 8 * 1024 * 1024
    max_reasoning_bytes_per_turn: int = 2 * 1024 * 1024
    max_step_blob_bytes: int = 262144
    max_steps_tracked: int = 128
    max_tool_markers_per_turn: int = 32
    max_retained_divergent_bytes: int = 65536
    transcript_read_max: int = 4 * 1024 * 1024
    dynamic_config_max_bytes: int = 65536
    usage_step_cap: int = 16384
    sqlite_row_limit: int = 16
    breaker_failures: int = 3
    breaker_cooldown_s: float = 30.0
    breaker_probe_lease_s: float = 60.0
    retry_capacity_tenths: int = 30
    retry_credit_tenths: int = 2
    retry_cost_tenths: int = 10
    poll_bucket_capacity_tenths: int = 30
    poll_bucket_refill_tenths_per_s: int = 20
    poll_cost_tenths: int = 10
    liveness_gated_timeout_enabled: bool = True

    def __post_init__(self) -> None:
        cap = max(1.0, self.req_budget_s - self.reserve_s)
        object.__setattr__(self, "idle_timeout_s", min(self.idle_timeout_s, cap))
        object.__setattr__(self, "min_attempt_s", min(self.min_attempt_s, cap))
        object.__setattr__(
            self,
            "retry_capacity_tenths",
            max(self.retry_capacity_tenths, self.retry_cost_tenths),
        )
        object.__setattr__(
            self,
            "poll_bucket_capacity_tenths",
            max(self.poll_bucket_capacity_tenths, self.poll_cost_tenths),
        )

    @property
    def breaker_failures_to_open(self) -> int:
        return self.breaker_failures

    @property
    def retry_refill_per_sec_tenths(self) -> int:
        return self.retry_credit_tenths

    @property
    def poll_refill_per_sec_tenths(self) -> int:
        return self.poll_bucket_refill_tenths_per_s


def _build_bridge_config() -> _BridgeConfig:
    """Собрать снимок конфигурации из текущего окружения."""
    return _BridgeConfig(
        port=_env_int("AGY_BRIDGE_PORT", 9887, 1, 65535),
        max_concurrent=_env_int("AGY_BRIDGE_MAX_CONCURRENT", 32, 1, 128),
        wal_max_bytes=_env_int(
            "AGY_BRIDGE_WAL_MAX_BYTES", 16 * 1024 * 1024, 1, 2147483647
        ),
        queue_timeout_s=_chain_int(
            ("AGY_BRIDGE_QUEUE_TIMEOUT_S", "AGY_BRIDGE_QUEUE_TIMEOUT"), 900, 1, 86400
        ),
        timeout_s=_chain_int(
            ("AGY_BRIDGE_TIMEOUT_S", "AGY_BRIDGE_TIMEOUT"), 1800, 1, 86400
        ),
        keepalive_s=_chain_float(
            ("AGY_BRIDGE_KEEPALIVE_S", "AGY_BRIDGE_KEEPALIVE"), 15.0, 0.5, 300.0
        ),
        first_token_timeout_s=_chain_float(
            ("AGY_BRIDGE_FIRST_TOKEN_TIMEOUT_S", "AGY_BRIDGE_FIRST_TOKEN_TIMEOUT"),
            120.0,
            5.0,
            3600.0,
        ),
        transcript_poll_s=_chain_float(
            ("AGY_BRIDGE_TRANSCRIPT_POLL_S", "AGY_BRIDGE_TRANSCRIPT_POLL"),
            0.05,
            0.01,
            10.0,
        ),
        req_budget_s=_env_float("AGY_BRIDGE_REQ_BUDGET_S", 3600.0, 10.0, 86400.0),
        reserve_s=_chain_float(
            ("AGY_BRIDGE_RESERVE_S", "AGY_BRIDGE_T_RESERVE_S"), 5.5, 0.5, 60.0
        ),
        min_attempt_s=_env_float("AGY_BRIDGE_MIN_ATTEMPT_S", 1.0, 0.1, 300.0),
        ext_max_timeout_s=_chain_float(
            ("AGY_BRIDGE_EXT_MAX_TIMEOUT_S", "AGY_TIMEOUT_S"), 3600.0, 10.0, 86400.0
        ),
        ext_idle_timeout_s=_chain_float(
            (
                "AGY_BRIDGE_IDLE_TIMEOUT_S",
                "AGY_IDLE_TIMEOUT_S",
                "AGY_BRIDGE_IDLE_TIMEOUT",
            ),
            1800.0,
            5.0,
            86400.0,
        ),
        idle_timeout_s=_chain_float(
            ("AGY_BRIDGE_BASE_IDLE_TIMEOUT_S", "AGY_BRIDGE_IDLE_TIMEOUT"),
            float(_CORE_IDLE_TIMEOUT_S),
            5.0,
            86400.0,
        ),
        watchdog_interval_s=_env_float(
            "AGY_BRIDGE_WATCHDOG_INTERVAL_S",
            float(_CORE_WATCHDOG_INTERVAL_S),
            0.5,
            60.0,
        ),
        kill_term_grace_s=_env_float("AGY_BRIDGE_KILL_TERM_GRACE_S", 2.0, 0.1, 30.0),
        proc_exit_wait_s=_env_float("AGY_BRIDGE_PROC_EXIT_WAIT_S", 0.05, 0.01, 60.0),
        drain_window_s=_chain_float(
            ("AGY_BRIDGE_DRAIN_WINDOW_S", "AGY_BRIDGE_TRANSCRIPT_GRACE"),
            0.35,
            0.05,
            120.0,
        ),
        drain_poll_step_s=_env_float("AGY_BRIDGE_DRAIN_POLL_STEP_S", 0.05, 0.01, 2.0),
        join_timeout_s=_chain_float(
            ("AGY_BRIDGE_JOIN_TIMEOUT_S", "AGY_BRIDGE_DRAIN_JOIN"), 0.15, 0.05, 10.0
        ),
        final_flush_s=_chain_float(
            ("AGY_BRIDGE_FINAL_FLUSH_S", "AGY_BRIDGE_T_FINAL_FLUSH_S"), 5.0, 0.5, 60.0
        ),
        session_max_ttl_s=_env_float(
            "AGY_BRIDGE_SESSION_MAX_TTL_S", 86400.0, 60.0, 604800.0
        ),
        session_max_turns=_env_int("AGY_BRIDGE_SESSION_MAX_TURNS", 30, 1, 1000),
        sweep_cutoff_s=_env_float("AGY_BRIDGE_SWEEP_CUTOFF_S", 3600.0, 60.0, 86400.0),
        max_content_bytes_per_turn=_env_int_with_zero_cap(
            "AGY_BRIDGE_MAX_CONTENT_BYTES", 8388608, 1024, 268435456, 268435456
        ),
        max_reasoning_bytes_per_turn=_env_int_with_zero_cap(
            "AGY_BRIDGE_MAX_REASONING_BYTES", 2097152, 1024, 67108864, 67108864
        ),
        max_step_blob_bytes=_env_int(
            "AGY_BRIDGE_MAX_STEP_BLOB_BYTES", 262144, 1024, 16777216
        ),
        max_steps_tracked=_chain_int(
            ("AGY_BRIDGE_MAX_STEPS", "AGY_BRIDGE_MAX_STEPS_TRACKED"), 128, 1, 4096
        ),
        max_tool_markers_per_turn=_env_int("AGY_BRIDGE_MAX_TOOL_MARKERS", 32, 1, 1024),
        max_retained_divergent_bytes=_chain_int(
            (
                "AGY_BRIDGE_MAX_DIVERGENT_BYTES",
                "AGY_BRIDGE_MAX_RETAINED_DIVERGENT_BYTES",
            ),
            65536,
            1024,
            1048576,
        ),
        transcript_read_max=_env_int(
            "AGY_BRIDGE_TRANSCRIPT_READ_MAX", 4194304, 1024, 67108864
        ),
        dynamic_config_max_bytes=_env_int(
            "AGY_BRIDGE_DYNAMIC_CONFIG_MAX_BYTES", 65536, 1024, 1048576
        ),
        usage_step_cap=_env_int("AGY_BRIDGE_USAGE_STEP_CAP", 16384, 128, 1048576),
        sqlite_row_limit=_env_int("AGY_BRIDGE_SQLITE_ROW_LIMIT", 16, 1, 1024),
        breaker_failures=_env_int("AGY_BRIDGE_BREAKER_FAILURES", 3, 1, 100),
        breaker_cooldown_s=_env_float("AGY_BRIDGE_BREAKER_COOLDOWN_S", 30.0, 1.0, 3600.0),
        breaker_probe_lease_s=_env_float("AGY_BRIDGE_BREAKER_PROBE_LEASE_S", 60.0, 1.0, 3600.0),
        retry_capacity_tenths=_env_int("AGY_BRIDGE_RETRY_CAPACITY_TENTHS", 30, 10, 1000),
        retry_credit_tenths=_chain_int(
            (
                "AGY_BRIDGE_RETRY_REFILL_PER_SEC_TENTHS",
                "AGY_BRIDGE_RETRY_CREDIT_TENTHS",
            ),
            2,
            1,
            100,
        ),
        retry_cost_tenths=_env_int("AGY_BRIDGE_RETRY_COST_TENTHS", 10, 1, 100),
        poll_bucket_capacity_tenths=_env_int(
            "AGY_BRIDGE_POLL_BUCKET_CAPACITY_TENTHS", 30, 10, 1000
        ),
        poll_bucket_refill_tenths_per_s=_chain_int(
            (
                "AGY_BRIDGE_POLL_REFILL_PER_SEC_TENTHS",
                "AGY_BRIDGE_POLL_BUCKET_REFILL_TENTHS_PER_S",
            ),
            20,
            1,
            100,
        ),
        poll_cost_tenths=_env_int("AGY_BRIDGE_POLL_COST_TENTHS", 10, 1, 100),
        liveness_gated_timeout_enabled=_chain_bool(
            (
                "AGY_BRIDGE_LIVENESS_GATED_TIMEOUT_ENABLED",
                "AGY_LIVENESS_GATED_TIMEOUT_ENABLED",
            ),
            True,
        ),
    )


_config_lock = threading.Lock()
_config: _BridgeConfig = _build_bridge_config()


def get_bridge_config() -> _BridgeConfig:
    """Текущий снимок конфигурации (неизменяемый)."""
    with _config_lock:
        return _config


def _build_steps_sql(config: _BridgeConfig) -> str:
    """SQL шагов транскрипта с лимитами из снимка конфигурации."""
    return (
        "SELECT idx, status, length(step_payload) AS blob_len, "
        + "CASE WHEN length(step_payload) <= %d THEN step_payload ELSE NULL END AS step_payload "
        + "FROM steps WHERE step_type = %d AND idx >= ? AND status IN (%d, %d) "
        + "ORDER BY idx ASC LIMIT %d"
    ) % (
        config.max_step_blob_bytes,
        STEP_TYPE_PLANNER,
        STEP_STATUS_GENERATING,
        STEP_STATUS_DONE,
        config.sqlite_row_limit,
    )


class _FairSlotSemaphore:
    """FIFO semaphore retaining each thread's position across polling timeouts.

    A caller abandoning a timed-out acquisition must call cancel_wait().
    """

    def __init__(self, value: int) -> None:
        from collections import deque

        if value < 1:
            raise ValueError("slot count must be positive")
        self._capacity = value
        self._active = 0
        self._waiters = deque()
        self._lock = threading.Lock()
        self._local = threading.local()

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active

    @property
    def waiters_count(self) -> int:
        with self._lock:
            return len(self._waiters)

    def _wake_head(self) -> None:
        if self._waiters and self._active < self._capacity:
            self._waiters[0].set()

    def cancel_wait(self) -> None:
        """Remove the calling thread's pending acquisition, if any."""
        waiter = getattr(self._local, "waiter", None)
        if waiter is None:
            return
        with self._lock:
            if waiter in self._waiters:
                self._waiters.remove(waiter)
            del self._local.waiter
            self._wake_head()

    def waiting(self):
        from contextlib import contextmanager

        @contextmanager
        def position():
            if getattr(self._local, "waiter", None) is not None:
                raise RuntimeError("nested slot wait")
            waiter = threading.Event()
            with self._lock:
                self._local.waiter = waiter
                self._waiters.append(waiter)
                self._wake_head()
            try:
                yield
            finally:
                self.cancel_wait()

        return position()

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        if timeout is not None and (timeout < 0 or not blocking):
            raise ValueError("invalid semaphore timeout")
        deadline = None if timeout is None else time.monotonic() + timeout
        waiter = getattr(self._local, "waiter", None)
        with self._lock:
            if waiter is None:
                if not self._waiters and self._active < self._capacity:
                    self._active += 1
                    return True
                if not blocking:
                    return False
                waiter = threading.Event()
                self._local.waiter = waiter
                self._waiters.append(waiter)
            self._wake_head()
        try:
            while True:
                with self._lock:
                    if self._waiters[0] is waiter and self._active < self._capacity:
                        self._waiters.popleft()
                        del self._local.waiter
                        self._active += 1
                        self._wake_head()
                        return True
                    waiter.clear()
                remaining = None if deadline is None else deadline - time.monotonic()
                if not blocking or (remaining is not None and remaining <= 0):
                    return False
                waiter.wait(remaining)
        except BaseException:
            self.cancel_wait()
            raise

    def release(self) -> None:
        with self._lock:
            if self._active == 0:
                raise ValueError("semaphore released too many times")
            self._active -= 1
            self._wake_head()


def reload_bridge_config() -> _BridgeConfig:
    global _config, _slots, _account_pool
    """Перечитать окружение, обновить снимок и глобальные константы (для тестов)."""
    global _config, _slots
    config = _build_bridge_config()
    with _config_lock:
        _config = config
    _apply_bridge_config(config)
    return config


def _apply_bridge_config(config: _BridgeConfig) -> None:
    """Привязать глобальные константы модуля к снимку конфигурации."""
    g = globals()
    g["PORT"] = config.port
    g["MAX_CONCURRENT"] = config.max_concurrent
    g["QUEUE_TIMEOUT_S"] = config.queue_timeout_s
    g["TIMEOUT_S"] = config.timeout_s
    g["KEEPALIVE_S"] = config.keepalive_s
    g["FIRST_TOKEN_TIMEOUT_S"] = config.first_token_timeout_s
    g["TRANSCRIPT_POLL_S"] = config.transcript_poll_s
    g["T_REQ_BUDGET_S"] = config.req_budget_s
    g["T_RESERVE_S"] = config.reserve_s
    g["T_MIN_ATTEMPT_S"] = config.min_attempt_s
    g["EXT_MAX_TIMEOUT_S"] = config.ext_max_timeout_s
    g["EXT_IDLE_TIMEOUT_S"] = config.ext_idle_timeout_s
    g["IDLE_TIMEOUT_S"] = config.idle_timeout_s
    g["WATCHDOG_INTERVAL_S"] = config.watchdog_interval_s
    g["KILL_TERM_GRACE_S"] = config.kill_term_grace_s
    g["PROC_EXIT_WAIT_S"] = config.proc_exit_wait_s
    g["DRAIN_WINDOW_S"] = config.drain_window_s
    g["DRAIN_POLL_STEP_S"] = config.drain_poll_step_s
    g["JOIN_TIMEOUT_S"] = config.join_timeout_s
    g["T_FINAL_FLUSH_S"] = config.final_flush_s
    g["SESSION_MAX_TTL_S"] = config.session_max_ttl_s
    g["SESSION_MAX_TURNS"] = config.session_max_turns
    g["SWEEP_CUTOFF_S"] = config.sweep_cutoff_s
    g["MAX_CONTENT_BYTES_PER_TURN"] = config.max_content_bytes_per_turn
    g["MAX_CONTENT_STEPS"] = config.max_steps_tracked
    g["MAX_REASONING_BYTES_PER_TURN"] = config.max_reasoning_bytes_per_turn
    g["MAX_STEP_BLOB_BYTES"] = config.max_step_blob_bytes
    g["MAX_STEPS_TRACKED"] = config.max_steps_tracked
    g["MAX_TOOL_MARKERS_PER_TURN"] = config.max_tool_markers_per_turn
    g["MAX_RETAINED_DIVERGENT_BYTES"] = config.max_retained_divergent_bytes
    g["TRANSCRIPT_READ_MAX"] = config.transcript_read_max
    g["DYNAMIC_CONFIG_MAX_BYTES"] = config.dynamic_config_max_bytes
    g["USAGE_STEP_CAP"] = config.usage_step_cap
    g["SQLITE_ROW_LIMIT"] = config.sqlite_row_limit
    g["BREAKER_FAILURES_TO_OPEN"] = config.breaker_failures
    g["BREAKER_COOLDOWN_S"] = config.breaker_cooldown_s
    g["BREAKER_PROBE_LEASE_S"] = config.breaker_probe_lease_s
    g["RETRY_CAPACITY_TENTHS"] = config.retry_capacity_tenths
    g["RETRY_CREDIT_TENTHS"] = config.retry_credit_tenths
    g["RETRY_REFILL_PER_SEC_TENTHS"] = config.retry_refill_per_sec_tenths
    g["RETRY_COST_TENTHS"] = config.retry_cost_tenths
    g["POLL_BUCKET_CAPACITY_TENTHS"] = config.poll_bucket_capacity_tenths
    g["POLL_BUCKET_REFILL_TENTHS_PER_S"] = config.poll_bucket_refill_tenths_per_s
    g["POLL_REFILL_PER_SEC_TENTHS"] = config.poll_refill_per_sec_tenths
    g["POLL_BUCKET_COST_TENTHS"] = config.poll_cost_tenths
    g["DEFAULT_LIVENESS_GATED_TIMEOUT_ENABLED"] = config.liveness_gated_timeout_enabled
    # STEP_TYPE_*/STEP_STATUS_* определены ниже; SQL пересобирается, когда они есть.
    if "STEP_TYPE_PLANNER" in g:
        g["_STEPS_SQL"] = _build_steps_sql(config)
    if "_slots" in g:
        g["_slots"] = _FairSlotSemaphore(config.max_concurrent)


_apply_bridge_config(_config)

# Явные привязки для статического анализа; reload обновляет их через globals().
PORT = _config.port
MAX_CONCURRENT = _config.max_concurrent
QUEUE_TIMEOUT_S = _config.queue_timeout_s
TIMEOUT_S = _config.timeout_s
KEEPALIVE_S = _config.keepalive_s
FIRST_TOKEN_TIMEOUT_S = _config.first_token_timeout_s


# ADR-0008: kill-switch'и защиты истории, персистентности сессий и повтора на 502/503.
AGY_BRIDGE_ENABLE_HEAD_PRUNING = _env_bool("AGY_BRIDGE_ENABLE_HEAD_PRUNING", True)
AGY_BRIDGE_ENABLE_SESSION_PERSISTENCE = _env_bool(
    "AGY_BRIDGE_ENABLE_SESSION_PERSISTENCE", True
)
AGY_BRIDGE_ENABLE_TRANSIENT_502_RECOVERY = _env_bool(
    "AGY_BRIDGE_ENABLE_TRANSIENT_502_RECOVERY", True
)
# Потолок строки NDJSON на stdin agy (байты UTF-8). agy молча режет хвост входа
# около 133 КБ, поэтому верхняя граница жёстко 96 КиБ; ниже 16 КиБ не опускаем.
PROMPT_MAX_NDJSON_BYTES_LOW = 16384
PROMPT_MAX_NDJSON_BYTES_HIGH = 98304
PROMPT_MAX_NDJSON_BYTES = _env_int(
    "AGY_BRIDGE_MAX_PROMPT_BYTES",
    PROMPT_MAX_NDJSON_BYTES_HIGH,
    PROMPT_MAX_NDJSON_BYTES_LOW,
    PROMPT_MAX_NDJSON_BYTES_HIGH,
)
# Минимум головы и хвоста якорного блока при пропорциональном сжатии (байты).
PRUNE_EDGE_MIN_BYTES = _env_int("AGY_BRIDGE_PRUNE_EDGE_MIN_BYTES", 512, 512, 8192)
# Завершённые напоминания и точные форматы снимка/уведомлений (ADR-0019).
SYNTHETIC_REMINDER_RE = re.compile(
    r"<system-reminder>(?:(?!</?system-reminder>).)*</system-reminder>", re.DOTALL
)
SYNTHETIC_RUNTIME_RE = re.compile(
    r"Current runtime context\. This snapshot supersedes earlier "
    r"(?:runtime-context )?snapshots\."
    r'(?:\n\n?Current working directory: "[^"\n]+"\.)?'
)
SYNTHETIC_POLICY_RE = re.compile(
    r'The approval policy changed from "[^"\n]+" to "[^"\n]+" '
    r"\(changed by the user\)\."
)
# Служебное уведомление DSH об одобрении/отказе инструмента — синтетика только при
# точном совпадении всего тела; любой иной текст `The user approved ...` — ввод
# человека (ADR-0019, Cycle 4 F-001).
SYNTHETIC_NOTICE_RE = re.compile(
    r"The user (?:approved|rejected)(?: the)? (?:bash|command|tool)"
    r"(?: command| call)?(?:\.)?",
    re.IGNORECASE,
)
# Сверх этого числа реальных user текущего хода якорями остаются только
# первый (исходная цель) и последние ANCHOR_USER_TAIL_COUNT (ADR-0019, Cycle 5 F-005).
ANCHOR_USER_NO_ASSISTANT_MAX = _env_int(
    "AGY_BRIDGE_ANCHOR_USER_NO_ASSISTANT_MAX", 5, 1, 100000
)
ANCHOR_USER_TAIL_COUNT = _env_int("AGY_BRIDGE_ANCHOR_USER_TAIL_COUNT", 3, 1, 100000)
HISTORY_PRUNED_MARKER = (
    "[ранняя история диалога опущена мостом для соблюдения лимита контекста]"
)
MIDDLE_PRUNED_MARKER = (
    "\n[... часть содержимого сообщения опущена мостом для соблюдения лимита"
    " контекста agy ...]\n"
)


# Мышление шагов agy: CLI кладёт его в транскрипт разговора пошагово, в середине
# хода. Путь и имя файла фиксированы CLI (проверено на agy 1.3.1).
# Изолированный профиль <clean-home> дочерних процессов agy (Zero-Canon): без
# AGENTS.md/GEMINI.md/hooks.json пользователя; transcript и SQLite — внутри него.
_AGY_HOME_LOCK = threading.Lock()
_AGY_HOME_INITIALIZED = False
# Верифицированный (resolved) корень <clean-home>: фиксируется под _AGY_HOME_LOCK
# при первой успешной проверке; последующая подмена пути отвергается.
_VERIFIED_CLEAN_HOME: Path | None = None
CLEAN_HOME_DIR = Path(
    os.environ.get("AGY_BRIDGE_CLEAN_HOME", "")
    or str(WORKSPACE / "runtime" / "agy-home")
).resolve()
BRAIN_DIR = Path(
    os.environ.get("AGY_BRIDGE_BRAIN", "")
    or str(CLEAN_HOME_DIR / ".gemini" / "antigravity-cli" / "brain")
).resolve()
TRANSCRIPT_NAME = "transcript_full.jsonl"
TRANSCRIPT_FALLBACK_NAME = "transcript.jsonl"
TRANSCRIPT_POLL_S = get_bridge_config().transcript_poll_s
TRANSCRIPT_READ_MAX = get_bridge_config().transcript_read_max

# Живой источник мышления: SQLite-база разговора agy (таблица `steps`, шаг
# планировщика `step_type=15`, подполе 20.3 `step_payload` растёт в `status=8`).
# База открывается только на чтение; транскрипт остаётся минимальным источником.
CONV_DIR = Path(
    os.environ.get("AGY_BRIDGE_CONVERSATIONS", "")
    or str(CLEAN_HOME_DIR / ".gemini" / "antigravity-cli" / "conversations")
).resolve()
# Бинарь agy: его идентичность (mtime_ns, size) ключует семантический canary.
AGY_BIN = os.environ.get("AGY_BRIDGE_AGY_BIN", "") or str(
    HOME / ".local" / "bin" / "agy.real"
)
SQLITE_POLL_S = _env_float("AGY_BRIDGE_SQLITE_POLL", 0.5, 0.5, 2.0)
# Рантайм-флаг SQLITE_REASONING_ENABLED лежит рядом с server.py (в git не коммитится).
DYNAMIC_CONFIG_PATH = ROOT / "dynamic_config.json"
FLAG_NAME = "SQLITE_REASONING_ENABLED"
FLAG_TTL_S = 1.0
# Процесс вышел: окно финального дренирования источников мышления. Env
# AGY_BRIDGE_TRANSCRIPT_GRACE задаёт само окно, граница DRAIN_MAX_S жёсткая.
DRAIN_MAX_S = 0.50
DRAIN_WINDOW_S = get_bridge_config().drain_window_s
DRAIN_MIN_S = min(_env_float("AGY_BRIDGE_DRAIN_MIN", 0.15, 0.05, 0.25), DRAIN_WINDOW_S)
DRAIN_POLL_STEP_S = get_bridge_config().drain_poll_step_s
JOIN_TIMEOUT_S = get_bridge_config().join_timeout_s
PROC_EXIT_WAIT_S = get_bridge_config().proc_exit_wait_s
# Потолки памяти и работы одной итерации опроса.
MAX_REASONING_BYTES_PER_TURN = get_bridge_config().max_reasoning_bytes_per_turn
MAX_STEP_BLOB_BYTES = get_bridge_config().max_step_blob_bytes
MAX_STEPS_TRACKED = get_bridge_config().max_steps_tracked
SQLITE_ROW_LIMIT = get_bridge_config().sqlite_row_limit
# Константы схемы привязаны к agy 1.4.9 и подтверждаются canary.
STEP_TYPE_PLANNER = 15
STEP_STATUS_GENERATING = 8
STEP_STATUS_DONE = 3
_STEPS_SQL = _build_steps_sql(get_bridge_config())
# cid, из которого строится путь к базе, обязан быть hex-строкой с дефисами.
_CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
_STEP_INDEX_RE = re.compile(rb'"step_index"\s*:\s*(\d+)')
# Процессные guardrails (AD-005): breaker, бюджеты, окно проб.
BREAKER_FAILURES_TO_OPEN = get_bridge_config().breaker_failures
BREAKER_COOLDOWN_S = get_bridge_config().breaker_cooldown_s
BREAKER_PROBE_LEASE_S = get_bridge_config().breaker_probe_lease_s
RETRY_CAPACITY_TENTHS = get_bridge_config().retry_capacity_tenths
RETRY_CREDIT_TENTHS = get_bridge_config().retry_credit_tenths
RETRY_REFILL_PER_SEC_TENTHS = get_bridge_config().retry_refill_per_sec_tenths
RETRY_COST_TENTHS = get_bridge_config().retry_cost_tenths
POLL_BUCKET_CAPACITY_TENTHS = get_bridge_config().poll_bucket_capacity_tenths
POLL_BUCKET_REFILL_TENTHS_PER_S = get_bridge_config().poll_bucket_refill_tenths_per_s
POLL_REFILL_PER_SEC_TENTHS = get_bridge_config().poll_refill_per_sec_tenths
POLL_BUCKET_COST_TENTHS = get_bridge_config().poll_cost_tenths
RETRY_PAUSE_CAP_S = 2.0
# Сквозные бюджеты запроса (AD-003/AD-004). Резерв 5.5 с = drain 0.5 + финальный flush 5.0.
T_REQ_BUDGET_S = get_bridge_config().req_budget_s
T_DRAIN_MAX_S = 0.5
T_FINAL_FLUSH_S = get_bridge_config().final_flush_s
T_RESERVE_S = get_bridge_config().reserve_s
T_MIN_ATTEMPT_S = get_bridge_config().min_attempt_s
# Настроенные idle/max при extended_timeout_enabled (AD-003): idle 1800 с, потолок 3600 с.
EXT_IDLE_TIMEOUT_S = get_bridge_config().ext_idle_timeout_s
EXT_MAX_TIMEOUT_S = get_bridge_config().ext_max_timeout_s
# Границы арбитра planner-контента одного хода (AD-001).
MAX_CONTENT_STEPS = MAX_STEPS_TRACKED
MAX_CONTENT_BYTES_PER_TURN = get_bridge_config().max_content_bytes_per_turn
MAX_TOOL_MARKERS_PER_TURN = get_bridge_config().max_tool_markers_per_turn
# Расходящийся (непрефиксный) planner-текст удерживается для graceful-хвоста до 64 КиБ.
MAX_RETAINED_DIVERGENT_BYTES = get_bridge_config().max_retained_divergent_bytes
# Закрытый список имён нативных инструментов для маркера прогресса (AD-002).
TOOL_NAME_ALLOWLIST = frozenset(
    {
        "run_command",
        "read_file",
        "write_file",
        "edit_file",
        "manage_task",
        "search_web",
        "search_marketplace",
        "ask_question",
        "schedule",
        "send_message",
        "invoke_subagent",
        "define_subagent",
        "manage_subagents",
        "list_resources",
        "read_resource",
        "grep_search",
        "find_by_name",
        "list_dir",
        "view_file_outline",
        "view_code_item",
        "replace_file_content",
        "multi_replace_file_content",
        "command_status",
        "send_command_input",
        "read_url_content",
        "view_content_chunk",
        "browser_subagent",
        "generate_image",
        "task_boundary",
        "notify_user",
        "bash",
        "glob",
        "grep",
        "read",
        "edit",
        "write",
    }
)
_SAFE_MCP_TOOL_RE = re.compile(r"mcp_[a-z0-9_-]{1,32}_[a-z0-9_]{1,32}\Z")

# Effort-оси. `--effort` у agy принимает low|medium|high; id модели — база без уровня,
# уровень всегда уходит отдельным флагом (см. модуль-docstring).
EFFORT_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")
CLI_EFFORT_LEVELS = ("low", "medium", "high")
IMAGE_STATUSES = ("unsupported", "unverified", "probe", "confirmed")
# Доставка изображений агенту: проверенные файлы в WORKSPACE/img-<uuid>, каталог отдаётся
# через `--add-dir`, модель читает их нативным view_file. Прямой image_url в NDJSON
# парсер agy не принимает (см. fleet.json, proof 1.3.1).
IMPLEMENTED_METHODS = {"workspace-read": 1}
METHOD_IMPL_VERSION = 1
IMAGE_FLAG_NAME = "IMAGE_INPUT_ENABLED"
IMAGE_FALLBACK_FLAG_NAME = "IMAGE_FALLBACK_ENABLED"
IMAGE_PROBE = os.environ.get("AGY_IMAGE_PROBE", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}
SHA_CHUNK_BYTES = 1024 * 1024
DYNAMIC_CONFIG_MAX_BYTES = get_bridge_config().dynamic_config_max_bytes
SWEEP_INTERVAL_S = 600.0
SWEEP_CUTOFF_S = get_bridge_config().sweep_cutoff_s

CWD_MAX_LEN = 4096


def _is_session_isolation_enabled() -> bool:
    """Изоляция включена, пока окружение явно не задаёт выключатель."""
    val = os.environ.get("AGY_BRIDGE_SESSION_ISOLATION_ENABLED", "1").strip().lower()
    return val not in ("0", "false", "no", "off")


AGY_BRIDGE_SESSION_ISOLATION_ENABLED = _is_session_isolation_enabled()

# Ленивые горячие сессии: следующий запрос с тем же (модель, cwd, effort) продолжает
# разговор agy через --conversation и шлёт только новые сообщения, а не всю историю.
SESSION_IDLE_TTL_S = 45 * 60.0
SESSION_MAX_TTL_S = get_bridge_config().session_max_ttl_s
SESSION_MAX_TURNS = get_bridge_config().session_max_turns

_started = time.time()
_active: dict = {}
_active_lock = threading.Lock()
_account_pool = AccountPool(AccountPoolConfig(max_concurrent=MAX_CONCURRENT, n_floor=1))
_slots = _FairSlotSemaphore(MAX_CONCURRENT)
_budget = None
_last_ok = [0.0]
_session_store_lock = threading.Lock()
# Ключ: (model, cwd, effort) либо (chat_token, model, cwd, effort) при x-dsh-chat-id.
_session_store: dict[tuple[str, ...], dict[str, Any]] = {}
_in_flight_cids: set[str] = set()
# Персистентность стора (ADR-0008): порядок замков строго файл -> память; I/O
# выполняется только под файловым замком. Запись включает загрузка в main():
# импорт модуля (тесты, утилиты) не трогает sessions.json живого моста.
_sessions_file_lock = threading.Lock()
_sessions_persist_ready = False
SESSIONS_FILE_ENV = "AGY_BRIDGE_SESSIONS_FILE"
SESSIONS_FILE_VERSION = 1
# Владение разговором: cid -> turn_id активного хода (под _session_store_lock).
# Два живых хода никогда не читают один <cid>.db и не делят один cid.
_active_cid_owners: dict[str, str] = {}

# Процессное состояние SQLite-источника мышления. Один замок охватывает breaker,
# бюджеты, compat-canary, кэш флага и счётчики /health; I/O под ним не выполняется.
_sqlite_guard_lock = threading.Lock()
_breaker_state: str = "CLOSED"
_breaker_failures: int = 0
_breaker_opened_at: float = 0.0
_breaker_probe_gen: int = 0
_breaker_active_probe_gen: int | None = None
_breaker_probe_started_at: float = 0.0
_retry_tenths: int = RETRY_CAPACITY_TENTHS
_compat_ident: tuple[int, int] | None = None
_compat_state: str = "SHADOW"
_flag_value: bool = False
_flag_key: tuple[int, int] | None = None
_flag_checked_at: float | None = None
_sqlite_divergence_count: int = 0
_sqlite_drain_deadline_count: int = 0
_sqlite_open_connections: int = 0
_sqlite_max_open_connections: int = 0
_rng: Callable[[], float] = random.random

# Изображения: хеш бинаря agy (кэш по идентичности файла), отдельный от SQLite-флага
# кэш IMAGE_INPUT_ENABLED и реестр активных каталогов img-* (под _active_lock).
_sha_cache_lock = threading.Lock()
_sha_compute_lock = threading.Lock()
_sha_cache: dict[str, tuple[tuple[int, int, int, int], str]] = {}
_image_flag_lock = threading.Lock()
_image_flag_cache: tuple[float, bool] = (0.0, False)
_image_fallback_flag_lock = threading.Lock()
_image_fallback_flag_cache: tuple[float, bool] = (0.0, False)
_active_img_dirs: set[str] = set()

# Токеноподобные последовательности в логах: сам ключ моста и длинные hex/base64.
_SECRET = re.compile(r"[A-Za-z0-9_\-]{24,}")
_NOISE = re.compile(
    r"NODE_TLS_REJECT_UNAUTHORIZED|--trace-warnings|^\(node:\d+\)", re.I
)


class FleetViolation(Exception):
    """Нарушение класса I каталога моделей: старт запрещён."""

    def __init__(self, reason: str, model: str = "-"):
        super().__init__(reason)
        self.reason = reason
        self.model = model


def _build_catalog(data: Any) -> dict:
    """Проверить каталог (класс I) и вернуть нормализованный словарь."""
    if not isinstance(data, dict):
        raise FleetViolation("fleet_unreadable", "-")
    if data.get("schema_version") != 2:
        raise FleetViolation("schema_version_invalid", "-")
    limits = data.get("image_limits")
    if not isinstance(limits, dict):
        raise FleetViolation("limits_invalid", "-")
    # Целочисленность и неотрицательность. НОЛЬ по числовым лимитам изображений —
    # законное значение: `max_images: 0` означает "изображений не принимаем вовсе".
    # Так у agy: stream-json принимает только текстовые блоки контента
    # (`error: stream input content block type "image_url" is not supported
    # (only "text")` — проверено 2026-10-07 на 1.3.1). max_body_bytes — это лимит
    # HTTP-тела запроса, он всегда > 0, поэтому проверяется отдельно.
    for key in ("max_images", "max_image_bytes", "max_total_image_bytes"):
        if (
            not isinstance(limits.get(key), int)
            or isinstance(limits.get(key), bool)
            or limits[key] < 0
        ):
            raise FleetViolation("limits_invalid", "-")
    if (
        not isinstance(limits.get("max_body_bytes"), int)
        or isinstance(limits.get("max_body_bytes"), bool)
        or limits["max_body_bytes"] <= 0
    ):
        raise FleetViolation("limits_invalid", "-")
    # Типы обязаны быть непустым списком только если изображения вообще принимаются.
    if not isinstance(limits.get("types"), list) or (
        limits["max_images"] > 0 and not limits["types"]
    ):
        raise FleetViolation("limits_invalid", "-")
    admission = data.get("admission")
    if not isinstance(admission, dict):
        raise FleetViolation("admission_invalid", "-")
    for key in ("max_http_connections", "max_inflight_body_bytes"):
        if (
            not isinstance(admission.get(key), int)
            or isinstance(admission.get(key), bool)
            or admission[key] <= 0
        ):
            raise FleetViolation("admission_invalid", "-")
    raw_models = data.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        raise FleetViolation("models_invalid", "-")
    models = {}
    order = []
    for item in raw_models:
        if not isinstance(item, dict):
            raise FleetViolation("model_invalid", "-")
        mid = item.get("id")
        if not isinstance(mid, str) or not mid:
            raise FleetViolation("model_invalid", "-")
        if mid in models:
            raise FleetViolation("duplicate_id", mid)
        efforts = item.get("efforts")
        if (
            not isinstance(efforts, list)
            or not efforts
            or not all(isinstance(e, str) for e in efforts)
            or any(e not in EFFORT_LEVELS for e in efforts)
        ):
            raise FleetViolation("efforts_invalid", mid)
        if item.get("default_effort") not in efforts:
            raise FleetViolation("default_effort_invalid", mid)
        images = item.get("images")
        if not isinstance(images, dict):
            raise FleetViolation("status_invalid", mid)
        status = images.get("status")
        if status not in IMAGE_STATUSES:
            raise FleetViolation("status_invalid", mid)
        input_types = item.get("input")
        if not isinstance(input_types, list) or not all(
            isinstance(t, str) for t in input_types
        ):
            raise FleetViolation("status_inconsistent", mid)
        if (
            images.get("cli_registry") == "explicit_unsupported"
            and status != "unsupported"
        ):
            raise FleetViolation("status_inconsistent", mid)
        # unsupported/unverified — text-only. confirmed/probe допустимы только с
        # реализованным методом доставки и входом image; proof проверяется на каждом
        # image-запросе (`_image_proof_reason`), а не при старте.
        if status in ("unsupported", "unverified"):
            if images.get("method") is not None or input_types != ["text"]:
                raise FleetViolation("status_inconsistent", mid)
        if status == "probe" and not IMAGE_PROBE:
            raise FleetViolation("probe_flag_missing", mid)
        method = images.get("method")
        proof = cast(object, images.get("proof"))
        if status in ("confirmed", "probe"):
            if method not in IMPLEMENTED_METHODS:
                raise FleetViolation("method_not_implemented", mid)
            if "image" not in input_types or "text" not in input_types:
                raise FleetViolation("status_inconsistent", mid)
            if status == "confirmed" and not isinstance(proof, dict):
                raise FleetViolation("proof_invalid", mid)
            if limits["max_images"] <= 0 or not limits["types"]:
                raise FleetViolation("limits_invalid", mid)
        elif method is not None and method not in IMPLEMENTED_METHODS:
            raise FleetViolation("method_not_implemented", mid)
        models[mid] = {
            "id": mid,
            "name": str(item.get("name") or mid),
            "efforts": [str(e) for e in efforts],
            "default_effort": str(item["default_effort"]),
            "context_window": int(item.get("context_window") or 0),
            "max_tokens": int(item.get("max_tokens") or 0),
            "input": [str(t) for t in input_types],
            "images": {
                "status": str(status),
                "cli_registry": str(images.get("cli_registry") or ""),
                "method": method,
                "proof": proof,
            },
        }
        order.append(mid)
    default_model = data.get("default_model")
    if not isinstance(default_model, str) or default_model not in models:
        raise FleetViolation("default_model_invalid", "-")
    if ENV_MODEL and ENV_MODEL not in models:
        raise FleetViolation("env_model_invalid", ENV_MODEL)
    technical_ref_raw = cast(object, data.get("technical_ref"))
    technical_ref = (
        cast("dict[str, object]", technical_ref_raw)
        if isinstance(technical_ref_raw, dict)
        else {}
    )
    return {
        "schema_version": data.get("schema_version"),
        "catalogue": str(cast("dict[str, object]", data).get("catalogue") or ""),
        "default_model": default_model,
        "order": order,
        "models": models,
        "image_limits": {
            "max_images": int(limits["max_images"]),
            "max_image_bytes": int(limits["max_image_bytes"]),
            "max_total_image_bytes": int(limits["max_total_image_bytes"]),
            "max_body_bytes": int(limits["max_body_bytes"]),
            "types": [str(t) for t in limits["types"]],
            "max_types": [str(t).lower() for t in limits["types"]],
        },
        "admission": {
            "max_http_connections": int(admission["max_http_connections"]),
            "max_inflight_body_bytes": int(admission["max_inflight_body_bytes"]),
        },
        "technical_ref": dict(technical_ref),
    }


def _load_fleet() -> dict:
    """Прочитать и проверить fleet.json; при нарушении класса I — отказ старта."""
    catalog = None
    try:
        raw = FLEET_PATH.read_bytes()
    except OSError:
        raw = None
    if raw is not None:
        try:
            catalog = _build_catalog(json.loads(raw.decode("utf-8")))
        except FleetViolation:
            raise
        except (ValueError, UnicodeDecodeError):
            catalog = None
    if catalog is None or raw is None:
        sys.stderr.write("fleet_invalid model=- reason=fleet_unreadable\n")
        sys.stderr.flush()
        raise SystemExit(1)
    catalog["path"] = str(FLEET_PATH)
    catalog["sha256"] = hashlib.sha256(raw).hexdigest()
    return catalog


try:
    FLEET = _load_fleet()
except FleetViolation as _violation:
    sys.stderr.write(
        f"fleet_invalid model={_violation.model} reason={_violation.reason}\n"
    )
    sys.stderr.flush()
    raise SystemExit(1)

MODEL_ID = ENV_MODEL or FLEET["default_model"]
FLEET_MODELS = cast("dict[str, dict[str, object]]", cast(object, FLEET["models"]))
IMAGE_LIMITS = cast("dict[str, object]", cast(object, FLEET["image_limits"]))


def _log(msg: str) -> None:
    sys.stderr.write(
        "[agy-bridge] %s %s\n" % (time.strftime("%H:%M:%S"), _mask_secrets(msg))
    )
    sys.stderr.flush()


def _idle_timeout_from_env() -> float:
    """Порог неактивности хода, с; невалидное или неположительное значение -> дефолт core."""
    raw = os.environ.get("AGY_BRIDGE_IDLE_TIMEOUT", "").strip()
    if not raw:
        return float(_CORE_IDLE_TIMEOUT_S)
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if not value > 0.0 or value != value or value == float("inf"):
        _log(
            f"AGY_BRIDGE_IDLE_TIMEOUT={raw!r} invalid, using {_CORE_IDLE_TIMEOUT_S:g}s"
        )
        return float(_CORE_IDLE_TIMEOUT_S)
    return value


def _is_watchdog_enabled() -> bool:
    """Kill-switch адаптивного сторожа: BRIDGE_ENABLE_ADAPTIVE_WATCHDOG=0|false|no|off."""
    raw = os.environ.get("BRIDGE_ENABLE_ADAPTIVE_WATCHDOG", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


# Имена диагностических событий и причин отказа (мышление, изображения) длиннее 24
# символов, но секретами не являются: без исключения маска скрыла бы их в логах.
# Только точное совпадение токена целиком, не префикс и не подстрока.
_LOG_EVENT_NAMES = frozenset(
    {
        "sqlite_snapshot_divergence",
        "sqlite_transcript_divergence",
        "image_input_not_supported",
        "unsupported_reasoning_effort",
        "invalid_reasoning_effort",
        "unsupported_image_type",
        "invalid_image_content",
        "invalid_image_base64",
        "image_url_not_allowed",
        "image_type_mismatch",
        "image_proof_invalid",
        "images_too_large",
        "image_too_large",
        "too_many_images",
        "image_spool_error",
        "image_cleanup_error",
        "image_sweep_removed",
        "usage-cumulative-fallback",
        "usage-step-ledger-incomplete",
        "media-degradation-reserve",
    }
)


def _mask_token(match: re.Match[str]) -> str:
    token = match.group(0)
    return token if token in _LOG_EVENT_NAMES else "***"


def _mask_secrets(text: str) -> str:
    """Погасить токеноподобные последовательности и сам ключ моста."""
    out = str(text)
    if AUTH_KEY:
        out = out.replace(AUTH_KEY, "***")
    return _SECRET.sub(_mask_token, out)


def _err_summary(err: Any, limit: int = 200) -> str:
    text = " ".join(str(err or "").split())
    return text[:limit]


# Порог неактивности хода (без протокольных событий и без прироста CPU/потомков группы).
IDLE_TIMEOUT_S = get_bridge_config().idle_timeout_s
WATCHDOG_INTERVAL_S = get_bridge_config().watchdog_interval_s
# Зачистка группы: сколько ждать после SIGTERM и сколько — reap лидера после SIGKILL.
KILL_TERM_GRACE_S = get_bridge_config().kill_term_grace_s
KILL_WAIT_S = 5.0
# После result ERROR процесс обязан выйти сам: сколько ждать done, прежде чем сдаться.
RESULT_EXIT_GRACE_S = 5.0
# События очереди, считающиеся активностью агента (result/done/pump_error — терминальные).
_ACTIVITY_KINDS = frozenset({"init", "text", "reasoning", "tool_trace"})
# Записи транскрипта, для которых хвост вообще разбирает JSON (остальное — быстрый отсев).
_TAIL_MARKER_RE = re.compile(rb"PLANNER_RESPONSE|ERROR_MESSAGE|END_TURN|TURN_COMPLETE")


# Zero-Canon: файлы канона/хуков пользователя, которых не должно быть в <clean-home>.
_CANON_FILE_NAMES = ("AGENTS.md", "GEMINI.md", "hooks.json")


def _assert_inside_clean_home(path: Path) -> None:
    """Путь (после resolve) обязан лежать внутри <clean-home> или совпадать с ним.

    Защита от symlink-атак: запись, chmod и удаление не выходят за границы профиля.
    """
    base = CLEAN_HOME_DIR.resolve()
    resolved = path.resolve()
    if resolved != base and base not in resolved.parents:
        raise RuntimeError(
            f"Path {path} resolves outside clean-home {base}: {resolved}"
        )


def _ensure_private_dir(path: Path) -> None:
    """Каталог с правами 0700 (umask и ранее созданные права выравниваются chmod).

    Симлинк вместо каталога отвергается без перехода по нему: chmod/mkdir
    во внешнем каталоге недопустимы.
    """
    if path.is_symlink():
        raise RuntimeError(f"Refusing to use symlink as private directory: {path}")
    _assert_inside_clean_home(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def _ensure_symlink(link: Path, target: Path) -> None:
    """Симлинк link -> target; чужой симлинк/файл/битая ссылка заменяются.

    Настоящий каталог по пути link не удаляется никогда (RuntimeError).
    Родитель link обязан находиться внутри <clean-home>.
    """
    _assert_inside_clean_home(link.parent)
    if link.is_symlink():
        if os.readlink(link) == str(target):
            return
        link.unlink(missing_ok=True)
    elif link.exists():
        if link.is_dir():
            raise RuntimeError(
                f"Refusing to replace real directory {link} with symlink to {target}"
            )
        link.unlink(missing_ok=True)
    link.symlink_to(target)


def _mirror_regular_files(
    src_dir: Path, dst_dir: Path, ancestors: frozenset[Path]
) -> None:
    """Пробрасывает содержимое src_dir в приватный dst_dir симлинками на файлы.

    Подкаталоги не линкуются целиком: для каждого создаётся приватный каталог
    0700 в <clean-home>, симлинками пробрасываются только файлы внутри него.
    Так сквозная запись в реальный профиль через вложенные каталоги невозможна.
    Циклы симлинков отсекаются по множеству resolved-предков.
    """
    _ensure_private_dir(dst_dir)
    ancestors = ancestors | {src_dir.resolve()}
    for entry in src_dir.iterdir():
        dst = dst_dir / entry.name
        if entry.is_dir():
            if entry.resolve() in ancestors:
                continue
            # Наследие прежних версий: симлинк на каталог/файл вместо приватного каталога.
            if dst.is_symlink() or (dst.exists() and not dst.is_dir()):
                dst.unlink()
            _mirror_regular_files(entry, dst, ancestors)
        else:
            _ensure_symlink(dst, entry)


def _unlink_quiet(path: Path) -> None:
    """Удаляет файл/ссылку; подавляется только ENOENT (конкурентное удаление).

    Прочие ошибки (EACCES/EPERM и т.п.) пробрасываются: запуск `agy` при
    неудалённом каноне недопустим (fail-loud).
    """
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _remove_canon_hooks(clean_gemini: Path) -> None:
    """Удаляет PreInvocation-хуки из фактического пути `.gemini/config/`.

    Симлинк `config` убирается как ссылка (цель не затрагивается); внутрь
    внешнего каталога удаление не заходит. Конкурентное удаление (ENOENT)
    допустимо; ошибки прав и прочие сбои удаления пробрасываются наружу.
    """
    config = clean_gemini / "config"
    if config.is_symlink():
        _unlink_quiet(config)
        return
    if not config.is_dir():
        return
    _assert_inside_clean_home(config)
    hooks_file = config / "hooks.json"
    if hooks_file.is_symlink() or hooks_file.is_file():
        _unlink_quiet(hooks_file)
    hooks_dir = config / "hooks"
    if hooks_dir.is_symlink() or hooks_dir.is_file():
        _unlink_quiet(hooks_dir)
    elif hooks_dir.is_dir():
        try:
            shutil.rmtree(hooks_dir)
        except FileNotFoundError:
            pass


def _clean_canon_files(clean_home: Path) -> None:
    """Zero-Canon: удаляет каноны и хуки из <clean-home> (идемпотентно).

    Вызывается при инициализации профиля и перед КАЖДЫМ запуском `agy`.
    Fail-loud: симлинк (или не-каталог) на месте <clean-home>, `.gemini` или
    `antigravity-cli` — признак подмены после инициализации. Тихое удаление
    ссылки оставило бы `agy` в разобранном профиле без креденшалов и каталогов
    состояния, поэтому запуск прерывается RuntimeError. Внутрь ссылки обход не
    заходит: канон за пределами <clean-home> никогда не затрагивается.
    """
    clean_gemini = clean_home / ".gemini"
    clean_cli = clean_gemini / "antigravity-cli"
    for base in (clean_home, clean_gemini, clean_cli):
        if base.is_symlink() or not base.is_dir():
            raise RuntimeError(
                "Invalid clean-home: profile directory cannot be a symlink "
                f"or missing ({base})"
            )
        _assert_inside_clean_home(base)
    _remove_canon_hooks(clean_gemini)
    for base in (clean_home, clean_gemini, clean_cli):
        for name in _CANON_FILE_NAMES:
            canon = base / name
            if canon.is_symlink() or canon.is_file():
                # Симлинк-канон на внешний файл удаляется как ссылка: проверяем
                # родителя (resolve симлинка вышел бы за границы и ложно упал).
                _assert_inside_clean_home(canon.parent if canon.is_symlink() else canon)
                _unlink_quiet(canon)
    _assert_zero_canon(clean_home, clean_gemini)


def _assert_zero_canon(clean_home: Path, clean_gemini: Path) -> None:
    """Пост-проверка Zero-Canon: после очистки канонов и хуков не осталось."""
    for base in (clean_home, clean_gemini, clean_gemini / "antigravity-cli"):
        for name in _CANON_FILE_NAMES:
            canon = base / name
            if canon.is_file() or canon.is_symlink():
                raise RuntimeError(
                    f"Zero-Canon invariant violated: canon file {canon} "
                    "still exists after cleaning"
                )
    config = clean_gemini / "config"
    for hook in (config / "hooks.json", config / "hooks"):
        if hook.is_symlink() or hook.exists():
            raise RuntimeError(
                f"Zero-Canon invariant violated: hook {hook} still exists after cleaning"
            )


def _copy_private_atomic(src: Path, dst: Path) -> None:
    """Атомарная копия src -> dst с правами 0600 через временный файл и os.replace."""
    tmp = dst.parent / f".tmp_{dst.name}_{uuid.uuid4().hex}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as out, open(src, "rb") as inp:
            shutil.copyfileobj(inp, out)
        os.chmod(tmp, 0o600)
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _verify_clean_home_root(clean_home: Path) -> Path:
    """Проверяет корень <clean-home> перед любой очисткой (вызывать под _AGY_HOME_LOCK).

    Корень, `.gemini` и `antigravity-cli` не могут быть симлинками, а после
    инициализации `.gemini` обязан существовать (fail-loud вместо запуска в
    разобранном профиле). Корень обязан совпадать с верифицированным при
    инициализации resolved-путём (подмена после старта отвергается) и не может
    совпадать с HOME или его предком, а также пересекаться с реальным профилем
    ~/.gemini (совпадать, быть его предком или лежать внутри): очистка канонов
    иначе удалила бы пользовательские файлы. Возвращает resolved-путь.
    """
    global _VERIFIED_CLEAN_HOME
    if clean_home.is_symlink():
        raise RuntimeError(
            "Invalid clean-home directory: CLEAN_HOME_DIR cannot be a symlink"
        )
    clean_home_resolved = clean_home.resolve()
    if _VERIFIED_CLEAN_HOME is not None and clean_home_resolved != _VERIFIED_CLEAN_HOME:
        raise RuntimeError(
            "Clean-home path mutated after initialization: "
            f"{clean_home_resolved} != {_VERIFIED_CLEAN_HOME}"
        )
    home_resolved = HOME.resolve()
    real_gemini_resolved = (HOME / ".gemini").resolve()
    if (
        clean_home_resolved == home_resolved
        or clean_home_resolved in home_resolved.parents
        or clean_home_resolved == real_gemini_resolved
        or clean_home_resolved in real_gemini_resolved.parents
        or real_gemini_resolved in clean_home_resolved.parents
    ):
        raise RuntimeError(
            "Invalid clean-home directory: overlaps with HOME or real .gemini "
            f"({clean_home_resolved})"
        )
    clean_gemini = clean_home / ".gemini"
    if clean_gemini.is_symlink():
        raise RuntimeError("Invalid clean-home directory: .gemini cannot be a symlink")
    if _AGY_HOME_INITIALIZED and not clean_gemini.is_dir():
        raise RuntimeError(
            "Invalid clean-home state: .gemini directory is missing or damaged "
            "after initialization"
        )
    if (clean_gemini / "antigravity-cli").is_symlink():
        raise RuntimeError(
            "Invalid clean-home directory: antigravity-cli cannot be a symlink"
        )
    _VERIFIED_CLEAN_HOME = clean_home_resolved
    return clean_home_resolved


def _prepare_agy_home() -> Path:
    """Потокобезопасно (однократно) готовит изолированный HOME для `agy`.

    Library -> ~/Library даёт доступ к Keychain macOS (без OAuth-окна браузера);
    учётные данные копируются атомарно с 0600; AGENTS.md/GEMINI.md/hooks.json
    в профиль не попадают никогда (Zero-Canon).

    Модель владения профилем: источник истины при старте — реальный профиль
    пользователя `~/.gemini`. Мост выполняет однократный атомарный снимок
    учётных данных с правами 0600 при инициализации процесса под локом.
    Ротация токенов в реальном профиле подхватывается при следующем
    перезапуске процесса моста, если копия в реальном профиле не старше
    файла в <clean-home> (mtime-guard: токен, обновлённый самим agy внутри
    <clean-home>, не затирается). Состояние сессий и транскрипты пишутся
    исключительно в изолированный <clean-home> и не загрязняют профиль
    пользователя.

    Инвариант изоляции: CLEAN_HOME_DIR, BRAIN_DIR и CONV_DIR замкнуты внутри
    <clean-home>; внешние AGY_BRIDGE_BRAIN/AGY_BRIDGE_CONVERSATIONS отвергаются.
    """
    global _AGY_HOME_INITIALIZED
    with _AGY_HOME_LOCK:
        clean_home_resolved = _verify_clean_home_root(CLEAN_HOME_DIR)
        if _AGY_HOME_INITIALIZED:
            return clean_home_resolved
        for state_dir in (BRAIN_DIR, CONV_DIR):
            try:
                _assert_inside_clean_home(state_dir)
            except RuntimeError as exc:
                raise RuntimeError(
                    f"BRAIN_DIR/CONV_DIR resolves outside clean-home: {state_dir}"
                ) from exc
        real_gemini = HOME / ".gemini"
        real_cli = real_gemini / "antigravity-cli"
        clean_gemini = CLEAN_HOME_DIR / ".gemini"
        clean_gemini_cli = clean_gemini / "antigravity-cli"

        _ensure_private_dir(CLEAN_HOME_DIR)
        _ensure_symlink(CLEAN_HOME_DIR / "Library", HOME / "Library")
        _ensure_private_dir(clean_gemini)
        _ensure_private_dir(clean_gemini_cli)
        for name in ("bin", "builtin"):
            src_dir = real_cli / name
            if src_dir.is_dir():
                clean_sub = clean_gemini_cli / name
                # Симлинк всего каталога (наследие прежних версий) допускал бы
                # сквозное создание файлов в реальном профиле: убираем ссылку,
                # цель не затрагивается.
                if clean_sub.is_symlink():
                    clean_sub.unlink()
                _mirror_regular_files(src_dir, clean_sub, frozenset())
        for src, dst in (
            (real_gemini / "jetski-standalone-oauth-token", clean_gemini),
            (real_gemini / "projects.json", clean_gemini),
            (real_cli / "installation_id", clean_gemini_cli),
            (real_cli / "jetski_state.pbtxt", clean_gemini_cli),
            (real_cli / "settings.json", clean_gemini_cli),
        ):
            dst_file = dst / src.name
            if src.is_file():
                # mtime-guard: более свежий файл в <clean-home> (например, токен,
                # обновлённый дочерним agy при OAuth-рефреше) не затирается
                # устаревшей копией из реального профиля. Симлинк на месте копии
                # не сохраняется (stat пошёл бы по ссылке): он удаляется и файл
                # копируется заново; сохранённый файл остаётся строго 0600.
                if dst_file.is_symlink():
                    dst_file.unlink()
                if (
                    not dst_file.exists()
                    or src.stat().st_mtime >= dst_file.stat().st_mtime
                ):
                    _copy_private_atomic(src, dst_file)
                else:
                    _assert_inside_clean_home(dst_file)
                    dst_file.chmod(0o600)
        _ensure_private_dir(clean_gemini_cli / "conversations")
        _ensure_private_dir(clean_gemini_cli / "brain")
        _clean_canon_files(CLEAN_HOME_DIR)
        _AGY_HOME_INITIALIZED = True
        return clean_home_resolved


ALLOWED_MODELS_ENV = "AGY_ALLOWED_MODELS_FILE"


def _allowed_models_file() -> str:
    """Путь к allowlist лончера: env AGY_ALLOWED_MODELS_FILE, иначе файл реального HOME.

    Единственный источник пути: им пользуются и окружение `agy` (`_launch_env`),
    и фильтр каталога `/v1/models`, поэтому каталог не расходится с guard лончера.
    """
    return os.environ.get(ALLOWED_MODELS_ENV) or str(
        HOME / ".config" / "agy-launch" / "allowed-models.txt"
    )


def _read_allowed_models() -> frozenset[str]:
    """Разобрать allowlist так же, как лончер: без CR, пробелов, пустых строк и `#`.

    Нет файла, он нечитаем или пуст -> пустое множество (фильтр отключается).
    """
    try:
        text = Path(_allowed_models_file()).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return frozenset()
    lines = (line.strip() for line in text.splitlines())
    return frozenset(line for line in lines if line and not line.startswith("#"))


def _model_in_allowlist(model_id: str, allowed: frozenset[str]) -> bool:
    """Каталог отдаёт только id, которые лончер примет дословно.

    Лончер сверяет запрошенный id с allowlist дословно (иначе rc=64
    «generation guard» -> HTTP 502). Расширять каталог по базовой форме
    (`-high`/`-medium`/`-low`) нельзя: такой id лончер отклонит, и вызывающая
    сторона снова получит ответ другой модели при формальном успехе.
    """
    return model_id in allowed


def _catalog_model_order() -> list[str]:
    """Порядок каталога: MODEL_ID первым, затем FLEET["order"]; только разрешённые.

    Нет allowlist или он пуст -> прежний состав без фильтрации и одна строка в лог.
    """
    order = [MODEL_ID] + [mid for mid in FLEET["order"] if mid != MODEL_ID]
    allowed = _read_allowed_models()
    if not allowed:
        _log(
            f"models catalog: allowlist {_allowed_models_file()} missing or empty,"
            " generation-guard filter disabled"
        )
        return order
    return [mid for mid in order if _model_in_allowlist(mid, allowed)]


def _launch_env() -> dict:
    """Окружение для `agy`. Ключ моста потомку не передаётся.

    HOME указывает на изолированный <clean-home> (Zero-Canon); браузер для
    OAuth заблокирован. Прокси-переменные (HTTPS_PROXY/HTTP_PROXY/NO_PROXY)
    выставляет сам лончер agy-cli.sh — мост их не дублирует и не переопределяет.

    agy-cli.sh ищет бинарь (`$HOME/.local/bin/agy.real`) и список разрешённых
    моделей (`$HOME/.config/agy-launch/allowed-models.txt`) относительно HOME, а
    в <clean-home> их нет (rc=64 «generation guard» / rc=127). Поэтому пути
    реального профиля пробрасываются явными AGY_BIN и AGY_ALLOWED_MODELS_FILE;
    значения, уже заданные в окружении моста, сохраняются (`setdefault`).
    """
    env = os.environ.copy()
    env.setdefault("AGY_SKIP_PREFLIGHT", "1")
    env.pop("AGY_BRIDGE_KEY", None)
    clean_home = str(_prepare_agy_home())
    # Per-launch Zero-Canon: канон, появившийся после инициализации, удаляется
    # перед каждым порождением процесса. Корень перепроверяется непосредственно
    # перед очисткой (подмена на симлинк/другой путь), очистка сериализована.
    with _AGY_HOME_LOCK:
        _verify_clean_home_root(CLEAN_HOME_DIR)
        _clean_canon_files(Path(clean_home))
    env["HOME"] = clean_home
    env.setdefault("AGY_BIN", str(AGY_BIN))
    env.setdefault(ALLOWED_MODELS_ENV, _allowed_models_file())
    env["BRIDGE_ZERO_CANON"] = "1"
    env["BROWSER"] = "/usr/bin/false"
    return env


class LauncherUnavailable(Exception):
    """Канонический лончер отсутствует или не исполняем."""


def _launcher() -> str:
    """Канонический лончер обязателен; запасного пути на голый бинарь нет.

    Без лончера agy гео-заблокирован (РФ), поэтому «fallback на голый бинарник»
    запрещён: это дало бы тихий отказ вместо честной ошибки.
    """
    if os.path.isfile(LAUNCHER) and os.access(LAUNCHER, os.X_OK):
        return LAUNCHER
    raise LauncherUnavailable(LAUNCHER)


def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    hdr = handler.headers.get("Authorization", "")
    if hdr.startswith("Bearer "):
        return hdr[7:].strip() == AUTH_KEY
    return handler.headers.get("x-api-key", "") == AUTH_KEY or hdr.strip() == AUTH_KEY


def _flatten_content(content: Any, img_counter: list[int] | None = None) -> str:
    """Контент сообщения в текст; с `img_counter` image-части дают маркеры `[image N]`."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif (
                img_counter is not None
                and isinstance(item, dict)
                and item.get("type") == "image_url"
            ):
                img_counter[0] += 1
                parts.append("[image %d]" % img_counter[0])
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(p for p in parts if p)
    return str(content)


@final
class ImageReject(ValueError):
    """Отказ по изображениям: `reason` — деталь для журнала, `code` — тип HTTP 400."""

    def __init__(self, reason: str, code: str = "image_input_not_supported") -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


@final
class ImageSpoolError(RuntimeError):
    """Проверенные изображения не удалось материализовать на диск."""


_B64_WS = re.compile(r"[ \t\r\n\f\v]")
_STATUS_REASONS = frozenset(
    {"status_unsupported", "status_probe", "model_unknown", "input_not_image"}
)


def _safe_log_value(value: object) -> str:
    """Значение из запроса для строки журнала: управляющие символы -> `_`."""
    return re.sub(r"[\x00-\x1f\x7f]", "_", str(value))


def _file_sha256(path: object) -> str:
    """SHA-256 файла чанками по 1 MiB; '' — файл недоступен или изменился при чтении.

    Кэш по пути с идентичностью (st_dev, st_ino, st_mtime_ns, st_size): неизменный
    бинарь (~190 MiB) хешируется один раз. Хеширование идёт вне `_sha_cache_lock`,
    под отдельным замком единственного вычислителя.
    """
    resolved = os.path.expanduser(str(path))

    def identity() -> tuple[int, int, int, int]:
        info = os.stat(resolved)
        return (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)

    try:
        key = identity()
        with _sha_cache_lock:
            cached = _sha_cache.get(resolved)
        if cached is not None and cached[0] == key:
            return cached[1]
        with _sha_compute_lock:
            with _sha_cache_lock:
                cached = _sha_cache.get(resolved)
            if cached is not None and cached[0] == key:
                return cached[1]
            digest = hashlib.sha256()
            with open(resolved, "rb") as handle:
                for chunk in iter(lambda: handle.read(SHA_CHUNK_BYTES), b""):
                    digest.update(chunk)
            if identity() != key:
                return ""
            hexdigest = digest.hexdigest()
            with _sha_cache_lock:
                _sha_cache[resolved] = (key, hexdigest)
            return hexdigest
    except OSError:
        return ""


def _read_image_flag() -> bool:
    """IMAGE_INPUT_ENABLED из dynamic_config.json: строго `true`, иначе False."""
    try:
        path = DYNAMIC_CONFIG_PATH
        if not path.is_file() or path.stat().st_size > DYNAMIC_CONFIG_MAX_BYTES:
            return False
        data = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    return cast("dict[str, object]", data).get(IMAGE_FLAG_NAME) is True


def _is_image_input_enabled() -> bool:
    """Fail-closed выключатель image-входа (по умолчанию False).

    Env `AGY_IMAGE_INPUT_ENABLED` (непустой) решает сразу: 0|false|no|off -> False,
    1|true|yes|on -> True, любое иное значение -> False. Без env — флаг
    `IMAGE_INPUT_ENABLED` в dynamic_config.json с кэшем TTL 1.0 с; не-boolean,
    битый или отсутствующий файл дают False. Не зависит от SQLITE_REASONING_ENABLED.
    """
    global _image_flag_cache
    env = os.environ.get("AGY_IMAGE_INPUT_ENABLED", "").strip().lower()
    if env:
        return env in ("1", "true", "yes", "on")
    now = time.monotonic()
    with _image_flag_lock:
        checked_at, cached = _image_flag_cache
        if checked_at > 0.0 and now - checked_at < FLAG_TTL_S:
            return cached
    value = _read_image_flag()
    with _image_flag_lock:
        _image_flag_cache = (now, value)
    return value


def _image_proof_reason(model_id: str, effort: str | None = None) -> str | None:
    """None — image-вход модели доказан; иначе короткая причина (без секретов)."""
    model = FLEET_MODELS.get(model_id)
    if model is None:
        return "model_unknown"
    raw_images = model.get("images")
    images = (
        cast("dict[str, object]", raw_images) if isinstance(raw_images, dict) else {}
    )
    raw_input = model.get("input")
    if not isinstance(raw_input, list) or "image" not in cast(
        "list[object]", raw_input
    ):
        return "input_not_image"
    status = images.get("status")
    if status == "probe":
        if not IMAGE_PROBE:
            return "status_probe"
    elif status != "confirmed":
        return "status_unsupported"
    method = images.get("method")
    if not isinstance(method, str) or method not in IMPLEMENTED_METHODS:
        return "method_not_implemented"
    proof_raw = images.get("proof")
    if not isinstance(proof_raw, dict):
        return "proof_missing"
    proof = cast("dict[str, object]", proof_raw)
    if proof.get("impl_version") != IMPLEMENTED_METHODS[method]:
        return "impl_version_mismatch"
    formats_raw = proof.get("formats")
    types_raw = IMAGE_LIMITS.get("types")
    types = cast("list[object]", types_raw) if isinstance(types_raw, list) else []
    if not isinstance(formats_raw, list) or not formats_raw:
        return "formats_mismatch"
    if not {str(t).lower() for t in types} <= {
        str(f).lower() for f in cast("list[object]", formats_raw)
    }:
        return "formats_mismatch"
    efforts_raw = proof.get("efforts_proven")
    if not isinstance(efforts_raw, list):
        return "efforts_missing"
    if effort is not None and effort not in cast("list[object]", efforts_raw):
        return "effort_not_proven"
    expected = proof.get("agy_binary_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        return "binary_sha_missing"
    actual = _file_sha256(AGY_BIN)
    if not actual or actual != expected.lower():
        return "binary_sha_mismatch"
    return None


def _model_supports_images(model_id: str) -> bool:
    return _is_image_input_enabled() and _image_proof_reason(model_id) is None


def _image_gate(model_id: str, effort: str | None) -> ImageReject | None:
    """Флаг и proof для image-запроса: None — можно, иначе отказ (без I/O с телом)."""
    if not _is_image_input_enabled():
        return ImageReject("image_input_disabled")
    reason = _image_proof_reason(model_id, effort)
    if reason is None:
        return None
    if reason in _STATUS_REASONS:
        return ImageReject(reason)
    if reason == "effort_not_proven":
        return ImageReject(reason, "unsupported_reasoning_effort")
    _log("image_proof_invalid model=%s reason=%s" % (_safe_log_value(model_id), reason))
    return ImageReject("image_proof_invalid")


def _read_image_fallback_flag() -> bool:
    """IMAGE_FALLBACK_ENABLED из dynamic_config.json: строго `true`, иначе False."""
    try:
        path = DYNAMIC_CONFIG_PATH
        if not path.is_file() or path.stat().st_size > DYNAMIC_CONFIG_MAX_BYTES:
            return False
        data = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    return cast("dict[str, object]", data).get(IMAGE_FALLBACK_FLAG_NAME) is True


def _is_image_fallback_enabled() -> bool:
    """Универсальная политика image-входа (по умолчанию False = строгий режим).

    Env `AGY_IMAGE_FALLBACK_ENABLED` (непустой) решает сразу: 1|true|yes -> True,
    любое иное значение (в т. ч. 0|false|no|on|off) -> False. Без env — флаг
    `IMAGE_FALLBACK_ENABLED` в dynamic_config.json с кэшем TTL 1.0 с и отдельным
    замком; не-boolean, битый или отсутствующий файл дают False. Не зависит от
    `IMAGE_INPUT_ENABLED` (он по-прежнему управляет только staging файлов).
    """
    global _image_fallback_flag_cache
    env = os.environ.get("AGY_IMAGE_FALLBACK_ENABLED", "").strip().lower()
    if env:
        return env in ("1", "true", "yes")
    now = time.monotonic()
    with _image_fallback_flag_lock:
        checked_at, cached = _image_fallback_flag_cache
        if checked_at > 0.0 and now - checked_at < FLAG_TTL_S:
            return cached
    value = _read_image_fallback_flag()
    with _image_fallback_flag_lock:
        _image_fallback_flag_cache = (now, value)
    return value


def _image_gate_universal(model_id: str, effort: str | None) -> ImageReject | None:
    """Универсальный допуск: staging включён, модель из каталога, effort валиден.

    Per-model proof, SHA бинаря и `efforts_proven` не проверяются и не читаются.
    """
    if not _is_image_input_enabled():
        return ImageReject("image_input_disabled")
    model = FLEET_MODELS.get(model_id)
    if model is None:
        return ImageReject("model_unknown")
    if effort:
        efforts = model.get("efforts")
        if not isinstance(efforts, list) or effort not in cast("list[object]", efforts):
            return ImageReject("effort_not_proven", "unsupported_reasoning_effort")
    return None


# [Refactored] Media normalization moved to agy_runtime.media_normalizer


def _messages_to_stripped_prompt(messages: object) -> str:
    """Промпт всей истории без media: нет `[image N]`, `[attachments]`, путей и payload."""
    return _messages_to_prompt(
        cast("list[object]", _strip_media_from_messages(messages))
    )


def _log_token(value: object, max_len: int = 64) -> str:
    """Идентификатор для журнала: только `A-Za-z0-9_.-`, остальное `_`, длина ограничена."""
    text = re.sub(r"[^A-Za-z0-9_.\-]", "_", str(value))[:max_len]
    return text or "unknown"


_IMAGE_FALLBACK_STAGES = frozenset({"collect", "post_slot", "spool", "runtime"})


def _log_image_fallback(
    stage: str, reason: str, model: str, attempt: int, count: int
) -> None:
    """Одна структурная строка `image_fallback` на фактический downgrade (без payload)."""
    stage_token = stage if stage in _IMAGE_FALLBACK_STAGES else "unknown"
    model_token = _log_token(model) if model in FLEET_MODELS else "unknown"
    _log(
        "image_fallback stage=%s reason=%s model=%s attempt=%d images=%d"
        % (
            stage_token,
            _log_token(reason),
            model_token,
            max(0, min(int(attempt), 9)),
            max(0, min(int(count), 1000000)),
        )
    )


def _collect_image_parts(
    messages: object,
) -> list[tuple[int, int, dict[str, object]]]:
    """Все image_url-части истории: (индекс сообщения с 0, сквозной номер с 1, часть)."""
    found: list[tuple[int, int, dict[str, object]]] = []
    if not isinstance(messages, list):
        return found
    number = 0
    for msg_index, msg in enumerate(cast("list[object]", messages)):
        if not isinstance(msg, dict):
            continue
        content = cast("dict[str, object]", msg).get("content")
        if not isinstance(content, list):
            continue
        for item in cast("list[object]", content):
            if isinstance(item, dict):
                part = cast("dict[str, object]", item)
                if part.get("type") == "image_url":
                    number += 1
                    found.append((msg_index, number, part))
    return found


def _sniff_image_type(raw: bytes) -> str | None:
    """MIME по сигнатуре (не декодирование пикселей); None — формат неизвестен."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def _limit(name: str, default: int) -> int:
    value = IMAGE_LIMITS.get(name, default)
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _new_img_dir() -> Path:
    """Путь (без обращений к диску) каталога изображений одного хода."""
    return Path(os.path.abspath(str(WORKSPACE))) / ("img-" + uuid.uuid4().hex)


def _collect_images(
    messages: object, model_id: str, effort: str | None, universal: bool = False
) -> list[dict[str, object]]:
    """Проверить image-части всей истории; вернуть записи для prompt и spool.

    Нет image-частей — `[]` сразу, без stat/хеша/флага. Порядок отказов: флаг и
    proof -> число частей -> по каждой части: роль, форма, `data:` URL, MIME,
    оценка размера base64 ДО decode, строгий base64, сигнатура, лимиты. Ничего не
    пишется на диск и не запускается. Декодированные байты не удерживаются
    (`data` пуст): в spool они пересоздаются из base64 уже после захвата слота.

    `universal=True`: image-алиасы (`image`, `input_image`, dict-content) приводятся
    к `image_url`, а вместо proof-гейта работает `_image_gate_universal`; остальные
    проверки те же. Любой отказ отбрасывает ВСЕ записи (исключение, без частичного набора).
    """
    parts = (
        _collect_image_parts_universal(messages)
        if universal
        else _collect_image_parts(messages)
    )
    if not parts:
        return []
    gate = _image_gate_universal(model_id, effort) if universal else _image_gate(model_id, effort)
    if gate is not None:
        raise gate
    max_images = _limit("max_images", 16)
    if max_images <= 0:
        raise ImageReject("images_disabled")
    if len(parts) > max_images:
        raise ImageReject("too_many_images", "too_many_images")
    max_bytes = _limit("max_image_bytes", 0)
    max_total = _limit("max_total_image_bytes", 0)
    allowed_raw = IMAGE_LIMITS.get("types")
    allowed = {
        str(t).lower()
        for t in (
            cast("list[object]", allowed_raw) if isinstance(allowed_raw, list) else []
        )
    }
    msgs = cast("list[object]", messages)
    img_dir = _new_img_dir()
    entries: list[dict[str, object]] = []
    total = 0
    for msg_index, number, part in parts:
        msg = cast("dict[str, object]", msgs[msg_index])
        if msg.get("role") != "user":
            raise ImageReject("non_user_image", "invalid_image_content")
        ref = part.get("image_url")
        url = (
            cast("dict[str, object]", ref).get("url") if isinstance(ref, dict) else None
        )
        if not isinstance(url, str) or not url:
            raise ImageReject("invalid_image_url", "invalid_image_content")
        if url[:5].lower() != "data:":
            raise ImageReject("remote_or_file_url", "image_url_not_allowed")
        comma = url.find(",")
        if comma < 0:
            raise ImageReject("malformed_data_url", "invalid_image_content")
        header = [h.strip().lower() for h in url[5:comma].split(";")]
        mime = header[0]
        if not mime or "base64" not in header[1:]:
            raise ImageReject("malformed_data_url", "invalid_image_content")
        if mime not in allowed or mime not in _EXT:
            raise ImageReject("unsupported_mime", "unsupported_image_type")
        payload = url[comma + 1 :]
        if _B64_WS.search(payload) is not None:
            payload = _B64_WS.sub("", payload)
        if not payload:
            raise ImageReject("empty_payload", "invalid_image_base64")
        pad = 2 if payload.endswith("==") else (1 if payload.endswith("=") else 0)
        if (len(payload) * 3) // 4 - pad > max_bytes:
            raise ImageReject("image_too_large", "image_too_large")
        try:
            raw = base64.b64decode(payload, validate=True)
        except Exception:
            raise ImageReject("invalid_base64", "invalid_image_base64") from None
        if not raw:
            raise ImageReject("empty_image", "invalid_image_content")
        actual = _sniff_image_type(raw)
        if actual is None:
            raise ImageReject("unknown_magic", "unsupported_image_type")
        if actual != mime:
            raise ImageReject("mime_mismatch", "image_type_mismatch")
        size = len(raw)
        del raw
        if size > max_bytes:
            raise ImageReject("image_too_large", "image_too_large")
        if total + size > max_total:
            raise ImageReject("images_too_large", "images_too_large")
        total += size
        ext = _EXT[mime]
        entries.append(
            {
                "index": number,
                "msg_index": msg_index,
                "mime": mime,
                "ext": ext,
                "size": size,
                "data": b"",
                "b64": payload,
                "path": img_dir / ("img-%d.%s" % (number, ext)),
            }
        )
    return entries


def _stage_images(img_dir: Path, images: list[dict[str, object]]) -> None:
    """Материализовать проверенные изображения: каталог 0700, файлы 0600, O_EXCL.

    Байты берутся из base64 здесь, после захвата слота, и сразу сбрасываются.
    Любая ошибка ввода-вывода удаляет частичный каталог и даёт ImageSpoolError.
    """
    try:
        os.makedirs(str(img_dir.parent), exist_ok=True)
        os.mkdir(str(img_dir), 0o700)
        for img in images:
            held = img.get("data")
            data = (
                bytes(cast(bytes, held))
                if held
                else base64.b64decode(cast(str, img["b64"]), validate=True)
            )
            if len(data) != cast(int, img["size"]):
                raise ValueError("size mismatch")
            fd = os.open(str(img["path"]), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                handle = os.fdopen(fd, "wb")
            except BaseException:
                os.close(fd)
                raise
            with handle:
                _ = handle.write(data)
            img["data"] = b""
            _ = img.pop("b64", None)
    except (OSError, ValueError) as exc:
        shutil.rmtree(str(img_dir), ignore_errors=True)
        raise ImageSpoolError(type(exc).__name__) from None


def _cleanup_img_dir(img_dir: Path) -> None:
    """Удалить каталог хода и снять его с реестра активных (ошибка видна в журнале)."""
    try:
        shutil.rmtree(str(img_dir))
    except FileNotFoundError:
        pass
    except OSError as exc:
        _log("image_cleanup_error err=%s" % type(exc).__name__)
        shutil.rmtree(str(img_dir), ignore_errors=True)
    finally:
        with _active_lock:
            _active_img_dirs.discard(str(img_dir))


_IMAGE_MARKER = re.compile(r"\[image \d+\]")


def _text_only_prompt_fallback(prompt: str) -> str:
    """Безопасный media-free промпт из готового: без `[attachments]` и `[image N]`.

    Запасной путь для вызывающих `_run_once` без предвычисленного
    `stripped_full_prompt`; штатно промпт берётся из `_messages_to_stripped_prompt`.
    """
    cut = prompt.rfind("[attachments]\n")
    if cut == 0 or (cut > 0 and prompt[cut - 2 : cut] == "\n\n"):
        prompt = prompt[:cut].rstrip()
    text = _IMAGE_MARKER.sub(_IMAGE_OMITTED, prompt).strip()
    return text or "Reply with exactly: PONG"


def _downgrade_to_text_in_run_once(
    ctx: dict[str, object],
    stage: str,
    reason: str,
    attempt: int,
    img_dir: Path | None,
) -> None:
    """Перевести ход в text-only: журнал, каталог, CID и оба промпта (AD-003).

    Порядок: событие (счёт ДО обнуления) -> удаление собственного каталога ->
    CAS-инвалидация и снятие владения старым CID -> `prompt`/`full_prompt` из
    предвычисленной media-free истории. Run вызывающий уже закрыл; повторный
    вызов безопасен (cleanup идемпотентен, CID уже пуст).
    """
    held = cast("list[dict[str, object]]", ctx.get("images") or [])
    _log_image_fallback(stage, reason, str(ctx.get("model") or ""), attempt, len(held))
    if img_dir is not None:
        _cleanup_img_dir(img_dir)
    old_cid = str(ctx.get("conversation_id") or "")
    if old_cid:
        sess_key = ctx.get("sess_key")
        if sess_key:
            _session_invalidate(cast(tuple, sess_key), old_cid)
        _cid_release(old_cid, str(ctx.get("turn_id") or ""))
        if ctx.get("hot_resumed"):
            with _session_store_lock:
                _in_flight_cids.discard(old_cid)
    stripped = ctx.get("stripped_full_prompt")
    if not isinstance(stripped, str) or not stripped:
        stripped = _text_only_prompt_fallback(
            str(ctx.get("full_prompt") or ctx.get("prompt") or "")
        )
    ctx["hot_resumed"] = False
    ctx["conversation_id"] = ""
    ctx["images"] = []
    ctx["img_dir"] = None
    ctx["prompt"] = stripped
    ctx["full_prompt"] = stripped


def _attachments_block(images: list[dict[str, object]]) -> str:
    lines = [
        "[attachments]",
        "The user attached %d image file(s), accessible in the workspace directory"
        % len(images)
        + " via --add-dir:",
    ]
    for img in images:
        lines.append(
            "- [image %d] %s (%s, %d bytes)"
            % (
                cast(int, img["index"]),
                str(img["path"]),
                cast(str, img["mime"]),
                cast(int, img["size"]),
            )
        )
    lines.append(
        "Read every attached image file listed above using your file/image inspection"
        + " tool (e.g. view_file) before answering."
    )
    return "\n".join(lines)


def _render_message(
    msg: Any, counter: list, img_counter: list[int] | None = None
) -> str:
    """Сообщение OpenAI в текстовый блок промпта (роли не теряются)."""
    if not isinstance(msg, dict):
        return ""
    role = str(msg.get("role") or "user")
    name = msg.get("name")
    label = role if not name else "%s(%s)" % (role, name)
    body = _flatten_content(msg.get("content"), img_counter)
    lines = []
    calls = msg.get("tool_calls")
    if isinstance(calls, list):
        for call in calls:
            if not isinstance(call, dict):
                continue
            fn = call.get("function") if isinstance(call.get("function"), dict) else {}
            fname = str(fn.get("name") or "unknown")
            fargs = fn.get("arguments")
            if not isinstance(fargs, str):
                fargs = (
                    json.dumps(fargs, ensure_ascii=False) if fargs is not None else "{}"
                )
            lines.append(
                "[tool call %s] %s(%s)" % (call.get("id") or "call", fname, fargs)
            )
    if role == "tool":
        cid = msg.get("tool_call_id") or "call"
        lines.append("[tool result %s] %s" % (cid, body))
    elif body:
        lines.append(body)
    prepared = "\n".join(lines).strip()
    if not prepared:
        return ""
    counter[0] += 1
    return "### %d. %s\n%s" % (counter[0], label, prepared)


def _messages_to_prompt(
    messages: list,
    images: list[dict[str, object]] | None = None,
    img_start: int = 0,
) -> str:
    """Собрать единый текстовый промпт хода.

    Секцию протокола инструментов добавляет `_with_tools_protocol` (только при
    эмуляции tools). Image-части получают сквозные маркеры `[image N]` (нумерация с `img_start + 1`),
    а `images` описываются блоком `[attachments]` с абсолютными путями файлов.
    Промпт сверх `PROMPT_MAX_NDJSON_BYTES` проходит head-pruning (ADR-0008).
    """
    counter = [0]
    img_counter = [img_start]
    blocks: list[tuple[int, str, str]] = []
    for index, msg in enumerate(messages):
        rendered = _render_message(msg, counter, img_counter)
        if rendered:
            role = str(msg.get("role") or "user") if isinstance(msg, dict) else ""
            blocks.append((index, role, rendered))
    tail_block = _attachments_block(images) if images else ""
    text = _join_prompt_parts([b[2] for b in blocks], tail_block)
    if not text:
        return "Reply with exactly: PONG"
    limit = PROMPT_MAX_NDJSON_BYTES
    if not AGY_BRIDGE_ENABLE_HEAD_PRUNING or _ndjson_bytes(text) <= limit:
        return text
    return _prune_prompt_blocks(blocks, tail_block, limit)


def _join_prompt_parts(parts: list[str], tail_block: str = "") -> str:
    joined = list(parts)
    if tail_block:
        joined.append(tail_block)
    return "\n\n".join(joined).strip()


def _is_synthetic_user_block(rendered_text: str) -> bool:
    """Синтетическое напоминание/снимок рантайма, а не ввод человека (ADR-0019).

    Завершённые теги занимают всё тело без полезного текста снаружи. Уведомления
    распознаются по полному известному формату; совпадения префикса недостаточно.
    Неизвестные форматы остаются вводом человека, чтобы не потерять директиву.
    """
    lines = rendered_text.splitlines()
    body = "\n".join(
        lines[1:] if len(lines) > 1 and lines[0].startswith("### ") else lines
    ).strip()
    if not body:
        return False
    if (
        SYNTHETIC_REMINDER_RE.search(body)
        and not SYNTHETIC_REMINDER_RE.sub("", body).strip()
    ):
        return True
    return any(
        pattern.fullmatch(body) is not None
        for pattern in (SYNTHETIC_RUNTIME_RE, SYNTHETIC_POLICY_RE, SYNTHETIC_NOTICE_RE)
    )


def _prompt_anchor_indices(blocks: list[tuple[int, str, str]]) -> set[int]:
    """Индексы блоков, которые head-pruning не отбрасывает (ADR-0008, ADR-0019).

    Якоря: системное `messages[0]`, реальные сообщения пользователя текущего хода
    (последний не-синтетический user и все реальные после предшествующего ему
    assistant), сам этот assistant, последний блок истории (assistant/tool/реальный
    user), ровно один последний assistant всей истории и результаты инструментов
    активного хода (после последнего assistant; без assistant в срезе — все).
    Исторические tool-результаты до последнего assistant вытесняются штатно.
    С числом реальных user текущего хода сверх ANCHOR_USER_NO_ASSISTANT_MAX
    якоря — первый (исходная цель) и последние ANCHOR_USER_TAIL_COUNT, промежуточные
    вытесняются head-pruning (Cycle 4 F-002). Без реальных user последний user
    закрепляется безусловно, даже при исторических tool-блоках (Cycle 4 F-001):
    крупный сжимается серединой с сохранением краёв, а не теряется.
    """
    count = len(blocks)
    anchors: set[int] = set()
    if not count:
        return anchors
    if blocks[0][0] == 0 and blocks[0][1] == "system":
        anchors.add(0)
    last = count - 1

    # Поиск реальных (не синтетических) пользовательских сообщений (ADR-0019)
    real_user_indices = [
        i
        for i in range(count)
        if blocks[i][1] == "user" and not _is_synthetic_user_block(blocks[i][2])
    ]

    if real_user_indices:
        last_real_user = real_user_indices[-1]
        anchors.add(last_real_user)
        preceding_assistant_idx = next(
            (
                i
                for i in range(last_real_user - 1, -1, -1)
                if blocks[i][1] == "assistant"
            ),
            -1,
        )
        if preceding_assistant_idx >= 0:
            anchors.add(preceding_assistant_idx)
        turn_users = [u for u in real_user_indices if u > preceding_assistant_idx]
        if len(turn_users) > ANCHOR_USER_NO_ASSISTANT_MAX:
            # Пачка user с assistant или без: исходная цель и хвост (Cycle 5 F-005).
            anchors.add(turn_users[0])
            tail_count = min(ANCHOR_USER_TAIL_COUNT, ANCHOR_USER_NO_ASSISTANT_MAX)
            anchors.update(turn_users[-tail_count:])
        else:
            # Все реальные user текущего хода (после предшествующего assistant).
            anchors.update(turn_users)
    else:
        # Fallback: реальных user нет; последний user — носитель ввода, закрепляется
        # безусловно, исторические tool-блоки этому не мешают (Cycle 4 F-001).
        last_user_idx = next(
            (i for i in range(last, -1, -1) if blocks[i][1] == "user"), -1
        )
        if last_user_idx >= 0:
            anchors.add(last_user_idx)

    # Сохранение последнего блока, если это assistant или tool, либо реальный user.
    # Хвостовая синтетика в якоря не попадает: при дефиците бюджета она уходит
    # первой (секция synthetic в droppable), не вырезая реальный ввод.
    if blocks[last][1] in ("assistant", "tool"):
        anchors.add(last)
    elif not _is_synthetic_user_block(blocks[last][2]):
        anchors.add(last)

    # Последний assistant всей истории (контекст tool calls) — ровно один: если он
    # уже якорь, более старые не добираются, чтобы не съедать бюджет (F-002).
    last_assistant = next(
        (i for i in range(last, -1, -1) if blocks[i][1] == "assistant"), -1
    )
    if last_assistant >= 0:
        anchors.add(last_assistant)

    # Результаты инструментов только активного хода (после последнего assistant);
    # срез без assistant (`new_msgs` продолжения) — весь активный ход (F-003).
    anchors.update(
        i for i in range(last_assistant + 1, count) if blocks[i][1] == "tool"
    )
    return anchors


def _prompt_priority_indices(
    blocks: list[tuple[int, str, str]],
) -> tuple[set[int], set[int]]:
    """Активные инструменты и защищённые блоки для сжатия (ADR-0019, Cycle 5 F-001).

    Защищены системное `messages[0]` и якорные user текущего хода;
    без реальных user используется служебный ввод. Инструменты подчинены им:
    их тела и заголовки сокращаются до любого сжатия защищённого ввода.
    """
    count = len(blocks)
    protected: set[int] = set()
    if count and blocks[0][0] == 0 and blocks[0][1] == "system":
        protected.add(0)
    users = [i for i in range(count) if blocks[i][1] == "user"]
    real_users = [i for i in users if not _is_synthetic_user_block(blocks[i][2])]
    carrier = real_users or users
    last_assistant = next(
        (i for i in range(count - 1, -1, -1) if blocks[i][1] == "assistant"), -1
    )
    preceding_assistant_idx = (
        next(
            (i for i in range(carrier[-1] - 1, -1, -1) if blocks[i][1] == "assistant"),
            -1,
        )
        if carrier
        else -1
    )
    turn_users = [u for u in carrier if u > preceding_assistant_idx]
    if turn_users:
        tail_count = min(ANCHOR_USER_TAIL_COUNT, ANCHOR_USER_NO_ASSISTANT_MAX)
        if len(turn_users) > ANCHOR_USER_NO_ASSISTANT_MAX:
            protected.add(turn_users[0])
            protected.update(turn_users[-tail_count:])
        else:
            protected.update(turn_users)
    active_tools = {
        i for i in range(last_assistant + 1, count) if blocks[i][1] == "tool"
    }
    return active_tools, protected


def _prune_prompt_blocks(
    blocks: list[tuple[int, str, str]], tail_block: str, limit: int
) -> str:
    """Head-pruning структурированной истории под потолок NDJSON (ADR-0008, REQ-01, ADR-0019).

    Якоря (`_prompt_anchor_indices`) и `[attachments]` не отбрасываются. Первыми
    уходят неякорные синтетические напоминания, затем история от старых к новым;
    оставшиеся блоки идут в исходном порядке, на месте каждого отброшенного
    отрезка — маркерное сообщение. Если не влезают даже якоря — приоритетное
    сжатие `_cap_prompt_parts`: сначала история и активные tool-результаты,
    затем их заголовки; система, носитель ввода и вложения защищены. Заголовок `### N. role`
    каждого оставшегося сообщения сохраняется.
    """
    count = len(blocks)
    anchors = _prompt_anchor_indices(blocks)
    synthetic = {
        i
        for i in range(count)
        if blocks[i][1] == "user" and _is_synthetic_user_block(blocks[i][2])
    }
    droppable = [i for i in range(count) if i not in anchors and i in synthetic] + [
        i for i in range(count) if i not in anchors and i not in synthetic
    ]
    marker_block = "### user\n" + HISTORY_PRUNED_MARKER

    def assemble(drop_count: int) -> list[str]:
        dropped = set(droppable[:drop_count])
        parts: list[str] = []
        in_gap = False
        for i, block in enumerate(blocks):
            if i in dropped:
                if not in_gap:
                    parts.append(marker_block)
                    in_gap = True
                continue
            in_gap = False
            parts.append(block[2])
        return parts

    # Минимальное число отброшенных блоков: размер монотонно убывает с ростом числа.
    low, high = 1, len(droppable)
    if high and _ndjson_bytes(_join_prompt_parts(assemble(high), tail_block)) <= limit:
        while low < high:
            mid = (low + high) // 2
            if _ndjson_bytes(_join_prompt_parts(assemble(mid), tail_block)) <= limit:
                high = mid
            else:
                low = mid + 1
        dropped_count = high
        text = _join_prompt_parts(assemble(high), tail_block)
    else:
        dropped_count = len(droppable)
        parts = assemble(dropped_count)
        # Позиции сообщений в `parts` по группам приоритета; маркеры пропуска и
        # `[attachments]` не сжимаются и не вытесняются.
        active_blocks, protected_blocks = _prompt_priority_indices(blocks)
        dropped_set = set(droppable)
        kept = [i for i in range(count) if i not in dropped_set]
        message_parts = [k for k, part in enumerate(parts) if part != marker_block]
        block_at = dict(zip(message_parts, kept))
        priority_blocks = active_blocks | protected_blocks
        historical = [k for k in message_parts if block_at[k] not in priority_blocks]
        active = [k for k in message_parts if block_at[k] in active_blocks]
        protected = {k for k in message_parts if block_at[k] in protected_blocks}
        if tail_block:
            protected.add(len(parts))
            parts.append(tail_block)
        parts = _cap_prompt_parts(parts, historical, active, limit, protected)
        text = _ensure_prompt_fits_ndjson(_join_prompt_parts(parts), limit)
    final_bytes = _ndjson_bytes(text)
    _log(
        f"history pruned: dropped {dropped_count} messages, "
        f"final ndjson bytes={final_bytes}"
    )
    return text


def _cap_prompt_parts(
    parts: list[str],
    historical: list[int],
    active: list[int],
    limit: int,
    protected: set[int] | None = None,
) -> list[str]:
    """Приоритетное сжатие якорей под `limit` (ADR-0019, Cycle 5 F-001).

    История и активные инструменты сначала сжимаются до пола с сохранением краёв,
    затем тела инструментов обнуляются раньше истории; если не влезают заголовки,
    сначала вытесняются инструменты, затем история. Защищённые система, носитель
    ввода и вложения не участвуют в этих операциях. Только если они одни превышают лимит, сжимаются их середины.
    """
    out = list(parts)
    keep = protected or set()
    historical = [k for k in historical if k not in keep]
    active = [k for k in active if k not in keep]
    if _prompt_parts_fit(out, limit):
        return out
    out = _middle_prune_group(out, historical, limit)
    out = _middle_prune_group(out, active, limit)
    if _prompt_parts_fit(out, limit):
        return out
    capped = _cap_group_bodies(out, active, limit)
    if capped is not None:
        return capped
    out = _cap_group_to(out, active, 0)
    capped = _cap_group_bodies(out, historical, limit)
    if capped is not None:
        return capped
    out = _cap_group_to(out, historical, 0)

    evictable = sorted(active) + sorted(historical)
    active_set = set(active) - keep
    marker_block = "### user\n" + HISTORY_PRUNED_MARKER

    def evict(n: int) -> tuple[list[str], list[int], list[int]]:
        dropped = set(evictable[:n])
        result: list[str] = []
        result_active: list[int] = []
        result_protected: list[int] = []
        for k, part in enumerate(out):
            if k in dropped or part == marker_block:
                if not result or result[-1] != marker_block:
                    result.append(marker_block)
                continue
            if k in active_set:
                result_active.append(len(result))
            if k in keep:
                result_protected.append(len(result))
            result.append(part)
        return result, result_active, result_protected

    def fits_after(n: int) -> bool:
        evicted, evicted_active, _ = evict(n)
        return _prompt_parts_fit(_cap_group_to(evicted, evicted_active, 0), limit)

    low, high = 1, len(evictable)
    if not high or not fits_after(high):
        # Все лишние заголовки удалены; лишь теперь режем середины защищённых.
        evicted, _, survivors = evict(high)
        evicted = _middle_prune_group(evicted, survivors, limit)
        if _prompt_parts_fit(evicted, limit):
            return evicted
        # Защитный рубеж для лимита меньше суммарного пола защищённых блоков.
        return _cap_group_bodies(evicted, survivors, limit) or _cap_group_to(
            evicted, survivors, 0
        )
    while low < high:
        mid = (low + high) // 2
        if fits_after(mid):
            high = mid
        else:
            low = mid + 1
    evicted, evicted_active, _ = evict(high)
    _log(f"history headers evicted: {high} messages")
    return _cap_group_bodies(evicted, evicted_active, limit) or evicted


def _prompt_parts_fit(parts: list[str], limit: int) -> bool:
    return _ndjson_bytes(_join_prompt_parts(parts)) <= limit


def _middle_prune_group(parts: list[str], group: list[int], limit: int) -> list[str]:
    """Вырезать середины блоков `group` пропорционально их запасу сверх пола.

    Пол — заголовок `### N. role`, голова и хвост тела по PRUNE_EDGE_MIN_BYTES плюс
    маркер: ни один блок группы не зануляется; блоки вне `group` не трогаются.
    """
    out = list(parts)
    marker_bytes = _json_text_bytes(MIDDLE_PRUNED_MARKER)
    floors = {
        k: 2 * (PRUNE_EDGE_MIN_BYTES + _json_text_bytes(parts[k].partition("\n")[0]))
        + marker_bytes
        for k in group
    }
    for _round in range(len(group) + 1):
        excess = _ndjson_bytes(_join_prompt_parts(out)) - limit
        if excess <= 0:
            break
        sizes = {k: _json_text_bytes(out[k]) for k in group}
        spare = {k: max(size - floors[k], 0) for k, size in sizes.items()}
        pool = sum(spare.values())
        if not pool:
            break
        changed = False
        for k, room in spare.items():
            if not room:
                continue
            cut = min(room, -(-excess * room // pool))
            pruned = _middle_prune_text(out[k], sizes[k] - cut)
            if pruned != out[k]:
                out[k] = pruned
                changed = True
        if not changed:
            break
    return out


def _cap_group_to(parts: list[str], group: list[int], cap: int) -> list[str]:
    out = list(parts)
    for k in group:
        out[k] = _cap_prompt_block(parts[k], cap)
    return out


def _cap_group_bodies(
    parts: list[str], group: list[int], limit: int
) -> list[str] | None:
    """Наибольший общий потолок блоков `group`, при котором промпт влезает в `limit`.

    Блоки крупнее потолка сжимаются серединой тела, заголовок сохраняется; None —
    промпт не влезает даже при пустых телах группы.
    """
    if not _prompt_parts_fit(_cap_group_to(parts, group, 0), limit):
        return None
    low = 0
    high = max((_json_text_bytes(parts[k]) for k in group), default=0)
    while low < high:
        mid = (low + high + 1) // 2
        if _prompt_parts_fit(_cap_group_to(parts, group, mid), limit):
            low = mid
        else:
            high = mid - 1
    return _cap_group_to(parts, group, low)


def _cap_prompt_block(block: str, cap: int) -> str:
    """Сжать блок промпта до `cap` экранированных байт, не трогая заголовок `### N. role`."""
    if _json_text_bytes(block) <= cap:
        return block
    header, sep, body = block.partition("\n")
    if not header.startswith("### "):
        return _middle_prune_text(block, cap)
    if not sep:
        return header
    budget = max(cap - _json_text_bytes(header + sep), 0)
    pruned = _middle_prune_text(body, budget)
    # Пустое тело — только заголовок: без висячего перевода строки на границе блоков.
    return header + sep + pruned if pruned else header


def _json_text_bytes(text: str) -> int:
    """Байты UTF-8 строки после JSON-экранирования, без обрамляющих кавычек."""
    return len(json.dumps(text, ensure_ascii=False).encode("utf-8")) - 2


def _middle_prune_text(text: str, max_text_bytes: int) -> str:
    """Вырезать середину `text` с MIDDLE_PRUNED_MARKER под экранированный бюджет.

    Голова (командная директива) и хвост (аргументы) делятся поровну по символам;
    результат — наибольший, чей JSON-экранированный размер <= `max_text_bytes`.
    """
    if _json_text_bytes(text) <= max_text_bytes:
        return text
    if _json_text_bytes(MIDDLE_PRUNED_MARKER) > max_text_bytes:
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if _json_text_bytes(text[:mid]) <= max_text_bytes:
                low = mid
            else:
                high = mid - 1
        return text[:low]

    def build(keep: int) -> str:
        head = (keep + 1) // 2
        tail = keep // 2
        return text[:head] + MIDDLE_PRUNED_MARKER + (text[-tail:] if tail else "")

    low, high = 0, len(text) - 1
    while low < high:
        mid = (low + high + 1) // 2
        if _json_text_bytes(build(mid)) <= max_text_bytes:
            low = mid
        else:
            high = mid - 1
    return build(low)


def _ensure_prompt_fits_ndjson(prompt: str, max_bytes: int | None = None) -> str:
    """Защитный рубеж: строка NDJSON промпта не длиннее `max_bytes` байт UTF-8.

    agy молча режет хвост длинного входа, поэтому при превышении вырезается
    середина промпта (голова и хвост с последним вводом сохраняются).
    """
    limit = PROMPT_MAX_NDJSON_BYTES if max_bytes is None else max_bytes
    size = _ndjson_bytes(prompt)
    if size <= limit:
        return prompt
    pruned = _middle_prune_text(prompt, limit - _ndjson_bytes(""))
    _log(f"prompt middle-pruned: ndjson bytes {size} -> {_ndjson_bytes(pruned)}")
    return pruned


def _get_resumed_turn_prompt(
    messages: list, images: list[dict[str, object]] | None = None
) -> str:
    """Промпт хода продолжения: сообщения после последнего assistant.

    Маркеры сохраняют сквозные номера всей истории; `[attachments]` — только для
    изображений новых сообщений. Без assistant в истории — вся история целиком.
    """
    last_asst = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], dict) and messages[i].get("role") == "assistant":
            last_asst = i
            break
    if last_asst >= 0 and last_asst + 1 < len(messages):
        new_msgs = messages[last_asst + 1 :]
        skipped = len(_collect_image_parts(cast("list[object]", messages[: last_asst + 1])))
        delta = [
            img
            for img in (images or [])
            if cast(int, img.get("msg_index", 0)) > last_asst
        ]
        prompt = _messages_to_prompt(new_msgs, delta, skipped)
        if prompt:
            return prompt
    return _messages_to_prompt(messages, images)


def _session_key_for(
    model: str, cwd: str, effort: str, raw_chat_id: str = ""
) -> tuple[str, ...]:
    """Ключ горячей сессии: токен чата, иначе cwd; без обоих ключ пуст.

    Сырой chat id в стор и на диск не попадает — только префикс его SHA-256.
    Переданный, но невалидный cwd (не строка, относительный, длиннее
    CWD_MAX_LEN, с NUL/контролами/суррогатами) — fail-closed: ключа нет.
    Пустой cwd допустим только при штатном отсутствии cwd (None или "").
    """
    chat = raw_chat_id.strip() if isinstance(raw_chat_id, str) else ""
    # Суррогаты и контролы в chat id не должны доходить до encode("utf-8").
    if any(
        ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in chat
    ):
        return ()

    cwd_norm = ""
    if cwd is not None:
        if isinstance(cwd, str):
            val = cwd.strip()
            if val:
                if (
                    len(val) > CWD_MAX_LEN
                    or not os.path.isabs(val)
                    or "\x00" in val
                    or any(
                        ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF
                        for c in val
                    )
                ):
                    return ()
                cwd_norm = os.path.normpath(val)
        else:
            return ()

    if chat:
        chat_token = hashlib.sha256(chat.encode("utf-8")).hexdigest()[:16]
        return (chat_token, model, cwd_norm, effort)
    if cwd_norm:
        return (model, cwd_norm, effort)
    return ()


def _request_chat_id(
    headers: Any, extra: dict[str, object], req: dict[str, object] | None = None
) -> tuple[str, bool]:
    """Первый переданный chat ID и признак невалидного идентификатора."""
    for value in (
        headers.get("x-dsh-chat-id"),
        headers.get("x-session-id"),
        extra.get("chat_id"),
        (req or {}).get("chat_id"),
    ):
        if value is None:
            continue
        if not isinstance(value, str) or len(value) > 256 or any(
            ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF
            for c in value
        ):
            return "", True
        val = value.strip()
        return val, not bool(val)
    return "", False


def _session_key_valid(sess_key: tuple[str, ...]) -> bool:
    """Стор принимает только ключ с непустым токеном чата или cwd."""
    if len(sess_key) == 4:
        return bool(sess_key[0].strip())
    if len(sess_key) == 3:
        return bool(sess_key[1].strip())
    return False


def _session_claim(sess_key: tuple[str, ...], turn_id: str = "") -> str:
    """Найти живую свободную сессию и занять её; '' — сессии нет.

    Проверка и занятие идут под одним замком: два параллельных запроса не
    получат один и тот же conversation_id. При непустом `turn_id` владение cid
    регистрируется в `_active_cid_owners` в той же критической секции.
    """
    if not _session_key_valid(sess_key):
        return ""
    now = time.time()
    evicted = False
    try:
        with _session_store_lock:
            entry = _session_store.get(sess_key)
            if entry is None:
                return ""
            if _session_expired(entry, now):
                _session_store.pop(sess_key, None)
                evicted = True
                return ""
            cid = cast(str, entry["cid"])
            if cid in _in_flight_cids:
                return ""
            owner = _active_cid_owners.get(cid)
            if owner is not None and owner != turn_id:
                return ""
            _in_flight_cids.add(cid)
            if turn_id:
                _active_cid_owners[cid] = turn_id
            return cid
    finally:
        if evicted:
            _persist_sessions()


def _session_expired(entry: dict[str, Any], now: float) -> bool:
    return (
        now - entry["last_used"] > SESSION_IDLE_TTL_S
        or now - entry["created"] > SESSION_MAX_TTL_S
        or entry["turns"] >= SESSION_MAX_TURNS
    )


def _session_invalidate(sess_key: tuple, cid: str) -> None:
    removed = False
    with _session_store_lock:
        entry = _session_store.get(sess_key)
        if entry is not None and entry["cid"] == cid:
            _session_store.pop(sess_key, None)
            removed = True
    if removed:
        _persist_sessions()


def _session_commit(sess_key: tuple[str, ...], cid: str) -> None:
    if not _session_key_valid(sess_key):
        return
    now = time.time()
    with _session_store_lock:
        entry = _session_store.get(sess_key)
        if entry is not None and entry["cid"] == cid:
            entry["last_used"] = now
            entry["turns"] += 1
        else:
            _session_store[sess_key] = {
                "cid": cid,
                "last_used": now,
                "created": now,
                "turns": 1,
            }
    _persist_sessions()


def _sessions_file_path() -> Path:
    override = os.environ.get(SESSIONS_FILE_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path(WORKSPACE) / "state" / "sessions.json"


def _session_key_to_json(key: tuple) -> list[str]:
    return [str(part) for part in key]


def _session_key_from_json(raw: object) -> tuple[str, ...] | None:
    """Строковый ключ с токеном чата или cwd; вырожденный ключ -> None."""
    if not isinstance(raw, list) or len(raw) not in (3, 4):
        return None
    items = cast("list[object]", raw)
    if not all(isinstance(part, str) for part in items):
        return None
    parts = cast("list[str]", items)
    if len(parts) == 4 and not parts[0].strip():
        return None
    cwd_index = 2 if len(parts) == 4 else 1
    cwd = parts[cwd_index].strip()
    if cwd:
        if not os.path.isabs(cwd):
            return None
        parts[cwd_index] = os.path.normpath(cwd)
    elif len(parts) == 4:
        parts[cwd_index] = ""
    else:
        return None
    key = tuple(parts)
    if not _session_key_valid(key):
        return None
    return key


def _session_entry_from_json(item: object, now: float) -> dict[str, Any] | None:
    """Проверенная живая запись стора из JSON; битая или протухшая -> None."""
    if not isinstance(item, dict):
        return None
    data = cast("dict[str, object]", item)
    cid = data.get("cid")
    if not isinstance(cid, str) or _CID_RE.fullmatch(cid) is None:
        return None
    stamps: list[float] = []
    for name in ("created", "last_used"):
        value = data.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(value):
            return None
        stamps.append(float(value))
    turns = data.get("turns")
    if isinstance(turns, bool) or not isinstance(turns, int) or turns < 0:
        return None
    entry: dict[str, Any] = {
        "cid": cid,
        "created": stamps[0],
        "last_used": stamps[1],
        "turns": turns,
    }
    if _session_expired(entry, now):
        return None
    return entry


def _atomic_write_sessions_json(
    snapshot: dict[tuple[str, ...], dict[str, Any]],
) -> None:
    """Атомарно записать снимок стора: temp в том же каталоге + fsync + os.replace.

    Файл 0600, каталог 0700. Ошибка I/O только логируется (fail-open): горячие
    сессии в памяти продолжают работать.
    """
    path = _sessions_file_path()
    payload = {
        "version": SESSIONS_FILE_VERSION,
        "sessions": [
            {
                "key": _session_key_to_json(key),
                "cid": entry["cid"],
                "created": entry["created"],
                "last_used": entry["last_used"],
                "turns": entry["turns"],
            }
            for key, entry in snapshot.items()
        ],
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    tmp_name = ""
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=str(path.parent), prefix=".sessions-", suffix=".tmp", delete=False
        ) as fh:
            tmp_name = fh.name
            _ = fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, str(path))
        tmp_name = ""
    except OSError as exc:
        _log(f"sessions-persist-error err={type(exc).__name__}")
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def _persist_sessions() -> None:
    """Снимок стора на диск: замок файла -> копия под замком памяти -> I/O без него."""
    if not (AGY_BRIDGE_ENABLE_SESSION_PERSISTENCE and _sessions_persist_ready):
        return
    with _sessions_file_lock:
        with _session_store_lock:
            snapshot = {key: dict(entry) for key, entry in _session_store.items()}
        _atomic_write_sessions_json(snapshot)


def _load_persisted_sessions(now: float | None = None) -> int:
    """Восстановить горячие сессии из sessions.json и включить запись на диск.

    Битый файл не мешает старту (fail-open); протухшие по TTL/turns записи
    отбрасываются, файл переписывается актуальным снимком. Возвращает число
    восстановленных сессий.
    """
    global _sessions_persist_ready
    if not AGY_BRIDGE_ENABLE_SESSION_PERSISTENCE:
        return 0
    moment = time.time() if now is None else now
    path = _sessions_file_path()
    restored: dict[tuple[str, ...], dict[str, Any]] = {}
    with _sessions_file_lock:
        data: object = None
        try:
            data = json.loads(path.read_bytes())
        except FileNotFoundError:
            data = None
        except (OSError, ValueError) as exc:
            _log(f"sessions-load-error err={type(exc).__name__} (fail-open)")
        items: object = None
        if isinstance(data, dict):
            doc = cast("dict[str, object]", data)
            if doc.get("version") == SESSIONS_FILE_VERSION:
                items = doc.get("sessions")
        if isinstance(items, list):
            for item in cast("list[object]", items):
                if not isinstance(item, dict):
                    continue
                key = _session_key_from_json(cast("dict[str, object]", item).get("key"))
                entry = _session_entry_from_json(item, moment)
                if key is not None and entry is not None:
                    restored[key] = entry
        with _session_store_lock:
            for key, entry in restored.items():
                _ = _session_store.setdefault(key, entry)
        _sessions_persist_ready = True
    _persist_sessions()
    _log(f"sessions restored={len(restored)} path={path}")
    return len(restored)


# Только явные HTTP-статусы 502/503 и сетевой сброс: свободный текст модели
# («Bad Gateway is a term», «timed out») транзиентным сбоем не считается.
_TRANSIENT_UPSTREAM_RE = re.compile(
    r"\b(?:HTTP(?:/\d(?:\.\d)?)?|status|code)\s*[:=]?\s*50[23]\b"
    r"|\b502 Server Error\b|\b503 Service Unavailable\b|\bConnectionResetError\b",
    re.IGNORECASE,
)


def _is_transient_upstream_error(err: object) -> bool:
    """Внешний сбой upstream: явный HTTP 502/503 или ConnectionResetError."""
    if not err:
        return False
    text = err if isinstance(err, str) else str(err)
    return any((_TRANSIENT_UPSTREAM_RE.search(text), is_transient_stream_interruption(text)))


def _ndjson_bytes(prompt: str) -> int:
    """Размер строки NDJSON для stdin agy в байтах UTF-8 (с переводом строки)."""
    return len(_ndjson_user_line(prompt).encode("utf-8"))


def _ndjson_user_line(prompt: str) -> str:
    """Строка NDJSON для stdin agy — единственный поддерживаемый вход промпта."""
    payload = {
        "event": "user",
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": prompt}],
        },
    }
    return json.dumps(payload, ensure_ascii=False) + "\n"


# Delegated to agy_runtime.process_supervisor (AD-002, M-MOD-I1)
_supervisor = ProcessSupervisor(
    ProcessSupervisorConfig(
        kill_term_grace_s=KILL_TERM_GRACE_S,
        kill_wait_s=KILL_WAIT_S,
    )
)
_group_alive = _supervisor.group_alive
_kill_group = _supervisor.kill_group
_LIFECYCLE = SubbridgeLifecycle(hooks=SubbridgeHooks(procs_fn=lambda: list(_active.copy().values()), cleanup_fn=lambda: _supervisor.kill_all([p for p in _active.copy().values() if p.returncode is None]), log_fn=_log), workspace=WORKSPACE)


# ---- Guardrails SQLite-источника мышления (AD-005, AD-006) -----------------------


def _reset_sqlite_guards_for_tests() -> None:
    """Сбросить процессные глобалы guardrails (хелпер тестов)."""
    global _breaker_state, _breaker_failures, _breaker_opened_at, _breaker_probe_gen
    global _breaker_active_probe_gen, _breaker_probe_started_at, _retry_tenths
    global _compat_ident, _compat_state, _flag_value, _flag_key, _flag_checked_at
    global _sqlite_divergence_count, _sqlite_drain_deadline_count
    global _sqlite_open_connections, _sqlite_max_open_connections, _rng
    global _cfg_snapshot, _cfg_key, _cfg_checked_at, _image_flag_cache, _image_fallback_flag_cache
    with _cfg_lock:
        _cfg_snapshot = _COLD_FLAGS
        _cfg_key = None
        _cfg_checked_at = None
    with _image_flag_lock:
        _image_flag_cache = (0.0, False)
    with _image_fallback_flag_lock:
        _image_fallback_flag_cache = (0.0, False)
    with _sha_cache_lock:
        _sha_cache.clear()
    with _sqlite_guard_lock:
        _breaker_state = "CLOSED"
        _breaker_failures = 0
        _breaker_opened_at = 0.0
        _breaker_probe_gen = 0
        _breaker_active_probe_gen = None
        _breaker_probe_started_at = 0.0
        _retry_tenths = RETRY_CAPACITY_TENTHS
        _compat_ident = None
        _compat_state = "SHADOW"
        _flag_value = False
        _flag_key = None
        _flag_checked_at = None
        _sqlite_divergence_count = 0
        _sqlite_drain_deadline_count = 0
        _sqlite_open_connections = 0
        _sqlite_max_open_connections = 0
        _rng = random.random
    with _session_store_lock:
        _active_cid_owners.clear()


def _runtime_flag_on() -> bool:
    """Рантайм-флаг SQLITE_REASONING_ENABLED из dynamic_config.json (fail-closed).

    Файл читается со stat-кэшем (mtime_ns, size) и TTL 1.0 с: JSON разбирается
    один раз, пока stat не изменился. Любая ошибка чтения, отсутствие ключа или
    не-boolean значение дают False.
    """
    global _flag_value, _flag_key, _flag_checked_at
    now = time.monotonic()
    with _sqlite_guard_lock:
        if _flag_checked_at is not None and now - _flag_checked_at < FLAG_TTL_S:
            return _flag_value
        known_key = _flag_key
        known_value = _flag_value
    value = False
    key: tuple[int, int] | None = None
    try:
        info = DYNAMIC_CONFIG_PATH.stat()
        key = (info.st_mtime_ns, info.st_size)
        if key == known_key:
            value = known_value
        else:
            data = cast(
                object, json.loads(DYNAMIC_CONFIG_PATH.read_text(encoding="utf-8"))
            )
            if isinstance(data, dict):
                value = cast("dict[str, object]", data).get(FLAG_NAME) is True
    except (OSError, ValueError):
        value = False
        key = None
    with _sqlite_guard_lock:
        _flag_value = value
        _flag_key = key
        _flag_checked_at = now
    return value


def _sqlite_disabled_reason() -> str:
    """'' — источник включён; иначе причина выключения: env или flag."""
    env = os.environ.get("AGY_SQLITE_REASONING_ENABLED", "1").strip().lower()
    if env in ("0", "false"):
        return "env"
    if not _runtime_flag_on():
        return "flag"
    return ""


def _is_sqlite_reasoning_enabled() -> bool:
    """Двухуровневый fail-closed выключатель SQLite-источника (REQ-011)."""
    return _sqlite_disabled_reason() == ""


# ---- Флаги новой политики (AD-005): локальный GigaRC-совместимый снимок -------------
# Stdlib-only LaunchAgent: ни SDK, ни удалённого транспорта. Старые флаги имеют
# кодовый False; stream resilience — True по брифу. Приоритет:
# env override > JSON из dynamic_config.json > кодовый default.


class _RuntimeFlags(NamedTuple):
    """Неизменяемый валидированный снимок флагов новой политики."""

    planner_content_streaming_enabled: bool = False
    emit_tool_trace: bool = False
    extended_timeout_enabled: bool = False
    graceful_timeout_on_partial: bool = False
    step_scoped_usage_enabled: bool = False
    stream_resilience_enabled: bool = True
    isolate_tool_preambles_to_reasoning: bool = True
    tool_emulation_enabled: bool = True
    self_heal_interrupted_turn: bool = True
    graceful_interruption_on_partial: bool = True
    graceful_timeout_finish_reason: str = "stop"


_NEW_FLAG_ENV = {
    "planner_content_streaming_enabled": "AGY_PLANNER_CONTENT_STREAMING_ENABLED",
    "emit_tool_trace": "AGY_BRIDGE_EMIT_TOOL_TRACE",
    "extended_timeout_enabled": "AGY_EXTENDED_TIMEOUT_ENABLED",
    "graceful_timeout_on_partial": "AGY_GRACEFUL_TIMEOUT_ON_PARTIAL",
    "step_scoped_usage_enabled": "AGY_STEP_SCOPED_USAGE_ENABLED",
    "stream_resilience_enabled": "AGY_BRIDGE_STREAM_RESILIENCE_ENABLED",
    "isolate_tool_preambles_to_reasoning": "AGY_ISOLATE_TOOL_PREAMBLES_TO_REASONING",
    "tool_emulation_enabled": "AGY_TOOL_EMULATION_ENABLED",
    "self_heal_interrupted_turn": "AGY_SELF_HEAL_INTERRUPTED_TURN",
    "graceful_interruption_on_partial": "AGY_GRACEFUL_INTERRUPTION_ON_PARTIAL",
}
_ENV_TRUE = frozenset({"1", "true", "yes", "on"})
_ENV_FALSE = frozenset({"0", "false", "no", "off"})
_COLD_FLAGS = _RuntimeFlags()
_cfg_lock = threading.Lock()
_cfg_snapshot: _RuntimeFlags = _COLD_FLAGS
_cfg_key: tuple[int, int] | None = None
_cfg_checked_at: float | None = None
_cfg_generation: int = 0


def _parse_runtime_flags(text: str) -> _RuntimeFlags:
    """Разобрать флаги; нестроковый finish_reason заменяется дефолтом 'stop'.

    ValueError для не-bool флагов отвергает файл целиком.
    """
    data = cast(object, json.loads(text))
    if not isinstance(data, dict):
        raise ValueError("dynamic_config: not an object")
    raw = cast("dict[str, object]", data)
    values: dict[str, bool] = {}
    finish_reason = _COLD_FLAGS.graceful_timeout_finish_reason
    for name in _RuntimeFlags._fields:
        default = getattr(_COLD_FLAGS, name)
        if name == "stream_resilience_enabled":
            default = raw.get(_NEW_FLAG_ENV[name], default)
        if name == "graceful_timeout_finish_reason":
            raw_val = raw.get("graceful_timeout_finish_reason")
            if raw_val is None:
                raw_val = raw.get("AGY_GRACEFUL_TIMEOUT_FINISH_REASON", default)
            if isinstance(raw_val, str):
                s = raw_val.strip().lower()
                if s in ("length", "max_tokens"):
                    finish_reason = "length"
                elif s == "stop":
                    finish_reason = "stop"
                else:
                    finish_reason = "stop"
            else:
                finish_reason = "stop"
            continue
        value = raw.get(name, default)
        if not isinstance(value, bool):
            raise ValueError("dynamic_config: %s is not boolean" % name)
        values[name] = value
    return _RuntimeFlags(**values, graceful_timeout_finish_reason=finish_reason)


def _runtime_snapshot() -> _RuntimeFlags:
    """Снимок флагов из dynamic_config.json: TTL 1.0 с, ключ версии (mtime_ns, size).

    Пока stat не изменился, JSON не разбирается (identity снимка сохраняется). Битый
    JSON или не-bool флаг отвергают файл целиком: действует last-known-good,
    на холодном старте — кодовые дефолты. Нестроковый finish_reason заменяется
    на 'stop'. При отсутствии файла используются кодовые дефолты.
    """
    global _cfg_snapshot, _cfg_key, _cfg_checked_at, _cfg_generation
    now = time.monotonic()
    with _cfg_lock:
        if _cfg_checked_at is not None and now - _cfg_checked_at < FLAG_TTL_S:
            return _cfg_snapshot
        known_key = _cfg_key
        snapshot = _cfg_snapshot
        gen = _cfg_generation
    key = known_key
    try:
        info = DYNAMIC_CONFIG_PATH.stat()
    except FileNotFoundError:
        snapshot, key = _COLD_FLAGS, None
    except OSError:
        pass  # транзиентная ошибка: остаётся last-known-good
    else:
        new_key = (info.st_mtime_ns, info.st_size)
        if new_key != known_key:
            try:
                parsed = _parse_runtime_flags(
                    DYNAMIC_CONFIG_PATH.read_text(encoding="utf-8")
                )
            except OSError:
                pass  # повторим на следующем TTL
            except ValueError:
                key = (
                    new_key  # битый файл: lastgood, без повторного разбора того же stat
                )
            else:
                snapshot, key = parsed, new_key
    with _cfg_lock:
        if _cfg_generation != gen:
            # Параллельный читатель уже записал более свежий снимок: не затираем его.
            return _cfg_snapshot
        _cfg_snapshot = snapshot
        _cfg_key = key
        _cfg_checked_at = time.monotonic()
        _cfg_generation = gen + 1
    return snapshot


def _new_flag(name: str, default: bool = False) -> bool:
    """Явный env > JSON bool > кодовый default; старые флаги выключены."""
    if name == "AGY_BRIDGE_STREAM_RESILIENCE_ENABLED":
        name = "stream_resilience_enabled"
    env = os.environ.get(_NEW_FLAG_ENV[name], "").strip().lower()
    if env in _ENV_TRUE:
        return True
    if env in _ENV_FALSE:
        return False
    return bool(getattr(_runtime_snapshot(), name, default))


def _graceful_finish_reason() -> str:
    """Возвращает finish_reason graceful-таймаута: 'stop' или 'length'.

    Приоритет: валидный AGY_GRACEFUL_TIMEOUT_FINISH_REASON, затем
    graceful_timeout_finish_reason из dynamic_config.json, затем 'stop'.
    Значение 'max_tokens' нормализуется в 'length'. Невалидный непустой env
    не переопределяет конфиг.
    """
    raw_env = os.getenv("AGY_GRACEFUL_TIMEOUT_FINISH_REASON")
    if raw_env is not None and raw_env.strip():
        s = raw_env.strip().lower()
        if s in ("length", "max_tokens"):
            return "length"
        if s == "stop":
            return "stop"
    snap = _runtime_snapshot()
    val = snap.graceful_timeout_finish_reason.strip().lower()
    if val in ("length", "max_tokens"):
        return "length"
    return "stop"


AGY_BRIDGE_STREAM_RESILIENCE_ENABLED = _new_flag(
    "AGY_BRIDGE_STREAM_RESILIENCE_ENABLED", True
)


def _positive_env(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if not value > 0.0 or value != value or value == float("inf"):
        return None
    return value


def _extended_timeouts() -> tuple[float, float]:
    """(idle, max) настроенные таймауты: env AGY_IDLE_TIMEOUT_S/AGY_TIMEOUT_S, иначе 1800/3600."""
    idle = (
        _positive_env("AGY_IDLE_TIMEOUT_S")
        or _positive_env("AGY_BRIDGE_IDLE_TIMEOUT")
        or EXT_IDLE_TIMEOUT_S
    )
    cap = _positive_env("AGY_TIMEOUT_S") or EXT_MAX_TIMEOUT_S
    return min(idle, cap), cap


@final
class _TimeoutPolicy:
    """Политика одной попытки при extended_timeout_enabled (AD-003)."""

    def __init__(
        self,
        t_req_start: float,
        idle_timeout_s: float,
        max_timeout_s: float,
        effective_max_timeout_s: float,
        can_start: bool = True,
    ) -> None:
        self.t_req_start = t_req_start
        self.idle_timeout_s = idle_timeout_s
        self.max_timeout_s = max_timeout_s
        self.effective_max_timeout_s = effective_max_timeout_s
        self.can_start = can_start


def _build_timeout_policy(t_req_start: float) -> _TimeoutPolicy | None:
    """Политика попытки; None — extended выключен (прежние TIMEOUT_S/IDLE_TIMEOUT_S).

    Бюджет запроса T_REQ_BUDGET_S считается от t_req_start (до admission) и не
    перезапускается на retry; на drain и финальный flush резервируется T_RESERVE_S.
    """
    if not _new_flag("extended_timeout_enabled"):
        return None
    idle, cap = _extended_timeouts()
    usable = t_req_start + T_REQ_BUDGET_S - time.monotonic() - T_RESERVE_S
    can_start = usable >= T_MIN_ATTEMPT_S
    return _TimeoutPolicy(
        t_req_start=t_req_start,
        idle_timeout_s=idle,
        max_timeout_s=cap,
        effective_max_timeout_s=min(cap, usable) if can_start else 0.0,
        can_start=can_start,
    )


def _breaker_blocks_now() -> bool:
    """Быстрая проверка без побочных эффектов: breaker OPEN и cooldown не истёк."""
    with _sqlite_guard_lock:
        return (
            _breaker_state == "OPEN"
            and time.monotonic() - _breaker_opened_at < BREAKER_COOLDOWN_S
        )


def _breaker_acquire() -> tuple[bool, int | None]:
    """Допуск хода к SQLite: (разрешено, probe_gen пробного хода или None)."""
    global _breaker_state, _breaker_probe_gen, _breaker_active_probe_gen
    global _breaker_probe_started_at
    now = time.monotonic()
    with _sqlite_guard_lock:
        if _breaker_state == "CLOSED":
            return True, None
        if _breaker_state == "OPEN":
            if now - _breaker_opened_at < BREAKER_COOLDOWN_S:
                return False, None
            _breaker_state = "HALF_OPEN"
            _breaker_active_probe_gen = None
        leased = (
            _breaker_active_probe_gen is not None
            and now - _breaker_probe_started_at < BREAKER_PROBE_LEASE_S
        )
        if leased:
            return False, None
        _breaker_probe_gen += 1
        _breaker_active_probe_gen = _breaker_probe_gen
        _breaker_probe_started_at = now
        return True, _breaker_probe_gen


def _breaker_permits(probe_gen: int | None) -> bool:
    """Можно ли выполнять SELECT: CLOSED-ход — пока CLOSED, пробный — пока его поколение актуально."""
    with _sqlite_guard_lock:
        if probe_gen is None:
            return _breaker_state == "CLOSED"
        return _breaker_state == "HALF_OPEN" and _breaker_active_probe_gen == probe_gen


def _breaker_report(probe_gen: int | None, selects_ok: int, failed: bool) -> None:
    """Исход хода для FSM breaker'а; устаревшая проба (другое поколение) — no-op."""
    global _breaker_state, _breaker_failures, _breaker_opened_at
    global _breaker_active_probe_gen
    now = time.monotonic()
    change = ""
    with _sqlite_guard_lock:
        if probe_gen is not None:
            if _breaker_active_probe_gen != probe_gen or _breaker_state != "HALF_OPEN":
                return
            _breaker_active_probe_gen = None
            if failed:
                _breaker_state = "OPEN"
                _breaker_opened_at = now
                change = "OPEN"
            elif selects_ok >= 1:
                _breaker_state = "CLOSED"
                _breaker_failures = 0
                change = "CLOSED"
            current_state = _breaker_state
            gen_now = probe_gen
        else:
            if _breaker_state != "CLOSED":
                return
            if failed:
                _breaker_failures += 1
                if _breaker_failures >= BREAKER_FAILURES_TO_OPEN:
                    _breaker_state = "OPEN"
                    _breaker_opened_at = now
                    change = "OPEN"
            elif selects_ok >= 1:
                _breaker_failures = 0
            current_state = _breaker_state
            gen_now = _breaker_probe_gen
    if change:
        _log(f"breaker state={current_state} probe_gen={gen_now}")


def _retry_credit() -> None:
    """Первичный запрос пополняет бюджет повторов (+0.2 токена, не выше ёмкости)."""
    global _retry_tenths
    with _sqlite_guard_lock:
        _retry_tenths = min(RETRY_CAPACITY_TENTHS, _retry_tenths + RETRY_CREDIT_TENTHS)


def _retry_take() -> bool:
    """Списать один повтор (1.0 токена); False — бюджет исчерпан."""
    global _retry_tenths
    with _sqlite_guard_lock:
        if _retry_tenths < RETRY_COST_TENTHS:
            return False
        _retry_tenths -= RETRY_COST_TENTHS
        return True


def _retry_pause_s(attempt: int, rng: Callable[[], float] | None = None) -> float:
    """Full Jitter: U(0, min(2.0, 2.0 * 2^(attempt-1))) через инъецируемый RNG."""
    cap = min(RETRY_PAUSE_CAP_S, RETRY_PAUSE_CAP_S * float(1 << max(0, attempt - 1)))
    source = rng if rng is not None else _rng
    return source() * cap


@final
class _PollBucket:
    """Token bucket опроса SQLite одного хода в целых десятых токена.

    Ёмкость 3.0, пополнение 2.0 токена/с, SELECT стоит 1.0: на любом окне Δt
    приходит не более 3 + 2·Δt запросов. Время ведётся целыми микросекундами.
    """

    def __init__(self) -> None:
        self.tenths: int = POLL_BUCKET_CAPACITY_TENTHS
        self.last_us: int = int(time.monotonic() * 1_000_000)

    def take(self) -> bool:
        now_us = int(time.monotonic() * 1_000_000)
        elapsed = now_us - self.last_us
        if elapsed > 0:
            add = elapsed * POLL_BUCKET_REFILL_TENTHS_PER_S // 1_000_000
            if add > 0:
                if self.tenths + add >= POLL_BUCKET_CAPACITY_TENTHS:
                    self.tenths = POLL_BUCKET_CAPACITY_TENTHS
                    self.last_us = now_us
                else:
                    self.tenths += add
                    self.last_us += add * 1_000_000 // POLL_BUCKET_REFILL_TENTHS_PER_S
        if self.tenths >= POLL_BUCKET_COST_TENTHS:
            self.tenths -= POLL_BUCKET_COST_TENTHS
            return True
        return False


def _agy_binary_identity() -> tuple[int, int] | None:
    """Идентичность бинаря agy (st_mtime_ns, st_size); None — stat не удался."""
    try:
        info = os.stat(AGY_BIN)
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


def _compat_turn_state(identity: tuple[int, int] | None) -> str:
    """Режим хода из процессного canary: новый или неизвестный бинарь -> SHADOW."""
    global _compat_ident, _compat_state
    changed = False
    with _sqlite_guard_lock:
        if identity is None or identity != _compat_ident:
            changed = _compat_state != "SHADOW" or _compat_ident is not None
            _compat_ident = identity
            _compat_state = "SHADOW"
        state = _compat_state
    if changed:
        _log("compat state=SHADOW reason=binary_identity")
    return state


def _compat_promote(turn_identity: tuple[int, int] | None) -> bool:
    """SHADOW -> LIVE для будущих ходов: бинарь хода совпал с текущим на диске."""
    global _compat_ident, _compat_state
    with _sqlite_guard_lock:
        current = _agy_binary_identity()
        if turn_identity is None or turn_identity != current:
            return False
        _compat_ident = turn_identity
        _compat_state = "LIVE"
    return True


def _compat_demote() -> None:
    """Любая расходимость в LIVE возвращает следующие ходы в SHADOW."""
    global _compat_state
    with _sqlite_guard_lock:
        was_live = _compat_state == "LIVE"
        _compat_state = "SHADOW"
    if was_live:
        _log("compat state=SHADOW reason=divergence")


def _count_divergence() -> None:
    global _sqlite_divergence_count
    with _sqlite_guard_lock:
        _sqlite_divergence_count += 1


def _count_drain_deadline() -> None:
    global _sqlite_drain_deadline_count
    with _sqlite_guard_lock:
        _sqlite_drain_deadline_count += 1


def _sqlite_health_fields() -> dict[str, object]:
    """Аддитивные диагностические поля /health (без SQLite-вызовов и секретов)."""
    disabled = _sqlite_disabled_reason()
    with _sqlite_guard_lock:
        if disabled:
            mode = "off"
        elif _breaker_state == "OPEN":
            mode = "breaker_open"
        else:
            mode = _compat_state.lower()
        return {
            "sqlite_reasoning_mode": mode,
            "sqlite_breaker_state": _breaker_state.lower(),
            "sqlite_divergence_count": _sqlite_divergence_count,
            "sqlite_drain_deadline_count": _sqlite_drain_deadline_count,
        }


def _cid_acquire(cid: str, turn_id: str) -> bool:
    """Занять разговор за ходом; False — cid занят другим активным ходом."""
    if not cid or not turn_id:
        return True
    with _session_store_lock:
        owner = _active_cid_owners.get(cid)
        if owner is not None and owner != turn_id:
            return False
        _active_cid_owners[cid] = turn_id
        return True


def _cid_release(cid: str, turn_id: str) -> None:
    """Снять владение, только если оно принадлежит этому ходу."""
    if not cid or not turn_id:
        return
    with _session_store_lock:
        if _active_cid_owners.get(cid) == turn_id:
            _ = _active_cid_owners.pop(cid, None)


# ---- Чтение SQLite разговора agy: только на чтение, без побочных эффектов --------


def _db_path_for(cid: str) -> Path | None:
    """Путь к <cid>.db строго внутри CONV_DIR; невалидный cid -> None."""
    if _CID_RE.fullmatch(cid) is None:
        return None
    path = CONV_DIR / (cid + ".db")
    try:
        if path.resolve().parent != CONV_DIR.resolve():
            return None
    except (OSError, RuntimeError):
        return None
    return path


_WAL_CHECKPOINT_LOCK = threading.Lock()
_last_wal_checkpoint_ts = 0.0


def _maybe_checkpoint_sqlite_wal(
    conv_dir: Path | None = None, max_wal_bytes: int | None = None
) -> int:
    """Best-effort WAL maintenance; busy databases never delay admission for long."""
    global _last_wal_checkpoint_ts
    if not _WAL_CHECKPOINT_LOCK.acquire(blocking=False):
        return 0
    try:
        now = time.monotonic()
        if now - _last_wal_checkpoint_ts < 30.0:
            return 0
        _last_wal_checkpoint_ts = now
        directory = CONV_DIR if conv_dir is None else conv_dir
        limit = _config.wal_max_bytes if max_wal_bytes is None else max_wal_bytes
        checkpointed = 0
        attempted = 0
        try:
            paths = list(directory.glob("*.db-wal"))
        except OSError:
            return 0
        for wal in paths:
            if attempted >= 2:
                break
            conn = None
            try:
                if wal.stat().st_size <= limit:
                    continue
                database = wal.with_name(wal.name[:-4])
                if not database.is_file():
                    continue
                attempted += 1
                conn = sqlite3.connect(str(database), timeout=0.05)
                conn.execute("PRAGMA busy_timeout = 50")
                result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                if result is not None and result[0] == 0:
                    checkpointed += 1
            except (sqlite3.Error, OSError):
                pass
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except sqlite3.Error:
                        pass
        return checkpointed
    finally:
        _WAL_CHECKPOINT_LOCK.release()


def _sqlite_ro_uri(path: Path) -> str:
    text = str(path).replace("%", "%25").replace("?", "%3f").replace("#", "%23")
    return f"file:{text}?mode=ro"


def _sqlite_open_ro(path: Path) -> sqlite3.Connection:
    """Открыть БД только на чтение; каждый connect обязан закрываться _sqlite_close."""
    global _sqlite_open_connections, _sqlite_max_open_connections

    def connect(uri: str) -> sqlite3.Connection:
        conn = sqlite3.connect(
            uri,
            uri=True,
            timeout=0.05,
            isolation_level=None,
            check_same_thread=False,
        )
        try:
            _ = conn.execute("PRAGMA query_only = ON")
            _ = conn.execute("PRAGMA busy_timeout = 50")
            _ = conn.execute("PRAGMA cache_size = -1024")
        except BaseException:
            conn.close()
            raise
        return conn

    uri = _sqlite_ro_uri(path)
    try:
        conn = connect(uri)
    except sqlite3.OperationalError as exc:
        # В Python 3.9 нет sqlite_errorcode; immutable не должен обходить блокировки.
        if str(exc).startswith(("database is locked", "database table is locked")):
            raise
        if (
            path.with_name(path.name + "-wal").exists()
            or path.with_name(path.name + "-shm").exists()
        ):
            raise
        conn = connect(uri + "&immutable=1")
    with _sqlite_guard_lock:
        _sqlite_open_connections += 1
        _sqlite_max_open_connections = max(
            _sqlite_max_open_connections, _sqlite_open_connections
        )
    return conn


def _sqlite_close(conn: sqlite3.Connection) -> None:
    global _sqlite_open_connections
    try:
        conn.close()
    except sqlite3.Error:
        pass
    with _sqlite_guard_lock:
        _sqlite_open_connections = max(0, _sqlite_open_connections - 1)


def _sqlite_max_idx(db_path: Path) -> int | None:
    """Наибольший idx шага в БД (или -1); None — прочитать не удалось."""
    conn: sqlite3.Connection | None = None
    try:
        conn = _sqlite_open_ro(db_path)
        row = cast(
            "tuple[object, ...]",
            conn.execute("SELECT COALESCE(MAX(idx), -1) FROM steps").fetchone(),
        )
        value = row[0]
        return value if isinstance(value, int) else None
    except sqlite3.Error:
        return None
    finally:
        if conn is not None:
            _sqlite_close(conn)


def _transcript_path(cid: str) -> Path:
    return BRAIN_DIR / cid / ".system_generated" / "logs" / TRANSCRIPT_NAME


def _select_transcript_path(cid: str) -> Path | None:
    """Существующий файл транскрипта: `transcript_full.jsonl`, при ENOENT — `transcript.jsonl`.

    None — ни одного файла (свежий разговор до первого шага) или ошибка stat.
    """
    base = _transcript_path(cid).parent
    for name in (TRANSCRIPT_NAME, TRANSCRIPT_FALLBACK_NAME):
        path = base / name
        try:
            _ = path.stat()
        except FileNotFoundError:
            continue
        except OSError:
            return None
        return path
    return None


def _transcript_anchor(cid: str, path: Path | None = None) -> tuple[int, int] | None:
    """(наибольший step_index, размер файла) транскрипта до старта хода.

    Нет файла — (-1, 0); ошибка чтения — None.
    """
    path = path if path is not None else _transcript_path(cid)
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return (-1, 0)
    except OSError:
        return None
    try:
        with open(path, "rb") as fh:
            _ = fh.seek(max(0, size - TRANSCRIPT_READ_MAX))
            data = fh.read(TRANSCRIPT_READ_MAX)
    except OSError:
        return None
    t_max = -1
    for match in _STEP_INDEX_RE.finditer(data):
        t_max = max(t_max, int(match.group(1)))
    return (t_max, size)


@final
class _TurnPlan:
    """Решения по источнику мышления хода: якорь resume и режим LIVE|SHADOW|OFF."""

    def __init__(self) -> None:
        self.mode: str = "OFF"
        self.reason: str = ""
        self.base_idx: int = 0
        self.offset: int = 0
        self.anchored: bool = True
        self.probe_gen: int | None = None
        self.identity: tuple[int, int] | None = None
        # Файл транскрипта, закреплённый на попытку (только step_scoped_usage_enabled).
        self.transcript_path: Path | None = None


def _prespawn_plan(cid: str, resumed: bool, usage_enabled: bool = False) -> _TurnPlan:
    """Якорь хода ДО spawn: байтовый водяной знак транскрипта и максимум idx в БД.

    Свежий разговор: base_idx=0. Продолжение треда (resume): оба водяных знака
    обязательны, иначе SQLite-опрос на весь ход выключается (resume_unanchored),
    а мышление идёт из транскрипта с pre-spawn смещением.
    """
    plan = _TurnPlan()
    if not resumed:
        return plan
    plan.anchored = False
    if _CID_RE.fullmatch(cid) is None:
        plan.reason = "cid"
        plan.offset = -1
        return plan
    if usage_enabled:
        # Выбранный файл (full, иначе transcript.jsonl) и его водяной знак — на попытку.
        plan.transcript_path = _select_transcript_path(cid)
    anchor = _transcript_anchor(cid, plan.transcript_path)
    if anchor is None:
        plan.reason = "resume_unanchored"
        plan.offset = -1
        return plan
    t_max, plan.offset = anchor
    plan.base_idx = t_max + 1
    if not _is_sqlite_reasoning_enabled():
        plan.reason = _sqlite_disabled_reason() or "flag"
        return plan
    if _breaker_blocks_now():
        plan.reason = "breaker"
        return plan
    db_path = _db_path_for(cid)
    db_max = _sqlite_max_idx(db_path) if db_path is not None else None
    if db_max is None:
        plan.reason = "resume_unanchored"
        return plan
    plan.anchored = True
    plan.base_idx = max(t_max, db_max) + 1
    return plan


def _decide_turn_mode(plan: _TurnPlan) -> None:
    """Режим хода фиксируется один раз: флаг, якорь, breaker, compat-canary."""
    disabled = _sqlite_disabled_reason()
    if disabled:
        plan.mode, plan.reason = "OFF", plan.reason or disabled
        return
    if not plan.anchored:
        plan.mode, plan.reason = "OFF", plan.reason or "resume_unanchored"
        return
    allowed, probe_gen = _breaker_acquire()
    if not allowed:
        plan.mode, plan.reason = "OFF", "breaker"
        return
    plan.probe_gen = probe_gen
    plan.identity = _agy_binary_identity()
    plan.mode = _compat_turn_state(plan.identity)
    plan.reason = ""


# ---- Разбор protobuf-wire формата step_payload (чистый Python, stdlib) -------------


def _read_varint(buf: bytes, pos: int, end: int) -> tuple[int, int]:
    """(значение, новая позиция); (-1, pos) — обрыв или варинт длиннее 10 байт."""
    value = 0
    shift = 0
    cur = pos
    while cur < end and shift < 70:
        byte = buf[cur]
        cur += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, cur
        shift += 7
    return -1, pos


def _wire_find(
    buf: bytes, start: int, end: int, field_no: int, stop: threading.Event | None
) -> list[tuple[int, int]] | None:
    """Границы length-delimited вхождений поля field_no в [start, end).

    None — разбор невозможен (неподдерживаемый wire type, выход за границу, stop).
    Каждые 64 тега проверяется stop: частичный результат не выдаётся.
    """
    found: list[tuple[int, int]] = []
    pos = start
    tags = 0
    while pos < end:
        tags += 1
        if tags % 64 == 0 and stop is not None and stop.is_set():
            return None
        tag, pos = _read_varint(buf, pos, end)
        if tag < 0:
            return None
        wire = tag & 7
        number = tag >> 3
        if wire == 0:
            value, pos = _read_varint(buf, pos, end)
            if value < 0:
                return None
        elif wire == 1:
            pos += 8
        elif wire == 5:
            pos += 4
        elif wire == 2:
            length, pos = _read_varint(buf, pos, end)
            if length < 0 or pos + length > end:
                return None
            if number == field_no:
                found.append((pos, pos + length))
            pos += length
        else:
            return None
        if pos > end:
            return None
    return found


def _trim_incomplete_utf8(data: bytes) -> bytes:
    """Отбросить неполный многобайтовый символ в конце снимка status=8."""
    size = len(data)
    for back in range(1, min(4, size) + 1):
        byte = data[size - back]
        if 0x80 <= byte <= 0xBF:
            continue
        if 0xC0 <= byte <= 0xF4:
            need = 2 if byte < 0xE0 else (3 if byte < 0xF0 else 4)
            if back < need:
                return data[: size - back]
        break
    return data


def _extract_thinking_from_step_blob(
    raw: bytes | None, final: bool, stop: threading.Event | None = None
) -> str:
    """Мышление шага из step_payload: корневое поле 20 -> подполе 3 (UTF-8).

    '' означает «мышления нет». Функция чистая: без I/O, логов и исключений
    наружу; битый или усечённый payload даёт ''. Для нефинального снимка
    (status=8) неполный UTF-8 хвост отбрасывается и придёт целым со следующим.
    """
    if not raw:
        return ""
    try:
        data = bytes(raw)
        roots = _wire_find(data, 0, len(data), 20, stop)
        if not roots:
            return ""
        chosen: tuple[int, int] | None = None
        for begin, finish in roots:
            subs = _wire_find(data, begin, finish, 3, stop)
            if subs is None:
                return ""
            if subs:
                chosen = subs[-1]
        if chosen is None:
            return ""
        text = data[chosen[0] : chosen[1]]
        if not final:
            text = _trim_incomplete_utf8(text)
        return text.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


# [Refactored] _StepState, _ContentArbiter, _ToolProgress moved to agy_runtime/


# ---- Step-scoped usage (step_scoped_usage_enabled): счётчики шагов хода из транскрипта --
# Потолок числа различных step_index на попытку (N_entities_max): один словарь служит и
# дедупликацией, и ledger; отдельный потолок мышления MAX_STEPS_TRACKED=128 не затронут.
USAGE_STEP_CAP = get_bridge_config().usage_step_cap


def _count_or_none(value: object) -> int | None:
    """Счётное значение токенов: int >= 0; bool, строки, float и отрицательные — не число."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


@dataclass(frozen=True)
class _UsageSnapshot:
    """Неизменяемый снимок счётчиков хода; публикуется читателем транскрипта целиком.

    `last_step_usage` — `(step_index, input, cache_read | None, output)` валидного
    `PLANNER_RESPONSE` с наибольшим индексом. `completeness` истинна, только когда
    наблюдался хотя бы один шаг, ledger не насыщен и ни одна запись хода не имела
    отсутствующих/невалидных счётчиков: иначе сумма output не точна.
    """

    last_step_usage: tuple[int, int, int | None, int] | None = None
    turn_output_tokens_sum: int = 0
    observed_planner_steps: int = 0
    observed_planner_steps_saturated: bool = False
    completeness: bool = False
    invalid_records_count: int = 0


_EMPTY_USAGE_SNAPSHOT = _UsageSnapshot()


def _add_preamble_bounded(target: set[int], item: int, cap: int | None = None) -> None:
    """Добавить индекс шага в коллекцию эмитированных преамбул с ограничением MAX_CONTENT_STEPS * 2."""
    eff_cap = max(1, MAX_CONTENT_STEPS * 2) if cap is None else cap
    target.add(item)
    if len(target) > eff_cap:
        try:
            oldest = min(tuple(target))
            target.discard(oldest)
        except (ValueError, RuntimeError):
            pass


@final
class _TranscriptTail(InterruptionTailState):
    """Источник мышления шагов agy: транскрипт разговора и SQLite `conversations/<cid>.db`.

    Один daemon-поток на ход — единственный писатель состояния шагов (без замков).
    Транскрипт `<BRAIN_DIR>/<cid>/.system_generated/logs/transcript_full.jsonl`
    читается инкрементально по байтовому смещению: запись `PLANNER_RESPONSE`
    появляется после завершения шага. Параллельно, пока шаг ещё генерируется
    (`status=8`), подполе 20.3 его `step_payload` в SQLite растёт — оттуда мышление
    уходит клиенту дельтами. База открывается строго на чтение, на каждый опрос
    своё соединение, закрываемое в `finally`.

    Режим хода `LIVE|SHADOW|OFF` фиксируется на старте: в SHADOW SQLite только
    наблюдается (canary совместимости agy), клиенту выдаёт транскрипт. Дедупликация
    по `idx == step_index` с проверкой префикса sha256: непрефиксный снимок
    замораживает выдачу шага на уже отданном префиксе.

    Поток вспомогательный и не может влиять на ответ: нет каталога, нет файла,
    битая строка, ошибка SQLite — просто «мышления нет».
    """

    def __init__(
        self,
        emit: Callable[[int, str, Callable[[], None] | None], bool],
        stop_event: threading.Event,
        done_event: threading.Event,
        resumed: bool,
        plan: _TurnPlan | None = None,
        turn_id: str = "",
        emit_content: Callable[[int | None, str], bool] | None = None,
        on_activity: Callable[[], None] | None = None,
        usage_enabled: bool = False,
        isolate_tool_preambles: bool = False,
        preambles_emitted: set[int] | None = None,
        run_ref: Any = None,
    ) -> None:
        self.emit = emit
        self.run_ref: Any = run_ref
        # PLANNER_RESPONSE.content -> арбитр (AD-001); None — прежнее поведение.
        self.emit_content = emit_content
        self.isolate_tool_preambles = isolate_tool_preambles
        # Реальный прогресс транскрипта/SQLite текущего хода -> producer activity (AD-003).
        self.on_activity = on_activity
        # Дедлайн потока: синхронизируется с effective_max_timeout_s политики (AD-003).
        self.deadline_s: float = TIMEOUT_S + 60.0
        self._in_rewrite: bool = False
        self.stop_event = stop_event
        self.done_event = done_event
        self.resumed = resumed
        self.plan: _TurnPlan = plan if plan is not None else _TurnPlan()
        self.turn_id: str = turn_id
        self.mode: str = self.plan.mode
        self.base_idx: int = self.plan.base_idx
        self.probe_gen: int | None = self.plan.probe_gen
        self.cid: str = ""
        self.seen: dict[int, _StepState] = {}
        self.poll_watermark: int = self.plan.base_idx
        self.sqlite_active: bool = self.plan.mode in ("LIVE", "SHADOW")
        self.bucket: _PollBucket = _PollBucket()
        self.selects_ok: int = 0
        self.failed: bool = False
        self.emitted: int = 0
        self.dead: bool = False
        self.end_marker: bool = False
        self.final_planner: bool = False
        self.drain_deadline: float = 0.0
        self.drain_outcome: str = ""
        self.last_poll: str = ""
        self._ready = threading.Event()
        self._offset: int = self.plan.offset
        self._buf: bytes = b""
        self._transcript_ok: bool = True
        self._owned_cid: str = ""
        self._next_poll_at: float = 0.0
        self._preambles_emitted: set[int] = (
            preambles_emitted if preambles_emitted is not None else set()
        )
        self._tool_step_indices: set[int] = set()
        self._interrupted: bool = False
        self._active_conn: sqlite3.Connection | None = None
        self._conn_lock = threading.Lock()
        self._db_path: Path | None = None
        self._open_fail_logged: bool = False
        self._oversize_logged: set[int] = set()
        self._finished: bool = False
        # Закреплённый на попытку файл транскрипта (только при usage_enabled).
        self._path: Path | None = self.plan.transcript_path
        # Счётчики шагов хода: единственный писатель — поток tail; наружу — снимок.
        self.usage_enabled: bool = usage_enabled
        self.step_records_by_index: (
            dict[int, tuple[int, int | None, int] | None] | None
        ) = {} if usage_enabled else None
        self.last_valid_step_index: int | None = None
        self.last_step_usage: tuple[int, int, int | None, int] | None = None
        self.observed_planner_steps_saturated: bool = False
        self._usage_out_sum: int = 0
        self._usage_invalid: int = 0
        self._usage_dirty: bool = False
        self._usage_lock = threading.Lock()
        self._usage_snapshot: _UsageSnapshot = _EMPTY_USAGE_SNAPSHOT
        self.thread = threading.Thread(target=self._run, daemon=True)

    # ---- жизненный цикл ----------------------------------------------------------
    def start(self) -> None:
        self.thread.start()

    def _cid8(self) -> str:
        return self.cid[:8] or "-"

    def bind(self, cid: str) -> None:
        """Привязать источник к разговору из события `init` потока agy."""
        if not cid or self.cid:
            return
        self.cid = cid
        if _CID_RE.fullmatch(cid) is None:
            self._transcript_ok = False
            self._sqlite_off("cid")
        else:
            if self.sqlite_active:
                if _cid_acquire(cid, self.turn_id):
                    self._owned_cid = cid
                else:
                    self._sqlite_off("cid_busy")
            self._db_path = _db_path_for(cid)
            if self._db_path is None:
                self._sqlite_off("cid")
            if self.resumed and self._offset < 0:
                try:
                    pinned = self._transcript_file() if self.usage_enabled else None
                    path = pinned if pinned is not None else _transcript_path(cid)
                    self._offset = path.stat().st_size
                except OSError:
                    self._offset = 0
        _log(
            f"turn_mode cid={self._cid8()} mode={self.mode if self.sqlite_active else 'OFF'}"
        )
        if self.plan.mode == "OFF" and self.plan.reason:
            _log(f"sqlite-off cid={self._cid8()} reason={self.plan.reason}")
        self._ready.set()

    def interrupt_active_query(self) -> None:
        """Прервать активный SELECT из другого потока; ошибки закрытого соединения гасятся."""
        with self._conn_lock:
            conn = self._active_conn
            if conn is not None:
                self._interrupted = True
                try:
                    conn.interrupt()
                except (sqlite3.ProgrammingError, sqlite3.OperationalError):
                    pass

    def _run(self) -> None:
        try:
            self._run_loop()
        except Exception as exc:
            _log(f"tail-error cid={self._cid8()} err={type(exc).__name__}")
        finally:
            self._finish()

    def _run_loop(self) -> None:
        # Файл и БД появляются только после первого шага — ждём привязки к разговору,
        # но не дольше, чем ждали бы первого события agy; выход процесса или stop
        # прерывают ожидание сразу (поток не висит до FIRST_TOKEN_TIMEOUT_S).
        waited = 0.0
        while not self._ready.wait(timeout=0.05):
            waited += 0.05
            if self.stop_event.is_set() or self.done_event.is_set():
                return
            if waited >= FIRST_TOKEN_TIMEOUT_S:
                _log(
                    f"tail-timeout cid={self._cid8()}: no bind within {FIRST_TOKEN_TIMEOUT_S:g}s"
                )
                return
        started = time.monotonic()
        while time.monotonic() - started < self.deadline_s:
            if self.stop_event.is_set():
                return
            if self.done_event.is_set():
                self._drain_post_eof()
                return
            self.tick()
            _ = self.done_event.wait(TRANSCRIPT_POLL_S)

    def _finish(self) -> None:
        """Закрыть соединение, вернуть исход breaker'у и снять владение cid (один раз)."""
        if self._finished:
            return
        self._finished = True
        with self._conn_lock:
            conn = self._active_conn
            self._active_conn = None
            if conn is not None:
                _sqlite_close(conn)
        if self.plan.mode in ("LIVE", "SHADOW"):
            _breaker_report(self.probe_gen, self.selects_ok, self.failed)
        if self._owned_cid:
            _cid_release(self._owned_cid, self.turn_id)

    # ---- один проход ---------------------------------------------------------------
    def tick(self) -> None:
        """Транскрипт каждый тик; SQLite — не чаще SQLITE_POLL_S (и по токенам bucket)."""
        self._read_transcript()
        if self.dead:
            return
        _ = self._sqlite_permitted()
        now = time.monotonic()
        if self.sqlite_active and now >= self._next_poll_at:
            self._next_poll_at = now + SQLITE_POLL_S
            _ = self._poll_sqlite()

    def _sqlite_off(self, reason: str) -> None:
        """Выключить SQLite-опрос до конца хода; транскрипт продолжает работу."""
        if not self.sqlite_active:
            return
        self.sqlite_active = False
        self.interrupt_active_query()
        _log(f"sqlite-off cid={self._cid8()} reason={reason}")

    def _sqlite_permitted(self) -> bool:
        """Флаг, breaker и режим хода на каждую итерацию и перед каждой строкой."""
        if not self.sqlite_active or self.dead:
            return False
        disabled = _sqlite_disabled_reason()
        if disabled:
            self._sqlite_off(disabled)
            return False
        if not _breaker_permits(self.probe_gen):
            self._sqlite_off("breaker" if self.probe_gen is None else "probe_stale")
            return False
        return True

    def _note_activity(self) -> None:
        callback = self.on_activity
        if callback is not None:
            try:
                callback()
            except Exception:
                pass

    # ---- транскрипт ----------------------------------------------------------------
    def _read_transcript(self) -> None:
        """Дочитать файл с offset; неполный хвост строки ждёт следующего прохода."""
        if not self.cid or not self._transcript_ok:
            return
        path = self._transcript_file()
        if path is None:
            return
        try:
            size = path.stat().st_size
        except OSError:
            return
        rewritten = False
        if size < self._offset:  # файл переписан с нуля — читаем заново
            _log(
                f"tail-rewrite cid={self._cid8()}: size {size} < offset {self._offset}"
            )
            self._offset, self._buf = 0, b""
            rewritten = True
        if size == self._offset:
            return
        try:
            with open(path, "rb") as fh:
                _ = fh.seek(self._offset)
                chunk = fh.read(TRANSCRIPT_READ_MAX)
        except OSError:
            return
        self._buf += chunk
        # Рост файла хода — активность producer (и неполная строка). При перезаписи
        # перечитывается старая история: активностью считаются только записи хода.
        self._in_rewrite = rewritten
        if chunk and not rewritten:
            self._note_activity()
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            self._offset += len(line) + 1
            try:
                self._emit_record(line)
            except Exception:
                pass
        if self._usage_dirty:
            self._publish_usage()

    def _transcript_file(self) -> Path | None:
        """Файл транскрипта: прежний путь; при usage_enabled — закреплённый на попытку.

        Приоритет `transcript_full.jsonl`, при ENOENT — `transcript.jsonl`; пока ни
        одного файла нет, проверка повторяется, а найденный путь не меняется до конца
        попытки (появившийся позже full не подменяет смещение другого файла).
        """
        if not self.usage_enabled:
            return _transcript_path(self.cid)
        if self._path is None:
            self._path = _select_transcript_path(self.cid)
        return self._path

    # ---- счётчики usage ------------------------------------------------------------
    def _record_usage(self, rec: dict[str, object]) -> None:
        """Учесть счётчики `PLANNER_RESPONSE` текущего хода за O(1) без хранения текста."""
        records = self.step_records_by_index
        if records is None:
            return
        self._usage_dirty = True
        idx = rec.get("step_index")
        if (
            not isinstance(idx, int)
            or isinstance(idx, bool)
            or idx < 0
            or idx < self.base_idx
        ):
            self._usage_invalid += 1  # шаг без пригодного индекса не атрибутируется
            return
        inp = _count_or_none(rec.get("input_tokens"))
        out = _count_or_none(rec.get("output_tokens"))
        cache_raw = rec.get("cache_read_tokens")
        cache = _count_or_none(cache_raw)
        counts: tuple[int, int | None, int] | None = None
        if (
            inp is not None
            and out is not None
            and (cache_raw is None or cache is not None)
        ):
            counts = (inp, cache, out)
        if idx in records:
            if counts is not None:
                old = records[idx]
                self._usage_out_sum += counts[2] - (old[2] if old is not None else 0)
                records[idx] = counts
        elif len(records) < USAGE_STEP_CAP:
            records[idx] = counts
            if counts is not None:
                self._usage_out_sum += counts[2]
        else:
            # Насыщение: ключ не вставляется, сумма output считается неполной.
            self.observed_planner_steps_saturated = True
        if counts is None:
            self._usage_invalid += 1
            return
        last = self.last_valid_step_index
        if last is None or idx >= last:
            self.last_valid_step_index = idx
            self.last_step_usage = (idx, counts[0], counts[1], counts[2])

    def _publish_usage(self) -> None:
        """Опубликовать неизменяемый снимок под коротким замком (без I/O под замком)."""
        records = self.step_records_by_index
        if records is None:
            return
        observed = len(records)
        snap = _UsageSnapshot(
            last_step_usage=self.last_step_usage,
            turn_output_tokens_sum=self._usage_out_sum,
            observed_planner_steps=observed,
            observed_planner_steps_saturated=self.observed_planner_steps_saturated,
            completeness=(
                observed > 0
                and not self.observed_planner_steps_saturated
                and self._usage_invalid == 0
            ),
            invalid_records_count=self._usage_invalid,
        )
        self._usage_dirty = False
        with self._usage_lock:
            self._usage_snapshot = snap

    def usage_snapshot(self) -> _UsageSnapshot:
        with self._usage_lock:
            return self._usage_snapshot

    def _emit_record(self, raw: bytes) -> None:
        line = raw.strip()
        if not line:
            return
        if not _TAIL_MARKER_RE.search(line):
            return  # быстрый отсев служебных записей без разбора JSON
        try:
            parsed = cast(object, json.loads(line.decode("utf-8", "replace")))
        except ValueError:
            return
        if not isinstance(parsed, dict):
            return
        rec = cast("dict[str, object]", parsed)
        rtype = str(rec.get("type") or "")
        idx = _as_int(rec.get("step_index"))
        if idx is not None and idx < self.base_idx:
            return  # история прошлых ходов
        if self._in_rewrite:
            self._note_activity()
        if rtype in ("END_TURN", "TURN_COMPLETE"):
            self.end_marker = True
            return
        if rtype != "PLANNER_RESPONSE":
            self.note_error_record(rtype, rec, idx)
            return
        if self.usage_enabled:
            self._record_usage(rec)
        content = rec.get("content")
        emit_content = self.emit_content
        has_tools = bool(rec.get("tool_calls"))
        if has_tools and idx is not None:
            tool_steps = getattr(self, "_tool_step_indices", None)
            if tool_steps is None:
                tool_steps = self._tool_step_indices = set()
            tool_steps.add(idx)
        isolate_tools = getattr(self, "isolate_tool_preambles", False)
        if emit_content is not None and isinstance(content, str) and content.strip():
            if has_tools and isolate_tools:
                run_ref = getattr(self, "run_ref", None)
                claimed = False
                if run_ref is not None and hasattr(run_ref, "claim_preamble"):
                    claimed = run_ref.claim_preamble(idx, source="transcript")
                else:
                    preambles = getattr(self, "_preambles_emitted", None)
                    if preambles is None:
                        preambles = self._preambles_emitted = set()
                    key_idx = idx if idx is not None else -1
                    if key_idx not in preambles:
                        _add_preamble_bounded(preambles, key_idx)
                        claimed = True
                if claimed:
                    _ = self.emit(idx if idx is not None else 0, content + "\n\n", None)
            else:
                _ = emit_content(
                    idx, content
                )  # live planner-текст, независимо от tool_calls
        if idx is None:
            return
        self.note_planner_record(rec, idx)
        thinking = rec.get("thinking")
        self._apply_final(idx, thinking if isinstance(thinking, str) else "")

    # ---- состояние шагов -----------------------------------------------------------
    def _state(self, idx: int) -> _StepState:
        state = self.seen.get(idx)
        if state is not None:
            return state
        if len(self.seen) >= MAX_STEPS_TRACKED:
            evictable = [
                k
                for k, s in self.seen.items()
                if s.finalized and k < self.poll_watermark
            ]
            if evictable:
                del self.seen[min(evictable)]
            else:
                self._sqlite_off("seen_cap")
                del self.seen[min(self.seen)]
        state = _StepState()
        self.seen[idx] = state
        return state

    def _step_done(self, state: _StepState) -> bool:
        return state.sql_done or (
            state.finalized and (self.mode != "SHADOW" or state.canary_done)
        )

    def _advance_watermark(self) -> None:
        """Сдвинуть нижнюю границу SELECT через непрерывный префикс завершённых шагов."""
        mark = self.poll_watermark
        for key in sorted(self.seen):
            if key < mark:
                continue
            if not self._step_done(self.seen[key]):
                break
            mark = key + 1
        self.poll_watermark = mark

    def _emit_delta(self, idx: int, state: _StepState, delta: str, source: str) -> bool:
        def delivered() -> None:
            state.delivered_len += len(delta)
            state.delivered_sha.update(delta.encode("utf-8"))

        ok = self.emit(idx, delta, delivered)
        if not ok:
            self.dead = True
            return False
        self.emitted += 1
        self._note_activity()
        _log(f"{source}-emit cid={self._cid8()} step={idx} len={len(delta)}")
        return True

    def _diverge(
        self, idx: int, state: _StepState, source: str, len_prev: int, len_new: int
    ) -> None:
        """Непрефиксное изменение: выдача шага замораживается на отданном префиксе."""
        state.diverged = True
        self.failed = True
        _count_divergence()
        if self.mode == "LIVE":
            _compat_demote()
        _log(
            f"sqlite_{source}_divergence cid={self._cid8()} step={idx} len_prev={len_prev} len_new={len_new}"
        )
        self._sqlite_off("divergence")

    def _apply_snapshot(self, idx: int, state: _StepState, text: str) -> None:
        """SQLite-снимок 20.3: выдать приращение, только если это префиксное продолжение."""
        if self.mode != "LIVE" or state.diverged or not text:
            return
        sent = state.delivered_len
        if sent == 0:
            _ = self._emit_delta(idx, state, text, "sqlite")
        elif len(text) < sent:
            return  # устаревший снимок
        elif _sha(text[:sent]) != state.delivered_sha.hexdigest():
            self._diverge(idx, state, "snapshot", sent, len(text))
        elif len(text) > sent:
            _ = self._emit_delta(idx, state, text[sent:], "sqlite")

    def _apply_final(self, idx: int, final_text: str) -> None:
        """Финал шага из транскрипта: докинуть хвост или заморозить при расхождении."""
        state = self._state(idx)
        if state.finalized:
            return
        state.final_len = len(final_text)
        state.final_sha = _sha(final_text) if final_text else ""
        sent = state.delivered_len
        if state.diverged:
            pass
        elif sent == 0:
            if final_text:
                _ = self._emit_delta(idx, state, final_text, "tail")
        elif (
            len(final_text) >= sent
            and _sha(final_text[:sent]) == state.delivered_sha.hexdigest()
        ):
            if len(final_text) > sent:
                _ = self._emit_delta(idx, state, final_text[sent:], "tail")
        else:
            self._diverge(idx, state, "transcript", sent, len(final_text))
        state.finalized = True
        self._judge_canary(idx, state)
        self._advance_watermark()

    def _judge_canary(self, idx: int, state: _StepState) -> None:
        """Семантический canary: финал транскрипта против status=3 снимка того же шага."""
        if (
            state.canary_done
            or not state.finalized
            or not state.observed_final
            or state.final_len == 0
            or state.diverged
        ):
            return
        state.canary_done = True
        if state.observed_len == 0:
            _compat_demote()
            _log(f"sqlite-live-loss cid={self._cid8()} step={idx}")
        elif state.observed_sha == state.final_sha:
            if self.mode == "SHADOW" and _compat_promote(self.plan.identity):
                _log("compat state=LIVE")
        elif self.mode == "SHADOW":
            state.diverged = True
            self.failed = True
            _count_divergence()
            _log(
                f"sqlite_transcript_divergence cid={self._cid8()} step={idx} len_prev={state.observed_len} len_new={state.final_len}"
            )
            self._sqlite_off("divergence")

    # ---- SQLite --------------------------------------------------------------------
    def _poll_sqlite(self) -> tuple[int, int] | None:
        """Один опрос: свой connect mode=ro, один SELECT, close в finally.

        Возвращает (число строк, число строк status=8) после успешного SELECT.
        """
        self.last_poll = "skip"
        if not self._sqlite_permitted() or self._db_path is None:
            return None
        if not self.bucket.take():
            return None
        conn: sqlite3.Connection | None = None
        result: tuple[int, int] | None = None
        try:
            conn = _sqlite_open_ro(self._db_path)
            with self._conn_lock:
                self._active_conn = conn
            result = self._select_rows(conn)
            self.last_poll = "ok"
        except sqlite3.Error as exc:
            self.last_poll = "error"
            self._on_sqlite_error(exc)
        except Exception as exc:
            self.last_poll = "error"
            _log(f"sqlite-error cid={self._cid8()} err={type(exc).__name__}")
            self._sqlite_off("internal")
        finally:
            with self._conn_lock:
                self._active_conn = None
                if conn is not None:
                    _sqlite_close(conn)
        return result

    def _on_sqlite_error(self, exc: sqlite3.Error) -> None:
        message = str(exc).lower()
        if "interrupted" in message and (self._interrupted or self.stop_event.is_set()):
            return  # собственный stop/interrupt отказом не считается
        operational = isinstance(exc, sqlite3.OperationalError)
        schema = operational and (
            "no such table" in message or "no such column" in message
        )
        cold = False
        if schema:
            self.failed = True
            _log(f"sqlite-schema-mismatch cid={self._cid8()}")
            self._sqlite_off("schema")
        elif operational:
            # cold-open: базы или её -wal ещё нет либо ошибка до первого успешного SELECT.
            wal = Path(str(self._db_path) + "-wal")
            cold = self.selects_ok == 0 or not wal.exists()
            if not cold:
                self.failed = True
        elif isinstance(exc, sqlite3.DatabaseError):
            self.failed = True
            self._sqlite_off("db_error")
        if not self._open_fail_logged:
            self._open_fail_logged = True
            _log(
                f"sqlite-open-fail cid={self._cid8()} err={type(exc).__name__} cold={1 if cold else 0}"
            )

    def _select_rows(self, conn: sqlite3.Connection) -> tuple[int, int]:
        start = max(self.poll_watermark, self.base_idx)
        cur = conn.execute(_STEPS_SQL, (start,))
        rows = 0
        generating = 0
        try:
            while True:
                if self.stop_event.is_set() or not self._sqlite_permitted():
                    break
                batch = cast("list[tuple[object, ...]]", cur.fetchmany(1))
                if not batch:
                    self.selects_ok += 1
                    break
                row = batch[0]
                idx, status, blob_len, payload = row[0], row[1], row[2], row[3]
                if not isinstance(idx, int) or not isinstance(status, int):
                    continue
                rows += 1
                if status == STEP_STATUS_GENERATING:
                    generating += 1
                self._handle_row(idx, status, blob_len, payload)
                if self.dead:
                    break
        finally:
            cur.close()
        self._advance_watermark()
        return rows, generating

    def _handle_row(
        self, idx: int, status: int, blob_len: object, payload: object
    ) -> None:
        state = self._state(idx)
        if state.finalized:
            if status == STEP_STATUS_DONE and not state.canary_done and state.final_len:
                self._observe_final_snapshot(idx, state, payload)
            return
        if state.diverged:
            return
        state.sql_seen = True
        if payload is None or not isinstance(payload, (bytes, bytearray)):
            if (
                isinstance(blob_len, int)
                and blob_len > MAX_STEP_BLOB_BYTES
                and idx not in self._oversize_logged
            ):
                self._oversize_logged.add(idx)
                _log(
                    f"sqlite-oversize cid={self._cid8()} step={idx} blob_len={blob_len}"
                )
            if status == STEP_STATUS_DONE:
                state.sql_done = True
            return
        data = bytes(payload)
        digest = hashlib.sha256(data).hexdigest()
        if state.blob_len == len(data) and state.blob_sha == digest:
            # Снимок не менялся: парсер не вызывается, меняется только статус шага.
            if status == STEP_STATUS_DONE:
                state.sql_done = True
                state.observed_final = True
                self._judge_canary(idx, state)
            return
        text = _extract_thinking_from_step_blob(
            data, final=(status == STEP_STATUS_DONE), stop=self.stop_event
        )
        if self.stop_event.is_set():
            return
        state.blob_len, state.blob_sha = len(data), digest
        first_gen = state.observed_len == 0 and bool(text)
        state.observed_len = len(text)
        state.observed_sha = _sha(text) if text else ""
        state.observed_final = status == STEP_STATUS_DONE
        if status == STEP_STATUS_DONE:
            state.sql_done = True
        if first_gen and status == STEP_STATUS_GENERATING:
            _log(f"sqlite-gen cid={self._cid8()} step={idx}")
        self._apply_snapshot(idx, state, text)
        self._judge_canary(idx, state)

    def _observe_final_snapshot(
        self, idx: int, state: _StepState, payload: object
    ) -> None:
        """Шаг уже финализирован транскриптом: status=3 снимок нужен только для canary."""
        if not isinstance(payload, (bytes, bytearray)):
            state.canary_done = True
            return
        text = _extract_thinking_from_step_blob(
            bytes(payload), final=True, stop=self.stop_event
        )
        if self.stop_event.is_set():
            return
        state.observed_len = len(text)
        state.observed_sha = _sha(text) if text else ""
        state.observed_final = True
        state.sql_done = True
        self._judge_canary(idx, state)

    # ---- финальное дренирование ----------------------------------------------------
    def _pending_steps(self) -> int:
        return sum(
            1
            for key, state in self.seen.items()
            if key >= self.base_idx and state.sql_seen and not state.finalized
        )

    def _drain_post_eof(self) -> None:
        """Процесс вышел: дочитать источники в окне DRAIN_WINDOW_S (≤ DRAIN_MAX_S).

        Эвристического раннего выхода нет: досрочно после DRAIN_MIN_S — только по
        авторитетному маркеру конца хода (END_TURN/TURN_COMPLETE, exit=end_turn)
        или по stop_event (exit=stop). Финальный PLANNER_RESPONSE без END_TURN/
        TURN_COMPLETE выдерживает полное окно DRAIN_WINDOW_S (exit=window).
        """
        started = time.monotonic()
        deadline = (
            self.drain_deadline if self.drain_deadline > 0 else started + DRAIN_WINDOW_S
        )
        deadline = min(deadline, started + DRAIN_MAX_S)
        earliest = started + DRAIN_MIN_S
        emitted_before = self.emitted
        exit_kind = "window"
        while True:
            if self.stop_event.is_set():
                exit_kind = "stop"
                break
            self._read_transcript()
            if self.sqlite_active:
                _ = self._poll_sqlite()
            now = time.monotonic()
            if now >= earliest and self.end_marker:
                exit_kind = "end_turn"
                break
            if now >= deadline:
                break
            time.sleep(min(DRAIN_POLL_STEP_S, max(0.0, deadline - now)))
        pending = self._pending_steps()
        complete = pending == 0 and (self.final_planner or self.end_marker)
        self.drain_outcome = "complete" if complete else "window_complete"
        if exit_kind != "stop" and pending > 0:
            _count_drain_deadline()
        ms = int((time.monotonic() - started) * 1000)
        _log(
            f"drain cid={self._cid8()} ms={ms} emitted={self.emitted - emitted_before} outcome={self.drain_outcome} pending_steps={pending} exit={exit_kind}"
        )


@final
class JobConflict(ValueError):
    """Ключ уже связан с другим входом."""


@dataclass
class _Job:
    key: str
    identity: tuple[str, str]
    events: list[tuple[str, Any]]
    cancelled: threading.Event
    readers: int = 1
    size_bytes: int = 0
    result: dict | None = None
    completed_at: float | None = None
    orphan: bool = False
    running: bool = True
    cancel: Callable[[], None] | None = None


class JobRegistry:
    """Атомарные attach/replay, bounded память, TTL/LRU и реальные orphan-слоты."""

    def __init__(
        self,
        *,
        max_buffer_bytes: int | None = None,
        max_entries: int | None = None,
        ttl_s: float | None = None,
        orphan_max: int | None = None,
    ) -> None:
        self.max_buffer_bytes = (
            max_buffer_bytes
            if max_buffer_bytes is not None
            else _env_int(
                "AGY_BRIDGE_JOB_BUFFER_MAX_BYTES", 5 * 1024 * 1024, 1, sys.maxsize
            )
        )
        self.max_entries = (
            max_entries
            if max_entries is not None
            else _env_int("AGY_BRIDGE_JOB_MAX_ENTRIES", 100, 0, sys.maxsize)
        )
        self.ttl_s = (
            ttl_s
            if ttl_s is not None
            else _env_float("AGY_BRIDGE_JOB_TTL_S", 900.0, 0.0, float("inf"))
        )
        self.orphan_max = (
            orphan_max
            if orphan_max is not None
            else _env_int("AGY_BRIDGE_ORPHAN_CONCURRENCY_MAX", 5, 0, sys.maxsize)
        )
        self.condition = threading.Condition(threading.Lock())
        self.jobs: dict[str, _Job] = {}
        self.completed: collections.OrderedDict[str, _Job] = collections.OrderedDict()
        self.expiry: collections.deque[tuple[float, str, _Job]] = collections.deque()
        self.orphans = 0

    def _prune(self) -> None:
        now = time.monotonic()
        while self.expiry and self.expiry[0][0] <= now:
            _at, key, job = self.expiry.popleft()
            if self.jobs.get(key) is job and job.result is not None:
                self.jobs.pop(key, None)
                self.completed.pop(key, None)
        while len(self.completed) > self.max_entries:
            key, job = self.completed.popitem(last=False)
            if self.jobs.get(key) is job:
                self.jobs.pop(key, None)
        # Реестр expiry тоже bounded: ссылки вытесненных записей не живут до TTL.
        if len(self.expiry) > self.max_entries:
            self.expiry = collections.deque(
                (at, key, job)
                for at, key, job in self.expiry
                if self.jobs.get(key) is job
            )

    def attach(self, key: str, model: str, prompt: str) -> tuple[_Job, bool]:
        identity = (model, hashlib.sha256(prompt.encode("utf-8")).hexdigest())
        with self.condition:
            self._prune()
            job = self.jobs.get(key)
            if job is not None:
                if job.identity != identity:
                    raise JobConflict(
                        "idempotency key is bound to another model or prompt"
                    )
                job.readers += 1
                if job.orphan and not job.cancelled.is_set():
                    job.orphan = False
                    self.orphans -= 1
                if key in self.completed:
                    self.completed.move_to_end(key)
                return job, False
            job = _Job(key, identity, [], threading.Event())
            self.jobs[key] = job
            return job, True

    def bind_cancel(self, job: _Job, cancel: Callable[[], None] | None) -> None:
        with self.condition:
            job.cancel = cancel
            should_cancel = job.cancelled.is_set()
        if should_cancel and cancel is not None:
            cancel()

    def _terminal(self, job: _Job, result: dict) -> None:
        if job.result is None:
            job.result = result
        self.condition.notify_all()
        if job.running or job.completed_at is not None:
            return
        job.completed_at = time.monotonic()
        if job.orphan:
            self.orphans -= 1
            job.orphan = False
        key = job.key
        if self.jobs.get(key) is job:
            self.completed[key] = job
            self.expiry.append((job.completed_at + self.ttl_s, key, job))
        self._prune()

    def publish(self, job: _Job, kind: str, payload: Any) -> bool:
        size = len(json.dumps((kind, payload), ensure_ascii=False).encode("utf-8"))
        cancel = None
        with self.condition:
            if job.result is not None or job.cancelled.is_set():
                return False
            if job.size_bytes + size > self.max_buffer_bytes:
                job.cancelled.set()
                self._terminal(job, {"state": "buffer_overflow", "text": "", "rc": 1})
                cancel = job.cancel
            else:
                job.events.append((kind, payload))
                job.size_bytes += size
                self.condition.notify_all()
                return True
        if cancel is not None:
            cancel()
        return False

    def finish(self, job: _Job, result: dict) -> None:
        with self.condition:
            job.running = False
            job.cancel = None
            if job.cancelled.is_set() and job.result is None:
                result = {"state": "orphan_limit", "text": "", "rc": 1}
            if (
                job.size_bytes
                + len(
                    json.dumps(
                        {
                            key: result.get(key)
                            for key in ("text", "reasoning", "retained_events")
                        },
                        ensure_ascii=False,
                    ).encode("utf-8")
                )
                > self.max_buffer_bytes
            ):
                result = {"state": "buffer_overflow", "text": "", "rc": 1}
            self._terminal(job, result)

    def read(
        self, job: _Job, offset: int, timeout: float
    ) -> tuple[list[tuple[str, Any]], dict | None]:
        with self.condition:
            if offset >= len(job.events) and job.result is None:
                self.condition.wait(timeout=timeout)
            return job.events[offset:], job.result

    def detach(self, job: _Job) -> None:
        cancel = None
        with self.condition:
            job.readers = max(0, job.readers - 1)
            if job.readers or job.result is not None or job.orphan:
                return
            if self.orphans < self.orphan_max:
                job.orphan = True
                self.orphans += 1
            else:
                job.cancelled.set()
                cancel = job.cancel
                self.condition.notify_all()
        # close()/kill/reap — только вне mutex; producer освободит Bulkhead в finally.
        if cancel is not None:
            cancel()


_JOB_REGISTRY = JobRegistry()


def resolve_agy_mode(req: dict) -> str:
    """Текстовый запрос не разрешает нативные инструменты CLI."""
    return (
        "agent"
        if req.get("tools") or req.get("functions") or req.get("agent_tools") is True
        else "ask"
    )


def _with_pure_text_protocol(prompt: str) -> str:
    """Инструкция подавления нативных инструментов agy CLI для чисто текстового хода."""
    suppress = (
        "[CRITICAL: DO NOT USE ANY TOOLS (no read_file, no grep, no bash, no agent tools). "
        "Provide your analysis and answer directly as pure text.]"
    )
    return f"{suppress}\n\n{prompt}" if prompt else suppress


def _with_tools_protocol(prompt: str, tools: list, tool_choice: object) -> str:
    """Промпт хода эмуляции: секция протокола `<tool_call>` ядра перед историей agy."""
    section = _core_messages_to_prompt([], tools, tool_choice)
    return f"{section}\n\n{prompt}" if prompt else section


def _safe_float_env(name: str, default: float) -> float:
    val = os.getenv(name)
    if not val:
        return default
    try:
        parsed = float(val)
        return parsed if (math.isfinite(parsed) and parsed > 0.0) else default
    except (ValueError, TypeError):
        return default


def _safe_int_env(name: str, default: int) -> int:
    val = os.getenv(name)
    if not val:
        return default
    try:
        parsed = int(val)
        return parsed if parsed > 0 else default
    except (ValueError, TypeError):
        return default


@final
class _ToolTurn:
    """Эмуляция одного хода OpenAI function calling поверх потока agy.

    Закрытие отдельного вызова не завершает ход: ожидаем следующего
    вызова, EOF либо периода тишины без открытого блока. Любая активность
    upstream (текст, reasoning, tool_trace) сбрасывает таймер тишины.
    """

    def __init__(
        self,
        tools: list,
        on_content: Callable[[str], bool],
        on_reasoning: Callable[[str], bool],
        on_calls: Callable[[list[dict[str, object]]], bool],
    ) -> None:
        self._schemas = build_tool_schemas(tools)
        self._on_content = on_content
        self._on_reasoning = on_reasoning
        self._on_calls = on_calls
        self.calls: list[dict[str, object]] = []
        self.error = ""
        self.ok = True
        self._is_repetition_loop = False
        self._finished = False
        self._max_calls = _safe_int_env("AGY_MAX_TOOL_CALLS", 32)
        self._max_bytes = _safe_int_env("AGY_MAX_TOOL_BYTES", 10 * 1024 * 1024)
        self._settle_timeout_s = _safe_float_env("AGY_TOOL_SETTLE_TIMEOUT_S", 5.0)
        self._stall_timeout_s = _safe_float_env("AGY_TOOL_CALL_STALL_TIMEOUT_S", 30.0)
        self._total_bytes = 0
        self._last_chunk_ts = time.monotonic()
        self._last_open_chunk_ts = 0.0
        self._normalizer = StreamNormalizer(
            self._content, self._reasoning, self._call, strict_live=True
        )

    @property
    def content(self) -> str:
        return self._normalizer.content

    @property
    def reasoning(self) -> str:
        return self._normalizer.reasoning_content

    def notify_activity(self) -> None:
        """Сбросить таймеры тишины при полезной активности upstream."""
        self._last_chunk_ts = time.monotonic()
        if self._normalizer.has_open_tool_call():
            self._last_open_chunk_ts = self._last_chunk_ts

    def feed_reasoning(self, text: str) -> bool:
        """Принять reasoning от upstream, сбросив таймер тишины хода."""
        self.notify_activity()
        if self.ok and not self._on_reasoning(text):
            self.ok = False
        return self.ok

    def _content(self, text: str) -> None:
        if self.ok and not self._on_content(text):
            self.ok = False

    def _reasoning(self, text: str) -> None:
        if self.ok and not self._on_reasoning(text):
            self.ok = False

    def _call(self, call: dict[str, Any]) -> None:
        if len(self.calls) >= self._max_calls:
            raise LiveParserError(f"tool call count exceeded limit ({self._max_calls})")
        entry: dict[str, object] = {
            "index": len(self.calls),
            "id": str(call.get("id") or "call_" + uuid.uuid4().hex[:24]),
            "type": "function",
            "function": {
                "name": str(call.get("name") or ""),
                "arguments": json.dumps(
                    call.get("arguments") or {}, ensure_ascii=False
                ),
            },
        }
        published = [
            dict(cast("dict[str, object]", item), index=len(self.calls) + offset)
            for offset, item in enumerate(sanitize_tool_call(entry, self._schemas))
        ]
        if len(self.calls) + len(published) > self._max_calls:
            raise LiveParserError(f"tool call count exceeded limit ({self._max_calls})")
        self.calls.extend(published)
        if self.ok and not self._on_calls(published):
            self.ok = False

    def feed(self, text: str) -> bool:
        """Принять дельту; ошибки разбора и превышение лимитов — fail-closed."""
        if self.error or self._finished or not text:
            return self.ok
        chunk_bytes = len(text.encode("utf-8"))
        if self._total_bytes + chunk_bytes > self._max_bytes:
            self.error = f"tool call buffer exceeded max bytes ({self._max_bytes})"
            return self.ok
        self._total_bytes += chunk_bytes
        self.notify_activity()
        if self._normalizer.has_open_tool_call():
            self._last_open_chunk_ts = self._last_chunk_ts
        try:
            self._normalizer.feed_text(text)
        except RepetitionLoopDetected as exc:
            self._is_repetition_loop = True
            self.error = str(exc) or type(exc).__name__
        except LiveParserError as exc:
            self.error = str(exc) or type(exc).__name__
        # Проверяем состояние ПОСЛЕ feed_text
        if self._normalizer.has_open_tool_call():
            self._last_open_chunk_ts = self._last_chunk_ts
        else:
            self._last_open_chunk_ts = 0.0
        return self.ok

    def finish(self) -> None:
        """На EOF сбросить хвост; незакрытый блок зафиксировать как ошибку."""
        if self.error or self._finished:
            return
        self._finished = True
        try:
            self._normalizer.finish()
        except RepetitionLoopDetected as exc:
            self._is_repetition_loop = True
            self.error = str(exc) or type(exc).__name__
        except LiveParserError as exc:
            self.error = str(exc) or type(exc).__name__

    def turn_complete(self) -> bool:
        """Завершить ход при ошибке или после тишины вне блока вызова."""
        if self.error:
            return True
        now = time.monotonic()
        if self._normalizer.has_open_tool_call():
            if (
                self._last_open_chunk_ts > 0.0
                and now - self._last_open_chunk_ts >= self._stall_timeout_s
            ):
                self.error = (
                    "tool call block stalled without progress for "
                    f"{self._stall_timeout_s:g}s"
                )
                return True
            return False
        if self.calls:
            return now - self._last_chunk_ts >= self._settle_timeout_s
        return False

    def error_body(self) -> dict[str, Any]:
        err_msg = self.error or ""
        if (
            getattr(self, "_is_repetition_loop", False)
            or "upstream_repetition_loop" in err_msg
        ):
            return {
                "message": "upstream repetition loop detected",
                "detail": err_msg[:500],
                "type": "upstream_repetition_loop",
                "code": 502,
            }
        return {
            "message": "agy emitted a malformed tool call",
            "detail": err_msg[:500],
            "type": "tool_call_parse_error",
            "code": 502,
        }


class Run:
    """Один процесс `agy`; поток-читатель превращает stdout NDJSON в события очереди.

    Промпт подаётся на stdin одной NDJSON-строкой и поток закрывается (`communicate`
    через отдельный поток-писатель): CLI читает stdin до EOF. `-p` не передаётся
    никогда — см. модуль-docstring.

    Очередь закрывается атомарно: ни одно ("reasoning", …) не ставится после
    ("done", …) — оба события кладутся под `_emit_lock`.
    """

    def __init__(
        self,
        prompt: str,
        model: str,
        effort: str,
        effort_source: str,
        cwd: str,
        tag: str,
        conversation_id: str = "",
        turn_id: str = "",
        policy: _TimeoutPolicy | None = None,
        add_dir: Path | None = None,
        mode: str = "agent",
    ):
        launcher = _launcher()
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        work_dir = cwd if (cwd and os.path.isdir(cwd)) else str(WORKSPACE)
        self.work_dir = work_dir
        self.mode = mode
        if AGY_BRIDGE_ENABLE_HEAD_PRUNING:
            prompt = _ensure_prompt_fits_ndjson(prompt)
        self.stdin_line = _ndjson_user_line(prompt)
        cli_mode = (
            os.environ.get("AGY_BRIDGE_ASK_CLI_MODE", "plan")
            if mode in ("ask", "plan")
            else os.environ.get("AGY_BRIDGE_AGENT_CLI_MODE", "auto")
            if mode in ("agent", "auto")
            else mode
        )
        cmd = [
            launcher,
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--dangerously-skip-permissions",
            "--mode",
            cli_mode,
            "--model",
            model,
            "--effort",
            effort,
            "--print-timeout=" + str(PRINT_TIMEOUT),
        ]
        # Изображения хода: каталог файлов отдельным аргументом, cwd не подменяется.
        if add_dir is not None:
            cmd += ["--add-dir", str(add_dir)]
        # RESUME: продолжение треда — отдельным флагом, промпт всё равно через stdin.
        self.run_cid = conversation_id or ""
        self.turn_id: str = turn_id or uuid.uuid4().hex
        if self.run_cid:
            cmd += ["--conversation", self.run_cid]
        # Флаг usage по окну шага фиксируется на попытку: коллектор счётчиков и выбор
        # файла транскрипта живут весь ход, финальный выбор формы usage — в _run_once.
        self.usage_enabled: bool = _new_flag("step_scoped_usage_enabled")
        # Единая монотонная точка отсчёта terminal drain попытки (<= DRAIN_MAX_S).
        self._drain_t0: float | None = None
        # Водяной знак resume снимается ДО spawn: история разговора не переотдаётся.
        plan = _prespawn_plan(self.run_cid, bool(self.run_cid), self.usage_enabled)
        if self.run_cid and not _cid_acquire(self.run_cid, self.turn_id):
            plan.anchored = False
            plan.reason = "cid_busy"
        try:
            self.proc = spawn_registered(
                cmd,
                cwd=work_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                env=_launch_env(),
            )
        except BaseException:
            _cid_release(self.run_cid, self.turn_id)
            raise
        self.started = time.monotonic()
        # Политика попытки (AD-003): None — прежние TIMEOUT_S/IDLE_TIMEOUT_S.
        self.policy = policy
        enabled = _is_watchdog_enabled()
        # Kill-switch выключен: порог неактивности = сквозной таймаут, `ps` не вызывается.
        if policy is not None:
            idle_s, cap_s = policy.idle_timeout_s, policy.effective_max_timeout_s
        else:
            idle_s = IDLE_TIMEOUT_S if enabled else float(TIMEOUT_S)
            cap_s = float(TIMEOUT_S)  # дефолт core (3600 с) не используется
        self.controller = AdaptiveTimeoutController(
            idle_timeout_s=idle_s,
            safety_cap_s=cap_s,
            finish_reserve_s=0.0,  # эффективный потолок ровно cap_s
            watchdog_enabled=enabled,
            log_fn=_log,
        )
        self.controller.register_pgid(self.proc.pid)
        self.got_event = False  # True после первого валидного JSON-события stdout
        self.stderr_head: list = []
        with _active_lock:
            _active[self.proc.pid] = self.proc
        self.q = queue.Queue()
        self.err_box = []
        # Протокол antigravity-cli передаёт инкрементальные чанки (text_delta).
        # Run аккумулирует дельты текущего шага в _stdout_step_accum для арбитража и изоляции преамбул.
        self._text_seen: dict = {}
        self._stdout_step_accum: collections.OrderedDict[object, str] = (
            collections.OrderedDict()
        )
        self._stdout_accum_bytes: int = 0
        self._preambles_emitted: set[int] = set()
        self._stdout_preamble_steps: set[int] = set()
        self._tool_step_indices: set[object] = set()
        self._last_reasoning_step_index: int | None = None
        self._last_reasoning_chunk: str = ""
        # Выдача мышления: счётчик байт и закрытие очереди под одним замком.
        self._emit_lock = threading.Lock()
        self.drain_closed: bool = False
        self._done_put: bool = False
        self._reasoning_bytes: int = 0
        self._cap_logged: bool = False
        # Мышление шагов: отдельный поток следит за транскриптом и SQLite разговора и
        # кладёт в очередь события ("reasoning", текст).
        self._proc_done = threading.Event()
        self._stop_watch = threading.Event()
        # Арбитр planner-контента двух источников (AD-001): работает под _emit_lock.
        self.content_streaming = _new_flag("planner_content_streaming_enabled")
        self.isolate_tool_preambles = _new_flag(
            "isolate_tool_preambles_to_reasoning", True
        )
        self._arbiter = _ContentArbiter(self.turn_id)
        self._last_step_index: object = None
        self._content_emitted_wire: str = ""
        # Реальная активность producer'ов (stdout/transcript), независимо от cpu_delta.
        self._activity_lock = threading.Lock()
        self.last_producer_activity_ts: float = self.started
        self.transcript_activity_ts: float | None = None
        _decide_turn_mode(plan)
        self._tail = _TranscriptTail(
            emit=self._emit_reasoning,
            stop_event=self._stop_watch,
            done_event=self._proc_done,
            resumed=bool(self.run_cid),
            plan=plan,
            turn_id=self.turn_id,
            emit_content=self._offer_transcript if self.content_streaming else None,
            on_activity=self._on_tail_activity,
            usage_enabled=self.usage_enabled,
            isolate_tool_preambles=self.isolate_tool_preambles,
            preambles_emitted=self._preambles_emitted,
            run_ref=self,
        )
        if policy is not None:
            self._tail.deadline_s = policy.effective_max_timeout_s + 60.0
        if self.run_cid:
            self._tail.bind(self.run_cid)
        threading.Thread(target=self._feed_stdin, daemon=True).start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        threading.Thread(target=self._pump, daemon=True).start()
        self._tail.start()

    def _emit_reasoning(
        self, idx: int, delta: str, on_delivered: Callable[[], None] | None = None
    ) -> bool:
        """Поставить дельту мышления в очередь; False — очередь закрыта или потолок.

        Закрытие очереди, счётчик байт и учёт выданного (`on_delivered`) идут под
        одним `_emit_lock`: после ("done", …) ни одно ("reasoning", …) не попадает.
        При смене `step_index`, если предыдущий фрагмент не оканчивался переводом
        строки, автоматически добавляется разделитель `\\n\\n`.
        """
        orig_len = len(delta)
        outcome = ""
        log_cap = False
        with self._emit_lock:
            sep = ""
            last_idx = getattr(self, "_last_reasoning_step_index", None)
            last_chunk = getattr(self, "_last_reasoning_chunk", "")
            if (
                last_idx is not None
                and last_idx != idx
                and last_chunk
                and not last_chunk.endswith("\n")
                and delta
            ):
                if not delta.startswith("\n"):
                    sep = "\n\n"
                elif not delta.startswith("\n\n"):
                    sep = "\n"
            out_delta = sep + delta
            size = len(out_delta.encode("utf-8"))
            if self.drain_closed:
                outcome = "late"
            elif self._reasoning_bytes + size > MAX_REASONING_BYTES_PER_TURN:
                outcome = "cap"
                log_cap = not self._cap_logged
                self._cap_logged = True
            else:
                self._reasoning_bytes += size
                self._last_reasoning_step_index = idx
                if out_delta:
                    self._last_reasoning_chunk = out_delta
                self.q.put(("reasoning", out_delta))
                if on_delivered is not None:
                    on_delivered()
                return True
            total = self._reasoning_bytes
        cid8 = self._tail.cid[:8] or "-"
        if outcome == "late":
            _log(f"reasoning-late-drop cid={cid8} step={idx} len={orig_len}")
        elif log_cap:
            _log(f"reasoning-cap cid={cid8} bytes={total}")
        return False

    def _close_and_put_done(self, kind: str, payload: object) -> None:
        """Атомарно закрыть выдачу мышления и поставить терминальное событие (один раз)."""
        with self._emit_lock:
            if self._done_put:
                return
            self._done_put = True
            self.drain_closed = True
            self.q.put((kind, payload))

    def note_producer_activity(self, source: str) -> None:
        """Новый прогресс producer'а (stdout/transcript): продлевает idle, не зависит от CPU."""
        now = time.monotonic()
        with self._activity_lock:
            self.last_producer_activity_ts = now
            if source == "transcript":
                self.transcript_activity_ts = now

    def _on_tail_activity(self) -> None:
        self.note_producer_activity("transcript")

    def offer_content(self, source: str, step_index: object, text: str) -> bool:
        """Кандидат planner-текста в арбитр; новый суффикс уходит в очередь под _emit_lock.

        Сокетного ввода-вывода здесь нет: потребитель (`_execute`) пишет в сокет сам.
        False — выдача уже закрыта terminal barrier'ом.
        """
        with self._emit_lock:
            if self.drain_closed:
                return False
            suffix = self._arbiter.offer(
                source, step_index, text, self._tail.cid or self.run_cid
            )
            if suffix:
                sep = ""
                last_idx = getattr(self, "_last_step_index", None)
                emitted_wire = getattr(self, "_content_emitted_wire", "")
                if last_idx is not None and last_idx != step_index and emitted_wire:
                    if not emitted_wire.endswith("\n"):
                        sep = (
                            "\n\n"
                            if not suffix.startswith("\n")
                            else ("\n" if not suffix.startswith("\n\n") else "")
                        )
                    elif not emitted_wire.endswith("\n\n"):
                        sep = "\n" if not suffix.startswith("\n") else ""
                self._last_step_index = step_index
                self._content_emitted_wire = emitted_wire + sep + suffix
                self.q.put(("text", sep + suffix))
        return True

    def _offer_transcript(self, step_index: int | None, text: str) -> bool:
        return self.offer_content("transcript", step_index, text)

    def reconcile_result(self, text: str) -> str:
        """Недостающий хвост `result.response` относительно уже принятого арбитром и выданного в wire."""
        with self._emit_lock:
            emitted_wire = getattr(self, "_content_emitted_wire", "")
            fallback_used = False
            fallback_idx: object = None
            if not text and not emitted_wire:
                step_accum = getattr(self, "_stdout_step_accum", None)
                if isinstance(step_accum, dict) and step_accum:
                    last_idx = next(reversed(step_accum))
                    tool_steps = getattr(self, "_tool_step_indices", None) or set()
                    tail_tools = (
                        getattr(
                            getattr(self, "_tail", None), "_tool_step_indices", None
                        )
                        or set()
                    )
                    if last_idx not in tool_steps and last_idx not in tail_tools:
                        candidate = str(step_accum.get(last_idx) or "")
                        if candidate:
                            text = candidate
                            fallback_used = True
                            fallback_idx = last_idx
            if emitted_wire and text:
                if text == emitted_wire or emitted_wire.startswith(text):
                    self._arbiter.last_result_diverged = False
                    return ""
                if text.startswith(emitted_wire):
                    self._arbiter.last_result_diverged = False
                    suffix = text[len(emitted_wire) :]
                    self._content_emitted_wire = text
                    return suffix
                clean_text = text.replace("\r\n", "\n").strip()
                clean_wire = emitted_wire.replace("\r\n", "\n").strip()
                if clean_text == clean_wire or clean_wire.startswith(clean_text):
                    self._arbiter.last_result_diverged = False
                    return ""
            delta = self._arbiter.reconcile_result(text)
            if delta:
                self._content_emitted_wire = emitted_wire + delta
                if fallback_used and not getattr(self, "drain_closed", True):
                    self._last_step_index = fallback_idx
                    self.q.put(("text", delta))
            return delta

    def retained_divergent_text(self) -> str:
        """Расходящийся (непрефиксный) planner-текст, удержанный арбитром."""
        with self._emit_lock:
            return self._arbiter.retained_divergent_text()

    def terminal_drain(self, budget_s: float) -> list[tuple[str, object]]:
        """Ограниченный (<= budget_s) финальный дренаж на timeout/ошибке: хвост источников,
        заморозка выдачи и остаток очереди ДО terminal marker'а.

        Процесс при этом ещё жив: окно дренирования хвоста открывает `_proc_done`.
        Возвращает необработанные потребителем события ("text"/"reasoning"/"tool_trace").
        """
        started = time.monotonic()
        join_budget = budget_s
        if getattr(self, "usage_enabled", False):
            # Один монотонный дедлайн попытки от EOF/первого drain: content-drain и
            # usage-drain делят его, второго окна нет.
            t0 = getattr(self, "_drain_t0", None)
            t0 = started if t0 is None else t0
            self._drain_t0 = t0
            limit = t0 + min(budget_s, DRAIN_MAX_S)
            if not getattr(self._tail, "drain_deadline", 0.0):
                self._tail.drain_deadline = min(limit, t0 + DRAIN_WINDOW_S)
            join_budget = max(0.0, limit - started)
        else:
            self._tail.drain_deadline = started + min(budget_s, DRAIN_WINDOW_S)
        self._proc_done.set()
        thread = self._tail.thread
        if thread is not threading.current_thread():
            thread.join(timeout=max(0.0, join_budget - (time.monotonic() - started)))
        with self._emit_lock:
            self.drain_closed = True
            self._done_put = True
        events: list[tuple[str, object]] = []
        while True:
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                break
            if kind in ("text", "reasoning", "tool_trace"):
                events.append((kind, payload))
        return events

    def usage_snapshot(self) -> _UsageSnapshot:
        """Снимок счётчиков хода; пока поток tail жив, полнота суммы не гарантируется."""
        getter = getattr(self._tail, "usage_snapshot", None)
        snap = getter() if callable(getter) else _EMPTY_USAGE_SNAPSHOT
        thread = getattr(self._tail, "thread", None)
        if (
            snap.completeness
            and thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            return replace(snap, completeness=False)
        return snap

    def _feed_stdin(self) -> None:
        """Отдать промпт на stdin и закрыть поток: agy читает stdin до EOF."""
        try:
            self.proc.stdin.write(self.stdin_line.encode("utf-8"))
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass
        finally:
            try:
                self.proc.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass
            self.proc.stdin = None

    def _drain_stderr(self) -> None:
        """Читать stderr построчно, держать только хвост: он идёт в error-ответ."""
        head: list = []
        try:
            for raw in iter(self.proc.stderr.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip()
                if not line or _NOISE.search(line):
                    continue
                head.append(line)
                if len(head) > 40:
                    del head[0]
        except Exception:  # noqa: BLE001 — вторичный поток, ошибку терять нельзя молча
            pass
        self.err_box.append("\n".join(head).strip())

    def claim_preamble(self, step_idx: int | None, source: str = "transcript") -> bool:
        """Атомарно заявить право на отправку преамбулы шага.

        - source == "stdout":
          Если step_idx уже был успешно заявлен stdout (step_idx in _stdout_preamble_steps),
          возвращает True (продолжение стриминга дельт текущего шага).
          Если step_idx уже был заявлен transcript (step_idx in _preambles_emitted),
          возвращает False (подавление дубля).
          Иначе атомарно регистрирует step_idx и в _preambles_emitted, и в _stdout_preamble_steps
          и возвращает True.

        - source == "transcript":
          Если step_idx уже был заявлен (stdout или transcript), возвращает False.
          Иначе регистрирует в _preambles_emitted и возвращает True.
        """
        with self._emit_lock:
            key_idx = step_idx if step_idx is not None else -1
            preambles = getattr(self, "_preambles_emitted", None)
            if preambles is None:
                preambles = self._preambles_emitted = set()
            stdout_claimed = getattr(self, "_stdout_preamble_steps", None)
            if stdout_claimed is None:
                stdout_claimed = self._stdout_preamble_steps = set()

            if source == "stdout":
                if key_idx in stdout_claimed:
                    return True
                if key_idx in preambles:
                    return False
                _add_preamble_bounded(preambles, key_idx)
                _add_preamble_bounded(stdout_claimed, key_idx)
                return True
            else:
                if key_idx in preambles:
                    return False
                _add_preamble_bounded(preambles, key_idx)
                return True

    def _pump(self) -> None:
        """Разбор NDJSON agy 1.3.1.

        `step_update.agent_response` несёт инкрементальные дельты `text_delta`;
        Run конкатенирует их в `accum = prev + delta`. `step_update.tool` — трассировка
        нативного инструмента (в stderr моста). `result` — финальный текст, usage, ошибка.

        После EOF: ждём выход процесса не дольше PROC_EXIT_WAIT_S, затем даём
        источнику мышления дренировать окно DRAIN_WINDOW_S (join с бюджетом) и
        только потом ставим ("done", …). Терминальное событие кладётся ровно один
        раз в `finally`, поэтому очередь закрывается при любом исходе.
        """
        final_text = ""
        result_ev = {}
        tool_ordinal = 0
        tool_ordinal_by_id: dict[str, int] = {}
        term_kind = "pump_error"
        term_payload: object = "pump terminated"
        try:
            for raw in iter(self.proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("{"):
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                self.got_event = True
                self.note_producer_activity("stdout")
                etype = ev.get("event")
                if etype == "init":
                    init = ev.get("init") if isinstance(ev.get("init"), dict) else {}
                    tools_raw = cast(object, init.get("tools"))
                    tools = cast("list[object]", tools_raw) if isinstance(tools_raw, list) else []
                    self.q.put(
                        (
                            "init",
                            {
                                "conversation_id": ev.get("conversation_id") or "",
                                "tools": len(tools),
                                "permission_mode": init.get("permission_mode") or "",
                            },
                        )
                    )
                    self._tail.bind(str(ev.get("conversation_id") or ""))
                elif etype == "step_update":
                    step = ev.get("step_update") if isinstance(ev.get("step_update"), dict) else {}
                    kind = step.get("step_type")
                    if kind == "tool":
                        t_idx = _as_int(step.get("step_index"))
                        if t_idx is not None:
                            tool_steps = getattr(self, "_tool_step_indices", None)
                            if tool_steps is None:
                                tool_steps = self._tool_step_indices = set()
                            tool_steps.add(t_idx)
                    if kind == "agent_response" and step.get("text_delta"):
                        step_idx = _as_int(step.get("step_index"))
                        delta = str(step["text_delta"])
                        if not isinstance(
                            getattr(self, "_stdout_step_accum", None),
                            collections.OrderedDict,
                        ):
                            self._stdout_step_accum = collections.OrderedDict(
                                getattr(self, "_stdout_step_accum", None) or {}
                            )
                        if not hasattr(self, "_stdout_accum_bytes") or (
                            self._stdout_accum_bytes == 0 and self._stdout_step_accum
                        ):
                            self._stdout_accum_bytes = sum(
                                len(v.encode("utf-8"))
                                for v in self._stdout_step_accum.values()
                            )
                        if step_idx not in self._stdout_step_accum:
                            while (
                                len(self._stdout_step_accum) >= MAX_CONTENT_STEPS
                                and self._stdout_step_accum
                            ):
                                _old_idx, old_val = self._stdout_step_accum.popitem(
                                    last=False
                                )
                                self._stdout_accum_bytes = max(
                                    0,
                                    self._stdout_accum_bytes
                                    - len(old_val.encode("utf-8")),
                                )
                        prev = self._stdout_step_accum.get(step_idx, "")
                        delta_bytes = len(delta.encode("utf-8"))
                        room = max(
                            0, MAX_CONTENT_BYTES_PER_TURN - self._stdout_accum_bytes
                        )
                        if delta_bytes > room:
                            delta = delta.encode("utf-8")[:room].decode(
                                "utf-8", "ignore"
                            )
                            delta_bytes = len(delta.encode("utf-8"))
                        self._stdout_accum_bytes += delta_bytes
                        accum = prev + delta
                        self._stdout_step_accum[step_idx] = accum
                        isolate = bool(
                            getattr(self, "isolate_tool_preambles", False)
                            and getattr(self, "mode", "") in ("agent", "auto")
                        )
                        if self.content_streaming:
                            if isolate:
                                if delta and self.claim_preamble(
                                    step_idx, source="stdout"
                                ):
                                    _ = self._emit_reasoning(step_idx or 0, delta)
                            else:
                                _ = self.offer_content("stdout", step_idx, accum)
                        else:
                            suffix = _reasoning_suffix(
                                self._text_seen,
                                str(step.get("step_index", "")),
                                accum,
                            )
                            if suffix:
                                if isolate:
                                    if self.claim_preamble(step_idx, source="stdout"):
                                        _ = self._emit_reasoning(step_idx or 0, suffix)
                                else:
                                    self.q.put(("text", suffix))
                    elif kind == "tool" and step.get("state") == "DONE":
                        step_idx = _as_int(step.get("step_index"))
                        trace: dict[str, object] = {
                            "name": str(step.get("tool_name") or "tool"),
                            "duration_s": step.get("duration_seconds"),
                            "step_index": step_idx,
                        }
                        if step_idx is None:
                            # Идентичность DONE без step_index: монотонный ordinal хода,
                            # назначается один раз и переживает повторную доставку события.
                            raw_id = (
                                step.get("call_id")
                                or step.get("tool_call_id")
                                or step.get("id")
                            )
                            call_id = str(raw_id).strip() if isinstance(raw_id, (str, int)) else ""
                            if call_id:
                                # Повтор события с тем же call_id получает тот же ordinal.
                                ord_val = tool_ordinal_by_id.get(call_id)
                                if ord_val is None:
                                    tool_ordinal += 1
                                    ord_val = tool_ordinal
                                    tool_ordinal_by_id[call_id] = ord_val
                                trace["fallback_ordinal"] = ord_val
                                trace["call_id"] = call_id
                            else:
                                tool_ordinal += 1
                                trace["fallback_ordinal"] = tool_ordinal
                        self.q.put(("tool_trace", trace))
                elif etype == "result":
                    result = (
                        ev.get("result") if isinstance(ev.get("result"), dict) else {}
                    )
                    result_ev = result
                    final_text = str(result.get("response") or "")
                    self.q.put(
                        (
                            "result",
                            {
                                "conversation_id": result.get("conversation_id") or "",
                                "status": str(result.get("status") or ""),
                                "error": str(result.get("error") or ""),
                                "duration_s": result.get("duration_seconds"),
                                "num_turns": result.get("num_turns"),
                                "usage": result.get("usage") or {},
                            },
                        )
                    )
            rc: int | None
            try:
                rc = self.proc.wait(timeout=PROC_EXIT_WAIT_S)
            except subprocess.TimeoutExpired:
                rc = None  # процесс ещё жив после EOF: добьёт Run.close
            time.sleep(0.05)  # дать стоку stderr дозавершиться
            t_exit = time.monotonic()
            self._drain_t0 = t_exit
            self._tail.drain_deadline = t_exit + DRAIN_WINDOW_S
            self._proc_done.set()
            self._join_source(t_exit)
            if rc is None:
                rc = 0 if result_ev else 1
            if (
                rc == 0
                and not final_text
                and not getattr(self, "_content_emitted_wire", "")
            ):
                step_accum = getattr(self, "_stdout_step_accum", None)
                if isinstance(step_accum, dict) and step_accum:
                    last_idx = next(reversed(step_accum))
                    tool_steps = getattr(self, "_tool_step_indices", None) or set()
                    tail_tools = (
                        getattr(
                            getattr(self, "_tail", None), "_tool_step_indices", None
                        )
                        or set()
                    )
                    if last_idx not in tool_steps and last_idx not in tail_tools:
                        fallback_accum = str(step_accum.get(last_idx) or "")
                        if fallback_accum:
                            final_text = fallback_accum
            term_kind = "done"
            term_payload = cast(object, (rc, final_text, result_ev))
        except Exception as exc:  # noqa: BLE001 — читатель не должен умирать молча
            self._stop_watch.set()
            term_kind = "pump_error"
            term_payload = repr(exc)
        finally:
            self._proc_done.set()
            self._close_and_put_done(term_kind, term_payload)

    def _join_source(self, t_exit: float) -> None:
        """Дождаться потока источника мышления в бюджете окна drain, затем прервать SELECT."""
        thread = self._tail.thread
        thread.join(timeout=max(0.0, t_exit + DRAIN_WINDOW_S - time.monotonic()))
        if not thread.is_alive():
            return
        self._tail.interrupt_active_query()
        thread.join(timeout=JOIN_TIMEOUT_S)
        if thread.is_alive():
            _count_drain_deadline()
            _log(f"drain-timeout cid={self._tail.cid[:8] or '-'}")

    def close(self) -> None:
        self._stop_watch.set()
        self._proc_done.set()
        self._tail.interrupt_active_query()
        self.controller.close()
        # Группа зачищается всегда: лидер мог выйти, оставив потомков (фоновые задачи agy).
        _kill_group(self.proc)
        with _active_lock:
            _active.pop(self.proc.pid, None)
        spawn_registered.unregister(self.proc)
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        thread = self._tail.thread
        if thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=JOIN_TIMEOUT_S)


def _reasoning_suffix(seen: dict, rid: str, text: str) -> str:
    """Новый хвост аккумулированного текста шага (`accum = prev + delta`) сверх уже отданного в `seen[rid]`.

    Пустой результат означает «нет прироста, не эмитить»."""
    prev = seen.get(rid, "")
    suffix = text[len(prev) :] if text.startswith(prev) else text
    seen[rid] = text
    return suffix


def _client_gone(sock: socket.socket) -> bool:
    try:
        ready, _, _ = select.select([sock], [], [], 0)
        return bool(ready) and sock.recv(1, socket.MSG_PEEK) == b""
    except (OSError, ValueError):
        return True


class _ByteBudget:
    """Резерв байт по заявленному Content-Length до чтения тела."""

    def __init__(self, total: int):
        self.total = total
        self.used = 0
        self.lock = threading.Lock()

    def reserve(self, amount: int) -> bool:
        with self.lock:
            if self.used + amount > self.total:
                return False
            self.used += amount
            return True

    def release(self, amount: int) -> None:
        with self.lock:
            self.used = max(0, self.used - amount)


# ---- Step-scoped usage: итоговое нормализованное usage попытки ---------------------------
# `result.usage` agy кумулятивен по всем вызовам модели хода: input_tokens бывает
# больше окна модели, и клиент (pi-ai) принимает успешный ход за overflow контекста.
# При step_scoped_usage_enabled prompt берётся из окна последнего шага транскрипта.


def _model_context_window(model_id: object) -> int | None:
    """Окно модели из fleet.json; None — нет модели или окно не положительный int."""
    info = FLEET_MODELS.get(model_id) if isinstance(model_id, str) else None
    window = info.get("context_window") if info is not None else None
    if isinstance(window, int) and not isinstance(window, bool) and window > 0:
        return window
    return None


def _raw_cache_tokens(raw: dict) -> tuple[int | None, bool]:
    """(cache_read, конфликт алиасов) из сырого usage: snake-ключ, иначе camel-ключ."""
    snake = raw.get("cache_read_tokens")
    camel = raw.get("cacheReadTokens")
    if snake is not None and camel is not None and snake != camel:
        return None, True  # алиасы расходятся: cache неизвестен, удобное не выбирается
    return _count_or_none(snake if snake is not None else camel), False


def _num_text(value: object) -> str:
    """Число для лога; всё остальное — `missing` (исходная строка не печатается)."""
    count = _count_or_none(value)
    return "missing" if count is None else str(count)


def _resolve_step_usage(
    out: dict, snap: _UsageSnapshot, window: int | None, resume: bool
) -> dict[str, object]:
    """Один неизменяемый wire-`usage` попытки; сырой `out["usage"]` не мутируется.

    Порядок: валидный последний шаг транскрипта (измеренное окно, без clamp) ->
    ограниченная оценка для успешного хода с накопительным raw выше окна ->
    result-only (input + cache, без clamp).
    """
    raw_obj = out.get("usage")
    raw = cast("dict[str, object]", raw_obj) if isinstance(raw_obj, dict) else {}
    raw_in = _count_or_none(raw.get("input_tokens"))
    raw_out = _count_or_none(raw.get("output_tokens"))
    raw_th = _count_or_none(raw.get("thinking_tokens"))
    raw_cache, conflict = _raw_cache_tokens(raw)
    details: dict[str, int] | None
    inconsistent = False
    reason = ""
    step_idx: int | None = None
    last = snap.last_step_usage
    if last is not None:
        source = "last_step"
        step_idx, last_in, last_cache, _last_out = last
        prompt = last_in + (last_cache if last_cache is not None else 0)
        details, inconsistent = normalize_prompt_cache_details(prompt, last_cache)
        if snap.completeness:
            completion = snap.turn_output_tokens_sum
        else:
            completion = 0
            reason = "ledger_incomplete"
            _log(
                "usage-step-ledger-incomplete observed_steps=%d saturated=%d "
                "invalid_records=%d raw_output=%s raw_thinking=%s"
                % (
                    snap.observed_planner_steps,
                    int(snap.observed_planner_steps_saturated),
                    snap.invalid_records_count,
                    _num_text(raw_out),
                    _num_text(raw_th),
                )
            )
    else:
        result_obj = out.get("result")
        result = cast("dict[str, object]", result_obj) if isinstance(result_obj, dict) else {}
        success = (
            out.get("rc") == 0
            and out.get("state") == "done"
            and str(result.get("status") or "").upper() != "ERROR"
            and not result.get("error")
        )
        cache_sum = raw_cache if raw_cache is not None else 0
        over_window = (
            window is not None
            and raw_in is not None
            and (raw_in >= window or raw_in + cache_sum > window)
        )
        if success and window is not None and raw_in is not None and over_window:
            source = "cumulative_estimate"
            turns = _count_or_none(out.get("num_turns")) or 0
            tools = _count_or_none(out.get("tool_events")) or 0
            divisor = max(2, turns + tools, snap.observed_planner_steps)
            prompt = min(raw_in // divisor, window - 1)
            reason = "over_window"
        else:
            source = "result"
            prompt = (raw_in or 0) + cache_sum
            reason = (
                "alias_conflict"
                if conflict
                else "not_success"
                if not success
                else "no_window"
                if window is None
                else "within_window"
            )
        details, inconsistent = normalize_prompt_cache_details(prompt, raw_cache)
        # Без ledger область raw output известна только у свежего разговора.
        if not resume and snap.observed_planner_steps == 0:
            completion = (raw_out or 0) + (raw_th or 0)
        else:
            completion = 0
        if source == "cumulative_estimate":
            _log(
                "usage-cumulative-fallback raw_in=%s raw_cache=%s window=%d n=%d "
                "prompt=%d turns=%d tools=%d observed_steps=%d inconsistent=%d "
                "raw_output=%s raw_thinking=%s"
                % (
                    _num_text(raw_in),
                    _num_text(raw_cache),
                    cast(int, window),
                    divisor,
                    prompt,
                    turns,
                    tools,
                    snap.observed_planner_steps,
                    int(inconsistent),
                    _num_text(raw_out),
                    _num_text(raw_th),
                )
            )
    wire: dict[str, object] = {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }
    if details is not None:
        wire["prompt_tokens_details"] = details
    return {
        "wire": wire,
        "source": source,
        "reason": reason,
        "step_idx": step_idx,
        "completeness": snap.completeness,
        "inconsistent": inconsistent,
        "cached": details["cached_tokens"] if details is not None else None,
        "raw_in": raw_in,
        "raw_out": raw_out,
        "raw_thinking": raw_th,
        "raw_total": _count_or_none(raw.get("total_tokens")),
        "raw_cache": raw_cache,
    }


def _usage_log_fields(resolved: object) -> str:
    """Числовая диагностика usage для строки done; пусто, если usage не нормализовался."""
    if not isinstance(resolved, dict):
        return ""
    info = cast("dict[str, object]", resolved)
    wire = cast("dict[str, object]", info.get("wire") or {})
    return (
        " usage_source=%s reason=%s step_idx=%s prompt=%s cached=%s completion=%s "
        "total=%s completeness=%d inconsistent=%d raw_in=%s raw_out=%s "
        "raw_thinking=%s raw_total=%s raw_cache=%s"
        % (
            _safe_log_value(str(info.get("source") or "")),
            _safe_log_value(str(info.get("reason") or "")) or "-",
            _num_text(info.get("step_idx")),
            _num_text(wire.get("prompt_tokens")),
            _num_text(info.get("cached")),
            _num_text(wire.get("completion_tokens")),
            _num_text(wire.get("total_tokens")),
            int(bool(info.get("completeness"))),
            int(bool(info.get("inconsistent"))),
            _num_text(info.get("raw_in")),
            _num_text(info.get("raw_out")),
            _num_text(info.get("raw_thinking")),
            _num_text(info.get("raw_total")),
            _num_text(info.get("raw_cache")),
        )
    )


def _image_fallback_view() -> tuple[dict[str, object], dict[str, bool]]:
    """Эффективная image-поддержка по каталогу и объект `image_fallback` для GET.

    universal -> поддержка = staging включён (для каждой модели каталога, proof не
    подделывается); иначе строгий `_model_supports_images`. Булевы `images` остаются
    булевыми, новая информация — только в отдельном объекте.
    """
    universal = _is_image_fallback_enabled()
    input_enabled = _is_image_input_enabled()
    effective = {
        mid: (input_enabled if universal else _model_supports_images(mid))
        for mid in FLEET_MODELS
    }
    if universal:
        acceptance = "optimistic" if input_enabled else "text-only"
    else:
        acceptance = "proof-gated"
    info: dict[str, object] = {
        "fallback_enabled": universal,
        "input_enabled": input_enabled,
        "mode": "universal" if universal else "strict",
        "acceptance": acceptance,
        "method": "workspace-read",
        "limits": dict(IMAGE_LIMITS),
        "models": [mid for mid, ok in effective.items() if ok],
    }
    return info, effective


def _terminal_state(name: str, err: str = "") -> dict[str, object]:
    """Итог хода без запуска agy (отказ до spawn)."""
    return {
        "state": name,
        "rc": 1,
        "text": "",
        "usage": {},
        "result": {},
        "err": err,
        "tool_calls": [],
        "tool_events": 0,
        "conversation_id": "",
        "num_turns": None,
        "duration_s": None,
    }


@_LIFECYCLE.install
class Handler(BaseHTTPRequestHandler):
    _registry_job: _Job | None = None
    protocol_version = "HTTP/1.1"
    server_version = "agy-bridge/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        del format, args

    def handle_error(self, request: Any, client_address: Any) -> None:
        return

    def _client_tag(self) -> str:
        try:
            return "%s:%s" % (self.client_address[0], self.client_address[1])
        except (TypeError, IndexError):
            return "-"

    def _send(self, code: int, payload: dict) -> None:
        if self._registry_job is not None:
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    # Дедлайн единого окна финальной записи (AD-004); None — обычный режим исполнения.
    _flush_deadline: float | None = None
    # Исходный таймаут сокета, сохранённый на время окна: окно не должно отравлять
    # следующий keep-alive запрос на том же соединении.
    _flush_socket_dirty: bool = False
    _saved_socket_timeout: float | None = None
    # Вход HTTP-запроса (monotonic): бюджет запроса считается до admission.
    _t_req_start: float | None = None

    def _arm_flush_window(self, ctx: dict) -> None:
        """Открыть окно T_FINAL_FLUSH_S: min(now + 5.0, t_req_start + T_REQ_BUDGET_S).

        Истёкший нативный дедлайн попытки окно не обнуляет и не сокращает.
        """
        deadline = time.monotonic() + T_FINAL_FLUSH_S
        t_req = ctx.get("t_req_start")
        if isinstance(t_req, (int, float)):
            deadline = min(deadline, float(t_req) + T_REQ_BUDGET_S)
        self._flush_deadline = deadline

    def _prepare_flush_write(self) -> bool:
        """Перед записью в окне: settimeout(min(5.0, остаток)); False — окно исчерпано."""
        deadline = self._flush_deadline
        if deadline is None:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return False
        if not self._flush_socket_dirty:
            get_to = getattr(self.connection, "gettimeout", None)
            self._saved_socket_timeout = get_to() if callable(get_to) else None
            self._flush_socket_dirty = True
        self.connection.settimeout(min(T_FINAL_FLUSH_S, remaining))
        return True

    def _reset_flush_window(self) -> None:
        """Закрыть окно финальной записи: дедлайн -> None, вернуть таймаут сокета."""
        self._flush_deadline = None
        if self._flush_socket_dirty:
            self._flush_socket_dirty = False
            saved = self._saved_socket_timeout
            self._saved_socket_timeout = None
            try:
                self.connection.settimeout(saved)
            except (OSError, ValueError, AttributeError):
                pass

    def _emit(self, data: str) -> bool:
        """Отправить SSE-строку; False — клиент ушёл или окно финальной записи исчерпано."""
        try:
            if not self._prepare_flush_write():
                return False
            self.wfile.write(data.encode("utf-8"))
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def _log_reject(
        self, reason: str, model: str = "unknown", model_len: int = 0
    ) -> None:
        _log(
            f"reject reason={reason} model={_safe_log_value(model)} "
            f"model_len={model_len} client={self._client_tag()}"
        )

    def _reject(
        self,
        code: int,
        reason: str,
        message: str,
        model: str = "unknown",
        model_len: int = 0,
    ) -> None:
        self._log_reject(reason, model, model_len)
        self._send(code, {"error": {"message": message, "type": reason, "code": code}})

    def _acquire_slot(self, keepalive) -> str:
        """Wait fairly using the semaphore interface and a separate queue deadline."""
        slots = _slots
        acquired = False

        def admitted() -> str:
            _maybe_checkpoint_sqlite_wal()
            return ""

        try:
            if self._registry_job is not None and self._registry_job.cancelled.is_set():
                return "client_gone"
            acquired = slots.acquire(blocking=False)
            if acquired:
                return admitted()
            deadline = time.monotonic() + QUEUE_TIMEOUT_S
            t_req_start = self._t_req_start
            if t_req_start is not None and _new_flag("extended_timeout_enabled"):
                deadline = min(deadline, t_req_start + T_REQ_BUDGET_S - T_RESERVE_S)
            while time.monotonic() < deadline:
                if (
                    self._registry_job is not None
                    and self._registry_job.cancelled.is_set()
                ):
                    return "client_gone"
                wait_s = min(1.0, max(0.0, deadline - time.monotonic()))
                acquired = slots.acquire(timeout=wait_s)
                if acquired:
                    return admitted()
                if keepalive is not None and not keepalive():
                    return "client_gone"
            return "queue_timeout"
        finally:
            if not acquired:
                getattr(slots, "cancel_wait", lambda: None)()

    def _execute(
        self,
        run: Run,
        on_text,
        on_tool_trace,
        on_reasoning,
        keepalive,
        turn_complete: Callable[[], bool] | None = None,
    ) -> dict:
        """Гнать ход до конца; сквозной таймаут TIMEOUT_S на весь ход.

        Колбэки возвращают False, если клиент ушёл. `turn_complete` (эмуляция tools)
        проверяется на каждой итерации: True — ход окончен (`done`,
        `tool_turn_stop`), фоновые задачи CLI не ждём, группу гасит `run.close()`.
        Превышение deadline -> kill группы (в run.close()), state=timeout.

        При extended_timeout_enabled (политика `run.policy`) действуют раздельные
        idle (по реальной активности producer'ов stdout/transcript, независимо от
        cpu_delta) и потолок `effective_max_timeout_s`; оба проверяются на каждой
        итерации, в том числе при непустой очереди. Выключение флага на лету
        возвращает legacy-дедлайн `run.started + TIMEOUT_S`.
        """
        pieces = []
        reasoning_pieces = []
        usage = {}
        result_ev = {}
        conversation_id = ""
        result_error = cleared_error = ""
        result_error_at = 0.0
        tool_events = 0
        last_ka = time.monotonic()
        last_wd_check = time.monotonic()
        deadline = time.monotonic() + TIMEOUT_S
        policy = getattr(run, "policy", None)
        content_streaming = bool(getattr(run, "content_streaming", False))
        usage_enabled = bool(getattr(run, "usage_enabled", False))
        gone = [False]

        def state(name: str, rc: int, err: str = "") -> dict:
            return {
                "rc": rc,
                "text": "".join(pieces),
                "reasoning": "".join(reasoning_pieces),
                "usage": usage,
                "result": result_ev,
                "state": name,
                "err": err,
                "conversation_id": conversation_id,
                "duration_s": result_ev.get("duration_s"),
                "num_turns": result_ev.get("num_turns"),
                "tool_events": tool_events,
                "tool_calls": [],
            }

        def add_content(text: str) -> None:
            if gone[0] or not text:
                return
            pieces.append(text)
            if not on_text(text):
                gone[0] = True

        def add_reasoning(text: str) -> None:
            if gone[0] or not text:
                return
            ok = on_reasoning(text)
            reasoning_pieces.append(text)
            # Диагностический след эмита мышления: что хвост добыл и дошло ли до клиента.
            _log(
                f"reasoning-emit cid={conversation_id[:8] or '-'} "
                f"n={len(reasoning_pieces)} len={len(text)} ok={int(bool(ok))}"
            )
            if not ok:
                gone[0] = True

        def deliver(events: list) -> None:
            nonlocal tool_events
            for kind, payload in events:
                if gone[0]:
                    break
                if kind == "text":
                    add_content(str(payload))
                elif kind == "reasoning":
                    add_reasoning(str(payload))
                elif kind == "tool_trace":
                    tool_events += 1
                    if not on_tool_trace(payload):
                        gone[0] = True

        def finish(name: str, rc: int, err: str = "", limit: float | None = None) -> dict:
            """Терминальное состояние с bounded drain (<= T_DRAIN_MAX_S) остатка источников.

            timeout/idle_timeout при graceful: остаток откладывается в `retained_events`
            (доставка и notice — в окне финальной записи). Иначе остаток уходит сразу.
            """
            retained: list = []
            drain = getattr(run, "terminal_drain", None)
            graceful = name in (
                "timeout",
                "idle_timeout",
            ) and _new_flag("graceful_timeout_on_partial")
            if drain is not None and (
                graceful
                or (
                    content_streaming
                    and name in ("timeout", "idle_timeout", "agy_error", "pump_error")
                )
            ):
                retained = list(drain(T_DRAIN_MAX_S))
                if not graceful:
                    deliver(retained)
                    retained = []
            out = state(name, rc, err)
            if limit is not None:
                out["timeout_limit_s"] = limit
            if retained:
                out["retained_events"] = retained
                out["retained_planner_text"] = "".join(
                    str(payload) for kind, payload in retained if kind == "text"
                )
            divergent = getattr(run, "retained_divergent_text", None)
            div_text = divergent() if callable(divergent) else ""
            if isinstance(div_text, str) and div_text:
                out["retained_divergent_text"] = div_text
                if (graceful or content_streaming) and not out.get(
                    "retained_planner_text"
                ):
                    out["retained_planner_text"] = div_text
            return out

        while True:
            if turn_complete is not None and run.q.empty() and turn_complete():
                stopped = state("done", 0)
                stopped["tool_turn_stop"] = True
                return stopped
            now = time.monotonic()
            ext = policy is not None and _new_flag("extended_timeout_enabled")
            if ext:
                cap = policy.effective_max_timeout_s
                if now - run.started >= cap:
                    return finish("timeout", 124, f"proxy timeout after {cap:g}s", cap)
                last_progress = max(
                    run.started,
                    getattr(run, "last_producer_activity_ts", run.started),
                )
                if now - last_progress >= policy.idle_timeout_s:
                    return finish(
                        "idle_timeout",
                        124,
                        f"proxy idle timeout after {policy.idle_timeout_s:g}s "
                        "(no stdout/transcript progress)",
                        policy.idle_timeout_s,
                    )
                # Прогресс transcript — тоже «первое событие upstream», keepalive моста — нет.
                no_first_event = (
                    not run.got_event
                    and getattr(run, "transcript_activity_ts", None) is None
                )
            else:
                limit_at = run.started + TIMEOUT_S if policy is not None else deadline
                if now > limit_at:
                    return finish(
                        "timeout",
                        124,
                        f"proxy timeout after {TIMEOUT_S}s",
                        float(TIMEOUT_S),
                    )
                no_first_event = not run.got_event
            if no_first_event and now - run.started > FIRST_TOKEN_TIMEOUT_S:
                return state(
                    "first_token_timeout",
                    124,
                    f"no agy event within {FIRST_TOKEN_TIMEOUT_S:g}s",
                )
            if self._job_client_gone():
                return state("client_gone", 1)
            if (
                result_error
                and time.monotonic() - result_error_at > RESULT_EXIT_GRACE_S
            ):
                # agy прислал result ERROR, но не завершился: ждать done бесконечно нельзя.
                return finish("agy_error", 1, result_error)
            try:
                kind, payload = run.q.get(timeout=1.0)
            except queue.Empty:
                # check() запускает `ps`: не чаще WATCHDOG_INTERVAL_S. Пока идут события,
                # on_activity() и так сбрасывает таймер, поэтому пропуск безопасен.
                now = time.monotonic()
                if not ext and now - last_wd_check >= WATCHDOG_INTERVAL_S:
                    last_wd_check = now
                    should_stop, wd_reason, _metrics = run.controller.check(
                        run.proc.pid
                    )
                    if should_stop and wd_reason == "idle_timeout":
                        _log(
                            f"watchdog idle_timeout pgid={run.proc.pid} "
                            f"idle>={IDLE_TIMEOUT_S:g}s"
                        )
                        return finish(
                            "idle_timeout",
                            124,
                            f"proxy idle timeout after {IDLE_TIMEOUT_S:g}s "
                            "(no activity in process group)",
                            float(IDLE_TIMEOUT_S),
                        )
                    if should_stop and wd_reason == "absolute_cap":
                        return finish(
                            "timeout",
                            124,
                            f"proxy timeout after {TIMEOUT_S}s",
                            float(TIMEOUT_S),
                        )
                    # wd_reason == "child_exited": штатно, "done"/"pump_error" придут из очереди
                if keepalive is not None and time.monotonic() - last_ka >= KEEPALIVE_S:
                    last_ka = time.monotonic()
                    if not keepalive():
                        return state("client_gone", 1)
                continue
            if kind in _ACTIVITY_KINDS:
                run.controller.on_activity(kind)
                if result_error:
                    if is_transient_stream_interruption(result_error):
                        cleared_error, result_error, result_error_at = result_error, "", 0.0
            if kind == "init":
                conversation_id = str(payload.get("conversation_id") or "")
                _log(
                    f"init conversation={conversation_id[:8] or '-'} "
                    f"tools={payload.get('tools')} "
                    f"permission_mode={payload.get('permission_mode')}"
                )
            elif kind == "reasoning":
                add_reasoning(str(payload))
                if gone[0]:
                    return state("client_gone", 1)
            elif kind == "text":
                add_content(str(payload))
                if gone[0]:
                    return state("client_gone", 1)
            elif kind == "tool_trace":
                tool_events += 1
                if not on_tool_trace(payload):
                    gone[0] = True
                    return state("client_gone", 1)
            elif kind == "result":
                result_ev = payload
                usage = payload.get("usage") or {}
                conversation_id = str(payload.get("conversation_id") or conversation_id)
                if str(payload.get("status") or "").upper() == "ERROR":
                    # Не выходим по result ERROR: мышление последнего шага ещё в очереди
                    # перед done, и оно обязано попасть в out до решения о повторе.
                    message = str(payload.get("error") or "agy reported an error")
                    result_error = message[:500]
                    result_error_at = time.monotonic()
            elif kind == "pump_error":
                return finish("pump_error", 1, str(payload))
            elif kind == "done":
                rc, final_text, raw_result = payload
                if not result_ev and raw_result:
                    result_ev = raw_result
                status = str(result_ev.get("status", "")).upper()
                tail = getattr(run, "_tail", None)
                result_error = settle_error(result_error, cleared_error, status)
                if content_streaming or usage_enabled:
                    # Хвост транскрипта, записанный прямо перед done, дренируется
                    # ДО reconcile: result.response — агрегат, досылается лишь недостающее.
                    # При usage_enabled тот же drain — барьер счётчиков шагов (единый
                    # дедлайн попытки <= T_DRAIN_MAX_S, второго окна нет).
                    drain = getattr(run, "terminal_drain", None)
                    if callable(drain):
                        deliver(list(drain(T_DRAIN_MAX_S)))
                final_text = trusted_final_text(final_text, result_error, tail)
                if content_streaming:
                    delta = run.reconcile_result(final_text)
                    if delta:
                        add_content(delta)
                    elif final_text and getattr(
                        run._arbiter, "last_result_diverged", False
                    ):
                        full_emitted = "".join(pieces)
                        sep = (
                            "\n\n"
                            if full_emitted and not full_emitted.endswith("\n")
                            else (
                                "\n"
                                if full_emitted and not full_emitted.endswith("\n\n")
                                else ""
                            )
                        )
                        _log(
                            f"content-reconcile-fallback "
                            f"turn={getattr(run, 'turn_id', '')[:8] or '-'} "
                            f"len={len(final_text)}"
                        )
                        add_content(sep + final_text if full_emitted else final_text)
                elif not pieces and final_text:
                    add_content(final_text)
                res = resolve_done_turn_outcome(
                    rc=rc,
                    result_error=result_error,
                    result_status=status,
                    final_text=final_text,
                    emitted_text="".join(pieces),
                    self_heal_enabled=_new_flag("self_heal_interrupted_turn", True),
                    **tail_turn_facts(tail, cleared_error),
                )
                if res.final:
                    _log(f"turn-resolved reason={res.reason} state={res.state}")
                    return state(res.state, res.rc, res.error)
                if gone[0]:
                    return state("client_gone", 1)
                time.sleep(0.05)
                err = "".join(run.err_box).strip()
                if rc != 0 and (status == "ERROR" or not pieces):
                    return state(
                        "agy_error",
                        rc,
                        (str(result_ev.get("error") or "") or err)[:500],
                    )
                return state("done", rc, err)

    @staticmethod
    def _attach_resolved_usage(run: object, out: dict, model: object) -> None:
        """Финальный выбор формы usage один раз на попытку, после terminal drain.

        Флаг выключен на финализации — usage остаётся прежним (legacy). Иначе
        `out["usage_resolved"]` — единый источник для лога, JSON и SSE.
        """
        if not _new_flag("step_scoped_usage_enabled"):
            return
        getter = getattr(run, "usage_snapshot", None)
        snap = getter() if callable(getter) else _EMPTY_USAGE_SNAPSHOT
        if not isinstance(snap, _UsageSnapshot):
            snap = _EMPTY_USAGE_SNAPSHOT
        resume = bool(getattr(run, "run_cid", ""))
        out["usage_resolved"] = _resolve_step_usage(out, snap, _model_context_window(model), resume)

    def _log_done(self, model: str, out: dict[str, object], t0: float, tag: str) -> None:
        """Одна строка done на каждом выходе _run_once (O-EXIT)."""
        conversation = str(out.get("conversation_id") or "-")[:8]
        out_bytes = len(str(out.get("text") or "").encode())
        _log(
            f"done model={model} rc={out.get('rc')} state={out.get('state')} "
            f"conversation={conversation} "
            f"turns={out.get('num_turns')} tool_events={out.get('tool_events')} "
            f"out_bytes={out_bytes} "
            f"wall_s={time.monotonic() - t0:.1f}"
            f"{_usage_log_fields(out.get('usage_resolved'))} "
            f"err={_err_summary(out.get('err'))!r} {tag}"
        )

    def _job_client_gone(self) -> bool:
        job = getattr(self, "_registry_job", None)
        return (
            job.cancelled.is_set() if job is not None else _client_gone(self.connection)
        )

    def _run_once(
        self, ctx: dict, on_text, on_tool_trace, on_reasoning, keepalive
    ) -> dict:
        key = str(ctx.get("step_job_id") or "")
        if not key:
            return self._run_once_impl(
                ctx, on_text, on_tool_trace, on_reasoning, keepalive
            )
        registry = _JOB_REGISTRY
        try:
            job, owner = registry.attach(
                key, str(ctx["model"]), str(ctx["full_prompt"])
            )
        except JobConflict:
            return {"state": "job_conflict", "text": "", "rc": 1}
        if owner:
            worker = copy.copy(self)
            worker._registry_job = job
            worker_ctx = dict(ctx)
            worker_ctx.pop("finalize_timeout", None)

            def produce() -> None:
                try:
                    out = worker._run_once_impl(
                        worker_ctx,
                        lambda value: registry.publish(job, "text", value),
                        lambda value: registry.publish(job, "tool_trace", value),
                        lambda value: registry.publish(job, "reasoning", value),
                        lambda: not job.cancelled.is_set(),
                    )
                except Exception as exc:
                    _log(f"job-producer-error err={type(exc).__name__}")
                    out = {"state": "pump_error", "text": "", "rc": 1}
                try:
                    registry.finish(job, out)
                finally:
                    use_cid = str(worker_ctx.get("registry_use_cid") or "")
                    if use_cid:
                        with _session_store_lock:
                            _in_flight_cids.discard(use_cid)
                    _cid_release(
                        use_cid or str(worker_ctx.get("registry_owned_cid") or ""),
                        str(worker_ctx.get("turn_id") or ""),
                    )

            ctx["job_owns_cid"] = True
            try:
                threading.Thread(target=produce, daemon=True, name="agy-job").start()
            except RuntimeError:
                ctx["job_owns_cid"] = False
                registry.finish(job, {"state": "pump_error", "text": "", "rc": 1})
        offset = 0
        heartbeat = _env_float(
            "BRIDGE_SSE_HEARTBEAT_INTERVAL_S", 12.0, 0.001, float("inf")
        )
        last_delivery = time.monotonic()
        try:
            while True:
                if _client_gone(self.connection):
                    return {"state": "client_gone", "text": "", "rc": 1}
                events, out = registry.read(
                    job, offset, min(heartbeat, TRANSCRIPT_POLL_S)
                )
                for kind, payload in events:
                    callback = {
                        "text": on_text,
                        "reasoning": on_reasoning,
                        "tool_trace": on_tool_trace,
                    }[kind]
                    if callback is not None and not callback(payload):
                        return {"state": "client_gone", "text": "", "rc": 1}
                    offset += 1
                    last_delivery = time.monotonic()
                if out is not None:
                    return out
                if time.monotonic() - last_delivery >= heartbeat:
                    if keepalive is not None and not keepalive():
                        return {"state": "client_gone", "text": "", "rc": 1}
                    last_delivery = time.monotonic()
        finally:
            registry.detach(job)

    def _run_once_impl(
        self, ctx: dict, on_text, on_tool_trace, on_reasoning, keepalive
    ) -> dict:
        if "stream_resilience_enabled" not in ctx:
            ctx["stream_resilience_enabled"] = _new_flag(
                "AGY_BRIDGE_STREAM_RESILIENCE_ENABLED", True
            )
        model = ctx["model"]
        effort = ctx["effort"]
        tag = ctx["tag"]
        t_enter = time.monotonic()
        # Бюджет запроса считается от входа HTTP-запроса, до ожидания admission.
        raw_req_start = ctx.get("t_req_start")
        t_req_start = (
            float(raw_req_start) if isinstance(raw_req_start, (int, float)) else t_enter
        )
        self._t_req_start = t_req_start
        reason = self._acquire_slot(keepalive)
        if reason:
            _log(f"no slot ({reason}) model={model} {tag}")
            if reason == "queue_timeout":
                self._log_reject("overloaded", model, ctx["model_len"])
            early: dict[str, object] = {
                "state": reason,
                "rc": 1,
                "text": "",
                "usage": {},
                "result": {},
                "err": "",
                "tool_calls": [],
                "tool_events": 0,
                "conversation_id": "",
                "num_turns": None,
                "duration_s": None,
            }
            self._log_done(
                cast(str, ctx["model"]), early, t_enter, cast(str, ctx["tag"])
            )
            return early
        t0 = time.monotonic()
        out: dict = {}
        typed_ctx = cast("dict[str, object]", ctx)
        images = cast("list[dict[str, object]]", typed_ctx.get("images") or [])
        img_dir = cast("Path | None", typed_ctx.get("img_dir")) if images else None
        img_registered = False
        try:
            try:
                _launcher()
            except LauncherUnavailable:
                self._log_reject("launcher_unavailable", model, ctx["model_len"])
                unavailable: dict[str, object] = {
                    "state": "launcher_unavailable",
                    "rc": 1,
                    "text": "",
                    "usage": {},
                    "result": {},
                    "err": "",
                    "tool_calls": [],
                    "tool_events": 0,
                    "conversation_id": "",
                    "num_turns": None,
                    "duration_s": None,
                }
                self._log_done(
                    cast(str, ctx["model"]), unavailable, t_enter, cast(str, ctx["tag"])
                )
                return unavailable
            universal = bool(typed_ctx.get("universal_fallback"))
            if images and img_dir is not None:
                if universal and not _is_image_input_enabled():
                    # Staging выключили, пока ход ждал слот: media не отправляем,
                    # ход идёт текстом (без mkdir и --add-dir).
                    _downgrade_to_text_in_run_once(
                        typed_ctx, "post_slot", "flag_disabled", 1, img_dir
                    )
                    images = []
                    img_dir = None
                else:
                    # Флаг и proof могли смениться, пока ход ждал слот: повторная
                    # проверка до mkdir и spawn (universal — только флаг, выше).
                    gate = None if universal else _image_gate(cast(str, model), cast(str, effort))
                    if gate is not None:
                        self._log_reject(
                            gate.code, cast(str, model), cast(int, ctx["model_len"])
                        )
                        rejected = _terminal_state("image_reject", gate.code)
                        self._log_done(
                            cast(str, ctx["model"]),
                            rejected,
                            t_enter,
                            cast(str, ctx["tag"]),
                        )
                        return rejected
                    # Реестр активных каталогов ПЕРЕД mkdir: sweep не тронет живой ход.
                    with _active_lock:
                        _active_img_dirs.add(str(img_dir))
                    img_registered = True
                    try:
                        _stage_images(img_dir, images)
                    except ImageSpoolError as exc:
                        _log(
                            "image_spool_error model=%s err=%s"
                            % (_safe_log_value(cast(str, model)), exc)
                        )
                        if not universal:
                            failed = _terminal_state("image_spool_error", str(exc))
                            self._log_done(
                                cast(str, ctx["model"]),
                                failed,
                                t_enter,
                                cast(str, ctx["tag"]),
                            )
                            return failed
                        _downgrade_to_text_in_run_once(
                            typed_ctx, "spool", "image_spool_error", 1, img_dir
                        )
                        images = []
                        img_dir = None
                        img_registered = False
            _retry_credit()
            for attempt in (1, 2):
                if (
                    self._registry_job is not None
                    and self._registry_job.cancelled.is_set()
                ):
                    out = _terminal_state("client_gone")
                    break
                policy = _build_timeout_policy(t_req_start)
                if policy is not None and not policy.can_start:
                    # Бюджет запроса исчерпан: новой попытки нет, остаток не перезапускается.
                    _log(f"request-budget-exhausted attempt={attempt} {tag}")
                    if attempt == 1:
                        out = {
                            "state": "timeout",
                            "rc": 124,
                            "text": "",
                            "usage": {},
                            "result": {},
                            "err": "request budget exhausted before the first attempt",
                            "tool_calls": [],
                            "tool_events": 0,
                            "conversation_id": "",
                            "num_turns": None,
                            "duration_s": None,
                            "timeout_limit_s": policy.max_timeout_s,
                        }
                    break
                _log(
                    f"exec model={model} effort={effort} effort_source={ctx['effort_source']} "
                    f"prompt_bytes={len(ctx['prompt'].encode())} "
                    f"tools={ctx['tools_count']} resume={1 if ctx.get('conversation_id') else 0} "
                    f"sess={'agentic' if ctx.get('sess_key') else 'plain'} {tag}"
                )
                try:
                    run = Run(
                        ctx["prompt"],
                        model,
                        effort,
                        ctx["effort_source"],
                        ctx["cwd"],
                        tag,
                        conversation_id=ctx.get("conversation_id") or "",
                        turn_id=str(ctx.get("turn_id") or ""),
                        policy=policy,
                        add_dir=img_dir if images else None,
                        **({"mode": ctx["agy_mode"]} if "agy_mode" in ctx else {}),
                    )
                except LauncherUnavailable:
                    self._reject(
                        503,
                        "launcher_unavailable",
                        "canonical launcher is missing or not executable",
                        model=model,
                        model_len=ctx["model_len"],
                    )
                    out = {
                        "state": "launcher_unavailable",
                        "rc": 1,
                        "text": "",
                        "usage": {},
                        "result": {},
                        "err": "",
                        "tool_calls": [],
                        "tool_events": 0,
                        "conversation_id": "",
                        "num_turns": None,
                        "duration_s": None,
                    }
                    break
                except OSError as exc:
                    out = {
                        "state": "pump_error",
                        "rc": 1,
                        "text": "",
                        "usage": {},
                        "result": {},
                        "err": repr(exc),
                        "tool_calls": [],
                        "tool_events": 0,
                        "conversation_id": "",
                        "num_turns": None,
                        "duration_s": None,
                    }
                    break
                job = getattr(self, "_registry_job", None)
                if job is not None:
                    _JOB_REGISTRY.bind_cancel(job, lambda: _kill_group(run.proc))
                stop_hook = ctx.get("tool_stop")
                try:
                    out = self._execute(
                        run,
                        on_text,
                        on_tool_trace,
                        on_reasoning,
                        keepalive,
                        **(
                            {"turn_complete": stop_hook}
                            if stop_hook is not None
                            else {}
                        ),
                    )
                    self._attach_resolved_usage(run, out, model)
                    finalize = ctx.get("finalize_timeout")
                    if finalize is not None and out.get("state") in (
                        "timeout",
                        "idle_timeout",
                        "agy_error",
                        "pump_error",
                    ):
                        # Graceful-финал пишется ДО зачистки процесса: kill/reap не
                        # съедает окно финальной записи. Внутренний state/rc не меняются.
                        try:
                            finalize(out)
                        except Exception as exc:  # noqa: BLE001
                            _log(f"graceful-finalize-error err={type(exc).__name__}")
                finally:
                    run.close()
                    if job is not None:
                        _JOB_REGISTRY.bind_cancel(job, None)
                if out["state"] == "done":
                    break
                # Выдача клиенту: текст, tool_calls или уже отданное в поток мышление.
                # JSON-режим мышление клиенту ещё не отдавал — там повтор безопасен.
                typed_out = cast("dict[str, object]", out)
                delivered_reasoning = bool(
                    typed_out.get("delivered_reasoning")
                ) or bool(typed_ctx.get("stream") and typed_out.get("reasoning"))
                delivered = bool(
                    typed_out.get("text")
                    or typed_out.get("tool_calls")
                    or delivered_reasoning
                )
                if ctx["stream_resilience_enabled"]:
                    # Commit запрещает невидимый повтор даже при пустом out;
                    # нативные инструменты могли изменить данные без tool_calls.
                    delivered = delivered or bool(
                        ctx.get("stream_committed")
                        or ctx.get("tool_activity")
                        or typed_out.get("tool_events")
                    )
                if (
                    attempt == 1
                    and universal
                    and images
                    and img_dir is not None
                    and out["state"] not in ("done", "client_gone")
                    and not delivered
                ):
                    # Реальная image-попытка упала без выдачи: один text-only повтор
                    # ДО обеих legacy-веток (hot continue и transient). Один токен
                    # бюджета, если есть; иначе — разовый резерв деградации запроса.
                    _downgrade_to_text_in_run_once(
                        typed_ctx,
                        "runtime",
                        _log_token(typed_out.get("state")),
                        attempt,
                        img_dir,
                    )
                    images = []
                    img_dir = None
                    img_registered = False
                    if not _retry_take():
                        _log(f"media-degradation-reserve state={out['state']} {tag}")
                    time.sleep(_retry_pause_s(attempt))
                    continue
                if (
                    ctx.get("hot_resumed")
                    and AGY_BRIDGE_ENABLE_TRANSIENT_502_RECOVERY
                    and out["state"] in ("agy_error", "pump_error")
                    and not delivered
                    and _is_transient_upstream_error(out.get("err"))
                ):
                    # Сбой upstream (502/503/сеть), а не разговора: сессия не
                    # инвалидируется, lease cid остаётся в _in_flight_cids до finally
                    # HTTP-хендлера, повтор идёт в тот же conversation_id.
                    if attempt == 2 or not _retry_take():
                        if attempt != 2:
                            _log(f"retry-budget-exhausted state={out['state']} {tag}")
                        # Повторы исчерпаны: сломанная сессия не достаётся следующим ходам.
                        _session_invalidate(ctx["sess_key"], ctx["conversation_id"])
                        break
                    _log(
                        f"transient upstream err={_err_summary(out.get('err'), 120)!r}, "
                        f"hot retry same cid={str(ctx['conversation_id'])[:8]} {tag}"
                    )
                    time.sleep(_retry_pause_s(attempt))
                    continue
                if ctx.get("hot_resumed") and out["state"] != "client_gone":
                    # Горячая сессия сломалась: больше её не используем, а повтор
                    # идёт холодным вызовом с полной историей.
                    _session_invalidate(ctx["sess_key"], ctx["conversation_id"])
                    _cid_release(
                        str(ctx["conversation_id"]), str(ctx.get("turn_id") or "")
                    )
                    ctx["hot_resumed"] = False
                    ctx["conversation_id"] = ""
                    ctx["prompt"] = ctx["full_prompt"]
                    if out["state"] == "agy_error" and not delivered:
                        if not _retry_take():
                            _log(f"retry-budget-exhausted state={out['state']} {tag}")
                            break
                        _log(
                            f"hot session failed err={_err_summary(out.get('err'), 120)!r}, "
                            f"cold fallback {tag}"
                        )
                        continue
                # Транзиентный сбой до выдачи клиенту — один невидимый повтор.
                transient = (
                    out["state"] in ("agy_error", "pump_error", "done")
                    and not delivered
                )
                if not transient or attempt == 2:
                    break
                if not _retry_take():
                    _log(f"retry-budget-exhausted state={out['state']} {tag}")
                    break
                _log(
                    f"transient failure state={out['state']} rc={out.get('rc')} "
                    f"err={_err_summary(out.get('err'), 120)!r}, retry {attempt} {tag}"
                )
                time.sleep(_retry_pause_s(attempt))
            if out.get("tool_turn_stop"):
                # Ход прерван после <tool_call>: разговор agy не завершён штатно и
                # горячей сессией не служит (следующий ход — холодный, с историей).
                if ctx.get("hot_resumed"):
                    _session_invalidate(ctx["sess_key"], str(ctx["conversation_id"]))
            elif (
                out.get("state") == "done"
                and out.get("conversation_id")
                and ctx.get("sess_key")
            ):
                _session_commit(ctx["sess_key"], str(out["conversation_id"]))
            if out.get("state") != "client_gone":
                _last_ok[0] = (
                    time.monotonic()
                    if (out.get("state") == "done" and out.get("rc") == 0)
                    else 0.0
                )
        finally:
            # Каталог изображений живёт весь ход (все попытки) и уходит до слота.
            if img_registered and img_dir is not None:
                _cleanup_img_dir(img_dir)
            _slots.release()
        self._log_done(
            cast(str, ctx["model"]),
            cast("dict[str, object]", out),
            t0,
            cast(str, ctx["tag"]),
        )
        return out

    @staticmethod
    def _usage_payload(usage: dict, resolved: object = None) -> dict:
        """usage agy -> OpenAI-поля. thinking_tokens прибавляем к completion.

        `resolved` — итог `_resolve_step_usage` (флаг включён): одна и та же форма
        для JSON и SSE; без него — прежнее отображение сырого usage.
        """
        if isinstance(resolved, dict):
            wire = cast("dict[str, object]", resolved).get("wire")
            if isinstance(wire, dict):
                return dict(cast("dict[str, object]", wire))
        return {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0)
            + usage.get("thinking_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    @staticmethod
    def _error_body(out: dict, resilience: bool | None = None) -> Any:
        st = out.get("state")
        if st in ("job_conflict", "buffer_overflow", "orphan_limit"):
            return {
                "message": str(st),
                "type": str(st),
                "code": 409 if st == "job_conflict" else 502,
            }
        limit = out.get("timeout_limit_s")
        has_limit = isinstance(limit, (int, float))
        if st == "timeout":
            shown = f"{limit:g}" if has_limit else str(TIMEOUT_S)
            return {
                "message": f"agy timed out after {shown}s",
                "type": "timeout",
                "code": 504,
            }
        if st == "idle_timeout":
            shown = f"{limit:g}" if has_limit else f"{IDLE_TIMEOUT_S:g}"
            return {
                "message": f"agy execution idle timeout after {shown}s "
                "(no activity or progress in process group)",
                "type": "idle_timeout",
                "code": 504,
            }
        if st == "first_token_timeout":
            return {
                "message": f"first_token_timeout: agy gave no event within "
                f"{FIRST_TOKEN_TIMEOUT_S:g}s",
                "type": "first_token_timeout",
                "code": 504,
            }
        if st == "queue_timeout":
            return {
                "message": f"bridge busy: queue full over {QUEUE_TIMEOUT_S}s",
                "type": "overloaded",
                "code": 503,
            }
        if st == "launcher_unavailable":
            return {
                "message": "canonical launcher is missing or not executable",
                "type": "launcher_unavailable",
                "code": 503,
            }
        if st == "client_gone":
            return {"message": "client gone", "type": "client_gone", "code": 499}
        if st == "image_reject":
            code = cast(str, out["err"]) or "image_input_not_supported"
            return {"message": f"image rejected: {code}", "type": code, "code": 400}
        if st == "image_spool_error":
            return {
                "message": "image spool failed",
                "type": "image_spool_error",
                "code": 500,
            }
        if st == "pump_error":
            return {
                "message": "bridge reader failed",
                "detail": str(out.get("err"))[:500],
                "type": "proxy_error",
                "code": 502,
            }
        if st == "agy_error":
            return {
                "message": str(out.get("err") or "agy reported an error")[:500],
                "type": "agy_error",
                "code": 502,
            }
        if resilience is None:
            resilience = _new_flag("AGY_BRIDGE_STREAM_RESILIENCE_ENABLED", True)
        has_payload = bool(out.get("text"))
        if resilience:
            has_payload = bool(
                out.get("text")
                or out.get("reasoning")
                or out.get("tool_events")
                or out.get("result")
            )
        if out.get("rc") != 0 or not has_payload:
            return {
                "message": f"agy exited rc={out.get('rc')}",
                "detail": str(out.get("err"))[:500],
                "type": "proxy_error",
                "code": 502,
            }
        return None

    # ---- HTTP --------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/v1/health"):
            with _active_lock:
                active = len(_active)
            fallback_info, effective = _image_fallback_view()
            health: dict[str, object] = {
                "ok": True,
                "transport": "agy-stream-json",
                "model": MODEL_ID,
                "active": active,
                "max_concurrent": MAX_CONCURRENT,
                "hot_sessions": len(_session_store),
                "tool_emulation": False,
                "tool_translation": False,
                "native_tools": True,
                "images": any(effective.values()),
                "image_fallback": fallback_info,
                "image_input_mode": (
                    "enabled" if _is_image_input_enabled() else "disabled"
                ),
                "uptime_s": int(time.time() - _started),
            }
            health.update(_sqlite_health_fields())
            self._send(200, health)
            return
        if not _auth_ok(self):
            self._send(
                401,
                {
                    "error": {
                        "message": "unauthorized",
                        "type": "auth_error",
                        "code": 401,
                    }
                },
            )
            return
        if path in ("/v1/models", "/models"):
            data = []
            order = _catalog_model_order()
            image_flags: list[bool] = []
            fallback_info, effective = _image_fallback_view()
            for mid in order:
                model = FLEET["models"][mid]
                supports = effective[cast(str, mid)]
                image_flags.append(supports)
                data.append(
                    {
                        "id": mid,
                        "object": "model",
                        "owned_by": "antigravity",
                        "created": 0,
                        "context_length": model["context_window"],
                        "images": supports,
                    }
                )
            self._send(
                200,
                {
                    "object": "list",
                    "data": data,
                    "images": any(image_flags),
                    "image_fallback": fallback_info,
                },
            )
            return
        self._send(
            404,
            {
                "error": {
                    "message": f"not found: {path}",
                    "type": "not_found",
                    "code": 404,
                }
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        t_req_start = time.monotonic()  # старт бюджета запроса: до admission
        if not _auth_ok(self):
            # Непрочитанное тело иначе будет разобрано как следующий запрос keep-alive.
            self.close_connection = True
            self._send(
                401,
                {
                    "error": {
                        "message": "unauthorized",
                        "type": "auth_error",
                        "code": 401,
                    }
                },
            )
            return
        if self.headers.get_all("Transfer-Encoding") is not None:
            self._reject(400, "invalid_request", "Transfer-Encoding is not supported")
            return
        content_lengths = self.headers.get_all("Content-Length")
        length = 0
        if content_lengths is not None:
            values = [str(v).strip() for v in content_lengths]
            if len(set(values)) != 1 or not re.fullmatch(r"[0-9]+", values[0]):
                self._reject(400, "invalid_request", "invalid Content-Length")
                return
            length = int(values[0])
        if length > int((FLEET.get("image_limits") or {}).get("max_body_bytes") or 0):
            self._reject(
                413, "payload_too_large", "request body exceeds the bridge limit"
            )
            return
        reserved = 0
        budget = _budget
        if budget is not None and length:
            if not budget.reserve(length):
                self._reject(
                    503, "overloaded", "bridge overloaded: body budget exhausted"
                )
                return
            reserved = length
        use_cid = ""
        owned_cid = ""
        ctx: dict[str, object] = {}
        turn_id = uuid.uuid4().hex
        try:
            raw = self.rfile.read(length) if length else b""
            if len(raw) < length:
                self._reject(400, "invalid_request", "request body truncated")
                return
            try:
                req = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._reject(400, "invalid_request", "invalid json")
                return
            if not isinstance(req, dict):
                self._reject(400, "invalid_request", "request must be a JSON object")
                return
            path = self.path.split("?", 1)[0]
            if path not in ("/v1/chat/completions", "/chat/completions"):
                self.close_connection = True
                self._send(
                    404,
                    {
                        "error": {
                            "message": f"not found: {path}",
                            "type": "not_found",
                            "code": 404,
                        }
                    },
                )
                return
            raw_model = req.get("model")
            model_len = len(raw_model) if isinstance(raw_model, str) else 0
            if raw_model is None:
                model_id = MODEL_ID
            elif isinstance(raw_model, str):
                candidate = raw_model.strip()
                model_id = candidate if candidate else MODEL_ID
            else:
                self._reject(
                    400,
                    "model_not_allowed",
                    "model must be a string from the catalogue",
                    "unknown",
                    model_len,
                )
                return
            if model_id not in FLEET["models"]:
                self._reject(
                    400,
                    "model_not_allowed",
                    "model is not in the catalogue",
                    "unknown",
                    model_len,
                )
                return
            model = FLEET["models"][model_id]
            raw_effort = req.get("reasoning_effort")
            if raw_effort is None:
                effort = model["default_effort"]
                effort_source = "default"
            elif isinstance(raw_effort, str):
                candidate = raw_effort.strip()
                if not candidate:
                    effort = model["default_effort"]
                    effort_source = "default"
                elif candidate in model["efforts"]:
                    effort = candidate
                    effort_source = "request"
                else:
                    self._reject(
                        400,
                        "unsupported_reasoning_effort",
                        "reasoning_effort is not allowed for this model",
                        model_id,
                        model_len,
                    )
                    return
            else:
                self._reject(
                    400,
                    "unsupported_reasoning_effort",
                    "reasoning_effort must be a string",
                    model_id,
                    model_len,
                )
                return
            if "reasoning" in req and req.get("reasoning") is not None:
                self._reject(
                    400,
                    "unsupported_parameter",
                    "reasoning parameter is not supported",
                    model_id,
                    model_len,
                )
                return
            messages_raw = cast(object, req.get("messages"))
            messages = cast("list[object]", messages_raw) if isinstance(messages_raw, list) else []
            # Универсальная политика фиксируется один раз на принятый запрос.
            universal = _is_image_fallback_enabled()
            images: list[dict[str, object]] = []
            render_messages: list[object] = messages
            stripped_full_prompt = ""
            force_cold = False
            if universal:
                # Рендер без raw dict-content и неперечисленных ключей — всегда,
                # в т. ч. когда media нет: его читают и cold, и hot-resume путь.
                render_messages = _universal_render_messages(messages)
                image_parts, other_media = _media_part_counts(messages)
                # Всегда нормализуем историю: любой cold/downgrade-путь берёт
                # промпт только отсюда, а не из legacy `_flatten_content`.
                stripped_full_prompt = _messages_to_stripped_prompt(messages)
                if image_parts or other_media:
                    if not _is_image_input_enabled():
                        _log_image_fallback(
                            "collect",
                            "flag_disabled",
                            cast(str, model_id),
                            1,
                            image_parts,
                        )
                        force_cold = True
                    else:
                        try:
                            images = _collect_images(
                                messages,
                                cast(str, model_id),
                                cast(str, effort),
                                universal=True,
                            )
                        except ImageReject as rejected:
                            _log_image_fallback(
                                "collect",
                                rejected.reason,
                                cast(str, model_id),
                                1,
                                image_parts,
                            )
                            images = []
                            force_cold = True
                        else:
                            if not images:
                                _log_image_fallback(
                                    "collect",
                                    "unsupported_media",
                                    cast(str, model_id),
                                    1,
                                    other_media,
                                )
                                force_cold = True
            else:
                try:
                    images = _collect_images(
                        messages, cast(str, model_id), cast(str, effort)
                    )
                except ImageReject as rejected:
                    _log("image_reject detail=%s" % rejected.reason)
                    self._reject(
                        400,
                        rejected.code,
                        f"image rejected: {rejected.code}",
                        model_id,
                        model_len,
                    )
                    return
            img_dir = cast(Path, images[0]["path"]).parent if images else None
            try:
                _launcher()
            except LauncherUnavailable:
                self._reject(
                    503,
                    "launcher_unavailable",
                    "canonical launcher is missing or not executable",
                    model_id,
                    model_len,
                )
                return
            raw_tools = req.get("tools")
            tools = (
                [t for t in raw_tools if isinstance(t, dict)]
                if isinstance(raw_tools, list)
                else []
            )
            tool_choice = req.get("tool_choice")
            tools_count = 0 if _tool_choice_none(tool_choice) else len(tools)
            # Эмуляция OpenAI function calling ядром: tools есть и tool_choice != "none".
            emulate_tools = tools_count > 0 and _new_flag(
                "tool_emulation_enabled", True
            )
            if force_cold or (universal and not images):
                full_prompt = stripped_full_prompt
            else:
                full_prompt = _messages_to_prompt(render_messages, images)
                if universal:
                    stripped_full_prompt = stripped_full_prompt or full_prompt
            if emulate_tools:
                full_prompt = _with_tools_protocol(full_prompt, tools, tool_choice)
                if stripped_full_prompt:
                    stripped_full_prompt = _with_tools_protocol(
                        stripped_full_prompt, tools, tool_choice
                    )
            else:
                full_prompt = _with_pure_text_protocol(full_prompt)
                if stripped_full_prompt:
                    stripped_full_prompt = _with_pure_text_protocol(stripped_full_prompt)
            extra = (
                req.get("extra_body") if isinstance(req.get("extra_body"), dict) else {}
            )
            raw_cwd = extra.get("cwd")
            cwd = ""
            cwd_invalid = False
            # Штатное отсутствие cwd (None/"") и явно невалидный cwd различаются:
            # невалидный деградирует не молча в "", а в fail-closed холодный ход.
            # Длина и запрещённые символы проверяются на сырой строке ДО normpath:
            # иначе "/"*N + "tmp" схлопывается в "/tmp", обходя лимит и аллоцируя O(N).
            if raw_cwd is not None:
                if isinstance(raw_cwd, str):
                    val = raw_cwd.strip()
                    if val:
                        if (
                            len(val) > CWD_MAX_LEN
                            or not os.path.isabs(val)
                            or "\x00" in val
                            or any(
                                ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF
                                for c in val
                            )
                        ):
                            _log(f"cwd-invalid-rejected cwd={val[:32]!r}")
                            cwd_invalid = True
                            force_cold = True
                        else:
                            cwd = os.path.normpath(val)
                else:
                    _log(f"cwd-nonstring-rejected type={type(raw_cwd).__name__}")
                    cwd_invalid = True
                    force_cold = True
            # Kill-switch изоляции читается на каждом запросе: без рестарта моста.
            isolation_enabled = _is_session_isolation_enabled()
            # Горячие сессии — только агентным запросам с инструментами. Фоновые и
            # plain-запросы (в т. ч. генерация заголовка DSH, tools=0) стор не читают
            # и не пишут: ни claim, ни commit, ни invalidate.
            chat_id, chat_id_invalid = _request_chat_id(
                self.headers, cast(dict, extra), req if isinstance(req, dict) else None
            )
            sess_key: tuple[str, ...] | None = (
                _session_key_for(
                    cast(str, model_id),
                    cwd,
                    cast(str, effort),
                    chat_id,
                )
                if tools_count > 0 and isolation_enabled and not cwd_invalid
                else None
            )
            if chat_id_invalid:
                _log("chat-id-invalid-rejected")
                sess_key = None
                force_cold = True
            if cwd_invalid or not isolation_enabled:
                sess_key = None
                force_cold = True
            if sess_key is not None and not _session_key_valid(sess_key):
                sess_key = None
            use_session_store = (
                tools_count > 0 and sess_key is not None and isolation_enabled
            )
            raw_cid = (
                extra.get("conversation_id")
                if "conversation_id" in extra
                else (req.get("conversation_id") if isinstance(req, dict) else None)
            )
            cid_clean = ""
            if raw_cid is not None:
                if isinstance(raw_cid, str):
                    val = raw_cid.strip()
                    if val:
                        if _CID_RE.fullmatch(val):
                            cid_clean = val
                        else:
                            _log(f"cid-malformed-rejected cid={val[:16]!r}")
                            force_cold = True
                else:
                    _log(f"cid-nonstring-rejected type={type(raw_cid).__name__}")
                    force_cold = True

            # Явный CID разрешён только при доказанном владении ключом этого чата.
            if cid_clean:
                is_owned = False
                if use_session_store and sess_key is not None:
                    with _session_store_lock:
                        entry = _session_store.get(sess_key)
                        is_owned = entry is not None and entry.get("cid") == cid_clean
                if not is_owned:
                    _log(f"cid-unowned-blocked cid={cid_clean[:8]}")
                    conversation_id = ""
                    force_cold = True
                else:
                    conversation_id = cid_clean
            else:
                conversation_id = ""
            is_resumed = False
            prompt = full_prompt
            if force_cold:
                # Media убраны из истории, либо malformed/unowned CID:
                # ход идёт холодным text-only с полной историей.
                conversation_id = ""
            elif conversation_id:
                if _cid_acquire(conversation_id, turn_id):
                    owned_cid = conversation_id
                else:
                    # cid занят другим активным ходом: два хода не делят один разговор.
                    _log(f"cid-busy-fresh cid={conversation_id[:8]}")
                    conversation_id = ""
            elif use_session_store and sess_key is not None:
                use_cid = _session_claim(sess_key, turn_id)
                if use_cid:
                    conversation_id = use_cid
                    is_resumed = True
                    prompt = _get_resumed_turn_prompt(render_messages, images)
                    if emulate_tools:
                        prompt = _with_tools_protocol(prompt, tools, tool_choice)
                    else:
                        prompt = _with_pure_text_protocol(prompt)
            ctx = {
                "registry_use_cid": use_cid,
                "registry_owned_cid": owned_cid,
                "t_req_start": t_req_start,
                "step_job_id": str(
                    self.headers.get("X-Idempotency-Key")
                    or req.get("step_job_id")
                    or ""
                ),
                # Эмуляция: модель зовёт инструменты клиента, нативные agy выключены.
                "agy_mode": "ask" if emulate_tools else resolve_agy_mode(req),
                "emulate_tools": emulate_tools,
                "tools": tools,
                "turn_id": turn_id,
                "sess_key": sess_key,
                "hot_resumed": is_resumed,
                "full_prompt": full_prompt,
                "model": model_id,
                "model_len": model_len,
                "effort": effort,
                "effort_source": effort_source,
                "prompt": prompt,
                "cwd": cwd,
                "tools_count": tools_count,
                "conversation_id": conversation_id,
                "tag": (
                    f"client={self._client_tag()} "
                    f"ua={(self.headers.get('User-Agent') or '-')[:60]}"
                ),
                "stream": bool(req.get("stream")),
                "images": images,
                "img_dir": img_dir,
                "universal_fallback": universal,
                "stripped_full_prompt": stripped_full_prompt,
            }
            if ctx["stream"]:
                self._serve_sse(ctx)
            else:
                self._serve_json(ctx)
        finally:
            if not ctx.get("job_owns_cid"):
                if use_cid:
                    with _session_store_lock:
                        _in_flight_cids.discard(use_cid)
                _cid_release(use_cid or owned_cid, turn_id)
            if reserved and budget is not None:
                budget.release(reserved)

    @staticmethod
    def _graceful_notice(reason: str, limit_s: object) -> str:
        """Диагностика мягкого завершения: фактическая причина и сработавший лимит."""
        if isinstance(limit_s, (int, float)):
            shown = f"{limit_s:g}"
        elif reason == "idle_timeout":
            shown = f"{IDLE_TIMEOUT_S:g}"
        else:
            shown = str(TIMEOUT_S)
        return (
            f"\n\n[⚠️ Превышен лимит времени хода agy ({reason}, {shown}s). "
            "Частичный ответ сохранён без аварийного сброса сессии.]\n\n"
        )

    def _serve_json(self, ctx: dict) -> None:
        self._reset_flush_window()
        try:
            self._serve_json_body(ctx)
        finally:
            self._reset_flush_window()

    def _serve_json_body(self, ctx: dict) -> None:
        progress = _ToolProgress(
            str(ctx.get("turn_id") or ""), str(ctx.get("conversation_id") or "")
        )
        markers: list[str] = []
        retained_cache: list[tuple[str, str]] = []

        def on_tool_trace(event: object) -> bool:
            # Выключенный флаг — полный no-op до любого форматирования.
            if not _new_flag("emit_tool_trace"):
                return True
            marker = progress.marker(event, commit=False)
            if marker is not None:
                markers.append(marker)
                progress.commit()
            return True

        def consume_retained(out: dict) -> tuple[str, str]:
            """Остаток terminal drain: (текст, мышление); tool_trace -> маркеры, один раз."""
            if retained_cache:
                return retained_cache[0]
            retained = list(out.get("retained_events") or [])
            retained_text = "".join(str(p) for k, p in retained if k == "text")
            retained_reasoning = ""
            for kind, payload in retained:
                if kind == "reasoning":
                    retained_reasoning += str(payload)
                elif kind == "tool_trace":
                    _ = on_tool_trace(payload)
            retained_cache.append((retained_text, retained_reasoning))
            return retained_cache[0]

        tool_turn = (
            _ToolTurn(
                cast(list, ctx.get("tools") or []),
                lambda _text: True,
                lambda _text: True,
                lambda _calls: True,
            )
            if ctx.get("emulate_tools")
            else None
        )
        if tool_turn is not None:
            ctx["tool_stop"] = tool_turn.turn_complete

        def build_payload(
            out: dict,
            content: str,
            reasoning: str,
            finish_reason: str,
            tool_calls: list[dict[str, object]] | None = None,
        ) -> dict:
            message: dict[str, object] = {"role": "assistant", "content": content}
            if tool_calls:
                message["content"] = content or None
                message["tool_calls"] = tool_calls
            if reasoning:
                # OpenAI-совместимое поле мышления: Harness читает его из сообщения
                # ассистента так же, как из дельты потока.
                message["reasoning_content"] = reasoning
            payload = {
                "id": f"chatcmpl-agy-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": ctx["model"],
                "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
                "usage": self._usage_payload(
                    out.get("usage") or {}, out.get("usage_resolved")
                ),
            }
            if out.get("conversation_id"):
                payload["conversation_id"] = out["conversation_id"]
            return payload

        def finalize_timeout(out: dict) -> None:
            """Graceful-финал: HTTP 200, настраиваемый finish_reason (дефолт stop).

            Идемпотентно, до run.close().
            """
            state = out.get("state")
            if out.get("graceful_done") or state not in ("timeout", "idle_timeout"):
                return
            if not _new_flag("graceful_timeout_on_partial"):
                return
            # Остаток terminal drain + partial -> HTTP 200, finish_reason из настроек.
            retained_text, retained_reasoning = consume_retained(out)
            content = str(out.get("text") or "")
            base_reasoning = str(out.get("reasoning") or "")
            reasoning = base_reasoning + retained_reasoning + "".join(markers)
            if tool_turn is not None:
                # Сырой <tool_call> в content не уходит: незакрытый блок отброшен.
                _ = tool_turn.feed(retained_text)
                tool_turn.finish()
                content, retained_text = tool_turn.content, ""
                reasoning += tool_turn.reasoning
            if not (content.strip() or reasoning.strip() or retained_text.strip()):
                return  # полная тишина: прежняя ошибка 504
            content += retained_text
            content += self._graceful_notice(str(state), out.get("timeout_limit_s"))
            self._arm_flush_window(ctx)
            out["graceful_done"] = True
            _log(f"graceful-timeout state={state} mode=json")
            if not self._prepare_flush_write():
                return
            self._send(
                200, build_payload(out, content, reasoning, _graceful_finish_reason())
            )

        ctx["finalize_timeout"] = finalize_timeout

        def _json_tool_trace_wrapped(payload: Any) -> bool:
            if tool_turn is not None:
                tool_turn.notify_activity()
            return on_tool_trace(payload)

        def _json_reasoning_wrapped(text: str) -> bool:
            if tool_turn is not None:
                return tool_turn.feed_reasoning(text)
            return True

        out = self._run_once(
            ctx,
            tool_turn.feed if tool_turn is not None else (lambda _v: True),
            _json_tool_trace_wrapped,
            _json_reasoning_wrapped,
            None,
        )
        if out.get("state") == "client_gone":
            return
        if out.get("graceful_done"):
            return
        finalize_timeout(out)  # страховка, если _run_once не вызвал hook
        if out.get("graceful_done"):
            return
        retained_reasoning = retained_cache[0][1] if retained_cache else ""
        reasoning = str(out.get("reasoning") or "") + retained_reasoning
        reasoning += "".join(markers)
        err = self._error_body(out, bool(ctx.get("stream_resilience_enabled", True)))
        if err is None and tool_turn is not None:
            tool_turn.finish()
            if tool_turn.error:
                err = tool_turn.error_body()
        if err is not None:
            self._send(err["code"], {"error": err})
            return
        if tool_turn is None:
            self._send(
                200, build_payload(out, str(out.get("text") or ""), reasoning, "stop")
            )
            return
        self._send(
            200,
            build_payload(
                out,
                tool_turn.content,
                reasoning + tool_turn.reasoning,
                "tool_calls" if tool_turn.calls else "stop",
                tool_turn.calls,
            ),
        )

    def _serve_sse(self, ctx: dict) -> None:
        self._reset_flush_window()
        try:
            self._serve_sse_body(ctx)
        finally:
            self._reset_flush_window()

    def _serve_sse_body(self, ctx: dict) -> None:
        completion_id = f"chatcmpl-agy-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        shown_model = ctx["model"]
        resilience = _new_flag("AGY_BRIDGE_STREAM_RESILIENCE_ENABLED", True)
        ctx["stream_resilience_enabled"] = resilience
        ctx["stream_committed"] = False
        disconnected = False
        self._stream_relay = StreamRelay(getattr(self, "wfile", None))

        def chunk(
            delta: dict,
            finish=None,
            usage: dict | None = None,
            conversation_id: str = "",
            error: dict | None = None,
        ) -> str:
            body: dict = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": shown_model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            if usage is not None:
                body["usage"] = usage
            if conversation_id:
                body["conversation_id"] = conversation_id
            if error is not None:
                body["error"] = error
            return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"

        def emit(data: str) -> bool:
            nonlocal disconnected
            if resilience and disconnected:
                return False
            ok = self._emit(data)
            if resilience and not ok:
                disconnected = True
            return ok

        def commit() -> bool:
            nonlocal disconnected
            if disconnected:
                return False
            if ctx["stream_committed"]:
                return True
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError, OSError):
                disconnected = True
                _log("client gone before headers")
                return False
            ctx["stream_committed"] = True
            self.close_connection = True
            return emit(chunk({"role": "assistant", "content": ""}))

        # Счётчики полезной выдачи растут только после УСПЕШНОЙ записи клиенту
        # (role-chunk, keepalive и пустые/whitespace-дельты не в счёт).
        emitted_content = [0]
        emitted_reasoning_or_tool = [0]
        emitted_tool_calls = [0]
        progress = _ToolProgress(
            str(ctx.get("turn_id") or ""), str(ctx.get("conversation_id") or "")
        )

        def on_text(value: str) -> bool:
            if resilience and not value:
                return not disconnected
            ok = commit() and emit(chunk({"content": value}))
            if ok and value.strip():
                emitted_content[0] += len(value.strip())
            return ok

        def on_reasoning(value: str) -> bool:
            # Мышление шага: Harness читает первое непустое из
            # reasoning_content|reasoning|reasoning_text — отдаём только первое.
            if resilience and not value:
                return not disconnected
            ok = commit() and emit(chunk({"reasoning_content": value}))
            if ok and value.strip():
                emitted_reasoning_or_tool[0] += 1
            return ok

        def on_tool_trace(event: dict) -> bool:
            if resilience:
                ctx["tool_activity"] = True
            # Нативный инструмент agy исполняется внутри CLI и наружу не уходит как
            # tool_call. Безопасный маркер прогресса — только при emit_tool_trace;
            # выключенный флаг — полный no-op до любого форматирования строк.
            if not _new_flag("emit_tool_trace"):
                return True
            marker = progress.marker(event, commit=False)
            if marker is None:
                return True
            ok = on_reasoning(marker)
            if ok:
                progress.commit()
            return ok

        tool_turn: _ToolTurn | None = None
        if ctx.get("emulate_tools"):

            def on_calls(calls: list[dict[str, object]]) -> bool:
                ok = commit() and emit(chunk({"tool_calls": calls}))
                if ok:
                    emitted_reasoning_or_tool[0] += 1
                    emitted_tool_calls[0] += 1
                return ok

            tool_turn = _ToolTurn(
                cast(list, ctx.get("tools") or []), on_text, on_reasoning, on_calls
            )
            ctx["tool_stop"] = tool_turn.turn_complete
        stream_text = tool_turn.feed if tool_turn is not None else on_text

        def keepalive() -> bool:
            if not ctx["stream_committed"]:
                if ctx.get("step_job_id"):
                    return commit() and emit(": keepalive\n\n")
                return not disconnected
            return emit(": keepalive\n\n")

        def close_interrupted(out: dict) -> None:
            """Мягко закрывает транзиентный обрыв после частичной выдачи (agent-agnostic)."""
            open_call = tool_turn._normalizer.has_open_tool_call() if tool_turn else False
            dec = evaluate_graceful_interruption(
                error_text=out.get("err"),
                delivered_content=bool(emitted_content[0]),
                delivered_reasoning=bool(emitted_reasoning_or_tool[0] - emitted_tool_calls[0]),
                delivered_tool_calls=any((emitted_tool_calls[0], out.get("tool_calls"))),
                has_unclosed_tool_call=open_call,
                graceful_enabled=_new_flag("graceful_interruption_on_partial", True),
            )
            if dec.should_gracefully_close:
                self._arm_flush_window(ctx)
                if tool_turn:
                    tool_turn.finish()
                _ = {"content": on_text}.get(dec.target_channel, on_reasoning)(dec.notice_text)
                out.update(state="done", rc=0, err="", graceful_interruption_closed=True)
                _log(f"stream-graceful-interruption target={dec.target_channel}")

        def finalize_timeout(out: dict) -> None:
            """Graceful-финал timeout/idle_timeout после полезной выдачи (идемпотентно).

            Один arbiter-досыл, один notice, один настраиваемый finish_reason
            (по умолчанию "stop"), один
            [DONE] — всё в одном окне T_FINAL_FLUSH_S; ошибка записи прекращает записи.
            """
            if out.get("graceful_done") or out.get("state") not in (
                "timeout",
                "idle_timeout",
            ):
                return
            if not _new_flag("graceful_timeout_on_partial"):
                return
            retained = list(out.get("retained_events") or [])
            retained_text = "".join(str(p) for k, p in retained if k == "text")
            if not (
                emitted_content[0] > 0
                or emitted_reasoning_or_tool[0] > 0
                or retained_text.strip()
            ):
                return  # полная тишина: прежняя ошибка 504
            self._arm_flush_window(ctx)
            ok = True
            for kind, payload in retained:
                if kind == "text":
                    ok = stream_text(str(payload))
                elif kind == "reasoning":
                    ok = on_reasoning(str(payload))
                elif kind == "tool_trace":
                    ok = on_tool_trace(payload)
                if not ok:
                    break
            if ok and tool_turn is not None:
                # Удержанный хвост — в content; незакрытый <tool_call> отброшен.
                tool_turn.finish()
                ok = tool_turn.ok
            reason = str(out.get("state"))
            conv_id = str(out.get("conversation_id") or "")
            if ok:
                ok = commit() and emit(
                    chunk({"content": self._graceful_notice(reason, out.get("timeout_limit_s"))})
                )
            if ok:
                ok = emit(chunk({}, _graceful_finish_reason(), conversation_id=conv_id))
            if ok:
                _ = emit("data: [DONE]\n\n")
            out["graceful_done"] = True
            _log(f"graceful-timeout state={reason} mode=sse ok={int(bool(ok))}")

        def finalize_stream(out: dict) -> None:
            """Graceful-финал по state: обрыв транспорта либо timeout/idle_timeout."""
            closers = dict.fromkeys(("agy_error", "pump_error"), close_interrupted)
            closers.get(str(out.get("state")), finalize_timeout)(out)

        ctx["finalize_timeout"] = finalize_stream
        if not resilience and not ctx.get("step_job_id") and not commit():
            return

        def _sse_tool_trace_wrapped(payload: Any) -> bool:
            if tool_turn is not None:
                tool_turn.notify_activity()
            return on_tool_trace(payload)

        stream_reasoning = (
            tool_turn.feed_reasoning if tool_turn is not None else on_reasoning
        )
        out = self._run_once(
            ctx, stream_text, _sse_tool_trace_wrapped, stream_reasoning, keepalive
        )
        if disconnected or out.get("state") == "client_gone":
            _log("client gone mid-stream, child killed")
            return
        finalize_stream(out)  # страховка, если _run_once не вызвал hook
        if out.get("graceful_done"):
            return
        err = self._error_body(out, resilience)
        finish_reason = "stop"
        if err is None and tool_turn is not None:
            tool_turn.finish()
            if disconnected or not tool_turn.ok:
                return
            if tool_turn.error:
                err = tool_turn.error_body()
            elif tool_turn.calls:
                finish_reason = "tool_calls"
        if (
            (resilience or ctx.get("step_job_id"))
            and err is not None
            and not ctx["stream_committed"]
        ):
            self._send(
                int(err.get("code") or 502) if ctx.get("step_job_id") else 502,
                {"error": err},
            )
            self.close_connection = True
            return
        if not commit():
            return
        if err is None:
            conv_id = str(out.get("conversation_id") or "")
            if (
                not emit(chunk({}, finish_reason, conversation_id=conv_id))
                and resilience
            ):
                return
            # Harness считает tok/s и % контекста только из usage в потоке
            # (dsh-llm-pi-ai toStreamChunks: usage-chunk -> session usage).
            # Шлём только при ненулевых токенах, чтобы пустой usage от agy
            # не превращался в ложные «0 tok/s / 0%».
            usage = self._usage_payload(
                out.get("usage") or {}, out.get("usage_resolved")
            )
            if usage["prompt_tokens"] or usage["completion_tokens"]:
                if (
                    not emit(chunk({}, finish_reason, usage, conversation_id=conv_id))
                    and resilience
                ):
                    return
        else:
            error_frame = (
                chunk({}, "stop", error=err)
                if resilience
                else "data: " + json.dumps({"error": err}, ensure_ascii=False) + "\n\n"
            )
            if not emit(error_frame) and resilience:
                return
        emit("data: [DONE]\n\n")


class Server(ThreadingHTTPServer):
    """HTTP-сервер с семафором числа соединений на уровне приёма."""

    daemon_threads = True
    request_queue_size = 64
    allow_reuse_address = True

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._conn_sem = threading.BoundedSemaphore(
            int(FLEET["admission"]["max_http_connections"])
        )

    def _send_raw_503(self, request: socket.socket) -> None:
        body = json.dumps(
            {
                "error": {
                    "message": "bridge overloaded: connection limit",
                    "type": "overloaded",
                    "code": 503,
                },
            }
        ).encode("utf-8")
        head = (
            b"HTTP/1.1 503 Service Unavailable\r\n"
            b"Content-Type: application/json; charset=utf-8\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"Connection: close\r\n\r\n"
        )
        request.sendall(head + body)

    def process_request(
        self, request: socket.socket | tuple[bytes, socket.socket], client_address: Any
    ) -> None:
        if not self._conn_sem.acquire(blocking=False):
            try:
                peer = f"{client_address[0]}:{client_address[1]}"
            except (TypeError, IndexError):
                peer = "unknown"
            _log(f"reject reason=overloaded model=unknown model_len=0 client={peer}")
            sock = request if isinstance(request, socket.socket) else request[1]
            try:
                self._send_raw_503(sock)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(
        self, request: socket.socket | tuple[bytes, socket.socket], client_address: Any
    ) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._conn_sem.release()


def _sweep_workspace(cutoff_s: float = SWEEP_CUTOFF_S) -> int:
    """Удалить каталоги ходов run-*/img-* старше cutoff_s (наследие упавших ходов).

    Симлинки не разыменовываются и не удаляются; каталоги из `_active_img_dirs`
    (живые ходы) сохраняются при любом возрасте. Возвращает число удалённых img-*.
    """
    removed = 0
    now = time.time()
    try:
        entries = list(os.scandir(str(WORKSPACE)))
    except OSError:
        return 0
    for entry in entries:
        if not entry.name.startswith(("run-", "img-")):
            continue
        try:
            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                continue
            if now - entry.stat(follow_symlinks=False).st_mtime <= cutoff_s:
                continue
        except OSError:
            continue
        with _active_lock:
            if os.path.abspath(entry.path) in _active_img_dirs:
                continue
        shutil.rmtree(entry.path, ignore_errors=True)
        if entry.name.startswith("img-"):
            removed += 1
    if removed:
        _log(f"image_sweep_removed count={removed}")
    return removed


def _sweep_loop() -> None:
    """Периодическая зачистка осиротевших каталогов (daemon-поток)."""
    while True:
        time.sleep(SWEEP_INTERVAL_S)
        try:
            _ = _sweep_workspace()
        except Exception as exc:  # noqa: BLE001 — поток зачистки не должен умирать
            _log(f"sweep_error err={type(exc).__name__}")


def main() -> None:
    global _budget
    if not AUTH_KEY:
        sys.stderr.write("AGY_BRIDGE_KEY is required; refusing to start\n")
        raise SystemExit(1)
    _budget = _ByteBudget(int(FLEET["admission"]["max_inflight_body_bytes"]))
    _reset_sqlite_guards_for_tests()  # чистое процессное состояние guardrails на старте
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    _ = _load_persisted_sessions()
    _ = _sweep_workspace()
    threading.Thread(target=_sweep_loop, daemon=True).start()
    # Хеш бинаря agy считается заранее, чтобы первый image-ход не платил за него.
    threading.Thread(target=_file_sha256, args=(AGY_BIN,), daemon=True).start()
    _log(f"fleet_sha256={FLEET['sha256']} models={len(FLEET['order'])}")
    try:
        _launcher()
    except LauncherUnavailable:
        _log(f"launcher_missing path={LAUNCHER} (requests will fail with 503)")
    api_key_present = "yes" if AUTH_KEY else "no"
    server = Server((HOST, PORT), Handler)
    _log(
        f"listen {HOST}:{PORT} model={MODEL_ID} max_concurrent={MAX_CONCURRENT} "
        f"queue_timeout={QUEUE_TIMEOUT_S}s timeout={TIMEOUT_S}s keepalive={KEEPALIVE_S}s "
        f"api_key={api_key_present}"
    )
    print(f"[agy-bridge] listening on http://{HOST}:{PORT}/v1", flush=True)
    raise SystemExit(_LIFECYCLE.serve_forever(server))


if __name__ == "__main__":
    main()


__all__ = [
    "ProcessSupervisor",
    "ProcessSupervisorConfig",
    "AccountPool",
    "AccountPoolConfig",
    "StreamRelay",
    "_StepState",
    "_ContentArbiter",
    "_ToolProgress",
    "_safe_tool_name",
    "_format_tool_marker",
    "_lower_keys",
    "_classify_part",
    "_part_text",
    "_content_items",
    "_image_part_canonical",
    "_media_part_counts",
    "_collect_image_parts_universal",
    "_json_copy",
    "_flatten_content_stripped",
    "_strip_media_from_messages",
    "_universal_render_messages",
]
