"""W2-A: fail-fast квота, бюджет выбора и неизменность начатого потока."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pytestmark = pytest.mark.asyncio
SECRET = "fixture-secret-must-not-leak"


class FakeBreaker:
    def __init__(self) -> None:
        self.blocked: set[str] = set()
        self.records: list[tuple[str, float, str]] = []

    def is_blocked(self, model_id: str) -> bool:
        return model_id in self.blocked

    def record_429(self, model_id: str, ttl_s: float, reason: str) -> None:
        self.records.append((model_id, ttl_s, reason))
        self.blocked.add(model_id)


class FakeTransport:
    def __init__(self) -> None:
        self.outcomes: list[Any] = []
        self.calls: list[tuple[dict[str, Any], float | None]] = []

    async def send(self, request: dict[str, Any], timeout: float | None) -> Any:
        self.calls.append((request, timeout))
        result = self.outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return await cast(Callable[[], Awaitable[Any]], result)() if callable(result) else result


def _response(status: int = 200, **kwargs: Any) -> Any:
    from core.quota_fallback_dispatch import DispatchResponse

    return DispatchResponse(status_code=status, **kwargs)


def _setup(env: dict[str, str] | None = None, **overrides: Any) -> Any:
    from core.model_fallback_chain import FallbackCandidate, load_chains
    from core.quota_fallback_dispatch import DispatchPorts, FallbackDispatcher

    env = {"BRIDGE_MODEL_FALLBACK_ENABLED": "true"} if env is None else env
    catalog = load_chains(ROOT / "fallback_chains.d", env=env)
    original = next(iter(catalog.chains.values()))
    chain = replace(
        original,
        candidates=tuple(
            FallbackCandidate(m, "subscription", 1000000) for m in ("model-a", "model-b")
        ),
        disabled_target="model-b",
        **overrides,
    )
    catalog = replace(catalog, chains={"summary-alias": chain})
    breaker, transport, failures, sleeps = FakeBreaker(), FakeTransport(), [], []
    clock = SimpleNamespace(now=0.0)

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.now += seconds

    ports = DispatchPorts(
        send=transport.send,
        breaker=breaker,
        record_start_failure=lambda model, reason: failures.append((model, reason)),
        sleep=sleep,
        monotonic=lambda: clock.now,
    )
    return SimpleNamespace(
        dispatcher=FallbackDispatcher(catalog, ports, env=env),
        transport=transport,
        breaker=breaker,
        failures=failures,
        sleeps=sleeps,
        clock=clock,
        request={"model": "summary-alias", "messages": [{"role": "user", "content": "hello"}]},
    )


@pytest.mark.parametrize("env", [{}, {"BRIDGE_MODEL_FALLBACK_ENABLED": "false"}])
async def test_kill_switch_resolves_disabled_target_with_legacy_penalty(
    env: dict[str, str],
) -> None:
    h = _setup(env)
    upstream = _response(429, body=b"quota resets in 2d 10h")
    h.transport.outcomes = [upstream]
    response = await h.dispatcher.dispatch(h.request)
    assert response.status_code == 429
    assert [call[0]["model"] for call in h.transport.calls] == ["model-b"]
    assert h.transport.calls[0][1] is None
    assert h.failures == [("model-b", "http_429")]
    assert not h.breaker.records and not h.sleeps


@pytest.mark.parametrize("preserve", [True, False])
async def test_configured_weekly_quota_fails_fast_and_preserves_response_contract(
    preserve: bool,
) -> None:
    h = _setup(preserve_alias_in_response=preserve)
    h.transport.outcomes = [
        _response(
            429, payload={"error": {"code": "GoUsageLimitError", "message": "resets in 2d 10h"}}
        ),
        _response(payload={"model": "untrusted-upstream-model", "choices": []}),
    ]
    response = await h.dispatcher.dispatch(h.request)
    assert response.status_code == 200
    assert response.payload["model"] == ("summary-alias" if preserve else "model-b")
    assert response.headers["x-bridge-fallback-model"] == "model-b"
    assert response.headers["x-bridge-fallback-attempts"] == "2"
    assert [call[0]["model"] for call in h.transport.calls] == ["model-a", "model-b"]
    assert h.breaker.records == [("model-a", 208800, "429_quota")]
    assert not h.failures and not h.sleeps
    assert h.request["model"] == "summary-alias"


@pytest.mark.parametrize("wait", ["2", "5", "5.001", None])
async def test_transient_retry_wait_boundary_and_unknown_429(wait: str | None) -> None:
    h = _setup()
    h.transport.outcomes = [
        _response(429, body=b"busy", headers={} if wait is None else {"Retry-After": wait}),
        _response(payload={"choices": []}),
    ]
    response = await h.dispatcher.dispatch(h.request)
    retries = wait is not None and float(wait) <= 5
    assert response.status_code == 200
    assert [call[0]["model"] for call in h.transport.calls] == [
        "model-a",
        "model-a" if retries else "model-b",
    ]
    assert h.sleeps == ([float(wait)] if retries else [])
    assert h.failures == [("model-a", "http_429")]
    assert not h.breaker.records


async def test_transient_retries_once_only_and_honors_configured_wait() -> None:
    h = _setup({"BRIDGE_MODEL_FALLBACK_ENABLED": "true", "BRIDGE_TRANSIENT_429_MAX_WAIT_S": "2"})
    busy = _response(429, body=b"busy", headers={"Retry-After": "2"})
    h.transport.outcomes = [busy, busy, _response()]
    assert (await h.dispatcher.dispatch(h.request)).status_code == 200
    assert [call[0]["model"] for call in h.transport.calls] == ["model-a", "model-a", "model-b"]
    assert h.sleeps == [2]
    assert len(h.failures) == 2


async def _stall() -> Any:
    await asyncio.Event().wait()


async def _broken_stream(kind: str) -> Any:
    if kind == "stream-timeout":
        await _stall()
    raise OSError(SECRET)
    yield {}  # pragma: no cover


@pytest.mark.parametrize("kind", ["failure", "timeout", "stream-failure", "stream-timeout"])
async def test_pre_first_byte_failures_switch_within_configured_budget(kind: str) -> None:
    h = _setup(
        {
            "BRIDGE_MODEL_FALLBACK_ENABLED": "true",
            "BRIDGE_FALLBACK_TOTAL_BUDGET_S": "0.3",
            "BRIDGE_FALLBACK_ATTEMPT_FIRST_BYTE_TIMEOUT_S": "0.03",
        }
    )
    h.dispatcher.ports = replace(h.dispatcher.ports, monotonic=time.monotonic)
    first = OSError(SECRET) if kind == "failure" else _stall
    if kind.startswith("stream"):
        first = _response(stream=_broken_stream(kind))
    h.transport.outcomes = [first, _response()]
    started = time.monotonic()
    assert (await h.dispatcher.dispatch(h.request)).status_code == 200
    assert time.monotonic() - started < 0.3
    assert [call[0]["model"] for call in h.transport.calls] == ["model-a", "model-b"]
    assert h.transport.calls[0][1] == pytest.approx(0.03)


async def test_total_budget_clips_remaining_attempt_and_forbids_retry_sleep() -> None:
    h = _setup(
        {
            "BRIDGE_MODEL_FALLBACK_ENABLED": "true",
            "BRIDGE_FALLBACK_TOTAL_BUDGET_S": "4",
            "BRIDGE_FALLBACK_ATTEMPT_FIRST_BYTE_TIMEOUT_S": "2",
        }
    )

    async def delayed_busy() -> Any:
        h.clock.now = 3
        return _response(429, body=b"busy", headers={"Retry-After": "2"})

    h.transport.outcomes = [delayed_busy, _response()]
    assert (await h.dispatcher.dispatch(h.request)).status_code == 200
    assert [call[1] for call in h.transport.calls] == [2, 1]
    assert not h.sleeps


async def test_exhausted_total_budget_stops_before_next_candidate() -> None:
    h = _setup()

    async def spent() -> Any:
        h.clock.now = 121
        raise TimeoutError(SECRET)

    h.transport.outcomes = [spent]
    response = await h.dispatcher.dispatch(h.request)
    assert response.payload["error"]["code"] == "fallback_chain_exhausted"
    assert len(h.transport.calls) == 1


@pytest.mark.parametrize("preserve", [True, False])
async def test_post_first_byte_never_switches_or_applies_selection_deadline(preserve: bool) -> None:
    h = _setup(preserve_alias_in_response=preserve)
    closed: list[bool] = []

    async def stream() -> Any:
        try:
            yield {"model": "upstream", "choices": [{"delta": {"content": "first"}}]}
            h.clock.now = 999
            yield {"model": "upstream", "choices": [{"delta": {"content": "second"}}]}
            raise OSError(SECRET)
        finally:
            closed.append(True)

    h.transport.outcomes = [_response(stream=stream())]
    response = await h.dispatcher.dispatch(h.request)
    for _ in range(2):
        assert (await anext(response.stream))["model"] == (
            "summary-alias" if preserve else "model-a"
        )
    with pytest.raises(OSError, match=SECRET):
        await anext(response.stream)
    assert len(h.transport.calls) == 1 and closed == [True]


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("blocked", [True, False])
async def test_exhaustion_has_configured_status_retry_after_and_no_secrets(
    status: int, blocked: bool
) -> None:
    h = _setup(exhausted_status_code=status)
    if blocked:
        h.breaker.blocked.update(("model-a", "model-b"))
    else:
        h.transport.outcomes = [
            _response(429, body=f"quota {SECRET}".encode(), headers={"Retry-After": "9"}),
            _response(
                429,
                body=f"quota https://user:{SECRET}@example.test".encode(),
                headers={"Retry-After": "3"},
            ),
        ]
    response = await h.dispatcher.dispatch(h.request)
    assert response.status_code == status
    error = response.payload["error"]
    assert error["code"] == "fallback_chain_exhausted" and error["type"] == "rate_limit_error"
    assert {a["model"] for a in error["attempts"]} == {"model-a", "model-b"}
    assert all(set(a) == {"model", "class"} for a in error["attempts"])
    assert SECRET not in json.dumps(error)
    assert 0 < float(response.headers["Retry-After"]) <= 604800
    if not blocked:
        assert response.headers["Retry-After"] == "3"
    calls = len(h.transport.calls)
    assert (await h.dispatcher.dispatch(h.request)).status_code == status
    assert len(h.transport.calls) == calls


async def test_direct_model_retains_legacy_behavior_and_cancellation_is_not_failover() -> None:
    h = _setup()
    h.transport.outcomes = [_response(429, body=b"quota")]
    assert (await h.dispatcher.dispatch({"model": "direct-model"})).status_code == 429
    assert h.failures == [("direct-model", "http_429")] and not h.breaker.records
    h.transport.outcomes = [_stall]
    task = asyncio.create_task(h.dispatcher.dispatch(h.request))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(h.transport.calls) <= 2


def _scoped(h: Any, scopes: tuple[str, str]) -> None:
    from core.model_fallback_chain import FallbackCandidate

    chain = h.dispatcher.catalog.chains["summary-alias"]
    chain = replace(chain, candidates=tuple(
        FallbackCandidate(c.model, c.cost_class, c.context_window, scope)
        for c, scope in zip(chain.candidates, scopes, strict=True)
    ))
    h.dispatcher.catalog = replace(h.dispatcher.catalog, chains={"summary-alias": chain})


async def test_quota_429_blocks_model_and_its_quota_scope() -> None:
    h = _setup()
    _scoped(h, ("acct", "other"))
    h.transport.outcomes = [
        _response(429, payload={"error": {"code": "GoUsageLimitError", "message": "resets in 2d"}}),
        _response(payload={"choices": []}),
    ]
    response = await h.dispatcher.dispatch(h.request)
    assert response.status_code == 200
    assert [r[0] for r in h.breaker.records] == ["model-a", "scope:acct"]
    assert {r[1] for r in h.breaker.records} == {172800}


async def test_blocked_quota_scope_skips_other_model_of_same_account() -> None:
    h = _setup()
    _scoped(h, ("acct", "acct"))
    h.breaker.blocked.add("scope:acct")
    response = await h.dispatcher.dispatch(h.request)
    assert response.status_code == 429
    assert not h.transport.calls
    assert [a["class"] for a in response.payload["error"]["attempts"]] == ["blocked", "blocked"]


async def test_permission_error_moves_to_next_candidate() -> None:
    h = _setup()
    h.transport.outcomes = [PermissionError("out of scope"), _response(payload={"choices": []})]
    response = await h.dispatcher.dispatch(h.request)
    assert response.status_code == 200
    assert response.headers["x-bridge-fallback-model"] == "model-b"
    assert [call[0]["model"] for call in h.transport.calls] == ["model-a", "model-b"]
    assert not h.failures


async def test_permission_error_on_all_candidates_is_exhaustion_not_crash() -> None:
    h = _setup()
    h.transport.outcomes = [PermissionError("a"), PermissionError("b")]
    response = await h.dispatcher.dispatch(h.request)
    assert response.status_code == 429
    assert [a["class"] for a in response.payload["error"]["attempts"]] == [
        "permission_denied", "permission_denied"]
