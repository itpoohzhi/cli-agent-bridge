"""Хуки телеметрии запросов для HTTP-фасада: миксин обработчика и карта топологии бэкендов.

Агент-агностично: знает про backend_id и маршрут, а не про имя агента. Модуль фасада
(REQUEST_TELEMETRY, BACKENDS, _log) находится по MRO обработчика, поэтому подмена стора в тестах
и запуск `python server.py` (модуль `__main__`) работают одинаково.
"""

from __future__ import annotations

import functools
import json
import math
import os
import sys
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlparse

from core import defaults as D
from core.telemetry_usage import extract_usage, tail_limit
from core.telemetry_util import as_int, as_str, first_truthy, header_value

_USAGE_KEYS = {"prompt_tokens": "input_tokens", "completion_tokens": "output_tokens", "cached_tokens": "cache_read_tokens"}
_MODEL_PLACEHOLDERS = {"unknown": None}


def _pair(value: Any) -> tuple[str, str] | None:
    """Пара (outbound_target, egress_proxy) из JSON-значения; None — значение парой не является."""
    try:
        head, tail = value[0], value[1]
    except (TypeError, KeyError, IndexError):
        return None
    return str(head), str(tail)


@functools.lru_cache(maxsize=8)
def _parse_backend_topology(raw: str) -> dict[str, tuple[str, str]]:
    """JSON-карта backend_id -> (outbound_target, egress_proxy); битые значения игнорируются."""
    try:
        parsed = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    items = parsed.items() if isinstance(parsed, dict) else ()
    pairs = ((str(key), _pair(value)) for key, value in items)
    return {key: pair for key, pair in pairs if pair}


def known_model(model: str) -> str | None:
    """Модель для телеметрии; плейсхолдер «unknown» не записывается."""
    return _MODEL_PLACEHOLDERS.get(model, model)


def http_error_type(status: int) -> str | None:
    """Тип ошибки для ответов 4xx/5xx; None — успешный статус."""
    label = f"http_{status}" if status >= 400 else None
    return label


def telemetry_note(handler: Any, nbytes: int | str = 0, chunk: bool = False, first_byte: bool = False) -> None:
    """Проброс учёта байт из ResponseSink в миксин обработчика (нет миксина — no-op)."""
    note = getattr(handler, "_telemetry_note", None)
    if callable(note):
        note(nbytes, chunk=chunk, first_byte=first_byte)


def telemetry_tail(handler: Any, data: bytes) -> None:
    """Проброс байт ответа passthrough в миксин: хвост нужен для usage (нет миксина — no-op)."""
    tail = getattr(handler, "_telemetry_tail", None)
    if callable(tail):
        tail(data)


def _always_on() -> bool:
    return True


def resolve_backend_topology(backends: Any, backend_id: str, route_mode: str) -> tuple[str, str]:
    """backend_id -> (outbound_target, egress_proxy) для телеметрии; карта настраивается через env."""
    topology = {
        **D.BRIDGE_TELEMETRY_BACKEND_TOPOLOGY,
        **_parse_backend_topology(os.environ.get("BRIDGE_TELEMETRY_BACKEND_TOPOLOGY_JSON", "")),
    }
    known = topology.get(backend_id)
    if known:
        return str(known[0]), str(known[1])
    port = getattr(backends.get(backend_id), "_port", None) if route_mode == "passthrough" else None
    return (f":{port}" if port else f"cli:{backend_id}"), "direct"


def _query_number(qs: dict[str, list[str]], key: str, default: Any, cast: type) -> Any:
    """Числовой параметр запроса: последнее значение; нечисловое, nan/inf и неположительное -> default."""
    try:
        value = cast(first_truthy(qs.get(key), [str(default)])[-1])
    except ValueError:
        return default
    return value if all((math.isfinite(value), value > 0)) else default


def _auth_mode(auth: str) -> str:
    """Режим авторизации запроса для телеметрии: bearer/other/none."""
    mode = "bearer" if auth.lower().startswith("bearer ") else ("other" if auth else "none")
    return mode


class TelemetryHooksMixin:
    """Учёт одного запроса: старт, байты/TTFB/чанки, одна идемпотентная запись в стор."""

    # Атрибуты HTTP-обработчика хоста: объявлены для типизации, реализация — в MRO после миксина.
    headers: Any = None
    command: str = ""
    path: str = ""
    client_address: tuple[str, int] = ("", 0)

    _req_started_mono: float | None = None
    _req_queue_ms = 0.0
    _req_ttfb_ms: float | None = None
    _req_stream_chunks = 0
    _req_recorded = False
    _req_bytes = 0
    _req_meta: dict[str, Any] | None = None
    _req_tail = b""
    _req_tracking = False

    def _send(self, code: int, payload: Any, extra_headers: dict[str, str] | None = None) -> None:
        """Заглушка отправки: рабочая реализация — в HTTP-обработчике хоста."""
        raise NotImplementedError

    def _subagent_id(self) -> str | None:
        """Заглушка атрибуции: рабочая реализация — в HTTP-обработчике хоста."""
        return None

    def _telemetry_srv(self) -> Any:
        """Модуль фасада по MRO обработчика: в нём живут REQUEST_TELEMETRY, BACKENDS, _log."""
        modules = [sys.modules.get(cls.__module__) for cls in type(self).__mro__]
        try:
            return next(mod for mod in modules if hasattr(mod, "REQUEST_TELEMETRY"))
        except StopIteration:
            raise RuntimeError("telemetry facade module not found") from None

    def _telemetry_begin(self) -> None:
        """Старт отсчёта нового запроса (Handler живёт на соединение, не на запрос)."""
        self._req_started_mono = time.monotonic()
        self._req_queue_ms, self._req_ttfb_ms = 0.0, None
        self._req_stream_chunks, self._req_bytes, self._req_recorded = 0, 0, False
        self._req_meta = {"endpoint": self.path.split("?", 1)[0], "route_mode": "rejected"}
        self._req_tail = b""
        self._req_tracking = self._tracking()

    def _tracking(self) -> bool:
        """Собирать ли событие: kill-switch спрашивает ленивый стор; нет фасада/стора — учитываем как раньше."""
        try:
            gate = getattr(self._telemetry_srv().REQUEST_TELEMETRY, "is_enabled", _always_on)
        except (AttributeError, RuntimeError):
            return True
        return bool(gate())

    def _telemetry_note(self, nbytes: int | str = 0, chunk: bool = False, first_byte: bool = False) -> None:
        """Учёт отданных клиенту байт (str — по UTF-8); TTFB фиксируется по первому chunk/first_byte."""
        started = self._req_started_mono
        if started is None:
            return
        self._req_bytes += len(nbytes.encode("utf-8")) if isinstance(nbytes, str) else nbytes
        self._req_stream_chunks += int(chunk)
        if all((any((first_byte, chunk)), self._req_ttfb_ms is None)):
            self._req_ttfb_ms = (time.monotonic() - started) * 1000.0

    def _telemetry_tail(self, data: bytes) -> None:
        """Кольцевой хвост ответа апстрима (tail_limit байт) для разбора usage в passthrough; без буферизации потока."""
        if self._req_tracking:
            self._req_tail = (self._req_tail + data)[-tail_limit():]

    def _telemetry_meta(self, **fields: Any) -> None:
        """Дополнить метаданные запроса; None не затирает уже известное значение."""
        updates = {key: value for key, value in fields.items() if value is not None}
        first_truthy(self._req_meta, default={}).update(updates)

    def _telemetry_meta_request(self, req: Mapping[str, Any]) -> None:
        """Метаданные из тела запроса: режим потока и модель (только строковая)."""
        model = req.get("model")
        self._telemetry_meta(stream=bool(req.get("stream")), model=model if isinstance(model, str) else None)

    def _telemetry_usage(self, usage: dict[str, Any] | None) -> None:
        """Токены из usage-блока ответа бэкенда (input/output/cache_read)."""
        values = first_truthy(usage, default={})
        self._telemetry_meta(**{dst: values.get(src) for dst, src in _USAGE_KEYS.items()})

    def _telemetry_queue_start(self, backend_id: str) -> float:
        self._telemetry_meta(backend_id=backend_id)
        return time.monotonic()

    def _telemetry_queue_done(self, started: float) -> None:
        self._req_queue_ms = (time.monotonic() - started) * 1000.0

    def _telemetry_gone(self) -> None:
        self._telemetry_meta(status_code=499, error_type="client_disconnected")

    def _telemetry_error(self, err: dict[str, Any] | None) -> None:
        """Ошибка бэкенда/доставки: статус >= 400 (иначе 502) и тип ошибки в метаданные."""
        if not err:
            return
        code = err.get("code")
        status = code if isinstance(code, int) else 502
        self._telemetry_meta(status_code=status if status >= 400 else 502, error_type=err.get("type"))

    def _telemetry_error_response(self, code: int, payload: Any, body: bytes) -> None:
        """Ответ-ошибка из _send (отказы до маршрутизации тоже попадают в статистику)."""
        error = payload.get("error") if isinstance(payload, dict) else {}
        error_type = error.get("type") if isinstance(error, dict) else None
        if code >= 400:
            self._telemetry_note(len(body))
            self._record_telemetry(status_code=code, error_type=error_type)

    def _telemetry_passthrough_done(self, status: int) -> None:
        """Финал passthrough-маршрута: usage из хвоста ответа, статус и тип ошибки для 4xx/5xx."""
        self._telemetry_usage(extract_usage(self._req_tail))
        self._record_telemetry(status_code=first_truthy(status, None), error_type=http_error_type(status))

    def _telemetry_serve_get(self) -> None:
        """GET /v1/telemetry: снимок агрегатов за окно (Bearer проверен фасадом до вызова)."""
        store = self._telemetry_srv().REQUEST_TELEMETRY
        qs = parse_qs(urlparse(self.path).query)
        payload = store.get_telemetry_payload(
            window_hours=_query_number(qs, "window_hours", 24.0, float),
            limit=_query_number(qs, "limit", store.recent_limit, int),
        )
        self._send(200, payload)

    def _telemetry_event(self, meta: dict[str, Any], status: int) -> dict[str, Any]:
        """Событие для стора: адрес, атрибуция, топология, латентности, токены и статус."""
        srv, headers, address = self._telemetry_srv(), self.headers, self.client_address
        backend_id, route_mode = as_str(meta.get("backend_id")), as_str(meta.get("route_mode"))
        target, egress = resolve_backend_topology(srv.BACKENDS, backend_id, route_mode) if backend_id else (None, None)
        auth = as_str(header_value(headers, "Authorization"))
        usage = {key: meta.pop(key, None) for key in _USAGE_KEYS}
        usage["total_tokens"] = first_truthy(as_int(usage["prompt_tokens"]) + as_int(usage["completion_tokens"]), None)
        trace = getattr(self, "_trace", None)
        return {
            "request_id": trace.request_id if trace else None,
            "client_ip": address[0],
            "client_port": address[1],
            "user_agent": header_value(headers, "User-Agent"),
            "subagent_id": self._subagent_id(),
            "subagent_role": header_value(headers, srv._bridge_env("SUBAGENT_ROLE_HEADER", "X-Subagent-Role")),
            "auth_mode": _auth_mode(auth),
            "http_method": self.command,
            "outbound_target": target,
            "egress_proxy": egress,
            "queue_ms": self._req_queue_ms,
            "ttfb_ms": self._req_ttfb_ms,
            "total_ms": (time.monotonic() - first_truthy(self._req_started_mono, default=0.0)) * 1000.0,
            "stream_chunks": self._req_stream_chunks,
            "response_bytes": self._req_bytes,
            **meta,
            **usage,
            "status_code": status,
        }

    def _record_telemetry(self, client_gone: bool = False, **fields: Any) -> None:
        """Одна запись на запрос (идемпотентно); неблокирующая, исключения наружу не выходят."""
        if all((self._req_started_mono is not None, not self._req_recorded)):
            self._req_recorded = True
            srv = self._telemetry_srv()
            try:
                self._emit_telemetry(srv, client_gone, fields)
            except Exception as err:  # noqa: BLE001 - телеметрия не должна влиять на ответ
                srv._log(f"telemetry_record_failed err={srv._err_summary(repr(err), 120)!r}")

    def _emit_telemetry(self, srv: Any, client_gone: bool, fields: dict[str, Any]) -> None:
        """Собрать событие из метаданных и контекста исключения и отдать стору (если телеметрия включена)."""
        gone = {"status_code": 499, "error_type": "client_disconnected"} if client_gone else {}
        meta = {**first_truthy(self._req_meta, default={}), **gone, **fields}
        exc = sys.exc_info()[1]
        status = as_int(first_truthy(meta.get("status_code"), getattr(self, "_response_status", 0)))
        if all((exc is not None, not meta.get("error_type"))):
            meta["error_type"] = type(exc).__name__
            status = 499 if isinstance(exc, (BrokenPipeError, ConnectionResetError)) else as_int(first_truthy(status, 500))
        if not status:
            meta["error_type"] = first_truthy(meta.get("error_type"), "client_disconnected")
            status = 499
        if self._req_tracking:
            srv.REQUEST_TELEMETRY.record_request(self._telemetry_event(meta, status))


__all__ = [
    "TelemetryHooksMixin",
    "http_error_type",
    "known_model",
    "resolve_backend_topology",
    "telemetry_note",
    "telemetry_tail",
]
