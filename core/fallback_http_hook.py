"""HTTP-шов цепочек: заголовки фиксируются только после выбора upstream."""

from __future__ import annotations

import asyncio
import concurrent.futures
import io
import json
import logging
import os
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adapters.passthrough_adapter import ClientGone, iter_sse_events
from core.model_fallback_chain import FallbackCatalog, empty_catalog, load_chains
from core.quota_fallback_dispatch import DispatchPorts, DispatchResponse, FallbackDispatcher, Payload
from core.stream_framing import format_stream_error_sse


_LOG = logging.getLogger(__name__)
_FLAG = "BRIDGE_MODEL_FALLBACK_ENABLED"
_CACHE_LOCK = threading.Lock()
_CACHE: list[Any] = []  # [ключ, каталог] — один элемент, заменяется целиком


def _enabled() -> bool:
    """Kill-switch читается на каждый вызов; по умолчанию хук выключен."""
    return os.environ.get(_FLAG, "false").strip().lower() == "true"


def _chains_path() -> str:
    return os.environ.get(
        "BRIDGE_FALLBACK_CHAINS_PATH", str(Path(__file__).resolve().parents[1] / "fallback_chains.d")
    )


def _cache_key(path: str) -> tuple[Any, ...]:
    """Путь, mtime каталога/файлов и все BRIDGE_FALLBACK_* / BRIDGE_QUOTA_* переменные."""
    directory = Path(path)
    stamps: list[tuple[str, int, int]] = []
    if directory.is_dir():
        stamps.append((".", directory.stat().st_mtime_ns, 0))
        for item in sorted((*directory.glob("*.yaml"), *directory.glob("*.yml"))):
            info = item.stat()
            stamps.append((item.name, info.st_mtime_ns, info.st_size))
    env = tuple(sorted((k, v) for k, v in os.environ.items()
                       if k.startswith(("BRIDGE_FALLBACK_", "BRIDGE_QUOTA_"))))
    return (path, tuple(stamps), env)


def _catalog() -> FallbackCatalog:
    """Кэшированный каталог; битый YAML/env даёт пустой каталог, а не исключение."""
    try:
        path = _chains_path()
        key = _cache_key(path)
        with _CACHE_LOCK:
            if _CACHE and _CACHE[0] == key:
                return _CACHE[1]
        try:
            catalog = load_chains(path)
        except Exception as exc:
            _LOG.warning("fallback chains config is invalid, hook disabled for this config: %s", exc)
            catalog = empty_catalog()
        with _CACHE_LOCK:
            _CACHE[:] = [key, catalog]
        return catalog
    except Exception as exc:
        _LOG.warning("fallback chains catalog unavailable: %s", exc)
        return empty_catalog()


def append_models(cards: list[dict[str, Any]], scope: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    """Публикует алиасы только при BRIDGE_MODEL_FALLBACK_ENABLED=true.

    Kill-switch выключен (по умолчанию) — ``cards`` возвращается без изменений и без
    обращения к каталогу; провайдер-scoped каталог не расширяется никогда.
    """
    if not _enabled() or scope is not None:
        return cards
    listed = {card["id"] for card in cards}
    return cards + [
        {"id": alias, "object": "model", "created": 0, "owned_by": "bridge",
         "context_window": chain.declared_context_window,
         "context_length": chain.declared_context_window}
        for alias, chain in _catalog().chains.items() if alias not in listed
    ]


@dataclass
class _Pipe:
    """Ограниченный канал с backpressure и отменой транспорта при закрытии."""

    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[bytes | BaseException | None]
    limits: Any
    presend_deadline: float | None
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    cancelled: threading.Event = field(default_factory=threading.Event)
    status: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    pending: bytes = b""
    task: asyncio.Task[None] | None = None

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        self.status, self.headers = status, dict(headers)
        self.loop.call_soon_threadsafe(self.ready.set)
    def client_gone(self) -> bool:
        return self.cancelled.is_set()
    def write(self, data: bytes | BaseException | None) -> None:
        future = asyncio.run_coroutine_threadsafe(self.queue.put(data), self.loop)
        try:
            while not self.cancelled.is_set():
                try:
                    future.result(timeout=self.limits.poll_interval_s)
                    return
                except concurrent.futures.TimeoutError:
                    continue
            raise ClientGone()
        finally:
            future.cancel()
    def run(self, call: Callable[[], None]) -> None:
        try:
            call()
        except BaseException as exc:
            if not self.client_gone():
                self.write(exc)
        finally:
            self.loop.call_soon_threadsafe(self.ready.set)
            if not self.client_gone():
                self.write(None)
    async def read(self) -> bytes:
        data = await self.queue.get()
        if isinstance(data, BaseException):
            raise data
        if data is None:
            raise StopAsyncIteration
        return data
    def __aiter__(self) -> _Pipe:
        return self
    async def __anext__(self) -> Payload:
        while True:
            parts = re.split(br"\r?\n\r?\n", self.pending, maxsplit=1)
            if len(parts) == 1:
                self.pending += await self.read()
                if len(self.pending) > self.limits.max_body_bytes:
                    raise OSError("upstream SSE event exceeds the bridge limit")
                continue
            frame, self.pending = parts
            for _, data in iter_sse_events(io.BytesIO(frame + b"\n\n").readline, self.limits.max_body_bytes):
                if data == "[DONE]":
                    raise StopAsyncIteration
                if data is not None:
                    try:
                        chunk = json.loads(data)
                    except ValueError as exc:
                        raise OSError("invalid upstream SSE payload") from exc
                    if not isinstance(chunk, dict):
                        raise OSError("upstream SSE payload must be an object")
                    return chunk
    async def aclose(self) -> None:
        self.cancelled.set()
        if self.task is not None:
            try:
                await asyncio.shield(self.task)
            except ClientGone:
                pass

async def _response(pipe: _Pipe) -> DispatchResponse:
    await pipe.ready.wait()
    sse = any(k.lower() == "content-type" and "text/event-stream" in v.lower()
              for k, v in pipe.headers.items())
    if sse and 200 <= pipe.status < 300:
        return DispatchResponse(status_code=pipe.status, headers=pipe.headers, stream=pipe)
    body = bytearray()
    try:
        while True:
            body.extend(await pipe.read())
            if len(body) > pipe.limits.max_body_bytes:
                raise OSError("upstream body exceeds the bridge limit")
    except StopAsyncIteration:
        try:
            payload = json.loads(body) if body else {}
        except ValueError as exc:
            if pipe.status < 400:
                raise OSError("invalid upstream JSON payload") from exc
            payload = {}
        return DispatchResponse(status_code=pipe.status, headers=pipe.headers,
                                payload=payload if isinstance(payload, dict) else {}, body=bytes(body))


def _adapter(host: Any, handler: Any, request: Payload, scope: str | None) -> Any:
    model = str(request["model"])
    adapter = host.BACKENDS.adapter_for_model(model)
    if adapter is None or not callable(getattr(adapter, "handle", None)):
        raise OSError("fallback candidate has no HTTP transport")
    owner = host.PROVIDER_SCOPES.get(scope) if scope is not None else None
    if owner is not None and adapter.owned_by not in ((owner,) if isinstance(owner, str) else owner):
        raise PermissionError("fallback candidate is outside provider scope")
    key = getattr(host, "_INTERNAL_SERVICE_KEY", "") or os.environ.get("INTERNAL_SERVICE_KEY", "")
    if key and model in host.INTERNAL_MODEL_IDS:
        import hmac
        if not hmac.compare_digest(handler.headers.get("X-Internal-Service-Key", ""), key):
            raise PermissionError("fallback candidate is reserved")
    bypass = handler.headers.get("X-Bypass-Model-Filter") == "1"
    if (not bypass and host._MODEL_NOTES_FILTER.is_blocked(model)) or host._PENALTY_TRACKER.get_model_status(model)["is_penalized"]:
        raise OSError("fallback candidate is temporarily blocked")
    if host._quarantine_denial(model, handler.headers.get("X-Subagent-Id")) is not None:
        raise PermissionError("fallback candidate is quarantined")
    return adapter

async def _serve(handler: Any, request: Payload, host: Any, upstream: Callable[..., None], scope: str | None) -> None:
    async def send(candidate: Payload, timeout: float | None) -> DispatchResponse:
        adapter = _adapter(host, handler, candidate, scope)
        candidate = dict(candidate)
        request_model = str(candidate["model"])
        idempotency_key = (handler.headers.get("X-Idempotency-Key") or "").strip()
        if idempotency_key:
            candidate["step_job_id"] = idempotency_key
        candidate["model"] = host.resolve_target_model(host.FLEET["models"][candidate["model"]], candidate["model"])
        _, candidate = host._strip_passthrough_env(json.dumps(candidate).encode("utf-8"), candidate)
        loop = asyncio.get_running_loop()
        pipe = _Pipe(loop, asyncio.Queue(maxsize=adapter.limits.read_queue_max_entries), adapter.limits,
                     None if timeout is None else loop.time() + timeout)
        pipe.task = asyncio.create_task(asyncio.to_thread(pipe.run, lambda: upstream(adapter, candidate, pipe)))
        try:
            response = await _response(pipe)
            if response.stream is None:
                await pipe.aclose()
            if 200 <= response.status_code < 300:
                mark = getattr(host._PENALTY_TRACKER, "record_start_success", None) or getattr(
                    host._PENALTY_TRACKER, "record_success", None)
                if callable(mark):
                    mark(str(request_model))
            return response
        except BaseException:
            await pipe.aclose()
            raise
    ports = DispatchPorts(send=send, breaker=host._QUOTA_CB_CACHE,
                          record_start_failure=host._PENALTY_TRACKER.record_start_failure)
    response = await FallbackDispatcher(_catalog(), ports).dispatch(request)
    headers = {k: v for k, v in response.headers.items()
               if k.lower() not in {"content-length", "transfer-encoding", "connection", "content-type"}}
    sink = host._HandlerSink(handler, extra_headers=host._trace_headers(handler._trace))
    if response.stream is None:
        body = json.dumps(dict(response.payload), ensure_ascii=False).encode("utf-8") if response.status_code < 400 else response.body or json.dumps(dict(response.payload)).encode("utf-8")
        content_type = next((v for k, v in response.headers.items() if k.lower() == "content-type"), "application/json")
        sink.start(response.status_code, [*headers.items(), ("Content-Type", content_type), ("Content-Length", str(len(body)))])
        sink.write(body)
        return
    try:
        sink.start(response.status_code, [*headers.items(), ("Content-Type", "text/event-stream"),
                                         ("Cache-Control", "no-cache")])
        try:
            async for chunk in response.stream:
                sink.write(("data: " + json.dumps(dict(chunk), ensure_ascii=False) + "\n\n").encode("utf-8"))
        except (OSError, ValueError):
            sink.write(format_stream_error_sse(message="upstream stream failed", model=str(request["model"])).encode("utf-8"))
            return
        sink.write(b"data: [DONE]\n\n")
    finally:
        await response.stream.aclose()

def dispatch(handler: Any, request: Mapping[str, Any], host: Any, upstream: Callable[..., None], scope: str | None = None) -> bool:
    """True означает полностью обработанный алиас; прямые модели не затрагиваются."""
    if not _enabled():
        return False
    model = request.get("model")
    if not isinstance(model, str) or model.strip() not in _catalog().chains:
        return False
    if not host._auth_ok(handler):
        handler._reply_error(401, "Unauthorized", "authentication_error")
        return True
    try:
        asyncio.run(_serve(handler, {**request, "model": model.strip()}, host, upstream, scope))
    except ClientGone:
        pass
    except PermissionError:
        handler._reply_error(403, "Fallback candidate is not permitted", "permission_error")
    except (OSError, ValueError):
        handler._reply_error(502, "Fallback upstream failed", "upstream_error")
    return True
