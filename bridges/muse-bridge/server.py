#!/usr/bin/env python3
"""muse-bridge — локальный OpenAI-совместимый мост поверх Muse Code CLI (Meta).

Один запрос `/v1/chat/completions` = один headless-ход
`~/.config/muse-launch/muse-cli.sh exec --provider meta --model muse-spark-1.3
 --reasoning-effort <TIER> --yolo --trust-workspace --workspace <WS> --json --prompt-file <f>`.

Вызов ТОЛЬКО через обёртку muse-cli.sh (прокси :10816, вычистка META_API_KEY,
exit 42 при DOWN прокси) — канон model-invocation.md §2d. Голый `muse` не используется.

Stdout CLI — JSONL-конверты (schema_version=1). Текст ответа — из
`run.terminal.completed` (payload.text); fallback — конкатенация `run.output.delta`
(payload.text). Ошибки — `run.terminal.*` с terminal != completed либо
`task.lifecycle.failed` (event.reason). Usage CLI в JSONL не отдаёт — оценка по словам.

Транспорт — stdlib. `stream:true`: заголовки 200 и role-delta уходят сразу, пока ход
идёт — data-чанки `chat.completion.chunk` с пустой дельтой `{"content": ""}`
(MUSE_BRIDGE_KEEPALIVE_S); по готовности — reasoning
summaries как `delta.reasoning_content`, tool_calls, content-чанки (~300 символов), финал
с finish_reason + usage, затем `data: [DONE]`. Ошибка после старта потока — кадр
`{"error": …}` + `[DONE]`. Текст ответа CLI отдаёт в конце хода, поэтому content
по-прежнему приходит в конце. `stream:false` — обычный JSON.

Провал хода (failed terminal, rc != 0, таймаут) не отдаётся как успешный финал: частичный
текст и tool-блоки отбрасываются — SSE-кадр ошибки + `[DONE]` (stream) либо 502 (JSON).

Keepalive: пустые data-чанки держат SSE-соединение, не меняя текст ответа.
Сброс idle-watchdog клиента pi-ai требует отдельной живой проверки в DSH.
Перед финалом поток запечатывается; после `data: [DONE]` записей нет.

Эмуляция OpenAI function calling (порт из droid-bridge): если запрос содержит
непустой `tools` (и tool_choice != "none"), в системный текст добавляется протокол
`<tool_call>{"name":…,"arguments":{…}}</tool_call>` и схемы инструментов; блоки в
ответе модели разбираются ToolCallParser в `message.tool_calls` +
`finish_reason:"tool_calls"`; история assistant.tool_calls / role:"tool"
рендерится обратно в те же блоки. Без `tools` мост чисто текстовый.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, NamedTuple

logger = logging.getLogger("muse-bridge")

HOST = os.environ.get("MUSE_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = int(os.environ.get("MUSE_BRIDGE_PORT", "9886"))
AUTH_KEY = os.environ.get("MUSE_BRIDGE_KEY", "").strip()

TIMEOUT_S = float(os.environ.get("MUSE_BRIDGE_TIMEOUT_S", "3600"))
MAX_CONCURRENT = int(os.environ.get("MUSE_BRIDGE_MAX_CONCURRENT", "2"))

MUSE_WRAPPER = os.environ.get(
    "MUSE_BRIDGE_CLI", str(Path.home() / ".config" / "muse-launch" / "muse-cli.sh")
)
ROOT = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("MUSE_BRIDGE_WORKSPACE", str(ROOT / "workspace")))
LOG_PATH = Path(os.environ.get("MUSE_BRIDGE_LOG", str(ROOT / "logs" / "bridge.log")))

ALLOWED_MODELS: dict[str, dict[str, Any]] = {
    "muse-spark-1.3": {"context_length": 1048576, "max_output": 131072},
    # 2026-10-05: контрибьютор-слот (только пикер, по просьбе владельца).
    # id подтверждён `muse model-profile show` (резолвится); окно/лимит как у spark.
    "muse-spark-1.3-contributor": {"context_length": 1048576, "max_output": 131072},
    "muse-wonder-1.0": {"context_length": 400_000, "max_output": 131072},
    "muse-wonder-full-1.0": {"context_length": 400_000, "max_output": 131072},
}
DEFAULT_MODEL = os.environ.get("MUSE_BRIDGE_MODEL", "muse-wonder-full-1.0")
DEFAULT_CONTEXT_LIMIT = 400_000

# Подстрока ошибки жёсткого порога контекста Meta (ADR-001.3, [F-01]).
HARD_THRESHOLD_ERR_SUBSTR = (
    "context compaction replacement still exceeds the hard threshold"
)
COMPACTION_MARKER = (
    "[... earlier conversation turns compacted to stay within Muse context limit ...]"
)
_COMPACTION_MARKER_ROLE = "__compaction_marker__"

# OpenAI/DSH effort -> `--reasoning-effort` Muse CLI. Нет/неизвестно -> max (канон слота).
EFFORT_MAP: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "max",
    # 2026-10-08: "none" запрещён meta-провайдером (muse exec RC=2:
    # "--reasoning-effort none is not supported with --provider meta"),
    # мост отдавал 502. "Без рассуждений" -> ближайший живой тир minimal.
    "off": "minimal",
    "none": "minimal",
    "minimal": "minimal",
    "ultra": "xhigh",  # runtime-гейт ultra откатывается в xhigh
}
DEFAULT_EFFORT = "max"

# Однократный ретрай exec — ТОЛЬКО на этот маркер (exec идемпотентен).
# Остальные ошибки (rc=42 прокси DOWN, timeout, terminal_*) не ретраятся.
NETWORK_RETRY_MARKER = "network connection could not be opened"

# Bridge-тир -> MSP ReasoningEffort (closed-вокабуляр SS3.2). _map_effort уже
# нормализовал запрос; ultra откатан в xhigh там же (EFFORT_MAP).
# 2026-10-08: +minimal (низший живой тир meta -> низший известный MSP-тир low);
# "none" оставлен оборонительно (сюда больше не приходит, но MSP-вокабуляр под вопросом).
_MSP_EFFORT = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "max",
    "minimal": "low",
    "none": "low",
}

# Грейс выхода CLI после terminal completed: вышел сам -> его rc настоящий; завис -> добивает мост.
# Грейс вне бюджета хода (таймер TIMEOUT_S отменяется по completed), но ограничен.
QUARANTINE_MAX_S = 600.0  # потолок карантина слота: группа не подтверждена мёртвой
_SIGNAL_RCS = (
    -signal.SIGKILL,
    -signal.SIGTERM,
)  # rc процесса, убитого мостом при уборке
TERMINAL_EXIT_GRACE_S = 0.5
SERVE_SPAWN_TIMEOUT_S = 30.0  # handshake+session/start должны уложиться сюда

# --- REQ-MUSE-002/003/004 (пакет a4): approval, бюджеты, повторы, live ---
APPROVAL_MODE = os.environ.get("MUSE_BRIDGE_APPROVAL_MODE", "allowAll").strip()
TRANSIENT_RETRY_SCOPE = os.environ.get(
    "MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE", "pre-action"
).strip()
FINISH_RESERVE_S = 35.0
CLOSE_RESERVE_S = 12.0
REQUEST_CAP_S = 3600.0
MIN_ATTEMPT_REMAINING_S = float(os.environ.get("MUSE_BRIDGE_MIN_ATTEMPT_S", "120"))
CONTROL_WRITE_TIMEOUT_S = 5.0
LIVE_WRITE_TIMEOUT_S = 3.0
APPROVAL_CANCEL_GRACE_S = 15.0
MAX_APPROVAL_DECIDE = 10
MAX_USER_INPUT_CANCEL = 3
TRANSIENT_MAX_RETRIES = 2
TRANSIENT_BACKOFF_S: tuple[float, float] = (2.0, 4.0)
TRANSIENT_JITTER_S = 1.0
TRANSIENT_MARKERS: tuple[str, ...] = (
    "[net-timeout]",
    "timed out waiting for response data",
    NETWORK_RETRY_MARKER,
    "transport_connect_unreachable",
)
NON_RETRYABLE_STATES = frozenset(
    {"timeout", "spawn_failed", "launcher_missing", "client_gone"}
)


def _validate_startup_config() -> None:
    """Невалидный env-режим или бюджет останавливают старт моста (AD-007)."""
    if APPROVAL_MODE not in ("allowAll", "denyUnmatched"):
        raise RuntimeError(f"MUSE_BRIDGE_APPROVAL_MODE invalid: {APPROVAL_MODE!r}")
    if TRANSIENT_RETRY_SCOPE not in ("pre-action", "observed-items"):
        raise RuntimeError(
            f"MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE invalid: {TRANSIENT_RETRY_SCOPE!r}"
        )
    if TIMEOUT_S < FINISH_RESERVE_S + MIN_ATTEMPT_REMAINING_S:
        raise RuntimeError(
            "MUSE_BRIDGE_TIMEOUT_S too small: "
            f"{TIMEOUT_S} < FINISH_RESERVE_S + MIN_ATTEMPT_REMAINING_S "
            f"({FINISH_RESERVE_S + MIN_ATTEMPT_REMAINING_S})"
        )


_validate_startup_config()


def _is_transient_text(*values: Any) -> bool:
    """Классификация транзиента только по явным маркерам (§3.1 пакета)."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            text = value
        elif isinstance(value, (list, tuple)):
            if _is_transient_text(*value):
                return True
            continue
        elif isinstance(value, dict):
            text = " ".join(
                str(value.get(key) or "") for key in ("kind", "message", "code")
            )
            if not text.strip():
                text = str(value)
        else:
            text = str(value)
        if any(marker in text for marker in TRANSIENT_MARKERS):
            return True
    return False


_AUDIT_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_TOOL_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:/-]+$")


def _render_audit_token(value: Any) -> str:
    """Безопасный рендер свободной строки в аудит-лог (FU-009)."""
    text = value if isinstance(value, str) else ""
    if text and len(text) <= 64 and _AUDIT_TOKEN_RE.match(text):
        return text
    raw = text if isinstance(value, str) else str(value or "")
    digest = hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:8]
    return f"redacted(len={len(raw)},sha256={digest})"


def _render_tool_token(value: Any) -> str:
    """Рендер toolName в журнал инструментальных item (allowlist §4.3)."""
    text = value if isinstance(value, str) else ""
    if text and len(text) <= 64 and _TOOL_TOKEN_RE.match(text):
        return text
    return f"redacted(len={len(text)})"


_TOOL_MARKER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_TOOL_MARKER_INVALID_RE = re.compile(r"[^A-Za-z0-9_.:-]")


def _sanitize_tool_name(value: Any) -> str:
    """Санитизация имени инструмента для live-маркеров reasoning (AD-002).

    Допустимо только `^[A-Za-z0-9_.:-]{1,64}$`; недопустимые символы
    заменяются на `_`, длина обрезается до 64, пустое/None — `tool`.
    """
    if not isinstance(value, str) or not value:
        return "tool"
    if _TOOL_MARKER_RE.match(value):
        return value
    cleaned = _TOOL_MARKER_INVALID_RE.sub("_", value)[:64]
    return cleaned or "tool"


class ApprovalPolicy:
    """Чистая политика решения по снимку approval (BND-001): без I/O.

    Читает только разрешённые поля снимка; rawArgs и тела не трогает.
    Выход: approve / deny (ветка деградации) / fail_turn + аудит-строка.
    """

    def __init__(self, mode: str) -> None:
        self.mode = mode

    @staticmethod
    def _choices(params: dict[str, Any]) -> list[dict[str, Any]]:
        raw = params.get("availableChoices")
        if not isinstance(raw, list):
            return []
        return [c for c in raw if isinstance(c, dict)]

    @staticmethod
    def deny_choice(params: dict[str, Any] | None) -> dict[str, Any] | None:
        if not params:
            return None
        for choice in ApprovalPolicy._choices(params):
            if choice.get("decision") in ("abort", "denied"):
                return choice
        return None

    def evaluate(self, params: dict[str, Any]) -> dict[str, Any]:
        choices = self._choices(params)
        approve = next(
            (c for c in choices if c.get("decision") == "approved"), None
        ) or next(
            (c for c in choices if c.get("decision") == "approvedForSession"), None
        )
        deny = self.deny_choice(params)
        action = "fail_turn"
        chosen: dict[str, Any] | None = None
        if self.mode == "allowAll" and approve is not None:
            action, chosen = "approve", approve
        elif deny is not None:
            action, chosen = "deny", deny
        subject = (
            params.get("subject") if isinstance(params.get("subject"), dict) else {}
        )
        choice_ids = ",".join(
            _render_audit_token(c.get("choiceId")) for c in choices[:8]
        )
        audit = (
            "approval_decide "
            f"tool={_render_audit_token(params.get('toolName'))} "
            f"subject={_render_audit_token(subject.get('kind'))} "
            f"protected={1 if params.get('protectedWrite') else 0} "
            f"judge={1 if params.get('judgeEscalated') else 0} "
            f"choices=[{choice_ids}] "
            f"chosen={_render_audit_token(chosen.get('choiceId')) if chosen else 'none'} "
            f"decision={_render_audit_token(chosen.get('decision')) if chosen else 'none'}"
        )
        return {
            "action": action,
            "choice_id": chosen.get("choiceId") if chosen else None,
            "decision": chosen.get("decision") if chosen else None,
            "audit": audit,
        }

    def evaluate_user_input(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "action": "cancel_user_input",
            "audit": (
                f"user_input_cancel tool={_render_audit_token(params.get('toolName'))}"
            ),
        }


class ServeUnavailable(Exception):
    """Транспорт serve недоступен -> тихий fallback на exec. Не ошибка запроса."""


def _uuid7() -> str:
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand = random.getrandbits(74)
    value = (ms << 74) | rand
    hx = f"{value:032x}"
    hx = hx[:12] + "7" + hx[13:16] + f"{8 | (int(hx[16], 16) & 3):x}" + hx[17:]
    return f"{hx[:8]}-{hx[8:12]}-{hx[12:16]}-{hx[16:20]}-{hx[20:]}"


TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"

DEFAULT_SYSTEM_HINT = (
    "Ты отвечаешь в текстовом чате. Не вызывай инструменты и не выполняй команды; "
    "верни только текстовый ответ."
)

_started = time.time()
_active: dict[str, float] = {}
_active_lock = threading.Lock()
# Слоты в карантине (по записи на слот: pgid не подтверждённых мёртвыми групп); под _active_lock.
_quarantined_slots: list[list[int]] = []
_slots = threading.Semaphore(MAX_CONCURRENT)
_LOG_LOCK = threading.Lock()


def _log(msg: str) -> None:
    safe_msg = _redact_secrets(msg)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {safe_msg}"
    sys.stderr.write(line + "\n")
    sys.stderr.flush()
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK, LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    hdr = handler.headers.get("Authorization", "")
    if hdr.startswith("Bearer "):
        return hdr[7:].strip() == AUTH_KEY
    return handler.headers.get("x-api-key", "") == AUTH_KEY or hdr.strip() == AUTH_KEY


def _redact_secrets(text: str) -> str:
    """Удалить отражённые ключи до обрезки диагностики; повторный вызов безопасен."""
    if AUTH_KEY:
        text = text.replace(AUTH_KEY, "[REDACTED]")
    text = re.sub(
        r"Authorization\s*:\s*[^\r\n]+",
        "Authorization: [REDACTED]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", text, flags=re.IGNORECASE)
    text = re.sub(
        r"""(["']?(?:api[_-]?key|token|secret|password|bridge[_-]?key)["']?\s*[:=]\s*)("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\s,;}"']+)""",
        lambda match: match[1] + "[REDACTED]",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[REDACTED]", text)


def _clip_diagnostic(text: str, limit: int) -> str:
    """Ограничить поле, убрав его целиком при разрезании маркера редакции."""
    for marker in re.finditer(re.escape("[REDACTED]"), text):
        if marker.start() < limit < marker.end():
            return ""
    return text[:limit]


def _prompt_reflected_parts(prompt: str) -> list[str]:
    """Выделить длинные отражённые реплики, начиная с самых полных совпадений."""
    parts = {prompt} if len(prompt.strip()) >= 8 else set()
    for part in prompt.split("\n\n") + prompt.splitlines():
        for candidate in (part, re.sub(r"^(?:User|Assistant|System):\s*", "", part)):
            if len(candidate.strip()) >= 8:
                parts.add(candidate)
    return sorted(parts, key=len, reverse=True)


def _diagnostic_text(value: Any, prompt: str = "") -> str:
    """Санитизировать свободное поле и нормализовать управляющие переводы строк."""
    text = str(value) if value is not None else ""
    parts = _prompt_reflected_parts(prompt)
    for part in parts:
        text = text.replace(part, "[REDACTED]")
        redacted_part = _redact_secrets(part)
        if len(redacted_part.strip()) >= 8:
            text = text.replace(redacted_part, "[REDACTED]")
    text = _redact_secrets(text)
    for part in parts:
        text = text.replace(part, "[REDACTED]")
        redacted_part = _redact_secrets(part)
        if len(redacted_part.strip()) >= 8:
            text = text.replace(redacted_part, "[REDACTED]")
    control_chars = r"[\x00-\x1f\x7f-\x9f\u2028\u2029]"
    text = re.sub(control_chars, " ", text).strip()
    for part in parts:
        for variant in (part, _redact_secrets(part)):
            normalized = re.sub(control_chars, " ", variant).strip()
            if len(normalized) >= 8:
                text = text.replace(normalized, "[REDACTED]")
    return text


def _sanitize_reflected(
    raw_text: str,
    reflected_prompts: list[str],
    raw_messages: list[Any] | None = None,
) -> str:
    """Вырезать отражённые промпты и тела сообщений до и после _redact_secrets."""
    text = str(raw_text or "")
    control_chars = r"[\x00-\x1f\x7f-\x9f\u2028\u2029]"

    def _strip_candidates(target: str) -> str:
        for ref_prompt in reflected_prompts:
            for rp_variant in (ref_prompt, _redact_secrets(ref_prompt)):
                if len(rp_variant.strip()) >= 8:
                    target = target.replace(rp_variant, "[REDACTED]")
            for part in _prompt_reflected_parts(ref_prompt):
                for p_variant in (part, _redact_secrets(part)):
                    if len(p_variant.strip()) >= 8:
                        target = target.replace(p_variant, "[REDACTED]")
                    norm_part = re.sub(control_chars, " ", p_variant).strip()
                    if len(norm_part) >= 8:
                        target = target.replace(norm_part, "[REDACTED]")
                    if len(norm_part) >= 160:
                        target = target.replace(norm_part[:160], "[REDACTED]")
        for message in raw_messages or []:
            if isinstance(message, dict):
                raw_ref = _flatten_content(message.get("content")).strip()
                for reflected in (raw_ref, _redact_secrets(raw_ref)):
                    if len(reflected) >= 8:
                        target = target.replace(reflected, "[REDACTED]")
                        normalized = re.sub(control_chars, " ", reflected).strip()
                        if len(normalized) >= 8:
                            target = target.replace(normalized, "[REDACTED]")
                        if len(normalized) >= 160:
                            target = target.replace(normalized[:160], "[REDACTED]")
        return target

    text = _strip_candidates(text)
    text = _redact_secrets(text)
    text = _strip_candidates(text)
    return _redact_secrets(text)


def _has_hard_threshold_marker(*values: Any) -> bool:
    """Проверить маркер жёсткого порога контекста до 160/300-символьной обрезки."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            if _has_hard_threshold_marker(*value.values()):
                return True
        elif isinstance(value, (list, tuple, set)):
            if _has_hard_threshold_marker(*value):
                return True
        elif HARD_THRESHOLD_ERR_SUBSTR in str(value):
            return True
    return False


def _redact_quota(value: Any) -> Any:
    """Удалить значения чувствительных ключей quota до JSON-сериализации."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if re.sub(r"[_-]", "", str(key)).lower()
            in {"token", "secret", "password", "apikey", "bridgekey", "authorization"}
            else _redact_quota(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_quota(item) for item in value]
    if isinstance(value, str):
        return _redact_secrets(value)
    return value


def _turn_diagnostics(params: dict[str, Any], prompt: str) -> list[str]:
    """Собрать приоритетный блок MSP с покомпонентными лимитами и бюджетом 300."""
    error = params.get("error")
    kind = message = quota = retryable = ""
    if isinstance(error, dict):
        kind = _diagnostic_text(error.get("kind"), prompt)
        message = _diagnostic_text(error.get("message"), prompt)
        if isinstance(error.get("retryable"), bool):
            retryable = f" retryable={error['retryable']}"
        if error.get("quota") is not None:
            try:
                quota = json.dumps(
                    _redact_quota(error["quota"]),
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                    separators=(",", ":"),
                )
            except (TypeError, ValueError, RecursionError):
                quota = str(error["quota"])
            quota = _diagnostic_text(quota, prompt)
    elif error is not None:
        message = _diagnostic_text(error, prompt)
    reason = _diagnostic_text(params.get("reason"), prompt)
    if reason == message:
        reason = ""
    fields = {
        "kind": _clip_diagnostic(kind, 64),
        "message": _clip_diagnostic(message, 160),
        "quota": _clip_diagnostic(quota, 120),
        "reason": _clip_diagnostic(reason, 160),
    }

    def lines() -> list[str]:
        primary = ": ".join(fields[key] for key in ("kind", "message") if fields[key])
        primary += retryable
        if fields["quota"]:
            primary += " quota=" + fields["quota"]
        result = [primary.strip()] if primary.strip() else []
        if fields["reason"]:
            result.append("reason: " + fields["reason"])
        return result

    for key in ("quota", "reason", "message", "kind"):
        excess = len("\n".join(lines())) - 300
        if excess <= 0:
            break
        minimum = min(16, len(fields[key])) if key == "reason" else 0
        fields[key] = _clip_diagnostic(
            fields[key], max(minimum, len(fields[key]) - excess)
        )
    return lines()


def _format_err_log(
    model: str, via: str, out: dict[str, Any], stream: bool, state: str | None = None
) -> str:
    """Единая однострочная запись финального отказа без промпта и секретов."""
    return (
        f"error model={model} via={via} rc={out.get('rc')} state={state or out.get('state')} "
        f"err={_redact_secrets(str(out.get('err') or ''))[:300]!r} stream={stream}"
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
    fn = (
        tool_choice.get("function")
        if isinstance(tool_choice.get("function"), dict)
        else {}
    )
    name = fn.get("name") or tool_choice.get("name") or ""
    return str(name) if name else ""


def _tools_section(tools: list, tool_choice: Any) -> str:
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
        "Do not run shell commands or edit files yourself: emit a tool_call block instead.",
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
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
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
        elif role in ("tool", _COMPACTION_MARKER_ROLE):
            turns.append(text)
        else:
            turns.append(f"User: {text}")
    return "\n\n".join(systems).strip(), "\n\n".join(turns)


def _assemble_prompt(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
    raw_tools: Any = None,
) -> tuple[str, str, str]:
    """Собрать (system_text, turns_text, full_prompt) по единым правилам моста."""
    clean_tools = (
        [t for t in tools if isinstance(t, dict)] if isinstance(tools, list) else []
    )
    emulate_tools = bool(clean_tools) and not _tool_choice_none(tool_choice)
    system_text, turns_text = _messages_to_prompt(messages)
    if not turns_text:
        return system_text, "", ""
    head: list[str] = []
    if system_text:
        head.append(f"[system]\n{system_text}")
    if emulate_tools:
        head.append(_tools_section(clean_tools, tool_choice))
    elif (raw_tools is not None and bool(raw_tools) or bool(tools)) and not system_text:
        head.append(f"[system]\n{DEFAULT_SYSTEM_HINT}")
    full_prompt = "\n\n".join(head) + f"\n\n{turns_text}" if head else turns_text
    return system_text, turns_text, full_prompt


def _strip_code_fence(text: str) -> str:
    """Снять обёртку ```…``` (в т.ч. ```json) вокруг JSON внутри блока."""
    body = text.strip()
    if body.startswith("```"):
        newline = body.find("\n")
        body = body[newline + 1 :] if newline != -1 else body[3:]
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
    arguments: dict = {}
    if "arguments" in obj:
        normalized = _normalize_arguments(obj.get("arguments"))
        if normalized is None:
            return None
        arguments = normalized
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
            inner = self._buf[len(TOOL_CALL_OPEN) : end]
            self._buf = self._buf[end + len(TOOL_CALL_CLOSE) :]
            call = _parse_tool_call_block(inner)
            if call is None:
                self._emit(TOOL_CALL_OPEN + inner + TOOL_CALL_CLOSE)
            else:
                self._on_tool_call(call)

    def _find_close_outside_string(self, start: int) -> int:
        """Позиция `</tool_call>` вне строковых литералов JSON, или -1.

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


def _split_tool_calls(chunks: list[str]) -> tuple[str, list[dict]]:
    """Дельты текста ответа -> (content, tool_calls в формате OpenAI).

    Тот же ToolCallParser, что у droid-bridge; id вызовов — call_<hex24>.
    """
    pieces: list[str] = []
    calls: list[dict] = []

    def add_call(call: dict) -> None:
        calls.append(
            {
                "index": len(calls),
                "id": "call_" + uuid.uuid4().hex[:24],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                },
            }
        )

    parser = ToolCallParser(pieces.append, add_call)
    for chunk in chunks:
        parser.feed(chunk)
    parser.finish()
    return "".join(pieces), calls


def _map_effort(req: dict[str, Any]) -> str:
    """reasoning_effort (chat) | reasoning.effort (responses-стиль) -> тир Muse."""
    raw: Any = req.get("reasoning_effort")
    if raw is None and isinstance(req.get("reasoning"), dict):
        raw = req["reasoning"].get("effort")
    key = str(raw).strip().lower() if raw is not None else ""
    return EFFORT_MAP.get(key, DEFAULT_EFFORT)


_TOKEN_RE = re.compile(r"\s+")


def _estimate_tokens(text: str) -> int:
    """Консервативная оценка токенов по UTF-8 байтам и символам (ADR-001.2 §2.5)."""
    if not text:
        return 0
    return max(len(text) // 3, len(text.encode("utf-8")) // 3)


def _estimate_usage_tokens(text: str) -> int:
    """Оценка клиентских метрик usage по словам на exec-ветке (не бюджет прунинга)."""
    if not text or not text.strip():
        return 0
    return max(1, int(len(_TOKEN_RE.split(text.strip())) * 1.3))


def _context_limit(model: str) -> int:
    """Единый источник лимита окна модели из ALLOWED_MODELS (ADR-001.1)."""
    spec = ALLOWED_MODELS.get(model)
    if isinstance(spec, dict):
        val = spec.get("context_length")
        if isinstance(val, int) and val > 0:
            return val
    return DEFAULT_CONTEXT_LIMIT


def _context_target(limit: int) -> int:
    """Целевой бюджет проактивного прунинга с гистерезисом 80% (ADR-001.1)."""
    return (limit * 4) // 5


def _context_retry_target(limit: int) -> int:
    """Аварийный бюджет однократного retry 50% (ADR-001.1)."""
    return limit // 2


class PruneResult(NamedTuple):
    status: str  # "pass_through" | "pruned" | "refused"
    messages: list[dict[str, Any]]
    prompt: str
    est_before: int
    est_after: int
    msgs_total: int
    msgs_kept: int
    msgs_dropped: int
    mandatory_est: int
    overhead_est: int


def _overhead_tokens_estimate(
    has_system: bool,
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
    raw_tools: Any,
) -> int:
    """Оценка фиксированной шапки промпта ([system], схемы инструментов, DEFAULT_SYSTEM_HINT)."""
    clean_tools = (
        [t for t in tools if isinstance(t, dict)] if isinstance(tools, list) else []
    )
    emulate_tools = bool(clean_tools) and not _tool_choice_none(tool_choice)
    overhead = 0
    if has_system:
        overhead += _estimate_tokens("[system]\n") + 1
    if emulate_tools:
        overhead += _estimate_tokens(_tools_section(clean_tools, tool_choice)) + 1
    elif (raw_tools is not None and bool(raw_tools) or bool(tools)) and not has_system:
        overhead += _estimate_tokens(f"[system]\n{DEFAULT_SYSTEM_HINT}") + 1
    return overhead


def _prune_messages(
    messages: list[dict[str, Any]],
    limit: int,
    target: int,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
    raw_tools: Any = None,
) -> PruneResult:
    """Чистая функция защитного прунинга истории диалога (ADR-001.2)."""
    _, _, full_prompt = _assemble_prompt(
        messages, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools
    )
    est_before = _estimate_tokens(full_prompt)

    valid_msgs: list[dict[str, Any]] = []
    roles: list[str] = []
    real_msgs_total = 0
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role, text = _render_turn(msg)
        if not text.strip():
            continue
        valid_msgs.append(msg)
        roles.append(role)
        if role != _COMPACTION_MARKER_ROLE:
            real_msgs_total += 1

    has_system = any(r in ("system", "developer") for r in roles)
    overhead_est = _overhead_tokens_estimate(has_system, tools, tool_choice, raw_tools)

    if est_before <= limit:
        mandatory_est = _compute_mandatory_est_only(
            valid_msgs, roles, tools, tool_choice, raw_tools
        )
        return PruneResult(
            status="pass_through",
            messages=messages,
            prompt=full_prompt,
            est_before=est_before,
            est_after=est_before,
            msgs_total=real_msgs_total,
            msgs_kept=real_msgs_total,
            msgs_dropped=0,
            mandatory_est=mandatory_est,
            overhead_est=overhead_est,
        )

    units, mandatory_indices = _partition_units(valid_msgs, roles)
    u_roles: list[str] = []
    u_chars: list[int] = []
    u_bytes: list[int] = []
    for unit in units:
        u_role = _render_turn(unit[0])[0]
        u_roles.append(u_role)
        if u_role in ("system", "developer", _COMPACTION_MARKER_ROLE):
            u_chars.append(0)
            u_bytes.append(0)
            continue
        rendered_turns: list[str] = []
        for m in unit:
            m_role, m_text = _render_turn(m)
            if m_role == "assistant":
                rendered_turns.append(f"Assistant: {m_text}")
            elif m_role == "tool":
                rendered_turns.append(m_text)
            else:
                rendered_turns.append(f"User: {m_text}")
        unit_str = "\n\n".join(rendered_turns)
        u_chars.append(len(unit_str))
        u_bytes.append(len(unit_str.encode("utf-8")))

    def build_candidate(kept_flags: list[bool]) -> list[dict[str, Any]]:
        pruned: list[dict[str, Any]] = []
        seen_kept_turn = False
        in_dropped_gap = False
        for u_idx, unit in enumerate(units):
            u_role = u_roles[u_idx]
            if u_role in ("system", "developer"):
                pruned.extend(unit)
                continue
            if u_role == _COMPACTION_MARKER_ROLE:
                if seen_kept_turn:
                    in_dropped_gap = True
                continue
            if kept_flags[u_idx]:
                if in_dropped_gap:
                    pruned.append(
                        {"role": _COMPACTION_MARKER_ROLE, "content": COMPACTION_MARKER}
                    )
                    in_dropped_gap = False
                pruned.extend(unit)
                seen_kept_turn = True
            else:
                if seen_kept_turn:
                    in_dropped_gap = True
        return pruned

    kept = [i in mandatory_indices for i in range(len(units))]
    mandatory_msgs = build_candidate(kept)
    _, mandatory_turns_text, mandatory_prompt = _assemble_prompt(
        mandatory_msgs, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools
    )
    mandatory_est = _estimate_tokens(mandatory_prompt)
    cap = max(limit, target)
    if mandatory_est > cap:
        kept_count = sum(
            len(units[i])
            for i in range(len(units))
            if kept[i] and u_roles[i] != _COMPACTION_MARKER_ROLE
        )
        return PruneResult(
            status="refused",
            messages=mandatory_msgs,
            prompt=mandatory_prompt,
            est_before=est_before,
            est_after=mandatory_est,
            msgs_total=real_msgs_total,
            msgs_kept=kept_count,
            msgs_dropped=max(0, real_msgs_total - kept_count),
            mandatory_est=mandatory_est,
            overhead_est=overhead_est,
        )

    # Фаза C: линейный проход O(n) от новейшей к старейшей опциональной единице (FU-001).
    head_prefix_chars = len(mandatory_prompt) - len(mandatory_turns_text)
    head_prefix_bytes = len(mandatory_prompt.encode("utf-8")) - len(
        mandatory_turns_text.encode("utf-8")
    )
    marker_chars = len(COMPACTION_MARKER)
    marker_bytes = len(COMPACTION_MARKER.encode("utf-8"))
    non_sys = [
        i for i in range(len(units)) if u_roles[i] not in ("system", "developer")
    ]
    pos_in_non_sys = {u_idx: p for p, u_idx in enumerate(non_sys)}
    is_kept = [
        kept[u_idx] and u_roles[u_idx] != _COMPACTION_MARKER_ROLE for u_idx in non_sys
    ]
    m_non_sys = len(non_sys)
    first_kept_p = next((p for p, flag in enumerate(is_kept) if flag), m_non_sys)
    ft_transitions = sum(
        1 for p in range(1, m_non_sys) if not is_kept[p - 1] and is_kept[p]
    )
    turns_count = sum(1 for flag in is_kept if flag)
    turns_chars = sum(u_chars[non_sys[p]] for p in range(m_non_sys) if is_kept[p])
    turns_bytes = sum(u_bytes[non_sys[p]] for p in range(m_non_sys) if is_kept[p])

    for u_idx in range(len(units) - 1, -1, -1):
        if u_idx in mandatory_indices or u_roles[u_idx] in (
            "system",
            "developer",
            _COMPACTION_MARKER_ROLE,
        ):
            continue
        p = pos_in_non_sys[u_idx]
        before_ft = (1 if p > 0 and not is_kept[p - 1] and is_kept[p] else 0) + (
            1 if p + 1 < m_non_sys and not is_kept[p] and is_kept[p + 1] else 0
        )
        after_ft = 1 if p > 0 and not is_kept[p - 1] else 0
        new_ft = ft_transitions - before_ft + after_ft
        new_first = min(first_kept_p, p)
        new_markers = (
            max(0, new_ft - (1 if new_first > 0 else 0)) if new_first < m_non_sys else 0
        )
        new_count = turns_count + 1
        new_chars = turns_chars + u_chars[u_idx]
        new_bytes = turns_bytes + u_bytes[u_idx]
        total_items = new_count + new_markers
        sep_cost = 2 * max(0, total_items - 1)
        cand_chars = (
            head_prefix_chars + new_chars + new_markers * marker_chars + sep_cost
        )
        cand_bytes = (
            head_prefix_bytes + new_bytes + new_markers * marker_bytes + sep_cost
        )
        if max(cand_chars // 3, cand_bytes // 3) <= target:
            kept[u_idx] = True
            is_kept[p] = True
            ft_transitions = new_ft
            first_kept_p = new_first
            turns_count = new_count
            turns_chars = new_chars
            turns_bytes = new_bytes
            continue
        break

    pruned_msgs = build_candidate(kept)
    _, _, pruned_prompt = _assemble_prompt(
        pruned_msgs, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools
    )
    est_after = _estimate_tokens(pruned_prompt)
    while est_after > target:
        opt_indices = [
            i
            for i in range(len(units))
            if kept[i]
            and i not in mandatory_indices
            and u_roles[i] != _COMPACTION_MARKER_ROLE
        ]
        if not opt_indices:
            break
        kept[opt_indices[0]] = False
        pruned_msgs = build_candidate(kept)
        _, _, pruned_prompt = _assemble_prompt(
            pruned_msgs, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools
        )
        est_after = _estimate_tokens(pruned_prompt)

    kept_count = sum(
        len(units[i])
        for i in range(len(units))
        if kept[i] and u_roles[i] != _COMPACTION_MARKER_ROLE
    )
    dropped_count = max(0, real_msgs_total - kept_count)
    if est_after > cap:
        return PruneResult(
            status="refused",
            messages=pruned_msgs,
            prompt=pruned_prompt,
            est_before=est_before,
            est_after=est_after,
            msgs_total=real_msgs_total,
            msgs_kept=kept_count,
            msgs_dropped=dropped_count,
            mandatory_est=mandatory_est,
            overhead_est=overhead_est,
        )
    return PruneResult(
        status="pruned",
        messages=pruned_msgs,
        prompt=pruned_prompt,
        est_before=est_before,
        est_after=est_after,
        msgs_total=real_msgs_total,
        msgs_kept=kept_count,
        msgs_dropped=dropped_count,
        mandatory_est=mandatory_est,
        overhead_est=overhead_est,
    )


def _partition_units(
    valid_msgs: list[dict[str, Any]], roles: list[str]
) -> tuple[list[list[dict[str, Any]]], set[int]]:
    """Разбить валидные сообщения на атомарные единицы и выделить обязательные индексы M."""
    units: list[list[dict[str, Any]]] = []
    consumed_tools: set[int] = set()

    for idx, msg in enumerate(valid_msgs):
        role = roles[idx]
        if role == "tool":
            # Осиротевшие tool не попадают в units при прунинге; связанные поглощаются assistant.
            continue
        if (
            role == "assistant"
            and isinstance(msg.get("tool_calls"), list)
            and msg.get("tool_calls")
        ):
            call_ids = [
                _normalize_tool_call(tc)["id"]
                for tc in msg["tool_calls"]
                if _normalize_tool_call(tc)["id"]
            ]
            if call_ids:
                expected = set(call_ids)
                matched_indices: list[int] = []
                matched_ids: set[str] = set()
                for j in range(idx + 1, len(valid_msgs)):
                    if roles[j] != "tool":
                        break
                    if j in consumed_tools:
                        continue
                    tc_id = str(
                        valid_msgs[j].get("tool_call_id")
                        or valid_msgs[j].get("id")
                        or ""
                    )
                    if tc_id in expected and tc_id not in matched_ids:
                        matched_indices.append(j)
                        matched_ids.add(tc_id)
                if matched_ids == expected:
                    consumed_tools.update(matched_indices)
                    units.append([msg] + [valid_msgs[j] for j in matched_indices])
                continue
        units.append([msg])

    mandatory_indices: set[int] = set()
    user_unit_indices: list[int] = []
    last_non_sys_idx: int | None = None
    for u_idx, unit in enumerate(units):
        u_role = _render_turn(unit[0])[0]
        if u_role in ("system", "developer"):
            mandatory_indices.add(u_idx)
        elif u_role != _COMPACTION_MARKER_ROLE:
            last_non_sys_idx = u_idx
            if u_role not in ("assistant", "tool"):
                user_unit_indices.append(u_idx)

    if user_unit_indices:
        mandatory_indices.add(user_unit_indices[0])
        mandatory_indices.add(user_unit_indices[-1])
        # Незавершённая единица ответа (assistant+tool после последнего user, ADR-001.2 §2.2 п.4).
        if (
            last_non_sys_idx is not None
            and last_non_sys_idx > user_unit_indices[-1]
            and len(units[last_non_sys_idx]) > 1
        ):
            mandatory_indices.add(last_non_sys_idx)

    return units, mandatory_indices


def _compute_mandatory_est_only(
    valid_msgs: list[dict[str, Any]],
    roles: list[str],
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
    raw_tools: Any,
) -> int:
    units, mandatory_indices = _partition_units(valid_msgs, roles)
    mandatory_msgs = [
        m
        for u_idx, unit in enumerate(units)
        if u_idx in mandatory_indices
        for m in unit
    ]
    _, _, mandatory_prompt = _assemble_prompt(
        mandatory_msgs, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools
    )
    return _estimate_tokens(mandatory_prompt)


def _log_context_prune(
    rid: str,
    model: str,
    reason: str,
    attempt: int,
    limit: int,
    target: int,
    res: PruneResult,
) -> None:
    """Структурная запись прунинга без тел сообщений и секретов (ADR-001.4 §4.3)."""
    logger.info(
        "muse_context_pruned: model=%s initial=%d target=%d dropped=%d is_retry=%s",
        model,
        res.est_before,
        target,
        res.msgs_dropped,
        attempt > 1,
    )
    _log(
        f"context_prune rid={rid} model={model} reason={reason} attempt={attempt} "
        f"limit={limit} target={target} est_before={res.est_before} est_after={res.est_after} "
        f"msgs_total={res.msgs_total} msgs_kept={res.msgs_kept} msgs_dropped={res.msgs_dropped} "
        f"mandatory_est={res.mandatory_est} overhead_est={res.overhead_est} method=bytes_div_3"
    )


# Эмуляция SSE (OpenAI chat.completion.chunk): результат генерации уже целиком —
# «стрим» = нарезка готового текста на чанки с минимальной задержкой между ними.
SSE_CHUNK_SIZE = int(os.environ.get("MUSE_BRIDGE_SSE_CHUNK_SIZE", "300"))
SSE_CHUNK_DELAY_S = float(os.environ.get("MUSE_BRIDGE_SSE_CHUNK_DELAY_S", "0.005"))
# stream=true: заголовки и role-кадр уходят сразу, пока ход идёт — комментарии keepalive.
# Без них клиент (OpenAI SDK в DeepSeek Harness) ждал заголовков до своего таймаута
# (~600 с) и рвал долгий ход как "Request timed out".
KEEPALIVE_S = float(os.environ.get("MUSE_BRIDGE_KEEPALIVE_S", "15"))


def _split_sse_chunks(text: str, size: int = 0) -> list[str]:
    """Готовый текст -> куски для SSE-дельт (по символам, юникод-сейф)."""
    size = size or SSE_CHUNK_SIZE
    size = max(1, size)
    return [text[i : i + size] for i in range(0, len(text), size)] if text else []


def _cli_permission_flags() -> list[str]:
    """Ограничивать запись и shell только по явному запросу через окружение."""
    return [
        flag
        for name, flag in (
            ("MUSE_BRIDGE_DISABLE_WRITE", "--disable-write"),
            ("MUSE_BRIDGE_DISABLE_SHELL", "--disable-shell"),
        )
        if os.environ.get(name, "0") == "1"
    ]


def _kill_group(proc: subprocess.Popen) -> None:
    """Убить всю группу процессов хода: ребёнок — лидер группы (start_new_session).

    Фолбэк proc.kill() — если killpg недоступен/запрещён (эталон
    adapters/muse_adapter.py, RW-009).
    """
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def _group_alive(pgid: int) -> bool:
    """Жива ли группа pgid (killpg сигналом 0 ничего не убивает)."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _wait_group_exit(pgid: int, timeout: float, leader_reaped: bool = False) -> bool:
    """Короткое ожидание ухода группы после SIGKILL (обычно мгновенно).

    Пока группа жива, SIGKILL повторяется: потомок, форкнувшийся в момент первого killpg,
    остаётся в группе и иначе держал бы pipe (close() вешался бы на чтении stderr).
    Лидер реапнут (leader_reaped) — его pid свободен для переиспользования, поэтому после
    одного контрольного killpg по ещё живым потомкам сигналы прекращаются, остаётся опрос.
    """
    deadline = time.monotonic() + timeout
    control_sent = False
    while _group_alive(pgid) and time.monotonic() < deadline:
        if not (leader_reaped and control_sent):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass
            control_sent = True
        time.sleep(0.05)
    return not _group_alive(pgid)


def _terminate_run(run: Any, streams: tuple) -> None:
    """Убить группу хода и подтвердить её смерть; результат — run.dead_confirmed.

    TimeoutExpired при ожидании после SIGKILL не считается смертью: SIGKILL группы повторяется
    (в _wait_group_exit тоже), смерть группы проверяется по факту. Не подтверждена — трубы не
    закрываются (close() ждал бы читателя), слот хендлера уйдёт в карантин.
    """
    proc = run.proc
    if proc is None:
        return
    # Уборка идёт под замком: параллельный close() (таймер, надзор обрыва, finally
    # execute) ждёт её конца и видит итоговый dead_confirmed, а не выходит по _closed.
    with run._cleanup_lock:
        if run._closed:
            return
        run._closed = True
        # Пессимистично до подтверждения: оборванная уборка уйдёт в карантин слота.
        run.dead_confirmed = False
        _kill_group(proc)
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            _log(f"cleanup: wait after SIGKILL timed out pid={proc.pid}, escalating")
            _kill_group(proc)
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                pass
        run.dead_confirmed = _wait_group_exit(
            proc.pid, 2.0, leader_reaped=proc.poll() is not None
        )
        if not run.dead_confirmed:
            _log(f"cleanup: process group {proc.pid} not confirmed dead after SIGKILL")
            return
        for stream in streams:
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass


def _quarantine_slot(runs: list) -> None:
    """Слот держится, пока группы ходов не подтверждены мёртвыми (карантин), затем возвращается."""
    pgids = [r.proc.pid for r in runs if r.proc is not None]
    _log(f"quarantine: slot held, groups not confirmed dead pgids={pgids}")
    with _active_lock:
        _quarantined_slots.append(pgids)

    def work() -> None:
        end = time.monotonic() + QUARANTINE_MAX_S
        escalated = False
        while True:
            alive = [r for r in runs if r.proc is not None and _group_alive(r.proc.pid)]
            if not alive:
                break
            if not escalated and time.monotonic() >= end:
                # Потолок вышел, а группа жива: слот отпускать нельзя (orphan продолжит
                # работу при свободном слоте) — сигнал оператору, дальше только опрос.
                escalated = True
                _log(
                    "CRITICAL quarantine: process groups still alive after "
                    f"{QUARANTINE_MAX_S:.0f}s pgids={[r.proc.pid for r in alive]}, "
                    "slot stays withdrawn until they die, signals stopped"
                )
            if not escalated:
                for run in alive:
                    # Реапнутый лидер освободил pid: killpg по нему может попасть в чужую группу.
                    if run.proc.poll() is None:
                        _kill_group(run.proc)
            time.sleep(1.0)
        with _active_lock:
            _quarantined_slots.remove(pgids)
        _log("quarantine: slot released")
        _slots.release()

    threading.Thread(target=work, daemon=True).start()


class Run:
    """Один прогон `muse-cli.sh exec` с разбором JSONL-конвертов."""

    def __init__(self, model_id: str, prompt: str, effort: str, workdir: Path) -> None:
        self.model_id = model_id
        self.prompt = prompt
        self.effort = effort
        self.workdir = workdir
        self.proc: subprocess.Popen | None = None
        self._closed = False
        self._cleanup_lock = threading.Lock()
        self.dead_confirmed = (
            True  # False — группа не подтверждена мёртвой (карантин слота)
        )
        # Барьеры AD-003: exec защёлкивает ACTION_POSSIBLE при старте процесса.
        self.action_possible = False
        self.approval_seen = False
        self.observed_barrier = False
        self.exec_deadline = float("inf")

    def close(self) -> None:
        """Убить группу процессов хода и коротко дождаться её ухода.

        Идемпотентно: повторный вызов (таймер, надзор обрыва, finally) — no-op,
        поэтому поздний killpg не может попасть в переиспользованный pid.
        """
        proc = self.proc
        if proc is None:
            return
        _terminate_run(self, (proc.stdout, proc.stderr))

    def execute(self) -> dict[str, Any]:
        if not os.access(MUSE_WRAPPER, os.X_OK):
            return {
                "rc": -1,
                "text": "",
                "err": f"muse wrapper not executable: {MUSE_WRAPPER}",
                "state": "launcher_missing",
            }

        self.workdir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.setdefault(
            "PATH",
            "/Users/aazhiry1/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        )
        env.pop(
            "META_API_KEY", None
        )  # обёртка тоже вычищает; двойная страховка (flat-подписка, не PAYG)

        fd, prompt_path = tempfile.mkstemp(
            prefix="muse-prompt-", suffix=".txt", dir=str(self.workdir)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(self.prompt)
        except OSError as exc:
            return {
                "rc": -1,
                "text": "",
                "err": f"prompt file write failed: {exc}",
                "state": "spawn_failed",
            }

        cmd = [
            MUSE_WRAPPER,
            "exec",
            "--provider",
            "meta",
            "--model",
            self.model_id,
            "--reasoning-effort",
            self.effort,
            "--yolo",
            "--trust-workspace",
            "--workspace",
            str(self.workdir),
            "--json",
            "--no-session-log",
            *_cli_permission_flags(),
            "--disable-web-tools",
            "--disable-reminders",
            "--prompt-file",
            prompt_path,
        ]
        _log(
            f"exec model={self.model_id} effort={self.effort} prompt_chars={len(self.prompt)} ws={self.workdir}"
        )

        run_id = uuid.uuid4().hex[:8]
        deltas: list[str] = []
        final_text: str | None = None
        terminal: str | None = None
        reason: str | None = None
        err_lines: list[str] = []
        state = "ok"
        try:
            # Регистрация в _active ДО Popen: между появлением self.proc и записью в _active
            # нет окна, в котором надзор уже видит процесс, а /health его не учитывает.
            with _active_lock:
                _active[run_id] = time.time()
            try:
                self.proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.workdir),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    start_new_session=True,
                )
            except OSError as exc:
                with _active_lock:
                    _active.pop(run_id, None)
                return {
                    "rc": -1,
                    "text": "",
                    "err": f"spawn failed: {exc}",
                    "state": "spawn_failed",
                }
            self.action_possible = True

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

            # Жёсткий дедлайн: таймер убивает процесс, даже если stdout молчит.
            _remain = self.exec_deadline - time.monotonic()
            _timer_s = min(TIMEOUT_S, _remain) if _remain != float("inf") else TIMEOUT_S
            timer = threading.Timer(
                max(0.05, _timer_s),
                lambda: (err_lines.append("bridge timeout"), self.close()),
            )
            timer.daemon = True
            timer.start()
            timed_out = False
            try:
                assert self.proc.stdout is not None
                for raw in self.proc.stdout:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    ptype = str(event.get("payload_type") or "")
                    raw_payload = event.get("payload")
                    payload: dict[str, Any] = (
                        raw_payload if isinstance(raw_payload, dict) else {}
                    )
                    if ptype == "run.output.delta":
                        text = payload.get("text")
                        if isinstance(text, str):
                            deltas.append(text)
                    elif ptype.startswith("run.terminal"):
                        terminal = str(
                            payload.get("terminal") or ptype.rsplit(".", 1)[-1]
                        )
                        text = payload.get("text")
                        if isinstance(text, str):
                            final_text = text
                        if payload.get("reason"):
                            reason = str(payload["reason"])
                        if terminal == "completed":
                            # Ход завершён: общий таймер хода отменяется сразу (грейс уборки вне
                            # бюджета хода). Процесс может висеть после terminal — ждать EOF не
                            # нужно, группу добьёт close() ниже.
                            timer.cancel()
                            break
                    elif ptype == "task.lifecycle.failed":
                        raw_ev = payload.get("event")
                        ev: dict[str, Any] = raw_ev if isinstance(raw_ev, dict) else {}
                        if ev.get("reason"):
                            err_lines.append(f"task failed: {ev['reason']}")
                if terminal == "completed":
                    # Короткий ограниченный грейс: CLI выходит сам (его rc настоящий) либо висит
                    # после terminal — тогда его добивает мост (rc от сигнала моста — не ошибка).
                    try:
                        self.proc.wait(timeout=TERMINAL_EXIT_GRACE_S)
                    except subprocess.TimeoutExpired:
                        pass
            except (OSError, ValueError) as exc:
                state = "stream_error"
                err_lines.append(f"stdout read failed: {exc}")
            finally:
                timer.cancel()
                # Порядок: kill группы -> wait ребёнка -> снятие с _active
                # (слот отпускается позже, в finally хендлера — после execute).
                self.close()
                try:
                    self.proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    timed_out = True
                err_thread.join(timeout=5)
                with _active_lock:
                    _active.pop(run_id, None)
        finally:
            try:
                os.unlink(prompt_path)
            except OSError:
                pass

        raw_rc = self.proc.returncode if self.proc else None
        rc = raw_rc if raw_rc is not None else -1
        if terminal == "completed" and (
            raw_rc is None or raw_rc == 0 or raw_rc in _SIGNAL_RCS
        ):
            # completed доставлен: rc 0 либо смерть от сигнала моста при уборке (SIGKILL/SIGTERM)
            # не ошибка; самостоятельный rc != 0 CLI (в т.ч. между грейсом и уборкой) — ошибка.
            # Не подтверждённая уборка (raw_rc None) не отменяет доставленный ход: журнал + карантин.
            state, rc = "ok", 0
        elif timed_out or any(line == "bridge timeout" for line in err_lines):
            state = "timeout"
        elif terminal is not None and terminal != "completed":
            state = f"terminal_{terminal}"
        elif rc != 0 and state == "ok":
            state = "nonzero_exit"

        # chunks — то, что кормим ToolCallParser: итоговый текст (приоритет) или дельты.
        chunks = [final_text] if final_text else deltas
        text = "".join(chunks)
        if reason:
            err_lines.append(f"reason: {reason}")
        return {
            "rc": rc,
            "text": text,
            "chunks": chunks,
            "err": "\n".join(err_lines[-6:]),
            "state": state,
            "hard_threshold": _has_hard_threshold_marker(err_lines, reason),
            "action_possible": self.action_possible,
            "approval_seen": False,
            "observed_barrier": bool(text),
            "transient": state != "ok" and _is_transient_text(err_lines, reason),
        }


class ServeRun:
    """Один запрос через `muse serve` (MSP v1 по stdio, NDJSON JSON-RPC).

    Поток: initialize -> notify initialized -> session/start
    (approvalMode из AD-001/AD-007; провайдер meta) -> turn/start
    (reasoningEffort=тир) -> ждём turn/completed; остаточные
    approval/userInput обрабатывает ApprovalPolicy в том же ходе (AD-002).
    Текст — из agentMessage (item/completed.text, fallback — item/delta);
    reasoning summaries — из reasoning-item (summary[] + item/delta
    field "summary.N"); токены — из session/tokenUsage (reasoningTokens
    включительно). Сырой reasoning-текст в v1 не стримится (только
    summaries) — ограничение протокола, не моста.

    Транспортная неполадка до ACTION_POSSIBLE -> ServeUnavailable;
    допуск exec-fallback решает единый предикат Handler (AD-003).
    Ошибка самой модели
    (terminal != completed) — НЕ ServeUnavailable: ход реально выполнен,
    fallback лишь удвоил бы вызов.
    """

    def __init__(self, model_id: str, prompt: str, effort: str, workdir: Path) -> None:
        self.model_id = model_id
        self.prompt = prompt
        self.effort = effort
        self.workdir = workdir
        self.proc: subprocess.Popen | None = None
        self._rid = 0
        self._closed = False
        self._cleanup_lock = threading.Lock()
        self._handle_event: Any = None  # обработчик событий; ставится в execute
        self.dead_confirmed = (
            True  # False — группа не подтверждена мёртвой (карантин слота)
        )
        # Запись в stdin serve ограничена дедлайном (ставится в execute): зависший читатель
        # не держит слот бессрочно, при истечении ход завершается, группа убивается.
        self._write_until = float("inf")
        # Барьеры и состояние approval/повторов (AD-002/AD-003, пакет a4).
        self.approval_seen = False
        self.action_possible = False
        self.allowing_decide_attempted = False
        self.approval_degraded = False
        self.degraded_at: float | None = None
        self.grace_end: float | None = None
        self.observed_barrier = False
        self.tool_item_count = 0
        self.decide_count = 0
        self.user_input_cancel_count = 0
        self.ceiling_seen = False
        self.server_version = "?"
        self.last_error_text = ""
        self.live_sink: Any = None
        self.exec_deadline = float("inf")
        self.write_deadline = float("inf")
        self.request_deadline = float("inf")
        self.turn_started_at: float | None = None
        self._live_frozen = False
        # Сквозной live-стриминг всех шагов (ADR-0004): аккумулятор по
        # составному ключу (item_id, idx), единый append-only stream-текст
        # для live/final/flush (S2), доступ — только под _acc_lock (S3).
        self._acc_lock = threading.Lock()
        self._reasoning_items: dict[tuple[str, int], str] = {}
        self._item_lengths: dict[tuple[str, int], int] = {}
        self._reasoning_order: list[tuple[str, int]] = []
        self._stream_text = ""
        self._tool_names: dict[str, str] = {}
        self._tool_started: set[str] = set()
        self._tool_completed: set[str] = set()

    def get_accumulated_reasoning(self) -> str:
        """Потокобезопасный снимок накопленного reasoning (AD-003, S3).

        Единый append-only stream-текст: дельты summary.* в порядке
        поступления + live-маркеры инструментов (только при stream).
        Тот же текст — база live, финала `_send_sse` и flush перед 502.
        """
        with self._acc_lock:
            if self._stream_text:
                return self._stream_text
            return "\n\n".join(
                self._reasoning_items[key]
                for key in self._reasoning_order
                if self._reasoning_items.get(key)
            )

    def _accumulate_reasoning(self, item_id: str, idx: int, piece: str) -> str:
        """Добавить дельту в аккумулятор (item_id, idx); вернуть stream-текст."""
        with self._acc_lock:
            key = (item_id, idx)
            is_new = key not in self._reasoning_items
            self._reasoning_items[key] = self._reasoning_items.get(key, "") + piece
            self._item_lengths[key] = len(self._reasoning_items[key])
            if is_new:
                self._reasoning_order.append(key)
                if self._stream_text and not self._stream_text.endswith("\n"):
                    self._stream_text += "\n\n"
            self._stream_text += piece
            return self._stream_text

    def _accumulate_completed_summary(self, item_id: str, idx: int, full: str) -> str:
        """Сверить завершённый summary[idx] с аккумулятором; дослать хвост."""
        with self._acc_lock:
            key = (item_id, idx)
            existing = self._reasoning_items.get(key, "")
            if full == existing:
                return self._stream_text
            is_new = key not in self._reasoning_items
            self._reasoning_items[key] = full
            self._item_lengths[key] = len(full)
            if is_new:
                self._reasoning_order.append(key)
                if self._stream_text and not self._stream_text.endswith("\n"):
                    self._stream_text += "\n\n"
                self._stream_text += full
            elif full.startswith(existing):
                self._stream_text += full[len(existing) :]
            return self._stream_text

    def _emit_live(self) -> None:
        """Отправить текущий stream-текст в live_sink; сбой не замораживает ход."""
        sink = self.live_sink
        if sink is None:
            return
        with self._acc_lock:
            snapshot = self._stream_text
        if not snapshot:
            return
        try:
            sink(snapshot)
        except Exception:  # noqa: BLE001, S110
            pass

    def _emit_tool_marker(self, item_id: str, marker: str) -> None:
        """Дописать маркер инструмента в stream-текст и отправить live (AD-002)."""
        del item_id
        if self.live_sink is None:
            return
        with self._acc_lock:
            self._stream_text += marker
        self._emit_live()

    def close(self) -> None:
        """Убить группу процессов хода и коротко дождаться её ухода (идемпотентно)."""
        proc = self.proc
        if proc is None:
            return
        _terminate_run(self, (proc.stdin, proc.stdout, proc.stderr))

    def _control_limit(self) -> float:
        limit = min(
            self._write_until,
            time.monotonic() + CONTROL_WRITE_TIMEOUT_S,
            self.exec_deadline,
        )
        if self.grace_end is not None:
            limit = min(limit, self.grace_end)
        return limit

    def _write_bytes(self, data: bytes, limit: float) -> None:
        assert self.proc is not None and self.proc.stdin is not None
        try:
            fd = self.proc.stdin.fileno()
            view = memoryview(data)
            sent = 0
            while sent < len(data):
                remaining = limit - time.monotonic()
                if remaining <= 0:
                    raise ServeUnavailable(
                        "serve stdin write timed out: child does not read"
                    )
                _, writable, _ = select.select([], [fd], [], min(0.5, remaining))
                if not writable:
                    continue
                try:
                    sent += os.write(fd, view[sent:])
                except BlockingIOError:
                    continue
        except ServeUnavailable:
            raise
        except (OSError, ValueError) as exc:
            raise ServeUnavailable(f"stdio write failed: {exc}")

    def _send(
        self,
        method: str,
        params: dict | None = None,
        notify: bool = False,
        *,
        control: bool = False,
    ) -> int:
        self._rid += 1
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not notify:
            msg["id"] = self._rid
        if params is not None:
            msg["params"] = params
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        self._write_bytes(data, self._control_limit() if control else self._write_until)
        return self._rid

    def _send_response(self, server_id: Any, result: dict) -> None:
        """Receipt по серверному id дословно (AD-002)."""
        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": server_id, "result": result}
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        self._write_bytes(data, self._control_limit())

    def _note_allowing_decide(self) -> None:
        """Защёлкивание ДО первой попытки записи разрешающего decide (a4)."""
        self.allowing_decide_attempted = True
        self.action_possible = True

    def execute(self) -> dict[str, Any]:
        if not os.access(MUSE_WRAPPER, os.X_OK):
            raise ServeUnavailable(f"muse wrapper not executable: {MUSE_WRAPPER}")
        self.workdir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.setdefault(
            "PATH",
            "/Users/aazhiry1/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        )
        env.pop("META_API_KEY", None)
        cmd = [
            MUSE_WRAPPER,
            "serve",
            "--provider",
            "meta",
            "--model",
            self.model_id,
            "--no-session-log",
            "--trust-workspace",
            *_cli_permission_flags(),
        ]
        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=str(self.workdir),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                start_new_session=True,
            )
        except OSError as exc:
            raise ServeUnavailable(f"serve spawn failed: {exc}")
        assert self.proc.stdout is not None and self.proc.stdin is not None
        # stdin неблокирующий: запись идёт срезами с дедлайном (см. _send).
        os.set_blocking(self.proc.stdin.fileno(), False)

        err_lines: list[str] = []
        turn_diag_lines: list[str] = []
        stderr_joined = False

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
        _now0 = time.monotonic()
        _exec_dl = self.exec_deadline
        deadline = (
            min(_now0 + TIMEOUT_S, _exec_dl)
            if _exec_dl != float("inf")
            else _now0 + TIMEOUT_S
        )
        if self.exec_deadline == float("inf"):
            self.exec_deadline = deadline
        setup_deadline = min(_now0 + SERVE_SPAWN_TIMEOUT_S, deadline)
        self._write_until = setup_deadline

        # Чтение stdout serve — собственным буфером поверх os.read: select по fd не видит строки,
        # уже вычитанные в буфер TextIOWrapper (пачка строк за один write зависала бы).
        rbuf = bytearray()

        def read_msg(timeout_at: float) -> dict[str, Any]:
            while time.monotonic() < timeout_at:
                if self.proc is None or self.proc.stdout is None:
                    raise ServeUnavailable("serve stdout closed")
                newline = rbuf.find(b"\n")
                if newline < 0:
                    _remain = max(0.0, timeout_at - time.monotonic())
                    ready, _, _ = select.select(
                        [self.proc.stdout], [], [], min(0.5, _remain)
                    )
                    if not ready:
                        if self.proc.poll() is not None:
                            raise ServeUnavailable(
                                f"serve exited rc={self.proc.returncode}: "
                                + " ".join(err_lines[-3:])
                            )
                        continue
                    chunk = os.read(self.proc.stdout.fileno(), 65536)
                    if not chunk:
                        raise ServeUnavailable(
                            f"serve stdout EOF rc={self.proc.poll()}: "
                            + " ".join(err_lines[-3:])
                        )
                    rbuf.extend(chunk)
                    continue
                line = bytes(rbuf[:newline]).decode("utf-8", "replace").strip()
                del rbuf[: newline + 1]
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if isinstance(msg, dict):
                    return msg
            raise ServeUnavailable("serve read timeout")

        kinds: dict[str, str] = {}
        deltas: list[str] = []
        summary_parts: dict[int, str] = {}
        summaries: list[str] = []
        final_text: str | None = None
        usage: dict[str, Any] = {}
        turn_id: str | None = None
        session_id: str | None = None
        pending: dict[int, str] = {}
        seen_pairs: set[tuple[str, str]] = set()
        tool_item_ids: set[str] = set()
        last_snapshot: list[dict[str, Any]] = []
        transient_terminal = [False]
        first_summary_logged = [False]

        def _pair_key(params: dict[str, Any]) -> tuple[str, str]:
            return (
                str(params.get("approvalId") or ""),
                json.dumps(
                    params.get("currentRequirementId"),
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ),
            )

        def _send_decide(
            snapshot: dict[str, Any], choice: dict[str, Any], *, allowing: bool
        ) -> None:
            if allowing:
                self._note_allowing_decide()
            self.decide_count += 1
            rid = self._send(
                "approval/decide",
                {
                    "approvalId": snapshot.get("approvalId"),
                    "choiceId": choice.get("choiceId"),
                    "commandId": _uuid7(),
                    "requirementId": snapshot.get("currentRequirementId"),
                    "sessionId": snapshot.get("sessionId") or session_id or "",
                },
                control=True,
            )
            pending[rid] = "decide"

        def _latch_degradation(
            reason: str, snapshot: dict[str, Any] | None = None
        ) -> None:
            if self.approval_degraded:
                return
            self.approval_degraded = True
            now = time.monotonic()
            self.degraded_at = now
            grace_end = now + APPROVAL_CANCEL_GRACE_S
            if self.write_deadline != float("inf"):
                grace_end = min(
                    grace_end, self.write_deadline - 2 * LIVE_WRITE_TIMEOUT_S
                )
            self.grace_end = grace_end
            _log(
                f"approval_degraded reason={reason} approval_seen={int(self.approval_seen)} "
                f"action_possible={int(self.action_possible)} "
                f"barrier={int(self.observed_barrier)} tool_items={self.tool_item_count} "
                f"grace_s={max(0.0, grace_end - now):.2f}"
            )
            snap = (
                snapshot
                if snapshot is not None
                else (last_snapshot[0] if last_snapshot else None)
            )
            try:
                deny = ApprovalPolicy.deny_choice(snap)
                if deny is not None and self.decide_count < MAX_APPROVAL_DECIDE:
                    _send_decide(snap or {}, deny, allowing=False)
                elif turn_id:
                    rid = self._send(
                        "turn/cancel",
                        {
                            "commandId": _uuid7(),
                            "sessionId": session_id or "",
                            "turnId": turn_id,
                        },
                        control=True,
                    )
                    pending[rid] = "turn_cancel"
            except ServeUnavailable as exc:
                _log(f"approval degrade command failed: {exc}")

        def _handle_ack(msg: dict[str, Any]) -> None:
            raw_id = msg.get("id")
            if not isinstance(raw_id, int):
                return
            kind = pending.pop(raw_id, None)
            if kind is None:
                return
            if "error" in msg:
                err = msg.get("error") if isinstance(msg.get("error"), dict) else {}
                code = err.get("code")
                if kind == "decide" and code == -32051:
                    _log("approval decide benign -32051 already resolved")
                    return
                if kind in ("decide", "user_cancel"):
                    _latch_degradation(f"{kind}_error_{code}")
                return
            result = msg.get("result") if isinstance(msg.get("result"), dict) else {}
            if result.get("terminal") is False:
                _log("approval decide terminal=false awaiting updated request")

        def await_result(rid: int, timeout_at: float) -> dict[str, Any]:
            while True:
                msg = read_msg(timeout_at)
                if "method" in msg:
                    self._handle_event(msg, None)
                    continue
                if isinstance(msg, dict) and msg.get("id") == rid:
                    if "error" in msg:
                        err = msg["error"]
                        if isinstance(err, dict) and err.get("code") == -32030:
                            self.ceiling_seen = True
                            _log(
                                f"serve approval ceiling -32030 version={self.server_version} "
                                "warning approvalMode not applied"
                            )
                        self.last_error_text = str(err)
                        raise ServeUnavailable(f"serve RPC error: {err}")
                    result = msg.get("result")
                    return result if isinstance(result, dict) else {}
                _handle_ack(msg)

        def _handle_event(msg: dict[str, Any], _unused: Any) -> None:
            nonlocal final_text
            method = msg.get("method")
            _raw_params = msg.get("params")
            params: dict[str, Any] = (
                _raw_params if isinstance(_raw_params, dict) else {}
            )
            if method in (
                "approval/request",
                "approval/requested",
                "userInput/request",
            ):
                # a4: защёлки ДО receipt/дедупликации/политики, включая setup.
                self.approval_seen = True
                self.action_possible = True
                self.observed_barrier = True
                if self.approval_degraded:
                    _log(f"approval after degraded ignored method={method}")
                    return
                server_id = msg.get("id")
                try:
                    if server_id is not None:
                        self._send_response(server_id, {})
                except ServeUnavailable:
                    _latch_degradation("receipt_write_failed", params)
                    return
                if method == "userInput/request":
                    last_snapshot[:] = [params]
                    policy = ApprovalPolicy(APPROVAL_MODE)
                    _log(policy.evaluate_user_input(params)["audit"])
                    if self.user_input_cancel_count >= MAX_USER_INPUT_CANCEL:
                        _latch_degradation("user_input_limit", params)
                        return
                    self.user_input_cancel_count += 1
                    try:
                        rid = self._send(
                            "userInput/cancel",
                            {
                                "commandId": _uuid7(),
                                "sessionId": params.get("sessionId")
                                or session_id
                                or "",
                                "userInputId": params.get("userInputId"),
                            },
                            control=True,
                        )
                        pending[rid] = "user_cancel"
                    except ServeUnavailable:
                        _latch_degradation("user_input_write_failed", params)
                    return
                pair = _pair_key(params)
                if pair in seen_pairs:
                    _log("approval duplicate suppressed")
                    return
                seen_pairs.add(pair)
                last_snapshot[:] = [params]
                if self.decide_count >= MAX_APPROVAL_DECIDE:
                    _latch_degradation("decide_limit", params)
                    return
                verdict = ApprovalPolicy(APPROVAL_MODE).evaluate(params)
                _log(f"{verdict['audit']} n={self.decide_count + 1}")
                if verdict["action"] == "approve":
                    choice = next(
                        (
                            c
                            for c in ApprovalPolicy._choices(params)
                            if c.get("choiceId") == verdict["choice_id"]
                        ),
                        {"choiceId": verdict["choice_id"]},
                    )
                    try:
                        _send_decide(params, choice, allowing=True)
                    except ServeUnavailable:
                        _latch_degradation("decide_write_failed", params)
                elif verdict["action"] == "deny":
                    _latch_degradation("no_approve_choice", params)
                else:
                    _latch_degradation("no_choice", params)
                return
            if method == "turn/modelRetryScheduled":
                _log(
                    "turn modelRetryScheduled "
                    f"attempt={params.get('attempt')} maxAttempts={params.get('maxAttempts')} "
                    f"retryDelayMs={params.get('retryDelayMs')} "
                    f"errorKind={_render_audit_token(params.get('errorKind'))}"
                )
                return
            if method in (
                "approval/updated",
                "approval/resolved",
                "session/approvalModeChanged",
                "userInput/settled",
            ):
                if method == "approval/resolved":
                    _log("approval resolved")
                return
            if method in ("item/started", "item/completed"):
                raw_item = params.get("item")
                item: dict[str, Any] = raw_item if isinstance(raw_item, dict) else {}
                iid = str(item.get("itemId") or "")
                kind = str(item.get("kind") or "")
                if iid:
                    kinds[iid] = kind
                if kind and kind not in ("reasoning", "agentMessage"):
                    self.observed_barrier = True
                    if iid:
                        tool_item_ids.add(iid)
                        self.tool_item_count = len(tool_item_ids)
                    _log(
                        f"tool_item kind={_render_tool_token(kind)} "
                        f"tool={_render_tool_token(item.get('toolName'))}"
                    )
                    # AD-002: live-маркеры инструментов только при stream
                    # (live_sink ставится Handler только для stream=true).
                    raw_tool = (
                        item.get("toolName")
                        or item.get("tool")
                        or (kind if kind != "toolCall" else None)
                    )
                    safe_tool = _sanitize_tool_name(raw_tool)
                    if iid and method == "item/started":
                        self._tool_names[iid] = safe_tool
                        if iid not in self._tool_started:
                            self._tool_started.add(iid)
                            self._emit_tool_marker(
                                iid, f"\n\n[Вызов инструмента: {safe_tool}]\n"
                            )
                    elif iid and method == "item/completed":
                        done_tool = self._tool_names.get(iid, safe_tool)
                        if iid not in self._tool_completed:
                            self._tool_completed.add(iid)
                            self._emit_tool_marker(
                                iid, f"\n[Инструмент {done_tool} завершён]\n"
                            )
                if (
                    method == "item/completed"
                    and turn_id is not None
                    and item.get("turnId") == turn_id
                ):
                    if kind == "agentMessage" and isinstance(item.get("text"), str):
                        final_text = item["text"]
                    if kind == "reasoning" and isinstance(item.get("summary"), list):
                        completed_parts = [
                            str(p) for p in item["summary"] if isinstance(p, str)
                        ]
                        summaries.extend(completed_parts)
                        for c_idx, c_part in enumerate(completed_parts):
                            self._accumulate_completed_summary(iid, c_idx, c_part)
                        self._emit_live()
            elif method == "item/delta":
                iid = str(params.get("itemId") or "")
                field = str(params.get("field") or "text")
                piece = params.get("delta")
                if not isinstance(piece, str) or not piece:
                    return
                if kinds.get(iid) == "reasoning" and field.startswith("summary"):
                    try:
                        idx = int(field.split(".", 1)[1])
                    except (IndexError, ValueError):
                        with self._acc_lock:
                            idx = len([k for k in self._reasoning_items if k[0] == iid])
                    if not first_summary_logged[0]:
                        first_summary_logged[0] = True
                        _t0 = self.turn_started_at or _now0
                        _log(
                            f"first summary delta idx={idx} "
                            f"after_s={time.monotonic() - _t0:.2f}"
                        )
                    summary_parts[idx] = summary_parts.get(idx, "") + piece
                    # AD-001: заморозки нет — все summary.0..N стримятся
                    # непрерывно; сбой live-записи ход не останавливает (S1).
                    self._accumulate_reasoning(iid, idx, piece)
                    self._emit_live()
                elif (
                    kinds.get(iid, "agentMessage") == "agentMessage" and field == "text"
                ):
                    deltas.append(piece)
            elif method == "session/tokenUsage":
                raw = params.get("usage")
                if isinstance(raw, dict):
                    usage.update(raw)

        self._handle_event = _handle_event

        try:
            init_rid = self._send(
                "initialize", {"clientInfo": {"name": "muse_bridge", "version": "1"}}
            )
            init = await_result(init_rid, setup_deadline)
            schema = init.get("schema") if isinstance(init.get("schema"), dict) else {}
            _srv = (
                init.get("serverInfo")
                if isinstance(init.get("serverInfo"), dict)
                else {}
            )
            self.server_version = str(_srv.get("version") or "?")
            _log(
                f"serve init server={self.server_version} "
                f"schema_fp={str(schema.get('fingerprint', ''))[:19]}"
            )
            if self.approval_degraded:
                raise ServeUnavailable("serve approval degraded during setup")
            self._send("initialized", {}, notify=True)
            sess_rid = self._send(
                "session/start",
                {
                    "commandId": _uuid7(),
                    "workspaceRoot": str(self.workdir),
                    "providerId": "meta",
                    "modelId": self.model_id,
                    "approvalMode": APPROVAL_MODE,
                },
            )
            sess = await_result(sess_rid, setup_deadline)
            session = (
                sess.get("session") if isinstance(sess.get("session"), dict) else {}
            )
            session_id = str(session.get("sessionId") or "")
            if not session_id:
                raise ServeUnavailable("session/start gave no sessionId")
            _eff = session.get("approvalMode")
            if isinstance(_eff, dict):
                _eff_mode = str(_eff.get("mode") or APPROVAL_MODE)
            elif isinstance(_eff, str) and _eff:
                _eff_mode = _eff
            else:
                _eff_mode = APPROVAL_MODE
            _log(f"serve session approvalMode={_eff_mode}")
            if self.approval_degraded:
                raise ServeUnavailable("serve approval degraded during setup")
            tier = _MSP_EFFORT.get(self.effort, "max")
            # ACTION_POSSIBLE защёлкивается ДО первого байта turn/start (a3/a4).
            self.action_possible = True
            turn_rid = self._send(
                "turn/start",
                {
                    "commandId": _uuid7(),
                    "sessionId": session_id,
                    "reasoningEffort": tier,
                    "input": [{"type": "text", "text": self.prompt}],
                },
            )
            self._write_until = deadline
            self.turn_started_at = time.monotonic()
            turn = await_result(turn_rid, setup_deadline)
            if turn.get("status") != "accepted":
                raise ServeUnavailable(f"turn/start not accepted: {turn}")
            turn_id = str(turn.get("turnId") or "")
            _log(
                f"serve turn session={session_id[:8]} turn={turn_id[:8]} effort={tier}"
            )
            terminal: str | None = None
            hard_threshold = False
            while True:
                _limit = (
                    self.grace_end
                    if self.approval_degraded and self.grace_end is not None
                    else deadline
                )
                if time.monotonic() >= _limit:
                    if self.approval_degraded:
                        break
                    raise ServeUnavailable("serve turn deadline exceeded")
                try:
                    msg = read_msg(_limit)
                except ServeUnavailable:
                    if self.approval_degraded:
                        break  # EOF после cancel — подтверждение уборки
                    raise
                if msg.get("method") == "turn/completed" and isinstance(
                    msg.get("params"), dict
                ):
                    p = msg["params"]
                    if turn_id is not None and p.get("turnId") not in (turn_id, None):
                        _handle_event(msg, None)
                        continue
                    terminal = str(p.get("terminal") or "unknown")
                    if isinstance(p.get("usage"), dict):
                        usage.update(p["usage"])  # type: ignore[arg-type]
                    if terminal != "completed":
                        hard_threshold = _has_hard_threshold_marker(
                            p.get("error"), p.get("reason")
                        )
                        turn_diag_lines = _turn_diagnostics(p, self.prompt)
                        _err_raw = p.get("error")
                        transient_terminal[0] = _is_transient_text(
                            _err_raw, p.get("reason")
                        )
                        if transient_terminal[0]:
                            _log(
                                "transient_terminal "
                                f"ttft={1 if p.get('timeToFirstTokenMs') is not None else 0} "
                                f"usage={1 if usage else 0} "
                                f"tool_items={self.tool_item_count}"
                            )
                    break
                if "method" not in msg and ("result" in msg or "error" in msg):
                    _handle_ack(msg)
                    continue
                _handle_event(msg, None)
            flags: dict[str, Any] = {
                "action_possible": self.action_possible,
                "approval_seen": self.approval_seen,
                "approval_degraded": self.approval_degraded,
                "allowing_decide": self.allowing_decide_attempted,
                "observed_barrier": self.observed_barrier,
                "tool_items": self.tool_item_count,
                "transient": bool(transient_terminal[0]),
            }
            if self.approval_degraded:
                _log(f"serve turn degraded outcome tool_items={self.tool_item_count}")
                return {
                    "rc": 1,
                    "text": "",
                    "chunks": [],
                    "err": "approval_degraded",
                    "state": "terminal_failed",
                    "summaries": [],
                    "usage": usage,
                    "via": "serve",
                    "hard_threshold": False,
                    **flags,
                }
            serve_rc: int | None = None
            if terminal == "completed":
                # D-A3-1: после completed — тот же грейс, что у exec: serve вышел сам с rc != 0 ->
                # ошибка; жив -> мост закрывает группу (сигнал моста rc не определяет).
                try:
                    self.proc.wait(timeout=TERMINAL_EXIT_GRACE_S)
                except subprocess.TimeoutExpired:
                    pass
                self.close()
                serve_rc = self.proc.returncode
            with self._acc_lock:
                _items_snapshot = dict(self._reasoning_items)
                _order_snapshot = list(self._reasoning_order)
            if _items_snapshot:
                _item_sequence: list[str] = []
                for _key in _order_snapshot:
                    if _key[0] not in _item_sequence:
                        _item_sequence.append(_key[0])
                ordered = [
                    _items_snapshot[(_iid, _idx)]
                    for _iid in _item_sequence
                    for _idx in sorted(k[1] for k in _items_snapshot if k[0] == _iid)
                    if _items_snapshot.get((_iid, _idx))
                ]
            else:
                ordered = [
                    summary_parts[i] for i in sorted(summary_parts) if summary_parts[i]
                ]
            for part in ordered:
                if part not in summaries:
                    summaries.append(part)
            text = final_text if final_text is not None else "".join(deltas)
            if terminal != "completed":
                self.close()
            # Прежнее ожидание drain_stderr переносится до снимка: шум после terminal
            # не теряется; приоритетный носитель не зависит от хвоста сборщика.
            err_thread.join(timeout=5)
            stderr_joined = True
            hard_threshold = hard_threshold or _has_hard_threshold_marker(err_lines)
            stderr_tail = _redact_secrets("\n".join(list(err_lines)[-6:]))
            if self.prompt:
                stderr_tail = stderr_tail.replace(self.prompt, "[REDACTED]")
            err = "\n".join(turn_diag_lines)
            if err:
                if stderr_tail:
                    err += "\n" + _clip_diagnostic(stderr_tail, 499 - len(err))
            else:
                err = stderr_tail
            if terminal == "completed" and serve_rc not in (None, 0, *_SIGNAL_RCS):
                return {
                    "rc": serve_rc,
                    "text": text,
                    "chunks": [text] if text else [],
                    "err": err,
                    "state": "nonzero_exit",
                    "summaries": summaries,
                    "usage": usage,
                    "via": "serve",
                    "hard_threshold": hard_threshold,
                    **flags,
                }
            if terminal != "completed":
                return {
                    "rc": 1,
                    "text": text,
                    "chunks": [text] if text else [],
                    "err": err,
                    "state": f"terminal_{terminal}",
                    "summaries": summaries,
                    "usage": usage,
                    "via": "serve",
                    "hard_threshold": hard_threshold,
                    **flags,
                }
            return {
                "rc": 0,
                "text": text,
                "chunks": [text] if text else [],
                "err": err,
                "state": "ok",
                "summaries": summaries,
                "usage": usage,
                "via": "serve",
                "hard_threshold": hard_threshold,
                **flags,
            }
        finally:
            self.close()
            if not stderr_joined:
                err_thread.join(timeout=1)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 300

    def log_message(self, format: str, *args: Any) -> None:
        _log("http " + (format % args))

    def handle_error(self, request: Any, client_address: Any) -> None:
        _log(f"http accept error from {client_address}")

    # Обрыв клиента и текущий ход: значения инициализируются в setup() каждого соединения.
    _client_gone: bool = False
    _current_run: Run | ServeRun | None = None
    # Ранний SSE (stream=true): состояние потока и keepalive текущего соединения.
    _sse_open: bool = False
    _content_started: bool = False
    _sse_id: str = ""
    _sse_created: int = 0
    _sse_model: str = ""
    _wlock: threading.Lock = threading.Lock()
    _sse_phase: str = "OPEN"
    _keepalive_stop: threading.Event | None = None
    _ka_thread: threading.Thread | None = None
    _live_sent_text: str = ""
    _live_reasoning_sent: str = ""
    _live_degraded: bool = False
    _live_lock: threading.Lock = threading.Lock()
    _current_serve_run: ServeRun | None = None
    _stream: bool = False
    _write_deadline: float = float("inf")
    _exec_deadline: float = float("inf")
    _request_deadline: float = float("inf")
    _delivery_failed: bool = False
    _req_done: threading.Event | None = None

    def setup(self) -> None:
        # Состояние обрыва клиента и ссылка на текущий ход — на каждое соединение.
        self._client_gone = False
        self._current_run = None
        self._sse_open = False
        self._content_started = False
        self._sse_id = ""
        self._sse_created = 0
        self._sse_model = ""
        self._wlock = threading.Lock()
        with self._wlock:
            self._sse_phase = "OPEN"
        self._keepalive_stop: threading.Event | None = None
        self._ka_thread: threading.Thread | None = None
        self._live_sent_text = ""
        self._live_reasoning_sent = ""
        self._live_degraded = False
        self._live_lock = threading.Lock()
        self._current_serve_run = None
        self._stream = False
        self._write_deadline = float("inf")
        self._exec_deadline = float("inf")
        self._request_deadline = float("inf")
        self._delivery_failed = False
        self._req_done = None
        super().setup()

    def _get_live_lock(self) -> threading.Lock:
        """Замок live-состояния; лениво для Handler без setup() в тестах."""
        lock = self.__dict__.get("_live_lock")
        if lock is None:
            lock = threading.Lock()
            self._live_lock = lock
        return lock

    def _reset_live_for_attempt(self) -> None:
        """Сброс live-префикса перед новым ServeRun в ретрае (S4)."""
        with self._get_live_lock():
            self._live_sent_text = ""
            self._live_reasoning_sent = ""
            self._live_degraded = False

    def _note_write_failure(self, fatal: bool, message: str) -> bool:
        """Сбой записи SSE: fatal — клиент ушёл+kill; иначе live-деградация (S1)."""
        if not fatal:
            if not getattr(self, "_live_degraded", False):
                _log(f"live_degraded {message}")
            self._live_degraded = True
            return False
        if not self._client_gone:
            self._client_gone = True
            self._delivery_failed = True
            _log(message)
            self._kill_current_run()
        return False

    # ---- ранний SSE: заголовки сразу, keepalive во время хода ---------------------
    def _sse_write(
        self,
        data: str,
        fatal: bool = True,
        *,
        keepalive: bool = False,
        mark_content: bool = False,
    ) -> bool:
        """Один ограниченный бюджет L=min(s+LIVE_WRITE_TIMEOUT_S, W) (AD-004).

        Ожидание замка, запись и flush делят единый остаток. При
        `fatal=True` исчерпание = зависший клиент (client_gone + killpg).
        При `fatal=False` (live reasoning, S1) сбой лишь ставит
        `_live_degraded`: ход ServeRun не убивается, буфер уйдёт в финале.
        """
        text = data
        started = time.monotonic()
        w_deadline = getattr(self, "_write_deadline", float("inf"))
        limit = min(started + LIVE_WRITE_TIMEOUT_S, w_deadline)
        if limit <= started:
            return self._note_write_failure(
                fatal, "delivery_deadline write budget exhausted before frame"
            )
        if not self._wlock.acquire(timeout=max(0.0, limit - time.monotonic())):
            return self._note_write_failure(
                fatal, "client gone mid-stream (sse lock wait budget)"
            )
        try:
            if self._sse_phase == "CLOSED" or self._client_gone:
                return False
            if keepalive and (
                self._sse_phase != "OPEN"
                or (self._keepalive_stop is not None and self._keepalive_stop.is_set())
            ):
                return False
            if time.monotonic() >= limit:
                raise TimeoutError("sse write budget exhausted")
            if mark_content:
                self._content_started = True
            conn = getattr(self, "connection", None)
            prev_timeout: Any = None
            have_conn = False
            if conn is not None and hasattr(conn, "settimeout"):
                try:
                    prev_timeout = conn.gettimeout()
                    conn.settimeout(max(0.001, limit - time.monotonic()))
                    have_conn = True
                except (OSError, ValueError, AttributeError):
                    have_conn = False
            try:
                self.wfile.write(text.encode("utf-8"))
                if have_conn:
                    try:
                        conn.settimeout(max(0.001, limit - time.monotonic()))
                    except (OSError, ValueError, AttributeError):
                        pass
                self.wfile.flush()
            finally:
                if text == "data: [DONE]\n\n":
                    self._sse_phase = "CLOSED"
                if have_conn:
                    try:
                        conn.settimeout(prev_timeout)
                    except (OSError, ValueError, AttributeError):
                        pass
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return self._note_write_failure(fatal, "client gone mid-stream")
        finally:
            self._wlock.release()

    def _sse_chunk(self, delta: dict, finish_reason: Any = None) -> dict:
        return {
            "id": self._sse_id,
            "object": "chat.completion.chunk",
            "created": self._sse_created,
            "model": self._sse_model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }

    def _sse_emit(
        self,
        obj: dict,
        *,
        keepalive: bool = False,
        mark_content: bool = False,
        fatal: bool = True,
    ) -> bool:
        return self._sse_write(
            "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n",
            fatal,
            keepalive=keepalive,
            mark_content=mark_content,
        )

    def _live_reasoning_sink(self, full_text: str) -> bool:
        """Sink ServeRun: публикует прирост всего stream-текста (summary.*+маркеры).

        Запись нефатальна (S1): при сбое `_live_degraded=True`, ход жив,
        повторные вызовы коротко возвращают True, буфер уйдёт в финале.
        """
        if not full_text or not getattr(self, "_sse_open", False):
            return True
        if getattr(self, "_live_degraded", False):
            return True
        with self._get_live_lock():
            sent = getattr(self, "_live_sent_text", "")
            if full_text == sent or not full_text.startswith(sent):
                return True
            delta = full_text[len(sent) :]
            if not delta:
                return True
            ok = self._sse_emit(
                self._sse_chunk({"reasoning_content": delta}),
                mark_content=True,
                fatal=False,
            )
            if ok:
                self._live_sent_text = full_text
                self._live_reasoning_sent = full_text
            else:
                self._live_degraded = True
            return ok

    def _accumulated_reasoning(self) -> str:
        """Накопленный reasoning текущего ServeRun или пустая строка."""
        run = getattr(self, "_current_serve_run", None) or getattr(
            self, "_current_run", None
        )
        getter = getattr(run, "get_accumulated_reasoning", None)
        if run is None or not callable(getter):
            return ""
        try:
            acc = getter()
        except Exception:  # noqa: BLE001
            return ""
        return acc if isinstance(acc, str) else ""

    def _flush_reasoning_before_error(self) -> None:
        """Опережающий сброс неотправленного reasoning перед 502 (AD-003)."""
        if not (getattr(self, "_sse_open", False) or getattr(self, "_stream", False)):
            return
        acc = self._accumulated_reasoning()
        if not acc:
            return
        with self._get_live_lock():
            sent = getattr(self, "_live_sent_text", "")
            if acc == sent or sent.startswith(acc):
                return
            if acc.startswith(sent):
                tail = acc[len(sent) :]
            else:
                common = 0
                for a_ch, b_ch in zip(sent, acc):
                    if a_ch != b_ch:
                        break
                    common += 1
                tail = acc[common:]
            if not tail:
                return
            _log(f"flush_reasoning_before_502 chars={len(tail)}")
            if self._sse_emit(
                self._sse_chunk({"reasoning_content": tail}),
                mark_content=True,
                fatal=False,
            ):
                self._live_sent_text = acc if acc.startswith(sent) else sent + tail
                self._live_reasoning_sent = self._live_sent_text

    def _force_close_connection(self) -> None:
        """Закрытие соединения надзором W без ожидания _wlock (a4)."""
        self._client_gone = True
        conn = getattr(self, "connection", None)
        if conn is None:
            return
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except (OSError, ValueError, AttributeError):
            pass
        try:
            conn.close()
        except (OSError, ValueError, AttributeError):
            pass

    def _sse_begin(self, model: str) -> bool:
        """Заголовки 200 + role-кадр до запуска хода и поток keepalive; False — клиент ушёл."""
        if time.monotonic() >= getattr(self, "_write_deadline", float("inf")):
            self._delivery_failed = True
            self._client_gone = True
            return False
        self._live_sent_text = ""
        self._live_reasoning_sent = ""
        self._live_degraded = False
        self._stream = True
        self._sse_id = f"chatcmpl-muse-{uuid.uuid4().hex[:12]}"
        self._sse_created = int(time.time())
        self._sse_model = model
        with self._wlock:
            self._sse_phase = "OPEN"
        self.close_connection = True
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, OSError):
            self._client_gone = True
            _log("client gone before headers")
            return False
        self._sse_open = True
        if not self._sse_emit(self._sse_chunk({"role": "assistant", "content": ""})):
            return False
        stop = threading.Event()
        self._keepalive_stop = stop
        self._ka_thread = threading.Thread(
            target=self._keepalive_loop, args=(stop,), daemon=True
        )
        self._ka_thread.start()
        return True

    def _keepalive_loop(self, stop: threading.Event) -> None:
        """Пустые data-чанки держат SSE; эффект на idle проверяется живым ходом."""
        while not stop.wait(KEEPALIVE_S):
            if self._client_gone or stop.is_set():
                return
            if not self._sse_emit(self._sse_chunk({"content": ""}), keepalive=True):
                return

    def _sse_stop_keepalive(self) -> None:
        if self._keepalive_stop is not None:
            self._keepalive_stop.set()
        w_deadline = getattr(self, "_write_deadline", float("inf"))
        if w_deadline == float("inf"):
            budget = LIVE_WRITE_TIMEOUT_S
        else:
            budget = min(LIVE_WRITE_TIMEOUT_S, max(0.0, w_deadline - time.monotonic()))
        if self._wlock.acquire(timeout=budget):
            try:
                if self._sse_phase == "OPEN":
                    self._sse_phase = "FINALIZING"
            finally:
                self._wlock.release()
        if self._ka_thread is not None:
            join_budget = 2.0
            if w_deadline != float("inf"):
                join_budget = min(join_budget, max(0.0, w_deadline - time.monotonic()))
            self._ka_thread.join(timeout=join_budget)
        self._keepalive_stop = None
        self._ka_thread = None

    def _client_gone_probe(self) -> bool:
        """Обрыв клиента: FIN даёт пустой peek; ошибки сокета считаем обрывом.

        Режим сокета (timeout/blocking) не меняется: сокет общий с _sse_write
        в соседних потоках, смена режима из пробы ломала бы их запись. Peek идёт
        флагом MSG_DONTWAIT; select(0) заранее отсекает случай «данных нет».
        """
        conn = self.connection
        if conn is None:
            return False
        try:
            ready, _, _ = select.select([conn], [], [], 0)
        except (OSError, ValueError):
            return True
        if not ready:
            return False
        try:
            data = conn.recv(1, socket.MSG_PEEK | getattr(socket, "MSG_DONTWAIT", 0))
        except (BlockingIOError, InterruptedError):
            return False
        except OSError:
            return True
        return data == b""

    def _kill_current_run(self) -> None:
        """Убить группу текущего хода: призраки не переживают обрыв клиента."""
        run = self._current_run
        if run is not None:
            run.close()

    def _watch_client(self, stop: threading.Event) -> None:
        """Надзор за клиентом во время хода: обрыв -> флаг + killpg группы хода.

        Не выходит после первого убийства: ход может зарегистрироваться (или запустить
        процесс) уже после обрыва — kill идемпотентен и повторяется каждый тик до stop.
        """
        reported = False
        while not stop.wait(0.25):
            if self._client_gone or self._client_gone_probe():
                self._client_gone = True
                if not reported:
                    reported = True
                    _log("client gone during run — killing process group")
                self._kill_current_run()

    def _send(self, code: int, payload: dict) -> None:
        if self._sse_open:
            # Заголовки 200 уже ушли: ошибка — кадром SSE, как у OpenAI-совместимых прокси.
            self._sse_stop_keepalive()
            if int(code) == 502:
                self._flush_reasoning_before_error()
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                error = dict(error)
                error.setdefault("code", int(code))
            self._sse_emit({"error": error or payload})
            self._sse_write("data: [DONE]\n\n")
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        w_deadline = getattr(self, "_write_deadline", float("inf"))
        if time.monotonic() >= w_deadline:
            self._delivery_failed = True
            _log("delivery_deadline json response skipped")
            self._force_close_connection()
            return
        conn = getattr(self, "connection", None)
        prev_timeout: Any = None
        have_conn = False
        if (
            conn is not None
            and hasattr(conn, "settimeout")
            and w_deadline != float("inf")
        ):
            try:
                prev_timeout = conn.gettimeout()
                conn.settimeout(max(0.001, w_deadline - time.monotonic()))
                have_conn = True
            except (OSError, ValueError, AttributeError):
                have_conn = False
        try:
            self.send_response(int(code))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self._client_gone = True
            _log("client gone before response")
            self._kill_current_run()
        finally:
            if have_conn:
                try:
                    conn.settimeout(prev_timeout)
                except (OSError, ValueError, AttributeError):
                    pass

    def _send_sse(
        self,
        model: str,
        content: str,
        tool_calls: list[dict],
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int,
        summaries: list[str] | None = None,
    ) -> None:
        """Выдача готового хода в поток SSE (см. модуль-docstring).

        Заголовки и role-кадр обычно уже ушли (_sse_begin до запуска хода); здесь —
        reasoning_content (summaries размышлений) -> tool_calls -> content-чанки
        (~SSE_CHUNK_SIZE символов) -> финал с finish_reason + usage -> `data: [DONE]`.
        """
        finish = "tool_calls" if tool_calls else "stop"
        if not self._sse_open and not self._sse_begin(model):
            return
        self._sse_stop_keepalive()
        chunk = self._sse_chunk
        reasoning = "\n\n".join(s for s in (summaries or []) if s)
        # S2: единый stream-буфер ServeRun (с маркерами) авторитетен для
        # live/final — сравнение с _live_sent_text не даёт ложного diverged.
        accumulated = self._accumulated_reasoning()
        if accumulated:
            reasoning = accumulated
        live_sent = getattr(self, "_live_sent_text", "")
        if reasoning:
            if not live_sent:
                tail = reasoning
            elif reasoning.startswith(live_sent):
                tail = reasoning[len(live_sent) :]
            else:
                common = 0
                for a_ch, b_ch in zip(live_sent, reasoning):
                    if a_ch != b_ch:
                        break
                    common += 1
                _log(
                    f"reasoning_diverged p_len={len(live_sent)} f_len={len(reasoning)} "
                    f"common={common} count=1"
                )
                tail = "\n\n" + reasoning
            if tail and not self._sse_emit(
                chunk({"reasoning_content": tail}), mark_content=True
            ):
                return
            if tail:
                self._live_sent_text = live_sent + tail
                self._live_reasoning_sent = self._live_sent_text
        for tc in tool_calls:
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            delta = {
                "tool_calls": [
                    {
                        "index": tc.get("index", 0),
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": fn.get("name", ""),
                            "arguments": fn.get("arguments", ""),
                        },
                    }
                ]
            }
            if not self._sse_emit(chunk(delta), mark_content=True):
                return
        for piece in _split_sse_chunks(content):
            if time.monotonic() >= getattr(self, "_write_deadline", float("inf")):
                self._delivery_failed = True
                return
            if not self._sse_emit(chunk({"content": piece}), mark_content=True):
                return
            if SSE_CHUNK_DELAY_S > 0:
                _w = getattr(self, "_write_deadline", float("inf"))
                if _w - time.monotonic() <= SSE_CHUNK_DELAY_S:
                    self._delivery_failed = True
                    return
                time.sleep(SSE_CHUNK_DELAY_S)
        final = chunk({}, finish)
        final["usage"] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "reasoning_tokens": reasoning_tokens,
        }
        if self._sse_emit(final):
            self._sse_write("data: [DONE]\n\n")

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/v1/health"):
            with _active_lock:
                active = len(_active)
                quarantined = len(_quarantined_slots)
            self._send(
                200,
                {
                    "ok": True,
                    "transport": "muse-cli",
                    "wrapper": MUSE_WRAPPER,
                    "models": sorted(ALLOWED_MODELS),
                    "default_model": DEFAULT_MODEL,
                    "default_effort": DEFAULT_EFFORT,
                    "active": active,
                    "quarantined": quarantined,
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
            self._send(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": mid,
                            "object": "model",
                            "owned_by": "meta-muse",
                            "created": 0,
                            "context_length": meta["context_length"],
                        }
                        for mid, meta in ALLOWED_MODELS.items()
                    ],
                },
            )
            return
        self._send(404, {"error": {"message": f"not found: {path}"}})

    def do_POST(self) -> None:  # noqa: N802
        if not _auth_ok(self):
            self.close_connection = True
            self._send(
                401, {"error": {"message": "unauthorized", "type": "auth_error"}}
            )
            return
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            self._send(400, {"error": {"message": "invalid json"}})
            return
        if path not in ("/v1/chat/completions", "/chat/completions"):
            self._send(404, {"error": {"message": f"not found: {path}"}})
            return
        try:
            self._serve_json(req)
        finally:
            # Любой выход (в т.ч. обрыв в очереди за слотом): поток keepalive не переживает запрос.
            self._sse_stop_keepalive()
            _done = getattr(self, "_req_done", None)
            if _done is not None:
                _done.set()
            self._write_deadline = float("inf")
            self._exec_deadline = float("inf")
            self._request_deadline = float("inf")
            self._delivery_failed = False

    def _serve_json(self, req: dict) -> None:
        # Абсолютный бюджет запроса a4: t0 при приёме, до очереди и вычислений.
        _t0 = time.monotonic()
        _req_deadline = _t0 + min(TIMEOUT_S, REQUEST_CAP_S)
        _exec_deadline = _req_deadline - FINISH_RESERVE_S
        _write_deadline = _req_deadline - CLOSE_RESERVE_S
        self._request_deadline = _req_deadline
        self._exec_deadline = _exec_deadline
        self._write_deadline = _write_deadline
        self._live_sent_text = ""
        self._live_reasoning_sent = ""
        self._live_degraded = False
        self._current_serve_run = None
        self._stream = req.get("stream") is True
        self._delivery_failed = False
        _req_done = threading.Event()
        self._req_done = _req_done

        def _supervise_w() -> None:
            while not _req_done.wait(0.05):
                if time.monotonic() >= _write_deadline:
                    self._delivery_failed = True
                    _log("delivery_deadline W reached: closing connection")
                    self._kill_current_run()
                    self._force_close_connection()
                    return

        threading.Thread(target=_supervise_w, daemon=True).start()
        model = str(req.get("model") or DEFAULT_MODEL).strip()
        if model not in ALLOWED_MODELS:
            self._send(
                400,
                {
                    "error": {
                        "message": f"unknown model '{model}'; allowed: {sorted(ALLOWED_MODELS)}",
                        "type": "invalid_request_error",
                        "code": "model_not_found",
                    }
                },
            )
            return

        raw_tools = req.get("tools")
        tools = (
            [t for t in raw_tools if isinstance(t, dict)]
            if isinstance(raw_tools, list)
            else []
        )
        tool_choice = req.get("tool_choice")
        emulate_tools = bool(tools) and not _tool_choice_none(tool_choice)

        raw_messages = req.get("messages") or []
        _, raw_turns_text = _messages_to_prompt(raw_messages)
        if not raw_turns_text:
            self._send(
                400,
                {
                    "error": {
                        "message": "no user content",
                        "type": "invalid_request_error",
                    }
                },
            )
            return

        rid = uuid.uuid4().hex[:8]
        limit = _context_limit(model)
        target = _context_target(limit)
        retry_target = _context_retry_target(limit)
        prune_res = _prune_messages(
            raw_messages,
            limit=limit,
            target=target,
            tools=tools,
            tool_choice=tool_choice,
            raw_tools=raw_tools,
        )
        if prune_res.status == "refused":
            _log_context_prune(
                rid, model, "refused_mandatory", 1, limit, target, prune_res
            )
            detail = (
                f"mandatory context exceeds budget "
                f"(est_tokens={prune_res.mandatory_est}, limit={limit})"
            )
            err_msg = f"muse turn failed (rc=1, state=terminal_failed): {detail}"
            _log(
                _format_err_log(
                    model,
                    "refused",
                    {"rc": 1, "state": "terminal_failed", "err": detail},
                    req.get("stream") is True,
                )
            )
            self._send(
                502,
                {
                    "error": {
                        "message": _redact_secrets(err_msg),
                        "detail": _redact_secrets(detail)[:500],
                        "type": "proxy_error",
                        "code": 502,
                    }
                },
            )
            return
        if prune_res.status == "pruned":
            _log_context_prune(
                rid, model, "proactive_prune", 1, limit, target, prune_res
            )

        prompt = prune_res.prompt
        current_est = prune_res.est_after
        reflected_prompts: list[str] = [prompt]

        effort = _map_effort(req)

        if req.get("stream") is True and not self._sse_begin(model):
            return
        while not _slots.acquire(timeout=1.0):
            if self._client_gone or self._client_gone_probe():
                self._client_gone = True
                _log("client gone while waiting for a slot")
                return
            if time.monotonic() >= _exec_deadline - MIN_ATTEMPT_REMAINING_S:
                _log("insufficient remaining budget while waiting for a slot")
                self._send(
                    503, {"error": {"message": "bridge busy", "type": "overloaded"}}
                )
                return
        if self._client_gone or self._client_gone_probe():
            # Клиент ушёл на границе получения слота: ход без надзора не стартует.
            self._client_gone = True
            _log("client gone while waiting for a slot")
            _slots.release()
            return
        if time.monotonic() > _exec_deadline - MIN_ATTEMPT_REMAINING_S:
            _log("insufficient remaining budget after slot acquire")
            _slots.release()
            self._send(503, {"error": {"message": "bridge busy", "type": "overloaded"}})
            return
        watch_stop = threading.Event()
        watcher = threading.Thread(
            target=self._watch_client, args=(watch_stop,), daemon=True
        )
        watcher.start()
        runs: list = []
        terminal_context_err: str | None = None
        context_retry_count = 0
        transient_retry_count = 0
        attempt_calls = [0]
        agg: dict[str, bool] = {
            "approval_seen": False,
            "action": False,
            "allowing": False,
            "degraded": False,
            "observed": False,
        }

        def _update_agg(run: Any, out: dict[str, Any] | None) -> None:
            if run is not None:
                agg["approval_seen"] = agg["approval_seen"] or bool(
                    getattr(run, "approval_seen", False)
                )
                agg["action"] = agg["action"] or bool(
                    getattr(run, "action_possible", False)
                )
                agg["allowing"] = agg["allowing"] or bool(
                    getattr(run, "allowing_decide_attempted", False)
                )
                agg["degraded"] = agg["degraded"] or bool(
                    getattr(run, "approval_degraded", False)
                )
                agg["observed"] = agg["observed"] or bool(
                    getattr(run, "observed_barrier", False)
                )
            if out:
                agg["approval_seen"] = agg["approval_seen"] or bool(
                    out.get("approval_seen")
                )
                agg["action"] = agg["action"] or bool(out.get("action_possible"))
                agg["allowing"] = agg["allowing"] or bool(out.get("allowing_decide"))
                agg["degraded"] = agg["degraded"] or bool(out.get("approval_degraded"))
                observed = out.get("observed_barrier")
                if observed is None:
                    observed = bool(out.get("text") or out.get("summaries"))
                agg["observed"] = agg["observed"] or bool(observed)

        def _can_start(is_exec: bool, *, context: bool = False) -> tuple[bool, str]:
            if self._client_gone or self._client_gone_probe():
                self._client_gone = True
                return False, "client_gone"
            if getattr(self, "_content_started", False):
                return False, "content_started"
            if getattr(self, "_delivery_failed", False):
                return False, "delivery_failed"
            if agg["degraded"]:
                return False, "approval_degraded"
            if agg["approval_seen"] or agg["allowing"]:
                return False, "approval_barrier"
            if is_exec and APPROVAL_MODE == "denyUnmatched":
                return False, "exec_fallback_disabled"
            if runs and not all(getattr(r, "dead_confirmed", True) for r in runs):
                return False, "group_not_dead"
            if time.monotonic() > _exec_deadline - MIN_ATTEMPT_REMAINING_S:
                return False, "insufficient_remaining"
            if context or TRANSIENT_RETRY_SCOPE == "observed-items":
                if agg["observed"]:
                    return False, "observed_barrier"
            elif agg["action"]:
                return False, "action_possible"
            return True, ""

        def _blocked_out(err: str) -> dict[str, Any]:
            return {
                "rc": 1,
                "text": "",
                "chunks": [],
                "err": err,
                "state": "terminal_failed",
                "approval_seen": agg["approval_seen"],
                "action_possible": agg["action"],
                "approval_degraded": agg["degraded"],
                "observed_barrier": agg["observed"],
                "transient": False,
            }

        def run_attempt(
            attempt_prompt: str, *, context: bool = False
        ) -> tuple[dict[str, Any], str]:
            attempt_calls[0] += 1
            ok_gate, gate_reason = _can_start(False, context=context)
            if not ok_gate:
                _log(f"new serve process blocked reason={gate_reason}")
                return _blocked_out(f"new process blocked: {gate_reason}"), "blocked"
            # S4: новый ServeRun (в т.ч. ретрай) стартует с чистого live-префикса.
            self._reset_live_for_attempt()
            serve_run = ServeRun(model, attempt_prompt, effort, WORKSPACE)
            serve_run.exec_deadline = _exec_deadline
            serve_run.write_deadline = _write_deadline
            serve_run.request_deadline = _req_deadline
            if req.get("stream") is True and self._sse_open:
                serve_run.live_sink = self._live_reasoning_sink
            runs.append(serve_run)
            self._current_run = serve_run
            self._current_serve_run = serve_run
            try:
                attempt_out = serve_run.execute()
                _update_agg(serve_run, attempt_out)
                return attempt_out, "serve"
            except ServeUnavailable as exc:
                _update_agg(serve_run, None)
                if self._client_gone:
                    _log("client gone during serve — exec fallback skipped")
                    return (
                        {
                            "rc": -1,
                            "text": "",
                            "err": "client gone",
                            "state": "client_gone",
                        },
                        "aborted",
                    )
                exc_text = str(exc)
                safe_exc = _sanitize_reflected(
                    exc_text, [*reflected_prompts, attempt_prompt], raw_messages
                )
                safe_exc = re.sub(
                    r"[\x00-\x1f\x7f-\x9f\u2028\u2029]", " ", safe_exc
                ).strip()[:300]
                if _is_transient_text(exc_text) and not serve_run.ceiling_seen:
                    return (
                        {
                            "rc": 1,
                            "text": "",
                            "err": exc_text,
                            "state": "terminal_failed",
                            "transient": True,
                            "approval_seen": agg["approval_seen"],
                            "action_possible": agg["action"],
                            "approval_degraded": agg["degraded"],
                            "observed_barrier": agg["observed"],
                        },
                        "serve",
                    )
                ok_exec, exec_reason = _can_start(True, context=context)
                if not ok_exec:
                    if exec_reason == "exec_fallback_disabled":
                        err = (
                            "exec_fallback_disabled(denyUnmatched): "
                            f"serve unavailable: {safe_exc}"
                        )
                    else:
                        err = exc_text
                    _log(
                        f"serve unavailable ({safe_exc}), exec fallback blocked "
                        f"reason={exec_reason}"
                    )
                    return _blocked_out(err), "serve"
                _log(f"serve unavailable ({safe_exc}), fallback exec model={model}")
                exec_run = Run(model, attempt_prompt, effort, WORKSPACE)
                exec_run.exec_deadline = _exec_deadline
                exec_run.action_possible = True
                agg["action"] = True
                runs.append(exec_run)
                self._current_run = exec_run
                attempt_out = exec_run.execute()
                _update_agg(exec_run, attempt_out)
                return attempt_out, "exec-after-serve-fallback"

        out: dict[str, Any] = {
            "rc": 1,
            "text": "",
            "err": "no attempt",
            "state": "terminal_failed",
        }
        via = "none"
        try:
            out, via = run_attempt(prompt)
            while True:
                if out.get("rc") == 0 and out.get("state") == "ok":
                    break
                if self._client_gone or getattr(self, "_delivery_failed", False):
                    break
                raw_err = str(out.get("err") or "")
                is_hard_threshold = (
                    out.get("rc") != 0
                    and out.get("state") == "terminal_failed"
                    and (
                        bool(out.get("hard_threshold"))
                        or HARD_THRESHOLD_ERR_SUBSTR in raw_err
                    )
                )
                # Сначала контекстный повтор (AD-005), затем транзиентный.
                if (
                    is_hard_threshold
                    and context_retry_count == 0
                    and attempt_calls[0] < 4
                    and not getattr(self, "_content_started", False)
                ):
                    for run in runs:
                        run.close()
                    if not all(run.dead_confirmed for run in runs):
                        _log(
                            "context retry skipped: first attempt process group not confirmed dead"
                        )
                        break
                    ok_ctx, ctx_reason = _can_start(False, context=True)
                    if not ok_ctx:
                        _log(f"context retry skipped reason={ctx_reason}")
                        break
                    retry_res = _prune_messages(
                        raw_messages,
                        limit=retry_target,
                        target=retry_target,
                        tools=tools,
                        tool_choice=tool_choice,
                        raw_tools=raw_tools,
                    )
                    if retry_res.status == "refused":
                        _log_context_prune(
                            rid,
                            model,
                            "refused_retry",
                            2,
                            limit,
                            retry_target,
                            retry_res,
                        )
                        terminal_context_err = (
                            f"mandatory context exceeds budget "
                            f"(est_tokens={retry_res.mandatory_est}, limit={retry_target})"
                        )
                        break
                    if retry_res.est_after >= current_est or (
                        time.monotonic() > _exec_deadline - MIN_ATTEMPT_REMAINING_S
                    ):
                        _log_context_prune(
                            rid,
                            model,
                            "refused_retry",
                            2,
                            limit,
                            retry_target,
                            retry_res,
                        )
                        terminal_context_err = (
                            "context hard threshold exceeded after single "
                            f"compaction retry (est_tokens={retry_res.est_after}, "
                            f"target={retry_target})"
                        )
                        break
                    if self._client_gone or self._client_gone_probe():
                        self._client_gone = True
                        break
                    context_retry_count = 1
                    _log_context_prune(
                        rid,
                        model,
                        "hard_threshold_retry",
                        2,
                        limit,
                        retry_target,
                        retry_res,
                    )
                    prompt = retry_res.prompt
                    current_est = retry_res.est_after
                    reflected_prompts.append(prompt)
                    out, via = run_attempt(prompt, context=True)
                    raw_err_2 = str(out.get("err") or "")
                    if (
                        out.get("rc") != 0
                        and out.get("state") == "terminal_failed"
                        and (
                            bool(out.get("hard_threshold"))
                            or HARD_THRESHOLD_ERR_SUBSTR in raw_err_2
                        )
                    ):
                        terminal_context_err = (
                            "context hard threshold exceeded after single "
                            f"compaction retry (est_tokens={current_est}, "
                            f"target={retry_target})"
                        )
                    continue
                is_transient = (
                    out.get("rc") != 0
                    and str(out.get("state") or "") not in NON_RETRYABLE_STATES
                    and (bool(out.get("transient")) or _is_transient_text(raw_err))
                )
                max_calls = 4 if context_retry_count else 3
                if (
                    not is_transient
                    or transient_retry_count >= TRANSIENT_MAX_RETRIES
                    or attempt_calls[0] >= max_calls
                ):
                    if is_transient and getattr(self, "_content_started", False):
                        _log("retry_blocked reason=content_started")
                    break
                for run in runs:
                    run.close()
                ok_retry, retry_reason = _can_start(False)
                if not ok_retry:
                    if getattr(self, "_content_started", False):
                        _log(f"retry_blocked reason={retry_reason} content_started=1")
                    else:
                        _log(f"transient retry blocked reason={retry_reason}")
                    break
                backoff = TRANSIENT_BACKOFF_S
                pause = backoff[min(transient_retry_count, len(backoff) - 1)]
                if TRANSIENT_JITTER_S > 0:
                    pause += random.uniform(0, TRANSIENT_JITTER_S)
                transient_retry_count += 1
                if TRANSIENT_RETRY_SCOPE == "observed-items":
                    _log(
                        "transient retry retry_scope=observed-items "
                        f"n={transient_retry_count}"
                    )
                else:
                    _log(
                        "transient retry retry_scope=pre-action "
                        f"n={transient_retry_count} pause_s={pause:.2f}"
                    )
                pause_end = min(time.monotonic() + pause, _exec_deadline)
                client_left = False
                while time.monotonic() < pause_end:
                    if self._client_gone or self._client_gone_probe():
                        self._client_gone = True
                        client_left = True
                        break
                    time.sleep(min(0.05, max(0.0, pause_end - time.monotonic())))
                if client_left:
                    break
                out, via = run_attempt(prompt)
        finally:
            # Слот отпускаем после остановки надзора (kill -> wait уже внутри execute).
            watch_stop.set()
            watcher.join(timeout=2)
            # close() идемпотентен и ждёт уборку, начатую другим потоком (надзор, таймер):
            # dead_confirmed читается только после её конца. Заодно страхует ход, упавший
            # между Popen и собственным finally execute().
            for run in runs:
                run.close()
            if all(run.dead_confirmed for run in runs):
                _slots.release()
            else:
                # Смерть группы не подтверждена: слот не освобождается, пока она жива (карантин).
                _quarantine_slot([run for run in runs if not run.dead_confirmed])

        if self._client_gone:
            # Клиент ушёл: ответ в закрытый сокет не пишется (ни JSON, ни кадр ошибки).
            _log("client gone — response skipped")
            return
        # Только локальная граница запроса знает отражённый промпт; глобально его не храним.
        out = dict(out)
        diagnostic = _sanitize_reflected(
            str(out.get("err") or ""), reflected_prompts, raw_messages
        )
        if terminal_context_err is not None:
            diagnostic = _redact_secrets(terminal_context_err)
        out["err"] = _redact_secrets(diagnostic)
        if out.get("state") in ("launcher_missing", "spawn_failed"):
            _log(_format_err_log(model, via, out, req.get("stream") is True))
            self._send(
                502,
                {
                    "error": {
                        "message": _redact_secrets(str(out.get("err") or out["state"])),
                        "detail": _redact_secrets(str(out.get("err") or ""))[:500],
                        "type": "proxy_error",
                        "code": 502,
                    }
                },
            )
            return
        if out.get("state") != "ok" or out.get("rc") != 0:
            # Провал хода (failed terminal, rc != 0, таймаут): частичный текст и tool-блоки
            # не выдаются как успешный финал — SSE error + [DONE] либо 502 (Q-004).
            hint = " (proxy :10816 DOWN?)" if out.get("rc") == 42 else ""
            _log(_format_err_log(model, via, out, req.get("stream") is True))
            detail = _redact_secrets(str(out.get("err") or ""))[:500]
            err_message = (
                f"muse turn failed (rc={out.get('rc')}, state={out.get('state')}){hint}"
            )
            if detail and detail != f"state={out.get('state')} rc={out.get('rc')}":
                err_message = f"{err_message}: {detail}"
            self._send(
                502,
                {
                    "error": {
                        "message": _redact_secrets(err_message),
                        "detail": detail,
                        "type": "proxy_error",
                        "code": 502,
                    }
                },
            )
            return
        content = out["text"]
        tool_calls: list[dict] = []
        if emulate_tools and content:
            content, tool_calls = _split_tool_calls(out.get("chunks") or [content])
        if not content and not tool_calls:
            hint = " (proxy :10816 DOWN?)" if out.get("rc") == 42 else ""
            _log(
                _format_err_log(
                    model, via, out, req.get("stream") is True, "empty_output"
                )
            )
            detail = _redact_secrets(str(out.get("err") or ""))[:500]
            err_message = (
                f"muse exec produced no text (rc={out.get('rc')}, "
                f"state={out.get('state')}){hint}"
            )
            if detail and detail != f"state={out.get('state')} rc={out.get('rc')}":
                err_message = f"{err_message}: {detail}"
            self._send(
                502,
                {
                    "error": {
                        "message": _redact_secrets(err_message),
                        "detail": detail,
                        "type": "proxy_error",
                        "code": 502,
                    }
                },
            )
            return

        prompt_tokens = _estimate_usage_tokens(prompt)
        completion_tokens = _estimate_usage_tokens(out["text"])
        # Serve даёт настоящие токены (session/tokenUsage); exec — оценку.
        # tokenUsage serve не даёт promptTokens — фолбэк на оценку по каждому
        # полю отдельно (раньше общий if занулял prompt при пустом поле).
        ru = out.get("usage") if isinstance(out.get("usage"), dict) else {}
        ru_prompt = ru.get("promptTokens") or ru.get("prompt_tokens") or 0
        ru_output = ru.get("outputTokens") or ru.get("output_tokens") or 0
        try:
            ru_prompt = int(ru_prompt)
        except (TypeError, ValueError):
            ru_prompt = 0
        try:
            ru_output = int(ru_output)
        except (TypeError, ValueError):
            ru_output = 0
        if ru_prompt > 0:
            prompt_tokens = ru_prompt
        if ru_output > 0:
            completion_tokens = ru_output
        ru_reasoning = ru.get("reasoningTokens") or ru.get("reasoning_tokens") or 0
        try:
            reasoning_tokens = int(ru_reasoning)
        except (TypeError, ValueError):
            reasoning_tokens = 0
        if reasoning_tokens < 0:
            reasoning_tokens = 0
        raw_summaries = out.get("summaries")
        summaries: list[str] = (
            [s for s in raw_summaries if isinstance(s, str)]
            if isinstance(raw_summaries, list)
            else []
        )
        sum_chars = sum(len(s) for s in summaries)
        if summaries:
            preview = next((s for s in summaries if s), "")[:300]
            _log(
                f"reasoning summaries={len(summaries)} chars={sum_chars} "
                f"reasoning_tokens={reasoning_tokens} preview={preview!r}"
            )
        message: dict[str, Any] = {"role": "assistant", "content": content}
        finish = "stop"
        if tool_calls:
            message["tool_calls"] = tool_calls
            finish = "tool_calls"
        _log(
            f"done model={model} via={via} rc={out.get('rc')} state={out.get('state')} "
            f"tools={len(tool_calls)} out_chars={len(out['text'])} "
            f"stream={req.get('stream') is True}"
        )
        if req.get("stream") is True:
            self._send_sse(
                model,
                content,
                tool_calls,
                prompt_tokens,
                completion_tokens,
                reasoning_tokens,
                summaries,
            )
            return
        self._send(
            200,
            {
                "id": f"chatcmpl-muse-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "reasoning_tokens": reasoning_tokens,
                },
                "reasoning_summaries": summaries,
            },
        )


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    if not AUTH_KEY:
        sys.stderr.write("MUSE_BRIDGE_KEY is required; refusing to start\n")
        return 2
    try:
        _validate_startup_config()
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}; refusing to start\n")
        _log(f"startup config invalid: {exc}")
        return 2
    if TRANSIENT_RETRY_SCOPE == "observed-items":
        _log("warning retry_scope=observed-items at-least-once accepted by operator")
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log(f"workspace mkdir failed: {exc}")
    _log(
        f"start host={HOST} port={PORT} models={sorted(ALLOWED_MODELS)} wrapper={MUSE_WRAPPER}"
    )
    server = Server((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
