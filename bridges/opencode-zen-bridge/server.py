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

import errno
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast


def _run_serve_helper_cli(args: list[str]) -> int:
    """Ранний помощник serve: один лидер группы на попытку, lease и дренаж пайпов."""
    if len(args) != 6:
        return 2
    (
        attempt_id,
        port_text,
        opencode_bin,
        lease_dir_text,
        parent_pid_text,
        parent_lstart,
    ) = args
    if not attempt_id or not opencode_bin or not lease_dir_text or not parent_lstart:
        return 2
    if not port_text.isdecimal() or not parent_pid_text.isdecimal():
        return 2
    port = int(port_text)
    parent_pid = int(parent_pid_text)
    if not 1 <= port <= 65535 or parent_pid <= 0:
        return 2
    lease_dir = Path(lease_dir_text)
    stopped: dict[str, bool] = {"flag": False}

    def _on_term(_signum: int, _frame: object) -> None:
        """Отметить SIGTERM без тяжёлой работы в обработчике."""
        stopped["flag"] = True

    _ = signal.signal(signal.SIGTERM, _on_term)
    try:
        lease_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(lease_dir, 0o700)
    except OSError:
        return 2
    lease_path = lease_dir / f"lease-{attempt_id}.json"

    def _lstart_of(pid: int) -> str:
        """lstart процесса из ps; при сбое ps — epoch-секунды."""
        try:
            out = subprocess.run(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return out.stdout.strip() or str(int(time.time()))
        except (OSError, subprocess.SubprocessError):
            return str(int(time.time()))

    helper_lstart = _lstart_of(os.getpid())

    def _write_lease(extra: dict[str, object]) -> None:
        """Атомарно опубликовать lease помощника."""
        payload: dict[str, object] = {
            "schema_version": 1,
            "attempt_id": attempt_id,
            "owner_uid": os.getuid(),
            "parent_pid": parent_pid,
            "parent_start_ts": parent_lstart,
            "helper_pid": os.getpid(),
            "helper_lstart": helper_lstart,
            "pgid": os.getpgrp(),
            "port": port,
            "start_ts": time.time(),
            "phase": "starting",
        }
        payload.update(extra)
        tmp_path = lease_path.with_suffix(".tmp")
        try:
            _ = tmp_path.write_text(json.dumps(payload), "utf-8")
            os.replace(tmp_path, lease_path)
        except OSError:
            pass

    def _fd_ready() -> bool:
        """EOF на lifeline fd 0 виден без блокировки."""
        try:
            ready, _w, _x = select.select([0], [], [], 0)
            return bool(ready)
        except BlockingIOError:
            return False
        except (OSError, ValueError) as _gone_exc:
            if isinstance(_gone_exc, OSError) and _gone_exc.errno in (
                errno.EAGAIN,
                errno.EWOULDBLOCK,
            ):
                return False
            return True

    _write_lease({})
    if _fd_ready():
        try:
            lease_path.unlink()
        except OSError:
            pass
        return 0
    serve_env = dict(os.environ)
    _ = serve_env.pop("OPENCODE_BIN", None)
    try:
        serve_proc = subprocess.Popen(
            [opencode_bin, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=False,
            close_fds=True,
            env=serve_env,
        )
    except OSError:
        return 2
    serve_lstart = _lstart_of(serve_proc.pid)
    _write_lease(
        {"serve_pid": serve_proc.pid, "serve_lstart": serve_lstart, "phase": "ready"}
    )
    try:
        _ = sys.stdout.write(
            json.dumps({"serve_pid": serve_proc.pid, "pgid": os.getpgrp()}) + "\n"
        )
        _ = sys.stdout.flush()
    except OSError:
        pass
    pipes: list[int] = []
    for stream in (serve_proc.stdout, serve_proc.stderr):
        if stream is not None:
            pipes.append(stream.fileno())
            os.set_blocking(stream.fileno(), False)
    code = 0
    try:
        while True:
            if stopped["flag"] or _fd_ready():
                break
            poll = serve_proc.poll()
            if poll is not None:
                code = int(poll)
                break
            watch: list[int] = [0, *pipes]
            try:
                ready, _w, _x = select.select(watch, [], [], 0.05)
            except (OSError, ValueError):
                ready = []
            for item in ready:
                if item == 0:
                    stopped["flag"] = True
                    continue
                try:
                    chunk = os.read(item, 65536)
                except OSError:
                    chunk = b""
                if chunk:
                    try:
                        _ = sys.stderr.write(chunk.decode("utf-8", "replace"))
                        _ = sys.stderr.flush()
                    except OSError:
                        pass
            if stopped["flag"]:
                break
    finally:
        # Убить всю собственную группу (serve и внуков), lease — только после смерти группы.
        _pgid = os.getpgrp()

        def _group_members() -> list[int]:
            """Живые члены группы, кроме самого помощника (ps — в отдельной сессии)."""
            _ = serve_proc.poll()
            try:
                listing = subprocess.run(
                    ["ps", "-A", "-o", "pid=,pgid="],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    start_new_session=True,
                )
            except (OSError, subprocess.SubprocessError):
                return [serve_proc.pid] if serve_proc.poll() is None else []
            members: list[int] = []
            for row in listing.stdout.splitlines():
                cols = row.split()
                if (
                    len(cols) == 2
                    and cols[0].isdecimal()
                    and cols[1] == str(_pgid)
                    and int(cols[0]) != os.getpid()
                ):
                    members.append(int(cols[0]))
            return members

        try:
            os.killpg(_pgid, signal.SIGTERM)
        except OSError:
            if serve_proc.poll() is None:
                try:
                    serve_proc.terminate()
                except OSError:
                    pass
        members_now = _group_members()
        _term_deadline = time.monotonic() + 4.0
        while members_now and time.monotonic() < _term_deadline:
            time.sleep(0.1)
            members_now = _group_members()
        if members_now:
            # Эскалация: SIGKILL всем оставшимся членам группы, даже если serve уже вышел.
            for _pid in members_now:
                try:
                    os.kill(_pid, signal.SIGKILL)
                except OSError:
                    pass
            _kill_deadline = time.monotonic() + 2.0
            while members_now and time.monotonic() < _kill_deadline:
                time.sleep(0.05)
                members_now = _group_members()
        # Дренировать остаток пайпов, чтобы потомок не остался с полным буфером.
        for fd in pipes:
            try:
                while True:
                    chunk = os.read(fd, 65536)
                    if not chunk:
                        break
                    _ = sys.stderr.write(chunk.decode("utf-8", "replace"))
            except OSError:
                pass
        if not members_now:
            try:
                lease_path.unlink()
            except OSError:
                pass
    return code


if sys.argv[1:2] == ["--serve-helper"]:
    raise SystemExit(_run_serve_helper_cli(sys.argv[2:]))
else:
    import base64
    import collections
    import hmac
    import http.client
    import io
    import queue
    import random
    import re
    import secrets
    import shlex
    import shutil
    import socket
    import sqlite3
    import stat
    import tempfile
    import threading
    import uuid
    from collections.abc import Callable, Iterable, Iterator
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from typing import TypedDict
    from urllib.parse import quote, urlsplit

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import zen_catalog as zc

HOST = os.environ.get("OPENCODE_ZEN_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_PORT", "9883"))
AUTH_KEY = os.environ.get("OPENCODE_ZEN_BRIDGE_KEY", "").strip()

TIMEOUT_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_TIMEOUT_S", "1800"))
# Пауза stdout `opencode run` на большом промпте может быть долгой; пока она длится, в SSE уходит
# пустая дельта раз в KEEPALIVE_INTERVAL_S (0 — выключено), иначе клиент рвёт «молчащий» стрим.
KEEPALIVE_INTERVAL_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_KEEPALIVE_S", "15.0"))
MAX_CONCURRENT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT", "2"))

OPENCODE_BIN = os.environ.get(
    "OPENCODE_BIN", str(Path.home() / ".opencode" / "bin" / "opencode")
)
WORKSPACE = Path(
    os.environ.get(
        "OPENCODE_ZEN_BRIDGE_WORKSPACE",
        str(Path(__file__).resolve().parent / "workspace"),
    )
)
LOG_PATH = Path(
    os.environ.get(
        "OPENCODE_ZEN_BRIDGE_LOG",
        str(Path(__file__).resolve().parent / "logs" / "bridge.log"),
    )
)

DEFAULTWORKDIR = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_WORKDIR", str(WORKSPACE)))

# --- Каталог моделей Zen ----------------------------------------------------------------
# 2026-10-24: каталог динамический. Единственный писатель — sync_dsh_models.py: он пересекает
# api.json (free, не deprecated, tool_call) со списком Zen и пишет state/zen-catalog.json; мост
# только читает файл (перечитывание по mtime, не чаще раза в CATALOG_STAT_INTERVAL_S) и при
# отсутствии/порче файла берёт встроенный снимок zen_catalog.STATIC_FALLBACK_CATALOG.
# Zen-модели запускаются как `opencode run --standalone` с OPENCODE_MODELS_PATH на свежий api.json
# и БЕЗ OPENCODE_API_KEY (истёкший ключ из env давал 401 api_key_expired — причина отказа от
# standalone 2026-10-19). Режим static (kill-switch) — прежний маршрут через фоновый сервис.
DEPRECATED_MODEL_ALIASES: dict[str, str] = zc.DEPRECATED_MODEL_ALIASES


def _normalize_catalog_mode(raw: str) -> str:
    """dynamic (по умолчанию) | static; `legacy` — синоним static (аварийный kill-switch)."""
    value = (raw or "").strip().lower()
    return "static" if value in ("static", "legacy") else "dynamic"


CATALOG_MODE = _normalize_catalog_mode(
    os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_MODE", "dynamic")
)
CATALOG_STATE_PATH = Path(
    os.environ.get(
        "OPENCODE_ZEN_BRIDGE_CATALOG_STATE",
        str(Path(__file__).resolve().parent / "state" / "zen-catalog.json"),
    )
)
OPENCODE_MODELS_PATH = os.environ.get(
    "OPENCODE_ZEN_BRIDGE_MODELS_PATH",
    str(Path.home() / ".cache" / "opencode" / "models.json"),
)
CATALOG_STAT_INTERVAL_S = float(
    os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_STAT_INTERVAL_S", "5")
)

# Живой каталог: id -> метаданные (context_length, max_output, supports_variant, variant_map, ...).
# Словарь изменяется на месте, чтобы ссылки на него (в том числе в тестах) оставались верными.
ALLOWED_MODELS: dict[str, dict[str, Any]] = {}
# Устаревшие/выбывшие id -> модель-исполнитель (статические ∪ deprecated из api.json ∪ retired).
MODEL_ALIASES: dict[str, str] = dict(DEPRECATED_MODEL_ALIASES)

_catalog_lock = threading.RLock()
_catalog_ids: set[str] = (
    set()
)  # id, добавленные каталогом (тестовые/Go-записи не трогаем)
_catalog_mtime: int | None = None
_catalog_checked_at = float("-inf")
CATALOG_SOURCE = "static"


def _set_catalog_source(source: str) -> None:
    """Обновить публичный CATALOG_SOURCE без global-записи в reload."""
    globals()["CATALOG_SOURCE"] = source


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
    global _catalog_mtime, _catalog_ids
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
        _set_catalog_source(source)
    return {
        "ok": True,
        "source": source,
        "mode": CATALOG_MODE,
        "models": sorted(models),
        "aliases": len(MODEL_ALIASES),
        "degraded": bool(state.get("degraded")),
    }


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
    return sorted(
        m
        for m, meta in ALLOWED_MODELS.items()
        if not meta.get("provider") and not meta.get("base_url")
    )


def _resolve_alias(model_id: str) -> str | None:
    """Модель-исполнитель для устаревшего/выбывшего id; None — id неизвестен."""
    target, aliased = zc.resolve_model(
        model_id, _zen_active_ids(), MODEL_ALIASES, DEFAULT_MODEL
    )
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
    return text.replace(TOOL_CALL_OPEN, ALT_TOOL_CALL_OPEN).replace(
        TOOL_CALL_CLOSE, ALT_TOOL_CALL_CLOSE
    )


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
STEP_RECOVERY_ENABLED = os.environ.get(
    "OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1"
).strip().lower() not in ("0", "false", "no", "off")

# 2026-10-24 (AD-003): единый потолок запусков `opencode run` на один HTTP-запрос — суммарно по
# первичному запуску, повтору транзиторного отказа CLI, повтору незавершённого шага и
# повтору встроенного инструмента без DSH-двойника (A_max).
MAX_TOTAL_SPAWNS = max(
    1, int(os.environ.get("OPENCODE_ZEN_BRIDGE_MAX_TOTAL_SPAWNS", "3"))
)

# 2026-10-10: `opencode run` иногда падает за ~1 с с rc=1 без вывода
# («Error: Unexpected error … database is locked», sqlite opencode при параллельном старте).
# Такой отказ — транзиторный: прогон без вывода повторяется (не более FAIL_RETRY_LIMIT раз,
# и всегда внутри потолка MAX_TOTAL_SPAWNS: первичный запуск + FAIL_RETRY_LIMIT <= MAX_TOTAL_SPAWNS).
FAIL_RETRY_LIMIT = min(
    int(os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRIES", "3")), MAX_TOTAL_SPAWNS - 1
)
# Старый линейный backoff заменён Full Jitter (_retry_backoff_s); значение 0 по-прежнему отключает паузы.
FAIL_RETRY_BACKOFF_S = float(
    os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRY_BACKOFF_S", "0.8")
)
RETRY_BACKOFF_BASE_S = float(
    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_BASE_S", "0.5")
)
RETRY_BACKOFF_CAP_S = float(
    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_CAP_S", "2.0")
)

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
RETRY_BUDGET_PER_REQUEST = float(
    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_PER_REQUEST", "0.20")
)
RETRY_BUDGET_RESERVE_RPS = float(
    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_RESERVE_RPS", "0.05")
)
CB_FAIL_THRESHOLD = int(os.environ.get("OPENCODE_ZEN_BRIDGE_CB_FAIL_THRESHOLD", "5"))
CB_RESET_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_CB_RESET_S", "10.0"))


def _retry_backoff_s(
    retry_num: int, rng_fn: Callable[[float, float], float] = random.uniform
) -> float:
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
    re.IGNORECASE,
)
_INTERRUPT_MARKERS = (
    "interrupted right before making tool calls",
    "previous response was interrupted",
)
# Сырой вызов `<tool_call>{…` / `<tool_invoke>{…`: не inline-код markdown и не упоминание тега в прозе.
_RAW_CALL_RE = re.compile(
    r"(?<!`)<(?:tool_call|tool_invoke)>\s*(?:(?:```|~~~)\w*\s*)?\{"
)
# Модель явно сказала, что отвечает без инструментов.
_NO_TOOLS_RE = re.compile(
    r"\bno tools?\b|\bwithout (?:any )?tools?\b|\bno need\b|\bnot (?:needed|required|necessary)\b|"
    r"\brule 0\b|правило 0|не требует инструмент|без инструмент|инструмент\w* не нужн",
    re.IGNORECASE,
)
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
    re.IGNORECASE,
)
_PROMISE_RE = _ACTION_INTENT_RE  # прежнее имя
# Финальный вывод/ответ (а не преамбула шага): заголовок-вывод в начале текста или фраза-итог.
_FINAL_CONCLUSION_RE = re.compile(
    r"^[\s*#>_`\-]*(?:итог(?:о|и)?|ответ|результат(?:ы)?|резюме|заключение|"
    r"summary|conclusion|answer|result|done|готово)\b|"
    r"\b(?:ошибок нет|нет ошибок|всё в порядке|все в порядке|так задумано|тесты (?:зел[её]ные|прошли)|"
    r"no errors?|all (?:good|tests pass\w*)|everything is fine)\b",
    re.IGNORECASE,
)
# План пачки вызовов в reasoning текущего шага.
_REASONING_TOOL_PLAN_RE = re.compile(
    r"let me batch|all in batch|\bone message\s*:|\bin one (?:message|batch|turn)\b|parallel calls|"
    r"\bcalls? in parallel\b|\bthen (?:both )?(?:tool )?calls\b|making tool calls|"
    r"\btool calls? (?:now|next|in parallel)\b|"
    r"\bemit (?:the )?(?:tool[_\s]?(?:call|invoke)?\s*)?blocks?\b|\btool[_\s]?(?:call|invoke)?\s*blocks?\b|"
    r"\bcall (?:the )?tools\b|\btwo independent calls\b|\bindependent calls\b",
    re.IGNORECASE,
)
_PLAN_RE = _REASONING_TOOL_PLAN_RE  # прежнее имя
# Мышление, где модель пишет «I need to call job_output…» без готовой фразы-плана.
_CALL_INTENT_RE = re.compile(
    r"\b(?:call|invoke|emit|parallel|batch|need to|let me|i'll|i will|should)\b",
    re.IGNORECASE,
)
# Апстрим вырезал `<tool_call>…</tool_call>` из text, но токены в step_finish остались: столько
# лишних токенов над оценкой видимого текста — признак проглоченного вызова.
SWALLOWED_TOKENS_MIN = 35
INCOMPLETE_STEP_MAX_TEXT = 1200  # дольше — это ответ, а не статусная преамбула
INCOMPLETE_STEP_TAIL = 400
TAIL_REMINDER_MIN_CHARS = 4000
SWALLOWED_MAX_TEXT = 600  # признак 3
PLAN_MAX_TEXT = 600  # признак 4
PREAMBLE_MAX_CHARS = 420  # признак 5
PREAMBLE_MAX_LINES = 6
PREAMBLE_SHORT_CHARS = 220

# Mid-stream `etype == "error"`: транзиентные сбои (повторяем) против детерминированных (Fail-Closed).
_FATAL_STREAM_STATUSES = (400, 401, 403, 404, 422)
_TRANSIENT_ERROR_MARKERS = (
    "econnreset",
    "etimedout",
    "timeout",
    "timed out",
    "socket hang up",
    "interrupted",
    "overloaded",
    "rate limit",
    "temporarily unavailable",
    "fetch failed",
    "network",
    "connection reset",
    "broken pipe",
    "eof",
)


def _strip_interrupted(text: str) -> str:
    """Убрать артефакт SYNTHETIC-продолжения opencode («I was interrupted right before…»)."""
    return _INTERRUPTED_RE.sub("", text).replace(
        "[opencode-zen-bridge: шаг модели оборвался]", ""
    )


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
                end == len(text) or not _is_ident_char(text[end])
            ):
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
        "OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1"
    ).strip().lower() in ("0", "false", "no", "off")


def _visible_token_estimate(stripped: str) -> int:
    """Грубая оценка токенов видимого текста (верхняя: не завышаем «проглоченные» токены)."""
    return max(len(stripped) // 2, _estimate_tokens(stripped)) if stripped else 0


def _swallowed_tokens(
    stripped: str, output_tokens: int, reasoning_tokens: int = 0
) -> int:
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
    return len(stripped) <= PREAMBLE_SHORT_CHARS and _mentions_request_tool(
        stripped, names
    )


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
        _mentions_request_tool(tail, names) and bool(_CALL_INTENT_RE.search(tail))
    )


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


def _drain_stderr(
    proc: subprocess.Popen[str], sink: collections.deque[str] | list[str]
) -> None:
    """Вычитать stderr в ограниченный буфер (кольцо на 64 строки, без секретов в лог)."""
    # Дренаж stderr помощника/CLI в ограниченный буфер; содержимое не логируется.
    try:
        assert proc.stderr is not None
        for line in proc.stderr:
            line_text: str = cast(str, line).strip()
            line = line_text
            if line:
                if isinstance(sink, list):
                    sink_list: list[str] = sink
                    _ = sink_list.append(line)
                    while len(sink_list) > 64:
                        _ = sink_list.pop(0)
                else:
                    sink_deque: collections.deque[str] = sink
                    _ = sink_deque.append(line)
    except (OSError, ValueError):
        pass


def _stop_proc(proc: subprocess.Popen[str]) -> None:
    """Остановить группу `opencode run` (SIGTERM -> SIGKILL); процесс запущен со start_new_session."""
    pgid = proc.pid  # start_new_session=True => pgid == pid лидера
    if proc.poll() is not None and not _pid_alive(-pgid):
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
        if proc.poll() is None:
            _ = proc.wait(timeout=5)
        else:
            # Лидер вышел, но группа ещё жива: ждём SIGTERM до 0.5 с.
            _dl = time.monotonic() + 0.5
            while time.monotonic() < _dl and _pid_alive(-pgid):
                time.sleep(0.05)
    except (OSError, subprocess.TimeoutExpired):
        pass
    if _pid_alive(-pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
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
        self._queue: queue.Queue[str] = queue.Queue(
            maxsize=STDOUT_QUEUE_MAX if maxsize is None else maxsize
        )
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
                    _log(
                        f"stdout_overflow queue_max={self._queue.maxsize} dropped_total={self.dropped_total}, "
                        "stopping opencode run"
                    )
                    _stop_proc(self._proc)
                    break
        except (OSError, ValueError) as exc:
            self._error = exc
        finally:
            self._done.set()  # после всех put: потребитель, увидев флаг, дочитывает остаток очереди

    def lines(
        self,
        deadline: float,
        idle_s: float = 0.0,
        on_idle: Callable[[], None] | None = None,
    ) -> Iterator[str]:
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
                    if (
                        idle_s > 0
                        and on_idle is not None
                        and now - last_activity >= idle_s
                    ):
                        on_idle()
                        last_activity = now
                    continue
            last_activity = time.monotonic()
            if last_activity > deadline:
                self.timed_out = True
                return
            if idle_s > 0 and on_idle is not None:
                # Watchdog проверяется и при поступлении строк, а не только на Empty:
                # служебный поток без токенов должен прерываться по тем же часам.
                on_idle()
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


_PROXY_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
)
_LOOPBACK_NO_PROXY = ("127.0.0.1", "localhost", "::1")
# THREAT-003 + принятое отклонение DEV-02: к ключам пакета добавлены переменные прокси.
_STANDALONE_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "TMPDIR",
    "LANG",
    "NO_PROXY",
    "no_proxy",
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
_DEFAULT_PROXYRACK_FILE = (
    Path.home()
    / ".local/share/gigaexplorator-proxies/2026-08-31-volkov-proxy-manager/06-proxyrack-global-dc-1000.txt"
)
_PROXYRACK_FORWARD_LOG = Path.home() / "Library/Logs/Factory/proxyrack-forward.log"
_DEFAULT_PROXYRACK_GATEWAY = "121.91.235.6"
_PROXYRACK_LOG_TAIL_BYTES = 16 * 1024
_IPV4_RE = re.compile(
    r"^(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$"
)

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
    pool_path = Path(
        os.environ.get(
            "OPENCODE_ZEN_BRIDGE_PROXYRACK_FILE", str(_DEFAULT_PROXYRACK_FILE)
        )
    )
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
            entries = [
                e
                for e in (
                    _parse_proxy_pool_line(ln, gateway) for ln in lines if ln.strip()
                )
                if e
            ]
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


DYNAMIC_CONFIG_PATH = Path(__file__).resolve().parent / "dynamic_config.json"
LEASE_DIR = Path("/tmp/opencode-zen-bridge-leases")
SERVE_TEST_ELIGIBLE = False
FIRST_EVENT_TIMEOUT_S = float(
    os.environ.get("OPENCODE_ZEN_BRIDGE_FIRST_EVENT_TIMEOUT_S", "20.0")
)
FIRST_TOKEN_TIMEOUT_S = float(
    os.environ.get("OPENCODE_ZEN_BRIDGE_FIRST_TOKEN_TIMEOUT_S", "60.0")
)
STALL_TIMEOUT_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S", "60.0"))
FIRST_STATUS_DELAY_S = 0.65
STATUS_WAITING_INTERVAL_S = 5.0
STALL_HEARTBEAT_INTERVAL_S = 15.0
STATUS_INITIAL = "[мост] Подключение к модели…\n"
STATUS_WAITING = "[мост] Ожидание первого токена…\n"
STATUS_CONTINUATION = "[мост] Ожидание продолжения…\n"
_SERVE_ALLOWLIST = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "TERM",
    "COLORTERM",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
    "XDG_DATA_HOME",
    "XDG_CONFIG_HOME",
    "OPENCODE_CONFIG",
    "OPENCODE_CONFIG_CONTENT",
    "OPENCODE_MODELS_PATH",
)
_dynamic_config_cache: dict[str, object] = {"key": None, "value": False, "path": ""}
_LSOF_CALLS: collections.deque[int] = collections.deque(maxlen=64)
_PORT_ALLOC_LOCK = threading.Lock()
_ACTIVE_SERVE_PORTS: set[int] = set()
_MAX_STDERR_TAIL_BYTES = 16384
_STDERR_CHUNK_READ_BYTES = 4096
_MAX_SSE_LINE_BYTES = 1024 * 1024
_STEP_DRAIN_WINDOW_S = 1.0
_MAX_SERVE_QUEUE_BYTES = 16 * 1024 * 1024
_MAX_SERVE_ACCUMULATED_BYTES = 16 * 1024 * 1024
_MAX_SERVE_HTTP_BODY_BYTES = 8 * 1024 * 1024
_MAX_SERVE_NATIVE_TOOLS = 128
_DOWNSTREAM_WRITE_TIMEOUT_S = 5.0
_AUX_IO_BUDGET_S = 54.0


class ServeUnavailable(Exception):
    """Serve недоступен до барьера доставки: допустим fallback на run в auto."""


class ServeClientDisconnect(Exception):
    """Клиент отключился при запуске serve: повтор через run запрещён."""


class ServeStartupDeadlineExceeded(Exception):
    """Общий бюджет запроса исчерпан при запуске serve."""


class ServeProtocolError(ValueError):
    """Битое событие serve: протокол, а не модель."""


class ServeSecurityError(Exception):
    """Отказ безопасности serve: fail-closed без fallback."""


class _ServeHealth:
    """Sticky деградация serve по протокольным отказам: 3 отказа, TTL 120 с."""

    def __init__(self, threshold: int = 3, ttl_s: float = 120.0) -> None:
        self.threshold = threshold
        self.ttl_s = ttl_s
        self.failures = 0
        self._degraded_until = 0.0
        self._lock = threading.Lock()

    def record_failure(self, now: float | None = None) -> None:
        """Засчитать протокольный отказ serve."""
        with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self._degraded_until = (
                    time.monotonic() if now is None else now
                ) + self.ttl_s

    def record_success(self) -> None:
        """Сбросить деградацию после успешной попытки."""
        with self._lock:
            self.failures = 0
            self._degraded_until = 0.0

    def is_degraded(self, now: float | None = None) -> bool:
        """Истёк ли sticky TTL деградации."""
        with self._lock:
            at = time.monotonic() if now is None else now
            if self._degraded_until and at >= self._degraded_until:
                self.failures = 0
                self._degraded_until = 0.0
                return False
            return bool(self._degraded_until and at < self._degraded_until)


FALLBACK_DECISION_TABLE: list[dict[str, object]] = [
    {
        "phase": "SPAWN/READY/CREATE/SUBSCRIBE",
        "event": "local spawn/ready/setup failure",
        "DELIVERED": "false",
        "action": "fallback_to_run",
        "ServeHealth_failure_increment": 1,
        "UpstreamBreaker_failure_increment": 0,
    },
    {
        "phase": "SPAWN→READY",
        "event": "ownership failure/timeout",
        "DELIVERED": "false",
        "action": "fallback_to_run",
        "ServeHealth_failure_increment": 1,
        "UpstreamBreaker_failure_increment": 0,
    },
    {
        "phase": "PROMPT_SENDING",
        "event": "first_event_timeout20s, no response headers and no valid execution SSE",
        "DELIVERED": "false",
        "action": "fallback_to_run",
        "ServeHealth_failure_increment": 1,
        "UpstreamBreaker_failure_increment": 0,
    },
    {
        "phase": "DELIVERED",
        "event": "first_event_timeout20s after headers, no valid execution SSE",
        "DELIVERED": "true",
        "action": "serve_retry",
        "ServeHealth_failure_increment": 1,
        "UpstreamBreaker_failure_increment": 0,
    },
    {
        "phase": "DELIVERED",
        "event": "first_token_timeout/stall with valid protocol and model silence",
        "DELIVERED": "true",
        "action": "serve_retry",
        "ServeHealth_failure_increment": 0,
        "UpstreamBreaker_failure_increment": 1,
    },
    {
        "phase": "DELIVERED",
        "event": "first_token_timeout with proven protocol/capability defect (non-security)",
        "DELIVERED": "true",
        "action": "serve_retry",
        "ServeHealth_failure_increment": 1,
        "UpstreamBreaker_failure_increment": 0,
    },
    {
        "phase": "ANY",
        "event": "HTTP401/403 or permission/form/capability-security failure",
        "DELIVERED": "any",
        "action": "fail_closed",
        "ServeHealth_failure_increment": 0,
        "UpstreamBreaker_failure_increment": 0,
    },
    {
        "phase": "ANY",
        "event": "HTTP400/404/422 invalid request",
        "DELIVERED": "any",
        "action": "fail_closed",
        "ServeHealth_failure_increment": 0,
        "UpstreamBreaker_failure_increment": 0,
    },
    {
        "phase": "PRE_PROMPT",
        "event": "HTTP5xx local readiness/create/subscribe endpoint",
        "DELIVERED": "false",
        "action": "fallback_to_run",
        "ServeHealth_failure_increment": 1,
        "UpstreamBreaker_failure_increment": 0,
    },
    {
        "phase": "PROMPT_RESPONSE",
        "event": "HTTP429/provider5xx prompt response headers_at received",
        "DELIVERED": "any",
        "action": "serve_retry_via_allow_retry_after_headers_at",
        "ServeHealth_failure_increment": 0,
        "UpstreamBreaker_failure_increment": 1,
    },
    {
        "phase": "DELIVERED",
        "event": "invalid SSE/EOF without terminal proven protocol-only",
        "DELIVERED": "true",
        "action": "serve_retry",
        "ServeHealth_failure_increment": 1,
        "UpstreamBreaker_failure_increment": 0,
    },
    {
        "phase": "ANY",
        "event": "client cancel/deadline/budget exhausted",
        "DELIVERED": "any",
        "action": "fail_closed",
        "ServeHealth_failure_increment": 0,
        "UpstreamBreaker_failure_increment": 0,
    },
]


class _WatchdogState(TypedDict):
    """Состояние watchdog одного legacy-прогона."""

    reason: str
    first_event_at: float | None
    first_token_at: float | None
    last_token_at: float
    status_next: float
    last_keepalive: float
    last_reasoning: str


class _ServeResult(TypedDict):
    """Итог одной serve-попытки с конкретными типами."""

    reasonings: list[str]
    texts: list[str]
    native_calls: list[dict[str, object]]
    usage: dict[str, int]
    error: dict[str, object] | None
    exit_reason: str
    delivered: bool
    terminal: str
    first_event_at: float | None
    first_token_at: float | None
    step_closed: bool
    first_event_ms: int | None
    ttft_ms: int | None
    prompt_status: int | None
    transient_error: bool


def _as_dict(value: object) -> dict[str, object]:
    """Объект как словарь с строковыми ключами, иначе пустой."""
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    return {}


def _combine_surrogates(value: object) -> object:
    """Склеить суррогатные пары UTF-16 в строках после json.loads."""
    if isinstance(value, str):
        try:
            return value.encode("utf-16", "surrogatepass").decode("utf-16")
        except UnicodeError as exc:
            raise ServeProtocolError(
                "invalid unpaired surrogate in serve event"
            ) from exc
    if isinstance(value, dict):
        return {
            str(_combine_surrogates(str(k))): _combine_surrogates(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_combine_surrogates(v) for v in value]
    return value


def _loads_object(raw: str) -> dict[str, object] | None:
    """JSON-объект стандартным json.loads; не-объект или битый JSON — None."""
    try:
        parsed: object = cast(object, json.loads(raw))
    except (ValueError, TypeError):
        return None
    if isinstance(parsed, dict):
        combined = _combine_surrogates({str(k): v for k, v in parsed.items()})
        return combined if isinstance(combined, dict) else None
    return None


def _loads_serve_object(raw: str) -> dict[str, object]:
    """JSON-объект события serve; битый JSON — ServeProtocolError."""
    parsed = _loads_object(raw)
    if parsed is None:
        raise ServeProtocolError("invalid_serve_event: json")
    return parsed


def _as_int(value: object) -> int:
    """Целое из wire-значения, иначе 0."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _read_dynamic_config_enabled(path: Path | None = None) -> bool:
    """Boolean REALTIME_SERVE_ENABLED из dynamic_config.json с кэшем по stat."""
    target = DYNAMIC_CONFIG_PATH if path is None else path
    try:
        stat = target.stat()
    except OSError:
        _dynamic_config_cache.update({"key": None, "value": False, "path": str(target)})
        return False
    key = (stat.st_mtime_ns, stat.st_size)
    if (
        _dynamic_config_cache.get("path") == str(target)
        and _dynamic_config_cache.get("key") == key
    ):
        return bool(_dynamic_config_cache.get("value"))
    value = False
    try:
        data = _as_dict(_loads_object(target.read_text("utf-8")))
        enabled_obj = data.get("REALTIME_SERVE_ENABLED")
        if isinstance(enabled_obj, bool):
            value = enabled_obj
    except (OSError, ValueError) as exc:
        _log(f"dynamic config unreadable: {_clean_err(str(exc))}")
        value = False
    _dynamic_config_cache.update({"key": key, "value": value, "path": str(target)})
    return value


_dynamic_config_enabled = _read_dynamic_config_enabled


def _serve_permission_effect() -> str:
    """Эффект permission из env политики: ask_reject -> ask, deny -> deny."""
    policy = os.environ.get(
        "OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY", "ask_reject"
    ).strip()
    if policy == "ask_reject":
        return "ask"
    if policy == "deny":
        return "deny"
    raise ServeSecurityError(f"unsupported serve permission policy: {policy}")


def _serve_env(model_id: str = "") -> dict[str, str]:
    """Санитизированное окружение serve на всех ветках маршрутизации."""
    base = _run_env(model_id)
    env: dict[str, str] = {k: v for k, v in base.items() if k in _SERVE_ALLOWLIST}
    _ = env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    if "HOME" not in env and os.environ.get("HOME"):
        env["HOME"] = str(os.environ["HOME"])
    if "XDG_DATA_HOME" not in env and os.environ.get("XDG_DATA_HOME"):
        env["XDG_DATA_HOME"] = str(os.environ["XDG_DATA_HOME"])
    config_raw = env.get("OPENCODE_CONFIG_CONTENT") or OPENCODE_CONFIG_CONTENT
    config = _as_dict(_loads_object(config_raw)) if config_raw else {}
    config["permission"] = {"*": _serve_permission_effect()}
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, ensure_ascii=False)
    state_dir = tempfile.mkdtemp(prefix="zen-serve-state-")
    env["XDG_STATE_HOME"] = state_dir
    env["TMPDIR"] = state_dir
    env["OPENCODE_DB"] = ":memory:"
    _ = env.pop("OPENCODE_BIN", None)
    env["OPENCODE_SERVER_PASSWORD"] = secrets.token_hex(16)
    return env


def _is_native_opencode_bin(path: str) -> bool:
    """Нативный бинарь opencode, а не текстовый фейк со shebang."""
    if SERVE_TEST_ELIGIBLE:
        return True
    try:
        with Path(path).open("rb") as fh:
            head = fh.read(4)
    except OSError:
        return False
    if head.startswith(b"#!"):
        return False
    return head[:2] in (b"\xcf\xfa", b"\xfa\xed") or head.startswith(b"\x7fELF")


def _select_transport(res: _Resilience | None = None) -> str:
    """Выбор транспорта: serve или run по приоритетам kill-switch."""
    transport = os.environ.get("OPENCODE_ZEN_BRIDGE_TRANSPORT", "auto").strip().lower()
    override = (
        os.environ.get("OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED", "").strip().lower()
    )
    if transport == "run" or override in ("0", "false", "no", "off"):
        return "run"
    disable_raw = os.environ.get(
        "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE",
        "~/.dsh/bridges/opencode-zen-bridge/disable-serve",
    )
    try:
        if Path(disable_raw).expanduser().exists():
            return "run"
    except OSError:
        return "run"
    health = res.serve_health if res is not None else None
    if transport == "serve":
        return "serve"
    if transport != "auto":
        return "run"
    if health is not None and health.is_degraded():
        return "run"
    enabled = override in ("1", "true", "yes", "on") or _read_dynamic_config_enabled()
    if not enabled:
        return "run"
    return "serve" if _is_native_opencode_bin(OPENCODE_BIN) else "run"


def _map_serve_event(
    event: dict[str, object],
) -> tuple[str, dict[str, object]] | None:
    """Wire-событие serve v2.1.2 -> канонический кортеж legacy-пути или None для служебных."""
    event = _as_dict(_combine_surrogates(event))
    etype_obj = event.get("type")
    etype = etype_obj if isinstance(etype_obj, str) else ""
    data = _as_dict(event.get("data"))
    if etype == "server.connected":
        return etype, data
    if not data:
        # Служебные/неизвестные события serve без данных игнорируются, а не рвут попытку.
        if etype in (
            "server.heartbeat",
            "integration.updated",
            "session.idle",
            "server.connected",
        ) or not etype.startswith("session."):
            return None
        raise ServeProtocolError("invalid_serve_event: data")
    if etype in ("session.reasoning.delta", "session.text.delta"):
        delta = data.get("delta")
        session_id = data.get("sessionID")
        if (
            not isinstance(delta, str)
            or not isinstance(session_id, str)
            or not session_id
        ):
            raise ServeProtocolError("invalid_serve_event: delta")
        if etype.startswith("session.reasoning"):
            return "reasoning", {"reasoning_content": delta, "sessionID": session_id}
        return "text", {"content": delta, "sessionID": session_id}
    if etype == "session.step.ended":
        tokens = _as_dict(data.get("tokens"))
        cache = _as_dict(tokens.get("cache"))
        read_obj = cache.get("read")

        def _valid_token_int(value: object) -> bool:
            return isinstance(value, int) and not isinstance(value, bool) and value >= 0

        if not tokens or any(
            value is not None and not _valid_token_int(value)
            for value in (
                tokens.get("input"),
                tokens.get("output"),
                tokens.get("reasoning"),
                read_obj,
            )
        ):
            raise ServeProtocolError("invalid token count in step_finish")
        out: dict[str, object] = {}
        for key in ("input", "output", "reasoning"):
            value = tokens.get(key)
            if not _valid_token_int(value):
                raise ServeProtocolError(f"invalid_serve_event: tokens.{key}")
            out[key] = value
        out["cached"] = read_obj
        sid_obj = data.get("sessionID")
        if isinstance(sid_obj, str):
            out["sessionID"] = sid_obj
        return "step_finish", out
    if etype in ("session.execution.failed", "session.step.failed"):
        err = _as_dict(data.get("error"))
        message = err.get("message")
        if not isinstance(message, str):
            raise ServeProtocolError("invalid_serve_event: error")
        status_obj = err.get("status")
        status: int | None = (
            status_obj
            if isinstance(status_obj, int) and 100 <= status_obj <= 599
            else None
        )
        if status is None:
            err_type_obj = err.get("type")
            err_type = err_type_obj if isinstance(err_type_obj, str) else ""
            status = {"provider.free-limit": 429, "provider.auth": 401}.get(err_type)
        err_out: dict[str, object] = {"statusCode": status, "message": message}
        sid_err = data.get("sessionID")
        if isinstance(sid_err, str):
            err_out["sessionID"] = sid_err
        return "error", err_out
    if etype == "permission.asked":
        return "permission", data
    if etype == "form.created":
        return "form_created", data
    if etype.startswith("session.tool."):
        return "tool_event", data
    return etype, data


parse_serve_event = _map_serve_event


def _variant_for(model_id: str, effort: str) -> str:
    """`#variant` для модели: только если модель их поддерживает и значение допустимо (иначе CLI: exit 1)."""
    meta = ALLOWED_MODELS.get(model_id, {})
    if not effort or not meta.get("supports_variant", False):
        return ""
    values = meta.get("effort_values")
    if values and effort not in values:
        _log(
            f"WARN variant {effort!r} is not in effort_values of {model_id}; suffix dropped"
        )
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


def _is_retryable_failure(
    rc: int | None, err_text: str, provider_status: int | None, had_output: bool
) -> bool:
    """Прогон без какого-либо вывода и с rc != 0 — транзиторный отказ CLI (повторяем).

    Не повторяем: был вывод; процесс убит нами/таймаутом (rc < 0 или None);
    провайдер вернул детерминированный отказ (400/401/402/403/404/422).
    """
    if had_output or rc is None or rc <= 0:
        return False
    return provider_status not in _FATAL_HTTP


def _error_payload(message: str, detail: str = "") -> dict[str, object]:
    """Тело OpenAI-style ошибки (SSE-чанк `{"error":…}` и non-stream 502)."""
    err: dict[str, object] = {
        "message": _clean_err(message),
        "type": "proxy_error",
        "code": 502,
    }
    if detail:
        err["detail"] = _clean_err(detail)
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

    def acquire(
        self,
        deadline: float | None = None,
        is_client_gone: Callable[[], bool] | None = None,
    ) -> None:
        wait_until = time.monotonic() + max(0.0, self._wait_s)
        while True:
            now = time.monotonic()
            if (is_client_gone is not None and is_client_gone()) or (
                deadline is not None and now >= deadline
            ):
                return
            remaining = max(
                0.0,
                min(wait_until, deadline if deadline is not None else wait_until) - now,
            )
            if _STARTUP_LOCK.acquire(timeout=min(0.05, remaining)):
                break
            if time.monotonic() >= wait_until:
                _log(
                    f"startup_gate_timeout wait_s={self._wait_s:.1f}, starting without the gate"
                )
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

    def __init__(
        self,
        max_concurrent: int | None = None,
        max_waiters: int | None = None,
        wait_timeout_s: float | None = None,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = MAX_CONCURRENT if max_concurrent is None else max_concurrent
        self._max_waiters = MAX_SLOT_WAITERS if max_waiters is None else max_waiters
        self._wait_timeout_s = (
            SLOT_WAIT_TIMEOUT_S if wait_timeout_s is None else wait_timeout_s
        )
        self._clock = clock_fn
        self._cond = threading.Condition(threading.Lock())
        self.in_use = 0
        self.waiters = 0

    def acquire_ex(self, timeout: float | None = None) -> str:
        """ "ok" | "timeout" | "overflow" (все слоты заняты и очередь ждущих полна)."""
        wait = (
            self._wait_timeout_s
            if timeout is None
            else min(timeout, self._wait_timeout_s)
        )
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

    def __init__(
        self,
        rate_rps: float = 1.0,
        burst: float = 1.0,
        clock_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._rate = max(rate_rps, 1e-9)
        self._burst = max(burst, 1.0)
        self._clock = clock_fn
        self._sleep = sleep_fn
        self._lock = threading.Lock()
        self._tokens = self._burst
        self._last = clock_fn()

    def acquire(
        self,
        max_wait_s: float | None = None,
        deadline: float | None = None,
        is_client_gone: Callable[[], bool] | None = None,
    ) -> bool:
        if (is_client_gone is not None and is_client_gone()) or (
            deadline is not None and self._clock() >= deadline
        ):
            return False
        with self._lock:
            now = self._clock()
            self._tokens = min(
                self._burst, self._tokens + max(0.0, now - self._last) * self._rate
            )
            self._last = now
            wait = max(0.0, (1.0 - self._tokens) / self._rate)
            if max_wait_s is not None and wait > max_wait_s:
                return False
            if deadline is not None and wait >= deadline - now:
                return False
            self._tokens -= 1.0
        if deadline is None and is_client_gone is None:
            if wait > 0:
                self._sleep(wait)
            return True
        ready_at = now + wait
        while True:
            now = self._clock()
            if (is_client_gone is not None and is_client_gone()) or (
                deadline is not None and now >= deadline
            ):
                self.refund()
                return False
            if now >= ready_at:
                break
            self._sleep(
                min(
                    0.05,
                    ready_at - now,
                    deadline - now if deadline is not None else 0.05,
                )
            )
        return True

    def refund(self, amount: float = 1.0) -> None:
        """Вернуть резерв, если дочерний процесс не был запущен."""
        with self._lock:
            self._tokens = min(self._burst, self._tokens + amount)


class _RetryBudget:
    """Process-level бюджет повторных запусков: ёмкость `capacity`, +`per_request_refill` за запрос, +`reserve_rps` в секунду."""

    def __init__(
        self,
        capacity: float | None = None,
        per_request_refill: float | None = None,
        reserve_rps: float | None = None,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capacity = RETRY_BUDGET_MAX if capacity is None else capacity
        self._per_request = (
            RETRY_BUDGET_PER_REQUEST
            if per_request_refill is None
            else per_request_refill
        )
        self._reserve_rps = (
            RETRY_BUDGET_RESERVE_RPS if reserve_rps is None else reserve_rps
        )
        self._clock = clock_fn
        self._lock = threading.Lock()
        self.tokens = float(self._capacity)
        self._last = clock_fn()

    def _refill_time(self) -> None:
        now = self._clock()
        self.tokens = min(
            self._capacity, self.tokens + max(0.0, now - self._last) * self._reserve_rps
        )
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

    def __init__(
        self,
        fail_threshold: int | None = None,
        reset_timeout_s: float | None = None,
        clock_fn: Callable[[], float] = time.monotonic,
        rng_fn: Callable[[float, float], float] = random.uniform,
        max_half_open_probes: int = 1,
        log_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._threshold = (
            CB_FAIL_THRESHOLD if fail_threshold is None else fail_threshold
        )
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
            if (
                self._probes >= self._max_probes
                and now - self._probe_started < self._reset_s
            ):
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
                self._say(
                    f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}"
                )


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
        self.serve_health = _ServeHealth()


_DEFAULT_RESILIENCE = _Resilience()
_slots = _DEFAULT_RESILIENCE.slots  # прежнее имя семафора слотов


class _AuxIoBudget:
    """Общий бюджет вспомогательного I/O одного запроса через все попытки (FU-002).

    Считается фактически проведённое время aux-фаз (gate/limiter, spawn/ready,
    control create/prompt до заголовков, подписка до первого SSE, backoff);
    модельный стриминг и cleanup-резерв в бюджет не входят.
    """

    def __init__(
        self,
        budget_s: float | None = None,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._budget_s: float = _AUX_IO_BUDGET_S if budget_s is None else budget_s
        self._clock: Callable[[], float] = clock_fn
        self._spent_s: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    def now_s(self) -> float:
        """Текущее время часов бюджета (точка старта aux-фазы)."""
        return self._clock()

    def spent_s(self) -> float:
        """Фактически потраченное aux-время запроса."""
        with self._lock:
            return self._spent_s

    def remaining_s(self) -> float:
        """Остаток aux-бюджета запроса."""
        return max(0.0, self._budget_s - self.spent_s())

    def exhausted(self) -> bool:
        """Исчерпан ли aux-бюджет: новый I/O и попытки не стартуют."""
        return self.remaining_s() <= 0.0

    def check(self) -> None:
        """Запретить старт нового I/O при исчерпанном бюджете."""
        if self.exhausted():
            raise ServeStartupDeadlineExceeded("aux io budget exhausted")

    def deadline(self, request_deadline: float | None = None) -> float:
        """Дедлайн следующей aux-фазы: не позже запроса и остатка бюджета."""
        phase_deadline = self._clock() + self.remaining_s()
        if request_deadline is None:
            return phase_deadline
        return min(phase_deadline, request_deadline)

    def debit_elapsed(self, started: float) -> None:
        """Списать фактически проведённое время aux-фазы (вызов из finally)."""
        elapsed = max(0.0, self._clock() - started)
        with self._lock:
            self._spent_s = min(self._budget_s, self._spent_s + elapsed)

    def debit_seconds(self, seconds: float) -> None:
        """Списать измеренную длительность aux-фазы в секундах."""
        with self._lock:
            self._spent_s = min(self._budget_s, self._spent_s + max(0.0, seconds))


class _RequestAttempts:
    """Учёт запусков одного HTTP-запроса: потолок MAX_TOTAL_SPAWNS, общий deadline, breaker, Retry Budget, backoff."""

    def __init__(
        self,
        res: _Resilience,
        deadline: float,
        max_total: int | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        rng_fn: Callable[[float, float], float] = random.uniform,
        use_breaker: bool = True,
    ) -> None:
        self.res = res
        self.deadline = deadline
        self.use_breaker = (
            use_breaker  # False: прямой Google-маршрут без `opencode run`
        )
        self.max_total = MAX_TOTAL_SPAWNS if max_total is None else max_total
        self.total_spawns = 0
        self.retries = 0
        self.signal = 0
        self.exit_reason = ""
        self._pending_failure = False
        self._sleep = sleep_fn
        self._rng = rng_fn
        self.aux_budget: _AuxIoBudget = _AuxIoBudget()
        res.retry_budget.on_request()

    def note_spawn(self) -> None:
        self.total_spawns += 1

    def can_spawn(self) -> bool:
        """Можно ли ещё запускать: суммарный потолок спавнов на запрос."""
        return (
            self.total_spawns < MAX_TOTAL_SPAWNS and self.total_spawns < self.max_total
        )

    def remaining_s(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def begin_attempt(self) -> bool:
        """Первичный запуск: потолок, deadline и Circuit Breaker (в HALF_OPEN резервирует единственную пробу)."""
        return (
            self.total_spawns < self.max_total
            and time.monotonic() < self.deadline
            and (not self.use_breaker or self.res.breaker.allow())
        )

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
        if self.aux_budget.exhausted():
            _log(f"retry denied ({reason}): aux io budget exhausted")
            return False
        if self.use_breaker and self.res.breaker.is_blocking():
            _log(f"retry denied ({reason}): upstream circuit open")
            return False
        if charge_budget and not self.res.retry_budget.try_acquire_retry():
            _log(f"retry denied ({reason}): retry budget exhausted")
            return False
        self.retries += 1
        delay = (
            _retry_backoff_s(self.retries, self._rng)
            if FAIL_RETRY_BACKOFF_S > 0
            else 0.0
        )
        delay = min(delay, self.remaining_s(), self.aux_budget.remaining_s())
        if delay > 0:
            aux_started = self.aux_budget.now_s()
            try:
                self._sleep(delay)
            finally:
                self.aux_budget.debit_elapsed(aux_started)
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
            return current[len(prefix) :]
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
        return current[len(prefix) :]
    return current


def _new_exit_state() -> dict[str, Any]:
    return {
        "t0": time.monotonic(),
        "mode": "",
        "model": "",
        "status": 0,
        "exit_reason": "",
        "attempts": None,
        "tools": 0,
        "out_chars": 0,
        "rc": None,
        "transport": "none",
        "first_event_ms": None,
        "ttft_ms": None,
        "transport_history": [],
    }


def _log_exit(xs: dict[str, Any]) -> None:
    """O-EXIT/v1: одна структурная строка bridge.log на каждый выход Handler.do_POST."""
    attempts_obj = xs.get("attempts")
    attempts_t = attempts_obj if isinstance(attempts_obj, _RequestAttempts) else None
    status_obj = xs.get("status")
    status = status_obj if isinstance(status_obj, int) else 0
    reason_obj = xs.get("exit_reason")
    reason = (reason_obj if isinstance(reason_obj, str) and reason_obj else "") or (
        "ok" if status == 200 else (f"http_{status}" if status else "client_gone")
    )
    t0_obj = xs.get("t0")
    t0 = t0_obj if isinstance(t0_obj, float) else time.monotonic()
    _log(
        f"O-EXIT/v1 mode={xs.get('mode') or '-'} model={xs.get('model') or '-'} status={status} "
        f"exit_reason={reason} rc={xs.get('rc')} total_spawns={attempts_t.total_spawns if attempts_t else 0} "
        f"retries={attempts_t.retries if attempts_t else 0} signal={attempts_t.signal if attempts_t else 0} "
        f"tools={xs.get('tools') or 0} out_chars={xs.get('out_chars') or 0} "
        f"transport={xs.get('transport') or 'none'} first_event_ms={xs.get('first_event_ms')} "
        f"ttft_ms={xs.get('ttft_ms')} transport_history={xs.get('transport_history') or []} "
        f"duration_s={time.monotonic() - t0:.2f}"
    )


def _parent_lstart(deadline: float | None = None) -> str:
    """lstart родителя дляargv помощника."""
    try:
        out = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(os.getpid())],
            capture_output=True,
            text=True,
            timeout=2.0
            if deadline is None
            else max(0.001, min(2.0, deadline - time.monotonic())),
        )
        return out.stdout.strip() or str(int(time.time()))
    except (OSError, subprocess.SubprocessError):
        return str(int(time.time()))


def _lsof_listener_pid(port: int, deadline: float | None = None) -> int | None:
    """PID слушателя порта одним вызовом lsof."""
    _LSOF_CALLS.append(port)
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            timeout=2.0
            if deadline is None
            else max(0.001, min(2.0, deadline - time.monotonic())),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.stdout.splitlines():
        if line.strip().isdecimal():
            return int(line.strip())
    return None


def _check_serve_start(
    deadline: float | None, is_client_gone: Callable[[], bool] | None
) -> None:
    """Отмена и общий дедлайн не означают недоступность транспорта."""
    if is_client_gone is not None and is_client_gone():
        raise ServeClientDisconnect("client disconnected before serve spawn")
    if deadline is not None and time.monotonic() >= deadline:
        raise ServeStartupDeadlineExceeded("deadline expired before serve spawn")


def _watch_serve_connection(
    conn: http.client.HTTPConnection,
    deadline: float | None,
    is_client_gone: Callable[[], bool] | None,
    phase_socket: list[socket.socket | None],
) -> threading.Event:
    """Прервать даже капающие HTTP-заголовки по абсолютному сроку или отмене."""
    stopped = threading.Event()

    def watch() -> None:
        while not stopped.wait(0.01):
            if (deadline is not None and time.monotonic() >= deadline) or (
                is_client_gone is not None and is_client_gone()
            ):
                sock = conn.sock or phase_socket[0]
                if sock is not None:
                    try:
                        _ = sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    try:
                        _ = sock.close()
                    except OSError:
                        pass
                return

    if deadline is not None or is_client_gone is not None:
        threading.Thread(target=watch, daemon=True).start()
    return stopped


def _serve_http(
    port: int,
    password: str,
    method: str,
    path: str,
    body: dict[str, object] | None = None,
    timeout: float = 3.0,
    conn: http.client.HTTPConnection | None = None,
    on_headers: Callable[[int], None] | None = None,
    deadline: float | None = None,
    is_client_gone: Callable[[], bool] | None = None,
    skip_body: bool = False,
) -> tuple[int, dict[str, object]]:
    """Один HTTP-вызов serve с Basic-авторизацией без прокси."""
    own_conn = conn is None
    active_conn = (
        conn
        if conn is not None
        else http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    )
    if conn is not None:
        conn.timeout = timeout
        if conn.sock is not None:
            _ = conn.sock.settimeout(timeout)

    phase_socket: list[socket.socket | None] = [None]
    stopped = _watch_serve_connection(
        active_conn, deadline, is_client_gone, phase_socket
    )

    def check_phase() -> None:
        """Ограничить следующую фазу оставшимся бюджетом и проверить отмену."""
        if is_client_gone is not None and is_client_gone():
            raise BrokenPipeError(errno.EPIPE, "client gone")
        remaining = (
            timeout if deadline is None else min(timeout, deadline - time.monotonic())
        )
        if remaining <= 0:
            active_conn.close()
            raise TimeoutError("serve http deadline expired")
        active_conn.timeout = remaining
        connected_socket = active_conn.sock or phase_socket[0]
        if connected_socket is not None and connected_socket.fileno() >= 0:
            _ = connected_socket.settimeout(remaining)

    try:
        check_phase()
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        auth = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("ascii")
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        active_conn.request(method, path, payload, headers)
        # HTTP/1.0 отделяет сокет от conn после заголовков; бюджет тела остаётся обязательным.
        phase_socket[0] = active_conn.sock
        check_phase()
        try:
            resp = active_conn.getresponse()
        except (AttributeError, ValueError):
            check_phase()
            raise
        if on_headers is not None:
            on_headers(int(resp.status))
        if skip_body:
            active_conn.close()
            resp.close()
            return int(resp.status), {}
        raw = bytearray()
        while not resp.isclosed():
            check_phase()
            try:
                chunk = resp.read1(65536)
            except (AttributeError, ValueError):
                check_phase()
                raise
            check_phase()
            if not chunk:
                break
            raw.extend(chunk)
            if len(raw) > _MAX_SERVE_HTTP_BODY_BYTES:
                active_conn.close()
                resp.close()
                raise ServeProtocolError("serve http response body exceeds max bytes")
        parsed: dict[str, object] = {}
        if raw:
            parsed = _as_dict(_loads_object(raw.decode("utf-8", "replace")))
        return int(resp.status), parsed
    finally:
        stopped.set()
        if own_conn:
            active_conn.close()


class _ServeLease:
    """Владение деревом helper->serve одной попытки."""

    def __init__(
        self,
        helper: subprocess.Popen[str],
        serve_pid: int,
        pgid: int,
        lifeline_w: int,
        lease_dir: Path,
        attempt_id: str,
        state_dir: str,
        port: int = 0,
    ) -> None:
        self.helper = helper
        self.serve_pid = serve_pid
        self.pgid = pgid
        self.lifeline_w = lifeline_w
        self.lease_dir = lease_dir
        self.attempt_id = attempt_id
        self.state_dir = state_dir
        self.port = port
        self._closed = False
        self._lock = threading.Lock()
        self.stderr_tail: bytearray = bytearray()

    def cleanup(self) -> None:
        """Идемпотентная уборка только своей группы процессов."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            os.close(self.lifeline_w)
        except OSError:
            pass
        _deadline = time.monotonic() + 4.0
        if self.helper.poll() is None or _pid_alive(-self.pgid):
            try:
                if os.getpgid(self.pgid) == self.pgid:
                    os.killpg(self.pgid, signal.SIGTERM)
            except OSError:
                pass
            while time.monotonic() < _deadline:
                if not _pid_alive(-self.pgid) and self.helper.poll() is not None:
                    break
                time.sleep(0.05)
            if _pid_alive(-self.pgid) or self.helper.poll() is None:
                try:
                    os.killpg(self.pgid, signal.SIGKILL)
                except OSError:
                    pass
                # Отдельное окно подтверждения смерти группы после SIGKILL (бюджет AC-011 <= 7 с).
                _deadline = time.monotonic() + 2.0
                while time.monotonic() < _deadline:
                    if not _pid_alive(-self.pgid) and self.helper.poll() is not None:
                        break
                    time.sleep(0.05)
            try:
                _ = self.helper.wait(timeout=max(0.1, _deadline - time.monotonic()))
            except (OSError, subprocess.SubprocessError):
                pass
        for stream in (self.helper.stdout, self.helper.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        if not _pid_alive(-self.pgid):
            try:
                (self.lease_dir / f"lease-{self.attempt_id}.json").unlink()
            except OSError:
                pass
            if self.port:
                with _PORT_ALLOC_LOCK:
                    _ACTIVE_SERVE_PORTS.discard(self.port)
        if self.state_dir and Path(self.state_dir).name.startswith("zen-serve-state-"):
            shutil.rmtree(self.state_dir, ignore_errors=True)


def _ensure_lease_dir(lease_dir: Path) -> None:
    """Каталог lease: свой uid, не симлинк, права 0700."""
    lease_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        info = os.lstat(lease_dir)
    except OSError as exc:
        raise ServeUnavailable(f"lease dir unavailable: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
        raise ServeUnavailable("lease dir ownership check failed")
    try:
        os.chmod(lease_dir, 0o700)
    except OSError:
        pass


def _discard_spawn_leftovers(port: int, lifeline_w: int, state_dir: str) -> None:
    """Освободить ресурсы неудачного старта serve до создания _ServeLease."""
    if lifeline_w >= 0:
        try:
            os.close(lifeline_w)
        except OSError:
            pass
    if port:
        with _PORT_ALLOC_LOCK:
            _ACTIVE_SERVE_PORTS.discard(port)
    if state_dir and Path(state_dir).name.startswith("zen-serve-state-"):
        shutil.rmtree(state_dir, ignore_errors=True)


def _spawn_serve(
    attempt_id: str,
    serve_env: dict[str, str],
    deadline: float | None = None,
    is_client_gone: Callable[[], bool] | None = None,
) -> tuple[_ServeLease, int, str]:
    """Запуск helper->serve, проверка слушателя и рукопожатия."""
    port = 0
    lifeline_w = -1
    lease: _ServeLease | None = None
    state_dir = serve_env.get("XDG_STATE_HOME", "")
    try:
        _check_serve_start(deadline, is_client_gone)
        lease_dir = Path(LEASE_DIR)
        _ensure_lease_dir(lease_dir)
        with _PORT_ALLOC_LOCK:
            for candidate in range(20000 + (os.getpid() % 20000), 60000):
                if candidate in _ACTIVE_SERVE_PORTS:
                    continue
                probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    probe.bind(("127.0.0.1", candidate))
                    port = candidate
                    _ACTIVE_SERVE_PORTS.add(candidate)
                    break
                except OSError:
                    continue
                finally:
                    probe.close()
        if not port:
            raise ServeUnavailable("no free serve port")
        password = serve_env.get("OPENCODE_SERVER_PASSWORD", "")
        parent_lstart = _parent_lstart(deadline)
        lifeline_r, lifeline_w = os.pipe()
        try:
            _check_serve_start(deadline, is_client_gone)
            helper: subprocess.Popen[str] = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    str(Path(__file__).resolve()),
                    "--serve-helper",
                    attempt_id,
                    str(port),
                    str(OPENCODE_BIN),
                    str(lease_dir),
                    str(os.getpid()),
                    parent_lstart,
                ],
                stdin=lifeline_r,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                close_fds=True,
                env=serve_env,
                text=True,
            )
        finally:
            try:
                os.close(lifeline_r)
            except OSError:
                pass
        lease = _ServeLease(
            helper,
            0,
            helper.pid,
            lifeline_w,
            lease_dir,
            attempt_id,
            state_dir,
            port,
        )
        stderr_tail = lease.stderr_tail

        def _drain_helper_stderr() -> None:
            """Дренировать пайп до handshake порциями, ограничивая хвост по байтам."""
            assert helper.stderr is not None
            try:
                while True:
                    chunk = os.read(helper.stderr.fileno(), _STDERR_CHUNK_READ_BYTES)
                    if not chunk:
                        return
                    stderr_tail[:] = (stderr_tail + chunk)[-_MAX_STDERR_TAIL_BYTES:]
            except (OSError, ValueError):
                return

        threading.Thread(target=_drain_helper_stderr, daemon=True).start()
        assert helper.stdout is not None
        out_fd = helper.stdout.fileno()
        _hs_deadline = (
            min(time.monotonic() + 3.0, deadline)
            if deadline is not None
            else time.monotonic() + 3.0
        )
        line_bytes = b""
        while not line_bytes.endswith(b"\n"):
            _check_serve_start(deadline, is_client_gone)
            if time.monotonic() >= _hs_deadline:
                raise ServeUnavailable("serve helper handshake timeout")
            _ready, _w2, _x2 = select.select(
                [out_fd], [], [], min(0.05, max(0.0, _hs_deadline - time.monotonic()))
            )
            if not _ready:
                continue
            chunk_b = os.read(out_fd, 1)
            if not chunk_b:
                break
            line_bytes += chunk_b
        line = line_bytes.decode("utf-8", "replace")
        handshake = _as_dict(_loads_object(line)) if line else {}
        serve_pid = _as_int(handshake.get("serve_pid"))
        pgid = _as_int(handshake.get("pgid"))
        lease.serve_pid = serve_pid
        if not serve_pid or pgid != helper.pid or helper.poll() is not None:
            raise ServeUnavailable("serve ownership handshake mismatch")
        _check_serve_start(deadline, is_client_gone)
        _listener_deadline = (
            min(time.monotonic() + 3.0, deadline)
            if deadline is not None
            else time.monotonic() + 3.0
        )
        listener_pid = _lsof_listener_pid(port, _listener_deadline)
        while (
            listener_pid is None
            and time.monotonic() < _listener_deadline
            and helper.poll() is None
        ):
            _check_serve_start(deadline, is_client_gone)
            time.sleep(min(0.05, max(0.0, _listener_deadline - time.monotonic())))
            listener_pid = _lsof_listener_pid(port, _listener_deadline)
        _check_serve_start(deadline, is_client_gone)
        if not (
            listener_pid is not None
            and listener_pid == serve_pid
            and _pid_pgid(listener_pid) == pgid
            and helper.poll() is None
        ):
            raise ServeUnavailable(
                "listener ownership verification failed: foreign listener on serve port"
            )
        return lease, port, password
    except BaseException as exc:
        if lease is not None:
            lease.cleanup()
        else:
            _discard_spawn_leftovers(port, lifeline_w, state_dir)
        if isinstance(exc, ServeUnavailable):
            raise
        if isinstance(exc, (OSError, ValueError, subprocess.SubprocessError)):
            raise ServeUnavailable(f"serve spawn os error: {exc}") from exc
        raise


def _startup_reaper(lease_dir: Path | None = None) -> int:
    """Убрать осиротевшие lease мёртвого родителя при старте моста."""
    target = Path(LEASE_DIR) if lease_dir is None else lease_dir
    removed = 0
    try:
        _dir_info = os.lstat(target)
        if stat.S_ISLNK(_dir_info.st_mode) or _dir_info.st_uid != os.getuid():
            return 0
        files = list(target.glob("lease-*.json"))
    except OSError:
        return 0
    for path in files:
        try:
            _file_info = os.lstat(path)
            if stat.S_ISLNK(_file_info.st_mode) or _file_info.st_uid != os.getuid():
                continue
            data = _as_dict(_loads_object(path.read_text("utf-8")))
            parent_pid = _as_int(data.get("parent_pid"))
            helper_pid = _as_int(data.get("helper_pid"))
            pgid = _as_int(data.get("pgid"))
        except (OSError, ValueError, TypeError):
            continue
        if _as_int(data.get("owner_uid")) != os.getuid():
            continue
        # Сверка lstart живого родителя/помощника с lease: переиспользованный PID не трогаем.
        _lstart_ok = True
        for _pid_key, _ts_key in (
            ("parent_pid", "parent_start_ts"),
            ("helper_pid", "helper_lstart"),
        ):
            _pid_v = _as_int(data.get(_pid_key))
            _ts_v = str(data.get(_ts_key) or "")
            if _pid_v > 0 and _ts_v and _pid_alive(_pid_v):
                try:
                    _live = subprocess.run(
                        ["ps", "-o", "lstart=", "-p", str(_pid_v)],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    ).stdout.strip()
                except (OSError, subprocess.SubprocessError):
                    _live = ""
                # helper_lstart записан epoch-секундами, parent_start_ts — lstart: сверяем только lstart-формат.
                if _live and not _ts_v.isdecimal() and _live != _ts_v:
                    if _pid_key == "helper_pid":
                        # PID помощника переиспользован: убивать группу нельзя.
                        helper_pid = 0
                    else:
                        _lstart_ok = False
        if not _lstart_ok:
            continue
        parent_alive = parent_pid > 0 and _pid_alive(parent_pid)
        if parent_alive:
            continue
        if helper_pid > 0 and pgid == helper_pid and _pid_alive(helper_pid):
            try:
                cmd = subprocess.run(
                    ["ps", "-ww", "-o", "command=", "-p", str(helper_pid)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                ).stdout
            except (OSError, subprocess.SubprocessError):
                cmd = ""
            if "--serve-helper" not in cmd:
                continue
            try:
                os.killpg(pgid, signal.SIGTERM)
            except OSError:
                pass
            _reap_deadline = time.monotonic() + 2.0
            while _pid_alive(-pgid) and time.monotonic() < _reap_deadline:
                time.sleep(0.05)
            if _pid_alive(-pgid):
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass
                while _pid_alive(-pgid) and time.monotonic() < _reap_deadline + 2.0:
                    time.sleep(0.05)
        if pgid <= 0 or not _pid_alive(-pgid):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def _pid_alive(pid: int) -> bool:
    """Жив ли процесс; отрицательный pid — проверка группы через kill(-pgid, 0)."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pid_pgid(pid: int) -> int:
    """PGID процесса или -1 при ошибке."""
    try:
        return os.getpgid(pid)
    except OSError:
        return -1


_find_listener_pid = _lsof_listener_pid


class _ToolItem(TypedDict):
    """Накопленный native вызов serve."""

    name: str
    text: str
    input: dict[str, object] | None


class _ServeToolState:
    """Накопление native tool lifecycle serve до полного ввода."""

    def __init__(self) -> None:
        self.tools: dict[str, _ToolItem] = {}
        self.emitted: set[str] = set()

    def feed(self, data: dict[str, object]) -> None:
        """Запомнить фрагмент native вызова."""
        call_id = str(data.get("id") or "")
        if not call_id:
            return
        if call_id not in self.tools and len(self.tools) >= _MAX_SERVE_NATIVE_TOOLS:
            raise ServeProtocolError("serve native tool calls count exceeded cap")
        item = self.tools.setdefault(call_id, {"name": "", "text": "", "input": None})
        name = data.get("name")
        if isinstance(name, str) and name:
            item["name"] = name
        text_value = data.get("text")
        if isinstance(text_value, str):
            item["text"] = text_value
        input_value = data.get("input")
        if isinstance(input_value, dict):
            item["input"] = _as_dict(input_value)

    def complete(
        self, call_id: str, event_type: str = ""
    ) -> tuple[str, dict[str, object]] | None:
        """Готовый вызов из called.input или input.ended.text; статус — из типа события."""
        if call_id in self.emitted:
            return None
        item = self.tools.get(call_id)
        if item is None or not item["name"]:
            return None
        args = item["input"]
        if not isinstance(args, dict):
            text_value = item["text"]
            try:
                parsed: object = json.loads(text_value) if text_value else None
            except ValueError:
                return None
            if not isinstance(parsed, dict):
                return None
            args = _as_dict(_combine_surrogates(parsed))
        self.emitted.add(call_id)
        _status = (
            "completed"
            if any(
                k in event_type for k in ("completed", "succeeded", "success", "called")
            )
            else "error"
        )
        return "tool_use", {
            "part": {"tool": item["name"], "state": {"input": args, "status": _status}},
            "call_id": call_id,
        }


_ToolInputAccumulator = _ServeToolState


def _native_call_as_dsh(
    payload: dict[str, object], tools: list[dict[str, object]] | None
) -> list[dict[str, object]]:
    """Native serve-вызов в DSH-вызов через канонический _native_to_tool_calls (fit_args + multiedit)."""
    part = _as_dict(payload.get("part"))
    state = _as_dict(part.get("state"))
    tool = part.get("tool")
    if not isinstance(tool, str) or not tool:
        return []
    args = _as_dict(state.get("input"))
    return _native_to_tool_calls(tool, args, list(tools or []))


def _open_serve_events(
    port: int,
    password: str,
    deadline: float,
    is_client_gone: Callable[[], bool] | None,
) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
    """Открыть подписку с общим дедлайном, прерывая даже капающие заголовки."""
    _check_serve_start(deadline, is_client_gone)
    sub_deadline = min(deadline, time.monotonic() + float(FIRST_EVENT_TIMEOUT_S))
    conn = http.client.HTTPConnection(
        "127.0.0.1",
        port,
        timeout=max(
            0.05, min(float(FIRST_EVENT_TIMEOUT_S), deadline - time.monotonic())
        ),
    )
    auth = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("ascii")
    phase_socket: list[socket.socket | None] = [None]
    stopped = _watch_serve_connection(conn, sub_deadline, is_client_gone, phase_socket)
    try:
        conn.request(
            "GET",
            "/api/event",
            None,
            {"Authorization": f"Basic {auth}", "Accept": "text/event-stream"},
        )
        phase_socket[0] = conn.sock
        _check_serve_start(sub_deadline, is_client_gone)
        response = conn.getresponse()
        _check_serve_start(sub_deadline, is_client_gone)
        if response.status in (400, 401, 403, 404, 422):
            raise ServeSecurityError(f"serve event HTTP {response.status}")
        if response.status != 200:
            raise ServeUnavailable(f"serve event HTTP {response.status}")
        # После заголовков паузы SSE контролирует цикл попытки, включая HTTP/1.0 с отделённым сокетом.
        if phase_socket[0] is not None:
            _ = phase_socket[0].settimeout(None)
        return conn, response
    except (ServeStartupDeadlineExceeded, OSError, http.client.HTTPException) as exc:
        conn.close()
        _check_serve_start(deadline, is_client_gone)
        if time.monotonic() >= sub_deadline:
            raise ServeUnavailable("serve event subscribe timeout") from exc
        raise
    except BaseException:
        conn.close()
        raise
    finally:
        stopped.set()


def _cleanup_serve_attempt(
    lease: _ServeLease,
    port: int,
    password: str,
    session_id: str,
    sse_conn: http.client.HTTPConnection | None,
    control_conn: http.client.HTTPConnection | None,
    stop_event: threading.Event | None,
    reader_thread: threading.Thread | None,
    prompt_thread: threading.Thread | None,
) -> None:
    """Общий короткий бюджет потоков и HTTP перед обязательной уборкой группы."""
    cleanup_deadline = time.monotonic() + 0.45
    if stop_event is not None:
        stop_event.set()
    if sse_conn is not None:
        if sse_conn.sock is not None:
            try:
                _ = sse_conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        try:
            sse_conn.close()
        except OSError:
            pass
    try:
        for thread in (reader_thread, prompt_thread):
            if thread is not None:
                thread.join(
                    timeout=min(0.2, max(0.0, cleanup_deadline - time.monotonic()))
                )
        if session_id:
            for method, path in (
                ("POST", f"/api/session/{session_id}/interrupt"),
                ("DELETE", f"/api/session/{session_id}"),
            ):
                try:
                    _ = _serve_http(
                        port,
                        password,
                        method,
                        path,
                        timeout=0.25,
                        deadline=cleanup_deadline,
                        skip_body=True,
                    )
                except (OSError, http.client.HTTPException):
                    pass
        if control_conn is not None:
            try:
                control_conn.close()
            except OSError:
                pass
    finally:
        lease.cleanup()


def _serve_attempt_error_reason(
    exc: Exception,
    deadline: float,
    is_client_gone: Callable[[], bool] | None,
    delivered: bool,
) -> str:
    """Отличить отмену и протокольный отказ от допустимого pre-prompt fallback."""
    if is_client_gone is not None and is_client_gone():
        return "client_gone"
    if time.monotonic() >= deadline:
        return "timeout"
    if isinstance(exc, ServeProtocolError):
        return "invalid_serve_event"
    if delivered:
        return "prompt_error"
    raise ServeUnavailable(f"serve startup failed: {exc}") from exc


def _drain_serve_step_usage(
    events: queue.Queue[dict[str, object] | None],
    session_id: str,
    assistant_message_id: object,
    deadline: float,
    usage: dict[str, int],
    tool_state: _ServeToolState,
    result: _ServeResult,
    on_tool: Callable[[dict[str, object]], None],
    release_event: Callable[[dict[str, object]], None],
    *,
    attempt_deadline: float | None = None,
    is_client_gone: Callable[[], bool] | None = None,
    pending_calls: list[dict[str, object]] | None = None,
    ctrl_http: Callable[
        [str, str, dict[str, object] | None], tuple[int, dict[str, object]]
    ]
    | None = None,
    reasoning_cb: Callable[[str], None] | None = None,
    text_cb: Callable[[str], None] | None = None,
    emulate_tools: bool = False,
    accumulated_bytes: list[int] | None = None,
    t0: float = 0.0,
) -> bool:
    """Дочитать все события шага до подтверждённого конца того же шага.

    Управляющие события и дельты обрабатываются как в основном цикле;
    готовые native вызовы складываются в `pending_calls` без публикации.
    """
    pending: list[dict[str, object]] = (
        pending_calls if pending_calls is not None else []
    )

    def _check_bytes(event_kind: str, payload: dict[str, object]) -> None:
        """Проверить байтовый бюджет с учётом накопленного и tool_state."""
        base = accumulated_bytes[0] if accumulated_bytes is not None else 0
        updated = _serve_accumulated_bytes(base, event_kind, payload, tool_state)
        if accumulated_bytes is not None:
            accumulated_bytes[0] = updated

    def _ctrl_quiet(path: str) -> None:
        """Best-effort управляющий вызов безопасности без маскировки итога дренажа."""
        if ctrl_http is None:
            return
        try:
            _ = ctrl_http("POST", path, None)
        except (
            OSError,
            http.client.HTTPException,
            ServeUnavailable,
            ServeProtocolError,
            ServeClientDisconnect,
            ServeStartupDeadlineExceeded,
        ):
            pass

    hard_deadline = attempt_deadline if attempt_deadline is not None else deadline
    wait_deadline = min(hard_deadline, deadline)
    while time.monotonic() < wait_deadline:
        if is_client_gone is not None and is_client_gone():
            raise ServeClientDisconnect("client disconnected")
        slice_timeout = min(0.05, max(0.0, wait_deadline - time.monotonic()))
        try:
            event = events.get(timeout=slice_timeout)
        except queue.Empty:
            if time.monotonic() >= wait_deadline:
                return False
            continue
        if event is None:
            return False
        release_event(event)
        if is_client_gone is not None and is_client_gone():
            raise ServeClientDisconnect("client disconnected")
        event_type = str(event.get("type") or "")
        if event_type == "__invalid_json__":
            raise ServeProtocolError("invalid event while draining tool step")
        data = _as_dict(event.get("data"))
        # form.created: до верхнего sessionID-фильтра и до разбора схемы события.
        if event_type == "form.created":
            form = _as_dict(data.get("form"))
            form_session = form.get("sessionID") or data.get("sessionID")
            if form_session != session_id:
                continue
            form_id = form.get("id") or data.get("id")
            if isinstance(form_id, str) and form_id:
                _ctrl_quiet(f"/api/session/{session_id}/form/{form_id}/cancel")
            _ctrl_quiet(f"/api/session/{session_id}/interrupt")
            raise ServeSecurityError(
                "serve requested interactive form during tool drain"
            )
        ev_msg_id = data.get("assistantMessageID")
        ev_sid = data.get("sessionID")
        sid_optional = ev_sid is None and event_type in (
            "permission.asked",
            "session.execution.failed",
            "session.step.failed",
        )
        if (ev_sid != session_id and not sid_optional) or (
            assistant_message_id and ev_msg_id and ev_msg_id != assistant_message_id
        ):
            continue
        mapped = _map_serve_event(event)
        if mapped is None:
            continue
        mapped_kind, payload = mapped
        if attempt_deadline is not None:
            wait_deadline = min(
                hard_deadline,
                max(
                    wait_deadline,
                    time.monotonic()
                    + min(_STEP_DRAIN_WINDOW_S, float(STALL_TIMEOUT_S)),
                ),
            )
        if mapped_kind == "permission":
            request_id = str(payload.get("id") or "")
            reject_failed = ctrl_http is None
            if ctrl_http is not None:
                try:
                    status, _body = ctrl_http(
                        "POST",
                        f"/api/session/{session_id}/permission/{request_id}/reply",
                        {"decision": "reject"},
                    )
                    reject_failed = status >= 300
                except (
                    OSError,
                    http.client.HTTPException,
                    ServeUnavailable,
                    ServeProtocolError,
                ):
                    reject_failed = True
            if reject_failed:
                _ctrl_quiet(f"/api/session/{session_id}/interrupt")
                raise ServeSecurityError("permission reject failed")
            continue
        if mapped_kind == "error":
            result["error"] = payload
            result["transient_error"] = _is_transient_stream_error(payload)
            result["terminal"] = "failed"
            return False
        if mapped_kind in ("reasoning", "text"):
            _check_bytes(mapped_kind, payload)
            if mapped_kind == "reasoning":
                text_value = str(payload.get("reasoning_content") or "")
                if text_value:
                    if result["first_token_at"] is None and t0:
                        result["first_token_at"] = time.monotonic()
                        result["ttft_ms"] = int(
                            ((result["first_token_at"] or 0.0) - t0) * 1000
                        )
                    result["reasonings"].append(text_value)
                    if reasoning_cb is not None:
                        reasoning_cb(text_value)
            else:
                text_value = str(payload.get("content") or "")
                if text_value:
                    if result["first_token_at"] is None and t0:
                        result["first_token_at"] = time.monotonic()
                        result["ttft_ms"] = int(
                            ((result["first_token_at"] or 0.0) - t0) * 1000
                        )
                    result["texts"].append(text_value)
                    if text_cb is not None:
                        text_cb(text_value)
            continue
        if mapped_kind == "tool_event":
            if not assistant_message_id and ev_msg_id:
                assistant_message_id = ev_msg_id
            tool_state.feed(payload)
            _check_bytes("tool_event", {})
            if event_type in (
                "session.tool.called",
                "session.tool.failed",
                "session.tool.success",
            ):
                done = tool_state.complete(str(payload.get("id") or ""), event_type)
                if done is not None:
                    pending.append(done[1])
            continue
        if mapped_kind == "step_finish":
            if result["error"] is not None:
                return False
            for call_id in list(tool_state.tools):
                done = tool_state.complete(call_id, event_type)
                if done is not None:
                    pending.append(done[1])
            for key in ("input", "output", "cached", "reasoning"):
                usage[key] = usage.get(key, 0) + _as_int(payload.get(key))
            if pending_calls is None:
                for call in pending:
                    result["native_calls"].append(call)
                    on_tool(call)
            return True
    return False


def _read_serve_events(
    sse_resp: http.client.HTTPResponse,
    events: queue.Queue[dict[str, object] | None],
    stop_event: threading.Event,
    queued_bytes: list[int],
    queue_bytes_lock: threading.Lock,
    release_event: Callable[[dict[str, object]], None],
) -> None:
    """Читать SSE с ограничением байтов очереди в пределах одной попытки."""

    def _put_event(item: dict[str, object] | None) -> bool:
        """Неблокирующая постановка с проверкой stop_event."""
        while not stop_event.is_set():
            try:
                events.put(item, timeout=0.25)
                return True
            except queue.Full:
                continue
        return False

    def _read() -> None:
        """Читатель SSE в очередь событий; тишина сокета не рвёт поток."""
        try:
            while not stop_event.is_set():
                try:
                    line = sse_resp.readline(_MAX_SSE_LINE_BYTES + 1)
                except (OSError, ValueError, AttributeError, http.client.HTTPException):
                    # Сокет закрыт или сброшен: watchdog главного цикла решает судьбу попытки.
                    break
                if not line:
                    break
                if len(line) > _MAX_SSE_LINE_BYTES:
                    _ = _put_event({"type": "__invalid_json__", "data": {}})
                    break
                text_line = line.decode("utf-8", "replace").strip()
                if not text_line.startswith("data:"):
                    continue
                payload = text_line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    obj: dict[str, object] | None = _loads_serve_object(payload)
                except ServeProtocolError:
                    _ = _put_event({"type": "__invalid_json__", "data": {}})
                    continue
                with queue_bytes_lock:
                    overflow = queued_bytes[0] + len(line) > _MAX_SERVE_QUEUE_BYTES
                    if not overflow:
                        queued_bytes[0] += len(line)
                        obj["_raw_bytes"] = len(line)
                if overflow:
                    _ = _put_event({"type": "__invalid_json__", "data": {}})
                    break
                if not _put_event(obj):
                    release_event(obj)
                    break
        except (OSError, ValueError, AttributeError, http.client.HTTPException):
            pass
        finally:
            _ = _put_event(None)

    _read()


def _serve_step_message_id(
    data: dict[str, object], session_id: str, step_closed: bool, current: str
) -> str:
    """Запомнить ID только открытого шага текущей сессии."""
    msg_id = data.get("assistantMessageID")
    if (
        data.get("sessionID") == session_id
        and not step_closed
        and isinstance(msg_id, str)
        and msg_id
    ):
        return msg_id
    return current


def _serve_tool_state_bytes(tool_state: _ServeToolState) -> int:
    """UTF-8 объём ID, имён, text и сериализованных input native вызовов."""
    total = 0
    for call_id, item in tool_state.tools.items():
        total += len(call_id.encode("utf-8", "replace"))
        total += len(item["name"].encode("utf-8", "replace"))
        total += len(item["text"].encode("utf-8", "replace"))
        args = item["input"]
        if isinstance(args, dict):
            total += len(
                json.dumps(
                    args, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8", "replace")
            )
    return total


def _serve_accumulated_bytes(
    current: int,
    event_type: str,
    payload: dict[str, object],
    tool_state: _ServeToolState | None = None,
) -> int:
    """Учесть общий UTF-8 бюджет reasoning/text и удерживаемого tool_state."""
    if event_type in ("reasoning", "text"):
        text_value = str(
            payload.get("reasoning_content" if event_type == "reasoning" else "content")
            or ""
        )
        current += len(text_value.encode("utf-8", "replace"))
    held = _serve_tool_state_bytes(tool_state) if tool_state is not None else 0
    if current + held > _MAX_SERVE_ACCUMULATED_BYTES:
        raise ServeProtocolError("serve accumulated output exceeded byte cap")
    return current


def _finish_serve_tool_step(
    events: queue.Queue[dict[str, object] | None],
    session_id: str,
    assistant_message_id: object,
    deadline: float,
    tool_state: _ServeToolState,
    result: _ServeResult,
    on_tool: Callable[[dict[str, object]], None],
    release_event: Callable[[dict[str, object]], None],
    *,
    attempt_deadline: float | None = None,
    is_client_gone: Callable[[], bool] | None = None,
    pending_calls: list[dict[str, object]] | None = None,
    ctrl_http: Callable[
        [str, str, dict[str, object] | None], tuple[int, dict[str, object]]
    ]
    | None = None,
    reasoning_cb: Callable[[str], None] | None = None,
    text_cb: Callable[[str], None] | None = None,
    emulate_tools: bool = False,
    accumulated_bytes: list[int] | None = None,
    t0: float = 0.0,
) -> bool:
    """Закрыть инструментальный шаг только после подтверждённого step.ended.

    True — шаг подтверждён и pending-вызовы опубликованы один раз; False —
    в дренаже записана provider-ошибка (`result["error"]`), pending не публикуется.
    """
    step_confirmed = _drain_serve_step_usage(
        events,
        session_id,
        assistant_message_id,
        deadline,
        result["usage"],
        tool_state,
        result,
        on_tool,
        release_event,
        attempt_deadline=attempt_deadline,
        is_client_gone=is_client_gone,
        pending_calls=pending_calls,
        ctrl_http=ctrl_http,
        reasoning_cb=reasoning_cb,
        text_cb=text_cb,
        emulate_tools=emulate_tools,
        accumulated_bytes=accumulated_bytes,
        t0=t0,
    )
    if result["error"] is not None:
        return False
    if not step_confirmed:
        raise ServeProtocolError("incomplete tool step without step.ended")
    if is_client_gone is not None and is_client_gone():
        raise ServeClientDisconnect("client disconnected")
    if pending_calls is not None:
        for call in pending_calls:
            result["native_calls"].append(call)
            on_tool(call)
    result["terminal"] = "tool_calls"
    result["step_closed"] = True
    return True


def _serve_one_attempt(
    model: str,
    prompt: str,
    effort: str,
    workdir: Path,
    on_reasoning: Callable[[str], None],
    on_text: Callable[[str], None],
    on_tool: Callable[[dict[str, object]], None],
    t0: float,
    is_client_gone: Callable[[], bool] | None = None,
    on_status: Callable[[str], None] | None = None,
    thinking_enabled: bool = True,
    deadline: float | None = None,
    proxy_url: str | None = None,
    on_startup_ready: Callable[[], None] | None = None,
    emulate_tools: bool = False,
    aux_budget: _AuxIoBudget | None = None,
) -> _ServeResult:
    """Одна попытка serve: helper, сессия, SSE, prompt и канонические события."""
    result: _ServeResult = {
        "reasonings": [],
        "texts": [],
        "native_calls": [],
        "usage": {},
        "error": None,
        "exit_reason": "",
        "delivered": False,
        "terminal": "",
        "first_event_at": None,
        "first_token_at": None,
        "step_closed": False,
        "first_event_ms": None,
        "ttft_ms": None,
        "prompt_status": None,
        "transient_error": False,
    }
    attempt_deadline = min(
        deadline if deadline is not None else t0 + TIMEOUT_S, t0 + TIMEOUT_S
    )
    aux = aux_budget if aux_budget is not None else _AuxIoBudget()
    if is_client_gone is not None and is_client_gone():
        result["exit_reason"] = "client_gone"
        result["delivered"] = True
        return result
    if aux.exhausted():
        result["exit_reason"] = "timeout"
        result["delivered"] = True
        return result
    try:
        serve_env = _serve_env(model)
    except OSError as exc:
        raise ServeUnavailable(f"serve env failed: {exc}") from exc
    if proxy_url:
        serve_env["HTTP_PROXY"] = proxy_url
        serve_env["HTTPS_PROXY"] = proxy_url
    password = serve_env.get("OPENCODE_SERVER_PASSWORD", "")
    attempt_id = uuid.uuid4().hex
    _aux_started = aux.now_s()
    try:
        lease, port, _pw = _spawn_serve(
            attempt_id,
            serve_env,
            deadline=aux.deadline(attempt_deadline),
            is_client_gone=is_client_gone,
        )
    except (ServeClientDisconnect, ServeStartupDeadlineExceeded) as exc:
        result["exit_reason"] = (
            "client_gone" if isinstance(exc, ServeClientDisconnect) else "timeout"
        )
        result["delivered"] = True
        return result
    finally:
        aux.debit_elapsed(_aux_started)
    session_id = ""
    sse_conn: http.client.HTTPConnection | None = None
    prompt_status: dict[str, object] = {}
    control_conn: list[http.client.HTTPConnection | None] = [None]
    stop_event: threading.Event | None = None
    reader_thread: threading.Thread | None = None
    prompt_thread: threading.Thread | None = None

    def _is_delivered() -> bool:
        return bool(
            prompt_status.get("headers_at")
            or result["first_event_at"] is not None
            or result["texts"]
            or result["reasonings"]
            or result["native_calls"]
        )

    def _ctrl_http(
        method: str,
        path: str,
        body: dict[str, object] | None = None,
        timeout: float = 3.0,
        phase_deadline: float | None = None,
    ) -> tuple[int, dict[str, object]]:
        """Управляющий вызов serve по одному keep-alive соединению."""
        charge_aux = phase_deadline is None
        if charge_aux:
            aux.check()
        started = aux.now_s()
        try:
            call_deadline = min(
                aux.deadline(attempt_deadline) if charge_aux else attempt_deadline,
                phase_deadline
                if phase_deadline is not None
                else time.monotonic() + float(timeout),
            )
            for attempt in (0, 1):
                _check_serve_start(attempt_deadline, is_client_gone)
                conn = control_conn[0]
                if conn is None:
                    conn = http.client.HTTPConnection(
                        "127.0.0.1", port, timeout=timeout
                    )
                    control_conn[0] = conn
                try:
                    return _serve_http(
                        port,
                        password,
                        method,
                        path,
                        body,
                        timeout=timeout,
                        conn=conn,
                        deadline=call_deadline,
                        is_client_gone=is_client_gone,
                    )
                except (OSError, http.client.HTTPException):
                    _check_serve_start(attempt_deadline, is_client_gone)
                    try:
                        conn.close()
                    except OSError:
                        pass
                    control_conn[0] = None
                    if attempt or time.monotonic() >= call_deadline:
                        raise
            raise ServeUnavailable("serve control connection failed")
        finally:
            if charge_aux:
                aux.debit_elapsed(started)

    def _drain_ctrl(
        method: str, path: str, body: dict[str, object] | None = None
    ) -> tuple[int, dict[str, object]]:
        """Управляющий вызов дренажа шага с коротким таймаутом."""
        return _ctrl_http(method, path, body, timeout=0.25)

    def _reject_and_interrupt(
        path: str, body: dict[str, object] | None, label: str
    ) -> None:
        """Всегда попробовать interrupt после reject/cancel; ошибки закрывают попытку."""
        failures: list[str] = []
        for control_path, control_body, control_label in (
            (path, body, label),
            (f"/api/session/{session_id}/interrupt", None, "interrupt"),
        ):
            try:
                status, _body = _ctrl_http(
                    "POST", control_path, control_body, timeout=0.25
                )
                if status not in (200, 204):
                    failures.append(f"{control_label} HTTP {status}")
            except (
                OSError,
                http.client.HTTPException,
                ServeUnavailable,
                ServeProtocolError,
            ) as exc:
                failures.append(f"{control_label}: {exc}")
        if failures:
            raise ServeSecurityError("; ".join(failures))

    def _open_session() -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
        """Aux-фазы попытки: ready, создание сессии и подписка до первого SSE."""
        nonlocal session_id
        status = 0
        active: dict[str, object] = {}
        if aux.exhausted():
            raise ServeStartupDeadlineExceeded("aux io budget exhausted")
        _aux_started = aux.now_s()
        ready_deadline = min(
            time.monotonic() + 3.0, attempt_deadline, aux.deadline(attempt_deadline)
        )
        try:
            while True:
                try:
                    status, active = _ctrl_http(
                        "GET",
                        "/api/session/active",
                        timeout=3.0,
                        phase_deadline=ready_deadline,
                    )
                    break
                except (OSError, http.client.HTTPException) as exc:
                    _check_serve_start(attempt_deadline, is_client_gone)
                    if time.monotonic() >= ready_deadline:
                        raise ServeUnavailable(f"serve ready failed: {exc}") from exc
                    time.sleep(0.05)
        finally:
            aux.debit_elapsed(_aux_started)
        if status in (401, 403):
            raise ServeSecurityError(f"serve auth HTTP {status}")
        if status in (400, 404, 422):
            raise ServeSecurityError(f"serve invalid request HTTP {status}")
        if status != 200 or not isinstance(active.get("data"), dict):
            raise ServeUnavailable(f"serve ready HTTP {status}")
        route = _model_route(model)
        provider, _sep, raw_id = route.partition("/")
        variant = _variant_for(model, effort)
        model_body: dict[str, object] = {
            "providerID": provider or "opencode",
            "id": raw_id or model,
        }
        if variant:
            model_body["variant"] = variant
        if aux.exhausted():
            raise ServeStartupDeadlineExceeded("aux io budget exhausted")
        _aux_started = aux.now_s()
        try:
            status, created = _ctrl_http(
                "POST",
                "/api/session",
                {
                    "location": {"directory": str(workdir)},
                    "model": model_body,
                    "permissions": [
                        {
                            "action": "*",
                            "resource": "*",
                            "effect": _serve_permission_effect(),
                        }
                    ],
                },
                timeout=3.0,
                phase_deadline=min(
                    time.monotonic() + 3.0,
                    attempt_deadline,
                    aux.deadline(attempt_deadline),
                ),
            )
        finally:
            aux.debit_elapsed(_aux_started)
        if status in (401, 403):
            raise ServeSecurityError(f"serve create HTTP {status}")
        if status in (400, 404, 422):
            raise ServeSecurityError(f"serve invalid request HTTP {status}")
        created_data = created.get("data")
        if (
            status != 200
            or not isinstance(created_data, dict)
            or not created_data.get("id")
        ):
            raise ServeUnavailable(f"serve create HTTP {status}")
        session_id = str(created_data["id"])
        if aux.exhausted():
            raise ServeStartupDeadlineExceeded("aux io budget exhausted")
        _aux_started = aux.now_s()
        try:
            opened = _open_serve_events(
                port, password, aux.deadline(attempt_deadline), is_client_gone
            )
        finally:
            aux.debit_elapsed(_aux_started)
        return opened

    subscribe_wait_started: float | None = None
    try:
        sse_conn, sse_resp = _open_session()
        subscribe_wait_started = aux.now_s()
        first_event_limit = time.monotonic() + float(FIRST_EVENT_TIMEOUT_S)
        first_event_deadline = min(first_event_limit, aux.deadline(attempt_deadline))
        events: queue.Queue[dict[str, object] | None] = queue.Queue(maxsize=4096)
        stop_event = threading.Event()
        queued_bytes = [0]
        queue_bytes_lock = threading.Lock()
        accumulated_bytes = 0
        current_step_msg_id = ""

        def _release_event(event: dict[str, object]) -> None:
            """Вернуть байтовый резерв после извлечения события из очереди."""
            with queue_bytes_lock:
                queued_bytes[0] -= _as_int(event.pop("_raw_bytes", 0))

        if sse_conn.sock is not None:
            # Без таймаута сокета: после первого таймаута SocketIO считает поток закрытым,
            # а любая пауза SSE > 0.5 с превращалась бы в ложный EOF. Остановка — shutdown в finally.
            _ = sse_conn.sock.settimeout(None)
        if on_startup_ready is not None:
            on_startup_ready()

        reader_thread = threading.Thread(
            target=_read_serve_events,
            args=(
                sse_resp,
                events,
                stop_event,
                queued_bytes,
                queue_bytes_lock,
                _release_event,
            ),
            daemon=True,
        )
        reader_thread.start()
        prompt_send_start = time.monotonic()
        prompt_aux_lock = threading.Lock()
        prompt_aux_finished = False

        def _finish_prompt_aux(finished_at: float) -> None:
            """Списать ожидание заголовков один раз, до начала генерации."""
            nonlocal prompt_aux_finished
            with prompt_aux_lock:
                if prompt_aux_finished:
                    return
                for stamp in (
                    prompt_status.get("headers_at"),
                    result["first_event_at"],
                ):
                    if isinstance(stamp, (int, float)):
                        finished_at = min(finished_at, float(stamp))
                aux.debit_seconds(finished_at - prompt_send_start)
                prompt_aux_finished = True

        def _prompt_worker() -> None:
            """Доставка prompt: заголовки ограничены остатком aux-бюджета."""
            prompt_deadline = aux.deadline(attempt_deadline)

            def _on_headers(status_code: int = 200) -> None:
                prompt_status["headers_at"] = time.monotonic()
                _finish_prompt_aux(time.monotonic())
                prompt_status["status"] = status_code
                if status_code in (401, 403):
                    prompt_status["security"] = True

            try:
                aux.check()
                prompt_timeout = min(
                    65.0, max(0.05, prompt_deadline - time.monotonic())
                )
                st, _body = _serve_http(
                    port,
                    password,
                    "POST",
                    f"/api/session/{session_id}/prompt",
                    {"text": prompt, "files": [], "delivery": "steer", "resume": True},
                    timeout=prompt_timeout,
                    on_headers=_on_headers,
                    deadline=prompt_deadline,
                    is_client_gone=is_client_gone,
                )
                prompt_status["status"] = st
                if st in (401, 403):
                    prompt_status["security"] = True
            except (
                OSError,
                http.client.HTTPException,
                ServeStartupDeadlineExceeded,
            ) as exc:
                if time.monotonic() >= prompt_deadline or aux.exhausted():
                    if result["first_event_at"] is None:
                        prompt_status["aux_exhausted"] = True
                else:
                    prompt_status["error"] = str(exc)
            except ServeProtocolError as exc:
                prompt_status["protocol_error"] = str(exc)
            finally:
                _finish_prompt_aux(time.monotonic())

        prompt_thread = threading.Thread(target=_prompt_worker, daemon=True)
        prompt_thread.start()
        tool_state = _ServeToolState()
        pending_step_calls: list[dict[str, object]] = []
        seen_steps: set[str] = set()
        deadline = min(
            deadline if deadline is not None else prompt_send_start + TIMEOUT_S,
            prompt_send_start + TIMEOUT_S,
        )
        status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25)
        _status_emitted = [0]
        last_token_at = prompt_send_start
        while time.monotonic() < deadline:
            if is_client_gone is not None and is_client_gone():
                result["exit_reason"] = "client_gone"
                return result
            if prompt_status.get("protocol_error"):
                result["exit_reason"] = "invalid_serve_event"
                return result
            now = time.monotonic()
            if prompt_status.get("aux_exhausted") or (
                result["first_event_at"] is None and now >= first_event_deadline
            ):
                result["exit_reason"] = (
                    "timeout"
                    if prompt_status.get("aux_exhausted")
                    or first_event_deadline < first_event_limit
                    else "first_event_timeout"
                )
                result["delivered"] = _is_delivered()
                return result
            if (
                result["first_event_at"] is not None
                and result["first_token_at"] is None
                and now - prompt_send_start > float(FIRST_TOKEN_TIMEOUT_S)
            ):
                result["exit_reason"] = "first_token_timeout"
                result["delivered"] = True
                return result
            if result["first_token_at"] is not None and now - last_token_at > float(
                STALL_TIMEOUT_S
            ):
                result["exit_reason"] = "stall_timeout"
                result["delivered"] = True
                return result
            # Классификация HTTP-статуса prompt по FALLBACK_DECISION_TABLE до ожидания SSE-события.
            _ps = prompt_status.get("status")
            if isinstance(_ps, int) and _ps != 200 and result["prompt_status"] is None:
                result["prompt_status"] = _ps
                if _ps in (401, 403):
                    raise ServeSecurityError(f"serve prompt HTTP {_ps}")
                if _ps in (400, 404, 422):
                    raise ServeSecurityError(f"serve prompt HTTP {_ps}")
                _delivered_now = _is_delivered()
                result["delivered"] = _delivered_now
                if _ps == 429:
                    result["exit_reason"] = "prompt_status_429"
                    result["transient_error"] = True
                    return result
                if 500 <= _ps <= 599:
                    result["exit_reason"] = f"prompt_status_{_ps}"
                    return result
            _prompt_err = prompt_status.get("error")
            if isinstance(_prompt_err, str):
                _has_delivery = _is_delivered()
                if not _has_delivery:
                    raise ServeUnavailable(f"serve prompt failed: {_prompt_err}")
                result["delivered"] = True
                result["exit_reason"] = "prompt_error"
                result["transient_error"] = True
                return result
            if thinking_enabled and on_status is not None and now >= status_next:
                if result["first_token_at"] is None:
                    on_status(
                        STATUS_INITIAL if _status_emitted[0] == 0 else STATUS_WAITING
                    )
                    _status_emitted[0] += 1
                    status_next = now + STATUS_WAITING_INTERVAL_S
                elif now - last_token_at >= float(STALL_HEARTBEAT_INTERVAL_S):
                    on_status(STATUS_CONTINUATION)
                    status_next = now + float(STALL_HEARTBEAT_INTERVAL_S)
            try:
                event = events.get(timeout=0.02)
            except queue.Empty:
                continue
            if event is None:
                if not result["terminal"]:
                    result["exit_reason"] = "invalid_serve_event"
                    result["delivered"] = _is_delivered()
                break
            if subscribe_wait_started is not None:
                aux.debit_elapsed(subscribe_wait_started)
                subscribe_wait_started = None
            _release_event(event)
            etype_raw = str(event.get("type") or "")
            if etype_raw == "__invalid_json__":
                result["exit_reason"] = "invalid_serve_event"
                result["delivered"] = _is_delivered()
                return result
            data_raw = _as_dict(event.get("data"))
            _raw_sid = data_raw.get("sessionID")
            if (
                etype_raw not in ("server.connected", "form.created")
                and isinstance(_raw_sid, str)
                and _raw_sid
                and _raw_sid != session_id
            ):
                continue
            current_step_msg_id = _serve_step_message_id(
                data_raw, session_id, result["step_closed"], current_step_msg_id
            )
            # form.created: безопасность до любой проверки title/fields/схемы.
            if etype_raw == "form.created":
                form = _as_dict(data_raw.get("form"))
                form_session = form.get("sessionID")
                form_id = form.get("id")
                if form_session == session_id and isinstance(form_id, str) and form_id:
                    result["step_closed"] = True
                    _reject_and_interrupt(
                        f"/api/session/{session_id}/form/{form_id}/cancel",
                        None,
                        "form cancel",
                    )
                    result["terminal"] = "cancelled"
                    break
                if form_session == session_id:
                    raise ServeSecurityError("form.created without id")
                continue
            if prompt_status.get("security"):
                raise ServeSecurityError("serve prompt auth failed")
            try:
                _mapped = _map_serve_event(event)
            except ServeProtocolError:
                result["exit_reason"] = "invalid_serve_event"
                result["delivered"] = _is_delivered()
                return result
            if _mapped is None:
                continue
            etype, payload = _mapped
            event_session = (
                payload.get("sessionID") if isinstance(payload, dict) else None
            )
            if etype_raw not in ("server.connected",) and event_session not in (
                None,
                session_id,
            ):
                continue
            is_execution = etype_raw in (
                "session.execution.started",
                "session.step.started",
                "session.reasoning.started",
                "session.reasoning.delta",
                "session.text.delta",
                "session.step.ended",
            ) or etype in ("reasoning", "text", "tool_event", "step_finish")
            if is_execution and result["first_event_at"] is None:
                result["first_event_at"] = time.monotonic()
                _finish_prompt_aux(time.monotonic())
                result["first_event_ms"] = int(
                    ((result["first_event_at"] or 0.0) - t0) * 1000
                )
            if etype == "permission":
                result["step_closed"] = True
                request_id = str(payload.get("id") or "")
                _reject_and_interrupt(
                    f"/api/session/{session_id}/permission/{request_id}/reply",
                    {"decision": "reject"},
                    "permission reply",
                )
                continue
            if result["step_closed"] and etype in ("reasoning", "text"):
                continue
            accumulated_bytes = _serve_accumulated_bytes(
                accumulated_bytes, etype, payload, tool_state
            )
            if etype == "reasoning":
                text_value = str(payload.get("reasoning_content") or "")
                if text_value:
                    if result["first_token_at"] is None:
                        result["first_token_at"] = time.monotonic()
                        result["ttft_ms"] = int(
                            ((result["first_token_at"] or 0.0) - t0) * 1000
                        )
                    result["reasonings"].append(text_value)
                    last_token_at = time.monotonic()
                    on_reasoning(text_value)
            elif etype == "text":
                text_value = str(payload.get("content") or "")
                if text_value:
                    if result["first_token_at"] is None:
                        result["first_token_at"] = time.monotonic()
                        result["ttft_ms"] = int(
                            ((result["first_token_at"] or 0.0) - t0) * 1000
                        )
                    result["texts"].append(text_value)
                    last_token_at = time.monotonic()
                    on_text(text_value)
            elif etype == "tool_event":
                if etype_raw == "session.tool.input.delta":
                    last_token_at = time.monotonic()
                tool_state.feed(payload)
                accumulated_bytes = _serve_accumulated_bytes(
                    accumulated_bytes, etype, payload, tool_state
                )
                call_id = str(payload.get("id") or "")
                if etype_raw in (
                    "session.tool.called",
                    "session.tool.failed",
                    "session.tool.success",
                ):
                    done = tool_state.complete(call_id, etype_raw)
                    if done is not None:
                        last_token_at = time.monotonic()
                        pending_step_calls.append(done[1])
                        if result["first_token_at"] is None:
                            result["first_token_at"] = time.monotonic()
                            result["ttft_ms"] = int(
                                ((result["first_token_at"] or 0.0) - t0) * 1000
                            )
                        if emulate_tools:
                            _acc_box = [accumulated_bytes]
                            _ = _finish_serve_tool_step(
                                events,
                                session_id,
                                data_raw.get("assistantMessageID")
                                or current_step_msg_id
                                or None,
                                min(deadline, time.monotonic() + _STEP_DRAIN_WINDOW_S),
                                tool_state,
                                result,
                                on_tool,
                                _release_event,
                                attempt_deadline=deadline,
                                is_client_gone=is_client_gone,
                                pending_calls=pending_step_calls,
                                ctrl_http=_drain_ctrl,
                                reasoning_cb=on_reasoning,
                                text_cb=on_text,
                                emulate_tools=emulate_tools,
                                accumulated_bytes=_acc_box,
                                t0=t0,
                            )
                            accumulated_bytes = _acc_box[0]
                            break
            elif etype == "step_finish":
                step_key = str(
                    _as_dict(payload).get("assistantMessageID")
                    or data_raw.get("assistantMessageID")
                    or ""
                )
                if step_key and step_key in seen_steps:
                    continue
                if step_key:
                    seen_steps.add(step_key)
                # payload шага после _map не несёт assistantMessageID: ключ из data_raw выше.
                for key in ("input", "output", "cached", "reasoning"):
                    result["usage"][key] = result["usage"].get(key, 0) + _as_int(
                        payload.get(key)
                    )
                # Завершить native вызовы без called: аргументы из input.ended.text.
                for call_id in list(tool_state.tools):
                    done = tool_state.complete(call_id, etype_raw)
                    if done is not None:
                        last_token_at = time.monotonic()
                        pending_step_calls.append(done[1])
                # step_finish — это session.step.ended: pending публикуется один раз.
                for pending_call in pending_step_calls:
                    result["native_calls"].append(pending_call)
                    on_tool(pending_call)
                pending_step_calls.clear()
                if result["native_calls"] or (
                    emulate_tools and _split_tool_calls(["".join(result["texts"])])[1]
                ):
                    if result["first_token_at"] is None and result["native_calls"]:
                        result["first_token_at"] = time.monotonic()
                        result["ttft_ms"] = int(
                            ((result["first_token_at"] or 0.0) - t0) * 1000
                        )
                    result["terminal"] = "tool_calls"
                    break
            elif etype == "error":
                result["error"] = payload
                result["delivered"] = _is_delivered()
                result["transient_error"] = _is_transient_stream_error(payload)
                result["terminal"] = "failed"
                break
            elif etype_raw == "session.execution.succeeded":
                for pending_call in pending_step_calls:
                    result["native_calls"].append(pending_call)
                    on_tool(pending_call)
                pending_step_calls.clear()
                result["terminal"] = "succeeded"
                break
        if (
            not result["terminal"]
            and not result["exit_reason"]
            and time.monotonic() >= deadline
        ):
            result["exit_reason"] = "timeout"
        result["delivered"] = result["delivered"] | _is_delivered()
        return result
    except (ServeClientDisconnect, ServeStartupDeadlineExceeded) as exc:
        result["exit_reason"] = (
            "client_gone" if isinstance(exc, ServeClientDisconnect) else "timeout"
        )
        result["delivered"] = True
        return result
    except (OSError, http.client.HTTPException, ServeProtocolError) as exc:
        result["exit_reason"] = _serve_attempt_error_reason(
            exc, attempt_deadline, is_client_gone, _is_delivered()
        )
        result["delivered"] = _is_delivered() | (
            result["exit_reason"] in ("client_gone", "timeout")
        )
        result["transient_error"] = result["exit_reason"] == "prompt_error"
        return result
    finally:
        if subscribe_wait_started is not None:
            aux.debit_elapsed(subscribe_wait_started)
        result["delivered"] = result["delivered"] | _is_delivered()
        _cleanup_serve_attempt(
            lease,
            port,
            password,
            session_id,
            sse_conn,
            control_conn[0],
            stop_event,
            reader_thread,
            prompt_thread,
        )
        result["delivered"] = result["delivered"] | _is_delivered()


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
    return _token_eq(handler.headers.get("x-api-key", ""), AUTH_KEY) or _token_eq(
        hdr.strip(), AUTH_KEY
    )


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

    text = re.sub(r"(?i)\b(Bearer\s+)[^\s,;\"']+", r"\1***", text)
    text = re.sub(r"(?i)(OPENCODE_SERVER_PASSWORD\s*[=:]\s*)[^\s,;]+", r"\1***", text)
    text = re.sub(
        r"(?i)(\b(?:https?|socks[45]h?)://)[^/\s:@]+:[^/\s@]+@", r"\1***@", text
    )
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
_BROKEN_BLOCK_NOTICE = (
    "[opencode-zen-bridge: невалидный блок вызова инструмента отброшен]"
)


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
        self._tail_after_tool = (
            ""  # весь текст после последнего вызова (для инварианта к чанкам)
        )

    def feed(self, text: str) -> None:
        self._buf += text
        self._drain(final=False)

    def finish(self) -> None:
        self._drain(final=True)

    def has_open_tool_call(self) -> bool:
        """Тег открыт и ждёт закрытия (или его начало может прийти следующей дельтой)."""
        return (
            any(open_tag in self._buf for open_tag, _ in TOOL_CALL_TAGS)
            or self._pending_prefix() > 0
        )

    def _classify_open(self, after: int, final: bool) -> str:
        """`<tool_call>` в буфере: "real" | "quoted" (inline-код markdown) | "wait" (нужен следующий символ)."""
        context = _code_context(self._history + self._buf, len(self._history), final)
        if context != "text":
            return "quoted" if context == "code" else "wait"
        tail = self._buf[after : after + 3]
        if not tail:
            return "real" if final else "wait"
        if (
            tail[0] != "`" or tail == "```"
        ):  # ```json-обёртка внутри блока — настоящий вызов
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
            self._buf = self._buf[end + len(close_tag) :]
            calls = _parse_tool_call_blocks(inner)
            if calls is None:
                _log(
                    f"tool_call_unparsed bytes={len(inner.encode('utf-8'))} "
                    f"head={_mask_secrets(inner[:120])!r}"
                )
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

    def _find_close_outside_string(
        self, start: int, close_tag: str = TOOL_CALL_CLOSE
    ) -> int:
        """Позиция закрывающего тега вне строковых литералов JSON буфера, или -1 (см. `_find_close_in`)."""
        return _find_close_in(self._buf, start, close_tag)

    def _pending_prefix(self) -> int:
        """Длина хвоста — префикса открывающего тега (его нельзя отдать в content)."""
        limit = min(
            max(len(open_tag) for open_tag, _ in TOOL_CALL_TAGS) - 1, len(self._buf)
        )
        for length in range(limit, 0, -1):
            if any(
                self._buf[-length:] == open_tag[:length]
                for open_tag, _ in TOOL_CALL_TAGS
            ):
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
        conn = sqlite3.connect(
            f"file:{quote(str(db_path))}?mode=ro", uri=True, timeout=5
        )
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
    r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*$",
    re.MULTILINE,
)


def _in_active_markdown_table(
    text: str, loop_start: int, sep_ends: list[int] | None = None
) -> bool:
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
            between = between[len(eol) :]
            break
    lines = between.splitlines()
    if lines and not between.endswith(
        ("\n", "\r")
    ):  # хвост до loop_start оборван посреди строки таблицы
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
        s.startswith("|")
        or s.endswith("|")
        or s.count("|") >= 2
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
        return "<![CDATA[" not in text[
            max(0, pos - 300) : pos
        ] and not _in_active_markdown_table(text, pos, seps)

    recent = []
    pos = text.find("]]>", recent_start)
    while pos >= 0:
        if is_terminator(pos):
            recent.append(pos)
        pos = text.find("]]>", pos + 3)
    if len(recent) < _CDATA_END_MIN:
        return None
    start = recent[0]
    while (
        prev := text.rfind("]]>", max(0, start - _CDATA_GAP_MAX), start)
    ) >= 0 and is_terminator(prev):
        start = prev
    return start


def _detect_repetition_loop(text: str) -> int | None:
    """Индекс начала зацикленного хвоста (кусок 4..80 символов >= 6 раз подряд, >= 120 символов) или None."""
    tail = text[-_LOOP_TAIL_CHARS:]
    base = len(text) - len(tail)
    if (
        "<![CDATA[" not in tail[-300:]
        and (cdata_idx := _cdata_loop_start(text)) is not None
    ):
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
        while pos - size >= 0 and tail[pos - size : pos] == unit:
            reps += 1
            pos -= size
        if reps < _LOOP_MIN_REPEATS or size * reps < _LOOP_MIN_BLOCK_CHARS:
            continue
        full_pos = (
            base + pos
        )  # цикл мог начаться раньше хвоста — отматываем по всему тексту
        while full_pos - size >= 0 and text[full_pos - size : full_pos] == unit:
            full_pos -= size
        if _is_table_block(
            unit, text, full_pos
        ):  # строки markdown-таблицы повторяются законно
            continue
        return full_pos
    return None


_THOUGHT_CLOSED_RE = re.compile(r"<unused94>thought\b.*?<unused95>\s*", re.DOTALL)
_THOUGHT_OPEN_RE = re.compile(r"<unused94>thought\b.*$", re.DOTALL)
_CDATA_LOOP_RE = re.compile(
    r"(?:(?:Sub-thought finished\.|end\.|stop\.)?\s*\]\]>\s*(?:Let's [^\n\]]*)?\s*){2,}.*$",
    re.DOTALL,
)


def _strip_unclosed_tool_calls(text: str) -> str:
    """Отрезать сырые `<tool_call>{…` после последнего закрывающего тега: они не закрыты и травят few-shot.

    Пачка блоков без промежуточных закрытий, закрытая в конце, не затрагивается.
    """
    close_end = max(
        (
            text.rfind(close_tag) + len(close_tag)
            for _, close_tag in TOOL_CALL_TAGS
            if close_tag in text
        ),
        default=0,
    )
    match = _RAW_CALL_RE.search(text, close_end)
    return text[: match.start()].rstrip() if match else text


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


def _google_request(
    model: str,
    prompt: str,
    effort: str,
    stream: bool,
    google_input: GoogleInput | None = None,
):
    """Открыть HTTP напрямую: прокси из окружения здесь не используются."""
    meta = ALLOWED_MODELS[model]
    base = urlsplit(meta["base_url"].rstrip("/"))
    token, org_id = _resolve_opencode_go_auth()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "curl/8.7.1",
        "x-goog-api-key": token,
        "Authorization": f"Bearer {token}",
        "x-opencode-session": "dsh",
    }
    if org_id:
        headers["x-opencode-org-id"] = org_id
    contents, system_instruction = (
        google_input if google_input is not None else (None, "")
    )
    body = json.dumps(
        _build_google_payload(
            prompt,
            effort,
            int(meta.get("max_output") or 65536),
            contents,
            system_instruction,
        ),
        ensure_ascii=False,
    ).encode("utf-8")
    action = "streamGenerateContent?alt=sse" if stream else "generateContent"
    path = f"{base.path}/models/{quote(model, safe='')}:{action}"
    cls = (
        http.client.HTTPSConnection
        if base.scheme == "https"
        else http.client.HTTPConnection
    )
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
        self.is_client_gone: Callable[[], bool] | None = None

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
        acc_reasonings: list[str] = []
        acc_chunks: list[str] = []
        acc_text = ""
        acc_first_event_at: float | None = None
        acc_first_token_at: float | None = None
        acc_usage: dict[str, int] = {
            "input": 0,
            "output": 0,
            "cached": 0,
            "reasoning": 0,
        }

        def _save_partial(out: dict[str, object]) -> None:
            """Сохранить вывод упавшей попытки без неподтверждённых tool calls."""
            nonlocal acc_text, acc_first_event_at, acc_first_token_at
            fe = out.get("first_event_at")
            if acc_first_event_at is None and isinstance(fe, (int, float)):
                acc_first_event_at = float(fe)
            ft = out.get("first_token_at")
            if acc_first_token_at is None and isinstance(ft, (int, float)):
                acc_first_token_at = float(ft)
            if out.get("reasoning"):
                acc_reasonings.append(str(out["reasoning"]))
            text = str(out.get("text") or "")
            if self.tools and text:
                raw_chunks = out.get("chunks")
                chunks = (
                    [str(c) for c in cast("list[object]", raw_chunks)]
                    if isinstance(raw_chunks, list) and raw_chunks
                    else [text]
                )
                text = _strip_broken_tool_blocks(_split_tool_calls(chunks)[0])[0]
            text = _strip_interrupted(text)
            repeated = bool(acc_text and text.startswith(acc_text))
            text = _dedup_retry_text(acc_text, text)
            if text:
                chunk = ("\n\n" if acc_text and not repeated else "") + text
                acc_chunks.append(chunk)
                acc_text += chunk
            previous_usage = _as_dict(out.get("usage"))
            for key in acc_usage:
                acc_usage[key] += int(str(previous_usage.get(key) or 0))

        def _with_previous(out: dict[str, object]) -> dict[str, object]:
            """Добавить накопленные попытки к любому конечному результату."""
            if acc_first_event_at is not None:
                out["first_event_at"] = acc_first_event_at
            if acc_first_token_at is not None:
                out["first_token_at"] = acc_first_token_at
            if acc_reasonings:
                out["reasoning"] = "".join(
                    acc_reasonings
                    + ([str(out["reasoning"])] if out.get("reasoning") else [])
                )
            if acc_text:
                text = _strip_interrupted(str(out.get("text") or ""))
                repeated = text.startswith(acc_text)
                text = _dedup_retry_text(acc_text, text)
                suffix = ("\n\n" if text and not repeated else "") + text
                out["text"] = acc_text + suffix
                out["chunks"] = acc_chunks + ([suffix] if suffix else [])
            if any(acc_usage.values()):
                final_usage = _as_dict(out.get("usage"))
                out["usage"] = {
                    key: acc_usage[key] + int(str(final_usage.get(key) or 0))
                    for key in acc_usage
                }
            return out

        try:
            while True:
                out = _as_dict(self._execute_once())
                if out.get("state") in (
                    "first_event_timeout",
                    "first_token_timeout",
                    "stall_timeout",
                ):
                    if attempts.can_spawn() and attempts.allow_retry(
                        str(out.get("state"))
                    ):
                        _save_partial(out)
                        self.close()
                        continue
                    return _with_previous(out)
                if fail_retries >= FAIL_RETRY_LIMIT or not _is_retryable_failure(
                    cast("int | None", out.get("rc")),
                    str(out.get("err") or ""),
                    cast("int | None", out.get("provider_status")),
                    bool(out.get("had_output")),
                ):
                    return _with_previous(out)
                if not attempts.allow_retry("cli_failure", charge_budget=out.get("provider_status") is not None):
                    return _with_previous(out)
                fail_retries += 1
                _log(f"exec failed rc={out.get('rc')} without output, retry {fail_retries}/{FAIL_RETRY_LIMIT} "
                     f"total_spawns={attempts.total_spawns}/{attempts.max_total}: "
                     f"{_clean_err(str(out.get('err') or ''), 300)!r}")
                _save_partial(out)
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
        gate.acquire(deadline=deadline, is_client_gone=self.is_client_gone)
        if not self.res.spawn_limiter.acquire(
            max_wait_s=min(SPAWN_WAIT_MAX_S, max(0.0, deadline - time.monotonic())),
            deadline=deadline,
            is_client_gone=self.is_client_gone,
        ):
            gate.release()
            if self.attempts is not None:
                self.attempts.attempt_done(False, False)
            return {
                "rc": -1,
                "text": "",
                "reasoning": "",
                "usage": {},
                "err": "spawn rate limit: deadline exceeded",
                "state": "client_gone"
                if self.is_client_gone is not None and self.is_client_gone()
                else "timeout",
                "finish": "error",
            }
        if (
            self.is_client_gone is not None and self.is_client_gone()
        ) or time.monotonic() >= deadline:
            self.res.spawn_limiter.refund()
            gate.release()
            if self.attempts is not None:
                self.attempts.attempt_done(False, False)
            return {
                "rc": -1,
                "text": "",
                "reasoning": "",
                "usage": {},
                "err": "request cancelled or deadline exceeded",
                "state": "client_gone"
                if self.is_client_gone is not None and self.is_client_gone()
                else "timeout",
                "finish": "error",
            }
        try:
            self.proc = _spawn_with_stdin(cmd, self.prompt, self.workdir, env)
        except OSError as exc:
            self.res.spawn_limiter.refund()
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
        attempt_start = time.monotonic()
        first_event_at: float | None = None
        first_token_at: float | None = None
        last_token_at: float | None = None
        watchdog_reason: list[str] = []
        subagent_started_at: dict[str, float] = {}
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

        def on_idle() -> None:
            """Прервать молчащий JSON-прогон при закрытии клиентского сокета."""
            nonlocal state
            if self.is_client_gone is not None and self.is_client_gone():
                state = "client_gone"
                if self.proc is not None:
                    _stop_proc(self.proc)
                return
            if watchdog_reason:
                return
            now = time.monotonic()
            reason = ""
            if first_event_at is None and now - attempt_start > float(
                FIRST_EVENT_TIMEOUT_S
            ):
                reason = "first_event_timeout"
            elif first_token_at is None and now - attempt_start > float(
                FIRST_TOKEN_TIMEOUT_S
            ):
                reason = "first_token_timeout"
            elif (
                last_token_at is not None
                and not subagent_started_at
                and now - last_token_at > float(STALL_TIMEOUT_S)
            ):
                reason = "stall_timeout"
            if reason:
                watchdog_reason.append(reason)
                state = reason
                _log(f"opencode run watchdog: {reason}")
                if self.proc is not None:
                    _stop_proc(self.proc)

        try:
            self.feed = _StdoutFeed(self.proc)
            for raw in self.feed.lines(
                deadline, idle_s=_STDOUT_POLL_S, on_idle=on_idle
            ):
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
                if isinstance(event, dict):
                    now_ev = time.monotonic()
                    if first_event_at is None:
                        first_event_at = now_ev
                    frame = _as_dict(cast(object, payload))
                    token = (
                        frame.get("content")
                        if etype == "text"
                        else frame.get("reasoning_content")
                    )
                    if (
                        etype in ("text", "reasoning")
                        and isinstance(token, str)
                        and token
                    ) or etype in ("tool_use", "tool_call"):
                        if first_token_at is None:
                            first_token_at = now_ev
                        last_token_at = now_ev
                    part = _as_dict(_as_dict(cast(object, event)).get("part"))
                    if (
                        etype in ("tool_use", "tool_call")
                        and part.get("tool") == "task"
                    ):
                        task_id = str(part.get("id") or "task")
                        task_status = _as_dict(part.get("state")).get("status")
                        if task_status in ("pending", "running"):
                            subagent_started_at[task_id] = now_ev
                        else:
                            _ = subagent_started_at.pop(task_id, None)
                if etype == "text":
                    ttext = payload.get("content")
                    if isinstance(ttext, str):
                        ttext = _strip_interrupted(ttext)
                    if isinstance(ttext, str) and ttext:
                        text_pieces.append(ttext)
                elif etype == "reasoning":
                    rtext = payload.get("reasoning_content")
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
            if watchdog_reason:
                state = watchdog_reason[0]
                err_lines.append(f"opencode run watchdog: {state}")
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
        if watchdog_reason:
            rc = 1
        if state == "stdout_overflow" and not had_output:
            rc = max(rc, 1)
        transient_failure = (
            bool(watchdog_reason)
            or had_error
            or (
                not had_output
                and _is_retryable_failure(rc, err_tail, provider_status, False)
            )
        )
        if self.attempts is not None:
            self.attempts.attempt_done(
                transient_failure,
                had_output and not transient_failure and state != "timeout",
            )
        elif transient_failure:
            self.res.breaker.record_failure()
        elif had_output and state != "timeout":
            self.res.breaker.record_success()
        return {
            "rc": rc,
            "text": text,
            "chunks": list(text_pieces),
            "native_calls": native_calls,
            "reasoning": reasoning,
            "usage": usage,
            "err": err_tail,
            "provider_status": provider_status,
            "had_output": had_output,
            "had_error": had_error,
            "fatal_error": fatal_error,
            "state": state,
            "finish": "stop" if text else "error",
            "first_event_at": first_event_at,
            "first_token_at": first_token_at,
        }


class _LockedWfile:
    """wfile потокового запроса под общим замком с конечным таймаутом записи клиенту.

    Запись ограничена `_DOWNSTREAM_WRITE_TIMEOUT_S` и остатком дедлайна запроса;
    `abort_socket` прерывает зависшую запись shutdown/close без замка.
    """

    def __init__(
        self,
        inner: io.BufferedIOBase,
        lock: threading.Lock | threading.RLock,
        sock: socket.socket | None = None,
        deadline: float | None = None,
        deadline_fn: Callable[[], float | None] | None = None,
        on_client_gone: Callable[[], None] | None = None,
    ) -> None:
        self._inner: io.BufferedIOBase = inner
        self._lock: threading.Lock | threading.RLock = lock
        self._sock: socket.socket | None = sock
        self._deadline: float | None = deadline
        self._deadline_fn: Callable[[], float | None] | None = deadline_fn
        self._on_client_gone: Callable[[], None] | None = on_client_gone
        self.client_gone: bool = False
        self._timer: threading.Timer | None = None
        # Авто-abort ровно на дедлайне не делается: обработчик ещё шлёт финальную
        # timeout-ошибку клиенту. Зависшая запись ограничена таймаутом сокета в
        # write/flush, а abort_socket доступен внешнему watchdog/таймеру.

    def _effective_deadline(self) -> float | None:
        """Дедлайн записи: явный или от deadline_fn."""
        if self._deadline_fn is not None:
            return self._deadline_fn()
        return self._deadline

    def _apply_write_timeout(self) -> None:
        """Ограничить сокет остатком дедлайна и downstream-таймаутом, если умеет."""
        sock = self._sock
        if sock is None:
            return
        set_timeout = getattr(sock, "settimeout", None)
        if not callable(set_timeout):
            return
        effective_deadline = self._effective_deadline()
        if effective_deadline is None:
            timeout = _DOWNSTREAM_WRITE_TIMEOUT_S
        else:
            remaining = effective_deadline - time.monotonic()
            timeout = min(_DOWNSTREAM_WRITE_TIMEOUT_S, max(0.05, remaining))
        try:
            _ = set_timeout(timeout)
        except OSError:
            pass

    def _mark_client_gone(self) -> None:
        """Отметить уход клиента один раз и уведомить обработчик запроса."""
        if self.client_gone:
            return
        self.client_gone = True
        try:
            if self._on_client_gone is not None:
                try:
                    self._on_client_gone()
                except Exception as exc:
                    _log(f"client_gone callback error: {_mask_secrets(str(exc))}")
        finally:
            self.abort_socket()

    def cancel_deadline_timer(self) -> None:
        """Отменить watchdog-таймер дедлайна при штатном завершении запроса."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def abort_socket(self) -> None:
        """Прервать клиентский сокет без замка записи (доступно watchdog/таймеру)."""
        if not self.client_gone:
            self._mark_client_gone()
            return
        sock = self._sock
        if sock is None:
            return
        try:
            _ = sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def write(self, data: bytes) -> int:
        """Записать чанк целиком под замком с ограниченным ожиданием сокета."""
        try:
            with self._lock:
                self._apply_write_timeout()
                return int(self._inner.write(data) or 0)
        except (OSError, ValueError) as exc:
            self.abort_socket()
            if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
                raise
            raise BrokenPipeError(errno.EPIPE, "downstream write failed") from exc

    def flush(self) -> None:
        """Сбросить буфер под замком с ограниченным ожиданием сокета."""
        try:
            with self._lock:
                self._apply_write_timeout()
                self._inner.flush()
        except (OSError, ValueError) as exc:
            self.abort_socket()
            if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
                raise
            raise BrokenPipeError(errno.EPIPE, "downstream flush failed") from exc

    def __getattr__(self, name: str) -> object:
        """Прочие атрибуты (closed, close, fileno) — у исходного wfile."""
        return cast(object, getattr(self._inner, name))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 300

    def log_message(self, format: str, *args: Any) -> None:
        _log("http " + (format % args))

    def handle_error(self, request: Any, client_address: Any) -> None:
        _log(f"http accept error from {client_address}")

    _xs: dict[str, Any] | None = None
    _serve_stream_usage: dict[str, int] | None = None
    _first_visible: threading.Event | None = None
    _downstream_client_gone: bool = False

    def _exit(self) -> dict[str, Any]:
        """Состояние выхода текущего запроса для структурной строки O-EXIT/v1."""
        if self._xs is None:
            self._xs = _new_exit_state()
        return self._xs

    def _res(self) -> _Resilience:
        """Защиты сервера (слоты, breaker, budget, лимитер); у `Server` — свои, иначе модульные."""
        return cast(
            "_Resilience",
            getattr(getattr(self, "server", None), "resilience", None)
            or _DEFAULT_RESILIENCE,
        )

    def _acquire_slot(self, res: _Resilience) -> bool:
        """Слот с ограниченным ожиданием; отказ -> 503 overloaded (таймаут 15 с или 13-й ждущий мгновенно)."""
        verdict = res.slots.acquire_ex()
        if verdict == "ok":
            return True
        self._exit()["exit_reason"] = (
            "slot_timeout" if verdict == "timeout" else "slot_overflow"
        )
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
        _ = self.wfile.write(
            ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode(
                "utf-8"
            )
        )
        _ = self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _client_gone_check(self) -> bool:
        """Клиент закрыл сокет: FIN/RST виден peek без чтения данных."""
        if self._downstream_client_gone:
            return True
        try:
            dup_fd = os.dup(self.rfile.fileno())
        except AttributeError:
            return False
        except (OSError, ValueError):
            return True
        try:
            conn_obj = socket.socket(fileno=dup_fd)
            try:
                ready, _w, _x = select.select([conn_obj], [], [], 0)
                if not ready:
                    return False
                data = conn_obj.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
                return data == b""
            finally:
                os.close(conn_obj.detach())
        except OSError as exc:
            # EAGAIN/EWOULDBLOCK — данных нет; ECONNRESET/EPIPE/EBADF — клиент сброшен.
            return exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK)
        except ValueError:
            return True

    def _run_serve_stream_attempts(
        self,
        model: str,
        prompt: str,
        effort: str,
        emulate_tools: bool,
        tools: list[dict[str, object]] | None,
        resp_id: str,
        created: int,
        shown_model: str,
        emit_content: Callable[[str], None],
        emit_parsed_content: Callable[[str], None],
        emit_tool_call: Callable[[dict[str, object]], None],
        attempts: _RequestAttempts,
        res: _Resilience,
        xs: dict[str, object],
        collected_texts: list[str],
        tool_choice: object = None,
    ) -> bool:
        """Serve-попытки для SSE; True — запрос завершён, False — fallback на run."""
        thinking = effort.strip().lower() not in ("", "off", "none")
        workdir = DEFAULTWORKDIR
        workdir.mkdir(parents=True, exist_ok=True)
        last_reasoning: list[str] = [""]
        collected_reasonings: list[str] = []
        # Барьер доставки монотонен на весь запрос: модельный чанк, ушедший клиенту, не снимается.
        delivered_any = [False]
        first_visible = self._first_visible or threading.Event()

        def on_status(text: str) -> None:
            """Синтетический статус с ведущим LF после незавершённой строки модели."""
            prefix = (
                "\n"
                if last_reasoning[0] and not last_reasoning[0].endswith("\n")
                else ""
            )
            chunk = format_sse_chunk(
                resp_id, created, shown_model, {"reasoning_content": prefix + text}
            )
            first_visible.set()
            _ = self.wfile.write(chunk.encode("utf-8"))
            self.wfile.flush()

        def attempt_status(text: str) -> None:
            """Статусы попытки; STATUS_INITIAL отдаёт только защитный таймер запроса."""
            if text == STATUS_INITIAL and self._first_visible is not None:
                return
            on_status(text)

        def on_reasoning(text: str) -> None:
            """Модельное размышление клиенту без модификации байтов."""
            if not text:
                return
            last_reasoning[0] = text
            collected_reasonings.append(text)
            delivered_any[0] = True
            first_visible.set()
            chunk = format_sse_chunk(
                resp_id, created, shown_model, {"reasoning_content": text}
            )
            _ = self.wfile.write(chunk.encode("utf-8"))
            self.wfile.flush()

        parser_box: list[ToolCallParser | None] = [None]
        _inter_buf_text: list[str] = [""]  # буфер потокового фильтра split-маркеров

        def on_text(text: str) -> None:
            """Модельный текст через ToolCallParser при эмуляции (с потоковым фильтром маркеров)."""
            _inter_buf_text[0] += text
            buf = _inter_buf_text[0]
            # Удерживаем только возможный префикс маркера либо его незавершённую строку.
            cut = len(buf)
            folded = buf.lower()
            for marker in (
                "i was interrupted right before making tool calls",
                "the previous response was interrupted. continue from where you left off without repeating completed content",
            ):
                pos = folded.find(marker)
                if pos >= 0 and "\n" not in buf[pos:]:
                    cut = min(cut, pos)
                for size in range(1, min(len(marker), len(buf)) + 1):
                    if folded.endswith(marker[:size]):
                        cut = min(cut, len(buf) - size)
            cleaned = _strip_interrupted(buf[:cut])
            _inter_buf_text[0] = buf[cut:]
            if not cleaned:
                return
            if parser_box[0] is not None:
                parser_box[0].feed(cleaned)
            else:
                emit_content(cleaned)

        def _flush_inter_buf() -> None:
            """Сброс остатка буфера после завершения попытки."""
            if not _inter_buf_text[0]:
                return
            cleaned = _strip_interrupted(_inter_buf_text[0])
            _inter_buf_text[0] = ""
            if not cleaned:
                return
            if parser_box[0] is not None:
                parser_box[0].feed(cleaned)
            else:
                emit_content(cleaned)

        unmapped_in_attempt: list[str] = []
        emitted_tools_in_attempt = [0]

        def on_tool(payload: dict[str, object]) -> None:
            """Native serve-вызов в DSH tool_call."""
            part = _as_dict(payload.get("part"))
            mapped = _native_call_as_dsh(payload, tools) if emulate_tools else []
            if not mapped and emulate_tools and part.get("tool"):
                unmapped_in_attempt.append(str(part.get("tool")))
            for call in mapped:
                emitted_tools_in_attempt[0] += 1
                delivered_any[0] = True
                emit_tool_call(call)

        def on_parsed_tool(call: dict[str, object]) -> None:
            """Вызов из текста модели: учесть в счётчике эмиссии попытки."""
            emitted_tools_in_attempt[0] += 1
            delivered_any[0] = True
            emit_tool_call(call)

        force_serve = (
            os.environ.get("OPENCODE_ZEN_BRIDGE_TRANSPORT", "").strip().lower()
            == "serve"
        )
        current_prompt = prompt
        serve_attempts = 0
        unmapped_retries = 0
        incomplete_retries = 0
        while True:
            unmapped_in_attempt.clear()
            emitted_tools_in_attempt[0] = 0
            _inter_buf_text[0] = ""  # сброс буфера split-маркеров на каждую попытку
            if parser_box[0] is not None:
                parser_box[0].finish()
            parser_box[0] = (
                ToolCallParser(emit_parsed_content, on_parsed_tool)
                if emulate_tools
                else None
            )
            if attempts.remaining_s() <= 0:
                attempts.attempt_done(False, False)
                xs["exit_reason"] = "timeout"
                self._sse_error(_error_payload("opencode timeout"))
                return True
            if attempts.total_spawns >= MAX_TOTAL_SPAWNS or not attempts.can_spawn():
                xs["exit_reason"] = "upstream_failed"
                self._sse_error(_error_payload("serve spawn limit reached"))
                return True
            _orig_reasoning, _orig_text = on_reasoning, on_text

            _prior_text = "".join(collected_texts)
            _dedup_text = (
                _PrefixDedup(_prior_text) if serve_attempts and _prior_text else None
            )

            def _text_seen(text: str, _f: Callable[[str], None] = _orig_text) -> None:
                if _dedup_text is not None:
                    text = _dedup_text.push(text)
                    if not text:
                        return
                delivered_any[0] = True
                _f(text)

            gate = _StartupGate()
            _aux_started = attempts.aux_budget.now_s()
            try:
                gate.acquire(
                    deadline=attempts.aux_budget.deadline(attempts.deadline),
                    is_client_gone=self._client_gone_check,
                )
            finally:
                attempts.aux_budget.debit_elapsed(_aux_started)
            _aux_started = attempts.aux_budget.now_s()
            try:
                _limiter_ok = res.spawn_limiter.acquire(
                    max_wait_s=min(
                        SPAWN_WAIT_MAX_S,
                        attempts.remaining_s(),
                        attempts.aux_budget.remaining_s(),
                    ),
                    deadline=attempts.aux_budget.deadline(attempts.deadline),
                    is_client_gone=self._client_gone_check,
                )
            finally:
                attempts.aux_budget.debit_elapsed(_aux_started)
            _aux_dead = attempts.aux_budget.exhausted()
            if (
                not _limiter_ok
                or _aux_dead
                or self._client_gone_check()
                or attempts.remaining_s() <= 0
            ):
                gate.release()
                if _limiter_ok:
                    res.spawn_limiter.refund()
                if (
                    self._client_gone_check()
                    or attempts.remaining_s() <= 0
                    or _aux_dead
                ):
                    attempts.attempt_done(False, False)
                    xs["exit_reason"] = (
                        "client_gone" if self._client_gone_check() else "timeout"
                    )
                    if xs["exit_reason"] == "timeout":
                        self._sse_error(_error_payload("opencode timeout"))
                    return True
                if not force_serve and not delivered_any[0]:
                    return False
                xs["exit_reason"] = "upstream_failed"
                self._sse_error(_error_payload("serve spawn limiter timeout"))
                return True
            attempts.note_spawn()
            if serve_attempts and first_visible.is_set() and thinking:
                # Единая точка разделителя: ровно один на каждый повтор, только в thinking-режиме.
                on_status(
                    f"[мост] Повтор попытки {attempts.total_spawns}/{attempts.max_total}…\n"
                )
            serve_attempts += 1
            try:
                result = _serve_one_attempt(
                    model,
                    current_prompt,
                    effort,
                    workdir,
                    _orig_reasoning,
                    _text_seen,
                    on_tool,
                    attempts.deadline - TIMEOUT_S,
                    is_client_gone=self._client_gone_check,
                    on_status=attempt_status,
                    thinking_enabled=thinking,
                    deadline=attempts.deadline,
                    on_startup_ready=gate.release,
                    emulate_tools=emulate_tools,
                    aux_budget=attempts.aux_budget,
                )
            except ServeUnavailable as exc:
                res.serve_health.record_failure()
                if not force_serve and not delivered_any[0]:
                    xs["transport"] = "run"
                    xs["transport_history"] = ["serve", "run"]
                    return False
                xs["exit_reason"] = "upstream_failed"
                self._sse_error(_error_payload(f"serve unavailable: {exc}"))
                return True
            except ServeSecurityError as exc:
                xs["exit_reason"] = "provider_fatal"
                self._sse_error(_error_payload(f"serve security failure: {exc}"))
                return True
            finally:
                gate.release()
            _flush_inter_buf()
            usage_acc = self._serve_stream_usage or {}
            for key in ("input", "output", "cached", "reasoning"):
                usage_acc[key] = int(usage_acc.get(key) or 0) + int(
                    result["usage"].get(key) or 0
                )
            self._serve_stream_usage = usage_acc
            usage_cur = result["usage"]
            if "first_event_ms" not in xs or xs.get("first_event_ms") is None:
                xs["first_event_ms"] = result["first_event_ms"]
            if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
                xs["ttft_ms"] = result["ttft_ms"]
            if parser_box[0] is not None:
                parser_box[0].finish()
            if result.get("exit_reason") == "client_gone":
                attempts.attempt_done(False, False)
                xs["exit_reason"] = "client_gone"
                return True
            if result.get("exit_reason") == "timeout":
                attempts.attempt_done(False, False)
                xs["exit_reason"] = "timeout"
                self._sse_error(_error_payload("opencode timeout"))
                return True
            if "first_event_ms" not in xs or xs.get("first_event_ms") is None:
                xs["first_event_ms"] = result["first_event_ms"]
            if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
                xs["ttft_ms"] = result["ttft_ms"]
            _delivered_now = bool(
                delivered_any[0]
                or result.get("delivered")
                or result["texts"]
                or result["reasonings"]
                or result["native_calls"]
            )
            delivered_any[0] = _delivered_now
            if result.get("exit_reason") in (
                "first_event_timeout",
                "first_token_timeout",
                "stall_timeout",
                "invalid_serve_event",
                "prompt_error",
                "eof_before_step_finish",
            ):
                reason = str(result["exit_reason"])
                if reason in ("first_event_timeout", "invalid_serve_event"):
                    res.serve_health.record_failure()
                else:
                    attempts.attempt_done(True, False)
                if not _delivered_now and not force_serve:
                    xs["transport"] = "run"
                    xs["transport_history"] = ["serve", "run"]
                    return False
                if attempts.allow_retry(reason):
                    continue
                xs["exit_reason"] = reason
                self._sse_error(_error_payload(f"serve {reason}"))
                return True
            if result.get("prompt_status") is not None:
                _ps_code = int(result["prompt_status"] or 0)
                if _ps_code == 429 or 500 <= _ps_code <= 599:
                    attempts.attempt_done(True, False)
                if not _delivered_now and not force_serve:
                    xs["transport"] = "run"
                    xs["transport_history"] = ["serve", "run"]
                    return False
                if attempts.allow_retry(f"prompt_status_{_ps_code}"):
                    continue
                xs["exit_reason"] = f"prompt_status_{_ps_code}"
                self._sse_error(_error_payload(f"serve prompt HTTP {_ps_code}"))
                return True
            if result.get("exit_reason") in ("prompt_status_429",):
                attempts.attempt_done(True, False)
                if attempts.allow_retry("prompt_status_429"):
                    continue
                xs["exit_reason"] = "prompt_status_429"
                self._sse_error(_error_payload("serve prompt HTTP 429"))
                return True
            if result["error"] is not None:
                err = result["error"]
                if result.get("transient_error"):
                    attempts.attempt_done(True, False)
                    _has_model_output = bool(
                        collected_texts
                        or collected_reasonings
                        or result.get("native_calls")
                    )
                    _delivered_err = _delivered_now or _has_model_output
                    if not _has_model_output and attempts.allow_retry(
                        "serve_transient_error"
                    ):
                        continue
                    if not _delivered_err and not force_serve:
                        xs["transport"] = "run"
                        xs["transport_history"] = ["serve", "run"]
                        return False
                    # После частичной доставки: step-interruption recovery ниже по incomplete-сигналу.
                    signal_t = _incomplete_step_signal(
                        "".join(result["texts"]),
                        "".join(result["reasonings"]),
                        tools or [],
                        True,
                        int(result["usage"].get("output") or 0),
                        int(result["usage"].get("reasoning") or 0),
                        tool_choice=tool_choice,
                    )
                    if signal_t and attempts.allow_retry("incomplete_step"):
                        attempts.signal = signal_t
                        current_prompt = _rewrite_tool_tags_for_model(
                            _incomplete_tool_step_prompt(
                                prompt,
                                "".join(collected_texts),
                                tools or [],
                                tool_choice,
                                model,
                            ),
                            model,
                        )
                        continue
                xs["exit_reason"] = "upstream_failed"
                self._sse_error(
                    _error_payload(
                        f"serve error: {_clean_err(str(err.get('message') or ''))}"
                    )
                )
                return True
            if result.get("terminal") == "cancelled":
                xs["exit_reason"] = "cancelled"
                self._sse_error(_error_payload("serve session cancelled"))
                return True
            res.serve_health.record_success()
            attempts.attempt_done(False, True)
            if emulate_tools and emitted_tools_in_attempt[0] == 0:
                if unmapped_in_attempt:
                    if unmapped_retries < NATIVE_RETRY_LIMIT and attempts.allow_retry(
                        "unmapped"
                    ):
                        unmapped_retries += 1
                        current_prompt = _rewrite_tool_tags_for_model(
                            _unavailable_tools_prompt(
                                current_prompt,
                                "".join(result["texts"]),
                                unmapped_in_attempt,
                                tools or [],
                                model,
                            ),
                            model,
                        )
                        continue
                    emit_content(
                        f"\n\n[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент ({', '.join(unmapped_in_attempt)}); повторы исчерпаны]"
                    )
                    return True
                signal = _incomplete_step_signal(
                    "".join(result["texts"]),
                    (
                        _strip_interrupted("".join(result["reasonings"]))
                        if "".join(result["texts"]).strip()
                        else "".join(result["reasonings"])
                    ),
                    tools or [],
                    False,
                    int(usage_cur.get("output") or 0),
                    int(usage_cur.get("reasoning") or 0),
                    tool_choice=tool_choice,
                )
                if (
                    signal
                    and incomplete_retries < NATIVE_RETRY_LIMIT
                    and attempts.allow_retry("incomplete_step")
                ):
                    incomplete_retries += 1
                    attempts.signal = signal
                    current_prompt = _rewrite_tool_tags_for_model(
                        _incomplete_tool_step_prompt(
                            prompt,
                            "".join(collected_texts),
                            tools or [],
                            tool_choice,
                            model,
                        ),
                        model,
                    )
                    continue
            return True

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
        xs["transport"] = "run"
        xs["transport_history"] = ["run"]
        launcher = _resolve_launcher()
        if not os.access(launcher, os.X_OK):
            xs["exit_reason"] = "launcher_missing"
            self._send(
                502,
                {
                    "error": {
                        "message": f"opencode launcher not executable: {launcher}",
                        "type": "proxy_error",
                        "code": 502,
                    }
                },
            )
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
        _log(
            f"stream exec model={model_route} {shown} prompt_chars={len(prompt)} cwd={workdir}"
        )

        proc: subprocess.Popen[str] | None = None
        feed: _StdoutFeed | None = None
        gate: _StartupGate | None = None
        run_id = uuid.uuid4().hex[:8]
        # Записи в wfile сериализуются общим замком; first_visible подавляет таймер статуса.
        wfile_lock = threading.RLock()
        first_visible = threading.Event()
        status_fired_at = [0.0]
        raw_wfile = self.wfile
        status_timer: threading.Timer | None = None

        try:
            if not attempts.begin_attempt():
                xs["exit_reason"] = "circuit_open"
                self._send(
                    503,
                    {
                        "error": {
                            "message": "upstream circuit open",
                            "type": "overloaded",
                        }
                    },
                )
                return

            self._downstream_client_gone = False

            def _mark_downstream_gone() -> None:
                """Downstream-запись признала клиента ушедшим: остановить serve."""
                self._downstream_client_gone = True

            locked_wfile = _LockedWfile(
                raw_wfile,
                wfile_lock,
                sock=cast(
                    "socket.socket | None",
                    cast(object, getattr(self, "connection", None)),
                ),
                deadline=attempts.deadline,
                on_client_gone=_mark_downstream_gone,
            )
            locked_wfile.flush()
            self.wfile = cast(io.BufferedIOBase, cast(object, locked_wfile))

            # 1. Отправляются HTTP-заголовки 200 SSE
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            try:
                self.end_headers()
                xs["status"] = 200
                first_chunk = format_sse_chunk(
                    resp_id, created, shown_model, {"role": "assistant", "content": ""}
                )
                _ = self.wfile.write(first_chunk.encode("utf-8"))
                self.wfile.flush()
            except (OSError, ValueError, TimeoutError, socket.timeout):
                locked_wfile.abort_socket()
                xs["exit_reason"] = "client_gone"
                return

            self._first_visible = first_visible

            def _initial_status() -> None:
                """Защитный таймер: первый видимый статус не позднее FIRST_STATUS_DELAY_S."""
                with wfile_lock:
                    if first_visible.is_set():
                        return
                    first_visible.set()
                    status_fired_at[0] = time.monotonic()
                    try:
                        _ = locked_wfile.write(
                            format_sse_chunk(
                                resp_id,
                                created,
                                shown_model,
                                {"reasoning_content": STATUS_INITIAL},
                            ).encode("utf-8")
                        )
                        locked_wfile.flush()
                    except (OSError, ValueError, TimeoutError, socket.timeout):
                        locked_wfile.abort_socket()

            if effort.strip().lower() not in ("", "off", "none"):
                status_timer = threading.Timer(
                    max(
                        0.0,
                        attempts.deadline
                        - TIMEOUT_S
                        + FIRST_STATUS_DELAY_S
                        - time.monotonic(),
                    ),
                    _initial_status,
                )
                status_timer.daemon = True
                status_timer.start()

            collected_texts: list[str] = []
            usage: dict[str, Any] = {}
            deadline = attempts.deadline
            tool_calls: list[dict[str, Any]] = []

            # Повтор незавершённого шага: уже отданный клиенту текст (dedup_prefix) подавляется,
            # расхождение (модель переформулировала) отдаётся целиком — текст не теряется.
            dedup: list[_PrefixDedup | None] = [None]

            def send_text(text: str) -> None:
                chunk = format_sse_chunk(
                    resp_id, created, shown_model, {"content": text}
                )
                first_visible.set()
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

            dropped_blocks = [
                0
            ]  # вырезано нераспарсенных блоков вызова (счётчик на запрос)

            def emit_parsed_content(text: str) -> None:
                # Нераспарсенный блок ToolCallParser отдаёт одним куском: сырой тег не уходит ни в SSE, ни в повтор.
                cleaned, dropped = _strip_broken_tool_blocks(text)
                if dropped:
                    dropped_blocks[0] += dropped
                    _log(
                        f"stream dropped {dropped} unparsed tool block(s) from content"
                    )
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
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                    },
                }
                tool_calls.append(tc)
                chunk = format_sse_chunk(
                    resp_id, created, shown_model, {"tool_calls": [tc]}
                )
                first_visible.set()
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()

            with _active_lock:
                _active[run_id] = time.time()

            if _select_transport(res) == "serve":
                xs["transport"] = "serve"
                xs["transport_history"] = ["serve"]
                self._serve_stream_usage = None
                handled = self._run_serve_stream_attempts(
                    model,
                    prompt,
                    effort,
                    emulate_tools,
                    tools,
                    resp_id,
                    created,
                    shown_model,
                    emit_content,
                    emit_parsed_content,
                    emit_tool_call,
                    attempts,
                    res,
                    xs,
                    collected_texts,
                    tool_choice=tool_choice
                    if isinstance(tool_choice, (str, dict)) or tool_choice is None
                    else None,
                )
                if handled:
                    if xs.get("exit_reason"):
                        return
                    serve_usage = self._serve_stream_usage or {}
                    for key in ("input", "output", "cached", "reasoning"):
                        if serve_usage.get(key):
                            usage[key] = int(usage.get(key) or 0) + serve_usage[key]
                    full_text_s = "".join(collected_texts)
                    final_s = format_sse_chunk(
                        resp_id,
                        created,
                        shown_model,
                        {},
                        finish_reason="tool_calls" if tool_calls else "stop",
                        usage=_build_openai_usage(
                            int(usage.get("input") or 0) or _estimate_tokens(prompt),
                            int(usage.get("output") or 0)
                            or _estimate_tokens(full_text_s),
                            int(usage.get("cached") or 0),
                            int(usage.get("reasoning") or 0),
                        ),
                    )
                    _ = self.wfile.write(final_s.encode("utf-8"))
                    _ = self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                    xs.update(
                        exit_reason="ok",
                        tools=len(tool_calls),
                        out_chars=len(full_text_s),
                        rc=0,
                    )
                    return
                xs["transport"] = "run"

            attempt_prompt = prompt
            retries = 0  # повторов с новым промптом: встроенный инструмент / незавершённый шаг (для лога)
            unmapped_retries = 0
            incomplete_retries = 0
            fail_retries = 0
            incomplete_retry = False
            failure: dict[str, Any] | None = None
            while True:
                if attempts.total_spawns >= MAX_TOTAL_SPAWNS:
                    failure = {"rc": -1, "tail": "", "timeout": False}
                    break
                # 3. Запускается proc (повтор — встроенный инструмент без DSH-двойника,
                #    незавершённый шаг или транзиторный отказ CLI без вывода) под потолком MAX_TOTAL_SPAWNS
                if attempts.total_spawns:
                    _log(
                        f"stream exec retry={retries} fail_retries={fail_retries} model={model_route} "
                        f"prompt_chars={len(attempt_prompt)} total_spawns={attempts.total_spawns}/{attempts.max_total}"
                    )
                gate = _StartupGate()
                gate.acquire(
                    deadline=attempts.deadline, is_client_gone=self._client_gone_check
                )
                if not res.spawn_limiter.acquire(
                    max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s()),
                    deadline=attempts.deadline,
                    is_client_gone=self._client_gone_check,
                ):
                    gate.release()
                    if self._client_gone_check() or attempts.remaining_s() <= 0:
                        attempts.attempt_done(False, False)
                        xs["exit_reason"] = (
                            "client_gone" if self._client_gone_check() else "timeout"
                        )
                        if xs["exit_reason"] == "timeout":
                            self._sse_error(_error_payload("opencode timeout"))
                        return
                    _log(
                        "stream spawn skipped: spawn rate limiter wait exceeds the request deadline"
                    )
                    if not collected_texts and not tool_calls:
                        failure = {"rc": -1, "tail": "", "timeout": True}
                    break
                if self._client_gone_check() or attempts.remaining_s() <= 0:
                    res.spawn_limiter.refund()
                    gate.release()
                    attempts.attempt_done(False, False)
                    xs["exit_reason"] = (
                        "client_gone" if self._client_gone_check() else "timeout"
                    )
                    if xs["exit_reason"] == "timeout":
                        self._sse_error(_error_payload("opencode timeout"))
                    return
                try:
                    # env на каждую попытку: ретрай получает следующий порт пула (чистый IP)
                    proc = _spawn_with_stdin(
                        cmd, attempt_prompt, workdir, _run_env(model)
                    )
                except OSError as exc:
                    res.spawn_limiter.refund()
                    gate.release()
                    _log(f"stream spawn failed: {exc}")
                    xs["exit_reason"] = "spawn_failed"
                    self._sse_error(_error_payload(f"opencode spawn failed: {exc}"))
                    return
                attempts.note_spawn()

                err_lines: list[str] = []

                err_thread = threading.Thread(
                    target=_drain_stderr, args=(proc, err_lines), daemon=True
                )
                err_thread.start()

                parser = (
                    ToolCallParser(emit_parsed_content, emit_tool_call)
                    if emulate_tools
                    else None
                )
                attempt_texts: list[str] = []
                attempt_reasonings: list[str] = []
                unmapped: list[str] = []
                attempt_output = False  # любой полезный вывод этого прогона (текст/мышление/инструмент)
                attempt_output_tokens = (
                    0  # output из step_finish этого прогона (для проглоченных вызовов)
                )
                attempt_reasoning_tokens = (
                    0  # reasoning из step_finish (output включает reasoning)
                )
                provider_status: int | None = None
                had_provider_error = (
                    False  # транзиентная ошибка посреди ответа (had_mid_stream_error)
                )
                fatal_mid_error = (
                    False  # детерминированная ошибка посреди ответа: без повтора
                )
                stopped_on_error = False
                prior_text = "".join(collected_texts)
                dedup[0] = (
                    _PrefixDedup(prior_text)
                    if incomplete_retry and prior_text
                    else None
                )

                attempt_start = time.monotonic()
                first_status_due = attempts.deadline - TIMEOUT_S + FIRST_STATUS_DELAY_S
                watchdog_state: _WatchdogState = {
                    "reason": "",
                    "first_event_at": None,
                    "first_token_at": None,
                    "last_token_at": attempt_start,
                    "status_next": (
                        first_status_due
                        if attempts.total_spawns <= 1 and not status_fired_at[0]
                        else attempt_start + FIRST_STATUS_DELAY_S
                    ),
                    "last_keepalive": attempt_start,
                    "last_reasoning": "",
                }
                thinking_enabled = effort.strip().lower() not in ("", "off", "none")

                def emit_synthetic(text: str) -> None:
                    """Синтетический статус отдельной reasoning-дельтой."""
                    tail = str(watchdog_state.get("last_reasoning") or "")
                    prefix = "\n" if tail and not tail.endswith("\n") else ""
                    chunk_s = format_sse_chunk(
                        resp_id,
                        created,
                        shown_model,
                        {"reasoning_content": prefix + text},
                    )
                    first_visible.set()
                    _ = self.wfile.write(chunk_s.encode("utf-8"))
                    self.wfile.flush()

                def send_keepalive(proc: subprocess.Popen[str] = proc) -> None:
                    """Надзор: статусы, watchdog и обнаружение ухода клиента."""
                    now_s = time.monotonic()
                    if self._client_gone_check():
                        _log("stream client gone, killing proc group")
                        _stop_proc(proc)
                        raise BrokenPipeError("client gone")
                    if watchdog_state[
                        "first_event_at"
                    ] is None and now_s - attempt_start > float(FIRST_EVENT_TIMEOUT_S):
                        watchdog_state["reason"] = "first_event_timeout"
                        _stop_proc(proc)
                        return
                    if (
                        watchdog_state["first_event_at"] is not None
                        and watchdog_state["first_token_at"] is None
                        and now_s - attempt_start > float(FIRST_TOKEN_TIMEOUT_S)
                    ):
                        watchdog_state["reason"] = "first_token_timeout"
                        _stop_proc(proc)
                        return
                    if watchdog_state["first_token_at"] is not None and now_s - float(
                        watchdog_state["last_token_at"]
                    ) > float(STALL_TIMEOUT_S):
                        watchdog_state["reason"] = "stall_timeout"
                        _stop_proc(proc)
                        return
                    try:
                        if thinking_enabled and now_s >= float(
                            watchdog_state["status_next"]
                        ):
                            if watchdog_state["first_token_at"] is None:
                                if (
                                    not first_visible.is_set()
                                    and not status_fired_at[0]
                                ):
                                    _initial_status()
                                    watchdog_state["status_next"] = (
                                        now_s + STATUS_WAITING_INTERVAL_S
                                    )
                                elif (
                                    status_fired_at[0]
                                    and now_s - status_fired_at[0]
                                    < STATUS_WAITING_INTERVAL_S
                                ):
                                    # Защитный таймер уже отдал STATUS_INITIAL: без дубля.
                                    watchdog_state["status_next"] = (
                                        status_fired_at[0] + STATUS_WAITING_INTERVAL_S
                                    )
                                else:
                                    emit_synthetic(STATUS_WAITING)
                                    watchdog_state["status_next"] = (
                                        now_s + STATUS_WAITING_INTERVAL_S
                                    )
                            elif now_s - float(
                                watchdog_state["last_token_at"]
                            ) >= float(STALL_HEARTBEAT_INTERVAL_S):
                                emit_synthetic(STATUS_CONTINUATION)
                                watchdog_state["status_next"] = now_s + float(
                                    STALL_HEARTBEAT_INTERVAL_S
                                )
                        if (
                            now_s - float(watchdog_state["last_keepalive"])
                            >= KEEPALIVE_INTERVAL_S
                        ):
                            watchdog_state["last_keepalive"] = now_s
                            keepalive = format_sse_chunk(
                                resp_id, created, shown_model, {"content": ""}
                            )
                            _ = self.wfile.write(keepalive.encode("utf-8"))
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        _log("stream client gone during keepalive, killing proc group")
                        _stop_proc(proc)
                        raise

                feed = _StdoutFeed(proc)
                for raw in feed.lines(deadline, 0.25, send_keepalive):
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
                    if etype:
                        if watchdog_state["first_event_at"] is None:
                            watchdog_state["first_event_at"] = time.monotonic()
                            if (
                                "first_event_ms" not in xs
                                or xs.get("first_event_ms") is None
                            ):
                                xs["first_event_ms"] = int(
                                    (time.monotonic() - (attempts.deadline - TIMEOUT_S))
                                    * 1000
                                )
                        _token_text = str(
                            payload.get("reasoning_content")
                            or payload.get("content")
                            or ""
                        )
                        if _token_text.strip():
                            if watchdog_state["first_token_at"] is None:
                                watchdog_state["first_token_at"] = time.monotonic()
                                if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
                                    xs["ttft_ms"] = int(
                                        (
                                            time.monotonic()
                                            - (attempts.deadline - TIMEOUT_S)
                                        )
                                        * 1000
                                    )
                            watchdog_state["last_token_at"] = time.monotonic()
                            if etype == "reasoning":
                                watchdog_state["last_reasoning"] = _token_text
                    if etype == "reasoning":
                        rtext = payload.get("reasoning_content")
                        if isinstance(rtext, str):
                            if rtext:
                                payload["reasoning_content"] = rtext
                            else:
                                del payload["reasoning_content"]
                        if payload:
                            attempt_output = True
                            if isinstance(rtext, str) and rtext:
                                attempt_reasonings.append(rtext)
                            chunk_str = format_sse_chunk(
                                resp_id, created, shown_model, payload
                            )
                            first_visible.set()
                            self.wfile.write(chunk_str.encode("utf-8"))
                            self.wfile.flush()
                    elif etype == "text":
                        ttext = payload.get("content")
                        if isinstance(ttext, str):
                            ttext = _strip_interrupted(ttext)
                        if isinstance(ttext, str) and ttext:
                            attempt_output = True
                            if (
                                retries
                                and not incomplete_retry
                                and not attempt_texts
                                and collected_texts
                            ):
                                emit_content("\n\n")
                            attempt_texts.append(ttext)
                            if parser is not None:
                                parser.feed(ttext)
                            else:
                                emit_content(ttext)
                    elif etype == "step_finish":
                        if payload:
                            for key in ("input", "output", "cached", "reasoning"):
                                usage[key] = int(usage.get(key) or 0) + int(
                                    payload.get(key) or 0
                                )
                            attempt_output_tokens += int(payload.get("output") or 0)
                            attempt_reasoning_tokens += int(
                                payload.get("reasoning") or 0
                            )
                        if emulate_tools and tool_calls:
                            # Следующие шаги — реакция на «отклонение» (повтор вызова): не нужны.
                            _log(
                                "stream: step with tool call finished, stopping opencode run"
                            )
                            _stop_proc(proc)
                            break
                    elif etype == "error":
                        _log(
                            f"stream provider error: HTTP {payload.get('statusCode')}: {payload.get('message')}"
                        )
                        if isinstance(payload.get("statusCode"), int):
                            provider_status = payload["statusCode"]
                        err_lines.append(
                            f"HTTP {payload.get('statusCode')}: {payload.get('message')}"
                        )
                        if attempt_output:
                            # Оборванный ответ: иначе opencode сам запустит SYNTHETIC-шаг «Continue…» —
                            # останавливаем сразу. Транзиентная ошибка -> повтор шага, детерминированная
                            # (401…) -> ошибка клиенту без повтора. Ошибка до первого токена — не трогаем:
                            # opencode повторит сам или выйдет, и тогда флаг не должен «залипнуть».
                            if _is_transient_stream_error(payload):
                                had_provider_error = True
                            else:
                                fatal_mid_error = True
                            _log(
                                f"stream: provider error mid-response (transient={had_provider_error}), "
                                "stopping opencode run"
                            )
                            stopped_on_error = True
                            _stop_proc(proc)
                            break
                        _log("stream: early provider error (waiting for CLI recovery)")
                    elif etype == "tool_use":
                        attempt_output = True
                        part = _dict_or_empty(event.get("part"))
                        tstate = _dict_or_empty(part.get("state"))
                        calls = (
                            _native_to_tool_calls(
                                part.get("tool"), tstate.get("input"), tools or []
                            )
                            if emulate_tools
                            else []
                        )
                        _log(
                            f"opencode built-in tool event: tool={part.get('tool')} status={tstate.get('status')} "
                            f"mapped={bool(calls)} as={[c['name'] for c in calls]}"
                        )
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
                has_watchdog = bool(watchdog_state.get("reason"))
                transient_failure = (
                    has_watchdog
                    or had_provider_error
                    or (
                        not attempt_output
                        and _is_retryable_failure(rc, tail, provider_status, False)
                    )
                )
                attempts.attempt_done(
                    transient_failure, attempt_output and not transient_failure
                )
                if watchdog_state.get("reason"):
                    reason_w = str(watchdog_state["reason"])
                    if attempts.allow_retry(reason_w):
                        if thinking_enabled and (attempt_reasonings or attempt_texts):
                            emit_synthetic(
                                f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n"
                            )
                        continue
                    xs["exit_reason"] = reason_w
                    failure = {"rc": rc, "tail": "", "watchdog": reason_w}
                    break
                if timed_out:
                    failure = {"rc": rc, "tail": "", "timeout": True}
                    break
                if rc != 0 and not attempt_output:
                    _log(f"stream cli failed rc={rc} stderr_tail={tail!r}")
                    if (
                        fail_retries < FAIL_RETRY_LIMIT
                        and time.monotonic() < deadline
                        and _is_retryable_failure(
                            rc, tail, provider_status, bool(tool_calls)
                        )
                        and attempts.allow_retry(
                            "cli_failure", charge_budget=provider_status is not None
                        )
                    ):
                        fail_retries += 1
                        _log(
                            f"stream retry {fail_retries}/{FAIL_RETRY_LIMIT} after cli failure without output"
                        )
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
                    if (
                        unmapped_retries >= NATIVE_RETRY_LIMIT
                        or not attempts.allow_retry("unmapped")
                    ):
                        _log(
                            f"stream unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})"
                        )
                        emit_content(
                            f"\n\n[opencode-zen-bridge: модель вызывала недоступный встроенный "
                            f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]"
                        )
                        break
                    retries += 1
                    unmapped_retries += 1
                    incomplete_retry = True
                    _log(
                        f"stream unmapped built-in tools={unmapped}: re-prompt "
                        f"{unmapped_retries}/{NATIVE_RETRY_LIMIT}"
                    )
                    attempt_prompt = _rewrite_tool_tags_for_model(
                        _unavailable_tools_prompt(
                            attempt_prompt,
                            "".join(attempt_texts),
                            unmapped,
                            tools or [],
                            model,
                        ),
                        model,
                    )
                    if thinking_enabled and (attempt_reasonings or attempt_texts):
                        emit_synthetic(
                            f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n"
                        )
                    continue
                signal = (
                    0
                    if provider_status in _FATAL_HTTP
                    else _incomplete_step_signal(
                        "".join(attempt_texts),
                        _strip_interrupted("".join(attempt_reasonings)),
                        tools or [],
                        had_provider_error,
                        attempt_output_tokens,
                        attempt_reasoning_tokens,
                        tool_choice=tool_choice,
                    )
                )
                if not signal:
                    break
                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
                    "incomplete_step"
                ):
                    _log(
                        f"stream incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}"
                    )
                    break
                retries += 1
                incomplete_retries += 1
                incomplete_retry = True
                attempts.signal = signal
                _log(
                    f"stream incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
                    f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}"
                )
                attempt_prompt = _rewrite_tool_tags_for_model(
                    _incomplete_tool_step_prompt(
                        prompt,
                        "".join(collected_texts),
                        tools or [],
                        tool_choice,
                        model,
                    ),
                    model,
                )
                if thinking_enabled and (attempt_reasonings or attempt_texts):
                    emit_synthetic(
                        f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n"
                    )

            if failure is not None:
                _log(
                    f"stream failed model={model} rc={failure['rc']} fail_retries={fail_retries} "
                    f"total_spawns={attempts.total_spawns}"
                )
                if failure.get("timeout"):
                    xs["exit_reason"] = "timeout"
                    self._sse_error(
                        _error_payload(f"opencode timed out after {TIMEOUT_S:.0f}s")
                    )
                    return
                if failure.get("watchdog"):
                    wd_obj: object = failure.get("watchdog")
                    wd_reason = wd_obj if isinstance(wd_obj, str) else ""
                    xs["exit_reason"] = wd_reason
                    self._sse_error(_error_payload(f"opencode {wd_reason}"))
                    return
                xs["exit_reason"] = (
                    "provider_fatal" if failure.get("partial") else "upstream_failed"
                )
                what = (
                    "opencode provider error after partial output"
                    if failure.get("partial")
                    else "opencode run failed"
                )
                self._sse_error(
                    _error_payload(
                        f"{what} (rc={failure['rc']})"
                        + ("" if failure.get("partial") else " without output")
                        + (f": {failure['tail']}" if failure["tail"] else ""),
                        failure["tail"] if isinstance(failure["tail"], str) else "",
                    )
                )
                return

            if (
                dropped_blocks[0]
                and not tool_calls
                and not "".join(collected_texts).strip()
            ):
                emit_content(
                    _BROKEN_BLOCK_NOTICE
                )  # иначе клиент получил бы пустой ответ
            full_text = "".join(collected_texts)
            prompt_tokens = int(usage.get("input") or 0) or _estimate_tokens(prompt)
            completion_tokens = int(usage.get("output") or 0) or _estimate_tokens(
                full_text
            )

            final_chunk = format_sse_chunk(
                resp_id,
                created,
                shown_model,
                {},
                finish_reason="tool_calls" if tool_calls else "stop",
                usage=_build_openai_usage(
                    prompt_tokens,
                    completion_tokens,
                    int(usage.get("cached") or 0),
                    int(usage.get("reasoning") or 0),
                ),
            )
            self.wfile.write(final_chunk.encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            xs.update(
                exit_reason="ok",
                tools=len(tool_calls),
                out_chars=len(full_text),
                rc=proc.returncode if proc is not None else None,
            )
            _log(
                f"stream done model={model} rc={proc.returncode if proc is not None else None} tools={len(tool_calls)} "
                f"out_chars={len(full_text)} emulate_tools={emulate_tools} retries={retries} "
                f"total_spawns={attempts.total_spawns}"
            )

        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            _log(f"client gone mid-stream: {exc}")
            xs["exit_reason"] = "client_gone"
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                except OSError:
                    pass
        finally:
            # Таймер статуса не должен писать после завершения запроса.
            first_visible.set()
            if status_timer is not None:
                status_timer.cancel()
            if isinstance(self.wfile, _LockedWfile):
                self.wfile.cancel_deadline_timer()
            with wfile_lock:
                self.wfile = raw_wfile
            self._first_visible = None
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

    def _serve_json_serve(
        self,
        model: str,
        prompt: str,
        effort: str,
        emulate_tools: bool,
        tools: list[dict[str, object]] | None,
        reported_model: str | None,
        tool_choice: object,
        res: _Resilience,
        attempts: _RequestAttempts,
        xs: dict[str, object],
    ) -> bool:
        """JSON через serve; True — ответ отправлен, False — fallback на run."""
        thinking = effort.strip().lower() not in ("", "off", "none")
        force_serve = (
            os.environ.get("OPENCODE_ZEN_BRIDGE_TRANSPORT", "").strip().lower()
            == "serve"
        )
        workdir = DEFAULTWORKDIR
        workdir.mkdir(parents=True, exist_ok=True)
        current_prompt = prompt
        contents: list[str] = []
        reasonings_all: list[str] = []
        tool_calls_all: list[dict[str, object]] = []
        tokens: dict[str, int] = {}
        unmapped_retries = 0
        incomplete_retries = 0
        delivered_any = False
        _prior_content = ""
        _seen_call_keys: set[str] = set()

        def _save_partial_output(texts: list[str], reasonings: list[str]) -> None:
            """Сохранить частичный JSON-вывод без tool calls неуспешной попытки."""
            nonlocal _prior_content
            partial_content = "".join(texts)
            if emulate_tools and partial_content:
                partial_texts: list[str] = []

                def _discard_partial_call(_call: dict[str, object]) -> None:
                    """Не публиковать tool calls из неподтверждённой попытки."""
                    return None

                partial_parser = ToolCallParser(
                    partial_texts.append, _discard_partial_call
                )
                partial_parser.feed(partial_content)
                partial_parser.finish()
                partial_content = _strip_broken_tool_blocks("".join(partial_texts))[0]
            partial_content = _strip_interrupted(partial_content)
            repeated_prefix = bool(
                _prior_content and partial_content.startswith(_prior_content)
            )
            partial_content = _dedup_retry_text(_prior_content, partial_content)
            if partial_content:
                if repeated_prefix and contents:
                    contents[-1] += partial_content
                else:
                    contents.append(partial_content)
            reasonings_all.extend(reasonings)
            _prior_content = "\n\n".join(c for c in contents if c)

        def _add_call(call: dict[str, object]) -> None:
            """Вызов инструмента в итог: одинаковый (name, arguments) не дублируется."""
            key = _call_key(str(call["name"]), call["arguments"])
            if key in _seen_call_keys:
                return
            _seen_call_keys.add(key)
            tool_calls_all.append(
                {
                    "index": len(tool_calls_all),
                    "id": "call_" + uuid.uuid4().hex[:24],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                    },
                }
            )

        while True:
            if attempts.remaining_s() <= 0:
                attempts.attempt_done(False, False)
                xs["exit_reason"] = "timeout"
                self._send(502, _error_payload("opencode timeout"))
                return True
            if attempts.total_spawns >= MAX_TOTAL_SPAWNS or not attempts.can_spawn():
                xs["exit_reason"] = "upstream_failed"
                self._send(502, _error_payload("serve spawn limit reached"))
                return True
            reasonings: list[str] = []
            texts: list[str] = []
            natives: list[dict[str, object]] = []
            _gate_j = _StartupGate()
            _aux_started_j = attempts.aux_budget.now_s()
            try:
                _gate_j.acquire(
                    deadline=attempts.aux_budget.deadline(attempts.deadline),
                    is_client_gone=self._client_gone_check,
                )
            finally:
                attempts.aux_budget.debit_elapsed(_aux_started_j)
            _aux_started_j = attempts.aux_budget.now_s()
            try:
                limiter_ok = res.spawn_limiter.acquire(
                    max_wait_s=min(
                        SPAWN_WAIT_MAX_S,
                        attempts.remaining_s(),
                        attempts.aux_budget.remaining_s(),
                    ),
                    deadline=attempts.aux_budget.deadline(attempts.deadline),
                    is_client_gone=self._client_gone_check,
                )
            finally:
                attempts.aux_budget.debit_elapsed(_aux_started_j)
            _aux_dead_j = attempts.aux_budget.exhausted()
            if (
                not limiter_ok
                or _aux_dead_j
                or self._client_gone_check()
                or attempts.remaining_s() <= 0
            ):
                _gate_j.release()
                if limiter_ok:
                    res.spawn_limiter.refund()
                if (
                    self._client_gone_check()
                    or attempts.remaining_s() <= 0
                    or _aux_dead_j
                ):
                    attempts.attempt_done(False, False)
                    xs["exit_reason"] = (
                        "client_gone" if self._client_gone_check() else "timeout"
                    )
                    if xs["exit_reason"] == "timeout":
                        self._send(502, _error_payload("opencode timeout"))
                    return True
                _j_delivered = delivered_any or bool(
                    contents
                    or reasonings_all
                    or tool_calls_all
                    or texts
                    or reasonings
                    or natives
                )
                if not force_serve and not _j_delivered:
                    return False
                xs["exit_reason"] = "upstream_failed"
                self._send(502, _error_payload("serve spawn limiter timeout"))
                return True
            attempts.note_spawn()
            try:
                result = _serve_one_attempt(
                    model,
                    current_prompt,
                    effort,
                    workdir,
                    reasonings.append,
                    texts.append,
                    natives.append,
                    attempts.deadline - TIMEOUT_S,
                    is_client_gone=self._client_gone_check,
                    on_status=lambda _t: None,
                    thinking_enabled=thinking,
                    deadline=attempts.deadline,
                    on_startup_ready=_gate_j.release,
                    emulate_tools=emulate_tools,
                    aux_budget=attempts.aux_budget,
                )
            except ServeUnavailable as exc:
                res.serve_health.record_failure()
                _j_delivered = delivered_any or bool(
                    contents
                    or reasonings_all
                    or tool_calls_all
                    or texts
                    or reasonings
                    or natives
                )
                if not force_serve and not _j_delivered:
                    return False
                xs["exit_reason"] = "upstream_failed"
                self._send(502, _error_payload(f"serve unavailable: {exc}"))
                return True
            except ServeSecurityError as exc:
                xs["exit_reason"] = "provider_fatal"
                self._send(502, _error_payload(f"serve security failure: {exc}"))
                return True
            finally:
                _gate_j.release()
            if "first_event_ms" not in xs or xs.get("first_event_ms") is None:
                xs["first_event_ms"] = result["first_event_ms"]
            if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
                xs["ttft_ms"] = result["ttft_ms"]
            if result.get("exit_reason") == "client_gone":
                attempts.attempt_done(False, False)
                xs["exit_reason"] = "client_gone"
                return True
            if result.get("exit_reason") == "timeout":
                attempts.attempt_done(False, False)
                xs["exit_reason"] = "timeout"
                self._send(502, _error_payload("opencode timeout"))
                return True
            # Токены неуспешных попыток тоже учитываются (как в потоковом пути).
            for _tk in ("input", "output", "cached", "reasoning"):
                tokens[_tk] = tokens.get(_tk, 0) + int(result["usage"].get(_tk) or 0)
            _delivered_j = bool(
                delivered_any
                or contents
                or reasonings_all
                or tool_calls_all
                or texts
                or reasonings
                or natives
                or result.get("delivered")
            )
            delivered_any = _delivered_j
            if result.get("exit_reason") in (
                "first_event_timeout",
                "first_token_timeout",
                "stall_timeout",
                "invalid_serve_event",
                "prompt_error",
                "eof_before_step_finish",
            ):
                reason = str(result["exit_reason"])
                if reason in ("first_event_timeout", "invalid_serve_event"):
                    res.serve_health.record_failure()
                else:
                    attempts.attempt_done(True, False)
                if not _delivered_j and not force_serve:
                    return False
                if attempts.allow_retry(reason):
                    _save_partial_output(texts, reasonings)
                    continue
                xs["exit_reason"] = reason
                self._send(502, _error_payload(f"serve {reason}"))
                return True
            if result.get("prompt_status") is not None:
                _ps_j = int(result["prompt_status"] or 0)
                if _ps_j == 429 or 500 <= _ps_j <= 599:
                    attempts.attempt_done(True, False)
                if not _delivered_j and not force_serve:
                    return False
                if attempts.allow_retry(f"prompt_status_{_ps_j}"):
                    _save_partial_output(texts, reasonings)
                    continue
                xs["exit_reason"] = f"prompt_status_{_ps_j}"
                self._send(502, _error_payload(f"serve prompt HTTP {_ps_j}"))
                return True
            if result["error"] is not None:
                err = result["error"]
                if result.get("transient_error"):
                    attempts.attempt_done(True, False)
                    _save_partial_output(texts, reasonings)
                    if (
                        not texts
                        and not reasonings
                        and not result.get("native_calls")
                        and attempts.allow_retry("serve_transient_error")
                    ):
                        _prior_content = "\n\n".join(c for c in contents if c)
                        continue
                    if not _delivered_j and not force_serve:
                        return False
                    _sig_j = _incomplete_step_signal(
                        "".join(texts),
                        "".join(reasonings),
                        tools or [],
                        True,
                        int(result["usage"].get("output") or 0),
                        int(result["usage"].get("reasoning") or 0),
                        tool_choice=tool_choice,
                    )
                    if _sig_j and attempts.allow_retry("incomplete_step"):
                        _prior_content = "\n\n".join(c for c in contents if c)
                        current_prompt = _rewrite_tool_tags_for_model(
                            _incomplete_tool_step_prompt(
                                prompt,
                                "".join(contents),
                                tools or [],
                                tool_choice,
                                model,
                            ),
                            model,
                        )
                        continue
                xs["exit_reason"] = "upstream_failed"
                self._send(
                    502,
                    _error_payload(
                        f"serve error: {_clean_err(str(err.get('message') or ''))}"
                    ),
                )
                return True
            if result.get("terminal") == "cancelled":
                xs["exit_reason"] = "cancelled"
                self._send(502, _error_payload("serve session cancelled"))
                return True
            res.serve_health.record_success()
            attempts.attempt_done(False, True)
            reasonings_all.extend(reasonings)
            content_raw = "".join(texts)
            calls: list[dict[str, object]] = []
            content = content_raw
            if emulate_tools and content_raw:
                parsed_texts: list[str] = []
                parser_json = ToolCallParser(parsed_texts.append, calls.append)
                parser_json.feed(content_raw)
                parser_json.finish()
                content = "".join(parsed_texts)
                content, _dropped = _strip_broken_tool_blocks(content)
            content = _strip_interrupted(content)
            repeated_prefix = bool(
                _prior_content and content.startswith(_prior_content)
            )
            if _prior_content:
                content = _dedup_retry_text(_prior_content, content)
            if content:
                if repeated_prefix and contents:
                    contents[-1] += content
                else:
                    contents.append(content)
            for call in calls:
                _add_call(call)
            unmapped: list[str] = []
            for native in natives:
                part = _as_dict(native.get("part"))
                mapped = _native_call_as_dsh(native, tools) if emulate_tools else []
                if not mapped and emulate_tools and part.get("tool"):
                    unmapped.append(str(part.get("tool")))
                for call in mapped:
                    _add_call(call)
            usage = result["usage"]
            if not emulate_tools or tool_calls_all:
                break
            if unmapped:
                if unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
                    "unmapped"
                ):
                    contents.append(
                        f"[opencode-zen-bridge: модель вызывала недоступный встроенный "
                        f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]"
                    )
                    break
                unmapped_retries += 1
                _prior_content = "\n\n".join(c for c in contents if c)
                current_prompt = _rewrite_tool_tags_for_model(
                    _unavailable_tools_prompt(
                        current_prompt, content_raw, unmapped, tools or [], model
                    ),
                    model,
                )
                continue
            signal = _incomplete_step_signal(
                content_raw,
                _strip_interrupted("".join(reasonings))
                if content_raw.strip()
                else "".join(reasonings),
                tools or [],
                False,
                int(usage.get("output") or 0),
                int(usage.get("reasoning") or 0),
                tool_choice=tool_choice,
            )
            if not signal:
                break
            if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
                "incomplete_step"
            ):
                break
            incomplete_retries += 1
            _prior_content = "\n\n".join(c for c in contents if c)
            current_prompt = _rewrite_tool_tags_for_model(
                _incomplete_tool_step_prompt(
                    prompt, "\n\n".join(contents), tools or [], tool_choice, model
                ),
                model,
            )
        content_final = "\n\n".join(c for c in contents if c)
        if not content_final and not tool_calls_all:
            xs["exit_reason"] = "upstream_failed"
            self._send(502, _error_payload("serve produced no text"))
            return True
        for i, tc_item in enumerate(tool_calls_all):
            tc_item["index"] = i
        msg: dict[str, object] = {"role": "assistant", "content": content_final}
        if reasonings_all:
            msg["reasoning_content"] = "".join(reasonings_all)
        finish = "stop"
        if tool_calls_all:
            msg["tool_calls"] = tool_calls_all
            finish = "tool_calls"
        if self._client_gone_check():
            xs["exit_reason"] = "client_gone"
            return True
        xs.update(
            exit_reason="ok",
            tools=len(tool_calls_all),
            out_chars=len(content_final),
            rc=0,
        )
        self._send(
            200,
            {
                "id": f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": reported_model or model,
                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                "usage": _build_openai_usage(
                    int(tokens.get("input") or 0) or _estimate_tokens(prompt),
                    int(tokens.get("output") or 0) or _estimate_tokens(content_final),
                    tokens.get("cached", 0),
                    tokens.get("reasoning", 0),
                ),
            },
        )
        return True

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
        attempts = _RequestAttempts(
            res,
            time.monotonic() + TIMEOUT_S,
            use_breaker=not _is_google_direct_model(model),
        )
        xs["attempts"] = attempts
        try:
            if not attempts.begin_attempt():
                xs["exit_reason"] = "circuit_open"
                self._send(
                    503,
                    {
                        "error": {
                            "message": "upstream circuit open",
                            "type": "overloaded",
                        }
                    },
                )
                return
            if not _is_google_direct_model(model) and _select_transport(res) == "serve":
                xs["transport"] = "serve"
                xs["transport_history"] = ["serve"]
                if self._serve_json_serve(
                    model,
                    prompt,
                    effort,
                    emulate_tools,
                    tools,
                    reported_model,
                    tool_choice
                    if isinstance(tool_choice, (str, dict)) or tool_choice is None
                    else None,
                    res,
                    attempts,
                    xs,
                ):
                    return
                xs["transport"] = "run"
                xs["transport_history"] = ["serve", "run"]
            else:
                xs["transport"] = "google" if _is_google_direct_model(model) else "run"
                xs["transport_history"] = [str(xs["transport"])]
            while True:
                if not attempts.can_spawn():
                    # Суммарный потолок serve + run: четвёртый спавн запрещён.
                    xs["exit_reason"] = "upstream_failed"
                    self._send(502, _error_payload("spawn limit reached"))
                    return
                if retries:
                    _log(
                        f"exec retry={retries} ({'incomplete tool step' if incomplete_retry else 'unmapped built-in tool'})"
                        f" total_spawns={attempts.total_spawns}/{attempts.max_total}"
                    )
                run = Run(
                    model,
                    attempt_prompt,
                    effort,
                    DEFAULTWORKDIR,
                    tools=(tools or []) if emulate_tools else None,
                    google_input=google_input,
                    attempts=attempts,
                    resilience=res,
                )
                run.is_client_gone = self._client_gone_check
                try:
                    out = run.execute()
                finally:
                    run.close()

                first_event_value = cast(object, out.get("first_event_at"))
                first_token_value = cast(object, out.get("first_token_at"))
                if xs.get("first_event_at") is None and isinstance(
                    first_event_value, (int, float)
                ):
                    xs["first_event_at"] = float(first_event_value)
                    xs["first_event_ms"] = int(
                        (float(first_event_value) - cast(float, xs["t0"])) * 1000
                    )
                if xs.get("first_token_at") is None and isinstance(
                    first_token_value, (int, float)
                ):
                    xs["first_token_at"] = float(first_token_value)
                    xs["ttft_ms"] = int(
                        (float(first_token_value) - cast(float, xs["t0"])) * 1000
                    )

                if out.get("state") in (
                    "launcher_missing",
                    "spawn_failed",
                    "client_gone",
                ):
                    xs["exit_reason"] = str(out["state"])
                    self._send(
                        502,
                        {
                            "error": {
                                "message": out.get("err") or out["state"],
                                "type": "proxy_error",
                                "code": 502,
                            }
                        },
                    )
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
                if retries:
                    # Уже отданная преамбула подавляется, переформулированный текст сохраняется целиком.
                    prior_content = "\n\n".join(c for c in contents if c)
                    repeated_prefix = bool(
                        prior_content and content.startswith(prior_content)
                    )
                    content = _dedup_retry_text(prior_content, content)
                    if repeated_prefix and contents:
                        contents[-1] += content
                        content = ""
                if content:
                    contents.append(content)
                if out.get("reasoning"):
                    reasonings.append(out["reasoning"])
                for key in ("input", "output", "cached", "reasoning"):
                    tokens[key] = tokens.get(key, 0) + int(
                        (out.get("usage") or {}).get(key) or 0
                    )
                unmapped: list[str] = []
                if emulate_tools:
                    for native in out.get("native_calls") or []:
                        calls = _native_to_tool_calls(
                            native.get("tool"), native.get("input"), tools or []
                        )
                        _log(
                            f"opencode built-in tool event: tool={native.get('tool')} status={native.get('status')} "
                            f"mapped={bool(calls)} as={[c['name'] for c in calls]}"
                        )
                        if not calls:
                            unmapped.append(str(native.get("tool")))
                        for call in calls:
                            tool_calls.append(
                                {
                                    "index": len(tool_calls),
                                    "id": "call_" + uuid.uuid4().hex[:24],
                                    "type": "function",
                                    "function": {
                                        "name": call["name"],
                                        "arguments": json.dumps(
                                            call["arguments"], ensure_ascii=False
                                        ),
                                    },
                                }
                            )
                watchdog_phase = cast(object, out.get("state"))
                if (
                    watchdog_phase
                    in (
                        "first_event_timeout",
                        "first_token_timeout",
                        "stall_timeout",
                        "timeout",
                    )
                    and not tool_calls
                ):
                    w_state = str(watchdog_phase)
                    tail = _clean_err(str(cast(object, out.get("err")) or ""), 500)
                    xs["exit_reason"] = w_state
                    self._send(
                        502,
                        _error_payload(
                            f"opencode {w_state}" + (f": {tail}" if tail else ""), tail
                        ),
                    )
                    return
                if out.get("fatal_error") and not tool_calls:
                    tail = _clean_err(str(out.get("err") or ""), 500)
                    xs["exit_reason"] = "provider_fatal"
                    self._send(
                        502,
                        _error_payload(
                            f"opencode provider error after partial output (HTTP {out.get('provider_status')})"
                            + (f": {tail}" if tail else ""),
                            tail,
                        ),
                    )
                    return
                if not emulate_tools or tool_calls:
                    break
                if unmapped:
                    if (
                        unmapped_retries >= NATIVE_RETRY_LIMIT
                        or not attempts.allow_retry("unmapped")
                    ):
                        _log(
                            f"unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})"
                        )
                        contents.append(
                            f"[opencode-zen-bridge: модель вызывала недоступный встроенный "
                            f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]"
                        )
                        break
                    retries += 1
                    unmapped_retries += 1
                    incomplete_retry = False
                    _log(
                        f"unmapped built-in tools={unmapped}: re-prompt {unmapped_retries}/{NATIVE_RETRY_LIMIT}"
                    )
                    attempt_prompt = _rewrite_tool_tags_for_model(
                        _unavailable_tools_prompt(attempt_prompt, out["text"], unmapped, tools or [], model), model)
                    continue
                run_usage = out.get("usage") or {}
                signal = (
                    0
                    if out.get("provider_status") in _FATAL_HTTP
                    else _incomplete_step_signal(
                        out["text"],
                        _strip_interrupted(str(out.get("reasoning") or "")),
                        tools or [],
                        bool(out.get("had_error")),
                        int(run_usage.get("output") or 0),
                        int(run_usage.get("reasoning") or 0),
                        tool_choice=tool_choice,
                    )
                )
                if not signal:
                    break
                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
                    "incomplete_step"
                ):
                    _log(
                        f"incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}"
                    )
                    break
                retries += 1
                incomplete_retries += 1
                incomplete_retry = True
                attempts.signal = signal
                _log(
                    f"incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
                    f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}"
                )
                attempt_prompt = _rewrite_tool_tags_for_model(
                    _incomplete_tool_step_prompt(
                        prompt,
                        "\n\n".join(c for c in contents if c),
                        tools or [],
                        tool_choice,
                        model,
                    ),
                    model,
                )
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
            content = (
                _BROKEN_BLOCK_NOTICE  # иначе клиент получил бы пустой ответ или 502
            )
        if not content and not tool_calls:
            # Пустой текст с ненулевым rc/ошибкой провайдера — честная 502, не выдуманный ответ.
            tail = _clean_err(str(out.get("err") or ""), 500)
            xs["exit_reason"] = "upstream_failed"
            self._send(
                502,
                _error_payload(
                    f"opencode run produced no text (rc={out.get('rc')}, state={out.get('state')})"
                    + (f": {tail}" if tail else ""),
                    tail,
                ),
            )
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
        xs.update(
            exit_reason="ok",
            tools=len(tool_calls),
            out_chars=len(content),
            rc=out.get("rc"),
        )
        _log(
            f"done model={model} rc={out.get('rc')} state={out.get('state')} tools={len(tool_calls)} "
            f"out_chars={len(content)} retries={retries} total_spawns={attempts.total_spawns}"
        )

        self._send(
            200,
            {
                "id": f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": reported_model or model,
                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                "usage": _build_openai_usage(
                    prompt_tokens,
                    completion_tokens,
                    tokens.get("cached", 0),
                    tokens.get("reasoning", 0),
                ),
            },
        )

    # ---- HTTP --------------------------------------------------------------------
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/v1/health"):
            _maybe_reload_catalog()
            with _active_lock:
                active = len(_active)
            self._send(
                200,
                {
                    "ok": True,
                    "transport": "opencode-zen-cli",
                    "models": sorted(ALLOWED_MODELS),
                    "default_model": _effective_default_model(),
                    "catalog_mode": CATALOG_MODE,
                    "catalog_source": CATALOG_SOURCE,
                    "active": active,
                    "max_concurrent": MAX_CONCURRENT,
                    "stream": True,
                    "tool_emulation": True,
                    "uptime_s": int(time.time() - _started),
                },
            )
            return
        if not _auth_ok(self):
            self._send(
                401, {"error": {"message": "unauthorized", "type": "auth_error"}}
            )
            return
        if path in ("/v1/models", "/models"):
            _maybe_reload_catalog()
            self._send(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": mid,
                            "object": "model",
                            "owned_by": "opencode-zen",
                            "created": 0,
                            "context_length": meta["context_length"],
                            "max_output": meta["max_output"],
                            "reasoning_efforts": list(
                                meta.get("reasoning_efforts") or []
                            ),
                        }
                        for mid, meta in sorted(ALLOWED_MODELS.items())
                    ],
                },
            )
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
    _ = _startup_reaper()
    _log(
        f"start host={HOST} port={PORT} catalog={CATALOG_MODE}/{CATALOG_SOURCE} "
        f"models={sorted(ALLOWED_MODELS)} launcher={_resolve_launcher()}"
    )
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
