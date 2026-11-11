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
Поле `autonomy`: `low|medium|high|off`, DROID_DEFAULT_AUTONOMY, безопасный дефолт `off`.
`high` требует DROID_ALLOW_HIGH_AUTONOMY=1; иное = 400 `unsupported_autonomy`.
`--skip-permissions-unsafe` не используется никогда; нативные tools droid отключены,
запросы разрешений отклоняются (`autoRejectPermissionRequests`).
Вывод хода удерживается до `agent_turn_completed` и затем отдаётся в OpenAI Chat
Completions (stream и не-stream); thinking транслируется в `reasoning_content`.

Каталог моделей — `fleet.json` (env `DROID_DSH_BRIDGE_FLEET`): читается один раз
при старте, структурно проверяется (класс I — отказ старта), уровни reasoning
берутся из каталога (запрошенный строковый уровень клампится к нему вниз).
Изображения принимаются только по контракту: data-URL PNG, только роли user,
только для моделей с применимым proof (метод workspace-read); файлы кладутся
в per-run каталог `workspace/img-<uuid>` (0700/0600) и удаляются при любом исходе.

Мост эмулирует OpenAI function calling (дословно из claude-p-bridge): если запрос
содержит непустой `tools`, в промпт добавляется протокол и схемы инструментов.

Ключи авторизации берутся из текущего окружения и ~/.dsh/.env:
BRIDGE_KEY и DROID_DSH_BRIDGE_KEY; ротация файла отзывает прежние ключи;
в окружение дочернего процесса ключи моста (любые `*_BRIDGE_KEY`, `BRIDGE_*KEY*`)
не передаются. FACTORY_API_KEY (headless-вход Droid
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
import hmac
import itertools
import json
import math
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
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Mapping, cast

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # пакеты core/ и adapters/ рядом с server.py
import b_guard  # noqa: E402  - охранник B: автоматический контур профилей DSH (RW-003)
from agent_browser import (  # noqa: E402,F401  - единый loopback-контур CDP (ADR-0016): мост и CLI
    discover_local_cdp_url,
    is_loopback_cdp_url,
)
from tools.receipt_schema import (  # noqa: E402,F401
    RECEIPT_PROBES as RECEIPT_PROBES, RECEIPT_SCHEMA, RPC_API_VERSION, SETTINGS_PROFILE as SETTINGS_PROFILE,
    TOOLS_POLICY as TOOLS_POLICY, ReceiptV3, catalog_tool_ids, receipt_gate_problem,
    settings_profile_digest as settings_profile_digest, tools_policy_digest as tools_policy_digest,
    validate_model_catalog, validate_receipt_components,
)

from adapters import ADAPTER_KINDS  # noqa: E402  - реестр видов адаптеров задан в коде
from adapters.passthrough_adapter import (  # noqa: E402
    ClientGone,
    PassthroughAdapter,
    PassthroughLimits,
    ResponseSink,
)
from core.backend_adapter import (  # noqa: E402
    EFFORT_LEVELS as EFFORT_LEVELS,
    AdapterRegistry,
    FleetViolation,
    ImageAttachment,
    StreamSink,
    Transcript,
    TranscriptItem,
    TurnContext,
    ToolCall,
    build_catalog,
    is_bridge_secret_name,
    strip_bridge_secrets,
)
from core import context_resilience as ctxres  # noqa: E402
from core.resilience import (  # noqa: E402
    ResilienceError,
    ResilienceLease,
    ResilienceManager,
)
from core.lifecycle import (  # noqa: E402,F401 - сохраняем прежние реэкспорты фасада
    DEFAULT_DRAIN_SECONDS,
    HubLifecycleManager,
    KEEPALIVE_INTERVAL_S,
    QoSSlotManager as QoSSlotManager,
    QUEUE_TIMEOUT_S as QOS_DEFAULT_QUEUE_TIMEOUT_S,
    RESERVED_INTERACTIVE_SLOTS,
    get_qos_manager,
    has_live_parent,
)
from core.tool_emulation import (  # noqa: E402,F401  - общая эмуляция tools (MB-REQ-007), реэкспорт имён
    TOOL_CALL_CLOSE,
    TOOL_CALL_OPEN,
    LiveParserError,
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
    build_tool_schemas,
    finalize_turn,
    sanitize_tool_call,
)
from core.stream_framing import build_stream_error_chunk  # noqa: E402
from core.turn_session_manager import (  # noqa: E402
    GapDetectedError,
    ManagedTurn,
    TurnSessionManager,
    _is_detached_enabled,
    _is_drain_enabled,
    _is_watchdog_enabled as _is_watchdog_enabled,
    hash_token,
    validate_turn_id,
)
from core.usage_wire import normalize_prompt_cache_details  # noqa: E402
from core.watchdog import (  # noqa: E402,F401
    DEFAULT_IDLE_TIMEOUT_S,
    DEFAULT_SAFETY_CAP_S,
    AdaptiveTimeoutController,
    ProcessWatchdog,
)
from core.model_penalty import get_penalty_tracker  # noqa: E402
from core.cli_runtime_config import (  # noqa: E402 - импорт после настройки путей пакетов
    CliRuntimeConfig,
    WatchdogConfig,
    cli_label,
    cli_number,
)
from core.liveness_registry import get_registry, new_passthrough_turn_id  # noqa: E402
from core.liveness_signals import FLAG_TELEMETRY, passthrough_window  # noqa: E402
from core.runtime_env import DynamicFlagSource, flag_enabled  # noqa: E402
from core.request_telemetry import RequestTelemetryStore  # noqa: E402
from core.telemetry_hooks import TelemetryHooksMixin, known_model, resolve_backend_topology, telemetry_note, telemetry_tail  # noqa: E402
from core.gateway_execution_policy import (  # noqa: E402
    AUTONOMY_LEVELS as AUTONOMY_LEVELS,
    AUTONOMY_OFF as AUTONOMY_OFF,
    AutonomyViolation,
    RpcError as RpcError,
    RpcPermissionDenied as RpcPermissionDenied,
    allow_high_autonomy,
    default_autonomy,
    denied_subagent,
    permission_event,
    permission_frame,
    require,
    resolve_autonomy_decision,
    validate_autonomy_request,
    validate_boolean_flags,
)
from core.catalog_flags import (  # noqa: E402
    catalog_flags,
    load_sidecar_view,
    quarantine_gate_enabled,
    resolve_fleet_path,
    sidecar_allowlist,
)
from core import gated_registry as greg, quarantine_gate as qgate  # noqa: E402
from core.droid_session_gate import ToolsGateError, admit_model, plan_tools_disable, verify_tools_disabled  # noqa: E402
from core.effort_policy import (  # noqa: E402
    DEFAULT_LOG_EFFORT_MAX_CHARS, EFFORT_ORDER, FLAG_EFFORT_CATALOG as FLAG_EFFORT_CATALOG, ModelEffortSpec,
    catalog_effort_specs, clamp_effort_downward, describe_clamp, resolve_alias_effort,
    resolve_model_effort_fields, resolve_passthrough_effort,
)
CLI_CFG = CliRuntimeConfig.from_env()
REQUEST_TELEMETRY = RequestTelemetryStore()  # DuckDB/sqlite3, неблокирующая запись, BRIDGE_TELEMETRY_* (core/defaults.py)


def resolve_target_model(model_entry: dict, requested_model_id: str) -> str:
    """Возвращает каноническую целевую модель для CLI/бэкенда (upstream_model при наличии)."""
    if not isinstance(model_entry, dict):
        return requested_model_id
    upstream = model_entry.get("upstream_model")
    if isinstance(upstream, str) and upstream.strip():
        return upstream.strip()
    return requested_model_id


def build_cli_model_selection(ctx: dict) -> str:
    """Выбирает целевую модель для запуска CLI-процесса (с учётом upstream_model)."""
    return ctx.get("target_model") or ctx["model"]


def prepare_passthrough_request(
    req: dict,
    model: dict,
    model_id: str,
    alias: tuple[str, str] | None = None,
    alias_effort: str | None = None,
    effort_on: bool = False,
) -> tuple[dict, Any]:
    """Формирует тело запроса для passthrough-маршрута с трансляцией upstream_model и effort."""
    upstream_model = model.get("upstream_model")
    has_upstream = isinstance(upstream_model, str) and bool(upstream_model.strip())
    pt_effort = resolve_passthrough_effort(
        req.get("reasoning_effort"),
        alias_effort,
        ModelEffortSpec.from_catalog_entry(model) if effort_on else ModelEffortSpec(),
        enabled=effort_on,
    )
    if has_upstream or alias or pt_effort.apply:
        target_model = resolve_target_model(model, model_id)
        req = {**req, "model": target_model}
        if pt_effort.apply:
            req["reasoning_effort"] = pt_effort.value
    return req, pt_effort


def _resolve_backend_topology(backend_id: str, route_mode: str) -> tuple[str, str]:
    """backend_id -> (outbound_target, egress_proxy) телеметрии; карта настраивается через env."""
    return resolve_backend_topology(BACKENDS, backend_id, route_mode)


HOME = Path.home()


def _bridge_env(name: str, default: str = "") -> str:
    """Читает параметр хаба с legacy fallback; принимает суффикс или полное имя (пустое canonical уступает legacy)."""
    if name.startswith("BRIDGE_"):
        value = os.environ.get(name) or os.environ.get("DROID_DSH_" + name)
        return value if value is not None else default
    for prefix in ("BRIDGE_", "DROID_DSH_BRIDGE_"):
        value = os.environ.get(prefix + name, "").strip()
        if value:
            return value
    return default


def _log(msg: str) -> None:
    """Диагностика в stderr (файлы вне каталога моста не создаём)."""
    try:
        sys.stderr.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}\n")
        sys.stderr.flush()
    except OSError:
        pass


HOST = _bridge_env("HOST", "127.0.0.1")
PORT = int(_bridge_env("PORT", "9882"))
AUTH_KEY = _bridge_env("KEY")
BRIDGE_KEY = AUTH_KEY
LAUNCHER = CLI_CFG.launcher or str(HOME / ".config" / "factory-launch" / "droid-cli.sh")
# Явный DROID_DSH_BRIDGE_FLEET приоритетнее флага BRIDGE_COMPILED_FLEET_ENABLED (стенды тестов).
FLEET_PATH = resolve_fleet_path(ROOT / "fleet.json", ADAPTER_KINDS)
ENV_MODEL = os.environ.get("DROID_DSH_BRIDGE_MODEL", "").strip()
IMAGE_PROBE = os.environ.get("DROID_DSH_BRIDGE_IMAGE_PROBE", "") == "1"
# ADR 0010: санитизация аргументов tool_calls (пустые опциональные строки, распаковка `parallel`).
BRIDGE_SANITIZE_TOOL_CALLS = os.getenv(
    "BRIDGE_SANITIZE_TOOL_CALLS", "true"
).lower() in ("true", "1", "yes")
# ADR 0011 AD-005: лимиты читаются здесь (не в ядре, BND-001) и передаются в ядро аргументами:
# BRIDGE_MAX_PARALLEL_CALLS (по умолчанию 64), BRIDGE_MAX_PARALLEL_DEPTH, лимиты passthrough.
BRIDGE_LIMITS = PassthroughLimits.from_env()


def _load_request_config() -> dict[str, Any]:
    """Прочитать и проверить настройки атрибуции и псевдонимов без вывода значений."""

    def warning(name: str) -> None:
        _log(f"bridge_config_invalid name={name} fallback=default")

    def boolean(name: str) -> bool:
        value = _bridge_env(name, "1").lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
        warning(name)
        return True

    def token(name: str, default: str, pattern: str) -> str:
        value = _bridge_env(name, default)
        if re.fullmatch(pattern, value):
            return value
        warning(name)
        return default

    try:
        max_len = int(_bridge_env("TRACE_ID_MAX_LEN", "64"))
        if not 8 <= max_len <= 256:
            raise ValueError("trace length")
    except ValueError:
        warning("TRACE_ID_MAX_LEN")
        max_len = 64
    request_header = token("REQUEST_ID_HEADER", "X-Request-Id", r"[A-Za-z0-9-]{1,64}")
    subagent_header = token(
        "SUBAGENT_ID_HEADER", "X-Subagent-Id", r"[A-Za-z0-9-]{1,64}"
    )
    if request_header.lower() == subagent_header.lower():
        warning("SUBAGENT_ID_HEADER")
        subagent_header = "X-Subagent-Id"
        if request_header.lower() == subagent_header.lower():
            warning("REQUEST_ID_HEADER")
            request_header = "X-Request-Id"
    default_suffixes = "minimal,low,medium,high,xhigh,max"
    values = tuple(
        v.strip() for v in _bridge_env("EFFORT_SUFFIXES", default_suffixes).split(",")
    )
    suffixes = tuple(dict.fromkeys(v for v in values if v in EFFORT_ORDER))
    if len(suffixes) != len(set(values)) or not suffixes:
        warning("EFFORT_SUFFIXES")
    if not suffixes:
        suffixes = tuple(default_suffixes.split(","))
    advertised = _bridge_env(
        "ADVERTISE_EFFORT_ALIASES",
        "off",
    )
    return {
        "REQUEST_ATTRIBUTION_ENABLED": boolean("REQUEST_ATTRIBUTION_ENABLED"),
        "TRACE_ID_MAX_LEN": max_len,
        "REQUEST_ID_HEADER": request_header,
        "SUBAGENT_ID_HEADER": subagent_header,
        "REQUEST_ID_PREFIX": token(
            "REQUEST_ID_PREFIX", "req_", r"[A-Za-z0-9_.:@-]{0,16}"
        ),
        "EFFORT_ALIAS_ENABLED": boolean("EFFORT_ALIAS_ENABLED"),
        "EFFORT_SUFFIXES": suffixes,
        "ADVERTISED_EFFORT_ALIASES": ()
        if advertised.lower() == "off"
        else tuple(
            dict.fromkeys(v.strip() for v in advertised.split(",") if v.strip())
        ),
    }


_REQUEST_CONFIG = _load_request_config()
REQUEST_ATTRIBUTION_ENABLED = bool(_REQUEST_CONFIG["REQUEST_ATTRIBUTION_ENABLED"])
TRACE_ID_MAX_LEN = int(_REQUEST_CONFIG["TRACE_ID_MAX_LEN"])
REQUEST_ID_HEADER = str(_REQUEST_CONFIG["REQUEST_ID_HEADER"])
SUBAGENT_ID_HEADER = str(_REQUEST_CONFIG["SUBAGENT_ID_HEADER"])
REQUEST_ID_PREFIX = str(_REQUEST_CONFIG["REQUEST_ID_PREFIX"])
EFFORT_ALIAS_ENABLED = bool(_REQUEST_CONFIG["EFFORT_ALIAS_ENABLED"])
EFFORT_SUFFIXES = cast(tuple[str, ...], _REQUEST_CONFIG["EFFORT_SUFFIXES"])
ADVERTISED_EFFORT_ALIASES = cast(
    tuple[str, ...], _REQUEST_CONFIG["ADVERTISED_EFFORT_ALIASES"]
)


@dataclass(frozen=True)
class RequestTrace:
    """Проверенные идентификаторы одного HTTP-запроса."""

    request_id: str
    subagent_id: str | None
    request_id_source: str


@functools.cache
def _trace_pattern(max_len: int) -> re.Pattern[str]:
    return re.compile(r"[A-Za-z0-9_.:@-]{1,%d}" % max_len)


def _sanitize_trace_id(value: object, max_len: int) -> str | None:
    """Пропустить только короткий ASCII-идентификатор без разделителей заголовков."""
    if isinstance(value, str) and _trace_pattern(max_len).fullmatch(value):
        return value
    return None


def _resolve_trace(headers: Mapping[str, str], req: Mapping[str, Any]) -> RequestTrace:
    """Выбрать идентификаторы по приоритету header → extra_body → body."""
    lowered = {key.lower(): value for key, value in headers.items()}
    extra = req.get("extra_body")
    extra = extra if isinstance(extra, Mapping) else {}

    def resolve(field: str, header: str) -> tuple[str | None, str]:
        for source, values, name in (
            ("header", lowered, header.lower()),
            ("extra_body", extra, field),
            ("body", req, field),
        ):
            if name not in values:
                continue
            value = values[name]
            clean = _sanitize_trace_id(value, TRACE_ID_MAX_LEN)
            if clean is not None:
                return clean, source
            size = len(value) if isinstance(value, (str, list, dict)) else 0
            _log(f"trace_id_rejected field={field} source={source} len={size}")
        return None, "generated"

    rid, source = resolve("request_id", REQUEST_ID_HEADER)
    sid, _ = resolve("subagent_id", SUBAGENT_ID_HEADER)
    if rid is None:
        random_id = uuid.uuid4().hex[: min(12, TRACE_ID_MAX_LEN)]
        rid = REQUEST_ID_PREFIX[: max(0, TRACE_ID_MAX_LEN - len(random_id))] + random_id
    return RequestTrace(rid, sid, source)


def _resolve_model_alias(
    raw_id: str, catalogue: Mapping[str, Any]
) -> tuple[str, str] | None:
    """Разрешить суффикс effort, оставляя точные записи каталога приоритетными."""
    return resolve_alias_effort(raw_id, catalogue, EFFORT_SUFFIXES, EFFORT_ALIAS_ENABLED)


def _trace_headers(trace: RequestTrace | None) -> list[tuple[str, str]]:
    """Сформировать заголовки только из проверенного состояния запроса."""
    if not REQUEST_ATTRIBUTION_ENABLED or trace is None:
        return []
    headers = [(REQUEST_ID_HEADER, trace.request_id)]
    if trace.subagent_id is not None:
        headers.append((SUBAGENT_ID_HEADER, trace.subagent_id))
    return headers


_SANITIZE_LIMITS = {
    "max_parallel_calls": BRIDGE_LIMITS.max_parallel_calls,
    "max_parallel_depth": BRIDGE_LIMITS.max_parallel_depth,
}
WORKSPACE = ROOT / "workspace"
MAX_CONCURRENT = int(_bridge_env("MAX_CONCURRENT", "128"))
QUEUE_TIMEOUT_S = float(_bridge_env("QUEUE_TIMEOUT_S", "900.0"))
TIMEOUT_S = float(_bridge_env("TIMEOUT_S", "1800.0"))
KEEPALIVE_S = float(_bridge_env("KEEPALIVE_S", "10.0"))
IDLE_TIMEOUT_S = float(_bridge_env("IDLE_TIMEOUT_S", "120.0"))
SAFETY_CAP_S = WatchdogConfig.from_env().safety_cap_s
UI_RESERVED_SLOTS = int(_bridge_env("UI_RESERVED_SLOTS", "2"))
SUBAGENT_MAX_CONCURRENT = int(_bridge_env("SUBAGENT_MAX_CONCURRENT", "128"))
SUBAGENT_QUEUE_TIMEOUT_S = float(_bridge_env("SUBAGENT_QUEUE_TIMEOUT_S", "120.0"))
SUBAGENT_WATCHDOG_CAP_S = float(_bridge_env("SUBAGENT_WATCHDOG_CAP_S", "300.0"))


# RW-009 в живом ходе: запись живого куска клиенту ограничена этим таймаутом (а не 300с
# socket-таймаута соединения) — зависший/нечитающий клиент не держит T/L (см. sse_writer в
# _serve_sse и add_content/add_reasoning в Handler._execute).
def parse_live_write_timeout(default: float = 30.0) -> float:
    """Write timeout from env; invalid -> ConfigError."""
    return cli_number("live_write_timeout_s", default)


LIVE_WRITE_TIMEOUT_S: float = parse_live_write_timeout(30.0)
# Таймаут первого события stream-json от `droid exec` (с момента старта процесса).
FIRST_TOKEN_TIMEOUT_S = CLI_CFG.first_token_timeout_s
# Окно после успешного хода, в котором лончеру передаётся DROID_SKIP_PREFLIGHT=1.
PREFLIGHT_SKIP_WINDOW_S = 120.0


# Автономность RPC сверяется read-back; безопасный дефолт off — read-only.
_allow_high_autonomy = functools.partial(allow_high_autonomy, "DROID")
_default_autonomy = functools.partial(default_autonomy, "DROID")
AUTONOMY_DEFAULT = _default_autonomy()
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


def _quarantine_denial(model_id: str, subagent_id: str | None) -> "qgate.Deny | None":
    """Решение карантинного гейта (флаг `BRIDGE_QUARANTINE_GATE_ENABLED`): `Deny` или `None`.

    Роль — из `X-Subagent-Id`; сайдкар битый — fail-closed для не-open ролей.
    """
    if not quarantine_gate_enabled():
        return None
    try:
        view = load_sidecar_view()
    except (OSError, ValueError):
        classes = qgate.RoleClasses.from_env()
        if classes.is_open(qgate.role_from_subagent_id(subagent_id)):
            return None
        return qgate.Deny(model=model_id, status="sidecar_unreadable")
    decision = qgate.gate(model_id, subagent_id, view)
    return decision if isinstance(decision, qgate.Deny) else None


def _build_catalog(data: Any) -> dict:
    """Общий с fleet_check структурный валидатор; env/probe остаются настройками хоста."""
    flags = catalog_flags()
    return build_catalog(
        data,
        ADAPTER_KINDS,
        env_model=ENV_MODEL,
        image_probe=IMAGE_PROBE,
        mode="isolate" if flags.safe_catalog else "strict",
        constraints_enabled=flags.provider_constraints,
        allowlist=sidecar_allowlist() if flags.provider_constraints else None,
    )


def _load_fleet() -> dict:
    """Прочитать и проверить fleet.json; при нарушении класса I — отказ старта."""
    catalog = None
    try:
        raw = FLEET_PATH.read_bytes()
    except OSError:
        raw = None
    if raw is not None:
        try:
            catalog = greg.gated_catalog(raw, _build_catalog)
        except FleetViolation:
            raise
        except (ValueError, UnicodeDecodeError):
            catalog = None
    if catalog is None:
        sys.stderr.write("fleet_invalid model=- reason=fleet_unreadable\n")
        sys.stderr.flush()
        raise SystemExit(1)
    for rejected_id, reason in cast(dict[str, str], catalog.get("rejected", {})).items():
        sys.stderr.write(f"fleet_model_rejected model={rejected_id} reason={reason}\n")
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
BACKENDS: AdapterRegistry = greg.GatedRegistry.from_fleet(
    FLEET, ADAPTER_KINDS, lambda: FLEET, sys.modules[__name__]
)

# Токеноподобные последовательности: длинные (>=24) и явные Factory-ключи `fk-`
# любой длины — короткий ключ иначе проходил мимо маскировщика в журнал.
_SECRET = re.compile(r"[A-Za-z0-9_\-]{24,}|fk-[A-Za-z0-9_\-]{4,}")
_NOISE = re.compile(
    r"NODE_TLS_REJECT_UNAUTHORIZED|--trace-warnings|^\(node:\d+\)", re.I
)

_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
_subagent_slots = threading.BoundedSemaphore(SUBAGENT_MAX_CONCURRENT)
_qos_lock = threading.Condition()
_active = {}
_active_lock = threading.Lock()
_started = time.time()
# Монотонная метка последнего успешного хода (0.0 = не было / последний провалился).
_last_ok = [0.0]
# Байтовый бюджет admission; включается в main() (в тестах/импорте — None).
_budget = None

# ---- ОТКАЗОУСТОЙЧИВОСТЬ КОНТЕКСТА (EYE-33873, ADR-0006): общее ядро core/context_resilience.
# Флаги читаются из локального снимка GigaRC (дефолт false = прежнее поведение хаба).
CONTEXT_FLAGS = ctxres.FlagSource()
# ---- ОТКАЗОУСТОЙЧИВОСТЬ БЭКЕНДОВ (ADR-0020): Circuit Breaker + Bulkhead по backend_id.
# Все механизмы за флагами GigaRC (дефолт false = прежнее поведение); fallback на другую модель запрещён.
RESILIENCE = ResilienceManager()
CONTEXT_EPOCHS = ctxres.EpochStore()
# Droid-маршрут хаба не квалифицирован (VER-006): строгий admission включается только флагом
# DYNAMIC_PRUNER_ENABLED; после паспорта счётчика владелец переводит маршрут в enrolled.
CONTEXT_ENROLLED = False
CONTEXT_DEFAULT_MAX_OUTPUT = 65536
_CONTEXT_OWNER_SECRET = os.urandom(32)
_sha_cache = {}
_sha_cache_lock = threading.Lock()

# ---- SCOPING И КАТАЛОГИЗАЦИЯ МОДЕЛЕЙ (ADR-0017) -----------------------------------
PROVIDER_SCOPES: dict[str, tuple[str, ...]] = {
    "claude-code": ("claude-p-bridge",),
    "codex": ("openai-codex",),
    "agy": ("agy-bridge",),
    "muse": ("muse-bridge", "meta-muse"),
    "opencode": ("opencode-zen-bridge",),
}

INTERNAL_MODEL_IDS = ("deepseek-v4.1-flash", "deepseek-v4.1-flash-free")
_INTERNAL_KEY_HEADER = "X-Internal-Service-Key"
_INTERNAL_SERVICE_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "")
MAX_OUTPUT_TOKENS = int(os.environ.get("BRIDGE_MAX_OUTPUT_TOKENS", "64000"))
MULTIMODAL_MODELS = ("gpt-6.1-sol", "gemini-4-argon")

_PROVIDER_MODELS_RE = re.compile(r"^/v1/providers/([^/]+)/v1/models$")
_PROVIDER_CHAT_RE = re.compile(r"^/v1/providers/([^/]+)/v1/chat/completions$")

_REFRESH_MIN_INTERVAL = float(
    os.environ.get("BRIDGE_MODELS_REFRESH_MIN_INTERVAL_S", "10.0")
)
_REFRESH_MAX_ENTRIES = int(os.environ.get("BRIDGE_MODELS_REFRESH_MAX_ENTRIES", "1000"))
_REFRESH_LOCK = threading.Lock()  # single-flight
_REFRESH_LAST: dict[str, float] = {}
_MODELS_CACHE: dict[str, dict[str, Any]] = {}
_MODELS_CACHE_LOCK = threading.Lock()


def _refresh_client_key(handler: BaseHTTPRequestHandler) -> str:
    raw = handler.headers.get("Authorization", "") or handler.headers.get(
        "X-Api-Key", ""
    )
    token = raw.strip()
    if token[:7].lower() == "bearer ":
        token = token[7:].strip()
    if token:
        return "t:" + hashlib.sha256(token.encode("utf-8")).hexdigest()
    client_ip = getattr(handler, "client_address", ("unknown",))[0]
    return "ip:" + str(client_ip)


def _refresh_acquire(key: str, now: float | None = None) -> int | None:
    now = time.monotonic() if now is None else now
    with _REFRESH_LOCK:
        horizon = 2 * _REFRESH_MIN_INTERVAL
        for stale_key in [k for k, ts in _REFRESH_LAST.items() if now - ts > horizon]:
            del _REFRESH_LAST[stale_key]
        last = _REFRESH_LAST.get(key)
        if last is not None and now - last < _REFRESH_MIN_INTERVAL:
            return max(1, int(math.ceil(_REFRESH_MIN_INTERVAL - (now - last))))
        if key not in _REFRESH_LAST and len(_REFRESH_LAST) >= _REFRESH_MAX_ENTRIES:
            del _REFRESH_LAST[min(_REFRESH_LAST, key=_REFRESH_LAST.get)]
        _REFRESH_LAST[key] = now
    return None


def _get_published_models() -> dict[str, tuple[Any, Any]]:
    published = {}
    models_source = BACKENDS.models() if hasattr(BACKENDS, "models") else []
    for item in models_source:
        if isinstance(item, tuple) and len(item) == 2:
            a, m = item
        else:
            m = item
            a = getattr(m, "adapter", None)
        mid = getattr(m, "id", None) or (m.get("id") if isinstance(m, dict) else None)
        if mid:
            published[mid] = (a, m)
    return published


_EFFORT_SPECS_CACHE: tuple[Any, dict[str, ModelEffortSpec]] = (None, {})


def _invalidate_effort_specs_cache(_: Any = None) -> None:
    """Сбрасывает кэш спек effort: GatedCatalog меняет модели без смены sha256 файла."""
    global _EFFORT_SPECS_CACHE
    _EFFORT_SPECS_CACHE = (None, {})


_catalog_add_listener = getattr(FLEET, "add_listener", None)  # только у GatedCatalog
if _catalog_add_listener is not None:
    _catalog_add_listener(_invalidate_effort_specs_cache)


def _effort_specs() -> dict[str, ModelEffortSpec]:
    """Спеки effort каталога с кэшем."""
    global _EFFORT_SPECS_CACHE
    # FLEET.get первым: у GatedCatalog он синхронизирует флаг droid до чтения `_st` и models.
    key = (FLEET.get("sha256"), getattr(FLEET, "_st", None), id(FLEET.get("models")),
           ADVERTISED_EFFORT_ALIASES, EFFORT_ALIAS_ENABLED, EFFORT_SUFFIXES)
    if _EFFORT_SPECS_CACHE[0] != key:
        models = FLEET.get("models", {})
        found = {a: r for a in ADVERTISED_EFFORT_ALIASES if (r := _resolve_model_alias(a, models))}
        _EFFORT_SPECS_CACHE = (key, catalog_effort_specs(models, found))
    return _EFFORT_SPECS_CACHE[1]


def _advertise_efforts(card: dict[str, Any], mid: str, specs: dict[str, ModelEffortSpec]) -> None:
    if fields := resolve_model_effort_fields(mid, specs):
        card["supported_reasoning_efforts"] = list(fields.supported_efforts)
        card["default_reasoning_effort"] = fields.default_effort


def _build_models_list(
    owner_tuple: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    published = _get_published_models()
    specs = _effort_specs() if flag_enabled(FLAG_EFFORT_CATALOG) else {}
    order = []
    if MODEL_ID in published:
        order.append(MODEL_ID)
    fleet_order = FLEET.get("order", []) if isinstance(FLEET, dict) else []
    for mid in fleet_order:
        if mid != MODEL_ID and mid in published and mid not in order:
            order.append(mid)
    for mid in published:
        if mid not in order:
            order.append(mid)

    internal_key = getattr(
        sys.modules[__name__], "_INTERNAL_SERVICE_KEY", None
    ) or os.environ.get("INTERNAL_SERVICE_KEY", "")
    hide_internal = bool(internal_key) or (owner_tuple is not None)

    data = []
    listed = set()
    for mid in order:
        if hide_internal and mid in INTERNAL_MODEL_IDS:
            continue
        a, m = published[mid]
        owned_by = (
            getattr(a, "owned_by", "")
            if a is not None
            else (
                getattr(m, "owned_by", "")
                or (m.get("owned_by", "") if isinstance(m, dict) else "")
            )
        )
        if owner_tuple is not None and owned_by not in owner_tuple:
            continue
        context_window = (
            getattr(m, "context_window", 200000)
            if not isinstance(m, dict)
            else m.get("context_window", 200000)
        )
        stat = _PENALTY_TRACKER.get_model_status(mid)
        is_pen = stat["is_penalized"]
        pen_until = int(stat["penalized_until"]) if is_pen else None
        card = {
            "id": mid,
            "object": "model",
            "owned_by": owned_by,
            "created": 0,
            "context_window": context_window,
            "context_length": context_window,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "modalities": ["text", "image"] if mid in MULTIMODAL_MODELS else ["text"],
            "supports_thinking": True,
            "supported_reasoning_efforts": ["low", "medium", "high"],
            "default_reasoning_effort": "high",
            "available": not is_pen,
            "penalized_until": pen_until,
        }
        _advertise_efforts(card, mid, specs)
        data.append(card)
        listed.add(mid)

    fleet_models = FLEET.get("models", {}) if isinstance(FLEET, dict) else {}
    for alias_id in ADVERTISED_EFFORT_ALIASES:
        if alias_id in listed or (hide_internal and alias_id in INTERNAL_MODEL_IDS):
            continue
        alias = _resolve_model_alias(alias_id, fleet_models)
        base_id = alias[0] if (alias and isinstance(alias, (tuple, list))) else alias
        if (
            not base_id
            or base_id not in published
            or (hide_internal and base_id in INTERNAL_MODEL_IDS)
        ):
            continue
        a, m = published[base_id]
        owned_by = (
            getattr(a, "owned_by", "")
            if a is not None
            else (
                getattr(m, "owned_by", "")
                or (m.get("owned_by", "") if isinstance(m, dict) else "")
            )
        )
        if owner_tuple is not None and owned_by not in owner_tuple:
            continue
        context_window = (
            getattr(m, "context_window", 200000)
            if not isinstance(m, dict)
            else m.get("context_window", 200000)
        )
        target_id = base_id if base_id else alias_id
        stat = _PENALTY_TRACKER.get_model_status(target_id)
        is_pen = stat["is_penalized"]
        pen_until = int(stat["penalized_until"]) if is_pen else None
        card = {
            "id": alias_id,
            "object": "model",
            "owned_by": owned_by,
            "created": 0,
            "context_window": context_window,
            "context_length": context_window,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "modalities": ["text", "image"]
            if base_id in MULTIMODAL_MODELS
            else ["text"],
            "supports_thinking": True,
            "supported_reasoning_efforts": ["low", "medium", "high"],
            "default_reasoning_effort": "high",
            "available": not is_pen,
            "penalized_until": pen_until,
        }
        _advertise_efforts(card, alias_id, specs)
        data.append(card)
        listed.add(alias_id)

    return data


def _etag(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return '"%s"' % hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _etag_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    if header.strip() == "*":
        return True
    candidates = (tag.strip() for tag in header.split(","))
    return any(tag.removeprefix("W/") == etag for tag in candidates)


# ---- RPC-СОСТОЯНИЕ: долгоживущий `droid exec --input-format stream-jsonrpc` на чат.
# Ключ чата — prompt_cache_key запроса (никогда не путь/argv: только sha256).
# Часы и пауза подменяются в тестах (fake clock): idle-реап и ретраи 2/4 с не
# должны замедлять набор.
RPC_NAMESPACE = "droid-bridge/v1"
# Idle-гашение процесса чата (по monotonic времени последнего terminal/release).
IDLE_SECONDS = CLI_CFG.idle_seconds
REAPER_TICK_S = 1.0
# Тишина без событий ТЕКУЩЕГО хода после первого события (сбрасывают только они).
SILENCE_WATCHDOG_S = CLI_CFG.silence_watchdog_s
# Ожидание ответа на служебный запрос (initialize/load/update/list_tools/add).
RPC_CALL_TIMEOUT_S = CLI_CFG.rpc_call_timeout_s
# После interrupt ждём terminal столько, затем процесс закрывается принудительно.
INTERRUPT_GRACE_S = 3.0
# Не больше пяти restore на один SID: шестой — свежая generation (вторичный предел).
RESTORE_MAX = 5


# Бюджет очистки детей после drain; входит в общий ExitTimeOut супервизора.
def _configured_shutdown_grace_s() -> float:
    """Читает конечный бюджет >= 0; ноль отключает ожидание, fallback — 4.5 с."""
    try:
        value = float(os.environ.get("BRIDGE_SHUTDOWN_GRACE_S", "4.5"))
    except ValueError:
        return 4.5
    return value if math.isfinite(value) and value >= 0 else 4.5


SHUTDOWN_GRACE_S = _configured_shutdown_grace_s()
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
MAX_RPC_LINE_BYTES = CLI_CFG.max_rpc_line_bytes
MAX_STDERR_BYTES = CLI_CFG.max_stderr_bytes
# Бюджет очереди событий; одна строка до MAX_RPC_LINE_BYTES принимается в пустую очередь (иначе
# легитимный ответ load_session крупнее 4 МиБ был бы недоставим), поэтому память очереди
# ограничена MAX_INBOX_BYTES + одной строкой.
MAX_INBOX_BYTES = CLI_CFG.max_inbox_bytes
MAX_TURN_TEXT_BYTES = CLI_CFG.max_turn_text_bytes
# Промежуточная очередь Run.q (RW-204, F-103 Архитектурной панели): ограничена, чтобы
# медленный потребитель (_execute) не давал producer (RPC-поток Run) копить события
# без предела. Переполнение — не блокировка producer, а явный fail-close (Run._publish).
RUN_QUEUE_MAXSIZE = CLI_CFG.run_queue_maxsize
# Структурный предел строки RPC: число `{`/`[`/`,`/`:` вне строк. Строка из миллионов пустых объектов или
# чисел укладывается в MAX_RPC_LINE_BYTES, но json.loads раздул бы её в сотни МиБ объектов (RW-014, RW-010):
# отклоняется до разбора.
MAX_JSON_STRUCT_TOKENS = CLI_CFG.max_json_struct_tokens
# Условная стоимость записи/слота в бюджетах: поток пустых сообщений тоже упирается в лимит.
ENTRY_OVERHEAD_BYTES = 64
# Предел длины id сообщения в карантине событий (RW-009): длиннее — ошибка хода (id удерживается в памяти).
MAX_HELD_MID_CHARS = 1024
# Кусок вывода при сериализации ответа клиенту (JSON/SSE выдаются порциями, без второй полной копии).
DELIVERY_CHUNK_BYTES = 64 << 10
# Общий бюджет памяти готовых ответов, удерживаемых до конца выдачи клиенту (RW-011): T/L к этому
# моменту свободны, а медленные клиенты держат `out`. Исчерпан — 502 proxy_error.
MAX_DELIVERY_BYTES = CLI_CFG.max_delivery_bytes
MAX_CHATS = CLI_CFG.max_chats
# Предел блока agent-instructions (REQ-003): больше — усечение проектных секций; канон сверх предела — отказ до spawn/add.
# BRIDGE_INSTR_LIMIT -> DROID_DSH_BRIDGE_INSTR_LIMIT -> 500000, диапазон и валидация — в b_guard (ADR 0015).
# Сверх предела блок не отклоняется, а мягко усекается (хвостовые проектные секции, канон защищён).
INSTR_BLOCK_LIMIT = b_guard.resolve_block_limit()
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


_WS_URL = re.compile(r"\bwss?://\S+", re.IGNORECASE)


def _mask_secrets(text: str) -> str:
    """Длинные токеноподобные последовательности и WebSocket URL -> ***."""
    return _SECRET.sub("***", _WS_URL.sub("ws://***", text))


def _err_summary(err: Any, limit: int = 200) -> str:
    """Усечённая причина ошибки для лога: маскирование секретов, затем обрезка."""
    return _mask_secrets(str(err or ""))[:limit]


# ---- ПРОБРОС СЕССИОННОГО ОКРУЖЕНИЯ extra_body.env (ADR-0016) ------------------------------
# Всё закрыто флагом GigaRC BRIDGE_BROWSER_FORWARDING_ENABLED (дефолт false = прежнее поведение
# побайтово). Проброшенное окружение живёт только в памяти: в chat_state/record не пишется.
FORWARD_FLAG = "BRIDGE_BROWSER_FORWARDING_ENABLED"
PASSTHROUGH_AUTH_FLAG = "BRIDGE_PASSTHROUGH_UPSTREAM_KEY_AUTH_ENABLED"


def _env_limit(name: str, default: int) -> int:
    """Положительный целочисленный лимит из окружения; нечисло/<=0 -> безопасный дефолт."""
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _env_float(name: str, default: float) -> float:
    """Положительный вещественный параметр из окружения; нечисло/nan/<=0 -> безопасный дефолт."""
    try:
        val = float(os.environ.get(name, default))
        return val if math.isfinite(val) and val > 0 else default
    except (TypeError, ValueError):
        return default


def _env_int_nonneg(name: str, default: int) -> int:
    """Неотрицательный целочисленный параметр из окружения; нечисло/<0 -> безопасный дефолт."""
    try:
        val = int(os.environ.get(name, default))
        return val if val >= 0 else default
    except (TypeError, ValueError):
        return default


_LOG_EFFORT_MAX = _env_limit("BRIDGE_LOG_EFFORT_MAX_CHARS", DEFAULT_LOG_EFFORT_MAX_CHARS)
FORWARD_ENV_MAX_KEYS = _env_limit("BRIDGE_FORWARD_ENV_MAX_KEYS", 64)
FORWARD_ENV_MAX_VALUE = _env_limit("BRIDGE_FORWARD_ENV_MAX_VALUE", 32768)
_FORWARD_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
# Имена, которые запрос подменять не вправе (регистр не важен: сравнение по upper()).
DENIED_FORWARD_ENV = frozenset(
    {
        "BRIDGE_KEY",
        "DROID_DSH_BRIDGE_KEY",
        "DROID_BIN",
        "FACTORY_HOME_OVERRIDE",
        "DROID_AUTO",
        "PATH",
        "HOME",
        "SHELL",
        "USER",
        "IFS",
        "ENV",
        "BASH_ENV",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "NODE_EXTRA_CA_CERTS",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "PWD",
        "TMPDIR",
        "ZDOTDIR",
        "CDPATH",
        "PS4",
        "PROMPT_COMMAND",
    }
)
DENIED_FORWARD_PREFIXES = (
    "DYLD_",
    "LD_",
    "PYTHON",
    "NODE_",
    "BASH_",
    "DROID_",
    "FACTORY_",
    "GIT_",
    "PERL",
    "RUBY",
    "BRIDGE_CLI_",
    "BRIDGE_NONSTREAM_",
    "BRIDGE_WATCHDOG_",
)
_MASK_NAME = re.compile(r"TOKEN|KEY|SECRET|AUTH|PASS", re.IGNORECASE)


class _ForwardFlagSource(DynamicFlagSource):
    _flag_name = FORWARD_FLAG


_FORWARD_FLAG_SOURCE = _ForwardFlagSource()


class _PassthroughAuthFlagSource(_ForwardFlagSource):
    """Тот же fail-closed снимок GigaRC для допуска upstream-ключа клиента."""

    _flag_name = PASSTHROUGH_AUTH_FLAG


PASSTHROUGH_AUTH_FLAG_SOURCE = _PassthroughAuthFlagSource()


def is_browser_forwarding_enabled() -> bool:
    """Включён ли проброс extra_body.env / tools в PATH (динамически, без рестарта)."""
    return _FORWARD_FLAG_SOURCE.enabled()


def _extra_denied_names() -> frozenset:
    raw = os.environ.get("BRIDGE_BROWSER_FORWARD_DENYLIST", "")
    return frozenset(n.strip().upper() for n in raw.split(",") if n.strip())


def _forward_name_denied(name: str) -> bool:
    upper = name.upper()
    return (
        upper in DENIED_FORWARD_ENV
        or upper.startswith(DENIED_FORWARD_PREFIXES)
        or upper.endswith("_BRIDGE_KEY")
        or is_bridge_secret_name(name)
        or upper in _extra_denied_names()
    )


def sanitize_forwarded_env(env_dict: Any) -> dict[str, str]:
    """Допустимое подмножество запрошенного окружения; остальное молча отбрасывается.

    Ключ — `^[A-Za-z_][A-Za-z0-9_]{0,127}$` вне денилиста; значение — строка без NUL длиной
    <= FORWARD_ENV_MAX_VALUE (32768); `AGENT_BROWSER_CDP` — только loopback-адрес. Идемпотентна. Значения не логируются.
    """
    clean: dict[str, str] = {}
    if not isinstance(env_dict, dict):
        return clean
    for name, value in env_dict.items():
        if (
            not isinstance(name, str)
            or not isinstance(value, str)
            or _FORWARD_KEY.fullmatch(name) is None
            or "\0" in value
            or len(value) > FORWARD_ENV_MAX_VALUE
            or _forward_name_denied(name)
        ):
            continue
        if name == "AGENT_BROWSER_CDP" and not is_loopback_cdp_url(value):
            continue
        clean[name] = value
    return clean


def mask_env_for_log(env_dict: dict) -> dict:
    """Копия окружения для лога: значения секретных имён и любые ws-адреса -> ***."""
    out = {}
    for name, value in env_dict.items():
        text = str(value)
        if _MASK_NAME.search(str(name)) or _WS_URL.search(text):
            out[name] = "***"
        else:
            out[name] = _mask_secrets(text)[:80]
    return out


def _secret_values(env_dict: dict) -> list:
    """ВСЕ значения проброшенного окружения (для вычистки из stderr ребёнка): секретом может быть любое."""
    return sorted((v for v in env_dict.values() if v), key=len, reverse=True)


def _redact_values(text: str, values: list) -> str:
    for value in values:
        if value:
            text = text.replace(value, "***")
    return text


def _strip_passthrough_env(raw: bytes, req: dict) -> "tuple[bytes, dict]":
    """Вырезать `extra_body.env` из тела, уходящего внешнему upstream (токены/CDP не покидают хост).

    Тело без `extra_body.env` возвращается дословно (побайтово), иначе пересериализуется.
    """
    extra = req.get("extra_body")
    if not isinstance(extra, dict) or "env" not in extra:
        return raw, req
    clean_req = dict(req)
    clean_req["extra_body"] = {k: v for k, v in extra.items() if k != "env"}
    return json.dumps(clean_req, ensure_ascii=False).encode("utf-8"), clean_req


def _launch_env() -> dict:
    """Окружение для `droid exec`; после недавнего успешного хода пропускаем префлайт.

    DROID_SKIP_PREFLIGHT=1 — официальный переключатель droid-cli.sh (пропускает
    wait_api/wait_hy2/pick_pr_gateway). Первый запуск и запуск после ошибки идут
    с полным префлайтом, как прежде. Ключи моста (`BRIDGE_KEY`, `DROID_DSH_BRIDGE_KEY` и любые
    `*_BRIDGE_KEY`, `BRIDGE_*KEY*` и `CODEX_LB_API_KEY`; `FACTORY_API_KEY` сохраняется) в потомка не передаются (C-03, ADR 0015 B1).
    При включённом флаге пробросов `tools/` ставится в начало PATH (agent-browser, ADR-0016).
    """
    env = strip_bridge_secrets(os.environ.copy())
    last = _last_ok[0]
    if last and 0 <= time.monotonic() - last < PREFLIGHT_SKIP_WINDOW_S:
        env["DROID_SKIP_PREFLIGHT"] = "1"
    if is_browser_forwarding_enabled():
        tools_dir = str(ROOT / "tools")
        parts = [p for p in env.get("PATH", "").split(os.pathsep) if p]
        env["PATH"] = os.pathsep.join(
            [tools_dir] + [p for p in parts if p != tools_dir]
        )
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
def _check_receipt_quad(rec: Mapping[str, object]) -> None:
    """Проверка протокола, политики tools и профиля настроек receipt; расхождение — LauncherUnavailable."""
    try:
        validate_receipt_components(rec)
    except (ValueError, TypeError) as exc:
        raise LauncherUnavailable(str(exc)) from exc


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


def _tools_receipt() -> ReceiptV3 | None:
    """Квалификация tools по моделям из receipt; None — gate выключен."""
    try:
        _, rec = _load_receipt()
    except LauncherUnavailable as exc:
        raise RpcError(f"droid receipt changed during spawn: {exc}")
    parsed = ReceiptV3.parse(rec) if rec else None
    if isinstance(parsed, str):
        raise RpcError(f"droid receipt invalid: {parsed}")
    return parsed


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


def _extract_auth_token(handler: BaseHTTPRequestHandler) -> str:
    hdr = handler.headers.get("Authorization", "")
    if hdr.startswith("Bearer "):
        return hdr[7:].strip()
    return handler.headers.get("x-api-key", "") or hdr.strip()


class TokenCache:
    """Кэш актуальных ключей окружения и .dsh/.env с отзывом при смене файла."""

    _NAMES: tuple[str, str] = ("BRIDGE_KEY", "DROID_DSH_BRIDGE_KEY")

    def __init__(
        self,
        *,
        path: Path | None = None,
        ttl_s: float | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._path: Path = path if path is not None else HOME / ".dsh" / ".env"
        self._env: Mapping[str, str] = os.environ if environ is None else environ
        if ttl_s is None:
            try:
                ttl_s = float(self._env.get("BRIDGE_TOKEN_CACHE_TTL_S", "300"))
            except ValueError:
                ttl_s = 300.0
        self._ttl_s: float = ttl_s if math.isfinite(ttl_s) and ttl_s > 0 else 300.0
        self._file_keys: tuple[bytes, ...] = ()
        try:
            self._path.stat()
            self._file_seen: bool = True
        except FileNotFoundError:
            self._file_seen = False
        except OSError:
            self._file_seen = True
        self._signature: tuple[int, int, int, int, int, int] | None = None
        self._next_check: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    def _refresh_file(self, now: float) -> None:
        try:
            st = self._path.stat()
            self._file_seen = True
            signature = (
                st.st_dev,
                st.st_ino,
                st.st_mtime_ns,
                st.st_size,
                st.st_mode,
                st.st_ctime_ns,
            )
            if signature == self._signature and now < self._next_check:
                return
            self._next_check = now + self._ttl_s
            keys: dict[str, str] = {}
            for line in self._path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:].lstrip()
                name, sep, value = line.partition("=")
                if sep and name.strip() in self._NAMES:
                    value = value.strip()
                    if value.startswith(("'", '"')):
                        quote = value[0]
                        end = value.find(quote, 1)
                        if end < 0 or (
                            value[end + 1 :].strip()
                            and not value[end + 1 :].lstrip().startswith("#")
                        ):
                            continue
                        value = value[1:end]
                    else:
                        value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
                    keys[name.strip()] = value
            self._file_keys = tuple(
                value.encode("utf-8") for value in keys.values() if value
            )
            self._signature = signature
        except FileNotFoundError:
            if self._file_seen:
                self._file_keys = ()
            self._signature = None
            self._next_check = 0.0
        except (OSError, UnicodeError):
            self._file_keys = ()
            self._signature = None
            self._next_check = 0.0
            self._file_seen = True

    def is_valid(self, token: str) -> bool:
        """Проверить непустой ключ; каждый кандидат сравнивается через compare_digest."""
        if not token:
            return False
        candidate = token.encode("utf-8")
        with self._lock:
            self._refresh_file(time.monotonic())
            if self._file_seen:
                expected = self._file_keys
            else:
                env_keys = tuple(self._env.get(name, "") for name in self._NAMES)
                expected = tuple(key.encode("utf-8") for key in env_keys if key)
        valid = False
        for key in expected:
            valid |= hmac.compare_digest(candidate, key)
        return valid


TOKEN_CACHE = TokenCache()


def is_hub_key(token: str) -> bool:
    """Проверяет токен по актуальному кэшу мастер-ключей хаба."""
    return TOKEN_CACHE.is_valid(token)


def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    """Проверить токен хаба исключительно через актуальный кэш ключей."""
    return TOKEN_CACHE.is_valid(_extract_auth_token(handler))


# Исходы хода, не связанные со здоровьем бэкенда (ADR-0020 §2.А): брейкеру нейтральны.
_RESILIENCE_NEUTRAL_STATES = frozenset(
    {"queue_timeout", "spool_error", "persist_error", "delivery_budget", "client_gone"}
)
_CHAT_PATHS = ("/v1/chat/completions", "/chat/completions")
_LOOPBACK_PEERS = ("127.0.0.1", "::1", "::ffff:127.0.0.1")


_MODEL_BLOCK_STATUSES = re.compile(
    r"\b(?:TEMP\s+OFF|LIMIT\s+BLOCKED|QUOTA_EXHAUSTED|BANNED)\b", re.I
)


def _base_quota_model(model: str) -> str:
    return re.sub(r"-(?:minimal|low|medium|high|xhigh|max)$", "", model)


class QuotaCircuitBreakerCache:
    """Thread-safe quota deadlines, persisted best-effort using wall-clock time."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(
            path
            or os.environ.get(
                "BRIDGE_QUOTA_CACHE_PATH", "/tmp/cli-agent-bridge-429-cache.json"
            )
        )
        self.lock = threading.Lock()
        self.entries: dict[str, dict] = {}
        self._file_sig: tuple[int, int] | None = None
        try:
            self._load()
        except (OSError, ValueError, UnicodeDecodeError):
            pass

    def _load(self) -> None:
        try:
            st = self.path.stat()
            signature = (st.st_mtime_ns, st.st_size)
            if signature == self._file_sig:
                return
            data = json.loads(self.path.read_text(encoding="utf-8"))
            entries: dict[str, dict] = {}
            now = time.time()
            if isinstance(data, dict):
                for model, entry in data.items():
                    if isinstance(entry, dict):
                        expires = float(entry.get("expires_at", 0))
                        if math.isfinite(expires) and expires > now:
                            entries[str(model)] = {
                                "expires_at": expires,
                                "reason": str(entry.get("reason", "429_quota")),
                            }
            self.entries, self._file_sig = entries, signature
        except FileNotFoundError:
            self.entries, self._file_sig = {}, None
        except (OSError, ValueError, UnicodeDecodeError, TypeError):
            pass

    def _save(self) -> None:
        now = time.time()
        self.entries = {
            key: entry
            for key, entry in self.entries.items()
            if entry["expires_at"] > now
        }
        temporary = None
        try:
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=self.path.name + ".",
                delete=False,
            ) as stream:
                temporary = stream.name
                json.dump(self.entries, stream)
                stream.flush()
                st = os.fstat(stream.fileno())
            os.replace(temporary, self.path)
            self._file_sig = (st.st_mtime_ns, st.st_size)
        except (OSError, ValueError):
            pass
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def record_429(
        self, model_id: str, ttl_s: float = 1800.0, reason: str = "429_quota"
    ) -> None:
        if not math.isfinite(ttl_s):
            ttl_s = 1800.0
        expires = time.time() + max(0.0, ttl_s)
        with self.lock:
            try:
                self._load()
            except (OSError, ValueError, UnicodeDecodeError):
                pass
            for key in {model_id, _base_quota_model(model_id)}:
                old = self.entries.get(key, {}).get("expires_at", 0)
                self.entries[key] = {"expires_at": max(old, expires), "reason": reason}
            self._save()

    def is_blocked(self, model_id: str) -> bool:
        with self.lock:
            now = time.time()
            return any(
                self.entries.get(key, {}).get("expires_at", 0) > now
                for key in {model_id, _base_quota_model(model_id)}
            )


_QUOTA_CB_CACHE = QuotaCircuitBreakerCache()


def _parse_blocked_models(
    text: str,
    now_utc: float | None = None,
    *,
    parsed_rules: list[tuple[frozenset[str], frozenset[str], float | None]]
    | None = None,
) -> frozenset[str]:
    """Только конкретные ID в статусных колонках; prose и запреты транспортов не модели."""
    from datetime import datetime, timedelta, timezone

    now_utc = time.time() if now_utc is None else now_utc
    blocked: set[str] = set()
    headers: list[str] = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            headers = []
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if any("статус" in cell.lower() for cell in cells):
            headers = [cell.lower() for cell in cells]
            continue
        if not headers or len(cells) != len(headers):
            continue
        status_index = next(
            (i for i, cell in enumerate(headers) if "статус" in cell), None
        )
        if status_index is None or not _MODEL_BLOCK_STATUSES.search(
            cells[status_index]
        ):
            continue
        expiration = re.search(
            r"\b\(?до\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+MSK\)?",
            line,
            re.I,
        )
        expires = None
        if expiration:
            try:
                expires = (
                    datetime.strptime(expiration.group(1), "%Y-%m-%d %H:%M")
                    .replace(tzinfo=timezone(timedelta(hours=3)))
                    .timestamp()
                )
            except ValueError:
                pass
        elif re.search(r"\bдо\b.*MSK", line, re.I):
            _log(f"warning: unparseable expiration date in model note: {line.strip()}")
        if "группа" in headers:
            group = cells[headers.index("группа")].lower()
            if group not in ("модели", "models"):
                continue
            model_cell = cells[headers.index("что")]
        elif "модель" in headers[0] or "model" in headers[0]:
            model_cell = cells[0].split(" / ", 1)[0]
        else:
            continue
        models = frozenset(re.findall(r"`([a-zA-Z0-9][a-zA-Z0-9._:-]*)`", model_cell))
        if parsed_rules is not None:
            parsed_rules.append((frozenset(), models, expires))
        if expires is not None and now_utc > expires:
            continue
        blocked.update(models)
    return frozenset(blocked)


class ModelNotesFilter:
    """TTL-снимок: медленный диск не задерживает HTTP, ошибки обновления — fail-open."""

    def __init__(self, path: Path | None = None, ttl_s: float | None = None) -> None:
        self.path = (
            path
            or Path(
                os.environ.get(
                    "BRIDGE_MODEL_NOTES_PATH", "~/Мой диск/Context/model-notes.md"
                )
            ).expanduser()
        )
        self.ttl_s = ttl_s
        self.blocked: frozenset[str] = frozenset()
        self.expires_at = 0.0
        self.lock = threading.Lock()
        self.loading: threading.Event | None = None
        self.signature: tuple[int, int] | None = None
        self._parsed_rules: (
            list[tuple[frozenset[str], frozenset[str], float | None]] | None
        ) = None

    def is_blocked(self, model: str) -> bool:
        if _QUOTA_CB_CACHE.is_blocked(model):
            return True
        return self._notes_blocked(model) or self._notes_blocked(
            _base_quota_model(model)
        )

    def _notes_blocked(self, model: str) -> bool:
        now = time.monotonic()
        if now < self.expires_at:
            return model in self.blocked
        # try-lock: запрос не ждёт чужого I/O под mutex.
        if not self.lock.acquire(blocking=False):
            return model in self.blocked
        try:
            if now < self.expires_at:
                return model in self.blocked
            if self.loading is None:
                done = self.loading = threading.Event()
                try:
                    ttl = (
                        self.ttl_s
                        if self.ttl_s is not None
                        else float(
                            os.environ.get("BRIDGE_MODEL_NOTES_CACHE_TTL_S", "10")
                        )
                    )
                    if not math.isfinite(ttl) or ttl < 0:
                        ttl = 10.0
                    wait_s = float(
                        os.environ.get("BRIDGE_MODEL_NOTES_READ_BUDGET_S", "0.02")
                    )
                    wait_s = (
                        min(0.04, max(0.0, wait_s)) if math.isfinite(wait_s) else 0.02
                    )
                except ValueError:
                    ttl, wait_s = 10.0, 0.02

                def refresh() -> None:
                    try:
                        stat = self.path.stat()
                        signature = (stat.st_mtime_ns, stat.st_size)
                        now_utc = time.time()
                        if (
                            signature == self.signature
                            and self._parsed_rules is not None
                        ):
                            rules = self._parsed_rules
                            models = frozenset(
                                model
                                for _, model_ids, expiry_ts in rules
                                if expiry_ts is None or expiry_ts >= now_utc
                                for model in model_ids
                            )
                        else:
                            rules = []
                            models = _parse_blocked_models(
                                self.path.read_text(encoding="utf-8"),
                                now_utc,
                                parsed_rules=rules,
                            )
                    except (OSError, UnicodeError, ValueError):
                        signature, models, rules = None, frozenset(), None
                    with self.lock:
                        self.blocked, self.signature = models, signature
                        self._parsed_rules = rules
                        self.expires_at = time.monotonic() + ttl
                        self.loading = None
                    done.set()

                threading.Thread(
                    target=refresh, daemon=True, name="model-notes-refresh"
                ).start()
            else:
                # Другой запрос уже обновляет; возвращаем stale кэш (F-007)
                return model in self.blocked
        finally:
            self.lock.release()
        if not done.wait(wait_s):
            return model in self.blocked
        return model in self.blocked


_MODEL_NOTES_FILTER = ModelNotesFilter()
_PENALTY_TRACKER = get_penalty_tracker()

# Нейтральные к здоровью бэкенда исходы passthrough: таймаут шага модели и оборванный
# стрим одного хода не означают недоступность апстрима, поэтому брейкер не штрафуется.
_PASSTHROUGH_NEUTRAL_ERROR_TYPES = frozenset(
    {"upstream_timeout", "upstream_incomplete_stream", "client_gone"}
)


_DEFAULT_PASSTHROUGH_ERROR_CAPTURE_BYTES = 8192


def _passthrough_error_capture_bytes() -> int:
    """Лимит захвата тела ошибки для классификации исхода; env с безопасным fallback."""
    raw = os.environ.get("BRIDGE_PASSTHROUGH_ERROR_CAPTURE_BYTES", "").strip()
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_PASSTHROUGH_ERROR_CAPTURE_BYTES
    return value if value >= 0 else _DEFAULT_PASSTHROUGH_ERROR_CAPTURE_BYTES


def _passthrough_error_type(raw: bytes) -> str:
    """Тип ошибки из тела ответа: JSON error.type/code либо терминальный SSE error-кадр."""
    if not raw:
        return ""
    text = raw.decode("utf-8", "replace")
    payloads: list[Any] = []
    try:
        payloads.append(json.loads(text))
    except ValueError:
        pass
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            payloads.append(json.loads(data))
        except ValueError:
            continue
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        error = payload.get("error")
        if not isinstance(error, dict):
            continue
        # JSON-тело шва: code — HTTP-статус (число), тип ошибки в type;
        # SSE-кадр: code — строковый код ошибки.
        for value in (error.get("code"), error.get("type")):
            if isinstance(value, str) and value:
                return value
    return ""


def _passthrough_discard_reason(status: int, error_type: str) -> str:
    """Причина нейтрального исхода брейкера; '' — исход оценивается как сбой/успех бэкенда.

    record_failure остаётся только для реальной недоступности апстрима (502
    upstream_unavailable, 503 апстрима и прочие 5xx без признаков таймаута/обрыва).
    """
    if error_type in _PASSTHROUGH_NEUTRAL_ERROR_TYPES or status == 504:
        return "turn_timeout_or_stream_incomplete"
    return ""


class _HandlerSink(ResponseSink):
    """Запись ответа passthrough-шва в сокет клиента; сбой записи — ClientGone."""

    _DROP = frozenset({"server", "date"})

    def __init__(
        self,
        handler: BaseHTTPRequestHandler,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        self._handler = handler
        self._extra_headers = list(extra_headers or ())
        self._extra_names = {key.lower() for key, _ in self._extra_headers}
        if extra_headers is not None and REQUEST_ATTRIBUTION_ENABLED:
            # Upstream не должен приписывать отсутствующий у клиента subagent_id.
            self._extra_names.update(
                {REQUEST_ID_HEADER.lower(), SUBAGENT_ID_HEADER.lower()}
            )
        self.status = 0
        self._client_gone_flag = False
        # Тело ошибки захватывается ограниченно: нужно только для классификации исхода lease.
        self._error_body = bytearray()
        self._error_limit = _passthrough_error_capture_bytes()

    def error_type(self) -> str:
        """Тип ошибки ответа (JSON-тело или терминальный SSE-кадр); '' — признаков ошибки нет."""
        if not self._error_body:
            return ""
        return _passthrough_error_type(bytes(self._error_body))

    def _capture_error(self, data: bytes) -> None:
        room = self._error_limit - len(self._error_body)
        if room > 0:
            self._error_body += data[:room]

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        self.status = int(status)
        telemetry_note(self._handler, first_byte=True)
        if getattr(self._handler, "_headers_already_sent", False):
            return
        try:
            self._handler.send_response(int(status))
            for key, value in headers:
                if key.lower() not in self._DROP | self._extra_names:
                    self._handler.send_header(key, value)
            for key, value in self._extra_headers:
                self._handler.send_header(key, value)
            if not any(key.lower() == "content-length" for key, _ in headers):
                self._handler.close_connection = (
                    True  # тело без длины (SSE) — конец по закрытию
                )
            self._handler.end_headers()
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            self._client_gone_flag = True
            raise ClientGone() from exc

    def client_gone(self) -> bool:
        return self._client_gone_flag or _client_gone(self._handler.connection)

    def write(self, data: bytes) -> None:
        """Отправить чанк сразу, включая сброс буфера wfile для SSE."""
        try:
            self._handler.wfile.write(data)
            self._handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            self._client_gone_flag = True
            raise ClientGone() from exc
        if self.status >= 400 or b'"error"' in data:
            self._capture_error(data)
        telemetry_note(self._handler, len(data), chunk=True)
        telemetry_tail(self._handler, data)


def _owner_token_hash(handler: BaseHTTPRequestHandler) -> str:
    explicit = handler.headers.get("X-Turn-Owner-Token", "").strip()
    return hash_token(explicit or _extract_auth_token(handler) or AUTH_KEY)


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


def shutdown_all(grace: float | None = None) -> int:
    """Закрыть детей параллельно после drain либо немедленно без drain.

    При включённом drain ожиданием активных ходов управляет LIFECYCLE;
    общий грейс здесь относится только к последующей очистке. Принудительно
    убиваются ТОЛЬКО собственные процессные группы из реестра детей — чужие PID
    никогда. Возвращает число закрывавшихся детей.
    """
    global _shutting_down
    if grace is None:
        grace = _configured_shutdown_grace_s()
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
    """Закрыть ребёнка; немедленный interrupt нужен только без drain."""
    if proc.busy and not _is_drain_enabled():
        proc.interrupt_quietly()
    proc.close(**close_kwargs)


def _kill_all(*_: Any) -> None:
    """SIGTERM/SIGINT моста: закрытие детей с настроенным грейсом и выход."""
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
        pgid = entry.get("pgid", pid)
        sig = str(entry.get("start") or "")
        if (
            not isinstance(pid, int)
            or isinstance(pid, bool)
            or pid <= 1
            or pgid != pid
            or not sig
        ):
            continue
        leader_sig = _proc_start_sig(pid)
        # Живой PID с другой подписью уже чужой: никакого fallback на stale pgid.
        if leader_sig and leader_sig != sig:
            continue
        owned_pid = pid if leader_sig == sig else None
        members: list = []
        if owned_pid is None:
            members = entry.get("members") or []
            if not isinstance(members, list):
                continue
            for member in members:
                if not isinstance(member, dict):
                    continue
                mid = member.get("pid")
                msig = member.get("start")
                if (
                    isinstance(mid, int)
                    and not isinstance(mid, bool)
                    and mid > 1
                    and isinstance(msig, str)
                    and msig
                    and _proc_start_sig(mid) == msig
                ):
                    try:
                        if os.getpgid(mid) == pgid:
                            owned_pid = mid
                            break
                    except (ProcessLookupError, PermissionError):
                        continue
        if owned_pid is None:
            continue
        if has_live_parent(owned_pid, entry):
            continue
        try:
            if os.getpgid(owned_pid) != pgid:
                continue
            # Последняя сверка подписи непосредственно перед сигналом.
            expected = (
                sig
                if owned_pid == pid
                else next(m["start"] for m in members if m.get("pid") == owned_pid)
            )
            if _proc_start_sig(owned_pid) != expected:
                continue
            if has_live_parent(owned_pid, entry):
                continue
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            continue
        killed += 1
        _log(f"session_rpc reconcile killed_orphan pid={pid}")
    with _children_lock:
        try:
            # После SIGKILL группа может ещё завершаться. Сохраняем подписанное владение,
            # пока хотя бы собственный член жив: следующий restart повторит cleanup.
            remaining = []
            for entry in entries:
                pgid = entry.get("pgid", entry.get("pid"))
                identities = [{"pid": entry.get("pid"), "start": entry.get("start")}]
                if isinstance(entry.get("members"), list):
                    identities += entry["members"]
                for identity in identities:
                    if not isinstance(identity, dict):
                        continue
                    mid, msig = identity.get("pid"), identity.get("start")
                    if (
                        not isinstance(mid, int)
                        or isinstance(mid, bool)
                        or mid <= 1
                        or not msig
                        or _proc_start_sig(mid) != msig
                    ):
                        continue
                    try:
                        if os.getpgid(mid) == pgid:
                            remaining.append(entry)
                            break
                    except (ProcessLookupError, PermissionError):
                        continue
            _atomic_write(_children_path(), json.dumps(remaining).encode())
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


_ACTIVE_WRITER_LOCK: Any = None


def release_writer_lock() -> None:
    """Освобождает блокировку реестра для нового экземпляра во время drain."""
    global _ACTIVE_WRITER_LOCK
    writer_lock, _ACTIVE_WRITER_LOCK = _ACTIVE_WRITER_LOCK, None
    if writer_lock is not None:
        try:
            fcntl.flock(writer_lock, fcntl.LOCK_UN)
        finally:
            writer_lock.close()


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

    def __init__(
        self,
        work_dir: str,
        pool: "ProcPool",
        holds_slot: bool,
        fwd_env: dict | None = None,
    ):
        self.pool = pool
        self.holds_slot = holds_slot
        # Повторная проверка kill-switch в точке spawn: флаг выключили между приёмом запроса и запуском.
        if fwd_env and not is_browser_forwarding_enabled():
            fwd_env = None
        # Проброшенное окружение (ADR-0016): только признак и значения секретов для вычистки stderr;
        # сам словарь процесс не хранит и на диск не пишет.
        self.has_fwd_env = bool(fwd_env)
        self._redact = _secret_values(fwd_env) if fwd_env else []
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
                env=_child_env(fwd_env),
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
        if self._redact:
            text = _redact_values(text, self._redact)
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
        if permission_frame(msg):
            self.server_requests += 1
            return self._put(
                "permission", "permission request forbidden by bridge", size
            )
        if msg.get("id") is not None:
            # Запрос разрешения — нарушение безопасного профиля, ход прерывается.
            self.server_requests += 1
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
        kind, payload, *_ = event
        require(kind != "permission", RpcPermissionDenied(str(payload)))
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


def _child_env(fwd_env: dict | None = None) -> dict:
    """Окружение ребёнка: как _launch_env + чистый Factory home и образ из receipt (AD-010).

    Сбой подготовки home — исключение (spawn не выполняется), молчаливого продолжения нет.

    Ключи мостов и upstream вырезаны в _launch_env. Чистый home не даёт
    хукам/персональным skills владельца
    попасть в контекст чата; DROID_AUTO=off — вторичная защита (главная — RPC).
    """
    env = _launch_env()
    if fwd_env and is_browser_forwarding_enabled():
        # Повторная санитизация на границе spawn; системные имена ниже всё равно перезаписываются.
        env.update(sanitize_forwarded_env(fwd_env))
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
        # Проброшенное окружение процесса (ADR-0016): строго in-memory, в _write_record не попадает.
        self.env: dict[str, str] | None = None


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
            _set_chat_env(chat, None)
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
        self.env_keys: set = (
            set()
        )  # key_hash чатов с проброшенным env: kill-switch идёт по ним за O(k)
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
                    _set_chat_env(chat, None)
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
                _set_chat_env(chat, None)
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
                _enforce_forward_kill_switch()
                self.reap_once()
            except OSError as exc:
                _log(f"session_rpc reaper_error err={_err_summary(exc, 120)!r}")


REGISTRY = ChatRegistry()
POOL = ProcPool()


def _set_chat_env(chat: Chat, env: dict | None) -> None:
    """Окружение чата (только память): учёт в env_keys для kill-switch."""
    with REGISTRY.lock:
        chat.env = env or None
        if chat.env is not None:
            REGISTRY.env_keys.add(chat.key_hash)
        else:
            REGISTRY.env_keys.discard(chat.key_hash)


def _kill_proc_now(proc: RpcProcess) -> None:
    """Немедленное завершение процесса: SIGTERM без ожидания, затем SIGKILL группы."""
    proc.close(mode="kill", term_wait=0.0, kill_wait=TERM_WAIT_S)


def _reconcile_chat_env(chat: Chat, fwd_env: dict | None) -> None:
    """Под арендой чата: окружение процесса == окружение запроса, иначе процесс убивается (ADR-0016).

    Смена env, запрос без env у чата с env и запрос с env у чата без env — во всех случаях живой
    процесс завершается, `chat.proc = None`, дальше план поднимет новый процесс с нужным окружением
    (`restore` того же SID). Без env с обеих сторон — no-op (поведение побайтово прежнее).
    """
    new = fwd_env or None
    if chat.env == new:
        return
    proc, chat.proc = chat.proc, None
    if proc is not None:
        if chat.state == "READY":
            chat.state = "PERSISTED"
        _log(
            f"session_rpc chat={chat.key_hash[:8]} env_changed pid={proc.pid} "
            f"had_env={int(chat.env is not None)} has_env={int(new is not None)}"
        )
        _kill_proc_now(proc)
    _set_chat_env(chat, new)


def _enforce_forward_kill_switch() -> int:
    """Флаг выключен -> завершить все процессы с проброшенным env (без рестарта моста). -> число убитых."""
    if is_browser_forwarding_enabled():
        return 0
    with _active_lock:
        procs = [p for p in _rpc_procs.values() if p.has_fwd_env]
    with REGISTRY.lock:
        keys = list(REGISTRY.env_keys)
        chats = [REGISTRY.chats[k] for k in keys if k in REGISTRY.chats]
        REGISTRY.env_keys.clear()
    for chat in chats:
        proc = chat.proc
        if proc is not None and proc in procs:
            chat.proc = None
            if chat.state == "READY":
                chat.state = "PERSISTED"
        chat.env = None
    for proc in procs:
        _log(f"session_rpc kill_switch forward_env pid={proc.pid}")
        _close_async(proc, "kill")
    return len(procs)


def _active_turn_count() -> int:
    return max(BACKENDS.active_total(), TURN_MANAGER.active_count())


def _configured_drain_timeout_s() -> float:
    """Читает конечный бюджет drain > 0, иначе возвращает штатный таймаут."""
    try:
        value = float(os.environ.get("BRIDGE_DRAIN_TIMEOUT_S", "").strip())
    except ValueError:
        return DEFAULT_DRAIN_SECONDS
    return value if math.isfinite(value) and value > 0 else DEFAULT_DRAIN_SECONDS


def _force_kill_all_on_drain() -> None:
    TURN_MANAGER.kill_all_active()
    shutdown_all()
    BACKENDS.shutdown(exclude=("droid",))
    try:
        _sweep_workspace(cutoff_s=60.0)
    except Exception:  # noqa: BLE001
        pass


TURN_MANAGER = TurnSessionManager(
    _state_dir,
    max_concurrent=max(MAX_CONCURRENT * 8, 256),
    finalize_fn=finalize_turn,
    log_fn=_log,
    persist_children_file=False,
    first_token_timeout_s=FIRST_TOKEN_TIMEOUT_S,
)
LIFECYCLE = HubLifecycleManager(
    state_dir=_state_dir,
    turn_manager=TURN_MANAGER,
    active_turns_fn=_active_turn_count,
    force_kill_fn=_force_kill_all_on_drain,
    drain_timeout_s=_configured_drain_timeout_s(),
    on_drain_start_fn=release_writer_lock,
    log_fn=_log,
)


def _reset_rpc_state() -> None:
    """Закрыть всех детей и сбросить реестр/пул (тесты; старт моста)."""
    global REGISTRY, POOL, _shutting_down
    with _active_lock:
        procs = list(_rpc_procs.values())
    for proc in procs:
        proc.close(mode="term", term_wait=1.0, kill_wait=1.0)
    REGISTRY = ChatRegistry()  # pyright: ignore[reportConstantRedefinition]
    POOL = ProcPool()  # pyright: ignore[reportConstantRedefinition]
    TURN_MANAGER.reset_state()
    LIFECYCLE.reset_state()
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

    def opt_num(key: str) -> int | None:
        value = tu.get(key)
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else None
        )

    return {
        "input_tokens": num("inputTokens"),
        "output_tokens": num("outputTokens"),
        "cache_creation_tokens": opt_num("cacheCreationTokens"),
        "cache_read_tokens": opt_num("cacheReadTokens"),
        "thinking_tokens": num("thinkingTokens"),
    }


def _wire_usage(
    prompt_tokens: Any, completion_tokens: Any, cache_read_tokens: Any
) -> dict:
    """Wire-`usage` OpenAI-контракта: `prompt_tokens_details` — только при известном кэше."""
    wire = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    details, inconsistent = normalize_prompt_cache_details(
        prompt_tokens, cache_read_tokens
    )
    if details is not None:
        wire["prompt_tokens_details"] = details
    if inconsistent:
        _log(
            "usage_cache_inconsistent prompt_tokens=%r cache_read_tokens=%r"
            % (prompt_tokens, cache_read_tokens)
        )
    return wire


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
    """История канонов не записана на диск: без неё после рестарта старый KB-блок потерял бы предел блока KB (RW-011)."""


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
    """Применимый предел блока: KB-форма (только канон) — INSTR_BLOCK_LIMIT, прочие — бюджет минус запас.

    Бюджет non-KB — не меньше INSTR_BLOCK_LIMIT: устаревший maxBytes клиентского профиля DSH
    (cordis.patch.yml, 118k) предел моста не занижает; больший maxBytes клиента допустим.
    """
    if block["canon_only"]:
        return INSTR_BLOCK_LIMIT
    return max(INSTR_BLOCK_LIMIT, max_bytes or 0) - INSTR_NONKB_MARGIN


_UG_CANON_SUFFIX = "/.dsh/AGENTS.md"
_REMINDER_CLOSE = "</system-reminder>"


def _truncation_marker(limit: int) -> str:
    return (
        f"\n\n[... agent-instructions truncated by bridge to limit {limit} bytes ...]\n"
    )


def _truncate_instr_text(text: str, limit: int) -> str:
    """Мягкое усечение блока agent-instructions до `limit` байт UTF-8 (LIFO по секциям, канон защищён).

    Секции-копии канона и глобальный `~/.dsh/AGENTS.md` не усекаются. Прочие секции режутся с конца:
    хвост тела обрезается по границе символа, секция, не вмещающаяся даже с заголовком, удаляется
    целиком. Вставляется маркер усечения; закрывающий `</system-reminder>` сохраняется. Если
    защищённая часть сама превышает предел, возвращается максимально усечённый текст (вызывающий
    повторно проверит предел и откажет).
    """
    heads = list(_SECTION_RE.finditer(text))
    total = len(text.encode("utf-8"))
    if not heads or total <= limit:
        return text
    tail = ""
    last_end = len(text)
    close = text.find(_REMINDER_CLOSE, heads[-1].end())
    if close != -1:
        tail, last_end = text[close:], close
    canon = {_canon_digest(), *_canon_seen} - {""}
    spans = []
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else last_end
        body = text[head.end() : end]
        path = head.group(1).strip()
        protected = (
            path == b_guard.UG_DISPLAY
            or path.endswith(_UG_CANON_SUFFIX)
            or hashlib.sha256(body.strip().encode("utf-8")).hexdigest() in canon
        )
        spans.append([head.start(), head.end(), end, protected])
    marker = _truncation_marker(limit)
    need = total - limit + len(marker.encode("utf-8"))
    # Результат по сегментам: (текст секции целиком | её усечённая версия), порядок документа сохраняется.
    pieces: dict[int, str] = {}
    marker_at = None
    for index in range(len(spans) - 1, -1, -1):
        if need <= 0:
            break
        start, body_start, end, protected = spans[index]
        if protected:
            continue
        header_bytes = len(text[start:body_start].encode("utf-8"))
        body_b = text[body_start:end].encode("utf-8")
        if need >= len(
            body_b
        ):  # от тела ничего не остаётся: заголовок без тела не нужен
            pieces[index] = ""
            need -= len(body_b) + header_bytes
        else:
            keep = max(0, len(body_b) - need)
            kept = body_b[:keep].decode("utf-8", "ignore")
            pieces[index] = text[start:body_start] + kept
            need = 0  # срезано не меньше нужного (граница символа округляет вверх)
        marker_at = index
    if marker_at is None:
        return text
    out = [text[: spans[0][0]]]
    for index, (start, _body_start, end, _protected) in enumerate(spans):
        if index in pieces:
            out.append(pieces[index])
            if index == marker_at:
                out.append(marker)
        else:
            out.append(text[start:end])
    out.append(tail)
    return "".join(out)


def _soft_truncate_instructions(
    messages: list, kb_cwd: bool, max_bytes: int | None
) -> int:
    """Усекает блоки agent-instructions сверх применимого предела прямо в `messages`; число усечённых блоков."""
    changed = 0
    for msg in messages:
        found = _instr_blocks([msg], kb_cwd)
        if not found:
            continue
        limit = _instr_limit(found[0], max_bytes)
        if found[0]["bytes"] <= limit:
            continue
        content = msg.get("content")
        text = _flatten_content(content)
        new_text = _truncate_instr_text(text, limit)
        if new_text == text:
            continue
        if isinstance(content, list):
            # Нетекстовые части (изображения) сохраняются, текстовые заменяются одной усечённой.
            rest = [
                part
                for part in content
                if not (
                    isinstance(part, str) or (isinstance(part, dict) and "text" in part)
                )
            ]
            msg["content"] = [{"type": "text", "text": new_text}, *rest]
        else:
            msg["content"] = new_text
        changed += 1
    return changed


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
                maxbytes,
                b_guard.DEFAULT_CWDS,
                GUARD_CANON,
                limit=INSTR_BLOCK_LIMIT,
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
    if adapter.capabilities.sessions != "resident":
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

    def __init__(
        self,
        plan: dict,
        proc: RpcProcess | None,
        holds_slot: bool,
        sse_writer: "StreamSink | None" = None,
    ):
        self.plan = plan
        self.proc = proc
        self.slot_held = holds_slot
        self.path = plan["path"]
        # RW-208 (AD-002/AD-003): лимит ёмкости очереди — только у живого SSE-хода
        # (sse_writer задан): его producer публикует дельты по мере готовности и может
        # обогнать consumer'а, отбрасывание здесь — осознанный fail-close. Non-stream копит
        # вывод до terminal, очередь остаётся неограниченной (как до RW-204): terminal-пачка
        # не теряется из-за размера.
        from core.backpressure import CoalescingQueue as _CoalescingQueue

        self.q: queue.Queue = (
            _CoalescingQueue(maxsize=RUN_QUEUE_MAXSIZE)
            if sse_writer is not None
            else queue.Queue()
        )
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
        # Живой SSE-ход (AD-002/AD-003): sse_writer сам не вызывается отсюда (это дело _execute),
        # сигнал используется только как флаг "эмитить text_delta/reasoning_delta в self.q по мере
        # подтверждения дельт" вместо прежней пачки одним куском на terminal.
        self.sse_writer = sse_writer
        self._live_mids: set = (
            set()
        )  # mid, для которых клиенту уже ушёл хоть один байт живьём
        self.live_invalidated = False  # AD-001: уже показанный mid потом retracted
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    # -- воркер ----------------------------------------------------------------
    def _work(self) -> None:
        try:
            self._run_turn()
        except _Cancelled:
            return
        except ModelMismatch as exc:
            self._publish(("stream_error", str(exc)[:500]))
        except RpcEof as exc:
            self._publish(("done", (exc.rc or 1, "")))
        except (RpcError, ToolsGateError) as exc:
            self._publish(("pump_error", str(exc)[:500]))
        except OSError as exc:
            self._publish(("pump_error", repr(exc)))
        except Exception as exc:  # noqa: BLE001 - воркер не должен умирать молча: ход иначе висел бы до таймаута
            _log(f"session_rpc worker_error err={_err_summary(repr(exc), 160)!r}")
            self._publish(("pump_error", repr(exc)[:500]))
        finally:
            if self.slot_held:
                self.slot_held = False
                POOL.release()
            if self.proc is not None:
                self.proc.busy = False

    def _publish(self, item: tuple) -> bool:
        """Публикация в self.q без блокировки producer.

        RW-204/RW-208: лимит RUN_QUEUE_MAXSIZE, неблокирующее отбрасывание при queue.Full
        и инвалидация live_invalidated действуют только у живого SSE-хода (sse_writer задан).
        Non-stream очередь неограниченна: событие не отбрасывается, live_invalidated из-за
        размера очереди не выставляется.
        """
        if self.sse_writer is None:
            self.q.put(
                item
            )  # неограниченная очередь: put не блокирует и не теряет события
            return True
        try:
            self.q.put_nowait(item)
            return True
        except queue.Full:
            from core.backpressure import (
                publish_preserving,
                stream_content_recovery_enabled,
            )

            _dynamic_config = globals().get("dynamic_config") or globals().get(
                "DYNAMIC_CONFIG"
            )
            if stream_content_recovery_enabled(
                _dynamic_config
            ) and publish_preserving(self.q, item, _dynamic_config):
                return True
            self.live_invalidated = True
            self._last_error = self._last_error or "Run.q overflow"
            _log(
                f"run_queue_overflow turn={self.active_turn or '-'} maxsize={self.q.maxsize}"
            )
            return False

    def _spawn(self) -> RpcProcess:
        holds = self.slot_held
        self.slot_held = False  # слот передан конструктору (при сбое он сам его вернёт)
        proc = RpcProcess(self.plan["work_dir"], POOL, holds, self.plan.get("fwd_env"))
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

    _check_flags = staticmethod(validate_boolean_flags)

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
        self._disable_native_tools(proc, plan["settings"][0])

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

    def _check_tools_policy(self, listed: list, model: str | None = None) -> None:
        """Точный каталог текущей модели обязан быть квалифицирован в receipt."""
        if not RECEIPT_REQUIRED:
            return
        try:
            _, rec = _load_receipt()
        except LauncherUnavailable as exc:
            raise RpcError(f"droid receipt changed during spawn: {exc}")
        validate_model_catalog(rec.get("qualified_models"), model or self.plan["settings"][0], listed, RpcError)

    def _disable_native_tools(self, proc: RpcProcess, model: str) -> None:
        """Нативные tools модели отключаются по актуальному list_tools; сбой — fail-closed."""
        result, _ = proc.call("droid.list_tools", {}, self.cancel)
        ids = catalog_tool_ids(result.get("tools"))
        keep = self.plan.get("keep_tools") or ()
        plan = plan_tools_disable(ids, _tools_receipt(), model, keep)
        self._check_tools_policy(list(ids), model)
        if plan.disabled_ids:
            _, stash = proc.call("droid.update_session_settings", {"disabledToolIds": list(plan.disabled_ids)}, self.cancel)
            updated = self._wait_settings_updated(proc, stash)
            verify_tools_disabled(plan, updated)
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
        admit_model(_tools_receipt(), model)
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
        if model != current[0]:
            self._disable_native_tools(proc, model)

    def _load(self, proc: RpcProcess) -> bool:
        """load_session того же SID + проверка целостности; False -> свежая generation."""
        plan = self.plan
        try:
            result, _ = proc.call(
                "droid.load_session",
                {"sessionId": plan["sid"], "disableBuiltinSkills": True},
                self.cancel,
            )
        except (RpcEof, RpcPermissionDenied):
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
        self._disable_native_tools(proc, str(plan["current_settings"][0] or plan["settings"][0]))
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
                "live_text": 0,  # сколько байт slot["text"] уже отдано live-ходу (sse_writer)
                "live_thinking": 0,
            }
            self._order.append(mid)
        return self._msgs[mid]

    def _live_diff(self, slot: dict, mid: str, field: str, kind: str) -> None:
        """Живой ход (AD-002/RW-009): протолкнуть в self.q только НОВЫЙ хвост slot[field].

        Вызывается после любого обновления slot["text"]/slot["thinking"] (дельта, complete с полным
        текстом, backfill из create_message) — одинаково покрывает все три источника, отдавая клиенту
        только то, что ещё не ушло. Применяется только когда sse_writer задан (живой SSE-ход);
        для обычного (не-live) хода ничего не публикуется здесь — вывод копится до terminal, как раньше.
        """
        if self.sse_writer is None:
            return
        live_key = "live_" + field
        sent = slot.get(live_key, 0)
        text = slot[field]
        if len(text) <= sent:
            return
        diff = text[sent:]
        slot[live_key] = len(text)
        self._live_mids.add(mid)
        self._publish((kind, (mid, diff)))

    def _check_live_prefix(self, slot: dict, field: str, new_text: str) -> bool:
        """RW-205: complete/backfill обязан продолжать уже отправленный live-префикс поля.

        Сравнение идёт с текстом, который РЕАЛЬНО ушёл в self.q (slot[field][:sent] до
        перезаписи), а не просто с предыдущим slot[field]: несовпадающий или укороченный
        complete после публикации префикса -> live_invalidated, без молчаливого среза и
        без нового хвоста (вызывающая сторона не должна звать _set_slot_text/_live_diff).
        """
        if self.sse_writer is None:
            return True
        sent = slot.get("live_" + field, 0)
        if sent == 0:
            return True
        if not new_text.startswith(slot[field][:sent]):
            self.live_invalidated = True
            self._last_error = self._last_error or "non-prefix complete detected"
            return False
        return True

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
        require(
            not permission_event(ntype),
            RpcPermissionDenied("permission request forbidden by bridge"),
        )
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
                self._live_diff(slot, counted_id, "text", "text_delta")
            if not slot["thinking"]:
                self._set_slot_text(slot, "thinking", "kb", _message_thinking(message))
                self._live_diff(slot, counted_id, "thinking", "reasoning_delta")
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
            self._live_diff(slot, mid, "text", "text_delta")
        elif ntype == "assistant_text_complete" and mid:
            slot = self._slot_for(mid)
            if isinstance(note.get("text"), str) and self._check_live_prefix(
                slot, "text", note["text"]
            ):
                self._set_slot_text(slot, "text", "tb", note["text"])
                self._live_diff(slot, mid, "text", "text_delta")
        elif ntype == "thinking_text_delta" and mid:
            delta = str(note.get("textDelta") or "")
            slot = self._slot_for(mid)
            size = len(delta.encode("utf-8"))
            slot["thinking"] += delta
            slot["kb"] += size
            slot["kc"] += size
            self._charge(size, slot)
            self._live_diff(slot, mid, "thinking", "reasoning_delta")
        elif ntype == "thinking_text_complete" and mid:
            slot = self._slot_for(mid)
            if isinstance(note.get("text"), str) and self._check_live_prefix(
                slot, "thinking", note["text"]
            ):
                self._set_slot_text(slot, "thinking", "kb", note["text"])
                self._live_diff(slot, mid, "thinking", "reasoning_delta")
        elif ntype == "assistant_message_retracted" and mid:
            if mid in self._live_mids:
                # Клиенту уже ушёл live-байт этого сообщения, а droid его отозвал: честный live-ход
                # не может сделать вид, что этого не было (AD-001) — весь ход фейлится явным сигналом.
                self.live_invalidated = True
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
                self._publish(
                    (
                        "stream_error",
                        self._last_error or f"turn ended: {reason or 'unknown'}",
                    )
                )
            return True
        if self.live_invalidated:
            # AD-001: клиенту уже ушёл байт живого сообщения, которое droid потом отозвал, а ход
            # всё же дошёл до успешного terminal — честный live-ход не может притвориться, что
            # retract не было: явный fail-close вместо обычных result/usage/stop.
            self._publish(
                (
                    "live_invalidated",
                    self._last_error
                    or "a streamed message was retracted before the turn completed",
                )
            )
            return True
        final_text = ""
        for mid in self._order:
            slot = self._msgs.get(mid) or {}
            if self.sse_writer is None:
                # Живой ход уже отдал text/reasoning по мере дельт (_live_diff); здесь — только
                # обычная (не-live) гранулярность: целиком message-событием на terminal, как прежде.
                if slot.get("thinking"):
                    self._publish(("reasoning", slot["thinking"]))
                if slot.get("text"):
                    self._publish(("text", slot["text"]))
            if slot.get("text"):
                final_text = slot["text"]
        self.ok = True
        self._publish(
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
        self._publish(("done", (0, final_text)))
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
        "settings": (build_cli_model_selection(ctx), ctx["effort"], ctx["autonomy"]),
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
                _set_chat_env(chat, None)
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
    # Повторная попытка (retry 2..3) поднимает процесс с plan["fwd_env"]: окружение чата обязано
    # совпасть с окружением реального процесса, иначе следующий запрос без env переиспользует его (F-001).
    spawned_env = getattr(proc, "has_fwd_env", None)
    _set_chat_env(
        chat, plan.get("fwd_env") if spawned_env is None or spawned_env else None
    )
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


def _client_gone(sock: socket.socket | None) -> bool:
    if sock is None or not hasattr(sock, "fileno"):
        return False
    try:
        ready, _, _ = select.select([sock], [], [], 0)
        return bool(ready) and sock.recv(1, socket.MSG_PEEK) == b""
    except (OSError, ValueError):
        return True


_DEFAULT_CLIENT_GONE = _client_gone


def _context_max_output(model_id: str) -> int:
    """Допущенный максимум выходных токенов модели из сырого fleet.json (catalog его не хранит)."""
    try:
        raw = json.loads(FLEET_PATH.read_text(encoding="utf-8"))
        for item in raw.get("models", []):
            if item.get("id") == model_id and isinstance(item.get("max_tokens"), int):
                return int(item["max_tokens"])
    except (OSError, ValueError, AttributeError):
        pass
    return CONTEXT_DEFAULT_MAX_OUTPUT


def _context_entry(model_id: str, model: dict) -> ctxres.RouteEntry:
    """Запись каталога маршрутов ядра для модели хаба: окно из каталога, паспорт BYTE-V1."""
    window = int(model.get("context_window") or 0)
    target = (
        ctxres.TargetBudget(window, min(_context_max_output(model_id), window))
        if window > 0
        else None
    )
    return ctxres.RouteEntry(
        backend=str(model.get("backend") or ""),
        ingress="droid-hub",
        route="/v1/chat/completions",
        model=model_id,
        target=target,
        protocol="openai",
        enrolled=CONTEXT_ENROLLED,
    )


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


class _LiveBudgetExceeded(Exception):
    """RW-011 в живом ходе: очередной кусок live-доставки не влез в бюджет памяти."""


def release_turn_slot(handler: Any, t_held: bool, t_released: list[bool]) -> None:
    """Освобождает слоты хода под _qos_lock с оповещением ожидающих запросов."""
    if t_held and not t_released[0]:
        t_released[0] = True
        with _qos_lock:
            _slots.release()
            if getattr(handler, "_subagent_slot_held", False):
                handler._subagent_slot_held = False
                _subagent_slots.release()
            _qos_lock.notify_all()


class Handler(TelemetryHooksMixin, BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 300
    _delivery_reserved = 0  # байты, взятые в _DELIVERY_BUDGET текущим запросом (RW-011)
    _client_write_dead = False  # RW-203: живая запись отвергнута — терминал не шлём
    _active_managed_turn: ManagedTurn | None = None
    _detach_on_disconnect = False
    _context_pruned: str | None = None  # X-DSH-Context-Pruned запроса (CD-003)
    _trace: RequestTrace | None = None
    _response_status = 0

    def end_headers(self) -> None:
        if LIFECYCLE.is_draining():
            self.close_connection = True
            self.send_header("Connection", "close")
        super().end_headers()

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        finally:
            tracking = getattr(self.server, "set_connection_active", None)
            if tracking is not None and not tracking(self.connection, False):
                self.close_connection = True
            # Drain мог начаться после отправки заголовков активного ответа.
            if LIFECYCLE.is_draining():
                self.close_connection = True

    def parse_request(self) -> bool:
        parsed = super().parse_request()
        tracking = getattr(self.server, "set_connection_active", None)
        if parsed and tracking is not None:
            return tracking(self.connection, True)
        return parsed

    def _trace_log_fields(self) -> str:
        """Безопасные поля корреляции для журнала маршрута."""
        trace = self._trace if REQUEST_ATTRIBUTION_ENABLED else None
        return f"request_id={trace.request_id if trace else '-'} subagent_id={trace.subagent_id if trace and trace.subagent_id else '-'}"

    def _is_subagent_request(self) -> bool:
        if hasattr(self, "headers") and self.headers:
            raw = self.headers.get(SUBAGENT_ID_HEADER)
            if raw and raw.strip():
                return True
        trace = getattr(self, "_trace", None)
        if trace is not None and getattr(trace, "subagent_id", None):
            return True
        return False

    def _subagent_id(self) -> str | None:
        if hasattr(self, "headers") and self.headers:
            raw = self.headers.get(SUBAGENT_ID_HEADER)
            if raw and raw.strip():
                return raw.strip()
        trace = getattr(self, "_trace", None)
        if trace is not None and getattr(trace, "subagent_id", None):
            return trace.subagent_id
        return None

    def _effective_safety_cap_s(self) -> float:
        raw_cap = None
        if hasattr(self, "headers") and self.headers:
            raw_cap = self.headers.get("X-Watchdog-Cap-Seconds")
        if raw_cap:
            try:
                val = float(raw_cap.strip())
                if val > 0 and math.isfinite(val):
                    return min(val, TIMEOUT_S)
            except ValueError:
                pass
        if self._is_subagent_request():
            return SUBAGENT_WATCHDOG_CAP_S
        return TIMEOUT_S

    def _effective_idle_timeout_s(self) -> float:
        raw_to = None
        if hasattr(self, "headers") and self.headers:
            raw_to = self.headers.get("X-Timeout-Seconds") or self.headers.get(
                "X-Subagent-Timeout"
            )
        if raw_to:
            try:
                val = float(raw_to.strip())
                if val > 0 and math.isfinite(val):
                    return max(val, 1.0)
            except ValueError:
                pass
        return IDLE_TIMEOUT_S

    def _effective_turn_timeout_s(self) -> float:
        return self._effective_idle_timeout_s()

    def log_message(self, fmt: str, *args: Any) -> None:
        _log("http " + (fmt % args))

    def handle_error(self, request: Any, client_address: Any) -> None:
        _log(f"http accept error from {client_address}")

    def _client_tag(self) -> str:
        return f"{self.client_address[0]}:{self.client_address[1]}"

    def _send(self, code: int, payload: dict, extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._response_status = int(code)
        self._telemetry_error_response(int(code), payload, body)
        try:
            self.send_response(int(code))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            for hdr_k, hdr_v in (extra_headers or {}).items():
                self.send_header(str(hdr_k), str(hdr_v))
            supplied = {key.lower() for key in (extra_headers or {})}
            for key, value in _trace_headers(self._trace):
                if key.lower() not in supplied:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            if not getattr(self, "_detach_on_disconnect", False):
                raise

    def _emit(self, data: str) -> bool:
        try:
            self.wfile.write(data.encode("utf-8"))
            self.wfile.flush()
            self._telemetry_note(data)
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def _reply_error(
        self,
        status: int,
        message: str,
        err_type: str = "invalid_request_error",
        code: str | int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.close_connection = True
        error: dict[str, Any] = {"message": message, "type": err_type}
        if code is not None:
            error["code"] = code
        self._send(status, {"error": error}, extra_headers=headers)

    def _handle_models_get(self) -> bool:
        """GET /v1/models[?provider=] и /v1/providers/{id}/v1/models."""
        url = urlparse(self.path)
        match = _PROVIDER_MODELS_RE.match(url.path)
        if match:
            provider_id = match.group(1)
        elif url.path in ("/v1/models", "/models"):
            query = parse_qs(url.query, keep_blank_values=True)
            provider_id = (query.get("provider") or [None])[0]
        else:
            return False

        # Auth-First: 401 до 404
        if not _auth_ok(self):
            self._reply_error(
                401,
                "Unauthorized",
                "authentication_error",
                headers={"WWW-Authenticate": "Bearer"},
            )
            return True

        owner_tuple = None
        if provider_id is not None:
            if provider_id not in PROVIDER_SCOPES:
                self._reply_error(404, "Unknown provider", "invalid_request_error")
                return True
            owner = PROVIDER_SCOPES[provider_id]
            owner_tuple = (owner,) if isinstance(owner, str) else owner

        payload = {"object": "list", "data": _build_models_list(owner_tuple)}
        etag = _etag(payload)
        if _etag_matches(self.headers.get("If-None-Match"), etag):
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return True
        self._send(
            200, payload, extra_headers={"ETag": etag, "Cache-Control": "no-cache"}
        )
        return True

    def _handle_quarantine_post(self):
        import math

        # Ограничиваем административный JSON-запрос до чтения тела.
        max_body_bytes = 64 * 1024

        if self.headers.get("Transfer-Encoding") is not None:
            self.close_connection = True
            self._reject(400, "invalid_request", "Transfer-Encoding is not supported")
            return

        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1:
            self.close_connection = True
            self._reject(400, "invalid_request", "A single Content-Length is required")
            return

        raw_length = lengths[0].strip()
        if not raw_length.isascii() or not raw_length.isdecimal():
            self.close_connection = True
            self._reject(400, "invalid_request", "Invalid Content-Length")
            return

        try:
            length = int(raw_length)
        except ValueError:
            self.close_connection = True
            self._reject(400, "invalid_request", "Invalid Content-Length")
            return

        if length > max_body_bytes:
            self.close_connection = True
            self._reject(413, "invalid_request", "Request body is too large")
            return

        raw_body = self.rfile.read(length)
        if len(raw_body) != length:
            self.close_connection = True
            self._reject(400, "invalid_request", "Incomplete request body")
            return

        try:
            body = json.loads(raw_body)
        except (ValueError, UnicodeError, RecursionError):
            self._reject(400, "invalid_request", "Invalid JSON body")
            return

        if not isinstance(body, dict):
            self._reject(400, "invalid_request", "JSON body must be an object")
            return

        action = body.get("action")

        if action == "set_enabled":
            enabled = body.get("enabled", True)
            if not isinstance(enabled, bool):
                self._reject(400, "invalid_request", "enabled must be a boolean")
                return

            res = _PENALTY_TRACKER.set_enabled(enabled)
            self._send(
                200,
                {
                    "ok": True,
                    "action": "set_enabled",
                    "enabled": res,
                    "max_start_fails": _PENALTY_TRACKER.max_start_fails,
                },
            )
            return

        if action in ("unban", "ban"):
            model = body.get("model")
            if (
                not isinstance(model, str)
                or not model.strip()
                or model.strip().lower() == "_meta"
            ):
                self._reject(
                    400,
                    "invalid_request",
                    "model must be a nonempty string other than '_meta'",
                )
                return

            if action == "unban":
                _PENALTY_TRACKER.unpenalize_model(model)
                self._send(200, {"ok": True, "action": "unban", "model": model})
                return

            raw_duration = body.get("duration_s", 300.0)
            try:
                if isinstance(raw_duration, bool):
                    raise ValueError("boolean duration")
                duration_s = float(raw_duration)
                if not math.isfinite(duration_s) or duration_s < 0:
                    raise ValueError("invalid duration")
            except (TypeError, ValueError, OverflowError):
                self._reject(
                    400,
                    "invalid_request",
                    "duration_s must be finite and nonnegative",
                )
                return

            try:
                st = _PENALTY_TRACKER.manually_penalize(model, duration_s)
            except ValueError as exc:
                self._reject(400, "invalid_request", str(exc))
                return

            self._send(
                200,
                {
                    "ok": True,
                    "action": "ban",
                    "model": model,
                    "status": st,
                },
            )
            return

        if action == "clear_all":
            _PENALTY_TRACKER.reset_all()
            self._send(200, {"ok": True, "action": "clear_all"})
            return

        self._send(
            400,
            {
                "error": {
                    "message": f"unknown action: {action}",
                    "type": "invalid_request",
                }
            },
        )

    def _handle_models_refresh(self) -> None:
        """POST /v1/models/refresh: Auth-First, rate-limit, single-flight, stale-while-revalidate."""
        if not _auth_ok(self):
            self._reply_error(
                401,
                "Unauthorized",
                "authentication_error",
                headers={"WWW-Authenticate": "Bearer"},
            )
            return

        key = _refresh_client_key(self)
        retry_after = _refresh_acquire(key)
        if retry_after is not None:
            self._reply_error(
                429,
                "Refresh rate limit exceeded",
                "rate_limit_error",
                headers={"Retry-After": str(retry_after)},
            )
            return

        url = urlparse(self.path)
        match = re.match(r"^/v1/providers/([^/]+)/v1/models/refresh$", url.path)
        provider_id = match.group(1) if match else None
        if provider_id is None:
            query = parse_qs(url.query, keep_blank_values=True)
            provider_id = (query.get("provider") or [None])[0]

        owner_tuple = None
        if provider_id is not None:
            if provider_id not in PROVIDER_SCOPES:
                self._reply_error(404, "Unknown provider", "invalid_request_error")
                return
            owner = PROVIDER_SCOPES[provider_id]
            owner_tuple = (owner,) if isinstance(owner, str) else owner

        cache_key = provider_id or "*"
        failed_upstreams: list[str] = []
        status = "complete"

        refresh_fn = getattr(sys.modules[__name__], "_refresh_fleet", None)
        try:
            if _REFRESH_LOCK.acquire(blocking=False):
                try:
                    if callable(refresh_fn):
                        failed_upstreams = list(refresh_fn() or [])
                    data = _build_models_list(owner_tuple)
                    with _MODELS_CACHE_LOCK:
                        _MODELS_CACHE[cache_key] = {"data": data, "ts": time.time()}
                finally:
                    _REFRESH_LOCK.release()
            else:
                with _REFRESH_LOCK:
                    pass
                with _MODELS_CACHE_LOCK:
                    cached = _MODELS_CACHE.get(cache_key)
                if cached is not None:
                    data = cached["data"]
                else:
                    data = _build_models_list(owner_tuple)
        except Exception:
            with _MODELS_CACHE_LOCK:
                cached = _MODELS_CACHE.get(cache_key)
            if cached is None:
                self._reply_error(
                    502, "Refresh failed and no cached payload", "refresh_failed"
                )
                return
            status = "stale"
            failed_upstreams = ["*"]
            data = cached["data"]

        if failed_upstreams and status != "stale":
            status = "partial"

        payload = {
            "object": "list",
            "status": status,
            "failed_upstreams": failed_upstreams,
            "data": data,
        }
        self._send(200, payload, extra_headers={"ETag": _etag(payload)})

    def _log_reject(
        self, reason: str, model: str = "unknown", model_len: int = 0
    ) -> None:
        """Строка отказа в журнал (строгий формат RW-013)."""
        _log(
            f"reject reason={reason} model={model or 'unknown'} "
            f"model_len={int(model_len)} client={self._client_tag()}"
        )

    def _reject(self, code: int, reason: str, message: str, model: str = "unknown", model_len: int = 0, extra_headers: dict[str, str] | None = None) -> None:
        """Отказ (до SSE): строка `reject …` в журнал и общий формат ошибки."""
        self._log_reject(reason, model, model_len)
        self._telemetry_meta(model=known_model(model))
        self.close_connection = True
        self._send(code, {"error": {"message": message, "type": reason, "code": {"model_not_found": reason}.get(reason, int(code))}}, extra_headers=extra_headers)

    def _acquire_slot(self, keepalive):
        """Ждём слот семафора с учётом QoS (резерв слотов для UI и квота сабагентов)."""
        is_subagent = self._is_subagent_request()
        waited = time.monotonic()
        last_ka = 0.0
        subagent_slot_acquired = False
        timeout_budget = SUBAGENT_QUEUE_TIMEOUT_S if is_subagent else QUEUE_TIMEOUT_S
        effective_reserved = min(UI_RESERVED_SLOTS, max(0, MAX_CONCURRENT - 1))

        try:
            if is_subagent:
                while not _subagent_slots.acquire(timeout=1.0):
                    if _client_gone(self.connection):
                        return "client_gone"
                    if time.monotonic() - waited > timeout_budget:
                        return "queue_timeout"
                    if (
                        keepalive is not None
                        and time.monotonic() - last_ka >= KEEPALIVE_S
                    ):
                        last_ka = time.monotonic()
                        if not keepalive():
                            return "client_gone"
                subagent_slot_acquired = True

            while True:
                with _qos_lock:
                    if is_subagent and _slots._value <= effective_reserved:
                        can_acquire = False
                    else:
                        can_acquire = _slots.acquire(blocking=False)

                    if can_acquire:
                        self._subagent_slot_held = is_subagent
                        return ""

                if _client_gone(self.connection):
                    if subagent_slot_acquired:
                        _subagent_slots.release()
                    return "client_gone"
                if time.monotonic() - waited > timeout_budget:
                    if subagent_slot_acquired:
                        _subagent_slots.release()
                    return "queue_timeout"
                if keepalive is not None and time.monotonic() - last_ka >= KEEPALIVE_S:
                    last_ka = time.monotonic()
                    if not keepalive():
                        if subagent_slot_acquired:
                            _subagent_slots.release()
                        return "client_gone"

                with _qos_lock:
                    _qos_lock.wait(timeout=0.2)
        except Exception:
            if subagent_slot_acquired:
                _subagent_slots.release()
            raise

    _FAIL_CLOSE_KINDS = ("stream_error", "pump_error", "live_invalidated")

    def _execute(
        self,
        run: Run,
        keepalive,
        emulate_tools: bool,
        sse_writer: "StreamSink | None" = None,
    ) -> dict:
        """Гнать ход до конца; сквозной таймаут TIMEOUT_S на весь ход.

        Без sse_writer вывод копится в out["events"] и уходит клиенту отдельным этапом после
        освобождения T/L (RW-009), как прежде. С sse_writer (живой SSE-ход, AD-001..AD-003)
        content/reasoning_content уходят сюда же, по мере готовности text_delta/reasoning_delta
        от Run — с коалесацией ~40мс (AD-003), чтобы не дробить кадры на один символ. Пока
        дельта мессенджа копится, вперёд подсматривается один элемент очереди (pushback): смена
        mid/вида завершает текущую группу, а fail-close вид (stream_error/pump_error/
        live_invalidated) или уже выставленный run.live_invalidated — отбрасывает НЕотданный
        буфер целиком и завершает ход ошибкой (ничего незакоммиченного клиенту не покажется).
        Размышления идут мимо ToolCallParser. При emulate_tools текстовый поток проходит через
        ToolCallParser (в живом ходе — в strict_live режиме: сырой `<tool_call>` не утечёт).
        Превышение deadline -> kill группы (в run.close()), state=timeout.
        """
        pieces = []
        events: list = []
        tool_calls: list = []
        usage = {}
        result_ev = {}
        turn_start = time.monotonic()
        last_ka = time.monotonic()
        # Safety cap is the absolute upper bound (watchdog against infinite loops)
        safety_cap_s = self._effective_safety_cap_s()
        safety_deadline = turn_start + safety_cap_s

        idle_timeout_s = self._effective_idle_timeout_s()
        last_activity = turn_start
        cur_mid = [
            None
        ]  # mid последнего content-куска в pieces (разделитель "\n\n" между сообщениями)
        pushback = None  # элемент очереди, подсмотренный при коалесации, но не обработанный сейчас
        managed_turn = getattr(self, "_active_managed_turn", None)
        detach_on_disconnect = bool(getattr(self, "_detach_on_disconnect", False))
        watchdog_enabled = os.environ.get(
            "BRIDGE_ADAPTIVE_WATCHDOG_ENABLED", "true"
        ).strip().lower() in ("1", "true", "yes", "on")
        proc_watchdog = ProcessWatchdog(log_fn=_log) if watchdog_enabled else None
        watchdog_seeded_pid = [0]

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
                "timeout_s": safety_cap_s,
            }

        # RW-009 в живом ходе: зависший (не читающий, но не закрытый) клиент — write()
        # с LIVE_WRITE_TIMEOUT_S сигналит об этом провалом sse_writer. Вычисление хода и
        # commit чата НЕ прерываются (как и в небуферизованном старом пути — T/L освобождаются
        # по расписанию _execute, независимо от клиента): просто дальнейшие попытки живой
        # записи этому клиенту прекращаются (повторный таймаут на каждый кусок — бессмысленная
        # трата времени, раз клиент уже не читает).
        # RW-203: состояние живёт на Handler (а не в локальной переменной), чтобы внешний
        # _serve_sse видел отказ и после возврата _execute; каждый ход начинает с чистого.
        self._client_write_dead = False

        def add_content(text: str) -> None:
            if not text:
                return
            pieces.append(text)
            events.append(("content", text))
            if sse_writer is not None:
                for piece in _text_slices(text):
                    if managed_turn is not None and not managed_turn.buffer.sealed:
                        managed_turn.buffer.append("content", piece)
                    if self._client_write_dead:
                        continue
                    # RW-011 в живом ходе: бюджет резервируется ДО фактической отдачи
                    # куска — ничего незарезервированного клиенту не покажется. Бюджет
                    # считается в байтах UTF-8 (RW-206): piece может содержать кириллицу/
                    # emoji, где len(piece) (символы) занижает фактический размер на проводе.
                    piece_bytes = len(piece.encode("utf-8"))
                    if not _DELIVERY_BUDGET.reserve(piece_bytes):
                        raise _LiveBudgetExceeded()
                    self._delivery_reserved += piece_bytes
                    if not sse_writer("content", piece):
                        self._client_write_dead = True
                        if managed_turn is not None and detach_on_disconnect:
                            TURN_MANAGER.mark_detached(managed_turn.turn_id)
                        else:
                            break
            elif managed_turn is not None and not managed_turn.buffer.sealed:
                for piece in _text_slices(text):
                    managed_turn.buffer.append("content", piece)

        def add_reasoning(text: str) -> None:
            if not text:
                return
            events.append(("reasoning", text))
            if sse_writer is not None:
                for piece in _text_slices(text):
                    if managed_turn is not None and not managed_turn.buffer.sealed:
                        managed_turn.buffer.append("reasoning", piece)
                    if self._client_write_dead:
                        continue
                    piece_bytes = len(piece.encode("utf-8"))
                    if not _DELIVERY_BUDGET.reserve(piece_bytes):
                        raise _LiveBudgetExceeded()
                    self._delivery_reserved += piece_bytes
                    if not sse_writer("reasoning", piece):
                        self._client_write_dead = True
                        if managed_turn is not None and detach_on_disconnect:
                            TURN_MANAGER.mark_detached(managed_turn.turn_id)
                        else:
                            break
            elif managed_turn is not None and not managed_turn.buffer.sealed:
                for piece in _text_slices(text):
                    managed_turn.buffer.append("reasoning", piece)

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
            # Managed replay получает вызовы после единственной границы в _dispatch.

        parser = (
            ToolCallParser(add_content, add_call, strict_live=sse_writer is not None)
            if emulate_tools
            else None
        )

        def take():
            nonlocal pushback
            if pushback is not None:
                item, pushback = pushback, None
                return item
            return run.q.get(timeout=1.0)

        while True:
            rproc = getattr(run, "proc", None)
            if (
                rproc is not None
                and getattr(rproc, "pid", 0)
                and watchdog_seeded_pid[0] != rproc.pid
            ):
                watchdog_seeded_pid[0] = rproc.pid
                if proc_watchdog is not None:
                    proc_watchdog.seed(rproc.pid)
                if managed_turn is not None:
                    managed_turn.bind_process(pgid=rproc.pid, terminate_fn=run.close)
            if managed_turn is not None and managed_turn.cancel_event.is_set():
                run.cancel.set()
                return state("client_gone", 1, "turn cancelled")
            now = time.monotonic()
            if now > safety_deadline:
                return state(
                    "safety_cap",
                    124,
                    f"proxy safety cap timeout after {safety_cap_s:.1f}s",
                )
            if not run.got_event and now - run.started > FIRST_TOKEN_TIMEOUT_S:
                return state(
                    "first_token_timeout",
                    124,
                    f"{cli_label('no_event')} within {FIRST_TOKEN_TIMEOUT_S:g}s",
                )
            latest_progress = max(
                last_activity, getattr(run, "last_progress", 0.0) or 0.0
            )
            effective_idle = max(idle_timeout_s, 1.0)
            if run.got_event and (now - latest_progress > effective_idle):
                if (
                    effective_idle >= 10.0
                    and proc_watchdog is not None
                    and rproc is not None
                    and getattr(rproc, "pid", 0)
                    and proc_watchdog.sample(rproc.pid).has_progress
                ):
                    last_activity = now
                    run.last_progress = now
                else:
                    return state(
                        "idle_timeout",
                        124,
                        f"{cli_label('no_progress')} within {effective_idle:.1f}s",
                    )
            if not self._client_write_dead and _client_gone(self.connection):
                if detach_on_disconnect:
                    self._client_write_dead = True
                    if managed_turn is not None:
                        TURN_MANAGER.mark_detached(managed_turn.turn_id)
                else:
                    return state("client_gone", 1)
            try:
                kind, payload = take()
                last_activity = time.monotonic()
            except queue.Empty:
                # RW-204/RW-203: страховка сверх проверки внутри text_delta/reasoning_delta
                # ниже — overflow Run.q (RW-204) мог выбросить именно terminal-событие
                # (result/done), так что очередь остаётся пустой навсегда и ничего не
                # подтвердит успех по kind=="done". Проверяется именно здесь (очередь
                # подтверждённо пуста прямо сейчас), а не перед take(): так уже
                # опубликованный и ещё не выбранный из очереди бэклог (например, валидный
                # префикс другого mid) не отбрасывается только из-за гонки с флагом,
                # выставленным producer'ом синхронно и раньше, чем успел отработать consumer.
                if run.live_invalidated:
                    return state(
                        "live_invalidated",
                        1,
                        run._last_error
                        or "a streamed message was retracted before the turn completed",
                    )
                # RW-201/RW-009: клиент уже признан мёртвым по провалу live-записи
                # content/reasoning (client_write_dead) — повторная запись keepalive
                # ему не нужна и не делается; само обращение к keepalive() ниже
                # ограничено тем же LIVE_WRITE_TIMEOUT_S, что и content/reasoning
                # (см. Handler._serve_sse.keepalive), так что эта ветка больше не
                # способна держать T/L дольше нескольких секунд ради одного клиента.
                if (
                    keepalive is not None
                    and not self._client_write_dead
                    and time.monotonic() - last_ka >= KEEPALIVE_S
                ):
                    last_ka = time.monotonic()
                    if not keepalive():
                        if detach_on_disconnect:
                            self._client_write_dead = True
                            if managed_turn is not None:
                                TURN_MANAGER.mark_detached(managed_turn.turn_id)
                        else:
                            return state("client_gone", 1)
                continue
            if kind in ("text_delta", "reasoning_delta"):
                group_mid, buf0 = payload
                buf = [buf0]
                coalesce_deadline = time.monotonic() + 0.04
                while True:
                    if run.live_invalidated:
                        break
                    remaining = coalesce_deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        nxt_kind, nxt_payload = run.q.get(timeout=remaining)
                    except queue.Empty:
                        break
                    if nxt_kind == kind and nxt_payload[0] == group_mid:
                        buf.append(nxt_payload[1])
                        continue
                    pushback = (nxt_kind, nxt_payload)
                    if nxt_kind in self._FAIL_CLOSE_KINDS:
                        buf = None  # не наш показывать: ход фейлится, обработает pushback ниже
                    break
                if run.live_invalidated:
                    return state(
                        "live_invalidated",
                        1,
                        run._last_error
                        or "a streamed message was retracted before the turn completed",
                    )
                if buf is None:
                    continue
                text = "".join(buf)
                if kind == "text_delta":
                    prefix = ""
                    if cur_mid[0] != group_mid:
                        if pieces:
                            prefix = "\n\n"
                        cur_mid[0] = group_mid
                    text = prefix + text
                    try:
                        if parser is not None:
                            parser.feed(text)
                        else:
                            add_content(text)
                    except LiveParserError as exc:
                        return state("live_invalidated", 1, str(exc)[:500])
                    except _LiveBudgetExceeded:
                        return state(
                            "delivery_budget",
                            1,
                            "bridge overloaded: delivery memory budget exhausted",
                        )
                else:
                    try:
                        add_reasoning(text)
                    except _LiveBudgetExceeded:
                        return state(
                            "delivery_budget",
                            1,
                            "bridge overloaded: delivery memory budget exhausted",
                        )
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
            elif kind == "live_invalidated":
                return state("live_invalidated", 1, str(payload))
            elif kind == "done":
                rc, final_text = payload
                if run.live_invalidated:
                    # RW-211/AD-001: инвалидация (retract уже отданного mid, срыв префикса,
                    # overflow live-очереди) проверяется ДО parser.finish и fallback
                    # final_text: клиенту уже мог уйти байт отозванного сообщения — успех
                    # не выдаётся, даже если терминал пришёл с rc == 0.
                    return state(
                        "live_invalidated",
                        1,
                        run._last_error
                        or "a streamed message was retracted before the turn completed",
                    )
                if parser is not None:
                    try:
                        parser.finish()  # досбрасываем хвост незакрытого блока текстом
                    except LiveParserError as exc:
                        return state("live_invalidated", 1, str(exc)[:500])
                    except _LiveBudgetExceeded:
                        return state(
                            "delivery_budget",
                            1,
                            "bridge overloaded: delivery memory budget exhausted",
                        )
                # Fallback: события message не дали ни текста, ни вызовов, но итог
                # есть в completion.finalText. Проводим его тем же путём (парсер +
                # on_text), чтобы потоковый клиент не получил пустой ответ со stop.
                if not pieces and not tool_calls and final_text:
                    try:
                        if parser is not None:
                            parser.feed(final_text)
                            parser.finish()
                        else:
                            add_content(final_text)
                    except LiveParserError as exc:
                        return state("live_invalidated", 1, str(exc)[:500])
                    except _LiveBudgetExceeded:
                        return state(
                            "delivery_budget",
                            1,
                            "bridge overloaded: delivery memory budget exhausted",
                        )
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

    def _run_once(
        self, ctx: dict, keepalive, sse_writer: "StreamSink | None" = None
    ) -> dict:
        """Ход запроса: порядок ресурсов L -> P -> T, до 3 попыток при транзиентном сбое.

        Без sse_writer — прежнее поведение: вывод копится в out["events"] и уходит клиенту
        отдельным этапом после освобождения T/L (RW-009). С sse_writer (живой SSE-ход)
        content/reasoning_content уходят клиенту ПРЯМО во время _execute (AD-001..AD-003);
        T/L всё равно освобождаются сразу по возврату _execute, независимо от скорости клиента.
        """
        # Адаптер возвращает legacy-контекст без фасадных полей корреляции.
        ctx = {
            **ctx,
            "request_id": self._trace.request_id if self._trace else None,
            "subagent_id": self._trace.subagent_id if self._trace else None,
        }
        model = build_cli_model_selection(ctx)
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
                _reconcile_chat_env(chat, ctx.get("fwd_env"))
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
                plan["fwd_env"] = ctx.get("fwd_env")
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
                t_released = [False]

                def _release_turn_slot() -> None:
                    release_turn_slot(self, t_held, t_released)

                managed_turn = getattr(self, "_active_managed_turn", None)
                if managed_turn is not None:
                    managed_turn._slot_release_fn = _release_turn_slot
                    managed_turn._slot_released = False
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
                        f"prompt_bytes={len(ctx['prompt'].encode())}{image_part} {tag} "
                        f"request_id={ctx.get('request_id') or '-'} subagent_id={ctx.get('subagent_id') or '-'}"
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
                            _release_turn_slot()
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
                        plan,
                        chat.proc if plan["path"] == "hot" else None,
                        holds_slot,
                        sse_writer,
                    )
                    if managed_turn is not None:
                        managed_turn.bind_process(
                            pgid=getattr(new_run, "pgid", None)
                            or getattr(getattr(new_run, "proc", None), "pid", None),
                            terminate_fn=lambda p=getattr(new_run, "proc", None): (
                                _close_async(p, "kill") if p is not None else None
                            ),
                        )
                    holds_slot = False
                except Exception as exc:  # noqa: BLE001 - любая ошибка подготовки хода: ресурсы назад, штатный 502
                    if new_run is None:
                        if t_held:
                            _release_turn_slot()
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
                            _release_turn_slot()
                        if holds_slot:
                            POOL.release()
                    raise
                run = new_run
                open_attempt = (plan, run)
                try:
                    out = self._execute(
                        run,
                        keepalive,
                        ctx["emulate_tools"],
                        sse_writer,
                    )
                finally:
                    try:
                        run.close()
                    finally:
                        if managed_turn is not None:
                            managed_turn.release_slot_once()
                        _release_turn_slot()
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
                # Без sse_writer контент до terminal не отдаётся, delivered здесь — страховка.
                # С sse_writer часть контента могла уже уйти клиенту ЖИВЬЁМ до сбоя (run._live_mids
                # непусто) — тихий повтор показал бы его клиенту повторно, поэтому тоже delivered.
                delivered = bool(
                    out.get("text") or out.get("tool_calls") or run._live_mids
                )
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
            cache_read = usage.get("cache_read_tokens")
            cache_read_str = (
                str(cache_read)
                if isinstance(cache_read, int) and not isinstance(cache_read, bool)
                else "-"
            )
            _log(
                f"usage sess={sess8} raw={raw_in}/{raw_out} "
                f"cache_read={cache_read_str} "
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
        label = str(out.get("backend_kind") or cli_label("binary"))
        timeout_s = float(out.get("timeout_s") or TIMEOUT_S)
        if st == "timeout":
            return {
                "message": out.get("err")
                or f"{label} exec timed out after {timeout_s:.1f}s",
                "type": "timeout",
                "code": 504,
            }
        if st in ("idle_timeout", "safety_cap"):
            return {
                "message": str(
                    out.get("err") or f"{label} exec timed out after {timeout_s:.1f}s"
                )[:500],
                "type": "timeout",
                "code": 504,
            }
        if st == "first_token_timeout":
            return {
                "message": f"first_token_timeout: {cli_label('exec')} gave no event "
                f"within {FIRST_TOKEN_TIMEOUT_S:g}s",
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
                "message": str(
                    out.get("err") or f"{cli_label('exec')} reported an error"
                )[:500],
                "type": "droid_error",
                "code": 502,
            }
        if st == "live_invalidated":
            # AD-001: часть уже отданного клиенту live-префикса оказалась незакоммиченной
            # (retract после показа или незакрытый/сломанный <tool_call> в strict_live-парсере).
            return {
                "message": str(
                    out.get("err") or "live stream prefix was invalidated mid-turn"
                )[:500],
                "type": "live_prefix_invalidated",
                "code": 502,
            }
        if st == "delivery_budget":
            # RW-011 в живом ходе: кусок, который привёл бы к превышению бюджета, отброшен
            # ДО отдачи (см. add_content/add_reasoning) — то же тело ошибки, что и у
            # _reserve_delivery, просто обнаружено раньше (на лету, а не постфактум).
            return {
                "message": "bridge overloaded: delivery memory budget exhausted",
                "type": "proxy_error",
                "code": 502,
            }
        if st == "backend_error":
            raw_err = str(out.get("err") or "")
            detail = " ".join(
                _err_summary(raw_err, 500).replace("\x00", " ").split()
            )
            message = f"{label} exec failed rc={out.get('rc')}"
            if detail:
                message = f"{message}: {detail}"
            return {
                "message": message,
                "detail": detail,
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
        """Резерв памяти ответа до выдачи (RW-011): None — взят, иначе тело ошибки 502 proxy_error.

        В живом ходе часть байт (content/reasoning) уже зарезервирована поштучно во время
        _execute (см. add_content/add_reasoning) — здесь довносится только остаток
        (например, аргументы tool_call), чтобы не резервировать один и тот же текст дважды.
        """
        size = _delivery_size(out) - self._delivery_reserved
        if size <= 0:
            return None
        if not _DELIVERY_BUDGET.reserve(size):
            _log(f"delivery_budget_exhausted bytes={size}")
            return {
                "message": "bridge overloaded: delivery memory budget exhausted",
                "type": "proxy_error",
                "code": 502,
            }
        self._delivery_reserved += size
        return None

    def _parse_from_seq(self) -> int | None:
        raw_seq = None
        if "?" in self.path:
            qs = self.path.split("?", 1)[1]
            for part in qs.split("&"):
                if part.startswith("from_seq="):
                    raw_seq = part.split("=", 1)[1]
                    break
        if raw_seq is None:
            hdr_seq = self.headers.get("Last-Event-ID")
            if hdr_seq is not None and hdr_seq.strip():
                raw_seq = hdr_seq.strip()
        if raw_seq is None or raw_seq == "":
            return 0
        if not re.fullmatch(r"[0-9]+", str(raw_seq).strip()):
            return None
        return int(str(raw_seq).strip())

    def _turn_snapshot(self, turn_id: str) -> dict[str, Any]:
        owner = _owner_token_hash(self)
        try:
            return TURN_MANAGER.get_turn_snapshot(turn_id, owner_token_hash=owner)
        except KeyError:
            if not flag_enabled(FLAG_TELEMETRY):
                raise
        return get_registry().turn_snapshot(turn_id, owner)

    def _serve_turn_stream(self, turn_id: str) -> None:
        if not validate_turn_id(turn_id):
            self._send(
                400,
                {
                    "error": {
                        "message": "invalid turn_id",
                        "type": "invalid_request",
                        "code": 400,
                    }
                },
            )
            return
        from_seq = self._parse_from_seq()
        if from_seq is None:
            self._send(
                400,
                {
                    "error": {
                        "message": "invalid from_seq",
                        "type": "invalid_request",
                        "code": 400,
                    }
                },
            )
            return
        try:
            turn = TURN_MANAGER.get_turn(
                turn_id, owner_token_hash=_owner_token_hash(self)
            )
        except KeyError:
            self._send(
                404,
                {
                    "error": {
                        "message": f"turn not found: {turn_id}",
                        "type": "not_found",
                        "code": 404,
                    }
                },
            )
            return
        except PermissionError:
            self._send(
                403,
                {
                    "error": {
                        "message": "turn belongs to another token",
                        "type": "forbidden",
                        "code": 403,
                    }
                },
            )
            return
        try:
            turn.buffer.get_since(
                from_seq,
                turn_id=turn.turn_id,
                state_dump_path=turn.state_dump_path,
            )
        except GapDetectedError as exc:
            self._send(410, exc.to_http_payload())
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("X-Turn-Id", turn.turn_id)
            self.end_headers()
            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        for frame in TURN_MANAGER.iter_sse_stream(
            turn,
            from_seq=from_seq,
            keepalive_interval_s=min(10.0, KEEPALIVE_S),
            client_gone_fn=lambda: _client_gone(self.connection),
        ):
            if not self._emit(frame):
                TURN_MANAGER.mark_detached(turn.turn_id)
                return

    # ---- HTTP --------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        self._trace = self._req_started_mono = None  # GET-ответы (_send) в телеметрию запросов не попадают
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/v1/health"):
            # Контракт из семи ключей прежний (расширять запрещено); ok = AND по обязательным
            # бэкендам (droid: невалидный receipt = spawn невозможен -> ok=false, RW-015),
            # active и max_concurrent суммируются по включённым бэкендам.
            required = [a for a in BACKENDS.adapters() if a.required]
            draining = _shutting_down or (
                _is_drain_enabled() and LIFECYCLE.is_draining()
            )
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
                extra_headers={"X-Bridge-Draining": "true"} if draining else None,
            )
            return
        if self._handle_models_get():
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
        if path == "/v1/resilience":
            self._send(200, RESILIENCE.snapshot(a.id for a in BACKENDS.adapters()))
            return
        if path == "/v1/telemetry":
            return self._telemetry_serve_get()
        if path == "/v1/quarantine":
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
            catalog_models = []
            models_source = BACKENDS.models() if hasattr(BACKENDS, "models") else []
            for item in models_source:
                m = item[1] if isinstance(item, tuple) and len(item) >= 2 else item
                mid = getattr(m, "id", None) or getattr(m, "name", None) or str(m)
                if mid and mid not in catalog_models:
                    catalog_models.append(mid)
            self._send(
                200,
                _PENALTY_TRACKER.get_quarantine_payload(catalog_models),
            )
            return
        if _is_detached_enabled() and path.startswith("/v1/turns/"):
            m_stream = re.fullmatch(r"/v1/turns/([^/]+)/stream", path)
            if m_stream:
                self._serve_turn_stream(m_stream.group(1))
                return
            m_turn = re.fullmatch(r"/v1/turns/([^/]+)", path)
            if m_turn:
                turn_id = m_turn.group(1)
                if not validate_turn_id(turn_id):
                    self._send(
                        400,
                        {
                            "error": {
                                "message": "invalid turn_id",
                                "type": "invalid_request",
                                "code": 400,
                            }
                        },
                    )
                    return
                try:
                    snap = self._turn_snapshot(turn_id)
                except KeyError:
                    self._send(
                        404,
                        {
                            "error": {
                                "message": f"turn not found: {turn_id}",
                                "type": "not_found",
                                "code": 404,
                            }
                        },
                    )
                    return
                except PermissionError:
                    self._send(
                        403,
                        {
                            "error": {
                                "message": "turn belongs to another token",
                                "type": "forbidden",
                                "code": 403,
                            }
                        },
                    )
                    return
                self._send(200, snap)
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

    def do_DELETE(self) -> None:  # noqa: N802
        if not _auth_ok(self):
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
        path = self.path.split("?", 1)[0]
        m_turn = (
            re.fullmatch(r"/v1/turns/([^/]+)", path) if _is_detached_enabled() else None
        )
        if not m_turn:
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
        turn_id = m_turn.group(1)
        if not validate_turn_id(turn_id):
            self._send(
                400,
                {
                    "error": {
                        "message": "invalid turn_id",
                        "type": "invalid_request",
                        "code": 400,
                    }
                },
            )
            return
        owner_hash = _owner_token_hash(self)
        try:
            TURN_MANAGER.cancel_turn(turn_id, owner_token_hash=owner_hash)
            snap = TURN_MANAGER.get_turn_snapshot(turn_id, owner_token_hash=owner_hash)
        except KeyError:
            self._send(
                404,
                {
                    "error": {
                        "message": f"turn not found: {turn_id}",
                        "type": "not_found",
                        "code": 404,
                    }
                },
            )
            return
        except PermissionError:
            self._send(
                403,
                {
                    "error": {
                        "message": "turn belongs to another token",
                        "type": "forbidden",
                        "code": 403,
                    }
                },
            )
            return
        self._send(200, snap)

    def do_POST(self) -> None:  # noqa: N802
        self._headers_already_sent = False
        self._trace = None
        self._response_status = 0
        self._telemetry_begin()
        path = self.path.split("?", 1)[0]
        m_cancel = (
            re.fullmatch(r"/v1/turns/([^/]+)/cancel", path)
            if _is_detached_enabled()
            else None
        )
        if not m_cancel and (
            _shutting_down or (_is_drain_enabled() and LIFECYCLE.is_draining())
        ):
            is_sub = self._is_subagent_request()
            if _shutting_down or not LIFECYCLE.wait_for_drain_hold(is_subagent=is_sub):
                code, drain_headers, drain_body = LIFECYCLE.draining_response(is_subagent=is_sub)
                err = drain_body.get("error", {})
                self._reject(code, err.get("type", "overloaded"), err.get("message", "bridge is shutting down"), extra_headers=drain_headers)
                return
        hub_auth_ok = _auth_ok(self)
        deferred_passthrough_auth = False
        if not hub_auth_ok:
            if (
                self.client_address[0] in _LOOPBACK_PEERS
                and urlparse(self.path).path in _CHAT_PATHS
                and PASSTHROUGH_AUTH_FLAG_SOURCE.enabled()
                and any(
                    isinstance(adapter, PassthroughAdapter)
                    and adapter.validate_client_token(_extract_auth_token(self))
                    for adapter in BACKENDS.adapters()
                )
            ):
                deferred_passthrough_auth = True
            else:
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
        if urlparse(self.path).path in (
            "/v1/models/refresh",
            "/models/refresh",
        ) or re.match(
            r"^/v1/providers/[^/]+/v1/models/refresh$", urlparse(self.path).path
        ):
            self._handle_models_refresh()
            return
        if path == "/v1/quarantine":
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
            self._handle_quarantine_post()
            return
        self._trace = None
        self._response_status = 0
        _enforce_forward_kill_switch()
        self._active_managed_turn = None
        self._context_pruned = None
        managed_turn: ManagedTurn | None = None
        attached_existing = False

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
            if m_cancel is not None:
                turn_id = m_cancel.group(1)
                if not validate_turn_id(turn_id):
                    self._reject(400, "invalid_request", "invalid turn_id")
                    return
                owner_hash = _owner_token_hash(self)
                try:
                    TURN_MANAGER.cancel_turn(turn_id, owner_token_hash=owner_hash)
                    snap = TURN_MANAGER.get_turn_snapshot(
                        turn_id, owner_token_hash=owner_hash
                    )
                except KeyError:
                    self.close_connection = True
                    self._send(
                        404,
                        {
                            "error": {
                                "message": f"turn not found: {turn_id}",
                                "type": "not_found",
                                "code": 404,
                            }
                        },
                    )
                    return
                except PermissionError:
                    self.close_connection = True
                    self._send(
                        403,
                        {
                            "error": {
                                "message": "turn belongs to another token",
                                "type": "forbidden",
                                "code": 403,
                            }
                        },
                    )
                    return
                self._send(200, snap)
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
            self._parsed_req = req
            self._telemetry_meta_request(req)
            if REQUEST_ATTRIBUTION_ENABLED:
                self._trace = _resolve_trace(dict(self.headers.items()), req)
            else:
                self._trace = None
            # (7) путь.
            m_provider_chat = _PROVIDER_CHAT_RE.match(path)
            provider_id = m_provider_chat.group(1) if m_provider_chat else None
            if m_provider_chat is not None:
                if not _auth_ok(self):
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
                if provider_id not in PROVIDER_SCOPES:
                    self._reply_error(404, "Unknown provider", "invalid_request_error")
                    return
                path = "/v1/chat/completions"
                self.path = "/v1/chat/completions"

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

            idempotency_key = (self.headers.get("X-Idempotency-Key") or "").strip()
            if idempotency_key and req.get("step_job_id") != idempotency_key:
                req["step_job_id"] = idempotency_key
                raw = json.dumps(req, ensure_ascii=False).encode("utf-8")
            if self.headers.get(
                "X-Bypass-Model-Filter"
            ) != "1" and _MODEL_NOTES_FILTER.is_blocked(model_id):
                self._send(
                    503,
                    {
                        "error": {
                            "message": "Model temporarily blocked by operational limits",
                            "type": "model_limit_blocked",
                            "code": 503,
                        }
                    },
                )
                return

            fleet_models = FLEET.get("models", {}) if isinstance(FLEET, dict) else {}
            alias = _resolve_model_alias(model_id, fleet_models)
            alias_effort = None
            if alias is not None:
                resolved_id = alias[0] if isinstance(alias, (tuple, list)) else alias
                alias_effort = (
                    alias[1]
                    if isinstance(alias, (tuple, list)) and len(alias) > 1
                    else None
                )
            else:
                resolved_id = model_id

            # Изоляция внутренних моделей (Auth-First / Secret Isolation)
            internal_key = getattr(
                sys.modules[__name__], "_INTERNAL_SERVICE_KEY", None
            ) or os.environ.get("INTERNAL_SERVICE_KEY", "")
            if bool(internal_key) and (
                raw_model in INTERNAL_MODEL_IDS
                or model_id in INTERNAL_MODEL_IDS
                or resolved_id in INTERNAL_MODEL_IDS
            ):
                supplied = self.headers.get("X-Internal-Service-Key", "")
                if not hmac.compare_digest(
                    supplied.encode("utf-8"), internal_key.encode("utf-8")
                ):
                    self._reject(
                        403,
                        "internal_model_forbidden",
                        "Model reserved for internal review",
                        "unknown",
                        model_len,
                    )
                    return

            # Проверка штрафа модели (Fail-Fast 503) по каноническому идентификатору
            canonical_pen_id = (resolved_id or model_id).strip().lower()
            stat = _PENALTY_TRACKER.get_model_status(canonical_pen_id)
            if stat["is_penalized"]:
                retry_after_s = max(1, math.ceil(stat["remaining_cooldown"]))
                pen_until = int(stat["penalized_until"])
                self._send(
                    503,
                    {
                        "error": {
                            "message": (
                                f"Model '{model_id}' is temporarily penalized due to start failures. "
                                f"Cooldown active for {retry_after_s}s."
                            ),
                            "type": "model_penalized",
                            "code": 503,
                            "penalized_until": pen_until,
                        }
                    },
                    extra_headers={"Retry-After": str(retry_after_s)},
                )
                return

            # Проверка скоупа провайдера для чата
            if provider_id is not None:
                owner = PROVIDER_SCOPES[provider_id]
                owner_tuple = (owner,) if isinstance(owner, str) else owner
                published = _get_published_models()
                if resolved_id not in published:
                    self._reject(
                        404,
                        "model_not_found",
                        "model is not in the catalogue",
                        "unknown",
                        model_len,
                    )
                    return
                a, m = published[resolved_id]
                owned_by = (
                    getattr(a, "owned_by", "")
                    if a is not None
                    else (
                        getattr(m, "owned_by", "")
                        or (m.get("owned_by", "") if isinstance(m, dict) else "")
                    )
                )
                if owned_by not in owner_tuple:
                    self._reply_error(
                        400,
                        f"Model '{raw_model}' is not available for provider '{provider_id}'",
                        code="model_not_in_provider_scope",
                    )
                    return

            if (
                resolved_id != model_id
                and self.headers.get("X-Bypass-Model-Filter") != "1"
                and _MODEL_NOTES_FILTER.is_blocked(resolved_id)
            ):
                self._send(
                    503,
                    {
                        "error": {
                            "message": "Model temporarily blocked by operational limits",
                            "type": "model_limit_blocked",
                            "code": 503,
                        }
                    },
                )
                return

            model_id = resolved_id
            self._telemetry_meta(model=model_id)
            if model_id not in fleet_models:
                self._reject(404, "model_not_found", "model is not in the catalogue", "unknown", model_len)
                return
            model = fleet_models[model_id]
            is_droid = str(model.get("backend") or "").strip().lower() == "droid"
            # denied: объединение raw-заголовка и trace (заголовок/extra_body/body), чтобы
            # роль судьи нельзя было провести альтернативным источником идентификатора.
            raw_subagent_id = str(self.headers.get("X-Subagent-Id") or "")
            # Прочие backend не платят за разбор trace; при выключенной атрибуции
            # self._trace пуст, поэтому для droid он строится здесь же, иначе запрет
            # судьям стал бы fail-open и обходился через extra_body/body.
            trace_subagent_id = None
            if is_droid:
                trace = getattr(self, "_trace", None) or _resolve_trace(
                    dict(self.headers.items()), req
                )
                trace_subagent_id = trace.subagent_id
            denied_role = is_droid and denied_subagent(
                "DROID", raw_subagent_id, trace_subagent_id
            )
            if denied_role:
                return self._reject(
                    403,
                    "droid_forbidden_for_role",
                    "droid route is forbidden for this subagent role",
                    model_id,
                    model_len,
                )
            denial = _quarantine_denial(model_id, self.headers.get("X-Subagent-Id"))
            if denial is not None:
                self._log_reject(denial.reason, model_id, model_len)
                self.close_connection = True
                self._send(denial.http, denial.body())
                return
            if deferred_passthrough_auth:
                selected = BACKENDS.get(model["backend"])
                if not isinstance(
                    selected, PassthroughAdapter
                ) or not selected.validate_client_token(_extract_auth_token(self)):
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
            # (8a) passthrough (AD-003/AD-007): raw-шов ДО effort-клампа, транскрипции и контекста —
            # model/reasoning_effort/tools/Authorization уходят upstream дословно.
            passthrough = BACKENDS.get(model["backend"])
            if isinstance(passthrough, PassthroughAdapter):
                if raw_model != model_id and alias is None:
                    self._reject(
                        400,
                        "model_not_allowed",
                        "passthrough requires an exact model id",
                    )
                    return
                effort_on = flag_enabled(FLAG_EFFORT_CATALOG)
                req, pt_effort = prepare_passthrough_request(
                    req, model, model_id, alias, alias_effort, effort_on
                )
                target_model = resolve_target_model(model, model_id)
                if pt_effort.apply or target_model != model_id or alias:
                    if pt_effort.clamped_from is not None:
                        _log(describe_clamp("passthrough reasoning_effort", pt_effort.clamped_from, pt_effort.value, model_id, _LOG_EFFORT_MAX))
                    raw = json.dumps(req, ensure_ascii=False).encode("utf-8")
                _log(
                    f"chat route=passthrough model={model_id} alias={model_id + '-' + alias[1] if alias else '-'} {self._trace_log_fields()}"
                )
                self._serve_resilient(
                    model["backend"],
                    lambda _h=hub_auth_ok: self._serve_passthrough(
                        passthrough, raw, req, model_id, _hub_auth_ok=_h
                    ),
                )
                return
            # (9) effort: строковый вне каталога клампится вниз к allowed модели.
            raw_effort = req.get("reasoning_effort")
            effort_from_alias = raw_effort is None and alias_effort is not None
            if effort_from_alias:
                raw_effort = alias_effort
            if raw_effort is None:
                effort = model["default_effort"]
                effort_source = "default"
            elif isinstance(raw_effort, str):
                candidate = raw_effort.strip()
                if not candidate:
                    effort = model["default_effort"]
                    effort_source = "default"
                else:
                    effort, clamped = clamp_effort_downward(
                        candidate, model["efforts"], model["default_effort"]
                    )
                    effort_source = "alias" if effort_from_alias else "request"
                    if clamped:
                        _log(describe_clamp("reasoning_effort", candidate, effort, model_id, _LOG_EFFORT_MAX))
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
            # (off — read-only droid); дефолт конфигурируемый, fail-closed off.
            autonomy, autonomy_source = req.get("autonomy"), "request"
            if is_droid:
                try:
                    decision = resolve_autonomy_decision(
                        req.get("autonomy"),
                        "DROID",
                        subagent_id=raw_subagent_id or None,
                        require_subagent=True,
                    )
                    autonomy, autonomy_source = decision.value, decision.source
                except AutonomyViolation as exc:
                    self._reject(400, exc.reason, str(exc), model_id, model_len)
                    return
            else:
                # Не-Droid маршруты сохраняют прежнюю базовую проверку формата: тип и
                # значение low|medium|high|off проверяются без Droid-ограничений роли.
                try:
                    _ = validate_autonomy_request(req.get("autonomy"))
                except AutonomyViolation as exc:
                    self._reject(400, exc.reason, str(exc), model_id, model_len)
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
            # (10a) отказоустойчивость контекста: история вмещается в окно модели до всего прочего.
            gated = self._context_gate(req, model_id, model, model_len)
            if gated is None:
                return
            req, self._context_pruned = gated
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
            fwd_env = self._forwarded_env(extra, model_id, model_len)
            if fwd_env is False:
                return
            req_turn_id = (
                self.headers.get("X-Turn-Id") or str(extra.get("turn_id") or "")
            ).strip()
            resume_turn_id = (
                self.headers.get("X-Resume-Turn-Id")
                or str(extra.get("resume_turn_id") or "")
            ).strip()
            for candidate_tid in (req_turn_id, resume_turn_id):
                if candidate_tid and not validate_turn_id(candidate_tid):
                    self._reject(
                        400,
                        "invalid_request",
                        "invalid turn_id",
                        model_id,
                        model_len,
                    )
                    return
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
            self._instr_truncated = False
            instr = self._prompt_guard(
                messages, route, raw_key, cwd, model_id, model_len, adapter
            )
            if instr is None:
                return
            if self._instr_truncated:
                # Блок инструкций усечён на месте: prompt и транскрипт строятся заново из обновлённых messages.
                prompt = _messages_to_prompt(messages, tools, tool_choice, images)
                transcript = _transcribe(messages, tools, tool_choice, images)
                if route == "fallback" or not transcript["runnable"]:
                    transcript = {
                        "system": None,
                        "runnable": True,
                        "items": [
                            {"role": "user", "text": prompt, "digest": _digest(prompt)}
                        ],
                    }
            is_legacy_muse_sleep = (
                model["backend"] == "muse"
                and not req_turn_id
                and not resume_turn_id
                and not keyed
                and (Path(getattr(adapter, "wrapper", "")).parent / "mode").is_file()
                and (Path(getattr(adapter, "wrapper", "")).parent / "mode")
                .read_text(encoding="utf-8", errors="ignore")
                .strip()
                == "sleep"
            )
            detach_on_disconnect = (
                _is_detached_enabled()
                and (
                    _client_gone is _DEFAULT_CLIENT_GONE
                    or bool(req_turn_id or resume_turn_id)
                )
                and not is_legacy_muse_sleep
            )
            managed_turn: ManagedTurn | None = None
            attached_existing = False
            if _is_detached_enabled():
                try:
                    managed_turn, attached_existing = (
                        TURN_MANAGER.create_or_attach_turn(
                            model=model_id,
                            backend=model["backend"],
                            cwd=cwd,
                            messages=messages,
                            session_id=raw_key if keyed else "",
                            owner_token_hash=_owner_token_hash(self),
                            requested_turn_id=req_turn_id or None,
                            resume_turn_id=resume_turn_id or None,
                            stream=bool(req.get("stream")),
                            emulate_tools=emulate_tools,
                            idle_timeout_s=self._effective_idle_timeout_s(),
                            safety_cap_s=self._effective_safety_cap_s(),
                        )
                    )
                except PermissionError:
                    self._reject(
                        403,
                        "forbidden",
                        "turn belongs to another token",
                        model_id,
                        model_len,
                    )
                    return
                except ValueError as exc:
                    self._reject(400, "invalid_request", str(exc), model_id, model_len)
                    return
            self._active_managed_turn = managed_turn
            if managed_turn is not None:
                managed_turn.is_subagent = self._is_subagent_request()
                managed_turn.subagent_id = self._subagent_id()
            ctx = {
                "request_id": self._trace.request_id if self._trace else None,
                "subagent_id": self._trace.subagent_id if self._trace else None,
                "route": route,
                "key_hash": _key_hash(raw_key)
                if (route == "keyed" and isinstance(raw_key, str))
                else "",
                "rpc": transcript,
                "instr": instr if route in ("keyed", "nokey") else (0, "-", 0),
                "model": model_id,
                "target_model": resolve_target_model(model, model_id),
                "backend": model["backend"],
                "model_len": model_len,
                "effort": effort,
                "effort_source": effort_source,
                "autonomy": autonomy,
                "autonomy_source": autonomy_source,
                "prompt": prompt,
                "images": images,
                "cwd": cwd,
                "fwd_env": fwd_env,
                "emulate_tools": emulate_tools,
                "tool_schemas": build_tool_schemas(raw_tools),
                "tag": (
                    f"client={self._client_tag()} "
                    f"ua={(self.headers.get('User-Agent') or '-')[:60]}"
                ),
                "stream": bool(req.get("stream")),
                "turn_id": managed_turn.turn_id if managed_turn is not None else "",
                "managed_turn": managed_turn,
                "detach_on_disconnect": detach_on_disconnect,
                "attached_existing": attached_existing,
            }
            _log(
                f"chat route=cli model={model_id} alias={model_id + '-' + alias[1] if alias else '-'} {self._trace_log_fields()}"
            )
            serve = (
                (lambda: self._serve_sse(ctx))
                if ctx["stream"]
                else (lambda: self._serve_json(ctx))
            )
            if attached_existing:
                # Присоединение к уже идущему ходу нового вызова бэкенда не создаёт: допуск не нужен.
                serve()
            else:
                self._serve_resilient(model["backend"], serve)
        finally:
            if (
                managed_turn is not None
                and not attached_existing
                and managed_turn.is_active
            ):
                TURN_MANAGER.finalize_abandoned_turn(managed_turn)
            self._active_managed_turn = None
            if reserved and budget is not None:
                budget.release(reserved)
            _DELIVERY_BUDGET.release(self._delivery_reserved)
            self._delivery_reserved = 0

    def _forwarded_env(
        self, extra: Any, model_id: str, model_len: int
    ) -> "dict[str, str] | None | bool":
        """`extra_body.env` под флагом GigaRC (ADR-0016): dict | None; False — 400 уже отправлен.

        Флаг выключен — поле игнорируется целиком (поведение прежнее). Включён: запрещённые и
        невалидные имена/значения отбрасываются, не-loopback `AGENT_BROWSER_CDP` — 400. Если клиент
        прислал непустой env без `AGENT_BROWSER_CDP`, мост подставляет локально найденный loopback CDP.
        """
        if not is_browser_forwarding_enabled():
            return None
        raw_env = extra.get("env")
        if not raw_env:
            return None
        if not isinstance(raw_env, dict) or len(raw_env) > FORWARD_ENV_MAX_KEYS:
            self._reject(
                400,
                "invalid_request",
                "extra_body.env must be an object with at most %d entries"
                % FORWARD_ENV_MAX_KEYS,
                model_id,
                model_len,
            )
            return False
        clean = sanitize_forwarded_env(raw_env)
        if "AGENT_BROWSER_CDP" in raw_env and "AGENT_BROWSER_CDP" not in clean:
            self._reject(
                400,
                "invalid_request",
                "AGENT_BROWSER_CDP must be a loopback ws|wss|http address",
                model_id,
                model_len,
            )
            return False
        if clean and "AGENT_BROWSER_CDP" not in raw_env:
            found = discover_local_cdp_url()
            if found:
                clean["AGENT_BROWSER_CDP"] = found
        dropped = sorted(str(k)[:40] for k in raw_env if k not in clean)
        # Значения не логируются вообще (токены/CDP): только имена ключей и длины.
        accepted = [(k, len(v)) for k, v in clean.items()]
        _log(f"forward_env accepted={accepted!r} dropped={dropped[:16]!r}")
        return clean or None

    def _context_gate(
        self, req: dict, model_id: str, model: dict, model_len: int
    ) -> tuple[dict, str | None] | None:
        """Допуск истории в окно модели до images/prompt/адаптера (I-07); None = отказ уже отправлен.

        Возвращает (запрос для дальнейшей обработки, значение X-DSH-Context-Pruned | None).
        Исходный `req` не мутируется; при выключенных флагах возвращается как есть.
        """
        if not isinstance(req.get("messages"), list):
            return req, None
        try:
            flags = CONTEXT_FLAGS.current()
        except Exception:  # noqa: BLE001 - снимок флагов не должен ронять запрос
            flags = ctxres.Flags()
        entry = _context_entry(model_id, model)
        if ctxres.decide_mode(entry, flags) == "off":
            return req, None
        identity = ctxres.build_identity(
            ctxres.owner_scope(_owner_token_hash(self), _CONTEXT_OWNER_SECRET),
            "droid-hub",
            self.headers.items(),
        )
        try:
            prepared = ctxres.prepare(
                req,
                entry,
                flags,
                protocol="openai",
                identity=identity,
                store=CONTEXT_EPOCHS,
                serialize=False,
            )
        except ctxres.ContextError as exc:
            _log(f"context_resilience reject reason={exc.reason} model={model_id}")
            self._reject(exc.status, exc.error_type, exc.message(), model_id, model_len)
            return None
        _log(prepared.report.log_line())
        header = prepared.header
        return dict(prepared.body), (header[1] if header else None)

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
            # Сверх предела: мягкое усечение хвостовых проектных секций (канон защищён) вместо отказа.
            _log(f"instr_gate_truncated bytes={over[0]} limit={over[1]}")
            try:
                _soft_truncate_instructions(messages, in_kb, guard_max)
                blocks = _instr_blocks(messages, in_kb)
                instr = _instr_scan(messages, in_kb) if blocks else (0, "-", 0)
            except CanonPersistError:
                self._reject(
                    503,
                    "launcher_unavailable",
                    "canon history is not persisted: request refused before launch",
                    model_id,
                    model_len,
                )
                return None
            self._instr_truncated = True
            over = _instr_violation(blocks, guard_max)
            if over is not None:
                # Усекать нечего (сам канон больше предела): REQ-003 — отказ до spawn/add.
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

    def _dispatch(
        self, ctx: dict, keepalive, sse_writer: "StreamSink | None" = None
    ) -> dict:
        """Ход через адаптер бэкенда модели; общий разбор `<tool_call>` и итог в формате фасада.

        sse_writer не None только у настоящего живого SSE-хода (_serve_sse): адаптеры, умеющие
        отдавать content/reasoning по мере готовности (сейчас — droid), сами вызывают его из
        своего пути выполнения. Остальные (muse) его просто игнорируют — поведение не меняется.
        """
        managed_turn: ManagedTurn | None = ctx.get("managed_turn") or getattr(
            self, "_active_managed_turn", None
        )
        if ctx.get("attached_existing") and managed_turn is not None:
            eff_fn = getattr(self, "_effective_turn_timeout_s", None)
            eff_to = eff_fn() if callable(eff_fn) else TIMEOUT_S
            managed_turn.done_event.wait(timeout=eff_to)
            if managed_turn.final_dict is not None:
                return dict(managed_turn.final_dict)
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
        transcript = ctx["rpc"]
        turn = TurnContext(
            **{
                key: value
                for key, value in ctx.items()
                if key
                not in (
                    "rpc",
                    "request_id",
                    "subagent_id",
                    "images",
                    "attached_existing",
                    "on_activity",
                    "register_pgid",
                    "cancel_event",
                )
            },
            rpc=Transcript(
                system=transcript["system"],
                runnable=transcript["runnable"],
                items=tuple(TranscriptItem(**item) for item in transcript["items"]),
            ),
            images=tuple(ImageAttachment(**image) for image in ctx["images"]),
            handler=self,
            keepalive=keepalive,
            client_gone=lambda: _client_gone(self.connection),
            on_activity=ctx.get("on_activity")
            or (
                getattr(managed_turn, "touch_activity", None)
                if managed_turn is not None
                else None
            ),
            register_pgid=ctx.get("register_pgid")
            or (
                (
                    lambda pgid: TURN_MANAGER.register_child_pgid(
                        pgid,
                        backend=adapter.id,
                        turn_id=getattr(managed_turn, "turn_id", ""),
                    )
                )
                if managed_turn is not None
                and getattr(managed_turn, "turn_id", None) is not None
                else None
            ),
            cancel_event=ctx.get("cancel_event")
            or (
                getattr(managed_turn, "cancel_event", None)
                if managed_turn is not None
                else None
            ),
        )
        t0 = time.monotonic()
        raw_turn_result = adapter.execute_turn(turn, sse_writer)
        limits = PassthroughLimits.from_env()
        result = finalize_turn(
            raw_turn_result,
            turn.emulate_tools,
            invoke_normalization_enabled=limits.invoke_normalization_enabled,
            repetition_guard_enabled=limits.repetition_guard_enabled,
        )
        if BRIDGE_SANITIZE_TOOL_CALLS:
            calls: list[ToolCall] = []
            by_id: dict[str, list[ToolCall]] = {}
            for call in result.tool_calls:
                cleaned = [
                    replace(item, index=len(calls) + index)
                    for index, item in enumerate(
                        sanitize_tool_call(call, turn.tool_schemas, **_SANITIZE_LIMITS)
                    )
                ]
                by_id[call.id] = cleaned
                calls.extend(cleaned)
            result = replace(
                result,
                tool_calls=tuple(calls),
                events=tuple(
                    item
                    for event in result.events or ()
                    for item in (
                        [replace(event, value=call) for call in by_id[event.value.id]]
                        if event.kind == "tool_call"
                        and isinstance(event.value, ToolCall)
                        else [event]
                    )
                ),
            )
        if managed_turn is not None:
            TURN_MANAGER.complete_turn_from_result(
                managed_turn, result, backend_kind=adapter.kind
            )
        # Только локальный HTTP-буфер: межмодульный seam уже вернул DTO.
        out = {
            "state": result.state,
            "rc": result.rc,
            "text": result.text,
            "reasoning": result.reasoning,
            "err": result.err,
            "usage": asdict(result.usage),
            "result": {},
            "tool_calls": [asdict(call) for call in result.tool_calls],
            "events": [
                (
                    event.kind,
                    asdict(event.value)
                    if not isinstance(event.value, str)
                    else event.value,
                )
                for event in result.events or ()
            ],
            "backend_kind": adapter.kind,
        }
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

    @staticmethod
    def _record_turn_outcome(
        lease: ResilienceLease, out: dict, backend_err: Any, model_id: str = ""
    ) -> None:
        """Явный исход хода CLI-бэкенда: успех — `rc == 0` и нет ошибки бэкенда (ADR-0020 §3.2)."""
        if backend_err is None and out.get("rc") == 0:
            lease.record_success()
            if model_id:
                _PENALTY_TRACKER.record_start_success(model_id)
        elif out.get("state") in _RESILIENCE_NEUTRAL_STATES:
            # Локальная перегрузка/хранилище моста — не вина бэкенда: брейкер не штрафуем.
            lease.record_discard(str(out.get("state")))
        else:
            lease.record_failure()
            if model_id:
                reason = str(
                    out.get("error") or out.get("state") or "rc_non_zero"
                ).strip()[:120]
                _PENALTY_TRACKER.record_start_failure(
                    model_id,
                    reason,
                )

    def _current_lease(self) -> ResilienceLease:
        """Lease текущего запроса; вне `_serve_resilient` (тесты, прямой вызов) — пустой (no-op)."""
        return getattr(self, "_resilience_lease", None) or ResilienceLease("")

    def _serve_resilient(self, backend_id: str, serve: Callable[[], None]) -> None:
        """Допуск по QoS-квоте, брейкеру и отсеку ДО любых заголовков; отказ — честный 503."""
        trace = getattr(self, "_trace", None)
        subagent_id = (
            getattr(trace, "subagent_id", None)
            if trace
            else self.headers.get("x-subagent-id")
        )
        is_interactive = subagent_id is None or str(subagent_id).strip() == ""

        qos_timeout = _env_float("BRIDGE_QUEUE_TIMEOUT_S", QOS_DEFAULT_QUEUE_TIMEOUT_S)
        qos = get_qos_manager(
            max_concurrent=MAX_CONCURRENT,
            reserved_interactive=_env_int_nonneg(
                "BRIDGE_RESERVED_INTERACTIVE_SLOTS",
                RESERVED_INTERACTIVE_SLOTS,
            ),
            queue_timeout_s=qos_timeout,
            keepalive_interval_s=_env_float(
                "BRIDGE_KEEPALIVE_INTERVAL_S", KEEPALIVE_INTERVAL_S
            ),
            drain_event=getattr(LIFECYCLE, "drain_started", None),
            max_queue_size=_env_int_nonneg("BRIDGE_MAX_QUEUE_SIZE", 128),
        )

        headers_sent = [False]
        req = getattr(self, "_parsed_req", None)
        is_stream = bool(isinstance(req, dict) and req.get("stream") is True)

        def _keepalive_cb() -> bool:
            if _client_gone(self.connection):
                return False
            if is_stream:
                try:
                    if not headers_sent[0]:
                        headers_sent[0] = True
                        self._headers_already_sent = True
                        self.send_response(200)
                        self.send_header(
                            "Content-Type", "text/event-stream; charset=utf-8"
                        )
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Connection", "keep-alive")
                        self.send_header("X-Accel-Buffering", "no")
                        self.end_headers()
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    return True
                except Exception:
                    return False
            return True

        queue_started = self._telemetry_queue_start(backend_id)
        qos_ok, qos_reason = qos.acquire_slot(
            is_interactive=is_interactive,
            keepalive_cb=_keepalive_cb if is_stream else None,
            timeout=qos_timeout,
            client_gone_fn=lambda: _client_gone(getattr(self, "connection", None)),
        )
        self._telemetry_queue_done(queue_started)
        if not qos_ok:
            if qos_reason == "client_gone":
                self.close_connection = True
                self._record_telemetry(client_gone=True)
                return
            qos_msg = (
                "bridge is draining for restart"
                if qos_reason == "draining"
                else ("Request queue is full" if qos_reason == "queue_full" else "Queue timeout exceeded waiting for slot")
            )
            if headers_sent[0]:
                self._record_telemetry(status_code=503, error_type="overloaded_error")
                sse_err = format_stream_error_sse(
                    message=qos_msg,
                    model=str((req or {}).get("model") or ""),
                    code=503,
                    error_type="overloaded_error",
                )
                try:
                    self.wfile.write(sse_err.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass
                self.close_connection = True
                return

            self.close_connection = True
            retry_s = _env_int_nonneg("BRIDGE_RETRY_AFTER_S", 3)
            extra_headers = {"Retry-After": str(retry_s)}
            if qos_reason == "draining":
                extra_headers["X-Bridge-Draining"] = "true"
            self._send(
                503,
                {"error": {"message": qos_msg, "type": "overloaded", "code": 503}},
                extra_headers=extra_headers,
            )
            return

        try:
            try:
                lease = RESILIENCE.acquire(backend_id)
            except ResilienceError as exc:
                _log(f"reject reason=resilience code={exc.error_code} backend={backend_id} retry_after={exc.retry_after}")
                self.close_connection = True
                res_msg = f"Backend '{backend_id}' is temporarily unavailable: {exc.reason}"
                if headers_sent[0]:
                    self._record_telemetry(status_code=503, error_type=exc.error_type)
                    sse_err = format_stream_error_sse(
                        message=res_msg,
                        model=str((req or {}).get("model") or ""),
                        code=exc.error_code,
                        error_type=exc.error_type,
                    )
                    try:
                        self.wfile.write(sse_err.encode("utf-8"))
                        self.wfile.flush()
                    except Exception:
                        pass
                    return
                self._send(
                    503,
                    {"error": {"message": res_msg, "type": exc.error_type, "code": exc.error_code, "retry_after": exc.retry_after}},
                    extra_headers={"Retry-After": str(exc.retry_after)},
                )
                return
            self._resilience_lease = lease
            try:
                with lease:
                    try:
                        serve()
                    except (BrokenPipeError, ConnectionResetError):
                        lease.record_discard("client_disconnected")
                        raise
            finally:
                self._resilience_lease = None
        finally:
            qos.release_slot(is_interactive=is_interactive)

    def _serve_passthrough(
        self,
        adapter: PassthroughAdapter,
        raw: bytes,
        req: dict,
        model_id: str,
        _hub_auth_ok: bool = False,
    ) -> None:
        """Passthrough-маршрут: шов пишет ответ клиенту сам (значения заголовков в журнал не идут)."""
        lease = self._current_lease()
        started = time.monotonic()
        self._telemetry_meta(route_mode="passthrough", backend_id=adapter.id, model=model_id)
        _log(f"passthrough route model={model_id} backend={adapter.id} {self._trace_log_fields()}")
        raw, req = _strip_passthrough_env(raw, req)
        headers = {key: value for key, value in self.headers.items()}
        trace_headers = _trace_headers(self._trace)
        if REQUEST_ATTRIBUTION_ENABLED:
            names = {REQUEST_ID_HEADER.lower(), SUBAGENT_ID_HEADER.lower()}
            headers = {
                key: value for key, value in headers.items() if key.lower() not in names
            }
            headers.update(trace_headers)
        if _hub_auth_ok and not getattr(adapter, "_upstream_key", None):
            headers = {
                key: value
                for key, value in headers.items()
                if key.lower()
                not in {"authorization", "x-api-key", "x-turn-owner-token"}
            }
        live_id = new_passthrough_turn_id() if flag_enabled(FLAG_TELEMETRY) else ""
        window = passthrough_window(adapter.limits, self.path, req) if live_id else None
        sink = _HandlerSink(
            self,
            extra_headers=[*trace_headers, ("X-Turn-Id", live_id)]
            if live_id
            else trace_headers,
        )
        try:
            extra = {"window": window} if live_id else {}
            if live_id:
                get_registry().register(live_id, _owner_token_hash(self), window)
            adapter.handle(
                path=self.path,
                raw_body=raw,
                request=req,
                headers=headers,
                sink=sink,
                **extra,
            )
            fleet_models = FLEET.get("models", {}) if isinstance(FLEET, dict) else {}
            canonical_model_id = (
                _resolve_model_alias(model_id, fleet_models)[0]
                if _resolve_model_alias(model_id, fleet_models)
                else model_id
            )
            # Исход фиксируется явно (ADR-0020 §3.2): обрыв клиента нейтрален, 5xx — сбой бэкенда.
            # Таймаут шага (504) и оборванный стрим — тоже нейтральны: это не отказ апстрима.
            error_type = getattr(sink, "error_type", None)
            discard_reason = _passthrough_discard_reason(
                sink.status, error_type() if callable(error_type) else ""
            )
            if sink._client_gone_flag:
                lease.record_discard("client_disconnected")
            elif discard_reason:
                lease.record_discard(discard_reason)
            elif sink.status == 429 or sink.status in (402, 408):
                # 429 / 402 / 408: модель исчерпала квоту/лимит/таймаут старта
                lease.record_success()
                _PENALTY_TRACKER.record_start_failure(
                    canonical_model_id, f"http_{sink.status}"
                )
            elif 200 <= sink.status < 300:
                # 2xx: реальный успешный ответ модели
                lease.record_success()
                _PENALTY_TRACKER.record_start_success(canonical_model_id)
            elif 400 <= sink.status < 500:
                # Клиентские ошибки (400, 401, 403, 404, 422 и т.д.): нейтральны к здоровью модели
                lease.record_success()
            else:
                lease.record_failure()
                _PENALTY_TRACKER.record_start_failure(
                    canonical_model_id, f"http_{sink.status}"
                )
        finally:
            get_registry().finish(live_id)
            self._telemetry_passthrough_done(sink.status)
            _log(f"done route=passthrough status={sink.status} {self._trace_log_fields()} elapsed_ms={int((time.monotonic() - started) * 1000)}")

    def _serve_json(self, ctx: dict) -> None:
        started = time.monotonic()
        self._response_status = 0
        self._telemetry_meta(route_mode="cli", backend_id=ctx.get("backend"), model=ctx.get("model"), stream=False)
        try:
            self._serve_json_body(ctx)
        finally:
            self._record_telemetry()
            _log(f"done route=cli status={self._response_status} {self._trace_log_fields()} elapsed_ms={int((time.monotonic() - started) * 1000)}")

    def _serve_json_body(self, ctx: dict[str, Any]) -> None:
        lease = self._current_lease()
        out = self._dispatch(ctx, None)
        if out.get("state") == "client_gone":
            lease.record_discard("client_disconnected")
            return
        backend_err = self._error_body(out)
        raw_m = str(ctx.get("model") or "")
        fleet_models = FLEET.get("models", {}) if isinstance(FLEET, dict) else {}
        cli_canon_id = (
            _resolve_model_alias(raw_m, fleet_models)[0]
            if _resolve_model_alias(raw_m, fleet_models)
            else raw_m
        )
        self._record_turn_outcome(lease, out, backend_err, model_id=cli_canon_id)
        err = backend_err or self._reserve_delivery(out)
        if err is not None:
            self._send(err["code"], {"error": err})
            return
        usage = out.get("usage") or {}
        self._telemetry_usage(usage)
        wire_usage = _wire_usage(
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
            usage.get("cache_read_tokens"),
        )
        # content и arguments вызовов сериализуются отдельно и вставляются на место меток: большой текст
        # не проходит через дополнительный dict -> dumps -> encode (RW-012).
        marker = "@@content-" + uuid.uuid4().hex + "@@"
        message: dict = {"role": "assistant", "content": marker}
        finish = "stop"
        arg_markers: list = []
        values = [out["text"]]
        reasoning_marker: list[str] = []
        if out.get("reasoning"):
            reasoning_marker = ["@@reasoning-" + uuid.uuid4().hex + "@@"]
            message["reasoning_content"] = reasoning_marker[0]
            values.append(out["reasoning"])
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
                "id": f"{cli_label('completion_prefix')}{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": ctx["model"],
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": wire_usage,
            },
            ensure_ascii=False,
        )
        segments = []
        rest = shell
        for mark in [marker] + reasoning_marker + arg_markers:
            head, rest = rest.split(json.dumps(mark), 1)
            segments.append(head.encode("utf-8"))
        segments.append(rest.encode("utf-8"))
        # Content-Length считается проходом по срезам, тело пишется вторым проходом: целиком
        # экранированная копия текста (до MAX_TURN_TEXT_BYTES) в памяти не строится.
        total = sum(len(seg) for seg in segments) + 2 * len(values)
        for value in values:
            for piece in _text_slices(value):
                total += len(_escape_json_piece(piece))
        self._response_status = 200
        self._telemetry_note(total, first_byte=True)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(total))
        active_turn = getattr(self, "_active_managed_turn", None)
        if active_turn is not None:
            self.send_header("X-Turn-Id", active_turn.turn_id)
        for key, value in _trace_headers(self._trace):
            self.send_header(key, value)
        if self._context_pruned:
            self.send_header(ctxres.PRUNED_HEADER, self._context_pruned)
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
        started = time.monotonic()
        self._response_status = 0
        self._telemetry_meta(route_mode="cli", backend_id=ctx.get("backend"), model=ctx.get("model"), stream=True)
        try:
            self._serve_sse_body(ctx)
        finally:
            self._record_telemetry(client_gone=self._client_write_dead)
            _log(f"done route=cli status={self._response_status} {self._trace_log_fields()} elapsed_ms={int((time.monotonic() - started) * 1000)}")

    def _serve_sse_body(self, ctx: dict[str, Any]) -> None:
        lease = self._current_lease()
        # RW-203: состояние отказа живой записи не наследуется следующим запросом.
        self._client_write_dead = False
        completion_id = f"{cli_label('completion_prefix')}{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        shown_model = ctx["model"]
        managed_turn: ManagedTurn | None = ctx.get("managed_turn") or getattr(
            self, "_active_managed_turn", None
        )
        try:
            self._response_status = 200
            if not getattr(self, "_headers_already_sent", False):
                self._headers_already_sent = True
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Accel-Buffering", "no")
                if managed_turn is not None:
                    self.send_header("X-Turn-Id", managed_turn.turn_id)
                for key, value in _trace_headers(self._trace):
                    self.send_header(key, value)
                if self._context_pruned:
                    self.send_header(ctxres.PRUNED_HEADER, self._context_pruned)
                self.end_headers()
            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError, OSError):
            _log("client gone before headers")
            self._telemetry_gone()
            lease.record_discard("client_disconnected")
            if managed_turn is not None and ctx.get("detach_on_disconnect"):
                TURN_MANAGER.mark_detached(managed_turn.turn_id)
            return

        if ctx.get("attached_existing") and managed_turn is not None:
            from_seq = self._parse_from_seq() or 0
            for frame in TURN_MANAGER.iter_sse_stream(
                managed_turn,
                from_seq=from_seq,
                keepalive_interval_s=min(10.0, KEEPALIVE_S),
                client_gone_fn=lambda: _client_gone(self.connection),
            ):
                if not self._emit(frame):
                    TURN_MANAGER.mark_detached(managed_turn.turn_id)
                    return
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

        live_sent = [
            0
        ]  # RW-211: байты content/reasoning, реально отданные этим запросом
        reasoning_live_chars = 0
        sse_lock = threading.RLock()
        sink_closed = threading.Event()

        def emit(frame: str) -> bool:
            with sse_lock:
                return self._emit(frame)

        def stream_error_frame(message: str, code: str = "live_prefix_invalidated", error_type: str = "stream_error", finish_reason: Any = None) -> str:
            err_chunk = build_stream_error_chunk(
                message=message,
                model=shown_model,
                code=code,
                error_type=error_type,
                finish_reason=finish_reason,
                completion_id=completion_id,
                created=created,
            )
            err_chunk["choices"][0]["delta"] = {}
            return "data: " + json.dumps(err_chunk, ensure_ascii=False) + "\n\n"

        def keepalive() -> bool:
            with sse_lock:
                if sink_closed.is_set():
                    return False
                return write_keepalive()

        def write_keepalive() -> bool:
            # RW-201/RW-009: та же защита, что у sse_writer ниже — запись ограничена
            # LIVE_WRITE_TIMEOUT_S, а не таймаутом соединения (300с), иначе клиент,
            # который просто не читает, держит T/L все 300с на одном keepalive.
            prev_timeout = self.connection.gettimeout()
            try:
                self.connection.settimeout(LIVE_WRITE_TIMEOUT_S)
                return emit(": keepalive\n\n")
            finally:
                self.connection.settimeout(prev_timeout)

        def sse_writer(kind: str, text: str) -> bool:
            with sse_lock:
                if sink_closed.is_set() or self._client_write_dead:
                    return False
                return write_live(kind, text)

        def write_live(kind: str, text: str) -> bool:
            nonlocal reasoning_live_chars
            # AD-002/AD-003: честная живая доставка — content/reasoning_content уходят прямо
            # отсюда, по мере готовности (с коалесацией ~40мс на стороне _execute), а не одним
            # куском после полного хода. Разрыв соединения здесь — тот же сигнал, что у keepalive.
            # RW-009: пишем с коротким таймаутом (не 300с socket-таймаута соединения) — клиент,
            # который не читает SSE (окно забито), не держит T/L всю длину connection timeout;
            # TimeoutError/socket.timeout — подвид OSError, _emit его уже превращает в False.
            field = "content" if kind == "content" else "reasoning_content"
            ok = True
            prev_timeout = self.connection.gettimeout()
            try:
                self.connection.settimeout(LIVE_WRITE_TIMEOUT_S)
                for piece in _text_slices(text) if text else [text]:
                    if not emit(chunk({field: piece})):
                        ok = False
                        break
                    self._telemetry_note(chunk=True)
                    live_sent[0] += len(piece.encode("utf-8"))
                    if kind == "reasoning":
                        reasoning_live_chars += len(piece)
            finally:
                self.connection.settimeout(prev_timeout)
            if not ok:
                # RW-203: отказ фиксируется на Handler — _serve_sse больше не отправит
                # этому клиенту ни одного терминального кадра (включая keepalive).
                self._client_write_dead = True
            return ok

        if not emit(chunk({"role": "assistant", "content": ""})):
            # Пустой стартовый кадр успехом не считается; обрыв клиента нейтрален.
            lease.record_discard("client_disconnected")
            if managed_turn is not None and ctx.get("detach_on_disconnect"):
                self._client_write_dead = True
                TURN_MANAGER.mark_detached(managed_turn.turn_id)
            else:
                return
        try:
            try:
                out = self._dispatch(ctx, keepalive, sse_writer)
            finally:
                # Возврат адаптера закрывает sink под тем же lock, что и записи.
                # Даже consumer, переживший join(5), больше не может дописать кадр.
                with sse_lock:
                    sink_closed.set()
        except Exception as exc:  # noqa: BLE001 - RW-211: клиенту нужен конверт, а не сырой сбой
            if self._client_write_dead:
                _log(f"client_write_dead: dispatch error suppressed err={_err_summary(repr(exc), 160)!r}")
                lease.record_discard("client_disconnected")
                return
            if not live_sent[0]:
                raise
            _log(f"live_dispatch_failed err={_err_summary(repr(exc), 160)!r}")
            lease.record_failure(exc)
            emit(stream_error_frame(str(exc)[:500] or exc.__class__.__name__, finish_reason=None))
            emit("data: [DONE]\n\n")
            return
        if self._client_write_dead:
            # RW-203: сокет отверг живую запись — терминальные кадры (tool_call, stop,
            # usage, error) и [DONE] мёртвому клиенту не отправляются.
            _log("client_write_dead: terminal frames suppressed")
            lease.record_discard("client_disconnected")
            return
        if out.get("state") == "client_gone":
            self._telemetry_gone()
            _log("client gone mid-stream, child killed")
            lease.record_discard("client_disconnected")
            return
        backend_err = self._error_body(out)
        raw_m = str(ctx.get("model") or "")
        fleet_models = FLEET.get("models", {}) if isinstance(FLEET, dict) else {}
        cli_canon_id = (
            _resolve_model_alias(raw_m, fleet_models)[0]
            if _resolve_model_alias(raw_m, fleet_models)
            else raw_m
        )
        self._record_turn_outcome(lease, out, backend_err, model_id=cli_canon_id)
        err = backend_err or self._reserve_delivery(out)
        self._telemetry_error(err)
        if err is None:
            # Доставка — отдельный этап: T/L уже свободны, checkpoint записан; обрыв клиента
            # здесь ни на что, кроме самого ответа, не влияет. У droid content/reasoning уже ушли
            # живьём из _execute (sse_writer выше): здесь остаются только tool_call-кадры.
            live_backend = out.get("backend_kind") == "droid"
            reasoning_to_skip = reasoning_live_chars
            for kind, value in out.get("events") or []:
                if kind in ("content", "reasoning"):
                    if live_backend:
                        continue
                    if kind == "reasoning" and reasoning_to_skip:
                        skipped = min(reasoning_to_skip, len(value))
                        value = value[skipped:]
                        reasoning_to_skip -= skipped
                        if not value:
                            continue
                    field = "content" if kind == "content" else "reasoning_content"
                    # Большое событие выдаётся срезами: в памяти одновременно только один срез SSE-кадра.
                    delivered = (
                        all(
                            emit(chunk({field: piece})) for piece in _text_slices(value)
                        )
                        if value
                        else emit(chunk({field: value}))
                    )
                else:
                    with sse_lock:
                        delivered = self._emit_tool_call(chunk, value)
                if not delivered:
                    _log("client gone during delivery; turn already committed")
                    return
                self._telemetry_note(chunk=True)
            finish = "tool_calls" if out.get("tool_calls") else "stop"
            emit(chunk({}, finish))
            # Harness считает tok/s и % контекста только из usage в потоке
            # (dsh-llm-pi-ai toStreamChunks: usage-chunk -> session usage ->
            # tokenUsage/contextPressure). Без этого чанка метрики пустые.
            # Шлём только при ненулевых токенах, чтобы нулевой usage от droid
            # не превращался в ложные "0 tok/s / 0%".
            out_usage = out.get("usage") or {}
            prompt_toks = out_usage.get("input_tokens", 0)
            compl_toks = out_usage.get("output_tokens", 0)
            self._telemetry_usage(out_usage)
            if prompt_toks or compl_toks:
                emit(
                    "data: "
                    + json.dumps(
                        {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": shown_model,
                            # AD-004/RW-206: finish уже ушёл отдельным кадром выше ТОЛЬКО
                            # для живого Droid-стриминга — там finish_reason здесь null (как
                            # у настоящего OpenAI stream_options.include_usage), а не повтор
                            # "stop"/"tool_calls" на том же кадре. Для остальных бэкендов это
                            # поведение не менялось: finish_reason в usage-кадре повторяет finish.
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {},
                                    "finish_reason": None if live_backend else finish,
                                }
                            ],
                            "usage": _wire_usage(
                                prompt_toks,
                                compl_toks,
                                out_usage.get("cache_read_tokens"),
                            ),
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
        elif err.get("type") == "live_prefix_invalidated" or live_sent[0] > 0:
            fin: Any = None if (err.get("type") == "live_prefix_invalidated" or out.get("backend_kind") == "droid") else ...
            emit(stream_error_frame(str(err["message"]), finish_reason=fin))
        else:
            emit("data: " + json.dumps({"error": err}, ensure_ascii=False) + "\n\n")
        emit("data: [DONE]\n\n")


BridgeHandler = Handler


def is_so_reuseport_enabled() -> bool:
    """Проверяет включение совместного bind через BRIDGE_SO_REUSEPORT_ENABLED."""
    return os.environ.get("BRIDGE_SO_REUSEPORT_ENABLED", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class Server(ThreadingHTTPServer):
    """HTTP-сервер с семафором числа соединений на уровне приёма (C-11)."""

    # ThreadingMixIn отслеживает non-daemon потоки: выход main не обрывает SSE.
    daemon_threads = False
    request_queue_size = 64
    allow_reuse_address = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._listener_close_lock = threading.Lock()
        self._listener_closed = False
        self._connections_lock = threading.Lock()
        self._connections: dict[socket.socket, bool] = {}
        self._closing_connections = False
        super().__init__(*args, **kwargs)
        self._conn_sem = threading.BoundedSemaphore(
            int(FLEET["admission"]["max_http_connections"])
        )

    def server_bind(self) -> None:
        """Разрешает совместный bind до привязки сокета, если ОС поддерживает его."""
        enabled = is_so_reuseport_enabled()
        actual = False
        reason = "disabled" if not enabled else "unsupported"
        if hasattr(socket, "SO_REUSEPORT") and enabled:
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                actual = True
                reason = "enabled"
            except OSError as exc:
                reason = f"error:{exc}"
        _log(f"socket_reuseport configured={enabled} enabled={actual} reason={reason}")
        super().server_bind()

    def set_connection_active(self, request: socket.socket, active: bool) -> bool:
        """Атомарно отделяет обработку HTTP-запроса от ожидания keepalive."""
        with self._connections_lock:
            if self._closing_connections:
                return False
            self._connections[request] = active
            return True

    def close_idle_connections(self) -> None:
        """Будит только idle-читателей; активные ответы завершаются своими потоками."""
        with self._connections_lock:
            self._closing_connections = True
            for request, active in self._connections.items():
                if not active:
                    try:
                        request.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

    def graceful_close_listener(self) -> None:
        """Идемпотентно закрывает только listener, сохраняя принятые соединения."""
        with self._listener_close_lock:
            if self._listener_closed:
                return
            self.socket.close()
            self._listener_closed = True
            release_writer_lock()

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
        with self._connections_lock:
            self._connections[request] = False
        try:
            super().process_request(request, client_address)
        except Exception:
            with self._connections_lock:
                self._connections.pop(request, None)
            self._conn_sem.release()
            self.shutdown_request(request)
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self._connections_lock:
                self._connections.pop(request, None)
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
    global _budget, _ACTIVE_WRITER_LOCK
    if not AUTH_KEY:
        sys.stderr.write(
            "BRIDGE_KEY (or DROID_DSH_BRIDGE_KEY) is required; refusing to start\n"
        )
        raise SystemExit(1)
    _budget = _ByteBudget(int(FLEET["admission"]["max_inflight_body_bytes"]))
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        _ACTIVE_WRITER_LOCK = acquire_writer_lock()
    except OSError as exc:
        # Каталог состояния чужой/недоступен/не 0700: старт отклоняется понятным сообщением, а не трассировкой.
        sys.stderr.write(f"state directory is not usable ({exc}); refusing to start\n")
        raise SystemExit(1)
    if _ACTIVE_WRITER_LOCK is None:
        sys.stderr.write(
            "another bridge instance holds the state writer lock; refusing to start\n"
        )
        raise SystemExit(1)
    _sweep_workspace()
    reconcile_children()
    LIFECYCLE.reap_startup_orphans()
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
    server = Server((HOST, PORT), Handler)
    if _is_drain_enabled():
        LIFECYCLE.install_signal_handlers()
        LIFECYCLE.start_signal_watcher(server)
    else:
        signal.signal(signal.SIGTERM, _kill_all)
        signal.signal(signal.SIGINT, _kill_all)
    _log(
        f"listen {HOST}:{PORT} model={MODEL_ID} max_concurrent={MAX_CONCURRENT} "
        f"queue_timeout={QUEUE_TIMEOUT_S}s timeout={TIMEOUT_S}s keepalive={KEEPALIVE_S}s"
    )
    print(f"[{cli_label('bridge')}] listening on http://{HOST}:{PORT}/v1", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if LIFECYCLE.is_draining():
            LIFECYCLE.drain_completed.wait()


if __name__ == "__main__":
    main()
