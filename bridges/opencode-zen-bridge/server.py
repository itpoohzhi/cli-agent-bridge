#!/usr/bin/env python3
"""opencode-zen-bridge — локальный OpenAI-совместимый мост поверх CLI `opencode run`.

Один запрос `/v1/chat/completions` = один headless-ход
`~/.opencode/bin/opencode run -m opencode/<id> --format json` с промптом через stdin
(не argv: история > ~1 МБ пробивает macOS ARG_MAX).
Ответ собирается из событий `type:"text"` (конкатенация part.text),
мышление — из событий `type:"reasoning"` (part.text и reasoningEncryptedContent),
usage — из события `type:"step_finish"` (part.tokens).

Транспорт — только stdlib. Стрим (SSE) реализован через честный потоковый вывод
дельт (text и reasoning) по мере поступления строк из `opencode run`.

Ключ авторизации берётся из OPENCODE_ZEN_BRIDGE_KEY (его подкладывает start.sh
из ~/.dsh/.env). Без ключа мост не стартует.
"""

from __future__ import annotations

import hmac
import http.client
import json
import os
import queue
import random
import re
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlsplit

HOST = os.environ.get("OPENCODE_ZEN_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_PORT", "9883"))
AUTH_KEY = os.environ.get("OPENCODE_ZEN_BRIDGE_KEY", "").strip()

TIMEOUT_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_TIMEOUT_S", "1800"))
# Пауза stdout `opencode run` на большом промпте может быть долгой; пока она длится, в SSE уходит
# пустая дельта раз в KEEPALIVE_INTERVAL_S (0 — выключено), иначе клиент рвёт «молчащий» стрим.
KEEPALIVE_INTERVAL_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_KEEPALIVE_S", "15.0"))
MAX_CONCURRENT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT", "2"))

OPENCODE_BIN = os.environ.get("OPENCODE_BIN", str(Path.home() / ".opencode" / "bin" / "opencode"))
WORKSPACE = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_WORKSPACE", str(Path(__file__).resolve().parent / "workspace")))
LOG_PATH = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_LOG", str(Path(__file__).resolve().parent / "logs" / "bridge.log")))

DEFAULTWORKDIR = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_WORKDIR", str(WORKSPACE)))

# --- Каталог моделей Zen ----------------------------------------------------------------
# 2026-10-24: каталог динамический. Единственный писатель — sync_dsh_models.py: он пересекает
# api.json (free, не deprecated, tool_call) со списком Zen и пишет state/zen-catalog.json; мост
# только читает файл (перечитывание по mtime, не чаще раза в CATALOG_STAT_INTERVAL_S) и при
# отсутствии/порче файла берёт встроенный снимок zen_catalog.STATIC_FALLBACK_CATALOG.
# Zen-модели запускаются как `opencode run --standalone` с OPENCODE_MODELS_PATH на свежий api.json
# и БЕЗ OPENCODE_API_KEY (истёкший ключ из env давал 401 api_key_expired — причина отказа от
# standalone 2026-10-19). Режим static (kill-switch) — прежний маршрут через фоновый сервис.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import zen_catalog as zc

DEPRECATED_MODEL_ALIASES: dict[str, str] = zc.DEPRECATED_MODEL_ALIASES


def _normalize_catalog_mode(raw: str) -> str:
    """dynamic (по умолчанию) | static; `legacy` — синоним static (аварийный kill-switch)."""
    value = (raw or "").strip().lower()
    return "static" if value in ("static", "legacy") else "dynamic"


CATALOG_MODE = _normalize_catalog_mode(os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_MODE", "dynamic"))
CATALOG_STATE_PATH = Path(os.environ.get(
    "OPENCODE_ZEN_BRIDGE_CATALOG_STATE", str(Path(__file__).resolve().parent / "state" / "zen-catalog.json")))
OPENCODE_MODELS_PATH = os.environ.get(
    "OPENCODE_ZEN_BRIDGE_MODELS_PATH", str(Path.home() / ".cache" / "opencode" / "models.json"))
CATALOG_STAT_INTERVAL_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_STAT_INTERVAL_S", "5"))

# Живой каталог: id -> метаданные (context_length, max_output, supports_variant, variant_map, ...).
# Словарь изменяется на месте, чтобы ссылки на него (в том числе в тестах) оставались верными.
ALLOWED_MODELS: dict[str, dict[str, Any]] = {}
# Устаревшие/выбывшие id -> модель-исполнитель (статические ∪ deprecated из api.json ∪ retired).
MODEL_ALIASES: dict[str, str] = dict(DEPRECATED_MODEL_ALIASES)

_catalog_lock = threading.RLock()
_catalog_ids: set[str] = set()           # id, добавленные каталогом (тестовые/Go-записи не трогаем)
_catalog_mtime: int | None = None
_catalog_checked_at = float("-inf")
CATALOG_SOURCE = "init"


def _stat_mtime(path: Path) -> int | None:
    """mtime state-файла каталога (нс) или None."""
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


def _read_catalog_state() -> tuple[dict[str, Any], str]:
    """Состояние каталога и его источник: file | fallback | static."""
    if CATALOG_MODE == "dynamic":
        state = zc.load_state_file(CATALOG_STATE_PATH)
        if state is not None:
            return state, "file"
        return zc.fallback_state(), "fallback"
    return zc.fallback_state(), "static"


def reload_catalog() -> dict[str, Any]:
    """Перечитать каталог и применить к ALLOWED_MODELS/MODEL_ALIASES на месте."""
    global _catalog_mtime, _catalog_ids, CATALOG_SOURCE
    mtime = _stat_mtime(CATALOG_STATE_PATH)
    state, source = _read_catalog_state()
    models = zc.entries_to_bridge_models(state["models"])
    with _catalog_lock:
        for model_id in _catalog_ids:
            ALLOWED_MODELS.pop(model_id, None)
        ALLOWED_MODELS.update(models)
        _catalog_ids = set(models)
        MODEL_ALIASES.clear()
        MODEL_ALIASES.update(DEPRECATED_MODEL_ALIASES)
        MODEL_ALIASES.update(state["aliases"])
        _catalog_mtime = mtime
        CATALOG_SOURCE = source
    return {"ok": True, "source": source, "mode": CATALOG_MODE, "models": sorted(models),
            "aliases": len(MODEL_ALIASES), "degraded": bool(state.get("degraded"))}


def _maybe_reload_catalog(now: float | None = None) -> bool:
    """Горячее обновление: не чаще одного stat за CATALOG_STAT_INTERVAL_S, перечитывание при смене mtime."""
    global _catalog_checked_at
    if CATALOG_MODE != "dynamic":
        return False
    now = time.monotonic() if now is None else now
    with _catalog_lock:
        if now - _catalog_checked_at < CATALOG_STAT_INTERVAL_S:
            return False
        _catalog_checked_at = now
        if _stat_mtime(CATALOG_STATE_PATH) == _catalog_mtime:
            return False
    reload_catalog()
    return True


def _zen_active_ids() -> list[str]:
    """Id Zen-моделей каталога (без Go-маршрутов)."""
    return sorted(m for m, meta in ALLOWED_MODELS.items() if not meta.get("provider") and not meta.get("base_url"))


def _resolve_alias(model_id: str) -> str | None:
    """Модель-исполнитель для устаревшего/выбывшего id; None — id неизвестен."""
    target, aliased = zc.resolve_model(model_id, _zen_active_ids(), MODEL_ALIASES, DEFAULT_MODEL)
    return target if aliased else None


reload_catalog()

DEFAULT_MODEL = os.environ.get("OPENCODE_ZEN_BRIDGE_MODEL", zc.ALIAS_TARGET)


def _effective_default_model() -> str:
    """Модель для запроса без `model`: DEFAULT_MODEL, а если её нет в каталоге — цель алиасов."""
    if DEFAULT_MODEL in ALLOWED_MODELS:
        return DEFAULT_MODEL
    return zc.pick_alias_target(_zen_active_ids(), DEFAULT_MODEL)


# Системный промпт по умолчанию: мост — чистый текстовый чат без инструментов.
DEFAULT_SYSTEM_HINT = (
    "Ты отвечаешь в текстовом чате. Не вызывай инструменты и не выполняй команды; "
    "верни только текстовый ответ."
)

# 2026-10-08: эмуляция OpenAI function calling (порт из muse-bridge / droid-bridge).
# Без неё DSH получал только текст + finish_reason "stop" и завершал ход после
# первой реплики («Completed in 11s»), а встроенные инструменты opencode пытались
# исполняться внутри CLI в workspace моста.
TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"
# 2026-10-24: на opencode.ai/zen `<tool_call>` — нативный спец-токен GLM-5: апстрим вырезает блок
# из text (токены при этом тарифицируются), а `<tool_call>` в прошлых репликах провоцирует модель
# выдавать его снова. Для GLM протокол ведётся на `<tool_invoke>`; парсер понимает оба тега.
ALT_TOOL_CALL_OPEN = "<tool_invoke>"
ALT_TOOL_CALL_CLOSE = "</tool_invoke>"
TOOL_CALL_TAGS: tuple[tuple[str, str], ...] = (
    (TOOL_CALL_OPEN, TOOL_CALL_CLOSE),
    (ALT_TOOL_CALL_OPEN, ALT_TOOL_CALL_CLOSE),
)


def _uses_alt_tool_tag(model_id: str = "") -> bool:
    """GLM-модели получают протокол на `<tool_invoke>`, а не на спец-токене `<tool_call>`."""
    return "glm" in (model_id or "").lower()


def _tool_tags_for_model(model_id: str = "") -> tuple[str, str]:
    """(открывающий, закрывающий) тег протокола для модели."""
    if _uses_alt_tool_tag(model_id):
        return ALT_TOOL_CALL_OPEN, ALT_TOOL_CALL_CLOSE
    return TOOL_CALL_OPEN, TOOL_CALL_CLOSE


def _rewrite_tool_tags_for_model(text: str, model_id: str = "") -> str:
    """Заменить `<tool_call>`-теги в промпте на `<tool_invoke>` для GLM; остальным — как есть."""
    if not _uses_alt_tool_tag(model_id):
        return text
    return text.replace(TOOL_CALL_OPEN, ALT_TOOL_CALL_OPEN).replace(TOOL_CALL_CLOSE, ALT_TOOL_CALL_CLOSE)


def _open_tag_at(text: str, index: int) -> tuple[str, str] | None:
    """Пара тегов, чей открывающий тег стоит в `text[index:]`, или None."""
    for open_tag, close_tag in TOOL_CALL_TAGS:
        if text.startswith(open_tag, index):
            return open_tag, close_tag
    return None

# Встроенные инструменты opencode НЕ исполняются в мосте: permission "ask" →
# `opencode run` автоматически отклоняет вызов (инструменты исполняет DSH).
# "deny" / tools:false НЕЛЬЗЯ: инструменты пропадают из запроса, и Zen отвечает 403
# «OpenCode's free tier can only be used from within OpenCode» (проверено 08.10).
OPENCODE_CONFIG_CONTENT = os.environ.get(
    "OPENCODE_ZEN_BRIDGE_OPENCODE_CONFIG",
    '{"permission":{"*":"ask"},"provider":{"opencode":{"options":{"baseURL":"http://127.0.0.1:10830/v1"}}}}',
)

# Модель часто зовёт встроенный инструмент opencode с тем же именем, что у DSH
# (bash/read/edit/write/glob/grep). Отклонённый вызов переводим в tool_call DSH.
NATIVE_ARG_ALIASES: dict[str, str] = {
    "filePath": "file_path",
    "oldString": "old_string",
    "newString": "new_string",
    "replaceAll": "replace_all",
    "timeout": "timeoutMs",
}


# 2026-10-08 (18:46, живая сессия): Muse вызвал встроенный `todowrite`, DSH-инструмента
# с таким именем нет (у DSH — `todo_write`) → mapped=False, 87 символов преамбулы и
# finish "stop", DSH закончил ход после одного шага. Встроенный инструмент opencode
# -> кандидаты DSH (по порядку; первый предложенный в запросе выигрывает).
NATIVE_TOOL_ALIASES: dict[str, tuple[str, ...]] = {
    "todowrite": ("todo_write", "TodoWrite", "write_todos"),
    "webfetch": ("web_fetch", "WebFetch", "fetch"),
    "websearch": ("web_search", "WebSearch"),
    "codesearch": ("web_search", "WebSearch"),
    "task": ("subagent", "Task", "agent"),
    "patch": ("apply_patch", "patch"),
    "apply_patch": ("apply_patch", "patch"),
    "skill": ("skill", "Skill"),
    "question": ("ask_user_question", "AskUserQuestion"),
    "plan_exit": ("exit_plan_mode", "ExitPlanMode"),
    "exitplanmode": ("exit_plan_mode", "ExitPlanMode"),
    "read": ("read", "Read", "read_file"),
    "write": ("write", "Write", "write_file"),
    "edit": ("edit", "Edit"),
    "bash": ("bash", "Bash", "shell"),
    # opencode v2.1.2: встроенный шелл называется `shell`, а не `bash`.
    "shell": ("bash", "Bash", "shell"),
    "glob": ("glob", "Glob"),
    "grep": ("grep", "Grep"),
}
# Подстрока имени DSH-инструмента, если точного кандидата нет (MCP-поиск и т.п.).
NATIVE_TOOL_NAME_PATTERNS: dict[str, tuple[str, ...]] = {
    "websearch": ("web_search", "websearch"),
    "codesearch": ("web_search", "websearch"),
}
# Значения enum, которых нет у DSH (opencode todo: cancelled).
ENUM_VALUE_ALIASES: dict[str, str] = {"cancelled": "completed", "canceled": "completed"}

NATIVE_RETRY_LIMIT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES", "2"))

# 2026-10-24 (AD-002): отдельный kill-switch детектора оборванного шага; независим от
# NATIVE_RETRY_LIMIT (повтор встроенного инструмента без DSH-двойника остаётся включённым).
STEP_RECOVERY_ENABLED = os.environ.get("OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1").strip().lower() not in (
    "0", "false", "no", "off")

# 2026-10-24 (AD-003): единый потолок запусков `opencode run` на один HTTP-запрос — суммарно по
# первичному запуску, повтору транзиторного отказа CLI, повтору незавершённого шага и
# повтору встроенного инструмента без DSH-двойника (A_max).
MAX_TOTAL_SPAWNS = max(1, int(os.environ.get("OPENCODE_ZEN_BRIDGE_MAX_TOTAL_SPAWNS", "3")))

# 2026-10-10: `opencode run` иногда падает за ~1 с с rc=1 без вывода
# («Error: Unexpected error … database is locked», sqlite opencode при параллельном старте).
# Такой отказ — транзиторный: прогон без вывода повторяется (не более FAIL_RETRY_LIMIT раз,
# и всегда внутри потолка MAX_TOTAL_SPAWNS: первичный запуск + FAIL_RETRY_LIMIT <= MAX_TOTAL_SPAWNS).
FAIL_RETRY_LIMIT = min(int(os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRIES", "3")), MAX_TOTAL_SPAWNS - 1)
# Старый линейный backoff заменён Full Jitter (_retry_backoff_s); значение 0 по-прежнему отключает паузы.
FAIL_RETRY_BACKOFF_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRY_BACKOFF_S", "0.8"))
RETRY_BACKOFF_BASE_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_BASE_S", "0.5"))
RETRY_BACKOFF_CAP_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_CAP_S", "2.0"))

# Очередь stdout `opencode run`: ограничена, переполнение — отказ попытки, а не рост кучи.
STDOUT_QUEUE_MAX = int(os.environ.get("OPENCODE_ZEN_BRIDGE_STDOUT_QUEUE_MAX", "4096"))

# Bulkhead слота: ожидание ограничено по времени и по числу ждущих (13-й ждущий — мгновенный 503).
MAX_SLOT_WAITERS = int(os.environ.get("OPENCODE_ZEN_BRIDGE_SLOT_MAX_WAITERS", "12"))
SLOT_WAIT_TIMEOUT_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_SLOT_WAIT_S", "15.0"))
SLOT_MAX_WAITERS = MAX_SLOT_WAITERS  # имена из архитектурного пакета
SLOT_WAIT_S = SLOT_WAIT_TIMEOUT_S

# Темп запусков `opencode run` (token bucket), process-level Retry Budget и Circuit Breaker апстрима.
SPAWN_RATE_PER_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_SPAWN_RATE_PER_S", "1.0"))
SPAWN_BURST = float(os.environ.get("OPENCODE_ZEN_BRIDGE_SPAWN_BURST", "1.0"))
SPAWN_WAIT_MAX_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_SPAWN_WAIT_MAX_S", "5.0"))
RETRY_BUDGET_MAX = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_MAX", "6"))
RETRY_BUDGET_PER_REQUEST = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_PER_REQUEST", "0.20"))
RETRY_BUDGET_RESERVE_RPS = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_RESERVE_RPS", "0.05"))
CB_FAIL_THRESHOLD = int(os.environ.get("OPENCODE_ZEN_BRIDGE_CB_FAIL_THRESHOLD", "5"))
CB_RESET_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_CB_RESET_S", "10.0"))


def _retry_backoff_s(retry_num: int, rng_fn: Callable[[float, float], float] = random.uniform) -> float:
    """Full Jitter: пауза перед повторным запуском = U(0, min(CAP, BASE * 2**retry_num)); retry_num с 1."""
    ceiling = min(RETRY_BACKOFF_CAP_S, RETRY_BACKOFF_BASE_S * (2 ** max(0, retry_num)))
    return rng_fn(0.0, ceiling)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    """JSON-объект как есть, иначе пустой словарь (для цепочек `.get()` без None)."""
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    """JSON-массив как есть, иначе пустой список."""
    return cast("list[Any]", value) if isinstance(value, list) else []


def _tool_schemas(tools: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Инструменты запроса -> {name: parameters-schema}."""
    out: dict[str, dict[str, Any]] = {}
    for item in tools:
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        if isinstance(fn, dict) and isinstance(fn.get("name"), str) and fn["name"]:
            out[fn["name"]] = _dict_or_empty(fn.get("parameters"))
    return out


def _fit_value(value: Any, schema: Any) -> tuple[bool, Any]:
    """Значение -> (ok, приведённое к схеме): ключи-алиасы, лишние ключи, enum."""
    if not isinstance(schema, dict):
        return True, value
    enum = schema.get("enum")
    if isinstance(enum, list) and enum and value not in enum:
        alias = ENUM_VALUE_ALIASES.get(value) if isinstance(value, str) else None
        if alias in enum:
            return True, alias
        return False, None
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        fitted = []
        for item in value:
            ok, item = _fit_value(item, schema["items"])
            if not ok:
                return False, None
            fitted.append(item)
        return True, fitted
    if isinstance(value, dict) and isinstance(schema.get("properties"), dict):
        props = schema["properties"]
        strict = schema.get("additionalProperties") is False
        mapped: dict[str, Any] = {}
        for raw_key, sub in value.items():
            key: str = NATIVE_ARG_ALIASES.get(str(raw_key), str(raw_key))
            if key not in props:
                if strict:
                    continue
                mapped[key] = sub
                continue
            ok, sub = _fit_value(sub, props[key])
            if not ok:
                return False, None
            mapped[key] = sub
        required = _list_or_empty(schema.get("required"))
        if any(r not in mapped for r in required):
            return False, None
        return True, mapped
    return True, value


def _fit_args(target: str, args: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any] | None:
    """Аргументы встроенного инструмента -> аргументы DSH-инструмента `target` или None.

    Верхний уровень: ключи переименовываются по NATIVE_ARG_ALIASES, лишние
    отбрасываются, вложенные объекты/массивы приводятся к схеме (enum, strict).
    Отсутствующий обязательный `description` (bash DSH) подставляется; одно
    недостающее обязательное строковое поле заполняется единственным
    неиспользованным строковым аргументом (query -> search_query и т.п.).
    """
    props = _dict_or_empty(schema.get("properties"))
    mapped: dict[str, Any] = {}
    leftovers: list[str] = []
    for key, value in args.items():
        key = NATIVE_ARG_ALIASES.get(key, key)
        if props and key not in props:
            if isinstance(value, str) and value.strip():
                leftovers.append(value)
            continue
        ok, value = _fit_value(value, props.get(key))
        if not ok:
            return None
        mapped[key] = value
    required = _list_or_empty(schema.get("required"))
    if "description" in required and "description" not in mapped:
        mapped["description"] = f"{target}: {str(mapped.get('command') or '')[:80]}".strip()
    missing = [r for r in required if r not in mapped]
    if (len(missing) == 1 and len(leftovers) == 1
            and (props.get(missing[0]) or {}).get("type") in ("string", None)):
        mapped[missing[0]] = leftovers[0]
        missing = []
    if missing:
        return None
    return mapped


def _pick_target(tool: str, schemas: dict[str, dict[str, Any]]) -> str | None:
    """Имя DSH-инструмента для встроенного `tool` (сначала то же имя)."""
    for name in (tool, *NATIVE_TOOL_ALIASES.get(tool.lower(), ())):
        if name in schemas:
            return name
    for pattern in NATIVE_TOOL_NAME_PATTERNS.get(tool.lower(), ()):
        for name in schemas:
            if pattern in name.lower():
                return name
    return None


def _native_to_tool_calls(tool: Any, args: Any, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Вызов встроенного инструмента opencode -> список {"name","arguments"} DSH.

    Пустой список — у инструмента нет DSH-двойника в текущем запросе (или
    аргументы не приводятся к его схеме). multiedit даёт несколько edit.
    """
    if not isinstance(tool, str) or not isinstance(args, dict):
        return []
    schemas = _tool_schemas(tools)
    low = tool.lower()
    if low in ("list", "ls") and tool not in schemas:
        path = str(args.get("path") or ".")
        if "bash" in schemas:
            fitted = _fit_args("bash", {"command": f"ls -la {shlex.quote(path)}"}, schemas["bash"])
            if fitted is not None:
                return [{"name": "bash", "arguments": fitted}]
        if "glob" in schemas:
            fitted = _fit_args("glob", {"pattern": "*", "path": path}, schemas["glob"])
            if fitted is not None:
                return [{"name": "glob", "arguments": fitted}]
        return []
    if low == "multiedit" and tool not in schemas:
        target = _pick_target("edit", schemas)
        edits = args.get("edits")
        if target is None or not isinstance(edits, list) or not edits:
            return []
        calls: list[dict[str, Any]] = []
        for edit in edits:
            if not isinstance(edit, dict):
                return []
            merged = {"filePath": args.get("filePath"), **{k: v for k, v in edit.items() if v is not None}}
            fitted = _fit_args(target, merged, schemas[target])
            if fitted is None:
                return []
            calls.append({"name": target, "arguments": fitted})
        return calls
    target = _pick_target(tool, schemas)
    if target is None:
        return []
    fitted = _fit_args(target, args, schemas[target])
    return [] if fitted is None else [{"name": target, "arguments": fitted}]


def _native_to_tool_call(tool: Any, args: Any, tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Совместимость: первый DSH-вызов для встроенного инструмента или None."""
    calls = _native_to_tool_calls(tool, args, tools)
    return calls[0] if calls else None


def _unavailable_tools_prompt(prompt: str, partial_text: str, unavailable: list[str],
                              tools: list[dict[str, Any]], model_id: str = "") -> str:
    """Промпт повтора: встроенный инструмент без DSH-двойника отклонён, продолжай DSH-инструментами."""
    open_tag, close_tag = _tool_tags_for_model(model_id)
    names = ", ".join(_tool_schemas(tools)) or "(none)"
    rejected = ", ".join(sorted({str(t) for t in unavailable}))
    parts = [prompt]
    if partial_text.strip():
        parts.append(f"Assistant: {partial_text.strip()}")
    parts.append(
        "[system]\n"
        f"Your call to the built-in tool(s) {rejected} was rejected: such a tool does not exist in "
        "this environment and nothing was executed. Do not call it again. Continue the same task "
        f"right now using ONLY the caller's tools: {names}. Emit the call as a block "
        f'{open_tag}{{"name": "<tool_name>", "arguments": {{<json matching its parameters>}}}}'
        f"{close_tag} (schemas are in the Tool calling protocol section above). "
        "If the task is already complete, give the final answer in plain text instead."
    )
    return "\n\n".join(parts)


# 2026-10-24: ECONNRESET посреди шага glm-5.3-flash-free. `opencode run` сам запускал 2-й шаг
# (SYNTHETIC «The previous response was interrupted…»), модель отвечала «I was interrupted right
# before making tool calls…», текст склеивался с преамбулой, а шаг кончался `stop` без вызовов.
_INTERRUPTED_RE = re.compile(
    r"I was interrupted right before making tool calls\.?(?:\s*Continue\b[^\n]*)?|"
    r"The previous response was interrupted\.\s*Continue from where you left off without repeating "
    r"completed content\.?",
    re.IGNORECASE)
_INTERRUPT_MARKERS = ("interrupted right before making tool calls", "previous response was interrupted")
# Сырой вызов `<tool_call>{…` / `<tool_invoke>{…`: не inline-код markdown и не упоминание тега в прозе.
_RAW_CALL_RE = re.compile(r"(?<!`)<(?:tool_call|tool_invoke)>\s*(?:(?:```|~~~)\w*\s*)?\{")
# Модель явно сказала, что отвечает без инструментов.
_NO_TOOLS_RE = re.compile(
    r"\bno tools?\b|\bwithout (?:any )?tools?\b|\bno need\b|\bnot (?:needed|required|necessary)\b|"
    r"\brule 0\b|правило 0|не требует инструмент|без инструмент|инструмент\w* не нужн",
    re.IGNORECASE)
# Намерение немедленного действия (преамбула шага без `<tool_call>`): явный глагол действия.
_ACTION_INTENT_RE = re.compile(
    r"\b(?:забираю|читаю|собираю|правлю|проверяю|запускаю|выполняю|запрашиваю|стартую|продолжаю|начинаю|"
    r"вызываю|смотрю|ищу|обновляю|посмотрим|посмотрю|прочитаю|проверю|запущу|соберу|выполню|открою)\b|"
    r"\b(?:следующим|вторым)\s+шагом\b|"
    r"параллельн\w*\s+вызов|🕐\s*\[|"
    r"\blet me (?:check|read|look|run|fetch|collect|gather|see|grab|update|fix|search|batch)\b|"
    r"\blet'?s (?:check|read|look|run|fetch|collect|gather|see|grab|update|fix|search)\b|"
    r"\bi(?:'ll| will) (?:check|read|look|run|fetch|collect|gather|update|fix|search)\b|"
    r"\b(?:collecting|checking|reading|running|fetching|gathering|updating|searching)\b",
    re.IGNORECASE)
_PROMISE_RE = _ACTION_INTENT_RE  # прежнее имя
# Финальный вывод/ответ (а не преамбула шага): заголовок-вывод в начале текста или фраза-итог.
_FINAL_CONCLUSION_RE = re.compile(
    r"^[\s*#>_`\-]*(?:итог(?:о|и)?|ответ|результат(?:ы)?|резюме|заключение|"
    r"summary|conclusion|answer|result|done|готово)\b|"
    r"\b(?:ошибок нет|нет ошибок|всё в порядке|все в порядке|так задумано|тесты (?:зел[её]ные|прошли)|"
    r"no errors?|all (?:good|tests pass\w*)|everything is fine)\b",
    re.IGNORECASE)
# План пачки вызовов в reasoning текущего шага.
_REASONING_TOOL_PLAN_RE = re.compile(
    r"let me batch|all in batch|\bone message\s*:|\bin one (?:message|batch|turn)\b|parallel calls|"
    r"\bcalls? in parallel\b|\bthen (?:both )?(?:tool )?calls\b|making tool calls|"
    r"\btool calls? (?:now|next|in parallel)\b|"
    r"\bemit (?:the )?(?:tool[_\s]?(?:call|invoke)?\s*)?blocks?\b|\btool[_\s]?(?:call|invoke)?\s*blocks?\b|"
    r"\bcall (?:the )?tools\b|\btwo independent calls\b|\bindependent calls\b",
    re.IGNORECASE)
_PLAN_RE = _REASONING_TOOL_PLAN_RE  # прежнее имя
# Мышление, где модель пишет «I need to call job_output…» без готовой фразы-плана.
_CALL_INTENT_RE = re.compile(
    r"\b(?:call|invoke|emit|parallel|batch|need to|let me|i'll|i will|should)\b", re.IGNORECASE)
# Апстрим вырезал `<tool_call>…</tool_call>` из text, но токены в step_finish остались: столько
# лишних токенов над оценкой видимого текста — признак проглоченного вызова.
SWALLOWED_TOKENS_MIN = 35
INCOMPLETE_STEP_MAX_TEXT = 1200  # дольше — это ответ, а не статусная преамбула
INCOMPLETE_STEP_TAIL = 400
TAIL_REMINDER_MIN_CHARS = 4000
SWALLOWED_MAX_TEXT = 600   # признак 3
PLAN_MAX_TEXT = 600        # признак 4
PREAMBLE_MAX_CHARS = 420   # признак 5
PREAMBLE_MAX_LINES = 6
PREAMBLE_SHORT_CHARS = 220

# Mid-stream `etype == "error"`: транзиентные сбои (повторяем) против детерминированных (Fail-Closed).
_FATAL_STREAM_STATUSES = (400, 401, 403, 404, 422)
_TRANSIENT_ERROR_MARKERS = (
    "econnreset", "etimedout", "timeout", "timed out", "socket hang up", "interrupted", "overloaded",
    "rate limit", "temporarily unavailable", "fetch failed", "network", "connection reset", "broken pipe", "eof",
)


def _strip_interrupted(text: str) -> str:
    """Убрать артефакт SYNTHETIC-продолжения opencode («I was interrupted right before…»)."""
    return _INTERRUPTED_RE.sub("", text)


def _has_interrupted_marker(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in _INTERRUPT_MARKERS)


def _is_forced_tool_choice(tool_choice: Any) -> bool:
    return tool_choice == "required" or bool(_tool_choice_name(tool_choice))


def _is_ident_char(char: str) -> bool:
    return char == "_" or (char.isascii() and char.isalnum())


def _mentions_request_tool(text: str, names: Iterable[str]) -> bool:
    """В тексте встречается имя инструмента запроса как отдельный токен (names — имена или схемы).

    Без `re.compile` на горячем пути (H-CPU-I2): граница токена проверяется по соседним символам.
    """
    for name in names:
        if not name:
            continue
        start = text.find(name)
        while start != -1:
            end = start + len(name)
            if (start == 0 or not _is_ident_char(text[start - 1])) and (
                    end == len(text) or not _is_ident_char(text[end])):
                return True
            start = text.find(name, start + 1)
    return False


def _tool_name_list(tools: Any) -> list[str]:
    """Инструменты запроса (OpenAI-схемы или голые имена) -> список имён."""
    names: list[str] = []
    for item in _list_or_empty(tools):
        if isinstance(item, str):
            if item:
                names.append(item)
        elif isinstance(item, dict):
            fn = item.get("function") if isinstance(item.get("function"), dict) else item
            name = fn.get("name") if isinstance(fn, dict) else None
            if isinstance(name, str) and name:
                names.append(name)
    return names


def _is_transient_stream_error(ev: dict[str, Any]) -> bool:
    """Ошибка провайдера посреди стрима транзиентна (повтор имеет смысл)?

    `ev` — сырое событие `{"type":"error","error":{…}}` или разобранный payload `{statusCode, message}`.
    400/401/403/404/422 — детерминированный отказ (False, без повтора, Fail-Closed). Нет статуса, 0, 408,
    429, >=500 либо маркер сетевого сбоя в сообщении — транзиентна (True).
    """
    containers: list[dict[str, Any]] = [ev]
    messages: list[str] = []
    err = ev.get("error")
    if isinstance(err, dict):
        containers.extend([err, _dict_or_empty(err.get("data"))])
    elif isinstance(err, str):
        messages.append(err)
    part = _dict_or_empty(ev.get("part"))
    if part:
        part_err = _dict_or_empty(part.get("error"))
        containers.extend([part, part_err, _dict_or_empty(part_err.get("data"))])
    status: int | None = None
    for container in containers:
        if status is None:
            for key in ("statusCode", "status_code", "status"):
                value = container.get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    status = value
                    break
        for key in ("message", "error"):
            value = container.get(key)
            if isinstance(value, str):
                messages.append(value)
    if status in _FATAL_STREAM_STATUSES:
        return False
    if status is None or status in (0, 408, 429) or status >= 500:
        return True
    low = " ".join(messages).lower()
    return any(marker in low for marker in _TRANSIENT_ERROR_MARKERS)


def _step_recovery_disabled() -> bool:
    """Kill-switch OPENCODE_ZEN_BRIDGE_STEP_RECOVERY (константа модуля и живое значение env)."""
    return not STEP_RECOVERY_ENABLED or os.environ.get(
        "OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1").strip().lower() in ("0", "false", "no", "off")


def _visible_token_estimate(stripped: str) -> int:
    """Грубая оценка токенов видимого текста (верхняя: не завышаем «проглоченные» токены)."""
    return max(len(stripped) // 2, _estimate_tokens(stripped)) if stripped else 0


def _swallowed_tokens(stripped: str, output_tokens: int, reasoning_tokens: int = 0) -> int:
    """Токены вывода, не объяснённые видимым текстом: output включает reasoning — вычитаем его."""
    if reasoning_tokens > 0 and output_tokens >= reasoning_tokens:
        non_reasoning_output = max(0, output_tokens - reasoning_tokens)
    else:
        non_reasoning_output = output_tokens
    return non_reasoning_output - _visible_token_estimate(stripped)


def _is_status_preamble(stripped: str, names: list[str]) -> bool:
    """Признак 5: короткая статусная преамбула с явным глаголом немедленного действия, без вывода/кода/таблиц."""
    if not stripped or len(stripped) > PREAMBLE_MAX_CHARS or stripped.endswith("?"):
        return False
    if len(stripped.splitlines()) > PREAMBLE_MAX_LINES:
        return False
    if "```" in stripped or "~~~" in stripped or _TABLE_SEP_RE.search(stripped):
        return False
    if _FINAL_CONCLUSION_RE.search(stripped) or not _ACTION_INTENT_RE.search(stripped):
        return False
    if stripped.endswith((":", "...", "…")):
        return True
    return len(stripped) <= PREAMBLE_SHORT_CHARS and _mentions_request_tool(stripped, names)


def _no_tools_overridden(body: str, thought: str, names: Iterable[str]) -> bool:
    """Цитата «Rule 0 / no tools» в reasoning не отменяет вызовы, если дальше модель их планирует.

    Да — когда видимый текст обещает действие, либо хвост reasoning содержит план вызовов
    (и там нет нового «no tools»).
    """
    if _ACTION_INTENT_RE.search(body):
        return True
    if _NO_TOOLS_RE.search(thought[-200:]):
        return False
    tail = thought[-400:]
    return bool(_REASONING_TOOL_PLAN_RE.search(thought[-600:])) or (
        _mentions_request_tool(tail, names) and bool(_CALL_INTENT_RE.search(tail)))


def _detect_incomplete_tool_step_signal(text: str, reasoning: str, tools: Any,
                                        had_mid_stream_error: bool = False, output_tokens: int = 0,
                                        reasoning_tokens: int = 0, *, tool_choice: Any = None,
                                        had_error: bool = False) -> int:
    """Номер сработавшего признака оборванного шага (1..5) или 0.

    1 — транзиентная ошибка посреди ответа (или принудительный tool_choice без вызова); 2 — маркер
    «interrupted»/сырой неразобранный вызов; 3 — проглоченные токены; 4 — план вызовов в reasoning
    + обещание в тексте; 5 — узкая преамбула действия (_ACTION_INTENT_RE; голое «:» не триггерит).
    """
    if _step_recovery_disabled():
        return 0
    names = _tool_name_list(tools)
    if not names or _tool_choice_none(tool_choice):
        return 0
    if _is_forced_tool_choice(tool_choice):
        return 1
    body = text.strip()
    thought = reasoning.strip()
    if (had_mid_stream_error or had_error) and (body or thought) and len(body) <= INCOMPLETE_STEP_MAX_TEXT:
        return 1
    if (_INTERRUPTED_RE.search(body) or _has_interrupted_marker(body)
            or _INTERRUPTED_RE.search(thought) or _has_interrupted_marker(thought)
            or _RAW_CALL_RE.search(text)):
        return 2
    if len(body) > INCOMPLETE_STEP_MAX_TEXT:
        return 0
    if _NO_TOOLS_RE.search(thought if thought else body) and not (
            thought and _no_tools_overridden(body, thought, names)):
        return 0
    if (len(body) <= SWALLOWED_MAX_TEXT and output_tokens > 0 and not body.endswith("?") and (body or thought)
            and _swallowed_tokens(body, output_tokens, reasoning_tokens) >= SWALLOWED_TOKENS_MIN):
        return 3
    if thought and len(body) <= PLAN_MAX_TEXT:
        tail = body[-INCOMPLETE_STEP_TAIL:]
        has_plan = bool(_REASONING_TOOL_PLAN_RE.search(thought)) or (
            _mentions_request_tool(thought, names)
            and bool(_ACTION_INTENT_RE.search(thought) or _CALL_INTENT_RE.search(thought)))
        has_promise = not body or (not body.endswith("?") and (
            bool(_ACTION_INTENT_RE.search(tail)) or _mentions_request_tool(tail, names)))
        if has_plan and has_promise:
            return 4
    return 5 if _is_status_preamble(body, names) else 0


def _is_incomplete_tool_step(text: str, reasoning: str, tools: Any,
                             had_mid_stream_error: bool = False, output_tokens: int = 0,
                             reasoning_tokens: int = 0, *, tool_choice: Any = None,
                             had_error: bool = False) -> bool:
    """Шаг без `<tool_call>`/`<tool_invoke>` оборвался или остановился на преамбуле — нужен повтор.

    Обёртка над `_detect_incomplete_tool_step_signal`: обычный ответ, в т.ч. «no tools», короткий итог
    и длинный итог, — False. Выключается kill-switch'ем STEP_RECOVERY_ENABLED первой же инструкцией.
    """
    return bool(_detect_incomplete_tool_step_signal(
        text, reasoning, tools, had_mid_stream_error, output_tokens, reasoning_tokens,
        tool_choice=tool_choice, had_error=had_error))


def _incomplete_step_signal(*args: Any, **kwargs: Any) -> int:
    """Номер признака для повтора шага (0 — повтор не нужен): решает `_is_incomplete_tool_step`, причина — для лога."""
    if not _is_incomplete_tool_step(*args, **kwargs):
        return 0
    return _detect_incomplete_tool_step_signal(*args, **kwargs) or 1


def _incomplete_tool_step_prompt(prompt: str, partial_text: str, tools: list[dict[str, Any]],
                                 tool_choice: Any = None, model_id: str = "") -> str:
    """Промпт повтора: шаг оборвался/остановился на преамбуле — выдай запланированные вызовы."""
    open_tag, close_tag = _tool_tags_for_model(model_id)
    names = ", ".join(_tool_schemas(tools)) or "(none)"
    parts = [prompt]
    partial = _strip_broken_tool_blocks(_strip_interrupted(partial_text), quiet=True)[0].strip()
    if partial:
        parts.append(f"Assistant: {partial}")
    forced = ""
    if tool_choice == "required":
        forced = " You MUST call at least one tool now."
    elif _tool_choice_name(tool_choice):
        forced = f' You MUST call the tool "{_tool_choice_name(tool_choice)}" now.'
    parts.append(
        "[system]\n"
        "Your previous reply was interrupted or ended after a status preamble without any tool call "
        "block, so nothing was executed. Do not repeat text you already wrote, do not apologize and "
        "do not add meta-comments. "
        f'If you planned tool calls, start your reply immediately with {open_tag}{{"name": and output '
        f'NOW ONLY the block(s) {open_tag}{{"name": "<tool_name>", "arguments": '
        f"{{<json matching its parameters>}}}}{close_tag} using ONLY these tools: {names}.{forced} "
        "If no tool is needed, continue the answer in plain text from where it stopped."
    )
    return "\n\n".join(parts)


def _tools_tail_reminder(history: str, tools: list[dict[str, Any]], tool_choice: Any = None,
                         model_id: str = "") -> str:
    """Хвостовое напоминание протокола для длинной истории (секция протокола — за сотни КБ до конца).

    Пусто, если история короткая и без смены модели/нескольких реплик assistant.
    """
    open_tag, close_tag = _tool_tags_for_model(model_id)
    if not tools or _tool_choice_none(tool_choice) or not (
            len(history) >= TAIL_REMINDER_MIN_CHARS or "[model changed:" in history
            or history.count("Assistant:") >= 2):
        return ""
    names = ", ".join(_tool_schemas(tools)) or "(none)"
    forced = ""
    if tool_choice == "required":
        forced = " You MUST call at least one tool now."
    elif _tool_choice_name(tool_choice):
        forced = f' You MUST call the tool "{_tool_choice_name(tool_choice)}" now.'
    return (
        "[system]\n"
        "Tool calling reminder (protocol is described at the top of this prompt). "
        f"Available tools: {names}.\n"
        "If the next step needs a tool, or your reply says that you are now reading, checking, "
        "collecting, fixing or running something, you MUST output the block(s) "
        f'{open_tag}{{"name": "<tool_name>", "arguments": {{<json>}}}}{close_tag} '
        "in this same reply right after a short preamble. Stopping after a status preamble without a "
        f"{open_tag} block is forbidden: nothing gets executed and the turn is lost.{forced} "
        "If no tool is needed, answer in plain text."
    )


def _call_key(name: str, arguments: Any) -> str:
    """Ключ дедупликации вызова в пределах одного ответа."""
    return name + "\x00" + json.dumps(arguments, ensure_ascii=False, sort_keys=True)


def _drain_stderr(proc: subprocess.Popen[str], sink: list[str]) -> None:
    """Вычитать stderr дочернего процесса построчно в `sink` (до EOF)."""
    try:
        assert proc.stderr is not None
        for line in proc.stderr:
            line = line.strip()
            if line:
                sink.append(line)
    except (OSError, ValueError):
        pass


def _stop_proc(proc: subprocess.Popen[str]) -> None:
    """Остановить группу `opencode run` (SIGTERM -> SIGKILL); процесс запущен со start_new_session."""
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass


_STDOUT_POLL_S = 0.25


class _StdoutFeed:
    """Строки stdout дочернего процесса через ограниченную очередь: ожидание не блокируется навсегда.

    Читатель — daemon-поток; без него `for raw in proc.stdout` не возвращает управление, пока CLI
    молчит, и ни дедлайн, ни keepalive не срабатывают. `timed_out` выставляется, когда `lines()`
    остановился по дедлайну (вызывающий сам останавливает процесс). Очередь ограничена `maxsize`:
    на `queue.Full` читатель не роняет данные молча — ставит `overflowed`, считает `dropped_total`,
    останавливает процесс (`_stop_proc`) и выходит; попытка считается неуспешной.
    """

    def __init__(self, proc: subprocess.Popen[str], maxsize: int | None = None) -> None:
        self._proc = proc
        self._queue: queue.Queue[str] = queue.Queue(maxsize=STDOUT_QUEUE_MAX if maxsize is None else maxsize)
        self.timed_out = False
        self.overflowed = False
        self.dropped_total = 0
        self._error: BaseException | None = None
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self) -> None:
        try:
            assert self._proc.stdout is not None
            for raw in self._proc.stdout:
                try:
                    self._queue.put_nowait(raw)
                except queue.Full:
                    self.dropped_total += 1
                    self.overflowed = True
                    _log(f"stdout_overflow queue_max={self._queue.maxsize} dropped_total={self.dropped_total}, "
                         "stopping opencode run")
                    _stop_proc(self._proc)
                    break
        except (OSError, ValueError) as exc:
            self._error = exc
        finally:
            self._done.set()  # после всех put: потребитель, увидев флаг, дочитывает остаток очереди

    def lines(self, deadline: float, idle_s: float = 0.0,
              on_idle: Callable[[], None] | None = None) -> Iterator[str]:
        """Строки до EOF, переполнения или дедлайна; `on_idle` вызывается, если строк нет дольше `idle_s` (0 — выкл.)."""
        last_activity = time.monotonic()
        while True:
            if self.overflowed:
                return
            now = time.monotonic()
            if now >= deadline:
                self.timed_out = True
                return
            wait = deadline - now
            if idle_s > 0 and on_idle is not None:
                wait = min(wait, max(last_activity + idle_s - now, 0.0))
            try:
                item = self._queue.get(timeout=min(max(wait, 0.001), _STDOUT_POLL_S))
            except queue.Empty:
                if self._done.is_set():
                    try:
                        item = self._queue.get_nowait()
                    except queue.Empty:
                        if self._error is not None:
                            raise self._error from None
                        return
                else:
                    now = time.monotonic()
                    if idle_s > 0 and on_idle is not None and now - last_activity >= idle_s:
                        on_idle()
                        last_activity = now
                    continue
            last_activity = time.monotonic()
            if last_activity > deadline:
                self.timed_out = True
                return
            yield item

    def close(self) -> None:
        """Закрыть stdout, если читатель вышел: close() при блокированном чтении виснет на замке буфера."""
        if self._thread.is_alive():
            return
        try:
            if self._proc.stdout is not None:
                self._proc.stdout.close()
        except OSError:
            pass

    def join(self, timeout: float) -> None:
        self._thread.join(timeout=timeout)


def _model_route(model_id: str) -> str:
    """Полный CLI-id; старые записи без provider остаются на Zen."""
    provider = ALLOWED_MODELS.get(model_id, {}).get("provider", "opencode")
    return f"{provider}/{model_id}"


def _is_zen_route(model_id: str) -> bool:
    """Zen-модель каталога (провайдер opencode, без своего base_url); Go-маршруты не затрагиваются."""
    meta = ALLOWED_MODELS.get(model_id, {})
    return meta.get("provider", "opencode") == "opencode" and not meta.get("base_url")


def _uses_standalone(model_id: str) -> bool:
    """`opencode run --standalone`: только Zen-модели и только в динамическом режиме каталога."""
    return CATALOG_MODE == "dynamic" and _is_zen_route(model_id)


_PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")
_LOOPBACK_NO_PROXY = ("127.0.0.1", "localhost", "::1")
# THREAT-003 + принятое отклонение DEV-02: к ключам пакета добавлены переменные прокси.
_STANDALONE_ENV_ALLOWLIST = (
    "PATH", "HOME", "TMPDIR", "LANG",
    "NO_PROXY", "no_proxy",
    *_PROXY_VARS,
)


def _merged_no_proxy(current: str) -> str:
    """NO_PROXY с обязательными loopback-адресами (локальные вызовы идут мимо прокси)."""
    parts = [p.strip() for p in current.split(",") if p.strip()]
    parts.extend(p for p in _LOOPBACK_NO_PROXY if p not in parts)
    return ",".join(parts)


# Пул выделенных US-портов ProxyRack: каждый порт 10000..10999 даёт отдельный чистый IP, а анонимный
# лимит opencode.ai (36 запросов в сутки на исходящий IP) считается по IP. Режим `pool` берёт
# порты по кругу — по одному на каждый запуск дочернего процесса (включая ретраи).
_DEFAULT_PROXYRACK_FILE = Path.home() / ".local/share/gigaexplorator-proxies/2026-08-31-volkov-proxy-manager/06-proxyrack-global-dc-1000.txt"
_PROXYRACK_FORWARD_LOG = Path.home() / "Library/Logs/Factory/proxyrack-forward.log"
_DEFAULT_PROXYRACK_GATEWAY = "121.91.235.6"
_PROXYRACK_LOG_TAIL_BYTES = 16 * 1024
_IPV4_RE = re.compile(r"^(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$")

_proxy_pool_lock = threading.Lock()
_proxy_pool_key: tuple[Any, ...] | None = None
_proxy_pool_entries: list[str] = []
_proxy_pool_idx = 0


def _resolve_proxyrack_gateway() -> str:
    """IP живого шлюза ProxyRack: env -> последняя запись лога proxyrack-forward -> значение по умолчанию.

    Прямой DNS global.rotating.proxyrack.net иногда отдаёт нерабочие 149.51.*; демон
    proxyrack-forward проверяет адреса пробой и пишет живой в лог (`gateway <old> -> <new>`).
    """
    forced = os.environ.get("OPENCODE_ZEN_BRIDGE_PROXYRACK_GATEWAY", "").strip()
    if forced:
        return forced
    try:
        with _PROXYRACK_FORWARD_LOG.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - _PROXYRACK_LOG_TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return _DEFAULT_PROXYRACK_GATEWAY
    for line in reversed(tail.splitlines()):
        if "proxyrack-forward gateway " not in line or " -> " not in line:
            continue
        candidate = line.rsplit(" -> ", 1)[1].strip()
        if _IPV4_RE.match(candidate) and not candidate.startswith("149.51."):
            return candidate
        break
    return _DEFAULT_PROXYRACK_GATEWAY


def _parse_proxy_pool_line(line: str, gateway: str) -> str | None:
    """`user:pass@host:port` или `host:port:user:pass` -> `http://user:pass@<gateway>:port` (host заменяется шлюзом)."""
    line = line.strip()
    if "@" in line:
        creds, _, hostport = line.rpartition("@")
        user, sep, password = creds.partition(":")
        port = hostport.rpartition(":")[2]
    else:
        parts = line.split(":", 3)
        if len(parts) != 4:
            return None
        _, port, user, password = parts
        sep = ":"
    if not (sep and user and password and port.isdigit()):
        return None
    return f"http://{quote(user, safe='')}:{quote(password, safe='')}@{gateway}:{port}"


def _next_standalone_proxy() -> str | None:
    """Прокси для очередного standalone-запуска: None | явный URL | следующий порт пула (по кругу)."""
    global _proxy_pool_key, _proxy_pool_entries, _proxy_pool_idx
    raw_proxy = os.environ.get("OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY", "").strip()
    if not raw_proxy:
        return None
    if raw_proxy != "pool":
        return raw_proxy
    pool_path = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_PROXYRACK_FILE", str(_DEFAULT_PROXYRACK_FILE)))
    gateway = _resolve_proxyrack_gateway()
    offset = os.environ.get("OPENCODE_ZEN_BRIDGE_PROXYRACK_OFFSET", "")
    try:
        st = os.stat(pool_path)
    except OSError:
        return None
    key = (str(pool_path), st.st_mtime_ns, st.st_size, gateway, offset)
    with _proxy_pool_lock:
        if key != _proxy_pool_key:
            try:
                lines = pool_path.read_text("utf-8", errors="replace").splitlines()
            except OSError:
                return None
            entries = [e for e in (_parse_proxy_pool_line(ln, gateway) for ln in lines if ln.strip()) if e]
            if not entries:
                return None
            _proxy_pool_key = key
            _proxy_pool_entries = entries
            try:
                start = int(offset) if offset.strip() else int(time.time() * 1000)
            except ValueError:
                start = int(time.time() * 1000)
            _proxy_pool_idx = start % len(entries)
        entry = _proxy_pool_entries[_proxy_pool_idx % len(_proxy_pool_entries)]
        _proxy_pool_idx += 1
        return entry


def _reset_proxy_pool_for_tests() -> None:
    """Сбросить кэш и индекс пула прокси."""
    global _proxy_pool_key, _proxy_pool_entries, _proxy_pool_idx
    with _proxy_pool_lock:
        _proxy_pool_key = None
        _proxy_pool_entries = []
        _proxy_pool_idx = 0


def _run_env(model_id: str = "") -> dict[str, str]:
    """Окружение CLI с отдельным конфигом маршрута для Go-моделей и свежим каталогом для Zen."""
    env = dict(os.environ)
    env.setdefault("PATH", "/Users/aazhiry1/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    if OPENCODE_CONFIG_CONTENT:
        env["OPENCODE_CONFIG_CONTENT"] = OPENCODE_CONFIG_CONTENT
    if ALLOWED_MODELS.get(model_id, {}).get("base_url"):
        for name in _PROXY_VARS:
            env.pop(name, None)
        env["NO_PROXY"] = "127.0.0.1,localhost"
        env["OPENCODE_CONFIG"] = str(Path(__file__).resolve().parent / "opencode-go.json")
    elif _uses_standalone(model_id):
        # THREAT-003: окружение standalone-вызова собирается строго по белому списку, а не из
        # полного os.environ — посторонние секреты родителя в дочерний opencode не попадают.
        # OPENCODE_API_KEY удаляется явно: истёкший ключ даёт 401 (для free Zen-моделей он не нужен).
        env = {k: os.environ[k] for k in _STANDALONE_ENV_ALLOWLIST if k in os.environ}
        env.setdefault("PATH", "/Users/aazhiry1/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin")
        if OPENCODE_CONFIG_CONTENT:
            env["OPENCODE_CONFIG_CONTENT"] = OPENCODE_CONFIG_CONTENT
        # Прокси сохраняется: без него приватный сервер получает RegionError («not available in
        # your country», проверено 2026-10-24 на beam-free) и анонимный лимит с локального IP.
        # Ротирующий прокси (OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY: URL или `pool`) даёт каждому новому
        # дочернему процессу чистый IP и обходит 429 FreeUsageLimitError на фиксированном IP.
        # Loopback идёт мимо.
        standalone_proxy = _next_standalone_proxy()
        if standalone_proxy:
            for name in _PROXY_VARS:
                env[name] = standalone_proxy
        no_proxy = _merged_no_proxy(env.get("NO_PROXY") or env.get("no_proxy") or "")
        env["NO_PROXY"] = no_proxy
        env["no_proxy"] = no_proxy
        if Path(OPENCODE_MODELS_PATH).is_file():
            env["OPENCODE_MODELS_PATH"] = OPENCODE_MODELS_PATH
            env["OPENCODE_DISABLE_MODELS_FETCH"] = "1"
    else:
        for name in _PROXY_VARS:
            env.pop(name, None)
        env["NO_PROXY"] = "127.0.0.1,localhost"
    return env


def _variant_for(model_id: str, effort: str) -> str:
    """`#variant` для модели: только если модель их поддерживает и значение допустимо (иначе CLI: exit 1)."""
    meta = ALLOWED_MODELS.get(model_id, {})
    if not effort or not meta.get("supports_variant", False):
        return ""
    values = meta.get("effort_values")
    if values and effort not in values:
        _log(f"WARN variant {effort!r} is not in effort_values of {model_id}; suffix dropped")
        return ""
    return effort


def _build_cmd(launcher: str, model_id: str, effort: str) -> tuple[list[str], str]:
    """Команда `opencode run` и её фрагмент для лога (`-m <id>[#variant] [--standalone] [--thinking]`)."""
    model_route = _model_route(model_id)
    variant = _variant_for(model_id, effort)
    model_spec = f"{model_route}#{variant}" if variant else model_route
    cmd = [launcher, "run", "-m", model_spec]
    if variant:
        cmd.append("--thinking")
    cmd.extend(["--format", "json"])
    shown = f"-m {model_spec}"
    if _uses_standalone(model_id):
        cmd.append("--standalone")
        shown += " --standalone"
    if variant:
        shown += " --thinking"
    return cmd, shown


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Детерминированные отказы провайдера: повтор бессмыслен.
_FATAL_HTTP = {400, 401, 402, 403, 404, 422}


def _clean_err(lines: list[str] | str, limit: int = 600) -> str:
    """Хвост stderr/ошибок CLI без ANSI-раскраски и токеноподобных секретов."""
    text = "\n".join(lines) if isinstance(lines, list) else lines
    text = _ANSI_RE.sub("", text)
    text = "\n".join(part.strip() for part in text.splitlines() if part.strip())
    return _mask_secrets(text)[-limit:]


def _is_retryable_failure(rc: int | None, err_text: str, provider_status: int | None,
                          had_output: bool) -> bool:
    """Прогон без какого-либо вывода и с rc != 0 — транзиторный отказ CLI (повторяем).

    Не повторяем: был вывод; процесс убит нами/таймаутом (rc < 0 или None);
    провайдер вернул детерминированный отказ (400/401/402/403/404/422).
    """
    if had_output or rc is None or rc <= 0:
        return False
    return provider_status not in _FATAL_HTTP


def _error_payload(message: str, detail: str = "") -> dict[str, Any]:
    """Тело OpenAI-style ошибки (SSE-чанк `{"error":…}` и non-stream 502)."""
    err: dict[str, Any] = {"message": message, "type": "proxy_error", "code": 502}
    if detail:
        err["detail"] = detail
    return {"error": err}


class _StartupGate:
    """Сериализует старт `opencode run`: sqlite opencode роняет «database is locked».

    Замок берётся до spawn и отпускается по первому событию stdout, завершению
    процесса или таймеру-предохранителю (STARTUP_GATE_S) — зависший CLI не блокирует остальных.
    Ожидание замка ограничено `wait_s` (STARTUP_WAIT_S): по таймауту — Fail-Open, запуск без замка
    (вспомогательная сериализация; «database is locked» ловит повтор транзиторного отказа CLI).
    """

    def __init__(self, wait_s: float | None = None) -> None:
        self._wait_s = STARTUP_WAIT_S if wait_s is None else wait_s
        self._held = False
        self._guard = threading.Lock()
        self._timer: threading.Timer | None = None

    def acquire(self) -> None:
        if not _STARTUP_LOCK.acquire(timeout=max(0.0, self._wait_s)):
            _log(f"startup_gate_timeout wait_s={self._wait_s:.1f}, starting without the gate")
            return
        with self._guard:
            self._held = True
        timer = threading.Timer(STARTUP_GATE_S, self.release)
        timer.daemon = True
        self._timer = timer
        timer.start()

    def release(self) -> None:
        with self._guard:
            if not self._held:
                return
            self._held = False
            timer, self._timer = self._timer, None
        if timer is not None:
            timer.cancel()
        _STARTUP_LOCK.release()


_STARTUP_LOCK = threading.Lock()
STARTUP_GATE_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_STARTUP_GATE_S", "12"))
STARTUP_WAIT_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_STARTUP_WAIT_S", "5.0"))

_started = time.time()
_active: dict[str, float] = {}
_active_lock = threading.Lock()

_LOG_LOCK = threading.Lock()


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {_mask_secrets(msg)}"
    sys.stderr.write(line + "\n")
    sys.stderr.flush()
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK, LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


class _SlotBulkhead:
    """Слоты параллельных `opencode run` с ограниченным ожиданием (bulkhead).

    Занято `max_concurrent` слотов -> до `max_waiters` запросов ждут не дольше `wait_timeout_s`;
    следующий ждущий получает отказ мгновенно ("overflow"). `in_use` и `waiters` уменьшаются
    в `finally`/`release` на любом выходе (таймаут, исключение, отмена).
    """

    def __init__(self, max_concurrent: int | None = None, max_waiters: int | None = None,
                 wait_timeout_s: float | None = None,
                 clock_fn: Callable[[], float] = time.monotonic) -> None:
        self._max = MAX_CONCURRENT if max_concurrent is None else max_concurrent
        self._max_waiters = MAX_SLOT_WAITERS if max_waiters is None else max_waiters
        self._wait_timeout_s = SLOT_WAIT_TIMEOUT_S if wait_timeout_s is None else wait_timeout_s
        self._clock = clock_fn
        self._cond = threading.Condition(threading.Lock())
        self.in_use = 0
        self.waiters = 0

    def acquire_ex(self, timeout: float | None = None) -> str:
        """"ok" | "timeout" | "overflow" (все слоты заняты и очередь ждущих полна)."""
        wait = self._wait_timeout_s if timeout is None else min(timeout, self._wait_timeout_s)
        with self._cond:
            if self.in_use < self._max:
                self.in_use += 1
                return "ok"
            if self.waiters >= self._max_waiters:
                return "overflow"
            self.waiters += 1
            try:
                deadline = self._clock() + wait
                while self.in_use >= self._max:
                    remaining = deadline - self._clock()
                    if remaining <= 0:
                        return "timeout"
                    self._cond.wait(remaining)
                self.in_use += 1
                return "ok"
            finally:
                self.waiters -= 1

    def acquire(self, timeout: float | None = None) -> bool:
        return self.acquire_ex(timeout) == "ok"

    def release(self) -> None:
        with self._cond:
            if self.in_use > 0:
                self.in_use -= 1
            self._cond.notify()


class _SpawnRateLimiter:
    """Token bucket запусков `opencode run`: не более `rate_rps` запусков в секунду (burst — ёмкость).

    Резервирование токена (GCRA): токен списывается сразу, при дефиците ждущий получает FIFO-очередь
    по моменту резерва; `acquire` возвращает False без резерва, если ожидание превысит `max_wait_s`.
    """

    def __init__(self, rate_rps: float = 1.0, burst: float = 1.0,
                 clock_fn: Callable[[], float] = time.monotonic,
                 sleep_fn: Callable[[float], None] = time.sleep) -> None:
        self._rate = max(rate_rps, 1e-9)
        self._burst = max(burst, 1.0)
        self._clock = clock_fn
        self._sleep = sleep_fn
        self._lock = threading.Lock()
        self._tokens = self._burst
        self._last = clock_fn()

    def acquire(self, max_wait_s: float | None = None) -> bool:
        with self._lock:
            now = self._clock()
            self._tokens = min(self._burst, self._tokens + max(0.0, now - self._last) * self._rate)
            self._last = now
            wait = max(0.0, (1.0 - self._tokens) / self._rate)
            if max_wait_s is not None and wait > max_wait_s:
                return False
            self._tokens -= 1.0
        if wait > 0:
            self._sleep(wait)
        return True


class _RetryBudget:
    """Process-level бюджет повторных запусков: ёмкость `capacity`, +`per_request_refill` за запрос, +`reserve_rps` в секунду."""

    def __init__(self, capacity: float | None = None, per_request_refill: float | None = None,
                 reserve_rps: float | None = None,
                 clock_fn: Callable[[], float] = time.monotonic) -> None:
        self._capacity = RETRY_BUDGET_MAX if capacity is None else capacity
        self._per_request = RETRY_BUDGET_PER_REQUEST if per_request_refill is None else per_request_refill
        self._reserve_rps = RETRY_BUDGET_RESERVE_RPS if reserve_rps is None else reserve_rps
        self._clock = clock_fn
        self._lock = threading.Lock()
        self.tokens = float(self._capacity)
        self._last = clock_fn()

    def _refill_time(self) -> None:
        now = self._clock()
        self.tokens = min(self._capacity, self.tokens + max(0.0, now - self._last) * self._reserve_rps)
        self._last = now

    def on_request(self) -> None:
        """Первичный запрос: +per_request_refill токена (не выше capacity)."""
        with self._lock:
            self._refill_time()
            self.tokens = min(self._capacity, self.tokens + self._per_request)

    def try_acquire_retry(self) -> bool:
        with self._lock:
            self._refill_time()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False


class _UpstreamBreaker:
    """Circuit Breaker зависимости `opencode run`: CLOSED -> OPEN (N подряд транзиентных отказов) -> HALF_OPEN (1 проба)."""

    def __init__(self, fail_threshold: int | None = None, reset_timeout_s: float | None = None,
                 clock_fn: Callable[[], float] = time.monotonic,
                 rng_fn: Callable[[float, float], float] = random.uniform,
                 max_half_open_probes: int = 1,
                 log_fn: Callable[[str], None] | None = None) -> None:
        self._threshold = CB_FAIL_THRESHOLD if fail_threshold is None else fail_threshold
        self._reset_s = CB_RESET_S if reset_timeout_s is None else reset_timeout_s
        self._clock = clock_fn
        self._rng = rng_fn
        self._max_probes = max_half_open_probes
        self._log_fn = log_fn
        self._lock = threading.Lock()
        self._state = "CLOSED"
        self._failures = 0
        self._open_until = 0.0
        self._probes = 0
        self._probe_started = 0.0
        self.max_half_open_probes = max_half_open_probes

    def _say(self, msg: str) -> None:
        (self._log_fn or _log)(msg)

    def _refresh(self, now: float) -> None:
        if self._state == "OPEN" and now >= self._open_until:
            self._state = "HALF_OPEN"
            self._probes = 0
            self._say("circuit_breaker state=HALF_OPEN")

    @property
    def state(self) -> str:
        with self._lock:
            self._refresh(self._clock())
            return self._state

    def is_blocking(self) -> bool:
        """OPEN и cooldown не истёк (без резервирования пробы)."""
        return self.state == "OPEN"

    def allow(self) -> bool:
        """Можно ли запускать `opencode run` (в HALF_OPEN — ровно одна проба; потерянная проба истекает через reset)."""
        with self._lock:
            now = self._clock()
            self._refresh(now)
            if self._state == "CLOSED":
                return True
            if self._state == "OPEN":
                return False
            if self._probes >= self._max_probes and now - self._probe_started < self._reset_s:
                return False
            self._probes = 1 if self._probes >= self._max_probes else self._probes + 1
            self._probe_started = now
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            if self._state != "CLOSED":
                self._state = "CLOSED"
                self._probes = 0
                self._say("circuit_breaker state=CLOSED")

    def record_failure(self) -> None:
        with self._lock:
            now = self._clock()
            self._refresh(now)
            if self._state == "OPEN":
                return
            self._failures += 1
            if self._state == "HALF_OPEN" or self._failures >= self._threshold:
                cooldown = self._reset_s * self._rng(0.8, 1.2)
                self._state = "OPEN"
                self._open_until = now + cooldown
                self._probes = 0
                self._say(f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}")


class _Resilience:
    """Набор process-level защит одного сервера: bulkhead слотов, spawn token bucket, Retry Budget, Breaker.

    В проде один `Server` на процесс (main передаёт модульный `_DEFAULT_RESILIENCE`); тесты создают
    отдельные `Server` и получают изолированные защиты.
    """

    def __init__(self) -> None:
        self.slots = _SlotBulkhead()
        self.spawn_limiter = _SpawnRateLimiter(SPAWN_RATE_PER_S, SPAWN_BURST)
        self.retry_budget = _RetryBudget()
        self.breaker = _UpstreamBreaker()


_DEFAULT_RESILIENCE = _Resilience()
_slots = _DEFAULT_RESILIENCE.slots  # прежнее имя семафора слотов


class _RequestAttempts:
    """Учёт запусков одного HTTP-запроса: потолок MAX_TOTAL_SPAWNS, общий deadline, breaker, Retry Budget, backoff."""

    def __init__(self, res: _Resilience, deadline: float, max_total: int | None = None,
                 sleep_fn: Callable[[float], None] = time.sleep,
                 rng_fn: Callable[[float, float], float] = random.uniform,
                 use_breaker: bool = True) -> None:
        self.res = res
        self.deadline = deadline
        self.use_breaker = use_breaker  # False: прямой Google-маршрут без `opencode run`
        self.max_total = MAX_TOTAL_SPAWNS if max_total is None else max_total
        self.total_spawns = 0
        self.retries = 0
        self.signal = 0
        self.exit_reason = ""
        self._pending_failure = False
        self._sleep = sleep_fn
        self._rng = rng_fn
        res.retry_budget.on_request()

    def note_spawn(self) -> None:
        self.total_spawns += 1

    def remaining_s(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def begin_attempt(self) -> bool:
        """Первичный запуск: потолок, deadline и Circuit Breaker (в HALF_OPEN резервирует единственную пробу)."""
        return (self.total_spawns < self.max_total and time.monotonic() < self.deadline
                and (not self.use_breaker or self.res.breaker.allow()))

    def allow_retry(self, reason: str, charge_budget: bool = True) -> bool:
        """Можно ли сделать повторный запуск: потолок, deadline, breaker, Retry Budget; затем Full Jitter пауза.

        charge_budget=False — локальный отказ старта CLI без обращения к провайдеру («database is locked»):
        он не нагружает апстрим, ограничен FAIL_RETRY_LIMIT, MAX_TOTAL_SPAWNS и темпом запусков.
        """
        if self.total_spawns >= self.max_total:
            _log(f"retry denied ({reason}): MAX_TOTAL_SPAWNS={self.max_total} reached")
            return False
        if time.monotonic() >= self.deadline:
            return False
        if self.use_breaker and self.res.breaker.is_blocking():
            _log(f"retry denied ({reason}): upstream circuit open")
            return False
        if charge_budget and not self.res.retry_budget.try_acquire_retry():
            _log(f"retry denied ({reason}): retry budget exhausted")
            return False
        self.retries += 1
        delay = _retry_backoff_s(self.retries, self._rng) if FAIL_RETRY_BACKOFF_S > 0 else 0.0
        delay = min(delay, self.remaining_s())
        if delay > 0:
            self._sleep(delay)
        return not self.use_breaker or self.res.breaker.allow()

    def attempt_done(self, transient_failure: bool, success: bool) -> None:
        """Итог попытки для Circuit Breaker: успех учитывается сразу, транзиентный отказ — по итогу запроса (commit).

        Запрос, который повтором дошёл до успеха, апстрим не «роняет»; отказ засчитывается, только
        если запрос закончился отказом. Нейтральные итоги (таймаут, детерминированный 4xx) не считаются.
        """
        if not self.use_breaker:
            return
        if success and not transient_failure:
            self._pending_failure = False
            self.res.breaker.record_success()
        else:
            self._pending_failure = transient_failure

    def commit(self) -> None:
        """Итог запроса: незакрытый транзиентный отказ последней попытки -> breaker.record_failure()."""
        if self._pending_failure:
            self._pending_failure = False
            self.res.breaker.record_failure()


class _PrefixDedup:
    """dedup_prefix повторной попытки SSE: уже отданный клиенту префикс подавляется, расхождение — отдаётся целиком.

    `current` — видимый текст новой попытки. Начинается с префикса -> префикс подавлен, дальше идёт
    остаток; не совпал (модель переформулировала) -> префикс сброшен и текст отдан без потерь
    (возможен видимый повтор формулировки — допустимо, потеря — нет).
    """

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.current = ""

    def push(self, text: str) -> str:
        """Фрагмент попытки -> то, что уходит клиенту сейчас (пустая строка — ждём больше текста)."""
        if not self.prefix:
            return text
        self.current += text
        current, prefix = self.current, self.prefix
        if current.startswith(prefix):
            self.prefix = ""
            return current[len(prefix):]
        if len(current) >= len(prefix) or not prefix.startswith(current):
            self.prefix = ""
            return "\n\n" + current
        return ""

    def finish(self) -> str:
        """Конец попытки: накопленный, но неотданный текст (кроме чистого повтора части префикса)."""
        leftover = ""
        if self.prefix and self.current and not self.prefix.startswith(self.current):
            leftover = "\n\n" + self.current
        self.prefix = ""
        return leftover


def _dedup_retry_text(prefix: str, current: str) -> str:
    """JSON-вариант dedup_prefix: подавить уже отданный префикс, переформулированный текст сохранить целиком."""
    if prefix and current.startswith(prefix):
        return current[len(prefix):]
    return current


def _new_exit_state() -> dict[str, Any]:
    return {"t0": time.monotonic(), "mode": "", "model": "", "status": 0, "exit_reason": "",
            "attempts": None, "tools": 0, "out_chars": 0, "rc": None}


def _log_exit(xs: dict[str, Any]) -> None:
    """O-EXIT/v1: одна структурная строка bridge.log на каждый выход Handler.do_POST."""
    attempts = xs.get("attempts")
    status = int(xs.get("status") or 0)
    reason = str(xs.get("exit_reason") or "") or ("ok" if status == 200 else (f"http_{status}" if status else "client_gone"))
    _log(f"O-EXIT/v1 mode={xs.get('mode') or '-'} model={xs.get('model') or '-'} status={status} "
         f"exit_reason={reason} rc={xs.get('rc')} total_spawns={attempts.total_spawns if attempts else 0} "
         f"retries={attempts.retries if attempts else 0} signal={attempts.signal if attempts else 0} "
         f"tools={xs.get('tools') or 0} out_chars={xs.get('out_chars') or 0} "
         f"duration_s={time.monotonic() - float(xs['t0']):.2f}")


def _resolve_launcher() -> str:
    if os.path.isfile(OPENCODE_BIN) and os.access(OPENCODE_BIN, os.X_OK):
        return OPENCODE_BIN
    found = shutil.which("opencode")
    if found:
        _log(f"launcher {OPENCODE_BIN} missing, using PATH opencode={found}")
        return found
    _log(f"launcher {OPENCODE_BIN} missing and opencode not on PATH")
    return OPENCODE_BIN


def _spawn_with_stdin(cmd: list[str], prompt: str, workdir: Path,
                      env: dict[str, str]) -> subprocess.Popen[str]:
    """Запуск `opencode run` с промптом через stdin, а не argv.

    Причина: история чата > ~1 МБ пробивает macOS ARG_MAX — Popen падает
    `OSError: [Errno 7] Argument list too long` (состояние spawn_failed).
    `opencode run` без позиционного message читает промпт из stdin
    (проверено 2026-10-08 на opencode 1.18.32: stdin становится user message).

    stdin=PIPE + поток-писатель: пишет prompt (utf-8) кусками и закрывает
    stdin (EOF), чтобы opencode стартовал. BrokenPipeError/ValueError
    глотаются: дочерний мог выйти раньше (напр. остановка через _stop_proc
    при tool call, или ранний отказ) — это наблюдают читатели stdout/stderr.
    """
    proc = subprocess.Popen(
        cmd, cwd=str(workdir), env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
        start_new_session=True,
    )

    def _feed() -> None:
        try:
            assert proc.stdin is not None
            step = 65536
            for off in range(0, len(prompt), step):
                proc.stdin.write(prompt[off:off + step])
            proc.stdin.close()
        except (OSError, ValueError):
            pass

    threading.Thread(target=_feed, daemon=True, name="opencode-stdin-feed").start()
    return proc


def _token_eq(candidate: str, expected: str) -> bool:
    """Сравнение секретов за константное время (не `==`: без утечки по таймингу)."""
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    hdr = handler.headers.get("Authorization", "")
    if hdr.startswith("Bearer "):
        return _token_eq(hdr[7:].strip(), AUTH_KEY)
    return _token_eq(handler.headers.get("x-api-key", ""), AUTH_KEY) or _token_eq(hdr.strip(), AUTH_KEY)


def _flatten_content(content: Any) -> str:
    """OpenAI content (str | list[part]) -> plain text."""
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
                if "text" in item:
                    parts.append(str(item["text"]))
                elif item.get("type") == "image_url":
                    parts.append("[image omitted]")
        return "\n".join(p for p in parts if p)
    return str(content)


_SECRET = re.compile(
    r"(?<![A-Za-z0-9_\-])(?:st_|rt_|sk-|fk-)[A-Za-z0-9_\-]{8,}"
    r"|(?<![A-Za-z0-9_\-])"
    r"(?!(?:gemini-|mimo-|muse-|longcat-|deepseek-|claude-|opencode-|nemotron-|minimax-|beam-|glm-|qwen|chatcmpl-|call_|session-|org_|user_|acc_|wrk_))"
    r"[A-Za-z0-9_\-]{24,}"
)


def _mask_secrets(text: str) -> str:
    """Длинные токеноподобные последовательности -> ***; id моделей каталога и алиасов не маскируются."""
    def keep_model_ids(match: re.Match[str]) -> str:
        token = match.group(0)
        return token if token in ALLOWED_MODELS or token in MODEL_ALIASES else "***"

    return _SECRET.sub(keep_model_ids, text)


_MAX_EXTRA_BRACES = 16  # предел лишних `}` после полного объекта вызова


def _recover_trailing_braces(text: str, strict: bool, quiet: bool = False) -> dict[str, Any] | None:
    """Первый JSON-объект, за которым идут только пробелы и 1..16 лишних `}`; иначе None (холодный путь)."""
    body = text.lstrip()
    try:
        obj, end = json.JSONDecoder(strict=strict).raw_decode(body)
    except (ValueError, RecursionError):
        return None
    tail = body[end:]
    extra = tail.count("}")
    if isinstance(obj, dict) and 1 <= extra <= _MAX_EXTRA_BRACES and not tail.strip(" \t\r\n}"):
        if not quiet:
            _log(f"tool_call_recovered extra_braces={extra}")
        return obj
    return None


def _loads_lenient(text: str, *, quiet: bool = False) -> Any:
    """json.loads с допуском сырых управляющих символов (\\n, \\t) внутри строк и лишних `}` в хвосте.

    Порт из droid-bridge (08.10): модели кладут многострочные команды в JSON-строку
    без экранирования переводов строк; строгий json.loads их отвергает, и вызов
    утекал в content текстом. Сначала строгий разбор, затем strict=False, затем
    полный объект с хвостом из пробелов и `}` (модель закрыла скобок больше нужного).
    Слишком глубокая вложенность (RecursionError) — это тоже невалидный JSON (ValueError).
    """
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        pass
    try:
        return json.loads(text, strict=False)
    except (ValueError, RecursionError) as exc:
        recovered = _recover_trailing_braces(text, strict=False, quiet=quiet)
        if recovered is None:
            if isinstance(exc, RecursionError):
                raise ValueError("JSON is nested too deeply") from exc
            raise
        return recovered


def _normalize_arguments(value: Any) -> dict[str, Any] | None:
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
                parsed = _loads_lenient(text)
            except ValueError:
                return None
            if isinstance(parsed, dict):
                return parsed
    return None


def _normalize_tool_call(item: Any) -> dict[str, Any]:
    """Один OpenAI tool_call -> {"id", "name", "arguments"}.

    id сохраняется, чтобы результат [tool result <id>] однозначно сопоставлялся
    с конкретным вызовом при нескольких одинаковых инструментах.
    """
    if not isinstance(item, dict):
        return {"id": "", "name": "", "arguments": {}}
    fn = _dict_or_empty(item.get("function"))
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
    fn = _dict_or_empty(tool_choice.get("function"))
    name = fn.get("name") or tool_choice.get("name") or ""
    return str(name) if name else ""


def _tools_section(tools: list[Any], tool_choice: Any, model_id: str = "") -> str:
    """Английская секция протокола и схем инструментов для промпта."""
    open_tag, close_tag = _tool_tags_for_model(model_id)
    # у GLM подстрока `tool_call` в промпте провоцирует нативный спец-токен
    block_name = "tool_invoke" if _uses_alt_tool_tag(model_id) else "tool_call"
    lines = [
        "[system]",
        "# Tool calling protocol",
        "You may call the external tools listed below.",
        "When you need a tool, output ONLY blocks exactly in this form:",
        f'{open_tag}{{"name": "<tool_name>", "arguments": {{<json>}}}}{close_tag}',
        "You may output several such blocks in a row. Do not narrate around them.",
        "Tool results arrive later as lines like [tool result <id>] with the result text.",
        "If no tool is needed, reply normally in plain text.",
        "Never attempt to use built-in tools; the only tools available are the ones listed here.",
        f"Do not run shell commands or edit files yourself: emit a {block_name} block instead.",
        (
            f"If a tool is needed, you MUST emit the {block_name} block in this reply; prose claims "
            "like \"I'll check...\" without a block are forbidden and end the turn with no action."
        ),
        "The block itself changes nothing: the caller executes the tool and sends back the result.",
    ]
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
        params = _dict_or_empty(fn.get("parameters"))
        lines.append(f"- {name}: {desc}")
        lines.append("  parameters: " + json.dumps(params, ensure_ascii=False))
    return "\n".join(lines)


def _render_turn(msg: dict[str, Any]) -> tuple[str, str]:
    """Одна реплика истории -> (role, текст); пустой текст = пропустить.

    assistant.tool_calls и role:"tool" рендерятся в те же блоки, что протокол.
    """
    role = str(msg.get("role") or "user").strip().lower()
    text = _flatten_content(msg.get("content"))
    if role == "tool":
        call_id = str(msg.get("tool_call_id") or msg.get("id") or "")
        name = str(msg.get("name") or "")
        header = f"[tool result {call_id}]"
        if name:
            header += f" ({name})"
        return role, f"{header}\n{text}" if text.strip() else header
    if role == "assistant":
        text = _sanitize_assistant_text(text)
        parts = [text] if text.strip() else []
        calls = msg.get("tool_calls")
        if isinstance(calls, list):
            parts.extend(_render_tool_call(tc) for tc in calls)
        return role, "\n".join(parts)
    return role, text


def _messages_to_prompt(messages: list[dict[str, Any]]) -> tuple[str, str]:
    """История OpenAI -> (system_text, размеченный текст реплик)."""
    systems: list[str] = []
    turns: list[str] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role, text = _render_turn(msg)
        if not text.strip():
            continue
        if role in ("system", "developer"):
            systems.append(text)
        elif role == "assistant":
            turns.append(f"Assistant: {text}")
        elif role == "tool":
            turns.append(text)
        else:
            turns.append(f"User: {text}")
    return "\n\n".join(systems).strip(), "\n\n".join(turns)


def _strip_code_fence(text: str) -> str:
    """Снять обёртку ```…``` или ~~~…~~~ (в т.ч. ```json) вокруг JSON внутри блока."""
    body = text.strip()
    if body.startswith(("```", "~~~")):
        newline = body.find("\n")
        body = body[newline + 1 :] if newline != -1 else body[3:]
    if body.rstrip().endswith(("```", "~~~")):
        body = body.rstrip()[:-3]
    return body.strip()


def _parse_tool_call_block(inner: str, *, quiet: bool = False) -> dict[str, Any] | None:
    """Содержимое блока -> {"name","arguments"}; None, если блок невалиден.

    Отсутствие ключа arguments — допустимый вызов с {}; присутствующее, но
    не-объектное значение (строка-не-JSON, список, число, null) — вызов
    отклоняем, чтобы не запускать инструмент с пустыми аргументами.
    OpenAI-обёртка {"id","type","function":{"name","arguments"}} разворачивается,
    только если name верхнего уровня отсутствует (он всегда побеждает).
    """
    try:
        obj = _loads_lenient(_strip_code_fence(inner), quiet=quiet)
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    if "name" not in obj and isinstance(obj.get("function"), dict):
        obj = obj["function"]
    name = obj.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    arguments: dict[str, Any] = {}
    if "arguments" in obj:
        normalized = _normalize_arguments(obj.get("arguments"))
        if normalized is None:
            return None
        arguments = normalized
    return {"name": name.strip(), "arguments": arguments}


def _is_quoted_open(text: str, start: int) -> bool:
    """`<tool_call>`/`<tool_invoke>` в inline-коде markdown (`` `<tool_call>` ``) — не тег."""
    if start > 0 and text[start - 1] == "`":
        return True
    pair = _open_tag_at(text, start)
    open_len = len(pair[0]) if pair else len(TOOL_CALL_OPEN)
    tail = text[start + open_len : start + open_len + 3]
    return bool(tail) and tail[0] == "`" and tail != "```"


def _split_tool_call_inner(inner: str) -> list[str]:
    """Разбить содержимое блока по вложенным `<tool_call>`/`<tool_invoke>` вне строковых литералов JSON.

    Модель иногда пропускает закрывающий тег между соседними вызовами пачки и ставит
    один общий в конце. Литерал открывающего тега внутри JSON-строки
    границей не считается (та же логика, что в `_find_close_outside_string`).
    Пустые сегменты сохраняются: пустой элемент делает всю пачку невалидной.
    """
    segments: list[str] = []
    seg_start = 0
    index = 0
    length = len(inner)
    in_string = False
    escaped = False
    while index < length:
        char = inner[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        else:
            pair = _open_tag_at(inner, index)
            if pair is not None and not _is_quoted_open(inner, index):
                segments.append(inner[seg_start:index])
                index += len(pair[0])
                seg_start = index
                continue
        index += 1
    segments.append(inner[seg_start:])
    return segments


def _parse_tool_call_blocks(inner: str, *, quiet: bool = False) -> list[dict[str, Any]] | None:
    """Содержимое блока -> список вызовов; None, если блок (или любой его член) невалиден.

    Обычный блок даёт один вызов. Если он не разбирается, но внутри есть
    несколько открывающих тегов без промежуточных закрывающих, блок делится на
    сегменты; пачка принимается только целиком (все сегменты валидны).
    """
    single = _parse_tool_call_block(inner, quiet=quiet)
    if single is not None:
        return [single]
    if not any(open_tag in inner for open_tag, _ in TOOL_CALL_TAGS):
        return None
    segments = _split_tool_call_inner(inner)
    if len(segments) < 2:
        return None
    calls: list[dict[str, Any]] = []
    for segment in segments:
        call = _parse_tool_call_block(segment, quiet=quiet)
        if call is None:
            return None
        calls.append(call)
    return calls


_OPAQUE_BLOCK = "￼"  # в `_history` на месте разобранного блока вызова


def _fence_run(line: str) -> tuple[str, int, str]:
    """Строка -> (символ, длина серии, остаток), если это строка-забор fenced-блока.

    Забор — серия от 3 одинаковых бэктиков или тильд после отступа до 3 пробелов;
    ("", 0, "") — не забор.
    """
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3 or stripped[:1] not in ("`", "~"):
        return "", 0, ""
    char = stripped[0]
    rest = stripped.lstrip(char)
    run = len(stripped) - len(rest)
    return (char, run, rest) if run >= 3 else ("", 0, "")


def _is_fence_open(char: str, run: int, rest: str) -> bool:
    """Строка-забор открывает блок: в info-строке бэктик-забора нет бэктиков."""
    return bool(run) and (char == "~" or "`" not in rest)


def _find_closing_run(doc: str, start: int, end: int, ticks: int) -> int:
    """Конец первой серии ровно из `ticks` бэктиков в `doc[start:end]`, или -1."""
    index = start
    while index < end:
        if doc[index] != "`":
            index += 1
            continue
        run_start = index
        while index < end and doc[index] == "`":
            index += 1
        if index - run_start == ticks:
            return index
    return -1


def _is_atx_heading(line: str) -> bool:
    """Строка — ATX-заголовок: отступ до 3 пробелов, 1-6 `#`, затем пробел/таб/конец."""
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return False
    rest = stripped.lstrip("#")
    return 1 <= len(stripped) - len(rest) <= 6 and (
        not rest.rstrip("\r") or rest[0] in " \t"
    )


def _code_context(doc: str, pos: int, final: bool) -> str:
    """Положение `pos` в `doc` относительно markdown-кода: "code" | "text" | "wait".

    "code" — внутри fenced-блока (CommonMark: забор с отступом до 3 пробелов, закрывает
    серия того же символа (``` или ~~~) не короче открывающей, без текста после неё) или парного inline-кода (серия из
    k бэктиков и ближайшая серия ровно из k в том же абзаце; абзац обрывают пустая
    строка, забор и ATX-заголовок — он сам отдельный блок). Непарная серия — обычный
    текст. "wait" — ответ зависит от ещё не пришедшего текста (только при `final=False`).
    Результат определяется одним `doc`, поэтому не зависит от нарезки потока на чанки.
    """
    line_start = doc.rfind("\n", 0, pos) + 1
    fence_char, fence_len, para, index = "", 0, 0, 0
    while index < line_start:
        eol = doc.index("\n", index)
        line = doc[index:eol]
        char, run, rest = _fence_run(line)
        if fence_len:
            if char == fence_char and run >= fence_len and not rest.strip(" \t\r"):
                fence_len, para = 0, eol + 1
        elif _is_fence_open(char, run, rest):
            fence_char, fence_len = char, run
        elif not line.strip() or _is_atx_heading(line):
            para = eol + 1
        index = eol + 1
    if fence_len:
        return "code"
    eol = doc.find("\n", pos)
    char, run, rest = _fence_run(doc[line_start : len(doc) if eol == -1 else eol])
    if _is_fence_open(char, run, rest):  # тег в info-строке забора
        return "code" if eol != -1 or final else "wait"
    para_end, decided = len(doc), final
    index = len(doc) if eol == -1 else eol + 1
    if _is_atx_heading(doc[line_start : len(doc) if eol == -1 else eol]):
        para = line_start  # заголовок — отдельный однострочный блок
        if eol != -1:
            para_end, decided, index = eol, True, len(doc)
    while index < len(doc):  # абзац кончается пустой строкой, забором или заголовком
        nxt = doc.find("\n", index)
        line = doc[index : len(doc) if nxt == -1 else nxt]
        # заголовок с текстом после `#` решён по префиксу, не дожидаясь конца строки
        if (
            nxt == -1
            and not final
            and not (_is_atx_heading(line) and line.lstrip(" ").lstrip("#"))
        ):
            break
        char, run, rest = _fence_run(line)
        if not line.strip() or _is_fence_open(char, run, rest) or _is_atx_heading(line):
            para_end, decided = index, True
            break
        if nxt == -1:
            break
        index = nxt + 1
    index = para
    while index < pos:
        char = doc[index]
        if char == "\\":
            index += 2
        elif char != "`":
            index += 1
        else:
            open_start = index
            while index < para_end and doc[index] == "`":
                index += 1
            close_end = _find_closing_run(doc, index, para_end, index - open_start)
            if close_end == -1:
                if not decided:  # пара может прийти позже
                    return "wait"
            elif close_end > pos:
                return "wait" if close_end == len(doc) and not final else "code"
            else:
                index = close_end
    return "text"


def _find_close_in(text: str, start: int, close_tag: str = TOOL_CALL_CLOSE) -> int:
    """Позиция закрывающего тега вне строковых литералов JSON в `text[start:]`, или -1.

    Закрывающий тег внутри JSON-строки (например, значение аргумента содержит
    `</tool_call>`) границей блока не является. Экранированные кавычки `\\"`
    строку не закрывают.
    """
    index = start
    length = len(text)
    in_string = False
    escaped = False
    while index < length:
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif text.startswith(close_tag, index):
            return index
        index += 1
    return -1


_STRIP_SCAN_MAX_TAGS = 16  # граница CPU: `_code_context` — O(len) на кандидата
_BROKEN_BLOCK_NOTICE = "[opencode-zen-bridge: невалидный блок вызова инструмента отброшен]"


def _strip_broken_tool_blocks(text: str, *, quiet: bool = False) -> tuple[str, int]:
    """Вырезать сырые блоки вызова, которые не разбираются; (текст, число вырезанных).

    Валидные блоки (одиночный, пачка без промежуточных закрытий), теги в markdown-коде
    и текст без тегов остаются как есть (тот же объект, если ничего не вырезано).
    Незакрытый хвост и закрытый невалидный блок отбрасываются. После `_STRIP_SCAN_MAX_TAGS`
    кандидатов остаток отбрасывается целиком (fail-closed): битый тег не утекает ни при каком вводе.
    """
    match = _RAW_CALL_RE.search(text)
    if match is None:
        return text, 0
    parts: list[str] = []
    cursor = 0
    dropped = 0
    scanned = 0
    while match is not None:
        start = match.start()
        pair = _open_tag_at(text, start)
        if pair is None:  # недостижимо: _RAW_CALL_RE начинается с тега
            break
        open_tag, close_tag = pair
        pos = start + len(open_tag)
        if _code_context(text, start, True) == "text":
            if scanned >= _STRIP_SCAN_MAX_TAGS:
                if not quiet:
                    _log(f"tool_strip_cap_hit max={_STRIP_SCAN_MAX_TAGS} dropping tail")
                parts.append(text[cursor:start])
                cursor = len(text)
                dropped += 1
                break
            scanned += 1
            end = _find_close_in(text, pos, close_tag)
            if end == -1:  # незакрытый хвост
                parts.append(text[cursor:start])
                cursor = len(text)
                dropped += 1
                break
            try:
                calls = _parse_tool_call_blocks(text[pos:end], quiet=True)
            except RecursionError:
                calls = None
            pos = end + len(close_tag)
            if calls is None:
                parts.append(text[cursor:start])
                cursor = pos
                dropped += 1
        match = _RAW_CALL_RE.search(text, pos)
    if not dropped:
        return text, 0
    parts.append(text[cursor:])
    return "".join(parts), dropped


class ToolCallParser:
    """Поток текстовых дельт -> content и завершённые вызовы инструментов.

    Тег <tool_call> (или <tool_invoke>) может прийти разорванным между дельтами: хвост, который может
    оказаться началом тега, удерживается и не уходит в content до разрешения.
    """

    def __init__(self, on_content, on_tool_call):
        self._buf = ""
        self._on_content = on_content
        self._on_tool_call = on_tool_call
        self._history = ""  # весь текст, ушедший в content
        self.tool_calls_count = 0
        self.trailing_chars_after_tool = 0
        self._tail_after_tool = ""  # весь текст после последнего вызова (для инварианта к чанкам)

    def feed(self, text: str) -> None:
        self._buf += text
        self._drain(final=False)

    def finish(self) -> None:
        self._drain(final=True)

    def has_open_tool_call(self) -> bool:
        """Тег открыт и ждёт закрытия (или его начало может прийти следующей дельтой)."""
        return any(open_tag in self._buf for open_tag, _ in TOOL_CALL_TAGS) or self._pending_prefix() > 0

    def _classify_open(self, after: int, final: bool) -> str:
        """`<tool_call>` в буфере: "real" | "quoted" (inline-код markdown) | "wait" (нужен следующий символ)."""
        context = _code_context(
            self._history + self._buf, len(self._history), final
        )
        if context != "text":
            return "quoted" if context == "code" else "wait"
        tail = self._buf[after:after + 3]
        if not tail:
            return "real" if final else "wait"
        if tail[0] != "`" or tail == "```":  # ```json-обёртка внутри блока — настоящий вызов
            return "real"
        if not final and tail == "`" * len(tail) and len(tail) < 3:
            return "wait"
        return "quoted"

    def _drain(self, final: bool) -> None:
        while True:
            start, open_tag, close_tag = self._find_open()
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
                # всё до тега завершено: текст уходит в content и в `_history`
                self._emit(self._buf[:start])
                self._buf = self._buf[start:]
            after = len(open_tag)
            verdict = self._classify_open(after, final)
            if verdict == "quoted":
                self._emit(self._buf[:after])
                self._buf = self._buf[after:]
                continue
            if verdict == "wait":
                return
            end = self._find_close_outside_string(after, close_tag)
            if end == -1:
                if final:
                    self._flush_all()  # незакрытый/невалидный блок отдаём текстом
                return
            inner = self._buf[after:end]
            self._buf = self._buf[end + len(close_tag):]
            calls = _parse_tool_call_blocks(inner)
            if calls is None:
                _log(f"tool_call_unparsed bytes={len(inner.encode('utf-8'))} "
                     f"head={_mask_secrets(inner[:120])!r}")
                self._emit(open_tag + inner + close_tag)
            else:
                self._history += _OPAQUE_BLOCK
                for call in calls:
                    self.tool_calls_count += 1
                    self._tail_after_tool = ""
                    self.trailing_chars_after_tool = 0
                    self._on_tool_call(call)

    def _find_open(self) -> tuple[int, str, str]:
        """Ближайший открывающий тег в буфере: (позиция, открывающий, закрывающий) или (-1, "", "")."""
        best = (-1, "", "")
        for open_tag, close_tag in TOOL_CALL_TAGS:
            pos = self._buf.find(open_tag)
            if pos != -1 and (best[0] == -1 or pos < best[0]):
                best = (pos, open_tag, close_tag)
        return best

    def _find_close_outside_string(self, start: int, close_tag: str = TOOL_CALL_CLOSE) -> int:
        """Позиция закрывающего тега вне строковых литералов JSON буфера, или -1 (см. `_find_close_in`)."""
        return _find_close_in(self._buf, start, close_tag)

    def _pending_prefix(self) -> int:
        """Длина хвоста — префикса открывающего тега (его нельзя отдать в content)."""
        limit = min(max(len(open_tag) for open_tag, _ in TOOL_CALL_TAGS) - 1, len(self._buf))
        for length in range(limit, 0, -1):
            if any(self._buf[-length:] == open_tag[:length] for open_tag, _ in TOOL_CALL_TAGS):
                return length
        return 0

    def _emit(self, text: str) -> None:
        if not text:
            return
        self._history += text
        if self.tool_calls_count:
            # Протокол: после вызова модель ничего не пишет; хвост (бред/цикл) не отдаём.
            self._tail_after_tool += text
            self.trailing_chars_after_tool = len(self._tail_after_tool.strip())
            return
        self._on_content(text)

    def _flush_all(self) -> None:
        if self._buf:
            text, self._buf = self._buf, ""
            self._emit(text)


def _split_tool_calls(chunks: list[str]) -> tuple[str, list[dict[str, Any]]]:
    """Дельты текста ответа -> (content, tool_calls в формате OpenAI).

    Тот же ToolCallParser, что у droid-bridge; id вызовов — call_<hex24>.
    """
    pieces: list[str] = []
    calls: list[dict[str, Any]] = []

    def add_call(call: dict[str, Any]) -> None:
        calls.append({
            "index": len(calls),
            "id": "call_" + uuid.uuid4().hex[:24],
            "type": "function",
            "function": {"name": call["name"],
                         "arguments": json.dumps(call["arguments"], ensure_ascii=False)},
        })

    parser = ToolCallParser(pieces.append, add_call)
    for chunk in chunks:
        parser.feed(chunk)
    parser.finish()
    return "".join(pieces), calls


_TOKEN_RE = re.compile(r"\s+")


def _estimate_tokens(text: str) -> int:
    """Грубая оценка, если CLI не отдал usage (fallback)."""
    if not text:
        return 0
    return max(1, int(len(_TOKEN_RE.split(text.strip())) * 1.3))


EFFORT_MAP: dict[str, str] = {
    "off": "",
    "none": "",
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "xhigh",
    "ultra": "xhigh",
}
DEFAULT_EFFORT = "high"


def _level_to_variant(meta: dict[str, Any], key: str) -> str:
    """Уровень запроса -> variant модели: по её variant_map (ceil_clamp), иначе общая EFFORT_MAP."""
    vmap = meta.get("variant_map")
    if isinstance(vmap, dict):
        if key in vmap:
            return vmap[key]
        return vmap.get(DEFAULT_EFFORT, "")
    return EFFORT_MAP.get(key, DEFAULT_EFFORT)


def _map_effort(req: dict[str, Any], model_id: str = "") -> str:
    reasoning = _dict_or_empty(req.get("reasoning"))
    raw: Any = req.get("reasoning_effort")
    if raw is None:
        raw = reasoning.get("effort")
    target = model_id or str(req.get("model") or _effective_default_model()).strip()
    meta = ALLOWED_MODELS.get(target, {})
    if raw is None:
        if (meta.get("provider") or meta.get("base_url")) and (
            "reasoning_effort" in req or "effort" in reasoning
        ):
            return ""
        return _level_to_variant(meta, DEFAULT_EFFORT)
    key = str(raw).strip().lower()
    if key in ("off", "none"):
        return ""
    return _level_to_variant(meta, key)


def parse_opencode_event(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Разбор одного события `opencode run` для чанков OpenAI SSE / non-stream."""
    if not isinstance(event, dict):
        return "", {}
    etype = str(event.get("type") or "").strip()
    part = _dict_or_empty(event.get("part"))

    if etype == "reasoning":
        rtext = part.get("text")
        meta = _dict_or_empty(part.get("metadata"))
        openai_meta = _dict_or_empty(meta.get("openai"))
        enc_data = openai_meta.get("reasoningEncryptedContent")

        delta: dict[str, Any] = {}
        if isinstance(rtext, str) and rtext:
            delta["reasoning_content"] = rtext
        if isinstance(enc_data, str) and enc_data:
            delta["reasoning_details"] = [{"type": "reasoning.encrypted", "data": enc_data}]
        return ("reasoning", delta)

    if etype == "text":
        ttext = part.get("text")
        if isinstance(ttext, str) and ttext:
            return ("text", {"content": ttext})
        return ("text", {})

    if etype == "step_finish":
        tokens = _dict_or_empty(part.get("tokens"))
        return ("step_finish", tokens)

    if etype == "error":
        err_obj = event.get("error")
        if not isinstance(err_obj, dict):
            err_obj = {"message": str(err_obj)}
        data = err_obj.get("data")
        if isinstance(data, dict):
            message = str(data.get("message") or err_obj.get("message") or err_obj)
            status = data.get("statusCode")
        else:
            message = str(err_obj.get("message") or err_obj)
            status = None
        if "provider.no-route" in message or "Variant unavailable" in message:
            status = 400
        return ("error", {"statusCode": status, "message": message})

    return (etype, {})


def format_sse_chunk(
    resp_id: str,
    created: int,
    model: str,
    delta: dict[str, Any],
    finish_reason: str | None = None,
    usage: dict[str, Any] | None = None,
) -> str:
    """Форматирование одного SSE-события OpenAI чанка."""
    choice: dict[str, Any] = {"index": 0, "delta": delta}
    if finish_reason is not None:
        choice["finish_reason"] = finish_reason
    chunk: dict[str, Any] = {
        "id": resp_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [choice],
    }
    if usage is not None:
        chunk["usage"] = usage
    return "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"


def _resolve_opencode_go_auth() -> tuple[str, str]:
    """Читать активную учётную запись заново на каждом запросе без записи в БД."""
    token = ""
    org_id = os.environ.get("OPENCODE_ORG_ID", "org_01M4ZR9TJ6XN1X4MS79ADKQJ60").strip()
    db_path = Path.home() / ".local/share/opencode/opencode.db"
    try:
        conn = sqlite3.connect(f"file:{quote(str(db_path))}?mode=ro", uri=True, timeout=5)
        try:
            try:
                row = conn.execute(
                    "SELECT a.access_token, s.active_org_id FROM account_state s "
                    "JOIN account a ON a.id = s.active_account_id LIMIT 1"
                ).fetchone()
            except sqlite3.Error:
                row = None
            if row and row[0]:
                token = str(row[0]).strip()
                org_id = str(row[1] or org_id).strip()
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        pass
    return token or os.environ.get("OPENCODE_GO_API_KEY", "").strip(), org_id


def _is_google_direct_model(model_id: str) -> bool:
    return bool(ALLOWED_MODELS.get(model_id, {}).get("base_url", "").rstrip("/").endswith("/v1beta"))


GOOGLE_STOP_SEQUENCES = ["\nUser:", "\n[tool result "]
GOOGLE_CONTINUE_TEXT = "Continue."


def _messages_to_google_contents(messages: list[dict[str, Any]],
                                 system_head: str) -> tuple[list[dict[str, Any]], str]:
    """История OpenAI -> (contents user/model, systemInstruction) без разбора плоского текста.

    Разделители «User: »/«Assistant: » внутри текста сообщений остаются содержимым;
    system/developer уже собраны в system_head. Соседние реплики одной роли склеиваются
    в parts одного content (tool-результаты идут как user).
    """
    contents: list[dict[str, Any]] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role, text = _render_turn(msg)
        if not text.strip() or role in ("system", "developer"):
            continue
        google_role = "model" if role == "assistant" else "user"
        if contents and contents[-1]["role"] == google_role:
            contents[-1]["parts"].append({"text": text})
        else:
            contents.append({"role": google_role, "parts": [{"text": text}]})
    return contents, system_head


def _build_google_payload(prompt: str, effort: str, max_output: int,
                          contents: list[dict[str, Any]] | None = None,
                          system_instruction: str = "",
                          emulate_tools: bool = False) -> dict[str, Any]:
    """Тело generateContent: systemInstruction + чередующиеся user/model contents.

    Плоский один `user` не попадает в неявный кэш Google (cachedContentTokenCount=0) и
    провоцирует модель дописывать чужие реплики, поэтому do_POST передаёт структуру.
    Без contents prompt уходит одним user-сообщением. emulate_tools оставлен для
    совместимости сигнатуры: stopSequences одинаковы с инструментами и без.
    """
    payload: dict[str, Any] = {}
    if system_instruction.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    if contents is None:
        payload["contents"] = [{"role": "user", "parts": [{"text": prompt}]}]
    else:
        payload["contents"] = list(contents)
        if payload["contents"] and payload["contents"][-1]["role"] == "model":
            payload["contents"].append({"role": "user", "parts": [{"text": GOOGLE_CONTINUE_TEXT}]})
    gen_cfg: dict[str, Any] = {"maxOutputTokens": max_output,
                               "stopSequences": list(GOOGLE_STOP_SEQUENCES)}
    if effort:
        level = "HIGH" if effort in ("high", "xhigh") else effort.upper()
        gen_cfg["thinkingConfig"] = {"includeThoughts": True, "thinkingLevel": level}
    payload["generationConfig"] = gen_cfg
    return payload


def _build_openai_usage(prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0,
                        reasoning_tokens: int = 0) -> dict[str, Any]:
    """OpenAI usage; cached/reasoning читает pi-ai (prompt_tokens_details, completion_tokens_details)."""
    usage_obj: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    if cached_tokens > 0:
        usage_obj["cached_tokens"] = cached_tokens
        usage_obj["prompt_tokens_details"] = {"cached_tokens": cached_tokens}
    if reasoning_tokens > 0:
        usage_obj["completion_tokens_details"] = {"reasoning_tokens": reasoning_tokens}
    return usage_obj


_LOOP_TAIL_CHARS = 600
_LOOP_MIN_REPEATS = 6
_LOOP_MIN_BLOCK_CHARS = 120
_CDATA_END_MIN = 6


_TABLE_SEP_RE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*$", re.MULTILINE)


def _in_active_markdown_table(text: str, loop_start: int, sep_ends: list[int] | None = None) -> bool:
    """Перед loop_start идёт строка-разделитель таблицы, а после неё нет пустой строки и все строки с «|».

    sep_ends — заранее посчитанные концы разделителей всего text (для многократных проверок без O(n) на вызов).
    """
    if sep_ends is None:
        sep_ends = [m.end() for m in _TABLE_SEP_RE.finditer(text, 0, loop_start)]
        last_end = sep_ends[-1] if sep_ends else None
    else:
        last_end = next((e for e in reversed(sep_ends) if e <= loop_start), None)
    if last_end is None:
        return False
    between = text[last_end:loop_start]
    for eol in ("\r\n", "\n"):  # перевод строки, завершающий сам разделитель
        if between.startswith(eol):
            between = between[len(eol):]
            break
    lines = between.splitlines()
    if lines and not between.endswith(("\n", "\r")):  # хвост до loop_start оборван посреди строки таблицы
        lines.pop()
    # Пустая строка (в т.ч. из пробелов/табов, CRLF) завершает таблицу.
    return all(ln.strip() and "|" in ln and "||" not in ln for ln in lines)


def _is_table_block(unit: str, text: str = "", loop_start: int = 0) -> bool:
    """Блок содержит разделитель ячеек markdown-таблицы (в т.ч. без крайних «|» и оборванную ротацию строки)."""
    if "\n" not in unit:
        return False
    lines = [s.strip() for s in (unit * 3).splitlines()[1:-1] if s.strip()]
    if not lines:
        return False
    if not all("|" in s and "||" not in s for s in lines):
        return False
    if _in_active_markdown_table(text, loop_start):
        return True
    return all(
        s.startswith("|") or s.endswith("|") or s.count("|") >= 2
        or (" | " in s and not s.endswith((".", "!", "?", ";")))
        for s in lines
    )


_CDATA_GAP_MAX = 80


def _cdata_loop_start(text: str) -> int | None:
    """Начало цикла «]]>»: >= _CDATA_END_MIN «]]>» вне таблиц в последних 300 символах, иначе None.

    «]]>» в строках активной markdown-таблицы и в окне после «<![CDATA[» — не цикл и в кластер не входят;
    назад идём по цепочке «]]>» с интервалом <= _CDATA_GAP_MAX символов.
    """
    recent_start = max(0, len(text) - 300)
    if text.count("]]>", recent_start) < _CDATA_END_MIN:
        return None
    seps = [m.end() for m in _TABLE_SEP_RE.finditer(text)]

    def is_terminator(pos: int) -> bool:
        return "<![CDATA[" not in text[max(0, pos - 300):pos] and not _in_active_markdown_table(text, pos, seps)

    recent = []
    pos = text.find("]]>", recent_start)
    while pos >= 0:
        if is_terminator(pos):
            recent.append(pos)
        pos = text.find("]]>", pos + 3)
    if len(recent) < _CDATA_END_MIN:
        return None
    start = recent[0]
    while (prev := text.rfind("]]>", max(0, start - _CDATA_GAP_MAX), start)) >= 0 and is_terminator(prev):
        start = prev
    return start


def _detect_repetition_loop(text: str) -> int | None:
    """Индекс начала зацикленного хвоста (кусок 4..80 символов >= 6 раз подряд, >= 120 символов) или None."""
    tail = text[-_LOOP_TAIL_CHARS:]
    base = len(text) - len(tail)
    if "<![CDATA[" not in tail[-300:] and (cdata_idx := _cdata_loop_start(text)) is not None:
        return cdata_idx
    size_total = len(tail)
    for size in range(4, 81):
        if size * _LOOP_MIN_REPEATS > size_total:
            break
        unit = tail[-size:]
        if len(set(unit) - set(" \t\r\n")) < 3:  # «-----», «0, 0, 0» — не цикл
            continue
        pos = size_total - size
        reps = 1
        while pos - size >= 0 and tail[pos - size:pos] == unit:
            reps += 1
            pos -= size
        if reps < _LOOP_MIN_REPEATS or size * reps < _LOOP_MIN_BLOCK_CHARS:
            continue
        full_pos = base + pos  # цикл мог начаться раньше хвоста — отматываем по всему тексту
        while full_pos - size >= 0 and text[full_pos - size:full_pos] == unit:
            full_pos -= size
        if _is_table_block(unit, text, full_pos):  # строки markdown-таблицы повторяются законно
            continue
        return full_pos
    return None


_THOUGHT_CLOSED_RE = re.compile(r"<unused94>thought\b.*?<unused95>\s*", re.DOTALL)
_THOUGHT_OPEN_RE = re.compile(r"<unused94>thought\b.*$", re.DOTALL)
_CDATA_LOOP_RE = re.compile(
    r"(?:(?:Sub-thought finished\.|end\.|stop\.)?\s*\]\]>\s*(?:Let's [^\n\]]*)?\s*){2,}.*$", re.DOTALL)


def _strip_unclosed_tool_calls(text: str) -> str:
    """Отрезать сырые `<tool_call>{…` после последнего закрывающего тега: они не закрыты и травят few-shot.

    Пачка блоков без промежуточных закрытий, закрытая в конце, не затрагивается.
    """
    close_end = max((text.rfind(close_tag) + len(close_tag) for _, close_tag in TOOL_CALL_TAGS
                     if close_tag in text), default=0)
    match = _RAW_CALL_RE.search(text, close_end)
    return text[:match.start()].rstrip() if match else text


def _sanitize_assistant_text(text: str) -> str:
    """Очистить реплику assistant из истории от сырых thought-блоков и зацикленного хвоста `]]>`.

    Старые сессии хранят сотни КБ «end.]]> Let's stop.]]>» и «<unused94>thought…»: их возврат
    в contents тратит токены и провоцирует модель повторять мусор.
    """
    text = _THOUGHT_CLOSED_RE.sub("", text)
    text = _THOUGHT_OPEN_RE.sub("", text)
    text = _strip_interrupted(text)
    text = _strip_unclosed_tool_calls(text)
    text = _strip_broken_tool_blocks(text, quiet=True)[0]
    if _detect_repetition_loop(text) is not None or text.count("]]>") >= 4:
        text = _CDATA_LOOP_RE.sub("", text)
        while (loop_idx := _detect_repetition_loop(text)) is not None:
            text = text[:loop_idx]
    return text


GoogleInput = tuple[list[dict[str, Any]], str]  # (contents, systemInstruction) из _messages_to_google_contents


def _google_request(model: str, prompt: str, effort: str, stream: bool,
                    google_input: GoogleInput | None = None):
    """Открыть HTTP напрямую: прокси из окружения здесь не используются."""
    meta = ALLOWED_MODELS[model]
    base = urlsplit(meta["base_url"].rstrip("/"))
    token, org_id = _resolve_opencode_go_auth()
    headers = {
        "Content-Type": "application/json", "User-Agent": "curl/8.7.1",
        "x-goog-api-key": token, "Authorization": f"Bearer {token}",
        "x-opencode-session": "dsh",
    }
    if org_id:
        headers["x-opencode-org-id"] = org_id
    contents, system_instruction = google_input if google_input is not None else (None, "")
    body = json.dumps(_build_google_payload(prompt, effort, int(meta.get("max_output") or 65536),
                                            contents, system_instruction),
                      ensure_ascii=False).encode("utf-8")
    action = "streamGenerateContent?alt=sse" if stream else "generateContent"
    path = f"{base.path}/models/{quote(model, safe='')}:{action}"
    cls = http.client.HTTPSConnection if base.scheme == "https" else http.client.HTTPConnection
    conn = cls(base.hostname or "127.0.0.1", base.port, timeout=TIMEOUT_S)
    try:
        conn.request("POST", path, body=body, headers=headers)
        return conn, conn.getresponse()
    except Exception:
        conn.close()
        raise


def _execute_google_once(model: str, prompt: str, effort: str,
                         google_input: GoogleInput | None = None) -> dict[str, Any]:
    """Нативный Google-ответ в том же формате, что результат CLI-прогона."""
    conn = None
    run_id = uuid.uuid4().hex[:8]
    with _active_lock:
        _active[run_id] = time.time()
    try:
        conn, resp = _google_request(model, prompt, effort, False, google_input)
        raw = resp.read().decode("utf-8", errors="replace")
        if resp.status != 200:
            return {"rc": 1, "text": "", "chunks": [], "native_calls": [], "reasoning": "", "usage": {},
                    "err": f"HTTP {resp.status}: {_clean_err(raw)}", "provider_status": resp.status,
                    "had_output": False, "state": "provider_error", "finish": "error"}
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise ValueError("google response is not a JSON object")
        candidates = event.get("candidates") or []
        cand = candidates[0] if candidates else {}
        finish_reason = cand.get("finishReason")
        parts = (cand.get("content") or {}).get("parts") or []
        texts: list[str] = []
        thoughts: list[str] = []
        for part in parts:
            text = part.get("text")
            if isinstance(text, str) and text:
                (thoughts if part.get("thought") is True else texts).append(text)
        text, reasoning = "".join(texts), "".join(thoughts)
        truncated = False
        while (loop_idx := _detect_repetition_loop(text)) is not None:
            text = text[:loop_idx]
            truncated = True
        if truncated:
            texts = [text] if text else []
        um = event.get("usageMetadata") or {}
        thought_tok = int(um.get("thoughtsTokenCount") or 0)
        cached_tok = int(um.get("cachedContentTokenCount") or 0)
        usage_dict: dict[str, int] = {"input": int(um.get("promptTokenCount") or 0),
                                      "output": int(um.get("candidatesTokenCount") or 0) + thought_tok}
        if cached_tok > 0:
            usage_dict["cached"] = cached_tok
        if thought_tok > 0:
            usage_dict["reasoning"] = thought_tok
        return {"rc": 0, "text": text, "chunks": texts, "native_calls": [], "reasoning": reasoning,
                "usage": usage_dict,
                "err": "", "provider_status": 200, "had_output": bool(text or reasoning),
                "state": "ok", "finish": ("length" if finish_reason == "MAX_TOKENS" else "stop") if (text or reasoning) else "error"}
    except (OSError, ValueError, TypeError, AttributeError, http.client.HTTPException) as exc:
        return {"rc": -1, "text": "", "chunks": [], "native_calls": [], "reasoning": "", "usage": {},
                "err": _clean_err(str(exc)), "provider_status": None, "had_output": False,
                "state": "provider_error", "finish": "error"}
    finally:
        if conn is not None:
            conn.close()
        with _active_lock:
            _active.pop(run_id, None)


class Run:
    """Один прогон `opencode run` с разбором JSON-событий (non-streaming)."""

    def __init__(self, model_id: str, prompt: str, effort: str, workdir: Path,
                 tools: list[dict[str, Any]] | None = None,
                 google_input: GoogleInput | None = None,
                 attempts: _RequestAttempts | None = None,
                 resilience: _Resilience | None = None) -> None:
        # tools задан (эмуляция) -> прогон обрывается в конце шага, давшего вызов для DSH:
        # следующие шаги — реакция модели на «отклонение» (повтор того же вызова).
        self.tools = tools
        self.google_input = google_input
        self.model_id = model_id
        self.prompt = prompt
        self.effort = effort
        self.workdir = workdir
        self.res = resilience or (attempts.res if attempts is not None else _DEFAULT_RESILIENCE)
        self.attempts = attempts
        self.proc: subprocess.Popen[str] | None = None
        self.feed: _StdoutFeed | None = None

    def close(self) -> None:
        proc = self.proc
        if proc is None:
            return
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        if self.feed is not None:
            self.feed.close()
        elif proc.stdout is not None:
            try:
                proc.stdout.close()
            except OSError:
                pass
        try:
            if proc.stderr is not None:
                proc.stderr.close()
        except OSError:
            pass

    def execute(self) -> dict[str, Any]:
        """Прогон с повтором транзиторных отказов CLI (rc != 0 без вывода, напр. `database is locked`).

        Повторы идут внутри общего потолка MAX_TOTAL_SPAWNS запроса, Retry Budget и Circuit Breaker.
        """
        owns_attempts = self.attempts is None
        if self.attempts is None:
            self.attempts = _RequestAttempts(self.res, time.monotonic() + TIMEOUT_S,
                                             use_breaker=not _is_google_direct_model(self.model_id))
        attempts = self.attempts
        fail_retries = 0
        try:
            while True:
                out = self._execute_once()
                if fail_retries >= FAIL_RETRY_LIMIT or not _is_retryable_failure(
                        out.get("rc"), str(out.get("err") or ""), out.get("provider_status"),
                        bool(out.get("had_output"))):
                    return out
                if not attempts.allow_retry("cli_failure", charge_budget=out.get("provider_status") is not None):
                    return out
                fail_retries += 1
                _log(f"exec failed rc={out.get('rc')} without output, retry {fail_retries}/{FAIL_RETRY_LIMIT} "
                     f"total_spawns={attempts.total_spawns}/{attempts.max_total}: "
                     f"{_clean_err(str(out.get('err') or ''), 300)!r}")
                self.close()
        finally:
            if owns_attempts:
                attempts.commit()

    def _execute_once(self) -> dict[str, Any]:
        """Один прогон: текст — из type:text, мышление — из type:reasoning, usage — из step_finish."""
        if _is_google_direct_model(self.model_id):
            return _execute_google_once(self.model_id, self.prompt, self.effort, self.google_input)
        launcher = _resolve_launcher()
        if not os.access(launcher, os.X_OK):
            return {"rc": -1, "text": "", "reasoning": "", "usage": {},
                    "err": f"opencode launcher not executable: {launcher}",
                    "state": "launcher_missing", "finish": "error"}

        self.workdir.mkdir(parents=True, exist_ok=True)
        env = _run_env(self.model_id)
        model_route = _model_route(self.model_id)

        cmd, shown = _build_cmd(launcher, self.model_id, self.effort)
        _log(f"exec model={model_route} {shown} prompt_chars={len(self.prompt)} cwd={self.workdir}")
        deadline = self.attempts.deadline if self.attempts is not None else time.monotonic() + TIMEOUT_S
        gate = _StartupGate()
        gate.acquire()
        if not self.res.spawn_limiter.acquire(max_wait_s=min(SPAWN_WAIT_MAX_S, max(0.0, deadline - time.monotonic()))):
            gate.release()
            return {"rc": -1, "text": "", "reasoning": "", "usage": {}, "err": "spawn rate limit: deadline exceeded",
                    "state": "timeout", "finish": "error"}
        try:
            self.proc = _spawn_with_stdin(cmd, self.prompt, self.workdir, env)
        except OSError as exc:
            gate.release()
            return {"rc": -1, "text": "", "reasoning": "", "usage": {}, "err": f"spawn failed: {exc}",
                    "state": "spawn_failed", "finish": "error"}
        if self.attempts is not None:
            self.attempts.note_spawn()

        text_pieces: list[str] = []
        reasoning_pieces: list[str] = []
        native_calls: list[dict[str, Any]] = []
        usage: dict[str, Any] = {}
        err_lines: list[str] = []
        provider_status: int | None = None
        had_error = False       # транзиентная ошибка провайдера посреди ответа (had_mid_stream_error)
        fatal_error = False     # детерминированная ошибка посреди ответа (400/401/403/404/422): без повтора
        stopped_on_error = False
        state = "ok"
        run_id = uuid.uuid4().hex[:8]

        with _active_lock:
            _active[run_id] = time.time()

        def drain_stderr() -> None:
            try:
                assert self.proc is not None and self.proc.stderr is not None
                for line in self.proc.stderr:
                    line = line.strip()
                    if line:
                        err_lines.append(line)
            except (OSError, ValueError):
                pass

        err_thread = threading.Thread(target=drain_stderr, daemon=True)
        err_thread.start()

        try:
            self.feed = _StdoutFeed(self.proc)
            for raw in self.feed.lines(deadline):
                gate.release()
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except ValueError:
                    _log(f"non-json stdout line: {_clean_err(raw)[:100]}")
                    err_lines.append(raw[:200])
                    continue

                etype, payload = parse_opencode_event(event)
                if etype == "text":
                    ttext = payload.get("content")
                    if isinstance(ttext, str):
                        ttext = _strip_interrupted(ttext)
                    if isinstance(ttext, str) and ttext:
                        text_pieces.append(ttext)
                elif etype == "reasoning":
                    rtext = payload.get("reasoning_content")
                    if isinstance(rtext, str):
                        rtext = _strip_interrupted(rtext)
                    if isinstance(rtext, str) and rtext:
                        reasoning_pieces.append(rtext)
                elif etype == "step_finish":
                    if payload:
                        for key in ("input", "output", "cached", "reasoning"):
                            usage[key] = int(usage.get(key) or 0) + int(payload.get(key) or 0)
                    if self.tools is not None and (
                            any(_native_to_tool_calls(nc.get("tool"), nc.get("input"), self.tools)
                                for nc in native_calls)
                            or any(close_tag in "".join(text_pieces) for _, close_tag in TOOL_CALL_TAGS)):
                        _log("exec: step with tool call finished, stopping opencode run")
                        _stop_proc(self.proc)
                        break
                elif etype == "tool_use":
                    tpart = _dict_or_empty(event.get("part"))
                    tstate = _dict_or_empty(tpart.get("state"))
                    native_calls.append({"tool": tpart.get("tool"), "input": tstate.get("input"),
                                         "status": tstate.get("status")})
                elif etype == "error":
                    state = "provider_error"
                    if isinstance(payload.get("statusCode"), int):
                        provider_status = payload["statusCode"]
                    err_lines.append(f"HTTP {payload.get('statusCode')}: {payload.get('message')}")
                    if text_pieces or reasoning_pieces or native_calls:
                        # Оборванный ответ: иначе opencode сам запустит SYNTHETIC-шаг «Continue…» —
                        # останавливаем сразу. Транзиентная ошибка -> had_error (повтор шага),
                        # детерминированная (401…) -> fatal_error (без повтора, ошибка клиенту).
                        # Ошибка до первого токена — не трогаем: opencode повторит сам или выйдет,
                        # и тогда had_error не должен «залипнуть» на восстановленном ответе.
                        if _is_transient_stream_error(payload):
                            had_error = True
                        else:
                            fatal_error = True
                        _log(f"exec: provider error mid-response (transient={had_error}), stopping opencode run")
                        stopped_on_error = True
                        _stop_proc(self.proc)
                        break
                    _log("exec: early provider error (waiting for CLI recovery)")
            if self.feed.overflowed:
                state = "stdout_overflow"
                err_lines.append("stdout queue overflow")
                had_error = True
                stopped_on_error = True
            elif self.feed.timed_out:
                state = "timeout"
                _log(f"exec timeout after {TIMEOUT_S:.0f}s, killing proc group")
                _stop_proc(self.proc)
        except (OSError, ValueError) as exc:
            state = "stream_error"
            err_lines.append(f"stdout read failed: {exc}")
        finally:
            gate.release()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                state = "timeout"
                self.close()
            err_thread.join(timeout=5)
            with _active_lock:
                _active.pop(run_id, None)

        rc = self.proc.returncode if self.proc and self.proc.returncode is not None else -1
        if stopped_on_error and rc < 0:
            rc = 1  # остановили сами после ошибки провайдера: для классификации отказа — как собственный выход CLI
        if rc != 0 and state == "ok":
            state = "nonzero_exit"

        text = "".join(text_pieces)
        reasoning = "".join(reasoning_pieces)
        err_tail = _clean_err(err_lines[-6:])
        if rc != 0 and err_tail:
            _log(f"exec cli failed rc={rc} state={state} stderr_tail={err_tail!r}")
        had_output = bool(text or reasoning or native_calls)
        if state == "stdout_overflow" and not had_output:
            rc = max(rc, 1)
        transient_failure = had_error or (
            not had_output and _is_retryable_failure(rc, err_tail, provider_status, False))
        if self.attempts is not None:
            self.attempts.attempt_done(transient_failure, had_output and not transient_failure)
        elif transient_failure:
            self.res.breaker.record_failure()
        elif had_output:
            self.res.breaker.record_success()
        return {"rc": rc, "text": text, "chunks": list(text_pieces), "native_calls": native_calls, "reasoning": reasoning, "usage": usage,
                "err": err_tail, "provider_status": provider_status,
                "had_output": had_output, "had_error": had_error, "fatal_error": fatal_error,
                "state": state, "finish": "stop" if text else "error"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 300

    def log_message(self, format: str, *args: Any) -> None:
        _log("http " + (format % args))

    def handle_error(self, request: Any, client_address: Any) -> None:
        _log(f"http accept error from {client_address}")

    _xs: dict[str, Any] | None = None

    def _exit(self) -> dict[str, Any]:
        """Состояние выхода текущего запроса для структурной строки O-EXIT/v1."""
        if self._xs is None:
            self._xs = _new_exit_state()
        return self._xs

    def _res(self) -> _Resilience:
        """Защиты сервера (слоты, breaker, budget, лимитер); у `Server` — свои, иначе модульные."""
        return cast("_Resilience", getattr(getattr(self, "server", None), "resilience", None) or _DEFAULT_RESILIENCE)

    def _acquire_slot(self, res: _Resilience) -> bool:
        """Слот с ограниченным ожиданием; отказ -> 503 overloaded (таймаут 15 с или 13-й ждущий мгновенно)."""
        verdict = res.slots.acquire_ex()
        if verdict == "ok":
            return True
        self._exit()["exit_reason"] = "slot_timeout" if verdict == "timeout" else "slot_overflow"
        self._send(503, {"error": {"message": "bridge busy", "type": "overloaded"}})
        return False

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        self._exit()["status"] = int(code)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(int(code))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            _log("client gone before response")

    def _sse_error(self, payload: dict[str, Any]) -> None:
        """Ошибка в уже открытом SSE-потоке: OpenAI-style `data: {"error":…}` + [DONE].

        Заголовки 200 уже отправлены, поэтому статус изменить нельзя; клиенты OpenAI
        (openai-node/ai-sdk) бросают исключение на чанке с полем error. finish_reason
        не отправляем: пустого успешного завершения быть не должно.
        """
        self.wfile.write(("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _stream_google_sse(self, model: str, prompt: str, effort: str,
                           emulate_tools: bool = False,
                           google_input: GoogleInput | None = None) -> None:
        """Перевести Google SSE в OpenAI SSE, сохранив эмуляцию инструментов."""
        res = self._res()
        if not self._acquire_slot(res):
            return
        conn = None
        started = False
        run_id = uuid.uuid4().hex[:8]
        with _active_lock:
            _active[run_id] = time.time()
        try:
            resp_id = f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}"
            created = int(time.time())
            self.close_connection = True
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            started = True
            self._exit()["status"] = 200

            def emit(delta: dict[str, Any]) -> None:
                self.wfile.write(format_sse_chunk(resp_id, created, model, delta).encode("utf-8"))
                self.wfile.flush()

            emit({"role": "assistant", "content": ""})
            conn, resp = _google_request(model, prompt, effort, True, google_input)
            if resp.status != 200:
                tail = _clean_err(resp.read().decode("utf-8", errors="replace"))
                _log(f"google upstream failed HTTP {resp.status}: {tail}")
                self._sse_error(_error_payload(f"google upstream failed (HTTP {resp.status}): {tail}", tail))
                return
            collected_texts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            seen_calls: set[str] = set()
            usage: dict[str, int] = {}
            finish_reason = ""
            had_reasoning = False

            def emit_content(text: str) -> None:
                if text:
                    emit({"content": text})

            def emit_tool_call(call: dict[str, Any]) -> None:
                key = _call_key(call["name"], call["arguments"])
                if key in seen_calls:
                    return
                seen_calls.add(key)
                tc = {"index": len(tool_calls), "id": "call_" + uuid.uuid4().hex[:24],
                      "type": "function", "function": {"name": call["name"],
                      "arguments": json.dumps(call["arguments"], ensure_ascii=False)}}
                tool_calls.append(tc)
                emit({"tool_calls": [tc]})

            parser = ToolCallParser(emit_content, emit_tool_call) if emulate_tools else None
            while True:
                # HTTPResponse.readline(), а не resp.fp: корректно декодирует chunked HTTP.
                line = resp.readline()
                if not line:
                    break
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    break
                event = json.loads(data)
                if not isinstance(event, dict):
                    raise ValueError("google response is not a JSON object")
                if event.get("error"):
                    tail = _clean_err(json.dumps(event["error"], ensure_ascii=False))
                    self._sse_error(_error_payload(f"google upstream stream failed: {tail}", tail))
                    return
                um = event.get("usageMetadata") or {}
                for source, target in (("promptTokenCount", "input"), ("candidatesTokenCount", "output"),
                                       ("cachedContentTokenCount", "cached"),
                                       ("thoughtsTokenCount", "reasoning")):
                    if source in um:
                        usage[target] = int(um[source] or 0)
                for cand in event.get("candidates") or []:
                    if cand.get("finishReason"):
                        finish_reason = cand["finishReason"]
                    for part in (cand.get("content") or {}).get("parts") or []:
                        text = part.get("text")
                        if not isinstance(text, str) or not text:
                            continue
                        if part.get("thought") is True:
                            had_reasoning = True
                            emit({"reasoning_content": text})
                        else:
                            collected_texts.append(text)
                            if parser is not None:
                                parser.feed(text)
                            else:
                                emit_content(text)
                if parser is not None and tool_calls:
                    if not parser.has_open_tool_call() and (
                            parser.trailing_chars_after_tool > 512
                            or _detect_repetition_loop("".join(collected_texts)) is not None):
                        _log("google stream: stopping after tool_call emission (trailing/loop detected)")
                        break
                elif (parser is None or not parser.has_open_tool_call()) \
                        and _detect_repetition_loop("".join(collected_texts)) is not None:
                    _log("google stream: repetition loop detected, stopping stream")
                    break
            if parser is not None:
                parser.finish()
            if not collected_texts and not tool_calls and not had_reasoning:
                self._sse_error(_error_payload("google upstream produced no text"))
                return
            reasoning_tokens = usage.get("reasoning", 0)
            prompt_tokens = usage.get("input", 0) or _estimate_tokens(prompt)
            completion_tokens = (usage.get("output", 0) + reasoning_tokens) or _estimate_tokens(
                "".join(collected_texts))
            final = format_sse_chunk(resp_id, created, model, {},
                finish_reason="tool_calls" if tool_calls else ("length" if finish_reason == "MAX_TOKENS" else "stop"),
                usage=_build_openai_usage(prompt_tokens, completion_tokens,
                                          usage.get("cached", 0), reasoning_tokens))
            self.wfile.write(final.encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            _log(f"google stream done model={model} tools={len(tool_calls)} out_chars={sum(map(len, collected_texts))}")
        except (OSError, ValueError, TypeError, AttributeError, http.client.HTTPException) as exc:
            tail = _clean_err(str(exc))
            _log(f"google stream failed: {tail}")
            if started:
                try:
                    self._sse_error(_error_payload(f"google stream failed: {tail}", tail))
                except OSError:
                    pass
        finally:
            if conn is not None:
                conn.close()
            with _active_lock:
                _active.pop(run_id, None)
            res.slots.release()

    def _stream_sse(self, model: str, prompt: str, effort: str, emulate_tools: bool = False,
                    tools: list[dict[str, Any]] | None = None,
                    google_input: GoogleInput | None = None, reported_model: str | None = None,
                    tool_choice: Any = None) -> None:
        shown_model = reported_model or model
        if _is_google_direct_model(model):
            self._stream_google_sse(model, prompt, effort, emulate_tools, google_input)
            return
        xs = self._exit()
        launcher = _resolve_launcher()
        if not os.access(launcher, os.X_OK):
            xs["exit_reason"] = "launcher_missing"
            self._send(502, {"error": {"message": f"opencode launcher not executable: {launcher}",
                                       "type": "proxy_error", "code": 502}})
            return

        res = self._res()
        if not self._acquire_slot(res):
            return
        attempts = _RequestAttempts(res, time.monotonic() + TIMEOUT_S)
        xs["attempts"] = attempts

        resp_id = f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        self.close_connection = True

        workdir = DEFAULTWORKDIR
        workdir.mkdir(parents=True, exist_ok=True)
        model_route = _model_route(model)

        cmd, shown = _build_cmd(launcher, model, effort)
        _log(f"stream exec model={model_route} {shown} prompt_chars={len(prompt)} cwd={workdir}")

        proc: subprocess.Popen[str] | None = None
        feed: _StdoutFeed | None = None
        gate: _StartupGate | None = None
        run_id = uuid.uuid4().hex[:8]

        try:
            if not attempts.begin_attempt():
                xs["exit_reason"] = "circuit_open"
                self._send(503, {"error": {"message": "upstream circuit open", "type": "overloaded"}})
                return

            # 1. Отправляются HTTP-заголовки 200 SSE
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            xs["status"] = 200

            # 2. Отправляется первый чанк
            first_chunk = format_sse_chunk(
                resp_id, created, shown_model, {"role": "assistant", "content": ""}
            )
            self.wfile.write(first_chunk.encode("utf-8"))
            self.wfile.flush()

            collected_texts: list[str] = []
            usage: dict[str, Any] = {}
            deadline = attempts.deadline
            tool_calls: list[dict[str, Any]] = []

            # Повтор незавершённого шага: уже отданный клиенту текст (dedup_prefix) подавляется,
            # расхождение (модель переформулировала) отдаётся целиком — текст не теряется.
            dedup: list[_PrefixDedup | None] = [None]

            def send_text(text: str) -> None:
                chunk = format_sse_chunk(resp_id, created, shown_model, {"content": text})
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()
                collected_texts.append(text)  # только реально отданное клиенту

            def emit_content(text: str) -> None:
                if not text:
                    return
                prefix_dedup = dedup[0]
                if prefix_dedup is not None:
                    text = prefix_dedup.push(text)
                    if not text:
                        return
                send_text(text)

            dropped_blocks = [0]  # вырезано нераспарсенных блоков вызова (счётчик на запрос)

            def emit_parsed_content(text: str) -> None:
                # Нераспарсенный блок ToolCallParser отдаёт одним куском: сырой тег не уходит ни в SSE, ни в повтор.
                cleaned, dropped = _strip_broken_tool_blocks(text)
                if dropped:
                    dropped_blocks[0] += dropped
                    _log(f"stream dropped {dropped} unparsed tool block(s) from content")
                emit_content(cleaned)

            seen_calls: set[str] = set()

            def emit_tool_call(call: dict[str, Any]) -> None:
                key = _call_key(call["name"], call["arguments"])
                if key in seen_calls:
                    _log(f"stream dropped duplicate tool call {call['name']}")
                    return
                seen_calls.add(key)
                tc = {
                    "index": len(tool_calls),
                    "id": "call_" + uuid.uuid4().hex[:24],
                    "type": "function",
                    "function": {"name": call["name"],
                                 "arguments": json.dumps(call["arguments"], ensure_ascii=False)},
                }
                tool_calls.append(tc)
                chunk = format_sse_chunk(resp_id, created, shown_model, {"tool_calls": [tc]})
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()

            with _active_lock:
                _active[run_id] = time.time()

            attempt_prompt = prompt
            retries = 0  # повторов с новым промптом: встроенный инструмент / незавершённый шаг (для лога)
            unmapped_retries = 0
            incomplete_retries = 0
            fail_retries = 0
            incomplete_retry = False
            failure: dict[str, Any] | None = None
            while True:
                # 3. Запускается proc (повтор — встроенный инструмент без DSH-двойника,
                #    незавершённый шаг или транзиторный отказ CLI без вывода) под потолком MAX_TOTAL_SPAWNS
                if attempts.total_spawns:
                    _log(f"stream exec retry={retries} fail_retries={fail_retries} model={model_route} "
                         f"prompt_chars={len(attempt_prompt)} total_spawns={attempts.total_spawns}/{attempts.max_total}")
                gate = _StartupGate()
                gate.acquire()
                if not res.spawn_limiter.acquire(max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())):
                    gate.release()
                    _log("stream spawn skipped: spawn rate limiter wait exceeds the request deadline")
                    if not collected_texts and not tool_calls:
                        failure = {"rc": -1, "tail": "", "timeout": True}
                    break
                try:
                    # env на каждую попытку: ретрай получает следующий порт пула (чистый IP)
                    proc = _spawn_with_stdin(cmd, attempt_prompt, workdir, _run_env(model))
                except OSError as exc:
                    gate.release()
                    _log(f"stream spawn failed: {exc}")
                    xs["exit_reason"] = "spawn_failed"
                    self._sse_error(_error_payload(f"opencode spawn failed: {exc}"))
                    return
                attempts.note_spawn()

                err_lines: list[str] = []

                err_thread = threading.Thread(target=_drain_stderr, args=(proc, err_lines), daemon=True)
                err_thread.start()

                parser = ToolCallParser(emit_parsed_content, emit_tool_call) if emulate_tools else None
                attempt_texts: list[str] = []
                attempt_reasonings: list[str] = []
                unmapped: list[str] = []
                attempt_output = False  # любой полезный вывод этого прогона (текст/мышление/инструмент)
                attempt_output_tokens = 0  # output из step_finish этого прогона (для проглоченных вызовов)
                attempt_reasoning_tokens = 0  # reasoning из step_finish (output включает reasoning)
                provider_status: int | None = None
                had_provider_error = False  # транзиентная ошибка посреди ответа (had_mid_stream_error)
                fatal_mid_error = False  # детерминированная ошибка посреди ответа: без повтора
                stopped_on_error = False
                prior_text = "".join(collected_texts)
                dedup[0] = _PrefixDedup(prior_text) if incomplete_retry and prior_text else None

                def send_keepalive(proc: subprocess.Popen[str] = proc) -> None:
                    # Парсируемый chat.completion.chunk с пустой дельтой: сбрасывает клиентские
                    # watchdog'и стрима (комментарий `: keepalive` их не сбрасывает).
                    try:
                        keepalive = format_sse_chunk(resp_id, created, shown_model, {"content": ""})
                        self.wfile.write(keepalive.encode("utf-8"))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        _log("stream client gone during keepalive, killing proc group")
                        _stop_proc(proc)
                        raise

                feed = _StdoutFeed(proc)
                for raw in feed.lines(deadline, KEEPALIVE_INTERVAL_S, send_keepalive):
                    gate.release()
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        _log(f"non-json stdout line: {raw[:100]}")
                        continue

                    etype, payload = parse_opencode_event(event)
                    if etype == "reasoning":
                        rtext = payload.get("reasoning_content")
                        if isinstance(rtext, str):
                            rtext = _strip_interrupted(rtext)
                            if rtext:
                                payload["reasoning_content"] = rtext
                            else:
                                del payload["reasoning_content"]
                        if payload:
                            attempt_output = True
                            if isinstance(rtext, str) and rtext:
                                attempt_reasonings.append(rtext)
                            chunk_str = format_sse_chunk(resp_id, created, shown_model, payload)
                            self.wfile.write(chunk_str.encode("utf-8"))
                            self.wfile.flush()
                    elif etype == "text":
                        ttext = payload.get("content")
                        if isinstance(ttext, str):
                            ttext = _strip_interrupted(ttext)
                        if isinstance(ttext, str) and ttext:
                            attempt_output = True
                            if retries and not incomplete_retry and not attempt_texts and collected_texts:
                                emit_content("\n\n")
                            attempt_texts.append(ttext)
                            if parser is not None:
                                parser.feed(ttext)
                            else:
                                emit_content(ttext)
                    elif etype == "step_finish":
                        if payload:
                            for key in ("input", "output", "cached", "reasoning"):
                                usage[key] = int(usage.get(key) or 0) + int(payload.get(key) or 0)
                            attempt_output_tokens += int(payload.get("output") or 0)
                            attempt_reasoning_tokens += int(payload.get("reasoning") or 0)
                        if emulate_tools and tool_calls:
                            # Следующие шаги — реакция на «отклонение» (повтор вызова): не нужны.
                            _log("stream: step with tool call finished, stopping opencode run")
                            _stop_proc(proc)
                            break
                    elif etype == "error":
                        _log(f"stream provider error: HTTP {payload.get('statusCode')}: {payload.get('message')}")
                        if isinstance(payload.get("statusCode"), int):
                            provider_status = payload["statusCode"]
                        err_lines.append(f"HTTP {payload.get('statusCode')}: {payload.get('message')}")
                        if attempt_output:
                            # Оборванный ответ: иначе opencode сам запустит SYNTHETIC-шаг «Continue…» —
                            # останавливаем сразу. Транзиентная ошибка -> повтор шага, детерминированная
                            # (401…) -> ошибка клиенту без повтора. Ошибка до первого токена — не трогаем:
                            # opencode повторит сам или выйдет, и тогда флаг не должен «залипнуть».
                            if _is_transient_stream_error(payload):
                                had_provider_error = True
                            else:
                                fatal_mid_error = True
                            _log(f"stream: provider error mid-response (transient={had_provider_error}), "
                                 "stopping opencode run")
                            stopped_on_error = True
                            _stop_proc(proc)
                            break
                        _log("stream: early provider error (waiting for CLI recovery)")
                    elif etype == "tool_use":
                        attempt_output = True
                        part = _dict_or_empty(event.get("part"))
                        tstate = _dict_or_empty(part.get("state"))
                        calls = (_native_to_tool_calls(part.get("tool"), tstate.get("input"), tools or [])
                                 if emulate_tools else [])
                        _log(f"opencode built-in tool event: tool={part.get('tool')} status={tstate.get('status')} "
                             f"mapped={bool(calls)} as={[c['name'] for c in calls]}")
                        if calls:
                            if parser is not None:
                                parser.finish()
                            for call in calls:
                                emit_tool_call(call)
                        elif emulate_tools:
                            unmapped.append(str(part.get("tool")))

                if feed.overflowed:
                    # Читатель уже остановил процесс (stdout_overflow): попытка неуспешна, данные не дропаются молча.
                    had_provider_error = True
                    stopped_on_error = True
                    err_lines.append("stdout queue overflow")
                timed_out = feed.timed_out
                if timed_out:
                    _log(f"stream timeout after {TIMEOUT_S:.0f}s, killing proc group")
                    _stop_proc(proc)

                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except OSError:
                        pass

                err_thread.join(timeout=5)
                feed.join(timeout=5)
                if parser is not None:
                    parser.finish()
                prefix_dedup = dedup[0]
                dedup[0] = None
                if prefix_dedup is not None:
                    leftover = prefix_dedup.finish()
                    if leftover:
                        send_text(leftover)
                feed.close()
                try:
                    if proc.stderr is not None:
                        proc.stderr.close()
                except OSError:
                    pass

                gate.release()
                rc = proc.returncode if proc.returncode is not None else -1
                if stopped_on_error and rc < 0:
                    rc = 1  # остановили сами после ошибки провайдера: для классификации отказа — как выход CLI
                tail = _clean_err(err_lines[-6:])
                transient_failure = had_provider_error or (
                    not attempt_output and _is_retryable_failure(rc, tail, provider_status, False))
                attempts.attempt_done(transient_failure, attempt_output and not transient_failure)
                if timed_out:
                    failure = {"rc": rc, "tail": "", "timeout": True}
                    break
                if rc != 0 and not attempt_output:
                    _log(f"stream cli failed rc={rc} stderr_tail={tail!r}")
                    if (fail_retries < FAIL_RETRY_LIMIT and time.monotonic() < deadline
                            and _is_retryable_failure(rc, tail, provider_status, bool(tool_calls))
                            and attempts.allow_retry("cli_failure", charge_budget=provider_status is not None)):
                        fail_retries += 1
                        _log(f"stream retry {fail_retries}/{FAIL_RETRY_LIMIT} after cli failure without output")
                        continue
                    if not collected_texts and not tool_calls:
                        failure = {"rc": rc, "tail": tail}
                        break

                if fatal_mid_error and not tool_calls:
                    failure = {"rc": rc, "tail": tail, "partial": True}
                    break
                if not emulate_tools or tool_calls or time.monotonic() > deadline:
                    break
                if unmapped:
                    if unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("unmapped"):
                        _log(f"stream unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})")
                        emit_content(f"\n\n[opencode-zen-bridge: модель вызывала недоступный встроенный "
                                     f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]")
                        break
                    retries += 1
                    unmapped_retries += 1
                    incomplete_retry = False
                    _log(f"stream unmapped built-in tools={unmapped}: re-prompt "
                         f"{unmapped_retries}/{NATIVE_RETRY_LIMIT}")
                    attempt_prompt = _rewrite_tool_tags_for_model(_unavailable_tools_prompt(
                        attempt_prompt, "".join(attempt_texts), unmapped, tools or [], model), model)
                    continue
                signal = 0 if provider_status in _FATAL_HTTP else _incomplete_step_signal(
                    "".join(attempt_texts), "".join(attempt_reasonings), tools or [],
                    had_provider_error, attempt_output_tokens, attempt_reasoning_tokens,
                    tool_choice=tool_choice)
                if not signal:
                    break
                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("incomplete_step"):
                    _log(f"stream incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}")
                    break
                retries += 1
                incomplete_retries += 1
                incomplete_retry = True
                attempts.signal = signal
                _log(f"stream incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
                     f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}")
                attempt_prompt = _rewrite_tool_tags_for_model(_incomplete_tool_step_prompt(
                    prompt, "".join(collected_texts), tools or [], tool_choice, model), model)

            if failure is not None:
                _log(f"stream failed model={model} rc={failure['rc']} fail_retries={fail_retries} "
                     f"total_spawns={attempts.total_spawns}")
                if failure.get("timeout"):
                    xs["exit_reason"] = "timeout"
                    self._sse_error(_error_payload(f"opencode timed out after {TIMEOUT_S:.0f}s"))
                    return
                xs["exit_reason"] = "provider_fatal" if failure.get("partial") else "upstream_failed"
                what = ("opencode provider error after partial output" if failure.get("partial")
                        else "opencode run failed")
                self._sse_error(_error_payload(
                    f"{what} (rc={failure['rc']})"
                    + ("" if failure.get("partial") else " without output")
                    + (f": {failure['tail']}" if failure["tail"] else ""), failure["tail"]))
                return

            if dropped_blocks[0] and not tool_calls and not "".join(collected_texts).strip():
                emit_content(_BROKEN_BLOCK_NOTICE)  # иначе клиент получил бы пустой ответ
            full_text = "".join(collected_texts)
            prompt_tokens = int(usage.get("input") or 0) or _estimate_tokens(prompt)
            completion_tokens = int(usage.get("output") or 0) or _estimate_tokens(full_text)

            final_chunk = format_sse_chunk(
                resp_id,
                created,
                shown_model,
                {},
                finish_reason="tool_calls" if tool_calls else "stop",
                usage=_build_openai_usage(prompt_tokens, completion_tokens,
                                          int(usage.get("cached") or 0), int(usage.get("reasoning") or 0)),
            )
            self.wfile.write(final_chunk.encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            xs.update(exit_reason="ok", tools=len(tool_calls), out_chars=len(full_text), rc=proc.returncode)
            _log(f"stream done model={model} rc={proc.returncode} tools={len(tool_calls)} "
                 f"out_chars={len(full_text)} emulate_tools={emulate_tools} retries={retries} "
                 f"total_spawns={attempts.total_spawns}")

        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            _log(f"client gone mid-stream: {exc}")
            xs["exit_reason"] = "client_gone"
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                except OSError:
                    pass
        finally:
            if gate is not None:
                gate.release()
            if proc is not None:
                if feed is not None:
                    feed.close()
                try:
                    if proc.stderr is not None:
                        proc.stderr.close()
                except OSError:
                    pass
                if proc.poll() is None:
                    try:
                        proc.kill()
                    except OSError:
                        pass
            with _active_lock:
                _active.pop(run_id, None)
            attempts.commit()
            res.slots.release()

    def _serve_json(self, model: str, prompt: str, effort: str, emulate_tools: bool = False,
                    tools: list[dict[str, Any]] | None = None,
                    google_input: GoogleInput | None = None, reported_model: str | None = None,
                    tool_choice: Any = None) -> None:
        xs = self._exit()
        contents: list[str] = []
        reasonings: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        tokens: dict[str, int] = {}
        attempt_prompt = prompt
        retries = 0  # повторов с новым промптом: встроенный инструмент / незавершённый шаг (для лога)
        unmapped_retries = 0
        incomplete_retries = 0
        incomplete_retry = False
        out: dict[str, Any] = {}
        dropped_blocks = 0  # вырезано нераспарсенных блоков вызова
        res = self._res()
        if not self._acquire_slot(res):
            return
        attempts = _RequestAttempts(res, time.monotonic() + TIMEOUT_S,
                                    use_breaker=not _is_google_direct_model(model))
        xs["attempts"] = attempts
        try:
            if not attempts.begin_attempt():
                xs["exit_reason"] = "circuit_open"
                self._send(503, {"error": {"message": "upstream circuit open", "type": "overloaded"}})
                return
            while True:
                if retries:
                    _log(f"exec retry={retries} ({'incomplete tool step' if incomplete_retry else 'unmapped built-in tool'})"
                         f" total_spawns={attempts.total_spawns}/{attempts.max_total}")
                run = Run(model, attempt_prompt, effort, DEFAULTWORKDIR,
                          tools=(tools or []) if emulate_tools else None, google_input=google_input,
                          attempts=attempts, resilience=res)
                try:
                    out = run.execute()
                finally:
                    run.close()

                if out.get("state") in ("launcher_missing", "spawn_failed", "client_gone"):
                    xs["exit_reason"] = str(out["state"])
                    self._send(502, {"error": {"message": out.get("err") or out["state"],
                                               "type": "proxy_error", "code": 502}})
                    return
                content = out["text"]
                if emulate_tools and content:
                    content, calls = _split_tool_calls(out.get("chunks") or [content])
                    tool_calls.extend(calls)
                    # Безусловно (и при calls): пачка из валидного и битого блока не вернёт битый в content.
                    content, dropped = _strip_broken_tool_blocks(content)
                    if dropped:
                        dropped_blocks += dropped
                        _log(f"dropped {dropped} unparsed tool block(s) from content")
                        if not content.strip():
                            content = ""
                if incomplete_retry:
                    # Уже отданная преамбула подавляется, переформулированный текст сохраняется целиком.
                    content = _dedup_retry_text("\n\n".join(c for c in contents if c), content)
                if content:
                    contents.append(content)
                if out.get("reasoning"):
                    reasonings.append(out["reasoning"])
                for key in ("input", "output", "cached", "reasoning"):
                    tokens[key] = tokens.get(key, 0) + int((out.get("usage") or {}).get(key) or 0)
                unmapped: list[str] = []
                if emulate_tools:
                    for native in out.get("native_calls") or []:
                        calls = _native_to_tool_calls(native.get("tool"), native.get("input"), tools or [])
                        _log(f"opencode built-in tool event: tool={native.get('tool')} status={native.get('status')} "
                             f"mapped={bool(calls)} as={[c['name'] for c in calls]}")
                        if not calls:
                            unmapped.append(str(native.get("tool")))
                        for call in calls:
                            tool_calls.append({
                                "index": len(tool_calls), "id": "call_" + uuid.uuid4().hex[:24], "type": "function",
                                "function": {"name": call["name"],
                                             "arguments": json.dumps(call["arguments"], ensure_ascii=False)}})
                if out.get("fatal_error") and not tool_calls:
                    tail = _clean_err(str(out.get("err") or ""), 500)
                    xs["exit_reason"] = "provider_fatal"
                    self._send(502, _error_payload(
                        f"opencode provider error after partial output (HTTP {out.get('provider_status')})"
                        + (f": {tail}" if tail else ""), tail))
                    return
                if not emulate_tools or tool_calls:
                    break
                if unmapped:
                    if unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("unmapped"):
                        _log(f"unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})")
                        contents.append(f"[opencode-zen-bridge: модель вызывала недоступный встроенный "
                                        f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]")
                        break
                    retries += 1
                    unmapped_retries += 1
                    incomplete_retry = False
                    _log(f"unmapped built-in tools={unmapped}: re-prompt {unmapped_retries}/{NATIVE_RETRY_LIMIT}")
                    attempt_prompt = _rewrite_tool_tags_for_model(
                        _unavailable_tools_prompt(attempt_prompt, out["text"], unmapped, tools or [], model), model)
                    continue
                run_usage = out.get("usage") or {}
                signal = 0 if out.get("provider_status") in _FATAL_HTTP else _incomplete_step_signal(
                    out["text"], str(out.get("reasoning") or ""), tools or [],
                    bool(out.get("had_error")), int(run_usage.get("output") or 0),
                    int(run_usage.get("reasoning") or 0), tool_choice=tool_choice)
                if not signal:
                    break
                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("incomplete_step"):
                    _log(f"incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}")
                    break
                retries += 1
                incomplete_retries += 1
                incomplete_retry = True
                attempts.signal = signal
                _log(f"incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
                     f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}")
                attempt_prompt = _rewrite_tool_tags_for_model(_incomplete_tool_step_prompt(
                    prompt, "\n\n".join(c for c in contents if c), tools or [], tool_choice, model), model)
        finally:
            attempts.commit()
            res.slots.release()

        seen_calls: set[str] = set()
        unique_calls: list[dict[str, Any]] = []
        for tc in tool_calls:
            key = _call_key(tc["function"]["name"], json.loads(tc["function"]["arguments"] or "{}"))
            if key in seen_calls:
                _log(f"dropped duplicate tool call {tc['function']['name']}")
                continue
            seen_calls.add(key)
            unique_calls.append(tc)
        tool_calls = unique_calls
        for i, tc in enumerate(tool_calls):
            tc["index"] = i
        content = "\n\n".join(c for c in contents if c)
        if dropped_blocks and not content.strip() and not tool_calls:
            content = _BROKEN_BLOCK_NOTICE  # иначе клиент получил бы пустой ответ или 502
        if not content and not tool_calls:
            # Пустой текст с ненулевым rc/ошибкой провайдера — честная 502, не выдуманный ответ.
            tail = _clean_err(str(out.get("err") or ""), 500)
            xs["exit_reason"] = "upstream_failed"
            self._send(502, _error_payload(
                f"opencode run produced no text (rc={out.get('rc')}, state={out.get('state')})"
                + (f": {tail}" if tail else ""), tail))
            return

        prompt_tokens = int(tokens.get("input") or 0) or _estimate_tokens(prompt)
        completion_tokens = int(tokens.get("output") or 0) or _estimate_tokens(content)

        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if reasonings:
            msg["reasoning_content"] = "".join(reasonings)
        finish = "length" if out.get("finish") == "length" else "stop"
        if tool_calls:
            msg["tool_calls"] = tool_calls
            finish = "tool_calls"
        xs.update(exit_reason="ok", tools=len(tool_calls), out_chars=len(content), rc=out.get("rc"))
        _log(f"done model={model} rc={out.get('rc')} state={out.get('state')} tools={len(tool_calls)} "
             f"out_chars={len(content)} retries={retries} total_spawns={attempts.total_spawns}")

        self._send(200, {
            "id": f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
            "created": int(time.time()), "model": reported_model or model,
            "choices": [{"index": 0,
                         "message": msg,
                         "finish_reason": finish}],
            "usage": _build_openai_usage(prompt_tokens, completion_tokens,
                                         tokens.get("cached", 0), tokens.get("reasoning", 0)),
        })

    # ---- HTTP --------------------------------------------------------------------
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/v1/health"):
            _maybe_reload_catalog()
            with _active_lock:
                active = len(_active)
            self._send(200, {
                "ok": True, "transport": "opencode-zen-cli",
                "models": sorted(ALLOWED_MODELS), "default_model": _effective_default_model(),
                "catalog_mode": CATALOG_MODE, "catalog_source": CATALOG_SOURCE,
                "active": active, "max_concurrent": MAX_CONCURRENT,
                "stream": True, "tool_emulation": True,
                "uptime_s": int(time.time() - _started),
            })
            return
        if not _auth_ok(self):
            self._send(401, {"error": {"message": "unauthorized", "type": "auth_error"}})
            return
        if path in ("/v1/models", "/models"):
            _maybe_reload_catalog()
            self._send(200, {"object": "list", "data": [
                {"id": mid, "object": "model", "owned_by": "opencode-zen", "created": 0,
                 "context_length": meta["context_length"], "max_output": meta["max_output"],
                 "reasoning_efforts": list(meta.get("reasoning_efforts") or [])}
                for mid, meta in sorted(ALLOWED_MODELS.items())
            ]})
            return
        self._send(404, {"error": {"message": f"not found: {path}"}})

    def do_POST(self) -> None:
        xs = self._xs = _new_exit_state()
        try:
            self._handle_post(xs)
        finally:
            _log_exit(xs)

    def _handle_post(self, xs: dict[str, Any]) -> None:
        if not _auth_ok(self):
            # Непрочитанное тело иначе будет разобрано как следующий запрос keep-alive.
            self.close_connection = True
            xs["exit_reason"] = "unauthorized"
            self._send(401, {"error": {"message": "unauthorized", "type": "auth_error"}})
            return
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        if path in ("/v1/models/reload", "/models/reload"):
            result = reload_catalog()
            _log(f"catalog reload source={result['source']} models={len(result['models'])}")
            xs["exit_reason"] = "catalog_reload"
            self._send(200, result)
            return
        try:
            req = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            xs["exit_reason"] = "bad_request"
            self._send(400, {"error": {"message": "invalid json"}})
            return
        if path not in ("/v1/chat/completions", "/chat/completions"):
            xs["exit_reason"] = "not_found"
            self._send(404, {"error": {"message": f"not found: {path}"}})
            return

        _maybe_reload_catalog()
        model = str(req.get("model") or "").strip() or _effective_default_model()
        requested_model = model
        xs["model"] = model
        xs["mode"] = "stream" if req.get("stream") is True else "json"
        if model not in ALLOWED_MODELS:
            alias_target = _resolve_alias(model)
            if alias_target is not None:
                _log(f"alias {model} -> {alias_target}")
                model = alias_target
        if model not in ALLOWED_MODELS:
            xs["exit_reason"] = "bad_request"
            self._send(400, {"error": {
                "message": f"unknown model '{model}'; allowed: {sorted(ALLOWED_MODELS)}",
                "type": "invalid_request_error", "code": "model_not_found"}})
            return

        raw_tools = req.get("tools")
        tools = [t for t in raw_tools if isinstance(t, dict)] if isinstance(raw_tools, list) else []
        tool_choice = req.get("tool_choice")
        emulate_tools = bool(tools) and not _tool_choice_none(tool_choice)

        system_text, prompt = _messages_to_prompt(req.get("messages") or [])
        if not prompt:
            xs["exit_reason"] = "bad_request"
            self._send(400, {"error": {"message": "no user content", "type": "invalid_request_error"}})
            return
        head: list[str] = []
        if system_text:
            head.append(f"[system]\n{system_text}")
        if emulate_tools:
            head.append(_tools_section(tools, tool_choice, model))
        elif raw_tools and not system_text:
            head.append(f"[system]\n{DEFAULT_SYSTEM_HINT}")
        google_input: GoogleInput | None = None
        if _is_google_direct_model(model):
            system_head = "\n\n".join(part.removeprefix("[system]\n") for part in head)
            google_input = _messages_to_google_contents(req.get("messages") or [], system_head)
        history = prompt
        if head:
            prompt = "\n\n".join(head) + f"\n\n{prompt}"
        if emulate_tools:
            reminder = _tools_tail_reminder(history, tools, tool_choice, model)
            if reminder:
                prompt += f"\n\n{reminder}"

        prompt = _rewrite_tool_tags_for_model(prompt, model)
        effort = _map_effort(req, model)
        if req.get("stream") is True:
            self._stream_sse(model, prompt, effort, emulate_tools, tools, google_input,
                             reported_model=requested_model, tool_choice=tool_choice)
        else:
            self._serve_json(model, prompt, effort, emulate_tools, tools, google_input,
                             reported_model=requested_model, tool_choice=tool_choice)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: Any, handler_class: Any, *args: Any,
                 resilience: _Resilience | None = None, **kwargs: Any) -> None:
        # Защиты process-level: прод передаёт модульный набор (main), тесты получают изолированный.
        self.resilience = resilience or _Resilience()
        super().__init__(server_address, handler_class, *args, **kwargs)


def main() -> int:
    if not AUTH_KEY:
        sys.stderr.write("OPENCODE_ZEN_BRIDGE_KEY is required; refusing to start\n")
        return 2
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log(f"workspace mkdir failed: {exc}")
    _log(f"start host={HOST} port={PORT} catalog={CATALOG_MODE}/{CATALOG_SOURCE} "
         f"models={sorted(ALLOWED_MODELS)} launcher={_resolve_launcher()}")
    server = Server((HOST, PORT), Handler, resilience=_DEFAULT_RESILIENCE)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
