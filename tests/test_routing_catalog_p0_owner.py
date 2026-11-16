"""C0-6, VER-008/021/026: защищённые контракты, вне P0_ROLLBACK_SLICE.

Веса синтетические, не политика P0. Платные ключи не читаются; Terra
компилируется только из codex manifest. Будущие модули связываются поздно.
"""

from __future__ import annotations

import copy
import importlib
import itertools
import json
import sys
from collections.abc import Iterator
from dataclasses import replace
from email.message import Message
from http.client import HTTPConnection
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
MODEL = "owner-test"
TERRA = "gpt-6.1-terra"
GET_PATHS = ("/v1/models", "/v1/models?provider=local", "/v1/providers/local/v1/models")
VALID_NOTES = "| Модель | Статус |\n|---|---|\n| `owner-test` | OK |\n"


def api(name: str) -> Any:
    return importlib.import_module(name)


def compile_local(providers: Any, model: str = MODEL) -> Any:
    header = json.loads((ROOT / "fleet.json").read_bytes())
    header = {key: header[key] for key in ("schema_version", "image_limits", "admission")}
    header.update(default_model=model, aliases={})
    return api("core.fleet_compiler").compile_catalog(
        header, providers, kinds=api("adapters").ADAPTER_KINDS, env={}, now="2026-11-16T00:00:00Z"
    )


def local_provider(pid: str, weight: int, priority: int, port: int = 9100) -> Any:
    manifest = api("core.provider_manifest")
    return manifest.ProviderManifest(
        provider_id=pid,
        kind="passthrough",
        owned_by="local-owner",
        priority=priority,
        routing=api("core.routing_schema").RoutingConfig(weight),
        transport=manifest.TransportConfig(bridge=manifest.BridgeTransport(f"http://127.0.0.1:{port}/v1")),
        allow_base_url=(api("core.backend_adapter").AllowEntry("http", "127.0.0.1", port, "/v1"),),
        models_overrides=(manifest.ModelRule(MODEL),),
    )


def install_catalog(stand: Any, document: Any) -> None:
    srv, patcher = stand.srv, stand.patcher
    catalog = srv._build_catalog(document)
    registry = api("core.backend_adapter").AdapterRegistry.from_fleet(
        catalog, api("adapters").ADAPTER_KINDS, lambda: catalog, srv
    )
    stand.registries.append(registry)
    patcher.setattr(srv, "FLEET", catalog)
    patcher.setattr(srv, "BACKENDS", registry)
    for adapter in registry.adapters():
        patcher.setattr(adapter, "preflight", lambda: (True, ""))
        patcher.setattr(adapter, "is_healthy", lambda: True)


def dispatch_capture(stand: Any, handler: Any, call: Any) -> None:
    adapter, _, _, model = call
    stand.sends.append((model, adapter.id))
    handler._send(200, {"id": "local-response", "choices": []})


def _handler_type(stand: Any) -> Any:
    class LocalHandler(stand.srv.Handler):
        def _serve_passthrough(self, *args: Any, **kwargs: Any) -> None:
            dispatch_capture(stand, self, args)

        def _serve_resilient(self, backend: str, serve: Any) -> None:
            serve()

        def log_message(self, format: str, *args: object) -> None:
            pass

    return LocalHandler


@pytest.fixture
def stand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    for name, value in {
        "MODEL_NOTES_PATH": str(tmp_path / "notes.md"),
        "BRIDGE_MODEL_NOTES_PATH": str(tmp_path / "notes.md"),
        "BRIDGE_STATE_DIR": str(tmp_path / "state"),
        "BRIDGE_DYNAMIC_CONFIG_PATH": str(tmp_path / "dynamic.json"),
        "BRIDGE_MODEL_PENALTIES_PATH": str(tmp_path / "penalties.json"),
        "BRIDGE_DROID_CATALOG_ENABLED": "1",
    }.items():
        monkeypatch.setenv(name, value)
    (tmp_path / "notes.md").write_text(VALID_NOTES, encoding="utf-8")
    srv = api("server")
    result = SimpleNamespace(srv=srv, patcher=monkeypatch, root=tmp_path, sends=[], registries=[], notes=[])
    _isolate_host(result)
    install_catalog(result, compile_local((local_provider("codex", 7, 1), local_provider("droid", 3, 2))).fleet)
    result.handler = _handler_type(result)
    try:
        yield result
    finally:
        for registry in result.registries:
            registry.shutdown()
        for notes in result.notes:
            close = getattr(notes, "close", None)
            if callable(close):
                close()


def _isolate_host(stand: Any) -> None:
    srv, patcher, root = stand.srv, stand.patcher, stand.root
    patcher.setattr(srv, "_auth_ok", lambda handler: True)
    patcher.setattr(srv, "_shutting_down", False)
    patcher.setattr(srv, "_is_drain_enabled", lambda: False)
    patcher.setattr(srv, "_is_detached_enabled", lambda: False)
    patcher.setattr(srv, "_client_gone", lambda connection: False)
    patcher.setattr(srv, "ADVERTISED_EFFORT_ALIASES", ())
    patcher.setattr(srv, "PROVIDER_SCOPES", {"local": ("local-owner", "openai-codex")})
    patcher.setattr(
        srv,
        "_PENALTY_TRACKER",
        api("core.model_penalty").ModelPenaltyTracker(root / "penalties.json", max_start_fails=1),
    )
    patcher.setattr(srv, "_QUOTA_CB_CACHE", srv.QuotaCircuitBreakerCache(root / "quota.json"))
    notes = srv.ModelNotesFilter(path=root / "notes.md")
    stand.notes.append(notes)
    patcher.setattr(srv, "_MODEL_NOTES_FILTER", notes)
    patcher.setattr(srv, "RESILIENCE", api("core.resilience").ResilienceManager())
    for name in (
        "_telemetry_begin",
        "_telemetry_meta",
        "_telemetry_meta_request",
        "_telemetry_error_response",
        "_log_reject",
    ):
        patcher.setattr(srv.Handler, name, lambda *args, **kwargs: None)
    patcher.setattr(api("core.fallback_http_hook"), "append_models", lambda models, owner: models)


@pytest.fixture(params=[False, True], ids=["routing-off", "routing-on"])
def routing_flag(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> bool:
    value = bool(request.param)
    monkeypatch.setenv("BRIDGE_TRANSPORT_ROUTING_ENABLED", str(value).lower())
    return value


def request_local(stand: Any, path: str, body: Any = None, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    handler = object.__new__(stand.handler)
    raw = json.dumps(body).encode() if body is not None else b""
    handler.path, handler.client_address = path, ("127.0.0.1", 12345)
    handler.headers = Message()
    for key, value in {"Content-Length": str(len(raw)), **(headers or {})}.items():
        handler.headers[key] = value
    handler.rfile, handler.connection = BytesIO(raw), None
    handler._send = Mock()
    handler._delivery_reserved = 0
    (handler.do_POST if body is not None else handler.do_GET)()
    assert handler._send.call_count == 1
    return handler._send.call_args.args[:2]


def request_wire(server: Any, path: str, body: Any = None, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    connection = HTTPConnection("127.0.0.1", server.port, timeout=3)
    try:
        raw = json.dumps(body).encode() if body is not None else None
        connection.request("POST" if body is not None else "GET", path, raw, headers or {})
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


@pytest.mark.parametrize("weights", [(2, 7), (11, 3), (5, 5)])
def test_owner_is_catalog_identity_not_adapter_iteration(
    stand: Any, weights: tuple[int, int], routing_flag: bool
) -> None:
    providers = (local_provider("codex", weights[0], 1), local_provider("droid", weights[1], 2))
    for inputs in itertools.permutations(providers):
        result = compile_local(inputs)
        install_catalog(stand, result.fleet)
        record = stand.srv.FLEET["models"][MODEL]
        owner = record["routing"]["legacy_backend"]
        explanation = api("core.fleet_explain").explain_model(result.sidecar, inputs, MODEL)
        primary = explanation.to_document()["candidates"][0]["provider_id"]
        assert primary == explanation.primary
        assert record["backend"] == primary == owner
        members = list(stand.srv.BACKENDS.models())
        for order in itertools.permutations(members):
            with stand.patcher.context() as scoped:
                scoped.setattr(stand.srv.BACKENDS, "models", lambda: list(order))
                canonical_owner = stand.srv._get_published_models()[MODEL][0].id
                assert canonical_owner == owner


def test_terra_singleton_internal_owner_and_wire_attribute(stand: Any, routing_flag: bool) -> None:
    manifest = api("core.provider_manifest")
    doc = manifest.read_yaml_file(ROOT / "providers.d/codex.yaml")
    codex = manifest.validate_manifest(doc, api("adapters").ADAPTER_KINDS, env={}).manifest
    assert codex is not None
    codex = replace(codex, models_overrides=tuple(rule for rule in codex.models_overrides if rule.model_id == TERRA))
    result = compile_local((codex,), TERRA)
    record = result.fleet["models"][0]
    assert record.get("routing") is None
    assert record["backend"] == result.sidecar["models"][TERRA]["provider"] == "codex"
    install_catalog(stand, result.fleet)
    with api("tests.transport_wire_support").RunningHTTPServer(stand.handler) as server:
        for path in GET_PATHS:
            status, payload = request_wire(server, path)
            assert status == 200
            card = next(card for card in payload["data"] if card["id"] == TERRA)
            assert card["owned_by"] == doc["owned_by"] == "openai-codex"


def open_codex(stand: Any) -> None:
    resilience = api("core.resilience")
    settings = resilience.ResilienceSettings(
        enabled=True, circuit_breaker=True, fail_threshold=1, cooldown_s=3600, cooldown_jitter=0
    )
    stand.clock = SimpleNamespace(now=0.0)
    manager = resilience.ResilienceManager(
        flags=SimpleNamespace(current=lambda: settings), clock=lambda: stand.clock.now
    )
    with manager.acquire("codex") as lease:
        lease.record_failure()
    stand.patcher.setattr(stand.srv, "RESILIENCE", manager)


@pytest.mark.parametrize("path", GET_PATHS)
@pytest.mark.parametrize("droid_open", [False, True])
def test_get_uses_actual_edges_without_healing_or_leasing(
    stand: Any, path: str, droid_open: bool, routing_flag: bool
) -> None:
    open_codex(stand)
    manager = stand.srv.RESILIENCE
    if droid_open:
        with manager.acquire("droid") as lease:
            lease.record_failure()
    stand.clock.now = 3601.0
    before = copy.deepcopy(manager.snapshot(("codex", "droid")))
    acquire = Mock(side_effect=AssertionError("GET must not acquire/heal"))
    stand.patcher.setattr(manager, "acquire", acquire)
    status, payload = request_local(stand, path)
    assert status == 200
    card = next(card for card in payload["data"] if card["id"] == MODEL)
    assert card["available"] is (not droid_open and routing_flag)
    assert manager.snapshot(("codex", "droid")) == before
    assert stand.sends == []
    acquire.assert_not_called()


def test_http_dispatch_keeps_healthy_droid_independent_of_open_codex(stand: Any, routing_flag: bool) -> None:
    if not routing_flag:
        # Без weighted routing проверяется тот же actual edge singleton droid.
        install_catalog(stand, compile_local((local_provider("droid", 7, 1),)).fleet)
    open_codex(stand)
    before = copy.deepcopy(stand.srv.FLEET["models"][MODEL])
    with api("tests.transport_wire_support").RunningHTTPServer(stand.handler) as server:
        status, _ = request_wire(server, "/v1/chat/completions", {"model": MODEL, "messages": []})
    assert status == 200
    assert stand.sends == [(MODEL, "droid")]
    attempted_backend = stand.sends[0][1]
    assert attempted_backend != before["backend"] if routing_flag else attempted_backend == before["backend"]
    assert stand.srv.FLEET["models"][MODEL] == before


def test_protected_file_budgets() -> None:
    checker = api("tests.test_transport_modularity")
    for filename in ("test_routing_catalog_p0_owner.py", "test_model_notes_dispatch.py"):
        source = (ROOT / "tests" / filename).read_bytes()
        assert len(source.splitlines()) <= 300
        assert not [name for name, node in checker.functions(source).items() if checker.exceeds(checker.metrics(node))]
