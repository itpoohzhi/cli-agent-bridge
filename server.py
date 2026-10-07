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
import hashlib
import json
import os
import queue
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
HOST = os.environ.get("DROID_DSH_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("DROID_DSH_BRIDGE_PORT", "9882"))
AUTH_KEY = os.environ.get("DROID_DSH_BRIDGE_KEY", "").strip()
LAUNCHER = os.environ.get("DROID_LAUNCHER", str(HOME / ".config" / "factory-launch" / "droid-cli.sh"))
FLEET_PATH = Path(os.environ.get("DROID_DSH_BRIDGE_FLEET", "") or str(ROOT / "fleet.json"))
ENV_MODEL = os.environ.get("DROID_DSH_BRIDGE_MODEL", "").strip()
IMAGE_PROBE = os.environ.get("DROID_DSH_BRIDGE_IMAGE_PROBE", "") == "1"
WORKSPACE = ROOT / "workspace"
MAX_CONCURRENT = int(os.environ.get("DROID_DSH_BRIDGE_MAX_CONCURRENT", "4"))
QUEUE_TIMEOUT_S = int(os.environ.get("DROID_DSH_BRIDGE_QUEUE_TIMEOUT", "900"))
TIMEOUT_S = int(os.environ.get("DROID_DSH_BRIDGE_TIMEOUT", "1800"))
KEEPALIVE_S = float(os.environ.get("DROID_DSH_BRIDGE_KEEPALIVE", "15"))
# Таймаут первого события stream-json от `droid exec` (с момента старта процесса).
FIRST_TOKEN_TIMEOUT_S = float(os.environ.get("DROID_BRIDGE_FIRST_TOKEN_TIMEOUT_S", "90"))
# Окно после успешного хода, в котором лончеру передаётся DROID_SKIP_PREFLIGHT=1.
PREFLIGHT_SKIP_WINDOW_S = 120.0
TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"

# Уровни reasoning, допустимые в каталоге (dev-контекст выбирает fleet.json).
EFFORT_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")
# Уровни автономности даунстрим-исполнителя (`droid exec --auto`): дефолт HIGH —
# максимум; OFF = флаг `--auto` опущен (read-only режим droid, Reviewer-пути).
AUTONOMY_LEVELS = ("low", "medium", "high")
AUTONOMY_OFF = "off"
AUTONOMY_DEFAULT = "high"
# Уровни автономности даунстрим-исполнителя (`droid exec --auto`): дефолт HIGH —
# максимум; OFF = флаг `--auto` опущен (read-only режим droid, Reviewer-пути).
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
IMAGE_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}


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
    for key in ("droid_version", "droid_binary_sha256", "method", "impl_version", "formats"):
        if key not in proof:
            raise FleetViolation("confirmed_proof_malformed", model_id)
    if not isinstance(proof.get("droid_version"), str) or not isinstance(proof.get("droid_binary_sha256"), str):
        raise FleetViolation("confirmed_proof_malformed", model_id)
    if not re.fullmatch(r"[0-9a-f]{64}", str(proof.get("droid_binary_sha256") or "")):
        raise FleetViolation("confirmed_proof_malformed", model_id)
    if proof.get("method") != method:
        raise FleetViolation("confirmed_proof_malformed", model_id)
    if not isinstance(proof.get("impl_version"), int) or isinstance(proof.get("impl_version"), bool):
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


def _build_catalog(data: Any) -> dict:
    """Проверить каталог (C-01, класс I) и вернуть нормализованный словарь."""
    if not isinstance(data, dict):
        raise FleetViolation("fleet_unreadable", "-")
    if data.get("schema_version") != 2:
        raise FleetViolation("schema_version_invalid", "-")
    limits = data.get("image_limits")
    if not isinstance(limits, dict):
        raise FleetViolation("limits_invalid", "-")
    for key in ("max_images", "max_image_bytes", "max_total_image_bytes", "max_body_bytes"):
        if not isinstance(limits.get(key), int) or isinstance(limits.get(key), bool) or limits[key] <= 0:
            raise FleetViolation("limits_invalid", "-")
    if not isinstance(limits.get("types"), list) or not limits["types"]:
        raise FleetViolation("limits_invalid", "-")
    admission = data.get("admission")
    if not isinstance(admission, dict):
        raise FleetViolation("admission_invalid", "-")
    for key in ("max_http_connections", "max_inflight_body_bytes"):
        if not isinstance(admission.get(key), int) or isinstance(admission.get(key), bool) or admission[key] <= 0:
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
        if (not isinstance(efforts, list) or not efforts
                or not all(isinstance(e, str) for e in efforts)
                or any(e not in EFFORT_LEVELS for e in efforts)):
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
        if not isinstance(input_types, list) or not all(isinstance(t, str) for t in input_types):
            raise FleetViolation("status_inconsistent", mid)
        if images.get("cli_registry") == "explicit_unsupported" and status != "unsupported":
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
            if method is None or "image" not in input_types or "text" not in input_types:
                raise FleetViolation("status_inconsistent", mid)
            if not IMAGE_PROBE:
                raise FleetViolation("probe_flag_missing", mid)
        method = images.get("method")
        if method is not None and method not in IMPLEMENTED_METHODS:
            raise FleetViolation("method_not_implemented", mid)
        models[mid] = {
            "id": mid,
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
    technical_ref = data.get("technical_ref") if isinstance(data.get("technical_ref"), dict) else {}
    return {
        "schema_version": data.get("schema_version"),
        "catalogue": str(data.get("catalogue") or ""),
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
    sys.stderr.write(f"fleet_invalid model={violation.model} reason={violation.reason}\n")
    sys.stderr.flush()
    raise SystemExit(1)

MODEL_ID = ENV_MODEL or FLEET["default_model"]

# Токеноподобные последовательности: длинные (>=24) и явные Factory-ключи `fk-`
# любой длины — короткий ключ иначе проходил мимо маскировщика в журнал.
_SECRET = re.compile(r"[A-Za-z0-9_\-]{24,}|fk-[A-Za-z0-9_\-]{4,}")
_NOISE = re.compile(r"NODE_TLS_REJECT_UNAUTHORIZED|--trace-warnings|^\(node:\d+\)", re.I)

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
TITLE_SYSTEM_PREFIX = ("Create a concise title for an AI coding-assistant session "
                       "from the supplied human messages.")
TITLE_USER_PREFIX = "Generate the session title from this JSON array of human messages:"
TITLE_MAX_TOKENS = 64
RPC_API_VERSION = "1.0.0"

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
    """Канонический лончер обязателен; запасного пути на голый бинарь нет."""
    if os.path.isfile(LAUNCHER) and os.access(LAUNCHER, os.X_OK):
        return LAUNCHER
    raise LauncherUnavailable(LAUNCHER)


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


def _flatten_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(p for p in parts if p)
    return str(content)


def _render_content(content: Any, counter: list) -> str:
    """Содержимое сообщения -> текст; на месте изображений маркер `[image N]`.

    Нумерация сквозная по порядку появления во всей истории. Неизвестные
    НЕ-image части (например input_audio) молча пропускаются, как раньше.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "image_url":
                    counter[0] += 1
                    parts.append(f"[image {counter[0]}]")
                elif "text" in item and item.get("text") is not None:
                    parts.append(str(item["text"]))
        return "\n".join(p for p in parts if p)
    return str(content)


def _normalize_arguments(value: Any) -> dict | None:
    """arguments -> JSON-объект; None, если значение задано, но объектом не является.

    None отличает невалидные аргументы (строку-не-JSON, список, число, null) от
    отсутствия ключа: вызывающий код не вправе молча подменять их на пустой словарь
    и запускать инструмент с пустыми аргументами.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                parsed = json.loads(text)
            except ValueError:
                return None
            if isinstance(parsed, dict):
                return parsed
    return None


def _normalize_tool_call(item: Any) -> dict:
    """Один OpenAI tool_call -> {"id", "name", "arguments"}.

    id сохраняется, чтобы результат [tool result <id>] однозначно сопоставлялся
    с конкретным вызовом при нескольких одинаковых инструментах.
    """
    if not isinstance(item, dict):
        return {"id": "", "name": "", "arguments": {}}
    fn = item.get("function") if isinstance(item.get("function"), dict) else {}
    name = fn.get("name") or item.get("name") or ""
    args = fn.get("arguments")
    if args is None:
        args = item.get("arguments")
    normalized = _normalize_arguments(args)
    return {
        "id": str(item.get("id") or ""),
        "name": str(name),
        "arguments": normalized if normalized is not None else {},
    }


def _render_tool_call(item: Any) -> str:
    """Историю вызова рендерим тем же блоком, что просим от модели."""
    payload = json.dumps(_normalize_tool_call(item), ensure_ascii=False)
    return f"{TOOL_CALL_OPEN}{payload}{TOOL_CALL_CLOSE}"


def _tool_choice_none(tool_choice: Any) -> bool:
    """tool_choice:"none" — инструменты не предлагаем вовсе."""
    return isinstance(tool_choice, str) and tool_choice.strip().lower() == "none"


def _tool_choice_name(tool_choice: Any) -> str:
    """Имя обязательного инструмента из tool_choice ("" — без принуждения)."""
    if not isinstance(tool_choice, dict):
        return ""
    fn = tool_choice.get("function") if isinstance(tool_choice.get("function"), dict) else {}
    name = fn.get("name") or tool_choice.get("name") or ""
    return str(name) if name else ""


def _tools_section(tools: list, tool_choice: Any, has_attachments: bool = False) -> str:
    """Английская секция протокола и схем инструментов для промпта."""
    lines = [
        "[system]",
        "# Tool calling protocol",
        "You may call the external tools listed below.",
        "When you need a tool, output ONLY blocks exactly in this form:",
        f'{TOOL_CALL_OPEN}{{"name": "<tool_name>", "arguments": {{<json>}}}}{TOOL_CALL_CLOSE}',
        "You may output several such blocks in a row. Do not narrate around them.",
        "Tool results arrive later as lines like [tool result <id>] with the result text.",
        "If no tool is needed, reply normally in plain text.",
        "Never attempt to use built-in tools; the only tools available are the ones listed here.",
    ]
    if has_attachments:
        lines[-1] += ", except Read on the attachment files listed under [attachments]."
    if tool_choice == "required":
        lines.append("You MUST call at least one tool now.")
    else:
        forced = _tool_choice_name(tool_choice)
        if forced:
            lines.append(f'You MUST call the tool "{forced}" now.')
    lines.append("")
    lines.append("Available tools:")
    for item in tools:
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "")
        desc = str(fn.get("description") or "")
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        lines.append(f"- {name}: {desc}")
        lines.append("  parameters: " + json.dumps(params, ensure_ascii=False))
    return "\n".join(lines)


def _render_message(msg: Any, counter: list) -> str:
    """Одно сообщение истории -> текстовый блок (с рендером tool-вызовов/результатов)."""
    if not isinstance(msg, dict):
        return ""
    role = str(msg.get("role") or "user")
    if role == "tool":
        call_id = str(msg.get("tool_call_id") or msg.get("id") or "")
        name = str(msg.get("name") or "")
        text = _render_content(msg.get("content"), counter)
        header = f"[tool result {call_id}]"
        if name:
            header += f" ({name})"
        return f"{header}\n{text}" if text.strip() else header
    text = _render_content(msg.get("content"), counter)
    if role == "assistant":
        parts = []
        if text.strip():
            parts.append(text)
        calls = msg.get("tool_calls")
        if isinstance(calls, list):
            parts.extend(_render_tool_call(tc) for tc in calls)
        body = "\n".join(p for p in parts if p)
        return f"[assistant]\n{body}" if body.strip() else ""
    if text.strip():
        return f"[{role}]\n{text}"
    return ""


def _attachments_section(images: list) -> str:
    """Хвост промпта метода workspace-read (эталон — kit/mkprompt.py)."""
    lines = [
        "[attachments]",
        "This request includes %d image(s) as local files in the working directory. "
        "The markers [image N] in the conversation refer to them in order." % len(images),
    ]
    for index, image in enumerate(images, 1):
        lines.append("- [image %d] ./%s (%s, %d bytes)" % (
            index, image["name"], image["mime"], len(image["data"])))
    lines.append(
        "Open each image with the Read tool on exactly these paths before answering about it "
        "(Read is the only built-in tool you may use, and only on these files). Do not claim to "
        "see an image you have not opened. If an image cannot be opened, say so explicitly "
        "instead of guessing.")
    return "\n".join(lines)


def _messages_to_prompt(messages: list, tools: list | None = None,
                        tool_choice: Any = None, images: list | None = None) -> str:
    """Собрать единый текстовый промпт; при наличии tools — с секцией протокола.

    При наличии изображений в конец добавляется секция [attachments], а строка
    протокола инструментов получает исключение для Read (C-09).
    """
    tools = tools or []
    counter = [0]
    blocks = []
    for msg in messages:
        rendered = _render_message(msg, counter)
        if rendered:
            blocks.append(rendered)
    head = []
    if tools and not _tool_choice_none(tool_choice):
        head.append(_tools_section(tools, tool_choice, bool(images)))
    text = "\n\n".join(head + blocks).strip() or "Reply with exactly: PONG"
    if images:
        text = text + "\n\n" + _attachments_section(images)
    return text


def _strip_code_fence(text: str) -> str:
    """Снять обёртку ```…``` (в т.ч. ```json) вокруг JSON внутри блока."""
    body = text.strip()
    if body.startswith("```"):
        newline = body.find("\n")
        body = body[newline + 1:] if newline != -1 else body[3:]
    if body.rstrip().endswith("```"):
        body = body.rstrip()[:-3]
    return body.strip()


def _parse_tool_call_block(inner: str) -> dict | None:
    """Содержимое блока -> {"name","arguments"}; None, если блок невалиден.

    Отсутствие ключа arguments — допустимый вызов с {}; присутствующее, но
    не-объектное значение (строка-не-JSON, список, число, null) — вызов
    отклоняем, чтобы не запускать инструмент с пустыми аргументами.
    """
    try:
        obj = json.loads(_strip_code_fence(inner))
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    name = obj.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    if "arguments" not in obj:
        arguments: dict = {}
    else:
        arguments = _normalize_arguments(obj.get("arguments"))
        if arguments is None:
            return None
    return {"name": name.strip(), "arguments": arguments}


class ToolCallParser:
    """Поток текстовых дельт -> content и завершённые вызовы инструментов.

    Тег <tool_call> может прийти разорванным между дельтами: хвост, который может
    оказаться началом тега, удерживается и не уходит в content до разрешения.
    """

    def __init__(self, on_content, on_tool_call):
        self._buf = ""
        self._on_content = on_content
        self._on_tool_call = on_tool_call

    def feed(self, text: str) -> None:
        self._buf += text
        self._drain(final=False)

    def finish(self) -> None:
        self._drain(final=True)

    def _drain(self, final: bool) -> None:
        while True:
            start = self._buf.find(TOOL_CALL_OPEN)
            if start == -1:
                if final:
                    self._flush_all()
                    return
                keep = self._pending_prefix()
                if keep:
                    self._emit(self._buf[:-keep])
                    self._buf = self._buf[-keep:]
                else:
                    self._flush_all()
                return
            if start > 0:
                self._emit(self._buf[:start])
                self._buf = self._buf[start:]
            end = self._find_close_outside_string(len(TOOL_CALL_OPEN))
            if end == -1:
                if final:
                    self._flush_all()  # незакрытый/невалидный блок отдаём текстом
                return
            inner = self._buf[len(TOOL_CALL_OPEN):end]
            self._buf = self._buf[end + len(TOOL_CALL_CLOSE):]
            call = _parse_tool_call_block(inner)
            if call is None:
                self._emit(TOOL_CALL_OPEN + inner + TOOL_CALL_CLOSE)
            else:
                self._on_tool_call(call)

    def _find_close_outside_string(self, start: int) -> int:
        """Позиция `</tool_call>` вне строковых литералов JSON, или -1.

        Закрывающий тег внутри JSON-строки (например значение аргумента содержит
        `</tool_call>`) границей блока не является. Экранированные кавычки `\\"`
        строку не закрывают.
        """
        index = start
        length = len(self._buf)
        in_string = False
        escaped = False
        while index < length:
            char = self._buf[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif self._buf.startswith(TOOL_CALL_CLOSE, index):
                return index
            index += 1
        return -1

    def _pending_prefix(self) -> int:
        """Длина хвоста — префикса открывающего тега (его нельзя отдать в content)."""
        limit = min(len(TOOL_CALL_OPEN) - 1, len(self._buf))
        for length in range(limit, 0, -1):
            if self._buf[-length:] == TOOL_CALL_OPEN[:length]:
                return length
        return 0

    def _emit(self, text: str) -> None:
        if text:
            self._on_content(text)

    def _flush_all(self) -> None:
        if self._buf:
            text, self._buf = self._buf, ""
            self._on_content(text)


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
    payload = url[comma + 1:]
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
        image["name"] = "img-%d.%s" % (index, IMAGE_EXTENSIONS.get(image["mime"], "bin"))
    return images


def _clean_err(text: str) -> str:
    lines = [ln for ln in (text or "").splitlines() if ln.strip() and not _NOISE.search(ln)]
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
    for proc in procs:
        if proc.busy:
            proc.interrupt_quietly()
    threads = []
    for proc in procs:
        thread = threading.Thread(
            target=proc.close,
            kwargs={"mode": "graceful", "graceful_wait": grace * 0.45,
                    "term_wait": grace * 0.2, "kill_wait": grace * 0.15},
            daemon=True)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))
    for proc in procs:
        proc.force_kill()
    return len(procs)


def _kill_all(*_: Any) -> None:
    """SIGTERM/SIGINT моста: graceful-закрытие детей (общий грейс 4,5 с) и выход."""
    closed = shutdown_all()
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


class ModelMismatch(Exception):
    """Фактические model/effort/autonomy не равны запрошенным: молча не подменяем."""


class _Cancelled(Exception):
    """Ход отменён вызывающей стороной (клиент ушёл, таймаут)."""


class _NeedRebase(Exception):
    """Живой процесс нельзя использовать (settings не подтвердились): свежая generation."""


def _proc_start_sig(pid: int) -> str:
    """Подпись старта процесса (`ps lstart`): защита от повторного использования PID."""
    try:
        res = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=3)
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
            _log(f"session_rpc children_registry_write_failed err={_err_summary(exc, 80)!r}")


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
            _log(f"session_rpc children_registry_write_failed err={_err_summary(exc, 80)!r}")
    return killed


def _mkdir_private(path: Path) -> None:
    """Каталог 0700 вместе с недостающими родителями внутри состояния."""
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            continue
        os.chmod(directory, 0o700)


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
        self._write_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._next_id = 0
        try:
            launcher = _launcher()
            WORKSPACE.mkdir(parents=True, exist_ok=True)
            cmd = [launcher, "exec", "--input-format", "stream-jsonrpc",
                   "--output-format", "stream-jsonrpc"]
            self.proc = subprocess.Popen(
                cmd, cwd=work_dir, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True, env=_child_env())
        except BaseException:
            if holds_slot:
                self.holds_slot = False
                pool.release()
            raise
        self.pid = self.proc.pid
        with _active_lock:
            _active[self.pid] = self.proc
            _rpc_procs[self.pid] = self
        _children_update(add={"pid": self.pid, "start": _proc_start_sig(self.pid),
                              "bridge_pid": os.getpid()})
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._err_reader = threading.Thread(target=self._drain_stderr, daemon=True)
        self._reader.start()
        self._err_reader.start()

    # -- чтение ----------------------------------------------------------------
    def _drain_stderr(self) -> None:
        try:
            self.err_box.append(_clean_err((self.proc.stderr.read() or b"").decode("utf-8", "replace")))
        except (OSError, ValueError) as exc:
            self.err_box.append(f"stderr unreadable: {exc!r}")

    def _read(self) -> None:
        try:
            for raw in iter(self.proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("{"):
                    continue  # шум лончера/preflight, как и раньше
                try:
                    msg = json.loads(line)
                except ValueError:
                    self.inbox.put(("bad_json", line[:200]))
                    continue
                if not isinstance(msg, dict):
                    self.inbox.put(("bad_json", line[:200]))
                    continue
                self._on_message(msg)
        except (OSError, ValueError) as exc:
            self.inbox.put(("pump_error", repr(exc)))
        rc = self.proc.wait()
        time.sleep(0.05)  # дать стоку stderr дозавершиться
        self.dead = True
        self.inbox.put(("eof", rc))

    def _on_message(self, msg: dict) -> None:
        method = msg.get("method")
        if method is None:
            if "id" in msg and ("result" in msg or "error" in msg):
                self.inbox.put(("resp", msg))
            return
        if msg.get("id") is not None:
            # Серверные запросы (разрешения): ответ отрицательный, ход не виснет.
            self.server_requests += 1
            if method == "droid.request_permission":
                self._respond(msg["id"], result={"selectedOption": "cancel"})
            else:
                self._respond(msg["id"], error={"code": -32601, "message": "not supported by bridge"})
            return
        if method == "droid.session_notification":
            params = msg.get("params")
            if isinstance(params, dict):
                self.inbox.put(("notif", params))

    def next_event(self, timeout: float) -> Any:
        """Следующее событие inbox или None; EOF липкий (виден всем потребителям)."""
        try:
            event = self.inbox.get(timeout=timeout)
        except queue.Empty:
            return None
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
            if event[0] == "eof":
                self.eof_rc = event[1]
                self.inbox.put(event)
                return dropped
            dropped += 1

    # -- запись ----------------------------------------------------------------
    def alive(self) -> bool:
        return not self.dead and not self.closed and self.proc.poll() is None

    def new_id(self) -> str:
        with self._write_lock:
            self._next_id += 1
            return f"r{self._next_id}"

    def _write(self, obj: dict) -> None:
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        with self._write_lock:
            try:
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
            except (OSError, ValueError) as exc:
                raise RpcError(f"droid stdin closed: {exc!r}")

    def _respond(self, rid: Any, result: Any = None, error: Any = None) -> None:
        msg = {"type": "response", "jsonrpc": "2.0", "factoryApiVersion": RPC_API_VERSION, "id": rid}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result if result is not None else {}
        try:
            self._write(msg)
        except RpcError as exc:
            _log(f"session_rpc respond_failed pid={self.pid} err={_err_summary(exc, 80)!r}")

    def notify(self, method: str, params: dict, rid: str | None = None) -> str:
        """Запрос без ожидания ответа (interrupt, close_session)."""
        rid = rid or self.new_id()
        self._write({"type": "request", "jsonrpc": "2.0", "factoryApiVersion": RPC_API_VERSION,
                     "id": rid, "method": method, "params": params})
        return rid

    def interrupt_quietly(self) -> None:
        try:
            self.notify("droid.interrupt_session", {})
        except RpcError as exc:
            _log(f"session_rpc interrupt_failed pid={self.pid} err={_err_summary(exc, 80)!r}")

    def call(self, method: str, params: dict, cancel: threading.Event | None = None,
             timeout: float | None = None, rid: str | None = None) -> tuple:
        """Запрос и ожидание ответа с тем же id -> (result, нотификации за это время)."""
        rid = self.notify(method, params, rid)
        end = time.monotonic() + (RPC_CALL_TIMEOUT_S if timeout is None else timeout)
        stash: list = []
        while True:
            if cancel is not None and cancel.is_set():
                raise _Cancelled()
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise RpcTimeout(f"{method}: no response within {RPC_CALL_TIMEOUT_S:g}s")
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
        if self.proc.poll() is not None:
            return
        try:
            os.killpg(self.pid, sig)
        except (ProcessLookupError, PermissionError):
            return

    def force_kill(self) -> None:
        """SIGKILL собственной группы (процесс — лидер, start_new_session)."""
        self._signal(signal.SIGKILL)

    def close(self, mode: str = "graceful", graceful_wait: float = 5.0,
              term_wait: float = TERM_WAIT_S, kill_wait: float = TERM_WAIT_S,
              keep_slot: bool = False) -> None:
        """Закрыть процесс: штатный close_session/EOF либо SIGTERM; затем SIGKILL.

        SID и файлы сессии остаются на диске. Слот P возвращается только после
        waitpid (keep_slot — передача слота следующему процессу при rebase).
        """
        with self._close_lock:
            if self.closed:
                return
            self.closed = True
        if mode == "graceful" and self.proc.poll() is None:
            try:
                self.notify("droid.close_session", {"reason": "bridge"})
            except RpcError as exc:
                _log(f"session_rpc close_session_failed pid={self.pid} err={_err_summary(exc, 80)!r}")
            self._close_stdin()
            self._wait(graceful_wait)
        if self.proc.poll() is None:
            self._signal(signal.SIGTERM)
            self._wait(term_wait)
        if self.proc.poll() is None:
            self._signal(signal.SIGKILL)
            self._wait(kill_wait)
        self._close_stdin()
        with _active_lock:
            _active.pop(self.pid, None)
            _rpc_procs.pop(self.pid, None)
        _children_update(remove_pid=self.pid)
        self._reader.join(timeout=1.0)
        self._err_reader.join(timeout=1.0)
        for stream in (self.proc.stdout, self.proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError as exc:
                _log(f"session_rpc stream_close_failed pid={self.pid} err={_err_summary(exc, 80)!r}")
        if self.holds_slot and not keep_slot:
            self.holds_slot = False
            self.pool.release()

    def _close_stdin(self) -> None:
        try:
            self.proc.stdin.close()
        except OSError as exc:
            _log(f"session_rpc stdin_close_failed pid={self.pid} err={_err_summary(exc, 80)!r}")


def _child_env() -> dict:
    """Окружение ребёнка: как _launch_env + чистый Factory home (AD-010).

    Ключ моста вырезан в _launch_env; FACTORY_API_KEY наследуется (в лог и state
    не попадает). Чистый home не даёт хукам/персональным skills владельца
    попасть в контекст чата; DROID_AUTO=off — вторичная защита (главная — RPC).
    """
    env = _launch_env()
    home = WORKSPACE / "runtime" / "factory-home"
    try:
        _mkdir_private(home)
        env["FACTORY_HOME_OVERRIDE"] = str(home)
    except OSError as exc:
        _log(f"session_rpc factory_home_unavailable err={_err_summary(exc, 80)!r}")
    env["DROID_AUTO"] = "off"
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
        self.proc: RpcProcess | None = None
        self.sid = ""
        self.generation = 0
        self.n = 0
        self.head = ""
        self.cfg = ""
        self.settings = ("", "", "")
        self.droid_real = -1
        self.restore_count = 0
        self.turns = 0
        self.last_used = 0.0
        self.rec_rev = 0
        self.state = "NEW"  # NEW | READY | PERSISTED | DIRTY


def _record_path(key_hash: str) -> Path:
    return _state_dir() / "conversations.v1" / "chats" / key_hash[:2] / f"{key_hash}.json"


def _read_record(path: Path) -> dict | None:
    """Запись чата или None, если файла нет/он повреждён (тогда — history-fallback)."""
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict) or rec.get("schema") != 1:
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
        "schema": 1, "key_hash": chat.key_hash, "sid": chat.sid, "generation": chat.generation,
        "state": state, "rec_rev": chat.rec_rev + 1, "n": chat.n, "head": chat.head,
        "cfg": chat.cfg, "model": chat.settings[0], "effort": chat.settings[1],
        "autonomy": chat.settings[2], "droid_real": chat.droid_real,
        "restore_count": chat.restore_count, "wall_time": int(time.time()),
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
                _log(f"session_rpc chat={chat.key_hash[:8]} evict pid={proc.pid} sid={chat.sid[:8] or '-'}")
                proc.close(mode="term")
            _persist_chat(chat)
        finally:
            chat.lock.release()


def _persist_chat(chat: Chat) -> None:
    """Записать состояние чата (best effort: ошибка записи -> DIRTY, не отказ запроса)."""
    if not chat.sid:
        return
    try:
        _write_record(chat, "READY" if chat.state in ("READY", "PERSISTED") else chat.state)
    except (OSError, StateConflict) as exc:
        chat.state = "DIRTY"
        _log(f"session_rpc chat={chat.key_hash[:8]} persist_failed err={_err_summary(exc, 120)!r}")


class ChatRegistry:
    """Реестр чатов: индекс O(1) по sha256(namespace+ключ), реапер idle, вытеснение LRU."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.chats: dict = {}
        self._reaper: threading.Thread | None = None

    def get(self, key_hash: str) -> Chat:
        with self.lock:
            chat = self.chats.get(key_hash)
            if chat is None:
                chat = Chat(key_hash)
                _load_record(chat)
                self.chats[key_hash] = chat
            return chat

    def add_waiter(self, chat: Chat) -> None:
        with self.lock:
            chat.waiters += 1

    def drop_waiter(self, chat: Chat) -> None:
        with self.lock:
            chat.waiters -= 1

    def _eligible(self, chat: Chat) -> bool:
        return (chat.proc is not None and chat.waiters == 0 and not chat.lock.locked()
                and chat.proc.alive())

    def take_victim(self) -> "_Victim | None":
        """LRU среди idle не-pending чатов; аренда берётся try-acquire без ожидания."""
        with self.lock:
            candidates = sorted((c for c in self.chats.values() if self._eligible(c)),
                                key=lambda c: c.last_used)
        for chat in candidates:
            if chat.lock.acquire(blocking=False):
                if chat.proc is not None and chat.waiters == 0:
                    return _Victim(chat)
                chat.lock.release()
        return None

    def reap_once(self, now: float | None = None) -> list:
        """Закрыть процессы idle >= IDLE_SECONDS (busy/pending не трогаем) -> hash8 закрытых."""
        now = _clock() if now is None else now
        with self.lock:
            candidates = [c for c in self.chats.values()
                          if self._eligible(c) and now - c.last_used >= IDLE_SECONDS]
        with self.lock:
            dead = [c for c in self.chats.values()
                    if c.proc is not None and not c.proc.alive() and c.waiters == 0
                    and not c.lock.locked()]
        for chat in dead:
            # Процесс умер в простое: слот P возвращаем, чат восстановим через load.
            if chat.lock.acquire(blocking=False):
                try:
                    proc, chat.proc = chat.proc, None
                    if proc is not None:
                        proc.close(mode="term", term_wait=0.5, kill_wait=0.5)
                    if chat.state == "READY":
                        chat.state = "PERSISTED"
                finally:
                    chat.lock.release()
        reaped = []
        for chat in candidates:
            if not chat.lock.acquire(blocking=False):
                continue
            try:
                if chat.proc is None or chat.waiters != 0:
                    continue
                proc, chat.proc = chat.proc, None
                if chat.state == "READY":
                    chat.state = "PERSISTED"
                _log(f"session_rpc chat={chat.key_hash[:8]} idle_close pid={proc.pid} "
                     f"sid={chat.sid[:8] or '-'}")
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
    REGISTRY = ChatRegistry()
    POOL = ProcPool()
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


def _is_service_message(message: Any) -> bool:
    """Служебные вставки droid (system-reminder, каталог tools) в проверку истории не входят."""
    text = _message_text(message).lstrip()
    return text.startswith("<system-reminder>") or text.startswith("Unified tool catalog")


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
        "input_tokens": num("inputTokens"), "output_tokens": num("outputTokens"),
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
            items.append({"role": "assistant", "text": rendered[len("[assistant]\n"):],
                          "digest": _digest(rendered)})
        elif role == "user":
            items.append({"role": "user", "text": rendered[len("[user]\n"):],
                          "digest": _digest(rendered)})
        else:  # tool и редкие mid-conversation system: как user с меткой роли
            items.append({"role": "user", "text": rendered, "digest": _digest(rendered)})
    if tools and not _tool_choice_none(tool_choice):
        section = _tools_section(tools, tool_choice, bool(images))
        system_parts.append(section[len("[system]\n"):] if section.startswith("[system]\n") else section)
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
    return _digest(json.dumps({"system": system or "", "cwd": work_dir}, sort_keys=True))


def _projection_digest(text: str, tool_calls: list) -> str:
    """Проекция выданного мостом assistant-сообщения, как её пришлёт клиент назад."""
    msg = {"role": "assistant", "content": text, "tool_calls": [
        {"id": tc["id"], "type": "function", "function": tc["function"]} for tc in tool_calls]}
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
        return isinstance(json.loads(text[len(TITLE_USER_PREFIX):].strip()), list)
    except ValueError:
        return False


def _instr_scan(messages: list) -> tuple:
    """Блок agent-instructions во входящих messages: (секций, omitted, байт)."""
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        text = _flatten_content(msg.get("content"))
        if "Instructions from:" not in text[:4096] and "Workspace instruction budget" not in text[:4096]:
            continue
        sections = len(re.findall(r"^Instructions from: ", text, re.M))
        omitted = "-"
        found = re.search(r"Workspace instruction budget \d+ bytes: omitted ([^;\n]+)", text)
        if found:
            omitted = found.group(1).strip()
        return sections, omitted, len(text.encode("utf-8"))
    return 0, "-", 0


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
                if proc.dead:
                    raise _NeedRebase()
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
        self._send_items(proc, items)
        self._consume(proc)

    def _check_settings(self, settings: Any) -> None:
        """Read-back фактических model/effort/autonomy: молча не подменяем (F-214)."""
        model, effort, autonomy = self.plan["settings"]
        if not isinstance(settings, dict):
            raise RpcError("settings read-back missing")
        got = (settings.get("modelId"), settings.get("reasoningEffort"))
        if got != (model, effort):
            raise ModelMismatch(f"droid substituted model/effort: wanted {model}/{effort}, got {got[0]}/{got[1]}")
        level = settings.get("autonomyLevel")
        if level is not None and level != autonomy:
            raise ModelMismatch(f"droid autonomy mismatch: wanted {autonomy}, got {level}")

    def _initialize(self, proc: RpcProcess) -> None:
        plan = self.plan
        model, effort, autonomy = plan["settings"]
        params = {
            "machineId": "droid-bridge", "cwd": plan["work_dir"], "modelId": model,
            "reasoningEffort": effort, "autonomyLevel": autonomy, "interactionMode": "auto",
            "title": plan["title"], "disableBuiltinSkills": True,
            "autoRejectPermissionRequests": True, "tags": ["droid-dsh-bridge"],
        }
        if plan["system"]:
            params["systemPrompt"] = plan["system"]
        result, _ = proc.call("droid.initialize_session", params, self.cancel)
        sid = result.get("sessionId")
        if not isinstance(sid, str) or not sid:
            raise RpcError("initialize_session: no sessionId in result")
        self._check_settings(result.get("settings"))
        session = result.get("session") if isinstance(result.get("session"), dict) else {}
        msgs = session.get("messages") if isinstance(session.get("messages"), list) else []
        self.sid = sid
        self.droid_real = sum(1 for m in msgs if not _is_service_message(m))
        self._disable_native_tools(proc)

    def _disable_native_tools(self, proc: RpcProcess) -> None:
        """Нативные tools отключаются по АКТУАЛЬНОМУ list_tools (новые id тоже); сбой — fail-closed."""
        result, _ = proc.call("droid.list_tools", {}, self.cancel)
        tools = result.get("tools")
        if not isinstance(tools, list) or not all(isinstance(t, dict) for t in tools):
            raise RpcError("list_tools: invalid catalogue")
        ids = [str(t["id"]) for t in tools if isinstance(t.get("id"), str) and t.get("id")]
        keep = set(self.plan.get("keep_tools") or ())
        ids = [i for i in ids if i not in keep]
        if not ids:
            return
        _, stash = proc.call("droid.update_session_settings", {"disabledToolIds": ids}, self.cancel)
        updated = self._wait_settings_updated(proc, stash)
        disabled = updated.get("disabledToolIds") if isinstance(updated, dict) else None
        if isinstance(disabled, list) and not set(ids).issubset(set(map(str, disabled))):
            raise RpcError("native tools were not disabled (read-back mismatch)")

    def _wait_settings_updated(self, proc: RpcProcess, stash: list, timeout: float = 2.0) -> Any:
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
        params = {"modelId": model, "reasoningEffort": effort, "autonomyLevel": autonomy}
        _, stash = proc.call("droid.update_session_settings", params, self.cancel)
        settings = self._wait_settings_updated(proc, stash, timeout=5.0)
        if settings is None or "modelId" not in settings:
            raise _NeedRebase()  # read-back не подтвердился: безопасно — свежая generation
        self._check_settings(settings)

    def _load(self, proc: RpcProcess) -> bool:
        """load_session того же SID + проверка целостности; False -> свежая generation."""
        plan = self.plan
        try:
            result, _ = proc.call("droid.load_session",
                                  {"sessionId": plan["sid"], "disableBuiltinSkills": True}, self.cancel)
        except RpcEof:
            raise
        except RpcError as exc:
            _log(f"session_rpc chat={plan['hash8']} restore_failed err={_err_summary(exc, 120)!r} fallback=history")
            return False
        session = result.get("session") if isinstance(result.get("session"), dict) else {}
        msgs = session.get("messages") if isinstance(session.get("messages"), list) else None
        if msgs is None or result.get("isAgentLoopInProgress"):
            _log(f"session_rpc chat={plan['hash8']} restore_failed reason=state fallback=history")
            return False
        if _service_duplicates(msgs):
            _log(f"restore_integrity chat={plan['hash8']} verdict=DUPLICATE_SCAFFOLDING action=sanitize")
            return False
        real = sum(1 for m in msgs if not _is_service_message(m))
        if plan["droid_real"] >= 0 and real != plan["droid_real"]:
            _log(f"restore_integrity chat={plan['hash8']} verdict=HISTORY_MISMATCH "
                 f"droid={real} bridge={plan['droid_real']} action=sanitize")
            return False
        self.sid = plan["sid"]
        self.droid_real = real
        settings = result.get("settings")
        self.plan["current_settings"] = (
            settings.get("modelId"), settings.get("reasoningEffort"),
            settings.get("autonomyLevel", plan["settings"][2])) if isinstance(settings, dict) else ("", "", "")
        self._disable_native_tools(proc)
        try:
            self._sync_settings(proc, plan["settings"])
        except _NeedRebase:
            return False
        return True

    def _send_items(self, proc: RpcProcess, items: list) -> None:
        """Все входы кроме последнего — skipAgentLoop, последний запускает ровно один цикл."""
        last = len(items) - 1
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
                _, stash = proc.call("droid.add_user_message", params, self.cancel, rid=self.turn_req_id)
                self._absorb(stash)

    def _absorb(self, stash: list) -> None:
        for params in stash:
            self._on_notif(params)

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
                    raise RpcError("add_user_message: " + str((msg["error"] or {}).get("message"))[:300])
                self._quarantined += 1  # дубль ACK/ответ прежнего запроса: ход не завершает
            elif kind == "eof":
                raise RpcEof(int(event[1] or 1))
            else:
                raise RpcError(f"{kind}: {str(event[1])[:200]}")

    # -- нотификации -------------------------------------------------------------
    def _slot_for(self, mid: str) -> dict:
        if mid not in self._msgs:
            self._msgs[mid] = {"text": "", "thinking": ""}
            self._order.append(mid)
        return self._msgs[mid]

    def _progress(self) -> None:
        self.last_progress = time.monotonic()
        self.got_event = True

    def _on_notif(self, params: Any) -> bool:
        """True — получен terminal ТЕКУЩЕГО хода (события опубликованы)."""
        if not isinstance(params, dict) or params.get("sessionId") != self.sid:
            self._quarantined += 1  # чужая/устаревшая сессия в карантин
            return False
        note = params.get("notification")
        if not isinstance(note, dict):
            return False
        ntype = note.get("type")
        mid = str(note.get("messageId") or "")
        if ntype == "create_message":
            message = note.get("message") if isinstance(note.get("message"), dict) else {}
            role = message.get("role")
            if not _is_service_message(message):
                self.droid_real += 1
            if role == "user" and note.get("requestId") == self.turn_req_id and self.turn_req_id:
                self.armed = True
                self._progress()
            elif role == "assistant" and self.armed:
                mid = mid or str(message.get("id") or "")
                slot = self._slot_for(mid) if mid else None
                if slot is not None and not slot["text"]:
                    slot["text"] = _message_text(message)
                self._progress()
            return False
        if not self.armed:
            return False  # запоздавшее событие прежнего хода
        self._progress()
        if ntype == "assistant_text_delta" and mid:
            self._slot_for(mid)["text"] += str(note.get("textDelta") or "")
        elif ntype == "assistant_text_complete" and mid:
            if isinstance(note.get("text"), str):
                self._slot_for(mid)["text"] = note["text"]
            else:
                self._slot_for(mid)
        elif ntype == "thinking_text_delta" and mid:
            self._slot_for(mid)["thinking"] += str(note.get("textDelta") or "")
        elif ntype == "thinking_text_complete" and mid:
            if isinstance(note.get("text"), str):
                self._slot_for(mid)["thinking"] = note["text"]
        elif ntype == "assistant_message_retracted" and mid:
            self._msgs.pop(mid, None)
            if mid in self._order:
                self._order.remove(mid)
        elif ntype == "error":
            self._last_error = str(note.get("message") or note.get("errorType") or "droid error")[:300]
        elif ntype == "agent_turn_completed":
            return self._terminal(note)
        return False

    def _terminal(self, note: dict) -> bool:
        reason = str(note.get("reason") or "")
        if self.cancel.is_set() or reason not in ("completed", "permission_rejected"):
            if not self.cancel.is_set():
                self.q.put(("stream_error", self._last_error or f"turn ended: {reason or 'unknown'}"))
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
        self.q.put(("result", {"finalText": final_text, "session_id": self.sid,
                               "duration_ms": note.get("durationMs"), "num_turns": None,
                               "usage": _map_usage(note.get("tokenUsage"))}))
        self.q.put(("done", (0, final_text)))
        return True

    # -- завершение ----------------------------------------------------------------
    def close(self) -> None:
        """Отмена хода: interrupt, ожидание terminal в пределах грейса; процесс не закрывается."""
        self.cancel.set()
        self.thread.join(timeout=INTERRUPT_GRACE_S + 1.0)


def _close_async(proc: RpcProcess, mode: str) -> None:
    """Закрытие в фоне: финальные кадры клиенту не ждут waitpid (слот P держится до него)."""
    threading.Thread(target=proc.close, kwargs={"mode": mode}, daemon=True).start()


def _make_plan(ctx: dict, chat: Chat | None, cfg: str, work_dir: str, keep_tools: list) -> dict:
    """Путь хода под арендой чата: hot | restore | rebase | cold | ephemeral.

    Префикс совпал (цепочка, cfg, SID) -> в RPC уходит только непросмотренный
    суффикс; любое расхождение/форк/правка/компакция/смена system|tools|cwd или
    нездоровое состояние -> свежая generation с replay всей истории запроса.
    Fuzzy-сопоставления нет.
    """
    rpc = ctx["rpc"]
    items = rpc["items"]
    plan = {
        "path": "ephemeral", "send": items, "all_items": items, "system": rpc["system"],
        "work_dir": work_dir, "settings": (ctx["model"], ctx["effort"], ctx["autonomy"]),
        "current_settings": ("", "", ""), "title": "bridge-title" if ctx["route"] == "title"
        else "droid-dsh-bridge", "sid": "", "droid_real": -1,
        "hash8": chat.key_hash[:8] if chat is not None else "-", "keep_tools": keep_tools,
        "need_slot": True, "handoff": None, "dead_proc": None,
    }
    if chat is None:
        return plan
    proc = chat.proc
    if proc is not None and not proc.alive():
        plan["dead_proc"] = proc
        proc = None
    count = chat.n
    prefix_ok = (chat.state in ("READY", "PERSISTED") and bool(chat.sid) and chat.cfg == cfg
                 and 0 < count < len(items) and _chain_head(items, count) == chat.head)
    if prefix_ok and proc is not None:
        plan.update(path="hot", send=items[count:], need_slot=False, sid=chat.sid,
                    droid_real=chat.droid_real, current_settings=chat.settings)
    elif prefix_ok and chat.restore_count < RESTORE_MAX:
        plan.update(path="restore", send=items[count:], sid=chat.sid, droid_real=chat.droid_real)
    else:
        plan["path"] = "rebase" if proc is not None else "cold"
        plan["handoff"] = proc
        plan["need_slot"] = proc is None
    return plan


def _finish_attempt(chat: Chat | None, plan: dict, run: Run, out: dict, ok: bool,
                    cfg: str, items: list) -> int:
    """Итог попытки: commit префикса и метаданных либо инвалидация чата. -> число ходов чата."""
    proc = run.proc
    if not ok:
        # Недоставленный/неполный ход: user мог попасть в контекст droid -> только
        # свежая generation; процесс закрывается (слот возвращается после waitpid).
        if chat is not None:
            chat.proc = None
            chat.state = "DIRTY"
            _persist_chat(chat)
        if proc is not None:
            _close_async(proc, "term")
        return 0
    if chat is None:
        if proc is not None:
            _close_async(proc, "graceful")
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
    _persist_chat(chat)
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


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 300

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

    def _log_reject(self, reason: str, model: str = "unknown", model_len: int = 0) -> None:
        """Строка отказа в журнал (строгий формат RW-013)."""
        _log(f"reject reason={reason} model={model or 'unknown'} "
             f"model_len={int(model_len)} client={self._client_tag()}")

    def _reject(self, code: int, reason: str, message: str,
                model: str = "unknown", model_len: int = 0) -> None:
        """Отказ (до SSE): строка `reject …` в журнал и общий формат ошибки."""
        self._log_reject(reason, model, model_len)
        self.close_connection = True
        self._send(code, {"error": {"message": message, "type": reason, "code": int(code)}})

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

    def _execute(self, run: Run, on_text, on_reasoning, on_tool_call,
                 keepalive, emulate_tools: bool) -> dict:
        """Гнать ход до конца; сквозной таймаут TIMEOUT_S на весь ход.

        on_text/on_reasoning/on_tool_call/keepalive возвращают False, если клиент ушёл.
        Размышления идут мимо ToolCallParser — сразу в on_reasoning.
        При emulate_tools текстовый поток проходит через ToolCallParser: блоки
        <tool_call> выделяются как вызовы, остальное — как content.
        Превышение deadline -> kill группы (в run.close()), state=timeout.
        """
        pieces = []
        tool_calls: list = []
        usage = {}
        result_ev = {}
        last_ka = time.monotonic()
        deadline = time.monotonic() + TIMEOUT_S
        gone = [False]

        def state(name: str, rc: int, err: str = "") -> dict:
            return {"rc": rc, "text": "".join(pieces), "usage": usage,
                    "result": result_ev, "state": name, "err": err,
                    "session_id": result_ev.get("session_id") or "",
                    "duration_ms": result_ev.get("duration_ms"),
                    "num_turns": result_ev.get("num_turns"),
                    "tool_calls": tool_calls}

        def add_content(text: str) -> None:
            if gone[0] or not text:
                return
            pieces.append(text)
            if not on_text(text):
                gone[0] = True

        def add_call(call: dict) -> None:
            if gone[0]:
                return
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
            if not on_tool_call(entry):
                gone[0] = True

        parser = ToolCallParser(add_content, add_call) if emulate_tools else None

        while True:
            if time.monotonic() > deadline:
                return state("timeout", 124, f"proxy timeout after {TIMEOUT_S}s")
            if not run.got_event and time.monotonic() - run.started > FIRST_TOKEN_TIMEOUT_S:
                return state("first_token_timeout", 124,
                             f"no droid event within {FIRST_TOKEN_TIMEOUT_S:g}s")
            if (run.got_event and run.last_progress
                    and time.monotonic() - run.last_progress > SILENCE_WATCHDOG_S):
                # Тишина: сбрасывают только события ТЕКУЩЕГО хода (не keepalive/чужие).
                return state("timeout", 124, f"no droid progress within {SILENCE_WATCHDOG_S:g}s")
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
                if gone[0]:
                    return state("client_gone", 1)
            elif kind == "reasoning":
                if not on_reasoning(str(payload)):
                    gone[0] = True
                    return state("client_gone", 1)
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
                if gone[0]:
                    return state("client_gone", 1)
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
        return {"state": reason, "rc": 1, "text": "", "usage": {}, "result": {},
                "err": "", "tool_calls": []}

    def _run_once(self, ctx: dict, on_text, on_reasoning, on_tool_call, keepalive) -> dict:
        """Ход запроса: порядок ресурсов L -> P -> T, до 3 попыток при транзиентном сбое."""
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
        committed_turns = 0
        try:
            try:
                _launcher()
            except LauncherUnavailable:
                # Гонка с удалением лончера: ответ отдаёт вызывающая ветка.
                self._log_reject("launcher_unavailable", model, ctx["model_len"])
                return {"state": "launcher_unavailable", "rc": 1, "text": "",
                        "usage": {}, "result": {}, "err": "", "tool_calls": []}
            if ctx["route"] == "keyed":
                chat = REGISTRY.get(ctx["key_hash"])
                reason = self._acquire_chat(chat, keepalive, poll_state)
                if reason:
                    return self._no_slot(ctx, reason)
                chat_held = True
            images = ctx.get("images") or []
            if images:
                img_dir = WORKSPACE / ("img-" + uuid.uuid4().hex)
                img_dir.mkdir(parents=True, exist_ok=True)
                try:
                    os.chmod(img_dir, 0o700)
                except OSError:
                    pass
                total_bytes = 0
                for image in images:
                    target = img_dir / image["name"]
                    target.write_bytes(image["data"])
                    try:
                        os.chmod(target, 0o600)
                    except OSError:
                        pass
                    total_bytes += len(image["data"])
                img_stats = (len(images), total_bytes,
                             ",".join(image["mime"] for image in images))
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
                if plan["need_slot"] and not holds_slot:
                    waited = time.monotonic()
                    reason = POOL.acquire(lambda: self._poll_wait(waited, keepalive, poll_state))
                    if reason:
                        return self._no_slot(ctx, reason)
                    holds_slot = True
                reason = self._acquire_slot(keepalive)
                if reason:
                    if holds_slot:
                        POOL.release()
                    return self._no_slot(ctx, reason)
                image_part = ""
                if img_stats:
                    image_part = " images=%d image_bytes=%d image_types=%s" % (
                        img_stats[0], img_stats[1], img_stats[2])
                _log(f"exec model={model} effort={effort} effort_source={ctx['effort_source']} "
                     f"autonomy={autonomy} autonomy_source={ctx['autonomy_source']} "
                     f"prompt_bytes={len(ctx['prompt'].encode())}{image_part} {tag}")
                if plan["path"] in ("cold", "rebase", "ephemeral") and ctx.get("instr", (0, "-", 0))[2]:
                    sections, omitted, nbytes = ctx["instr"]
                    _log(f"instr_guard sections={sections} omitted={omitted} bytes={nbytes}")
                if chat is not None and chat.sid:
                    # Отпечаток ожидающего хода ДО add: после падения моста — только replay.
                    try:
                        _write_record(chat, "PENDING")
                    except (OSError, StateConflict) as exc:
                        chat.state = "DIRTY"
                        _log(f"session_rpc chat={chat.key_hash[:8]} persist_failed "
                             f"err={_err_summary(exc, 120)!r}")
                _log(f"session_rpc chat={plan['hash8']} key={1 if chat is not None else 0} "
                     f"path={plan['path']} gen={(chat.generation if chat else 0)} "
                     f"sid={plan['sid'][:8] or '-'}")
                run = Run(plan, chat.proc if plan["path"] == "hot" else None, holds_slot)
                try:
                    out = self._execute(run, on_text, on_reasoning, on_tool_call,
                                        keepalive, ctx["emulate_tools"])
                finally:
                    try:
                        run.close()
                    finally:
                        _slots.release()
                ok = bool(run.ok and out.get("state") == "done" and out.get("rc") == 0)
                committed_turns = _finish_attempt(chat, plan, run, out, ok, cfg, rpc["items"])
                if ok:
                    break
                delivered = bool(out.get("text") or out.get("tool_calls"))
                # Контент до terminal не отдаётся, поэтому delivered здесь — страховка.
                if out["state"] != "done" or delivered or attempt == 3:
                    break
                # Транзиентный сбой (rc!=0, клиенту ничего не выдано): повтор невидим;
                # он строится заново из истории запроса, а не повтором user в старую сессию.
                _log(f"transient failure rc={out['rc']} err={_err_summary(out.get('err'), 120)!r}, "
                     f"retry {attempt} {tag}")
                # Сбой egress не должен сохранять SKIP-префлайт: повтор идёт с полным префлайтом.
                _last_ok[0] = 0.0
                _sleep(2 * attempt)
            ok_done = bool(run is not None and run.ok and out.get("state") == "done"
                           and out.get("rc") == 0)
            hot = bool(ok_done and run.path in ("hot", "restore"))
            usage = out.get("usage") or {}
            rep_turns = committed_turns if ok_done else 0
            sess8 = ((run.sid if ok_done else plan["sid"]) or "")[:8] or "-"
            raw_in = usage.get("input_tokens", 0)
            raw_out = usage.get("output_tokens", 0)
            _log(f"usage sess={sess8} raw={raw_in}/{raw_out} "
                 f"rep={raw_in}/{raw_out} resumed={1 if hot else 0} turns={rep_turns}")
        finally:
            if img_dir is not None:
                shutil.rmtree(str(img_dir), ignore_errors=True)
            if chat_held:
                chat.lock.release()
        if out.get("state") != "client_gone":
            _last_ok[0] = time.monotonic() if (out.get("state") == "done" and out.get("rc") == 0) else 0.0
        _log(f"done model={model} rc={out['rc']} state={out['state']} "
             f"sess={sess8} resumed={1 if hot else 0} turns={rep_turns} "
             f"out_bytes={len(out['text'].encode())} wall_s={time.monotonic() - t0:.1f} "
             f"err={_err_summary(out.get('err'))!r} {tag}")
        return out

    @staticmethod
    def _error_body(out: dict) -> Any:
        st = out.get("state")
        if st == "timeout":
            return {"message": f"droid exec timed out after {TIMEOUT_S}s",
                    "type": "timeout", "code": 504}
        if st == "first_token_timeout":
            return {"message": f"first_token_timeout: droid exec gave no event within "
                               f"{FIRST_TOKEN_TIMEOUT_S:g}s",
                    "type": "first_token_timeout", "code": 504}
        if st == "queue_timeout":
            return {"message": f"bridge busy: queue full over {QUEUE_TIMEOUT_S}s",
                    "type": "overloaded", "code": 503}
        if st == "launcher_unavailable":
            return {"message": "canonical launcher is missing or not executable",
                    "type": "launcher_unavailable", "code": 503}
        if st == "client_gone":
            return {"message": "client gone", "type": "client_gone", "code": 499}
        if st == "pump_error":
            return {"message": "bridge reader failed", "detail": str(out.get("err"))[:500],
                    "type": "proxy_error", "code": 502}
        if st == "droid_error":
            return {"message": str(out.get("err") or "droid exec reported an error")[:500],
                    "type": "droid_error", "code": 502}
        if out.get("rc") != 0 or not (out.get("text") or out.get("tool_calls")):
            return {"message": f"droid exec exited rc={out.get('rc')}",
                    "detail": str(out.get("err"))[:500], "type": "proxy_error", "code": 502}
        return None

    # ---- HTTP --------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/v1/health"):
            with _active_lock:
                active = len(_active)
            self._send(200, {
                "ok": True, "transport": "droid-exec", "model": MODEL_ID,
                "active": active, "max_concurrent": MAX_CONCURRENT,
                "tool_emulation": True,
                "uptime_s": int(time.time() - _started),
            })
            return
        if not _auth_ok(self):
            self._send(401, {"error": {"message": "unauthorized", "type": "auth_error", "code": 401}})
            return
        if path in ("/v1/models", "/models"):
            data = []
            order = [MODEL_ID] + [mid for mid in FLEET["order"] if mid != MODEL_ID]
            for mid in order:
                model = FLEET["models"][mid]
                data.append({
                    "id": mid, "object": "model", "owned_by": "factory-droid",
                    "created": 0, "context_length": model["context_window"],
                })
            self._send(200, {"object": "list", "data": data})
            return
        self._send(404, {"error": {"message": f"not found: {path}", "type": "not_found", "code": 404}})

    def do_POST(self) -> None:  # noqa: N802
        if _shutting_down:
            self._reject(503, "overloaded", "bridge is shutting down")
            return
        if not _auth_ok(self):
            # Непрочитанное тело иначе будет разобрано как следующий запрос keep-alive.
            self.close_connection = True
            self._send(401, {"error": {"message": "unauthorized", "type": "auth_error", "code": 401}})
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
            self._reject(413, "payload_too_large", "request body exceeds the bridge limit")
            return
        # (3) admission: резерв байт по заявленному Content-Length до чтения тела.
        reserved = 0
        budget = _budget
        if budget is not None and length:
            if not budget.reserve(length):
                self._reject(503, "overloaded", "bridge overloaded: body budget exhausted")
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
                self._send(404, {"error": {"message": f"not found: {path}",
                                           "type": "not_found", "code": 404}})
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
                self._reject(400, "model_not_allowed", "model must be a string from the catalogue",
                             "unknown", model_len)
                return
            if model_id not in FLEET["models"]:
                self._reject(400, "model_not_allowed", "model is not in the catalogue",
                             "unknown", model_len)
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
                    self._reject(400, "unsupported_reasoning_effort",
                                 "reasoning_effort is not allowed for this model",
                                 model_id, model_len)
                    return
            else:
                self._reject(400, "unsupported_reasoning_effort",
                             "reasoning_effort must be a string", model_id, model_len)
                return
            # (9a) autonomy: low|medium|high -> `--auto`; "off" -> без флага
            # (read-only droid, Reviewer-пути); дефолт high (максимум).
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
                    self._reject(400, "unsupported_autonomy",
                                 "autonomy is not allowed (low|medium|high|off)",
                                 model_id, model_len)
                    return
            else:
                self._reject(400, "unsupported_autonomy",
                             "autonomy must be a string", model_id, model_len)
                return
            # (10) reasoning-объект не поддерживаем.
            if "reasoning" in req and req.get("reasoning") is not None:
                self._reject(400, "unsupported_parameter",
                             "reasoning parameter is not supported", model_id, model_len)
                return
            # (11) изображения (C-08…C-11).
            try:
                images = _collect_images(req, model, effort)
            except ImageReject as exc:
                self._reject(400, exc.reason, f"image rejected: {exc.reason}",
                             model_id, model_len)
                return
            # (12) лончер: проверка до SSE и до любого запуска.
            try:
                _launcher()
            except LauncherUnavailable:
                self._reject(503, "launcher_unavailable",
                             "canonical launcher is missing or not executable",
                             model_id, model_len)
                return
            messages = req.get("messages") if isinstance(req.get("messages"), list) else []
            raw_tools = req.get("tools")
            tools = [t for t in raw_tools if isinstance(t, dict)] if isinstance(raw_tools, list) else []
            tool_choice = req.get("tool_choice")
            emulate_tools = bool(tools) and not _tool_choice_none(tool_choice)
            prompt = _messages_to_prompt(messages, tools, tool_choice, images)
            extra = req.get("extra_body") if isinstance(req.get("extra_body"), dict) else {}
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
                transcript = {"system": None, "runnable": True, "items": [
                    {"role": "user", "text": prompt, "digest": _digest(prompt)}]}
            elif keyed:
                route = "keyed"
            else:
                route = "nokey"
            ctx = {
                "route": route,
                "key_hash": _key_hash(raw_key) if (route == "keyed") else "",
                "rpc": transcript,
                "instr": _instr_scan(messages) if route in ("keyed", "nokey") else (0, "-", 0),
                "model": model_id,
                "model_len": model_len,
                "effort": effort,
                "effort_source": effort_source,
                "autonomy": autonomy,
                "autonomy_source": autonomy_source,
                "prompt": prompt,
                "images": images,
                "cwd": cwd,
                "emulate_tools": emulate_tools,
                "tag": (f"client={self._client_tag()} "
                        f"ua={(self.headers.get('User-Agent') or '-')[:60]}"),
                "stream": bool(req.get("stream")),
            }
            if ctx["stream"]:
                self._serve_sse(ctx)
            else:
                self._serve_json(ctx)
        finally:
            if reserved and budget is not None:
                budget.release(reserved)

    def _serve_json(self, ctx: dict) -> None:
        out = self._run_once(ctx, lambda _v: True, lambda _v: True, lambda _e: True, None)
        if out.get("state") == "client_gone":
            return
        err = self._error_body(out)
        if err is not None:
            self._send(err["code"], {"error": err})
            return
        usage = out.get("usage") or {}
        message = {"role": "assistant", "content": out["text"]}
        finish = "stop"
        if out.get("tool_calls"):
            message["tool_calls"] = out["tool_calls"]
            finish = "tool_calls"
        self._send(200, {
            "id": f"chatcmpl-droid-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
            "created": int(time.time()), "model": ctx["model"],
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
        })

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
            return "data: " + json.dumps({
                "id": completion_id, "object": "chat.completion.chunk", "created": created,
                "model": shown_model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }, ensure_ascii=False) + "\n\n"

        def on_text(value: str) -> bool:
            return self._emit(chunk({"content": value}))

        def on_reasoning(value: str) -> bool:
            return self._emit(chunk({"reasoning_content": value}))

        def on_tool_call(entry: dict) -> bool:
            return self._emit(chunk({"tool_calls": [entry]}))

        def keepalive() -> bool:
            return self._emit(": keepalive\n\n")

        if not self._emit(chunk({"role": "assistant", "content": ""})):
            return
        out = self._run_once(ctx, on_text, on_reasoning, on_tool_call, keepalive)
        if out.get("state") == "client_gone":
            _log("client gone mid-stream, child killed")
            return
        err = self._error_body(out)
        if err is None:
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
                self._emit("data: " + json.dumps({
                    "id": completion_id, "object": "chat.completion.chunk",
                    "created": created, "model": shown_model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                    "usage": {
                        "prompt_tokens": prompt_toks,
                        "completion_tokens": compl_toks,
                        "total_tokens": prompt_toks + compl_toks,
                    },
                }, ensure_ascii=False) + "\n\n")
        else:
            self._emit("data: " + json.dumps({"error": err}, ensure_ascii=False) + "\n\n")
        self._emit("data: [DONE]\n\n")


class Server(ThreadingHTTPServer):
    """HTTP-сервер с семафором числа соединений на уровне приёма (C-11)."""

    daemon_threads = True
    request_queue_size = 64
    allow_reuse_address = True

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._conn_sem = threading.BoundedSemaphore(
            int(FLEET["admission"]["max_http_connections"]))

    def _send_raw_503(self, request: socket.socket) -> None:
        body = json.dumps({
            "error": {"message": "bridge overloaded: connection limit",
                      "type": "overloaded", "code": 503},
        }).encode("utf-8")
        head = (
            b"HTTP/1.1 503 Service Unavailable\r\n"
            b"Content-Type: application/json; charset=utf-8\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"Connection: close\r\n\r\n"
        )
        request.sendall(head + body)

    def process_request(self, request: socket.socket, client_address: Any) -> None:
        if not self._conn_sem.acquire(blocking=False):
            try:
                peer = f"{client_address[0]}:{client_address[1]}"
            except (TypeError, IndexError):
                peer = "unknown"
            _log(f"reject reason=overloaded model=unknown model_len=0 client={peer}")
            try:
                self._send_raw_503(request)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request: socket.socket, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._conn_sem.release()


def _sweep_workspace() -> None:
    """Удалить prompt-*.txt и img-* старше часа (наследие упавших ходов)."""
    cutoff = time.time() - 3600
    for path in WORKSPACE.glob("prompt-*.txt"):
        try:
            if path.stat().st_mtime < cutoff:
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
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    _sweep_workspace()
    reconcile_children()
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
    _log(f"listen {HOST}:{PORT} model={MODEL_ID} max_concurrent={MAX_CONCURRENT} "
         f"queue_timeout={QUEUE_TIMEOUT_S}s timeout={TIMEOUT_S}s keepalive={KEEPALIVE_S}s")
    print(f"[droid-bridge] listening on http://{HOST}:{PORT}/v1", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
