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

Инструменты (tools) НЕ эмулируются текстовым протоколом. `agy` 1.3.1 сам
пробрасывает ~51 нативный инструмент (`run_command`, `write_to_file`, `view_file`
и др.) и с `--dangerously-skip-permissions` реально их исполняет. Штатный режим
моста:

  * если запрос пришёл без `tools` — это текстовый ход (роль судьи/ревьюера);
    `--dangerously-skip-permissions` всё равно передаётся (набор флагов не зависит
    от tools), но шаг без инструментов их и не вызывает;
  * если запрос пришёл с `tools` — мост работает как АГЕНТНЫЙ ход: модель сама
    исполняет свои нативные инструменты, мост лишь ждёт финальный текст. Наружу
    `delta.tool_calls` НЕ отдаются (см. README, раздел «Инструменты»).

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
    idle_timeout после частичной выдачи завершаются `finish_reason="length"` вместо 504.

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

import bisect
import base64
import hashlib
import json
import os
import queue
import random
import re
import select
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, NamedTuple, cast, final

# Корень репозитория cli-agent-bridge: resolve() раскрывает симлинк деплоя
# (~/.dsh/bridges/agy-bridge -> <repo>/bridges/agy-bridge), parents[2] = <repo>.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.watchdog import (  # noqa: E402
    IDLE_TIMEOUT_S as _CORE_IDLE_TIMEOUT_S,
    WATCHDOG_INTERVAL_S,
    AdaptiveTimeoutController,
)

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
HOST = os.environ.get("AGY_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("AGY_BRIDGE_PORT", "9887"))
AUTH_KEY = os.environ.get("AGY_BRIDGE_KEY", "").strip()
LAUNCHER = os.environ.get(
    "AGY_LAUNCHER", str(HOME / ".config" / "agy-launch" / "agy-cli.sh")
)
FLEET_PATH = Path(os.environ.get("AGY_BRIDGE_FLEET", "") or str(ROOT / "fleet.json"))
ENV_MODEL = os.environ.get("AGY_BRIDGE_MODEL", "").strip()
WORKSPACE = ROOT / "workspace"
MAX_CONCURRENT = int(os.environ.get("AGY_BRIDGE_MAX_CONCURRENT", "4"))
QUEUE_TIMEOUT_S = int(os.environ.get("AGY_BRIDGE_QUEUE_TIMEOUT", "900"))
TIMEOUT_S = int(os.environ.get("AGY_BRIDGE_TIMEOUT", "1800"))
KEEPALIVE_S = float(os.environ.get("AGY_BRIDGE_KEEPALIVE", "15"))
# Первое событие agy приходит не мгновенно (инициализация CLI + MCP-серверов),
# но и не через минуты; 120 с — с запасом на холодный egress.
FIRST_TOKEN_TIMEOUT_S = float(os.environ.get("AGY_BRIDGE_FIRST_TOKEN_TIMEOUT", "120"))
PRINT_TIMEOUT = os.environ.get("AGY_BRIDGE_PRINT_TIMEOUT", "0")


def _env_float(name: str, default: float, low: float, high: float) -> float:
    """Число из окружения, зажатое в [low, high]; невалидное значение -> default."""
    raw = os.environ.get(name, "").strip()
    try:
        value = float(raw) if raw else default
    except ValueError:
        value = default
    if value != value:
        value = default
    return min(high, max(low, value))


# Мышление шагов agy: CLI кладёт его в транскрипт разговора пошагово, в середине
# хода. Путь и имя файла фиксированы CLI (проверено на agy 1.3.1).
BRAIN_DIR = Path(
    os.environ.get("AGY_BRIDGE_BRAIN", "")
    or str(HOME / ".gemini" / "antigravity-cli" / "brain")
)
TRANSCRIPT_NAME = "transcript_full.jsonl"
TRANSCRIPT_POLL_S = float(os.environ.get("AGY_BRIDGE_TRANSCRIPT_POLL", "0.05"))
TRANSCRIPT_READ_MAX = 4 * 1024 * 1024

# Живой источник мышления: SQLite-база разговора agy (таблица `steps`, шаг
# планировщика `step_type=15`, подполе 20.3 `step_payload` растёт в `status=8`).
# База открывается только на чтение; транскрипт остаётся минимальным источником.
CONV_DIR = Path(
    os.environ.get("AGY_BRIDGE_CONVERSATIONS", "")
    or str(HOME / ".gemini" / "antigravity-cli" / "conversations")
)
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
DRAIN_WINDOW_S = _env_float("AGY_BRIDGE_TRANSCRIPT_GRACE", 0.35, 0.20, DRAIN_MAX_S)
DRAIN_MIN_S = min(_env_float("AGY_BRIDGE_DRAIN_MIN", 0.15, 0.05, 0.25), DRAIN_WINDOW_S)
DRAIN_POLL_STEP_S = 0.05
JOIN_TIMEOUT_S = _env_float("AGY_BRIDGE_DRAIN_JOIN", 0.15, 0.05, 0.20)
PROC_EXIT_WAIT_S = 0.05
# Потолки памяти и работы одной итерации опроса.
MAX_REASONING_BYTES_PER_TURN = 2 * 1024 * 1024
MAX_STEP_BLOB_BYTES = 262144
MAX_STEPS_TRACKED = 128
SQLITE_ROW_LIMIT = 16
# Константы схемы привязаны к agy 1.4.9 и подтверждаются canary.
STEP_TYPE_PLANNER = 15
STEP_STATUS_GENERATING = 8
STEP_STATUS_DONE = 3
# cid, из которого строится путь к базе, обязан быть hex-строкой с дефисами.
_CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
_STEP_INDEX_RE = re.compile(rb'"step_index"\s*:\s*(\d+)')
# Процессные guardrails (AD-005): breaker, бюджеты, окно проб.
BREAKER_FAILURES_TO_OPEN = 3
BREAKER_COOLDOWN_S = 30.0
BREAKER_PROBE_LEASE_S = 60.0
RETRY_CAPACITY_TENTHS = 30
RETRY_CREDIT_TENTHS = 2
RETRY_COST_TENTHS = 10
POLL_BUCKET_CAPACITY_TENTHS = 30
POLL_BUCKET_REFILL_TENTHS_PER_S = 20
POLL_BUCKET_COST_TENTHS = 10
RETRY_PAUSE_CAP_S = 2.0
# Сквозные бюджеты запроса (AD-003/AD-004). Резерв 5.5 с = drain 0.5 + финальный flush 5.0.
T_REQ_BUDGET_S = 3600.0
T_DRAIN_MAX_S = 0.5
T_FINAL_FLUSH_S = 5.0
T_RESERVE_S = T_DRAIN_MAX_S + T_FINAL_FLUSH_S
T_MIN_ATTEMPT_S = 1.0
# Настроенные idle/max при extended_timeout_enabled (AD-003): idle 1800 с, потолок 3600 с.
EXT_IDLE_TIMEOUT_S = 1800.0
EXT_MAX_TIMEOUT_S = 3600.0
# Границы арбитра planner-контента одного хода (AD-001).
MAX_CONTENT_STEPS = MAX_STEPS_TRACKED
MAX_CONTENT_BYTES_PER_TURN = 8 * 1024 * 1024
MAX_TOOL_MARKERS_PER_TURN = 32
# Расходящийся (непрефиксный) planner-текст удерживается для graceful-хвоста до 64 КиБ.
MAX_RETAINED_DIVERGENT_BYTES = 65536
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
DYNAMIC_CONFIG_MAX_BYTES = 65536
SWEEP_INTERVAL_S = 600.0

CWD_MAX_LEN = 4096

# Ленивые горячие сессии: следующий запрос с тем же (модель, cwd, effort) продолжает
# разговор agy через --conversation и шлёт только новые сообщения, а не всю историю.
SESSION_IDLE_TTL_S = 45 * 60.0
SESSION_MAX_TTL_S = 24 * 3600.0
SESSION_MAX_TURNS = 30

_started = time.time()
_active: dict = {}
_active_lock = threading.Lock()
_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
_budget = None
_last_ok = [0.0]
_session_store_lock = threading.Lock()
_session_store: dict[tuple[str, str, str], dict[str, Any]] = {}
_in_flight_cids: set[str] = set()
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
IDLE_TIMEOUT_S = _idle_timeout_from_env()
# Зачистка группы: сколько ждать после SIGTERM и сколько — reap лидера после SIGKILL.
KILL_TERM_GRACE_S = 2.0
KILL_WAIT_S = 5.0
# После result ERROR процесс обязан выйти сам: сколько ждать done, прежде чем сдаться.
RESULT_EXIT_GRACE_S = 5.0
# События очереди, считающиеся активностью агента (result/done/pump_error — терминальные).
_ACTIVITY_KINDS = frozenset({"init", "text", "reasoning", "tool_trace"})


def _launch_env() -> dict:
    """Окружение для `agy`. Ключ моста потомку не передаётся.

    Прокси-переменные (HTTPS_PROXY/HTTP_PROXY/NO_PROXY) выставляет сам лончер
    agy-cli.sh — мост их не дублирует и не переопределяет.
    """
    env = os.environ.copy()
    env.pop("AGY_BRIDGE_KEY", None)
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


def _tool_choice_none(tool_choice: Any) -> bool:
    return isinstance(tool_choice, str) and tool_choice.strip().lower() == "none"


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
    messages: object, model_id: str, effort: str | None
) -> list[dict[str, object]]:
    """Проверить image-части всей истории; вернуть записи для prompt и spool.

    Нет image-частей — `[]` сразу, без stat/хеша/флага. Порядок отказов: флаг и
    proof -> число частей -> по каждой части: роль, форма, `data:` URL, MIME,
    оценка размера base64 ДО decode, строгий base64, сигнатура, лимиты. Ничего не
    пишется на диск и не запускается. Декодированные байты не удерживаются
    (`data` пуст): в spool они пересоздаются из base64 уже после захвата слота.
    """
    parts = _collect_image_parts(messages)
    if not parts:
        return []
    gate = _image_gate(model_id, effort)
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

    Секции протокола инструментов нет намеренно: agy исполняет СВОИ нативные
    инструменты, а не инструменты DSH (см. README, раздел «Инструменты»).
    Image-части получают сквозные маркеры `[image N]` (нумерация с `img_start + 1`),
    а `images` описываются блоком `[attachments]` с абсолютными путями файлов.
    """
    counter = [0]
    img_counter = [img_start]
    blocks: list[str] = []
    for msg in messages:
        rendered = _render_message(msg, counter, img_counter)
        if rendered:
            blocks.append(rendered)
    if images:
        blocks.append(_attachments_block(images))
    text = "\n\n".join(blocks).strip()
    if not text:
        text = "Reply with exactly: PONG"
    return text


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
        skipped = len(
            _collect_image_parts(cast("list[object]", messages[: last_asst + 1]))
        )
        delta = [
            img
            for img in (images or [])
            if cast(int, img.get("msg_index", 0)) > last_asst
        ]
        prompt = _messages_to_prompt(new_msgs, delta, skipped)
        if prompt:
            return prompt
    return _messages_to_prompt(messages, images)


def _session_claim(sess_key: tuple, turn_id: str = "") -> str:
    """Найти живую свободную сессию и занять её; '' — сессии нет.

    Проверка и занятие идут под одним замком: два параллельных запроса не
    получат один и тот же conversation_id. При непустом `turn_id` владение cid
    регистрируется в `_active_cid_owners` в той же критической секции.
    """
    now = time.time()
    with _session_store_lock:
        entry = _session_store.get(sess_key)
        if entry is None:
            return ""
        if (
            now - entry["last_used"] > SESSION_IDLE_TTL_S
            or now - entry["created"] > SESSION_MAX_TTL_S
            or entry["turns"] >= SESSION_MAX_TURNS
        ):
            _session_store.pop(sess_key, None)
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


def _session_invalidate(sess_key: tuple, cid: str) -> None:
    with _session_store_lock:
        entry = _session_store.get(sess_key)
        if entry is not None and entry["cid"] == cid:
            _session_store.pop(sess_key, None)


def _session_commit(sess_key: tuple, cid: str) -> None:
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


def _group_alive(pgid: int) -> bool:
    """Есть ли в процессной группе хоть один процесс (`killpg(pgid, 0)`)."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _kill_group(proc: subprocess.Popen) -> None:
    """Зачистить процессную группу хода: SIGTERM -> ожидание -> SIGKILL -> reap лидера.

    `proc.wait()` вызывается ВСЕГДА (в том числе когда группы уже нет), иначе
    завершившийся лидер остаётся зомби (`Z`).
    """
    pgid = proc.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # группы уже нет — остаётся только reap лидера
    except (PermissionError, OSError):
        try:
            proc.terminate()
        except OSError:
            pass
    else:
        deadline = time.monotonic() + KILL_TERM_GRACE_S
        while time.monotonic() < deadline:
            if proc.poll() is not None and not _group_alive(pgid):
                break
            time.sleep(0.05)
        if proc.poll() is None or _group_alive(pgid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except (PermissionError, OSError):
                try:
                    proc.kill()
                except OSError:
                    pass
    try:
        proc.wait(timeout=KILL_WAIT_S)
    except subprocess.TimeoutExpired:
        _log(f"kill_group_wait_timeout pid={pgid} after {KILL_WAIT_S:g}s")


def _kill_all(*_: Any) -> None:
    with _active_lock:
        procs = list(_active.values())
    for proc in procs:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    _log(f"shutdown: killed {len(procs)} child process group(s)")
    os._exit(0)


# ---- Guardrails SQLite-источника мышления (AD-005, AD-006) -----------------------


def _reset_sqlite_guards_for_tests() -> None:
    """Сбросить процессные глобалы guardrails (хелпер тестов)."""
    global _breaker_state, _breaker_failures, _breaker_opened_at, _breaker_probe_gen
    global _breaker_active_probe_gen, _breaker_probe_started_at, _retry_tenths
    global _compat_ident, _compat_state, _flag_value, _flag_key, _flag_checked_at
    global _sqlite_divergence_count, _sqlite_drain_deadline_count
    global _sqlite_open_connections, _sqlite_max_open_connections, _rng
    global _cfg_snapshot, _cfg_key, _cfg_checked_at, _image_flag_cache
    with _cfg_lock:
        _cfg_snapshot = _COLD_FLAGS
        _cfg_key = None
        _cfg_checked_at = None
    with _image_flag_lock:
        _image_flag_cache = (0.0, False)
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
# Stdlib-only LaunchAgent: ни SDK, ни удалённого транспорта. Все четыре флага имеют
# строгий кодовый False (прежнее поведение до явного включения). Приоритет:
# env override > JSON bool из dynamic_config.json > False.


class _RuntimeFlags(NamedTuple):
    """Неизменяемый валидированный снимок флагов новой политики."""

    planner_content_streaming_enabled: bool = False
    emit_tool_trace: bool = False
    extended_timeout_enabled: bool = False
    graceful_timeout_on_partial: bool = False


_NEW_FLAG_ENV = {
    "planner_content_streaming_enabled": "AGY_PLANNER_CONTENT_STREAMING_ENABLED",
    "emit_tool_trace": "AGY_BRIDGE_EMIT_TOOL_TRACE",
    "extended_timeout_enabled": "AGY_EXTENDED_TIMEOUT_ENABLED",
    "graceful_timeout_on_partial": "AGY_GRACEFUL_TIMEOUT_ON_PARTIAL",
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
    """Разобрать dynamic_config.json; ValueError — файл отвергается целиком."""
    data = cast(object, json.loads(text))
    if not isinstance(data, dict):
        raise ValueError("dynamic_config: not an object")
    raw = cast("dict[str, object]", data)
    values: dict[str, bool] = {}
    for name in _RuntimeFlags._fields:
        value = raw.get(name, False)
        if not isinstance(value, bool):
            raise ValueError("dynamic_config: %s is not boolean" % name)
        values[name] = value
    return _RuntimeFlags(**values)


def _runtime_snapshot() -> _RuntimeFlags:
    """Снимок флагов из dynamic_config.json: TTL 1.0 с, ключ версии (mtime_ns, size).

    Пока stat не изменился, JSON не разбирается (identity снимка сохраняется). Битый
    JSON или не-bool значение отвергают файл целиком: действует last-known-good,
    на холодном старте — False. Отсутствие файла — валидное состояние «все False».
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


def _new_flag(name: str) -> bool:
    """Флаг новой политики: явный env (0/false/no/off, 1/true/yes/on) > JSON bool > False."""
    env = os.environ.get(_NEW_FLAG_ENV[name], "").strip().lower()
    if env in _ENV_TRUE:
        return True
    if env in _ENV_FALSE:
        return False
    return bool(getattr(_runtime_snapshot(), name))


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


def _transcript_anchor(cid: str) -> tuple[int, int] | None:
    """(наибольший step_index, размер файла) транскрипта до старта хода.

    Нет файла — (-1, 0); ошибка чтения — None.
    """
    path = _transcript_path(cid)
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


def _prespawn_plan(cid: str, resumed: bool) -> _TurnPlan:
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
    anchor = _transcript_anchor(cid)
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


@final
class _StepState:
    """Состояние одного шага планировщика (общее для SQLite и транскрипта).

    Текст мышления не хранится: только длины и sha256. observed_* — последний
    SQLite-снимок (любой режим), delivered_* — реально отданное клиенту.
    """

    def __init__(self) -> None:
        self.blob_len: int = -1
        self.blob_sha: str = ""
        self.observed_len: int = 0
        self.observed_sha: str = ""
        self.observed_final: bool = False
        self.delivered_len: int = 0
        self.delivered_sha = hashlib.sha256()
        self.final_len: int = 0
        self.final_sha: str = ""
        self.diverged: bool = False
        self.finalized: bool = False
        self.sql_seen: bool = False
        self.sql_done: bool = False
        self.canary_done: bool = False


_STEPS_SQL = (
    "SELECT idx, status, length(step_payload) AS blob_len, "
    + "CASE WHEN length(step_payload) <= %d THEN step_payload ELSE NULL END AS step_payload "
    + "FROM steps WHERE step_type = %d AND idx >= ? AND status IN (%d, %d) "
    + "ORDER BY idx ASC LIMIT %d"
) % (
    MAX_STEP_BLOB_BYTES,
    STEP_TYPE_PLANNER,
    STEP_STATUS_GENERATING,
    STEP_STATUS_DONE,
    SQLITE_ROW_LIMIT,
)


@final
class _ArbStep:
    """Канонический шаг арбитра: источник-создатель, выданный префикс, заморозка."""

    __slots__ = ("origin", "emitted", "frozen")

    def __init__(self, origin: str) -> None:
        self.origin = origin
        self.emitted = ""
        self.frozen = False


@final
class _ContentArbiter:
    """Двухуровневый арбитр planner-текста двух источников (stdout и transcript), AD-001.

    Вызывается под `Run._emit_lock`; ввода-вывода внутри нет. Кандидат — кумулятивный
    снимок текста шага.

    Уровень 1 — ключ `(turn_id, cid, step_idx)` при валидном `step_idx >= 0`: равный
    снимок или его префикс дают 0 байт, расширение — только суффикс, непрефиксное
    расхождение замораживает шаг (без повтора старого префикса и склейки мусора).

    Уровень 2 — turn-level: кандидат без валидного idx (None/<0/не-int) либо со
    «чужим» idx сверяется со снимками шагов, созданных ДРУГИМ источником (при idx
    None — любым): равный/префикс -> 0 байт, расширение последнего снимка -> суффикс;
    совпавший шаг получает alias (source, idx) -> канонический watermark. Два
    валидных шага одного источника с одинаковым текстом сохраняются оба.

    Индексы: equality — dict, префикс — bisect по отсортированным снимкам; обхода
    всей истории на каждый чанк нет. При исчерпании лимитов приём прекращается с
    явным `overflow` (accepted-текст молча не отбрасывается и не переотдаётся).
    """

    def __init__(self, turn_id: str) -> None:
        self.turn_id = turn_id
        self.by_key: dict[tuple[str, str, int], _ArbStep] = {}
        self.step_count = 0
        self.eq_index: dict[str, list[_ArbStep]] = {}
        self.sorted_texts: list[str] = []
        # Те же индексы в разрезе источника-создателя: кандидат с валидным idx
        # сверяется только с шагами ДРУГИХ источников, без скана одноимённых.
        self._eq_by_source: dict[str, dict[str, list[_ArbStep]]] = {}
        self._sorted_by_source: dict[str, list[str]] = {}
        self.retained_divergent: list[str] = []
        self.retained_divergent_bytes = 0
        self.last_step: _ArbStep | None = None
        self.last_by_source: dict[str, _ArbStep] = {}
        self.chunks: list[str] = []
        self.bytes_total = 0
        self.overflow = False
        self.divergences = 0
        self.probes = 0

    def _set_overflow(self, why: str) -> None:
        if not self.overflow:
            self.overflow = True
            _log(f"content-overflow turn={self.turn_id[:8] or '-'} why={why}")

    def _retain_divergent(self, text: str) -> None:
        """Удержать расходящийся текст (до MAX_RETAINED_DIVERGENT_BYTES суммарно)."""
        room = MAX_RETAINED_DIVERGENT_BYTES - self.retained_divergent_bytes
        if room <= 0 or not text:
            return
        data = text.encode("utf-8")
        if len(data) > room:
            text = data[:room].decode("utf-8", "ignore")
            data = text.encode("utf-8")
        if text:
            self.retained_divergent.append(text)
            self.retained_divergent_bytes += len(data)

    def retained_divergent_text(self) -> str:
        return "".join(self.retained_divergent)

    @staticmethod
    def _drop(
        eq: dict[str, list[_ArbStep]],
        texts: list[str],
        step: _ArbStep,
        old: str,
    ) -> None:
        bucket = eq.get(old)
        if bucket is None:
            return
        bucket.remove(step)
        if not bucket:
            del eq[old]
            pos = bisect.bisect_left(texts, old)
            if pos < len(texts) and texts[pos] == old:
                del texts[pos]

    @staticmethod
    def _put(
        eq: dict[str, list[_ArbStep]], texts: list[str], step: _ArbStep, text: str
    ) -> None:
        bucket = eq.setdefault(text, [])
        if not bucket:
            bisect.insort(texts, text)
        bucket.append(step)

    def _unindex(self, step: _ArbStep) -> None:
        old = step.emitted
        if not old:
            return
        self._drop(self.eq_index, self.sorted_texts, step, old)
        self._drop(
            self._eq_by_source.setdefault(step.origin, {}),
            self._sorted_by_source.setdefault(step.origin, []),
            step,
            old,
        )

    def _index(self, step: _ArbStep, text: str) -> None:
        self._put(self.eq_index, self.sorted_texts, step, text)
        self._put(
            self._eq_by_source.setdefault(step.origin, {}),
            self._sorted_by_source.setdefault(step.origin, []),
            step,
            text,
        )

    def _eligible(self, step: _ArbStep, source: str, idx: int | None) -> bool:
        self.probes += 1
        return idx is None or step.origin != source

    def _match(self, source: str, idx: int | None, text: str) -> _ArbStep | None:
        """Шаг, к которому относится кандидат без прямого ключа (уровень 2)."""
        if idx is None:
            found = self._scan(self.eq_index, self.sorted_texts, source, idx, text)
        else:
            # Валидный idx: подходят только шаги других источников; одноимённые
            # (N одинаковых шагов одного источника) не просматриваются вовсе.
            found = None
            for other, eq in self._eq_by_source.items():
                if other == source:
                    continue
                found = self._scan(eq, self._sorted_by_source[other], source, idx, text)
                if found is not None:
                    break
        if found is not None:
            return found
        refs: list[_ArbStep] = []
        if self.last_step is not None:
            refs.append(self.last_step)
        for other, step in self.last_by_source.items():
            if other != source and step not in refs:
                refs.append(step)
        for step in refs:
            if (
                step.emitted
                and text.startswith(step.emitted)
                and self._eligible(step, source, idx)
            ):
                return step
        return None

    def _scan(
        self,
        eq: dict[str, list[_ArbStep]],
        texts: list[str],
        source: str,
        idx: int | None,
        text: str,
    ) -> _ArbStep | None:
        for step in eq.get(text, ()):
            if self._eligible(step, source, idx):
                return step
        pos = bisect.bisect_left(texts, text)
        while pos < len(texts) and texts[pos].startswith(text):
            for step in eq[texts[pos]]:
                if self._eligible(step, source, idx):
                    return step
            pos += 1
        return None

    def _advance(self, step: _ArbStep, source: str, text: str) -> str:
        if step.frozen:
            return ""
        prefix = step.emitted
        if text == prefix or (len(text) < len(prefix) and prefix.startswith(text)):
            return ""
        if not text.startswith(prefix):
            step.frozen = True
            self._retain_divergent(text)
            self.divergences += 1
            _log(f"content-divergence turn={self.turn_id[:8] or '-'} source={source}")
            return ""
        suffix = text[len(prefix) :]
        size = len(suffix.encode("utf-8"))
        if self.bytes_total + size > MAX_CONTENT_BYTES_PER_TURN:
            self._set_overflow("bytes")
            return ""
        self._unindex(step)
        step.emitted = text
        self._index(step, text)
        self.chunks.append(suffix)
        self.bytes_total += size
        self.last_step = step
        self.last_by_source[source] = step
        return suffix

    def offer(self, source: str, step_index: object, text: str, cid: str = "") -> str:
        """Кумулятивный снимок -> новый суффикс ('' — дубль, префикс или заморозка)."""
        if self.overflow or not text:
            return ""
        idx = (
            step_index
            if isinstance(step_index, int)
            and not isinstance(step_index, bool)
            and step_index >= 0
            else None
        )
        key = (self.turn_id, cid, idx) if idx is not None else None
        step = self.by_key.get(key) if key is not None else None
        if step is None:
            step = self._match(source, idx, text)
            if step is None:
                if self.step_count >= MAX_CONTENT_STEPS:
                    self._set_overflow("steps")
                    return ""
                step = _ArbStep(source)
                self.step_count += 1
            if key is not None:
                if len(self.by_key) >= 4 * MAX_CONTENT_STEPS:
                    self._set_overflow("aliases")
                    return ""
                self.by_key[key] = step
        return self._advance(step, source, text)

    def reconcile_result(self, text: str) -> str:
        """`result.response` как агрегат: досылается только то, чего ещё не было выдано."""
        if self.overflow or not text:
            return ""
        emitted = "".join(self.chunks)
        if not emitted:
            if self.step_count >= MAX_CONTENT_STEPS:
                self._set_overflow("steps")
                return ""
            self.step_count += 1
            return self._advance(_ArbStep("result"), "result", text)
        if text == emitted or emitted.startswith(text):
            return ""
        if text.startswith(emitted):
            if self.step_count >= MAX_CONTENT_STEPS:
                self._set_overflow("steps")
                return ""
            self.step_count += 1
            return self._advance(_ArbStep("result"), "result", text[len(emitted) :])
        if text in self.eq_index:
            self.probes += 1
            return ""
        pos = bisect.bisect_left(self.sorted_texts, text)
        if pos < len(self.sorted_texts) and self.sorted_texts[pos].startswith(text):
            self.probes += 1
            return ""
        last = self.last_step
        if last is not None and last.emitted and text.startswith(last.emitted):
            return self._advance(last, "result", text)
        self._retain_divergent(text)
        self.divergences += 1
        _log(f"content-divergence turn={self.turn_id[:8] or '-'} source=result")
        return ""


def _safe_tool_name(raw: object) -> str:
    """Имя инструмента для маркера: только закрытый список, всё остальное -> `tool`."""
    if not isinstance(raw, str):
        return "tool"
    name = raw.strip()
    if (
        not name
        or len(name) > 128
        or name[0] in "/."
        or ".." in name
        or re.fullmatch(r"[A-Za-z0-9_:./-]+", name) is None
    ):
        return "tool"
    bare = re.split(r"[:./]", name)[-1]
    if bare in TOOL_NAME_ALLOWLIST or _SAFE_MCP_TOOL_RE.fullmatch(bare) is not None:
        return bare
    return "tool"


def _format_tool_marker(safe_name: str) -> str:
    return "\n[🔧 tool: %s — done]\n" % safe_name


@final
class _ToolProgress:
    """Дедупликация DONE нативных инструментов хода и безопасный маркер (AD-002).

    Идентичность — `(turn_id, cid, step_index)`; без валидного `step_index` —
    `("id", call_id)`, затем монотонный `("ord", fallback_ordinal)` из `Run._pump`,
    иначе уникальный `("anon", n)` (событие не теряется, но тоже под потолком
    `max_markers`). Имя инструмента ключом не является. Ни args, ни result, ни пути
    в маркер не попадают.

    Двухфазный учёт: `marker(ev, commit=False)` ключ лишь резервирует, а `commit()`
    расходует лимит только после успешной записи маркера клиенту.
    """

    def __init__(
        self, turn_id: str, cid: str, max_markers: int = MAX_TOOL_MARKERS_PER_TURN
    ) -> None:
        self.turn_id = turn_id
        self.cid = cid
        self.max_markers = max_markers
        self._seen: set[tuple[object, ...]] = set()
        self._anon_seq = 0
        self._pending_key: tuple[object, ...] | None = None

    def _key_for(self, ev: dict[str, object]) -> tuple[object, ...]:
        step = _as_int(ev.get("step_index"))
        if step is not None and step >= 0:
            return (self.turn_id, self.cid, step)
        raw_id = ev.get("call_id") or ev.get("tool_call_id") or ev.get("id")
        if isinstance(raw_id, (str, int)) and str(raw_id).strip():
            return ("id", str(raw_id).strip())
        ordinal = _as_int(ev.get("fallback_ordinal"))
        if ordinal is not None:
            return ("ord", ordinal)
        self._anon_seq += 1
        return ("anon", self._anon_seq)

    def marker(self, event: object, *, commit: bool = True) -> str | None:
        """Строка маркера или None (дубль DONE того же шага / лимит маркеров)."""
        self._pending_key = None
        if not isinstance(event, dict):
            return None
        ev = cast("dict[str, object]", event)
        key = self._key_for(ev)
        if key in self._seen or len(self._seen) >= self.max_markers:
            return None
        if commit:
            self._seen.add(key)
        else:
            self._pending_key = key
        return _format_tool_marker(_safe_tool_name(ev.get("name")))

    def commit(self, event: object | None = None) -> None:
        """Засчитать маркер после успешной записи (ключ из последнего `commit=False`)."""
        key = self._pending_key
        self._pending_key = None
        if key is None and isinstance(event, dict):
            key = self._key_for(cast("dict[str, object]", event))
        if key is not None and len(self._seen) < self.max_markers:
            self._seen.add(key)


@final
class _TranscriptTail:
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
    ) -> None:
        self.emit = emit
        # PLANNER_RESPONSE.content -> арбитр (AD-001); None — прежнее поведение.
        self.emit_content = emit_content
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
        self._interrupted: bool = False
        self._active_conn: sqlite3.Connection | None = None
        self._conn_lock = threading.Lock()
        self._db_path: Path | None = None
        self._open_fail_logged: bool = False
        self._oversize_logged: set[int] = set()
        self._finished: bool = False
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
                    self._offset = _transcript_path(cid).stat().st_size
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
        path = _transcript_path(self.cid)
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

    def _emit_record(self, raw: bytes) -> None:
        line = raw.strip()
        if not line:
            return
        if (
            b"PLANNER_RESPONSE" not in line
            and b"END_TURN" not in line
            and b"TURN_COMPLETE" not in line
        ):
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
            return
        content = rec.get("content")
        emit_content = self.emit_content
        if emit_content is not None and isinstance(content, str) and content.strip():
            _ = emit_content(
                idx, content
            )  # live planner-текст, независимо от tool_calls
        if idx is None:
            return
        if isinstance(content, str) and content.strip() and not rec.get("tool_calls"):
            self.final_planner = True
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
    ):
        launcher = _launcher()
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        work_dir = cwd if (cwd and os.path.isdir(cwd)) else str(WORKSPACE)
        self.work_dir = work_dir
        self.stdin_line = _ndjson_user_line(prompt)
        cmd = [
            launcher,
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--dangerously-skip-permissions",
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
        # Водяной знак resume снимается ДО spawn: история разговора не переотдаётся.
        plan = _prespawn_plan(self.run_cid, bool(self.run_cid))
        if self.run_cid and not _cid_acquire(self.run_cid, self.turn_id):
            plan.anchored = False
            plan.reason = "cid_busy"
        try:
            self.proc = subprocess.Popen(
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
        # Последний виденный текст agent_response по id шага: CLI присылает
        # накопительный снимок, новым считается только хвост сверх него.
        self._text_seen: dict = {}
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
        self._arbiter = _ContentArbiter(self.turn_id)
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
        """
        size = len(delta.encode("utf-8"))
        outcome = ""
        log_cap = False
        with self._emit_lock:
            if self.drain_closed:
                outcome = "late"
            elif self._reasoning_bytes + size > MAX_REASONING_BYTES_PER_TURN:
                outcome = "cap"
                log_cap = not self._cap_logged
                self._cap_logged = True
            else:
                self._reasoning_bytes += size
                self.q.put(("reasoning", delta))
                if on_delivered is not None:
                    on_delivered()
                return True
            total = self._reasoning_bytes
        cid8 = self._tail.cid[:8] or "-"
        if outcome == "late":
            _log(f"reasoning-late-drop cid={cid8} step={idx} len={len(delta)}")
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
                self.q.put(("text", suffix))
        return True

    def _offer_transcript(self, step_index: int | None, text: str) -> bool:
        return self.offer_content("transcript", step_index, text)

    def reconcile_result(self, text: str) -> str:
        """Недостающий хвост `result.response` относительно уже принятого арбитром."""
        with self._emit_lock:
            return self._arbiter.reconcile_result(text)

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
        self._tail.drain_deadline = started + min(budget_s, DRAIN_WINDOW_S)
        self._proc_done.set()
        thread = self._tail.thread
        if thread is not threading.current_thread():
            thread.join(timeout=max(0.0, budget_s - (time.monotonic() - started)))
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

    def _pump(self) -> None:
        """Разбор NDJSON agy 1.3.1.

        `step_update.agent_response` несёт накопительный `text_delta` — наружу
        уходит только хвост. `step_update.tool` — трассировка нативного
        инструмента (в stderr моста). `result` — финальный текст, usage, ошибка.

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
                    tools = (
                        cast("list[object]", tools_raw)
                        if isinstance(tools_raw, list)
                        else []
                    )
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
                    step = (
                        ev.get("step_update")
                        if isinstance(ev.get("step_update"), dict)
                        else {}
                    )
                    kind = step.get("step_type")
                    if kind == "agent_response" and step.get("text_delta"):
                        if self.content_streaming:
                            _ = self.offer_content(
                                "stdout",
                                _as_int(step.get("step_index")),
                                str(step["text_delta"]),
                            )
                        else:
                            suffix = _reasoning_suffix(
                                self._text_seen,
                                str(step.get("step_index", "")),
                                str(step["text_delta"]),
                            )
                            if suffix:
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
                            call_id = (
                                str(raw_id).strip()
                                if isinstance(raw_id, (str, int))
                                else ""
                            )
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
            self._tail.drain_deadline = t_exit + DRAIN_WINDOW_S
            self._proc_done.set()
            self._join_source(t_exit)
            if rc is None:
                rc = 0 if result_ev else 1
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
    """Хвост накопительного снимка текста.

    Пустой результат означает «дубликат, не эмитить»."""
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


class Handler(BaseHTTPRequestHandler):
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
        """Занять слот исполнения; '' — успех, иначе причина отказа.

        При extended_timeout_enabled ожидание не длиннее остатка бюджета запроса
        за вычетом резерва drain + финального flush.
        """
        if _slots.acquire(blocking=False):
            return ""
        deadline = time.monotonic() + QUEUE_TIMEOUT_S
        t_req_start = self._t_req_start
        if t_req_start is not None and _new_flag("extended_timeout_enabled"):
            deadline = min(deadline, t_req_start + T_REQ_BUDGET_S - T_RESERVE_S)
        while time.monotonic() < deadline:
            if _slots.acquire(timeout=1.0):
                return ""
            if keepalive is not None and not keepalive():
                return "client_gone"
        return "queue_timeout"

    def _execute(
        self, run: Run, on_text, on_tool_trace, on_reasoning, keepalive
    ) -> dict:
        """Гнать ход до конца; сквозной таймаут TIMEOUT_S на весь ход.

        Колбэки возвращают False, если клиент ушёл.
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
        result_error = ""
        result_error_at = 0.0
        tool_events = 0
        last_ka = time.monotonic()
        last_wd_check = time.monotonic()
        deadline = time.monotonic() + TIMEOUT_S
        policy = getattr(run, "policy", None)
        content_streaming = bool(getattr(run, "content_streaming", False))
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

        def finish(
            name: str, rc: int, err: str = "", limit: float | None = None
        ) -> dict:
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
            if _client_gone(self.connection):
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
                if result_error:
                    return state("agy_error", 1, result_error)
                if not result_ev and raw_result:
                    result_ev = raw_result
                if content_streaming:
                    # Хвост транскрипта, записанный прямо перед done, дренируется
                    # ДО reconcile: result.response — агрегат, досылается лишь недостающее.
                    drain = getattr(run, "terminal_drain", None)
                    if callable(drain):
                        deliver(list(drain(T_DRAIN_MAX_S)))
                    add_content(run.reconcile_result(final_text))
                elif not pieces and final_text:
                    add_content(final_text)
                if gone[0]:
                    return state("client_gone", 1)
                time.sleep(0.05)
                err = "".join(run.err_box).strip()
                status = str(result_ev.get("status") or "").upper()
                if rc != 0 and (status == "ERROR" or not pieces):
                    return state(
                        "agy_error",
                        rc,
                        (str(result_ev.get("error") or "") or err)[:500],
                    )
                return state("done", rc, err)

    def _log_done(
        self, model: str, out: dict[str, object], t0: float, tag: str
    ) -> None:
        """Одна строка done на каждом выходе _run_once (O-EXIT)."""
        conversation = str(out.get("conversation_id") or "-")[:8]
        out_bytes = len(str(out.get("text") or "").encode())
        _log(
            f"done model={model} rc={out.get('rc')} state={out.get('state')} "
            f"conversation={conversation} "
            f"turns={out.get('num_turns')} tool_events={out.get('tool_events')} "
            f"out_bytes={out_bytes} "
            f"wall_s={time.monotonic() - t0:.1f} "
            f"err={_err_summary(out.get('err'))!r} {tag}"
        )

    def _run_once(
        self, ctx: dict, on_text, on_tool_trace, on_reasoning, keepalive
    ) -> dict:
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
            if images and img_dir is not None:
                # Флаг и proof могли смениться, пока ход ждал слот: повторная проверка
                # до mkdir и spawn.
                gate = _image_gate(cast(str, model), cast(str, effort))
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
                    failed = _terminal_state("image_spool_error", str(exc))
                    self._log_done(
                        cast(str, ctx["model"]), failed, t_enter, cast(str, ctx["tag"])
                    )
                    return failed
            _retry_credit()
            for attempt in (1, 2):
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
                try:
                    out = self._execute(
                        run, on_text, on_tool_trace, on_reasoning, keepalive
                    )
                    finalize = ctx.get("finalize_timeout")
                    if finalize is not None and out.get("state") in (
                        "timeout",
                        "idle_timeout",
                    ):
                        # Graceful-финал пишется ДО зачистки процесса: kill/reap не
                        # съедает окно финальной записи. Внутренний state/rc не меняются.
                        try:
                            finalize(out)
                        except Exception as exc:  # noqa: BLE001
                            _log(f"graceful-finalize-error err={type(exc).__name__}")
                finally:
                    run.close()
                if out["state"] == "done":
                    break
                # Выдача клиенту: текст, tool_calls или уже отданное в поток мышление.
                # JSON-режим мышление клиенту ещё не отдавал — там повтор безопасен.
                delivered = bool(
                    out.get("text")
                    or out.get("tool_calls")
                    or (ctx.get("stream") and out.get("reasoning"))
                )
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
            if (
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
    def _usage_payload(usage: dict) -> dict:
        """usage agy -> OpenAI-поля. thinking_tokens прибавляем к completion."""
        return {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0)
            + usage.get("thinking_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    @staticmethod
    def _error_body(out: dict) -> Any:
        st = out.get("state")
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
        if out.get("rc") != 0 or not out.get("text"):
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
                "images": any(_model_supports_images(mid) for mid in FLEET_MODELS),
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
            order = [MODEL_ID] + [mid for mid in FLEET["order"] if mid != MODEL_ID]
            image_flags: list[bool] = []
            for mid in order:
                model = FLEET["models"][mid]
                supports = _model_supports_images(cast(str, mid))
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
                200, {"object": "list", "data": data, "images": any(image_flags)}
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
            messages = (
                cast("list[object]", messages_raw)
                if isinstance(messages_raw, list)
                else []
            )
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
            tools_count = 0 if _tool_choice_none(req.get("tool_choice")) else len(tools)
            full_prompt = _messages_to_prompt(messages, images)
            extra = (
                req.get("extra_body") if isinstance(req.get("extra_body"), dict) else {}
            )
            cwd = str(extra.get("cwd") or "")
            if len(cwd) > CWD_MAX_LEN:
                cwd = ""
            conversation_id = str(
                extra.get("conversation_id") or req.get("conversation_id") or ""
            )
            # Горячие сессии — только агентным запросам с инструментами. Фоновые и
            # plain-запросы (в т. ч. генерация заголовка DSH, tools=0) стор не читают
            # и не пишут: ни claim, ни commit, ни invalidate.
            use_session_store = tools_count > 0
            sess_key: tuple[str, str, str] | None = (
                (cast(str, model_id), cwd, cast(str, effort))
                if use_session_store
                else None
            )
            is_resumed = False
            prompt = full_prompt
            if conversation_id:
                if _cid_acquire(conversation_id, turn_id):
                    owned_cid = conversation_id
                else:
                    # cid занят другим активным ходом: два хода не делят один разговор.
                    _log(f"cid-busy-fresh cid={conversation_id[:8]}")
                    conversation_id = ""
            elif sess_key is not None:
                use_cid = _session_claim(sess_key, turn_id)
                if use_cid:
                    conversation_id = use_cid
                    is_resumed = True
                    prompt = _get_resumed_turn_prompt(messages, images)
            ctx: dict[str, object] = {
                "t_req_start": t_req_start,
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
            }
            if ctx["stream"]:
                self._serve_sse(ctx)
            else:
                self._serve_json(ctx)
        finally:
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

        def build_payload(
            out: dict, content: str, reasoning: str, finish_reason: str
        ) -> dict:
            message = {"role": "assistant", "content": content}
            if reasoning:
                # OpenAI-совместимое поле мышления: Harness читает его из сообщения
                # ассистента так же, как из дельты потока.
                message["reasoning_content"] = reasoning
            payload = {
                "id": f"chatcmpl-agy-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": ctx["model"],
                "choices": [
                    {"index": 0, "message": message, "finish_reason": finish_reason}
                ],
                "usage": self._usage_payload(out.get("usage") or {}),
            }
            if out.get("conversation_id"):
                payload["conversation_id"] = out["conversation_id"]
            return payload

        def finalize_timeout(out: dict) -> None:
            """Graceful-финал timeout/idle_timeout: 200/length (идемпотентно, до run.close())."""
            state = out.get("state")
            if out.get("graceful_done") or state not in ("timeout", "idle_timeout"):
                return
            if not _new_flag("graceful_timeout_on_partial"):
                return
            # Остаток источников из terminal drain + полезный partial -> 200/length.
            retained_text, retained_reasoning = consume_retained(out)
            content = str(out.get("text") or "")
            base_reasoning = str(out.get("reasoning") or "")
            reasoning = base_reasoning + retained_reasoning + "".join(markers)
            if not (content.strip() or reasoning.strip() or retained_text.strip()):
                return  # полная тишина: прежняя ошибка 504
            content += retained_text
            content += self._graceful_notice(str(state), out.get("timeout_limit_s"))
            self._arm_flush_window(ctx)
            out["graceful_done"] = True
            _log(f"graceful-timeout state={state} mode=json")
            if not self._prepare_flush_write():
                return
            self._send(200, build_payload(out, content, reasoning, "length"))

        ctx["finalize_timeout"] = finalize_timeout
        out = self._run_once(ctx, lambda _v: True, on_tool_trace, lambda _r: True, None)
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
        err = self._error_body(out)
        if err is not None:
            self._send(err["code"], {"error": err})
            return
        self._send(
            200, build_payload(out, str(out.get("text") or ""), reasoning, "stop")
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
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError, OSError):
            _log("client gone before headers")
            return

        def chunk(
            delta: dict,
            finish=None,
            usage: dict | None = None,
            conversation_id: str = "",
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
            return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"

        # Счётчики полезной выдачи растут только после УСПЕШНОЙ записи клиенту
        # (role-chunk, keepalive и пустые/whitespace-дельты не в счёт).
        emitted_content = [0]
        emitted_reasoning_or_tool = [0]
        progress = _ToolProgress(
            str(ctx.get("turn_id") or ""), str(ctx.get("conversation_id") or "")
        )

        def on_text(value: str) -> bool:
            ok = self._emit(chunk({"content": value}))
            if ok and value.strip():
                emitted_content[0] += len(value.strip())
            return ok

        def on_reasoning(value: str) -> bool:
            # Мышление шага: Harness читает первое непустое из
            # reasoning_content|reasoning|reasoning_text — отдаём только первое.
            ok = self._emit(chunk({"reasoning_content": value}))
            if ok and value.strip():
                emitted_reasoning_or_tool[0] += 1
            return ok

        def on_tool_trace(event: dict) -> bool:
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

        def keepalive() -> bool:
            return self._emit(": keepalive\n\n")

        def finalize_timeout(out: dict) -> None:
            """Graceful-финал timeout/idle_timeout после полезной выдачи (идемпотентно).

            Один общий arbiter-досыл, один notice, один `finish_reason="length"`, один
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
                    ok = on_text(str(payload))
                elif kind == "reasoning":
                    ok = on_reasoning(str(payload))
                elif kind == "tool_trace":
                    ok = on_tool_trace(payload)
                if not ok:
                    break
            reason = str(out.get("state"))
            conv_id = str(out.get("conversation_id") or "")
            if ok:
                ok = self._emit(
                    chunk(
                        {
                            "content": self._graceful_notice(
                                reason, out.get("timeout_limit_s")
                            )
                        }
                    )
                )
            if ok:
                ok = self._emit(chunk({}, "length", conversation_id=conv_id))
            if ok:
                _ = self._emit("data: [DONE]\n\n")
            out["graceful_done"] = True
            _log(f"graceful-timeout state={reason} mode=sse ok={int(bool(ok))}")

        ctx["finalize_timeout"] = finalize_timeout
        if not self._emit(chunk({"role": "assistant", "content": ""})):
            return
        out = self._run_once(ctx, on_text, on_tool_trace, on_reasoning, keepalive)
        if out.get("state") == "client_gone":
            _log("client gone mid-stream, child killed")
            return
        finalize_timeout(out)  # страховка, если _run_once не вызвал hook
        if out.get("graceful_done"):
            return
        err = self._error_body(out)
        if err is None:
            conv_id = str(out.get("conversation_id") or "")
            self._emit(chunk({}, "stop", conversation_id=conv_id))
            # Harness считает tok/s и % контекста только из usage в потоке
            # (dsh-llm-pi-ai toStreamChunks: usage-chunk -> session usage).
            # Шлём только при ненулевых токенах, чтобы пустой usage от agy
            # не превращался в ложные «0 tok/s / 0%».
            usage = self._usage_payload(out.get("usage") or {})
            if usage["prompt_tokens"] or usage["completion_tokens"]:
                self._emit(chunk({}, "stop", usage, conversation_id=conv_id))
        else:
            self._emit(
                "data: " + json.dumps({"error": err}, ensure_ascii=False) + "\n\n"
            )
        self._emit("data: [DONE]\n\n")


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


def _sweep_workspace(cutoff_s: float = 3600.0) -> int:
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
    _ = _sweep_workspace()
    threading.Thread(target=_sweep_loop, daemon=True).start()
    # Хеш бинаря agy считается заранее, чтобы первый image-ход не платил за него.
    threading.Thread(target=_file_sha256, args=(AGY_BIN,), daemon=True).start()
    _log(f"fleet_sha256={FLEET['sha256']} models={len(FLEET['order'])}")
    try:
        _launcher()
    except LauncherUnavailable:
        _log(f"launcher_missing path={LAUNCHER} (requests will fail with 503)")
    signal.signal(signal.SIGTERM, _kill_all)
    signal.signal(signal.SIGINT, _kill_all)
    api_key_present = "yes" if AUTH_KEY else "no"
    server = Server((HOST, PORT), Handler)
    _log(
        f"listen {HOST}:{PORT} model={MODEL_ID} max_concurrent={MAX_CONCURRENT} "
        f"queue_timeout={QUEUE_TIMEOUT_S}s timeout={TIMEOUT_S}s keepalive={KEEPALIVE_S}s "
        f"api_key={api_key_present}"
    )
    print(f"[agy-bridge] listening on http://{HOST}:{PORT}/v1", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
