#!/usr/bin/env python3
"""OpenAI-совместимый мост к Factory Droid CLI (`droid exec`) для DeepSeek Harness.

Один запрос /v1/chat/completions = один headless-ход
`droid exec -o stream-json -m <model> --cwd <workspace> --tag droid-dsh-bridge -f <prompt_file> -r <effort> [--auto <autonomy>]`
через канонический лончер ~/.config/factory-launch/droid-cli.sh (egress-пиннинг).
Автономность даунстрим-исполнителя задаётся top-level полем `autonomy`
(`low|medium|high`, дефолт `high` — максимум); `"off"` = флаг `--auto`
не передаётся (read-only режим droid, для Reviewer-путей); иное = 400
`unsupported_autonomy`. `--skip-permissions-unsafe` не используется никогда.
Поток stream-json переводится в OpenAI Chat Completions (stream и не-stream).
События `reasoning` транслируются в SSE-дельты `reasoning_content`.

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

# ---- HOT-SESSIONS: ленивые горячие сессии `droid exec -s` + честные дельты токенов.
# Ключ сессии: (model, realpath(work_dir), effort, autonomy); model/effort/autonomy
# уже нормализованы вызывающим кодом. work_dir разрешается так же, как в Run
# (cwd если isdir, иначе workspace); image-запуски живут в per-run каталоге и
# потому всегда холодные. Создание ленивое: сессия рождается на первом вызове,
# прогрева и фоновых процессов нет.
_SESSION_IDLE_TTL_S = 45 * 60
_SESSION_MAX_AGE_S = 24 * 3600
_SESSION_MAX_TURNS = 30
_sessions = {}  # key -> (session_id, last_used_mono, created_mono, turns)
_sessions_lock = threading.Lock()
_sessions_inflight = set()  # ключи с живым Run (два resume одного sid запрещены)
_sessions_usage = {}  # (key, sid) -> (input_tokens, output_tokens) прошлого вызова


def _hot_work_dir(cwd: str, img_dir: Any) -> str:
    """HOT-SESSIONS: каталог для ключа сессии (разрешение — как в Run.__init__)."""
    if img_dir is not None:
        return os.path.realpath(str(img_dir))
    work_dir = cwd if (cwd and os.path.isdir(cwd)) else str(WORKSPACE)
    return os.path.realpath(work_dir)


def _session_key(model: str, cwd: str, effort: str, autonomy: str, img_dir: Any) -> tuple:
    """HOT-SESSIONS: ключ сессии (model, realpath(work_dir), effort, autonomy)."""
    return (model, _hot_work_dir(cwd, img_dir), effort, autonomy)


def _usage_purge(key: tuple) -> None:
    """HOT-SESSIONS: стереть базы дельт ключа (при drop/evict сессии)."""
    for ukey in [u for u in _sessions_usage if u[0] == key]:
        _sessions_usage.pop(ukey, None)


def _session_drop(key: tuple) -> None:
    """HOT-SESSIONS: забыть сессию ключа и её базы дельт."""
    with _sessions_lock:
        _sessions.pop(key, None)
        _usage_purge(key)


def _session_claim(key: tuple) -> str:
    """HOT-SESSIONS: занять живую сессию ключа для одного Run (sid или "").

    Второй живой Run на тот же ключ запрещён (конкурентный resume портит
    .jsonl сессии и двоит биллинг): проигравший claim идёт холодным с новой
    сессией, без ожидания. Просрочка (idle 45 мин / age 24 ч / 30 ходов) ->
    drop + холодный старт.
    """
    with _sessions_lock:
        rec = _sessions.get(key)
        if rec is None or key in _sessions_inflight:
            return ""
        sid, last_used, created, turns = rec
        now = time.monotonic()
        if (now - last_used > _SESSION_IDLE_TTL_S
                or now - created > _SESSION_MAX_AGE_S
                or turns >= _SESSION_MAX_TURNS):
            _sessions.pop(key, None)
            _usage_purge(key)
            _log(f"hot session expired sess={str(sid)[:8]} turns={turns}")
            return ""
        _sessions_inflight.add(key)
        return sid


def _session_release(key: tuple) -> None:
    """HOT-SESSIONS: освободить claim ключа (в finally хода)."""
    with _sessions_lock:
        _sessions_inflight.discard(key)


def _session_turns(key: tuple, sid: str) -> int:
    """HOT-SESSIONS: ходы сессии (prev+1 при том же sid в store, иначе 1)."""
    with _sessions_lock:
        rec = _sessions.get(key)
        if rec is not None and rec[0] == sid:
            return int(rec[3]) + 1
    return 1


def _session_store(key: tuple, sid: str, turns: int) -> None:
    """HOT-SESSIONS: запомнить сессию после успешного хода."""
    if not sid:
        return
    now = time.monotonic()
    with _sessions_lock:
        prev = _sessions.get(key)
        created = prev[2] if (prev is not None and prev[0] == sid) else now
        _sessions[key] = (sid, now, created, int(turns))


def _usage_delta(key: tuple, sid: str, usage: dict, hot: bool) -> dict:
    """HOT-SESSIONS: честные токены вызова.

    droid отдаёт usage КУМУЛЯТИВНО по сессии, поэтому на продолженной сессии
    (-s реально использовался, run_sid!) клиенту отдаётся дельта против
    прошлого вызова, а не растущий итог. Холодный вызов, первый вызов сессии
    и сброс счётчика — как есть. База — по (key, sid): параллельный cold на
    том же ключе иначе затирает базу горячей сессии. Лишние ключи usage
    (cache_*, factory_credits, ...) сохраняются.
    """
    if not isinstance(usage, dict):
        return usage
    try:
        cur_in = int(usage.get("input_tokens", 0) or 0)
        cur_out = int(usage.get("output_tokens", 0) or 0)
    except (TypeError, ValueError):
        return usage
    ukey = (key, sid or "")
    with _sessions_lock:
        prev = _sessions_usage.get(ukey)
        _sessions_usage[ukey] = (cur_in, cur_out)
        if not hot or prev is None:
            return usage
        delta_in = cur_in - prev[0]
        delta_out = cur_out - prev[1]
        if delta_in < 0 or delta_out < 0:
            return usage
        rep = dict(usage)
        rep["input_tokens"] = delta_in
        rep["output_tokens"] = delta_out
        return rep


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


def _reasoning_suffix(seen: dict, rid: str, text: str) -> str:
    """Новый хвост reasoning-снимка сверх ранее виденного (по id).

    CLI шлёт накопительные снимки; если текст — продолжение прежнего,
    возвращаем только суффикс, иначе (пересборка) — текст целиком.
    Пустой результат означает «дубликат, не эмитить»."""
    prev = seen.get(rid, "")
    suffix = text[len(prev):] if text.startswith(prev) else text
    seen[rid] = text
    return suffix


def _clean_err(text: str) -> str:
    lines = [ln for ln in (text or "").splitlines() if ln.strip() and not _NOISE.search(ln)]
    return "\n".join(lines).strip()


def _kill_group(proc: subprocess.Popen) -> None:
    """SIGTERM процессной группе, затем SIGKILL, если не завершилась."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue


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


class Run:
    """Один процесс `droid exec`; поток-читатель превращает stdout в события очереди.

    Для запроса с изображениями cwd и prompt-файл живут в per-run каталоге
    `workspace/img-<uuid>` (0700, файлы 0600); для текстового — прежняя форма:
    cwd = workspace, -f workspace/prompt-<uuid>.txt. argv всегда содержит ровно
    один `-m` и один `-r`; `-r` передаётся всегда (запрос или default).
    `--auto <autonomy>` добавляется всегда, кроме `autonomy == "off"` (read-only).
    """

    def __init__(self, prompt: str, model: str, effort: str, effort_source: str,
                 autonomy: str, autonomy_source: str,
                 cwd: str, tag: str, img_dir: Path | None = None,
                 img_stats: tuple | None = None, sess_sid: str = ""):
        launcher = _launcher()
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        if img_dir is not None:
            work_dir = str(img_dir)
            self.prompt_path = Path(img_dir) / "prompt.txt"
        else:
            self.prompt_path = WORKSPACE / f"prompt-{uuid.uuid4().hex}.txt"
            work_dir = cwd if (cwd and os.path.isdir(cwd)) else str(WORKSPACE)
        self.prompt_path.write_text(prompt, encoding="utf-8")
        try:
            os.chmod(self.prompt_path, 0o600)
        except OSError:
            pass
        cmd = [
            launcher, "exec", "-o", "stream-json", "-m", model,
            "--cwd", work_dir, "--tag", "droid-dsh-bridge",
            "-f", str(self.prompt_path),
            "-r", effort,
        ]
        if autonomy != AUTONOMY_OFF:
            cmd += ["--auto", autonomy]
        # HOT-SESSIONS: живой sid ключа -> resume `-s`; run_sid — единственный
        # источник флага resumed для дельты и done-лога.
        self.run_sid = sess_sid or ""
        if self.run_sid:
            cmd += ["-s", self.run_sid]
        self.proc = subprocess.Popen(
            cmd, cwd=work_dir, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, env=_launch_env(),
        )
        self.started = time.monotonic()
        self.got_event = False  # True после первого валидного JSON-события stdout
        with _active_lock:
            _active[self.proc.pid] = self.proc
        self.q = queue.Queue()
        self.err_box = []
        # Последний виденный reasoning-текст по id события: CLI присылает
        # накопительный снимок, новым считается только хвост сверх него.
        self._reasoning_seen: dict[str, str] = {}
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        threading.Thread(target=self._pump, daemon=True).start()

    def _drain_stderr(self) -> None:
        try:
            self.err_box.append(_clean_err((self.proc.stderr.read() or b"").decode("utf-8", "replace")))
        except Exception:  # noqa: BLE001 - вторичный поток, ошибку терять нельзя молча
            pass

    def _pump(self) -> None:
        """Разбор stream-json: message -> текст, reasoning -> хвост размышлений,
        completion -> usage/finalText, error -> ошибка."""
        final_text = ""
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
                etype = ev.get("type")
                if etype == "message" and ev.get("role") == "assistant" and ev.get("text"):
                    self.q.put(("text", ev["text"]))
                elif etype == "reasoning" and ev.get("text"):
                    suffix = _reasoning_suffix(
                        self._reasoning_seen, str(ev.get("id") or ""), str(ev["text"]))
                    if suffix:
                        self.q.put(("reasoning", suffix))
                elif etype == "completion":
                    # HOT-SESSIONS: session_id забираем из top-level completion
                    # (НЕ из usage), вместе с уже имеющимися durationMs/numTurns.
                    final_text = ev.get("finalText") or ""
                    self.q.put(("result", {"finalText": final_text,
                                           "session_id": ev.get("session_id") or "",
                                           "duration_ms": ev.get("durationMs"),
                                           "num_turns": ev.get("numTurns"),
                                           "usage": ev.get("usage") or {}}))
                elif etype == "error":
                    self.q.put(("stream_error", str(ev.get("message") or ev.get("error") or ev)[:500]))
            rc = self.proc.wait()
        except Exception as exc:  # noqa: BLE001 - читатель не должен умирать молча
            self.q.put(("pump_error", repr(exc)))
            return
        time.sleep(0.05)  # дать стоку stderr дозавершиться
        self.q.put(("done", (rc, final_text)))

    def close(self) -> None:
        if self.proc.poll() is None:
            _kill_group(self.proc)
        with _active_lock:
            _active.pop(self.proc.pid, None)
        try:
            self.prompt_path.unlink(missing_ok=True)
        except OSError:
            pass
        for stream in (self.proc.stdout, self.proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass


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

    def _run_once(self, ctx: dict, on_text, on_reasoning, on_tool_call, keepalive) -> dict:
        model = ctx["model"]
        effort = ctx["effort"]
        autonomy = ctx["autonomy"]
        tag = ctx["tag"]
        reason = self._acquire_slot(keepalive)
        if reason:
            _log(f"no slot ({reason}) model={model} {tag}")
            if reason == "queue_timeout":
                # HTTP-ответ отдаст вызывающая ветка (_serve_json/_serve_sse):
                # в SSE заголовки уже отправлены, второй ответ недопустим.
                self._log_reject("overloaded", model, ctx["model_len"])
            return {"state": reason, "rc": 1, "text": "", "usage": {}, "result": {},
                    "err": "", "tool_calls": []}
        t0 = time.monotonic()
        out = {}
        img_dir = None
        try:
            try:
                _launcher()
            except LauncherUnavailable:
                # Гонка с удалением лончера: ответ отдаёт вызывающая ветка.
                self._log_reject("launcher_unavailable", model, ctx["model_len"])
                return {"state": "launcher_unavailable", "rc": 1, "text": "",
                        "usage": {}, "result": {}, "err": "", "tool_calls": []}
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
            # HOT-SESSIONS: ключ сессии вызова; run_sid — sid, реально ушедший
            # в Run (единственный источник флага resumed); cold_retried —
            # повтор после мёртвой сессии идёт холодным.
            sess_key = _session_key(model, ctx["cwd"], effort, autonomy, img_dir)
            # в Run (единственный источник флага resumed); cold_retried —
            # повтор после мёртвой сессии идёт холодным.
            sess_key = _session_key(model, ctx["cwd"], effort, autonomy, img_dir)
            run_sid = ""
            cold_retried = False
            rep_turns = 0
            hot = False
            sess8 = "-"
            for attempt in (1, 2, 3):
                image_part = ""
                if img_stats:
                    image_part = " images=%d image_bytes=%d image_types=%s" % (
                        img_stats[0], img_stats[1], img_stats[2])
                _log(f"exec model={model} effort={effort} effort_source={ctx['effort_source']} "
                     f"autonomy={autonomy} autonomy_source={ctx['autonomy_source']} "
                     f"prompt_bytes={len(ctx['prompt'].encode())}{image_part} {tag}")
                # HOT-SESSIONS: claim живой сессии (проигрыш -> холодный старт
                # с новой сессией, без ожидания чужого Run).
                run_sid = "" if cold_retried else _session_claim(sess_key)
                try:
                    run = Run(ctx["prompt"], model, effort, ctx["effort_source"],
                              autonomy, ctx["autonomy_source"],
                              ctx["cwd"], tag, img_dir=img_dir, img_stats=img_stats,
                              sess_sid=run_sid)
                except LauncherUnavailable:
                    _session_release(sess_key)
                    self._reject(503, "launcher_unavailable",
                                 "canonical launcher is missing or not executable",
                                 model=model, model_len=ctx["model_len"])
                    out = {"state": "launcher_unavailable", "rc": 1, "text": "",
                           "usage": {}, "result": {}, "err": "", "tool_calls": []}
                    break
                except OSError as exc:
                    _session_release(sess_key)
                    _session_drop(sess_key)
                    out = {"state": "pump_error", "rc": 1, "text": "", "usage": {},
                           "result": {}, "err": repr(exc), "tool_calls": []}
                    break
                try:
                    out = self._execute(run, on_text, on_reasoning, on_tool_call,
                                        keepalive, ctx["emulate_tools"])
                finally:
                    try:
                        run.close()
                    finally:
                        _session_release(sess_key)
                # HOT-SESSIONS: инвалидация — ошибка чтения/исполнителя роняет
                # ключ (+purge базы usage), следующий ход холодный.
                if out.get("state") in ("droid_error", "timeout",
                                        "first_token_timeout", "pump_error"):
                    _session_drop(sess_key)
                delivered = bool(out.get("text") or out.get("tool_calls"))
                if out["state"] == "done" and out["rc"] == 0:
                    break
                # Нюанс: уже ушедшие клиенту reasoning-чанки в delivered не
                # учитываются — при повторе размышления продублируются в потоке.
                if out["state"] != "done" or delivered or attempt == 3:
                    if out["state"] == "done" and out.get("rc") != 0 and not delivered:
                        _session_drop(sess_key)
                    break
                # HOT-SESSIONS: done + rc!=0 без delivered — мёртвая сессия:
                # drop ключа + холодный retry. Детектор «session not found» —
                # подстрока в err (case-insensitive).
                dead_sid = run_sid
                _session_drop(sess_key)
                cold_retried = True
                run_sid = ""
                if "session not found" in str(out.get("err") or "").lower():
                    _log(f"dead session (session not found) sess={dead_sid[:8]} {tag}")
                # Транзиентный сбой (rc=1, ничего не выдано клиенту): повтор
                # невидим для клиента (как в droid-cli-proxy; замечено на
                # спорадических "Exec failed" при параллельных стартах).
                _log(f"transient failure rc={out['rc']} err={_err_summary(out.get('err'), 120)!r}, "
                     f"retry {attempt} {tag}")
                # Сбой egress не должен сохранять SKIP-префлайт: повтор идёт с полным префлайтом.
                _last_ok[0] = 0.0
                time.sleep(2 * attempt)
            # HOT-SESSIONS: честная дельта + учёт сессии — один чок-поинт для
            # _serve_json и _serve_sse (оба читают out["usage"] — дельта до эмита).
            raw_usage = out.get("usage") or {}
            out_sid = out.get("session_id") or ""
            ok_done = out.get("state") == "done" and out.get("rc") == 0
            hot = bool(run_sid and not cold_retried and out_sid)
            out["usage"] = _usage_delta(sess_key, out_sid, raw_usage, hot)
            if ok_done and out_sid:
                rep_turns = _session_turns(sess_key, out_sid)
                _session_store(sess_key, out_sid, rep_turns)
            elif ok_done:
                _session_drop(sess_key)
            raw_in = raw_usage.get("input_tokens", 0)
            raw_out = raw_usage.get("output_tokens", 0)
            rep_in = out["usage"].get("input_tokens", 0)
            rep_out = out["usage"].get("output_tokens", 0)
            sess8 = (out_sid or run_sid or "")[:8] or "-"
            _log(f"usage sess={sess8} raw={raw_in}/{raw_out} "
                 f"rep={rep_in}/{rep_out} resumed={1 if hot else 0} turns={rep_turns}")
        finally:
            if img_dir is not None:
                shutil.rmtree(str(img_dir), ignore_errors=True)
            _slots.release()
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
            ctx = {
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
