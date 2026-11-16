"""C0-5 / VER-008: недоступная модель остаётся явным 503, без платного fallback.

Реальные compiler, resolver и HTTP-dispatch; только ingress и transport I/O
заменены локальными портами. Нет xfail, ключей и живых backend.
"""

from __future__ import annotations

import copy
import json
import socket
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import compile_routes_pipeline, passthrough_facade
from core.http_post_context import PostRequestContext
from core.http_post_routing import resolve_post_route
from core.provider_manifest import ModelRule
from tests.test_transport_routing import MODEL, compiled, provider

PAID = "openai-key-2"
NATIVE = ("codex", "droid")


class Recorder:
    def __init__(self, result: Any = None) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.result = result

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return self.result


def _forbidden(*args: Any, **kwargs: Any) -> Any:
    pytest.fail("C0-5 запрещает реальные socket и sleep")


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BRIDGE_MODEL_PENALTIES_PATH", str(tmp_path / "penalties.json"))
    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(time, "sleep", _forbidden)
    monkeypatch.setattr(time, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(time, "time", lambda: 1000.0)


def _compile(enabled: bool = True) -> Any:
    inputs = (
        replace(provider("codex", 100, 0), enabled=enabled),
        replace(provider("droid", 20, 1), enabled=enabled),
        replace(provider(PAID, 0, 2), enabled=False),
        replace(provider("neutral", 100, 3),
                models_overrides=(ModelRule("other-model"),)),
    )
    return compiled(inputs, compiler=_catalog)


def _catalog(header: Any, manifests: Any, **options: Any) -> Any:
    """Здоровый default отделяет отказ модели от глобального отказа fleet."""
    return compile_routes_pipeline.compile_catalog(
        {**header, "default_model": "other-model"}, manifests, **options,
    )


def _model() -> dict[str, Any]:
    record = copy.deepcopy(_compile().fleet["models"][0])
    assert record["id"] == MODEL
    assert record["backend"] == "codex"
    assert record["routing"]["legacy_backend"] == "codex"
    return record


def _adapter(backend: str) -> Any:
    return SimpleNamespace(
        id=backend, kind="synthetic", config={"enabled": backend != PAID},
        preflight=lambda: (True, ""),
        is_healthy=lambda: True,
        get_models=lambda: [SimpleNamespace(id=MODEL)],
    )


def _host(record: dict[str, Any], routing_enabled: bool) -> Any:
    adapters = {backend: _adapter(backend) for backend in (*NATIVE, PAID)}
    circuits = {backend: {"state": "CLOSED"} for backend in adapters}
    penalty = {"is_penalized": False, "remaining_cooldown": 0, "penalized_until": 0}
    return SimpleNamespace(
        FLEET={"models": {MODEL: record}, "backends": {
            backend: adapter.config for backend, adapter in adapters.items()
        }},
        MODEL_ID=MODEL, INTERNAL_MODEL_IDS=(), BACKENDS=adapters,
        PassthroughAdapter=bytes, json=json,
        _resolve_model_alias=lambda *_: None,
        _MODEL_NOTES_FILTER=SimpleNamespace(is_blocked=Recorder(False)),
        _PENALTY_TRACKER=SimpleNamespace(get_model_status=Recorder(penalty)),
        RESILIENCE=SimpleNamespace(snapshot=lambda *_: {"backends": circuits}),
        flag_enabled=lambda _: routing_enabled,
        _strip_passthrough_env=lambda raw, request: (raw, request),
        _client_gone=lambda _: False,
        circuits=circuits,
    )


def _handler() -> Any:
    return SimpleNamespace(
        path="/v1/chat/completions", headers={"X-Transport-Seed": "c0-5"},
        _trace=None, connection=object(), close_connection=False,
        _headers_already_sent=False, _telemetry_meta=Recorder(),
        _reject=Recorder(), _send=Recorder(), _reply_error=Recorder(),
    )


def _seam(monkeypatch: pytest.MonkeyPatch, routing_enabled: bool) -> Any:
    host, handler = _host(_model(), routing_enabled), _handler()
    context = PostRequestContext(handler, host)
    body = {"model": MODEL, "messages": [{"role": "user", "content": "PONG"}]}
    context.prepare_route(json.dumps(body).encode(), body)
    sent: list[str] = []

    def dispatch(route: Any, prepared: Any = None) -> None:
        sent.append(route.model["backend"])
        handler._send(200, {"choices": [{"message": {"content": "PONG"}}]})

    monkeypatch.setattr(passthrough_facade, "begin_post", lambda *_: context)
    monkeypatch.setattr(passthrough_facade, "read_post_request", lambda _: True)
    monkeypatch.setattr(passthrough_facade, "_cleanup_post", lambda _: None)
    monkeypatch.setattr(passthrough_facade, "dispatch_route", dispatch)
    return SimpleNamespace(host=host, handler=handler, context=context, sent=sent)


def _response(seam: Any) -> tuple[int, str]:
    """Пустой ответ или несколько терминальных ответов — отдельный дефект."""
    replies = seam.handler._reject.calls + seam.handler._send.calls
    assert len(replies) == 1, f"ожидался один ответ, получено {replies}"
    args = replies[0][0]
    kind = args[1] if isinstance(args[1], str) else args[1].get("error", {}).get("type", "")
    return args[0], kind


def _post(seam: Any) -> tuple[int, str]:
    passthrough_facade.handle_post(seam.handler, seam.host)
    return _response(seam)


@pytest.mark.parametrize("routing_enabled", (False, True))
def test_all_open_edges_are_deterministic_503(
    monkeypatch: pytest.MonkeyPatch, routing_enabled: bool,
) -> None:
    """OPEN всех допустимых edges не превращается в drop/успех/платный POST."""
    seam = _seam(monkeypatch, routing_enabled)
    for backend in NATIVE:
        seam.host.circuits[backend]["state"] = "OPEN"
    first = _post(seam)
    seam.handler._reject.calls.clear()
    seam.handler._send.calls.clear()
    second = _post(seam)
    assert seam.sent == [], f"недопустимая отправка: {seam.sent}"
    assert first[0] == second[0] == 503
    assert first == second


@pytest.mark.parametrize("routing_enabled", (False, True))
def test_empty_enabled_routes_are_named_503(
    monkeypatch: pytest.MonkeyPatch, routing_enabled: bool,
) -> None:
    seam = _seam(monkeypatch, routing_enabled)
    seam.host.FLEET["models"][MODEL]["routing"]["routes"] = []
    result = _post(seam)
    assert seam.sent == [], f"пустой routes дал fallback: {seam.sent}"
    assert result == (503, "no_enabled_routes")


@pytest.mark.parametrize("routing_enabled", (False, True))
def test_all_disabled_compiler_keeps_model_for_explicit_503(
    monkeypatch: pytest.MonkeyPatch, routing_enabled: bool,
) -> None:
    """Компилятор сохраняет ID, но не оживляет отключённого владельца."""
    result = _compile(enabled=False)
    records = {record["id"]: record for record in result.fleet["models"]}
    assert MODEL in records, "модель silently dropped вместо явного 503"
    assert MODEL not in result.rejected
    assert all(not result.fleet["backends"][bid]["enabled"] for bid in (*NATIVE, PAID))
    seam = _seam(monkeypatch, routing_enabled)
    seam.host.FLEET["models"][MODEL] = records[MODEL]
    for adapter in seam.host.BACKENDS.values():
        adapter.config["enabled"] = False
    status, _ = _post(seam)
    assert seam.sent == []
    assert status == 503


@pytest.mark.parametrize("routing_enabled", (False, True))
@pytest.mark.parametrize("field", ("backend", "legacy_backend"))
def test_owner_mismatch_rejected_before_routing_can_be_dropped(
    monkeypatch: pytest.MonkeyPatch, routing_enabled: bool, field: str,
) -> None:
    seam = _seam(monkeypatch, routing_enabled)
    record = seam.host.FLEET["models"][MODEL]
    target = record if field == "backend" else record["routing"]
    target[field] = PAID
    before = copy.deepcopy(record)
    resolved = resolve_post_route(seam.context)
    assert record == before
    assert resolved is None, "mismatch silently stripped routing instead of HTTP 503"
    assert _response(seam)[0] == 503
    assert seam.sent == []


@pytest.mark.parametrize("routing_enabled", (False, True))
@pytest.mark.parametrize("field", ("backend", "legacy_backend", "disabled_backend"))
def test_mismatch_never_dispatches_disabled_paid_key(
    monkeypatch: pytest.MonkeyPatch, routing_enabled: bool, field: str,
) -> None:
    seam = _seam(monkeypatch, routing_enabled)
    record = seam.host.FLEET["models"][MODEL]
    target = record if field == "backend" else record["routing"]
    target[field] = PAID
    status, _ = _post(seam)
    assert seam.sent == [], f"mismatch скрыт отправкой: {seam.sent}"
    assert status == 503


@pytest.mark.parametrize("routing_enabled", (False, True))
@pytest.mark.parametrize("bypass", (False, True))
def test_notes_blocked_mismatch_stays_503_without_paid_fallback(
    monkeypatch: pytest.MonkeyPatch, routing_enabled: bool, bypass: bool,
) -> None:
    seam = _seam(monkeypatch, routing_enabled)
    seam.host.FLEET["models"][MODEL]["routing"]["legacy_backend"] = PAID
    seam.host._MODEL_NOTES_FILTER.is_blocked = Recorder(True)
    if bypass:
        seam.handler.headers["X-Bypass-Model-Filter"] = "1"
    status, _ = _post(seam)
    assert seam.sent == []
    assert status == 503


@pytest.mark.parametrize("routing_enabled", (False, True))
def test_healthy_route_control_dispatches_once(
    monkeypatch: pytest.MonkeyPatch, routing_enabled: bool,
) -> None:
    """Положительный контроль: harness не превращает любой запрос в 503."""
    seam = _seam(monkeypatch, routing_enabled)
    assert _post(seam)[0] == 200
    assert len(seam.sent) == 1
    assert seam.sent[0] in NATIVE
    assert PAID not in seam.sent
