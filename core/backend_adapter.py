"""Контракт адаптера бэкенда и реестр адаптеров мульти-бинарного хаба (ADR 0002).

Фасад (`server.py`) знает только этот модуль: HTTP, авторизация, `b_guard`, лимиты и
формат ответа остаются в нём, а запуск конкретного консольного бинарника делает адаптер.
Модуль не импортирует ни `server`, ни конкретные адаптеры (зависимость однонаправленная:
`adapters.* -> core.*`). Загрузка адаптеров из конфигурации невозможна по построению:
`kind` из `fleet.json` разрешается только через словарь, заданный в коде
(`adapters.ADAPTER_KINDS`), и передаётся в `AdapterRegistry.from_fleet` вызывающим.
"""

from __future__ import annotations

import re
import threading
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, NamedTuple, Optional, get_type_hints

# Версия контракта: адаптер обязан подтверждать её в qualify() (несовпадение = модели недоступны).
ADAPTER_API = 1

SESSIONS_RESIDENT = "resident"
SESSIONS_NONE = "none"
STREAMING_NATIVE = "native"
STREAMING_EMULATED = "emulated"

StreamSink = Callable[[str, str], bool]
PollCallback = Callable[[], bool]


class Qualification(NamedTuple):
    """Типизированный результат допуска без изменения пары ok/reason."""

    ok: bool
    reason: str


@dataclass(frozen=True)
class Capabilities:
    """Возможности адаптера, проверяемые при регистрации."""

    sessions: str = SESSIONS_NONE
    streaming: str = STREAMING_EMULATED
    autonomy: bool = False
    usage: str = "estimated"


@dataclass(frozen=True)
class TranscriptItem:
    """Один вход истории для неизменённого Droid-пути."""

    role: str
    text: str
    digest: str


@dataclass(frozen=True)
class Transcript:
    """Нормализованная история хода."""

    system: str | None = None
    runnable: bool = True
    items: tuple[TranscriptItem, ...] = ()


@dataclass(frozen=True)
class ImageAttachment:
    """Проверенное вложение хода."""

    name: str
    mime: str
    data: bytes


@dataclass(frozen=True)
class TurnContext:
    """Контекст нового seam; opaque handler нужен лишь legacy-конвертеру Droid."""

    model: str
    effort: str
    prompt: str
    backend: str = ""
    route: str = "nokey"
    key_hash: str = ""
    rpc: Transcript = field(default_factory=Transcript)
    instr: tuple[int, str, int] = (0, "-", 0)
    model_len: int = 0
    effort_source: str = "request"
    autonomy: str = "high"
    autonomy_source: str = "default"
    images: tuple[ImageAttachment, ...] = ()
    cwd: str = ""
    emulate_tools: bool = False
    tag: str = ""
    stream: bool = False
    handler: object | None = None
    keepalive: PollCallback | None = None
    client_gone: PollCallback | None = None


@dataclass(frozen=True)
class Usage:
    """Токены готового ответа."""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ToolFunction:
    """Сериализованные аргументы вызова OpenAI function."""

    name: str
    arguments: str


@dataclass(frozen=True)
class ToolCall:
    """Вызов инструмента в готовом ответе."""

    index: int
    id: str
    function: ToolFunction
    type: str = "function"


@dataclass(frozen=True)
class TurnEvent:
    """Событие доставки: текст или типизированный вызов."""

    kind: str
    value: str | ToolCall


@dataclass(frozen=True)
class TurnResult:
    """Итог адаптера; None events означает необходимость фасадного разбора текста."""

    state: str = "done"
    rc: int = 0
    text: str = ""
    reasoning: str = ""
    usage: Usage = field(default_factory=Usage)
    err: str = ""
    events: tuple[TurnEvent, ...] | None = None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class BackendModel:
    """Представление модели на границе адаптер/реестр/HTTP."""

    id: str
    backend: str
    context_window: int


# ---- schema 3: единая проверка записи `backends[id]` (RW-005) ------------------------
# Ключи записи бэкенда; проверка одна для загрузчика сервера (`_build_backends`) и
# `fleet_check`: обе стороны обязаны принимать ровно одно множество каталогов.
BACKEND_KEYS = frozenset(
    {
        "kind",
        "enabled",
        "required",
        "owned_by",
        "max_concurrent",
        "wrapper",
        "technical_ref",
        "proxy_port",
    }
)
TECHNICAL_REF_KEYS = frozenset({"version", "binary_path", "binary_sha256"})
PROXY_PORT_MIN = 1
PROXY_PORT_MAX = 65535
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
# Виды, для которых pin технического образа обязателен (AD-007): без него `qualify()`
# нечего сверять, и допуск вырождается в «любой файл, который найдёт обёртка».
PIN_REQUIRED_KINDS = frozenset({"muse"})


def backend_entry_error(backend_id: Any, entry: Any, kinds: Mapping[str, Any]) -> str:
    """Причина отказа записи `backends[id]` schema 3 ('' — запись валидна).

    Короткий slug класса I (без пользовательских данных): его пишут в журнал/отчёт и
    сервер, и `fleet_check`. `kinds` — реестр видов, заданный В КОДЕ
    (`adapters.ADAPTER_KINDS`), а не конфигурация.
    """
    if not isinstance(backend_id, str) or not backend_id:
        return "backend_invalid"
    if not isinstance(entry, dict):
        return "backend_invalid"
    if set(entry) - BACKEND_KEYS:
        return "backend_key_unknown"
    kind = entry.get("kind")
    if not isinstance(kind, str) or kind not in kinds:
        return "backend_kind_unknown"
    for flag, default in (("enabled", True), ("required", False)):
        if not isinstance(entry.get(flag, default), bool):
            return "backend_invalid"
    cap = entry.get("max_concurrent", 1)
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        return "backend_max_concurrent_invalid"
    if kind == "muse" and cap != 1:
        return "backend_muse_max_concurrent_invalid"
    owned_by = entry.get("owned_by", backend_id)
    if not isinstance(owned_by, str) or not owned_by:
        return "backend_invalid"
    if "wrapper" in entry and (
        not isinstance(entry["wrapper"], str) or not entry["wrapper"].strip()
    ):
        return "backend_wrapper_invalid"
    if "proxy_port" in entry:
        port = entry["proxy_port"]
        if (
            isinstance(port, bool)
            or not isinstance(port, int)
            or not PROXY_PORT_MIN <= port <= PROXY_PORT_MAX
        ):
            return "backend_proxy_port_invalid"
    if "technical_ref" not in entry:
        return "backend_technical_ref_missing" if kind in PIN_REQUIRED_KINDS else ""
    ref = entry.get("technical_ref")
    if not isinstance(ref, dict) or set(ref) - TECHNICAL_REF_KEYS:
        return "backend_technical_ref_invalid"
    if "version" in ref and not isinstance(ref["version"], str):
        return "backend_technical_ref_invalid"
    path = ref.get("binary_path")
    digest = ref.get("binary_sha256")
    if (
        not isinstance(path, str)
        or not path.strip()
        or not isinstance(digest, str)
        or not _SHA256_HEX.fullmatch(digest)
    ):
        return "backend_technical_ref_incomplete"
    return ""


class FleetViolation(Exception):
    """Структурный отказ общего загрузчика каталога."""

    def __init__(self, reason: str, model: str = "-") -> None:
        super().__init__(reason)
        self.reason = reason
        self.model = model or "-"


FLEET_TOP_KEYS = frozenset(
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
FLEET_MODEL_KEYS = frozenset(
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
EFFORT_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")
IMAGE_STATUSES = ("unsupported", "unverified", "probe", "confirmed")
IMPLEMENTED_METHODS = {"workspace-read": 1}
IMPLICIT_DROID_BACKEND = {
    "kind": "droid",
    "enabled": True,
    "required": True,
    "owned_by": "factory-droid",
    "max_concurrent": 4,
}


def _validate_proof(model_id: str, images: dict, method: str, efforts: list) -> None:
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
    if (
        not proven
        or len(set(proven)) != len(proven)
        or any(p not in efforts for p in proven)
    ):
        raise FleetViolation("confirmed_efforts_proven_invalid", model_id)


def build_catalog(
    data: Any,
    kinds: Mapping[str, Any],
    *,
    env_model: str = "",
    image_probe: bool = False,
) -> dict:
    """Единая полная структурная проверка и нормализация schema 2/3, без I/O."""
    if not isinstance(data, dict):
        raise FleetViolation("fleet_unreadable")
    schema = data.get("schema_version")
    if isinstance(schema, bool) or schema not in (2, 3):
        raise FleetViolation("schema_version_invalid")
    if schema == 2:
        if "backends" in data:
            raise FleetViolation("backends_in_schema_2")
        backends = {"droid": dict(IMPLICIT_DROID_BACKEND)}
    else:
        if set(data) - FLEET_TOP_KEYS:
            raise FleetViolation("fleet_key_unknown")
        raw = data.get("backends")
        if not isinstance(raw, dict) or not raw:
            raise FleetViolation("backends_invalid")
        backends = {}
        for bid, entry in raw.items():
            reason = backend_entry_error(bid, entry, kinds)
            if reason:
                raise FleetViolation(reason, str(bid))
            normalized = dict(entry)
            normalized.update(
                enabled=entry.get("enabled", True),
                required=entry.get("required", False),
                owned_by=entry.get("owned_by") or bid,
                max_concurrent=entry.get("max_concurrent", 1),
            )
            backends[bid] = normalized
        if not any(b["enabled"] for b in backends.values()):
            raise FleetViolation("backends_none_enabled")
    limits = data.get("image_limits")
    if not isinstance(limits, dict):
        raise FleetViolation("limits_invalid")
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
            raise FleetViolation("limits_invalid")
    if (
        not isinstance(limits.get("types"), list)
        or not limits["types"]
        or not all(isinstance(t, str) for t in limits["types"])
    ):
        raise FleetViolation("limits_invalid")
    admission = data.get("admission")
    if not isinstance(admission, dict):
        raise FleetViolation("admission_invalid")
    for key in ("max_http_connections", "max_inflight_body_bytes"):
        if (
            not isinstance(admission.get(key), int)
            or isinstance(admission.get(key), bool)
            or admission[key] <= 0
        ):
            raise FleetViolation("admission_invalid")
    raw_models = data.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        raise FleetViolation("models_invalid")
    models = {}
    order = []
    seen: set = set()
    for item in raw_models:
        if not isinstance(item, dict):
            raise FleetViolation("model_invalid")
        mid = item.get("id")
        if not isinstance(mid, str) or not mid:
            raise FleetViolation("model_invalid")
        if mid in seen:
            raise FleetViolation("duplicate_id", mid)
        seen.add(mid)
        if schema == 3:
            if set(item) - FLEET_MODEL_KEYS:
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
        if not isinstance(images, dict) or images.get("status") not in IMAGE_STATUSES:
            raise FleetViolation("status_invalid", mid)
        status = images["status"]
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
        if status in ("unsupported", "unverified") and (
            images.get("method") is not None or input_types != ["text"]
        ):
            raise FleetViolation("status_inconsistent", mid)
        method = images.get("method")
        if status == "confirmed":
            if method is None:
                raise FleetViolation("confirmed_method_missing", mid)
            if "image" not in input_types or "text" not in input_types:
                raise FleetViolation("confirmed_input_missing", mid)
            _validate_proof(mid, images, method, efforts)
        if status == "probe":
            if (
                method is None
                or "image" not in input_types
                or "text" not in input_types
            ):
                raise FleetViolation("status_inconsistent", mid)
            if not image_probe:
                raise FleetViolation("probe_flag_missing", mid)
        if method is not None and (
            not isinstance(method, str) or method not in IMPLEMENTED_METHODS
        ):
            raise FleetViolation("method_not_implemented", mid)
        if not backends[backend_id]["enabled"]:
            continue
        try:
            window = int(item.get("context_window") or 0)
        except (ValueError, TypeError, OverflowError) as exc:
            raise FleetViolation("context_window_invalid", mid) from exc
        models[mid] = {
            "id": mid,
            "backend": backend_id,
            "name": str(item.get("name") or mid),
            "efforts": [str(e) for e in efforts],
            "default_effort": str(item["default_effort"]),
            "context_window": window,
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
        raise FleetViolation("default_model_invalid")
    if env_model and env_model not in models:
        raise FleetViolation("env_model_invalid", env_model)
    ref = (
        data.get("technical_ref") if isinstance(data.get("technical_ref"), dict) else {}
    )
    return {
        "schema_version": schema,
        "catalogue": str(data.get("catalogue") or ""),
        "default_model": default_model,
        "backends": backends,
        "backend_order": list(backends),
        "order": order,
        "models": models,
        "image_limits": {**limits, "max_types": [t.lower() for t in limits["types"]]},
        "admission": {
            key: int(admission[key])
            for key in ("max_http_connections", "max_inflight_body_bytes")
        },
        "technical_ref": {
            key: str(ref.get(key) or "")
            for key in ("droid_version", "droid_binary_sha256", "droid_binary_path")
        },
    }


class BackendError(Exception):
    """Базовая ошибка бэкенда; `reason` — короткий slug для журнала (без prompt-текста)."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class BackendUnavailable(BackendError):
    """Бэкенд недоступен или не допущен (-> 503 launcher_unavailable)."""


class BackendProtocolError(BackendError):
    """Бэкенд нарушил протокол / вернул пустой ответ (-> 502 proxy_error)."""


class BackendTimeout(BackendError):
    """Ход превысил дедлайн (-> 504, процесс убит)."""


class BackendNotSupported(BackendError):
    """Операция не поддерживается бэкендом (например, spawn_session при sessions=none)."""


class BackendAdapter(ABC):
    """Интерфейс адаптера одного консольного бинарника.

    `config` — запись `backends[<id>]` каталога; `catalog_source` — вызываемый объект,
    отдающий ТЕКУЩИЙ нормализованный каталог (его подменяют стенды тестов), поэтому
    адаптер не копирует список моделей при создании.
    """

    kind: str = ""
    adapter_api: int = ADAPTER_API
    capabilities: Capabilities = Capabilities()

    def __init__(
        self,
        backend_id: str,
        config: Mapping[str, Any],
        catalog_source: Callable[[], Mapping[str, Any]],
        host: Any = None,
    ):
        self.id = backend_id
        self.config = dict(config)
        self._catalog_source = catalog_source
        self.host = host

    # -- общие вспомогательные свойства -------------------------------------------------
    @property
    def owned_by(self) -> str:
        return str(self.config.get("owned_by") or self.id)

    @property
    def required(self) -> bool:
        return bool(self.config.get("required", False))

    @property
    def max_concurrent(self) -> int:
        return int(self.config.get("max_concurrent") or 1)

    def _catalog_models(self) -> list[BackendModel]:
        """Модели каталога, привязанные к этому бэкенду, в порядке fleet.json."""
        catalog = self._catalog_source()
        models = catalog.get("models") or {}
        order = catalog.get("order") or list(models)
        return [
            BackendModel(
                str(models[mid]["id"]),
                str(models[mid]["backend"]),
                int(models[mid].get("context_window") or 0),
            )
            for mid in order
            if mid in models and models[mid].get("backend") == self.id
        ]

    def active_count(self) -> int:
        """Число ходов в работе (для /health); по умолчанию 0."""
        return 0

    def preflight(self) -> Qualification:
        """Дешёвая проверка перед ходом: (ok, reason). По умолчанию — is_healthy()."""
        return (
            Qualification(True, "")
            if self.is_healthy()
            else Qualification(False, "backend_unhealthy")
        )

    # -- контракт -----------------------------------------------------------------------
    @abstractmethod
    def get_models(self) -> list[BackendModel]:
        """Модели бэкенда (записи каталога); чистая функция конфигурации, без spawn."""

    @abstractmethod
    def qualify(self) -> Qualification:
        """Допуск бинарника: (ok, причина-slug). Результат может кэшироваться."""

    @abstractmethod
    def is_healthy(self) -> bool:
        """Дёшево и без spawn: бэкенд способен принять ход."""

    @abstractmethod
    def spawn_session(self, ctx: TurnContext) -> object:
        """Открыть резидентную сессию (sessions=none -> BackendNotSupported)."""

    @abstractmethod
    def execute_turn(
        self, ctx: TurnContext, sse_writer: Optional[StreamSink]
    ) -> TurnResult:
        """Выполнить один ход и вернуть итог.

        `ctx` — типизированный контекст запроса фасада. `sse_writer` — необязательный вызываемый
        `(kind, text)` для бэкендов с нативным потоком; None — вывод удерживается и
        доставляется фасадом. Итог — TurnResult; блоки `<tool_call>`
        адаптер не разбирает: это делает фасад (core.tool_emulation).
        """

    @abstractmethod
    def close_session(self, sid: str) -> None:
        """Закрыть сессию по идентификатору (идемпотентно)."""

    @abstractmethod
    def shutdown(self) -> None:
        """Остановить дочерние процессы адаптера (вызывается при остановке хаба)."""


class AdapterRegistry:
    """Реестр адаптеров хаба: маппинг `backend id -> адаптер` и `model id -> адаптер`."""

    def __init__(self) -> None:
        self._adapters: dict[str, BackendAdapter] = {}
        self._lock = threading.Lock()

    def register(self, adapter: BackendAdapter) -> None:
        caps = adapter.capabilities
        if (
            adapter.adapter_api != ADAPTER_API
            or not isinstance(caps, Capabilities)
            or caps.sessions not in (SESSIONS_NONE, SESSIONS_RESIDENT)
            or caps.streaming not in (STREAMING_NATIVE, STREAMING_EMULATED)
            or not isinstance(caps.autonomy, bool)
            or caps.usage not in ("exact", "estimated")
        ):
            raise ValueError("adapter_contract_capabilities")
        try:
            hints = get_type_hints(adapter.execute_turn)
            qualify_hints = get_type_hints(adapter.qualify)
            inspect.signature(adapter.execute_turn).bind(object(), None)
        except (TypeError, ValueError, NameError) as exc:
            raise ValueError("adapter_contract_signature") from exc
        if (
            hints.get("ctx") is not TurnContext
            or hints.get("return") is not TurnResult
            or qualify_hints.get("return") is not Qualification
        ):
            raise ValueError("adapter_contract_types")
        with self._lock:
            if adapter.id in self._adapters:
                raise ValueError(f"duplicate_backend_id:{adapter.id}")
            self._adapters[adapter.id] = adapter

    @classmethod
    def from_fleet(
        cls,
        catalog: Mapping[str, Any],
        kinds: Mapping[str, Any],
        catalog_source: Callable[[], Mapping[str, Any]],
        host: Any = None,
    ) -> "AdapterRegistry":
        """Создать адаптеры включённых бэкендов каталога (порядок — как в fleet.json).

        `kinds` — словарь `kind -> класс`, заданный В КОДЕ; неизвестный kind — ValueError
        (конфигурация не может подключить произвольный код).
        """
        registry = cls()
        backends = catalog.get("backends") or {}
        for backend_id in catalog.get("backend_order") or list(backends):
            config = backends[backend_id]
            if not config.get("enabled", True):
                continue
            kind = str(config.get("kind") or "")
            factory = kinds.get(kind)
            if factory is None:
                raise ValueError(f"unknown_backend_kind:{kind}")
            registry.register(factory(backend_id, config, catalog_source, host))
        return registry

    # -- доступ -------------------------------------------------------------------------
    def get(self, backend_id: str) -> "BackendAdapter | None":
        return self._adapters.get(backend_id)

    def adapters(self) -> list[BackendAdapter]:
        return list(self._adapters.values())

    def adapter_for_model(self, model_id: str) -> "BackendAdapter | None":
        """Адаптер, обслуживающий модель (по текущему каталогу); None — модели нет."""
        for adapter in self._adapters.values():
            if any(model.id == model_id for model in adapter.get_models()):
                return adapter
        return None

    def models(self) -> list[tuple[BackendAdapter, BackendModel]]:
        """Объединение моделей всех активных адаптеров: [(адаптер, модель)] в порядке реестра."""
        return [(a, m) for a in self._adapters.values() for m in a.get_models()]

    def active_total(self) -> int:
        return sum(a.active_count() for a in self._adapters.values())

    def max_concurrent_total(self) -> int:
        return sum(a.max_concurrent for a in self._adapters.values())

    def shutdown(self, exclude: tuple = ()) -> None:
        """Остановить адаптеры (кроме `exclude` по id); сбой одного не мешает остальным."""
        for adapter in list(self._adapters.values()):
            if adapter.id in exclude:
                continue
            try:
                adapter.shutdown()
            except Exception:  # noqa: BLE001 - остановка best-effort, остальные адаптеры идут дальше
                pass
