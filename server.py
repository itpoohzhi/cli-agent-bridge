#!/usr/bin/env python3
"""OpenAI-совместимый мост к Factory Droid CLI (`droid exec`) для DeepSeek Harness.

Один запрос /v1/chat/completions = один ход в долгоживущем процессе
`droid exec --input-format stream-jsonrpc --output-format stream-jsonrpc`
(по одному процессу на keyed-чат; ключ чата — `prompt_cache_key` запроса, в argv/пути
не попадает: только sha256). Процесс запускается через канонический лончер
~/.config/factory-launch/droid-cli.sh (egress-пиннинг). В droid уходит только
непросмотренный суффикс истории; расхождение истории (форк, правка, компакция, смена
system/tools/cwd) = новая generation с replay. Idle-процесс гасится через
`DROID_DSH_BRIDGE_IDLE_SECONDS` (по умолчанию 2700 с), SID и файлы остаются, следующий
ход восстанавливается `load_session` того же SID. Без ключа, для title-запросов и для
запросов с изображениями — эфемерная чистая сессия с replay истории запроса.
Автономность даунстрим-исполнителя задаётся top-level полем `autonomy`
(`low|medium|high|off`, дефолт `high`); иное = 400 `unsupported_autonomy`.
`--skip-permissions-unsafe` не используется никогда; нативные tools droid отключены,
запросы разрешений отклоняются (`autoRejectPermissionRequests`).
Вывод хода удерживается до `agent_turn_completed` и затем отдаётся в OpenAI Chat
Completions (stream и не-stream); thinking транслируется в `reasoning_content`.

Каталог моделей — `fleet.json` (env `DROID_DSH_BRIDGE_FLEET`): читается один раз
при старте, структурно проверяется (класс I — отказ старта), уровни reasoning
строго берутся из каталога (никаких клампов и алиасов; `-r` передаётся всегда).
Изображения принимаются только по контракту: data-URL PNG, только роли user,
только для моделей с применимым proof (метод workspace-read); файлы кладутся
в per-run каталог `workspace/img-<uuid>` (0700/0600) и удаляются при любом исходе.

Мост эмулирует OpenAI function calling (дословно из claude-p-bridge): если запрос
содержит непустой `tools`, в промпт добавляется протокол и схемы инструментов.

Секреты с диска не читаются: ключ авторизации берётся только из окружения
DROID_DSH_BRIDGE_KEY (его подкладывает start.sh из ~/.dsh/.env); в окружение
дочернего процесса ключ не передаётся. FACTORY_API_KEY (headless-вход Droid
без интерактивного логина) наследуется потомком как есть — его подкладывает
start.sh из ~/.zshenv; `droid exec` читает его из окружения сам.
"""

from __future__ import annotations

import base64
import binascii
import collections
import fcntl
import functools
import hashlib
import itertools
import json
import os
import queue
import re
import select
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # пакеты core/ и adapters/ рядом с server.py
import b_guard  # noqa: E402  - охранник B: автоматический контур профилей DSH (RW-003)
from receipt_schema import (  # noqa: E402
    RECEIPT_PROBES,
    RECEIPT_SCHEMA,
    RPC_API_VERSION,
    SETTINGS_PROFILE,
    TOOLS_POLICY,
    settings_profile_digest,
    tools_policy_digest,
)

from adapters import ADAPTER_KINDS  # noqa: E402  - реестр видов адаптеров задан в коде
from core.backend_adapter import (  # noqa: E402
    AdapterRegistry,
    backend_entry_error,
)
from core.tool_emulation import (  # noqa: E402,F401  - общая эмуляция tools (MB-REQ-007), реэкспорт имён
    TOOL_CALL_CLOSE,
    TOOL_CALL_OPEN,
    ToolCallParser,
    _attachments_section,
    _flatten_content,
    _messages_to_prompt,
    _normalize_arguments,
    _normalize_tool_call,
    _parse_tool_call_block,
    _render_content,
    _render_message,
    _render_tool_call,
    _strip_code_fence,
    _tool_choice_name,
    _tool_choice_none,
    _tools_section,
    finalize_turn,
)

HOME = Path.home()
HOST = os.environ.get("DROID_DSH_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("DROID_DSH_BRIDGE_PORT", "9882"))
AUTH_KEY = os.environ.get("DROID_DSH_BRIDGE_KEY", "").strip()
LAUNCHER = os.environ.get(
    "DROID_LAUNCHER", str(HOME / ".config" / "factory-launch" / "droid-cli.sh")
)
FLEET_PATH = Path(
    os.environ.get("DROID_DSH_BRIDGE_FLEET", "") or str(ROOT / "fleet.json")
)
ENV_MODEL = os.environ.get("DROID_DSH_BRIDGE_MODEL", "").strip()
IMAGE_PROBE = os.environ.get("DROID_DSH_BRIDGE_IMAGE_PROBE", "") == "1"
WORKSPACE = ROOT / "workspace"
MAX_CONCURRENT = int(os.environ.get("DROID_DSH_BRIDGE_MAX_CONCURRENT", "4"))
QUEUE_TIMEOUT_S = int(os.environ.get("DROID_DSH_BRIDGE_QUEUE_TIMEOUT", "900"))
TIMEOUT_S = int(os.environ.get("DROID_DSH_BRIDGE_TIMEOUT", "1800"))
KEEPALIVE_S = float(os.environ.get("DROID_DSH_BRIDGE_KEEPALIVE", "15"))
# Таймаут первого события stream-json от `droid exec` (с момента старта процесса).
FIRST_TOKEN_TIMEOUT_S = float(
    os.environ.get("DROID_BRIDGE_FIRST_TOKEN_TIMEOUT_S", "90")
)
# Окно после успешного хода, в котором лончеру передаётся DROID_SKIP_PREFLIGHT=1.
PREFLIGHT_SKIP_WINDOW_S = 120.0

# Уровни reasoning, допустимые в каталоге (dev-контекст выбирает fleet.json).
EFFORT_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")
# Уровни автономности даунстрим-исполнителя: передаются в `autonomyLevel` RPC
# (`initialize_session`/`update_session_settings`) и сверяются read-back; дефолт high,
# `off` — read-only режим droid (Reviewer-пути).
AUTONOMY_LEVELS = ("low", "medium", "high")
AUTONOMY_OFF = "off"
AUTONOMY_DEFAULT = "high"
IMAGE_STATUSES = ("unsupported", "unverified", "probe", "confirmed")
# Известные сигнатуры изображений: нужны, чтобы отличить image_type_mismatch
# от unsupported_image_type (пиксели не декодируются, сторонних библиотек нет).
IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF8", "image/gif"),
)
KNOWN_IMAGE_MIMES = ("image/png", "image/jpeg", "image/gif", "image/webp")
# Реализован ровно один метод хранения вложений (C-09); расширение — только
# новым delta-пакетом Architect.
IMPLEMENTED_METHODS = {"workspace-read": 1}
METHOD_IMPL_VERSION = IMPLEMENTED_METHODS["workspace-read"]
IMAGE_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


class FleetViolation(Exception):
    """Структурное нарушение каталога (класс I): отказ старта."""

    def __init__(self, reason: str, model: str = "-"):
        super().__init__(reason)
        self.reason = reason
        self.model = model or "-"


def _validate_proof(model_id: str, images: dict, method: str, efforts: list) -> None:
    """Форма proof у confirmed-модели (класс I: confirmed_proof_malformed и др.)."""
    proof = images.get("proof")
    if proof is None:
        raise FleetViolation("confirmed_proof_missing", model_id)
    if not isinstance(proof, dict):
        raise FleetViolation("confirmed_proof_malformed", model_id)
    for key in (
        "droid_version",
        "droid_binary_sha256",
        "method",
        "impl_version",
        "formats",
    ):
        if key not in proof:
            raise FleetViolation("confirmed_proof_malformed", model_id)
    if not isinstance(proof.get("droid_version"), str) or not isinstance(
        proof.get("droid_binary_sha256"), str
    ):
        raise FleetViolation("confirmed_proof_malformed", model_id)
    if not re.fullmatch(r"[0-9a-f]{64}", str(proof.get("droid_binary_sha256") or "")):
        raise FleetViolation("confirmed_proof_malformed", model_id)
    if proof.get("method") != method:
        raise FleetViolation("confirmed_proof_malformed", model_id)
    if not isinstance(proof.get("impl_version"), int) or isinstance(
        proof.get("impl_version"), bool
    ):
        raise FleetViolation("confirmed_proof_malformed", model_id)
    formats = proof.get("formats")
    if not isinstance(formats, list) or not all(isinstance(f, str) for f in formats):
        raise FleetViolation("confirmed_proof_malformed", model_id)
    proven = proof.get("efforts_proven")
    if not isinstance(proven, list) or not all(isinstance(p, str) for p in proven):
        raise FleetViolation("confirmed_proof_malformed", model_id)
    if not proven or len(set(proven)) != len(proven):
        raise FleetViolation("confirmed_efforts_proven_invalid", model_id)
    if any(p not in efforts for p in proven):
        raise FleetViolation("confirmed_efforts_proven_invalid", model_id)


_FLEET_TOP_KEYS = frozenset(
    {
        "schema_version",
        "catalogue",
        "default_model",
        "policy_ref",
        "technical_ref",
        "image_limits",
        "admission",
        "backends",
        "models",
    }
)
_FLEET_MODEL_KEYS = frozenset(
    {
        "id",
        "backend",
        "name",
        "efforts",
        "default_effort",
        "context_window",
        "max_tokens",
        "input",
        "images",
        "policy_lines",
    }
)
# schema 2 = единственный неявный бэкенд droid (поведение прежнее, откат конфигурации без смены кода).
_IMPLICIT_DROID_BACKEND = {
    "kind": "droid",
    "enabled": True,
    "required": True,
    "owned_by": "factory-droid",
    "max_concurrent": 4,
}


def _build_backends(data: dict, schema: int) -> tuple:
    """Секция `backends` каталога (класс I) -> ({id: нормализованная запись}, порядок id).

    schema 2: секции нет (её появление — отказ), неявный бэкенд droid. schema 3: словарь
    `id -> запись`; kind только из реестра в коде (`ADAPTER_KINDS`), полная проверка записи —
    общей `backend_entry_error` (тот же код в `fleet_check`, RW-005): вложенные типы
    (`technical_ref` с комплектным pin, wrapper, proxy_port), флаги, `max_concurrent` и
    неизвестные ключи отвергаются ДО регистрации адаптера, а не падением на `.get()`.
    """
    if schema == 2:
        if "backends" in data:
            raise FleetViolation("backends_in_schema_2", "-")
        return {"droid": dict(_IMPLICIT_DROID_BACKEND)}, ["droid"]
    if set(data) - _FLEET_TOP_KEYS:
        raise FleetViolation("fleet_key_unknown", "-")
    raw = data.get("backends")
    if not isinstance(raw, dict) or not raw:
        raise FleetViolation("backends_invalid", "-")
    backends: dict = {}
    for backend_id, entry in raw.items():
        reason = backend_entry_error(backend_id, entry, ADAPTER_KINDS)
        if reason:
            raise FleetViolation(reason, str(backend_id))
        enabled = entry.get("enabled", True)
        required = entry.get("required", False)
        normalized = {
            key: value
            for key, value in entry.items()
            if key not in ("enabled", "required")
        }
        normalized.update(
            enabled=enabled,
            required=required,
            owned_by=entry.get("owned_by") or backend_id,
            max_concurrent=entry.get("max_concurrent", 1),
        )
        backends[backend_id] = normalized
    if not any(b["enabled"] for b in backends.values()):
        raise FleetViolation("backends_none_enabled", "-")
    return backends, list(backends)


def _build_catalog(data: Any) -> dict:
    """Проверить каталог (C-01, класс I) и вернуть нормализованный словарь."""
    if not isinstance(data, dict):
        raise FleetViolation("fleet_unreadable", "-")
    schema = data.get("schema_version")
    if isinstance(schema, bool) or schema not in (2, 3):
        raise FleetViolation("schema_version_invalid", "-")
    backends, backend_order = _build_backends(data, schema)
    limits = data.get("image_limits")
    if not isinstance(limits, dict):
        raise FleetViolation("limits_invalid", "-")
    for key in (
        "max_images",
        "max_image_bytes",
        "max_total_image_bytes",
        "max_body_bytes",
    ):
        if (
            not isinstance(limits.get(key), int)
            or isinstance(limits.get(key), bool)
            or limits[key] <= 0
        ):
            raise FleetViolation("limits_invalid", "-")
    if not isinstance(limits.get("types"), list) or not limits["types"]:
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
    seen: set = set()
    for item in raw_models:
        if not isinstance(item, dict):
            raise FleetViolation("model_invalid", "-")
        mid = item.get("id")
        if not isinstance(mid, str) or not mid:
            raise FleetViolation("model_invalid", "-")
        if mid in seen:
            raise FleetViolation("duplicate_id", mid)
        seen.add(mid)
        if schema == 3:
            if set(item) - _FLEET_MODEL_KEYS:
                raise FleetViolation("model_key_unknown", mid)
            backend_id = item.get("backend")
            if not isinstance(backend_id, str) or backend_id not in backends:
                raise FleetViolation("model_backend_unknown", mid)
        else:
            backend_id = "droid"
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
        if status in ("unsupported", "unverified"):
            if images.get("method") is not None or input_types != ["text"]:
                raise FleetViolation("status_inconsistent", mid)
        if status == "confirmed":
            method = images.get("method")
            if method is None:
                raise FleetViolation("confirmed_method_missing", mid)
            if "image" not in input_types or "text" not in input_types:
                raise FleetViolation("confirmed_input_missing", mid)
            _validate_proof(mid, images, method, efforts)
        if status == "probe":
            method = images.get("method")
            if (
                method is None
                or "image" not in input_types
                or "text" not in input_types
            ):
                raise FleetViolation("status_inconsistent", mid)
            if not IMAGE_PROBE:
                raise FleetViolation("probe_flag_missing", mid)
        method = images.get("method")
        if method is not None and method not in IMPLEMENTED_METHODS:
            raise FleetViolation("method_not_implemented", mid)
        if not backends[backend_id]["enabled"]:
            continue  # модели выключенного бэкенда проверены, но не публикуются
        models[mid] = {
            "id": mid,
            "backend": backend_id,
            "name": str(item.get("name") or mid),
            "efforts": [str(e) for e in efforts],
            "default_effort": str(item["default_effort"]),
            "context_window": int(item.get("context_window") or 0),
            "input": [str(t) for t in input_types],
            "images": {
                "status": str(status),
                "cli_registry": str(images.get("cli_registry") or ""),
                "method": method,
                "proof": images.get("proof"),
            },
        }
        order.append(mid)
    default_model = data.get("default_model")
    if not isinstance(default_model, str) or default_model not in models:
        raise FleetViolation("default_model_invalid", "-")
    if ENV_MODEL and ENV_MODEL not in models:
        raise FleetViolation("env_model_invalid", ENV_MODEL)
    technical_ref = (
        data.get("technical_ref") if isinstance(data.get("technical_ref"), dict) else {}
    )
    return {
        "schema_version": data.get("schema_version"),
        "catalogue": str(data.get("catalogue") or ""),
        "default_model": default_model,
        "backends": backends,
        "backend_order": backend_order,
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
        "technical_ref": {
            "droid_version": str(technical_ref.get("droid_version") or ""),
            "droid_binary_sha256": str(technical_ref.get("droid_binary_sha256") or ""),
            "droid_binary_path": str(technical_ref.get("droid_binary_path") or ""),
        },
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
    if catalog is None:
        sys.stderr.write("fleet_invalid model=- reason=fleet_unreadable\n")
        sys.stderr.flush()
        raise SystemExit(1)
    catalog["path"] = str(FLEET_PATH)
    catalog["sha256"] = hashlib.sha256(raw).hexdigest()
    return catalog


try:
    FLEET = _load_fleet()
except FleetViolation as violation:
    sys.stderr.write(
        f"fleet_invalid model={violation.model} reason={violation.reason}\n"
    )
    sys.stderr.flush()
    raise SystemExit(1)

MODEL_ID = ENV_MODEL or FLEET["default_model"]
# Реестр адаптеров включённых бэкендов (ADR 0002): каталог читается лениво, чтобы подмена FLEET
# стендом тестов действовала и на маршрутизацию; хост адаптеров — этот модуль.
BACKENDS = AdapterRegistry.from_fleet(
    FLEET, ADAPTER_KINDS, lambda: FLEET, sys.modules[__name__]
)

# Токеноподобные последовательности: длинные (>=24) и явные Factory-ключи `fk-`
# любой длины — короткий ключ иначе проходил мимо маскировщика в журнал.
_SECRET = re.compile(r"[A-Za-z0-9_\-]{24,}|fk-[A-Za-z0-9_\-]{4,}")
_NOISE = re.compile(
    r"NODE_TLS_REJECT_UNAUTHORIZED|--trace-warnings|^\(node:\d+\)", re.I
)

_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
_active = {}
_active_lock = threading.Lock()
_started = time.time()
# Монотонная метка последнего успешного хода (0.0 = не было / последний провалился).
_last_ok = [0.0]
# Байтовый бюджет admission; включается в main() (в тестах/импорте — None).
_budget = None
_sha_cache = {}
_sha_cache_lock = threading.Lock()

# ---- RPC-СОСТОЯНИЕ: долгоживущий `droid exec --input-format stream-jsonrpc` на чат.
# Ключ чата — prompt_cache_key запроса (никогда не путь/argv: только sha256).
# Часы и пауза подменяются в тестах (fake clock): idle-реап и ретраи 2/4 с не
# должны замедлять набор.
RPC_NAMESPACE = "droid-bridge/v1"
# Idle-гашение процесса чата (по monotonic времени последнего terminal/release).
IDLE_SECONDS = float(os.environ.get("DROID_DSH_BRIDGE_IDLE_SECONDS", "2700"))
REAPER_TICK_S = 1.0
# Тишина без событий ТЕКУЩЕГО хода после первого события (сбрасывают только они).
SILENCE_WATCHDOG_S = float(os.environ.get("DROID_BRIDGE_SILENCE_WATCHDOG_S", "120"))
# Ожидание ответа на служебный запрос (initialize/load/update/list_tools/add).
RPC_CALL_TIMEOUT_S = float(os.environ.get("DROID_BRIDGE_RPC_CALL_TIMEOUT_S", "60"))
# После interrupt ждём terminal столько, затем процесс закрывается принудительно.
INTERRUPT_GRACE_S = 3.0
# Не больше пяти restore на один SID: шестой — свежая generation (вторичный предел).
RESTORE_MAX = 5
# Общий грейс остановки моста (< exit timeout 5 с), SIGTERM->waitpid при вытеснении.
SHUTDOWN_GRACE_S = 4.5
TERM_WAIT_S = 2.0
KEY_MAX_LEN = 512
# Структурные признаки title-запроса DSH (F-512): размер сообщения не критерий.
TITLE_SYSTEM_PREFIX = (
    "Create a concise title for an AI coding-assistant session "
    "from the supplied human messages."
)
TITLE_USER_PREFIX = "Generate the session title from this JSON array of human messages:"
TITLE_MAX_TOKENS = 64
# Допуск Droid-бинаря (AD-010, RW-007): spawn только по receipt квалификации неизменяемого
# образа; `DROID_DSH_BRIDGE_RECEIPT_REQUIRED=0` отключает gate (только стенд/разработка).
RECEIPT_REQUIRED = os.environ.get("DROID_DSH_BRIDGE_RECEIPT_REQUIRED", "1") != "0"
# Байтовые бюджеты (AD-011/TM-020, RW-008): превышение — предусмотренная ошибка, процесс и
# слот возвращаются. Значения подбираются env; в тестах подменяются малыми.
MAX_RPC_LINE_BYTES = int(
    os.environ.get("DROID_BRIDGE_MAX_RPC_LINE_BYTES", str(8 << 20))
)
MAX_STDERR_BYTES = int(os.environ.get("DROID_BRIDGE_MAX_STDERR_BYTES", str(64 << 10)))
# Бюджет очереди событий; одна строка до MAX_RPC_LINE_BYTES принимается в пустую очередь (иначе
# легитимный ответ load_session крупнее 4 МиБ был бы недоставим), поэтому память очереди
# ограничена MAX_INBOX_BYTES + одной строкой.
MAX_INBOX_BYTES = int(os.environ.get("DROID_BRIDGE_MAX_INBOX_BYTES", str(4 << 20)))
MAX_TURN_TEXT_BYTES = int(
    os.environ.get("DROID_BRIDGE_MAX_TURN_TEXT_BYTES", str(10 << 20))
)
# Структурный предел строки RPC: число `{`/`[`/`,`/`:` вне строк. Строка из миллионов пустых объектов или
# чисел укладывается в MAX_RPC_LINE_BYTES, но json.loads раздул бы её в сотни МиБ объектов (RW-014, RW-010):
# отклоняется до разбора.
MAX_JSON_STRUCT_TOKENS = int(
    os.environ.get("DROID_BRIDGE_MAX_JSON_STRUCT_TOKENS", str(50_000))
)
# Условная стоимость записи/слота в бюджетах: поток пустых сообщений тоже упирается в лимит.
ENTRY_OVERHEAD_BYTES = 64
# Предел длины id сообщения в карантине событий (RW-009): длиннее — ошибка хода (id удерживается в памяти).
MAX_HELD_MID_CHARS = 1024
# Кусок вывода при сериализации ответа клиенту (JSON/SSE выдаются порциями, без второй полной копии).
DELIVERY_CHUNK_BYTES = 64 << 10
# Общий бюджет памяти готовых ответов, удерживаемых до конца выдачи клиенту (RW-011): T/L к этому
# моменту свободны, а медленные клиенты держат `out`. Исчерпан — 502 proxy_error.
MAX_DELIVERY_BYTES = int(
    os.environ.get("DROID_BRIDGE_MAX_DELIVERY_BYTES", str(256 << 20))
)
MAX_CHATS = int(os.environ.get("DROID_BRIDGE_MAX_CHATS", "4096"))
# Предел блока agent-instructions (REQ-003): больше — отказ до spawn/add (строгая граница).
INSTR_BLOCK_LIMIT = int(os.environ.get("DROID_DSH_BRIDGE_INSTR_LIMIT", "60000"))
# Не-KB формы cwd (WA/AB/DW): допустимый блок = maxBytes профиля минус запас (матрица b_guard);
# жёсткие 60 000 Б относятся только к блокам, целиком состоящим из копий канона (KB, REQ-003).
INSTR_NONKB_MARGIN = int(
    os.environ.get("DROID_DSH_BRIDGE_INSTR_MARGIN", str(b_guard.LINE_MARGIN_MIN))
)
GUARD_TICK_S = float(os.environ.get("DROID_DSH_BRIDGE_GUARD_TICK", "30"))
GUARD_PROFILES_DIR = os.environ.get(
    "DROID_DSH_BRIDGE_PROFILES_DIR", b_guard.PROFILES_DIR
)
GUARD_CANON = os.environ.get("DROID_DSH_BRIDGE_CANON", b_guard.CANON_PATH)
# Срез ожидания записи в stdin ребёнка: проверка отмены/закрытия между срезами.
RPC_WRITE_SLICE_S = 0.1
# Бюджет коротких служебных записей (interrupt/close/ответ на запрос разрешения).
RPC_SHORT_WRITE_S = 0.5
# Завершённые turnId живого процесса не вытесняются (вытесненный ID снова прошёл бы как «текущий»);
# при превышении предела процесс помечается retired и заменяется новым на границе хода.
FINISHED_TURNS_KEEP = 65536
LEADER_EXIT_GRACE_S = 0.5  # грейс читателя pipe после выхода лидера процесса

_clock = time.monotonic
_sleep = time.sleep
_shutting_down = False
_rpc_procs: dict = {}  # pid -> RpcProcess (под _active_lock): нужен для graceful-остановки


def _state_dir() -> Path:
    """Собственное хранилище моста; _sweep_workspace его не трогает (prompt-*/img-*)."""
    return WORKSPACE / "state"


def _work_dir_for(cwd: str, img_dir: Any) -> str:
    """Рабочий каталог процесса: per-run каталог картинок, иначе cwd, иначе workspace."""
    if img_dir is not None:
        return os.path.realpath(str(img_dir))
    work_dir = cwd if (cwd and os.path.isdir(cwd)) else str(WORKSPACE)
    return os.path.realpath(work_dir)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chain(head: str, digest: str) -> str:
    """Следующая голова хеш-цепочки потреблённой истории."""
    return hashlib.sha256((head + "|" + digest).encode("utf-8")).hexdigest()


def _key_hash(key: str) -> str:
    """Идентичность чата: sha256(namespace + ключ); сам ключ нигде не хранится."""
    return hashlib.sha256((RPC_NAMESPACE + "\0" + key).encode("utf-8")).hexdigest()


def _log(msg: str) -> None:
    """Диагностика в stderr (файлы вне каталога моста не создаём)."""
    try:
        sys.stderr.write(
            f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}\n"
        )
        sys.stderr.flush()
    except OSError:
        pass


def _mask_secrets(text: str) -> str:
    """Длинные токеноподобные последовательности -> ***."""
    return _SECRET.sub("***", text)


def _err_summary(err: Any, limit: int = 200) -> str:
    """Усечённая причина ошибки для лога: маскирование секретов, затем обрезка."""
    return _mask_secrets(str(err or ""))[:limit]


def _launch_env() -> dict:
    """Окружение для `droid exec`; после недавнего успешного хода пропускаем префлайт.

    DROID_SKIP_PREFLIGHT=1 — официальный переключатель droid-cli.sh (пропускает
    wait_api/wait_hy2/pick_pr_gateway). Первый запуск и запуск после ошибки идут
    с полным префлайтом, как прежде. Ключ моста в потомка не передаётся (C-03).
    """
    env = os.environ.copy()
    env.pop("DROID_DSH_BRIDGE_KEY", None)
    last = _last_ok[0]
    if last and 0 <= time.monotonic() - last < PREFLIGHT_SKIP_WINDOW_S:
        env["DROID_SKIP_PREFLIGHT"] = "1"
    return env


class LauncherUnavailable(Exception):
    """Канонический лончер отсутствует или не исполняем (C-03)."""


def _launcher() -> str:
    """Канонический лончер обязателен; запасного пути на голый бинарь нет.

    Вместе с лончером проверяется допуск образа droid по receipt (RW-007): функция
    вызывается на каждом spawn, поэтому отсутствие/расхождение receipt запрещает запуск.
    """
    if os.path.isfile(LAUNCHER) and os.access(LAUNCHER, os.X_OK):
        _droid_image()
        return LAUNCHER
    raise LauncherUnavailable(LAUNCHER)


def _receipt_path() -> Path:
    """Receipt квалификации образа droid (пишет DEP-09 `tools/droid_image.py`)."""
    return _state_dir() / "droid-binary-receipt.json"


# Квалификационный receipt (RW-009): четвёрка «образ + протокол + политика tools + профиль настроек».
# Любое расхождение с ожиданиями моста запрещает spawn до новой квалификации (tools/droid_image.py).
# Константы и отпечатки живут в tools/receipt_schema.py: их делят мост и установщик (RW-013).
def _check_receipt_quad(rec: dict) -> None:
    """Проверка протокола, политики tools и профиля настроек receipt; расхождение — LauncherUnavailable."""
    protocol = rec.get("protocol")
    if (
        not isinstance(protocol, dict)
        or protocol.get("api_version") != RPC_API_VERSION
        or not isinstance(protocol.get("protocol_version"), str)
        or not protocol["protocol_version"]
    ):
        raise LauncherUnavailable(
            "droid receipt: stream-jsonrpc protocol version mismatch"
        )
    policy = rec.get("tools_policy")
    ids = policy.get("disabled_tool_ids") if isinstance(policy, dict) else None
    if (
        not isinstance(policy, dict)
        or policy.get("policy") != TOOLS_POLICY
        or not isinstance(ids, list)
        or not ids
        or policy.get("digest") != tools_policy_digest(ids)
    ):
        raise LauncherUnavailable("droid receipt: tools policy mismatch")
    profile = rec.get("settings_profile")
    if (
        not isinstance(profile, dict)
        or profile.get("profile") != SETTINGS_PROFILE
        or profile.get("digest") != settings_profile_digest()
    ):
        raise LauncherUnavailable("droid receipt: settings profile mismatch")
    probes = rec.get("probes")
    if not isinstance(probes, dict) or any(
        probes.get(name) != "ok" for name in RECEIPT_PROBES
    ):
        raise LauncherUnavailable("droid receipt: qualification probes are not all ok")


def _load_receipt() -> tuple:
    """(путь образа, receipt) либо LauncherUnavailable; ('', None) — gate выключен.

    Receipt читается заново на каждом вызове. Образ обязан лежать в
    workspace/runtime/droid-image/ и совпадать с image_sha256; глобальный бинарь из
    унаследованного окружения не используется (DROID_BIN ребёнку задаётся этим путём).
    Кроме образа сверяются протокол, политика tools и профиль настроек (RW-009).
    """
    if not RECEIPT_REQUIRED:
        return "", None
    try:
        rec = json.loads(_receipt_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise LauncherUnavailable("droid receipt missing or unreadable")
    if not isinstance(rec, dict) or rec.get("schema") != RECEIPT_SCHEMA:
        raise LauncherUnavailable(
            "droid receipt malformed or outdated: requalify with tools/droid_image.py"
        )
    image, digest = rec.get("image_path"), rec.get("image_sha256")
    if (
        not isinstance(image, str)
        or not image
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
    ):
        raise LauncherUnavailable("droid receipt malformed")
    real = os.path.realpath(image)
    root = os.path.realpath(str(WORKSPACE / "runtime" / "droid-image"))
    if (
        not real.startswith(root + os.sep)
        or not os.path.isfile(real)
        or not os.access(real, os.X_OK)
    ):
        raise LauncherUnavailable(
            "droid image outside runtime/droid-image or not executable"
        )
    if _file_sha256(real) != digest:
        raise LauncherUnavailable("droid image sha256 does not match receipt")
    _check_receipt_quad(rec)
    return real, rec


def _droid_image() -> str:
    """Путь квалифицированного образа из receipt ('' — gate выключен) либо LauncherUnavailable."""
    return _load_receipt()[0]


def _receipt_state() -> str:
    """ok | invalid | not_required: состояние допуска образа для /health (без деталей и путей)."""
    if not RECEIPT_REQUIRED:
        return "not_required"
    try:
        _load_receipt()
    except LauncherUnavailable:
        return "invalid"
    return "ok"


def _file_sha256(path: str) -> str:
    """sha256 файла с кэшем по (mtime, size); ошибки чтения -> '' (fail-closed)."""
    try:
        st = os.stat(path)
    except OSError:
        return ""
    with _sha_cache_lock:
        cached = _sha_cache.get(path)
    if cached is not None and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
        return cached[2]
    try:
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""
    with _sha_cache_lock:
        _sha_cache[path] = (st.st_mtime_ns, st.st_size, digest)
    return digest


def _image_proof_reason(model: dict, effort: str = "") -> str:
    """Применимость proof (класс II) -> '' (ок) или причина деградации.

    Сверяются sha256 файла technical_ref.droid_binary_path, версия реализации
    метода, форматы image_limits.types ⊆ proof.formats и применимый effort
    запроса ∈ proof.efforts_proven. Ошибка чтения бинаря — тоже несовпадение.
    """
    proof = (model.get("images") or {}).get("proof")
    if not proof:
        return ""
    ref = FLEET.get("technical_ref") or {}
    path = os.path.expanduser(str(ref.get("droid_binary_path") or ""))
    if not path or _file_sha256(path) != str(proof.get("droid_binary_sha256") or ""):
        return "droid_binary_sha"
    if proof.get("impl_version") != METHOD_IMPL_VERSION:
        return "impl_version"
    formats = proof.get("formats") or []
    types = (FLEET.get("image_limits") or {}).get("types") or []
    if not set(types).issubset(set(formats)):
        return "formats"
    if effort and effort not in (proof.get("efforts_proven") or []):
        return "effort"
    return ""


def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    hdr = handler.headers.get("Authorization", "")
    if hdr.startswith("Bearer "):
        return hdr[7:].strip() == AUTH_KEY
    return handler.headers.get("x-api-key", "") == AUTH_KEY or hdr.strip() == AUTH_KEY


class ImageReject(Exception):
    """Отказ image-пути с типом из таксономии C-10."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _sniff_image(data: bytes) -> str:
    """MIME по магическим байтам ('' — сигнатура неизвестна)."""
    for prefix, mime in IMAGE_SIGNATURES:
        if data.startswith(prefix):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _collect_image_parts(messages: Any) -> list:
    """Все image-части сообщений с их ролью, по порядку истории."""
    found = []
    if not isinstance(messages, list):
        return found
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "image_url":
                found.append((str(msg.get("role") or ""), item))
    return found


def _parse_data_url(url: str) -> tuple:
    """data-URL -> (mime, bytes); ошибки — ImageReject из таксономии C-10."""
    comma = url.find(",")
    if comma == -1:
        raise ImageReject("invalid_image_content")
    head = url[5:comma]
    payload = url[comma + 1 :]
    fields = [f.strip().lower() for f in head.split(";")]
    mime = fields[0] if fields else ""
    if not mime or "base64" not in fields[1:]:
        raise ImageReject("invalid_image_content")
    if mime not in KNOWN_IMAGE_MIMES:
        raise ImageReject("unsupported_image_type")
    if not payload:
        raise ImageReject("invalid_image_base64")
    try:
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise ImageReject("invalid_image_base64")
    return mime, data


def _collect_images(request: dict, model: dict, effort: str) -> list:
    """Проверить изображения запроса (C-08); [] — изображений нет.

    Порядок: применимость модели/proof (класс II) -> форма частей -> data-URL ->
    сигнатура -> формат -> лимиты (число, размер, сумма).
    """
    messages = request.get("messages")
    parts = _collect_image_parts(messages)
    if not parts:
        return []
    status = (model.get("images") or {}).get("status")
    capable = status == "confirmed" or (status == "probe" and IMAGE_PROBE)
    if not capable:
        raise ImageReject("image_input_not_supported")
    reason = _image_proof_reason(model, effort)
    if reason:
        _log(f"image_proof_invalid model={model.get('id')} reason={reason}")
        raise ImageReject("image_input_not_supported")
    limits = FLEET.get("image_limits") or {}
    max_images = int(limits.get("max_images") or 0)
    max_image_bytes = int(limits.get("max_image_bytes") or 0)
    max_total = int(limits.get("max_total_image_bytes") or 0)
    allowed = [str(t).lower() for t in (limits.get("max_types") or [])]
    images = []
    total = 0
    for role, item in parts:
        if role != "user":
            raise ImageReject("invalid_image_content")
        image_url = item.get("image_url")
        if not isinstance(image_url, dict):
            raise ImageReject("invalid_image_content")
        url = image_url.get("url")
        if not isinstance(url, str):
            raise ImageReject("invalid_image_content")
        if not url.startswith("data:"):
            raise ImageReject("image_url_not_allowed")
        mime, data = _parse_data_url(url)
        sniffed = _sniff_image(data)
        if not sniffed:
            raise ImageReject("unsupported_image_type")
        if sniffed != mime:
            raise ImageReject("image_type_mismatch")
        if mime not in allowed:
            raise ImageReject("unsupported_image_type")
        if len(images) + 1 > max_images:
            raise ImageReject("too_many_images")
        if len(data) > max_image_bytes:
            raise ImageReject("image_too_large")
        total += len(data)
        if total > max_total:
            raise ImageReject("images_too_large")
        images.append({"mime": mime, "data": data})
    for index, image in enumerate(images, 1):
        image["name"] = "img-%d.%s" % (
            index,
            IMAGE_EXTENSIONS.get(image["mime"], "bin"),
        )
    return images


def _clean_err(text: str) -> str:
    lines = [
        ln for ln in (text or "").splitlines() if ln.strip() and not _NOISE.search(ln)
    ]
    return "\n".join(lines).strip()


def shutdown_all(grace: float = SHUTDOWN_GRACE_S) -> int:
    """Остановка моста: прекратить приём, interrupt активных, закрыть детей параллельно.

    Общий грейс (4,5 с) меньше exit timeout launchd (5 с). Принудительно
    убиваются ТОЛЬКО собственные процессные группы из реестра детей — чужие PID
    никогда. Возвращает число закрывавшихся детей.
    """
    global _shutting_down
    _shutting_down = True
    with _active_lock:
        procs = list(_rpc_procs.values())
    deadline = time.monotonic() + grace
    threads = []
    for proc in procs:
        # interrupt и закрытие — в потоке процесса: зависшая запись одного ребёнка не
        # задерживает остальных и не съедает общий грейс (RW-011).
        thread = threading.Thread(
            target=_shutdown_one,
            args=(
                proc,
                {
                    "mode": "graceful",
                    "graceful_wait": grace * 0.45,
                    "term_wait": grace * 0.2,
                    "kill_wait": grace * 0.15,
                },
            ),
            daemon=True,
        )
        try:
            thread.start()
        except RuntimeError:
            # поток не создан: ребёнок закрывается здесь же (слот P и реестры), force_kill ниже — страховка (RW-008);
            # сбой закрытия одного ребёнка не прерывает обход остальных и финальный force_kill (RW-007)
            try:
                _shutdown_one(
                    proc,
                    {
                        "mode": "term",
                        "term_wait": grace * 0.2,
                        "kill_wait": grace * 0.15,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                _log(
                    f"shutdown_child_failed pid={proc.pid} err={_err_summary(exc, 80)!r}"
                )
            continue
        threads.append(thread)
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))
    for proc in procs:
        try:
            proc.force_kill()
        except Exception as exc:  # noqa: BLE001
            _log(
                f"shutdown_force_kill_failed pid={proc.pid} err={_err_summary(exc, 80)!r}"
            )
    return len(procs)


def _shutdown_one(proc: "RpcProcess", close_kwargs: dict) -> None:
    """Остановка одного ребёнка: interrupt (не блокируется записью), затем закрытие."""
    if proc.busy:
        proc.interrupt_quietly()
    proc.close(**close_kwargs)


def _kill_all(*_: Any) -> None:
    """SIGTERM/SIGINT моста: graceful-закрытие детей (общий грейс 4,5 с) и выход."""
    closed = shutdown_all()
    # Остальные бэкенды: droid уже закрыт выше (его adapter.shutdown() — тот же shutdown_all).
    BACKENDS.shutdown(exclude=("droid",))
    try:
        # Ходы убиты: свежие prompt/turn-файлы собственных детей больше не нужны (RW-010).
        _sweep_workspace(cutoff_s=0.0)
    except Exception as exc:  # noqa: BLE001 - уборка не должна мешать остановке
        _log(f"sweep_workspace_failed err={_err_summary(exc, 80)!r}")
    _log(f"shutdown: closed {closed} child process group(s)")
    os._exit(0)


class RpcError(Exception):
    """Ошибка протокола droid: JSON-RPC error, невалидный обязательный ответ."""


class RpcEof(RpcError):
    """stdout droid закрыт (процесс умер) раньше ожидаемого ответа или terminal."""

    def __init__(self, rc: int):
        super().__init__(f"droid exited rc={rc}")
        self.rc = rc


class RpcTimeout(RpcError):
    """Нет ответа на служебный запрос за RPC_CALL_TIMEOUT_S."""


class RpcWriteBusy(RpcError):
    """Запись в stdin занята другим писателем: interrupt/close не ждут её (RW-011)."""


class ModelMismatch(Exception):
    """Фактические model/effort/autonomy не равны запрошенным: молча не подменяем."""


class _Cancelled(Exception):
    """Ход отменён вызывающей стороной (клиент ушёл, таймаут)."""


class _NeedRebase(Exception):
    """Живой процесс нельзя использовать (settings не подтвердились): свежая generation."""


def _proc_start_sig(pid: int) -> str:
    """Подпись старта процесса (`ps lstart`): защита от повторного использования PID."""
    try:
        res = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return res.stdout.strip()


_children_lock = threading.Lock()


def _children_path() -> Path:
    return _state_dir() / "children.json"


def _read_children() -> list:
    try:
        data = json.loads(_children_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []


def _children_update(add: dict | None = None, remove_pid: int | None = None) -> None:
    """Реестр собственных детей (pid + start-signature) для сверки при старте."""
    with _children_lock:
        entries = _read_children()
        if remove_pid is not None:
            entries = [e for e in entries if e.get("pid") != remove_pid]
        if add is not None:
            entries.append(add)
        try:
            _atomic_write(_children_path(), json.dumps(entries).encode("utf-8"))
        except OSError as exc:
            _log(
                f"session_rpc children_registry_write_failed err={_err_summary(exc, 80)!r}"
            )


def reconcile_children() -> int:
    """На старте добить ТОЛЬКО собственных осиротевших детей прошлого запуска.

    Запись принимается, если PID жив, start-signature совпала и процесс — лидер
    своей группы (мы стартуем детей через start_new_session). Всё остальное —
    чужой/переиспользованный PID, его не трогаем.
    """
    killed = 0
    with _children_lock:
        entries = _read_children()
    for entry in entries:
        pid = entry.get("pid")
        sig = str(entry.get("start") or "")
        if not isinstance(pid, int) or pid <= 1 or not sig:
            continue
        if _proc_start_sig(pid) != sig:
            continue
        try:
            if os.getpgid(pid) != pid:
                continue
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            continue
        killed += 1
        _log(f"session_rpc reconcile killed_orphan pid={pid}")
    with _children_lock:
        try:
            _atomic_write(_children_path(), b"[]")
        except OSError as exc:
            _log(
                f"session_rpc children_registry_write_failed err={_err_summary(exc, 80)!r}"
            )
    return killed


def _ensure_private(directory: Path) -> None:
    """Существующий каталог обязан быть своим и 0700: права чинятся, невозможность — исключение."""
    info = os.stat(str(directory))
    if not stat.S_ISDIR(info.st_mode):
        raise NotADirectoryError(
            f"private directory path is not a directory: {directory}"
        )
    if info.st_uid != os.getuid():
        raise PermissionError(
            f"private directory {directory} is owned by uid {info.st_uid}, not by the bridge user"
        )
    if info.st_mode & 0o077:
        os.chmod(str(directory), 0o700)


def _mkdir_private(path: Path) -> None:
    """Каталог 0700 вместе с недостающими родителями; уже существующие каталоги состояния чинятся.

    Права 0700 гарантируются и для существующих каталогов цепочки внутри WORKSPACE (state/,
    runtime/factory-home и т.п.): раньше исправлялись только созданные, и каталог 0755 проходил.
    Ошибка chmod или чужой владелец — исключение (запуск/запись отклоняются), не молчаливый пропуск.
    """
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            pass
        os.chmod(directory, 0o700)
    root = WORKSPACE.resolve()
    chain = [path]
    for parent in path.parents:
        if parent.resolve() == root or parent == parent.parent:
            break
        chain.append(parent)
    inside = path.resolve() != root and root in path.resolve().parents
    for directory in chain if inside else [path]:
        _ensure_private(directory)


def _atomic_write(path: Path, data: bytes) -> None:
    """tmp -> fsync -> os.replace -> fsync каталога; файл 0600."""
    _mkdir_private(path.parent)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp), str(path))
    except BaseException:
        try:
            os.unlink(str(tmp))
        except OSError:
            pass
        raise
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def acquire_writer_lock() -> Any:
    """flock на state/.writer.lock: второй экземпляр моста реестр не пишет (None — занято)."""
    path = _state_dir() / ".writer.lock"
    _mkdir_private(path.parent)
    handle = open(path, "a+")
    os.chmod(path, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


_JSON_STRING = re.compile(rb'"(?:[^"\\]|\\.)*"', re.DOTALL)


def _struct_flood(raw: bytes) -> bool:
    """Строка содержит больше MAX_JSON_STRUCT_TOKENS токенов `{`, `[`, `,`, `:` вне строковых литералов (RW-010)."""
    limit = MAX_JSON_STRUCT_TOKENS
    if _struct_tokens(raw) <= limit:
        return False  # быстрый путь: верхняя оценка уже в пределах
    return _struct_tokens(_JSON_STRING.sub(b'""', raw)) > limit


def _struct_tokens(raw: bytes) -> int:
    """Число структурных токенов: массив из миллионов чисел содержит мало скобок, но много запятых."""
    return raw.count(b"{") + raw.count(b"[") + raw.count(b",") + raw.count(b":")


class RpcProcess:
    """Один долгоживущий `droid exec` в режиме stream-jsonrpc.

    Поток-читатель разбирает stdout в inbox (ответы, нотификации, EOF);
    единственный потребитель inbox — владелец аренды чата. Слот ёмкости P
    принадлежит процессу и возвращается в пул только после waitpid.
    """

    def __init__(self, work_dir: str, pool: "ProcPool", holds_slot: bool):
        self.pool = pool
        self.holds_slot = holds_slot
        self.busy = False
        self.dead = False
        self.closed = False
        self.eof_rc = None
        self.inbox: queue.Queue = queue.Queue()
        self.err_box: list = []
        self.server_requests = 0
        self.inbox_bytes = 0
        self.overflowed = False
        self.retired = False  # набор завершённых turnId переполнен: процесс заменяется на границе хода
        self.protocol_version = ""  # factoryProtocolVersion из первого кадра droid
        self.finished_turns: set = set()
        self.finished_mids: set = (
            set()
        )  # сообщения завершённых ходов: их поздние события чужие для следующего
        self._inbox_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._id_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._stdin_closing = False
        self._group_released = False
        self._next_id = 0
        try:
            launcher = _launcher()
            WORKSPACE.mkdir(parents=True, exist_ok=True)
            cmd = [
                launcher,
                "exec",
                "--input-format",
                "stream-jsonrpc",
                "--output-format",
                "stream-jsonrpc",
            ]
            self.proc = subprocess.Popen(
                cmd,
                cwd=work_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                env=_child_env(),
            )
            # Запись в stdin идёт срезами с дедлайном/отменой (select): fd неблокирующий.
            os.set_blocking(self.proc.stdin.fileno(), False)
        except BaseException:
            proc = getattr(self, "proc", None)
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
            if holds_slot:
                self.holds_slot = False
                pool.release()
            raise
        self.pid = self.proc.pid
        with _active_lock:
            _active[self.pid] = self.proc
            _rpc_procs[self.pid] = self
        _children_update(
            add={
                "pid": self.pid,
                "start": _proc_start_sig(self.pid),
                "bridge_pid": os.getpid(),
            }
        )
        self._eof_lock = threading.Lock()
        self._eof_sent = False
        self._read_at = time.monotonic()  # последняя активность читателя (сторож лидера отличает «занят» от «заблокирован»)
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._err_reader = threading.Thread(target=self._drain_stderr, daemon=True)
        try:
            self._reader.start()
            self._err_reader.start()
            threading.Thread(target=self._watch_leader, daemon=True).start()
        except BaseException:
            self._abort_spawn()
            raise

    def _abort_spawn(self) -> None:
        """Потоки чтения не запустились: процесс уже порождён, поэтому он убивается, реестры и слот P чистятся."""
        self.closed = True
        self._group_released = False
        self._signal(signal.SIGKILL)
        try:
            self.proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            pass
        self._group_released = True
        with _active_lock:
            _active.pop(self.pid, None)
            _rpc_procs.pop(self.pid, None)
        _children_update(remove_pid=self.pid)
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except (OSError, ValueError, AttributeError):
                pass
        if self.holds_slot:
            self.holds_slot = False
            self.pool.release()

    # -- чтение ----------------------------------------------------------------
    def _drain_stderr(self) -> None:
        """Читает stderr до конца (pipe не встаёт), но хранит не больше MAX_STDERR_BYTES."""
        kept = bytearray()
        dropped = 0
        try:
            while True:
                chunk = cast(Any, self.proc.stderr).read1(65536)
                if not chunk:
                    break
                room = max(0, MAX_STDERR_BYTES - len(kept))
                kept += chunk[:room]
                dropped += len(chunk) - min(room, len(chunk))
        except (OSError, ValueError) as exc:
            self.err_box.append(f"stderr unreadable: {exc!r}")
            return
        text = _clean_err(bytes(kept).decode("utf-8", "replace"))
        if dropped:
            text += f"\n[stderr truncated: {dropped} bytes dropped]"
        self.err_box.append(text)

    def _read(self) -> None:
        limit = MAX_RPC_LINE_BYTES
        try:
            while True:
                raw = self.proc.stdout.readline(limit + 1)
                self._read_at = time.monotonic()
                if not raw:
                    break
                if len(raw) > limit and not raw.endswith(b"\n"):
                    # Строка длиннее лимита: хвост читаем и выбрасываем, ход завершится ошибкой.
                    total = len(raw)
                    while True:
                        part = self.proc.stdout.readline(1 << 20)
                        total += len(part)
                        if not part or part.endswith(b"\n"):
                            break
                    self._put_error(
                        "oversize", f"rpc line of {total} bytes exceeds limit {limit}"
                    )
                    continue
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("{"):
                    continue  # шум лончера/preflight, как и раньше
                if _struct_flood(raw):
                    self._put_error(
                        "bad_json",
                        f"rpc line exceeds {MAX_JSON_STRUCT_TOKENS} structural tokens",
                    )
                    continue
                try:
                    msg = json.loads(line)
                except (
                    ValueError,
                    RecursionError,
                ):  # глубокая вложенность: ошибка хода, а не гибель читателя
                    self._put_error("bad_json", line[:200])
                    continue
                if not isinstance(msg, dict):
                    self._put_error("bad_json", line[:200])
                    continue
                self._on_message(msg, len(raw))
        except (OSError, ValueError) as exc:
            self._put_error("pump_error", repr(exc))
        rc = self.proc.wait()
        time.sleep(0.05)  # дать стоку stderr дозавершиться
        self._emit_eof(rc)

    def _emit_eof(self, rc: Any) -> None:
        """Одно событие eof за жизнь процесса (читатель и сторож лидера могут прийти оба)."""
        with self._eof_lock:
            if self._eof_sent:
                return
            self._eof_sent = True
        self.dead = True
        self.inbox.put(("eof", rc))

    def _watch_leader(self) -> None:
        """Лидер вышел, а потомок держит pipe: читатель не увидит EOF, ход ждал бы до таймаута (RW-010).

        После короткого грейса читатель считается заблокированным: eof публикуется по факту выхода
        лидера, группа добивается SIGKILL, чтобы потомок не пережил закрытие процесса.
        """
        rc = self.proc.wait()
        while True:
            self._reader.join(timeout=LEADER_EXIT_GRACE_S)
            if not self._reader.is_alive():
                return  # штатный EOF: читатель сам опубликует его
            if time.monotonic() - self._read_at >= LEADER_EXIT_GRACE_S:
                break  # читатель молчит и заблокирован на pipe, который держит потомок
        _log(f"session_rpc leader_exited_pipe_held pid={self.pid} rc={rc}")
        self._emit_eof(rc)
        self._signal(signal.SIGKILL)

    def _put(self, kind: str, payload: Any, size: int) -> None:
        """Положить событие в inbox с учётом байтового бюджета; переполнение — одно событие overflow."""
        size = max(int(size), ENTRY_OVERHEAD_BYTES)
        with self._inbox_lock:
            if self.overflowed:
                return
            # Одна строка (до MAX_RPC_LINE_BYTES) принимается в пустую очередь: иначе легитимный
            # ответ крупнее бюджета очереди был бы недоставим.
            if self.inbox_bytes > 0 and self.inbox_bytes + size > MAX_INBOX_BYTES:
                self.overflowed = True
                self.inbox.put(
                    ("overflow", f"rpc inbox exceeds limit {MAX_INBOX_BYTES} bytes")
                )
                return
            self.inbox_bytes += size
        self.inbox.put((kind, payload, size))

    def _put_error(self, kind: str, payload: str) -> None:
        """Ошибка чтения тоже занимает бюджет очереди: поток мусорных строк не растит память."""
        self._put(kind, payload, len(payload))

    def _on_message(self, msg: dict, size: int | None = None) -> None:
        if size is None:
            size = len(json.dumps(msg, ensure_ascii=False))
        if not self.protocol_version and isinstance(
            msg.get("factoryProtocolVersion"), str
        ):
            self.protocol_version = msg["factoryProtocolVersion"]
        method = msg.get("method")
        if method is None:
            if "id" in msg and ("result" in msg or "error" in msg):
                self._put("resp", msg, size)
            return
        if msg.get("id") is not None:
            # Серверные запросы (разрешения): ответ отрицательный, ход не виснет.
            self.server_requests += 1
            if method == "droid.request_permission":
                self._respond(msg["id"], result={"selectedOption": "cancel"})
            else:
                self._respond(
                    msg["id"],
                    error={"code": -32601, "message": "not supported by bridge"},
                )
            return
        if method == "droid.session_notification":
            params = msg.get("params")
            if isinstance(params, dict):
                self._put("notif", params, size)

    def _taken(self, event: tuple) -> None:
        """Событие вынуто из inbox: вернуть его байты в бюджет."""
        if len(event) > 2:
            with self._inbox_lock:
                self.inbox_bytes = max(0, self.inbox_bytes - int(event[2]))

    def note_turn(self, turn_id: str, mids: Any = ()) -> None:
        """Запомнить turnId завершённого хода: его terminal больше не засчитывается.

        ID не вытесняются: вытесненный старый ID снова принимался бы за текущий. При превышении
        предела процесс помечается retired и заменяется новым на следующей границе хода.
        """
        self.finished_turns.add(turn_id)
        self.finished_mids.update(mids)
        if (
            len(self.finished_turns) > FINISHED_TURNS_KEEP
            or len(self.finished_mids) > 4 * FINISHED_TURNS_KEEP
        ):
            self.retired = True

    def next_event(self, timeout: float) -> Any:
        """Следующее событие inbox или None; EOF липкий (виден всем потребителям)."""
        try:
            event = self.inbox.get(timeout=timeout)
        except queue.Empty:
            return None
        self._taken(event)
        if event[0] == "eof":
            self.eof_rc = event[1]
            self.inbox.put(event)
        return event

    def drain_stale(self) -> int:
        """Выбросить всё, что пришло между ходами: запоздавшее не засчитывается новому."""
        dropped = 0
        while True:
            try:
                event = self.inbox.get_nowait()
            except queue.Empty:
                return dropped
            self._taken(event)
            if event[0] == "eof":
                self.eof_rc = event[1]
                self.inbox.put(event)
                return dropped
            if event[0] == "notif":
                note = (
                    (event[1] or {}).get("notification")
                    if isinstance(event[1], dict)
                    else None
                )
                if (
                    isinstance(note, dict)
                    and note.get("type") == "agent_turn_completed"
                    and note.get("turnId")
                ):
                    self.note_turn(
                        str(note["turnId"])
                    )  # запоздавший terminal: его повтор не засчитаем
            dropped += 1

    # -- запись ----------------------------------------------------------------
    def alive(self) -> bool:
        return not self.dead and not self.closed and self.proc.poll() is None

    def new_id(self) -> str:
        with self._id_lock:
            self._next_id += 1
            return f"r{self._next_id}"

    def _write(
        self,
        obj: dict,
        deadline: float | None = None,
        cancel: threading.Event | None = None,
        block: bool = True,
    ) -> None:
        """Записать одну строку в stdin ребёнка срезами: дедлайн и отмена прерывают запись.

        Если ребёнок перестал читать (pipe полон), запись не висит бессрочно: по дедлайну
        RpcTimeout, по отмене _Cancelled, при закрытии stdin RpcError. block=False —
        interrupt/close не ждут пишущий лок (RpcWriteBusy), чтобы не зависеть от чужой записи.
        """
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        if not self._write_lock.acquire(blocking=block):
            raise RpcWriteBusy("droid stdin write is busy")
        try:
            view = memoryview(data)
            sent = 0
            while sent < len(data):
                if self._stdin_closing:
                    raise RpcError("droid stdin closed")
                if cancel is not None and cancel.is_set():
                    raise _Cancelled()
                now = time.monotonic()
                if deadline is not None and now >= deadline:
                    raise RpcTimeout(
                        "write to droid stdin blocked: child does not read"
                    )
                wait = (
                    RPC_WRITE_SLICE_S
                    if deadline is None
                    else max(0.0, min(RPC_WRITE_SLICE_S, deadline - now))
                )
                try:
                    fd = self.proc.stdin.fileno()
                    _, writable, _ = select.select([], [fd], [], wait)
                    if not writable:
                        continue
                    sent += os.write(fd, view[sent:])
                except BlockingIOError:
                    continue
                except (OSError, ValueError) as exc:
                    # Процесс, умерший на старте, рвёт канал: это смерть процесса (EOF), а не
                    # ошибка протокола — иначе таксономия зависела бы от гонки с читателем.
                    if self._wait(0.5):
                        raise RpcEof(int(self.proc.returncode or 1))
                    raise RpcError(f"droid stdin closed: {exc!r}")
        finally:
            self._write_lock.release()

    def _respond(self, rid: Any, result: Any = None, error: Any = None) -> None:
        msg = {
            "type": "response",
            "jsonrpc": "2.0",
            "factoryApiVersion": RPC_API_VERSION,
            "id": rid,
        }
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result if result is not None else {}
        try:
            self._write(msg, deadline=time.monotonic() + RPC_SHORT_WRITE_S * 10)
        except RpcError as exc:
            _log(
                f"session_rpc respond_failed pid={self.pid} err={_err_summary(exc, 80)!r}"
            )

    def notify(
        self,
        method: str,
        params: dict,
        rid: str | None = None,
        deadline: float | None = None,
        cancel: threading.Event | None = None,
        block: bool = True,
    ) -> str:
        """Запрос без ожидания ответа (interrupt, close_session)."""
        rid = rid or self.new_id()
        self._write(
            {
                "type": "request",
                "jsonrpc": "2.0",
                "factoryApiVersion": RPC_API_VERSION,
                "id": rid,
                "method": method,
                "params": params,
            },
            deadline=deadline,
            cancel=cancel,
            block=block,
        )
        return rid

    def interrupt_quietly(self) -> None:
        """interrupt без ожидания записи: занятый/зависший pipe -> пропуск (дальше kill-путь)."""
        try:
            self.notify(
                "droid.interrupt_session",
                {},
                deadline=time.monotonic() + RPC_SHORT_WRITE_S,
                block=False,
            )
        except RpcError as exc:
            _log(
                f"session_rpc interrupt_failed pid={self.pid} err={_err_summary(exc, 80)!r}"
            )

    def call(
        self,
        method: str,
        params: dict,
        cancel: threading.Event | None = None,
        timeout: float | None = None,
        rid: str | None = None,
    ) -> tuple:
        """Запрос и ожидание ответа с тем же id -> (result, нотификации за это время).

        Дедлайн охватывает и фазу записи запроса, и ожидание ответа.
        """
        end = time.monotonic() + (RPC_CALL_TIMEOUT_S if timeout is None else timeout)
        rid = self.notify(method, params, rid, deadline=end, cancel=cancel)
        stash: list = []
        stash_bytes = (
            0  # байты, уже вынутые из inbox, но ещё удерживаемые до выдачи вызывающему
        )
        while True:
            if cancel is not None and cancel.is_set():
                raise _Cancelled()
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise RpcTimeout(
                    f"{method}: no response within {RPC_CALL_TIMEOUT_S:g}s"
                )
            event = self.next_event(min(0.2, remaining))
            if event is None:
                continue
            kind = event[0]
            if kind == "resp":
                msg = event[1]
                if msg.get("id") != rid:
                    continue  # запоздавший ответ прежнего запроса
                if msg.get("error") is not None:
                    err = msg["error"]
                    detail = err.get("message") if isinstance(err, dict) else err
                    raise RpcError(f"{method}: {str(detail)[:300]}")
                result = msg.get("result")
                return (result if isinstance(result, dict) else {}), stash
            if kind == "notif":
                stash_bytes += int(event[2]) if len(event) > 2 else ENTRY_OVERHEAD_BYTES
                if stash and stash_bytes > MAX_INBOX_BYTES:
                    raise RpcError(
                        f"{method}: notifications held while waiting exceed limit "
                        f"{MAX_INBOX_BYTES} bytes"
                    )
                stash.append(event[1])
            elif kind == "eof":
                raise RpcEof(int(event[1] or 1))
            else:
                raise RpcError(f"{method}: {kind}: {str(event[1])[:200]}")

    # -- закрытие ----------------------------------------------------------------
    def _wait(self, timeout: float) -> bool:
        try:
            self.proc.wait(timeout=max(0.0, timeout))
            return True
        except subprocess.TimeoutExpired:
            return False

    def _signal(self, sig: int) -> None:
        """Сигнал ТОЛЬКО собственной группе (pgid == pid лидера, start_new_session).

        Состояние лидера не проверяется: после его выхода потомок, сохранивший stdout/stderr,
        остаётся в группе и должен быть убит. После завершения close() группа считается
        освобождённой и не сигналится (pid мог быть переиспользован).
        """
        if self._group_released:
            return
        try:
            os.killpg(self.pid, sig)
        except (ProcessLookupError, PermissionError):
            return

    def _group_alive(self) -> bool:
        """Есть ли живые члены группы (лидер при выходе сначала пожинается, иначе зомби считался бы членом)."""
        if self._group_released:
            return False
        self.proc.poll()
        try:
            os.killpg(self.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return (
                False  # группа уже не наша (pid переиспользован): не трогаем и не ждём
            )
        return True

    def _wait_group(self, timeout: float) -> bool:
        """Ждать исчезновения группы не дольше timeout; True — группа пуста."""
        end = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < end:
            if not self._group_alive():
                return True
            time.sleep(0.02)
        return not self._group_alive()

    def force_kill(self) -> None:
        """SIGKILL собственной группы (процесс — лидер, start_new_session)."""
        self._signal(signal.SIGKILL)

    def close(
        self,
        mode: str = "graceful",
        graceful_wait: float = 5.0,
        term_wait: float = TERM_WAIT_S,
        kill_wait: float = TERM_WAIT_S,
        keep_slot: bool = False,
    ) -> None:
        """Закрыть процесс: штатный close_session/EOF либо SIGTERM; затем SIGKILL.

        SID и файлы сессии остаются на диске. Слот P возвращается только после
        waitpid (keep_slot — передача слота следующему процессу при rebase).
        """
        with self._close_lock:
            if self.closed:
                return
            self.closed = True
        if mode == "graceful" and self.proc.poll() is None:
            graceful = True
            try:
                self.notify(
                    "droid.close_session",
                    {"reason": "bridge"},
                    deadline=time.monotonic() + RPC_SHORT_WRITE_S,
                    block=False,
                )
            except RpcError as exc:
                graceful = False  # запись зависла/процесс умер: штатного закрытия не будет -> сразу TERM
                _log(
                    f"session_rpc close_session_failed pid={self.pid} err={_err_summary(exc, 80)!r}"
                )
            self._close_stdin()
            if graceful:
                self._wait(graceful_wait)
        # Группа убивается независимо от состояния лидера: потомок мог пережить его вместе с pipe.
        if self._group_alive():
            self._signal(signal.SIGTERM)
            self._wait_group(term_wait)
        if self._group_alive():
            self._signal(signal.SIGKILL)
            self._wait_group(kill_wait)
        self._close_stdin()
        self._group_released = True
        with _active_lock:
            _active.pop(self.pid, None)
            _rpc_procs.pop(self.pid, None)
        _children_update(remove_pid=self.pid)
        self._reader.join(timeout=1.0)
        self._err_reader.join(timeout=1.0)
        try:
            for stream, reader in (
                (self.proc.stdout, self._reader),
                (self.proc.stderr, self._err_reader),
            ):
                if stream is None:
                    continue
                if reader.is_alive():
                    # Читатель всё ещё блокирован на pipe (его держит чужой потомок вне группы):
                    # close() BufferedReader ждал бы его лок, поэтому закрываем в фоне, слот не задерживаем.
                    _log(
                        f"session_rpc pipe_reader_blocked pid={self.pid}: closing stream in background"
                    )
                    try:
                        threading.Thread(
                            target=self._close_stream, args=(stream,), daemon=True
                        ).start()
                    except RuntimeError as exc:  # поток не создан: исключение не выходит из close() (RW-007), fd уйдёт с GC
                        _log(
                            f"session_rpc stream_close_thread_failed pid={self.pid} err={_err_summary(exc, 80)!r}"
                        )
                else:
                    self._close_stream(stream)
        finally:  # отказ создать фоновый поток (RuntimeError) не должен оставить слот P занятым (RW-008)
            if self.holds_slot and not keep_slot:
                self.holds_slot = False
                self.pool.release()

    def _close_stream(self, stream: Any) -> None:
        try:
            stream.close()
        except OSError as exc:
            _log(
                f"session_rpc stream_close_failed pid={self.pid} err={_err_summary(exc, 80)!r}"
            )

    def _close_stdin(self) -> None:
        """Закрыть stdin под пишущим локом: писатель выходит за срез, fd не переиспользуется на лету."""
        self._stdin_closing = True
        got = self._write_lock.acquire(timeout=1.0)
        try:
            self.proc.stdin.close()
        except OSError as exc:
            _log(
                f"session_rpc stdin_close_failed pid={self.pid} err={_err_summary(exc, 80)!r}"
            )
        finally:
            if got:
                self._write_lock.release()


def _child_env() -> dict:
    """Окружение ребёнка: как _launch_env + чистый Factory home и образ из receipt (AD-010).

    Сбой подготовки home — исключение (spawn не выполняется), молчаливого продолжения нет.

    Ключ моста вырезан в _launch_env; FACTORY_API_KEY наследуется (в лог и state
    не попадает). Чистый home не даёт хукам/персональным skills владельца
    попасть в контекст чата; DROID_AUTO=off — вторичная защита (главная — RPC).
    """
    env = _launch_env()
    home = WORKSPACE / "runtime" / "factory-home"
    try:
        _mkdir_private(home)
    except OSError as exc:
        # Без чистого home ребёнок увидел бы персональные hooks/skills владельца: запуск запрещён.
        _log(f"session_rpc factory_home_unavailable err={_err_summary(exc, 80)!r}")
        raise
    env["FACTORY_HOME_OVERRIDE"] = str(home)
    env["DROID_AUTO"] = "off"
    image = _droid_image()
    if image:
        env["DROID_BIN"] = (
            image  # исполняется образ из receipt, а не унаследованный глобальный бинарь
        )
    return env


class ProcPool:
    """Ёмкость P: cap процессов (resident, STARTING, title, закрывающиеся до waitpid).

    FIFO по билету с прямой передачей слота головному билету. Ожидание держит
    максимум аренду своего чата. Если вытеснять некого — очередь до таймаута.
    """

    def __init__(self) -> None:
        self.cv = threading.Condition()
        self.used = 0
        self.queue: collections.deque = collections.deque()

    def cap(self) -> int:
        return max(1, int(MAX_CONCURRENT))

    def acquire(self, poll) -> str:
        """'' — слот получен; иначе причина от poll(): client_gone | queue_timeout."""
        ticket = object()
        with self.cv:
            self.queue.append(ticket)
        try:
            while True:
                with self.cv:
                    head = bool(self.queue) and self.queue[0] is ticket
                    if head and self.used < self.cap():
                        self.queue.popleft()
                        self.used += 1
                        self.cv.notify_all()
                        return ""
                if head:
                    victim = REGISTRY.take_victim()
                    if victim is not None:
                        victim.evict()
                        continue
                with self.cv:
                    self.cv.wait(timeout=0.5)
                reason = poll()
                if reason:
                    return reason
        finally:
            with self.cv:
                if ticket in self.queue:
                    self.queue.remove(ticket)
                    self.cv.notify_all()

    def release(self) -> None:
        with self.cv:
            self.used = max(0, self.used - 1)
            self.cv.notify_all()


class StateConflict(Exception):
    """rec_rev файла на диске не равен ожидаемому: второй писатель/откат диска."""


class Chat:
    """Логический чат (ключ prompt_cache_key): аренда L, процесс, потреблённый префикс."""

    def __init__(self, key_hash: str):
        self.key_hash = key_hash
        self.lock = threading.Lock()  # аренда чата L (single-flight на ключ)
        self.waiters = 0
        self.refs = 0  # держатели ссылки на объект чата (запросы между get и release): индекс не вытесняет
        self.proc: RpcProcess | None = None
        self.sid = ""
        self.generation = 0
        self.n = 0
        self.head = ""
        self.cfg = ""
        self.settings: tuple[str, str, str] = ("", "", "")
        self.droid_real = -1
        self.restore_count = 0
        self.turns = 0
        self.last_used = 0.0
        self.rec_rev = 0
        self.state = "NEW"  # NEW | READY | PERSISTED | DIRTY


def _record_path(key_hash: str) -> Path:
    return (
        _state_dir() / "conversations.v1" / "chats" / key_hash[:2] / f"{key_hash}.json"
    )


_RECORD_STR_FIELDS = (
    "key_hash",
    "sid",
    "state",
    "head",
    "cfg",
    "model",
    "effort",
    "autonomy",
)
_RECORD_INT_FIELDS = ("generation", "rec_rev", "n", "droid_real", "restore_count")


def _record_valid(rec: dict) -> bool:
    """Обязательные поля записи чата и их типы (число — не bool; счётчики неотрицательные)."""
    for name in _RECORD_STR_FIELDS:
        if not isinstance(rec.get(name), str):
            return False
    for name in _RECORD_INT_FIELDS:
        value = rec.get(name)
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        if value < (-1 if name == "droid_real" else 0):
            return False
    return True


def _read_record(path: Path) -> dict | None:
    """Запись чата или None, если файла нет/она повреждена/не проходит валидацию (history-fallback)."""
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict) or rec.get("schema") != 1 or not _record_valid(rec):
        return None
    return rec


def _write_record(chat: Chat, state: str) -> None:
    """Атомарная запись метаданных чата (только хеши; 0600; O(одной записи))."""
    path = _record_path(chat.key_hash)
    if path.exists():
        disk = _read_record(path)
        if disk is not None and int(disk.get("rec_rev") or 0) != chat.rec_rev:
            raise StateConflict(f"rec_rev {disk.get('rec_rev')} != {chat.rec_rev}")
    rec = {
        "schema": 1,
        "key_hash": chat.key_hash,
        "sid": chat.sid,
        "generation": chat.generation,
        "state": state,
        "rec_rev": chat.rec_rev + 1,
        "n": chat.n,
        "head": chat.head,
        "cfg": chat.cfg,
        "model": chat.settings[0],
        "effort": chat.settings[1],
        "autonomy": chat.settings[2],
        "droid_real": chat.droid_real,
        "restore_count": chat.restore_count,
        "wall_time": int(time.time()),
    }
    _atomic_write(path, json.dumps(rec, sort_keys=True).encode("utf-8"))
    chat.rec_rev += 1


def _load_record(chat: Chat) -> None:
    """Подхватить запись чата с диска: после рестарта чат PERSISTED либо DIRTY."""
    path = _record_path(chat.key_hash)
    if not path.exists():
        return
    rec = _read_record(path)
    if rec is None:
        _log(f"session_rpc chat={chat.key_hash[:8]} record=corrupt fallback=history")
        return
    try:
        chat.sid = str(rec["sid"])
        chat.generation = int(rec["generation"])
        chat.n = int(rec["n"])
        chat.head = str(rec["head"])
        chat.cfg = str(rec["cfg"])
        chat.settings = (str(rec["model"]), str(rec["effort"]), str(rec["autonomy"]))
        chat.droid_real = int(rec["droid_real"])
        chat.restore_count = int(rec["restore_count"])
        chat.rec_rev = int(rec["rec_rev"])
    except (KeyError, TypeError, ValueError):
        _log(f"session_rpc chat={chat.key_hash[:8]} record=malformed fallback=history")
        chat.sid = ""
        chat.n = 0
        return
    # PENDING/DIRTY: ход мог дойти до droid, но не зафиксирован -> только replay.
    chat.state = "PERSISTED" if rec.get("state") in ("READY", "PERSISTED") else "DIRTY"


class _Victim:
    """Захваченный (try-acquire) чат-жертва вытеснения: аренда уже у нас."""

    def __init__(self, chat: Chat):
        self.chat = chat

    def evict(self) -> None:
        chat = self.chat
        try:
            proc, chat.proc = chat.proc, None
            if chat.state == "READY":
                chat.state = "PERSISTED"
            if proc is not None:
                _log(
                    f"session_rpc chat={chat.key_hash[:8]} evict pid={proc.pid} sid={chat.sid[:8] or '-'}"
                )
                proc.close(mode="term")
            _persist_chat(chat)
        finally:
            chat.lock.release()


class PersistError(Exception):
    """Запись состояния чата не удалась: ход не может быть выдан как успешный (RW-005)."""


def _persist_chat(chat: Chat) -> bool:
    """Записать состояние чата. False — запись не удалась (чат -> DIRTY, следующий ход — replay).

    Вызывающий решает, критична ли ошибка: commit после terminal и PENDING до add — критичны
    (ход не выдаётся / не стартует), вытеснение и реап — нет (процесс закрыт, чат восстановится replay).
    """
    if not chat.sid:
        return True
    try:
        _write_record(
            chat, "READY" if chat.state in ("READY", "PERSISTED") else chat.state
        )
        return True
    except (OSError, StateConflict, ValueError, TypeError) as exc:
        chat.state = "DIRTY"
        _log(
            f"session_rpc chat={chat.key_hash[:8]} persist_failed err={_err_summary(exc, 120)!r}"
        )
        return False


def _write_pending(chat: Chat, sid: str) -> None:
    """PENDING нового SID до первого add_user_message: не записан — ход не стартует (RpcError -> 502)."""
    chat.sid = sid
    try:
        _write_record(chat, "PENDING")
    except (OSError, StateConflict, ValueError, TypeError) as exc:
        chat.state = "DIRTY"
        _log(
            f"session_rpc chat={chat.key_hash[:8]} persist_failed err={_err_summary(exc, 120)!r}"
        )
        raise RpcError("chat state is not writable")


class ChatRegistry:
    """Реестр чатов: индекс O(1) по sha256(namespace+ключ), реапер idle, вытеснение LRU."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.chats: dict = {}
        self._reaper: threading.Thread | None = None

    def get(self, key_hash: str) -> Chat:
        """Чат по хешу ключа (создаёт/читает запись); вызывающий обязан вернуть его через release()."""
        with self.lock:
            chat = self.chats.get(key_hash)
            if chat is None:
                self._evict_index()
                chat = Chat(key_hash)
                _load_record(chat)
                self.chats[key_hash] = chat
            chat.refs += 1
            return chat

    def release(self, chat: Chat) -> None:
        with self.lock:
            chat.refs = max(0, chat.refs - 1)

    def _evict_index(self) -> None:
        """Индекс не растёт без границы: вытесняются чаты без процесса/ссылок/ожидающих (запись остаётся на диске)."""
        if len(self.chats) < MAX_CHATS:
            return
        idle = sorted(
            (
                c
                for c in self.chats.values()
                if c.proc is None
                and c.refs == 0
                and c.waiters == 0
                and not c.lock.locked()
            ),
            key=lambda c: c.last_used,
        )
        for chat in idle:
            if len(self.chats) < MAX_CHATS:
                break
            del self.chats[chat.key_hash]

    def add_waiter(self, chat: Chat) -> None:
        with self.lock:
            chat.waiters += 1

    def drop_waiter(self, chat: Chat) -> None:
        with self.lock:
            chat.waiters -= 1

    def _eligible(self, chat: Chat) -> bool:
        return (
            chat.proc is not None
            and chat.waiters == 0
            and not chat.lock.locked()
            and chat.proc.alive()
        )

    def take_victim(self) -> "_Victim | None":
        """LRU среди idle не-pending чатов; аренда берётся try-acquire без ожидания."""
        with self.lock:
            candidates = sorted(
                (c for c in self.chats.values() if self._eligible(c)),
                key=lambda c: c.last_used,
            )
        for chat in candidates:
            if chat.lock.acquire(blocking=False):
                if chat.proc is not None and chat.waiters == 0:
                    return _Victim(chat)
                chat.lock.release()
        return None

    def reap_once(self, now: float | None = None) -> list:
        """Закрыть процессы idle >= IDLE_SECONDS (busy/pending не трогаем) -> hash8 закрытых.

        Список кандидатов — лишь снимок: после захвата аренды чата предикат (idle, не busy, жив/мёртв)
        и идентичность процесса проверяются ЗАНОВО, иначе свежий процесс нового хода закрывался бы
        по устаревшему снимку (RW-011).
        """
        now = _clock() if now is None else now
        with self.lock:
            candidates = [
                (c, c.proc)
                for c in self.chats.values()
                if self._eligible(c) and now - c.last_used >= IDLE_SECONDS
            ]
            dead = [
                (c, c.proc)
                for c in self.chats.values()
                if c.proc is not None
                and not c.proc.alive()
                and c.waiters == 0
                and not c.lock.locked()
            ]
        for chat, seen in dead:
            # Процесс умер в простое: слот P возвращаем, чат восстановим через load.
            if chat.lock.acquire(blocking=False):
                try:
                    proc = chat.proc
                    if proc is not seen or proc is None or proc.alive():
                        continue  # за время снимка процесс заменён или ожил: это уже не тот процесс
                    chat.proc = None
                    proc.close(mode="term", term_wait=0.5, kill_wait=0.5)
                    if chat.state == "READY":
                        chat.state = "PERSISTED"
                finally:
                    chat.lock.release()
        reaped = []
        for chat, seen in candidates:
            if not chat.lock.acquire(blocking=False):
                continue
            try:
                proc = chat.proc
                if (
                    proc is None
                    or proc is not seen
                    or chat.waiters != 0
                    or proc.busy
                    or not proc.alive()
                    or now - chat.last_used < IDLE_SECONDS
                ):
                    continue  # состояние изменилось с момента снимка: процесс свежий или чужой
                chat.proc = None
                if chat.state == "READY":
                    chat.state = "PERSISTED"
                _log(
                    f"session_rpc chat={chat.key_hash[:8]} idle_close pid={proc.pid} "
                    f"sid={chat.sid[:8] or '-'}"
                )
                proc.close(mode="graceful")
                _persist_chat(chat)
                reaped.append(chat.key_hash[:8])
            finally:
                chat.lock.release()
        return reaped

    def start_reaper(self) -> None:
        if self._reaper is not None:
            return
        self._reaper = threading.Thread(target=self._reap_loop, daemon=True)
        self._reaper.start()

    def _reap_loop(self) -> None:
        while not _shutting_down:
            time.sleep(REAPER_TICK_S)
            try:
                self.reap_once()
            except OSError as exc:
                _log(f"session_rpc reaper_error err={_err_summary(exc, 120)!r}")


REGISTRY = ChatRegistry()
POOL = ProcPool()


def _reset_rpc_state() -> None:
    """Закрыть всех детей и сбросить реестр/пул (тесты; старт моста)."""
    global REGISTRY, POOL, _shutting_down
    with _active_lock:
        procs = list(_rpc_procs.values())
    for proc in procs:
        proc.close(mode="term", term_wait=1.0, kill_wait=1.0)
    REGISTRY = ChatRegistry()  # pyright: ignore[reportConstantRedefinition]
    POOL = ProcPool()  # pyright: ignore[reportConstantRedefinition]
    _shutting_down = False


def _message_text(message: Any) -> str:
    """Текст сообщения droid (content: строка или блоки {type,text|thinking})."""
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
    return "\n".join(p for p in parts if p)


def _message_thinking(message: Any) -> str:
    """Текст thinking-блоков сообщения droid."""
    content = message.get("content") if isinstance(message, dict) else None
    parts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "thinking":
                parts.append(str(block.get("thinking") or ""))
    return "\n".join(p for p in parts if p)


def _is_service_message(message: Any) -> bool:
    """Служебные вставки droid (system-reminder, каталог tools) в проверку истории не входят."""
    text = _message_text(message).lstrip()
    return text.startswith("<system-reminder>") or text.startswith(
        "Unified tool catalog"
    )


def _is_blank_user_message(message: Any) -> bool:
    """User-сообщение без текста: живой create_message служебной вставки (system-reminder) приходит с content=[],
    текст виден только после load_session; такое сообщение не входит в учёт истории (RW-012)."""
    return (
        isinstance(message, dict)
        and message.get("role") == "user"
        and not _message_text(message)
    )


def _service_duplicates(messages: list) -> bool:
    """Повтор служебного блока после load (накопление scaffolding) по sha256 содержимого."""
    seen = set()
    for message in messages:
        if not _is_service_message(message):
            continue
        digest = _digest(" ".join(_message_text(message).split()))
        if digest in seen:
            return True
        seen.add(digest)
    return False


def _map_usage(token_usage: Any) -> dict:
    """tokenUsage терминального agent_turn_completed (ПО ХОДУ) -> usage моста."""
    tu = token_usage if isinstance(token_usage, dict) else {}

    def num(key: str) -> int:
        value = tu.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    return {
        "input_tokens": num("inputTokens"),
        "output_tokens": num("outputTokens"),
        "cache_creation_tokens": num("cacheCreationTokens"),
        "cache_read_tokens": num("cacheReadTokens"),
        "thinking_tokens": num("thinkingTokens"),
    }


def _transcribe(messages: list, tools: list, tool_choice: Any, images: list) -> dict:
    """История запроса DSH -> system + последовательность RPC-входов.

    Ведущие system/developer-сообщения и протокол эмуляции tools уходят одним
    systemPrompt; остальное — по одному входу на сообщение (assistant — как
    assistant, tool-результаты — как user-эмуляция). digest берётся от
    канонического рендера сообщения: им сверяется префикс. runnable=False —
    запрос пуст или заканчивается не user: тогда прежний _messages_to_prompt.
    """
    counter = [0]
    system_parts = []
    items = []
    leading = True
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "user")
        if leading and role in ("system", "developer"):
            text = _render_content(msg.get("content"), counter)
            if text.strip():
                system_parts.append(text)
            continue
        leading = False
        rendered = _render_message(msg, counter)
        if not rendered:
            continue
        if role == "assistant":
            items.append(
                {
                    "role": "assistant",
                    "text": rendered[len("[assistant]\n") :],
                    "digest": _digest(rendered),
                }
            )
        elif role == "user":
            items.append(
                {
                    "role": "user",
                    "text": rendered[len("[user]\n") :],
                    "digest": _digest(rendered),
                }
            )
        else:  # tool и редкие mid-conversation system: как user с меткой роли
            items.append(
                {"role": "user", "text": rendered, "digest": _digest(rendered)}
            )
    if tools and not _tool_choice_none(tool_choice):
        section = _tools_section(tools, tool_choice, bool(images))
        system_parts.append(
            section[len("[system]\n") :]
            if section.startswith("[system]\n")
            else section
        )
    system = "\n\n".join(system_parts).strip() or None
    if images and items and items[-1]["role"] == "user":
        items[-1]["text"] += "\n\n" + _attachments_section(images)
    runnable = bool(items) and items[-1]["role"] == "user"
    return {"system": system, "items": items, "runnable": runnable}


def _chain_head(items: list, count: int) -> str:
    """Голова хеш-цепочки по первым count входам."""
    head = ""
    for item in items[:count]:
        head = _chain(head, item["digest"])
    return head


def _config_digest(system: str | None, work_dir: str) -> str:
    """Иммутабельная конфигурация чата: system/tools-протокол и cwd (смена -> rebase)."""
    return _digest(
        json.dumps({"system": system or "", "cwd": work_dir}, sort_keys=True)
    )


def _projection_digest(text: str, tool_calls: list) -> str:
    """Проекция выданного мостом assistant-сообщения, как её пришлёт клиент назад."""
    msg = {
        "role": "assistant",
        "content": text,
        "tool_calls": [
            {"id": tc["id"], "type": "function", "function": tc["function"]}
            for tc in tool_calls
        ],
    }
    return _digest(_render_message(msg, [0]))


def _is_title_request(messages: list, tools: list, req: dict) -> bool:
    """Title-запрос DSH по СТРУКТУРЕ (F-512): system-инструкция, 2 сообщения, без tools, max_tokens=64."""
    if tools or len(messages) != 2 or req.get("max_tokens") != TITLE_MAX_TOKENS:
        return False
    system, user = messages
    if not isinstance(system, dict) or not isinstance(user, dict):
        return False
    if system.get("role") != "system" or user.get("role") != "user":
        return False
    if not _flatten_content(system.get("content")).startswith(TITLE_SYSTEM_PREFIX):
        return False
    text = _flatten_content(user.get("content"))
    if not text.startswith(TITLE_USER_PREFIX):
        return False
    try:
        return isinstance(json.loads(text[len(TITLE_USER_PREFIX) :].strip()), list)
    except ValueError:
        return False


_SECTION_RE = re.compile(r"^Instructions from: (.*)$", re.M)
_canon_cache: dict = {"key": None, "digest": ""}
# Дайджесты канонов, виденных мостом: блок со старой копией канона остаётся KB-формой и после правки канона
# и после рестарта (state/canon_seen.json, RW-014). Упорядоченное множество; предел — страховка от разрастания файла.
_canon_seen: dict = {}
_canon_seen_lock = threading.Lock()
CANON_SEEN_KEEP = 256


def _canon_seen_path() -> Path:
    return _state_dir() / "canon_seen.json"


def _canon_seen_load() -> None:
    """Загрузить дайджесты канонов прошлых запусков (старт моста); нечитаемый файл — пустая история."""
    try:
        data = json.loads(_canon_seen_path().read_text("utf-8"))
    except (OSError, ValueError):
        return
    with _canon_seen_lock:
        for digest in data if isinstance(data, list) else []:
            if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
                _canon_seen[digest] = None


class CanonPersistError(Exception):
    """История канонов не записана на диск: без неё после рестарта старый KB-блок потерял бы предел 60000 (RW-011)."""


def _canon_seen_add(digest: str) -> None:
    """Запомнить дайджест канона и сохранить историю на диск (0600, атомарно).

    Fail-closed: сбой записи откатывает запись в памяти и поднимает CanonPersistError (ход отклоняется).
    """
    with _canon_seen_lock:
        if digest in _canon_seen:
            return
        snapshot = dict(_canon_seen)
        _canon_seen[digest] = None
        while len(_canon_seen) > CANON_SEEN_KEEP:
            del _canon_seen[next(iter(_canon_seen))]
        try:
            _atomic_write(
                _canon_seen_path(), json.dumps(list(_canon_seen)).encode("utf-8")
            )
        except OSError as exc:
            _canon_seen.clear()
            _canon_seen.update(snapshot)
            _log(f"canon_seen_persist_failed err={_err_summary(exc, 80)!r}")
            raise CanonPersistError("canon_seen.json is not writable") from exc


def _canon_digest() -> str:
    """sha256 канона (с кэшем по mtime/size); '' — канон нечитаем."""
    try:
        info = os.stat(GUARD_CANON)
        key = (GUARD_CANON, info.st_mtime_ns, info.st_size)
        if _canon_cache["key"] == key:
            return _canon_cache["digest"]
        with open(GUARD_CANON, "rb") as handle:
            text = handle.read().decode("utf-8", "replace").rstrip()
    except OSError:
        return ""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    _canon_seen_add(digest)  # до кэша: при отказе записи следующий ход повторит попытку
    _canon_cache.update(key=key, digest=digest)
    return digest


def _block_is_canon_only(text: str) -> bool:
    """Все секции блока — копии канона: форма KB/DW, к которой применим жёсткий предел REQ-003."""
    canon = {_canon_digest(), *_canon_seen} - {""}
    heads = list(_SECTION_RE.finditer(text))
    if not canon or not heads:
        return False
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        body = text[head.end() : end].strip()
        if body.endswith("</system-reminder>"):
            body = body[: -len("</system-reminder>")]
        if hashlib.sha256(body.strip().encode("utf-8")).hexdigest() not in canon:
            return False
    return True


def _in_kb_cwd(cwd: str) -> bool:
    """cwd запроса — KB (или каталог внутри): там предел REQ-003 жёсткий независимо от состава блока."""
    if not cwd:
        return False
    real = os.path.realpath(cwd)
    root = os.path.realpath(b_guard.KB_CWD)
    return real == root or real.startswith(root + os.sep)


def _instr_blocks(messages: list, kb_cwd: bool = False) -> list:
    """ВСЕ блоки agent-instructions входящих messages: [{bytes, sections, omitted, canon_only}].

    canon_only — форма KB: cwd запроса = KB либо блок целиком из копий канона (текущего или виденного ранее).

    Маркер ищется по всему тексту user-сообщения (без ограничения префиксом), блоков может быть несколько
    (baseline старого разговора плюс новый): каждый проверяется отдельно.
    """
    blocks = []
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        text = _flatten_content(msg.get("content"))
        if not _SECTION_RE.search(text) and "Workspace instruction budget" not in text:
            continue
        omitted = "-"
        found = re.search(
            r"Workspace instruction budget \d+ bytes: omitted ([^;\n]+)", text
        )
        if found:
            omitted = found.group(1).strip()
        blocks.append(
            {
                "bytes": len(text.encode("utf-8")),
                "sections": len(_SECTION_RE.findall(text)),
                "omitted": omitted,
                "canon_only": kb_cwd or _block_is_canon_only(text),
            }
        )
    return blocks


def _instr_scan(messages: list, kb_cwd: bool = False) -> tuple:
    """Крупнейший блок agent-instructions входящих messages: (секций, omitted, байт); нет блоков — (0, "-", 0)."""
    blocks = _instr_blocks(messages, kb_cwd)
    if not blocks:
        return 0, "-", 0
    top = max(blocks, key=lambda b: b["bytes"])
    return top["sections"], top["omitted"], top["bytes"]


def _instr_limit(block: dict, max_bytes: int | None) -> int:
    """Применимый предел блока: KB-форма (только канон) — INSTR_BLOCK_LIMIT, прочие — maxBytes минус запас."""
    if block["canon_only"]:
        return INSTR_BLOCK_LIMIT
    return (max_bytes or b_guard.DEFAULT_MAXBYTES) - INSTR_NONKB_MARGIN


def _instr_violation(blocks: list, max_bytes: int | None) -> tuple | None:
    """(байт, предел) первого блока сверх применимого предела либо None."""
    for block in blocks:
        limit = _instr_limit(block, max_bytes)
        if block["bytes"] > limit:
            return block["bytes"], limit
    return None


def _text_slices(text: str):
    """Срезы текста для выдачи: не более DELIVERY_CHUNK_BYTES байт UTF-8 в каждом (до 4 Б на символ)."""
    step = max(1, int(DELIVERY_CHUNK_BYTES) // 4)
    for start in range(0, len(text), step):
        yield text[start : start + step]


def _str_mem_bytes(text: str) -> int:
    """Память, удерживаемая строкой CPython: 1/2/4 Б на символ по самому широкому символу, а не длина UTF-8 (RW-008)."""
    return sys.getsizeof(text) if text else 0


def _delivery_size(out: dict) -> int:
    """Память, удерживаемая готовым ответом до конца выдачи: объединённый текст И события (две копии) и аргументы вызовов."""
    size = _str_mem_bytes(out.get("text") or "")
    for kind, value in out.get("events") or []:
        size += _str_mem_bytes(
            value
            if kind in ("content", "reasoning")
            else value["function"]["arguments"]
        )
    return size


def _escape_json_piece(piece: str) -> bytes:
    """Содержимое JSON-строки для среза (без обрамляющих кавычек)."""
    return json.dumps(piece, ensure_ascii=False)[1:-1].encode("utf-8")


class InstructionGuard:
    """Автоматический контур b_guard: фактические профили DSH и канон проверяются на старте и периодически.

    Состояние: ok | unsafe | unknown. unsafe (CANON_LOST, DUPLICATE_RETURNED, REQ003_SIZE_EXCEEDED на
    профиле, maxBytes не читается) даёт alert в журнал и управляемый отказ для НОВЫХ чатов с блоком
    инструкций; живые чаты продолжают работать, процесс не перезапускается. unknown (профилей нет) —
    предел блока применяется по умолчанию (fail-closed).
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.state = "unknown"
        self.reasons: list = []
        self.max_bytes: int | None = None
        self.checked = 0.0
        self._alerted: tuple | None = None
        self._had_profiles = (
            False  # профили DSH уже наблюдались: их исчезновение — unsafe, а не unknown
        )
        self._thread: threading.Thread | None = None

    def snapshot(self) -> tuple:
        with self.lock:
            return self.state, list(self.reasons), self.max_bytes

    def _evaluate(self) -> tuple:
        """(состояние, причины, maxBytes, предупреждения b_guard)."""
        profiles = b_guard.find_profiles(GUARD_PROFILES_DIR)
        if not profiles:
            if self._had_profiles:
                return (
                    "unsafe",
                    [
                        "PROFILES_LOST: profile directory disappeared after it was verified"
                    ],
                    None,
                    [],
                )
            return "unknown", ["PROFILES_NOT_FOUND"], None, []
        self._had_profiles = True
        reasons: list = []
        warnings: list = []
        unsafe = False
        known: list = []
        for name, _path, maxbytes in profiles:
            if maxbytes is None:
                reasons.append(f"PROFILE_MAXBYTES_UNREADABLE profile={name}")
                unsafe = True
                continue
            known.append(maxbytes)
            result = b_guard.check_installed(
                maxbytes, b_guard.DEFAULT_CWDS, GUARD_CANON
            )
            if result is None:
                reasons.append(f"CANON_LOST profile={name}: canon is missing")
                unsafe = True
            elif result.exit_code == 2:
                reasons.extend(
                    f"profile={name} {reason.split(':')[0]}"
                    for reason in result.reasons
                )
                unsafe = True
            elif result.exit_code == 1:
                warnings.extend(f"profile={name} {reason}" for reason in result.reasons)
        return (
            ("unsafe" if unsafe else "ok"),
            reasons,
            (min(known) if known else None),
            warnings,
        )

    def check_once(self) -> str:
        """Один проход контура; alert пишется при смене состояния/причин, а не на каждом тике."""
        try:
            state, reasons, max_bytes, warnings = self._evaluate()
        except OSError as exc:
            state, reasons, max_bytes, warnings = (
                "unsafe",
                [f"GUARD_CHECK_FAILED {_err_summary(exc, 80)}"],
                None,
                [],
            )
        with self.lock:
            self.state, self.reasons, self.max_bytes = state, reasons, max_bytes
            self.checked = time.time()
            changed = (state, tuple(reasons), tuple(warnings)) != self._alerted
            self._alerted = (state, tuple(reasons), tuple(warnings))
        if changed and (state != "ok" or reasons or warnings):
            # Предупреждения (запас ниже порога, риск oracle строки) не отказ, но видны в журнале владельцу.
            _log(
                f"instr_guard_alert state={state} warnings={len(warnings)} "
                f"reasons={'; '.join(reasons + warnings)[:300]!r} max_bytes={max_bytes}"
            )
        elif changed:
            _log(f"guard_state state=ok max_bytes={max_bytes}")
        return state

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not _shutting_down:
            time.sleep(GUARD_TICK_S)
            self.check_once()


GUARD = InstructionGuard()


def _chat_known(route: str, raw_key: Any, adapter: Any = None) -> bool:
    """Продолжение существующего чата ТОГО ЖЕ резидентного бэкенда, а не новый (RW-008).

    Исключение b_guard для «известного чата» — только подтверждённое продолжение сессии:
    у backend с `sessions=none` (muse) сессий нет, поэтому ключ существующего droid-чата не
    делает muse-запрос продолжением — под unsafe он считается новым и отклоняется до spawn.
    """
    if route != "keyed" or adapter is None:
        return False
    if adapter.capabilities.get("sessions") != "resident":
        return False
    key_hash = _key_hash(raw_key)
    chat = REGISTRY.chats.get(key_hash)
    if chat is not None and chat.sid:
        return True
    return _record_path(key_hash).exists()


class Run:
    """Один ход чата поверх RpcProcess; воркер-поток публикует события в очередь.

    Интерфейс очереди прежний (text/reasoning/result/stream_error/pump_error/done),
    поэтому HTTP-слой (_execute) не знает про RPC. Вывод хода удерживается до
    успешного agent_turn_completed: retract/llm_retry удаляют только
    незакоммиченное; после успеха — прежняя гранулярность SSE.
    """

    def __init__(self, plan: dict, proc: RpcProcess | None, holds_slot: bool):
        self.plan = plan
        self.proc = proc
        self.slot_held = holds_slot
        self.path = plan["path"]
        self.q: queue.Queue = queue.Queue()
        self.err_box: list = proc.err_box if proc is not None else []
        self.got_event = False
        self.started = time.monotonic()
        self.last_progress = 0.0
        self.cancel = threading.Event()
        self.ok = False
        self.sent = False
        self.armed = False
        self.sid = plan.get("sid") or ""
        self.droid_real = int(plan.get("droid_real", -1))
        self.turn_req_id = ""
        self.interrupted = False
        self._msgs: dict = {}
        self._order: list = []
        self._counted: set = (
            set()
        )  # id сообщений, уже учтённых в droid_real (дубли/retraction)
        self._acc_bytes = (
            0  # накопленный text/thinking/метаданные хода (бюджет MAX_TURN_TEXT_BYTES)
        )
        self.active_turn = ""  # id user-сообщения текущего хода: у реального droid он же turnId терминала
        self._foreign_mids: set = (
            set()
        )  # сообщения прежних ходов, попавшие в поток после arming
        self._own: set = set()  # подтверждённые id хода: user-сообщение и собственные assistant (цепочка parentId)
        self._held: dict = {}  # события ещё не подтверждённого mid (дельты раньше create_message): mid -> [(type, note, size)]
        self._held_bytes = 0
        self._last_error = ""
        self._quarantined = 0
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    # -- воркер ----------------------------------------------------------------
    def _work(self) -> None:
        try:
            self._run_turn()
        except _Cancelled:
            return
        except ModelMismatch as exc:
            self.q.put(("stream_error", str(exc)[:500]))
        except RpcEof as exc:
            self.q.put(("done", (exc.rc or 1, "")))
        except RpcError as exc:
            self.q.put(("pump_error", str(exc)[:500]))
        except OSError as exc:
            self.q.put(("pump_error", repr(exc)))
        except Exception as exc:  # noqa: BLE001 - воркер не должен умирать молча: ход иначе висел бы до таймаута
            _log(f"session_rpc worker_error err={_err_summary(repr(exc), 160)!r}")
            self.q.put(("pump_error", repr(exc)[:500]))
        finally:
            if self.slot_held:
                self.slot_held = False
                POOL.release()
            if self.proc is not None:
                self.proc.busy = False

    def _spawn(self) -> RpcProcess:
        holds = self.slot_held
        self.slot_held = False  # слот передан конструктору (при сбое он сам его вернёт)
        proc = RpcProcess(self.plan["work_dir"], POOL, holds)
        self.proc = proc
        self.err_box = proc.err_box
        return proc

    def _rebase(self, proc: RpcProcess) -> None:
        """Отказ от процесса: слот передаётся новому (cap не превышается), полный replay."""
        proc.close(mode="term", keep_slot=True)
        self.slot_held = True
        self.path = "rebase"
        self.sid = ""
        self.proc = None

    def _run_turn(self) -> None:
        plan = self.plan
        items = plan["send"]
        proc = self.proc
        if self.path == "hot":
            assert proc is not None
            proc.drain_stale()
            try:
                if proc.dead or proc.overflowed or proc.retired:
                    raise _NeedRebase()  # процесс умер, его очередь переполнялась или набор turnId исчерпан
                self._sync_settings(proc, plan["settings"])
            except _NeedRebase:
                self._rebase(proc)
                items = plan["all_items"]
        if self.path != "hot":
            proc = self._spawn()
            if self.path == "restore" and not self._load(proc):
                self._rebase(proc)
                items = plan["all_items"]
                proc = self._spawn()
            if self.path != "restore":
                self._initialize(proc)
        assert proc is not None
        proc.busy = True
        before_add = plan.get("before_add")
        if before_add is not None:
            before_add(self.sid)
        if not self._send_items(proc, items):
            self._consume(proc)

    def _check_settings(self, settings: Any) -> None:
        """Read-back фактических model/effort/autonomy: молча не подменяем (F-214)."""
        model, effort, autonomy = self.plan["settings"]
        if not isinstance(settings, dict):
            raise RpcError("settings read-back missing")
        got = (settings.get("modelId"), settings.get("reasoningEffort"))
        if got != (model, effort):
            raise ModelMismatch(
                f"droid substituted model/effort: wanted {model}/{effort}, got {got[0]}/{got[1]}"
            )
        level = settings.get("autonomyLevel")
        if not isinstance(level, str) or not level:
            raise RpcError("settings read-back: autonomyLevel missing")
        if level != autonomy:
            raise ModelMismatch(
                f"droid autonomy mismatch: wanted {autonomy}, got {level}"
            )
        self._check_flags(settings)

    @staticmethod
    def _check_flags(settings: dict) -> None:
        """disableBuiltinSkills/autoRejectPermissionRequests: если droid их сообщает, они обязаны быть true.

        Реальный droid (протокол 1.248) эти поля в settings не возвращает, поэтому отсутствие
        не отказ; присутствующее расхождение — fail-closed.
        """
        for flag in ("disableBuiltinSkills", "autoRejectPermissionRequests"):
            if flag in settings and settings[flag] is not True:
                raise RpcError(
                    f"settings read-back: {flag} is {settings[flag]!r}, expected true"
                )

    def _initialize(self, proc: RpcProcess) -> None:
        plan = self.plan
        model, effort, autonomy = plan["settings"]
        params = {
            "machineId": "droid-bridge",
            "cwd": plan["work_dir"],
            "modelId": model,
            "reasoningEffort": effort,
            "autonomyLevel": autonomy,
            "interactionMode": "auto",
            "title": plan["title"],
            "disableBuiltinSkills": True,
            "autoRejectPermissionRequests": True,
        }
        if plan["system"]:
            params["systemPrompt"] = plan["system"]
        result, _ = proc.call("droid.initialize_session", params, self.cancel)
        self._check_protocol(proc)
        sid = result.get("sessionId")
        if not isinstance(sid, str) or not sid:
            raise RpcError("initialize_session: no sessionId in result")
        self._check_settings(result.get("settings"))
        session = (
            result.get("session") if isinstance(result.get("session"), dict) else {}
        )
        raw_msgs = session.get("messages")
        msgs = raw_msgs if isinstance(raw_msgs, list) else []
        self.sid = sid
        self.droid_real = sum(1 for m in msgs if not _is_service_message(m))
        self._disable_native_tools(proc)

    @staticmethod
    def _check_protocol(proc: RpcProcess) -> None:
        """Версия протокола живого droid обязана совпасть с квалифицированной в receipt (RW-009)."""
        if not RECEIPT_REQUIRED:
            return
        try:
            _, rec = _load_receipt()
        except LauncherUnavailable as exc:
            raise RpcError(f"droid receipt changed during spawn: {exc}")
        expected = rec["protocol"]["protocol_version"]
        if proc.protocol_version != expected:
            raise RpcError(
                f"droid protocol {proc.protocol_version or '-'} differs from qualified {expected}"
            )

    @staticmethod
    def _check_tools_policy(listed: list) -> None:
        """Каталог tools живого droid обязан совпасть с квалифицированным набором из receipt (RW-009)."""
        if not RECEIPT_REQUIRED:
            return
        try:
            _, rec = _load_receipt()
        except LauncherUnavailable as exc:
            raise RpcError(f"droid receipt changed during spawn: {exc}")
        if sorted(listed) != sorted(rec["tools_policy"]["disabled_tool_ids"]):
            raise RpcError(
                "native tool catalogue differs from the qualified tools policy"
            )

    def _disable_native_tools(self, proc: RpcProcess) -> None:
        """Нативные tools отключаются по АКТУАЛЬНОМУ list_tools (новые id тоже); сбой — fail-closed."""
        result, _ = proc.call("droid.list_tools", {}, self.cancel)
        tools = result.get("tools")
        if (
            not isinstance(tools, list)
            or not tools
            or not all(
                isinstance(t, dict) and isinstance(t.get("id"), str) and t["id"]
                for t in tools
            )
        ):
            raise RpcError("list_tools: invalid catalogue")
        ids = [t["id"] for t in tools]
        self._check_tools_policy(ids)
        keep = set(self.plan.get("keep_tools") or ())
        ids = [i for i in ids if i not in keep]
        if not ids:
            return
        _, stash = proc.call(
            "droid.update_session_settings", {"disabledToolIds": ids}, self.cancel
        )
        updated = self._wait_settings_updated(proc, stash)
        if updated is None:
            raise RpcError("native tools: settings_updated read-back not received")
        disabled = updated.get("disabledToolIds")
        if not isinstance(disabled, list):
            raise RpcError("native tools: disabledToolIds missing in read-back")
        if not set(ids).issubset(set(map(str, disabled))):
            raise RpcError("native tools were not disabled (read-back mismatch)")
        self._check_flags(updated)

    def _wait_settings_updated(
        self, proc: RpcProcess, stash: list, timeout: float = 2.0
    ) -> Any:
        """settings из нотификации settings_updated (read-back) или None, если не пришла."""

        def pick(notifs: list) -> Any:
            for params in notifs:
                note = params.get("notification") if isinstance(params, dict) else None
                if isinstance(note, dict) and note.get("type") == "settings_updated":
                    settings = note.get("settings")
                    return settings if isinstance(settings, dict) else {}
            return None

        found = pick(stash)
        end = time.monotonic() + timeout
        while found is None and time.monotonic() < end:
            if self.cancel.is_set():
                raise _Cancelled()
            event = proc.next_event(0.1)
            if event is None:
                continue
            if event[0] == "notif":
                found = pick([event[1]])
            elif event[0] == "eof":
                raise RpcEof(int(event[1] or 1))
        return found

    def _sync_settings(self, proc: RpcProcess, desired: tuple) -> None:
        """Смена model/effort/autonomy на границе хода: update + read-back."""
        current = self.plan["current_settings"]
        if tuple(current) == tuple(desired):
            return
        model, effort, autonomy = desired
        params = {
            "modelId": model,
            "reasoningEffort": effort,
            "autonomyLevel": autonomy,
        }
        _, stash = proc.call("droid.update_session_settings", params, self.cancel)
        settings = self._wait_settings_updated(proc, stash, timeout=5.0)
        if settings is None or "modelId" not in settings:
            raise _NeedRebase()  # read-back не подтвердился: безопасно — свежая generation
        self._check_settings(settings)

    def _load(self, proc: RpcProcess) -> bool:
        """load_session того же SID + проверка целостности; False -> свежая generation."""
        plan = self.plan
        try:
            result, _ = proc.call(
                "droid.load_session",
                {"sessionId": plan["sid"], "disableBuiltinSkills": True},
                self.cancel,
            )
        except RpcEof:
            raise
        except RpcError as exc:
            _log(
                f"session_rpc chat={plan['hash8']} restore_failed err={_err_summary(exc, 120)!r} fallback=history"
            )
            return False
        self._check_protocol(proc)
        session = (
            result.get("session") if isinstance(result.get("session"), dict) else {}
        )
        msgs = (
            session.get("messages")
            if isinstance(session.get("messages"), list)
            else None
        )
        if msgs is None or result.get("isAgentLoopInProgress"):
            _log(
                f"session_rpc chat={plan['hash8']} restore_failed reason=state fallback=history"
            )
            return False
        if _service_duplicates(msgs):
            _log(
                f"restore_integrity chat={plan['hash8']} verdict=DUPLICATE_SCAFFOLDING action=sanitize"
            )
            return False
        real = sum(1 for m in msgs if not _is_service_message(m))
        if plan["droid_real"] >= 0 and real != plan["droid_real"]:
            _log(
                f"restore_integrity chat={plan['hash8']} verdict=HISTORY_MISMATCH "
                f"droid={real} bridge={plan['droid_real']} action=sanitize"
            )
            return False
        self.sid = plan["sid"]
        self.droid_real = real
        settings = result.get("settings")
        self.plan["current_settings"] = (
            (
                settings.get("modelId"),
                settings.get("reasoningEffort"),
                settings.get("autonomyLevel") or "",
            )
            if isinstance(settings, dict)
            else ("", "", "")
        )
        self._disable_native_tools(proc)
        try:
            self._sync_settings(proc, plan["settings"])
        except _NeedRebase:
            return False
        return True

    def _send_items(self, proc: RpcProcess, items: list) -> bool:
        """Все входы кроме последнего — skipAgentLoop, последний запускает ровно один цикл.

        True — terminal хода уже получен до ACK (событие лежало в stash): ожидание и interrupt не нужны.
        """
        last = len(items) - 1
        done = False
        for index, item in enumerate(items):
            params = {"text": item["text"]}
            if item["role"] == "assistant":
                params["role"] = "assistant"
            if index < last:
                params["skipAgentLoop"] = True
                _, stash = proc.call("droid.add_user_message", params, self.cancel)
                self._absorb(stash)
            else:
                self.turn_req_id = proc.new_id()
                self.sent = True
                _, stash = proc.call(
                    "droid.add_user_message", params, self.cancel, rid=self.turn_req_id
                )
                done = self._absorb(stash)
        return done

    def _absorb(self, stash: list) -> bool:
        for params in stash:
            if self._on_notif(params):
                return True
        return False

    def _consume(self, proc: RpcProcess) -> None:
        grace_end = 0.0
        while True:
            if self.cancel.is_set() and not self.interrupted:
                self.interrupted = True
                grace_end = time.monotonic() + INTERRUPT_GRACE_S
                if self.sent:
                    proc.interrupt_quietly()
            if self.interrupted and time.monotonic() > grace_end:
                return
            event = proc.next_event(0.1)
            if event is None:
                continue
            kind = event[0]
            if kind == "notif":
                if self._on_notif(event[1]):
                    return
            elif kind == "resp":
                msg = event[1]
                if msg.get("id") == self.turn_req_id and msg.get("error") is not None:
                    raise RpcError(
                        "add_user_message: "
                        + str((msg["error"] or {}).get("message"))[:300]
                    )
                self._quarantined += (
                    1  # дубль ACK/ответ прежнего запроса: ход не завершает
                )
            elif kind == "eof":
                raise RpcEof(int(event[1] or 1))
            else:
                raise RpcError(f"{kind}: {str(event[1])[:200]}")

    # -- нотификации -------------------------------------------------------------
    def _slot_for(self, mid: str) -> dict:
        if mid not in self._msgs:
            self._charge(
                ENTRY_OVERHEAD_BYTES
            )  # пустые сообщения тоже расходуют бюджет хода
            # tb/kb — текущий размер, tc/kc — максимум уже учтённого в бюджете (короткий complete его не снижает)
            self._msgs[mid] = {
                "text": "",
                "thinking": "",
                "tb": 0,
                "kb": 0,
                "tc": 0,
                "kc": 0,
                "acc": ENTRY_OVERHEAD_BYTES,
            }
            self._order.append(mid)
        return self._msgs[mid]

    def _progress(self) -> None:
        self.last_progress = time.monotonic()
        self.got_event = True

    _MID_EVENTS = (
        "assistant_text_delta",
        "assistant_text_complete",
        "thinking_text_delta",
        "thinking_text_complete",
        "assistant_message_retracted",
    )

    def _on_notif(self, params: Any) -> bool:
        """True — получен terminal ТЕКУЩЕГО хода (события опубликованы)."""
        if not isinstance(params, dict):
            return False
        note = params.get("notification")
        if not isinstance(note, dict):
            return False
        # sessionId в реальном droid лежит в params (часть событий — внутри notification).
        got_sid = params.get("sessionId") or note.get("sessionId")
        if got_sid and got_sid != self.sid:
            self._quarantined += 1  # чужая/устаревшая сессия в карантин
            return False
        ntype = note.get("type")
        mid = str(note.get("messageId") or "")
        if ntype == "create_message":
            self._on_create(note, mid)
            return False
        if not self.armed:
            return False  # запоздавшее событие прежнего хода
        if ntype == "agent_turn_completed":
            # Принадлежность проверяется ДО _progress(): отклонённый terminal не сбрасывает watchdog.
            if not self._own_terminal(note):
                self._quarantined += 1
                return False
            self._progress()
            if self.proc is not None:
                self.proc.note_turn(str(note.get("turnId")), self._order)
            return self._terminal(note)
        if ntype in self._MID_EVENTS and not mid:
            self._quarantined += 1  # событие сообщения без messageId не подтверждено: ни прогресса, ни вывода (RW-007)
            return False
        if mid and self._is_foreign_mid(mid):
            self._quarantined += 1
            return False
        if mid and ntype in self._MID_EVENTS and mid not in self._own:
            # Сообщение не подтверждено цепочкой parentId: прогресса, слота и текста нет, событие ждёт свой create.
            self._hold(mid, ntype, note)
            return False
        self._progress()
        self._apply(ntype, mid, note)
        return False

    def _on_create(self, note: dict, mid: str) -> None:
        message = note.get("message") if isinstance(note.get("message"), dict) else {}
        role = message.get("role")
        counted_id = mid or str(message.get("id") or "")
        if role == "assistant":
            parent = str(message.get("parentId") or "")
            if (
                self._is_foreign_mid(counted_id)
                or self._is_foreign_parent(parent)
                or (self.armed and (not counted_id or parent not in self._own))
            ):
                self._drop_foreign(
                    counted_id
                )  # прежний ход или неподтверждённая цепочка: не наш и не в истории хода
                return
            if self.armed:
                self._own.add(counted_id)
        if (
            not _is_service_message(message)
            and not _is_blank_user_message(message)
            and (not counted_id or counted_id not in self._counted)
        ):
            self.droid_real += 1
            if counted_id:
                self._charge(ENTRY_OVERHEAD_BYTES + len(counted_id))
                self._counted.add(counted_id)
        if (
            role == "user"
            and note.get("requestId") == self.turn_req_id
            and self.turn_req_id
        ):
            self.armed = True
            # У реального droid turnId терминала равен id user-сообщения, запустившего ход.
            self.active_turn = str(message.get("id") or mid or "")
            if self.active_turn:
                self._own.add(self.active_turn)
            self._progress()
        elif role == "assistant" and self.armed:
            slot = self._slot_for(counted_id)
            self._release_held(counted_id)
            if not slot["text"]:
                self._set_slot_text(slot, "text", "tb", _message_text(message))
            if not slot["thinking"]:
                self._set_slot_text(slot, "thinking", "kb", _message_thinking(message))
            self._progress()

    @staticmethod
    def _held_size(mid: str, kept: dict) -> int:
        """Реальный размер удерживаемой записи: id сообщения, дельта и полный текст + накладные расходы."""
        payload = len(kept["textDelta"].encode("utf-8")) + len(
            (kept["text"] or "").encode("utf-8")
        )
        return ENTRY_OVERHEAD_BYTES + len(mid.encode("utf-8")) + payload

    def _hold(self, mid: str, ntype: str, note: dict) -> None:
        if ntype.endswith("_complete") and isinstance(note.get("text"), str):
            # complete несёт полный текст блока и вытесняет накопленные дельты: байты не считаются дважды.
            kind = ntype[: -len("_complete")]
            kept = []
            for entry in self._held.get(mid, []):
                if entry[0] in (kind + "_delta", ntype):
                    self._held_bytes -= entry[2]
                else:
                    kept.append(entry)
            self._held[mid] = kept
        if len(mid) > MAX_HELD_MID_CHARS:
            raise RpcError(f"message id exceeds {MAX_HELD_MID_CHARS} chars")
        # Сохраняются только поля, нужные _apply: остальной note (произвольные поля сервера) не удерживается.
        kept = {
            "textDelta": str(note.get("textDelta") or ""),
            "text": note["text"] if isinstance(note.get("text"), str) else None,
        }
        size = self._held_size(mid, kept)
        self._held_bytes += size
        if self._acc_bytes + self._held_bytes > MAX_TURN_TEXT_BYTES:
            raise RpcError(f"turn output exceeds limit {MAX_TURN_TEXT_BYTES} bytes")
        self._held.setdefault(mid, []).append((ntype, kept, size))

    def _release_held(self, mid: str, apply: bool = True) -> None:
        """События mid, пришедшие раньше его create_message: применить (сообщение подтверждено) либо выбросить."""
        for ntype, note, size in self._held.pop(mid, []):
            self._held_bytes -= size
            if apply:
                self._apply(ntype, mid, note)

    def _apply(self, ntype: Any, mid: str, note: dict) -> None:
        if ntype == "assistant_text_delta" and mid:
            delta = str(note.get("textDelta") or "")
            slot = self._slot_for(mid)
            size = len(delta.encode("utf-8"))
            slot["text"] += delta
            slot["tb"] += size
            slot["tc"] += size
            self._charge(size, slot)
        elif ntype == "assistant_text_complete" and mid:
            slot = self._slot_for(mid)
            if isinstance(note.get("text"), str):
                self._set_slot_text(slot, "text", "tb", note["text"])
        elif ntype == "thinking_text_delta" and mid:
            delta = str(note.get("textDelta") or "")
            slot = self._slot_for(mid)
            size = len(delta.encode("utf-8"))
            slot["thinking"] += delta
            slot["kb"] += size
            slot["kc"] += size
            self._charge(size, slot)
        elif ntype == "thinking_text_complete" and mid:
            slot = self._slot_for(mid)
            if isinstance(note.get("text"), str):
                self._set_slot_text(slot, "thinking", "kb", note["text"])
        elif ntype == "assistant_message_retracted" and mid:
            slot = self._msgs.pop(mid, None)
            if slot is not None:
                self._acc_bytes = max(0, self._acc_bytes - slot["acc"])
            if mid in self._order:
                self._order.remove(mid)
            if mid in self._counted:
                # Сообщение удалено из истории droid: счётчик согласуется с его историей.
                self._counted.discard(mid)
                self.droid_real -= 1
        elif ntype == "error":
            self._last_error = str(
                note.get("message") or note.get("errorType") or "droid error"
            )[:300]

    def _own_terminal(self, note: dict) -> bool:
        """terminal принадлежит ТЕКУЩЕМУ ходу: непустой turnId, не завершённый ранее, равный id запустившего user.

        У реального droid turnId есть только у agent_turn_completed и равен id user-сообщения хода
        (create_message с requestId нашего add). Пока id user-сообщения неизвестен, терминал не принимается
        (fail-closed): ход закончится по watchdog, а не по чужому событию.
        """
        turn_id = str(note.get("turnId") or "")
        if not turn_id or not self.active_turn:
            return False
        if self.proc is not None and turn_id in self.proc.finished_turns:
            return False
        return turn_id == self.active_turn

    def _is_foreign_mid(self, mid: str) -> bool:
        return mid in self._foreign_mids or (
            self.proc is not None and mid in self.proc.finished_mids
        )

    def _is_foreign_parent(self, parent: str) -> bool:
        """parentId ассистентского сообщения указывает на другой (уже завершённый или чужой) ход."""
        if not parent:
            return False
        if self.proc is not None and parent in self.proc.finished_turns:
            return True
        return False

    def _drop_foreign(self, mid: str) -> None:
        """Выбросить уже накопленное сообщение чужого хода: его байты и вывод не принадлежат текущему."""
        self._quarantined += 1
        if mid:
            self._foreign_mids.add(mid)
            slot = self._msgs.pop(mid, None)
            if slot is not None:
                self._acc_bytes = max(0, self._acc_bytes - slot["acc"])
            if mid in self._order:
                self._order.remove(mid)
            self._release_held(mid, apply=False)

    def _charge(self, size: int, slot: dict | None = None) -> None:
        """Бюджет хода MAX_TURN_TEXT_BYTES: текст, размышления и метаданные (сообщения, слоты) вместе.

        Сверх лимита — RpcError (ход завершается ошибкой, процесс и слоты возвращаются).
        """
        self._acc_bytes += size
        if slot is not None:
            slot["acc"] += size
        if self._acc_bytes + self._held_bytes > MAX_TURN_TEXT_BYTES:
            raise RpcError(f"turn output exceeds limit {MAX_TURN_TEXT_BYTES} bytes")

    def _set_slot_text(
        self, slot: dict, field: str, size_field: str, text: str
    ) -> None:
        """*_complete несёт полный текст: бюджет получает только прирост к максимуму уже учтённого."""
        size = len(text.encode("utf-8"))
        charged = "tc" if field == "text" else "kc"
        if size > slot[charged]:
            self._charge(size - slot[charged], slot)
            slot[charged] = size
        slot[field] = text
        slot[size_field] = size

    def _terminal(self, note: dict) -> bool:
        reason = str(note.get("reason") or "")
        if self.cancel.is_set() or reason not in ("completed", "permission_rejected"):
            if not self.cancel.is_set():
                self.q.put(
                    (
                        "stream_error",
                        self._last_error or f"turn ended: {reason or 'unknown'}",
                    )
                )
            return True
        final_text = ""
        for mid in self._order:
            slot = self._msgs.get(mid) or {}
            if slot.get("thinking"):
                self.q.put(("reasoning", slot["thinking"]))
            if slot.get("text"):
                self.q.put(("text", slot["text"]))
                final_text = slot["text"]
        self.ok = True
        self.q.put(
            (
                "result",
                {
                    "finalText": final_text,
                    "session_id": self.sid,
                    "duration_ms": note.get("durationMs"),
                    "num_turns": None,
                    "usage": _map_usage(note.get("tokenUsage")),
                },
            )
        )
        self.q.put(("done", (0, final_text)))
        return True

    # -- завершение ----------------------------------------------------------------
    def close(self) -> None:
        """Отмена хода: interrupt, ожидание terminal в пределах грейса; процесс не закрывается."""
        self.cancel.set()
        self.thread.join(timeout=INTERRUPT_GRACE_S + 1.0)


def _close_async(proc: RpcProcess, mode: str) -> None:
    """Закрытие в фоне: финальные кадры клиенту не ждут waitpid (слот P держится до него)."""
    try:
        threading.Thread(target=proc.close, kwargs={"mode": mode}, daemon=True).start()
    except RuntimeError:
        proc.close(
            mode=mode
        )  # поток не создан: закрываем синхронно, иначе процесс и слот P остались бы навсегда


def _make_plan(
    ctx: dict, chat: Chat | None, cfg: str, work_dir: str, keep_tools: list
) -> dict:
    """Путь хода под арендой чата: hot | restore | rebase | cold | ephemeral.

    Префикс совпал (цепочка, cfg, SID) -> в RPC уходит только непросмотренный
    суффикс; любое расхождение/форк/правка/компакция/смена system|tools|cwd или
    нездоровое состояние -> свежая generation с replay всей истории запроса.
    Fuzzy-сопоставления нет.
    """
    rpc = ctx["rpc"]
    items = rpc["items"]
    plan = {
        "path": "ephemeral",
        "send": items,
        "all_items": items,
        "system": rpc["system"],
        "work_dir": work_dir,
        "settings": (ctx["model"], ctx["effort"], ctx["autonomy"]),
        "current_settings": ("", "", ""),
        "title": "bridge-title" if ctx["route"] == "title" else "droid-dsh-bridge",
        "sid": "",
        "droid_real": -1,
        "hash8": chat.key_hash[:8] if chat is not None else "-",
        "keep_tools": keep_tools,
        "need_slot": True,
        "handoff": None,
        "dead_proc": None,
    }
    if chat is None:
        return plan
    proc = chat.proc
    if proc is not None and not proc.alive():
        plan["dead_proc"] = proc
        proc = None
    count = chat.n
    prefix_ok = (
        chat.state in ("READY", "PERSISTED")
        and bool(chat.sid)
        and chat.cfg == cfg
        and 0 < count < len(items)
        and _chain_head(items, count) == chat.head
    )
    if prefix_ok and proc is not None:
        plan.update(
            path="hot",
            send=items[count:],
            need_slot=False,
            sid=chat.sid,
            droid_real=chat.droid_real,
            current_settings=chat.settings,
        )
    elif prefix_ok and chat.restore_count < RESTORE_MAX:
        plan.update(
            path="restore", send=items[count:], sid=chat.sid, droid_real=chat.droid_real
        )
    else:
        plan["path"] = "rebase" if proc is not None else "cold"
        plan["handoff"] = proc
        plan["need_slot"] = proc is None
    return plan


def _finish_attempt(
    chat: Chat | None, plan: dict, run: Run, out: dict, ok: bool, cfg: str, items: list
) -> int:
    """Итог попытки: commit префикса и метаданных либо инвалидация чата. -> число ходов чата."""
    proc = run.proc
    if not ok:
        # Недоставленный/неполный ход: user мог попасть в контекст droid -> только
        # свежая generation; процесс закрывается (слот возвращается после waitpid).
        try:
            if chat is not None:
                chat.proc = None
                chat.state = "DIRTY"
                _persist_chat(chat)
        finally:
            if proc is not None:
                _close_async(proc, "term")
        return 0
    if chat is None:
        # Эфемерная сессия (nokey/title/image) никому не нужна после ответа: быстрое закрытие без
        # close_session, иначе слот P держался бы до ~10 с (RW-013).
        if proc is not None:
            _close_async(proc, "term")
        return 1
    new_generation = run.path in ("cold", "rebase")
    if new_generation:
        chat.generation += 1
        chat.restore_count = 0
    elif run.path == "restore":
        chat.restore_count += 1
    chat.proc = proc
    chat.sid = run.sid
    chat.cfg = cfg
    chat.n = len(items) + 1
    projection = _projection_digest(out.get("text") or "", out.get("tool_calls") or [])
    chat.head = _chain(_chain_head(items, len(items)), projection)
    chat.settings = plan["settings"]
    chat.droid_real = run.droid_real
    chat.turns += 1
    chat.last_used = _clock()
    chat.state = "READY"
    if not _persist_chat(chat):
        # Commit не записан: успех клиенту не выдаётся, процесс закрывается, чат DIRTY -> только
        # новая generation (после рестарта запись на диске PENDING/отсутствует — продолжения старого SID нет).
        chat.proc = None
        chat.state = "DIRTY"
        if proc is not None:
            _close_async(proc, "term")
        raise PersistError("chat state commit failed")
    return chat.turns


def _client_gone(sock: socket.socket) -> bool:
    try:
        ready, _, _ = select.select([sock], [], [], 0)
        return bool(ready) and sock.recv(1, socket.MSG_PEEK) == b""
    except (OSError, ValueError):
        return True


class _ByteBudget:
    """Резерв байт admission по заявленному Content-Length (C-11)."""

    def __init__(self, total: int):
        self.total = int(total)
        self._used = 0
        self._lock = threading.Lock()

    def reserve(self, amount: int) -> bool:
        with self._lock:
            if self._used + amount > self.total:
                return False
            self._used += amount
            return True

    def release(self, amount: int) -> None:
        with self._lock:
            self._used = max(0, self._used - int(amount))


_DELIVERY_BUDGET = _ByteBudget(MAX_DELIVERY_BYTES)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 300
    _delivery_reserved = 0  # байты, взятые в _DELIVERY_BUDGET текущим запросом (RW-011)

    def log_message(self, fmt: str, *args: Any) -> None:
        _log("http " + (fmt % args))

    def handle_error(self, request: Any, client_address: Any) -> None:
        _log(f"http accept error from {client_address}")

    def _client_tag(self) -> str:
        return f"{self.client_address[0]}:{self.client_address[1]}"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(code))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _emit(self, data: str) -> bool:
        try:
            self.wfile.write(data.encode("utf-8"))
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def _log_reject(
        self, reason: str, model: str = "unknown", model_len: int = 0
    ) -> None:
        """Строка отказа в журнал (строгий формат RW-013)."""
        _log(
            f"reject reason={reason} model={model or 'unknown'} "
            f"model_len={int(model_len)} client={self._client_tag()}"
        )

    def _reject(
        self,
        code: int,
        reason: str,
        message: str,
        model: str = "unknown",
        model_len: int = 0,
    ) -> None:
        """Отказ (до SSE): строка `reject …` в журнал и общий формат ошибки."""
        self._log_reject(reason, model, model_len)
        self.close_connection = True
        self._send(
            code, {"error": {"message": message, "type": reason, "code": int(code)}}
        )

    def _acquire_slot(self, keepalive):
        """Ждём слот семафора до QUEUE_TIMEOUT_S, попутно keepalive и проверка клиента."""
        waited = time.monotonic()
        last_ka = 0.0
        while not _slots.acquire(timeout=1.0):
            if _client_gone(self.connection):
                return "client_gone"
            if time.monotonic() - waited > QUEUE_TIMEOUT_S:
                return "queue_timeout"
            if keepalive is not None and time.monotonic() - last_ka >= KEEPALIVE_S:
                last_ka = time.monotonic()
                if not keepalive():
                    return "client_gone"
        return ""

    def _execute(self, run: Run, keepalive, emulate_tools: bool) -> dict:
        """Гнать ход до конца; сквозной таймаут TIMEOUT_S на весь ход.

        Клиенту во время вычисления пишется только keepalive (False — клиент ушёл). Вывод
        НЕ доставляется здесь: он копится в out["events"] (content/reasoning/tool_call по
        порядку) и уходит клиенту отдельным этапом после освобождения T/L и checkpoint
        (RW-009). Размышления идут мимо ToolCallParser. При emulate_tools текстовый поток
        проходит через ToolCallParser: блоки <tool_call> выделяются как вызовы.
        Превышение deadline -> kill группы (в run.close()), state=timeout.
        """
        pieces = []
        events: list = []
        tool_calls: list = []
        usage = {}
        result_ev = {}
        last_ka = time.monotonic()
        deadline = time.monotonic() + TIMEOUT_S

        def state(name: str, rc: int, err: str = "") -> dict:
            return {
                "rc": rc,
                "text": "".join(pieces),
                "usage": usage,
                "result": result_ev,
                "state": name,
                "err": err,
                "session_id": result_ev.get("session_id") or "",
                "duration_ms": result_ev.get("duration_ms"),
                "num_turns": result_ev.get("num_turns"),
                "tool_calls": tool_calls,
                "events": events,
            }

        def add_content(text: str) -> None:
            if not text:
                return
            pieces.append(text)
            events.append(("content", text))

        def add_call(call: dict) -> None:
            entry = {
                "index": len(tool_calls),
                "id": "call_" + uuid.uuid4().hex[:24],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                },
            }
            tool_calls.append(entry)
            events.append(("tool_call", entry))

        parser = ToolCallParser(add_content, add_call) if emulate_tools else None

        while True:
            if time.monotonic() > deadline:
                return state("timeout", 124, f"proxy timeout after {TIMEOUT_S}s")
            if (
                not run.got_event
                and time.monotonic() - run.started > FIRST_TOKEN_TIMEOUT_S
            ):
                return state(
                    "first_token_timeout",
                    124,
                    f"no droid event within {FIRST_TOKEN_TIMEOUT_S:g}s",
                )
            if (
                run.got_event
                and run.last_progress
                and time.monotonic() - run.last_progress > SILENCE_WATCHDOG_S
            ):
                # Тишина: сбрасывают только события ТЕКУЩЕГО хода (не keepalive/чужие).
                return state(
                    "timeout", 124, f"no droid progress within {SILENCE_WATCHDOG_S:g}s"
                )
            if _client_gone(self.connection):
                return state("client_gone", 1)
            try:
                kind, payload = run.q.get(timeout=1.0)
            except queue.Empty:
                if keepalive is not None and time.monotonic() - last_ka >= KEEPALIVE_S:
                    last_ka = time.monotonic()
                    if not keepalive():
                        return state("client_gone", 1)
                continue
            if kind == "text":
                # Событие message несёт ПОЛНЫЙ текст сообщения, не дельту:
                # между сообщениями вставляем разделитель "\n\n" (как
                # droid-cli-proxy), чтобы несколько message-событий не
                # склеивались в одно слово.
                delta = payload if not pieces else "\n\n" + payload
                if parser is not None:
                    parser.feed(delta)
                else:
                    add_content(delta)
            elif kind == "reasoning":
                events.append(("reasoning", str(payload)))
            elif kind == "result":
                result_ev = payload
                usage = payload.get("usage") or {}
            elif kind == "stream_error":
                return state("droid_error", 1, str(payload))
            elif kind == "pump_error":
                return state("pump_error", 1, str(payload))
            elif kind == "done":
                rc, final_text = payload
                if parser is not None:
                    parser.finish()  # досбрасываем хвост незакрытого блока текстом
                # Fallback: события message не дали ни текста, ни вызовов, но итог
                # есть в completion.finalText. Проводим его тем же путём (парсер +
                # on_text), чтобы потоковый клиент не получил пустой ответ со stop.
                if not pieces and not tool_calls and final_text:
                    if parser is not None:
                        parser.feed(final_text)
                        parser.finish()
                    else:
                        add_content(final_text)
                time.sleep(0.05)
                return state("done", rc, "".join(run.err_box))

    def _poll_wait(self, started: float, keepalive, state: dict) -> str:
        """Один тик ожидания (аренда чата, ёмкость P): клиент, таймаут очереди, keepalive."""
        if _client_gone(self.connection):
            return "client_gone"
        now = time.monotonic()
        if now - started > QUEUE_TIMEOUT_S:
            return "queue_timeout"
        if keepalive is not None and now - state["last_ka"] >= KEEPALIVE_S:
            state["last_ka"] = now
            if not keepalive():
                return "client_gone"
        return ""

    def _acquire_chat(self, chat: Chat, keepalive, state: dict) -> str:
        """Аренда чата L: запросы одного ключа идут строго по очереди, ничего не удерживая."""
        started = time.monotonic()
        REGISTRY.add_waiter(chat)
        try:
            while not chat.lock.acquire(timeout=1.0):
                reason = self._poll_wait(started, keepalive, state)
                if reason:
                    return reason
            return ""
        finally:
            REGISTRY.drop_waiter(chat)

    def _no_slot(self, ctx: dict, reason: str) -> dict:
        """Отказ на ожидании аренды/ёмкости/хода: ответ отдаёт вызывающая ветка."""
        _log(f"no slot ({reason}) model={ctx['model']} {ctx['tag']}")
        if reason == "queue_timeout":
            # HTTP-ответ отдаст _serve_json/_serve_sse: в SSE заголовки уже ушли.
            self._log_reject("overloaded", ctx["model"], ctx["model_len"])
        return {
            "state": reason,
            "rc": 1,
            "text": "",
            "usage": {},
            "result": {},
            "err": "",
            "tool_calls": [],
            "events": [],
        }

    def _run_once(self, ctx: dict, keepalive) -> dict:
        """Ход запроса: порядок ресурсов L -> P -> T, до 3 попыток при транзиентном сбое.

        Возвращает итог с буфером вывода (out["events"]); к моменту возврата T/L уже освобождены
        и checkpoint записан — клиенту вывод отдаёт вызывающая ветка (RW-009).
        """
        model = ctx["model"]
        effort = ctx["effort"]
        autonomy = ctx["autonomy"]
        tag = ctx["tag"]
        t0 = time.monotonic()
        out: dict = {}
        img_dir = None
        chat = None
        chat_held = False
        poll_state = {"last_ka": 0.0}
        run = None
        open_attempt = None
        committed_turns = 0
        cfg = (
            ""  # заданы до ветвлений: finally видит их и при раннем исключении (RW-004)
        )
        rpc = ctx["rpc"]
        try:
            try:
                _launcher()
            except LauncherUnavailable:
                # Гонка с удалением лончера: ответ отдаёт вызывающая ветка.
                self._log_reject("launcher_unavailable", model, ctx["model_len"])
                return {
                    "state": "launcher_unavailable",
                    "rc": 1,
                    "text": "",
                    "usage": {},
                    "result": {},
                    "err": "",
                    "tool_calls": [],
                    "events": [],
                }
            if ctx["route"] == "keyed":
                chat = REGISTRY.get(ctx["key_hash"])
                reason = self._acquire_chat(chat, keepalive, poll_state)
                if reason:
                    return self._no_slot(ctx, reason)
                chat_held = True
            images = ctx.get("images") or []
            if images:
                img_dir = WORKSPACE / ("img-" + uuid.uuid4().hex)
                total_bytes = 0
                try:
                    img_dir.mkdir(parents=True, exist_ok=True)
                    os.chmod(img_dir, 0o700)
                    for image in images:
                        target = img_dir / image["name"]
                        target.write_bytes(image["data"])
                        os.chmod(target, 0o600)
                        total_bytes += len(image["data"])
                except OSError as exc:
                    # ENOSPC, отказ chmod и пр. при spool картинок: предусмотренная ошибка 502, каталог чистится в finally.
                    _log(f"spool_error err={_err_summary(exc, 120)!r}")
                    return {
                        "state": "spool_error",
                        "rc": 1,
                        "text": "",
                        "usage": {},
                        "result": {},
                        "err": "",
                        "tool_calls": [],
                        "events": [],
                    }
                img_stats = (
                    len(images),
                    total_bytes,
                    ",".join(image["mime"] for image in images),
                )
            else:
                img_stats = None
            work_dir = _work_dir_for(ctx["cwd"], img_dir)
            rpc = ctx["rpc"]
            cfg = _config_digest(rpc["system"], work_dir)
            keep_tools = ["Read"] if images else []
            for attempt in (1, 2, 3):
                plan = _make_plan(ctx, chat, cfg, work_dir, keep_tools)
                holds_slot = False
                dead = plan.pop("dead_proc")
                if dead is not None:
                    chat.proc = None
                    dead.close(mode="term", term_wait=0.5, kill_wait=0.5)
                old = plan.pop("handoff")
                if old is not None:
                    # rebase: слот P старого процесса передаётся новому без возврата в пул.
                    chat.proc = None
                    old.close(mode="term", keep_slot=True)
                    holds_slot = True
                t_held = False
                new_run = None
                try:
                    # Любая ошибка между взятием слотов P/T и созданием Run возвращает их (RW-012):
                    # после создания Run слот P принадлежит ему, а T освобождает внутренний finally.
                    if plan["need_slot"] and not holds_slot:
                        waited = time.monotonic()
                        reason = POOL.acquire(
                            lambda: self._poll_wait(waited, keepalive, poll_state)
                        )
                        if reason:
                            return self._no_slot(ctx, reason)
                        holds_slot = True
                    reason = self._acquire_slot(keepalive)
                    if reason:
                        if holds_slot:
                            POOL.release()
                            holds_slot = False
                        return self._no_slot(ctx, reason)
                    t_held = True
                    image_part = ""
                    if img_stats:
                        image_part = " images=%d image_bytes=%d image_types=%s" % (
                            img_stats[0],
                            img_stats[1],
                            img_stats[2],
                        )
                    _log(
                        f"exec model={model} effort={effort} effort_source={ctx['effort_source']} "
                        f"autonomy={autonomy} autonomy_source={ctx['autonomy_source']} "
                        f"prompt_bytes={len(ctx['prompt'].encode())}{image_part} {tag}"
                    )
                    if (
                        plan["path"] in ("cold", "rebase", "ephemeral")
                        and ctx.get("instr", (0, "-", 0))[2]
                    ):
                        sections, omitted, nbytes = ctx["instr"]
                        _log(
                            f"instr_guard sections={sections} omitted={omitted} bytes={nbytes}"
                        )
                    if (
                        chat is not None
                        and chat.sid
                        and plan["path"] in ("hot", "restore")
                    ):
                        # Отпечаток ожидающего хода ДО add: после падения моста — только replay.
                        # Не записан — ход не стартует (иначе рестарт продолжил бы старый SID неоднозначно).
                        try:
                            _write_record(chat, "PENDING")
                        except (OSError, StateConflict, ValueError, TypeError) as exc:
                            chat.state = "DIRTY"
                            _log(
                                f"session_rpc chat={chat.key_hash[:8]} persist_failed "
                                f"err={_err_summary(exc, 120)!r}"
                            )
                            stale, chat.proc = chat.proc, None
                            if stale is not None:
                                _close_async(stale, "term")
                            _slots.release()
                            t_held = False
                            if holds_slot:
                                POOL.release()
                                holds_slot = False
                            return {
                                "state": "persist_error",
                                "rc": 1,
                                "text": "",
                                "usage": {},
                                "result": {},
                                "err": "chat state is not writable",
                                "tool_calls": [],
                                "events": [],
                            }
                    _log(
                        f"session_rpc chat={plan['hash8']} key={1 if chat is not None else 0} "
                        f"path={plan['path']} gen={(chat.generation if chat else 0)} "
                        f"sid={plan['sid'][:8] or '-'}"
                    )
                    if chat is not None and plan["path"] in ("cold", "rebase"):
                        # Новая generation: SID известен только после initialize, PENDING пишется Run до первого add.
                        plan["before_add"] = functools.partial(_write_pending, chat)
                    new_run = Run(
                        plan, chat.proc if plan["path"] == "hot" else None, holds_slot
                    )
                    holds_slot = False
                except Exception as exc:  # noqa: BLE001 - любая ошибка подготовки хода: ресурсы назад, штатный 502
                    if new_run is None:
                        if t_held:
                            _slots.release()
                        if holds_slot:
                            POOL.release()
                    _log(
                        f"session_rpc chat={plan['hash8']} attempt_setup_failed "
                        f"err={_err_summary(repr(exc), 160)!r}"
                    )
                    out = {
                        "state": "pump_error",
                        "rc": 1,
                        "text": "",
                        "usage": {},
                        "result": {},
                        "err": repr(exc)[:500],
                        "tool_calls": [],
                        "events": [],
                    }
                    break
                except BaseException:
                    if new_run is None:
                        if t_held:
                            _slots.release()
                        if holds_slot:
                            POOL.release()
                    raise
                run = new_run
                open_attempt = (plan, run)
                try:
                    out = self._execute(run, keepalive, ctx["emulate_tools"])
                finally:
                    try:
                        run.close()
                    finally:
                        _slots.release()
                ok = bool(run.ok and out.get("state") == "done" and out.get("rc") == 0)
                try:
                    committed_turns = _finish_attempt(
                        chat, plan, run, out, ok, cfg, rpc["items"]
                    )
                except PersistError:
                    # Commit не записан: успешный ответ клиенту не выдаётся, повтор хода не делаем.
                    open_attempt = None
                    out = {
                        "state": "persist_error",
                        "rc": 1,
                        "text": "",
                        "usage": {},
                        "result": {},
                        "err": "chat state commit failed",
                        "tool_calls": [],
                        "events": [],
                    }
                    break
                open_attempt = None
                if ok:
                    break
                delivered = bool(out.get("text") or out.get("tool_calls"))
                # Контент до terminal не отдаётся, поэтому delivered здесь — страховка.
                if out["state"] != "done" or delivered or attempt == 3:
                    break
                # Транзиентный сбой (rc!=0, клиенту ничего не выдано): повтор невидим;
                # он строится заново из истории запроса, а не повтором user в старую сессию.
                _log(
                    f"transient failure rc={out['rc']} err={_err_summary(out.get('err'), 120)!r}, "
                    f"retry {attempt} {tag}"
                )
                # Сбой egress не должен сохранять SKIP-префлайт: повтор идёт с полным префлайтом.
                _last_ok[0] = 0.0
                _sleep(2 * attempt)
            ok_done = bool(
                run is not None
                and run.ok
                and out.get("state") == "done"
                and out.get("rc") == 0
            )
            hot = bool(ok_done and run.path in ("hot", "restore"))
            usage = out.get("usage") or {}
            rep_turns = committed_turns if ok_done else 0
            sess8 = ((run.sid if ok_done else plan["sid"]) or "")[:8] or "-"
            raw_in = usage.get("input_tokens", 0)
            raw_out = usage.get("output_tokens", 0)
            _log(
                f"usage sess={sess8} raw={raw_in}/{raw_out} "
                f"rep={raw_in}/{raw_out} resumed={1 if hot else 0} turns={rep_turns}"
            )
        finally:
            # Независимые звенья: сбой одного (например, _finish_attempt) не оставляет аренду L и ссылку на чат.
            try:
                if open_attempt is not None:
                    # Исключение посреди хода: чат инвалидируется, процесс не остаётся «в середине хода».
                    _finish_attempt(
                        chat,
                        open_attempt[0],
                        open_attempt[1],
                        {},
                        False,
                        cfg,
                        rpc["items"],
                    )
            finally:
                try:
                    if img_dir is not None:
                        shutil.rmtree(str(img_dir), ignore_errors=True)
                finally:
                    try:
                        if chat_held:
                            chat.lock.release()
                    finally:
                        if chat is not None:
                            REGISTRY.release(chat)
        if out.get("state") != "client_gone":
            _last_ok[0] = (
                time.monotonic()
                if (out.get("state") == "done" and out.get("rc") == 0)
                else 0.0
            )
        _log(
            f"done model={model} rc={out['rc']} state={out['state']} "
            f"sess={sess8} resumed={1 if hot else 0} turns={rep_turns} "
            f"out_bytes={len(out['text'].encode())} wall_s={time.monotonic() - t0:.1f} "
            f"err={_err_summary(out.get('err'))!r} {tag}"
        )
        return out

    @staticmethod
    def _error_body(out: dict) -> Any:
        st = out.get("state")
        label = str(out.get("backend_kind") or "droid")  # имя бинарника в тексте ошибки
        if st == "timeout":
            return {
                "message": f"{label} exec timed out after {TIMEOUT_S}s",
                "type": "timeout",
                "code": 504,
            }
        if st == "first_token_timeout":
            return {
                "message": f"first_token_timeout: droid exec gave no event within "
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
        if st == "spool_error":
            return {
                "message": "bridge storage is full or unavailable",
                "type": "proxy_error",
                "code": 502,
            }
        if st == "persist_error":
            return {
                "message": "bridge could not persist chat state; the turn was not accepted",
                "detail": str(out.get("err"))[:200],
                "type": "proxy_error",
                "code": 502,
            }
        if st == "pump_error":
            return {
                "message": "bridge reader failed",
                "detail": str(out.get("err"))[:500],
                "type": "proxy_error",
                "code": 502,
            }
        if st == "droid_error":
            return {
                "message": str(out.get("err") or "droid exec reported an error")[:500],
                "type": "droid_error",
                "code": 502,
            }
        if st == "backend_error":
            return {
                "message": f"{label} exec failed rc={out.get('rc')}",
                "detail": str(out.get("err"))[:500],
                "type": "proxy_error",
                "code": 502,
            }
        if out.get("rc") != 0 or not (out.get("text") or out.get("tool_calls")):
            return {
                "message": f"{label} exec exited rc={out.get('rc')}",
                "detail": str(out.get("err"))[:500],
                "type": "proxy_error",
                "code": 502,
            }
        return None

    def _reserve_delivery(self, out: dict) -> Any:
        """Резерв памяти ответа до выдачи (RW-011): None — взят, иначе тело ошибки 502 proxy_error."""
        size = _delivery_size(out)
        if not _DELIVERY_BUDGET.reserve(size):
            _log(f"delivery_budget_exhausted bytes={size}")
            return {
                "message": "bridge overloaded: delivery memory budget exhausted",
                "type": "proxy_error",
                "code": 502,
            }
        self._delivery_reserved = size
        return None

    # ---- HTTP --------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/v1/health"):
            # Контракт из семи ключей прежний (расширять запрещено); ok = AND по обязательным
            # бэкендам (droid: невалидный receipt = spawn невозможен -> ok=false, RW-015),
            # active и max_concurrent суммируются по включённым бэкендам.
            required = [a for a in BACKENDS.adapters() if a.required]
            self._send(
                200,
                {
                    "ok": all(a.is_healthy() for a in required),
                    "transport": "droid-exec",
                    "model": MODEL_ID,
                    "active": BACKENDS.active_total(),
                    "max_concurrent": BACKENDS.max_concurrent_total(),
                    "tool_emulation": True,
                    "uptime_s": int(time.time() - _started),
                },
            )
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
            # Объединение моделей всех активных адаптеров; порядок — как в fleet.json, модель по умолчанию первой.
            published = {m["id"]: (a, m) for a, m in BACKENDS.models()}
            order = [MODEL_ID] + [mid for mid in FLEET["order"] if mid != MODEL_ID]
            data = []
            for mid in order:
                if mid not in published:
                    continue
                adapter, model = published[mid]
                data.append(
                    {
                        "id": mid,
                        "object": "model",
                        "owned_by": adapter.owned_by,
                        "created": 0,
                        "context_length": model["context_window"],
                    }
                )
            self._send(200, {"object": "list", "data": data})
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
        if _shutting_down:
            self._reject(503, "overloaded", "bridge is shutting down")
            return
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
        # (1) framing: Transfer-Encoding не поддерживаем, Content-Length строго числовой.
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
        # (2) длина тела: 413 до чтения.
        if length > int((FLEET.get("image_limits") or {}).get("max_body_bytes") or 0):
            self._reject(
                413, "payload_too_large", "request body exceeds the bridge limit"
            )
            return
        # (3) admission: резерв байт по заявленному Content-Length до чтения тела.
        reserved = 0
        budget = _budget
        if budget is not None and length:
            if not budget.reserve(length):
                self._reject(
                    503, "overloaded", "bridge overloaded: body budget exhausted"
                )
                return
            reserved = length
        try:
            raw = self.rfile.read(length) if length else b""
            # (4) короткое тело.
            if len(raw) < length:
                self._reject(400, "invalid_request", "request body truncated")
                return
            # (5) JSON и (6) JSON-объект.
            try:
                req = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._reject(400, "invalid_request", "invalid json")
                return
            if not isinstance(req, dict):
                self._reject(400, "invalid_request", "request must be a JSON object")
                return
            # (7) путь.
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
            # (8) модель.
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
            # (9) effort: строго из allowed модели, без клампов и алиасов.
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
            # (9a) autonomy: low|medium|high|off -> `autonomyLevel` RPC
            # (off — read-only droid, Reviewer-пути); дефолт high (максимум).
            raw_autonomy = req.get("autonomy")
            if raw_autonomy is None:
                autonomy = AUTONOMY_DEFAULT
                autonomy_source = "default"
            elif isinstance(raw_autonomy, str):
                candidate = raw_autonomy.strip()
                if not candidate:
                    autonomy = AUTONOMY_DEFAULT
                    autonomy_source = "default"
                elif candidate in AUTONOMY_LEVELS or candidate == AUTONOMY_OFF:
                    autonomy = candidate
                    autonomy_source = "request"
                else:
                    self._reject(
                        400,
                        "unsupported_autonomy",
                        "autonomy is not allowed (low|medium|high|off)",
                        model_id,
                        model_len,
                    )
                    return
            else:
                self._reject(
                    400,
                    "unsupported_autonomy",
                    "autonomy must be a string",
                    model_id,
                    model_len,
                )
                return
            # (10) reasoning-объект не поддерживаем.
            if "reasoning" in req and req.get("reasoning") is not None:
                self._reject(
                    400,
                    "unsupported_parameter",
                    "reasoning parameter is not supported",
                    model_id,
                    model_len,
                )
                return
            # (11) изображения (C-08…C-11).
            try:
                images = _collect_images(req, model, effort)
            except ImageReject as exc:
                self._reject(
                    400,
                    exc.reason,
                    f"image rejected: {exc.reason}",
                    model_id,
                    model_len,
                )
                return
            # (12) бэкенд модели: допуск/лончер проверяются до SSE и до любого запуска.
            adapter = BACKENDS.get(model["backend"])
            ok, why = (
                (False, "backend_disabled") if adapter is None else adapter.preflight()
            )
            if not ok:
                self._reject(
                    503,
                    "launcher_unavailable",
                    "canonical launcher is missing or not executable"
                    if why == "launcher_unavailable"
                    else f"backend {model['backend']} is unavailable: {why}",
                    model_id,
                    model_len,
                )
                return
            raw_messages = req.get("messages")
            messages = raw_messages if isinstance(raw_messages, list) else []
            raw_tools = req.get("tools")
            tools = (
                [t for t in raw_tools if isinstance(t, dict)]
                if isinstance(raw_tools, list)
                else []
            )
            tool_choice = req.get("tool_choice")
            emulate_tools = bool(tools) and not _tool_choice_none(tool_choice)
            prompt = _messages_to_prompt(messages, tools, tool_choice, images)
            extra = (
                req.get("extra_body") if isinstance(req.get("extra_body"), dict) else {}
            )
            cwd = str(extra.get("cwd") or "")
            # Маршрут хода: нового 400 на ключ нет — плохой/отсутствующий ключ = холодная
            # изолированная сессия с replay истории запроса.
            transcript = _transcribe(messages, tools, tool_choice, images)
            raw_key = req.get("prompt_cache_key")
            keyed = isinstance(raw_key, str) and 0 < len(raw_key) <= KEY_MAX_LEN
            if images:
                route = "image"
            elif _is_title_request(messages, tools, req):
                route = "title"
            elif not transcript["runnable"]:
                route = "fallback"
                transcript = {
                    "system": None,
                    "runnable": True,
                    "items": [
                        {"role": "user", "text": prompt, "digest": _digest(prompt)}
                    ],
                }
            elif keyed:
                route = "keyed"
            else:
                route = "nokey"
            instr = self._prompt_guard(
                messages, route, raw_key, cwd, model_id, model_len, adapter
            )
            if instr is None:
                return
            ctx = {
                "route": route,
                "key_hash": _key_hash(raw_key)
                if (route == "keyed" and isinstance(raw_key, str))
                else "",
                "rpc": transcript,
                "instr": instr if route in ("keyed", "nokey") else (0, "-", 0),
                "model": model_id,
                "backend": model["backend"],
                "model_len": model_len,
                "effort": effort,
                "effort_source": effort_source,
                "autonomy": autonomy,
                "autonomy_source": autonomy_source,
                "prompt": prompt,
                "images": images,
                "cwd": cwd,
                "emulate_tools": emulate_tools,
                "tag": (
                    f"client={self._client_tag()} "
                    f"ua={(self.headers.get('User-Agent') or '-')[:60]}"
                ),
                "stream": bool(req.get("stream")),
            }
            if ctx["stream"]:
                self._serve_sse(ctx)
            else:
                self._serve_json(ctx)
        finally:
            if reserved and budget is not None:
                budget.release(reserved)
            _DELIVERY_BUDGET.release(self._delivery_reserved)
            self._delivery_reserved = 0

    def _prompt_guard(
        self,
        messages: list,
        route: str,
        raw_key: Any,
        cwd: str,
        model_id: str,
        model_len: int,
        adapter: Any,
    ) -> Any:
        """Фасадный контур b_guard / REQ-003 для ВСЕХ бэкендов: до выбора процесса и до адаптера.

        Блок agent-instructions — свойство клиента DSH, а не бинарника, поэтому гард общий и
        отключению per-backend не подлежит (fail-closed). Возвращает сводку `instr` либо None,
        если отказ уже отправлен клиенту.
        """
        in_kb = _in_kb_cwd(cwd)
        try:
            blocks = _instr_blocks(messages, in_kb) if route != "title" else []
            instr = _instr_scan(messages, in_kb) if blocks else (0, "-", 0)
        except CanonPersistError:
            # Код из базовой таксономии (503 launcher_unavailable): ход без подтверждённой истории канона не идёт.
            self._reject(
                503,
                "launcher_unavailable",
                "canon history is not persisted: request refused before launch",
                model_id,
                model_len,
            )
            return None
        guard_state, guard_reasons, guard_max = GUARD.snapshot()
        over = _instr_violation(blocks, guard_max)
        if guard_state == "unsafe" and blocks:
            # Профиль DSH небезопасен (alert уже в журнале): размер не режем немым 400, а явно
            # отказываем только НОВЫМ чатам; живые резидентные чаты продолжают (RW-008).
            refuse = not _chat_known(route, raw_key, adapter)
            if refuse or over is not None:
                top = over or (
                    instr[2],
                    _instr_limit(max(blocks, key=lambda b: b["bytes"]), guard_max),
                )
                _log(
                    f"instr_gate_alert guard=unsafe refused={int(refuse)} bytes={top[0]} limit={top[1]}"
                )
            if refuse:
                # Код из базовой таксономии отказов (503 launcher_unavailable), клиенты DSH нового кода не знают.
                self._reject(
                    503,
                    "launcher_unavailable",
                    "instruction guard is unsafe ("
                    + "; ".join(guard_reasons)[:200]
                    + "): new chats are refused until the DSH profile is fixed",
                    model_id,
                    model_len,
                )
                return None
        elif over is not None:
            # REQ-003: блок agent-instructions сверх применимого предела не доходит ни до spawn, ни до add.
            _log(
                f"instr_gate_alert reason=REQ003_SIZE_EXCEEDED bytes={over[0]} limit={over[1]}"
            )
            self._reject(
                503,
                "launcher_unavailable",
                f"agent-instructions block {over[0]} bytes exceeds {over[1]}: request refused before launch",
                model_id,
                model_len,
            )
            return None
        return instr

    def _dispatch(self, ctx: dict, keepalive) -> dict:
        """Ход через адаптер бэкенда модели; общий разбор `<tool_call>` и итог в формате фасада."""
        adapter = BACKENDS.get(ctx["backend"])
        if adapter is None:
            return {
                "state": "launcher_unavailable",
                "rc": 1,
                "text": "",
                "usage": {},
                "result": {},
                "err": "",
                "tool_calls": [],
                "events": [],
            }
        ctx["handler"] = self
        ctx["keepalive"] = keepalive
        ctx["client_gone"] = lambda: _client_gone(self.connection)
        t0 = time.monotonic()
        out = finalize_turn(adapter.execute_turn(ctx, None), ctx["emulate_tools"])
        out.setdefault("backend_kind", adapter.kind)
        if (
            adapter.kind != "droid"
        ):  # droid-путь пишет свои done/usage строки в _run_once
            # RW-007: сырой stderr/terminal reason бэкенда может содержать пользовательский
            # текст; в постоянный журнал идут только коды и размеры (сырой err — в ответ клиенту).
            _log(
                f"done model={ctx['model']} backend={adapter.id} rc={out.get('rc')} "
                f"state={out.get('state')} out_bytes={len(str(out.get('text') or '').encode())} "
                f"wall_s={time.monotonic() - t0:.1f} "
                f"err_bytes={len(str(out.get('err') or '').encode())} {ctx['tag']}"
            )
        return out

    def _serve_json(self, ctx: dict) -> None:
        out = self._dispatch(ctx, None)
        if out.get("state") == "client_gone":
            return
        err = self._error_body(out) or self._reserve_delivery(out)
        if err is not None:
            self._send(err["code"], {"error": err})
            return
        usage = out.get("usage") or {}
        # content и arguments вызовов сериализуются отдельно и вставляются на место меток: большой текст
        # не проходит через дополнительный dict -> dumps -> encode (RW-012).
        marker = "@@content-" + uuid.uuid4().hex + "@@"
        message: dict = {"role": "assistant", "content": marker}
        finish = "stop"
        arg_markers: list = []
        values = [out["text"]]
        if out.get("tool_calls"):
            calls = []
            for call in out["tool_calls"]:
                arg_markers.append("@@args-" + uuid.uuid4().hex + "@@")
                values.append(call["function"]["arguments"])
                calls.append(
                    dict(
                        call, function=dict(call["function"], arguments=arg_markers[-1])
                    )
                )
            message["tool_calls"] = calls
            finish = "tool_calls"
        shell = json.dumps(
            {
                "id": f"chatcmpl-droid-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": ctx["model"],
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                    "total_tokens": usage.get("input_tokens", 0)
                    + usage.get("output_tokens", 0),
                },
            },
            ensure_ascii=False,
        )
        segments = []
        rest = shell
        for mark in [marker] + arg_markers:
            head, rest = rest.split(json.dumps(mark), 1)
            segments.append(head.encode("utf-8"))
        segments.append(rest.encode("utf-8"))
        # Content-Length считается проходом по срезам, тело пишется вторым проходом: целиком
        # экранированная копия текста (до MAX_TURN_TEXT_BYTES) в памяти не строится.
        total = sum(len(seg) for seg in segments) + 2 * len(values)
        for value in values:
            for piece in _text_slices(value):
                total += len(_escape_json_piece(piece))
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(total))
        self.end_headers()
        for index, value in enumerate(values):
            self.wfile.write(segments[index] + b'"')
            for piece in _text_slices(value):
                self.wfile.write(_escape_json_piece(piece))
            self.wfile.write(b'"')
        self.wfile.write(segments[-1])

    def _emit_tool_call(self, chunk: Any, call: dict) -> bool:
        """Вызов инструмента одним кадром; arguments больше среза — фрагментами (OpenAI-стриминг, RW-012)."""
        slices = _text_slices(call["function"]["arguments"])
        first_piece = next(slices, "")
        second_piece = next(slices, None)
        if second_piece is None:
            return self._emit(chunk({"tool_calls": [call]}))
        first = dict(call, function=dict(call["function"], arguments=first_piece))
        if not self._emit(chunk({"tool_calls": [first]})):
            return False
        return all(
            self._emit(
                chunk(
                    {
                        "tool_calls": [
                            {"index": call["index"], "function": {"arguments": piece}}
                        ]
                    }
                )
            )
            for piece in itertools.chain([second_piece], slices)
        )

    def _serve_sse(self, ctx: dict) -> None:
        completion_id = f"chatcmpl-droid-{uuid.uuid4().hex[:12]}"
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

        def chunk(delta: dict, finish=None) -> str:
            return (
                "data: "
                + json.dumps(
                    {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": shown_model,
                        "choices": [
                            {"index": 0, "delta": delta, "finish_reason": finish}
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        def keepalive() -> bool:
            return self._emit(": keepalive\n\n")

        if not self._emit(chunk({"role": "assistant", "content": ""})):
            return
        out = self._dispatch(ctx, keepalive)
        if out.get("state") == "client_gone":
            _log("client gone mid-stream, child killed")
            return
        err = self._error_body(out) or self._reserve_delivery(out)
        if err is None:
            # Доставка — отдельный этап: T/L уже свободны, checkpoint записан; обрыв клиента
            # здесь ни на что, кроме самого ответа, не влияет.
            for kind, value in out.get("events") or []:
                if kind in ("content", "reasoning"):
                    field = "content" if kind == "content" else "reasoning_content"
                    # Большое событие выдаётся срезами: в памяти одновременно только один срез SSE-кадра.
                    delivered = (
                        all(
                            self._emit(chunk({field: piece}))
                            for piece in _text_slices(value)
                        )
                        if value
                        else self._emit(chunk({field: value}))
                    )
                else:
                    delivered = self._emit_tool_call(chunk, value)
                if not delivered:
                    _log("client gone during delivery; turn already committed")
                    return
            finish = "tool_calls" if out.get("tool_calls") else "stop"
            self._emit(chunk({}, finish))
            # Harness считает tok/s и % контекста только из usage в потоке
            # (dsh-llm-pi-ai toStreamChunks: usage-chunk -> session usage ->
            # tokenUsage/contextPressure). Без этого чанка метрики пустые.
            # Шлём только при ненулевых токенах, чтобы нулевой usage от droid
            # не превращался в ложные "0 tok/s / 0%".
            out_usage = out.get("usage") or {}
            prompt_toks = out_usage.get("input_tokens", 0)
            compl_toks = out_usage.get("output_tokens", 0)
            if prompt_toks or compl_toks:
                self._emit(
                    "data: "
                    + json.dumps(
                        {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": shown_model,
                            "choices": [
                                {"index": 0, "delta": {}, "finish_reason": finish}
                            ],
                            "usage": {
                                "prompt_tokens": prompt_toks,
                                "completion_tokens": compl_toks,
                                "total_tokens": prompt_toks + compl_toks,
                            },
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
        else:
            self._emit(
                "data: " + json.dumps({"error": err}, ensure_ascii=False) + "\n\n"
            )
        self._emit("data: [DONE]\n\n")


class Server(ThreadingHTTPServer):
    """HTTP-сервер с семафором числа соединений на уровне приёма (C-11)."""

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

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._conn_sem.acquire(blocking=False):
            try:
                peer = f"{client_address[0]}:{client_address[1]}"
            except (TypeError, IndexError):
                peer = "unknown"
            _log(f"reject reason=overloaded model=unknown model_len=0 client={peer}")
            try:
                if isinstance(request, socket.socket):
                    self._send_raw_503(request)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._conn_sem.release()


def _sweep_workspace(cutoff_s: float = 3600.0) -> None:
    """Удалить ходы muse и prompt-*/img-* старше cutoff (наследие упавших ходов, RW-010).

    Подметаются per-turn подкаталоги muse (`muse/turn-*`) и legacy `muse/prompt-*.txt`:
    после SIGKILL хаба они остаются без владельца. `cutoff_s=0` — уборка на shutdown.
    """
    cutoff = time.time() - cutoff_s
    for pattern in ("prompt-*.txt", "muse/prompt-*.txt", "muse/turn-*"):
        for path in WORKSPACE.glob(pattern):
            try:
                if path.stat().st_mtime >= cutoff:
                    continue
                if path.is_dir():
                    shutil.rmtree(str(path), ignore_errors=True)
                else:
                    path.unlink()
            except OSError:
                pass
    for path in WORKSPACE.glob("img-*"):
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(str(path), ignore_errors=True)
        except OSError:
            pass


def main() -> None:
    global _budget
    if not AUTH_KEY:
        sys.stderr.write("DROID_DSH_BRIDGE_KEY is required; refusing to start\n")
        raise SystemExit(1)
    _budget = _ByteBudget(int(FLEET["admission"]["max_inflight_body_bytes"]))
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        writer_lock = acquire_writer_lock()
    except OSError as exc:
        # Каталог состояния чужой/недоступен/не 0700: старт отклоняется понятным сообщением, а не трассировкой.
        sys.stderr.write(f"state directory is not usable ({exc}); refusing to start\n")
        raise SystemExit(1)
    if writer_lock is None:
        sys.stderr.write(
            "another bridge instance holds the state writer lock; refusing to start\n"
        )
        raise SystemExit(1)
    _sweep_workspace()
    reconcile_children()
    if RECEIPT_REQUIRED:
        try:
            _droid_image()
        except LauncherUnavailable as exc:
            _log(
                f"droid_receipt_invalid err={_err_summary(exc, 120)!r}: spawn disabled until "
                f"tools/droid_image.py writes a valid receipt (see README, section Deployment)"
            )
    _canon_seen_load()
    GUARD.check_once()
    GUARD.start()
    REGISTRY.start_reaper()
    _log(f"fleet_sha256={FLEET['sha256']} models={len(FLEET['order'])}")
    for mid in FLEET["order"]:
        model = FLEET["models"][mid]
        if (model.get("images") or {}).get("status") == "confirmed":
            reason = _image_proof_reason(model)
            if reason:
                _log(f"image_proof_invalid model={mid} reason={reason}")
    signal.signal(signal.SIGTERM, _kill_all)
    signal.signal(signal.SIGINT, _kill_all)
    server = Server((HOST, PORT), Handler)
    _log(
        f"listen {HOST}:{PORT} model={MODEL_ID} max_concurrent={MAX_CONCURRENT} "
        f"queue_timeout={QUEUE_TIMEOUT_S}s timeout={TIMEOUT_S}s keepalive={KEEPALIVE_S}s"
    )
    print(f"[droid-bridge] listening on http://{HOST}:{PORT}/v1", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
