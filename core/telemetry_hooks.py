"""Хуки телеметрии запросов для HTTP-фасада: миксин обработчика и карта топологии бэкендов.

Агент-агностично: знает про backend_id и маршрут, а не про имя агента. Модуль фасада
(REQUEST_TELEMETRY, BACKENDS, _log) находится по MRO обработчика, поэтому подмена стора в тестах
и запуск `python server.py` (модуль `__main__`) работают одинаково.
"""

from __future__ import annotations

import functools
import json
import os
import sys
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from core import defaults as D

_USAGE_KEYS = {"prompt_tokens": "input_tokens", "completion_tokens": "output_tokens", "cached_tokens": "cache_read_tokens"}


@functools.lru_cache(maxsize=8)
def _parse_backend_topology(raw: str) -> dict[str, tuple[str, str]]:
    try:
        parsed = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    return {
        str(key): (str(val[0]), str(val[1]))
        for key, val in (parsed.items() if isinstance(parsed, dict) else ())
        if isinstance(val, (list, tuple)) and len(val) >= 2
    }


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
    try:
        return cast((qs.get(key) or [str(default)])[-1])
    except ValueError:
        return default


class TelemetryHooksMixin:
    """Учёт одного запроса: старт, байты/TTFB/чанки, одна идемпотентная запись в стор."""

    # Атрибуты HTTP-обработчика хоста: объявлены для типизации, реализация — в MRO после миксина.
    headers: Any
    command: str
    path: str
    client_address: tuple[str, int]

    _req_started_mono: float | None = None
    _req_queue_ms = 0.0
    _req_ttfb_ms: float | None = None
    _req_stream_chunks = 0
    _req_recorded = False
    _req_bytes = 0
    _req_meta: dict[str, Any] | None = None

    def _telemetry_srv(self) -> Any:
        for cls in type(self).__mro__:
            mod = sys.modules.get(cls.__module__)
            if mod is not None and hasattr(mod, "REQUEST_TELEMETRY"):
                return mod
        raise RuntimeError("telemetry facade module not found")

    def _telemetry_begin(self) -> None:
        """Старт отсчёта нового запроса (Handler живёт на соединение, не на запрос)."""
        self._req_started_mono = time.monotonic()
        self._req_queue_ms, self._req_ttfb_ms = 0.0, None
        self._req_stream_chunks, self._req_bytes, self._req_recorded = 0, 0, False
        self._req_meta = {"endpoint": self.path.split("?", 1)[0], "route_mode": "rejected"}

    def _telemetry_note(self, nbytes: int | str = 0, chunk: bool = False, first_byte: bool = False) -> None:
        """Учёт отданных клиенту байт (str — по UTF-8); TTFB фиксируется по первому chunk/first_byte."""
        if self._req_started_mono is None:
            return
        self._req_bytes += len(nbytes.encode("utf-8")) if isinstance(nbytes, str) else nbytes
        if chunk:
            self._req_stream_chunks += 1
        if (chunk or first_byte) and self._req_ttfb_ms is None:
            self._req_ttfb_ms = (time.monotonic() - self._req_started_mono) * 1000.0

    def _telemetry_meta(self, **fields: Any) -> None:
        """Дополнить метаданные запроса; None не затирает уже известное значение."""
        if self._req_started_mono is not None and self._req_meta is not None:
            self._req_meta.update({k: v for k, v in fields.items() if v is not None})

    def _telemetry_usage(self, usage: dict[str, Any] | None) -> None:
        usage = usage or {}
        self._telemetry_meta(**{dst: usage.get(src) for dst, src in _USAGE_KEYS.items()})

    def _telemetry_queue_start(self, backend_id: str) -> float:
        self._telemetry_meta(backend_id=backend_id)
        return time.monotonic()

    def _telemetry_queue_done(self, started: float) -> None:
        self._req_queue_ms = (time.monotonic() - started) * 1000.0

    def _telemetry_gone(self) -> None:
        self._telemetry_meta(status_code=499, error_type="client_disconnected")

    def _telemetry_error(self, err: dict[str, Any] | None) -> None:
        """Ошибка бэкенда/доставки: статус >= 400 (иначе 502) и тип ошибки в метаданные."""
        if err is None:
            return
        code = err.get("code")
        self._telemetry_meta(status_code=code if isinstance(code, int) and code >= 400 else 502, error_type=err.get("type"))

    def _telemetry_error_response(self, code: int, payload: Any, body: bytes) -> None:
        """Ответ-ошибка из _send (отказы до маршрутизации тоже попадают в статистику)."""
        if code < 400 or self._req_started_mono is None:
            return
        error = payload.get("error") if isinstance(payload, dict) else None
        self._telemetry_note(len(body))
        self._record_telemetry(status_code=code, error_type=error.get("type") if isinstance(error, dict) else None)

    def _telemetry_serve_get(self) -> None:
        store = self._telemetry_srv().REQUEST_TELEMETRY
        qs = parse_qs(urlparse(self.path).query)
        payload = store.get_telemetry_payload(
            window_hours=_query_number(qs, "window_hours", 24.0, float),
            limit=_query_number(qs, "limit", store.recent_limit, int),
        )
        self._send(200, payload)  # type: ignore[attr-defined] - реализация в обработчике хоста

    def _telemetry_event(self, meta: dict[str, Any], status: int) -> dict[str, Any]:
        srv, hdrs = self._telemetry_srv(), getattr(self, "headers", None)
        backend_id, route_mode = str(meta.get("backend_id") or ""), str(meta.get("route_mode") or "")
        target, egress = resolve_backend_topology(srv.BACKENDS, backend_id, route_mode) if backend_id else (None, None)
        auth = hdrs.get("Authorization", "") if hdrs else ""
        usage = {k: meta.pop(k, None) for k in _USAGE_KEYS}
        usage["total_tokens"] = (usage["prompt_tokens"] or 0) + (usage["completion_tokens"] or 0) or None
        trace = getattr(self, "_trace", None)
        role_header = srv._bridge_env("SUBAGENT_ROLE_HEADER", "X-Subagent-Role")
        return {
            "request_id": trace.request_id if trace else None,
            "client_ip": self.client_address[0],
            "client_port": self.client_address[1],
            "user_agent": hdrs.get("User-Agent") if hdrs else None,
            "subagent_id": self._subagent_id(),  # type: ignore[attr-defined] - реализация в обработчике хоста
            "subagent_role": hdrs.get(role_header) if hdrs else None,
            "auth_mode": "bearer" if auth.lower().startswith("bearer ") else ("none" if not auth else "other"),
            "http_method": self.command,
            "outbound_target": target,
            "egress_proxy": egress,
            "queue_ms": self._req_queue_ms,
            "ttfb_ms": self._req_ttfb_ms,
            "total_ms": (time.monotonic() - (self._req_started_mono or 0.0)) * 1000.0,
            "stream_chunks": self._req_stream_chunks,
            "response_bytes": self._req_bytes,
            **meta,
            **usage,
            "status_code": status,
        }

    def _record_telemetry(self, client_gone: bool = False, **fields: Any) -> None:
        """Одна запись на запрос (идемпотентно); неблокирующая, исключения наружу не выходят."""
        if self._req_started_mono is None or self._req_recorded:
            return
        self._req_recorded = True
        srv = self._telemetry_srv()
        try:
            gone = {"status_code": 499, "error_type": "client_disconnected"} if client_gone else {}
            meta = {**(self._req_meta or {}), **gone, **fields}
            exc = sys.exc_info()[1]
            status = int(meta.get("status_code") or getattr(self, "_response_status", 0) or 0)
            if exc is not None and not meta.get("error_type"):
                meta["error_type"] = type(exc).__name__
                status = 499 if isinstance(exc, (BrokenPipeError, ConnectionResetError)) else (status or 500)
            if not status:
                status, meta["error_type"] = 499, meta.get("error_type") or "client_disconnected"
            srv.REQUEST_TELEMETRY.record_request(self._telemetry_event(meta, status))
        except Exception as err:  # noqa: BLE001 - телеметрия не должна влиять на ответ
            srv._log(f"telemetry_record_failed err={srv._err_summary(repr(err), 120)!r}")
