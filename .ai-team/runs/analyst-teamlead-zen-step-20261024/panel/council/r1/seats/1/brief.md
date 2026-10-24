# Бриф судьи Совета Тимлидов по коду (code-panel, Раунд 1, Seat 1: Скептик (Adversarial / Failure Modes & High-Load Invariants))

- **Run ID:** `analyst-teamlead-zen-step-20261024`
- **Раунд:** `council` / `r1` (`code-panel`, приёмка реализации по одобренному Архитектурным Советом пакету `v5`)
- **Роль судьи:** `skeptic` — Скептик (Adversarial / Failure Modes & High-Load Invariants)
- **Слот / модель:** `muse-wonder-full-1.0` (`Meta`, транспорт `muse`)
- **Проверяемый артефакт:** `bridges/opencode-zen-bridge/server.py` (`sha256=90b1d66499dceadac24f7990423b4c53b2ebd5b23247aaf50efe187851598b9e`)

## 1. Контекст и предмет приёмки

Архитектурный Совет (`panel/arch/r2`) единогласно (`3/3 ACCEPT`, `verify_panel_proof exit=0`) утвердил архитектурный пакет `v5` (`architecture-packet.json`, `sha256=1053a4ca2e97d0eba0f350c3a71e13d8810c1a716e3b1e66a6c7ff0097e4f565`).
Сабагент `Coder` (`claude-sonnet-5-5`, `high`, `claude-cli`) реализовал пакет `v5` в `bridges/opencode-zen-bridge/server.py` (`sha256=90b1d66499dceadac24f7990423b4c53b2ebd5b23247aaf50efe187851598b9e`) и `bridges/opencode-zen-bridge/tests/test_step_interruption.py`:

1. **`AD-001` / `REQ-001`:** Поддержка `<tool_invoke>` и `<tool_call>` в `ToolCallParser` и `_parse_tool_call_blocks`, алиас `"shell"` в `NATIVE_TOOL_ALIASES`.
2. **`AD-002` / `REQ-002` / `REQ-003`:** Классификатор транзиентных ошибок `_is_transient_stream_error` (`400/401/403/404/422` не ретраятся), детектор `_detect_incomplete_tool_step_signal` (`1..5`) и `_is_incomplete_tool_step` с вычитанием `reasoning_tokens`, суженным признаком 5 (требует `_ACTION_INTENT_RE`; короткие ответы `"Ответ: 42:"` возвращают `0`), защитой `_no_tools_overridden` от ложного подавления при цитировании `Rule 0` в начале `reasoning` и отдельным kill-switch `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY`.
3. **`AD-003` / `REQ-004` / `REQ-005`:** Ограниченная очередь `_StdoutFeed(maxsize=4096)` с остановкой процесса при `queue.Full`, потолок `MAX_TOTAL_SPAWNS = 3` (`A_max = 3`) на HTTP-запрос, Full-Jitter backoff `_retry_backoff_s`, сохранение полного текста при несовпадении `dedup_prefix`.
4. **`AD-004` / `CD-003`:** `_SlotBulkhead(max_concurrent=6, max_waiters=12, wait_timeout_s=15.0)`, `_StartupGate(wait_s=5.0)` fail-open, `_SpawnRateLimiter(1.0/s)`, `_RetryBudget(capacity=6)`, `_UpstreamBreaker` (`HALF_OPEN = 1` проба) и структурное логирование `O-EXIT/v1` на всех выходах `do_POST`.
5. **Верификация:** `441` тест моста (`uvx pytest -q tests/`) — `0` падений; `177` тестов в `test_step_interruption.py` (включая `clean-room`, `9` тестов `VER-005` и `26` тестов `HlResilienceOracles`) — `OK`; `VER-004` (`diff -u` репо vs `~/.dsh/bridges/opencode-zen-bridge/server.py`) — `exit=0`.

## 2. Инструкция по формату ответа судьи

1. Первые две непустые строки ответа заполняются по системному требованию лаунчера (`PANEL-NONCE` и `ARTIFACT-SHA256`).
2. Оцените соответствие кода `server.py` и тестов `test_step_interruption.py` утверждённому архитектурному пакету `v5` с позиции вашей роли (`skeptic`).
3. В конце ответа укажите канонический блок:
   - Если блокеров нет: `FINDINGS: NONE` и на следующей строке `VERDICT: ACCEPT`.
   - Если обнаружены критические блокеры: перечислите их как `F1..Fn` и на последней строке укажите `VERDICT: NEEDS WORK` (или `VERDICT: RED FLAG`).

## 3. Встроенные артефакты (D9)

<<<ARTIFACT path="bridges/opencode-zen-bridge/server.py" sha256="90b1d66499dceadac24f7990423b4c53b2ebd5b23247aaf50efe187851598b9e" bytes="194256">>>
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
    partial = _strip_interrupted(partial_text).strip()
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


def _loads_lenient(text: str) -> Any:
    """json.loads с допуском сырых управляющих символов (\\n, \\t) внутри строк.

    Порт из droid-bridge (08.10): модели кладут многострочные команды в JSON-строку
    без экранирования переводов строк; строгий json.loads их отвергает, и вызов
    утекал в content текстом. Сначала строгий разбор, затем strict=False.
    """
    try:
        return json.loads(text)
    except ValueError:
        return json.loads(text, strict=False)


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


def _parse_tool_call_block(inner: str) -> dict[str, Any] | None:
    """Содержимое блока -> {"name","arguments"}; None, если блок невалиден.

    Отсутствие ключа arguments — допустимый вызов с {}; присутствующее, но
    не-объектное значение (строка-не-JSON, список, число, null) — вызов
    отклоняем, чтобы не запускать инструмент с пустыми аргументами.
    """
    try:
        obj = _loads_lenient(_strip_code_fence(inner))
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
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


def _parse_tool_call_blocks(inner: str) -> list[dict[str, Any]] | None:
    """Содержимое блока -> список вызовов; None, если блок (или любой его член) невалиден.

    Обычный блок даёт один вызов. Если он не разбирается, но внутри есть
    несколько открывающих тегов без промежуточных закрывающих, блок делится на
    сегменты; пачка принимается только целиком (все сегменты валидны).
    """
    single = _parse_tool_call_block(inner)
    if single is not None:
        return [single]
    if not any(open_tag in inner for open_tag, _ in TOOL_CALL_TAGS):
        return None
    segments = _split_tool_call_inner(inner)
    if len(segments) < 2:
        return None
    calls: list[dict[str, Any]] = []
    for segment in segments:
        call = _parse_tool_call_block(segment)
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
        """Позиция закрывающего тега вне строковых литералов JSON, или -1.

        Закрывающий тег внутри JSON-строки (например, значение аргумента содержит
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
            elif self._buf.startswith(close_tag, index):
                return index
            index += 1
        return -1

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

                parser = ToolCallParser(emit_content, emit_tool_call) if emulate_tools else None
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
<<<END ARTIFACT>>>

<<<ARTIFACT path="bridges/opencode-zen-bridge/tests/test_step_interruption.py" sha256="1bb4ae56cfb87765c18dd09837d19cb7d82e051c8b7f1fa92a103a8ef43af0dd" bytes="105910">>>
#!/usr/bin/env python3
"""Regression: оборванный/незавершённый инструментальный шаг glm-5.3-flash-free (2026-10-24).

Симптом 1 (ECONNRESET посреди ответа): `opencode run` продолжал сам (SYNTHETIC «The previous
response was interrupted…»), модель отвечала «I was interrupted right before making tool calls…»,
текст склеивался с преамбулой, шаг заканчивался `stop` без инструментов.
Симптом 2 (rc=0, tools=0): модель спланировала вызовы в reasoning, выдала статусную преамбулу
и остановилась без `<tool_call>`.

Ожидается: мост останавливает оборванный `opencode run`, не пропускает «I was interrupted…» в
content, распознаёт незавершённый шаг и перезапрашивает модель — клиент получает tool_calls.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import socket
import tempfile
import threading
import time
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from unittest import mock

import server
from tests._fake_cli import allow_child_env
from tests._fixtures import install_test_models

install_test_models(server)
GLM_MODEL = "glm-5.3-flash-free"
server.ALLOWED_MODELS.setdefault(GLM_MODEL, {"context_length": 200000, "max_output": 131072,
                                             "supports_variant": True})

DSH_TOOLS = json.loads((Path(__file__).resolve().parent / "dsh_tools_fixture.json").read_text("utf-8"))
TOOLS = [
    {"type": "function", "function": {
        "name": "job_output", "description": "Read output of a background job",
        "parameters": {"type": "object", "properties": {"job_id": {"type": "string"}},
                       "required": ["job_id"]}}},
    {"type": "function", "function": {
        "name": "bash", "description": "Run a shell command",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"},
                                                        "description": {"type": "string"}},
                       "required": ["command", "description"]}}},
]

PREAMBLE = "**2026-10-24 13:55 MSK — статус.** Фетч был завершён (exit 0) — забираю вывод."
STATUS_ONLY = ("**2026-10-24 13:56 MSK — статус по цели (обновляю туду каждую минуту).** "
               "Собираю факты: вывод fetch-джобы, состояние данных.\n")
PLAN = ("One message: job_output(bash-4a99049e1f764309) + bash check state.json. "
        "Let me do: 1. job_output for fetch 2. bash: cat state.json")
CALLS = ('<tool_call>{"name": "job_output", "arguments": {"job_id": "bash-4a99"}}</tool_call>'
         '<tool_call>{"name": "bash", "arguments": {"command": "cat state.json", '
         '"description": "Show state"}}</tool_call>')
INVOKE_CALLS = CALLS.replace("tool_call", "tool_invoke")
# Реальный шаг glm-5.3-flash-free: апстрим вырезал `<tool_call>…` из text, а 97 токенов выставил.
SWALLOWED_TEXT = "2026-10-24 (MSK) — статус: проверяю вывод джобы job_fetch_01 и читаю goal.md."

FAKE_OPENCODE = r'''#!/usr/bin/env python3
import json, os, sys, time
counter = os.environ["FAKE_OC_COUNTER"]
n = int(open(counter).read()) if os.path.exists(counter) else 0
open(counter, "w").write(str(n + 1))
with open(counter + ".prompts", "a") as fh:
    fh.write(json.dumps(sys.stdin.read()) + "\n")
mode = os.environ.get("FAKE_OC_MODE", "")
def ev(o): print(json.dumps(o), flush=True)
def text(t): ev({"type": "text", "part": {"text": t}})
def reasoning(t): ev({"type": "reasoning", "part": {"text": t}})
def finish(out=5): ev({"type": "step_finish", "part": {"tokens": {"input": 10, "output": out}}})
calls = os.environ["FAKE_OC_CALLS"]
if mode == "econnreset" and n == 0:
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_PREAMBLE"])
    ev({"type": "error", "error": {"name": "APIError", "data": {
        "message": "provider.transport: Connection lost while reading the response: ECONNRESET"}}})
    time.sleep(2)
    # Сюда opencode попадает сам (SYNTHETIC-продолжение), если мост не остановил процесс.
    open(counter + ".second_step", "w").write("reached")
    reasoning("I was interrupted right before making tool calls. Continue.")
    text("I was interrupted right before making tool calls. Continue: collect output.")
    finish()
elif mode == "promise" and n == 0:
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_STATUS"])
    finish()
elif mode == "swallowed" and n == 0:
    text(os.environ["FAKE_OC_SWALLOW"])
    finish(97)
elif mode == "plain":
    reasoning("Simple greeting per Rule 0, no tools needed")
    text("Привет!")
    finish()
elif mode == "early_error" and n == 0:
    # Ошибка ДО первого токена: мост не должен убивать proc (opencode вправе восстановиться сам).
    ev({"type": "error", "error": {"name": "APIError", "data": {
        "message": "provider.transport: Connection lost: ECONNRESET"}}})
    time.sleep(1)
    open(counter + ".survived", "w").write("yes")
    text(calls)
    finish()
elif mode == "unmapped_then_error" and n == 0:
    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
    ev({"type": "error", "error": {"name": "APIError", "data": {
        "message": "provider.transport: Connection lost: ECONNRESET"}}})
    time.sleep(2)
    open(counter + ".second_step", "w").write("reached")
    finish()
elif mode == "early_error_plain":
    # Ошибка ДО первого токена, затем opencode сам восстановился и дал короткий текстовый ответ.
    ev({"type": "error", "error": {"name": "APIError", "data": {
        "message": "provider.transport: Connection lost: ECONNRESET"}}})
    time.sleep(1)
    text("Готово, проверил.")
    finish()
elif mode == "reasoning_interrupted":
    reasoning("The previous response was interrupted. Continue from where you left off without repeating completed content.")
    reasoning("Simple greeting.")
    text("Привет!")
    finish()
elif mode == "unmapped_then_promise" and n < 1:
    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
    finish()
elif mode == "unmapped_then_promise" and n == 1:
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_STATUS"])
    finish()
elif mode == "unmapped_then_promise_forever":
    if n == 0:
        ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
        finish()
    else:
        reasoning(os.environ["FAKE_OC_PLAN"])
        text(os.environ["FAKE_OC_STATUS"])
        finish()
elif mode == "unmapped_forever":
    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
    finish()
elif mode == "always_promise":
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_STATUS"])
    finish()
elif mode == "locked_then_promise":
    if n == 0:
        sys.stderr.write("Error: Unexpected error\n\ndatabase is locked\n")
        sys.exit(1)
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_STATUS"])
    finish()
elif mode == "slow_promise" and n == 0:
    time.sleep(float(os.environ.get("FAKE_OC_DELAY", "0.4")))
    text("Checking state...")
    finish()
elif mode == "rephrase":
    if n == 0:
        text("Checking state...")
        finish()
    else:
        text("Here is the result" + calls)
        finish()
elif mode == "repeat_prefix":
    if n == 0:
        text("Checking state...")
        finish()
    else:
        text("Checking state..." + calls)
        finish()
elif mode == "error401":
    text(os.environ["FAKE_OC_PREAMBLE"])
    ev({"type": "error", "error": {"name": "APIError", "data": {"statusCode": 401, "message": "api_key_expired"}}})
    time.sleep(2)
    open(counter + ".second_step", "w").write("reached")
    finish()
else:
    text(calls)
    finish()
'''


def fresh_resilience() -> Any:
    """Изолированный набор защит; лимитер запусков ускорен (его темп проверяется отдельно, на FakeClock)."""
    res = server._Resilience()
    res.spawn_limiter = server._SpawnRateLimiter(1000.0, 1000.0)
    return res


class FakeClock:
    """Детерминированные часы: sleep двигает время, реального ожидания нет."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class TestStepInterruptionLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        fake = Path(cls.tmp.name) / "opencode"
        fake.write_text(FAKE_OPENCODE, "utf-8")
        fake.chmod(0o755)
        cls.saved = (server.OPENCODE_BIN, server.AUTH_KEY, server.DEFAULTWORKDIR, server.LOG_PATH,
                     server.FAIL_RETRY_BACKOFF_S)
        cls.env_patch = allow_child_env("FAKE_OC_COUNTER", "FAKE_OC_MODE", "FAKE_OC_PLAN", "FAKE_OC_DELAY",
                                        "FAKE_OC_PREAMBLE", "FAKE_OC_STATUS", "FAKE_OC_CALLS", "FAKE_OC_SWALLOW")
        cls.env_patch.start()
        server.FAIL_RETRY_BACKOFF_S = 0.0  # без пауз между повторами в живых тестах
        server.OPENCODE_BIN = str(fake)
        server.AUTH_KEY = "test-key"
        server.DEFAULTWORKDIR = Path(cls.tmp.name) / "ws"
        server.LOG_PATH = Path(cls.tmp.name) / "bridge.log"
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]
        cls.httpd = server.Server(("127.0.0.1", cls.port), server.Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.env_patch.stop()
        (server.OPENCODE_BIN, server.AUTH_KEY, server.DEFAULTWORKDIR, server.LOG_PATH,
         server.FAIL_RETRY_BACKOFF_S) = cls.saved
        cls.tmp.cleanup()

    counter: Path = Path()

    def setUp(self) -> None:
        self.counter = Path(self.tmp.name) / f"counter-{self.id()}"
        os.environ["FAKE_OC_COUNTER"] = str(self.counter)
        # Свежие защиты на каждый тест (Retry Budget и Breaker process-level): изоляция тестов друг от друга.
        self.res = fresh_resilience()
        self.httpd.resilience = self.res
        os.environ["FAKE_OC_PLAN"] = PLAN
        os.environ["FAKE_OC_PREAMBLE"] = PREAMBLE
        os.environ["FAKE_OC_STATUS"] = STATUS_ONLY
        os.environ["FAKE_OC_CALLS"] = CALLS
        os.environ["FAKE_OC_SWALLOW"] = SWALLOWED_TEXT

    def tearDown(self) -> None:
        for name in ("FAKE_OC_COUNTER", "FAKE_OC_MODE", "FAKE_OC_PLAN", "FAKE_OC_PREAMBLE", "FAKE_OC_DELAY",
                     "FAKE_OC_STATUS", "FAKE_OC_CALLS", "FAKE_OC_SWALLOW"):
            os.environ.pop(name, None)

    def _post(self, stream: bool, model: str = "muse-spark-1.3-contributor-free",
              messages: list[dict[str, Any]] | None = None) -> bytes:
        body = json.dumps({"model": model, "stream": stream,
                           "messages": messages or [{"role": "user", "content": "продолжай цель"}],
                           "tools": TOOLS}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=body,
                                     headers={"Authorization": "Bearer test-key",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    def _runs(self) -> int:
        return int(self.counter.read_text())

    def _prompts(self) -> list[str]:
        return [json.loads(line) for line in Path(str(self.counter) + ".prompts").read_text().splitlines()]

    def _stream(self, model: str = "muse-spark-1.3-contributor-free",
                messages: list[dict[str, Any]] | None = None) -> tuple[str, list[str], list[str]]:
        raw = self._post(stream=True, model=model, messages=messages).decode()
        chunks = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: {")]
        content = "".join(c["choices"][0]["delta"].get("content") or "" for c in chunks)
        finishes = [c["choices"][0]["finish_reason"] for c in chunks if c["choices"][0].get("finish_reason")]
        names = [tc["function"]["name"] for c in chunks
                 for tc in c["choices"][0]["delta"].get("tool_calls") or []]
        return content, finishes, names

    def _assert_reprompt(self) -> None:
        retry_prompt = self._prompts()[1]
        self.assertIn(PREAMBLE if os.environ["FAKE_OC_MODE"] == "econnreset" else STATUS_ONLY.strip(),
                      retry_prompt)
        self.assertIn("<tool_call>", retry_prompt.rsplit("[system]", 1)[1])
        self.assertIn("job_output", retry_prompt.rsplit("[system]", 1)[1])

    # --- Симптом 1: ECONNRESET ---------------------------------------------------------

    def test_econnreset_stream_stops_proc_and_reprompts(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 2)
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")
        self.assertNotIn("interrupted", content)
        self.assertIn("забираю вывод", content)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self._assert_reprompt()

    def test_econnreset_json_stops_proc_and_reprompts(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        out = json.loads(self._post(stream=False))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")
        self.assertNotIn("interrupted", choice["message"]["content"])
        self.assertEqual([c["function"]["name"] for c in choice["message"]["tool_calls"]],
                         ["job_output", "bash"])
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self._assert_reprompt()

    # --- Симптом 2: статусная преамбула без <tool_call> --------------------------------

    def test_promise_without_tool_call_stream_reprompts(self) -> None:
        os.environ["FAKE_OC_MODE"] = "promise"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 2)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self.assertIn("Собираю факты", content)
        self.assertEqual(content.count("Собираю факты"), 1)
        self._assert_reprompt()

    def test_promise_without_tool_call_json_reprompts(self) -> None:
        os.environ["FAKE_OC_MODE"] = "promise"
        out = json.loads(self._post(stream=False))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertEqual([c["function"]["name"] for c in choice["message"]["tool_calls"]],
                         ["job_output", "bash"])
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self._assert_reprompt()

    # --- GLM: протокол на <tool_invoke>, проглоченный <tool_call> --------------------------

    def _assert_no_tool_call_token(self) -> None:
        for prompt in self._prompts():
            self.assertNotIn("tool_call", prompt)
            self.assertIn("<tool_invoke>", prompt)

    def test_glm_prompt_uses_tool_invoke_only_stream(self) -> None:
        os.environ["FAKE_OC_CALLS"] = INVOKE_CALLS
        _content, finishes, names = self._stream(GLM_MODEL)
        self.assertEqual(self._runs(), 1)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self._assert_no_tool_call_token()

    def test_glm_history_tool_calls_rewritten_to_tool_invoke(self) -> None:
        os.environ["FAKE_OC_CALLS"] = INVOKE_CALLS
        messages = [
            {"role": "user", "content": "продолжай цель"},
            {"role": "assistant", "content": "Проверяю.", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "job_output", "arguments": '{"job_id": "bash-4a99"}'}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
        ]
        _content, _finishes, names = self._stream(GLM_MODEL, messages)
        self.assertEqual(names, ["job_output", "bash"])
        self._assert_no_tool_call_token()
        self.assertIn('<tool_invoke>{"id": "call_1", "name": "job_output"', self._prompts()[0])

    def test_glm_swallowed_tool_call_reprompts_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "swallowed"
        os.environ["FAKE_OC_CALLS"] = INVOKE_CALLS
        content, finishes, names = self._stream(GLM_MODEL)
        self.assertEqual(self._runs(), 2)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self.assertEqual(content.count("проверяю вывод джобы"), 1)
        self._assert_no_tool_call_token()
        retry_tail = self._prompts()[1].rsplit("[system]", 1)[1]
        self.assertIn('start your reply immediately with <tool_invoke>{"name":', retry_tail)

    def test_glm_swallowed_tool_call_reprompts_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "swallowed"
        os.environ["FAKE_OC_CALLS"] = INVOKE_CALLS
        out = json.loads(self._post(stream=False, model=GLM_MODEL))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertEqual([c["function"]["name"] for c in choice["message"]["tool_calls"]],
                         ["job_output", "bash"])
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self._assert_no_tool_call_token()

    def test_swallowed_status_not_retried_when_tokens_match_text(self) -> None:
        os.environ["FAKE_OC_MODE"] = "plain"
        _content, finishes, names = self._stream(GLM_MODEL)
        self.assertEqual(self._runs(), 1)
        self.assertEqual(names, [])
        self.assertEqual(finishes, ["stop"])

    # --- Ошибка до первого токена: proc не убиваем ----------------------------------------

    def _assert_early_error_survived(self) -> None:
        self.assertEqual(self._runs(), 1)
        self.assertTrue(Path(str(self.counter) + ".survived").exists(),
                        "proc must not be killed by an error before any output")

    def test_early_error_does_not_kill_proc_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "early_error"
        _content, finishes, names = self._stream()
        self._assert_early_error_survived()
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])

    def test_early_error_does_not_kill_proc_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "early_error"
        out = json.loads(self._post(stream=False))
        self._assert_early_error_survived()
        self.assertEqual([c["function"]["name"] for c in out["choices"][0]["message"]["tool_calls"]],
                         ["job_output", "bash"])

    def test_unmapped_then_error_stops_proc_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_then_error"
        out = json.loads(self._post(stream=False))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")
        self.assertEqual([c["function"]["name"] for c in choice["message"]["tool_calls"]],
                         ["job_output", "bash"])
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self.assertIn("todoread", self._prompts()[1])

    # --- Ранняя ошибка + восстановление коротким текстом: had_error не липнет --------------

    def test_early_error_then_plain_text_not_retried_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "early_error_plain"
        out = json.loads(self._post(stream=False))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 1)
        self.assertEqual(choice["finish_reason"], "stop")
        self.assertEqual(choice["message"]["content"], "Готово, проверил.")

    def test_early_error_then_plain_text_not_retried_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "early_error_plain"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 1)
        self.assertEqual((content, finishes, names), ("Готово, проверил.", ["stop"], []))

    # --- «The previous response was interrupted» вычищается и из reasoning -----------------

    def test_interrupted_artifact_removed_from_reasoning_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "reasoning_interrupted"
        raw = self._post(stream=True).decode()
        chunks = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: {")]
        thoughts = "".join(c["choices"][0]["delta"].get("reasoning_content") or "" for c in chunks)
        self.assertEqual(thoughts, "Simple greeting.")
        self.assertNotIn("interrupted", raw)
        self.assertEqual(self._runs(), 1)

    def test_interrupted_artifact_removed_from_reasoning_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "reasoning_interrupted"
        out = json.loads(self._post(stream=False))
        message = out["choices"][0]["message"]
        self.assertEqual(message["reasoning_content"], "Simple greeting.")
        self.assertEqual(message["content"], "Привет!")
        self.assertEqual(out["choices"][0]["finish_reason"], "stop")
        self.assertEqual(self._runs(), 1)

    # --- Бюджеты повторов раздельные -----------------------------------------------------

    def test_unmapped_retries_do_not_exhaust_incomplete_budget_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 3)  # 1 unmapped + 1 incomplete: общий потолок MAX_TOTAL_SPAWNS
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self.assertEqual(content.count("Собираю факты"), 1)

    def test_unmapped_retries_do_not_exhaust_incomplete_budget_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
        out = json.loads(self._post(stream=False))
        self.assertEqual(self._runs(), 3)
        self.assertEqual([c["function"]["name"] for c in out["choices"][0]["message"]["tool_calls"]],
                         ["job_output", "bash"])

    # --- Обычный текстовый ответ не ретраится ------------------------------------------

    def test_plain_answer_not_retried_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "plain"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 1)
        self.assertEqual((content, finishes, names), ("Привет!", ["stop"], []))

    def test_plain_answer_not_retried_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "plain"
        out = json.loads(self._post(stream=False))
        self.assertEqual(self._runs(), 1)
        self.assertEqual(out["choices"][0]["finish_reason"], "stop")
        self.assertEqual(out["choices"][0]["message"]["content"], "Привет!")

    def test_tail_reminder_in_long_prompt(self) -> None:
        os.environ["FAKE_OC_MODE"] = "plain"
        history: list[dict[str, Any]] = []
        for i in range(3):
            history.append({"role": "user", "content": f"шаг {i} " + "x" * 2000})
            history.append({"role": "assistant", "content": f"Смотрю {i}."})
        history.append({"role": "user", "content": "дальше"})
        body = json.dumps({"model": "muse-spark-1.3-contributor-free", "stream": False,
                           "messages": history, "tools": TOOLS}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=body,
                                     headers={"Authorization": "Bearer test-key",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60):
            pass
        prompt = self._prompts()[0]
        tail = prompt.rsplit("[system]", 1)[1]
        self.assertIn("Available tools: job_output, bash", tail)
        self.assertIn("<tool_call>", tail)
        self.assertTrue(prompt.rstrip().endswith(tail.rstrip()))

    # --- Помощники для проверок ceiling/O-EXIT ---------------------------------------------

    def _post_raw(self, body: bytes | None = None, stream: bool = False, tool_choice: Any = None,
                  model: str = "muse-spark-1.3-contributor-free") -> tuple[int, bytes]:
        payload: dict[str, Any] = {"model": model, "stream": stream, "tools": TOOLS,
                                   "messages": [{"role": "user", "content": "продолжай цель"}]}
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions",
                                     data=body if body is not None else json.dumps(payload).encode(),
                                     headers={"Authorization": "Bearer test-key",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, exc.read()

    @staticmethod
    def _exit_lines() -> list[dict[str, str]]:
        text = server.LOG_PATH.read_text("utf-8") if server.LOG_PATH.exists() else ""
        return [dict(re.findall(r"(\w+)=(\S+)", line)) for line in text.splitlines() if "O-EXIT/v1" in line]

    def _last_exit(self, before: int) -> dict[str, str]:
        """Последняя строка O-EXIT/v1 после `before` строк (лог пишется уже после ответа клиенту)."""
        for _ in range(100):
            lines = self._exit_lines()
            if len(lines) > before:
                return lines[-1]
            time.sleep(0.05)
        self.fail("O-EXIT/v1 line was not written")

    # --- VER-005: пять целевых тестов ---------------------------------------------------

    def test_serve_json_without_emulate_tools_skips_step_recovery(self) -> None:
        # tool_choice="none" -> emulate_tools=False: детектор не вызывается, ровно один запуск.
        os.environ["FAKE_OC_MODE"] = "promise"
        before = len(self._exit_lines())
        with mock.patch.object(server, "_is_incomplete_tool_step",
                               wraps=server._is_incomplete_tool_step) as detector:
            status, raw = self._post_raw(tool_choice="none")
        self.assertEqual(status, 200)
        detector.assert_not_called()
        self.assertEqual(self._runs(), 1)
        choice = json.loads(raw)["choices"][0]
        self.assertEqual(choice["finish_reason"], "stop")
        self.assertIn("Собираю факты", choice["message"]["content"])
        self.assertEqual(self._last_exit(before)["total_spawns"], "1")

    def test_env_kill_switch_skips_step_recovery_keeps_unmapped_retry(self) -> None:
        # OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0 выключает дозапрос преамбулы; повтор встроенного инструмента — нет.
        self.assertEqual(server.NATIVE_RETRY_LIMIT, 2)
        with mock.patch.dict(os.environ, {"OPENCODE_ZEN_BRIDGE_STEP_RECOVERY": "0"}):
            os.environ["FAKE_OC_MODE"] = "promise"
            _content, finishes, names = self._stream()
            self.assertEqual((self._runs(), names, finishes), (1, [], ["stop"]))  # преамбула не дозапрошена
            self.counter.unlink()
            Path(str(self.counter) + ".prompts").unlink()
            os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
            _content, finishes, names = self._stream()
            # повтор встроенного инструмента сработал (2-й запуск), а преамбула 2-го шага — уже без дозапроса
            self.assertEqual(self._runs(), 2)
            self.assertEqual((names, finishes), ([], ["stop"]))
            self.assertIn("todoread", self._prompts()[1])

    def test_stream_dedup_prefix_mismatch_emits_full_text(self) -> None:
        # Попытка 1: «Checking state...»; попытка 2 переформулировала: текст и tool_calls доходят целиком.
        os.environ["FAKE_OC_MODE"] = "rephrase"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 2)
        self.assertIn("Checking state...", content)
        self.assertIn("Here is the result", content)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])

    def test_json_dedup_prefix_mismatch_keeps_full_text(self) -> None:
        os.environ["FAKE_OC_MODE"] = "rephrase"
        choice = json.loads(self._post(stream=False))["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertIn("Checking state...", choice["message"]["content"])
        self.assertIn("Here is the result", choice["message"]["content"])
        self.assertEqual(choice["finish_reason"], "tool_calls")

    def test_stream_dedup_prefix_match_suppresses_repeated_preamble(self) -> None:
        os.environ["FAKE_OC_MODE"] = "repeat_prefix"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 2)
        self.assertEqual(content.count("Checking state..."), 1)
        self.assertEqual((names, finishes), (["job_output", "bash"], ["tool_calls"]))

    def test_json_dedup_prefix_match_suppresses_repeated_preamble(self) -> None:
        os.environ["FAKE_OC_MODE"] = "repeat_prefix"
        choice = json.loads(self._post(stream=False))["choices"][0]
        self.assertEqual(choice["message"]["content"].count("Checking state..."), 1)
        self.assertEqual(choice["finish_reason"], "tool_calls")

    def test_short_final_answer_with_colon_not_incomplete(self) -> None:
        for text in ("Ответ: 42:", "Итог проверки:", "Результат проверки:", "Вывод:", "Summary:"):
            with self.subTest(text=text):
                self.assertFalse(server._is_incomplete_tool_step(text, "", TOOLS))
                self.assertEqual(server._detect_incomplete_tool_step_signal(text, "", TOOLS), 0)
        self.assertEqual(server._detect_incomplete_tool_step_signal("Читаю файл:", "", TOOLS), 5)

    def test_mid_stream_error_401_not_retried_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "error401"
        raw = self._post(stream=True).decode()
        chunks = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: {")]
        errors = [c["error"] for c in chunks if "error" in c]
        self.assertEqual(self._runs(), 1)
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")
        self.assertEqual(len(errors), 1)
        self.assertIn("api_key_expired", errors[0]["message"])
        self.assertFalse([c for c in chunks if c.get("choices") and c["choices"][0].get("finish_reason")])

    def test_mid_stream_error_401_not_retried_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "error401"
        before = len(self._exit_lines())
        status, raw = self._post_raw()
        self.assertEqual(status, 502)
        self.assertIn("api_key_expired", raw.decode())
        self.assertEqual(self._runs(), 1)
        self.assertEqual(self._last_exit(before)["total_spawns"], "1")
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")

    def test_mid_stream_error_econnreset_retried_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        with mock.patch.object(server, "_stop_proc", wraps=server._stop_proc) as stop:
            content, finishes, names = self._stream()
        self.assertTrue(stop.called)
        self.assertEqual(self._runs(), 2)
        self.assertFalse(Path(str(self.counter) + ".second_step").exists())
        self.assertNotIn("interrupted", content)
        self.assertEqual((names, finishes), (["job_output", "bash"], ["tool_calls"]))

    def test_mid_stream_error_econnreset_retried_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        before = len(self._exit_lines())
        choice = json.loads(self._post(stream=False))["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertEqual(choice["finish_reason"], "tool_calls")
        info = self._last_exit(before)
        self.assertEqual((info["total_spawns"], info["signal"]), ("2", "1"))

    def test_run_execute_once_stops_proc_on_mid_stream_error(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        run = server.Run("muse-spark-1.3-contributor-free", "prompt", "", Path(self.tmp.name) / "ws",
                         tools=TOOLS, resilience=self.res)
        out = run._execute_once()
        run.close()
        self.assertTrue(out["had_error"])
        self.assertFalse(out["fatal_error"])
        self.assertEqual(out["state"], "provider_error")
        self.assertNotIn("interrupted", out["text"])
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")

    def test_run_execute_once_overflow_stops_proc_and_marks_attempt_failed(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        original = server._StdoutFeed.lines

        def slow_lines(feed: Any, *args: Any, **kwargs: Any) -> Any:
            time.sleep(0.5)  # читатель успевает переполнить очередь maxsize=1
            yield from original(feed, *args, **kwargs)

        with (mock.patch.object(server, "STDOUT_QUEUE_MAX", 1),
              mock.patch.object(server._StdoutFeed, "lines", slow_lines)):
            run = server.Run("muse-spark-1.3-contributor-free", "prompt", "", Path(self.tmp.name) / "ws",
                             tools=TOOLS, resilience=self.res)
            out = run._execute_once()
            run.close()
        self.assertEqual(out["state"], "stdout_overflow")
        self.assertTrue(out["had_error"])
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on overflow")

    # --- Потолок MAX_TOTAL_SPAWNS = 3 на все комбинации классов повтора ----------------------

    def test_ceiling_always_promise_stops_after_three_spawns(self) -> None:
        # QA-BND-02: 1 + NATIVE_RETRY_LIMIT запусков, дальше накопленный текст с finish stop.
        os.environ["FAKE_OC_MODE"] = "always_promise"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), server.MAX_TOTAL_SPAWNS)
        self.assertEqual((names, finishes), ([], ["stop"]))
        self.assertIn("Собираю факты", content)

    def test_ceiling_unmapped_then_promise_forever_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_then_promise_forever"
        before = len(self._exit_lines())
        choice = json.loads(self._post(stream=False))["choices"][0]
        self.assertEqual(self._runs(), 3)  # было бы 1 + 2 + 2 без общего потолка
        self.assertEqual(choice["finish_reason"], "stop")
        self.assertEqual(self._last_exit(before)["total_spawns"], "3")

    def test_ceiling_unmapped_forever_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_forever"
        content, finishes, _names = self._stream()
        self.assertEqual(self._runs(), 3)
        self.assertIn("повторы исчерпаны", content)
        self.assertEqual(finishes, ["stop"])

    def test_ceiling_locked_then_promise_stream(self) -> None:
        # fail_retries + attempt: 1 (rc=1) + 1 fail-повтор + 1 дозапрос = 3, четвёртого запуска нет.
        os.environ["FAKE_OC_MODE"] = "locked_then_promise"
        _content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 3)
        self.assertEqual((names, finishes), ([], ["stop"]))

    def test_ceiling_locked_then_promise_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "locked_then_promise"
        out = json.loads(self._post(stream=False))
        self.assertEqual(self._runs(), 3)
        self.assertEqual(out["choices"][0]["finish_reason"], "stop")

    def test_retry_budget_exhausted_returns_last_attempt_without_retry(self) -> None:
        os.environ["FAKE_OC_MODE"] = "promise"
        self.res.retry_budget = server._RetryBudget(capacity=0.0, per_request_refill=0.0, reserve_rps=0.0)
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 1)
        self.assertEqual((names, finishes), ([], ["stop"]))
        self.assertIn("Собираю факты", content)

    # --- SSE keepalive во время повтора ------------------------------------------------

    def test_keepalive_chunks_sent_while_waiting_for_step_recovery_retry(self) -> None:
        os.environ["FAKE_OC_MODE"] = "slow_promise"
        os.environ["FAKE_OC_DELAY"] = "0.5"
        with mock.patch.object(server, "KEEPALIVE_INTERVAL_S", 0.05):
            raw = self._post(stream=True).decode()
        chunks = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: {")]
        deltas = [c["choices"][0]["delta"] for c in chunks if c.get("choices")]
        self.assertGreaterEqual(deltas[1:].count({"content": ""}), 1, deltas)
        self.assertEqual(self._runs(), 2)
        self.assertEqual([c["choices"][0].get("finish_reason") for c in chunks if c.get("choices")][-1],
                         "tool_calls")

    # --- O-EXIT/v1: структурная строка на каждом выходе do_POST -------------------------------

    def _assert_exit_fields(self, info: dict[str, str], **expected: str) -> None:
        for key in ("mode", "model", "exit_reason", "total_spawns", "signal", "status"):
            self.assertIn(key, info)
        for key, value in expected.items():
            self.assertEqual(info[key], value, (key, info))

    def test_o_exit_logged_for_json_and_stream_success(self) -> None:
        os.environ["FAKE_OC_MODE"] = "plain"
        before = len(self._exit_lines())
        self._post(stream=False)
        self._assert_exit_fields(self._last_exit(before), mode="json", exit_reason="ok", status="200",
                                 total_spawns="1", signal="0")
        before = len(self._exit_lines())
        self._post(stream=True)
        self._assert_exit_fields(self._last_exit(before), mode="stream", exit_reason="ok", status="200",
                                 total_spawns="1", signal="0",
                                 model="muse-spark-1.3-contributor-free")

    def test_o_exit_logged_for_400_and_401(self) -> None:
        before = len(self._exit_lines())
        status, _ = self._post_raw(body=b"{not json")
        self.assertEqual(status, 400)
        self._assert_exit_fields(self._last_exit(before), exit_reason="bad_request", status="400",
                                 total_spawns="0")
        before = len(self._exit_lines())
        status, _ = self._post_raw(body=json.dumps({"model": "no-such-model", "messages": []}).encode())
        self.assertEqual(status, 400)
        self._assert_exit_fields(self._last_exit(before), exit_reason="bad_request", status="400")
        before = len(self._exit_lines())
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=b"{}",
                                     headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req, timeout=10)
        caught.exception.close()
        self.assertEqual(caught.exception.code, 401)
        self._assert_exit_fields(self._last_exit(before), exit_reason="unauthorized", status="401")

    def test_o_exit_logged_for_503_circuit_open_without_spawn(self) -> None:
        for _ in range(server.CB_FAIL_THRESHOLD):
            self.res.breaker.record_failure()
        self.assertEqual(self.res.breaker.state, "OPEN")
        for stream in (False, True):
            with self.subTest(stream=stream):
                before = len(self._exit_lines())
                status, raw = self._post_raw(stream=stream)
                self.assertEqual(status, 503)
                error = json.loads(raw)["error"]
                self.assertEqual((error["message"], error["type"]), ("upstream circuit open", "overloaded"))
                self._assert_exit_fields(self._last_exit(before), exit_reason="circuit_open", status="503",
                                         total_spawns="0")
        self.assertFalse(self.counter.exists(), "в OPEN запусков нет")
        self.assertEqual(self.res.slots.in_use, 0)

    def test_o_exit_logged_for_503_slot_timeout_and_overflow(self) -> None:
        self.res.slots = server._SlotBulkhead(max_concurrent=1, max_waiters=1, wait_timeout_s=0.2)
        self.assertEqual(self.res.slots.acquire_ex(), "ok")
        before = len(self._exit_lines())
        started = time.monotonic()
        status, raw = self._post_raw()
        self.assertEqual(status, 503)
        self.assertGreaterEqual(time.monotonic() - started, 0.15)
        self.assertEqual(json.loads(raw)["error"]["type"], "overloaded")
        self._assert_exit_fields(self._last_exit(before), exit_reason="slot_timeout", status="503")
        self.res.slots = server._SlotBulkhead(max_concurrent=1, max_waiters=0, wait_timeout_s=30.0)
        self.assertEqual(self.res.slots.acquire_ex(), "ok")
        before = len(self._exit_lines())
        started = time.monotonic()
        status, _ = self._post_raw(stream=True)
        self.assertEqual(status, 503)
        self.assertLess(time.monotonic() - started, 2.0, "переполнение очереди ждущих — мгновенный отказ")
        self._assert_exit_fields(self._last_exit(before), exit_reason="slot_overflow", status="503")
        self.assertFalse(self.counter.exists())

    def test_breaker_opens_after_repeated_transient_failures_and_blocks_next_request(self) -> None:
        os.environ["FAKE_OC_MODE"] = "locked_then_promise"
        self.res.breaker = server._UpstreamBreaker(fail_threshold=2, reset_timeout_s=60.0)
        with mock.patch.object(server, "FAIL_RETRY_LIMIT", 0):
            for _ in range(2):
                status, _raw = self._post_raw()
                self.assertEqual(status, 502)
                self.counter.unlink()
        self.assertEqual(self.res.breaker.state, "OPEN")
        status, raw = self._post_raw()
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(raw)["error"]["message"], "upstream circuit open")
        self.assertFalse(self.counter.exists())

    def test_retried_then_successful_request_does_not_count_as_breaker_failure(self) -> None:
        self.res.breaker = server._UpstreamBreaker(fail_threshold=1, reset_timeout_s=60.0)
        os.environ["FAKE_OC_MODE"] = "econnreset"  # 1-й запуск оборван ECONNRESET, 2-й — вызовы
        choice = json.loads(self._post(stream=False))["choices"][0]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self.assertEqual(self.res.breaker.state, "CLOSED")


class TestIsIncompleteToolStep(unittest.TestCase):
    def check(self, text: str = "", reasoning: str = "", **kw: Any) -> bool:
        return server._is_incomplete_tool_step(text, reasoning, kw.pop("tools", TOOLS), **kw)

    def test_no_tools_never_incomplete(self) -> None:
        self.assertFalse(self.check("Собираю факты", "let me batch", tools=[], tool_choice="required"))

    def test_tool_choice_required_or_named(self) -> None:
        self.assertTrue(self.check("Привет", tool_choice="required"))
        self.assertTrue(self.check("Привет", tool_choice={"type": "function", "function": {"name": "bash"}}))

    def test_provider_error_with_partial_output(self) -> None:
        self.assertTrue(self.check("Фетч был завершён", had_error=True))
        self.assertTrue(self.check("", "thinking", had_error=True))
        self.assertFalse(self.check("", "", had_error=True))

    def test_interrupt_markers(self) -> None:
        self.assertTrue(self.check("I was interrupted right before making tool calls."))
        self.assertTrue(self.check("", "The previous response was interrupted. Continue"))

    def test_unparsed_raw_tool_call(self) -> None:
        self.assertTrue(self.check('Смотрю <tool_call>{"name": "bash", "arguments": {"command": "ls"'))
        self.assertFalse(self.check("В протоколе используется `<tool_call>` как тег."))

    def test_russian_promise_preamble_without_reasoning(self) -> None:
        self.assertTrue(self.check("Фетч завершён, забираю вывод:"))
        self.assertTrue(self.check("🕐 [14:11 MSK] Проверяю состояние…"))
        self.assertTrue(self.check("Собираю факты..."))

    def test_english_promise_preamble_without_reasoning(self) -> None:
        self.assertTrue(self.check("Let me check the job output:"))
        self.assertTrue(self.check("Running the tests now..."))

    def test_russian_promise_with_plan_in_reasoning(self) -> None:
        self.assertTrue(self.check(PREAMBLE, PLAN))
        self.assertTrue(self.check(STATUS_ONLY, PLAN))

    def test_plan_in_reasoning_with_short_status(self) -> None:
        self.assertTrue(self.check("**Статус.** Собираю факты.", PLAN))
        self.assertTrue(self.check("", "All in batch: job_output then bash, parallel calls."))

    def test_plan_in_reasoning_requires_promise_in_body(self) -> None:
        self.assertFalse(self.check("**Статус.**", PLAN))
        self.assertFalse(self.check("Суббота", PLAN))
        self.assertFalse(self.check("Проверять ли состояние, или сразу смотрю?", PLAN))

    def test_short_answer_with_promise_words_but_no_plan_is_complete(self) -> None:
        self.assertFalse(self.check("Сейчас проверяю этот пункт — всё в порядке."))
        self.assertFalse(self.check("Обновляю данные раз в час, так задумано."))
        self.assertFalse(self.check("Проверяю: ошибок нет.", "Thinking about the answer."))
        self.assertFalse(self.check("Обновляю.", "Short answer, nothing to run."))
        self.assertFalse(self.check("Let me check: yes, it is Saturday."))

    def test_tool_choice_none_never_incomplete(self) -> None:
        self.assertFalse(self.check(PREAMBLE, PLAN, tool_choice="none"))
        self.assertFalse(self.check("Фетч завершён", had_error=True, tool_choice="none"))
        self.assertFalse(self.check("I was interrupted right before making tool calls.", tool_choice="none"))

    def test_long_final_answer_after_provider_error_is_complete(self) -> None:
        answer = "Итог работы. " * 120 + "Тесты зелёные."
        self.assertGreater(len(answer), server.INCOMPLETE_STEP_MAX_TEXT)
        self.assertFalse(self.check(answer, had_error=True))
        self.assertTrue(self.check(answer[:500], had_error=True))

    def test_interrupted_marker_in_reasoning_or_text(self) -> None:
        self.assertTrue(self.check("", "I was interrupted right before making tool calls."))
        self.assertTrue(self.check("The previous response was interrupted."))

    def test_plain_answers_are_complete(self) -> None:
        self.assertFalse(self.check("Суббота"))
        self.assertFalse(self.check("Привет! Чем помочь?"))
        self.assertFalse(self.check("OK"))
        self.assertFalse(self.check("Привет!", "Simple greeting per Rule 0, no tools needed"))
        self.assertFalse(self.check("Привет!", "Правило 0: не требует инструментов"))
        self.assertFalse(self.check("Готово.", "The answer needs no tools. Let me do: reply with the answer."))

    def test_rule0_quote_in_reasoning_with_tool_plan_and_next_step_promise_triggers_retry(self) -> None:
        # chatcmpl-oczen-07836803fb70: цитата Rule 0 в начале reasoning, дальше — план вызова.
        reasoning = (
            "Per Rule 0 'Status, greeting, a single reference question — one text, without tools' ... "
            "But answering requires reading the file, so tools needed. Per tool protocol, emit blocks ... "
            "Actually keep it minimal: one bash call computing hash")
        text = ("Подтверждаю: общий канон ~/Мой диск/Context/AGENTS.md прочитан целиком "
                "(маркер <!-- КАНОН-КОНЕЦ --> в конце), проектные файлы правил в рабочей папке "
                "проверю следующим шагом.")
        self.assertIn(server._detect_incomplete_tool_step_signal(text, reasoning, TOOLS), (4, 5))
        self.assertTrue(self.check(text, reasoning))
        self.assertFalse(self.check("Привет!", "Simple greeting per Rule 0, no tools needed"))

    def test_long_final_answer_with_plan_words_is_complete(self) -> None:
        answer = "Итог работы. " * 200 + "Тесты зелёные, правки закоммичены."
        self.assertFalse(self.check(answer, "Let me do: summarize; job_output is not needed."))


class TestStripInterrupted(unittest.TestCase):
    def test_i_was_interrupted_with_continue(self) -> None:
        self.assertEqual(server._strip_interrupted(
            "Забираю.I was interrupted right before making tool calls. Continue: collect output."), "Забираю.")

    def test_i_was_interrupted_without_continue(self) -> None:
        self.assertEqual(server._strip_interrupted("Раз. I was interrupted right before making tool calls."),
                         "Раз. ")

    def test_previous_response_interrupted(self) -> None:
        text = ("Раз. The previous response was interrupted. Continue from where you left off without "
                "repeating completed content. Два.")
        self.assertEqual(server._strip_interrupted(text), "Раз.  Два.")

    def test_unrelated_text_untouched(self) -> None:
        text = "Предыдущий ответ был прерван? The previous response was fine. Continue: ok."
        self.assertEqual(server._strip_interrupted(text), text)


class TestTailReminder(unittest.TestCase):
    LONG = "x" * (server.TAIL_REMINDER_MIN_CHARS + 1)

    def test_reminder_for_long_history(self) -> None:
        self.assertIn("Available tools: job_output, bash", server._tools_tail_reminder(self.LONG, TOOLS))

    def test_no_reminder_for_tool_choice_none(self) -> None:
        self.assertEqual(server._tools_tail_reminder(self.LONG, TOOLS, "none"), "")

    def test_no_reminder_without_tools(self) -> None:
        self.assertEqual(server._tools_tail_reminder(self.LONG, []), "")


class TestShellAlias(unittest.TestCase):
    def test_shell_maps_to_bash(self) -> None:
        calls = server._native_to_tool_calls("shell", {"command": "ls -la"}, DSH_TOOLS)
        self.assertEqual([c["name"] for c in calls], ["bash"])
        self.assertEqual(calls[0]["arguments"]["command"], "ls -la")
        self.assertTrue(calls[0]["arguments"]["description"])


class TestSanitizeAssistantHistory(unittest.TestCase):
    def test_interrupted_artifact_removed(self) -> None:
        text = ("Фетч был завершён (exit 0) — забираю вывод."
                "I was interrupted right before making tool calls. Continue: collect output.")
        self.assertEqual(server._sanitize_assistant_text(text),
                         "Фетч был завершён (exit 0) — забираю вывод.")

    def test_interrupted_artifact_own_line(self) -> None:
        text = "Раз.\nI was interrupted right before making tool calls. Continue.\nДва."
        self.assertEqual(server._sanitize_assistant_text(text), "Раз.\n\nДва.")

    def test_unclosed_tool_call_tail_removed(self) -> None:
        text = ('Смотрю.\n<tool_call>{"name": "bash", "arguments": {"command": "ls"}}</tool_call>\n'
                'Потом:\n<tool_call>{"name": "read", "arguments": {"file_path": "/etc/ho')
        out = server._sanitize_assistant_text(text)
        self.assertEqual(out.count("<tool_call>"), 1)
        self.assertTrue(out.rstrip().endswith("Потом:"))

    def test_closed_batch_without_intermediate_close_kept(self) -> None:
        text = ('<tool_call>{"name": "a", "arguments": {}}\n<tool_call>{"name": "b", "arguments": {}}'
                '</tool_call>')
        self.assertEqual(server._sanitize_assistant_text(text), text)

    def test_quoted_tag_in_prose_kept(self) -> None:
        text = "Блок `<tool_call>` открывает вызов."
        self.assertEqual(server._sanitize_assistant_text(text), text)


PLAN_EMIT = ("Let me think... I need to call the tools in the protocol format shown in the [system] block. "
             "I should follow the injected protocol and emit blocks.")


class TestIncompleteStepGlmPatterns(unittest.TestCase):
    """Реальные паттерны glm-5.3-flash-free (2026-10-24), которые раньше пропускались."""

    def check(self, text: str = "", reasoning: str = "", **kw: Any) -> bool:
        return server._is_incomplete_tool_step(text, reasoning, kw.pop("tools", TOOLS), **kw)

    def test_status_ending_with_period_needs_token_evidence(self) -> None:
        self.assertFalse(self.check(SWALLOWED_TEXT))
        self.assertTrue(self.check(SWALLOWED_TEXT, output_tokens=97))

    def test_emit_blocks_plan_with_russian_status(self) -> None:
        text = "Статус: 24.10.2026, время MSK уточню по ходу — забираю вывод job_fetch_01 и читаю goal.md."
        self.assertTrue(self.check(text, PLAN_EMIT))
        self.assertTrue(self.check(text, PLAN_EMIT, output_tokens=144))

    def test_two_independent_calls_plan(self) -> None:
        reasoning = ("Two independent calls — I should make both in one turn. Status line with MSK "
                     "datetime first, then tool blocks... I'll write status and make both calls in parallel.")
        text = "Статус (MSK, 24.10.2026): забираю вывод job_fetch_01 и параллельно проверяю goal.md."
        self.assertTrue(self.check(text, reasoning))

    def test_then_both_tool_calls_plan(self) -> None:
        reasoning = ("Let me start by following the protocol: write a status line with MSK date-time, then "
                     "call job_output for job_fetch_01 and bash... then both tool calls in parallel")
        text = "Статус: 24.10.2026 ~MSK, стартую ход — параллельно забираю вывод job_fetch_01 и читаю goal.md."
        self.assertTrue(self.check(text, reasoning))

    def test_parallel_calls_plan_with_confirmation_text(self) -> None:
        reasoning = ("Parallel calls: job_output and bash... Let me do one bash with date and cat, "
                     "plus job_output in parallel.")
        text = ("Подтверждаю: правила прочитал. Выполняю параллельные вызовы: job_output по фетчу + bash "
                "по goal.md (замер MSK — уже есть: 2026-10-24 13:52 MSK).")
        self.assertTrue(self.check(text, reasoning))

    def test_tool_named_in_reasoning_and_text_without_plan_phrase(self) -> None:
        self.assertTrue(self.check("Продолжаю — job_output по фетчу.", "I should call job_output now."))

    def test_new_promise_verbs(self) -> None:
        for verb in ("Стартую", "Продолжаю", "Начинаю", "Вызываю", "Запрашиваю"):
            self.assertTrue(self.check(f"{verb} проверку:"), verb)

    def test_promise_with_tool_name_short_text_without_reasoning(self) -> None:
        self.assertTrue(self.check("Запускаю bash для проверки."))
        self.assertFalse(self.check("Запускаю проверку."))

    def test_swallowed_tokens_with_reasoning_only(self) -> None:
        self.assertTrue(self.check("", "Some planning.", output_tokens=80))

    def test_swallowed_tokens_need_text_or_reasoning(self) -> None:
        self.assertFalse(self.check("", "", output_tokens=200))

    def test_tokens_matching_visible_text_are_complete(self) -> None:
        text = "Всё в порядке: ошибок нет, тесты зелёные, правки закоммичены."
        self.assertFalse(self.check(text, output_tokens=30))
        self.assertFalse(self.check("Привет!", output_tokens=8))

    def test_question_never_swallowed(self) -> None:
        self.assertFalse(self.check("Какой джобой заняться первой?", output_tokens=200))

    def test_long_final_answer_never_swallowed(self) -> None:
        answer = "Итог работы. " * 200 + "Тесты зелёные."
        self.assertFalse(self.check(answer, output_tokens=5000))

    def test_no_tools_wins_over_swallowed_tokens(self) -> None:
        self.assertFalse(self.check("Привет!", "Simple greeting, no tools needed", output_tokens=100))

    def test_tool_choice_none_ignores_swallowed_tokens(self) -> None:
        self.assertFalse(self.check(SWALLOWED_TEXT, output_tokens=97, tool_choice="none"))

    def test_final_answer_mentioning_tool_is_complete(self) -> None:
        self.assertFalse(self.check("Ответ: в джобе ошибок нет, всё в порядке.",
                                    "The user asks about job_output; I should answer."))

    def test_raw_tool_invoke_is_incomplete(self) -> None:
        self.assertTrue(self.check('Смотрю <tool_invoke>{"name": "bash", "arguments": {"command": "ls"'))
        self.assertFalse(self.check("В протоколе используется `<tool_invoke>` как тег."))

    def test_mentions_request_tool_uses_token_boundaries(self) -> None:
        schemas = server._tool_schemas(TOOLS)
        self.assertTrue(server._mentions_request_tool("Вызываю job_output.", schemas))
        self.assertFalse(server._mentions_request_tool("job_output_2 и bashrc", schemas))


class TestAltToolTagHelpers(unittest.TestCase):
    GLM = "glm-5.3-flash-free"

    def test_uses_alt_tool_tag_only_for_glm(self) -> None:
        self.assertTrue(server._uses_alt_tool_tag(self.GLM))
        self.assertTrue(server._uses_alt_tool_tag("opencode/GLM-5#high"))
        self.assertFalse(server._uses_alt_tool_tag("muse-spark-1.3-contributor-free"))
        self.assertFalse(server._uses_alt_tool_tag(""))
        self.assertFalse(server._uses_alt_tool_tag())

    def test_tool_tags_for_model(self) -> None:
        self.assertEqual(server._tool_tags_for_model(self.GLM), ("<tool_invoke>", "</tool_invoke>"))
        self.assertEqual(server._tool_tags_for_model("muse"), ("<tool_call>", "</tool_call>"))
        self.assertEqual(server._tool_tags_for_model(), ("<tool_call>", "</tool_call>"))
        self.assertEqual(server.TOOL_CALL_OPEN, "<tool_call>")
        self.assertEqual(server.TOOL_CALL_CLOSE, "</tool_call>")

    def test_rewrite_tool_tags_for_model(self) -> None:
        text = '<tool_call>{"name": "a"}</tool_call>'
        self.assertEqual(server._rewrite_tool_tags_for_model(text, self.GLM),
                         '<tool_invoke>{"name": "a"}</tool_invoke>')
        self.assertEqual(server._rewrite_tool_tags_for_model(text, "muse"), text)
        self.assertEqual(server._rewrite_tool_tags_for_model(text), text)

    def test_tools_section_glm_has_no_tool_call_substring(self) -> None:
        section = server._tools_section(TOOLS, None, self.GLM)
        self.assertNotIn("tool_call", section)
        self.assertIn('<tool_invoke>{"name": "<tool_name>"', section)
        self.assertIn("emit a tool_invoke block", section)
        self.assertIn("MUST emit the tool_invoke block", section)

    def test_tools_section_default_keeps_tool_call(self) -> None:
        for section in (server._tools_section(TOOLS, None), server._tools_section(TOOLS, None, "muse")):
            self.assertIn('<tool_call>{"name": "<tool_name>"', section)
            self.assertIn("emit a tool_call block", section)
            self.assertNotIn("tool_invoke", section)

    def test_tail_reminder_glm(self) -> None:
        long_history = "x" * (server.TAIL_REMINDER_MIN_CHARS + 1)
        reminder = server._tools_tail_reminder(long_history, TOOLS, None, self.GLM)
        self.assertIn("<tool_invoke>", reminder)
        self.assertNotIn("tool_call", reminder)
        self.assertIn("<tool_call>", server._tools_tail_reminder(long_history, TOOLS))

    def test_incomplete_step_prompt_glm(self) -> None:
        prompt = server._incomplete_tool_step_prompt("P", "Статус:", TOOLS, None, self.GLM)
        self.assertIn('start your reply immediately with <tool_invoke>{"name":', prompt)
        self.assertIn('<tool_invoke>{"name": "<tool_name>", "arguments": {<json matching its parameters>}}'
                      "</tool_invoke> using ONLY these tools: job_output, bash.", prompt)
        self.assertNotIn("tool_call", prompt)
        default = server._incomplete_tool_step_prompt("P", "Статус:", TOOLS)
        self.assertIn('start your reply immediately with <tool_call>{"name":', default)

    def test_unavailable_tools_prompt_glm(self) -> None:
        prompt = server._unavailable_tools_prompt("P", "", ["todoread"], TOOLS, self.GLM)
        self.assertIn("<tool_invoke>", prompt)
        self.assertNotIn("tool_call", prompt)
        self.assertIn("<tool_call>", server._unavailable_tools_prompt("P", "", ["todoread"], TOOLS))


class TestDualTagParser(unittest.TestCase):
    A = '{"name": "job_output", "arguments": {"job_id": "j1"}}'
    B = '{"name": "bash", "arguments": {"command": "ls"}}'

    def names(self, chunks: list[str]) -> tuple[str, list[str]]:
        content, calls = server._split_tool_calls(chunks)
        return content, [c["function"]["name"] for c in calls]

    def test_tool_invoke_block(self) -> None:
        content, names = self.names([f"Проверяю. <tool_invoke>{self.A}</tool_invoke>"])
        self.assertEqual(names, ["job_output"])
        self.assertEqual(content, "Проверяю. ")

    def test_tool_invoke_split_across_chunks(self) -> None:
        for size in (1, 2, 3, 5, 7):
            doc = f"Статус. <tool_invoke>{self.A}</tool_invoke>"
            chunks = [doc[i:i + size] for i in range(0, len(doc), size)]
            content, names = self.names(chunks)
            self.assertEqual(names, ["job_output"], size)
            self.assertEqual(content, "Статус. ", size)

    def test_tool_invoke_batch_without_intermediate_close(self) -> None:
        content, names = self.names([f"<tool_invoke>{self.A}\n<tool_invoke>{self.B}</tool_invoke>"])
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(content, "")

    def test_tool_invoke_batch_with_all_closes(self) -> None:
        _content, names = self.names([f"<tool_invoke>{self.A}</tool_invoke><tool_invoke>{self.B}</tool_invoke>"])
        self.assertEqual(names, ["job_output", "bash"])

    def test_mixed_tags(self) -> None:
        _content, names = self.names([f"<tool_call>{self.A}</tool_call><tool_invoke>{self.B}</tool_invoke>"])
        self.assertEqual(names, ["job_output", "bash"])

    def test_tool_call_still_parsed(self) -> None:
        _content, names = self.names([f"<tool_call>{self.A}</tool_call>"])
        self.assertEqual(names, ["job_output"])

    def test_quoted_tool_invoke_is_prose(self) -> None:
        text = "Тег `<tool_invoke>` открывает вызов."
        content, names = self.names([text])
        self.assertEqual(names, [])
        self.assertEqual(content, text)

    def test_tool_invoke_in_fenced_code_is_prose(self) -> None:
        text = f"Пример:\n```\n<tool_invoke>{self.A}</tool_invoke>\n```\n"
        content, names = self.names([text])
        self.assertEqual(names, [])
        self.assertEqual(content, text)

    def test_close_tag_inside_json_string_is_not_boundary(self) -> None:
        block = '{"name": "bash", "arguments": {"command": "echo </tool_invoke>"}}'
        _content, calls = server._split_tool_calls([f"<tool_invoke>{block}</tool_invoke>"])
        self.assertEqual([json.loads(c["function"]["arguments"])["command"] for c in calls],
                         ["echo </tool_invoke>"])

    def test_other_tag_close_does_not_end_block(self) -> None:
        content, names = self.names([f"<tool_invoke>{self.A}</tool_call>"])
        self.assertEqual(names, [])
        self.assertIn("<tool_invoke>", content)

    def test_unparsed_block_returned_as_text(self) -> None:
        content, names = self.names(["<tool_invoke>{broken</tool_invoke>"])
        self.assertEqual(names, [])
        self.assertEqual(content, "<tool_invoke>{broken</tool_invoke>")

    def test_has_open_tool_call_for_alt_tag(self) -> None:
        parser = server.ToolCallParser(lambda _t: None, lambda _c: None)
        parser.feed("Текст <tool_inv")
        self.assertTrue(parser.has_open_tool_call())
        parser.feed(f"oke>{self.A}")
        self.assertTrue(parser.has_open_tool_call())
        parser.feed("</tool_invoke>")
        self.assertFalse(parser.has_open_tool_call())

    def test_shared_prefix_not_held_forever(self) -> None:
        content, names = self.names(["Версия <tool_x и <tool_"])
        self.assertEqual(names, [])
        self.assertEqual(content, "Версия <tool_x и <tool_")

    def test_split_inner_on_alt_tag(self) -> None:
        segments = server._split_tool_call_inner(f"{self.A}<tool_invoke>{self.B}")
        self.assertEqual(segments, [self.A, self.B])
        self.assertEqual(len(server._parse_tool_call_blocks(f"{self.A}<tool_invoke>{self.B}") or []), 2)

    def test_quoted_open_alt_tag(self) -> None:
        self.assertTrue(server._is_quoted_open("a `<tool_invoke>` b", 3))
        self.assertTrue(server._is_quoted_open("<tool_invoke>`x`", 0))
        self.assertFalse(server._is_quoted_open(f"<tool_invoke>{self.A}", 0))

    def test_sanitize_unclosed_tool_invoke_tail_removed(self) -> None:
        text = (f"Смотрю.\n<tool_invoke>{self.B}</tool_invoke>\nПотом:\n"
                '<tool_invoke>{"name": "read", "arguments": {"file_path": "/etc/ho')
        out = server._sanitize_assistant_text(text)
        self.assertEqual(out.count("<tool_invoke>"), 1)
        self.assertTrue(out.rstrip().endswith("Потом:"))

    def test_sanitize_unclosed_after_other_tag_close(self) -> None:
        text = f'<tool_call>{self.B}</tool_call>\nПотом:\n<tool_invoke>{{"name": "read", "arguments": {{"f'
        out = server._sanitize_assistant_text(text)
        self.assertNotIn('"read"', out)
        self.assertEqual(out.count("<tool_call>"), 1)

    def test_sanitize_closed_alt_batch_kept(self) -> None:
        text = f"<tool_invoke>{self.A}\n<tool_invoke>{self.B}</tool_invoke>"
        self.assertEqual(server._sanitize_assistant_text(text), text)

    def test_sanitize_quoted_alt_tag_kept(self) -> None:
        text = "Блок `<tool_invoke>` открывает вызов."
        self.assertEqual(server._sanitize_assistant_text(text), text)


class TestDetectorSignals(unittest.TestCase):
    """VER-001: признаки 1..5 `_detect_incomplete_tool_step_signal` и вычитание reasoning_tokens."""

    NAMES = ["job_output", "bash"]

    def signal(self, text: str = "", reasoning: str = "", **kw: Any) -> int:
        return server._detect_incomplete_tool_step_signal(text, reasoning, kw.pop("tools", self.NAMES), **kw)

    def test_signature_accepts_names_and_openai_schemas(self) -> None:
        self.assertEqual(self.signal("Читаю файл:", tools=self.NAMES), 5)
        self.assertEqual(self.signal("Читаю файл:", tools=TOOLS), 5)
        self.assertEqual(self.signal("Читаю файл:", tools=[]), 0)
        self.assertTrue(server._is_incomplete_tool_step("Читаю файл:", "", self.NAMES, False, 0, 0))

    def test_signal_1_mid_stream_error(self) -> None:
        self.assertEqual(self.signal("Фетч завершён", had_mid_stream_error=True), 1)
        self.assertEqual(self.signal("", "thinking", had_mid_stream_error=True), 1)
        self.assertEqual(self.signal("", "", had_mid_stream_error=True), 0)
        self.assertEqual(self.signal("Привет", tool_choice="required"), 1)

    def test_signal_2_interrupted_marker_and_raw_call(self) -> None:
        self.assertEqual(self.signal("I was interrupted right before making tool calls."), 2)
        self.assertEqual(self.signal("", "The previous response was interrupted. Continue from where you left "
                                         "off without repeating completed content."), 2)
        self.assertEqual(self.signal('Смотрю <tool_invoke>{"name": "bash", "arguments": {"command": "ls"'), 2)

    def test_signal_3_swallowed_tokens_and_reasoning_subtraction(self) -> None:
        text = "Готово, все проверки пройдены."
        # output=450, reasoning=430: non_reasoning=20 -> не проглочено; output=500, reasoning=150 -> 350 токенов
        self.assertEqual(self.signal(text, "x", output_tokens=450, reasoning_tokens=430), 0)
        self.assertFalse(server._is_incomplete_tool_step(text, "x", self.NAMES, False, 450, 430))
        self.assertEqual(self.signal(SWALLOWED_TEXT, "x", output_tokens=500, reasoning_tokens=150), 3)
        self.assertTrue(server._is_incomplete_tool_step(SWALLOWED_TEXT, "x", self.NAMES, False, 500, 150))
        # без reasoning_tokens output считается целиком
        self.assertEqual(self.signal(SWALLOWED_TEXT, output_tokens=97), 3)
        # QA-NEG-01: output=400 reasoning=385 -> 15 < 35
        for answer in ("Готово, все проверки пройдены.", "Ответ: 42."):
            self.assertEqual(self.signal(answer, "reasoning", output_tokens=400, reasoning_tokens=385), 0, answer)

    def test_signal_3_boundary_34_false_35_true(self) -> None:
        text = "Статус обновлён и сохранён." * 3
        estimate = server._visible_token_estimate(text.strip())
        tokens = estimate + server.SWALLOWED_TOKENS_MIN
        self.assertEqual(self.signal(text, output_tokens=tokens - 1), 0)
        self.assertEqual(self.signal(text, output_tokens=tokens), 3)
        # граница по длине видимого текста: 600 символов ещё признак 3, 601 — уже нет
        for size, expected in ((600, 3), (601, 0)):
            body = ("слово " * 200)[:size].strip() + "."
            body = body.ljust(size, "я")[:size]
            self.assertEqual(self.signal(body, output_tokens=5000), expected, size)

    def test_signal_4_reasoning_plan_with_tool_name_and_promise(self) -> None:
        self.assertEqual(self.signal(PREAMBLE, PLAN), 4)
        self.assertEqual(self.signal("Продолжаю — job_output по фетчу.", "I should call job_output now."), 4)
        self.assertEqual(self.signal("**Статус.**", PLAN), 0)
        self.assertEqual(self.signal("", "All in batch: job_output then bash, parallel calls."), 4)

    def test_signal_5_narrow_action_preamble(self) -> None:
        for text in ("Читаю…", "Собираю факты...", "Теперь посмотрим:", "Let's check:", "I'll run the tests...",
                     "Фетч завершён, забираю вывод:", "Запускаю bash для проверки."):
            self.assertEqual(self.signal(text), 5, text)

    def test_signal_5_bare_colon_without_action_intent_is_not_incomplete(self) -> None:
        for text in ("Ответ: 42:", "Результат проверки:", "Итог проверки:", "Список файлов:", "Вот что нашёл:"):
            self.assertEqual(self.signal(text), 0, text)
            self.assertFalse(server._is_incomplete_tool_step(text, "", self.NAMES), text)

    def test_signal_5_excludes_long_tables_code_and_conclusions(self) -> None:
        long_text = "Читаю файлы проекта и собираю сводку. " * 20 + "Дальше:"
        self.assertGreater(len(long_text), server.PREAMBLE_MAX_CHARS)
        self.assertEqual(self.signal(long_text), 0)
        table = "Проверяю результаты:\n| a | b |\n|---|---|\n| 1 | 2 |\n"
        self.assertEqual(self.signal(table), 0)
        fenced = "Запускаю:\n```\nls -la\n```\nДальше:"
        self.assertEqual(self.signal(fenced), 0)
        many_lines = "Читаю:\n" + "\n".join(f"- пункт {i}" for i in range(8)) + "\nДальше:"
        self.assertEqual(self.signal(many_lines), 0)
        self.assertEqual(self.signal("Проверяю: ошибок нет, всё в порядке:"), 0)
        self.assertEqual(self.signal("Итог: проверяю результаты..."), 0)
        self.assertEqual(self.signal("Читаю ли я файл?"), 0)

    def test_signal_5_boundary_420_chars(self) -> None:
        base = "Читаю файл "
        at_limit = base + "а" * (server.PREAMBLE_MAX_CHARS - len(base) - 1) + ":"
        self.assertEqual(len(at_limit), server.PREAMBLE_MAX_CHARS)
        self.assertEqual(self.signal(at_limit), 5)
        self.assertEqual(self.signal(at_limit + "я:"), 0)

    def test_signal_5_short_text_without_tool_mention_needs_terminator(self) -> None:
        self.assertEqual(self.signal("Запускаю проверку."), 0)
        self.assertEqual(self.signal("Запускаю job_output."), 5)

    def test_kill_switch_constant_and_env_return_zero_first(self) -> None:
        with mock.patch.object(server, "STEP_RECOVERY_ENABLED", False):
            self.assertEqual(self.signal("Читаю…"), 0)
            self.assertFalse(server._is_incomplete_tool_step("I was interrupted right before making tool calls.",
                                                             "", self.NAMES, had_mid_stream_error=True))
        for value in ("0", "false", "No", "OFF"):
            with mock.patch.dict(os.environ, {"OPENCODE_ZEN_BRIDGE_STEP_RECOVERY": value}):
                self.assertEqual(self.signal("Читаю…"), 0, value)
        with mock.patch.dict(os.environ, {"OPENCODE_ZEN_BRIDGE_STEP_RECOVERY": "1"}):
            self.assertEqual(self.signal("Читаю…"), 5)
        self.assertTrue(server.STEP_RECOVERY_ENABLED)

    def test_incomplete_step_signal_wrapper_follows_is_incomplete_tool_step(self) -> None:
        with mock.patch.object(server, "_is_incomplete_tool_step", return_value=False):
            self.assertEqual(server._incomplete_step_signal("Читаю…", "", self.NAMES), 0)
        self.assertEqual(server._incomplete_step_signal("Читаю…", "", self.NAMES), 5)


class TestTransientStreamError(unittest.TestCase):
    """AD-002: детерминированные ошибки не ретраятся (Fail-Closed), транзиентные — да."""

    @staticmethod
    def event(status: Any = None, message: str = "") -> dict[str, Any]:
        data: dict[str, Any] = {"message": message}
        if status is not None:
            data["statusCode"] = status
        return {"type": "error", "error": {"name": "APIError", "data": data}}

    def test_deterministic_statuses_are_not_transient(self) -> None:
        for status in (400, 401, 403, 404, 422):
            self.assertFalse(server._is_transient_stream_error(self.event(status, "boom ECONNRESET")), status)
            self.assertFalse(server._is_transient_stream_error({"statusCode": status, "message": ""}), status)

    def test_transient_statuses(self) -> None:
        for status in (None, 0, 408, 429, 500, 502, 503, 504):
            self.assertTrue(server._is_transient_stream_error(self.event(status, "whatever")), status)

    def test_transient_message_markers(self) -> None:
        for message in ("read ECONNRESET", "ETIMEDOUT", "request timed out", "socket hang up", "Overloaded",
                        "rate limit exceeded", "temporarily unavailable", "fetch failed", "network error",
                        "connection reset by peer", "broken pipe", "unexpected EOF", "stream interrupted"):
            self.assertTrue(server._is_transient_stream_error(self.event(402, message)), message)
        self.assertFalse(server._is_transient_stream_error(self.event(402, "payment required")))

    def test_event_shapes(self) -> None:
        self.assertTrue(server._is_transient_stream_error({"error": "read ECONNRESET"}))
        self.assertFalse(server._is_transient_stream_error({"part": {"statusCode": 401}}))
        self.assertTrue(server._is_transient_stream_error({"part": {"statusCode": 503}}))
        self.assertTrue(server._is_transient_stream_error({}))
        etype, payload = server.parse_opencode_event(self.event(401, "api_key_expired"))
        self.assertEqual(etype, "error")
        self.assertFalse(server._is_transient_stream_error(payload))
        _etype, payload = server.parse_opencode_event(self.event(None, "Connection lost: ECONNRESET"))
        self.assertTrue(server._is_transient_stream_error(payload))


class TestStdoutFeed(unittest.TestCase):
    """VER-002: ограниченная очередь stdout, переполнение, дедлайн, EOF."""

    @staticmethod
    def spawn(script: str) -> Any:
        import subprocess
        import sys
        return subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True,
                                start_new_session=True)

    def test_default_queue_is_bounded_to_4096(self) -> None:
        self.assertEqual(server.STDOUT_QUEUE_MAX, 4096)
        proc = types.SimpleNamespace(stdout=iter([]), poll=lambda: 0)
        feed = server._StdoutFeed(proc)  # type: ignore[arg-type]
        feed.join(2)
        self.assertEqual(feed._queue.maxsize, 4096)
        self.assertEqual((feed.overflowed, feed.dropped_total), (False, 0))

    def test_overflow_stops_real_proc_and_counts_dropped(self) -> None:
        proc = self.spawn("import time\nfor i in range(200): print(i, flush=True)\ntime.sleep(60)")
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        feed = server._StdoutFeed(proc, maxsize=4)
        feed.join(10)
        self.assertTrue(feed.overflowed)
        self.assertGreaterEqual(feed.dropped_total, 1)
        self.assertIsNotNone(proc.poll(), "_stop_proc обязан остановить процесс на queue.Full")
        self.assertEqual(list(feed.lines(time.monotonic() + 5)), [], "после переполнения попытка неуспешна")

    def test_queue_full_calls_stop_proc_once_per_overflow(self) -> None:
        proc = types.SimpleNamespace(stdout=iter([f"{i}\n" for i in range(10)]))
        with mock.patch.object(server, "_stop_proc") as stop:
            feed = server._StdoutFeed(proc, maxsize=3)  # type: ignore[arg-type]
            feed.join(5)
        stop.assert_called_once_with(proc)
        self.assertEqual((feed.overflowed, feed.dropped_total), (True, 1))

    def test_all_lines_delivered_when_queue_is_big_enough(self) -> None:
        proc = self.spawn("for i in range(50): print(i, flush=True)")
        feed = server._StdoutFeed(proc, maxsize=4096)
        lines = [line.strip() for line in feed.lines(time.monotonic() + 30)]
        proc.wait(5)
        self.assertEqual(lines, [str(i) for i in range(50)])
        self.assertFalse(feed.overflowed)

    def test_deadline_unblocks_silent_proc(self) -> None:
        proc = self.spawn("import time; time.sleep(30)")
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        feed = server._StdoutFeed(proc)
        started = time.monotonic()
        self.assertEqual(list(feed.lines(time.monotonic() + 0.3)), [])
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertTrue(feed.timed_out)

    def test_idle_callback_fires_during_silence(self) -> None:
        proc = self.spawn("import time; time.sleep(0.6); print('x', flush=True)")
        feed = server._StdoutFeed(proc)
        idle: list[int] = []
        lines = list(feed.lines(time.monotonic() + 10, 0.1, lambda: idle.append(1)))
        self.assertEqual([line.strip() for line in lines], ["x"])
        self.assertGreaterEqual(len(idle), 2)

    def test_reader_error_is_raised_to_consumer(self) -> None:
        def boom() -> Any:
            yield "a\n"
            raise ValueError("closed")

        proc = types.SimpleNamespace(stdout=boom())
        feed = server._StdoutFeed(proc)  # type: ignore[arg-type]
        got: list[str] = []
        with self.assertRaises(ValueError):
            for line in feed.lines(time.monotonic() + 5):
                got.append(line)
        self.assertEqual(got, ["a\n"])


class TestParserAndAliasVer001(unittest.TestCase):
    """VER-001 / AD-001: оба тега одинаково, алиас shell."""

    A = '{"name": "job_output", "arguments": {"job_id": "j1"}}'

    def test_tool_invoke_and_tool_call_give_identical_calls(self) -> None:
        for chunks in (["<tool_invoke>" + self.A + "</tool_invoke>"], ["<tool_call>" + self.A + "</tool_call>"]):
            _content, calls = server._split_tool_calls(chunks)
            self.assertEqual([(c["function"]["name"], json.loads(c["function"]["arguments"])) for c in calls],
                             [("job_output", {"job_id": "j1"})])
        for open_tag in ("<tool_invoke>", "<tool_call>"):
            inner = self.A + open_tag + self.A.replace("j1", "j2")
            self.assertEqual([c["arguments"]["job_id"] for c in server._parse_tool_call_blocks(inner) or []],
                             ["j1", "j2"])

    def test_native_aliases_contain_shell_and_bash_maps_to_client_shell(self) -> None:
        self.assertIn("shell", server.NATIVE_TOOL_ALIASES)
        self.assertEqual([c["name"] for c in server._native_to_tool_calls("shell", {"command": "ls"}, DSH_TOOLS)],
                         ["bash"])

    def test_glm_prompts_use_tool_invoke_as_primary_tag(self) -> None:
        self.assertIn("<tool_invoke>", server._tools_section(TOOLS, None, GLM_MODEL))
        self.assertIn("<tool_invoke>", server._incomplete_tool_step_prompt("P", "x", TOOLS, None, GLM_MODEL))


class TestRetryAndDedupHelpers(unittest.TestCase):
    def test_prefix_dedup_match_mismatch_and_partial(self) -> None:
        dedup = server._PrefixDedup("Checking state...")
        self.assertEqual(dedup.push("Check"), "")
        self.assertEqual(dedup.push("ing state... Next"), " Next")
        self.assertEqual(dedup.push(" more"), " more")
        self.assertEqual(dedup.finish(), "")
        dedup = server._PrefixDedup("Checking state...")
        self.assertEqual(dedup.push("Here is the result"), "\n\nHere is the result")
        self.assertEqual(dedup.push("!"), "!")
        dedup = server._PrefixDedup("Checking state...")
        self.assertEqual(dedup.push("Hi"), "\n\nHi")  # разошлось раньше длины префикса
        dedup = server._PrefixDedup("Checking state...")
        self.assertEqual(dedup.push("Check"), "")
        self.assertEqual(dedup.finish(), "", "чистый повтор части префикса не дублируется")
        dedup = server._PrefixDedup("Checking state...")
        self.assertEqual(dedup.finish(), "")

    def test_dedup_retry_text_json_variant(self) -> None:
        self.assertEqual(server._dedup_retry_text("Статус.", "Статус. Дальше"), " Дальше")
        self.assertEqual(server._dedup_retry_text("Статус.", "Другое"), "Другое")
        self.assertEqual(server._dedup_retry_text("", "Текст"), "Текст")
        self.assertEqual(server._dedup_retry_text("Статус.", ""), "")


class HlResilienceOracles(unittest.TestCase):
    """VER-006: детерминированные оракулы (FakeClock / инъекция rng_fn / spy), без wall-clock."""

    # --- S-HERD-I2: Full Jitter ---------------------------------------------------------

    def test_backoff_full_jitter_points(self) -> None:
        def at(u: float) -> Any:
            return lambda lo, hi: lo + u * (hi - lo)

        self.assertEqual([server._retry_backoff_s(1, at(u)) for u in (0.0, 0.5, 1.0)], [0.0, 0.5, 1.0])
        self.assertEqual([server._retry_backoff_s(2, at(u)) for u in (0.0, 0.5, 1.0)], [0.0, 1.0, 2.0])
        seen: list[tuple[float, float]] = []
        server._retry_backoff_s(7, lambda lo, hi: seen.append((lo, hi)) or hi)
        self.assertEqual(seen, [(0.0, server.RETRY_BACKOFF_CAP_S)])
        self.assertEqual((server.RETRY_BACKOFF_BASE_S, server.RETRY_BACKOFF_CAP_S), (0.5, 2.0))

    # --- S-HERD-I1: spawn token bucket --------------------------------------------------

    def test_spawn_token_bucket_at_most_one_per_second(self) -> None:
        clock = FakeClock()
        limiter = server._SpawnRateLimiter(1.0, 1.0, clock_fn=clock, sleep_fn=clock.sleep)
        starts = []
        for _ in range(10):
            self.assertTrue(limiter.acquire())
            starts.append(clock.now)
        self.assertEqual(starts[0], 1000.0)
        for first, second in zip(starts, starts[1:]):
            self.assertGreaterEqual(second - first, 1.0 - 1e-9)
        window = [t for t in starts if 1003.0 <= t < 1004.0]
        self.assertLessEqual(len(window), 1)

    def test_spawn_limiter_ten_concurrent_reservations_are_spread(self) -> None:
        clock = FakeClock()
        waits: list[float] = []
        limiter = server._SpawnRateLimiter(1.0, 1.0, clock_fn=clock, sleep_fn=waits.append)
        for _ in range(10):  # все десять приходят в один и тот же момент времени
            self.assertTrue(limiter.acquire())
        self.assertEqual(waits, [float(i) for i in range(1, 10)])

    def test_spawn_limiter_refuses_without_reserving_when_wait_exceeds_budget(self) -> None:
        clock = FakeClock()
        waits: list[float] = []
        limiter = server._SpawnRateLimiter(1.0, 1.0, clock_fn=clock, sleep_fn=waits.append)
        self.assertTrue(limiter.acquire())
        self.assertFalse(limiter.acquire(max_wait_s=0.5))
        self.assertFalse(limiter.acquire(max_wait_s=0.5))
        self.assertEqual(waits, [])
        clock.sleep(1.0)
        self.assertTrue(limiter.acquire(max_wait_s=0.0), "резерв не списан отказами")

    # --- R-BULK-I2: потолок запусков и Retry Budget ------------------------------------------

    def test_max_total_spawns_ceiling_for_all_retry_class_combinations(self) -> None:
        self.assertEqual(server.MAX_TOTAL_SPAWNS, 3)
        kinds = ("cli_failure", "unmapped", "incomplete_step")
        for sequence in itertools.product(kinds, repeat=5):
            clock = FakeClock()
            res = server._Resilience()
            res.retry_budget = server._RetryBudget(capacity=100.0, clock_fn=clock)
            attempts = server._RequestAttempts(res, clock() + 1e6, sleep_fn=lambda _s: None)
            self.assertTrue(attempts.begin_attempt())
            attempts.note_spawn()
            for kind in sequence:
                if attempts.allow_retry(kind):
                    attempts.note_spawn()
                self.assertLessEqual(attempts.total_spawns, 3, sequence)
            self.assertEqual(attempts.total_spawns, 3, sequence)

    def test_retry_budget_bound_for_100_failing_requests(self) -> None:
        clock = FakeClock()
        budget = server._RetryBudget(6, 0.20, 0.05, clock_fn=clock)
        retries = 0
        for _ in range(100):
            budget.on_request()
            for _retry in range(2):  # каждый запрос падает и хочет оба повтора
                if budget.try_acquire_retry():
                    retries += 1
            clock.sleep(5.0)  # T_w = 500 c
        bound = int(0.20 * 100 + 0.05 * 500) + 6
        self.assertEqual(bound, 51)
        self.assertLessEqual(retries, bound)
        self.assertGreater(retries, 0)
        self.assertLess(retries, 200, "без бюджета было бы 200 повторов")

    def test_retry_budget_starts_full_and_caps(self) -> None:
        clock = FakeClock()
        budget = server._RetryBudget(6, 0.20, 0.05, clock_fn=clock)
        self.assertEqual(sum(budget.try_acquire_retry() for _ in range(10)), 6)
        clock.sleep(20.0)  # +1.0 токен от резерва
        self.assertTrue(budget.try_acquire_retry())
        self.assertFalse(budget.try_acquire_retry())
        clock.sleep(10000.0)
        budget.on_request()
        self.assertEqual(sum(budget.try_acquire_retry() for _ in range(10)), 6, "ёмкость не превышается")

    def test_exhausted_budget_denies_retry_without_sleep_or_spawn(self) -> None:
        clock = FakeClock()
        res = server._Resilience()
        res.retry_budget = server._RetryBudget(0.0, 0.0, 0.0, clock_fn=clock)
        sleeps: list[float] = []
        attempts = server._RequestAttempts(res, clock() + 1e6, sleep_fn=sleeps.append)
        self.assertFalse(attempts.allow_retry("incomplete_step"))
        self.assertEqual((sleeps, attempts.total_spawns, attempts.retries), ([], 0, 0))
        # локальный отказ старта CLI не списывает бюджет: повтор разрешён и при пустом бюджете
        self.assertTrue(attempts.allow_retry("cli_failure", charge_budget=False))
        self.assertEqual(attempts.retries, 1)

    # --- R-BULK-I3: Circuit Breaker -------------------------------------------------------

    def test_breaker_open_after_five_failures_half_open_single_probe(self) -> None:
        clock = FakeClock()
        logs: list[str] = []
        spans: list[tuple[float, float]] = []

        def rng(lo: float, hi: float) -> float:
            spans.append((lo, hi))
            return 1.0

        breaker = server._UpstreamBreaker(5, 10.0, clock_fn=clock, rng_fn=rng, log_fn=logs.append)
        for _ in range(4):
            breaker.record_failure()
        self.assertEqual(breaker.state, "CLOSED")
        self.assertTrue(breaker.allow())
        breaker.record_failure()
        self.assertEqual(breaker.state, "OPEN")
        self.assertEqual(spans, [(0.8, 1.2)])
        self.assertFalse(breaker.allow())
        clock.sleep(9.9)
        self.assertEqual(breaker.state, "OPEN")
        clock.sleep(0.2)
        self.assertEqual(breaker.state, "HALF_OPEN")
        results: list[bool] = []
        barrier = threading.Barrier(10)

        def probe() -> None:
            barrier.wait()
            results.append(breaker.allow())

        threads = [threading.Thread(target=probe) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertEqual(results.count(True), 1, "в HALF_OPEN ровно одна проба")
        self.assertEqual(breaker.max_half_open_probes, 1)
        breaker.record_failure()  # проба не удалась -> снова OPEN
        self.assertEqual(breaker.state, "OPEN")
        clock.sleep(10.0)
        self.assertTrue(breaker.allow())
        breaker.record_success()
        self.assertEqual(breaker.state, "CLOSED")
        self.assertTrue(any("state=OPEN" in line for line in logs))
        self.assertTrue(any("state=HALF_OPEN" in line for line in logs))
        self.assertTrue(any("state=CLOSED" in line for line in logs))

    def test_breaker_success_resets_failure_streak_and_lost_probe_expires(self) -> None:
        clock = FakeClock()
        breaker = server._UpstreamBreaker(3, 10.0, clock_fn=clock, rng_fn=lambda _lo, hi: hi, log_fn=lambda _m: None)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()
        breaker.record_failure()
        self.assertEqual(breaker.state, "CLOSED")
        breaker.record_failure()
        self.assertEqual(breaker.state, "OPEN")
        clock.sleep(12.0)
        self.assertTrue(breaker.allow())      # проба занята
        self.assertFalse(breaker.allow())
        clock.sleep(10.5)                     # результат пробы потерян -> проба истекает
        self.assertTrue(breaker.allow())

    def test_request_attempts_commit_counts_only_final_failure(self) -> None:
        res = server._Resilience()
        res.breaker = server._UpstreamBreaker(1, 60.0, log_fn=lambda _m: None)
        attempts = server._RequestAttempts(res, time.monotonic() + 100)
        attempts.attempt_done(True, False)   # отказ, затем успех повтором
        attempts.attempt_done(False, True)
        attempts.commit()
        self.assertEqual(res.breaker.state, "CLOSED")
        attempts.attempt_done(True, False)   # запрос закончился отказом
        attempts.commit()
        attempts.commit()
        self.assertEqual(res.breaker.state, "OPEN")

    # --- C-MULT-I2 / I4: bulkhead слотов ----------------------------------------------------

    def test_slot_bulkhead_thirteenth_waiter_gets_immediate_overflow(self) -> None:
        bulkhead = server._SlotBulkhead(max_concurrent=6, max_waiters=12, wait_timeout_s=30.0)
        self.assertEqual([bulkhead.acquire_ex() for _ in range(6)], ["ok"] * 6)
        verdicts: list[str] = []

        def waiter() -> None:
            verdict = bulkhead.acquire_ex()
            verdicts.append(verdict)
            if verdict == "ok":
                bulkhead.release()

        threads = [threading.Thread(target=waiter) for _ in range(12)]
        for thread in threads:
            thread.start()
        for _ in range(200):
            if bulkhead.waiters == 12:
                break
            time.sleep(0.01)
        self.assertEqual(bulkhead.waiters, 12)
        started = time.monotonic()
        self.assertEqual(bulkhead.acquire_ex(), "overflow")
        self.assertFalse(bulkhead.acquire())
        self.assertLess(time.monotonic() - started, 0.5, "13-й ждущий получает отказ мгновенно")
        for _ in range(6):
            bulkhead.release()
        for thread in threads:
            thread.join(10)
        self.assertEqual(verdicts, ["ok"] * 12)
        self.assertEqual((bulkhead.in_use, bulkhead.waiters), (0, 0))

    def test_slot_bulkhead_returns_to_zero_after_50_interrupted_requests(self) -> None:
        bulkhead = server._SlotBulkhead(max_concurrent=1, max_waiters=50, wait_timeout_s=0.05)
        self.assertEqual(bulkhead.acquire_ex(), "ok")
        verdicts: list[str] = []
        threads = [threading.Thread(target=lambda: verdicts.append(bulkhead.acquire_ex())) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertEqual(verdicts, ["timeout"] * 50)
        self.assertEqual((bulkhead.in_use, bulkhead.waiters), (1, 0))
        bulkhead.release()
        self.assertEqual(bulkhead.in_use, 0)
        bulkhead.release()  # лишний release не уводит счётчик в минус
        self.assertEqual(bulkhead.in_use, 0)

    def test_slot_bulkhead_cancellation_inside_wait_restores_waiters(self) -> None:
        bulkhead = server._SlotBulkhead(max_concurrent=1, max_waiters=3, wait_timeout_s=30.0)
        self.assertEqual(bulkhead.acquire_ex(), "ok")
        with mock.patch.object(bulkhead._cond, "wait", side_effect=KeyboardInterrupt):
            for _ in range(5):
                with self.assertRaises(KeyboardInterrupt):
                    bulkhead.acquire_ex()
        self.assertEqual((bulkhead.in_use, bulkhead.waiters), (1, 0))

    def test_slot_bulkhead_uses_injected_clock_for_timeout(self) -> None:
        clock = FakeClock()

        class Cond:  # условная переменная без реального ожидания: время двигают часы
            def __init__(self, fake: FakeClock) -> None:
                self._fake = fake

            def __enter__(self) -> "Cond":
                return self

            def __exit__(self, *exc: Any) -> None:
                return None

            def wait(self, timeout: float) -> None:
                self._fake.sleep(timeout)

            def notify(self) -> None:
                return None

        bulkhead = server._SlotBulkhead(max_concurrent=1, max_waiters=1, wait_timeout_s=15.0, clock_fn=clock)
        bulkhead._cond = Cond(clock)  # type: ignore[assignment]
        self.assertEqual(bulkhead.acquire_ex(), "ok")
        self.assertEqual(bulkhead.acquire_ex(), "timeout")
        self.assertEqual(clock.now, 1015.0)

    # --- R-BULK-I1: ожидания и deadline ---------------------------------------------------------

    def test_startup_gate_wait_is_bounded_and_fails_open(self) -> None:
        server._STARTUP_LOCK.acquire()
        try:
            gate = server._StartupGate(wait_s=0.1)
            started = time.monotonic()
            gate.acquire()
            self.assertLess(time.monotonic() - started, 2.0)
            self.assertFalse(gate._held)
            gate.release()  # no-op: замок чужой
            self.assertTrue(server._STARTUP_LOCK.locked())
        finally:
            server._STARTUP_LOCK.release()
        gate = server._StartupGate(wait_s=0.1)
        gate.acquire()
        self.assertTrue(gate._held)
        gate.release()
        self.assertFalse(server._STARTUP_LOCK.locked())
        self.assertEqual((server.STARTUP_WAIT_S, server.STARTUP_GATE_S), (5.0, 12.0))

    def test_deadline_in_the_past_blocks_next_attempt_and_sleep(self) -> None:
        res = server._Resilience()
        sleeps: list[float] = []
        attempts = server._RequestAttempts(res, time.monotonic() - 1.0, sleep_fn=sleeps.append)
        self.assertFalse(attempts.begin_attempt())
        self.assertFalse(attempts.allow_retry("incomplete_step"))
        self.assertEqual((sleeps, attempts.total_spawns), ([], 0))

    def test_retry_sleep_never_exceeds_remaining_deadline(self) -> None:
        res = server._Resilience()
        sleeps: list[float] = []
        attempts = server._RequestAttempts(res, time.monotonic() + 0.3, sleep_fn=sleeps.append,
                                           rng_fn=lambda _lo, hi: hi)
        with mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.8):
            self.assertTrue(attempts.allow_retry("cli_failure"))
        self.assertEqual(len(sleeps), 1)
        self.assertLessEqual(sleeps[0], 0.3)

    # --- H-CPU-I2 / I3: горячий путь ------------------------------------------------------------

    def test_disabled_step_recovery_does_not_touch_regexes(self) -> None:
        spies = {name: mock.Mock() for name in ("_ACTION_INTENT_RE", "_REASONING_TOOL_PLAN_RE",
                                                "_FINAL_CONCLUSION_RE", "_INTERRUPTED_RE", "_RAW_CALL_RE",
                                                "_NO_TOOLS_RE", "_CALL_INTENT_RE")}
        patches = [mock.patch.object(server, name, spy) for name, spy in spies.items()]
        patches.append(mock.patch.object(server, "STEP_RECOVERY_ENABLED", False))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.assertFalse(server._is_incomplete_tool_step("Читаю…", "plan " * 50, TOOLS, had_mid_stream_error=True,
                                                         output_tokens=900))
        self.assertEqual(sum(spy.search.call_count + spy.match.call_count for spy in spies.values()), 0)

    def test_hot_path_has_no_regex_compile_or_deepcopy(self) -> None:
        import copy
        with (mock.patch.object(re, "_compile", wraps=re._compile) as compiled,
              mock.patch.object(copy, "deepcopy", wraps=copy.deepcopy) as deep):
            for text, reasoning in (("Читаю…", ""), (PREAMBLE, PLAN), ("Привет!", "no tools needed"),
                                    (SWALLOWED_TEXT, "x"), ("Ответ: 42:", "job_output bash")):
                server._is_incomplete_tool_step(text, reasoning, TOOLS, output_tokens=100)
                server._detect_incomplete_tool_step_signal(text, reasoning, TOOLS, True, 300, 150)
            server._is_transient_stream_error({"statusCode": 503, "message": "ECONNRESET"})
            server._retry_backoff_s(2)
        self.assertEqual((compiled.call_count, deep.call_count), (0, 0))

    # --- Расчётные оракулы по константам модуля -------------------------------------------------

    def test_hl_env_01_memory_closure_by_module_constants(self) -> None:
        self.assertEqual(server.STDOUT_QUEUE_MAX, 4096)
        rss_worker, rss_child, mem_limit = 64 * 2**20, 192 * 2**20, 2048 * 2**20
        shared = 6 * rss_child
        self.assertEqual(rss_worker + shared, 1275068416)
        self.assertLessEqual(rss_worker + shared, 0.80 * mem_limit)

    def test_c_mult_i1_i5_by_module_constants(self) -> None:
        concurrent = 6  # MAX_CONCURRENT из plist; дефолт кода (2) укладывается тем более
        self.assertLessEqual(max(server.MAX_CONCURRENT, 1), concurrent)
        self.assertLessEqual(concurrent * 1, 0.60 * 10)
        self.assertEqual(server.MAX_SLOT_WAITERS, 2 * concurrent)
        fds = 1 + (concurrent + server.MAX_SLOT_WAITERS) + concurrent * 3 + 1 + 20
        self.assertLessEqual(fds, 128)
        self.assertLessEqual(128, 0.70 * 4096)
        self.assertLessEqual(0.6 * 1 * 60.0 + 12, 0.50 * (1 * 16383))

    def test_r_bulk_i1_total_auxiliary_wait_by_module_constants(self) -> None:
        cap = server.RETRY_BACKOFF_CAP_S
        base = server.RETRY_BACKOFF_BASE_S
        total = 0.0
        for attempt in range(1, server.MAX_TOTAL_SPAWNS + 1):
            slot_wait = server.SLOT_WAIT_TIMEOUT_S if attempt == 1 else 0.0
            backoff = 0.0 if attempt == 1 else min(cap, base * 2 ** (attempt - 1))
            total += slot_wait + server.STARTUP_WAIT_S + server.SPAWN_WAIT_MAX_S + backoff
        self.assertEqual(total, 48.0)
        self.assertLessEqual(total, 0.30 * 180.0)

    def test_h_cpu_i5_utilisation_by_module_constants(self) -> None:
        t_req = 0.02 + server.MAX_TOTAL_SPAWNS * 0.05
        util = 1.0 * 0.2 * t_req / 1 + 0.02
        self.assertAlmostEqual(util, 0.054, places=6)
        self.assertLessEqual(util, 0.70)
        self.assertLessEqual(util + 0.25, 0.80 * 2.0)

    def test_new_constants_match_architecture_packet(self) -> None:
        self.assertEqual((server.CB_FAIL_THRESHOLD, server.CB_RESET_S), (5, 10.0))
        self.assertEqual((server.RETRY_BUDGET_MAX, server.RETRY_BUDGET_PER_REQUEST,
                          server.RETRY_BUDGET_RESERVE_RPS), (6.0, 0.20, 0.05))
        self.assertEqual((server.SPAWN_RATE_PER_S, server.SPAWN_BURST), (1.0, 1.0))
        self.assertEqual((server.MAX_SLOT_WAITERS, server.SLOT_WAIT_TIMEOUT_S), (12, 15.0))
        self.assertEqual(server.KEEPALIVE_INTERVAL_S, 15.0)
        self.assertLessEqual(server.FAIL_RETRY_LIMIT, server.MAX_TOTAL_SPAWNS - 1)

    def test_server_gets_isolated_resilience_and_main_uses_module_default(self) -> None:
        first = server.Server(("127.0.0.1", 0), server.Handler)
        second = server.Server(("127.0.0.1", 0), server.Handler)
        self.addCleanup(first.server_close)
        self.addCleanup(second.server_close)
        self.assertIsNot(first.resilience, second.resilience)
        self.assertIs(server._slots, server._DEFAULT_RESILIENCE.slots)


if __name__ == "__main__":
    unittest.main()
<<<END ARTIFACT>>>

<<<ARTIFACT path=".ai-team/runs/analyst-teamlead-zen-step-20261024/architecture/architecture-packet.json" sha256="1053a4ca2e97d0eba0f350c3a71e13d8810c1a716e3b1e66a6c7ff0097e4f565" bytes="109328">>>
{
  "schema_version": "1.0",
  "packet_version": "v5",
  "cycle": "cycle-2 (rework after arch-panel r1 NEEDS WORK: Seat 1 F1..F7, Seat 3 F1..F2)",
  "task_id": "ZEN-STEP-INTERRUPTION-001",
  "run_id": "analyst-teamlead-zen-step-20261024",
  "criticality": "S2",
  "profile": "python-bridge-bugfix",
  "status": "APPROVED",
  "summary": "Устранение преждевременного обрыва многошаговых агентных цепочек в opencode-zen-bridge: двойная схема тегов <tool_invoke>/<tool_call> + алиас shell; немедленный _stop_proc на mid-stream etype==error с ретраем только транзиентных ошибок (_is_transient_stream_error); детектор оборванного tool-шага с узким признаком 5 (_ACTION_INTENT_RE) и отдельным kill-switch OPENCODE_ZEN_BRIDGE_STEP_RECOVERY; единый потолок MAX_TOTAL_SPAWNS=3 (A_max) на HTTP-запрос, Full-Jitter backoff, process-level Retry Budget, Circuit Breaker (HALF_OPEN=1) и spawn token-bucket 1.0/с; ограниченные ожидания слота (15 с, max_waiters=12) и _StartupGate (5 с, fail-open); ограниченный _StdoutFeed (maxsize=4096) + SSE keepalive 15 с; fallback dedup_prefix без потери текста. HL-ENV/v1 (46 полей) и 21 стоп-код + T-LIFE/O-EXIT/M-SEM закрыты численно. Контрактные дельты: CD-001 (внутренний prompt), CD-002 (SSE keepalive + finish_reason recovery), CD-003 (ограниченное ожидание слота и 503 circuit open).",
  "requirement_ids": [
    "REQ-001",
    "REQ-002",
    "REQ-003",
    "REQ-004",
    "REQ-005",
    "REQ-006"
  ],
  "requirements": [
    {
      "id": "REQ-001",
      "statement": "Системная инструкция эмуляции требует <tool_invoke>{\"name\":...,\"arguments\":...}</tool_invoke>; ToolCallParser (поток) и _parse_tool_call_blocks (батч) принимают оба тега <tool_invoke> и <tool_call>; в NATIVE_TOOL_ALIASES добавлен ключ \"shell\".",
      "evidence_ids": [
        "EVD-005",
        "EVD-008"
      ]
    },
    {
      "id": "REQ-002",
      "statement": "На etype==\"error\" в Run._execute_once и Handler._stream_sse — немедленный _stop_proc(proc) и вырезание строк _INTERRUPTED_RE из видимого текста. had_mid_stream_error=True выставляется ТОЛЬКО если _is_transient_stream_error(ev): statusCode отсутствует/None/0/408/429/>=500 или message (lower) содержит econnreset|etimedout|timeout|timed out|socket hang up|interrupted|overloaded|rate limit|temporarily unavailable|fetch failed|network. statusCode in (400,401,403,404,422) -> had_mid_stream_error=False, без ретрая (Fail-Closed), ошибка отдаётся клиенту.",
      "evidence_ids": [
        "EVD-001",
        "EVD-004",
        "EVD-009",
        "EVD-012"
      ]
    },
    {
      "id": "REQ-003",
      "statement": "STEP_RECOVERY_ENABLED = os.environ.get(\"OPENCODE_ZEN_BRIDGE_STEP_RECOVERY\", \"1\").strip().lower() not in (\"0\",\"false\",\"no\",\"off\") — отдельный kill-switch, независимый от OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES. _is_incomplete_tool_step(visible_text, reasoning_text, tool_names, had_mid_stream_error=False, output_tokens=0, reasoning_tokens=0) -> bool: первой инструкцией `if not STEP_RECOVERY_ENABLED: return False`; вызывается только при emulate_tools=True и отсутствии распознанных tool_calls; 5 признаков, где признак 5 требует _ACTION_INTENT_RE (явный глагол немедленного действия) и НЕ срабатывает на голом завершающем ':' — \"Ответ: 42:\" и \"Итог проверки:\" -> False.",
      "evidence_ids": [
        "EVD-003",
        "EVD-007",
        "EVD-009",
        "EVD-010",
        "EVD-011"
      ]
    },
    {
      "id": "REQ-004",
      "statement": "MAX_TOTAL_SPAWNS = 3 (A_max): суммарно по первичному запуску, fail_retries и attempt (step-recovery/unmapped) в Handler._stream_sse и Handler._serve_json не более 3 запусков opencode run на HTTP-запрос под единым deadline = time.monotonic() + TIMEOUT_S. Пауза между запусками — _retry_backoff_s(retry_num, rng_fn=random.uniform) = rng_fn(0.0, min(RETRY_BACKOFF_CAP_S, RETRY_BACKOFF_BASE_S * (2 ** retry_num))), RETRY_BACKOFF_BASE_S=0.5, RETRY_BACKOFF_CAP_S=2.0 (заменяет FAIL_RETRY_BACKOFF_S * n). В _stream_sse при attempt > 0: current.startswith(dedup_prefix) -> подавить уже отправленный префикс; если len(current) >= len(dedup_prefix) и not current.startswith(dedup_prefix) -> dedup_prefix = \"\" и клиенту отправляется current[emitted_len:] без потери текста.",
      "evidence_ids": [
        "EVD-003",
        "EVD-006",
        "EVD-015"
      ]
    },
    {
      "id": "REQ-005",
      "statement": "Блокирующий `for raw in proc.stdout` заменяется daemon-потоком _StdoutFeed с queue.Queue(maxsize=STDOUT_QUEUE_MAX), STDOUT_QUEUE_MAX = 4096; запись put_nowait, при queue.Full — флаг overflow, лог `stdout_overflow` и _stop_proc(proc) (попытка считается неуспешной, без неограниченного роста кучи). Потребители: get(timeout=0.25) в Run._execute_once (проверка deadline), get(timeout=1.0) в Handler._stream_sse с ': keepalive\\n\\n' при простое >= KEEPALIVE_INTERVAL_S = 15.0.",
      "evidence_ids": [
        "EVD-006",
        "EVD-013",
        "EVD-015"
      ]
    },
    {
      "id": "REQ-006",
      "statement": "Эндпоинты /health, /v1/models, /v1/chat/completions, порт 127.0.0.1:9883 и схема OpenAI совместимы; изменения наблюдаемого поведения зафиксированы только как CD-002 и CD-003; после деплоя bridges/opencode-zen-bridge/server.py побайтово совпадает с ~/.dsh/bridges/opencode-zen-bridge/server.py (VER-004).",
      "evidence_ids": [
        "EVD-014",
        "EVD-016"
      ]
    }
  ],
  "evidence": [
    {
      "id": "EVD-001",
      "ledger_ref": "F-01",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:1441-1486,1952-1981,2310-2358 (parse_opencode_event)",
      "claim": "step_finish возвращает только tokens и отбрасывает part.reason; etype==error извлекает statusCode/message."
    },
    {
      "id": "EVD-002",
      "ledger_ref": "F-02",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:1961-1964,2329-2332,2412-2423,2541-2561",
      "claim": "Токены step_finish суммируются только для usage и не сравниваются с длиной видимого текста."
    },
    {
      "id": "EVD-003",
      "ledger_ref": "F-03",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:233-239,1874-1882,2379-2403,2420,2509-2519,2547 (Handler._stream_sse, Handler._serve_json)",
      "claim": "Ретрай только при unmapped (NATIVE_RETRY_LIMIT=2) или падении без вывода (FAIL_RETRY_LIMIT=3); оборванный tool-шаг завершается break + finish_reason=stop."
    },
    {
      "id": "EVD-004",
      "ledger_ref": "F-04",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:1977-1981,2338-2342",
      "claim": "etype==error посреди стрима только логируется, proc не останавливается -> opencode run запускает синтетический шаг продолжения."
    },
    {
      "id": "EVD-005",
      "ledger_ref": "F-05",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:179-224,349-390,1007-1096,1223-1385 (ToolCallParser, _parse_tool_call_blocks, NATIVE_TOOL_ALIASES)",
      "claim": "Парсер понимает только <tool_call>; в NATIVE_TOOL_ALIASES нет ключа shell (OpenCode v2.1.2)."
    },
    {
      "id": "EVD-006",
      "ledger_ref": "F-06",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:43-44,641-656,692-725,753-785,975-993,1937-1941,2013,2297-2300",
      "claim": "Мост stateless на запрос; _slots Semaphore + _StartupGate; блокирующий for raw in proc.stdout без keepalive."
    },
    {
      "id": "EVD-007",
      "ledger_ref": "F-07",
      "kind": "document",
      "ref": "~/.local/share/opencode/opencode.db:session_v2/ses_e9231183effexUq1AtanwPx1eg,session_message/msg_16dcee844001sbe9M6aE7ob0qb",
      "claim": "Ход 12: reasoning содержит план вызова тулов, text=168 символов преамбулы, finish=stop, tokens output=499 reasoning=366."
    },
    {
      "id": "EVD-008",
      "ledger_ref": "F-08",
      "kind": "document",
      "ref": "~/.local/share/opencode/opencode.db:session_message/msg_16e398eba001wfHVse61q8hJUN,session_message/msg_16e3a015800106BnYiGKkyJ3WI",
      "claim": "На glm-5.3-flash-free тег <tool_invoke> проходит апстрим (len=283), тег <tool_call> вырезается (content=[], output=75)."
    },
    {
      "id": "EVD-009",
      "ledger_ref": "F-09",
      "kind": "document",
      "ref": "~/.local/share/opencode/opencode.db:session_v2/ses_e92752838ffeR1RI1LOyzoqDQU,ses_e9231183effexUq1AtanwPx1eg,ses_e9263c73fffeRuhHv7uSWVYnf7",
      "claim": "tokens.output включает tokens.reasoning; non_reasoning_output 350/133 против ~46/56 токенов видимого текста; после ECONNRESET синтетическое 'I was interrupted...' с finish=stop."
    },
    {
      "id": "EVD-010",
      "ledger_ref": "F-10",
      "kind": "document",
      "ref": "~/.dsh/storages/session_projcache/sessions/session-00e33abb-224c-4e4b-bd3d-6490f2bc9b87.json:4881,5147,5454",
      "claim": "Три подряд оборванных хода пользователя (Turn 10/11/12) с короткими преамбулами."
    },
    {
      "id": "EVD-011",
      "ledger_ref": "F-11",
      "kind": "document",
      "ref": "~/.dsh/sessions/.../session-00e33abb-224c-4e4b-bd3d-6490f2bc9b87/session.v4.jsonl.zstd:L261-L267",
      "claim": "assistant/message без tool/call и stopReason=stop -> DSH пишет step/end и turn/end completed."
    },
    {
      "id": "EVD-012",
      "ledger_ref": "F-12",
      "kind": "document",
      "ref": "~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log:14571-14721",
      "claim": "Четыре инцидента коррелируют с opencode.db и журналом DSH: два ECONNRESET rc=1 tools=0 и два rc=0 tools=0 out_chars=138/168, retries=0."
    },
    {
      "id": "EVD-013",
      "ledger_ref": "F-13",
      "kind": "document",
      "ref": "~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log:14571-14726",
      "claim": "Длительность оборванных запросов 8-44 с исключает TIMEOUT_S=1800 и Handler.timeout=300."
    },
    {
      "id": "EVD-014",
      "ledger_ref": "F-14",
      "kind": "document",
      "ref": "~/Library/LaunchAgents/com.user.dsh-opencode-zen-bridge.plist:5-33, ~/.dsh/bridges/opencode-zen-bridge/start.sh:6-59",
      "claim": "LaunchAgent KeepAlive, MAX_CONCURRENT=6, однопроцессный ThreadingHTTPServer на 127.0.0.1:9883."
    },
    {
      "id": "EVD-015",
      "ledger_ref": "F-15",
      "kind": "code",
      "ref": "~/.dsh/bridges/opencode-zen-bridge/server.py:45-49,276-282,973-1006,2349,2667",
      "claim": "TIMEOUT_S=1800, Handler.timeout=300, MAX_CONCURRENT=6, STARTUP_GATE_S=12, NATIVE_RETRY_LIMIT=2, FAIL_RETRY_LIMIT=3."
    },
    {
      "id": "EVD-016",
      "ledger_ref": "F-16",
      "kind": "document",
      "ref": "~/.dsh/profiles/desktop/cordis.patch.yml:28-39,179,239",
      "claim": "DSH Desktop маршрутизирует провайдера opencode-zen на http://127.0.0.1:9883/v1."
    },
    {
      "id": "EVD-017",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py@sha256:03eadced631e090a73bcada5579f60bc71ad02858c6e0a72e1f615bd5838673b строки 43-44 (TIMEOUT_S, MAX_CONCURRENT default 2), 233-239 (NATIVE_RETRY_LIMIT, FAIL_RETRY_LIMIT, FAIL_RETRY_BACKOFF_S=0.8), 435-446 (_stop_proc), 692-725 (_StartupGate: _STARTUP_LOCK.acquire() без таймаута; _slots), 2196 (_slots.acquire(timeout=TIMEOUT_S)), 2297 (for raw in proc.stdout), 2386 (time.sleep(FAIL_RETRY_BACKOFF_S * fail_retries)), 2473-2476 (Run.execute из _serve_json)",
      "claim": "Свежая сверка кода (Cycle 2): ожидание слота до TIMEOUT_S=1800 с и ожидание _STARTUP_LOCK без таймаута — R-BULK-I1 без новых ограничений не замыкается; backoff линейный без джиттера; потолка суммарных запусков нет. Функций _complete_response/_stream_response/_run_opencode в коде нет — фактические точки: Handler.do_POST -> Handler._stream_sse | Handler._serve_json -> Run.execute -> Run._execute_once."
    }
  ],
  "risk_triggers": [],
  "assumptions": [
    {
      "id": "ASM-001",
      "statement": "tokens.output в step_finish opencode включает tokens.reasoning, поэтому non_reasoning_output = max(0, output_tokens - reasoning_tokens) корректно оценивает объём невидимого (проглоченного) не-reasoning вывода (OPEN-01 класса МОЖНО ПРОДОЛЖИТЬ).",
      "status": "VALIDATED",
      "evidence_ids": [
        "EVD-007",
        "EVD-009"
      ]
    },
    {
      "id": "ASM-002",
      "statement": "Апстрим opencode.ai/zen (семейство GLM) вырезает <tool_call>, но пропускает нейтральный тег <tool_invoke> без потерь.",
      "status": "VALIDATED",
      "evidence_ids": [
        "EVD-008",
        "EVD-005"
      ]
    },
    {
      "id": "ASM-003",
      "statement": "Профиль памяти/CPU HL-ENV/v1 (Mem_rss_worker_max=64 MiB, 192 MiB RSS на opencode run, U_pod_sidecars=0.25) — инженерная оценка из handoff-architect.md §3 и rework-brief F1, а не замер; при MAX_CONCURRENT=6 (plist, EVD-014). Замер RSS под 6 параллельными запусками — пункт not_verified/hard-path у verifier.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-014",
        "EVD-015"
      ]
    }
  ],
  "drivers": [
    "reliability: многошаговая цепочка не должна завершаться finish_reason=stop при оборванном tool-шаге (REQ-002..REQ-004)",
    "compatibility: внешний HTTP/OpenAI контракт, порт 127.0.0.1:9883 и формат SSE/JSON совместимы; дельты только CD-002/CD-003 (REQ-006)",
    "operability: A_max=3 запуска на запрос, Retry Budget, Circuit Breaker и ограниченные ожидания под единым deadline (REQ-004)",
    "reliability: долгая фаза thinking не должна рвать SSE-соединение клиента; память ограничена (REQ-005)",
    "safety: отдельный kill-switch OPENCODE_ZEN_BRIDGE_STEP_RECOVERY без деплоя кода (REQ-003)"
  ],
  "verification_surface": [
    {
      "id": "VER-001",
      "kind": "command",
      "command": "cd /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/",
      "expected": "exit 0; все тесты моста (существующие и новые test_step_interruption.py) зелёные, 0 failed / 0 errors.",
      "environment": "local macOS, python3 через uvx pytest, фейковый opencode CLI (tests/_fake_cli.py), без сети",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "AD-001",
        "AD-002",
        "AD-003",
        "AD-004",
        "QA-001",
        "QA-002",
        "QA-003",
        "QA-004",
        "QA-005",
        "QA-006",
        "QA-007",
        "QA-008",
        "BND-001",
        "BND-002",
        "BND-003",
        "CD-001",
        "CD-002",
        "CD-003",
        "RISK-001",
        "RISK-002",
        "RISK-003",
        "RISK-004",
        "RISK-005",
        "THREAT-001"
      ]
    },
    {
      "id": "VER-002",
      "kind": "command",
      "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -v",
      "expected": "exit 0; test_step_interruption.py покрывает QA-POS-01..03, QA-NEG-01..02, QA-BND-01..02, QA-FAIL-01..02 (handoff-qa.md) и класс HlResilienceOracles (VER-006); Ran N>=20 tests, OK.",
      "environment": "local macOS, системный python3 stdlib unittest, фейковый opencode CLI, без сети",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "AD-001",
        "AD-002",
        "AD-003",
        "AD-004",
        "QA-001",
        "QA-002",
        "QA-003",
        "QA-004",
        "QA-005",
        "QA-007",
        "QA-008",
        "CD-001",
        "CD-002",
        "RISK-001",
        "RISK-002",
        "RISK-004",
        "RISK-005",
        "THREAT-001"
      ]
    },
    {
      "id": "VER-003",
      "kind": "command",
      "command": "PYTHONPATH=/Users/aazhiry1/work/src/cli-agent-bridge uvx pytest -q -p no:cacheprovider /Users/aazhiry1/work/src/cli-agent-bridge/tests/",
      "expected": "exit 0; корневой набор tests/ зелёный, 0 failed / 0 errors — регрессий в соседних мостах нет.",
      "environment": "local macOS, uvx pytest, PYTHONPATH=корень репозитория",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-006",
        "QA-006",
        "BND-001",
        "BND-002",
        "BND-003",
        "RISK-003"
      ]
    },
    {
      "id": "VER-004",
      "kind": "command",
      "command": "cd /Users/aazhiry1/work/src/cli-agent-bridge && diff -u bridges/opencode-zen-bridge/server.py ~/.dsh/bridges/opencode-zen-bridge/server.py",
      "expected": "exit 0, пустой вывод (после синхронизации деплоя). Baseline Cycle 2: репо sha256=03eadced…673b, ~/.dsh sha256=d619476e…de8a5 — сейчас различаются, проверка выполняется после rollout.",
      "environment": "local macOS, после копирования server.py в ~/.dsh и перед перезапуском LaunchAgent",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-006",
        "CD-002",
        "CD-003",
        "QA-006"
      ]
    },
    {
      "id": "VER-005",
      "kind": "command",
      "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -k skips_step_recovery -k dedup_prefix_mismatch -k colon_not_incomplete -k error_401_not_retried -k error_econnreset_retried -v",
      "expected": "exit 0; Ran >=5 tests, OK. Обязательные тесты: test_serve_json_without_emulate_tools_skips_step_recovery (Handler._serve_json с emulate_tools=False — _is_incomplete_tool_step не вызывается, ровно 1 запуск; это фактическая точка, которую brief называл _complete_response — такой функции в коде нет, EVD-017); test_stream_dedup_prefix_mismatch_emits_full_text (переформулированный ответ на ретрае доходит клиенту целиком); test_short_final_answer_with_colon_not_incomplete ('Ответ: 42:' и 'Итог проверки:' -> False); test_mid_stream_error_401_not_retried (1 запуск, ошибка клиенту) и test_mid_stream_error_econnreset_retried (2 запуска, _stop_proc вызван).",
      "environment": "local macOS, системный python3 stdlib unittest, фейковый opencode CLI, без сети",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "AD-002",
        "AD-003",
        "QA-003",
        "QA-007",
        "RISK-001",
        "RISK-004"
      ]
    },
    {
      "id": "VER-006",
      "kind": "command",
      "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -k HlResilienceOracles -v",
      "expected": "exit 0; детерминированные оракулы (FakeClock / инъекция rng_fn / call_count, без wall-clock): backoff u∈[0.0,0.5,1.0] -> [0.0, 0.5*cap_a, 1.0*cap_a] для retry_num 1..2 (S-HERD-I2); spawn token-bucket не более 1 запуска/с на FakeClock (S-HERD-I1); MAX_TOTAL_SPAWNS=3 на всех комбинациях fail_retries/attempt (R-BULK-I2); Retry Budget N_retries <= floor(0.2*N_req + 0.05*T_w) + 6 на 100 падающих запросах (R-BULK-I2); Circuit Breaker: 5 транзиентных отказов -> OPEN, после cooldown*U(0.8,1.2) из 10 потоков ровно 1 probe (R-BULK-I3); 13-й ожидающий слота при 6 занятых и 12 ждущих -> мгновенный 503 (C-MULT-I2); слот и waiters возвращаются в 0 после 50 прерванных запросов (C-MULT-I4); _StdoutFeed queue.Full -> _stop_proc (H-CPU-I3); STEP_RECOVERY_ENABLED=False -> детектор не трогает regex (spy call_count==0) (H-CPU-I3); spy re._compile/copy.deepcopy call_count==0 на горячем пути (H-CPU-I2); при clock.now()>=deadline следующая попытка не стартует (R-BULK-I1); расчётные тесты HL-ENV-01, C-MULT-I1, C-MULT-I5, H-CPU-I5, R-BULK-I1 по константам модуля. Ran N>=14 tests, OK.",
      "environment": "local macOS, системный python3 stdlib unittest, без сети",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-004",
        "REQ-005",
        "AD-003",
        "AD-004",
        "QA-005",
        "QA-008",
        "RISK-002",
        "RISK-005",
        "CD-003"
      ]
    }
  ],
  "decisions": [
    {
      "id": "AD-001",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как доставить текстовые вызовы инструментов через апстрим opencode.ai/zen, который вырезает <tool_call>, и маппить встроенный shell OpenCode v2.1.2?",
      "choice": "Двойная схема тегов: системная инструкция эмуляции требует <tool_invoke>{\"name\":...,\"arguments\":...}</tool_invoke>; ToolCallParser (поток) и _parse_tool_call_blocks (батч) принимают оба тега <tool_invoke> и <tool_call>; в NATIVE_TOOL_ALIASES добавляется ключ \"shell\" с кандидатами клиентского shell-инструмента (как у \"bash\").",
      "alternatives": [
        "Оставить только <tool_call> и полагаться на ретрай-детектор (каждый шаг GLM тратит лишнюю попытку, детекция вероятностна)",
        "Перейти полностью на <tool_invoke> без поддержки <tool_call> (ломает модели/истории, уже выдающие <tool_call>)",
        "Перейти на JSON-only вывод без XML-тегов (большой рефакторинг парсера, хрупко на смешанном тексте)"
      ],
      "drivers": [
        "reliability",
        "compatibility"
      ],
      "evidence_ids": [
        "EVD-005",
        "EVD-008",
        "EVD-016"
      ],
      "evidence_refs": [
        "EVD-005",
        "EVD-008",
        "EVD-016"
      ],
      "consequences": [
        "Шаги GLM перестают терять вызовы на уровне апстрима (EVD-008)",
        "Обратная совместимость: <tool_call> продолжает распознаваться",
        "Парсер усложняется второй парой open/close-маркеров; потоковый буфер должен удерживать префикс обоих тегов"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -v",
        "expected": "QA-POS-01 и QA-POS-02 зелёные: оба тега дают одинаковые name/arguments, shell маппится в клиентский shell-инструмент."
      }
    },
    {
      "id": "AD-002",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как обнаружить и восстановить оборванный инструментальный шаг (mid-stream error, синтетическое продолжение, проглоченный <tool_call>, преамбула намерения) без ложных ретраев на коротких финальных ответах и детерминированных ошибках?",
      "choice": "1) На etype==\"error\" — немедленный _stop_proc(proc) (opencode run не успевает запустить синтетический шаг) и _strip_interrupted_notice; had_mid_stream_error=True только если _is_transient_stream_error(ev) (statusCode None/0/408/429/>=500 или маркеры econnreset|etimedout|timeout|timed out|socket hang up|interrupted|overloaded|rate limit|temporarily unavailable|fetch failed|network); 400/401/403/404/422 -> False, Fail-Closed без ретрая. 2) Kill-switch STEP_RECOVERY_ENABLED = os.environ.get(\"OPENCODE_ZEN_BRIDGE_STEP_RECOVERY\", \"1\").strip().lower() not in (\"0\",\"false\",\"no\",\"off\"), независимый от OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES; при False детектор возвращает False первой инструкцией (O(1)). 3) _is_incomplete_tool_step(visible_text, reasoning_text, tool_names, had_mid_stream_error=False, output_tokens=0, reasoning_tokens=0) — только при emulate_tools=True и отсутствии tool_calls; признаки: (1) транзиентная ошибка; (2) _INTERRUPTED_RE в visible/reasoning; (3) swallowed tokens: non_reasoning_output = max(0, output_tokens - reasoning_tokens) при reasoning_tokens>0 and output_tokens>=reasoning_tokens, иначе output_tokens; срабатывает при len(stripped)<=600 и non_reasoning_output - max(1, len(stripped)//3) >= SWALLOWED_TOKENS_MIN (35); (4) имена tool_names + _REASONING_TOOL_PLAN_RE в reasoning при видимом <=600; (5) УЗКАЯ преамбула: <=420 символов, <=6 строк, без таблицы/кода/_FINAL_CONCLUSION_RE, ОБЯЗАТЕЛЬНО совпадение _ACTION_INTENT_RE (явный глагол немедленного действия: 'Читаю…', 'Собираю факты…', 'Теперь посмотрим…', 'Let's check…', 'I'll run…') И (окончание на ':'/'...'/'…' ИЛИ длина <=220). Голое ':' без _ACTION_INTENT_RE и без признаков 3/4 -> False ('Ответ: 42:' -> False). 4) При срабатывании — дозапрос _incomplete_tool_step_prompt(tool_names, partial_text) в _stream_sse и _serve_json в рамках MAX_TOTAL_SPAWNS=3 и Retry Budget (AD-004). При успешном дозапросе с tool_calls клиент получает finish_reason=\"tool_calls\" вместо прежнего ошибочного \"stop\" (CD-002).",
      "alternatives": [
        "Только останавливать proc на error без детектора (не покрывает проглоченный <tool_call> и преамбулы Turn 10/12)",
        "Детектор без вычитания reasoning_tokens (ложные дозапросы на коротких финальных ответах с большим reasoning, QA-NEG-01)",
        "Возвращать клиенту finish_reason=length/ошибку вместо дозапроса (DSH всё равно завершает ход или показывает ошибку)",
        "Неограниченный ретрай до появления tool_calls (UNBOUNDED_RETRY / RETRY_STORM)",
        "Признак 5 по голому завершающему ':' без глагола намерения (ложные дозапросы на коротких финальных ответах — отклонено Seat 1 F4)",
        "Ретраить любой etype==error включая 401/403 (бесполезные запуски и задержка при детерминированных ошибках — отклонено Seat 1 F5)"
      ],
      "drivers": [
        "reliability",
        "operability",
        "compatibility"
      ],
      "evidence_ids": [
        "EVD-001",
        "EVD-002",
        "EVD-003",
        "EVD-004",
        "EVD-007",
        "EVD-009",
        "EVD-010",
        "EVD-011",
        "EVD-012"
      ],
      "evidence_refs": [
        "EVD-001",
        "EVD-002",
        "EVD-003",
        "EVD-004",
        "EVD-007",
        "EVD-009",
        "EVD-010",
        "EVD-011",
        "EVD-012"
      ],
      "consequences": [
        "Реальные сбои детектируются: 350-46=304>=35 (Turn 10), 133-56=77>=35 (Turn 12), маркер interrupted + ECONNRESET (Turn 11)",
        "Короткий финальный ответ с output=400 reasoning=385 даёт 15<35 -> без дозапроса; 'Ответ: 42:' -> без дозапроса",
        "401/403/400/404/422 не ретраятся: 1 запуск, ошибка клиенту без задержки",
        "Откат детектора без деплоя: OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0 в EnvironmentVariables plist + перезапуск LaunchAgent; unmapped-ретрай не затрагивается"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -k skips_step_recovery -k dedup_prefix_mismatch -k colon_not_incomplete -k error_401_not_retried -k error_econnreset_retried -v",
        "expected": "VER-005 зелёный; плюс QA-POS-03, QA-NEG-01/02, QA-BND-01/02, QA-FAIL-01 в VER-002."
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как устроить цикл исполнения попыток: ограниченное чтение stdout, keepalive, дедлайн, единый потолок запусков, backoff и дедупликация SSE-префикса без потери текста?",
      "choice": "1) _StdoutFeed: daemon-поток читает proc.stdout в queue.Queue(maxsize=STDOUT_QUEUE_MAX), STDOUT_QUEUE_MAX=4096, put_nowait; при queue.Full — overflow=True, лог `stdout_overflow`, _stop_proc(proc) — попытка неуспешна (данные не дропаются молча); по EOF кладёт sentinel. Потребители: get(timeout=0.25) в Run._execute_once, get(timeout=1.0) в Handler._stream_sse; ': keepalive\\n\\n' при простое >= KEEPALIVE_INTERVAL_S=15.0. Один _StdoutFeed на живой proc; старый proc останавливается _stop_proc до следующего запуска (T-LIFE/v1). 2) MAX_TOTAL_SPAWNS=3 (A_max): единый счётчик total_spawns на HTTP-запрос в Handler._stream_sse и Handler._serve_json (через Run) суммирует первичный запуск, fail_retries и attempt; запуск №4 невозможен ни при какой комбинации классов ретрая; существующие NATIVE_RETRY_LIMIT/FAIL_RETRY_LIMIT остаются верхними границами внутри потолка. 3) _retry_backoff_s(retry_num, rng_fn=random.uniform) = rng_fn(0.0, min(RETRY_BACKOFF_CAP_S, RETRY_BACKOFF_BASE_S * (2 ** retry_num))), BASE=0.5, CAP=2.0: retry 1 -> U(0,1.0), retry 2 -> U(0,2.0); заменяет FAIL_RETRY_BACKOFF_S*n; сон не превышает deadline - monotonic(). 4) dedup_prefix в _stream_sse при attempt>0: если current.startswith(dedup_prefix) — emitted_len=len(dedup_prefix), подавить префикс; если len(current) >= len(dedup_prefix) и not current.startswith(dedup_prefix) — dedup_prefix=\"\" и клиенту уходит current[emitted_len:] (emitted_len — длина реально отправленного в этой попытке), текст не теряется (возможен видимый повтор формулировки — допустимо, потеря — нет). 5) _StartupGate: ранний release по первому полезному событию step_start/text/reasoning/tool_use или выходу процесса (типично ~1.5–2.0 с), STARTUP_GATE_S=12.0 — только аварийный потолок удержания; latency_p95_ms=90000, SLA_p99_s=180.0.",
      "alternatives": [
        "selectors/select на pipe-дескрипторе (непереносимо с текстовым буфером Popen, сложнее)",
        "Переписать мост на asyncio (несоразмерный рефакторинг ThreadingHTTPServer)",
        "Неограниченная queue.Queue() (UNBOUNDED_QUEUE, рост кучи — отклонено Seat 1 F2)",
        "Раздельные лимиты 2/3 без общего потолка (до 1+2+3=6 запусков на запрос — отклонено Seat 1 F3)",
        "Обрезать current до dedup_prefix при несовпадении (потеря текста — отклонено Seat 1 F5)"
      ],
      "drivers": [
        "reliability",
        "operability"
      ],
      "evidence_ids": [
        "EVD-006",
        "EVD-013",
        "EVD-014",
        "EVD-015",
        "EVD-017"
      ],
      "evidence_refs": [
        "EVD-006",
        "EVD-013",
        "EVD-014",
        "EVD-015",
        "EVD-017"
      ],
      "consequences": [
        "Клиент получает keepalive каждые 15 с во время thinking; дедлайн проверяется каждые <=0.25/1.0 с",
        "Память на поток чтения ограничена 4096 строками; переполнение = контролируемый отказ попытки",
        "Худший случай латентности — 3 запуска в одном слоте; паузы суммарно <= 1.0 + 2.0 = 3.0 с",
        "+1 daemon-поток на активный proc (<=6), threads_per_worker=12"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -v",
        "expected": "QA-FAIL-02 (keepalive/deadline), QA-POS-03 и test_stream_dedup_prefix_mismatch_emits_full_text, HlResilienceOracles: MAX_TOTAL_SPAWNS и backoff-точки — зелёные."
      }
    },
    {
      "id": "AD-004",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как замкнуть неснимаемые гейты S-HERD-I1, R-BULK-I1..I3 и C-MULT-I2, если в текущем коде ожидание слота до 1800 с, _STARTUP_LOCK без таймаута и нет ни Retry Budget, ни Circuit Breaker (EVD-017)?",
      "choice": "1) Bulkhead слота: SLOT_WAIT_S = 15.0 (env OPENCODE_ZEN_BRIDGE_SLOT_WAIT_S) вместо TIMEOUT_S в _slots.acquire; SLOT_MAX_WAITERS = 12 (= 2 × MAX_CONCURRENT при 6) — счётчик ожидающих под lock, 13-й ожидающий получает немедленный 503 {\"error\":{\"message\":\"bridge busy\",\"type\":\"overloaded\"}} (существующий payload); счётчик уменьшается в finally. Применяется ко всем путям, разделяющим _slots (_stream_sse, _serve_json, _stream_google_sse). 2) _StartupGate.acquire: _STARTUP_LOCK.acquire(timeout=STARTUP_WAIT_S), STARTUP_WAIT_S = 5.0; при таймауте — Fail-Open (вспомогательная сериализация sqlite): запуск без удержания замка + лог `startup_gate_wait_timeout`; возможный «database is locked» классифицируется существующим _is_retryable_failure и укладывается в MAX_TOTAL_SPAWNS. 3) Spawn token-bucket _SpawnRateLimiter (capacity=1, refill SPAWN_RATE_PER_S = 1.0 токен/с = 0.50 × Limit_dep_rps[opencode_cli]), реализован резервированием (GCRA, FIFO по моменту резерва): t_start = max(now, next_free), next_free = t_start + 1/SPAWN_RATE_PER_S, wait = t_start - now; если wait > deadline - now — запуск отменяется; лимитер вызывается перед КАЖДЫМ Popen, включая fail-open; не обходится; ожидание токена <= (MAX_CONCURRENT-1)/SPAWN_RATE_PER_S = 5.0 с; инъекция clock для тестов. 4) Process-level Retry Budget _RetryBudget: capacity = B_retry_max = 6, старт = 6, +0.20 токена на каждый первичный запрос + min_reserve_retry_rps × Δt (0.05/с); каждый повторный запуск (номер 2 и 3) списывает 1 токен; нет токена -> повтор не выполняется, клиенту уходит результат последней попытки (накопленный текст с finish_reason=stop либо ошибка). 5) Circuit Breaker _UpstreamBreaker (per-process, зависимость opencode_cli): OPEN после CB_FAIL_THRESHOLD = 5 подряд транзиентных отказов попытки (транзиентная ошибка/rc!=0 без вывода/overflow), cooldown CB_RESET_S = 10.0 × U(0.8,1.2); в OPEN новые запуски не делаются (0 с, без spawn): первичный запрос -> 503 {\"error\":{\"message\":\"upstream circuit open\",\"type\":\"overloaded\"}} (SSE — через _sse_error), повтор -> отказ от повтора; HALF_OPEN — ровно 1 пробный запуск на процесс, остальные fast-fail до исхода пробы; успех -> CLOSED. Детерминированные 4xx в счётчик не входят.",
      "alternatives": [
        "Оставить ожидание слота TIMEOUT_S=1800 с (R-BULK-I1: sum T_wait = 1800 >> 54 с — неснимаемый FAIL)",
        "Fail-Closed по таймауту _StartupGate (503 при пачке из 6 одновременных стартов — регрессия параллельных сабагентов DSH)",
        "Считать S-HERD-I1 по формуле без лимитера (B=5.24 req/с > 1.0 — FAIL)",
        "Circuit Breaker только на путь ретраев (не соответствует R-BULK-I3: вызовы в OPEN должны уходить в fallback без обращения)"
      ],
      "drivers": [
        "reliability",
        "operability"
      ],
      "evidence_ids": [
        "EVD-006",
        "EVD-012",
        "EVD-014",
        "EVD-015",
        "EVD-017"
      ],
      "evidence_refs": [
        "EVD-006",
        "EVD-012",
        "EVD-014",
        "EVD-015",
        "EVD-017"
      ],
      "consequences": [
        "При 6 занятых слотах 7-й..18-й запросы ждут <= 15 с, 19-й получает 503 сразу; DSH видит тот же тип ошибки overloaded (CD-003)",
        "При 5 подряд транзиентных отказах апстрима мост ~8–12 с отвечает 503 без запусков, затем 1 probe",
        "Темп запусков opencode run <= 1.0/с при любой нагрузке; в типичном режиме (_StartupGate держит 1.5–2.0 с) лимитер не добавляет задержки",
        "Новые константы SLOT_WAIT_S, SLOT_MAX_WAITERS, STARTUP_WAIT_S, SPAWN_RATE_PER_S, B_RETRY_MAX, CB_FAIL_THRESHOLD, CB_RESET_S — env-переопределяемые, внутренние"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -k HlResilienceOracles -v",
        "expected": "VER-006 зелёный: token-bucket, Retry Budget, Breaker HALF_OPEN=1, bounded waiters, deadline-обрыв."
      }
    }
  ],
  "quality_scenarios": [
    {
      "id": "QA-001",
      "quality": "reliability",
      "source": "апстрим opencode.ai/zen (GLM)",
      "stimulus": "модель выдаёт вызов инструмента текстовым тегом",
      "environment": "emulate_tools=True, нормальная работа",
      "artifact": "_build_tool instruction + ToolCallParser/_parse_tool_call_blocks",
      "response": "вызов доходит до клиента как OpenAI tool_calls",
      "response_measure": "100% вызовов в <tool_invoke> и <tool_call> распознаются одинаково (QA-POS-01/02)",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "QA-002",
      "quality": "reliability",
      "source": "апстрим opencode.ai/zen",
      "stimulus": "блок <tool_call> проглочен, видна только короткая преамбула, step_finish output=506 reasoning=156",
      "environment": "emulate_tools=True, SSE и JSON",
      "artifact": "_is_incomplete_tool_step + цикл дозапроса",
      "response": "мост делает дозапрос и возвращает finish_reason=tool_calls без дублирования преамбулы",
      "response_measure": "суммарно <= MAX_TOTAL_SPAWNS=3 запусков на запрос; 0 дубликатов префикса и 0 потерь текста в SSE (QA-POS-03, dedup mismatch)",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "QA-003",
      "quality": "reliability",
      "source": "модель",
      "stimulus": "короткий финальный ответ с output=400 reasoning=385 или 'Ответ: 42:' без глагола намерения",
      "environment": "emulate_tools=True",
      "artifact": "_is_incomplete_tool_step",
      "response": "детектор возвращает False, ответ отдаётся с первой попытки",
      "response_measure": "0 ложных дозапросов на QA-NEG-01/02 и 'Ответ: 42:'; граница 34->False, 35->True (QA-BND-01)",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "QA-004",
      "quality": "reliability",
      "source": "сеть апстрима",
      "stimulus": "mid-stream etype=error (read ECONNRESET) после частичного текста",
      "environment": "SSE и JSON",
      "artifact": "Run._execute_once, Handler._stream_sse, _stop_proc, _strip_interrupted_notice",
      "response": "proc останавливается немедленно, синтетическое 'I was interrupted...' не попадает клиенту, выполняется дозапрос",
      "response_measure": "0 строк _INTERRUPTED_RE в ответе клиенту; 0 живых дочерних процессов после попытки (QA-FAIL-01)",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "QA-005",
      "quality": "operability",
      "source": "opencode run в фазе thinking",
      "stimulus": "stdout молчит дольше 15 с / дольше TIMEOUT_S",
      "environment": "SSE-стрим",
      "artifact": "_StdoutFeed + KEEPALIVE_INTERVAL_S",
      "response": "клиент получает ': keepalive', по дедлайну процесс останавливается",
      "response_measure": "интервал keepalive <= 15 с +1 с; разблокировка ожидания <= 1 с после deadline; очередь stdout <= 4096 (QA-FAIL-02)",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-006"
      ]
    },
    {
      "id": "QA-006",
      "quality": "compatibility",
      "source": "DSH Desktop и другие клиенты",
      "stimulus": "обычные запросы /health, /v1/models, /v1/chat/completions",
      "environment": "127.0.0.1:9883, после деплоя фикса",
      "artifact": "HTTP API моста",
      "response": "формат SSE/JSON OpenAI, порт и эндпоинты не изменились; дельты только CD-002/CD-003; репо == ~/.dsh",
      "response_measure": "существующие тесты моста и корневые tests/ зелёные (QA-REG-01); diff -u exit 0",
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-004"
      ]
    },
    {
      "id": "QA-007",
      "quality": "reliability",
      "source": "апстрим opencode.ai/zen",
      "stimulus": "mid-stream etype=error со statusCode=401 (детерминированная) vs message 'read ECONNRESET' (транзиентная)",
      "environment": "SSE и JSON, emulate_tools=True",
      "artifact": "_is_transient_stream_error + цикл попыток",
      "response": "401 — без ретрая, ошибка клиенту; ECONNRESET — _stop_proc и повтор в рамках A_max и Retry Budget",
      "response_measure": "401: ровно 1 запуск; ECONNRESET: ровно 2 запуска, 0 живых дочерних процессов после запроса",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "QA-008",
      "quality": "operability",
      "source": "DSH Desktop (параллельные сабагенты) / деградация апстрима",
      "stimulus": "19 одновременных запросов при MAX_CONCURRENT=6; 5 подряд транзиентных отказов апстрима",
      "environment": "127.0.0.1:9883, FakeClock в тестах",
      "artifact": "_slots + SLOT_MAX_WAITERS, _UpstreamBreaker, _SpawnRateLimiter, _RetryBudget",
      "response": "6 работают, 12 ждут <= 15 с, 19-й — мгновенный 503; breaker OPEN -> 503 без spawn, затем 1 probe",
      "response_measure": "темп spawn <= 1.0/с; N_retries <= floor(0.2*N_req + 0.05*T_w) + 6; probe_calls == 1",
      "verification_ids": [
        "VER-001",
        "VER-006"
      ]
    }
  ],
  "boundaries": [
    {
      "id": "BND-001",
      "component": "server.py: слой парсинга (ToolCallParser, _parse_tool_call_blocks, _split_tool_calls, _native_to_tool_calls, NATIVE_TOOL_ALIASES)",
      "responsibility": "Чистое преобразование текста/нативных событий в OpenAI tool_calls; без I/O и без знания о ретраях.",
      "allowed_dependencies": [
        "stdlib json/re",
        "список tools клиента"
      ],
      "forbidden_dependencies": [
        "subprocess / proc",
        "Handler / сокет клиента",
        "глобальное состояние ретраев"
      ],
      "verification_ids": [
        "VER-001",
        "VER-003"
      ]
    },
    {
      "id": "BND-002",
      "component": "server.py: детектор и классификаторы (_is_incomplete_tool_step, _is_transient_stream_error, _strip_interrupted_notice, _incomplete_tool_step_prompt, _INTERRUPTED_RE, _REASONING_TOOL_PLAN_RE, _ACTION_INTENT_RE, _FINAL_CONCLUSION_RE, STEP_RECOVERY_ENABLED)",
      "responsibility": "Детерминированные чистые функции решения 'шаг оборван' и формирования промпта дозапроса.",
      "allowed_dependencies": [
        "stdlib re",
        "константы SWALLOWED_TOKENS_MIN и пороги длины"
      ],
      "forbidden_dependencies": [
        "subprocess / proc",
        "сеть",
        "время/рандом",
        "Handler"
      ],
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-005"
      ]
    },
    {
      "id": "BND-003",
      "component": "server.py: исполнение и транспорт (Run._execute_once, Handler._stream_sse, Handler._serve_json, _StdoutFeed, _stop_proc, _slots + SLOT_MAX_WAITERS, _StartupGate, _SpawnRateLimiter, _RetryBudget, _UpstreamBreaker, _retry_backoff_s)",
      "responsibility": "Жизненный цикл opencode run, единый deadline, бюджет попыток, keepalive, уборка процессов; вызывает BND-001/BND-002, но не наоборот.",
      "allowed_dependencies": [
        "BND-001",
        "BND-002",
        "subprocess",
        "threading",
        "queue",
        "random (инъектируемый rng_fn)",
        "time.monotonic (инъектируемые часы в лимитерах)"
      ],
      "forbidden_dependencies": [
        "изменение внешних эндпоинтов и формата ответа OpenAI",
        "новые сторонние зависимости"
      ],
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-006"
      ]
    }
  ],
  "contract_deltas": [
    {
      "id": "CD-001",
      "type": "behavior",
      "producer": "opencode-zen-bridge (системная инструкция эмуляции тулов)",
      "consumer": "модель апстрима opencode.ai/zen через opencode run",
      "change": "Внутренний prompt-контракт мост->модель: модели предписывается тег <tool_invoke> вместо <tool_call>; мост продолжает принимать оба тега. Внешний HTTP/OpenAI контракт мост->DSH не меняется.",
      "compatibility": "backward-compatible: <tool_call> по-прежнему парсится; клиент видит те же OpenAI tool_calls и finish_reason",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "CD-002",
      "type": "behavior",
      "producer": "opencode-zen-bridge (Handler._stream_sse / Handler._serve_json)",
      "consumer": "DSH Desktop и другие OpenAI-совместимые клиенты 127.0.0.1:9883/v1",
      "change": "(а) В SSE-стриме при простое stdout >= 15 с мост шлёт строку-комментарий ': keepalive\\n\\n'; (б) при успешном восстановлении оборванного шага (AD-002) итоговый finish_reason ответа = \"tool_calls\" вместо прежнего ошибочного \"stop\", а tool_calls присутствуют в delta/message.",
      "compatibility": "backward-compatible: строки SSE, начинающиеся с ':', — комментарии и игнорируются клиентами (WHATWG HTML Living Standard, Server-sent events, 'If the line starts with a U+003A COLON character, ignore the line'); \"tool_calls\" — штатное значение finish_reason OpenAI Chat Completions; эндпоинты, порт и схема чанков не меняются. Mixed-version: клиенту безразлично, старый мост просто не шлёт keepalive. Явно требуется текущей задачей (handoff-architect.md REQ-005/REQ-006, rework-brief F6).",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-004"
      ]
    },
    {
      "id": "CD-003",
      "type": "behavior",
      "producer": "opencode-zen-bridge (Handler: _slots bulkhead, _UpstreamBreaker)",
      "consumer": "DSH Desktop и другие OpenAI-совместимые клиенты 127.0.0.1:9883/v1",
      "change": "Ожидание свободного слота ограничено SLOT_WAIT_S=15 с и SLOT_MAX_WAITERS=12 (было до TIMEOUT_S=1800 с без лимита ожидающих); при OPEN Circuit Breaker ответ HTTP 503 с message \"upstream circuit open\". Тип ошибки и статус прежние: 503 {\"error\":{\"type\":\"overloaded\"}}.",
      "compatibility": "backward-compatible по схеме: тот же HTTP 503 и error.type=overloaded, что уже отдаётся при таймауте слота; меняется только момент отказа (15 с вместо 1800 с) и добавляется новый message. Требуется закрытием неснимаемого R-BULK-I1/C-MULT-I2 (AD-004). Риск обработки 503 клиентом DSH — RISK-005, проверка — hard-path verifier.",
      "verification_ids": [
        "VER-001",
        "VER-004",
        "VER-006"
      ]
    }
  ],
  "views": [
    {
      "id": "VIEW-001",
      "type": "dynamic",
      "question": "Как оборванный tool-шаг проходит через opencode run -> мост -> DSH и где вмешивается детектор/дозапрос?",
      "artifact_ref": "analysis/zen-step-interruption/handoff-architect.md#1-контекст-и-доказанная-корневая-причина"
    },
    {
      "id": "VIEW-002",
      "type": "component",
      "question": "Какие компоненты server.py меняются и в каком направлении зависимости?",
      "artifact_ref": "architecture/architecture-packet.json#boundaries (BND-001..BND-003) + decisions AD-003/AD-004"
    },
    {
      "id": "VIEW-003",
      "type": "deployment",
      "question": "Где и как запущен мост?",
      "artifact_ref": "~/Library/LaunchAgents/com.user.dsh-opencode-zen-bridge.plist (EVD-014): однопроцессный ThreadingHTTPServer 127.0.0.1:9883"
    },
    {
      "id": "VIEW-004",
      "type": "dynamic",
      "question": "Как выглядит цикл попыток одного HTTP-запроса с бюджетами (slot -> gate -> token -> spawn -> feed -> detector -> backoff -> retry/finish)?",
      "artifact_ref": "architecture/architecture-packet.json#resilience_gates.dependency_failure_matrix + R_BULK.R-BULK-I1"
    }
  ],
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "Ложное срабатывание признака 5 (преамбула намерения) или 4 (план в reasoning) на легитимном коротком ответе -> лишние запуски opencode run и задержка ответа.",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Признак 5 требует _ACTION_INTENT_RE (голое ':' не триггерит); вычитание reasoning_tokens; пороги 420/600; исключение таблиц/кода/финальных выводов; MAX_TOTAL_SPAWNS=3 и Retry Budget; fallback на накопленный текст; kill-switch OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0; тесты QA-NEG-01/02 и VER-005.",
      "evidence_refs": [
        "EVD-007",
        "EVD-010",
        "EVD-011"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "RISK-002",
      "scenario": "Дозапросы утраивают латентность хода (до 3 запусков) и удерживают слот _slots дольше; при шторме отказов — умножение нагрузки на апстрим.",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Единый deadline; слот берётся один раз на запрос; MAX_TOTAL_SPAWNS=3; Retry Budget (B_retry_max=6, +0.2/запрос); Circuit Breaker (5 отказов -> OPEN, HALF_OPEN=1); spawn token-bucket 1.0/с; QA-BND-02, VER-006.",
      "evidence_refs": [
        "EVD-013",
        "EVD-014",
        "EVD-015"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-006"
      ]
    },
    {
      "id": "RISK-003",
      "scenario": "Апстрим начнёт вырезать и <tool_invoke> либо другие модели Zen (kimi-k2.5, qwen3.6-plus) имеют иной профиль токенов -> SWALLOWED_TOKENS_MIN=35 некалиброван.",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Детектор swallowed tokens — второй рубеж поверх двойной схемы тегов; порог в константе; Q-001 — калибровка как follow-up; регрессия VER-003.",
      "evidence_refs": [
        "EVD-008",
        "EVD-009"
      ],
      "verification_ids": [
        "VER-001",
        "VER-003"
      ]
    },
    {
      "id": "RISK-004",
      "scenario": "dedup_prefix не совпадает с префиксом повторной попытки -> дублирование или потеря текста в SSE.",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Совпадение — подавление отправленного префикса; несовпадение (len(current) >= len(dedup_prefix)) — dedup_prefix=\"\" и отправка current[emitted_len:] целиком (потеря исключена, возможен видимый повтор); тесты QA-POS-03 и test_stream_dedup_prefix_mismatch_emits_full_text (VER-005).",
      "evidence_refs": [
        "EVD-003",
        "EVD-006",
        "EVD-012",
        "EVD-016"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "RISK-005",
      "scenario": "Ограничение ожидания слота 15 с / max_waiters=12 и 503 'upstream circuit open' (CD-003) приводят к видимым ошибкам в DSH при пачке параллельных сабагентов, если DSH не ретраит 503 overloaded.",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Тот же 503 overloaded, что уже отдаётся при таймауте слота; 18 одновременных запросов (6+12) обслуживаются без отказа; константы env-переопределяемые (OPENCODE_ZEN_BRIDGE_SLOT_WAIT_S); hard-path проверка verifier пачкой параллельных сабагентов DSH; при регрессии — поднять SLOT_WAIT_S в пределах R-BULK-I1 (<= 21 с при прочих бюджетах).",
      "evidence_refs": [
        "EVD-014",
        "EVD-017"
      ],
      "verification_ids": [
        "VER-001",
        "VER-006"
      ]
    }
  ],
  "threat_model": {
    "required": false,
    "reason": "S2 без risk_triggers: мост слушает только 127.0.0.1, auth/PII/новых внешних поверхностей не добавляется.",
    "assets": [
      "инструменты клиента DSH (исполнение shell/edit на машине владельца)",
      "история диалога (prompt) в stdin opencode run"
    ],
    "trust_boundaries": [
      "DSH Desktop -> мост 127.0.0.1:9883 (локальный HTTP)",
      "мост -> opencode run -> апстрим opencode.ai/zen (внешняя модель)"
    ],
    "threats": [
      {
        "id": "THREAT-001",
        "scenario": "Prompt-injection в выводе инструмента или ответе модели содержит <tool_invoke>/<tool_call> и порождает непредусмотренный tool_call; дозапрос повторно отправляет частичный текст модели.",
        "mitigation": "Парсер маппит только имена из списка tools текущего запроса клиента; исполнение и разрешения остаются на стороне DSH (permission ask/approval); встроенные тулы opencode не исполняются в мосте (permission *=ask); дозапрос ограничен MAX_TOTAL_SPAWNS=3 и Retry Budget и не расширяет набор тулов.",
        "verification_ids": [
          "VER-001",
          "VER-002"
        ]
      }
    ]
  },
  "evolution": {
    "compatibility": "Внешний HTTP/OpenAI контракт совместим; дельты CD-002 (SSE-комментарий keepalive, finish_reason=tool_calls при восстановлении) и CD-003 (ограниченное ожидание слота, 503 circuit open) — backward-compatible по схеме; парсер принимает оба тега; новые константы — внутренние, env-переопределяемые.",
    "migration": "Миграций данных нет: мост stateless, opencode.db мостом не модифицируется; persisted state не меняется.",
    "rollout": "Правка bridges/opencode-zen-bridge/server.py (+ tests/test_step_interruption.py) -> VER-001..003, VER-005, VER-006 -> копирование в ~/.dsh/bridges/opencode-zen-bridge/server.py -> VER-004 (diff -u exit 0) -> перезапуск LaunchAgent com.user.dsh-opencode-zen-bridge -> живой многошаговый ход DSH на glm-5.3-flash-free и пачка параллельных сабагентов (тяжёлый путь).",
    "rollback": "Мгновенно без деплоя: OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0 в EnvironmentVariables plist + перезапуск LaunchAgent (отключает только детектор/дозапрос, unmapped-ретрай сохраняется). Полный: git revert коммита фикса + повторная синхронизация ~/.dsh и перезапуск LaunchAgent; VER-004 подтверждает идентичность.",
    "feature_flag": "Канонический GigaRC-фичефлаг неприменим: локальный мост на машине владельца без gc_pytools/dynamic_config и без доступа к GigaRC; функциональный эквивалент kill-switch — env OPENCODE_ZEN_BRIDGE_STEP_RECOVERY (default \"1\", т.к. фикс — восстановление ожидаемого поведения, а не новая фича)."
  },
  "approval": {
    "status": "APPROVED",
    "decision_ids": [],
    "approved_by": "orchestrator (analyst-teamlead, routing_approval=auto, approved_by_user=true in route-manifest.json); one-way решений нет",
    "evidence_ref": ".ai-team/runs/analyst-teamlead-zen-step-20261024/route-manifest.json"
  },
  "independent_review": {
    "required": false,
    "status": "PASS",
    "reviewer": "deterministic fail-closed validate_architecture_packet.py (draft+approved); S2 — независимое review не обязательно; Архитектурный Совет (arch-panel cycle-2) — отдельный downstream-гейт",
    "evidence_ref": ".ai-team/runs/analyst-teamlead-zen-step-20261024/receipts/architect.json"
  },
  "open_questions": [
    {
      "id": "Q-001",
      "ledger_ref": "OPEN-01",
      "class": "МОЖНО ПРОДОЛЖИТЬ",
      "question": "Калибровка SWALLOWED_TOKENS_MIN=35 для других моделей Zen (kimi-k2.5, qwen3.6-plus): порог подтверждён только на glm-5.3-flash-free.",
      "blocking": false
    },
    {
      "id": "Q-002",
      "class": "ЗАКРЫТ",
      "question": "Отдельный env-флаг kill-switch детектора дозапроса — закрыт решением AD-002: OPENCODE_ZEN_BRIDGE_STEP_RECOVERY.",
      "blocking": false
    }
  ],
  "protected_paths": [],
  "materialization": [],
  "deferred": [
    "Калибровка SWALLOWED_TOKENS_MIN на kimi-k2.5 / qwen3.6-plus (Q-001)",
    "Логирование причины срабатывания детектора в bridge.log (signal=1..5) для наблюдаемости",
    "Замер фактического RSS opencode run под 6 параллельными запусками (ASM-003)"
  ],
  "high_load_envelope": {
    "schema": "HL-ENV/v1",
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0 (REQUIRED_HL_ENV_FIELDS)",
    "field_count": 46,
    "units": "SI; память — в байтах (MiB = 1048576 B); время — с; CPU — cores; темпы — 1/с",
    "required_hl_env_fields": {
      "P_steady": 1,
      "P_hpa_max": 1,
      "maxSurge_pct": 0.0,
      "maxSurge_abs": 0,
      "maxUnavailable_pct": 0.0,
      "maxUnavailable_abs": 0,
      "P_terminating_overlap": 0,
      "P_live": 1,
      "P_avail_min": 1,
      "W": 1,
      "N_proc": 1,
      "N_proc_steady": 1,
      "N_proc_avail_min": 1,
      "CPU_limit_per_pod": 2.0,
      "κ_skew": 1.0,
      "u_bg_worker": 0.02,
      "U_pod_sidecars": 0.25,
      "Mem_limit_per_pod": 2147483648,
      "Mem_rss_worker_max": 67108864,
      "Mem_shared_max": 1207959552,
      "RPS_peak": 0.2,
      "A_max": 3,
      "SLA_p99_s": 180.0,
      "N_entities_max": 64,
      "Limit_dep_share[d]": {
        "opencode_cli": 10
      },
      "Limit_dep_rps[d]": {
        "opencode_cli": 2.0
      },
      "W_fetchers[d]": {
        "opencode_cli": 1
      },
      "J_init_s[d]": {
        "opencode_cli": 12.0
      },
      "J_pod_s[d]": {
        "opencode_cli": 12.0
      },
      "T_poll_s[d]": {
        "opencode_cli": 15.0
      },
      "K_calls[d]": {
        "opencode_cli": 1
      },
      "T_base_s[d]": {
        "opencode_cli": 0.5
      },
      "T_cap_s[d]": {
        "opencode_cli": 2.0
      },
      "Max_stale_age_s[c]": {
        "stateless_bridge": 0.0
      },
      "Min_healthy_ratio": 1.0,
      "B_retry_max": 6,
      "min_reserve_retry_rps": 0.05,
      "FD_worker": 128,
      "ulimit_n": 4096,
      "λ_new_conn_per_pod(s)": {
        "node_ephemeral": 0.6,
        "shared_snat": 0.6
      },
      "C_active_in_scope(s)": {
        "node_ephemeral": 12,
        "shared_snat": 12
      },
      "N_pods_in_scope(s)": {
        "node_ephemeral": 1,
        "shared_snat": 1
      },
      "Port_range_size(s)": {
        "node_ephemeral": 16383,
        "shared_snat": 16383
      },
      "T_hold_s(s)": {
        "node_ephemeral": 60.0,
        "shared_snat": 60.0
      },
      "SNAT_ips_count(s)": {
        "node_ephemeral": 1,
        "shared_snat": 1
      },
      "HOTPATH_MODULES": [
        "bridges/opencode-zen-bridge/server.py"
      ]
    },
    "field_sources": {
      "P_steady": "~/Library/LaunchAgents/com.user.dsh-opencode-zen-bridge.plist (EVD-014): один процесс, KeepAlive, без k8s/HPA",
      "P_hpa_max": "~/Library/LaunchAgents/com.user.dsh-opencode-zen-bridge.plist (EVD-014): один процесс, KeepAlive, без k8s/HPA",
      "maxSurge_pct": "LaunchAgent: нет RollingUpdate, рестарт = стоп старого -> старт нового (один порт 9883)",
      "maxSurge_abs": "derived: ceil(P_hpa_max × maxSurge_pct) = ceil(1 × 0.0) = 0",
      "maxUnavailable_pct": "LaunchAgent: нет RollingUpdate",
      "maxUnavailable_abs": "derived: floor(P_steady × maxUnavailable_pct) = floor(1 × 0.0) = 0",
      "P_terminating_overlap": "bind 127.0.0.1:9883 исключает параллельную жизнь двух поколений (EVD-014)",
      "P_live": "derived: P_hpa_max + maxSurge_abs + P_terminating_overlap = 1 + 0 + 0 = 1",
      "P_avail_min": "derived: max(1, P_steady - maxUnavailable_abs) = max(1, 1 - 0) = 1",
      "W": "server.py ThreadingHTTPServer, один Python-процесс (EVD-006, EVD-014)",
      "N_proc": "derived: P_live × W = 1 × 1 = 1",
      "N_proc_steady": "derived: P_steady × W = 1",
      "N_proc_avail_min": "derived: P_avail_min × W = 1",
      "CPU_limit_per_pod": "handoff-architect.md §3 (cpu_limit_m=2000), бюджет демона на рабочей станции",
      "κ_skew": "W=1 — неравномерности между воркерами нет",
      "u_bg_worker": "handoff §3: GC/логирование/таймеры, оценка",
      "U_pod_sidecars": "handoff §3: дочерние opencode run в сетевом ожидании, оценка (ASM-003)",
      "Mem_limit_per_pod": "rework-brief F1: 2048 MiB бюджет LaunchAgent (без cgroup)",
      "Mem_rss_worker_max": "rework-brief F1: 64 MiB RSS Python-моста с _StdoutFeed maxsize=4096 (ASM-003)",
      "Mem_shared_max": "rework-brief F1: 6 × 192 MiB RSS opencode run = 1152 MiB (ASM-003)",
      "RPS_peak": "handoff §3 operational_profile.rps_peak; bridge.log (EVD-012/013)",
      "A_max": "AD-003: MAX_TOTAL_SPAWNS = 3",
      "SLA_p99_s": "handoff §3 latency_p99_ms=180000",
      "N_entities_max": "максимум tools в запросе DSH (allowed_map/canonical_map), handoff §4.3",
      "Limit_dep_share[d]": "handoff §4.1 C-MULT-I1: 10 слотов opencode CLI на хост (YAML §3 'Limit_dep_share_d: 6' — опечатка, принято 10 по расчёту C-MULT-I1)",
      "Limit_dep_rps[d]": "handoff §3 rate_limit_rps=2.0",
      "W_fetchers[d]": "один процесс моста",
      "J_init_s[d]": "server.py:720 STARTUP_GATE_S=12 (EVD-015)",
      "J_pod_s[d]": "server.py:720 STARTUP_GATE_S=12",
      "T_poll_s[d]": "KEEPALIVE_INTERVAL_S=15.0 (клиентский keepalive; поллинга зависимости нет)",
      "K_calls[d]": "1 opencode run на запуск",
      "T_base_s[d]": "AD-003 RETRY_BACKOFF_BASE_S=0.5",
      "T_cap_s[d]": "AD-003 RETRY_BACKOFF_CAP_S=2.0",
      "Max_stale_age_s[c]": "мост stateless: кэшей нет",
      "Min_healthy_ratio": "одна зависимость без пула нод: N_floor=1",
      "B_retry_max": "AD-004 _RetryBudget capacity",
      "min_reserve_retry_rps": "AD-004 _RetryBudget refill",
      "FD_worker": "оценка: 1 listen + 18 клиентских сокетов + 6×3 pipe + log + запас (см. C-MULT-I5)",
      "ulimit_n": "macOS launchd soft limit для агента (оценка; verifier: `launchctl limit maxfiles`)",
      "λ_new_conn_per_pod(s)": "handoff §3: локальные подключения DSH + исходящие opencode run",
      "C_active_in_scope(s)": "6 клиентских + 6 исходящих соединений",
      "N_pods_in_scope(s)": "один хост",
      "Port_range_size(s)": "macOS net.inet.ip.portrange 49152..65535 = 16384 (принято 16383)",
      "T_hold_s(s)": "TIME_WAIT 2×MSL, консервативно 60 с",
      "SNAT_ips_count(s)": "одна машина, без SNAT-пула",
      "HOTPATH_MODULES": "единственный модуль горячего пути моста"
    },
    "memory_closure_check": {
      "formula": "W * Mem_rss_worker_max + Mem_shared_max <= 0.80 * Mem_limit_per_pod",
      "substitution": "W * Mem_rss_worker_max + Mem_shared_max = 1 * 67108864 + 1207959552 = 1275068416 B (1216 MiB) <= 0.80 * Mem_limit_per_pod = 1717986918.4 B (1638.4 MiB) -> PASS",
      "lhs_bytes": 1275068416,
      "rhs_bytes": 1717986918.4,
      "result": "PASS"
    },
    "operational_profile": {
      "threads_per_worker": 12,
      "threads_breakdown": "6 HTTP handler threads (MAX_CONCURRENT=6 активных) + 6 daemon _StdoutFeed (1 на живой proc); ожидающие слота потоки (<= SLOT_MAX_WAITERS=12) блокированы и не исполняют код",
      "stdout_queue_max": 4096,
      "latency_p50_ms": 14000,
      "latency_p95_ms": 90000,
      "latency_p99_ms": 180000,
      "max_total_spawns": 3,
      "max_retries": 2,
      "rps_sustained": 0.05,
      "rps_peak": 0.2,
      "concurrency_max": 6,
      "payload_p50_kb": 48,
      "payload_p99_kb": 480,
      "cpu_limit_m": 2000,
      "mem_limit_mb": 2048,
      "workers_processes": 1,
      "connect_timeout_ms": 5000,
      "read_timeout_ms": 300000,
      "total_deadline_ms": 1800000,
      "backoff_base_ms": 500,
      "backoff_max_ms": 2000,
      "jitter_mode": "full_jitter",
      "slot_wait_s": 15.0,
      "slot_max_waiters": 12,
      "startup_wait_s": 5.0,
      "startup_gate_s": 12.0,
      "startup_gate_typical_release_s": "1.5-2.0",
      "spawn_rate_per_s": 1.0,
      "retry_budget_capacity": 6,
      "retry_budget_refill_per_req": 0.2,
      "circuit_breaker_threshold": 5,
      "circuit_breaker_reset_s": 10.0,
      "half_open_probes": 1,
      "keepalive_interval_sec": 15,
      "swallowed_tokens_min": 35,
      "graceful_shutdown_sec": 5,
      "max_response_size_mb": 16
    }
  },
  "resilience_gates": {
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0–3.4, §7.2, §7.3",
    "HL_ENV_v1": {
      "HL-ENV-01": {
        "status": "PASS",
        "check": "len(required_hl_env_fields) == 46 и REQUIRED_HL_ENV_FIELDS ⊆ keys; источник у каждого поля (field_sources); memory closure 1275068416 B <= 1717986918.4 B; каждый N/A ниже — с git_diff_files + transitive_call_graph",
        "oracle": "VER-006: расчётный тест по константам модуля"
      }
    },
    "C_MULT": {
      "C-MULT-I1": {
        "status": "PASS",
        "substitution": "roles: bridge_http_workers (N_proc=1, pool=_slots=MAX_CONCURRENT=6, G_reload=1 — _slots создаётся один раз при импорте, reload каталога семафор не пересоздаёт; dedicated=0); crawler/pod_fetcher/control_plane/migrations_cron = 0 процессов. C_dep(opencode_cli) = 1 × (1 × 6 + 0) = 6 <= 0.60 × 10 = 6.0 -> PASS. Повторы идут в том же слоте после _stop_proc (синхронный wait<=5 с) — одновременных детей <= 6. Расчёт при MAX_CONCURRENT=6 из plist (EVD-014); дефолт кода 2 (EVD-017) даёт 2 <= 6.0."
      },
      "C-MULT-I2": {
        "status": "PASS",
        "substitution": "Пул = _slots(M=6) с timeout T_wait_s=SLOT_WAIT_S=15.0 и max_waiters=SLOT_MAX_WAITERS=12 <= 2M=12; 13-й ожидающий -> немедленный 503 overloaded (аналог PoolWaitersExhaustedError); очередь stdout queue.Queue(maxsize=4096) (AD-003, AD-004)."
      },
      "C-MULT-I3": {
        "status": "PASS",
        "substitution": "_slots, _STARTUP_LOCK, _SpawnRateLimiter, _RetryBudget, _UpstreamBreaker — синглтоны модуля (один процесс, fork() воркеров нет); новые объекты в обработчике не создаются, кроме per-request _StdoutFeed/_StartupGate (не сетевые клиенты). subprocess.Popen делает exec с close_fds=True (Python 3 default) — сокеты моста не наследуются."
      },
      "C-MULT-I4": {
        "status": "PASS",
        "substitution": "asyncio нет; прерывания — исключения/BrokenPipe в потоке обработчика. _slots.release(), декремент waiters, gate.release() и _stop_proc(proc) — в try/finally в Handler._stream_sse, Handler._serve_json, Run._execute_once; оракул: после 50 прерванных запросов in_use==0, waiters==0 (VER-006)."
      },
      "C-MULT-I5": {
        "status": "PASS",
        "substitution": "FD_worker = 128 <= 0.70 × 4096 = 2867.2 (оценка пика: 1 listen + 18 клиентских (6 активных + 12 ждущих) + 6 × 3 pipe + 1 log + ~20 прочих ≈ 58 <= 128). Порты для s ∈ {node_ephemeral, shared_snat}: 0.6 × 1 × 60.0 + 12 = 48 <= 0.50 × (1 × 16383) = 8191.5 -> PASS."
      }
    },
    "S_HERD": {
      "S-HERD-I1": {
        "status": "PASS",
        "substitution": "Формульная граница: λ_fetch = P_live × W_fetchers / max(J_init_s, J_pod_s) = 1 × 1 / 12.0 = 0.0833 1/с; B = K_calls × (λ + 4√λ + 4) = 1 × (0.0833 + 1.1547 + 4) = 5.24 > 0.50 × 2.0 = 1.0 — формула НЕ проходит (константа +4 > 1.0), поэтому применена разрешённая каноном альтернатива: RPS Token-Bucket Rate-Limiter _SpawnRateLimiter (capacity=1, 1.0 токен/с) перед каждым Popen: B_dep,1s <= 1.0 <= 0.50 × Limit_dep_rps = 1.0 -> PASS. Поллинг зависимости отсутствует: R_poll(opencode_cli) = 0 <= 0.20 × 2.0 = 0.4 -> PASS (keepalive 15 с — к клиенту, не к зависимости). pod_fetcher/os.replace — N/A (роли нет).",
        "oracle": "VER-006: на FakeClock 10 конкурентных запусков дают <= 1 Popen в любом окне 1 с"
      },
      "S-HERD-I2": {
        "status": "PASS",
        "substitution": "Full Jitter: _retry_backoff_s(retry_num, rng_fn) = rng_fn(0, min(2.0, 0.5 × 2^retry_num)); retry 1: cap_1 = min(2.0, 1.0) = 1.0, u∈[0,0.5,1] -> [0.0, 0.5, 1.0]; retry 2: cap_2 = min(2.0, 2.0) = 2.0 -> [0.0, 1.0, 2.0]; jitter cooldown breaker 10.0 × U(0.8,1.2) ∈ [8.0, 12.0]. Пересев CSPRNG после fork() — N/A: fork() Python-воркеров нет (Popen сразу exec в opencode); поллеров с T_poll×U(0.8,1.2) нет.",
        "na_proof_for_subclauses": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "S-HERD-I3": {
        "status": "N/A",
        "reason": "Нет поллеров Snapshot/DynamicConfig и условных fetch с ETag/If-None-Match: мост — stateless HTTP->CLI.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "S-HERD-I4": {
        "status": "N/A",
        "reason": "Нет TTL-кэшей с сетевым дозапросом и singleflight; negative caching отсутствует.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "S-HERD-I5": {
        "status": "N/A",
        "reason": "Нет Snapshot/Control Plane/секретов в кэше; Max_stale_age_s[stateless_bridge] = 0; /health отвечает без зависимости от кэша.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      }
    },
    "H_CPU": {
      "H-CPU-I1": {
        "status": "N/A",
        "reason": "Нет Snapshot-индексов маршрутизации; маппинг тулов — dict O(1) (canonical_map/allowed_map) на N_entities_max=64 tools запроса.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "H-CPU-I2": {
        "status": "PASS",
        "substitution": "_TOOL_BLOCK_RE, _INTERRUPTED_RE, _ACTION_INTENT_RE, _REASONING_TOOL_PLAN_RE, _FINAL_CONCLUSION_RE и маркеры _is_transient_stream_error компилируются при импорте модуля; в цикле событий и детекторе нет re.compile, copy.deepcopy, pydantic, json.loads конфигов (json.loads строки события opencode — разбор payload, не конфига); оракул spy re._compile/copy.deepcopy call_count==0 (VER-006)."
      },
      "H-CPU-I3": {
        "status": "PASS",
        "substitution": "Zero-Cost Disabled Path: `if not STEP_RECOVERY_ENABLED: return False` — первая инструкция _is_incomplete_tool_step до любых regex/аллокаций. Очередь _StdoutFeed: put_nowait в maxsize=4096; при Full — не drop (это данные ответа, drop = SILENT_DATA_LOSS), а overflow-флаг + _stop_proc + лог: вызов не блокирует поток-читатель. Телеметрия = _log под _LOG_LOCK с проглатыванием OSError (fail-open)."
      },
      "H-CPU-I4": {
        "status": "N/A",
        "reason": "В server.py нет asyncio event loop и горячего reload Snapshot; reload каталога моделей — вне изменённого пути.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "H-CPU-I5": {
        "status": "PASS",
        "substitution": "t_per_req_s = 0.02, t_per_attempt_s = 0.05 CPU-с; t_req_total = 0.02 + 3 × 0.05 = 0.17 с. Util_worker = κ × RPS_peak × t_req_total / (P_avail_min × W) + u_bg = 1.0 × 0.2 × 0.17 / (1 × 1) + 0.02 = 0.054 <= 0.70 -> PASS; W × Util + U_pod_sidecars = 0.054 + 0.25 = 0.304 <= 0.80 × 2.0 = 1.60 -> PASS; ΔCores_feature = RPS_peak × Δt = 0.2 × (2 × 0.05 + 0.001 детектор) = 0.0202 <= 0.05 × (1 × 2.0) = 0.10 -> PASS."
      }
    },
    "R_BULK": {
      "R-BULK-I1": {
        "status": "PASS",
        "substitution": "Σ_{a=1..3}(T_crit_aux(a) + T_wait(a) + T_backoff(a)): a=1: T_wait слота 15.0 + gate-wait 5.0 + token-wait 5.0 + backoff 0 = 25.0; a=2: 0 + 5.0 + 5.0 + cap_1 1.0 = 11.0; a=3: 0 + 5.0 + 5.0 + cap_2 2.0 = 12.0; итого 48.0 с <= 0.30 × 180.0 = 54.0 с -> PASS. Было бы: T_wait = TIMEOUT_S = 1800 с (EVD-017) -> FAIL, поэтому AD-004 вводит SLOT_WAIT_S/STARTUP_WAIT_S. T_call = min(TIMEOUT_S, deadline - monotonic()); при deadline - monotonic() <= 0 следующая попытка/сон не стартуют.",
        "oracle": "VER-006 (FakeClock, call_count==0 после deadline)"
      },
      "R-BULK-I2": {
        "status": "PASS",
        "substitution": "MAX_TOTAL_SPAWNS=3 на запрос + process Retry Budget (capacity 6, +0.20/первичный запрос, +0.05/с): для N_req=100 падающих запросов за T_w=500 с: N_retries <= floor(0.20×100 + 0.05×500) + 6 = floor(45) + 6 = 51 (без бюджета было бы до 200). Bulkhead: _slots(max_concurrent=6, max_waiters=12) с мгновенным 503 при переполнении."
      },
      "R-BULK-I3": {
        "status": "PASS",
        "substitution": "Fail-Closed: детерминированные 400/401/403/404/422 -> ошибка клиенту без повтора; Fail-Open: _StartupGate (таймаут 5 с -> запуск без замка), bridge.log (OSError проглатывается). Circuit Breaker opencode_cli: OPEN после 5 подряд транзиентных отказов, cooldown 10.0 × U(0.8,1.2) ∈ [8,12] с, в OPEN 503 без spawn за 0 с, HALF_OPEN — max_half_open_probes=1."
      },
      "R-BULK-I4": {
        "status": "N/A",
        "reason": "Нет пула прокси-нод/тенантов и V_eligible: единственная зависимость — бинарник OPENCODE_BIN; карантина нод нет.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "R-BULK-I5": {
        "status": "N/A",
        "reason": "Нет прокси-нод и разделения origin/node: ошибки апстрима opencode.ai/zen учитываются единым _UpstreamBreaker.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      }
    },
    "T_LIFE_v1": {
      "status": "PASS",
      "substitution": "Каждый proc (start_new_session) закрывается _stop_proc (killpg SIGTERM -> wait 5 с -> SIGKILL) в finally перед следующим запуском и при выходе из запроса; _StdoutFeed (daemon) завершается по EOF после остановки proc; таймер _StartupGate — daemon и идемпотентный release; синглтоны лимитеров живут весь процесс, внешних клиентов нет. LaunchAgent stop -> SIGTERM процессу моста, дети в своих сессиях останавливаются finally-обработчиками активных запросов (graceful_shutdown_sec=5)."
    },
    "O_EXIT_v1": {
      "status": "PASS",
      "substitution": "На каждом выходе Handler.do_POST (401, 400 invalid json, 404, 503 bridge busy/circuit open, 502 opencode error, успех stream/json, overflow, deadline) — одна структурная строка bridge.log: mode, model, rc, tools, out_chars, retries/total_spawns, exit_reason, duration."
    },
    "M_SEM_v1": {
      "status": "N/A",
      "reason": "Нет пулов нод разных назначений (crawler/llm) и eligibility-фильтра: один локальный CLI на все запросы.",
      "na_proof": {
        "git_diff_files": [
          "bridges/opencode-zen-bridge/server.py",
          "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
        ],
        "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
        "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
      }
    },
    "dependency_failure_matrix": [
      {
        "dependency_operation": "opencode run (spawn+stream -> opencode.db + opencode.ai/zen)",
        "path": "hot",
        "timeout_budget": "T_call = min(TIMEOUT_S=1800, deadline - monotonic()); poll get(timeout=0.25 JSON / 1.0 SSE)",
        "bulkhead": "_slots max_concurrent=6 / max_waiters=12, SLOT_WAIT_S=15",
        "circuit_breaker": "OPEN после 5 подряд транзиентных отказов / cooldown 10×U(0.8,1.2) с / HALF_OPEN=1",
        "failure_mode_fallback": "транзиентная -> _stop_proc + повтор (A_max=3, Retry Budget, Full Jitter); детерминированная 4xx -> Fail-Closed ошибка клиенту; исчерпано -> накопленный текст finish_reason=stop или 502; OPEN -> 503 overloaded без spawn"
      },
      {
        "dependency_operation": "_StartupGate (сериализация старта sqlite opencode.db)",
        "path": "hot (aux)",
        "timeout_budget": "ожидание <= STARTUP_WAIT_S=5; удержание <= STARTUP_GATE_S=12 (типично 1.5–2.0)",
        "bulkhead": "1 держатель",
        "circuit_breaker": "нет (aux)",
        "failure_mode_fallback": "Fail-Open: запуск без замка + лог; 'database is locked' -> retryable failure в пределах A_max"
      },
      {
        "dependency_operation": "_SpawnRateLimiter (token-bucket запусков)",
        "path": "hot (aux)",
        "timeout_budget": "ожидание токена <= 5.0 с",
        "bulkhead": "capacity 1, 1.0 токен/с",
        "circuit_breaker": "нет",
        "failure_mode_fallback": "не обходится; при deadline - monotonic() <= 0 запуск отменяется"
      },
      {
        "dependency_operation": "_StdoutFeed (очередь stdout)",
        "path": "hot",
        "timeout_budget": "get(timeout=0.25/1.0)",
        "bulkhead": "queue maxsize=4096",
        "circuit_breaker": "нет",
        "failure_mode_fallback": "queue.Full -> overflow + _stop_proc, попытка неуспешна (засчитывается breaker), без silent drop"
      },
      {
        "dependency_operation": "Сокет клиента DSH (SSE/JSON)",
        "path": "hot",
        "timeout_budget": "Handler.timeout=300 с; keepalive каждые 15 с",
        "bulkhead": "по _slots",
        "circuit_breaker": "нет",
        "failure_mode_fallback": "BrokenPipe/ConnectionReset -> _stop_proc, без повтора, лог O-EXIT"
      },
      {
        "dependency_operation": "bridge.log (телеметрия)",
        "path": "hot -> bg",
        "timeout_budget": "синхронный append под _LOG_LOCK",
        "bulkhead": "1 писатель",
        "circuit_breaker": "нет",
        "failure_mode_fallback": "Fail-Open: OSError проглатывается, 0 влияния на запрос"
      }
    ],
    "non_waivable_stop_codes": [
      "HL-ENV-01",
      "C-MULT-I1",
      "C-MULT-I2",
      "C-MULT-I3",
      "C-MULT-I4",
      "C-MULT-I5",
      "S-HERD-I1",
      "S-HERD-I2",
      "S-HERD-I3",
      "S-HERD-I4",
      "S-HERD-I5",
      "H-CPU-I1",
      "H-CPU-I2",
      "H-CPU-I3",
      "H-CPU-I4",
      "H-CPU-I5",
      "R-BULK-I1",
      "R-BULK-I2",
      "R-BULK-I3",
      "R-BULK-I4",
      "R-BULK-I5",
      "T-LIFE/v1",
      "O-EXIT/v1",
      "M-SEM/v1"
    ],
    "summary": {
      "PASS": 16,
      "N/A": 8,
      "FAIL": 0
    }
  },
  "legacy_arch_antipattern_checks": {
    "ARCH_CYCLE_DETECTED": {
      "status": "PASS",
      "rationale": "BND-003 -> BND-001/BND-002, обратных зависимостей нет."
    },
    "LAYER_VIOLATION": {
      "status": "PASS",
      "rationale": "Детектор и парсер — чистые функции без I/O (BND-001/BND-002 forbidden_dependencies)."
    },
    "GOD_OBJECT": {
      "status": "PASS",
      "rationale": "Новая логика выносится в отдельные функции/класс _StdoutFeed, а не в Handler; baseline-размер server.py — унаследованный долг."
    },
    "TIGHT_COUPLING": {
      "status": "PASS",
      "rationale": "Детектор получает примитивы (строки, int, список имён), не объекты proc/Handler."
    },
    "LEAKY_ABSTRACTION": {
      "status": "PASS",
      "rationale": "Клиент видит только OpenAI tool_calls/finish_reason; внутренние теги и ретраи скрыты."
    },
    "MISSING_TIMEOUT": {
      "status": "PASS",
      "rationale": "Единый deadline TIMEOUT_S, get(timeout=0.25/1.0), _stop_proc wait(5), Handler.timeout=300."
    },
    "UNBOUNDED_RETRY": {
      "status": "PASS",
      "rationale": "MAX_TOTAL_SPAWNS=3 на запрос + Retry Budget (B_retry_max=6)."
    },
    "RETRY_STORM": {
      "status": "PASS",
      "rationale": "A_max=3, Retry Budget, Circuit Breaker HALF_OPEN=1, ретраи внутри одного слота."
    },
    "THUNDERING_HERD": {
      "status": "PASS",
      "rationale": "_StartupGate + _SpawnRateLimiter 1.0/с + Full Jitter backoff."
    },
    "UNBOUNDED_QUEUE": {
      "status": "PASS",
      "rationale": "_StdoutFeed queue.Queue(maxsize=4096), queue.Full -> _stop_proc; waiters слота <= 12."
    },
    "MISSING_BACKPRESSURE": {
      "status": "PASS",
      "rationale": "Semaphore(6) + 503 по таймауту слота."
    },
    "BLOCKING_IO_IN_ASYNC": {
      "status": "N/A",
      "rationale": "asyncio не используется (ThreadingHTTPServer); блокирующее чтение stdout вынесено в выделенный поток."
    },
    "CPU_SPIN_WAIT": {
      "status": "PASS",
      "rationale": "Ожидание через Queue.get(timeout), без циклов с sleep(0)/poll."
    },
    "RESOURCE_LEAK": {
      "status": "PASS",
      "rationale": "_stop_proc в finally каждой попытки; daemon-поток завершается по EOF после остановки процесса."
    },
    "ZOMBIE_SUBPROCESS": {
      "status": "PASS",
      "rationale": "start_new_session + killpg SIGTERM -> wait -> SIGKILL на всех путях выхода, включая mid-stream error."
    },
    "RACE_CONDITION": {
      "status": "PASS",
      "rationale": "Состояние попытки локально для потока запроса; общий ресурс — только Queue (потокобезопасна) и _slots/_STARTUP_LOCK."
    },
    "NON_IDEMPOTENT_RETRY": {
      "status": "PASS",
      "rationale": "Мост не исполняет инструменты (permission *=ask); ретрай повторяет только генерацию модели; уже отправленный SSE-префикс не дублируется (dedup_prefix)."
    },
    "BREAKING_CONTRACT": {
      "status": "PASS",
      "rationale": "Внешний HTTP/OpenAI контракт неизменен (REQ-006); CD-001 — внутренний, backward-compatible."
    },
    "SILENT_DATA_LOSS": {
      "status": "PASS",
      "rationale": "Проглоченный tool-шаг детектируется и дозапрашивается; несовпадение dedup_prefix не теряет текст; overflow stdout — явный отказ, не drop."
    },
    "UNHANDLED_UPSTREAM_ERROR": {
      "status": "PASS",
      "rationale": "Mid-stream etype=error обрабатывается: _stop_proc + детектор + дозапрос (REQ-002)."
    },
    "HARDCODED_SECRET": {
      "status": "PASS",
      "rationale": "Секретов не добавляется; изменения — теги, регэкспы, числовые константы."
    }
  },
  "evidence_coverage": {
    "EVD-001..EVD-016": "все связаны: AD-001 {005,008,016}; AD-002 {001,002,003,004,007,009,010,011,012}; AD-003 {006,013,014,015,017}; AD-004 {006,012,014,015,017}; RISK-001 {007,010,011}; RISK-002 {013,014,015}; RISK-003 {008,009}; RISK-004 {003,006,012,016}; RISK-005 {014,017}"
  },
  "panel_findings_closure": {
    "Seat1-F1 BLOCKER": "high_load_envelope: schema HL-ENV/v1, field_count 46, 46 канонических ключей + field_sources, memory_closure_check PASS",
    "Seat1-F2 BLOCKER": "resilience_gates: 21 код + T-LIFE/O-EXIT/M-SEM, dependency_failure_matrix, двойное N/A-доказательство, non_waivable_stop_codes (24), _StdoutFeed maxsize=4096 + _stop_proc на queue.Full (AD-003, REQ-005)",
    "Seat1-F3 MAJOR": "MAX_TOTAL_SPAWNS=3 (AD-003, REQ-004), _retry_backoff_s Full Jitter, _StartupGate ранний release vs SLA_p99_s=180/p95=90 с; дополнительно AD-004 (ограниченные ожидания, token-bucket, Retry Budget, Breaker) — найдено при честной подстановке R-BULK-I1/S-HERD-I1",
    "Seat1-F4 MAJOR": "STEP_RECOVERY_ENABLED / OPENCODE_ZEN_BRIDGE_STEP_RECOVERY; признак 5 только с _ACTION_INTENT_RE; RISK-001 impact=medium",
    "Seat1-F5 MAJOR": "_is_transient_stream_error (REQ-002, AD-002); fallback dedup_prefix без потери (REQ-004, AD-003)",
    "Seat1-F6 MAJOR": "CD-002 (keepalive + finish_reason recovery); CD-003 (bulkhead/breaker 503)",
    "Seat1-F7 MINOR": "threads_per_worker=12 с разбивкой; все EVD-001..016 связаны",
    "Seat3-F1": "EVD-001..016 связаны с AD/RISK (evidence_coverage)",
    "Seat3-F2": "VER-004 diff -u репо vs ~/.dsh; VER-005 (emulate_tools=False, dedup mismatch, 'Ответ: 42:', 401 vs ECONNRESET)"
  },
  "role_plan": {
    "path": "plans/architect-02.json",
    "sha256": "27ff2ee9e1a7db6d3d48533dffc9280d2bf1197f6d605faced7ab0600f4a6bcb"
  }
}
<<<END ARTIFACT>>>

<<<ARTIFACT path=".ai-team/runs/analyst-teamlead-zen-step-20261024/plans/coder-01.json" sha256="7c9e39bfbde86036c3b4f2b34e34fb0119f2b043705153496193b399191d8fd4" bytes="994">>>
{
  "schema_version": "1.0",
  "run_id": "analyst-teamlead-zen-step-20261024",
  "role": "coder",
  "model_id": "claude-sonnet-5-5",
  "provider": "anthropic",
  "transport": "claude-cli",
  "effort": "high",
  "selected_skill_file": "/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/bugfix.md",
  "selected_agent_files": [
    "/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/code.md",
    "/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/testing.md"
  ],
  "architecture_packet_sha256": "1053a4ca2e97d0eba0f350c3a71e13d8810c1a716e3b1e66a6c7ff0097e4f565",
  "allowed_write_scope": [
    "bridges/opencode-zen-bridge/server.py",
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
  ],
  "rationale": "Реализация архитектурного пакета v5 (AD-001..AD-004, REQ-001..REQ-006, CD-001..CD-003, VER-001..VER-006) в opencode-zen-bridge.",
  "created_at": "2026-10-24T19:52:00+03:00"
}
<<<END ARTIFACT>>>

<<<ARTIFACT path="analysis/zen-step-interruption/handoff-architect.md" sha256="b4ca344f74aaf39c79b0d0416d9066b4c13b65f7f093b0628b71ce8a48067013" bytes="25577">>>
# Handoff to Architect: Устранение преждевременного обрывания многошаговых агентных цепочек в `opencode-zen-bridge` (v5)

## 1. Контекст и доказанная корневая причина (`[F-01]..[F-16]`)

В локальном мосте `bridges/opencode-zen-bridge/server.py` (обслуживающем `http://127.0.0.1:9883/v1` для DSH Desktop `[F-14]`, `[F-16]`) многошаговые агентные цепочки (`glm-5.3-flash-free` и др. модели с `emulate_tools=True`) обрываются посреди выполнения задачи с `finish_reason="stop"` и `tools=0` (`[F-10]`, `[F-11]`, `[F-12]`). Расследование по коду (`Zone A`), базе `opencode.db` (`Zone B`), журналу сессий DSH (`Zone C`) и логам моста (`Zone D`) выявило четыре взаимосвязанных механизма обрыва:

1. **Проглатывание тегов `<tool_call>` апстримом `opencode.ai/zen` (`[F-05]`, `[F-07]`, `[F-08]`, `[F-09]`):**
   Апстрим-провайдер `opencode.ai/zen` для семейства GLM (`glm-5.3-flash-free`) фильтрует/вырезает блоки `<tool_call>...</tool_call>` как служебные спец-токены (`[F-08]`: на промпте с `<tool_call>` возвращается `content=[]` при `tokens.output=75`, тогда как с нейтральным тегом `<tool_invoke>` возвращается валидный вызов `len(text)=283`). На Ходах 10 и 12 сессии `00e33abb-224c-4e4b-bd3d-6490f2bc9b87` модель сгенерировала короткую преамбулу намерения (`138` и `168` символов) и вызов инструмента (`non_reasoning_output = 350` и `133` токена), но блок `<tool_call>` был проглочен апстримом, а шаг закрылся с `finish="stop"` (`[F-07]`, `[F-09]`).
2. **Игнорирование `etype == "error"` (`ECONNRESET`) посреди стрима и склейка с синтетическим шагом `opencode run` (`[F-04]`, `[F-09]`, `[F-12]`):**
   На Ходе 11 (`14:11:56–14:12:27 MSK`) во время генерации произошёл обрыв соединения `ECONNRESET` (`[F-12]`). Исходный `server.py` при получении события `etype == "error"` не останавливал `proc` (`[F-04]`), из-за чего `opencode run` автоматически создал внутреннее синтетическое сообщение `"The previous response was interrupted..."`, на которое модель ответила текстом `"I was interrupted right before making tool calls..."` с `finish="stop"` без вызова тулов (`[F-09]`), а мост вернул этот склеенный текст клиенту как успешно завершённый ответ (`[F-03]`).
3. **Отсутствие детекции и ретрая оборванных инструментальных шагов в `Handler._stream_sse` и `Handler._serve_json` (`[F-01]`, `[F-02]`, `[F-03]`):**
   В исходном `server.py` ретрай при `emulate_tools=True` срабатывал только при `unmapped` нативных тулах (`NATIVE_RETRY_LIMIT = 2`) или при падении CLI с пустым выводом (`FAIL_RETRY_LIMIT = 3`) (`[F-03]`). Когда модель выдавала:
   - маркер прерванного ответа (`"I was interrupted right before making tool calls"`),
   - проглоченные токены (`non_reasoning_output - visible_est >= SWALLOWED_TOKENS_MIN`),
   - явный план вызова инструментов клиента в `reasoning` при короткой текстовой преамбуле без `tool_calls`,
   - или короткую статусную преамбулу намерения (`"Читаю вывод и проверяю состояние..."`, `"Собираю факты: ..."`),
   мост возвращал `finish_reason="stop"`, что приводило к немедленной записи `turn/end` в DSH (`[F-11]`).
4. **Блокирующее чтение `proc.stdout` без неблокирующей очереди с `maxsize` и SSE keepalive (`[F-06]`, `[F-15]`), а также отсутствие алиаса `"shell"` в `NATIVE_TOOL_ALIASES` (`[F-05]`):**
   В OpenCode v2.1.2 встроенный shell-инструмент называется `"shell"` (отсутствовал в `NATIVE_TOOL_ALIASES` `[F-05]`), а блокирующий цикл `for raw in proc.stdout:` не позволял отправлять `: keepalive\n\n` каждые `15s` и проверять дедлайн во время долгой фазы `thinking` (`[F-06]`).

## 2. Требования к архитектурному решению (`REQ-001..REQ-006`) с учётом замечаний Архитектурного Совета (`F1..F7`)

- **`REQ-001` (Двойная схема XML-тегов `<tool_invoke>` + `<tool_call>` и алиас `"shell"`):** В системной инструкции эмуляции инструментов требовать от модели тег `<tool_invoke>{"name": ..., "arguments": ...}</tool_invoke>` (не вырезаемый апстримом `opencode.ai/zen` `[F-08]`), а в `ToolCallParser` и `_parse_tool_call_blocks` поддерживать оба тега (`<tool_invoke>` и `<tool_call>`) для полной обратной совместимости (`[F-05]`, `[F-08]`). Добавить `"shell"` в `NATIVE_TOOL_ALIASES` (`[F-05]`).
- **`REQ-002` (Немедленная остановка `proc` при `etype == "error"`, классификация транзиентных ошибок и очистка маркеров обрыва):** В `Run._execute_once` и `Handler._stream_sse` при приходе `etype == "error"` немедленно останавливать дочерний процесс `_stop_proc(proc)`, чтобы не допускать запуска внутреннего синтетического шага `opencode run` (`[F-04]`, `[F-09]`), и вырезать строки `_INTERRUPTED_RE` из видимого текста. При этом выставлять `had_mid_stream_error = True` (разрешая ретрай) **только для транзиентных ошибок** (`_is_transient_stream_error(ev)`): когда `statusCode` отсутствует/`None`/`0`/`408`/`429`/`>= 500` или текст ошибки содержит транзиентный сетевой маркер (`econnreset`, `etimedout`, `timeout`, `timed out`, `socket hang up`, `interrupted`, `overloaded`, `rate limit`, `temporarily unavailable`, `fetch failed`, `network`), а для детерминированных клиентских/авторизационных ошибок `statusCode in (400, 401, 403, 404, 422)` НЕ ретраить (`had_mid_stream_error = False`) (`[F-12]`, закрытие `F5`).
- **`REQ-003` (Детектор оборванного инструментального шага `_is_incomplete_tool_step` с суженным признаком 5 и отдельным kill-switch `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY`):**
  - Ввести отдельный kill-switch `STEP_RECOVERY_ENABLED = os.environ.get("OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1").strip().lower() not in ("0", "false", "no", "off")` (независимый от `OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES`, закрытие `F4`). При `not STEP_RECOVERY_ENABLED` функция `_is_incomplete_tool_step` немедленно возвращает `False`.
  - Реализовать детерминированную функцию `_is_incomplete_tool_step(visible_text, reasoning_text, tool_names, had_mid_stream_error=False, output_tokens=0, reasoning_tokens=0) -> bool`, которая при `emulate_tools=True`, `STEP_RECOVERY_ENABLED=True` и отсутствии распознанных `tool_calls` определяет оборванный шаг по 5 признакам:
    1. `had_mid_stream_error=True` (только транзиентный `etype == "error"` или транзиентный сбой CLI);
    2. наличие маркера прерывания `_INTERRUPTED_RE` в `visible_text` или `reasoning_text`;
    3. **проглоченные токены (`swallowed_tokens`):** поскольку `tokens.output` в `opencode` включает `tokens.reasoning` (`[F-09]`), вычислять `non_reasoning_output = max(0, output_tokens - reasoning_tokens)` (если `reasoning_tokens > 0 and output_tokens >= reasoning_tokens`, иначе `output_tokens`), и при `len(stripped) <= 600` и `non_reasoning_output - max(1, len(stripped) // 3) >= SWALLOWED_TOKENS_MIN` (`35`) фиксировать проглоченный `<tool_call>`;
    4. явное упоминание имён клиентских инструментов (`tool_names`) и паттернов вызова (`_REASONING_TOOL_PLAN_RE`) в `reasoning_text` при коротком видимом ответе (`<= 600` символов);
    5. **узкая преамбула намерения (закрытие `F4`):** короткий текст (`<= 420` символов, до 6 строк, без финального вывода/таблицы/кода), который содержит **явный глагол намерения немедленного действия** (`_ACTION_INTENT_RE`: `"Читаю вывод..."`, `"Собираю факты..."`, `"Теперь посмотрим..."`, `"Let's check..."`, `"I'll run..."`) и при этом либо оканчивается на `:` / `...` / `…`, либо очень короток (`<= 220` символов). Голое двоеточие `:` в конце строки **без** `_ACTION_INTENT_RE` и без признаков 3/4 **не триггерит** ретрай (короткий финальный ответ `"Ответ: 42:"` или `"Итог проверки:"` возвращает `False`).
- **`REQ-004` (Единый потолок `A_max = 3` запусков на запрос, Full-Jitter backoff и безопасный fallback `dedup_prefix` в SSE/JSON):**
  - В `Handler._stream_sse` и `Handler._serve_json` ограничить **суммарное число запусков `opencode run` на один HTTP-запрос** константой `MAX_TOTAL_SPAWNS = 3` (`A_max = 3`: 1 первичный запуск + не более 2 повторных запусков суммарно по `fail_retries` и `attempt`) под единым `deadline = time.monotonic() + TIMEOUT_S` (закрытие `F3`).
  - Унифицировать паузу между повторными запусками через функцию `_retry_backoff_s(retry_num, rng_fn=random.uniform)` по формуле Full Jitter из `S-HERD-I2`: `rng_fn(0.0, min(RETRY_BACKOFF_CAP_S, RETRY_BACKOFF_BASE_S * (2 ** retry_num)))`, где `RETRY_BACKOFF_BASE_S = 0.5`, `RETRY_BACKOFF_CAP_S = 2.0` (закрытие `F3`).
  - В `Handler._stream_sse` при `attempt > 0`: если новый накопленный текст `current` начинается с `dedup_prefix`, подавлять уже отправленный префикс (`emitted_len = len(dedup_prefix)`). Если же `len(current) >= len(dedup_prefix)` и `not current.startswith(dedup_prefix)` (модель переформулировала начало на ретрае), **не терять текст**: сбрасывать `dedup_prefix = ""` и отправлять клиенту весь новый текст `current[emitted_len:]` (закрытие `F5`).
- **`REQ-005` (Ограниченный `_StdoutFeed` с `maxsize=4096` и SSE keepalive):** Заменить блокирующее чтение `for raw in proc.stdout:` на фоновый поток-читатель `_StdoutFeed` с ограниченной очередью `queue.Queue(maxsize=STDOUT_QUEUE_MAX)` (`STDOUT_QUEUE_MAX = 4096`). При переполнении очереди (`queue.Full`) выставлять флаг переполнения и останавливать процесс (`_stop_proc(proc)`), исключая неограниченный рост памяти (закрытие `F2`). Проверять дедлайн `TIMEOUT_S` каждые `0.25s` в `Run._execute_once` и отправлять `: keepalive\n\n` каждые `KEEPALIVE_INTERVAL_S = 15.0` секунд в `Handler._stream_sse` (`[F-06]`, `[F-15]`).
- **`REQ-006` (Сохранение публичных HTTP/OpenAI контрактов, `CD-002` и синхронизация репо с `~/.dsh`):** Внешний HTTP API (`/health`, `/v1/models`, `/v1/chat/completions`), порт `127.0.0.1:9883` и схема OpenAI остаются совместимыми (`[F-14]`, `[F-16]`). В `contract_deltas` явно зафиксировать `CD-002` (SSE `: keepalive` комментарии каждые `15s` и восстановление наблюдаемого `finish_reason` со сломанного `"stop"` на `"tool_calls"` при успешном ретрае), а в `VER-004` проверять побайтовое совпадение `bridges/opencode-zen-bridge/server.py` и `~/.dsh/bridges/opencode-zen-bridge/server.py` (закрытие `F6`, `F7`, `Seat 3 F2`).

## 3. Обязательный конверт `HL-ENV/v1` (46 канонических полей `REQUIRED_HL_ENV_FIELDS` + эксплуатационный профиль)

Ниже заданы все 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` из `aisdlc-gcge/agents/architecture.md` §3.0 в единицах СИ (секунды, байты, ядра, 1/с) и производные параметры:

```yaml
schema: HL-ENV/v1
required_hl_env_fields_46:
  P_steady: 1
  P_hpa_max: 1
  maxSurge_pct: 0.0
  maxSurge_abs: 0
  maxUnavailable_pct: 0.0
  maxUnavailable_abs: 0
  P_terminating_overlap: 0
  P_live: 1
  P_avail_min: 1
  W: 1
  N_proc: 1
  N_proc_steady: 1
  N_proc_avail_min: 1
  CPU_limit_per_pod: 2.0
  kappa_skew: 1.0
  u_bg_worker: 0.02
  U_pod_sidecars: 0.25
  Mem_limit_per_pod: 2147483648
  Mem_rss_worker_max: 67108864
  Mem_shared_max: 1207959552
  RPS_peak: 0.2
  A_max: 3
  SLA_p99_s: 180.0
  N_entities_max: 64
  Limit_dep_share_d: 6
  Limit_dep_rps_d: 2.0
  W_fetchers_d: 1
  J_init_s_d: 12.0
  J_pod_s_d: 12.0
  T_poll_s_d: 15.0
  K_calls_d: 1
  T_base_s_d: 0.5
  T_cap_s_d: 2.0
  Max_stale_age_s_c: 0.0
  Min_healthy_ratio: 1.0
  B_retry_max: 6
  min_reserve_retry_rps: 0.05
  FD_worker: 128
  ulimit_n: 4096
  lambda_new_conn_per_pod_s: 0.6
  C_active_in_scope_s: 12
  N_pods_in_scope_s: 1
  Port_range_size_s: 16383
  T_hold_s_s: 60.0
  SNAT_ips_count_s: 1
  HOTPATH_MODULES: "bridges/opencode-zen-bridge/server.py"
operational_profile:
  threads_per_worker: 12
  stdout_queue_max: 4096
  latency_p50_ms: 14000
  latency_p95_ms: 90000
  latency_p99_ms: 180000
  rps_sustained: 0.05
  rps_peak: 0.2
  concurrency_max: 6
  payload_p50_kb: 48
  payload_p99_kb: 480
  read_write_ratio: "10:90"
  session_ttl_sec: 1800
  availability_target: "99.5%"
  error_budget_window: "30d"
  cpu_request_m: 100
  cpu_limit_m: 2000
  mem_request_mb: 64
  mem_limit_mb: 2048
  workers_processes: 1
  db_pool_min: 0
  db_pool_max: 1
  conn_max_lifetime_sec: 1800
  network_bandwidth_mbps: 100
  connect_timeout_ms: 5000
  read_timeout_ms: 300000
  write_timeout_ms: 300000
  total_deadline_ms: 1800000
  max_retries: 2
  max_total_spawns: 3
  backoff_base_ms: 500
  backoff_max_ms: 2000
  jitter_mode: "full_jitter"
  retry_budget_pct: 20
  queue_max_depth: 4096
  rate_limit_rps: 2.0
  circuit_breaker_threshold: 3
  bulkhead_max_concurrent: 6
  startup_gate_sec: 12
  max_batch_size: 1
  max_response_size_mb: 16
  hot_dataset_gb: 1.8
  cache_ttl_sec: 0
  replication_lag_max_ms: 0
  graceful_shutdown_sec: 5
  keepalive_interval_sec: 15
  swallowed_tokens_min: 35
```

### Пояснение к замыканию памяти (`HL-ENV-01`) и потокам (`threads_per_worker`)
- **Память (`HL-ENV-01`):** `W = 1` (один Python-процесс `ThreadingHTTPServer`), `Mem_rss_worker_max = 67 108 864 B` (`64 MiB` — верхняя оценка RSS самого Python-процесса моста с очередями `_StdoutFeed` `maxsize=4096`), `Mem_shared_max = 1 207 959 552 B` (`1152 MiB` = до `MAX_CONCURRENT = 6` одновременных дочерних процессов `opencode run` по `192 MiB` RSS каждый), `Mem_limit_per_pod = 2 147 483 648 B` (`2048 MiB` — бюджет локального демона `com.user.dsh-opencode-zen-bridge` на рабочей станции macOS). Проверка инварианта `HL-ENV-01`:
  $$W \cdot \text{Mem\_rss\_worker\_max} + \text{Mem\_shared\_max} = 1 \times 64\text{ MiB} + 1152\text{ MiB} = 1216\text{ MiB} \le 0.80 \times 2048\text{ MiB} = 1638.4\text{ MiB} \quad (\text{PASS}).$$
- **Потоки (`threads_per_worker = 12`):** до `MAX_CONCURRENT = 6` потоков HTTP-хендлеров `ThreadingHTTPServer` + до `6` daemon-потоков `_StdoutFeed` (ровно 1 `_StdoutFeed` на активный `proc`, старый процесс завершается через `_stop_proc(proc)` до старта ретрая).

## 4. Семь гейтов отказоустойчивости (`HL-ENV/v1`, `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`) и 21 стоп-код

### 4.1. `C-MULT` (`C-MULT-I1..I5`) — Мультипликация коннектов, подпроцессов, портов и FD
- **`C-MULT-I1`:** Единственная зависимость моста — локальный CLI `opencode run` (обращающийся к `opencode.db` и `opencode.ai/zen`), `Limit_dep_share[opencode_cli] = 10` слотов на хосте. В мосте `N_proc = 1`, `G_reload = 1`, семафор `_slots = threading.Semaphore(MAX_CONCURRENT)` (`6`) удерживается на весь HTTP-запрос (ретраи выполняются внутри захваченного слота после `_stop_proc(proc)`): $1 \times 1 \times 6 = 6 \le 0.60 \times 10 = 6.0$ (`PASS`).
- **`C-MULT-I2`:** Очередь чтения stdout каждого дочернего процесса ограничена `queue.Queue(maxsize=STDOUT_QUEUE_MAX)` (`4096`), а входные HTTP-запросы ограничены семафором `_slots.acquire(timeout=TIMEOUT_S)` с отказом `HTTP 503 {"error": "slot timeout"}` (`PASS`).
- **`C-MULT-I3`:** Семафор `_slots` и `_STARTUP_LOCK` — синглтоны уровня процесса (`N_proc = 1`, `fork()` воркеров нет, а дочерний `subprocess.Popen` делает `execve("opencode")` с `close_fds=True` по умолчанию в Python 3) (`PASS`).
- **`C-MULT-I4`:** Освобождение `_slots.release()` и `_stop_proc(proc)` обёрнуты в `try ... finally:` как в `Handler.do_POST`, так и в `Run._execute_once` и `Handler._stream_sse` (`PASS`).
- **`C-MULT-I5`:** `FD_worker = 128 <= 0.70 * ulimit_n = 2867.2` (`ulimit_n = 4096`); эфемерные порты: $\lambda_{\text{new\_conn}} \cdot N_{\text{pods}} \cdot T_{\text{hold\_s}} + C_{\text{active}} = 0.6 \times 1 \times 60 + 12 = 48 \le 0.50 \times (1 \times 16383) = 8191.5$ (`PASS`).

### 4.2. `S-HERD` (`S-HERD-I1..I5`) — Защита от Thundering Herd и Full-Jitter Backoff
- **`S-HERD-I1`:** Первые `STARTUP_GATE_S = 12.0` с старта `opencode run` сериализуются через `_StartupGate` (`_STARTUP_LOCK`), причём слот освобождается сразу по первому событию `step_start`/`text`/`reasoning`/`tool_use` (`gate.release()`). Темп старта $\lambda_{\text{fetch}} = 1 / 12.0 = 0.0833\text{ с}^{-1}$, пачечная граница $1 \cdot (0.0833 + 4\sqrt{0.0833} + 4) = 5.24\text{ с}^{-1}$ при serial gate фактически не превышает $1$ одновременный холодный старт (`PASS`).
- **`S-HERD-I2`:** Пауза между ретраями вычисляется через `_retry_backoff_s(retry_num, rng_fn)` с Full Jitter `rng_fn(0.0, min(T_cap_s, T_base_s * (2 ** retry_num)))` (`T_base_s = 0.5`, `T_cap_s = 2.0`), детерминированно тестируемой с инъекцией `rng_fn` на точках `u in [0.0, 0.5, 1.0]` (`PASS`).
- **`S-HERD-I3`, `S-HERD-I4`, `S-HERD-I5`:** `N/A` с двойным доказательством: (а) `git diff` затрагивает только `bridges/opencode-zen-bridge/server.py` и `bridges/opencode-zen-bridge/tests/test_step_interruption.py`; (б) транзитивный граф вызовов `Handler.do_POST -> _stream_response/_complete_response -> _stream_sse/_serve_json -> Run.execute/_execute_once` не содержит фоновых поллеров Control Plane, `If-None-Match` кэшей, `singleflight`-кэшей и ротации секретов (`stateless HTTP-to-CLI bridge`).

### 4.3. `H-CPU` (`H-CPU-I1..I5`) — Отсутствие busy-wait, предкомпилированные регулярные выражения и бюджет CPU
- **`H-CPU-I1`:** `N/A` (двойное доказательство по `git diff` и графу вызовов: мост не хранит routing-индексы нод; маппинг тулов `canonical_map` и `allowed_map` — $O(1)$ `dict` на `<= 64` инструментов запроса).
- **`H-CPU-I2`:** Все регулярные выражения (`_TOOL_BLOCK_RE`, `_INTERRUPTED_RE`, `_ACTION_INTENT_RE`, `_REASONING_TOOL_PLAN_RE`, `_FINAL_CONCLUSION_RE`) компилируются **один раз при импорте модуля** на уровне `server.py`; внутри цикла обработки SSE-событий и `_is_incomplete_tool_step` вызовов `re.compile` и `copy.deepcopy` нет (`PASS`).
- **`H-CPU-I3`:** При `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0` (`STEP_RECOVERY_ENABLED = False`) `_is_incomplete_tool_step` возвращает `False` за $O(1)$ на первой инструкции (`Zero-Cost Disabled Path`); очередь `_StdoutFeed` использует `maxsize=4096` с немедленной остановкой процесса при `queue.Full` (`PASS`).
- **`H-CPU-I4`:** `N/A` (двойное доказательство: в `server.py` нет `asyncio` event loop и нет горячего reload `Snapshot`).
- **`H-CPU-I5`:** При `RPS_peak = 0.2`, `A_max = 3`, CPU-времени Python-моста на попытку `t_per_attempt_s = 0.05 с` и `t_per_req_s = 0.02 с`:
  $$\text{Util}_{\text{worker}} = 0.02 + 0.2 \times (0.02 + 3 \times 0.05) = 0.054 \le 0.70, \quad \text{CPU}_{\text{pod}} = 0.054 + 0.25 = 0.304 \le 0.80 \times 2.0 = 1.60 \quad (\text{PASS}).$$

### 4.4. `R-BULK` (`R-BULK-I1..I5`) и `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`
- **`R-BULK-I1`:** Сумма вспомогательных ожиданий и межатемптовых пауз по `A_max = 3` попыткам: $\sum_{a=1}^{3} (T_{\text{crit\_aux\_s}}(a) + T_{\text{wait\_s}}(a) + T_{\text{backoff\_s}}(a)) \le (12.0 + 0) + (12.0 + 1.0) + (12.0 + 2.0) = 39.0\text{ с} \le 0.30 \times 180.0 = 54.0\text{ с}$ (`SLA_p99_s = 180.0`), а при `time.monotonic() >= deadline` цикл немедленно прерывается (`PASS`).
- **`R-BULK-I2`:** Потолок запусков `MAX_TOTAL_SPAWNS = 3` (`A_max = 3`) и семафор `_slots = Semaphore(6)` жёстко ограничивают параллелизм и число ретраев (`PASS`).
- **`R-BULK-I3`:** Классификатор `_is_transient_stream_error(ev)` разделяет транзиентные сетевые сбои (`ECONNRESET`, `ETIMEDOUT`, `429`, `5xx` -> ретрай) и детерминированные ошибки (`400`, `401`, `403`, `404`, `422` -> немедленный Fail-Closed без ретрая) (`PASS`).
- **`R-BULK-I4`, `R-BULK-I5`, `M-SEM/v1`:** `N/A` с двойным доказательством (`git diff` + граф вызовов `server.py`: мост проксирует запросы в единственный локальный бинарник `OPENCODE_BIN` без пула прокси-нод и без мульти-тенантных пулов `crawler`/`llm`).
- **`T-LIFE/v1`:** Жизненный цикл каждого дочернего `proc` и его daemon-потока `_StdoutFeed` детерминированно закрывается вызовом `_stop_proc(proc)` (`SIGTERM` -> `SIGKILL`) в `finally:` перед любым следующим `attempt` или выходом из запроса (`PASS`).
- **`O-EXIT/v1`:** На каждом выходе из `Handler.do_POST` (включая `503 slot timeout`, `400 invalid json`, ошибку `opencode` и успешный ответ) в `bridge.log` записывается структурная строка с `mode` (`stream`/`json`), `model`, `rc`, `tools`, `out_chars`, `duration` (`PASS`).
<<<END ARTIFACT>>>


---
PANEL-NONCE: 1496e981c6adcf00
ARTIFACT-SHA256: 90b1d66499dceadac24f7990423b4c53b2ebd5b23247aaf50efe187851598b9e
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 1496e981c6adcf00» и «ARTIFACT-SHA256: 90b1d66499dceadac24f7990423b4c53b2ebd5b23247aaf50efe187851598b9e».
