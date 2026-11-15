"""Агент-агностичный выбор модели до первого байта, без собственного кэша квот.

Транспорт возвращает разобранные JSON-чанки и обязан освобождать ресурсы при
отмене send/aclose. HTTP-фасад отправляет заголовки только после dispatch,
закрывает возвращённый stream при отключении клиента и сам кодирует SSE.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Protocol

from core.model_fallback_chain import (
    FallbackCandidate,
    FallbackCatalog,
    FallbackChain,
    QuotaBreakerPort,
    candidate_blocked,
    scope_key,
)
from core.quota_classifier import QuotaClassification, QuotaRules, classify_429

Payload = Mapping[str, object]


class ChunkStream(Protocol):
    """Разобранный поток с явным освобождением ресурсов, в том числе до чтения."""

    def __aiter__(self) -> ChunkStream: ...
    async def __anext__(self) -> Payload: ...
    async def aclose(self) -> None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class DispatchResponse:
    """Независимый от HTTP-фреймворка ответ; body сохраняет сырое тело ошибки."""

    status_code: int
    payload: Payload = field(default_factory=dict[str, object])
    headers: Mapping[str, str] = field(default_factory=dict[str, str])
    stream: ChunkStream | None = None
    body: bytes = b""


@dataclass(frozen=True, slots=True, kw_only=True)
class DispatchPorts:
    """Внедряемые транспорт, единый breaker, штрафы и монотонные часы."""

    send: Callable[[Payload, float | None], Awaitable[DispatchResponse]]
    breaker: QuotaBreakerPort
    record_start_failure: Callable[[str, str], object]
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    monotonic: Callable[[], float] = time.monotonic


@dataclass(slots=True)
class _ModelStream:
    source: ChunkStream
    model: str
    first: Payload | None = None

    def __aiter__(self) -> _ModelStream:
        return self

    async def __anext__(self) -> Payload:
        try:
            chunk = self.first
            self.first = None
            if chunk is None:
                chunk = await anext(self.source)
            return {**chunk, "model": self.model}
        except BaseException:
            await self.aclose()
            raise

    async def aclose(self) -> None:
        self.first = None
        await self.source.aclose()


@dataclass(frozen=True, slots=True)
class _Ready:
    response: DispatchResponse
    first: Payload | None = None


@dataclass(slots=True)
class _Run:
    alias: str
    chain: FallbackChain
    deadline: float
    attempts: list[tuple[str, str]] = field(default_factory=list)
    retry_at: list[float] = field(default_factory=list)


def _present(ready: _Ready, public_model: str, model: str, count: int) -> DispatchResponse:
    response = ready.response
    headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in {"x-bridge-fallback-model", "x-bridge-fallback-attempts"}
    }
    headers.update({"x-bridge-fallback-model": model, "x-bridge-fallback-attempts": str(count)})
    success = 200 <= response.status_code < 300
    return replace(
        response,
        headers=headers,
        payload={**response.payload, "model": public_model} if success else response.payload,
        stream=_ModelStream(response.stream, public_model, ready.first)
        if response.stream is not None and success
        else response.stream,
    )


@dataclass(slots=True)
class FallbackDispatcher:
    """Dispatch принимает исходный запрос; send не должен писать байты клиенту."""

    catalog: FallbackCatalog
    ports: DispatchPorts
    env: Mapping[str, str] | None = None

    async def dispatch(self, request: Payload) -> DispatchResponse:
        """Раскрывает алиас; флаг перечитывается на каждом входе, по умолчанию false."""
        alias = request.get("model")
        if not isinstance(alias, str):
            raise ValueError("model must be a string")
        env = os.environ if self.env is None else self.env
        enabled = env.get("BRIDGE_MODEL_FALLBACK_ENABLED", "false").strip().lower() == "true"
        chain = self.catalog.chains.get(alias)
        if not enabled or chain is None:
            return await self._direct(request, chain)
        rules = QuotaRules.from_config(self.catalog.quota_rules, env=env)
        run = _Run(alias, chain, self.ports.monotonic() + self.catalog.total_budget_s)
        for candidate in chain.candidates:
            if candidate_blocked(self.ports.breaker, candidate):
                run.attempts.append((candidate.model, "blocked"))
        for candidate in self.catalog.select_candidates(alias, request, self.ports.breaker):
            if self.ports.monotonic() >= run.deadline:
                break
            response = await self._candidate({**request, "model": candidate.model}, run, rules)
            if response is not None:
                return response
        return self._exhausted(run, rules)

    async def _direct(self, request: Payload, chain: FallbackChain | None) -> DispatchResponse:
        model = chain.disabled_target if chain else str(request["model"])
        response = await self.ports.send({**request, "model": model}, None)
        if response.status_code in (402, 408, 429) or response.status_code >= 500:
            _ = self.ports.record_start_failure(model, f"http_{response.status_code}")
        if chain is None:
            return response
        public = str(request["model"]) if chain.preserve_alias_in_response else model
        return _present(_Ready(response), public, model, 1)

    async def _open(self, request: Payload, timeout: float) -> _Ready:
        response = await self.ports.send(request, timeout)
        if response.stream is None or not 200 <= response.status_code < 300:
            return _Ready(response)
        try:
            first = await anext(response.stream)
        except BaseException as exc:
            await response.stream.aclose()
            if isinstance(exc, StopAsyncIteration):
                raise OSError("empty upstream stream") from None
            raise
        return _Ready(response, first)

    async def _attempt(self, request: Payload, run: _Run) -> _Ready | None:
        remaining = run.deadline - self.ports.monotonic()
        if remaining <= 0:
            return None
        model = str(request["model"])
        timeout = min(remaining, self.catalog.attempt_first_byte_timeout_s)
        try:
            ready = await asyncio.wait_for(self._open(request, timeout), timeout)
        except PermissionError:
            # Кандидат запрещён политикой (scope/quarantine/ключ): штраф не пишем, идём дальше.
            run.attempts.append((model, "permission_denied"))
            return None
        except (TimeoutError, OSError) as exc:
            reason = (
                "first_byte_timeout" if isinstance(exc, TimeoutError) else "pre_first_byte_failure"
            )
            run.attempts.append((model, reason))
            _ = self.ports.record_start_failure(model, reason)
            return None
        status = ready.response.status_code
        if status != 429:
            run.attempts.append((model, "ok" if 200 <= status < 300 else f"http_{status}"))
        if status in (402, 408) or status >= 500:
            _ = self.ports.record_start_failure(model, f"http_{status}")
            if ready.response.stream is not None:
                await ready.response.stream.aclose()
            return None
        return ready

    def _quota(
        self, response: DispatchResponse, run: _Run, rules: QuotaRules, model: str
    ) -> QuotaClassification:
        body = response.body or json.dumps(response.payload, ensure_ascii=False).encode("utf-8")
        decision = classify_429(response.headers, body, rules)
        reason = "429_quota" if decision.is_quota else "http_429"
        run.attempts.append((model, reason))
        if decision.is_quota:
            self.ports.breaker.record_429(model, ttl_s=decision.reset_s, reason=reason)
            scope = scope_key(self._candidate_meta(run, model))
            if scope:
                self.ports.breaker.record_429(scope, ttl_s=decision.reset_s, reason=reason)
            run.retry_at.append(self.ports.monotonic() + decision.reset_s)
        else:
            _ = self.ports.record_start_failure(model, reason)
            if decision.retry_after_s is not None:
                run.retry_at.append(self.ports.monotonic() + decision.retry_after_s)
        return decision

    @staticmethod
    def _candidate_meta(run: _Run, model: str) -> FallbackCandidate:
        return next(c for c in run.chain.candidates if c.model == model)

    async def _candidate(
        self, request: Payload, run: _Run, rules: QuotaRules
    ) -> DispatchResponse | None:
        model = str(request["model"])
        meta = self._candidate_meta(run, model)
        for retried in (False, True):
            if candidate_blocked(self.ports.breaker, meta):
                return None
            ready = await self._attempt(request, run)
            if ready is None:
                return None
            if ready.response.status_code != 429:
                public = run.alias if run.chain.preserve_alias_in_response else model
                count = sum(reason != "blocked" for _, reason in run.attempts)
                return _present(ready, public, model, count)
            decision = self._quota(ready.response, run, rules, model)
            if ready.response.stream is not None:
                await ready.response.stream.aclose()
            delay = decision.retry_after_s
            remaining = run.deadline - self.ports.monotonic()
            if retried or not decision.retry_allowed or delay is None or delay >= remaining:
                return None
            try:
                await asyncio.wait_for(self.ports.sleep(delay), remaining)
            except TimeoutError:
                return None
        return None

    def _exhausted(self, run: _Run, rules: QuotaRules) -> DispatchResponse:
        now = self.ports.monotonic()
        remaining = [deadline - now for deadline in run.retry_at if deadline > now]
        # Порт bool не раскрывает TTL ранее сохранённых блокировок: используем конфиг.
        retry = min(remaining, default=rules.cooldown_default_s)
        retry = min(retry, rules.cooldown_max_s)
        attempts = [{"model": model, "class": reason} for model, reason in run.attempts]
        return DispatchResponse(
            status_code=run.chain.exhausted_status_code,
            headers={
                "Retry-After": str(math.ceil(retry)),
                "x-bridge-fallback-attempts": str(sum(r != "blocked" for _, r in run.attempts)),
            },
            payload={
                "error": {
                    "message": "No eligible fallback candidate succeeded",
                    "type": "rate_limit_error",
                    "code": "fallback_chain_exhausted",
                    "attempts": attempts,
                }
            },
        )
