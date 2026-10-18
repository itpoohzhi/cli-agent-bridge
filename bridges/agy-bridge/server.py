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

Секреты с диска не читаются: ключ авторизации берётся только из окружения
AGY_BRIDGE_KEY (его подкладывает start.sh из ~/.dsh/.env); в окружение дочернего
процесса ключ моста не передаётся. Прокси-переменные выставляет сам лончер.
"""

from __future__ import annotations

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
LAUNCHER = os.environ.get("AGY_LAUNCHER", str(HOME / ".config" / "agy-launch" / "agy-cli.sh"))
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

# Мышление шагов agy: CLI кладёт его в транскрипт разговора пошагово, в середине
# хода. Путь и имя файла фиксированы CLI (проверено на agy 1.3.1).
BRAIN_DIR = Path(os.environ.get("AGY_BRIDGE_BRAIN",
                                "") or str(HOME / ".gemini" / "antigravity-cli" / "brain"))
TRANSCRIPT_NAME = "transcript_full.jsonl"
TRANSCRIPT_POLL_S = float(os.environ.get("AGY_BRIDGE_TRANSCRIPT_POLL", "0.05"))
# Процесс вышел: один финальный проход по файлу, чтобы поймать запись последнего шага.
TRANSCRIPT_GRACE_S = float(os.environ.get("AGY_BRIDGE_TRANSCRIPT_GRACE", "0.4"))
TRANSCRIPT_READ_MAX = 4 * 1024 * 1024

# Effort-оси. `--effort` у agy принимает low|medium|high; id модели — база без уровня,
# уровень всегда уходит отдельным флагом (см. модуль-docstring).
EFFORT_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")
CLI_EFFORT_LEVELS = ("low", "medium", "high")
IMAGE_STATUSES = ("unsupported", "unverified", "probe", "confirmed")
IMPLEMENTED_METHODS: dict = {}

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

# Токеноподобные последовательности в логах: сам ключ моста и длинные hex/base64.
_SECRET = re.compile(r"[A-Za-z0-9_\-]{24,}")
_NOISE = re.compile(r"NODE_TLS_REJECT_UNAUTHORIZED|--trace-warnings|^\(node:\d+\)", re.I)


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
        if not isinstance(limits.get(key), int) or isinstance(limits.get(key), bool) or limits[key] < 0:
            raise FleetViolation("limits_invalid", "-")
    if not isinstance(limits.get("max_body_bytes"), int) or isinstance(limits.get("max_body_bytes"), bool) \
            or limits["max_body_bytes"] <= 0:
        raise FleetViolation("limits_invalid", "-")
    # Типы обязаны быть непустым списком только если изображения вообще принимаются.
    if not isinstance(limits.get("types"), list) or (limits["max_images"] > 0 and not limits["types"]):
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
        # agy-мост изображений не принимает вовсе: max_images = 0, поэтому любая
        # модель обязана быть text-only. Расширение — сначала proof-метод.
        if status in ("unsupported", "unverified"):
            if images.get("method") is not None or input_types != ["text"]:
                raise FleetViolation("status_inconsistent", mid)
        if status == "confirmed":
            raise FleetViolation("method_not_implemented", mid)
        if status == "probe":
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
            "max_tokens": int(item.get("max_tokens") or 0),
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
    if catalog is None:
        sys.stderr.write("fleet_invalid model=- reason=fleet_unreadable\n")
        sys.stderr.flush()
        raise SystemExit(1)
    catalog["path"] = str(FLEET_PATH)
    catalog["sha256"] = hashlib.sha256(raw).hexdigest()
    return catalog


try:
    FLEET = _load_fleet()
except FleetViolation as _violation:
    sys.stderr.write(f"fleet_invalid model={_violation.model} reason={_violation.reason}\n")
    sys.stderr.flush()
    raise SystemExit(1)

MODEL_ID = ENV_MODEL or FLEET["default_model"]


def _log(msg: str) -> None:
    sys.stderr.write("[agy-bridge] %s %s\n" % (time.strftime("%H:%M:%S"), _mask_secrets(msg)))
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
        _log(f"AGY_BRIDGE_IDLE_TIMEOUT={raw!r} invalid, using {_CORE_IDLE_TIMEOUT_S:g}s")
        return float(_CORE_IDLE_TIMEOUT_S)
    return value


def _is_watchdog_enabled() -> bool:
    """Kill-switch адаптивного сторожа: BRIDGE_ENABLE_ADAPTIVE_WATCHDOG=0|false|no|off."""
    raw = os.environ.get("BRIDGE_ENABLE_ADAPTIVE_WATCHDOG", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _mask_secrets(text: str) -> str:
    """Погасить токеноподобные последовательности и сам ключ моста."""
    out = str(text)
    if AUTH_KEY:
        out = out.replace(AUTH_KEY, "***")
    return _SECRET.sub("***", out)


def _err_summary(err: Any, limit: int = 200) -> str:
    text = " ".join(str(err or "").split())
    return text[:limit]


# Порог неактивности хода (без протокольных событий и без прироста CPU/потомков группы).
IDLE_TIMEOUT_S = _idle_timeout_from_env()
# Зачистка группы: сколько ждать после SIGTERM и сколько — reap лидера после SIGKILL.
KILL_TERM_GRACE_S = 2.0
KILL_WAIT_S = 5.0
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


def _tool_choice_none(tool_choice: Any) -> bool:
    return isinstance(tool_choice, str) and tool_choice.strip().lower() == "none"


def _has_image_parts(messages: Any) -> bool:
    """Есть ли в истории запроса image-части (мост их не поддерживает)."""
    if not isinstance(messages, list):
        return False
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "image_url":
                return True
    return False


def _render_message(msg: Any, counter: list) -> str:
    """Сообщение OpenAI в текстовый блок промпта (роли не теряются)."""
    if not isinstance(msg, dict):
        return ""
    role = str(msg.get("role") or "user")
    name = msg.get("name")
    label = role if not name else "%s(%s)" % (role, name)
    body = _flatten_content(msg.get("content"))
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
                fargs = json.dumps(fargs, ensure_ascii=False) if fargs is not None else "{}"
            lines.append("[tool call %s] %s(%s)" % (call.get("id") or "call", fname, fargs))
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


def _messages_to_prompt(messages: list) -> str:
    """Собрать единый текстовый промпт хода.

    Секции протокола инструментов нет намеренно: agy исполняет СВОИ нативные
    инструменты, а не инструменты DSH (см. README, раздел «Инструменты»).
    """
    counter = [0]
    blocks = []
    for msg in messages:
        rendered = _render_message(msg, counter)
        if rendered:
            blocks.append(rendered)
    text = "\n\n".join(blocks).strip()
    if not text:
        text = "Reply with exactly: PONG"
    return text


def _get_resumed_turn_prompt(messages: list) -> str:
    last_asst = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], dict) and messages[i].get("role") == "assistant":
            last_asst = i
            break
    if last_asst >= 0 and last_asst + 1 < len(messages):
        new_msgs = messages[last_asst + 1:]
        prompt = _messages_to_prompt(new_msgs)
        if prompt:
            return prompt
    return _messages_to_prompt(messages)


def _session_claim(sess_key: tuple) -> str:
    """Найти живую свободную сессию и занять её; '' — сессии нет.

    Проверка и занятие идут под одним замком: два параллельных запроса не
    получат один и тот же conversation_id.
    """
    now = time.time()
    with _session_store_lock:
        entry = _session_store.get(sess_key)
        if entry is None:
            return ""
        if (now - entry["last_used"] > SESSION_IDLE_TTL_S
                or now - entry["created"] > SESSION_MAX_TTL_S
                or entry["turns"] >= SESSION_MAX_TURNS):
            _session_store.pop(sess_key, None)
            return ""
        cid = entry["cid"]
        if cid in _in_flight_cids:
            return ""
        _in_flight_cids.add(cid)
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
            _session_store[sess_key] = {"cid": cid, "last_used": now,
                                        "created": now, "turns": 1}


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


class _TranscriptTail:
    """Мышление шагов agy из транскрипта разговора.

    CLI пишет `<BRAIN_DIR>/<conversation_id>/.system_generated/logs/transcript_full.jsonl`
    пошагово, не дожидаясь конца хода: запись `PLANNER_RESPONSE` с непустым
    `thinking` появляется сразу после завершения шага. Файл читается
    инкрементально по байтовому смещению, наружу уходит только приращение текста
    мышления (`_reasoning_suffix` защищает от повторной выдачи того же шага).

    Поток вспомогательный и не может влиять на ответ: нет каталога, нет файла,
    пустой файл, битая строка, оборванный JSON — просто «мышления нет». У
    одновременных запросов разные conversation_id, поэтому и разные файлы.
    """

    def __init__(self, emit, stop_event: threading.Event, done_event: threading.Event,
                 resumed: bool):
        self.emit = emit
        self.stop_event = stop_event
        self.done_event = done_event
        self.resumed = resumed
        self.cid = ""
        self._ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def bind(self, cid: str) -> None:
        """Привязать watcher к разговору из события `init` потока agy."""
        if cid and not self.cid:
            self.cid = cid
            self._ready.set()

    def _path(self) -> Path:
        return (BRAIN_DIR / self.cid / ".system_generated" / "logs" / TRANSCRIPT_NAME)

    def _run(self) -> None:
        # Файл появляется только после первого завершённого шага — ждём привязки к
        # разговору, но не дольше, чем ждали бы первого события agy.
        waited = 0.0
        while not self._ready.wait(timeout=0.2):
            waited += 0.2
            if self.stop_event.is_set() or waited >= FIRST_TOKEN_TIMEOUT_S:
                if not self.stop_event.is_set():
                    # Диагностический след: хвост умер, не дождавшись привязки.
                    _log(f"tail-timeout cid={self.cid[:8] or '-'}: "
                         f"no bind within {FIRST_TOKEN_TIMEOUT_S:g}s")
                return
        path = self._path()
        offset = 0
        if self.resumed:
            # Продолжение треда: в файле уже лежит история, отдавать её повторно
            # нельзя — читаем только то, что допишется после старта хода.
            try:
                offset = path.stat().st_size
            except OSError:
                offset = 0
        buf = b""
        seen: dict = {}
        deadline = time.monotonic() + TIMEOUT_S + 60
        while time.monotonic() < deadline:
            offset, buf = self._read(path, offset, buf, seen)
            if self.done_event.is_set() or self.stop_event.is_set():
                # Ход закончился: последняя запись шага ложится в файл вплотную к
                # событию `result` — один финальный проход и выход из потока.
                time.sleep(TRANSCRIPT_GRACE_S)
                self._read(path, offset, buf, seen)
                return
            time.sleep(TRANSCRIPT_POLL_S)

    def _read(self, path: Path, offset: int, buf: bytes, seen: dict) -> tuple:
        """Дочитать файл с offset; вернуть новое смещение и неполный хвост."""
        try:
            size = path.stat().st_size
        except OSError:
            return offset, buf
        if size < offset:  # файл переписан с нуля — читаем заново
            # Диагностический след: ротация переписала транскрипт с нуля.
            _log(f"tail-rewrite cid={self.cid[:8] or '-'}: size {size} < offset {offset}")
            offset, buf = 0, b""
        if size == offset:
            return offset, buf
        try:
            with open(path, "rb") as fh:
                fh.seek(offset)
                buf += fh.read(TRANSCRIPT_READ_MAX)
        except OSError:
            return offset, buf
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            offset += len(line) + 1
            try:
                self._emit_record(line, seen)
            except Exception:  # noqa: BLE001 — вспомогательный поток не роняет ход
                pass
        return offset, buf

    def _emit_record(self, raw: bytes, seen: dict) -> None:
        line = raw.strip()
        if not line or b"PLANNER_RESPONSE" not in line:
            return  # быстрый отсев служебных записей без разбора JSON
        try:
            rec = json.loads(line.decode("utf-8", "replace"))
        except ValueError:
            return
        if not isinstance(rec, dict) or str(rec.get("type") or "") != "PLANNER_RESPONSE":
            return
        thinking = str(rec.get("thinking") or "")
        if not thinking:
            return
        suffix = _reasoning_suffix(seen, str(rec.get("step_index", "")), thinking)
        if suffix:
            # Диагностический след: хвост увидел запись мышления в транскрипте.
            _log(f"tail-emit cid={self.cid[:8] or '-'} step={rec.get('step_index')} "
                 f"len={len(suffix)}")
            self.emit(suffix)


class Run:
    """Один процесс `agy`; поток-читатель превращает stdout NDJSON в события очереди.

    Промпт подаётся на stdin одной NDJSON-строкой и поток закрывается (`communicate`
    через отдельный поток-писатель): CLI читает stdin до EOF. `-p` не передаётся
    никогда — см. модуль-docstring.
    """

    def __init__(self, prompt: str, model: str, effort: str, effort_source: str,
                 cwd: str, tag: str, conversation_id: str = ""):
        launcher = _launcher()
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        work_dir = cwd if (cwd and os.path.isdir(cwd)) else str(WORKSPACE)
        self.work_dir = work_dir
        self.stdin_line = _ndjson_user_line(prompt)
        cmd = [
            launcher,
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--dangerously-skip-permissions",
            "--model", model,
            "--effort", effort,
            "--print-timeout=" + str(PRINT_TIMEOUT),
        ]
        # RESUME: продолжение треда — отдельным флагом, промпт всё равно через stdin.
        self.run_cid = conversation_id or ""
        if self.run_cid:
            cmd += ["--conversation", self.run_cid]
        self.proc = subprocess.Popen(
            cmd, cwd=work_dir, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, env=_launch_env(),
        )
        self.started = time.monotonic()
        enabled = _is_watchdog_enabled()
        # Kill-switch выключен: порог неактивности = сквозной таймаут, `ps` не вызывается.
        self.controller = AdaptiveTimeoutController(
            idle_timeout_s=IDLE_TIMEOUT_S if enabled else float(TIMEOUT_S),
            safety_cap_s=float(TIMEOUT_S),  # дефолт core (3600 с) не используется
            finish_reserve_s=0.0,           # эффективный потолок ровно TIMEOUT_S
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
        # Мышление шагов: отдельный поток следит за транскриптом разговора и
        # кладёт в очередь события ("reasoning", текст).
        self._proc_done = threading.Event()
        self._stop_watch = threading.Event()
        self._tail = _TranscriptTail(
            emit=lambda text: self.q.put(("reasoning", text)),
            stop_event=self._stop_watch, done_event=self._proc_done,
            resumed=bool(self.run_cid))
        threading.Thread(target=self._feed_stdin, daemon=True).start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        threading.Thread(target=self._pump, daemon=True).start()
        self._tail.start()

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
        """
        final_text = ""
        result_ev = {}
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
                etype = ev.get("event")
                if etype == "init":
                    init = ev.get("init") if isinstance(ev.get("init"), dict) else {}
                    tools = init.get("tools") if isinstance(init.get("tools"), list) else []
                    self.q.put(("init", {
                        "conversation_id": ev.get("conversation_id") or "",
                        "tools": len(tools),
                        "permission_mode": init.get("permission_mode") or "",
                    }))
                    self._tail.bind(str(ev.get("conversation_id") or ""))
                elif etype == "step_update":
                    step = ev.get("step_update") if isinstance(ev.get("step_update"), dict) else {}
                    kind = step.get("step_type")
                    if kind == "agent_response" and step.get("text_delta"):
                        suffix = _reasoning_suffix(
                            self._text_seen, str(step.get("step_index", "")), str(step["text_delta"]))
                        if suffix:
                            self.q.put(("text", suffix))
                    elif kind == "tool" and step.get("state") == "DONE":
                        self.q.put(("tool_trace", {
                            "name": str(step.get("tool_name") or "tool"),
                            "duration_s": step.get("duration_seconds"),
                        }))
                elif etype == "result":
                    result = ev.get("result") if isinstance(ev.get("result"), dict) else {}
                    result_ev = result
                    final_text = str(result.get("response") or "")
                    self.q.put(("result", {
                        "conversation_id": result.get("conversation_id") or "",
                        "status": str(result.get("status") or ""),
                        "error": str(result.get("error") or ""),
                        "duration_s": result.get("duration_seconds"),
                        "num_turns": result.get("num_turns"),
                        "usage": result.get("usage") or {},
                    }))
            rc = self.proc.wait()
        except Exception as exc:  # noqa: BLE001 — читатель не должен умирать молча
            self._proc_done.set()
            self.q.put(("pump_error", repr(exc)))
            return
        time.sleep(0.05)  # дать стоку stderr дозавершиться
        self._proc_done.set()
        self.q.put(("done", (rc, final_text, result_ev)))

    def close(self) -> None:
        self._stop_watch.set()
        self._proc_done.set()
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


def _reasoning_suffix(seen: dict, rid: str, text: str) -> str:
    """Хвост накопительного снимка текста.

    Пустой результат означает «дубликат, не эмитить»."""
    prev = seen.get(rid, "")
    suffix = text[len(prev):] if text.startswith(prev) else text
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


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "agy-bridge/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

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

    def _emit(self, data: str) -> bool:
        """Отправить SSE-строку; False — клиент ушёл."""
        try:
            self.wfile.write(data.encode("utf-8"))
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def _log_reject(self, reason: str, model: str = "unknown", model_len: int = 0) -> None:
        _log(f"reject reason={reason} model={model} model_len={model_len} "
             f"client={self._client_tag()}")

    def _reject(self, code: int, reason: str, message: str,
                model: str = "unknown", model_len: int = 0) -> None:
        self._log_reject(reason, model, model_len)
        self._send(code, {"error": {"message": message, "type": reason, "code": code}})

    def _acquire_slot(self, keepalive) -> str:
        """Занять слот исполнения; '' — успех, иначе причина отказа."""
        if _slots.acquire(blocking=False):
            return ""
        deadline = time.monotonic() + QUEUE_TIMEOUT_S
        while time.monotonic() < deadline:
            if _slots.acquire(timeout=1.0):
                return ""
            if keepalive is not None and not keepalive():
                return "client_gone"
        return "queue_timeout"

    def _execute(self, run: Run, on_text, on_tool_trace, on_reasoning,
                 keepalive) -> dict:
        """Гнать ход до конца; сквозной таймаут TIMEOUT_S на весь ход.

        Колбэки возвращают False, если клиент ушёл.
        Превышение deadline -> kill группы (в run.close()), state=timeout.
        """
        pieces = []
        reasoning_pieces = []
        usage = {}
        result_ev = {}
        conversation_id = ""
        tool_events = 0
        last_ka = time.monotonic()
        last_wd_check = time.monotonic()
        deadline = time.monotonic() + TIMEOUT_S
        gone = [False]

        def state(name: str, rc: int, err: str = "") -> dict:
            return {"rc": rc, "text": "".join(pieces),
                    "reasoning": "".join(reasoning_pieces), "usage": usage,
                    "result": result_ev, "state": name, "err": err,
                    "conversation_id": conversation_id,
                    "duration_s": result_ev.get("duration_s"),
                    "num_turns": result_ev.get("num_turns"),
                    "tool_events": tool_events, "tool_calls": []}

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
            _log(f"reasoning-emit cid={conversation_id[:8] or '-'} "
                 f"n={len(reasoning_pieces)} len={len(text)} ok={int(bool(ok))}")
            if not ok:
                gone[0] = True

        while True:
            if time.monotonic() > deadline:
                return state("timeout", 124, f"proxy timeout after {TIMEOUT_S}s")
            if not run.got_event and time.monotonic() - run.started > FIRST_TOKEN_TIMEOUT_S:
                return state("first_token_timeout", 124,
                             f"no agy event within {FIRST_TOKEN_TIMEOUT_S:g}s")
            if _client_gone(self.connection):
                return state("client_gone", 1)
            try:
                kind, payload = run.q.get(timeout=1.0)
            except queue.Empty:
                # check() запускает `ps`: не чаще WATCHDOG_INTERVAL_S. Пока идут события,
                # on_activity() и так сбрасывает таймер, поэтому пропуск безопасен.
                now = time.monotonic()
                if now - last_wd_check >= WATCHDOG_INTERVAL_S:
                    last_wd_check = now
                    should_stop, wd_reason, _metrics = run.controller.check(run.proc.pid)
                    if should_stop and wd_reason == "idle_timeout":
                        _log(f"watchdog idle_timeout pgid={run.proc.pid} "
                             f"idle>={IDLE_TIMEOUT_S:g}s")
                        return state("idle_timeout", 124,
                                     f"proxy idle timeout after {IDLE_TIMEOUT_S:g}s "
                                     "(no activity in process group)")
                    if should_stop and wd_reason == "absolute_cap":
                        return state("timeout", 124, f"proxy timeout after {TIMEOUT_S}s")
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
                _log(f"init conversation={conversation_id[:8] or '-'} "
                     f"tools={payload.get('tools')} "
                     f"permission_mode={payload.get('permission_mode')}")
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
                    message = str(payload.get("error") or "agy reported an error")
                    if not message:
                        message = "agy reported an error"
                    return state("agy_error", 1, message[:500])
            elif kind == "pump_error":
                return state("pump_error", 1, str(payload))
            elif kind == "done":
                rc, final_text, raw_result = payload
                if not result_ev and raw_result:
                    result_ev = raw_result
                if not pieces and final_text:
                    add_content(final_text)
                if gone[0]:
                    return state("client_gone", 1)
                time.sleep(0.05)
                err = "".join(run.err_box).strip()
                status = str(result_ev.get("status") or "").upper()
                if rc != 0 and (status == "ERROR" or not pieces):
                    return state("agy_error", rc, (str(result_ev.get("error") or "") or err)[:500])
                return state("done", rc, err)

    def _run_once(self, ctx: dict, on_text, on_tool_trace, on_reasoning, keepalive) -> dict:
        model = ctx["model"]
        effort = ctx["effort"]
        tag = ctx["tag"]
        reason = self._acquire_slot(keepalive)
        if reason:
            _log(f"no slot ({reason}) model={model} {tag}")
            if reason == "queue_timeout":
                self._log_reject("overloaded", model, ctx["model_len"])
            return {"state": reason, "rc": 1, "text": "", "usage": {}, "result": {},
                    "err": "", "tool_calls": [], "tool_events": 0,
                    "conversation_id": "", "num_turns": None, "duration_s": None}
        t0 = time.monotonic()
        out: dict = {}
        try:
            try:
                _launcher()
            except LauncherUnavailable:
                self._log_reject("launcher_unavailable", model, ctx["model_len"])
                return {"state": "launcher_unavailable", "rc": 1, "text": "",
                        "usage": {}, "result": {}, "err": "", "tool_calls": [],
                        "tool_events": 0, "conversation_id": "", "num_turns": None,
                        "duration_s": None}
            for attempt in (1, 2):
                _log(f"exec model={model} effort={effort} effort_source={ctx['effort_source']} "
                     f"prompt_bytes={len(ctx['prompt'].encode())} "
                     f"tools={ctx['tools_count']} resume={1 if ctx.get('conversation_id') else 0} {tag}")
                try:
                    run = Run(ctx["prompt"], model, effort, ctx["effort_source"],
                              ctx["cwd"], tag, conversation_id=ctx.get("conversation_id") or "")
                except LauncherUnavailable:
                    self._reject(503, "launcher_unavailable",
                                 "canonical launcher is missing or not executable",
                                 model=model, model_len=ctx["model_len"])
                    out = {"state": "launcher_unavailable", "rc": 1, "text": "",
                           "usage": {}, "result": {}, "err": "", "tool_calls": [],
                           "tool_events": 0, "conversation_id": "", "num_turns": None,
                           "duration_s": None}
                    break
                except OSError as exc:
                    out = {"state": "pump_error", "rc": 1, "text": "", "usage": {},
                           "result": {}, "err": repr(exc), "tool_calls": [],
                           "tool_events": 0, "conversation_id": "", "num_turns": None,
                           "duration_s": None}
                    break
                try:
                    out = self._execute(run, on_text, on_tool_trace, on_reasoning, keepalive)
                finally:
                    run.close()
                if out["state"] == "done":
                    break
                delivered = bool(out.get("text") or out.get("tool_calls"))
                if ctx.get("hot_resumed") and out["state"] != "client_gone":
                    # Горячая сессия сломалась: больше её не используем, а повтор
                    # идёт холодным вызовом с полной историей.
                    _session_invalidate(ctx["sess_key"], ctx["conversation_id"])
                    ctx["hot_resumed"] = False
                    ctx["conversation_id"] = ""
                    ctx["prompt"] = ctx["full_prompt"]
                    if out["state"] == "agy_error" and not delivered:
                        _log(f"hot session failed err={_err_summary(out.get('err'), 120)!r}, "
                             f"cold fallback {tag}")
                        continue
                # Транзиентный сбой до выдачи текста клиенту — один невидимый повтор.
                transient = out["state"] in ("agy_error", "pump_error", "done") and not delivered
                if not transient or attempt == 2:
                    break
                _log(f"transient failure state={out['state']} rc={out.get('rc')} "
                     f"err={_err_summary(out.get('err'), 120)!r}, retry {attempt} {tag}")
                time.sleep(2 * attempt)
            if (out.get("state") == "done" and out.get("conversation_id")
                    and ctx.get("sess_key")):
                _session_commit(ctx["sess_key"], str(out["conversation_id"]))
            if out.get("state") != "client_gone":
                _last_ok[0] = (time.monotonic()
                               if (out.get("state") == "done" and out.get("rc") == 0) else 0.0)
        finally:
            _slots.release()
        _log(f"done model={model} rc={out.get('rc')} state={out.get('state')} "
             f"conversation={(out.get('conversation_id') or '-')[:8]} "
             f"turns={out.get('num_turns')} tool_events={out.get('tool_events')} "
             f"out_bytes={len((out.get('text') or '').encode())} "
             f"wall_s={time.monotonic() - t0:.1f} "
             f"err={_err_summary(out.get('err'))!r} {tag}")
        return out

    @staticmethod
    def _usage_payload(usage: dict) -> dict:
        """usage agy -> OpenAI-поля. thinking_tokens прибавляем к completion."""
        return {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0) + usage.get("thinking_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    @staticmethod
    def _error_body(out: dict) -> Any:
        st = out.get("state")
        if st == "timeout":
            return {"message": f"agy timed out after {TIMEOUT_S}s",
                    "type": "timeout", "code": 504}
        if st == "idle_timeout":
            return {"message": f"agy execution idle timeout after {IDLE_TIMEOUT_S:g}s "
                               "(no activity or progress in process group)",
                    "type": "idle_timeout", "code": 504}
        if st == "first_token_timeout":
            return {"message": f"first_token_timeout: agy gave no event within "
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
        if st == "agy_error":
            return {"message": str(out.get("err") or "agy reported an error")[:500],
                    "type": "agy_error", "code": 502}
        if out.get("rc") != 0 or not out.get("text"):
            return {"message": f"agy exited rc={out.get('rc')}",
                    "detail": str(out.get("err"))[:500], "type": "proxy_error", "code": 502}
        return None

    # ---- HTTP --------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/v1/health"):
            with _active_lock:
                active = len(_active)
            self._send(200, {
                "ok": True, "transport": "agy-stream-json", "model": MODEL_ID,
                "active": active, "max_concurrent": MAX_CONCURRENT,
                "hot_sessions": len(_session_store),
                "tool_emulation": False,
                "tool_translation": False,
                "native_tools": True,
                "images": False,
                "uptime_s": int(time.time() - _started),
            })
            return
        if not _auth_ok(self):
            self._send(401, {"error": {"message": "unauthorized",
                                       "type": "auth_error", "code": 401}})
            return
        if path in ("/v1/models", "/models"):
            data = []
            order = [MODEL_ID] + [mid for mid in FLEET["order"] if mid != MODEL_ID]
            for mid in order:
                model = FLEET["models"][mid]
                data.append({
                    "id": mid, "object": "model", "owned_by": "antigravity",
                    "created": 0, "context_length": model["context_window"],
                })
            self._send(200, {"object": "list", "data": data})
            return
        self._send(404, {"error": {"message": f"not found: {path}",
                                   "type": "not_found", "code": 404}})

    def do_POST(self) -> None:  # noqa: N802
        if not _auth_ok(self):
            # Непрочитанное тело иначе будет разобрано как следующий запрос keep-alive.
            self.close_connection = True
            self._send(401, {"error": {"message": "unauthorized",
                                       "type": "auth_error", "code": 401}})
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
            self._reject(413, "payload_too_large", "request body exceeds the bridge limit")
            return
        reserved = 0
        budget = _budget
        if budget is not None and length:
            if not budget.reserve(length):
                self._reject(503, "overloaded", "bridge overloaded: body budget exhausted")
                return
            reserved = length
        use_cid = ""
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
                self._send(404, {"error": {"message": f"not found: {path}",
                                           "type": "not_found", "code": 404}})
                return
            raw_model = req.get("model")
            model_len = len(raw_model) if isinstance(raw_model, str) else 0
            if raw_model is None:
                model_id = MODEL_ID
            elif isinstance(raw_model, str):
                candidate = raw_model.strip()
                model_id = candidate if candidate else MODEL_ID
            else:
                self._reject(400, "model_not_allowed",
                             "model must be a string from the catalogue", "unknown", model_len)
                return
            if model_id not in FLEET["models"]:
                self._reject(400, "model_not_allowed", "model is not in the catalogue",
                             "unknown", model_len)
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
                    self._reject(400, "unsupported_reasoning_effort",
                                 "reasoning_effort is not allowed for this model",
                                 model_id, model_len)
                    return
            else:
                self._reject(400, "unsupported_reasoning_effort",
                             "reasoning_effort must be a string", model_id, model_len)
                return
            if "reasoning" in req and req.get("reasoning") is not None:
                self._reject(400, "unsupported_parameter",
                             "reasoning parameter is not supported", model_id, model_len)
                return
            messages = req.get("messages") if isinstance(req.get("messages"), list) else []
            if _has_image_parts(messages):
                self._reject(400, "image_input_not_supported",
                             "image rejected: image_input_not_supported",
                             model_id, model_len)
                return
            try:
                _launcher()
            except LauncherUnavailable:
                self._reject(503, "launcher_unavailable",
                             "canonical launcher is missing or not executable",
                             model_id, model_len)
                return
            raw_tools = req.get("tools")
            tools = [t for t in raw_tools if isinstance(t, dict)] if isinstance(raw_tools, list) else []
            tools_count = 0 if _tool_choice_none(req.get("tool_choice")) else len(tools)
            full_prompt = _messages_to_prompt(messages)
            extra = req.get("extra_body") if isinstance(req.get("extra_body"), dict) else {}
            cwd = str(extra.get("cwd") or "")
            if len(cwd) > CWD_MAX_LEN:
                cwd = ""
            conversation_id = str(extra.get("conversation_id") or req.get("conversation_id") or "")
            sess_key = (model_id, cwd, effort)
            is_resumed = False
            prompt = full_prompt
            if not conversation_id:
                use_cid = _session_claim(sess_key)
                if use_cid:
                    conversation_id = use_cid
                    is_resumed = True
                    prompt = _get_resumed_turn_prompt(messages)
            ctx = {
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
                "tag": (f"client={self._client_tag()} "
                        f"ua={(self.headers.get('User-Agent') or '-')[:60]}"),
                "stream": bool(req.get("stream")),
            }
            if ctx["stream"]:
                self._serve_sse(ctx)
            else:
                self._serve_json(ctx)
        finally:
            if use_cid:
                with _session_store_lock:
                    _in_flight_cids.discard(use_cid)
            if reserved and budget is not None:
                budget.release(reserved)

    def _serve_json(self, ctx: dict) -> None:
        out = self._run_once(ctx, lambda _v: True, lambda _e: True, lambda _r: True, None)
        if out.get("state") == "client_gone":
            return
        err = self._error_body(out)
        if err is not None:
            self._send(err["code"], {"error": err})
            return
        usage = out.get("usage") or {}
        message = {"role": "assistant", "content": out["text"]}
        reasoning = out.get("reasoning") or ""
        if reasoning:
            # OpenAI-совместимое поле мышления: Harness читает его из сообщения
            # ассистента так же, как из дельты потока.
            message["reasoning_content"] = reasoning
        payload = {
            "id": f"chatcmpl-agy-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
            "created": int(time.time()), "model": ctx["model"],
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": self._usage_payload(usage),
        }
        if out.get("conversation_id"):
            payload["conversation_id"] = out["conversation_id"]
        self._send(200, payload)

    def _serve_sse(self, ctx: dict) -> None:
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

        def chunk(delta: dict, finish=None, usage: dict | None = None,
                  conversation_id: str = "") -> str:
            body: dict = {
                "id": completion_id, "object": "chat.completion.chunk", "created": created,
                "model": shown_model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            if usage is not None:
                body["usage"] = usage
            if conversation_id:
                body["conversation_id"] = conversation_id
            return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"

        def on_text(value: str) -> bool:
            return self._emit(chunk({"content": value}))

        def on_reasoning(value: str) -> bool:
            # Мышление шага: Harness читает первое непустое из
            # reasoning_content|reasoning|reasoning_text — отдаём только первое.
            return self._emit(chunk({"reasoning_content": value}))

        def on_tool_trace(_event: dict) -> bool:
            # Нативный инструмент agy исполняется внутри CLI и наружу не транслируется:
            # клиенту нечего добавлять к его же истории вызовов. Трассировка — в stderr.
            return True

        def keepalive() -> bool:
            return self._emit(": keepalive\n\n")

        if not self._emit(chunk({"role": "assistant", "content": ""})):
            return
        out = self._run_once(ctx, on_text, on_tool_trace, on_reasoning, keepalive)
        if out.get("state") == "client_gone":
            _log("client gone mid-stream, child killed")
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
            self._emit("data: " + json.dumps({"error": err}, ensure_ascii=False) + "\n\n")
        self._emit("data: [DONE]\n\n")


class Server(ThreadingHTTPServer):
    """HTTP-сервер с семафором числа соединений на уровне приёма."""

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
    """Удалить временные каталоги ходов старше часа (наследие упавших ходов)."""
    cutoff = time.time() - 3600
    for path in WORKSPACE.glob("run-*"):
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(str(path), ignore_errors=True)
        except OSError:
            pass


def main() -> None:
    global _budget
    if not AUTH_KEY:
        sys.stderr.write("AGY_BRIDGE_KEY is required; refusing to start\n")
        raise SystemExit(1)
    _budget = _ByteBudget(int(FLEET["admission"]["max_inflight_body_bytes"]))
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    _sweep_workspace()
    _log(f"fleet_sha256={FLEET['sha256']} models={len(FLEET['order'])}")
    try:
        _launcher()
    except LauncherUnavailable:
        _log(f"launcher_missing path={LAUNCHER} (requests will fail with 503)")
    signal.signal(signal.SIGTERM, _kill_all)
    signal.signal(signal.SIGINT, _kill_all)
    api_key_present = "yes" if AUTH_KEY else "no"
    server = Server((HOST, PORT), Handler)
    _log(f"listen {HOST}:{PORT} model={MODEL_ID} max_concurrent={MAX_CONCURRENT} "
         f"queue_timeout={QUEUE_TIMEOUT_S}s timeout={TIMEOUT_S}s keepalive={KEEPALIVE_S}s "
         f"api_key={api_key_present}")
    print(f"[agy-bridge] listening on http://{HOST}:{PORT}/v1", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
