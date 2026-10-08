"""Контракт адаптера бэкенда и реестр адаптеров мульти-бинарного хаба (ADR 0002).

Фасад (`server.py`) знает только этот модуль: HTTP, авторизация, `b_guard`, лимиты и
формат ответа остаются в нём, а запуск конкретного консольного бинарника делает адаптер.
Модуль не импортирует ни `server`, ни конкретные адаптеры (зависимость однонаправленная:
`adapters.* -> core.*`). Загрузка адаптеров из конфигурации невозможна по построению:
`kind` из `fleet.json` разрешается только через словарь, заданный в коде
(`adapters.ADAPTER_KINDS`), и передаётся в `AdapterRegistry.from_fleet` вызывающим.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Mapping

# Версия контракта: адаптер обязан подтверждать её в qualify() (несовпадение = модели недоступны).
ADAPTER_API = 1

SESSIONS_RESIDENT = "resident"
SESSIONS_NONE = "none"
STREAMING_NATIVE = "native"
STREAMING_EMULATED = "emulated"


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
    capabilities: dict = {
        "sessions": SESSIONS_NONE,
        "streaming": STREAMING_EMULATED,
        "autonomy": False,
        "usage": "estimated",
    }

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

    def _catalog_models(self) -> list:
        """Модели каталога, привязанные к этому бэкенду, в порядке fleet.json."""
        catalog = self._catalog_source()
        models = catalog.get("models") or {}
        order = catalog.get("order") or list(models)
        return [
            models[mid]
            for mid in order
            if mid in models and models[mid].get("backend") == self.id
        ]

    def active_count(self) -> int:
        """Число ходов в работе (для /health); по умолчанию 0."""
        return 0

    def preflight(self) -> tuple:
        """Дешёвая проверка перед ходом: (ok, reason). По умолчанию — is_healthy()."""
        return (True, "") if self.is_healthy() else (False, "backend_unhealthy")

    # -- контракт -----------------------------------------------------------------------
    @abstractmethod
    def get_models(self) -> list:
        """Модели бэкенда (записи каталога); чистая функция конфигурации, без spawn."""

    @abstractmethod
    def qualify(self) -> tuple:
        """Допуск бинарника: (ok, причина-slug). Результат может кэшироваться."""

    @abstractmethod
    def is_healthy(self) -> bool:
        """Дёшево и без spawn: бэкенд способен принять ход."""

    @abstractmethod
    def spawn_session(self, ctx: dict) -> Any:
        """Открыть резидентную сессию (sessions=none -> BackendNotSupported)."""

    @abstractmethod
    def execute_turn(self, ctx: dict, sse_writer: Any) -> dict:
        """Выполнить один ход и вернуть итог.

        `ctx` — контекст запроса фасада (model, effort, prompt, cwd, emulate_tools, tag,
        client_gone, keepalive и т.д.). `sse_writer` — необязательный вызываемый
        `(kind, text)` для бэкендов с нативным потоком; None — вывод удерживается и
        доставляется фасадом. Итог — словарь с ключами `state`, `rc`, `text`, `usage`, `err`
        (+ необязательные `reasoning`, `events`, `tool_calls`); блоки `<tool_call>`
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
        self._adapters: dict = {}
        self._lock = threading.Lock()

    def register(self, adapter: BackendAdapter) -> None:
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

    def adapters(self) -> list:
        return list(self._adapters.values())

    def adapter_for_model(self, model_id: str) -> "BackendAdapter | None":
        """Адаптер, обслуживающий модель (по текущему каталогу); None — модели нет."""
        for adapter in self._adapters.values():
            if any(model.get("id") == model_id for model in adapter.get_models()):
                return adapter
        return None

    def models(self) -> list:
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
